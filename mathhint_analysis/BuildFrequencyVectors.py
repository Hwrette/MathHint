"""TXT 폴더를 공통 어휘 순서의 빈도 벡터로 바꾼다.

INPUT·OUTPUT·VOCABULARY를 바꾸고 실행한다.
학습/테스트 분할까지 만들 때는 PrepareDataset.py를 사용한다.
"""

import json  # 파이썬 리스트와 딕셔너리를 JSON 파일로 저장하고 읽습니다.
from pathlib import Path  # 파일·폴더 경로를 다룹니다.

# 이미 만든 분석 함수를 가져옵니다. 이 파일에서 토큰화 규칙을 다시 만들지 않습니다.
# 파일 직접 실행과 python -m 실행에서 모두 같은 분석 함수를 사용합니다.
if __package__:
    from .BagOfWord import Kiwi, count_tokens
else:
    from BagOfWord import Kiwi, count_tokens


# 저장된 학습 어휘를 사용하므로 테스트 문항에서 어휘가 늘어나지 않는다.
ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data/processed/problems"
OUTPUT = ROOT / "outputs/frequency_vectors"
VOCABULARY = ROOT / "data/vectors/problems/vocabulary.json"
INCLUDE_SUBFOLDERS = False
ENCODING = "utf-8-sig"


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


def main():
    vocabulary = None
    if VOCABULARY is not None:
        vocabulary = json.loads(Path(VOCABULARY).read_text(encoding="utf-8-sig"))
    result = build_frequency_vectors(
        INPUT, vocabulary=vocabulary, recursive=INCLUDE_SUBFOLDERS, encoding=ENCODING,
    )
    vocabulary_path, vectors_path = save_results(result, OUTPUT)
    print(f"문항 {result['shape'][0]}개 × 어휘 {result['shape'][1]}개")
    print(f"어휘: {vocabulary_path}")
    print(f"빈도 벡터: {vectors_path}")


if __name__ == "__main__":
    main()
