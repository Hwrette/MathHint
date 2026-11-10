"""확정 모델의 감사된 요청만 실행한다. 기존 SDK·채점·재시도·즉시 저장을 재사용한다."""

from datetime import datetime, timezone
import os
from pathlib import Path
import time

from ... import CompareGeneration as comparison
from .budget import BudgetRateLimiter
from .common import (ROOT, OUTPUT, DEFAULT_POLICY, METHODS, append_jsonl, read_json,
                     read_jsonl, write_json, safe_output, load_saved, execution_lock)
from .plan import prepare_plan, initialize, dry_run, reuse_existing, MODEL


def load_data(root):
    from mathhint_learning.final_experiment_2.solution_data.prepare import load_data as load
    return load(root, include_test=True)


def state_record(output, config, plan, *, status, reason=None, limiter=None):
    output = Path(output)
    records = comparison.load_completed(output, comparison.digest(config))
    successes = [row for row in records.values() if row["status"] == "success"]
    failed = [row for row in records.values() if row["status"] != "success"]
    pending = [{"id": row["id"], "condition": row["condition"], "method": row["method"],
                "split": row["split"], "request_sha256": row["request_sha256"],
                "last_status": records.get((row["id"], row["method"]), {}).get("status", "not_executed")}
               for row in plan if records.get((row["id"], row["method"]), {}).get("status") != "success"]
    if not pending:
        status, reason = "completed", "모든 조건의 성공 응답이 저장되었습니다."
    result = {"status": status, "reason": reason, "updated_at": comparison.utc_now(),
        "config_id": comparison.digest(config), "split": config["split"],
        "expected_requests": len(plan), "successful_requests": len(successes),
        "failed_requests": len(failed), "saved_responses": len(records),
        "response_log_entries": len(read_jsonl(output / "responses.jsonl")),
        "pending_count": len(pending), "pending_requests": pending,
        "reused_successes": sum(row.get("response_origin") == "reused_exact_request" for row in successes),
        "new_successes": sum(row.get("response_origin") == "new_api_call" for row in successes),
        "safe_to_resume": bool(pending) and status not in ("missing_api_key", "permission_denied"),
        "resume_command": "python -m mathhint_solver.final_experiment_2.gemini_comparison generate"
                          + (" --split train" if config["split"] == "train" else "")
                          + (" --clear-stop" if (output / "stop_requested").exists() else ""),
        "resume_prerequisites": "공급자 일일 할당량 초기화를 실제로 확인한 후 재실행" if status == "daily_quota_exhausted" else
            "키/접근 권한 또는 동일 요청 모델 지원을 복구한 후 재실행" if status in ("missing_api_key", "permission_denied") else
            "기록된 재시도 대기 및 실행 제한을 확인한 후 미완료 요청만 재실행",
        "provider_daily_reset_time": None,
        "resume_note": "설정·입력·성공 응답 해시를 다시 확인하고 미완료 요청만 실행한다. 환경 종료 후 자동 예약은 설정하지 않았다.",
        "training_extension": {"executed": False, "pending_requests": 185 * 4,
             "allowed": False, "reason": "test80 검증 후 현재 호출 예산이 확인된 경우에만 별도 확장한다. 현재 공급자 잔여 예산 미확인."}}
    if limiter is not None:
        result["limiter"] = limiter.snapshot()
    write_json(output / "state.json", result)
    return result


def _load_policy(output, supplied=None):
    path = Path(output) / "policy.json"
    policy = {**DEFAULT_POLICY, **(read_json(path) if path.exists() else {}), **(supplied or {})}
    if policy["workers"] != 1:
        raise ValueError("이번 예산 미확인 실행은 작업자1개로 제한합니다. 전역 제한기는 모든 재시도에 공유됩니다.")
    if not policy.get("provider_limits_confirmed") and (policy["interval_seconds"] < 10 or policy["rpm"] > 6):
        raise ValueError("현재 공급자 한도가 미확인이므로10초/6RPM보다 높은 속도를 임의로 설정하지 않습니다.")
    if not path.exists():
        write_json(path, policy)
    return policy


