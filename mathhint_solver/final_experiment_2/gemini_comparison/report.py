"""저장된 A/B/C/D 응답의 채점·사용량·풀이 검토·오프라인 화면을 생성한다.

모델 학습, 모델 예측, Gemini 요청을 실행하지 않는다.
"""

from collections import Counter
from itertools import combinations
import json
import math
import os
from pathlib import Path

from ...AnswerEvaluation import CHOICES, choice_options, numeric_constant, evaluate_answer, extract_reference
from ...CompareGeneration import DEFAULT_SYSTEM, USAGE_FIELDS, digest, read_json, write_json
from .review import build_reviews, key_conflicts, text_hash, write_cases, write_csv
from .viewer import METHODS, build as build_viewer, href


TOKEN_FIELDS = ("prompt_token_count", "candidates_token_count", "thoughts_token_count",
                "cached_content_token_count", "total_token_count")
TOKEN_LABELS = {"prompt_token_count": "입력", "candidates_token_count": "출력",
                "thoughts_token_count": "추론", "cached_content_token_count": "캐시", "total_token_count": "전체"}


def _finite_count(value):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError(f"토큰 사용량은 미제공(null) 또는 유한한 음이 아닌 수여야 합니다: {type(value).__name__}")
    return value


def _canonical_answer(grade, problem_text):
    if grade.get("predicted_kind") == "choice" and grade.get("predicted_choice") is not None:
        option = choice_options(problem_text).get(CHOICES[grade["predicted_choice"] - 1])
        value = numeric_constant(option) if option else None
        if value is not None:
            return "value:" + format(value, ".10g")
        return "choice:" + str(grade["predicted_choice"])
    if grade.get("predicted_numeric_value") is not None:
        return "value:" + format(grade["predicted_numeric_value"], ".10g")
    return str(grade.get("predicted_answer")) if grade.get("predicted_answer") is not None else None


