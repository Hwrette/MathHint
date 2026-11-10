"""내부 검증으로 제한된 선형 후보를 개선하고 최종185학습 모델을 동결한다."""

import csv
import json
from pathlib import Path

import torch

from ...TorchData import file_hash, identity_digest, read_json
from ..solution_data.common import ROOT, write_json
from ..solution_data.prepare import load_data
from ..solution_data.model_tools import (metrics, rank_key, write_csv, utc_now,
    save_checkpoint, export_final, verify_manifest, write_model_reports)
from .model import fit_model, restore


POLICY = {"primary": "validation precision_at_20 maximum on clipped predictions",
          "ties": ["validation clipped MSE minimum", "predeclared candidate order"],
          "validation_count": 37, "fit_count": 148, "max_configurations": 12,
          "test_used_for_model_selection": False,
          "refinement": "one validation-best neighborhood of two hyperparameters; then stop",
          "baseline": "fit148 mean for validation; train185 mean for final test",
          "inputs": "raw counts; optional fit-only standardization is algebraically converted to raw affine weights"}


def _candidates():
    values = [{"candidate_id": "adam_original", "family": "adam_linear", "epochs": 500,
               "learning_rate": .01, "seed": 42, "stage": "initial"}]
    values += [{"candidate_id": f"ridge_raw_{alpha:g}", "family": "ridge", "alpha": alpha,
                "standardize": False, "stage": "coarse"} for alpha in (0., .1, 1., 10., 100., 1000.)]
    values += [{"candidate_id": f"ridge_scaled_{alpha:g}", "family": "ridge", "alpha": alpha,
                "standardize": True, "stage": "coarse"} for alpha in (1., 10., 100.)]
    return values


