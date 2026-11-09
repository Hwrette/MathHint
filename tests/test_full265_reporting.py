"""평가 범위가 다른 표를 섞거나 중복 문항을 보고하지 않는지 확인한다."""

import csv
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

try:
    from mathhint_learning.full_dataset_265.reporting import report_results
except ModuleNotFoundError:
    report_results = None


@unittest.skipIf(report_results is None, "Requires optional learning dependencies")
class FullDatasetReportingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.parent = self.root / "results/final_experiment/01_clustering"
        self.output = self.parent / "full_dataset_265"
        self.output.mkdir(parents=True)
        self.summaries, self.members = [], []
        old = []
        for level, k in (("curriculum", 2), ("unit", 8), ("subunit", 25), ("type", 70)):
            for method in ("euclidean", "spherical"):
                experiment = f"{level}_{method}"
                self.summaries.append(dict(experiment=experiment, level=level, method=method,
                                          k=k, n=265, ari=.3, nmi=.4, full_majority_match_rate=.6))
                old.append(dict(experiment=experiment, level=level, method=method,
                                split="test", n=80, ari=.1, nmi=.2))
                for i in range(265):
                    self.members.append(dict(experiment=experiment, level=level, method=method,
                                             id=f"q{i:03d}", cluster=i % k,
                                             actual_label=f"가짜 과목 / 단원 / 소단원 / 유형 {i % 5}",
                                             original_split="train" if i < 185 else "test"))
        self.holdout = self.parent / "summary.csv"
        with self.holdout.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(old[0]))
            writer.writeheader()
            writer.writerows(old)

    def test_comparison_preserves_different_evaluation_scopes_and_source_csv(self):
        before = self.holdout.read_bytes()
        with patch("mathhint_learning.full_dataset_265.reporting._summary_figures"):
            rows = report_results(self.root, self.output, self.summaries, self.members, [])
        self.assertEqual(len(rows), 8)
        self.assertEqual(rows[0]["holdout_test_ari"], .1)
        self.assertEqual(rows[0]["full_265_ari"], .3)
        self.assertEqual(rows[0]["holdout_test_nmi"], .2)
        self.assertEqual(rows[0]["full_265_nmi"], .4)
        self.assertEqual(rows[0]["holdout_test_n"], 80)
        self.assertEqual(rows[0]["full_fit_and_evaluation_n"], 265)
        self.assertEqual(self.holdout.read_bytes(), before)
        analysis = (self.output / "analysis.md").read_text()
        self.assertIn("일반화 성능이 개선됐다는 뜻이 아니다", analysis)
        self.assertIn("q000", analysis)

    def test_duplicate_question_is_rejected_before_report_is_written(self):
        self.members[1]["id"] = self.members[0]["id"]
        with self.assertRaisesRegex(ValueError, "중복 없이 265"):
            report_results(self.root, self.output, self.summaries, self.members, [])
        self.assertFalse((self.output / "README.md").exists())


if __name__ == "__main__":
    unittest.main()
