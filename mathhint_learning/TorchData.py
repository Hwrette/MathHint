"""저장된 학습·테스트 ID와 빈도 벡터를 읽는다. 데이터 검사는 여기서만 한다."""

import json
from pathlib import Path

import torch


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_fixed_dataset(root):
    """한 행은 문항, 한 열은 어휘다. 원래 학습·테스트 분할을 그대로 읽는다."""
    root = Path(root)
    metadata = read_json(root / "data/processed/metadata.json")
    ids = {part: read_json(root / f"data/processed/splits/{part}.json") for part in ("train", "test")}
    if any(len(values) != len(set(values)) for values in ids.values()):
        raise ValueError("문항 ID가 중복됩니다.")
    if set(ids["train"]) & set(ids["test"]):
        raise ValueError("학습·테스트 문항이 겹칩니다 (overlap).")
    records = {record["id"]: record for record in metadata["records"]}
    if set(records) != set(ids["train"] + ids["test"]):
        raise ValueError("메타데이터와 분할 목록의 문항 ID가 다릅니다.")

    arrays, vocabularies = {}, {}
    for region in ("problems", "solutions"):
        folder = root / "data/vectors" / region
        vocabulary = read_json(folder / "vocabulary.json")
        vocabularies[region] = vocabulary
        arrays[region] = {}
        for part in ("train", "test"):
            data = read_json(folder / f"{part}_vectors.json")
            documents = data["documents"]
            if data["generation_id"] != metadata["generation_id"]:
                raise ValueError("서로 다른 데이터 버전입니다 (generation IDs).")
            if data["vocabulary_fitted_on"] != "train":
                raise ValueError("어휘는 학습 자료에서만 만들어야 합니다 (training data only).")
            if [document["id"] for document in documents] != ids[part]:
                raise ValueError(f"{region}/{part}: 문항 행 순서가 다릅니다 (ID order).")
            matrix = torch.tensor([document["vector"] for document in documents], dtype=torch.float32)
            if list(matrix.shape) != [len(ids[part]), len(vocabulary)]:
                raise ValueError(f"{region}/{part}: 문항 수·어휘 수와 벡터 차원이 다릅니다.")
            arrays[region][part] = matrix

    return {
        "ids": ids, "records": records, "arrays": arrays,
        "vocabularies": vocabularies, "generation_id": metadata["generation_id"],
    }
