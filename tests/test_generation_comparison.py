"""생성 비교의 입력 누출 방지·재개 중복 요청 방지·사용량/실패 처리 검증."""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from mathhint_solver import CompareGeneration as comparison
from mathhint_solver import RateLimitedComparison as rate_limited


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.ids = ["diff_1_005", "diff_1_011"]
        for folder in ("data/processed/splits", "data/processed/problems", "data/processed/solutions"):
            (self.root / folder).mkdir(parents=True)
        records = []
        for identifier in self.ids:
            (self.root / "data/processed/problems" / (identifier + ".txt")).write_text("$6 \\times 7$의 값은?", encoding="utf-8")
            (self.root / "data/processed/solutions" / (identifier + ".txt")).write_text("REFERENCE_ONLY_SECRET 정답42", encoding="utf-8")
            records.append({"id": identifier, "answer_text": "$42$", "subject": "SUBJECT_SECRET",
                            "unit": "UNIT_SECRET", "type": "TYPE_SECRET", "source": "SOURCE_SECRET"})
        comparison.write_json(self.root / "data/processed/metadata.json", {"generation_id": "fixture", "records": records})
        comparison.write_json(self.root / "data/processed/splits/train.json", ["train_only_001"])
        comparison.write_json(self.root / "data/processed/splits/test.json", self.ids)
        self.predictions = self.root / "predictions.json"
        comparison.write_json(self.predictions, {"generation_id": "fixture", "train_ids": ["train_only_001"],
            "vocabulary": ["term", "negative", "zero", "tiny"], "documents": [
                {"id": identifier, "predicted_vector": [2.12345, -3, 0, .0001],
                 "actual_vector": [999991, 999992, 999993, 999994]} for identifier in self.ids]})
        self.config, self.plan = comparison.prepare_plan(self.root, self.predictions, model="fixture_model",
            thinking_level="minimal", temperature=0., max_output_tokens=100)

    def tearDown(self):
        self.temporary.cleanup()

    @staticmethod
    def response(text="최종정답: 42", finish="STOP"):
        return SimpleNamespace(text=text, usage_metadata=SimpleNamespace(
            prompt_token_count=10, candidates_token_count=20, thoughts_token_count=5, total_token_count=35),
            candidates=[SimpleNamespace(finish_reason=finish)], model_version="fixed", response_id="response")

    def test_reference_and_labels_and_actual_vectors_never_enter_prompt(self):
        self.assertEqual(len(self.plan), 4)
        for item in self.plan:
            for secret in ("REFERENCE_ONLY_SECRET", "SUBJECT_SECRET", "UNIT_SECRET", "TYPE_SECRET", "SOURCE_SECRET", "999991"):
                self.assertNotIn(secret, item["input_text"])
            if item["method"] == "baseline":
                self.assertEqual(item["input_text"], item["problem_text"])
            else:
                self.assertEqual(item["hint"]["mapping"], {"term": 2.123})
        self.assertEqual([item["method"] for item in self.plan],
                         ["baseline", "regression_hint", "regression_hint", "baseline"])

    def test_main_prepares_inputs_without_requesting_a_solution(self):
        output = self.root / "prepared"
        with patch.multiple(comparison, ROOT=self.root, PREDICTIONS=self.predictions, OUTPUT=output), \
                patch.object(comparison, "make_request", side_effect=AssertionError("no API in prepare step")), \
                patch.object(comparison, "render_reports", return_value={}):
            comparison.main()
        self.assertTrue((output / "questions" / self.ids[0] / "baseline/input.txt").is_file())
        self.assertFalse((output / "responses.jsonl").exists())

    def test_rate_limited_main_records_responses_without_replacing_global_function(self):
        output = self.root / "executed"
        comparison.initialize_run(output, self.config, self.plan)
        generate = comparison.generate_one
        limiter = SimpleNamespace(daily_exhausted=False, request=lambda function, text: function(text))
        with patch.multiple(rate_limited, ROOT=self.root, PREDICTIONS=self.predictions,
                            OUTPUT=output, RUN_API=True, WORKERS=1), \
                patch.dict("os.environ", {"GEMINI_API_KEY": "fixture"}), \
                patch.object(rate_limited, "GlobalRateLimiter", return_value=limiter), \
                patch.object(comparison, "make_request", return_value=lambda _: self.response()), \
                patch.object(comparison, "render_reports", return_value={}):
            rate_limited.main()
        records = comparison.load_completed(output, comparison.digest(self.config))
        self.assertEqual(len(records), 4)
        self.assertTrue(all(record["status"] == "success" for record in records.values()))
        self.assertIs(comparison.generate_one, generate)
        execution = next((output / "execution_runs").glob("*.json"))
        self.assertEqual(comparison.read_json(execution)["status"], "completed")

    def test_top_tokens_are_fixed_k_frequency_sorted_with_vocabulary_ties(self):
        vocabulary = [f"t{index}" for index in range(25)]
        vector = [float(index % 5 + 1) for index in range(25)]
        _, audit = comparison.serialize_hint(vocabulary, vector)
        expected = sorted(range(25), key=lambda index: (-vector[index], index))[:20]
        self.assertEqual(list(audit["mapping"]), [vocabulary[index] for index in expected])
        self.assertEqual(audit["top_k"], 20)
        _, full = comparison.serialize_hint(vocabulary, vector, mode="full_vector")
        self.assertEqual(list(full["mapping"]), vocabulary)
        full_config, _ = comparison.prepare_plan(self.root, self.predictions, model="fixture_model",
            thinking_level="minimal", temperature=0., max_output_tokens=100, hint_mode="full_vector")
        self.assertNotEqual(comparison.digest(full_config), comparison.digest(self.config))

    def test_imported_control_is_identical_provenanced_and_not_duplicated(self):
        source, output = self.root / "source", self.root / "new_run"
        source_config, source_plan = comparison.prepare_plan(self.root, self.predictions, model="fixture_model",
            thinking_level="minimal", temperature=0., max_output_tokens=100, hint_mode="full_vector")
        source_id = comparison.initialize_run(source, source_config, source_plan)
        item = next(item for item in source_plan if item["method"] == "baseline")
        original = comparison.generate_one(item, source_config, source_id, "fixture", lambda _: self.response())
        comparison.save_result(source, original)
        imported = comparison.import_baseline(source, output, self.config, self.plan)
        self.assertEqual(imported["total_reused_controls"], 1)
        loaded = comparison.load_completed(output, comparison.digest(self.config))[(item["id"], "baseline")]
        self.assertEqual(loaded["response_origin"], "reused_control")
        for field in ("output_text", "usage", "attempts", "started_at", "completed_at"):
            self.assertEqual(loaded[field], original[field])
        self.assertEqual(loaded["provenance"]["source_record_sha256"], comparison.digest(original))
        comparison.import_baseline(source, output, self.config, self.plan)
        self.assertEqual(len((output / "responses.jsonl").read_text().splitlines()), 1)
        original["input_text"] += "altered"
        comparison.save_result(source, original)
        with self.assertRaisesRegex(ValueError, "문항 데이터가 다릅니다"):
            comparison.import_baseline(source, self.root / "unsafe", self.config, self.plan)

    def test_predictions_must_cover_exact_fixed_test_ids(self):
        data = comparison.read_json(self.predictions)
        data["documents"].pop()
        comparison.write_json(self.predictions, data)
        with self.assertRaisesRegex(ValueError, "테스트 ID"):
            comparison.load_predictions(self.predictions, self.ids, "fixture")

    def test_changed_inputs_cannot_resume_an_existing_run(self):
        folder = self.root / "run"
        comparison.initialize_run(folder, self.config, self.plan)
        changed = {**self.config, "temperature": .5}
        with self.assertRaisesRegex(ValueError, "달라졌습니다"):
            comparison.initialize_run(folder, changed, self.plan)

    def test_pilot_then_full_resume_does_not_repeat_successful_requests(self):
        folder = self.root / "run"

        original = comparison.generate_one
        def fake(item, config, config_id, api_key):
            return original(item, config, config_id, api_key, request_function=lambda _: self.response())
        with patch.object(comparison, "generate_one", side_effect=fake) as generate, \
                patch.object(comparison, "render_reports", return_value={}):
            comparison.run_requests(folder, self.config, self.plan, api_key="fixture", limit=1, workers=1)
            self.assertEqual(generate.call_count, 2)
            comparison.run_requests(folder, self.config, self.plan, api_key="fixture", workers=1)
            self.assertEqual(generate.call_count, 4)
        self.assertEqual(len((folder / "responses.jsonl").read_text().splitlines()), 4)

    def test_missing_usage_is_null_and_retry_keeps_both_attempts(self):
        self.assertIsNone(comparison.usage_record(None)["total_token_count"])
        class Unavailable(Exception):
            code = 503
        calls = []
        def request(_):
            calls.append(1)
            if len(calls) == 1:
                raise Unavailable("temporary")
            return self.response()
        with patch.object(comparison.time, "sleep"):
            result = comparison.generate_one(self.plan[0], self.config, "config", "fixture", request)
        self.assertEqual(result["status"], "success")
        self.assertEqual(len(result["attempts"]), 2)
        self.assertIsNone(result["attempts"][0]["usage"]["total_token_count"])
        self.assertEqual(result["attempts"][1]["usage"]["total_token_count"], 35)

    def test_truncated_output_is_separate_from_an_incorrect_answer(self):
        result = comparison.generate_one(self.plan[0], self.config, "config", "fixture",
                                         lambda _: self.response("최종정답: 7", "MAX_TOKENS"))
        self.assertEqual(result["status"], "truncated_response")
        self.assertIsNone(result["evaluation"]["correct"])
        self.assertEqual(result["output_text"], "최종정답: 7")
        self.assertEqual(result["usage"]["total_token_count"], 35)

    def test_graceful_stop_saves_inflight_result_without_next_api_call(self):
        folder = self.root / "stop_run"
        stop_file = folder / "stop_requested"
        original = comparison.generate_one
        def fake(item, config, config_id, api_key):
            result = original(item, config, config_id, api_key, lambda _: self.response())
            stop_file.touch()
            return result
        with patch.object(comparison, "generate_one", side_effect=fake) as generate, \
                patch.object(comparison, "render_reports", return_value={}):
            with self.assertRaises(comparison.RequestedStop):
                comparison.run_requests(folder, self.config, self.plan, api_key="fixture", workers=1, stop_file=stop_file)
            self.assertEqual(generate.call_count, 1)
        rows = comparison.load_completed(folder, comparison.digest(self.config))
        self.assertEqual(len(rows), 1)
        self.assertEqual(next(iter(rows.values()))["status"], "success")

    def test_errors_redact_the_api_key(self):
        class Unauthorized(Exception):
            code = 401
        def request(_):
            raise Unauthorized("credential secret-key-used-for-test rejected")
        result = comparison.generate_one(self.plan[0], self.config, "config", "secret-key-used-for-test", request)
        self.assertNotIn("secret-key-used-for-test", json.dumps(result))
        self.assertEqual(len(result["attempts"]), 1)
        self.assertIsNone(result["evaluation"]["correct"])

    def test_summary_separates_coverage_from_parsed_accuracy(self):
        row = comparison.generate_one(self.plan[0], self.config, "config", "fixture", lambda _: self.response())
        summary = comparison.summarize([row], self.ids)
        baseline = summary["methods"]["baseline"]
        self.assertEqual(baseline["accuracy_on_graded"], 1.)
        self.assertEqual(baseline["correct_per_expected_question"], .5)
        self.assertEqual(baseline["grading_coverage"], .5)
        self.assertEqual(baseline["missing_requests"], 1)


if __name__ == "__main__":
    unittest.main()
