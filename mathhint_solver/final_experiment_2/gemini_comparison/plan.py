"""두 확정 모델을 검증하고 같은 문제·시스템·전송 규칙의 네 조건을 만든다."""

from itertools import permutations
from pathlib import Path
from types import SimpleNamespace

from ... import CompareGeneration as comparison
from ...AnswerEvaluation import extract_reference
from .common import ROOT, OUTPUT, METHODS, read_json, write_json, read_jsonl, append_jsonl, safe_output

MODEL = "gemini-3.1-flash-lite"
SETTINGS = {"model": MODEL, "temperature": 0.0, "thinking_level": "minimal",
            "max_output_tokens": 8192, "system_instruction": comparison.DEFAULT_SYSTEM}
ORDERS = tuple(permutations("ABCD"))


def model_gate(root, data):
    """모델·예측 SHA와 전체 어휘·행을 검사한다. 여기서는 모델을 학습하지 않는다."""
    root = Path(root)
    identifiers = data["ids"]["train"] + data["ids"]["test"]
    vocabulary = data["vocabularies"]["solutions"]
    models, predictions = {}, {}
    for name in ("regression", "deep_learning"):
        folder = root / "results/final_experiment_2" / name
        manifest_path = folder / "model_manifest.json"
        if not manifest_path.is_file():
            raise FileNotFoundError(f"Gemini 실행 전 두 모델을 모두 확정해야 합니다: {manifest_path}")
        manifest = read_json(manifest_path)
        if (manifest.get("frozen") is not True or manifest.get("frozen_before_test") is not True
                or manifest.get("dataset_id") != data["dataset_id"]
                or manifest.get("selection_basis") != "internal_validation_precision_at_20"):
            raise ValueError(f"검증 기준으로 확정한 모델이 아닙니다: {manifest_path}")
        files = {}
        for key in ("checkpoint", "predictions"):
            record = manifest[key]
            path = (folder / record["path"]).resolve()
            if not path.is_relative_to(folder.resolve()) or comparison.file_hash(path) != record["sha256"]:
                raise ValueError(f"확정 모델/예측의 경로 또는 SHA가 다릅니다: {path}")
            files[key] = {"path": str(path.relative_to(root.resolve())), "sha256": record["sha256"]}
        predicted = read_json(root / files["predictions"]["path"])
        if predicted["dataset_id"] != data["dataset_id"] or predicted["vocabulary"] != vocabulary:
            raise ValueError(f"모델 예측의 데이터 또는 풀이 어휘 순서가 다릅니다: {name}")
        docs = predicted["documents"]
        if [row["id"] for row in docs] != identifiers or len(set(row["id"] for row in docs)) != len(identifiers):
            raise ValueError(f"모델 예측이 원래265개 ID 순서와 다릅니다: {name}")
        vectors = {}
        for row in docs:
            vector = row["raw_predicted_vector"]
            comparison.serialize_hint(vocabulary, vector)
            if "actual_vector" in row or "reference_solution" in row:
                raise ValueError(f"모델 예측 파일에는 실제 풀이를 섞지 않습니다: {name}")
            vectors[row["id"]] = vector
        if name == "deep_learning" and not any(value in str(manifest.get("architecture"))
                  for value in ("ReLU", "GELU", "SiLU", "Tanh", "ELU", "Softplus")):
            raise ValueError("확정 딥러닝 구조에서 비선형 활성화 함수를 확인할 수 없습니다.")
        models[name] = {"manifest_path": str(manifest_path.relative_to(root)),
                        "manifest_sha256": comparison.file_hash(manifest_path), **files,
                        "architecture": manifest["architecture"], "frozen_before_test": True}
        predictions[name] = vectors
    return models, predictions


def serialize_vector(vocabulary, vector, condition):
    if condition not in ("B", "C", "D"):
        raise ValueError("힌트 조건은 B/C/D입니다.")
    text, hint = comparison.serialize_hint(vocabulary, vector)
    if condition == "C":
        text = text.replace("학습 데이터로 학습한 선형회귀가 예측한", "학습 데이터로 학습한 딥러닝이 예측한", 1)
    if condition == "D":
        text = text.replace("학습 데이터로 학습한 선형회귀가 예측한", "정답 해설에서 계산한 실제", 1)
        text = text.replace("예측 빈도순", "실제 빈도순", 1)
    source = {"B": "regression_prediction", "C": "deep_learning_prediction", "D": "actual_reference"}[condition]
    return text, {**hint, "source": source}


