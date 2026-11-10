"""저장된 네 조건 입력·응답·사용량을 검증한다. 학습·실제 API 호출은 없다."""

from pathlib import Path

from ... import CompareGeneration as comparison
from ...AnswerEvaluation import evaluate_answer
from .common import ROOT, OUTPUT, METHODS, load_saved, read_json, read_jsonl, write_json
from .plan import prepare_plan
from .run import load_data


def run(root=ROOT, output=OUTPUT, *, save=True):
    root, output = Path(root).resolve(), Path(output).resolve()
    config, plan, records, state = load_saved(output)
    before = {str(path.relative_to(output)): comparison.file_hash(path)
              for path in output.rglob("*") if path.is_file() and path.name != "validation.json"}
    checks = []
    def check(name, condition):
        checks.append({"check": name, "passed": bool(condition)})
    data = load_data(root)
    expected_config, expected_plan = prepare_plan(root, data, split=config["split"])
    check("both_models_frozen_and_identical_data_vocabulary_prediction_files", config == expected_config)
    check("all_saved_prompts_equal_current_frozen_model_requests", plan == expected_plan)
    for item in plan:
        saved = read_json(output / "prompt_audit/requests" / item["id"] / (item["condition"] + ".json"))
        expected = comparison.request_snapshot(comparison.sdk_request_arguments(config, item["input_text"]))
        check(f"saved_request_{item['id']}_{item['condition']}", saved["sdk_request"] == expected
              and saved["request_sha256"] == comparison.digest(expected) == item["request_sha256"]
              and saved["user_message"] == item["input_text"]
              and saved["system_instruction"] == config["system_instruction"])
    identifiers = config["test_ids"]
    check("four_conditions_for_every_original_target_id", len(plan) == len(identifiers) * 4
          and {(row["id"], row["condition"]) for row in plan} == {(i, c) for i in identifiers for c in "ABCD"})
    lookup = {(row["id"], row["method"]): row for row in plan}
    check("identical_problem_and_common_system_across_all_conditions", all(
        len({r["problem_text"] for r in plan if r["id"] == i}) == 1
        and len({r["system_instruction"] for r in plan if r["id"] == i}) == 1 for i in identifiers))
    captures = read_jsonl(output / "prompt_audit/sdk_calls.jsonl")
    by_request = {}
    for capture in captures:
        by_request.setdefault(capture["request_sha256"], []).append(capture)
        check(f"sdk_capture_{len(checks)}", comparison.digest(capture["sdk_request"]) == capture["request_sha256"]
              and capture["matches_saved_prompt"] is True)
    for row in records:
        key = row["id"], row["method"]
        expected = lookup.get(key)
        check(f"response_identity_{row['id']}_{row['condition']}", expected is not None
              and row["condition"] == expected["condition"] and row["split"] == config["split"]
              and row["request_sha256"] == expected["request_sha256"]
              and row["input_text"] == expected["input_text"] and row["hint"] == expected["hint"])
        usage = row.get("usage", {})
        check(f"usage_values_{row['id']}_{row['condition']}", all(usage.get(field) is None or
              (type(usage[field]) is int and usage[field] >= 0) for field in comparison.USAGE_FIELDS))
        raw = usage.get("raw")
        if isinstance(raw, dict):
            check(f"usage_matches_api_fields_{row['id']}_{row['condition']}", all(
                usage.get(field) == raw.get(field) for field in comparison.USAGE_FIELDS))
        if row["status"] == "success":
            evaluation = evaluate_answer(row["output_text"], expected["reference"], expected["problem_text"])
            check(f"independent_final_answer_grade_{row['id']}_{row['condition']}", row["evaluation"] == evaluation)
            if row["response_origin"] == "new_api_call":
                check(f"successful_response_has_exact_live_sdk_capture_{row['id']}_{row['condition']}",
                      any(cap["id"] == row["id"] and cap["condition"] == row["condition"]
                          for cap in by_request.get(row["request_sha256"], [])))
            elif row["response_origin"] == "reused_exact_request":
                provenance = row["source_provenance"]
                check(f"reused_response_source_preserved_{row['id']}_{row['condition']}",
                    comparison.file_hash(root / provenance["records"]) == provenance["records_sha256"]
                    and comparison.file_hash(root / provenance["request_audit"]) == provenance["request_audit_sha256"]
                    and read_json(root / provenance["request_audit"])["sdk_request_sha256"] == row["request_sha256"]
                    and provenance["request_match"] == "exact SDK arguments including all generation settings and hint")
    lines = read_jsonl(output / "responses.jsonl")
    successes = [row for row in lines if row["status"] == "success"]
    check("successful_exact_requests_never_saved_twice", len(successes) == len({row["request_sha256"] for row in successes}))
    latest_successes = [row for row in records if row["status"] == "success"]
    expected_pending = {(row["id"], row["condition"]) for row in plan
                        if not any(r["id"] == row["id"] and r["condition"] == row["condition"]
                                   and r["status"] == "success" for r in records)}
    check("state_counts_and_pending_exactly_match_saved_responses", state.get("successful_requests") == len(latest_successes)
          and state.get("pending_count") == len(expected_pending)
          and {(r["id"], r["condition"]) for r in state.get("pending_requests", [])} == expected_pending)
    check("completed_status_only_when_all_requests_succeeded", (state.get("status") == "completed") == (not expected_pending))
    browser_path = output / "review/browser_validation.json"
    browser = read_json(browser_path) if browser_path.exists() else {"performed": False,
        "note": "실제 브라우저 검사는 별도 수행하며, 파일 존재 검증으로 대신하지 않는다."}
    if browser.get("performed"):
        check("actual_browser_record_matches_current_html_and_assets", browser.get("passed") is True
              and browser.get("report_sha256") == comparison.file_hash(output / "report.html")
              and bool(browser.get("assets_sha256"))
              and all((root / name).is_file() and comparison.file_hash(root / name) == digest
                      for name, digest in browser["assets_sha256"].items()))
    after = {str(path.relative_to(output)): comparison.file_hash(path)
             for path in output.rglob("*") if path.is_file() and path.name != "validation.json"}
    check("verification_leaves_inputs_models_and_response_logs_unchanged", before == after)
    result = {"verified_at": comparison.utc_now(), "config_id": comparison.digest(config),
        "dataset_id": config["dataset_id"], "split": config["split"], "checks": checks,
        "passed": sum(r["passed"] for r in checks), "failed": sum(not r["passed"] for r in checks),
        "complete": all(r["passed"] for r in checks), "experiment_complete": not expected_pending,
        "successful_requests": len(latest_successes), "expected_requests": len(plan),
        "pending_requests": len(expected_pending), "live_api_calls_during_verification": 0,
        "model_training_during_verification": False,
        "actual_browser_validation": browser,
        "limits": ["검증 통과와 실험 완료는 구분한다. 미완료 요청은 그대로 표시한다.",
                   "최종 답의 자동 판정은 수학적 풀이 타당성의 확정 판정이 아니다."]}
    if save:
        write_json(output / "validation.json", result)
    return result
