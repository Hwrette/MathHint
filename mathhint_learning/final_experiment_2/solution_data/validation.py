"""저장된 문제·풀이 빈도와 분할을 독립 대조한다. 토큰화·학습·API는 실행하지 않는다."""

import csv
from datetime import datetime, timezone
import importlib
import json
from pathlib import Path

import numpy as np

from .common import ROOT, file_hash, fingerprint, read_json, write_json


def _csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def validate_filter(raw, filtered, vocabulary, active_vocabulary, active_indices, stopwords):
    """같은 크기의 어휘 순서 변경과 승인 외 좌표·행 변경도 거부한다."""
    raw, filtered = np.asarray(raw), np.asarray(filtered)
    selected = set(stopwords)
    expected = [j for j, token in enumerate(vocabulary) if token not in selected]
    if (raw.ndim != 2 or filtered.ndim != 2 or raw.shape[1] != len(vocabulary)
            or filtered.shape != (raw.shape[0], len(expected))
            or len(vocabulary) != len(set(vocabulary))
            or list(active_indices) != expected
            or list(active_vocabulary) != [vocabulary[j] for j in expected]):
        raise ValueError("풀이 원시·활성 어휘의 인덱스/차원/순서가 다릅니다.")
    if (not np.isfinite(raw).all() or np.any(raw < 0) or not np.array_equal(raw, np.floor(raw))
            or not np.array_equal(filtered, raw[:, expected])):
        raise ValueError("승인 불용어 외 빈도 좌표나 문항 행이 변경되었습니다.")
    return expected


