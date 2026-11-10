"""기존 오프라인 수식 렌더러를 네 조건에 맞춰 최소 확장한다."""

import html
import json
import os
from pathlib import Path
from urllib.parse import quote

from mathhint_analysis.ResultViewer import ASSETS, SAFE_RESPONSE_FIELDS, SAFE_PROVENANCE_FIELDS
from ...CompareGeneration import file_hash, write_json


METHODS = (
    {"key": "baseline", "condition": "A", "label": "A 문제만"},
    {"key": "regression_hint", "condition": "B", "label": "B 선형회귀 예측 토큰"},
    {"key": "deep_learning_hint", "condition": "C", "label": "C 딥러닝 예측 토큰"},
    {"key": "oracle_hint", "condition": "D", "label": "D 실제 해설 토큰"},
)


def safe_payload(payload):
    """감사 원본은 보존하고 읽기 화면에는 필요한 필드만 복사한다."""
    result = dict(payload)
    result["config"] = {key: value for key, value in payload.get("config", {}).items() if key in (
        "model", "thinking_level", "temperature", "max_output_tokens", "system_instruction", "dataset_id")}
    allowed = set(SAFE_RESPONSE_FIELDS) | {"condition", "split", "request_path", "request_sha256",
              "display_output_sha256", "correct_ai_supplemental", "review"}
    provenance_fields = set(SAFE_PROVENANCE_FIELDS) | {"source_request_sha256", "source_output_sha256", "original_started_at", "original_completed_at"}
    result["questions"] = []
    for question in payload["questions"]:
        copied = dict(question)
        copied["conditions"] = {}
        for key, row in question["conditions"].items():
            safe = {name: value for name, value in row.items() if name in allowed} if row else None
            if safe:
                for name in ("provenance", "source_provenance"):
                    if name in safe:
                        safe[name] = {field: value for field, value in (safe[name] or {}).items() if field in provenance_fields}
            copied["conditions"][key] = safe
        result["questions"].append(copied)
    return result


def href(path, output):
    return quote(Path(os.path.relpath(path, Path(output).parent)).as_posix(), safe="/._-")


