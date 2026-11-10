"""새 지도 모델과 Gemini 저장 결과를 한곳에 연결한다. 학습·API 호출은 없다."""

import argparse
import csv
from pathlib import Path

from .solution_data.common import ROOT, file_hash, read_json, write_csv, write_json


def rows(path):
    path = Path(path)
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def number(value, digits=4):
    return "—" if value in (None, "") else f"{float(value):.{digits}f}"


def table(headers, values):
    return ["|" + "|".join(headers) + "|", "|" + "|".join("---" for _ in headers) + "|"] + [
        "|" + "|".join(str(v) for v in row) + "|" for row in values]


def model_rows(base):
    result = []
    for name in ("regression", "deep_learning"):
        folder = base / name
        if not (folder / "model_manifest.json").exists():
            continue
        manifest = read_json(folder / "model_manifest.json")
        summary = rows(folder / "summary.csv")
        for phase in ("validation", "test"):
            if name == "regression":
                result.append({"model": "training_mean", "label": "학습 평균 기준선", "split": phase,
                               **next(r for r in summary if r["split"] == phase and r["method"] == "training_mean"),
                               "architecture": "training mean vector"})
            actual = next(r for r in summary if r["split"] == phase and r["method"] == "clipped_nonnegative")
            result.append({"model": name, "label": "선형회귀" if name == "regression" else "nn.Sequential MLP",
                           **actual, "architecture": manifest["architecture"]})
    return result


def _model_table(values, phase):
    selected = [r for r in values if r["split"] == phase]
    return table(["모델", "MSE ↓", "MAE ↓", "코사인 ↑", "Precision@20 ↑", "Recall@20 ↑", "공통 토큰 수/20"],
                 [(r["label"], *[number(r[k]) for k in ("mse", "mae", "cosine_similarity", "precision_at_20",
                                                       "recall_at_20", "mean_common_top20_count")]) for r in selected])


def _api_table(values):
    return table(["조건", "성공/80", "채점 가능", "원본 기준 정답", "정답률", "평균 입력", "평균 출력", "평균 전체"],
        [(r["label"], r["success_count"], r["graded_count"], r["correct_count"],
          "—" if r["accuracy_graded"] == "" else f"{float(r['accuracy_graded']):.2%}",
          *[number(r.get(key + "_mean"), 1) for key in ("prompt_token_count", "candidates_token_count", "total_token_count")])
         for r in values if r["split"] == "test"])


def _api_findings(base, values):
    """서로 대응 가능한 저장 응답만 비교하고 미완료를 효과 없음으로 해석하지 않는다."""
    lookup = {r["condition"]: r for r in values if r["split"] == "test"}
    if not lookup:
        return []
    lines = ["### 실제 풀이 효과와 사용량을 구분해 읽기", ""]
    for condition in ("B", "C", "D"):
        if condition in lookup:
            r = lookup[condition]
            lines.append(f"- {condition}: 성공 {r['success_count']}/80, 원본 정답표 기준 "
                         f"{r['correct_count']}/{r['graded_count']}채점 가능. "
                         f"미완료 {r['pending_count']}·실패 {r['failed_count']}·채점 불가 {r['ungradable_count']}.")
    pairs = [r for r in rows(base / "gemini_comparison/paired_comparison.csv") if r["split"] == "test"]
    if pairs:
        lines += ["", *table(["대응 조건", "공통 채점 수", "앞만 정답", "뒤만 정답", "정확 McNemar p", "Holm 보정 p"],
            [(r["pair"], r["matched_gradable_count"], r["first_correct_second_wrong"], r["first_wrong_second_correct"],
              number(r["p_exact_mcnemar"]), number(r["p_holm_within_split"])) for r in pairs]), "",
            "정오답 변화가 적으면 검정력이 낮다. 유의하지 않다는 사실은 효과가 없다는 증명이 아니며, "
            "반복 생성하지 않은 작은 표본과 시점이 다른 과거 A 재사용이라는 한계가 있다."]
    questions = [r for r in rows(base / "gemini_comparison/question_comparison.csv") if r["split"] == "test"]
    differences = []
    for first, second in (("B", "A"), ("C", "A"), ("D", "A"), ("C", "B")):
        valid = [r for r in questions if r.get(first + "_status") == r.get(second + "_status") == "success"
                 and r.get(first + "_total_token_count") not in (None, "")
                 and r.get(second + "_total_token_count") not in (None, "")]
        deltas = [int(r[first + "_total_token_count"]) - int(r[second + "_total_token_count"]) for r in valid]
        differences.append((first + "−" + second, len(deltas), sum(deltas) if deltas else "—",
                            number(sum(deltas) / len(deltas), 2) if deltas else "—"))
    lines += ["", *table(["전체 토큰 차이", "사용량 제공 공통 문항", "차이 합계", "문항당 평균 차이"], differences), "",
              "토큰 차이는 두 응답이 모두 성공하고 실제 total이 제공된 공통 문항만 사용했다. "
              "음수는 뒤 조건보다 적은 토큰, 양수는 많은 토큰이다. 미완료 집합의 서로 다른 합계를 직접 비교하지 않는다."]
    return lines + [""]


