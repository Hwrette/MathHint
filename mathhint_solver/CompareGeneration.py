"""세 조건 실행기가 재사용하는 입력·SDK 전송·응답 저장·재개 공통 함수.

실행 진입점은 ThreeWayGeneration.py 하나다. 여기서는 API 키를 읽거나
독립 실험을 시작하지 않는다. 성공 응답은 재요청하지 않고 입력 변경을 거부한다.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__:
    from .AnswerEvaluation import evaluate_answer, extract_reference
else:
    from AnswerEvaluation import evaluate_answer, extract_reference


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
    if mode != "top_tokens" or isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
        raise ValueError("최종 실험은 top_tokens 방식과 양수 top_k를 사용합니다.")
    clipped = []
    for value in vector:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("회귀 예측은 유한한 실수여야 합니다.")
        clipped.append(max(0.0, float(value)))
    indices = [index for index, value in enumerate(clipped) if value > 0]
    indices = sorted(indices, key=lambda index: (-clipped[index], index))[:top_k]
    mapping = {vocabulary[index]: round(clipped[index], 3) for index in indices if round(clipped[index], 3) > 0}
    payload = json.dumps(mapping, ensure_ascii=False, separators=(",", ":"))
    text = (f"\n\n[학습 데이터로 학습한 선형회귀가 예측한 해설 주요 토큰: 예측 빈도순 상위{top_k}개]\n"
            + payload + "\n위 주요 토큰을 참고하여 풀이를 작성해줘.")
    return (text,
            {"transform": "clip_min_0_round_3_decimal_places_omit_zeros",
             "mode": mode, "top_k": top_k,
             "selection": "descending_unrounded_positive_frequency_ties_vocabulary_order",
             "vocabulary_size": len(vocabulary), "transmitted_coordinates": len(mapping),
             "mapping": mapping})


def load_predictions(path: Path, test_ids: list[str], generation_id: str) -> tuple[list[str], dict]:
    data = read_json(path)
    if data.get("generation_id") not in (None, generation_id):
        raise ValueError("회귀 예측의 데이터 generation_id가 다릅니다.")
    vocabulary = data["vocabulary"]
    documents = data["documents"]
    predictions = {}
    for document in documents:
        identifier = document.get("id")
        vector = document["predicted_vector"]
        if not isinstance(identifier, str) or identifier in predictions or not isinstance(vector, list):
            raise ValueError("예측 문항 ID가 중복되거나 예측 벡터가 없습니다.")
        serialize_hint(vocabulary, vector)
        predictions[identifier] = vector
    if [document["id"] for document in documents] != test_ids:
        raise ValueError(f"{path}: 회귀 예측 문항 ID/행 순서가 고정 테스트 ID 목록과 다릅니다.")
    return vocabulary, predictions


def prepare_plan(project: Path, predictions_path: Path, *, model: str,
                 thinking_level: str, temperature: float, max_output_tokens: int,
                 system_instruction: str = DEFAULT_SYSTEM, attempts: int = 2,
                 hint_mode: str = "top_tokens", hint_top_k: int = 20,
                 data_root: Path | None = None) -> tuple[dict, list[dict]]:
    project = Path(project)
    data_root = Path(data_root) if data_root is not None else project / "data"
    metadata_path = data_root / "processed/metadata.json"
    metadata = read_json(metadata_path)
    train_path = data_root / "processed/splits/train.json"
    test_path = data_root / "processed/splits/test.json"
    train_ids, test_ids = read_json(train_path), read_json(test_path)
    if set(train_ids) & set(test_ids) or len(set(test_ids)) != len(test_ids) or len(set(train_ids)) != len(train_ids):
        raise ValueError("학습·테스트 ID가 겹치거나 테스트 ID가 중복됩니다.")
    vocabulary, predictions = load_predictions(predictions_path, test_ids, metadata["generation_id"])
    prediction_metadata = read_json(predictions_path)
    vocabulary_path = data_root / "vectors/solutions/vocabulary.json"
    if vocabulary != read_json(vocabulary_path):
        raise ValueError(f"{predictions_path}: 해설 어휘 내용/순서가 {vocabulary_path}와 다릅니다.")
    if "input_vocabulary" in prediction_metadata:
        input_path = data_root / "vectors/problems/vocabulary.json"
        if prediction_metadata["input_vocabulary"] != read_json(input_path):
            raise ValueError(f"{predictions_path}: 문제 어휘 내용/순서가 {input_path}와 다릅니다.")
    if "train_ids" in prediction_metadata and prediction_metadata["train_ids"] != train_ids:
        raise ValueError("회귀 학습 ID가 고정 학습 ID/순서와 다릅니다.")
    records = {record["id"]: record for record in metadata["records"]}
    plan, input_hashes = [], []
    for index, identifier in enumerate(test_ids):
        meta = records[identifier]
        problem = (data_root / "processed/problems" / (identifier + ".txt")).read_text(encoding="utf-8-sig")
        solution = (data_root / "processed/solutions" / (identifier + ".txt")).read_text(encoding="utf-8-sig")
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
              "hint_transform": "positive_clip_select_unrounded_desc_tie_vocab_round_3_omit_zeros",
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
    for item in (() if config.get("compact_storage") else plan):
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


def sdk_request_arguments(config, text):
    """인증 정보를 제외하고 실제 generate_content에 넘길 SDK 인자를 만든다."""
    from google.genai import types
    return {"model": config["model"], "contents": text,
            "config": types.GenerateContentConfig(
                system_instruction=config["system_instruction"],
                temperature=config["temperature"],
                max_output_tokens=config["max_output_tokens"],
                thinking_config=types.ThinkingConfig(thinking_level=config["thinking_level"]))}


def request_snapshot(arguments):
    """SDK 객체의 실제 필드와 원문 문자열을 JSON으로 보존한다. 키·헤더는 포함하지 않는다."""
    return {"model": arguments["model"], "contents": arguments["contents"],
            "config": arguments["config"].model_dump(mode="json", exclude_none=True)}


def make_request(config, api_key, *, request_observer=None, client_factory=None):
    """호출 직전에 SDK 인자를 관찰할 수 있는 공통 전송 경로다."""
    from google import genai
    from google.genai import types
    factory = client_factory or genai.Client

    def request(text):
        arguments = sdk_request_arguments(config, text)
        with factory(api_key=api_key, http_options=types.HttpOptions(
                timeout=90_000, retry_options=types.HttpRetryOptions(attempts=1))) as client:
            if request_observer is not None:
                request_observer(request_snapshot(arguments))
            return client.models.generate_content(**arguments)
    return request


def generate_one(item: dict, config: dict, config_id: str, api_key: str,
                 request_function=None) -> dict:
    """한 조건을 요청하며 실패한 시도도 경과 시간과 알려진 사용량을 남긴다."""
    if request_function is None:
        request_function = make_request(config, api_key)
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
    if result.get("compact_storage"):
        return
    folder = output / "questions" / result["id"] / result["method"]
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "output.txt").write_text(result["output_text"], encoding="utf-8")
    write_json(folder / "record.json", result)


def run_requests(output: Path, config: dict, plan: list[dict], *, api_key: str, report_function,
                 limit: int | None = None, workers: int = 3, retry_errors: bool = False,
                 stop_file: Path | None = None, generate_function=None) -> dict:
    generate = generate_function or generate_one
    render = report_function
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
                active[executor.submit(generate, item, config, config_id, api_key)] = item

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
            render(output, list(completed.values()), config, charts=False)
    summary = render(output, list(completed.values()), config)
    if stopped:
        raise RequestedStop("중단 요청을 확인했습니다. 진행 중 응답은 저장했고 새 API 요청은 중단했습니다.")
    if aborted:
        raise RuntimeError("설정/인증 관련 API 오류가 3회 연속 발생해 추가 요청을 중단했습니다.")
    return summary
