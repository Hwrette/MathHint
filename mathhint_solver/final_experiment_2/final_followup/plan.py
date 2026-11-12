"""저장된 실제 SDK 요청을 동결하고 186개 신규 반복 신원을 만든다."""

from copy import deepcopy
import csv
from pathlib import Path

from ... import CompareGeneration as comparison
from ...AnswerEvaluation import extract_reference
from .common import (ROOT, OUTPUT, METHODS, read_json, read_jsonl, write_json,
    append_jsonl, source_output, request_id, request_key)

CONTROL_IDS = ("trig_1_040", "trig_1_044", "diff_2_039", "diff_2_004", "trig_1_043")
ERROR_IDS = ("diff_2_039", "diff_3_045", "trig_1_040", "trig_1_044", "trig_1_047",
             "trig_2_020", "trig_3_008", "trig_3_033", "trig_3_036", "trig_2_022", "trig_3_034")
TARGET_IDS = tuple(dict.fromkeys(CONTROL_IDS + ERROR_IDS))
REPEATS = (1, 2, 3)
MODEL = "gemini-3.1-flash-lite"
NEUTRAL_TITLE = "해설에 등장한 토큰과 빈도: 상위20개"
E_INSTRUCTION = "풀이를 작성해줘."
SETTING_FIELDS = ("model", "temperature", "thinking_level", "max_output_tokens", "system_instruction")


def _csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _source_data(root):
    old = source_output(root)
    wrapped = read_json(old / "config.json")
    config = wrapped["config"]
    if wrapped["config_id"] != comparison.digest(config):
        raise ValueError("과거 전체265 설정 해시가 다릅니다.")
    if (config["model"] != MODEL or config["temperature"] != 0.0
            or str(config["thinking_level"]).lower() != "minimal" or config["max_output_tokens"] != 8192
            or config["system_instruction"] != comparison.DEFAULT_SYSTEM):
        raise ValueError("확정 Gemini 설정과 다릅니다. 다른 설정으로 변경하지 않습니다.")
    source_rows = read_jsonl(old / "plan.jsonl")
    rows = {(r["id"], r["condition"]): r for r in source_rows}
    if len(rows) != len(source_rows) or len(rows) != 1060:
        raise ValueError("과거1060개 계획이 손상되었습니다.")
    corrected = _csv(old / "key_corrected/question_comparison.csv")
    error_union = {r["id"] for r in corrected if any(r[f"{c}_correct_verified"] == "False" for c in "ABCD")}
    if error_union != set(ERROR_IDS):
        raise ValueError("정정된 실제 오답 관련 문항이 승인된11문항과 다릅니다: " + str(sorted(error_union)))
    if len(corrected) != 265 or len({r["id"] for r in corrected}) != 265:
        raise ValueError("과거 정정표의265문항이 손상되었습니다.")
    return old, config, rows, {r["id"]: r for r in corrected}