def prepare_plan(root, data, *, split="test"):
    root = Path(root).resolve()
    if split not in ("test", "train"):
        raise ValueError("생성 대상은 test 또는 train입니다.")
    models, predictions = model_gate(root, data)
    identifiers = data["ids"][split]
    vocabulary = data["vocabularies"]["solutions"]
    answers = data["arrays"]["solutions"][split]
    answers = answers.tolist() if hasattr(answers, "tolist") else answers
    if len(answers) != len(identifiers):
        raise ValueError("실제 풀이 행과 생성 대상 ID 수가 다릅니다.")
    actual = dict(zip(identifiers, answers))
    plan = []
    for position, identifier in enumerate(identifiers):
        meta = data["records"][identifier]
        problem = (root / f"data/processed/problems/{identifier}.txt").read_text(encoding="utf-8-sig")
        solution = (root / f"data/processed/solutions/{identifier}.txt").read_text(encoding="utf-8-sig")
        arms = {}
        for condition in "ABCD":
            hint_text, hint = "", None
            if condition != "A":
                vector = (predictions["regression"][identifier] if condition == "B" else
                          predictions["deep_learning"][identifier] if condition == "C" else actual[identifier])
                hint_text, hint = serialize_vector(vocabulary, vector, condition)
            text = problem + hint_text
            snapshot = comparison.request_snapshot(comparison.sdk_request_arguments(SETTINGS, text))
            arms[condition] = {"id": identifier, "condition": condition, "method": METHODS[condition],
                "split": split, "problem_text": problem, "reference_solution": solution,
                "reference_answer_text": meta["answer_text"], "reference": extract_reference(meta, problem),
                **{key: meta.get(key) for key in ("subject", "curriculum", "unit", "subunit", "type", "source")},
                "input_text": text, "input_sha256": comparison.digest(text),
                "system_instruction": comparison.DEFAULT_SYSTEM, "hint": hint,
                "request_sha256": comparison.digest(snapshot), "compact_storage": True,
                "uses_test_reference_vector": condition == "D" and split == "test"}
        plan.extend(arms[condition] for condition in ORDERS[position % len(ORDERS)])
    config = {"schema_version": 4, **SETTINGS, "max_attempts": 2,
        "dataset_id": data["dataset_id"], "generation_id": data["dataset_id"],
        "models": models, "split": split, "test_ids": identifiers, "train_ids": data["ids"]["train"],
        "original_test_ids": data["ids"]["test"], "methods": list(METHODS.values()),
        "conditions": METHODS, "compact_storage": True,
        "solution_vocabulary_sha256": comparison.digest(vocabulary),
        "data_identity_sha256": comparison.digest(data.get("identity", {"dataset_id": data["dataset_id"]})),
        "condition_order": "24_permutations_rotated_by_document_index; exact successes skipped",
        "old_condition_mapping": "old C actual-reference oracle is new D; new C is nonlinear MLP",
        "oracle_caveat": "D uses actual reference-token frequencies, privileged diagnostic information, not a service prediction or guaranteed upper bound.",
        "grading": "deterministic original-reference final answer; solution validity reviewed separately",
        "grader_sha256": comparison.file_hash(Path(comparison.__file__).with_name("AnswerEvaluation.py")),
        "inputs": [{"id": row["id"], "condition": row["condition"], "request_sha256": row["request_sha256"]} for row in plan]}
    return config, plan


def initialize(output, config, plan):
    output = Path(output)
    config_id = comparison.initialize_run(output, config, plan)
    path = output / "plan.jsonl"
    if path.exists():
        if read_jsonl(path) != plan:
            raise ValueError("저장된 준비 입력이 새 계획과 다릅니다. 기존 응답을 섞지 않습니다.")
    else:
        for row in plan:
            append_jsonl(path, row)
    return config_id


def dry_run(root, output, config, plan, *, write=True):
    """공통 make_request의 실제 SDK 경계를 모의 클라이언트로 관찰한다."""
    output = Path(output)
    calls = 0
    for item in plan:
        snapshot = comparison.request_snapshot(comparison.sdk_request_arguments(config, item["input_text"]))
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
                return SimpleNamespace(text="offline dry run")
        request = comparison.make_request(config, "NO_LIVE_CREDENTIAL", client_factory=FakeClient)
        request(item["input_text"])
        calls += 1
        if captured != [snapshot] or comparison.digest(snapshot) != item["request_sha256"]:
            raise ValueError("감사 입력과 SDK에 전달할 인자가 다릅니다.")
        if not item["input_text"].startswith(item["problem_text"]):
            raise ValueError("문제 원문이 완전히 보존되지 않았습니다.")
        if item["condition"] == "A" and item["input_text"] != item["problem_text"]:
            raise ValueError("A 조건에 힌트가 들어갔습니다.")
        record = {"id": item["id"], "condition": item["condition"], "method": item["method"],
            "split": item["split"], "requested_model": config["model"],
            "system_instruction": item["system_instruction"], "user_message": item["input_text"],
            "problem_text": item["problem_text"], "hint": item["hint"],
            "full_request_text": "[SYSTEM]\n" + item["system_instruction"] + "\n[USER]\n" + item["input_text"],
            "sdk_request": snapshot, "sdk_request_sha256": item["request_sha256"],
            "request_sha256": item["request_sha256"], "input_sha256": item["input_sha256"],
            "dataset_id": config["dataset_id"], "models": config["models"],
            "solution_vocabulary_sha256": config["solution_vocabulary_sha256"],
            "data_identity_sha256": config["data_identity_sha256"],
            "verification": {"mocked_sdk_arguments_match_saved": True, "raw_problem_unchanged": True,
                             "new_live_api_calls": 0},
            "sources": {"problem": f"data/processed/problems/{item['id']}.txt",
                        "vector_source": "actual reference only for D" if item["condition"] == "D" else
                          config["models"]["regression" if item["condition"] == "B" else "deep_learning"]["predictions"] if item["condition"] in "BC" else None}}
        path = output / "prompt_audit/requests" / item["id"] / (item["condition"] + ".json")
        if path.exists():
            if read_json(path) != record:
                raise ValueError(f"저장된 요청 감사가 달라졌습니다: {path}")
        elif write:
            write_json(path, record)
        else:
            raise FileNotFoundError(path)
    result = {"mocked_sdk_calls": calls, "live_generation_calls": 0,
              "requests": len(plan), "all_sdk_arguments_match": True,
              "system_is_exact_legacy_default": config["system_instruction"] == comparison.DEFAULT_SYSTEM,
              "oracle_condition": "D; previous experiment C", "model_freeze_gate": "both manifests checked before plan"}
    if write:
        write_json(output / "prompt_audit/dry_run.json", result)
    return result


