"""실수 예측 평가와 동률·빈 토큰 집합의 비교 기준을 보호한다."""

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
    from mathhint_learning.VectorComparison import export_comparison, top_tokens, token_overlap, vector_metrics


@unittest.skipIf(torch is None, "Requires torch")
class VectorComparisonTests(unittest.TestCase):
    def test_float_evaluation_preserves_negative_and_fractional_predictions(self):
        predicted, actual = torch.tensor([-0.4, 0.6]), torch.tensor([0., 1.])
        result = vector_metrics(predicted, actual)
        self.assertAlmostEqual(result["mse"], .16)
        self.assertAlmostEqual(result["mae"], .4)
        self.assertLess(result["cosine_similarity"], 1.)
        self.assertEqual(predicted.tolist(), torch.tensor([-0.4, .6]).tolist())

    def test_top_tokens_use_unrounded_values_then_vocabulary_index_and_omit_zeros(self):
        chosen = top_tokens(torch.tensor([1., 1., 1.0001, 0., -4., .0001]), list("abcdef"), k=4)
        self.assertEqual([row["token"] for row in chosen], ["c", "a", "b", "f"])
        self.assertGreater(chosen[-1]["frequency"], 0)
        self.assertEqual(len(top_tokens([0, -1], ["a", "b"])), 0)

    def test_underfilled_precision_reports_fixed_and_available_denominators(self):
        actual = top_tokens([2., 1., 0.], list("abc"))
        predicted = top_tokens([1., 0., 1.], list("abc"))
        overlap = token_overlap(actual, predicted)
        self.assertEqual(overlap["common_top20_count"], 1)
        self.assertEqual(overlap["precision_at_20"], .05)
        self.assertEqual(overlap["precision_at_available_k"], .5)
        empty = token_overlap([], [])
        self.assertEqual(empty["precision_at_20"], 0)
        self.assertIsNone(empty["precision_at_available_k"])
        self.assertIsNone(empty["recall_of_actual_top20"])

    def test_exports_integer_truth_but_keeps_unrounded_raw_and_clipped_floats(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            raw = torch.tensor([[-.25, .6]])
            with mock.patch("mathhint_learning.VectorComparison._plots"), mock.patch("mathhint_learning.VectorComparison._analysis"):
                export_comparison(["item"], ["a", "b"], torch.tensor([[0., 1.]]), raw, torch.tensor([[0., .5]]), path)
            document = json.loads((path / "vectors.json").read_text())["documents"][0]
            self.assertEqual(document["actual_vector"], [0, 1])
            self.assertTrue(all(type(value) is int for value in document["actual_vector"]))
            self.assertEqual(document["raw_predicted_vector"], raw[0].tolist())
            self.assertEqual(document["predicted_vector"], raw[0].clamp_min(0).tolist())
            self.assertNotEqual(document["predicted_vector"], [0, 1])


if __name__ == "__main__":
    unittest.main()
