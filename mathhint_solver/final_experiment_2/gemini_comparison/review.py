"""최종 답 채점과 수학적 풀이 검토를 분리해 기록한다. 외부 검토 API는 없다."""

from collections import Counter
import csv
import hashlib
import json
from pathlib import Path

from mathhint_analysis.ResultViewer import _legacy_reviews
from ...CompareGeneration import read_json, write_json


def text_hash(text):
    return hashlib.sha256((text or "").encode()).hexdigest()


def clean_presentation_blank_lines(text):
    """표시용 불필요한 공백만 정리한다. Markdown 줄바꿈인 끝 두 공백은 보존한다."""
    result = []
    for line in text.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        if body and body.isspace():
            result.append(line[len(body):])
        elif body.endswith(" ") and not body.endswith("  "):
            result.append(body[:-1] + line[len(body):])
        else:
            result.append(line)
    return "".join(result)


def write_csv(path, rows, fields=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(rows)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(fields or rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def key_conflicts(root):
    path = Path(root) / "results/model_comparison_2026-11-07/03_Gemini비교/원본정답표_오류근거.json"
    return {row["id"]: {**row, "source_path": str(path.relative_to(root)), "human_confirmed": False}
            for row in read_json(path).get("records", [])} if path.exists() else {}


def build_reviews(root, output, questions):
    """새 판정은 미검토가 기본이다. 과거 검토는 동일 응답의 A에만 출처와 연결한다."""
    root, output = Path(root), Path(output)
    latest_a = {(q["id"], "baseline"): q["conditions"].get("baseline") for q in questions
                if q["conditions"].get("baseline") and q["conditions"]["baseline"].get("status") == "success"}
    historical = _legacy_reviews(root, latest_a, output / "report.html")
    manual_path = output / "review/curated_reviews.json"
    curated = {}
    if manual_path.exists():
        for row in read_json(manual_path).get("records", []):
            key = row["id"], row["condition"]
            if key in curated:
                raise ValueError(f"풀이 검토 키가 중복되었습니다: {key}")
            curated[key] = row
    rows = []
    for q in questions:
        if not q["expected_generation"]:
            continue
        for condition, method in (("A", "baseline"), ("B", "regression_hint"),
                                  ("C", "deep_learning_hint"), ("D", "oracle_hint")):
            response = q["conditions"][method]
            success = response.get("status") == "success"
            review = {"review_status": "deferred" if success else "not_generated",
                      "math_status": "uncertain", "reviewer_type": "not_reviewed",
                      "human_confirmed": False,
                      "reason": "최종 답 자동채점과 풀이 타당성은 별개다. 수학적 단계의 검증은 보류했다." if success else "성공한 생성 풀이가 없어 검토 대상이 아니다.",
                      "error_step": None, "evidence_quotes": [], "source_path": None}
            if condition == "A" and (q["id"], "baseline") in historical:
                old = historical[q["id"], "baseline"]
                review.update(old)
                review.update(review_status="historical_AI_suspected_error" if old["math_status"] == "inappropriate" else "deferred",
                              reviewer_type="historical_AI_assisted_exact_response",
                              source_path=old.get("source_href"),
                              reason="기존 동일 응답에 대한 AI 보조 검토를 연결했다. 이번의 사람 확정 판정이 아니다.\n\n" + old.get("reason", ""))
            own = curated.get((q["id"], condition))
            if own is not None:
                if not success or own.get("response_sha256") != text_hash(response.get("output_text")):
                    raise ValueError(f"검토 응답의 해시가 현재 생성 풀이와 다릅니다: {q['id']}/{condition}")
                quotes = own.get("evidence_quotes", [])
                if any(not isinstance(quote, str) or quote not in response.get("output_text", "") for quote in quotes):
                    raise ValueError(f"검토 인용이 응답 원문에 없습니다: {q['id']}/{condition}")
                if own.get("review_status") == "confirmed_error" and not (quotes and own.get("error_step") and own.get("reason")
                                                                           and own.get("math_status") == "inappropriate"):
                    raise ValueError(f"오류 확정에는 실제 인용·오류 단계·근거가 모두 필요합니다: {q['id']}/{condition}")
                review.update(own)
            review["response_sha256"] = text_hash(response.get("output_text")) if success else None
            response["review"] = review
            evaluation = response.get("evaluation", {})
            rows.append({"id": q["id"], "split": q["split"], "condition": condition,
                         "api_status": response.get("status"), "final_answer_correct_original": evaluation.get("correct"),
                         "final_answer_correct_supplemental": response.get("correct_ai_supplemental"),
                         "response_sha256": review["response_sha256"], "review_status": review["review_status"],
                         "math_status": review.get("math_status"), "reviewer_type": review.get("reviewer_type"),
                         "human_confirmed": bool(review.get("human_confirmed")), "reason": review.get("reason"),
                         "error_step": review.get("error_step"), "evidence_quotes": json.dumps(review.get("evidence_quotes", []), ensure_ascii=False),
                         "source_path": review.get("source_path")})
    folder = output / "review"
    write_csv(folder / "status.csv", rows)
    write_json(folder / "summary.json", {"planned_response_count": len(rows),
               "review_status_counts": dict(Counter(row["review_status"] for row in rows)),
               "human_confirmed_count": sum(row["human_confirmed"] for row in rows),
               "additional_review_api_calls": 0,
               "note": "전체 상태를 기록했지만 보류를 수학적 검증 완료로 취급하지 않는다."})
    (folder / "README.md").write_text("""# 풀이 과정 검토 상태

[전체 응답별 상태](status.csv) · [상태별 개수](summary.json) · [문항 화면](../report.html)

최종 답은 기존 보수적 자동채점기로 비교한다. **최종 답이 맞아도 풀이가 타당하다고 판정하지 않는다.**
새 응답의 수학적 단계를 충분히 검증하지 못한 경우 `deferred`(검토 보류)다. 미실행 풀이에는 `not_generated`를 쓴다.
과거 A 응답과 문제·입력·출력이 완전히 같은 경우에만 과거 AI 보조 검토를 연결한다. 사람의 확정 판정으로 승격하지 않는다.
새 B/C/D에 과거 검토를 옮기지 않는다. 문장이 원본과 다르다는 사실만으로 오류라고 판단하지 않는다.

추가 검토 API는 호출하지 않았다. 후속 직접 검토는 선택적으로 `curated_reviews.json`의 records 배열에
id/condition/response_sha256/review_status/math_status/reason/error_step/evidence_quotes/reviewer_type/human_confirmed를 기록할 수 있다.
`confirmed_error`에는 응답에 실제 존재하는 인용, 잘못된 단계, 수학적 근거가 모두 필요하다. 응답 SHA나 인용이 맞지 않으면 보고서 생성을 중단한다.
""", encoding="utf-8")
    return rows


CASE_LABELS = {
    "A_correct_B_wrong": "A 정답 → B 오답", "A_correct_C_wrong": "A 정답 → C 오답",
    "B_only_correct": "B만 정답", "C_only_correct": "C만 정답", "D_only_correct": "D만 정답",
    "learned_hint_improvement": "B 또는 C에서 정답으로 변화", "D_wrong": "D에서도 오답",
    "all_wrong": "네 조건 모두 오답", "changed_answers": "조건별 최종 답 변화",
    "answer_key_conflict": "원본 정답표 충돌 의심", "reasoning_suspected": "풀이 오류 의심",
    "correct_but_reasoning_suspected": "답은 맞지만 풀이 오류 의심", "possible_alternative": "다른 타당 풀이 가능성 검토",
    "large_token_change": "토큰 사용량 큰 증가", "incomplete": "장황·불완전 의심",
    "ungraded": "채점 불가", "api_incomplete": "API 실패·미완료", "review_pending": "풀이 검토 보류",
}


def select_tags(q):
    by_condition = {row["condition"]: row for row in q["conditions"].values() if row}
    good = {condition: row.get("evaluation", {}).get("correct") if row.get("status") == "success" else None
            for condition, row in by_condition.items()}
    tags = []
    if good.get("A") is True and good.get("B") is False:
        tags.append("A_correct_B_wrong")
    if good.get("A") is True and good.get("C") is False:
        tags.append("A_correct_C_wrong")
    if good.get("A") is False and any(good.get(c) is True for c in ("B", "C")):
        tags.append("learned_hint_improvement")
    if all(type(good.get(c)) is bool for c in "ABCD"):
        for condition in "BCD":
            if good[condition] is True and all(not good[c] for c in "ABCD" if c != condition):
                tags.append(condition + "_only_correct")
        if not any(good.values()):
            tags.append("all_wrong")
    if good.get("D") is False:
        tags.append("D_wrong")
    if q["changed_answers"]:
        tags.append("changed_answers")
    if q["answer_key_conflict"]:
        tags.append("answer_key_conflict")
    suspected = [row for row in by_condition.values() if row.get("review", {}).get("math_status") == "inappropriate"]
    if suspected:
        tags.append("reasoning_suspected")
        if any(row.get("evaluation", {}).get("correct") is True for row in suspected):
            tags.append("correct_but_reasoning_suspected")
    if any(row.get("review", {}).get("review_status") == "possibly_valid_alternative"
           or row.get("review", {}).get("alternative_solution") is True for row in by_condition.values()):
        tags.append("possible_alternative")
    baseline_total = by_condition.get("A", {}).get("usage", {}).get("total_token_count")
    for condition in "BCD":
        value = by_condition.get(condition, {}).get("usage", {}).get("total_token_count")
        if value is not None and baseline_total is not None and (
                value - baseline_total >= 500 or (baseline_total > 0 and value / baseline_total >= 1.5 and value - baseline_total >= 250)):
            tags.append("large_token_change")
            break
    if any("truncated" in (row.get("status") or "") or "MAX_TOKENS" in str(row.get("finish_reasons", []))
           or len(row.get("output_text") or "") > 15000 for row in by_condition.values()):
        tags.append("incomplete")
    if any(row.get("status") == "success" and type(row.get("evaluation", {}).get("correct")) is not bool for row in by_condition.values()):
        tags.append("ungraded")
    if any(row.get("status") != "success" for row in by_condition.values()):
        tags.append("api_incomplete")
    if any(row.get("status") == "success" and row.get("review", {}).get("review_status") == "deferred" for row in by_condition.values()):
        tags.append("review_pending")
    q.update(case_tags=tags, reasoning_suspected=bool(suspected), review_pending="review_pending" in tags)
    return tags


def write_cases(output, questions):
    output = Path(output)
    folder = output / "case_reports"
    folder.mkdir(parents=True, exist_ok=True)
    questions = list(questions)
    previous_index = []
    if (folder / "index.csv").is_file():
        with (folder / "index.csv").open(encoding="utf-8-sig", newline="") as stream:
            previous_index = list(csv.DictReader(stream))
    index = []
    for q in questions:
        if not q["expected_generation"]:
            continue
        tags = select_tags(q)
        if not tags:
            continue
        lines = [f"# {q['id']} · 네 조건 비교", "", f"[수식 비교 화면](../report.html#{q['id']}) · [사례 목록](README.md)", "",
                 "분류: " + " / ".join(str(q["metadata"].get(key, "")) for key in ("curriculum", "unit", "subunit", "type")), "",
                 "자동 선별 사유: " + ", ".join(CASE_LABELS[tag] for tag in tags), "",
                 "## 원본 문제와 선택지", "", q["problem_text"], "", "## 원본 정답", "", str(q["reference_answer"]), "",
                 "## 원본 해설 전체", "", q["reference_solution"], ""]
        if q["answer_key_conflict"]:
            evidence = q["key_conflict_evidence"]
            lines += ["## 정답표 충돌 근거 · 원본은 변경하지 않음", "",
                      f"원본: {evidence['original_answer']} / 기존 AI 보조 검토 대안: {evidence['mathematically_supported_answer']}.", "",
                      evidence["reason"], "", "사람의 최종 확정 판정과 구분하며 원본 기준 점수와 보조 기준 점수를 따로 계산했다.", ""]
        for method in q["methods"]:
            row = q["conditions"][method["key"]]
            grade = row.get("evaluation", {})
            usage = row.get("usage", {})
            review = row.get("review", {})
            lines += [f"## {method['label']}", "", f"API 상태: `{row['status']}` · 원본 정답 판정: `{grade.get('correct')}` · 판독 답: `{grade.get('predicted_answer')}`", "",
                      "사용량(미제공=null): `" + json.dumps({key: usage.get(key) for key in (
                          "prompt_token_count", "candidates_token_count", "thoughts_token_count", "cached_content_token_count", "total_token_count")}, ensure_ascii=False) + "`", "",
                      "### 전송 예정 힌트 · API 미실행" if row["status"] == "not_run" else "### 실제 요청의 힌트", "", "```json", json.dumps((row.get("hint") or {}).get("mapping"), ensure_ascii=False, indent=2), "```", "",
                      "### 생성 풀이 전체", "", row.get("output_text") or "저장된 성공 풀이가 없습니다. 미완료·실패를 오답으로 단정하지 않습니다.", "",
                      "### 풀이 검토 상태", "", f"`{review.get('review_status', 'not_generated')}` · 사람 확정: `{review.get('human_confirmed', False)}`", "",
                      review.get("reason", "수학적 단계는 검토 보류다."), ""]
            if row.get("request_path"):
                lines += [f"[실제 요청 감사 기록](../{row['request_path']})", ""]
        lines += ["## 관찰과 판단의 경계", "",
                  "확인한 사실은 위의 저장된 최종 답·정오·토큰·입력·풀이 전문이다. 토큰 힌트가 차이의 원인이라는 주장은 아직 검증하지 않았다.", "",
                  "풀이 문장이 원본과 다르다는 사실만으로 수학적 오류라고 판단하지 않는다. 구체적인 잘못된 단계가 검증되지 않은 응답은 검토 보류로 남긴다.", "",
                  "자동 선별 기준: 전체 토큰 증가≥500 또는 증가≥250이면서 A의1.5배 이상. 장황·불완전 후보는 MAX_TOKENS/잘림 상태 또는15000자 초과이며 그 자체가 오류 확정은 아니다."]
        presentation = clean_presentation_blank_lines("\n".join(lines).rstrip() + "\n")
        (folder / f"{q['id']}.md").write_text(presentation, encoding="utf-8")
        index.append({"id": q["id"], "split": q["split"], "case_tags": ",".join(tags),
                      "case_path": f"{q['id']}.md", "viewer": f"../report.html#{q['id']}",
                      "user_review_needed": True})
    write_csv(folder / "index.csv", index, ["id", "split", "case_tags", "case_path", "viewer", "user_review_needed"])
    lines = ["# 풀이·오류·특이 사례", "", "자동 선별은 수학적 오류 확정이 아니다. 각 문서에서 원본과 네 조건 풀이를 함께 읽는다.", "",
             "[수식 비교 화면](../report.html) · [정확한 전체 사례 목록](index.csv) · [전체 풀이 검토 상태](../review/status.csv)", "",
             "|문항|선별 사유|직접 읽기|", "|---|---|---|"]
    for row in index:
        lines.append(f"|{row['id']}|{', '.join(CASE_LABELS[tag] for tag in row['case_tags'].split(','))}|[사례]({row['case_path']}) · [수식 화면]({row['viewer']})|")
    (folder / "README.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    current_paths = {row["case_path"] for row in index}
    known_ids = {q["id"] for q in questions}
    for row in previous_index:
        identifier, filename = row.get("id"), row.get("case_path")
        if (identifier not in known_ids or filename != f"{identifier}.md" or filename in current_paths
                or Path(filename).name != filename):
            continue
        path = folder / filename
        if path.is_symlink() or not path.is_file():
            continue
        previous = path.read_text(encoding="utf-8")
        header = (f"# {identifier} · 네 조건 비교\n\n"
                  f"[수식 비교 화면](../report.html#{identifier}) · [사례 목록](README.md)\n")
        if previous.startswith(header) and "\n자동 선별 사유: " in previous:
            path.unlink()
    return index
