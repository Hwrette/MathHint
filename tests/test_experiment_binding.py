"""선택한 새 실험이 같은 데이터·모델·예측으로 끝까지 이어지는지 검증한다."""

from dataclasses import replace
import contextlib
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
    from mathhint_learning.Experiment import Experiment, validate_predictions
    from mathhint_learning.TorchData import read_dataset, file_hash
    from mathhint_learning.TorchRegression import train_for_experiment
    from mathhint_learning.VectorComparison import evaluate_for_experiment
    from test_fixed_training import write_fixture


@unittest.skipIf(torch is None, "Requires optional torch dependency")
class ExperimentBindingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        write_fixture(self.root)
        self.exp = Experiment(name="toy", project_root=self.root, epochs=3, seed=7)

    def train(self, experiment=None):
        with contextlib.redirect_stdout(io.StringIO()):
            return train_for_experiment(experiment or self.exp, make_figures=False)

    def test_new_experiment_trains_predicts_evaluates_its_selected_model_and_never_resplits(self):
        with patch.object(torch, "randperm", side_effect=AssertionError("must keep fixed split")):
            result = self.train()
        self.assertEqual(Path(result["checkpoint"]), self.exp.checkpoint)
        self.assertEqual(Path(result["predictions"]), self.exp.predictions)
        verified = validate_predictions(self.exp)
        self.assertEqual(verified["validation"], "data_identity")
        self.assertEqual(verified["predictions"]["model_sha256"], file_hash(self.exp.checkpoint))
        self.assertEqual(verified["predictions"]["test_ids"], ["c"])
        self.assertEqual(verified["checkpoint"]["train_ids"], ["a", "b"])
        document = verified["predictions"]["documents"][0]
        self.assertTrue(all(type(v) is int for v in document["actual_vector"]))
        self.assertTrue(all(type(v) is float for v in document["raw_predicted_vector"]))
        with patch("mathhint_learning.TorchRegression.train_regression", side_effect=AssertionError("evaluation must not train")), contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(evaluate_for_experiment(self.exp, make_figures=False)["reused"])

    def test_nested_checkpoint_uses_its_recorded_learning_curve_and_rejects_changes(self):
        from mathhint_learning.VectorComparison import export_comparison
        experiment = replace(self.exp, checkpoint=self.exp.regression_dir / "models/custom.pt")
        with patch("mathhint_learning.VectorComparison.export_comparison", wraps=export_comparison) as export:
            self.train(experiment)
        curve_path = experiment.regression_dir / "regression_learning_curve.json"
        curve = json.loads(curve_path.read_text())
        self.assertEqual(export.call_args.kwargs["history"], curve)
        self.assertEqual(len(curve), experiment.epochs + 1)
        checkpoint = torch.load(experiment.checkpoint, map_location="cpu", weights_only=True)
        self.assertEqual(checkpoint["learning_curve"], {"path": "../regression_learning_curve.json", "sha256": file_hash(curve_path)})
        provenance = json.loads((experiment.regression_dir / "provenance.json").read_text())
        self.assertEqual(Path(provenance["learning_curve_source"]), curve_path)
        curve[0]["train_mse"] += 1
        curve_path.write_text(json.dumps(curve))
        with self.assertRaisesRegex(ValueError, "regression_learning_curve.json.*학습 곡선 SHA"):
            evaluate_for_experiment(experiment, make_figures=False)

    def test_same_dimension_swapped_vocabulary_is_rejected_with_file_name(self):
        self.train()
        path = self.root / "data/vectors/solutions/vocabulary.json"
        path.write_text(json.dumps(["s2", "s1"]))
        with self.assertRaisesRegex(ValueError, "solutions/vocabulary.json"):
            validate_predictions(self.exp)

    def test_changed_vector_with_unchanged_generation_and_dimensions_is_rejected(self):
        self.train()
        path = self.root / "data/vectors/problems/train_vectors.json"
        value = json.loads(path.read_text())
        value["documents"][0]["vector"][0] += 1
        path.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, "problems/train_vectors.json"):
            validate_predictions(self.exp)

    def test_predictions_from_another_selected_checkpoint_are_not_reused(self):
        self.train()
        other = replace(self.exp, name="other", result_root=self.root / "results/other", checkpoint=None, predictions=None, seed=18)
        self.train(other)
        mismatch = replace(other, predictions=self.exp.predictions)
        with self.assertRaisesRegex(ValueError, "체크포인트 SHA"):
            validate_predictions(mismatch)
        self.assertNotEqual(file_hash(self.exp.checkpoint), file_hash(other.checkpoint))

    def test_missing_selected_checkpoint_or_predictions_never_falls_back(self):
        self.train()
        with self.assertRaises(FileNotFoundError):
            validate_predictions(replace(self.exp, predictions=self.root / "missing.json"))
        with self.assertRaises(FileNotFoundError):
            evaluate_for_experiment(replace(self.exp, checkpoint=self.root / "missing.pt"), make_figures=False)

    def test_training_refuses_published_or_nonempty_result_directory(self):
        with self.assertRaisesRegex(ValueError, "새 result_root"):
            self.train(Experiment(project_root=self.root, epochs=1))
        self.train()
        with self.assertRaises(FileExistsError):
            self.train()

    def test_raw_counts_must_be_finite_nonnegative_integers(self):
        path = self.root / "data/vectors/problems/test_vectors.json"
        original = json.loads(path.read_text())
        for invalid in (.2, -1, float("nan"), True):
            with self.subTest(invalid=invalid):
                value = json.loads(json.dumps(original))
                value["documents"][0]["vector"][0] = invalid
                path.write_text(json.dumps(value))
                with self.assertRaisesRegex(ValueError, "음이 아닌 정수"):
                    read_dataset(self.root)
        path.write_text(json.dumps(original))

    def test_cached_vectors_and_metrics_cannot_silently_belong_to_another_result(self):
        self.train()
        path = self.exp.regression_dir / "vectors.json"
        value = json.loads(path.read_text())
        value["documents"][0]["predicted_vector"][0] += 5
        path.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, "다른 모델·데이터"):
            evaluate_for_experiment(self.exp, make_figures=False)

    def test_cached_summary_must_match_selected_model_evaluation(self):
        self.train()
        path = self.exp.regression_dir / "summary.json"
        value = json.loads(path.read_text())
        value["metrics"]["raw"]["mse"] = 1000000
        path.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, "summary.json"):
            evaluate_for_experiment(self.exp, make_figures=False)

    def test_relative_settings_are_resolved_from_selected_project_not_process_cwd(self):
        experiment = Experiment(name="relative", project_root=self.root,
                                data_root=Path("data"), result_root=Path("results/relative"),
                                checkpoint=Path("results/relative/02_regression/chosen.pt"))
        self.assertEqual(experiment.data_root, self.root / "data")
        self.assertEqual(experiment.result_root, self.root / "results/relative")
        self.assertEqual(experiment.checkpoint, self.root / "results/relative/02_regression/chosen.pt")

    def test_dataset_identity_is_portable_across_data_directory_locations(self):
        import shutil
        before = read_dataset(self.root)["identity"]
        copied = self.root / "separate_data"
        shutil.copytree(self.root / "data", copied)
        after = read_dataset(self.root, copied)["identity"]
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
