"""유한한 MLP 개선과 시드 검증을 끝내고 테스트 전에 모델을 확정한다."""

import csv
import json
from pathlib import Path
import shutil
import statistics

import torch

from ...TorchData import file_hash, identity_digest, read_json
from ..solution_data.common import ROOT, write_json
from ..solution_data.prepare import load_data
from ..solution_data.model_tools import (export_final, metrics, rank_key, save_checkpoint,
    utc_now, verify_manifest, write_csv, write_model_reports)
from .model import fit_candidate, refit_full_training, restore


POLICY = {
    "primary": "maximum internal validation Precision@20 of clipped predictions",
    "ties": ["minimum validation clipped MSE", "predeclared candidate order"],
    "inputs": "unchanged raw problem counts; no L2/TF-IDF/per-feature normalization",
    "fit_count": 148, "validation_count": 37,
    "coarse_candidates": 6, "refinement_candidates": 2,
    "refinement": "one best-coarse neighborhood: stronger regularization and half learning rate",
    "stability": "top2 configurations; seeds42,43,44; select by mean validation P@20 then mean clipped MSE",
    "final_seed": 42, "final_epochs": "median best validation epoch of selected configuration's three seeds",
    "max_epochs": 1000, "validation_interval": 10, "primary_patience_epochs": 100,
    "optimizer": "AdamW; full batch; gradient norm clipping 5",
    "test_targets_used_for_model_selection": False,
    "stop": "six initial and two refinement configurations plus top2 seed stability, then freeze",
}


def _candidates():
    settings = [([32], 0., 0., .003, "mse"),
                ([32], .1, .001, .003, "mse"),
                ([64], .1, .001, .003, "mse"),
                ([64], .2, .01, .001, "mse"),
                ([32, 16], .1, .001, .003, "mse"),
                ([32], .1, .001, .003, "smooth_l1")]
    return [{"candidate_id": f"M{i}", "family": "sequential_mlp", "hidden_dims": hidden,
             "dropout": dropout, "weight_decay": decay, "learning_rate": rate,
             "loss": loss, "max_epochs": 1000, "stage": "initial"}
            for i, (hidden, dropout, decay, rate, loss) in enumerate(settings)]


def _trial_paths(output, configuration, seed):
    name = configuration["candidate_id"] + f"_seed{seed}"
    return output / "checkpoints/search" / f"{name}.pt", output / "search_trials" / f"{name}.json"


def _attempt(output, data, configuration, seed, signature):
    checkpoint, path = _trial_paths(output, configuration, seed)
    trial_id = identity_digest({"search_signature": signature, "configuration": configuration, "seed": seed})
    if path.exists():
        saved = read_json(path)
        if saved["trial_id"] != trial_id or file_hash(checkpoint) != saved["checkpoint_sha256"]:
            raise ValueError(f"기존 MLP 후보의 데이터·설정·체크포인트가 다릅니다: {path}")
        print(f"MLP 후보 재사용: {configuration['candidate_id']} seed{seed}", flush=True)
        return saved
    x, y = data["arrays"]["problems"], data["arrays"]["solutions"]
    model, report = fit_candidate(x["fit"], y["fit"], x["validation"], y["validation"],
                                  data["vocabularies"]["solutions"], configuration, seed=seed)
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"input_dim": x["fit"].shape[1], "output_dim": y["fit"].shape[1],
                "dataset_id": data["dataset_id"], "configuration": {**configuration, "seed": seed},
                "model_state_dict": model.state_dict(), "best_epoch": report["best_epoch"],
                "fit_ids": data["ids"]["fit"], "validation_ids": data["ids"]["validation"],
                "test_targets_available": False}, checkpoint)
    saved = {"trial_id": trial_id, "candidate_id": configuration["candidate_id"], "seed": seed,
             "configuration": configuration, "checkpoint_sha256": file_hash(checkpoint), **report}
    write_json(path, saved)
    print(f"MLP {configuration['candidate_id']} seed{seed}: 검증 P@20={report['metrics']['precision_at_20']:.4f}, "
          f"MSE={report['metrics']['mse']:.4f}, 최적 epoch={report['best_epoch']}", flush=True)
    return saved


