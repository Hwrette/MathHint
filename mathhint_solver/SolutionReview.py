"""최종 답과 별도로 풀이 과정을 검토하는 HTML과 집계표를 만든다.

아래 설정을 바꾸고 실행한다. 검토 전 항목은 unreviewed로 남기고,
사람의 판정과 AI 보조 제안은 별도로 저장한다.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
from typing import Any


# 설정: 검토할 응답 폴더와 내려받은 검토 파일을 지정한다.
ROOT = Path(__file__).resolve().parents[1]
RUN_ROOT = ROOT / "outputs/model_comparison"
GENERATION = RUN_ROOT / "generation_top_tokens"
OUTPUT = RUN_ROOT / "solution_review"
METADATA = ROOT / "data/processed/metadata.json"
REVIEWS = None  # 완료한 사람 검토 JSON. 없으면 기존 검토 내용을 보존한다.
AI_REVIEWS = []  # AI 보조 검토 JSON 경로 목록. 사람 평가와 합치지 않는다.
CURRICULUM_NOTES = None  # 실제 수업 범위를 적은 UTF-8 파일 경로


RUBRIC_VERSION = "mathhint-solution-review-v1"
RATINGS = ("appropriate", "inappropriate", "uncertain", "unreviewed")
CRITERIA = {
    "logical_validity": {"label": "논리적 타당성", "guidance": "변형·계산·조건 적용·결론에 수학적 오류나 모순이 있는지 확인한다. 최종 답이 맞아도 잘못된 논증은 부적절하다."},
    "enough_justification": {"label": "설명의 충분성", "guidance": "답을 얻는 핵심 단계와 필요한 경우 나누기를 설명했는지 확인한다. 길이나 말투로 평가하지 않는다."},
    "curriculum_scope": {"label": "교과 범위 적합성", "guidance": "제공된 단원·교과 및 수업 범위 메모와 사용한 개념을 대조한다. 정확한 범위가 확인되지 않으면 uncertain으로 남긴다."},
    "reference_consistency": {"label": "문제·원본 정답과의 일관성", "guidance": "문제 조건을 바꾸거나 원본 정답과 상충하는 결론을 내지 않았는지 확인한다. 원본과 다른 타당한 풀이도 허용한다. 원본 오류가 의심되면 uncertain과 근거를 남긴다."},
}
MATHEMATICAL_CRITERIA = ("logical_validity", "enough_justification", "reference_consistency")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_latest_records(path: Path, snapshot: dict | None = None) -> list[dict[str, Any]]:
    """재실행 로그에서 같은 config/id/method의 마지막 상태를 사용한다."""
    latest = {}
    raw = path.read_bytes()
    if snapshot is not None:
        snapshot.update(path=str(path.resolve()), generation_folder=str(path.parent.resolve()),
                        sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw), loaded_at=_now())
    for index, line in enumerate(raw.decode("utf-8").splitlines()):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"응답 로그 {index + 1}행이 잘렸습니다. 완료된 로그로 다시 내보내세요.") from error
        latest[(row.get("config_id"), row["id"], row["method"])] = row
    return list(latest.values())


def build_review_bundle(records: list[dict[str, Any]], *, metadata: dict[str, dict] | None = None,
                        curriculum_notes: str = "", expected_responses: int | None = None,
                        previous: dict | None = None) -> tuple[dict, dict]:
    """방법을 숨긴 검토 자료와 별도 보관할 복호화 목록을 만든다."""
    metadata = metadata or {}
    prior_items = {row["review_id"]: row for row in (previous or {}).get("items", [])}
    if previous:
        validate_review_bundle(previous)
    items, mapping, excluded = [], {}, []
    seen = set()
    config_ids = {row.get("config_id") for row in records}
    if len(config_ids) > 1:
        raise ValueError("서로 다른 실험 설정을 한 검토 자료에 섞을 수 없습니다.")
    for row in records:
        key = (row["id"], row["method"])
        if key in seen:
            raise ValueError("최신 응답만 전달해야 합니다: " + str(key))
        seen.add(key)
        text = row.get("output_text") or ""
        if row.get("status") != "success" or not text.strip():
            excluded.append({"id": row["id"], "method": row["method"],
                             "status": row.get("status"), "reason": "no_successful_solution_to_review"})
            continue
        digest = _hash(text)
        review_id = "review_" + _hash(json.dumps([row.get("config_id"), row["id"], row["method"], digest]))[:24]
        source = metadata.get(row["id"], {})
        item = {
            "review_id": review_id, "question_id": row["id"], "output_sha256": digest,
            "problem_text": row.get("problem_text", ""), "output_text": text,
            "reference_answer": row.get("reference_answer_text", ""),
            "reference_solution": row.get("reference_solution", ""),
            "curriculum_context": {key: source.get(key, row.get(key, ""))
                                   for key in ("curriculum", "subject", "unit", "subunit", "type")},
            "curriculum_notes": curriculum_notes,
            "reviewer": {"id": "", "kind": "human"}, "reviewed_at": None,
            "rubric": {name: {"rating": "unreviewed", "evidence_quotes": [], "explanation": ""} for name in CRITERIA},
        }
        if review_id in prior_items:
            old = prior_items[review_id]
            if any(old.get(field) != item[field] for field in ("output_sha256", "problem_text", "output_text", "reference_answer", "reference_solution", "curriculum_context", "curriculum_notes")):
                raise ValueError("기존 검토의 문제/출력/참고 자료가 변경되었습니다: " + review_id)
            item.update({field: old[field] for field in ("reviewer", "reviewed_at", "rubric")})
        items.append(item)
        mapping[review_id] = {"id": row["id"], "method": row["method"], "config_id": row.get("config_id"), "output_sha256": digest}
    # 동일한 검토 자료를 다시 만들 때 방법의 순서로 배치되지 않도록 고정 해시 순서를 쓴다.
    items.sort(key=lambda item: _hash("blind-order-v1:" + item["review_id"]))
    bundle = {"schema_version": 1, "rubric_version": RUBRIC_VERSION, "generated_at": _now(),
              "experiment_config_id": next(iter(config_ids), None),
              "review_target_digest": _hash(json.dumps(sorted((item["review_id"], item["output_sha256"]) for item in items))),
              "criteria": CRITERIA, "rating_values": list(RATINGS),
              "review_scope": "Solution reasoning review, independent of final-answer accuracy. No automatic appropriateness judgments.",
              "blindness_limit": "Method, input hint, tokens and automatic grades are omitted. The generated solution itself can still reveal its method.",
              "counts": {"expected_responses": expected_responses, "recorded_responses": len(records),
                         "eligible_solutions": len(items), "excluded_non_success": len(excluded),
                         "not_recorded_yet": max(0, expected_responses - len(records)) if expected_responses is not None else None},
              "items": items}
    private = {"schema_version": 1, "rubric_version": RUBRIC_VERSION, "mapping": mapping, "excluded_responses": excluded}
    validate_review_bundle(bundle)
    return bundle, private


def validate_review_bundle(bundle: dict) -> None:
    """기록의 버전, 평가 근거, 검토자와 출력 무결성을 확인한다."""
    if bundle.get("schema_version") != 1 or bundle.get("rubric_version") != RUBRIC_VERSION:
        raise ValueError("지원하지 않는 검토/루브릭 버전입니다.")
    seen = set()
    for item in bundle.get("items", []):
        identifier = item.get("review_id")
        if not identifier or identifier in seen:
            raise ValueError("검토 ID가 비었거나 중복되었습니다.")
        seen.add(identifier)
        if item.get("output_sha256") != _hash(item.get("output_text", "")):
            raise ValueError("검토 대상 출력 해시가 다릅니다: " + identifier)
        reviewer = item.get("reviewer", {})
        if reviewer.get("kind") not in {"human", "ai_suggestion"}:
            raise ValueError("검토 종류는 human 또는 ai_suggestion이어야 합니다.")
        rubric = item.get("rubric", {})
        if set(rubric) != set(CRITERIA):
            raise ValueError("네 가지 평가 기준을 모두 저장해야 합니다.")
        any_rated = False
        for name, criterion in rubric.items():
            rating = criterion.get("rating")
            quotes = criterion.get("evidence_quotes")
            explanation = criterion.get("explanation")
            if rating not in RATINGS or not isinstance(quotes, list) or not all(isinstance(q, str) and q.strip() for q in quotes) or not isinstance(explanation, str):
                raise ValueError("평가 상태/인용/설명 형식이 잘못되었습니다: " + name)
            if any(q not in item["output_text"] for q in quotes):
                raise ValueError("인용문이 실제 출력에 없습니다: " + name)
            if rating != "unreviewed":
                any_rated = True
                if not explanation.strip():
                    raise ValueError("검토한 항목에는 판정 설명이 필요합니다: " + name)
                if rating in {"appropriate", "inappropriate"} and not quotes:
                    raise ValueError("적절/부적절 판정에는 출력의 실제 인용문이 필요합니다: " + name)
            elif quotes or explanation.strip():
                raise ValueError("근거를 작성했다면 판정을 선택해야 합니다: " + name)
        if any_rated and (not str(reviewer.get("id", "")).strip() or not item.get("reviewed_at")):
            raise ValueError("검토한 항목에는 검토자 ID와 검토 시각이 필요합니다.")


def _combined_rating(item: dict, criteria: tuple | dict) -> str:
    ratings = [item["rubric"][name]["rating"] for name in criteria]
    if "unreviewed" in ratings:
        return "unreviewed"
    if "inappropriate" in ratings:
        return "inappropriate"
    return "uncertain" if "uncertain" in ratings else "appropriate"


def overall_rating(item: dict) -> str:
    """교과 범위까지 네 기준을 모두 포함한 종합 판정."""
    return _combined_rating(item, CRITERIA)


def mathematical_appropriateness(item: dict) -> str:
    """교과 범위와 분리한 세 수학적 기준의 종합 판정."""
    return _combined_rating(item, MATHEMATICAL_CRITERIA)


def _rating_counts(ratings: list[str], eligible_count: int | None = None) -> dict:
    counts = {rating: ratings.count(rating) for rating in RATINGS}
    reviewed = len(ratings) - counts["unreviewed"]
    decisive = counts["appropriate"] + counts["inappropriate"]
    eligible_count = len(ratings) if eligible_count is None else eligible_count
    return {**counts, "reviewed_count": reviewed, "decisive_count": decisive,
            "eligible_count": eligible_count, "not_reviewed_count": eligible_count - reviewed,
            "reviewed_coverage": reviewed / eligible_count if eligible_count else None,
            "appropriate_rate_on_reviewed": counts["appropriate"] / reviewed if reviewed else None,
            "appropriate_rate_on_decisive": counts["appropriate"] / decisive if decisive else None}


def summarize_reviews(bundle: dict, private: dict) -> dict:
    validate_review_bundle(bundle)
    methods = sorted({entry["method"] for entry in private["mapping"].values()} |
                     {entry["method"] for entry in private.get("excluded_responses", [])})
    summary = {"rubric_version": RUBRIC_VERSION, "counts": bundle["counts"],
               "config_id": bundle.get("experiment_config_id"),
               "review_target_digest": bundle.get("review_target_digest"),
               "source_snapshot": bundle.get("source_snapshot"),
               "mathematical_criteria": list(MATHEMATICAL_CRITERIA),
               "scope": "Final answer grades are not used. API errors excluded. Unreviewed solutions never enter reviewed-rate denominators. AI suggestions and human reviews are separate.",
               "review_kinds": {}}
    for kind in ("human", "ai_suggestion"):
        summary["review_kinds"][kind] = {}
        for method in methods:
            items = [item for item in bundle["items"] if item["reviewer"]["kind"] == kind and private["mapping"][item["review_id"]]["method"] == method]
            if kind == "ai_suggestion":
                indexed = {item["review_id"]: item for item in bundle["items"]}
                imported = {entry["review_id"]: {**indexed[entry["review_id"]], **entry}
                            for entry in private.get("ai_suggestions", [])
                            if entry["review_id"] in indexed and private["mapping"][entry["review_id"]]["method"] == method}
                items = list({**{item["review_id"]: item for item in items}, **imported}.values())
            total_eligible = sum(private["mapping"][item["review_id"]]["method"] == method for item in bundle["items"])
            summary["review_kinds"][kind][method] = {
                "total_eligible_solutions": total_eligible, "eligible_in_this_review_kind": len(items),
                "missing_review_records": total_eligible - len(items),
                "overall": _rating_counts([overall_rating(item) for item in items], total_eligible),
                "mathematical_appropriateness": _rating_counts([mathematical_appropriateness(item) for item in items], total_eligible),
                "criteria": {name: _rating_counts([item["rubric"][name]["rating"] for item in items], total_eligible) for name in CRITERIA},
            }
    summary["ai_import"] = private.get("ai_import", {"accepted": 0, "rejected": []})
    return summary


def import_ai_suggestions(bundle: dict, private: dict, proposals: list[dict]) -> dict:
    """AI의 제안은 사람 검토와 별도로 보관한다. 대상 해시·실제 인용문을 검증한다.

    proposals 항목: id, method, output_sha256, criteria의 네 평가와
    rating/evidence/reason. evidence는 출력에서 복사한 문자열 또는 문자열 목록.
    잘못된 제안은 rejected에 남고 사람 판정이나 원본 응답을 바꾸지 않는다.
    """
    targets = {item["review_id"]: item for item in bundle["items"]}
    by_pair = {(entry["id"], entry["method"]): identifier for identifier, entry in private["mapping"].items()}
    accepted = {entry["review_id"]: entry for entry in private.get("ai_suggestions", []) if entry["review_id"] in targets}
    for identifier, entry in accepted.items():
        validate_review_bundle({"schema_version": 1, "rubric_version": RUBRIC_VERSION,
                                "items": [{**targets[identifier], **entry}]})
    rejected = []
    for proposal in proposals:
        pair = (proposal.get("id"), proposal.get("method"))
        try:
            identifier = by_pair.get(pair)
            if identifier is None:
                raise ValueError("해당 실험에 성공한 검토 대상이 없습니다.")
            target = targets[identifier]
            if proposal.get("output_sha256") != target["output_sha256"]:
                raise ValueError("검토한 출력 해시가 현재 출력과 다릅니다.")
            rubric = {}
            for name in CRITERIA:
                source = proposal.get("criteria", proposal.get("rubric", {})).get(name, {})
                quotes = source.get("evidence_quotes", source.get("evidence", []))
                if isinstance(quotes, str):
                    quotes = [quotes] if quotes.strip() else []
                rubric[name] = {"rating": source.get("rating"), "evidence_quotes": quotes,
                                "explanation": source.get("explanation", source.get("reason", ""))}
            suggestion = {"review_id": identifier, "output_sha256": target["output_sha256"],
                          "reviewer": {"id": proposal.get("reviewer_id") or "AI-assisted reviewer",
                                       "kind": "ai_suggestion", "provenance": proposal.get("reviewer_provenance", "AI-assisted proposal; not a human-verified judgment")},
                          "reviewed_at": proposal.get("reviewed_at") or _now(), "rubric": rubric,
                          "notes": proposal.get("notes", ""), "source_file": proposal.get("_source_file"),
                          "reported_overall_rating": proposal.get("overall_rating")}
            validate_review_bundle({"schema_version": 1, "rubric_version": RUBRIC_VERSION,
                                    "items": [{**target, **suggestion}]})
            suggestion["derived_overall_rating"] = overall_rating(suggestion)
            suggestion["derived_mathematical_appropriateness"] = mathematical_appropriateness(suggestion)
            accepted[identifier] = suggestion
        except (ValueError, TypeError, KeyError) as error:
            rejected.append({"id": pair[0], "method": pair[1], "output_sha256": proposal.get("output_sha256"),
                             "reason": str(error), "source_file": proposal.get("_source_file")})
    private["ai_suggestions"] = list(accepted.values())
    report = {"accepted": len(accepted), "rejected": rejected,
              "note": "AI-assisted suggestions only. Exact output-hash and evidence-quote checks are not independent verification of mathematical correctness."}
    private["ai_import"] = report
    return report


def review_json_schema() -> dict:
    """배포용 JSON Schema. 실제 인용문 포함 여부는 별도 검증 함수로 검사한다."""
    criterion = {"type": "object", "required": ["rating", "evidence_quotes", "explanation"],
                 "properties": {"rating": {"enum": list(RATINGS)}, "evidence_quotes": {"type": "array", "items": {"type": "string", "minLength": 1}}, "explanation": {"type": "string"}}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "MathHint solution review", "type": "object",
            "required": ["schema_version", "rubric_version", "items"], "properties": {
                "schema_version": {"const": 1}, "rubric_version": {"const": RUBRIC_VERSION},
                "items": {"type": "array", "items": {"type": "object",
                    "required": ["review_id", "question_id", "output_sha256", "output_text", "reviewer", "reviewed_at", "rubric"],
                    "properties": {"review_id": {"type": "string"}, "question_id": {"type": "string"},
                        "output_sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"}, "output_text": {"type": "string"},
                        "reviewed_at": {"type": ["string", "null"]},
                        "reviewer": {"type": "object", "required": ["id", "kind"], "properties": {"id": {"type": "string"}, "kind": {"enum": ["human", "ai_suggestion"]}}},
                        "rubric": {"type": "object", "required": list(CRITERIA), "additionalProperties": False,
                                   "properties": {name: criterion for name in CRITERIA}}}}}}}


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def export_review_files(bundle: dict, private: dict, output: Path) -> dict:
    validate_review_bundle(bundle)
    output.mkdir(parents=True, exist_ok=True)
    _write_json(output / "blind_reviews.json", bundle)
    private_path = output / "private_method_key.json"
    _write_json(private_path, private)
    private_path.chmod(0o600)
    _write_json(output / "solution_review_schema.json", review_json_schema())
    summary = summarize_reviews(bundle, private)
    _write_json(output / "solution_review_summary.json", summary)
    fields = ["review_id", "question_id", "output_sha256", "reviewer_id", "review_kind", "reviewed_at", "overall_rating", "mathematical_appropriateness"]
    fields += [name + suffix for name in CRITERIA for suffix in ("_rating", "_evidence_quotes", "_explanation")]
    with (output / "blind_reviews.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for item in bundle["items"]:
            row = {field: item.get(field) for field in ("review_id", "question_id", "output_sha256", "reviewed_at")}
            row.update(reviewer_id=item["reviewer"]["id"], review_kind=item["reviewer"]["kind"], overall_rating=overall_rating(item), mathematical_appropriateness=mathematical_appropriateness(item))
            for name in CRITERIA:
                row.update({name + "_" + field: json.dumps(value, ensure_ascii=False) if isinstance(value, list) else value
                            for field, value in item["rubric"][name].items()})
            writer.writerow(row)
    escaped = lambda value: html.escape(str(value))
    articles = []
    for item in bundle["items"]:
        controls = []
        for name, criterion in CRITERIA.items():
            saved = item["rubric"][name]
            options = "".join(f"<option value='{rating}' {'selected' if saved['rating'] == rating else ''}>{rating}</option>" for rating in RATINGS)
            quotes = "\n".join(saved["evidence_quotes"])
            controls.append(f"<fieldset data-criterion='{name}'><legend>{escaped(criterion['label'])}</legend><p>{escaped(criterion['guidance'])}</p>"
                            f"<label>판정 <select data-field='rating'>{options}</select></label>"
                            f"<label>출력에서 그대로 인용 (한 줄에 하나)<textarea data-field='evidence_quotes'>{escaped(quotes)}</textarea></label>"
                            f"<label>판정 설명<textarea data-field='explanation'>{escaped(saved['explanation'])}</textarea></label></fieldset>")
        articles.append(f"<article data-review-id='{item['review_id']}'><h2>{escaped(item['review_id'])} · {escaped(item['question_id'])}</h2>"
                        f"<p>{escaped(' / '.join(str(v) for v in item['curriculum_context'].values() if v))}</p>"
                        f"<details><summary>문제·교과 범위 메모</summary><pre>{escaped(item['problem_text'])}</pre><pre>{escaped(item['curriculum_notes'] or '확정된 수업 범위 메모 없음: 단원명만으로 범위를 단정하지 마세요.')}</pre></details>"
                        f"<h3>검토할 풀이</h3><pre>{escaped(item['output_text'])}</pre>"
                        f"<details><summary>원본 정답·해설</summary><pre>{escaped(item['reference_answer'])}</pre><pre>{escaped(item['reference_solution'])}</pre></details>"
                        + "".join(controls) + "</article>")
    data = json.dumps(bundle, ensure_ascii=False).replace("<", "\\u003c").replace("&", "\\u0026")
    script = """
