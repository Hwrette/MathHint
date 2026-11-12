"""Saved-only repeat statistics, independent answer review and safe-reader wiring."""

import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest

from mathhint_solver.final_experiment_2.final_followup import report
from mathhint_solver.final_experiment_2.final_followup.viewer import _script
from mathhint_solver.CompareGeneration import USAGE_FIELDS


class RepeatReportingTests(unittest.TestCase):
    def test_sample_sd_and_missing_usage_are_distinct(self):
        self.assertEqual(report._stats([]), {"provided_count": 0, "mean": None, "min": None,
                                            "max": None, "std": None, "sum": None})
        self.assertIsNone(report._stats([None, 7])["std"])
        values = report._stats([None, 2, 6])
        self.assertEqual(values["provided_count"], 2)
        self.assertEqual(values["mean"], 4)
        self.assertAlmostEqual(values["std"], math.sqrt(8))

    def test_output_reduction_quality_keeps_unknown_answers_and_validity_separate(self):
        def pair(delta, first, second, math_first, math_second, received=True):
            return {"contrast": "E-A", "both_received": received,
                    "candidates_token_count_difference": delta,
                    "first_correct": first, "second_correct": second,
                    "first_math_status": math_first, "second_math_status": math_second}
        pairs = [pair(-10, False, True, "inappropriate", "appropriate"),
                 pair(-5, True, False, "appropriate", "inappropriate"),
                 pair(-3, True, True, "appropriate", "appropriate"),
                 pair(-1, None, False, "uncertain", "inappropriate"),
                 pair(7, False, True, "inappropriate", "appropriate"),
                 pair(0, True, True, "appropriate", "appropriate"),
                 pair(-9, False, True, "inappropriate", "appropriate", received=False),
                 pair(None, False, True, "inappropriate", "appropriate")]
        rows = report.output_reduction_quality(pairs)
        self.assertEqual(len(rows), 5)
        selected = next(r for r in rows if r["contrast"] == "E-A")
        self.assertEqual(selected["provided_pairs"], 6)
        self.assertEqual(selected["shorter_pairs"], 4)
        for prefix in ("answer", "math"):
            self.assertEqual([selected[prefix + "_" + name] for name in ("gains", "losses", "same", "unknown")],
                             [1, 1, 1, 1])
            self.assertEqual(sum(selected[prefix + "_" + name] for name in ("gains", "losses", "same", "unknown")),
                             selected["shorter_pairs"])
        self.assertTrue(all(r["shorter_pairs"] == 0 for r in rows if r["contrast"] != "E-A"))

    def _fixture(self, repeat=1, grade=None):
        item = {"id": "trig_1_044", "condition": "B", "repeat": repeat,
                "request_id": f"trig_1_044__B__r{repeat}", "split": "train", "input_text": "problem+hint",
                "problem_text": "problem", "request_sha256": "frozen", "reference_answer_text": "③"}
        saved = {**item, "status": "success", "output_text": "최종정답: 12 (선택지 오류)",
                 "evaluation": {"predicted_answer": "12 (선택지 오류)", "correct": grade},
                 "usage": {field: None for field in USAGE_FIELDS}}
        return item, saved

    def test_actual_new_abstention_requires_new_specific_review(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            item, saved = self._fixture()
            rows, objects = report.build_rows(output, output, {}, [item], [saved])
            self.assertIsNone(rows[0]["correct_scored"])
            self.assertEqual(rows[0]["math_status"], "uncertain")
            review = {"id": item["id"], "condition": "B", "repeat": 1,
                      "response_sha256": hashlib.sha256(saved["output_text"].encode()).hexdigest(),
                      "review_status": "suspected_error", "math_status": "inappropriate", "human_confirmed": False,
                      "reason": "x=1/2의 최대값 교점을 누락했고 실제 답은13이다.", "error_step": "경계 교점 누락",
                      "evidence_quotes": ["최종정답: 12"], "final_answer_correct": False}
            (output / "review").mkdir()
            (output / "review/curated_reviews.json").write_text(json.dumps({"records": [review]}, ensure_ascii=False))
            rows, objects = report.build_rows(output, output, {}, [item], [saved])
            self.assertIs(rows[0]["correct_scored"], False)
            self.assertEqual(rows[0]["grade_source"], "independent_new_AI_answer_review")
            self.assertIsNone(objects[item["id"], "B", 1]["evaluation_raw"]["correct"])
            self.assertIsNone(saved["evaluation"]["correct"])

    def test_comparative_case_prose_rejects_stale_new_response_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "review").mkdir()
            self.assertEqual(report.case_findings(output, []), {})
            records = [{"request_id": f"trig_1_044__{condition}__r{repeat}", "status": "success",
                        "output_text": f"NEW {condition} repeat {repeat}"}
                       for condition in "ABCD" for repeat in (1, 2, 3)]
            finding = {"AD": "A와 D의 실제 새 식을 대조한 요약.", "BC": "B와 C의 새 응답 비교.",
                       "human_confirmed": False,
                       "response_sha256s": {r["request_id"]: hashlib.sha256(r["output_text"].encode()).hexdigest() for r in records}}
            path = output / "review/curated_reviews.json"
            path.write_text(json.dumps({"records": [], "case_findings": {"trig_1_044": finding}}, ensure_ascii=False))
            self.assertEqual(report.case_findings(output, records)["trig_1_044"]["AD"], finding["AD"])
            records[-1]["output_text"] += " CHANGED"
            with self.assertRaisesRegex(ValueError, "Stale or missing new response"):
                report.case_findings(output, records)

    def test_review_cannot_be_transferred_to_different_repeat_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            item, saved = self._fixture()
            (output / "review").mkdir()
            (output / "review/curated_reviews.json").write_text(json.dumps({"records": [
                {"id": item["id"], "condition": "B", "repeat": 1, "response_sha256": "wrong",
                 "evidence_quotes": ["not in new output"]}]}))
            with self.assertRaisesRegex(ValueError, "response hash"):
                report.build_rows(output, output, {}, [item], [saved])

    def test_shared_math_renderer_adds_repeat_navigation_without_enabling_html(self):
        source = _script()
        self.assertIn("html:false", source)
        self.assertIn("trust:false", source)
        self.assertIn("setRepeat:function", source)
        self.assertIn("q.available_conditions", source)
        self.assertIn("evaluation_raw:row.evaluation_raw", source)

    def test_three_repeat_summary_preserves_nulls_and_math_answer_separation(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            plans, saved = zip(*(self._fixture(r, True) for r in (1, 2, 3)))
            saved = [dict(r) for r in saved]
            for r, value in zip(saved, (2, None, 6)):
                r["usage"] = {**r["usage"], "candidates_token_count": value}
            rows, _ = report.build_rows(p, p, {}, list(plans), saved)
            cell = report.grouped_summary(rows, ["trig_1_044"], "B")[0]
            self.assertEqual(cell["correct_count"], 3)
            self.assertEqual(cell["reviewed_math_count"], 0)
            self.assertEqual(cell["math_uncertain_count"], 3)
            self.assertEqual(cell["candidates_token_count_provided_count"], 2)
            self.assertEqual(cell["candidates_token_count_mean"], 4)
            self.assertAlmostEqual(cell["candidates_token_count_std"], math.sqrt(8))
            self.assertIsNone(cell["thoughts_token_count_mean"])

    def test_received_truncation_counts_once_keeps_actual_usage_and_ungraded_answer(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            plans, saved = zip(*(self._fixture(r, True) for r in (1, 2, 3)))
            saved = [dict(r) for r in saved]
            for row, value in zip(saved, (2, 8188, 6)):
                row["usage"] = {**row["usage"], "candidates_token_count": value}
            partial = saved[1]
            partial.update(status="truncated_response", evaluation={"predicted_answer": None, "correct": None})
            review = {"id": partial["id"], "condition": "B", "repeat": 2,
                      "response_sha256": hashlib.sha256(partial["output_text"].encode()).hexdigest(),
                      "math_status": "inappropriate", "review_status": "suspected_error",
                      "reason": "Partial proof has a concrete wrong count; no submitted final answer.",
                      "error_step": "wrong intersection count", "evidence_quotes": ["12"],
                      "final_answer_correct": False}
            (p / "review").mkdir()
            (p / "review/curated_reviews.json").write_text(json.dumps({"records": [review]}))
            rows, objects = report.build_rows(p, p, {}, list(plans), saved)
            cell = report.grouped_summary(rows, ["trig_1_044"], "B")[0]
            self.assertEqual(cell["received_count"], 3)
            self.assertEqual(cell["success_count"], 2)
            self.assertEqual(cell["truncated_count"], 1)
            self.assertEqual(cell["pending_count"], 0)
            self.assertEqual(cell["failed_count"], 0)
            self.assertEqual(cell["graded_count"], 2)
            self.assertEqual(cell["math_inappropriate_count"], 1)
            self.assertEqual(cell["candidates_token_count_provided_count"], 3)
            self.assertEqual(cell["candidates_token_count_mean"], 2732)
            self.assertIsNone(objects[partial["id"], "B", 2]["correct_scored"])


if __name__ == "__main__":
    unittest.main()
