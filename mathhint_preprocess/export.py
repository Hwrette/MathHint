"""추출·분리된 문서를 실제 파일로 저장하는 모듈이다.

문제 본문과 정답·해설을 다른 텍스트 파일에 저장하고, 원시 수식과 출처는
JSON 기록에 함께 보존한다. 사람이 읽는 텍스트가 간단해지더라도 원본을
다시 대조할 수 있도록 원본 HWPX 사본과 SHA-256 값도 남긴다.

처리 흐름은 원본 확인 → 수식 변환 → 문항별 기록·보고서 구성 → 임시 폴더에
저장 → 완성된 폴더로 이동 순서다. 이 모듈은 문제를 풀거나 답을 생성하지 않는다.
"""
from __future__ import annotations

# asdict는 데이터클래스 객체를 중첩된 딕셔너리·목록으로 바꾼다.
# json 모듈은 이렇게 바꾼 자료를 파일에 쓸 문자열로 직렬화한다.
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
    """원본 변경·출력 충돌 등으로 안전하게 저장할 수 없을 때 알리는 오류다."""

    pass


def convert_document_equations(document: Document) -> None:
    """문서의 모든 수식을 규칙으로 변환하고 기존 Equation 객체에 결과를 적는다.

    반환값을 만드는 대신 document 안의 latex와 warnings 필드를 갱신한다.
    지원 구문으로 변환됐다는 사실은 원본과 수학적으로 같음을 증명하지 않는다.
    """
    for equation in document.raw.equations.values():
        result = convert_equation(equation.raw)
        equation.latex = result.latex
        equation.warnings = list(result.warnings)


def render_text(blocks: list[Block], equations: dict[str, Equation]) -> str:
    """문단과 조각의 원래 순서를 따라 사람이 읽을 텍스트를 만든다.

    Block은 문단에 해당하고 Span은 문장·수식·탭 같은 작은 조각이다.
    미주 연결 표시, 출처, 자동 번호는 텍스트에 넣지 않으며 실제 해설은
    별도로 전달된 solution_blocks를 이 함수에 넣어 다른 파일로 저장한다.
    """
    rendered = []
    for block in blocks:
        spans = []
        for span in block.spans:
            if span.kind in {"note", "provenance", "auto_number"}:
                continue
            if span.kind == "equation":
                # 각 수식 Span의 reference로 Equation 객체를 찾아 변환 결과를 읽는다.
                equation = equations[span.reference]
                if equation.latex is None or equation.warnings:
                    # 실패한 수식을 그럴듯한 LaTeX로 지어내지 않는다. 텍스트에는
                    # 검토 표시를 쓰고 정확한 원문은 JSON의 해당 equation_id에 보존한다.
                    spans.append(f"[수식 변환 검토 필요: {equation.equation_id}]")
                else:
                    # $...$는 이 구간이 일반 문장이 아니라 LaTeX 수식임을 나타낸다.
                    spans.append("$" + equation.latex + "$")
            else:
                spans.append(span.text)
        text = "".join(spans).strip()
        if text:
            rendered.append(text)
    # 읽기용 텍스트에서만 연속 빈 줄을 줄인다. 수식 객체를 합치거나 내용을
    # 다시 해석하지 않으며, JSON에 저장할 원시 Span은 이 과정에서 바뀌지 않는다.
    return re.sub(r"\n[ \t]*\n(?:[ \t]*\n)+", "\n\n", "\n".join(rendered)).strip() + "\n"


def _coverage(ids: list[str], equations: dict[str, Equation]) -> dict[str, int]:
    """지정한 영역의 전체·변환 완료·검토 필요 수식 개수를 계산한다.

    이름 앞의 _는 이 모듈 내부에서 쓰는 보조 함수라는 관례다.
    같은 ID가 반복되더라도 수식 객체 하나는 한 번만 세도록 중복을 제거한다.
    """
    unique = list(dict.fromkeys(ids))
    # 조건식의 True는 합계에서 1, False는 0으로 계산되므로 통과 개수가 된다.
    converted = sum(equations[i].latex is not None and not equations[i].warnings for i in unique)
    return {"total": len(unique), "converted": converted, "needs_review": len(unique) - converted}


