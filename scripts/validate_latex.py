#!/usr/bin/env python3
"""HWPX 내보내기의 document.json 수식을 pdflatex로 확인하는 선택적 도구.

현재 HML 데이터 준비에는 필요 없다. 아래 경로를 바꿔 실행한다.
원본을 수정하지 않고 새 폴더에 TeX·PDF·로그를 저장한다.
컴파일 성공은 LaTeX 문법 검사이며 원본과의 수학적 동치 확인은 아니다.
"""

import json
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "outputs/hwpx"
OUTPUT = ROOT / "artifacts/latex-validation"


def _tex_label(value):
    """수식 식별자를 LaTeX 명령으로 해석하지 않도록 이스케이프한다."""
    escapes = {
        "\\": r"\textbackslash{}", "{": r"\{", "}": r"\}",
        "#": r"\#", "$": r"\$", "%": r"\%", "&": r"\&",
        "_": r"\_", "^": r"\textasciicircum{}", "~": r"\textasciitilde{}",
    }
    value = value.encode("ascii", "backslashreplace").decode("ascii")
    return "".join(escapes.get(char, char) for char in value.replace("\n", " ").replace("\r", " "))


def validate_latex(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    documents = sorted(root.rglob("document.json"))
    if not documents:
        raise ValueError(f"검사할 HWPX document.json이 없습니다: {root}")
    executable = shutil.which("pdflatex")
    if executable is None:
        raise RuntimeError("선택적 검사에는 pdflatex와 amsmath/amssymb 설치가 필요합니다.")

    summary = {
        "schema_version": 1, "input_root": str(root), "total_equations": 0,
        "supported": 0, "skipped": 0, "raw_warnings_total": 0, "documents": [],
        "skipped_equations": [], "raw_warnings": [],
        "math_equivalence_verified": False, "syntax_validation_passed": False,
    }
    lines = [r"\documentclass{article}", r"\usepackage{amsmath,amssymb}", r"\begin{document}"]
    for number, path in enumerate(documents, 1):
        raw = json.loads(path.read_text(encoding="utf-8"))["document"]["raw"]
        equations = raw["equations"]
        document_id = f"D{number:03d}"
        counts = {
            "document_id": document_id, "document_json": str(path),
            "source_sha256": raw.get("source_sha256"), "total_equations": len(equations),
            "supported": 0, "skipped": 0, "raw_warnings_total": 0,
        }
        lines.append("% " + document_id + " " + ascii(str(path.relative_to(root))))
        for key, equation in equations.items():
            equation_id = equation.get("equation_id", key)
            warnings = equation.get("warnings", [])
            counts["raw_warnings_total"] += len(warnings)
            if warnings:
                summary["raw_warnings"].append({
                    "document_id": document_id, "equation_id": equation_id,
                    "raw": equation.get("raw"), "warnings": warnings,
                })
            latex = equation.get("latex")
            if latex and latex.strip():
                counts["supported"] += 1
                lines.append(r"\noindent\texttt{" + document_id + "/" + _tex_label(str(equation_id))
                             + r"}\quad $" + latex + r"$\par")
            else:
                counts["skipped"] += 1
                summary["skipped_equations"].append({
                    "document_id": document_id, "equation_id": equation_id,
                    "raw": equation.get("raw"), "location": equation.get("location"), "warnings": warnings,
                })
        summary["documents"].append(counts)
        for key in ("total_equations", "supported", "skipped", "raw_warnings_total"):
            summary[key] += counts[key]
    lines.append(r"\end{document}")

    # 기존 검사 결과를 덮어쓰지 않는다. TeX 외부 명령 실행도 허용하지 않는다.
    output.mkdir(parents=True, exist_ok=False)
    command = [executable, "-no-shell-escape", "-halt-on-error", "-interaction=nonstopmode", "equations.tex"]
    summary.update({"command": command, "timeout_seconds": 60})
    with TemporaryDirectory(prefix="mathhint-latex-validation-") as directory:
        work = Path(directory)
        (work / "equations.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
        try:
            result = subprocess.run(command, cwd=work, capture_output=True, text=True,
                                    encoding="utf-8", errors="replace", timeout=60, check=False)
            summary["return_code"] = result.returncode
            summary["syntax_validation_passed"] = result.returncode == 0 and (work / "equations.pdf").is_file()
            stdout = result.stdout + result.stderr
        except (subprocess.TimeoutExpired, OSError) as error:
            summary.update({"return_code": None, "error": str(error)})
            stdout = str(error)
        (output / "compile.stdout.txt").write_text(stdout, encoding="utf-8")
        for name in ("equations.tex", "equations.log", "equations.pdf"):
            if (work / name).is_file():
                shutil.copyfile(work / name, output / name)
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main():
    summary = validate_latex(INPUT, OUTPUT)
    print(f"LaTeX 문법 검사: {'통과' if summary['syntax_validation_passed'] else '실패'}, "
          f"변환 {summary['supported']}개, 제외 {summary['skipped']}개")
    print(f"저장 위치: {OUTPUT}")
    return 0 if summary["syntax_validation_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