def validate_dataset(root=ROOT, *, save=False):
    """모든 실제 빈도·TF/DF·행·검증 분할을 대조하고 선택적으로 새 검증 기록만 저장한다."""
    root = Path(root).resolve()
    output = root / "results/final_experiment_2/solution_data"
    before = {str(p.relative_to(output)): file_hash(p) for p in output.rglob("*")
              if p.is_file() and p.name != "validation.json"}
    checks = []

    def check(name, condition):
        checks.append({"check": name, "passed": bool(condition)})

    config = read_json(output / "config.json")
    manifest = read_json(output / "manifest.json")
    dataset_id = config["dataset_id"]
    source = config["source_definition"]
    protected = config["protected_files_sha256"]
    changed = [name for name, expected in protected.items()
               if not (root / name).is_file() or file_hash(root / name) != expected]
    check("all_original_data_models_responses_token_analysis_and_cluster_results_preserved", not changed)
    check("dataset_identifier_is_source_definition_digest", dataset_id == fingerprint(source) == manifest["dataset_id"])
    check("all_prepared_artifact_hashes_match", all((output / name).is_file() and file_hash(output / name) == value
          for name, value in manifest["files_sha256"].items()))
    check("all_source_hashes_match", config["source_files_sha256"] == source["files"] and
          all((root / name).is_file() and file_hash(root / name) == value
              for name, value in config["source_files_sha256"].items()))
    original = {p: read_json(root / f"data/processed/splits/{p}.json") for p in ("train", "test")}
    ids = original["train"] + original["test"]
    records = read_json(root / "data/processed/metadata.json")["records"]
    split = read_json(output / "generated_data/splits.json")
    check("original265_ids_and_185_80_order_preserved", len(ids) == len(set(ids)) == 265
          and len(original["train"]) == 185 and len(original["test"]) == 80
          and not set(original["train"]) & set(original["test"])
          and {r["id"] for r in records} == set(ids)
          and all(split[p] == original[p] == source["ids"][p] for p in ("train", "test")))
    fit, validation = split["fit"], split["validation"]
    check("inner_split_is_148_37_subset_of_original_train_only", len(fit) == len(set(fit)) == 148
          and len(validation) == len(set(validation)) == 37 and not set(fit) & set(validation)
          and set(fit + validation) == set(original["train"])
          and not set(fit + validation) & set(original["test"])
          and all(source["ids"][p] == split[p] for p in ("fit", "validation")))
    from sklearn.model_selection import train_test_split
    by_id = {row["id"]: row for row in records}
    strata = [tuple(by_id[i][field] for field in ("curriculum", "unit")) for i in original["train"]]
    groups = [" / ".join(values) for values in strata]
    expected_fit, expected_validation = train_test_split(original["train"], test_size=37, random_state=42, stratify=groups)
    check("internal_split_reproduces_preregistered_seed42_stratification", set(expected_fit) == set(fit)
          and set(expected_validation) == set(validation)
          and fit == [i for i in original["train"] if i in set(fit)]
          and validation == [i for i in original["train"] if i in set(validation)])
    policy = config["selection_policy"]
    check("selection_policy_precision20_before_test", policy == source["selection_policy"]
          and policy["primary"] == "validation_precision_at_20_maximize"
          and policy["precision_denominator"] == 20 and policy["internal_split_seed"] == 42
          and policy["validation_count"] == 37
          and policy["test_policy"] == "no_test_target_loading_until_model_selection_freeze")

    reference = read_json(output / "generated_data/input_reference.json")
    problem_vocab = read_json(root / reference["problem_vocabulary_path"])
    problem_payload = read_json(root / reference["problem_vectors_path"])
    expected_prefix = "results/final_experiment_2/cluster_improvement/00_dataset/generated_data/filtered/problems"
    check("problem_counts_reused_without_new_tokenization_or_normalization", reference["problem_vectors_path"] == expected_prefix + "/all_vectors.json"
          and reference["problem_vocabulary_path"] == expected_prefix + "/vocabulary.json"
          and reference["problem_vectors_sha256"] == file_hash(root / reference["problem_vectors_path"])
          and reference["problem_vocabulary_sha256"] == file_hash(root / reference["problem_vocabulary_path"])
          and len(problem_vocab) == reference["dimension"] == 270
          and problem_payload["shape"] == [265, len(problem_vocab)]
          and [r["id"] for r in problem_payload["documents"]] == ids)

    raw_vocab = read_json(output / "generated_data/raw/solutions/vocabulary.json")
    active_vocab = read_json(output / "generated_data/filtered/solutions/vocabulary.json")
    payloads = {kind: read_json(output / f"generated_data/{kind}/solutions/all_vectors.json")
                for kind in ("raw", "filtered")}
    arrays = {kind: np.asarray([row["vector"] for row in payload["documents"]], dtype=np.int64)
              for kind, payload in payloads.items()}
    raw, filtered = arrays["raw"], arrays["filtered"]
    for kind, vocabulary in (("raw", raw_vocab), ("filtered", active_vocab)):
        payload = payloads[kind]
        check(kind + "_solution_ids_and_integer_coordinates", payload["dataset_id"] == dataset_id
              and payload["vocabulary_fitted_on"] == "full265" and payload["region"] == "solutions"
              and payload["variant"] == kind and payload["shape"] == [265, len(vocabulary)]
              and [row["id"] for row in payload["documents"]] == ids
              and len(vocabulary) == len(set(vocabulary))
              and vocabulary == sorted(vocabulary)
              and all(len(row["vector"]) == len(vocabulary) and
                      all(type(v) is int and v >= 0 for v in row["vector"]) for row in payload["documents"])
              and all(row["original_split"] == ("train" if j < 185 else "test")
                      and row["token_count"] == int(arrays[kind][j].sum())
                      and row["raw_token_count"] == int(raw[j].sum())
                      for j, row in enumerate(payload["documents"])))
    choices = read_json(root / config["stopwords"]["path"])
    selected = set(choices)
    active = validate_filter(raw, filtered, raw_vocab, active_vocab, source["active_indices"], choices)
    check("only_approved103_solution_stopwords_removed", config["stopwords"]["tokens"] == choices
          and config["stopwords"]["sha256"] == file_hash(root / config["stopwords"]["path"])
          and len(choices) == 103 and len(set(raw_vocab) & selected) == 103)
    check("raw_vocabulary_and_matrix_reproduce_source_identity", source["raw_solution_vocabulary"] == raw_vocab
          and source["raw_vectors_sha256"] == fingerprint(raw.tolist())
          and np.all(raw.sum(axis=0) > 0))

    old_vocab = read_json(root / "data/vectors/solutions/vocabulary.json")
    positions = {token: j for j, token in enumerate(raw_vocab)}
    old_columns = [positions[token] for token in old_vocab]
    restored = [j for j, token in enumerate(raw_vocab) if token not in set(old_vocab)]
    old_docs = [row for p in ("train", "test")
                for row in read_json(root / f"data/vectors/solutions/{p}_vectors.json")["documents"]]
    check("every_original_solution_coordinate_and_document_count_preserved", [r["id"] for r in old_docs] == ids
          and np.array_equal(raw[:, old_columns], [r["vector"] for r in old_docs])
          and all(int(raw[j].sum()) == row["token_count"]
                  and int(raw[j, restored].sum()) == row["ignored_token_count"] for j, row in enumerate(old_docs)))
    oov = [row for row in _csv(root / "results/token_analysis/03_oov_analysis/excluded_tokens.csv") if row["region"] == "solutions"]
    check("restored_solution_tokens_equal_original_oov_inventory", {raw_vocab[j] for j in restored} == {row["token"] for row in oov})
    for row in oov:
        column = raw[:, positions[row["token"]]]
        check("restored_" + row["token"], int(column.sum()) == int(row["total_tf"])
              and int(np.count_nonzero(column)) == int(row["total_df"])
              and {i for i, count in zip(ids, column) if count} == set(row["document_ids"].split(",")))

    mapping = _csv(output / "solution_token_mapping.csv")
    check("complete_raw_and_active_token_mapping", len(mapping) == len(raw_vocab)
          and [r["token"] for r in mapping] == raw_vocab)
    active_positions = {j: i for i, j in enumerate(active)}
    legacy_positions = {t: j for j, t in enumerate(old_vocab)}
    for j, row in enumerate(mapping):
        check(f"solution_coordinate_{j}_mapping_tf_df", int(row["raw_index"]) == j
              and row["active_index"] == (str(active_positions[j]) if j in active_positions else ""))
        check(f"solution_coordinate_{j}_frequency_and_removal", row["removed"] == str(row["token"] in selected)
              and int(row["total_tf"]) == int(raw[:, j].sum())
              and int(row["total_df"]) == int(np.count_nonzero(raw[:, j]))
              and row["legacy_index"] == (str(legacy_positions[row["token"]]) if row["token"] in legacy_positions else ""))
    audit = _csv(output / "stopword_audit.csv")
    check("stopword_audit_preserves_user_order_and_counts", [r["token"] for r in audit] == list(dict.fromkeys(choices))
          and all(row["found"] == str(row["token"] in positions)
                  and int(row["total_tf"]) == (int(raw[:, positions[row["token"]]].sum()) if row["token"] in positions else 0)
                  and int(row["total_df"]) == (int(np.count_nonzero(raw[:, positions[row["token"]]])) if row["token"] in positions else 0)
                  for row in audit))
    counts = _csv(output / "question_token_counts.csv")
    recount = _csv(output / "recount_validation.csv")
    check("all265_per_document_before_after_counts", len(counts) == 265 and [r["id"] for r in counts] == ids
          and all(int(r["raw_tf"]) == int(raw[j].sum()) and int(r["filtered_tf"]) == int(filtered[j].sum())
                  and int(r["removed_tf"]) == int(raw[j].sum() - filtered[j].sum())
                  and r["original_split"] == ("train" if j < 185 else "test") for j, r in enumerate(counts)))
    check("all265_fresh_solution_recount_records_match", len(recount) == 265 and [r["id"] for r in recount] == ids
          and all(r["all_legacy_coordinates_match"] == "True"
                  and int(r["token_count"]) == int(raw[j].sum())
                  and int(r["restored_token_count"]) == int(raw[j, restored].sum()) for j, r in enumerate(recount)))
    summary = read_json(output / "summary.json")
    expected = {"n": 265, "train": 185, "test": 80, "inner_fit": 148, "validation": 37,
                "input_dimension": len(problem_vocab), "raw_solution_dimension": len(raw_vocab),
                "output_dimension": len(active_vocab), "registered_solution_stopwords": len(choices),
                "removed_solution_stopwords": len(set(raw_vocab) & selected), "unknown_stopwords": sorted(selected - set(raw_vocab)),
                "duplicate_choices": len(choices) - len(selected), "raw_solution_tf": int(raw.sum()),
                "filtered_solution_tf": int(filtered.sum()), "raw_zero_vectors": int(np.count_nonzero(raw.sum(axis=1) == 0)),
                "filtered_zero_vectors": int(np.count_nonzero(filtered.sum(axis=1) == 0)),
                "new_problem_tokenizations": 0, "new_solution_tokenizations": 265,
                "test_only_active_solution_tokens": [t for j, t in enumerate(active_vocab) if not np.any(filtered[:185, j])]}
    check("summary_matches_actual_vectors_and_policy", summary == expected)
    from .prepare import load_data
    locked = load_data(root, include_test=False)
    check("selection_loader_exposes_only_train_fit_validation_tensors", not locked["test_targets_loaded"]
          and all(set(parts) == {"train", "fit", "validation"} for parts in locked["arrays"].values())
          and locked["ids"]["fit"] == fit and locked["ids"]["validation"] == validation)
    after = {str(p.relative_to(output)): file_hash(p) for p in output.rglob("*")
             if p.is_file() and p.name != "validation.json"}
    check("validation_does_not_modify_saved_data_or_originals", before == after)
    result = {"verified_at": datetime.now(timezone.utc).isoformat(), "dataset_id": dataset_id,
              "passed": sum(c["passed"] for c in checks), "failed": sum(not c["passed"] for c in checks),
              "checks": checks, "protected_original_files": len(protected), "changed_original_files": changed,
              "input_dimension": len(problem_vocab), "raw_solution_dimension": len(raw_vocab),
              "output_dimension": len(active_vocab), "n": len(ids), "inner_fit": len(fit), "validation": len(validation),
              "test_only_active_solution_tokens": len(expected["test_only_active_solution_tokens"]),
              "training_performed": False, "api_calls": 0, "tokenizer_calls": 0,
              "limitations": ["원문 새 토큰화는 prepare 단계에서 수행했고 이 검증은 저장된 계수·원문 SHA·원래 좌표와 OOV 근거를 대조한다.",
                              "전체265 어휘는 테스트 표현도 포함하며, 모델 학습·선택에 테스트 타깃을 사용하는 것을 허용하지 않는다."]}
    result["complete"] = result["failed"] == 0
    if save:
        write_json(output / "validation.json", result)
    return result


