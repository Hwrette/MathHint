"""폴더 안의 텍스트에서 공통 토큰 목록과 파일별 빈도벡터를 만듭니다.

설치: python -m pip install kiwipiepy
실행: python BuildFrequencyVectors.py
폴더 지정: python BuildFrequencyVectors.py "문제텍스트폴더"

한국어는 Kiwi, LaTeX는 기존 BagOfWord.py의 정규식으로 분석합니다.
불용어 제거·품사 필터·숫자 치환 없이 나온 토큰을 모두 사용합니다.
"""

import argparse  # 터미널에서 받은 폴더 경로와 옵션을 해석합니다.
import json  # 파이썬 리스트와 딕셔너리를 JSON 파일로 저장하고 읽습니다.
from pathlib import Path  # 파일·폴더 경로를 다룹니다.

# 이미 만든 분석 함수를 가져옵니다. 이 파일에서 토큰화 규칙을 다시 만들지 않습니다.
from BagOfWord import Kiwi, count_tokens


# ▶ 버튼으로 실행할 때는 여기만 원하는 폴더 경로로 바꾸면 됩니다.
# 예: INPUT_FOLDER = "outputs/run01/문서폴더/problems"
# 예: INPUT_FOLDER = "/Users/hwrette/Desktop/문제텍스트"
# 처음에는 저장소에 포함된 예제 폴더로 실행되도록 설정했습니다.
INPUT_FOLDER = "examples"
OUTPUT_FOLDER = "outputs/frequency_vectors"

# True이면 하위 폴더의 텍스트까지 읽고, False이면 지정 폴더 바로 안만 읽습니다.
INCLUDE_SUBFOLDERS = False


def build_frequency_vectors(
    input_folder: str | Path,
    *,
    vocabulary: list[str] | None = None,
    recursive: bool = False,
    encoding: str = "utf-8-sig",
    kiwi: Kiwi | None = None,
) -> dict:
    """파일별 빈도를 모아 공통 인덱스에 맞춘 벡터를 돌려줍니다.

    vocabulary가 None이면 이번 파일들의 토큰 합집합으로 새 목록을 만듭니다.
    목록을 전달하면 그 순서와 길이를 유지하고, 없는 토큰은 무시합니다.
    * 뒤의 옵션은 recursive=True처럼 이름을 붙여 전달해야 합니다.
    """
    folder = Path(input_folder).expanduser().resolve()
    if not folder.is_dir():
        raise ValueError(f"입력 폴더를 찾을 수 없습니다: {folder}")

    # 저장해 둔 어휘를 사용할 때 잘못된 파일로 인덱스가 바뀌는 것을 막습니다.
    if vocabulary is not None:
        if not isinstance(vocabulary, list) or any(not isinstance(t, str) for t in vocabulary):
            raise ValueError("어휘 목록은 문자열로 이루어진 JSON 리스트여야 합니다.")
        if len(vocabulary) != len(set(vocabulary)):
            raise ValueError("어휘 목록에 중복 토큰이 있습니다.")

    # .txt와 .TXT를 모두 읽습니다. 하위 폴더 포함 여부는 recursive로 정합니다.
    candidates = folder.rglob("*") if recursive else folder.iterdir()
    files = sorted(
        (path for path in candidates if path.is_file() and path.suffix.lower() == ".txt"),
        key=lambda path: path.relative_to(folder).as_posix(),
    )
    if not files:
        raise ValueError(f"분석할 .txt 파일이 없습니다: {folder}")

    # Kiwi의 초기화는 시간이 걸리므로 모든 파일에서 한 객체를 공유합니다.
    if kiwi is None:
        kiwi = Kiwi()

    documents = []
    counts_per_file = []
    all_tokens = set()  # set은 중복을 허용하지 않으므로 합집합을 만들 때 사용합니다.
    for path in files:
        try:
            # utf-8-sig는 일반 UTF-8과 BOM이 붙은 UTF-8을 모두 읽습니다.
            text = path.read_text(encoding=encoding)
            counts = count_tokens(text, kiwi)
        except (OSError, UnicodeError, ValueError) as error:
            # 실패한 파일을 조용히 빼지 않습니다. 어느 파일인지 알려 주고 중단합니다.
            raise ValueError(f"{path}: {error}") from error

        # Kiwi 분석 결과를 보관하므로 벡터를 만들 때 파일을 다시 분석하지 않습니다.
        counts_per_file.append(counts)
        documents.append({"file": path.relative_to(folder).as_posix()})
        all_tokens.update(counts.keys())

    if vocabulary is None:
        # 토큰을 정렬하면 같은 데이터에서는 항상 같은 인덱스가 만들어집니다.
        # 리스트의 0번째 토큰은 모든 벡터의 0번째 칸에 대응합니다.
        vocabulary = sorted(all_tokens)
    else:
        # 이미 정한 어휘는 정렬하거나 늘리지 않습니다. 전달된 리스트도 수정하지 않습니다.
        vocabulary = list(vocabulary)
    token_to_index = {token: index for index, token in enumerate(vocabulary)}

    for document, counts in zip(documents, counts_per_file):
        # 처음에는 모든 칸이 0입니다. 해당 파일에 있는 토큰의 칸만 채웁니다.
        vector = [0] * len(vocabulary)
        ignored = 0
        for token, count in counts.items():
            index = token_to_index.get(token)
            if index is None:
                # 새 문제에 처음 나온 토큰은 기존 벡터에 칸이 없으므로 제외합니다.
                ignored += count
            else:
                # index가 0인 경우도 정상 인덱스이므로 if index로 검사하면 안 됩니다.
                vector[index] = count
        document["vector"] = vector
        document["token_count"] = sum(counts.values())
        document["ignored_token_count"] = ignored

    return {
        "input_folder": str(folder),
        "vocabulary": vocabulary,
        "shape": [len(documents), len(vocabulary)],  # [파일 수, 토큰 종류 수]
        "documents": documents,
    }


