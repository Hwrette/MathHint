"""조사한 문제은행의 미주 표지를 이용해 문서를 문제 단위로 나눈다.

첨부 원본에서는 각 문제의 시작에 endNote 미주가 있고, 그 안에 정답과
해설이 들어 있다. 이 구조를 이용해 문제 본문과 해설을 분리한다.
문장 속 '1.', '2.' 같은 숫자만 보고 경계를 추측하는 방식은 사용하지 않는다.
다른 구조의 HWPX까지 자동으로 처리한다고 가정하지 않으며, 경계가 모호하면
오류로 알려 사람이 원본을 확인할 수 있게 한다.
"""
from __future__ import annotations

import re

from .hwpx import HWPXError
from .models import Block, Document, Problem, RawDocument, raw_text


def split_problems(raw: RawDocument) -> Document:
    """읽기 모듈이 만든 원시 문서를 문제 목록과 앞뒤 부가 영역으로 나눈다.

    raw.blocks는 원본 순서의 문단들이다. 문단을 하나씩 읽으며 현재 문제에
    본문을 모으다가 새 미주를 만나면 다음 문제를 만든다. 정답 영역으로
    들어간 뒤에는 그 내용을 appendix에 모아 마지막 문제에 섞이지 않게 한다.
    """
    problems: list[Problem] = []
    # preamble은 첫 문제 앞의 제목 등, appendix는 빠른 정답 등 뒤쪽 영역이다.
    preamble: list[Block] = []
    appendix: list[Block] = []
    # 출처 표는 문제 앞에 나온다. 현재 문제에 바로 붙이지 않고, 다음
    # 문제 시작을 만날 때까지 이 대기 목록에 보관한다.
    pending_sources: list[Block] = []
    # None은 아직 첫 문제를 만나지 않았다는 뜻이다.
    current: Problem | None = None
    in_appendix = False
    for block in raw.blocks:
        text = raw_text([block])
        # 읽기 모듈은 미주 내용 대신 참조 조각만 본문에 넣었다. 그 참조를
        # 통해 raw.notes에서 별도로 저장한 번호·해설을 찾을 수 있다.
        note_refs = [s.reference for s in block.spans if s.kind == "note"]
        # endNote 요소 자체와 자동으로 찍힌 ENDNOTE 번호는 다르다.
        # 조사한 원본에서 후자는 본문 뒤의 빠른 정답 번호로 사용된다.
        quick_numbers = any(s.kind == "auto_number" and s.attributes.get("numType") == "ENDNOTE"
                            for s in block.spans)
        # '(해설)' 같은 글자가 일반 문제 문장에 등장할 수도 있다. 제목으로
        # 쓰인 표 문단에서 찾도록 범위를 좁혀 잘못된 종료 판정을 줄인다.
        heading = (any(s.kind == "table_start" for s in block.spans)
                   and bool(re.search(r"\(\s*(?:빠른\s*정답|해설)\s*\)", text)))
        answer_line = bool(re.match(r"\s*\[(?:정답|해설)\]", text))
        # 정답 표지 문단에 새 문제 미주가 없을 때 뒤쪽 영역으로 전환한다.
        if not note_refs and (heading or quick_numbers or answer_line):
            in_appendix = True
        if in_appendix:
            # 정답이 시작된 뒤 새 문제가 나타나면, 지원하는 문서 배치와
            # 맞지 않는 것이다. 어느 쪽이 문제인지 임의로 선택하지 않는다.
            if note_refs:
                raise HWPXError(f"정답 영역 뒤에 문제 미주가 나옵니다: {block.location}. 경계 검토가 필요합니다.")
            appendix.append(block)
            continue
        if len(note_refs) > 1:
            raise HWPXError(f"한 문단에 미주가 여러 개 있어 문제 경계를 확정할 수 없습니다: {block.location}")
        sources = [s for s in block.spans if s.kind == "provenance"]
        pending_sources.extend(Block(s.location, [s]) for s in sources)
        # 출처는 별도 보관했으므로 학습·분류용 문제 본문에서는 제외한다.
        body = Block(block.location, [s for s in block.spans if s.kind != "provenance"])
        if note_refs:
            note = raw.notes[note_refs[0]]
            if not note.number:
                raise HWPXError(f"번호 없는 미주입니다: {note.location}")
            # 지원하는 원본에서는 미주 표지가 문제의 첫 문장보다 먼저 나온다.
            # 앞에 글자가 있으면 이전 문제의 끝인지 현재 문제의 시작인지
            # 불명확하므로, 앞부분을 임의로 잘라 내지 않고 오류로 알린다.
            anchor_index = next(i for i, s in enumerate(body.spans) if s.kind == "note")
            before = body.spans[:anchor_index]
            if any(s.text.strip() for s in before):
                raise HWPXError(f"미주 앞에 본문이 있어 시작 경계가 모호합니다: {block.location}")
            if note.number in {p.number for p in problems}:
                raise HWPXError(f"중복 문제 번호 {note.number}: section별 번호 재시작은 검토가 필요합니다.")
            # 문제 id에는 원본 해시의 앞부분과 추출 순번을 사용한다.
            # note.blocks는 해설 전용 필드로 넘기며 본문 리스트와 구별한다.
            current = Problem(f"{raw.source_sha256[:12]}-{len(problems) + 1:03d}", note.number,
                              pending_sources, [], note.blocks, [note.note_id])
            pending_sources = []
            problems.append(current)
        if any(s.text.strip() for s in body.spans):
            # 다음 출처를 이미 본 뒤, 다음 문제 표지 없이 일반 본문이
            # 나오면 경계가 모호하다. 이를 이전 문제의 본문으로 붙이지 않는다.
            if pending_sources and current is not None:
                raise HWPXError(f"다음 출처와 문제 미주 사이에 본문이 있습니다: {block.location}")
            if current is None:
                preamble.append(body)
            else:
                # 새 표지가 없는 일반 문단은 현재 문제의 이어지는 내용이다.
                current.blocks.append(body)
    # 전체 순회를 마친 뒤에도 연결되지 않은 출처나 빈 문제가 있으면
    # 분리가 성공한 것처럼 결과를 내보내지 않는다.
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
        # 번호가 1부터 연속적이지 않은 경우는 즉시 실패시키지는 않지만,
        # 누락 여부를 연구자가 확인할 수 있도록 경고한다.
        warnings.append("문제 미주 번호가 1부터 연속적이지 않습니다. 원본과 대조하세요.")
    return Document(raw, problems, preamble, appendix, warnings)
