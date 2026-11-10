"""거리 통계의 분석·저장 결과 표시·검증만 제공한다."""

from pathlib import Path
import sys

from ..common import ROOT, dump_json, read_json, sha256
from ..validation import verify_sources


def write_manifest(output):
    dump_json(output / "manifest.json", {"files_sha256": {
        p.relative_to(output).as_posix(): sha256(p) for p in output.rglob("*")
        if p.is_file() and p.name != "manifest.json"}})


def check_manifest(output, *, numeric_only=False):
    for name, expected in read_json(output / "manifest.json")["files_sha256"].items():
        if numeric_only and not name.endswith((".csv", "summary.json")):
            continue
        if not (output / name).is_file() or sha256(output / name) != expected:
            raise ValueError(f"저장된 거리 분석 파일이 바뀌었습니다: {output / name}")


def prepare_config(root, output):
    path = output / "config.json"
    if path.exists():
        config = read_json(path)
        verify_sources(root, config)
        return config
    token_root = root / "results/token_analysis"
    mutable = {"README.md", "token_analysis_report.md", "01_problem_tokens/README.md", "manifest.json"}
    protected = {}
    for folder in (root / "data", root / "results/final_experiment", root / "results/model_comparison_2026-11-07"):
        protected.update({p.relative_to(root).as_posix(): sha256(p) for p in folder.rglob("*") if p.is_file()})
    protected.update({p.relative_to(root).as_posix(): sha256(p) for p in token_root.rglob("*")
                      if p.is_file() and not p.is_relative_to(output) and p.relative_to(token_root).as_posix() not in mutable})
    for name in ("mathhint_analysis/BagOfWord.py", "mathhint_analysis/PrepareDataset.py",
                 "mathhint_learning/TorchKMeans.py", "mathhint_learning/TorchData.py"):
        protected[name] = sha256(root / name)
    config = {"analysis": "training_distance_normalization_statistics_v1", "n": 185, "dimensions": 346,
              "unordered_pair_count": 17020, "fit_or_assignment_performed": False,
              "input_scope": "existing problem train vectors only; no test-label token assessment",
              "zero_vector_policy": "Cosine undefined: stop without deleting documents or assigning arbitrary distances",
              "distance_units": {"contribution_euclidean": "squared raw Euclidean", "pair_comparison_euclidean": "ordinary raw Euclidean", "cosine": "1-cos = half squared L2-normalized Euclidean"},
              "protected_files_sha256": protected,
              "note": "Stopword files are protected user records, never inputs to masking or token selection."}
    dump_json(path, config)
    return config


def run(action="analyze", *, root=ROOT, output=None):
    if action not in ("analyze", "report", "verify"):
        raise ValueError("analyze / report / verify만 제공합니다. 학습·토큰 제거 명령은 없습니다.")
    root = Path(root).resolve()
    output = Path(output).resolve() if output is not None else root / "results/token_analysis/04_distance_comparison"
    if output != root / "results/token_analysis/04_distance_comparison":
        raise ValueError("거리 분석은 results/token_analysis/04_distance_comparison/에만 저장합니다.")
    if action != "analyze" and not (output / "config.json").exists():
        raise FileNotFoundError("저장된 거리 분석이 없습니다. 먼저 analyze를 실행하세요.")
    config = prepare_config(root, output)
    print(f"거리 통계 {action}: 학습185·346좌표·17020쌍 · 저장 {output}", flush=True)
    if action != "analyze":
        check_manifest(output, numeric_only=action == "report")
    if action == "analyze":
        from .geometry import load_geometry, build_geometry_analysis
        from .context import build_context
        geometry = load_geometry(root)
        summary = {"geometry": build_geometry_analysis(root, output, geometry=geometry),
                   "context": build_context(root, output, geometry=geometry)}
        dump_json(output / "summary.json", summary)
        config["analysis_sources_sha256"] = {p.relative_to(root).as_posix(): sha256(p)
                                            for p in Path(__file__).parent.glob("*.py")}
        for name in ("common.py", "statistics.py"):
            p = Path(__file__).parent.parent / name
            config["analysis_sources_sha256"][p.relative_to(root).as_posix()] = sha256(p)
        dump_json(output / "config.json", config)
    if action in ("analyze", "report"):
        from .reporting import build_report
        build_report(root, output, summary=read_json(output / "summary.json"))
    from .validation import verify
    result = verify(root, output, save=action != "verify")
    if result["failed"]:
        raise ValueError("거리 통계 검증 실패: " + ", ".join(c["check"] for c in result["checks"] if not c["passed"]))
    if action != "verify":
        write_manifest(output)
    print(f"검증 {result['passed']}개 통과 · 보호 파일 {result['protected_original_files']}개 불변 · 새 학습/API 없음", flush=True)
    return result


def main():
    if len(sys.argv) > 2:
        raise SystemExit("python -m mathhint_analysis.token_analysis.distance_comparison [analyze|report|verify]")
    return run(sys.argv[1] if len(sys.argv) == 2 else "analyze")
