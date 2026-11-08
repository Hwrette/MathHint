"""ThreeWayGeneration에서 재사용하는 Gemini 요청 속도·할당량 제한기.

15 RPM 무료 할당량에서는 작업자 수와 무관하게 기본5초 간격(최대12 RPM)으로 실행한다.
429의 RetryInfo/재시도 메시지를 준수하며 일일 할당량 소진 시 중단한다.
기존 성공 응답은 보존하고 실패한 조건만 다시 요청할 수 있다.
"""

from __future__ import annotations

import json
import math
import re
import threading
import time

if __package__:
    from . import CompareGeneration as comparison
else:
    import CompareGeneration as comparison


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
