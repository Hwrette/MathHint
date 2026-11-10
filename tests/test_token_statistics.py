"""모델 실행 없이 토큰 통계의 분모·분산 분해·중복 좌표를 검증한다."""

import unittest

import numpy as np

from mathhint_analysis.token_analysis.statistics import (
    token_moments, variance_decomposition, redundancy_pairs, bounded_eta,
)


class TokenStatisticsTests(unittest.TestCase):
    def test_tf_df_population_variance_and_test_statistics_are_separate(self):
        train = np.array([[0, 1], [2, 1], [4, 0]])
        test = np.array([[6, 2]])
        result = token_moments(train, test)
        np.testing.assert_array_equal(result["train_tf"], [6, 2])
        np.testing.assert_array_equal(result["train_df"], [2, 2])
        np.testing.assert_array_equal(result["test_tf"], [6, 2])
        np.testing.assert_array_equal(result["test_df"], [1, 1])
        np.testing.assert_array_equal(result["total_tf"], [12, 4])
        np.testing.assert_array_equal(result["total_df"], [3, 3])
        np.testing.assert_allclose(result["mean"], [3, 1])
        np.testing.assert_allclose(result["variance"], [5, .5])
        np.testing.assert_allclose(result["train_variance"], [8 / 3, 2 / 9])
        # Changing test counts cannot change train-only moments or distance contributions.
        changed = token_moments(train, np.array([[600, 200]]))
        for field in ("train_tf", "train_df", "train_mean", "train_variance", "train_distance_contribution_ratio"):
            np.testing.assert_array_equal(result[field], changed[field])

    def test_mean_pairwise_squared_distance_has_the_finite_sample_factor(self):
        train = np.array([[0, 1], [2, 1], [5, 4], [9, 0]], dtype=float)
        result = token_moments(train, np.array([[0, 0]]))
        actual_pairs = np.array([np.square(train[a] - train[b])
                                 for a in range(len(train)) for b in range(a + 1, len(train))])
        np.testing.assert_allclose(result["mean_pair_squared_distance_train"], actual_pairs.mean(axis=0))
        np.testing.assert_allclose(result["train_distance_contribution_ratio"],
                                   actual_pairs.sum(axis=0) / actual_pairs.sum())

    def test_weighted_variance_decomposition_and_undefined_eta(self):
        matrix = np.array([[0, 5], [2, 5], [4, 5], [6, 5]])
        result = variance_decomposition(matrix, ["A", "A", "B", "B"])
        np.testing.assert_allclose(result["total_variance"], [5, 0])
        np.testing.assert_allclose(result["between_variance"], [4, 0])
        np.testing.assert_allclose(result["within_variance"], [1, 0])
        self.assertAlmostEqual(result["eta_squared"][0], .8)
        self.assertAlmostEqual(result["adjusted_eta_squared"][0], .7)
        self.assertTrue(np.isnan(result["eta_squared"][1]))
        self.assertTrue(np.isnan(result["adjusted_eta_squared"][1]))
        self.assertEqual([group["n"] for group in result["groups"]], [2, 2])

    def test_unequal_groups_use_document_weights_not_equal_group_weights(self):
        matrix = np.array([[0], [0], [0], [4]], dtype=float)
        result = variance_decomposition(matrix, ["A", "A", "A", "B"])
        np.testing.assert_allclose(result["total_variance"], [3])
        np.testing.assert_allclose(result["between_variance"], [3])
        np.testing.assert_allclose(result["within_variance"], [0])
        np.testing.assert_allclose(result["eta_squared"], [1])

    def test_adjusted_eta_can_be_negative_and_is_undefined_for_all_singletons(self):
        matrix = np.array([[0], [2], [4], [6]])
        mixed = variance_decomposition(matrix, ["A", "B", "A", "B"])
        self.assertAlmostEqual(mixed["eta_squared"][0], .2)
        self.assertAlmostEqual(mixed["adjusted_eta_squared"][0], -.2)
        singletons = variance_decomposition(matrix, ["A", "B", "C", "D"])
        self.assertAlmostEqual(singletons["eta_squared"][0], 1)
        self.assertTrue(np.isnan(singletons["adjusted_eta_squared"][0]))

    def test_exact_equality_differs_from_perfect_correlation_and_constant_pairs(self):
        x = np.arange(6, dtype=float)
        matrix = np.stack((x, x, 2 * x + 1, np.ones(6) * 3, np.ones(6) * 4), axis=1)
        vocab = ["latex:{", "latex:}", "latex:x", r"latex:\left", r"latex:\right"]
        rows = redundancy_pairs(matrix, vocab)
        pair = next(row for row in rows if row["index_a"] == 0 and row["index_b"] == 1)
        self.assertTrue(pair["exact_equal"])
        self.assertEqual(pair["counts_equal_documents"], 6)
        correlated = next(row for row in rows if row["index_a"] == 0 and row["index_b"] == 2)
        self.assertFalse(correlated["exact_equal"])
        self.assertAlmostEqual(correlated["pearson_correlation"], 1)
        constant = next(row for row in rows if row["index_a"] == 3 and row["index_b"] == 4)
        self.assertTrue(constant["constant_pattern"])
        self.assertIsNone(constant["pearson_correlation"])
        self.assertIn("requested_pair", constant["selection_reason"])

    def test_zero_total_distance_and_single_document_mean_pair_distance_are_undefined(self):
        result = token_moments([[2, 3]], [[4, 5]])
        self.assertTrue(np.isnan(result["train_distance_contribution_ratio"]).all())
        self.assertTrue(np.isnan(result["mean_pair_squared_distance_train"]).all())

    def test_invalid_row_label_correspondence_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "문항 행"):
            variance_decomposition([[1], [2]], ["A"])
        with self.assertRaisesRegex(ValueError, "어휘"):
            redundancy_pairs([[1], [2]], ["x", "y"])

    def test_eta_boundary_roundoff_only_is_normalized_and_nan_is_preserved(self):
        values = bounded_eta([-5e-14, 5e-14, .3, 1 - 5e-14, 1 + 5e-14, np.nan])
        np.testing.assert_array_equal(values[:5], [0, 0, .3, 1, 1])
        self.assertTrue(np.isnan(values[5]))
        for invalid in (-2e-12, 1 + 2e-12):
            with self.subTest(invalid=invalid), self.assertRaisesRegex(ArithmeticError, "이론"):
                bounded_eta([invalid])


if __name__ == "__main__":
    unittest.main()
