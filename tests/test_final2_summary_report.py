"""종합 보고서의 저장 자료 해석만 검사한다. 학습·API·실제 결과 쓰기는 없다."""

import csv
from pathlib import Path
import tempfile
import unittest

from mathhint_learning.final_experiment_2 import report


def save_csv(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(dict.fromkeys(key for row in values for key in row)))
        writer.writeheader()
        writer.writerows(values)


def question(identifier, a=True, b=True):
    row = {"id": identifier, "split": "test", "original_answer": "②", "ai_supplemental_answer": "",
           "answer_key_conflict": False, "changed_answers": False}
    for c, correct in zip("ABCD", (a, b, None, None)):
        row.update({c + "_status": "success" if c in "AB" else "not_run",
                    c + "_answer": "②" if correct else "①", c + "_correct_original": correct,
                    c + "_correct_ai_supplemental": correct})
        for field, value in (("prompt_token_count", 100 if c == "A" else 130),
                             ("candidates_token_count", 100 if c == "A" else 50),
                             ("total_token_count", 200 if c == "A" else 180)):
            row[c + "_" + field] = value if c in "AB" else None
    return row


class SummaryInterpretationTests(unittest.TestCase):
    def test_model_findings_keep_metric_tradeoffs_and_overlap_counts_distinct(self):
        values = []
        for name, p20, common, mse, mae, cosine in (
                ("training_mean", .4, 8, 2, .3, .7), ("regression", .6, 12, 1, .2, .9),
                ("deep_learning", .61, 12.2, 1.2, .15, .8)):
            values.append(dict(model=name, label=name, split="test", precision_at_20=p20,
                               mean_common_top20_count=common, mse=mse, mae=mae, cosine_similarity=cosine, n="10"))
        text = "\n".join(report._model_findings(values))
        self.assertIn("P@20 차이 +0.200000", text)
        self.assertIn("MSE: 선형, MAE: MLP, 코사인: 선형, P@20: MLP", text)
        self.assertIn("공통 10문항", text)
        self.assertIn("MLP−선형 +2.00개", text)
        self.assertIn("수학 정답률이 아니다", text)

    def test_accuracy_uses_matched_grades_but_tokens_include_ungradable_successes(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            questions = [question("gain", False, True), question("loss", True, False),
                         question("ungraded", True, None), question("pending", True, None)]
            questions[-1].update(B_status="not_run", B_total_token_count=9999)
            questions[2]["B_candidates_token_count"] = None
            save_csv(base / "gemini_comparison/question_comparison.csv", questions)
            values = [dict(split="test", condition=c, pending_count=1 if c == "B" else 0,
                           failed_count=0, accuracy_ai_supplemental=.75, correct_count_ai_supplemental=3,
                           graded_count=4) for c in "ABCD"]
            before = (base / "gemini_comparison/question_comparison.csv").read_bytes()
            text = "\n".join(report._api_interpretation(base, values))
            self.assertIn("공통 채점 n=2/4 (제외 2), A 1/2→B 1/2", text)
            self.assertIn("오답→정답 1개, 정답→오답 1개", text)
            self.assertIn("B 미완료 1·실패 0", text)
            self.assertIn("입력 +30.00토큰(n=3), 출력 -50.00토큰(n=2), 전체 -20.00토큰(n=3)", text)
            self.assertIn("AI 보조 정답표 기준은 A 3/4 (75.00%)", text)
            self.assertEqual(before, (base / "gemini_comparison/question_comparison.csv").read_bytes())

    def test_zero_matched_grades_can_still_have_saved_token_comparison(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            save_csv(base / "gemini_comparison/question_comparison.csv", [question("ungraded", None, None)])
            text = "\n".join(report._api_interpretation(base, []))
            self.assertIn("공통 채점 n=0/1", text)
            self.assertIn("전체 -20.00토큰(n=1)", text)

    def test_complete_equal_accuracy_keeps_swapped_answers_and_input_cost_visible(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            questions = [question("gain", False, True), question("loss", True, False)]
            for row in questions:
                for condition in "BCD":
                    row.update({condition + "_status": "success",
                                condition + "_correct_original": row["B_correct_original"],
                                condition + "_prompt_token_count": 130,
                                condition + "_candidates_token_count": 170,
                                condition + "_total_token_count": 300})
            save_csv(base / "gemini_comparison/question_comparison.csv", questions)
            values = [dict(split="test", condition=c, success_count=2, graded_count=2,
                           correct_count=1, pending_count=0, failed_count=0) for c in "ABCD"]
            text = "\n".join(report._api_interpretation(base, values))
            self.assertIn("정답 수가 모두 1개로 같았다", text)
            self.assertIn("개선·악화가 상쇄", text)
            self.assertIn("B +50.00%, C +50.00%, D +50.00%", text)
            self.assertIn("실패·재시도 비용", text)

    def test_cases_use_canonical_change_flags_and_separate_key_conflict_and_review(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            equivalent = question("equivalent")
            equivalent.update(A_answer="②", B_answer="2")
            conflict = question("conflict", False, False)
            conflict.update(answer_key_conflict=True, original_answer="④", ai_supplemental_answer="②",
                            A_answer="②", B_answer="②", A_correct_ai_supplemental=True, B_correct_ai_supplemental=True)
            change = question("change", True, False)
            change["changed_answers"] = True
            reasoning = question("reasoning", True, True)
            save_csv(base / "gemini_comparison/question_comparison.csv", [equivalent, conflict, change, reasoning])
            save_csv(base / "gemini_comparison/review/status.csv", [dict(id="reasoning", split="test", condition="B",
                     api_status="success", math_status="inappropriate", final_answer_correct_original=True,
                     review_status="suspected_error", error_step="계수 비교", reason="계수 비교에서 a를 a+1로 잘못 썼다.",
                     human_confirmed=False)])
            case_path = base / "gemini_comparison/case_reports/reasoning.md"
            case_path.parent.mkdir(parents=True)
            case_path.write_text("저장된 사례", encoding="utf-8")
            text = "\n".join(report._case_findings(base))
            self.assertIn("두 개 이상인 4문항", text)
            self.assertIn("최종 답 변화는 1문항", text)
            self.assertNotIn("**equivalent**", text)
            self.assertIn("원본 정답 ④ / AI 보조 대안 ②", text)
            self.assertIn("보조 기준에서 A 정답, B 정답", text)
            self.assertIn("**change**: A ②(원본 정답), B ①(원본 오답)", text)
            self.assertIn("계수 비교에서 a를 a+1로 잘못 썼다", text)
            self.assertIn("사람 확정: False", text)
            self.assertIn("gemini_comparison/case_reports/reasoning.md", text)
            self.assertNotIn("gemini_comparison/case_reports/conflict.md", text)
            self.assertIn("gemini_comparison/report.html#conflict", text)

    def test_no_saved_rows_do_not_invent_findings(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            self.assertEqual(report._api_interpretation(base, []), [])
            self.assertEqual(report._model_findings([]), [])
            self.assertIn("아직 저장된 문항별 비교가 없다", "\n".join(report._case_findings(base)))


if __name__ == "__main__":
    unittest.main()