def _saved_bool(value):
    """CSV의 공란은 미판정이다. 문자열 'False'를 참으로 해석하지 않는다."""
    return True if value is True or value == "True" else False if value is False or value == "False" else None


def _model_findings(values):
    selected = {r["model"]: r for r in values if r["split"] == "test"}
    if not all(key in selected for key in ("training_mean", "regression", "deep_learning")):
        return []
    baseline, linear, deep = [selected[key] for key in ("training_mean", "regression", "deep_learning")]
    lines = ["### 예측 지표가 보여 주는 차이", ""]
    for row in (linear, deep):
        lines.append(f"- {row['label']}: 평균 기준선 대비 P@20 차이 "
                     f"{float(row['precision_at_20'])-float(baseline['precision_at_20']):+.6f}, "
                     f"문항당 공통 토큰 차이 {float(row['mean_common_top20_count'])-float(baseline['mean_common_top20_count']):+.4f}개, "
                     f"MSE 차이 {float(row['mse'])-float(baseline['mse']):+.4f}다. "
                     "이는 문제에 따라 달라지는 예측과 고정 평균 벡터의 이 저장 테스트 비교다.")
    differences = [(key, float(deep[key])-float(linear[key]))
                   for key in ("mse", "mae", "cosine_similarity", "precision_at_20")]
    labels = {"mse": "MSE", "mae": "MAE", "cosine_similarity": "코사인", "precision_at_20": "P@20"}
    lines += ["", "MLP−선형 차이는 " + ", ".join(f"{labels[key]} {delta:+.6f}" for key, delta in differences) + "다. "
              "MSE·MAE는 작을수록, 코사인·P@20은 클수록 좋으므로 지표마다 방향을 함께 읽어야 한다."]
    winners = {key: ("동일" if delta == 0 else "MLP" if (delta < 0 if key in ("mse", "mae") else delta > 0) else "선형")
               for key, delta in differences}
    lines.append("이 테스트에서 더 좋은 값은 " + ", ".join(f"{labels[key]}: {winners[key]}" for key, _ in differences) + "다.")
    if linear.get("n") and linear.get("n") == deep.get("n"):
        n = int(linear["n"])
        difference = (float(deep["mean_common_top20_count"])-float(linear["mean_common_top20_count"]))*n
        lines.append(f"공통 {n}문항의 상위20 일치 수를 합산한 차이는 MLP−선형 {difference:+.2f}개다. "
                     "서로 다른 고유 토큰의 수나 수학 문제 정답 수를 뜻하지 않는다.")
    return lines + ["", "P@20은 토큰 집합의 겹침을 분모20으로 나눈 값이며 코사인도 수학 정답률이 아니다. "
                    "이 차이에서 Gemini 정답 변화나 비선형 모델의 일반적 우월성을 도출하지 않는다.", ""]