def build_questions(root, output, config, plan, records):
    root, output = Path(root), Path(output)
    metadata = read_json(root / "data/processed/metadata.json")["records"]
    ids = {split: read_json(root / f"data/processed/splits/{split}.json") for split in ("train", "test")}
    all_ids = ids["train"] + ids["test"]
    if len(set(all_ids)) != len(all_ids) or {row["id"] for row in metadata} != set(all_ids):
        raise ValueError("읽기 화면의 분할/메타데이터 ID가 서로 다릅니다.")
    source = {row["id"]: row for row in metadata}
    split_by_id = {identifier: split for split in ids for identifier in ids[split]}
    plan_by_key = {(row["id"], row["condition"]): row for row in plan}
    if len(plan_by_key) != len(plan):
        raise ValueError("저장 계획의 문항/조건 키가 중복되었습니다.")
    by_key = {}
    for row in records:
        condition = row.get("condition") or next((m["condition"] for m in METHODS if m["key"] == row.get("method")), None)
        key = row["id"], condition
        if key not in plan_by_key or key in by_key:
            raise ValueError(f"저장 응답의 문항/조건이 계획과 다르거나 중복됩니다: {key}")
        by_key[key] = row
    primary_split = config.get("split", "test")
    expected = set(ids[primary_split]) | {row["id"] for row in plan}
    conflicts = key_conflicts(root)
    questions = []
    for identifier in all_ids:
        meta = source[identifier]
        problem_path = root / f"data/processed/problems/{identifier}.txt"
        solution_path = root / f"data/processed/solutions/{identifier}.txt"
        problem = problem_path.read_text(encoding="utf-8-sig")
        solution = solution_path.read_text(encoding="utf-8-sig")
        reference = extract_reference(meta, problem)
        methods = {}
        for method in METHODS:
            key = identifier, method["condition"]
            item, stored = plan_by_key.get(key), by_key.get(key)
            if identifier not in expected:
                methods[method["key"]] = None
                continue
            row = dict(item or {})
            if stored:
                row.update(stored)
            if row.get("problem_text", problem) != problem:
                raise ValueError(f"저장 응답의 문제 원문이 다릅니다: {key}")
            if item and stored and stored.get("input_text") != item["input_text"]:
                raise ValueError(f"실제 입력과 저장된 계획이 다릅니다: {key}")
            row.update(id=identifier, condition=method["condition"], method=method["key"],
                       problem_text=problem, status=row.get("status", "not_run"))
            row.setdefault("input_text", problem if method["condition"] == "A" else "")
            row.setdefault("system_instruction", config.get("system_instruction", DEFAULT_SYSTEM))
            row.setdefault("output_text", "")
            row.setdefault("hint", None)
            row.setdefault("model", config.get("model"))
            row.setdefault("thinking_level", config.get("thinking_level"))
            row["usage"] = {**(row.get("usage") or {})}
            for field in USAGE_FIELDS:
                row["usage"][field] = _finite_count(row["usage"].get(field))
            if row["status"] == "success":
                row["evaluation"] = evaluate_answer(row["output_text"], reference, problem)
                row["display_output_sha256"] = text_hash(row["output_text"])
                if stored and stored.get("evaluation", {}).get("correct") != row["evaluation"]["correct"]:
                    raise ValueError(f"저장 자동채점과 동일 채점기의 재계산이 다릅니다: {key}")
            else:
                row["evaluation"] = {"predicted_answer": None, "correct": None,
                                     "status": "not_evaluated", "reason": "api_not_successful"}
            evidence = conflicts.get(identifier)
            row["correct_ai_supplemental"] = (evaluate_answer(row["output_text"],
                extract_reference({**meta, "answer_text": evidence["mathematically_supported_answer"]}, problem), problem)["correct"]
                if evidence and row["status"] == "success" else row["evaluation"].get("correct"))
            path = output / f"prompt_audit/requests/{identifier}/{method['condition']}.json"
            row["request_path"] = str(path.relative_to(output)) if path.is_file() else None
            methods[method["key"]] = row
        grades = [row["evaluation"]["correct"] for row in methods.values() if row and type(row["evaluation"]["correct"]) is bool]
        answers = [_canonical_answer(row["evaluation"], problem) for row in methods.values() if row and row["status"] == "success"]
        answers = [value for value in answers if value is not None]
        questions.append({"id": identifier, "split": split_by_id[identifier],
                          "metadata": {field: meta.get(field) for field in ("subject", "curriculum", "unit", "subunit", "type", "source")},
                          "problem_text": problem, "reference_answer": meta["answer_text"], "reference_solution": solution,
                          "problem_href": href(problem_path, output / "report.html"), "solution_href": href(solution_path, output / "report.html"),
                          "expected_generation": identifier in expected, "conditions": methods, "methods": list(METHODS),
                          "changed_correctness": len(set(grades)) > 1, "changed_answers": len(set(answers)) > 1,
                          "answer_key_conflict": identifier in conflicts, "key_conflict_evidence": conflicts.get(identifier),
                          "ai_supplemental_answer": conflicts.get(identifier, {}).get("mathematically_supported_answer")})
    return questions, ids


def summaries(questions):
    metric_rows, token_rows = [], []
    for split in ("test", "train"):
        selected = [q for q in questions if q["expected_generation"] and q["split"] == split]
        if not selected:
            continue
        for method in METHODS:
            rows = [q["conditions"][method["key"]] for q in selected]
            successes = [r for r in rows if r["status"] == "success"]
            graded = [r for r in successes if type(r["evaluation"]["correct"]) is bool]
            correct = sum(r["evaluation"]["correct"] for r in graded)
            primary = {"split": split, "condition": method["condition"], "label": method["label"],
                       "expected_count": len(rows), "success_count": len(successes), "graded_count": len(graded),
                       "correct_count": correct, "incorrect_count": len(graded) - correct,
                       "ungradable_count": len(successes) - len(graded),
                       "failed_count": sum(r["status"] not in ("success", "not_run") for r in rows),
                       "pending_count": sum(r["status"] == "not_run" for r in rows),
                       "accuracy_graded": correct / len(graded) if graded else None,
                       "correct_count_ai_supplemental": sum(r["correct_ai_supplemental"] is True for r in graded),
                       "accuracy_ai_supplemental": sum(r["correct_ai_supplemental"] is True for r in graded) / len(graded) if graded else None,
                       "reused_count": sum(r.get("response_origin") in ("reused_exact_request", "reused_control") for r in successes),
                       "new_success_count": sum(r.get("response_origin") not in ("reused_exact_request", "reused_control") for r in successes)}
            for field in TOKEN_FIELDS:
                values = [r["usage"][field] for r in successes if r["usage"][field] is not None]
                total = sum(values) if values else None
                mean = total / len(values) if values else None
                token_rows.append({"split": split, "condition": method["condition"], "token_field": field,
                                   "success_count": len(successes), "provided_count": len(values),
                                   "missing_count": len(successes) - len(values), "sum": total, "mean": mean})
                primary[field + "_mean"] = mean
                primary[field + "_sum"] = total
            metric_rows.append(primary)
    return metric_rows, token_rows


