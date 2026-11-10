"""명시적으로 승인한 전체265 확장. 공통 Gemini 호출·제한·저장은 기존 구현을 사용한다."""

from datetime import datetime, timezone
import os
from pathlib import Path

from ... import CompareGeneration as comparison
from ..gemini_comparison.budget import BudgetRateLimiter
from ..gemini_comparison.run import transport_request, load_data
from .common import (ROOT, OUTPUT, METHODS, DEFAULT_POLICY, append_jsonl, read_json,
    read_jsonl, write_json, safe_output, source_output, all_request_events, execution_lock, verify_preservation)
from .plan import prepare_plan, initialize, dry_run, reuse_existing, MODEL


def _load_policy(output, supplied=None):
    path = Path(output) / "policy.json"
    policy = {**DEFAULT_POLICY, **(read_json(path) if path.exists() else {}), **(supplied or {})}
    if policy["workers"] != 1 or policy["interval_seconds"] < 10 or policy["rpm"] > 6:
        raise ValueError("공급자 한도가 미확인이므로10초/6RPM/1작업자를 유지합니다.")
    if policy.get("provider_limits_confirmed"):
        raise ValueError("이번 사용자의 전체265 승인은 공급자 한도 확인으로 취급하지 않습니다.")
    for field in ("rpd", "rph", "rpm", "max_new_requests", "max_run_seconds", "max_wait_seconds", "http_timeout_ms"):
        if policy[field] <= 0:
            raise ValueError(f"양수 실행 제한이 필요합니다: {field}")
    if not path.exists():
        write_json(path, policy)
    return policy


def state_record(output, config, plan, *, status, reason=None, limiter=None):
    output = Path(output)
    records = comparison.load_completed(output, comparison.digest(config))
    expected = {(row["id"], row["method"]) for row in plan}
    if set(records) - expected:
        raise ValueError("저장 응답에 전체265 계획 외 문항이 있습니다.")
    successes = [row for row in records.values() if row["status"] == "success"]
    failures = [row for row in records.values() if row["status"] != "success"]
    pending = [{"id": row["id"], "condition": row["condition"], "method": row["method"],
                "split": row["split"], "request_sha256": row["request_sha256"],
                "last_status": records.get((row["id"], row["method"]), {}).get("status", "not_executed")}
               for row in plan if records.get((row["id"], row["method"]), {}).get("status") != "success"]
    if not pending:
        status, reason = "completed", "전체265문항 네 조건의 성공 응답이 저장되었습니다."
    elif status == "completed":
        status, reason = "partial_complete", "실패·미완료 요청이 남아 있습니다."
    by_split = {split: {"expected_requests": sum(row["split"] == split for row in plan),
                       "successful_requests": sum(row["split"] == split for row in successes),
                       "pending_requests": sum(row["split"] == split for row in pending)} for split in ("test", "train")}
    result = {"status": status, "reason": reason, "updated_at": comparison.utc_now(),
        "config_id": comparison.digest(config), "split": "all", "experiment_scope": "full265",
        "expected_requests": len(plan), "successful_requests": len(successes),
        "failed_requests": len(failures), "saved_responses": len(records),
        "response_log_entries": len(read_jsonl(output / "responses.jsonl")),
        "pending_count": len(pending), "pending_requests": pending, "by_split": by_split,
        "reused_successes": sum(row.get("response_origin") == "reused_exact_request" for row in successes),
        "new_successes": sum(row.get("response_origin") == "new_api_call" for row in successes),
        "safe_to_resume": bool(pending) and status not in ("missing_api_key", "permission_denied"),
        "resume_command": "python -m mathhint_solver.final_experiment_2.gemini_full265 generate"
                          + (" --clear-stop" if (output / "stop_requested").exists() else ""),
        "resume_prerequisites": "공급자 실제 일일 제한/초기화 또는 로컬rolling24h 상한을 확인" if status == "daily_quota_exhausted" else
            "인증·접근 권한/요청 모델 지원을 복구" if status in ("missing_api_key", "permission_denied") else
            "기록된 대기시간과 실행 예산을 확인하고 미완료만 실행",
        "provider_daily_reset_time": None,
        "resume_note": "성공 요청은 해시를 검증해 재사용한다. 환경 종료 후 자동 예약은 설정하지 않았다.",
        "user_authorized_additional_train185": True,
        "training_scope_note": "train185는 모델 가중치 학습에 사용된 문항의 예측이다. 전체265 혼합값은 독립 테스트 성능이 아니다."}
    if limiter is not None:
        result["limiter"] = limiter.snapshot()
    write_json(output / "state.json", result)
    return result


