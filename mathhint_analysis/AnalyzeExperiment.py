"""저장된 회귀·군집·Gemini 결과를 집계해 표와 흑백 PDF로 정리한다.

아래 설정을 바꾸고 실행한다. 데이터 읽기 → 정답률·토큰 집계 → 보고서 저장 순서다.
정답 일치, 풀이 적절성, API 사용량은 각각 따로 평가한다.
"""

from __future__ import annotations

from collections import defaultdict
import csv
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any


# 설정: 학습·생성을 마친 실험 폴더를 지정한다.
ROOT = Path(__file__).resolve().parents[1]
RUN_ROOT = ROOT / "outputs/model_comparison"
GENERATION_NAME = "generation_top_tokens"
OUTPUT = RUN_ROOT / "report_top_tokens"
SOLUTION_REVIEW = None  # 다른 검토 요약을 쓸 때만 JSON 경로를 지정한다.


METHODS = ("baseline", "regression_hint")
METHOD_NAMES = {"baseline": "기본 풀이", "regression_hint": "회귀 가이드 추가"}
TOKEN_NAMES = {
    "prompt_token_count": "입력", "candidates_token_count": "출력",
    "thoughts_token_count": "추론", "total_token_count": "전체",
    "cached_content_token_count": "캐시 입력", "tool_use_prompt_token_count": "도구 입력",
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


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


def _correct(record: dict | None) -> bool | None:
    if not record or record.get("status") != "success":
        return None
    value = record.get("evaluation", {}).get("correct")
    return value if type(value) is bool else None


def _valid_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def reused_control(record: dict) -> bool:
    return record.get("response_origin") == "reused_control"


def type_count_note(training: dict) -> str:
    """같은 데이터의 유형 수를 학습 결과에서 읽는다."""
    if not training.get("clustering"):
        return "학습·테스트 유형 수가 기록되어 있지 않다."
    metrics = training["clustering"][0]["metrics"]
    return (f"학습 유형{metrics['train']['type']['n_labels']}개, "
            f"테스트 유형{metrics['test']['type']['n_labels']}개.")


def paired_summary(records: dict[tuple[str, str], dict], ids: list[str]) -> dict:
    pairs = [(identifier, _correct(records.get((identifier, METHODS[0]))),
              _correct(records.get((identifier, METHODS[1])))) for identifier in ids]
    valid = [(identifier, a, b) for identifier, a, b in pairs if a is not None and b is not None]
    cells = {"both_correct": 0, "baseline_only_correct": 0, "regression_only_correct": 0, "both_incorrect": 0}
    outcomes = []
    for identifier, a, b in valid:
        key = "both_correct" if a and b else "baseline_only_correct" if a else "regression_only_correct" if b else "both_incorrect"
        cells[key] += 1
        outcomes.append({"id": identifier, "baseline_correct": a, "regression_hint_correct": b, "outcome": key})
    correct_a = cells["both_correct"] + cells["baseline_only_correct"]
    correct_b = cells["both_correct"] + cells["regression_only_correct"]
    n = len(valid)
    result = {"expected_pairs": len(ids), "both_graded_pairs": n,
              "excluded_pairs": len(ids) - n, **cells,
              "baseline_correct": correct_a, "regression_hint_correct": correct_b,
              "baseline_accuracy": correct_a / n if n else None,
              "regression_hint_accuracy": correct_b / n if n else None,
              "baseline_wilson95": wilson_interval(correct_a, n),
              "regression_hint_wilson95": wilson_interval(correct_b, n),
              "accuracy_difference_hint_minus_baseline": (correct_b - correct_a) / n if n else None,
              "exact_mcnemar_two_sided_p": exact_mcnemar(cells["baseline_only_correct"], cells["regression_only_correct"]),
              "outcomes": outcomes}
    if n:
        import numpy as np
        changes = np.array([int(b) - int(a) for _, a, b in valid], dtype=float)
        rng = np.random.default_rng(42)
        samples = changes[rng.integers(0, n, size=(10000, n))].mean(axis=1)
        result["paired_question_bootstrap95_difference"] = [float(x) for x in np.quantile(samples, [.025, .975])]
        result["bootstrap_note"] = "10,000 paired question resamples; seed42; sampling uncertainty, not repeat-generation variability"
    else:
        result["paired_question_bootstrap95_difference"] = None
    return result


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
    graded = [row for row in rows if _correct(row) is not None]
    correct = sum(_correct(row) is True for row in graded)
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


def adjudicated_scores(run_root: Path, latest: dict, expected: list[str]) -> dict | None:
    """Supplement source-key scores with explicit, traceable mathematical review.

    This never alters a dataset, request, saved response, or original-key score.
    AI-assisted review is labelled as such; it is not certified human ground truth.
    """
    path = run_root / "audit/audited_answer_conflicts.json"
    if not path.exists():
        return None
    conflicts = [row for row in read_json(path).get("records", []) if row.get("id") in expected]
    if not conflicts:
        return None
    from mathhint_solver.AnswerEvaluation import evaluate_answer
    reviewed = dict(latest)
    evaluations = []
    for conflict in conflicts:
        identifier = conflict["id"]
        replacement = conflict["mathematically_supported_answer"]
        for method in METHODS:
            key = identifier, method
            row = latest.get(key)
            if not row:
                continue
            if row.get("reference_answer_text") != conflict["original_answer"]:
                raise ValueError(f"Original answer differs from audited conflict evidence: {identifier}")
            source_hash = row.get("reference", {}).get("source", {}).get("source_sha256")
            if conflict.get("source_sha256") and source_hash != conflict["source_sha256"]:
                raise ValueError(f"Source hash differs from audited conflict evidence: {identifier}")
            evaluation = (evaluate_answer(row.get("output_text", ""), replacement, row.get("problem_text", ""))
                          if row.get("status") == "success" else row.get("evaluation", {}))
            reviewed[key] = {**row, "evaluation": evaluation}
            evaluations.append({"id": identifier, "method": method,
                                "original_evaluation": row.get("evaluation"),
                                "mathematical_review_evaluation": evaluation,
                                "original_answer": conflict["original_answer"], "review_answer": replacement})
    return {
        "label": "AI-assisted mathematics-based supplemental answer-key evaluation; not certified human ground truth",
        "source_path": str(path.relative_to(run_root)),
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "conflict_count": len(conflicts), "conflicts": conflicts,
        "raw_data_or_responses_modified": False,
        "evaluations": evaluations,
        "methods": {method: answer_metrics([row for (identifier, name), row in reviewed.items() if name == method], len(expected))
                    for method in METHODS},
        "paired": paired_summary(reviewed, expected),
    }


def generation_directory(run_root: Path, name: str) -> Path:
    """Select one generation run; never merge alternate hint experiments."""
    if not name or name in {".", ".."} or Path(name).name != name or "/" in name or "\\" in name:
        raise ValueError("generation-name must be a single folder name under run-root.")
    return run_root / name


def hint_description(hint: dict) -> str:
    mode, top_k = hint.get("mode", "full_vector"), hint.get("top_k")
    if mode in {"top_tokens", "top_k", "major_tokens"}:
        return f"예측 빈도가 높은 주요 토큰 최대{top_k}개와 빈도를 풀이 가이드로 전달"
    return "음수 제거·소수점3자리 반올림한 모든 양수 좌표를 토큰:빈도로 전달"


def load_solution_review(run_root: Path, generation: Path, config_id: str,
                         current_responses_sha: str | None, review_path: Path | None = None) -> dict | None:
    explicit = review_path is not None
    path = review_path or run_root / "solution_review/solution_review_summary.json"
    if not path.exists():
        if explicit:
            raise ValueError(f"Solution review summary not found: {path}")
        return None
    summary = read_json(path)
    if summary.get("config_id") != config_id:
        if explicit:
            raise ValueError("Solution review belongs to a different generation experiment.")
        return {"status": "excluded_different_generation", "path": str(path),
                "reason": "Default review config_id differs from selected generation; no ratings were combined."}
    snapshot = summary.get("source_snapshot", {})
    source_generation = snapshot.get("generation_folder")
    if source_generation and Path(source_generation).resolve() != generation.resolve():
        raise ValueError("Review generation folder differs from selected experiment.")
    for methods in summary.get("review_kinds", {}).values():
        if any("mathematical_appropriateness" not in row for row in methods.values()):
            raise ValueError("Review summary must separate mathematical_appropriateness from all-criteria overall.")
    current = snapshot.get("sha256") == current_responses_sha
    return {"status": "included_current_snapshot" if current else "included_earlier_snapshot",
            "path": str(path), "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "review_response_snapshot_matches_current": current, "summary": summary,
            "primary_appropriateness_field": "mathematical_appropriateness",
            "note": "AI suggestions were method-aware and are not blinded human ground truth. Human blind packets remain separate. Unreviewed solutions are not appropriate. Mathematical appropriateness uses three mathematical criteria only; curriculum scope remains separate."}


def analyze(run_root: Path, generation_name: str = "generation", solution_review_path: Path | None = None) -> dict:
    generation = generation_directory(run_root, generation_name)
    config_manifest = read_json(generation / "config.json")
    config = config_manifest["config"]
    expected = config["test_ids"]
    if len(set(expected)) != len(expected):
        raise ValueError("Duplicate test IDs in immutable experiment config.")
    latest = {}
    path = generation / "responses.jsonl"
    all_rows = []
    if path.exists():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("config_id") != config_manifest["config_id"]:
                raise ValueError(f"Config mismatch in responses line {number}")
            key = row.get("id"), row.get("method")
            if key[0] not in expected or key[1] not in METHODS:
                raise ValueError(f"Unexpected question or method in responses line {number}")
            all_rows.append(row)
            latest[key] = row
    training = read_json(run_root / "training/training_summary.json")
    if config["generation_id"] != training["generation_id"]:
        raise ValueError("Training and generation dataset versions differ.")
    reused_rows = [row for row in latest.values() if reused_control(row)]
    if any(row["method"] != "baseline" for row in reused_rows):
        raise ValueError("Only identical baseline controls may be reused across hint experiments.")
    control_reuse = {
        "count": len(reused_rows), "ids": sorted(row["id"] for row in reused_rows),
        "source_directories": sorted({row.get("provenance", {}).get("source_directory", "unknown") for row in reused_rows}),
        "records": [{"id": row["id"], "method": row["method"], "model_version": row.get("model_version"),
                     "started_at": row.get("started_at"), "completed_at": row.get("completed_at"),
                     "provenance": row.get("provenance")} for row in reused_rows],
        "new_condition_requests_expected": len(expected) * len(METHODS) - len(reused_rows),
        "new_condition_records_observed": len(latest) - len(reused_rows),
        "accounting_note": "Reused control response tokens are informational comparison usage, not newly incurred API usage in this run.",
    }
    methods = {}
    for method in METHODS:
        rows = [row for (identifier, name), row in latest.items() if name == method]
        methods[method] = {
            **answer_metrics(rows, len(expected)),
            "usage": usage_summary(rows),
            "reused_control_records": sum(reused_control(row) for row in rows),
            "incremental_usage": usage_summary([row for row in rows if not reused_control(row)]),
        }
    paired_tokens = {}
    for field in TOKEN_NAMES:
        differences, base_values, hint_values = [], [], []
        for identifier in expected:
            left, right = (latest.get((identifier, method), {}) for method in METHODS)
            a, b = (row.get("usage", {}).get(field) for row in (left, right))
            if left.get("status") == right.get("status") == "success" and _valid_number(a) and _valid_number(b):
                base_values.append(a)
                hint_values.append(b)
                differences.append(b - a)
        paired_tokens[field] = {
            "known_successful_pairs": len(differences),
            "baseline_sum": sum(base_values) if differences else None,
            "regression_hint_sum": sum(hint_values) if differences else None,
            "mean_difference_hint_minus_baseline": sum(differences) / len(differences) if differences else None,
            "relative_difference": (sum(hint_values) / sum(base_values) - 1) if base_values and sum(base_values) else None,
        }
    unit_ids = defaultdict(list)
    for identifier in expected:
        row = next((latest[(identifier, method)] for method in METHODS if (identifier, method) in latest), None)
        if row:
            unit_ids[(row.get("subject", ""), row.get("unit", ""))].append(identifier)
    per_unit = [{"subject": subject, "unit": unit, **paired_summary(latest, ids)}
                for (subject, unit), ids in sorted(unit_ids.items())]
    response_sha = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
    return {
        "schema_version": 2, "config_id": config_manifest["config_id"],
        "generation_name": generation_name,
        "hint": {"mode": config.get("hint_mode", "full_vector"),
                 "top_k": config.get("hint_top_k", config.get("top_k")),
                 "transform": config.get("hint_transform")},
        "dataset_generation_id": config["generation_id"],
        "model": config["model"], "thinking_level": config["thinking_level"],
        "temperature": config["temperature"], "max_output_tokens": config["max_output_tokens"],
        "expected_questions": len(expected), "raw_log_rows": len(all_rows),
        "latest_condition_records": len(latest), "methods": methods,
        "control_reuse": control_reuse,
        "adjudicated_answer_scores": adjudicated_scores(run_root, latest, expected),
        "solution_review": load_solution_review(run_root, generation, config_manifest["config_id"], response_sha, solution_review_path),
        "paired": paired_summary(latest, expected), "paired_tokens": paired_tokens,
        "per_unit": per_unit, "training": training,
        "source_sha256": {"config": hashlib.sha256((generation / "config.json").read_bytes()).hexdigest(),
                          "responses": response_sha},
        "limitations": [
            f"A single generation per method for {len(expected)} fixed held-out questions; repeated-run variability was not estimated.",
            "Correctness is final-answer agreement with original answer, not verification of mathematical reasoning or curriculum compliance.",
            "Ungradable, incomplete and missing responses are reported separately, not silently treated as wrong.",
            "Clustering labels and original answers are never generation hints. Linear-regression hints contain predicted frequencies only.",
            type_count_note(training) + " Higher cluster counts can increase purity through fragmentation and do not imply semantic separation.",
            "Results describe raw frequency counts and Euclidean K-means; no comparison with normalized counts or embeddings was performed.",
            "Missing usage metadata is unknown; strict token totals are null if any attempt lacks the field.",
            "If controls are reused, comparison includes their original token usage but incremental API totals exclude imported requests; generation times may differ.",
        ],
    }


def _pct(value: float | None, digits: int = 2) -> str:
    return "미제공" if value is None else f"{value * 100:.{digits}f}%"


def _num(value: float | int | None, digits: int = 1) -> str:
    if value is None:
        return "미제공"
    return f"{value:,.{digits}f}" if digits else f"{value:,.0f}"


def solution_review_markdown(result: dict, output: Path) -> list[str]:
    review = result.get("solution_review")
    if not review or not review.get("summary"):
        return []
    summary = review["summary"]
    lines = ["## 풀이 적절성 검토 — 정답 일치율과 분리", "",
             "수학적 적절성은 논리 타당성·설명 충분성·원본 해설과의 수학적 일관성을 검토한 결과다. "
             "교과 범위는 별도 항목이다. **AI 보조 검토 제안과 사람의 검토를 합치지 않았으며, AI 판단은 독립적으로 인증된 정답이 아니다.** "
             "AI 검토는 방식 정보를 볼 수 있는 상태에서 이루어졌고 블라인드 평가가 아니다. 사람용 블라인드 검토표는 별도로 제공한다. "
             "원문 인용·응답 해시가 맞는다는 검사는 수학 판정 자체의 독립 검증을 의미하지 않는다. "
             "미검토를 적절로 간주하지 않았고, 적절 비율의 분모에는 검토된 불확실 판정도 포함했다.", ""]
    if not review["review_response_snapshot_matches_current"]:
        lines += ["검토표는 현재 응답 파일보다 이전 스냅샷을 기준으로 한다. 아래 검토 문항 수와 미검토 수를 확인해야 한다.", ""]
    lines += ["| 검토 주체 | 방식 | 검토/대상 | 적절 | 부적절 | 불확실 | 적절/검토 비율 | 미검토 |",
              "|---|---|---:|---:|---:|---:|---:|---:|"]
    for kind, kind_label in (("ai_suggestion", "AI 보조 제안"), ("human", "사람")):
        for method in METHODS:
            row = summary.get("review_kinds", {}).get(kind, {}).get(method)
            if not row:
                continue
            overall = row["mathematical_appropriateness"]
            total = row["total_eligible_solutions"]
            lines.append(f"| {kind_label} | {METHOD_NAMES[method]} | {overall['reviewed_count']}/{total} | "
                         f"{overall['appropriate']} | {overall['inappropriate']} | {overall['uncertain']} | "
                         f"{_pct(overall['appropriate_rate_on_reviewed'])} | {total - overall['reviewed_count']} |")
    lines += ["", "교과 범위 판정은 실제 수업 범위 메모가 불충분하면 불확실로 남긴다. "
              "최종 답이 맞아도 잘못된 중간 계산·설명 생략·범위를 벗어난 도구 사용은 별도로 검토한다.", "",
              "| 검토 주체 | 방식 | 범위 적합 | 범위 부적합 | 불확실 | 미검토 |",
              "|---|---|---:|---:|---:|---:|"]
    for kind, kind_label in (("ai_suggestion", "AI 보조 제안"), ("human", "사람")):
        for method in METHODS:
            row = summary.get("review_kinds", {}).get(kind, {}).get(method)
            if not row:
                continue
            criterion = row["criteria"]["curriculum_scope"]
            lines.append(f"| {kind_label} | {METHOD_NAMES[method]} | {criterion['appropriate']} | {criterion['inappropriate']} | "
                         f"{criterion['uncertain']} | {row['total_eligible_solutions'] - criterion['reviewed_count']} |")
    review_dir = Path(review["path"]).parent
    lines += ["", f"[풀이 검토 파일]({os.path.relpath(review_dir, output)})의 원문 인용·근거·응답 해시로 각 판정을 추적할 수 있다.", ""]
    return lines


def markdown_report(result: dict, run_root: Path, output: Path) -> str:
    p, training = result["paired"], result["training"]
    report_link = os.path.relpath(run_root / result["generation_name"] / "report.html", output)
    lines = ["# MathHint 모델 학습·풀이 생성 비교", "",
             f"학습 {training['train_count']}문항 · 테스트 {result['expected_questions']}문항. "
             f"모델 `{result['model']}`, 추론 `{result['thinking_level']}`, temperature={result['temperature']}.", "",
             f"선택한 실험 폴더: `{result['generation_name']}`. {hint_description(result['hint'])}. "
             "다른 가이드 방식의 응답은 이 집계에 합치지 않았다.", "",
             f"기록된 조건별 요청 {result['latest_condition_records']}/{result['expected_questions'] * 2}개. "
             "일부 요청이 미완료라면 아래 결과도 중간 집계다.", "",
             f"동일 입력·설정의 기본 응답 재사용 **{result['control_reuse']['count']}개**. "
             f"이번 실험의 새 조건별 요청 대상은 {result['control_reuse']['new_condition_requests_expected']}개다. "
             "재사용 응답의 토큰은 방식 비교에 포함하지만 이번 실행의 신규 사용량에는 포함하지 않는다. "
             "각 원본 폴더·설정ID·응답 해시·원래 생성시각은 통계 JSON의 `control_reuse`에 보존했다.", "",
             f"[문항별 입력·출력·실제 정답·사용량 열람]({report_link})", "",
             "## 풀이 생성 비교 — 원본 정답표 기준", "",
             "정확도는 원본 정답표와 최종 답의 일치율이다. 풀이 과정의 타당성은 별도로 검토해야 한다. "
             "원본 정답표 충돌이 확인된 문항은 아래 수학 검토 기준의 보조 점수도 함께 표시한다.", "",
             "| 방식 | 정답/판독 가능 | 판독 가능 응답 정확도 | 정답 확인/전체 테스트 | 미판독·실패·미실행 |",
             "|---|---:|---:|---:|---:|"]
    for method in METHODS:
        row = result["methods"][method]
        lines.append(f"| {METHOD_NAMES[method]} | {row['correct']}/{row['graded_responses']} | {_pct(row['accuracy_on_graded'])} | "
                     f"{row['correct']}/{row['expected_questions']} ({_pct(row['confirmed_correct_per_expected_question'])}) | {row['ungraded_or_missing']} |")
    lines += ["", f"두 방식 모두 판독 가능한 동일 문항은 **{p['both_graded_pairs']}개**다. 이 문항에서 기본 풀이 "
              f"{_pct(p['baseline_accuracy'])}, 회귀 가이드 추가 {_pct(p['regression_hint_accuracy'])}, 차이(회귀−기본) "
              f"{_num(None if p['accuracy_difference_hint_minus_baseline'] is None else p['accuracy_difference_hint_minus_baseline'] * 100)}%p다.", "",
              f"둘 다 정답 {p['both_correct']} · 기본만 정답 {p['baseline_only_correct']} · 회귀만 정답 "
              f"{p['regression_only_correct']} · 둘 다 오답 {p['both_incorrect']}.", "",
              f"Exact McNemar 양측 p={p['exact_mcnemar_two_sided_p']:.4g}. "
              "문항 표본의 차이에 대한 보조 통계이며, 같은 문제를 반복 생성했을 때의 변동성을 나타내지 않는다.", ""]
    adjudicated = result.get("adjudicated_answer_scores")
    if adjudicated:
        review_pair = adjudicated["paired"]
        lines += ["## 원본 정답표 충돌과 별도 수학 검토 점수", "",
                  f"원본 정답표와 수학 계산이 충돌하는 문항 **{adjudicated['conflict_count']}개**가 확인됐다. "
                  "아래는 AI 보조 수학 검토 기준의 추가 평가이며, 교사 등 사람이 인증한 새 정답표로 간주하지 않는다. "
                  "원본 정답·데이터·API 입력·응답·위 원본 기준 점수는 수정하지 않았다.", ""]
        for conflict in adjudicated["conflicts"]:
            lines.append(f"- `{conflict['id']}`: 원본 표기 **{conflict['original_answer']}** "
                         f"({conflict.get('original_answer_value', '')}), 수학 검토 **{conflict['mathematically_supported_answer']}** "
                         f"({conflict.get('mathematically_supported_value', '')}). {conflict['reason']}")
        lines += ["", "| 방식 | 수학 검토 기준 정답/판독 가능 | 수학 검토 기준 정답률 | 정답 확인/전체 테스트 |",
                  "|---|---:|---:|---:|"]
        for method in METHODS:
            row = adjudicated["methods"][method]
            lines.append(f"| {METHOD_NAMES[method]} | {row['correct']}/{row['graded_responses']} | "
                         f"{_pct(row['accuracy_on_graded'])} | {row['correct']}/{row['expected_questions']} |")
        lines += ["", f"수학 검토 기준 공통 판독 n={review_pair['both_graded_pairs']}: "
                  f"기본 {_pct(review_pair['baseline_accuracy'])}, 회귀 {_pct(review_pair['regression_hint_accuracy'])}. "
                  f"기본만 정답 {review_pair['baseline_only_correct']}, 회귀만 정답 {review_pair['regression_only_correct']}. "
                  f"Exact McNemar 양측 p={review_pair['exact_mcnemar_two_sided_p']:.4g}.", "",
                  "보조 점수의 Wilson95%·대응 문항 부트스트랩 구간과 문항별 평가 변경 근거는 "
                  "`integrated_summary.json`의 `adjudicated_answer_scores`에 보존했다.", ""]
    lines += solution_review_markdown(result, output)
    lines += ["## 토큰 사용량", "", "먼저 최종 성공 응답의 사용량을 비교한다. 요청 실패·재시도의 불명확한 사용량은 아래에 별도로 기록한다.", "",
              "| 항목 | 기본 성공 응답 합계 | 회귀 성공 응답 합계 | 기본 성공 응답 평균 | 회귀 성공 응답 평균 | 같은 문항 평균 차이 |",
              "|---|---:|---:|---:|---:|---:|"]
    for field, label in TOKEN_NAMES.items():
        a, b = (result["methods"][method]["usage"][field] for method in METHODS)
        delta = result["paired_tokens"][field]
        lines.append(f"| {label} | {_num(a['successful_response_strict_total'], 0)} | {_num(b['successful_response_strict_total'], 0)} | "
                     f"{_num(a['successful_response_mean'])} | {_num(b['successful_response_mean'])} | "
                     f"{_num(delta['mean_difference_hint_minus_baseline'])} (n={delta['known_successful_pairs']}) |")
    total_delta = result["paired_tokens"]["total_token_count"]
    if total_delta["known_successful_pairs"]:
        lines += ["", f"같은 성공 문항 {total_delta['known_successful_pairs']}개의 전체 토큰 합계는 기본 "
                  f"{_num(total_delta['baseline_sum'], 0)}, 회귀 {_num(total_delta['regression_hint_sum'], 0)}이다. "
                  f"차이(회귀−기본)는 {_num(total_delta['regression_hint_sum'] - total_delta['baseline_sum'], 0)}토큰 "
                  f"({_pct(total_delta['relative_difference'])})이다."]
    lines += ["", "이번 실행의 **새 요청**에서 실패·재시도를 포함한 요청 시도는 다음과 같다. 재사용한 대조 응답의 원래 시도는 제외한다. "
              "알려진 사용량의 합은 실제 전체 합계의 대체값이 아니다. "
              "미제공이 하나라도 있으면 전체 시도의 엄밀한 합계는 미제공으로 표시하며0으로 간주하지 않는다.", "",
              "| 항목 | 기본 전체 시도 수 | 기본 알려진 합 | 기본 미제공 시도 | 기본 엄밀 합계 | 회귀 전체 시도 수 | 회귀 알려진 합 | 회귀 미제공 시도 | 회귀 엄밀 합계 |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for field, label in TOKEN_NAMES.items():
        a, b = (result["methods"][method]["incremental_usage"][field] for method in METHODS)
        lines.append(f"| {label} | {a['all_attempts']} | {_num(a['known_sum'], 0)} | {a['missing_attempts']} | {_num(a['strict_total'], 0)} | "
                     f"{b['all_attempts']} | {_num(b['known_sum'], 0)} | {b['missing_attempts']} | {_num(b['strict_total'], 0)} |")
    reg = training["regression"]["metrics"]
    lines += ["", "## 회귀 학습", "",
              f"`{training['regression']['architecture']}` · {training['regression']['optimizer']} · {training['regression']['epochs']}epochs · "
              f"학습률 {training['regression']['learning_rate']}. 저장된 학습 문항만 가중치 갱신에 사용했다.", "",
              "| 입력에 사용할 해설 벡터 | 테스트 MSE | 테스트 MAE | 테스트 평균 코사인 유사도 |",
              "|---|---:|---:|---:|"]
    for key, label in (("raw", "회귀 원시 예측"), ("clipped_nonnegative", "음수를0으로 만든 회귀 예측"), ("training_mean_baseline", "학습 해설 벡터 평균")):
        row = reg["test"][key]
        lines.append(f"| {label} | {row['mse']:.4f} | {row['mae']:.4f} | {row['mean_cosine_similarity']:.4f} |")
    lines += ["", "API 회귀 가이드: " + hint_description(result["hint"]) + ". "
              "실제 테스트 정답·해설·유형은 넣지 않았다. 벡터 예측 오차 감소와 풀이 정답률 증가는 서로 다른 평가다.", "",
              "## 군집화와 실제 분류의 대응", "",
              "학습 데이터로 중심을 만들고, 초기화 결과 중 학습 군집 내 거리 합이 가장 작은 결과를 골랐다. "
              "초기화 횟수: " + ", ".join(f"k={row['k']}에서 {row['restarts']}회" for row in training['clustering']) + ". "
              "테스트 라벨로 군집 수·초기화를 고르지 않았다. 아래는 테스트 결과다.", "",
              "| k | 비교 라벨 | ARI | NMI | Purity | 학습 다수 라벨을 이용한 테스트 분류 정확도 |",
              "|---:|---|---:|---:|---:|---:|"]
    for config in training["clustering"]:
        level = config["nominal_target_level"]
        row = config["metrics"]["test"][level]
        label = {"subject": "과목", "unit": "단원", "type": "세부 유형"}[level]
        lines.append(f"| {config['k']} | {label} | {row['adjusted_rand_index']:.4f} | "
                     f"{row['normalized_mutual_information']:.4f} | {row['purity']:.4f} | "
                     f"{_pct(row['accuracy_using_train_cluster_majority'])} |")
    lines += ["", type_count_note(training) + " 군집 수가 커지면 작은 군집이 늘어 Purity·NMI가 높아지기 쉽다. "
              "ARI와 학습 라벨로 정한 유형의 테스트 정확도를 함께 봐야 한다. "
              "현재 실험은 군집별 설명을 풀이 입력에 넣지 않았으며, 빈도 벡터가 분류 구조를 담는지 평가하는 용도로 사용했다.", "",
              "## 해석 범위", "",
              f"- 테스트{result['expected_questions']}문항에 방식별1회 생성한 결과다. 반복 실행에 따른 변동성과 다른 데이터에 대한 일반화는 추가 실험이 필요하다.",
              "- 자동 판정은 최종 정답만 확인한다. 교과 밖 풀이·논리 오류는 사람이 출력을 읽고 검토해야 한다.",
              "- 원시 빈도와 유클리드 거리를 사용했다. 정규화·TF-IDF·임베딩과의 우열은 이 결과만으로 판단할 수 없다.",
              "- 학습·테스트 ID, 입력 전문, 예측 벡터, 원본 정답, 응답 전문, 사용량과 요청 오류를 보존했다.", ""]
    return "\n".join(lines)


def render_figures(result: dict, run_root: Path, output: Path) -> list[Path]:
    os.environ.setdefault("MPLCONFIGDIR", str(output / ".matplotlib_cache"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    from matplotlib.backends.backend_pdf import PdfPages
    import numpy as np
    font_path = Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
    if font_path.exists():
        font_manager.fontManager.addfont(str(font_path))
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=str(font_path)).get_name()
    plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False,
                         "axes.unicode_minus": False, "figure.dpi": 160, "font.size": 10})
    p = result["paired"]
    figures = []
    a, b = p["baseline_accuracy"], p["regression_hint_accuracy"]
    fig, ax = plt.subplots(figsize=(7.5, 4.8))
    if a is not None and b is not None:
        ci = [p["baseline_wilson95"], p["regression_hint_wilson95"]]
        values = np.array([a, b]) * 100
        errors = np.array([[value - bounds[0] * 100 for value, bounds in zip(values, ci)],
                           [bounds[1] * 100 - value for value, bounds in zip(values, ci)]])
        bars = ax.bar([0, 1], values, color=["white", ".65"], edgecolor="black", yerr=errors, capsize=5)
        bars[1].set_hatch("///")
        for bar, value in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, max(3, value / 2), f"{value:.2f}%", ha="center")
    else:
        ax.text(.5, .5, "두 조건 모두 채점 가능한 응답이 아직 없습니다.", ha="center", transform=ax.transAxes)
    ax.set_xticks([0, 1], [METHOD_NAMES[m] for m in METHODS])
    ax.set_ylim(0, 105)
    ax.set_ylabel("최종 정답 일치율 (%)")
    ax.set_title(f"원본 정답표 기준 비교 (공통 판독 n={p['both_graded_pairs']})")
    ax.text(.5, -.18, "오차 막대: 방식별 Wilson95% 신뢰구간 · 풀이 과정의 정확성은 별도 검토", ha="center", transform=ax.transAxes, fontsize=9)
    fig.tight_layout()
    figures.append(("paired_accuracy", fig))

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    matrix = np.array([[p["both_correct"], p["baseline_only_correct"]],
                       [p["regression_only_correct"], p["both_incorrect"]]])
    axes[0].imshow(matrix, cmap="Greys", vmin=0, vmax=max(1, matrix.max()))
    for (i, j), count in np.ndenumerate(matrix):
        axes[0].text(j, i, str(count), ha="center", va="center", fontsize=20,
                     color="white" if count > matrix.max() / 2 else "black")
    axes[0].set_xticks([0, 1], ["회귀 정답", "회귀 오답"])
    axes[0].set_yticks([0, 1], ["기본 정답", "기본 오답"])
    axes[0].set_title("같은 문항의 결과 변화")
    fields = ["prompt_token_count", "candidates_token_count", "thoughts_token_count", "total_token_count"]
    x = np.arange(4)
    for offset, method, color, hatch in ((-.18, METHODS[0], "white", ""), (.18, METHODS[1], ".65", "///")):
        values = [result["methods"][method]["usage"][field]["successful_response_mean"] for field in fields]
        heights = [value if value is not None else 0 for value in values]
        bars = axes[1].bar(x + offset, heights, width=.36, color=color, edgecolor="black", hatch=hatch, label=METHOD_NAMES[method])
        for bar, value in zip(bars, values):
            axes[1].text(bar.get_x() + bar.get_width() / 2, bar.get_height(), "미제공" if value is None else f"{value:,.0f}", ha="center", va="bottom", fontsize=8)
    axes[1].set_xticks(x, [TOKEN_NAMES[field] for field in fields])
    axes[1].set_ylabel("성공 응답당 평균 토큰 (제공된 값만)")
    axes[1].set_title("사용량 비교 · 미제공 값은0을 뜻하지 않음")
    axes[1].legend(frameon=False, fontsize=8)
    fig.tight_layout()
    figures.append(("paired_outcomes_and_tokens", fig))

    fig, ax = plt.subplots(figsize=(10, 5.8))
    units = result["per_unit"]
    y = np.arange(len(units))
    for offset, method, color, hatch in ((-.18, METHODS[0], "white", ""), (.18, METHODS[1], ".65", "///")):
        key = "baseline_accuracy" if method == METHODS[0] else "regression_hint_accuracy"
        values = [row[key] * 100 if row[key] is not None else 0 for row in units]
        ax.barh(y + offset, values, height=.36, edgecolor="black", color=color, hatch=hatch, label=METHOD_NAMES[method])
    ax.set_yticks(y, [f"{row['subject']} / {row['unit']} (n={row['both_graded_pairs']})" for row in units])
    ax.set_xlim(0, 105)
    ax.invert_yaxis()
    ax.set_xlabel("두 조건 공통 판독 문항의 최종 정답 일치율 (%)")
    ax.set_title("단원별 결과 · 적은 문항 수의 차이는 신중하게 해석")
    ax.legend(frameon=False)
    fig.tight_layout()
    figures.append(("accuracy_by_unit", fig))

    review = result.get("solution_review")
    if review and review.get("summary"):
        summary = review["summary"]
        fig, axes = plt.subplots(2, 2, figsize=(11, 7), sharex=True)
        colors = ["white", ".35", ".7", ".95"]
        hatches = ["", "///", "xx", ".."]
        rating_names = ["적절", "부적절", "불확실", "미검토"]
        keys = ["appropriate", "inappropriate", "uncertain", "unreviewed"]
        maximum = max(1, result["expected_questions"])
        for row_index, (kind, label) in enumerate((("ai_suggestion", "AI 보조 제안"), ("human", "사람 검토"))):
            for col_index, criterion in enumerate(("mathematical_appropriateness", "curriculum_scope")):
                ax = axes[row_index, col_index]
                for method_index, method in enumerate(METHODS):
                    row = summary.get("review_kinds", {}).get(kind, {}).get(method)
                    if not row:
                        ax.text(0, method_index, "아직 검토 대상 응답 없음", va="center", fontsize=8)
                        continue
                    counts = row["mathematical_appropriateness"] if criterion == "mathematical_appropriateness" else row["criteria"][criterion]
                    left = 0
                    for key, color, hatch in zip(keys, colors, hatches):
                        value = (row["total_eligible_solutions"] - counts["reviewed_count"]
                                 if key == "unreviewed" else counts[key])
                        ax.barh(method_index, value, left=left, height=.6, color=color, edgecolor="black", hatch=hatch)
                        if value >= 3:
                            ax.text(left + value / 2, method_index, str(value), ha="center", va="center",
                                    color="white" if key == "inappropriate" else "black", fontsize=9)
                        left += value
                ax.set_yticks([0, 1], [METHOD_NAMES[method] for method in METHODS])
                ax.set_xlim(0, maximum)
                ax.invert_yaxis()
                ax.set_title(label + " · " + ("수학적 풀이 적절성" if criterion == "mathematical_appropriateness" else "교과 범위 (별도)"))
                ax.set_xlabel("검토 대상 풀이 수")
        from matplotlib.patches import Patch
        fig.legend([Patch(facecolor=color, edgecolor="black", hatch=hatch) for color, hatch in zip(colors, hatches)],
                   rating_names, loc="lower center", ncol=4, frameon=False)
        fig.suptitle("풀이 검토 상태 · AI 검토는 방식 정보가 보이는 상태의 보조 제안", fontsize=13)
        fig.tight_layout(rect=(0, .06, 1, .95))
        figures.append(("solution_appropriateness", fig))

    paths = []
    with PdfPages(output / "실험_결과_요약.pdf") as pdf:
        fig = plt.figure(figsize=(8.27, 11.69))
        fig.text(.08, .94, "MathHint 모델 학습·풀이 생성 비교", fontsize=19, weight="bold")
        summary_lines = [
            f"학습{result['training']['train_count']}문항 / 테스트{result['expected_questions']}문항 / 방식별1회 생성",
            f"{result['model']} · 추론 {result['thinking_level']} · temperature {result['temperature']}", "",
            f"실험: {result['generation_name']}",
            f"기본 응답 재사용 {result['control_reuse']['count']}개 / 이번 실행 새 요청 대상 {result['control_reuse']['new_condition_requests_expected']}개",
            f"조건별 요청 기록 {result['latest_condition_records']}/{result['expected_questions'] * 2}개 (미완료 시 중간 집계)",
            f"원본 정답표 기준·공통 판독{p['both_graded_pairs']}개: 기본 {_pct(a)} / 회귀 {_pct(b)}",
            f"기본만 정답 {p['baseline_only_correct']}개 / 회귀만 정답 {p['regression_only_correct']}개",
            f"Exact McNemar 양측 p={p['exact_mcnemar_two_sided_p']:.4g}", "",
            "성공 응답당 평균 토큰 (입력 / 출력 / 전체):",
            "기본: " + " / ".join(_num(result['methods']['baseline']['usage'][field]['successful_response_mean'])
                                     for field in ('prompt_token_count', 'candidates_token_count', 'total_token_count')),
            "회귀: " + " / ".join(_num(result['methods']['regression_hint']['usage'][field]['successful_response_mean'])
                                     for field in ('prompt_token_count', 'candidates_token_count', 'total_token_count')), "",
            f"회귀 모델: 문제{result['training']['problem_dimensions']}차원 → 해설{result['training']['solution_dimensions']}차원 · "
            f"{result['training']['regression']['optimizer']} · {result['training']['regression']['epochs']}epochs",
            f"테스트 MSE: 원시 예측 {result['training']['regression']['metrics']['test']['raw']['mse']:.4f}",
            f"음수 제거 예측 {result['training']['regression']['metrics']['test']['clipped_nonnegative']['mse']:.4f} / "
            f"학습 평균 벡터 {result['training']['regression']['metrics']['test']['training_mean_baseline']['mse']:.4f}", "",
            "군집화: 학습 데이터만 사용, k=" + " / ".join(str(row['k']) for row in result['training']['clustering']),
            type_count_note(result['training']) + " Purity 외 ARI·NMI와 테스트 라벨 정확도를 함께 확인.", "",
            "API 입력에는 문제와 예측 벡터만 사용. 실제 정답·해설·유형은 평가용.",
            hint_description(result["hint"]) + ".", "",
            "정답률은 최종 답의 일치율이며 풀이 논리·교과 적합성은 자동 검증하지 않음.",
            f"{result['expected_questions']}문항에 대한1회 실험이다. 반복 실행이나 다른 데이터의 결과를 보장하지 않음.",
            "미제공 사용량은0으로 대체하지 않으며, 실패·미판독은 별도로 기록.", "",
            f"상세 기록: {result['generation_name']}/report.html, comparison.csv 및 questions/{{ID}}/",
            f"통계 원본: {output.name}/integrated_summary.json",
            "문서: 실험_결과_요약.md",
        ]
        adjudicated = result.get("adjudicated_answer_scores")
        if adjudicated:
            review_pair = adjudicated["paired"]
            summary_lines[9:9] = [
                f"원본 정답표 충돌 {adjudicated['conflict_count']}개: AI 보조 수학 검토 기준은 별도 평가",
                f"수학 검토 기준: 기본 {_pct(review_pair['baseline_accuracy'])} / 회귀 {_pct(review_pair['regression_hint_accuracy'])}",
                "원본 정답표·API 응답은 그대로 보존. 수학 검토 점수는 사람이 인증한 정답표가 아님.", "",
            ]
        fig.text(.08, .88, "\n".join(summary_lines), fontsize=10.3, va="top", linespacing=1.65)
        pdf.savefig(fig)
        plt.close(fig)
        for name, fig in figures:
            path = output / f"{name}.png"
            fig.savefig(path, bbox_inches="tight")
            fig.savefig(path.with_suffix(".pdf"), bbox_inches="tight")
            pdf.savefig(fig, bbox_inches="tight")
            paths.append(path)
            plt.close(fig)
        for filename in ("regression_learning_curve.png", "regression_test_metrics.png", "pca_unit_vs_clusters.png", "type_cluster_heatmap.png", "clustering_heldout_scores.png"):
            path = run_root / "training" / filename
            if path.exists():
                fig, ax = plt.subplots(figsize=(11.7, 8.3))
                ax.imshow(plt.imread(path))
                ax.axis("off")
                fig.tight_layout()
                pdf.savefig(fig, bbox_inches="tight")
                plt.close(fig)
    return paths


def main() -> None:
    # 1. 같은 실험의 학습 결과와 응답을 읽어 집계한다.
    run_root = RUN_ROOT.resolve()
    review_path = SOLUTION_REVIEW.resolve() if SOLUTION_REVIEW else None
    result = analyze(run_root, GENERATION_NAME, review_path)

    # 2. 통계 원본·설명·문항별 결과 변화표를 저장한다.
    output = OUTPUT.resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / "integrated_summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (output / "실험_결과_요약.md").write_text(markdown_report(result, run_root, output), encoding="utf-8")
    with (output / "paired_outcomes.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["id", "baseline_correct", "regression_hint_correct", "outcome"])
        writer.writeheader()
        writer.writerows(result["paired"]["outcomes"])
    # 3. 비교 그림과 PDF를 만든다.
    render_figures(result, run_root, output)
    print(json.dumps({"output": str(output), "expected_questions": result["expected_questions"],
                      "graded_pairs": result["paired"]["both_graded_pairs"],
                      "baseline_accuracy": result["paired"]["baseline_accuracy"],
                      "regression_hint_accuracy": result["paired"]["regression_hint_accuracy"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
