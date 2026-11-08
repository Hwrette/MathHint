"""실제 네트워크 없이 요청 시작 간격·RetryInfo·일일 할당량 중단을 검증한다."""

import unittest

from mathhint_solver.RateLimitedComparison import DailyQuotaStop, GlobalRateLimiter, quota_details


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class QuotaError(Exception):
    code = 429


class RateLimitTests(unittest.TestCase):

    def test_global_request_start_spacing(self):
        clock = FakeClock()
        limiter = GlobalRateLimiter(5, clock=clock, sleeper=clock.sleep)
        starts = []
        for _ in range(3):
            limiter.request(lambda text: starts.append(clock()), "problem")
        self.assertEqual(starts, [0, 5, 10])
        self.assertTrue(all(delay <= 10 for delay in clock.sleeps))

    def test_fractional_message_delay_and_retryinfo_use_largest(self):
        error = QuotaError("Please retry in 54.25s. {'retryDelay': '54s'}")
        self.assertEqual(quota_details(error), {"daily_quota": False, "retry_after_seconds": 54.25})
        clock = FakeClock()
        limiter = GlobalRateLimiter(5, clock=clock, sleeper=clock.sleep)
        with self.assertRaises(QuotaError):
            limiter.request(lambda text: (_ for _ in ()).throw(error), "problem")
        limiter.acquire()
        self.assertEqual(clock(), 55.25)
        self.assertTrue(all(delay <= 10 for delay in clock.sleeps))

    def test_structured_retryinfo_and_http_header(self):
        error = QuotaError("RESOURCE_EXHAUSTED")
        error.details = [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "43s"}]
        self.assertEqual(quota_details(error)["retry_after_seconds"], 43)

    def test_daily_quota_stops_all_further_network_calls(self):
        clock = FakeClock()
        limiter = GlobalRateLimiter(5, clock=clock, sleeper=clock.sleep)
        calls = []
        def request(text):
            calls.append(text)
            raise QuotaError("quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier. Please retry in 12s.")
        with self.assertRaises(QuotaError):
            limiter.request(request, "first")
        with self.assertRaises(DailyQuotaStop):
            limiter.request(request, "second")
        self.assertEqual(calls, ["first"])
        self.assertEqual(clock.sleeps, [])

    def test_minute_quota_is_not_misclassified_as_daily(self):
        details = quota_details(QuotaError("GenerateRequestsPerMinutePerProjectPerModel-FreeTier; limit: 15"))
        self.assertFalse(details["daily_quota"])
        self.assertEqual(details["retry_after_seconds"], 60)

    def test_service_overload_backoff_and_success_reset_preserve_quota_delay(self):
        class Overloaded(Exception):
            code = 503
        clock = FakeClock()
        limiter = GlobalRateLimiter(5, clock=clock, sleeper=clock.sleep)
        waits = []
        for _ in range(4):
            limiter.observe_error(Overloaded("high demand"))
            before = clock()
            limiter.acquire()
            waits.append(clock() - before)
        self.assertEqual(waits, [30, 60, 120, 120])
        limiter.observe_success()
        limiter.observe_error(Overloaded("high demand"))
        before = clock()
        limiter.acquire()
        self.assertEqual(clock() - before, 30)
        limiter.observe_error(QuotaError("Please retry in 54s."))
        limiter.observe_success()
        before = clock()
        limiter.acquire()
        self.assertEqual(clock() - before, 55)

    def test_stop_guard_prevents_unsent_request(self):
        clock = FakeClock()
        limiter = GlobalRateLimiter(5, clock=clock, sleeper=clock.sleep, stop_requested=lambda: True)
        calls = []
        with self.assertRaises(DailyQuotaStop.__bases__[0]):
            limiter.request(lambda text: calls.append(text), "not sent")
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
