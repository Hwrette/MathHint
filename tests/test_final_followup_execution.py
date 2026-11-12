"""반복 신원·새 프롬프트·안전한 재개를 실제 API 없이 검사한다."""

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from mathhint_solver import CompareGeneration as comparison
from mathhint_solver.AnswerEvaluation import extract_reference
from mathhint_solver.final_experiment_2.gemini_comparison.budget import BudgetRateLimiter
from mathhint_solver.final_experiment_2.gemini_comparison.plan import SETTINGS
from mathhint_solver.final_experiment_2.final_followup import common, plan, run


class Clock:
    def __init__(self):
        self.value = 0.
    def monotonic(self):
        return self.value
    def wall(self):
        return 1_800_000_000 + self.value
    def sleep(self, value):
        self.value += value


def fake_preparation(root, repeats=3):
    output = common.safe_output(root)
    config = {**SETTINGS, "experiment_id": "synthetic-followup", "max_attempts": 1, "compact_storage": True}
    text = "1+0의 값은?"
    snapshot = comparison.request_snapshot(comparison.sdk_request_arguments(config, text))
    rows = [{"id": "q", "condition": "A", "method": "baseline", "repeat": repeat,
        "request_id": common.request_id("q", "A", repeat), "schedule_position": repeat,
        "split": "test", "frozen_prompt_path": "frozen_prompts/q/A.json",
        "problem_text": text, "input_text": text, "input_sha256": comparison.digest(text),
        "request_sha256": comparison.digest(snapshot), "sdk_request_sha256": comparison.digest(snapshot),
        "reference_solution": "원본 해설", "reference_answer_text": "1",
        "reference": extract_reference({"answer_text": "1"}, text), "hint": None,
        "system_instruction": config["system_instruction"], "compact_storage": True} for repeat in range(1, repeats + 1)]
    comparison.initialize_run(output, config, rows)
    common.write_json(output / "frozen_prompts/q/A.json", {"sdk_request": snapshot})
    policy = {**common.DEFAULT_POLICY, "max_new_requests": 1}
    def prepare(*_, **__):
        state = run.state_record(output, config, rows, status="partial_complete")
        return config, rows, {"state": state}, output, policy
    return output, config, rows, prepare


