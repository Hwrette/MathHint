"""고정 80문항: 문제만(A), 예측 상위20토큰(B), 실제 해설 상위20토큰(C).

RUN_API=False가 기본이다. 정확히 일치하는 기존 A/B만 재사용하고, C의 실제
해설 빈도는 진단용 oracle 정보로 구분한다. 요청 직전 SDK 인자를 저장한다.
"""

import html
import json
import os
from pathlib import Path
from types import SimpleNamespace

if __package__:
    from . import CompareGeneration as comparison
    from .RateLimitedComparison import GlobalRateLimiter, DailyQuotaStop
else:
    import CompareGeneration as comparison
    from RateLimitedComparison import GlobalRateLimiter, DailyQuotaStop

ROOT = Path(__file__).resolve().parents[1]
PREVIOUS = ROOT / "results/model_comparison_2026-11-07"
PREDICTIONS = PREVIOUS / "01_회귀모델/regression_predictions.json"
OUTPUT = ROOT / "results/final_experiment/03_gemini"
SOURCE_CONFIG = PREVIOUS / "03_Gemini비교/실험설정.json"
SOURCE_RECORDS = PREVIOUS / "03_Gemini비교/원본응답_160개.jsonl"
MODEL = "gemini-3.1-flash-lite"
THINKING_LEVEL = "minimal"
TEMPERATURE = 0.0
MAX_OUTPUT_TOKENS = 8192
RUN_API = False
INTERVAL = 5.0
WORKERS = 2
LIMIT = None
METHODS = ("baseline", "regression_hint", "oracle_hint")
CONDITIONS = dict(zip(METHODS, "ABC"))
METHOD_NAMES = {"baseline": "A 문제만", "regression_hint": "B 예측 상위20토큰", "oracle_hint": "C 실제 해설 상위20토큰 (oracle)"}
ORDERS = ((0, 1, 2), (0, 2, 1), (1, 0, 2), (1, 2, 0), (2, 0, 1), (2, 1, 0))


def serialize_vector(vocabulary, values, *, source="regression_prediction"):
    """선택·반올림·JSON 구조는 공통이며 C에서 출처 설명만 바꾼다."""
    if source not in ("regression_prediction", "actual_reference"):
        raise ValueError("알 수 없는 벡터 출처입니다.")
    text, hint = comparison.serialize_hint(vocabulary, values, mode="top_tokens", top_k=20)
    if source == "actual_reference":
        text = text.replace("학습 데이터로 학습한 선형회귀가 예측한", "정답 해설에서 계산한 실제", 1)
        text = text.replace("예측 빈도순", "실제 빈도순", 1)
    return text, {**hint, "source": source}