def _history(path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _best(rows):
    return min((row for row in rows if row["family"] != "training_mean"),
               key=lambda row: rank_key(row, row["order"]))


def _save_best(path, model, data, configuration):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    torch.save({"input_dim": len(data["vocabularies"]["problems"]),
                "output_dim": len(data["vocabularies"]["solutions"]),
                "model_state_dict": model.state_dict(), "dataset_id": data["dataset_id"],
                "configuration": configuration,
                "fit_transform": getattr(model, "fit_transform", None)}, temporary)
    temporary.replace(path)


def train(root=ROOT):
    root = Path(root).resolve()
    output = root / "results/final_experiment_2/regression"
    data = load_data(root, include_test=False)
    if "test" in data["arrays"]["solutions"]:
        raise ValueError("모델 탐색 중 테스트 타깃을 읽지 않습니다.")
    signature = identity_digest({"dataset_id": data["dataset_id"], "policy": POLICY,
        "fit_ids": data["ids"]["fit"], "validation_ids": data["ids"]["validation"],
        "model_source_sha256": file_hash(Path(__file__).with_name("model.py")),
        "coarse_candidates": _candidates()})
    config_path = output / "config.json"
    if config_path.exists() and read_json(config_path)["signature"] != signature:
        raise ValueError("다른 데이터/탐색 정책의 선형 결과를 덮어쓰지 않습니다.")
    if (output / "model_manifest.json").exists():
        manifest = verify_manifest(output, data["dataset_id"])
        print("선형회귀 확정 결과 재사용: 체크포인트·예측 해시 일치, 재학습 없음", flush=True)
        return manifest
    output.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(2)
    write_json(config_path, {"signature": signature, "dataset_id": data["dataset_id"], "policy": POLICY,
        "fit_ids": data["ids"]["fit"], "validation_ids": data["ids"]["validation"],
        "input_dim": len(data["vocabularies"]["problems"]), "output_dim": len(data["vocabularies"]["solutions"]),
        "runtime": {"torch": str(torch.__version__), "device": "cpu", "threads": 2},
        "test_targets_available_during_search": False})
    x, y = data["arrays"]["problems"], data["arrays"]["solutions"]
    vocabulary = data["vocabularies"]["solutions"]
    state_path = output / "search_state.json"
    curve_path = output / "training_history.csv"
    state = read_json(state_path) if state_path.exists() else {"signature": signature, "candidates": [], "improvements": []}
    if state["signature"] != signature:
        raise ValueError("중단된 탐색의 입력이 현재와 다릅니다.")
    rows, history = state["candidates"], _history(curve_path)
    baseline_prediction = y["fit"].mean(0).expand_as(y["validation"])
    baseline = metrics(baseline_prediction, y["validation"], vocabulary)
    if not rows:
        rows.append({"candidate_id": "training_mean", "family": "training_mean", "order": -1,
                     "configuration": "fit148 mean", "stage": "baseline", **baseline})

    def attempt(configuration):
        if any(row["candidate_id"] == configuration["candidate_id"] for row in rows):
            return
        previous = _best(rows) if len(rows) > 1 else None
        model, curve = fit_model(x["fit"], y["fit"], configuration)
        with torch.no_grad():
            prediction = model(x["validation"])
            report = metrics(prediction.clamp_min(0), y["validation"], vocabulary)
            train_metrics = metrics(model(x["fit"]).clamp_min(0), y["fit"], vocabulary)
        order = len(rows) - 1
        row = {"candidate_id": configuration["candidate_id"], "family": configuration["family"],
               "order": order, "stage": configuration["stage"],
               "configuration": json.dumps(configuration, ensure_ascii=False, sort_keys=True),
               "fit_mse": train_metrics["mse"], "fit_precision_at_20": train_metrics["precision_at_20"], **report}
        rows.append(row)
        history.extend({"candidate_id": configuration["candidate_id"], "phase": "internal_fit",
                        "epoch": point["epoch"], "train_mse": point["train_mse"],
                        "validation_clipped_mse": report["mse"] if i == len(curve) - 1 else None,
                        "validation_precision_at_20": report["precision_at_20"] if i == len(curve) - 1 else None}
                       for i, point in enumerate(curve))
        if previous is None or rank_key(row, order) < rank_key(previous, previous["order"]):
            _save_best(output / "checkpoints/best_validation.pt", model, data, configuration)
            state["improvements"].append({"candidate_id": row["candidate_id"], "precision_at_20": row["precision_at_20"],
                                           "mse": row["mse"], "observed_at": utc_now()})
        state["candidates"] = rows
        write_json(state_path, state)
        write_csv(curve_path, history)
        write_csv(output / "model_comparison.csv", rows)
        print(f"선형 후보 {row['candidate_id']}: 검증 P@20={row['precision_at_20']:.4f}, MSE={row['mse']:.4f}", flush=True)

    for configuration in _candidates():
        attempt(configuration)
    coarse_best = _best([row for row in rows if row["stage"] != "refinement"])
    chosen_coarse = json.loads(coarse_best["configuration"])
    if chosen_coarse["family"] == "ridge":
        alpha = chosen_coarse["alpha"]
        neighbors = (alpha / 3.1622776601683795, alpha * 3.1622776601683795) if alpha else (.01, .03)
        refinements = [{**chosen_coarse, "candidate_id": f"refined_{i}", "alpha": value, "stage": "refinement"}
                       for i, value in enumerate(neighbors)]
    else:
        refinements = [{**chosen_coarse, "candidate_id": f"refined_{i}", "learning_rate": value, "stage": "refinement"}
                       for i, value in enumerate((.003, .03))]
    for configuration in refinements:
        attempt(configuration)
    best = _best(rows)
    configuration = json.loads(best["configuration"])
    frozen_path = output / "selection.json"
    if frozen_path.exists():
        selection = read_json(frozen_path)
        if selection["selected_configuration"] != configuration or selection["dataset_id"] != data["dataset_id"]:
            raise ValueError("확정된 선형 선택과 재개한 탐색 결과가 다릅니다.")
    else:
        selection = {"dataset_id": data["dataset_id"], "policy": POLICY,
            "selected_configuration": configuration, "selected_validation_metrics": {key: best[key] for key in baseline},
            "validation_baseline_metrics": baseline, "frozen_at": utc_now(),
            "test_targets_used_for_selection": False, "completed_configurations": len(rows) - 1,
            "improvements": state["improvements"], "stop_reason": "bounded coarse search and one two-candidate refinement completed",
            "fit_ids": data["ids"]["fit"], "validation_ids": data["ids"]["validation"],
            "stability": "Ridge closed-form is deterministic; repeated random initialization would not change its solution" if configuration["family"] == "ridge"
                         else "final model uses the predeclared seed42; validation chosen before seeing test targets"}
        write_json(frozen_path, selection)
    validation_saved = torch.load(output / "checkpoints/best_validation.pt", map_location="cpu", weights_only=True)
    validation_model = restore(validation_saved)
    with torch.no_grad():
        validation_prediction = validation_model(x["validation"])
    final_path = output / "checkpoints/final.pt"
    if final_path.exists():
        frozen = torch.load(final_path, map_location="cpu", weights_only=True)
        if frozen["dataset_id"] != data["dataset_id"] or frozen["selection"]["selected_configuration"] != configuration:
            raise ValueError("기존 최종 선형 모델의 데이터/설정이 다릅니다.")
        final_model = restore(frozen)
    else:
        final_model, final_curve = fit_model(x["train"], y["train"], configuration)
        history.extend({"candidate_id": "final_refit185", "phase": "final_refit185",
                        "epoch": point["epoch"], "train_mse": point["train_mse"]} for point in final_curve)
        save_checkpoint(output, data, final_model, "linear_affine_raw_counts", selection,
                        extra={"fit_transform": getattr(final_model, "fit_transform", None),
                               "training_configuration": configuration})
    # 검증 선택과 전체185 최종 체크포인트 저장이 끝난 뒤 최초로 test80 타깃을 읽는다.
    full_data = load_data(root, include_test=True)
    validation_history = [{"epoch": 0, "validation_clipped_mse": best["mse"],
                           "validation_precision_at_20": best["precision_at_20"]}]
    result = export_final(root, output, full_data, final_model, selection, history,
                          validation_prediction, validation_history=validation_history)
    print(f"선형회귀 확정: {configuration}; 테스트80 P@20={result['test_metrics']['precision_at_20']:.4f}", flush=True)
    return result


def evaluate(root=ROOT):
    torch.set_num_threads(2)
    root = Path(root).resolve()
    data = load_data(root, include_test=True)
    output = root / "results/final_experiment_2/regression"
    manifest = verify_manifest(output, data["dataset_id"])
    checkpoint = torch.load(output / manifest["checkpoint"]["path"], map_location="cpu", weights_only=True)
    model = restore(checkpoint)
    stored = read_json(output / manifest["predictions"]["path"])
    with torch.no_grad():
        predictions = torch.cat([model(data["arrays"]["problems"][part]) for part in ("train", "test")])
    if not torch.equal(predictions, torch.tensor([row["raw_predicted_vector"] for row in stored["documents"]])):
        raise ValueError("체크포인트의 예측과 저장된 선형 예측이 다릅니다.")
    write_model_reports(root, output, data)
    return manifest
