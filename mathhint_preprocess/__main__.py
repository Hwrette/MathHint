"""HWPX 자료용 보조 실행 파일. 현재 HML 자료는 PrepareDataset.py에서 처리한다."""

import json
from pathlib import Path
import sys

from .export import ExportError, export_document
from .hwpx import HWPXError, read_hwpx
from .segment import split_problems

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ()  # 예: (ROOT / "data/raw/문제.hwpx",)
OUTPUT = ROOT / "outputs/hwpx"
STRICT = True


def main():
    if not INPUTS:
        print("현재 HML 자료는 python -m mathhint_analysis.PrepareDataset 실행. 이 파일은 HWPX 보조 도구입니다.")
        return 0
    failed, review = False, False
    for source in INPUTS:
        source = Path(source)
        try:
            document = split_problems(read_hwpx(source))
            result = export_document(document, OUTPUT)
            report = json.loads((result / "report.json").read_text(encoding="utf-8"))
        except (OSError, HWPXError, ExportError, RecursionError) as error:
            print(f"오류: {source}: {error}", file=sys.stderr)
            failed = True
            continue
        body = report["regions"]["body"]
        print(f"{source.name}: {report['problem_count']}문항, 본문 수식 {body['converted']}/{body['total']}개 변환, "
              f"본문/문서 검토 {report['problems_needing_review']}문항")
        print(f"  저장: {result}")
        review = review or not report["supported_for_text_export"]
    return 1 if failed else 2 if STRICT and review else 0


if __name__ == "__main__":
    raise SystemExit(main())
