"""문제 빈도벡터로 해설 빈도벡터 전체를 예측하는 PyTorch 회귀 예제입니다.

설치: python -m pip install torch
실행: python TorchRegression.py
직접 지정: python TorchRegression.py 문제/frequency_vectors.json --solutions 해설/frequency_vectors.json

텍스트 분석이나 빈도벡터 생성은 하지 않고, 기존 JSON만 읽습니다.
같은 파일명의 문제·해설 벡터를 짝지어 학습합니다. 해설 벡터를 임의로 만들지 않습니다.
"""

import argparse
import json
import math
from pathlib import Path

import torch
from torch import nn

from TorchData import load_paired_matrices


# ▶ 버튼으로 실행할 때는 이 경로들을 실제 파일 위치로 바꾸면 됩니다.
# 상대 경로는 이 파이썬 파일이 있는 폴더를 기준으로 찾습니다.
PROBLEM_VECTORS_FILE = "outputs/problem_vectors/frequency_vectors.json"
SOLUTION_VECTORS_FILE = "outputs/solution_vectors/frequency_vectors.json"
OUTPUT_FOLDER = "outputs/regression"
EPOCHS = 500
LEARNING_RATE = 0.01
TEST_FRACTION = 0.2
SEED = 42


def train_regression(
    X: torch.Tensor,
    Y: torch.Tensor,
    *,
    epochs: int = 500,
    learning_rate: float = 0.01,
    test_fraction: float = 0.2,
    seed: int = 42,
) -> dict:
    """학습용 행으로만 모델을 학습하고, 따로 남긴 행에서 오차를 측정합니다.

    X는 [파일 수, 문제 토큰 수], Y는 [파일 수, 해설 토큰 수]입니다.
    문제와 해설의 토큰 목록은 달라도 되며, 각 목록의 순서를 따로 유지합니다.
    반환한 predictions의 행 순서는 입력 X의 행 순서와 같습니다.
    """
    if not isinstance(X, torch.Tensor) or X.ndim != 2 or min(X.shape) < 1:
        raise ValueError("X는 파일과 토큰이 하나 이상인 2차원 텐서여야 합니다.")
    if X.shape[0] < 2:
        raise ValueError("학습·평가 데이터를 나누려면 파일이 2개 이상 필요합니다.")
    if not isinstance(Y, torch.Tensor) or Y.ndim != 2 or Y.shape[0] != X.shape[0] or Y.shape[1] < 1:
        raise ValueError("Y는 문제와 행 수가 같고 해설 토큰이 하나 이상인 2차원 텐서여야 합니다.")
    if not isinstance(epochs, int) or isinstance(epochs, bool) or epochs < 1:
        raise ValueError("epochs는 1 이상의 정수여야 합니다.")
    if not isinstance(learning_rate, (int, float)) or not math.isfinite(learning_rate) or learning_rate <= 0:
        raise ValueError("학습률은 유한한 양수여야 합니다.")
    if not isinstance(test_fraction, (int, float)) or not math.isfinite(test_fraction) or not 0 < test_fraction < 1:
        raise ValueError("평가 비율은 0보다 크고 1보다 작아야 합니다.")
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise ValueError("seed는 0 이상의 정수여야 합니다.")

    # 이 예제는 CPU와 float32를 사용합니다. 빈도를 정규화하거나 변환하지 않습니다.
    X = X.detach().to(device="cpu", dtype=torch.float32)
    Y = Y.detach().to(device="cpu", dtype=torch.float32)
    if not torch.isfinite(X).all() or not torch.isfinite(Y).all():
        raise ValueError("문제와 해설 행렬에 NaN이나 무한대가 있으면 학습할 수 없습니다.")

    # seed를 고정하면 같은 데이터와 설정에서 같은 행 분할과 초기 가중치를 사용합니다.
    torch.manual_seed(seed)
    order = torch.randperm(len(X), generator=torch.Generator().manual_seed(seed))
    test_count = max(1, min(len(X) - 1, int(len(X) * test_fraction)))
    test_indices = order[:test_count]
    train_indices = order[test_count:]
    train_X, train_Y = X[train_indices], Y[train_indices]

    # 입력의 각 칸을 해설 벡터의 각 칸과 연결합니다. 해설 토큰 수만큼 숫자를 출력합니다.
    # 예: 문제 토큰 100개, 해설 토큰 40개라면 100칸을 받아 40칸을 예측합니다.
    model = nn.Linear(X.shape[1], Y.shape[1])
    loss_function = nn.MSELoss()  # 해설 벡터 모든 칸에서 오차 제곱의 평균을 구합니다.
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    with torch.no_grad():
        initial_train_mse = loss_function(model(train_X), train_Y).item()

    model.train()
    for _ in range(epochs):
        prediction = model(train_X)
        loss = loss_function(prediction, train_Y)
        if not torch.isfinite(loss):
            raise ValueError("학습 오차가 유한하지 않습니다. 입력 수치와 학습률을 확인하세요.")
        optimizer.zero_grad()  # 이전 반복의 기울기를 비웁니다.
        loss.backward()  # 오차를 줄이려면 가중치를 어느 방향으로 바꿀지 계산합니다.
        optimizer.step()  # 계산한 기울기로 가중치를 갱신합니다.

    # 평가용 행은 여기서 처음 사용합니다. 학습 중 가중치 갱신에는 쓰지 않습니다.
    model.eval()
    with torch.no_grad():
        predictions = model(X)
        train_mse = loss_function(predictions[train_indices], Y[train_indices]).item()
        test_mse = loss_function(predictions[test_indices], Y[test_indices]).item()
    if not torch.isfinite(predictions).all() or not math.isfinite(train_mse + test_mse):
        raise ValueError("학습 결과가 유한하지 않습니다. 입력 수치와 학습률을 확인하세요.")
    return {
        "model": model,
        "train_indices": train_indices,
        "test_indices": test_indices,
        "predictions": predictions,
        "initial_train_mse": initial_train_mse,
        "train_mse": train_mse,
        "test_mse": test_mse,
    }