def prepare(root=ROOT, output=OUTPUT, *, data=None):
    root = Path(root).resolve()
    output = safe_output(root, output)
    preservation = verify_preservation(root, output)
    data = data or load_data(root)
    policy = _load_policy(output)
    config, plan = prepare_plan(root, data)
    initialize(output, config, plan)
    audit = dry_run(root, output, config, plan)
    reuse = reuse_existing(root, output, config, plan)
    state = state_record(output, config, plan, status="partial_complete", reason="전체265 요청 감사·정확 재사용 완료. 실제 API 환경은 별도 확인합니다.")
    return config, plan, {"dry_run": audit, "reuse": reuse, "state": state, "preservation": preservation}, output, policy


def _preflight(root=ROOT, output=OUTPUT, *, offline=False, data=None, client_factory=None, api_key=None):
    config, plan, preparation, output, policy = prepare(root, output, data=data)
    key = api_key if api_key is not None else os.environ.get("GEMINI_API_KEY")
    info = {"checked_at": comparison.utc_now(), "config_id": comparison.digest(config),
        "requested_model": MODEL, "generation_calls": 0, "non_generation_network_calls": 0,
        "expected_requests": len(plan), "successful_saved": preparation["state"]["successful_requests"],
        "new_requests_needed": preparation["state"]["pending_count"], "preparation": preparation,
        "provider_rate_limits": {"requests_per_minute": None, "requests_per_hour": None,
                                 "requests_per_day": None, "tokens_per_minute": None, "remaining_daily_requests": None},
        "quota_observability": "models.get does not expose project rate or remaining daily quota; explicit user authorization is not provider quota confirmation",
        "local_execution_policy": policy, "api_key_present": bool(key), "api_readiness": "not_checked",
        "user_authorized_additional_train185": True, "shared_prior_request_events": str((source_output(root) / "execution_runs/request_events.jsonl").relative_to(Path(root).resolve()))}
    if offline:
        info["api_readiness"] = "offline_audit_only"
    elif (output / "stop_requested").exists():
        info["api_readiness"] = "interrupted"
        state_record(output, config, plan, status="interrupted", reason="중단 파일이 있어 API를 보내지 않았습니다.")
    elif not key:
        info["api_readiness"] = "missing_api_key"
        state_record(output, config, plan, status="missing_api_key", reason="GEMINI_API_KEY 환경변수가 없습니다.")
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
                raise ValueError("요청 모델이 generateContent를 지원하지 않습니다. 다른 모델로 변경하지 않습니다.")
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
    if not path.exists():
        return False
    record = read_json(path)
    try:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(record["checked_at"])).total_seconds()
    except (KeyError, ValueError, TypeError):
        return False
    return record.get("config_id") == comparison.digest(config) and record.get("api_readiness") == "ready" and age < 1800


