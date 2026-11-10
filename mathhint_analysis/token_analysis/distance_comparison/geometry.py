"""학습 문항의 거리 분해와 정규화 전후 분산만 계산한다. 모델은 실행하지 않는다."""

from collections import Counter
from pathlib import Path

import numpy as np

from ..common import dump_csv, load_data, read_csv, read_json
from ..statistics import LEVELS, variance_decomposition


PAIR_GROUPS = (
    ("braces_pair", "중괄호 두 좌표", ("latex:{", "latex:}")),
    ("left_right_pair", "좌우 크기 표시 두 좌표", (r"latex:\left", r"latex:\right")),
    ("parentheses_pair", "소괄호 두 좌표", ("latex:(", "latex:)")),
    ("duplicate_six", "중괄호·좌우 표시·소괄호 6좌표", (
        "latex:{", "latex:}", r"latex:\left", r"latex:\right", "latex:(", "latex:)")),
)


def pair_geometry(matrix, ids=None):
    """서로 다른 비영벡터의 상삼각 쌍을 한 번씩 계산한다.

    영벡터가 있으면 임의로 코사인 값을 만들거나 문항을 버리지 않고 중단한다.
    normalized 좌표는 메모리에만 존재하며 입력 행렬은 변경하지 않는다.
    """
    matrix = np.asarray(matrix, dtype=np.float64)
    if matrix.ndim != 2 or len(matrix) < 2 or matrix.shape[1] < 1 or not np.isfinite(matrix).all():
        raise ValueError("거리 분석에는 둘 이상의 유한한 문항 벡터가 필요합니다.")
    l2 = np.linalg.norm(matrix, axis=1)
    zero = np.flatnonzero(l2 == 0)
    if len(zero):
        names = [ids[i] if ids is not None else str(i) for i in zero]
        raise ValueError("영벡터의 코사인 거리는 정의되지 않습니다. 문항을 삭제하지 않고 중단합니다: " + ", ".join(names))
    normalized = matrix / l2[:, None]
    first, second = np.triu_indices(len(matrix), k=1)
    euclidean_squared = np.square(matrix[first] - matrix[second]).sum(axis=1)
    cosine_by_coordinates = .5 * np.square(normalized[first] - normalized[second]).sum(axis=1)
    cosine_by_dot = 1 - np.einsum("ij,ij->i", normalized[first], normalized[second])
    if np.any(cosine_by_dot < -1e-12) or np.any(cosine_by_dot > 2 + 1e-12):
        raise ArithmeticError("코사인 거리가 부동소수점 허용 오차를 넘어 이론 범위 밖입니다.")
    # 비영벡터의 항등식은 좌표 합과 내적을 각각 계산하여 확인한다.
    if not np.allclose(cosine_by_coordinates, cosine_by_dot, rtol=1e-11, atol=1e-12):
        raise ArithmeticError("정규화 좌표 제곱차와 1-cos의 항등식이 일치하지 않습니다.")
    # 내적식과 수학적으로 같은 좌표식을 사용하면 동일 벡터의 미세한 음수 거리를 피한다.
    cosine = cosine_by_coordinates
    if not np.allclose(np.linalg.norm(normalized, axis=1), 1, rtol=0, atol=1e-12):
        raise ArithmeticError("L2 정규화된 행이 단위 길이가 아닙니다.")
    return {"X": matrix, "Z": normalized, "pair_i": first, "pair_j": second,
            "euclidean_squared": euclidean_squared, "euclidean": np.sqrt(euclidean_squared),
            "cosine": cosine, "l1": np.abs(matrix).sum(axis=1), "l2": l2,
            "cosine_identity_max_abs_error": float(np.abs(cosine_by_coordinates - cosine_by_dot).max())}


