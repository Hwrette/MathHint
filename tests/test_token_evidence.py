"""저장 근거의 OOV·전송값·반올림 전후 차이를 작은 자료로 확인한다."""

from collections import Counter
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from mathhint_analysis.token_analysis.common import dump_csv, dump_json, read_csv, read_json
from mathhint_analysis.token_analysis.evidence import (
    ROLE_GROUPS, build_top20, check_request, positive_top_indices, restore_region,
)
from mathhint_analysis.token_analysis.roles import CATEGORIES
from mathhint_solver.CompareGeneration import digest
from mathhint_solver.ThreeWayGeneration import serialize_vector


class TokenEvidenceTests(unittest.TestCase):
    def test_original_top_order_uses_unrounded_values_and_index_ties(self):
        self.assertEqual(positive_top_indices([.0004, .00045, 3., -1., 3.]), [2, 4, 1, 0])
        with self.assertRaises(ValueError):
            positive_top_indices([float("nan")])
        self.assertEqual(set(ROLE_GROUPS), set(CATEGORIES))

    def test_oov_reconstruction_must_match_every_original_coordinate_and_count(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data = {"vocabularies": {"problems": ["latex:x"]}, "ids": {"train": ["a"], "test": ["b"]}}
            for part, identifier, text, known, ignored in (
                ("train", "a", "a", 2, 0), ("test", "b", "b", 1, 3),
            ):
                path = root / f"data/processed/problems/{identifier}.txt"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
                dump_json(root / f"data/vectors/problems/{part}_vectors.json",
                          {"documents": [{"id": identifier, "vector": [known],
                                          "token_count": known + ignored, "ignored_token_count": ignored}]})
            def count(text):
                return Counter({"latex:x": 2}) if text == "a" else Counter({"latex:x": 1, r"latex:\gamma": 3})
            rows, checks, summary = restore_region(root, data, "problems", count)
            self.assertEqual(len(checks), 2)
            self.assertEqual(rows[0]["token"], r"latex:\gamma")
            self.assertEqual((rows[0]["total_tf"], rows[0]["total_df"]), (3, 1))
            self.assertEqual(summary["ignored_fraction"], .75)
            path = root / "data/vectors/problems/test_vectors.json"
            saved = read_json(path)
            saved["documents"][0]["vector"] = [2]
            dump_json(path, saved)
            with self.assertRaisesRegex(ValueError, "재계수"):
                restore_region(root, data, "problems", count)

    def _request(self, root, data, condition, values):
        identifier = "toy"
        text = "$x$의 값은?\n"
        path = root / "data/processed/problems/toy.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        suffix, hint = serialize_vector(data["vocabularies"]["solutions"], values,
                                        source="regression_prediction" if condition == "B" else "actual_reference")
        user = text + suffix
        sdk = {"model": "saved-model", "contents": user, "config": {"system_instruction": "원래 지시"}}
        request = {"id": identifier, "condition": condition,
                   "method": "regression_hint" if condition == "B" else "oracle_hint",
                   "generation_id": data["generation_id"], "problem_text": text, "hint": hint,
                   "user_message": user, "input_sha256": digest(user), "sdk_request": sdk,
                   "requested_model": "saved-model", "system_instruction": "원래 지시",
                   "sdk_request_sha256": digest(sdk), "full_request_text": "[SYSTEM]\n원래 지시\n[USER]\n" + user}
        path = root / f"results/final_experiment/03_gemini/prompt_audit/requests/toy/{condition}.json"
        dump_json(path, request)
        return path

    def test_request_validation_rejects_wrong_transmitted_value_and_wrong_sdk_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data = {"vocabularies": {"solutions": ["latex:x", r"latex:\lim"]}, "generation_id": "toy-gen"}
            values = [1.23456, 2.]
            path = self._request(root, data, "B", values)
            request, _ = check_request(root, data, "toy", "B", values)
            request["hint"]["mapping"]["latex:x"] = 50.
            dump_json(path, request)
            with self.assertRaisesRegex(ValueError, "직렬화"):
                check_request(root, data, "toy", "B", values)
            path = self._request(root, data, "B", values)
            request = read_json(path)
            request["sdk_request_sha256"] = "incorrect"
            dump_json(path, request)
            with self.assertRaisesRegex(ValueError, "해시"):
                check_request(root, data, "toy", "B", values)

    def test_actual_transmitted_coordinates_are_separate_from_full_vector_top20(self):
        with tempfile.TemporaryDirectory() as folder:
            root, output = Path(folder), Path(folder) / "analysis"
            vocabulary = ["latex:x", r"latex:\lim", "latex:2"]
            actual, predicted = [2, 1, 0], [1.0004, 1.00045, .00049]
            data = {"vocabularies": {"solutions": vocabulary}, "generation_id": "toy-gen",
                    "ids": {"test": ["toy"]}, "arrays": {"solutions": {"test": np.array([actual])}}}
            for condition, values in (("B", predicted), ("C", actual)):
                self._request(root, data, condition, values)
            dump_json(root / "results/final_experiment/02_regression/vectors.json",
                      {"vocabulary": vocabulary, "documents": [{"id": "toy", "actual_vector": actual,
                       "raw_predicted_vector": predicted, "predicted_vector": predicted}]})
            dump_csv(root / "results/final_experiment/02_regression/question_comparison.csv",
                     [{"id": "toy", "common_top20_count": 2, "precision_at_20": .1,
                       "predicted_top_count": 3, "actual_top_count": 2}])
            summary = build_top20(root, output, data)
            self.assertEqual(summary["transmitted_coordinates"], {"B": 2, "C": 2})
            self.assertEqual(summary["omitted_after_rounding"], 1)
            comparison = read_csv(output / "02_solution_tokens/top20_analysis.csv")
            self.assertEqual(comparison[0]["vector_top20_count"], "3")
            self.assertEqual(comparison[0]["transmitted_count"], "2")
            self.assertEqual(comparison[0]["omitted_after_rounding"], "1")
            composition = read_csv(output / "02_solution_tokens/top20_category_composition.csv")
            self.assertAlmostEqual(sum(float(row["coordinate_fraction"]) for row in composition if row["condition"] == "B"), 1.)
            self.assertFalse(summary["stopword_filtered_reselection"])
            self.assertEqual(summary["new_api_calls"], 0)
            # Historical B has no source provenance field; its exact input and
            # coordinates still match. C additionally has a boundary snapshot.
            generation = root / "results/final_experiment/03_gemini"
            responses = []
            for condition in ("B", "C"):
                request = read_json(generation / f"prompt_audit/requests/toy/{condition}.json")
                hint = dict(request["hint"])
                if condition == "B":
                    hint.pop("source")
                responses.append({"id": "toy", "method": request["method"], "status": "success",
                                  "input_text": request["user_message"], "input_sha256": request["input_sha256"], "hint": hint})
            (generation / "responses.jsonl").write_text("\n".join(json.dumps(row) for row in responses) + "\n")
            request = read_json(generation / "prompt_audit/requests/toy/C.json")
            snapshot = {"id": "toy", "condition": "C", "request": request["sdk_request"],
                        "request_sha256": request["sdk_request_sha256"]}
            capture = generation / "prompt_audit/sdk_calls/toy_C.json"
            dump_json(capture, snapshot)
            summary = build_top20(root, output, data)
            self.assertEqual(summary["successful_response_inputs_verified"], 2)
            self.assertEqual(summary["contemporaneous_sdk_capture_files_verified"], 1)
            snapshot["request_sha256"] = "changed"
            dump_json(capture, snapshot)
            with self.assertRaisesRegex(ValueError, "SDK 캡처"):
                build_top20(root, output, data)