def independent_scores(prediction, actual):
    """저장 예측을 float64로 독립 집계한다. 순위는 양수/원래 좌표순, P@20 분모20."""
    prediction, actual = np.asarray(prediction, dtype=float), np.asarray(actual, dtype=float)
    if prediction.ndim == 1:
        prediction, actual = prediction[None, :], actual[None, :]
    if prediction.shape != actual.shape or prediction.ndim != 2 or not len(actual):
        raise ValueError("실제·예측 빈도의 행과 좌표가 다릅니다.")
    error = prediction - actual
    denominator = np.maximum(np.linalg.norm(prediction, axis=1), 1e-8) * np.maximum(np.linalg.norm(actual, axis=1), 1e-8)

    def top(row):
        return sorted(np.flatnonzero(row > 0), key=lambda j: (-row[j], j))[:20]

    counts, recalls, actual_short, predicted_short = [], [], 0, 0
    for observed, predicted in zip(actual, np.maximum(prediction, 0)):
        a, p = set(top(observed)), set(top(predicted))
        common = len(a & p)
        counts.append(common)
        if a:
            recalls.append(common / len(a))
        actual_short += len(a) < 20
        predicted_short += len(p) < 20
    return {"mse": float(np.mean(error ** 2)), "mae": float(np.mean(abs(error))),
            "cosine_similarity": float(np.mean((prediction * actual).sum(axis=1) / denominator)),
            "precision_at_20": float(np.mean(counts) / 20),
            "recall_at_20": float(np.mean(recalls)) if recalls else None,
            "mean_common_top20_count": float(np.mean(counts)),
            "actual_fewer_than_20": int(actual_short), "predicted_fewer_than_20": int(predicted_short),
            "n": len(actual)}


