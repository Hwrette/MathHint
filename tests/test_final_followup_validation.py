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
    preservation_result, token_statistics, case_findings_checks, transport_consistency_checks,
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
    def test_transport_timeouts_bind_per_execution_without_rewriting_old_attempts(self):
        runs = [{"execution_id": name, "policy": {"http_timeout_ms": timeout},
                 "transport": {"http_timeout_ms": timeout, "sdk_attempts": 1}}
                for name, timeout in (("old180s", 180000), ("new300s", 300000))]
        captures, responses = [], []
        for run in runs:
            row = {"id": "q", "condition": "A", "repeat": 1,
                   "execution_id": run["execution_id"], "transport": dict(run["transport"])}
            captures.append(dict(row))
            responses.append({**row, "status": "api_error" if run["execution_id"] == "old180s" else "success",
                              "sdk_boundary_captured_attempts": 1, "sdk_boundary_capture_expected": True})
        self.assertTrue(all(check["passed"] for check in transport_consistency_checks(runs, captures, responses)))
        # 새 대기 한도를 과거 SDK 시도에 소급하면 그 시도만의 증거 불일치를 잡는다.
        captures[0]["transport"] = dict(runs[1]["transport"])
        failures = [check for check in transport_consistency_checks(runs, captures, responses) if not check["passed"]]
        self.assertEqual(len(failures), 1)
        self.assertIn("capture_transport_matches", failures[0]["check"])

    def test_final186_requires11_fresh_hash_bound_AD_BC_analyses(self):
        _, plan = fixture_plan()
        records = [{**row, "status": "success", "output_text": row["request_id"] + " 실제 새 풀이"} for row in plan]
        received = {(row["id"], row["condition"], row["repeat"]): row for row in records}
        findings = {identifier: {
            "AD": "A와 D의 세 번 새 풀이를 실제 오류 단계와 자기수정 여부로 비교했다.",
            "BC": "B와 C의 세 번 새 풀이와 예측 토큰의 차이를 비교했다.",
            "human_confirmed": False,
            "response_sha256s": {f"{identifier}__{condition}__r{repeat}": hashlib.sha256(
                received[identifier, condition, repeat]["output_text"].encode()).hexdigest()
                for condition in "ABCD" for repeat in (1, 2, 3)}} for identifier in ERROR_IDS}
        self.assertTrue(all(check["passed"] for check in case_findings_checks(findings, records, require_complete=True)))
        subset = {ERROR_IDS[0]: findings[ERROR_IDS[0]]}
        self.assertTrue(all(check["passed"] for check in case_findings_checks(subset, records, require_complete=False)))
        self.assertFalse(all(check["passed"] for check in case_findings_checks(subset, records, require_complete=True)))
        self.assertFalse(all(check["passed"] for check in case_findings_checks({}, records, require_complete=True)))
        # 새 응답 한 개라도 달라지면 이전 종합문을 그대로 재사용할 수 없다.
        received[ERROR_IDS[0], "A", 1]["output_text"] += " 변경됨"
        failures = [check for check in case_findings_checks(findings, records, require_complete=True) if not check["passed"]]
        self.assertEqual(len(failures), 1)
        self.assertIn("12_new_response_hashes", failures[0]["check"])

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
        self.assertIsNone(_scored_grade({"status": "truncated_response", "evaluation": {"correct": None}},
                                       {"final_answer_correct": False}))

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
                           "received_count": 3, "completed_count": 3, "api_response_count": 3,
                           "incomplete_count": 0, "truncated_count": 0, "blocked_count": 0, "empty_count": 0,
                           "graded_count": 3, "correct_count": 2, "incorrect_count": 1, "ungradable_count": 0,
                           "pending_count": 0, "failed_count": 0, "math_appropriate_count": 1,
                           "math_inappropriate_count": 1, "math_uncertain_count": 1, "reviewed_math_count": 2,
                           "correct_but_math_inappropriate_count": 0, "prior_error_recurred_count": 0,
                           "prior_error_assessed_count": 0, "self_corrected_count": 0, "self_correction_assessed_count": 0}
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
            summaries["control_top5"][0]["candidates_token_count_std"] = 1
            # MAX_TOKENS도 고정된 3회 시행 중 하나다. 8192를 버려 평균을 줄이거나
            # 정상 STOP만의 토큰 평균을 전체 평균이라고 표시하면 독립 검증이 실패한다.
            target = next(row for row in records if row["id"] == CONTROL_IDS[0]
                          and row["condition"] == "F" and row["repeat"] == 1)
            target["status"] = "truncated_response"
            target["evaluation"]["correct"] = None
            target["usage"]["candidates_token_count"] = 8192
            reviews[CONTROL_IDS[0], "F", 1]["math_status"] = "uncertain"
            cell = next(row for row in summaries["control_top5"] if row["id"] == CONTROL_IDS[0] and row["condition"] == "F")
            cell.update(success_count=2, graded_count=2, correct_count=1, ungradable_count=1,
                        incomplete_count=1, truncated_count=1, math_appropriate_count=0,
                        math_uncertain_count=2, reviewed_math_count=1)
            vals = (8192, 2, 3)
            avg = sum(vals) / 3
            cell.update(candidates_token_count_sum=sum(vals), candidates_token_count_mean=avg,
                        candidates_token_count_min=2, candidates_token_count_max=8192,
                        candidates_token_count_std=math.sqrt(sum((x - avg) ** 2 for x in vals) / 2))
            pair = next(row for row in paired if row["id"] == CONTROL_IDS[0] and row["repeat"] == 1 and row["pair"] == "F-D")
            pair["candidates_token_count_difference"] = 8191
            write(output / "control_top5/summary.csv", summaries["control_top5"])
            write(output / "control_top5/paired_differences.csv", paired)
            self.assertTrue(all(row["passed"] for row in _summary_checks(output, plan, records, reviews)))


if __name__ == "__main__":
    unittest.main()
