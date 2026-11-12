"""Three-repeat offline reader; reuse the existing safe Markdown/LaTeX renderer."""

import html
import json
import os
from pathlib import Path
from urllib.parse import quote

from mathhint_analysis.ResultViewer import ASSETS
from ..gemini_comparison.viewer import _adapt_script
from ...CompareGeneration import file_hash, write_json


LABELS = {
    "A": "A 문제만", "B": "B Ridge 예측 토큰", "C": "C MLP 예측 토큰",
    "D": "D 실제 해설 토큰", "E": "E 추가 지시문만", "F": "F 실제 토큰 · 중립 출처",
}


def _href(path, target):
    return quote(Path(os.path.relpath(path, Path(target).parent)).as_posix(), safe="/._-")


def _script():
    """Only navigation/status additions; math parsing and HTML safety stay shared."""
    source = _adapt_script((ASSETS / "viewer.js").read_text(encoding="utf-8"))
    changes = [
        ("var methods = data.methods ||", "var repeatControl=document.getElementById('repeat-select');\n  var methods = data.methods ||"),
        ("methods.forEach(function (method) {", "methods.filter(function(method){return(q.available_conditions||[]).includes(method.condition);}).forEach(function (method) {"),
        ("var rows=methods.map(function(m){return(q.conditions||{})[m.key];});", "var rows=methods.filter(function(m){return(q.available_conditions||[]).includes(m.condition);}).map(function(m){return(q.conditions||{})[m.key];});"),
        ("if(value==='train')return q.split==='train';", "if(value==='control_scope')return q.is_control;if(value==='error_scope')return q.is_error_repeat;if(value==='train')return q.split==='train';"),
        ("r.status==='success'&&typeof(r.evaluation||{}).correct!=='boolean'", "r.api_received===true&&typeof(r.evaluation||{}).correct!=='boolean'"),
        ("r.status==='success'&&(!r.review||!r.review.math_status||r.review.math_status==='uncertain')", "r.api_received===true&&(!r.review||!r.review.math_status||r.review.math_status==='uncertain')"),
        ("원본 정답표 기준입니다.", "정정 정답표와 새 응답의 독립 검토 기준입니다. 원본 자동채점은 원문 감사에 보존합니다."),
        ("D는 실제 해설 빈도를 제공한 오라클 진단 조건입니다.", "D/F는 같은 실제 해설 토큰의 오라클 진단이며 출처 제목만 다릅니다. E는 지시문만 추가합니다."),
        ("학습 문항 확장 실험:", "학습 문항의 반복 실험:"),
        ("card.append(el('h3','',method.label),el('span','badge '+state.kind,state.label));", "card.append(el('h3','',method.label+' · 반복 '+repeatControl.value),el('span','badge '+state.kind,state.label));"),
        ("if(row.evaluation&&row.evaluation.predicted_answer!==undefined)", "if(row.grade_source==='independent_new_AI_answer_review')card.append(el('p','notice','자동 판정과 구분해 이 새 응답의 구체 근거로 최종 답을 따로 검토했습니다. 원본 판정은 아래 감사에 보존합니다.'));if(row.evaluation&&row.evaluation.predicted_answer!==undefined)"),
        ("return d;\n  }\n  function conditionStatus", "d.append(rawPanel('반복·원본 자동채점·표시용 판정',JSON.stringify({repeat:row.repeat,request_id:row.request_id,request_sha256:row.request_sha256,evaluation_raw:row.evaluation_raw,grade_source:row.grade_source,api_response_received:row.api_received,finish_reasons:row.finish_reasons,response_origin:row.response_origin},null,2)),rawPanel('동결 SDK 요청 인자',JSON.stringify(row.sdk_request||{},null,2)),rawPanel('동결 원천·모델·어휘 해시와 원본 정답',JSON.stringify(row.frozen_source_audit||{},null,2)),rawPanel('새 응답 풀이 검토 원문',JSON.stringify(row.review||{},null,2)));return d;\n  }\n  function conditionStatus"),
        ("search.addEventListener('input',function(){applyFilter(currentId);});", "repeatControl.addEventListener('change',function(){questions.forEach(function(q){q.conditions=q.repetitions[String(repeatControl.value)]||{};});applyFilter(currentId);});search.addEventListener('input',function(){applyFilter(currentId);});"),
        ("getQuestionCount:function(){return questions.length;}", "getQuestionCount:function(){return questions.length;},setRepeat:function(r){if(!['1','2','3'].includes(String(r)))return false;repeatControl.value=String(r);repeatControl.dispatchEvent(new Event('change'));return true;},getRepeat:function(){return Number(repeatControl.value);}"),
        ("applyFilter(byId.has(initial)?initial:(data.test_ids||[])[0]);", "applyFilter(byId.has(initial)?initial:(questions[0]||{}).id);"),
    ]
    for old, new in changes:
        count = source.count(old)
        if count != 1:
            raise ValueError(f"Shared reader adaptation point changed ({count}): {old[:70]}")
        source = source.replace(old, new, 1)
    return source


