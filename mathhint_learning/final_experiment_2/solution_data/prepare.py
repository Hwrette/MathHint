"""문제 벡터는 읽기만 하고 원본 풀이265개만 기존 함수로 새로 계수한다."""

from collections import Counter
from importlib.metadata import version
from pathlib import Path

from .common import ROOT, OUTPUT, check_hashes, file_hash, fingerprint, read_json, write_csv, write_json


PROBLEM_BASE = "results/final_experiment_2/cluster_improvement/00_dataset/generated_data/filtered/problems"
STOPWORDS = "results/token_analysis/stopwords/solution_stopwords.json"
SELECTION_POLICY = {
    "primary": "validation_precision_at_20_maximize",
    "tie_breaker": "clipped_validation_mse_minimize_then_model_simplicity_then_preregistered_order",
    "top20": "positive_unrounded_descending_ties_vocabulary_index",
    "precision_denominator": 20,
    "recall_denominator": "available_actual_top20_count; null_if_empty",
    "internal_split_seed": 42, "validation_count": 37,
    "test_policy": "no_test_target_loading_until_model_selection_freeze",
    "input_policy": "existing raw problem counts; no automatic L2 or TF-IDF",
    "evaluation_scale": "original solution token counts; no integer rounding of predictions",
    "linear_search_limit": 12, "deep_coarse_limit": 6, "deep_refinement_limit": 2,
}


def _source_paths(root, ids):
    names = ["data/processed/metadata.json", "data/processed/splits/train.json", "data/processed/splits/test.json",
             "data/vectors/report.json", "data/vectors/solutions/vocabulary.json",
             "data/vectors/solutions/train_vectors.json", "data/vectors/solutions/test_vectors.json",
             PROBLEM_BASE + "/vocabulary.json", PROBLEM_BASE + "/all_vectors.json", STOPWORDS,
             "mathhint_analysis/BagOfWord.py", "mathhint_analysis/PrepareDataset.py"]
    names += [f"data/processed/solutions/{identifier}.txt" for identifier in ids]
    return {name: file_hash(Path(root) / name) for name in names}


def _original(root):
    root = Path(root)
    metadata = read_json(root / "data/processed/metadata.json")
    ids = {part: read_json(root / f"data/processed/splits/{part}.json") for part in ("train", "test")}
    all_ids = ids["train"] + ids["test"]
    records = {r["id"]: r for r in metadata["records"]}
    if len(ids["train"]) != 185 or len(ids["test"]) != 80 or len(set(all_ids)) != 265 or set(records) != set(all_ids):
        raise ValueError("기존185/80 분할과265개 ID가 일치하지 않습니다.")
    x = read_json(root / PROBLEM_BASE / "all_vectors.json")
    vocabulary = read_json(root / PROBLEM_BASE / "vocabulary.json")
    if [r["id"] for r in x["documents"]] != all_ids or x["shape"] != [265, 270] or len(vocabulary) != 270:
        raise ValueError("기존 문제270차원·ID/행 순서가 다릅니다.")
    if any(len(r["vector"]) != len(vocabulary) or any(type(v) is not int or v < 0 for v in r["vector"]) for r in x["documents"]):
        raise ValueError("기존 문제 BoW가 원시 음이 아닌 정수 빈도가 아닙니다.")
    return ids, records, all_ids, vocabulary, x