def load_geometry(root):
    """기존 train185의 ID·어휘 순서를 그대로 사용한다. 테스트 라벨은 분석하지 않는다."""
    root = Path(root)
    data = load_data(root)
    ids = data["ids"]["train"]
    vocabulary = data["vocabularies"]["problems"]
    matrix = data["arrays"]["problems"]["train"]
    if tuple(matrix.shape) != (185, 346) or len(ids) != 185 or len(vocabulary) != 346:
        raise ValueError("기존 학습185문항·문제346차원과 다른 데이터입니다.")
    saved = read_json(root / "data/vectors/problems/train_vectors.json")["documents"]
    if [row["id"] for row in saved] != ids:
        raise ValueError("학습 문항 ID·원래 벡터 행 순서가 다릅니다.")
    geometry = pair_geometry(matrix, ids)
    token_count = np.asarray([row["token_count"] for row in saved], dtype=np.int64)
    if not np.array_equal(token_count, matrix.sum(axis=1)) or any(row["ignored_token_count"] for row in saved):
        raise ValueError("학습 토큰 수와 고정 어휘의 L1 합이 다릅니다.")
    labels_by_level = {}
    for level, (_, fields) in LEVELS.items():
        if any(not data["records"][identifier].get(field) for identifier in ids for field in fields):
            raise ValueError(f"학습 문항의 {level} 계층 경로가 비었습니다.")
        labels_by_level[level] = [" / ".join(data["records"][identifier][field] for field in fields)
                                 for identifier in ids]
    geometry.update(data=data, ids=ids, vocabulary=vocabulary, token_count=token_count,
                    labels_by_level=labels_by_level, metadata=data["records"])
    return geometry


def contribution_statistics(geometry):
    """모든 쌍의 평균 좌표 제곱차를 직접 합산하고 분산 공식과 대조한다."""
    x, z, first, second = [geometry[key] for key in ("X", "Z", "pair_i", "pair_j")]
    raw_coordinate = np.square(x[first] - x[second]).mean(axis=0)
    normalized_coordinate = .5 * np.square(z[first] - z[second]).mean(axis=0)
    raw_variance, normalized_variance = x.var(axis=0, ddof=0), z.var(axis=0, ddof=0)
    factor = len(x) / (len(x) - 1)
    if (not np.allclose(raw_coordinate, 2 * factor * raw_variance, rtol=1e-11, atol=1e-12)
            or not np.allclose(normalized_coordinate, factor * normalized_variance, rtol=1e-11, atol=1e-14)):
        raise ArithmeticError("모든 문항쌍의 좌표 제곱차 평균이 분산 공식과 다릅니다.")
    if not np.isclose(raw_coordinate.sum(), geometry["euclidean_squared"].mean(), rtol=1e-12, atol=1e-12):
        raise ArithmeticError("유클리드 제곱거리와 좌표별 기여도 합이 다릅니다.")
    if not np.isclose(normalized_coordinate.sum(), geometry["cosine"].mean(), rtol=1e-11, atol=1e-12):
        raise ArithmeticError("코사인 거리와 좌표별 기여도 합이 다릅니다.")

    def percentages(values):
        total = float(values.sum())
        return values / total * 100 if total > 0 else np.full(values.shape, np.nan)

    raw_percent, normalized_percent = percentages(raw_coordinate), percentages(normalized_coordinate)
    for values in (raw_percent, normalized_percent):
        if np.isfinite(values).any() and not np.isclose(values.sum(), 100, rtol=0, atol=1e-10):
            raise ArithmeticError("토큰 기여율의 합이 100%가 아닙니다.")
    return {"original_variance": raw_variance, "normalized_variance": normalized_variance,
            "pair_mean_euclidean_squared_coordinate": raw_coordinate,
            "pair_mean_cosine_coordinate": normalized_coordinate,
            "euclidean_contribution": raw_percent, "cosine_contribution": normalized_percent}


def contribution_ranks(values):
    """기여도 내림차순, 완전 동률은 원래 어휘 인덱스 순서의 1기준 순위다."""
    ranked = sorted((i for i, value in enumerate(values) if np.isfinite(value)), key=lambda i: (-values[i], i))
    ranks = [None] * len(values)
    for rank, index in enumerate(ranked, 1):
        ranks[index] = rank
    return ranks


def _number(value):
    return float(value) if np.isfinite(value) else None


def _optional_sum(values):
    values = list(values)
    return sum(values) if all(value is not None for value in values) else None


