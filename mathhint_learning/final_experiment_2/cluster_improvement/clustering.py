"""전체265 문제 BoW의 K0/K1 군집화. 기존 공통 알고리즘만 학습에 사용한다.

대표 라벨과 중심을 동일한 전체 자료에서 정한 탐색 실험이다. 원래
train/test 소속은 출처로만 보존하며, 테스트 성능을 새로 계산하지 않는다.
"""

from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import (adjusted_mutual_info_score, adjusted_rand_score,
                             f1_score, normalized_mutual_info_score)

from ...TorchKMeans import (fit_kmeans, fit_spherical_kmeans, MAX_ITER,
                            TOLERANCE, RESTARTS, SEED)
from ...holdout.run import (LEVELS, LEVEL_NAMES, METHOD_NAMES, hierarchy_label,
                            majority_labels, write_csv)
from ...TorchData import write_json


CONDITIONS = {"K0": "raw", "K1": "filtered"}
SEEDS = tuple(range(SEED, SEED + RESTARTS))


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _signature(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":")).encode()).hexdigest()


def full_matrix(data, variant):
    """원래 분할의 행순서를 출처로 보존하며 전체를 한 학습 집합으로 합친다."""
    rows = data["variants"][variant]["arrays"]["problems"]
    ids = data["ids"]["train"] + data["ids"]["test"]
    matrix = torch.cat([torch.as_tensor(rows[part], dtype=torch.float32)
                        for part in ("train", "test")]).detach().cpu()
    vocabulary = data["variants"][variant]["vocabularies"]["problems"]
    if len(ids) != len(set(ids)) or matrix.shape != (len(ids), len(vocabulary)):
        raise ValueError("전체 문제의 ID·어휘·벡터 행 대응이 다릅니다.")
    if not torch.isfinite(matrix).all() or (matrix < 0).any() or not torch.equal(matrix, matrix.round()):
        raise ValueError("군집 입력은 기존 토큰화로 얻은 유한한 원시 정수 빈도여야 합니다.")
    return ids, matrix, vocabulary


def evaluate(assignments, actual, majorities, k):
    """임의 군집번호의 일치도와 같은265에서 얻은 대표 라벨 일치율을 구분한다."""
    predicted = [majorities[int(cluster)] for cluster in assignments]
    labels = sorted(set(actual) | set(predicted))
    counts = Counter(int(cluster) for cluster in assignments)
    return {
        "ari": float(adjusted_rand_score(actual, assignments)),
        "ami": float(adjusted_mutual_info_score(actual, assignments)),
        "nmi": float(normalized_mutual_info_score(actual, assignments)),
        "majority_accuracy": sum(a == b for a, b in zip(actual, predicted)) / len(actual),
        "full_majority_match_rate": sum(a == b for a, b in zip(actual, predicted)) / len(actual),
        "macro_f1": float(f1_score(actual, predicted, labels=labels, average="macro", zero_division=0)),
        "weighted_f1": float(f1_score(actual, predicted, labels=labels, average="weighted", zero_division=0)),
        "f1_label_count": len(labels), "n": len(actual), "occupied_clusters": len(counts),
        "cluster_sizes": {str(c): counts[c] for c in range(k)},
    }


def _experiment_config(root, data, condition, level, method, matrix, vocabulary, ids):
    return {
        "experiment": f"{condition}_{level}_{method}", "condition": condition,
        "representation": CONDITIONS[condition], "level": level, "method": method,
        "dataset_id": data["dataset_id"], "fit_scope": "all_265",
        "evaluation_scope": "same_all_documents_not_generalization",
        "fit_ids": ids, "vocabulary": vocabulary,
        "matrix_sha256": hashlib.sha256(matrix.numpy().tobytes()).hexdigest(),
        "seeds": list(SEEDS), "restarts": len(SEEDS), "max_iter": MAX_ITER,
        "tolerance": TOLERANCE,
        "algorithm_file_sha256": _hash(Path(root) / "mathhint_learning/TorchKMeans.py"),
        "selection": "minimum fit objective only; ties use first seed",
        "majority_label_scope": "same all 265 documents",
        "majority_tie_rule": "highest frequency, then full hierarchical label lexical order",
        "f1_labels": "union of observed actual and representative predicted labels; zero_division=0",
        "original_split_role": "provenance only; not a train/test evaluation",
        "zero_vector_policy": "existing shared algorithm: zeros remain zero; spherical similarities zero; smallest cluster on tie",
        "torch_version": str(torch.__version__),
    }


def _documents(data, experiment, condition, level, method, ids, assignments, actual, majorities):
    original = {identifier: part for part, values in data["ids"].items() for identifier in values}
    rows = []
    for identifier, cluster, label in zip(ids, assignments, actual):
        record = data["records"][identifier]
        rows.append({
            "experiment": experiment, "condition": condition, "level": level, "method": method,
            "id": identifier, "original_split": original[identifier], "cluster": int(cluster),
            "actual_label": label, "full_majority_label": majorities[int(cluster)],
            "matches_full_majority": label == majorities[int(cluster)],
            **{field: record.get(field, "") for field in
               ("subject", "curriculum", "unit", "subunit", "type", "source", "source_file", "original_number", "current_number")},
            "problem_path": f"data/processed/problems/{identifier}.txt",
            "annotated_path": f"data/processed/annotated/{identifier}.txt",
        })
    return rows


