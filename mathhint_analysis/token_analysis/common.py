"""토큰 분석의 읽기와 새 결과 저장만 담당한다. 원본 파일은 쓰지 않는다."""

import csv
import hashlib
import json
from pathlib import Path

import numpy as np

from mathhint_learning.TorchData import read_dataset

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "results/token_analysis"


def load_data(root=ROOT):
    data = read_dataset(root)
    data["arrays"] = {region: {part: np.asarray(rows, dtype=np.int64)
                               for part, rows in splits.items()}
                      for region, splits in data["arrays"].items()}
    return data


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _plain(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"JSON에 저장할 수 없는 값: {type(value).__name__}")


def dump_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2,
                                    allow_nan=False, default=_plain) + "\n", encoding="utf-8")
    temporary.replace(path)


def dump_csv(path, rows, fields=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(rows)
    fields = list(fields or (rows[0] if rows else []))
    if not fields:
        raise ValueError(f"빈 CSV에도 열 이름이 필요합니다: {path}")
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def review_files(output):
    """처음에만 빈 선택 파일을 만든다. 사용자가 작성한 목록을 덮어쓰지 않는다."""
    paths = [Path(output) / f"stopwords/{region}_stopwords.json"
             for region in ("problem", "solution")]
    for path in paths:
        if not path.exists():
            dump_json(path, [])
        values = read_json(path)
        if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
            raise ValueError(f"사용자 선택 목록은 문자열 배열이어야 합니다: {path}")
    return paths