def _summary(trial, order):
    return {"candidate_id": trial["candidate_id"] + f"_seed{trial['seed']}", "seed": trial["seed"],
            "configuration_id": trial["candidate_id"], "order": order, "stage": trial["configuration"]["stage"],
            "configuration": json.dumps(trial["configuration"], ensure_ascii=False, sort_keys=True),
            "best_epoch": trial["best_epoch"], "stopped_epoch": trial["stopped_epoch"],
            "stop_reason": trial["stop_reason"], "fit_mse": trial["fit_metrics"]["mse"],
            "fit_precision_at_20": trial["fit_metrics"]["precision_at_20"], **trial["metrics"]}


def _note_improvement(state, trial):
    # 중단 재개에서 읽어온 같은 후보를 새 학습 개선으로 중복 기록하지 않는다.
    if any(row["candidate_id"] == trial["candidate_id"] and row["seed"] == trial["seed"]
           for row in state["improvements"]):
        return
    state["improvements"].append({"candidate_id": trial["candidate_id"], "seed": trial["seed"],
        "validation_precision_at_20": trial["metrics"]["precision_at_20"],
        "validation_mse": trial["metrics"]["mse"], "observed_at": utc_now()})


def _store_progress(output, state, baseline, trials, configurations):
    order = {conf["candidate_id"]: i for i, conf in enumerate(configurations)}
    rows = [{"candidate_id": "training_mean", "seed": "", "configuration_id": "training_mean", "order": -1,
             "stage": "baseline", "configuration": "fit148 mean; no model weights", **baseline}]
    rows.extend(_summary(trial, order[trial["candidate_id"]]) for trial in trials)
    write_csv(output / "model_comparison.csv", rows)
    history = [{"candidate_id": trial["candidate_id"] + f"_seed{trial['seed']}", "phase": "internal_fit", **point}
               for trial in trials for point in trial["history"]]
    write_csv(output / "training_history.csv", history)
    state["completed_trials"] = [row["candidate_id"] for row in rows if row["candidate_id"] != "training_mean"]
    state["configurations"] = configurations
    write_json(output / "search_state.json", state)
    return history