def _generate(root=ROOT, output=OUTPUT, *, policy=None, request_function=None, api_key=None, data=None):
    root = Path(root).resolve()
    config, plan, preparation, output, saved_policy = prepare(root, output, data=data)
    policy = _load_policy(output, {**saved_policy, **(policy or {})})
    key = api_key if api_key is not None else os.environ.get("GEMINI_API_KEY")
    if not preparation["state"]["pending_requests"]:
        return state_record(output, config, plan, status="completed")
    if request_function is None:
        if not _preflight_fresh(output, config):
            info = _preflight(root, output, data=data, api_key=key)
            if info["api_readiness"] != "ready":
                return read_json(output / "state.json")
        if not key:
            return state_record(output, config, plan, status="missing_api_key", reason="GEMINI_API_KEY가 없습니다.")
    config_id = comparison.digest(config)
    execution_id = comparison.utc_now().replace(":", "").replace(".", "_")
    path = output / "execution_runs" / (execution_id + ".json")
    context = {"id": None, "condition": None, "split": None}
    events_path = output / "execution_runs/request_events.jsonl"
    prior_events_path = source_output(root) / "execution_runs/request_events.jsonl"
    execution = {"execution_id": execution_id, "config_id": config_id, "started_at": comparison.utc_now(),
        "status": "running", "experiment_scope": "full265", "policy": policy,
        "transport": {"http_timeout_ms": policy["http_timeout_ms"], "sdk_attempts": 1},
        "preexisting_successes": preparation["state"]["successful_requests"],
        "runner_sha256": comparison.file_hash(Path(__file__)),
        "shared_transport_sha256": comparison.file_hash(Path(transport_request.__code__.co_filename)),
        "prior_request_events": {"path": str(prior_events_path.relative_to(root)), "sha256": comparison.file_hash(prior_events_path)},
        "sdk_request_capture": "immediately before generate_content"}
    write_json(path, execution)
    def event(value):
        append_jsonl(events_path, {**value, "execution_id": execution_id, **context})
    limiter = BudgetRateLimiter(policy, events=all_request_events(root, output), event_handler=event,
                               stop_requested=(output / "stop_requested").exists)
    final_status, reason, consecutive_failures = "partial_complete", "미완료 요청이 남아 있습니다.", 0
    try:
        completed = comparison.load_completed(output, config_id)
        for item in plan:
            key_tuple = item["id"], item["method"]
            if completed.get(key_tuple, {}).get("status") == "success":
                continue
            context.update(id=item["id"], condition=item["condition"], split=item["split"])
            expected = read_json(output / f"prompt_audit/requests/{item['id']}/{item['condition']}.json")
            captures, transport_errors = [], []
            def observe(snapshot):
                if snapshot != expected["sdk_request"] or comparison.digest(snapshot) != item["request_sha256"]:
                    raise ValueError("실제 전송 직전 SDK 인자가 감사 기록과 다릅니다.")
                captures.append(comparison.digest(snapshot))
                append_jsonl(output / "prompt_audit/sdk_calls.jsonl", {"id": item["id"],
                    "condition": item["condition"], "split": item["split"], "execution_id": execution_id,
                    "captured_at": comparison.utc_now(), "sdk_request": snapshot,
                    "request_sha256": captures[-1], "matches_saved_prompt": True,
                    "transport": {"http_timeout_ms": policy["http_timeout_ms"], "sdk_attempts": 1},
                    "capture": "immediately_before_sdk_generate_content"})
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
                    "reason": "최종 답 자동채점과 풀이 타당성은 별개이며 신규 응답은 검토 보류다."})
            if row["status"] == "stopped_before_request":
                final_status = limiter.stop_status or ("daily_quota_exhausted" if limiter.daily_exhausted else "interrupted")
                reason = limiter.stop_reason or "새 요청 전 실행을 중단했습니다."
                break
            previous = completed.get(key_tuple)
            if previous:
                row["prior_executions"] = previous.get("prior_executions", []) + [{field: previous.get(field)
                    for field in ("status", "started_at", "completed_at", "error", "response_id")}]
            comparison.save_result(output, row)
            completed[key_tuple] = row
            consecutive_failures = 0 if row["status"] == "success" else consecutive_failures + 1
            state_record(output, config, plan, status="partial_complete", reason="성공을 즉시 저장하고 남은 요청을 진행합니다.", limiter=limiter)
            print(f"{item['id']} {item['condition']}: {row['status']} · 저장 성공 {sum(r['status']=='success' for r in completed.values())}/{len(plan)}", flush=True)
            if limiter.daily_exhausted or limiter.stop_status:
                final_status = "daily_quota_exhausted" if limiter.daily_exhausted else limiter.stop_status
                reason = limiter.stop_reason or "공급자 일일 할당량 소진을 확인했습니다."
                break
            if consecutive_failures >= 3:
                final_status, reason = "partial_complete", "세 요청이 연속 실패하여 무제한 재시도 없이 중단했습니다."
                break
        else:
            final_status, reason = "completed", "전체265 네 조건의 성공 응답을 저장했습니다."
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
            pending_count=state["pending_count"], pending_requests=state["pending_requests"],
            new_request_starts=limiter.new_starts, limiter=limiter.snapshot(), reason=reason)
        write_json(path, execution)
    return state


def preflight(root=ROOT, output=OUTPUT, **kwargs):
    with execution_lock(root, safe_output(root, output)):
        return _preflight(root, output, **kwargs)


def generate(root=ROOT, output=OUTPUT, **kwargs):
    output = safe_output(root, output)
    clear_stop = kwargs.pop("clear_stop", False)
    callback = kwargs.pop("render_callback", None)
    with execution_lock(root, output):
        if clear_stop:
            (output / "stop_requested").unlink(missing_ok=True)
        try:
            return _generate(root, output, **kwargs)
        finally:
            if callback is not None and (output / "config.json").exists() and (output / "state.json").exists():
                callback(root, output)
