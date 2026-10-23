"""폴더의 토큰 합집합과 문서별 벡터가 같은 인덱스를 사용하는지 검사합니다."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

# HWPX 전처리만 사용하는 환경에서는 Kiwi 관련 검사만 건너뜁니다.
try:
    import BuildFrequencyVectors as vectors
except ModuleNotFoundError as error:
    if error.name != "kiwipiepy":
        raise
    vectors = None


@unittest.skipIf(vectors is None, "빈도벡터 검사는 python -m pip install kiwipiepy 후 실행하세요.")
class FrequencyVectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 실제 Kiwi를 사용하며 여러 검사에서 한 객체를 재사용합니다.
        cls.kiwi = vectors.Kiwi(num_workers=1)

    def test_mixed_files_share_exact_vocabulary_and_vectors(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            # 생성 순서와 다른 파일명 순서를 사용하고 대문자 확장자도 확인합니다.
            (folder / "b.TXT").write_text("사과 $y+2$ 사과", encoding="utf-8")
            (folder / "a.txt").write_text("값 $x+x$", encoding="utf-8-sig")
            (folder / "안내.md").write_text("분석하지 않는 문서", encoding="utf-8")

            with patch.object(vectors, "count_tokens", wraps=vectors.count_tokens) as analyze:
                result = vectors.build_frequency_vectors(folder, kiwi=self.kiwi)

            self.assertEqual(result["vocabulary"], [
                "kiwi:값", "kiwi:사과", "latex:+", "latex:2", "latex:x", "latex:y",
            ])
            self.assertEqual(result["shape"], [2, 6])
            self.assertEqual(result["documents"], [
                {"file": "a.txt", "vector": [1, 0, 1, 0, 2, 0],
                 "token_count": 4, "ignored_token_count": 0},
                {"file": "b.TXT", "vector": [0, 2, 1, 1, 0, 1],
                 "token_count": 5, "ignored_token_count": 0},
            ])
            # 파일은 한 번씩만 분석하고, 같은 Kiwi 객체를 전달해야 합니다.
            self.assertEqual(analyze.call_count, 2)
            for call in analyze.call_args_list:
                self.assertIs(call.args[1], self.kiwi)
            self.assertEqual(vectors.build_frequency_vectors(folder, kiwi=self.kiwi), result)

    def test_frozen_vocabulary_keeps_index_zero_and_ignores_unknown_tokens(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "new.txt").write_text("값 $x+x+y$", encoding="utf-8")
            # 일부러 정렬하지 않은 목록을 전달해 기존 순서가 유지되는지 봅니다.
            vocabulary = ["latex:x", "kiwi:값", "latex:missing"]
            result = vectors.build_frequency_vectors(
                folder, vocabulary=vocabulary, kiwi=self.kiwi,
            )
            self.assertEqual(result["vocabulary"], vocabulary)
            self.assertEqual(vocabulary, ["latex:x", "kiwi:값", "latex:missing"])
            self.assertEqual(result["shape"], [1, 3])
            self.assertEqual(result["documents"], [
                {"file": "new.txt", "vector": [2, 1, 0],
                 "token_count": 6, "ignored_token_count": 3},
            ])

    def test_explicit_empty_vocabulary_does_not_create_a_new_one(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "new.txt").write_text("$x+x$", encoding="utf-8")
            result = vectors.build_frequency_vectors(folder, vocabulary=[], kiwi=self.kiwi)
            self.assertEqual(result["vocabulary"], [])
            self.assertEqual(result["shape"], [1, 0])
            self.assertEqual(result["documents"], [
                {"file": "new.txt", "vector": [],
                 "token_count": 3, "ignored_token_count": 3},
            ])

    def test_empty_file_is_retained_as_a_zero_vector(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "empty.txt").write_text(" \n\t", encoding="utf-8")
            empty_result = vectors.build_frequency_vectors(folder, kiwi=self.kiwi)
            self.assertEqual(empty_result["shape"], [1, 0])
            self.assertEqual(empty_result["documents"][0]["vector"], [])

            (folder / "math.txt").write_text("$x$", encoding="utf-8")
            result = vectors.build_frequency_vectors(folder, kiwi=self.kiwi)
            self.assertEqual(result["vocabulary"], ["latex:x"])
            self.assertEqual(result["documents"], [
                {"file": "empty.txt", "vector": [0],
                 "token_count": 0, "ignored_token_count": 0},
                {"file": "math.txt", "vector": [1],
                 "token_count": 1, "ignored_token_count": 0},
            ])

    def test_recursion_is_optional_and_duplicate_basenames_stay_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "001.txt").write_text("$x$", encoding="utf-8")
            for subfolder, formula in (("b", "$x+y$"), ("a", "$y$")):
                (folder / subfolder).mkdir()
                (folder / subfolder / "001.txt").write_text(formula, encoding="utf-8")

            direct = vectors.build_frequency_vectors(folder, kiwi=self.kiwi)
            self.assertEqual(direct["vocabulary"], ["latex:x"])
            self.assertEqual([doc["file"] for doc in direct["documents"]], ["001.txt"])

            recursive = vectors.build_frequency_vectors(folder, recursive=True, kiwi=self.kiwi)
            self.assertEqual(recursive["vocabulary"], ["latex:+", "latex:x", "latex:y"])
            self.assertEqual(recursive["shape"], [3, 3])
            self.assertEqual([doc["file"] for doc in recursive["documents"]],
                             ["001.txt", "a/001.txt", "b/001.txt"])
            self.assertEqual([doc["vector"] for doc in recursive["documents"]],
                             [[0, 1, 0], [0, 0, 1], [1, 1, 1]])

    def test_missing_or_empty_folder_reports_the_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            for path in (folder / "없는폴더", folder):
                with self.subTest(path=path):
                    with self.assertRaises(ValueError) as raised:
                        vectors.build_frequency_vectors(path, kiwi=self.kiwi)
                    self.assertIn(str(path), str(raised.exception))

    def test_invalid_text_reports_the_offending_filename(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            path = folder / "잘못된문제.txt"
            for contents, expected in ((b"$x", "수식이 닫히지 않았습니다"), (b"\xff", "codec")):
                with self.subTest(contents=contents):
                    path.write_bytes(contents)
                    with self.assertRaises(ValueError) as raised:
                        vectors.build_frequency_vectors(folder, kiwi=self.kiwi)
                    self.assertIn(str(path), str(raised.exception))
                    self.assertIn(expected, str(raised.exception))

    def test_invalid_vocabulary_cannot_create_ambiguous_indices(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "problem.txt").write_text("$x$", encoding="utf-8")
            for vocabulary in ("latex:x", [1], ["latex:x", "latex:x"]):
                with self.subTest(vocabulary=vocabulary):
                    with self.assertRaises(ValueError):
                        vectors.build_frequency_vectors(
                            folder, vocabulary=vocabulary, kiwi=self.kiwi,
                        )

    def test_saved_vocabulary_and_vectors_can_be_reused_for_new_problems(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            training = root / "training"
            training.mkdir()
            (training / "001.txt").write_text("$x+y$", encoding="utf-8")
            (training / "002.txt").write_text("$x$", encoding="utf-8")
            original = vectors.build_frequency_vectors(training, kiwi=self.kiwi)

            vocabulary_path, vectors_path = vectors.save_results(original, training / "results")
            vocabulary_bytes = vocabulary_path.read_bytes()
            vocabulary = json.loads(vocabulary_path.read_text(encoding="utf-8"))
            saved_vectors = json.loads(vectors_path.read_text(encoding="utf-8"))
            self.assertEqual(vocabulary, ["latex:+", "latex:x", "latex:y"])
            self.assertEqual(saved_vectors["vocabulary_file"], "vocabulary.json")
            self.assertEqual(saved_vectors["shape"], original["shape"])
            self.assertEqual(saved_vectors["documents"], original["documents"])

            # 입력 안에 저장한 JSON이 재실행 때 텍스트로 분석되지 않아야 합니다.
            self.assertEqual(
                vectors.build_frequency_vectors(training, recursive=True, kiwi=self.kiwi),
                original,
            )

            new_problems = root / "new"
            new_problems.mkdir()
            (new_problems / "003.txt").write_text("$z+x+x$", encoding="utf-8")
            transformed = vectors.build_frequency_vectors(
                new_problems, vocabulary=vocabulary, kiwi=self.kiwi,
            )
            vectors.save_results(transformed, root / "transformed")
            self.assertEqual(transformed["vocabulary"], vocabulary)
            self.assertEqual(transformed["documents"], [
                {"file": "003.txt", "vector": [2, 2, 0],
                 "token_count": 5, "ignored_token_count": 1},
            ])
            self.assertEqual(vocabulary_path.read_bytes(), vocabulary_bytes)


if __name__ == "__main__":
    unittest.main()