def build(output, payload):
    output = Path(output)
    target = output / "report.html"
    assets = output / "viewer_assets"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "viewer.js").write_text(_script(), encoding="utf-8")
    style = (ASSETS / "viewer.css").read_text(encoding="utf-8") + """
.conditions{grid-template-columns:repeat(2,minmax(0,1fr));margin-top:0}
.comparison-layout{display:grid;grid-template-columns:minmax(270px,.65fr) minmax(0,2fr);gap:18px;align-items:start;margin-top:20px}
.comparison-layout>.reference{position:sticky;top:12px;max-height:90vh;overflow:auto;margin-top:0}
.toolbar{grid-template-columns:minmax(180px,2fr) minmax(150px,1.4fr) minmax(110px,.8fr) minmax(140px,1.4fr);align-items:end}
.taxonomy{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
.taxonomy label{display:flex;flex-direction:column;min-width:0;font-size:.88rem}.taxonomy select{font:inherit;padding:8px;max-width:100%}
@media(max-width:1400px){.comparison-layout{grid-template-columns:1fr}.comparison-layout>.reference{position:static;max-height:none}}
@media(max-width:1100px){.conditions{grid-template-columns:1fr}.toolbar{grid-template-columns:1fr 1fr}.taxonomy{grid-template-columns:1fr 1fr}}
@media(max-width:600px){.toolbar,.taxonomy{grid-template-columns:1fr}}
"""
    (assets / "viewer.css").write_text(style, encoding="utf-8")
    write_json(assets / "source.json", {"renderer_source": "mathhint_analysis/viewer_assets/viewer.js",
        "renderer_source_sha256": file_hash(ASSETS / "viewer.js"),
        "adaptation": "3 repetitions, A-F applicable-condition navigation and raw grading/SDK panels only",
        "external_network_required": False, "vendor_source": "mathhint_analysis/viewer_assets/vendor",
        "audit_payload_mutated": False})
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    for old, new in (("&", "\\u0026"), ("<", "\\u003c"), (">", "\\u003e"),
                     ("\u2028", "\\u2028"), ("\u2029", "\\u2029")):
        encoded = encoded.replace(old, new)
    options = [("all", "전체 13문항"), ("control_scope", "출력 토큰 대조군 5문항"),
               ("error_scope", "기존 오답 관련 11문항"), ("changed", "조건·반복 정오답 변화"),
               ("reasoning_suspected", "풀이 오류 의심"), ("review_pending", "풀이 검토 보류"),
               ("ungraded", "채점 보류·불가"), ("api_error", "API 실패·불완전 응답"), ("not_run", "API 미실행·미수신"),
               ("train", "학습 문항"), ("test", "기존 테스트 분할 문항")]
    option_html = "".join(f'<option value="{key}">{html.escape(label)}</option>' for key, label in options)
    taxonomy = "".join(f'<label>{label}<select id="field-{key}"><option value="">전체</option></select></label>'
        for key, label in (("curriculum", "과목"), ("unit", "단원"), ("subunit", "세부단원"), ("type", "유형")))
    vendor, local = _href(ASSETS / "vendor", target), _href(assets, target)
    document = f'''<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'self' file:; style-src 'self' file: 'unsafe-inline'; font-src 'self' file:; img-src 'self' file: data:; connect-src 'none'; object-src 'none'; frame-src 'none'; base-uri 'none'; form-action 'none'">
<title>MathHint · 신규 3회 반복 비교</title>
<link rel="stylesheet" href="{vendor}/katex.min.css"><link rel="stylesheet" href="{local}/viewer.css">
<script defer src="{vendor}/markdown-it.min.js"></script><script defer src="{vendor}/katex.min.js"></script><script defer src="{local}/viewer.js"></script></head>
<body><header><p>MATHHINT · 저장된 신규 응답만 읽는 오프라인 화면</p><h1>신규 3회 반복 · A/B/C/D/E/F 풀이 비교</h1>
<p>반복 번호를 선택하면 동일 문항의 새 응답들을 비교합니다. 기존265 실험 응답은 신규 반복에 포함하지 않습니다. 3회는 탐색적 반복이며 인과효과·오류 불가능성을 증명하지 않습니다.</p><nav id="report-links"></nav></header>
<main><section class="toolbar"><label>문항 ID·분류 검색<input id="search" type="search" placeholder="trig_1_044 또는 분류명"></label>
<label>분석 필터<select id="filter">{option_html}</select></label><label>신규 반복<select id="repeat-select"><option value="1">반복 1</option><option value="2">반복 2</option><option value="3">반복 3</option></select></label>
<label>문항 선택<select id="question-select"></select></label><div class="pager"><button id="previous" type="button">이전</button><button id="next" type="button">다음</button></div></section>
<section class="taxonomy" aria-label="교육과정 분류">{taxonomy}</section><p id="status" role="status"></p><section id="question-content"></section>
<p id="asset-warning">수식 표시 파일을 읽는 중입니다. 저장소 전체 구조를 유지해 열어 주세요.</p>
<noscript>문항·반복 선택과 수식에는 로컬 JavaScript가 필요합니다. Markdown 사례와 CSV도 확인할 수 있습니다.</noscript></main>
<footer>읽기 화면은 API 요청을 보내거나 원본을 수정하지 않습니다. 정답 판정과 풀이의 수학적 타당성 검토는 별개입니다.</footer>
<script id="viewer-data" type="application/json">{encoded}</script></body></html>'''
    target.write_text(document, encoding="utf-8")
    return target
