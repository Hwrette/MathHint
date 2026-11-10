"""저장된 통계와 원본 좌표를 대조한다. 모델 평가·학습은 포함하지 않는다."""

from collections import Counter
import math
from pathlib import Path
from urllib.parse import unquote, urlsplit
import re

import numpy as np

from .common import dump_json, load_data, read_csv, read_json, sha256


def verify_sources(root, config):
    root = Path(root)
    changed = [name for name, expected in config["protected_files_sha256"].items()
               if not (root / name).is_file() or sha256(root / name) != expected]
    if changed:
        raise ValueError("분석 기준 원본이 변경되었습니다: " + ", ".join(changed[:10]))
    return len(config["protected_files_sha256"])


def scan_report_links(output):
    output = Path(output)
    links, missing = 0, []
    for path in output.rglob("*.md"):
        text = re.sub(r"^```[^\n]*\n.*?^```\s*$", "", path.read_text(encoding="utf-8"), flags=re.M | re.S)
        for href in re.findall(r"\[[^\]\n]*\]\((<[^>]+>|[^)\n]+)\)", text):
            url = urlsplit(href.strip("<>"))
            if url.scheme or not url.path:
                continue
            links += 1
            target = path.parent / unquote(url.path)
            # 이번 검증이 마지막에 작성할 자기 자신에 대한 링크는 유효하다.
            if target.resolve() != (output / "validation.json").resolve() and not target.exists():
                missing.append({"source": str(path.relative_to(output)), "target": href})
    return links, missing


