"""고정 테스트 문항의 Gemini 풀이를 기본/회귀 벡터 조건으로 짝지어 비교한다.

실제 정답과 원본 해설은 평가·열람에만 사용하고 API 입력에는 넣지 않는다.
--prepare-only로 입력을 검토한 뒤 같은 폴더에서 --limit 1, 전체 순으로
실행할 수 있다. 성공한 응답은 재요청하지 않으며 설정/입력 변경 시 중단한다.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import os
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .AnswerEvaluation import evaluate_answer, extract_reference


DEFAULT_SYSTEM = (
    "이 문제 풀어줘. 마지막 줄에 최종정답: ... 형식으로 정답을 적어줘. "
    "객관식은 선택지 번호(①~⑤)를 적어줘."
)
METHODS = ("baseline", "regression_hint")
USAGE_FIELDS = (
    "prompt_token_count", "candidates_token_count", "thoughts_token_count",
    "cached_content_token_count", "total_token_count", "tool_use_prompt_token_count",
)


class RequestedStop(RuntimeError):
    """사용자가 요청한 중단 파일 때문에 새 API 요청을 전송하지 않는다."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _dump(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool, list, dict)):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude_none=False)
    return str(value)


def usage_record(usage: Any) -> dict:
    """미제공 사용량은0이 아닌null로, SDK의 추가 필드도 함께 보관한다."""
    data = _dump(usage)
    return {**{field: data.get(field) if isinstance(data, dict)
               else getattr(usage, field, None) for field in USAGE_FIELDS},
            "raw": data}


def serialize_hint(vocabulary: list[str], vector: list[float], *, mode: str = "top_tokens",
                   top_k: int = 20) -> tuple[str, dict]:
    if not vocabulary or len(set(vocabulary)) != len(vocabulary) or len(vocabulary) != len(vector):
        raise ValueError("예측 벡터와 중복 없는 어휘의 길이가 같아야 합니다.")
    if mode not in ("top_tokens", "full_vector") or isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
        raise ValueError("hint mode는 top_tokens/full_vector, top_k는 양수여야 합니다.")
    clipped = []
    for value in vector:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("회귀 예측은 유한한 실수여야 합니다.")
        clipped.append(max(0.0, float(value)))
    indices = [index for index, value in enumerate(clipped) if value > 0]
    if mode == "top_tokens":
        indices = sorted(indices, key=lambda index: (-clipped[index], index))[:top_k]
    mapping = {vocabulary[index]: round(clipped[index], 3) for index in indices if round(clipped[index], 3) > 0}
    payload = json.dumps(mapping, ensure_ascii=False, separators=(",", ":"))
    text = (f"\n\n[학습 데이터로 학습한 선형회귀가 예측한 해설 주요 토큰: 예측 빈도순 상위{top_k}개]\n"
            + payload + "\n위 주요 토큰을 참고하여 풀이를 작성해줘." if mode == "top_tokens" else
            "\n\n[학습 데이터로 학습한 선형회귀가 예측한 해설 토큰 빈도]\n" + payload)
    return (text,
            {"transform": "clip_min_0_round_3_decimal_places_omit_zeros",
             "mode": mode, "top_k": top_k if mode == "top_tokens" else None,
             "selection": "descending_unrounded_positive_frequency_ties_vocabulary_order" if mode == "top_tokens" else "vocabulary_order",
             "vocabulary_size": len(vocabulary), "transmitted_coordinates": len(mapping),
             "mapping": mapping})


def load_predictions(path: Path, test_ids: list[str], generation_id: str) -> tuple[list[str], dict]:
    data = read_json(path)
    if data.get("generation_id") not in (None, generation_id):
        raise ValueError("회귀 예측의 데이터 generation_id가 다릅니다.")
    vocabulary = data.get("vocabulary", data.get("solution_vocabulary"))
    documents = data.get("documents", data.get("predictions"))
    if not isinstance(vocabulary, list) or not isinstance(documents, list):
        raise ValueError("예측 JSON에 vocabulary와 documents 배열이 필요합니다.")
    predictions = {}
    for document in documents:
        identifier = document.get("id")
        vector = document.get("predicted_vector", document.get("prediction"))
        if not isinstance(identifier, str) or identifier in predictions or not isinstance(vector, list):
            raise ValueError("예측 문항 ID가 중복되거나 예측 벡터가 없습니다.")
        serialize_hint(vocabulary, vector)
        predictions[identifier] = vector
    if set(predictions) != set(test_ids):
        raise ValueError("회귀 예측 ID 집합이 고정 테스트 ID 집합과 다릅니다.")
    return vocabulary, predictions


