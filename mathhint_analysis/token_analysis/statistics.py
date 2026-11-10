"""고정 어휘의 빈도·학습 분류별 분산·중복 좌표를 분석한다.

이 모듈에는 불용어 선택, 벡터 변환 또는 모델 실행 기능이 없다.
"""

from pathlib import Path

import numpy as np


LEVELS = {
    "curriculum": ("과목", ("curriculum",)),
    "unit": ("단원", ("curriculum", "unit")),
    "subunit": ("세부단원", ("curriculum", "unit", "subunit")),
    "type": ("문제 유형", ("curriculum", "unit", "subunit", "type")),
}
REQUESTED_PAIRS = (
    ("latex:{", "latex:}"),
    (r"latex:\left", r"latex:\right"),
    ("latex:(", "latex:)"),
)
REDUNDANCY_FIELDS = (
    "index_a", "token_a", "index_b", "token_b", "n", "selection_reason", "exact_equal",
    "counts_equal_documents", "pearson_correlation", "max_abs_difference", "mean_abs_difference",
    "variance_a", "variance_b", "pair_distance_contribution_ratio", "constant_pattern",
)


def token_moments(train, test):
    """TF=횟수 합, DF=양수 문항 수; 분산은 각 범위의 문항 수로 나눈다."""
    train, test = np.asarray(train, dtype=np.float64), np.asarray(test, dtype=np.float64)
    if train.ndim != 2 or test.ndim != 2 or not len(train) or not len(test) or train.shape[1] != test.shape[1]:
        raise ValueError("빈도가 비어 있거나 학습·테스트의 어휘 차원이 다릅니다.")
    combined = np.concatenate((train, test))
    variance = train.var(axis=0, ddof=0)
    denominator = float(variance.sum())
    return {
        "train_tf": train.sum(axis=0).astype(np.int64), "train_df": (train > 0).sum(axis=0),
        "test_tf": test.sum(axis=0).astype(np.int64), "test_df": (test > 0).sum(axis=0),
        "total_tf": combined.sum(axis=0).astype(np.int64), "total_df": (combined > 0).sum(axis=0),
        "mean": combined.mean(axis=0), "variance": combined.var(axis=0, ddof=0),
        "std": combined.std(axis=0, ddof=0), "train_mean": train.mean(axis=0),
        "train_variance": variance, "train_std": train.std(axis=0, ddof=0),
        "train_distance_contribution_ratio": np.divide(variance, denominator, out=np.full_like(variance, np.nan), where=denominator > 0),
        "mean_pair_squared_distance_train": variance * (2 * len(train) / (len(train) - 1)) if len(train) > 1 else np.full_like(variance, np.nan),
    }


def variance_decomposition(matrix, labels):
    """가중 집단 간·집단 내 제곱합을 같은 n으로 나누어 분산을 분해한다."""
    matrix = np.asarray(matrix, dtype=np.float64)
    if matrix.ndim != 2 or len(matrix) != len(labels) or not len(matrix):
        raise ValueError("문항 행과 분류 라벨이 대응하지 않습니다.")
    unique = sorted(set(labels))
    positions = {label: np.flatnonzero(np.asarray(labels) == label) for label in unique}
    n, g = len(matrix), len(unique)
    mean = matrix.mean(axis=0)
    total_ss = np.square(matrix - mean).sum(axis=0)
    between_ss, within_ss = np.zeros(matrix.shape[1]), np.zeros(matrix.shape[1])
    groups = []
    for label, indices in positions.items():
        group = matrix[indices]
        group_mean = group.mean(axis=0)
        between_ss += len(group) * np.square(group_mean - mean)
        within_ss += np.square(group - group_mean).sum(axis=0)
        groups.append({"label": label, "n": len(group), "mean": group_mean,
                       "df": (group > 0).sum(axis=0)})
    if not np.allclose(total_ss, between_ss + within_ss, rtol=1e-12, atol=1e-10):
        raise ArithmeticError("집단 간·집단 내 제곱합이 전체 제곱합과 다릅니다.")
    eta = np.divide(between_ss, total_ss, out=np.full(matrix.shape[1], np.nan), where=total_ss > 0)
    eta = bounded_eta(eta)
    adjusted = 1 - (1 - eta) * (n - 1) / (n - g) if n > g else np.full_like(eta, np.nan)
    return {"n": n, "group_count": g, "groups": groups, "mean": mean,
            "total_variance": total_ss / n, "between_variance": between_ss / n,
            "within_variance": within_ss / n, "eta_squared": eta,
            "adjusted_eta_squared": adjusted}


