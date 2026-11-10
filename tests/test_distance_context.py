"""문항 쌍의 분모·희소 집단·단위와 기존 배정 읽기 경계를 검증한다."""

import unittest
from pathlib import Path
import tempfile

import numpy as np

from mathhint_analysis.token_analysis.distance_comparison.context import (
    pair_distance_summary, norm_distance_diagnostics, read_cluster_context,
)
from mathhint_analysis.token_analysis.common import dump_csv, read_csv, sha256


class DistanceContextTests(unittest.TestCase):
    def test_existing_metrics_are_read_exactly_and_saved_label_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "results/final_experiment/01_clustering"
            output = root / "new_analysis"
            ids, labels = ["a", "b", "c", "d"], ["A", "A", "B", "B"]
            summaries, members = [], []
            for level in ("curriculum", "unit", "subunit", "type"):
                for method in ("euclidean", "spherical"):
                    experiment = level + "_" + method
                    summaries.append({"experiment": experiment, "level": level, "level_name": level,
                        "method": method, "method_name": method, "split": "test", "k": 2, "n": 2,
                        "ari": "0.123456789", "nmi": "0.234567891", "train_majority_accuracy": "0.5", "selected_seed": 42})
                    members.extend({"experiment": experiment, "level": level, "method": method,
                        "id": identifier, "split": "train", "cluster": i // 2, "actual_label": labels[i]}
                        for i, identifier in enumerate(ids))
            dump_csv(source / "summary.csv", summaries)
            dump_csv(source / "cluster_members.csv", members)
            before = sha256(source / "summary.csv")
            geometry = {"ids": ids, "labels_by_level": {level: labels for level in ("curriculum", "unit", "subunit", "type")},
                        "l1": np.array([2., 3., 7., 9.]), "l2": np.array([1., 2., 4., 5.]), "token_count": np.array([2., 3., 7., 9.])}
            metrics, association = read_cluster_context(root, output, geometry)
            self.assertEqual([row["ari"] for row in metrics], ["0.123456789"] * 8)
            self.assertEqual([row["nmi"] for row in read_csv(output / "old_clustering_metrics.csv")], ["0.234567891"] * 8)
            self.assertEqual(len(association), 8)
            self.assertEqual(sha256(source / "summary.csv"), before)
            members[0]["actual_label"] = "wrong path"
            dump_csv(source / "cluster_members.csv", members)
            with self.assertRaisesRegex(ValueError, "계층 라벨"):
                read_cluster_context(root, output, geometry)

    def test_pooled_means_medians_counts_and_macro_same_subset(self):
        # A의 두 문항 거리2, B의 한 문항까지 거리10과8이다.
        i, j = np.triu_indices(3, 1)
        total, classes = pair_distance_summary(["A", "A", "B"], i, j, [2, 10, 8],
                                              level="unit", metric="euclidean")
        self.assertEqual((total["within_pairs"], total["between_pairs"]), (1, 2))
        self.assertEqual((total["within_mean"], total["between_mean"]), (2, 9))
        self.assertEqual((total["within_median"], total["between_median"]), (2, 9))
        self.assertEqual(total["between_minus_within"], 7)
        self.assertEqual(total["between_div_within"], 4.5)
        self.assertEqual(total["macro_comparable_classes"], 1)
        self.assertEqual(total["macro_excluded_classes"], 1)
        self.assertEqual(total["macro_within_mean"], 2)
        self.assertEqual(total["macro_between_mean"], 9)
        singleton = next(row for row in classes if row["label"] == "B")
        self.assertEqual(singleton["between_pairs"], 2)
        self.assertIsNone(singleton["within_mean"])
        self.assertIsNone(singleton["between_div_within"])

    def test_no_within_pairs_and_zero_denominator_are_undefined(self):
        i, j = np.triu_indices(3, 1)
        rows, _ = pair_distance_summary(["A", "B", "C"], i, j, [1, 2, 3], level="type", metric="cosine")
        self.assertEqual(rows["within_pairs"], 0)
        self.assertIsNone(rows["within_mean"])
        self.assertIsNone(rows["between_div_within"])
        rows, _ = pair_distance_summary(["A", "A", "B"], i, j, [0, 1, 1], level="type", metric="cosine")
        self.assertEqual(rows["within_mean"], 0)
        self.assertIsNone(rows["between_div_within"])

    def test_incomplete_or_ordered_double_counted_pairs_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "i<j"):
            pair_distance_summary(["A", "A", "B"], [0, 1], [1, 2], [1, 2], level="type", metric="euclidean")
        with self.assertRaisesRegex(ValueError, "i<j"):
            pair_distance_summary(["A", "B"], [0, 1], [1, 0], [1, 1], level="type", metric="euclidean")

    def test_euclidean_norm_direction_identity_is_checked_without_model(self):
        x = np.array([[3., 0.], [0., 4.], [6., 0.]])
        i, j = np.triu_indices(3, 1)
        norms = np.linalg.norm(x, axis=1)
        z = x / norms[:, None]
        squared = ((x[i] - x[j]) ** 2).sum(axis=1)
        cosine = .5 * ((z[i] - z[j]) ** 2).sum(axis=1)
        result = norm_distance_diagnostics({"pair_i": i, "pair_j": j, "l2": norms,
            "l1": x.sum(axis=1), "euclidean_squared": squared, "euclidean": np.sqrt(squared), "cosine": cosine})
        self.assertTrue(result["radial_identity_verified"])
        self.assertAlmostEqual(result["norm_difference_squared_share_pct"] + result["norm_scaled_direction_share_pct"], 100)
        self.assertTrue(all(row["independent_sample_size_claim"] is False for row in result["correlations"]))


if __name__ == "__main__":
    unittest.main()
