"""저장된 거리 통계로만 한국어 설명과 그림을 만든다. 모델은 실행하지 않는다."""

from pathlib import Path

from ..common import read_csv, read_json
from ..reporting import _plots, _token


LEVELS = (("curriculum", "과목"), ("unit", "단원"),
          ("subunit", "세부단원"), ("type", "문제 유형"))
TOKENS = ("latex:{", "latex:}", r"latex:\left", r"latex:\right", "latex:(", "latex:)",
          r"latex:\mathrm", "latex:x", "latex:2", r"latex:\sin", r"latex:\cos",
          r"latex:\tan", r"latex:\lim", r"latex:\pi", r"latex:\theta")


def _float(value):
    return None if value in (None, "", "null") else float(value)


def _num(value, digits=4, *, signed=False):
    value = _float(value)
    if value is None:
        return "정의되지 않음"
    return f"{value:+.{digits}f}" if signed else f"{value:.{digits}f}"


def _percent(value):
    return _num(value, 2) + "%" if _float(value) is not None else "정의되지 않음"


def _write(path, lines):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _save(plt, figure, path, *, footnote=""):
    if footnote:
        figure.text(.5, .012, footnote, ha="center", fontsize=9)
    figure.tight_layout(rect=(0, .055 if footnote else 0, 1, .965))
    figure.savefig(path, dpi=190, facecolor="white")
    plt.close(figure)


def _dual_bar(ax, labels, left, right, *, title, xlabel, limits=None,
              legend_names=("원시 유클리드", "코사인 / L2 정규화")):
    import numpy as np
    y = np.arange(len(labels))
    for offset, values, name, color in ((-.18, left, legend_names[0], ".83"),
                                         (.18, right, legend_names[1], ".32")):
        valid = [(i, _float(v)) for i, v in enumerate(values) if _float(v) is not None]
        bars = ax.barh([y[i] + offset for i, _ in valid], [v for _, v in valid], height=.34,
                       label=name, color=color, edgecolor="black", linewidth=.4)
        ax.bar_label(bars, fmt="%.2f", fontsize=7, padding=2)
        for i, value in enumerate(values):
            if _float(value) is None:
                ax.text(0, y[i] + offset, "정의되지 않음", fontsize=7)
    ax.set_yticks(y, labels, fontsize=8.5)
    ax.invert_yaxis()
    ax.set(title=title, xlabel=xlabel)
    if limits:
        ax.set_xlim(*limits)
    else:
        maximum = max([_float(v) for v in left + right if _float(v) is not None] or [0])
        ax.set_xlim(0, maximum * 1.19 if maximum else 1)
    ax.legend(fontsize=8)


def _draw_contributions(output, rows, groups):
    plt = _plots()
    folder = output / "figures"
    figure, axes = plt.subplots(1, 2, figsize=(16, 9))
    maximum = max(float(r[field]) for r in rows for field in ("euclidean_contribution", "cosine_contribution"))
    for ax, field, title in zip(axes, ("euclidean_contribution", "cosine_contribution"),
                                ("원시 BoW · 제곱 유클리드", "L2 정규화 · 코사인 1−cos")):
        chosen = sorted(rows, key=lambda r: (-float(r[field]), int(r["index"])))[:20]
        bars = ax.barh(range(len(chosen)), [float(r[field]) for r in chosen],
                       color=".48", edgecolor="black", linewidth=.4)
        ax.set_yticks(range(len(chosen)), [r["token"] for r in chosen], fontsize=9)
        ax.invert_yaxis()
        ax.set(title=title, xlabel="해당 거리의 전체 평균 기여 중 비율 (%)", xlim=(0, maximum * 1.2))
        ax.bar_label(bars, fmt="%.2f%%", padding=3, fontsize=8)
    figure.suptitle("토큰별 거리 기여 상위20 · 학습185문항 · 서로 다른17,020쌍", fontsize=14)
    _save(plt, figure, folder / "contribution_top20.png",
          footnote="두 패널은 각 거리 안의 상대적 기여율이다. 원시 분산과 정규화 분산의 절댓값을 서로 비교하지 않는다.")
    lookup = {row["token"]: row for row in rows}
    chosen = [lookup[token] for token in TOKENS if token in lookup]
    figure, ax = plt.subplots(figsize=(13, 9))
    _dual_bar(ax, [r["token"] for r in chosen], [r["euclidean_contribution"] for r in chosen],
              [r["cosine_contribution"] for r in chosen], title="같은15토큰의 상대적 거리 기여 · 학습185문항",
              xlabel="각 거리의 전체 평균 기여 중 비율 (%)")
    _save(plt, figure, folder / "selected_token_contributions.png",
          footnote="숫자는 좌표의 상대적 거리 기여다. 수학적 유용성이나 불용어 판정이 아니다.")
    figure, ax = plt.subplots(figsize=(12, 5.8))
    names = {"braces_pair": "latex:{ / latex:}", "left_right_pair": r"latex:\left / latex:\right",
             "parentheses_pair": "latex:( / latex:)", "duplicate_six": "위 세 쌍의6좌표 합계"}
    _dual_bar(ax, [names.get(r["group"], r.get("group_name", r["group"])) for r in groups],
              [r["euclidean_contribution"] for r in groups], [r["cosine_contribution"] for r in groups],
              title="중복 서식·구조 좌표의 기여 변화 · 학습185문항", xlabel="각 거리의 전체 평균 기여 중 비율 (%)")
    _save(plt, figure, folder / "duplicate_group_contributions.png",
          footnote="6좌표 합계는 위 세 쌍을 합친 값이다. 네 행 전체를 다시 합산하면 중복 집계된다.")


