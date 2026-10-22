"""HWPX 원본에서 글·수식·미주를 읽고, 원본 위치와 함께 보관한다.

HWPX는 여러 XML 파일을 ZIP으로 묶은 문서 형식이다. 이 모듈은 화면에
보이는 미리보기나 PDF를 읽는 대신, ZIP 안의 문서 본문 XML을 직접 읽는다.
수식의 한글 전용 스크립트도 여기에서는 변환하지 않고 그대로 보존한다.

읽은 내용은 작은 조각인 Span, 문단 단위 묶음인 Block, 별도로 보관하는
미주인 Note 등으로 나눈다. 이후 segment 모듈이 이 구조로 문제를 분리하고,
다른 모듈이 수식을 LaTeX로 변환한다. 읽기·분리·변환을 구분하는 이유는
어느 단계에서 원문이 잘못 처리됐는지 따로 확인할 수 있게 하기 위해서다.
"""
from __future__ import annotations

import hashlib
import posixpath
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from .models import Block, Equation, Note, RawDocument, Span


class HWPXError(ValueError):
    """원본 구조를 안전하게 해석할 수 없을 때 사용하는 전용 오류다."""

    pass


def local(element: ET.Element) -> str:
    """XML 요소 이름에서 네임스페이스 주소를 제외한 이름만 얻는다.

    원본에서 hp:p라고 보이는 태그를 ElementTree는 보통
    '{네임스페이스 주소}p'로 읽는다. hp 같은 접두사는 문서마다 다를 수
    있으므로, 이 모듈에서는 마지막 중괄호 뒤의 p 같은 이름으로 구별한다.
    """
    return element.tag.rsplit("}", 1)[-1]


def children_with_paths(element: ET.Element, path: str):
    """각 자식 요소와, 그 요소를 원본에서 다시 찾을 수 있는 경로를 내준다.

    yield는 결과를 한꺼번에 리스트로 만들지 않고 하나씩 전달하는 문법이다.
    예를 들어 같은 부모 아래 두 번째 run은 '/run[2]'로 표시한다.
    이 번호는 같은 이름을 가진 형제끼리 1부터 세는 출현 순서다. 원본의
    id 값이 중복돼도 경로로는 서로 다른 수식 위치를 구별할 수 있다.
    """
    counts: dict[str, int] = {}
    for child in element:
        name = local(child)
        counts[name] = counts.get(name, 0) + 1
        yield child, f"{path}/{name}[{counts[name]}]"


def _xml(archive: zipfile.ZipFile, name: str) -> ET.Element:
    """ZIP 내부의 XML 한 파일을 읽어 부모·자식 관계가 있는 요소로 만든다.

    앞에 밑줄이 붙은 함수 이름은 이 모듈 내부에서 사용할 보조 함수라는
    관례다. 크기 제한과 XML 문법 검사를 통과하지 못하면 원인을 알린다.
    """
    # 압축된 크기가 아니라, 압축을 풀었을 때의 XML 크기를 확인한다.
    if archive.getinfo(name).file_size > 32 * 1024 * 1024:
        raise HWPXError(f"XML이 32 MiB 제한을 초과합니다: {name}")
    try:
        return ET.fromstring(archive.read(name))
    except ET.ParseError as exc:
        raise HWPXError(f"XML을 읽을 수 없습니다: {name}: {exc}") from exc