def prepare_plan(project, predictions_path, *, model=MODEL, thinking_level=THINKING_LEVEL,
                 temperature=TEMPERATURE, max_output_tokens=MAX_OUTPUT_TOKENS,
                 system_instruction=comparison.DEFAULT_SYSTEM, attempts=2):
    """문제 원문과 고정 어휘를 유지하고 실제 해설 벡터는 C에만 연결한다."""
    project, predictions_path = Path(project), Path(predictions_path)
    config, pairs = comparison.prepare_plan(project, predictions_path, model=model,
        thinking_level=thinking_level, temperature=temperature, max_output_tokens=max_output_tokens,
        system_instruction=system_instruction, attempts=attempts, hint_mode="top_tokens", hint_top_k=20)
    actual_path = project / "data/vectors/solutions/test_vectors.json"
    vocabulary_path = project / "data/vectors/solutions/vocabulary.json"
    vocabulary = comparison.read_json(vocabulary_path)
    predictions = comparison.read_json(predictions_path)
    actual = comparison.read_json(actual_path)
    if predictions["vocabulary"] != vocabulary or actual["generation_id"] != config["generation_id"]:
        raise ValueError("실제·예측 벡터의 어휘 또는 데이터 버전이 다릅니다.")
    if [row["id"] for row in actual["documents"]] != config["test_ids"]:
        raise ValueError("실제 해설 벡터의 행이 고정 테스트 ID 순서와 다릅니다.")
    if any(len(row["vector"]) != len(vocabulary) or any(isinstance(v,bool) or not isinstance(v,(int,float))
           or v < 0 or v != int(v) for v in row["vector"]) for row in actual["documents"]):
        raise ValueError("실제 해설 빈도는 고정 어휘에 대응하는 0 이상의 정수여야 합니다.")
    answers = {row["id"]: row["vector"] for row in actual["documents"]}
    grouped = {(row["id"], row["method"]): row for row in pairs}
    plan, hashes = [], []
    for index, identifier in enumerate(config["test_ids"]):
        base = grouped[identifier, "baseline"]
        predicted = grouped[identifier, "regression_hint"]
        oracle_text, oracle_hint = serialize_vector(vocabulary, answers[identifier], source="actual_reference")
        arms = [base, predicted, {**base, "method": "oracle_hint", "input_text": base["problem_text"] + oracle_text,
            "input_sha256": comparison.digest(base["problem_text"] + oracle_text), "hint": oracle_hint}]
        for item in arms:
            item.update(condition=CONDITIONS[item["method"]], uses_test_reference_vector=item["method"] == "oracle_hint",
                        compact_storage=True)
            if item["method"] == "regression_hint":
                item["hint"] = {**item["hint"], "source": "regression_prediction"}
        plan.extend(arms[position] for position in ORDERS[index % len(ORDERS)])
        hashes.append({"id": identifier, **{row["method"]: row["input_sha256"] for row in arms},
                       "reference_sha256": comparison.digest([base["reference"], base["reference_solution"]])})
    config.update(schema_version=3, methods=list(METHODS), compact_storage=True, predictions_source=str(predictions_path),
        condition_order="six_balanced_permutations_new_calls_skip_reused_successes",
        oracle_caveat="Actual held-out reference-solution token counts are privileged diagnostic information; not service accuracy or a guaranteed upper bound.",
        hint_source_wording="B legacy predicted-source description; C replaces only source description by actual-reference description; identical JSON/selection/instruction structure.",
        actual_solution_vectors_sha256=comparison.file_hash(actual_path), vocabulary_sha256=comparison.file_hash(vocabulary_path),
        inputs=hashes, runner_sha256=comparison.file_hash(Path(__file__)),
        shared_runner_sha256=comparison.file_hash(Path(comparison.__file__)))
    return config, plan


def reuse_existing(output, config, plan, source_config_path, source_records_path):
    """기존 A/B의 입력·설정을 모두 검증한 뒤 저장하며 다른 요청을 섞지 않는다."""
    source_config_path, source_records_path = Path(source_config_path), Path(source_records_path)
    source = comparison.read_json(source_config_path)
    old_config, old_id = source["config"], source["config_id"]
    if comparison.digest(old_config) != old_id:
        raise ValueError("기존 설정의 해시가 다릅니다.")
    for field in ("model", "thinking_level", "temperature", "max_output_tokens", "system_instruction",
                  "generation_id", "train_ids", "test_ids", "grader_sha256", "hint_mode", "hint_top_k"):
        if old_config.get(field) != config.get(field):
            raise ValueError("기존 요청 설정 불일치: " + field)
    previous = {}
    for line in source_records_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        key = row["id"], row["method"]
        if row["config_id"] != old_id or key in previous:
            raise ValueError("기존 응답 설정이 다르거나 문항·조건이 중복됩니다.")
        if row["input_sha256"] != comparison.digest(row["input_text"]):
            raise ValueError("기존 입력 해시가 실제 텍스트와 다릅니다.")
        previous[key] = row
    candidates = []
    for item in plan:
        if item["method"] not in ("baseline", "regression_hint"):
            continue
        row = previous.get((item["id"], item["method"]))
        if row is None or row["status"] != "success":
            continue
        for field in ("input_text", "input_sha256", "system_instruction", "reference", "reference_answer_text", "reference_solution", "problem_text"):
            if row.get(field) != item.get(field):
                raise ValueError("기존 문항 입력 불일치: " + item["id"] + "/" + field)
        if row.get("model") != config["model"] or row.get("thinking_level") != config["thinking_level"]:
            raise ValueError("기존 응답의 요청 모델 또는 추론 설정이 다릅니다.")
        if (row.get("hint") or {}).get("mapping") != (item.get("hint") or {}).get("mapping"):
            raise ValueError("기존 힌트의 토큰·수치가 다릅니다.")
        candidates.append((item, row))
    config_id = comparison.initialize_run(output, config, plan)
    completed = comparison.load_completed(output, config_id)
    imported = []
    for item, row in candidates:
        if completed.get((item["id"], item["method"]), {}).get("status") == "success":
            continue
        comparison.save_result(output, {**row, "config_id": config_id, "compact_storage": True,
            "condition": item["condition"], "uses_test_reference_vector": False,
            "response_origin": "reused_exact_request", "source_provenance": row.get("provenance"),
            "provenance": {"source_config": str(source_config_path), "source_records": str(source_records_path),
                "source_config_id": old_id, "source_record_sha256": comparison.digest(row),
                "source_records_sha256": comparison.file_hash(source_records_path),
                "request_match": "exact_user_text_system_model_temperature_thinking_max_output",
                "historical_sdk_boundary_capture": False, "imported_at": comparison.utc_now()}})
        imported.append({"id": item["id"], "method": item["method"]})
    return {"validated_reusable": len(candidates), "imported_this_run": len(imported), "imported": imported,
            "source_config_id": old_id, "source_records_sha256": comparison.file_hash(source_records_path)}


