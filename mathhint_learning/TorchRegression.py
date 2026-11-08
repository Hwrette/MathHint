"""문제 빈도 벡터 → 해설 빈도 벡터를 예측하는 선형회귀.

아래 설정을 바꾸고 이 파일을 실행한다. 학습·테스트를 다시 나누지 않는다.
"""

from pathlib import Path

import torch
from torch import nn

if __package__:
    from .TorchData import load_fixed_dataset, write_json
else:
    from TorchData import load_fixed_dataset, write_json


# 1. 설정
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs/regression"
EPOCHS = 500
LEARNING_RATE = 0.01
SEED = 42


def train_regression(X, Y, epochs=EPOCHS, learning_rate=LEARNING_RATE, seed=SEED):
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
    error = prediction - answer
    return {
        "mse": error.square().mean().item(),
        "mae": error.abs().mean().item(),
        "mean_cosine_similarity": nn.functional.cosine_similarity(prediction, answer, dim=1).mean().item(),
    }


def main():
    # 2. 원래 나눈 학습·테스트 데이터 읽기
    torch.set_num_threads(2)
    data = load_fixed_dataset(ROOT)
    X_train = data["arrays"]["problems"]["train"]
    X_test = data["arrays"]["problems"]["test"]
    Y_train = data["arrays"]["solutions"]["train"]
    Y_test = data["arrays"]["solutions"]["test"]

    # 3. 학습 — 테스트 정답은 사용하지 않는다.
    model, history = train_regression(X_train, Y_train, EPOCHS, LEARNING_RATE, SEED)

    # 4. 평가 — 평균 벡터만 예측하는 기준선과도 비교한다.
    with torch.no_grad():
        train_prediction, test_prediction = model(X_train), model(X_test)
    mean_prediction = Y_train.mean(dim=0).expand_as(Y_test)
    metrics = {
        "train": {"raw": evaluate(train_prediction, Y_train)},
        "test": {
            "raw": evaluate(test_prediction, Y_test),
            "clipped_nonnegative": evaluate(test_prediction.clamp_min(0), Y_test),
            "training_mean_baseline": evaluate(mean_prediction, Y_test),
        },
    }

    # 5. 모델·지표·문항별 예측 저장
    OUTPUT.mkdir(parents=True, exist_ok=True)
    config = {"epochs": EPOCHS, "learning_rate": LEARNING_RATE, "seed": SEED}
    torch.save({
        "model_state_dict": model.state_dict(), "config": config,
        "input_vocabulary": data["vocabularies"]["problems"],
        "output_vocabulary": data["vocabularies"]["solutions"],
        "train_ids": data["ids"]["train"], "generation_id": data["generation_id"],
    }, OUTPUT / "regression_model.pt")
    write_json(OUTPUT / "regression_metrics.json", {
        "config": config, "train_ids": data["ids"]["train"], "test_ids": data["ids"]["test"], "metrics": metrics,
    })
    write_json(OUTPUT / "regression_learning_curve.json", history)
    write_json(OUTPUT / "regression_predictions.json", {
        "generation_id": data["generation_id"], "train_ids": data["ids"]["train"], "config": config,
        "vocabulary": data["vocabularies"]["solutions"],
        "documents": [{
            "id": item_id, "raw_predicted_vector": test_prediction[i].tolist(),
            "predicted_vector": test_prediction[i].clamp_min(0).tolist(), "actual_vector": Y_test[i].tolist(),
        } for i, item_id in enumerate(data["ids"]["test"])],
    })
    print(f"학습 {len(X_train)}개 / 테스트 {len(X_test)}개")
    print(f"테스트 MSE: {metrics['test']['raw']['mse']:.4f}")
    print(f"저장 위치: {OUTPUT}")


if __name__ == "__main__":
    main()
