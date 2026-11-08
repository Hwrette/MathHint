"""Meaningful checks for fixed-split training and train-only cluster mapping."""

import json
from pathlib import Path
import tempfile
import unittest

try:
    import torch
except ModuleNotFoundError:
    torch = None

if torch is not None:
    from mathhint_learning.RunTraining import fit_fixed_regression, load_fixed_dataset, majority_labels


def write_fixture(root: Path) -> None:
    def save(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")
    save(root / "data/processed/metadata.json", {"generation_id": "fixture", "records": [{"id": i} for i in ("a", "b", "c")]})
    save(root / "data/processed/splits/train.json", ["a", "b"])
    save(root / "data/processed/splits/test.json", ["c"])
    for region, vocabulary, values in (("problems", ["p"], {"a": [1], "b": [2], "c": [3]}),
                                        ("solutions", ["s1", "s2"], {"a": [2, 1], "b": [4, 1], "c": [6, 1]})):
        folder = root / "data/vectors" / region
        save(folder / "vocabulary.json", vocabulary)
        for part, ids in (("train", ["a", "b"]), ("test", ["c"])):
            save(folder / f"{part}_vectors.json", {"generation_id": "fixture", "region": region, "split": part, "vocabulary_file": "vocabulary.json", "vocabulary_fitted_on": "train", "shape": [len(ids), len(vocabulary)],
                 "documents": [{"id": i, "file": i + ".txt", "vector": values[i]} for i in ids]})


@unittest.skipIf(torch is None, "Requires optional torch dependency")
class FixedSplitTrainingTests(unittest.TestCase):
    def test_fixed_loader_preserves_ids_and_different_dimensions(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); write_fixture(root)
            data = load_fixed_dataset(root)
            self.assertEqual(data["ids"], {"train": ["a", "b"], "test": ["c"]})
            self.assertEqual(data["arrays"]["problems"]["train"].shape, (2, 1))
            self.assertEqual(data["arrays"]["solutions"]["test"].shape, (1, 2))

    def test_fixed_loader_rejects_reordered_ids(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); write_fixture(root)
            path = root / "data/vectors/solutions/train_vectors.json"
            data = json.loads(path.read_text()); data["documents"].reverse(); path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "ID order"):
                load_fixed_dataset(root)

    def test_fixed_loader_rejects_train_test_overlap(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); write_fixture(root)
            (root / "data/processed/splits/test.json").write_text('["a"]')
            with self.assertRaisesRegex(ValueError, "overlap"):
                load_fixed_dataset(root)

    def test_fixed_loader_rejects_vocabulary_not_train_only(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); write_fixture(root)
            path = root / "data/vectors/problems/test_vectors.json"
            data = json.loads(path.read_text()); data["vocabulary_fitted_on"] = "all"; path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "training data only"):
                load_fixed_dataset(root)

    def test_fixed_loader_rejects_mixed_generations(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); write_fixture(root)
            path = root / "data/vectors/problems/test_vectors.json"
            data = json.loads(path.read_text()); data["generation_id"] = "stale"; path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "generation IDs"):
                load_fixed_dataset(root)

    def test_fixed_model_learns_train_rows_without_accepting_test_targets(self):
        X = torch.tensor([[float(i), float(i % 3)] for i in range(12)])
        Y = X @ torch.tensor([[2., -1.], [1., 3.]]) + 2
        first, history = fit_fixed_regression(X[:9], Y[:9], epochs=1000, learning_rate=.04, seed=17)
        # Even wildly different held-out targets cannot enter this training API.
        changed_holdout = Y[9:] + 10000
        second, second_history = fit_fixed_regression(X[:9], Y[:9], epochs=1000, learning_rate=.04, seed=17)
        self.assertLess(history[-1]["train_mse"], history[0]["train_mse"] * .01)
        self.assertEqual(history, second_history)
        for key, value in first.state_dict().items():
            self.assertTrue(torch.equal(value, second.state_dict()[key]))
        self.assertGreater(torch.mean((first(X[9:]) - changed_holdout)**2).item(), 1e6)

    def test_majority_cluster_label_ties_are_deterministic(self):
        # No test labels are passed. Unknown test clusters should remain unmapped.
        mapping = majority_labels([0, 0, 1, 1, 1], ["b", "a", "c", "c", "d"])
        self.assertEqual(mapping, {0: "a", 1: "c"})
        self.assertIsNone(mapping.get(2))


if __name__ == "__main__":
    unittest.main()
