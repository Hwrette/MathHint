"""186개 반복키·프롬프트 대조·표본통계·원본 보존의 핵심 회귀 검사."""

import csv
import hashlib
import math
from pathlib import Path
import tempfile
import unittest

from mathhint_solver.final_experiment_2.final_followup.verify import (
    CONTROL_IDS, ERROR_IDS, OLD_HEADER, NEUTRAL_HEADER, USAGE_FIELDS,
    _scored_grade, _summary_checks, expected_message, plan_checks,
    preservation_result, token_statistics,
)


def fixture_plan():
    targets = list(dict.fromkeys(CONTROL_IDS + ERROR_IDS))
    plan = []
    for repeat in range(1, 4):
        for identifier in targets:
            for condition in ("ABCDEF" if identifier in CONTROL_IDS else "ABCD"):
                plan.append({"id": identifier, "condition": condition, "repeat": repeat,
                             "request_id": f"{identifier}__{condition}__r{repeat}",
                             "request_sha256": identifier + condition})
    config = {"control_ids": list(CONTROL_IDS), "error_ids": list(ERROR_IDS), "target_ids": targets}
    return config, plan


class FollowupValidationTests(unittest.TestCase):
    def test_repeated_identical_prompt_is186_distinct_calls(self):
        config, plan = fixture_plan()
        self.assertEqual(len({r["request_sha256"] for r in plan}), 62)
        self.assertTrue(all(row["passed"] for row in plan_checks(config, plan)))
        collapsed = list({r["request_sha256"]: r for r in plan}.values())
        self.assertFalse(all(row["passed"] for row in plan_checks(config, collapsed)))

    def test_extra_or_duplicate_repeat_is_rejected(self):
        config, plan = fixture_plan()
        broken = [dict(r) for r in plan]
        broken[-1]["repeat"] = 2
        self.assertFalse(all(row["passed"] for row in plan_checks(config, broken)))

    def test_E_only_appends_instruction_and_F_only_changes_source_heading(self):
        a = {"sdk_request": {"contents": "원문\\frac{1}{2}\n"}}
        d = {"sdk_request": {"contents": "문제\n\n" + OLD_HEADER + '\n{"latex:\\\\sin":2.0}\n위 주요 토큰을 참고하여 풀이를 작성해줘.'}}
        self.assertEqual(expected_message("E", a, a, d), "원문\\frac{1}{2}\n\n\n풀이를 작성해줘.")
        f = expected_message("F", d, a, d)
        self.assertEqual(f.replace(NEUTRAL_HEADER, OLD_HEADER), d["sdk_request"]["contents"])
        self.assertEqual(expected_message("D", d), d["sdk_request"]["contents"])
        with self.assertRaises(ValueError):
            expected_message("F", d, a, a)

    def test_sample_std_and_missing_usage(self):
        stats = token_statistics([10, None, 30])
        self.assertEqual(stats["provided_count"], 2)
        self.assertEqual(stats["sum"], 40)
        self.assertEqual(stats["mean"], 20)
        self.assertAlmostEqual(stats["std"], math.sqrt(200))
        self.assertIsNone(token_statistics([None])["mean"])
        self.assertIsNone(token_statistics([5])["std"])
        self.assertEqual(token_statistics([0, None])["provided_count"], 1)
        self.assertEqual(token_statistics([0, None])["mean"], 0)

    def test_parser_abstention_is_not_automatically_wrong(self):
        row = {"evaluation": {"correct": None}}
        self.assertIsNone(_scored_grade(row, {}))
        self.assertIsNone(_scored_grade(row, {"math_status": "inappropriate"}))
        self.assertIs(_scored_grade(row, {"final_answer_correct": False}), False)

    def test_preservation_hash_rejects_changed_original(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.txt"
            source.write_bytes(b"original")
            manifest = {"files_sha256": {"source.txt": hashlib.sha256(b"original").hexdigest()}}
            self.assertTrue(preservation_result(root, manifest)["passed"])
            source.write_bytes(b"changed")
            self.assertFalse(preservation_result(root, manifest)["passed"])

    def test_independent_report_check_detects_population_std(self):
        _, plan = fixture_plan()
        records, reviews = [], {}
        for item in plan:
            repeat = item["repeat"]
            row = {**item, "status": "success", "evaluation": {"correct": repeat < 3},
                   "usage": {field: None if field == "thoughts_token_count" else repeat for field in USAGE_FIELDS}}
            records.append(row)
            reviews[item["id"], item["condition"], repeat] = {"math_status": ("appropriate", "uncertain", "inappropriate")[repeat - 1]}
        summaries = {}
        for folder, identifiers, conditions in (("control_top5", CONTROL_IDS, "ABCDEF"), ("error_repeat_11", ERROR_IDS, "ABCD")):
            rows = []
            for identifier in identifiers:
                for condition in conditions:
                    row = {"id": identifier, "condition": condition, "expected_count": 3, "success_count": 3,
                           "graded_count": 3, "correct_count": 2, "incorrect_count": 1, "ungradable_count": 0,
                           "pending_count": 0, "failed_count": 0, "math_appropriate_count": 1,
                           "math_inappropriate_count": 1, "math_uncertain_count": 1, "reviewed_math_count": 2}
                    for field in USAGE_FIELDS:
                        values = ({"provided_count": 0, "sum": None, "mean": None, "min": None, "max": None, "std": None}
                                  if field == "thoughts_token_count" else
                                  {"provided_count": 3, "sum": 6, "mean": 2, "min": 1, "max": 3, "std": 1})
                        row.update({field + "_" + key: value for key, value in values.items()})
                    rows.append(row)
            summaries[folder] = rows
        paired = [{"id": identifier, "repeat": repeat, "pair": pair,
                   **{field + "_difference": None if field == "thoughts_token_count" else 0 for field in USAGE_FIELDS}}
                  for identifier in CONTROL_IDS for repeat in range(1, 4) for pair in ("E-A", "B-A", "C-A", "D-A", "F-D")]
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            def write(path, rows):
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("w", encoding="utf-8-sig", newline="") as stream:
                    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
                    writer.writeheader(); writer.writerows(rows)
            for folder, rows in summaries.items():
                write(output / folder / "summary.csv", rows)
            write(output / "control_top5/paired_differences.csv", paired)
            self.assertTrue(all(row["passed"] for row in _summary_checks(output, plan, records, reviews)))
            summaries["control_top5"][0]["candidates_token_count_std"] = math.sqrt(2 / 3)
            write(output / "control_top5/summary.csv", summaries["control_top5"])
            failures = [row for row in _summary_checks(output, plan, records, reviews) if not row["passed"]]
            self.assertEqual(len(failures), 1)
            self.assertIn("candidates_token_count_std", failures[0]["check"])


if __name__ == "__main__":
    unittest.main()
