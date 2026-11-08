"""K-means의 군집 평균, 마지막 배정, 빈 군집 처리를 확인한다."""

import unittest

try:
    import torch
except ModuleNotFoundError:
    torch = None

if torch is not None:
    from mathhint_learning.TorchKMeans import assign_clusters, fit_kmeans


@unittest.skipIf(torch is None, "Requires optional torch dependency")
class TorchKMeansTests(unittest.TestCase):
    def test_three_clear_groups_have_expected_centers_and_squared_distances(self):
        X = torch.tensor([[0., 0.], [0., 2.], [10., 10.], [10., 12.], [20., 0.], [22., 0.]])
        result = fit_kmeans(X, n_clusters=3, seed=42)
        centers = result["centers"][result["centers"][:, 0].argsort()]
        torch.testing.assert_close(centers, torch.tensor([[0., 1.], [10., 11.], [21., 0.]]))
        self.assertAlmostEqual(result["inertia"], 6.)
        groups = result["assignments"].tolist()
        self.assertEqual(groups[0], groups[1])
        self.assertEqual(groups[2], groups[3])
        self.assertEqual(groups[4], groups[5])
        self.assertEqual(len(set(groups)), 3)

    def test_assignments_match_final_centers_even_at_iteration_limit(self):
        X = torch.tensor([[0.], [4.], [5.], [6.], [20.], [22.]])
        result = fit_kmeans(X, n_clusters=2, max_iter=1, seed=42)
        distances = ((X[:, None, :] - result["centers"][None, :, :]) ** 2).sum(dim=2)
        nearest = distances.argmin(dim=1)
        self.assertTrue(torch.equal(result["assignments"], nearest))
        self.assertTrue(torch.equal(assign_clusters(X, result["centers"]), nearest))
        self.assertAlmostEqual(result["inertia"], ((X - result["centers"][nearest]) ** 2).sum().item())

    def test_identical_points_form_one_cluster(self):
        X = torch.ones(4, 2)
        result = fit_kmeans(X, n_clusters=1)
        self.assertEqual(result["inertia"], 0)
        self.assertEqual(result["assignments"].tolist(), [0, 0, 0, 0])
        torch.testing.assert_close(result["centers"], torch.ones(1, 2))


if __name__ == "__main__":
    unittest.main()