def train(root=ROOT):
    root = Path(root).resolve()
    output = root / "results/final_experiment_2/deep_learning"
    data = load_data(root, include_test=False)
    if "test" in data["arrays"]["solutions"]:
        raise ValueError("MLP 탐색에는 테스트 타깃을 전달하지 않습니다.")
    signature = identity_digest({"dataset_id": data["dataset_id"], "policy": POLICY,
        "fit_ids": data["ids"]["fit"], "validation_ids": data["ids"]["validation"],
        "model_source_sha256": file_hash(Path(__file__).with_name("model.py")), "initial_candidates": _candidates()})
    config_path = output / "config.json"
    if config_path.exists() and read_json(config_path)["signature"] != signature:
        raise ValueError("다른 입력·검색 정책의 MLP 결과를 덮어쓰지 않습니다.")
    if (output / "model_manifest.json").exists():
        result = verify_manifest(output, data["dataset_id"])
        print("비선형 MLP 확정 결과 재사용: 체크포인트·예측 해시 일치, 재학습 없음", flush=True)
        return result
    output.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(2)
    write_json(config_path, {"signature": signature, "dataset_id": data["dataset_id"], "policy": POLICY,
        "initial_candidates": _candidates(), "fit_ids": data["ids"]["fit"],
        "validation_ids": data["ids"]["validation"], "input_dim": len(data["vocabularies"]["problems"]),
        "output_dim": len(data["vocabularies"]["solutions"]),
        "runtime": {"torch": str(torch.__version__), "device": "cpu", "threads": 2},
        "test_targets_available_during_search": False})
    state_path = output / "search_state.json"
    state = read_json(state_path) if state_path.exists() else {"signature": signature, "improvements": []}
    if state["signature"] != signature:
        raise ValueError("중단된 MLP 탐색과 현재 데이터·정책이 다릅니다.")
    x, y, vocab = data["arrays"]["problems"], data["arrays"]["solutions"], data["vocabularies"]["solutions"]
    baseline = metrics(y["fit"].mean(0).expand_as(y["validation"]), y["validation"], vocab)
    configurations, trials = _candidates(), []
    for order, conf in enumerate(configurations):
        trial = _attempt(output, data, conf, 42, signature)
        prior = min(trials, key=lambda t: rank_key(t["metrics"])) if trials else None
        trials.append(trial)
        if prior is None or rank_key(trial["metrics"]) < rank_key(prior["metrics"]):
            _note_improvement(state, trial)
        _store_progress(output, state, baseline, trials, configurations)
    coarse_best = min(trials, key=lambda t: rank_key(t["metrics"], configurations.index(t["configuration"])))
    base = coarse_best["configuration"]
    refinements = [
        {**base, "candidate_id": "M6", "stage": "refinement", "dropout": min(.35, max(.1, base["dropout"] + .1)),
         "weight_decay": max(.001, base["weight_decay"] * 3)},
        {**base, "candidate_id": "M7", "stage": "refinement", "learning_rate": base["learning_rate"] / 2},
    ]
    state["refinement_reason"] = {"coarse_best": base["candidate_id"],
        "fit_mse": coarse_best["fit_metrics"]["mse"], "validation_mse": coarse_best["metrics"]["mse"],
        "missing_actual_top20_mean": float(y["validation"].gt(0).sum(1).clamp_max(20).double().mean())
                                       - coarse_best["metrics"]["mean_common_top20_count"],
        "unmatched_top20_slots_mean": 20 - coarse_best["metrics"]["mean_common_top20_count"],
        "decision": "test stronger regularization against fit/validation gap and a smaller learning rate; no test80 inspected"}
    configurations += refinements
    for conf in refinements:
        trial = _attempt(output, data, conf, 42, signature)
        prior = min(trials, key=lambda t: rank_key(t["metrics"]))
        trials.append(trial)
        if rank_key(trial["metrics"]) < rank_key(prior["metrics"]):
            _note_improvement(state, trial)
        _store_progress(output, state, baseline, trials, configurations)
    order = {conf["candidate_id"]: i for i, conf in enumerate(configurations)}
    top = sorted(trials, key=lambda t: rank_key(t["metrics"], order[t["candidate_id"]]))[:2]
    aggregates = []
    for representative in top:
        conf = representative["configuration"]
        group = [representative]
        for seed in (43, 44):
            trial = _attempt(output, data, conf, seed, signature)
            trials.append(trial); group.append(trial)
            _store_progress(output, state, baseline, trials, configurations)
        aggregates.append({"candidate_id": conf["candidate_id"], "configuration": conf,
            "precision_at_20": statistics.mean(t["metrics"]["precision_at_20"] for t in group),
            "mse": statistics.mean(t["metrics"]["mse"] for t in group),
            "precision_std_ddof0": statistics.pstdev(t["metrics"]["precision_at_20"] for t in group),
            "best_epochs": [t["best_epoch"] for t in group],
            "seed_metrics": [{"seed": t["seed"], **t["metrics"], "best_epoch": t["best_epoch"]} for t in group]})
    write_csv(output / "configuration_stability.csv", [{"candidate_id": a["candidate_id"],
        "mean_precision_at_20": a["precision_at_20"], "mean_mse": a["mse"],
        "precision_std_ddof0": a["precision_std_ddof0"], "seeds": "42,43,44",
        "best_epochs": json.dumps(a["best_epochs"])} for a in aggregates])
    selected = min(aggregates, key=lambda a: rank_key(a, order[a["candidate_id"]]))
    conf = {**selected["configuration"], "seed": 42,
            "epochs": max(1, int(statistics.median(selected["best_epochs"]))) }
    representative = next(t for t in trials if t["candidate_id"] == conf["candidate_id"] and t["seed"] == 42)
    selection = {"dataset_id": data["dataset_id"], "policy": POLICY, "selected_configuration": conf,
        "selected_validation_metrics": representative["metrics"],
        "validation_reporting": "seed42 best validation checkpoint; configuration selected by 3seed mean",
        "configuration_stability_metrics": selected, "all_configuration_stability": aggregates,
        "validation_baseline_metrics": baseline, "frozen_at": utc_now(),
        "test_targets_used_for_selection": False, "completed_configurations": 8,
        "completed_seed_trials": len(trials), "final_refit_epochs": conf["epochs"],
        "fit_ids": data["ids"]["fit"], "validation_ids": data["ids"]["validation"],
        "improvements": state["improvements"],
        "stop_reason": "predeclared six initial plus two refinements and top2 three-seed checks completed"}
    frozen_path = output / "selection.json"
    if frozen_path.exists():
        old = read_json(frozen_path)
        if old["selected_configuration"] != conf or old["dataset_id"] != data["dataset_id"]:
            raise ValueError("확정된 MLP 선택이 현재 탐색 결과와 다릅니다.")
        selection = old
    else:
        write_json(frozen_path, selection)
    validation_path, _ = _trial_paths(output, representative["configuration"], 42)
    shutil.copyfile(validation_path, output / "checkpoints/best_validation.pt")
    validation_model = restore(torch.load(validation_path, map_location="cpu", weights_only=True))
    with torch.no_grad():
        validation_prediction = validation_model(x["validation"])
    history = _store_progress(output, state, baseline, trials, configurations)
    final_path = output / "checkpoints/final.pt"
    if final_path.exists():
        saved = torch.load(final_path, map_location="cpu", weights_only=True)
        if saved["dataset_id"] != data["dataset_id"] or saved["selection"]["selected_configuration"] != conf:
            raise ValueError("기존 최종 MLP 체크포인트의 데이터·설정이 다릅니다.")
        final_model = restore(saved)
        final_history_path = output / "final_training_history.json"
        final_curve = read_json(final_history_path)
    else:
        final_model, final_curve = refit_full_training(x["train"], y["train"], conf)
        write_json(output / "final_training_history.json", final_curve)
        save_checkpoint(output, data, final_model, "nonlinear_nn_sequential_mlp", selection,
                        extra={"training_configuration": conf, "input_transform": "none; raw counts",
                               "nonlinear_activation": "ReLU", "gradient_clip_norm": 5.})
    history.extend(final_curve)
    # 설정과185개 재학습 체크포인트를 모두 저장한 뒤에만 test80 타깃을 읽는다.
    full_data = load_data(root, include_test=True)
    manifest = export_final(root, output, full_data, final_model, selection, history, validation_prediction,
                            validation_history=representative["history"])
    _explain(output, selection)
    print(f"MLP 확정: {conf['candidate_id']} seed42 epoch{conf['epochs']}; "
          f"테스트 P@20={manifest['test_metrics']['precision_at_20']:.4f}", flush=True)
    return manifest


