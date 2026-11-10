"""네 조건의 미완료·사용량·대응 검정과 원문 안전 표시를 보호한다."""

import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from mathhint_solver.AnswerEvaluation import evaluate_answer, extract_reference
from mathhint_solver.final_experiment_2.gemini_comparison import report, review, viewer


def question(answers, statuses=None):
    statuses = statuses or ["success"] * 4
    conditions = {}
    for method, correct, status in zip(viewer.METHODS, answers, statuses):
        conditions[method["key"]] = {"condition": method["condition"], "status": status,
            "evaluation": {"correct": correct}, "correct_ai_supplemental": correct,
            "usage": {key: None for key in report.TOKEN_FIELDS}, "output_text": "최종정답: ②"}
    return {"id": "q", "split": "test", "expected_generation": True, "conditions": conditions}


class FourWayReportTests(unittest.TestCase):
    def test_presentation_blank_cleanup_preserves_meaningful_markdown_hardbreaks(self):
        original = "풀이 첫 줄  \n   \n\t\r\n다음 줄  \n끝 한 공백 \n"
        self.assertEqual(review.clean_presentation_blank_lines(original), "풀이 첫 줄  \n\n\r\n다음 줄  \n끝 한 공백\n")

    def test_missing_failures_and_ungradable_are_separate_from_wrong_and_zero_usage(self):
        q = question([True, False, None, None], ["success", "api_error", "success", "not_run"])
        q["conditions"]["baseline"]["usage"]["total_token_count"] = 100
        rows, tokens = report.summaries([q])
        a, b, c, d = rows
        self.assertEqual((a["correct_count"], a["accuracy_graded"]), (1, 1))
        self.assertEqual((b["failed_count"], b["incorrect_count"]), (1, 0))
        self.assertIsNone(b["accuracy_graded"])
        self.assertEqual(c["ungradable_count"], 1)
        self.assertIsNone(c["accuracy_graded"])
        self.assertEqual(d["pending_count"], 1)
        self.assertIsNone(d["total_token_count_sum"])
        self.assertIsNone(a["thoughts_token_count_sum"])
        self.assertEqual(next(r for r in tokens if r["condition"] == "A" and r["token_field"] == "total_token_count")["provided_count"], 1)

    def test_exact_paired_mcnemar_and_holm_use_only_both_graded(self):
        rows = report.paired_tests([question([True, False, True, True]) for _ in range(10)]
                                  + [question([True, None, True, True])])
        ab = next(row for row in rows if row["pair"] == "A-B")
        self.assertEqual(ab["matched_gradable_count"], 10)
        self.assertEqual(ab["excluded_count"], 1)
        self.assertAlmostEqual(ab["p_exact_mcnemar"], 2 / 2 ** 10)
        self.assertGreaterEqual(ab["p_holm_within_split"], ab["p_exact_mcnemar"])
        ac = next(row for row in rows if row["pair"] == "A-C")
        self.assertEqual((ac["discordant_count"], ac["p_exact_mcnemar"]), (0, 1))

    def test_token_deltas_exclude_failed_responses_with_provided_usage(self):
        q = question([True, None, True, True], ["success", "truncated_response", "success", "success"])
        q.update(metadata={}, reference_answer="②", answer_key_conflict=False, ai_supplemental_answer=None,
                 changed_correctness=False, changed_answers=False, case_tags=[])
        for method, total in zip(viewer.METHODS, (100, 30, 140, 0)):
            q["conditions"][method["key"]]["usage"]["total_token_count"] = total
        row = report.question_rows([q])[0]
        self.assertEqual(row["B_total_token_count"], 30)
        self.assertIsNone(row["B_minus_A_total_tokens"])
        self.assertIsNone(row["C_minus_B_total_tokens"])
        self.assertEqual(row["C_minus_A_total_tokens"], 40)
        self.assertEqual(row["D_minus_A_total_tokens"], -100)
        q["conditions"]["regression_hint"]["status"] = "success"
        row = report.question_rows([q])[0]
        self.assertEqual(row["B_minus_A_total_tokens"], -70)
        self.assertEqual(row["C_minus_B_total_tokens"], 110)

    def test_empty_mcnemar_does_not_invent_a_p_value(self):
        rows = report.paired_tests([question([None] * 4, ["not_run"] * 4)])
        self.assertTrue(all(row["p_exact_mcnemar"] is None for row in rows))

    def test_case_cleanup_only_removes_previously_indexed_generated_known_ids(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            q = question([None] * 4, ["not_run"] * 4)
            q.update(metadata={}, problem_text="문제", reference_answer="②", reference_solution="풀이",
                     changed_answers=False, answer_key_conflict=False, methods=list(viewer.METHODS))
            old_index = review.write_cases(output, [q])
            folder = output / "case_reports"
            self.assertTrue((folder / "q.md").is_file())
            (folder / "manual.md").write_text("# 개인 기록\n", encoding="utf-8")
            (folder / "q2.md").write_text("# 수동 작성 문서\n", encoding="utf-8")
            (folder / "unknown.md").write_text(
                "# unknown · 네 조건 비교\n\n[수식 비교 화면](../report.html#unknown) · [사례 목록](README.md)\n\n자동 선별 사유: 과거 사례\n",
                encoding="utf-8")
            extra = [{**old_index[0], "id": identifier, "case_path": f"{identifier}.md"} for identifier in ("q2", "unknown")]
            review.write_csv(folder / "index.csv", old_index + extra)
            for response in q["conditions"].values():
                response.update(status="success", evaluation={"correct": True}, review={"math_status": "appropriate"})
            q2 = {**q, "id": "q2"}
            self.assertEqual(review.write_cases(output, [q, q2]), [])
            self.assertFalse((folder / "q.md").exists())
            self.assertEqual((folder / "manual.md").read_text(encoding="utf-8"), "# 개인 기록\n")
            self.assertEqual((folder / "q2.md").read_text(encoding="utf-8"), "# 수동 작성 문서\n")
            self.assertTrue((folder / "unknown.md").is_file())

    def test_curated_alternative_flag_selects_filter_tag_and_case(self):
        with tempfile.TemporaryDirectory() as temporary:
            q = question([True] * 4)
            q.update(metadata={}, problem_text="문제", reference_answer="②", reference_solution="풀이",
                     changed_answers=False, answer_key_conflict=False, methods=list(viewer.METHODS))
            q["conditions"]["baseline"]["review"] = {
                "review_status": "AI_assisted_appropriate", "math_status": "appropriate", "alternative_solution": True}
            self.assertEqual(review.select_tags(q), ["possible_alternative"])
            index = review.write_cases(Path(temporary), [q])
            self.assertEqual(index[0]["case_tags"], "possible_alternative")
            self.assertIn(review.CASE_LABELS["possible_alternative"], (Path(temporary) / "case_reports/q.md").read_text(encoding="utf-8"))
            q["conditions"]["baseline"]["review"]["alternative_solution"] = False
            self.assertEqual(review.select_tags(q), [])

    def fixture(self, root):
        metadata = [{"id": identifier, "curriculum": "수학", "unit": "단원", "subunit": "세부", "type": "유형", "answer_text": "②"}
                    for identifier in ("train_q", "test_q")]
        def save(path, data):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        save(root / "data/processed/metadata.json", {"records": metadata})
        for split, identifier in (("train", "train_q"), ("test", "test_q")):
            save(root / f"data/processed/splits/{split}.json", [identifier])
            for region, text in (("problems", r"문제 $\frac{1}{2}$ ① $1$ ② $2$ ③ $3$ ④ $4$ ⑤ $5$"),
                                 ("solutions", r"원본 풀이 $\lim_{x\to0}x=0$")):
                path = root / f"data/processed/{region}/{identifier}.txt"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
        problem = (root / "data/processed/problems/test_q.txt").read_text()
        item = {"id": "test_q", "condition": "A", "method": "baseline", "input_text": problem,
                "problem_text": problem, "system_instruction": "지시", "split": "test"}
        reference = extract_reference(metadata[1], problem)
        record = {**item, "status": "success", "output_text": "최종정답: ②",
                  "evaluation": evaluate_answer("최종정답: ②", reference, problem)}
        return item, record

    def test_original_problem_mismatch_is_rejected_and_no_training_or_sdk_is_needed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            item, record = self.fixture(root)
            before = (root / "data/processed/problems/test_q.txt").read_bytes()
            questions, ids = report.build_questions(root, root / "output", {"split": "test"}, [item], [record])
            self.assertEqual(ids, {"train": ["train_q"], "test": ["test_q"]})
            self.assertEqual(questions[1]["conditions"]["baseline"]["evaluation"]["correct"], True)
            self.assertEqual((root / "data/processed/problems/test_q.txt").read_bytes(), before)
            with self.assertRaisesRegex(ValueError, "문제 원문"):
                report.build_questions(root, root / "output", {"split": "test"}, [item], [{**record, "problem_text": "변형 문제"}])

    def test_correct_answer_still_deferred_and_error_review_requires_exact_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            item, record = self.fixture(root)
            output = root / "output"
            questions, _ = report.build_questions(root, output, {"split": "test"}, [item], [record])
            rows = review.build_reviews(root, output, questions)
            first = next(row for row in rows if row["condition"] == "A")
            self.assertEqual(first["review_status"], "deferred")
            self.assertTrue(first["final_answer_correct_original"])
            bad = {"id": "test_q", "condition": "A", "response_sha256": review.text_hash(record["output_text"]),
                   "review_status": "confirmed_error", "math_status": "inappropriate", "error_step": "잘못된 단계",
                   "reason": "근거", "evidence_quotes": ["응답에 없는 인용"]}
            (output / "review/curated_reviews.json").write_text(json.dumps({"records": [bad]}))
            with self.assertRaisesRegex(ValueError, "인용"):
                review.build_reviews(root, output, questions)

    def test_four_condition_viewer_preserves_original_strings_and_blocks_html_injection(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            attack = '</script><script>window.injected=1</script><img onerror="x">'
            q = question([True, False, False, False])
            q.update(metadata={}, problem_text=r"$\frac{1}{2}$" + attack, reference_answer="②", reference_solution="풀이", case_tags=[])
            q["conditions"]["baseline"].update(provenance={"api_key": "must-not-appear"}, output_text=attack)
            payload = {"questions": [q], "methods": list(viewer.METHODS), "config": {"api_key": "must-not-appear"},
                       "test_ids": ["q"], "train_ids": [], "experiment_name": "test", "links": {}}
            path = viewer.build(output, payload)
            text = path.read_text()
            self.assertNotIn("must-not-appear", text)
            self.assertNotIn(attack, text)
            embedded = json.loads(re.search(r'<script id="viewer-data" type="application/json">(.*?)</script>', text, re.S).group(1))
            self.assertEqual(embedded["questions"][0]["problem_text"], q["problem_text"])
            self.assertEqual(len(embedded["methods"]), 4)
            self.assertIn("connect-src 'none'", text)
            self.assertIn("field-curriculum", text)


if __name__ == "__main__":
    unittest.main()
