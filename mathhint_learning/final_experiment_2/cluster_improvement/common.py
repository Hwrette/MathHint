"""이번 실험의 경로와 작은 파일 입출력. 기존 데이터에는 쓰지 않는다."""

import csv
from pathlib import Path

from ...TorchData import file_hash, identity_digest, read_json, write_json

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / "results/final_experiment_2/cluster_improvement"
def fingerprint(value):
    return identity_digest(value)


def write_csv(path, rows, fields=None):
    rows = list(rows)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(fields or (rows[0] if rows else []))
    if not fields:
        raise ValueError(f"빈 표에는 열 이름이 필요합니다: {path}")
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def check_hashes(root, hashes):
    changed = [name for name, digest in hashes.items()
               if not (Path(root) / name).is_file() or file_hash(Path(root) / name) != digest]
    if changed:
        raise ValueError("입력·보호 파일이 변경되었습니다: " + ", ".join(changed[:10]))


def output_path(root=ROOT, output=None):
    expected = Path(root).resolve() / "results/final_experiment_2/cluster_improvement"
    selected = Path(output).resolve() if output is not None else expected
    if selected != expected:
        raise ValueError(f"이번 실험의 출력은 {expected}여야 합니다: {selected}")
    return selected