def request_audit_record(project, item, config):
    """완성된 전체 입력과 SDK의 정규화 인자를 저장용으로 구성한다."""
    snapshot = comparison.request_snapshot(comparison.sdk_request_arguments(config, item["input_text"]))
    project = Path(project)
    return {"id": item["id"], "condition": item["condition"], "method": item["method"],
        "requested_model": config["model"], "system_instruction": item["system_instruction"],
        "user_message": item["input_text"], "problem_text": item["problem_text"], "hint": item["hint"],
        "full_request_text": "[SYSTEM]\n" + item["system_instruction"] + "\n[USER]\n" + item["input_text"],
        "sdk_request": snapshot, "sdk_request_sha256": comparison.digest(snapshot),
        "input_sha256": item["input_sha256"], "generation_id": config["generation_id"],
        "sources": {"problem": str(project / f"data/processed/problems/{item['id']}.txt"),
            "vector": str(project / "data/vectors/solutions/test_vectors.json") if item["method"] == "oracle_hint"
                      else (config.get("predictions_source", str(PREDICTIONS)) if item["method"] == "regression_hint" else None),
            "vocabulary": str(project / "data/vectors/solutions/vocabulary.json") if item["hint"] else None},
        "transport": {"timeout_ms": 90000, "sdk_attempts": 1},
        "historical_capture_note": "A/B old successful records are reconstructed and exact-input-verified, not retroactively captured live; new C is observed immediately before SDK call."}


