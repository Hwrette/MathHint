"""전체265 보고서의 혼합/분할 집계·재사용·읽기 화면 검증. 실제 API는 호출하지 않는다."""

from copy import deepcopy
import hashlib
from pathlib import Path
import tempfile
import unittest

from mathhint_solver.final_experiment_2.gemini_full265.report import all_scope_metrics, build_full_viewer
from mathhint_solver.final_experiment_2.gemini_full265.verify import preservation_check, reused_scientific_fields_equal, _same_csv_value, saved_metric_checks
from mathhint_solver.final_experiment_2.gemini_comparison.report import summaries, paired_tests, TOKEN_FIELDS
from mathhint_solver.final_experiment_2.gemini_comparison.viewer import METHODS


def question(identifier, split, total, answers=(True, False, True, True)):
    conditions = {}
    for method, correct in zip(METHODS, answers):
        conditions[method["key"]] = {"status": "success", "evaluation": {"correct": correct},
            "correct_ai_supplemental": correct, "response_origin": "reused_exact_request" if split == "test" else "new_api_call",
            "usage": {field: total for field in TOKEN_FIELDS}}
    return {"id": identifier, "split": split, "expected_generation": True, "conditions": conditions}


def saved_rows(questions):
    plan, records = [], []
    for q in questions:
        for method in METHODS:
            identity = {"id": q["id"], "condition": method["condition"], "split": q["split"]}
            plan.append(identity)
            records.append({**deepcopy(q["conditions"][method["key"]]), **identity})
    overall, overall_tokens, overall_pairs = all_scope_metrics(questions)
    split, split_tokens = summaries(questions)
    return plan, records, overall+split, overall_tokens+split_tokens, overall_pairs+paired_tests(questions)


