"""보고서가 통계 범위와 실제 전송 좌표 분모를 섞지 않는지 확인한다."""

import unittest

from mathhint_analysis.token_analysis.reporting import _mixture, _stat_tables, _token


class TokenReportingTests(unittest.TestCase):
    def test_key_table_uses_training_variance_with_training_eta(self):
        problem = [{"token": "latex:x", "index": "0", "variance": "999", "train_variance": "2",
                    "meaning": "변수"}]
        variance = [{"level": level, "token": "latex:x", "eta_squared": ".25"}
                    for level in ("curriculum", "unit", "subunit", "type")]
        table = "\n".join(_stat_tables(problem, variance))
        self.assertIn("학습185 전체 분산", table)
        self.assertIn("2.0000", table)
        self.assertNotIn("999", table)
        self.assertEqual(table.count("0.2500"), 4)

    def test_category_mixture_counts_actual_coordinates_without_frequency_weights(self):
        composition = [{"condition": c, "category": cat, "coordinate_count": n, "total_coordinates": 10}
                       for c in ("B", "C") for cat, n in (("괄호·수식 구조 기호", 3),
                       ("LaTeX 숫자", 2), ("LaTeX 수학 명령어", 1), ("풀이 방법 자연어", 0),
                       ("분류 불확실·검토 필요", 4))]
        result = _mixture(composition)
        for condition in ("B", "C"):
            self.assertEqual(result[condition]["total"], 10)
            self.assertEqual(sum(result[condition]["groups"].values()), 10)
            self.assertEqual(result[condition]["groups"]["서식·구조·고정 양식"], 3)
            self.assertEqual(result[condition]["groups"]["풀이 방법 자연어"], 0)

    def test_token_label_preserves_backslashes_and_table_boundary(self):
        self.assertEqual(_token(r"latex:\lim"), r"`latex:\lim`")
        self.assertEqual(_token("latex:|"), r"`latex:\|`")
