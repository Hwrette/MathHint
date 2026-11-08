"""정답 일치와 풀이 적절성의 분리 및 검토 기록 무결성을 검사한다."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from mathhint_solver.SolutionReview import (
    CRITERIA, build_review_bundle, export_review_files, overall_rating,
    summarize_reviews, validate_review_bundle, import_ai_suggestions, mathematical_appropriateness,
)


def response(identifier="q1", method="baseline", *, status="success", output="중간 계산 2+2=4. 따라서 답은4."):
    return {"id": identifier, "method": method, "config_id": "fixed_config", "status": status,
            "problem_text": "2+2는?", "output_text": output if status == "success" else "",
            "reference_answer_text": "4", "reference_solution": "정답4", "evaluation": {"correct": True},
            "input_text": "이 비밀 힌트를 보이지 마세요", "usage": {"total_token_count": 123}}


def reviewed(item, *, kind="human", rating="appropriate"):
    item["reviewer"] = {"id": "reviewer-1", "kind": kind}
    item["reviewed_at"] = "2026-11-07T00:00:00+00:00"
    item["rubric"] = {name: {"rating": rating, "evidence_quotes": ["2+2=4"], "explanation": "계산과 설명을 확인했습니다."} for name in CRITERIA}


class SolutionReviewTests(unittest.TestCase):
    def test_correct_answer_never_auto_rates_reasoning_and_errors_excluded(self):
        packet, key = build_review_bundle([response(), response("q2", status="api_error")], expected_responses=4)
        self.assertEqual(len(packet["items"]), 1)
        self.assertEqual(packet["counts"]["excluded_non_success"], 1)
        self.assertEqual(packet["counts"]["not_recorded_yet"], 2)
        self.assertTrue(all(x["rating"] == "unreviewed" for x in packet["items"][0]["rubric"].values()))
        summary = summarize_reviews(packet, key)["review_kinds"]["human"]["baseline"]["overall"]
        self.assertEqual(summary["reviewed_count"], 0)
        self.assertIsNone(summary["appropriate_rate_on_reviewed"])

    def test_blind_packet_hides_method_hint_tokens_and_automatic_grade(self):
        packet, _ = build_review_bundle([response()])
        encoded = json.dumps(packet, ensure_ascii=False)
        for secret in ("baseline", "regression_hint", "비밀 힌트", "total_token_count", '"evaluation"'):
            self.assertNotIn(secret, encoded)

    def test_reviewed_denominator_and_ai_suggestions_remain_separate(self):
        packet, key = build_review_bundle([response("a"), response("b"), response("c"), response("d", "regression_hint")])
        indexed = {item["question_id"]: item for item in packet["items"]}
        reviewed(indexed["a"])
        reviewed(indexed["b"], kind="ai_suggestion", rating="inappropriate")
        reviewed(indexed["d"], rating="uncertain")
        summary = summarize_reviews(packet, key)
        human = summary["review_kinds"]["human"]["baseline"]["overall"]
        self.assertEqual(human["reviewed_count"], 1)
        self.assertEqual(human["unreviewed"], 1)
        self.assertEqual(human["appropriate_rate_on_reviewed"], 1)
        uncertain = summary["review_kinds"]["human"]["regression_hint"]["overall"]
        self.assertEqual(uncertain["reviewed_count"], 1)
        self.assertEqual(uncertain["decisive_count"], 0)
        self.assertIsNone(uncertain["appropriate_rate_on_decisive"])

    def test_quotes_reviewer_and_output_hash_are_validated(self):
        packet, _ = build_review_bundle([response()])
        item = packet["items"][0]
        reviewed(item)
        validate_review_bundle(packet)
        item["rubric"]["logical_validity"]["evidence_quotes"] = ["출력에 없는 문장"]
        with self.assertRaisesRegex(ValueError, "인용문"):
            validate_review_bundle(packet)
        item["rubric"]["logical_validity"]["evidence_quotes"] = ["2+2=4"]
        item["reviewer"]["id"] = ""
        with self.assertRaisesRegex(ValueError, "검토자"):
            validate_review_bundle(packet)
        item["reviewer"]["id"] = "reviewer"
        item["output_text"] += " 변경"
        with self.assertRaisesRegex(ValueError, "해시"):
            validate_review_bundle(packet)

    def test_changed_output_creates_new_unreviewed_item(self):
        records = [response()]
        packet, _ = build_review_bundle(records)
        reviewed(packet["items"][0])
        same, _ = build_review_bundle(records, previous=packet)
        self.assertEqual(overall_rating(same["items"][0]), "appropriate")
        records[0]["output_text"] = "다른 풀이 2+2=4."
        changed, _ = build_review_bundle(records, previous=packet)
        self.assertEqual(overall_rating(changed["items"][0]), "unreviewed")

    def test_export_has_blind_html_csv_schema_and_private_key(self):
        packet, key = build_review_bundle([response(output="2+2=4. <script>unsafe</script>")])
        with tempfile.TemporaryDirectory() as directory:
            export_review_files(packet, key, Path(directory))
            page = (Path(directory) / "blind_review.html").read_text()
            self.assertNotIn("<script>unsafe</script>", page)
            self.assertIn("&lt;script&gt;unsafe&lt;/script&gt;", page)
            self.assertNotIn("baseline", page)
            self.assertTrue((Path(directory) / "solution_review_schema.json").exists())
            self.assertTrue((Path(directory) / "blind_reviews.csv").exists())
            self.assertTrue((Path(directory) / "private_method_key.json").exists())

    def test_imported_ai_rating_is_distinct_from_human_and_validates_hash_quotes(self):
        packet, key = build_review_bundle([response()])
        proposal = {"id": "q1", "method": "baseline", "output_sha256": packet["items"][0]["output_sha256"],
                    "criteria": {name: {"rating": "appropriate", "evidence": "2+2=4", "reason": "등식을 확인했습니다."} for name in CRITERIA}}
        result = import_ai_suggestions(packet, key, [proposal])
        self.assertEqual(result["accepted"], 1)
        self.assertEqual(result["rejected"], [])
        self.assertEqual(overall_rating(packet["items"][0]), "unreviewed")
        summary = summarize_reviews(packet, key)
        self.assertEqual(summary["review_kinds"]["human"]["baseline"]["overall"]["reviewed_count"], 0)
        self.assertEqual(summary["review_kinds"]["ai_suggestion"]["baseline"]["overall"]["appropriate"], 1)
        bad_hash = deepcopy(proposal)
        bad_hash["output_sha256"] = "wrong"
        self.assertEqual(len(import_ai_suggestions(packet, key, [bad_hash])["rejected"]), 1)
        bad_quote = deepcopy(proposal)
        bad_quote["criteria"]["logical_validity"]["evidence"] = "존재하지 않는 인용"
        self.assertEqual(len(import_ai_suggestions(packet, key, [bad_quote])["rejected"]), 1)
        with tempfile.TemporaryDirectory() as directory:
            export_review_files(packet, key, Path(directory))
            self.assertNotIn("ai_suggestion", (Path(directory) / "blind_review.html").read_text().split("<script type=")[0])
            self.assertTrue((Path(directory) / "ai_suggested_reviews.csv").exists())

    def test_math_appropriateness_keeps_curriculum_uncertainty_separate(self):
        packet, key = build_review_bundle([response()])
        item = packet["items"][0]
        reviewed(item)
        item["rubric"]["curriculum_scope"] = {"rating": "uncertain", "evidence_quotes": [], "explanation": "공식 수업 범위가 제공되지 않았습니다."}
        self.assertEqual(mathematical_appropriateness(item), "appropriate")
        self.assertEqual(overall_rating(item), "uncertain")
        summary = summarize_reviews(packet, key)["review_kinds"]["human"]["baseline"]
        self.assertEqual(summary["mathematical_appropriateness"]["appropriate"], 1)
        self.assertEqual(summary["mathematical_appropriateness"]["reviewed_coverage"], 1)
        self.assertEqual(summary["overall"]["uncertain"], 1)


if __name__ == "__main__":
    unittest.main()
