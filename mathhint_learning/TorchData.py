"""고정 분할·어휘·빈도 벡터를 한곳에서 읽고 데이터의 정확한 신원을 확인한다."""

import hashlib
import json
import math
from pathlib import Path


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def identity_digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def dataset_paths(root, data_root=None):
    base = Path(data_root).resolve() if data_root is not None else Path(root).resolve() / "data"
    paths = {"metadata": base / "processed/metadata.json"}
    paths.update({f"{part}_ids": base / f"processed/splits/{part}.json" for part in ("train", "test")})
    for region in ("problems", "solutions"):
        paths[f"{region}_vocabulary"] = base / f"vectors/{region}/vocabulary.json"
        paths.update({f"{region}_{part}": base / f"vectors/{region}/{part}_vectors.json" for part in ("train", "test")})
    return base, paths


def read_dataset(root, data_root=None):
    """텐서나 모델 없이도 ID·정수 빈도·학습 어휘를 검증한다."""
    base, paths = dataset_paths(root, data_root)
    metadata = read_json(paths["metadata"])
    if not isinstance(metadata.get("generation_id"), str) or not metadata["generation_id"]:
        raise ValueError(f"{paths['metadata']}: 비어 있지 않은 generation_id가 필요합니다.")
    ids = {part: read_json(paths[f"{part}_ids"]) for part in ("train", "test")}
    for part, values in ids.items():
        if not isinstance(values, list) or not values or any(not isinstance(v, str) for v in values) or len(values) != len(set(values)):
            raise ValueError(f"{paths[part + '_ids']}: 문항 ID 목록이 비었거나 중복됩니다.")
    if set(ids["train"]) & set(ids["test"]):
        raise ValueError(f"{paths['train_ids']} / {paths['test_ids']}: 학습·테스트 문항이 겹칩니다 (overlap).")
    records = {record["id"]: record for record in metadata["records"]}
    if len(records) != len(metadata["records"]) or set(records) != set(ids["train"] + ids["test"]):
        raise ValueError(f"{paths['metadata']}: 메타데이터와 분할 목록의 문항 ID가 다릅니다.")
    arrays, vocabularies = {}, {}
    for region in ("problems", "solutions"):
        vocabulary = read_json(paths[f"{region}_vocabulary"])
        if (not isinstance(vocabulary, list) or not vocabulary
                or any(not isinstance(v, str) or not v for v in vocabulary)
                or len(vocabulary) != len(set(vocabulary))):
            raise ValueError(f"{paths[region + '_vocabulary']}: 어휘는 중복 없는 문자열 목록이어야 합니다.")
        vocabularies[region] = vocabulary
        arrays[region] = {}
        for part in ("train", "test"):
            path = paths[f"{region}_{part}"]
            data = read_json(path)
            if data["generation_id"] != metadata["generation_id"]:
                raise ValueError(f"{path}: 서로 다른 데이터 버전입니다 (generation IDs).")
            if data["vocabulary_fitted_on"] != "train":
                raise ValueError(f"{path}: 어휘는 학습 자료에서만 만들어야 합니다 (training data only).")
            documents = data["documents"]
            if [document["id"] for document in documents] != ids[part]:
                raise ValueError(f"{path}: 문항 행 순서가 다릅니다 (ID order).")
            values = [document["vector"] for document in documents]
            if any(not isinstance(row, list) or len(row) != len(vocabulary) for row in values):
                raise ValueError(f"{path}: 문항 수·어휘 수와 벡터 차원이 다릅니다.")
            if any(type(value) not in (int, float) or not math.isfinite(value)
                   or value < 0 or value != int(value) for row in values for value in row):
                raise ValueError(f"{path}: 실제 빈도는 유한한 음이 아닌 정수여야 합니다.")
            arrays[region][part] = values
    identity = {"schema_version": 1, "generation_id": metadata["generation_id"],
                "files_sha256": {key: file_hash(path) for key, path in paths.items()}}
    identity["fingerprint"] = identity_digest(identity)
    return {"ids": ids, "records": records, "arrays": arrays, "vocabularies": vocabularies,
            "generation_id": metadata["generation_id"], "identity": identity, "data_root": base, "paths": paths}


def load_fixed_dataset(root, data_root=None):
    """기존 호출과 호환하며 선택한 데이터 위치의 원래 분할을 그대로 읽는다."""
    import torch
    data = read_dataset(root, data_root)
    data["arrays"] = {region: {part: torch.tensor(values, dtype=torch.float32)
                               for part, values in splits.items()} for region, splits in data["arrays"].items()}
    return data