def _json(path: Path, data: object) -> None:
    """하나의 자료를 들여쓰기된 JSON 파일로 저장한다.

    UTF-8은 한글을 포함한 문자를 저장하는 인코딩이다. ensure_ascii=False는
    한글을 유니코드 이스케이프 표기로 바꾸지 않고 그대로 표시하며,
    indent=2는 읽기 쉽게 들여쓴다.
    """
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _directory_name(source: Path, digest: str) -> str:
    """원본 이름과 해시 앞부분으로 재실행해도 같은 결과 폴더 이름을 만든다.

    NFC는 한글 자모가 분리되어 들어온 이름을 가능한 한 조합된 표기로 맞춘다.
    같은 이름의 다른 내용은 해시로 구별하고, 연속된 .hwpx 확장자도 정리한다.
    """
    stem = unicodedata.normalize("NFC", source.name)
    while stem.lower().endswith(".hwpx"):
        stem = stem[:-5]
    stem = re.sub(r"[^\w.\-가-힣]+", "_", stem, flags=re.UNICODE).strip("._")
    # 폴더 이름 길이는 글자 수가 아니라 UTF-8 바이트 수로 제한한다.
    # 한글 한 글자는 보통 3바이트이므로 일반적인 255바이트 파일명 제한을 고려한다.
    while len(stem.encode("utf-8")) > 160:
        stem = stem[:-1]
    return f"{stem or 'document'}_{digest[:12]}"


