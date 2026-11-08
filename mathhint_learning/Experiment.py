"""한 실험이 사용할 데이터·모델·예측·출력 위치를 지정한다.

새 실험은 EXPERIMENT 한곳을 변경한다. 과거 모델을 새 실험에 자동 대입하지 않는다.
"""

from dataclasses import dataclass
import math
from pathlib import Path

from .TorchData import dataset_paths, file_hash, read_dataset, read_json

ROOT = Path(__file__).resolve().parents[1]
LEGACY_NAME = "model_comparison_2026-11-07"
# 신원 필드가 없던 최초 모델에만 허용하는, 게시·검증된 원본 바이트의 예외다.
LEGACY_MODEL_SHA256 = "d196bd3147db4acd0c91d8d9a6b5aaded5329e0860f9f8b74931f975dd19503e"
LEGACY_PREDICTIONS_SHA256 = "06ceb7eb8131ea6505b7f55a35724e354b6c6073275bbac4291f6fe8f0d6fd0a"
LEGACY_DATA_FINGERPRINT = "6e1cc73d9b4a712ff3a7b9916e14b9570373f92f6dae347ace711cb930e89035"


@dataclass(frozen=True)
class Experiment:
    name: str = "final_experiment"
    project_root: Path = ROOT
    data_root: Path | None = None
    result_root: Path | None = None
    checkpoint: Path | None = None
    predictions: Path | None = None
    epochs: int = 500
    learning_rate: float = .01
    seed: int = 42

    def __post_init__(self):
        if not self.name or self.name in (".", "..") or "/" in self.name or "\\" in self.name:
            raise ValueError("실험 이름은 경로가 아닌 한 개의 이름이어야 합니다.")
        project = Path(self.project_root).resolve()
        def resolve(value, default):
            path = Path(value) if value is not None else default
            return (path if path.is_absolute() else project / path).resolve()
        result = resolve(self.result_root, project / "results" / self.name)
        object.__setattr__(self, "project_root", project)
        object.__setattr__(self, "result_root", result)
        object.__setattr__(self, "data_root", resolve(self.data_root, project / "data"))
        object.__setattr__(self, "checkpoint", resolve(self.checkpoint, result / "02_regression/regression_model.pt"))
        object.__setattr__(self, "predictions", resolve(self.predictions, result / "02_regression/regression_predictions.json"))

    @property
    def regression_dir(self):
        return self.result_root / "02_regression"

    def as_dict(self):
        _, paths = dataset_paths(self.project_root, self.data_root)
        return {"name": self.name, "project_root": str(self.project_root), "data_root": str(self.data_root),
                "result_root": str(self.result_root), "checkpoint": str(self.checkpoint),
                "predictions": str(self.predictions), "epochs": self.epochs,
                "learning_rate": self.learning_rate, "seed": self.seed,
                "dataset_files": {key: str(path) for key, path in paths.items()}}


# 기존 결과를 읽는 기본값만 과거 모델을 명시적으로 선택한다.
EXPERIMENT = Experiment(checkpoint=ROOT / f"results/{LEGACY_NAME}/models/regression_model.pt",
                        predictions=ROOT / f"results/{LEGACY_NAME}/01_회귀모델/regression_predictions.json")


def _identity_matches(saved, current, path, data):
    if not isinstance(saved, dict):
        raise ValueError(f"{path}: data_identity가 없는 모델/예측은 새 실험에 사용할 수 없습니다.")
    for key, expected in current["files_sha256"].items():
        if saved.get("files_sha256", {}).get(key) != expected:
            raise ValueError(f"{path}: 데이터 파일 불일치: {data['paths'][key]}")
    if saved != current:
        raise ValueError(f"{path}: 데이터 식별 정보(generation/fingerprint)가 다릅니다.")


def _legacy_model(experiment, data, model_hash):
    manifest_path = experiment.project_root / f"results/{LEGACY_NAME}/manifest.json"
    manifest = read_json(manifest_path)["files"]
    if (model_hash != LEGACY_MODEL_SHA256
            or manifest.get("models/regression_model.pt") != model_hash
            or data["identity"]["fingerprint"] != LEGACY_DATA_FINGERPRINT):
        raise ValueError(f"{experiment.checkpoint}: 신원 필드가 없는 과거 모델은 검증된 원본 데이터와만 호환됩니다 ({manifest_path}).")
    return "frozen_legacy"


