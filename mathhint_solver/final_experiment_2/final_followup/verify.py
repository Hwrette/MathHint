"""저장된 3회 반복 실험을 독립 대조한다. 학습·모델 예측·API 호출은 없다."""

from collections import Counter, defaultdict
import csv
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
from urllib.parse import unquote, urlsplit

from ... import CompareGeneration as comparison
from ...AnswerEvaluation import evaluate_answer
from ..gemini_full265.verify import saved_request_rate_checks
from .common import API_RECEIVED_STATUSES, is_received


CONTROL_IDS = ("trig_1_040", "trig_1_044", "diff_2_039", "diff_2_004", "trig_1_043")
ERROR_IDS = ("diff_2_039", "diff_3_045", "trig_1_040", "trig_1_044", "trig_1_047",
             "trig_2_020", "trig_3_008", "trig_3_033", "trig_3_036", "trig_2_022", "trig_3_034")
OLD_HEADER = "[정답 해설에서 계산한 실제 해설 주요 토큰: 실제 빈도순 상위20개]"
NEUTRAL_HEADER = "[해설에 등장한 토큰과 빈도: 상위20개]"
USAGE_FIELDS = ("prompt_token_count", "candidates_token_count", "thoughts_token_count",
                "cached_content_token_count", "total_token_count")


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _jsonl(path):
    path = Path(path)
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.is_file() else []


def _csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _key(row):
    return row["id"], row["condition"], row["repeat"]


def _same(actual, expected):
    if actual in (None, "") and expected in (None, ""):
        return True
    if actual == expected:
        return True
    if actual in (None, "") or expected in (None, ""):
        return False
    if type(expected) is bool:
        return str(expected) == actual
    try:
        return math.isclose(float(actual), float(expected), rel_tol=1e-11, abs_tol=1e-11)
    except (ValueError, TypeError):
        return False


def token_statistics(values):
    """제공값만 집계하며 표준편차는 표본 표준편차(ddof=1)다."""
    values = [value for value in values if value is not None]
    if not values:
        return {"provided_count": 0, "sum": None, "mean": None, "min": None,
                "max": None, "std": None}
    return {"provided_count": len(values), "sum": sum(values), "mean": statistics.mean(values),
            "min": min(values), "max": max(values), "std": statistics.stdev(values) if len(values) >= 2 else None}


def plan_checks(config, plan):
    """실행 코드의 계획 생성 함수를 재호출하지 않고 사용자 설계에서 기대키를 만든다."""
    checks = []
    def check(name, value):
        checks.append({"check": name, "passed": bool(value)})
    controls, errors = set(CONTROL_IDS), set(ERROR_IDS)
    targets = controls | errors
    expected = {(identifier, condition, repeat) for identifier in targets
                for condition in ("ABCDEF" if identifier in controls else "ABCD") for repeat in range(1, 4)}
    keys = [_key(row) for row in plan]
    check("186_unique_id_condition_repeat_keys", len(plan) == len(set(keys)) == len(expected) == 186 and set(keys) == expected)
    check("configured_control5_error11_target13", set(config.get("control_ids", [])) == controls
          and set(config.get("error_ids", [])) == errors and set(config.get("target_ids", [])) == targets)
    check("control90_error132_share36", sum(identifier in controls for identifier, _, _ in keys) == 90
          and sum(identifier in errors and condition in "ABCD" for identifier, condition, _ in keys) == 132
          and len(controls & errors) == 3
          and sum(identifier in controls & errors and condition in "ABCD" for identifier, condition, _ in keys) == 36)
    check("all_conditions_have_exactly3_repeats", all(count == 3 for count in Counter((r["id"], r["condition"]) for r in plan).values()))
    check("repeat_numbers_are_integers1to3", all(type(row["repeat"]) is int and row["repeat"] in (1, 2, 3) for row in plan))
    check("request_id_unique_per_repeat", len({row.get("request_id") for row in plan}) == 186
          and all(row.get("request_id") for row in plan))
    groups = defaultdict(list)
    for row in plan:
        groups[row["id"], row["condition"]].append(row)
    check("same_prompt_is_retained_for_three_independent_repeats", all(
        len({row.get("request_sha256") for row in rows}) == 1 for rows in groups.values()))
    # 조건을 한꺼번에 몰지 않는지 검사한다. 구체적인 라틴 회전의 유일한 형태를 강요하지 않는다.
    run_lengths = []
    previous, length = None, 0
    for row in plan:
        if row["condition"] == previous:
            length += 1
        else:
            if length:
                run_lengths.append(length)
            previous, length = row["condition"], 1
    run_lengths.append(length)
    check("conditions_are_interleaved_not_blocked_by_arm", max(run_lengths, default=0) <= 2)
    return checks


