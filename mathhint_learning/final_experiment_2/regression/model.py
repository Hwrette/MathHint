"""선형 모델 후보. Ridge도 최종적으로 원시 입력의 nn.Linear에 저장한다."""

import torch
from torch import nn

from ...TorchRegression import train_regression


def fit_model(x, y, configuration):
    """호출자가 정한 학습 행만 받는다. 검증·테스트 타깃은 받지 않는다."""
    if configuration["family"] == "adam_linear":
        return train_regression(x, y, epochs=configuration["epochs"],
                                learning_rate=configuration["learning_rate"],
                                seed=configuration["seed"])
    if configuration["family"] != "ridge":
        raise ValueError(f"지원하지 않는 선형 계열: {configuration['family']}")
    alpha = float(configuration["alpha"])
    if alpha < 0:
        raise ValueError("Ridge alpha는 음수가 될 수 없습니다.")
    # 이 평균·표준편차는 이 함수에 넘긴 fit 행에서만 추정한다.
    x64, y64 = x.double(), y.double()
    x_mean, y_mean = x64.mean(0), y64.mean(0)
    scale = x64.std(0, unbiased=False).clamp_min(1e-12) if configuration.get("standardize") else torch.ones_like(x_mean)
    centered = (x64 - x_mean) / scale
    target = y64 - y_mean
    if alpha == 0:
        coefficient = torch.linalg.lstsq(centered, target, driver="gelsd").solution
    else:
        # n<d인 작은 자료에서 동일 Ridge 해의 dual 식을 사용한다.
        kernel = centered @ centered.T
        coefficient = centered.T @ torch.linalg.solve(
            kernel + alpha * torch.eye(len(centered), dtype=torch.float64), target)
    raw_weight = coefficient / scale[:, None]
    raw_bias = y_mean - x_mean @ raw_weight
    model = nn.Linear(x.shape[1], y.shape[1])
    with torch.no_grad():
        model.weight.copy_(raw_weight.T.float())
        model.bias.copy_(raw_bias.float())
        mse = nn.functional.mse_loss(model(x), y).item()
    model.eval()
    # 해석: 원시 입력에서 평가하는 선형층이며, 별도 추론 정규화는 없다.
    model.fit_transform = {"fitted_on": "provided_training_rows_only",
                           "standardization_used_in_solver": bool(configuration.get("standardize")),
                           "x_mean": x_mean.float().tolist(), "x_scale": scale.float().tolist(),
                           "weight_converted_back_to_raw_input": True,
                           "objective": "sum_squared_error + alpha * squared_coefficient_norm; intercept unpenalized"}
    return model, [{"epoch": 0, "train_mse": mse, "solver": "closed_form_ridge"}]


def restore(checkpoint):
    model = nn.Linear(checkpoint["input_dim"], checkpoint["output_dim"])
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    return model
