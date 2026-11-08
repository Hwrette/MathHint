"""문항별 두 풀이·정답·토큰·검토 근거를 나란히 보는 HTML을 만든다.

아래 설정을 바꾸고 실행한다. latex2mathml이 있으면 수식을 변환하고,
없으면 LaTeX 원문을 보존한다. HTML은 외부 스크립트 없이 열린다.
"""

from __future__ import annotations

import base64
import hashlib
import html
import json
from pathlib import Path
import re
from typing import Any
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
RUN_ROOT = ROOT / "outputs/model_comparison"
GENERATION_NAME = "generation_top_tokens"
OUTPUT = RUN_ROOT / "report_top_tokens/문항별_비교.html"


METHODS = ("baseline", "regression_hint")
METHOD_NAMES = {"baseline": "문제만 입력", "regression_hint": "문제 + 회귀 예측 상위 20토큰"}
RATINGS = {"appropriate": "적절", "inappropriate": "부적절", "uncertain": "판단 보류", "unreviewed": "미검토"}
CRITERIA = {"logical_validity": "논리적 타당성", "enough_justification": "충분한 정당화",
            "reference_consistency": "원본 해설과의 일치", "curriculum_scope": "교과 범위 적합성"}
OPEN_MATH = re.compile(r"(?<!\\)(?:\$\$|\$)|\\\(|\\\[")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def escaped(value: Any) -> str:
    return html.escape(str(value), quote=True)


def download_text(value: str, filename: str, label: str) -> str:
    encoded = base64.b64encode(value.encode("utf-8")).decode("ascii")
    return f'<a download="{escaped(filename)}" href="data:text/plain;charset=utf-8;base64,{encoded}">{escaped(label)}</a>'


def raw_pre(value: str) -> str:
    # <code> prevents HTML's special stripping of an initial LF inside <pre>.
    return "<pre><code>" + escaped(value) + "</code></pre>"


class MathRenderer:
    def __init__(self) -> None:
        try:
            from latex2mathml.converter import convert
        except ImportError:
            convert = None
        self.convert = convert
        self.cache: dict[tuple[str, bool], tuple[str, str | None]] = {}
        self.warnings: list[dict] = []
        self.math_count = 0

    def equation(self, tex: str, display: bool, *, location: str) -> str:
        key = (tex, display)
        if key not in self.cache:
            try:
                if self.convert is None:
                    raise ImportError("latex2mathml이 없어 수식 원문을 표시합니다.")
                markup = self.convert(tex, display="block" if display else "inline")
                root = ET.fromstring(markup)
                for node in root.iter():
                    local_tag = node.tag.rsplit("}", 1)[-1]
                    if local_tag in {"script", "style", "iframe", "object", "embed", "a"}:
                        raise ValueError("Active content is not permitted in displayed MathML")
                    if any(name.rsplit("}", 1)[-1].lower() in {"href", "src"} or name.lower().startswith("on") for name in node.attrib):
                        raise ValueError("External/action attributes are not permitted in displayed MathML")
                # Unknown control sequences can survive without a converter exception.
                unknown = [node.text for node in root.iter() if node.text and re.search(r"\\[A-Za-z]{2,}", node.text)]
                if unknown:
                    raise ValueError("Unsupported literal control sequence in MathML: " + "; ".join(unknown[:3]))
                self.cache[key] = (markup, None)
            except Exception as error:
                self.cache[key] = ("", f"{type(error).__name__}: {error}")
        markup, error = self.cache[key]
        if error:
            self.warnings.append({"location": location, "tex": tex, "display": display, "reason": error})
            return '<code class="math-fallback" title="LaTeX 원문 표시">' + escaped(tex) + '</code><span class="fallback-note">[수식 원문]</span>'
        self.math_count += 1
        tag = "div" if display else "span"
        return f'<{tag} class="math-{ "display" if display else "inline"}" title="{escaped(tex)}">{markup}</{tag}>'

    def rich(self, value: str, *, location: str) -> str:
        output, position = [], 0
        while match := OPEN_MATH.search(value, position):
            opening = match.group()
            closing = {"$": "$", "$$": "$$", r"\(": r"\)", r"\[": r"\]"}[opening]
            content_start = match.end()
            if closing.startswith("$"):
                end = re.compile(r"(?<!\\)" + re.escape(closing)).search(value, content_start)
            else:
                end = re.search(re.escape(closing), value[content_start:])
                if end is not None:
                    # Normalize the relative match to absolute offsets below.
                    content_end, end_position = content_start + end.start(), content_start + end.end()
            if end is None:
                self.warnings.append({"location": location, "tex": value[match.start():],
                                      "display": opening in ("$$", r"\["), "reason": "Unclosed math delimiter; source text retained."})
                break
            if closing.startswith("$"):
                content_end, end_position = end.start(), end.end()
            output.append(self._plain(value[position:match.start()]))
            tex = value[content_start:content_end]
            output.append(self.equation(tex, opening in ("$$", r"\["), location=location))
            position = end_position
        output.append(self._plain(value[position:]))
        return '<div class="richtext">' + "".join(output) + "</div>"

    @staticmethod
    def _plain(value: str) -> str:
        text = escaped(value)
        text = re.sub(r"\*\*([^*\n]+)\*\*", r"<strong>\1</strong>", text)
        return text.replace("\n", "<br>\n")


