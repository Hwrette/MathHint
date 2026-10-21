"""Command-line entry point: python -m mathhint_preprocess INPUT... -o OUTPUT."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from . import __version__
from .export import ExportError, export_document
from .hwpx import HWPXError, read_hwpx
from .segment import split_problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="HWPX 수식을 규칙 기반 LaTeX로 변환하고 문제별 UTF-8 텍스트를 저장합니다.",
        epilog="지원되지 않는 수식은 원본과 경고를 보존합니다. 변환 지원은 수학적 동치 인증이 아닙니다.",
    )
    parser.add_argument("inputs", metavar="INPUT", nargs="+", type=Path, help="원본 HWPX 파일(여러 개 가능)")
    parser.add_argument("-o", "--output", required=True, type=Path, help="새 결과 폴더를 만들 상위 폴더")
    parser.add_argument("--strict", action="store_true", help="본문/문서 검토가 필요하면 결과 저장 후 종료 코드 2 반환")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)
    failed = False
    review = False
    for source in args.inputs:
        try:
            document = split_problems(read_hwpx(source))
            result = export_document(document, args.output)
            report = json.loads((result / "report.json").read_text(encoding="utf-8"))
        except (OSError, HWPXError, ExportError, RecursionError) as exc:
            print(f"오류: {source}: {exc}", file=sys.stderr)
            failed = True
            continue
        body = report["regions"]["body"]
        print(f"{source.name}: {report['problem_count']}문항, 본문 수식 {body['converted']}/{body['total']}개 변환, "
              f"본문/문서 검토 {report['problems_needing_review']}문항")
        print(f"  저장: {result}")
        print("  원본과의 수학적 동치는 별도 대조가 필요합니다. 상세 경고: report.json")
        review = review or not report["supported_for_text_export"]
    if failed:
        return 1
    return 2 if args.strict and review else 0


if __name__ == "__main__":
    sys.exit(main())
