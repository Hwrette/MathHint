"""전체265 요청·응답·재사용·표시·기존 자료 보존 검증. 학습·API 호출은 없다."""

from collections import Counter
from bisect import bisect_left, bisect_right
import csv
from datetime import datetime
from itertools import combinations
import math
from pathlib import Path

from ... import CompareGeneration as comparison
from ...AnswerEvaluation import evaluate_answer
from ..gemini_comparison.run import load_data


def saved_request_rate_checks(shared_events, new_events, policy, *, tolerance_seconds=.01):
    """새 생성 시작 시점에서만 공유 로그와 로컬 정책을 대조한다. 공급자 한도 검증은 아니다."""
    interval = float(policy["interval_seconds"])
    caps = {60: int(policy["rpm"]), 3600: int(policy["rph"]), 86400: int(policy["rpd"])}
    if interval <= 0 or any(cap <= 0 for cap in caps.values()) or tolerance_seconds < 0:
        raise ValueError("양수 로컬 제한과 음이 아닌 시각 오차 허용값이 필요합니다.")
    malformed = []
    observed_counts = {"shared": 0, "new": 0}

    def starts(events, source):
        values = []
        for index, event in enumerate(events):
            if event.get("event") != "request_start":
                continue
            observed_counts[source] += 1
            try:
                timestamp = datetime.fromisoformat(event["time"].replace("Z", "+00:00"))
                if timestamp.tzinfo is None:
                    raise ValueError("UTC offset missing")
                seconds = timestamp.timestamp()
                if not math.isfinite(seconds):
                    raise ValueError("nonfinite timestamp")
            except (KeyError, TypeError, AttributeError, ValueError, OverflowError):
                malformed.append({"source": source, "event_index": index})
                continue
            values.append((seconds, comparison.digest(event)))
        return values

    shared = starts(shared_events, "shared")
    new = starts(new_events, "new")
    shared_unique = sorted(set(shared))
    shared_keys = {key for _, key in shared_unique}
    new_unique = sorted(set(new))
    new_keys = {key for _, key in new_unique}
    times = [seconds for seconds, _ in shared_unique]
    gaps, violations = [], []
    maxima = {window: 0 for window in caps}
    for position, (when, key) in enumerate(shared_unique):
        if key not in new_keys:
            continue
        upper = bisect_right(times, when)
        simultaneous = upper-bisect_left(times, when) > 1
        if position or simultaneous:
            gap = 0.0 if simultaneous else when-times[position-1]
            gaps.append(gap)
            if gap+tolerance_seconds < interval:
                violations.append({"kind": "interval", "event_sha256": key,
                                   "gap_seconds": gap, "required_seconds": interval})
        # 제한기와 같이 (t-window, t]를 센다. t-window의 시작은 이미 창 밖이다.
        for window, cap in caps.items():
            count = upper-bisect_right(times, when-window)
            maxima[window] = max(maxima[window], count)
            if count > cap:
                violations.append({"kind": "rolling_window", "event_sha256": key,
                                   "window_seconds": window, "start_count": count, "limit": cap})
    checks = [
        {"check": "rate_log_request_start_timestamps_are_valid", "passed": not malformed},
        {"check": "new_generation_start_records_are_unique", "passed": len(new) == len(new_unique)},
        {"check": "new_generation_starts_exist_in_shared_history", "passed": new_keys <= shared_keys},
        {"check": "new_starts_obey_shared_local_interval", "passed": not any(v["kind"] == "interval" for v in violations)},
        *[{"check": f"new_starts_obey_shared_rolling_{window}_second_cap", "passed": maxima[window] <= cap}
          for window, cap in caps.items()],
    ]
    return {"checks": checks, "passed": all(check["passed"] for check in checks),
        "new_request_start_count": observed_counts["new"], "valid_new_request_start_count": len(new),
        "new_unique_request_start_count": len(new_unique),
        "shared_request_start_log_count": observed_counts["shared"],
        "shared_request_start_count": len(shared_unique),
        "minimum_new_start_interval_seconds": min(gaps) if gaps else None,
        "maximum_rolling_start_counts_at_new_attempts": {str(window): value for window, value in maxima.items()},
        "local_policy": {"interval_seconds": interval, "rpm": caps[60], "rph": caps[3600], "rpd": caps[86400]},
        "timestamp_tolerance_seconds": tolerance_seconds, "violations": violations,
        "malformed_request_start_events": malformed, "provider_limits_confirmed": False,
        "scope_note": "새 생성 request_start 시점에서만 기존+신규 공유 이력과 저장 로컬 정책을 비교했다. 과거5초 정책 구간 자체를 현재10초 정책으로 판정하지 않는다. 공급자 실제 할당량은 확인하지 못했다.",
        "model_get_note": "비생성 models.get 조회는 별도 로그이며 생성 request_start 속도 집계에 포함하지 않는다."}