def paired_tests(questions):
    """미완료·채점 불가를 제외한 대응표에 정확 이항 McNemar 검정을 쓴다."""
    rows = []
    for split in ("test", "train"):
        selected = [q for q in questions if q["expected_generation"] and q["split"] == split]
        if not selected:
            continue
        for first, second in combinations(METHODS, 2):
            table = Counter()
            for q in selected:
                a, b = q["conditions"][first["key"]], q["conditions"][second["key"]]
                x, y = a["evaluation"]["correct"], b["evaluation"]["correct"]
                if a["status"] == b["status"] == "success" and type(x) is bool and type(y) is bool:
                    table[int(x), int(y)] += 1
            discordant = table[1, 0] + table[0, 1]
            pvalue = (min(1.0, 2 * sum(math.comb(discordant, i) for i in range(min(table[1, 0], table[0, 1]) + 1)) / 2 ** discordant)
                      if discordant else 1.0) if sum(table.values()) else None
            rows.append({"split": split, "pair": first["condition"] + "-" + second["condition"],
                         "matched_gradable_count": sum(table.values()), "excluded_count": len(selected) - sum(table.values()),
                         "both_correct": table[1, 1], "first_correct_second_wrong": table[1, 0],
                         "first_wrong_second_correct": table[0, 1], "both_wrong": table[0, 0],
                         "discordant_count": discordant, "p_exact_mcnemar": pvalue,
                         "low_power_note": "정오답이 달라진 문항이 적으면 검정력이 낮다. 유의하지 않음은 효과 없음의 증명이 아니다."})
        indices = sorted((i for i, row in enumerate(rows) if row["split"] == split and row["p_exact_mcnemar"] is not None),
                         key=lambda i: rows[i]["p_exact_mcnemar"])
        maximum = 0.0
        for rank, i in enumerate(indices):
            maximum = max(maximum, min(1.0, (len(indices) - rank) * rows[i]["p_exact_mcnemar"]))
            rows[i]["p_holm_within_split"] = maximum
        for row in rows:
            row.setdefault("p_holm_within_split", None)
    return rows


def question_rows(questions):
    rows = []
    for q in questions:
        if not q["expected_generation"]:
            continue
        row = {"id": q["id"], "split": q["split"], **q["metadata"], "original_answer": q["reference_answer"],
               "answer_key_conflict": q["answer_key_conflict"], "ai_supplemental_answer": q["ai_supplemental_answer"],
               "changed_correctness": q["changed_correctness"], "changed_answers": q["changed_answers"],
               "case_tags": ",".join(q["case_tags"])}
        for method in METHODS:
            condition, response = method["condition"], q["conditions"][method["key"]]
            row.update({condition + "_status": response["status"], condition + "_answer": response["evaluation"].get("predicted_answer"),
                        condition + "_correct_original": response["evaluation"].get("correct"),
                        condition + "_correct_ai_supplemental": response.get("correct_ai_supplemental"),
                        condition + "_review_status": response.get("review", {}).get("review_status"),
                        condition + "_response_origin": response.get("response_origin"),
                        condition + "_model_version": response.get("model_version"), condition + "_request_path": response.get("request_path")})
            for field in TOKEN_FIELDS:
                row[condition + "_" + field] = response["usage"][field]
        for first, second in (("B", "A"), ("C", "A"), ("D", "A"), ("C", "B")):
            a, b = row[first + "_total_token_count"], row[second + "_total_token_count"]
            both_succeeded = row[first + "_status"] == row[second + "_status"] == "success"
            row[first + "_minus_" + second + "_total_tokens"] = a - b if both_succeeded and a is not None and b is not None else None
        rows.append(row)
    return rows


def _fmt(value, *, percent=False):
    return "—" if value is None else f"{100*value:.2f}%" if percent else f"{value:,.2f}" if isinstance(value, float) else str(value)


