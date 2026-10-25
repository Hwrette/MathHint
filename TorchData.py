"""저장된 빈도벡터 JSON을 PyTorch 행렬로 읽는 공통 코드입니다.

텍스트를 분석하거나 빈도벡터를 새로 만들지는 않습니다.
한 행은 파일 하나, 한 열은 vocabulary.json의 토큰 하나에 대응합니다.
"""

import json
import math
from pathlib import Path

import torch


def load_frequency_matrix(path: str | Path) -> tuple[list[str], torch.Tensor, list[str]]:
    """파일명 목록, 빈도행렬, 토큰 목록을 같은 순서로 돌려줍니다.

    BuildFrequencyVectors.py가 저장한 frequency_vectors.json과 그 옆의
    vocabulary.json을 읽습니다. float32는 학습 계산에 사용할 실수 자료형입니다.
    """
    path = Path(path).expanduser().resolve()
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"빈도벡터 JSON은 객체여야 합니다: {path}")
    vocabulary_file = data.get("vocabulary_file")
    documents = data.get("documents")
    if not isinstance(vocabulary_file, str) or not vocabulary_file:
        raise ValueError(f"vocabulary_file 경로가 없습니다: {path}")
    vocabulary_path = path.parent / vocabulary_file
    vocabulary = json.loads(vocabulary_path.read_text(encoding="utf-8-sig"))
    if (not isinstance(vocabulary, list) or not vocabulary
            or any(not isinstance(token, str) for token in vocabulary)):
        raise ValueError(f"어휘 목록에는 문자열 토큰이 하나 이상 필요합니다: {vocabulary_path}")
    if len(set(vocabulary)) != len(vocabulary):
        raise ValueError(f"어휘 목록에 중복 토큰이 있습니다: {vocabulary_path}")
    if not isinstance(documents, list) or not documents:
        raise ValueError(f"빈도벡터에 파일이 하나 이상 필요합니다: {path}")

    files = []
    rows = []
    for document in documents:
        if not isinstance(document, dict):
            raise ValueError(f"documents의 각 항목은 객체여야 합니다: {path}")
        file = document.get("file")
        vector = document.get("vector")
        if not isinstance(file, str) or not file or file in files:
            raise ValueError(f"파일명이 비어 있거나 중복됩니다: {file!r}")
        if not isinstance(vector, list) or len(vector) != len(vocabulary):
            raise ValueError(f"{file}: 벡터 길이가 어휘 목록의 길이와 다릅니다.")
        if any(isinstance(value, bool) or not isinstance(value, (int, float))
               or not math.isfinite(value) or value < 0 for value in vector):
            raise ValueError(f"{file}: 빈도는 0 이상의 유한한 숫자여야 합니다.")
        files.append(file)
        rows.append(vector)

    if data.get("shape") != [len(rows), len(vocabulary)]:
        raise ValueError(f"shape에 적힌 행렬 크기가 실제 데이터와 다릅니다: {path}")
    # 리스트들을 행으로 쌓습니다. 예: 파일 50개 × 토큰 300개 → [50, 300].
    matrix = torch.tensor(rows, dtype=torch.float32)
    if not torch.isfinite(matrix).all():
        raise ValueError(f"빈도 값이 float32 범위를 넘었습니다: {path}")
    return files, matrix, vocabulary


def load_paired_matrices(
    problems_path: str | Path, solutions_path: str | Path,
) -> tuple[list[str], torch.Tensor, torch.Tensor, list[str], list[str]]:
    """문제 X와 해설 Y를 파일명으로 짝지어 같은 행 순서로 돌려줍니다.

    두 JSON의 행 순서는 달라도 됩니다. 예를 들어 문제의 001.txt는 해설의
    001.txt와 짝짓습니다. 각 폴더 기준 상대 경로 전체가 같아야 하므로,
    서로 다른 하위 폴더의 동명 파일을 임의로 연결하지 않습니다.
    """
    files, X, problem_vocabulary = load_frequency_matrix(problems_path)
    solution_files, solution_matrix, solution_vocabulary = load_frequency_matrix(solutions_path)
    missing = sorted(set(files) - set(solution_files))
    extra = sorted(set(solution_files) - set(files))
    if missing or extra:
        raise ValueError(f"문제·해설 파일명이 일치하지 않습니다. 해설 없음: {missing}, 문제 없음: {extra}")

    # 정렬 순서로 추측하지 않고, 파일명으로 해설 행의 위치를 찾아 재배열합니다.
    solution_index = {file: index for index, file in enumerate(solution_files)}
    Y = solution_matrix[[solution_index[file] for file in files]]
    # 문제와 해설이 서로 다른 어휘 목록을 사용해도 X의 열 수와 Y의 열 수를
    # 따로 기록하므로 학습할 수 있습니다. 각 목록 안의 인덱스는 그대로 유지합니다.
    return files, X, Y, problem_vocabulary, solution_vocabulary
