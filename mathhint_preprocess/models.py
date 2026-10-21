"""Lossless source references and ordered intermediate records (schema v1)."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Span:
    kind: str
    text: str
    location: str
    reference: str | None = None
    attributes: dict[str, str] = field(default_factory=dict)


@dataclass
class Block:
    location: str
    spans: list[Span]


@dataclass
class Equation:
    equation_id: str
    raw: str
    location: str
    hwp_id: str | None = None
    latex: str | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass
class Note:
    note_id: str
    number: str
    location: str
    blocks: list[Block]


@dataclass
class RawDocument:
    source_file: str
    source_sha256: str
    sections: list[str]
    blocks: list[Block]
    notes: dict[str, Note]
    equations: dict[str, Equation]
    xml_script_count: int
    warnings: list[str] = field(default_factory=list)


@dataclass
class Problem:
    problem_id: str
    number: str
    source_blocks: list[Block]
    blocks: list[Block]
    solution_blocks: list[Block]
    note_ids: list[str]


@dataclass
class Document:
    raw: RawDocument
    problems: list[Problem]
    preamble_blocks: list[Block]
    appendix_blocks: list[Block]
    warnings: list[str] = field(default_factory=list)
    boundary_method: str = "endnote-anchors"


def raw_text(blocks: list[Block]) -> str:
    """Readable view only; ordered spans remain the authoritative source record."""
    return "\n".join(
        "".join(
            ("$" + s.text + "$") if s.kind == "equation" else s.text
            for s in b.spans if s.kind != "note"
        ).strip()
        for b in blocks
    ).strip()


def equation_ids(blocks: list[Block]) -> list[str]:
    return [s.reference for b in blocks for s in b.spans
            if s.kind == "equation" and s.reference is not None]