def _extension_allowed(root, data, policy):
    test = Path(root) / "results/final_experiment_2/gemini_comparison"
    status = read_json(test / "state.json") if (test / "state.json").exists() else {}
    validation = read_json(test / "validation.json") if (test / "validation.json").exists() else {}
    if status.get("status") != "completed" or not (validation.get("complete") is True or validation.get("failed") == 0):
        raise ValueError("추가185문항은 test80 네 조건 완료 및 검증 후에만 실행합니다.")
    quota = policy.get("quota_confirmation") or {}
    if (policy.get("provider_limits_confirmed") is not True or not quota.get("source")
            or int(quota.get("remaining_daily_requests", 0)) < len(data["ids"]["train"]) * 4):
        raise ValueError("현재 공급자 호출 예산이 충분하다는 확인 자료가 없어185문항을 확장하지 않습니다.")


def prepare(root=ROOT, output=OUTPUT, *, split="test", data=None):
    root = Path(root).resolve()
    base = safe_output(root, output)
    data = data or load_data(root)
    policy = _load_policy(base)
    if split == "train":
        _extension_allowed(root, data, policy)
    output = base / "extension_train185" if split == "train" else base
    config, plan = prepare_plan(root, data, split=split)
    initialize(output, config, plan)
    audit = dry_run(root, output, config, plan)
    reuse = reuse_existing(root, output, config, plan)
    state = state_record(output, config, plan, status="partial_complete", reason="모델·요청 감사 완료. 현재 API 환경 확인 전입니다.")
    return config, plan, {"dry_run": audit, "reuse": reuse, "state": state}, output, policy


def _preflight(root=ROOT, output=OUTPUT, *, split="test", offline=False, data=None,
              client_factory=None, api_key=None):
    """두 모델 확정 이후 모델GET만 수행한다. 생성 호출은 여기서 실행하지 않는다."""
    config, plan, preparation, output, policy = prepare(root, output, split=split, data=data)
    key = api_key if api_key is not None else os.environ.get("GEMINI_API_KEY")
    info = {"checked_at": comparison.utc_now(), "config_id": comparison.digest(config),
        "requested_model": MODEL, "generation_calls": 0, "non_generation_network_calls": 0,
        "expected_requests": len(plan), "successful_saved": preparation["state"]["successful_requests"],
        "new_requests_needed": preparation["state"]["pending_count"], "preparation": preparation,
        "provider_rate_limits": {"requests_per_minute": None, "requests_per_hour": None,
                                 "requests_per_day": None, "tokens_per_minute": None,
                                 "remaining_daily_requests": None},
        "quota_observability": "models.get exposes model capabilities/token ceilings, not this project's current rate or remaining daily quota; no privileged quota credential was available",
        "local_execution_policy": policy, "api_key_present": bool(key), "api_readiness": "not_checked",
        "legacy_interval_seconds": 5, "applied_interval_seconds": policy["interval_seconds"],
        "legacy_workers": 2, "applied_workers": policy["workers"],
        "legacy_settings_match": True, "automatic_extension_allowed": False}
    if offline:
        info["api_readiness"] = "offline_audit_only"
    elif (output / "stop_requested").exists():
        info["api_readiness"] = "interrupted"
        state_record(output, config, plan, status="interrupted", reason="중단 파일이 있어 모델 확인 API도 보내지 않았습니다.")
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
    value = read_json(path)
    try:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(value["checked_at"])).total_seconds()
    except (KeyError, ValueError, TypeError):
        return False
    return value.get("config_id") == comparison.digest(config) and value.get("api_readiness") == "ready" and age < 1800