def _section_order(archive: zipfile.ZipFile) -> tuple[list[str], list[str]]:
    """본문 section 파일들의 읽기 순서와, 순서 관련 경고를 반환한다.

    section0.xml 같은 파일은 문서의 본문 구역을 담는다. content.hpf의
    manifest는 파일의 id와 경로를 연결하고, spine은 그 id를 이용해
    실제 읽기 순서를 지정한다. spine이 있으면 파일명 정렬보다 우선한다.
    """
    # 정규식은 여기에서 'section 뒤에 숫자가 붙는 XML 경로'만 고른다.
    # 숫자를 int로 바꾸어 정렬하므로 section2가 section10보다 앞에 온다.
    candidates = sorted(
        (n for n in archive.namelist() if re.fullmatch(r"Contents/section\d+\.xml", n)),
        key=lambda n: int(re.search(r"section(\d+)", n).group(1)),
    )
    if not candidates:
        raise HWPXError("Contents/sectionN.xml이 없는 파일입니다. HWPX 원본인지 확인하세요.")
    if "Contents/content.hpf" not in archive.namelist():
        # 순서를 명시한 파일이 없을 때만 번호순을 쓰고, 추정 사실을 남긴다.
        return candidates, ["content.hpf가 없어 section 번호순으로 읽었습니다. 문서 순서를 확인하세요."]
    package = _xml(archive, "Contents/content.hpf")
    manifest = {}
    for item in package.iter():
        if local(item) != "item":
            continue
        href = item.get("href", "")
        # ZIP 맨 위를 기준으로 쓴 경로와 content.hpf 위치를 기준으로 쓴
        # 경로를 모두 확인한다. ZIP 내부 경로이므로 운영체제와 관계없이
        # 슬래시(/)를 사용하는 posixpath로 다룬다. 디스크에 압축을 풀지는 않는다.
        resolved = href if href in archive.namelist() else posixpath.normpath(posixpath.join("Contents", href))
        manifest[item.get("id")] = resolved
    # spine의 itemref가 가리키는 id를 실제 파일 경로로 바꾼다.
    ordered = [manifest.get(ref.get("idref")) for spine in package.iter()
               if local(spine) == "spine" for ref in spine if local(ref) == "itemref"]
    sections = [name for name in ordered if name in candidates]
    # 어떤 section이 빠지거나 중복되면 문제의 순서도 달라질 수 있으므로
    # 나머지 파일을 임의로 덧붙이는 대신 처리를 멈춘다.
    if len(sections) != len(candidates) or len(set(sections)) != len(sections):
        raise HWPXError("content.hpf의 section 순서가 누락되거나 중복됐습니다. 임의로 순서를 추정하지 않습니다.")
    return sections, []


