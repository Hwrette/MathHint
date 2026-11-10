"""MLP 학습·검증 선택과 확정 체크포인트의 읽기 전용 재평가를 구분한다."""

import argparse

from .run import evaluate, train


def main():
    parser = argparse.ArgumentParser(description="검증 Precision@20으로 선택하는 작은 nn.Sequential MLP")
    parser.add_argument("action", choices=("train", "evaluate"))
    args = parser.parse_args()
    result = train() if args.action == "train" else evaluate()
    print(f"확정 모델: {result['architecture']}; 데이터 {result['dataset_id']}")


if __name__ == "__main__":
    main()