def prepare_plan(project: Path, predictions_path: Path, *, model: str,
                 thinking_level: str, temperature: float, max_output_tokens: int,
                 system_instruction: str = DEFAULT_SYSTEM, attempts: int = 2,
                 hint_mode: str = "top_tokens", hint_top_k: int = 20) -> tuple[dict, list[dict]]:
    metadata_path = project / "data/processed/metadata.json"
    metadata = read_json(metadata_path)
    train_path = project / "data/processed/splits/train.json"
    test_path = project / "data/processed/splits/test.json"
    train_ids, test_ids = read_json(train_path), read_json(test_path)
    if set(train_ids) & set(test_ids) or len(set(test_ids)) != len(test_ids):
        raise ValueError("학습·테스트 ID가 겹치거나 테스트 ID가 중복됩니다.")
    vocabulary, predictions = load_predictions(predictions_path, test_ids, metadata["generation_id"])
    prediction_metadata = read_json(predictions_path)
    if "train_ids" in prediction_metadata and prediction_metadata["train_ids"] != train_ids:
        raise ValueError("회귀 학습 ID가 고정 학습 ID/순서와 다릅니다.")
    records = {record["id"]: record for record in metadata["records"]}
    plan, input_hashes = [], []
    for index, identifier in enumerate(test_ids):
        meta = records[identifier]
        problem = (project / "data/processed/problems" / (identifier + ".txt")).read_text(encoding="utf-8-sig")
        solution = (project / "data/processed/solutions" / (identifier + ".txt")).read_text(encoding="utf-8-sig")
        reference = extract_reference(meta, problem)
        hint, hint_audit = serialize_hint(vocabulary, predictions[identifier], mode=hint_mode, top_k=hint_top_k)
        pair = []
        for method in METHODS:
            text = problem if method == "baseline" else problem + hint
            entry = {"id": identifier, "method": method, "input_text": text,
                     "system_instruction": system_instruction, "input_sha256": digest(text),
                     "reference": reference, "reference_answer_text": meta.get("answer_text"),
                     "reference_solution": solution, "problem_text": problem,
                     "subject": meta.get("subject"), "unit": meta.get("unit"),
                     "type": meta.get("type"), "source": meta.get("source"),
                     "hint": hint_audit if method == "regression_hint" else None}
            pair.append(entry)
        # 조건의 시간 순서가 항상 같지 않도록 문항마다 요청 순서를 바꾼다.
        plan.extend(pair if index % 2 == 0 else list(reversed(pair)))
        input_hashes.append({"id": identifier, "problem_sha256": digest(problem),
                             "reference_sha256": digest([reference, solution]),
                             "baseline_sha256": pair[0]["input_sha256"],
                             "regression_hint_sha256": pair[1]["input_sha256"]})
    config = {"schema_version": 1, "model": model, "thinking_level": thinking_level,
              "temperature": temperature, "max_output_tokens": max_output_tokens,
              "system_instruction": system_instruction, "max_attempts": attempts,
              "generation_id": metadata["generation_id"], "train_ids": train_ids,
              "test_ids": test_ids, "metadata_sha256": file_hash(metadata_path),
              "predictions_sha256": file_hash(predictions_path),
              "hint_mode": hint_mode, "hint_top_k": hint_top_k,
              "hint_transform": "positive_clip_select_unrounded_desc_tie_vocab_round_3_omit_zeros" if hint_mode == "top_tokens" else "all_coordinates_clip_min_0_round_3_omit_zeros",
              "condition_order": "alternate_by_test_id_position", "inputs": input_hashes,
              "grading": "deterministic_final_answer_only_not_solution_quality",
              "runner_sha256": file_hash(Path(__file__)),
              "grader_sha256": file_hash(Path(__file__).with_name("AnswerEvaluation.py"))}
    return config, plan


