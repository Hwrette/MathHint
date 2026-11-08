"""최종 군집화의 구면 계산과 학습 전용 대표 라벨을 검증한다."""

import unittest

import torch

from mathhint_learning.FinalClustering import hierarchy_label, majority_labels, evaluate_assignments
from mathhint_learning.TorchKMeans import (assign_spherical, fit_spherical_kmeans,
                                          l2_normalize)


class SphericalKMeansTests(unittest.TestCase):
    def test_centers_are_normalized_sums_and_objective_matches_final_assignments(self):
        matrix = torch.tensor([[10., 0.], [2., 1.], [0., 12.], [1., 3.]])
        result = fit_spherical_kmeans(matrix, n_clusters=2, seed=42)
        assignments, centers = result["assignments"], result["centers"]
        self.assertEqual(assignments[0].item(), assignments[1].item())
        self.assertEqual(assignments[2].item(), assignments[3].item())
        self.assertNotEqual(assignments[0].item(), assignments[2].item())
        torch.testing.assert_close(torch.linalg.vector_norm(centers, dim=1), torch.ones(2))
        normalized = l2_normalize(matrix)
        for cluster in range(2):
            expected = l2_normalize(normalized[assignments == cluster].sum(dim=0, keepdim=True))[0]
            torch.testing.assert_close(centers[cluster], expected)
        self.assertTrue(torch.equal(assignments, assign_spherical(matrix, centers)))
        expected_loss = (1 - (normalized * centers[assignments]).sum(dim=1)).sum().item()
        self.assertAlmostEqual(result["cosine_loss"], expected_loss)

    def test_assignment_ignores_positive_row_lengths(self):
        centers = torch.tensor([[1., 0.], [0., 1.]])
        matrix = torch.tensor([[3., 1.], [1., 7.], [0., 0.]])
        scaled = matrix * torch.tensor([[.02], [100.], [1.]])
        self.assertEqual(assign_spherical(matrix, centers).tolist(), [0, 1, 0])
        self.assertTrue(torch.equal(assign_spherical(matrix, centers), assign_spherical(scaled, centers * 3)))

    def test_zero_and_duplicate_directions_with_empty_clusters_are_finite(self):
        matrix = torch.tensor([[0., 0.], [1., 0.], [2., 0.], [0., 1.], [0., 2.]])
        result = fit_spherical_kmeans(matrix, n_clusters=4, max_iter=10, seed=2)
        self.assertEqual(list(result["centers"].shape), [4, 2])
        self.assertTrue(torch.isfinite(result["centers"]).all())
        self.assertTrue(torch.isfinite(torch.tensor(result["cosine_loss"])))
        self.assertEqual(result["assignments"][0].item(), 0)
        zeros = fit_spherical_kmeans(torch.zeros(4, 2), n_clusters=1)
        torch.testing.assert_close(zeros["centers"], torch.zeros(1, 2))
        self.assertEqual(zeros["cosine_loss"], 4.)

    def test_invalid_cluster_count_does_not_silently_reduce_k(self):
        with self.assertRaises(ValueError):
            fit_spherical_kmeans(torch.ones(3, 2), n_clusters=2)


class ClusteringLabelsTests(unittest.TestCase):
    def test_hierarchy_uses_course_and_disambiguates_same_names(self):
        record = {"id": "a", "subject": "삼각함수", "curriculum": "대수", "unit": "단원 A", "subunit": "같은 이름", "type": "유형"}
        self.assertEqual(hierarchy_label(record, "curriculum"), "대수")
        second = dict(record, unit="단원 B")
        self.assertNotEqual(hierarchy_label(record, "type"), hierarchy_label(second, "type"))

    def test_training_majority_is_fixed_even_if_test_majority_differs(self):
        mapping = majority_labels([0, 0, 1, 1], ["A", "A", "B", "C"])
        self.assertEqual(mapping, {0: "A", 1: "B"})
        metrics = evaluate_assignments([0, 0, 0, 1], ["B", "B", "A", "C"], mapping, 2)
        self.assertEqual(metrics["train_majority_accuracy"], .25)
        self.assertEqual(metrics["cluster_sizes"], {"0": 3, "1": 1})


if __name__ == "__main__":
    unittest.main()
