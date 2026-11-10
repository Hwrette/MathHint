"""nn.Sequential MLP와 내부 검증에만 의존하는 작은 학습 함수."""

from copy import deepcopy

import torch
from torch import nn

from ..solution_data.model_tools import metrics, rank_key


def build_model(input_dim, output_dim, configuration, *, seed=42):
    torch.manual_seed(seed)
    layers, previous = [], input_dim
    for width in configuration["hidden_dims"]:
        layers.extend((nn.Linear(previous, width), nn.ReLU()))
        if configuration["dropout"]:
            layers.append(nn.Dropout(configuration["dropout"]))
        previous = width
    layers.append(nn.Linear(previous, output_dim))
    return nn.Sequential(*layers)


def restore(checkpoint):
    configuration = checkpoint.get("training_configuration", checkpoint.get("configuration"))
    if configuration is None:
        configuration = checkpoint["selection"]["selected_configuration"]
    model = build_model(checkpoint["input_dim"], checkpoint["output_dim"], configuration,
                        seed=configuration.get("seed", 42))
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    return model


def _optimizer(model, configuration):
    return torch.optim.AdamW(model.parameters(), lr=configuration["learning_rate"],
                             weight_decay=configuration["weight_decay"])


def _criterion(configuration):
    return nn.MSELoss() if configuration["loss"] == "mse" else nn.SmoothL1Loss(beta=1.)


def fit_candidate(x, y, validation_x, validation_y, vocabulary, configuration, *, seed):
    """여기에는 fit148와 validation37만 전달한다. test80은 받지 않는다."""
    model = build_model(x.shape[1], y.shape[1], configuration, seed=seed)
    optimizer, criterion = _optimizer(model, configuration), _criterion(configuration)
    history = []
    best_state, best_report, best_epoch = None, None, 0
    best_primary, last_primary_improvement = float("-inf"), 0

    def observe(epoch):
        nonlocal best_state, best_report, best_epoch, best_primary, last_primary_improvement
        model.eval()
        with torch.no_grad():
            train_prediction = model(x)
            prediction = model(validation_x)
            report = metrics(prediction.clamp_min(0), validation_y, vocabulary)
            train_mse = nn.functional.mse_loss(train_prediction, y).item()
            raw_validation_mse = nn.functional.mse_loss(prediction, validation_y).item()
            point = {"epoch": epoch, "train_mse": train_mse,
                     "train_objective": criterion(train_prediction, y).item(),
                     "validation_mse": raw_validation_mse,
                     "validation_clipped_mse": report["mse"],
                     "validation_precision_at_20": report["precision_at_20"]}
        history.append(point)
        if best_report is None or rank_key(report) < rank_key(best_report):
            best_state, best_report, best_epoch = deepcopy(model.state_dict()), report, epoch
        if report["precision_at_20"] > best_primary + 1e-12:
            best_primary, last_primary_improvement = report["precision_at_20"], epoch

    observe(0)
    stop_reason = "max_epochs_reached"
    for epoch in range(1, configuration["max_epochs"] + 1):
        model.train()
        optimizer.zero_grad()
        loss = criterion(model(x), y)
        if not torch.isfinite(loss):
            raise ValueError("MLP 학습 손실이 유한하지 않습니다. 후보를 임의로 재시도하지 않습니다.")
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.)
        optimizer.step()
        if epoch % 10 == 0 or epoch == configuration["max_epochs"]:
            observe(epoch)
            if epoch - last_primary_improvement >= 100:
                stop_reason = "validation_precision_plateau_100_epochs"
                break
    model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        train_metrics = metrics(model(x).clamp_min(0), y, vocabulary)
    return model, {"best_epoch": best_epoch, "stopped_epoch": epoch,
                   "stop_reason": stop_reason, "metrics": best_report,
                   "fit_metrics": train_metrics, "history": history}


def refit_full_training(x, y, configuration):
    """확정한 epoch/seed로185개 전체를 재학습하며 테스트로 중단하지 않는다."""
    model = build_model(x.shape[1], y.shape[1], configuration, seed=configuration["seed"])
    optimizer, criterion = _optimizer(model, configuration), _criterion(configuration)
    history = []
    for epoch in range(configuration["epochs"] + 1):
        if epoch:
            model.train()
            optimizer.zero_grad()
            loss = criterion(model(x), y)
            if not torch.isfinite(loss):
                raise ValueError("최종 MLP 재학습의 손실이 유한하지 않습니다.")
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.)
            optimizer.step()
        if epoch % 10 == 0 or epoch == configuration["epochs"]:
            model.eval()
            with torch.no_grad():
                prediction = model(x)
                history.append({"candidate_id": "final_refit185", "phase": "final_refit185",
                    "epoch": epoch, "train_mse": nn.functional.mse_loss(prediction, y).item(),
                    "train_objective": criterion(prediction, y).item()})
    model.eval()
    return model, history
