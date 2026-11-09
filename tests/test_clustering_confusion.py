"""군집 번호가 아닌 학습 대표 분류로 계산되는지 검사한다."""

import csv
from pathlib import Path
import tempfile
import unittest

import numpy as np

from mathhint_learning.ClusteringConfusion import build_confusion_matrix, _holdout_matrix
from mathhint_learning.ClusterReport import save_final_cluster_readme


class ClusteringConfusionTests(unittest.TestCase):
    def test_axes_use_full_hierarchical_labels_in_same_order_including_unobserved(self):
        labels = ["과목A / 단원 / 같은유형", "과목B / 단원 / 같은유형", "미등장"]
        matrix = build_confusion_matrix([labels[0], labels[1], labels[1]],
                                        [labels[1], labels[1], labels[0]], labels)
        np.testing.assert_array_equal(matrix, [[0, 1, 0], [1, 1, 0], [0, 0, 0]])
        self.assertEqual(int(matrix.sum()), 3)
        self.assertEqual(int(np.trace(matrix)), 1)

    def test_unknown_prediction_cannot_be_silently_dropped(self):
        with self.assertRaisesRegex(ValueError, "없는"):
            build_confusion_matrix(["A"], ["cluster_0"], ["A", "B"])
        with self.assertRaises(ValueError):
            build_confusion_matrix(["A"], [], ["A"])
        with self.assertRaises(ValueError):
            build_confusion_matrix(["A"], ["A"], ["A", "A"])

    def fixture(self, folder):
        fields = ["id", "split", "cluster", "actual_label", "train_majority_label"]
        members = [dict(zip(fields, [f"train_{i}", "train", "0", label, "A"]))
                   for i, label in enumerate(["A", "A", "B"])]
        members += [dict(zip(fields, [f"test_{i}", "test", "0", "B", "A"])) for i in range(80)]
        for name, rows, columns in (("members.csv", members, fields),
                                    ("label_key.csv", [{"label_code": "L01", "actual_label": "A"},
                                                       {"label_code": "L02", "actual_label": "B"}],
                                     ["label_code", "actual_label"])):
            with (folder / name).open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=columns)
                writer.writeheader()
                writer.writerows(rows)
        return members

    def test_test_majority_does_not_change_train_representative_or_false_score(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            members = self.fixture(folder)
            summary = {"n": "80", "train_majority_accuracy": "0"}
            matrix, labels, _ = _holdout_matrix(folder, members, summary)
            self.assertEqual(labels, ["A", "B"])
            np.testing.assert_array_equal(matrix, [[0, 0], [80, 0]])
            with self.assertRaisesRegex(ValueError, "대각선"):
                _holdout_matrix(folder, members, {"n": "80", "train_majority_accuracy": "1"})

    def test_saved_representative_must_match_recomputed_train_only_majority(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            members = self.fixture(folder)
            members[-1]["train_majority_label"] = "B"
            with (folder / "members.csv").open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(members[0]))
                writer.writeheader()
                writer.writerows(members)
            with self.assertRaisesRegex(ValueError, "대표 라벨"):
                _holdout_matrix(folder, members, {"n": "80", "train_majority_accuracy": "0"})

    def test_document_refresh_keeps_saved_confusion_explanation_without_duplication(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            (folder / "figures").mkdir()
            save_final_cluster_readme(folder, "toy", 2)
            self.assertNotIn("혼동행렬", (folder / "README.md").read_text())
            (folder / "figures/confusion_matrix_test.png").write_bytes(b"placeholder")
            section = "\n## 테스트 혼동행렬\n\n[그림](figures/confusion_matrix_test.png)\n\n학습 대표라벨만 사용한 검증된 설명.\n"
            with (folder / "README.md").open("a") as stream:
                stream.write(section)
            for _ in range(2):
                save_final_cluster_readme(folder, "toy", 2)
                text = (folder / "README.md").read_text()
                self.assertTrue(text.endswith(section))
                self.assertEqual(text.count("## 테스트 혼동행렬"), 1)


if __name__ == "__main__":
    unittest.main()
