"""독립 반복 신원만 실행하며 기존 SDK·공유 속도 제한기를 재사용한다."""

from datetime import datetime, timezone
import os
from pathlib import Path

from ... import CompareGeneration as comparison
from ..gemini_comparison.budget import BudgetRateLimiter
from ..gemini_comparison.run import transport_request
from ..gemini_full265.run import provider_quota_observation
from .common import (ROOT, OUTPUT, METHODS, DEFAULT_POLICY, append_jsonl, read_json,
    read_jsonl, write_json, safe_output, source_output, all_request_events, execution_lock,
    verify_preservation, request_key, load_latest, is_received, API_RECEIVED_STATUSES)
from .plan import prepare_plan, initialize, MODEL


def _load_policy(output, supplied=None):
    path = Path(output) / "policy.json"
    policy = {**DEFAULT_POLICY, **(read_json(path) if path.is_file() else {}), **(supplied or {})}
    if (policy["workers"] != 1 or policy["interval_seconds"] < 10 or policy["rpm"] > 6
            or policy.get("provider_limits_confirmed")):
        raise ValueError("공급자 전체 한도는 미확인이므로10초/6RPM/작업자1과 미확인 표시를 유지합니다.")
    for name in ("rpm", "rph", "rpd", "max_new_requests", "max_run_seconds", "max_wait_seconds", "http_timeout_ms"):
        if policy[name] <= 0:
            raise ValueError("양수 실행 한도가 필요합니다: " + name)
    if not path.exists():
        write_json(path, policy)
    return policy


def state_record(output, config, plan, *, status, reason=None, limiter=None):
    output = Path(output)
    records = load_latest(output, comparison.digest(config))
    index = {request_key(row): row for row in plan}
    if set(records) - set(index):
        raise ValueError("승인된186개 밖의 저장 요청이 있습니다.")
    for key, record in records.items():
        planned = index[key]
        if any(record.get(name) != planned.get(name) for name in
               ("request_id", "request_sha256", "input_sha256", "input_text", "problem_text", "system_instruction", "hint")):
            raise ValueError("저장 응답과 동결 요청이 다릅니다: " + str(key))
    successes = [row for row in records.values() if row["status"] == "success"]
    received = [row for row in records.values() if is_received(row)]
    incomplete = [row for row in received if row["status"] != "success"]
    failed = [row for row in records.values() if not is_received(row)]
    pending = [{**{name: row[name] for name in ("id", "condition", "repeat", "request_id", "split", "request_sha256", "schedule_position")},
                "last_status": records.get(request_key(row), {}).get("status", "not_executed")}
               for row in plan if not is_received(records.get(request_key(row), {}))]
    if not pending:
        status, reason = "completed", (f"계획된 {len(plan)}개 반복의 API 응답을 모두 저장했습니다. "
            f"정상 STOP {len(successes)}개, 길이 제한·차단·빈 응답 {len(incomplete)}개이며 비정상 응답도 재추첨하지 않습니다.")
    elif status == "completed":
        status, reason = "partial_complete", "실패·미완료 반복이 남아 있습니다."
    result = {"status": status, "reason": reason, "updated_at": comparison.utc_now(),
        "config_id": comparison.digest(config), "experiment_id": config["experiment_id"],
        "expected_requests": len(plan), "successful_requests": len(successes),
        "completed_requests": len(received), "api_response_count": len(received),
        "incomplete_response_count": len(incomplete),
        "by_status": {status: sum(row["status"] == status for row in records.values())
                      for status in sorted({row["status"] for row in records.values()})},
        "failed_requests": len(failed), "saved_responses": len(records),
        "response_log_entries": len(read_jsonl(output / "responses.jsonl")),
        "pending_count": len(pending), "pending_requests": pending,
        "pending_by_condition": {c: sum(row["condition"] == c for row in pending) for c in METHODS},
        "successful_by_condition": {c: sum(row["condition"] == c for row in successes) for c in METHODS},
        "completed_by_condition": {c: sum(row["condition"] == c for row in received) for c in METHODS},
        "by_repeat": {str(repeat): {"expected": sum(row["repeat"] == repeat for row in plan),
            "success": sum(row["repeat"] == repeat for row in successes),
            "completed": sum(row["repeat"] == repeat for row in received),
            "incomplete": sum(row["repeat"] == repeat for row in incomplete),
            "failed": sum(row["repeat"] == repeat for row in failed),
            "pending": sum(row["repeat"] == repeat for row in pending)} for repeat in (1, 2, 3)},
        "new_successes": len(successes), "new_completed_requests": len(received),
        "historical_reused_successes": 0, "reused_successes": 0,
        "safe_to_resume": bool(pending) and status not in ("missing_api_key", "permission_denied"),
        "resume_command": "python -m mathhint_solver.final_experiment_2.final_followup generate"
                          + (" --clear-stop" if (output / "stop_requested").exists() else ""),
        "resume_prerequisites": "공급자 제한·기록된 재시도 대기와 실행 예산을 확인한 뒤 미완료 반복만 재개",
        "provider_daily_reset_time": None,
        "provider_quota_observation": provider_quota_observation(read_jsonl(output / "responses.jsonl"),
            read_jsonl(output / "execution_runs/request_events.jsonl")),
        "api_received_terminal_statuses": list(API_RECEIVED_STATUSES),
        "resume_note": "과거 응답을 반복으로 세지 않는다. 같은 API수신(id,condition,repeat)은 정상 STOP/길이제한/차단/빈응답 모두 재호출하지 않으며 다른 repeat은 같은 프롬프트도 신규 호출한다. 전송실패만 재개한다. 자동 재개 예약은 설정하지 않았다.",
        "study_status": "three-repeat follow-up only; no project-final closure"}
    if limiter is not None:
        result["limiter"] = limiter.snapshot()
    write_json(output / "state.json", result)
    return result