CSS = """
:root{color-scheme:light;font-family:Arial,'Noto Sans CJK KR',sans-serif;color:#111;background:#f2f2f2}
*{box-sizing:border-box}body{margin:0;font-size:15px;line-height:1.65}header,main,footer{max-width:1440px;margin:auto;padding:22px}
header{background:#fff;border-bottom:2px solid #111}h1{font-size:27px;margin:0 0 8px}h2{font-size:19px;margin:0}h3{font-size:17px;margin:0 0 8px}h4{font-size:14px;margin:10px 0 4px}
p{margin:8px 0}a{color:#111;text-decoration:underline;text-underline-offset:3px}small,.muted{color:#555}.note{padding:12px 15px;background:#f6f6f6;border-left:3px solid #555}
.topstats{display:flex;gap:10px;flex-wrap:wrap;margin:15px 0}.stat{padding:10px 16px;border:1px solid #bbb;background:white}.stat strong{font-size:22px;display:block}
.controls{position:sticky;top:0;z-index:10;background:#fff;border:1px solid #aaa;padding:12px;display:flex;gap:9px;flex-wrap:wrap;align-items:center;box-shadow:0 2px 4px #0001}
input,select,button{font:inherit;padding:7px 10px;border:1px solid #999;background:white;border-radius:2px}input{min-width:240px;flex:1}button{cursor:pointer}button:hover{background:#eee}
.question{margin:22px 0;background:white;border:1px solid #aaa;scroll-margin-top:100px}.question[hidden]{display:none}.qhead{padding:16px 20px;border-bottom:1px solid #bbb;background:#fafafa}.labels{display:flex;gap:7px;flex-wrap:wrap;margin-top:5px}.tag,.badge{display:inline-block;padding:2px 7px;border:1px solid #aaa;border-radius:2px;font-size:12px;background:white}
.qbody{padding:18px 20px;border-bottom:1px solid #ddd}.problem{font-size:16px}.paired{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr)}.arm{padding:19px;min-width:0}.arm+.arm{border-left:1px solid #bbb}
.badge.correct{background:#fff;font-weight:bold;border:2px solid #222}.badge.incorrect{background:#222;color:#fff;border:2px solid #222}.badge.ungraded{background:#eee}.gradebox{margin:8px 0}.tokens{display:grid;grid-template-columns:repeat(3,1fr);gap:5px;margin:10px 0}.tokens div{padding:7px;border:1px solid #ccc;font-size:12px}.tokens b{display:block;font-size:17px;font-variant-numeric:tabular-nums}
.richtext{overflow-wrap:anywhere}.math-inline{display:inline-block;max-width:100%;overflow-x:auto;vertical-align:middle}.math-display{overflow-x:auto;text-align:center;margin:11px 0;padding:4px 0}math{font-size:1.07em}pre{margin:9px 0;padding:12px;background:#f5f5f5;border:1px solid #ccc;white-space:pre-wrap;overflow-wrap:anywhere;max-height:440px;overflow:auto;font-size:12px;line-height:1.55}code{font-family:ui-monospace,Consolas,monospace}
details{margin:11px 0;border-top:1px solid #ddd;padding-top:8px}summary{cursor:pointer;font-weight:bold}.downloads{display:flex;gap:12px;flex-wrap:wrap;font-size:12px}.review{margin-top:17px;padding-top:13px;border-top:2px solid #444}.criterion{border:1px solid #ddd;padding:9px 11px;margin:8px 0;font-size:13px}.criterion blockquote{margin:7px 0;padding-left:10px;border-left:2px solid #bbb}.conflict{padding:14px;border:2px solid #333;background:#f6f6f6;margin:12px 0}.reference{padding:14px 20px;border-top:1px solid #aaa;margin:0;background:#fafafa}.reference summary{font-size:15px}dl{display:grid;grid-template-columns:110px 1fr;gap:4px 9px;font-size:12px}dt{font-weight:bold}dd{margin:0;overflow-wrap:anywhere}.math-fallback{padding:2px;background:#eee}.fallback-note{font-size:10px;color:#555}footer{font-size:12px;color:#555}
@media(max-width:900px){.paired{grid-template-columns:1fr}.arm+.arm{border-left:0;border-top:1px solid #bbb}header,main{padding:12px}.tokens{grid-template-columns:repeat(3,minmax(0,1fr))}.controls{position:static}}
@media print{body{background:white;font-size:11px}.controls,.downloads{display:none}header,main{max-width:none;padding:5px}.question{break-inside:avoid;margin:12px 0}.arm{padding:10px}pre{max-height:none}.math-display{overflow:visible}}
"""