def bounded_eta(values, tolerance=1e-12):
    """η² 이론 경계 근처의 기계 오차만 정리한다. 정의 불가 값은 보존한다."""
    values = np.asarray(values, dtype=np.float64).copy()
    finite = values[np.isfinite(values)]
    if np.any(finite < -tolerance) or np.any(finite > 1 + tolerance):
        raise ArithmeticError("η²가 허용 가능한 부동소수점 오차를 넘어 이론 범위 밖입니다.")
    values[np.isclose(values, 0, rtol=0, atol=tolerance)] = 0
    values[np.isclose(values, 1, rtol=0, atol=tolerance)] = 1
    return values


def redundancy_pairs(matrix, vocabulary, threshold=.98):
    """빈도 완전일치·높은 양의 상관·명시 쌍만 기록한다. 좌표를 합치지 않는다."""
    matrix = np.asarray(matrix, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[1] != len(vocabulary):
        raise ValueError("중복성 분석의 어휘와 벡터 열이 다릅니다.")
    centered = matrix - matrix.mean(axis=0)
    norms = np.sqrt(np.square(centered).sum(axis=0))
    denominator = np.outer(norms, norms)
    correlations = np.divide(centered.T @ centered, denominator,
                             out=np.full_like(denominator, np.nan), where=denominator > 0)
    correlations = np.clip(correlations, -1, 1)
    variance = matrix.var(axis=0, ddof=0)
    total_variance = float(variance.sum())
    requested = {frozenset(pair) for pair in REQUESTED_PAIRS}
    rows = []
    for a in range(len(vocabulary)):
        for b in range(a + 1, len(vocabulary)):
            difference = np.abs(matrix[:, a] - matrix[:, b])
            exact = bool(np.all(difference == 0))
            correlation = correlations[a, b]
            named = frozenset((vocabulary[a], vocabulary[b])) in requested
            if not (exact or (np.isfinite(correlation) and correlation >= threshold) or named):
                continue
            reasons = []
            if exact:
                reasons.append("exact_equal")
            if np.isfinite(correlation) and correlation >= threshold:
                reasons.append("pearson_ge_0.98")
            if named:
                reasons.append("requested_pair")
            rows.append({"index_a": a, "token_a": vocabulary[a], "index_b": b, "token_b": vocabulary[b],
                         "n": len(matrix), "selection_reason": ";".join(reasons), "exact_equal": exact,
                         "counts_equal_documents": int(np.count_nonzero(difference == 0)),
                         "pearson_correlation": float(correlation) if np.isfinite(correlation) else None,
                         "max_abs_difference": float(difference.max()), "mean_abs_difference": float(difference.mean()),
                         "variance_a": float(variance[a]), "variance_b": float(variance[b]),
                         "pair_distance_contribution_ratio": float((variance[a] + variance[b]) / total_variance) if total_variance else None,
                         "constant_pattern": bool(norms[a] == 0 or norms[b] == 0)})
    return sorted(rows, key=lambda row: (-row["pair_distance_contribution_ratio"] if row["pair_distance_contribution_ratio"] is not None else 0,
                                         row["index_a"], row["index_b"]))


def _number(value):
    return float(value) if np.isfinite(value) else None


def build_statistics(root, output):
    """원래 좌표를 읽어 새 분석 폴더의 통계 CSV만 작성한다."""
    from .common import load_data, dump_csv
    from .roles import classify_token

    data = load_data(root)
    output = Path(output)
    directories = {"problems": output / "01_problem_tokens", "solutions": output / "02_solution_tokens"}
    all_rows, summaries = {}, {}
    for region, folder in directories.items():
        train, test = [data["arrays"][region][part] for part in ("train", "test")]
        moments = token_moments(train, test)
        rows = []
        for index, token in enumerate(data["vocabularies"][region]):
            role = classify_token(token, region=region)
            row = {"index": index, "token": token, "source": role["source"], "category": role["category"]}
            for field, values in moments.items():
                row[field] = int(values[index]) if field.endswith(("_tf", "_df")) else _number(values[index])
            row.update({key: role.get(key, "") for key in ("meaning", "ambiguity_note", "information_loss_if_removed")})
            rows.append(row)
        dump_csv(folder / "all_tokens.csv", rows)
        all_rows[region] = rows
        summaries[region] = {"vocabulary_size": len(rows),
            "train_tf": sum(row["train_tf"] for row in rows), "test_tf": sum(row["test_tf"] for row in rows),
            "total_tf": sum(row["total_tf"] for row in rows),
            "source_vocabulary_counts": {source: sum(row["source"] == source for row in rows) for source in ("Kiwi", "LaTeX")},
            "train_variance_sum": sum(row["train_variance"] for row in rows),
            "zero_train_variance_count": sum(row["train_variance"] == 0 for row in rows),
            "top_variance_train": sorted(rows, key=lambda row: (-row["train_variance"], row["index"]))[:20],
            "top_variance_total": sorted(rows, key=lambda row: (-row["variance"], row["index"]))[:20],
            "top_tf_total": sorted(rows, key=lambda row: (-row["total_tf"], row["index"]))[:20]}

    train = np.asarray(data["arrays"]["problems"]["train"], dtype=np.float64)
    problem_rows = all_rows["problems"]
    distance_ratio = np.asarray([row["train_distance_contribution_ratio"] for row in problem_rows], dtype=np.float64)
    variance_rows, class_rows, mean_rows, highlights, level_summaries = [], [], [], [], {}
    for level, (level_name, fields) in LEVELS.items():
        labels = [" / ".join(data["records"][identifier][field] for field in fields) for identifier in data["ids"]["train"]]
        if any(not label or any(not data["records"][identifier][field] for field in fields)
               for identifier, label in zip(data["ids"]["train"], labels)):
            raise ValueError(f"{level}의 계층 분류가 비었습니다.")
        decomposition = variance_decomposition(train, labels)
        sizes = [group["n"] for group in decomposition["groups"]]
        level_rows = []
        for index, token in enumerate(data["vocabularies"]["problems"]):
            row = {"level": level, "level_name": level_name, "index": index, "token": token,
                   "n": len(train), "group_count": len(sizes), "singleton_groups": sizes.count(1),
                   "min_group_n": min(sizes), "max_group_n": max(sizes),
                   "train_df": problem_rows[index]["train_df"], "rare_train_df_le_5": problem_rows[index]["train_df"] <= 5}
            row.update({field: _number(decomposition[field][index]) for field in
                        ("mean", "total_variance", "between_variance", "within_variance", "eta_squared", "adjusted_eta_squared")})
            row["distance_contribution_ratio"] = _number(distance_ratio[index])
            level_rows.append(row)
        variance_rows.extend(level_rows)
        for number, group in enumerate(decomposition["groups"], 1):
            code = f"L{number:02d}"
            class_rows.append({"level": level, "label_code": code, "full_label": group["label"], "n": group["n"]})
            mean_rows.extend({"level": level, "label_code": code, "index": i, "token": token,
                              "n": group["n"], "mean": float(group["mean"][i]), "df": int(group["df"][i])}
                             for i, token in enumerate(data["vocabularies"]["problems"]))
        defined = [row for row in level_rows if row["eta_squared"] is not None]
        variance_quartile = float(np.quantile([row["total_variance"] for row in defined], .75)) if defined else None
        eta_median = float(np.median([row["eta_squared"] for row in defined])) if defined else None
        patterns = {
            "A_high_variance": sorted(level_rows, key=lambda row: (-row["total_variance"], row["index"])),
            "B_high_eta": sorted(defined, key=lambda row: (-row["eta_squared"], -row["train_df"], row["index"])),
            "C_high_variance_low_eta": sorted([row for row in defined if row["total_variance"] >= variance_quartile and row["eta_squared"] <= eta_median],
                                               key=lambda row: (-row["total_variance"], row["eta_squared"], row["index"])),
        }
        for pattern, candidates in patterns.items():
            for rank, row in enumerate(candidates[:20], 1):
                role = problem_rows[row["index"]]
                highlights.append({"level": level, "pattern": pattern, "rank": rank,
                    "index": row["index"], "token": row["token"], "train_variance": row["total_variance"],
                    "eta_squared": row["eta_squared"], "adjusted_eta_squared": row["adjusted_eta_squared"],
                    "train_df": row["train_df"], "distance_contribution_ratio": row["distance_contribution_ratio"],
                    "category": role["category"], "meaning": role["meaning"]})
        level_summaries[level] = {"level_name": level_name, "n": len(train), "group_count": len(sizes),
            "min_group_n": min(sizes), "max_group_n": max(sizes), "median_group_n": float(np.median(sizes)),
            "singleton_groups": sizes.count(1), "groups_with_n_le_2": sum(n <= 2 for n in sizes),
            "eta_defined_tokens": len(defined), "eta_undefined_tokens": len(level_rows) - len(defined),
            "pattern_C_variance_threshold_q75": variance_quartile, "pattern_C_eta_threshold_median": eta_median,
            "pattern_C_eligible_tokens": len(patterns["C_high_variance_low_eta"])}
    folder = directories["problems"]
    dump_csv(folder / "variance_by_classification.csv", variance_rows)
    dump_csv(folder / "class_labels.csv", class_rows)
    dump_csv(folder / "class_token_means.csv", mean_rows)
    dump_csv(folder / "highlight_patterns.csv", highlights)
    joined = []
    for token_row in problem_rows:
        index = token_row["index"]
        joined.append({"index": index, "token": token_row["token"], "train_variance": token_row["train_variance"],
            **{level + "_eta_squared": next(row["eta_squared"] for row in variance_rows if row["level"] == level and row["index"] == index)
               for level in LEVELS}, "meaning": token_row["meaning"]})
    dump_csv(folder / "key_token_statistics.csv", sorted(joined, key=lambda row: (-row["train_variance"], row["index"])))
    pairs = redundancy_pairs(train, data["vocabularies"]["problems"])
    dump_csv(folder / "redundancy_analysis.csv", pairs, fields=REDUNDANCY_FIELDS)
    named_pairs = [row for row in pairs if "requested_pair" in row["selection_reason"]]
    return {"train_n": len(data["ids"]["train"]), "test_n": len(data["ids"]["test"]),
        "total_n": len(data["ids"]["train"]) + len(data["ids"]["test"]), "regions": summaries,
        "classification": level_summaries,
        "redundancy": {"scope": "train", "n": len(train), "recorded_pairs": len(pairs),
            "exact_equal_pairs": sum(row["exact_equal"] for row in pairs), "correlation_threshold": .98,
            "constant_correlation_policy": "undefined/null", "requested_pairs": named_pairs,
            "overlap_warning": "Pair contribution ratios overlap if the same token appears in multiple pairs; do not sum all rows."},
        "definitions": {
            "all_tokens_scope": "mean/variance/std use all265; train_* moments and every label-based statistic use train185 only",
            "variance_denominator": "n (population variance, ddof=0)",
            "decomposition": "total_SS/n = between_SS/n + within_SS/n; between_SS=sum_g n_g(mean_g-mean)^2",
            "eta_squared": "between_SS/total_SS; undefined/null for total_SS=0",
            "eta_floating_boundary": "Only absolute roundoff <=1e-12 near 0 or 1 is represented as that boundary; values outside [0,1] beyond that tolerance raise ArithmeticError. Raw variance and SS values are unchanged.",
            "adjusted_eta_squared": "1-(1-eta_squared)*(n-1)/(n-g); may be negative, null if n<=g or total_SS=0; not a significance test",
            "mean_pair_squared_distance": "For distinct unordered document pairs, mean((x_i-x_j)^2)=2*n/(n-1)*population_variance_j",
            "distance_contribution_ratio": "train_variance_j/sum_j(train_variance_j); undefined null if all dimensions have zero variance",
            "pattern_C": "Descriptive intersection of variance>=within-levelQ75 and eta<=within-levelMedian, no token selection/removal",
            "statistical_selection": "No stopwords selected; patterns and categories are descriptive review aids only"}}
