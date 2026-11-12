"""Read frozen prompts and new repeat responses only; no training or API calls."""

from collections import Counter
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics

from ...CompareGeneration import USAGE_FIELDS, file_hash, utc_now
from ..gemini_comparison.common import read_json, read_jsonl, write_json
from .common import API_RECEIVED
from .viewer import LABELS, build as build_viewer, _href


CONTROL_IDS = ("trig_1_040", "trig_1_044", "diff_2_039", "diff_2_004", "trig_1_043")
ERROR_IDS = ("diff_2_039", "diff_3_045", "trig_1_040", "trig_1_044", "trig_1_047",
             "trig_2_020", "trig_3_008", "trig_3_033", "trig_3_036", "trig_2_022", "trig_3_034")
TOKEN_LABELS = {"prompt_token_count": "입력", "candidates_token_count": "출력",
                "thoughts_token_count": "추론", "cached_content_token_count": "캐시", "total_token_count": "전체",
                "tool_use_prompt_token_count": "도구 입력"}
CONTRASTS = (("A", "E"), ("A", "B"), ("A", "C"), ("A", "D"), ("D", "F"))


def csv_rows(path):
    if not Path(path).is_file():
        return []
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError("A planned report table must not be empty: " + str(path))
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def _fmt(value, digits=2):
    if value is None or value == "":
        return "—"
    if isinstance(value, bool):
        return "정답" if value else "오답"
    return f"{value:.{digits}f}" if isinstance(value, float) else str(value)


def _cell(value):
    return str(value if value is not None else "—").replace("|", "\\|").replace("\n", "<br>")


def _bool(value):
    return {"True": True, "False": False, "": None, None: None}.get(value, value if type(value) is bool else None)


def _key(row):
    return row["id"], row["condition"], int(row["repeat"])


def _stats(values):
    values = [v for v in values if v is not None]
    if not values:
        return {"provided_count": 0, "mean": None, "min": None, "max": None, "std": None, "sum": None}
    return {"provided_count": len(values), "mean": statistics.mean(values), "min": min(values), "max": max(values),
            "std": statistics.stdev(values) if len(values) > 1 else None, "sum": sum(values)}


def _new_reviews(output, records):
    path = Path(output) / "review/curated_reviews.json"
    if not path.is_file():
        return {}
    by_key = {_key(r): r for r in records}
    payload = read_json(path)
    result = {}
    for review in payload.get("records", []):
        key = _key(review)
        row = by_key.get(key)
        if key in result or row is None or row.get("status") not in API_RECEIVED:
            raise ValueError("New review is duplicated or has no received new response: " + str(key))
        text = row.get("output_text") or ""
        if review.get("response_sha256") != hashlib.sha256(text.encode()).hexdigest():
            raise ValueError("New review response hash mismatch: " + str(key))
        if any(not isinstance(q, str) or q not in text for q in review.get("evidence_quotes", [])):
            raise ValueError("New review quote not in actual new output: " + str(key))
        result[key] = review
    return result


def case_findings(output, records):
    """Load optional new comparative prose only when all12 referenced outputs match."""
    path = Path(output) / "review/curated_reviews.json"
    if not path.is_file():
        return {}
    findings = read_json(path).get("case_findings", {})
    if not isinstance(findings, dict):
        raise ValueError("case_findings must be a dictionary keyed by selected error-case ID.")
    actual = {row.get("request_id"): row for row in records}
    result = {}
    for identifier, finding in findings.items():
        if identifier not in ERROR_IDS or not isinstance(finding, dict):
            raise ValueError("Comparative finding is outside the selected11 cases: " + str(identifier))
        if finding.get("human_confirmed") is not False:
            raise ValueError("New comparative findings must remain explicitly AI assisted: " + identifier)
        if any(not isinstance(finding.get(pair), str) or not finding[pair].strip() for pair in ("AD", "BC")):
            raise ValueError("Comparative finding needs both AD and BC analysis: " + identifier)
        expected = {f"{identifier}__{condition}__r{repeat}" for condition in "ABCD" for repeat in (1, 2, 3)}
        hashes = finding.get("response_sha256s")
        if not isinstance(hashes, dict) or set(hashes) != expected:
            raise ValueError("Comparative finding must reference exactly12 new ABCD response IDs: " + identifier)
        for request_id, expected_hash in hashes.items():
            row = actual.get(request_id)
            if (row is None or row.get("status") not in API_RECEIVED
                    or expected_hash != hashlib.sha256((row.get("output_text") or "").encode()).hexdigest()):
                raise ValueError("Stale or missing new response in comparative finding: " + request_id)
        result[identifier] = finding
    return result


def build_rows(root, output, config, plan, records):
    """Keep immutable response grading intact; only derived views may resolve abstentions."""
    root, output = Path(root), Path(output)
    by_key = {_key(r): r for r in records}
    if len(by_key) != len(records) or not set(by_key) <= {_key(r) for r in plan}:
        raise ValueError("New response keys are duplicated or outside the frozen repeat plan.")
    reviews = _new_reviews(output, records)
    rows, objects = [], {}
    for item in plan:
        key = _key(item)
        saved = by_key.get(key)
        row = {**item, **(saved or {})}
        row.setdefault("status", "not_run")
        row.setdefault("output_text", "")
        if saved and any(saved.get(name) != item.get(name) for name in ("input_text", "request_sha256", "problem_text")):
            raise ValueError("Saved new response no longer matches frozen input: " + str(key))
        raw = row.get("evaluation") or {"predicted_answer": None, "correct": None, "status": "not_evaluated"}
        correct = raw.get("correct") if row["status"] == "success" and type(raw.get("correct")) is bool else None
        received = row["status"] in API_RECEIVED
        grade_source = ("saved_automatic_corrected_key" if row["status"] == "success" else
                        "not_graded_incomplete_response" if received else "not_generated")
        review = reviews.get(key, {"review_status": "deferred" if received else "not_generated",
                                  "math_status": "uncertain", "reviewer_type": "not_reviewed", "human_confirmed": False,
                                  "reason": "새 응답의 풀이 과정을 아직 검토하지 않았다.", "error_step": None,
                                  "evidence_quotes": [], "prior_error_recurred": None, "self_corrected": None})
        reviewed_grade = review.get("final_answer_correct")
        if type(reviewed_grade) is not bool:
            reviewed_grade = (review.get("final_answer_adjudication") or {}).get("correct")
        if (row["status"] == "success" and type(reviewed_grade) is bool and reviewed_grade is not correct
                and review.get("reason") and review.get("evidence_quotes")):
            correct, grade_source = reviewed_grade, "independent_new_AI_answer_review"
        row["evaluation_raw"] = dict(raw)
        row["evaluation"] = {**raw, "correct": correct}
        row["correct_scored"], row["grade_source"], row["review"] = correct, grade_source, dict(review)
        row["api_received"] = received
        row["display_output_sha256"] = hashlib.sha256(row["output_text"].encode()).hexdigest() if received else None
        row["usage"] = dict(row.get("usage") or {})
        for field in USAGE_FIELDS:
            value = row["usage"].get(field)
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError("Usage must be the actual nonnegative API count or null: " + str(key))
            row["usage"][field] = value
        audit = output / "frozen_prompts" / item["id"] / (item["condition"] + ".json")
        frozen = read_json(audit) if audit.is_file() else {}
        row["sdk_request"] = frozen.get("sdk_request", {})
        row["frozen_source_audit"] = {name: frozen.get(name) for name in (
            "source_condition", "source_prompt_audit", "source_prompt_audit_sha256", "source_request_sha256",
            "models", "dataset_id", "solution_vocabulary_sha256", "data_identity_sha256", "transformation")}
        row["frozen_source_audit"].update(original_reference_answer_text=row.get("original_reference_answer_text"),
            grading_key_status=row.get("grading_key_status"), original_reference=row.get("original_reference"))
        row["request_path"] = str(audit.relative_to(output)) if audit.is_file() else None
        objects[key] = row
        flat = {"id": row["id"], "condition": row["condition"], "repeat": int(row["repeat"]),
                "request_id": row.get("request_id"), "split": row["split"], "status": row["status"], "api_received": received,
                "answer": raw.get("predicted_answer"), "correct_raw": raw.get("correct") if row["status"] == "success" else None,
                "correct_scored": correct, "grade_source": grade_source,
                "reference_answer": row.get("reference_answer_text"),
                "math_status": review.get("math_status"), "review_status": review.get("review_status"),
                "prior_error_recurred": review.get("prior_error_recurred"), "self_corrected": review.get("self_corrected"),
                "reason": review.get("reason"), "error_step": review.get("error_step"),
                "evidence_quotes": json.dumps(review.get("evidence_quotes", []), ensure_ascii=False),
                "response_sha256": row["display_output_sha256"], "request_sha256": row.get("request_sha256"),
                "input_sha256": row.get("input_sha256"), "request_path": row["request_path"],
                "started_at": row.get("started_at"), "completed_at": row.get("completed_at")}
        flat.update({field: row["usage"][field] for field in USAGE_FIELDS})
        rows.append(flat)
    return rows, objects