def prepare(root=ROOT, output=OUTPUT):
    root = Path(root).resolve()
    output = safe_output(root, output)
    preservation = verify_preservation(root, output)
    policy = _load_policy(output)
    config, plan, frozen = prepare_plan(root)
    initialize(output, config, plan, frozen)
    state = state_record(output, config, plan, status="partial_complete",
                         reason="186개 반복 신원과62개 실제 요청 전문을 동결했습니다. API 환경은 별도 확인합니다.")
    return config, plan, {"preservation": preservation, "state": state,
        "frozen_prompt_count": len(frozen), "new_live_api_calls": 0}, output, policy


def _preflight(root=ROOT, output=OUTPUT, *, offline=False, client_factory=None, api_key=None):
    config, plan, preparation, output, policy = prepare(root, output)
    key = api_key if api_key is not None else os.environ.get("GEMINI_API_KEY")
    info = {"checked_at": comparison.utc_now(), "config_id": comparison.digest(config),
        "requested_model": MODEL, "generation_calls": 0, "non_generation_network_calls": 0,
        "expected_requests": len(plan), "successful_saved": preparation["state"]["successful_requests"],
        "completed_saved": preparation["state"]["completed_requests"],
        "incomplete_saved": preparation["state"]["incomplete_response_count"],
        "new_requests_needed": preparation["state"]["pending_count"],
        "preservation": preparation["preservation"], "frozen_prompt_count": preparation["frozen_prompt_count"],
        "provider_rate_limits": {"requests_per_minute": None, "requests_per_hour": None,
            "requests_per_day": None, "tokens_per_minute": None, "remaining_daily_requests": None},
        "quota_observability": "models.get verifies capabilities, not project quota or current remaining budget; local limits are not provider confirmation",
        "local_execution_policy": policy, "api_key_present": bool(key), "api_readiness": "not_checked"}
    if offline:
        info["api_readiness"] = "offline_audit_only"
    elif (output / "stop_requested").exists():
        info["api_readiness"] = "interrupted"
        state_record(output, config, plan, status="interrupted", reason="중단 파일이 있어 모델 조회도 보내지 않았습니다.")
    elif not key:
        info["api_readiness"] = "missing_api_key"
        state_record(output, config, plan, status="missing_api_key", reason="GEMINI_API_KEY가 없습니다.")
    else:
        try:
            if client_factory is None:
                from google import genai
                client_factory = genai.Client
            from google.genai import types
            with client_factory(api_key=key, http_options=types.HttpOptions(timeout=30_000,
                    retry_options=types.HttpRetryOptions(attempts=1))) as client:
                info["non_generation_network_calls"] += 1
                model = client.models.get(model=MODEL)
            details = comparison._dump(model)
            actions = details.get("supported_actions") if isinstance(details, dict) else None
            if actions and not any("generatecontent" in str(action).replace("_", "").lower() for action in actions):
                raise ValueError("요청 모델이 generateContent를 지원하지 않습니다. 대체 모델을 사용하지 않습니다.")
            info.update(api_readiness="ready", model_metadata=details,
                reported_model_name=details.get("name") if isinstance(details, dict) else None)
        except Exception as error:
            code = comparison._error_code(error)
            status = "permission_denied" if code in (400, 401, 403, 404) else "paused_rate_limit" if code == 429 else "partial_complete"
            message = str(error).replace(key, "[REDACTED]") if key else str(error)
            info.update(api_readiness=status, error={"code": code, "type": type(error).__name__, "message": message})
            state_record(output, config, plan, status=status, reason="모델 지원·인증 확인 실패: " + message)
    write_json(output / "preflight.json", info)
    if info["non_generation_network_calls"]:
        append_jsonl(output / "execution_runs/preflight_network_calls.jsonl", {
            "checked_at": info["checked_at"], "operation": "models.get", "model": MODEL,
            "network_calls": info["non_generation_network_calls"], "readiness": info["api_readiness"]})
    return info