def verify_analysis(root, output):
    root, output = Path(root), Path(output)
    config = read_json(output / "config.json")
    protected = verify_sources(root, config)
    data = load_data(root)
    checks = []

    def check(name, condition):
        checks.append({"check": name, "passed": bool(condition)})

    def close(a, b):
        return math.isclose(float(a), float(b), rel_tol=1e-10, abs_tol=1e-10)

    check("fixed_185_80", [len(data["ids"][p]) for p in ("train", "test")] == [185, 80])
    for region, name, width in (("problems", "01_problem_tokens", 346),
                                ("solutions", "02_solution_tokens", 431)):
        rows = read_csv(output / name / "all_tokens.csv")
        vocab = data["vocabularies"][region]
        check(region + "_unchanged_indices", len(rows) == width and
              [(int(row["index"]), row["token"]) for row in rows] == list(enumerate(vocab)))
        arrays = data["arrays"][region]
        combined = np.concatenate([arrays[p] for p in ("train", "test")])
        for i, row in enumerate(rows):
            valid = True
            for part in ("train", "test"):
                x = arrays[part][:, i]
                valid &= int(row[part + "_tf"]) == int(x.sum())
                valid &= int(row[part + "_df"]) == int(np.count_nonzero(x))
            x, train = combined[:, i], arrays["train"][:, i]
            valid &= int(row["total_tf"]) == int(x.sum()) and int(row["total_df"]) == int(np.count_nonzero(x))
            valid &= close(row["mean"], x.mean()) and close(row["variance"], x.var()) and close(row["std"], x.std())
            valid &= close(row["train_variance"], train.var())
            check(f"{region}_coordinate_{i}_moments", valid)

    matrix = data["arrays"]["problems"]["train"].astype(float)
    fields = ("curriculum", "unit", "subunit", "type")
    decomposed = read_csv(output / "01_problem_tokens/variance_by_classification.csv")
    class_keys = read_csv(output / "01_problem_tokens/class_labels.csv")
    class_means = read_csv(output / "01_problem_tokens/class_token_means.csv")
    check("four_levels_346_coordinates", len(decomposed) == 4 * 346)
    for level_number, level in enumerate(fields, 1):
        labels = [tuple(data["records"][identifier][key] for key in fields[:level_number])
                  for identifier in data["ids"]["train"]]
        groups = sorted(set(labels))
        means = {label: matrix[[v == label for v in labels]].mean(axis=0) for label in groups}
        fitted = np.stack([means[label] for label in labels])
        overall = matrix.mean(axis=0)
        total = np.mean((matrix - overall) ** 2, axis=0)
        between = np.mean((fitted - overall) ** 2, axis=0)
        within = np.mean((matrix - fitted) ** 2, axis=0)
        rows = [row for row in decomposed if row["level"] == level]
        valid = len(rows) == 346
        for i, row in enumerate(rows):
            valid &= int(row["index"]) == i and row["token"] == data["vocabularies"]["problems"][i]
            valid &= close(row["total_variance"], total[i]) and close(row["between_variance"], between[i])
            valid &= close(row["within_variance"], within[i]) and close(total[i], between[i] + within[i])
            valid &= (row["eta_squared"] == "") if total[i] == 0 else close(row["eta_squared"], between[i] / total[i])
            valid &= close(row["distance_contribution_ratio"], total[i] / total.sum())
        check(level + "_independent_group_projection", valid)
        keys = [row for row in class_keys if row["level"] == level]
        check(level + "_group_paths_and_sizes", [row["full_label"] for row in keys] ==
              [" / ".join(label) for label in groups] and
              all(int(row["n"]) == labels.count(label) for row, label in zip(keys, groups)))
        expected = {f"L{i + 1:02d}": (label, matrix[[v == label for v in labels]])
                    for i, label in enumerate(groups)}
        rows = [row for row in class_means if row["level"] == level]
        valid = len(rows) == len(groups) * 346
        expected_means = {code: array.mean(axis=0) for code, (_, array) in expected.items()}
        expected_dfs = {code: np.count_nonzero(array, axis=0) for code, (_, array) in expected.items()}
        observed_keys = set()
        for row in rows:
            code, i = row["label_code"], int(row["index"])
            valid &= (code, i) not in observed_keys and row["token"] == data["vocabularies"]["problems"][i]
            observed_keys.add((code, i))
            valid &= int(row["n"]) == len(expected[code][1])
            valid &= close(row["mean"], expected_means[code][i]) and int(row["df"]) == expected_dfs[code][i]
        check(level + "_all_class_token_means_and_df", valid)

    for row in read_csv(output / "01_problem_tokens/redundancy_analysis.csv"):
        a, b = int(row["index_a"]), int(row["index_b"])
        x, y = matrix[:, a], matrix[:, b]
        difference = np.abs(x - y)
        correlation = float(np.corrcoef(x, y)[0, 1]) if x.std() and y.std() else None
        valid = (row["exact_equal"] == "True") == bool(np.array_equal(x, y))
        valid &= int(row["counts_equal_documents"]) == int(np.count_nonzero(difference == 0))
        valid &= close(row["max_abs_difference"], difference.max()) and close(row["mean_abs_difference"], difference.mean())
        valid &= row["pearson_correlation"] == "" if correlation is None else close(row["pearson_correlation"], correlation)
        valid &= close(row["pair_distance_contribution_ratio"], (x.var() + y.var()) / matrix.var(axis=0).sum())
        check(f"redundancy_{a}_{b}", valid)

    oov_rows = read_csv(output / "03_oov_analysis/excluded_tokens.csv")
    for region in ("problems", "solutions"):
        saved = read_json(root / f"data/vectors/{region}/test_vectors.json")["documents"]
        expected = sum(row["ignored_token_count"] for row in saved)
        check(region + "_oov_tf", sum(int(row["total_tf"]) for row in oov_rows if row["region"] == region) == expected)
        check(region + "_oov_outside_fixed_vocabulary", all(row["token"] not in data["vocabularies"][region]
              for row in oov_rows if row["region"] == region))
    recount = read_csv(output / "03_oov_analysis/recount_validation.csv")
    check("530_recounted_regions_and_documents", len(recount) == 530 and
          all(row["all_original_coordinates_match"] == "True" for row in recount))

    transmitted = read_csv(output / "02_solution_tokens/transmitted_tokens.csv")
    expected_keys = {(identifier, condition) for identifier in data["ids"]["test"] for condition in ("B", "C")}
    check("160_actual_request_keys", {(row["id"], row["condition"]) for row in transmitted} == expected_keys)
    for identifier, condition in sorted(expected_keys):
        request = read_json(root / f"results/final_experiment/03_gemini/prompt_audit/requests/{identifier}/{condition}.json")
        rows = [row for row in transmitted if row["id"] == identifier and row["condition"] == condition]
        observed = [(row["token"], float(row["transmitted_value"])) for row in rows]
        check(identifier + condition + "_actual_mapping", observed == list(request["hint"]["mapping"].items()))
    for condition in ("B", "C"):
        rows = [row for row in transmitted if row["condition"] == condition]
        counts = Counter(row["category"] for row in rows)
        composition = [row for row in read_csv(output / "02_solution_tokens/top20_category_composition.csv")
                       if row["condition"] == condition]
        check(condition + "_category_denominator", sum(int(row["coordinate_count"]) for row in composition) == len(rows) and
              all(int(row["coordinate_count"]) == counts[row["category"]] and
                  close(row["coordinate_fraction"], counts[row["category"]] / len(rows)) for row in composition))

    for region in ("problem", "solution"):
        path = output / f"stopwords/{region}_stopwords.json"
        check(region + "_user_choice_file_initially_empty", path.exists() and read_json(path) == [])

    links, missing = scan_report_links(output)
    check("all_report_links_exist", not missing)
    check("required_reading_documents", all((output / p).is_file() for p in (
        "README.md", "token_analysis_report.md", "01_problem_tokens/README.md",
        "02_solution_tokens/README.md", "03_oov_analysis/README.md")))
    pngs = list(output.rglob("*.png"))
    check("token_figures_present", len(pngs) >= 8)
    result = {"passed": sum(c["passed"] for c in checks), "failed": sum(not c["passed"] for c in checks),
              "checks": checks, "protected_original_files": protected,
              "all_original_source_hashes_unchanged": True, "relative_links_checked": links,
              "missing_links": missing, "png_count": len(pngs),
              "scope": "Stage 1 descriptive token analysis only; user chooses stopwords later",
              "user_selection_required": True, "new_model_experiments": 0, "new_gemini_calls": 0,
              "limits": "Category labels are descriptive; figures need visual inspection; no hint-effect or model-improvement experiment performed."}
    dump_json(output / "validation.json", result)
    return result