def _draw_eta(output, rows):
    plt = _plots()
    folder = output / "figures"
    figure, axes = plt.subplots(2, 2, figsize=(12, 10))
    for ax, (level, name) in zip(axes.flat, LEVELS):
        selected = [r for r in rows if r["level"] == level and _float(r["original_eta_squared"]) is not None
                    and _float(r["normalized_eta_squared"]) is not None]
        for rare, marker, color, label in ((False, "o", ".3", "DF>5"), (True, "x", ".68", "DF≤5")):
            subset = [r for r in selected if (int(r["train_df"]) <= 5) == rare]
            ax.scatter([float(r["original_eta_squared"]) for r in subset],
                       [float(r["normalized_eta_squared"]) for r in subset],
                       s=23, marker=marker, color=color, alpha=.75, label=label)
        ax.plot([0, 1], [0, 1], "--", color=".65", linewidth=.8)
        ax.set(xlabel="원시 빈도 η²", ylabel="L2 정규화 η²", title=name,
               xlim=(-.03, 1.03), ylim=(-.03, 1.03))
        ax.legend(fontsize=8)
    figure.suptitle("정규화 전후 실제 분류와 토큰의 연관성 · 학습185문항", fontsize=14)
    _save(plt, figure, folder / "normalized_eta_scatter.png",
          footnote="점선 위쪽은 정규화 η²가 더 큰 토큰이다. 희귀 토큰·소집단·많은 유형에서 높은 값을 과대평가하지 않는다.")
    figure, axes = plt.subplots(2, 2, figsize=(19, 14))
    for ax, (level, name) in zip(axes.flat, LEVELS):
        lookup = {r["token"]: r for r in rows if r["level"] == level}
        selected = [lookup[token] for token in TOKENS if token in lookup]
        _dual_bar(ax, [r["token"] for r in selected], [r["original_eta_squared"] for r in selected],
                  [r["normalized_eta_squared"] for r in selected], title=name,
                  xlabel="η² · 같은 분류 수준 안에서 비교", limits=(0, 1.12),
                  legend_names=("원시 BoW", "L2 정규화 BoW"))
    figure.suptitle("주요 수학 명령어·서식·변수의 η² 변화 · 학습185문항", fontsize=14)
    _save(plt, figure, folder / "selected_eta_comparison.png",
          footnote="원시/정규화 공간마다 별도로 분산을 분해했다. 네 분류 수준의 집단 수가 달라 수준 간 점수를 단순 비교하지 않는다.")
    figure, axes = plt.subplots(2, 2, figsize=(18, 15))
    for ax, (level, name) in zip(axes.flat, LEVELS):
        selected = [r for r in rows if r["level"] == level and _float(r["eta_difference"]) is not None]
        upper = sorted([r for r in selected if float(r["eta_difference"]) > 0],
                       key=lambda r: (-float(r["eta_difference"]), int(r["index"])))[:10]
        lower = sorted([r for r in selected if float(r["eta_difference"]) < 0],
                       key=lambda r: (float(r["eta_difference"]), int(r["index"])))[:10]
        shown = upper + lower
        bars = ax.barh(range(len(shown)), [float(r["eta_difference"]) for r in shown],
                       color=[".35" if float(r["eta_difference"]) >= 0 else ".82" for r in shown],
                       edgecolor="black", linewidth=.4)
        ax.set_yticks(range(len(shown)), [r["token"] + (" · DF≤5" if int(r["train_df"]) <= 5 else "") for r in shown], fontsize=8)
        ax.invert_yaxis()
        ax.axvline(0, color="black", linewidth=.7)
        ax.set(title=name, xlabel="정규화 η² − 원시 η² (η² 단위, %p 아님)")
        ax.bar_label(bars, fmt="%+.3f", padding=2, fontsize=7)
        span = max([abs(float(r["eta_difference"])) for r in shown] or [.1])
        ax.set_xlim(-span * 1.4, span * 1.4)
    figure.suptitle("η²가 크게 증가·감소한 토큰 각10개 · 학습185문항", fontsize=14)
    _save(plt, figure, folder / "eta_change_extremes.png",
          footnote="증가·감소는 표현과 라벨의 통계 관계 변화다. 토큰 제거 효과나 새 문제에 대한 분류 성능을 측정한 값이 아니다.")


