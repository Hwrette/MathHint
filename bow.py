"""Kiwi로 텍스트 파일에서 명사 단어가방을 만듭니다.

설치: pip install kiwipiepy
실행: python bow.py sample.txt
"""

import argparse
from collections import Counter
from pathlib import Path

from kiwipiepy import Kiwi


def make_bow(file_path: str, encoding: str = "utf-8") -> Counter:
    text = Path(file_path).read_text(encoding=encoding)
    kiwi = Kiwi()
    return Counter(
        token.form
        for token in kiwi.tokenize(text)
        if token.tag in {"NNG", "NNP"}
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="텍스트 파일의 명사 빈도 계산")
    parser.add_argument("file", help="분석할 텍스트 파일 경로")
    parser.add_argument("--encoding", default="utf-8", help="파일 인코딩")
    args = parser.parse_args()

    bow = make_bow(args.file, args.encoding)
    for word, count in bow.most_common():
        print(f"{word}\t{count}")


if __name__ == "__main__":
    main()
