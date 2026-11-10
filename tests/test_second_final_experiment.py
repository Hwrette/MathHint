"""2차 전체265 문제 군집화의 좌표 보존·대표 라벨·읽기 전용 검증을 보호한다."""

import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from mathhint_learning.final_experiment_2.cluster_improvement import verify


class SecondFinalVerificationTests(unittest.TestCase):
    def test_saved_report_runs_without_tokenizer_or_training_and_preserves_sources(self):
        from mathhint_learning.final_experiment_2.cluster_improvement import prepare, report
        from mathhint_learning.final_experiment_2.cluster_improvement.common import ROOT, OUTPUT
        names = ["00_dataset/summary.json", "00_dataset/restored_tokens.csv",
                 "01_clustering/summary.csv", "01_clustering/seed_summary.csv"]
        original = {name: (OUTPUT / name).read_bytes() for name in names}
        with tempfile.TemporaryDirectory() as temporary, \
             patch.object(prepare, "version", side_effect=AssertionError("읽기에 Kiwi 설치 불필요")), \
             patch("mathhint_learning.TorchKMeans.fit_kmeans", side_effect=AssertionError("학습 금지")) as fit, \
             patch("mathhint_learning.TorchKMeans.fit_spherical_kmeans", side_effect=AssertionError("학습 금지")) as sphere:
            data = prepare.load_dataset(ROOT, OUTPUT)
            root = Path(temporary)
            output = root / "results/final_experiment_2/cluster_improvement"
            for name in names:
                target = output / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(original[name])
            old = Path("results/final_experiment/01_clustering/full_dataset_265/summary.csv")
            (root / old).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / old, root / old)
            (root / "results/README.md").write_text("# 기존 결과 안내\n", encoding="utf-8")
            result = report.run(root, output, data)
            self.assertEqual(result["comparison_rows"], 8)
            self.assertFalse(result["training_performed"])
            self.assertEqual(result["api_calls"], 0)
            self.assertIn("시드", (output / "final_report.md").read_text())
            self.assertIn("Macro-F1", (output / "README.md").read_text())
            self.assertEqual({name: (OUTPUT / name).read_bytes() for name in names}, original)
            fit.assert_not_called()
            sphere.assert_not_called()

    def test_cancelled_actions_are_rejected_before_loading_any_dataset(self):
        from mathhint_learning.final_experiment_2.cluster_improvement.__main__ import run
        with tempfile.TemporaryDirectory() as temporary, \
             patch("mathhint_learning.final_experiment_2.cluster_improvement.prepare.load_dataset") as load:
            for action in ("train", "regression", "solution_bow", "holdout", "gemini"):
                with self.subTest(action=action), self.assertRaisesRegex(ValueError, "지원 명령"):
                    run(action, root=Path(temporary))
            load.assert_not_called()

    def test_filtering_keeps_token_and_row_identity_even_with_duplicate_user_choices(self):
        raw = np.array([[4, 1, 3], [0, 2, 5]])
        vocabulary = ["latex:2", r"latex:\sin", "kiwi:연속"]
        choices = ["latex:2", "latex:2"]
        original_choices = list(choices)
        self.assertEqual(verify.validate_projection(raw, raw[:, [1, 2]], vocabulary,
                         vocabulary[1:], choices, [1, 2]), [1, 2])
        self.assertEqual(choices, original_choices)
        np.testing.assert_array_equal(raw, [[4, 1, 3], [0, 2, 5]])

    def test_same_dimension_wrong_vocabulary_order_or_wrong_rows_are_rejected(self):
        raw = np.array([[4, 1, 3], [0, 2, 5]])
        vocabulary = ["latex:2", r"latex:\sin", "kiwi:연속"]
        cases = [(raw[:, [2, 1]], [vocabulary[2], vocabulary[1]], [2, 1]),
                 (raw[::-1, 1:], vocabulary[1:], [1, 2]),
                 (raw[:, [0, 1]], vocabulary[:2], [0, 1])]
        for filtered, words, indices in cases:
            with self.subTest(indices=indices), self.assertRaises(ValueError):
                verify.validate_projection(raw, filtered, vocabulary, words, ["latex:2"], indices)

    def test_majority_collisions_are_summed_and_both_axes_have_identical_order(self):
        assignments = [7, 7, 3, 3, 9]
        labels = ["A", "A", "A", "B", "B"]
        majority = verify.majority_mapping(assignments, labels)
        self.assertEqual(majority, {7: "A", 3: "A", 9: "B"})
        predicted = [majority[cluster] for cluster in assignments]
        matrix = verify.expected_confusion(labels, predicted, ["A", "B"])
        np.testing.assert_array_equal(matrix, [[3, 0], [1, 1]])
        self.assertEqual(matrix.sum(), 5)
        self.assertEqual(matrix.trace() / matrix.sum(), .8)
        with self.assertRaises(ValueError):
            verify.expected_confusion(labels, predicted, ["B", "B"])

    def test_hierarchical_labels_use_curriculum_and_keep_upper_paths(self):
        first = {"subject": "삼각함수", "curriculum": "수학Ⅰ", "unit": "가", "subunit": "동명", "type": "유형"}
        second = dict(first, unit="나")
        self.assertEqual(verify.label_path(first, "curriculum"), "수학Ⅰ")
        self.assertNotEqual(verify.label_path(first, "type"), verify.label_path(second, "type"))

    def test_verification_does_not_rewrite_audits_or_train_models(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "results/final_experiment_2/cluster_improvement"
            output.mkdir(parents=True)
            (output / "config.json").write_text(json.dumps({"dataset_id": "fake",
                                                         "protected_files_sha256": {}}))
            (output / "validation.json").write_text('{"historical": true}\n')
            before = {path.name: path.read_bytes() for path in output.iterdir()}
            with patch.object(verify, "_check_dataset", return_value={}), \
                 patch.object(verify, "_check_clustering", return_value={}), \
                 patch.object(verify, "_check_images", return_value={}), \
                 patch("mathhint_learning.TorchKMeans.fit_kmeans", side_effect=AssertionError("학습 금지")) as fit, \
                 patch("mathhint_learning.TorchKMeans.fit_spherical_kmeans", side_effect=AssertionError("학습 금지")) as sphere:
                result = verify.run(root, output, {"dataset_id": "fake"}, save=False)
            self.assertTrue(result["complete"])
            self.assertEqual({path.name: path.read_bytes() for path in output.iterdir()}, before)
            self.assertFalse(fit.called)
            self.assertFalse(sphere.called)

    def test_relative_links_ignore_examples_and_detect_missing_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            (output / "README.md").write_text('[검증](validation.json) · [누락](absent.csv)\n\n```text\n[예제](not-a-real-file)\n```\n')
            count, broken = verify.scan_links(output)
            self.assertEqual(count, 2)
            self.assertEqual(broken, [{"source": "README.md", "target": "absent.csv"}])


if __name__ == "__main__":
    unittest.main()
