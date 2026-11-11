"""실제 요청 로그의 로컬 속도 검증을 작은 경계 사례로 확인한다. API·결과 파일 접근 없음."""

from datetime import datetime, timezone
import unittest

from mathhint_solver.final_experiment_2.gemini_full265.verify import saved_request_rate_checks


def event(seconds, label):
    return {"event": "request_start", "time": datetime.fromtimestamp(100000+seconds, timezone.utc).isoformat(),
            "execution_id": label}


class SavedGenerationRateTests(unittest.TestCase):
    def test_old_five_second_period_is_not_rejudged_and_minute_boundary_is_excluded(self):
        old = [event(t, "old"+str(t)) for t in range(0, 30, 5)]
        new = [event(60, "new60"), event(70, "new70")]
        metadata_get = {"event": "models.get", "time": event(65, "ignored")["time"]}
        result = saved_request_rate_checks(old+new+[metadata_get], new,
            {"interval_seconds": 10, "rpm": 6, "rph": 360, "rpd": 1400})
        self.assertTrue(result["passed"])
        self.assertEqual(result["new_request_start_count"], 2)
        self.assertEqual(result["shared_request_start_count"], 8)
        self.assertEqual(result["minimum_new_start_interval_seconds"], 10)
        self.assertEqual(result["maximum_rolling_start_counts_at_new_attempts"]["60"], 6)
        self.assertFalse(result["provider_limits_confirmed"])

    def test_interval_accepts_small_clock_roundoff_but_detects_actual_early_request(self):
        for when, expected in ((9.995, True), (9.98, False)):
            with self.subTest(when=when):
                new = [event(when, "new")]
                result = saved_request_rate_checks([event(0, "old")]+new, new,
                    {"interval_seconds": 10, "rpm": 6, "rph": 360, "rpd": 1400})
                self.assertEqual(result["passed"], expected)

    def test_hour_and_day_windows_exclude_exact_lower_boundary(self):
        for when, caps, window in ((3600, {"rpm": 100, "rph": 2, "rpd": 100}, "3600"),
                                  (86400, {"rpm": 100, "rph": 100, "rpd": 2}, "86400")):
            with self.subTest(window=window):
                new = [event(when, "new")]
                result = saved_request_rate_checks([event(0, "old0"), event(1, "old1")]+new,
                    new, {"interval_seconds": 10, **caps})
                self.assertTrue(result["passed"])
                self.assertEqual(result["maximum_rolling_start_counts_at_new_attempts"][window], 2)

    def test_rolling_excess_and_missing_or_duplicate_new_records_are_rejected(self):
        for cap, seconds, window in (("rpm", (0, 10, 20), "60"),
                                     ("rph", (0, 100, 200), "3600"),
                                     ("rpd", (0, 100, 200), "86400")):
            with self.subTest(cap=cap):
                shared = [event(t, str(t)) for t in seconds]
                result = saved_request_rate_checks(shared, shared[1:],
                    {"interval_seconds": 10, "rpm": 1000, "rph": 1000, "rpd": 1000, cap: 2})
                self.assertFalse(result["passed"])
                self.assertEqual(result["maximum_rolling_start_counts_at_new_attempts"][window], 3)
        new = [event(10, "new")]
        policy = {"interval_seconds": 10, "rpm": 6, "rph": 360, "rpd": 1400}
        self.assertFalse(saved_request_rate_checks([], new, policy)["passed"])
        self.assertFalse(saved_request_rate_checks(new, new+new, policy)["passed"])

    def test_simultaneous_old_new_starts_and_bad_timestamps_cannot_appear_as_zero_work(self):
        policy = {"interval_seconds": 10, "rpm": 6, "rph": 360, "rpd": 1400}
        for label in ("aaa", "zzz"):
            new = [event(10, label)]
            result = saved_request_rate_checks([event(10, "other")]+new, new, policy)
            self.assertFalse(result["passed"])
            self.assertEqual(result["minimum_new_start_interval_seconds"], 0)
        bad = [{"event": "request_start", "time": "not-a-timestamp"}]
        result = saved_request_rate_checks(bad, bad, policy)
        self.assertFalse(result["passed"])
        self.assertEqual(result["new_request_start_count"], 1)
        self.assertEqual(result["valid_new_request_start_count"], 0)
        self.assertIsNone(result["minimum_new_start_interval_seconds"])


if __name__ == "__main__":
    unittest.main()