def transport_request(config, api_key, *, http_timeout_ms, request_observer=None,
                      error_observer=None, client_factory=None):
    """SDK 본문은 공통 함수를 재사용하고 HTTP 대기만 늘린다. timeout만 유한 재시도 대상으로 정규화한다."""
    import httpx
    from google import genai

    if type(http_timeout_ms) is not int or http_timeout_ms <= 0:
        raise ValueError("HTTP 제한 시간은 양의 정수 밀리초여야 합니다.")
    factory = client_factory or genai.Client

    def with_timeout(**arguments):
        # 기존 make_request의 SDK 1회 시도 정책과 나머지 HttpOptions는 유지한다.
        options = arguments["http_options"].model_copy(update={"timeout": http_timeout_ms})
        return factory(**{**arguments, "http_options": options})

    request = comparison.make_request(config, api_key, request_observer=request_observer,
                                      client_factory=with_timeout)

    def invoke(text):
        try:
            return request(text)
        except httpx.TimeoutException as error:
            message = str(error).replace(api_key, "[REDACTED]") if api_key else str(error)
            detail = {"original_error_type": type(error).__name__, "normalized_error_type": "TimeoutError",
                      "message": message, "http_timeout_ms": http_timeout_ms,
                      "observed_at": comparison.utc_now()}
            if error_observer is not None:
                error_observer(detail)
            # 기존 generate_one은 builtin TimeoutError를 max_attempts 범위에서만 재시도한다.
            raise TimeoutError(f"{type(error).__name__}: {message}") from error
    return invoke


