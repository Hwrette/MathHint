"""학습 문제로 K-means 군집을 만들고, 테스트 문제의 실제 단원·유형과 비교합니다.

아래 설정값을 바꾼 뒤 이 파일을 실행하세요. 저장된 학습·테스트 분할을 그대로 씁니다.
"""

from collections import Counter
import json
from pathlib import Path

import torch
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs/kmeans"
N_CLUSTERS = 8
MAX_ITER = 100
TOLERANCE = 0.0001
RESTARTS = 5
SEED = 42


def assign_clusters(matrix, centers):
    """각 문제를 가장 가까운 군집 중심에 배정합니다."""
    return torch.cdist(matrix, centers).argmin(dim=1)


def fit_kmeans(matrix, n_clusters=N_CLUSTERS, max_iter=MAX_ITER,
               tol=TOLERANCE, seed=SEED):
    """가까운 중심에 배정하고, 군집의 평균으로 중심을 옮기는 과정을 반복합니다."""
    matrix = matrix.detach().to(device="cpu", dtype=torch.float32)
    unique_rows = torch.unique(matrix, dim=0)
    generator = torch.Generator().manual_seed(seed)
    selected = torch.randperm(len(unique_rows), generator=generator)[:n_clusters]
    centers = unique_rows[selected].clone()

    for iteration in range(1, max_iter + 1):
        distances = torch.cdist(matrix, centers)
        assignments = distances.argmin(dim=1)
        updated = centers.clone()
        nearest_distances = distances.min(dim=1).values.clone()

        for cluster in range(n_clusters):
            members = matrix[assignments == cluster]
            if len(members):
                updated[cluster] = members.mean(dim=0)
            else:
                # 빈 군집은 현재 중심에서 가장 멀리 떨어진 문제로 옮깁니다.
                farthest = nearest_distances.argmax()
                updated[cluster] = matrix[farthest]
                nearest_distances[farthest] = -1

        movement = torch.linalg.vector_norm(updated - centers, dim=1).max().item()
        centers = updated
        if movement <= tol:
            break

    # 마지막으로 옮긴 중심을 기준으로 군집 번호를 다시 계산합니다.
    assignments = assign_clusters(matrix, centers)
    inertia = ((matrix - centers[assignments]) ** 2).sum().item()
    return {"centers": centers, "assignments": assignments,
            "inertia": inertia, "iterations": iteration}


def main():
    if __package__:
        from .TorchData import load_fixed_dataset
    else:
        from TorchData import load_fixed_dataset

    # 1. 저장된 학습·테스트 문제 벡터와 실제 분류를 읽습니다.
    torch.set_num_threads(2)
    data = load_fixed_dataset(ROOT)
    X_train = data["arrays"]["problems"]["train"]
    X_test = data["arrays"]["problems"]["test"]
    ids, records = data["ids"], data["records"]

    # 2. 초기 중심을 바꿔 보고, 학습 군집 내 거리 합이 가장 작은 결과를 씁니다.
    trials = [fit_kmeans(X_train, N_CLUSTERS, MAX_ITER, TOLERANCE, SEED + i)
              for i in range(RESTARTS)]
    best = min(range(RESTARTS), key=lambda i: trials[i]["inertia"])
    fitted = trials[best]
    assignments = {"train": fitted["assignments"].tolist(),
                   "test": assign_clusters(X_test, fitted["centers"]).tolist()}

    # 3. 군집 번호를 실제 과목·단원·유형과 비교합니다. 다수 라벨도 학습에서만 정합니다.
    metrics = {"train": {}, "test": {}}
    label_maps = {}
    for field in ("subject", "unit", "type"):
        train_labels = [records[item_id][field] for item_id in ids["train"]]
        groups = {}
        for cluster, label in zip(assignments["train"], train_labels):
            groups.setdefault(cluster, []).append(label)
        label_maps[field] = {}
        for cluster, labels in groups.items():
            counts = Counter(labels)
            label_maps[field][cluster] = sorted(counts, key=lambda label: (-counts[label], label))[0]
        for part in ("train", "test"):
            labels = [records[item_id][field] for item_id in ids[part]]
            predicted = [label_maps[field].get(c) for c in assignments[part]]
            metrics[part][field] = {
                "adjusted_rand_index": adjusted_rand_score(labels, assignments[part]),
                "normalized_mutual_information": normalized_mutual_info_score(labels, assignments[part]),
                "accuracy_using_train_cluster_majority": sum(a == b for a, b in zip(labels, predicted)) / len(labels),
            }

    # 4. 중심, 문항별 군집 번호, 평가 결과를 저장합니다.
    OUTPUT.mkdir(parents=True, exist_ok=True)
    config = {"n_clusters": N_CLUSTERS, "seeds": [SEED + i for i in range(RESTARTS)],
              "selected_seed": SEED + best, "max_iter": MAX_ITER, "tol": TOLERANCE,
              "fit_split": "train", "selection": "lowest_training_inertia_only"}
    torch.save({"centers": fitted["centers"], "vocabulary": data["vocabularies"]["problems"],
                "train_ids": ids["train"], "generation_id": data["generation_id"], "config": config},
               OUTPUT / "kmeans_model.pt")
    documents = [{"id": item_id, "split": part, "cluster": cluster,
                  "actual_labels": {field: records[item_id][field] for field in label_maps}}
                 for part in ("train", "test") for item_id, cluster in zip(ids[part], assignments[part])]
    results = {"clusters.json": {"documents": documents, "train_majority_label_maps": label_maps},
               "clustering_metrics.json": {"train_count": len(ids["train"]), "test_count": len(ids["test"]),
                                            "config": config, "metrics": metrics, "train_inertia": fitted["inertia"]}}
    for filename, value in results.items():
        (OUTPUT / filename).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"학습 {len(ids['train'])}개 / 테스트 {len(ids['test'])}개, 군집 {N_CLUSTERS}개")
    print("테스트 유형 평가:", metrics["test"]["type"])
    print("저장 위치:", OUTPUT)


if __name__ == "__main__":
    main()
