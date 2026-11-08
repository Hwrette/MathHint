"""CompareGeneration의 입력/설정을 바꾸지 않고 Gemini 요청 간격을 제한한다.

15 RPM 무료 할당량에서는 작업자 수와 무관하게 기본5초 간격(최대12 RPM)으로 실행한다.
429의 RetryInfo/재시도 메시지를 준수하며 일일 할당량 소진 시 중단한다.
기존 성공 응답은 보존하고 실패한 조건만 다시 요청할 수 있다.
"""

from __future__ import annotations

import json
import math
import os
import re
import threading
import time
from pathlib import Path

if __package__:
    from . import CompareGeneration as comparison
else:
    import CompareGeneration as comparison


# CompareGeneration.py에서 입력을 준비한 뒤 RUN_API를 True로 바꿔 실행한다.
ROOT = Path(__file__).resolve().parents[1]
RUN_ROOT = ROOT / "outputs/model_comparison"
PREDICTIONS = RUN_ROOT / "training/regression_predictions.json"
OUTPUT = RUN_ROOT / "generation_top_tokens"
RUN_API = False
INTERVAL = 5.0
WORKERS = 2
RETRY_ERRORS = True
LIMIT = None  # 처음 한 문항만 실행하려면 1, 전체는 None


class DailyQuotaStop(comparison.RequestedStop):
    """일일 할당량 소진 이후 API 요청을 전송하지 않았음을 나타낸다."""


def quota_details(error: Exception) -> dict:
    """SDK 메시지와 google.rpc.RetryInfo에서 가장 긴 재시도 지연을 읽는다."""
    fragments = [str(error)]
    for name in ("details", "response_json", "error_details"):
        value = getattr(error, name, None)
        if value is not None:
            try:
                fragments.append(json.dumps(value, ensure_ascii=False, default=str))
            except (TypeError, ValueError):
                fragments.append(str(value))
    text = "\n".join(fragments)
    normalized = text.lower()
    daily = bool(re.search(r"per[ _-]*day|requests\s*/\s*day|\bdaily\b|\brpd\b", normalized))
    delays = [float(value) for value in re.findall(
        r"(?:please\s+retry\s+in\s+|retryDelay[\s'\"=:]+)(\d+(?:\.\d+)?)\s*s", text, flags=re.I)]
    # 일부 클라이언트는 HTTP Retry-After 헤더만 제공한다.
    response = getattr(error, "response", None)
    headers = getattr(response, "headers", None)
    if headers is not None:
        try:
            delays.append(float(headers.get("Retry-After")))
        except (TypeError, ValueError):
            pass
    return {"daily_quota": daily, "retry_after_seconds": max(delays) if delays else 60.0}


class GlobalRateLimiter:
    """프로세스 전체 요청 시작 간격과429 냉각 시간을 함께 적용한다."""

    def __init__(self, interval: float = 5.0, *, clock=time.monotonic, sleeper=time.sleep,
                 initial_cooldown: float = 0.0, event_handler=None, stop_requested=None):
        if not math.isfinite(interval) or interval < 4.1:
            raise ValueError("15RPM보다 여유 있게 실행하도록 요청 간격은4.1초 이상이어야 합니다.")
        self.interval, self.clock, self.sleeper = interval, clock, sleeper
        self.lock = threading.Lock()
        self.next_start = clock() + max(0.0, initial_cooldown)
        self.cooldown_until = self.next_start
        self.daily_exhausted = False
        self.service_failures = 0
        self.service_cooldown_until = 0.0
        self.stop_requested = stop_requested or (lambda: False)
        self.event_handler = event_handler or (lambda event: None)

    def acquire(self) -> None:
        while True:
            if self.stop_requested():
                raise comparison.RequestedStop("중단 요청 파일을 확인하여 새 API 요청을 전송하지 않았습니다.")
            with self.lock:
                if self.daily_exhausted:
                    raise DailyQuotaStop("일일 할당량이 소진되어 추가 API 요청을 전송하지 않았습니다.")
                now = self.clock()
                remaining = max(self.next_start, self.cooldown_until, self.service_cooldown_until) - now
                if remaining <= 0:
                    self.next_start = now + self.interval
                    self.event_handler({"event": "request_start", "time": comparison.utc_now()})
                    return
            # 배경 실행에서도 취소·상태 확인이 가능하도록 짧은 단위로 기다린다.
            self.sleeper(min(remaining, 10.0))

    def observe_error(self, error: Exception) -> None:
        code = comparison._error_code(error)
        if code == 503:
            with self.lock:
                self.service_failures += 1
                delay = min(30 * 2 ** min(self.service_failures - 1, 2), 120)
                self.service_cooldown_until = max(self.service_cooldown_until, self.clock() + delay)
                self.event_handler({"event": "service_overloaded", "time": comparison.utc_now(),
                                    "consecutive_503": self.service_failures, "backoff_seconds": delay})
            return
        if code != 429:
            return
        details = quota_details(error)
        with self.lock:
            self.daily_exhausted = details["daily_quota"]
            self.cooldown_until = max(self.cooldown_until, self.clock() + details["retry_after_seconds"] + 1.0)
            self.event_handler({"event": "quota_error", "time": comparison.utc_now(), **details})

    def observe_success(self) -> None:
        with self.lock:
            if self.service_failures:
                self.event_handler({"event": "service_recovered", "time": comparison.utc_now()})
            self.service_failures = 0
            self.service_cooldown_until = 0.0

    def request(self, function, text: str):
        self.acquire()
        try:
            response = function(text)
            self.observe_success()
            return response
        except Exception as error:
            self.observe_error(error)
            raise