def _explain(output, selection):
    chosen = selection["selected_configuration"]
    intro = ["## 구성 선택을 먼저 확인", "",
        f"선택 구성 **{chosen['candidate_id']}**: 은닉층 {chosen['hidden_dims']}, Dropout {chosen['dropout']}, "
        f"AdamW 학습률 {chosen['learning_rate']}, Weight Decay {chosen['weight_decay']}, "
        f"손실 `{chosen['loss']}`, 최종 seed42·{selection['final_refit_epochs']}epoch다.", "",
        "초기/개선 후보의 대표seed42 점수로 상위2구성을 고른 뒤, 아래3시드 평균으로 최종 구성을 선택했다. "
        "최종 테스트나 Gemini 정답률로 설정을 바꾸지 않았다.", "",
        "|상위 구성|검증 P@20 평균|시드 표준편차|검증 보정 MSE 평균|최적 epoch(42/43/44)|",
        "|---|---:|---:|---:|---|"]
    for item in selection["all_configuration_stability"]:
        intro.append(f"|{item['candidate_id']}|{item['precision_at_20']:.4f}|{item['precision_std_ddof0']:.4f}|"
                     f"{item['mse']:.4f}|{item['best_epochs']}|")
    intro += ["", "기본 검증표의 점수는 선택 구성의 seed42 최적 체크포인트다. "
              "구성 선택에 쓴3시드 평균과 같은 값으로 해석하지 않는다.", "",
              "공통 학습·검증 곡선의 MSE는 원래 빈도 척도의 예측 오차다. "
              "최종 모델이 실제로 최적화한 SmoothL1 손실은 학습 기록의 train_objective 열에 별도로 보존했다.", ""]
    paragraph = ["", "## 비선형 모델의 선택과 재학습", "",
        "입력270개는 기존 원시 빈도를 그대로 사용했다. 입력 L2·TF-IDF·어휘 재선정은 없다. "
        "Linear→ReLU(필요시Dropout)→Linear의 실제 nn.Sequential 비선형 구조이며, "
        "출력은 원본 해설의 빈도 척도다. 음수는 평가를 구분하고 Gemini 전송에서0으로 보정한다.", "",
        f"초기6구성+규제/학습률 개선2구성을 내부148/37에서만 비교했다. 상위2구성은 시드42~44에서 확인했고 "
        f"구성선택의 평균 P@20은 **{selection['configuration_stability_metrics']['precision_at_20']:.4f}**, "
        f"시드 표준편차는 {selection['configuration_stability_metrics']['precision_std_ddof0']:.4f}다. "
        "위 기본 검증표는 선택 구성의 seed42 최적 검증 체크포인트이며 3시드 평균과 구분한다.", "",
        f"최종185개 재학습은 고정seed42로 {selection['final_refit_epochs']}epoch 수행했다. "
        "epoch는 선택 구성의3시드 검증 최적epoch 중앙값으로 정했고 최종 테스트로 조기종료하지 않았다. "
        "검증상승이 정체되거나 유한 후보 범위를 끝내면 중단하며 테스트/Gemini 결과로 다시 최적화하지 않는다.", "",
        "[구성별3시드 검증](configuration_stability.csv) · [모든 후보와 중단 기록](search_state.json)", ""]
    path = output / "README.md"
    text = path.read_text(encoding="utf-8").replace("## 검증과 최종 테스트", "\n".join(intro) + "\n## 검증과 최종 테스트", 1)
    with (output / "model_comparison.csv").open(encoding="utf-8-sig", newline="") as stream:
        for item in csv.DictReader(stream):
            try:
                setting = json.loads(item["configuration"])
            except (json.JSONDecodeError, TypeError):
                continue
            brief = (f"은닉{setting['hidden_dims']}, Dropout={setting['dropout']}, "
                     f"lr={setting['learning_rate']}, WD={setting['weight_decay']}, {setting['loss']}")
            text = text.replace("`" + item["configuration"] + "`", "`" + brief + "`")
    comparison = []
    linear_path = output.parent / "regression/model_manifest.json"
    if linear_path.exists():
        linear = read_json(linear_path)
        deep = read_json(output / "model_manifest.json")
        comparison = ["", "## 확정한 선형회귀와의 테스트80 비교", "",
            "|모델|MSE ↓|MAE ↓|코사인 ↑|Precision@20 ↑|", "|---|---:|---:|---:|---:|"]
        for name, manifest in (("선형회귀", linear), ("비선형 MLP", deep)):
            value = manifest["test_metrics"]
            comparison.append(f"|{name}|{value['mse']:.4f}|{value['mae']:.4f}|{value['cosine_similarity']:.4f}|{value['precision_at_20']:.4f}|")
        delta = deep["test_metrics"]["precision_at_20"] - linear["test_metrics"]["precision_at_20"]
        comparison += ["", f"P@20 차이는 MLP−선형회귀 **{delta:+.6f}**다. MSE·MAE·코사인도 함께 비교하며 "
                       "한 지표의 작은 차이를 비선형 모델의 전반적 우월성이나 Gemini 풀이 효과로 해석하지 않는다.", ""]
    path.write_text(text + "\n".join(paragraph + comparison), encoding="utf-8")
    path = output / "analysis.md"
    path.write_text(path.read_text(encoding="utf-8") + "\n".join(intro + paragraph + comparison), encoding="utf-8")


def evaluate(root=ROOT):
    root = Path(root).resolve()
    output = root / "results/final_experiment_2/deep_learning"
    data = load_data(root, include_test=True)
    manifest = verify_manifest(output, data["dataset_id"])
    model = restore(torch.load(output / manifest["checkpoint"]["path"], map_location="cpu", weights_only=True))
    stored = read_json(output / manifest["predictions"]["path"])
    for part in ("train", "test"):
        documents = [row for row in stored["documents"] if row["split"] == part]
        with torch.no_grad():
            predicted = model(data["arrays"]["problems"][part])
        if not torch.equal(predicted, torch.tensor([row["raw_predicted_vector"] for row in documents])):
            raise ValueError("체크포인트와 저장된 MLP 예측이 다릅니다.")
    write_model_reports(root, output, data)
    _explain(output, read_json(output / "selection.json"))
    return manifest
