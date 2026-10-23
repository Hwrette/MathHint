r"""한국어 형태소와 LaTeX 토큰을 합쳐 단어별 등장 횟수를 셉니다.

설치: python -m pip install kiwipiepy
실행: python BagOfWord.py examples/bow_sample.txt

한국어는 Kiwi로, $...$ 같은 수식 구간은 정규식으로 나눕니다.
명사만 고르거나 불용어를 제거하지 않고, 나온 토큰을 모두 셉니다.
결과의 kiwi:와 latex:는 토큰을 어느 분석기로 나눴는지 표시합니다.
"""

# argparse: 터미널에서 입력한 파일 경로와 옵션을 읽는 파이썬 기본 도구입니다.
import argparse
# re: 문자열에서 정해진 모양(정규식)에 맞는 부분을 찾습니다. 추가 설치는 필요 없습니다.
import re
# Counter: 단어별로 몇 번 등장했는지 세어 주는 파이썬 기본 도구입니다.
from collections import Counter
# Path: 파일 경로를 다루고 파일 내용을 읽을 때 사용하는 기본 도구입니다.
from pathlib import Path

# Kiwi: 한국어 문장을 작은 의미 단위인 '형태소'로 나누고 품사를 알아냅니다.
# 파이썬 기본 기능이 아니므로 위의 pip install 명령으로 설치해야 합니다.
from kiwipiepy import Kiwi


# 수식의 시작 표시와 그에 대응하는 끝 표시입니다.
# r"..."은 백슬래시를 파이썬의 특수 문자로 해석하지 않는 문자열입니다.
MATH_DELIMITERS = {"$": "$", "$$": "$$", r"\(": r"\)", r"\[": r"\]"}

# 백슬래시와 다음 문자 한 쌍, 또는 달러 표시를 찾습니다.
# \$는 한 쌍으로 읽으므로 수식의 시작으로 오인하지 않습니다.
# 수식 밖에서는 $$를 먼저 읽고, $ 수식 안에서는 닫는 $ 한 글자만 읽습니다.
MATH_MARKER = re.compile(r"\\[^\r\n]|\$\$|\$")

# |는 '또는'이라는 뜻이며, 왼쪽 규칙부터 순서대로 검사합니다.
# 1) \log, \frac 같은 명령어: 백슬래시 + 연속된 영문자
# 2) \{, \}, \, 같은 기호 명령어: 백슬래시 + 공백 아닌 한 글자
# 3) 25, 3.14 같은 숫자: 여러 자리를 한 토큰으로 유지
# 4) 나머지 공백 아닌 한 글자: 변수, 연산자, 중괄호 등을 보존
# 알 수 없는 명령어도 버리지 않으며, \left와 \right도 그대로 셉니다.
LATEX_TOKEN = re.compile(r"\\[A-Za-z]+|\\[^\s]|[0-9]+(?:\.[0-9]+)?|[^\s]")


def split_math(text: str) -> list[tuple[str, str]]:
    """본문을 (분석기 이름, 내용) 쌍으로 나눕니다. 수식 경계 표시는 제외합니다.

    예: '값 $x+1$을' -> [('kiwi', '값 '), ('latex', 'x+1'), ('kiwi', '을')]
    중괄호가 아무리 중첩되어도 수식 전체를 먼저 분리하므로 문제가 없습니다.
    수식이 닫히지 않으면 오류를 내어 잘못된 빈도가 만들어지는 것을 막습니다.
    """
    parts = []
    start = 0  # 아직 처리하지 않은 내용이 시작하는 문자 위치입니다.
    cursor = 0  # 다음 수식 표시를 검색하기 시작할 위치입니다.
    closing = None  # None이면 일반 문장, 값이 있으면 수식 안에 있다는 뜻입니다.

    while True:
        match = MATH_MARKER.search(text, cursor)
        if match is None:
            break  # 더 이상 수식 표시가 없으면 검색을 마칩니다.
        marker = match.group()  # 현재 찾은 표시의 실제 문자열입니다.
        cursor = match.end()
        if closing == "$" and marker == "$$":
            # $x$$y$에서는 가운데 두 달러가 서로 다른 수식의 끝과 시작입니다.
            # 첫 달러만 닫는 표시로 쓰고, 다음 검색에서 둘째 달러를 다시 읽습니다.
            marker = "$"
            cursor = match.start() + 1
        if closing is None:
            if marker not in MATH_DELIMITERS:
                continue  # 수식의 시작 표시가 아니면 다음 표시를 확인합니다.
            parts.append(("kiwi", text[start:match.start()]))
            closing = MATH_DELIMITERS[marker]
            start = cursor  # 시작 표시 자체는 빈도에 넣지 않습니다.
        elif marker == closing:
            parts.append(("latex", text[start:match.start()]))
            closing = None
            start = cursor  # 끝 표시 다음부터는 다시 일반 문장입니다.

    if closing is not None:
        raise ValueError(f"수식이 닫히지 않았습니다. 끝 표시 {closing!r}를 확인하세요.")

    parts.append(("kiwi", text[start:]))  # 마지막 수식 뒤에 남은 문장도 포함합니다.
    return parts