const packet=JSON.parse(document.getElementById('packet').textContent);
document.getElementById('save').onclick=()=>{try{
 const reviewer=document.getElementById('reviewer').value.trim();
 document.querySelectorAll('article').forEach(article=>{
  const item=packet.items.find(x=>x.review_id===article.dataset.reviewId);let rated=false;
  const original=JSON.stringify(item.rubric);
  article.querySelectorAll('fieldset').forEach(field=>{
   const rating=field.querySelector('[data-field=rating]').value;
   const quotes=field.querySelector('[data-field=evidence_quotes]').value.split('\\n').map(x=>x.trim()).filter(Boolean);
   const explanation=field.querySelector('[data-field=explanation]').value.trim();
   if(quotes.some(q=>!item.output_text.includes(q)))throw Error(item.question_id+': 인용문이 실제 출력에 없습니다.');
   if(rating!=='unreviewed'){
    rated=true;if(!explanation)throw Error('검토한 항목의 설명을 작성하세요.');
    if(['appropriate','inappropriate'].includes(rating)&&!quotes.length)throw Error('적절/부적절 판단의 인용문이 필요합니다.');
   }else if(quotes.length||explanation)throw Error('근거를 작성한 항목의 판정을 선택하세요.');
   item.rubric[field.dataset.criterion]={rating,evidence_quotes:quotes,explanation};
  });
  if(rated&&original!==JSON.stringify(item.rubric)){if(!reviewer)throw Error('검토자 ID를 입력하세요.');item.reviewer={id:reviewer,kind:'human'};item.reviewed_at=new Date().toISOString();}
  if(!rated){item.reviewer={id:'',kind:'human'};item.reviewed_at=null;}
 });
 const url=URL.createObjectURL(new Blob([JSON.stringify(packet,null,2)+'\\n'],{type:'application/json'}));
 const link=document.createElement('a');link.href=url;link.download='completed_solution_reviews.json';link.click();URL.revokeObjectURL(url);
}catch(error){alert(error.message);}};
"""
    page = ("<!doctype html><html lang='ko'><meta charset='utf-8'><meta name='viewport' content='width=device-width'>"
            "<title>풀이 적절성 블라인드 검토</title><style>body{font-family:system-ui,sans-serif;max-width:1000px;margin:30px auto;padding:0 20px;background:#fff;color:#111}"
            "pre{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.6;font-family:inherit}article{border-top:2px solid #111;margin-top:32px;padding-top:12px}"
            "fieldset{border:1px solid #aaa;margin:15px 0}label{display:block;margin:10px 0}textarea{display:block;width:98%;min-height:65px;font:inherit}"
            "button,input,select{font:inherit;padding:6px}.toolbar{position:sticky;top:0;background:white;border-bottom:1px solid #111;padding:10px}</style>"
            "<h1>풀이 적절성 블라인드 검토</h1><p>정답 여부와 별도로 네 기준을 검토하세요. 실제 검토 전에는 모두 unreviewed이며 API 오류는 평가 대상에서 제외됩니다.</p>"
            "<p>방법·토큰·자동 채점은 숨겨져 있습니다. 출력 내용만으로 생성 방식을 추측할 가능성은 남습니다. 근거 인용과 설명을 남겨 주세요.</p>"
            f"<p>루브릭 버전: {RUBRIC_VERSION} · 검토 가능한 풀이 {len(bundle['items'])}개</p>"
            "<div class='toolbar'><label>검토자 ID <input id='reviewer' placeholder='이름 또는 연구용 ID'></label><button id='save'>작성한 검토 JSON 다운로드</button></div>"
            + "".join(articles) + f"<script type='application/json' id='packet'>{data}</script><script>{script}</script></html>")
    (output / "blind_review.html").write_text(page, encoding="utf-8")
    if private.get("ai_suggestions"):
        ai_rows = []
        for suggestion in private["ai_suggestions"]:
            ai_rows.append({**private["mapping"][suggestion["review_id"]], **suggestion})
        _write_json(output / "ai_suggested_reviews.json", {"rubric_version": RUBRIC_VERSION,
                    "warning": "AI-assisted proposals, not human-verified ground truth. Separate from blind human review.", "records": ai_rows})
        with (output / "ai_suggested_reviews.csv").open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=["id", "method", *fields])
            writer.writeheader()
            for suggestion in ai_rows:
                row = {name: suggestion.get(name) for name in ("id", "method", "review_id", "output_sha256", "reviewed_at")}
                row.update(question_id=suggestion["id"], reviewer_id=suggestion["reviewer"]["id"], review_kind="ai_suggestion", overall_rating=overall_rating(suggestion), mathematical_appropriateness=mathematical_appropriateness(suggestion))
                for name in CRITERIA:
                    row.update({name + "_" + field: json.dumps(value, ensure_ascii=False) if isinstance(value, list) else value
                                for field, value in suggestion["rubric"][name].items()})
                writer.writerow(row)
        details = []
        for suggestion in ai_rows:
            criteria = "".join(f"<h3>{escaped(CRITERIA[name]['label'])}: {escaped(criterion['rating'])}</h3><blockquote>{escaped(chr(10).join(criterion['evidence_quotes']))}</blockquote><p>{escaped(criterion['explanation'])}</p>"
                               for name, criterion in suggestion["rubric"].items())
            details.append(f"<article><h2>{escaped(suggestion['id'])} / {escaped(suggestion['method'])}</h2><p>수학적 적절성(논리·설명·일관성): {escaped(mathematical_appropriateness(suggestion))} / 교과 범위: {escaped(suggestion['rubric']['curriculum_scope']['rating'])} / 네 기준 종합: {escaped(overall_rating(suggestion))}</p>{criteria}<p>검토자: {escaped(suggestion['reviewer'])}</p></article>")
        (output / "ai_suggested_review.html").write_text("<!doctype html><html lang='ko'><meta charset='utf-8'><title>AI 보조 풀이 검토</title><style>body{font-family:system-ui;max-width:1000px;margin:30px auto;padding:20px;color:#111;background:#fff}article{border-top:2px solid #111;margin-top:30px}blockquote{white-space:pre-wrap}</style><h1>AI 보조 풀이 검토 제안</h1><p>사람이 검증한 정답 판정이 아닙니다. 실제 인용·출력 해시를 확인한 AI 제안이며, 블라인드 사람 검토와 별도로 집계합니다.</p>" + "".join(details) + "</html>", encoding="utf-8")
    return summary


def main() -> None:
    # 1. 응답과 참고 자료, 이전에 작성한 사람 검토를 읽는다.
    snapshot = {}
    records = load_latest_records(GENERATION / "responses.jsonl", snapshot)
    config_path = GENERATION / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    config = config.get("config", config)
    metadata = json.loads(METADATA.read_text(encoding="utf-8"))["records"] if METADATA.exists() else []
    previous_path = REVIEWS or OUTPUT / "blind_reviews.json"
    previous = json.loads(previous_path.read_text(encoding="utf-8")) if REVIEWS or previous_path.exists() else None
    notes = CURRICULUM_NOTES.read_text(encoding="utf-8") if CURRICULUM_NOTES else ""
    expected = len(config["test_ids"]) * len(config.get("methods", ["baseline", "regression_hint"])) if "test_ids" in config else None

    # 2. 생성 방식을 가린 검토 자료를 만든다. 이전 판정은 같은 출력에만 연결한다.
    bundle, private = build_review_bundle(records, metadata={row["id"]: row for row in metadata},
                                         curriculum_notes=notes, expected_responses=expected, previous=previous)
    bundle["source_snapshot"] = snapshot
    if REVIEWS:
        unknown = {item["review_id"] for item in previous["items"]} - set(private["mapping"])
        if unknown:
            raise ValueError("지정한 검토 파일에 현재 실험과 다른 출력의 검토가 있습니다.")

    # 3. AI 제안을 읽고, 출력 해시와 실제 인용문을 확인한다.
    old_key = OUTPUT / "private_method_key.json"
    if old_key.exists():
        previous_private = json.loads(old_key.read_text(encoding="utf-8"))
        private["ai_suggestions"] = [entry for entry in previous_private.get("ai_suggestions", []) if entry["review_id"] in private["mapping"]]
    proposals = []
    for path in AI_REVIEWS:
        value = json.loads(path.read_text(encoding="utf-8"))
        value = value.get("records", value.get("reviews", [])) if isinstance(value, dict) else value
        if not isinstance(value, list):
            raise ValueError("AI 검토 파일은 목록 또는 records 목록이어야 합니다.")
        proposals.extend({**row, "_source_file": str(path)} for row in value)
    if proposals or private.get("ai_suggestions"):
        import_ai_suggestions(bundle, private, proposals)

    # 4. 사람 검토와 AI 제안을 나누어 HTML·CSV·요약을 저장한다.
    summary = export_review_files(bundle, private, OUTPUT)
    print(json.dumps({"output": str(OUTPUT), "counts": summary["counts"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
