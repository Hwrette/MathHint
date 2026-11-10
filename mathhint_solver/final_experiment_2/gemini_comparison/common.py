"""감사 가능한 저장·경로·성공 응답 읽기. API를 호출하지 않는다."""

import json
from contextlib import contextmanager
import os
from pathlib import Path
import socket

from ... import CompareGeneration as comparison

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / "results/final_experiment_2/gemini_comparison"
METHODS = {"A": "baseline", "B": "regression_hint", "C": "deep_learning_hint", "D": "oracle_hint"}
CONDITIONS = {value: key for key, value in METHODS.items()}
DEFAULT_POLICY = {"interval_seconds": 10.0, "workers": 1, "rpm": 6, "rph": 360,
                  "rpd": 320, "max_new_requests": 320, "max_run_seconds": 3600,
                  "max_wait_seconds": 120, "max_attempts": 2,
                  "http_timeout_ms": 180_000,
                  "provider_limits_confirmed": False,
                  "limits_note": "local conservative rolling-window caps; not confirmed provider quotas"}


def read_json(path):
    return comparison.read_json(Path(path))


def write_json(path, value):
    comparison.write_json(Path(path), value)


def append_jsonl(path, value):
    import os
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def read_jsonl(path):
    path = Path(path)
    if not path.exists():
        return []
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise ValueError(f"{path}:{number}: 불완전한 JSONL입니다. 성공 기록을 보존하여 복구하세요.") from error
    return rows


def load_saved(output=OUTPUT):
    """정적 보고서가 재학습·API 호출 없이 쓰는 공통 읽기 경로."""
    output = Path(output)
    wrapped = read_json(output / "config.json")
    config = wrapped["config"]
    if wrapped["config_id"] != comparison.digest(config):
        raise ValueError("저장된 API 설정의 해시가 다릅니다.")
    plan = read_jsonl(output / "plan.jsonl")
    records = list(comparison.load_completed(output, wrapped["config_id"]).values())
    state = read_json(output / "state.json") if (output / "state.json").exists() else {}
    return config, plan, records, state


def safe_output(root=ROOT, output=None):
    expected = Path(root).resolve() / "results/final_experiment_2/gemini_comparison"
    selected = Path(output).resolve() if output is not None else expected
    if selected != expected:
        raise ValueError(f"새 Gemini 결과는 전용 경로에만 저장합니다: {expected}")
    return selected


@contextmanager
def execution_lock(output):
    """같은 출력에서 두 프로세스가 동시에 요청하지 못하게 한다. 죽은 로컬 PID만 복구한다."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    path = output / ".execution.lock"
    if path.exists():
        previous = read_json(path)
        if previous.get("host") != socket.gethostname():
            raise RuntimeError("다른 환경의 실행 잠금이 남아 있습니다. 기존 실행 종료를 확인한 뒤 복구하세요.")
        try:
            os.kill(int(previous["pid"]), 0)
        except ProcessLookupError:
            path.unlink()
            append_jsonl(output / "execution_runs/lock_recovery.jsonl", {
                "recovered_at": comparison.utc_now(), "dead_local_pid": previous["pid"]})
        else:
            raise RuntimeError("이미 같은 결과를 사용하는 실행이 있습니다. 중복 API 호출을 막아 중단합니다.")
    handle = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(handle, "w", encoding="utf-8") as stream:
        json.dump({"pid": os.getpid(), "host": socket.gethostname(), "started_at": comparison.utc_now()}, stream)
    try:
        yield
    finally:
        if path.exists():
            path.unlink()