def prepare_plan(root=ROOT):
    root = Path(root).resolve()
    old, source_config, source_rows, corrected = _source_data(root)
    sources = {str((old / name).relative_to(root)): comparison.file_hash(old / name)
               for name in ("config.json", "plan.jsonl", "responses.jsonl",
                            "key_corrected/question_comparison.csv", "key_corrected/summary.csv",
                            "error_analysis_11/error_cases.json", "error_analysis_11/README.md")}
    frozen = {}
    templates = {}
    for identifier in TARGET_IDS:
        conditions = "ABCDEF" if identifier in CONTROL_IDS else "ABCD"
        for condition in conditions:
            parent_condition = condition if condition in "ABCD" else "A" if condition == "E" else "D"
            previous = deepcopy(source_rows[identifier, parent_condition])
            audit_path = old / f"prompt_audit/requests/{identifier}/{parent_condition}.json"
            audit = read_json(audit_path)
            source_snapshot = audit["sdk_request"]
            if (comparison.digest(source_snapshot) != previous["request_sha256"]
                    or audit["request_sha256"] != previous["request_sha256"]
                    or source_snapshot["contents"] != previous["input_text"]
                    or audit["problem_text"] != previous["problem_text"]
                    or previous["input_sha256"] != comparison.digest(previous["input_text"])):
                raise ValueError(f"과거 실제 요청 감사가 손상되었습니다: {identifier}/{parent_condition}")
            text = previous["input_text"]
            if condition == "E":
                if text != previous["problem_text"] or previous["hint"] is not None:
                    raise ValueError("기존A가 문제만인 조건이 아닙니다.")
                text += "\n\n" + E_INSTRUCTION
            elif condition == "F":
                suffix = text[len(previous["problem_text"]):]
                lines = suffix.splitlines(keepends=True)
                titles = [line.rstrip("\r\n") for line in lines if line.startswith("[") and line.rstrip().endswith("]")]
                if len(titles) != 1 or "정답 해설에서 계산한 실제" not in titles[0]:
                    raise ValueError("D의 원본 출처 제목을 하나로 식별할 수 없습니다.")
                replacement = "[" + NEUTRAL_TITLE + "]"
                text = previous["problem_text"] + suffix.replace(titles[0], replacement, 1)
                if text.replace(replacement, titles[0], 1) != previous["input_text"]:
                    raise ValueError("F에서 출처 제목 외의 요청이 변경되었습니다.")
            snapshot = comparison.request_snapshot(comparison.sdk_request_arguments(source_config, text))
            if condition in "ABCD" and snapshot != source_snapshot:
                raise ValueError("A/B/C/D 신규 반복 요청이 과거와 다릅니다.")
            reference_answer = corrected[identifier]["answer_for_scoring"]
            item = {**previous, "condition": condition, "method": METHODS[condition],
                "original_reference": previous["reference"],
                "original_reference_answer_text": previous["reference_answer_text"],
                "reference_answer_text": reference_answer,
                "reference": extract_reference({"answer_text": reference_answer}, previous["problem_text"]),
                "grading_key_status": corrected[identifier]["key_status"],
                "input_text": text, "input_sha256": comparison.digest(text),
                "request_sha256": comparison.digest(snapshot), "sdk_request_sha256": comparison.digest(snapshot),
                "frozen_prompt_path": f"frozen_prompts/{identifier}/{condition}.json",
                "memberships": (["control_top5"] if identifier in CONTROL_IDS else [])
                               + (["error_repeat_11"] if identifier in ERROR_IDS and condition in "ABCD" else []),
                "source_condition": parent_condition, "source_request_sha256": previous["request_sha256"],
                "source_prompt_audit": str(audit_path.relative_to(root)),
                "source_prompt_audit_sha256": comparison.file_hash(audit_path),
                "uses_test_reference_vector": condition in "DF" and previous["split"] == "test",
                "compact_storage": True}
            frozen[identifier, condition] = {"id": identifier, "condition": condition,
                "repeat_numbers": list(REPEATS), "requested_model": source_config["model"],
                "system_instruction": item["system_instruction"], "problem_text": item["problem_text"],
                "user_message": text, "hint": item["hint"], "sdk_request": snapshot,
                "full_request_text": "[SYSTEM]\n" + item["system_instruction"] + "\n[USER]\n" + text,
                "input_sha256": item["input_sha256"], "request_sha256": item["request_sha256"],
                "sdk_request_sha256": item["request_sha256"], "source_condition": parent_condition,
                "source_prompt_audit": item["source_prompt_audit"],
                "source_prompt_audit_sha256": item["source_prompt_audit_sha256"],
                "source_request_sha256": previous["request_sha256"],
                "models": source_config["models"], "dataset_id": source_config["dataset_id"],
                "solution_vocabulary_sha256": source_config["solution_vocabulary_sha256"],
                "data_identity_sha256": source_config["data_identity_sha256"],
                "transformation": "original SDK request unchanged" if condition in "ABCD" else
                    "A plus only the specified instruction" if condition == "E" else "D source title replaced; exact JSON and remaining structure unchanged"}
            templates[identifier, condition] = item
    plan = []
    for repeat in REPEATS:
        offset = 4 * (repeat - 1) % len(TARGET_IDS)
        identifiers = TARGET_IDS[offset:] + TARGET_IDS[:offset]
        for identifier in identifiers:
            index = TARGET_IDS.index(identifier)
            arms = "ABCDEF" if identifier in CONTROL_IDS else "ABCD"
            shift = (index + 2 * (repeat - 1)) % len(arms)
            order = arms[shift:] + arms[:shift]
            for position, condition in enumerate(order, 1):
                plan.append({**deepcopy(templates[identifier, condition]), "repeat": repeat,
                    "request_id": request_id(identifier, condition, repeat), "condition_order_in_block": order,
                    "condition_position_in_block": position, "schedule_position": len(plan) + 1})
    if len(plan) != 186 or len({request_key(row) for row in plan}) != 186:
        raise ValueError("고유 신규 반복 요청186개가 아닙니다.")
    config = {"schema_version": 1,
        **{name: source_config[name] for name in SETTING_FIELDS},
        "experiment_id": "final_followup_three_repeats", "split": "mixed_selected",
        "generation_id": "final_followup_three_repeats", "repeats": list(REPEATS),
        "control_ids": list(CONTROL_IDS), "error_ids": list(ERROR_IDS), "target_ids": list(TARGET_IDS),
        "control_conditions": list("ABCDEF"), "error_conditions": list("ABCD"),
        "conditions": METHODS, "methods": list(METHODS.values()), "expected_requests": 186,
        "logical_control_requests": 90, "logical_error_requests": 132, "shared_requests": 36,
        "max_attempts": source_config["max_attempts"], "compact_storage": True,
        "models": source_config["models"], "dataset_id": source_config["dataset_id"],
        "solution_vocabulary_sha256": source_config["solution_vocabulary_sha256"],
        "data_identity_sha256": source_config["data_identity_sha256"], "sources_sha256": sources,
        "source_experiment": str(old.relative_to(root)),
        "error_id_validation": {"verified_false_union_equals_requested_11": True, "count": len(ERROR_IDS)},
        "execution_order": "three repeat rounds; question order rotated by4 per round; condition Latin cyclic rotations by question index+2*(repeat-1); no whole-condition grouping",
        "E_instruction": E_INSTRUCTION, "F_neutral_title": NEUTRAL_TITLE,
        "cache_policy": "Only a successful request with the same(id,condition,repeat) and exact frozen SDK hash is skipped. Historical responses never count as new repetitions.",
        "grading": "use saved corrected reference answer; raw parser abstentions stay unknown pending new-response-specific evidenced review",
        "training_scope_note": "Selected13 includes model train185 and independent test80 IDs; B/C train predictions are in-sample. Selected11 are postselected old failures.",
        "study_status": "exploratory three-repeat results only; not project-final closure or causal identification",
        "inputs": [{key: row[key] for key in ("id", "condition", "repeat", "request_id", "request_sha256", "schedule_position")} for row in plan]}
    return config, plan, frozen


def initialize(output, config, plan, frozen):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    config_id = comparison.initialize_run(output, config, plan)
    path = output / "plan.jsonl"
    if path.exists():
        if read_jsonl(path) != plan:
            raise ValueError("동결된 반복 계획이 변경되었습니다.")
    else:
        for row in plan:
            append_jsonl(path, row)
    for (identifier, condition), record in frozen.items():
        path = output / f"frozen_prompts/{identifier}/{condition}.json"
        if path.exists():
            if read_json(path) != record:
                raise ValueError("동결된 실제 프롬프트가 변경되었습니다.")
        else:
            write_json(path, record)
    return config_id