def expected_message(condition, source_audit, audit_a=None, audit_d=None):
    """사용자 대조군 정의에서 프롬프트를 독립 재구성한다."""
    if condition in "ABCD":
        return source_audit["sdk_request"]["contents"]
    if condition == "E":
        return audit_a["sdk_request"]["contents"] + "\n\n풀이를 작성해줘."
    if condition == "F":
        message = audit_d["sdk_request"]["contents"]
        if message.count(OLD_HEADER) != 1:
            raise ValueError("원본 D 출처 제목의 유일한 위치를 확인할 수 없습니다.")
        return message.replace(OLD_HEADER, NEUTRAL_HEADER, 1)
    raise ValueError("알 수 없는 조건: " + condition)


def preservation_result(root, manifest):
    files = manifest.get("files_sha256", {})
    changed = [name for name, digest in files.items()
               if not (Path(root) / name).is_file() or _hash(Path(root) / name) != digest]
    return {"passed": bool(files) and not changed, "protected_files": len(files),
            "changed_files": changed, "source_commit": manifest.get("source_commit")}


def transport_consistency_checks(executions, captures, response_history):
    """각 실행의 실제 전송 제한을 그 실행의 기록끼리 대조한다.

    전송 대기 한도는 생성 SDK 본문과 별개다. 180초·300초 등 하나의 값을
    과거/미래 시행 전체에 소급 강제하지 않고 실행 당시 정책을 보존한다.
    """
    checks = []
    def check(name, value):
        checks.append({"check": name, "passed": bool(value)})
    runs = {row["execution_id"]: row for row in executions}
    check("transport_execution_ids_are_unique", len(runs) == len(executions))
    capture_counts = Counter((row.get("execution_id"), _key(row)) for row in captures)
    fields = ("http_timeout_ms", "sdk_attempts")
    for execution_id, row in runs.items():
        transport = row.get("transport") or {}
        timeout = transport.get("http_timeout_ms")
        check("transport_policy_matches_execution_" + execution_id,
              type(timeout) is int and timeout > 0 and transport.get("sdk_attempts") == 1
              and row.get("policy", {}).get("http_timeout_ms") == timeout)
    for index, capture in enumerate(captures):
        run = runs.get(capture.get("execution_id"))
        check("capture_transport_matches_its_execution_" + str(index), run is not None
              and all(capture.get("transport", {}).get(field) == run.get("transport", {}).get(field) for field in fields))
    for index, row in enumerate(response_history):
        run = runs.get(row.get("execution_id"))
        check("response_transport_matches_its_execution_" + str(index), run is not None
              and all(row.get("transport", {}).get(field) == run.get("transport", {}).get(field) for field in fields))
        if row.get("sdk_boundary_capture_expected", True):
            check("response_attempt_capture_count_" + str(index),
                  row.get("sdk_boundary_captured_attempts") == capture_counts[row.get("execution_id"), _key(row)])
    return checks


def _link_checks(output):
    count, broken = 0, []
    for path in Path(output).rglob("*.md"):
        text = re.sub(r"^```[^\n]*\n.*?^```\s*$", "", path.read_text(encoding="utf-8"), flags=re.M | re.S)
        for target in re.findall(r"\[[^\]\n]*\]\((<[^>]+>|[^)\n]+)\)", text):
            url = urlsplit(target.strip("<>"))
            if url.scheme or not url.path:
                continue
            count += 1
            destination = path.parent / unquote(url.path)
            if destination.resolve() != (Path(output) / "validation.json").resolve() and not destination.exists():
                broken.append({"source": str(path.relative_to(output)), "target": target})
    return count, broken


def _review_lookup(output):
    path = Path(output) / "review/curated_reviews.json"
    if not path.is_file():
        return {}, []
    payload = _read(path)
    records = payload.get("records", []) if isinstance(payload, dict) else payload
    return {_key(row): row for row in records}, records


