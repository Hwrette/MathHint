"""저장된 최종 실험을 집계한다. API를 호출하거나 학습을 다시 수행하지 않는다.

실행: python -m mathhint_analysis.AnalyzeThreeWay
완료된 응답과 아직 없는 응답, 원본 정답표와 AI 보조 판정은 구분한다.
"""

from __future__ import annotations

from collections import Counter
import csv
import hashlib
import json
import os
from pathlib import Path

from .ExperimentMetrics import answer_metrics, exact_mcnemar, usage_summary, wilson_interval, record_correct as correct
from mathhint_solver.AnswerEvaluation import evaluate_answer
from mathhint_solver.GenerationAudit import audit_generation

ROOT = Path(__file__).resolve().parents[1]
RUN_ROOT = ROOT / "results/final_experiment"
METHODS = ("baseline", "regression_hint", "oracle_hint")
CONDITIONS = dict(zip(METHODS, "ABC"))
NAMES = {"baseline": "A 문제만", "regression_hint": "B 예측 상위20토큰", "oracle_hint": "C 실제 해설 상위20토큰"}
TOKENS = {"prompt_token_count": "입력", "candidates_token_count": "출력", "thoughts_token_count": "추론", "total_token_count": "전체"}
LEGACY = ROOT / "results/model_comparison_2026-11-07/03_Gemini비교"
CONFLICTS = LEGACY / "원본정답표_오류근거.json"


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_csv(path, rows, fields=None):
    fields = fields or (list(rows[0]) if rows else ["id"])
    with Path(path).open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path):
    if not Path(path).exists():
        return []
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def reader_opening_guide():
    return ("GitHub 파일 페이지는 HTML 소스를 보여주며 읽기 화면을 실행하지 않는다. "
            "저장소 ZIP 전체를 압축 해제하거나 clone한 뒤, 이 안내와 같은 폴더의 `03_gemini/report.html`을 브라우저에서 연다. "
            "화면만 보려면 `report.html`과 그 파일 기준 `../viewer_assets/`를 같은 상대 구조로 함께 보존해야 한다. "
            "HTML 하나만 내려받으면 수식·Markdown 표시 파일이 빠진다. 원문·CSV 링크까지 사용하려면 저장소 전체가 필요하다. "
            "렌더러와 글꼴은 로컬에 포함되어 외부 인터넷 연결은 필요하지 않다.")


def cluster_reading_table(run_root):
    lines = ["|실제 분류 수준|유클리드 군집별 문제|코사인(구면) 군집별 문제|", "|---|---|---|"]
    for level, name in (("curriculum", "과목"), ("unit", "단원"), ("subunit", "세부단원"), ("type", "문제 유형")):
        links = []
        for method in ("euclidean", "spherical"):
            relative = Path("01_clustering/experiments") / f"{level}_{method}" / "clusters.md"
            links.append(f"[군집 목록]({relative.as_posix()})" if (run_root / relative).exists() else "미생성")
        lines.append(f"|{name}|{'|'.join(links)}|")
    return lines


def token_comparison_rows(predicted, actual):
    """저장된 전송 JSON의 순서·값을 비교한다. 빠진 토큰을 0으로 가정하지 않는다."""
    b_rank = {token: i + 1 for i, token in enumerate(predicted)}
    c_rank = {token: i + 1 for i, token in enumerate(actual)}
    tokens = sorted(set(predicted) | set(actual), key=lambda t: (b_rank.get(t, 21), c_rank.get(t, 21), t))
    return [{"token": token, "B_value": predicted.get(token), "B_rank": b_rank.get(token),
             "C_value": actual.get(token), "C_rank": c_rank.get(token),
             "presence": "공통" if token in predicted and token in actual else "B만" if token in predicted else "C만"}
            for token in tokens]