def _csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _same_csv_value(actual, expected):
    if actual in (None, "") and expected in (None, ""):
        return True
    if actual == expected:
        return True
    if actual in (None, "") or expected in (None, ""):
        return False
    try:
        return math.isclose(float(actual), float(expected), rel_tol=1e-12, abs_tol=1e-12)
    except (ValueError, TypeError):
        return False


def preservation_check(root, manifest):
    """복사 백업 대신 작업 시작 전 기록한 기존 추적 파일의 SHA를 대조한다."""
    root = Path(root)
    files = manifest.get("files_sha256", {})
    changed = [name for name, digest in files.items()
               if not (root / name).is_file() or comparison.file_hash(root / name) != digest]
    return {"protected_files": len(files), "changed_files": changed,
            "passed": bool(files) and not changed, "source_commit": manifest.get("source_commit")}


def reused_scientific_fields_equal(current, source):
    """새 실험 ID/출처만 달라질 수 있다. 원래 성공의 과학적 필드는 그대로다."""
    fields = ("id", "condition", "method", "split", "input_text", "input_sha256", "request_sha256",
              "output_text", "usage", "raw_response", "model_version", "response_id", "started_at", "completed_at",
              "evaluation", "attempts", "latency_seconds", "finish_reasons", "prompt_feedback", "transport", "transport_errors")
    return all(current.get(name) == source.get(name) for name in fields)