def _successful_pair(questions, first, second):
    return [r for r in questions if r.get(first + "_status") == r.get(second + "_status") == "success"]


def _api_interpretation(base, values):
    """저장 CSV에서만 읽는 대응 정답·토큰 해석. 서로 다른 완료 집합을 빼지 않는다."""
    questions = [r for r in rows(base / "gemini_comparison/question_comparison.csv") if r["split"] == "test"]
    if not questions:
        return []
    lookup = {r["condition"]: r for r in values if r["split"] == "test"}
    lines = ["### 정답 변화와 토큰 변화는 같은 결론인가?", ""]
    for first, second in (("A", "B"), ("A", "C"), ("A", "D"), ("B", "C")):
        successes = _successful_pair(questions, first, second)
        matched = [r for r in successes if all(_saved_bool(r.get(c + "_correct_original")) is not None
                                              for c in (first, second))]
        states = " / ".join(f"{c} 미완료 {lookup[c]['pending_count']}·실패 {lookup[c]['failed_count']}"
                            for c in (first, second) if c in lookup)
        if not matched:
            lines.append(f"- {first}→{second}: 원본 기준 공통 채점 n=0/{len(questions)}. {states}. "
                         "정답률 차이를 아직 계산할 수 없다.")
        else:
            counts = [sum(_saved_bool(r[c + "_correct_original"]) is True for r in matched) for c in (first, second)]
            gain = sum(_saved_bool(r[first + "_correct_original"]) is False
                       and _saved_bool(r[second + "_correct_original"]) is True for r in matched)
            loss = sum(_saved_bool(r[first + "_correct_original"]) is True
                       and _saved_bool(r[second + "_correct_original"]) is False for r in matched)
            lines.append(f"- {first}→{second}: 원본 기준 공통 채점 n={len(matched)}/{len(questions)} "
                         f"(제외 {len(questions)-len(matched)}), {first} {counts[0]}/{len(matched)}→"
                         f"{second} {counts[1]}/{len(matched)} "
                         f"({second}−{first} {(counts[1]-counts[0])/len(matched)*100:+.2f}%p). "
                         f"오답→정답 {gain}개, 정답→오답 {loss}개. {states}.")
        token_parts = []
        for field, label in (("prompt_token_count", "입력"), ("candidates_token_count", "출력"),
                             ("total_token_count", "전체")):
            provided = [r for r in successes if all(r.get(c + "_" + field) not in (None, "") for c in (first, second))]
            if provided:
                delta = sum(float(r[second + "_" + field])-float(r[first + "_" + field]) for r in provided)/len(provided)
                token_parts.append(f"{label} {delta:+.2f}토큰(n={len(provided)})")
            else:
                token_parts.append(f"{label} 미제공(n=0)")
        lines.append(f"  같은 문항의 {second}−{first} 평균 사용량 차이: " + ", ".join(token_parts) + ".")
    supplements = [r for r in lookup.values() if r.get("accuracy_ai_supplemental") not in (None, "")]
    if supplements:
        lines += ["", "원본 기준과 별도로 계산한 AI 보조 정답표 기준은 " + "; ".join(
            f"{r['condition']} {r['correct_count_ai_supplemental']}/{r['graded_count']} "
            f"({float(r['accuracy_ai_supplemental']):.2%})" for r in supplements) + "다. "
            "보조 기준은 원본 점수를 대체하지 않으며 사람의 정답표 확정 판정이 아니다."]
    return lines + ["", "입력 힌트가 늘어난 조건에서도 출력과 전체 토큰의 방향은 별도로 확인한다. "
                    "각 토큰 항목은 성공하고 해당 값이 제공된 공통 문항만 사용하므로 n이 채점 집합과 다를 수 있다. "
                    "전체 토큰 감소와 정답 증가를 같은 효과로 취급하지 않는다. "
                    "표본이 진행 중이면 관측된 일부 문항의 차이이며, 완료 후에도 단일 생성·과거 A 재사용·탐색적 설계의 제한이 남는다.", ""]