def case_findings_checks(findings, records, *, require_complete=False):
    """11개 A/D·B/C 종합 분석을 새 12응답에 독립 연결한다.

    부분 실행에서는 이미 완성된 문항의 올바른 부분집합을 허용한다. 전체 API
    시행이 끝나면 11문항의 실제 3회 분석이 모두 있어야 최종 검증을 통과한다.
    보고서 생성기의 검사 함수나 과거 응답 해시는 사용하지 않는다.
    """
    checks = []
    def check(name, value):
        checks.append({"check": name, "passed": bool(value)})
    check("case_findings_are_a_dictionary", isinstance(findings, dict))
    if not isinstance(findings, dict):
        return checks
    check("case_findings_only_select_requested_error11", set(findings) <= set(ERROR_IDS))
    if require_complete:
        check("all186_receipts_require_all11_case_findings", set(findings) == set(ERROR_IDS))
    received = {_key(row): row for row in records if is_received(row)}
    for identifier, finding in findings.items():
        name = str(identifier)
        check("case_finding_object_" + name, isinstance(finding, dict))
        if not isinstance(finding, dict):
            continue
        keys = [(identifier, condition, repeat) for condition in "ABCD" for repeat in (1, 2, 3)]
        expected = {f"{identifier}__{condition}__r{repeat}": hashlib.sha256(
            received[identifier, condition, repeat].get("output_text", "").encode()).hexdigest()
                    for _, condition, repeat in keys if (identifier, condition, repeat) in received}
        check("case_finding_12_new_response_hashes_" + name,
              len(expected) == 12 and isinstance(finding.get("response_sha256s"), dict)
              and finding["response_sha256s"] == expected)
        check("case_finding_AD_BC_nonempty_" + name,
              all(isinstance(finding.get(field), str) and finding[field].strip() for field in ("AD", "BC")))
        check("case_finding_AI_not_human_confirmed_" + name, finding.get("human_confirmed") is False)
    return checks


def _scored_grade(row, review):
    """원본 파서 결과와 새 응답을 직접 검토한 판정을 분리한다."""
    if row.get("status", "success") != "success":
        return None
    grade = row.get("evaluation", {}).get("correct")
    decision = review.get("final_answer_correct")
    if type(decision) is bool:
        return decision
    adjudication = review.get("final_answer_adjudication") or {}
    if type(adjudication.get("correct")) is bool:
        return adjudication["correct"]
    return grade