def _validate_deep_search(output, data, configuration, selection, module, check, close):
    """실제 저장된12시드 실행과 상위2구성 평균 선택을 재학습 없이 대조한다."""
    import torch
    trials = [read_json(path) for path in sorted((output / "search_trials").glob("*.json"))]
    lookup = {(row["candidate_id"], row["seed"]): row for row in trials}
    state = read_json(output / "search_state.json")
    configurations = state["configurations"]
    order = {row["candidate_id"]: j for j, row in enumerate(configurations)}
    check("deep_bounded_six_plus_two_configurations_and_12_seed_trials", len(configurations) == 8
          and len(order) == 8 and configurations[:6] == configuration["initial_candidates"]
          and len(trials) == len(lookup) == selection["completed_seed_trials"] == 12
          and selection["completed_configurations"] == 8
          and state["signature"] == configuration["signature"])
    expected_signature = fingerprint({"dataset_id": data["dataset_id"], "policy": configuration["policy"],
        "fit_ids": data["ids"]["fit"], "validation_ids": data["ids"]["validation"],
        "model_source_sha256": file_hash(Path(module.__file__)),
        "initial_candidates": configuration["initial_candidates"]})
    check("deep_search_signature_binds_data_policy_and_model_source", configuration["signature"] == expected_signature)

    def rank(row):
        return (-row["metrics"]["precision_at_20"], row["metrics"]["mse"], order[row["candidate_id"]])

    seed42 = [lookup[row["candidate_id"], 42] for row in configurations]
    coarse = min(seed42[:6], key=rank)
    base = coarse["configuration"]
    expected_refinements = [
        {**base, "candidate_id": "M6", "stage": "refinement",
         "dropout": min(.35, max(.1, base["dropout"] + .1)), "weight_decay": max(.001, base["weight_decay"] * 3)},
        {**base, "candidate_id": "M7", "stage": "refinement", "learning_rate": base["learning_rate"] / 2}]
    check("deep_refinement_depends_only_on_best_internal_validation_configuration", configurations[6:] == expected_refinements
          and state["refinement_reason"]["coarse_best"] == coarse["candidate_id"])
    finalists = sorted(seed42, key=rank)[:2]
    expected_keys = {(row["candidate_id"], 42) for row in seed42} | {
        (row["candidate_id"], seed) for row in finalists for seed in (43, 44)}
    check("deep_only_top_two_configurations_get_seed43_and44", set(lookup) == expected_keys)
    for trial in trials:
        label = trial["candidate_id"] + f"_seed{trial['seed']}"
        path = output / "checkpoints/search" / (label + ".pt")
        saved = torch.load(path, map_location="cpu", weights_only=True)
        check(label + "_checkpoint_uses_only_fit148_validation37", file_hash(path) == trial["checkpoint_sha256"]
              and saved["dataset_id"] == data["dataset_id"] and not saved["test_targets_available"]
              and saved["fit_ids"] == data["ids"]["fit"] and saved["validation_ids"] == data["ids"]["validation"]
              and saved["configuration"] == {**trial["configuration"], "seed": trial["seed"]}
              and saved["best_epoch"] == trial["best_epoch"])
        with torch.no_grad():
            predicted = module.restore(saved)(data["arrays"]["problems"]["validation"]).numpy()
        expected = independent_scores(np.maximum(predicted, 0), data["arrays"]["solutions"]["validation"].numpy())
        check(label + "_validation_metrics_independently_reproduced", all(close(value, trial["metrics"][key])
              for key, value in expected.items()))
        history = trial["history"]
        best = min(history, key=lambda point: (-point["validation_precision_at_20"], point["validation_clipped_mse"]))
        check(label + "_best_epoch_selected_without_test_metrics", best["epoch"] == trial["best_epoch"]
              and close(best["validation_precision_at_20"], trial["metrics"]["precision_at_20"])
              and close(best["validation_clipped_mse"], trial["metrics"]["mse"])
              and history[0]["epoch"] == 0 and history[-1]["epoch"] == trial["stopped_epoch"]
              and 0 <= trial["best_epoch"] <= trial["stopped_epoch"] <= trial["configuration"]["max_epochs"])
    aggregates = selection["all_configuration_stability"]
    check("deep_stability_contains_exact_top_two_configuration_ids", [a["candidate_id"] for a in aggregates] ==
          [row["candidate_id"] for row in finalists])
    for aggregate in aggregates:
        group = [lookup[aggregate["candidate_id"], seed] for seed in (42, 43, 44)]
        scores = [row["metrics"]["precision_at_20"] for row in group]
        errors = [row["metrics"]["mse"] for row in group]
        check(aggregate["candidate_id"] + "_three_seed_mean_and_population_sd", close(aggregate["precision_at_20"], np.mean(scores))
              and close(aggregate["mse"], np.mean(errors))
              and close(aggregate["precision_std_ddof0"], np.std(scores))
              and aggregate["best_epochs"] == [row["best_epoch"] for row in group]
              and [r["seed"] for r in aggregate["seed_metrics"]] == [42, 43, 44])
    stability = _csv(output / "configuration_stability.csv")
    aggregate_by_id = {a["candidate_id"]: a for a in aggregates}
    check("deep_stability_csv_matches_trial_means_and_population_sd", len(stability) == len(aggregates)
          and {row["candidate_id"] for row in stability} == set(aggregate_by_id)
          and all(close(row["mean_precision_at_20"], aggregate_by_id[row["candidate_id"]]["precision_at_20"])
                  and close(row["mean_mse"], aggregate_by_id[row["candidate_id"]]["mse"])
                  and close(row["precision_std_ddof0"], aggregate_by_id[row["candidate_id"]]["precision_std_ddof0"])
                  and row["seeds"] == "42,43,44"
                  and json.loads(row["best_epochs"]) == aggregate_by_id[row["candidate_id"]]["best_epochs"] for row in stability))
    comparison = _csv(output / "model_comparison.csv")
    trial_rows = [row for row in comparison if row["candidate_id"] != "training_mean"]
    check("deep_candidate_csv_reports_all12_actual_trial_results", len(trial_rows) == len(trials)
          and all((row["configuration_id"], int(row["seed"])) in lookup and
                  all(close(row[key], value) for key, value in lookup[row["configuration_id"], int(row["seed"])]["metrics"].items())
                  for row in trial_rows))
    selected = min(aggregates, key=lambda a: (-a["precision_at_20"], a["mse"], order[a["candidate_id"]]))
    expected_configuration = {**selected["configuration"], "seed": 42,
                              "epochs": max(1, int(np.median(selected["best_epochs"])))}
    check("deep_configuration_chosen_by_three_seed_mean_precision_then_mean_mse", selection["selected_configuration"] == expected_configuration
          and selection["configuration_stability_metrics"] == selected
          and selection["final_refit_epochs"] == expected_configuration["epochs"])
    check("deep_reported_validation_metrics_are_selected_seed42_not_in_sample_final_model", selection["selected_validation_metrics"] ==
          lookup[selected["candidate_id"], 42]["metrics"])


