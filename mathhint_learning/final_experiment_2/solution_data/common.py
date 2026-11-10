"""지도학습 후속 실험의 공통 경로·원자적 파일 저장."""

from pathlib import Path

from mathhint_analysis.token_analysis.common import dump_csv as write_csv, dump_json as write_json
from mathhint_learning.TorchData import file_hash, identity_digest as fingerprint, read_json

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / "results/final_experiment_2/solution_data"


def check_hashes(root, hashes):
    root = Path(root)
    changed = [name for name, digest in hashes.items()
               if not (root / name).is_file() or file_hash(root / name) != digest]
    if changed:
        raise ValueError("연결된 데이터/선택 목록/기존 결과가 변경되었습니다: " + ", ".join(changed[:12]))


def verify_frozen_model(root, model_name, dataset_id):
    """두 모델의 API 사용 전 게이트에 사용할 고정 모델·예측 신원 확인."""
    folder = Path(root) / "results/final_experiment_2" / model_name
    manifest = read_json(folder / "model_manifest.json")
    if not manifest.get("frozen") or not manifest.get("frozen_before_test") or manifest["dataset_id"] != dataset_id:
        raise ValueError(f"{model_name}: 확정되지 않았거나 다른 데이터의 모델입니다.")
    for kind in ("checkpoint", "predictions"):
        info = manifest[kind]
        if file_hash(folder / info["path"]) != info["sha256"]:
            raise ValueError(f"{model_name}: {kind} 파일/해시가 확정본과 다릅니다.")
    return manifest
