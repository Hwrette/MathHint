"""학습 문항 쌍의 거리와 기존 군집의 길이·노름 구성을 설명한다.

저장된 배정과 평가값은 읽기만 한다. 중심 계산, 군집 배정, 모델 로딩,
새 군집 평가나 API 호출은 하지 않는다.
"""

from collections import Counter
from pathlib import Path

import numpy as np

from ..common import dump_csv, read_csv
from ..statistics import LEVELS, variance_decomposition


def _moments(values):
    values = np.asarray(values, dtype=float)
    if not len(values):
        return {"mean": None, "median": None}
    return {"mean": float(values.mean()), "median": float(np.median(values))}


def _comparison(within, between):
    inside, outside = _moments(within), _moments(between)
    defined = inside["mean"] is not None and outside["mean"] is not None
    return {"within_pairs": len(within), "between_pairs": len(between),
            "within_mean": inside["mean"], "between_mean": outside["mean"],
            "within_median": inside["median"], "between_median": outside["median"],
            "between_minus_within": outside["mean"] - inside["mean"] if defined else None,
            "between_div_within": outside["mean"] / inside["mean"]
            if defined and inside["mean"] != 0 else None}


def pair_distance_summary(labels, pair_i, pair_j, distances, *, level, metric):
    """모든 i<j 쌍을 실제 분류에 따라 나누고, 집단별 보조표도 만든다."""
    labels = np.asarray(labels, dtype=str)
    pair_i, pair_j = np.asarray(pair_i, dtype=int), np.asarray(pair_j, dtype=int)
    distances = np.asarray(distances, dtype=float)
    expected_i, expected_j = np.triu_indices(len(labels), 1)
    if (not np.array_equal(pair_i, expected_i) or not np.array_equal(pair_j, expected_j)
            or distances.shape != pair_i.shape or not np.isfinite(distances).all()
            or (distances < 0).any()):
        raise ValueError("거리와 문항 쌍은 빠짐없는 i<j 순서의 유한 비음수 값이어야 합니다.")
    sizes = Counter(labels)
    same = labels[pair_i] == labels[pair_j]
    comparison = _comparison(distances[same], distances[~same])
    expected_within = sum(n * (n - 1) // 2 for n in sizes.values())
    if comparison["within_pairs"] != expected_within:
        raise ArithmeticError("분류별 크기로 계산한 내부 쌍 수와 실제 쌍 수가 다릅니다.")
    class_rows = []
    for label in sorted(sizes):
        first, second = labels[pair_i] == label, labels[pair_j] == label
        row = {"level": level, "metric": metric, "label": label, "n": sizes[label],
               **_comparison(distances[first & second], distances[first ^ second])}
        if row["between_pairs"] != sizes[label] * (len(labels) - sizes[label]):
            raise ArithmeticError("분류별 one-vs-rest 문항 쌍 수가 다릅니다.")
        class_rows.append(row)
    # 두 평균이 모두 정의되는 동일한 분류 집합에서만 macro 비교한다.
    comparable = [row for row in class_rows
                  if row["within_mean"] is not None and row["between_mean"] is not None]
    macro_inside = float(np.mean([row["within_mean"] for row in comparable])) if comparable else None
    macro_outside = float(np.mean([row["between_mean"] for row in comparable])) if comparable else None
    row = {"level": level, "level_name": LEVELS.get(level, (level, ()))[0],
           "metric": metric, "n": len(labels), "pair_count": len(distances),
           **comparison, "group_count": len(sizes),
           "singleton_groups": sum(n == 1 for n in sizes.values()),
           "macro_comparable_classes": len(comparable),
           "macro_excluded_classes": len(sizes) - len(comparable),
           "macro_within_mean": macro_inside, "macro_between_mean": macro_outside,
           "macro_between_minus_within": macro_outside - macro_inside if comparable else None,
           "macro_between_div_within": macro_outside / macro_inside
           if comparable and macro_inside != 0 else None}
    return row, class_rows


def _norm_fields(indices, geometry):
    result = {}
    for name in ("token_count", "l1", "l2"):
        values = np.asarray(geometry[name], dtype=float)[indices]
        result[name + "_mean"] = float(values.mean()) if len(values) else None
        result[name + "_variance"] = float(values.var(ddof=0)) if len(values) else None
    return result


def _correlation(x, y):
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    if len(x) < 2 or x.std() == 0 or y.std() == 0:
        return None
    return float(np.corrcoef(x, y)[0, 1])


def norm_distance_diagnostics(geometry):
    """거리-크기 차이의 기술적 상관과 유클리드 제곱거리의 항등식을 확인한다."""
    first, second = geometry["pair_i"], geometry["pair_j"]
    radii = np.asarray(geometry["l2"], dtype=float)
    radial = np.square(radii[first] - radii[second])
    directional = 2 * radii[first] * radii[second] * geometry["cosine"]
    squared = np.asarray(geometry["euclidean_squared"], dtype=float)
    if not np.allclose(squared, radial + directional, rtol=1e-11, atol=1e-11):
        raise ArithmeticError("제곱 유클리드 거리의 노름 차이 항등식이 성립하지 않습니다.")
    total = float(squared.sum())
    associations = []
    for metric in ("euclidean", "cosine"):
        values = geometry[metric]
        associations.append({"metric": metric, "pair_count": len(first),
            "pearson_distance_vs_abs_l2_difference": _correlation(values, np.abs(radii[first] - radii[second])),
            "pearson_distance_vs_abs_l1_difference": _correlation(values,
                np.abs(np.asarray(geometry["l1"])[first] - np.asarray(geometry["l1"])[second])),
            "independent_sample_size_claim": False})
    return {"pair_count": len(first), "mean_raw_euclidean_squared": float(squared.mean()) if len(first) else None,
            "mean_norm_difference_squared": float(radial.mean()) if len(first) else None,
            "mean_norm_scaled_direction_term": float(directional.mean()) if len(first) else None,
            "norm_difference_squared_share_pct": float(radial.sum() / total * 100) if total else None,
            "norm_scaled_direction_share_pct": float(directional.sum() / total * 100) if total else None,
            "radial_identity_verified": True,
            "identity": "||x-y||²=(||x||-||y||)²+2||x||||y||(1-cos(x,y))",
            "correlations": associations,
            "interpretation": "Descriptive associations only. Pairs share documents; no independent-pair p-value or causal claim."}


def read_cluster_context(root, output, geometry):
    """기존 test 평가값과 train 배정을 읽어 길이·크기 분포만 요약한다."""
    root, output = Path(root), Path(output)
    source = root / "results/final_experiment/01_clustering"
    original = [row for row in read_csv(source / "summary.csv") if row["split"] == "test"]
    if len(original) != 8:
        raise ValueError("기존 테스트 군집화 결과는 4수준×2방식의 8개여야 합니다.")
    members = read_csv(source / "cluster_members.csv")
    ids = list(geometry["ids"])
    positions = {identifier: i for i, identifier in enumerate(ids)}
    if len(positions) != len(ids):
        raise ValueError("학습 문항 ID가 중복됩니다.")
    metrics, cluster_rows, associations = [], [], []
    norm_matrix = np.column_stack([geometry[name] for name in ("token_count", "l1", "l2")])
    for row in original:
        experiment, level, method, k = row["experiment"], row["level"], row["method"], int(row["k"])
        rows = [member for member in members
                if member["experiment"] == experiment and member["split"] == "train"]
        if [member["id"] for member in rows] != ids:
            raise ValueError(f"{experiment}: 저장된 학습 배정의 ID·행 순서가 다릅니다.")
        if ([member["actual_label"] for member in rows] != list(geometry["labels_by_level"][level])
                or any(member["level"] != level or member["method"] != method for member in rows)):
            raise ValueError(f"{experiment}: 저장된 실제 계층 라벨이 원본 메타데이터와 다릅니다.")
        clusters = [int(member["cluster"]) for member in rows]
        if any(cluster < 0 or cluster >= k for cluster in clusters):
            raise ValueError(f"{experiment}: 저장된 군집 번호의 범위가 잘못됐습니다.")
        metrics.append({key: row[key] for key in (
            "experiment", "level", "level_name", "method", "method_name", "k", "n", "ari", "nmi",
            "train_majority_accuracy", "selected_seed")})
        metrics[-1].update(train_n=len(ids), source_csv="results/final_experiment/01_clustering/summary.csv")
        for cluster in range(k):
            indices = [positions[member["id"]] for member in rows if int(member["cluster"]) == cluster]
            cluster_rows.append({"experiment": experiment, "level": level, "method": method,
                                 "cluster": cluster, "n": len(indices), **_norm_fields(indices, geometry)})
        decomposed = variance_decomposition(norm_matrix, clusters)
        associations.append({"experiment": experiment, "level": level, "method": method, "k": k,
                             "n": len(ids), "occupied_clusters": len(set(clusters)),
                             **{name + "_eta_squared": float(decomposed["eta_squared"][i])
                                if np.isfinite(decomposed["eta_squared"][i]) else None
                                for i, name in enumerate(("token_count", "l1", "l2"))}})
    dump_csv(output / "old_clustering_metrics.csv", metrics)
    dump_csv(output / "cluster_norm_summary.csv", cluster_rows)
    dump_csv(output / "cluster_norm_association.csv", associations)
    return metrics, associations


def build_context(root, output, geometry=None):
    """새 분석 폴더에만 쌍거리·분류 크기·기존 군집 맥락을 저장한다."""
    from .geometry import load_geometry

    root, output = Path(root), Path(output)
    geometry = load_geometry(root) if geometry is None else geometry
    pair_i, pair_j = geometry["pair_i"], geometry["pair_j"]
    summaries, class_rows, norm_rows = [], [], []
    for level, labels in geometry["labels_by_level"].items():
        labels = list(labels)
        for metric in ("euclidean", "cosine"):
            summary, individual = pair_distance_summary(labels, pair_i, pair_j, geometry[metric],
                                                       level=level, metric=metric)
            summaries.append(summary)
            class_rows.extend(individual)
        for label in sorted(set(labels)):
            indices = [i for i, actual in enumerate(labels) if actual == label]
            norm_rows.append({"level": level, "level_name": LEVELS[level][0], "label": label,
                              "n": len(indices), **_norm_fields(indices, geometry)})
    dump_csv(output / "within_between_distances.csv", summaries)
    dump_csv(output / "class_pair_distances.csv", class_rows)
    dump_csv(output / "class_norm_summary.csv", norm_rows)
    dump_csv(output / "document_pair_distances.csv", [
        {"id_i": geometry["ids"][int(a)], "id_j": geometry["ids"][int(b)],
         "euclidean": float(geometry["euclidean"][i]),
         "euclidean_squared": float(geometry["euclidean_squared"][i]),
         "cosine": float(geometry["cosine"][i]),
         **{"same_" + level: labels[int(a)] == labels[int(b)]
            for level, labels in geometry["labels_by_level"].items()}}
        for i, (a, b) in enumerate(zip(pair_i, pair_j))])
    existing, cluster_associations = read_cluster_context(root, output, geometry)
    diagnostics = norm_distance_diagnostics(geometry)
    dump_csv(output / "length_distance_association.csv", diagnostics["correlations"])
    return {"n": len(geometry["ids"]), "pair_count": len(pair_i),
            "within_between": summaries, "existing_test_metrics": existing,
            "train_token_count_equals_l1": bool(np.array_equal(geometry["token_count"], geometry["l1"])),
            "cluster_norm_association": cluster_associations,
            "norm_distance_diagnostics": diagnostics,
            "definitions": {
                "euclidean": "sqrt(sum_j (x_ij-x_kj)^2), raw count units; not squared in within/between tables",
                "cosine": "1-cos(x_i,x_k), dimensionless",
                "ratio_comparison_limit": "Ratios remove units but are not invariant to nonlinear transforms. Cosine is half the squared normalized Euclidean distance; a larger ratio alone does not prove better class separation or K-means performance.",
                "pooled_weighting": "All distinct i<j pairs, each pair weight1; large classes contribute n_g(n_g-1)/2 within pairs",
                "macro_weighting": "Equal weight per class with both within and one-vs-rest between means defined; same subset on both sides",
                "class_between_scope": "One-vs-rest; summing class between counts counts every cross-class pair twice",
                "undefined": "Empty pair sets and ratios with zero denominator are null/blank, never imputed",
                "sample_independence": "17020 pairs share 185 documents, so they are not 17020 independent observations",
                "cluster_norm_eta": "Descriptive norm variance explained by stored train cluster groups; arbitrary cluster numbers are not correlated numerically",
                "cluster_count_limit": "More groups can inflate eta-squared. Compare stored distance methods at the same level/k; do not interpret larger-k norm eta as stronger causal evidence.",
                "norm_variance_denominator": "n, population variance ddof=0",
                "model_execution": "No training, reassignment, model loading, or new ARI/NMI calculation; old metrics are read from CSV only"}}
