"""최종 답의 판독, 보기 값 매핑, 미판독 상태를 검사한다."""

import unittest

from mathhint_solver.AnswerEvaluation import evaluate_answer, extract_reference, numeric_constant


class AnswerEvaluationTests(unittest.TestCase):
    problem = "값은?\n① $1$\t② $3$\t③ $4$\n④ $5$\t⑤ $6$"

    def test_reference_bold_integer_and_choice_provenance(self):
        reference = extract_reference({"id": "diff_3_005", "answer_text": r"$\mathbf{9}$"})
        self.assertEqual(reference["numeric_value"], 9)
        self.assertEqual(reference["source"]["id"], "diff_3_005")
        choice = extract_reference({"answer_text": "②"}, self.problem)
        self.assertEqual(choice["choice"], 2)
        self.assertEqual(choice["numeric_value"], 3)

    def test_explicit_choice_and_explicit_bare_index(self):
        self.assertTrue(evaluate_answer("계산 중 ⑤를 검토했다.\n최종정답: ②", "②", self.problem)["correct"])
        self.assertFalse(evaluate_answer("풀이\n최종정답: 3", "②", self.problem)["correct"])
        self.assertTrue(evaluate_answer("최종정답: 2번", "②", self.problem)["correct"])

    def test_boxed_value_maps_to_correct_option_value_not_option_index(self):
        grade = evaluate_answer(r"결론은 $\boxed{3}$", "②", self.problem)
        self.assertTrue(grade["correct"])
        self.assertEqual(grade["predicted_kind"], "value")

    def test_equivalent_fraction_and_radical(self):
        self.assertTrue(evaluate_answer(r"최종정답: $\frac{22}{2}$", "$11$")["correct"])
        problem = r"① $- \frac{\sqrt{3}}{3}$ ② $0$ ③ $1$ ④ $2$ ⑤ $3$"
        grade = evaluate_answer(r"$\boxed{-1/\sqrt{3}}$", "①", problem)
        self.assertTrue(grade["correct"])
        self.assertAlmostEqual(numeric_constant(r"\frac{4}{3}\pi"), 4 * 3.141592653589793 / 3)

    def test_final_marker_beats_intermediate_box_and_later_correction_wins(self):
        output = "중간 계산 \\boxed{9}\n최종정답: 9\n검산으로 수정\n최종정답: $11$"
        self.assertTrue(evaluate_answer(output, "$11$")["correct"])

    def test_no_numbers_from_working_or_options_are_guessed(self):
        grade = evaluate_answer("① 1, ② 3, ③ 4, ④ 5, ⑤ 6\n중간 계산은 3이다.", "②", self.problem)
        self.assertIsNone(grade["correct"])
        self.assertEqual(grade["status"], "ungradable")
        self.assertIsNone(evaluate_answer("최종정답: ② 또는 ③", "②", self.problem)["correct"])
        self.assertIsNone(evaluate_answer("최종정답: 2번 또는 3번", "②", self.problem)["correct"])

    def test_unsupported_answer_remains_ungradable(self):
        self.assertIsNone(evaluate_answer("최종정답: 해가 없다.", "$11$")["correct"])
        self.assertIsNone(evaluate_answer("최종정답: $x$", "$11$")["correct"])
        self.assertFalse(evaluate_answer("최종정답: 12", "$11$")["correct"])
        self.assertIsNone(evaluate_answer("최종정답: 1 1", "$11$")["correct"])
        self.assertTrue(evaluate_answer("최종정답: **11**입니다.", "$11$")["correct"])

    def test_untrusted_expression_never_executes(self):
        for expression in ("__import__('os').system('echo unsafe')", "1e99999", "9**999999999", "1/0", "sqrt(-1)"):
            self.assertIsNone(numeric_constant(expression))


if __name__ == "__main__":
    unittest.main()