def saved_metric_checks(plan, records, summary_rows, token_rows, paired_rows, *, supplemental_grades=None):
    """표시 함수와 독립적으로 저장 원시 응답에서 합계·분모·대응표를 다시 계산한다."""
    checks = []
    def check(name, passed):
        checks.append({"check": name, "passed": bool(passed)})
    latest = {(row["id"], row["condition"]): row for row in records}
    summary = {(row["split"], row["condition"]): row for row in summary_rows}
    tokens = {(row["split"], row["condition"], row["token_field"]): row for row in token_rows}
    pairs = {(row["split"], row["pair"]): row for row in paired_rows}
    scopes = ("all265", "train", "test")
    fields = ("prompt_token_count", "candidates_token_count", "thoughts_token_count",
              "cached_content_token_count", "total_token_count")
    check("saved_summary_has12_unique_scope_condition_rows", len(summary_rows) == len(summary) == 12)
    check("saved_usage_has60_unique_scope_condition_fields", len(token_rows) == len(tokens) == 60)
    check("saved_paired_has18_unique_scope_pairs", len(paired_rows) == len(pairs) == 18)
    for scope in scopes:
        scoped = [item for item in plan if scope == "all265" or item["split"] == scope]
        scope_ids = list(dict.fromkeys(item["id"] for item in scoped))
        for condition in "ABCD":
            keys = [(item["id"], condition) for item in scoped if item["condition"] == condition]
            response_rows = [latest.get(key, {"status": "not_run"}) for key in keys]
            successes = [r for r in response_rows if r["status"] == "success"]
            graded = [r for r in successes if type(r.get("evaluation", {}).get("correct")) is bool]
            correct = sum(r["evaluation"]["correct"] for r in graded)
            supplemental = sum((supplemental_grades or {}).get((r["id"], condition), r["evaluation"]["correct"]) is True for r in graded)
            reused = sum(r.get("response_origin") in ("reused_exact_request", "reused_control") for r in successes)
            expected = {"expected_count": len(keys), "success_count": len(successes), "graded_count": len(graded),
                "correct_count": correct, "incorrect_count": len(graded)-correct, "ungradable_count": len(successes)-len(graded),
                "failed_count": sum(r["status"] not in ("success", "not_run") for r in response_rows),
                "pending_count": sum(r["status"] == "not_run" for r in response_rows),
                "accuracy_graded": correct/len(graded) if graded else None,
                "correct_count_ai_supplemental": supplemental,
                "accuracy_ai_supplemental": supplemental/len(graded) if graded else None,
                "reused_count": reused, "new_success_count": len(successes)-reused}
            actual = summary.get((scope, condition), {})
            for name, value in expected.items():
                check(f"csv_{scope}_{condition}_{name}", name in actual and _same_csv_value(actual[name], value))
            for field in fields:
                provided = [r.get("usage", {}).get(field) for r in successes if r.get("usage", {}).get(field) is not None]
                total = sum(provided) if provided else None
                mean = total/len(provided) if provided else None
                for suffix, value in (("_sum", total), ("_mean", mean)):
                    name = field+suffix
                    check(f"csv_{scope}_{condition}_{name}", name in actual and _same_csv_value(actual[name], value))
                token = tokens.get((scope, condition, field), {})
                for name, value in {"success_count": len(successes), "provided_count": len(provided),
                                    "missing_count": len(successes)-len(provided), "sum": total, "mean": mean}.items():
                    check(f"usage_csv_{scope}_{condition}_{field}_{name}", name in token and _same_csv_value(token[name], value))
        expected_pairs = []
        for first, second in combinations("ABCD", 2):
            table = Counter()
            for identifier in scope_ids:
                a, b = latest.get((identifier, first), {}), latest.get((identifier, second), {})
                x, y = a.get("evaluation", {}).get("correct"), b.get("evaluation", {}).get("correct")
                if a.get("status") == b.get("status") == "success" and type(x) is bool and type(y) is bool:
                    table[int(x), int(y)] += 1
            matched, discordant = sum(table.values()), table[1, 0]+table[0, 1]
            p = (min(1.0, 2*sum(math.comb(discordant, i) for i in range(min(table[1, 0], table[0, 1])+1))/2**discordant)
                 if discordant else 1.0) if matched else None
            expected_pairs.append({"pair": first+"-"+second, "matched_gradable_count": matched,
                "excluded_count": len(scope_ids)-matched, "both_correct": table[1, 1], "first_correct_second_wrong": table[1, 0],
                "first_wrong_second_correct": table[0, 1], "both_wrong": table[0, 0], "discordant_count": discordant,
                "p_exact_mcnemar": p, "p_holm_within_split": None})
        ordered = sorted((r for r in expected_pairs if r["p_exact_mcnemar"] is not None), key=lambda r: r["p_exact_mcnemar"])
        corrected = 0.0
        for index, row in enumerate(ordered):
            corrected = max(corrected, min(1.0, row["p_exact_mcnemar"]*(len(ordered)-index)))
            row["p_holm_within_split"] = corrected
        for row in expected_pairs:
            actual = pairs.get((scope, row["pair"]), {})
            for name, value in row.items():
                if name != "pair":
                    check(f"paired_csv_{scope}_{row['pair']}_{name}", name in actual and _same_csv_value(actual[name], value))
    return checks


