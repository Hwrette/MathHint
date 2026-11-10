"""거리 비교표를 원본 학습 좌표에서 독립 대조한다. 모델은 사용하지 않는다."""

from collections import Counter
from pathlib import Path
import math

import numpy as np

from ..common import dump_json, load_data, read_csv, read_json
from ..validation import scan_report_links, verify_sources


def verify(root, output, *, save=True):
    root, output = Path(root), Path(output)
    config = read_json(output / "config.json")
    protected = verify_sources(root, config)
    data = load_data(root)
    ids, vocabulary = data["ids"]["train"], data["vocabularies"]["problems"]
    x = data["arrays"]["problems"]["train"].astype(float)
    norms = np.sqrt(np.einsum("ij,ij->i", x, x))
    if (norms == 0).any():
        raise ValueError("영벡터가 있어 코사인 통계를 검증할 수 없습니다.")
    z = x / norms[:, None]
    first, second = np.triu_indices(len(x), 1)
    raw_coordinates = (x[first] - x[second]) ** 2
    normalized_coordinates = .5 * (z[first] - z[second]) ** 2
    squared, cosine = raw_coordinates.sum(axis=1), normalized_coordinates.sum(axis=1)
    ordinary = np.sqrt(squared)
    dot_distance = 1 - np.sum(z[first] * z[second], axis=1)
    raw_share = raw_coordinates.mean(axis=0) / squared.mean() * 100
    cosine_share = normalized_coordinates.mean(axis=0) / cosine.mean() * 100
    checks = []

    def check(name, condition):
        checks.append({"check": name, "passed": bool(condition)})

    def close(a, b):
        if b is None:
            return a in (None, "")
        return a not in (None, "") and math.isclose(float(a), float(b), rel_tol=1e-9, abs_tol=1e-11)

    check("fixed_training_185_by_346", x.shape == (185, 346) and len(set(ids)) == 185)
    check("all_17020_unique_nonself_pairs", len(first) == 17020 and np.all(first < second))
    check("cosine_coordinate_dot_identity", np.allclose(cosine, dot_distance, atol=1e-12, rtol=1e-11))
    check("two_contribution_sums_100_percent", close(raw_share.sum(), 100) and close(cosine_share.sum(), 100))
    contributions = read_csv(output / "token_distance_contributions.csv")
    check("token_indices_and_order", [(int(r["index"]), r["token"]) for r in contributions] == list(enumerate(vocabulary)))
    raw_ranks = {i: rank for rank, i in enumerate(sorted(range(346), key=lambda i: (-raw_share[i], i)), 1)}
    cosine_ranks = {i: rank for rank, i in enumerate(sorted(range(346), key=lambda i: (-cosine_share[i], i)), 1)}
    for i, row in enumerate(contributions):
        check(f"token_{i}_contributions_variances_and_ranks", all((
            close(row["original_variance"], x[:, i].var()), close(row["normalized_variance"], z[:, i].var()),
            close(row["euclidean_contribution"], raw_share[i]), close(row["cosine_contribution"], cosine_share[i]),
            close(row["pair_mean_euclidean_squared_coordinate"], raw_coordinates[:, i].mean()),
            close(row["pair_mean_cosine_coordinate"], normalized_coordinates[:, i].mean()),
            close(row["contribution_difference"], cosine_share[i] - raw_share[i]),
            int(row["euclidean_rank"]) == raw_ranks[i], int(row["cosine_rank"]) == cosine_ranks[i],
            int(row["rank_change"]) == raw_ranks[i] - cosine_ranks[i])))

    pair_rows = read_csv(output / "document_pair_distances.csv")
    check("all_pair_rows_once", len(pair_rows) == len(first))
    fields = ("curriculum", "unit", "subunit", "type")
    labels_by_level = {level: np.asarray([" / ".join(data["records"][identifier][key] for key in fields[:number])
                                        for identifier in ids]) for number, level in enumerate(fields, 1)}
    check("all_pair_values_and_hierarchy_flags", len(pair_rows) == 17020 and all(
        r["id_i"] == ids[a] and r["id_j"] == ids[b] and close(r["euclidean_squared"], squared[i])
        and close(r["euclidean"], ordinary[i]) and close(r["cosine"], cosine[i])
        and all((r["same_" + level] == "True") == bool(labels[a] == labels[b])
                for level, labels in labels_by_level.items())
        for i, (r, a, b) in enumerate(zip(pair_rows, first, second))))

    eta_rows = read_csv(output / "normalized_eta_comparison.csv")
    check("four_levels_eta_rows", len(eta_rows) == 1384)
    pooled = read_csv(output / "within_between_distances.csv")
    check("four_levels_two_metrics", len(pooled) == 8)
    for level, labels in labels_by_level.items():
        sizes = Counter(labels)
        for prefix, matrix in (("original", x), ("normalized", z)):
            total = np.mean((matrix - matrix.mean(axis=0)) ** 2, axis=0)
            group_means = {label: matrix[labels == label].mean(axis=0) for label in sizes}
            fitted = np.stack([group_means[label] for label in labels])
            between = np.mean((fitted - matrix.mean(axis=0)) ** 2, axis=0)
            within = np.mean((matrix - fitted) ** 2, axis=0)
            rows = [r for r in eta_rows if r["level"] == level]
            valid = len(rows) == 346 and np.allclose(total, between + within, atol=1e-11, rtol=1e-10)
            for i, row in enumerate(rows):
                eta = between[i] / total[i] if total[i] else None
                adjusted = 1 - (1 - eta) * 184 / (185 - len(sizes)) if eta is not None else None
                valid &= int(row["index"]) == i and row["token"] == vocabulary[i]
                valid &= close(row[prefix + "_total_variance"], total[i]) and close(row[prefix + "_between_variance"], between[i])
                valid &= close(row[prefix + "_within_variance"], within[i]) and close(row[prefix + "_eta_squared"], eta)
                valid &= close(row[prefix + "_adjusted_eta_squared"], adjusted) and int(row["train_df"]) == np.count_nonzero(x[:, i])
                valid &= int(row["n"]) == 185 and int(row["group_count"]) == len(sizes)
            check(level + "_" + prefix + "_independent_variance_projection", valid)
        check(level + "_eta_changes", all(close(r["eta_difference"], float(r["normalized_eta_squared"]) - float(r["original_eta_squared"]))
              if r["normalized_eta_squared"] and r["original_eta_squared"] else r["eta_difference"] == ""
              for r in eta_rows if r["level"] == level))
        same = labels[first] == labels[second]
        for metric, distances in (("euclidean", ordinary), ("cosine", cosine)):
            row = next(r for r in pooled if r["level"] == level and r["metric"] == metric)
            inside, outside = distances[same], distances[~same]
            check(level + metric + "_within_between", int(row["within_pairs"]) == int(same.sum())
                  and int(row["between_pairs"]) == int((~same).sum())
                  and int(same.sum()) == sum(n * (n - 1) // 2 for n in sizes.values())
                  and close(row["within_mean"], inside.mean() if len(inside) else None)
                  and close(row["between_mean"], outside.mean() if len(outside) else None)
                  and close(row["within_median"], np.median(inside) if len(inside) else None)
                  and close(row["between_median"], np.median(outside) if len(outside) else None)
                  and close(row["between_minus_within"], outside.mean() - inside.mean())
                  and close(row["between_div_within"], outside.mean() / inside.mean() if len(inside) and inside.mean() else None)
                  and int(row["singleton_groups"]) == sum(n == 1 for n in sizes.values()))

    original = {r["experiment"]: r for r in read_csv(root / "results/final_experiment/01_clustering/summary.csv") if r["split"] == "test"}
    old_metrics = read_csv(output / "old_clustering_metrics.csv")
    check("old_test_metrics_read_not_recomputed", len(old_metrics) == 8
          and {r["experiment"] for r in old_metrics} == set(original) and all(
        all(close(r[key], original[r["experiment"]][key]) for key in ("ari", "nmi", "train_majority_accuracy")) and int(r["n"]) == 80
        for r in old_metrics))
    for region in ("problem", "solution"):
        check(region + "_selection_file_unchanged_and_empty", read_json(root / f"results/token_analysis/stopwords/{region}_stopwords.json") == [])
    links, missing = scan_report_links(output)
    check("all_new_report_links", not missing)
    check("new_reading_documents", (output / "README.md").is_file() and (output / "clustering_context.md").is_file())
    check("new_figures_present", len(list((output / "figures").glob("*.png"))) >= 7)
    result = {"passed": sum(c["passed"] for c in checks), "failed": sum(not c["passed"] for c in checks),
              "checks": checks, "n": 185, "dimensions": 346, "pair_count": len(first), "zero_vectors": 0,
              "protected_original_files": protected, "all_original_source_hashes_unchanged": True,
              "relative_links_checked": links, "missing_links": missing, "models_trained": 0,
              "new_cluster_assignments": 0, "model_checkpoint_loads": 0, "new_gemini_calls": 0,
              "limits": "Descriptive fixed-training statistics; no causal attribution, token-removal or new clustering experiment."}
    if save:
        dump_json(output / "validation.json", result)
    return result