def _draw_context(output, distances, old, associations):
    import numpy as np
    plt = _plots()
    folder = output / "figures"
    figure, axes = plt.subplots(1, 2, figsize=(15, 5.8))
    for ax, metric, title, ylabel in zip(axes, ("euclidean", "cosine"),
        ("원시 BoW · 일반 유클리드 거리", "L2 정규화 · 코사인 거리"),
        ("거리 ||x−y||_2 · 원시 빈도 단위", "거리 1−cos(x,y) · 무차원")):
        selected = [next(r for r in distances if r["level"] == level and r["metric"] == metric) for level, _ in LEVELS]
        for offset, field, label, color in ((-.18, "within_mean", "같은 실제 분류", ".82"),
                                           (.18, "between_mean", "다른 실제 분류", ".32")):
            valid = [(i, _float(r[field])) for i, r in enumerate(selected) if _float(r[field]) is not None]
            bars = ax.bar([i + offset for i, _ in valid], [value for _, value in valid], width=.35,
                          label=label, color=color, edgecolor="black", linewidth=.5)
            ax.bar_label(bars, fmt="%.4f", fontsize=7.5, padding=3)
        ax.set_xticks(range(4), [f"{name}\n내부{r['within_pairs']} / 간{r['between_pairs']}쌍" for (_, name), r in zip(LEVELS, selected)], fontsize=8)
        ax.set(title=title, ylabel=ylabel, ylim=(0, max(float(r["between_mean"]) for r in selected) * 1.23))
        ax.legend(fontsize=8)
    figure.suptitle("같은 분류 내부·다른 분류 사이 평균 거리 · 학습185문항의17,020쌍", fontsize=14)
    _save(plt, figure, folder / "within_between_distances.png",
          footnote="두 패널은 거리 단위가 달라 높이를 직접 비교하지 않는다. 각 평균은 문항쌍 가중이며 큰 집단의 영향이 더 크다.")
    figure, ax = plt.subplots(figsize=(10.5, 5))
    for offset, method, label, color in ((-.18, "euclidean", "원시 유클리드 K-means", ".82"),
                                        (.18, "spherical", "Spherical K-means", ".32")):
        selected = [next(r for r in old if r["level"] == level and r["method"] == method) for level, _ in LEVELS]
        bars = ax.bar(np.arange(4) + offset, [float(r["ari"]) for r in selected], width=.35,
                      label=label, color=color, edgecolor="black", linewidth=.5)
        ax.bar_label(bars, fmt="%.4f", padding=3, fontsize=9)
    ax.set_xticks(range(4), [name for _, name in LEVELS])
    ax.set(ylabel="기존 테스트 ARI", ylim=(0, max(float(r["ari"]) for r in old) * 1.27),
           title="기존 저장 실험의 ARI · 학습185 → 테스트80 · 신규 학습 없음")
    ax.legend(fontsize=9)
    _save(plt, figure, folder / "old_test_ari_comparison.png",
          footnote="원본 summary.csv를 읽었다. 거리 통계의 대상185와 이 그림의 평가 대상80은 서로 다르다.")
    figure, ax = plt.subplots(figsize=(10.5, 5))
    for offset, method, label, color in ((-.18, "euclidean", "기존 유클리드 군집", ".82"),
                                        (.18, "spherical", "기존 구면 군집", ".32")):
        selected = [next(r for r in associations if r["level"] == level and r["method"] == method) for level, _ in LEVELS]
        bars = ax.bar(np.arange(4) + offset, [float(r["l2_eta_squared"]) for r in selected], width=.35,
                      label=label, color=color, edgecolor="black", linewidth=.5)
        ax.bar_label(bars, fmt="%.3f", padding=3, fontsize=8)
    ax.set_xticks(range(4), [name for _, name in LEVELS])
    ax.set(ylabel="L2 노름 분산 중 군집 간 분산 비율 η²", ylim=(0, 1.12),
           title="기존 군집과 원시 벡터 크기의 연관성 · 학습185문항")
    ax.legend(fontsize=9)
    _save(plt, figure, folder / "cluster_norm_association.png",
          footnote="실제 분류 η²와 다른 보조 통계다. 군집 번호는 범주로 다뤘으며 번호 크기와 상관을 구하지 않았다. 큰 k의 편향도 고려한다.")


