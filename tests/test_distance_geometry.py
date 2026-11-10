"""문항쌍 거리 항등식·분산 기여율·정규화 효과를 작은 수학 예제로 검증한다."""

import unittest

import numpy as np

from mathhint_analysis.token_analysis.distance_comparison.geometry import (
    contribution_ranks, contribution_statistics, pair_geometry,
)
from mathhint_analysis.token_analysis.statistics import variance_decomposition


class DistanceGeometryTests(unittest.TestCase):
    def test_all_unordered_pairs_and_known_distances(self):
        matrix = np.array([[1., 0.], [0., 1.], [1., 1.]])
        actual = pair_geometry(matrix)
        np.testing.assert_array_equal(actual["pair_i"], [0, 0, 1])
        np.testing.assert_array_equal(actual["pair_j"], [1, 2, 2])
        np.testing.assert_allclose(actual["euclidean_squared"], [2., 1., 1.])
        np.testing.assert_allclose(actual["euclidean"], [np.sqrt(2), 1., 1.])
        np.testing.assert_allclose(actual["cosine"], [1., 1 - 1 / np.sqrt(2), 1 - 1 / np.sqrt(2)])
        result = contribution_statistics(actual)
        np.testing.assert_allclose(result["euclidean_contribution"], [50., 50.])
        np.testing.assert_allclose(result["cosine_contribution"], [50., 50.])

    def test_pair_coordinate_means_equal_population_variance_formulas(self):
        matrix = np.array([[1., 2., 3.], [4., 1., 1.], [2., 3., 4.], [8., 1., 2.]])
        geometry = pair_geometry(matrix)
        result = contribution_statistics(geometry)
        n = len(matrix)
        np.testing.assert_allclose(result["pair_mean_euclidean_squared_coordinate"], 2 * n / (n - 1) * matrix.var(axis=0))
        np.testing.assert_allclose(result["pair_mean_cosine_coordinate"], n / (n - 1) * geometry["Z"].var(axis=0))
        self.assertAlmostEqual(result["euclidean_contribution"].sum(), 100)
        self.assertAlmostEqual(result["cosine_contribution"].sum(), 100)

    def test_each_document_rescaling_changes_raw_distances_but_not_cosine(self):
        matrix = np.array([[1., 1.], [2., 0.], [0., 2.]])
        first = pair_geometry(matrix)
        second = pair_geometry(matrix * np.array([1., 3., 2.])[:, None])
        np.testing.assert_allclose(first["cosine"], second["cosine"], atol=1e-14)
        self.assertFalse(np.allclose(first["euclidean_squared"], second["euclidean_squared"]))

    def test_zero_vector_is_not_deleted_or_given_an_arbitrary_cosine(self):
        with self.assertRaisesRegex(ValueError, "영벡터.*zero_id"):
            pair_geometry([[1., 2.], [0., 0.]], ids=["valid", "zero_id"])

    def test_identical_nonzero_rows_have_undefined_contribution_rates(self):
        result = contribution_statistics(pair_geometry([[1., 2.], [1., 2.], [1., 2.]]))
        self.assertTrue(np.isnan(result["euclidean_contribution"]).all())
        self.assertTrue(np.isnan(result["cosine_contribution"]).all())
        self.assertEqual(contribution_ranks(result["cosine_contribution"]), [None, None])

    def test_rank_ties_use_original_coordinate_order(self):
        self.assertEqual(contribution_ranks(np.array([40., 40., 20., np.nan])), [1, 2, 3, None])

    def test_185_documents_yield_17020_unique_unordered_pairs(self):
        matrix = np.column_stack((np.arange(185) + 1., np.ones(185)))
        result = pair_geometry(matrix)
        self.assertEqual(len(result["pair_i"]), 17020)
        self.assertTrue(np.all(result["pair_i"] < result["pair_j"]))
        self.assertEqual(len(set(zip(result["pair_i"], result["pair_j"]))), 17020)

    def test_normalization_eta_has_its_own_variance_space(self):
        matrix = np.array([[1., 0., 0.], [2., 0., 0.], [0., 1., 0.], [0., 2., 0.]])
        geometry = pair_geometry(matrix)
        labels = ["A", "A", "B", "B"]
        raw, normalized = [variance_decomposition(m, labels) for m in (matrix, geometry["Z"])]
        self.assertLess(raw["eta_squared"][0], normalized["eta_squared"][0])
        np.testing.assert_allclose(normalized["eta_squared"][:2], 1)
        self.assertTrue(np.isnan(normalized["eta_squared"][2]))
        np.testing.assert_allclose(normalized["total_variance"], normalized["between_variance"] + normalized["within_variance"])

    def test_inputs_are_not_mutated_and_nonfinite_values_are_rejected(self):
        matrix = np.array([[1., 2.], [3., 4.]])
        original = matrix.copy()
        contribution_statistics(pair_geometry(matrix))
        np.testing.assert_array_equal(matrix, original)
        with self.assertRaisesRegex(ValueError, "유한"):
            pair_geometry([[1., np.nan], [2., 3.]])
