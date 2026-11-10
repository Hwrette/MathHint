"""저장된 265문항 문제 BoW·군집 결과만 검사한다. 학습·API 호출은 없다."""

from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

import numpy as np


FIELDS = ("curriculum", "unit", "subunit", "type")


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _rows(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _array(value):
    return value.detach().cpu().numpy() if hasattr(value, "detach") else np.asarray(value)


def _close(a, b):
    return math.isclose(float(a), float(b), rel_tol=2e-6, abs_tol=2e-7)


def label_path(record, level):
    return " / ".join(record[field] for field in FIELDS[:FIELDS.index(level) + 1])


def majority_mapping(assignments, labels):
    """독립 재계산. 동일265문항의 최빈 라벨, 동률은 문자열 오름차순이다."""
    groups = {}
    for cluster, label in zip(assignments, labels):
        groups.setdefault(int(cluster), Counter())[label] += 1
    return {cluster: min(counts, key=lambda label: (-counts[label], label))
            for cluster, counts in groups.items()}


def expected_confusion(actual, predicted, labels):
    """행·열에 같은 라벨 순서를 쓰고, 동일 대표 라벨의 여러 군집을 합산한다."""
    actual, predicted, labels = list(actual), list(predicted), list(labels)
    if len(actual) != len(predicted) or len(labels) != len(set(labels)):
        raise ValueError("문항 수 또는 분류 순서가 잘못됐습니다.")
    indices = {label: i for i, label in enumerate(labels)}
    result = np.zeros((len(labels), len(labels)), dtype=np.int64)
    for observed, forecast in zip(actual, predicted):
        if observed not in indices or forecast not in indices:
            raise ValueError("분류 목록에 없는 실제·대표 라벨입니다.")
        result[indices[observed], indices[forecast]] += 1
    return result


def validate_projection(raw, filtered, vocabulary, filtered_vocabulary, stopwords, active_indices):
    """사용자가 선택한 좌표만 제거되었는지, 같은 크기의 순서 변경도 거부한다."""
    expected = [i for i, token in enumerate(vocabulary) if token not in set(stopwords)]
    if list(active_indices) != expected or list(filtered_vocabulary) != [vocabulary[i] for i in expected]:
        raise ValueError("활성 토큰·인덱스가 승인 불용어 및 원래 순서와 다릅니다.")
    if not np.array_equal(_array(filtered), _array(raw)[:, expected]):
        raise ValueError("불용어 외 좌표가 바뀌었거나 문항 행이 뒤바뀌었습니다.")
    return expected


def scan_links(output):
    output = Path(output)
    count, broken = 0, []
    for path in output.rglob("*.md"):
        text = re.sub(r"^```[^\n]*\n.*?^```\s*$", "", path.read_text(encoding="utf-8"), flags=re.M | re.S)
        for target in re.findall(r"\[[^\]\n]*\]\((<[^>]+>|[^)\n]+)\)", text):
            url = urlsplit(target.strip("<>"))
            if url.scheme or not url.path:
                continue
            count += 1
            destination = path.parent / unquote(url.path)
            if destination.resolve() == (output / "validation.json").resolve():
                continue
            if not destination.exists():
                broken.append({"source": str(path.relative_to(output)), "target": target})
    return count, broken


def _check_dataset(root, output, data, check):
    ids = data["ids"]
    all_ids = ids["train"] + ids["test"]
    check("original_185_80_split_and_265_unique_ids", len(ids["train"]) == 185 and len(ids["test"]) == 80
          and len(set(all_ids)) == 265 and set(data["records"]) == set(all_ids)
          and ids["train"] == _read(root / "data/processed/splits/train.json")
          and ids["test"] == _read(root / "data/processed/splits/test.json"))
    raw_data, filtered_data = (data["variants"][name] for name in ("raw", "filtered"))
    raw_vocab = raw_data["vocabularies"]["problems"]
    filtered_vocab = filtered_data["vocabularies"]["problems"]
    raw = np.concatenate([_array(raw_data["arrays"]["problems"][part]) for part in ("train", "test")])
    filtered = np.concatenate([_array(filtered_data["arrays"]["problems"][part]) for part in ("train", "test")])
    check("problem_vocabulary_unique_order_and_integer_counts", len(raw_vocab) == len(set(raw_vocab))
          and raw.shape == (265, len(raw_vocab)) and filtered.shape == (265, len(filtered_vocab))
          and np.isfinite(raw).all() and np.all(raw >= 0) and np.array_equal(raw, raw.astype(np.int64))
          and list(raw_data["active_indices"]["problems"]) == list(range(len(raw_vocab))))
    stopwords = _read(root / "results/token_analysis/stopwords/problem_stopwords.json")
    active = validate_projection(raw, filtered, raw_vocab, filtered_vocab, stopwords,
                                 filtered_data["active_indices"]["problems"])
    check("only_approved_problem_stopword_coordinates_removed", filtered.shape[1] == len(active))
    check("no_solutions_or_regression_data_generated", all(set(variant["vocabularies"]) == {"problems"}
          for variant in data["variants"].values()) and not (output / "02_regression").exists()
          and not (output / "03_gemini").exists())
    old_vocab = _read(root / "data/vectors/problems/vocabulary.json")
    indices = {token: i for i, token in enumerate(raw_vocab)}
    check("legacy_problem_vocabulary_fully_preserved_in_raw", set(old_vocab).issubset(indices))
    old_columns = [indices[token] for token in old_vocab]
    restored_columns = [i for i, token in enumerate(raw_vocab) if token not in set(old_vocab)]
    legacy_documents = [document for part in ("train", "test")
                        for document in _read(root / f"data/vectors/problems/{part}_vectors.json")["documents"]]
    check("all_legacy_coordinates_and_restored_counts_match_per_document",
          [row["id"] for row in legacy_documents] == all_ids
          and np.array_equal(raw[:, old_columns], [row["vector"] for row in legacy_documents])
          and all(int(raw[i, restored_columns].sum()) == int(row["ignored_token_count"])
                  for i, row in enumerate(legacy_documents)))
    oov = [row for row in _rows(root / "results/token_analysis/03_oov_analysis/excluded_tokens.csv")
           if row["region"] == "problems"]
    check("restored_tokens_equal_verified_problem_oov_inventory",
          {raw_vocab[i] for i in restored_columns} == {row["token"] for row in oov})
    for row in oov:
        column = raw[:, indices[row["token"]]]
        observed_ids = {identifier for identifier, value in zip(all_ids, column) if value > 0}
        check("restored_" + row["token"], int(column.sum()) == int(row["total_tf"])
              and int(np.count_nonzero(column)) == int(row["total_df"])
              and observed_ids == set(row["document_ids"].split(",")))
    recount = _rows(output / "00_dataset/recount_validation.csv")
    check("265_original_problem_recounts_recorded", len(recount) == 265
          and [row["id"] for row in recount] == all_ids
          and all(row["region"] == "problems" and row["split"] == ("train" if i < 185 else "test")
                  and int(row["token_count"]) == int(raw[i].sum())
                  and int(row["legacy_token_count"]) == sum(legacy_documents[i]["vector"])
                  and int(row["restored_token_count"]) == int(raw[i, restored_columns].sum())
                  and row["all_legacy_coordinates_match"] == "True" for i, row in enumerate(recount)))
    return {"raw_problem_dimensions": len(raw_vocab), "filtered_problem_dimensions": len(filtered_vocab),
            "removed_tokens": len(raw_vocab) - len(filtered_vocab), "restored_tokens": len(restored_columns),
            "raw_zero_vectors": int(np.count_nonzero(np.linalg.norm(raw, axis=1) == 0)),
            "filtered_zero_vectors": int(np.count_nonzero(np.linalg.norm(filtered, axis=1) == 0))}


def run(root, output, data, *, save=True):
    """저장된 데이터·군집 모델을 검사한다. save=False이면 모든 파일이 읽기 전용이다."""
    root, output = Path(root), Path(output)
    checks, detail = [], {}

    def check(name, passed):
        checks.append({"check": name, "passed": bool(passed)})

    def stage(name, callback):
        try:
            detail[name] = callback()
        except (ValueError, KeyError, TypeError, OSError, AssertionError, IndexError, StopIteration, RuntimeError) as error:
            checks.append({"check": name + "_completed", "passed": False,
                           "error": f"{type(error).__name__}: {error}"})

    before = {str(path.relative_to(output)): _hash(path) for path in output.rglob("*")
              if path.is_file() and path.name != "validation.json"}
    config = _read(output / "config.json")
    protected = config["protected_files_sha256"]
    changed = [name for name, expected in protected.items()
               if not (root / name).is_file() or _hash(root / name) != expected]
    check("original_data_models_results_and_stopword_lists_unchanged", not changed)
    check("dataset_identifier_matches_experiment_config", config["dataset_id"] == data["dataset_id"])
    stage("dataset", lambda: _check_dataset(root, output, data, check))
    stage("clustering", lambda: _check_clustering(root, output, data, check))
    links, broken = scan_links(output)
    check("all_markdown_relative_links_exist", not broken)
    stage("images", lambda: _check_images(output, check))
    after = {str(path.relative_to(output)): _hash(path) for path in output.rglob("*")
             if path.is_file() and path.name != "validation.json"}
    check("verification_does_not_modify_saved_data_models_or_reports", before == after)
    result = {"verified_at": datetime.now(timezone.utc).isoformat(),
              "scope": "full265_problem_bow_raw_vs_user_filtered_clustering_only",
              "dataset_id": data["dataset_id"], "checks": checks,
              "passed": sum(row["passed"] for row in checks), "failed": sum(not row["passed"] for row in checks),
              "protected_original_files": len(protected), "changed_original_files": changed,
              "markdown_file_links_checked": links, "broken_links": broken, **detail,
              "model_training_performed": False, "gemini_api_called": False,
              "limits": ["저장된 수치·파일·모델 대응 검증이다. 이미지 수학적 해석이나 가독성의 사람 확인을 대신하지 않는다.",
                         "전체265 어휘·중심·대표 라벨로 동일265문항을 평가한 탐색 결과이며 독립 테스트 성능이 아니다."]}
    result["complete"] = result["failed"] == 0
    if save:
        from .common import write_json
        write_json(output / "validation.json", result)
    return result


def _check_images(output, check):
    from PIL import Image
    images = list(output.rglob("*.png"))
    for path in images:
        with Image.open(path) as image:
            width, height = image.size
            image.verify()
        check("image_" + str(path.relative_to(output)), width >= 500 and height >= 300)
    check("clustering_images_present", len(images) >= 16)
    return {"decoded_png_count": len(images), "manual_visual_inspection": "별도 작업 기록 참조"}


def _check_clustering(root, output, data, check):
    import torch
    from sklearn.metrics import (adjusted_mutual_info_score, adjusted_rand_score,
                                 f1_score, normalized_mutual_info_score)

    directory = output / "01_clustering"
    all_ids = data["ids"]["train"] + data["ids"]["test"]
    original_split = {identifier: part for part, values in data["ids"].items() for identifier in values}
    expected_names = [f"{condition}_{level}_{method}" for condition in ("K0", "K1")
                      for level in FIELDS for method in ("euclidean", "spherical")]
    paths = list((directory / "experiments").glob("*/experiment.json"))
    check("exactly_16_full265_clustering_experiments", {path.parent.name for path in paths} == set(expected_names)
          and len(paths) == 16)
    summary = _rows(directory / "summary.csv")
    check("clustering_summary_16_unique_conditions", len(summary) == 16
          and len({(row["condition"], row["level"], row["method"]) for row in summary}) == 16)
    confusion_count = 0

    def independent_metrics(assignments, labels, predicted, k):
        return {"ari": adjusted_rand_score(labels, assignments),
                "ami": adjusted_mutual_info_score(labels, assignments),
                "nmi": normalized_mutual_info_score(labels, assignments),
                "majority_accuracy": sum(a == b for a, b in zip(labels, predicted)) / len(labels),
                "macro_f1": f1_score(labels, predicted, labels=sorted(set(labels) | set(predicted)),
                                     average="macro", zero_division=0),
                "weighted_f1": f1_score(labels, predicted, labels=sorted(set(labels) | set(predicted)),
                                        average="weighted", zero_division=0),
                "n": len(labels), "occupied_clusters": len(set(assignments)),
                "cluster_sizes": {str(c): assignments.count(c) for c in range(k)}}

    for name in expected_names:
        target = directory / "experiments" / name
        result = _read(target / "experiment.json")
        payload = {key: value for key, value in result.items() if key != "payload_sha256"}
        payload_sha = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                               separators=(",", ":")).encode()).hexdigest()
        check(name + "_saved_assignment_payload_digest", result["payload_sha256"] == payload_sha)
        condition, level, method = result["condition"], result["level"], result["method"]
        variant = "raw" if condition == "K0" else "filtered"
        arrays = data["variants"][variant]["arrays"]["problems"]
        matrix = torch.cat([torch.as_tensor(arrays[part], dtype=torch.float32) for part in ("train", "test")])
        vocabulary = data["variants"][variant]["vocabularies"]["problems"]
        labels = [label_path(data["records"][identifier], level) for identifier in all_ids]
        ordered_labels = sorted(set(labels))
        k = len(ordered_labels)
        config = result["config"]
        signature = hashlib.sha256(json.dumps(config, ensure_ascii=False, sort_keys=True,
                                              separators=(",", ":")).encode()).hexdigest()
        check(name + "_input_algorithm_and_fixed_settings", result["dataset_id"] == data["dataset_id"]
              and result["k"] == k and config["k"] == k
              and config["vocabulary"] == vocabulary and config["fit_ids"] == all_ids
              and config["matrix_sha256"] == hashlib.sha256(matrix.numpy().tobytes()).hexdigest()
              and config["seeds"] == [42, 43, 44, 45, 46] and config["restarts"] == 5
              and config["max_iter"] == 100 and _close(config["tolerance"], .0001)
              and config["algorithm_file_sha256"] == _hash(root / "mathhint_learning/TorchKMeans.py")
              and config["fit_scope"] == "all_265" and result["fit_scope"] == "all"
              and result["evaluation_scope"] == "same_all_documents_not_generalization"
              and result["config_sha256"] == signature)
        documents = result["documents"]
        assignments = [int(row["cluster"]) for row in documents]
        mapping = majority_mapping(assignments, labels)
        predicted = [mapping[cluster] for cluster in assignments]
        check(name + "_all265_ids_original_provenance_and_actual_paths", [row["id"] for row in documents] == all_ids
              and all(row["original_split"] == original_split[row["id"]]
                      and row["actual_label"] == labels[i]
                      and all(row[field] == data["records"][row["id"]][field] for field in FIELDS)
                      for i, row in enumerate(documents)))
        check(name + "_same_all265_majority_labels_and_tie_policy", result["full_majority_labels"] ==
              {str(cluster): label for cluster, label in mapping.items()}
              and [row["full_majority_label"] for row in documents] == predicted
              and all(row["matches_full_majority"] == (labels[i] == predicted[i]) for i, row in enumerate(documents)))
        metrics = independent_metrics(assignments, labels, predicted, k)
        check(name + "_independent_metrics", all(_close(result["metrics"][key], value)
              for key, value in metrics.items() if key != "cluster_sizes")
              and result["metrics"]["cluster_sizes"] == metrics["cluster_sizes"]
              and sum(result["metrics"]["cluster_sizes"].values()) == 265)
        summary_row = next(row for row in summary if row["condition"] == condition
                           and row["level"] == level and row["method"] == method)
        check(name + "_summary_values", all(_close(summary_row[key], value)
              for key, value in metrics.items() if key != "cluster_sizes")
              and int(summary_row["k"]) == k and int(summary_row["feature_dim"]) == len(vocabulary))
        restarts = result["restarts"]
        selected = min(range(len(restarts)), key=lambda i: restarts[i]["training_objective"])
        chosen = restarts[selected]
        check(name + "_seed_selected_by_fit_objective_only", [row["seed"] for row in restarts] == [42, 43, 44, 45, 46]
              and result["selected_seed"] == chosen["seed"] and chosen["assignments"] == assignments
              and _close(result["selected_training_objective"], chosen["training_objective"])
              and all(math.isfinite(float(row["training_objective"])) and 1 <= row["iterations"] <= 100
                      for row in restarts))
        for trial in restarts:
            groups = trial["assignments"]
            majority = majority_mapping(groups, labels)
            expected = independent_metrics(groups, labels, [majority[group] for group in groups], k)
            check(name + f"_seed{trial['seed']}_metrics", len(groups) == 265
                  and all(0 <= group < k for group in groups)
                  and all(_close(trial["metrics"][key], value) for key, value in expected.items() if key != "cluster_sizes")
                  and trial["metrics"]["cluster_sizes"] == expected["cluster_sizes"])
        model_path = target / "model.pt"
        checkpoint = torch.load(model_path, map_location="cpu", weights_only=True)
        centers = checkpoint["centers"].float()
        check(name + "_saved_model_identity", _hash(model_path) == result["model_sha256"]
              and checkpoint["config_sha256"] == signature and checkpoint["dataset_id"] == data["dataset_id"]
              and checkpoint["fit_ids"] == all_ids and checkpoint["original_splits"] == data["ids"]
              and checkpoint["input_vocabulary"] == vocabulary and centers.shape == (k, len(vocabulary))
              and torch.isfinite(centers).all().item()
              and checkpoint["assignments"].tolist() == assignments)
        if method == "euclidean":
            assigned = torch.cdist(matrix, centers).argmin(dim=1)
            objective = ((matrix - centers[assigned]) ** 2).sum().item()
            objective_name = "inertia"
        else:
            normalized = torch.nn.functional.normalize(matrix, p=2, dim=1, eps=1e-12)
            normalized_centers = torch.nn.functional.normalize(centers, p=2, dim=1, eps=1e-12)
            assigned = (normalized @ normalized_centers.T).argmax(dim=1)
            objective = (1 - (normalized * centers[assigned]).sum(dim=1)).sum().item()
            objective_name = "cosine_loss"
            norms = torch.linalg.vector_norm(centers, dim=1)
            check(name + "_spherical_centers_l2_normalized", bool(torch.all((norms < 1e-7) | ((norms - 1).abs() < 1e-5))))
        check(name + "_saved_centers_assignments_and_training_objective", assigned.tolist() == assignments
              and result["training_objective_name"] == objective_name
              and _close(objective, result["selected_training_objective"]))
        confusion_count += _check_cluster_tables(target, labels, predicted, assignments, ordered_labels,
                                                metrics, check, name)
    check("16_full265_confusion_matrices_checked", confusion_count == 16)
    return {"experiment_count": len(expected_names), "confusion_matrices": confusion_count,
            "seed_runs_checked": len(expected_names) * 5,
            "evaluation_count_per_experiment": 265, "majority_scope": "same265_exploratory"}