def run(root=None, output=None, *, save=True):
    from .common import ROOT, OUTPUT, all_request_events, load_saved, read_json, read_jsonl, safe_output, write_json
    from .plan import prepare_plan
    from mathhint_learning.final_experiment_2.cluster_improvement.verify import scan_links
    from PIL import Image
    root = Path(root or ROOT).resolve()
    output = safe_output(root, output or (root / OUTPUT.relative_to(ROOT)))
    before = {str(p.relative_to(output)): comparison.file_hash(p) for p in output.rglob("*")
              if p.is_file() and p.name != "validation.json"}
    config, plan, records, state = load_saved(output)
    checks = []
    def check(name, condition):
        checks.append({"check": name, "passed": bool(condition)})
    data = load_data(root)
    expected_config, expected_plan = prepare_plan(root, data)
    check("frozen_models_data_and_full265_plan_match", config == expected_config and plan == expected_plan)
    ids = config["target_ids"]
    check("original185_80_split_and265_unique_target_ids", len(config["train_ids"]) == 185 and len(config["test_ids"]) == 80
          and len(ids) == len(set(ids)) == 265 and set(ids) == set(config["train_ids"]) | set(config["test_ids"]))
    check("1060_unique_original_split_request_keys", len(plan) == 1060
          and {(r["id"], r["condition"]) for r in plan} == {(identifier, c) for identifier in ids for c in "ABCD"}
          and all(r["split"] == ("train" if r["id"] in set(config["train_ids"]) else "test") for r in plan))
    lookup = {(r["id"], r["condition"]): r for r in plan}
    check("one_identical_problem_and_system_per_four_conditions", all(
        len({r["problem_text"] for r in plan if r["id"] == identifier}) == 1
        and len({r["system_instruction"] for r in plan if r["id"] == identifier}) == 1 for identifier in ids))
    for item in plan:
        saved = read_json(output / "prompt_audit/requests" / item["id"] / (item["condition"] + ".json"))
        sdk = comparison.request_snapshot(comparison.sdk_request_arguments(config, item["input_text"]))
        check("request_"+item["id"]+"_"+item["condition"], saved["sdk_request"] == sdk
              and comparison.digest(sdk) == saved["request_sha256"] == item["request_sha256"]
              and saved["user_message"] == item["input_text"])
    captures = read_jsonl(output / "prompt_audit/sdk_calls.jsonl")
    capture_keys = set()
    for index, capture in enumerate(captures):
        item = lookup.get((capture["id"], capture["condition"]))
        check("sdk_capture_"+str(index), item is not None and capture["request_sha256"] == item["request_sha256"]
              and comparison.digest(capture["sdk_request"]) == capture["request_sha256"]
              and capture.get("matches_saved_prompt") is True)
        capture_keys.add((capture["id"], capture["condition"], capture["request_sha256"]))
    source_cache, latest = {}, {}
    for row in records:
        key = row["id"], row["condition"]
        item = lookup.get(key)
        check("response_identity_"+"_".join(key), item is not None and row["split"] == item["split"]
              and row["input_text"] == item["input_text"] and row["hint"] == item["hint"]
              and row["request_sha256"] == item["request_sha256"])
        check("response_key_unique_"+"_".join(key), key not in latest)
        latest[key] = row
        usage = row.get("usage") or {}
        check("usage_"+"_".join(key), all(usage.get(f) is None or type(usage[f]) is int and usage[f] >= 0
                                              for f in comparison.USAGE_FIELDS))
        if isinstance(usage.get("raw"), dict):
            check("usage_raw_"+"_".join(key), all(usage.get(f) == usage["raw"].get(f) for f in comparison.USAGE_FIELDS))
        if row["status"] != "success":
            continue
        check("grade_"+"_".join(key), row["evaluation"] == evaluate_answer(row["output_text"], item["reference"], item["problem_text"]))
        if row.get("response_origin") == "new_api_call":
            check("live_sdk_boundary_"+"_".join(key), (*key, row["request_sha256"]) in capture_keys)
        elif row.get("response_origin") == "reused_exact_request":
            provenance = row.get("source_provenance") or {}
            source_path = root / provenance.get("records", "missing")
            if str(source_path) not in source_cache:
                source_cache[str(source_path)] = (comparison.file_hash(source_path) if source_path.is_file() else None,
                    {comparison.digest(r): r for r in read_jsonl(source_path)} if source_path.is_file() else {})
            source_hash, source_records = source_cache[str(source_path)]
            original = source_records.get(provenance.get("source_record_sha256"))
            check("reused_original_"+"_".join(key), source_hash == provenance.get("records_sha256")
                  and original is not None and reused_scientific_fields_equal(row, original))
            check("reused_prior_source_chain_"+"_".join(key), original is not None
                  and provenance.get("prior_provenance") == original.get("source_provenance"))
            audit_path = root / provenance.get("request_audit", "missing")
            audit = read_json(audit_path) if audit_path.is_file() else {}
            check("reused_sdk_request_"+"_".join(key), audit_path.is_file()
                  and comparison.file_hash(audit_path) == provenance.get("request_audit_sha256")
                  and comparison.digest(audit.get("sdk_request")) == row["request_sha256"])
    successful = [r for r in records if r["status"] == "success"]
    pending = {key for key in lookup if latest.get(key, {}).get("status") != "success"}
    check("state_counts_and_remaining_keys_match", state.get("successful_requests") == len(successful)
          and state.get("expected_requests") == len(plan) and state.get("pending_count") == len(pending)
          and {(r["id"], r["condition"]) for r in state.get("pending_requests", [])} == pending)
    check("completed_requires1060_successes", (state.get("status") == "completed") == (not pending))
    rate_audit = saved_request_rate_checks(all_request_events(root, output),
        read_jsonl(output / "execution_runs/request_events.jsonl"), read_json(output / "policy.json"))
    checks.extend(rate_audit["checks"])
    history_successes = [r for r in read_jsonl(output / "responses.jsonl") if r.get("status") == "success"]
    check("successful_requests_never_saved_twice", len(history_successes) == len({(r["id"], r["condition"]) for r in history_successes}))
    preservation = preservation_check(root, read_json(output / "preservation_manifest.json"))
    check("all_existing_files_preserved", preservation["passed"])
    summary_path = output / "summary.csv"
    if summary_path.is_file():
        from ..gemini_comparison.review import key_conflicts
        from ...AnswerEvaluation import extract_reference
        supplemental_grades = {}
        for identifier, evidence in key_conflicts(root).items():
            for condition in "ABCD":
                row = latest.get((identifier, condition))
                if row and row["status"] == "success":
                    reference = extract_reference({**data["records"][identifier],
                        "answer_text": evidence["mathematically_supported_answer"]}, row["problem_text"])
                    supplemental_grades[identifier, condition] = evaluate_answer(row["output_text"], reference, row["problem_text"])["correct"]
        checks.extend(saved_metric_checks(plan, records, _csv(summary_path), _csv(output / "token_summary.csv"),
                                         _csv(output / "paired_comparison.csv"), supplemental_grades=supplemental_grades))
        scientific_fields = ("expected_count", "success_count", "graded_count", "correct_count", "incorrect_count",
            "ungradable_count", "failed_count", "pending_count", "accuracy_graded", "correct_count_ai_supplemental",
            "accuracy_ai_supplemental", *[field+suffix for field in ("prompt_token_count", "candidates_token_count",
            "thoughts_token_count", "cached_content_token_count", "total_token_count") for suffix in ("_mean", "_sum")])
        old_rows = {r["condition"]: r for r in _csv(root / "results/final_experiment_2/gemini_comparison/summary.csv") if r["split"] == "test"}
        new_rows = {r["condition"]: r for r in _csv(summary_path) if r["split"] == "test"}
        check("old80_scientific_summary_matches_exact_reuse", set(old_rows) == set(new_rows) == set("ABCD") and all(
            _same_csv_value(new_rows[c].get(f), old_rows[c].get(f)) for c in "ABCD" for f in scientific_fields))
    links, broken = scan_links(output)
    check("all_relative_markdown_links_exist", not broken)
    image_errors = []
    images = list(output.glob("figures/*.png"))
    for path in images:
        try:
            with Image.open(path) as image:
                size = image.size; image.verify()
            if size[0] < 500 or size[1] < 300:
                image_errors.append(path.name)
        except (OSError, ValueError):
            image_errors.append(path.name)
    check("new_figures_decode_readably", bool(images) and not image_errors)
    browser_path = output / "review/browser_validation.json"
    browser = read_json(browser_path) if browser_path.is_file() else {"performed": False}
    if browser.get("performed"):
        check("actual_browser_record_matches_html_assets", browser.get("passed") is True
              and browser.get("report_sha256") == comparison.file_hash(output / "report.html")
              and bool(browser.get("assets_sha256")) and all((root / name).is_file()
              and comparison.file_hash(root / name) == digest for name, digest in browser["assets_sha256"].items()))
    after = {str(p.relative_to(output)): comparison.file_hash(p) for p in output.rglob("*")
             if p.is_file() and p.name != "validation.json"}
    check("verification_does_not_mutate_inputs_logs_or_results", before == after)
    result = {"verified_at": comparison.utc_now(), "checks": checks, "passed": sum(c["passed"] for c in checks),
        "failed": sum(not c["passed"] for c in checks), "complete": all(c["passed"] for c in checks),
        "experiment_complete": not pending, "successful_requests": len(successful), "expected_requests": len(plan),
        "pending_requests": len(pending), "split_counts": {s: sum(r["status"] == "success" and r["split"] == s for r in records) for s in ("train", "test")},
        "preservation": preservation, "markdown_links_checked": links, "broken_links": broken,
        "actual_generation_rate_audit": rate_audit,
        "decoded_png_count": len(images), "invalid_images": image_errors, "actual_browser_validation": browser,
        "live_api_calls_during_verification": 0, "model_training_during_verification": False,
        "limits": ["전체265는학습185와테스트80의혼합참고자료이며새미관측일반화평가가아니다。",
                   "풀이검토상태와최종답자동채점은별개이며검토보류는타당판정이아니다。"]}
    if save:
        write_json(output / "validation.json", result)
    return result
