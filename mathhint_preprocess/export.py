"""Export separate problem/solution text and complete, reproducible audit records."""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
import unicodedata

from . import SCHEMA_VERSION, __version__
from .equations import convert_equation
from .models import Block, Document, Equation, equation_ids, raw_text


class ExportError(ValueError):
    pass


def convert_document_equations(document: Document) -> None:
    """Apply supported rules; conversion support does not certify equivalence."""
    for equation in document.raw.equations.values():
        result = convert_equation(equation.raw)
        equation.latex = result.latex
        equation.warnings = list(result.warnings)


def render_text(blocks: list[Block], equations: dict[str, Equation]) -> str:
    """Render ordered body spans; notes and provenance never enter problem text."""
    rendered = []
    for block in blocks:
        spans = []
        for span in block.spans:
            if span.kind in {"note", "provenance", "auto_number"}:
                continue
            if span.kind == "equation":
                equation = equations[span.reference]
                if equation.latex is None or equation.warnings:
                    spans.append(f"[수식 변환 검토 필요: {equation.equation_id}]")
                else:
                    spans.append("$" + equation.latex + "$")
            else:
                spans.append(span.text)
        text = "".join(spans).strip()
        if text:
            rendered.append(text)
    # Do not join mathematical objects or alter their contents. Repeated blank
    # layout lines may be compacted in this text view; raw spans remain unchanged.
    return re.sub(r"\n[ \t]*\n(?:[ \t]*\n)+", "\n\n", "\n".join(rendered)).strip() + "\n"


def _coverage(ids: list[str], equations: dict[str, Equation]) -> dict[str, int]:
    unique = list(dict.fromkeys(ids))
    converted = sum(equations[i].latex is not None and not equations[i].warnings for i in unique)
    return {"total": len(unique), "converted": converted, "needs_review": len(unique) - converted}


def _json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _directory_name(source: Path, digest: str) -> str:
    stem = unicodedata.normalize("NFC", source.name)
    while stem.lower().endswith(".hwpx"):
        stem = stem[:-5]
    stem = re.sub(r"[^\w.\-가-힣]+", "_", stem, flags=re.UNICODE).strip("._")
    # Byte-limit the readable prefix for common 255-byte filesystem components.
    while len(stem.encode("utf-8")) > 160:
        stem = stem[:-1]
    return f"{stem or 'document'}_{digest[:12]}"


