"""선형 탐색·확정과 저장 체크포인트 재평가를 구분한다."""

import argparse

from .run import train, evaluate


def main():
    parser = argparse.ArgumentParser(description="검증 Precision@20 기준의 선형 해설 BoW 모델")
    parser.add_argument("action", choices=("train", "evaluate"))
    args = parser.parse_args()
    result = train() if args.action == "train" else evaluate()
    print(f"확정 모델: {result['architecture']}; 데이터 {result['dataset_id']}")


if __name__ == "__main__":
    main()
