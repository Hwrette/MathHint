"""거리 보고서의 단위·정의되지 않는 값·원래 지표 표시를 확인한다."""

import unittest

from mathhint_analysis.token_analysis.distance_comparison.reporting import (
    LEVELS, _contribution_table, _distance_table, _old_table,
)


class DistanceReportingTests(unittest.TestCase):
    def test_percent_contribution_and_percentage_point_difference_are_distinct(self):
        rows = [{"token": r"latex:\sin", "euclidean_contribution": "1.5", "cosine_contribution": "3.0",
                 "contribution_difference": "1.5", "euclidean_rank": "8", "cosine_rank": "4", "meaning": "사인"}]
        text = "\n".join(_contribution_table(rows))
        self.assertIn(r"`latex:\sin`", text)
        self.assertIn("1.50%|3.00%|+1.50|8→4", text)
        self.assertIn("C−E (%p)", text)

    def test_undefined_within_distances_are_not_rendered_as_zero(self):
        rows = [{"level": level, "metric": metric, "within_pairs": "0", "between_pairs": "10",
                 "within_mean": "", "between_mean": ".4", "between_minus_within": "", "between_div_within": ""}
                for level, _ in LEVELS for metric in ("euclidean", "cosine")]
        text = "\n".join(_distance_table(rows))
        self.assertEqual(text.count("정의되지 않음"), 24)
        self.assertNotIn("|0.0000|", text)
        self.assertTrue(all(len(line.split("|")) == 9 for line in text.splitlines()))

    def test_saved_ari_values_are_used_without_an_assumed_cosine_win(self):
        rows = [{"level": level, "method": method, "ari": ".2" if method == "euclidean" else ".1", "nmi": ".3"}
                for level, _ in LEVELS for method in ("euclidean", "spherical")]
        text = "\n".join(_old_table(rows))
        self.assertEqual(text.count("-0.100000"), 4)
        self.assertNotIn("0.2404", text)