def initialize_run(output: Path, config: dict, plan: list[dict]) -> str:
    output.mkdir(parents=True, exist_ok=True)
    config_id = digest(config)
    path = output / "config.json"
    if path.exists():
        existing = read_json(path)
        if existing.get("config_id") != config_id or existing.get("config") != config:
            raise ValueError("기존 실행의 설정 또는 입력이 달라졌습니다. 새 출력 폴더를 사용하세요.")
    else:
        if (output / "responses.jsonl").exists():
            raise ValueError("설정 없이 기존 응답 파일이 있습니다. 덮어쓰지 않습니다.")
        write_json(path, {"config_id": config_id, "created_at": utc_now(), "config": config})
    for item in plan:
        folder = output / "questions" / item["id"] / item["method"]
        folder.mkdir(parents=True, exist_ok=True)
        for filename, text in (("input.txt", item["input_text"]),
                               ("system.txt", item["system_instruction"]),
                               ("reference_solution.txt", item["reference_solution"])):
            target = folder / filename
            if target.exists() and target.read_text(encoding="utf-8") != text:
                raise ValueError(f"입력/정답 파일이 기존 실행과 다릅니다: {target}")
            if not target.exists():
                target.write_text(text, encoding="utf-8")
        if item["hint"] is not None:
            write_json(folder / "hint.json", item["hint"])
    return config_id


def load_completed(output: Path, config_id: str) -> dict[tuple[str, str], dict]:
    records = {}
    path = output / "responses.jsonl"
    if not path.exists():
        return records
    lines = path.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"응답 로그 {index + 1}행이 잘렸습니다. 복구 후 다시 실행하세요.") from error
        if record.get("config_id") != config_id:
            raise ValueError("응답 로그의 config_id가 다릅니다.")
        records[(record["id"], record["method"])] = record
    return records


def import_baseline(source: Path, output: Path, config: dict, plan: list[dict]) -> dict:
    """입력·모델 설정이 같은 기존 성공 대조군을 출처와 실제 시각을 보존해 가져온다."""
    if source.resolve() == output.resolve():
        raise ValueError("대조군 원본과 새 실행 폴더는 달라야 합니다.")
    source_manifest = read_json(source / "config.json")
    source_config, source_id = source_manifest["config"], source_manifest["config_id"]
    if digest(source_config) != source_id:
        raise ValueError("기존 대조군 설정의 해시가 일치하지 않습니다.")
    for field in ("model", "thinking_level", "temperature", "max_output_tokens", "system_instruction",
                  "generation_id", "train_ids", "test_ids", "grader_sha256"):
        if source_config.get(field) != config.get(field):
            raise ValueError(f"기존 대조군의 설정이 다릅니다: {field}")
    config_id = initialize_run(output, config, plan)
    current, previous = load_completed(output, config_id), load_completed(source, source_id)
    candidates = []
    for item in plan:
        if item["method"] != "baseline":
            continue
        row = previous.get((item["id"], "baseline"))
        if row is None or row.get("status") != "success":
            continue
        for field in ("input_text", "input_sha256", "system_instruction", "reference", "reference_answer_text",
                      "reference_solution", "problem_text"):
            if row.get(field) != item.get(field):
                raise ValueError(f"기존 대조군의 문항 데이터가 다릅니다: {item['id']} / {field}")
        if (item["id"], "baseline") not in current or current[(item["id"], "baseline")]["status"] != "success":
            candidates.append(row)
    imported = []
    for row in candidates:
        reused = {**row, "config_id": config_id, "response_origin": "reused_control",
                  "provenance": {"source_directory": str(source.resolve()), "source_config_id": source_id,
                                 "source_record_sha256": digest(row), "imported_at": utc_now(),
                                 "reason": "Identical problem-only control reused across hint policies; no new API call."}}
        save_result(output, reused)
        imported.append(row["id"])
    report = {"source_directory": str(source.resolve()), "source_config_id": source_id,
              "destination_config_id": config_id, "imported_at": utc_now(), "imported_this_execution": imported,
              "total_reused_controls": sum(row.get("response_origin") == "reused_control"
                                           for row in load_completed(output, config_id).values())}
    write_json(output / "baseline_imports.json", report)
    return report


