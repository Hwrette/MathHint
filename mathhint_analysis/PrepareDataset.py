"""HML 문항의 ID를 보존해 분할하고 학습 어휘로 문제·해설 빈도벡터를 만든다.

실행: python -m mathhint_analysis.PrepareDataset
확인용 annotated/에는 분류·출처를 남기지만, 벡터화에는 clean 본문만 사용한다.
문제와 원본 해설은 서로 다른 어휘를 사용하며 각 영역의 학습·테스트는 같은
어휘 순서를 사용한다. Gemini·임베딩·군집화 모델은 호출하지 않는다.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from collections.abc import Callable
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import shutil
import tempfile
import unicodedata
import uuid


ROOT = Path(__file__).resolve().parents[1]
TYPE_FIELDS = ("subject", "curriculum", "unit", "subunit", "type")
REGIONS = {"problems": "problem_text", "solutions": "solution_text"}


def _normalized(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text)).strip()


def _type_key(record: dict) -> tuple[str, ...]:
    return tuple(record[field] for field in TYPE_FIELDS)


def validate_records(records: list[dict], *, strict: bool = True) -> None:
    """누락·중복 ID와 분류 없는 문항을 벡터화 전에 거부한다."""
    if not records:
        raise ValueError("추출된 문항이 없습니다.")
    seen = set()
    warnings = []
    for record in records:
        question_id = record.get("id")
        subject_code = {"미분": "diff", "삼각함수": "trig"}.get(record.get("subject"))
        if subject_code is None:
            raise ValueError(f"지원하지 않는 자료군: {record.get('subject')!r}")
        if not isinstance(record.get("file_number"), int) or record["file_number"] < 1:
            raise ValueError(f"파일 번호가 없습니다: {question_id}")
        for field in ("original_number", "current_number"):
            if not isinstance(record.get(field), int) or record[field] < 1:
                raise ValueError(f"{field}가 없습니다: {question_id}")
        expected = f"{subject_code}_{record['file_number']}_{record['original_number']:03d}"
        if question_id != expected or question_id in seen:
            raise ValueError(f"문항 ID가 원래 번호와 다르거나 중복됩니다: {question_id!r}")
        seen.add(question_id)
        for field in (*TYPE_FIELDS, "source", "problem_text", "solution_text", "answer_text"):
            if not isinstance(record.get(field), str) or not record[field].strip():
                raise ValueError(f"{question_id}: {field}가 비어 있습니다.")
        if record.get("has_body_graphic"):
            raise ValueError(f"문제 본문에 그래프·그림이 남아 있습니다: {question_id}")
        if record.get("warnings"):
            warnings.append(question_id)
    if strict and warnings:
        raise ValueError("수식/문항 변환 검토가 필요합니다: " + ", ".join(warnings))


def _duplicate_groups(records: list[dict]) -> list[dict]:
    """동일 출처 또는 공백만 다른 동일 본문을 하나의 분할 그룹으로 묶는다."""
    parent = list(range(len(records)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a: int, b: int) -> None:
        parent[find(a)] = find(b)

    for field in ("source", "problem_text"):
        first = {}
        for i, record in enumerate(records):
            value = _normalized(record[field])
            if value in first:
                union(i, first[value])
            else:
                first[value] = i
    members = defaultdict(list)
    for i, record in enumerate(records):
        members[find(i)].append(record)
    result = []
    for group in members.values():
        keys = {_type_key(record) for record in group}
        if len(keys) != 1:
            raise ValueError("동일 출처/본문의 분류가 서로 다릅니다: " + ", ".join(r["id"] for r in group))
        ids = sorted(record["id"] for record in group)
        result.append({"group_id": ids[0], "ids": ids, "size": len(ids), "type_key": next(iter(keys))})
    return sorted(result, key=lambda group: group["group_id"])


def _subset_options(groups: list[dict], rng: random.Random) -> dict[int, tuple[str, ...]]:
    """유형 안에서 중복 그룹을 쪼개지 않는 가능한 테스트 문항 수를 구한다."""
    if len(groups) == 1:
        return {0: ()}  # 한 문항/분리 불가 중복 그룹은 학습에 둔다.
    shuffled = list(groups)
    rng.shuffle(shuffled)
    choices = {0: ()}
    for group in shuffled:
        for total, selected in list(choices.items()):
            choices.setdefault(total + group["size"], (*selected, group["group_id"]))
    n = sum(group["size"] for group in groups)
    return {total: selected for total, selected in sorted(choices.items()) if 0 < total < n}


def split_records(records: list[dict], *, test_fraction: float = 0.3, seed: int = 42) -> dict:
    """단원별 목표에 가깝게 나누되, 분리 가능한 유형은 양쪽에 최소 1개 둔다.

    동일 유형이 한 그룹뿐이면 학습에 둔다. 각 유형의 가능한 그룹 조합을
    먼저 구한 뒤 단원별 동적 계획법으로 목표 테스트 수에 가장 가까운 합을
    선택한다. 같은 합에서는 유형별 목표 문항 수의 제곱 오차를 최소화한다.
    """
    if not math.isfinite(test_fraction) or not 0 < test_fraction < 1:
        raise ValueError("test_fraction은 0과 1 사이여야 합니다.")
    ordered = sorted(records, key=lambda record: record["id"])
    validate_records(ordered, strict=False)
    groups = _duplicate_groups(ordered)
    rng = random.Random(seed)
    by_type = defaultdict(list)
    for group in groups:
        by_type[group["type_key"]].append(group)
    by_unit = defaultdict(list)
    for type_key in sorted(by_type):
        by_unit[type_key[:3]].append(type_key)
    test_groups = set()
    units = []
    types = []
    for unit_key, type_keys in sorted(by_unit.items()):
        total = sum(group["size"] for key in type_keys for group in by_type[key])
        target = int(math.floor(total * test_fraction + 0.5))
        states = {0: (0.0, {})}
        for key in type_keys:
            size = sum(group["size"] for group in by_type[key])
            options = _subset_options(by_type[key], rng)
            updated = {}
            for old_total, (cost, selection) in states.items():
                for n_test, subset in options.items():
                    new_total = old_total + n_test
                    new_cost = cost + (n_test - size * test_fraction) ** 2
                    if new_total not in updated or new_cost < updated[new_total][0] - 1e-12:
                        updated[new_total] = (new_cost, {**selection, key: (n_test, subset)})
            states = updated
        actual = min(states, key=lambda n: (abs(n - target), states[n][0], n))
        selection = states[actual][1]
        for key, (n_test, subset) in selection.items():
            test_groups.update(subset)
            size = sum(group["size"] for group in by_type[key])
            reason = None
            if len(by_type[key]) == 1:
                reason = "single_question" if size == 1 else "inseparable_duplicate_group"
            types.append({**dict(zip(TYPE_FIELDS, key)), "total": size,
                          "train": size - n_test, "test": n_test,
                          "forced_train_reason": reason})
        units.append({**dict(zip(TYPE_FIELDS[:3], unit_key)), "total": total,
                      "target_test": target, "actual_test": actual,
                      "train": total - actual, "target_deviation": actual - target})
    test_ids = sorted(question_id for group in groups if group["group_id"] in test_groups for question_id in group["ids"])
    train_ids = sorted({record["id"] for record in ordered} - set(test_ids))
    assert not set(train_ids) & set(test_ids)
    assert set(train_ids) | set(test_ids) == {record["id"] for record in records}
    return {"seed": seed, "test_fraction_requested": test_fraction,
            "method": "unit_target_then_type_coverage_and_squared_count_error",
            "train_ids": train_ids, "test_ids": test_ids, "units": units, "types": types,
            "duplicate_groups": [group["ids"] for group in groups if group["size"] > 1]}


def _json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _publish_pair(pairs: list[tuple[Path, Path]], *, overwrite: bool) -> None:
    """두 결과 폴더를 교체하고 실패하면 기존 두 폴더를 함께 복구한다."""
    backups = {}
    published = []
    try:
        for _, destination in pairs:
            if destination.exists():
                if not overwrite:
                    raise ValueError(f"기존 결과는 덮어쓰지 않습니다: {destination}")
                backup = destination.with_name(f".{destination.name}.backup-{uuid.uuid4().hex}")
                destination.rename(backup)
                backups[destination] = backup
        for stage, destination in pairs:
            stage.rename(destination)
            published.append(destination)
    except BaseException:
        for destination in reversed(published):
            shutil.rmtree(destination)
        for destination, backup in backups.items():
            backup.rename(destination)
        raise
    else:
        for backup in backups.values():
            shutil.rmtree(backup)


def _count_function() -> Callable[[str], Counter]:
    # Keep this optional dependency lazy so split/integrity checks need no Kiwi.
    from .BagOfWord import Kiwi, count_tokens
    from importlib.metadata import version
    kiwi = Kiwi(num_workers=2)
    def count(text):
        return count_tokens(text, kiwi)
    count.tokenizer_info = {"package": "kiwipiepy", "version": version("kiwipiepy"),
                            "model_package_version": version("kiwipiepy_model"),
                            "num_workers": 2}
    return count


def _vectors(records: dict[str, dict], ids: list[str], counts: dict[str, Counter],
             vocabulary: list[str], split: str, region: str, input_folder: str) -> dict:
    index = {token: i for i, token in enumerate(vocabulary)}
    documents = []
    for question_id in ids:
        counter = counts[question_id]
        vector = [0] * len(vocabulary)
        ignored = 0
        for token, count in counter.items():
            if token in index:
                vector[index[token]] = count
            else:
                ignored += count
        documents.append({"id": question_id, "file": question_id + ".txt", "vector": vector,
                          "token_count": sum(counter.values()), "ignored_token_count": ignored})
    return {"schema_version": 1, "region": region, "split": split,
            "vocabulary_file": "vocabulary.json", "vocabulary_fitted_on": "train",
            "input_folder": input_folder, "input_folder_base": "this_json_directory",
            "shape": [len(ids), len(vocabulary)],
            "documents": documents}


def prepare_records(records: list[dict], output_dir: str | Path, vectors_dir: str | Path,
                    *, test_fraction: float = 0.3, seed: int = 42,
                    count_fn: Callable[[str], Counter] | None = None,
                    strict: bool = True, overwrite: bool = False,
                    source_files: list[dict] | None = None) -> dict:
    """문항 파일·분류·분할·문제/해설 벡터를 같은 ID로 저장한다."""
    validate_records(records, strict=strict)
    output_dir, vectors_dir = Path(output_dir).resolve(), Path(vectors_dir).resolve()
    if output_dir == vectors_dir or output_dir in vectors_dir.parents or vectors_dir in output_dir.parents:
        raise ValueError("전처리 결과와 벡터 결과 폴더는 서로 겹치면 안 됩니다.")
    for destination in (output_dir, vectors_dir):
        if destination.exists() and not overwrite:
            raise ValueError(f"기존 결과는 덮어쓰지 않습니다: {destination} (--overwrite로 명시)")
        destination.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(records, key=lambda record: record["id"])
    by_id = {record["id"]: record for record in ordered}
    split = split_records(ordered, test_fraction=test_fraction, seed=seed)
    if not split["train_ids"] or not split["test_ids"]:
        raise ValueError("학습·테스트 중 하나가 비었습니다. 유형당 독립 문항을 확보해 주세요.")
    count_fn = count_fn or _count_function()
    tokenizer_info = getattr(count_fn, "tokenizer_info", {"package": "injected_count_function"})
    vector_data = {}
    for region, field in REGIONS.items():
        counts = {record["id"]: Counter(count_fn(record[field])) for record in ordered}
        for question_id, counter in counts.items():
            if any(not isinstance(t, str) or not isinstance(n, int) or isinstance(n, bool) or n < 0
                   for t, n in counter.items()):
                raise ValueError(f"올바르지 않은 토큰 빈도: {region}/{question_id}")
        vocabulary = sorted({token for question_id in split["train_ids"] for token, count in counts[question_id].items() if count})
        if not vocabulary:
            raise ValueError(f"학습 어휘가 비었습니다: {region}")
        vector_data[region] = {"vocabulary": vocabulary}
        for part in ("train", "test"):
            ids = split[part + "_ids"]
            vector_data[region][part] = _vectors(by_id, ids, counts, vocabulary, part, region,
                                                  Path(os.path.relpath(output_dir / region, vectors_dir / region)).as_posix())
    fingerprint = {"seed": seed, "test_fraction": test_fraction, "tokenizer": tokenizer_info,
                   "records": [{"id": r["id"], "type_path": _type_key(r), "source": r["source"],
                                "problem_text": r["problem_text"], "solution_text": r["solution_text"]}
                               for r in ordered],
                   "vectors": {region: {"vocabulary": data["vocabulary"],
                                        "train": data["train"]["documents"], "test": data["test"]["documents"]}
                               for region, data in vector_data.items()}}
    generation_id = hashlib.sha256(json.dumps(fingerprint, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    for data in vector_data.values():
        for part in ("train", "test"):
            data[part]["generation_id"] = generation_id
    metadata = []
    for record in ordered:
        question_id = record["id"]
        metadata.append({**{key: value for key, value in record.items()
                            if key not in ("problem_text", "solution_text")},
                         "split": "train" if question_id in set(split["train_ids"]) else "test",
                         "annotated_file": f"annotated/{question_id}.txt",
                         "problem_file": f"problems/{question_id}.txt",
                         "solution_file": f"solutions/{question_id}.txt"})
    report = {"schema_version": 1, "generation_id": generation_id, "question_count": len(records),
              "tokenizer": tokenizer_info,
              "train_count": len(split["train_ids"]), "test_count": len(split["test_ids"]),
              "test_fraction_actual": len(split["test_ids"]) / len(records),
              "type_count": len(split["types"]), "seed": seed,
              "conversion_warning_ids": [record["id"] for record in ordered if record.get("warnings")],
              "source_files": source_files or [],
              "vector_dimensions": {region: len(data["vocabulary"]) for region, data in vector_data.items()},
              "test_ignored_token_counts": {region: sum(doc["ignored_token_count"] for doc in data["test"]["documents"])
                                            for region, data in vector_data.items()},
              "checks": {"all_ids_unique": True, "train_test_disjoint": True,
                         "paired_problem_solution_ids_and_row_order": True,
                         "duplicate_groups_do_not_cross_splits": True,
                         "vocabulary_fitted_on_train_only": True,
                         "metadata_excluded_from_vector_inputs": True}}
    for part in ("train", "test"):
        for region in REGIONS:
            assert [doc["id"] for doc in vector_data[region][part]["documents"]] == split[part + "_ids"]
    staging = Path(tempfile.mkdtemp(prefix=".dataset-", dir=output_dir.parent))
    vector_stage = Path(tempfile.mkdtemp(prefix=".vectors-", dir=vectors_dir.parent))
    try:
        for folder in ("annotated", "problems", "solutions", "splits"):
            (staging / folder).mkdir()
        for record in ordered:
            question_id = record["id"]
            text = (f"[문항 ID] {question_id}\n[자료군] {record['subject']}\n"
                    f"[파일 번호] {record['file_number']}\n[원래 문제 번호] {record['original_number']}\n"
                    f"[현재 문제 번호] {record['current_number']}\n[과목] {record['curriculum']}\n"
                    f"[단원] {record['unit']}\n[세부 단원] {record['subunit']}\n"
                    f"[유형] {record['type']}\n[출처] {record['source']}\n\n"
                    f"[문제]\n{record['problem_text'].strip()}\n\n"
                    f"[원본 정답·해설]\n{record['solution_text'].strip()}\n")
            (staging / "annotated" / f"{question_id}.txt").write_text(text, encoding="utf-8")
            for region, field in REGIONS.items():
                (staging / region / f"{question_id}.txt").write_text(record[field].strip() + "\n", encoding="utf-8")
        _json(staging / "metadata.json", {"schema_version": 1, "generation_id": generation_id, "records": metadata})
        _json(staging / "splits" / "train.json", split["train_ids"])
        _json(staging / "splits" / "test.json", split["test_ids"])
        _json(staging / "splits" / "report.json", {"generation_id": generation_id,
              **{key: value for key, value in split.items() if not key.endswith("_ids")}})
        _json(staging / "report.json", report)
        hashes = {path.relative_to(staging).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in sorted(staging.rglob("*")) if path.is_file()}
        _json(staging / "manifest.json", {"schema_version": 1, "generation_id": generation_id, "question_ids": sorted(by_id),
                                         "files_sha256": hashes})
        for region, data in vector_data.items():
            folder = vector_stage / region
            folder.mkdir()
            _json(folder / "vocabulary.json", data["vocabulary"])
            for part in ("train", "test"):
                _json(folder / f"{part}_vectors.json", data[part])
        _json(vector_stage / "report.json", {"schema_version": 1, "generation_id": generation_id, "counts_method": "raw_token_counts",
                                            "tokenizer": tokenizer_info,
                                            "metadata_excluded": True, "train_only_vocabulary": True,
                                            "dimensions": report["vector_dimensions"]})
        _publish_pair([(staging, output_dir), (vector_stage, vectors_dir)], overwrite=overwrite)
    finally:
        for stage in (staging, vector_stage):
            if stage.exists():
                shutil.rmtree(stage)
    return report


def load_original_number_maps(path: str | Path) -> dict[str, dict[int, int]]:
    """삭제 전 원래 번호를 파일명별 현재 번호에 연결한다."""
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(data, list):
        raise ValueError("번호 대조표는 문항별 JSON 리스트여야 합니다.")
    result = defaultdict(dict)
    for row in data:
        if row.get("상태") != "유지":
            continue
        filename = row["파일"]
        current, original = int(row["현재번호"]), int(row["원래번호"])
        if current in result[filename]:
            raise ValueError(f"번호 대조표의 현재 번호가 중복됩니다: {filename}/{current}")
        result[filename][current] = original
    return dict(result)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=ROOT / "data/raw")
    parser.add_argument("--output", type=Path, default=ROOT / "data/processed")
    parser.add_argument("--vectors", type=Path, default=ROOT / "data/vectors")
    parser.add_argument("--number-map", type=Path, default=ROOT / "data/provenance/question_number_map.json")
    parser.add_argument("--transcriptions", type=Path, default=ROOT / "data/provenance/latex_transcriptions.json")
    parser.add_argument("--test-fraction", type=float, default=0.3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--allow-conversion-warnings", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    from mathhint_preprocess.hml import read_hml
    maps = load_original_number_maps(args.number_map)
    transcriptions = json.loads(args.transcriptions.read_text(encoding="utf-8"))
    raw = args.raw.resolve()
    if any(raw == p.resolve() or raw in p.resolve().parents or p.resolve() in raw.parents
           for p in (args.output, args.vectors)):
        parser.error("결과 폴더와 원본 폴더가 겹치면 안 됩니다.")
    paths = sorted(raw.glob("*.hml"))
    if not paths:
        parser.error(f"HML 원본이 없습니다: {raw}")
    records = []
    sources = []
    try:
        for path in paths:
            if path.name not in maps:
                raise ValueError(f"원래 번호 대조표가 없는 파일: {path.name}")
            extracted = read_hml(path, original_numbers=maps[path.name], transcriptions=transcriptions)
            if len(extracted) != len(maps[path.name]):
                raise ValueError(f"번호 대조표와 문항 수가 다릅니다: {path.name}")
            records.extend(extracted)
            sources.append({"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "questions": len(extracted)})
        expected_transcriptions = {(e["question_id"], e["region"], e["raw_sha256"]) for e in transcriptions}
        used_transcriptions = {(r["id"], e["region"], hashlib.sha256(e["raw"].encode()).hexdigest())
                               for r in records for e in r["equations"] if "transcription_reason" in e}
        if expected_transcriptions != used_transcriptions:
            raise ValueError("수식 전사표에 현재 원문과 대응하지 않는 항목이 있습니다.")
        report = prepare_records(records, args.output, args.vectors, test_fraction=args.test_fraction,
                                 seed=args.seed, strict=not args.allow_conversion_warnings,
                                 overwrite=args.overwrite, source_files=sources)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