def dry_run(output, project, config, plan):
    """모든 입력을 SDK 호출 스파이로 검사한다. 네트워크를 사용하지 않는다."""
    audit = Path(output) / "prompt_audit"
    observed = []
    examples = []
    for item in plan:
        record = request_audit_record(project, item, config)
        expected = record["sdk_request"]
        captured = []
        class FakeClient:
            def __init__(self, **_):
                self.models = self
            def __enter__(self):
                return self
            def __exit__(self, *_):
                return False
            def generate_content(self, **arguments):
                captured.append(comparison.request_snapshot(arguments))
                return SimpleNamespace(text="dry-run")
        request = comparison.make_request(config, "DRY_RUN_NO_CREDENTIAL", request_observer=observed.append, client_factory=FakeClient)
        request(item["input_text"])
        if captured != [expected] or observed[-1] != expected:
            raise ValueError("저장한 입력과 실제 SDK 호출 인자가 다릅니다.")
        roundtrip = json.loads(json.dumps(record, ensure_ascii=False))
        if roundtrip["user_message"] != item["input_text"] or not item["input_text"].startswith(item["problem_text"]):
            raise ValueError("JSON 직렬화 과정에서 문제 문자열이 바뀌었습니다.")
        if item["method"] == "baseline" and item["input_text"] != item["problem_text"]:
            raise ValueError("문제만 조건에 추가 정보가 있습니다.")
        record["verification"] = {"mocked_sdk_arguments_match_saved": True, "json_roundtrip_preserves_latex": True,
            "problem_is_exact_prefix": True, "reference_prose_not_in_sdk_arguments": item["reference_solution"] not in item["input_text"]}
        comparison.write_json(audit / "requests" / item["id"] / (item["condition"] + ".json"), record)
        if item["id"] in {config["test_ids"][0], config["test_ids"][len(config["test_ids"]) // 2], config["test_ids"][-1]}:
            examples.append(record)
    table = ["# 실제 입력 감사", "", "240개 입력을 인증 없는 모의 SDK 경계로 검증했다. 실서비스 호출은 이 단계에서 0회다.", "",
        "| 조건 | 사용자 메시지 | 해설 정보 |", "|---|---|---|", "| A | 문제 원문 전체 | 없음 |",
        "| B | 문제 + 예측 상위20토큰 JSON | 학습된 회귀 모델 |", "| C | 문제 + 실제 상위20토큰 JSON | 테스트 정답 해설 (oracle) |", "",
        "B와 C는 최대20개 양의 빈도를 반올림 전 값으로 내림차순 정렬하고, 동률이면 고정 어휘 순서를 따른다. 전송 수치는 소수 셋째 자리까지 반올림하며 0으로 표시되는 항목은 제외한다. 실제 빈도는 정수지만 공통 직렬화에서 실수 표기가 될 수 있다.", "",
        "B의 기존 문구는 보존하고 C에서는 정보 출처 표현만 바꿨다. JSON 구조와 마지막 지시문은 동일하다. 선택된 양의 토큰이20개 미만이면 있는 항목만 보낸다.", "",
        "A/B 재사용 응답은 기존 요청 텍스트·설정·해시가 일치함을 검증했다. 과거에 SDK 경계를 실시간 기록했다고 주장하지 않는다. C 실호출에서는 호출 직전 인자를 별도 sdk_calls에 기록한다.", "",
        "요청 모델명과 응답 model_version은 별개다. API가 공개하지 않는 내부 모델 정보는 검증할 수 없다.", ""]
    for record in sorted(examples, key=lambda row:(row["id"], row["condition"])):
        table += [f"## {record['id']} — {record['condition']}", "", "```text", record["full_request_text"], "```", ""]
    (audit / "README.md").write_text("\n".join(table), encoding="utf-8")
    report = {"requests": len(plan), "ids": len(config["test_ids"]), "conditions": list(CONDITIONS.values()),
        "mocked_sdk_calls": len(observed), "live_api_calls": 0, "all_saved_requests_match_mocked_sdk_arguments": True,
        "json_roundtrip_preserves_latex": True, "source_code_audit": {
            "GoogleAPI.py": "Standalone legacy one-question tool sends original problem unchanged; display-only to_math_markdown runs after API. Final experiment does not use this tool or its different system setting.",
            "CompareGeneration.py": "make_request shares SDK arguments helper and observer immediately before client.models.generate_content.",
            "RateLimitedComparison.py": "GlobalRateLimiter only gates starts/retries; input text passed unchanged."}}
    comparison.write_json(audit / "dry_run.json", report)
    return report


def render_reports(output, records, config, *, charts=False):
    """세 조건을 같은 표와 세 열의 문항별 화면으로 내보낸다."""
    summary = {"expected_questions": len(config["test_ids"]), "methods": {}, "oracle_caveat": config["oracle_caveat"]}
    for method in METHODS:
        rows = [row for row in records if row["method"] == method]
        success = [row for row in rows if row["status"] == "success"]
        graded = [row for row in success if row["evaluation"].get("correct") is not None]
        correct = sum(row["evaluation"]["correct"] is True for row in graded)
        usage = {}
        for field in comparison.USAGE_FIELDS:
            values = [row["usage"].get(field) for row in success]
            known = [value for value in values if value is not None]
            usage[field] = {"sum": sum(known) if values and len(known) == len(values) else None,
                            "known_sum": sum(known), "mean": sum(known) / len(known) if known else None,
                            "provided": len(known), "missing": len(values) - len(known)}
        summary["methods"][method] = {"recorded": len(rows), "successful": len(success), "graded": len(graded),
            "correct": correct, "accuracy_on_graded": correct / len(graded) if graded else None,
            "correct_per_expected": correct / len(config["test_ids"]), "usage": usage,
            "reused_controls": sum(row.get("response_origin", "").startswith("reused") for row in rows)}
    escaped = lambda value: html.escape(str(value))
    indexed = {(row["id"], row["method"]): row for row in records}
    cards = []
    for identifier in config["test_ids"]:
        columns = []
        for method in METHODS:
            row = indexed.get((identifier, method))
            content = "미실행" if row is None else (f'<p>원본 정답: {escaped(row["reference_answer_text"])} / 판정: {escaped(row["evaluation"].get("correct"))} / 전체 토큰: {escaped(row["usage"].get("total_token_count"))}</p>'
                f'<details><summary>실제 입력</summary><pre>{escaped(row["input_text"])}</pre></details>'
                f'<pre>{escaped(row["output_text"] or row.get("error", ""))}</pre>'
                f'<details><summary>원본 정답·해설</summary><pre>{escaped(row["reference_solution"])}</pre></details>')
            columns.append(f'<section><h3>{METHOD_NAMES[method]}</h3>{content}</section>')
        cards.append(f'<article data-id="{escaped(identifier)}"><h2>{escaped(identifier)}</h2><div class="columns">' + "".join(columns) + '</div></article>')
    document = '<!doctype html><html lang="ko"><meta charset="utf-8"><title>세 조건 풀이 비교</title><style>body{font:15px/1.6 system-ui;max-width:1700px;margin:25px auto;padding:20px;color:#111}.columns{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px}article{border-top:2px solid #333;margin-top:25px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit}details{border:1px solid #ccc;padding:8px}section{min-width:0}@media(max-width:900px){.columns{grid-template-columns:1fr}}</style><h1>세 조건 풀이 비교</h1><p>실제 해설 벡터 조건은 테스트 정답 정보를 제공한 조건이며 예측 모델의 성능으로 해석하지 않습니다. 표시된 정오답은 원본 정답표 기준이며 풀이 타당성은 별도 평가입니다.</p><input id="search" placeholder="문항 ID 검색">' + "".join(cards) + '<script>document.querySelector("#search").oninput=e=>document.querySelectorAll("article").forEach(a=>a.hidden=!a.dataset.id.includes(e.target.value));</script></html>'
    (output / "report.html").write_text(document, encoding="utf-8")
    return summary


def resolve_resume_config(output, config):
    """입력·설정이 모두 같으면 소스 정리 뒤에도 기존 실험 ID를 보존한다."""
    path = Path(output) / "config.json"
    if not path.exists():
        return config
    saved = comparison.read_json(path)
    frozen = saved["config"]
    source_fields = {"runner_sha256", "shared_runner_sha256"}
    semantic = lambda value: {key: item for key, item in value.items() if key not in source_fields}
    if comparison.digest(frozen) != saved["config_id"] or semantic(config) != semantic(frozen):
        raise ValueError("기존 실험의 입력 또는 설정이 달라졌습니다. 새 출력 폴더를 사용하세요.")
    if config != frozen:
        transition_path = Path(output) / "source_transition.json"
        transition = comparison.read_json(transition_path) if transition_path.exists() else {
            "frozen_config_id": saved["config_id"], "frozen_source_hashes": {key:frozen.get(key) for key in sorted(source_fields)}, "versions": []}
        current = {key:config.get(key) for key in sorted(source_fields)}
        if not any(version["source_hashes"] == current for version in transition["versions"]):
            transition["versions"].append({"recorded_at": comparison.utc_now(), "source_hashes": current,
                "all_non_source_config_fields_and_input_hashes_match": True,
                "reason": "Source provenance changed; model/settings/prompt/vector/input/grader fingerprints are identical."})
            comparison.write_json(transition_path, transition)
    return frozen


def prepare(output, config, plan, source_config_path=SOURCE_CONFIG, source_records_path=SOURCE_RECORDS, *, project=ROOT):
    output = Path(output)
    config = resolve_resume_config(output, config)
    # Validate source reuse before storing any imported result.
    imported = reuse_existing(output, config, plan, source_config_path, source_records_path) if source_config_path else {
        "validated_reusable": 0, "imported_this_run": 0}
    comparison.initialize_run(output, config, plan)
    audit = dry_run(output, project, config, plan)
    completed = comparison.load_completed(output, comparison.digest(config))
    pending = [item for item in plan if completed.get((item["id"], item["method"]), {}).get("status") != "success"]
    preflight = {"config_id": comparison.digest(config), "expected_requests": len(plan), **imported,
        "successful_already_saved": len([row for row in completed.values() if row["status"] == "success"]),
        "new_calls_needed": len(pending), "pending_by_method": {method:sum(item["method"] == method for item in pending) for method in METHODS},
        "dry_run": audit, "maximum_attempts_per_pending": config["max_attempts"]}
    comparison.write_json(output / "preflight.json", preflight)
    render_reports(output, list(completed.values()), config)
    return preflight


def run_experiment(output, config, plan, *, api_key, interval=INTERVAL, workers=WORKERS,
                   limit=None, retry_errors=True, request_function=None):
    """검증된 입력만 기존 저장·재개·속도 제한 엔진으로 실행한다."""
    output = Path(output)
    config = resolve_resume_config(output, config)
    comparison.initialize_run(output, config, plan)
    execution_id = comparison.utc_now().replace(":", "").replace(".", "_")
    directory = output / "execution_runs"; directory.mkdir(exist_ok=True)
    execution = {"config_id": comparison.digest(config), "started_at": comparison.utc_now(), "status": "running",
        "wrapper_sha256": comparison.file_hash(Path(__file__)), "interval": interval, "workers": workers,
        "retry_errors": retry_errors, "limit": limit}
    comparison.write_json(directory / (execution_id + ".json"), execution)
    def event(value):
        with (directory / (execution_id + "_rate_events.jsonl")).open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(value, ensure_ascii=False) + "\n")
    stop_file = output / "stop_requested"
    limiter = GlobalRateLimiter(interval, event_handler=event, stop_requested=stop_file.exists)
    def generate(item, current_config, current_id, key):
        if limiter.daily_exhausted:
            raise DailyQuotaStop("일일 한도가 소진되어 다음 요청을 보내지 않습니다.")
        request_hashes = []
        expected_path = output / "prompt_audit/requests" / item["id"] / (item["condition"] + ".json")
        expected = comparison.read_json(expected_path) if expected_path.exists() else request_audit_record(ROOT, item, config)
        def observe(snapshot):
            if snapshot != expected["sdk_request"]:
                raise ValueError("실호출 SDK 인자가 감사한 입력과 다릅니다.")
            request_hashes.append(comparison.digest(snapshot))
            comparison.write_json(output / "prompt_audit/sdk_calls" /
                f"{item['id']}_{item['condition']}_{execution_id}_{len(request_hashes)}.json",
                {"id": item["id"], "condition": item["condition"], "method": item["method"], "captured_at": comparison.utc_now(),
                 "execution_id": execution_id, "request": snapshot, "request_sha256": request_hashes[-1],
                 "matches_saved_prompt": True, "capture": "immediately_before_sdk_generate_content"})
        request = request_function or comparison.make_request(config, api_key, request_observer=observe)
        result = comparison.generate_one(item, current_config, current_id, key,
            request_function=lambda text: limiter.request(request, text))
        result.update(rate_limited_execution_id=execution_id, sdk_request_sha256=expected["sdk_request_sha256"],
            sdk_boundary_captured_attempts=len(request_hashes), sdk_boundary_capture_expected=request_function is None)
        if limiter.daily_exhausted and (result["status"].startswith("stopped_") or any(a.get("code") == 429 for a in result["attempts"])):
            result.update(status="api_error", daily_quota_exhausted=True)
        return result
    try:
        result = comparison.run_requests(output, config, plan, api_key=api_key, workers=workers, limit=limit,
            retry_errors=retry_errors, stop_file=stop_file, generate_function=generate, report_function=render_reports)
        execution["status"] = "completed"
        return result
    except comparison.RequestedStop:
        execution["status"] = "daily_quota_exhausted" if limiter.daily_exhausted else "stopped_gracefully"
        raise
    except BaseException as error:
        execution.update(status="interrupted_or_failed", error_type=type(error).__name__, error_message=str(error).replace(api_key, "[REDACTED]"))
        raise
    finally:
        execution["completed_at"] = comparison.utc_now()
        comparison.write_json(directory / (execution_id + ".json"), execution)


def main():
    config, plan = prepare_plan(ROOT, PREDICTIONS)
    preflight = prepare(OUTPUT, config, plan)
    print(json.dumps({key:preflight[key] for key in ("expected_requests", "validated_reusable", "successful_already_saved", "new_calls_needed", "pending_by_method")}, ensure_ascii=False))
    if RUN_API:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env", override=False)
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise SystemExit("GEMINI_API_KEY가 필요합니다.")
        run_experiment(OUTPUT, config, plan, api_key=key, limit=LIMIT)


if __name__ == "__main__":
    main()