def reuse_existing(root, output, config, plan):
    """기존 응답의 SDK 요청 전문 해시가 같은 성공만 가져온다."""
    root, output = Path(root), Path(output)
    current_id = comparison.digest(config)
    completed = comparison.load_completed(output, current_id)
    source = root / "results/final_experiment/03_gemini"
    old_wrapper = read_json(source / "config.json")
    old_config = old_wrapper["config"]
    if comparison.digest(old_config) != old_wrapper["config_id"]:
        raise ValueError("과거 API 설정의 해시가 다릅니다.")
    for field in SETTINGS:
        if old_config[field] != config[field]:
            return {"imported": 0, "reason": "historical generation setting differs: " + field}
    index = {}
    for row in read_jsonl(source / "responses.jsonl"):
        if row["status"] != "success" or row["config_id"] != old_wrapper["config_id"]:
            continue
        if row["input_sha256"] != comparison.digest(row["input_text"]):
            raise ValueError("과거 성공 입력의 해시가 다릅니다.")
        old_condition = row.get("condition") or {"baseline": "A", "regression_hint": "B", "oracle_hint": "C"}[row["method"]]
        audit_path = source / "prompt_audit/requests" / row["id"] / (old_condition + ".json")
        if not audit_path.is_file():
            continue
        saved_audit = read_json(audit_path)
        snapshot = saved_audit["sdk_request"]
        request_hash = comparison.digest(snapshot)
        if (saved_audit["sdk_request_sha256"] != request_hash
                or snapshot["contents"] != row["input_text"]
                or snapshot["model"] != old_config["model"]):
            raise ValueError("과거 저장 요청 전문 또는 SDK 해시가 응답의 입력과 다릅니다.")
        index[request_hash] = row, audit_path, saved_audit
    imports = []
    for item in plan:
        key = item["id"], item["method"]
        if completed.get(key, {}).get("status") == "success":
            continue
        candidate = index.get(item["request_sha256"])
        if candidate is None:
            continue
        previous, audit_path, saved_audit = candidate
        if previous["id"] != item["id"]:
            continue
        if any(previous.get(field) != item.get(field) for field in
               ("problem_text", "input_text", "system_instruction", "reference", "reference_answer_text", "reference_solution")):
            raise ValueError("과거 SDK 요청은 같지만 문항 또는 원본 정답 대응이 다릅니다.")
        transfer = {field: previous.get(field) for field in ("status", "output_text", "usage", "raw_response",
                    "model_version", "response_id", "finish_reasons", "prompt_feedback", "latency_seconds",
                    "started_at", "completed_at", "evaluation")}
        imported = {**item, **transfer, "config_id": current_id, "attempts": [],
            "model": config["model"], "thinking_level": config["thinking_level"],
            "solution_review": {"status": "pending_review", "mathematical_validity": None,
                                "reason": "동일 요청의 답/응답은 재사용했지만 풀이 타당성은 별도로 검토한다."},
            "response_origin": "reused_exact_request", "source_provenance": {
                "records": str((source / "responses.jsonl").relative_to(root)),
                "records_sha256": comparison.file_hash(source / "responses.jsonl"),
                "source_config_id": old_wrapper["config_id"], "source_record_sha256": comparison.digest(previous),
                "source_condition": previous.get("condition"), "imported_at": comparison.utc_now(),
                "request_audit": str(audit_path.relative_to(root)),
                "request_audit_sha256": comparison.file_hash(audit_path),
                "historical_capture_note": saved_audit.get("historical_capture_note"),
                "source_completed_at": previous.get("completed_at"), "request_match": "exact SDK arguments including all generation settings and hint"}}
        comparison.save_result(output, imported)
        completed[key] = imported
        imports.append({"id": item["id"], "condition": item["condition"]})
    return {"imported": len(imports), "requests": imports,
            "note": "Old oracle C can map to new D only if the full actual SDK request is identical."}
