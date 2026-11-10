"""기존 문제·풀이 벡터 265문항의 탐색적 η²를 별도 경로에 저장한다."""

from collections import Counter
import math
from pathlib import Path
import sys

import numpy as np

from .common import ROOT, dump_csv, dump_json, load_data, read_csv, read_json, sha256
from .statistics import LEVELS, variance_decomposition
from .validation import scan_report_links


FOLDERS = {"problems": "01_problem_tokens", "solutions": "02_solution_tokens"}
WIDTHS = {"problems": 346, "solutions": 431}


def _number(value):
    return float(value) if np.isfinite(value) else None


def combined_data(root):
    data = load_data(root)
    ids = data["ids"]["train"] + data["ids"]["test"]
    if [len(data["ids"][split]) for split in ("train", "test")] != [185, 80] or len(set(ids)) != 265:
        raise ValueError("기존 학습185/테스트80·중복 없는265문항과 다릅니다.")
    labels = {level: [" / ".join(data["records"][identifier][field] for field in fields) for identifier in ids]
              for level, (_, fields) in LEVELS.items()}
    matrices = {}
    for region, width in WIDTHS.items():
        matrix = np.concatenate([data["arrays"][region][split] for split in ("train", "test")]).astype(np.float64)
        if matrix.shape != (265, width) or len(data["vocabularies"][region]) != width:
            raise ValueError(f"{region}: 기존 문항 수·어휘 차원이 다릅니다.")
        norms = np.linalg.norm(matrix, axis=1)
        if np.any(norms == 0):
            raise ValueError(f"{region}: L2 정규화가 정의되지 않는 영벡터: " + ", ".join(ids[i] for i in np.flatnonzero(norms == 0)))
        matrices[region] = (matrix, matrix / norms[:, None])
    return data, labels, matrices


def analyze(root, output):
    data, labels, matrices = combined_data(root)
    groups, class_rows = {}, []
    for level, values in labels.items():
        sizes, train_sizes, test_sizes = Counter(values), Counter(values[:185]), Counter(values[185:])
        groups[level] = {"name": LEVELS[level][0], "group_count": len(sizes), "singleton_groups": sum(n == 1 for n in sizes.values())}
        class_rows.extend({"level": level, "level_name": LEVELS[level][0], "label": label,
                           "n": count, "train_n": train_sizes[label], "test_n": test_sizes[label]}
                          for label, count in sorted(sizes.items()))
    for region, folder in FOLDERS.items():
        matrix, normalized = matrices[region]
        descriptions = read_csv(root / "results/token_analysis" / folder / "all_tokens.csv")
        if [(int(r["index"]), r["token"]) for r in descriptions] != list(enumerate(data["vocabularies"][region])):
            raise ValueError(f"{region}: 기존 설명과 어휘 인덱스가 다릅니다.")
        rows = []
        for level, values in labels.items():
            raw, norm = variance_decomposition(matrix, values), variance_decomposition(normalized, values)
            sizes = Counter(values)
            for index, previous in enumerate(descriptions):
                train_df = int(np.count_nonzero(matrix[:185, index]))
                test_df = int(np.count_nonzero(matrix[185:, index]))
                total_tf = int(matrix[:, index].sum())
                if (train_df != int(previous["train_df"]) or test_df != int(previous["test_df"])
                        or total_tf != int(previous["total_tf"]) or train_df + test_df != int(previous["total_df"])
                        or not np.isclose(raw["total_variance"][index], float(previous["variance"]), rtol=1e-11, atol=1e-12)):
                    raise ValueError(f"{region}/{index}: 기존 전체 TF·DF·분산과 다릅니다.")
                row = {"region": region, "level": level, "level_name": LEVELS[level][0], "index": index,
                       "token": previous["token"], "source": previous["source"], "category": previous["category"],
                       "meaning": previous["meaning"], "n": 265, "train_n": 185, "test_n": 80,
                       "total_tf": total_tf, "total_df": train_df + test_df, "train_df": train_df, "test_df": test_df,
                       **{key: groups[level][key] for key in ("group_count", "singleton_groups")},
                       "min_group_n": min(sizes.values()), "max_group_n": max(sizes.values())}
                for prefix, result in (("original", raw), ("normalized", norm)):
                    row.update({prefix + "_" + key: _number(result[key][index]) for key in
                                ("total_variance", "between_variance", "within_variance", "eta_squared", "adjusted_eta_squared")})
                a, b = row["original_eta_squared"], row["normalized_eta_squared"]
                row["eta_difference"] = b - a if a is not None and b is not None else None
                rows.append(row)
        dump_csv(output / folder / "eta_statistics.csv", rows)
    dump_csv(output / "class_labels.csv", class_rows)
    input_paths = list(data["paths"].values()) + [root / "results/token_analysis" / folder / "all_tokens.csv" for folder in FOLDERS.values()]
    source_paths = [Path(__file__), Path(__file__).with_name("full_dataset_eta_report.py"),
                    Path(__file__).with_name("eta_rankings.py"), Path(__file__).with_name("statistics.py"),
                    Path(__file__).with_name("common.py")]
    config = {"analysis": "problem_solution_full265_eta_v1", "counts": {"train": 185, "test": 80, "total": 265, **WIDTHS},
              "document_order": "original train IDs followed by original test IDs; never modify split files",
              "scope": "Exploratory combined-data statistics including test labels; not independent holdout feature selection",
              "vocabulary_policy": "Original training-fitted vocabularies and coordinate order; no OOV expansion",
              "data_identity": data["identity"], "groups": groups,
              "zero_vectors": {region: 0 for region in FOLDERS},
              "ignored_test_tokens": {region: sum(row["ignored_token_count"] for row in read_json(root / f"data/vectors/{region}/test_vectors.json")["documents"]) for region in FOLDERS},
              "input_files_sha256": {p.relative_to(root).as_posix(): sha256(p) for p in input_paths},
              "analysis_sources_sha256": {p.relative_to(root).as_posix(): sha256(p) for p in source_paths},
              "variance_denominator": 265, "numpy_version": np.__version__,
              "model_training": False, "gemini_calls": 0, "stopwords_selected_or_applied": False}
    dump_json(output / "config.json", config)