def run(root, output, data):
    """16개 전체자료 실험을 학습한다. 완료된 동일 조건은 모델 해시 확인 후 재사용한다."""
    root, output = Path(root), Path(output)
    target_root = output / "01_clustering"
    target_root.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(2)
    summaries = []
    for condition, variant in CONDITIONS.items():
        ids, matrix, vocabulary = full_matrix(data, variant)
        for level in LEVELS:
            actual = [hierarchy_label(data["records"][identifier], level) for identifier in ids]
            k = len(set(actual))
            for method in METHOD_NAMES:
                config = _experiment_config(root, data, condition, level, method, matrix, vocabulary, ids)
                config["k"] = k
                signature = _signature(config)
                target = target_root / "experiments" / config["experiment"]
                target.mkdir(parents=True, exist_ok=True)
                saved = target / "experiment.json"
                if saved.is_file():
                    result = _read(saved)
                    if result.get("config_sha256") != signature:
                        raise ValueError(f"완료된 군집의 입력/설정이 다릅니다. 새 실험 경로가 필요합니다: {target}")
                    payload = {key: value for key, value in result.items() if key != "payload_sha256"}
                    if result.get("payload_sha256") != _signature(payload):
                        raise ValueError(f"완료된 군집의 배정/평가 기록이 변형되었습니다: {target}")
                    if not (target / "model.pt").is_file() or _hash(target / "model.pt") != result["model_sha256"]:
                        raise ValueError(f"완료된 군집 모델이 변형되었습니다: {target}")
                    print(f"전체265 군집 재사용: {config['experiment']}", flush=True)
                else:
                    if any(target.iterdir()):
                        raise ValueError(f"미완료 군집 폴더의 파일 출처를 확인할 수 없습니다: {target}")
                    fit = fit_kmeans if method == "euclidean" else fit_spherical_kmeans
                    objective = "inertia" if method == "euclidean" else "cosine_loss"
                    trials = [fit(matrix, k, MAX_ITER, TOLERANCE, seed) for seed in SEEDS]
                    best = min(range(len(trials)), key=lambda index: trials[index][objective])
                    selected = trials[best]
                    assignments = selected["assignments"].tolist()
                    majorities = majority_labels(assignments, actual)
                    documents = _documents(data, config["experiment"], condition, level, method,
                                           ids, assignments, actual, majorities)
                    restarts = []
                    for seed, trial in zip(SEEDS, trials):
                        groups = trial["assignments"].tolist()
                        majority = majority_labels(groups, actual)
                        restarts.append({"seed": seed, "training_objective": float(trial[objective]),
                            "iterations": int(trial["iterations"]), "assignments": groups,
                            "metrics": evaluate(groups, actual, majority, k)})
                    torch.save({"experiment": config["experiment"], "config_sha256": signature,
                        "dataset_id": data["dataset_id"], "centers": selected["centers"],
                        "assignments": selected["assignments"], "fit_ids": ids, "fit_scope": "all",
                        "input_vocabulary": vocabulary, "vocabulary": vocabulary,
                        "original_splits": data["ids"], "method": method, "k": k}, target / "model.pt")
                    result = {"experiment": config["experiment"], "condition": condition,
                        "level": level, "method": method, "k": k, "config": config,
                        "config_sha256": signature, "dataset_id": data["dataset_id"],
                        "fit_scope": "all", "evaluation_scope": "same_all_documents_not_generalization",
                        "selected_seed": SEEDS[best], "training_objective_name": objective,
                        "selected_training_objective": float(selected[objective]),
                        "selected_iterations": int(selected["iterations"]),
                        "restarts": restarts, "metrics": evaluate(assignments, actual, majorities, k),
                        "full_majority_labels": {str(key): value for key, value in majorities.items()},
                        "documents": documents, "model_sha256": _hash(target / "model.pt")}
                    result["payload_sha256"] = _signature(result)
                    write_json(saved, result)
                    print(f"전체265 {config['experiment']}: k={k}, seed={SEEDS[best]}, "
                          f"ARI={result['metrics']['ari']:.4f}", flush=True)
                summaries.append(result)
    from .clustering_reporting import render
    render(root, output, data, summaries)
    return summaries


def report(root, output, data):
    """저장된 배정만 읽어 문서와 그림을 다시 만든다. 모델 로딩·학습·재배정은 없다."""
    output = Path(output)
    saved = []
    for condition in CONDITIONS:
        for level in LEVELS:
            for method in METHOD_NAMES:
                path = output / "01_clustering/experiments" / f"{condition}_{level}_{method}/experiment.json"
                result = _read(path)
                if result["dataset_id"] != data["dataset_id"]:
                    raise ValueError(f"보고서의 데이터와 저장 군집이 다릅니다: {path}")
                payload = {key: value for key, value in result.items() if key != "payload_sha256"}
                if result.get("payload_sha256") != _signature(payload):
                    raise ValueError(f"보고서의 군집 배정/평가 기록이 변형되었습니다: {path}")
                saved.append(result)
    from .clustering_reporting import render
    render(Path(root), output, data, saved)
    return saved
