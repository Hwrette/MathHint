"""Problem segmentation for verified endnote-anchored question banks."""
from __future__ import annotations

import re

from .hwpx import HWPXError
from .models import Block, Document, Problem, RawDocument, raw_text


def split_problems(raw: RawDocument) -> Document:
    problems: list[Problem] = []
    preamble: list[Block] = []
    appendix: list[Block] = []
    pending_sources: list[Block] = []
    current: Problem | None = None
    in_appendix = False
    for block in raw.blocks:
        text = raw_text([block])
        note_refs = [s.reference for s in block.spans if s.kind == "note"]
        quick_numbers = any(s.kind == "auto_number" and s.attributes.get("numType") == "ENDNOTE"
                            for s in block.spans)
        # Restrict textual heading detection to title/table paragraphs. A quoted phrase
        # in a normal question must not silently terminate the question.
        heading = (any(s.kind == "table_start" for s in block.spans)
                   and bool(re.search(r"\(\s*(?:빠른\s*정답|해설)\s*\)", text)))
        answer_line = bool(re.match(r"\s*\[(?:정답|해설)\]", text))
        if not note_refs and (heading or quick_numbers or answer_line):
            in_appendix = True
        if in_appendix:
            if note_refs:
                raise HWPXError(f"정답 영역 뒤에 문제 미주가 나옵니다: {block.location}. 경계 검토가 필요합니다.")
            appendix.append(block)
            continue
        if len(note_refs) > 1:
            raise HWPXError(f"한 문단에 미주가 여러 개 있어 문제 경계를 확정할 수 없습니다: {block.location}")
        sources = [s for s in block.spans if s.kind == "provenance"]
        pending_sources.extend(Block(s.location, [s]) for s in sources)
        body = Block(block.location, [s for s in block.spans if s.kind != "provenance"])
        if note_refs:
            note = raw.notes[note_refs[0]]
            if not note.number:
                raise HWPXError(f"번호 없는 미주입니다: {note.location}")
            # In supported files the anchor occurs before the question in its paragraph.
            anchor_index = next(i for i, s in enumerate(body.spans) if s.kind == "note")
            before = body.spans[:anchor_index]
            if any(s.text.strip() for s in before):
                raise HWPXError(f"미주 앞에 본문이 있어 시작 경계가 모호합니다: {block.location}")
            if note.number in {p.number for p in problems}:
                raise HWPXError(f"중복 문제 번호 {note.number}: section별 번호 재시작은 검토가 필요합니다.")
            current = Problem(f"{raw.source_sha256[:12]}-{len(problems) + 1:03d}", note.number,
                              pending_sources, [], note.blocks, [note.note_id])
            pending_sources = []
            problems.append(current)
        if any(s.text.strip() for s in body.spans):
            if pending_sources and current is not None:
                raise HWPXError(f"다음 출처와 문제 미주 사이에 본문이 있습니다: {block.location}")
            if current is None:
                preamble.append(body)
            else:
                current.blocks.append(body)
    if not problems:
        raise HWPXError("문제 시작을 나타내는 endNote 미주를 찾지 못했습니다. "
                        "현재 지원하는 문제은행 구조와 다릅니다. 문서 전체를 한 문제로 추정하지 않습니다.")
    if pending_sources:
        raise HWPXError("연결할 문제가 없는 출처 표가 남았습니다. 문항 경계를 확인하세요.")
    if any(not raw_text(p.blocks) for p in problems):
        raise HWPXError("본문이 비어 있는 문제가 있습니다. 미주가 문제 시작인지 확인하세요.")
    numbers = [p.number for p in problems]
    warnings = []
    if numbers != [str(n) for n in range(1, len(numbers) + 1)]:
        warnings.append("문제 미주 번호가 1부터 연속적이지 않습니다. 원본과 대조하세요.")
    return Document(raw, problems, preamble, appendix, warnings)
