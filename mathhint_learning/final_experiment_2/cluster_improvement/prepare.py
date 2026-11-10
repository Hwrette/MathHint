"""문제 원문265개를 원래 토큰화로 재계수하여 raw/filtered를 함께 만든다."""

from collections import Counter
from importlib.metadata import version
from pathlib import Path
import sys

from .common import (ROOT, OUTPUT, check_hashes,
                     file_hash, fingerprint, output_path, read_json, write_csv,
                     write_json)


def original_data(root):
    root = Path(root)
    metadata = read_json(root / "data/processed/metadata.json")
    ids = {part: read_json(root / f"data/processed/splits/{part}.json") for part in ("train", "test")}
    full_ids = ids["train"] + ids["test"]
    records = {r["id"]: r for r in metadata["records"]}
    if ([len(ids[p]) for p in ("train", "test")] != [185, 80]
            or len(set(full_ids)) != 265 or set(records) != set(full_ids)
            or len(records) != len(metadata["records"])):
        raise ValueError("원래265개 ID와185/80 소속이 일치하지 않습니다.")
    vocabulary = read_json(root / "data/vectors/problems/vocabulary.json")
    documents = {}
    for part in ("train", "test"):
        payload = read_json(root / f"data/vectors/problems/{part}_vectors.json")
        if [r["id"] for r in payload["documents"]] != ids[part]:
            raise ValueError(f"기존 {part} 벡터 ID 순서가 다릅니다.")
        documents.update({r["id"]: r for r in payload["documents"]})
    return ids, records, vocabulary, documents


def source_configuration(root, ids, *, tokenizer_info=None):
    root = Path(root)
    sources = ["data/processed/metadata.json", "data/processed/splits/train.json",
               "data/processed/splits/test.json", "data/vectors/problems/vocabulary.json",
               "data/vectors/problems/train_vectors.json", "data/vectors/problems/test_vectors.json",
               "data/vectors/report.json", "results/token_analysis/stopwords/problem_stopwords.json",
               "mathhint_analysis/BagOfWord.py", "mathhint_analysis/PrepareDataset.py",
               "mathhint_learning/TorchKMeans.py", "mathhint_learning/ClusteringConfusion.py"]
    sources += [f"data/processed/problems/{identifier}.txt" for identifier in ids["train"] + ids["test"]]
    # 읽기 전용 작업은 저장 당시 토큰화 정보를 사용하며 Kiwi 설치를 요구하지 않는다.
    tokenizer = tokenizer_info or {"package": "kiwipiepy", "version": version("kiwipiepy"),
                                  "model_package_version": version("kiwipiepy_model"), "num_workers": 2}
    expected = read_json(root / "data/vectors/report.json")["tokenizer"]
    if tokenizer != expected:
        raise ValueError(f"기존 토큰화 환경과 다릅니다: 기존 {expected}, 현재 {tokenizer}")
    return {"tokenizer": tokenizer, "source_files_sha256": {name: file_hash(root / name) for name in sources},
            "vocabulary_policy": "full265_problem_original_text", "count_policy": "raw_integer_counts",
            "filter_policy": "exact_user_problem_stopwords_only_remove_dimensions",
            "scope": "full265_fit_and_descriptive_evaluation_only", "ids": ids}