def _contribution_table(rows):
    lookup = {row["token"]: row for row in rows}
    lines = ["|토큰|유클리드 기여|코사인 기여|C−E (%p)|순위 E→C|의미|", "|---|---:|---:|---:|---:|---|"]
    for token in TOKENS:
        if token in lookup:
            row = lookup[token]
            lines.append(f"|{_token(token)}|{_percent(row['euclidean_contribution'])}|{_percent(row['cosine_contribution'])}|{_num(row['contribution_difference'],2,signed=True)}|{row['euclidean_rank']}→{row['cosine_rank']}|{row['meaning']}|")
    return lines


def _distance_table(rows, *, macro=False):
    prefix = "macro_" if macro else ""
    count_label = "전체 내부 / 간 쌍 (가중치 아님)" if macro else "내부 / 간 문항쌍"
    lines = [f"|분류|거리|{count_label}|내부 평균|간 평균|간−내부|간/내부|", "|---|---|---:|---:|---:|---:|---:|"]
    for level, name in LEVELS:
        for metric, label in (("euclidean", "유클리드"), ("cosine", "코사인")):
            row = next(r for r in rows if r["level"] == level and r["metric"] == metric)
            lines.append(f"|{name}|{label}|{row['within_pairs']} / {row['between_pairs']}|{_num(row[prefix+'within_mean'])}|{_num(row[prefix+'between_mean'])}|{_num(row[prefix+'between_minus_within'])}|{_num(row[prefix+'between_div_within'])}|")
    return lines


def _old_table(rows):
    lines = ["|분류|유클리드 ARI|구면 ARI|구면−유클리드 ARI|유클리드 NMI|구면 NMI|", "|---|---:|---:|---:|---:|---:|"]
    for level, name in LEVELS:
        a, b = [next(r for r in rows if r["level"] == level and r["method"] == method)
                for method in ("euclidean", "spherical")]
        lines.append(f"|{name}|{_num(a['ari'],6)}|{_num(b['ari'],6)}|{_num(float(b['ari'])-float(a['ari']),6,signed=True)}|{_num(a['nmi'],6)}|{_num(b['nmi'],6)}|")
    return lines


def _eta_highlights(rows):
    lines = ["|분류|η² 증가가 큰 예 (변화량·DF)|η² 감소가 큰 예 (변화량·DF)|", "|---|---|---|"]
    for level, name in LEVELS:
        valid = [r for r in rows if r["level"] == level and _float(r["eta_difference"]) is not None]
        up = sorted(valid, key=lambda r: (-float(r["eta_difference"]), int(r["index"])))[:3]
        down = sorted(valid, key=lambda r: (float(r["eta_difference"]), int(r["index"])))[:3]
        def text(values):
            return ", ".join(f"{_token(r['token'])} ({_num(r['eta_difference'],3,signed=True)}, DF={r['train_df']})" for r in values)
        lines.append(f"|{name}|{text(up)}|{text(down)}|")
    return lines


def _direction_notes(rows, groups):
    """그룹 합계 감소와 개별 좌표 증가를 구분한다."""
    pairs = [row for row in groups if row["group"] != "duplicate_six"]
    decrease = sorted(pairs, key=lambda row: float(row["contribution_difference"]))
    increase = [row for row in pairs if float(row["contribution_difference"]) > 0]
    lines = []
    if decrease and float(decrease[0]["contribution_difference"]) < 0:
        row = decrease[0]
        lines.append(f"합계 감소를 가장 크게 만든 묶음은 **{row['group_name']}**이며 변화는 {_num(row['contribution_difference'],2,signed=True)}%p다.")
    if increase:
        lines.append("반대로 " + ", ".join(f"{row['group_name']}({_num(row['contribution_difference'],2,signed=True)}%p)" for row in increase) + "는 증가했다. 따라서 모든 서식·괄호 토큰의 영향이 줄었다고 설명할 수 없다.")
    example = next((row for row in rows if row["token"] == r"latex:\cos" and
                    float(row["contribution_difference"]) > 0 and int(row["rank_change"]) < 0), None)
    if example:
        lines.append(f"비율과 순위도 별개다. {_token(example['token'])}는 기여율이 {_percent(example['euclidean_contribution'])}→{_percent(example['cosine_contribution'])}로 늘었지만, 다른 토큰의 증가가 더 커 순위는 {example['euclidean_rank']}→{example['cosine_rank']}로 내려갔다.")
    return lines