class _Reader:
    """XML을 순회하며 수식·미주 목록과 문서 순서상의 Span을 함께 만든다.

    self.equations와 self.notes는 각각 고유 키로 원본 정보를 찾는 사전이다.
    본문 수식 조각에는 수식 원문과 해당 키를, 미주 표지에는 키만 둔다.
    미주의 해설 내용은 별도 목록에 두어 문제 본문으로 섞이지 않게 한다.
    """

    # 배치·쪽 설정·숨은 설명 등 본문으로 읽지 않을 요소들이다. 수식의
    # caption에는 실제 수학 내용과 무관한 문자열이 있어 별도로 제외한다.
    # script는 equation 분기에서만 읽어 같은 수식을 두 번 세지 않는다.
    SKIP = {"secPr", "header", "footer", "caption", "shapeComment", "linesegarray",
            "pos", "sz", "outMargin", "inMargin", "cellAddr", "cellSpan", "cellSz",
            "cellMargin", "script", "autoNumFormat", "colPr", "pageNumCtrl", "pageHiding",
            "newNum", "bookmark", "fieldBegin", "fieldEnd", "hiddenComment"}
    # 이 요소들은 텍스트 추출만으로 시각적 의미를 복원할 수 없는 대상이다.
    GRAPHICS = {"pic", "line", "rect", "ellipse", "arc", "polygon", "curve",
                "connectLine", "container", "ole", "chart", "video", "textart"}

    def __init__(self):
        """문서 하나를 읽는 동안 모을 원본 수식·미주·경고를 초기화한다."""
        self.equations: dict[str, Equation] = {}
        self.notes: dict[str, Note] = {}
        self.warnings: list[str] = []

    def block(self, node: ET.Element, path: str) -> Block:
        """요소 하나를 읽은 조각들과 그 원본 경로를 Block으로 묶는다."""
        return Block(path, self.read(node, path))

    def read(self, node: ET.Element, path: str) -> list[Span]:
        """요소 종류별 규칙을 적용하며 원본 순서대로 내용 조각들을 반환한다.

        중첩된 표나 문단은 같은 read 함수를 다시 호출해 읽는다. 이것이
        재귀 호출이며, 바깥 요소 안에 든 내용을 안쪽부터 처리할 수 있다.
        수식·미주처럼 별도 규칙이 있는 요소는 해당 분기에서 끝내어, 그
        내부의 caption이나 해설을 일반 본문처럼 다시 읽지 않게 한다.
        """
        name = local(node)
        if name in self.SKIP:
            return []
        if name == "equation":
            # equation 안의 모든 텍스트를 이어 붙이면 caption의 잡음도
            # 들어간다. 바로 아래 script 하나만 수식 원문으로 채택한다.
            scripts = [x for x in node if local(x) == "script"]
            if len(scripts) != 1:
                raise HWPXError(f"수식 객체의 script 개수가 1이 아닙니다: {path}")
            raw = "".join(scripts[0].itertext())
            # eq00001처럼 우리가 만든 키와 원본 id를 모두 남긴다.
            # 원본 id는 중복될 수 있으므로 내부 참조 키로 직접 쓰지 않는다.
            key = f"eq{len(self.equations) + 1:05d}"
            self.equations[key] = Equation(key, raw, path, node.get("id"))
            return [Span("equation", raw, path, key)]
        if name in {"endNote", "footNote"}:
            if name != "endNote":
                # 각주(footNote)는 문제 시작이라는 보장이 없다. 현재 지원하지
                # 않는 구조로 표시하며, 문제 경계라고 추측하지 않는다.
                return [Span("unsupported", "[각주: 원본 검토 필요]", path, attributes=dict(node.attrib))]
            key = f"note{len(self.notes) + 1:05d}"
            note = Note(key, node.get("number", ""), path, [])
            self.notes[key] = note
            # 미주의 내용은 note.blocks에만 저장한다. 본문으로 돌려주는
            # 조각에는 빈 문자열과 note 키만 있어 정답·해설 누출을 막는다.
            for sub, subpath in children_with_paths(node, path):
                if local(sub) == "subList":
                    note.blocks.extend(self.block(p, ppath) for p, ppath in children_with_paths(sub, subpath))
            return [Span("note", "", path, key)]
        if name == "t":
            # XML의 혼합 내용 예: <t>①<tab/>②</t>에서 ①은 t.text,
            # ②는 tab.tail이다. text만 읽으면 뒤의 선택지 글자가 사라진다.
            # 따라서 앞 텍스트 → 자식(탭·줄바꿈 등) → 자식 뒤 텍스트 순으로 읽는다.
            spans = [Span("text", node.text, path)] if node.text else []
            for child, childpath in children_with_paths(node, path):
                spans.extend(self.read(child, childpath))
                if child.tail:
                    spans.append(Span("text", child.tail, childpath + "/tail()"))
            return spans
        if name in {"tab", "lineBreak", "nbSpace", "fwSpace"}:
            # XML의 배치용 요소를 텍스트의 탭·줄바꿈·공백 문자로 옮긴다.
            value = {"tab": "\t", "lineBreak": "\n", "nbSpace": "\u00a0", "fwSpace": "\u3000"}[name]
            return [Span("text", value, path)]
        if name == "autoNum":
            # 조사한 원본에서 미주 바깥의 ENDNOTE 자동 번호는 '빠른 정답'
            # 목록의 번호였다. 문제 시작의 endNote 요소와 구별해 저장한다.
            return [Span("auto_number", "", path, attributes=dict(node.attrib))]
        if name in self.GRAPHICS:
            spans = [Span("media", f"[시각 자료: {name}; 원본 확인 필요]", path,
                          attributes=dict(node.attrib))]
            # 그림을 이해하거나 OCR로 읽은 것처럼 처리하지 않는다. 검토
            # 표시는 유지하고, drawText로 저장된 글자만 추가로 읽는다.
            for child, childpath in children_with_paths(node, path):
                if local(child) == "drawText":
                    spans.extend(self.read(child, childpath))
            return spans
        if name == "tbl":
            # [출처]라는 표지가 있는 표는 문제 내용이 아니라 출처 정보다.
            # 이후 분리 모듈에서 '다음 문제'에 연결할 수 있게 종류를 달리한다.
            is_source = any(local(t) == "t" and (t.text or "").strip() == "[출처]" for t in node.iter())
            spans = [Span("table_start", "\n", path, attributes=dict(node.attrib))]
            for row, rowpath in children_with_paths(node, path):
                if local(row) != "tr":
                    continue
                first = True
                for cell, cellpath in children_with_paths(row, rowpath):
                    if local(cell) != "tc":
                        continue
                    spans.append(Span("cell_start", "" if first else "\t", cellpath,
                                      attributes=dict(cell.attrib)))
                    first = False
                    spans.extend(self.read(cell, cellpath))
                    spans.append(Span("cell_end", "", cellpath))
                spans.append(Span("row_end", "\n", rowpath))
            # 표의 시작·셀·행·끝을 조각 종류로 남기고, 셀 사이는 탭,
            # 행 사이는 줄바꿈으로 구분한다. (가)/(나) 조건 표도 보존된다.
            # 이 표시는 원본의 병합 셀이나 화면 배치를 완전히 재현한다는 뜻은 아니다.
            spans.append(Span("table_end", "\n", path))
            if is_source:
                return [Span("provenance", "".join(s.text for s in spans).strip(), path)]
            return spans
        spans = []
        # 별도 규칙이 없는 바깥 묶음은 자식을 원래 순서대로 읽는다.
        for child, childpath in children_with_paths(node, path):
            spans.extend(self.read(child, childpath))
        if name == "p":
            spans.append(Span("paragraph_end", "\n", path))
        # 더 읽을 자식도 없고 처리 결과도 없는 요소에 텍스트가 있다면,
        # 모르는 내용이라고 표시한다. 조용히 버리면 검토할 단서가 없어진다.
        if not spans and node.text and node.text.strip():
            spans.append(Span("unsupported", f"[지원되지 않는 {name}: {node.text}]", path))
        return spans


