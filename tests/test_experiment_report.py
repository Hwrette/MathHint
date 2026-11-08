"""최종 분석에서 분모·누락·재사용·정답표 충돌이 잘못 집계되지 않게 한다."""

import csv
import json
from pathlib import Path
import tempfile
import unittest

from mathhint_analysis.ExperimentMetrics import answer_metrics, exact_mcnemar, usage_summary, wilson_interval
from mathhint_analysis.AnalyzeThreeWay import export_tables, method_scores, paired_scores, supplemental_scores


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


if __name__ == "__main__":
    unittest.main()