def build_report(root, output, summary=None):
    """새 분석 폴더의 표만 읽고 문서·PNG를 생성한다."""
    root, output = Path(root), Path(output)
    if summary is None:
        summary = read_json(output / "summary.json") if (output / "summary.json").exists() else {}
    rows = read_csv(output / "token_distance_contributions.csv")
    groups = read_csv(output / "requested_token_groups.csv")
    eta = read_csv(output / "normalized_eta_comparison.csv")
    distances = read_csv(output / "within_between_distances.csv")
    old = read_csv(output / "old_clustering_metrics.csv")
    associations = read_csv(output / "cluster_norm_association.csv")
    length_associations = read_csv(output / "length_distance_association.csv")
    categories = read_csv(output / "category_contributions.csv")
    if len(rows) != 346 or len(eta) != 4 * 346 or len(distances) != 8 or len(old) != 8:
        raise ValueError("거리 보고서의 346좌표·4분류·두 거리 조건이 기존 연구와 다릅니다.")
    folder = output / "figures"
    folder.mkdir(parents=True, exist_ok=True)
    _draw_contributions(output, rows, groups)
    _draw_eta(output, eta)
    _draw_context(output, distances, old, associations)
    six = next(r for r in groups if r["group"] == "duplicate_six")
    group_lines = ["|좌표 묶음|유클리드 기여|코사인 기여|C−E (%p)|", "|---|---:|---:|---:|"]
    for row in groups:
        group_lines.append(f"|{row['group_name']}|{_percent(row['euclidean_contribution'])}|{_percent(row['cosine_contribution'])}|{_num(row['contribution_difference'],2,signed=True)}|")
    changes = ["|변화 방향|토큰|C−E (%p)|설명용 역할|", "|---|---|---:|---|"]
    for label, selected in (("증가", sorted(rows,key=lambda r:(-float(r['contribution_difference']),int(r['index'])))[:5]),
                            ("감소", sorted(rows,key=lambda r:(float(r['contribution_difference']),int(r['index'])))[:5])):
        for row in selected:
            changes.append(f"|{label}|{_token(row['token'])}|{_num(row['contribution_difference'],2,signed=True)}|{row['category']}|")
    category_lines = ["|기존 설명용 범주|유클리드 기여|코사인 기여|C−E (%p)|", "|---|---:|---:|---:|"]
    for row in categories:
        category_lines.append(f"|{row['category']}|{_percent(row['euclidean_contribution'])}|{_percent(row['cosine_contribution'])}|{_num(row['contribution_difference'],2,signed=True)}|")
    category_notes = []
    extra_increases = [r for r in categories if r["category"] in ("일반 조사·어미·연결어", "분류 불확실·검토 필요")
                       and float(r["contribution_difference"]) > 0]
    if extra_increases:
        category_notes.append("함께 증가한 범주에는 " + ", ".join(f"{r['category']}({_num(r['contribution_difference'],2,signed=True)}%p)" for r in extra_increases) + "도 있다. 정규화가 수학적 의미가 있는 토큰만 선택적으로 강조했다고 판단할 수 없다.")
    sizes = []
    for level, name in LEVELS:
        row = next(r for r in distances if r['level']==level and r['metric']=='euclidean')
        sizes.append(f"|{name}|{row['group_count']}|{row['singleton_groups']}|{row['within_pairs']}|{row['between_pairs']}|")
    eta_changes = _eta_highlights(eta)
    report = ["# 유클리드·코사인: 토큰 영향과 실제 분류의 관계", "",
        "**학습185문항·고정346차원·서로 다른17,020쌍의 통계만 추가했다.** 기존 모델의 재학습·새 군집 배정·불용어 선정/적용·회귀/신경망·Gemini 호출은 없다.", "",
        "## 1. 코사인 관점이 필요한 이유", "",
        "원시 유클리드는 문항의 토큰 사용 규모와 방향 차이를 함께 반영한다. 코사인은 각 문항을 L2 노름으로 나누어 방향을 비교한다. 이때 각 토큰은 같은 상수로 나뉘는 것이 아니라 문항마다 다른 크기로 나뉘므로, 토큰별 상대적 거리 기여와 라벨 연관성도 달라질 수 있다.", "",
        f"중괄호·좌우 표시·소괄호 **6좌표의 기여는 {_percent(six['euclidean_contribution'])} → {_percent(six['cosine_contribution'])}**, 변화는 **{_num(six['contribution_difference'],2,signed=True)}%p**다. 제시됐던 근삿값을 정답으로 넣지 않고 기존 벡터에서 계산한 결과다.", "",
        "## 2. 계산 정의와 비교 단위", "",
        "학습 문항의 i<k인 모든 쌍을 한 번씩 사용했다: 185×184/2=17,020쌍. 원시 좌표 차이 제곱의 평균을 토큰 j의 제곱 유클리드 기여로 정했다. 코사인 기여는 L2 정규화 좌표 차이 제곱의 절반을 같은 쌍에서 평균했다.", "",
        "- 제곱 유클리드: d_E²(x,y)=Σ_j(x_j−y_j)².",
        "- 영벡터가 아닌 문항에서 z=x/||x||₂이고 d_cos(x,y)=1−cos(x,y)=½Σ_j(z_j−w_j)².",
        "- 토큰 기여율=100×해당 좌표의 평균 기여/모든 좌표의 평균 기여 합. 두 방식 각각346좌표의 합은100%다.",
        "- 모집단 분산 V의 분모는185다. 모든 서로 다른 쌍의 평균 좌표 제곱차는 2n/(n−1)×V이므로, 두 방식 각각 기여율은 해당 표현의 V_j/ΣV와 같다.",
        "- CSV contribution 열은% 단위, contribution_difference는 코사인−유클리드의 퍼센트포인트(%p)다. 순위1이 가장 크며 동률은 기존 어휘 인덱스 순서다. rank_change=유클리드 순위−코사인 순위이며 양수는 순위 상승이다.",
        "- 원시 분산과 정규화 분산의 척도는 다르다. 절댓값 감소를 중요도 감소로 해석하지 않고, 각 거리 안의 상대 기여율을 비교한다.",
        "- 현재 학습185문항에는 영벡터가 없다. 영벡터가 발견되면 코사인의 위 항등식이 적용되지 않으므로 임의 거리·토큰 기여를 넣지 않고 명확히 중단하도록 했다.", "",
        "코사인 기여도는 **현재346좌표로 정규화한 표현의 가법적 거리 분해**다. 토큰을 실제 제거한 뒤 다시 정규화하면 남은 모든 좌표의 분모가 바뀐다. 낮은 기여가 삭제해도 안전하다는 뜻도, 높은 기여가 제거 후 코사인 거리가 정확히 그만큼 줄어든다는 뜻도 아니다.", "",
        "[전체346좌표와 순위](token_distance_contributions.csv) · [좌표 묶음](requested_token_groups.csv) · [검증](validation.json)", "",
        "![거리별 상위20](figures/contribution_top20.png)", "",
        "## 3. 어떤 토큰의 상대적 영향이 달라졌는가?", "", *_contribution_table(rows), "",
        "![동일 토큰 비교](figures/selected_token_contributions.png)", "", *group_lines, "",
        "6좌표 합계 행은 앞의 세 쌍을 합친 값이므로 네 행 전체를 다시 합치지 않는다. 같은 패턴을 두 좌표가 공유하면 거리에서 반복 가중된다. 코사인에서도 이 그룹의 비중은 남아 있으며 수식 복잡도나 분류별 표기 방식과 관련될 수 있다.", "",
        *_direction_notes(rows, groups), "",
        "![중복6좌표](figures/duplicate_group_contributions.png)", "", *changes, "",
        "설명용 범주별 상대 기여도도 함께 본다. 수학 명령·개념이 상대적으로 강조되더라도 이것만으로 실제 분류 성능이 개선됐다고 결론내리지 않는다. 변수·숫자·서식도 조건과 구조의 흔적을 담을 수 있다.", "", *category_lines, "", *category_notes, "",
        "## 4. 정규화 전후 η²는 어떻게 달라졌는가?", "",
        "같은 계층 경로와 학습185문항으로 원시·정규화 공간을 각각 분산 분해했다. 각 공간에서 전체 분산=집단 간 분산+집단 내 분산이며 η²=집단 간/전체다. 전체 분산0인 좌표의 η²와 그 변화량은 정의되지 않음으로 남겼다.", "",
        "과목은 curriculum, 단원은 curriculum/unit, 세부단원은 curriculum/unit/subunit, 유형은 curriculum/unit/subunit/type 경로를 사용했다. 자료군을 뜻하는 subject를 과목 라벨로 사용하지 않았으며 이름이 같은 하위 분류도 상위 경로가 다르면 구분했다.", "",
        "[모든1384좌표·수준의 분산 분해/η²/조정η²/DF](normalized_eta_comparison.csv)", "",
        "![원시와정규화eta](figures/normalized_eta_scatter.png)", "", *eta_changes, "",
        "![주요토큰eta](figures/selected_eta_comparison.png)", "",
        "[η² 증가·감소가 큰 토큰 각10개 그림](figures/eta_change_extremes.png)", "",
        "높은 η²는 문항 표본 안의 연관성이며 유용성 판정이 아니다. 유형70개에185문항으로 희귀 유형·단일 문항 집단이 많다. 조정η²=1−(1−η²)(n−1)/(n−g), 집단 크기와 DF를 함께 제공하며 음수 보조 지표도 그대로 보존한다. 분류 수준 간 점수의 단순 우열 비교를 피한다.", "",
        "## 5. 같은 분류의 문제는 더 가까운가?", "", *_distance_table(distances), "",
        "이 표의 유클리드는 일반 거리 ||x−y||₂다. 앞의 토큰 기여도는 **제곱거리**를 분해했으므로 두 평균을 혼동하지 않는다. 코사인은1−cos이며 두 거리의 절댓값을 직접 비교하지 않는다. 간/내부 비율도 평균적인 집계이고 군집 성능 점수가 아니다. 비율은 단위를 없애지만 제곱 같은 비선형 변환에는 불변이 아니므로 비율 크기만으로 두 거리의 우열을 정하지 않는다.", "",
        "![내부간거리](figures/within_between_distances.png)", "",
        "|분류|집단 수|내부쌍 없는1문항 집단|같은 분류 쌍|다른 분류 쌍|", "|---|---:|---:|---:|---:|", *sizes, "",
        "문항쌍 기준 평균에서는 큰 집단이 더 많은 내부쌍을 만든다. 내부쌍이 없는 집단이나 분모0은0으로 대체하지 않았다. 클래스별·동일 가중 macro 결과와 중앙값은 아래 자료에서 함께 확인한다. 17,020쌍은185문항을 반복 사용하므로 독립표본17,020개가 아니며 유의성 검정을 수행하지 않았다.", "",
        "[평균·중앙값·차이·비율·macro](within_between_distances.csv) · [분류별 내부/다른 분류 비교](class_pair_distances.csv) · [17,020문항쌍](document_pair_distances.csv)", "",
        "## 6. 기존 K-means 결과와 연결", "", *_old_table(old), "",
        "이 표는 기존 학습185→테스트80 실험의 summary.csv를 읽어 온 값이다. 이번에 새로운 ARI·NMI를 계산하거나 군집을 재학습하지 않았다. 거리 분석은학습185, 이 성능표는 테스트80이라는 대상 차이를 유지한다.", "",
        "![기존테스트ARI](figures/old_test_ari_comparison.png)", "",
        "[군집별 길이·L2 노름과 해석의 상세 근거](clustering_context.md) · [원래 실험 결과](../../final_experiment/01_clustering/README.md)", "",
        "## 7. 확인된 사실과 아직 검증하지 못한 원인", "",
        "확인한 것은 토큰별 상대 기여와 η², 실제 분류 내부·간 거리, 이미 저장된 군집의 길이 분포 사이의 관계다. 평균적으로 같은 분류끼리 더 가깝더라도 실제 K-means의 테스트 ARI가 더 높다는 보장은 없다.", "",
        "원시 유클리드 K-means와 Spherical K-means는 입력 정규화뿐 아니라 군집 중심 갱신·정규화도 다르다. 거리 통계만으로 원인을 L2 정규화 하나로 확정할 수 없다. 정규화 유클리드 K-means를 새로 학습하는 분리 실험은 이번에 수행하지 않았다.", "",
        "불용어 선정·제거·회귀/신경망·Gemini 실험도 하지 않았다. 기존 분석과 두 사용자 선택 파일은 그대로 보존하고, 다음 실험은 사용자의 후속 결정을 기다린다.", "",
        "## 자료·실행 안내", "",
        "`python -m mathhint_analysis.token_analysis.distance_comparison analyze`는 기존 자료로 이 통계를 생성하고, `report`는 저장 표로 문서·그림만 재생성하며, `verify`는 무결성과 계산을 대조한다. 어떤 명령에도 모델 학습·API 실행 기능이 없다.", "",
        "[기존 토큰 분석](../README.md) · [검증 기록](validation.json) · [설정·입력 출처](config.json)"]
    _write(output / "README.md", report)

    deltas = []
    for level, name in LEVELS:
        a,b = [next(r for r in old if r['level']==level and r['method']==m) for m in ('euclidean','spherical')]
        deltas.append(f"- {name}: 구면−유클리드 ARI 차이 **{_num(float(b['ari'])-float(a['ari']),6,signed=True)}**.")
    norm_lines = ["|분류|유클리드 군집의 L2 노름 η²|구면 군집의 L2 노름 η²|", "|---|---:|---:|"]
    for level, name in LEVELS:
        a,b = [next(r for r in associations if r['level']==level and r['method']==m) for m in ('euclidean','spherical')]
        norm_lines.append(f"|{name}|{_num(a['l2_eta_squared'])}|{_num(b['l2_eta_squared'])}|")
    length_lines = ["|거리|거리와 L2 노름 차이 절댓값의 Pearson 상관|거리와 L1 차이 절댓값의 Pearson 상관|", "|---|---:|---:|"]
    for row in length_associations:
        label = "일반 유클리드" if row["metric"] == "euclidean" else "코사인1−cos"
        length_lines.append(f"|{label}|{_num(row['pearson_distance_vs_abs_l2_difference'])}|{_num(row['pearson_distance_vs_abs_l1_difference'])}|")
    norm_decomposition = summary.get("context", {}).get("norm_distance_diagnostics", {})
    decomposition_lines = []
    if norm_decomposition:
        decomposition_lines = [
            "제곱 유클리드 거리의 대수적 항등식도 별도로 확인했다: d_E²=(||x||−||y||)²+2||x||||y||×d_cos.",
            f"첫 노름 차이 제곱항의 전체 평균 제곱거리 비중은 {_percent(norm_decomposition['norm_difference_squared_share_pct'])}다. 이는 같은 원시 거리를 항으로 나눈 수치이며, 토큰을 없앴을 때의 효과나 군집화 성능 차이의 인과적 기여율을 추정한 것이 아니다.", ""]
    context = ["# 거리 통계와 기존 K-means 결과의 연결", "",
        "이번 통계는 학습185문항의 표현을 분석한다. 아래 ARI·NMI는 기존 모델이 별도 테스트80문항에서 얻은 값이며 이번 분석의 새 성능 실험이 아니다.", "", *_old_table(old), "", *deltas, "",
        "과목에서 구면 방식의 ARI 차이가 가장 크다. 단원과 세부단원의 수치 차이는 작고, 문제 유형에서는 유클리드가 더 높다. 반복 분할이나 유의성 검정을 하지 않았으므로 작은 차이를 통계적으로 확정적인 우열로 해석하지 않는다.", "",
        "## 내부·간 거리의 방향과 성능을 구별", "", *_distance_table(distances), "",
        "전체 문항쌍을 가중한 평균은 큰 집단에 더 큰 가중치를 준다. 아래 macro는 비교 가능한 같은 클래스 집합을 동일 가중으로 읽기 위한 보조 집계다.", "", *_distance_table(distances, macro=True), "",
        "클래스별 다른 분류 거리는 해당 클래스 대 나머지(one-vs-rest)다. 클래스별 between_pairs를 합하면 교차쌍을 두 번 세므로 전체17,020쌍 검증에는 pooled 표를 사용한다. 내부쌍이 없는 singleton은 클래스별 내부 통계와 comparable macro에서 제외하고 개수를 원표에 남긴다.", "",
        "거리 분리의 평균·비율은 실제 라벨 구조를 관찰하는 값이다. 코사인은 정규화 유클리드 제곱거리의 절반이므로, 비율의 차이에도 비선형 거리 변환이 관여한다. 비율이 높아도 거리 방식의 우열이나 기존 테스트 ARI와의 인과 관계가 입증된 것은 아니다. 군집화는 개별 거리 평균이 아니라 여러 중심에 대한 최적화다.", "",
        "## 문항 길이·벡터 크기와 저장된 군집", "",
        "원래 token_count와 고정 BoW L1 노름, L2 노름을 문항·실제 분류·기존 학습 군집별로 읽었다. 원래 학습 문항의 어휘 밖 토큰은 없으므로 token_count와 L1은 같은 값이며 서로 독립적인 두 증거가 아니다. API 사용량과도 다른 수치다.", "",
        *length_lines, "",
        "[문항쌍별 길이 차이와 거리의 관계](length_distance_association.csv). 이 상관도 반복 문항쌍의 기술 통계이며 p값·인과관계로 해석하지 않는다.", "", *decomposition_lines,
        "[분류별 길이·노름](class_norm_summary.csv) · [기존 군집별 분포](cluster_norm_summary.csv) · [군집-노름 연관성](cluster_norm_association.csv)", "", *norm_lines, "",
        "이 η²는 군집을 집단으로 두었을 때 원시 L2 노름의 분산을 얼마나 나누는지 나타낸다. 실제 교육과정 라벨에 대한 토큰 η²와 다른 통계다. 임의의 군집 번호를 연속 숫자로 보고 상관을 계산하지 않았다. 큰 k·적은 문항의 집단에서는 이 보조 통계도 커질 수 있다.", "",
        "![군집과노름](figures/cluster_norm_association.png)", "",
        "## 가능한 설명과 미확인 부분", "",
        "- 관찰: 정규화는 중복 좌표의 상대적 비중과 일부 개념·연산·변수 좌표의 비중을 바꿨다. 토큰별·설명용 범주별 수치를 함께 읽는다.",
        "- 해석 후보: 원시 유클리드가 절대 토큰 사용 규모와 서식 반복량의 영향을 더 받을 수 있다. 정규화 후에도 서식 좌표가 사라지지 않고 일부 분류와의 연관성이 높아질 수 있다.",
        "- 미확인: 원인 전체를 정규화로 설명할 수 없다. Spherical K-means의 단위 중심 갱신, 초기 중심이 미치는 영향, 목적함수 차이, 학습185와 테스트80의 차이가 함께 있다.",
        "- 미실행: 원인 분리를 위한 정규화 유클리드 K-means·불용어 제거·새로운 성능/유의성 실험은 하지 않았다. Pearson 등의 보조 관계가 저장돼 있더라도 반복 문항쌍을 독립 표본으로 간주한 인과·유의성 결론을 내리지 않는다.", "",
        "[거리·토큰 분석 처음으로](README.md) · [원래 군집화 결과](../../final_experiment/01_clustering/README.md)"]
    _write(output / "clustering_context.md", context)
    return {"figures": 9, "documents": 2, "scope": "saved train185 distance statistics and pre-existing test80 metrics"}