def protected_files(root):
    root = Path(root)
    files = set()
    for name in ("data", "results/final_experiment", "results/token_analysis", "results/model_comparison_2026-11-07"):
        files.update(p for p in (root / name).rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    for name in ("mathhint_analysis/BagOfWord.py", "mathhint_analysis/PrepareDataset.py",
                 "mathhint_learning/TorchData.py", "mathhint_learning/TorchKMeans.py",
                 "mathhint_learning/TorchRegression.py", "mathhint_learning/VectorComparison.py",
                 "mathhint_learning/ClusteringConfusion.py", "mathhint_learning/ClusterReport.py",
                 "mathhint_learning/Experiment.py", "mathhint_learning/RunExperiment.py"):
        files.add(root / name)
    for folder in ("mathhint_learning/holdout", "mathhint_learning/full_dataset_265"):
        files.update((root / folder).glob("*.py"))
    return {str(p.relative_to(root)): file_hash(p) for p in sorted(files)}


def project_counts(full_ids, counts, vocabulary, selected_stopwords):
    """같은 원시 계수에서 활성 좌표만 추출한다. 정규화·재토큰화는 없다."""
    active = [i for i, token in enumerate(vocabulary) if token not in selected_stopwords]
    kept = [vocabulary[i] for i in active]
    raw = [[int(counts[identifier][token]) for token in vocabulary] for identifier in full_ids]
    filtered = [[row[i] for i in active] for row in raw]
    return raw, filtered, active, kept


def run(root=ROOT, output=OUTPUT):
    root, output = Path(root).resolve(), output_path(root, output)
    ids, records, old_vocabulary, old_documents = original_data(root)
    source = source_configuration(root, ids)
    source_id = fingerprint(source)
    config_path = output / "config.json"
    if config_path.exists():
        prior = read_json(config_path)
        if prior["source_fingerprint"] != source_id:
            raise ValueError("다른 입력으로 만든 기존 실험이 있습니다. 덮어쓰거나 재사용하지 않습니다.")
        if (output / "00_dataset/manifest.json").is_file():
            data = load_dataset(root, output)
            print("문제265의 기존 준비 결과를 해시 검증해 재사용했습니다. 재토큰화 없음.", flush=True)
            return data
    protected = protected_files(root)
    choices_path = root / "results/token_analysis/stopwords/problem_stopwords.json"
    choices = read_json(choices_path)
    if not isinstance(choices, list) or not choices or any(not isinstance(v, str) for v in choices):
        raise ValueError("승인된 문제 불용어 문자열 배열이 필요합니다. 빈 목록으로 제거 완료를 표시하지 않습니다.")
    selected = set(choices)
    from mathhint_analysis.PrepareDataset import _count_function
    counter = _count_function()
    counts = {}
    full_ids = ids["train"] + ids["test"]
    split = {identifier: p for p in ("train", "test") for identifier in ids[p]}
    for i, identifier in enumerate(full_ids, 1):
        text = (root / f"data/processed/problems/{identifier}.txt").read_text(encoding="utf-8-sig")
        counts[identifier] = counter(text)
        if i % 50 == 0 or i == len(full_ids):
            print(f"문제 원문 재토큰화 {i}/{len(full_ids)}", flush=True)
    vocabulary = sorted({token for row in counts.values() for token, count in row.items() if count > 0})
    raw, filtered, active, kept = project_counts(full_ids, counts, vocabulary, selected)
    if not kept:
        raise ValueError("필터 후 문제 어휘가 비었습니다. 임의 변경 없이 중단합니다.")
    old_positions = {token: i for i, token in enumerate(old_vocabulary)}
    positions = {token: i for i, token in enumerate(vocabulary)}
    if not set(old_vocabulary).issubset(positions):
        raise ValueError("새 토큰화에서 기존 어휘 일부가 사라졌습니다.")
    recount = []
    for identifier in full_ids:
        row = old_documents[identifier]
        same = all(counts[identifier][token] == row["vector"][j] for token, j in old_positions.items())
        restored = sum(count for token, count in counts[identifier].items() if token not in old_positions)
        if not same or restored != row["ignored_token_count"] or sum(counts[identifier].values()) != row["token_count"]:
            raise ValueError(f"기존 토큰화/좌표와 재계수가 다릅니다: {identifier}")
        recount.append({"region": "problems", "id": identifier, "split": split[identifier],
                        "token_count": sum(counts[identifier].values()),
                        "legacy_token_count": sum(row["vector"]), "restored_token_count": restored,
                        "all_legacy_coordinates_match": same})
    total = sum(counts.values(), Counter())
    df = Counter(token for row in counts.values() for token in row if row[token] > 0)
    removed = selected & set(vocabulary)
    dataset_id = fingerprint({"source_fingerprint": source_id, "vocabulary": vocabulary,
                              "active_indices": active, "ids": full_ids, "raw_vectors": raw})
    folder = output / "00_dataset"
    generated = folder / "generated_data"
    variants = {}
    for kind, vocab, values, indices in (("raw", vocabulary, raw, list(range(len(vocabulary)))),
                                         ("filtered", kept, filtered, active)):
        directory = generated / kind / "problems"
        write_json(directory / "vocabulary.json", vocab)
        payload = {"schema_version": 1, "dataset_id": dataset_id, "generation_id": dataset_id + ":" + kind,
                   "variant": kind, "region": "problems", "vocabulary_fitted_on": "full265",
                   "evaluation_scope": "all265 descriptive", "shape": [len(full_ids), len(vocab)],
                   "active_full_vocabulary_indices": indices,
                   "documents": [{"id": identifier, "original_split": split[identifier],
                       "problem_path": f"data/processed/problems/{identifier}.txt", "vector": values[i],
                       "token_count": sum(values[i]), "original_token_count": sum(raw[i]),
                       "removed_token_count": sum(raw[i]) - sum(values[i])}
                       for i, identifier in enumerate(full_ids)]}
        write_json(directory / "all_vectors.json", payload)
        variants[kind] = {"vocabulary": str((directory / "vocabulary.json").relative_to(output)),
                          "vectors": str((directory / "all_vectors.json").relative_to(output)),
                          "active_indices": indices}
    write_json(generated / "dataset.json", {"dataset_id": dataset_id, "ids": full_ids,
               "original_splits": ids, "variants": variants, "source_fingerprint": source_id})
    write_csv(folder / "recount_validation.csv", recount)
    restored_rows = [{"token": token, "new_index": positions[token], "total_tf": total[token], "total_df": df[token]}
                     for token in vocabulary if token not in old_positions]
    write_csv(folder / "restored_tokens.csv", restored_rows,
              fields=["token", "new_index", "total_tf", "total_df"])
    stop_rows = [{"token": token, "found_in_full265": token in positions,
                  "total_tf": total[token], "total_df": df[token], "full_index": positions.get(token, "")}
                 for token in dict.fromkeys(choices)]
    write_csv(folder / "stopword_audit.csv", stop_rows)
    write_csv(folder / "retained_tokens.csv", [{"active_index": i, "full_index": positions[token], "token": token,
               "total_tf": total[token], "total_df": df[token]} for i, token in enumerate(kept)])
    active_positions = {j: i for i, j in enumerate(active)}
    write_csv(folder / "token_index_mapping.csv", [{"full_index": j, "token": token,
               "legacy_index": old_positions.get(token, ""), "active_index": active_positions.get(j, ""),
               "removed": token in removed} for j, token in enumerate(vocabulary)])
    write_csv(folder / "question_token_counts.csv", [{"id": identifier, "original_split": split[identifier],
               "raw_token_count": sum(raw[i]), "filtered_token_count": sum(filtered[i]),
               "removed_token_count": sum(raw[i]) - sum(filtered[i])} for i, identifier in enumerate(full_ids)])
    zeros = {kind: {p: sum(not any(values[i]) for i, identifier in enumerate(full_ids) if split[identifier] == p)
                   for p in ("train", "test")} for kind, values in (("raw", raw), ("filtered", filtered))}
    info = {"legacy_vocab_count": len(old_vocabulary), "raw_vocab_count": len(vocabulary),
            "filtered_vocab_count": len(kept), "restored_token_count": len(restored_rows),
            "registered_stopword_count": len(choices), "execution_unique_stopword_count": len(selected),
            "duplicate_stopwords": len(choices) - len(selected), "removed_token_count": len(removed),
            "removed_tf": sum(total[t] for t in removed), "total_tf_before": sum(total.values()),
            "total_tf_after": sum(total[t] for t in kept), "zero_vectors": zeros,
            "stopwords_not_found": sorted(selected - positions.keys()),
            "unique_vectors": {"raw": len({tuple(v) for v in raw}), "filtered": len({tuple(v) for v in filtered})}}
    summary = {"n": len(full_ids), "train": len(ids["train"]), "test": len(ids["test"]),
               "split_role": "provenance only, no holdout experiment", "regions": {"problems": info},
               "retokenized_problem_count": len(counts), "retokenized_solution_count": 0}
    write_json(folder / "summary.json", summary)
    levels = ("curriculum", "unit", "subunit", "type")
    k = {level: len({tuple(records[i][key] for key in levels[:j + 1]) for i in full_ids})
         for j, level in enumerate(levels)}
    legacy_config = read_json(root / "results/final_experiment/01_clustering/full_dataset_265/config.json")
    if k != legacy_config["k"]:
        raise ValueError(f"실제 분류 수가 기존 full265와 다릅니다: {k}")
    clustering = {name: legacy_config[name] for name in ("seeds", "initialization_restarts", "max_iter", "tolerance", "k", "selection")}
    config = {"schema_version": 1, "experiment": "final_experiment_2/cluster_improvement",
              "scope": "full265_problems_only", "dataset_id": dataset_id, "source_fingerprint": source_id,
              "source_configuration": source, "protected_files_sha256": protected,
              "stopwords": {"path": "results/token_analysis/stopwords/problem_stopwords.json",
                            "sha256": file_hash(choices_path), "selected_tokens": choices,
                            "application": "problems only; reduced active dimensions"},
              "clustering": clustering, "labels_used_for_center_fitting": False,
              "majority_scope": "all265; descriptive resubstitution only",
              "forbidden_tasks": ["regression", "solution_bow", "holdout_experiment", "gemini", "neural_network"],
              "runtime": {"python": sys.version.split()[0], "tokenizer": source["tokenizer"]}}
    write_json(config_path, config)
    _documents(folder, info, summary, choices)
    check_hashes(root, protected)
    hashes = {str(path.relative_to(folder)): file_hash(path) for path in sorted(folder.rglob("*"))
              if path.is_file() and path.name != "manifest.json"}
    write_json(folder / "manifest.json", {"dataset_id": dataset_id, "files_sha256": hashes})
    print(f"문제 BoW {len(old_vocabulary)}→{len(vocabulary)}→{len(kept)}, 승인 토큰 {len(removed)}종 제거; 기존 자료 {len(protected)}개 SHA 불변", flush=True)
    return load_dataset(root, output)


def _documents(folder, info, summary, choices):
    text = f'''# 문제265개 · 새 전체 어휘와 사용자 불용어\n\n[상위 실험 안내](../README.md) · [어휘 비교](vocabulary_comparison.md)\n\n문제 원문265개를 기존 Kiwi·LaTeX 함수로 **새로 토큰화**했다. 분류·출처 주석과 원본 풀이를 토큰화하지 않았다. 원래185/80 소속은 행 추적용이며 이번 실험은 전체265개를 함께 학습·평가한다.\n\n|문제 어휘|종류|\n|---|---:|\n|기존 학습 전용 어휘|{info['legacy_vocab_count']}|\n|전체265 Raw(K0)|{info['raw_vocab_count']}|\n|원래 없던 복원 토큰|{info['restored_token_count']}|\n|사용자 지정/실제 제거|{info['registered_stopword_count']} / {info['removed_token_count']}|\n|Filtered(K1) 활성 차원|{info['filtered_vocab_count']}|\n\n- [복원된 모든 토큰·TF/DF](restored_tokens.csv)\n- [승인된 제거 토큰 전체·TF/DF·실제 존재 여부](stopword_audit.csv)\n- [유지한 토큰 전체](retained_tokens.csv) · [원래/전체/활성 인덱스 대응](token_index_mapping.csv)\n- [문항별 제거 전후 등장 횟수](question_token_counts.csv) · [원래 좌표와 재토큰화 대조265행](recount_validation.csv)\n- [요약 수치](summary.json) · [생성 데이터/경로](generated_data/dataset.json) · [준비 결과 SHA](manifest.json)\n\n총 등장 횟수는 {info['total_tf_before']:,}→{info['total_tf_after']:,}회이며 {info['removed_tf']:,}회({info['removed_tf']/info['total_tf_before']:.2%})를 제외했다. 영벡터는 raw {sum(info['zero_vectors']['raw'].values())}개 / filtered {sum(info['zero_vectors']['filtered'].values())}개다. 고유 벡터 수는 각각 {info['unique_vectors']['raw']} / {info['unique_vectors']['filtered']}개다. 사용자 목록 중 원문에 없는 토큰: {', '.join(info['stopwords_not_found']) or '없음'}. 중복 지정: {info['duplicate_stopwords']}개.\n\n기존 어휘·벡터는 수정하지 않았다. K0/K1은 같은 원문 계수에서 출발하며 K1은 지정96개 좌표를 제외한 **축소 차원**이다. 빈도 재가중·새 정규화·미승인 토큰 삭제는 없다. 새 어휘에는 전체 자료가 사용되었고 동일 전체 자료를 평가하므로 미관측 문항의 일반화 성능이 아니다.\n'''
    (folder / "README.md").write_text(text, encoding="utf-8")
    token_lines = "\n".join(f"- `{token}`" for token in choices)
    (folder / "vocabulary_comparison.md").write_text(text + "\n## 실제 사용자 지정 제거 목록\n\n" + token_lines + "\n", encoding="utf-8")


def load_dataset(root=ROOT, output=OUTPUT):
    """전체265 어휘 정책을 명시한 전용 로더. 기존 train-only 로더는 바꾸지 않는다."""
    import torch
    root, output = Path(root).resolve(), output_path(root, output)
    config = read_json(output / "config.json")
    check_hashes(root, config["protected_files_sha256"])
    source = source_configuration(root, config["source_configuration"]["ids"],
                                  tokenizer_info=config["source_configuration"]["tokenizer"])
    if fingerprint(source) != config["source_fingerprint"]:
        raise ValueError("입력/토큰화 환경이 저장된 데이터와 다릅니다.")
    folder = output / "00_dataset"
    manifest = read_json(folder / "manifest.json")
    check_hashes(folder, manifest["files_sha256"])
    descriptor = read_json(folder / "generated_data/dataset.json")
    ids, records, _, _ = original_data(root)
    if (descriptor["dataset_id"] != config["dataset_id"] or descriptor["original_splits"] != ids
            or descriptor["ids"] != ids["train"] + ids["test"]):
        raise ValueError("데이터 ID/행 순서/원래 소속이 다릅니다.")
    variants = {}
    full_ids = descriptor["ids"]
    for kind, paths in descriptor["variants"].items():
        vocab = read_json(output / paths["vocabulary"])
        payload = read_json(output / paths["vectors"])
        if (payload["dataset_id"] != config["dataset_id"] or payload["vocabulary_fitted_on"] != "full265"
                or [r["id"] for r in payload["documents"]] != full_ids
                or len(vocab) != len(set(vocab)) or payload["shape"] != [len(full_ids), len(vocab)]):
            raise ValueError(f"{kind}: 어휘/정책/ID/차원이 다릅니다.")
        values = [r["vector"] for r in payload["documents"]]
        if any(len(row) != len(vocab) or any(type(v) is not int or v < 0 for v in row) for row in values):
            raise ValueError(f"{kind}: 빈도는 음이 아닌 정수이며 어휘와 같은 차원이어야 합니다.")
        identity = {"dataset_id": config["dataset_id"], "variant": kind,
                    "vocabulary_sha256": file_hash(output / paths["vocabulary"]),
                    "vectors_sha256": file_hash(output / paths["vectors"])}
        identity["fingerprint"] = fingerprint(identity)
        matrix = torch.tensor(values, dtype=torch.float32)
        cut = len(ids["train"])
        variants[kind] = {"arrays": {"problems": {"train": matrix[:cut], "test": matrix[cut:]}},
                          "vocabularies": {"problems": vocab}, "active_indices": {"problems": paths["active_indices"]},
                          "identity": identity, "generation_id": payload["generation_id"]}
    return {"ids": ids, "full_ids": full_ids, "records": records, "variants": variants,
            "dataset_id": config["dataset_id"], "identity": {"fingerprint": config["dataset_id"]}, "config": config}
