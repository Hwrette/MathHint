"""정답·사용량 통계. 미제공 토큰과 미채점 응답을 0으로 바꾸지 않는다."""

import math
from typing import Any


TOKEN_NAMES = {
    "prompt_token_count": "입력", "candidates_token_count": "출력",
    "thoughts_token_count": "추론", "total_token_count": "전체",
    "cached_content_token_count": "캐시 입력", "tool_use_prompt_token_count": "도구 입력",
}


def wilson_interval(correct: int, total: int, z: float = 1.959963984540054) -> list[float] | None:
    """정답 비율의 95% Wilson 구간. 평가 문항이 없으면 계산하지 않는다."""
    if total == 0:
        return None
    p = correct / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return [max(0.0, center - margin), min(1.0, center + margin)]


def exact_mcnemar(baseline_only: int, hint_only: int) -> float:
    """두 방식의 정오답이 달랐던 문항으로 McNemar 양측 검정을 한다."""
    n = baseline_only + hint_only
    if not n:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(min(baseline_only, hint_only) + 1)) / (2 ** n))


def record_correct(record: dict | None) -> bool | None:
    if not record or record.get("status") != "success":
        return None
    value = record.get("evaluation", {}).get("correct")
    return value if type(value) is bool else None


def _valid_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def usage_summary(rows: list[dict]) -> dict:
    result = {}
    successful = [row for row in rows if row.get("status") == "success"]
    # Retry history is preserved in each latest record by CompareGeneration.
    all_attempts = [attempt for row in rows for attempt in row.get("attempts", [])]
    attempts = [attempt for attempt in all_attempts
                if not attempt.get("request_skipped") and attempt.get("status") != "skipped"]
    for field in TOKEN_NAMES:
        values = [attempt.get("usage", {}).get(field) for attempt in attempts]
        known = [value for value in values if _valid_number(value)]
        final = [row.get("usage", {}).get(field) for row in successful]
        final_known = [value for value in final if _valid_number(value)]
        result[field] = {
            "all_attempts": len(values), "skipped_without_request": len(all_attempts) - len(attempts),
            "known_attempts": len(known),
            "missing_attempts": len(values) - len(known), "known_sum": sum(known) if known else None,
            "strict_total": sum(known) if values and len(known) == len(values) else None,
            "successful_responses": len(successful), "known_successful_responses": len(final_known),
            "successful_response_known_sum": sum(final_known) if final_known else None,
            "successful_response_strict_total": (sum(final_known)
                                                   if successful and len(final_known) == len(successful) else None),
            "missing_successful_responses": len(successful) - len(final_known),
            "successful_response_mean": sum(final_known) / len(final_known) if final_known else None,
        }
    return result


def answer_metrics(rows: list[dict], expected_count: int) -> dict:
    graded = [row for row in rows if record_correct(row) is not None]
    correct = sum(record_correct(row) is True for row in graded)
    return {
        "expected_questions": expected_count, "recorded_questions": len(rows),
        "successful_responses": sum(row.get("status") == "success" for row in rows),
        "graded_responses": len(graded), "correct": correct,
        "incorrect": len(graded) - correct, "ungraded_or_missing": expected_count - len(graded),
        "accuracy_on_graded": correct / len(graded) if graded else None,
        "accuracy_on_graded_wilson95": wilson_interval(correct, len(graded)),
        "confirmed_correct_per_expected_question": correct / expected_count if expected_count else None,
        "grading_coverage": len(graded) / expected_count if expected_count else None,
    }