def _compare_existing_statistics(root, contribution_rows, eta_rows):
    folder = Path(root) / "results/token_analysis/01_problem_tokens"
    original = read_csv(folder / "all_tokens.csv")
    if len(original) != len(contribution_rows):
        raise ValueError("기존 토큰 통계와 어휘 수가 다릅니다.")
    for current, previous in zip(contribution_rows, original):
        old_contribution = 100 * float(previous["train_distance_contribution_ratio"]) if previous["train_distance_contribution_ratio"] else None
        new_contribution = current["euclidean_contribution"]
        contribution_matches = (new_contribution is None and old_contribution is None) or (
            new_contribution is not None and old_contribution is not None
            and np.isclose(new_contribution, old_contribution, rtol=1e-11, atol=1e-10))
        if (current["index"] != int(previous["index"]) or current["token"] != previous["token"]
                or not np.isclose(current["original_variance"], float(previous["train_variance"]), rtol=1e-12, atol=1e-12)
                or not contribution_matches):
            raise ValueError(f"기존 원시 토큰 통계와 다릅니다: {current['token']}")
    previous_eta = {(row["level"], int(row["index"])): row for row in read_csv(folder / "variance_by_classification.csv")}
    for row in eta_rows:
        old = previous_eta[(row["level"], row["index"])]
        for current_key, old_key in (("original_total_variance", "total_variance"),
                                     ("original_between_variance", "between_variance"),
                                     ("original_within_variance", "within_variance"),
                                     ("original_eta_squared", "eta_squared")):
            current = row[current_key]
            previous = float(old[old_key]) if old[old_key] else None
            if ((current is None) != (previous is None)
                    or current is not None and not np.isclose(current, previous, rtol=1e-11, atol=1e-12)):
                raise ValueError(f"기존 학습 η²·분산과 다릅니다: {row['level']}/{row['token']}")