def check_inputs(root, output):
    for name, digest in read_json(output / "config.json")["input_files_sha256"].items():
        if not (root / name).is_file() or sha256(root / name) != digest:
            raise ValueError(f"전체265 η²의 입력 파일이 바뀌었습니다: {name}")


def manifest(output, *, write=False, tables_only=False):
    path = output / "manifest.json"
    if write:
        dump_json(path, {"files_sha256": {p.relative_to(output).as_posix(): sha256(p)
                                         for p in output.rglob("*") if p.is_file() and p != path}})
        return
    for name, digest in read_json(path)["files_sha256"].items():
        if tables_only and not name.endswith((".csv", "config.json")):
            continue
        if not (output / name).is_file() or sha256(output / name) != digest:
            raise ValueError(f"저장된 전체265 η² 파일이 바뀌었습니다: {name}")


def verify(root, output, *, save=False):
    check_inputs(root, output)
    data, labels, matrices = combined_data(root)
    checks = []
    def check(name, passed):
        checks.append({"check": name, "passed": bool(passed)})
    def close(a, b):
        return a == "" if b is None or not np.isfinite(b) else a != "" and math.isclose(float(a), float(b), rel_tol=1e-9, abs_tol=1e-11)
    for region, folder in FOLDERS.items():
        rows = read_csv(output / folder / "eta_statistics.csv")
        x, z = matrices[region]
        width = WIDTHS[region]
        lookup = {(row["level"], int(row["index"])): row for row in rows}
        check(region + "_all_indices_once", len(rows) == width * 4 and set(lookup) == {(level, index) for level in LEVELS for index in range(width)})
        for level, values in labels.items():
            sizes = Counter(values)
            for prefix, matrix in (("original", x), ("normalized", z)):
                overall = matrix.mean(axis=0)
                means = {label: matrix[np.asarray(values) == label].mean(axis=0) for label in sizes}
                fitted = np.stack([means[label] for label in values])
                total = np.mean((matrix - overall) ** 2, axis=0)
                between = np.mean((fitted - overall) ** 2, axis=0)
                within = np.mean((matrix - fitted) ** 2, axis=0)
                valid = np.allclose(total, between + within, rtol=1e-11, atol=1e-11)
                for i in range(width):
                    row = lookup[level, i]
                    eta = between[i] / total[i] if total[i] else None
                    adjusted = 1 - (1 - eta) * 264 / (265 - len(sizes)) if eta is not None else None
                    valid &= all(close(row[prefix + "_" + key], value) for key, value in
                                 (("total_variance", total[i]), ("between_variance", between[i]), ("within_variance", within[i]),
                                  ("eta_squared", eta), ("adjusted_eta_squared", adjusted)))
                    valid &= row["region"] == region and row["token"] == data["vocabularies"][region][i] and int(row["n"]) == 265
                    valid &= int(row["total_tf"]) == x[:, i].sum() and int(row["total_df"]) == np.count_nonzero(x[:, i])
                    valid &= int(row["train_df"]) == np.count_nonzero(x[:185, i]) and int(row["test_df"]) == np.count_nonzero(x[185:, i])
                    valid &= int(row["group_count"]) == len(sizes) and int(row["singleton_groups"]) == sum(n == 1 for n in sizes.values())
                check(region + "_" + level + "_" + prefix + "_independent_projection", valid)
        check(region + "_four_ranking_documents", all((output / folder / f"{level}.md").is_file() for level in LEVELS))
    class_rows = read_csv(output / "class_labels.csv")
    for level, values in labels.items():
        rows = [row for row in class_rows if row["level"] == level]
        counts, train, test = Counter(values), Counter(values[:185]), Counter(values[185:])
        check(level + "_class_sizes", len(rows) == len(counts) and {r["label"] for r in rows} == set(counts)
              and all(int(r["n"]) == counts[r["label"]] and int(r["train_n"]) == train[r["label"]]
                      and int(r["test_n"]) == test[r["label"]] for r in rows))
    links, missing = scan_report_links(output)
    check("relative_links", not missing)
    result = {"passed": sum(c["passed"] for c in checks), "failed": sum(not c["passed"] for c in checks), "checks": checks,
              "n": 265, "train_n": 185, "test_n": 80, "widths": WIDTHS, "relative_links_checked": links, "missing_links": missing,
              "models_trained": 0, "new_cluster_assignments": 0, "model_checkpoint_loads": 0, "new_gemini_calls": 0,
              "limits": "Full265 exploratory labels include test data. Existing fixed vocabularies omit test OOV29/48. No stopword selection or new model evaluation."}
    if save:
        dump_json(output / "validation.json", result)
    if result["failed"]:
        raise ValueError("전체265 η² 검증 실패: " + ", ".join(c["check"] for c in checks if not c["passed"]))
    return result


def run(action="analyze", *, root=ROOT):
    if action not in ("analyze", "report", "verify"):
        raise ValueError("analyze/report/verify만 제공합니다. 모델 학습·불용어 명령은 없습니다.")
    root = Path(root).resolve()
    output = root / "results/token_analysis/05_full_dataset_eta"
    if action == "analyze":
        if (output / "config.json").exists():
            check_inputs(root, output)
        analyze(root, output)
    else:
        check_inputs(root, output)
        manifest(output, tables_only=action == "report")
    if action in ("analyze", "report"):
        from .full_dataset_eta_report import build_report
        build_report(root, output)
    result = verify(root, output, save=action != "verify")
    if action != "verify":
        manifest(output, write=True)
    print(f"전체265 문제346·풀이431 η² {action}: {result['passed']}검사 통과 · {output}", flush=True)
    return result


if __name__ == "__main__":
    if len(sys.argv) > 2:
        raise SystemExit("python -m mathhint_analysis.token_analysis.full_dataset_eta [analyze|report|verify]")
    run(sys.argv[1] if len(sys.argv) == 2 else "analyze")
