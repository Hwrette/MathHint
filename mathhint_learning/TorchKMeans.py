"""학습 문제로 K-means 군집을 만들고, 실제 소단원과 비교합니다.

아래 설정값을 바꾼 뒤 이 파일을 실행하세요. 저장된 학습·테스트 분할을 그대로 씁니다.
"""

from collections import Counter
import json
from pathlib import Path

import torch
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs/kmeans"
N_CLUSTERS = None  # None이면 학습 자료의 실제 소단원 수로 자동 설정한다.
MAX_ITER = 100
TOLERANCE = 0.0001
RESTARTS = 5
SEED = 42


def assign_clusters(matrix, centers):
    """각 문제를 가장 가까운 군집 중심에 배정합니다."""
    return torch.cdist(matrix, centers).argmin(dim=1)


def fit_kmeans(matrix, n_clusters=8, max_iter=MAX_ITER,
               tol=TOLERANCE, seed=SEED):
    """가까운 중심에 배정하고, 군집의 평균으로 중심을 옮기는 과정을 반복합니다."""
    matrix = matrix.detach().to(device="cpu", dtype=torch.float32)
    _validate_fit(matrix, n_clusters, max_iter)
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


def _validate_fit(matrix, n_clusters, max_iter):
    if matrix.ndim != 2 or not len(matrix) or not torch.isfinite(matrix).all():
        raise ValueError("군집 입력은 비어 있지 않은 유한한 2차원 행렬이어야 합니다.")
    if not 1 <= n_clusters <= len(torch.unique(matrix, dim=0)):
        raise ValueError("군집 수는 1 이상, 고유 학습 벡터 수 이하여야 합니다.")
    if max_iter < 1:
        raise ValueError("최소 한 번은 중심을 갱신해야 합니다.")


def l2_normalize(matrix):
    """영벡터는 그대로 두고 각 행을 단위 길이로 만든다."""
    return torch.nn.functional.normalize(matrix, p=2, dim=1, eps=1e-12)


def assign_spherical(matrix, centers):
    """코사인 유사도가 최대인 중심에 배정한다. 영벡터·동률은 작은 번호다."""
    return (l2_normalize(matrix) @ l2_normalize(centers).T).argmax(dim=1)


def fit_spherical_kmeans(matrix, n_clusters=8, max_iter=MAX_ITER,
                          tol=TOLERANCE, seed=SEED):
    """입력과 매번 갱신한 중심을 정규화하는 Spherical K-means.

    유클리드 방식과 같은 원시 고유 행 순서 및 시드에서 초기 중심을 뽑는다.
    영벡터의 유사도는 0으로 정의한다. 빈 군집은 현재 중심들과의 최대
    유사도가 가장 낮은 영벡터 아닌 학습 문항으로 재초기화한다.
    """
    matrix = matrix.detach().to(device="cpu", dtype=torch.float32)
    _validate_fit(matrix, n_clusters, max_iter)
    unique_rows = torch.unique(matrix, dim=0)
    generator = torch.Generator().manual_seed(seed)
    selected = torch.randperm(len(unique_rows), generator=generator)[:n_clusters]
    centers = l2_normalize(unique_rows[selected].clone())
    normalized = l2_normalize(matrix)
    nonzero = torch.linalg.vector_norm(matrix, dim=1) > 0

    for iteration in range(1, max_iter + 1):
        similarities = normalized @ centers.T
        assignments = similarities.argmax(dim=1)
        updated = centers.clone()
        nearest_similarity = similarities.max(dim=1).values.clone()
        nearest_similarity[~nonzero] = float("inf")
        for cluster in range(n_clusters):
            members = normalized[assignments == cluster]
            if len(members):
                updated[cluster] = l2_normalize(members.sum(dim=0, keepdim=True))[0]
            elif nonzero.any():
                farthest = nearest_similarity.argmin()
                updated[cluster] = normalized[farthest]
                nearest_similarity[farthest] = float("inf")
        updated = l2_normalize(updated)
        movement = torch.linalg.vector_norm(updated - centers, dim=1).max().item()
        centers = updated
        if movement <= tol:
            break

    assignments = assign_spherical(matrix, centers)
    cosine_loss = (1 - (normalized * centers[assignments]).sum(dim=1)).sum().item()
    return {"centers": centers, "assignments": assignments,
            "cosine_loss": cosine_loss, "iterations": iteration}


def subunit_label(record):
    """다른 단원의 동명 소단원이 섞이지 않도록 상위 분류도 함께 사용한다."""
    return " / ".join(record.get(field, "") for field in ("curriculum", "unit", "subunit"))


