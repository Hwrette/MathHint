"""HWPML(HML) 문제은행에서 분류·문제·원본 정답/해설을 분리한다.

문서의 분류 표는 다음 분류 표까지 이어받고, 출처 표와 ENDNOTE 미주를
일대일로 연결한다. 수식 caption과 미주의 내용은 문제 본문에 섞지 않는다.
삭제 전 번호 매핑을 전달하면 자동 번호가 바뀌어도 문항 ID가 유지된다.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
import unicodedata
import xml.etree.ElementTree as ET

from .equations import convert_equation


class HMLError(ValueError):
    """원본을 임의로 추측해서 문항을 만들 수 없는 구조 오류."""


# 이 자료의 표지·쪽 장식, 수식 caption에는 본문에 없는 문자열도 있다.
_SKIP = {
    "CAPTION", "SHAPECOMMENT", "HEADER", "FOOTER", "MASTERPAGE", "SECDEF",
    "AUTONUM", "NEWNUM", "BINDATA", "BINDATASTORAGE", "SCRIPTCODE",
}
_GRAPHICS = {
    "PICTURE", "LINE", "RECTANGLE", "ELLIPSE", "ARC", "POLYGON", "CURVE",
    "OLE", "CONTAINER", "GROUP", "VIDEO", "TEXTART",
}


def _normal_text(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", value)).strip()


def _plain_chars(element: ET.Element) -> list[str]:
    """분류·출처를 찾는 보기. 수식·해설·caption은 이 보기에서 제외한다."""
    if element.tag in _SKIP | {"ENDNOTE", "FOOTNOTE", "EQUATION"}:
        return []
    if element.tag == "CHAR":
        return [element.text or ""]
    return [text for child in element for text in _plain_chars(child)]


def _clean_lines(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


class _Renderer:
    def __init__(self, question_id: str, transcriptions: dict | None = None):
        self.question_id = question_id
        self.transcriptions = transcriptions or {}
        self.equations: list[dict] = []
        self.warnings: list[str] = []
        self.graphics = {"problem": False, "solution": False}

    def render(self, element: ET.Element, region: str, location: str) -> str:
        tag = element.tag
        if tag in _SKIP | {"ENDNOTE", "FOOTNOTE"}:
            return ""
        if tag == "EQUATION":
            scripts = list(element.iter("SCRIPT"))
            if len(scripts) != 1:
                raise HMLError(f"{self.question_id}: 수식 SCRIPT는 하나여야 합니다: {location}")
            raw = scripts[0].text or ""
            result = convert_equation(raw)
            transcription = self.transcriptions.get((self.question_id, region, hashlib.sha256(raw.encode()).hexdigest()))
            if transcription is not None and transcription["expected_raw"] != raw:
                raise HMLError("수식 전사표와 원문이 일치하지 않습니다.")
            equation_id = f"{self.question_id}_eq{len(self.equations) + 1:04d}"
            record = {"id": equation_id, "raw": raw, "latex": result.latex,
                      "warnings": list(result.warnings), "region": region,
                      "location": location}
            self.equations.append(record)
            if transcription is not None:
                record["original_warnings"] = record["warnings"]
                record["warnings"] = []
                record["latex"] = transcription["latex"]
                record["transcription_reason"] = transcription["reason"]
                return "$" + transcription["latex"] + "$" if transcription["latex"] else ""
            if result.latex is None or result.warnings:
                self.warnings.append(f"{region}:{equation_id}: {'; '.join(result.warnings)}")
                # 원본 구문을 숨기거나 잘못된 LaTeX를 그럴듯하게 보이지 않는다.
                return "[수식 변환 검토 필요: " + raw.replace("$", r"\$") + "]"
            return "$" + result.latex + "$"
        if tag == "TAB":
            return "\t"
        if tag == "LINEBREAK":
            return "\n"
        if tag in _GRAPHICS:
            self.graphics[region] = True
            # 이미지 자체를 텍스트 특징에 넣지 않는다. 도형의 글자는 보존한다.
            if tag == "PICTURE":
                return ""
        if tag == "TABLE":
            rows = []
            for row_i, row in enumerate(element.findall("ROW")):
                cells = [self.render(cell, region, f"{location}/ROW[{row_i}]/CELL[{j}]").strip()
                         for j, cell in enumerate(row.findall("CELL"))]
                rows.append("\t".join(cells))
            return "\n" + "\n".join(rows) + "\n"
        pieces = [element.text or ""]
        for i, child in enumerate(element):
            pieces.append(self.render(child, region, f"{location}/{child.tag}[{i}]"))
            # TAB/LINEBREAK 이후의 tail에도 선택지와 조건이 들어갈 수 있다.
            pieces.append(child.tail or "")
        text = "".join(pieces)
        return text + "\n" if tag == "P" else text


def _file_identity(path: Path) -> tuple[str, int, str]:
    name = unicodedata.normalize("NFC", path.name)
    subject = "삼각함수" if "삼각함수" in name else "미분" if "미분" in name else None
    match = re.search(r"문제[-_\s]*(\d+)\.hml$", name, re.IGNORECASE)
    if subject is None or match is None:
        raise HMLError("파일명에는 미분/삼각함수와 '문제_1.hml' 형태의 자료 번호가 필요합니다.")
    return subject, int(match.group(1)), "diff" if subject == "미분" else "trig"


def read_hml(path: str | Path, original_numbers: dict[int, int] | None = None,
             transcriptions: list[dict] | None = None) -> list[dict]:
    """문제·정답을 같은 원래 번호의 ID로 반환하며 원본 파일은 수정하지 않는다.

    ``original_numbers``는 현재 자동 번호→삭제 전 번호다. 매핑이 주어졌다면
    문항마다 값이 있어야 하며, 누락되었다고 현재 번호를 대신 사용하지 않는다.
    """
    path = Path(path)
    transcription_index = {}
    for entry in transcriptions or []:
        key = (entry["question_id"], entry["region"], entry["raw_sha256"])
        if key in transcription_index or hashlib.sha256(entry["expected_raw"].encode()).hexdigest() != key[2]:
            raise HMLError("수식 전사표가 중복되거나 해시가 일치하지 않습니다.")
        if (not entry["latex"].strip() and not entry.get("layout_only")) or "$" in entry["latex"]:
            raise HMLError("전사한 LaTeX는 구분자 없는 수식이어야 합니다. 빈 전사는 명시적인 서식 객체만 허용합니다.")
        transcription_index[key] = entry
    subject, file_number, prefix = _file_identity(path)
    if original_numbers is not None:
        if any(not isinstance(k, int) or isinstance(k, bool) or k < 1
               or not isinstance(v, int) or isinstance(v, bool) or v < 1
               for k, v in original_numbers.items()):
            raise HMLError("원래 번호 매핑은 양의 정수→양의 정수여야 합니다.")
        if len(set(original_numbers.values())) != len(original_numbers):
            raise HMLError("원래 번호 매핑에 중복된 원래 번호가 있습니다.")
    data = path.read_bytes()
    try:
        document = ET.fromstring(data)
    except ET.ParseError as exc:
        raise HMLError(f"HML XML을 읽을 수 없습니다: {path.name}: {exc}") from exc
    if document.tag != "HWPML":
        raise HMLError("HWPML 루트가 없는 파일입니다.")
    sections = document.findall("./BODY/SECTION")
    if not sections:
        raise HMLError("HML BODY/SECTION이 없습니다.")
    digest = hashlib.sha256(data).hexdigest()
    records: list[dict] = []
    labels: list[str] | None = None
    pending: dict | None = None
    used_numbers: set[int] = set()

    def finish():
        nonlocal pending
        if pending is None:
            return
        notes = [(p_i, n) for p_i, p in pending["paragraphs"] for n in p.iter("ENDNOTE")]
        if len(notes) != 1:
            raise HMLError(f"{path.name}: 출처마다 ENDNOTE 미주가 하나여야 합니다: {pending['source']}")
        note_p, note = notes[0]
        note_numbers = [int(a.get("Number", "0")) for a in note.iter("AUTONUM")
                        if a.get("NumberType") == "Endnote"]
        if len(note_numbers) != 1 or note_numbers[0] < 1:
            raise HMLError(f"{path.name}: 미주의 자동 번호를 확인할 수 없습니다.")
        current = note_numbers[0]
        if current in used_numbers:
            raise HMLError(f"{path.name}: 중복된 현재 문항 번호 {current}")
        used_numbers.add(current)
        if original_numbers is not None and current not in original_numbers:
            raise HMLError(f"{path.name}: 현재 {current}번의 원래 번호 매핑이 없습니다.")
        original = original_numbers[current] if original_numbers is not None else current
        question_id = f"{prefix}_{file_number}_{original:03d}"
        renderer = _Renderer(question_id, transcription_index)
        problem = _clean_lines("".join(renderer.render(p, "problem", f"SECTION/P[{p_i}]")
                                         for p_i, p in pending["paragraphs"]))
        # ENDNOTE 자체는 본문 렌더러가 제외하므로 그 자식만 별도 렌더링한다.
        solution = _clean_lines("".join(renderer.render(c, "solution", f"SECTION/P[{note_p}]/ENDNOTE/{c.tag}[{j}]")
                                          for j, c in enumerate(note)))
        if not problem:
            raise HMLError(f"{question_id}: 문제 본문이 비어 있습니다.")
        if "[정답]" not in solution:
            raise HMLError(f"{question_id}: 원본 정답 표지가 없습니다.")
        answer = solution.split("[정답]", 1)[1].split("[해설]", 1)[0].strip()
        if not answer:
            raise HMLError(f"{question_id}: 원본 정답이 비어 있습니다.")
        if renderer.graphics["problem"]:
            renderer.warnings.append("problem: 문제 본문에 그림/도형 객체가 있습니다.")
        curriculum, unit, subunit, type_label = pending["labels"]
        records.append({
            "id": question_id, "subject": subject, "file_number": file_number,
            "original_number": original, "current_number": current,
            "curriculum": curriculum, "unit": unit, "subunit": subunit,
            "type": type_label, "source": pending["source"],
            "source_file": unicodedata.normalize("NFC", path.name), "source_sha256": digest,
            "source_paragraph": pending["source_paragraph"], "problem_paragraph": note_p,
            "problem_text": problem, "solution_text": solution, "answer_text": answer,
            "equations": renderer.equations, "warnings": renderer.warnings,
            "has_body_graphic": renderer.graphics["problem"],
            "has_solution_graphic": renderer.graphics["solution"],
        })
        pending = None

    for section_i, section in enumerate(sections):
        for p_i, paragraph in enumerate(section):
            chars = [_normal_text(t) for t in _plain_chars(paragraph) if _normal_text(t)]
            if "빠른 정답" in "".join(chars):
                finish()
                break
            heading = [t for t in chars if re.match(r"^\d{2}\s", t)]
            if len(heading) == 4:
                finish()
                labels = heading
                continue
            if "[출처]" in chars:
                finish()
                if labels is None:
                    raise HMLError(f"{path.name}: 분류표보다 먼저 출처가 나왔습니다.")
                source = _normal_text("".join(t for t in chars if t != "[출처]"))
                if not source:
                    raise HMLError(f"{path.name}: 출처 내용이 비어 있습니다.")
                pending = {"source": source, "labels": labels[:], "source_paragraph": p_i,
                           "section": section_i, "paragraphs": []}
                continue
            if pending is not None:
                pending["paragraphs"].append((p_i, paragraph))
        finish()
    if not records:
        raise HMLError(f"{path.name}: 지원하는 문제은행 문항을 찾지 못했습니다.")
    if len(records) != len(list(document.iter("ENDNOTE"))):
        raise HMLError(f"{path.name}: 출처와 ENDNOTE 미주의 수가 일치하지 않습니다.")
    if len({r["id"] for r in records}) != len(records):
        raise HMLError(f"{path.name}: 중복 문항 ID가 있습니다.")
    return records
