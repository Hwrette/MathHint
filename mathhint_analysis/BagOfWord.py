r"""한국어는 Kiwi, LaTeX 수식은 정규식으로 나누어 등장 횟수를 센다.

INPUT을 바꾸고 실행하면 한 문제의 빈도를 확인할 수 있다.
불용어 제거 없이 모든 토큰을 세며, kiwi:/latex:는 분석 출처다.
"""

from collections import Counter
from pathlib import Path
import re

from kiwipiepy import Kiwi


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data/processed/problems/diff_1_005.txt"
ENCODING = "utf-8-sig"

MATH_DELIMITERS = {"$": "$", "$$": "$$", r"\(": r"\)", r"\[": r"\]"}
# \$를 수식 시작으로 오인하지 않도록 백슬래시와 다음 문자를 한 쌍으로 읽는다.
MATH_MARKER = re.compile(r"\\[^\r\n]|\$\$|\$")
# 명령어 → 기호 명령어 → 숫자 → 나머지 문자 순서로 토큰을 나눈다.
LATEX_TOKEN = re.compile(r"\\[A-Za-z]+|\\[^\s]|[0-9]+(?:\.[0-9]+)?|[^\s]")


def split_math(text: str) -> list[tuple[str, str]]:
    """'값 $x+1$을' → [('kiwi', '값 '), ('latex', 'x+1'), ('kiwi', '을')]."""
    parts = []
    start, cursor = 0, 0
    closing = None
    while True:
        match = MATH_MARKER.search(text, cursor)
        if match is None:
            break
        marker = match.group()
        cursor = match.end()
        if closing == "$" and marker == "$$":
            # $x$$y$의 가운데 두 달러는 앞 수식의 끝과 다음 수식의 시작이다.
            marker = "$"
            cursor = match.start() + 1
        if closing is None:
            if marker not in MATH_DELIMITERS:
                continue
            parts.append(("kiwi", text[start:match.start()]))
            closing = MATH_DELIMITERS[marker]
            start = cursor
        elif marker == closing:
            parts.append(("latex", text[start:match.start()]))
            closing = None
            start = cursor
    if closing is not None:
        raise ValueError(f"수식이 닫히지 않았습니다. 끝 표시 {closing!r}를 확인하세요.")
    parts.append(("kiwi", text[start:]))
    return parts


def tokenize_latex(formula: str) -> list[str]:
    """수식을 명령어·숫자·기호로 나눈다. 중괄호와 알 수 없는 명령어도 보존한다."""
    return LATEX_TOKEN.findall(formula)


def count_tokens(text: str, kiwi: Kiwi | None = None) -> Counter[str]:
    """본문과 수식의 토큰을 {'kiwi:값': 1, 'latex:x': 2, ...}로 센다."""
    bow = Counter()
    for source, content in split_math(text):
        if not content.strip():
            continue
        if source == "latex":
            words = tokenize_latex(content)
        else:
            if kiwi is None:
                kiwi = Kiwi()
            words = [token.form for token in kiwi.tokenize(content)]
        bow.update(f"{source}:{word}" for word in words)
    return bow


def make_bow(file_path: str, encoding: str = "utf-8") -> Counter[str]:
    """파일을 읽고 토큰별 빈도를 반환한다."""
    return count_tokens(Path(file_path).read_text(encoding=encoding))


def main():
    counts = make_bow(INPUT, ENCODING)
    for token, count in counts.most_common():
        print(f"{token}\t{count}")


if __name__ == "__main__":
    main()
