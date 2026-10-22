#!/usr/bin/env python3
"""저장한 LaTeX 수식을 pdflatex로 컴파일하는 선택적 추가 검사 도구.

실행 예:
    python scripts/validate_latex.py outputs/sample --output artifacts/latex-validation

이 파일은 기본 전처리와 별도로 실행하는 검사 도구다. 이미 저장한 document.json의
LaTeX를 읽으며, 한글 수식 변환을 다시 수행하지 않는다. 따라서 실제 저장 결과가
LaTeX 문서로 처리되는지 확인한다. pdflatex와 amsmath/amssymb는 사용자가 별도로
설치한 경우에만 사용할 수 있고, 기본 전처리에는 필요하지 않다.

원본·기존 결과는 수정하지 않고 새 검사 폴더에 TeX/PDF/로그/요약을 남긴다.
컴파일 성공은 문법 검사 결과이며 원본과 수학적 의미가 같다는 증명은 아니다.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory


def _tex_label(value: str) -> str:
    """식별자 같은 설명용 글자를 LaTeX 명령으로 해석되지 않게 바꾼다.

    이 함수에 들어오는 것은 수식 자체가 아닌 '수식 번호' 등의 표시다.
    LaTeX에서 특수한 뜻이 있는 문자들을 안전한 출력 명령으로 바꾸고,
    ASCII 밖의 문자는 문자 코드 표기로 남겨 설명용 글자 때문에 컴파일이
    깨지지 않도록 한다. 변환된 수식 본문은 이 함수를 통과시키지 않는다.
    """
    # 사전의 키는 원래 문자, 값은 그 문자를 글자로 출력할 LaTeX 표현이다.
    escapes = {
        "\\": r"\textbackslash{}", "{": r"\{", "}": r"\}",
        "#": r"\#", "$": r"\$", "%": r"\%", "&": r"\&",
        "_": r"\_", "^": r"\textasciicircum{}", "~": r"\textasciitilde{}",
    }
    ascii_value = value.encode("ascii", "backslashreplace").decode("ascii")
    # 줄바꿈을 한 칸으로 바꾼 뒤 문자마다 사전에서 출력 방법을 찾는다.
    # get(char, char)는 등록된 특수 문자가 아니면 원래 문자를 그대로 쓴다.
    return "".join(escapes.get(char, char) for char in ascii_value.replace("\n", " ").replace("\r", " "))


def main() -> int:
    """명령행 입력 읽기 → 검사할 수식 모으기 → 컴파일 → 검사 결과 저장.

    성공이면 0, 컴파일 실패이면 1을 반환한다. 경로나 데이터 형식에 문제가
    있으면 argparse의 error()가 이유를 보여 주고 실행을 종료한다.
    """
    # argparse는 터미널에 적은 위치 인자와 --output 같은 옵션을 읽는 표준 도구다.
    # __doc__는 이 파일 맨 위의 설명 문자열이며 --help에도 사용한다.
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("outputs_root", type=Path, help="Directory containing exported document.json files")
    parser.add_argument("--output", type=Path, required=True, help="New directory for TeX, log, PDF, and summary.json")
    args = parser.parse_args()
    # resolve()는 작업 위치에 따라 달라질 수 있는 상대 경로를 절대 경로로 만든다.
    root = args.outputs_root.resolve()
    output = args.output.resolve()
    if not root.is_dir():
        parser.error(f"input directory does not exist: {root}")
    if output.exists():
        parser.error(f"artifact output already exists; choose a new directory: {output}")
    executable = shutil.which("pdflatex")
    # which()는 실행 가능한 프로그램의 경로를 찾는다. 설치하지 않았다면 None이다.
    if executable is None:
        parser.error("optional pdflatex executable was not found; install a TeX distribution with amsmath/amssymb to run this validation")
    documents = sorted(root.rglob("document.json"))
    # rglob는 하위 폴더까지 검색한다. 여러 원본의 결과를 한 번에 검사할 수 있다.
    # sorted로 순서를 고정해 D001, D002 같은 검사 번호가 매번 같도록 한다.
    if not documents:
        parser.error(f"no document.json files found under {root}")

    # 최종 summary.json의 뼈대. 검사 도중 각 문서의 집계와 오류 목록을 채운다.
    # supported는 컴파일에 넣은 수식 수, skipped는 LaTeX가 없어 제외한 수식 수다.
    # raw_warnings_total은 경고 '메시지 수'이므로 실패 수식 수와 다를 수 있다.
    summary = {
        "schema_version": 1,
        "input_root": str(root),
        "total_equations": 0,
        "supported": 0,
        "skipped": 0,
        "raw_warnings_total": 0,
        "documents": [],
        "skipped_equations": [],
        "raw_warnings": [],
        "math_equivalence_verified": False,
        "syntax_validation_passed": False,
    }
    lines = [r"\documentclass{article}", r"\usepackage{amsmath,amssymb}", r"\begin{document}"]
    # lines는 한 줄씩 쌓아 마지막에 합칠 LaTeX 문서다. r"..."는 백슬래시를
    # Python의 줄바꿈 등의 이스케이프로 해석하지 않는 원시 문자열 표기다.
    try:
        for number, path in enumerate(documents, 1):
            # enumerate(..., 1)는 목록의 항목과 1부터 시작하는 번호를 함께 준다.
            # JSON을 Python 사전으로 읽어 그 안의 document → raw → equations에 접근한다.
            raw = json.loads(path.read_text(encoding="utf-8"))["document"]["raw"]
            equations = raw["equations"]
            if not isinstance(equations, dict):
                raise ValueError(f"expected raw.equations object: {path}")
            document_id = f"D{number:03d}"
            # :03d는 정수를 세 자리로 쓰며 빈자리를 0으로 채우는 형식이다(1 → 001).
            counts = {"document_id": document_id, "document_json": str(path),
                      "source_sha256": raw.get("source_sha256"),
                      "total_equations": len(equations), "supported": 0, "skipped": 0,
                      "raw_warnings_total": 0}
            lines.append("% " + document_id + " " + ascii(str(path.relative_to(root))))
            for key, equation in equations.items():
                # items()는 사전의 키(식별자)와 값(수식 자료)을 한 쌍씩 꺼낸다.
                equation_id = equation.get("equation_id", key)
                warnings = equation.get("warnings", [])
                if not isinstance(warnings, list):
                    raise ValueError(f"expected equation warnings list: {path}:{equation_id}")
                counts["raw_warnings_total"] += len(warnings)
                if warnings:
                    # 경고 원문도 요약에 보존해 컴파일에서 빠진 이유를 다시 볼 수 있다.
                    summary["raw_warnings"].append({"document_id": document_id,
                                                    "equation_id": equation_id,
                                                    "raw": equation.get("raw"),
                                                    "warnings": warnings})
                latex = equation.get("latex")
                if isinstance(latex, str) and latex.strip():
                    # 만들어진 LaTeX가 있는 경우만 검사 문서에 붙인다.
                    # 실제 수식과 D001/eq00001 같은 표지를 함께 적어 오류 위치를 찾는다.
                    counts["supported"] += 1
                    lines.append(r"\noindent\texttt{" + document_id + "/" + _tex_label(str(equation_id))
                                 + r"}\quad $" + latex + r"$\par")
                else:
                    # 미지원 수식은 삭제하지 않고 제외 목록에 원문·위치·경고를 기록한다.
                    counts["skipped"] += 1
                    summary["skipped_equations"].append({"document_id": document_id,
                                                        "equation_id": equation_id,
                                                        "raw": equation.get("raw"),
                                                        "location": equation.get("location"),
                                                        "warnings": warnings})
            summary["documents"].append(counts)
            # 문서별 합계를 전체 합계에도 더한다.
            for key in ("total_equations", "supported", "skipped", "raw_warnings_total"):
                summary[key] += counts[key]
    except (OSError, ValueError, KeyError, TypeError) as error:
        # 파일 접근, JSON 형식, 필드 누락 등의 오류를 알아볼 수 있는 메시지로 보고한다.
        parser.error(f"cannot read exported equation data: {error}")
    lines.append(r"\end{document}")
    command = [executable, "-no-shell-escape", "-halt-on-error", "-interaction=nonstopmode", "equations.tex"]
    # 문자열 하나로 셸 명령을 조립하지 않고, 프로그램과 인자를 목록으로 전달한다.
    # -no-shell-escape: TeX 문서가 외부 명령을 실행하는 기능을 끈다.
    # -halt-on-error: 오류에서 멈춘다. nonstopmode: 대화식 입력을 기다리지 않는다.
    summary["command"] = command
    summary["timeout_seconds"] = 60
    try:
        output.mkdir(parents=True, exist_ok=False)
    except OSError as error:
        parser.error(f"cannot create new artifact directory: {error}")
    with TemporaryDirectory(prefix="mathhint-latex-validation-") as directory:
        # with를 벗어나면 임시 폴더는 자동 정리된다. 필요한 산출물만 아래에서 복사한다.
        work = Path(directory)
        (work / "equations.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
        try:
            result = subprocess.run(command, cwd=work, capture_output=True, text=True,
                                    encoding="utf-8", errors="replace", timeout=60, check=False)
            # subprocess는 다른 프로그램을 실행하는 표준 모듈이다.
            # cwd: 실행 폴더, capture_output: 화면 출력을 문자열로 받기,
            # timeout: 최대 대기 시간. check=False이므로 종료 코드를 직접 검사한다.
            summary["return_code"] = result.returncode
            summary["syntax_validation_passed"] = result.returncode == 0 and (work / "equations.pdf").is_file()
            # 종료 코드 0뿐 아니라 실제 PDF 생성 여부도 확인한다.
            stdout = result.stdout + result.stderr
        except subprocess.TimeoutExpired as error:
            # 시간 초과도 오류 기록으로 남긴다. 끝없이 기다리지는 않는다.
            summary["return_code"] = None
            summary["error"] = "pdflatex exceeded 60-second timeout"
            stdout = str(error)
        except OSError as error:
            summary["return_code"] = None
            summary["error"] = str(error)
            stdout = str(error)
        (output / "compile.stdout.txt").write_text(stdout, encoding="utf-8")
        # 도구가 출력한 메시지와 생성한 파일들을 검토용 폴더에 남긴다.
        for name in ("equations.tex", "equations.log", "equations.pdf"):
            source = work / name
            if source.is_file():
                shutil.copyfile(source, output / name)
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # ensure_ascii=False로 한글 경고를 그대로 저장하고, indent=2로 읽기 좋게 들여쓴다.
    state = "passed" if summary["syntax_validation_passed"] else "failed"
    print(f"LaTeX syntax validation {state}: {summary['supported']} supported, {summary['skipped']} skipped, "
          f"{summary['raw_warnings_total']} raw warnings, {summary['total_equations']} total.")
    print(f"Artifacts: {output}")
    print("Mathematical equivalence verified: false")
    return 0 if summary["syntax_validation_passed"] else 1


if __name__ == "__main__":
    # 파일을 직접 실행했을 때만 main()을 호출한다. 다른 파일이 import하면 실행하지 않는다.
    # SystemExit로 main()의 0/1 반환값을 터미널 종료 코드로 전달한다.
    raise SystemExit(main())