def _preflight_fresh(output, config):
    path = Path(output) / "preflight.json"
    if not path.is_file():
        return False
    record = read_json(path)
    try:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(record["checked_at"])).total_seconds()
    except (KeyError, ValueError, TypeError):
        return False
    return record.get("config_id") == comparison.digest(config) and record.get("api_readiness") == "ready" and 0 <= age < 1800


def _generate(root=ROOT, output=OUTPUT, *, policy=None, request_function=None, api_key=None):
    root = Path(root).resolve()
    config, plan, preparation, output, saved_policy = prepare(root, output)
    policy = _load_policy(output, {**saved_policy, **(policy or {})})
    key = api_key if api_key is not None else os.environ.get("GEMINI_API_KEY")
    if not preparation["state"]["pending_requests"]:
        return state_record(output, config, plan, status="completed")
    if request_function is None:
        if not _preflight_fresh(output, config):
            info = _preflight(root, output, api_key=key)
            if info["api_readiness"] != "ready":
                return read_json(output / "state.json")
        if not key:
            return state_record(output, config, plan, status="missing_api_key", reason="GEMINI_API_KEY가 없습니다.")
    config_id = comparison.digest(config)
    execution_id = comparison.utc_now().replace(":", "").replace(".", "_")
    path = output / "execution_runs" / (execution_id + ".json")
    context = {"id": None, "condition": None, "repeat": None, "request_id": None}
    events_path = output / "execution_runs/request_events.jsonl"
    execution = {"execution_id": execution_id, "config_id": config_id, "started_at": comparison.utc_now(),
        "status": "running", "policy": policy, "preexisting_successes": preparation["state"]["successful_requests"],
        "runner_sha256": comparison.file_hash(Path(__file__)),
        "shared_transport_sha256": comparison.file_hash(Path(transport_request.__code__.co_filename)),
        "transport": {"http_timeout_ms": policy["http_timeout_ms"], "sdk_attempts": 1},
        "sdk_request_capture": "immediately before generate_content",
        "cache_identity": "id+condition+repeat; historical results excluded"}
    write_json(path, execution)
    def event(value):
        append_jsonl(events_path, {**value, "execution_id": execution_id, **context})
    limiter = BudgetRateLimiter(policy, events=all_request_events(root, output), event_handler=event,
                               stop_requested=(output / "stop_requested").exists)
    final_status, reason, consecutive_failures = "partial_complete", "미완료 반복 요청이 남아 있습니다.", 0
    try:
        completed = load_latest(output, config_id)
        for item in plan:
            key_tuple = request_key(item)
            if is_received(completed.get(key_tuple, {})):
                continue
            context.update({name: item[name] for name in context})
            expected = read_json(output / item["frozen_prompt_path"])
            captures, transport_errors = [], []
            def observe(snapshot):
                if snapshot != expected["sdk_request"] or comparison.digest(snapshot) != item["request_sha256"]:
                    raise ValueError("실제 전송 직전 SDK 인자가 동결 기록과 다릅니다.")
                captures.append(comparison.digest(snapshot))
                append_jsonl(output / "prompt_audit/sdk_calls.jsonl", {
                    **{name: item[name] for name in ("id", "condition", "repeat", "request_id", "split")},
                    "execution_id": execution_id, "captured_at": comparison.utc_now(),
                    "sdk_request": snapshot, "request_sha256": captures[-1], "matches_frozen_prompt": True,
                    "capture": "immediately_before_sdk_generate_content",
                    "transport": {"http_timeout_ms": policy["http_timeout_ms"], "sdk_attempts": 1}})
            request = request_function or transport_request(config, key,
                http_timeout_ms=policy["http_timeout_ms"], request_observer=observe,
                error_observer=transport_errors.append)
            row = comparison.generate_one(item, config, config_id, key or "",
                request_function=lambda text: limiter.request(request, text))
            row.update(execution_id=execution_id, sdk_request_sha256=item["request_sha256"],
                transport={"http_timeout_ms": policy["http_timeout_ms"], "sdk_attempts": 1},
                transport_errors=transport_errors, sdk_boundary_captured_attempts=len(captures),
                sdk_boundary_capture_expected=request_function is None,
                solution_review={"status": "pending_review", "mathematical_validity": None,
                    "reason": "새 반복의 풀이를 별도 검토해야 하며 과거 오류 판정을 복사하지 않는다."})
            if row["status"] == "stopped_before_request":
                final_status = limiter.stop_status or ("daily_quota_exhausted" if limiter.daily_exhausted else "interrupted")
                reason = limiter.stop_reason or "새 요청 전 중단했습니다."
                break
            previous = completed.get(key_tuple)
            if previous:
                row["prior_executions"] = previous.get("prior_executions", []) + [{field: previous.get(field)
                    for field in ("status", "started_at", "completed_at", "error", "response_id")}]
            comparison.save_result(output, row)
            completed[key_tuple] = row
            consecutive_failures = 0 if is_received(row) else consecutive_failures + 1
            state_record(output, config, plan, status="partial_complete",
                         reason="새 반복 성공을 즉시 저장하고 남은 요청을 진행합니다.", limiter=limiter)
            print(f"{item['id']} {item['condition']} 반복{item['repeat']}: {row['status']} · "
                  f"저장 응답 {sum(is_received(r) for r in completed.values())}/{len(plan)} · "
                  f"정상 STOP {sum(r['status']=='success' for r in completed.values())}", flush=True)
            if limiter.daily_exhausted or limiter.stop_status:
                final_status = "daily_quota_exhausted" if limiter.daily_exhausted else limiter.stop_status
                reason = limiter.stop_reason or "공급자 일일 할당량 소진을 확인했습니다."
                break
            if consecutive_failures >= 3:
                final_status, reason = "partial_complete", "세 요청 연속 실패로 무한 재시도 없이 중단했습니다."
                break
        else:
            final_status, reason = "completed", "계획된 반복 API 응답을 모두 저장했습니다. 비정상 수신 응답도 한 시행으로 보존합니다."
    except KeyboardInterrupt:
        final_status, reason = "interrupted", "실행 중단 신호를 확인했습니다."
    except comparison.RequestedStop as error:
        final_status, reason = getattr(error, "status", "interrupted"), str(error)
    except BaseException as error:
        final_status, reason = "interrupted", str(error).replace(key, "[REDACTED]") if key else str(error)
        execution["error_type"] = type(error).__name__
        raise
    finally:
        state = state_record(output, config, plan, status=final_status, reason=reason, limiter=limiter)
        execution.update(completed_at=comparison.utc_now(), status=state["status"],
            successful_requests=state["successful_requests"], failed_requests=state["failed_requests"],
            completed_requests=state["completed_requests"], api_response_count=state["api_response_count"],
            incomplete_response_count=state["incomplete_response_count"], by_status=state["by_status"],
            pending_count=state["pending_count"], pending_requests=state["pending_requests"],
            new_request_starts=limiter.new_starts, limiter=limiter.snapshot(), reason=reason)
        write_json(path, execution)
    return state


def preflight(root=ROOT, output=OUTPUT, **kwargs):
    with execution_lock(root, output):
        return _preflight(root, output, **kwargs)


def generate(root=ROOT, output=OUTPUT, *, clear_stop=False, render_callback=None, **kwargs):
    with execution_lock(root, output):
        if clear_stop:
            (safe_output(root, output) / "stop_requested").unlink(missing_ok=True)
        try:
            result = _generate(root, output, **kwargs)
        finally:
            if render_callback is not None and (Path(output) / "config.json").is_file():
                render_callback(root, output)
        return result