def export_document(document: Document, output_root: Path) -> Path:
    """문서 하나의 결과 폴더를 새로 만들고 그 경로를 반환한다.

    problems/와 solutions/에는 문항별 텍스트를 따로 넣는다. records.jsonl은
    한 줄에 한 문항을 기록하고, document.json은 문서 전체의 원시 구조를,
    report.json은 영역별 변환 결과와 검토 대상을 담는다. source.hwpx에는
    원본 바이트를 그대로 복사한다. 기존 출력이나 원본에는 덮어쓰지 않는다.
    """
    # resolve로 상대 경로를 절대 경로로 맞춰 경로 충돌을 비교하기 쉽게 한다.
    source = Path(document.raw.source_file).resolve()
    output_root = Path(output_root).resolve()
    destination = output_root / _directory_name(source, document.raw.source_sha256)
    if output_root == source or destination == source or destination in source.parents:
        raise ExportError("출력 위치가 원본 파일과 겹칩니다. 별도 출력 폴더를 선택하세요.")
    if destination.exists() or destination.is_symlink():
        raise ExportError(f"기존 출력은 덮어쓰지 않습니다: {destination}. 다른 출력 폴더를 사용하세요.")
    source_bytes = source.read_bytes()
    # SHA-256은 파일 내용을 바탕으로 계산한 식별값이다. 추출할 때 기록한 값과
    # 지금 값이 다르면 원본이 바뀐 것이므로 서로 다른 버전의 자료를 섞지 않는다.
    if hashlib.sha256(source_bytes).hexdigest() != document.raw.source_sha256:
        raise ExportError("추출 이후 원본이 변경됐습니다. 변경된 원본에서 다시 실행하세요.")
    convert_document_equations(document)
    equations = document.raw.equations
    # dict.fromkeys는 순서를 유지하면서 중복 경고를 제거하는 데 사용한다.
    document_warnings = list(dict.fromkeys(document.raw.warnings + document.warnings))
    source_info = {"source_file": str(source), "source_sha256": document.raw.source_sha256,
                   "preserved_source": "source.hwpx"}
    regions = {
        "body": [i for p in document.problems for i in equation_ids(p.blocks)],
        "solutions": [i for n in document.raw.notes.values() for i in equation_ids(n.blocks)],
        "appendix": equation_ids(document.appendix_blocks),
        "preamble": equation_ids(document.preamble_blocks),
    }
    # 본문·해설·부록·머리말을 따로 세어 해설 수식을 문제 입력 통계에 섞지 않는다.
    # 어디에도 연결되지 않은 수식은 버리지 않고 unassigned 영역과 경고로 남긴다.
    assigned = set(i for ids in regions.values() for i in ids)
    regions["unassigned"] = [i for i in equations if i not in assigned]
    if regions["unassigned"]:
        document_warnings.append("본문·해설·부록·머리말에 연결되지 않은 수식이 있습니다. document.json에서 확인하세요.")
    records = []
    problem_reports = []
    for index, problem in enumerate(document.problems, 1):
        # enumerate(..., 1)은 문항을 하나씩 읽으며 파일명에 사용할 1부터의 순번도 준다.
        body_ids = equation_ids(problem.blocks)
        solution_ids = equation_ids(problem.solution_blocks)
        body_equations = [equations[i] for i in body_ids]
        body_bad = [asdict(e) for e in body_equations if e.latex is None or e.warnings]
        body_media = [asdict(s) for b in problem.blocks for s in b.spans if s.kind == "media"]
        body_unsupported = [asdict(s) for b in problem.blocks for s in b.spans if s.kind == "unsupported"]
        supported = not (body_bad or body_media or body_unsupported or document_warnings)
        # :03d는 순번을 001, 002처럼 세 자리로 맞추는 문자열 포맷이다.
        problem_file = f"problems/{index:03d}.txt"
        solution_file = f"solutions/{index:03d}.txt"
        solution_review = any(equations[i].latex is None or equations[i].warnings for i in solution_ids)
        solution_review = solution_review or any(s.kind in {"media", "unsupported"}
                                               for b in problem.solution_blocks for s in b.spans)
        # 해설에만 이미지나 변환 경고가 있어도 문제 본문의 supported 값은 바꾸지 않는다.
        # 연구에서 문제 입력과 해설 평가 자료를 분리하기 위한 기준이다.
        record = {
            "schema_version": SCHEMA_VERSION, "software_version": __version__,
            **source_info, **asdict(problem),
            # **는 딕셔너리의 항목을 현재 딕셔너리에 펼쳐 넣는다. asdict(problem)은
            # 문제의 중첩 Block·Span도 함께 변환하므로 원래 문장/수식 순서가 남는다.
            "problem_file": problem_file, "solution_file": solution_file,
            "problem_text_raw": raw_text(problem.blocks),
            "problem_latex": render_text(problem.blocks, equations).rstrip("\n"),
            "solution_raw": raw_text(problem.solution_blocks),
            "solution_latex": render_text(problem.solution_blocks, equations).rstrip("\n"),
            "equations": [asdict(e) for e in body_equations],
            "solution_equations": [asdict(equations[i]) for i in solution_ids],
            "supported_for_text_export": supported,
            # 변환 규칙을 적용할 수 있는지와 수학적 동치 검증 여부는 서로 다른 정보다.
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
    # 보고서는 문항별 검토 사유와 문서 전체의 집계를 함께 제공한다.
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
    # 잠금 파일을 x 모드(이미 있으면 실패)로 열어 같은 결과에 대한 동시 실행을 막는다.
    # 이전 실행이 비정상 종료되어 잠금이 남은 경우에도 자동 덮어쓰지 않고 알린다.
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
        # 완성 전 파일은 임시 폴더 staging에만 쓴다. 중간에 실패한 결과가 완성된
        # 출력 폴더처럼 보이지 않도록 모든 저장을 마친 다음 최종 이름으로 이동한다.
        (staging / "problems").mkdir()
        (staging / "solutions").mkdir()
        (staging / "source.hwpx").write_bytes(source_bytes)
        for record in records:
            (staging / record["problem_file"]).write_text(record["problem_latex"] + "\n", encoding="utf-8")
            (staging / record["solution_file"]).write_text(record["solution_latex"] + "\n", encoding="utf-8")
        with (staging / "records.jsonl").open("w", encoding="utf-8") as handle:
            # JSON은 파일 전체가 한 자료이고 JSONL은 줄마다 독립된 JSON 자료다.
            # 문항별로 한 줄을 쓰면 나중에 전체를 한 번에 읽지 않고 한 문항씩 처리할 수 있다.
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
        # 이동이 끝나면 임시 경로는 더 이상 없으므로 정리 대상에서 제외한다.
        staging = None
    finally:
        # finally는 정상 완료와 오류 발생 모두에서 실행된다. 실패한 임시 결과와
        # 이번 실행의 잠금을 지워 다음 실행에 불완전한 상태를 남기지 않는다.
        if staging is not None:
            shutil.rmtree(staging)
        lock.unlink(missing_ok=True)
    return destination
