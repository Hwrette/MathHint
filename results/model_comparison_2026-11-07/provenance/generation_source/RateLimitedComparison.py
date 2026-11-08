"""CompareGeneration의 입력/설정을 바꾸지 않고 Gemini 요청 간격을 제한한다.

15 RPM 무료 할당량에서는 작업자 수와 무관하게 기본5초 간격(최대12 RPM)으로 실행한다.
429의 RetryInfo/재시도 메시지를 준수하며 일일 할당량 소진 시 중단한다.
기존 성공 응답은 그대로 두고 --retry-errors로 실패 조건만 다시 요청한다.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import threading
import time
from pathlib import Path

from . import CompareGeneration as comparison


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


def sdk_request(config: dict, api_key: str):
    """원래 비교 코드와 동일한 Gemini 요청 설정을 사용한다."""
    from google import genai
    from google.genai import types

    def request(text):
        with genai.Client(api_key=api_key, http_options=types.HttpOptions(
                timeout=90_000, retry_options=types.HttpRetryOptions(attempts=1))) as client:
            return client.models.generate_content(model=config["model"], contents=text,
                config=types.GenerateContentConfig(
                    system_instruction=config["system_instruction"],
                    temperature=config["temperature"], max_output_tokens=config["max_output_tokens"],
                    thinking_config=types.ThinkingConfig(thinking_level=config["thinking_level"])))
    return request


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument("--initial-cooldown", type=float, default=0.0)
    parser.add_argument("--retry-errors", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--workers", type=int, choices=(1, 2, 3), default=2)
    parser.add_argument("--stop-file", type=Path, help="기본값: 출력 폴더/stop_requested")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit은1 이상이어야 합니다.")
    project, output = args.project.resolve(), args.output.resolve()
    manifest = comparison.read_json(output / "config.json")
    frozen = manifest["config"]
    config, plan = comparison.prepare_plan(project, args.predictions.resolve(), model=frozen["model"],
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
        parser.error("환경변수 또는 로컬 .env에 GEMINI_API_KEY를 설정하세요.")
    execution_id = comparison.utc_now().replace(":", "").replace(".", "_")
    execution_dir = output / "execution_runs"
    execution_dir.mkdir(exist_ok=True)
    execution_path = execution_dir / (execution_id + ".json")
    events_path = execution_dir / (execution_id + "_rate_events.jsonl")
    execution = {"execution_id": execution_id, "started_at": comparison.utc_now(),
                 "config_id": config_id, "wrapper_sha256": comparison.file_hash(Path(__file__)),
                 "rate_policy": {"minimum_start_interval_seconds": args.interval,
                                 "initial_cooldown_seconds": args.initial_cooldown,
                                 "honor_429_retry_after": True, "cooldown_safety_seconds": 1,
                                 "workers": args.workers, "daily_quota_abort": True,
                                 "service_503_backoff_seconds": [30, 60, 120], "reset_backoff_on_success": True},
                 "retry_errors": args.retry_errors, "limit": args.limit, "status": "running"}
    comparison.write_json(execution_path, execution)

    def event_handler(event):
        with events_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + "\n")

    stop_file = args.stop_file.resolve() if args.stop_file else output / "stop_requested"
    execution["stop_file"] = str(stop_file)
    limiter = GlobalRateLimiter(args.interval, initial_cooldown=args.initial_cooldown, event_handler=event_handler,
                                stop_requested=stop_file.exists)
    original = comparison.generate_one
    network_request = sdk_request(config, key)

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

    comparison.generate_one = limited_generation
    try:
        comparison.run_requests(output, config, plan, api_key=key, limit=args.limit,
                                workers=args.workers, retry_errors=args.retry_errors, stop_file=stop_file)
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
        comparison.generate_one = original
        execution["completed_at"] = comparison.utc_now()
        comparison.write_json(execution_path, execution)


if __name__ == "__main__":
    main()