def main() -> None:
    """문제·해설 행렬을 읽어 학습하고, 모델 및 파일별 예측 벡터를 저장합니다."""
    script_folder = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="문제 빈도벡터에서 해설 빈도벡터를 예측하는 회귀")
    parser.add_argument("problems", nargs="?", type=Path, help="문제 frequency_vectors.json 경로")
    parser.add_argument("--solutions", "--answers", dest="solutions", type=Path, help="해설 frequency_vectors.json 경로")
    parser.add_argument("-o", "--output", type=Path, help="학습 결과를 저장할 폴더")
    parser.add_argument("--epochs", type=int, default=EPOCHS)
    parser.add_argument("--learning-rate", type=float, default=LEARNING_RATE)
    parser.add_argument("--test-fraction", type=float, default=TEST_FRACTION)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    problems_path = args.problems if args.problems is not None else script_folder / Path(PROBLEM_VECTORS_FILE).expanduser()
    solutions_path = args.solutions if args.solutions is not None else script_folder / Path(SOLUTION_VECTORS_FILE).expanduser()
    output_folder = args.output if args.output is not None else script_folder / Path(OUTPUT_FOLDER).expanduser()
    config = {
        "epochs": args.epochs, "learning_rate": args.learning_rate,
        "test_fraction": args.test_fraction, "seed": args.seed,
    }
    try:
        files, X, Y, problem_vocabulary, solution_vocabulary = load_paired_matrices(problems_path, solutions_path)
        print(f"문제 행렬: {X.shape[0]}행 × {X.shape[1]}열", flush=True)
        print(f"해설 행렬: {Y.shape[0]}행 × {Y.shape[1]}열", flush=True)
        print("회귀 학습 중...", flush=True)
        result = train_regression(X, Y, **config)

        output_folder = output_folder.expanduser().resolve()
        output_folder.mkdir(parents=True, exist_ok=True)
        model_path = output_folder / "model.pt"
        report_path = output_folder / "results.json"
        # 새 문제에서도 같은 토큰 인덱스를 쓰도록 모델과 공통 목록을 함께 저장합니다.
        torch.save({
            "model_type": "multioutput_linear_regression", "input_dim": X.shape[1], "output_dim": Y.shape[1],
            "model_state_dict": result["model"].state_dict(),
            "input_vocabulary": problem_vocabulary, "output_vocabulary": solution_vocabulary,
            "target": "solution_frequency_vector",
            "config": config,
        }, model_path)
        test_rows = set(result["test_indices"].tolist())
        documents = [
            {"file": file, "target_vector": Y[index].tolist(),
             "predicted_vector": result["predictions"][index].tolist(),
             "split": "test" if index in test_rows else "train"}
            for index, file in enumerate(files)
        ]
        report_path.write_text(json.dumps({
            "model_type": "multioutput_linear_regression",
            "target": "solution_frequency_vector",
            "problem_matrix_shape": list(X.shape), "solution_matrix_shape": list(Y.shape),
            "config": config, "initial_train_mse": result["initial_train_mse"],
            "train_mse": result["train_mse"], "test_mse": result["test_mse"],
            "documents": documents,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, UnicodeError, ValueError) as error:
        parser.error(str(error))

    print(f"학습용 파일: {len(result['train_indices'])}개 / 평가용 파일: {len(result['test_indices'])}개")
    print(f"학습 MSE: {result['train_mse']:.6f}")
    print(f"평가 MSE: {result['test_mse']:.6f}")
    print(f"모델 저장: {model_path}")
    print(f"예측 결과 저장: {report_path}")


if __name__ == "__main__":
    main()
