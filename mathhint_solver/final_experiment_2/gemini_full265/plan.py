"""같은 확정 모델·요청 전문으로1060개 계획을 만들고 기존320성공을 검증해 재사용한다."""

from pathlib import Path

from ... import CompareGeneration as comparison
from ..gemini_comparison.plan import (prepare_plan as split_plan, initialize, dry_run,
    model_gate, serialize_vector, SETTINGS, MODEL)
from .common import read_json, read_jsonl, write_json, source_output


def prepare_plan(root, data, *, split="all"):
    if split != "all":
        raise ValueError("새 비교의 범위는 all265입니다. 원래 split 정보는 각 행에 유지합니다.")
    root = Path(root).resolve()
    test_config, test = split_plan(root, data, split="test")
    train_config, train = split_plan(root, data, split="train")
    for field in ("models", "dataset_id", "solution_vocabulary_sha256", "data_identity_sha256"):
        if test_config[field] != train_config[field]:
            raise ValueError(f"학습/테스트 계획의 확정 자료가 다릅니다: {field}")
    identifiers = data["ids"]["test"] + data["ids"]["train"]
    if len(identifiers) != 265 or len(set(identifiers)) != 265:
        raise ValueError("전체265 고유 문항이 필요합니다.")
    plan = test + train
    if len(plan) != 1060 or {(row["id"], row["condition"]) for row in plan} != {(i, c) for i in identifiers for c in "ABCD"}:
        raise ValueError("전체265×4 요청이 누락 또는 중복되었습니다.")
    old = source_output(root)
    source = {"path": str(old.relative_to(root)),
        "config_sha256": comparison.file_hash(old / "config.json"),
        "records_sha256": comparison.file_hash(old / "responses.jsonl"),
        "curated_reviews_sha256": comparison.file_hash(old / "review/curated_reviews.json")}
    config = {**test_config, "schema_version": 5, "split": "all",
        "experiment_id": "final_experiment_2_gemini_full265", "experiment_scope": "full265",
        "target_ids": identifiers, "test_ids": data["ids"]["test"], "train_ids": data["ids"]["train"],
        "original_test_ids": data["ids"]["test"], "original_train_ids": data["ids"]["train"],
        "explicit_user_authorization": "Run A/B/C/D for all265 in a separate folder; reuse matching test80 responses; additional train185 generation authorized even though provider remaining quota is not exposed.",
        "training_scope_note": "train185 B/C predictions use data used to fit model weights; in-sample analysis, not generalization performance",
        "reused_experiment": source,
        "inputs": [{"id": row["id"], "condition": row["condition"], "request_sha256": row["request_sha256"]} for row in plan]}
    return config, plan


def reuse_existing(root, output, config, plan):
    root, output = Path(root).resolve(), Path(output)
    old = source_output(root)
    wrapped = read_json(old / "config.json")
    old_config = wrapped["config"]
    if comparison.digest(old_config) != wrapped["config_id"]:
        raise ValueError("기존80의 설정 해시가 다릅니다.")
    for field in SETTINGS:
        if old_config[field] != config[field]:
            raise ValueError(f"기존80과 생성 설정이 다릅니다: {field}")
    current_id = comparison.digest(config)
    current = comparison.load_completed(output, current_id)
    source_rows = comparison.load_completed(old, wrapped["config_id"])
    index = {}
    for row in source_rows.values():
        if row["status"] != "success":
            continue
        audit_path = old / f"prompt_audit/requests/{row['id']}/{row['condition']}.json"
        audit = read_json(audit_path)
        snapshot = audit["sdk_request"]
        request_sha = comparison.digest(snapshot)
        if request_sha != audit["request_sha256"] or request_sha != row["request_sha256"]:
            raise ValueError("기존 성공과 SDK 요청 전문의 해시가 다릅니다.")
        if snapshot["contents"] != row["input_text"] or row["input_sha256"] != comparison.digest(row["input_text"]):
            raise ValueError("기존 성공 요청 내용이 손상되었습니다.")
        index[(row["id"], row["condition"], request_sha)] = row, audit_path
    imported = []
    for item in plan:
        key = item["id"], item["method"]
        if current.get(key, {}).get("status") == "success":
            continue
        candidate = index.get((item["id"], item["condition"], item["request_sha256"]))
        if candidate is None:
            continue
        previous, audit_path = candidate
        for field in ("problem_text", "input_text", "system_instruction", "reference", "reference_answer_text", "reference_solution", "hint", "split"):
            if previous.get(field) != item.get(field):
                raise ValueError(f"기존 요청의 문항·정답·힌트가 새 계획과 다릅니다: {item['id']}/{field}")
        snapshot = comparison.request_snapshot(comparison.sdk_request_arguments(config, item["input_text"]))
        if comparison.digest(snapshot) != item["request_sha256"]:
            raise ValueError("새 SDK 요청이 재사용 원본과 다릅니다.")
        row = {**previous, **item, "config_id": current_id,
            "response_origin": "reused_exact_request",
            "source_provenance": {"records": str((old / "responses.jsonl").relative_to(root)),
                "records_sha256": comparison.file_hash(old / "responses.jsonl"),
                "source_config_id": wrapped["config_id"], "source_record_sha256": comparison.digest(previous),
                "source_condition": previous["condition"], "imported_at": comparison.utc_now(),
                "request_audit": str(audit_path.relative_to(root)),
                "request_audit_sha256": comparison.file_hash(audit_path),
                "source_completed_at": previous.get("completed_at"),
                "request_match": "exact SDK arguments including all generation settings and hint",
                "prior_provenance": previous.get("source_provenance")}}
        comparison.save_result(output, row)
        current[key] = row
        imported.append({"id": item["id"], "condition": item["condition"]})
    review_path = output / "review/curated_reviews.json"
    saved = read_json(review_path) if review_path.exists() else {"records": []}
    reviews = {(row["id"], row["condition"]): row for row in saved["records"]}
    for review in read_json(old / "review/curated_reviews.json")["records"]:
        record = current.get((review["id"], config["conditions"][review["condition"]]))
        if not record or record["status"] != "success":
            continue
        import hashlib
        text = record["output_text"]
        if review["response_sha256"] != hashlib.sha256(text.encode()).hexdigest() or any(q not in text for q in review["evidence_quotes"]):
            raise ValueError("기존 AI 검토의 응답 해시 또는 인용이 다릅니다.")
        key = review["id"], review["condition"]
        if key in reviews and reviews[key] != review:
            raise ValueError("이미 저장한 직접 검토를 기존 검토로 덮어쓰지 않습니다.")
        reviews[key] = review
    if not review_path.exists() or saved["records"] != list(reviews.values()):
        write_json(review_path, {**saved, "records": list(reviews.values())})
    return {"imported": len(imported), "requests": imported,
        "review_records": len(reviews), "source_path": str(old.relative_to(root)),
        "note": "Only exact successful SDK requests reused; original outputs/usage/times/grades and separately hash-bound AI reviews preserved."}
