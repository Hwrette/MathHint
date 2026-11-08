"""저장된 요청·SDK 경계 스냅샷·응답을 오프라인으로 대조한다. API는 호출하지 않는다."""

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from . import CompareGeneration as comparison

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "results/final_experiment/03_gemini"
CONDITIONS = {"baseline": "A", "regression_hint": "B", "oracle_hint": "C"}


def resolve_source_file(historical_path, project, config):
    """역사적 절대경로는 보존하고 같은 저장소 상대경로를 현재 clone에서 찾는다."""
    source = Path(historical_path)
    prediction_path = Path(config.get("predictions_source", ""))
    if "results" in prediction_path.parts:
        original_root = Path(*prediction_path.parts[:prediction_path.parts.index("results")])
        try:
            candidate = Path(project) / source.relative_to(original_root)
            if candidate.is_file():
                return candidate
        except ValueError:
            pass
    return source


def audit_generation(output=OUTPUT, *, project=ROOT, write_output=True):
    output, project = Path(output), Path(project)
    manifest = comparison.read_json(output / "config.json")
    config, config_id = manifest["config"], manifest["config_id"]
    violations, warnings = [], []
    if comparison.digest(config) != config_id:
        violations.append("config.json digest mismatch")
    expected = {(identifier, method) for identifier in config["test_ids"] for method in config["methods"]}
    all_rows = [json.loads(line) for line in (output / "responses.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    histories, latest = defaultdict(list), {}
    for row in all_rows:
        key = row["id"], row["method"]
        if key not in expected or row.get("config_id") != config_id:
            violations.append(f"response identity/config mismatch: {key}")
        histories[key].append(row)
        latest[key] = row
    for key, rows in histories.items():
        if sum(row["status"] == "success" for row in rows) > 1:
            violations.append(f"multiple successful responses for same request: {key}")
    snapshots = defaultdict(list)
    for path in sorted((output / "prompt_audit/sdk_calls").glob("*.json")):
        row = comparison.read_json(path)
        snapshots[row["id"], row["method"]].append((path, row))
    inputs = {row["id"]: row for row in config["inputs"]}
    index, version_counts, raw_usage_compared = [], Counter(), 0
    source_cache = {}
    for identifier, method in sorted(expected):
        condition = CONDITIONS[method]
        key = identifier, method
        request_path = output / "prompt_audit/requests" / identifier / (condition + ".json")
        if not request_path.exists():
            violations.append(f"missing saved request: {key}")
            continue
        request = comparison.read_json(request_path)
        payload = request["sdk_request"]
        text = request["user_message"]
        problem_path = project / "data/processed/problems" / (identifier + ".txt")
        problem = problem_path.read_text(encoding="utf-8-sig")
        checks = {
            "request_identity": (request["id"], request["method"], request["condition"]) == (identifier, method, condition),
            "exact_problem": request["problem_text"] == problem and text.startswith(problem),
            "request_hash": comparison.digest(payload) == request["sdk_request_sha256"],
            "input_hash": comparison.digest(text) == request["input_sha256"] == inputs[identifier][method],
            "sdk_contents": payload["contents"] == text,
            "requested_model": payload["model"] == config["model"],
            "system": payload["config"]["system_instruction"] == config["system_instruction"],
            "temperature": payload["config"]["temperature"] == config["temperature"],
            "max_output_tokens": payload["config"]["max_output_tokens"] == config["max_output_tokens"],
            "thinking": str(payload["config"]["thinking_config"]["thinking_level"]).rsplit(".", 1)[-1].lower() == str(config["thinking_level"]).lower(),
            "baseline_no_hint": method != "baseline" or (text == problem and request["hint"] is None),
            "hint_source": method == "baseline" or request["hint"]["source"] == (
                "actual_reference" if method == "oracle_hint" else "regression_prediction"),
        }
        for name, passed in checks.items():
            if not passed:
                violations.append(f"{name}: {key}")
        for path, captured in snapshots.get(key, []):
            if captured["request"] != payload or captured["request_sha256"] != comparison.digest(payload):
                violations.append(f"SDK snapshot differs from saved prompt: {path.name}")
            if captured.get("condition") != condition or captured.get("capture") != "immediately_before_sdk_generate_content":
                violations.append(f"SDK capture identity/kind mismatch: {path.name}")
        row = latest.get(key)
        if row:
            for field, wanted in (("input_text", text), ("input_sha256", request["input_sha256"]),
                                  ("problem_text", problem), ("system_instruction", config["system_instruction"]),
                                  ("model", config["model"])):
                if row.get(field) != wanted:
                    violations.append(f"response {field} differs from saved request: {key}")
            if row.get("uses_test_reference_vector") != (method == "oracle_hint"):
                violations.append(f"oracle source flag mismatch: {key}")
            if row["status"] != "success" and row.get("evaluation", {}).get("correct") is not None:
                violations.append(f"failed API response counted as a graded answer: {key}")
            raw = row.get("usage", {}).get("raw")
            if isinstance(raw, dict):
                raw_usage_compared += 1
                for field in comparison.USAGE_FIELDS:
                    if row["usage"].get(field) != raw.get(field):
                        violations.append(f"usage field differs from original SDK field: {key}/{field}")
            raw_response = row.get("raw_response")
            if isinstance(raw_response, dict) and raw_response.get("model_version") != row.get("model_version"):
                violations.append(f"response model_version differs from raw SDK response: {key}")
            version_counts[str(row.get("model_version"))] += 1
            if row.get("response_origin") == "new_api_call":
                current = [value for _, value in snapshots.get(key, []) if value["execution_id"] == row.get("rate_limited_execution_id")]
                if not current or len(current) != row.get("sdk_boundary_captured_attempts"):
                    violations.append(f"new response lacks matching actual SDK call capture(s): {key}")
                if row.get("sdk_request_sha256") != request["sdk_request_sha256"]:
                    violations.append(f"response SDK request hash mismatch: {key}")
            elif row.get("response_origin", "").startswith("reused"):
                provenance = row.get("provenance", {})
                source_path = resolve_source_file(provenance.get("source_records", ""), project, config)
                if not source_path.is_file():
                    violations.append(f"reused response original file unavailable: {key}")
                else:
                    if str(source_path) not in source_cache:
                        source_hash = comparison.file_hash(source_path)
                        source_rows = ([json.loads(line) for line in source_path.read_text(encoding="utf-8").splitlines() if line.strip()]
                                       if source_hash == provenance.get("source_records_sha256") else [])
                        source_cache[str(source_path)] = (source_hash,
                            {(value["id"], value["method"]): value for value in source_rows})
                    source_hash, source_rows = source_cache[str(source_path)]
                    original = source_rows.get(key)
                    if source_hash != provenance.get("source_records_sha256") or original is None:
                        violations.append(f"reused response source file hash/ID mismatch: {key}")
                    elif comparison.digest(original) != provenance.get("source_record_sha256"):
                        violations.append(f"reused original record hash mismatch: {key}")
                    elif any(row.get(field) != original.get(field) for field in
                             ("input_text", "system_instruction", "output_text", "usage", "model_version", "response_id", "started_at", "completed_at")):
                        violations.append(f"reused response differs from original request/response: {key}")
            else:
                warnings.append(f"unknown response origin: {key}")
        index.append({"id": identifier, "condition": condition, "method": method,
            "response_status": row.get("status") if row else "missing", "response_origin": row.get("response_origin") if row else None,
            "requested_model": config["model"], "response_model_version": row.get("model_version") if row else None,
            "saved_request": str(request_path.relative_to(output)), "sdk_request_sha256": request["sdk_request_sha256"],
            "captured_sdk_calls": len(snapshots.get(key, [])), "response_history_records": len(histories.get(key, [])),
            "input_matches": all(checks.values()), "response_id": row.get("response_id") if row else None})
    unexpected_snapshots = sorted(set(snapshots) - expected)
    if unexpected_snapshots:
        violations.append("SDK snapshots contain unexpected IDs/conditions: " + repr(unexpected_snapshots))
    # Latest retry records contain cumulative attempts; counting every JSONL history would double-count old attempts.
    attempts = [(row, attempt) for row in latest.values() for attempt in row.get("attempts", [])
                if not attempt.get("request_skipped")]
    unknown_usage = [{"id": row["id"], "method": row["method"], "condition": CONDITIONS[row["method"]],
        "response_origin": row.get("response_origin"), "attempt": attempt.get("attempt"),
        "execution": attempt.get("execution"), "status": attempt.get("status"), "error_type": attempt.get("error_type"),
        "total_token_count": None, "server_completion_and_billing": "not_confirmable_from_saved_response"}
        for row, attempt in attempts if attempt.get("usage", {}).get("total_token_count") is None]
    missing = [{"id": identifier, "method": method} for identifier, method in sorted(expected - set(latest))]
    report = {"checked_at": comparison.utc_now(), "config_id": config_id, "expected_requests": len(expected),
        "latest_records": len(latest), "historical_record_count": len(all_rows),
        "verification_passed": not violations, "all_expected_responses_available": not missing,
        "all_expected_successful": len(latest) == len(expected) and all(row["status"] == "success" for row in latest.values()),
        "violations": violations, "warnings": warnings, "missing_requests": missing,
        "status_counts": dict(Counter(row["status"] for row in latest.values())),
        "reused_successful_responses": sum(row["status"] == "success" and row.get("response_origin", "").startswith("reused") for row in latest.values()),
        "new_successful_responses": sum(row["status"] == "success" and row.get("response_origin") == "new_api_call" for row in latest.values()),
        "sdk_boundary_call_count": sum(map(len, snapshots.values())),
        "sdk_call_count_by_condition": {CONDITIONS[m]:sum(len(v) for (i, method), v in snapshots.items() if method == m) for m in config["methods"]},
        "raw_usage_fields_compared": raw_usage_compared, "unknown_usage_attempts": unknown_usage,
        "unknown_usage_attempts_by_condition": dict(Counter(value["condition"] for value in unknown_usage)),
        "model_versions": dict(version_counts),
        "model_verification_limit": "Requested model and API-returned model_version are recorded separately. Hidden internal model identity is not observable.",
        "historical_boundary_capture_limit": "Reused A/B requests are exact-text/config/hash verified against saved original records. Historical live SDK boundary capture was not available; current dry-run boundary verification does not retroactively establish it.",
        "token_accounting": "Use API total_token_count directly. Input/output/thought/cache fields are reported separately and never added to that total. Missing attempt usage stays null, so complete billed totals cannot be inferred.",
        "retry_accounting": "Failed then successful records for one ID/condition are preserved history. Two successful responses for one ID/condition would be flagged as duplicate completion."}
    if write_output:
        comparison.write_json(output / "prompt_audit/response_audit.json", report)
        with (output / "prompt_audit/request_response_index.csv").open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(index[0]) if index else ["id"])
            writer.writeheader(); writer.writerows(index)
    return report


def main():
    report = audit_generation()
    print(json.dumps({key: report[key] for key in ("verification_passed", "all_expected_responses_available", "all_expected_successful", "latest_records", "sdk_boundary_call_count")}, ensure_ascii=False))
    if not report["verification_passed"]:
        raise SystemExit("요청·응답 감사 불일치가 있습니다. response_audit.json을 확인하세요.")


if __name__ == "__main__":
    main()