def _summary_checks(output, plan, records, reviews):
    checks = []
    def check(name, value):
        checks.append({"check": name, "passed": bool(value)})
    latest = {_key(row): row for row in records}
    for folder, targets, conditions in (("control_top5", CONTROL_IDS, "ABCDEF"), ("error_repeat_11", ERROR_IDS, "ABCD")):
        path = Path(output) / folder / "summary.csv"
        if not path.is_file():
            check(folder + "_summary_exists", False)
            continue
        rows = _csv(path)
        index = {(row["id"], row["condition"]): row for row in rows}
        check(folder + "_unique_summary_rows", len(rows) == len(index) == len(targets) * len(conditions))
        for identifier in targets:
            for condition in conditions:
                actual = index.get((identifier, condition), {})
                selected = [latest.get((identifier, condition, repeat), {"status": "not_run"}) for repeat in range(1, 4)]
                successes = [r for r in selected if r.get("status") == "success"]
                received = [r for r in selected if is_received(r)]
                grades = [_scored_grade(r, reviews.get((identifier, condition, r["repeat"]), {})) for r in received]
                graded = [g for g in grades if type(g) is bool]
                received_reviews = [reviews.get((identifier, condition, r["repeat"]), {}) for r in received]
                math_statuses = [review.get("math_status", "uncertain") for review in received_reviews]
                expected = {"expected_count": 3, "success_count": len(successes), "graded_count": len(graded),
                            "received_count": len(received), "completed_count": len(received), "api_response_count": len(received),
                            "incomplete_count": len(received) - len(successes),
                            "truncated_count": sum(r.get("status") == "truncated_response" for r in received),
                            "blocked_count": sum(r.get("status") == "blocked_or_incomplete_response" for r in received),
                            "empty_count": sum(r.get("status") == "empty_response" for r in received),
                            "correct_count": sum(g is True for g in graded), "incorrect_count": sum(g is False for g in graded),
                            "ungradable_count": len(received) - len(graded),
                            "pending_count": sum(r.get("status") == "not_run" for r in selected),
                            "failed_count": sum(r.get("status") != "not_run" and not is_received(r) for r in selected),
                            "math_appropriate_count": math_statuses.count("appropriate"),
                            "math_inappropriate_count": math_statuses.count("inappropriate"),
                            "math_uncertain_count": math_statuses.count("uncertain"),
                            "reviewed_math_count": sum(status in ("appropriate", "inappropriate") for status in math_statuses),
                            "correct_but_math_inappropriate_count": sum(grade is True and status == "inappropriate"
                                                                         for grade, status in zip(grades, math_statuses)),
                            "prior_error_recurred_count": sum(review.get("prior_error_recurred") is True for review in received_reviews),
                            "prior_error_assessed_count": sum(type(review.get("prior_error_recurred")) is bool for review in received_reviews),
                            "self_corrected_count": sum(review.get("self_corrected") is True for review in received_reviews),
                            "self_correction_assessed_count": sum(type(review.get("self_corrected")) is bool for review in received_reviews)}
                for field, value in expected.items():
                    check(f"{folder}_{identifier}_{condition}_{field}", field in actual and _same(actual[field], value))
                for field in USAGE_FIELDS:
                    stats = token_statistics([r.get("usage", {}).get(field) for r in received])
                    for statistic, value in stats.items():
                        name = field + "_" + statistic
                        check(f"{folder}_{identifier}_{condition}_{name}", name in actual and _same(actual[name], value))
    paired_path = Path(output) / "control_top5/paired_differences.csv"
    if paired_path.is_file():
        rows = _csv(paired_path)
        check("75_control_paired_repeat_rows", len(rows) == 75)
        # 구체적인 CSV 열 이름은 보고서와 공유하지 않고 저장된 조건 표기로 판별한다.
        contrasts = {"E-A": ("E", "A"), "B-A": ("B", "A"), "C-A": ("C", "A"),
                     "D-A": ("D", "A"), "F-D": ("F", "D")}
        for index, row in enumerate(rows):
            pair = row.get("pair", row.get("contrast"))
            check(f"paired_{index}_known_contrast", pair in contrasts and row.get("id") in CONTROL_IDS)
            if pair not in contrasts:
                continue
            repeat = int(row["repeat"])
            first, second = (latest.get((row["id"], c, repeat), {}) for c in contrasts[pair])
            for field in USAGE_FIELDS:
                a, b = first.get("usage", {}).get(field), second.get("usage", {}).get(field)
                expected = a - b if is_received(first) and is_received(second) and a is not None and b is not None else None
                name = field + "_difference"
                if name in row:
                    check(f"paired_{index}_{field}", _same(row[name], expected))
    else:
        check("control_paired_differences_exist", False)
    return checks


