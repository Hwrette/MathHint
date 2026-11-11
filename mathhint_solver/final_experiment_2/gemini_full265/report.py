"""전체265 A/B/C/D의 저장 응답만 읽는 보고서. 학습·API 호출은 없다."""

from collections import Counter
from pathlib import Path

from ..gemini_comparison import report as shared
from ..gemini_comparison.review import build_reviews, write_cases, write_csv
from ..gemini_comparison.viewer import build as build_viewer, METHODS
from ...CompareGeneration import write_json


def aggregate_questions(questions):
    """공유 집계 함수의 test 그룹을 임시로 사용한다. 원래 분할·응답은 바꾸지 않는다."""
    return [{**question, "split": "test"} for question in questions if question["expected_generation"]]


def all_scope_metrics(questions):
    combined = aggregate_questions(questions)
    summary, tokens = shared.summaries(combined)
    pairs = shared.paired_tests(combined)
    for row in (*summary, *tokens, *pairs):
        row["split"] = "all265"
    return summary, tokens, pairs


def build_full_viewer(output, payload):
    """원래 안전 렌더러를 쓰고 전체 범위의 제목·초기 선택만 표시용으로 바꾼다."""
    output = Path(output)
    result = build_viewer(output, payload)
    text = result.read_text(encoding="utf-8")
    replacements = {
        "<title>MathHint Final Experiment 2 · A/B/C/D 풀이 비교</title>":
            "<title>MathHint 전체265 · A/B/C/D 풀이 비교</title>",
        "<h1>A/B/C/D 문항별 풀이 비교</h1>":
            "<h1>전체265문항 · A/B/C/D 풀이 비교</h1>",
        '<option value="all">전체 문항</option>':
            '<option value="all" selected>전체265문항 · 학습185+테스트80</option>',
        "원본 정답 판정과 풀이 검토를 분리합니다.</p>":
            "원본 정답 판정과 풀이 검토를 분리합니다. 학습185는 인샘플 예측이며 전체265는 일반화 성능이 아닙니다.</p>",
    }
    for old, new in replacements.items():
        if text.count(old) != 1:
            raise ValueError("전체265 화면의 공통 렌더러 확장 위치가 바뀌었습니다: " + old[:60])
        text = text.replace(old, new, 1)
    result.write_text(text, encoding="utf-8")
    script = output / "viewer_assets/viewer.js"
    source = script.read_text(encoding="utf-8")
    old = "applyFilter(byId.has(initial)?initial:(data.test_ids||[])[0]);"
    new = "applyFilter(byId.has(initial)?initial:(questions[0]||{}).id);"
    if source.count(old) != 1:
        raise ValueError("전체265 화면의 최초 문항 선택 확장 위치가 바뀌었습니다.")
    script.write_text(source.replace(old, new, 1), encoding="utf-8")
    return result


def _overall_figures(output, summary):
    from mathhint_learning.ClusterReport import setup_final_plots
    plt = setup_final_plots()
    folder = Path(output) / "figures"
    folder.mkdir(exist_ok=True)
    colors = [".8", ".6", ".4", ".2"]
    counts = [row["success_count"] for row in summary]
    progress = f"조건별 성공 {min(counts)}~{max(counts)}/265" if min(counts) != max(counts) else f"조건별 성공 {counts[0]}/265"
    fig, ax = plt.subplots(figsize=(8, 4.8), constrained_layout=True)
    for i, row in enumerate(summary):
        value = row["accuracy_graded"]
        if value is None:
            ax.text(i, .02, "채점 가능 응답 없음", ha="center", rotation=90)
        else:
            ax.bar(i, value, color=colors[i], edgecolor="black")
            ax.text(i, value+.025, f"{value:.1%}\n{row['correct_count']}/{row['graded_count']}", ha="center", fontsize=9)
    ax.set(xticks=range(4), xticklabels=list("ABCD"), ylim=(0, 1.18), ylabel="정답 / 채점 가능 성공 응답",
           title=f"전체265 계획 · {progress}\n학습185+테스트80 혼합 참고값 · 일반화 성능이 아님")
    fig.savefig(folder / "accuracy_all265.png", dpi=200); plt.close(fig)
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.5), constrained_layout=True)
    for ax, field in zip(axes, ("prompt_token_count", "candidates_token_count", "total_token_count")):
        available = []
        for i, row in enumerate(summary):
            value = row[field + "_mean"]
            if value is None:
                ax.text(i, .02, "미제공", ha="center", rotation=90, transform=ax.get_xaxis_transform())
            else:
                available.append(value)
                ax.bar(i, value, color=colors[i], edgecolor="black")
                ax.text(i, value, f"{value:.1f}", ha="center", fontsize=8)
        ax.set(xticks=range(4), xticklabels=list("ABCD"), title=shared.TOKEN_LABELS[field]+" 토큰",
               ylabel="성공 응답의 제공된 값 평균", ylim=(0, max(available)*1.2 if available and max(available) else 1))
    fig.suptitle(f"전체265 계획 · {progress}\n성공 응답 참고 평균 · 미제공=null · 실패 사용량을0으로 채우지 않음")
    fig.savefig(folder / "tokens_all265.png", dpi=200); plt.close(fig)


