"""prepare와 읽기 전용 verify를 구분한다."""

import argparse
from .prepare import prepare, verify


def main():
    parser = argparse.ArgumentParser(description="기존270차원 문제 → 새 전체265 풀이 BoW 준비")
    parser.add_argument("action", choices=("prepare", "verify"))
    args = parser.parse_args()
    (prepare if args.action == "prepare" else verify)()


if __name__ == "__main__":
    main()
