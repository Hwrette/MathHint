"""전체265 확장: 원본80 재사용·공유 제한·새 경로·중단/재개의 비용 없는 검증."""

from datetime import datetime, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import socket
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from mathhint_solver import CompareGeneration as comparison
from mathhint_solver.AnswerEvaluation import extract_reference
from mathhint_solver.final_experiment_2.gemini_comparison.budget import BudgetRateLimiter
from mathhint_solver.final_experiment_2.gemini_comparison.plan import SETTINGS, initialize
from mathhint_solver.final_experiment_2.gemini_full265 import common, plan, run
from mathhint_solver.final_experiment_2.gemini_full265 import __main__ as cli


class Clock:
    def __init__(self):
        self.value = 0.0
    def monotonic(self):
        return self.value
    def wall(self):
        return 100000 + self.value
    def sleep(self, delay):
        self.value += delay


def question(config, identifier="q", condition="A", split="test"):
    text = "문제 선택지 ① 1 ② 2"
    snapshot = comparison.request_snapshot(comparison.sdk_request_arguments(config, text))
    return {"id": identifier, "condition": condition, "method": common.METHODS[condition], "split": split,
            "problem_text": text, "input_text": text, "input_sha256": comparison.digest(text),
            "system_instruction": config["system_instruction"], "reference_solution": "원본 풀이",
            "reference_answer_text": "①", "reference": extract_reference({"answer_text": "①"}, text),
            "hint": None, "request_sha256": comparison.digest(snapshot), "compact_storage": True}, snapshot


