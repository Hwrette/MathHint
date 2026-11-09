"""새 안내를 재집계에서도 보존하며 기존 문서는 그대로 생성한다."""

from pathlib import Path
import tempfile
import unittest

from mathhint_learning.holdout import preserve_navigation


class ClusteringNavigationTests(unittest.TestCase):
    def test_only_marked_navigation_survives_a_report_rebuild(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "README.md"
            block = "<!-- clustering-additions:start -->\n[전체265](full_dataset_265/README.md)\n<!-- clustering-additions:end -->"
            path.write_text("# 이전 제목\n\n" + block + "\n\n이전 집계\n")
            rebuilt = preserve_navigation(path, "# 새 제목\n\n새 집계\n")
            self.assertEqual(rebuilt, "# 새 제목\n\n" + block + "\n\n새 집계\n")
            self.assertNotIn("이전 집계", rebuilt)

    def test_no_new_navigation_leaves_generated_content_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "README.md"
            self.assertEqual(preserve_navigation(path, "# 원래 안내\n"), "# 원래 안내\n")
            path.write_text("# 이전 안내\n")
            self.assertEqual(preserve_navigation(path, "# 원래 안내\n"), "# 원래 안내\n")