def grouped_summary(rows, identifiers, conditions):
    result = []
    for identifier in identifiers:
        for condition in conditions:
            selected = [r for r in rows if r["id"] == identifier and r["condition"] == condition]
            if len(selected) != 3 or {r["repeat"] for r in selected} != {1, 2, 3}:
                raise ValueError("Exactly three planned repeats required per selected cell.")
            success = [r for r in selected if r["status"] == "success"]
            received = [r for r in selected if r["status"] in API_RECEIVED]
            graded = [r for r in success if type(r["correct_scored"]) is bool]
            reviewed = [r for r in received if r["math_status"] in ("appropriate", "inappropriate")]
            item = {"id": identifier, "split": selected[0]["split"], "condition": condition, "label": LABELS[condition],
                "expected_count": 3, "success_count": len(success), "graded_count": len(graded),
                "received_count": len(received), "completed_count": len(received), "api_response_count": len(received),
                "incomplete_count": len(received) - len(success),
                "unique_output_count": len({r["response_sha256"] for r in received}),
                "truncated_count": sum(r["status"] == "truncated_response" for r in received),
                "blocked_count": sum(r["status"] == "blocked_or_incomplete_response" for r in received),
                "empty_count": sum(r["status"] == "empty_response" for r in received),
                "correct_count": sum(r["correct_scored"] is True for r in graded),
                "incorrect_count": sum(r["correct_scored"] is False for r in graded),
                "ungradable_count": len(received) - len(graded),
                "pending_count": sum(r["status"] == "not_run" for r in selected),
                "failed_count": sum(r["status"] != "not_run" and r["status"] not in API_RECEIVED for r in selected),
                "accuracy_graded": sum(r["correct_scored"] is True for r in graded) / len(graded) if graded else None,
                "reviewed_math_count": len(reviewed),
                "math_appropriate_count": sum(r["math_status"] == "appropriate" for r in reviewed),
                "math_inappropriate_count": sum(r["math_status"] == "inappropriate" for r in reviewed),
                "math_uncertain_count": len(received) - len(reviewed),
                "correct_but_math_inappropriate_count": sum(r["correct_scored"] is True and r["math_status"] == "inappropriate" for r in received),
                "prior_error_recurred_count": sum(r["prior_error_recurred"] is True for r in received),
                "prior_error_assessed_count": sum(type(r["prior_error_recurred"]) is bool for r in received),
                "self_corrected_count": sum(r["self_corrected"] is True for r in received),
                "self_correction_assessed_count": sum(type(r["self_corrected"]) is bool for r in received)}
            for field in USAGE_FIELDS:
                item.update({field + "_" + name: value for name, value in _stats([r[field] for r in received]).items()})
            result.append(item)
    return result


def paired_differences(rows, identifiers):
    index = {_key(r): r for r in rows}
    result = []
    for identifier in identifiers:
        for first, second in CONTRASTS:
            for repeat in (1, 2, 3):
                a, b = index[identifier, first, repeat], index[identifier, second, repeat]
                both = a["status"] == b["status"] == "success"
                both_received = a["status"] in API_RECEIVED and b["status"] in API_RECEIVED
                row = {"id": identifier, "split": a["split"], "contrast": second + "-" + first,
                       "first": first, "second": second, "repeat": repeat, "both_success": both, "both_received": both_received,
                       "first_correct": a["correct_scored"], "second_correct": b["correct_scored"],
                       "first_math_status": a["math_status"], "second_math_status": b["math_status"]}
                for field in USAGE_FIELDS:
                    row[field + "_difference"] = b[field] - a[field] if both_received and a[field] is not None and b[field] is not None else None
                result.append(row)
    return result


def _historical(root):
    folder = Path(root) / "results/final_experiment_2/gemini_full265"
    comparison = {r["id"]: r for r in csv_rows(folder / "key_corrected/question_comparison.csv")}
    reviews = {(r["id"], r["condition"]): r for r in read_json(folder / "review/curated_reviews.json")["records"]}
    return comparison, reviews


def historical_comparison(summary, historical, old_reviews):
    result = []
    for row in summary:
        old = historical[row["id"]]
        condition = row["condition"]
        review = old_reviews.get((row["id"], condition), {})
        result.append({**row, "old_answer": old.get(condition + "_answer"),
            "old_correct_verified": _bool(old.get(condition + "_correct_verified")),
            "old_math_status": review.get("math_status"), "old_error_step": review.get("error_step"),
            "old_review_reason": review.get("reason"), "old_is_new_repeat": False})
    return result


def _questions(root, output, config, plan, objects):
    root, output = Path(root), Path(output)
    control, error = set(config.get("control_ids", CONTROL_IDS)), set(config.get("error_ids", ERROR_IDS))
    identifiers = config.get("target_ids") or list(dict.fromkeys(r["id"] for r in plan))
    result = []
    for identifier in identifiers:
        items = [r for r in plan if r["id"] == identifier]
        first = items[0]
        conditions = [c for c in LABELS if any(r["condition"] == c for r in items)]
        repetitions = {str(repeat): {c: objects[identifier, c, repeat] for c in conditions} for repeat in (1, 2, 3)}
        all_rows = [row for cell in repetitions.values() for row in cell.values()]
        grades = [r["correct_scored"] for r in all_rows if type(r.get("correct_scored")) is bool]
        suspected = any(r["review"].get("math_status") == "inappropriate" for r in all_rows)
        pending_review = any(r["status"] in API_RECEIVED and r["review"].get("math_status") == "uncertain" for r in all_rows)
        result.append({"id": identifier, "split": first["split"],
            "metadata": {name: first.get(name) for name in ("subject", "curriculum", "unit", "subunit", "type", "source")},
            "problem_text": first["problem_text"], "reference_answer": first.get("reference_answer_text"),
            "reference_solution": first["reference_solution"],
            "problem_href": _href(root / f"data/processed/problems/{identifier}.txt", output / "report.html"),
            "solution_href": _href(root / f"data/processed/solutions/{identifier}.txt", output / "report.html"),
            "expected_generation": True, "available_conditions": conditions, "repetitions": repetitions,
            "conditions": repetitions["1"], "is_control": identifier in control, "is_error_repeat": identifier in error,
            "changed_correctness": len(set(grades)) > 1,
            "reasoning_suspected": suspected, "review_pending": pending_review,
            "case_tags": [tag for tag, flag in (("reasoning_suspected", suspected), ("review_pending", pending_review)) if flag]})
    return result


