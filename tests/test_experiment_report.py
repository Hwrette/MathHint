"""Checks for missing-usage and paired-denominator reporting errors."""

import json
from pathlib import Path
import tempfile
import unittest

from mathhint_analysis.AnalyzeExperiment import adjudicated_scores, analyze, exact_mcnemar, generation_directory, load_solution_review, markdown_report, paired_summary, solution_review_markdown, usage_summary, wilson_interval
from mathhint_analysis.BuildComparisonViewer import MathRenderer


class PairedReportingTests(unittest.TestCase):
    def test_report_labels_follow_saved_training_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "training").mkdir()
            generation = root / "generation"
            generation.mkdir()
            metric = {"mse": 1., "mae": .5, "mean_cosine_similarity": .8}
            cluster_metric = {"n_labels": 1, "adjusted_rand_index": .2, "normalized_mutual_information": .3,
                              "purity": .5, "accuracy_using_train_cluster_majority": .4}
            training = {"generation_id": "dataset", "train_count": 3, "problem_dimensions": 3, "solution_dimensions": 4,
                        "regression": {"architecture": "nn.Linear(3,4)", "optimizer": "SGD", "epochs": 7, "learning_rate": .05,
                                       "metrics": {"test": {key: metric for key in ("raw", "clipped_nonnegative", "training_mean_baseline")}}},
                        "clustering": [{"k": 3, "restarts": 2, "nominal_target_level": "type",
                                        "metrics": {"train": {"type": {"n_labels": 2}}, "test": {"type": cluster_metric}}}]}
            (root / "training/training_summary.json").write_text(json.dumps(training))
            config = {"config_id": "run", "config": {"test_ids": ["q"], "generation_id": "dataset", "model": "model",
                       "thinking_level": "minimal", "temperature": 0, "max_output_tokens": 100}}
            (generation / "config.json").write_text(json.dumps(config))
            rows = [{"id": "q", "method": method, "config_id": "run", "status": "success",
                     "evaluation": {"correct": True}, "usage": {"total_token_count": 10}}
                    for method in ("baseline", "regression_hint")]
            (generation / "responses.jsonl").write_text("\n".join(json.dumps(row) for row in rows))
            result = analyze(root)
            text = markdown_report(result, root, root / "report")
            self.assertIn("학습 3문항 · 테스트 1문항", text)
            self.assertIn("`nn.Linear(3,4)` · SGD · 7epochs", text)
            self.assertIn("k=3에서 2회", text)
            self.assertIn("학습 유형2개, 테스트 유형1개", text)
            self.assertIn("테스트1문항에 방식별1회", text)
            self.assertIn("1 fixed held-out questions", result["limitations"][0])

    def test_viewer_preserves_formula_source_without_optional_converter(self):
        renderer = MathRenderer()
        renderer.convert = None
        text = renderer.rich("조건 $x^2 < 3$", location="question")
        self.assertIn("x^2 &lt; 3", text)
        self.assertIn("[수식 원문]", text)
        self.assertNotIn("<math", text)
        self.assertEqual(renderer.math_count, 0)
        self.assertIn("latex2mathml", renderer.warnings[0]["reason"])

    def test_shared_denominator_excludes_incomplete_response(self):
        def record(value, status="success"):
            return {"status": status, "evaluation": {"correct": value}}

        rows = {
            ("a", "baseline"): record(True), ("a", "regression_hint"): record(False),
            ("b", "baseline"): record(False), ("b", "regression_hint"): record(True),
            ("c", "baseline"): record(True), ("c", "regression_hint"): record(True, "truncated_response"),
        }
        result = paired_summary(rows, ["a", "b", "c"])
        self.assertEqual(result["both_graded_pairs"], 2)
        self.assertEqual(result["excluded_pairs"], 1)
        self.assertEqual(result["baseline_accuracy"], .5)
        self.assertEqual(result["regression_hint_accuracy"], .5)
        self.assertEqual(result["exact_mcnemar_two_sided_p"], 1)

    def test_missing_attempt_usage_prevents_strict_total_but_known_zero_is_zero(self):
        result = usage_summary([
            {"status": "success", "usage": {"total_token_count": 20, "thoughts_token_count": 0},
             "attempts": [{"usage": {}}, {"usage": {"total_token_count": 20, "thoughts_token_count": 0}}]},
        ])
        self.assertIsNone(result["total_token_count"]["strict_total"])
        self.assertEqual(result["total_token_count"]["known_sum"], 20)
        self.assertEqual(result["total_token_count"]["successful_response_strict_total"], 20)
        self.assertEqual(result["total_token_count"]["missing_successful_responses"], 0)
        self.assertEqual(result["thoughts_token_count"]["successful_response_mean"], 0)
        self.assertEqual(result["thoughts_token_count"]["missing_attempts"], 1)
        self.assertIsNone(result["cached_content_token_count"]["known_sum"])

    def test_exact_p_value_uses_discordant_pairs(self):
        self.assertEqual(exact_mcnemar(0, 0), 1)
        self.assertAlmostEqual(exact_mcnemar(0, 5), .0625)
        self.assertEqual(exact_mcnemar(3, 3), 1)

    def test_wilson_empty_and_boundary(self):
        self.assertIsNone(wilson_interval(0, 0))
        lower, upper = wilson_interval(0, 80)
        self.assertEqual(lower, 0)
        self.assertGreater(upper, 0)
        lower, upper = wilson_interval(80, 80)
        self.assertLess(lower, 1)
        self.assertAlmostEqual(upper, 1)

    def test_alternate_hint_runs_stay_separate_and_reused_control_is_not_new_usage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "training").mkdir()
            (root / "training/training_summary.json").write_text(json.dumps({"generation_id": "dataset"}))
            for folder, hint_correct, config_id in (("generation", False, "old"), ("generation_top_tokens", True, "new")):
                target = root / folder
                target.mkdir()
                config = {"config_id": config_id, "config": {"test_ids": ["q"], "generation_id": "dataset",
                           "model": "model", "thinking_level": "minimal", "temperature": 0,
                           "max_output_tokens": 100, "hint_mode": "full_vector" if folder == "generation" else "top_tokens", "hint_top_k": 20}}
                (target / "config.json").write_text(json.dumps(config))
                rows = []
                for method, correct in (("baseline", True), ("regression_hint", hint_correct)):
                    row = {"id": "q", "method": method, "config_id": config_id, "status": "success",
                           "evaluation": {"correct": correct}, "unit": "unit", "subject": "subject",
                           "usage": {"total_token_count": 100}, "attempts": [{"usage": {"total_token_count": 100}}]}
                    if config_id == "new" and method == "baseline":
                        row.update(response_origin="reused_control", provenance={"source_directory": "generation", "source_config_id": "old", "source_record_sha256": "sha"})
                    rows.append(row)
                (target / "responses.jsonl").write_text("\n".join(json.dumps(row) for row in rows))
            old, new = analyze(root), analyze(root, "generation_top_tokens")
            self.assertEqual(old["paired"]["regression_hint_accuracy"], 0)
            self.assertEqual(new["paired"]["regression_hint_accuracy"], 1)
            self.assertEqual(new["control_reuse"]["count"], 1)
            self.assertEqual(new["control_reuse"]["new_condition_requests_expected"], 1)
            self.assertEqual(new["methods"]["baseline"]["usage"]["total_token_count"]["successful_response_strict_total"], 100)
            self.assertIsNone(new["methods"]["baseline"]["incremental_usage"]["total_token_count"]["strict_total"])
            self.assertEqual(new["methods"]["regression_hint"]["incremental_usage"]["total_token_count"]["strict_total"], 100)

    def test_generation_selector_cannot_escape_run_root(self):
        for name in ("", "..", "../generation", "/tmp/run", "generation/subfolder"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                generation_directory(Path("/tmp/run"), name)

    def test_skipped_retry_is_not_counted_as_sent_request_or_missing_usage(self):
        result = usage_summary([{"status": "success", "usage": {"total_token_count": 10},
                                 "attempts": [{"status": "success", "usage": {"total_token_count": 10}},
                                              {"status": "skipped", "request_skipped": True, "usage": {}}]}])
        self.assertEqual(result["total_token_count"]["all_attempts"], 1)
        self.assertEqual(result["total_token_count"]["skipped_without_request"], 1)
        self.assertEqual(result["total_token_count"]["strict_total"], 10)

    def test_reviewed_key_is_supplemental_and_source_hash_guarded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "audit").mkdir()
            conflict = {"id": "q", "original_answer": "④", "mathematically_supported_answer": "②", "source_sha256": "source-sha"}
            (root / "audit/audited_answer_conflicts.json").write_text(json.dumps({"records": [conflict]}))
            row = {"id": "q", "method": "baseline", "status": "success", "reference_answer_text": "④",
                   "reference": {"source": {"source_sha256": "source-sha"}},
                   "evaluation": {"correct": False}, "output_text": "최종정답: ②", "problem_text": ""}
            original = json.dumps(row, sort_keys=True)
            result = adjudicated_scores(root, {("q", "baseline"): row}, ["q"])
            self.assertEqual(result["methods"]["baseline"]["correct"], 1)
            self.assertEqual(json.dumps(row, sort_keys=True), original)
            self.assertFalse(result["raw_data_or_responses_modified"])
            row["reference"]["source"]["source_sha256"] = "different-source"
            with self.assertRaises(ValueError):
                adjudicated_scores(root, {("q", "baseline"): row}, ["q"])

    def test_review_ratings_cannot_be_combined_with_another_experiment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "solution_review"
            folder.mkdir()
            path = folder / "solution_review_summary.json"
            path.write_text(json.dumps({"config_id": "old"}))
            result = load_solution_review(root, root / "generation_top_tokens", "new", "sha")
            self.assertEqual(result["status"], "excluded_different_generation")
            self.assertNotIn("summary", result)
            with self.assertRaises(ValueError):
                load_solution_review(root, root / "generation_top_tokens", "new", "sha", path)
            path.write_text(json.dumps({"config_id": "new", "source_snapshot": {"sha256": "earlier"}}))
            result = load_solution_review(root, root / "generation_top_tokens", "new", "sha", path)
            self.assertEqual(result["status"], "included_earlier_snapshot")
            self.assertFalse(result["review_response_snapshot_matches_current"])

    def test_primary_appropriateness_uses_math_only_not_scope_uncertainty(self):
        row = {"total_eligible_solutions": 80,
               "overall": {"appropriate": 0, "inappropriate": 5, "uncertain": 75, "reviewed_count": 80, "appropriate_rate_on_reviewed": 0},
               "mathematical_appropriateness": {"appropriate": 76, "inappropriate": 4, "uncertain": 0, "reviewed_count": 80, "appropriate_rate_on_reviewed": .95},
               "criteria": {"curriculum_scope": {"appropriate": 0, "inappropriate": 1, "uncertain": 79, "reviewed_count": 80}}}
        result = {"solution_review": {"path": "/tmp/review/summary.json", "review_response_snapshot_matches_current": True,
                                      "summary": {"review_kinds": {"ai_suggestion": {"baseline": row}}}}}
        text = "\n".join(solution_review_markdown(result, Path("/tmp/report")))
        self.assertIn("| 80/80 | 76 | 4 | 0 | 95.00% | 0 |", text)
        self.assertIn("| 0 | 1 | 79 | 0 |", text)
        self.assertIn("블라인드 평가가 아니다", text)


if __name__ == "__main__":
    unittest.main()