def _case_findings(base, limit=6):
    questions = [r for r in rows(base / "gemini_comparison/question_comparison.csv") if r["split"] == "test"]
    if not questions:
        return ["아직 저장된 문항별 비교가 없다.", ""]
    reviews = [r for r in rows(base / "gemini_comparison/review/status.csv")
               if r["split"] == "test" and r.get("api_status") == "success"]
    review_by_id = {}
    for r in reviews:
        if r.get("math_status") == "inappropriate":
            review_by_id.setdefault(r["id"], []).append(r)
    comparable = [r for r in questions if sum(r.get(c + "_status") == "success"
                  and r.get(c + "_answer") not in (None, "") for c in "ABCD") >= 2]
    changed = [r for r in comparable if _saved_bool(r.get("changed_answers")) is True]
    incomplete = sum(any(r.get(c + "_status") != "success" for c in "ABCD") for r in questions)
    lines = [f"저장 성공 응답에서 답을 판독한 조건이 두 개 이상인 {len(comparable)}문항 중 동등 답 표기를 정규화한 "
             f"최종 답 변화는 {len(changed)}문항이다. 네 조건 중 실패·미완료가 남은 문항은 {incomplete}/{len(questions)}다. "
             "사례는 정답 변화·정답표 충돌·답과 추론의 불일치를 읽기 위한 선별이며 전체 빈도를 대표하지 않는다.", ""]
    chosen = []

    def choose(predicate):
        row = next((r for r in questions if r not in chosen and predicate(r)), None)
        if row is not None and len(chosen) < limit:
            chosen.append(row)

    choose(lambda r: _saved_bool(r.get("answer_key_conflict")) is True)
    for before, after in ((False, True), (True, False)):
        choose(lambda r: _saved_bool(r.get("answer_key_conflict")) is not True
               and r.get("A_status") == "success" and _saved_bool(r.get("A_correct_original")) is before
               and any(r.get(c + "_status") == "success" and _saved_bool(r.get(c + "_correct_original")) is after
                       for c in "BC"))
    for correct in (True, False):
        choose(lambda r: any(_saved_bool(v.get("final_answer_correct_original")) is correct
                             for v in review_by_id.get(r["id"], [])))
    choose(lambda r: r in changed)
    for q in chosen:
        identifier = q["id"]
        link = f"[네 풀이](gemini_comparison/report.html#{identifier})"
        if (base / f"gemini_comparison/case_reports/{identifier}.md").exists():
            link += f" · [사례·원문 근거](gemini_comparison/case_reports/{identifier}.md)"
        answers = []
        for c in "ABCD":
            if q.get(c + "_status") != "success":
                answers.append(f"{c} {'미완료' if q.get(c + '_status') == 'not_run' else '실패'}")
                continue
            grade = {True: "정답", False: "오답", None: "채점 불가"}[_saved_bool(q.get(c + "_correct_original"))]
            answers.append(f"{c} {q.get(c + '_answer') or '답 판독 불가'}(원본 {grade})")
        lines.append(f"- **{identifier}**: " + ", ".join(answers) + f". {link}.")
        if _saved_bool(q.get("answer_key_conflict")) is True:
            supplemental = [f"{c} " + {True: "정답", False: "오답", None: "채점 불가"}[
                _saved_bool(q.get(c + "_correct_ai_supplemental"))] for c in "ABCD" if q.get(c + "_status") == "success"]
            lines.append(f"  원본 정답 {q['original_answer']} / AI 보조 대안 {q.get('ai_supplemental_answer') or '미제공'}; "
                         "보조 기준에서 " + ", ".join(supplemental) + ". 이 충돌을 힌트에 의한 정답 개선으로 세지 않는다.")
        evidence = review_by_id.get(identifier, [])
        if evidence:
            review = next((r for r in evidence if r.get("error_step")), evidence[0])
            lines.append(f"  {review['condition']}의 AI 보조 검토 상태 `{review['review_status']}`: "
                         + " ".join((review.get("reason") or review.get("error_step") or "근거 설명 미제공").split())
                         + f" (사람 확정: {review.get('human_confirmed', 'False')}).")
    return lines + ["", "최종 답 자동채점과 위 AI 보조 풀이 검토는 별개다. 오류 의심은 형식증명이나 사람의 확정 판정이 아니며, "
                    "검토 보류를 타당 판정으로 바꾸지 않았다. [전체 풀이 검토 상태](gemini_comparison/review/status.csv)에서 "
                    "오류 단계·실제 인용·검토 주체를 확인할 수 있다.", ""]


