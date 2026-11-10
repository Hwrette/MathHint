"""새 풀이 데이터의 사용자 선택·어휘/행 정렬·읽기 전용 검증을 보호한다."""

from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np

from mathhint_learning.final_experiment_2.solution_data.common import ROOT, OUTPUT
from mathhint_learning.final_experiment_2.solution_data.validation import (
    independent_scores, validate_dataset, validate_filter, validate_model)


class SolutionDataValidationTests(unittest.TestCase):
    def test_independent_metrics_keep_fixed20_precision_and_available_recall(self):
        prediction = np.array([[2., 0., 5.], [0., 0., 0.]])
        actual = np.array([[2., 1., 0.], [0., 3., 0.]])
        result = independent_scores(prediction, actual)
        self.assertAlmostEqual(result["mse"], 35 / 6)
        self.assertAlmostEqual(result["mae"], 1.5)
        self.assertAlmostEqual(result["precision_at_20"], .025)
        self.assertAlmostEqual(result["recall_at_20"], .25)
        self.assertAlmostEqual(result["mean_common_top20_count"], .5)
        self.assertEqual(result["predicted_fewer_than_20"], 2)
        self.assertIsNone(independent_scores([[0., 0.]], [[0., 0.]])["recall_at_20"])

    def test_duplicate_choices_do_not_change_user_list_or_counts(self):
        raw = np.array([[3, 1, 4], [2, 5, 0]])
        vocabulary = ["latex:2", r"latex:\lim", "kiwi:연속"]
        choices = ["latex:2", "latex:2"]
        before = list(choices)
        self.assertEqual(validate_filter(raw, raw[:, 1:], vocabulary, vocabulary[1:], [1, 2], choices), [1, 2])
        self.assertEqual(choices, before)
        np.testing.assert_array_equal(raw, [[3, 1, 4], [2, 5, 0]])

    def test_same_dimension_wrong_token_order_and_wrong_document_order_fail(self):
        raw = np.array([[3, 1, 4], [2, 5, 0]])
        vocabulary = ["latex:2", r"latex:\lim", "kiwi:연속"]
        cases = [(raw[:, [2, 1]], vocabulary[2:] + vocabulary[1:2], [2, 1]),
                 (raw[::-1, 1:], vocabulary[1:], [1, 2]),
                 (raw[:, :2], vocabulary[:2], [0, 1])]
        for values, words, indices in cases:
            with self.subTest(indices=indices), self.assertRaises(ValueError):
                validate_filter(raw, values, vocabulary, words, indices, ["latex:2"])

    def test_negative_and_fractional_original_counts_fail(self):
        for value in (-1, .5, np.nan):
            raw = np.array([[value, 1.]])
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_filter(raw, raw.copy(), ["latex:x", "latex:y"], ["latex:x", "latex:y"], [0, 1], [])

    def test_saved_data_validation_is_read_only_and_does_not_prepare_or_train(self):
        before = {str(p.relative_to(OUTPUT)): p.read_bytes() for p in OUTPUT.rglob("*") if p.is_file()}
        with patch("mathhint_learning.final_experiment_2.solution_data.prepare.prepare",
                   side_effect=AssertionError("원문 재처리 금지")) as prepare, \
             patch("mathhint_learning.TorchRegression.train_regression",
                   side_effect=AssertionError("검증에서 학습 금지")) as train:
            result = validate_dataset(ROOT, save=False)
        self.assertTrue(result["complete"], [c for c in result["checks"] if not c["passed"]])
        self.assertEqual(result["api_calls"], 0)
        self.assertEqual(result["tokenizer_calls"], 0)
        self.assertEqual({str(p.relative_to(OUTPUT)): p.read_bytes() for p in OUTPUT.rglob("*") if p.is_file()}, before)
        prepare.assert_not_called()
        train.assert_not_called()

    def test_saved_linear_model_matches_predictions_without_retraining(self):
        output = ROOT / "results/final_experiment_2/regression"
        before = {str(p.relative_to(output)): p.read_bytes() for p in output.rglob("*") if p.is_file()}
        with patch("mathhint_learning.final_experiment_2.regression.model.fit_model",
                   side_effect=AssertionError("동결 모델 검증에서 학습 금지")) as train:
            result = validate_model(ROOT, "regression", save=False)
        self.assertTrue(result["complete"], [c for c in result["checks"] if not c["passed"]])
        self.assertEqual(result["prediction_rows"], 265)
        self.assertEqual(result["test_rows"], 80)
        self.assertEqual({str(p.relative_to(output)): p.read_bytes() for p in output.rglob("*") if p.is_file()}, before)
        train.assert_not_called()

    def test_saved_nonlinear_model_and_seed_selection_verify_without_training(self):
        output = ROOT / "results/final_experiment_2/deep_learning"
        before = {str(p.relative_to(output)): p.read_bytes() for p in output.rglob("*") if p.is_file()}
        with patch("mathhint_learning.final_experiment_2.deep_learning.model.fit_candidate",
                   side_effect=AssertionError("딥러닝 후보 재학습 금지")) as fit, \
             patch("mathhint_learning.final_experiment_2.deep_learning.model.refit_full_training",
                   side_effect=AssertionError("딥러닝 최종 재학습 금지")) as refit:
            result = validate_model(ROOT, "deep_learning", save=False)
        self.assertTrue(result["complete"], [c for c in result["checks"] if not c["passed"]])
        self.assertEqual(result["prediction_rows"], 265)
        self.assertEqual(result["test_rows"], 80)
        self.assertEqual({str(p.relative_to(output)): p.read_bytes() for p in output.rglob("*") if p.is_file()}, before)
        fit.assert_not_called()
        refit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