def _protected(root):
    from ..cluster_improvement.prepare import protected_files
    root = Path(root)
    hashes = protected_files(root)
    for name in ("results/final_experiment_2/cluster_improvement", "mathhint_learning/final_experiment_2/cluster_improvement"):
        for path in sorted((root / name).rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                hashes[str(path.relative_to(root))] = file_hash(path)
    return hashes


def _inner_split(ids, records):
    from sklearn.model_selection import train_test_split
    train = ids["train"]
    groups = [" / ".join(records[i][key] for key in ("curriculum", "unit")) for i in train]
    fit, validation = train_test_split(train, test_size=37, random_state=42, stratify=groups)
    fit, validation = set(fit), set(validation)
    return {"fit": [i for i in train if i in fit], "validation": [i for i in train if i in validation]}


def prepare(root=ROOT):
    root = Path(root).resolve()
    output = root / "results/final_experiment_2/solution_data"
    ids, records, all_ids, input_vocabulary, input_payload = _original(root)
    source_hashes = _source_paths(root, all_ids)
    prior_path = output / "config.json"
    if prior_path.exists():
        prior = read_json(prior_path)
        if prior["source_files_sha256"] != source_hashes or prior["selection_policy"] != SELECTION_POLICY:
            raise ValueError("기존 solution_data와 입력·목록·검증 정책이 다릅니다. 덮어쓰지 않습니다.")
        if (output / "manifest.json").is_file():
            print("전체265 풀이 준비 결과 재사용: 문제 재토큰화0·풀이 재토큰화0", flush=True)
            return load_data(root)
    protected = _protected(root)
    choices = read_json(root / STOPWORDS)
    if not isinstance(choices, list) or not choices or any(not isinstance(v, str) for v in choices):
        raise ValueError("사용자 승인 풀이 불용어 문자열 목록이 필요합니다.")
    selected = set(choices)
    from mathhint_analysis.PrepareDataset import _count_function
    count = _count_function()
    expected = read_json(root / "data/vectors/report.json")["tokenizer"]
    if count.tokenizer_info != expected:
        raise ValueError(f"기존과 토큰화 환경이 다릅니다: {count.tokenizer_info} / {expected}")
    counts = {}
    for j, identifier in enumerate(all_ids, 1):
        counts[identifier] = count((root / f"data/processed/solutions/{identifier}.txt").read_text(encoding="utf-8-sig"))
        if j % 50 == 0 or j == len(all_ids):
            print(f"원본 풀이 재토큰화 {j}/{len(all_ids)} · 기존 문제 벡터는 그대로", flush=True)
    raw_vocabulary = sorted({token for values in counts.values() for token, n in values.items() if n})
    active = [j for j, token in enumerate(raw_vocabulary) if token not in selected]
    vocabulary = [raw_vocabulary[j] for j in active]
    if not vocabulary:
        raise ValueError("불용어 제거 후 풀이 어휘가 없습니다.")
    raw = [[int(counts[i][token]) for token in raw_vocabulary] for i in all_ids]
    filtered = [[row[j] for j in active] for row in raw]
    old_vocab = read_json(root / "data/vectors/solutions/vocabulary.json")
    old_docs = {r["id"]: r for part in ("train", "test")
                for r in read_json(root / f"data/vectors/solutions/{part}_vectors.json")["documents"]}
    old_positions = {token: j for j, token in enumerate(old_vocab)}
    if not set(old_vocab).issubset(raw_vocabulary):
        raise ValueError("새 원시 풀이 어휘에 기존 어휘가 빠졌습니다.")
    recount = []
    for identifier in all_ids:
        values, old = counts[identifier], old_docs[identifier]
        same = all(values[token] == old["vector"][j] for token, j in old_positions.items())
        restored = sum(n for token, n in values.items() if token not in old_positions)
        if not same or restored != old["ignored_token_count"] or sum(values.values()) != old["token_count"]:
            raise ValueError(f"원래 풀이 좌표·TF·OOV 재계수가 다릅니다: {identifier}")
        recount.append({"id": identifier, "token_count": sum(values.values()),
                        "all_legacy_coordinates_match": same, "restored_token_count": restored})
    inner = _inner_split(ids, records)
    splits = {**ids, **inner}
    source = {"files": source_hashes, "tokenizer": count.tokenizer_info, "selection_policy": SELECTION_POLICY,
              "ids": splits, "raw_solution_vocabulary": raw_vocabulary,
              "active_indices": active, "raw_vectors_sha256": fingerprint(raw)}
    dataset_id = fingerprint(source)
    generated = output / "generated_data"
    split_of = {i: part for part in ("train", "test") for i in ids[part]}
    for kind, vocab, values in (("raw", raw_vocabulary, raw), ("filtered", vocabulary, filtered)):
        folder = generated / kind / "solutions"
        write_json(folder / "vocabulary.json", vocab)
        write_json(folder / "all_vectors.json", {"dataset_id": dataset_id, "vocabulary_fitted_on": "full265",
            "variant": kind, "region": "solutions", "shape": [265, len(vocab)],
            "documents": [{"id": i, "original_split": split_of[i], "vector": values[j],
                           "token_count": sum(values[j]), "raw_token_count": sum(raw[j])} for j, i in enumerate(all_ids)]})
    write_json(generated / "splits.json", {**splits, "policy": "original185/80; inner148/37 stratified curriculum+unit seed42"})
    write_json(generated / "input_reference.json", {"problem_vectors_path": PROBLEM_BASE + "/all_vectors.json",
        "problem_vocabulary_path": PROBLEM_BASE + "/vocabulary.json",
        "problem_vectors_sha256": file_hash(root / PROBLEM_BASE / "all_vectors.json"),
        "problem_vocabulary_sha256": file_hash(root / PROBLEM_BASE / "vocabulary.json"),
        "dimension": len(input_vocabulary), "policy": "read_only_reuse; no new problem tokenization"})
    total = sum(counts.values(), Counter())
    df = Counter(token for values in counts.values() for token in values)
    raw_pos = {token: j for j, token in enumerate(raw_vocabulary)}
    active_pos = {token: j for j, token in enumerate(vocabulary)}
    write_csv(output / "solution_token_mapping.csv", [{"token": token, "raw_index": j,
              "active_index": active_pos.get(token, ""), "removed": token in selected,
              "total_tf": total[token], "total_df": df[token], "legacy_index": old_positions.get(token, "")}
              for j, token in enumerate(raw_vocabulary)])
    write_csv(output / "stopword_audit.csv", [{"token": token, "found": token in raw_pos,
              "total_tf": total[token], "total_df": df[token]} for token in dict.fromkeys(choices)])
    write_csv(output / "recount_validation.csv", recount)
    write_csv(output / "question_token_counts.csv", [{"id": i, "original_split": split_of[i],
              "raw_tf": sum(raw[j]), "filtered_tf": sum(filtered[j]), "removed_tf": sum(raw[j])-sum(filtered[j])}
              for j, i in enumerate(all_ids)])
    summary = {"n": 265, "train": 185, "test": 80, "inner_fit": len(inner["fit"]), "validation": len(inner["validation"]),
        "input_dimension": len(input_vocabulary), "raw_solution_dimension": len(raw_vocabulary),
        "output_dimension": len(vocabulary), "registered_solution_stopwords": len(choices),
        "removed_solution_stopwords": len(selected & set(raw_vocabulary)),
        "unknown_stopwords": sorted(selected - set(raw_vocabulary)), "duplicate_choices": len(choices)-len(selected),
        "raw_solution_tf": sum(total.values()), "filtered_solution_tf": sum(sum(row) for row in filtered),
        "raw_zero_vectors": sum(not any(row) for row in raw), "filtered_zero_vectors": sum(not any(row) for row in filtered),
        "new_problem_tokenizations": 0, "new_solution_tokenizations": len(counts),
        "test_only_active_solution_tokens": [token for token in vocabulary if not any(counts[i][token] for i in ids["train"])]}
    write_json(output / "summary.json", summary)
    write_json(output / "config.json", {"schema_version": 1, "dataset_id": dataset_id,
        "source_files_sha256": source_hashes, "source_definition": source, "protected_files_sha256": protected,
        "selection_policy": SELECTION_POLICY, "stopwords": {"path": STOPWORDS, "sha256": file_hash(root / STOPWORDS), "tokens": choices},
        "transductive_caveat": "Vocabulary from all265 including test reference solutions; weights/selection use only original train185.",
        "input_problem_vectors_reused": True, "source_texts": "original cleaned solutions only, not Gemini outputs or annotations"})
    _readme(output, summary)
    check_hashes(root, protected)
    hashes = {str(p.relative_to(output)): file_hash(p) for p in sorted(output.rglob("*"))
              if p.is_file() and p.name != "manifest.json"}
    write_json(output / "manifest.json", {"dataset_id": dataset_id, "files_sha256": hashes})
    print(f"공통 데이터 준비 완료: {len(input_vocabulary)}→{len(vocabulary)} · 내부 {len(inner['fit'])}/{len(inner['validation'])} · test80 잠금", flush=True)
    return load_data(root)


def _readme(output, summary):
    text = f'''# 문제 → 원본 풀이 예측의 공통 데이터

[2차 연구 목차](../README.md)

|구분|결과|
|---|---:|
|기존 불용어 제거 문제 입력|{summary['input_dimension']}차원, 그대로 재사용|
|전체265 원본 풀이 어휘|{summary['raw_solution_dimension']}개|
|사용자 풀이 불용어|{summary['registered_solution_stopwords']}개|
|실제 제거 후 풀이 타깃|{summary['output_dimension']}차원|
|원래 학습 / 테스트|185 / 80|
|학습 내부 fit / validation|{summary['inner_fit']} / {summary['validation']}|
|풀이 TF 제거 전 / 후|{summary['raw_solution_tf']:,} / {summary['filtered_solution_tf']:,}|
|풀이 영벡터|{summary['filtered_zero_vectors']}개|

문제 벡터는 군집화에서 완성한 원시 정수 빈도를 읽기만 했다. 원본 풀이265개만 원래 Kiwi·LaTeX 함수로 새로 토큰화했다. 사용자103개 외 토큰은 제거하지 않았다. 문제와 풀이 어휘·인덱스는 독립이다.

검증은 기존 학습185 안에서 과목/단원으로 층화한148/37(시드42)이다. 모델 선택의 주 지표는 **검증 Precision@20**, 동률이면 음수 보정 MSE, 단순한 모델/사전 후보 순서다. 양의 빈도만 내림차순, 동률 어휘 인덱스 순으로20개를 선택한다. P@20의 분모는20, Recall의 분모는 실제 선택된 최대20개 수다. 테스트 타깃은 모델 확정 후에만 읽는 로더 옵션으로 분리했다.

전체265의 어휘와 테스트 원본 풀이의 단어 존재를 미리 알고 있는 전이적 실험이다. 가중치·검증 최적화에 테스트를 넣지 않았다는 사실과 완전히 독립적인 미관측 평가라는 주장을 구분한다. 학습에서 한 번도 나타나지 않은 타깃 토큰은 어휘에 있어도 해당 빈도를 배울 직접 사례가 없다. 기존 문제필터에서 동일벡터가 된 diff_1_007/train·diff_1_011/test도 원래 분할 그대로 보존한다.

- [요약](summary.json) · [설정·입력/불용어 SHA와 선택 정책](config.json)
- [전체 풀이 어휘·제거/유지·원시↔활성 인덱스·TF/DF](solution_token_mapping.csv)
- [승인 목록 실제 적용](stopword_audit.csv) · [기존 좌표 재계수265행](recount_validation.csv)
- [문항별 빈도 감소](question_token_counts.csv) · [원래·내부 분할](generated_data/splits.json)
- [불변 문제 입력 참조](generated_data/input_reference.json) · [준비 파일 SHA](manifest.json)

```bash
python -m mathhint_learning.final_experiment_2.solution_data prepare
python -m mathhint_learning.final_experiment_2.solution_data verify
```

prepare는 완료된 동일 입력을 검증해 재사용한다. verify는 저장 자료만 읽으며 모델 학습·토큰화·API 호출이 없다.
'''
    (output / "README.md").write_text(text, encoding="utf-8")


def load_data(root=ROOT, *, include_test=False):
    """모델 선택용 기본 반환값에는 테스트 입력·타깃 텐서를 넣지 않는다."""
    import torch
    root = Path(root).resolve()
    output = root / "results/final_experiment_2/solution_data"
    config = read_json(output / "config.json")
    check_hashes(root, config["protected_files_sha256"])
    check_hashes(root, config["source_files_sha256"])
    manifest = read_json(output / "manifest.json")
    check_hashes(output, manifest["files_sha256"])
    ids, records, all_ids, x_vocab, x_payload = _original(root)
    split = read_json(output / "generated_data/splits.json")
    ids.update({key: split[key] for key in ("fit", "validation")})
    if (set(ids["fit"]) & set(ids["validation"]) or set(ids["fit"] + ids["validation"]) != set(ids["train"])
            or [len(ids[p]) for p in ("fit", "validation")] != [148, 37]):
        raise ValueError("내부 검증 분할이 원래 학습185 안에서만 이루어지지 않았습니다.")
    y_payload = read_json(output / "generated_data/filtered/solutions/all_vectors.json")
    y_vocab = read_json(output / "generated_data/filtered/solutions/vocabulary.json")
    if (y_payload["dataset_id"] != config["dataset_id"] or [r["id"] for r in y_payload["documents"]] != all_ids
            or len(y_vocab) != len(set(y_vocab)) or y_payload["shape"] != [265, len(y_vocab)]):
        raise ValueError("풀이 ID/어휘/행/데이터 버전이 다릅니다.")
    for row in y_payload["documents"]:
        if len(row["vector"]) != len(y_vocab) or any(type(v) is not int or v < 0 for v in row["vector"]):
            raise ValueError("풀이 실제 빈도는 어휘에 대응하는 음이 아닌 정수여야 합니다.")
    by_id = {"problems": {r["id"]: r["vector"] for r in x_payload["documents"]},
             "solutions": {r["id"]: r["vector"] for r in y_payload["documents"]}}
    parts = ("train", "fit", "validation", "test", "all") if include_test else ("train", "fit", "validation")
    lookup = {**ids, "all": all_ids}
    arrays = {region: {part: torch.tensor([rows[i] for i in lookup[part]], dtype=torch.float32)
                       for part in parts} for region, rows in by_id.items()}
    return {"dataset_id": config["dataset_id"], "identity": {"fingerprint": config["dataset_id"]},
            "ids": ids, "all_ids": all_ids, "arrays": arrays,
            "vocabularies": {"problems": x_vocab, "solutions": y_vocab}, "records": records,
            "config": config, "data_root": output, "test_targets_loaded": include_test}


def verify(root=ROOT):
    root = Path(root).resolve()
    output = root / "results/final_experiment_2/solution_data"
    data = load_data(root, include_test=True)
    import torch
    raw = read_json(output / "generated_data/raw/solutions/all_vectors.json")
    vocabulary = read_json(output / "generated_data/raw/solutions/vocabulary.json")
    choices = set(read_json(root / STOPWORDS))
    indices = [j for j, token in enumerate(vocabulary) if token not in choices]
    expected = torch.tensor([r["vector"] for r in raw["documents"]], dtype=torch.float32)[:, indices]
    if (data["vocabularies"]["solutions"] != [vocabulary[j] for j in indices]
            or not torch.equal(data["arrays"]["solutions"]["all"], expected)):
        raise ValueError("승인 불용어 외 좌표 또는 어휘 순서가 변경되었습니다.")
    print(f"공통 데이터 검증 PASS:265문항·내부148/37·{len(data['vocabularies']['problems'])}→{len(indices)} · 학습/API 없음")
    return data
