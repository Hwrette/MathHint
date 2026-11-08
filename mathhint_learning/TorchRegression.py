"""문제 빈도 벡터 → 해설 빈도 벡터를 예측하는 선형회귀.

Experiment.py의 EXPERIMENT에서 별도 실험 경로를 선택하고 RunExperiment의
train 작업으로 실행한다. 학습·테스트를 다시 나누지 않는다.
"""

import os

import torch
from torch import nn

if __package__:
    from .TorchData import load_fixed_dataset, write_json
else:
    from TorchData import load_fixed_dataset, write_json


def train_regression(X, Y, epochs=500, learning_rate=.01, seed=42):
    """학습 자료 X와 Y만 받는다. 테스트 자료는 이 함수에 넣지 않는다."""
    torch.manual_seed(seed)
    model = nn.Linear(X.shape[1], Y.shape[1])
    loss_function = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)

    with torch.no_grad():
        history = [{"epoch": 0, "train_mse": loss_function(model(X), Y).item()}]
    model.train()
    for epoch in range(1, epochs + 1):
        prediction = model(X)
        loss = loss_function(prediction, Y)
        optimizer.zero_grad()  # 이전 기울기 지우기
        loss.backward()       # 오차를 줄일 방향 계산
        optimizer.step()      # 가중치 수정
        with torch.no_grad():
            history.append({"epoch": epoch, "train_mse": loss_function(model(X), Y).item()})
    model.eval()
    return model, history


def evaluate(prediction, answer):
    prediction, answer = prediction.float(), answer.float()
    error = prediction - answer
    return {
        "mse": error.square().mean().item(),
        "mae": error.abs().mean().item(),
        "mean_cosine_similarity": nn.functional.cosine_similarity(prediction, answer, dim=1).mean().item(),
    }


def train_for_experiment(experiment, *, make_figures=True):
    """선택한 별도 실험 경로에서만 학습하고 해당 모델로 예측·평가한다."""
    from .Experiment import LEGACY_NAME
    from .TorchData import file_hash
    from .VectorComparison import evaluate_for_experiment

    output = experiment.regression_dir
    protected = experiment.project_root / "results/final_experiment"
    archive = experiment.project_root / "results" / LEGACY_NAME
    if experiment.result_root == protected or experiment.result_root.is_relative_to(archive):
        raise ValueError(f"{experiment.result_root}: 보존된 실험에 학습 결과를 덮어쓰지 않습니다. 새 result_root를 지정하세요.")
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"{output}: 기존 회귀 결과가 있습니다. 새 실험 경로를 지정하세요.")
    if (not experiment.checkpoint.is_relative_to(output)
            or not experiment.predictions.is_relative_to(output)):
        raise ValueError(f"{output}: 새 학습의 checkpoint와 predictions는 선택한 회귀 출력 폴더 안에 있어야 합니다.")
    if type(experiment.epochs) is not int or experiment.epochs < 1 or experiment.learning_rate <= 0:
        raise ValueError("epochs는 양의 정수, learning_rate는 양수여야 합니다.")
    torch.set_num_threads(2)
    data = load_fixed_dataset(experiment.project_root, experiment.data_root)
    model, history = train_regression(data["arrays"]["problems"]["train"], data["arrays"]["solutions"]["train"],
                                      experiment.epochs, experiment.learning_rate, experiment.seed)
    output.mkdir(parents=True, exist_ok=True)
    experiment.checkpoint.parent.mkdir(parents=True, exist_ok=True)
    config = {"epochs": experiment.epochs, "learning_rate": experiment.learning_rate,
              "seed": experiment.seed, "architecture": f"nn.Linear({len(data['vocabularies']['problems'])},{len(data['vocabularies']['solutions'])})",
              "evaluation_rounding": "none"}
    history_path = output / "regression_learning_curve.json"
    write_json(history_path, history)
    torch.save({"model_type": "multioutput_linear_regression", "model_state_dict": model.state_dict(),
                "config": config, "input_dim": len(data["vocabularies"]["problems"]),
                "output_dim": len(data["vocabularies"]["solutions"]),
                "input_vocabulary": data["vocabularies"]["problems"], "output_vocabulary": data["vocabularies"]["solutions"],
                "train_ids": data["ids"]["train"], "test_ids": data["ids"]["test"],
                "generation_id": data["generation_id"], "data_identity": data["identity"],
                "learning_curve": {"path": os.path.relpath(history_path, experiment.checkpoint.parent),
                                   "sha256": file_hash(history_path)}}, experiment.checkpoint)
    result = evaluate_for_experiment(experiment, make_figures=make_figures)
    result["training_performed"] = True
    return result


def main(experiment=None):
    from .Experiment import EXPERIMENT
    result = train_for_experiment(experiment or EXPERIMENT)
    print(f"학습 결과: {result['regression_dir']}")


if __name__ == "__main__":
    main()