def read_hwpx(path: str | Path) -> RawDocument:
    """HWPX 파일 하나를 읽어 원시 문서 구조를 반환한다. 원본은 수정하지 않는다.

    path는 파일 경로이며 문자열과 pathlib.Path를 모두 받는다. 결과에는
    절대 경로·원본 파일의 SHA-256·section 순서·문단·미주·수식이 들어간다.
    SHA-256은 원본 바이트에서 계산한 지문이므로 같은 이름의 다른 파일을
    구별하고, 이후 실험에 어떤 원본을 썼는지 추적하는 데 사용할 수 있다.
    """
    path = Path(path)
    reader = _Reader()
    try:
        with zipfile.ZipFile(path) as archive:
            # 같은 ZIP 경로가 두 번 들어 있으면 어느 XML을 읽었는지
            # 불명확해질 수 있어, 원본 위치의 유일성을 먼저 확인한다.
            if len(archive.namelist()) != len(set(archive.namelist())):
                raise HWPXError("중복된 ZIP 경로가 있어 원본 위치를 확정할 수 없습니다.")
            sections, warnings = _section_order(archive)
            blocks = []
            script_count = 0
            for section in sections:
                root = _xml(archive, section)
                # 전체 script 수와 실제 추출 수를 따로 센다. 제외한 각주나
                # 장식 속에 수식이 있다면 개수 차이로 검토 필요성을 알린다.
                script_count += sum(local(e) == "script" for e in root.iter())
                # 'ZIP 내부 파일:/sec/p[1]/...' 형태의 출처 경로를 붙인다.
                blocks.extend(reader.block(p, ppath) for p, ppath in children_with_paths(root, section + ":/sec"))
    except (zipfile.BadZipFile, KeyError) as exc:
        raise HWPXError(f"HWPX 패키지를 읽을 수 없습니다: {exc}") from exc
    if script_count != len(reader.equations):
        warnings.append(f"전체 script {script_count}개 중 {len(reader.equations)}개를 추출했습니다. "
                        "각주·장식 등 읽기 제외 영역을 원본에서 확인하세요.")
    return RawDocument(str(path.resolve()), hashlib.sha256(path.read_bytes()).hexdigest(),
                       sections, blocks, reader.notes, reader.equations, script_count,
                       warnings + reader.warnings)
