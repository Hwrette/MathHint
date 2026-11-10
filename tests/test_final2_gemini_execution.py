"""네 조건의 전송 규칙·로컬 제한·중단/재개를 비용 없는 모의 요청으로 검증한다."""

from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from mathhint_solver import CompareGeneration as comparison
from mathhint_solver.AnswerEvaluation import extract_reference
from mathhint_solver.final_experiment_2.gemini_comparison.budget import BudgetRateLimiter, BudgetStop
from mathhint_solver.final_experiment_2.gemini_comparison.common import execution_lock, write_json
from mathhint_solver.final_experiment_2.gemini_comparison.plan import (SETTINGS, serialize_vector,
    model_gate, initialize, reuse_existing)
from mathhint_solver.final_experiment_2.gemini_comparison import run as runner


class FakeClock:
    def __init__(self):
        self.seconds = 0.0
    def clock(self):
        return self.seconds
    def wall(self):
        return 100000 + self.seconds
    def sleep(self, delay):
        self.seconds += delay


class APIError(Exception):
    def __init__(self, code, message, *, headers=None, details=None):
        super().__init__(message)
        self.code = code
        self.response = SimpleNamespace(headers=headers or {})
        self.details = details


class Final2GenerationTests(unittest.TestCase):
    def test_longer_http_timeout_changes_only_transport_not_sdk_body_or_hash(self):
        captured, transport, observed = [], [], []
        class FakeClient:
            def __init__(self, **arguments):
                transport.append((arguments["http_options"].timeout,
                                  arguments["http_options"].retry_options.attempts))
                self.models = self
            def __enter__(self):
                return self
            def __exit__(self, *_):
                return False
            def generate_content(self, **arguments):
                captured.append(comparison.request_snapshot(arguments))
                return SimpleNamespace(text="최종정답: ①")
        text = r"수식 $\lim_{x\to0}\frac{\sin x}{x}$"
        comparison.make_request(SETTINGS, "fake", client_factory=FakeClient)(text)
        runner.transport_request(SETTINGS, "fake", http_timeout_ms=180_000,
                                 client_factory=FakeClient, request_observer=observed.append)(text)
        self.assertEqual(transport, [(90_000, 1), (180_000, 1)])
        self.assertEqual(captured[0], captured[1])
        self.assertEqual(comparison.digest(captured[0]), comparison.digest(captured[1]))
        self.assertEqual(observed, [captured[1]])

    def test_httpx_read_timeout_uses_existing_bounded_retry_and_preserves_safe_cause(self):
        import httpx
        attempts, details = [], []
        class TimeoutClient:
            def __init__(self, **_):
                self.models = self
            def __enter__(self):
                return self
            def __exit__(self, *_):
                return False
            def generate_content(self, **_):
                attempts.append(True)
                raise httpx.ReadTimeout("timed out key=private")
        request = runner.transport_request(SETTINGS, "private", http_timeout_ms=180_000,
                                           client_factory=TimeoutClient, error_observer=details.append)
        with self.assertRaises(TimeoutError) as stopped:
            request("problem")
        self.assertIsInstance(stopped.exception.__cause__, httpx.ReadTimeout)
        self.assertNotIn("private", str(stopped.exception))
        attempts.clear()
        details.clear()
        item = {"id": "q", "method": "baseline", "input_text": "problem", "reference": {}, "problem_text": "problem"}
        with patch.object(comparison.time, "sleep"):
            row = comparison.generate_one(item, {**SETTINGS, "max_attempts": 2}, "c", "private", request_function=request)
        self.assertEqual(len(attempts), 2)
        self.assertEqual(len(row["attempts"]), 2)
        self.assertEqual(row["error"]["type"], "TimeoutError")
        self.assertTrue(all(detail["original_error_type"] == "ReadTimeout" for detail in details))
        self.assertTrue(all("private" not in detail["message"] for detail in details))

    def test_three_hint_arms_share_selection_json_and_final_instruction(self):
        vocabulary = ["latex:x", r"latex:\sin", "kiwi:연속", "latex:2", "kiwi:대입"]
        values = [-1, 2.12345, 2.12345, .0004, .0006]
        payloads = [serialize_vector(vocabulary, values, c) for c in "BCD"]
        self.assertEqual([record[1]["mapping"] for record in payloads], [
            {r"latex:\sin": 2.123, "kiwi:연속": 2.123, "kiwi:대입": .001}] * 3)
        self.assertEqual(len({text.splitlines()[-2] for text, _ in payloads}), 1)
        self.assertTrue(all(text.endswith("위 주요 토큰을 참고하여 풀이를 작성해줘.") for text, _ in payloads))
        self.assertIn("딥러닝", payloads[1][0])
        self.assertIn("정답 해설", payloads[2][0])
        self.assertIn("...", SETTINGS["system_instruction"])

    def test_missing_frozen_model_blocks_before_any_sdk_request(self):
        with tempfile.TemporaryDirectory() as temporary, \
             patch.object(comparison, "make_request", side_effect=AssertionError("전송 금지")) as request:
            with self.assertRaises(FileNotFoundError):
                model_gate(Path(temporary), {"ids": {"train": ["q"], "test": []},
                           "vocabularies": {"solutions": ["latex:x"]}})
            request.assert_not_called()

    def test_budget_counts_every_attempt_and_never_waits_forever(self):
        clock = FakeClock()
        limiter = BudgetRateLimiter({"max_new_requests": 2}, clock=clock.clock,
                                    wall_clock=clock.wall, sleeper=clock.sleep)
        limiter.acquire()
        limiter.acquire()
        self.assertEqual(clock.seconds, 10)
        with self.assertRaises(BudgetStop) as stopped:
            limiter.acquire()
        self.assertEqual(stopped.exception.status, "partial_complete")
        self.assertEqual(limiter.new_starts, 2)

    def test_hour_cap_long_wait_pauses_and_persists_prior_starts(self):
        clock = FakeClock()
        event = {"event": "request_start", "time": datetime.fromtimestamp(clock.wall(), timezone.utc).isoformat()}
        limiter = BudgetRateLimiter({"rph": 1}, events=[event], clock=clock.clock,
                                    wall_clock=clock.wall, sleeper=clock.sleep)
        with self.assertRaises(BudgetStop) as stopped:
            limiter.acquire()
        self.assertEqual(stopped.exception.status, "paused_rate_limit")
        self.assertEqual(clock.seconds, 0)
        self.assertEqual(limiter.new_starts, 0)

    def test_503_http_date_retry_after_is_respected_above_default_backoff(self):
        clock = FakeClock()
        limiter = BudgetRateLimiter(clock=clock.clock, wall_clock=clock.wall, sleeper=clock.sleep)
        when = format_datetime(datetime.fromtimestamp(clock.wall() + 90, timezone.utc), usegmt=True)
        limiter.observe_error(APIError(503, "busy", headers={"Retry-After": when}))
        limiter.acquire()
        self.assertGreaterEqual(clock.seconds, 91)

    def test_daily_quota_and_permanent_auth_stop_without_retry(self):
        clock = FakeClock()
        limiter = BudgetRateLimiter(clock=clock.clock, wall_clock=clock.wall, sleeper=clock.sleep)
        limiter.observe_error(APIError(429, "GenerateRequestsPerDay quota exceeded", details={"retryDelay": "90s"}))
        with self.assertRaises(BudgetStop) as stopped:
            limiter.acquire()
        self.assertEqual(stopped.exception.status, "daily_quota_exhausted")
        self.assertEqual(clock.seconds, 0)
        limiter = BudgetRateLimiter(clock=clock.clock, wall_clock=clock.wall, sleeper=clock.sleep)
        attempts = []
        def denied(text):
            attempts.append(text)
            raise APIError(403, "permission denied")
        item = {"id": "q", "method": "baseline", "input_text": "problem", "reference": {}, "problem_text": "problem"}
        row = comparison.generate_one(item, {**SETTINGS, "max_attempts": 2}, "c", "private",
                                     request_function=lambda text: limiter.request(denied, text))
        self.assertEqual(len(attempts), 1)
        self.assertEqual(row["error"]["code"], 403)
        self.assertEqual(limiter.stop_status, "permission_denied")

    def test_exclusive_process_lock_blocks_second_owner_and_cleans_up(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            with execution_lock(output):
                with self.assertRaises(RuntimeError), execution_lock(output):
                    pass
            self.assertFalse((output / ".execution.lock").exists())

    def test_exact_legacy_success_is_reused_once_without_rewriting_usage(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "results/final_experiment/03_gemini"
            output = root / "new"
            config = {**SETTINGS, "compact_storage": True}
            old_id = comparison.digest(config)
            write_json(source / "config.json", {"config_id": old_id, "config": config})
            text = r"문제 $\frac{1}{2}$"
            item = {"id": "q", "condition": "A", "method": "baseline", "split": "test",
                    "input_text": text, "input_sha256": comparison.digest(text), "problem_text": text,
                    "system_instruction": SETTINGS["system_instruction"], "reference": {"choice": "①"},
                    "reference_answer_text": "①", "reference_solution": "원본 풀이", "hint": None,
                    "compact_storage": True,
                    "request_sha256": comparison.digest(comparison.request_snapshot(comparison.sdk_request_arguments(config, text)))}
            old = {**item, "status": "success", "config_id": old_id, "output_text": "최종정답: ①",
                   "usage": comparison.usage_record(None), "evaluation": {"correct": True}}
            write_json(source / "prompt_audit/requests/q/A.json", {"sdk_request":
                comparison.request_snapshot(comparison.sdk_request_arguments(config, text)),
                "sdk_request_sha256": item["request_sha256"]})
            from mathhint_solver.final_experiment_2.gemini_comparison.common import append_jsonl, read_jsonl
            append_jsonl(source / "responses.jsonl", old)
            initialize(output, config, [item])
            self.assertEqual(reuse_existing(root, output, config, [item])["imported"], 1)
            self.assertEqual(reuse_existing(root, output, config, [item])["imported"], 0)
            rows = read_jsonl(output / "responses.jsonl")
            self.assertEqual(len(rows), 1)
            self.assertIsNone(rows[0]["usage"]["thoughts_token_count"])
            self.assertEqual(rows[0]["response_origin"], "reused_exact_request")

    def test_runner_resume_skips_success_and_never_recalls_model(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "results/final_experiment_2/gemini_comparison"
            text = "문제 선택지 ① 1 ② 2"
            reference = extract_reference({"answer_text": "①"}, text)
            config = {**SETTINGS, "max_attempts": 2, "compact_storage": True, "split": "test", "test_ids": ["q"]}
            snapshot = comparison.request_snapshot(comparison.sdk_request_arguments(config, text))
            item = {"id": "q", "condition": "A", "method": "baseline", "split": "test", "input_text": text,
                    "problem_text": text, "reference": reference, "hint": None, "compact_storage": True,
                    "request_sha256": comparison.digest(snapshot)}
            initialize(output, config, [item])
            write_json(output / "prompt_audit/requests/q/A.json", {"sdk_request": snapshot})
            preparation = {"state": {"successful_requests": 0, "pending_requests": [item]}}
            def prepared(*_, **__):
                return config, [item], preparation, output, {}
            calls = []
            def request(_):
                calls.append(True)
                return SimpleNamespace(text="최종정답: ①", candidates=[], usage_metadata=None,
                                       model_version="fake", response_id="r", prompt_feedback=None)
            with patch.object(runner, "prepare", side_effect=prepared):
                first = runner.generate(root, output, request_function=request, api_key="fake")
                second = runner.generate(root, output, request_function=request, api_key="fake")
            self.assertEqual(len(calls), 1)
            self.assertEqual(first["status"], "completed")
            self.assertEqual(second["successful_requests"], 1)


if __name__ == "__main__":
    unittest.main()
