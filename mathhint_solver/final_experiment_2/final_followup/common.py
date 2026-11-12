"""반복 번호를 포함한 신원·저장·보호. 네 조건 과거 캐시와 섞지 않는다."""

from contextlib import contextmanager
import os
from pathlib import Path
import socket

from ... import CompareGeneration as comparison
from ..gemini_comparison.common import (ROOT, read_json, write_json, read_jsonl,
    append_jsonl, execution_lock as _execution_lock)
from ..gemini_full265.common import DEFAULT_POLICY as BASE_POLICY

OUTPUT = ROOT / "results/final_experiment_2/final_followup"
METHODS = {"A": "baseline", "B": "regression_hint", "C": "deep_learning_hint",
           "D": "oracle_hint", "E": "instruction_only", "F": "neutral_reference_hint"}
CONDITIONS = {value: key for key, value in METHODS.items()}
# 새 반복은 전달받은 API 응답 한 개가 한 시행이다. 길이 제한/차단/빈 응답을
# 다시 뽑으면 출력 길이와 오류 재현율을 선택 편향시키므로 정상 STOP과 구별해
# 보존하되 같은 반복 번호를 재호출하지 않는다. 전송 오류만 미완료로 남긴다.
API_RECEIVED_STATUSES = ("success", "truncated_response", "blocked_or_incomplete_response", "empty_response")
API_RECEIVED = API_RECEIVED_STATUSES
DEFAULT_POLICY = {**BASE_POLICY, "max_new_requests": 60,
    "user_authorized_additional_requests": 186,
    "limits_note": "conservative local caps shared with old80/full265 attempts; provider quotas/remaining budget not inferred"}


def is_received(row):
    return row.get("status") in API_RECEIVED_STATUSES


def safe_output(root=ROOT, output=None):
    expected = Path(root).resolve() / "results/final_experiment_2/final_followup"
    selected = Path(output).resolve() if output is not None else expected
    if selected != expected:
        raise ValueError(f"반복 실험은 새 전용 경로에만 저장합니다: {expected}")
    return selected


def source_output(root=ROOT):
    return Path(root).resolve() / "results/final_experiment_2/gemini_full265"


def request_key(row):
    repeat = row.get("repeat")
    if type(repeat) is not int or repeat not in (1, 2, 3):
        raise ValueError("반복 번호는 정수1/2/3이어야 합니다.")
    condition = row.get("condition")
    if condition not in METHODS:
        raise ValueError("알 수 없는 반복 실험 조건입니다.")
    return row["id"], condition, repeat


def request_id(identifier, condition, repeat):
    return f"{identifier}__{condition}__r{repeat}"


def load_latest(output=OUTPUT, config_id=None):
    latest = {}
    delivered = set()
    for row in read_jsonl(Path(output) / "responses.jsonl"):
        key = request_key(row)
        if config_id is not None and row.get("config_id") != config_id:
            raise ValueError("반복 응답의 config_id가 다릅니다.")
        if row.get("request_id") != request_id(*key):
            raise ValueError("반복 요청 ID가 문항·조건·반복과 다릅니다.")
        if key in delivered:
            raise ValueError("API 응답을 이미 받은 반복의 중복 실행 기록이 있습니다.")
        if is_received(row):
            delivered.add(key)
        latest[key] = row
    return latest


def load_saved(output=OUTPUT):
    output = Path(output)
    wrapped = read_json(output / "config.json")
    config = wrapped["config"]
    if wrapped["config_id"] != comparison.digest(config):
        raise ValueError("반복 실험 설정의 해시가 다릅니다.")
    plan = read_jsonl(output / "plan.jsonl")
    records = list(load_latest(output, wrapped["config_id"]).values())
    state = read_json(output / "state.json") if (output / "state.json").is_file() else {}
    return config, plan, records, state


def verify_preservation(root, output):
    path = Path(output) / "preservation_manifest.json"
    if not path.is_file():
        raise FileNotFoundError("실행 전에 기존 파일의 보존 manifest를 저장하세요: " + str(path))
    record = read_json(path)
    files = record.get("files_sha256", {})
    if not files:
        raise ValueError("보존 manifest가 비어 있습니다.")
    changed = [name for name, sha in files.items()
               if not (Path(root) / name).is_file() or comparison.file_hash(Path(root) / name) != sha]
    if changed:
        raise ValueError("보호된 과거 파일이 변경되었습니다: " + ", ".join(changed[:10]))
    return {"passed": True, "checked_files": len(files), "source_commit": record.get("source_commit")}


def all_request_events(root=ROOT, output=OUTPUT):
    paths = [Path(root) / "results/final_experiment_2/gemini_comparison/execution_runs/request_events.jsonl",
             source_output(root) / "execution_runs/request_events.jsonl",
             Path(output) / "execution_runs/request_events.jsonl"]
    events = {}
    for path in paths:
        for event in read_jsonl(path):
            events[comparison.digest(event)] = event
    return sorted(events.values(), key=lambda row: row["time"])


@contextmanager
def execution_lock(root=ROOT, output=OUTPUT):
    root = Path(root).resolve()
    for previous_output in (root / "results/final_experiment_2/gemini_comparison", source_output(root)):
        lock = previous_output / ".execution.lock"
        if not lock.is_file():
            continue
        previous = read_json(lock)
        if previous.get("host") != socket.gethostname():
            raise RuntimeError("과거 실행의 다른 환경 잠금이 있어 동시 호출을 거부합니다.")
        try:
            os.kill(int(previous["pid"]), 0)
        except ProcessLookupError:
            continue
        raise RuntimeError("과거 실행이 살아 있어 동시 호출을 거부합니다.")
    with _execution_lock(safe_output(root, output)):
        yield