def tokenize_latex(formula: str) -> list[str]:
    r"""수식을 명령어·숫자·기호로 나눕니다. 수학적 구조를 해석하지는 않습니다.

    예: \log_{3} 25 -> ['\\log', '_', '{', '3', '}', '25']
    중괄호도 각각 한 토큰입니다. 공백과 줄바꿈은 토큰으로 세지 않습니다.
    """
    return LATEX_TOKEN.findall(formula)


def count_tokens(text: str, kiwi: Kiwi | None = None) -> Counter[str]:
    """문자열을 분석해 한국어와 수식의 토큰별 등장 횟수를 합칩니다.

    Counter는 {'kiwi:값': 1, 'latex:\\log': 3, ...}처럼 저장됩니다.
    이 '토큰 -> 횟수'가 현재 단계의 희소 빈도벡터입니다. 전체 데이터에서
    공통 단어 목록을 정하거나 숫자 배열로 바꾸는 작업은 아직 하지 않습니다.
    """
    bow = Counter()
    for source, content in split_math(text):
        if not content.strip():
            continue  # 빈 문자열이나 공백만 있는 구간에는 셀 토큰이 없습니다.

        if source == "latex":
            words = tokenize_latex(content)
        else:
            # Kiwi 객체를 한 번만 만들고 여러 문장 구간에 재사용합니다.
            # 밖에서 Kiwi를 전달하면 여러 파일을 분석할 때도 재사용할 수 있습니다.
            if kiwi is None:
                kiwi = Kiwi()
            # token.form은 형태소의 글자입니다. 품사 조건을 걸지 않으므로
            # 명사뿐 아니라 조사·어미·문장부호 등 Kiwi의 모든 결과가 포함됩니다.
            words = [token.form for token in kiwi.tokenize(content)]

        # 출처를 붙여 본문의 '3'과 수식의 '3'을 서로 구분합니다.
        # update는 이미 센 토큰이 다시 나오면 횟수를 더해 줍니다.
        bow.update(f"{source}:{word}" for word in words)
    return bow


def make_bow(file_path: str, encoding: str = "utf-8") -> Counter[str]:
    """텍스트 파일을 읽어 토큰별 등장 횟수를 돌려줍니다.

    file_path는 읽을 파일의 경로입니다. encoding은 글자를 해석하는 방식이며,
    따로 지정하지 않으면 UTF-8을 사용합니다. 파일 인코딩과 맞아야 한글이
    제대로 읽힙니다. 오래된 한글 파일이라면 cp949가 필요할 수도 있습니다.

    매개변수 뒤의 ': str'과 끝의 '-> Counter[str]'는 값의 종류를 알려주는
    타입 힌트입니다. 문자열을 받고 문자열을 키로 하는 Counter를 돌려줍니다.
    """
    # 파일 전체를 읽어 하나의 문자열로 저장합니다.
    # 파일을 찾지 못하거나 인코딩이 맞지 않으면 이 줄에서 오류가 납니다.
    text = Path(file_path).read_text(encoding=encoding)
    # 한국어와 수식을 나눠 분석한 결과를 호출한 곳으로 돌려줍니다.
    return count_tokens(text)


def main() -> None:
    """사용자의 터미널 입력을 받아 분석하고 결과를 화면에 출력합니다.

    -> None은 이 함수가 별도의 결과값을 돌려주지 않는다는 뜻입니다.
    """
    # 입력 규칙을 정합니다. python BagOfWord.py --help로 사용법을 볼 수 있습니다.
    parser = argparse.ArgumentParser(description="한국어 형태소 + LaTeX 토큰 빈도 계산")
    # file은 필수 입력입니다. 예: python BagOfWord.py sample.txt
    # 상대 경로(sample.txt)는 터미널의 현재 작업 폴더를 기준으로 찾습니다.
    parser.add_argument("file", help="분석할 텍스트 파일 경로")
    # --encoding은 선택 사항입니다. 생략하면 utf-8을 사용합니다.
    # 예: python BagOfWord.py sample.txt --encoding cp949
    parser.add_argument("--encoding", default="utf-8", help="파일 인코딩")
    # 입력을 해석한 결과를 args에 담습니다.
    args = parser.parse_args()

    # 위에서 만든 함수를 호출하고 단어별 등장 횟수를 bow에 저장합니다.
    try:
        bow = make_bow(args.file, args.encoding)
    except (OSError, UnicodeError, ValueError) as error:
        parser.error(str(error))  # 잘못된 경로나 닫히지 않은 수식을 알려 줍니다.
    # most_common()은 등장 횟수가 많은 순서대로 (단어, 횟수)를 제공합니다.
    # for 문은 각 쌍을 word와 count에 나눠 담으며 출력 작업을 반복합니다.
    for word, count in bow.most_common():
        # f 문자열의 중괄호 안에는 실제 값을 넣습니다.
        # \t는 단어와 횟수 사이에 넣는 탭 문자입니다.
        print(f"{word}\t{count}")


# 이 파일을 python BagOfWord.py ...로 직접 실행했을 때만 main()을 호출합니다.
# 다른 파이썬 파일에서 import BagOfWord로 불러올 때는 자동 실행하지 않습니다.
if __name__ == "__main__":
    main()