def _review_markdown(row):
    review = row["review"]
    labels = {"appropriate": "수학적 타당 가능", "inappropriate": "구체적 오류 의심", "uncertain": "검토 보류"}
    lines = [f"- **새 풀이 검토:** {labels.get(review.get('math_status'), '검토 보류')} · AI 보조 / 사람 확정 아님.",
             "- 검토 근거: " + (review.get("reason") or "아직 검토하지 않음"),
             "- 오류 단계: " + (review.get("error_step") or "확인된 구체적 오류 단계 없음 / 미검토 여부는 위 상태 참조"),
             "- 기존 오류 재발 여부: " + ({True: "예", False: "아니오"}.get(review.get("prior_error_recurred"), "미평가 / 해당 없음")),
             "- 중간 오류 자기 수정 여부: " + ({True: "예", False: "아니오"}.get(review.get("self_corrected"), "미평가 / 해당 없음"))]
    if review.get("evidence_quotes"):
        lines += ["", "실제 새 응답의 인용:", ""]
        for quote in review["evidence_quotes"]:
            lines += ["> " + quote.replace("\n", "\n> "), ""]
    return lines


def write_cases(output, questions, historical, old_reviews):
    output = Path(output)
    folder = output / "case_reports"
    folder.mkdir(exist_ok=True)
    index = ["# 13문항의 신규 3회 반복 전문", "", "정답과 풀이 타당성은 구분한다. 과거 응답은 비교 기준이며 신규 반복 횟수에 포함하지 않는다.", "",
             "[반복 선택·수식 HTML](../report.html) · [전체 신규 요청 CSV](../question_comparison.csv)", "",
             "|문항|기존 분할|실험 포함|신규 반복 수|", "|---|---|---|---:|"]
    for q in questions:
        identifier = q["id"]
        memberships = ", ".join(name for name, flag in (("대조군5", q["is_control"]), ("오답반복11", q["is_error_repeat"])) if flag)
        index.append(f"|[{identifier}]({identifier}.md)|{q['split']}|{memberships}|{len(q['available_conditions'])}조건 ×3|")
        lines = ["# " + identifier + " · 신규 3회 반복", "", f"기존 분할: **{q['split']}** · {memberships}.", "",
                 f"[수식 HTML](../report.html#{identifier}) · [실제 동결 요청](../frozen_prompts/{identifier}/) · [과거 1회 수식 화면](../../gemini_full265/report.html#{identifier})", "",
                 "## 문제 원문", "", q["problem_text"], "", "## 원본 정답·해설", "", "원본 정답: " + str(q["reference_answer"]), "", q["reference_solution"], "",
                 "## 과거 265문항 실험의 1회 결과 · 신규 반복 아님", "", "|조건|과거 최종 답|과거 정정 판정|과거 풀이 보조검토|", "|---|---|---|---|"]
        old = historical[identifier]
        for condition in "ABCD":
            lines.append(f"|{condition}|{_cell(old.get(condition+'_answer'))}|{_fmt(_bool(old.get(condition+'_correct_verified')))}|{old_reviews.get((identifier,condition),{}).get('math_status','미검토')}|")
        for repeat, cell in q["repetitions"].items():
            lines += ["", f"## 신규 반복 {repeat}", ""]
            for condition in q["available_conditions"]:
                row = cell[condition]
                lines += [f"### {LABELS[condition]} · 반복 {repeat}", "",
                    f"상태: **{row['status']}** · 최종 답: **{_cell(row['evaluation_raw'].get('predicted_answer'))}** · 정정 기준 판정: **{_fmt(row['correct_scored'])}** · 판정 출처: `{row['grade_source']}`.", "",
                    "|입력|출력|추론|캐시|전체|도구 입력|", "|---:|---:|---:|---:|---:|---:|",
                    "|" + "|".join(_fmt(row["usage"].get(field)) for field in USAGE_FIELDS) + "|", "",
                    "#### 실제 추가 힌트 · 원본 JSON", "", "```json", json.dumps((row.get("hint") or {}).get("mapping", {}), ensure_ascii=False, indent=2), "```", "",
                    "#### 생성 풀이 전문", "", row.get("output_text") or "API 미완료. 오답이나 0토큰으로 대체하지 않음.", "",
                    "#### 새 풀이의 독립 검토", "", *_review_markdown(row), "",
                    "<details><summary>시스템·실제 입력·원시 자동채점·SDK 인자·해시</summary>", "", "```text", row.get("system_instruction", ""), "```", "", "```text", row.get("input_text", ""), "```", "", "```json",
                    json.dumps({"request_id": row.get("request_id"), "repeat": row["repeat"], "request_sha256": row.get("request_sha256"),
                                "response_sha256": row.get("display_output_sha256"), "evaluation_raw": row["evaluation_raw"],
                                "sdk_request": row.get("sdk_request"), "usage": row["usage"]}, ensure_ascii=False, indent=2), "```", "", "</details>", ""]
        (folder / f"{identifier}.md").write_text("\n".join(lines), encoding="utf-8")
    (folder / "README.md").write_text("\n".join(index) + "\n", encoding="utf-8")


def detailed_comparison(output, questions, summary, historical, old_reviews, first, second, findings=None):
    output = Path(output)
    index = {(r["id"], r["condition"]): r for r in summary}
    labels = "A 기본 조건과 D 실제 해설 토큰" if (first, second) == ("A", "D") else "B Ridge와 C MLP 예측 힌트"
    lines = ["# " + labels + " · 11문항 신규 반복 상세", "",
        "각 문항은 과거 오답 발생을 보고 사후 선택했다. 아래 결과는 새 3회 생성에서 관측된 사실과 AI 보조 풀이 검토다. 인과효과 또는 오류 불가능성을 뜻하지 않는다.", "",
        "[11문항 요약](README.md) · [모든 새 풀이 전문](../case_reports/README.md) · [수식·반복 선택 HTML](../report.html)", ""]
    for q in questions:
        if not q["is_error_repeat"]:
            continue
        identifier = q["id"]
        lines += ["## " + identifier, "", f"기존 분할: {q['split']} · 정답: {_cell(q['reference_answer'])}.", "",
                  f"[원문·새 풀이 전문](../case_reports/{identifier}.md) · [수식 화면](../report.html#{identifier})", "",
                  "### 문항별 새3회 비교 요약", ""]
        finding = (findings or {}).get(identifier)
        if finding:
            lines += ["AI 보조 비교 분석이며 사람의 최종 확정이 아니다. 아래 요약은 새 A/B/C/D×3의12개 응답 해시와 일치하는 경우에만 표시한다.", "",
                      finding[first + second], "",
                      "<details><summary>비교 요약이 참조한12개 새 응답 SHA-256</summary>", "", "```json",
                      json.dumps(finding["response_sha256s"], ensure_ascii=False, indent=2), "```", "", "</details>", ""]
        else:
            lines += ["**문항별 비교 요약 검토 보류:** 새 A/B/C/D의3회 응답 전체를 직접 대조한 요약이 아직 등록되지 않았다. 아래의 개별 판정·식·인용은 그대로 확인할 수 있다.", ""]
        lines += [
                  "|조건|과거 정정 판정|이번 정답/채점 가능/계획|이번 타당 가능/검토/계획|기존 오류 재발/평가|",
                  "|---|---|---|---|---|"]
        for condition in (first, second):
            s = index[identifier, condition]
            old = historical[identifier]
            lines.append(f"|{condition}|{_fmt(_bool(old.get(condition+'_correct_verified')))}|{s['correct_count']}/{s['graded_count']}/3|{s['math_appropriate_count']}/{s['reviewed_math_count']}/3|{s['prior_error_recurred_count']}/{s['prior_error_assessed_count']}|")
        for repeat, cell in q["repetitions"].items():
            a, b = cell[first], cell[second]
            lines += ["", "### 반복 " + repeat, ""]
            if a["status"] == b["status"] == "success":
                lines += [f"최종 답: {first} **{_fmt(a['correct_scored'])}**, {second} **{_fmt(b['correct_scored'])}**. 풀이 검토: {first} `{a['review'].get('math_status')}`, {second} `{b['review'].get('math_status')}`.", ""]
            else:
                lines += ["아직 두 응답이 모두 성공하지 않아 대응 결과를 확정하지 않는다.", ""]
            for condition, row in ((first, a), (second, b)):
                lines += [f"**{condition}: 새 풀이의 실제 단계와 근거**", "", *_review_markdown(row), ""]
        lines += ["동일 오류의 소멸·새 오류·공통 재발 여부는 위 새 응답의 식과 인용으로 판단한다. 과거 판정은 새 응답에 자동 복사하지 않았다.", ""]
    (output / "error_repeat_11" / f"{first}{second}_detailed_analysis.md").write_text("\n".join(lines), encoding="utf-8")


