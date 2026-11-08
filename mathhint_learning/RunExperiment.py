"""선택한 실험의 읽기·평가·학습·API 준비를 연결하는 얇은 실행기.

기본은 view다. generate를 명시한 경우에만 외부 API를 호출한다.
설정은 Experiment.py의 EXPERIMENT 한곳에서 선택한다.
"""

from dataclasses import replace
import json
from pathlib import Path
import sys

from .Experiment import EXPERIMENT, Experiment, LEGACY_DATA_FINGERPRINT
from .TorchData import file_hash, read_dataset, read_json

ACTIONS = ("view", "evaluate", "train", "prepare", "generate")


def _write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _relocated(path, stored, experiment):
    path = Path(path)
    for old, current in ((Path(stored["result_root"]), experiment.result_root),
                         (Path(stored["project_root"]), experiment.project_root)):
        try:
            return current / path.relative_to(old)
        except ValueError:
            pass
    return path


def _logical_path(path, settings):
    path = Path(path)
    for key in ("result_root", "project_root"):
        try:
            return key, str(path.relative_to(Path(settings[key])))
        except ValueError:
            pass
    return "absolute", str(path)


def verify_saved_data(run_root, data, *, project_root):
    """보고서도 모델을 읽지 않고 저장 당시의 어휘·행·분할 신원을 대조한다."""
    run_root, project_root = Path(run_root), Path(project_root)
    evidence = []
    binding = run_root / "experiment.json"
    provenance = run_root / "02_regression/provenance.json"
    config = run_root / "03_gemini/config.json"
    for path in (binding, provenance, config):
        if path.exists():
            value = read_json(path)
            value = value.get("config", value)
            if value.get("data_identity"):
                evidence.append((path, value["data_identity"]))
    for path, identity in evidence:
        if identity != data["identity"]:
            raise ValueError(f"{path}: 선택한 데이터/어휘/행 순서/분할이 저장 결과와 다릅니다: {data['data_root']}")
    if evidence:
        return
    # 신원 필드가 없던 최종 연구만 알려진 전체 데이터 해시로 복원한다.
    canonical = run_root.resolve() == (project_root / "results/final_experiment").resolve()
    has_results = any((run_root / p).exists() for p in (
        "01_clustering/summary.csv", "02_regression/summary.csv", "02_regression/vectors.json",
        "03_gemini/config.json", "03_gemini/responses.jsonl"))
    if canonical and has_results and data["identity"]["fingerprint"] == LEGACY_DATA_FINGERPRINT:
        return
    if has_results:
        raise ValueError(f"{run_root}: 저장 결과의 전체 데이터 신원을 확인할 수 없습니다. experiment.json 또는 provenance.json의 data_identity가 필요합니다: {data['data_root']}")


def _existing_binding(experiment, *, action):
    """저장된 결과의 데이터와 선택 설정이 다른 경우 조용히 과거 모델로 돌아가지 않는다."""
    path = experiment.result_root / "experiment.json"
    data = read_dataset(experiment.project_root, experiment.data_root)
    verify_saved_data(experiment.result_root, data, project_root=experiment.project_root)
    if not path.exists():
        provenance = experiment.regression_dir / "provenance.json"
        config = experiment.result_root / "03_gemini/config.json"
        for source_record in (provenance, config):
            if not source_record.exists():
                continue
            value = read_json(source_record)
            value = value.get("config", value)
            for key, fields, legacy_field in (("checkpoint", ("model_sha256", "checkpoint_sha256"), "models/regression_model.pt"),
                                              ("predictions", ("prediction_sha256", "predictions_sha256"), "01_회귀모델/regression_predictions.json")):
                expected = next((value[field] for field in fields if value.get(field)), None) or value.get("source_sha256", {}).get(legacy_field)
                source = getattr(experiment, key)
                if expected and source.exists() and file_hash(source) != expected:
                    raise ValueError(f"{source_record}: 선택한 {key} 파일이 저장 결과를 만든 파일과 다릅니다: {source}")
        return experiment, data, None
    record = read_json(path)
    if record["data_identity"] != data["identity"]:
        raise ValueError(f"{path}: 선택한 데이터/어휘/분할이 저장 실험과 다릅니다: {experiment.data_root}")
    selected, current = record["selected"], experiment.as_dict()
    if selected["name"] != current["name"]:
        raise ValueError(f"{path}: 실험 이름이 다릅니다. 별도 결과 경로를 사용하세요.")
    for key in ("checkpoint", "predictions"):
        if _logical_path(current[key], current) != _logical_path(selected[key], selected):
            raise ValueError(f"{path}: 선택한 {key}가 저장 실험과 다릅니다. 다른 모델/예측은 별도 실험 경로를 사용하세요.")
    artifacts = record.get("artifacts", {})
    bound = replace(experiment,
        checkpoint=_relocated(artifacts.get("checkpoint", selected["checkpoint"]), selected, experiment),
        predictions=_relocated(artifacts.get("predictions", selected["predictions"]), selected, experiment))
    for key in ("checkpoint", "predictions"):
        source = getattr(bound, key)
        expected = artifacts.get(key + "_sha256")
        if expected and source.exists() and file_hash(source) != expected:
            raise ValueError(f"{path}: 저장 결과의 {key} 파일 SHA가 바뀌었습니다: {source}")
        if (action in ("prepare", "generate") or (action == "evaluate" and key == "checkpoint")) and not source.exists():
            raise FileNotFoundError(f"{path}: 필요한 {key} 파일이 없습니다: {source}")
    return bound, data, record


