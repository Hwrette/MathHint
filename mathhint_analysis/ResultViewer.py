"""저장된 문항·응답을 오프라인 읽기 화면으로 만든다. 학습·API 호출은 하지 않는다."""

import csv
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shutil
from urllib.parse import quote


METHODS = (
    {"key": "baseline", "label": "A 문제만"},
    {"key": "regression_hint", "label": "B 예측 해설 토큰"},
    {"key": "oracle_hint", "label": "C 실제 해설 토큰"},
)
ASSETS = Path(__file__).with_name("viewer_assets")
SAFE_RESPONSE_FIELDS = (
    "id", "method", "status", "problem_text", "input_text", "system_instruction",
    "input_sha256", "output_text", "evaluation", "usage", "hint", "model",
    "thinking_level", "model_version", "response_id", "finish_reasons",
    "config_id", "started_at", "completed_at", "response_origin", "error",
    "sdk_request_sha256", "condition", "uses_test_reference_vector",
    "reference_answer_text", "provenance", "source_provenance",
)
SAFE_PROVENANCE_FIELDS = (
    "source_config", "source_records", "source_config_id", "source_record_sha256",
    "source_records_sha256", "request_match", "historical_sdk_boundary_capture", "imported_at",
)


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _csv(path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _href(path, output):
    return quote(Path(os.path.relpath(path, output.parent)).as_posix(), safe="/._-")


def _paths(project_root, run_root, output_path, data_root):
    project = Path(project_root).resolve()
    def selected(path):
        path = Path(path)
        return path if path.is_absolute() else project / path
    run = selected(run_root)
    output = selected(output_path) if output_path is not None else run / "03_gemini/report.html"
    data = selected(data_root) if data_root is not None else project / "data"
    return project, run, output, data


def _latest(rows, expected_ids, config_id=None):
    result = {}
    methods = {item["key"] for item in METHODS}
    for row in rows:
        key = row.get("id"), row.get("method")
        if key[0] not in expected_ids or key[1] not in methods:
            raise ValueError(f"읽기 화면의 응답 ID/조건이 선택한 데이터와 다릅니다: {key}")
        if config_id and row.get("config_id") != config_id:
            raise ValueError(f"읽기 화면의 응답 설정 ID가 다릅니다: {key}")
        if key in result and result[key].get("status") == "success":
            raise ValueError(f"성공한 응답 뒤 중복 기록을 발견했습니다: {key}")
        result[key] = row
    return result


def _new_reviews(folder, latest):
    path = folder / "solution_review.json"
    if not path.exists():
        return {}
    result = {}
    for review in _read(path).get("records", []):
        key = review["id"], review["method"]
        row = latest.get(key)
        if not row or row.get("status") != "success":
            continue
        expected = review.get("response_sha256", review.get("output_sha256"))
        if hashlib.sha256((row.get("output_text") or "").encode()).hexdigest() != expected:
            raise ValueError(f"읽기 화면 검토의 응답 해시가 다릅니다: {path}: {key}")
        quotes = review.get("evidence_quotes", [review["quote"]] if review.get("quote") else [])
        if any(text not in (row.get("output_text") or "") for text in quotes):
            raise ValueError(f"읽기 화면 검토 인용문이 실제 응답에 없습니다: {key}")
        if key in result:
            raise ValueError(f"읽기 화면에 같은 응답의 검토가 중복됩니다: {key}")
        result[key] = dict(review)
    return result


def _legacy_reviews(project, latest, output):
    """기존 검토는 출처 해시와 현재 응답의 완전 일치가 확인될 때만 연결한다."""
    if not any(row.get("response_origin") in ("reused_control", "reused_exact_request") for row in latest.values()):
        return {}
    base = project / "results/model_comparison_2026-11-07"
    folder = base / "03_Gemini비교"
    source = folder / "원본응답_160개.jsonl"
    summary = folder / "풀이검토_요약.json"
    document = folder / "AI보조_풀이검토.html"
    manifest = base / "manifest.json"
    if not all(p.exists() for p in (source, summary, document, manifest)):
        return {}
    if _read(summary).get("source_snapshot", {}).get("sha256") != _sha(source):
        raise ValueError(f"기존 풀이 검토의 원본 응답 해시가 다릅니다: {source}")
    expected = _read(manifest)["files"][str(document.relative_to(base))]
    if _sha(document) != expected:
        raise ValueError(f"기존 풀이 검토 화면의 보존 해시가 다릅니다: {document}")
    original = {(row["id"], row["method"]): row for row in
                (json.loads(line) for line in source.read_text().splitlines() if line.strip())}
    result = {}
    for article in re.findall(r"<article>(.*?)</article>", document.read_text(), re.S):
        header = re.search(r"<h2>(.*?)</h2>", article, re.S)
        rating = re.search(r"수학적 적절성[^:]*:\s*(appropriate|inappropriate|uncertain)", article)
        if not header or not rating:
            continue
        parts = html.unescape(header.group(1)).split(" / ")
        if len(parts) != 2:
            continue
        key = tuple(parts)
        row, old = latest.get(key), original.get(key)
        if not row or not old or row.get("response_origin") not in ("reused_control", "reused_exact_request") or any(row.get(field) != old.get(field)
                                     for field in ("output_text", "input_sha256", "problem_text")):
            continue
        result[key] = {
            "math_status": rating.group(1), "reviewer_type": "AI_assisted",
            "human_confirmed": False,
            "reason": html.unescape(re.sub(r"<[^>]*>", "\n", article)).strip(),
            "source_href": _href(document, output),
        }
    return result


def build_payload(project_root, run_root, output_path, *, data_root=None, records=None, config=None):
    """원본 읽기만 수행해 HTML용 자료를 반환한다. 모델·SDK를 import하지 않는다."""
    project, run, output, data = _paths(project_root, run_root, output_path, data_root)
    metadata_path = data / "processed/metadata.json"
    metadata = _read(metadata_path)
    identifiers = {split: _read(data / f"processed/splits/{split}.json") for split in ("train", "test")}
    for split, ids in identifiers.items():
        if len(ids) != len(set(ids)) or any(not isinstance(i, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", i) for i in ids):
            raise ValueError(f"읽기 화면 문항 ID가 중복되거나 안전한 파일명이 아닙니다: {split}")
    if set(identifiers["train"]) & set(identifiers["test"]):
        raise ValueError("읽기 화면의 학습·테스트 문항이 겹칩니다.")
    all_ids = set(identifiers["train"] + identifiers["test"])
    metadata_rows = metadata["records"]
    if len(metadata_rows) != len(all_ids) or {r["id"] for r in metadata_rows} != all_ids:
        raise ValueError(f"읽기 화면의 메타데이터와 고정 분할 ID가 다릅니다: {metadata_path}")
    folder = run / "03_gemini"
    config_path = folder / "config.json"
    envelope = config if config is not None else (_read(config_path) if config_path.exists() else {})
    selected_config = envelope.get("config", envelope)
    config_id = envelope.get("config_id")
    if config is not None and "config" not in envelope:
        config_id = hashlib.sha256(json.dumps(selected_config, ensure_ascii=False, sort_keys=True,
                                              separators=(",", ":")).encode()).hexdigest()
    for key in ("train_ids", "test_ids"):
        split = key.split("_")[0]
        if key in selected_config and selected_config[key] != identifiers[split]:
            raise ValueError(f"읽기 화면의 {key}와 선택한 데이터 행 순서가 다릅니다: {config_path}")
    if selected_config.get("generation_id", metadata["generation_id"]) != metadata["generation_id"]:
        raise ValueError(f"읽기 화면의 데이터 식별 정보가 다릅니다: {config_path}")
    if selected_config.get("metadata_sha256") and selected_config["metadata_sha256"] != _sha(metadata_path):
        raise ValueError(f"읽기 화면 메타데이터 파일의 SHA-256이 저장 설정과 다릅니다: {metadata_path}")
    response_path = folder / "responses.jsonl"
    if records is None:
        records = [json.loads(line) for line in response_path.read_text().splitlines() if line.strip()] if response_path.exists() else []
    latest = _latest(records, set(identifiers["test"]), config_id)
    reviews = _legacy_reviews(project, latest, output)
    reviews.update(_new_reviews(folder, latest))
    regression = {r["id"]: r for r in _csv(run / "02_regression/question_comparison.csv")}
    comparison = {r["id"]: r for r in _csv(folder / "question_comparison.csv")}
    clusters = {}
    for row in _csv(run / "01_clustering/cluster_members.csv"):
        clusters.setdefault(row["id"], []).append(row)
    questions = []
    for meta in metadata_rows:
        identifier = meta["id"]
        split = "test" if identifier in identifiers["test"] else "train"
        problem_path = data / "processed/problems" / (identifier + ".txt")
        solution_path = data / "processed/solutions" / (identifier + ".txt")
        problem = problem_path.read_text(encoding="utf-8-sig")
        solution = solution_path.read_text(encoding="utf-8-sig")
        conditions = {}
        for method in METHODS:
            row = latest.get((identifier, method["key"]))
            if row is None:
                conditions[method["key"]] = None
                continue
            if "problem_text" in row and row["problem_text"] != problem:
                raise ValueError(f"저장 응답의 문제 원문이 선택한 데이터와 다릅니다: {identifier}/{method['key']}")
            safe = {key: row[key] for key in SAFE_RESPONSE_FIELDS if key in row}
            for key in ("provenance", "source_provenance"):
                if key in safe:
                    value = safe[key]
                    safe[key] = {name: value[name] for name in SAFE_PROVENANCE_FIELDS if name in value} if isinstance(value, dict) else None
            safe["display_output_sha256"] = hashlib.sha256(row["output_text"].encode()).hexdigest() if row.get("output_text") else None
            safe["review"] = reviews.get((identifier, method["key"]))
            condition = {"baseline": "A", "regression_hint": "B", "oracle_hint": "C"}[method["key"]]
            supplemental = comparison.get(identifier, {}).get(condition + "_correct_ai_supplemental")
            safe["correct_ai_supplemental"] = {"True": True, "False": False}.get(supplemental)
            conditions[method["key"]] = safe
        correct = [r.get("evaluation", {}).get("correct") for r in conditions.values()
                   if r and r.get("status") == "success" and type(r.get("evaluation", {}).get("correct")) is bool]
        answers = [str(r["evaluation"]["predicted_answer"]) for r in conditions.values()
                   if r and r.get("status") == "success" and r.get("evaluation", {}).get("predicted_answer") is not None]
        related = comparison.get(identifier, {})
        questions.append({
            "id": identifier, "split": split,
            "metadata": {key: meta.get(key) for key in
                         ("subject", "curriculum", "unit", "subunit", "type", "source", "source_file", "original_number", "current_number")},
            "problem_text": problem, "reference_answer": meta.get("answer_text"),
            "reference_solution": solution, "problem_href": _href(problem_path, output),
            "solution_href": _href(solution_path, output), "expected_generation": split == "test",
            "changed_correctness": len(set(correct)) > 1, "changed_answers": len(set(answers)) > 1,
            "conditions": conditions, "regression": regression.get(identifier),
            "clusters": clusters.get(identifier, []),
            "answer_key_conflict": str(related.get("answer_key_conflict", "")).lower() == "true",
            "ai_supplemental_answer": related.get("ai_supplemental_answer"),
        })
    safe_config = {key: selected_config[key] for key in (
        "model", "thinking_level", "temperature", "max_output_tokens", "system_instruction",
        "generation_id", "hint_mode", "hint_top_k", "predictions_sha256",
    ) if key in selected_config}
    links = {key: _href(path, output) if path.exists() else None for key, path in {
        "readme": run / "README.md", "final_report": run / "final_report.md",
        "comparison_csv": folder / "question_comparison.csv", "raw_responses": response_path,
        "regression_csv": run / "02_regression/question_comparison.csv",
        "clusters_csv": run / "01_clustering/cluster_members.csv",
    }.items()}
    return {"schema_version": 1, "experiment_name": run.name, "config": safe_config,
            "config_id": config_id, "methods": list(METHODS), "questions": questions,
            "test_ids": identifiers["test"], "train_ids": identifiers["train"],
            "generation_id": metadata["generation_id"], "links": links}


def build_viewer(project_root, run_root, output_path=None, *, data_root=None, records=None, config=None):
    """저장 자료와 로컬 렌더러만 복사한다. HTML 단독보다 assets와 함께 연다."""
    project, run, output, data = _paths(project_root, run_root, output_path, data_root)
    payload = build_payload(project, run, output, data_root=data, records=records, config=config)
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    for char, escaped in (("&", "\\u0026"), ("<", "\\u003c"), (">", "\\u003e"),
                          ("\u2028", "\\u2028"), ("\u2029", "\\u2029")):
        encoded = encoded.replace(char, escaped)
    output.parent.mkdir(parents=True, exist_ok=True)
    destination = run / "viewer_assets"
    if ASSETS.resolve() != destination.resolve():
        shutil.copytree(ASSETS, destination, dirs_exist_ok=True)
    assets = _href(destination, output)
    title = html.escape("MathHint · " + payload["experiment_name"])
    document = f'''<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'self' file:; style-src 'self' file: 'unsafe-inline'; font-src 'self' file:; img-src 'self' file: data:; connect-src 'none'; object-src 'none'; frame-src 'none'; base-uri 'none'; form-action 'none'">
<title>{title}</title><link rel="stylesheet" href="{assets}/vendor/katex.min.css"><link rel="stylesheet" href="{assets}/viewer.css">
<script defer src="{assets}/vendor/markdown-it.min.js"></script><script defer src="{assets}/vendor/katex.min.js"></script><script defer src="{assets}/viewer.js"></script></head>
<body><header class="page-header"><p class="eyebrow">MATHHINT · 저장된 연구 결과</p><h1>문항별 풀이 비교</h1>
<p>문제와 풀이를 수식으로 읽고, 원본 기록과 모델 결과를 함께 확인합니다.</p><nav id="report-links" aria-label="연구 결과"></nav></header>
<main><section class="toolbar" aria-label="문항 찾기"><label for="search">문항 ID 검색<input id="search" type="search" placeholder="예: diff_3_004" autocomplete="off"></label>
<label for="filter">확인할 문항<select id="filter"><option value="test">생성 실험 문항</option><option value="changed">조건별 정오답 변화</option><option value="answers">조건별 답변 변화</option><option value="review">풀이 오류·검토 보류</option><option value="api_error">API 실패</option><option value="not_run">API 미실행</option><option value="ungraded">채점 불가</option><option value="review_pending">검토 보류·미검토</option><option value="all">전체 문항</option><option value="train">학습 문항</option></select></label>
<label for="question-select">문항 선택<select id="question-select"></select></label><div class="pager"><button id="previous" type="button">이전</button><button id="next" type="button">다음</button></div></section>
<p id="status" role="status" aria-live="polite"></p><section id="question-content" aria-label="선택한 문항"></section>
<p id="asset-warning">수식 표시 파일을 읽는 중입니다. 화면이 열리지 않으면 report.html과 viewer_assets 폴더를 같은 구조로 내려받았는지 확인하세요.</p>
<noscript><p>이 화면의 수식과 문항 선택은 로컬 JavaScript가 필요합니다. 감사 원문은 같은 결과 폴더의 CSV·JSONL에서 확인할 수 있습니다.</p></noscript>
</main><footer>화면 표시는 원본 입력·응답을 바꾸지 않습니다. 풀이 검토는 AI 보조 판단이며 사람의 확정 판정과 구분합니다.</footer>
<script type="application/json" id="viewer-data">{encoded}</script></body></html>'''
    output.write_text(document, encoding="utf-8")
    return output