def _adapt_script(source):
    """수식·Markdown·HTML 안전 처리는 원래 렌더러를 그대로 재사용한다."""
    changes = [
        ("C는 실제 해설 빈도를 제공한 진단 조건입니다.",
         "D는 실제 해설 빈도를 제공한 오라클 진단 조건입니다. 정답과 풀이 검토는 별개입니다."),
        ("var labels = {appropriate:'타당',inappropriate:'오류 있음',uncertain:'판단 보류'};",
         "var labels = {appropriate:'타당 가능 · 보조 검토',inappropriate:'오류 의심 · 보조 검토',uncertain:'검토 보류'};"),
        ("review.human_confirmed === true ? '사람 확인' : 'AI 보조'",
         "review.human_confirmed === true ? '사람 확인' : review.reviewer_type==='not_reviewed' ? '아직 검토하지 않음' : 'AI 보조 · 사람 미확정'"),
        ("var reference=disclosure('원본 정답·해설 펼치기','reference');",
         "var reference=disclosure('원본 정답·해설 전체','reference');reference.open=true;"),
        ("});article.append(grid);",
         "});var comparison=el('div','comparison-layout');reference.remove();comparison.append(reference,grid);article.append(comparison);"),
        ("if (!row) return {label:'API 미실행',kind:'not-run'};",
         "if (!row || row.status==='not_run') return {label:'API 미실행',kind:'not-run'};"),
        ("rows.some(function(r){return r&&r.status!=='success';})",
         "rows.some(function(r){return r&&r.status!=='success'&&r.status!=='not_run';})"),
        ("rows.some(function(r){return !r;})", "rows.some(function(r){return !r||r.status==='not_run';})"),
        ("if(value==='train')return q.split==='train';if(value==='test')return q.expected_generation;",
         "if(value==='train')return q.split==='train';if(value==='test')return q.split==='test';"
         "if(value==='answers')return q.changed_answers;"
         "if(value==='review')return q.reasoning_suspected||q.review_pending;"
         "if(['A_correct_B_wrong','A_correct_C_wrong','B_only_correct','C_only_correct','D_only_correct',"
         "'all_wrong','D_wrong','answer_key_conflict','reasoning_suspected','possible_alternative','large_token_change','incomplete'].includes(value))"
         "return(q.case_tags||[]).includes(value);"),
        ("var filter = document.getElementById('filter');",
         "var filter = document.getElementById('filter');"
         "var taxonomyFields=['curriculum','unit','subunit','type'];"
         "var taxonomy=taxonomyFields.map(function(k){return document.getElementById('field-'+k);});"
         "taxonomyFields.forEach(function(k,i){var values=Array.from(new Set(questions.map(function(q){return(q.metadata||{})[k];}).filter(Boolean))).sort();"
         "values.forEach(function(v){var o=document.createElement('option');o.value=v;o.textContent=v;taxonomy[i].append(o);});});"),
        (".toLowerCase().includes(term)&&qualifies(q,kind);",
         ".toLowerCase().includes(term)&&qualifies(q,kind)&&taxonomyFields.every(function(k,i){return !taxonomy[i].value||(q.metadata||{})[k]===taxonomy[i].value;});"),
        ("search.addEventListener('input',function(){applyFilter(currentId);});",
         "taxonomy.forEach(function(field){field.addEventListener('change',function(){applyFilter(currentId);});});"
         "search.addEventListener('input',function(){applyFilter(currentId);});"),
        ("if(row.evaluation&&row.evaluation.predicted_answer!==undefined)",
         "if(row.hint){var hints=disclosure(row.status==='not_run'?'전송 예정 힌트 · API 미실행':'실제 요청 힌트 · token: frequency');"
         "hints.append(rawPanel('전송 JSON',JSON.stringify(row.hint.mapping||{},null,2)));card.append(hints);}"
         "if(row.evaluation&&row.evaluation.predicted_answer!==undefined)"),
        ("rawPanel('실제 사용자 입력',row.input_text || '')",
         "rawPanel(row.status==='not_run'?'저장된 전송 예정 입력 · API 미실행':'실제 사용자 입력',row.input_text || '')"),
        ("if(meta.source)article.append(el('p','source','출처: '+meta.source));",
         "if(meta.source)article.append(el('p','source','출처: '+meta.source));"
         "if(q.split==='train'&&q.expected_generation)article.append(el('p','notice','학습 문항 확장 실험: 모델 학습에 사용된 문항의 결과이며 일반화 성능이 아닙니다.'));"),
        ("if(q.answer_key_conflict)article.append(el('p','notice','정답표 충돌 문항:",
         "if(q.answer_key_conflict)article.append(el('p','notice','원본 정답표 충돌 의심 · 기존 AI 보조 근거, 사람 미확정. 정답표 충돌 문항:"),
    ]
    for old, new in changes:
        if source.count(old) != 1:
            raise ValueError(f"기존 안전 렌더러의 확장 위치가 바뀌었습니다: {old[:65]}")
        source = source.replace(old, new, 1)
    reset = "search.value='';filter.value='all';applyFilter(id);"
    if source.count(reset) != 2:
        raise ValueError("문항 ID 이동의 기존 필터 초기화 위치가 바뀌었습니다.")
    source = source.replace(reset, "search.value='';filter.value='all';taxonomy.forEach(function(f){f.value='';});applyFilter(id);")
    return source