class Full265ExecutionTests(unittest.TestCase):
    def test_cli_prepare_report_verify_refuse_an_active_generation_lock_before_work(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); output = common.safe_output(root)
            with common.execution_lock(root, output):
                for action, module_name, function_name in (("prepare", "run", "prepare"),
                        ("report", "report", "run"), ("verify", "verify", "run")):
                    module = importlib.import_module("mathhint_solver.final_experiment_2.gemini_full265." + module_name)
                    with self.subTest(action=action), patch.object(cli, "ROOT", root), patch.object(cli, "OUTPUT", output), \
                            patch("sys.argv", ["full265", action]), patch.object(module, function_name) as function:
                        with self.assertRaises(RuntimeError):
                            cli.main()
                        function.assert_not_called()
            self.assertFalse((output / ".execution.lock").exists())

    def test_default_saved_reader_uses_new_scope_and_preservation_rejects_old_changes(self):
        with patch.object(common, "_load_saved", return_value="new") as reader:
            self.assertEqual(common.load_saved(), "new")
            reader.assert_called_once_with(common.OUTPUT)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); output = common.safe_output(root)
            source = root / "protected.txt"; source.write_text("original")
            common.write_json(output / "preservation_manifest.json", {"source_commit": "old",
                "files_sha256": {"protected.txt": hashlib.sha256(source.read_bytes()).hexdigest()}})
            self.assertEqual(common.verify_preservation(root, output)["checked_files"], 1)
            source.write_text("changed")
            with self.assertRaises(ValueError):
                common.verify_preservation(root, output)

    def test_only_new_output_is_writable_and_explicit_user_authorization_is_not_provider_confirmation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.assertEqual(common.safe_output(root), root / "results/final_experiment_2/gemini_full265")
            with self.assertRaises(ValueError):
                common.safe_output(root, root / "results/final_experiment_2/gemini_comparison")
            policy = run._load_policy(common.safe_output(root))
            self.assertFalse(policy["provider_limits_confirmed"])
            self.assertEqual((policy["rpd"], policy["user_authorized_additional_requests"]), (1400, 740))
            with self.assertRaises(ValueError):
                run._load_policy(common.safe_output(root), {"provider_limits_confirmed": True})

    def test_combined_plan_keeps_exact_split_requests_and_real_185_80_membership(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            old = common.source_output(root)
            for name in ("config.json", "responses.jsonl", "review/curated_reviews.json"):
                path = old / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text("source")
            ids = {"train": [f"r{i}" for i in range(185)], "test": [f"t{i}" for i in range(80)]}
            def split_plan(root, data, *, split):
                rows = [{"id": i, "condition": c, "split": split, "request_sha256": i+c} for i in ids[split] for c in "ABCD"]
                return {"models": {}, "dataset_id": "d", "solution_vocabulary_sha256": "v", "data_identity_sha256": "d"}, rows
            with patch.object(plan, "split_plan", side_effect=split_plan):
                config, rows = plan.prepare_plan(root, {"ids": ids})
            self.assertEqual(config["split"], "all")
            self.assertEqual(config["test_ids"], ids["test"])
            self.assertEqual(config["train_ids"], ids["train"])
            self.assertEqual(config["target_ids"], ids["test"]+ids["train"])
            self.assertEqual(len(rows), 1060)
            self.assertEqual(rows[0]["request_sha256"], "t0A")
            self.assertEqual(rows[320]["split"], "train")

    def test_exact_source_response_and_math_review_are_reused_once_without_mutating_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); old = common.source_output(root); output = common.safe_output(root)
            config = {**SETTINGS, "max_attempts": 2, "compact_storage": True, "split": "all", "conditions": common.METHODS}
            old_config = {**config, "split": "test"}
            item, sdk = question(config)
            common.write_json(old / "config.json", {"config_id": comparison.digest(old_config), "config": old_config})
            audit = old / "prompt_audit/requests/q/A.json"
            common.write_json(audit, {"sdk_request": sdk, "request_sha256": item["request_sha256"]})
            response = {**item, "config_id": comparison.digest(old_config), "status": "success", "output_text": "최종정답: ①",
                "usage": comparison.usage_record(None), "raw_response": {"original": True}, "evaluation": {"correct": True},
                "started_at": "old-time", "completed_at": "old-completion", "attempts": [{"original": True}],
                "response_id": "original", "source_provenance": {"older": True}}
            common.append_jsonl(old / "responses.jsonl", response)
            review = {"id": "q", "condition": "A", "response_sha256": hashlib.sha256(response["output_text"].encode()).hexdigest(),
                      "evidence_quotes": ["최종정답"], "human_confirmed": False}
            common.write_json(old / "review/curated_reviews.json", {"records": [review]})
            before = {str(p.relative_to(old)): p.read_bytes() for p in old.rglob("*") if p.is_file()}
            initialize(output, config, [item])
            self.assertEqual(plan.reuse_existing(root, output, config, [item])["imported"], 1)
            self.assertEqual(plan.reuse_existing(root, output, config, [item])["imported"], 0)
            saved = common.read_jsonl(output / "responses.jsonl")
            self.assertEqual(len(saved), 1)
            for field in ("output_text", "raw_response", "usage", "evaluation", "started_at", "completed_at", "response_id", "attempts"):
                self.assertEqual(saved[0][field], response[field])
            self.assertIsNone(saved[0]["usage"]["thoughts_token_count"])
            self.assertEqual(saved[0]["source_provenance"]["prior_provenance"], {"older": True})
            self.assertEqual(common.read_json(output / "review/curated_reviews.json")["records"], [review])
            self.assertEqual(before, {str(p.relative_to(old)): p.read_bytes() for p in old.rglob("*") if p.is_file()})

    def test_old_and_new_rate_history_are_deduplicated_and_jointly_limit_requests(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); output = common.safe_output(root); clock = Clock()
            for i in range(6):
                event = {"event": "request_start", "time": datetime.fromtimestamp(clock.wall()-1+i/10, timezone.utc).isoformat(), "execution_id": str(i)}
                path = (common.source_output(root) if i < 5 else output) / "execution_runs/request_events.jsonl"
                common.append_jsonl(path, event)
                if i == 0:
                    common.append_jsonl(output / "execution_runs/request_events.jsonl", event)
            events = common.all_request_events(root, output)
            self.assertEqual(len(events), 6)
            limiter = BudgetRateLimiter(common.DEFAULT_POLICY, events=events, clock=clock.monotonic,
                wall_clock=clock.wall, sleeper=clock.sleep)
            limiter.acquire()
            self.assertGreaterEqual(clock.value, 59)

    def test_live_old_execution_is_rejected_without_touching_old_lock(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); output = common.safe_output(root); old = common.source_output(root) / ".execution.lock"
            common.write_json(old, {"pid": os.getpid(), "host": socket.gethostname()})
            before = old.read_bytes()
            with self.assertRaises(RuntimeError), common.execution_lock(root, output):
                pass
            self.assertEqual(old.read_bytes(), before)
            self.assertFalse((output / ".execution.lock").exists())

    def test_pending_cannot_be_completed_and_counts_keep_train_and_test_separate(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            config = {"split": "all"}
            rows = [dict(id=i, condition="A", method="baseline", split=s, request_sha256=i) for i, s in (("a", "test"), ("b", "train"))]
            state = run.state_record(output, config, rows, status="completed")
            self.assertEqual(state["status"], "partial_complete")
            self.assertEqual(state["by_split"]["train"]["pending_requests"], 1)
            self.assertIn("gemini_full265 generate", state["resume_command"])
            self.assertNotIn("training_extension", state)

    def test_generate_resumes_only_missing_request_without_network_or_model_training(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); output = common.safe_output(root)
            config = {**SETTINGS, "max_attempts": 2, "compact_storage": True, "split": "all"}
            item, sdk = question(config, split="train")
            initialize(output, config, [item])
            common.write_json(output / "prompt_audit/requests/q/A.json", {"sdk_request": sdk})
            old_events = common.source_output(root) / "execution_runs/request_events.jsonl"
            old_events.parent.mkdir(parents=True, exist_ok=True); old_events.write_text("")
            preparation = {"state": {"successful_requests": 0, "pending_requests": [item]}}
            def prepared(*_, **__):
                return config, [item], preparation, output, {}
            calls = []
            def request(_):
                calls.append(True)
                return SimpleNamespace(text="최종정답: ①", candidates=[], usage_metadata=None,
                    model_version="fake", response_id="q", prompt_feedback=None)
            with patch.object(run, "prepare", side_effect=prepared):
                first = run.generate(root, output, request_function=request, api_key="fake")
                second = run.generate(root, output, request_function=request, api_key="fake")
            self.assertEqual(len(calls), 1)
            self.assertEqual(first["status"], "completed")
            self.assertEqual(second["successful_requests"], 1)
            self.assertEqual(old_events.read_bytes(), b"")
            self.assertFalse((output / ".execution.lock").exists())


if __name__ == "__main__":
    unittest.main()