def load_checkpoint(experiment, data=None):
    """가중치 메타데이터를 검증한다. 이 함수는 학습·예측을 실행하지 않는다."""
    import torch
    data = data if data is not None else read_dataset(experiment.project_root, experiment.data_root)
    path = experiment.checkpoint
    checkpoint = torch.load(path, map_location="cpu", weights_only=True)
    for key, expected, source in [
        ("input_vocabulary", data["vocabularies"]["problems"], data["paths"]["problems_vocabulary"]),
        ("output_vocabulary", data["vocabularies"]["solutions"], data["paths"]["solutions_vocabulary"]),
        ("train_ids", data["ids"]["train"], data["paths"]["train_ids"]),
    ]:
        if checkpoint.get(key) != expected:
            raise ValueError(f"{path}: {key}의 내용 또는 순서가 다릅니다: {source}")
    if checkpoint.get("generation_id") != data["generation_id"]:
        raise ValueError(f"{path}: generation_id가 다릅니다: {data['paths']['metadata']}")
    model_hash = file_hash(path)
    if "data_identity" in checkpoint:
        _identity_matches(checkpoint["data_identity"], data["identity"], path, data)
        if checkpoint.get("test_ids") != data["ids"]["test"]:
            raise ValueError(f"{path}: 테스트 ID/행 순서가 다릅니다: {data['paths']['test_ids']}")
        validation = "data_identity"
    else:
        validation = _legacy_model(experiment, data, model_hash)
    state = checkpoint.get("model_state_dict", {})
    expected_shape = (len(data["vocabularies"]["solutions"]), len(data["vocabularies"]["problems"]))
    if "weight" not in state or tuple(state["weight"].shape) != expected_shape or tuple(state.get("bias", torch.empty(0)).shape) != (expected_shape[0],):
        raise ValueError(f"{path}: 모델 가중치 차원이 선택한 문제·해설 어휘와 다릅니다.")
    return {"data": data, "checkpoint": checkpoint, "model_sha256": model_hash, "validation": validation}


def validate_predictions(experiment):
    """API 준비에서 잘못된 데이터/모델의 예측을 섞지 않는다. 모델 재추론은 없다."""
    result = load_checkpoint(experiment)
    data, path = result["data"], experiment.predictions
    predictions = read_json(path)
    if predictions.get("model_sha256") != result["model_sha256"]:
        raise ValueError(f"{path}: 예측을 만든 체크포인트 SHA가 선택한 모델과 다릅니다: {experiment.checkpoint}")
    for key, expected in [("generation_id", data["generation_id"]), ("train_ids", data["ids"]["train"]),
                          ("vocabulary", data["vocabularies"]["solutions"])]:
        if predictions.get(key) != expected:
            raise ValueError(f"{path}: {key}의 내용 또는 순서가 선택한 데이터와 다릅니다.")
    if "data_identity" in predictions:
        _identity_matches(predictions["data_identity"], data["identity"], path, data)
        if predictions.get("input_vocabulary") != data["vocabularies"]["problems"]:
            raise ValueError(f"{path}: 입력 어휘의 내용 또는 순서가 다릅니다.")
    elif result["validation"] == "frozen_legacy":
        manifest_path = experiment.project_root / f"results/{LEGACY_NAME}/manifest.json"
        manifest = read_json(manifest_path)["files"]
        if file_hash(path) != LEGACY_PREDICTIONS_SHA256 or manifest.get("01_회귀모델/regression_predictions.json") != file_hash(path):
            raise ValueError(f"{path}: 검증된 과거 예측 파일의 SHA가 다릅니다 ({manifest_path}).")
    else:
        raise ValueError(f"{path}: data_identity가 없어 선택한 데이터와의 대응을 검증할 수 없습니다.")
    if "test_ids" in predictions and predictions["test_ids"] != data["ids"]["test"]:
        raise ValueError(f"{path}: 선언한 테스트 ID/순서가 다릅니다: {data['paths']['test_ids']}")
    documents = predictions.get("documents", [])
    if [doc.get("id") for doc in documents] != data["ids"]["test"]:
        raise ValueError(f"{path}: 테스트 ID/행 순서가 다릅니다: {data['paths']['test_ids']}")
    width = len(data["vocabularies"]["solutions"])
    for index, document in enumerate(documents):
        raw, clipped = document.get("raw_predicted_vector"), document.get("predicted_vector")
        if (not isinstance(raw, list) or not isinstance(clipped, list) or len(raw) != width or len(clipped) != width
                or any(type(v) not in (int, float) or not math.isfinite(v) for v in raw + clipped)):
            raise ValueError(f"{path}: {document.get('id')}의 예측 차원 또는 유한 실수 값이 잘못됐습니다.")
        if clipped != [max(0., value) for value in raw]:
            raise ValueError(f"{path}: {document['id']}의 음수 보정 정책이 다릅니다.")
        if document.get("actual_vector") != data["arrays"]["solutions"]["test"][index]:
            raise ValueError(f"{path}: {document['id']}의 실제 해설 벡터가 선택한 데이터와 다릅니다.")
    return {**result, "predictions": predictions, "predictions_sha256": file_hash(path)}
