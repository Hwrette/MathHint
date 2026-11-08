"""생성 비교의 표·HTML·그림을 만든다. API 요청이나 채점은 하지 않는다."""

import csv
import html
import json
from pathlib import Path


def plot_comparison(output: Path, summary: dict) -> None:
    """정답률과 실제 API 사용량을 흑백 PNG/PDF로 저장한다."""
    if not any(value["recorded"] for value in summary["methods"].values()):
        return
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    methods = list(summary["methods"])
    labels = ["Problem only", "+ Predicted frequencies"]
    figure, axis = plt.subplots(figsize=(7.5, 4.5))
    scores = [summary["methods"][method]["accuracy_on_graded"] for method in methods]
    for index, score in enumerate(scores):
        if score is not None:
            axis.bar(index, score * 100, color="white" if index == 0 else "0.6", edgecolor="black", width=.55)
            details = summary["methods"][methods[index]]
            axis.text(index, score * 100 + 2, f"{details['correct']}/{details['graded']}", ha="center")
    axis.set(xticks=[0, 1], xticklabels=labels, ylabel="Correct final answers (% of gradable responses)", ylim=(0, 110))
    axis.spines[["top", "right"]].set_visible(False)
    figure.tight_layout()
    for suffix in ("png", "pdf"):
        figure.savefig(output / ("accuracy_comparison." + suffix), dpi=180)
    plt.close(figure)

    fields = ("prompt_token_count", "candidates_token_count", "thoughts_token_count", "total_token_count")
    figure, axis = plt.subplots(figsize=(9, 4.8))
    for method_index, method in enumerate(methods):
        values = [summary["methods"][method]["usage"][field]["successful_response_mean"] for field in fields]
        for index, value in enumerate(values):
            if value is not None:
                axis.bar(index + (method_index - .5) * .34, value, width=.32,
                         color="white" if method_index == 0 else "0.6", edgecolor="black",
                         label=labels[method_index] if index == 0 else None)
    axis.set(xticks=range(4), xticklabels=["Input", "Answer", "Thinking", "Total"],
             ylabel="Mean reported tokens per successful response")
    axis.spines[["top", "right"]].set_visible(False)
    axis.legend(frameon=False)
    figure.tight_layout()
    for suffix in ("png", "pdf"):
        figure.savefig(output / ("token_comparison." + suffix), dpi=180)
    plt.close(figure)