def _summary_table(rows, *, math_counts=True):
    lines = ["|문항|조건|수신/3|정상/불완전|정답/채점 가능|풀이 타당/검토|출력 평균|최소~최대|표본 SD|",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for row in rows:
        lines.append("|" + "|".join([f"[{row['id']}](../case_reports/{row['id']}.md)", row["condition"], f"{row['received_count']}/3", f"{row['success_count']}/{row['incomplete_count']}",
            f"{row['correct_count']}/{row['graded_count']}", f"{row['math_appropriate_count']}/{row['reviewed_math_count']}",
            _fmt(row["candidates_token_count_mean"]), _fmt(row["candidates_token_count_min"]) + "~" + _fmt(row["candidates_token_count_max"]),
            _fmt(row["candidates_token_count_std"])]) + "|")
    return lines


def _scope_table(rows, conditions):
    lines = ["|조건|신규 수신/계획|정상/불완전|정답/채점 가능|풀이 타당/검토|평균 입력|평균 출력|평균 전체|", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for c in conditions:
        selected = [r for r in rows if r["condition"] == c]
        sums = lambda field: sum(r[field] for r in selected)
        values = []
        for field in ("prompt_token_count", "candidates_token_count", "total_token_count"):
            n, total = sums(field + "_provided_count"), sum(r[field + "_sum"] or 0 for r in selected)
            values.append(total / n if n else None)
        lines.append("|" + "|".join([LABELS[c], f"{sums('received_count')}/{sums('expected_count')}", f"{sums('success_count')}/{sums('incomplete_count')}",
            f"{sums('correct_count')}/{sums('graded_count')}", f"{sums('math_appropriate_count')}/{sums('reviewed_math_count')}", *map(_fmt, values)]) + "|")
    return lines


def _control_observations(control, differences, rows):
    """Descriptive questions answered from saved data, without causal claims."""
    lines = ["### 저장 자료에서 관측한 방향", ""]
    purposes = {"E-A": "추가 지시문만 붙인 E와 A", "B-A": "Ridge 힌트 B와 A",
                "C-A": "MLP 힌트 C와 A", "D-A": "실제 해설 토큰 D와 A", "F-D": "중립 출처 F와 D"}
    for first, second in CONTRASTS:
        contrast = second + "-" + first
        per_question = []
        n = 0
        for identifier in CONTROL_IDS:
            values = [r["candidates_token_count_difference"] for r in differences
                      if r["id"] == identifier and r["contrast"] == contrast and r["candidates_token_count_difference"] is not None]
            if values:
                per_question.append(statistics.mean(values)); n += len(values)
        if per_question:
            decreased = sum(v < 0 for v in per_question)
            increased = sum(v > 0 for v in per_question)
            equal = sum(v == 0 for v in per_question)
            lines.append(f"- **{purposes[contrast]}({contrast})**: 제공된 대응 {n}/15쌍에서 문항별 평균 출력 차이가 감소한 문항 {decreased}개, 증가 {increased}개, 동일 {equal}개다. 문항별 평균 차이 범위는 {_fmt(min(per_question))}~{_fmt(max(per_question))}토큰이다.")
        else:
            lines.append(f"- **{purposes[contrast]}({contrast})**: 아직 제공된 대응 사용량이 없어 방향을 판단하지 않는다.")
    lines += ["", "### 출력이 줄어든 대응에서 정답·풀이 판정은 어떻게 달라졌는가?", "",
        "같은 문항·같은 반복 번호의 두 API 수신 응답 중 출력 토큰 차이가 음수인 쌍만 살펴본다. 사용량 미제공 쌍은 제외하며, 잘린 응답 등 최종 답이 없는 경우는 오답이 아니라 미판정으로 남긴다.", "",
        "|대응(뒤−앞)|출력 감소/사용량 제공쌍|최종 답: 개선/악화/동일/미판정|풀이: 개선/악화/동일/보류|",
        "|---|---:|---:|---:|"]
    for quality in output_reduction_quality(differences):
        answer = "/".join(str(quality["answer_" + name]) for name in ("gains", "losses", "same", "unknown"))
        validity = "/".join(str(quality["math_" + name]) for name in ("gains", "losses", "same", "unknown"))
        lines.append(f"|{quality['contrast']}|{quality['shorter_pairs']}/{quality['provided_pairs']}|{answer}|{validity}|")
    lines += ["", "최종 답의 개선/악화는 오답→정답/정답→오답, 풀이의 개선/악화는 오류 의심→타당 가능/타당 가능→오류 의심을 뜻한다. ‘동일’은 판정 상태가 같다는 뜻이며 답 문자열·풀이·오류 단계가 동일하다는 뜻은 아니다. 각 행의 네 판정 횟수 합은 출력 감소 쌍 수와 같다.",
        "같은 5문항을 조건당3회 반복한 설명 통계다. 출력이 짧아진 쌍만 사후 선택한 이 표로 토큰 감소가 정답이나 수학적 타당성을 바꾼 인과효과를 추정하지 않는다.", ""]
    partial = [r for r in rows if r["id"] in CONTROL_IDS and r["status"] in API_RECEIVED and r["status"] != "success"]
    if partial:
        lines += ["", "**출력 제한·불완전 응답도 연구 결과에 포함했다.**"]
        for r in partial:
            lines.append(f"- `{r['id']}/{r['condition']}/반복{r['repeat']}`: `{r['status']}`, 실제 출력 {_fmt(r['candidates_token_count'])}·전체 {_fmt(r['total_token_count'])}토큰. 최종 답 미완성 여부와 풀이 오류는 따로 기록했다.")
        lines += ["", "큰 사용량을 가진 응답은 평균·SD를 크게 바꿀 수 있다. 이를 제외하거나 같은 반복을 다시 생성하지 않았으며 문항별 그림의 개별 반복 점과 최소~최대에서 직접 확인할 수 있다."]
    lines += ["", "E-A의 변화가 관측되어도 모든 차이를 지시문으로 설명할 수 없고, F-D의 변화가 관측되어도 출처 강조의 인과효과라고 확정할 수 없다. D/F는 동일한 토큰·빈도 JSON을 유지했지만 제목이 바뀌며, 표본은 조건당3회뿐이다.", ""]
    return lines


def output_reduction_quality(differences):
    """Describe answer/validity changes among shorter paired API receipts only."""
    result = []
    for first, second in CONTRASTS:
        contrast = second + "-" + first
        provided = [r for r in differences if r["contrast"] == contrast and r.get("both_received") is True
                    and r.get("candidates_token_count_difference") is not None]
        shorter = [r for r in provided if r["candidates_token_count_difference"] < 0]
        row = {"contrast": contrast, "provided_pairs": len(provided), "shorter_pairs": len(shorter)}
        for prefix in ("answer", "math"):
            counts = {name: 0 for name in ("gains", "losses", "same", "unknown")}
            for pair in shorter:
                if prefix == "answer":
                    a, b = pair.get("first_correct"), pair.get("second_correct")
                else:
                    values = {"appropriate": True, "inappropriate": False}
                    a, b = values.get(pair.get("first_math_status")), values.get(pair.get("second_math_status"))
                category = ("unknown" if type(a) is not bool or type(b) is not bool else
                            "same" if a == b else "gains" if b else "losses")
                counts[category] += 1
            row.update({prefix + "_" + name: value for name, value in counts.items()})
        result.append(row)
    return result


def _error_observations(rows):
    index = {_key(r): r for r in rows if r["id"] in ERROR_IDS}
    lines = ["### 동일 문항·반복의 정오 및 풀이 변화", ""]
    for first, second in (("A", "D"), ("B", "C")):
        graded = []
        math_pairs = []
        for identifier in ERROR_IDS:
            for repeat in (1, 2, 3):
                a, b = index[identifier, first, repeat], index[identifier, second, repeat]
                if type(a["correct_scored"]) is bool and type(b["correct_scored"]) is bool:
                    graded.append((a, b))
                if a["math_status"] in ("appropriate", "inappropriate") and b["math_status"] in ("appropriate", "inappropriate"):
                    math_pairs.append((a, b))
        gained = sum(a["correct_scored"] is False and b["correct_scored"] is True for a, b in graded)
        lost = sum(a["correct_scored"] is True and b["correct_scored"] is False for a, b in graded)
        bad_to_valid = sum(a["math_status"] == "inappropriate" and b["math_status"] == "appropriate" for a, b in math_pairs)
        valid_to_bad = sum(a["math_status"] == "appropriate" and b["math_status"] == "inappropriate" for a, b in math_pairs)
        both_bad = sum(a["math_status"] == b["math_status"] == "inappropriate" for a, b in math_pairs)
        lines += [f"- **{first}→{second}**: 양쪽 최종 답을 채점한 {len(graded)}/33쌍에서 오답→정답 {gained}회, 정답→오답 {lost}회였다. 양쪽 풀이를 판단한 {len(math_pairs)}/33쌍에서는 오류 의심→타당 가능 {bad_to_valid}회, 타당 가능→오류 의심 {valid_to_bad}회, 양쪽 오류 의심 {both_bad}회였다."]
    coincidental = [r for r in rows if r["id"] in ERROR_IDS and r["correct_scored"] is True and r["math_status"] == "inappropriate"]
    recurrence = [r for r in rows if r["id"] in ERROR_IDS and r["prior_error_recurred"] is True]
    corrected = [r for r in rows if r["id"] in ERROR_IDS and r["self_corrected"] is True]
    lines += [f"- 새 최종 답은 맞지만 구체적인 풀이 오류가 남은 응답은 {len(coincidental)}회, 기존 오류 재발로 판단한 응답은 {len(recurrence)}회, 중간 오류를 이후 스스로 수정한 것으로 기록된 응답은 {len(corrected)}회다. 미평가 항목을0회 오류로 추정한 것은 아니다.",
        "", "이 대응 횟수는 같은 11문제를 반복 관측한 설명 통계다. 풀이가 달라져도 수학적으로 타당할 수 있고, 동일 오류를 놓치지 않았는지는 아래 실제 식·계산·반례를 포함한 AI 보조 검토에서 확인해야 한다.", ""]
    return lines


def _plots(output, control, error, differences, request_rows):
    from mathhint_learning.ClusterReport import setup_final_plots
    plt = setup_final_plots()
    import numpy as np
    folder = Path(output) / "figures"
    folder.mkdir(exist_ok=True)
    figures = []
    fig, axes = plt.subplots(5, 1, figsize=(11, 15), constrained_layout=True)
    repeat_colors = {1: "#b45f06", 2: "#674ea7", 3: "#0b7a75"}
    for ax, identifier in zip(axes, CONTROL_IDS):
        selected = [r for r in control if r["id"] == identifier]
        for i, r in enumerate(selected):
            mean = r["candidates_token_count_mean"]
            if mean is not None:
                ax.bar(i, mean, color=".65", edgecolor="black", yerr=r["candidates_token_count_std"] or 0, capsize=4)
                ax.text(i, mean, f"{mean:.1f}\n(n={r['candidates_token_count_provided_count']}/3)", ha="center", va="bottom", fontsize=8)
            trials = [v for v in request_rows if v["id"] == identifier and v["condition"] == r["condition"]
                      and v["status"] in API_RECEIVED and v["candidates_token_count"] is not None]
            for trial in trials:
                ax.scatter(i + (trial["repeat"] - 2) * .13, trial["candidates_token_count"],
                    color=repeat_colors[trial["repeat"]], marker="o", s=24, zorder=4,
                    label="반복 " + str(trial["repeat"]) if i == 0 else None)
                if trial["status"] != "success":
                    ax.annotate(f"R{trial['repeat']} {trial['candidates_token_count']} · 불완전",
                        (i + (trial["repeat"] - 2) * .13, trial["candidates_token_count"]),
                        xytext=(-12, -24 - (trial["repeat"] - 1) * 20), textcoords="offset points",
                        ha="right", va="top", fontsize=8,
                        bbox={"boxstyle": "round,pad=.2", "facecolor": "white", "edgecolor": ".7", "alpha": .94},
                        arrowprops={"arrowstyle": "-", "color": ".4", "linewidth": .7})
        ax.legend(loc="upper left", ncol=3, fontsize=7)
        ax.set(xticks=range(6), xticklabels=list("ABCDEF"), title=identifier, ylabel="출력 토큰 · 평균±SD / 각 반복 점")
        ax.margins(y=.18)
    fig.suptitle("대조군 5문항 · 신규 반복 각3회 · 문항별 독립 축\n잘림 포함 실제 수신 토큰, 회색막대=평균±표본SD, 색점=각반복; 큰값도 제외하지 않음")
    path = folder / "control_output_tokens.png"; fig.savefig(path, dpi=170); plt.close(fig); figures.append(path.name)
    fig, axes = plt.subplots(1, 5, figsize=(17, 5.5), constrained_layout=True)
    for ax, (first, second) in zip(axes, CONTRASTS):
        contrast = second + "-" + first
        for i, identifier in enumerate(CONTROL_IDS):
            vals = [r["candidates_token_count_difference"] for r in differences if r["id"] == identifier and r["contrast"] == contrast and r["candidates_token_count_difference"] is not None]
            if vals:
                mean = statistics.mean(vals); ax.barh(i, mean, color=".6", edgecolor="black")
                ax.text(mean, i, f" {mean:+.1f} (n={len(vals)})", va="center", fontsize=7)
        ax.axvline(0, color="black", linewidth=.7); ax.set(yticks=range(5), yticklabels=CONTROL_IDS, title=contrast, xlabel="대응 출력 토큰 차이 평균")
    fig.suptitle("대조군: 같은 문항·같은 반복 번호의 대응 차이 · 각최대3쌍\n단위: 토큰; 조건·시간·제공 정보 효과를 완전히 분리한 인과 추정이 아님")
    path = folder / "control_output_differences.png"; fig.savefig(path, dpi=170); plt.close(fig); figures.append(path.name)
    for name, field, title, denom in (("error_correct_counts.png", "correct_count", "정답 횟수 / 채점 가능 응답", "graded_count"),
                                    ("error_math_counts.png", "math_appropriate_count", "풀이 타당 가능 횟수 / AI 보조 검토", "reviewed_math_count")):
        fig, ax = plt.subplots(figsize=(9, 8), constrained_layout=True)
        matrix = np.full((11, 4), np.nan)
        for y, identifier in enumerate(ERROR_IDS):
            for x, condition in enumerate("ABCD"):
                r = next(r for r in error if r["id"] == identifier and r["condition"] == condition)
                if r[denom]:
                    matrix[y, x] = r[field]
                ax.text(x, y, f"{r[field]}/{r[denom]}\n계획3", ha="center", va="center", fontsize=9, color="black")
        cmap = plt.get_cmap("Blues").copy(); cmap.set_bad(".9")
        image = ax.imshow(matrix, vmin=0, vmax=3, cmap=cmap, aspect="auto")
        ax.set(xticks=range(4), xticklabels=list("ABCD"), yticks=range(11), yticklabels=[i + (" · 테스트" if next(r for r in error if r['id']==i)['split']=='test' else " · 학습") for i in ERROR_IDS], title="오답 관련11문항 · 신규 각3회\n" + title)
        fig.colorbar(image, ax=ax, label="횟수(최대3); 회색은 평가된 응답 없음")
        path = folder / name; fig.savefig(path, dpi=180); plt.close(fig); figures.append(path.name)
    fig, axes = plt.subplots(1, 3, figsize=(13, 5), constrained_layout=True)
    for ax, field in zip(axes, ("prompt_token_count", "candidates_token_count", "total_token_count")):
        for i, condition in enumerate("ABCD"):
            selected = [r for r in error if r["condition"] == condition]
            n = sum(r[field + "_provided_count"] for r in selected)
            mean = sum(r[field + "_sum"] or 0 for r in selected) / n if n else None
            if mean is not None:
                ax.bar(i, mean, color=".65", edgecolor="black"); ax.text(i, mean, f"{mean:.1f}\nn={n}/33", ha="center", va="bottom", fontsize=8)
        ax.set(xticks=range(4), xticklabels=list("ABCD"), title=TOKEN_LABELS[field] + " 토큰", ylabel="API 수신 응답의 제공값 평균")
    fig.suptitle("오답 관련11문항 × 신규3회 · 사용량\n사후선별 자료·학습/테스트 혼합, 추론 토큰을 전체에 임의 가산하지 않음")
    path = folder / "error_token_usage.png"; fig.savefig(path, dpi=180); plt.close(fig); figures.append(path.name)
    fig, axes = plt.subplots(5, 1, figsize=(11, 13), constrained_layout=True)
    for ax, identifier in zip(axes, CONTROL_IDS):
        selected = [r for r in control if r["id"] == identifier]
        for i, r in enumerate(selected):
            if r["graded_count"]:
                ax.bar(i, r["correct_count"], color=".6", edgecolor="black")
            ax.text(i, r["correct_count"] + .05, f"{r['correct_count']}/{r['graded_count']} (계획3)", ha="center", fontsize=8)
        ax.set(xticks=range(6), xticklabels=list("ABCDEF"), yticks=(0, 1, 2, 3), ylim=(0, 3.65), title=identifier, ylabel="정답 횟수")
    fig.suptitle("대조군5문항 · 신규 각3회 정답 횟수\n미완료·채점 보류를 오답으로 처리하지 않음")
    path = folder / "control_correct_counts.png"; fig.savefig(path, dpi=170); plt.close(fig); figures.append(path.name)
    return figures


def _write_readmes(output, config, state, rows, control, error, differences, figures):
    output = Path(output)
    success = sum(r["status"] == "success" for r in rows)
    received = sum(r["status"] in API_RECEIVED for r in rows)
    pending = len(rows) - received
    review_counts = Counter(r["math_status"] for r in rows if r["status"] in API_RECEIVED)
    split_by_id = {r["id"]: r["split"] for r in rows}
    unique_split_counts = Counter(split_by_id.values())
    request_split_counts = Counter(r["split"] for r in rows)
    protocol_note = ("동결된 config.json의 cache_policy에는 관측 전의 ‘success’ 표현이 해시 보존을 위해 남아 있다. "
        "첫 잘림 응답을 관측한 뒤 반복 슬롯을 다시 뽑는 선택 편향을 막도록 **실제 API 응답을 받은 슬롯은 정상 종료 여부와 관계없이 한 번의 관측으로 종료**하는 정책을 명시했다. "
        "현재 완료 수와 미수신 목록은 state.json의 completed_requests/api_response_count를 기준으로 읽는다. 모델·프롬프트·출력 상한·토큰은 바꾸지 않았다.")
    common = ["3회 표본 SD는 **ddof=1**이다. 사용량이 제공된 API 수신 응답이0개면 평균·최소·최대·SD는 —, 1개면 SD는 —다. 미제공은 null/—이며0으로 채우지 않는다.",
              "**출력 제한(MAX_TOKENS)·차단·빈 응답도 API 응답을 받은 한 번의 반복이다. 같은 반복을 다시 뽑지 않는다.** 잘린 응답의 실제 토큰은 사용량 평균에 포함하지만, 최종 답이 완성되지 않았다면 채점 보류로 남긴다. 설정된 토큰 상한을 실제 사용량 대신 넣지 않는다.",
              "정답 횟수와 풀이 타당 가능 횟수는 별개다. 검토 보류를 오류로 간주하지 않으며 AI 보조 검토는 사람의 확정이나 형식적 증명이 아니다. 자기 수정 횟수는 일부 중간 오류의 명시적 수정을 뜻하며, 다른 오류가 남아 최종 오답·풀이 부적절과 함께 나타날 수도 있다.",
              "같은 문항·같은 반복 번호를 대응시켰지만 조건 순서가 섞인 탐색적 비교다. 3회 모두 정답이어도 오류 가능성이 사라졌다고 주장하지 않는다."]
    control_lines = ["# 출력 토큰 감소 대조군 · 5문항 ×6조건 ×신규3회", "",
        "A 문제만 / B Ridge / C MLP / D 실제 해설 토큰 / E 지시문만 / F D와 같은 토큰+중립 출처 제목이다. E/F만으로 토큰의 순수 효과를 완전히 분리하지 못한다.", "",
        "[첫 안내](../README.md) · [수식·반복 비교](../report.html) · [문항·조건 통계 CSV](summary.csv) · [반복별 대응 차이 CSV](paired_differences.csv)", "",
        *common, "", *_scope_table(control, "ABCDEF"), "", *_control_observations(control, differences, rows), "![출력 토큰 평균과 표본SD](../figures/control_output_tokens.png)", "",
        "![대응 출력 차이](../figures/control_output_differences.png)", "", "![정답 횟수](../figures/control_correct_counts.png)", "", "## 문항별 전체 통계", "", *_summary_table(control)]
    (output / "control_top5/README.md").write_text("\n".join(control_lines) + "\n", encoding="utf-8")
    error_lines = ["# 기존 오답 관련11문항 · A/B/C/D 신규 각3회", "",
        "기존 정정표에서 A/B/C/D 중 적어도 하나가 오답인11문항을 다시 확인한 사후선별 집합이다. 이 집합 정답률을 전체265의 일반화 정확도로 해석하지 않는다.", "",
        "[A와 D 상세](AD_detailed_analysis.md) · [B와 C 상세](BC_detailed_analysis.md) · [신규 통계 CSV](summary.csv) · [과거1회와 비교 CSV](prior_comparison.csv)", "",
        "[원문·새3회 풀이 전문](../case_reports/README.md) · [수식 화면](../report.html) · [기존11문항 분석](../../gemini_full265/error_analysis_11/README.md)", "",
        *common, "", *_scope_table(error, "ABCD"), "", *_error_observations(rows), "![정답 횟수](../figures/error_correct_counts.png)", "",
        "![풀이 검토](../figures/error_math_counts.png)", "", "![사용량](../figures/error_token_usage.png)", "", "## 문항별 전체 통계", "", *_summary_table(error)]
    (output / "error_repeat_11/README.md").write_text("\n".join(error_lines) + "\n", encoding="utf-8")
    lines = ["# MathHint · 신규3회 반복 결과", "", "이번 범위는 **출력 토큰 대조군과 기존 오답의 3회 반복 결과 정리**다. 프로젝트 전체의 최종 마무리나 모델 개선 실험이 아니다.", "",
        f"동결 설정: 모델 `{config.get('model')}`, temperature `{config.get('temperature')}`, thinking `{config.get('thinking_level')}`, 최대 출력 토큰 `{config.get('max_output_tokens')}`. 이 상한은 응답별 실제 사용량과 다르다.", "",
        f"**상태: {state.get('status','unknown')} · 신규 API 응답 수신 {received}/186 · 정상 완료 {success} · 불완전 수신 {received-success} · 미수신 {pending}.** 기존265실험의 응답은 신규 반복 횟수에 포함하지 않았다.", "",
        "두 실험은 대조군90회 + 오답반복132회 − 공유36회 = **186개 고유 요청**이다. 공유3문항의 A/B/C/D×3을 한 번만 호출해 두 분석에 연결한다. 같은 프롬프트 해시라도 반복 번호1/2/3은 서로 다른 실제 신규 호출이다.", "",
        "|먼저 볼 자료|내용|", "|---|---|", "|[출력 감소 대조군](control_top5/README.md)|A-E, A-B/C/D, D-F의 출력 토큰 차이·3회 평균/범위/표본SD·정답 횟수|",
        "|[오답11문항 반복](error_repeat_11/README.md)|새 정답/풀이 타당 횟수·기존 오류 재발과 새 오류|", "|[A↔D 상세](error_repeat_11/AD_detailed_analysis.md)|실제 오류 단계·반례·새 풀이 비교|",
        "|[B↔C 상세](error_repeat_11/BC_detailed_analysis.md)|Ridge/MLP 힌트 조건의 관찰 차이|", "|[13문항 수식·반복 비교 HTML](report.html)|원문·실제 해설·힌트·반복1/2/3의 모든 새 풀이·원문 감사|",
        "|[연구 보고서](final_report.md)|관찰과 해석·검증 범위·한계|", "|[모든 신규 요청 CSV](question_comparison.csv)|186개 계획의 상태·정오·풀이 검토·사용량·해시|", "",
        "## 출력 토큰 대조군5 · 조건별 요약", "", *_scope_table(control, "ABCDEF"), "", *_control_observations(control, differences, rows),
        "## 기존 오답11 · 조건별 요약", "", *_scope_table(error, "ABCD"), "", *_error_observations(rows),
        f"대상13문항은 기존 학습 분할 {unique_split_counts.get('train',0)}개·테스트 분할 {unique_split_counts.get('test',0)}개이며, 신규186요청은 각각 {request_split_counts.get('train',0)}회·{request_split_counts.get('test',0)}회다. 두 표는 일부 요청을 공유하므로 서로 독립인 표본으로 합쳐 유의성을 주장하지 않는다. 학습 문항의 B/C 예측은 인샘플이며 기존 테스트80 결과와 구분한다.", "",
        "## 실행·재개·감사", "", "```bash", "python -m mathhint_solver.final_experiment_2.final_followup preflight",
        "python -m mathhint_solver.final_experiment_2.final_followup generate",
        "python -m mathhint_solver.final_experiment_2.final_followup report", "python -m mathhint_solver.final_experiment_2.final_followup verify", "```", "",
        "report와 verify는 저장 자료만 읽고 API 호출·모델 학습을 시작하지 않는다. generate는 이미 응답을 받은 같은 문항·조건·반복을 잘림 여부와 관계없이 재호출하지 않는다. API 제한으로 중단되면 정확한 미수신 목록과 재개 명령을 [state.json](state.json)에서 확인한다.", "",
        protocol_note, "",
        "[설정](config.json) · [동결된 실제 프롬프트](frozen_prompts/) · [신규 응답 원문](responses.jsonl) · [검토 상태 CSV](review/status.csv) · [검증](validation.json) · [실행 기록](execution_runs/)", "",
        f"API 수신 응답의 수학 검토 상태: `{dict(review_counts)}`. 과거 판정을 새 응답에 그대로 복사하지 않았고 검토 근거는 새 응답 SHA와 실제 인용으로 연결한다.", "",
        "실제 상위 토큰은 최대20종이다. 기존 D/trig_2_022는 양의 빈도 좌표가19개여서19종을 그대로 재사용했으며20번째 토큰을 만들지 않았다.", "",
        "## HTML 여는 방법", "", "GitHub 파일 페이지는 HTML 실행 화면이 아니다. 저장소 ZIP 전체를 압축 해제한 뒤 `results/final_experiment_2/final_followup/report.html`을 브라우저로 연다. 같은 폴더의 viewer_assets와 기존 mathhint_analysis/viewer_assets/vendor의 수식·Markdown·글꼴이 필요하므로 HTML 한 파일만 내려받으면 충분하지 않다. 외부 렌더링 서버나 추가 API 없이 읽는다.", "",
        "## 해석의 범위", "", *common,
        "고정 temperature0에서도 서비스 구현·실행 시점에 따라 응답이 달라질 수 있다. 같은 텍스트가 반복돼도 실제 신규 호출 여부는 실행·SDK 경계 기록으로 확인한다. 3회는 탐색적 재현 관찰이며 인과효과나 확정적 성능 순위를 뜻하지 않는다.",
        "D/F는 원본 정답 해설의 토큰을 미리 제공한 오라클 진단이다. 문제 원문·모델·학습 모델·어휘·기존 응답은 변경하지 않았다. 추론/캐시 미제공은0이 아니며 전체 토큰에 임의로 더하지 않는다.", ""]
    (output / "README.md").write_text("\n".join(lines), encoding="utf-8")
    pairs = []
    for first, second in CONTRASTS:
        key = second + "-" + first
        values = [r["candidates_token_count_difference"] for r in differences if r["contrast"] == key and r["candidates_token_count_difference"] is not None]
        stats = _stats(values)
        pairs.append(f"|{key}|{len(values)}/15|{_fmt(stats['mean'])}|{_fmt(stats['min'])}~{_fmt(stats['max'])}|")
    report = ["# 신규3회 반복 연구 보고서", "", "## 목적과 실제 실행 범위", "",
        f"출력 토큰 대조군 5문항과 기존 오답 관련 11문항을 합쳐 13개 고유 문항의 186요청을 계획했다. 현재 신규 API 응답 수신 {received}/186(정상 완료 {success}, 불완전 {received-success}), 미수신 {pending}이다. 이전 265문항의 응답은 비교 기준으로만 읽고 신규 3회로 세지 않았다.", "",
        "A는 기존 문제만, B/C는 동결된 Ridge/MLP 예측 힌트, D는 실제 해설 토큰, E는 문제 뒤 ‘풀이를 작성해줘.’만 추가한 조건이다. F는 D의 동일한 토큰·빈도·JSON에서 출처 제목만 ‘해설에 등장한 토큰과 빈도: 상위20개’로 바꾼 조건이다. 가짜 토큰·새 예측·새 학습은 없다.", "",
        "## 관찰1: 출력 토큰 대조군", "", *_scope_table(control, "ABCDEF"), "", *_control_observations(control, differences, rows),
        "같은 문항·같은 반복 번호에서 뒤 조건−앞 조건으로 계산한 출력 토큰 차이는 다음과 같다. 최대 15쌍은 5문항×3반복이며 15개의 독립된 문제를 뜻하지 않는다.", "",
        "|대응 차이|제공쌍/계획|평균 출력토큰 차이|최소~최대|", "|---|---:|---:|---:|", *pairs, "",
        "문항별 평균·범위·표본 SD와 실제 응답은 [대조군 분석](control_top5/README.md)에 있다. A-E는 추가 지시문과 관련된 변화를, D-F는 출처 표현과 관련된 변화를 관찰하지만, 두 조건만으로 토큰의 순수 인과효과를 완전히 분리하지 못한다.", "",
        "## 관찰2: 과거 오답의 반복", "", *_scope_table(error, "ABCD"), "", *_error_observations(rows),
        "기존의 틀린 최종 답과 논리 오류가 새 응답에서도 나타나는지는 새 풀이의 잘못된 식·올바른 계산·반례와 함께 [A-D 상세](error_repeat_11/AD_detailed_analysis.md), [B-C 상세](error_repeat_11/BC_detailed_analysis.md)에 기록했다. 정답 횟수가 같더라도 풀이 타당성이 같다고 볼 수 없다. 중간 오류를 스스로 수정한 경우와 최종 답은 맞지만 오류를 남긴 경우를 구분했다.", "",
        "## 판단의 근거와 불확실성", "", *common,
        "11문항은 과거 오답을 보고 선정했으므로 선택 편향이 있다. 전체 265문항 또는 기존 테스트 80문항의 정답률과 동등한 성능 평가가 아니다. B/C는 전체 265문항의 어휘를 미리 아는 조건이며 학습 185문항에 대한 예측은 인샘플이다.",
        "표본 3회와 이번 실행 자료만으로 차이의 원인을 모델 능력·지시문·힌트·출처 강조 중 하나로 확정할 수 없다. 3회 모두 정답이어도 해당 오류가 영원히 재현되지 않는다는 뜻이 아니다. API 입출력 토큰과 외부 모델의 전체 연산 비용은 별개이며, 측정하지 않은 전체 시스템 효율 향상은 주장하지 않는다.", "",
        "## 보존과 재현", "", "[설정](config.json), [실제 프롬프트](frozen_prompts/), [신규 응답](responses.jsonl), [실행 상태](state.json), [검증](validation.json)을 보존한다. 모든 핵심 수치는 저장된 새 응답에서 생성했으며 report/verify는 학습·API를 실행하지 않는다.", "", protocol_note, "",
        "이번 산출물은 3회 반복 결과의 정리까지이며 프로젝트 전체의 최종 결론을 확정하거나 후속 실험을 자동 실행하지 않는다.", ""]
    (output / "final_report.md").write_text("\n".join(report), encoding="utf-8")


def run(root=None, output=None):
    from .common import ROOT, OUTPUT, safe_output, load_saved
    root = Path(root or ROOT).resolve()
    output = safe_output(root, output or OUTPUT)
    config, plan, records, state = load_saved(output)
    rows, objects = build_rows(root, output, config, plan, records)
    controls = config.get("control_ids", CONTROL_IDS)
    errors = config.get("error_ids", ERROR_IDS)
    control = grouped_summary(rows, controls, "ABCDEF")
    error = grouped_summary(rows, errors, "ABCD")
    differences = paired_differences(rows, controls)
    historical, old_reviews = _historical(root)
    old_comparison = historical_comparison(error, historical, old_reviews)
    for folder in ("control_top5", "error_repeat_11", "review", "case_reports"):
        (output / folder).mkdir(exist_ok=True)
    write_csv(output / "question_comparison.csv", rows)
    write_csv(output / "review/status.csv", rows)
    write_csv(output / "control_top5/summary.csv", control)
    write_csv(output / "control_top5/paired_differences.csv", differences)
    write_csv(output / "error_repeat_11/summary.csv", error)
    write_csv(output / "error_repeat_11/prior_comparison.csv", old_comparison)
    questions = _questions(root, output, config, plan, objects)
    write_cases(output, questions, historical, old_reviews)
    findings = case_findings(output, records)
    for pair in (("A", "D"), ("B", "C")):
        detailed_comparison(output, questions, error, historical, old_reviews, *pair, findings=findings)
    figures = _plots(output, control, error, differences, rows)
    _write_readmes(output, config, state, rows, control, error, differences, figures)
    payload = {"schema_version": 1, "experiment_name": "최종 후속실험 · 신규3회 반복(프로젝트 최종마무리 아님)",
        "config": {name: config.get(name) for name in ("model", "temperature", "thinking_level", "max_output_tokens", "system_instruction")},
        "questions": questions, "methods": [{"key": c, "condition": c, "label": label} for c, label in LABELS.items()],
        "test_ids": [q["id"] for q in questions if q["split"] == "test"], "train_ids": [q["id"] for q in questions if q["split"] == "train"],
        "links": {"readme": "README.md", "final_report": "final_report.md", "comparison_csv": "question_comparison.csv", "raw_responses": "responses.jsonl"}}
    build_viewer(output, payload)
    review_counts = dict(Counter(r["math_status"] for r in rows if r["status"] in API_RECEIVED))
    received_count = sum(r["status"] in API_RECEIVED for r in rows)
    write_json(output / "review/summary.json", {"planned_count": len(rows), "success_count": sum(r["status"] == "success" for r in rows),
        "api_response_count": received_count, "completed_count": received_count,
        "incomplete_response_count": sum(r["status"] in API_RECEIVED and r["status"] != "success" for r in rows),
        "math_status_counts": review_counts, "review_status_counts": dict(Counter(r["review_status"] for r in rows if r["status"] in API_RECEIVED)),
        "human_confirmed": sum(r["review"].get("human_confirmed") is True for r in objects.values()), "additional_review_api_calls": 0})
    write_json(output / "metrics.json", {"control_summary": control, "error_summary": error, "paired_differences": differences,
        "question_count": len(questions), "planned_request_count": len(rows), "state": state, "math_status_counts": review_counts,
        "figures": figures, "report_generation_api_calls": 0, "model_training_performed": False,
        "raw_responses_sha256": file_hash(output / "responses.jsonl") if (output / "responses.jsonl").exists() else None})
    return {"question_count": len(questions), "planned_request_count": len(rows), "figures": len(figures),
            "successful_requests": sum(r["status"] == "success" for r in rows), "completed_requests": received_count,
            "api_calls": 0, "training_performed": False}
