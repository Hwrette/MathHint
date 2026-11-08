"""최종 보고서가 실제 출력의 검토만 사용하고 AI와 사람을 혼동하지 않게 한다."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mathhint_analysis import AnalyzeThreeWay as analysis


class ReviewEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.folder = Path(self.temporary.name)
        self.output = "중간 계산 2+2=5는 틀렸지만 최종정답: 4"
        self.latest = {("q", "oracle_hint"): {
            "status": "success", "output_text": self.output, "evaluation": {"correct": True},
        }}
        self.review = {
            "id": "q", "method": "oracle_hint", "reviewer_type": "AI_assisted",
            "human_confirmed": False, "math_status": "inappropriate",
            "response_sha256": hashlib.sha256(self.output.encode()).hexdigest(),
            "quote": "2+2=5", "reason": "최종 답과 별도로 중간 계산 오류가 있다.",
            "final_answer_original_correct": True,
        }
        self.legacy = patch.object(analysis, "LEGACY", self.folder / "no_legacy")
        self.legacy.start()
        self.addCleanup(self.legacy.stop)
        self.addCleanup(self.temporary.cleanup)

    def save_review(self):
        (self.folder / "solution_review.json").write_text(json.dumps({
            "reviewer_type": "AI_assisted", "human_confirmed": False,
            "records": [self.review],
        }), encoding="utf-8")

    def test_correct_answer_and_ai_review_are_separate_from_human_confirmation(self):
        self.save_review()
        result = analysis.review_evidence(self.folder, self.latest)
        self.assertEqual(result["human_reviewed_count"], 0)
        self.assertFalse(result["new_review"]["human_confirmed"])
        self.assertEqual(result["new_review_counts"]["oracle_hint"], {"inappropriate": 1})
        self.assertEqual(result["new_review_correct_answer_with_issues"], ["q"])
        self.assertEqual(result["new_review_wrong_answer_with_issues"], [])

    def test_changed_output_cannot_reuse_an_old_review(self):
        self.save_review()
        self.latest["q", "oracle_hint"]["output_text"] += " 변경"
        with self.assertRaisesRegex(ValueError, "출력 해시"):
            analysis.review_evidence(self.folder, self.latest)

    def test_review_quote_must_be_in_the_actual_output(self):
        self.review["quote"] = "실제 응답에 없는 문장"
        self.save_review()
        with self.assertRaisesRegex(ValueError, "인용문"):
            analysis.review_evidence(self.folder, self.latest)

    def test_unreviewed_success_and_api_error_are_not_automatically_assessed(self):
        self.latest["failed", "oracle_hint"] = {
            "status": "api_error", "output_text": "", "evaluation": {"correct": None},
        }
        result = analysis.review_evidence(self.folder, self.latest)
        self.assertIsNone(result["new_review"])
        self.assertEqual(result["ai_review"], {})
        self.assertEqual(result["human_reviewed_count"], 0)


if __name__ == "__main__":
    unittest.main()