def _plots(output, summary, comparisons):
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/mathhint-mpl")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    font = Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
    if font.is_file():
        font_manager.fontManager.addfont(str(font))
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=str(font)).get_name()
    plt.rcParams.update({"axes.unicode_minus": False, "font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    folder = output / "figures"
    folder.mkdir(exist_ok=True)
    for split in sorted({row["split"] for row in summary}):
        rows = [row for row in summary if row["split"] == split]
        labels = [row["condition"] for row in rows]
        scope = "테스트80" if split == "test" else "학습문항 확장 · 학습자료 예측"
        fig, ax = plt.subplots(figsize=(8, 4.6))
        for i, row in enumerate(rows):
            value = row["accuracy_graded"]
            if value is None:
                ax.text(i, .02, "채점 가능 응답 없음", ha="center", va="bottom", rotation=90, fontsize=8)
            else:
                ax.bar(i, value, color=[".8", ".6", ".4", ".2"][i], edgecolor="black", linewidth=.5)
                ax.text(i, value + .025, f"{value:.1%}\n{row['correct_count']}/{row['graded_count']}", ha="center", fontsize=9)
        ax.set(xticks=range(len(rows)), xticklabels=labels, ylim=(0, 1.18), ylabel="정답 / 채점 가능 성공 응답",
               title=f"{scope} · A/B/C/D 원본 정답표 기준\n미완료·실패는 오답으로 대체하지 않음")
        fig.tight_layout(); fig.savefig(folder / f"accuracy_{split}.png", dpi=200); plt.close(fig)
        fig, axes = plt.subplots(2, 3, figsize=(14, 8))
        for ax, field in zip(axes.flat, TOKEN_FIELDS):
            available = [row[field + "_mean"] for row in rows if row[field + "_mean"] is not None]
            for i, row in enumerate(rows):
                value = row[field + "_mean"]
                if value is None:
                    ax.text(i, .02, "미제공", rotation=90, ha="center", va="bottom", transform=ax.get_xaxis_transform())
                else:
                    ax.bar(i, value, color=[".8", ".6", ".4", ".2"][i], edgecolor="black", linewidth=.5)
                    ax.text(i, value, f"{value:.1f}", ha="center", va="bottom", fontsize=8)
            ax.set(xticks=range(len(rows)), xticklabels=labels, title=TOKEN_LABELS[field] + " 토큰", ylabel="성공 응답의 제공된 값 평균")
            ax.set_ylim(0, max(available) * 1.2 if available and max(available) else 1)
        axes.flat[-1].axis("off")
        fig.suptitle(f"{scope} · API 사용량 · 미제공=null · 전체에 추론 토큰을 더하지 않음")
        fig.tight_layout(); fig.savefig(folder / f"tokens_{split}.png", dpi=200); plt.close(fig)
        selected = [row for row in comparisons if row["split"] == split]
        fig, ax = plt.subplots(figsize=(12, 4.5))
        for name, color in (("B_minus_A_total_tokens", ".7"), ("C_minus_A_total_tokens", ".45"),
                            ("D_minus_A_total_tokens", ".2"), ("C_minus_B_total_tokens", "black")):
            values = [(i, row[name]) for i, row in enumerate(selected) if row[name] is not None]
            if values:
                ax.scatter([i for i, _ in values], [v for _, v in values], marker=".", s=18, color=color, label=name.replace("_total_tokens", ""))
        ax.axhline(0, color=".7", linewidth=.5)
        ax.set(xlabel="고정 문항 순서 (정확한 ID는 문항 CSV)", ylabel="전체 토큰 차이",
               title=f"{scope} · 동일 문항 대응 토큰 차이 · 누락은 연결·0 대체하지 않음")
        if ax.get_legend_handles_labels()[0]:
            ax.legend()
        fig.tight_layout(); fig.savefig(folder / f"token_differences_{split}.png", dpi=200); plt.close(fig)


def run(root, output):
    from .common import load_saved
    root, output = Path(root).resolve(), Path(output).resolve()
    config, plan, records, state = load_saved(output)
    questions, ids = build_questions(root, output, config, plan, records)
    review_rows = build_reviews(root, output, questions)
    cases = write_cases(output, questions)
    summary, token_rows = summaries(questions)
    comparisons = question_rows(questions)
    pairs = paired_tests(questions)
    write_csv(output / "summary.csv", summary)
    write_csv(output / "token_summary.csv", token_rows)
    write_csv(output / "question_comparison.csv", comparisons)
    write_csv(output / "paired_comparison.csv", pairs)
    for split in sorted({row["split"] for row in comparisons}):
        split_rows = [row for row in comparisons if row["split"] == split]
        write_csv(output / f"question_comparison_{split}.csv", split_rows)
    _plots(output, summary, comparisons)
    safe_config = {key: config.get(key) for key in ("model", "thinking_level", "temperature", "max_output_tokens", "system_instruction", "dataset_id")}
    payload = {"schema_version": 2, "experiment_name": "Final Experiment 2 · A/B/C/D", "methods": list(METHODS),
               "config": safe_config, "questions": questions, "test_ids": ids["test"], "train_ids": ids["train"],
               "primary_split": config.get("split", "test"),
               "links": {"readme": "README.md", "comparison_csv": "question_comparison.csv", "raw_responses": "responses.jsonl",
                         "final_report": "../final_report.md" if (output.parent / "final_report.md").is_file() else None}}
    build_viewer(output, payload)
    metrics = {"summary": summary, "paired_comparison": pairs, "token_summary": token_rows,
               "case_count": len(cases), "reasoning_review_rows": len(review_rows),
               "review_status_counts": dict(Counter(row["review_status"] for row in review_rows)),
               "additional_review_api_calls": 0, "report_generation_api_calls": 0,
               "model_training_performed": False, "state": state}
    write_json(output / "metrics.json", metrics)
    _readme(output, config, state, summary, token_rows, pairs, cases, review_rows, questions)
    # 정정표 기반 점수는 원래 API 응답·해시·역사적 채점을 수정하지 않고 별도 재생성한다.
    if (root / "data/curation/answer_key_corrections.json").is_file():
        from mathhint_analysis.VerifiedAnswerKey import get_registry, regrade
        registry_path, corrections = get_registry(root)
        regrade(root, "gemini_comparison", registry_path, corrections)
    return {"summary": summary, "question_count": len(comparisons), "case_count": len(cases),
            "review_rows": len(review_rows), "training_performed": False, "api_calls": 0}


def _readme(output, config, state, summary, tokens, pairs, cases, reviews, questions):
    preflight = read_json(output / "preflight.json") if (output / "preflight.json").is_file() else {}
    policy_path = output / "policy.json"
    if not policy_path.exists():
        policy_path = output.parent / "policy.json"
    policy = (state.get("limiter", {}).get("policy") or
              (read_json(policy_path) if policy_path.is_file() else preflight.get("local_execution_policy", {})))
    execution = "[실행 기록](execution_runs/)" if (output / "execution_runs").is_dir() else "실제 실행 기록은 아직 없음"
    audit = "[요청 감사](prompt_audit/)" if (output / "prompt_audit").is_dir() else "요청 감사는 아직 작성되지 않음"
    preflight_link = "[사전 점검](preflight.json)" if (output / "preflight.json").is_file() else "사전 점검 미실행"
    lines = ["# Gemini A/B/C/D · 문제 풀이 성능과 토큰 사용량", "",
             "A 문제만 · B 선형회귀 예측 상위20 · C 딥러닝 예측 상위20 · D 실제 해설 상위20. 이전 실험의 C 오라클이 이번 D다.", "",
             "먼저 [수식이 표시되는 문항 화면](report.html), [모든 문항 비교](question_comparison.csv), [풀이·오류 사례](case_reports/README.md)를 본다.", ""]
    if state.get("pending_count", 0):
        lines += ["**부분 결과:** 완료 문항은 기존 ID 순서로 실행한 집합이며 무작위 하위표본이 아니다. "
                  "조건별 완료 수가 다르면 전체 평균을 직접 비교하지 말고 공통 완료 문항의 대응 비교를 확인한다. "
                  "미완료가 남아 있는 동안 테스트80 전체에 대한 효과를 결론내리지 않는다.", ""]
    for split in ("test", "train"):
        rows = [row for row in summary if row["split"] == split]
        if not rows:
            continue
        scope = "테스트80문항" if split == "test" else "학습185문항 확장 · 일반화 성능이 아님"
        lines += [f"## {scope}", "", "정답률 분모는 **채점 가능한 성공 응답**이다. 미완료·실패·채점 불가를 오답 또는0토큰으로 바꾸지 않는다.", "",
                  "|조건|성공/계획|채점 가능|정답|정답률|평균 입력|평균 출력|평균 전체|", "|---|---:|---:|---:|---:|---:|---:|---:|"]
        for row in rows:
            lines.append("|" + "|".join([row["label"], f"{row['success_count']}/{row['expected_count']}", str(row["graded_count"]),
                         str(row["correct_count"]), _fmt(row["accuracy_graded"], percent=True),
                         *[_fmt(row[field + "_mean"]) for field in ("prompt_token_count", "candidates_token_count", "total_token_count")]]) + "|")
        lines += ["", f"![정답률](figures/accuracy_{split}.png)", "", f"![토큰 사용량](figures/tokens_{split}.png)", "",
                  f"![문항별 전체 토큰 차이](figures/token_differences_{split}.png)", "",
                  f"[이 범위의 문항별 CSV](question_comparison_{split}.csv)", ""]
    lines += ["## 실행·재사용 상태", "", f"현재 실행 상태: `{state.get('status', state.get('state', '기록 확인 필요'))}`.", "",
              f"성공 {state.get('successful_requests', '미기록')} / 미완료 {state.get('pending_count', '미기록')} 요청. 중단·미완료 사유: {state.get('reason') or '상태 파일 참조'}", "",
              f"요청 모델 `{config.get('model')}` · temperature `{config.get('temperature')}` · thinking `{config.get('thinking_level')}` · 최대 출력 `{config.get('max_output_tokens')}`.", "",
              "정확한 실제 요청 설정과 모델·데이터·예측 해시는 [설정](config.json), " + audit + ", " + execution + "에서 확인한다. "
              "재사용 응답은 원래 실행 시각·출처와 새 호출을 구분했다. 같은 모델 이름이어도 서로 다른 시기의 서비스 내부 가중치가 동일하다고 확인한 것은 아니다.", "",
              f"기존은5초/2작업자였고 이번 저장 정책은 요청 시작 간격 `{policy.get('interval_seconds', '미기록')}`초 / `{policy.get('workers', '미기록')}`작업자다. "
              f"로컬 제한은 RPM `{policy.get('rpm', '미기록')}`, 시간당 `{policy.get('rph', '미기록')}`, 일일 `{policy.get('rpd', '미기록')}`이며 공급자의 확정 한도와 구분한다. "
              f"공급자 제한 확인 여부: `{policy.get('provider_limits_confirmed', False)}`. 현재 확인 가능한 공급자 제한: `"
              + json.dumps(preflight.get("provider_rate_limits", {}), ensure_ascii=False) + "`.", "",
              "확인할 수 없는 TPM·일일 잔여 요청 수는 추정하지 않는다. 잔여 예산이 확인되지 않으면 학습185문항 확장을 실행하지 않는다. "
              + preflight_link + " 및 [정확한 재개 상태](state.json)를 확인한다.", "",
              "[정확한 응답·채점 수](summary.csv) · [모든 사용량·합계·제공 수](token_summary.csv) · [6쌍 대응 비교](paired_comparison.csv) · [재개 상태](state.json)", "",
              "입력·출력·추론·캐시·전체 사용량은 API 필드를 그대로 집계한다. 미제공 값은 null/—이며 평균 분모는 해당 값이 제공된 성공 응답 수다. "
              "추론 토큰이나 캐시 토큰을 전체 토큰에 더하지 않는다. 성공 응답의 집계이므로 사용량이 제공되지 않은 실패·재시도의 총 과금 비용을 측정한 것으로 주장하지 않는다. "
              "모델 자체 계산량을 측정하지 않았으므로 시스템 전체 계산 효율 개선을 주장하지 않는다.", "",
              "## 정답표와 풀이 검토", "",
              "trig_1_010은 원본④와 원본 해설의9/5·②가 충돌한 기존 근거가 있다. 원본 답을 수정하지 않고 원본 기준을 주 점수로 삼았다. "
              "보조 대안 기준의 점수는 summary.csv의 `accuracy_ai_supplemental`에 분리했으며 사람의 확정 답안표라고 주장하지 않는다.", "",
              f"응답별 검토 상태 {len(reviews)}행을 [검토 표](review/status.csv)에 저장했다. 상태 개수: `"
              + json.dumps(dict(Counter(row["review_status"] for row in reviews)), ensure_ascii=False) + "`.", "",
              "답이 맞다는 사실은 풀이의 타당성을 보장하지 않는다. 새 풀이를 충분히 검증하지 못한 경우 보류로 남겼다. 과거 AI 검토는 완전히 같은 A 응답에만 연결하며 새 B/C/D로 옮기지 않는다. 추가 검토 API 호출은0회다.", "",
              "[사례별 원본·네 풀이 전체](case_reports/README.md) · [검토 기준과 한계](review/README.md)", "",
              "## 대응 비교의 해석", "",
              "A↔B/A↔C/A↔D/B↔C/B↔D/C↔D에서 양쪽 모두 성공·채점 가능한 문항만 대응시켰다. McNemar의 정확 이항 p값과 split별6검정 Holm 보정값을 기록했다. "
              "정오답 변화 문항이 적으면 검정력이 낮으며, 유의하지 않다고 효과가 없다고 확정할 수 없다. 같은 자료에서 여러 결과를 관찰한 탐색 연구이며 가설 확증으로 과장하지 않는다.", "",
              "## 화면을 여는 방법", "",
              "GitHub의 HTML 파일 페이지는 실행 화면이 아니다. **저장소 전체 ZIP을 압축 해제**한 뒤 `results/final_experiment_2/gemini_comparison/report.html`을 브라우저에서 연다. "
              "같은 폴더의 `viewer_assets/`와 기존 `mathhint_analysis/viewer_assets/vendor/`의 Markdown·KaTeX·폰트가 함께 필요하다. HTML 하나만 내려받으면 수식이 표시되지 않는다. "
              "인터넷·서버·로그인·추가 Gemini 요청 없이 작동한다. 임의 HTML은 실행하지 않으며 수식 실패는 원문과 실패 표시로 남긴다.", "",
              "## 재개·보고서 재생성", "", "저장 결과만 다시 읽는 명령은 다음과 같다. 새 모델 학습이나 API 호출은 없다.", "",
              "```bash", "python -m mathhint_solver.final_experiment_2.gemini_comparison report",
              "python -m mathhint_solver.final_experiment_2.gemini_comparison verify", "```", "",
              "실제 호출은 별도로 실행한다. 프로젝트 solver 의존성을 설치하고 안전한 환경변수 `GEMINI_API_KEY`를 설정한다. "
              "preflight는 모델 지원·인증을 모델 조회 API로 확인하지만 풀이를 생성하지 않는다. generate만 미완료 풀이를 요청한다.", "",
              "```bash", "python -m mathhint_solver.final_experiment_2.gemini_comparison preflight",
              "python -m mathhint_solver.final_experiment_2.gemini_comparison generate", "```", "",
              "중단 파일이 남아 있다면 state.json의 정확한 재개 명령에 있는 `--clear-stop`을 사용한다. "
              "현재 통신 제한 시간과 재시도·요청 예산은 실행별 execution_runs 기록을 확인한다.", "",
              "generate는 같은 요청의 성공 기록을 건너뛰고 미완료만 처리한다. report/verify는 모델 학습이나 새 API 호출을 시작하지 않는다. "
              "실행 환경이 종료된 뒤 스스로 계속 실행되거나 별도 예약이 설정됐다고 가정하지 않는다."]
    traces = ["", "## 응답의 실행 시기와 보고 모델 버전", "",
              "요청 모델 ID와 API 응답의 model_version은 별개다. 미제공 버전을 추정하지 않는다. 원래 시각을 유지한 재사용과 신규 호출을 구분한다.", "",
              "|범위|조건|재사용 / 신규 성공|API 보고 모델 버전|성공 응답 시작 시각 범위|", "|---|---|---:|---|---|"]
    for row in summary:
        matching = [q["conditions"][method["key"]] for q in questions if q["expected_generation"] and q["split"] == row["split"]
                    for method in METHODS if method["condition"] == row["condition"]
                    and q["conditions"][method["key"]]["status"] == "success"]
        versions = Counter(r.get("model_version") or "미제공" for r in matching)
        timestamps = sorted(str(r["started_at"]) for r in matching if r.get("started_at"))
        trace = " / ".join(f"{key} ({value})" for key, value in sorted(versions.items())) or "성공 응답 없음"
        interval = (timestamps[0] + " ~ " + timestamps[-1]) if timestamps else "미제공"
        traces.append(f"|{row['split']}|{row['condition']}|{row['reused_count']} / {row['new_success_count']}|{trace}|{interval}|")
    lines += traces
    if (output / "extension_train185/README.md").is_file():
        lines += ["", "[별도 보관한 학습185문항 확장 결과](extension_train185/README.md)"]
    (output / "README.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