def _table(rows):
    result = ["|조건|성공/계획|채점 가능|정답|정답률|평균 입력|평균 출력|평균 전체|",
              "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for row in rows:
        result.append("|" + "|".join([row["label"], f"{row['success_count']}/{row['expected_count']}",
            str(row["graded_count"]), str(row["correct_count"]), shared._fmt(row["accuracy_graded"], percent=True),
            *[shared._fmt(row[field+"_mean"]) for field in ("prompt_token_count", "candidates_token_count", "total_token_count")]]) + "|")
    return result


def key_comparison(questions, state):
    """문항 전체가 갖춰진 A↔조건 쌍만 효과를 요약하고 나머지는 분모만 표시한다."""
    selected = [q for q in questions if q["expected_generation"]]
    if not selected:
        return ["## 핵심 비교 · A 기준", "", "아직 비교할 저장 문항이 없다.", ""]
    methods = {method["condition"]: method["key"] for method in METHODS}
    def response(question, condition):
        return question["conditions"].get(methods[condition]) or {}
    complete = not state.get("pending_count", 0) and all(
        response(q, c).get("status") == "success" for q in selected for c in "ABCD")
    rows, pending_rows = [], []
    for condition in "BCD":
        successful = [(response(q, "A"), response(q, condition)) for q in selected
                      if response(q, "A").get("status") == response(q, condition).get("status") == "success"]
        graded = [(a, b) for a, b in successful
                  if all(type(r.get("evaluation", {}).get("correct")) is bool for r in (a, b))]
        provided = [(a["usage"]["total_token_count"], b["usage"]["total_token_count"]) for a, b in successful
                    if all(r.get("usage", {}).get("total_token_count") is not None for r in (a, b))]
        values = [condition, f"{len(graded)}/{len(selected)}"]
        if len(successful) == len(graded) == len(provided) == len(selected):
            gain = sum(not a["evaluation"]["correct"] and b["evaluation"]["correct"] for a, b in graded)
            loss = sum(a["evaluation"]["correct"] and not b["evaluation"]["correct"] for a, b in graded)
            difference = sum(b-a for a, b in provided)
            baseline = sum(a for a, _ in provided)
            values += [f"{gain} / {loss} / {gain-loss:+d}" if graded else "—", f"{len(provided)}/{len(selected)}",
                       f"{difference/len(provided):+.2f}" if provided else "—",
                       f"{difference/baseline*100:+.2f}%" if provided and baseline else "—"]
            rows.append("|" + "|".join(values) + "|")
        else:
            values.append(f"{len(provided)}/{len(selected)}")
            pending_rows.append("|" + "|".join(values) + "|")
    train = sum(q["split"] == "train" for q in selected)
    test = sum(q["split"] == "test" for q in selected)
    lines = ["## 핵심 비교 · A 기준", "",
             f"전체{len(selected)}는 학습{train} + 테스트{test}의 혼합 참고값이며, 학습 문항의 B/C는 인샘플 예측이므로 일반화 성능이 아니다."]
    if rows:
        lines += ["다음은 A와 해당 조건의 전체 문항에 성공·채점·전체 토큰 사용량이 모두 갖춰진 대응 비교이며, 다른 조건의 완료를 기다려 섞지 않는다. A 토큰 분모가 없는 값은 —다.", "",
                  "|A 대비 조건|공통 채점/전체|개선 / 악화 / 순변화(문항)|사용량 공통/전체|평균 전체토큰 차이|전체토큰 변화율|",
                  "|---|---:|---:|---:|---:|---:|", *rows, ""]
    if pending_rows:
        lines += ["**아래 미완료 비교의 완료 집합은 조건 우선순위·ID 실행 순서·실패에 영향을 받아 무작위 하위표본이 아니며, 해당 조건의 전체 효과를 확정할 수 없어 공통 비교 분모만 표시한다.**", "",
                  "|미완료 A 대비 조건|공통 채점/전체|사용량 공통/전체|", "|---|---:|---:|", *pending_rows, ""]
    conflicts = sum(bool(q.get("answer_key_conflict")) for q in selected)
    if complete and conflicts:
        scores = []
        for condition in "ABCD":
            graded = [response(q, condition) for q in selected
                      if type(response(q, condition).get("evaluation", {}).get("correct")) is bool]
            scores.append(f"{condition} {sum(r.get('correct_ai_supplemental') is True for r in graded)}/{len(graded)}")
        lines += [f"원본 키 충돌 {conflicts}문항의 주 점수는 원본 그대로 유지하고, AI 보조 대안 기준 점수만 별도로 계산하면 "
                  + ", ".join(scores) + "이며 사람의 확정 답안표나 주 점수 대체로 취급하지 않는다."]
    else:
        lines += ["주 점수는 원본 정답표 기준이며, 원본 키 충돌의 AI 보조 대안 점수는 별도 CSV 열로 분리해 섞지 않는다."]
    return lines + [""]


def execution_notice(state, questions=()):
    """저장된 실행 상태를 먼저 보여 준다. 대기시각을 공급자 초기화시각으로 바꾸지 않는다."""
    pending = state.get("pending_count", 1060)
    if not pending:
        return []
    failures = state.get("failed_requests", 0)
    quota_blocked = state.get("status") == "daily_quota_exhausted"
    lines = ["## 현재 실행 상태", "",
             "**일일 할당량 제한으로 중단 · 전체 실험 미완료**" if quota_blocked else "**부분 완료 · 전체 실험 미완료**", "",
             f"성공 **{state.get('successful_requests', 0)}/{state.get('expected_requests', 1060)}** "
             f"(기존80 재사용 {state.get('reused_successes', 0)} + 신규 {state.get('new_successes', 0)}), "
             f"미완료 **{pending}**(마지막 실패 {failures} + 미실행 {pending-failures})다. "
             "기존80 결과는 그대로 보존했으며, 미완료 조건의 전체265 효과를 확정하지 않는다.", ""]
    order = state.get("condition_order")
    if order:
        lines += ["현재 요청 우선순서: **" + " → ".join(order) + "**. 각 조건의 미완료 전체 문항을 먼저 실행하고, 같은 조건 안에서는 기존 문항 순서를 유지한다. "
                  "조건 의미는 A 문제만 / B 선형회귀 / C 딥러닝(MLP) / D 실제 해설(오라클)로 유지한다.", ""]
    pending_by_condition = state.get("pending_by_condition") or {}
    selected = [q for q in questions if q["expected_generation"]]
    if pending_by_condition:
        expected = len(selected) if selected else state.get("expected_requests", 1060) // len(METHODS)
        lines += ["|조건|성공/계획|미완료|", "|---|---:|---:|"]
        for condition in order or "ABCD":
            method = next(m for m in METHODS if m["condition"] == condition)
            missing = pending_by_condition.get(condition)
            success = sum((q["conditions"].get(method["key"]) or {}).get("status") == "success" for q in selected) if selected else (
                expected-missing if missing is not None else None)
            lines.append(f"|{method['label']}|{success if success is not None else '—'}/{expected}|{missing if missing is not None else '—'}|")
        lines.append("")
    failed = [r for r in state.get("pending_requests", []) if r.get("last_status") not in (None, "not_executed")]
    if failed:
        lines += ["재시도할 마지막 실패: " + ", ".join(f"`{r['condition']}/{r['id']}`" for r in failed) + ".", ""]
    observation = state.get("provider_quota_observation") or {}
    if observation and not quota_blocked:
        lines += ["[과거429 관측 기록](state.json)은 보존한다. 이 과거 기록만으로 현재도 할당량에 차단됐다고 판단하지 않으며, 현재 실행 상태와 새 응답을 기준으로 확인한다.", ""]
    if quota_blocked:
        violations = observation.get("quota_violations", [])
        if violations:
            lines += ["실제429 응답에서 관측한 제한은 다음과 같다. 공급자의 전체 호출·토큰 한도나 남은 예산을 확인한 것은 아니다.", "",
                      "|관측 항목|저장된 값|", "|---|---|"]
            for violation in violations:
                identifier = violation.get("quota_id") or violation.get("quota_metric") or "미제공"
                label = "무료 일일 요청 한도" if "free" in identifier.lower() and "day" in identifier.lower() else "관측 할당량"
                value = violation.get("quota_value")
                lines.append(f"|{label}|{value if value is not None else '미제공'} · 모델 `{observation.get('model') or '미제공'}` · `{identifier}`|")
            delay = observation.get("retry_info_delay_seconds")
            lines += [f"|RetryInfo 대기|{str(delay)+'초' if delay is not None else '미제공'}|",
                      f"|응답에서 계산한 이른 재시도 시각|`{observation.get('earliest_retry_from_response') or '미제공'}`|",
                      f"|기록된 안전 대기 시각|`{observation.get('recorded_cooldown_until') or '미제공'}`|", "",
                      "위 시각은 응답의 재시도 지시와 로컬 안전 여유를 보존한 값이며, **공급자가 확정한 일일 한도 초기화 시각이 아니다.** "
                      "로컬 RPD 설정은 공급자 실제 한도와 구분한다. [429 원문·근거 해시 및 재개 상태](state.json)를 확인한다.", ""]
        lines += ["공급자 일일 제한과 기록된 재시도 대기를 확인한 뒤 아래 명령으로 미완료 요청만 재개한다. 성공 응답은 재호출하지 않으며, 자동 재개 예약은 설정하지 않았다.", "",
                  "```bash", state["resume_command"], "```", ""]
    return lines


def _readme(output, config, state, summary, review_rows, cases, questions):
    scopes = {scope: [row for row in summary if row["split"] == scope] for scope in ("all265", "train", "test")}
    execution_link = "[실행 이력](execution_runs/)" if (Path(output) / "execution_runs").is_dir() else "실제 실행 기록은 아직 없음"
    lines = ["# 전체265문항 Gemini A/B/C/D 비교", "",
        "A 문제만 · B 확정 선형회귀 예측 토큰 · C 확정 MLP 예측 토큰 · D 실제 원본 해설 토큰(오라클).", ""]
    lines += execution_notice(state, questions)
    lines += [
        "기존 [테스트80 결과](../gemini_comparison/README.md)는 보존했다. 동일한320개 요청의 성공 응답·사용량·검토 기록을 출처 해시로 재사용하고 학습185×4조건을 추가한다. 모델 재학습·어휘 변경·문제 원문 변경은 없다.", "",
        "**전체265는 학습185와 테스트80의 혼합 참고 결과다. 학습185의 B/C는 해당 모델이 학습했던 문항의 인샘플 예측이며 새로운 문제의 일반화 성능이 아니다.** 테스트80은 기존 평가로 별도 표시한다. D는 정답 해설 정보가 있는 진단 조건이다.", "",
        "먼저 [수식 비교 화면](report.html), [문항265개 비교 CSV](question_comparison.csv), [풀이·오류 사례](case_reports/README.md)를 연다.", ""]
    lines += key_comparison(questions, state)
    lines += ["## 전체265 · 혼합 참고 결과", "", *_table(scopes["all265"]), "",
        "![전체265 정답률](figures/accuracy_all265.png)", "", "![전체265 사용량](figures/tokens_all265.png)", ""]
    for scope, title in (("train", "학습185 · 인샘플 예측"), ("test", "기존 테스트80 · 저장 성공 응답 재사용")):
        lines += ["## " + title, "", *_table(scopes[scope]), "",
            f"![{title} 정답률](figures/accuracy_{scope}.png)", "", f"![{title} 사용량](figures/tokens_{scope}.png)", "",
            f"[이 범위의 문항별 CSV](question_comparison_{scope}.csv) · [토큰 차이 그림](figures/token_differences_{scope}.png)", ""]
    lines += ["## 실행·재사용·재개", "", f"상태: **{state.get('status', 'unknown')}** · 성공 {state.get('successful_requests', 0)}/1060 · 미완료 {state.get('pending_count', 1060)}. " + (state.get("reason") or ""), "",
        "무료 API라도 공급자 요청·토큰 한도는 존재한다. 상단의 실제429 관측값은 공급자 할당량 전체를 확인했다는 뜻은 아니다. 로컬 실행 상한(예: RPD1400)은 공급자 한도가 아니며, 실제429/503·Retry-After/RetryInfo와 구분해 기록한다.", "",
        "모델은 `gemini-3.1-flash-lite`, temperature0, thinking minimal, max output8192이며 A/B/C/D 문제 원문과 기본 시스템 지시가 동일하다. B/C/D는 동일한 양수·음수보정·상위20·반올림전순위·어휘순동점·소수3자리 규칙을 사용한다.", "",
        "[설정](config.json) · [실제 요청 감사](prompt_audit/) · [응답 원문](responses.jsonl) · [실행 상태/미완료 목록](state.json) · " + execution_link + " · [기존 자료 보존 해시](preservation_manifest.json) · [검증](validation.json)", "",
        "```bash", "python -m mathhint_solver.final_experiment_2.gemini_full265 preflight",
        "python -m mathhint_solver.final_experiment_2.gemini_full265 generate",
        "python -m mathhint_solver.final_experiment_2.gemini_full265 report",
        "python -m mathhint_solver.final_experiment_2.gemini_full265 verify", "```", "",
        "report/verify는 저장 자료만 읽어 학습이나 API 호출을 시작하지 않는다. generate는 동일 성공 요청을 건너뛰고 미완료만 재개한다. 중단 파일이 있다면 state.json의 정확한 재개 명령을 따른다. 예약 자동 재개는 별도로 설정하지 않았다.", "",
        "## 집계와 해석", "",
        "정답률 분모는 채점 가능한 성공 응답이다. 실패·미완료·채점 불가를 오답으로 대체하지 않는다. 토큰의 평균 분모는 해당 필드가 실제 제공된 성공 응답 수이고 미제공은 null/—다. 추론·캐시 토큰을 전체 토큰에 더하지 않는다. 전체265 평균은 문항·제공 수를 기준으로 합쳐 계산하며185와80의 평균을 단순 평균하지 않는다.", "",
        "[전체/분할 핵심 수치](summary.csv) · [사용량 합계·제공 수](token_summary.csv) · [6쌍 대응 비교](paired_comparison.csv)", "",
        "대응 검정은 각 범위에서 양쪽 성공·채점 가능한 같은 문항만 사용하고 범위별6쌍에 Holm 보정을 적용한다. 세 범위는 서로 겹치는 탐색 요약이며 독립 표본이 아니다. 작은 정오답 변화의 검정력 한계, 과거80 재사용과 새185의 실행 시점 차이를 함께 고려한다.", "",
        "부분 결과의 완료 집합은 조건 우선순위·ID 실행 순서·제한에 영향을 받아 무작위 하위표본이 아니다. 미완료 조건의 전체265 효과를 확정하지 않는다. 예측 모델 연산비용과 사용량이 제공되지 않은 실패·재시도 비용을 측정하지 않았으므로 시스템 전체 효율 향상을 주장하지 않는다.", "",
        "## 정답표·풀이 검토", "",
        "trig_1_010의 원본④와 해설 계산9/5·②의 기존 충돌을 보존한다. 원본 기준 점수를 주 결과로 표시하고 AI 보조 대안 기준은 CSV 별도 열에 둔다. 원본 정답을 자동 수정하지 않는다.", "",
        f"총 {len(review_rows)}개 조건의 검토 상태를 [검토 CSV](review/status.csv)에 기록했다. 상태 개수: `" + str(dict(Counter(row["review_status"] for row in review_rows))) + "`. "
        "과거320개 검토는 응답SHA와 실제 인용이 일치하는 경우에만 재사용했다. 새185의 생성 풀이를 직접 검증하지 않았다면 검토 보류이며, 정답이 맞았다는 이유로 풀이 타당성을 확정하지 않는다. 별도 외부 검토 API 호출은 없다.", "",
        f"[선별 사례 {len(cases)}문항](case_reports/README.md) · [모든 응답 검토 상태](review/status.csv)", "",
        "## 화면을 여는 방법", "",
        "GitHub의 HTML 파일 페이지는 실행 화면이 아니다. 저장소 ZIP 전체를 압축 해제한 뒤 `results/final_experiment_2/gemini_full265/report.html`을 브라우저로 연다. 같은 폴더의 viewer_assets와 기존 mathhint_analysis/viewer_assets/vendor의 로컬 수식·Markdown·폰트가 함께 필요하다. HTML 하나만 내려받으면 충분하지 않다. 외부 렌더링 서버·로그인·추가 API 없이 읽는다.", "",
        "[2차 연구 목차](../README.md) · [변경하지 않은 기존80 결과](../gemini_comparison/README.md)", ""]
    if (Path(output).parents[2] / "data/curation/answer_key_corrections.json").is_file():
        lines += ["", "## 원본 정답표 보존과 검증된 정정 점수", "",
                  "원본 정답표 기준 수치는 역사적 기록으로 보존한다. "
                  "trig_1_010의 확인된 오류(④→②)를 반영한 [정정 점수표](key_corrected/README.md)를 "
                  "문항별·전체265/학습185/테스트80별로 별도 제공한다. "
                  "미완료를 오답 처리하지 않으며 API 호출 없이 재생성된다.",
                  "[정정 규칙](../../../data/curation/answer_key_corrections.json) · "
                  "[검토 기록](../../../docs/answer_key_audit_2026-11-11.md)", ""]
    (Path(output) / "README.md").write_text("\n".join(lines), encoding="utf-8")


def run(root=None, output=None):
    from .common import ROOT, OUTPUT, load_saved, safe_output
    root = Path(root or ROOT).resolve()
    output = safe_output(root, output or (root / OUTPUT.relative_to(ROOT)))
    config, plan, records, state = load_saved(output)
    # 공통 읽기 함수가 원래 분할을 유지하면서 계획의 모든 문항을 포함한다.
    questions, ids = shared.build_questions(root, output, {**config, "split": "test"}, plan, records)
    if len(questions) != 265 or not all(q["expected_generation"] for q in questions):
        raise ValueError("전체265 계획과 원본 문항의 읽기 범위가 다릅니다.")
    review_rows = build_reviews(root, output, questions)
    review_readme = output / "review/README.md"
    review_readme.write_text(review_readme.read_text(encoding="utf-8") +
        "\n전체265 실험의 기존 테스트80 A/B/C/D 검토는 동일 응답 SHA와 실제 인용이 일치한320개만 출처를 보존해 재사용한다. "
        "이 검토를 새 학습185 응답에 자동 복사하지 않는다.\n", encoding="utf-8")
    cases = write_cases(output, questions)
    split_summary, split_tokens = shared.summaries(questions)
    split_pairs = shared.paired_tests(questions)
    overall_summary, overall_tokens, overall_pairs = all_scope_metrics(questions)
    summary, tokens, pairs = overall_summary + split_summary, overall_tokens + split_tokens, overall_pairs + split_pairs
    comparisons = shared.question_rows(questions)
    for name, rows in (("summary.csv", summary), ("token_summary.csv", tokens),
                       ("question_comparison.csv", comparisons), ("paired_comparison.csv", pairs)):
        write_csv(output / name, rows)
    for split in ("train", "test"):
        write_csv(output / f"question_comparison_{split}.csv", [r for r in comparisons if r["split"] == split])
    shared._plots(output, split_summary, comparisons)
    _overall_figures(output, overall_summary)
    payload = {"schema_version": 2, "experiment_name": "Final Experiment 2 · 전체265 A/B/C/D",
               "methods": list(METHODS), "config": config, "questions": questions,
               "test_ids": ids["test"], "train_ids": ids["train"], "primary_split": "all",
               "links": {"readme": "README.md", "comparison_csv": "question_comparison.csv", "raw_responses": "responses.jsonl",
                         "final_report": "README.md"}}
    build_full_viewer(output, payload)
    write_json(output / "metrics.json", {"summary": summary, "token_summary": tokens, "paired_comparison": pairs,
        "question_count": len(comparisons), "case_count": len(cases), "review_status_counts": dict(Counter(r["review_status"] for r in review_rows)),
        "state": state, "additional_review_api_calls": 0, "report_generation_api_calls": 0, "model_training_performed": False})
    _readme(output, config, state, summary, review_rows, cases, questions)
    # 미완료 실행에서도 성공 응답만 정정 채점한다. 원본 API 이력 및 원래 집계는 보존한다.
    if (root / "data/curation/answer_key_corrections.json").is_file():
        from mathhint_analysis.VerifiedAnswerKey import get_registry, regrade
        registry_path, corrections = get_registry(root)
        regrade(root, "gemini_full265", registry_path, corrections)
    return {"question_count": len(comparisons), "case_count": len(cases), "training_performed": False, "api_calls": 0}