def response_record(response: Any) -> dict:
    candidates = getattr(response, "candidates", None) or []
    try:
        text = getattr(response, "text", None) or ""
    except (ValueError, AttributeError):
        text = ""
    return {"output_text": text, "usage": usage_record(getattr(response, "usage_metadata", None)),
            "model_version": getattr(response, "model_version", None),
            "response_id": getattr(response, "response_id", None),
            "finish_reasons": [str(getattr(candidate, "finish_reason", "")) for candidate in candidates],
            "prompt_feedback": _dump(getattr(response, "prompt_feedback", None)),
            "raw_response": _dump(response)}


def _error_code(error: Exception) -> int | None:
    value = getattr(error, "code", getattr(error, "status_code", None))
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def generate_one(item: dict, config: dict, config_id: str, api_key: str,
                 request_function=None) -> dict:
    """한 조건을 요청하며 실패한 시도도 경과 시간과 알려진 사용량을 남긴다."""
    if request_function is None:
        from google import genai
        from google.genai import types

        def request_function(text):
            with genai.Client(api_key=api_key, http_options=types.HttpOptions(
                timeout=90_000, retry_options=types.HttpRetryOptions(attempts=1))) as client:
                return client.models.generate_content(
                    model=config["model"], contents=text,
                    config=types.GenerateContentConfig(
                        system_instruction=config["system_instruction"],
                        temperature=config["temperature"],
                        max_output_tokens=config["max_output_tokens"],
                        thinking_config=types.ThinkingConfig(thinking_level=config["thinking_level"])))
    result = {**item, "config_id": config_id, "started_at": utc_now(),
              "response_origin": "new_api_call",
              "model": config["model"], "thinking_level": config["thinking_level"],
              "attempts": [], "status": "api_error", "output_text": "",
              "usage": usage_record(None), "model_version": None}
    started = time.monotonic()
    for index in range(config["max_attempts"]):
        attempt_started = time.monotonic()
        attempt = {"attempt": index + 1, "started_at": utc_now(), "usage": usage_record(None)}
        try:
            response = request_function(item["input_text"])
            parsed = response_record(response)
            attempt.update(status="success", usage=parsed["usage"], response_id=parsed["response_id"])
            result.update(parsed)
            result["status"] = "success" if parsed["output_text"].strip() else "empty_response"
            finish_names = [reason.rsplit(".", 1)[-1].upper() for reason in parsed["finish_reasons"]]
            if "MAX_TOKENS" in finish_names:
                result["status"] = "truncated_response"
            elif any(reason not in ("STOP", "FINISH_REASON_UNSPECIFIED", "", "NONE") for reason in finish_names):
                result["status"] = "blocked_or_incomplete_response"
            break
        except Exception as error:
            # API 키가 예외 표현에 포함된 경우에도 로그에 남기지 않는다.
            message = str(error)
            if api_key:
                message = message.replace(api_key, "[REDACTED]")
            if isinstance(error, RequestedStop):
                attempt.update(status="skipped", request_skipped=True, message=message)
                result["status"] = "stopped_before_request" if not result["attempts"] else "stopped_after_attempt"
                break
            code = _error_code(error)
            attempt.update(status="error", error_type=type(error).__name__, code=code, message=message)
            result["error"] = {"code": code, "type": type(error).__name__, "message": message}
            retryable = code in (408, 429, 500, 502, 503, 504) or isinstance(error, (TimeoutError, ConnectionError))
            if not retryable or index + 1 >= config["max_attempts"]:
                break
            time.sleep(min(2 ** index, 8))
        finally:
            attempt["latency_seconds"] = round(time.monotonic() - attempt_started, 3)
            result["attempts"].append(attempt)
    result["latency_seconds"] = round(time.monotonic() - started, 3)
    result["completed_at"] = utc_now()
    result["evaluation"] = (evaluate_answer(result["output_text"], item["reference"], item["problem_text"])
                            if result["status"] == "success" else {
                                "predicted_answer": None, "correct": None, "status": "ungradable",
                                "reason": result["status"], "extraction_method": None})
    return result