def _generate(root=ROOT, output=OUTPUT, *, split="test", policy=None, request_function=None,
             api_key=None, data=None, render_callback=None):
    root = Path(root).resolve()
    config, plan, preparation, output, saved_policy = prepare(root, output, split=split, data=data)
    policy = _load_policy(safe_output(root), {**saved_policy, **(policy or {})})
    key = api_key if api_key is not None else os.environ.get("GEMINI_API_KEY")
    if not preparation["state"]["pending_requests"]:
        return state_record(output, config, plan, status="completed")
    if request_function is None:
        if not _preflight_fresh(output, config):
            info = _preflight(root, safe_output(root), split=split, data=data, api_key=key)
            if info["api_readiness"] != "ready":
                return read_json(output / "state.json")
        if not key:
            return state_record(output, config, plan, status="missing_api_key", reason="GEMINI_API_KEY가 없습니다.")
    config_id = comparison.digest(config)
    execution_id = comparison.utc_now().replace(":", "").replace(".", "_")
    path = output / "execution_runs" / (execution_id + ".json")
    context = {"id": None, "condition": None, "split": split}
    events_path = safe_output(root) / "execution_runs/request_events.jsonl"
    execution = {"execution_id": execution_id, "config_id": config_id, "started_at": comparison.utc_now(),
        "status": "running", "split": split, "policy": policy,
        "transport": {"http_timeout_ms": policy["http_timeout_ms"], "sdk_attempts": 1,
                      "timeout_error_policy": "httpx.TimeoutException to chained builtin TimeoutError; existing bounded max_attempts"},
        "preexisting_successes": preparation["state"]["successful_requests"],
        "runner_sha256": comparison.file_hash(Path(__file__)), "sdk_request_capture": "immediately before generate_content"}
    write_json(path, execution)

    def event(value):
        append_jsonl(events_path, {**value, "execution_id": execution_id, **context})
    limiter = BudgetRateLimiter(policy, events=read_jsonl(events_path), event_handler=event,
                               stop_requested=(output / "stop_requested").exists)
    final_status, reason, consecutive_failures = "partial_complete", "미완료 요청이 남아 있습니다.", 0
    try:
        completed = comparison.load_completed(output, config_id)
        for item in plan:
            key_tuple = item["id"], item["method"]
            if completed.get(key_tuple, {}).get("status") == "success":
                continue
            context.update(id=item["id"], condition=item["condition"])
            expected = read_json(output / "prompt_audit/requests" / item["id"] / (item["condition"] + ".json"))
            captures = []
            transport_errors = []

            def observe(snapshot):
                if snapshot != expected["sdk_request"] or comparison.digest(snapshot) != item["request_sha256"]:
                    raise ValueError("실제 전송 직전의 SDK 인자가 감사 기록과 다릅니다.")
                captures.append(comparison.digest(snapshot))
                append_jsonl(output / "prompt_audit/sdk_calls.jsonl", {"id": item["id"],
                    "condition": item["condition"], "execution_id": execution_id,
                    "captured_at": comparison.utc_now(), "sdk_request": snapshot,
                    "request_sha256": captures[-1], "matches_saved_prompt": True,
                    "transport": {"http_timeout_ms": policy["http_timeout_ms"], "sdk_attempts": 1},
                    "capture": "immediately_before_sdk_generate_content"})
            request = request_function or transport_request(config, key,
                http_timeout_ms=policy["http_timeout_ms"], request_observer=observe,
                error_observer=transport_errors.append)
            row = comparison.generate_one(item, config, config_id, key or "", request_function=lambda text: limiter.request(request, text))
            row.update(execution_id=execution_id, sdk_request_sha256=item["request_sha256"],
                transport={"http_timeout_ms": policy["http_timeout_ms"], "sdk_attempts": 1},
                transport_errors=transport_errors,
                sdk_boundary_captured_attempts=len(captures), sdk_boundary_capture_expected=request_function is None,
                solution_review={"status": "pending_review", "mathematical_validity": None,
                                 "reason": "최종 답 채점과 별개이며 수학적 타당성을 자동 확정하지 않았다."})
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
            state_record(output, config, plan, status="partial_complete", reason="성공 응답은 즉시 저장했고 남은 요청을 순서대로 진행합니다.", limiter=limiter)
            print(f"{item['id']} {item['condition']}: {row['status']} · 저장 성공 {sum(r['status']=='success' for r in completed.values())}/{len(plan)}", flush=True)
            if limiter.daily_exhausted or limiter.stop_status:
                final_status = "daily_quota_exhausted" if limiter.daily_exhausted else limiter.stop_status
                reason = limiter.stop_reason or "공급자 일일 할당량 소진을 확인했습니다."
                break
            if consecutive_failures >= 3:
                final_status, reason = "partial_complete", "세 요청이 연속으로 실패하여 불필요한 비용을 막고 중단했습니다."
                break
        else:
            final_status, reason = "completed", "모든 문항·조건의 성공 응답을 저장했습니다."
    except KeyboardInterrupt:
        final_status, reason = "interrupted", "사용자 또는 실행 환경의 중단 신호를 확인했습니다."
    except comparison.RequestedStop as error:
        final_status, reason = getattr(error, "status", "interrupted"), str(error)
    except BaseException as error:
        final_status = "interrupted"
        reason = str(error).replace(key, "[REDACTED]") if key else str(error)
        execution["error_type"] = type(error).__name__
        raise
    finally:
        state = state_record(output, config, plan, status=final_status, reason=reason, limiter=limiter)
        execution.update(completed_at=comparison.utc_now(), status=state["status"],
            successful_requests=state["successful_requests"], failed_requests=state["failed_requests"],
            pending_count=state["pending_count"], pending_requests=state["pending_requests"],
            new_request_starts=limiter.new_starts, limiter=limiter.snapshot(), reason=reason)
        write_json(path, execution)
        if render_callback is not None:
            render_callback(root, output)
    return state


def preflight(root=ROOT, output=OUTPUT, **kwargs):
    with execution_lock(safe_output(root, output)):
        return _preflight(root, output, **kwargs)


def generate(root=ROOT, output=OUTPUT, **kwargs):
    base = safe_output(root, output)
    target = base / "extension_train185" if kwargs.get("split") == "train" else base
    clear_stop = kwargs.pop("clear_stop", False)
    callback = kwargs.pop("render_callback", None)
    with execution_lock(base):
        if clear_stop:
            (target / "stop_requested").unlink(missing_ok=True)
        try:
            return _generate(root, output, **kwargs)
        finally:
            if callback is not None and (target / "config.json").exists() and (target / "state.json").exists():
                callback(root, target)