def build_geometry_analysis(root, output, geometry=None):
    """새 하위 폴더에만 토큰 기여도와 η² 비교표를 저장한다."""
    root, output = Path(root), Path(output)
    geometry = load_geometry(root) if geometry is None else geometry
    x, z, vocabulary = geometry["X"], geometry["Z"], geometry["vocabulary"]
    description_rows = read_csv(root / "results/token_analysis/01_problem_tokens/all_tokens.csv")
    if [row["token"] for row in description_rows] != vocabulary:
        raise ValueError("기존 토큰 설명과 원래 어휘 순서가 다릅니다.")
    contributions = contribution_statistics(geometry)
    raw_ranks = contribution_ranks(contributions["euclidean_contribution"])
    normalized_ranks = contribution_ranks(contributions["cosine_contribution"])
    rows = []
    for index, token in enumerate(vocabulary):
        previous = description_rows[index]
        row = {"index": index, "token": token, "source": previous["source"],
               "category": previous["category"], "meaning": previous["meaning"],
               "train_df": int(np.count_nonzero(x[:, index]))}
        row.update({key: _number(values[index]) for key, values in contributions.items()})
        raw, normalized = row["euclidean_contribution"], row["cosine_contribution"]
        row.update(contribution_difference=normalized - raw if raw is not None and normalized is not None else None,
                   euclidean_rank=raw_ranks[index], cosine_rank=normalized_ranks[index],
                   rank_change=raw_ranks[index] - normalized_ranks[index]
                       if raw_ranks[index] is not None and normalized_ranks[index] is not None else None)
        rows.append(row)

    eta_rows, eta_levels = [], {}
    for level, (level_name, _) in LEVELS.items():
        labels = geometry["labels_by_level"][level]
        original, normalized = variance_decomposition(x, labels), variance_decomposition(z, labels)
        sizes = list(Counter(labels).values())
        for index, token in enumerate(vocabulary):
            row = {"level": level, "level_name": level_name, "index": index, "token": token,
                   "category": rows[index]["category"], "meaning": rows[index]["meaning"],
                   "train_df": rows[index]["train_df"], "n": len(x), "group_count": len(sizes),
                   "singleton_groups": sizes.count(1), "min_group_n": min(sizes), "max_group_n": max(sizes)}
            for prefix, result in (("original", original), ("normalized", normalized)):
                row.update({prefix + "_" + key: _number(result[key][index]) for key in (
                    "total_variance", "between_variance", "within_variance", "eta_squared", "adjusted_eta_squared")})
            a, b = row["original_eta_squared"], row["normalized_eta_squared"]
            row["eta_difference"] = b - a if a is not None and b is not None else None
            eta_rows.append(row)
        eta_levels[level] = {"group_count": len(sizes), "singleton_groups": sizes.count(1),
                             "groups_with_n_le_2": sum(n <= 2 for n in sizes),
                             "original_zero_variance_tokens": int(np.count_nonzero(original["total_variance"] == 0)),
                             "normalized_zero_variance_tokens": int(np.count_nonzero(normalized["total_variance"] == 0))}
    _compare_existing_statistics(root, rows, eta_rows)
    dump_csv(output / "token_distance_contributions.csv", rows)
    dump_csv(output / "normalized_eta_comparison.csv", eta_rows)

    by_token = {row["token"]: row for row in rows}
    group_rows = []
    for key, name, tokens in PAIR_GROUPS:
        if any(token not in by_token for token in tokens):
            raise ValueError("요청한 비교 토큰이 고정 어휘에 없습니다: " + key)
        indices = [by_token[token]["index"] for token in tokens]
        raw = _optional_sum(by_token[token]["euclidean_contribution"] for token in tokens)
        normalized = _optional_sum(by_token[token]["cosine_contribution"] for token in tokens)
        paired = [(indices[i], indices[i + 1]) for i in range(0, len(indices), 2)]
        group_rows.append({"group": key, "group_name": name, "tokens": ";".join(tokens), "token_count": len(tokens),
            "euclidean_contribution": raw, "cosine_contribution": normalized,
            "contribution_difference": normalized - raw if raw is not None and normalized is not None else None,
            "raw_pair_equal_all": all(np.array_equal(x[:, a], x[:, b]) for a, b in paired),
            "normalized_pair_equal_all": all(np.array_equal(z[:, a], z[:, b]) for a, b in paired)})
    dump_csv(output / "requested_token_groups.csv", group_rows)
    categories = sorted({row["category"] for row in rows})
    category_rows = []
    for category in categories:
        selected = [row for row in rows if row["category"] == category]
        raw = _optional_sum(row["euclidean_contribution"] for row in selected)
        normalized = _optional_sum(row["cosine_contribution"] for row in selected)
        category_rows.append({"category": category, "token_count": len(selected), "euclidean_contribution": raw,
                              "cosine_contribution": normalized, "contribution_difference":
                                  normalized - raw if raw is not None and normalized is not None else None})
    dump_csv(output / "category_contributions.csv", category_rows)

    return {"scope": {"split": "train", "n": len(x), "dimensions": x.shape[1],
                       "pairs": len(geometry["pair_i"]), "zero_vectors": 0},
            "pair_means": {"euclidean_squared": float(geometry["euclidean_squared"].mean()),
                           "euclidean": float(geometry["euclidean"].mean()),
                           "cosine": float(geometry["cosine"].mean())},
            "contribution_sums": {key: _number(contributions[key].sum())
                                  for key in ("euclidean_contribution", "cosine_contribution")},
            "cosine_identity_max_abs_error": geometry["cosine_identity_max_abs_error"],
            "requested_groups": group_rows, "eta_levels": eta_levels,
            "definitions": {"population_variance_denominator": len(x),
                "unordered_pairs": "i<j, no self-pairs; each different document pair once",
                "euclidean_contribution": "100*mean_pairs((x_j-y_j)^2)/mean_pairs(sum_j((x_j-y_j)^2))",
                "cosine_contribution": "100*mean_pairs(0.5*(z_j-w_j)^2)/mean_pairs(1-dot(z,w)); rows z,w have L2 norm 1",
                "percentages_computed_by": "Direct all-pair coordinate means; independently checked against variance_j/sum(variance)",
                "contribution_difference_unit_and_sign": "percentage points; cosine minus euclidean",
                "rank_change_sign": "euclidean_rank minus cosine_rank; positive means higher relative rank after normalization",
                "rank_ties": "same contribution sorts by original vocabulary index; unique ordinal ranks start at 1",
                "zero_vector_policy": "Cosine undefined: stop with IDs; never delete a document or assign an arbitrary distance",
                "cosine_numerics": "Compute 1-dot independently and verify its identity with 0.5*sum((z-w)^2); use the nonnegative coordinate form to avoid roundoff-negative distances",
                "zero_total_distance_policy": "Relative contributions undefined/null if all document-pair distances in a space equal zero",
                "zero_variance_eta_policy": "undefined/null, not zero or one; same existing bounded_eta policy for 1e-12 roundoff",
                "adjusted_eta_squared": "1-(1-eta_squared)*(n-1)/(n-g); negative values retained; undefined for n<=g or zero total variance",
                "interpretation": "Raw and normalized variance have different units; compare relative contribution within each metric, not their absolute variances"},
            "original_raw_statistics_match": True, "new_models": 0, "new_api_calls": 0}