def build(output, payload):
    """자료는 HTML에 안전하게 내장하고, 기존 로컬 vendor/fonts를 상대 경로로 쓴다."""
    output = Path(output)
    payload = safe_payload(payload)
    target = output / "report.html"
    assets = output / "viewer_assets"
    assets.mkdir(parents=True, exist_ok=True)
    source = ASSETS / "viewer.js"
    (assets / "viewer.js").write_text(_adapt_script(source.read_text(encoding="utf-8")), encoding="utf-8")
    style = (ASSETS / "viewer.css").read_text(encoding="utf-8") + """
.conditions{grid-template-columns:repeat(2,minmax(0,1fr));margin-top:0}
.comparison-layout{display:grid;grid-template-columns:minmax(280px,.7fr) minmax(0,2fr);gap:20px;align-items:start;margin-top:20px}
.comparison-layout>.reference{position:sticky;top:12px;max-height:90vh;overflow:auto;margin-top:0}
.taxonomy{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
.taxonomy label{display:flex;flex-direction:column;min-width:0;font-size:.88rem}.taxonomy select{font:inherit;padding:8px;max-width:100%}
@media(max-width:1400px){.comparison-layout{grid-template-columns:1fr}.comparison-layout>.reference{position:static;max-height:none}}
@media(max-width:1100px){.conditions{grid-template-columns:1fr}.taxonomy{grid-template-columns:1fr 1fr}}
@media(max-width:600px){.taxonomy{grid-template-columns:1fr}}
"""
    (assets / "viewer.css").write_text(style, encoding="utf-8")
    write_json(assets / "source.json", {"renderer_source": "mathhint_analysis/viewer_assets/viewer.js",
               "renderer_source_sha256": file_hash(source), "adaptation": "ABCD labels, filters, taxonomy and reference layout only",
               "external_network_required": False, "vendor_source": "mathhint_analysis/viewer_assets/vendor",
               "audit_payload_mutated": False})
    vendor = href(ASSETS / "vendor", target)
    local = href(assets, target)
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    for character, escape in (("&", "\\u0026"), ("<", "\\u003c"), (">", "\\u003e"),
                              ("\u2028", "\\u2028"), ("\u2029", "\\u2029")):
        encoded = encoded.replace(character, escape)
    options = [("test", "테스트 80문항"), ("changed", "조건별 정오답 변화"), ("answers", "조건별 최종 답 변화"),
               ("A_correct_B_wrong", "A 정답 → B 오답"), ("A_correct_C_wrong", "A 정답 → C 오답"),
               ("B_only_correct", "B만 정답"), ("C_only_correct", "C만 정답"), ("D_only_correct", "D만 정답"),
               ("all_wrong", "네 조건 모두 오답"), ("D_wrong", "D에서도 오답"),
               ("reasoning_suspected", "풀이 오류 의심"), ("answer_key_conflict", "정답표 충돌 의심"),
               ("possible_alternative", "타당한 대안 풀이"),
               ("review_pending", "풀이 검토 보류"), ("large_token_change", "토큰 사용량 큰 변화"),
               ("incomplete", "불완전·장황한 응답 의심"), ("ungraded", "채점 불가"),
               ("api_error", "API 실패"), ("not_run", "API 미실행·미완료"), ("train", "학습 문항"), ("all", "전체 문항")]
    options = "".join(f'<option value="{key}">{html.escape(label)}</option>' for key, label in options)
    taxonomy = "".join(f'<label>{label}<select id="field-{key}"><option value="">전체</option></select></label>'
                       for key, label in (("curriculum", "과목"), ("unit", "단원"), ("subunit", "세부단원"), ("type", "유형")))
    document = f'''<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'self' file:; style-src 'self' file: 'unsafe-inline'; font-src 'self' file:; img-src 'self' file: data:; connect-src 'none'; object-src 'none'; frame-src 'none'; base-uri 'none'; form-action 'none'">
<title>MathHint Final Experiment 2 · A/B/C/D 풀이 비교</title>
<link rel="stylesheet" href="{vendor}/katex.min.css"><link rel="stylesheet" href="{local}/viewer.css">
<script defer src="{vendor}/markdown-it.min.js"></script><script defer src="{vendor}/katex.min.js"></script><script defer src="{local}/viewer.js"></script></head>
<body><header><p>MATHHINT · 저장된 결과만 읽는 오프라인 화면</p><h1>A/B/C/D 문항별 풀이 비교</h1>
<p>A 문제만 · B 선형회귀 · C 딥러닝 · D 원본 해설 토큰. 원본 정답 판정과 풀이 검토를 분리합니다.</p><nav id="report-links"></nav></header>
<main><section class="toolbar"><label>문항 ID·분류 검색<input id="search" type="search" placeholder="diff_1_005 또는 분류명"></label>
<label>분석 필터<select id="filter">{options}</select></label><label>문항 선택<select id="question-select"></select></label>
<div class="pager"><button id="previous" type="button">이전</button><button id="next" type="button">다음</button></div></section>
<section class="taxonomy" aria-label="교육과정 분류">{taxonomy}</section><p id="status" role="status"></p>
<section id="question-content"></section><p id="asset-warning">수식 표시 파일을 읽는 중입니다. 저장소 전체 구조를 유지해 열어 주세요.</p>
<noscript>수식·문항 선택에는 로컬 JavaScript가 필요합니다. 같은 폴더의 Markdown·CSV도 확인할 수 있습니다.</noscript></main>
<footer>읽기 화면은 API 요청을 보내거나 원본을 수정하지 않습니다. 검토 보류는 오답 판정이 아닙니다.</footer>
<script id="viewer-data" type="application/json">{encoded}</script></body></html>'''
    target.write_text(document, encoding="utf-8")
    return target