def export_document(document: Document, output_root: Path) -> Path:
    """Create one new source directory. Existing outputs and originals are untouched.

    The returned directory contains problems/, solutions/, records.jsonl,
    document.json, report.json, and an unchanged source.hwpx copy.
    """
    source = Path(document.raw.source_file).resolve()
    output_root = Path(output_root).resolve()
    destination = output_root / _directory_name(source, document.raw.source_sha256)
    if output_root == source or destination == source or destination in source.parents:
        raise ExportError("출력 위치가 원본 파일과 겹칩니다. 별도 출력 폴더를 선택하세요.")
    if destination.exists() or destination.is_symlink():
        raise ExportError(f"기존 출력은 덮어쓰지 않습니다: {destination}. 다른 출력 폴더를 사용하세요.")
    source_bytes = source.read_bytes()
    if hashlib.sha256(source_bytes).hexdigest() != document.raw.source_sha256:
        raise ExportError("추출 이후 원본이 변경됐습니다. 변경된 원본에서 다시 실행하세요.")
    convert_document_equations(document)
    equations = document.raw.equations
    document_warnings = list(dict.fromkeys(document.raw.warnings + document.warnings))
    source_info = {"source_file": str(source), "source_sha256": document.raw.source_sha256,
                   "preserved_source": "source.hwpx"}
    regions = {
        "body": [i for p in document.problems for i in equation_ids(p.blocks)],
        "solutions": [i for n in document.raw.notes.values() for i in equation_ids(n.blocks)],
        "appendix": equation_ids(document.appendix_blocks),
        "preamble": equation_ids(document.preamble_blocks),
    }
    assigned = set(i for ids in regions.values() for i in ids)
    regions["unassigned"] = [i for i in equations if i not in assigned]
    if regions["unassigned"]:
        document_warnings.append("본문·해설·부록·머리말에 연결되지 않은 수식이 있습니다. document.json에서 확인하세요.")
    records = []
    problem_reports = []
    for index, problem in enumerate(document.problems, 1):
        body_ids = equation_ids(problem.blocks)
        solution_ids = equation_ids(problem.solution_blocks)
        body_equations = [equations[i] for i in body_ids]
        body_bad = [asdict(e) for e in body_equations if e.latex is None or e.warnings]
        body_media = [asdict(s) for b in problem.blocks for s in b.spans if s.kind == "media"]
        body_unsupported = [asdict(s) for b in problem.blocks for s in b.spans if s.kind == "unsupported"]
        supported = not (body_bad or body_media or body_unsupported or document_warnings)
        problem_file = f"problems/{index:03d}.txt"
        solution_file = f"solutions/{index:03d}.txt"
        solution_review = any(equations[i].latex is None or equations[i].warnings for i in solution_ids)
        solution_review = solution_review or any(s.kind in {"media", "unsupported"}
                                               for b in problem.solution_blocks for s in b.spans)
        record = {
            "schema_version": SCHEMA_VERSION, "software_version": __version__,
            **source_info, **asdict(problem),
            "problem_file": problem_file, "solution_file": solution_file,
            "problem_text_raw": raw_text(problem.blocks),
            "problem_latex": render_text(problem.blocks, equations).rstrip("\n"),
            "solution_raw": raw_text(problem.solution_blocks),
            "solution_latex": render_text(problem.solution_blocks, equations).rstrip("\n"),
            "equations": [asdict(e) for e in body_equations],
            "solution_equations": [asdict(equations[i]) for i in solution_ids],
            "supported_for_text_export": supported,
            "mathematical_equivalence_verified": False,
            "strategy_labels": [],
        }
        records.append(record)
        problem_reports.append({
            "problem_id": problem.problem_id, "number": problem.number,
            "problem_file": problem_file, "solution_file": solution_file,
            "supported_for_text_export": supported,
            "body_equations": _coverage(body_ids, equations),
            "body_conversion_warnings": body_bad,
            "body_visual_review_required": bool(body_media),
            "body_media": body_media, "body_unsupported_spans": body_unsupported,
            "solution_needs_review": bool(solution_review),
        })
    needs_review = sum(not p["supported_for_text_export"] for p in problem_reports)
    report = {
        "schema_version": SCHEMA_VERSION, "software_version": __version__, **source_info,
        "boundary_method": document.boundary_method,
        "problem_count": len(document.problems), "problems_needing_review": needs_review,
        "supported_for_text_export": needs_review == 0 and not document_warnings,
        "mathematical_equivalence_verified": False,
        "conversion_status_meaning": "converted는 지원 규칙으로 변환했다는 뜻이며 원본과의 수학적 동치 검증을 뜻하지 않습니다.",
        "xml_script_count": document.raw.xml_script_count,
        "extracted_equation_count": len(equations),
        "regions": {name: _coverage(ids, equations) for name, ids in regions.items()},
        "document_warnings": document_warnings,
        "problems": problem_reports,
        "all_conversion_warnings": [asdict(e) for e in equations.values() if e.latex is None or e.warnings],
    }
    output_root.mkdir(parents=True, exist_ok=True)
    # Cooperating exporters cannot race to replace the same result directory.
    lock = output_root / f".{destination.name}.lock"
    try:
        lock_file = lock.open("x", encoding="utf-8")
    except FileExistsError as exc:
        raise ExportError(f"같은 출력의 다른 실행 또는 남은 잠금 파일이 있습니다: {lock}") from exc
    staging = None
    try:
        lock_file.close()
        if destination.exists() or destination.is_symlink():
            raise ExportError(f"기존 출력은 덮어쓰지 않습니다: {destination}")
        staging = Path(tempfile.mkdtemp(prefix=".mathhint-", dir=output_root))
        (staging / "problems").mkdir()
        (staging / "solutions").mkdir()
        (staging / "source.hwpx").write_bytes(source_bytes)
        for record in records:
            (staging / record["problem_file"]).write_text(record["problem_latex"] + "\n", encoding="utf-8")
            (staging / record["solution_file"]).write_text(record["solution_latex"] + "\n", encoding="utf-8")
        with (staging / "records.jsonl").open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        _json(staging / "document.json", {
            "schema_version": SCHEMA_VERSION, "software_version": __version__,
            "document": asdict(document),
            "conversion_policy": {"method": "rule-based", "unknown_syntax": "review",
                                  "mathematical_equivalence_verified": False},
        })
        _json(staging / "report.json", report)
        staging.rename(destination)
        staging = None
    finally:
        if staging is not None:
            shutil.rmtree(staging)
        lock.unlink(missing_ok=True)
    return destination
