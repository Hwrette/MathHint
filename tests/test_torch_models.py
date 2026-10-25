"""문제·해설 행렬의 짝짓기, 회귀의 평가 분리, K-means 계산을 검사합니다."""

import json
from pathlib import Path
import tempfile
import unittest

# 문서 전처리만 사용하는 환경에서는 PyTorch 검사만 건너뜁니다.
try:
    import torch
except ModuleNotFoundError as error:
    if error.name != "torch":
        raise
    torch = None

if torch is not None:
    from TorchData import load_frequency_matrix, load_paired_matrices
    from TorchKMeans import assign_clusters, fit_kmeans
    from TorchRegression import train_regression


def write_vectors(root, name, documents, vocabulary, shape=None):
    """토큰 분석 없이, 검사에 필요한 작은 JSON 행렬을 직접 만듭니다."""
    folder = root / name
    folder.mkdir()
    (folder / "vocabulary.json").write_text(
        json.dumps(vocabulary, ensure_ascii=False), encoding="utf-8-sig",
    )
    path = folder / "frequency_vectors.json"
    path.write_text(json.dumps({
        "vocabulary_file": "vocabulary.json",
        "shape": shape if shape is not None else [len(documents), len(vocabulary)],
        "documents": documents,
    }, ensure_ascii=False), encoding="utf-8-sig")
    return path