def _save_binding(selected, effective, data, action):
    artifacts = {key: str(getattr(effective, key)) for key in ("checkpoint", "predictions")}
    for key in ("checkpoint", "predictions"):
        path = getattr(effective, key)
        artifacts[key + "_sha256"] = file_hash(path) if path.is_file() else None
    # 읽기용 복사본에 모델 원본이 빠져도 저장 당시의 알려진 SHA를 버리지 않는다.
    for source_record in (selected.regression_dir / "provenance.json", selected.result_root / "03_gemini/config.json"):
        if source_record.exists():
            value = read_json(source_record)
            value = value.get("config", value)
            for key, fields, legacy_field in (("checkpoint", ("model_sha256", "checkpoint_sha256"), "models/regression_model.pt"),
                                              ("predictions", ("prediction_sha256", "predictions_sha256"), "01_회귀모델/regression_predictions.json")):
                expected = next((value[field] for field in fields if value.get(field)), None) or value.get("source_sha256", {}).get(legacy_field)
                if artifacts[key + "_sha256"] is None and expected:
                    artifacts[key + "_sha256"] = expected
    binding_path = selected.result_root / "experiment.json"
    if action == "view" and binding_path.exists():
        return
    _write(binding_path, {
        "schema_version": 1, "selected": selected.as_dict(), "data_identity": data["identity"],
        "artifacts": artifacts, "last_action": action,
        "note": "view reads saved results only; model evaluation and API execution require explicit actions.",
    })


def prepare_experiment(experiment, *, generate=False):
    """모델·데이터·예측 연결을 검증하고 필요할 때만 실제 API 실행으로 넘어간다."""
    from .Experiment import validate_predictions
    from mathhint_solver import ThreeWayGeneration as three
    checked = validate_predictions(experiment)
    config, plan = three.prepare_plan(experiment.project_root, experiment.predictions,
                                     data_root=experiment.data_root)
    output = experiment.result_root / "03_gemini"
    # 새 실험은 모델 신원도 캐시에 포함한다. 이미 게시한 frozen 요청은 바꾸지 않는다.
    saved_config = read_json(output / "config.json")["config"] if (output / "config.json").exists() else None
    if saved_config is None or "data_identity" in saved_config:
        config.update(data_identity=checked["data"]["identity"], checkpoint_sha256=checked["model_sha256"])
    legacy = experiment.project_root / "results/model_comparison_2026-11-07/03_Gemini비교"
    source_config = legacy / "실험설정.json" if checked["validation"] == "frozen_legacy" else None
    source_records = legacy / "원본응답_160개.jsonl" if source_config else None
    preflight = three.prepare(output, config, plan, source_config_path=source_config, source_records_path=source_records,
                             project=experiment.project_root, data_root=experiment.data_root)
    if generate and preflight["new_calls_needed"]:
        from dotenv import load_dotenv
        import os
        load_dotenv(experiment.project_root / ".env", override=False)
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY가 필요합니다. 입력 준비는 저장했고 실제 API는 호출하지 않았습니다.")
        three.run_experiment(output, config, plan, api_key=key, project=experiment.project_root,
                             data_root=experiment.data_root)
    return preflight


def run(action="view", experiment=None, *, make_figures=True):
    if action not in ACTIONS:
        raise ValueError("작업은 " + ", ".join(ACTIONS) + " 중 하나여야 합니다.")
    selected = experiment if experiment is not None else EXPERIMENT
    print(json.dumps({"action": action, "selected_experiment": selected.as_dict()}, ensure_ascii=False, indent=2))
    if action == "train":
        # 회귀 폴더가 비어 있어도 같은 결과 경로의 기존 생성·데이터 기록을 덮지 않는다.
        _existing_binding(selected, action=action)
        from .TorchRegression import train_for_experiment
        result = train_for_experiment(selected, make_figures=make_figures)
        effective = replace(selected, checkpoint=Path(result["checkpoint"]), predictions=Path(result["predictions"]))
        data = read_dataset(selected.project_root, selected.data_root)
    else:
        if action == "view" and not selected.result_root.exists():
            raise FileNotFoundError(f"결과 폴더가 없습니다: {selected.result_root}")
        effective, data, _ = _existing_binding(selected, action=action)
        if action == "evaluate":
            from .VectorComparison import evaluate_for_experiment
            result = evaluate_for_experiment(effective, make_figures=make_figures)
            effective = replace(effective, checkpoint=Path(result["checkpoint"]), predictions=Path(result["predictions"]))
        elif action in ("prepare", "generate"):
            result = prepare_experiment(effective, generate=action == "generate")
        else:
            result = None
    _save_binding(selected, effective, data, action)
    from mathhint_analysis.AnalyzeThreeWay import build_report
    report = build_report(selected.result_root, project_root=selected.project_root, data_root=selected.data_root)
    return {"action": action, "experiment": effective.as_dict(), "result": result, "report": report}


def main():
    if len(sys.argv) > 2:
        raise SystemExit("python -m mathhint_learning.RunExperiment [view|evaluate|train|prepare|generate]")
    run(sys.argv[1] if len(sys.argv) == 2 else "view")


if __name__ == "__main__":
    main()