def main():
    if __package__:
        from .TorchData import load_fixed_dataset
        from .ClusterReport import save_cluster_reports
    else:
        from TorchData import load_fixed_dataset
        from ClusterReport import save_cluster_reports

    # 1. 저장된 학습·테스트 문제 벡터와 실제 분류를 읽습니다.
    torch.set_num_threads(2)
    data = load_fixed_dataset(ROOT)
    X_train = data["arrays"]["problems"]["train"]
    X_test = data["arrays"]["problems"]["test"]
    ids, records = data["ids"], data["records"]
    train_subunits = {subunit_label(records[item_id]) for item_id in ids["train"]}
    test_subunits = {subunit_label(records[item_id]) for item_id in ids["test"]}
    n_clusters = len(train_subunits) if N_CLUSTERS is None else N_CLUSTERS

    # 2. 소단원 수만큼 군집을 만든다. 초기값 선택에도 학습 데이터만 쓴다.
    trials = [fit_kmeans(X_train, n_clusters, MAX_ITER, TOLERANCE, SEED + i)
              for i in range(RESTARTS)]
    best = min(range(RESTARTS), key=lambda i: trials[i]["inertia"])
    fitted = trials[best]
    assignments = {"train": fitted["assignments"].tolist(),
                   "test": assign_clusters(X_test, fitted["centers"]).tolist()}

    # 3. 군집과 소단원의 일치도를 비교한다. 군집 번호 자체는 소단원 번호가 아니다.
    metrics = {"train": {}, "test": {}}
    label_maps = {}
    for field in ("subject", "unit", "subunit", "type"):
        labels_by_part = {
            part: [subunit_label(records[item_id]) if field == "subunit"
                   else records[item_id][field] for item_id in ids[part]]
            for part in ("train", "test")
        }
        train_labels = labels_by_part["train"]
        groups = {}
        for cluster, label in zip(assignments["train"], train_labels):
            groups.setdefault(cluster, []).append(label)
        label_maps[field] = {}
        for cluster, labels in groups.items():
            counts = Counter(labels)
            label_maps[field][cluster] = sorted(counts, key=lambda label: (-counts[label], label))[0]
        for part in ("train", "test"):
            labels = labels_by_part[part]
            predicted = [label_maps[field].get(c) for c in assignments[part]]
            metrics[part][field] = {
                "adjusted_rand_index": adjusted_rand_score(labels, assignments[part]),
                "normalized_mutual_information": normalized_mutual_info_score(labels, assignments[part]),
                "accuracy_using_train_cluster_majority": sum(a == b for a, b in zip(labels, predicted)) / len(labels),
                "label_count": len(set(labels)),
                "occupied_cluster_count": len(set(assignments[part])),
            }

    # 4. 중심·문항별 배정·평가와 군집별 문항 목록을 저장한다.
    OUTPUT.mkdir(parents=True, exist_ok=True)
    config = {"n_clusters": n_clusters, "seeds": [SEED + i for i in range(RESTARTS)],
              "selected_seed": SEED + best, "max_iter": MAX_ITER, "tol": TOLERANCE,
              "fit_split": "train", "selection": "lowest_training_inertia_only",
              "cluster_count_source": "training_subunit_count" if N_CLUSTERS is None else "manual_override",
              "subunit_definition": ["curriculum", "unit", "subunit"],
              "train_subunit_count": len(train_subunits), "test_subunit_count": len(test_subunits),
              "all_subunit_count": len(train_subunits | test_subunits)}
    torch.save({"centers": fitted["centers"], "vocabulary": data["vocabularies"]["problems"],
                "train_ids": ids["train"], "generation_id": data["generation_id"], "config": config},
               OUTPUT / "kmeans_model.pt")
    documents = []
    for part in ("train", "test"):
        for item_id, cluster in zip(ids[part], assignments[part]):
            record = records[item_id]
            labels = {field: subunit_label(record) if field == "subunit" else record[field] for field in label_maps}
            documents.append({"id": item_id, "split": part, "cluster": cluster,
                              "actual_labels": labels,
                              "train_majority_predicted_labels": {field: label_maps[field].get(cluster) for field in label_maps},
                              "curriculum": record.get("curriculum", ""), "unit": record.get("unit", ""),
                              "subunit": record.get("subunit", ""), "type": record.get("type", ""),
                              "source": record.get("source", ""), "source_file": record.get("source_file", ""),
                              "original_number": record.get("original_number"), "current_number": record.get("current_number")})
    results = {"clusters.json": {"config": config, "documents": documents, "train_majority_label_maps": label_maps},
               "clustering_metrics.json": {"train_count": len(ids["train"]), "test_count": len(ids["test"]),
                                            "config": config, "metrics": metrics, "train_inertia": fitted["inertia"]}}
    for filename, value in results.items():
        (OUTPUT / filename).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    save_cluster_reports(ROOT, OUTPUT, documents, n_clusters)
    print(f"학습 {len(ids['train'])}개 / 테스트 {len(ids['test'])}개, 군집 {n_clusters}개")
    print(f"실제 소단원: 학습 {len(train_subunits)}개 / 테스트 {len(test_subunits)}개")
    print("테스트 소단원 평가:", metrics["test"]["subunit"])
    print("저장 위치:", OUTPUT)


if __name__ == "__main__":
    main()
