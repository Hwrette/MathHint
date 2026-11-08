"""세 조건의 정보 접근·상위20개·SDK 경계·정확한 재사용·재개를 확인한다."""

import json
import shutil
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from mathhint_solver import CompareGeneration as comparison
from mathhint_solver import ThreeWayGeneration as three


class ThreeWayTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.ids = ["q1", "q2"]
        vocabulary = ["actual_only", "predicted_only", "both", "negative", "half"]
        for folder in ["splits", "problems", "solutions"]:
            (self.root / "data/processed" / folder).mkdir(parents=True)
        metadata = []
        for identifier in self.ids:
            (self.root / f"data/processed/problems/{identifier}.txt").write_text("$6 \\times 7$의 값은?", encoding="utf-8")
            (self.root / f"data/processed/solutions/{identifier}.txt").write_text("REFERENCE_PROSE_SECRET 정답42", encoding="utf-8")
            metadata.append({"id": identifier, "answer_text": "$42$", "subject": "SUBJECT_SECRET",
                             "unit": "UNIT_SECRET", "type": "TYPE_SECRET", "source": "SOURCE_SECRET"})
        comparison.write_json(self.root / "data/processed/metadata.json", {"generation_id": "fixture", "records": metadata})
        comparison.write_json(self.root / "data/processed/splits/train.json", ["train1"])
        comparison.write_json(self.root / "data/processed/splits/test.json", self.ids)
        comparison.write_json(self.root / "data/vectors/solutions/vocabulary.json", vocabulary)
        self.actual_path = self.root / "data/vectors/solutions/test_vectors.json"
        comparison.write_json(self.actual_path, {"generation_id": "fixture", "documents": [
            {"id": identifier, "vector": [11, 0, 7, 0, 0]} for identifier in self.ids]})
        self.predictions = self.root / "predictions.json"
        comparison.write_json(self.predictions, {"generation_id": "fixture", "train_ids": ["train1"], "vocabulary": vocabulary,
            "documents": [{"id": identifier, "predicted_vector": [0, 1.49, 2.5, -2, .5],
                           "actual_vector": [999991] * 5} for identifier in self.ids]})
        self.config, self.plan = three.prepare_plan(self.root, self.predictions, model="fixture_model", max_output_tokens=100)

    def tearDown(self):
        self.temporary.cleanup()

    @staticmethod
    def response():
        return SimpleNamespace(text="최종정답: 42", usage_metadata=SimpleNamespace(
            prompt_token_count=10, candidates_token_count=20, thoughts_token_count=None, total_token_count=30),
            candidates=[SimpleNamespace(finish_reason="STOP")], model_version="fixture_model", response_id="fixture")

    def test_same_serialization_except_truthful_source_and_float_precision(self):
        text1, hint1 = three.serialize_vector(["token"], [2.123456])
        text2, hint2 = three.serialize_vector(["token"], [2.123456], source="actual_reference")
        self.assertEqual(hint1["mapping"], {"token": 2.123})
        self.assertEqual(hint1["mapping"], hint2["mapping"])
        self.assertEqual(text2.replace("정답 해설에서 계산한 실제", "학습 데이터로 학습한 선형회귀가 예측한").replace("실제 빈도순", "예측 빈도순"), text1)
        self.assertEqual(three.serialize_vector(["a", "b"], [.49999, .5])[1]["mapping"], {"b": .5, "a": .5})

    def test_only_oracle_receives_true_vector_and_no_arm_receives_reference_prose(self):
        self.assertEqual(len(self.plan), 6)
        by_method = {row["method"]: row for row in self.plan if row["id"] == "q1"}
        self.assertEqual(by_method["baseline"]["input_text"], by_method["baseline"]["problem_text"])
        self.assertEqual(by_method["oracle_hint"]["hint"]["mapping"], {"actual_only": 11, "both": 7})
        self.assertEqual(by_method["regression_hint"]["hint"]["mapping"], {"both": 2.5, "predicted_only": 1.49, "half": .5})
        for row in self.plan:
            for secret in ["REFERENCE_PROSE_SECRET", "SUBJECT_SECRET", "UNIT_SECRET", "TYPE_SECRET", "SOURCE_SECRET", "999991"]:
                self.assertNotIn(secret, row["input_text"])
            self.assertEqual(row["uses_test_reference_vector"], row["method"] == "oracle_hint")

    def test_only_top_twenty_positive_coordinates_with_stable_ties(self):
        _, hint = three.serialize_vector([f"t{i}" for i in range(25)], [1] * 25)
        self.assertEqual(hint["transmitted_coordinates"], 20)
        self.assertEqual(list(hint["mapping"]), [f"t{i}" for i in range(20)])
        self.assertEqual(three.serialize_vector(["tiny", "negative"], [.0001, -2])[1]["mapping"], {})

    def test_sdk_boundary_receives_exact_saved_contents_and_config_without_key(self):
        output = self.root / "audit"
        audit = three.dry_run(output, self.root, self.config, self.plan)
        self.assertEqual(audit["mocked_sdk_calls"], 6)
        for item in self.plan:
            saved = comparison.read_json(output / "prompt_audit/requests" / item["id"] / (item["condition"] + ".json"))
            self.assertEqual(saved["sdk_request"]["contents"], item["input_text"])
            self.assertEqual(saved["sdk_request"]["config"]["system_instruction"], self.config["system_instruction"])
            self.assertNotIn("DRY_RUN_NO_CREDENTIAL", json.dumps(saved))
            self.assertEqual(saved["sdk_request_sha256"], comparison.digest(saved["sdk_request"]))

    def test_changed_actual_reference_vector_changes_only_oracle_inputs_and_config(self):
        changed = comparison.read_json(self.actual_path)
        changed["documents"][0]["vector"][0] = 12
        comparison.write_json(self.actual_path, changed)
        config, plan = three.prepare_plan(self.root, self.predictions, model="fixture_model", max_output_tokens=100)
        self.assertNotEqual(comparison.digest(config), comparison.digest(self.config))
        before = {(row["id"], row["method"]): row["input_text"] for row in self.plan}
        after = {(row["id"], row["method"]): row["input_text"] for row in plan}
        self.assertNotEqual(before["q1", "oracle_hint"], after["q1", "oracle_hint"])
        self.assertEqual(before["q1", "regression_hint"], after["q1", "regression_hint"])
        self.assertEqual(before["q1", "baseline"], after["q1", "baseline"])

    def test_actual_vector_id_order_must_match_fixed_test_ids(self):
        changed = comparison.read_json(self.actual_path)
        changed["documents"].reverse()
        comparison.write_json(self.actual_path, changed)
        with self.assertRaises(ValueError):
            three.prepare_plan(self.root, self.predictions)

    def test_all_six_orders_balance_position_and_relative_hint_order(self):
        orders = [[three.METHODS[i] for i in order] for order in three.ORDERS]
        for method in three.METHODS:
            self.assertEqual([sum(order.index(method) == position for order in orders) for position in range(3)], [2, 2, 2])
        self.assertEqual(sum(order.index("oracle_hint") < order.index("regression_hint") for order in orders), 3)

    def test_reused_exact_requests_keep_output_usage_time_and_are_not_repeated(self):
        source, output = self.root / "source", self.root / "new"
        config, plan = comparison.prepare_plan(self.root, self.predictions, model="fixture_model", thinking_level="minimal",
                                               temperature=0., max_output_tokens=100)
        source_id = comparison.initialize_run(source, config, plan)
        originals = []
        for item in plan:
            if item["method"] in ("baseline", "regression_hint"):
                row = comparison.generate_one(item, config, source_id, "fixture", lambda _: self.response())
                comparison.save_result(source, row); originals.append(row)
        self.assertEqual(three.prepare(output, self.config, self.plan, source / "config.json", source / "responses.jsonl", project=self.root)["imported_this_run"], 4)
        self.assertEqual(three.prepare(output, self.config, self.plan, source / "config.json", source / "responses.jsonl", project=self.root)["imported_this_run"], 0)
        rows = comparison.load_completed(output, comparison.digest(self.config))
        for original in originals:
            row = rows[original["id"], original["method"]]
            self.assertEqual(row["response_origin"], "reused_exact_request")
            for field in ["output_text", "usage", "attempts", "started_at", "completed_at"]:
                self.assertEqual(row[field], original[field])
        originals[-1]["input_text"] += "changed"
        comparison.save_result(source, originals[-1])
        with self.assertRaises(ValueError):
            three.prepare(self.root / "bad", self.config, self.plan, source / "config.json", source / "responses.jsonl")
        self.assertFalse((self.root / "bad/responses.jsonl").exists())

    def test_source_only_resume_keeps_original_identity_but_rejects_input_or_settings_changes(self):
        output = self.root / "source_transition"
        comparison.initialize_run(output, self.config, self.plan)
        changed = {**self.config, "runner_sha256": "new_source_fingerprint"}
        resolved = three.resolve_resume_config(output, changed)
        self.assertEqual(resolved, self.config)
        transition = comparison.read_json(output / "source_transition.json")
        self.assertTrue(transition["versions"][0]["all_non_source_config_fields_and_input_hashes_match"])
        self.assertEqual(len(transition["versions"]), 1)
        three.resolve_resume_config(output, changed)
        self.assertEqual(len(comparison.read_json(output / "source_transition.json")["versions"]), 1)
        with self.assertRaises(ValueError):
            three.resolve_resume_config(output, {**changed, "temperature": .5})
        with self.assertRaises(ValueError):
            three.resolve_resume_config(output, {**changed, "inputs": []})

    def test_prediction_path_is_location_only_but_changed_bytes_are_rejected(self):
        output = self.root / "relocation"
        comparison.initialize_run(output, self.config, self.plan)
        changed = {**self.config, "predictions_source": "/different/clone/predictions.json"}
        self.assertEqual(three.resolve_resume_config(output, changed), self.config)
        transition = comparison.read_json(output / "source_transition.json")
        self.assertEqual(transition["frozen_source_locations"]["predictions_source"], str(self.predictions))
        self.assertEqual(transition["versions"][-1]["source_locations"]["predictions_source"], changed["predictions_source"])
        with self.assertRaises(ValueError):
            three.resolve_resume_config(output, {**changed, "predictions_sha256": "different_prediction_bytes"})
        with self.assertRaises(ValueError):
            three.resolve_resume_config(output, {**changed, "grader_sha256": "different_grader"})

    def test_real_dataset_in_another_root_resumes_and_preserves_historical_requests(self):
        original = three.ROOT / "results/final_experiment/03_gemini"
        if not (original / "config.json").exists():
            self.skipTest("Final experiment artifacts are not present")
        relocated = self.root / "different_clone"
        relocated.mkdir()
        (relocated / "data").symlink_to(three.ROOT / "data", target_is_directory=True)
        (relocated / "results").mkdir()
        (relocated / "results/model_comparison_2026-11-07").symlink_to(three.PREVIOUS, target_is_directory=True)
        output = relocated / "results/final_experiment/03_gemini"
        output.mkdir(parents=True)
        (output / "config.json").write_bytes((original / "config.json").read_bytes())
        shutil.copytree(original / "prompt_audit/requests", output / "prompt_audit/requests")
        hashes = {path:comparison.file_hash(path) for path in (output / "prompt_audit/requests").glob("*/*.json")}
        predictions = relocated / "results/model_comparison_2026-11-07/01_회귀모델/regression_predictions.json"
        config, plan = three.prepare_plan(relocated, predictions)
        frozen = comparison.read_json(output / "config.json")
        self.assertNotEqual(config["predictions_source"], frozen["config"]["predictions_source"])
        self.assertEqual(config["predictions_sha256"], frozen["config"]["predictions_sha256"])
        resolved = three.resolve_resume_config(output, config)
        self.assertEqual(comparison.digest(resolved), frozen["config_id"])
        audit = three.dry_run(output, relocated, resolved, plan)
        self.assertEqual(audit["requests"], 240)
        self.assertTrue(all(comparison.file_hash(path) == digest for path, digest in hashes.items()))

    def test_renderer_counts_reused_exact_requests_without_duplicate_summary_files(self):
        output = self.root / "viewer"; output.mkdir()
        row = comparison.generate_one(self.plan[0], self.config, "fixture", "fixture", lambda _: self.response())
        row["response_origin"] = "reused_exact_request"
        summary = three.render_reports(output, [row], self.config)
        self.assertEqual(summary["methods"][row["method"]]["reused_controls"], 1)
        self.assertTrue((output / "report.html").is_file())
        self.assertFalse((output / "summary.json").exists())
        self.assertFalse((output / "comparison.csv").exists())

    def test_three_arm_resume_and_unknown_usage_use_existing_durable_engine(self):
        output = self.root / "run"; calls = []
        def request(text):
            calls.append(text)
            return self.response()
        limiter = SimpleNamespace(daily_exhausted=False, request=lambda function, text: function(text))
        with patch.object(three, "GlobalRateLimiter", return_value=limiter):
            three.run_experiment(output, self.config, self.plan, api_key="fixture", limit=1, workers=1, request_function=request)
            self.assertEqual(len(calls), 3)
            summary = three.run_experiment(output, self.config, self.plan, api_key="fixture", workers=1, request_function=request)
        self.assertEqual(len(calls), 6)
        rows = comparison.load_completed(output, comparison.digest(self.config))
        self.assertEqual(len(rows), 6)
        self.assertFalse((output / "summary.json").exists())
        self.assertFalse((output / "comparison.csv").exists())
        self.assertEqual(set(summary["methods"]), set(three.METHODS))
        self.assertTrue(all(row["correct"] == 2 for row in summary["methods"].values()))
        self.assertIsNone(summary["methods"]["oracle_hint"]["usage"]["thoughts_token_count"]["sum"])
        self.assertEqual(comparison.METHODS, ("baseline", "regression_hint"))


if __name__ == "__main__":
    unittest.main()