def _check_cluster_tables(target, actual, predicted, assignments, labels, metrics, check, name):
    keys = _rows(target / "label_key.csv")
    codes = [row["label_code"] for row in keys]
    check(name + "_complete_hierarchical_label_codes_and_order", [row["actual_label"] for row in keys] == labels
          and codes == [f"L{i + 1:02d}" for i in range(len(labels))])
    rows = _rows(target / "confusion_matrix_all.csv")
    matrix = np.asarray([[int(row[code]) for code in codes] for row in rows], dtype=np.int64)
    expected = expected_confusion(actual, predicted, labels)
    check(name + "_confusion_rows_columns_counts_and_diagonal", len(rows) == len(labels)
          and list(rows[0]) == ["label_code", "actual_label"] + codes
          and [row["actual_label"] for row in rows] == labels
          and [row["label_code"] for row in rows] == codes
          and np.array_equal(matrix, expected) and int(matrix.sum()) == 265
          and _close(np.trace(matrix) / 265, metrics["majority_accuracy"]))
    check(name + "_confusion_image_present", (target / "figures/confusion_matrix_all.png").is_file())
    k = len(metrics["cluster_sizes"])
    cross = _rows(target / "cross_tab_all.csv")
    cross_columns = [f"cluster_{cluster:02d}" for cluster in range(k)]
    table = np.asarray([[int(row[column]) for column in cross_columns] for row in cross], dtype=np.int64)
    expected_cross = np.zeros((len(labels), k), dtype=np.int64)
    positions = {label: i for i, label in enumerate(labels)}
    for observed, cluster in zip(actual, assignments):
        expected_cross[positions[observed], cluster] += 1
    check(name + "_cross_tab_preserves_cluster_numbers", len(cross) == len(labels)
          and list(cross[0]) == ["label_code", "actual_label"] + cross_columns
          and [row["actual_label"] for row in cross] == labels
          and [row["label_code"] for row in cross] == codes
          and np.array_equal(table, expected_cross) and int(table.sum()) == 265)
    members = _rows(target / "members.csv")
    saved = _read(target / "experiment.json")["documents"]
    check(name + "_member_csv_matches_saved_assignments", len(members) == 265
          and [row["id"] for row in members] == [row["id"] for row in saved]
          and [int(row["cluster"]) for row in members] == assignments
          and [row["actual_label"] for row in members] == actual
          and [row["full_majority_label"] for row in members] == predicted
          and [row["original_split"] for row in members] == [row["original_split"] for row in saved])
    summaries = _rows(target / "cluster_summary.csv")
    check(name + "_all_k_cluster_sizes_and_member_ids", len(summaries) == k
          and [int(row["cluster"]) for row in summaries] == list(range(k))
          and all(int(row["n"]) == metrics["cluster_sizes"][str(cluster)]
                  and row["ids"] == ",".join(item["id"] for item in saved if item["cluster"] == cluster)
                  and int(row["original_train_n"]) == sum(item["cluster"] == cluster and item["original_split"] == "train"
                                                           for item in saved)
                  and int(row["original_test_n"]) == sum(item["cluster"] == cluster and item["original_split"] == "test"
                                                          for item in saved)
                  for cluster, row in enumerate(summaries)))
    distribution = _rows(target / "cluster_label_distribution.csv")
    expected_distribution = Counter(zip(assignments, actual))
    check(name + "_cluster_label_composition", len(distribution) == len(expected_distribution)
          and sum(int(row["count"]) for row in distribution) == 265
          and all(int(row["count"]) == expected_distribution[int(row["cluster"]), row["actual_label"]]
                  and int(row["cluster_n"]) == metrics["cluster_sizes"][row["cluster"]]
                  and _close(row["ratio"], int(row["count"]) / int(row["cluster_n"])) for row in distribution))
    dispersion = _rows(target / "label_dispersion.csv")
    check(name + "_label_dispersion_counts", [row["actual_label"] for row in dispersion] == labels
          and all(int(row["n"]) == int(expected_cross[i].sum())
                  and int(row["occupied_clusters"]) == int(np.count_nonzero(expected_cross[i]))
                  and row["cluster_ids"] == ",".join(str(cluster) for cluster in range(k) if expected_cross[i, cluster])
                  and _close(row["largest_cluster_share"], expected_cross[i].max() / expected_cross[i].sum())
                  for i, row in enumerate(dispersion)))
    return 1
