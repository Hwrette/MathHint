"""Read HWPX XML in document order without using previews or flattening notes."""
from __future__ import annotations

import hashlib
import posixpath
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from .models import Block, Equation, Note, RawDocument, Span


class HWPXError(ValueError):
    pass


def local(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def children_with_paths(element: ET.Element, path: str):
    counts: dict[str, int] = {}
    for child in element:
        name = local(child)
        counts[name] = counts.get(name, 0) + 1
        yield child, f"{path}/{name}[{counts[name]}]"


def _xml(archive: zipfile.ZipFile, name: str) -> ET.Element:
    if archive.getinfo(name).file_size > 32 * 1024 * 1024:
        raise HWPXError(f"XML이 32 MiB 제한을 초과합니다: {name}")
    try:
        return ET.fromstring(archive.read(name))
    except ET.ParseError as exc:
        raise HWPXError(f"XML을 읽을 수 없습니다: {name}: {exc}") from exc


def _section_order(archive: zipfile.ZipFile) -> tuple[list[str], list[str]]:
    candidates = sorted(
        (n for n in archive.namelist() if re.fullmatch(r"Contents/section\d+\.xml", n)),
        key=lambda n: int(re.search(r"section(\d+)", n).group(1)),
    )
    if not candidates:
        raise HWPXError("Contents/sectionN.xml이 없는 파일입니다. HWPX 원본인지 확인하세요.")
    if "Contents/content.hpf" not in archive.namelist():
        return candidates, ["content.hpf가 없어 section 번호순으로 읽었습니다. 문서 순서를 확인하세요."]
    package = _xml(archive, "Contents/content.hpf")
    manifest = {}
    for item in package.iter():
        if local(item) != "item":
            continue
        href = item.get("href", "")
        # Hancom packages use archive-root-relative paths; also accept OPF-relative ones.
        resolved = href if href in archive.namelist() else posixpath.normpath(posixpath.join("Contents", href))
        manifest[item.get("id")] = resolved
    ordered = [manifest.get(ref.get("idref")) for spine in package.iter()
               if local(spine) == "spine" for ref in spine if local(ref) == "itemref"]
    sections = [name for name in ordered if name in candidates]
    if len(sections) != len(candidates) or len(set(sections)) != len(sections):
        raise HWPXError("content.hpf의 section 순서가 누락되거나 중복됐습니다. 임의로 순서를 추정하지 않습니다.")
    return sections, []


class _Reader:
    SKIP = {"secPr", "header", "footer", "caption", "shapeComment", "linesegarray",
            "pos", "sz", "outMargin", "inMargin", "cellAddr", "cellSpan", "cellSz",
            "cellMargin", "script", "autoNumFormat", "colPr", "pageNumCtrl", "pageHiding",
            "newNum", "bookmark", "fieldBegin", "fieldEnd", "hiddenComment"}
    GRAPHICS = {"pic", "line", "rect", "ellipse", "arc", "polygon", "curve",
                "connectLine", "container", "ole", "chart", "video", "textart"}

    def __init__(self):
        self.equations: dict[str, Equation] = {}
        self.notes: dict[str, Note] = {}
        self.warnings: list[str] = []

    def block(self, node: ET.Element, path: str) -> Block:
        return Block(path, self.read(node, path))

    def read(self, node: ET.Element, path: str) -> list[Span]:
        name = local(node)
        if name in self.SKIP:
            return []
        if name == "equation":
            scripts = [x for x in node if local(x) == "script"]
            if len(scripts) != 1:
                raise HWPXError(f"수식 객체의 script 개수가 1이 아닙니다: {path}")
            raw = "".join(scripts[0].itertext())
            key = f"eq{len(self.equations) + 1:05d}"
            self.equations[key] = Equation(key, raw, path, node.get("id"))
            return [Span("equation", raw, path, key)]
        if name in {"endNote", "footNote"}:
            if name != "endNote":
                # A footnote need not be a problem boundary, so never infer one.
                return [Span("unsupported", "[각주: 원본 검토 필요]", path, attributes=dict(node.attrib))]
            key = f"note{len(self.notes) + 1:05d}"
            note = Note(key, node.get("number", ""), path, [])
            self.notes[key] = note
            for sub, subpath in children_with_paths(node, path):
                if local(sub) == "subList":
                    note.blocks.extend(self.block(p, ppath) for p, ppath in children_with_paths(sub, subpath))
            return [Span("note", "", path, key)]
        if name == "t":
            spans = [Span("text", node.text, path)] if node.text else []
            for child, childpath in children_with_paths(node, path):
                spans.extend(self.read(child, childpath))
                if child.tail:
                    spans.append(Span("text", child.tail, childpath + "/tail()"))
            return spans
        if name in {"tab", "lineBreak", "nbSpace", "fwSpace"}:
            value = {"tab": "\t", "lineBreak": "\n", "nbSpace": "\u00a0", "fwSpace": "\u3000"}[name]
            return [Span("text", value, path)]
        if name == "autoNum":
            # ENDNOTE auto numbers outside a note are quick-answer list numbers.
            return [Span("auto_number", "", path, attributes=dict(node.attrib))]
        if name in self.GRAPHICS:
            spans = [Span("media", f"[시각 자료: {name}; 원본 확인 필요]", path,
                          attributes=dict(node.attrib))]
            # Preserve text labels while retaining the graphic marker.
            for child, childpath in children_with_paths(node, path):
                if local(child) == "drawText":
                    spans.extend(self.read(child, childpath))
            return spans
        if name == "tbl":
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
            spans.append(Span("table_end", "\n", path))
            if is_source:
                return [Span("provenance", "".join(s.text for s in spans).strip(), path)]
            return spans
        spans = []
        for child, childpath in children_with_paths(node, path):
            spans.extend(self.read(child, childpath))
        if name == "p":
            spans.append(Span("paragraph_end", "\n", path))
        # Unknown leaf content must remain visible rather than being discarded.
        if not spans and node.text and node.text.strip():
            spans.append(Span("unsupported", f"[지원되지 않는 {name}: {node.text}]", path))
        return spans


def read_hwpx(path: str | Path) -> RawDocument:
    path = Path(path)
    reader = _Reader()
    try:
        with zipfile.ZipFile(path) as archive:
            if len(archive.namelist()) != len(set(archive.namelist())):
                raise HWPXError("중복된 ZIP 경로가 있어 원본 위치를 확정할 수 없습니다.")
            sections, warnings = _section_order(archive)
            blocks = []
            script_count = 0
            for section in sections:
                root = _xml(archive, section)
                script_count += sum(local(e) == "script" for e in root.iter())
                blocks.extend(reader.block(p, ppath) for p, ppath in children_with_paths(root, section + ":/sec"))
    except (zipfile.BadZipFile, KeyError) as exc:
        raise HWPXError(f"HWPX 패키지를 읽을 수 없습니다: {exc}") from exc
    if script_count != len(reader.equations):
        warnings.append(f"전체 script {script_count}개 중 {len(reader.equations)}개를 추출했습니다. "
                        "각주·장식 등 읽기 제외 영역을 원본에서 확인하세요.")
    return RawDocument(str(path.resolve()), hashlib.sha256(path.read_bytes()).hexdigest(),
                       sections, blocks, reader.notes, reader.equations, script_count,
                       warnings + reader.warnings)