def main() -> None:
    if not RUN_API:
        print("현재는 API를 호출하지 않습니다. 입력을 확인한 뒤 RUN_API = True로 바꾸세요.")
        return

    # 1. 준비할 때 저장한 설정과 지금의 입력이 같은지 확인
    project, output = ROOT.resolve(), OUTPUT.resolve()
    manifest = comparison.read_json(output / "config.json")
    frozen = manifest["config"]
    config, plan = comparison.prepare_plan(project, PREDICTIONS.resolve(), model=frozen["model"],
        thinking_level=frozen["thinking_level"], temperature=frozen["temperature"],
        max_output_tokens=frozen["max_output_tokens"], system_instruction=frozen["system_instruction"],
        attempts=frozen["max_attempts"], hint_mode=frozen.get("hint_mode", "full_vector"),
        hint_top_k=frozen.get("hint_top_k", 20))
    # 원래 runner/grader와 모든 입력의 해시가 그대로인 경우만 같은 실행에 재개한다.
    config_id = comparison.initialize_run(output, config, plan)
    from dotenv import load_dotenv
    load_dotenv(project / ".env", override=False)
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise SystemExit("환경변수 또는 로컬 .env에 GEMINI_API_KEY를 설정하세요.")
    # 2. 실행별 사용량·오류·요청 간격 기록
    execution_id = comparison.utc_now().replace(":", "").replace(".", "_")
    execution_dir = output / "execution_runs"
    execution_dir.mkdir(exist_ok=True)
    execution_path = execution_dir / (execution_id + ".json")
    events_path = execution_dir / (execution_id + "_rate_events.jsonl")
    execution = {"execution_id": execution_id, "started_at": comparison.utc_now(),
                 "config_id": config_id, "wrapper_sha256": comparison.file_hash(Path(__file__)),
                 "rate_policy": {"minimum_start_interval_seconds": INTERVAL,
                                 "initial_cooldown_seconds": 0.0,
                                 "honor_429_retry_after": True, "cooldown_safety_seconds": 1,
                                 "workers": WORKERS, "daily_quota_abort": True,
                                 "service_503_backoff_seconds": [30, 60, 120], "reset_backoff_on_success": True},
                 "retry_errors": RETRY_ERRORS, "limit": LIMIT, "status": "running"}
    comparison.write_json(execution_path, execution)

    def event_handler(event):
        with events_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + "\n")

    stop_file = output / "stop_requested"
    execution["stop_file"] = str(stop_file)
    limiter = GlobalRateLimiter(INTERVAL, initial_cooldown=0.0, event_handler=event_handler,
                                stop_requested=stop_file.exists)
    original = comparison.generate_one
    network_request = comparison.make_request(config, key)

    def limited_generation(item, current_config, current_id, api_key):
        # 이전 일일429 결과를 원래 runner가 저장한 뒤, 다음 작업을 전송하기 전에 중단한다.
        if limiter.daily_exhausted:
            raise DailyQuotaStop("일일 할당량 소진으로 실행을 중단했습니다. 다음 날 같은 실행을 재개하세요.")
        if stop_file.exists():
            raise comparison.RequestedStop("중단 요청을 확인하여 다음 문항의 API 요청을 전송하지 않았습니다.")
        result = original(item, current_config, current_id, api_key,
                          request_function=lambda text: limiter.request(network_request, text))
        result["rate_limited_execution_id"] = execution_id
        if limiter.daily_exhausted and (result["status"].startswith("stopped_") or
                                       any(attempt.get("code") == 429 for attempt in result["attempts"])):
            result["daily_quota_exhausted"] = True
            result["status"] = "api_error"
            # 건너뛴 재시도 예외가 실제429 정보를 가리지 않도록 대표 오류를 보존한다.
            actual_quota_error = next((attempt for attempt in result["attempts"] if attempt.get("code") == 429), None)
            if actual_quota_error:
                result["error"] = {field: actual_quota_error.get(field) for field in ("code", "message")}
                result["error"]["type"] = actual_quota_error.get("error_type")
            for attempt in result["attempts"]:
                if attempt.get("error_type") == "DailyQuotaStop" or attempt.get("status") == "skipped":
                    attempt["request_skipped"] = True
        return result

    # 3. 같은 입력을 속도 제한과 함께 실행하고 완료한 응답부터 저장
    try:
        comparison.run_requests(output, config, plan, api_key=key, limit=LIMIT,
                                workers=WORKERS, retry_errors=RETRY_ERRORS, stop_file=stop_file,
                                generate_function=limited_generation)
        execution["status"] = "completed"
    except comparison.RequestedStop as error:
        execution["status"] = "daily_quota_exhausted" if limiter.daily_exhausted else "stopped_gracefully"
        execution["message"] = str(error)
        print(json.dumps({"status": execution["status"], "message": str(error)}, ensure_ascii=False), flush=True)
    except BaseException as error:
        execution["status"] = "daily_quota_exhausted" if limiter.daily_exhausted else "interrupted_or_failed"
        execution["error_type"] = type(error).__name__
        execution["error_message"] = str(error).replace(key, "[REDACTED]")
        raise
    finally:
        execution["completed_at"] = comparison.utc_now()
        comparison.write_json(execution_path, execution)


if __name__ == "__main__":
    main()