class Full265ReportTests(unittest.TestCase):
    def test_independent_summary_check_rejects_unweighted_combined_mean(self):
        args = list(saved_rows([question("one", "train", 0), question("two", "train", 10), question("three", "test", 100)]))
        checks = saved_metric_checks(*args)
        self.assertTrue(all(c["passed"] for c in checks), [c for c in checks if not c["passed"]])
        combined = next(r for r in args[2] if r["split"] == "all265" and r["condition"] == "A")
        combined["total_token_count_mean"] = (5+100)/2
        failures = [c["check"] for c in saved_metric_checks(*args) if not c["passed"]]
        self.assertIn("csv_all265_A_total_token_count_mean", failures)

    def test_independent_summary_check_rejects_missing_usage_as_zero(self):
        questions = [question("one", "train", 0), question("two", "train", 10), question("three", "test", 100)]
        for q in questions:
            q["conditions"]["regression_hint"]["usage"]["thoughts_token_count"] = None
        args = list(saved_rows(questions))
        self.assertTrue(all(c["passed"] for c in saved_metric_checks(*args)))
        token = next(r for r in args[3] if r["split"] == "all265" and r["condition"] == "B" and r["token_field"] == "thoughts_token_count")
        token.update(mean=0, sum=0, provided_count=3, missing_count=0)
        failures = [c["check"] for c in saved_metric_checks(*args) if not c["passed"]]
        self.assertIn("usage_csv_all265_B_thoughts_token_count_mean", failures)
        self.assertIn("usage_csv_all265_B_thoughts_token_count_provided_count", failures)

    def test_independent_paired_check_rejects_swapped_gain_loss_counts(self):
        questions = [question("one", "train", 10, (True, False, True, True)),
                     question("two", "train", 10, (False, True, True, True)),
                     question("three", "test", 10, (True, False, True, True))]
        args = list(saved_rows(questions))
        self.assertTrue(all(c["passed"] for c in saved_metric_checks(*args)))
        pair = next(r for r in args[4] if r["split"] == "all265" and r["pair"] == "A-B")
        pair["first_correct_second_wrong"], pair["first_wrong_second_correct"] = pair["first_wrong_second_correct"], pair["first_correct_second_wrong"]
        failures = [c["check"] for c in saved_metric_checks(*args) if not c["passed"]]
        self.assertIn("paired_csv_all265_A-B_first_correct_second_wrong", failures)

    def test_aggregate_uses_document_counts_and_preserves_original_split(self):
        questions = [question("train1", "train", 0), question("train2", "train", 10), question("test1", "test", 100)]
        before = deepcopy(questions)
        overall, tokens, pairs = all_scope_metrics(questions)
        a = next(r for r in overall if r["condition"] == "A")
        self.assertEqual((a["split"], a["expected_count"], a["success_count"], a["reused_count"], a["new_success_count"]),
                         ("all265", 3, 3, 1, 2))
        self.assertAlmostEqual(a["total_token_count_mean"], 110/3)
        self.assertNotEqual(a["total_token_count_mean"], (5+100)/2)
        self.assertEqual(a["total_token_count_sum"], 110)
        self.assertTrue(all(r["split"] == "all265" for r in tokens+pairs))
        self.assertEqual(questions, before)
        split_rows, _ = summaries(questions)
        self.assertEqual({r["split"] for r in split_rows}, {"train", "test"})

    def test_missing_usage_keeps_provided_denominator_and_paired_swaps(self):
        questions = [question("one", "train", 30, (True, False, True, True)),
                     question("two", "train", 60, (False, True, True, True)),
                     question("three", "test", 90)]
        for q in questions[:2]:
            q["conditions"]["regression_hint"]["usage"]["total_token_count"] = None
        _, tokens, pairs = all_scope_metrics(questions)
        token = next(r for r in tokens if r["condition"] == "B" and r["token_field"] == "total_token_count")
        self.assertEqual((token["provided_count"], token["missing_count"], token["sum"], token["mean"]), (1, 2, 90, 90))
        pair = next(r for r in pairs if r["pair"] == "A-B")
        self.assertEqual(pair["matched_gradable_count"], 3)
        self.assertEqual(pair["first_wrong_second_correct"], 1)

    def test_reuse_can_change_experiment_identity_but_not_scientific_fields(self):
        source = {"id": "test", "condition": "B", "split": "test", "output_text": "최종정답: ②",
                  "usage": {"total_token_count": None}, "config_id": "old", "response_origin": "new_api_call"}
        reused = {**deepcopy(source), "config_id": "full265", "response_origin": "reused_exact_request"}
        self.assertTrue(reused_scientific_fields_equal(reused, source))
        reused["usage"]["total_token_count"] = 0
        self.assertFalse(reused_scientific_fields_equal(reused, source))
        reused = {**source, "output_text": "최종정답: ③"}
        self.assertFalse(reused_scientific_fields_equal(reused, source))
        self.assertTrue(_same_csv_value("1.0000", "1"))
        self.assertFalse(_same_csv_value("", "0"))

    def test_preservation_manifest_detects_changed_original_and_empty_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "original.txt").write_text("보존할 원문", encoding="utf-8")
            manifest = {"source_commit": "original", "files_sha256": {
                "original.txt": hashlib.sha256((root / "original.txt").read_bytes()).hexdigest()}}
            self.assertTrue(preservation_check(root, manifest)["passed"])
            (root / "original.txt").write_text("다른 원문", encoding="utf-8")
            result = preservation_check(root, manifest)
            self.assertFalse(result["passed"])
            self.assertEqual(result["changed_files"], ["original.txt"])
            self.assertFalse(preservation_check(root, {"files_sha256": {}})["passed"])

    def test_full_viewer_defaults_to_all_and_retains_safe_original_renderer(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            payload = {"config": {"system_instruction": "</script><img src=x onerror=alert(1)>"},
                       "questions": [], "test_ids": [], "train_ids": [], "primary_split": "all"}
            target = build_full_viewer(output, payload)
            text = target.read_text(encoding="utf-8")
            self.assertIn('<option value="all" selected>', text)
            self.assertIn("전체265문항", text)
            self.assertIn("일반화 성능이 아닙니다", text)
            self.assertNotIn("</script><img src=x onerror", text)
            self.assertIn("\\u003c/script", text)
            source = (output / "viewer_assets/viewer.js").read_text(encoding="utf-8")
            self.assertIn("applyFilter(byId.has(initial)?initial:(questions[0]||{}).id);", source)
            self.assertIn("q.split==='test'", source)
            self.assertIn("html:false", source.replace(" ", ""))


if __name__ == "__main__":
    unittest.main()