JAVASCRIPT = """
const cards = [...document.querySelectorAll('.question')];
function filterCards(){
 const term=document.querySelector('#search').value.trim().toLocaleLowerCase();
 const grade=document.querySelector('#grade').value, ai=document.querySelector('#ai').value;
 let shown=0;
 for(const card of cards){
  const match=(!term||card.dataset.search.includes(term))&&(!grade||card.dataset.grade.split(' ').includes(grade))&&(!ai||card.dataset.ai.split(' ').includes(ai));
  card.hidden=!match;if(match)shown++;
 }
 document.querySelector('#visible-count').textContent=shown+' / '+cards.length+'문항';
}
for(const id of ['search','grade','ai']) document.querySelector('#'+id).addEventListener(id==='search'?'input':'change',filterCards);
document.querySelector('#open-reviews').addEventListener('click',()=>{for(const x of document.querySelectorAll('.question:not([hidden]) details.ai-details'))x.open=true;});
document.querySelector('#close-details').addEventListener('click',()=>{for(const x of document.querySelectorAll('details'))x.open=false;});
filterCards();
"""


def grade_label(evaluation: dict) -> str:
    value = evaluation.get("correct")
    return "정답" if value is True else "오답" if value is False else "판독 보류"


def grade_class(evaluation: dict) -> str:
    value = evaluation.get("correct")
    return "correct" if value is True else "incorrect" if value is False else "ungraded"