def validate_model(root=ROOT, model_name="regression", *, save=False):
    """동결 모델을 복원·추론하여 저장 예측과 평가를 대조한다. 가중치 학습은 없다."""
    import torch
    from .prepare import load_data
    if model_name not in ("regression", "deep_learning"):
        raise ValueError("회귀 또는 딥러닝의 동결 결과만 검증합니다.")
    root = Path(root).resolve()
    output = root / "results/final_experiment_2" / model_name
    before = {str(p.relative_to(output)): file_hash(p) for p in output.rglob("*")
              if p.is_file() and p.name != "validation.json"}
    checks = []

    def check(name, condition):
        checks.append({"check": name, "passed": bool(condition)})

    def close(a, b):
        return a is None and b in (None, "") or a is not None and b not in (None, "") and bool(
            np.isclose(float(a), float(b), rtol=3e-6, atol=3e-7))

    data = load_data(root, include_test=True)
    manifest = read_json(output / "model_manifest.json")
    selection = read_json(output / "selection.json")
    configuration = read_json(output / "config.json")
    check("frozen_model_dataset_and_selection_identity", manifest["dataset_id"] == selection["dataset_id"] == data["dataset_id"]
          and manifest["frozen"] and manifest["frozen_before_test"]
          and not selection["test_targets_used_for_selection"]
          and manifest["selection_sha256"] == file_hash(output / "selection.json")
          and manifest["selected_configuration"] == selection["selected_configuration"])
    for key in ("checkpoint", "predictions"):
        info = manifest[key]
        check(key + "_file_matches_frozen_hash", file_hash(output / info["path"]) == info["sha256"])
    checkpoint = torch.load(output / manifest["checkpoint"]["path"], map_location="cpu", weights_only=True)
    check("weights_frozen_before_test_and_refit_only_train185", checkpoint["dataset_id"] == data["dataset_id"]
          and checkpoint["saved_before_loading_test_targets"] and checkpoint["final_refit_training_count"] == 185
          and checkpoint["selection"] == selection
          and datetime.fromisoformat(selection["frozen_at"]) <= datetime.fromisoformat(checkpoint["saved_at"])
          <= datetime.fromisoformat(manifest["finalized_at"]))
    check("checkpoint_vocabularies_and_all_ids_preserved", checkpoint["input_vocabulary"] == data["vocabularies"]["problems"]
          and checkpoint["output_vocabulary"] == data["vocabularies"]["solutions"]
          and checkpoint["input_dim"] == len(data["vocabularies"]["problems"])
          and checkpoint["output_dim"] == len(data["vocabularies"]["solutions"])
          and all(checkpoint[p + "_ids"] == data["ids"][p] == selection[p + "_ids"]
                  for p in ("fit", "validation"))
          and all(checkpoint[p + "_ids"] == data["ids"][p] == manifest[p + "_ids"]
                  for p in ("train", "test")))
    module = importlib.import_module(f"mathhint_learning.final_experiment_2.{model_name}.model")
    model = module.restore(checkpoint).eval()
    if model_name == "deep_learning":
        nonlinear = (torch.nn.ReLU, torch.nn.GELU, torch.nn.SiLU, torch.nn.Tanh, torch.nn.ELU, torch.nn.Softplus)
        check("actual_nonlinear_sequential_architecture", isinstance(model, torch.nn.Sequential)
              and sum(isinstance(layer, torch.nn.Linear) for layer in model.modules()) >= 2
              and any(isinstance(layer, nonlinear) for layer in model.modules()))
    else:
        check("actual_linear_affine_architecture", isinstance(model, torch.nn.Linear))
    payload = read_json(output / manifest["predictions"]["path"])
    documents = payload["documents"]
    ids = data["ids"]["train"] + data["ids"]["test"]
    check("all265_prediction_rows_and_unambiguous_vocabularies", payload["dataset_id"] == data["dataset_id"]
          and payload["vocabulary"] == data["vocabularies"]["solutions"]
          and payload["input_vocabulary"] == data["vocabularies"]["problems"]
          and [row["id"] for row in documents] == ids and len(set(ids)) == 265
          and all(row["split"] == ("train" if j < 185 else "test") for j, row in enumerate(documents))
          and not payload["actual_solution_vectors_included"]
          and not any("actual_vector" in row for row in documents))
    stored = np.asarray([row["raw_predicted_vector"] for row in documents], dtype=float)
    clipped = np.asarray([row["predicted_vector"] for row in documents], dtype=float)
    check("raw_real_predictions_and_negative_only_correction", stored.shape == clipped.shape == (265, checkpoint["output_dim"])
          and np.isfinite(stored).all() and np.array_equal(clipped, np.maximum(stored, 0)))
    with torch.no_grad():
        generated = {p: model(data["arrays"]["problems"][p]).cpu().numpy() for p in ("train", "test")}
    check("frozen_checkpoint_reproduces_all265_saved_predictions", np.allclose(
          np.concatenate([generated[p] for p in ("train", "test")]), stored, rtol=3e-6, atol=3e-7))
    validation_checkpoint = torch.load(output / "checkpoints/best_validation.pt", map_location="cpu", weights_only=True)
    validation_model = module.restore(validation_checkpoint).eval()
    with torch.no_grad():
        validation_prediction = validation_model(data["arrays"]["problems"]["validation"]).cpu().numpy()
    validation_actual = data["arrays"]["solutions"]["validation"].numpy()
    scores = independent_scores(np.maximum(validation_prediction, 0), validation_actual)
    check("selected_internal_validation_scores_reproduced", all(close(value, selection["selected_validation_metrics"][key])
          for key, value in scores.items()))
    check("validation_selection_uses_exact_fit148_validation37", selection["fit_ids"] == configuration["fit_ids"] == data["ids"]["fit"]
          and selection["validation_ids"] == configuration["validation_ids"] == data["ids"]["validation"])
    candidates = _csv(output / "model_comparison.csv")
    if model_name == "regression":
        eligible = [row for row in candidates if row["family"] != "training_mean"]
        best = min(eligible, key=lambda row: (-float(row["precision_at_20"]), float(row["mse"]), int(row["order"])))
        check("linear_selection_is_best_validation_precision_then_mse", json.loads(best["configuration"]) == selection["selected_configuration"]
              and len(eligible) == selection["completed_configurations"] <= selection["policy"]["max_configurations"]
              and all(int(row["n"]) == 37 for row in candidates))
        transform = checkpoint.get("fit_transform")
        if selection["selected_configuration"]["family"] == "ridge":
            x, y = (data["arrays"][r]["train"].double().numpy() for r in ("problems", "solutions"))
            scale = np.maximum(x.std(0), 1e-12) if selection["selected_configuration"].get("standardize") else np.ones(x.shape[1])
            weight = model.weight.detach().double().numpy().T
            bias = model.bias.detach().double().numpy()
            design, coefficient = (x - x.mean(0)) / scale, weight * scale[:, None]
            alpha = float(selection["selected_configuration"]["alpha"])
            gradient = design.T @ (design @ coefficient - (y - y.mean(0))) + alpha * coefficient
            residual = float(np.linalg.norm(gradient) / max(1, np.linalg.norm(design.T @ (y - y.mean(0)))))
            check("ridge_fit_transform_uses_train185_only", transform["fitted_on"] == "provided_training_rows_only"
                  and np.allclose(transform["x_mean"], x.mean(0), rtol=2e-6, atol=1e-7)
                  and np.allclose(transform["x_scale"], scale, rtol=2e-6, atol=1e-7)
                  and np.allclose(bias, y.mean(0) - x.mean(0) @ weight, rtol=2e-5, atol=2e-6))
            check("ridge_weights_satisfy_training_normal_equation_without_refitting", residual < 1e-5)
    else:
        _validate_deep_search(output, data, configuration, selection, module, check, close)
    rows = _csv(output / "summary.csv")
    check("all9_phase_method_summary_rows_present", {(r["split"], r["method"]) for r in rows} ==
          {(p, method) for p in ("validation", "train", "test") for method in ("training_mean", "raw", "clipped_nonnegative")} and len(rows) == 9)
    means = {"validation": data["arrays"]["solutions"]["fit"].numpy().mean(0),
             "train": data["arrays"]["solutions"]["train"].numpy().mean(0),
             "test": data["arrays"]["solutions"]["train"].numpy().mean(0)}
    phase_raw = {"validation": validation_prediction, "train": stored[:185], "test": stored[185:]}
    for row in rows:
        phase, method = row["split"], row["method"]
        actual = data["arrays"]["solutions"][phase].numpy()
        values = np.broadcast_to(means[phase], actual.shape) if method == "training_mean" else phase_raw[phase]
        values = np.maximum(values, 0) if method == "clipped_nonnegative" else values
        expected = independent_scores(values, actual)
        check(phase + "_" + method + "_independent_metrics", all(close(value, row[key]) for key, value in expected.items()))
    questions = _csv(output / "question_comparison.csv")
    check("test80_question_comparison_rows_exact", [row["id"] for row in questions] == data["ids"]["test"])
    for j, row in enumerate(questions):
        actual = data["arrays"]["solutions"]["test"][j].numpy()
        expected = independent_scores(np.maximum(stored[185 + j], 0), actual)
        check(row["id"] + "_independent_test_metrics", all(close(value, row["clipped_nonnegative_" + key])
              for key, value in expected.items()))
        actual_top, predicted_top = json.loads(row["actual_top20"]), json.loads(row["predicted_top20"])
        for label, top_rows, values in (("actual", actual_top, actual), ("predicted", predicted_top, np.maximum(stored[185 + j], 0))):
            indices = sorted(np.flatnonzero(values > 0), key=lambda i: (-values[i], i))[:20]
            check(row["id"] + "_" + label + "_unrounded_top20", [r["index"] for r in top_rows] == indices
                  and [r["token"] for r in top_rows] == [payload["vocabulary"][i] for i in indices]
                  and all(close(r["frequency"], values[i]) for r, i in zip(top_rows, indices)))
    after = {str(p.relative_to(output)): file_hash(p) for p in output.rglob("*")
             if p.is_file() and p.name != "validation.json"}
    check("model_verification_does_not_modify_weights_predictions_or_reports", before == after)
    result = {"verified_at": datetime.now(timezone.utc).isoformat(), "model": model_name, "dataset_id": data["dataset_id"],
              "passed": sum(row["passed"] for row in checks), "failed": sum(not row["passed"] for row in checks),
              "checks": checks, "complete": all(row["passed"] for row in checks),
              "training_performed": False, "api_calls": 0, "prediction_rows": len(documents),
              "test_rows": len(questions), "selection_primary": "validation_precision_at_20"}
    if save:
        write_json(output / "validation.json", result)
    return result
