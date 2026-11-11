"""전체265 결과의 전용 경로와 기존 API 이력 읽기. 기존 자료에는 쓰지 않는다."""

from contextlib import contextmanager
import os
from pathlib import Path
import socket

from ..gemini_comparison.common import (
    ROOT, METHODS, CONDITIONS, append_jsonl, read_json, read_jsonl, write_json,
    load_saved as _load_saved, execution_lock as _execution_lock,
)
from ..gemini_comparison.common import DEFAULT_POLICY as ORIGINAL_POLICY
from ... import CompareGeneration as comparison

OUTPUT = ROOT / "results/final_experiment_2/gemini_full265"
DEFAULT_POLICY = {**ORIGINAL_POLICY, "rpd": 1400, "max_new_requests": 40,
    "user_authorized_additional_requests": 740,
    "provider_limits_confirmed": False,
    "limits_note": "user-authorized local safety cap for full265 extension; not a confirmed provider quota; old and new request starts share rolling windows"}


def validate_condition_order(value):
    """실행 우선순위만 허용한다. 누락·중복·소문자 조건은 조용히 보정하지 않는다."""
    if not isinstance(value, str) or len(value) != 4 or set(value) != set("ABCD"):
        raise ValueError("condition-order는 A/B/C/D를 한 번씩 포함한 순열이어야 합니다(예: ABDC).")
    return value


def safe_output(root=ROOT, output=None):
    expected = Path(root).resolve() / "results/final_experiment_2/gemini_full265"
    selected = Path(output).resolve() if output is not None else expected
    if selected != expected:
        raise ValueError(f"전체265 비교는 새 전용 경로에만 저장합니다: {expected}")
    return selected


def source_output(root=ROOT):
    return Path(root).resolve() / "results/final_experiment_2/gemini_comparison"


def load_saved(output=OUTPUT):
    """새 호출에서 출력 경로를 생략해도 과거80 결과를 읽지 않는다."""
    return _load_saved(output)


def verify_preservation(root, output):
    path = Path(output) / "preservation_manifest.json"
    if not path.is_file():
        raise FileNotFoundError(f"실행 전에 기존 자료의 복구·보존 기준을 저장해야 합니다: {path}")
    record = read_json(path)
    expected = record["files_sha256"]
    changed = [name for name, digest in expected.items()
               if not (Path(root) / name).is_file() or comparison.file_hash(Path(root) / name) != digest]
    if changed:
        raise ValueError("보호된 기존 파일이 달라져 전체265 실행을 중단합니다: " + ", ".join(changed[:10]))
    return {"passed": True, "checked_files": len(expected), "source_commit": record["source_commit"]}


def all_request_events(root, output):
    """기존 이력은 읽기만 하며 복사하지 않는다. 재개 시 대기와 모든 시작 수를 합산한다."""
    paths = (source_output(root) / "execution_runs/request_events.jsonl",
             Path(output) / "execution_runs/request_events.jsonl")
    unique = {}
    for path in paths:
        for event in read_jsonl(path):
            unique[comparison.digest(event)] = event
    return sorted(unique.values(), key=lambda event: event["time"])


@contextmanager
def execution_lock(root=ROOT, output=OUTPUT):
    """새 결과에서만 잠금을 생성하고 기존 실행의 살아 있는 잠금은 읽어서 거부한다."""
    old = source_output(root) / ".execution.lock"
    if old.exists():
        previous = read_json(old)
        if previous.get("host") != socket.gethostname():
            raise RuntimeError("이전80 실험의 다른 환경 잠금이 남아 있습니다. 기존 실행 종료를 먼저 확인하세요.")
        try:
            os.kill(int(previous["pid"]), 0)
        except ProcessLookupError:
            pass
        else:
            raise RuntimeError("이전80 API 실행이 살아 있어 전체265 동시 실행을 거부합니다.")
    with _execution_lock(safe_output(root, output)):
        yield
