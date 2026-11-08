"""최종 분석에서 분모·누락·재사용·정답표 충돌이 잘못 집계되지 않게 한다."""

import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mathhint_analysis.ExperimentMetrics import answer_metrics, exact_mcnemar, usage_summary, wilson_interval
from mathhint_analysis.AnalyzeThreeWay import (
    case_studies, export_tables, method_scores, paired_scores, regression_token_observation,
    supplemental_scores, token_comparison_rows, type_case_examples,
)


class ReportingTests(unittest.TestCase):
    def test_pairing_excludes_api_errors_and_ungraded_responses(self):
        def record(value, status="success"):
            return {"status": status, "evaluation": {"correct": value}}
        rows = {
            ("a", "baseline"): record(True), ("a", "regression_hint"): record(False),
            ("b", "baseline"): record(False), ("b", "regression_hint"): record(True),
            ("c", "baseline"): record(True), ("c", "regression_hint"): record(True, "truncated_response"),
        }
        result = paired_scores(rows, ["a", "b", "c"], "baseline", "regression_hint")
        self.assertEqual((result["graded_pairs"], result["excluded_pairs"]), (2, 1))
        self.assertEqual((result["left_only"], result["right_only"]), (1, 1))
        self.assertEqual(result["exact_mcnemar_p"], 1)
        missing = paired_scores(rows, ["a", "b", "c"], "baseline", "oracle_hint")
        self.assertIsNone(missing["difference_right_minus_left"])
        self.assertIsNone(missing["exact_mcnemar_p"])

    def test_missing_usage_is_null_while_a_reported_zero_is_zero(self):
        result = usage_summary([
            {"status": "success", "usage": {"total_token_count": 20, "thoughts_token_count": 0},
             "attempts": [{"usage": {}}, {"usage": {"total_token_count": 20, "thoughts_token_count": 0}}]},
        ])
        self.assertIsNone(result["total_token_count"]["strict_total"])
        self.assertEqual(result["total_token_count"]["known_sum"], 20)
        self.assertEqual(result["total_token_count"]["successful_response_strict_total"], 20)
        self.assertEqual(result["thoughts_token_count"]["successful_response_mean"], 0)
        self.assertEqual(result["thoughts_token_count"]["missing_attempts"], 1)
        self.assertIsNone(result["cached_content_token_count"]["known_sum"])

    def test_failed_response_is_neither_a_math_error_nor_successful_usage(self):
        rows = [{"status": "api_error", "evaluation": {"correct": False}, "usage": {"total_token_count": 50}}]
        result = answer_metrics(rows, 80)
        self.assertEqual(result["graded_responses"], 0)
        self.assertEqual(result["incorrect"], 0)
        self.assertEqual(result["ungraded_or_missing"], 80)
        self.assertIsNone(result["accuracy_on_graded"])
        self.assertIsNone(usage_summary(rows)["total_token_count"]["successful_response_mean"])

    def test_skipped_retry_is_not_a_sent_request(self):
        result = usage_summary([{"status": "success", "usage": {"total_token_count": 10},
                                 "attempts": [{"status": "success", "usage": {"total_token_count": 10}},
                                              {"status": "skipped", "request_skipped": True, "usage": {}}]}])
        self.assertEqual(result["total_token_count"]["all_attempts"], 1)
        self.assertEqual(result["total_token_count"]["skipped_without_request"], 1)
        self.assertEqual(result["total_token_count"]["strict_total"], 10)

    def test_reused_responses_are_not_new_api_usage(self):
        row = {"status": "success", "evaluation": {"correct": True}, "usage": {"total_token_count": 100},
               "response_origin": "reused_exact_request"}
        scores = method_scores({("q", "baseline"): row}, ["q"])
        self.assertEqual(scores["baseline"]["reused_responses"], 1)
        self.assertEqual(scores["baseline"]["usage"]["total_token_count"]["successful_response_strict_total"], 100)
        self.assertIsNone(scores["baseline"]["new_api_usage"]["total_token_count"]["successful_response_strict_total"])
        self.assertIsNone(scores["oracle_hint"]["accuracy_on_graded"])

    def test_reviewed_key_preserves_original_and_checks_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "conflicts.json"
            conflict = {"id": "q", "original_answer": "④", "mathematically_supported_answer": "②", "source_sha256": "source-sha"}
            path.write_text(json.dumps({"records": [conflict]}))
            row = {"id": "q", "method": "baseline", "status": "success", "reference_answer_text": "④",
                   "reference": {"source": {"source_sha256": "source-sha"}},
                   "evaluation": {"correct": False}, "output_text": "최종정답: ②", "problem_text": ""}
            original = json.dumps(row, sort_keys=True)
            reviewed, evidence = supplemental_scores({("q", "baseline"): row}, ["q"], path)
            self.assertTrue(reviewed["q", "baseline"]["evaluation"]["correct"])
            self.assertEqual(json.dumps(row, sort_keys=True), original)
            self.assertFalse(evidence["raw_data_modified"])
            row["reference"]["source"]["source_sha256"] = "different-source"
            with self.assertRaises(ValueError):
                supplemental_scores({("q", "baseline"): row}, ["q"], path)

    def test_pending_condition_stays_empty_in_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            row = {"status": "success", "evaluation": {"correct": True, "predicted_answer": "①"},
                   "reference_answer_text": "①", "usage": {"total_token_count": 12}, "response_origin": "reused_exact_request"}
            latest = {("q", "baseline"): row}
            scores = method_scores(latest, ["q"])
            result = {"test_ids": ["q"], "source_key": scores, "supplemental_key": {"methods": scores, "conflicts": []}}
            export_tables(folder, result, latest, latest)
            with (folder / "question_comparison.csv").open(encoding="utf-8-sig") as stream:
                saved = next(csv.DictReader(stream))
            self.assertEqual(saved["C_status"], "not_run")
            self.assertEqual(saved["C_correct_original"], "")
            self.assertEqual(saved["C_total_tokens"], "")
            with (folder / "summary.csv").open(encoding="utf-8-sig") as stream:
                c = list(csv.DictReader(stream))[2]
            self.assertEqual(c["correct_original_key"], "")
            self.assertEqual(c["accuracy_original_key"], "")

    def test_small_sample_statistics(self):
        self.assertAlmostEqual(exact_mcnemar(0, 5), .0625)
        self.assertEqual(exact_mcnemar(3, 3), 1)
        self.assertIsNone(wilson_interval(0, 0))
        lower, upper = wilson_interval(0, 80)
        self.assertEqual(lower, 0)
        self.assertGreater(upper, 0)
        lower, upper = wilson_interval(80, 80)
        self.assertLess(lower, 1)
        self.assertAlmostEqual(upper, 1)

    def test_transmitted_token_comparison_preserves_rank_and_missing_is_not_zero(self):
        rows = token_comparison_rows({"latex:x": 2.001, "latex:y": 2.001},
                                     {"latex:y": 3.0, "latex:z": 1.0})
        indexed = {row["token"]: row for row in rows}
        self.assertEqual((indexed["latex:x"]["B_rank"], indexed["latex:y"]["B_rank"]), (1, 2))
        self.assertEqual(indexed["latex:y"]["presence"], "공통")
        self.assertEqual(indexed["latex:z"]["presence"], "C만")
        self.assertIsNone(indexed["latex:z"]["B_value"])
        self.assertIsNone(indexed["latex:x"]["C_value"])

    def test_type_cases_distinguish_match_mixture_and_dispersion_from_actual_members(self):
        def member(identifier, label, cluster, split="train", match=False):
            return {"id": identifier, "level": "type", "experiment": "type_spherical",
                    "actual_label": label, "cluster": str(cluster), "split": split,
                    "matches_train_majority": str(match)}
        members = [member("a1", "course/unit/A", 0), member("a2", "course/unit/A", 0),
                   member("b1", "course/unit/B", 1), member("c1", "course/unit/C", 1),
                   member("b2", "course/unit/B", 2), member("test-a", "course/unit/A", 0, "test", True)]
        selected = type_case_examples(members)[0]
        self.assertEqual(selected["matched"]["id"], "test-a")
        self.assertEqual(len({row["actual_label"] for row in selected["mixed"]}), 2)
        self.assertEqual({row["id"] for row in selected["dispersed"]}, {"b1", "b2"})

    def test_case_heading_does_not_claim_B_only_when_C_also_improves(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            metadata = root / "data/processed/metadata.json"
            metadata.parent.mkdir(parents=True)
            metadata.write_text(json.dumps({"records": [{"id": "q", "curriculum": "course", "unit": "unit",
                "subunit": "sub", "type": "type", "source": "source", "original_number": 1, "current_number": 1}]}))
            run_root = root / "results/final_experiment"
            run_root.mkdir(parents=True)
            question = {"id": "q", "changed_original_correctness": True}
            for prefix, value in zip("ABC", (False, True, True)):
                question.update({prefix + "_answer": "①" if value else "②", prefix + "_correct_original": value,
                                 prefix + "_correct_ai_supplemental": value, prefix + "_total_tokens": 10})
            with patch("mathhint_analysis.AnalyzeThreeWay.ROOT", root):
                case_studies(run_root, {"complete": True}, {}, [question])
            text = (run_root / "04_case_studies/selected_cases.md").read_text()
            self.assertNotIn("### 예측 조건에서만 개선", text)
            self.assertIn("B와 C가 모두 정답", text)

    def test_token_interpretation_reports_exact_values_and_top20_omission(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); folder = root / "02_regression"; folder.mkdir()
            with (folder / "question_comparison.csv").open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=["id", "actual_top20", "predicted_top20", "common_top20_count"])
                writer.writeheader()
                writer.writerows([
                    {"id": "trig_2_016", "actual_top20": json.dumps([{"token": r"latex:\sin", "frequency": 4}]),
                     "predicted_top20": json.dumps([{"token": r"latex:\sin", "frequency": 2.5258607864379883}]), "common_top20_count": 18},
                    {"id": "trig_1_043", "actual_top20": json.dumps([{"token": r"latex:\pi", "frequency": 13}]),
                     "predicted_top20": json.dumps([{"token": "latex:0", "frequency": 13.23560905456543}]), "common_top20_count": 8}])
            text = "\n".join(regression_token_observation(root))
            self.assertIn("2.525861", text)
            self.assertIn("13.235609", text)
            self.assertIn("상위20 미포함", text)
            self.assertIn("예측 빈도0과 다르다", text)


if __name__ == "__main__":
    unittest.main()
