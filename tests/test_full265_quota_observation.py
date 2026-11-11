"""저장된 실제 한도 근거의 안전한 표시와 재개 대기 상한을 API 없이 검사한다."""

from copy import deepcopy
from datetime import datetime
from pathlib import Path
import tempfile
import unittest

from mathhint_solver import CompareGeneration as comparison
from mathhint_solver.final_experiment_2.gemini_comparison.budget import BudgetRateLimiter, BudgetStop
from mathhint_solver.final_experiment_2.gemini_full265 import common, run


def fixture():
    payload = {"error": {"code": 429, "details": [
        {"@type": "type.googleapis.com/google.rpc.QuotaFailure", "violations": [{
            "quotaMetric": "generativelanguage.googleapis.com/generate_content_free_tier_requests",
            "quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier", "quotaValue": "500",
            "quotaDimensions": {"location": "global", "model": "gemini-3.1-flash-lite"},
            "description": "Generate content requests per day limit exceeded on Free Tier."}]},
        {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "26943s"}]}}
    context = {"execution_id": "run", "id": "q", "condition": "D"}
    error = {"code": 429, "type": "ClientError", "message": "429 RESOURCE_EXHAUSTED. " + repr(payload)}
    row = {**context, "status": "stopped_after_attempt", "error": error, "request_sha256": "request",
        "attempts": [{"attempt": 1, "status": "error", "error_type": "ClientError", "code": 429,
                      "message": error["message"], "started_at": "2026-11-11T00:30:50+00:00"},
                     {"attempt": 2, "status": "skipped", "message": "daily guard skipped", "request_skipped": True}]}
    events = [{**context, "event": "quota_error", "time": "2026-11-11T00:30:56.860528+00:00",
        "daily_quota": True, "retry_after_seconds": 26943.0},
        {**context, "event": "cooldown_updated", "code": 429, "time": "2026-11-11T00:30:56.861436+00:00",
         "cooldown_until": "2026-11-11T08:00:00.861426+00:00"}]
    return row, events


class Full265QuotaObservationTests(unittest.TestCase):
    def test_saved_sdk_repr_is_parsed_and_linked_without_inventing_a_reset_or_complete_quota(self):
        row, events = fixture()
        before = deepcopy((row, events))
        result = run.provider_quota_observation([row], events)
        self.assertEqual(result["quota_violations"][0]["quota_value"], 500)
        self.assertTrue(result["daily_quota"])
        self.assertEqual(result["model"], "gemini-3.1-flash-lite")
        self.assertEqual(result["retry_info_delay_seconds"], 26943)
        self.assertEqual(result["earliest_retry_from_response"], "2026-11-11T07:59:59.860528+00:00")
        self.assertEqual(result["recorded_cooldown_until"], "2026-11-11T08:00:00.861426+00:00")
        self.assertFalse(result["confirmed_daily_reset"])
        self.assertFalse(result["provider_full_limits_confirmed"])
        source = result["source"]
        self.assertEqual(source["response_record_sha256"], comparison.digest(row))
        self.assertEqual(source["attempt_index"], 1)
        self.assertEqual(source["attempt_sha256"], comparison.digest(row["attempts"][0]))
        self.assertEqual(source["quota_event_sha256"], comparison.digest(events[0]))
        self.assertEqual(source["cooldown_event_sha256"], comparison.digest(events[1]))
        self.assertEqual((row, events), before)

    def test_no_recorded_violation_never_becomes_the_observed_500_value_and_success_preserves_history(self):
        row, events = fixture()
        result = run.provider_quota_observation([row, {"status": "success", "error": None, "attempts": [{"error": None}]}], events)
        self.assertEqual(result["source"]["id"], "q")
        row["error"]["message"] = "429 RESOURCE_EXHAUSTED"
        row["attempts"][0]["message"] = "429 RESOURCE_EXHAUSTED"
        result = run.provider_quota_observation([row], [])
        self.assertEqual(result["quota_violations"], [])
        self.assertIsNone(result["retry_info_delay_seconds"])
        self.assertIsNone(result["earliest_retry_from_response"])
        self.assertIsNone(run.provider_quota_observation([{"status": "success", "error": None}], []))

    def test_refresh_only_adds_observation_and_preserves_status_counts_limiter_and_source_files(self):
        row, events = fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); output = common.safe_output(root)
            state = {"status": "daily_quota_exhausted", "successful_requests": 515, "pending_count": 545,
                "reason": "original", "updated_at": "original-time", "limiter": {"original_snapshot": True}}
            common.write_json(output / "state.json", state)
            common.append_jsonl(output / "responses.jsonl", row)
            for event in events:
                common.append_jsonl(output / "execution_runs/request_events.jsonl", event)
            originals = {path: path.read_bytes() for path in output.rglob("*") if path.is_file() and path.name != "state.json"}
            result = run.refresh_quota_observation(root, output)
            self.assertEqual({key: value for key, value in result.items() if key != "provider_quota_observation"}, state)
            self.assertEqual(result["provider_quota_observation"]["quota_violations"][0]["quota_value"], 500)
            self.assertEqual(originals, {path: path.read_bytes() for path in originals})
            self.assertFalse((output / ".execution.lock").exists())

    def test_retry_after_seven_hours_is_restored_and_stops_without_sleep_or_request_start(self):
        _, events = fixture()
        wall_now = datetime.fromisoformat("2026-11-11T00:31:00+00:00").timestamp()
        recorded, sleeps = [], []
        limiter = BudgetRateLimiter(common.DEFAULT_POLICY, events=events, clock=lambda: 0,
            wall_clock=lambda: wall_now, sleeper=sleeps.append, event_handler=recorded.append)
        with self.assertRaises(BudgetStop) as raised:
            limiter.acquire()
        self.assertEqual(raised.exception.status, "paused_rate_limit")
        self.assertEqual(limiter.new_starts, 0)
        self.assertEqual(sleeps, [])
        self.assertFalse(any(event.get("event") == "request_start" for event in recorded))


if __name__ == "__main__":
    unittest.main()