def prompt_token_comparison(run_root, ids, *, preserve_existing=False):
    folder = run_root / "03_gemini/prompt_audit"
    if preserve_existing and (folder / "token_comparison.md").exists():
        return
    lines = ["# B·C에 실제로 전송한 토큰 비교", "",
             "고정 테스트 목록의 첫째·가운데·마지막 문항을 예시로 골랐다. 아래 값과 순위는 보존된 요청 JSON에서 읽었으며 입력 파일을 다시 쓰지 않았다.", "",
             "A에는 문제와 공통 시스템 지시만 제공한다. B와 C는 동일한 상위20토큰 JSON 구조를 사용하고 출처 설명만 다르다. **미전송은 해당 벡터의 빈도가0이라는 뜻이 아니다.** 상위20 선택에서 제외되었거나 표시 반올림 뒤 생략된 항목일 수 있다.", "",
             "순위는 반올림된 값을 다시 정렬한 결과가 아니라 저장된 전송 JSON의 순서다. 값은 읽기 쉽게 최대 소수3자리로 표시하며 정확한 요청 전문은 각 JSON에 있다."]
    for identifier in dict.fromkeys([ids[0], ids[len(ids)//2], ids[-1]]):
        paths = {condition: folder / "requests" / identifier / (condition + ".json") for condition in "ABC"}
        if not all(path.exists() for path in paths.values()):
            continue
        b, c = (read_json(paths[condition])["hint"]["mapping"] for condition in "BC")
        compared = token_comparison_rows(b, c)
        counts = Counter(row["presence"] for row in compared)
        lines += ["", f"## {identifier}", "",
                  " · ".join(f"[{condition} 전체 입력](requests/{identifier}/{condition}.json)" for condition in "ABC"), "",
                  f"B {len(b)}개 / C {len(c)}개, 공통 {counts['공통']}개, B만 {counts['B만']}개, C만 {counts['C만']}개.", "",
                  "|토큰|B 예측 빈도|B 순위|C 실제 빈도|C 순위|포함 상태|", "|---|---:|---:|---:|---:|---|"]
        for row in compared:
            display = lambda value: "미전송" if value is None else f"{value:.3f}".rstrip("0").rstrip(".")
            lines.append(f"|`{row['token']}`|{display(row['B_value'])}|{row['B_rank'] or '—'}|{display(row['C_value'])}|{row['C_rank'] or '—'}|{row['presence']}|")
    (folder / "token_comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def type_case_examples(members):
    """기존 유형 배정에서 설명용 사례만 고른다. 군집이나 매개변수를 바꾸지 않는다."""
    examples = []
    for experiment in sorted({row["experiment"] for row in members if row["level"] == "type"}):
        selected = [row for row in members if row["experiment"] == experiment]
        train = [row for row in selected if row["split"] == "train"]
        groups, labels = {}, {}
        for row in train:
            groups.setdefault(row["cluster"], []).append(row)
            labels.setdefault(row["actual_label"], []).append(row)
        success = [row for row in selected if row["split"] == "test" and row["matches_train_majority"] in (True, "True")]
        def success_key(row):
            group = groups[row["cluster"]]
            purity = max(Counter(r["actual_label"] for r in group).values()) / len(group)
            return (-int(len(group) >= 2), -purity, -len(group), row["id"])
        matched = min(success, key=success_key) if success else None
        mixed = [group for group in groups.values() if len({row["actual_label"] for row in group}) > 1]
        mixed = min(mixed, key=lambda group: (-len({r["actual_label"] for r in group}), -len(group), int(group[0]["cluster"]))) if mixed else []
        representatives = []
        for label in sorted({r["actual_label"] for r in mixed}):
            representatives.append(min((r for r in mixed if r["actual_label"] == label), key=lambda r: r["id"]))
        dispersed = [group for group in labels.values() if len({row["cluster"] for row in group}) > 1]
        dispersed = min(dispersed, key=lambda group: (-len({r["cluster"] for r in group}), -len(group), group[0]["actual_label"])) if dispersed else []
        examples.append({"experiment": experiment, "matched": matched,
                         "mixed": representatives[:2], "mixed_label_count": len({r["actual_label"] for r in mixed}),
                         "dispersed": dispersed})
    return examples


def regression_token_observation(run_root):
    rows = {row["id"]: row for row in read_csv(run_root / "02_regression/question_comparison.csv")}
    if not all(identifier in rows for identifier in ("trig_2_016", "trig_1_043")):
        return []
    good, bad = rows["trig_2_016"], rows["trig_1_043"]
    lines = ["### 실제로 맞히고 놓친 상위 토큰", "",
             "다음은 문항별 CSV의 실제·예측 상위20토큰에서 읽은 빈도다. 예측값은 평가 때의 실수를 소수6자리로 표시했다. ‘상위20 미포함’은 예측 빈도0과 다르다.", "",
             "|문항|토큰|실제 빈도|음수 보정 예측 빈도|상위20 비교|", "|---|---|---:|---:|---|"]
    for row, tokens in [(good, [r"latex:\sin", r"latex:\cos", r"latex:\sqrt", r"latex:\theta", r"latex:\frac"]),
                        (bad, [r"latex:\pi", r"latex:\theta", r"latex:\frac", "latex:0", r"latex:\cos"])]:
        actual = {item["token"]: item["frequency"] for item in json.loads(row["actual_top20"])}
        predicted = {item["token"]: item["frequency"] for item in json.loads(row["predicted_top20"])}
        for token in tokens:
            a, b = actual.get(token), predicted.get(token)
            lines.append(f"|{row['id']}|`{token}`|{number(a,0) if a is not None else '상위20 미포함'}|{number(b,6) if b is not None else '상위20 미포함'}|{'공통' if a is not None and b is not None else '실제에만' if a is not None else '예측에만' if b is not None else '양쪽 상위20 미포함'}|")
    lines += ["", f"**관찰:** `trig_2_016`에서는 sin·cos·sqrt·theta·frac가 양쪽 상위20에 남고 총 공통 토큰이 {good['common_top20_count']}개다. 반면 `trig_1_043`에서는 실제 상위20의 pi·theta·frac를 예측 상위20에 남기지 못하고 0·cos를 높게 예측하며 공통 토큰이 {bad['common_top20_count']}개다.", "",
              "이 사례는 빈도 구성의 재현 차이를 보여준다. 토큰이 수학적으로 중요하다는 판정이나 순서·수식 관계를 이해했다는 증거는 아니며, 이런 토큰 차이가 Gemini 오답의 원인이라고 확정하지 않는다.", "",
              "[높은 유사도 문항의 토큰 그림](02_regression/figures/top_tokens_high_cosine_trig_2_016.png) · [낮은 유사도 문항의 토큰 그림](02_regression/figures/top_tokens_low_cosine_trig_1_043.png)", ""]
    return lines


def number(value, digits=3):
    return "미제공" if value is None else f"{float(value):,.{digits}f}"


def percent(value):
    return "미제공" if value is None else f"{value:.2%}"


def reused(row):
    return row.get("response_origin") in ("reused_control", "reused_exact_request")


def paired_scores(latest, ids, left, right):
    pairs = [(i, correct(latest.get((i, left))), correct(latest.get((i, right)))) for i in ids]
    pairs = [(i, a, b) for i, a, b in pairs if a is not None and b is not None]
    cells = Counter("both_correct" if a and b else "left_only" if a else "right_only" if b else "both_incorrect" for _, a, b in pairs)
    n = len(pairs)
    a, b = sum(x for _, x, _ in pairs), sum(y for _, _, y in pairs)
    return {"left": left, "right": right, "graded_pairs": n, "excluded_pairs": len(ids) - n,
            **{key: cells[key] for key in ("both_correct", "left_only", "right_only", "both_incorrect")},
            "left_correct": a, "right_correct": b, "difference_right_minus_left": (b-a)/n if n else None,
            "left_wilson95": wilson_interval(a, n), "right_wilson95": wilson_interval(b, n),
            "exact_mcnemar_p": exact_mcnemar(cells["left_only"], cells["right_only"]) if n else None,
            "changed_ids": [i for i, a, b in pairs if a != b]}


def supplemental_scores(latest, ids, conflicts_path):
    """원본 응답과 원본 정답표는 수정하지 않고 근거가 있는 충돌만 별도 집계한다."""
    reviewed = dict(latest)
    conflicts = read_json(conflicts_path).get("records", []) if conflicts_path.exists() else []
    conflicts = [c for c in conflicts if c["id"] in ids]
    changes = []
    for conflict in conflicts:
        for method in METHODS:
            key = conflict["id"], method
            if key not in latest:
                continue
            row = latest[key]
            if row["reference_answer_text"] != conflict["original_answer"]:
                raise ValueError("원본 정답표 충돌의 답이 다릅니다: " + conflict["id"])
            source = row.get("reference", {}).get("source", {}).get("source_sha256")
            if conflict.get("source_sha256") and source != conflict["source_sha256"]:
                raise ValueError("정답표 충돌의 원본 파일 해시가 다릅니다: " + conflict["id"])
            evaluation = evaluate_answer(row["output_text"], conflict["mathematically_supported_answer"], row["problem_text"]) if row.get("status") == "success" else row.get("evaluation", {})
            reviewed[key] = {**row, "evaluation": evaluation}
            changes.append({"id": conflict["id"], "method": method, "original": row.get("evaluation"), "supplemental": evaluation})
    return reviewed, {"conflicts": conflicts, "changes": changes,
                      "evidence_sha256": file_hash(conflicts_path) if conflicts_path.exists() else None,
                      "label": "AI 보조 수학 검토 점수; 사람의 확정 판정이 아님", "raw_data_modified": False}


def method_scores(latest, ids):
    result = {}
    for method in METHODS:
        rows = [latest[i, method] for i in ids if (i, method) in latest]
        result[method] = {**answer_metrics(rows, len(ids)), "usage": usage_summary(rows),
                          "new_api_usage": usage_summary([r for r in rows if not reused(r)]),
                          "reused_responses": sum(reused(r) for r in rows),
                          "statuses": dict(Counter(r.get("status") for r in rows)),
                          "model_versions": dict(Counter(r.get("model_version") or "not_provided" for r in rows)),
                          "uses_actual_test_reference_vector": method == "oracle_hint"}
    return result


def review_evidence(folder, latest, *, legacy_dir=None, project_root=ROOT):
    """기존 AI 검토의 대상 원본과 현재 출력이 같을 때만 요약을 재사용한다."""
    legacy = LEGACY if legacy_dir is None else (Path(legacy_dir) if legacy_dir else None)
    summary_path = legacy / "풀이검토_요약.json" if legacy else Path(folder) / "no_legacy_review"
    response_path = legacy / "원본응답_160개.jsonl" if legacy else Path(folder) / "no_legacy_responses"
    result = {"human_reviewed_count": 0, "ai_review": {}, "new_review": None,
              "caveat": "AI 보조 검토는 수학적 증명이나 교사의 확정 판정이 아니다. 검토하지 않은 응답은 미검토다."}
    if summary_path.exists() and response_path.exists():
        old = read_json(summary_path)
        if old.get("source_snapshot", {}).get("sha256") != file_hash(response_path):
            raise ValueError("기존 풀이 검토 대상의 원본 해시가 다릅니다.")
        source_rows = [json.loads(line) for line in response_path.read_text().splitlines() if line.strip()]
        for method in METHODS[:2]:
            originals = [r for r in source_rows if r["method"] == method]
            if len(originals) == 80 and all(all(latest.get((r["id"], method), {}).get(key) == r.get(key) for key in ("output_text", "input_sha256", "problem_text", "reference_answer_text", "model", "thinking_level")) for r in originals):
                result["ai_review"][method] = old["review_kinds"]["ai_suggestion"][method]
        result["legacy_summary_path"] = os.path.relpath(summary_path, project_root)
        result["legacy_source_sha256"] = file_hash(response_path)
    new_path = folder / "solution_review.json"
    if new_path.exists():
        new = read_json(new_path)
        for record in new.get("records", []):
            row = latest.get((record["id"], record["method"]))
            if not row or hashlib.sha256(row.get("output_text", "").encode()).hexdigest() != record.get("output_sha256", record.get("response_sha256")):
                raise ValueError("신규 풀이 검토와 출력 해시가 다릅니다.")
            for quote in record.get("evidence_quotes", [record["quote"]] if record.get("quote") else []):
                if quote not in row.get("output_text", ""):
                    raise ValueError("신규 풀이 검토 인용문이 출력에 없습니다.")
        result["new_review"] = {k:v for k,v in new.items() if k!="records"}
        result["new_review_correct_answer_with_issues"] = [r["id"] for r in new.get("records",[]) if r.get("math_status")=="inappropriate" and r.get("final_answer_original_correct") is True]
        result["new_review_wrong_answer_with_issues"] = [r["id"] for r in new.get("records",[]) if r.get("math_status")=="inappropriate" and r.get("final_answer_original_correct") is False]
        result["new_review_counts"] = {m: dict(Counter(r.get("math_status", "unreviewed") for r in new.get("records", []) if r["method"] == m)) for m in METHODS}
    return result


def analyze(run_root=RUN_ROOT, conflicts_path=None, *, project_root=ROOT, data_root=None, use_legacy=None):
    run_root, project_root = Path(run_root), Path(project_root)
    use_legacy = run_root.resolve() == (project_root / "results/final_experiment").resolve() if use_legacy is None else use_legacy
    folder = run_root / "03_gemini"
    manifest = read_json(folder / "config.json")
    config, config_id = manifest["config"], manifest["config_id"]
    ids = config["test_ids"]
    if len(set(ids)) != len(ids):
        raise ValueError("테스트 ID 중복")
    latest, attempts = {}, Counter()
    path = folder / "responses.jsonl"
    for line in path.read_text().splitlines() if path.exists() else []:
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("config_id") != config_id or row["id"] not in ids or row["method"] not in METHODS:
            raise ValueError("응답 설정·문항·조건이 최종 실험과 다릅니다.")
        key = row["id"], row["method"]
        attempts[key] += 1
        if key in latest and latest[key].get("status") == "success":
            raise ValueError("성공 응답 뒤 같은 조건의 중복 기록이 있습니다.")
        latest[key] = row
    reviewed, adjudication = supplemental_scores(latest, ids, Path(conflicts_path) if conflicts_path else (project_root / "results/model_comparison_2026-11-07/03_Gemini비교/원본정답표_오류근거.json" if use_legacy else run_root / "answer_conflicts.json"))
    comparisons = [("baseline", "regression_hint"), ("baseline", "oracle_hint"), ("regression_hint", "oracle_hint")]
    expected = len(ids) * len(METHODS)
    result = {"config_id": config_id, "settings": config, "test_ids": ids,
              "expected_questions": len(ids), "expected_conditions": expected, "recorded_conditions": len(latest),
              "successful_conditions": sum(r.get("status") == "success" for r in latest.values()),
              "complete": len(latest) == expected and all(r.get("status") == "success" for r in latest.values()),
              "source_key": method_scores(latest, ids),
              "new_api_attempts": [{"id": r["id"], "method": r["method"], "execution": a.get("execution"), "attempt": a.get("attempt"), "status": a.get("status"), "error_type": a.get("error_type"), "total_tokens": a.get("usage",{}).get("total_token_count")} for r in latest.values() if not reused(r) for a in r.get("attempts",[]) if not a.get("request_skipped") and a.get("status")!="skipped"],
              "supplemental_key": {**adjudication, "methods": method_scores(reviewed, ids)},
              "paired_source": {f"{a}_vs_{b}": paired_scores(latest, ids, a, b) for a, b in comparisons},
              "paired_supplemental": {f"{a}_vs_{b}": paired_scores(reviewed, ids, a, b) for a, b in comparisons},
              "review": review_evidence(folder, latest, legacy_dir=(project_root / "results/model_comparison_2026-11-07/03_Gemini비교") if use_legacy else False, project_root=project_root),
              "source_hashes": {"config": file_hash(folder / "config.json"), "responses": file_hash(path) if path.exists() else None},
              "interpretation": ["C는 실제 해설의 상위 토큰을 제공하는 진단 조건이며 일반 예측 성능이나 보장된 이론적 상한이 아니다.",
                                 "회귀 평가는 반올림하지 않는다. API에는 음수 보정 후 반올림 전 값으로 선정한 상위20토큰을 소수 셋째 자리까지 표시한다.",
                                 "원본 정답표와 AI 보조 보정 점수는 분리하며 원본 응답을 수정하지 않는다.",
                                 f"{len(ids)}문항·각 조건 문항당1회 생성이며, 반복 생성의 변동을 측정하지 않았다.",
                                 "이전 테스트 결과를 본 뒤 후속 비교를 설계했다. 학습에 테스트를 넣지 않았지만 완전히 미관찰한 독립 평가라고 주장하지 않는다.",
                                 "미제공 추론 토큰은 null이며 전체 토큰에 추가 합산하지 않는다."]}
    return result, latest, reviewed


def export_tables(folder, result, latest, reviewed):
    ids = result["test_ids"]
    summaries, token_rows, questions = [], [], []
    conflicts = {r["id"]: r for r in result["supplemental_key"]["conflicts"]}
    review_path=folder/"solution_review.json"
    new_reviews={(r["id"],r["method"]):r for r in read_json(review_path).get("records",[])} if review_path.exists() else {}
    for method in METHODS:
        raw, fixed = result["source_key"][method], result["supplemental_key"]["methods"][method]
        summaries.append({"condition": CONDITIONS[method], "method": method, "name": NAMES[method],
            "expected": len(ids), "recorded": raw["recorded_questions"], "successful": raw["successful_responses"],
            "graded": raw["graded_responses"], "correct_original_key": raw["correct"] if raw["graded_responses"] else None,
            "accuracy_original_key": raw["accuracy_on_graded"], "correct_ai_supplemental_key": fixed["correct"] if fixed["graded_responses"] else None,
            "accuracy_ai_supplemental_key": fixed["accuracy_on_graded"], "ungraded_or_missing": raw["ungraded_or_missing"],
            "reused_responses": raw["reused_responses"], "original_accuracy_wilson95": json.dumps(raw["accuracy_on_graded_wilson95"])})
        for field, label in TOKENS.items():
            usage = raw["usage"][field]
            token_rows.append({"condition": CONDITIONS[method], "method": method, "token_field": field, "token_kind": label,
                "successful_responses": usage["successful_responses"], "provided_responses": usage["known_successful_responses"],
                "missing_responses": usage["missing_successful_responses"],
                "sum_when_all_provided": usage["successful_response_strict_total"],
                "sum_of_known": usage["successful_response_known_sum"], "mean_of_known": usage["successful_response_mean"],
                "all_attempts_known_sum": usage["known_sum"], "all_attempts_strict_total": usage["strict_total"]})
    for i in ids:
        first = next((latest[i, m] for m in METHODS if (i, m) in latest), {})
        conflict = conflicts.get(i)
        row = {"id": i, "original_answer": first.get("reference_answer_text"),
               "answer_key_conflict": bool(conflict), "ai_supplemental_answer": conflict.get("mathematically_supported_answer") if conflict else first.get("reference_answer_text")}
        for method in METHODS:
            prefix = CONDITIONS[method]
            raw = latest.get((i, method), {})
            row.update({prefix+"_answer": raw.get("evaluation", {}).get("predicted_answer"),
                prefix+"_correct_original": correct(raw), prefix+"_correct_ai_supplemental": correct(reviewed.get((i, method))),
                prefix+"_status": raw.get("status", "not_run"), prefix+"_model_version": raw.get("model_version"),
                prefix+"_input_sha256": raw.get("input_sha256"), prefix+"_response_origin": raw.get("response_origin"),
                prefix+"_request_path": f"prompt_audit/requests/{i}/{prefix}.json"})
            for field, label in TOKENS.items():
                suffix = {"prompt_token_count": "input", "candidates_token_count": "output", "thoughts_token_count": "thinking", "total_token_count": "total"}[field]
                row[prefix+"_"+suffix+"_tokens"] = raw.get("usage", {}).get(field)
        oracle_review=new_reviews.get((i,"oracle_hint"),{})
        row["C_math_review"]=oracle_review.get("math_status", "unreviewed")
        row["C_math_error_kind"]=oracle_review.get("error_kind")
        row["C_math_review_source"]="solution_review.json" if oracle_review else None
        row["changed_original_correctness"] = len({correct(latest.get((i, m))) for m in METHODS if correct(latest.get((i, m))) is not None}) > 1
        row["changed_final_answers"] = len({str(latest.get((i, m), {}).get("evaluation", {}).get("predicted_answer")) for m in METHODS if (i, m) in latest}) > 1
        for method, prefix in [("regression_hint", "B"), ("oracle_hint", "C")]:
            left, right = row["A_total_tokens"], row[prefix+"_total_tokens"]
            row[prefix+"_minus_A_total_tokens"] = right-left if isinstance(left, (int, float)) and isinstance(right, (int, float)) else None
        questions.append(row)
    write_csv(folder/"summary.csv", summaries)
    write_csv(folder/"token_summary.csv", token_rows)
    write_csv(folder/"question_comparison.csv", questions)
    write_csv(folder/"changed_questions.csv", [r for r in questions if r["changed_original_correctness"] or r["changed_final_answers"]], list(questions[0]))
    write_json(folder/"analysis.json", result)
    return questions


def render_figures(folder, result, questions):
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/mathhint-mpl")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib import font_manager
    from matplotlib.colors import ListedColormap
    font = Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
    if font.exists():
        font_manager.fontManager.addfont(str(font))
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=str(font)).get_name()
    plt.rcParams.update({"axes.unicode_minus": False, "axes.spines.top": False, "axes.spines.right": False})
    figures = folder/"figures"; figures.mkdir(exist_ok=True)
    colors = ["white", "#aaa", "#444"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    for ax, key, title in zip(axes, ("source_key", "supplemental_key"), ("원본 정답표", "AI 보조 보정 정답표")):
        scores = result[key] if key == "source_key" else result[key]["methods"]
        values = [scores[m]["accuracy_on_graded"] for m in METHODS]
        bars = ax.bar(range(3), [v*100 if v is not None else 0 for v in values], color=colors, edgecolor="black")
        ax.set(xticks=range(3), xticklabels=["A 문제만", "B 예측", "C 실제"], ylim=(0,113), ylabel="판독 응답의 정답률 (%)", title=title)
        for b,m,v in zip(bars,METHODS,values):
            ax.text(b.get_x()+b.get_width()/2,b.get_height()+1,"미실행" if v is None else f"{v:.2%}\n{scores[m]['correct']}/{scores[m]['graded_responses']}",ha="center",fontsize=9)
    fig.suptitle("최종 답의 일치도 비교 · 풀이의 타당성과 별도 평가")
    fig.tight_layout(); fig.savefig(figures/"accuracy.png",dpi=180); plt.close(fig)
    fig, axes = plt.subplots(1, 4, figsize=(14,4.3))
    for ax,(field,label) in zip(axes,TOKENS.items()):
        vals = [result["source_key"][m]["usage"][field]["successful_response_mean"] for m in METHODS]
        if all(v is None for v in vals):
            ax.set_axis_off();ax.set_title(label+" 토큰")
            ax.text(.5,.5,"API 미제공\n0으로 추정하지 않음",transform=ax.transAxes,ha="center",va="center")
            continue
        bars=ax.bar(range(3),[v if v is not None else 0 for v in vals],color=colors,edgecolor="black")
        ax.set(xticks=range(3),xticklabels=["A", "B", "C"],title=label+" 토큰",ylabel="제공된 성공 응답의 평균")
        for b,v in zip(bars,vals):ax.text(b.get_x()+b.get_width()/2,b.get_height(),"미제공" if v is None else f"{v:.1f}",ha="center",va="bottom",fontsize=9)
    fig.tight_layout();fig.savefig(figures/"tokens.png",dpi=180);plt.close(fig)
    for start in range(0,len(questions),40):
        rows=questions[start:start+40]
        data=np.array([[1 if r[p+"_correct_original"] is True else 0 if r[p+"_correct_original"] is False else -1 for r in rows] for p in "ABC"])
        fig,ax=plt.subplots(figsize=(15,3.7));ax.imshow(data,cmap=ListedColormap(["#ddd","#222","white"]),vmin=-1,vmax=1,aspect="auto")
        ax.set(yticks=range(3),yticklabels=["A 문제만","B 예측","C 실제"],xticks=range(len(rows)),xticklabels=[r["id"] for r in rows],title="원본 정답표 기준: ○ 정답 / × 오답 / ? 미완료·채점불가")
        ax.tick_params(axis="x",rotation=90,labelsize=8)
        for y in range(3):
            for x in range(len(rows)):ax.text(x,y,"○" if data[y,x]==1 else "×" if data[y,x]==0 else "?",ha="center",va="center",color="white" if data[y,x]==0 else "black",fontsize=8)
        fig.tight_layout();fig.savefig(figures/f"question_outcomes_{start+1:02d}_{start+len(rows):02d}.png",dpi=180);plt.close(fig)
    fig,axes=plt.subplots(2,1,figsize=(15,7),sharex=True)
    for ax,prefix in zip(axes,"BC"):
        vals=[r[prefix+"_minus_A_total_tokens"] for r in questions]
        ax.scatter(range(len(vals)),[np.nan if v is None else v for v in vals],color="#333",s=14)
        ax.axhline(0,color="#888",lw=1);ax.set(ylabel=prefix+" − A 전체 토큰",title="양수면 문제만 제공할 때보다 많은 전체 토큰 사용")
    axes[-1].set_xticks(range(len(questions)),[r["id"] for r in questions],rotation=90,fontsize=7)
    fig.tight_layout();fig.savefig(figures/"question_token_differences.png",dpi=180);plt.close(fig)


def gemini_markdown(result):
    config=result["settings"]
    lines=["# Gemini 세 조건 비교", "",f"성공 응답 **{result['successful_conditions']}/{result['expected_conditions']}개**. 미완료 응답을 오답이나 0토큰으로 바꾸지 않는다.","",
        f"요청 모델 `{config['model']}`, temperature `{config['temperature']}`, thinking `{config['thinking_level']}`, 최대 출력 `{config['max_output_tokens']}`.","",
        "|조건|원본 정답표|정답률|AI 보조 보정표|보조 정답률|미채점·누락|재사용|", "|---|---:|---:|---:|---:|---:|---:|"]
    for m in METHODS:
        a,b=result["source_key"][m],result["supplemental_key"]["methods"][m]
        original = f"{a['correct']}/{a['graded_responses']}" if a["graded_responses"] else "미실행·미채점"
        supplemental = f"{b['correct']}/{b['graded_responses']}" if b["graded_responses"] else "미실행·미채점"
        lines.append(f"|{NAMES[m]}|{original}|{percent(a['accuracy_on_graded'])}|{supplemental}|{percent(b['accuracy_on_graded'])}|{a['ungraded_or_missing']}|{a['reused_responses']}|")
    lines += ["", "정답률은 최종 답의 자동 판독 결과다. 소스 정답표 충돌은 `trig_1_010`이며 원본은 ④, 수학 검토가 지지한 값은 ②(9/5)다. 원본을 고치지 않고 AI 보조 점수를 따로 표시했다.", "",
              "|성공 응답 토큰|A 합계 / 평균|B 합계 / 평균|C 합계 / 평균|", "|---|---:|---:|---:|"]
    for field,label in TOKENS.items():
        cells=[]
        for m in METHODS:
            u=result["source_key"][m]["usage"][field]; cells.append(number(u["successful_response_strict_total"],0)+" / "+number(u["successful_response_mean"],2))
        lines.append("|"+"|".join([label,*cells])+"|")
    lines += ["", "API usage의 입력·출력·추론·전체 필드를 그대로 보존했다. 전체 토큰에는 추론 등을 다시 더하지 않는다. 추론 미제공은 0이 아니다. 합계는 해당 조건 성공 응답 모두에서 값이 제공될 때만 표시한다.", "",
              "|대응 비교|채점된 쌍|왼쪽만 정답|오른쪽만 정답|오른쪽−왼쪽|McNemar p|", "|---|---:|---:|---:|---:|---:|"]
    for row in result["paired_source"].values():
        lines.append(f"|{CONDITIONS[row['left']]} → {CONDITIONS[row['right']]}|{row['graded_pairs']}|{row['left_only']}|{row['right_only']}|{percent(row['difference_right_minus_left'])}|{number(row['exact_mcnemar_p'],4)}|")
    unknown_by_condition={CONDITIONS[m]:result["source_key"][m]["usage"]["total_token_count"]["missing_attempts"] for m in METHODS}
    lines += ["", "전체 토큰이 미제공인 전송 시도(누적 보존 이력): "+" / ".join(f"{c} {n}회" for c,n in unknown_by_condition.items())+". A/B의 이력은 재사용한 과거 실행이며 현재 추가 C 실행과 구분한다. 따라서 이 표의 성공 응답 합계를 모든 시도의 확정 소비량·청구 비용으로 해석하지 않는다."]
    new_attempts=result.get("new_api_attempts",[])
    failed=[a for a in new_attempts if a["status"]!="success"]
    unknown=[a for a in new_attempts if a["total_tokens"] is None]
    if new_attempts:
        resumed_ids=sorted({a["id"] for a in new_attempts if (a.get("execution") or 1)>1})
        if resumed_ids:
            lines += ["", "실패 후 별도 실행에서 재요청한 문항: "+", ".join(f"`{i}` (누적 {sum(a['id']==i for a in new_attempts)}시도)" for i in resumed_ids)+". 성공이 이미 저장된 조건은 다시 요청하지 않았다."]
        lines += ["",f"신규 실험의 기록된 전송 시도 {len(new_attempts)}회 중 실패 기록 {len(failed)}회, 전체 토큰 미제공 시도 {len(unknown)}회다. 성공 응답의 합계는 비교할 수 있지만, 실패 시도의 사용량이 미확인인 경우 전체 청구 비용·소비량은 확정할 수 없다."]
        for a in failed:
            lines.append(f"- `{a['id']}`: `{a['error_type'] or a['status']}` (실행 {a['execution']}, 시도 {a['attempt']}). 서버에서 처리가 끝났는지와 사용량은 응답이 없어 미확인이다. 재개 시 성공 응답을 중복 호출하지 않고 실패 문항만 제한적으로 다시 요청했다면 그 이력을 누적 보존한다.")
    lines += ["", "McNemar 검정은 같은 문제의 정오답 차이에 대한 보조 분석이다. 계획된 세 비교에 다중 비교 보정을 적용하지 않았으며 채점된 쌍이 없으면 산출하지 않는다. 작은 정답 수 차이를 일반적인 개선으로 단정하지 않는다.", "",
              "## 실제 입력과 응답", "", "[입력 감사](prompt_audit/) · [B/C 전송 토큰 나란히 비교](prompt_audit/token_comparison.md) · [80문항 한 행 비교](question_comparison.csv) · [정오답 또는 답이 다른 문항](changed_questions.csv) · [생성 응답](responses.jsonl) · [상세 집계](analysis.json)", "",
              "B/C의 선택·정렬·표시·기본 지시는 같고 벡터의 출처 설명만 달라진다. B는 기존 입력과 설정이 정확히 같을 때만 재사용했다. A/B는 이전 실행을 재사용하고 C는 추가 실험이다. 저장된 C 응답은 A/B와 호출 시점이 다르다. 요청 모델과 실제 반환 model_version을 별도로 저장했으며 제공되지 않은 내부 모델 정보를 검증했다고 주장하지 않는다.", "",
              "응답이 보고한 model_version 분포: " + " / ".join(CONDITIONS[m]+"="+json.dumps(result["source_key"][m]["model_versions"],ensure_ascii=False) for m in METHODS) + ". 이는 반환된 식별자이며 내부 모델 동일성을 증명하지 않는다.", "",
              "## 풀이 타당성", ""]
    reviews=result["review"]["ai_review"]
    for m in METHODS:
        item=reviews.get(m)
        if item:
            r=item["mathematical_appropriateness"]
            lines.append(f"- {NAMES[m]}: 기존 동일 응답의 AI 보조 검토 재사용. 적절 {r['appropriate']}, 부적절 {r['inappropriate']}, 불확실 {r['uncertain']}, 미검토 {r['unreviewed']}. 사람의 확정 검토 0건.")
        elif m=="oracle_hint":
            new=result["review"].get("new_review")
            counts=result["review"].get("new_review_counts",{}).get(m,{})
            reviewed_n=sum(v for k,v in counts.items() if k!="unreviewed")
            pending=max(0,result["source_key"][m]["successful_responses"]-reviewed_n)
            lines.append(f"- {NAMES[m]}: "+(f"신규 AI 보조 검토 적절 {counts.get('appropriate',0)}, 부적절 {counts.get('inappropriate',0)}, 불확실 {counts.get('uncertain',0)}, 미검토 {pending}. [실제 인용·수학 근거](solution_review.json)를 확인한다. 사람의 확정 판정이 아니다." if new else "수학적 풀이 검토 미실시. 최종 답이 맞았다고 풀이가 타당하다고 집계하지 않는다."))
    if result["review"].get("new_review"):
        right_issues=result["review"].get("new_review_correct_answer_with_issues",[])
        wrong_issues=result["review"].get("new_review_wrong_answer_with_issues",[])
        lines += ["", f"C의 부적절 판정은 최종 답이 맞지만 표기·중간 논리에 문제가 있는 {len(right_issues)}건과 최종 오답이면서 풀이에도 문제가 있는 {len(wrong_issues)}건을 포함한다. 표기 오류·뒤에서 재계산한 오류·근거 부족·최종 오답의 error_kind를 구분해 기록했다. 따라서 {len(right_issues)+len(wrong_issues)}건을 모두 최종 오답이나 같은 심각도의 오류로 해석하지 않는다.", "", "신규 C와 기존 A/B는 검토 시점·검토자가 달라 AI 검토 개수 차이를 엄밀히 통제된 성능 차이로 확정하지 않는다. 공식 교육과정 성취기준 전체와 대조하지 않아 교과 범위는 여전히 미확정이다."]
    lines += ["", "기존 AI 검토는 조건을 알 수 있는 상태에서 작성되었으며 독립적인 블라인드 사람 평가가 아니다. 해시·인용 일치는 대상의 동일성을 확인할 뿐 판단의 수학적 정확성을 보증하지 않는다.", "",
              "![정답률](figures/accuracy.png)", "![토큰](figures/tokens.png)", "![문항별 토큰 차이](figures/question_token_differences.png)", "", "## 해석 범위", ""]
    lines += ["- "+note for note in result["interpretation"]]
    return "\n".join(lines)+"\n"


def case_studies(run_root, result, latest, questions, *, project_root=None, data_root=None):
    output=run_root/"04_case_studies";output.mkdir(exist_ok=True)
    project_root = Path(project_root) if project_root is not None else ROOT
    data_root = Path(data_root) if data_root is not None else Path(project_root) / "data"
    metadata={r["id"]:r for r in read_json(data_root/"processed/metadata.json")["records"]}
    regression={r["id"]:r for r in read_csv(run_root/"02_regression/question_comparison.csv")}
    assignments={}
    members=read_csv(run_root/"01_clustering/cluster_members.csv")
    for row in members:
        assignments.setdefault(row["id"],[]).append(row)
    lines=["# 문항 ID로 모든 결과 찾기", "", f"**먼저 [전체 {len(metadata)}문항 수식 읽기 화면](../03_gemini/report.html)을 연다.** 이 문서는 Gemini 비교 대상 {len(questions)}문항의 근거 연결이다. 학습 문항은 읽기 화면에서 검색하며 ‘생성 실험 대상 아님’으로 표시된다. 학습 문항에 누락 응답이 있다는 뜻이 아니다.", "",
           "읽기 화면에서 ID를 검색하고 조건별 정오답·답변 변화 필터로 관심 문항을 고른 뒤, 아래의 원본 문제·해설·A/B/C 요청·회귀·군집 링크로 근거를 확인한다. 원문을 여러 번 복사하지 않고 고정 ID로 연결했다. 군집 번호는 임의 번호이며 서로 다른 실험의 같은 번호가 같은 그룹을 뜻하지 않는다.", "",
           "[군집 성공·실패 관찰](../01_clustering/analysis.md) · [회귀 성공·실패 관찰](../02_regression/analysis.md) · [Gemini 정오답 변화](../03_gemini/changed_questions.csv)", ""]
    index=[]
    for row in questions:
        i=row["id"];meta=metadata[i];reg=regression.get(i,{})
        lines += [f"## {i}", "", " / ".join(meta[k] for k in ("curriculum","unit","subunit","type")), "",
                  f"[읽기 화면](../03_gemini/report.html#{i}) · [원본 문제]({os.path.relpath(data_root / f'processed/problems/{i}.txt', output)}) · [원본 해설]({os.path.relpath(data_root / f'processed/solutions/{i}.txt', output)}) · [출처·분류 포함 텍스트]({os.path.relpath(data_root / f'processed/annotated/{i}.txt', output)})","",
                  f"출처: {meta['source']} · 원본 번호 {meta['original_number']} · 현재 번호 {meta['current_number']}", "",
                  "|조건|답|원본 정오|전체 토큰|실제 입력|", "|---|---|---|---:|---|"]
        for m in METHODS:
            c=CONDITIONS[m];answer=row[c+"_answer"];score=row[c+"_correct_original"]
            lines.append(f"|{NAMES[m]}|{answer if answer is not None else '미실행·미판독'}|{'정답' if score is True else '오답' if score is False else '미채점'}|{number(row[c+'_total_tokens'],0)}|[{c} 요청](../03_gemini/prompt_audit/requests/{i}/{c}.json)|")
        lines += ["",f"[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#{i})에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `{i}` 검색.", ""]
        if reg:
            lines += [f"회귀: 음수 보정 MSE {number(reg.get('clipped_nonnegative_mse'))}, 코사인 {number(reg.get('clipped_nonnegative_cosine_similarity'))}, 상위20 공통 토큰 {reg.get('common_top20_count')}/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.", ""]
        if assignments.get(i):
            lines += ["|군집 실험|배정 군집|학습 다수 라벨과 일치|", "|---|---:|---|"]
            for a in assignments[i]:
                lines.append(f"|[{a['experiment']}](../01_clustering/experiments/{a['experiment']}/clusters.md)|{a['cluster']}|{a['matches_train_majority']}|")
            lines.append("")
        index.append({"id":i,"problem_path":os.path.relpath(data_root / f"processed/problems/{i}.txt",project_root),"solution_path":os.path.relpath(data_root / f"processed/solutions/{i}.txt",project_root), "reader_path":"../03_gemini/report.html#"+i,"case_anchor":"questions.md#"+i, "curriculum":meta["curriculum"],"unit":meta["unit"],"subunit":meta["subunit"],"type":meta["type"], "gemini_changed":row["changed_original_correctness"],"regression_clipped_mse":reg.get("clipped_nonnegative_mse"),"regression_precision_at_20":reg.get("precision_at_20")})
    (output/"questions.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    write_csv(output/"question_index.csv",index)
    changed=[r for r in questions if r["changed_original_correctness"]]
    notes=["# 직접 비교할 사례", "", "선정은 이미 나온 결과를 설명하기 위한 관찰이다. 이 문항을 보고 모델을 다시 선택하거나 학습하지 않았다.", "",
           "## 실제 문제 유형과 군집의 성공·혼합·분산", "",
           "아래는 세부단원이 아닌 과목/단원/세부단원/유형 전체 경로를 비교한다. 학습에서 정한 대표 라벨을 그대로 쓰며 테스트 결과로 모델을 선택하지 않는다."]
    for case in type_case_examples(members):
        experiment=case["experiment"]
        notes += ["", f"### {experiment}", "",
                  f"[이 실험의 모든 군집·문항](../01_clustering/experiments/{experiment}/clusters.md)"]
        matched=case["matched"]
        if matched:
            group=[r for r in members if r["experiment"]==experiment and r["split"]=="train" and r["cluster"]==matched["cluster"]]
            same=sum(r["actual_label"]==matched["actual_label"] for r in group)
            notes.append(f"- **일치 사례:** [{matched['id']}](questions.md#{matched['id']})는 군집{matched['cluster']}에 배정되었고 실제 유형 `{matched['actual_label']}`이 학습 대표 유형과 같다. 해당 학습 군집에서 이 유형은 {same}/{len(group)}문항이다.")
        if case["mixed"]:
            a,b=case["mixed"]
            notes.append(f"- **서로 다른 유형의 혼합:** 학습 군집{a['cluster']}에는 {case['mixed_label_count']}개 실제 유형이 섞였다. [{a['id']}](../../../data/processed/problems/{a['id']}.txt)의 `{a['actual_label']}`과 [{b['id']}](../../../data/processed/problems/{b['id']}.txt)의 `{b['actual_label']}`을 비교한다.")
        dispersed=case["dispersed"]
        if dispersed:
            clusters=sorted({r["cluster"] for r in dispersed},key=int)
            representatives=[min((r for r in dispersed if r["cluster"]==c),key=lambda r:r["id"]) for c in clusters]
            links=" · ".join(f"[{r['id']}](../../../data/processed/problems/{r['id']}.txt)→군집{r['cluster']}" for r in representatives)
            notes.append(f"- **동일 유형의 분산:** `{dispersed[0]['actual_label']}`의 학습 {len(dispersed)}문항이 {len(clusters)}개 군집으로 나뉘었다. {links}.")
    notes += ["", "세부단원 사례와 모든 라벨의 분산도는 [군집 분석](../01_clustering/analysis.md), [라벨 분산 CSV](../01_clustering/label_dispersion.csv)에 있다.", "",
              "## 조건별 정오답이 바뀐 문항", ""]
    for r in changed:
        i=r["id"];notes += [f"- [{i}](questions.md#{i}): "+" / ".join(f"{p}={r[p+'_answer']} ({'정답' if r[p+'_correct_original'] else '오답'})" for p in "ABC" if r[p+"_correct_original"] is not None)]
    notes += ["", "## 벡터 정보와 정오답 변화 관찰", ""]
    categories=[("기본 조건 대비 예측 조건에서 개선된 것으로 보이는 사례",lambda r:r["A_correct_ai_supplemental"] is False and r["B_correct_ai_supplemental"] is True),
        ("예측 조건에서 악화된 것으로 보이는 사례",lambda r:r["A_correct_ai_supplemental"] is True and r["B_correct_ai_supplemental"] is False),
        ("실제 해설 벡터에도 오답이 남은 사례",lambda r:r["C_correct_ai_supplemental"] is False)]
    for title,predicate in categories:
        matched=[r for r in questions if predicate(r)]
        notes += [f"### {title}", ""]
        notes += [" · ".join(f"[{r['id']}](questions.md#{r['id']})" for r in matched) if matched else ("현재 확보된 판독·보조 채점 결과에는 해당 사례가 없다." if result["complete"] else "아직 C 등 미완료 조건이 있어 전체 비교를 확정하지 않는다."), ""]
        both=[r for r in matched if title.startswith("기본 조건 대비") and r["C_correct_ai_supplemental"] is True]
        if both:
            notes += ["위 사례 중 "+", ".join(f"`{r['id']}`" for r in both)+"는 B와 C가 모두 정답이다. 예측 조건에서만 개선되었다는 뜻은 아니다.", ""]
    review_path=run_root/"03_gemini/solution_review.json"
    new_review=read_json(review_path) if review_path.exists() else {}
    invalid=[r for r in new_review.get("records",[]) if r.get("math_status") in ("inappropriate","uncertain")]
    if invalid:
        notes += ["### 신규 C 풀이의 오류·불확실 사례", ""]
        for review in invalid:
            i=review["id"]
            notes += [f"- [{i}](questions.md#{i}): {review['math_status']} / {review.get('error_kind')} / 원본 최종정오={review.get('final_answer_original_correct')} · {review.get('reason','')}"]
        notes += ["", "근거는 [검토 JSON](../03_gemini/solution_review.json)의 실제 출력 인용과 해시를 확인한다. 최종 정오답과 별도인 AI 보조 판단이다."]
    numeric_case=run_root/"03_gemini/prompt_audit/requests/diff_3_004/C.json"
    if numeric_case.exists() and ("diff_3_004","oracle_hint") in latest:
        mapping=read_json(numeric_case).get("hint",{}).get("mapping",{})
        response=latest["diff_3_004","oracle_hint"]
        if "latex:16" in mapping:
            answer=response.get("evaluation",{}).get("predicted_answer")
            notes += ["", f"`diff_3_004`의 실제 C 입력에는 정답16에 직접 연결되는 `latex:16` 빈도 {mapping['latex:16']}도 들어 있지만 최종 출력은 {answer}다. 숫자 토큰의 존재와 올바른 수식 관계·풀이 순서의 생성은 같지 않다는 관찰 사례다. 토큰 때문에 오류가 생겼다는 인과 주장은 아니다."]
    notes += ["", "이 변화만으로 빈도 토큰이 변화의 원인이었다고 확정할 수 없다. 풀이의 실제 인용과 수학적 검토를 함께 확인해야 한다.","",
              "## 이미 확인된 풀이 문제", "", "- `diff_3_004`: 기본 풀이에는 잘못된 중간 등식이 있으나 최종16에 도달한 사례다. 예측 조건의 답32와 구분해 볼 수 있다.",
              "- `diff_2_004`: 기본 풀이가 불가능한 중간 등식을 썼다가 뒤에서 다시 계산해 최종20에 도달한다. 최종 답 일치와 논리적 타당성은 다르다.",
              "- `trig_2_022`: 기본 조건은 주기 안 해의 누락으로 π를 출력했고 기존 예측 조건은 2π를 출력했다. [문항](questions.md#trig_2_022)에서 원문과 각 요청·출력을 비교한다.",
              "- `diff_3_005`: 기본 풀이의 로피탈 사용은 교과 범위 검토 대상으로 남긴다. 다른 풀이의 공식 교육과정 적합성은 단원명만 보고 확정하지 않았다.",
              "- `trig_1_010`: 원본 정답표 충돌 때문에 두 채점 기준이 다른 문항이다. [충돌 근거](../../model_comparison_2026-11-07/03_Gemini비교/원본정답표_오류근거.json)를 먼저 읽는다.","",
              "기존 상세 AI 검토: [원래 검토·인용](../../model_comparison_2026-11-07/03_Gemini비교/AI보조_풀이검토.html). 사람의 검증된 확정 판정이 아니다.",""]
    (output/"selected_cases.md").write_text("\n".join(notes),encoding="utf-8")


def final_report(run_root, result):
    cluster=read_csv(run_root/"01_clustering/summary.csv")
    reg=read_json(run_root/"02_regression/summary.json") if (run_root/"02_regression/summary.json").exists() else None
    config=result["settings"]
    lines=["# MathHint 고2 연구 최종 보고서", "",f"저장된 성공 응답 {result['successful_conditions']}/{result['expected_conditions']}개. "+("응답 확보 완료이며 검토 범위는 아래에 따로 명시한다." if result['complete'] else "아직 미완료인 실험이 있다. 현재 확보된 자료만 집계했다."), "",
           "## 1. 연구 목적 및 가설", "", "수학 문제를 BoW 빈도 벡터로 나타내고, K-means로 교육과정 분류를 재현할 수 있는지, 선형회귀로 해설 빈도를 예측할 수 있는지, 그 정보를 LLM에 제공하면 풀이에 도움이 되는지 확인한다. 가설은 (1) 토큰 구성으로 일부 분류가 묶이고, (2) 예측 해설 토큰이 풀이를 보완하며, (3) 실제 해설 토큰과 비교하면 예측 오차와 표현 방식의 한계를 탐색할 수 있다는 것이다. 효과의 존재나 원인은 결과를 보기 전에 확정하지 않았다.", "",
           "## 2. 데이터 구성과 전처리", "", "그래프·그림 문제를 걸러낸 HML 6개에서 265문항을 확보했다. 고정 학습185·테스트80을 유지하며 ID·분류·출처는 메타데이터로, 문제와 해설은 별도 텍스트로 저장한다. 어휘는 학습 자료에서만 만들었고 문제346·해설431차원이다. 테스트 해설의 새 어휘는 추가하지 않았다. `subject`는 미분/삼각함수 자료군이고 실제 과목은 `curriculum`이다. 라벨 경로는 과목→단원→세부단원→유형을 포함해 동명이인을 합치지 않는다.", "", "[데이터 검증](../../docs/data_validation.json) · [분할](../../data/processed/splits/) · [메타데이터](../../data/processed/metadata.json)", "",
           "## 3. K-means 군집화 실험 방법", "", "분류 단계마다 학습에서 고유 라벨 수를 계산해 k로 정했다. 원시 BoW의 유클리드 K-means와 L2 정규화 입력·정규화 중심을 쓰는 Spherical K-means를 비교한다. 반복100회·시드42~46의5개 재시작을 통제하며 각자의 학습 목적함수로 실행을 선택한다. 테스트의 라벨·ARI·NMI로 시드를 선택하지 않았다. 중심과 군집 대표 라벨은 학습에서만 계산한다. ARI는 우연 일치를 보정한 군집 유사도, NMI는 라벨·군집 사이 정보의 일치도다. 군집 번호 자체는 정답 라벨 번호가 아니다. 학습 다수 라벨 정확도는 보조 지표다.", "",
           "## 4. 군집화 비교 결과와 해석", "", "아래는 고정 테스트80문항의 결과다. 학습·테스트 각각의 수치는 [전체 CSV](01_clustering/summary.csv)에 있다.", "",
           "|분류|방식|k|ARI|NMI|학습 다수 라벨 정확도|관찰된 테스트 군집|", "|---|---|---:|---:|---:|---:|---:|"]
    tests=[r for r in cluster if r["split"]=="test"]
    for r in tests:
        lines.append(f"|{r['level_name']}|{r['method_name']}|{r['k']}|{number(r['ari'],4)}|{number(r['nmi'],4)}|{percent(float(r['train_majority_accuracy']))}|{r['occupied_clusters']}|")
    if tests:
        best=max(tests,key=lambda r:float(r["ari"]));worst=min(tests,key=lambda r:float(r["ari"]))
        lines += ["", f"**관찰:** 이 구성에서 가장 높은 테스트 ARI는 {best['level_name']}·{best['method_name']}의 {number(best['ari'],4)}, 가장 낮은 값은 {worst['level_name']}·{worst['method_name']}의 {number(worst['ari'],4)}다. 이는 서로 다른 k와 라벨 크기의 조건을 단순 순위로 비교한 관찰이며 분류 단계의 난이도를 통제한 인과 비교는 아니다."]
    if tests:
        by={(r["level"],r["method"]):r for r in tests}
        levels=list(dict.fromkeys(r["level"] for r in tests))
        ari_wins=sum(float(by[level,"spherical"]["ari"])>float(by[level,"euclidean"]["ari"]) for level in levels)
        nmi_wins=sum(float(by[level,"spherical"]["nmi"])>float(by[level,"euclidean"]["nmi"]) for level in levels)
        lines += ["",f"구면 방식의 테스트 ARI는 {len(levels)}단계 중 {ari_wins}단계에서 높고, NMI는 {nmi_wins}단계에서 높았다. 따라서 어느 거리 기준이 모든 지표·분류 수준에서 일관되게 우수했다고 해석할 수 없다."]
    lines += ["", "세부 유형은 학습70개·테스트42개이므로 학습185문항에서 유형당 자료가 적다. 높은 k에서는 작은 군집·테스트에 나타나지 않는 라벨이 많고 지표가 불안정할 수 있다. 원시 BoW와 구면 방식 차이가 토큰 수 영향과 관련될 가능성은 있지만 거리·정규화가 함께 바뀐 비교여서 길이만의 원인이라고 확정할 수 없다. 실제 성공·혼합·분산 사례는 [군집 분석](01_clustering/analysis.md), [문항 배정](01_clustering/cluster_members.csv), [군집별 원문 링크](01_clustering/experiments/)로 확인한다.", "",
              "## 5. 선형회귀 모델의 구조 및 실험 방법", "", "문제346차원에서 해설431차원으로 가는 하나의 선형층(가중치·편향)을 MSE로 학습했다. 기존500epoch·Adam·학습률0.01·seed42 모델을 보존하고 동일한 가중치·데이터·출력임을 검증해 재사용한다. 테스트는 가중치 학습에 들어가지 않는다. 학습 평균 해설 벡터 기준선, 원시 실수 예측, 음수를0으로 바꾼 예측을 비교한다. 평가에는 정수 반올림을 하지 않는다.", "",
              "## 6. 회귀 모델의 벡터 예측 성능", "", "|방법|MSE ↓|MAE ↓|평균 코사인 ↑|", "|---|---:|---:|---:|"]
    if reg:
        for name,values in reg["metrics"].items():
            lines.append(f"|{name}|{number(values['mse'],6)}|{number(values['mae'],6)}|{number(values['cosine_similarity'],6)}|")
        top=reg["top_tokens"]
        lines += ["", f"상위20토큰의 평균 공통 개수 {number(top['mean_common_top20_count'],3)}개, Precision@20 {number(top['mean_precision_at_20'],4)}. 양의 값만 선택하고 동률은 고정 어휘 인덱스로 처리한다. 실제 양의 토큰이20개 미만인 문항 {top['actual_fewer_than_20_count']}개이며 Precision@20 분모는20을 유지한다. 선택된 예측 개수를 분모로 한 지표도 별도로 보존했다."]
        mean,clip=reg["metrics"]["training_mean"],reg["metrics"]["clipped_nonnegative"]
        lines += ["",f"**관찰:** 음수 보정의 MSE는 학습 평균 기준선보다 {1-clip['mse']/mean['mse']:.2%} 작았고 평균 코사인은 {clip['cosine_similarity']-mean['cosine_similarity']:.4f} 높았다. MAE는 {clip['mae']:.6f}로 기준선 {mean['mae']:.6f}보다 약간 커서 모든 오차 지표가 개선된 것은 아니다."]
        rows=read_csv(run_root/"02_regression/question_comparison.csv")
        if rows:
            ordered=sorted(rows,key=lambda r:float(r["clipped_nonnegative_cosine_similarity"]))
            low,high=ordered[0],ordered[-1]
            lines += ["",f"예를 들어 `{high['id']}`는 코사인 {float(high['clipped_nonnegative_cosine_similarity']):.4f}·공통 토큰 {high['common_top20_count']}개인 반면 `{low['id']}`는 {float(low['clipped_nonnegative_cosine_similarity']):.4f}·{low['common_top20_count']}개다. 이 순위는 빈도 벡터의 유사도이며 수학적으로 중요한 개념을 맞혔다는 판정은 아니다."]
    lines += ["", "코사인 유사도는 벡터 방향의 유사도이며 문제의 정답률이 아니다. 음수 보정은 BoW의 비음수 성질과 맞지만 빈도 예측 오차가 사라지는 것은 아니다. 공통 대수 기호·일반 표현의 높은 빈도가 수학적으로 필요한 순서·관계를 포착했다는 뜻도 아니다. [문항별 지표·상위 토큰](02_regression/question_comparison.csv), [실제·원시·보정 벡터](02_regression/vectors.json), [성공·실패 및 그래프](02_regression/analysis.md)를 함께 본다.", ""]
    lines += regression_token_observation(run_root)
    lines += [
              "## 7. Gemini API 비교 실험 방법", "", f"테스트80문항에 A문제만, B예측 해설 상위20토큰, C실제 해설 상위20토큰을 제공한다. 요청 모델 `{config['model']}`, temperature `{config['temperature']}`, thinking `{config['thinking_level']}`, 최대 출력 `{config['max_output_tokens']}` 및 시스템 지시·정답 평가를 통제한다. B/C는 동일한 고정 학습 어휘, 양수 토큰 선택·내림차순·동률 어휘순·소수3자리 표시·프롬프트 구조를 사용하며 정보 출처 설명만 다르다. 원시 예측값은 별도로 남긴다.", "", "C는 정답 해설에서 얻은 정보가 포함되는 오라클 진단 조건이다. 정답에 직접 연결되는 토큰이 있을 수 있어 서비스 성능으로 해석하지 않는다. 고정 어휘·상위20으로 정보를 제한하므로 전체 해설을 준 것도 아니고 이론적 성능 상한도 아니다. 기존 A/B 응답은 설정·완성 입력 해시가 같은 경우에만 재사용한다. C는 이번 추가 실험이며 호출 날짜 차이 및 서비스 내부 변경 가능성은 남는다. API 직전 저장된 요청과 SDK 호출 인자는 [입력 감사](03_gemini/prompt_audit/)로 추적하고, 실제 모델 버전은 반환값 범위에서만 기록한다.", "",
              "대표3문항의 B/C 토큰·빈도·순위 차이는 [실제 전송 토큰 비교표](03_gemini/prompt_audit/token_comparison.md)에서 확인한다. 실제 문제 유형의 일치·혼합·분산 사례는 [사례 요약](04_case_studies/selected_cases.md)에 연결했다.", "",
              "## 8. 세 조건의 풀이 성능 및 토큰 사용량 비교", ""]
    gem=gemini_markdown(result)
    table=gem[gem.index("|조건|"):gem.index("## 실제 입력과 응답")]
    lines += [table, ""]
    a,b=result["source_key"]["baseline"],result["source_key"]["regression_hint"]
    if a["graded_responses"] == len(result["test_ids"]) and b["graded_responses"] == len(result["test_ids"]):
        left=a["usage"]["total_token_count"]["successful_response_strict_total"]
        right=b["usage"]["total_token_count"]["successful_response_strict_total"]
        cost=f" 성공 응답에 보고된 전체 토큰은 {left:,}→{right:,}로 {(right-left)/left:.2%} 증가했다." if left and right is not None else ""
        lines += [f"**관찰:** A와 B의 원본 정답 수는 {a['correct']}→{b['correct']}개다."+cost+" 이80문항의 결과에서 예측 힌트가 정답률을 높였다는 증거는 없으며 입력 토큰의 증가는 확인된다. 작은 차이의 일반화·원인은 확정할 수 없다.",""]
    c=result["source_key"]["oracle_hint"]
    if c["graded_responses"]==len(result["test_ids"]):
        lines += [f"**관찰:** 실제 해설 토큰을 제공한 C는 원본 정답표 기준 {c['correct']}/{c['graded_responses']}개로 A보다 {c['correct']-a['correct']:+d}개, B보다 {c['correct']-b['correct']:+d}개 차이가 났다. 정답 해설에서 미리 얻은 정보를 주는 조건이므로 이를 일반적인 서비스 성능으로 비교하거나 원인 하나를 확정할 수 없다. 차이가 작고 문항당1회 생성이므로 예측 오차의 영향과 빈도 표현의 유용성을 탐색하는 참고 결과로 해석한다.", ""]
    review_section=gem[gem.index("## 풀이 타당성"):gem.index("![정답률]")]
    lines += [review_section.replace("## 풀이 타당성","### 풀이 타당성").replace("](solution_review.json)","](03_gemini/solution_review.json)"), ""]
    if not result["complete"]:
        lines += ["**미완료:** C 조건의 응답이 모두 확보되지 않아 실제 해설 정보 자체의 효과와 회귀 예측 오차의 영향을 구분하려던 세 조건 진단은 아직 검증되지 않았다.",""]
    lines += ["모든80문항을 같은 행에서 비교하는 [Gemini CSV](03_gemini/question_comparison.csv), [전체 분석](03_gemini/analysis.md), [조건별 실제 응답](03_gemini/responses.jsonl)을 제공한다. 풀이 타당성의 기존 AI 검토·미검토 범위는 Gemini 분석에 따로 표시했다. 최종 답과 풀이 평가를 합쳐 하나의 정확도로 부르지 않는다.", "",
              "## 9. 실험에서 발견한 문제와 원인에 관한 가설", "", "**확인한 사실:** 원본 정답표와 수학적 도출이 충돌하는 문항1개가 있다. BoW에는 토큰 순서·수식의 구조 관계가 저장되지 않는다. 예측 벡터에는 실제와 다른 빈도가 있고 상위20은 전체 해설의 일부만 남긴다. 최종 답이 맞아도 잘못된 중간 등식을 쓰는 기존 응답 사례가 있다.", "", "**해석·가설:** 예측 힌트의 오차, 이미 강한 기본 모델의 높은 정답률, 자주 나오는 일반 토큰의 제한된 정보, 추가 정보가 만드는 혼란 등이 효과가 작거나 불안정한 이유일 수 있다. C가 B보다 좋아도 예측 오차만이 유일한 원인이라고 확정할 수 없고, C에서도 개선이 작아도 모든 빈도 표현이 무용하다고 결론낼 수 없다. 동일80문항 단일 생성 비교만으로 이러한 원인을 분리해 검증하지 못했다. 조건별 변동 사례는 [직접 분석 자료](04_case_studies/selected_cases.md)와 [ID 연결](04_case_studies/questions.md)을 본다.", "",
              "## 10. 연구의 한계", "", "- 학습185·테스트80의 작은 자료이며 일부 유형은 매우 적다. 그래프가 필요한 문제를 제외해 수학 문제 전체를 대표하지 않는다.", "- 학습과 테스트를 분리했지만 이전 테스트 결과를 이미 본 후 후속 비교를 설계했다. 완전히 새로운 미관찰 최종 평가라고 주장하지 않는다.", "- 각 조건 문항당1회 생성이다. temperature0도 모델 서비스의 완전한 결정성을 보장하지 않으며 반복 생성 분산을 측정하지 않았다.", "- 정답 표기·자동 파싱의 한계와 원본 키 충돌이 있다. AI 보조 판정과 사람의 확정 판정을 구분한다.", "- 풀이 검토에는 AI 판단의 오류·조건 인지 편향이 남고, 공식 성취기준과 전부 대조하지 않아 교육과정 적합성은 다수 미확정이다.", "- C는 실제 정답 해설의 정보를 미리 주는 진단이며 실제 사용 시 제공할 수 있는 정보가 아니다. B/C 모두 학습 어휘 밖 토큰과 순서·수식 구조를 담지 못한다.", "- 토큰 사용량은 API의 제공값이며 미제공 추론 값을0으로 추정하지 않았다. 과거 A/B 재사용과 신규C의 실행 시점 차이가 있다.", "",
              "## 11. 최종 결론 및 후속 연구 방향", "", "이번 연구는 별도의 단순 모델에서 얻은 특징을 LLM에 간접 제공하는 방법을 실제 문항·벡터·응답으로 추적 가능하게 비교했다. 관찰한 점수 차이와 토큰 비용을 함께 보아야 하며 작은 차이만으로 일반적인 성능 개선이나 실패를 확정하지 않는다. BoW 군집·회귀는 일부 빈도 관계를 분석하지만 토큰 순서와 수식의 의미 관계를 직접 표현하지 못한다.", "", "후속으로 다층 신경망 회귀를 고려할 수 있으나 이번 결과만으로 필요성이나 향상을 단정하지 않는다. 실제 해설 조건과 예측 조건의 차이를 먼저 해석해야 한다. 제한된 데이터에서는 작은 모델, 학습 집합 내부 검증 또는 교차검증, 가중치 규제·조기 종료로 과적합을 관리하고 학습/검증 차이를 확인한다. 최종 테스트를 반복적으로 하이퍼파라미터 선택에 쓰지 않으며 단순 평균·선형 기준선보다 개선되는지 검증해야 한다. 층을 늘려도 BoW에서 잃은 순서·수식 구조가 자동 복구되지는 않는다.", "", "고3 연구는 사전학습 LLM의 문맥·순서 관계를 다루는 트랜스포머를 이해하고 디코딩 제약으로 생성을 직접 제어하거나 Lean으로 형식화된 결과를 검증하는 방향으로 확장할 수 있다. 트랜스포머를 처음부터 대규모 학습할 필요는 없다. 이는 빈도 표현의 실패를 미리 단정한 교체가 아니라 간접 특징 제공의 효과를 살핀 뒤 생성의 직접 제어·검증을 탐구하는 연결이다. 디코딩 제약은 잃은 입력 정보를 복원하지 않으며 Lean의 증명 성공이 고교 교육과정 적합성까지 보장하지 않는다. 이번에는 이 후속 모델·파이프라인을 구현하지 않았다.", ""]
    (run_root/"final_report.md").write_text("\n".join(lines),encoding="utf-8")


def _build_final_report(run_root=RUN_ROOT, *, project_root=ROOT, data_root=None, rebuild_figures=False):
    run_root=Path(run_root);folder=run_root/"03_gemini";folder.mkdir(parents=True,exist_ok=True)
    result,latest,reviewed=analyze(run_root, project_root=project_root, data_root=data_root)
    postflight=audit_generation(folder, project=project_root, data_root=data_root, write_output=False)
    if not postflight["verification_passed"]:
        raise ValueError("저장된 요청·응답·선택 데이터가 불일치합니다: " + "; ".join(postflight["violations"][:5]))
    result["api_responses_complete"]=result["complete"]
    result["postflight_verified"]=postflight["verification_passed"] and postflight["all_expected_successful"]
    result["complete"]=result["complete"] and result["postflight_verified"]
    questions=export_tables(folder,result,latest,reviewed)
    prompt_token_comparison(run_root,result["test_ids"], preserve_existing=True)
    if rebuild_figures or not (folder / "figures/accuracy.png").exists():
        render_figures(folder,result,questions)
    (folder/"analysis.md").write_text(gemini_markdown(result),encoding="utf-8")
    case_studies(run_root,result,latest,questions,project_root=project_root,data_root=data_root)
    final_report(run_root,result)
    state="실험 응답 확보 완료" if result["complete"] else "부분 결과 · 미완료 항목 존재"
    binding_reference = "[데이터·모델 연결](experiment.json)" if (run_root / "experiment.json").exists() else "[회귀 모델 출처](02_regression/provenance.json)"
    index=["# MathHint 최종 결과 · [수식 읽기 화면](03_gemini/report.html)", "",
           "**전체 265문항을 ID로 검색한다.** 테스트 80문항은 A 문제만 / B 예측 해설 토큰 / C 실제 해설 토큰을 비교하고, 학습 185문항은 ‘생성 실험 대상 아님’으로 표시한다. 문제·선택지·풀이의 수식과 Markdown을 읽고, 정오답 변화 필터로 관심 문항을 찾을 수 있다.", "",
           f"**{state}: 성공 {result['successful_conditions']}/{result['expected_conditions']}개 응답.**", "",
           reader_opening_guide(), "", "## 처음 → 다음 → 근거", "",
           "|순서|바로 열 자료|", "|---|---|",
           "|처음: 전체 흐름|[최종 한국어 보고서](final_report.md) · [군집 ARI·NMI](01_clustering/summary.csv) · [회귀 MSE·MAE·코사인](02_regression/summary.csv) · [Gemini 정답률](03_gemini/summary.csv) · [토큰 합계·평균](03_gemini/token_summary.csv)|",
           "|다음: 관심 문항 선택|[수식 읽기 화면](03_gemini/report.html) · [80문항 A/B/C 한 행 비교](03_gemini/question_comparison.csv) · [정오답·답변 변화](03_gemini/changed_questions.csv) · [실제·예측 토큰과 오차](02_regression/question_comparison.csv) · [대표 사례](04_case_studies/selected_cases.md)|",
           "|문제 하나의 전체 결과|[80문항 ID별 근거 연결](04_case_studies/questions.md) · [전체 문항 군집 배정 CSV](01_clustering/cluster_members.csv)|",
           f"|자세한 근거|[실제 A/B/C 요청 전문](03_gemini/prompt_audit/requests/) · [B/C 전송 토큰 비교](03_gemini/prompt_audit/token_comparison.md) · [응답 원문](03_gemini/responses.jsonl) · [실제·원시·보정 벡터](02_regression/vectors.json) · {binding_reference}|", "",
           "## 8개 군집 실험의 실제 문항", "", "군집 목록의 문항 ID를 누르면 수식 읽기 화면으로 연결된다. 학습/테스트 구분과 실제 과목·단원·세부단원·유형을 함께 확인한다.", "",
           *cluster_reading_table(run_root), "", "[군집 해석](01_clustering/analysis.md) · [회귀 해석](02_regression/analysis.md) · [Gemini 해석](03_gemini/analysis.md)", "",
           "## 표·그림과 검증 기록", "", "[군집 그림](01_clustering/figures/) · [회귀 그림](02_regression/figures/) · [Gemini 그림](03_gemini/figures/)", "",
           "[전체 산출물 검증](validation.json) · [읽기 화면 브라우저 검증](reader_validation.json) · [핵심 테스트 로그](test_results.txt) · [독립 ML 수식 감사](independent_ml_audit.json)", "",
           "API 오류·미완료·채점불가는 오답이나 0토큰으로 합치지 않는다. 원본 정답표와 AI 보조 보정 점수는 별도다. C는 실제 해설 정보를 제공한 오라클 진단이며 서비스 성능이나 보장된 상한이 아니다. 코사인 유사도는 정답률이 아니다.", "",
           "## 화면과 안내 다시 만들기", "", "`python -m mathhint_learning.RunExperiment view`는 저장된 결과만 읽어 화면·표·안내를 다시 만든다. 학습·모델 재추론·Gemini API 호출은 하지 않으며 보존된 원본 감사 기록을 다시 쓰지 않는다. 설치와 별도 평가·학습·API 준비 명령은 [프로젝트 README](../../README.md)를 따른다.", ""]
    from mathhint_learning.holdout import preserve_navigation
    (run_root/"README.md").write_text(preserve_navigation(run_root/"README.md", "\n".join(index)),encoding="utf-8")
    print(json.dumps({"output":str(run_root),"successful_conditions":result["successful_conditions"],"expected_conditions":result["expected_conditions"],"complete":result["complete"]},ensure_ascii=False))
    return result



def _selected_run_report(run_root, *, project_root, data_root):
    """새 실험에는 그 폴더의 저장 결과만 쓰고 과거 연구의 수치를 대입하지 않는다."""
    metadata = read_json(data_root / "processed/metadata.json")
    train_ids = read_json(data_root / "processed/splits/train.json")
    test_ids = read_json(data_root / "processed/splits/test.json")
    binding_path = run_root / "experiment.json"
    binding = read_json(binding_path) if binding_path.exists() else {}
    name = binding.get("selected", {}).get("name", run_root.name)
    lines = [f"# {name} 저장 결과", "", "이 안내는 선택한 실험 폴더의 파일만 읽어 생성했다. 재학습·모델 재추론·실제 API 호출은 하지 않았다.", "",
             "**먼저 열기:** [수식·Markdown 문항 읽기 화면](03_gemini/report.html). 최종 결과 폴더와 viewer_assets를 함께 두고 브라우저에서 연다. GitHub 파일 페이지는 HTML 실행 화면이 아니다.", "",
             f"데이터 식별자: `{metadata['generation_id']}` · 학습 {len(train_ids)}개 / 테스트 {len(test_ids)}개.", ""]
    if binding_path.exists():
        lines += ["[선택한 데이터·체크포인트·예측 연결](experiment.json)", "", "|자료|실제 선택 경로|", "|---|---|"]
        for key, value in binding.get("artifacts", {}).items():
            if not key.endswith("_sha256"):
                lines.append(f"|{key}|`{os.path.relpath(value, run_root)}`|")
        lines.append("")
    regression = read_csv(run_root / "02_regression/summary.csv")
    lines += ["## 회귀 예측", ""]
    if regression:
        lines += ["|방법|평가 문항|MSE ↓|MAE ↓|코사인 ↑|", "|---|---:|---:|---:|---:|"]
        for row in regression:
            lines.append(f"|{row['method']}|{row['test_count']}|{number(row['mse'],6)}|{number(row['mae'],6)}|{number(row['cosine_similarity'],6)}|")
        lines += ["", "[문항별 실제·예측 토큰과 오차](02_regression/question_comparison.csv) · [실수 벡터](02_regression/vectors.json) · [해석과 그림](02_regression/analysis.md)", "",
                  "원시 횟수는 정수, 회귀 예측은 실수다. 음수 보정 전후를 구분하며 코사인을 정답률로 해석하지 않는다.", ""]
    else:
        lines += ["이 실험 폴더에는 회귀 평가 결과가 아직 없다. 기존 모델이나 예측을 대신 가져오지 않았다.", ""]
    if (run_root / "01_clustering/summary.csv").exists():
        lines += ["## 군집화", "", "[현재 실험의 군집 비교표](01_clustering/summary.csv) · [실제 문항 목록](01_clustering/experiments/)", ""]
    folder = run_root / "03_gemini"
    folder.mkdir(exist_ok=True)
    result = {"complete": False, "generation_prepared": False, "successful_conditions": 0,
              "expected_conditions": len(test_ids) * len(METHODS), "regression_available": bool(regression)}
    lines += ["## Gemini 세 조건", ""]
    if (folder / "config.json").exists():
        result, latest, reviewed = analyze(run_root, project_root=project_root, data_root=data_root, use_legacy=False)
        audit = audit_generation(folder, project=project_root, data_root=data_root, write_output=False)
        if not audit["verification_passed"]:
            raise ValueError("선택한 실험의 요청·응답 감사 불일치: " + "; ".join(audit["violations"][:5]))
        result.update(generation_prepared=True, postflight_verified=audit["verification_passed"],
                      complete=result["complete"] and audit["all_expected_successful"])
        export_tables(folder, result, latest, reviewed)
        prompt_token_comparison(run_root, result["test_ids"], preserve_existing=True)
        lines += [f"성공 응답 {result['successful_conditions']}/{result['expected_conditions']}개. 미실행·실패·미채점은 오답이나0토큰으로 합치지 않는다.", "",
                  "[문항별 세 조건 비교](03_gemini/question_comparison.csv) · [실제 입력](03_gemini/prompt_audit/) · [B/C 전송 토큰 비교](03_gemini/prompt_audit/token_comparison.md)", ""]
        if (folder / "responses.jsonl").exists():
            lines += ["[응답 원문](03_gemini/responses.jsonl)", ""]
        lines += ["|조건|채점 문항|정답|정답률|", "|---|---:|---:|---:|"]
        for method, score in result["source_key"].items():
            lines.append(f"|{NAMES[method]}|{score['graded_responses']}|{score['correct'] if score['graded_responses'] else '미채점'}|{percent(score['accuracy_on_graded'])}|")
        lines += ["", "실제 해설 토큰 조건은 정답 해설 정보를 제공하는 오라클 진단이며 서비스 예측 성능이나 이론적 상한이 아니다.", ""]
    else:
        lines += ["생성 실험은 준비·실행하지 않았다. 읽기 화면의 테스트 문항은 ‘미실행’, 학습 문항은 ‘생성 실험 대상 아님’으로 구분한다. 다른 실험의 응답은 가져오지 않았다.", ""]
    lines += ["## 다음 작업", "", "읽기와 보고서 재생성은 view, 지정 체크포인트 재평가는 evaluate, 별도 경로의 새 학습은 train, API 없는 입력 검증은 prepare로 구분한다. generate를 명시한 경우에만 실제 Gemini를 호출한다.", ""]
    (run_root / "final_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    index = [f"# {name} 결과 · [수식 읽기 화면](03_gemini/report.html)", "", f"전체 {len(metadata['records'])}문항을 ID로 검색한다. 테스트 {len(test_ids)}문항은 A/B/C 비교 대상이며, 학습 {len(train_ids)}문항은 ‘생성 실험 대상 아님’으로 구분한다. 응답이 없으면 ‘미실행’으로 표시한다.", "", reader_opening_guide(), "",
             "## 처음 → 다음 → 근거", "",
             "- [현재 실험의 보고서와 지표](final_report.md)",
             "- [선택한 데이터·모델·예측 연결](experiment.json)" if binding_path.exists() else "- 데이터·모델 연결 정보는 현재 저장 결과의 출처 기록을 따른다."]
    if regression:
        index.append("- [회귀 문항별 실제·예측 토큰과 오차](02_regression/question_comparison.csv) · [실수 벡터](02_regression/vectors.json)")
    if (run_root / "01_clustering/summary.csv").exists():
        index.append("- [군집 비교표](01_clustering/summary.csv) · [군집별 실제 문항](01_clustering/experiments/)")
        index += ["", *cluster_reading_table(run_root), ""]
    if (folder / "config.json").exists():
        index.append("- [Gemini 문항별 비교](03_gemini/question_comparison.csv) · [실제 입력 원문](03_gemini/prompt_audit/)")
    index += ["", "`python -m mathhint_learning.RunExperiment view`로 저장된 결과의 화면과 안내를 다시 만든다. 재학습·모델 재추론·API 호출은 하지 않으며 기존 원본 감사 기록을 다시 쓰지 않는다.", ""]
    (run_root / "README.md").write_text("\n".join(index), encoding="utf-8")
    return result


def build_report(run_root=RUN_ROOT, *, project_root=ROOT, data_root=None, rebuild_figures=False):
    """저장 결과만 읽는다. 선택한 모델의 학습·재추론·API 실행은 하지 않는다."""
    run_root, project_root = Path(run_root), Path(project_root)
    data_root = Path(data_root) if data_root is not None else project_root / "data"
    if not run_root.is_dir():
        raise FileNotFoundError(f"저장 결과 폴더가 없습니다: {run_root}")
    from mathhint_learning.RunExperiment import verify_saved_data
    from mathhint_learning.Experiment import LEGACY_DATA_FINGERPRINT
    from mathhint_learning.TorchData import read_dataset
    data = read_dataset(project_root, data_root)
    verify_saved_data(run_root, data, project_root=project_root)
    canonical = (run_root.resolve() == (project_root / "results/final_experiment").resolve()
                 and data["identity"]["fingerprint"] == LEGACY_DATA_FINGERPRINT)
    if canonical and (run_root / "03_gemini/config.json").is_file():
        result = _build_final_report(run_root, project_root=project_root, data_root=data_root, rebuild_figures=rebuild_figures)
    else:
        result = _selected_run_report(run_root, project_root=project_root, data_root=data_root)
    from .ResultViewer import build_viewer
    build_viewer(project_root, run_root, data_root=data_root)
    from mathhint_learning.ClusterReport import refresh_cluster_reading_links
    refresh_cluster_reading_links(project_root, run_root / "01_clustering", data_root=data_root)
    return result

def main():
    from mathhint_learning.RunExperiment import run
    return run("view")


if __name__ == "__main__":
    main()
