"""조건별 전체 그룹 우선 실행은 요청 의미·기존 성공 응답을 바꾸지 않는다."""

from copy import deepcopy
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mathhint_solver import CompareGeneration as comparison
from mathhint_solver.final_experiment_2.gemini_full265 import common, run
from mathhint_solver.final_experiment_2.gemini_full265 import __main__ as cli


def requests():
    return [{"id": identifier, "condition": condition, "method": common.METHODS[condition],
             "split": "train", "request_sha256": identifier + condition, "compact_storage": True}
            for identifier in ("z", "a") for condition in "ABCD"]


class NoNetworkLimiter:
    def __init__(self, policy, **kwargs):
        self.policy, self.new_starts = policy, 0
        self.stop_status = self.stop_reason = None
        self.daily_exhausted = False
    def snapshot(self):
        return {"policy": self.policy}


class Full265PriorityTests(unittest.TestCase):
    def test_order_is_a_strict_permutation_and_group_order_is_stable_without_plan_mutation(self):
        rows = requests(); before = deepcopy(rows)
        ordered = run.execution_plan(rows, "ABDC")
        self.assertEqual([(row["condition"], row["id"]) for row in ordered],
            [(condition, identifier) for condition in "ABDC" for identifier in ("z", "a")])
        self.assertEqual(rows, before)
        self.assertEqual(comparison.digest(rows), comparison.digest(before))
        self.assertEqual(run.execution_plan(rows), rows)
        for invalid in ("ABD", "ABDD", "ABDCE", "abdc", " AB DC ", None):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                common.validate_condition_order(invalid)

    def test_policy_and_state_remember_priority_without_changing_config_or_request_hashes(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            common.write_json(output / "policy.json", {**common.DEFAULT_POLICY, "condition_order": "ABDC"})
            self.assertEqual(run._load_policy(output)["condition_order"], "ABDC")
            with self.assertRaises(ValueError):
                run._load_policy(output, {"condition_order": "ABDD"})
            config, rows = {"frozen_model": "original"}, requests()
            before = deepcopy((config, rows))
            state = run.state_record(output, config, rows, status="partial_complete")
            self.assertEqual(state["condition_order"], "ABDC")
            self.assertEqual(state["pending_by_condition"], dict.fromkeys("ABCD", 2))
            self.assertEqual([row["condition"] for row in state["pending_requests"]], list("AABBDDCC"))
            self.assertIn("--condition-order ABDC", state["resume_command"])
            self.assertEqual((config, rows), before)

    def test_cli_passes_explicit_priority_and_rejects_invalid_value_before_generate(self):
        from mathhint_solver.final_experiment_2.gemini_full265 import report
        result = {"status": "partial_complete", "successful_requests": 515, "expected_requests": 1060, "pending_count": 545}
        with patch.object(run, "generate", return_value=result) as generate, patch.object(report, "run"), \
                patch("sys.argv", ["full265", "generate", "--condition-order", "ABDC"]), patch("sys.stdout", io.StringIO()):
            cli.main()
        self.assertEqual(generate.call_args.kwargs["policy"]["condition_order"], "ABDC")
        with patch.object(run, "generate") as generate, patch("sys.stderr", io.StringIO()), \
                patch("sys.argv", ["full265", "generate", "--condition-order", "ABDD"]):
            with self.assertRaises(SystemExit):
                cli.main()
            generate.assert_not_called()

    def test_mocked_generation_skips_saved_success_and_exhausts_each_condition_group_first(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); output = common.safe_output(root)
            config, rows = {"frozen": "config"}, requests()
            config_id = comparison.digest(config)
            common.write_json(output / "config.json", {"config": config, "config_id": config_id})
            old_events = common.source_output(root) / "execution_runs/request_events.jsonl"
            old_events.parent.mkdir(parents=True); old_events.write_text("")
            for item in rows:
                common.write_json(output / f"prompt_audit/requests/{item['id']}/{item['condition']}.json", {"sdk_request": {"frozen": True}})
            saved = {**rows[0], "config_id": config_id, "status": "success", "output_text": "original"}
            common.append_jsonl(output / "responses.jsonl", saved)
            before_requests = {path: path.read_bytes() for path in (output / "prompt_audit").rglob("*.json")}
            preparation = {"state": {"successful_requests": 1, "pending_requests": rows[1:]}}
            calls = []
            def fake_generate(item, config, config_id, key, **kwargs):
                calls.append((item["condition"], item["id"]))
                return {**item, "config_id": config_id, "status": "success", "output_text": "mocked"}
            with patch.object(run, "prepare", return_value=(config, rows, preparation, output, {})), \
                    patch.object(run, "BudgetRateLimiter", NoNetworkLimiter), \
                    patch.object(comparison, "generate_one", side_effect=fake_generate), patch("sys.stdout", io.StringIO()):
                state = run.generate(root, output, policy={"condition_order": "ABDC"}, request_function=lambda text: None, api_key="fake")
            self.assertEqual(calls, [("A", "a"), ("B", "z"), ("B", "a"), ("D", "z"), ("D", "a"), ("C", "z"), ("C", "a")])
            self.assertEqual(common.read_jsonl(output / "responses.jsonl")[0], saved)
            self.assertEqual(state["condition_order"], "ABDC")
            self.assertEqual(state["pending_by_condition"], dict.fromkeys("ABCD", 0))
            execution = next(path for path in (output / "execution_runs").glob("*.json"))
            self.assertEqual(common.read_json(execution)["condition_order"], "ABDC")
            self.assertEqual(before_requests, {path: path.read_bytes() for path in before_requests})
            self.assertEqual(comparison.digest(config), config_id)


if __name__ == "__main__":
    unittest.main()
