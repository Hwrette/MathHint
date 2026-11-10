"""저장된 토큰 통계 CSV를 읽어 검토용 문서와 그림만 만든다."""

from collections import Counter
import csv
import json
from pathlib import Path


LEVELS = (("curriculum", "과목"), ("unit", "단원"),
          ("subunit", "세부단원"), ("type", "문제 유형"))
PAIRS = (("latex:{", "latex:}"), (r"latex:\left", r"latex:\right"),
         ("latex:(", "latex:)"))
STRATEGY = "풀이 방법 자연어"
FORMAT_CATEGORIES = {"표시용 LaTeX 명령어", "괄호·수식 구조 기호", "해설지 고정 양식"}
NUMBER_VARIABLE_CATEGORIES = {"LaTeX 숫자", "LaTeX 변수명"}
MATH_CATEGORIES = {"수학 개념 자연어", "LaTeX 수학 명령어", "연산·관계 기호"}


def _rows(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _float(value):
    return None if value in (None, "", "null") else float(value)


def _num(value, digits=4):
    value = _float(value)
    return "정의되지 않음" if value is None else f"{value:.{digits}f}"


def _pct(value):
    value = _float(value)
    return "미제공" if value is None else f"{value:.2%}"


def _token(value):
    # Markdown 표의 열 구분과 토큰에 포함된 백틱을 보호한다.
    value = str(value).replace("|", "\\|")
    delimiter = "``" if "`" in value else "`"
    return delimiter + value + delimiter


def _write(path, lines):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    generated = "\n".join(lines).rstrip() + "\n"
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    blocks = []
    for section in ("distance-comparison", "eta-rankings", "full-dataset-eta"):
        start, end = f"<!-- {section}:start -->", f"<!-- {section}:end -->"
        if start in existing and end in existing:
            block = start + existing.split(start, 1)[1].split(end, 1)[0] + end
            blocks.append((existing.index(start), block))
    if blocks:
        heading, body = generated.split("\n", 1)
        generated = heading + "\n\n" + "\n\n".join(block for _, block in sorted(blocks)) + "\n" + body
    path.write_text(generated, encoding="utf-8")


def _plots():
    from mathhint_learning.ClusterReport import setup_final_plots
    plt = setup_final_plots()
    # 토큰의 $와 백슬래시는 수식이 아니라 원래 문자열로 표시한다.
    plt.rcParams["text.parse_math"] = False
    return plt


def _bar(plt, path, tokens, values, title, xlabel, *, footnote="", rare=None):
    figure, ax = plt.subplots(figsize=(12, max(5, .36 * len(tokens) + 1.8)))
    positions = list(range(len(tokens)))
    bars = ax.barh(positions, values, color=".45", edgecolor="black", linewidth=.4)
    if rare:
        for bar, is_rare in zip(bars, rare):
            if is_rare:
                bar.set_hatch("///")
    ax.set_yticks(positions, tokens, fontsize=9)
    ax.invert_yaxis()
    ax.set(xlabel=xlabel, title=title)
    ax.bar_label(bars, fmt="%.4f", padding=3, fontsize=8)
    maximum = max(values, default=0)
    ax.set_xlim(0, maximum * 1.22 if maximum else 1)
    if xlabel.startswith("η²"):
        ax.set_xlim(0, 1.08)
        ax.set_xticks([0, .2, .4, .6, .8, 1])
    if footnote:
        figure.text(.5, .015, footnote, ha="center", fontsize=9)
    figure.tight_layout(rect=(0, .055 if footnote else 0, 1, 1))
    figure.savefig(path, dpi=190)
    plt.close(figure)


def _draw_problem_figures(output, problem, solution, variance, redundancy):
    import numpy as np
    from matplotlib.ticker import FuncFormatter, NullFormatter
    plt = _plots()
    folder = output / "01_problem_tokens/figures"
    folder.mkdir(parents=True, exist_ok=True)
    top = sorted(problem, key=lambda row: (-float(row["train_variance"]), int(row["index"])))[:20]
    _bar(plt, folder / "variance_top20.png", [r["token"] for r in top],
         [float(r["train_variance"]) for r in top], "문제 토큰 분산 상위20 · 학습185문항",
         "빈도 분산 · 분모 n=185", footnote="분산이 크다는 사실은 실제 분류를 잘 구별한다는 뜻이 아니다.")
    for level, name in LEVELS:
        eligible = [r for r in variance if r["level"] == level and _float(r["eta_squared"]) is not None]
        chosen = sorted(eligible, key=lambda r: (-float(r["eta_squared"]), -int(r["train_df"]), int(r["index"])))[:20]
        _bar(plt, folder / f"eta_top20_{level}.png", [r["token"] for r in chosen],
             [float(r["eta_squared"]) for r in chosen], f"{name} η² 상위20 · 문제 토큰 · 학습185문항",
             "η² = 집단 간 제곱합 / 전체 제곱합", rare=[int(r["train_df"]) <= 5 for r in chosen],
             footnote="빗금: 학습 DF≤5인 희귀 토큰. 소집단·많은 분류에서는 η²가 커지기 쉬우며 수준 간 단순 비교를 피한다.")
    figure, axes = plt.subplots(2, 2, figsize=(13, 10), constrained_layout=True)
    for ax, (level, name) in zip(axes.flat, LEVELS):
        shown = [r for r in variance if r["level"] == level and float(r["total_variance"]) > 0 and _float(r["eta_squared"]) is not None]
        rare = [int(r["train_df"]) <= 5 for r in shown]
        for is_rare, marker, label, color in ((False, "o", "DF>5", ".25"), (True, "x", "DF≤5", ".65")):
            selected = [r for r, flag in zip(shown, rare) if flag == is_rare]
            ax.scatter([float(r["total_variance"]) for r in selected], [float(r["eta_squared"]) for r in selected],
                       s=23, marker=marker, color=color, label=label, alpha=.75)
        ax.set(xscale="log", ylim=(-.03, 1.05), xlabel="학습185 전체 분산 (로그축)", ylabel="η²", title=name)
        # 토큰의 백슬래시는 그대로 표시하면서 로그 눈금은 일반 숫자로 읽는다.
        ax.xaxis.set_major_formatter(FuncFormatter(lambda value, position: f"{value:g}"))
        ax.xaxis.set_minor_formatter(NullFormatter())
        ax.legend(fontsize=8)
    figure.suptitle("문제 토큰의 거리 영향과 분류 연관성 · 학습185문항\n분산0은 η²가 정의되지 않아 산점도에서 제외", fontsize=13)
    figure.savefig(folder / "variance_eta_scatter.png", dpi=190)
    plt.close(figure)
    by_token = {r["token"]: r for r in problem}
    pair_values = []
    pair_names = []
    for a, b in PAIRS:
        if a in by_token and b in by_token:
            pair_names.append(a + " / " + b)
            pair_values.append(sum(float(by_token[t]["train_distance_contribution_ratio"]) for t in (a, b)) * 100)
    _bar(plt, folder / "redundant_distance_contribution.png", pair_names, pair_values,
         "좌우 토큰 쌍의 제곱거리 기여 비율 · 학습185문항", "서로 다른 모든 문항쌍의 평균 제곱 유클리드 거리 중 비율 (%)",
         footnote="문항쌍 기준 두 좌표의 분산 비율 합이다. 학습된 군집중심까지의 손실 기여를 계산한 값은 아니다.")
    figure, axes = plt.subplots(1, 2, figsize=(12, 4.8), constrained_layout=True)
    regions = (problem, solution)
    for source, color, hatch in (("Kiwi", ".8", ""), ("LaTeX", ".35", "///")):
        counts = [sum(r["source"] == source for r in rows) for rows in regions]
        weights = [sum(int(r["total_tf"]) for r in rows if r["source"] == source) for rows in regions]
        if source == "Kiwi":
            bottoms = [0, 0]
            tf_bottoms = [0, 0]
        else:
            bottoms = [sum(r["source"] == "Kiwi" for r in rows) for rows in regions]
            tf_bottoms = [sum(int(r["total_tf"]) for r in rows if r["source"] == "Kiwi") / sum(int(r["total_tf"]) for r in rows) * 100 for rows in regions]
        values = [weight / sum(int(r["total_tf"]) for r in rows) * 100 for weight, rows in zip(weights, regions)]
        first = axes[0].bar([0, 1], counts, bottom=bottoms, color=color, hatch=hatch, label=source, edgecolor="black")
        second = axes[1].bar([0, 1], values, bottom=tf_bottoms, color=color, hatch=hatch, label=source, edgecolor="black")
        axes[0].bar_label(first, labels=[str(x) for x in counts], label_type="center")
        axes[1].bar_label(second, labels=[f"{x:.1f}%" for x in values], label_type="center", color="white" if source == "LaTeX" else "black")
    for ax in axes:
        ax.set_xticks([0, 1], ["문제", "해설"])
        ax.legend(fontsize=8)
    axes[0].set(title="고정 어휘의 출처별 종류 수", ylabel="토큰 종류 수 · 문제346/해설431")
    axes[1].set(title="전체265문항에서의 출처별 TF 비율", ylabel="고정 어휘 내 등장 횟수 비율 (%)", ylim=(0, 100))
    figure.suptitle("문제·해설의 Kiwi/LaTeX 구성 · OOV는 TF 분모에서 제외")
    figure.savefig(folder / "source_distribution.png", dpi=190)
    plt.close(figure)


def _draw_solution_figures(output, problem, solution, composition):
    import numpy as np
    plt = _plots()
    folder = output / "02_solution_tokens/figures"
    folder.mkdir(parents=True, exist_ok=True)
    top = sorted(solution, key=lambda r: (-int(r["total_tf"]), int(r["index"])))[:20]
    _bar(plt, folder / "tf_top20.png", [r["token"] for r in top], [int(r["total_tf"]) for r in top],
         "해설 토큰 총 등장 횟수 상위20 · 전체265문항", "TF · 고정 해설 어휘431개 안에서 센 총 등장 횟수",
         footnote="TF는 반복 등장까지 합한 횟수다. DF(등장 문항 수)와 다르며 높은 TF가 풀이 전략의 중요도를 보장하지 않는다.")
    categories = list(dict.fromkeys(r["category"] for r in composition))
    figure, ax = plt.subplots(figsize=(13, max(6, .48 * len(categories) + 2)))
    for i, condition in enumerate(("B", "C")):
        by_category = {r["category"]: r for r in composition if r["condition"] == condition}
        values = [float(by_category[c]["coordinate_fraction"]) * 100 if c in by_category else 0 for c in categories]
        y = np.arange(len(categories)) + (i - .5) * .34
        bars = ax.barh(y, values, height=.34, color=".8" if condition == "B" else ".35", edgecolor="black", label="B 예측 해설" if condition == "B" else "C 실제 해설")
        ax.bar_label(bars, fmt="%.1f%%", padding=3, fontsize=8)
    ax.set_yticks(range(len(categories)), categories, fontsize=9)
    ax.invert_yaxis()
    ax.set(xlabel="실제 전송된 토큰 좌표 수 중 범주 비율 (%)", title="Gemini B·C 전송 상위토큰의 범주 구성 · 조건별80문항")
    ax.legend()
    maximum = max((float(r["coordinate_fraction"]) * 100 for r in composition), default=1)
    ax.set_xlim(0, maximum * 1.22)
    figure.text(.5, .015, "각 요청의 token:value 좌표를 한 번씩 센 비율이다. 빈도 값 가중치·API 사용량·힌트 효과의 비율이 아니다.", ha="center", fontsize=9)
    figure.tight_layout(rect=(0, .04, 1, 1))
    figure.savefig(folder / "top20_category_composition.png", dpi=190)
    plt.close(figure)
    pmap, smap = ({r["token"]: r for r in rows} for rows in (problem, solution))
    examples = ["latex:{", "latex:}", r"latex:\left", r"latex:\right", "latex:x", "latex:2", r"latex:\lim", r"latex:\sin", "kiwi:대입", "kiwi:판별식", "kiwi:연속", "kiwi:정답"]
    examples = [token for token in examples if token in pmap or token in smap]
    figure, ax = plt.subplots(figsize=(13, 6.5), constrained_layout=True)
    for i, (mapping, name, color) in enumerate(((pmap, "문제", ".8"), (smap, "해설", ".35"))):
        values = [float(mapping[t]["mean"]) if t in mapping else float("nan") for t in examples]
        bars = ax.bar(np.arange(len(examples)) + (i - .5) * .35, values, width=.35, label=name, color=color, edgecolor="black")
        ax.bar_label(bars, labels=[f"{v:.2f}" if t in mapping else "" for t, v in zip(examples, values)], fontsize=7, rotation=90, padding=3)
        for token, bar in zip(examples, bars):
            if token not in mapping:
                ax.text(bar.get_x() + bar.get_width() / 2, .03, "어휘 없음", rotation=90, va="bottom", ha="center", fontsize=7, transform=ax.get_xaxis_transform())
    ax.set_xticks(range(len(examples)), examples, rotation=65, ha="right", fontsize=8)
    ax.set(ylabel="문항당 평균 빈도 · 전체265문항", title="문제와 해설의 대표 토큰 빈도 · 고정 어휘 안의 기술적 비교")
    ax.legend()
    ax.set_ylim(0, ax.get_ylim()[1] * 1.18)
    figure.savefig(folder / "problem_solution_comparison.png", dpi=190)
    plt.close(figure)


def _stat_tables(problem, variance):
    by_token = {r["token"]: r for r in problem}
    by_eta = {(r["level"], r["token"]): r for r in variance}
    chosen = ["latex:{", "latex:}", r"latex:\left", r"latex:\right", "latex:(", "latex:)",
              r"latex:\lim", r"latex:\sin", r"latex:\cos", r"latex:\tan", r"latex:\pi", r"latex:\theta", "latex:x", "latex:2"]
    chosen += [r["token"] for r in sorted(problem, key=lambda r: (-float(r["train_variance"]), int(r["index"])))[:8]]
    lines = ["|토큰|학습185 전체 분산|과목 η²|단원 η²|세부단원 η²|유형 η²|의미|",
             "|---|---:|---:|---:|---:|---:|---|"]
    for token in dict.fromkeys(chosen):
        if token not in by_token:
            continue
        row = by_token[token]
        etas = [_num(by_eta[(level, token)]["eta_squared"]) for level, _ in LEVELS]
        lines.append("|" + "|".join([_token(token), _num(row["train_variance"]), *etas, row["meaning"].replace("|", "\\|")]) + "|")
    return lines



def _pattern_table(highlights):
    lines = ["|분류 수준|큰 분산·낮은 η²인 관찰 예 (η²)|", "|---|---|"]
    for level, name in LEVELS:
        selected = [r for r in highlights if r["level"] == level and r["pattern"] == "C_high_variance_low_eta"][:5]
        content = ", ".join(f"{_token(r['token'])} ({_num(r['eta_squared'])})" for r in selected) or "해당 교집합 없음"
        lines.append(f"|{name}|{content}|")
    return lines


def _duplicate_table(redundancy):
    selected = []
    for a, b in PAIRS:
        row = next((r for r in redundancy if {r["token_a"], r["token_b"]} == {a, b}), None)
        if row:
            selected.append(row)
    lines = ["|학습185문항의 좌표 쌍|빈도가 같은 문항 수|상관계수|쌍의 제곱거리 기여 비율|", "|---|---:|---:|---:|"]
    for row in selected:
        lines.append(f"|{_token(row['token_a'])} / {_token(row['token_b'])}|{row['counts_equal_documents']}/{row['n']}|{_num(row['pearson_correlation'])}|{_pct(row['pair_distance_contribution_ratio'])}|")
    return lines



def _attention_table(solution, frequency):
    vocabulary = {r["token"]: r for r in solution}
    transmitted = {(r["condition"], r["token"]): int(r["document_count"]) for r in frequency}
    examples = ["kiwi:정답", "kiwi:해설", "kiwi:대입", "kiwi:판별식", "kiwi:연속",
                r"latex:\left", r"latex:\right", r"latex:\lim"]
    lines = ["|관심 토큰|고정 해설 어휘에 포함|B 실제 전송 문항 수|C 실제 전송 문항 수|설명용 역할|", "|---|---|---:|---:|---|"]
    for token in examples:
        if token in vocabulary:
            row = vocabulary[token]
            lines.append(f"|{_token(token)}|예 (인덱스{row['index']})|{transmitted.get(('B', token), 0)}/80|{transmitted.get(('C', token), 0)}/80|{row['category']} · {row['meaning']}|")
        else:
            lines.append(f"|{_token(token)}|아니오|해당 없음|해당 없음|기존 어휘에 없어 전송0과 별도 구분|")
    return lines


def _mixture(composition):
    result = {}
    for condition in ("B", "C"):
        chosen = [r for r in composition if r["condition"] == condition]
        total = int(chosen[0]["total_coordinates"]) if chosen else 0
        groups = {}
        for name, categories in (("서식·구조·고정 양식", FORMAT_CATEGORIES), ("숫자·변수", NUMBER_VARIABLE_CATEGORIES),
                                 ("수학 개념·명령·연산", MATH_CATEGORIES), ("풀이 방법 자연어", {STRATEGY})):
            groups[name] = sum(int(r["coordinate_count"]) for r in chosen if r["category"] in categories)
        groups["그 밖의 일반·불확실 토큰"] = total - sum(groups.values())
        result[condition] = {"total": total, "groups": groups}
    return result


def build_report(root, output, summary=None):
    """모델·토큰화·API를 실행하지 않고 저장된 통계만 문서화한다."""
    root, output = Path(root), Path(output)
    problem = _rows(output / "01_problem_tokens/all_tokens.csv")
    solution = _rows(output / "02_solution_tokens/all_tokens.csv")
    variance = _rows(output / "01_problem_tokens/variance_by_classification.csv")
    redundancy = _rows(output / "01_problem_tokens/redundancy_analysis.csv")
    labels = _rows(output / "01_problem_tokens/class_labels.csv")
    highlights = _rows(output / "01_problem_tokens/highlight_patterns.csv")
    composition = _rows(output / "02_solution_tokens/top20_category_composition.csv")
    top20 = _rows(output / "02_solution_tokens/top20_analysis.csv")
    token_frequency = _rows(output / "02_solution_tokens/top20_token_frequency.csv")
    oov = _rows(output / "03_oov_analysis/excluded_tokens.csv")
    oov_summary = json.loads((output / "03_oov_analysis/summary.json").read_text())
    if len(problem) != 346 or len(solution) != 431 or len(variance) != 4 * 346:
        raise ValueError("보고서의 문제/해설 어휘 또는 학습 분산 분석 행 수가 기존 연구와 다릅니다.")
    if len(top20) != 160:
        raise ValueError("B·C 요청별 분석은 고정 테스트80문항×2조건이어야 합니다.")
    _draw_problem_figures(output, problem, solution, variance, redundancy)
    _draw_solution_figures(output, problem, solution, composition)
    pmap = {r["token"]: r for r in problem}
    pair_tokens = {token for pair in PAIRS for token in pair if token in pmap}
    pair_share = sum(float(pmap[t]["train_distance_contribution_ratio"]) for t in pair_tokens)
    top_variance = sorted(problem, key=lambda r: (-float(r["train_variance"]), int(r["index"])))[:20]
    mixture = _mixture(composition)
    b_rows = [r for r in top20 if r["condition"] == "B"]
    mean_common = sum(float(r["common_vector_top20"]) for r in b_rows) / len(b_rows)
    mean_precision = sum(float(r["vector_precision_at_20"]) for r in b_rows) / len(b_rows)
    mean_transmitted_common = sum(float(r["common_bc_transmitted"]) for r in b_rows) / len(b_rows)
    omitted = sum(int(r["omitted_after_rounding"]) for r in top20)
    overlap_note = (f"예측·실제 해설의 전체 벡터 상위20 공통 수는 문항당 평균 {mean_common:.4f}개, "
                    f"Precision@20은 {mean_precision:.6f}다(분모20). 실제 전송된 B·C 집합의 공통 수 평균은 {mean_transmitted_common:.4f}개다. "
                    f"이번160요청에서 표시 반올림 후 0이 되어 생략된 좌표는 {omitted}개다. 이 값은 풀이 정답률이 아니다.")
    mix_lines = ["|실제 전송 좌표의 설명용 범주|B 예측 해설|C 실제 해설|", "|---|---:|---:|"]
    for category in mixture["B"]["groups"]:
        b, c = (mixture[k]["groups"][category] for k in ("B", "C"))
        mix_lines.append(f"|{category}|{b}/{mixture['B']['total']} ({_pct(b / mixture['B']['total'])})|{c}/{mixture['C']['total']} ({_pct(c / mixture['C']['total'])})|")
    top_names = ", ".join(_token(r["token"]) for r in top_variance[:6])
    eta_lookup = {(r["level"], r["token"]): r for r in variance}
    brace_token, sine_token = "latex:{", r"latex:\sin"
    evidence_contrast = (f"{_token(brace_token)}의 학습 분산은 {_num(pmap[brace_token]['train_variance'])}, "
                         f"과목 η²는 {_num(eta_lookup[('curriculum', brace_token)]['eta_squared'])}다. "
                         f"{_token(sine_token)}은 분산 {_num(pmap[sine_token]['train_variance'])}, "
                         f"과목 η² {_num(eta_lookup[('curriculum', sine_token)]['eta_squared'])}다. "
                         "큰 거리 기여와 특정 분류의 구별 능력은 같은 순위를 보이지 않는다.")

    eta_lines = ["|분류 수준|학습 집단 수|1문항 집단 수|η² 상위3 토큰|", "|---|---:|---:|---|"]
    for level, name in LEVELS:
        groups = [r for r in labels if r["level"] == level]
        eligible = [r for r in variance if r["level"] == level and _float(r["eta_squared"]) is not None]
        best = sorted(eligible, key=lambda r: (-float(r["eta_squared"]), -int(r["train_df"]), int(r["index"])))[:3]
        eta_lines.append(f"|{name}|{len(groups)}|{sum(int(r['n']) == 1 for r in groups)}|" + ", ".join(f"{_token(r['token'])} ({_num(r['eta_squared'])}, DF={r['train_df']})" for r in best) + "|")
    oov_regions = oov_summary.get("regions", oov_summary)
    oov_lines = ["|영역|제외된 등장 횟수 / 테스트 전체 토큰 수|제외 토큰 등장 비율|제외 토큰 종류|", "|---|---:|---:|---:|"]
    for region, name in (("problems", "문제"), ("solutions", "해설")):
        stat = oov_regions[region]
        oov_lines.append(f"|{name}|{stat['ignored_tf']}/{stat['test_total_tokens']}|{_pct(float(stat['ignored_fraction']))}|{stat['unique_oov_tokens']}|")
    problem_readme = ["# 문제 토큰 · 학습185문항의 분산과 분류 연관성", "",
        "먼저 분산 상위 토큰과 아래 표를 본다. 통계는 사용자가 토큰을 검토할 근거이며 제거/유지 결정을 내리지 않았다.", "",
        "- [전체346토큰과 학습/테스트 TF·DF](all_tokens.csv)",
        "- [4분류 수준×346토큰 분산 분해](variance_by_classification.csv) · [분류별 토큰 평균·DF](class_token_means.csv) · [집단 크기](class_labels.csv)",
        "- [같거나 유사한 빈도 좌표](redundancy_analysis.csv) · [통계적 관찰 패턴](highlight_patterns.csv)", "",
        "## 분산과 거리 영향", "", "![문제 토큰 분산 상위20](figures/variance_top20.png)", "",
        "이 그림과 η²는 학습185문항 기준이다. all_tokens.csv의 mean/variance/std는 전체265문항의 라벨을 사용하지 않는 빈도 통계이고, train_mean/train_variance/train_std가 학습 기준이다.", "",
        "## 주요 토큰을 같은 표에서 비교", "", *_stat_tables(problem, variance), "",
        "## 분류별 η²", "", *eta_lines, "", "### 큰 분산·낮은 η²의 관찰 예", "", *_pattern_table(highlights), "", "이 표는 각 수준에서 분산≥75백분위수·η²≤중앙값인 교집합을 요약한다. 삭제 후보나 최종 선택 목록이 아니다.", ""]
    for level, name in LEVELS:
        problem_readme += [f"- [{name} η² 상위20](figures/eta_top20_{level}.png)"]
    problem_readme += ["", "![분산과 eta 관계](figures/variance_eta_scatter.png)", "",
        "η²가 높은 희귀 토큰은 해당 소집단에만 우연히 나타난 결과일 수 있다. 특히 유형70개에는 표본1개인 집단이 많다. 토큰별 train_df·집단 크기·adjusted_eta_squared를 함께 보되 이것으로 불용어를 자동 선정하지 않는다.", "",
        "## 중복 좌표", "", f"명시적으로 비교한 중괄호·좌우 표시·소괄호의 6좌표가 학습 제곱거리에서 차지하는 합은 {_pct(pair_share)}다. 같은 빈도 패턴을 여러 좌표로 표현하면 그 패턴의 거리 가중치가 반복된다. 괄호 개수는 수식 복잡도의 흔적도 담을 수 있으므로 통계적 중복을 제거의 근거 하나로만 읽는다.", "",
        "![중복쌍 거리 기여](figures/redundant_distance_contribution.png)", "", *_duplicate_table(redundancy), "",
        "다른 토큰의 빈도 벡터가 같더라도 수학적 의미가 같다는 뜻은 아니다. 특히 희귀 토큰이 같은 소수 문항에만 나타나면 서로 다른 개념도 동일 패턴이 될 수 있다.", "",
        "## Kiwi·LaTeX 분포와 문제/해설의 차이", "", "![출처 분포](figures/source_distribution.png)", "",
        "[정의·분모·토큰화 한계의 전체 보고서](../token_analysis_report.md) · [처음으로](../README.md)"]
    _write(output / "01_problem_tokens/README.md", problem_readme)
    frequent_lines = ["|조건|실제 전송 상위토큰에 자주 포함된 토큰 (문항 수)|", "|---|---|"]
    for condition in ("B", "C"):
        chosen = sorted([r for r in token_frequency if r["condition"] == condition], key=lambda r: (-int(r["document_count"]), int(r["index"])))[:12]
        frequent_lines.append(f"|{condition}|" + ", ".join(f"{_token(r['token'])} ({r['document_count']}/80)" for r in chosen) + "|")
    solution_readme = ["# 해설 토큰과 기존 Gemini의 실제 상위토큰", "",
        "해설431차원의 기술 통계와 기존 B·C 요청 기록을 읽었다. 회귀 모델을 로드하거나 새 토큰으로 Gemini를 호출하지 않았다.", "",
        "- [전체431토큰 TF·DF·분산](all_tokens.csv)",
        "- [160요청별 전송/전체벡터 상위20 비교](top20_analysis.csv)",
        "- [실제 전송 token:value 좌표](transmitted_tokens.csv) · [토큰별 등장 문항 수](top20_token_frequency.csv) · [11범주 구성](top20_category_composition.csv)", "",
        "## 해설 자체에서 자주 나타나는 토큰", "", "![해설 TF 상위20](figures/tf_top20.png)", "",
        "## B·C 실제 전송 구성", "", *mix_lines, "", "![실제 전송 범주](figures/top20_category_composition.png)", "",
        "표의 분모는 각 조건80개 요청의 실제 전송된 token:value 좌표 수다. 한 요청에서 한 토큰을 한 번 센다. 토큰의 예측 빈도 값으로 가중하지 않았으며 API 토큰 사용량도 아니다.", "",
        *frequent_lines, "", "### 관심 토큰이 실제로 포함된 문항 수", "", *_attention_table(solution, token_frequency), "", "어휘에 있으나 전송되지 않은 토큰은0/80이다. 어휘 자체에 없는 표현은 ‘해당 없음’으로 구분한다. 높은 전송 문항 수가 실제 풀이에 유용했다는 뜻은 아니다.", "", "## 전체 벡터 상위20과 실제 전송의 구분", "",
        "B는 저장된 실수 예측을 음수0보정한 뒤 반올림 전 양수 빈도로 내림차순 정렬하고, 동률은 기존 어휘 인덱스 순서로 처리했다. C도 같은 어휘와 규칙으로 실제 해설 빈도를 사용했다. 최대20개를 고른 다음 소수점3자리 표시에서 0이 된 값은 전송에서 빠질 수 있다. CSV는 선택된 전체 벡터 토큰과 실제 prompt_audit의 hint.mapping을 따로 비교한다.", "",
        "B의 기존 요청 파일은 과거 성공 응답의 입력을 바탕으로 복원하고 원본 입력·힌트와 정확히 대조한 감사 자료다. C는 실제 SDK 호출 직전 기록도 대조했다. 복원 기록을 과거 시점의 실시간 SDK 캡처로 표현하지 않는다.", "",
        overlap_note, "", "상위20 집합의 공통 토큰 수/20은 빈도 표현의 일치도다. 특정 원본 해설과 빈도가 다르더라도 다른 올바른 풀이가 가능하므로 수학적 정오로 해석하지 않는다.", "",
        "## 문제와 해설의 대표적인 빈도 차이", "", "![문제해설 대표토큰](figures/problem_solution_comparison.png)", "",
        "이 그림에서 고정 어휘에 없는 토큰은 0 막대를 만들지 않고 ‘어휘 없음’으로 표시한다. 정확한 어휘 포함 여부와 TF는 각 all_tokens.csv에서 확인한다. 문제·해설은 목적과 길이가 다르므로 같은 토큰의 높은 빈도만으로 중요도를 판단하지 않는다.", "",
        "## 해석의 경계", "", "서식·숫자·변수 비중은 입력의 구성에 관한 관찰이다. 이것만으로 힌트가 유용하지 않았다거나, 특정 토큰을 지우면 정답률이 개선된다고 결론내릴 수 없다. 현재 설명용 역할 사전에서 ‘풀이 방법 자연어’로 분류한 토큰은 B·C에서 모두 0좌표다. 이는 명시적인 해당 자연어 범주가 없다는 관찰이며, 수학 명령·연산에 암묵적 단서가 없었다는 뜻이 아니다. 범주에 ‘표시’가 붙어도 인수·단위·조건 정보를 담을 수 있고, ‘불확실’에는 모든·항상·만족 같은 논리 조건도 포함된다. 실제 대안 입력의 효과는 이번에 검증하지 않았다.", "",
        "[처음으로](../README.md) · [전체 해석](../token_analysis_report.md)"]
    _write(output / "02_solution_tokens/README.md", solution_readme)
    oov_examples = sorted(oov, key=lambda r: (r["region"], -int(r["total_tf"]), r["token"]))
    oov_readme = ["# 학습 어휘 밖의 테스트 토큰", "", *oov_lines, "",
        "비율의 분모는 해당 영역 테스트80문항의 모든 원래 토큰 등장 횟수다. 기존 벡터의 합과 제외 횟수를 합친 값이며, 토큰 종류 수 비율이나 정보 의미의 손실률을 뜻하지 않는다.", "",
        "[제외 토큰 전체 목록·등장 문항·의미·손실 가능성](excluded_tokens.csv)", "",
        "|영역|토큰|TF|DF|의미와 정보 손실 가능성|", "|---|---|---:|---:|---|"]
    for row in oov_examples:
        oov_readme.append(f"|{'문제' if row['region']=='problems' else '해설'}|{_token(row['token'])}|{row['total_tf']}|{row['total_df']}|{row['meaning'].replace('|', '\\|')} {row['information_loss_if_removed'].replace('|', '\\|')}|")
    oov_readme += ["", "이 토큰들은 학습185문항에서 나타나지 않아 학습 전용 어휘에 포함되지 않았다. 새 어휘를 추가하지 않았고 원래 벡터도 수정하지 않았다. 적은 제외 횟수라도 특정 수학적 조건의 표현이 빠질 수 있으며, 빈도만으로 의미상의 영향이 작다고 단정하지 않는다.", "",
        "[원문 재토큰화·저장 제외기록 대조](summary.json) · [처음으로](../README.md)"]
    _write(output / "03_oov_analysis/README.md", oov_readme)
    report = ["# MathHint 1단계: 토큰 표현과 실제 분류의 관계", "",
        "이번 단계의 가설은 ‘거리 계산을 크게 좌우하는 토큰이 실제 수학적 분류와도 강하게 연관되는가’다. 답을 미리 정하지 않고 기존 원시 빈도와 학습 분류만 기술적으로 분석했다. 후속 불용어 목록은 사용자가 정하며 모델 개선 효과는 아직 실험하지 않았다.", "",
        "## 1. 데이터와 분석 경계", "", "문제265개, 기존 학습185/테스트80 분할과 문제346·해설431개의 학습 전용 어휘를 유지했다. 전체 TF·DF·mean/variance/std는 고정 어휘 안의 전체265 통계이며, 분류별 분산 분해와 거리 기여도·중복 비교의 주 분석은 학습185만 사용한다. 테스트 라벨로 토큰을 선정하지 않았다. 별도의 전체265 분류 연관성 실험도 수행하지 않았다.", "",
        "## 2. 토큰화가 보존하는 것과 잃는 것", "",
        "수식 경계($...$, $$...$$, \\(…\\), \\[…\\])를 먼저 분리한 뒤 자연어 영역은 Kiwi의 문맥 기반 형태소 분석으로 나눈다. 조사·어미·문장부호도 세며, 저장한 것은 token.form이다. 품사표와 원문 위치는 벡터에 남기지 않으므로 같은 ‘이’가 지시어·조사 등 여러 역할을 합칠 수 있다. 설명용 역할 범주에는 이런 모호성을 남겼다.", "",
        r"LaTeX 영역의 정규식은 `\\[A-Za-z]+|\\[^\s]|[0-9]+(?:\.[0-9]+)?|[^\s]`다. 영문 명령어, 백슬래시 기호 명령, 정수·소수 숫자열, 나머지 비공백 한 글자 순서로 분리한다. `\frac`, `\lim`, `\sin`, `\left`, `\right`는 각각 명령 토큰이고 `{`, `}`, `(`, `)`도 독립 좌표다. 일반 영문 변수는 한 글자씩 나뉘며 숫자의 부호·지수·첨자는 별도 기호/숫자 좌표로 나뉜다. 예컨대 `\begin{cases}`의 환경명도 문자 조각으로 세어질 수 있어, 글자 좌표가 항상 변수 역할을 뜻하는 것은 아니다.", "",
        "BoW는 각 조각의 등장 횟수와 Kiwi/LaTeX 출처만 보존한다. 어떤 괄호가 어느 괄호와 짝인지, 분자/분모·밑/지수·변수의 역할, 항의 순서, 같은 문장·수식 안에서의 연결 관계는 빈도 합으로 복원할 수 없다. 괄호·서식의 횟수에는 표기 길이나 복잡도의 흔적이 남을 수 있지만 수식 구조 자체가 보존된 것은 아니다.", "",
        r"실제 어휘에는 `latex:\ge`와 `latex:\geq`, `latex:\le`와 `latex:\leq`처럼 같은 관계를 나타낼 수 있는 별도 표기가 있다. 해설에는 `latex:\to`와 `latex:\rightarrow`, `latex:\ne`와 `latex:\neq`도 함께 존재한다. 이번에는 통합하지 않았다. 같게 보이는 문자라도 Kiwi/LaTeX 영역이나 명령 표기 차이로 서로 다른 좌표가 될 수 있다.", "",
        "## 3. TF·DF와 분산의 정의", "",
        "TF는 문항 안의 반복을 모두 합한 등장 횟수, DF는 한 번 이상 나온 문항 수다. 한 문제에서 x가10번 나오면 TF에는10, DF에는1을 더한다. 인덱스는 원래 vocabulary.json의 0기준 좌표를 그대로 쓴다.", "",
        "n개 문항의 빈도 x에 대해 평균 μ=Σx/n, 전체 분산 V=Σ(x−μ)²/n, 표준편차=√V로 계산한다(ddof=0). 분류 g의 크기 n_g와 평균 μ_g로 집단 간 분산 V_B=Σn_g(μ_g−μ)²/n, 집단 내 분산 V_W=Σ_gΣ_i∈g(x_i−μ_g)²/n이다. V=V_B+V_W이고 η²=V_B/V다. V=0이면 η²는 정의되지 않아 CSV 빈칸과 문서의 ‘정의되지 않음’으로 남겼다. η²의 이론 범위 경계에서 발생한 절대1e-12 이내의 부동소수점 오차만 0 또는 1로 정리했으며, 원시 분산·제곱합은 바꾸지 않았다.", "",
        "서로 다른 문항의 모든 쌍에 대한 한 좌표의 평균 제곱차는 2n/(n−1)×V다. 모든 좌표에 공통인 계수가 약분되므로 전체 제곱 유클리드 거리의 기여 비율은 V_j/ΣV다. 이는 코사인 거리 기여도나 수학적 중요도의 비율이 아니며, 학습된 군집중심까지의 K-means 손실 기여를 계산한 값도 아니다.", "",
        "## 4. 거리 영향과 분류 연관성의 관찰", "", f"학습 분산 상위에는 {top_names} 등이 있다. " + evidence_contrast + " 원문 전체의 빈도와 분류 사이의 관계는 다음 표에서 함께 읽는다.", "", *_stat_tables(problem, variance), "",
        "분산이 크지만 특정 수준의 η²가 낮으면 거리 영향과 해당 라벨의 구별 능력이 다를 가능성이 있다. 반대로 희귀 토큰의 높은 η²는 작은 집단에 한 번만 나타난 효과일 수 있다. 상위 토큰 목록 자체는 유용성 판정이나 삭제 추천이 아니다. highlight_patterns.csv의 ‘큰 분산·낮은 η²’는 해당 수준에서 분산이75백분위수 이상이고 η²가 중앙값 이하인 교집합을 기술한 것이며 토큰 선택 규칙으로 사용하지 않았다.", "", *eta_lines, "",
        "분산이 큰데도 해당 분류와의 연관성이 낮은 예는 다음과 같다.", "", *_pattern_table(highlights), "",
        "조정된 η²는 1−(1−η²)×(n−1)/(n−g)로 계산했다. g는 해당 분류 수준의 집단 수다. 음수도 그대로 두고 n≤g 또는 V=0이면 정의되지 않는다. 작은 표본과 많은 집단의 영향을 보조적으로 읽기 위한 값이며 유의성 검정이 아니다. 네 수준의 η²는 집단 수가 다르므로 높은 수준을 자동으로 더 유용하다고 판단하지 않는다. 서식·구조 토큰도 분류별 표기 양식이나 복잡도와 함께 변할 수 있으므로, 관찰된 η²만으로 수학적 의미나 제거 효과를 확정할 수 없다.", "",
        "## 5. 좌우 중복의 관찰", "", f"중괄호·좌우 표시·소괄호 쌍의 6좌표는 학습 제곱거리 기여의 합 {_pct(pair_share)}를 차지한다. 동일 빈도 쌍은 내용 하나가 두 좌표에서 반복 가중되는 현상으로 읽을 수 있다. 한쪽만 지우기·양쪽 지우기·공통 좌표로 합치기는 서로 다른 가중치와 정보 손실을 낳으므로 이번에는 아무 처리도 하지 않았다.", "",
        *_duplicate_table(redundancy), "", "[정확 일치·유사도와 차이](01_problem_tokens/redundancy_analysis.csv) · [거리 기여 그림](01_problem_tokens/figures/redundant_distance_contribution.png)", "",
        "## 6. 테스트에서 제외된 표현", "", *oov_lines, "",
        "기존 토큰화 함수를 읽기 전용으로 재사용하여 복원한 제외 목록과 원래 기록을 대조했다. 재토큰화는 기존 어휘를 다시 만들거나 벡터를 교체하는 작업이 아니다. 수학 기호·숫자처럼 문항의 조건에 영향을 줄 수 있는 표현은 TF가 적어도 의미를 따로 검토한다.", "",
        "## 7. Gemini에 실제 전달된 해설 토큰", "", *mix_lines, "",
        "이 비율은 실제 B·C 사용자 메시지의 힌트 좌표를 세어 구한 입력 구성이다. 고정 어휘 전체의 분포나 API 사용량을 대신하지 않는다. 전체 예측 벡터의 상위20과 최종 전송 토큰은 반올림·0생략을 거치므로 별도 표에 보존했다.", "", overlap_note, "",
        "관찰된 범주 편중은 특정 풀이 전략 정보가 얼마나 포함됐는지 검토할 근거다. 구성만으로 실제 힌트의 효과나 불용어 제거 후 성능을 확정할 수 없다. 풀이 방법을 나타내는 자연어가 적더라도 수학 명령·연산·변수의 조합이 일부 정보를 담을 수 있다.", "",
        "## 8. 특정 원본 해설을 정답 벡터로 쓴 한계", "", "확인된 사실은 회귀 목표가 문항마다 제공된 한 원본 해설의 토큰 빈도였다는 것이다. 수학 문제에 여러 올바른 풀이가 가능하다는 점을 고려하면 그 해설의 빈도와 다르다는 이유만으로 수학적으로 잘못된 풀이로 판단할 수 없다. 대안 풀이별 토큰 분포나 전략 전달 효과는 현재 자료로 검증하지 않은 후속 질문이다.", "",
        "## 9. 사용자 검토와 다음 단계", "", "문제·해설의 역할 분류는 설명용 휴리스틱이다. 표시는 불용어 확정이 아니며, 모호한 토큰은 ambiguity_note를 함께 읽는다. 토큰 제거 시 잃을 수 있는 정보도 각 all_tokens.csv에 남겼다.", "",
        "[문제 선택 파일](stopwords/problem_stopwords.json)과 [해설 선택 파일](stopwords/solution_stopwords.json)은 사용자용이며 최초에는 빈 배열이다. 프로그램이 토큰을 자동 추가하지 않는다. 문제와 해설의 목적이 다르므로 서로 독립적으로 선택한다.", "",
        "이번에 불용어를 선정하거나 삭제하지 않았고, 제거 벡터·K-means·회귀·신경망·Gemini·새 성능 지표·순열 검정 기능을 구현하거나 실행하지 않았다. 게시 후에는 사용자가 목록을 직접 정하고 후속 작업을 명시적으로 승인할 때까지 중단한다.", "",
        "## 10. 실행과 재현", "", "프로젝트 루트에서 다음 명령을 사용한다.", "",
        "```bash", "python -m mathhint_analysis.token_analysis analyze", "python -m mathhint_analysis.token_analysis report", "python -m mathhint_analysis.token_analysis verify", "```", "",
        "analyze는 기존 벡터·원문·저장 요청을 읽어 이 분석을 생성한다. report는 저장된 분석 CSV만으로 문서·그림을 다시 만들며 토큰화·학습·API를 실행하지 않는다. verify는 원본과 분석의 대응 및 보존 상태를 검사한다.", "",
        "[처음 읽을 요약](README.md) · [검증 기록](validation.json)"]
    _write(output / "token_analysis_report.md", report)
    source_counts = {region: Counter(r["source"] for r in rows) for region, rows in (("문제", problem), ("해설", solution))}
    readme = ["# MathHint 후속 연구 1단계 · 사용자의 토큰 검토 자료", "",
        "**토큰 분석만 완료했다. 불용어는 선정하지 않았고, 군집화 재실험·모델 학습·Gemini 호출은 수행하지 않았다.** 문제346·해설431개의 고정 어휘와 기존185/80 분할을 그대로 읽었다.", "",
        "## 먼저 확인할 주요 관찰", "", f"- 어휘 종류: 문제 Kiwi{source_counts['문제']['Kiwi']}·LaTeX{source_counts['문제']['LaTeX']}, 해설 Kiwi{source_counts['해설']['Kiwi']}·LaTeX{source_counts['해설']['LaTeX']}.",
        f"- 문제의 학습 분산 상위: {top_names}.",
        f"- 중괄호·좌우 표시·소괄호 6좌표의 학습 문항쌍 제곱거리 기여 합: **{_pct(pair_share)}**. 높은 기여는 수학적 중요도와 같지 않다.",
        "- " + evidence_contrast,
        "- 실제 분류와의 연관성 η²는 학습185에서 계산했다. 분산이 크거나 η²가 높다는 이유로 토큰을 자동 제거하지 않았다.", "",
        *eta_lines, "", "## 기존 Gemini B·C 상위토큰의 실제 구성", "", *mix_lines, "",
        "각 비율은 조건별80문항에 실제 전송된 좌표 수를 분모로 삼는다. 빈도 값 가중치나 API 사용량이 아니다. 특정 원본 해설과 토큰이 다르더라도 다른 올바른 풀이가 존재할 수 있다. ‘풀이 방법 자연어’의0은 현재 설명용 사전에 해당하는 명시적 자연어가 없다는 뜻이며, 수학 명령·연산의 단서나 실제 힌트 효과가0이라는 뜻은 아니다.", "",
        "## 학습 어휘 밖의 테스트 표현", "", *oov_lines, "",
        "제외 횟수가 적어도 수학적 조건을 담은 표현이 빠질 수 있다. [OOV의 실제 문자열과 의미](03_oov_analysis/README.md)를 확인한다. 어휘를 확장하지 않았다.", "",
        "## 읽는 순서", "", "|순서|바로 볼 자료|", "|---|---|",
        "|1 문제 표현의 통계|[문제 토큰 안내·그림](01_problem_tokens/README.md) · [전체346목록](01_problem_tokens/all_tokens.csv)|",
        "|2 분류 연관성과 중복성|[분산·η² 표](01_problem_tokens/variance_by_classification.csv) · [동일/유사 좌표](01_problem_tokens/redundancy_analysis.csv)|",
        "|3 해설 힌트의 구성|[해설 토큰·B/C 분석](02_solution_tokens/README.md) · [전체431목록](02_solution_tokens/all_tokens.csv)|",
        "|4 제외된 테스트 토큰|[문자열·횟수·손실 가능성](03_oov_analysis/README.md)|",
        "|5 전체 해석과 정의|[토큰화·분산 정의·한계 보고서](token_analysis_report.md) · [검증 기록](validation.json)|", "",
        "## 사용자가 직접 선택할 파일", "", "- [문제 불용어 선택용 빈 배열](stopwords/problem_stopwords.json)",
        "- [해설 불용어 선택용 빈 배열](stopwords/solution_stopwords.json)", "",
        "**두 목록은 프로그램이 자동으로 채우지 않는다.** 범주·분산·η²는 선택 근거이며 제거/유지의 확정 판정이 아니다. 사용자의 목록 확정과 명시적 요청 전에는 후속 단계를 구현하거나 실행하지 않는다.", "",
        "## 그림과 실행", "", "![분산 상위20](01_problem_tokens/figures/variance_top20.png)", "",
        "[분산과 η² 산점도](01_problem_tokens/figures/variance_eta_scatter.png) · [중복 거리 기여](01_problem_tokens/figures/redundant_distance_contribution.png) · [Kiwi/LaTeX 구성](01_problem_tokens/figures/source_distribution.png) · [B/C 범주 비교](02_solution_tokens/figures/top20_category_composition.png)", "",
        "문서는 GitHub에서 읽고 PNG 링크는 눌러 확대한다. CSV는 UTF-8 BOM으로 저장되어 Excel에서 한글을 읽을 수 있다. 원래 토큰의 kiwi:/latex: 접두사와 백슬래시를 그대로 표시한다.", "",
        "```bash", "python -m mathhint_analysis.token_analysis analyze  # 기존 자료로 통계 생성", "python -m mathhint_analysis.token_analysis report   # 저장 CSV로 문서·그림만 재생성", "python -m mathhint_analysis.token_analysis verify   # 분석·원본 보존 검증", "```", "",
        "기존 final_experiment는 불변 비교 근거로 보존했다. 이번에는 모델 성능 개선이 아니라 사용자 검토용 근거를 게시한 뒤 중단한다."]
    _write(output / "README.md", readme)
    figures = sorted(str(path.relative_to(output)) for path in output.rglob("*.png"))
    return {"problem_vocabulary_size": len(problem), "solution_vocabulary_size": len(solution),
            "known_pair_distance_contribution_ratio": pair_share, "actual_top20_mixture": mixture,
            "figure_count": len(figures), "figures": figures, "scope": "stage1_analysis_only"}
