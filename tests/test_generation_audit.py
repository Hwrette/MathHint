"""실호출 없이 요청·응답 해시와 실패→성공 이력을 검증한다."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from mathhint_solver import CompareGeneration as comparison
from mathhint_solver.GenerationAudit import audit_generation, CONDITIONS


class GenerationAuditTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.project = Path(self.temporary.name)
        self.output = self.project / "result"
        problem = "$\\frac{1}{2}$의 값은? ①1/2 ②2"
        source = self.project / "data/processed/problems/q.txt"
        source.parent.mkdir(parents=True)
        source.write_text(problem)
        self.config = {"model": "fixture_model", "system_instruction": "풀이와 최종정답", "temperature": 0.,
            "max_output_tokens": 100, "thinking_level": "minimal", "test_ids": ["q"], "methods": list(CONDITIONS),
            "inputs": [{"id": "q", **{method:comparison.digest(problem if method == "baseline" else problem + method) for method in CONDITIONS}}]}
        config_id = comparison.digest(self.config)
        comparison.write_json(self.output / "config.json", {"config": self.config, "config_id": config_id})
        usage = {"prompt_token_count": 10, "candidates_token_count": 20, "thoughts_token_count": None, "total_token_count": 30}
        self.rows = []
        for method, condition in CONDITIONS.items():
            text = problem if method == "baseline" else problem + method
            payload = {"model": "fixture_model", "contents": text, "config": {
                "system_instruction": "풀이와 최종정답", "temperature": 0., "max_output_tokens": 100,
                "thinking_config": {"thinking_level": "MINIMAL"}}}
            request = {"id": "q", "method": method, "condition": condition, "sdk_request": payload,
                "sdk_request_sha256": comparison.digest(payload), "user_message": text, "problem_text": problem,
                "input_sha256": comparison.digest(text), "hint": None if method == "baseline" else {
                    "source": "actual_reference" if method == "oracle_hint" else "regression_prediction"}}
            comparison.write_json(self.output / f"prompt_audit/requests/q/{condition}.json", request)
            row = {"id": "q", "method": method, "config_id": config_id, "input_text": text, "problem_text": problem,
                "input_sha256": comparison.digest(text), "system_instruction": "풀이와 최종정답", "model": "fixture_model",
                "model_version": "fixture_model", "raw_response": {"model_version": "fixture_model"},
                "uses_test_reference_vector": method == "oracle_hint", "evaluation": {"correct": True},
                "status": "success", "response_origin": "new_api_call" if method == "oracle_hint" else "reused_exact_request",
                "usage": {**usage, "raw": usage}, "attempts": [{"attempt": 1, "status": "success", "usage": usage}],
                "rate_limited_execution_id": "new", "sdk_boundary_captured_attempts": 1,
                "sdk_request_sha256": request["sdk_request_sha256"]}
            self.rows.append(row)
            if method == "oracle_hint":
                self.capture = {"id": "q", "condition": "C", "method": method, "request": payload,
                    "request_sha256": request["sdk_request_sha256"], "execution_id": "new",
                    "capture": "immediately_before_sdk_generate_content"}
                comparison.write_json(self.output / "prompt_audit/sdk_calls/q_C_new_1.json", self.capture)
        source_records = self.project / "original_responses.jsonl"
        source_records.write_text("\n".join(json.dumps(row) for row in self.rows) + "\n")
        for row in self.rows:
            if row["response_origin"].startswith("reused"):
                row["provenance"] = {"source_records": str(source_records),
                    "source_records_sha256": comparison.file_hash(source_records),
                    "source_record_sha256": comparison.digest(row)}
        self.save()

    def tearDown(self):
        self.temporary.cleanup()

    def save(self):
        (self.output / "responses.jsonl").write_text("\n".join(json.dumps(row) for row in self.rows) + "\n")

    def audit(self):
        return audit_generation(self.output, project=self.project, write_output=False)

    def test_matching_requests_usage_and_sdk_capture_pass(self):
        report = self.audit()
        self.assertTrue(report["verification_passed"], report["violations"])
        self.assertTrue(report["all_expected_successful"])
        self.assertEqual(report["reused_successful_responses"], 2)
        self.assertEqual(report["sdk_boundary_call_count"], 1)
        self.assertEqual(report["raw_usage_fields_compared"], 3)

    def test_sdk_contents_tampering_is_a_verification_failure(self):
        tampered = deepcopy(self.capture)
        tampered["request"]["contents"] += "changed"
        comparison.write_json(self.output / "prompt_audit/sdk_calls/q_C_new_1.json", tampered)
        self.assertFalse(self.audit()["verification_passed"])

    def test_failed_then_successful_retry_preserves_unknown_usage_and_is_not_duplicate_success(self):
        failure = deepcopy(self.rows[-1])
        failure.update(status="api_error", evaluation={"correct": None}, rate_limited_execution_id="old",
            attempts=[{"attempt": 1, "execution": 1, "status": "error", "error_type": "ReadTimeout",
                       "usage": {"total_token_count": None}}])
        old_capture = {**self.capture, "execution_id": "old"}
        comparison.write_json(self.output / "prompt_audit/sdk_calls/q_C_old_1.json", old_capture)
        final = self.rows[-1]
        final["attempts"] = failure["attempts"] + [{**final["attempts"][0], "execution": 2}]
        self.rows.insert(-1, failure)
        self.save()
        report = self.audit()
        self.assertTrue(report["verification_passed"], report["violations"])
        self.assertEqual(report["historical_record_count"], 4)
        self.assertEqual(report["sdk_boundary_call_count"], 2)
        self.assertEqual(len(report["unknown_usage_attempts"]), 1)

    def test_original_response_is_found_in_relocated_clone_and_still_hash_checked(self):
        relocated_source = self.project / "results/original_responses.jsonl"
        relocated_source.parent.mkdir()
        relocated_source.write_bytes((self.project / "original_responses.jsonl").read_bytes())
        self.config["predictions_source"] = "/unavailable/old_clone/results/predictions.json"
        config_id = comparison.digest(self.config)
        comparison.write_json(self.output / "config.json", {"config": self.config, "config_id": config_id})
        for row in self.rows:
            row["config_id"] = config_id
            if row["response_origin"].startswith("reused"):
                row["provenance"]["source_records"] = "/unavailable/old_clone/results/original_responses.jsonl"
        self.save()
        report = self.audit()
        self.assertTrue(report["verification_passed"], report["violations"])
        relocated_source.write_text("[]\n")
        self.assertFalse(self.audit()["verification_passed"])

    def test_two_successful_results_for_one_condition_are_flagged(self):
        self.rows.append(deepcopy(self.rows[-1])); self.save()
        self.assertFalse(self.audit()["verification_passed"])


if __name__ == "__main__":
    unittest.main()
