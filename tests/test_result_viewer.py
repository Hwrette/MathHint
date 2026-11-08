"""정적 읽기 화면이 원문을 바꾸거나 HTML/인증정보를 실행·노출하지 않게 한다."""

import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mathhint_analysis import ResultViewer as viewer


class HtmlDocument(HTMLParser):
    def __init__(self):
        super().__init__()
        self.script_attributes = []
        self.tags = []
        self.json_text = []
        self.in_data = False

    def handle_starttag(self, tag, attributes):
        attributes = dict(attributes)
        self.tags.append(tag)
        if tag == "script":
            self.script_attributes.append(attributes)
            self.in_data = attributes.get("id") == "viewer-data"

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_data = False

    def handle_data(self, text):
        if self.in_data:
            self.json_text.append(text)


class ResultViewerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.data = self.root / "selected_data"
        self.run = self.root / "results/chosen_experiment"
        self.output = self.run / "03_gemini/report.html"
        self.problem = "문제 $\\frac{1}{x_1}$\n① $1$ ② $2$\n"
        self.solution = "[정답] ②\n[해설]\n$\\lim_{x \\to 0} x=0$"
        self.identifiers = {"train": ["training"], "test": ["question"]}
        self.save(self.data / "processed/metadata.json", {
            "generation_id": "selected-generation",
            "records": [{"id": i, "curriculum": "과목", "unit": "단원", "subunit": "세부", "type": "유형", "answer_text": "②"}
                        for i in ("training", "question")],
        })
        for split, ids in self.identifiers.items():
            self.save(self.data / f"processed/splits/{split}.json", ids)
            for i in ids:
                self.text(self.data / f"processed/problems/{i}.txt", self.problem)
                self.text(self.data / f"processed/solutions/{i}.txt", self.solution)
        self.config = {"config_id": "selected-config", "config": {
            "generation_id": "selected-generation", "train_ids": ["training"], "test_ids": ["question"],
            "model": "test-model", "temperature": 0, "api_key": "must-not-appear-in-html",
        }}
        self.record = {"id": "question", "method": "baseline", "status": "success",
                       "problem_text": self.problem, "input_text": self.problem,
                       "system_instruction": "원래 지시", "output_text": "최종정답: ②",
                       "config_id": "selected-config", "input_sha256": "original-input-sha",
                       "evaluation": {"predicted_answer": "②", "correct": True},
                       "usage": {"total_token_count": 20, "thoughts_token_count": None},
                       "provenance": {"source_config_id": "old-config", "api_key": "must-not-appear-in-html"}}
        self.assets = self.root / "source_assets"
        for name in ("viewer.js", "viewer.css", "vendor/katex.min.js", "vendor/katex.min.css", "vendor/markdown-it.min.js"):
            self.text(self.assets / name, "/* local test asset */")
        assets_patch = patch.object(viewer, "ASSETS", self.assets)
        assets_patch.start()
        self.addCleanup(assets_patch.stop)

    def save(self, path, value):
        self.text(path, json.dumps(value, ensure_ascii=False))

    def text(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8")

    def payload(self, records=None, config=None):
        return viewer.build_payload(self.root, self.run, self.output, data_root=self.data,
                                    records=[self.record] if records is None else records,
                                    config=self.config if config is None else config)

    def test_inline_json_cannot_close_script_and_original_text_survives_round_trip(self):
        attack = '</script><script>window.injected=1</script><img src="x" onerror="window.injected=2">'
        self.record["output_text"] = attack + "\n$\\frac{a_1}{b^2}$\n```html\n<script>code</script>\n```"
        source_files = list(self.data.rglob("*.txt"))
        before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files}
        viewer.build_viewer(self.root, self.run, data_root=self.data, records=[self.record], config=self.config)
        document = self.output.read_text()
        parsed = HtmlDocument()
        parsed.feed(document)
        payload = json.loads("".join(parsed.json_text))
        output = payload["questions"][1]["conditions"]["baseline"]["output_text"]
        self.assertEqual(output, self.record["output_text"])
        self.assertEqual(len(parsed.script_attributes), 4)
        self.assertNotIn("img", parsed.tags)
        self.assertNotIn("must-not-appear-in-html", document)
        self.assertEqual(before, {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files})
        self.assertTrue((self.run / "viewer_assets/viewer.js").exists())
        self.assertIn("../viewer_assets/viewer.js", document)
        self.assertIn("connect-src 'none'", document)

    def test_train_not_in_generation_and_api_failures_ungraded_and_missing_are_distinct(self):
        failure = {**self.record, "method": "regression_hint", "status": "api_error",
                   "output_text": None, "evaluation": {"correct": None}, "usage": {"total_token_count": None}}
        ungraded = {**self.record, "evaluation": {"correct": None, "predicted_answer": None}}
        payload = self.payload(records=[failure, ungraded])
        train, test = payload["questions"]
        self.assertFalse(train["expected_generation"])
        self.assertTrue(all(row is None for row in train["conditions"].values()))
        self.assertTrue(test["expected_generation"])
        self.assertEqual(test["conditions"]["regression_hint"]["status"], "api_error")
        self.assertIsNone(test["conditions"]["regression_hint"]["usage"]["total_token_count"])
        self.assertIsNone(test["conditions"]["baseline"]["evaluation"]["correct"])
        self.assertIsNone(test["conditions"]["oracle_hint"])
        self.assertFalse(test["changed_correctness"])

    def test_failed_attempt_then_success_is_allowed_but_duplicate_success_is_rejected(self):
        failed = {**self.record, "status": "api_error", "output_text": None}
        self.assertEqual(self.payload(records=[failed, self.record])["questions"][1]["conditions"]["baseline"]["status"], "success")
        with self.assertRaisesRegex(ValueError, "중복"):
            self.payload(records=[self.record, self.record])

    def test_explicit_data_root_is_used_without_falling_back_to_project_data(self):
        self.assertEqual(self.payload()["generation_id"], "selected-generation")
        with self.assertRaises(FileNotFoundError):
            viewer.build_payload(self.root, self.run, self.output, data_root=self.root / "missing", records=[], config={})
        wrong = {**self.config, "config": {**self.config["config"], "test_ids": ["different"]}}
        with self.assertRaisesRegex(ValueError, "test_ids"):
            self.payload(config=wrong)
        wrong = {**self.config, "config": {**self.config["config"], "generation_id": "other"}}
        with self.assertRaisesRegex(ValueError, "식별"):
            self.payload(config=wrong)
        original_directory = Path.cwd()
        try:
            os.chdir(self.root.parent)
            output = viewer.build_viewer(self.root, "results/chosen_experiment", data_root="selected_data",
                                         records=[self.record], config=self.config)
            self.assertEqual(output, self.output)
            self.assertTrue(output.exists())
        finally:
            os.chdir(original_directory)

    def test_review_links_are_bound_to_exact_response_and_quotes(self):
        path = self.run / "03_gemini/solution_review.json"
        review = {"id": "question", "method": "baseline", "math_status": "inappropriate",
                  "human_confirmed": False, "quote": "최종정답", "reason": "중간 오류",
                  "response_sha256": hashlib.sha256(self.record["output_text"].encode()).hexdigest()}
        self.save(path, {"records": [review]})
        saved = self.payload()["questions"][1]["conditions"]["baseline"]["review"]
        self.assertEqual(saved["math_status"], "inappropriate")
        self.assertFalse(saved["human_confirmed"])
        review["quote"] = "실제 응답에 없는 인용"
        self.save(path, {"records": [review]})
        with self.assertRaisesRegex(ValueError, "인용"):
            self.payload()
        review["quote"] = "최종정답"
        review["response_sha256"] = "not-the-output"
        self.save(path, {"records": [review]})
        with self.assertRaisesRegex(ValueError, "해시"):
            self.payload()

    def test_same_generation_with_changed_metadata_hash_is_rejected(self):
        path = self.data / "processed/metadata.json"
        config = {**self.config, "config": {**self.config["config"],
                  "metadata_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}}
        self.payload(config=config)
        metadata = json.loads(path.read_text())
        metadata["records"][0]["unit"] = "다른 분류"
        self.save(path, metadata)
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            self.payload(config=config)

    def test_new_run_does_not_consult_an_unselected_legacy_review_archive(self):
        latest = {("question", "baseline"): {**self.record, "response_origin": "new_api_call"}}
        with patch.object(viewer, "_read", side_effect=AssertionError("Unselected archive read")):
            self.assertEqual(viewer._legacy_reviews(self.root, latest, self.output), {})

    def test_wrong_response_problem_and_config_are_not_silently_mixed(self):
        self.record["problem_text"] += "다른 문제"
        with self.assertRaisesRegex(ValueError, "문제 원문"):
            self.payload()
        self.record["problem_text"] = self.problem
        self.record["config_id"] = "different-experiment"
        with self.assertRaisesRegex(ValueError, "설정 ID"):
            self.payload()


if __name__ == "__main__":
    unittest.main()
