"""Kiwi로 텍스트 파일에서 명사 단어가방을 만듭니다.

설치: pip install kiwipiepy
실행: python bow.py sample.txt

예를 들어 sample.txt에 '사과와 바나나를 샀다. 사과는 맛있다.'가 있으면
명사인 '사과'는 2번, '바나나'는 1번 등장했다고 출력합니다.
단어가방(BoW)은 문장 속 단어의 순서를 버리고 등장 횟수만 저장하는 방식입니다.
"""

# argparse: 터미널에서 입력한 파일 경로와 옵션을 읽는 파이썬 기본 도구입니다.
import argparse
# Counter: 단어별로 몇 번 등장했는지 세어 주는 파이썬 기본 도구입니다.
from collections import Counter
# Path: 파일 경로를 다루고 파일 내용을 읽을 때 사용하는 기본 도구입니다.
from pathlib import Path

# Kiwi: 한국어 문장을 작은 의미 단위인 '형태소'로 나누고 품사를 알아냅니다.
# 파이썬 기본 기능이 아니므로 위의 pip install 명령으로 설치해야 합니다.
from kiwipiepy import Kiwi


def make_bow(file_path: str, encoding: str = "utf-8") -> Counter:
    """파일에서 명사만 골라 단어별 등장 횟수를 돌려줍니다.

    file_path는 읽을 파일의 경로입니다. encoding은 글자를 해석하는 방식이며,
    따로 지정하지 않으면 UTF-8을 사용합니다. 파일 인코딩과 맞아야 한글이
    제대로 읽힙니다. 오래된 한글 파일이라면 cp949가 필요할 수도 있습니다.

    매개변수 뒤의 ': str'과 끝의 '-> Counter'는 값의 종류를 알려주는
    타입 힌트입니다. 각각 문자열을 받고 Counter를 돌려준다는 뜻입니다.
    """
    # 파일 전체를 읽어 하나의 문자열로 저장합니다.
    # 파일을 찾지 못하거나 인코딩이 맞지 않으면 이 줄에서 오류가 납니다.
    text = Path(file_path).read_text(encoding=encoding)
    # 실제 형태소 분석을 담당할 Kiwi 객체를 만듭니다.
    kiwi = Kiwi()
    # tokenize(text)는 문장을 분석해 형태소 정보(token)를 차례로 제공합니다.
    # token.form은 형태소의 글자, token.tag는 품사 코드입니다.
    # NNG는 일반 명사(사과 등), NNP는 고유 명사(사람 이름, 지명 등)입니다.
    # if 조건에 맞는 명사만 Counter에 전달해 단어별 횟수를 셉니다.
    # return은 계산한 결과를 이 함수를 호출한 곳으로 돌려줍니다.
    return Counter(
        token.form
        for token in kiwi.tokenize(text)
        if token.tag in {"NNG", "NNP"}
    )


def main() -> None:
    """사용자의 터미널 입력을 받아 분석하고 결과를 화면에 출력합니다.

    -> None은 이 함수가 별도의 결과값을 돌려주지 않는다는 뜻입니다.
    """
    # 입력 규칙을 정합니다. python bow.py --help로 사용법을 볼 수 있습니다.
    parser = argparse.ArgumentParser(description="텍스트 파일의 명사 빈도 계산")
    # file은 필수 입력입니다. 예: python bow.py sample.txt
    # 상대 경로(sample.txt)는 터미널의 현재 작업 폴더를 기준으로 찾습니다.
    parser.add_argument("file", help="분석할 텍스트 파일 경로")
    # --encoding은 선택 사항입니다. 생략하면 utf-8을 사용합니다.
    # 예: python bow.py sample.txt --encoding cp949
    parser.add_argument("--encoding", default="utf-8", help="파일 인코딩")
    # 입력을 해석한 결과를 args에 담습니다.
    args = parser.parse_args()

    # 위에서 만든 함수를 호출하고 단어별 등장 횟수를 bow에 저장합니다.
    bow = make_bow(args.file, args.encoding)
    # most_common()은 등장 횟수가 많은 순서대로 (단어, 횟수)를 제공합니다.
    # for 문은 각 쌍을 word와 count에 나눠 담으며 출력 작업을 반복합니다.
    for word, count in bow.most_common():
        # f 문자열의 중괄호 안에는 실제 값을 넣습니다.
        # \t는 단어와 횟수 사이에 넣는 탭 문자입니다.
        print(f"{word}\t{count}")


# 이 파일을 python bow.py ...로 직접 실행했을 때만 main()을 호출합니다.
# 다른 파이썬 파일에서 import bow로 불러올 때는 자동 실행하지 않습니다.
if __name__ == "__main__":
    main()
