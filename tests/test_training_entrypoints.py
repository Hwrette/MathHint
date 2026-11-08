"""기본 실행이 저장된 학습·테스트 분할을 유지하는지 확인한다."""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

try:
    import torch
except ModuleNotFoundError:
    torch = None

if torch is not None:
    from mathhint_learning import TorchKMeans, TorchRegression
    from mathhint_learning.Experiment import Experiment
    from test_fixed_training import write_fixture


@unittest.skipIf(torch is None, "Requires optional torch dependency")
class TrainingEntrypointTests(unittest.TestCase):
    def test_regression_keeps_supplied_ids_and_never_resplits(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_fixture(root)
            experiment = Experiment(name="tiny", project_root=root, epochs=5)
            output = experiment.regression_dir
            with mock.patch.object(torch, "randperm", side_effect=AssertionError("must not resplit")), \
                 contextlib.redirect_stdout(io.StringIO()):
                TorchRegression.train_for_experiment(experiment, make_figures=False)
            metrics = json.loads((output / "provenance.json").read_text())
            predictions = json.loads((output / "regression_predictions.json").read_text())
            self.assertEqual(metrics["train_ids"], ["a", "b"])
            self.assertEqual(metrics["test_ids"], ["c"])
            self.assertEqual(predictions["train_ids"], ["a", "b"])
            self.assertEqual([row["id"] for row in predictions["documents"]], ["c"])
            checkpoint = torch.load(output / "regression_model.pt", weights_only=True)
            self.assertEqual(checkpoint["train_ids"], ["a", "b"])

    def test_kmeans_fits_only_training_rows_and_evaluates_test_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_fixture(root)
            output = root / "results"
            path = root / "data/processed/metadata.json"
            metadata = json.loads(path.read_text())
            for record in metadata["records"]:
                record.update({field: ("A" if record["id"] == "a" else "B")
                               for field in ("subject", "unit", "type")})
            path.write_text(json.dumps(metadata))
            with mock.patch.multiple(TorchKMeans, ROOT=root, OUTPUT=output, N_CLUSTERS=2, RESTARTS=2), \
                 contextlib.redirect_stdout(io.StringIO()):
                TorchKMeans.main()
            clusters = json.loads((output / "clusters.json").read_text())
            metrics = json.loads((output / "clustering_metrics.json").read_text())
            self.assertEqual([row["id"] for row in clusters["documents"] if row["split"] == "test"], ["c"])
            self.assertEqual((metrics["train_count"], metrics["test_count"]), (2, 1))
            self.assertEqual(metrics["metrics"]["test"]["type"]["accuracy_using_train_cluster_majority"], 1.)
            self.assertIn("adjusted_rand_index", metrics["metrics"]["test"]["unit"])
            checkpoint = torch.load(output / "kmeans_model.pt", weights_only=True)
            torch.testing.assert_close(checkpoint["centers"].flatten().sort().values, torch.tensor([1., 2.]))


if __name__ == "__main__":
    unittest.main()
