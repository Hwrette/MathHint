#!/usr/bin/env python3
"""Optionally syntax-check exported equations with an installed pdflatex.

Usage: python scripts/validate_latex.py outputs/sample --output artifacts/latex-validation

Uses the exported LaTeX, without reconverting source scripts. Never modifies the
sample data or replaces an existing artifact directory. A successful TeX run
checks syntax only, not mathematical equivalence to the original equations.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory


def _tex_label(value: str) -> str:
    """Render metadata as literal ASCII text, never as TeX commands."""
    escapes = {
        "\\": r"\textbackslash{}", "{": r"\{", "}": r"\}",
        "#": r"\#", "$": r"\$", "%": r"\%", "&": r"\&",
        "_": r"\_", "^": r"\textasciicircum{}", "~": r"\textasciitilde{}",
    }
    ascii_value = value.encode("ascii", "backslashreplace").decode("ascii")
    return "".join(escapes.get(char, char) for char in ascii_value.replace("\n", " ").replace("\r", " "))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("outputs_root", type=Path, help="Directory containing exported document.json files")
    parser.add_argument("--output", type=Path, required=True, help="New directory for TeX, log, PDF, and summary.json")
    args = parser.parse_args()
    root = args.outputs_root.resolve()
    output = args.output.resolve()
    if not root.is_dir():
        parser.error(f"input directory does not exist: {root}")
    if output.exists():
        parser.error(f"artifact output already exists; choose a new directory: {output}")
    executable = shutil.which("pdflatex")
    if executable is None:
        parser.error("optional pdflatex executable was not found; install a TeX distribution with amsmath/amssymb to run this validation")
    documents = sorted(root.rglob("document.json"))
    if not documents:
        parser.error(f"no document.json files found under {root}")

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
    try:
        for number, path in enumerate(documents, 1):
            raw = json.loads(path.read_text(encoding="utf-8"))["document"]["raw"]
            equations = raw["equations"]
            if not isinstance(equations, dict):
                raise ValueError(f"expected raw.equations object: {path}")
            document_id = f"D{number:03d}"
            counts = {"document_id": document_id, "document_json": str(path),
                      "source_sha256": raw.get("source_sha256"),
                      "total_equations": len(equations), "supported": 0, "skipped": 0,
                      "raw_warnings_total": 0}
            lines.append("% " + document_id + " " + ascii(str(path.relative_to(root))))
            for key, equation in equations.items():
                equation_id = equation.get("equation_id", key)
                warnings = equation.get("warnings", [])
                if not isinstance(warnings, list):
                    raise ValueError(f"expected equation warnings list: {path}:{equation_id}")
                counts["raw_warnings_total"] += len(warnings)
                if warnings:
                    summary["raw_warnings"].append({"document_id": document_id,
                                                    "equation_id": equation_id,
                                                    "raw": equation.get("raw"),
                                                    "warnings": warnings})
                latex = equation.get("latex")
                if isinstance(latex, str) and latex.strip():
                    counts["supported"] += 1
                    lines.append(r"\noindent\texttt{" + document_id + "/" + _tex_label(str(equation_id))
                                 + r"}\quad $" + latex + r"$\par")
                else:
                    counts["skipped"] += 1
                    summary["skipped_equations"].append({"document_id": document_id,
                                                        "equation_id": equation_id,
                                                        "raw": equation.get("raw"),
                                                        "location": equation.get("location"),
                                                        "warnings": warnings})
            summary["documents"].append(counts)
            for key in ("total_equations", "supported", "skipped", "raw_warnings_total"):
                summary[key] += counts[key]
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(f"cannot read exported equation data: {error}")
    lines.append(r"\end{document}")
    command = [executable, "-no-shell-escape", "-halt-on-error", "-interaction=nonstopmode", "equations.tex"]
    summary["command"] = command
    summary["timeout_seconds"] = 60
    try:
        output.mkdir(parents=True, exist_ok=False)
    except OSError as error:
        parser.error(f"cannot create new artifact directory: {error}")
    with TemporaryDirectory(prefix="mathhint-latex-validation-") as directory:
        work = Path(directory)
        (work / "equations.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
        try:
            result = subprocess.run(command, cwd=work, capture_output=True, text=True,
                                    encoding="utf-8", errors="replace", timeout=60, check=False)
            summary["return_code"] = result.returncode
            summary["syntax_validation_passed"] = result.returncode == 0 and (work / "equations.pdf").is_file()
            stdout = result.stdout + result.stderr
        except subprocess.TimeoutExpired as error:
            summary["return_code"] = None
            summary["error"] = "pdflatex exceeded 60-second timeout"
            stdout = str(error)
        except OSError as error:
            summary["return_code"] = None
            summary["error"] = str(error)
            stdout = str(error)
        (output / "compile.stdout.txt").write_text(stdout, encoding="utf-8")
        for name in ("equations.tex", "equations.log", "equations.pdf"):
            source = work / name
            if source.is_file():
                shutil.copyfile(source, output / name)
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    state = "passed" if summary["syntax_validation_passed"] else "failed"
    print(f"LaTeX syntax validation {state}: {summary['supported']} supported, {summary['skipped']} skipped, "
          f"{summary['raw_warnings_total']} raw warnings, {summary['total_equations']} total.")
    print(f"Artifacts: {output}")
    print("Mathematical equivalence verified: false")
    return 0 if summary["syntax_validation_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
