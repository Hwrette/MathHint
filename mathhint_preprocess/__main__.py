"""터미널에서 전처리 프로그램을 실행할 때 시작하는 모듈이다.

실행 예시는 ``python -m mathhint_preprocess 원본.hwpx -o outputs/run01``이다.
입력 읽기·문항 분리·파일 저장을 연결하고, 처리 결과를 화면과 종료 코드로 알린다.
"""
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
    """명령행 인자를 받아 파일들을 처리한 뒤 종료 코드 정수를 반환한다.

    argv가 None이면 실제 터미널 인자를 사용하고, 테스트에서는 문자열 목록을
    직접 전달한다. 0은 정상 저장, 1은 처리 오류, 2는 --strict 사용 중 검토 필요다.
    """
    # argparse는 사용자가 입력한 파일 경로·옵션을 해석하고 --help 안내를 만든다.
    parser = argparse.ArgumentParser(
        description="HWPX 수식을 규칙 기반 LaTeX로 변환하고 문제별 UTF-8 텍스트를 저장합니다.",
        epilog="지원되지 않는 수식은 원본과 경고를 보존합니다. 변환 지원은 수학적 동치 인증이 아닙니다.",
    )
    parser.add_argument("inputs", metavar="INPUT", nargs="+", type=Path, help="원본 HWPX 파일(여러 개 가능)")
    # nargs="+"는 입력 파일을 하나 이상 받는다는 뜻이고 type=Path는 경로 객체로 바꾼다.
    parser.add_argument("-o", "--output", required=True, type=Path, help="새 결과 폴더를 만들 상위 폴더")
    parser.add_argument("--strict", action="store_true", help="본문/문서 검토가 필요하면 결과 저장 후 종료 코드 2 반환")
    # store_true 옵션은 값 없이 --strict를 적으면 True, 생략하면 False가 된다.
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)
    failed = False
    review = False
    # 여러 입력 중 하나가 실패해도 다음 파일을 계속 처리한다. 최종 종료 코드는
    # failed/review에 남긴 전체 상태로 결정하며 이미 성공한 결과는 보존한다.
    for source in args.inputs:
        try:
            # HWPX 원시 구조 읽기 → 문제 경계 분리 → 수식 변환 및 결과 저장 순서다.
            document = split_problems(read_hwpx(source))
            result = export_document(document, args.output)
            report = json.loads((result / "report.json").read_text(encoding="utf-8"))
            # loads는 JSON 문자열을 다시 파이썬 딕셔너리로 읽는 함수다.
        except (OSError, HWPXError, ExportError, RecursionError) as exc:
            # 예상한 파일/문서 오류는 stderr(오류 출력)에 알린다. continue는
            # 현재 입력 처리를 끝내고 반복문의 다음 입력으로 넘어간다.
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
        # 하나라도 실제 처리 오류가 있으면 검토 필요 상태보다 우선해서 1을 반환한다.
        return 1
    # 엄격 모드도 검토 기록을 먼저 저장한다. 코드 2는 결과 미생성이 아니라
    # 보고서의 검토 대상을 확인해야 함을 후속 스크립트 등에 전달하는 신호다.
    return 2 if args.strict and review else 0


if __name__ == "__main__":
    # 이 파일이 실행 시작점일 때만 main을 호출한다. import한 테스트에서는
    # 자동 실행되지 않으며 sys.exit는 반환한 정수를 운영체제 종료 코드로 전달한다.
    sys.exit(main())