def save_result(output: Path, result: dict) -> None:
    # 먼저 추기/fsync하여 저장한다. 재개 시 성공한 API 요청은 다시 보내지 않는다.
    with (output / "responses.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    folder = output / "questions" / result["id"] / result["method"]
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "output.txt").write_text(result["output_text"], encoding="utf-8")
    write_json(folder / "record.json", result)


def summarize(records: list[dict], expected_ids: list[str]) -> dict:
    summary = {"expected_questions": len(expected_ids), "methods": {}, "paired": {}}
    for method in METHODS:
        rows = [row for row in records if row["method"] == method]
        successful = [row for row in rows if row["status"] == "success"]
        graded = [row for row in successful if row["evaluation"].get("correct") is not None]
        correct = sum(row["evaluation"].get("correct") is True for row in graded)
        usages = {}
        # 사용량이 누락된 시도는 별도 표시하고 알려진 합계를 전체로 오인하지 않는다.
        for field in USAGE_FIELDS:
            values = [attempt["usage"].get(field) for row in rows for attempt in row["attempts"]]
            known = [value for value in values if value is not None]
            successful_values = [row["usage"].get(field) for row in successful]
            known_successful = [value for value in successful_values if value is not None]
            usages[field] = {"known_attempt_sum": sum(known), "known_attempts": len(known),
                            "missing_attempts": len(values) - len(known),
                            "successful_response_mean": (sum(known_successful) / len(known_successful)
                                                         if known_successful else None),
                            "successful_response_count": len(known_successful)}
        summary["methods"][method] = {
            "recorded": len(rows), "successful": len(successful), "graded": len(graded),
            "correct": correct, "incorrect": len(graded) - correct,
            "ungradable_successes": len(successful) - len(graded),
            "reused_controls": sum(row.get("response_origin") == "reused_control" for row in rows),
            "api_errors_or_empty": len(rows) - len(successful),
            "missing_requests": len(expected_ids) - len(rows),
            "accuracy_on_graded": correct / len(graded) if graded else None,
            "correct_per_expected_question": correct / len(expected_ids) if expected_ids else None,
            "grading_coverage": len(graded) / len(expected_ids) if expected_ids else None,
            "usage": usages,
        }
    indexed = {(row["id"], row["method"]): row for row in records}
    pairs = [(indexed[(identifier, METHODS[0])], indexed[(identifier, METHODS[1])])
             for identifier in expected_ids if all((identifier, method) in indexed for method in METHODS)]
    valid = [(left, right) for left, right in pairs
             if left["evaluation"].get("correct") is not None and right["evaluation"].get("correct") is not None]
    summary["paired"] = {"recorded_pairs": len(pairs), "both_gradable": len(valid),
                         "both_correct": sum(a["evaluation"]["correct"] and b["evaluation"]["correct"] for a, b in valid),
                         "baseline_only_correct": sum(a["evaluation"]["correct"] and not b["evaluation"]["correct"] for a, b in valid),
                         "regression_only_correct": sum(not a["evaluation"]["correct"] and b["evaluation"]["correct"] for a, b in valid),
                         "both_incorrect": sum(not a["evaluation"]["correct"] and not b["evaluation"]["correct"] for a, b in valid)}
    return summary


def plot_comparison(output: Path, summary: dict) -> None:
    """정답률과 실제 API 사용량을 흑백 PNG/PDF로 저장한다."""
    if not any(value["recorded"] for value in summary["methods"].values()):
        return
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels = ["Problem only", "+ Predicted frequencies"]
    figure, axis = plt.subplots(figsize=(7.5, 4.5))
    scores = [summary["methods"][method]["accuracy_on_graded"] for method in METHODS]
    for index, score in enumerate(scores):
        if score is not None:
            axis.bar(index, score * 100, color="white" if index == 0 else "0.6", edgecolor="black", width=.55)
            details = summary["methods"][METHODS[index]]
            axis.text(index, score * 100 + 2, f"{details['correct']}/{details['graded']}", ha="center")
    axis.set(xticks=[0, 1], xticklabels=labels, ylabel="Correct final answers (% of gradable responses)", ylim=(0, 110))
    axis.spines[["top", "right"]].set_visible(False)
    figure.tight_layout()
    for suffix in ("png", "pdf"):
        figure.savefig(output / ("accuracy_comparison." + suffix), dpi=180)
    plt.close(figure)

    fields = ("prompt_token_count", "candidates_token_count", "thoughts_token_count", "total_token_count")
    figure, axis = plt.subplots(figsize=(9, 4.8))
    for method_index, method in enumerate(METHODS):
        values = [summary["methods"][method]["usage"][field]["successful_response_mean"] for field in fields]
        for index, value in enumerate(values):
            if value is not None:
                axis.bar(index + (method_index - .5) * .34, value, width=.32,
                         color="white" if method_index == 0 else "0.6", edgecolor="black",
                         label=labels[method_index] if index == 0 else None)
    axis.set(xticks=range(4), xticklabels=["Input", "Answer", "Thinking", "Total"],
             ylabel="Mean reported tokens per successful response")
    axis.spines[["top", "right"]].set_visible(False)
    axis.legend(frameon=False)
    figure.tight_layout()
    for suffix in ("png", "pdf"):
        figure.savefig(output / ("token_comparison." + suffix), dpi=180)
    plt.close(figure)


