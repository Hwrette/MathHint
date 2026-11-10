"""거리 분석의 저장 범위와 후속 실험 금지를 검사한다."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mathhint_analysis.token_analysis.common import dump_json
from mathhint_analysis.token_analysis.distance_comparison.run import check_manifest, run, write_manifest


class DistanceRunTests(unittest.TestCase):
    def test_verify_rejects_a_changed_image_without_rebaselining(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            image = output / "figure.png"
            image.write_bytes(b"original")
            write_manifest(output)
            manifest = (output / "manifest.json").read_bytes()
            image.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "figure.png"):
                check_manifest(output)
            self.assertEqual((output / "manifest.json").read_bytes(), manifest)

    def test_verify_checks_without_writing_validation_or_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "results/token_analysis/04_distance_comparison"
            output.mkdir(parents=True)
            dump_json(output / "config.json", {"protected_files_sha256": {}})
            write_manifest(output)
            before = (output / "manifest.json").read_bytes()
            with patch("mathhint_analysis.token_analysis.distance_comparison.validation.verify",
                       return_value={"passed": 1, "failed": 0, "protected_original_files": 0}) as verify:
                run("verify", root=root)
            verify.assert_called_once_with(root, output, save=False)
            self.assertEqual((output / "manifest.json").read_bytes(), before)
            self.assertFalse((output / "validation.json").exists())

    def test_model_and_stopword_actions_are_not_available(self):
        for action in ("train", "assign", "apply_stopwords", "generate", "normalized_kmeans"):
            with self.subTest(action=action), self.assertRaisesRegex(ValueError, "학습·토큰 제거 명령은 없습니다"):
                run(action)

    def test_existing_final_result_path_cannot_be_used(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(ValueError, "04_distance_comparison"):
                run(root=root, output=root / "results/final_experiment")
            self.assertFalse((root / "results").exists())

    def test_previous_token_result_directory_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(ValueError, "04_distance_comparison"):
                run(root=root, output=root / "results/token_analysis")

    def test_rendering_an_absent_analysis_does_not_start_new_analysis(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(FileNotFoundError, "먼저 analyze"):
                run("report", root=root)
            self.assertFalse((root / "results").exists())
