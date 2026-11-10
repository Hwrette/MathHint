"""후속 실험 차단·원본 변경 감지·사용자 목록 보존을 검증한다."""

from pathlib import Path
import tempfile
import unittest

from mathhint_analysis.token_analysis.common import dump_json, read_json, review_files, sha256
from mathhint_analysis.token_analysis.run import run, save_manifest, verify_saved_tables
from mathhint_analysis.token_analysis.validation import scan_report_links, verify_sources


class TokenRunTests(unittest.TestCase):
    def test_first_validation_accepts_its_own_pending_output_link(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "README.md").write_text("[검증](validation.json) · [잘못된 링크](absent.csv)\n")
            self.assertEqual(scan_report_links(root), (2, [{"source": "README.md", "target": "absent.csv"}]))

    def test_user_stopword_choices_are_not_reset_or_applied(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = review_files(root)
            self.assertEqual([read_json(path) for path in paths], [[], []])
            dump_json(paths[0], ["latex:{"])
            review_files(root)
            self.assertEqual(read_json(paths[0]), ["latex:{"])
            self.assertEqual(read_json(paths[1]), [])

    def test_source_changes_and_missing_files_fail(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "original.txt"
            source.write_text("고정 원본")
            config = {"protected_files_sha256": {"original.txt": sha256(source)}}
            self.assertEqual(verify_sources(root, config), 1)
            source.write_text("변경")
            with self.assertRaisesRegex(ValueError, "original.txt"):
                verify_sources(root, config)
            source.unlink()
            with self.assertRaises(ValueError):
                verify_sources(root, config)

    def test_future_model_actions_are_not_implemented(self):
        for action in ("train", "cluster", "generate", "permutation", "apply_stopwords"):
            with self.subTest(action=action), self.assertRaisesRegex(ValueError, "모델 실험 명령은 없습니다"):
                run(action)

    def test_analysis_cannot_write_into_existing_results(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(ValueError, "token_analysis"):
                run("analyze", root=root, output=root / "results/final_experiment")
            self.assertFalse((root / "results").exists())

    def test_report_rebuild_detects_modified_numeric_tables(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            table = root / "stats.csv"
            table.write_text("token,tf\nlatex:x,1\n")
            review_files(root)
            save_manifest(root)
            verify_saved_tables(root)
            table.write_text("token,tf\nlatex:x,100\n")
            with self.assertRaisesRegex(ValueError, "stats.csv"):
                verify_saved_tables(root)