def render_reports(output: Path, records: list[dict], config: dict, *, charts: bool = True) -> dict:
    summary = summarize(records, config["test_ids"])
    write_json(output / "summary.json", summary)
    fields = ["id", "method", "response_origin", "started_at", "completed_at", "subject", "unit", "type", "reference_answer_text",
              "predicted_answer", "correct", "status", "grading_status", *USAGE_FIELDS,
              "latency_seconds", "input_file", "output_file", "reference_file"]
    with (output / "comparison.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in records:
            writer.writerow({**{field: row.get(field) for field in fields},
                             "predicted_answer": row["evaluation"].get("predicted_answer"),
                             "correct": row["evaluation"].get("correct"),
                             "grading_status": row["evaluation"].get("status"),
                             **{field: row["usage"].get(field) for field in USAGE_FIELDS},
                             **{field: f"questions/{row['id']}/{row['method']}/{filename}"
                                for field, filename in (("input_file", "input.txt"), ("output_file", "output.txt"),
                                                        ("reference_file", "reference_solution.txt"))}})
    escaped = lambda value: html.escape(str(value))
    rows = []
    indexed = {(row["id"], row["method"]): row for row in records}
    for identifier in config["test_ids"]:
        pair = [indexed.get((identifier, method)) for method in METHODS]
        first = next((row for row in pair if row), None)
        if first is None:
            continue
        columns = []
        for method, row in zip(METHODS, pair):
            if row is None:
                columns.append(f"<section data-method='{method}' data-grade='pending'><h3>{method}</h3><p>아직 실행하지 않음</p></section>")
                continue
            evaluation = row["evaluation"]
            usage = row["usage"]
            columns.append(
                f"<section data-method='{method}' data-grade='{escaped(evaluation.get('status'))}'><h3>{method}</h3><p>판정: {escaped(evaluation.get('status'))} · "
                f"추출 정답: {escaped(evaluation.get('predicted_answer'))} · "
                f"입력/출력/추론/전체 토큰: {escaped(usage.get('prompt_token_count'))}/"
                f"{escaped(usage.get('candidates_token_count'))}/{escaped(usage.get('thoughts_token_count'))}/"
                f"{escaped(usage.get('total_token_count'))}</p>"
                f"<p>응답 출처: {'동일 조건의 기존 대조군 재사용' if row.get('response_origin') == 'reused_control' else '새 API 요청'} · "
                f"실제 생성 시각: {escaped(row.get('completed_at'))}</p>"
                f"<details><summary>실제 API 입력 전체</summary><pre>{escaped(row['input_text'])}</pre></details>"
                f"<details><summary>출력 풀이 전체</summary><pre>{escaped(row['output_text'] or str(row.get('error')))}</pre></details>"
                f"<details><summary>판정 근거와 전체 사용량</summary><pre>{escaped(json.dumps({'evaluation':evaluation,'usage':usage},ensure_ascii=False,indent=2))}</pre></details></section>")
        rows.append(f"<article data-search='{escaped(identifier + ' ' + str(first['subject']) + ' ' + str(first['unit']) + ' ' + str(first['type']))}'><h2>{escaped(identifier)} · 실제 정답 {escaped(first['reference_answer_text'])}</h2>"
                    f"<p>{escaped(first['subject'])} / {escaped(first['unit'])} / {escaped(first['type'])}</p>"
                    f"<details><summary>문제·원본 정답해설</summary><pre>{escaped(first['problem_text'])}</pre>"
                    f"<hr><pre>{escaped(first['reference_solution'])}</pre></details><div class='pair'>"
                    + "".join(columns) + "</div></article>")
    document = ("<!doctype html><html lang='ko'><meta charset='utf-8'><meta name='viewport' content='width=device-width'>"
                "<title>MathHint 풀이 생성 비교</title><style>body{max-width:1400px;margin:32px auto;padding:0 20px;"
                "font-family:system-ui,sans-serif;color:#111;background:#fff}article{border-top:2px solid #111;margin-top:32px}"
                ".pair{display:grid;grid-template-columns:1fr 1fr;gap:24px}section{min-width:0}pre{white-space:pre-wrap;"
                "overflow-wrap:anywhere;font-family:inherit;line-height:1.65}details{border:1px solid #bbb;padding:10px;margin:10px 0}"
                "@media(max-width:800px){.pair{grid-template-columns:1fr}}@media print{details{break-inside:avoid}"
                ".pair{display:block}article{break-before:page}}</style><h1>풀이 생성 비교</h1>"
                f"<p>모델 {escaped(config['model'])} · 추론 {escaped(config['thinking_level'])}. "
                "정확도는 최종 정답 자동 비교이며 풀이의 교육과정 적합성·논리 검증은 별도 확인이 필요합니다.</p>"
                "<p><label>검색 <input id='search' placeholder='문항 ID·단원·유형'></label> "
                "<label>조건 <select id='method'><option value=''>전체</option><option value='baseline'>기본</option>"
                "<option value='regression_hint'>회귀 벡터 추가</option></select></label> "
                "<label>판정 <select id='grade'><option value=''>전체</option><option value='correct'>정답</option>"
                "<option value='incorrect'>오답</option><option value='ungradable'>자동 판정 불가</option></select></label></p>"
                "<details><summary>비교 요약과 사용량 집계</summary><pre>" + escaped(json.dumps(summary, ensure_ascii=False, indent=2))
                + "</pre></details>" + "".join(rows)
                + "<script>function filter(){let q=document.getElementById('search').value.toLowerCase(),"
                "m=document.getElementById('method').value,g=document.getElementById('grade').value;"
                "document.querySelectorAll('article').forEach(a=>{let n=0;a.querySelectorAll('section').forEach(s=>{"
                "s.hidden=!!((m&&s.dataset.method!==m)||(g&&s.dataset.grade!==g));if(!s.hidden)n++;});"
                "a.hidden=!n||!a.dataset.search.toLowerCase().includes(q);});}"
                "['search','method','grade'].forEach(id=>document.getElementById(id).addEventListener('input',filter));</script>"
                "<script>window.MathJax={tex:{inlineMath:[['$','$'],['\\\\(','\\\\)']],displayMath:[['$$','$$'],['\\\\[','\\\\]']]},"
                "options:{skipHtmlTags:['script','noscript','style','textarea','code']}};</script>"
                "<script defer src='https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js'></script></html>")
    (output / "report.html").write_text(document, encoding="utf-8")
    if charts:
        plot_comparison(output, summary)
    return summary


def run_requests(output: Path, config: dict, plan: list[dict], *, api_key: str,
                 limit: int | None = None, workers: int = 3, retry_errors: bool = False,
                 stop_file: Path | None = None) -> dict:
    config_id = initialize_run(output, config, plan)
    completed = load_completed(output, config_id)
    selected = set(config["test_ids"][:limit] if limit is not None else config["test_ids"])
    pending = iter(item for item in plan if item["id"] in selected and (
        (item["id"], item["method"]) not in completed or
        (retry_errors and completed[(item["id"], item["method"])]["status"] != "success")))
    failures, aborted, stopped = 0, False, False
    with ThreadPoolExecutor(max_workers=workers) as executor:
        active = {}

        def schedule():
            nonlocal stopped
            if stopped or (stop_file is not None and stop_file.exists()):
                stopped = True
                return
            item = next(pending, None)
            if item is not None:
                active[executor.submit(generate_one, item, config, config_id, api_key)] = item

        for _ in range(workers):
            schedule()
        while active:
            done, _ = wait(active, return_when=FIRST_COMPLETED)
            for future in done:
                item = active.pop(future)
                try:
                    result = future.result()
                except RequestedStop:
                    stopped = True
                    continue
                if result["status"] == "stopped_before_request":
                    stopped = True
                    continue
                if result["status"] == "stopped_after_attempt":
                    stopped = True
                previous = completed.get((result["id"], result["method"]))
                execution = len(previous.get("prior_executions", [])) + 2 if previous else 1
                for attempt in result["attempts"]:
                    attempt["execution"] = execution
                if previous:
                    result["prior_executions"] = previous.get("prior_executions", []) + [
                        {field: previous.get(field) for field in
                         ("status", "started_at", "completed_at", "error", "response_id")}]
                    result["attempts"] = previous["attempts"] + result["attempts"]
                save_result(output, result)
                completed[(result["id"], result["method"])] = result
                print(json.dumps({"id": result["id"], "method": result["method"],
                                  "status": result["status"], "correct": result["evaluation"].get("correct"),
                                  "total_tokens": result["usage"].get("total_token_count"),
                                  "completed_calls": len(completed)}, ensure_ascii=False), flush=True)
                fatal = result["status"] == "api_error" and result.get("error", {}).get("code") in (400, 401, 403, 404)
                failures = failures + 1 if fatal else 0
                if failures >= 3:
                    aborted = True
                if not aborted and not stopped:
                    schedule()
            render_reports(output, list(completed.values()), config, charts=False)
    summary = render_reports(output, list(completed.values()), config)
    if stopped:
        raise RequestedStop("중단 요청을 확인했습니다. 진행 중 응답은 저장했고 새 API 요청은 중단했습니다.")
    if aborted:
        raise RuntimeError("설정/인증 관련 API 오류가 3회 연속 발생해 추가 요청을 중단했습니다.")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--predictions", "--training-results", dest="predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="gemini-3.1-flash-lite")
    parser.add_argument("--thinking-level", default="minimal")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-output-tokens", type=int, default=8192)
    parser.add_argument("--hint-mode", choices=("top_tokens", "full_vector"), default="top_tokens")
    parser.add_argument("--hint-top-k", type=int, default=20)
    parser.add_argument("--import-baseline-from", type=Path)
    parser.add_argument("--attempts", type=int, choices=(1, 2), default=2)
    parser.add_argument("--workers", type=int, choices=(1, 2, 3, 4), default=3)
    parser.add_argument("--limit", type=int, help="선두 N개 문항만 실행. 설정 해시에 포함하지 않아 전체 재개 가능")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--report-only", action="store_true")
    parser.add_argument("--retry-errors", action="store_true")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit은 1 이상이어야 합니다.")
    if not math.isfinite(args.temperature) or not 0 <= args.temperature <= 2 or args.max_output_tokens < 1:
        parser.error("temperature는0~2, max-output-tokens는 양수여야 합니다.")
    config, plan = prepare_plan(args.project.resolve(), args.predictions.resolve(), model=args.model,
                                thinking_level=args.thinking_level, temperature=args.temperature,
                                max_output_tokens=args.max_output_tokens, attempts=args.attempts,
                                hint_mode=args.hint_mode, hint_top_k=args.hint_top_k)
    output = args.output.resolve()
    config_id = initialize_run(output, config, plan)
    if args.import_baseline_from is not None:
        import_baseline(args.import_baseline_from.resolve(), output, config, plan)
    if args.prepare_only or args.report_only:
        render_reports(output, list(load_completed(output, config_id).values()), config)
        print(json.dumps({"config_id": config_id, "planned_calls": len(plan), "api_calls": 0,
                          "output": str(output)}, ensure_ascii=False))
        return
    from dotenv import load_dotenv
    load_dotenv(args.project / ".env", override=False)
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        parser.error("환경변수 또는 로컬 .env에 GEMINI_API_KEY를 설정하세요.")
    run_requests(output, config, plan, api_key=key, limit=args.limit,
                 workers=args.workers, retry_errors=args.retry_errors)


if __name__ == "__main__":
    main()