class FinalFollowupExecutionTests(unittest.TestCase):
    def test_saved_actual_sdk_identity_and_deduplicated_study_membership(self):
        config, rows, frozen = plan.prepare_plan()
        self.assertEqual(len(rows), 186)
        self.assertEqual(len(frozen), 62)
        self.assertEqual(len({common.request_key(r) for r in rows}), 186)
        self.assertEqual(sum("control_top5" in r["memberships"] for r in rows), 90)
        self.assertEqual(sum("error_repeat_11" in r["memberships"] for r in rows), 132)
        self.assertEqual(sum(len(r["memberships"]) == 2 for r in rows), 36)
        self.assertEqual(config["max_attempts"], 2)
        for identifier in plan.CONTROL_IDS:
            for condition in "ABCD":
                audit = common.read_json(common.source_output() / f"prompt_audit/requests/{identifier}/{condition}.json")
                self.assertEqual(frozen[identifier, condition]["sdk_request"], audit["sdk_request"])
            a = frozen[identifier, "A"]
            e = frozen[identifier, "E"]
            d = frozen[identifier, "D"]
            f = frozen[identifier, "F"]
            self.assertEqual(e["user_message"], a["user_message"] + "\n\n" + plan.E_INSTRUCTION)
            self.assertIsNone(e["hint"])
            self.assertEqual(f["hint"], d["hint"])
            before = d["user_message"].split("\n")
            after = f["user_message"].split("\n")
            differences = [(x, y) for x, y in zip(before, after) if x != y]
            self.assertEqual(len(before), len(after))
            self.assertEqual(len(differences), 1)
            self.assertEqual(differences[0][1], "[" + plan.NEUTRAL_TITLE + "]")

    def test_rounds_interleave_conditions_and_each_control_position_is_balanced(self):
        _, rows, _ = plan.prepare_plan()
        from collections import Counter
        for repeat in plan.REPEATS:
            selected = [r for r in rows if r["repeat"] == repeat]
            self.assertEqual(len(selected), 62)
            self.assertEqual(set(r["condition"] for r in selected), set("ABCDEF"))
        for condition in "ABCDEF":
            positions = Counter(r["condition_position_in_block"] for r in rows
                                if r["condition"] == condition and "control_top5" in r["memberships"])
            self.assertEqual(set(positions), set(range(1, 7)))
            self.assertLessEqual(max(positions.values()) - min(positions.values()), 1)

    def test_same_prompt_three_repeats_make_three_calls_and_resume_skips_only_successful_repeat(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output, config, rows, preparation = fake_preparation(root)
            clock = Clock()
            def limiter(policy, **kwargs):
                return BudgetRateLimiter(policy, **kwargs, clock=clock.monotonic,
                                         wall_clock=clock.wall, sleeper=clock.sleep)
            calls = []
            def request(text):
                calls.append(text)
                return SimpleNamespace(text="최종정답: 1")
            with patch.object(run, "prepare", side_effect=preparation), patch.object(run, "BudgetRateLimiter", side_effect=limiter):
                first = run.generate(root, output, request_function=request, api_key="fake")
                self.assertEqual(first["successful_requests"], 1)
                self.assertEqual([r["repeat"] for r in first["pending_requests"]], [2, 3])
                second = run.generate(root, output, request_function=request, api_key="fake",
                                      policy={"max_new_requests": 5})
                self.assertEqual(second["status"], "completed")
                third = run.generate(root, output, request_function=request, api_key="fake")
                self.assertEqual(third["successful_requests"], 3)
            self.assertEqual(len(calls), 3)
            self.assertEqual(len(set(calls)), 1)
            saved = common.read_jsonl(output / "responses.jsonl")
            self.assertEqual([r["repeat"] for r in saved], [1, 2, 3])
            self.assertEqual(len({r["request_sha256"] for r in saved}), 1)
            self.assertEqual({r["response_origin"] for r in saved}, {"new_api_call"})

    def test_tampered_success_cannot_be_reused_and_duplicate_success_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            output, config, rows, _ = fake_preparation(Path(temporary), repeats=1)
            saved = {**rows[0], "config_id": comparison.digest(config), "status": "success", "input_text": "tampered"}
            common.append_jsonl(output / "responses.jsonl", saved)
            with self.assertRaises(ValueError):
                run.state_record(output, config, rows, status="partial_complete")
            common.append_jsonl(output / "responses.jsonl", saved)
            with self.assertRaises(ValueError):
                common.load_latest(output, comparison.digest(config))

    def test_policy_and_paths_keep_prior_experiments_read_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = common.safe_output(root)
            with self.assertRaises(ValueError):
                common.safe_output(root, common.source_output(root))
            with self.assertRaises(ValueError):
                run._load_policy(output, {"interval_seconds": 5})
            with self.assertRaises(ValueError):
                run._load_policy(output, {"provider_limits_confirmed": True})
            common.append_jsonl(root / "results/final_experiment_2/gemini_comparison/execution_runs/request_events.jsonl", {"event": "request_start", "time": "2026-01-01T00:00:00+00:00"})
            common.append_jsonl(common.source_output(root) / "execution_runs/request_events.jsonl", {"event": "request_start", "time": "2026-01-01T00:01:00+00:00"})
            common.append_jsonl(output / "execution_runs/request_events.jsonl", {"event": "request_start", "time": "2026-01-01T00:02:00+00:00"})
            self.assertEqual(len(common.all_request_events(root, output)), 3)
            with common.execution_lock(root, output):
                with self.assertRaises(RuntimeError):
                    with common.execution_lock(root, output):
                        self.fail("duplicate lock entered")

    def test_preservation_guard_refuses_prior_file_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = common.safe_output(root)
            prior = root / "prior.txt"
            prior.write_text("immutable")
            common.write_json(output / "preservation_manifest.json", {"source_commit": "test",
                "files_sha256": {"prior.txt": comparison.file_hash(prior)}})
            self.assertTrue(common.verify_preservation(root, output)["passed"])
            prior.write_text("changed")
            with self.assertRaises(ValueError):
                common.verify_preservation(root, output)


if __name__ == "__main__":
    unittest.main()
