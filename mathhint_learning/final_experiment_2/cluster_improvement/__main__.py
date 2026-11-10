"""prepare/cluster는 명시적 실행, report/verify는 저장된 결과만 읽는다."""

import argparse

from .common import ROOT, OUTPUT, output_path


def run(action, *, root=ROOT, output=None):
    output = output_path(root, output)
    if action == "prepare":
        from .prepare import run as prepare
        return prepare(root, output)
    if action not in ("cluster", "report", "verify"):
        raise ValueError("지원 명령: prepare, cluster, report, verify. 회귀·API 명령은 없습니다.")
    from .prepare import load_dataset
    data = load_dataset(root, output)
    if action == "cluster":
        from .clustering import run as cluster
        return cluster(root, output, data)
    if action == "report":
        from .clustering import report as cluster_report
        from .report import run as report
        cluster_report(root, output, data)
        return report(root, output, data)
    from .verify import run as verify
    return verify(root, output, data)


def main():
    parser = argparse.ArgumentParser(description="전체265 문제 BoW의 K0/K1 군집 구조 비교")
    parser.add_argument("action", choices=("prepare", "cluster", "report", "verify"))
    parser.add_argument("--output", default=str(OUTPUT), help="이번 실험 전용 결과 경로")
    args = parser.parse_args()
    result = run(args.action, output=args.output)
    if args.action == "report":
        print(f"저장 결과의 보고서: {args.output}/README.md · 새 군집 학습/API 호출 없음")
    if args.action == "verify":
        print(f"검증 {result['passed']}개 통과 · {result['failed']}개 실패 · 보호 원본 {result['protected_original_files']}개")
        if result["failed"]:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
