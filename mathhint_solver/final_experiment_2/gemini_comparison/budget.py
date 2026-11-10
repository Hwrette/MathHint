"""기존 전역 간격/429 제한기에 실행 시간·로컬 예산·영구 오류 중단만 보완한다."""

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import re
import threading
import time

from ... import CompareGeneration as comparison
from ...RateLimitedComparison import GlobalRateLimiter, quota_details
from .common import DEFAULT_POLICY


class BudgetStop(comparison.RequestedStop):
    def __init__(self, status, reason):
        super().__init__(reason)
        self.status, self.reason = status, reason


def start_timestamps(events):
    values = []
    for event in events:
        if event.get("event") == "request_start":
            values.append(datetime.fromisoformat(event["time"].replace("Z", "+00:00")).timestamp())
    return sorted(values)


class BudgetRateLimiter(GlobalRateLimiter):
    """모든 시도/작업자가 공유하며, 저장된 시작 이력으로 재개 후에도 로컬 한도를 지킨다."""

    def __init__(self, policy=None, *, events=(), stop_requested=None, event_handler=None,
                 clock=time.monotonic, wall_clock=time.time, sleeper=time.sleep):
        self.policy = {**DEFAULT_POLICY, **(policy or {})}
        for field in ("rpm", "rph", "rpd", "max_new_requests", "max_run_seconds", "max_wait_seconds"):
            if self.policy[field] <= 0:
                raise ValueError(f"양수 실행 한도가 필요합니다: {field}")
        self.wall_clock = wall_clock
        self.started = clock()
        self.starts = start_timestamps(events)
        self.new_starts = 0
        self.stop_status, self.stop_reason = None, None
        self.budget_lock = threading.RLock()
        self.output_event = event_handler or (lambda _: None)

        def event(value):
            if value.get("event") == "request_start":
                self.starts.append(self.wall_clock())
                self.new_starts += 1
            self.output_event(value)
        super().__init__(max(self.policy["interval_seconds"], 60 / self.policy["rpm"]),
                         clock=clock, sleeper=sleeper, event_handler=event,
                         stop_requested=stop_requested)

    def halt(self, status, reason):
        self.stop_status, self.stop_reason = status, reason
        raise BudgetStop(status, reason)

    def acquire(self):
        # 잠금 아래 예약까지 마쳐 작업자가 늘어도 예산을 동시에 초과하지 않는다.
        with self.budget_lock:
            while True:
                if self.stop_status:
                    raise BudgetStop(self.stop_status, self.stop_reason)
                if self.stop_requested():
                    self.halt("interrupted", "중단 파일을 확인하여 새 요청을 보내지 않았습니다.")
                if self.daily_exhausted:
                    self.halt("daily_quota_exhausted", "API가 일일 할당량 소진을 보고했습니다. 장시간 대기하지 않습니다.")
                remaining_run = self.policy["max_run_seconds"] - (self.clock() - self.started)
                if remaining_run <= 0:
                    self.halt("interrupted", "허용된 실행 시간에 도달했습니다. 저장된 성공 다음부터 재개하세요.")
                if self.new_starts >= self.policy["max_new_requests"]:
                    self.halt("partial_complete", "이번 실행의 신규 요청 예산에 도달했습니다.")
                now = self.wall_clock()
                self.starts = [value for value in self.starts if value > now - 86400]
                if len(self.starts) >= self.policy["rpd"]:
                    self.halt("daily_quota_exhausted", "로컬 rolling24h 요청 상한에 도달했습니다. 공급자 한도와 구분합니다.")
                waits = [max(0.0, max(self.next_start, self.cooldown_until, self.service_cooldown_until) - self.clock())]
                for window, cap in ((60, self.policy["rpm"]), (3600, self.policy["rph"])):
                    recent = [value for value in self.starts if value > now - window]
                    if len(recent) >= cap:
                        waits.append(max(0.0, recent[-cap] + window - now))
                delay = max(waits)
                if delay > self.policy["max_wait_seconds"] or delay >= remaining_run:
                    self.halt("paused_rate_limit", f"재시도 대기 {delay:.1f}초가 허용 범위를 넘습니다. 성공 기록은 보존했습니다.")
                if delay > 0:
                    self.sleeper(min(delay, 10.0))
                    continue
                return super().acquire()

    def observe_error(self, error):
        super().observe_error(error)
        code = comparison._error_code(error)
        if code in (401, 403, 404):
            self.stop_status, self.stop_reason = "permission_denied", f"인증·접근 또는 요청 모델 오류({code})로 재시도하지 않습니다."
        elif code == 400:
            self.stop_status, self.stop_reason = "partial_complete", "영구적인 요청 설정 오류(400)로 실행을 중단합니다."
        if code in (429, 503):
            # 기존 파서는 숫자 Retry-After/RetryInfo를 처리한다. HTTP 날짜만 추가한다.
            headers = getattr(getattr(error, "response", None), "headers", None)
            delays = []
            fragments = [str(error)]
            for field in ("details", "response_json", "error_details"):
                value = getattr(error, field, None)
                if value is not None:
                    fragments.append(json.dumps(value, default=str))
            if re.search(r"retryDelay|please\s+retry\s+in", " ".join(fragments), flags=re.I):
                delays.append(quota_details(error)["retry_after_seconds"])
            if headers is not None:
                value = headers.get("Retry-After")
                try:
                    delays.append(float(value))
                except (ValueError, TypeError, OverflowError):
                    try:
                        when = parsedate_to_datetime(value)
                        if when.tzinfo is None:
                            when = when.replace(tzinfo=timezone.utc)
                        delays.append(max(0.0, when.timestamp() - self.wall_clock()))
                    except (ValueError, TypeError, OverflowError):
                        pass
            if delays:
                until = self.clock() + max(delays) + 1
                if code == 429:
                    self.cooldown_until = max(self.cooldown_until, until)
                else:
                    self.service_cooldown_until = max(self.service_cooldown_until, until)

    def snapshot(self):
        now = self.wall_clock()
        return {"new_request_starts": self.new_starts,
                "rolling_minute_starts": sum(value > now - 60 for value in self.starts),
                "rolling_hour_starts": sum(value > now - 3600 for value in self.starts),
                "rolling_24h_starts": sum(value > now - 86400 for value in self.starts),
                "status": self.stop_status, "reason": self.stop_reason,
                "daily_quota_reported": self.daily_exhausted,
                "cooldown_remaining_seconds": max(0, self.cooldown_until - self.clock()),
                "policy": self.policy, "provider_quota_confirmation": "not inferred from local caps"}