def run(root=None, output=None, *, save=True):
    """현재 저장 상태만 검증한다. 미완료 API를 자동 실행하지 않는다."""
    from .common import ROOT, OUTPUT, all_request_events, load_saved, safe_output, write_json
    from PIL import Image
    root = Path(root or ROOT).resolve()
    output = safe_output(root, output or root / OUTPUT.relative_to(ROOT))
    before = {str(p.relative_to(output)): _hash(p) for p in output.rglob("*")
              if p.is_file() and p.name not in ("validation.json", ".execution.lock")}
    config, plan, records, state = load_saved(output)
    checks = plan_checks(config, plan)
    def check(name, value):
        checks.append({"check": name, "passed": bool(value)})
    source = root / "results/final_experiment_2/gemini_full265"
    corrected = _csv(source / "key_corrected/question_comparison.csv")
    old_error_ids = {r["id"] for r in corrected if any(r[c + "_correct_verified"] == "False" for c in "ABCD")}
    check("selected_error11_matches_all_old_verified_failures", old_error_ids == set(ERROR_IDS))
    old_config = _read(source / "config.json")["config"]
    for field in ("model", "temperature", "thinking_level", "max_output_tokens", "system_instruction"):
        check("frozen_generation_setting_" + field, config.get(field) == old_config.get(field))
    check("requested_model_exact", config.get("model") == "gemini-3.1-flash-lite")
    check("frozen_models_vocab_and_data_identity", all(config.get(field) == old_config.get(field)
          for field in ("models", "dataset_id", "solution_vocabulary_sha256", "data_identity_sha256")))
    check("all_source_hash_bindings_match", bool(config.get("sources_sha256")) and all(
        (root / path).is_file() and _hash(root / path) == sha for path, sha in config.get("sources_sha256", {}).items()))
    check("config_inputs_match_frozen_repeat_plan", config.get("inputs") == [
        {name: row[name] for name in ("id", "condition", "repeat", "request_id", "request_sha256", "schedule_position")}
        for row in plan])
    corrected_lookup = {row["id"]: row for row in corrected}
    old_plan = {(row["id"], row["condition"]): row for row in _jsonl(source / "plan.jsonl")}
    lookup = {_key(row): row for row in plan}
    for row in plan:
        identifier, condition, repeat = _key(row)
        def original(c):
            return _read(source / f"prompt_audit/requests/{identifier}/{c}.json")
        source_audit = original(condition if condition in "ABCD" else "A" if condition == "E" else "D")
        message = expected_message(condition, source_audit, original("A"), original("D"))
        sdk = {**source_audit["sdk_request"], "contents": message}
        frozen_path = output / f"frozen_prompts/{identifier}/{condition}.json"
        frozen = _read(frozen_path) if frozen_path.is_file() else {}
        check(f"prompt_{identifier}_{condition}_r{repeat}", row.get("input_text") == message
              and comparison.digest(sdk) == row.get("request_sha256")
              and frozen.get("sdk_request") == sdk and frozen.get("request_sha256") == row.get("request_sha256"))
        check(f"problem_unchanged_{identifier}_{condition}_r{repeat}", row.get("problem_text") == source_audit["problem_text"]
              and row.get("system_instruction") == source_audit["system_instruction"])
        source_condition = condition if condition in "ABCD" else "A" if condition == "E" else "D"
        source_item = old_plan[identifier, source_condition]
        source_audit_path = source / f"prompt_audit/requests/{identifier}/{source_condition}.json"
        check(f"frozen_source_provenance_{identifier}_{condition}_r{repeat}",
              frozen.get("source_prompt_audit") == str(source_audit_path.relative_to(root))
              and frozen.get("source_prompt_audit_sha256") == _hash(source_audit_path)
              and frozen.get("source_request_sha256") == source_audit["request_sha256"]
              and frozen.get("full_request_text") == "[SYSTEM]\n" + row["system_instruction"] + "\n[USER]\n" + message)
        check(f"source_split_labels_reference_{identifier}_{condition}_r{repeat}",
              all(row.get(field) == source_item.get(field) for field in
                  ("split", "subject", "curriculum", "unit", "subunit", "type", "reference_solution"))
              and row.get("reference_answer_text") == corrected_lookup[identifier]["answer_for_scoring"])
        check(f"hint_unchanged_{identifier}_{condition}_r{repeat}",
              row.get("hint") == source_audit.get("hint") if condition != "E" else not (row.get("hint") or {}).get("mapping"))
    history = _jsonl(output / "responses.jsonl")
    successes = [r for r in history if r.get("status") == "success"]
    received = [r for r in history if is_received(r)]
    check("received_repeat_keys_are_saved_once", len(received) == len({_key(row) for row in received}))
    captures = _jsonl(output / "prompt_audit/sdk_calls.jsonl")
    capture_keys = set()
    for index, capture in enumerate(captures):
        key = _key(capture)
        item = lookup.get(key)
        check("sdk_capture_" + str(index), item is not None
              and comparison.digest(capture.get("sdk_request")) == item.get("request_sha256")
              and capture.get("request_sha256") == item.get("request_sha256")
              and capture.get("matches_frozen_prompt") is True)
        capture_keys.add(key)
    executions = [_read(path) for path in sorted((output / "execution_runs").glob("*.json"))]
    executions = [row for row in executions if isinstance(row, dict) and row.get("execution_id")]
    transport_checks = transport_consistency_checks(executions, captures, history)
    checks.extend(transport_checks)
    reviews, review_records = _review_lookup(output)
    check("unique_new_review_keys", len(reviews) == len(review_records))
    check("reviews_only_reference_new_API_received_repeats", set(reviews) <= {_key(row) for row in received})
    review_path = output / "review/curated_reviews.json"
    review_payload = _read(review_path) if review_path.is_file() else {}
    findings = review_payload.get("case_findings", {}) if isinstance(review_payload, dict) else {}
    findings_checks = case_findings_checks(findings, records, require_complete=len(received) == 186)
    checks.extend(findings_checks)
    for row in records:
        key = _key(row)
        name = "_".join(map(str, key))
        item = lookup.get(key)
        check("response_identity_" + name, item is not None and all(row.get(f) == item.get(f)
              for f in ("id", "condition", "repeat", "request_id", "split", "input_text", "request_sha256", "problem_text", "hint")))
        usage = row.get("usage") or {}
        check("usage_types_" + name, all(usage.get(f) is None or type(usage[f]) is int and usage[f] >= 0 for f in comparison.USAGE_FIELDS))
        if isinstance(usage.get("raw"), dict):
            check("usage_matches_API_" + name, all(usage.get(f) == usage["raw"].get(f) for f in comparison.USAGE_FIELDS))
        if not is_received(row):
            continue
        check("new_actual_call_" + name, key in capture_keys and row.get("response_origin", row.get("source_origin")) == "new_api_call")
        automatic_grade = (evaluate_answer(row.get("output_text", ""), item["reference"], item["problem_text"])
                           if row.get("status") == "success" else
                           {"predicted_answer": None, "correct": None, "status": "ungradable",
                            "reason": row["status"], "extraction_method": None})
        check("saved_automatic_grade_" + name, row.get("evaluation") == automatic_grade)
        review = reviews.get(key)
        if review:
            text = row.get("output_text", "")
            quotes = review.get("evidence_quotes") or []
            check("review_hash_quotes_" + name, review.get("response_sha256") == hashlib.sha256(text.encode()).hexdigest()
                  and isinstance(quotes, list)
                  and (bool(quotes) if text else not quotes and review.get("math_status") == "uncertain")
                  and all(isinstance(quote, str) and quote and quote in text for quote in quotes))
            check("AI_review_not_human_confirmed_" + name, review.get("human_confirmed") is False)
            check("review_outcomes_have_explicit_types_" + name,
                  review.get("math_status") in ("appropriate", "inappropriate", "uncertain")
                  and all(review.get(field) is None or type(review.get(field)) is bool
                          for field in ("final_answer_correct", "prior_error_recurred", "self_corrected")))
            check("math_error_has_concrete_evidence_" + name, review.get("math_status") != "inappropriate"
                  or bool(review.get("reason") and review.get("error_step") and quotes))
            if type(review.get("final_answer_correct")) is bool and row.get("evaluation", {}).get("correct") is None:
                check("parser_abstention_review_has_reason_" + name, bool(review.get("reason") and quotes))
    latest = {_key(row): row for row in records}
    pending = set(lookup) - {key for key, row in latest.items() if is_received(row)}
    check("state_success_pending_counts", state.get("successful_requests") == len(successes)
          and state.get("pending_count") == len(pending) and state.get("completed_requests") == len(received)
          and state.get("api_response_count") == len(received)
          and state.get("incomplete_response_count") == len(received) - len(successes))
    check("state_failed_saved_response_counts", state.get("failed_requests") == sum(not is_received(row) for row in records)
          and state.get("saved_responses") == len(records)
          and state.get("response_log_entries") == len(history))
    check("state_pending_keys_are_exact", {_key(row) for row in state.get("pending_requests", [])} == pending)
    check("state_per_condition_pending_counts", state.get("pending_by_condition") == {
        condition: sum(key[1] == condition for key in pending) for condition in "ABCDEF"})
    check("state_per_repeat_counts", state.get("by_repeat") == {
        str(repeat): {"expected": 62, "success": sum(row["repeat"] == repeat for row in successes),
                      "completed": sum(row["repeat"] == repeat for row in received),
                      "incomplete": sum(row["repeat"] == repeat and row["status"] != "success" for row in received),
                      "failed": sum(row["repeat"] == repeat and not is_received(row) for row in records),
                      "pending": sum(key[2] == repeat for key in pending)} for repeat in (1, 2, 3)})
    check("historical_success_reuse_count_is_zero", state.get("historical_reused_successes") == 0
          and state.get("new_successes") == len(successes) and state.get("new_completed_requests") == len(received))
    check("resume_command_targets_only_this_study", state.get("resume_command", "").startswith(
        "python -m mathhint_solver.final_experiment_2.final_followup generate"))
    check("completed_requires186_API_receipts", (state.get("status") == "completed") == (len(received) == 186 and not pending))
    check("abnormal_received_trials_are_not_pending_rerolls", not ({_key(row) for row in received if row["status"] != "success"} & pending)
          and state.get("api_received_terminal_statuses") == list(API_RECEIVED_STATUSES))
    manifest = _read(output / "preservation_manifest.json")
    preservation = preservation_result(root, manifest)
    check("all_old_tracked_files_preserved", preservation["passed"])
    policy = _read(output / "policy.json")
    rate = saved_request_rate_checks(all_request_events(root, output), _jsonl(output / "execution_runs/request_events.jsonl"), policy)
    checks.extend(rate["checks"])
    if (output / "question_comparison.csv").is_file():
        checks.extend(_summary_checks(output, plan, records, reviews))
        comparison_rows = _csv(output / "question_comparison.csv")
        check("186_planned_comparison_rows", len(comparison_rows) == 186
              and {(_r["id"], _r["condition"], int(_r["repeat"])) for _r in comparison_rows} == set(lookup))
    links, broken_links = _link_checks(output)
    check("all_relative_Markdown_links_exist", not broken_links)
    image_errors, images = [], list(output.glob("figures/*.png"))
    for path in images:
        try:
            with Image.open(path) as image:
                width, height = image.size
                image.verify()
                if width < 600 or height < 300:
                    image_errors.append(path.name)
        except Exception:
            image_errors.append(path.name)
    if (output / "report.html").is_file():
        check("figures_decode_at_readable_resolution", bool(images) and not image_errors)
    browser_path = output / "review/browser_validation.json"
    browser = _read(browser_path) if browser_path.is_file() else {"performed": False}
    if browser.get("performed"):
        check("browser_evidence_matches_frozen_HTML_assets", browser.get("passed") is True
              and browser.get("report_sha256") == _hash(output / "report.html")
              and bool(browser.get("assets_sha256"))
              and all((root / path).is_file() and _hash(root / path) == sha for path, sha in browser["assets_sha256"].items()))
    after = {str(p.relative_to(output)): _hash(p) for p in output.rglob("*")
             if p.is_file() and p.name not in ("validation.json", ".execution.lock")}
    check("verify_does_not_mutate_inputs_responses_or_reports", before == after)
    result = {"verified_at": comparison.utc_now(), "passed": sum(c["passed"] for c in checks),
              "failed": sum(not c["passed"] for c in checks), "complete": all(c["passed"] for c in checks),
              "experiment_complete": len(received) == 186 and not pending,
              "review_complete": len(reviews) == len(received) and set(reviews) <= {key for key, row in latest.items() if is_received(row)},
              "case_findings_count": len(findings) if isinstance(findings, dict) else 0,
              "case_analysis_complete": len(received) == 186 and all(item["passed"] for item in findings_checks),
              "checks": checks, "expected_requests": 186, "successful_requests": len(successes), "pending_requests": len(pending),
              "completed_requests": len(received), "api_response_count": len(received),
              "incomplete_response_count": len(received) - len(successes),
              "preservation": preservation, "rate_audit": rate,
              "transport_audit": {"execution_count": len(executions), "captured_attempt_count": len(captures),
                  "response_history_count": len(history),
                  "recorded_http_timeouts_ms": sorted({row.get("transport", {}).get("http_timeout_ms") for row in executions
                                                        if type(row.get("transport", {}).get("http_timeout_ms")) is int}),
                  "passed": all(item["passed"] for item in transport_checks),
                  "scope": "Per-execution policy, actual SDK-boundary capture and response metadata agree; timeouts are not generation-body settings and old values are not rewritten."},
              "markdown_links_checked": links, "broken_links": broken_links,
              "decoded_png_count": len(images), "invalid_images": image_errors,
              "actual_browser_validation": browser, "model_training_performed": False,
              "generation_API_calls": 0, "additional_review_API_calls": 0}
    if save:
        write_json(output / "validation.json", result)
    return result