@unittest.skipIf(torch is None, "학습 검사는 python -m pip install torch 후 실행하세요.")
class TorchDataTests(unittest.TestCase):
    def test_json_rows_and_vocabulary_keep_their_order(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_vectors(Path(directory), "problems", [
                {"file": "002.txt", "vector": [3, 0]},
                {"file": "001.txt", "vector": [1, 2]},
            ], ["latex:x", "kiwi:값"])
            files, matrix, vocabulary = load_frequency_matrix(path)
            self.assertEqual(files, ["002.txt", "001.txt"])
            self.assertEqual(vocabulary, ["latex:x", "kiwi:값"])
            self.assertEqual(matrix.dtype, torch.float32)
            torch.testing.assert_close(matrix, torch.tensor([[3., 0.], [1., 2.]]))

    def test_shuffled_solutions_pair_by_exact_filename_with_different_dimensions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            problems = write_vectors(root, "problems", [
                {"file": "a/001.txt", "vector": [1, 2]},
                {"file": "b/001.txt", "vector": [3, 4]},
            ], ["latex:x", "latex:y"])
            solutions = write_vectors(root, "solutions", [
                {"file": "b/001.txt", "vector": [30, 40, 50]},
                {"file": "a/001.txt", "vector": [10, 20, 30]},
            ], ["kiwi:계산", "kiwi:값", "latex:2"])
            files, X, Y, problem_vocabulary, solution_vocabulary = load_paired_matrices(problems, solutions)
            self.assertEqual(files, ["a/001.txt", "b/001.txt"])
            self.assertEqual(X.shape, (2, 2))
            self.assertEqual(Y.shape, (2, 3))
            self.assertEqual(len(problem_vocabulary), 2)
            self.assertEqual(len(solution_vocabulary), 3)
            torch.testing.assert_close(Y, torch.tensor([[10., 20., 30.], [30., 40., 50.]]))

    def test_missing_or_extra_solution_filenames_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            problems = write_vectors(root, "problems", [
                {"file": "001.txt", "vector": [1]},
                {"file": "002.txt", "vector": [2]},
            ], ["latex:x"])
            for name, files in (("missing", ["001.txt"]),
                                ("extra", ["001.txt", "002.txt", "003.txt"]),
                                ("wrong_path", ["001.txt", "sub/002.txt"])):
                with self.subTest(case=name):
                    solutions = write_vectors(root, name,
                        [{"file": file, "vector": [1]} for file in files], ["kiwi:값"])
                    with self.assertRaises(ValueError):
                        load_paired_matrices(problems, solutions)

    def test_invalid_matrix_metadata_or_values_are_rejected(self):
        cases = [
            ("ragged", [{"file": "001.txt", "vector": [1]}], ["x", "y"], None),
            ("wrong_shape", [{"file": "001.txt", "vector": [1, 2]}], ["x", "y"], [2, 2]),
            ("duplicate_file", [{"file": "001.txt", "vector": [1]},
                                {"file": "001.txt", "vector": [2]}], ["x"], None),
            ("duplicate_token", [{"file": "001.txt", "vector": [1, 2]}], ["x", "x"], None),
            ("nonstr_token", [{"file": "001.txt", "vector": [1]}], [1], None),
            ("empty_vocabulary", [{"file": "001.txt", "vector": []}], [], None),
            ("negative", [{"file": "001.txt", "vector": [-1]}], ["x"], None),
            ("boolean", [{"file": "001.txt", "vector": [True]}], ["x"], None),
            ("nan", [{"file": "001.txt", "vector": [float("nan")]}], ["x"], None),
            ("float32_overflow", [{"file": "001.txt", "vector": [1e100]}], ["x"], None),
        ]
        with tempfile.TemporaryDirectory() as directory:
            for name, documents, vocabulary, shape in cases:
                with self.subTest(case=name):
                    path = write_vectors(Path(directory), name, documents, vocabulary, shape)
                    with self.assertRaises(ValueError):
                        load_frequency_matrix(path)


@unittest.skipIf(torch is None, "학습 검사는 python -m pip install torch 후 실행하세요.")
class TorchRegressionTests(unittest.TestCase):
    def test_multioutput_regression_learns_a_known_linear_mapping(self):
        # 구현 예제의 성능을 주장하기 위한 데이터가 아니라, 계산을 검증하는 합성 행렬입니다.
        X = torch.tensor([[float(a), float(b)] for a in range(4) for b in range(4)])
        Y = X @ torch.tensor([[1., 2., .5], [2., -1., 1.]]) + torch.tensor([0., 3., 1.])
        result = train_regression(X, Y, epochs=1200, learning_rate=.05, seed=7)
        self.assertEqual(result["predictions"].shape, (16, 3))
        self.assertLess(result["train_mse"], result["initial_train_mse"] * .01)
        self.assertLess(result["train_mse"], .02)
        self.assertLess(result["test_mse"], .03)
        train = set(result["train_indices"].tolist())
        test = set(result["test_indices"].tolist())
        self.assertFalse(train & test)
        self.assertEqual(train | test, set(range(16)))

    def test_changing_only_holdout_targets_cannot_change_trained_weights(self):
        X = torch.tensor([[float(i), float(i % 3)] for i in range(10)])
        Y = torch.stack((X[:, 0] + X[:, 1], 2 * X[:, 0] + 1), dim=1)
        first = train_regression(X, Y, epochs=50, seed=19)
        changed_Y = Y.clone()
        changed_Y[first["test_indices"]] += 1000
        second = train_regression(X, changed_Y, epochs=50, seed=19)
        self.assertTrue(torch.equal(first["test_indices"], second["test_indices"]))
        for key, value in first["model"].state_dict().items():
            self.assertTrue(torch.equal(value, second["model"].state_dict()[key]))
        self.assertTrue(torch.equal(first["predictions"], second["predictions"]))
        self.assertGreater(second["test_mse"], first["test_mse"])

    def test_invalid_regression_shapes_or_hyperparameters_are_rejected(self):
        X, Y = torch.ones(3, 2), torch.ones(3, 4)
        invalid = [
            (X[:1], Y[:1], {}), (X, Y[:2], {}), (X, Y[:, 0], {}),
            (X, Y, {"epochs": 0}), (X, Y, {"learning_rate": 0}),
            (X, Y, {"test_fraction": 1}), (X, Y, {"test_fraction": 0}),
            (X * float("nan"), Y, {}),
        ]
        for matrix, targets, options in invalid:
            with self.subTest(options=options, shapes=(matrix.shape, targets.shape)):
                with self.assertRaises(ValueError):
                    train_regression(matrix, targets, **options)


@unittest.skipIf(torch is None, "학습 검사는 python -m pip install torch 후 실행하세요.")
class TorchKMeansTests(unittest.TestCase):
    def test_three_clear_groups_have_expected_centers_and_squared_distances(self):
        X = torch.tensor([[0., 0.], [0., 2.], [10., 10.], [10., 12.], [20., 0.], [22., 0.]])
        first = fit_kmeans(X, n_clusters=3, seed=42)
        second = fit_kmeans(X, n_clusters=3, seed=42)
        self.assertTrue(torch.equal(first["centers"], second["centers"]))
        self.assertTrue(torch.equal(first["assignments"], second["assignments"]))
        centers = first["centers"][first["centers"][:, 0].argsort()]
        torch.testing.assert_close(centers, torch.tensor([[0., 1.], [10., 11.], [21., 0.]]))
        self.assertAlmostEqual(first["inertia"], 6.)
        groups = first["assignments"].tolist()
        self.assertEqual(groups[0], groups[1])
        self.assertEqual(groups[2], groups[3])
        self.assertEqual(groups[4], groups[5])
        self.assertEqual(len(set(groups)), 3)

    def test_assignments_match_final_centers_even_at_iteration_limit(self):
        X = torch.tensor([[0.], [4.], [5.], [6.], [20.], [22.]])
        result = fit_kmeans(X, n_clusters=2, max_iter=1, seed=42)
        # 거리를 직접 계산해 마지막 중심 기준으로 배정됐는지 독립적으로 확인합니다.
        squared_distances = ((X[:, None, :] - result["centers"][None, :, :]) ** 2).sum(dim=2)
        nearest = squared_distances.argmin(dim=1)
        self.assertTrue(torch.equal(result["assignments"], nearest))
        self.assertTrue(torch.equal(assign_clusters(X, result["centers"]), nearest))
        expected_inertia = ((X - result["centers"][nearest]) ** 2).sum().item()
        self.assertAlmostEqual(result["inertia"], expected_inertia)

    def test_invalid_cluster_counts_and_identical_points(self):
        X = torch.tensor([[0., 0.], [1., 1.], [2., 2.]])
        for k in (0, -1, 1.5, True, 4):
            with self.subTest(k=k):
                with self.assertRaises(ValueError):
                    fit_kmeans(X, n_clusters=k)
        identical = torch.ones(4, 2)
        single = fit_kmeans(identical, n_clusters=1)
        self.assertEqual(single["inertia"], 0)
        self.assertEqual(single["assignments"].tolist(), [0, 0, 0, 0])
        torch.testing.assert_close(single["centers"], torch.ones(1, 2))
        with self.assertRaises(ValueError):
            fit_kmeans(identical, n_clusters=2)


if __name__ == "__main__":
    unittest.main()