def build(run_root: Path, generation_name: str, output: Path | None = None) -> dict:
    run_root = run_root.resolve()
    generation = run_root / generation_name
    if output is None:
        suffix = "_top_tokens" if generation_name == "generation_top_tokens" else ""
        output = run_root / ("report" + suffix) / "문항별_비교.html"
    output = output.resolve(); output.parent.mkdir(parents=True, exist_ok=True)
    response_path, config_path = generation / "responses.jsonl", generation / "config.json"
    review_path = run_root / "solution_review/ai_suggested_reviews.json"
    adjudication_path = run_root / "audit/audited_answer_conflicts.json"
    integrated_path = output.parent / "integrated_summary.json"
    config = read_json(config_path)
    rows = [json.loads(line) for line in response_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    latest = {(row["id"], row["method"]): row for row in rows}
    # CompareGeneration.digest hashes the canonical JSON encoding of the string.
    if any(row.get("input_sha256") != hashlib.sha256(json.dumps(row["input_text"], ensure_ascii=False,
            sort_keys=True, separators=(",", ":")).encode()).hexdigest() for row in latest.values()):
        raise ValueError("Recorded API input hash differs from the displayed input text.")
    test_ids = config["config"]["test_ids"]
    expected = {(item_id, method) for item_id in test_ids for method in METHODS}
    if set(latest) != expected:
        raise ValueError("Response ID/method pairs differ from the configured fixed test set.")
    if any(row.get("config_id") != config["config_id"] for row in latest.values()):
        raise ValueError("Response configuration differs from displayed configuration.")
    for item_id in test_ids:
        if any(latest[(item_id, "baseline")].get(field) != latest[(item_id, "regression_hint")].get(field)
               for field in ("problem_text", "reference_solution", "reference_answer_text", "source")):
            raise ValueError("Paired responses differ in problem or reference material.")
    reviews = read_json(review_path).get("records", []) if review_path.exists() else []
    valid_reviews, review_issues = {}, []
    for review in reviews:
        key = (review["id"], review["method"])
        row = latest.get(key)
        if row is None or review.get("output_sha256") != hashlib.sha256(row["output_text"].encode()).hexdigest() or review.get("config_id") != row["config_id"]:
            review_issues.append({"id": key[0], "method": key[1], "reason": "Review output hash/config does not match displayed response."})
        else:
            valid_reviews[key] = review
    conflicts = {record["id"]: record for record in read_json(adjudication_path).get("records", [])} if adjudication_path.exists() else {}
    supplemental = {}
    if integrated_path.exists():
        integrated = read_json(integrated_path)
        if integrated.get("source_sha256", {}).get("responses") != sha256(response_path):
            raise ValueError("Integrated report source hash differs from current responses.")
        if integrated.get("source_sha256", {}).get("config") != sha256(config_path):
            raise ValueError("Integrated report configuration hash differs from current configuration.")
        audited_hash = integrated.get("adjudicated_answer_scores", {}).get("source_sha256")
        if adjudication_path.exists() and audited_hash != sha256(adjudication_path):
            raise ValueError("Supplemental answer correction source hash differs from the audited conflict file.")
        for record in integrated.get("adjudicated_answer_scores", {}).get("evaluations", []):
            supplemental[(record["id"], record["method"])] = record["mathematical_review_evaluation"]
    if conflicts and not supplemental:
        raise ValueError("Answer conflicts need the separately audited supplemental evaluations.")
    renderer = MathRenderer()
    cards, counts = [], {method: {"original": 0, "supplemental": 0} for method in METHODS}

    def render_review(item_id: str, method: str) -> str:
        review = valid_reviews.get((item_id, method))
        if not review:
            return '<div class="review">AI 보조 검토: 미검토</div>'
        mathematical = review.get("derived_mathematical_appropriateness", "unreviewed")
        parts = [f'<div class="review"><b>풀이의 수학적 적절성 · AI 제안: {RATINGS.get(mathematical, escaped(mathematical))}</b>',
                 '<p class="muted"><small>조건을 아는 AI 보조 검토다. 사람의 검증·맹검 판정이 아니다. 교과 범위 판정은 별도다.</small></p>',
                 '<details class="ai-details"><summary>네 가지 기준·인용 근거 보기</summary>']
        for criterion, label in CRITERIA.items():
            rubric = review.get("rubric", {}).get(criterion, {})
            rating = rubric.get("rating", "unreviewed")
            parts.append(f'<section class="criterion"><b>{label}: {RATINGS.get(rating, escaped(rating))}</b>')
            parts.append(renderer.rich(rubric.get("explanation", ""), location=f"{item_id}/{method}/review/{criterion}/explanation"))
            for quote in rubric.get("evidence_quotes", []):
                parts.append('<blockquote>' + renderer.rich(quote, location=f"{item_id}/{method}/review/{criterion}/quote") + '</blockquote>')
            parts.append('</section>')
        for note in review.get("notes", []):
            parts.append(renderer.rich(note, location=f"{item_id}/{method}/review/note"))
        parts.append('<small>검토자: ' + escaped(review.get("reviewer", {}).get("id", "AI")) + ' · ' + escaped(review.get("reviewed_at", "")) + '</small>')
        parts.append('<details><summary>검토 출처·무결성</summary>' + raw_pre(json.dumps({key: review.get(key) for key in ("review_id", "reviewer", "source_file", "output_sha256", "config_id")}, ensure_ascii=False, indent=2)) + '</details>')
        parts.append('</details></div>')
        return "".join(parts)

    def render_arm(row: dict) -> str:
        item_id, method = row["id"], row["method"]
        original = row.get("evaluation", {})
        corrected = supplemental.get((item_id, method), original)
        counts[method]["original"] += original.get("correct") is True
        counts[method]["supplemental"] += corrected.get("correct") is True
        usage = row.get("usage") or {}
        parts = [f'<section class="arm" data-method="{method}"><h3>{METHOD_NAMES[method]}</h3>',
            f'<div class="gradebox"><span class="badge {grade_class(corrected)}">정답표 충돌 보정: {grade_label(corrected)}</span> ',
            f'<span class="badge">원본 정답표 기준: {grade_label(original)}</span></div>',
            '<p>추출된 최종 답: <b>' + escaped(original.get("predicted_answer", "미판독")) + '</b></p>', '<div class="tokens">']
        for field, label in (("prompt_token_count", "입력 토큰"), ("candidates_token_count", "출력 토큰"), ("total_token_count", "합계 토큰")):
            count = usage.get(field)
            parts.append(f'<div>{label}<b>{escaped(count) if count is not None else "미제공"}</b></div>')
        parts.append('</div><small>생각 토큰: ' + escaped(usage.get("thoughts_token_count") if usage.get("thoughts_token_count") is not None else "메타데이터 미제공") + '</small>')
        parts.append('<div class="generated-output">' + renderer.rich(row.get("output_text", ""), location=f"{item_id}/{method}/output") + '</div>')
        parts.append('<div class="downloads">' + download_text(row["input_text"], f"{item_id}_{method}_input.txt", "입력 TXT") +
                     download_text(row.get("output_text", ""), f"{item_id}_{method}_output.txt", "출력 TXT") + '</div>')
        parts.append('<details><summary>실제 API 입력 원문·시스템 지시문</summary><p><small>표시용 수식으로 바꾸지 않은 정확한 전송 문자열이다.</small></p><h4>시스템 지시문</h4>' +
                     raw_pre(row.get("system_instruction", "")) + '<h4>사용자 입력</h4>' + raw_pre(row["input_text"]) + '</details>')
        parts.append('<details><summary>출력 원문·토큰 메타데이터·실행 출처</summary>' + raw_pre(row.get("output_text", "")))
        provenance = {key: row.get(key) for key in ("model", "model_version", "thinking_level", "status", "response_origin", "provenance", "response_id", "started_at", "completed_at", "latency_seconds", "config_id", "input_sha256", "finish_reasons")}
        provenance["usage"] = usage; provenance["original_evaluation"] = original
        provenance["mathematical_supplemental_evaluation"] = corrected
        parts.append(raw_pre(json.dumps(provenance, ensure_ascii=False, indent=2)) + '</details>')
        parts.append(render_review(item_id, method)); parts.append('</section>')
        return "".join(parts)

    for item_id in test_ids:
        pair = {method: latest[(item_id, method)] for method in METHODS}
        row = pair["baseline"]
        evaluations = {method: supplemental.get((item_id, method), pair[method].get("evaluation", {})) for method in METHODS}
        filters = []
        if any(value.get("correct") is False for value in evaluations.values()): filters.append("any_incorrect")
        if evaluations["baseline"].get("correct") is False: filters.append("baseline_incorrect")
        if evaluations["regression_hint"].get("correct") is False: filters.append("hint_incorrect")
        if evaluations["baseline"].get("correct") != evaluations["regression_hint"].get("correct"): filters.append("different_outcome")
        if item_id in conflicts: filters.append("answer_conflict")
        ai_values = [valid_reviews.get((item_id, method), {}).get("derived_mathematical_appropriateness", "unreviewed") for method in METHODS]
        ai_filters = []
        if "inappropriate" in ai_values: ai_filters.append("any_inappropriate")
        if "uncertain" in ai_values: ai_filters.append("any_uncertain")
        if all(value == "appropriate" for value in ai_values): ai_filters.append("both_appropriate")
        if "unreviewed" in ai_values: ai_filters.append("any_unreviewed")
        search = " ".join(str(row.get(key, "")) for key in ("id", "subject", "unit", "type", "source")).lower()
        parts = [f'<article class="question" id="{item_id}" data-search="{escaped(search)}" data-grade="{" ".join(filters)}" data-ai="{" ".join(ai_filters)}">',
            f'<div class="qhead"><h2><a href="#{item_id}">{item_id}</a></h2><div class="labels">']
        for field in ("subject", "unit", "type"):
            parts.append('<span class="tag">' + escaped(row.get(field, "")) + '</span>')
        source = row.get("reference", {}).get("source", {})
        parts.append('</div><p class="muted"><small>출처: ' + escaped(row.get("source", "")) + ' · 원본 ' + escaped(source.get("original_number", "")) + '번 / 현재 ' + escaped(source.get("current_number", "")) + '번</small></p></div>')
        parts.append('<div class="qbody"><div class="problem">' + renderer.rich(row["problem_text"], location=f"{item_id}/problem") + '</div>')
        parts.append('<p><b>원본 정답 표기: ' + escaped(row.get("reference_answer_text", "")) + '</b></p>')
        if item_id in conflicts:
            conflict = conflicts[item_id]
            math_ground = r'$\sin t=\frac35,\quad \cos t=-\frac45,\quad k=-\frac{12}5,\quad k\tan t=\left(-\frac{12}5\right)\left(-\frac34\right)=\frac95$'
            ground = renderer.rich(math_ground, location=f"{item_id}/adjudication") if item_id == "trig_1_010" else raw_pre(json.dumps(conflict.get("independent_exact_calculation", {}), ensure_ascii=False, indent=2))
            parts.append('<div class="conflict"><b>원본 정답표 충돌 · 원본 ' + escaped(conflict["original_answer"]) + ' / 수학 근거 보조 정답 ' +
                escaped(conflict["mathematically_supported_answer"]) + ' (' + escaped(conflict["mathematically_supported_value"]) + ')</b>' +
                ground + '<p>' + escaped(conflict["reason"]) + '</p>' +
                '<p><small>AI 보조 독립 계산에 따른 별도 채점이다. 사람의 확정 판정이 아니며 원본 HML·응답·원본 채점 결과는 수정하지 않았다.</small></p></div>')
        parts.append('</div><div class="paired">')
        parts.extend(render_arm(pair[method]) for method in METHODS)
        parts.append('</div><details class="reference"><summary>원본 정답·해설 보기 (원본 표기 유지)</summary>' +
                     renderer.rich(row.get("reference_solution", ""), location=f"{item_id}/reference") + '</details></article>')
        cards.append("".join(parts))
    n = len(test_ids)
    header = ['<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">',
              '<title>문항별 풀이 비교 · MathHint</title><style>', CSS, '</style></head><body><header><h1>문항별 풀이 비교</h1>',
              '<p>같은 테스트 문항의 기본 생성과 회귀 예측 상위 토큰 추가 생성을 나란히 확인한다. ' +
              ('수식은 MathML로 표시한다.' if renderer.convert else '수식 변환 패키지가 없어 LaTeX 원문으로 표시한다.') +
              ' 외부 스크립트나 인터넷 연결은 필요 없다.</p>',
              f'<p class="muted"><small>{escaped(config["config"]["model"])} · thinking={escaped(config["config"]["thinking_level"])} · temperature={escaped(config["config"].get("temperature"))} · {n}문항 × 두 조건</small></p>',
              '<div class="topstats">']
    for method in METHODS:
        header.append(f'<div class="stat">{METHOD_NAMES[method]}<strong>{counts[method]["supplemental"]}/{n} · {counts[method]["supplemental"]/n:.2%}</strong><small>정답표 충돌 보정 / 원본 정답표 기준 {counts[method]["original"]}/{n}</small></div>')
    header.append(f'<div class="stat">풀이 적절성 검토<strong>AI {len(valid_reviews)}/{2*n} · 사람 0</strong><small>정답 일치와 풀이 적절성은 별도 평가</small></div></div>')
    header.append('<div class="note">AI 검토자는 생성 조건을 알고 검토했다. AI 보조 제안이며 사람의 검증·맹검 평가가 아니다. 교과 범위는 공식 성취기준과 대조하지 않아 판단 보류로 기록했다. 정답표 충돌 보정은 감사 기록이 있는 문항만 별도 정답으로 채점하며 나머지는 원본 정답표를 따른다. 토큰 수는 표시된 성공 응답의 값이며 실패 요청의 미제공 사용량은 포함하지 않는다. 재사용한 기본 응답은 실행 시점이 다를 수 있다.</div></header><main>')
    header.append('<div class="controls"><input id="search" type="search" aria-label="문항 검색" placeholder="ID · 단원 · 유형 · 출처 검색"><select id="grade" aria-label="정답 필터"><option value="">정답 결과 전체</option><option value="any_incorrect">한 조건 이상 오답</option><option value="baseline_incorrect">기본 생성 오답</option><option value="hint_incorrect">회귀 토큰 생성 오답</option><option value="different_outcome">두 조건 정오답 다름</option><option value="answer_conflict">원본 정답표 충돌</option></select><select id="ai" aria-label="AI 풀이 적절성 필터"><option value="">AI 풀이 적절성 전체</option><option value="any_inappropriate">한 조건 이상 부적절</option><option value="any_uncertain">한 조건 이상 판단 보류</option><option value="both_appropriate">두 조건 모두 적절</option><option value="any_unreviewed">미검토 포함</option></select><button id="open-reviews">AI 근거 펼치기</button><button id="close-details">접기</button><span id="visible-count"></span></div>')
    manifest = {"generation_name": generation_name, "config_id": config["config_id"], "questions": n,
                "condition_records": len(latest), "ai_review_records_joined": len(valid_reviews), "human_review_records": 0,
                "grade_counts": counts, "mathml_expressions_rendered": renderer.math_count,
                "unique_math_expressions": len(renderer.cache), "math_fallback_occurrences": len(renderer.warnings),
                "review_validation_issues": review_issues, "source_files": {
                    "responses": {"path": str(response_path), "sha256": sha256(response_path)},
                    "config": {"path": str(config_path), "sha256": sha256(config_path)},
                    "ai_reviews": {"path": str(review_path), "sha256": sha256(review_path) if review_path.exists() else None},
                    "answer_conflicts": {"path": str(adjudication_path), "sha256": sha256(adjudication_path) if adjudication_path.exists() else None}},
                "raw_records_modified": False, "uses_external_scripts_or_styles": False}
    manifest["math_rendering_mode"] = "mathml" if renderer.convert else "latex_source"
    footer = '<footer><p>설정값을 바꾼 뒤 다시 실행: python -m mathhint_analysis.BuildComparisonViewer</p>'
    footer += '<details><summary>출처 파일·해시·수식 변환 기록</summary>' + raw_pre(json.dumps(manifest, ensure_ascii=False, indent=2)) + '</details></footer>'
    output.write_text("".join(header + cards) + '</main>' + footer + '<script>' + JAVASCRIPT + '</script></body></html>', encoding="utf-8")
    warnings_path = output.with_name(output.stem + "_수식변환_기록.json")
    warnings_path.write_text(json.dumps({**manifest, "warnings": renderer.warnings}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest["html_path"] = str(output); manifest["warnings_path"] = str(warnings_path)
    return manifest


def main() -> None:
    print(json.dumps(build(RUN_ROOT, GENERATION_NAME, OUTPUT), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