def _model_plot(base, values):
    from mathhint_learning.ClusterReport import setup_final_plots
    plt = setup_final_plots()
    selected = [r for r in values if r["split"] == "test"]
    if len(selected) != 3:
        return
    folder = base / "figures"
    folder.mkdir(exist_ok=True)
    fig, axes = plt.subplots(1, 4, figsize=(15, 4.5), constrained_layout=True)
    for ax, key, title in zip(axes, ("mse", "mae", "cosine_similarity", "precision_at_20"),
                              ("MSE ↓", "MAE ↓", "코사인 유사도 ↑", "Precision@20 ↑")):
        heights = [float(r[key]) for r in selected]
        bars = ax.bar(["학습 평균", "선형회귀", "MLP"], heights, color=[".8", ".5", ".2"], edgecolor="black")
        ax.bar_label(bars, fmt="%.3f", fontsize=8, padding=3)
        ax.set(title=title, ylim=(0, max(heights)*1.2))
    fig.suptitle("같은 테스트80 · 동일 풀이 활성 어휘 · 음수→0 예측 · 수학 문제 정답률과 구분")
    fig.savefig(folder / "model_comparison.png", dpi=200)
    plt.close(fig)


def report(root=ROOT):
    root = Path(root).resolve()
    base = root / "results/final_experiment_2"
    data = read_json(base / "solution_data/summary.json")
    values = model_rows(base)
    if values:
        write_csv(base / "model_comparison.csv", values)
    _model_plot(base, values)
    api = rows(base / "gemini_comparison/summary.csv")
    api_state_path = base / "gemini_comparison/state.json"
    state = read_json(api_state_path) if api_state_path.exists() else {"status": "not_started_models_or_preflight_pending"}
    scope = state.get("status", "unknown")
    manifests = {name: read_json(base / name / "model_manifest.json") for name in ("regression", "deep_learning")
                 if (base / name / "model_manifest.json").exists()}
    if len(manifests) == 2:
        linear, deep = [manifests[n]["test_metrics"] for n in ("regression", "deep_learning")]
        model_fact = (f"테스트80의 음수 보정 P@20은 선형 {linear['precision_at_20']:.4f}, MLP {deep['precision_at_20']:.4f}다. "
                      f"MLP−선형 차이는 {deep['precision_at_20']-linear['precision_at_20']:+.4f}다. "
                      "이는 이 고정 테스트의 관찰이며 비선형 모델의 일반적인 우월성을 보장하지 않는다.")
    else:
        model_fact = "아직 두 모델의 독립 확정본이 모두 준비되지 않았다. Gemini 생성 실험은 시작할 수 없다."
    model_sections = ["## 같은 기준으로 두 예측 모델 비교", "", "내부 검증37 · 기준선은 fit148 평균", "",
                      *_model_table(values, "validation"), "",
                      "MLP 검증 행은 대표 seed42의 값이다. 구성 선택에 사용한3시드 평균과는 구분하며 자세한 값은 딥러닝 README에 있다.", "",
                      "최종 테스트80 · 기준선은 학습185 평균", "",
                      *_model_table(values, "test"), "", model_fact, ""]
    if len(manifests) == 2:
        model_sections += ["![동일 타깃 공간 모델 비교](figures/model_comparison.png)", ""]
    links = ["|연구|먼저 열 자료|", "|---|---|",
             "|완료된 군집화|[군집화 결과](cluster_improvement/README.md)|",
             "|문제270 → 원본 풀이 공통 데이터|[데이터·분할·어휘·불용어](solution_data/README.md)|",
             "|선형회귀와 개선 기록|[선형 결과](regression/README.md) · [문항별 예측](regression/question_comparison.csv)|",
             "|nn.Sequential 비선형 모델|[MLP 결과](deep_learning/README.md) · [문항별 예측](deep_learning/question_comparison.csv)|",
             "|Gemini A/B/C/D|[정답·사용량](gemini_comparison/README.md) · [네 풀이 비교 HTML](gemini_comparison/report.html)|",
             "|모든 연구 해석과 한계|[종합 보고서](final_report.md) · [전체 검증](validation.json)|"]
    api_section = ["## Gemini 네 조건의 실제 풀이", "", f"현재 실행 상태: **{scope}**. "
                   "완료하지 않은 응답을 오답이나0토큰으로 집계하지 않는다.", ""]
    if api:
        api_section += [*_api_table(api), "", "평균 토큰은 실제 제공된 성공 응답 값에 대한 평균이며 미제공은 —다. "
                        "추론 토큰을 전체 토큰에 다시 더하지 않는다. 원본 정답 기준과 trig_1_010의 AI 보조 기준은 분리한다.", ""]
        api_section += _api_findings(base, api)
    else:
        api_section += ["아직 저장된 네 조건의 최종 비교 수치가 없다. 새 해설 토큰의 풀이 효과는 미검증이다.", ""]
    notes = [
        "전체265 문제·원본 풀이의 어휘를 사전에 사용했다. 가중치와 모델 선택은 원래 학습185 내부에서만 수행했지만 완전히 독립적인 미관측 일반화 평가가 아니다.",
        "검증 P@20을 먼저 고정하고 내부148/37에서 유한 후보를 개선했다. 최종 설정을 확정한 뒤185개로 재학습하고 테스트80 예측을 만들었다. API 정답률을 보고 모델을 다시 바꾸지 않는다.",
        "특정 원본 해설의 토큰 빈도는 가능한 여러 올바른 풀이 중 하나의 표현이다. 빈도 오차와 수학적 풀이의 옳고 그름은 다른 평가다.",
        "학습185에서 빈도가0인 풀이 토큰25개는 전체 어휘에 있어도 학습 사례가 없다. 문제의 동일 BoW가 train/test에 걸친 diff_1_007·diff_1_011도 원래 분할대로 남겨 해석에 제한이 있다.",
        "BoW는 수식의 순서·분자/분모·변수 역할·논리 연결을 보존하지 못한다. 층을 늘리는 것만으로 소실된 수식 구조가 복원되지 않는다.",
        "원본 답 정오답과 풀이 과정 타당성을 분리했다. 구체적 오류 단계·근거로 충분히 확인하지 못한 생성 풀이는 검토 보류로 남기며 사람의 확정 판정으로 표시하지 않는다.",
        "API 원문·사용량·미완료 상태·실제 요청을 보존한다. 과거의 정확히 같은 요청 재사용과 새 응답의 실행 시점 차이도 구분한다.",
        "API가 미완료라면 완료된 ID 순서의 집합은 무작위 하위표본이 아니다. 공통 완료 문항끼리의 대응 비교도 테스트80 전체의 효과를 대신하지 않는다.",
        "예측 모델의 연산 비용을 측정하지 않았으므로 Gemini 토큰 절감만으로 시스템 전체 계산 효율성이 개선됐다고 주장하지 않는다.",
    ]
    readme = ["# MathHint Final Experiment 2", "", "## 결과를 읽는 순서", "", *links, "",
              f"문제 입력은 기존 **{data['input_dimension']}차원**을 그대로 읽었고, 원본 풀이265개는 "
              f"어휘 {data['raw_solution_dimension']}종에서 승인103개를 제외한 **{data['output_dimension']}차원**을 새로 구성했다.", "",
              *model_sections, *api_section, "## 연구 범위와 한계", "", *["- " + n for n in notes], "",
              "학습185 확장은 테스트80 네 조건을 완료·검증한 뒤 확인된 호출 예산이 충분할 때만 실행한다. "
              "현재 예산이 확인되지 않으면 확장하지 않는다. HTML은 GitHub 파일 화면에서 실행되지 않으므로 저장소 ZIP 전체를 압축 해제해 브라우저로 연다. "
              "로컬 수식 자산과 연결된 폴더가 함께 필요하며 인터넷 연결 없이 읽을 수 있다.", "",
              "## 실행과 재개", "", "각 모델·API README의 명령을 따른다. 저장 결과의 종합 안내만 재생성하려면:", "",
              "```bash", "python -m mathhint_learning.final_experiment_2.report report",
              "python -m mathhint_learning.final_experiment_2.report verify", "```", "",
              "report/verify는 새 모델 학습이나 Gemini 호출을 실행하지 않는다. 실제 API 재개는 gemini_comparison의 generate 명령으로 분리했다.", ""]
    (base / "README.md").write_text("\n".join(readme), encoding="utf-8")
    final = ["# MathHint: 외부 해설 토큰 예측과 LLM 풀이 비교", "",
             "## 1. 연구 질문과 실험 설계", "",
             "외부 선형/비선형 모델이 예측한 풀이 토큰이 Gemini의 정답과 사용량에 어떤 차이를 만드는지 조사했다. "
             "해설 빈도 예측의 성능과 실제 수학 풀이 성능을 분리해 분석했다. 개선을 전제로 모델이나 정답을 수정하지 않았다.", "",
             "## 2. 데이터와 내부 검증", "", f"기존 문제270은 재토큰화 없이 재사용했다. 풀이 {data['raw_solution_dimension']}→"
             f"{data['output_dimension']}차원, 원시 빈도 {data['raw_solution_tf']:,}→{data['filtered_solution_tf']:,}회다. "
             "원래185/80을 유지했고 학습185 안의148/37로 두 모델을 선택했다. 데이터 변환의 추정값도 내부 학습 자료에서만 계산했다.", "",
             "## 3. 선형회귀의 개선", ""]
    for name, title in (("regression", "선형 모델"), ("deep_learning", "비선형 MLP")):
        if name in manifests:
            m = manifests[name]
            final += [f"### {title}", "", f"최종 구조: `{m['architecture']}`", "",
                      f"선택 설정: `{m['selected_configuration']}`", "",
                      f"[전체 후보·개선 이유·중단·손실곡선]({name}/README.md). "
                      "검증 P@20과 오차를 기준으로 설정을 확정했으며 테스트와 API 결과는 후보 선택에 쓰지 않았다.", ""]
    final += ["## 4. 동일 타깃 공간에서 모델은 얼마나 예측했는가?", "", *model_sections, *_model_findings(values),
              "## 5. Gemini 입력과 실행", "",
              "A는 원문만, B는 선형 예측, C는 비선형 예측, D는 실제 해설 상위20개다. D는 이전 연구 C에 해당하는 오라클이다. "
              "모든 문제 원문·DEFAULT_SYSTEM·gemini-3.1-flash-lite·temperature0·minimal·8192 설정을 통제했다. "
              "힌트는 양수/음수보정·반올림전순위·어휘순동점·셋째자리표시·0표시제외 JSON과 마지막 지시문을 공유한다. "
              "실제 모델 사용 가능 여부·인증·확인 가능한 제한은 [사전점검과 실행 상태](gemini_comparison/README.md)에 기록한다.", "",
              *api_section, *_api_interpretation(base, api), "## 6. 어떤 문항에서 도움이 되거나 방해됐는가?", "",
              "[문항별 네 조건 비교](gemini_comparison/question_comparison.csv), [오류·특이 사례](gemini_comparison/case_reports/README.md), "
              "[원본·생성 풀이를 함께 읽는 화면](gemini_comparison/report.html)에서 실제 답 변화와 토큰 차이를 확인한다. "
              "최종 답이 맞아도 풀이를 자동으로 타당하다고 판정하지 않았다. 검토 보류는 실제 오류 확정과 다르다.", "",
              *_case_findings(base),
              "## 7. 결론의 범위와 후속 과제", "", *["- " + n for n in notes], "",
              "모델 P@20이 좋아진 사실만으로 Gemini 정답률·효율성 개선을 주장하지 않는다. 실제 API 대응 결과와 사용량을 따로 평가한다. "
              "어텐션 기반 표현이나 출력 제약·형식 검증은 향후 방향이며 새로운 미관측 문제에서 재검증해야 한다.", "",
              "[공통 데이터](solution_data/README.md) · [선형 결과](regression/README.md) · "
              "[비선형 결과](deep_learning/README.md) · [API 결과](gemini_comparison/README.md) · [전체 검증](validation.json)", ""]
    (base / "final_report.md").write_text("\n".join(final), encoding="utf-8")
    return {"models_frozen": len(manifests), "api_status": scope, "training_performed": False, "api_calls": 0}