def render_reports(output, records, config, summary, methods, usage_fields, *, charts=True):
    fields = ["id", "method", "response_origin", "started_at", "completed_at", "subject", "unit", "type", "reference_answer_text",
              "predicted_answer", "correct", "status", "grading_status", *usage_fields,
              "latency_seconds", "input_file", "output_file", "reference_file"]
    with (output / "comparison.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in records:
            writer.writerow({**{field: row.get(field) for field in fields},
                             "predicted_answer": row["evaluation"].get("predicted_answer"),
                             "correct": row["evaluation"].get("correct"),
                             "grading_status": row["evaluation"].get("status"),
                             **{field: row["usage"].get(field) for field in usage_fields},
                             **{field: f"questions/{row['id']}/{row['method']}/{filename}"
                                for field, filename in (("input_file", "input.txt"), ("output_file", "output.txt"),
                                                        ("reference_file", "reference_solution.txt"))}})
    escaped = lambda value: html.escape(str(value))
    rows = []
    indexed = {(row["id"], row["method"]): row for row in records}
    for identifier in config["test_ids"]:
        pair = [indexed.get((identifier, method)) for method in methods]
        first = next((row for row in pair if row), None)
        if first is None:
            continue
        columns = []
        for method, row in zip(methods, pair):
            if row is None:
                columns.append(f"<section data-method='{method}' data-grade='pending'><h3>{method}</h3><p>아직 실행하지 않음</p></section>")
                continue
            evaluation = row["evaluation"]
            usage = row["usage"]
            columns.append(
                f"<section data-method='{method}' data-grade='{escaped(evaluation.get('status'))}'><h3>{method}</h3><p>판정: {escaped(evaluation.get('status'))} · "
                f"추출 정답: {escaped(evaluation.get('predicted_answer'))} · "
                f"입력/출력/추론/전체 토큰: {escaped(usage.get('prompt_token_count'))}/"
                f"{escaped(usage.get('candidates_token_count'))}/{escaped(usage.get('thoughts_token_count'))}/"
                f"{escaped(usage.get('total_token_count'))}</p>"
                f"<p>응답 출처: {'동일 조건의 기존 대조군 재사용' if row.get('response_origin') == 'reused_control' else '새 API 요청'} · "
                f"실제 생성 시각: {escaped(row.get('completed_at'))}</p>"
                f"<details><summary>실제 API 입력 전체</summary><pre>{escaped(row['input_text'])}</pre></details>"
                f"<details><summary>출력 풀이 전체</summary><pre>{escaped(row['output_text'] or str(row.get('error')))}</pre></details>"
                f"<details><summary>판정 근거와 전체 사용량</summary><pre>{escaped(json.dumps({'evaluation':evaluation,'usage':usage},ensure_ascii=False,indent=2))}</pre></details></section>")
        rows.append(f"<article data-search='{escaped(identifier + ' ' + str(first['subject']) + ' ' + str(first['unit']) + ' ' + str(first['type']))}'><h2>{escaped(identifier)} · 실제 정답 {escaped(first['reference_answer_text'])}</h2>"
                    f"<p>{escaped(first['subject'])} / {escaped(first['unit'])} / {escaped(first['type'])}</p>"
                    f"<details><summary>문제·원본 정답해설</summary><pre>{escaped(first['problem_text'])}</pre>"
                    f"<hr><pre>{escaped(first['reference_solution'])}</pre></details><div class='pair'>"
                    + "".join(columns) + "</div></article>")
    document = ("<!doctype html><html lang='ko'><meta charset='utf-8'><meta name='viewport' content='width=device-width'>"
                "<title>MathHint 풀이 생성 비교</title><style>body{max-width:1400px;margin:32px auto;padding:0 20px;"
                "font-family:system-ui,sans-serif;color:#111;background:#fff}article{border-top:2px solid #111;margin-top:32px}"
                ".pair{display:grid;grid-template-columns:1fr 1fr;gap:24px}section{min-width:0}pre{white-space:pre-wrap;"
                "overflow-wrap:anywhere;font-family:inherit;line-height:1.65}details{border:1px solid #bbb;padding:10px;margin:10px 0}"
                "@media(max-width:800px){.pair{grid-template-columns:1fr}}@media print{details{break-inside:avoid}"
                ".pair{display:block}article{break-before:page}}</style><h1>풀이 생성 비교</h1>"
                f"<p>모델 {escaped(config['model'])} · 추론 {escaped(config['thinking_level'])}. "
                "정확도는 최종 정답 자동 비교이며 풀이의 교육과정 적합성·논리 검증은 별도 확인이 필요합니다.</p>"
                "<p><label>검색 <input id='search' placeholder='문항 ID·단원·유형'></label> "
                "<label>조건 <select id='method'><option value=''>전체</option><option value='baseline'>기본</option>"
                "<option value='regression_hint'>회귀 벡터 추가</option></select></label> "
                "<label>판정 <select id='grade'><option value=''>전체</option><option value='correct'>정답</option>"
                "<option value='incorrect'>오답</option><option value='ungradable'>자동 판정 불가</option></select></label></p>"
                "<details><summary>비교 요약과 사용량 집계</summary><pre>" + escaped(json.dumps(summary, ensure_ascii=False, indent=2))
                + "</pre></details>" + "".join(rows)
                + "<script>function filter(){let q=document.getElementById('search').value.toLowerCase(),"
                "m=document.getElementById('method').value,g=document.getElementById('grade').value;"
                "document.querySelectorAll('article').forEach(a=>{let n=0;a.querySelectorAll('section').forEach(s=>{"
                "s.hidden=!!((m&&s.dataset.method!==m)||(g&&s.dataset.grade!==g));if(!s.hidden)n++;});"
                "a.hidden=!n||!a.dataset.search.toLowerCase().includes(q);});}"
                "['search','method','grade'].forEach(id=>document.getElementById(id).addEventListener('input',filter));</script>"
                "<script>window.MathJax={tex:{inlineMath:[['$','$'],['\\\\(','\\\\)']],displayMath:[['$$','$$'],['\\\\[','\\\\]']]},"
                "options:{skipHtmlTags:['script','noscript','style','textarea','code']}};</script>"
                "<script defer src='https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js'></script></html>")
    (output / "report.html").write_text(document, encoding="utf-8")
    if charts:
        plot_comparison(output, summary)
    return summary
