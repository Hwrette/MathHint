"""1단계 분석·저장 결과 표시·검증을 구분한다. 모델 실행 명령은 없다."""

from importlib.metadata import version
from pathlib import Path
import sys

from .common import ROOT, dump_json, load_data, read_json, review_files, sha256
from .validation import verify_analysis, verify_sources


def prepare_config(root, output):
    path = output / "config.json"
    if path.exists():
        config = read_json(path)
        verify_sources(root, config)
        return config
    data = load_data(root)
    if [len(data["ids"][p]) for p in ("train", "test")] != [185, 80] or [len(data["vocabularies"][r]) for r in ("problems", "solutions")] != [346, 431]:
        raise ValueError("기존265문항·고정185/80분할·346/431어휘와 다릅니다.")
    protected = {}
    for folder in (root / "data", root / "results/final_experiment", root / "results/model_comparison_2026-11-07"):
        protected.update({file.relative_to(root).as_posix(): sha256(file)
                          for file in folder.rglob("*") if file.is_file()})
    for name in ("mathhint_analysis/BagOfWord.py", "mathhint_analysis/PrepareDataset.py",
                 "mathhint_learning/TorchKMeans.py", "mathhint_learning/TorchData.py"):
        protected[name] = sha256(root / name)
    config = {"analysis": "token_statistics_stage1_user_review_v1", "data_identity": data["identity"],
              "counts": {"train": 185, "test": 80, "total": 265, "problem_vocabulary": 346, "solution_vocabulary": 431},
              "classification_scope": "train185 only", "unlabelled_all_token_moments_scope": "all265",
              "variance_ddof": 0, "stopwords_auto_selected": False,
              "model_execution_allowed": False, "gemini_calls_allowed": False,
              "protected_files_sha256": protected,
              "packages": {name: version(name) for name in ("numpy", "matplotlib", "kiwipiepy", "kiwipiepy-model")}}
    dump_json(path, config)
    return config


def save_manifest(output):
    files = {path.relative_to(output).as_posix(): sha256(path) for path in output.rglob("*")
             if path.is_file() and path.name != "manifest.json" and "stopwords" not in path.relative_to(output).parts}
    dump_json(output / "manifest.json", {"generated_files_sha256": files,
              "user_owned_files_excluded": ["stopwords/problem_stopwords.json", "stopwords/solution_stopwords.json"],
              "note": "User choices are not generated token selections; analysis never applies or resets them."})


def verify_saved_tables(output):
    """보고서 재생성 전에 저장된 수치표의 변경 여부를 확인한다."""
    manifest = read_json(output / "manifest.json")
    names = manifest["generated_files_sha256"]
    for name, expected in names.items():
        if name.endswith(".csv") or name.endswith("summary.json"):
            path = output / name
            if not path.is_file() or sha256(path) != expected:
                raise ValueError(f"저장된 분석 표가 변경되었습니다. 원인을 확인하세요: {path}")


def run(action="analyze", *, root=ROOT, output=None):
    if action not in ("analyze", "report", "verify"):
        raise ValueError("analyze / report / verify 중 하나를 지정하세요. 모델 실험 명령은 없습니다.")
    root = Path(root).resolve()
    output = Path(output).resolve() if output is not None else root / "results/token_analysis"
    if output != root / "results/token_analysis":
        raise ValueError("이번 분석은 results/token_analysis/에만 저장합니다.")
    if action != "analyze" and not (output / "config.json").exists():
        raise FileNotFoundError("저장된 분석이 없습니다. 먼저 analyze를 실행하세요.")
    config = prepare_config(root, output)
    if action in ("report", "verify"):
        verify_saved_tables(output)
    print(f"토큰 분석 {action}: 원본 읽기 전용 · 결과 {output}", flush=True)
    if action == "analyze":
        review_files(output)
        from .statistics import build_statistics
        from .evidence import build_evidence
        summary = {"statistics": build_statistics(root, output), "evidence": build_evidence(root, output)}
        dump_json(output / "summary.json", summary)
        config["analysis_sources_sha256"] = {p.relative_to(root).as_posix(): sha256(p)
             for p in Path(__file__).parent.glob("*.py")}
        dump_json(output / "config.json", config)
    if action in ("analyze", "report"):
        from .reporting import build_report
        build_report(root, output, summary=read_json(output / "summary.json"))
    result = verify_analysis(root, output)
    if result["failed"]:
        raise ValueError("검증 실패: " + ", ".join(c["check"] for c in result["checks"] if not c["passed"]))
    save_manifest(output)
    print(f"검증 {result['passed']}개 통과 · 원본 {result['protected_original_files']}파일 해시 동일 · 후속 실험 실행 없음", flush=True)
    return result


def main():
    if len(sys.argv) > 2:
        raise SystemExit("python -m mathhint_analysis.token_analysis [analyze|report|verify]")
    return run(sys.argv[1] if len(sys.argv) == 2 else "analyze")
