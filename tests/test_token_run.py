"""후속 실험 차단·원본 변경 감지·사용자 목록 보존을 검증한다."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mathhint_analysis.token_analysis.common import dump_json, read_json, review_files, sha256
from mathhint_analysis.token_analysis.run import run, save_manifest, verify_saved_tables
from mathhint_analysis.token_analysis.validation import scan_report_links, validate_user_stopwords, verify_sources


class TokenRunTests(unittest.TestCase):
    def test_only_exact_user_owned_lists_are_exempt_from_historical_hashes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            user_name = "results/token_analysis/stopwords/problem_stopwords.json"
            fixed_name = "data/problem_stopwords.json"
            dump_json(root / user_name, [])
            dump_json(root / fixed_name, [])
            config = {"protected_files_sha256": {name: sha256(root / name) for name in (user_name, fixed_name)}}
            dump_json(root / user_name, ["latex:x"])
            self.assertEqual(verify_sources(root, config), 1)
            dump_json(root / fixed_name, ["latex:x"])
            with self.assertRaisesRegex(ValueError, fixed_name):
                verify_sources(root, config)

    def test_user_choices_must_be_unique_strings_in_the_corresponding_vocabulary(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            paths = review_files(output)
            vocabulary = {"problems": ["latex:x"], "solutions": [r"latex:\gamma"]}
            dump_json(paths[0], ["latex:x"])
            dump_json(paths[1], [r"latex:\gamma"])
            before = [p.read_bytes() for p in paths]
            self.assertEqual(validate_user_stopwords(output, vocabulary)["problem"], ["latex:x"])
            self.assertEqual([p.read_bytes() for p in paths], before)
            for invalid in (["latex:x", "latex:x"], [r"latex:\gamma"], [1], {"token": "latex:x"}):
                dump_json(paths[0], invalid)
                with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                    validate_user_stopwords(output, vocabulary)

    def test_verifying_does_not_rewrite_historical_validation_or_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "results/token_analysis"
            dump_json(output / "config.json", {"protected_files_sha256": {}})
            dump_json(output / "validation.json", {"historical": True})
            save_manifest(output)
            before = {p.name: p.read_bytes() for p in output.glob("*.json")}
            with patch("mathhint_analysis.token_analysis.run.verify_analysis",
                       return_value={"passed": 1, "failed": 0, "protected_original_files": 0}) as verify:
                run("verify", root=root)
            verify.assert_called_once_with(root, output, save=False)
            self.assertEqual({p.name: p.read_bytes() for p in output.glob("*.json")}, before)

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
