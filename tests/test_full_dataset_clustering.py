"""전체 데이터 탐색의 입력 결합·비지도 선택·완료 결과 재사용을 작은 자료로 검사한다."""

import contextlib
import importlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

try:
    import torch
except ModuleNotFoundError:
    torch = None

if torch is not None:
    full = importlib.import_module("mathhint_learning.full_dataset_265.run")
    from test_fixed_training import write_fixture


@unittest.skipIf(torch is None, "Requires optional torch dependency")
class FullDatasetClusteringTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        write_fixture(self.root)
        metadata_path = self.root / "data/processed/metadata.json"
        metadata = json.loads(metadata_path.read_text())
        for index, record in enumerate(metadata["records"]):
            record.update(curriculum="A" if index < 2 else "B", unit="U", subunit="S", type=record["id"])
            path = self.root / "data/processed/problems" / f"{record['id']}.txt"
            path.parent.mkdir(exist_ok=True)
            path.write_text("검사용 문제 " + record["id"])
        metadata_path.write_text(json.dumps(metadata))
        self.output = self.root / "results/exploration"

    def run_toy(self, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()), patch("mathhint_learning.full_dataset_265.reporting.report_results"):
            return full.run(self.root, self.output, seeds=[42], expected_count=3, expected_dimensions=1,
                            make_figures=False, **kwargs)

    def test_all_original_ids_are_fitted_once_and_cache_never_trains_again(self):
        result = self.run_toy()
        self.assertEqual(len(result["experiments"]), 8)
        config = json.loads((self.output / "config.json").read_text())
        self.assertEqual(config["full_ids"], ["a", "b", "c"])
        self.assertEqual(config["original_splits"], {"train": ["a", "b"], "test": ["c"]})
        for report in result["experiments"]:
            self.assertEqual([row["id"] for row in report["documents"]], ["a", "b", "c"])
            self.assertEqual([row["original_split"] for row in report["documents"]], ["train", "train", "test"])
            self.assertEqual(report["metrics"]["n"], 3)
            self.assertNotIn("test_accuracy", report["metrics"])
        with patch.object(full, "fit_kmeans", side_effect=AssertionError("cache must not fit")), \
             patch.object(full, "fit_spherical_kmeans", side_effect=AssertionError("cache must not fit")):
            cached = self.run_toy()
        self.assertEqual(cached, result)
        saved = self.output / "experiments/type_euclidean/members.csv"
        saved.write_text(saved.read_text() + "tampered")
        with self.assertRaisesRegex(ValueError, "무결성"):
            self.run_toy()

    def test_labels_do_not_change_numeric_features_and_reordered_rows_are_rejected(self):
        first = full.dataset(self.root, expected_count=3, expected_dimensions=1)
        path = self.root / "data/processed/metadata.json"
        metadata = json.loads(path.read_text())
        for record in metadata["records"]:
            record["type"] = "RENAMED_" + record["type"]
        path.write_text(json.dumps(metadata))
        second = full.dataset(self.root, expected_count=3, expected_dimensions=1)
        self.assertTrue(torch.equal(first["matrix"], second["matrix"]))
        self.assertEqual(first["full_ids"], second["full_ids"])
        path = self.root / "data/vectors/problems/train_vectors.json"
        value = json.loads(path.read_text()); value["documents"].reverse(); path.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, "ID order"):
            full.dataset(self.root, expected_count=3, expected_dimensions=1)

    def test_restart_selection_uses_objective_even_when_label_agreement_is_worse(self):
        def fake_fit(matrix, k, max_iter, tolerance, seed):
            # Objective favours one mixed cluster; selecting by label metrics would prefer the other run.
            assignments = torch.tensor([0, 0, 0] if seed == 43 else [0, 0, min(1, k - 1)])
            return {"centers": matrix[:k].clone(), "assignments": assignments,
                    "inertia": 0 if seed == 43 else 10, "cosine_loss": 0 if seed == 43 else 10, "iterations": 1}
        with contextlib.redirect_stdout(io.StringIO()), patch("mathhint_learning.full_dataset_265.reporting.report_results"), \
             patch.object(full, "fit_kmeans", side_effect=fake_fit), patch.object(full, "fit_spherical_kmeans", side_effect=fake_fit):
            result = full.run(self.root, self.output, seeds=[42, 43], expected_count=3,
                              expected_dimensions=1, make_figures=False)
        self.assertTrue(all(report["selected_seed"] == 43 for report in result["experiments"]))
        self.assertTrue(all(report["metrics"]["occupied_clusters"] == 1 for report in result["experiments"]))

    def test_wrong_shape_and_missing_problem_cannot_start_full_fit(self):
        with self.assertRaisesRegex(ValueError, "차원"):
            full.dataset(self.root, expected_count=3, expected_dimensions=346)
        (self.root / "data/processed/problems/c.txt").unlink()
        with self.assertRaisesRegex(FileNotFoundError, "c"):
            full.dataset(self.root, expected_count=3, expected_dimensions=1)


if __name__ == "__main__":
    unittest.main()
