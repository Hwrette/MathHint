"""한국어와 수식이 섞인 문제에서 토큰이 빠지거나 잘못 합쳐지지 않는지 검사합니다."""

from collections import Counter
from pathlib import Path
import tempfile
import unittest

# 문서 전처리만 사용하는 사람은 Kiwi를 설치하지 않아도 기존 검사를 실행할 수 있습니다.
try:
    from mathhint_analysis import BagOfWord as bow
except ModuleNotFoundError as error:
    if error.name != "kiwipiepy":
        raise
    bow = None


@unittest.skipIf(bow is None, "토큰 분석 검사는 python -m pip install kiwipiepy 후 실행하세요.")
class BowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 실제 Kiwi를 사용하되, 검사 동안 한 객체를 공유합니다.
        cls.kiwi = bow.Kiwi(num_workers=1)

    def test_user_log_problem_counts_math_and_korean_together(self):
        problem = (
            r"$\log_{3} 25 \times \left( \log_{5} 9 + \log_{25} 3 \right)$"
            "의 값을 구하시오."
        )
        counts = bow.count_tokens(problem, self.kiwi)
        math_counts = {key: value for key, value in counts.items() if key.startswith("latex:")}
        self.assertEqual(math_counts, {
            "latex:\\log": 3, "latex:_": 3, "latex:{": 3, "latex:}": 3,
            "latex:3": 2, "latex:25": 2, "latex:5": 1, "latex:9": 1,
            "latex:\\times": 1, "latex:\\left": 1, "latex:(": 1,
            "latex:+": 1, "latex:\\right": 1, "latex:)": 1,
        })
        self.assertEqual(counts["kiwi:값"], 1)
        self.assertEqual(counts["kiwi:을"], 1)  # 조사도 남아 있어야 합니다.
        self.assertEqual(counts["kiwi:."], 1)  # 문장부호도 남아 있어야 합니다.

    def test_kiwi_keeps_particles_and_endings(self):
        counts = bow.count_tokens("사과를 먹었다.", self.kiwi)
        for form in ("사과", "를", "먹", "었", "다", "."):
            self.assertEqual(counts[f"kiwi:{form}"], 1)

    def test_same_spelling_keeps_korean_and_math_sources_separate(self):
        counts = bow.count_tokens("3 $3+3$", self.kiwi)
        self.assertEqual(counts, Counter({"kiwi:3": 1, "latex:3": 2, "latex:+": 1}))

    def test_nested_braces_and_unknown_commands_are_preserved(self):
        self.assertEqual(
            bow.tokenize_latex(r"\frac{1}{\sqrt{x^{2}}}+\foobar"),
            [r"\frac", "{", "1", "}", "{", r"\sqrt", "{", "x", "^",
             "{", "2", "}", "}", "}", "+", r"\foobar"],
        )

    def test_numbers_variables_and_escaped_symbols(self):
        self.assertEqual(
            bow.tokenize_latex(r"-25+3.14xy\{\}\,\%"),
            ["-", "25", "+", "3.14", "x", "y", r"\{", r"\}", r"\,", r"\%"],
        )

    def test_all_supported_delimiters_and_multiline_math(self):
        text = "$x$ $$y\n+1$$ " + r"\(z\) \[w\]"
        parts = bow.split_math(text)
        self.assertEqual([content for source, content in parts if source == "latex"],
                         ["x", "y\n+1", "z", "w"])
        self.assertEqual(bow.count_tokens(text, self.kiwi), Counter({
            "latex:x": 1, "latex:y": 1, "latex:+": 1,
            "latex:1": 1, "latex:z": 1, "latex:w": 1,
        }))

    def test_escaped_dollar_is_not_a_math_boundary(self):
        self.assertEqual(bow.split_math(r"가격 \$3"), [("kiwi", r"가격 \$3")])
        self.assertEqual(bow.split_math(r"$x+\$3$"),
                         [("kiwi", ""), ("latex", r"x+\$3"), ("kiwi", "")])
        # 백슬래시 두 개는 서로 한 쌍이므로, 그다음 달러는 수식 경계입니다.
        self.assertEqual(bow.split_math(r"\\$x$"),
                         [("kiwi", r"\\"), ("latex", "x"), ("kiwi", "")])

    def test_adjacent_math_spans_do_not_create_dollar_tokens(self):
        # 문서 전처리 결과에는 수식 두 개가 공백 없이 붙어 있을 수 있습니다.
        for text in ("$x$$y$", "$x$$$y$$", "$$x$$$y$", "$$x$$$$y$$"):
            with self.subTest(text=text):
                parts = bow.split_math(text)
                self.assertEqual(
                    [content for source, content in parts if source == "latex"], ["x", "y"]
                )
                self.assertEqual(bow.count_tokens(text, self.kiwi),
                                 Counter({"latex:x": 1, "latex:y": 1}))

    def test_math_boundaries_do_not_join_unrelated_korean_fragments(self):
        self.assertEqual(bow.split_math("앞$x$뒤$y$끝"), [
            ("kiwi", "앞"), ("latex", "x"), ("kiwi", "뒤"),
            ("latex", "y"), ("kiwi", "끝"),
        ])

    def test_unclosed_math_raises_instead_of_counting_as_korean(self):
        for text in ("값 $x", "값 $$x$", r"값 \(x", r"값 \[x"):
            with self.subTest(text=text):
                with self.assertRaisesRegex(ValueError, "수식이 닫히지 않았습니다"):
                    bow.count_tokens(text, self.kiwi)

    def test_empty_input_has_no_counts(self):
        self.assertEqual(bow.count_tokens(" \n\t", self.kiwi), Counter())

    def test_file_reading_and_encoding(self):
        # 실제 파일을 읽는 경로와 CP949 옵션도 확인합니다.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "문제.txt"
            path.write_text("$25+25$", encoding="utf-8")
            self.assertEqual(bow.make_bow(str(path)),
                             Counter({"latex:25": 2, "latex:+": 1}))
            path.write_text("값 $3$", encoding="cp949")
            counts = bow.make_bow(str(path), encoding="cp949")
            self.assertEqual(counts["kiwi:값"], 1)
            self.assertEqual(counts["latex:3"], 1)


if __name__ == "__main__":
    unittest.main()