def verify(root=ROOT):
    from .solution_data.validation import validate_dataset, validate_model
    from .cluster_improvement.verify import scan_links
    from PIL import Image
    root = Path(root).resolve()
    base = root / "results/final_experiment_2"
    dataset = validate_dataset(root, save=True)
    models = {name: validate_model(root, name, save=True) for name in ("regression", "deep_learning")}
    from mathhint_solver.final_experiment_2.gemini_comparison.verify import run as verify_api
    api = verify_api(root, base / "gemini_comparison")
    details = {"solution_data": dataset, **models, "gemini_comparison": api}
    link_count, broken = scan_links(base)
    images = list((base / "figures").glob("*.png"))
    for folder in ("regression", "deep_learning", "gemini_comparison"):
        images.extend((base / folder).rglob("*.png"))
    invalid_images = []
    for path in images:
        try:
            with Image.open(path) as image:
                size = image.size
                image.verify()
            if size[0] < 500 or size[1] < 300:
                invalid_images.append(str(path.relative_to(base)))
        except (OSError, ValueError):
            invalid_images.append(str(path.relative_to(base)))
    presentation = {"markdown_file_links_checked": link_count, "broken_links": broken,
                    "decoded_png_count": len(images), "invalid_images": invalid_images,
                    "checks": [{"check": "all_result_markdown_links_exist", "passed": not broken},
                               {"check": "new_png_files_decode_at_readable_resolution", "passed": bool(images) and not invalid_images}],
                    "manual_visual_check": "실제 브라우저 검사는 API 검증의 actual_browser_validation 및 진행 기록과 구분해 확인한다."}
    presentation["passed"] = sum(row["passed"] for row in presentation["checks"])
    presentation["failed"] = sum(not row["passed"] for row in presentation["checks"])
    details["presentation"] = presentation
    passed = sum(int(v.get("passed", 0)) for v in details.values())
    failed = sum(int(v.get("failed", 0)) for v in details.values())
    result = {"passed": passed, "failed": failed,
              "complete": failed == 0 and api.get("experiment_complete", False),
              "component_details": details, "training_performed": False, "api_calls": 0,
              "scope": "filtered_full265_vocab; train185/internal148-37; test80 ABCD; optionaltrain185onlyconfirmedbudget"}
    write_json(base / "validation.json", result)
    print(f"종합 검증 {passed}통과/{failed}실패 · 실제 API 완료 여부 {api.get('experiment_complete')}")
    return result


def main():
    parser = argparse.ArgumentParser(description="저장된 모델·API 결과의 종합 보고서와 검증")
    parser.add_argument("action", choices=("report", "verify"))
    args = parser.parse_args()
    result = (report if args.action == "report" else verify)()
    if args.action == "verify" and result["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
