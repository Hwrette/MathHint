"""문서를 읽은 뒤 각 단계가 주고받는 자료의 형태를 정의한다(스키마 버전 1).

이 파일은 수식을 변환하거나 파일을 저장하지 않는다. 문장 조각, 수식, 미주,
문항 등을 어떤 이름의 칸에 보관할지 정한다. 다른 파일들이 이 공통 구조를
사용하므로 추출·변환·저장을 따로 확인할 수 있다.

자료의 기본 포함 관계는 Document → Problem → Block → Span이다.
수식의 원문과 변환 결과는 Equation에, 미주 내용은 Note에 따로 보관하고
Span.reference의 식별자로 연결한다. 원본 ZIP 안의 위치도 함께 기록한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Span:
    """문서 순서대로 놓인 작은 조각 하나. 예: 문장, 수식, 탭, 표 경계.

    @dataclass는 아래 필드들을 받아 객체를 만드는 초기화 함수를 자동으로
    만들어 준다. ``Span(\"text\", \"문제 문장\", \"원본 위치\")``처럼 사용한다.
    필드 뒤의 타입 표시는 저장하려는 자료의 종류를 설명한다.
    """

    # 조각의 종류. text, equation, note, media, table_start 등이 들어간다.
    kind: str
    # 화면에 보일 문자열. equation이면 아직 변환 전인 한글 수식 원문이다.
    # note 표지처럼 화면에 직접 출력하지 않는 조각은 빈 문자열일 수 있다.
    text: str
    # ZIP 내부 XML 파일명과 요소 경로. 원본의 어느 부분인지 다시 찾는 데 쓴다.
    location: str
    # 다른 자료를 가리키는 식별자. 수식은 eq00001, 미주는 note00001 등이다.
    # ``str | None``은 문자열 또는 '연결 대상 없음(None)'을 허용한다는 뜻이다.
    reference: str | None = None
    # 원본 XML의 속성. 번호 종류나 표 속성 등을 문자열 사전으로 보존한다.
    # default_factory=dict는 객체마다 새 사전을 만든다. 여러 조각이 실수로
    # 하나의 수정 가능한 사전을 공유하는 것을 막는 작성 방식이다.
    attributes: dict[str, str] = field(default_factory=dict)


@dataclass
class Block:
    """문단처럼 함께 처리할 조각들을 순서대로 묶은 단위."""

    location: str
    # list는 순서 있는 목록이다. 문장 → 수식 → 문장의 순서를 바꾸지 않는다.
    spans: list[Span]


@dataclass
class Equation:
    """한 수식의 원문, 원본 위치, 변환 결과와 경고를 함께 보관한다."""

    # 이 실행에서 만든 고유 번호. 원본 HWP 수식 번호와 구별해서 사용한다.
    equation_id: str
    # 원본 hp:script 내용. LaTeX 변환에 실패해도 이 문자열은 남긴다.
    raw: str
    location: str
    # 원본 수식 객체의 id. 원본에서 중복될 수 있으므로 고유 키로 쓰지 않는다.
    hwp_id: str | None = None
    # 초기에는 아직 변환하지 않았으므로 None이다. 변환에 성공하면 문자열,
    # 지원하지 못한 경우에는 None과 warnings에 담긴 이유를 함께 확인한다.
    latex: str | None = None
    # 목록도 객체마다 따로 만든다. 다른 수식의 경고가 섞이면 안 되기 때문이다.
    warnings: list[str] = field(default_factory=list)


@dataclass
class Note:
    """문제 시작에 연결된 미주. 이 자료에서는 정답·해설이 들어 있다."""

    note_id: str
    # 원본 미주에 쓰인 번호와 우리가 만든 note_id를 둘 다 남긴다.
    number: str
    location: str
    blocks: list[Block]


@dataclass
class RawDocument:
    """HWPX를 읽은 결과. 아직 문항별로 나누기 전의 문서 자료다."""

    # 읽은 원본의 절대 경로와 파일 내용의 SHA-256 해시(내용 확인용 값).
    source_file: str
    source_sha256: str
    # content.hpf에 지정된 순서대로 읽은 section XML 파일 목록.
    sections: list[str]
    # 본문 쪽 문단들. 미주 내용은 아래 notes에 분리하고 이곳에는 표지만 남긴다.
    blocks: list[Block]
    # dict는 '키 → 값' 연결표다. notes['note00001']로 해당 미주를 찾는다.
    notes: dict[str, Note]
    # equations['eq00001']로 수식의 원문과 LaTeX 결과를 찾는다.
    equations: dict[str, Equation]
    # 원본 section XML 전체의 script 수와 실제 추출 수를 대조하기 위한 개수.
    xml_script_count: int
    warnings: list[str] = field(default_factory=list)


@dataclass
class Problem:
    """문제 하나의 본문과 출처, 연결된 정답·해설을 서로 구분해서 담는다."""

    problem_id: str
    # 원본 문제 번호. 출력 파일의 순서 번호(001.txt 등)와 다를 수 있다.
    number: str
    # 해당 문제 바로 앞의 [출처] 표. 문제 텍스트에는 넣지 않는 메타데이터다.
    source_blocks: list[Block]
    # 질문, 조건, 선택지가 있는 문제 본문.
    blocks: list[Block]
    # 연결된 미주에서 가져온 정답·해설. 입력 문제와 섞지 않는다.
    solution_blocks: list[Block]
    note_ids: list[str]


@dataclass
class Document:
    """문항 분리까지 마친 문서. 원시 자료와 문항 밖의 내용도 보관한다."""

    raw: RawDocument
    problems: list[Problem]
    # 첫 문제 전의 제목 등과 문제 뒤의 빠른 정답·해설 제목 등을 분리해 둔다.
    preamble_blocks: list[Block]
    appendix_blocks: list[Block]
    warnings: list[str] = field(default_factory=list)
    # 이 문서를 어떤 경계 규칙으로 나눴는지 결과에 기록한다.
    boundary_method: str = "endnote-anchors"


def raw_text(blocks: list[Block]) -> str:
    """Block 목록을 사람이 읽기 쉬운 '원시 텍스트 보기'로 합친다.

    수식은 원시 한글 수식 문자열을 $로 감싸서 문장 사이의 위치를 표시한다.
    여기서 LaTeX로 변환하는 것은 아니다. 미주 표지는 빼고, 문단 사이는
    줄바꿈으로 잇는다. 원본 구조를 확인할 때는 이 보기와 함께 spans의
    종류·순서·위치를 확인해야 한다.
    """
    # 안쪽 join: 한 Block의 조각들을 잇는다.
    # 바깥 join: 여러 Block을 줄바꿈으로 잇는다. strip은 양끝 공백 정리다.
    return "\n".join(
        "".join(
            ("$" + s.text + "$") if s.kind == "equation" else s.text
            for s in b.spans if s.kind != "note"
        ).strip()
        for b in blocks
    ).strip()


def equation_ids(blocks: list[Block]) -> list[str]:
    """주어진 Block들에서 수식 식별자만 등장 순서대로 골라 반환한다.

    ``[값 for ... if ...]``는 조건에 맞는 값들을 새 목록으로 만드는
    리스트 컴프리헨션 문법이다. 문장이나 표 경계는 건너뛰고 equation의
    reference만 모아 영역별 수식 개수 계산 등에 사용한다.
    """
    return [s.reference for b in blocks for s in b.spans
            if s.kind == "equation" and s.reference is not None]