def save_results(result: dict, output_folder: str | Path) -> tuple[Path, Path]:
    """공통 리스트와 파일별 벡터를 각각 JSON 파일로 저장합니다."""
    folder = Path(output_folder).expanduser().resolve()
    folder.mkdir(parents=True, exist_ok=True)
    vocabulary_path = folder / "vocabulary.json"
    vectors_path = folder / "frequency_vectors.json"

    # ensure_ascii=False는 한글을 읽을 수 있는 모양으로 저장합니다.
    # indent=2는 들여쓰기를 넣습니다. 결과 파일은 다시 실행하면 갱신됩니다.
    vocabulary_path.write_text(
        json.dumps(result["vocabulary"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    vectors_path.write_text(
        json.dumps(
            {
                "vocabulary_file": vocabulary_path.name,
                "input_folder": result["input_folder"],
                "shape": result["shape"],
                "documents": result["documents"],
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    return vocabulary_path, vectors_path


def main() -> None:
    """설정한 폴더를 분석하고, 저장 위치와 벡터 크기를 터미널에 출력합니다."""
    script_folder = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="폴더의 한국어·LaTeX 토큰 목록과 빈도벡터 생성")
    # nargs='?'이므로 폴더 입력을 생략해도 됩니다. ▶ 실행 시 위의 설정을 사용합니다.
    parser.add_argument("folder", nargs="?", type=Path, help="분석할 텍스트 폴더")
    parser.add_argument("-o", "--output", type=Path, help="결과를 저장할 폴더")
    parser.add_argument("--recursive", action="store_true", help="하위 폴더의 .txt도 포함")
    parser.add_argument("--encoding", default="utf-8-sig", help="텍스트 파일 인코딩")
    parser.add_argument("--vocabulary", type=Path, help="새 문제에 사용할 기존 vocabulary.json")
    args = parser.parse_args()

    # 코드 위의 설정값은 이 파이썬 파일을 기준으로 찾습니다. ~는 먼저 사용자 폴더로 바꿉니다.
    # 터미널에서 직접 지정한 상대 경로는 터미널의 현재 폴더를 기준으로 찾습니다.
    input_folder = args.folder if args.folder is not None else script_folder / Path(INPUT_FOLDER).expanduser()
    output_folder = args.output if args.output is not None else script_folder / Path(OUTPUT_FOLDER).expanduser()
    try:
        vocabulary = None
        if args.vocabulary is not None:
            vocabulary = json.loads(args.vocabulary.expanduser().read_text(encoding="utf-8-sig"))
            # JSON의 null이 '새 어휘 생성'으로 오인되지 않도록 목록인지 먼저 검사합니다.
            if not isinstance(vocabulary, list):
                raise ValueError("vocabulary.json은 JSON 리스트여야 합니다.")

        print(f"입력 폴더: {input_folder.expanduser().resolve()}", flush=True)
        print("텍스트 파일 분석 중...", flush=True)
        result = build_frequency_vectors(
            input_folder,
            vocabulary=vocabulary,
            recursive=args.recursive or INCLUDE_SUBFOLDERS,
            encoding=args.encoding,
        )
        vocabulary_path, vectors_path = save_results(result, output_folder)
    except (OSError, UnicodeError, ValueError) as error:
        parser.error(str(error))

    file_count, token_count = result["shape"]
    print(f"분석한 파일: {file_count}개")
    print(f"공통 토큰 목록: {token_count}개")
    print(f"빈도벡터 크기: {file_count}행 × {token_count}열")
    print(f"토큰 목록 저장: {vocabulary_path}")
    print(f"빈도벡터 저장: {vectors_path}")
    if args.vocabulary is not None:
        ignored = sum(doc["ignored_token_count"] for doc in result["documents"])
        print(f"기존 목록에 없어 제외한 토큰의 등장 횟수: {ignored}")


# import로 가져왔을 때는 실행하지 않고, 직접 실행했을 때만 시작합니다.
if __name__ == "__main__":
    main()
