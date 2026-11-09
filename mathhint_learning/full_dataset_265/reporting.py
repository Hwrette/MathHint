"""전체 265문항 탐색 실험의 저장 결과를 비교표·그림·문항 사례로 읽는다.

모델 학습과 배정은 실행기의 역할이다. 이 모듈은 전달된 최종 배정과
기존 분리 실험의 저장 CSV만 사용하며 회귀·Gemini를 실행하지 않는다.
"""

from collections import Counter, defaultdict
import csv
import math
import os
from pathlib import Path

from ..ClusterReport import setup_final_plots
from ..FinalClustering import LEVEL_NAMES, METHOD_NAMES, write_csv


LEVELS = tuple(LEVEL_NAMES)
METHODS = tuple(METHOD_NAMES)


def _csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _number(value):
    return f"{float(value):.6f}"


def _question_link(root, output, identifier):
    viewer = Path(root) / "results/final_experiment/03_gemini/report.html"
    return f"[{identifier}]({Path(os.path.relpath(viewer, output)).as_posix()}#{identifier})"


def _comparison_table(rows):
    lines = ["|분류 수준|거리 방식|기존 테스트 80 ARI|전체 265 ARI|기존 테스트 80 NMI|전체 265 NMI|",
             "|---|---|---:|---:|---:|---:|"]
    for row in rows:
        lines.append(f"|{LEVEL_NAMES[row['level']]}|{METHOD_NAMES[row['method']]}|"
                     f"{_number(row['holdout_test_ari'])}|{_number(row['full_265_ari'])}|"
                     f"{_number(row['holdout_test_nmi'])}|{_number(row['full_265_nmi'])}|")
    return lines


def _summary_figures(output, summaries, comparisons):
    plt = setup_final_plots()
    folder = output / "figures"
    folder.mkdir(exist_ok=True)
    index = {(row["level"], row["method"]): row for row in summaries}
    comparison_index = {(row["level"], row["method"]): row for row in comparisons}
    names = [LEVEL_NAMES[level] for level in LEVELS]
    for metric in ("ari", "nmi"):
        fig, ax = plt.subplots(figsize=(10, 5))
        for offset, method, color in ((-.19, "euclidean", ".75"), (.19, "spherical", ".3")):
            values = [float(index[level, method][metric]) for level in LEVELS]
            bars = ax.bar([i + offset for i in range(len(LEVELS))], values, .36,
                          color=color, edgecolor="black", linewidth=.6, label=METHOD_NAMES[method])
            ax.bar_label(bars, fmt="%.3f", padding=3, fontsize=9)
        values = [float(row[metric]) for row in summaries]
        ax.set(xticks=range(len(names)), xticklabels=names, ylabel=metric.upper(),
               title=f"전체 265문항 탐색 · {metric.upper()} · 학습한 동일 265문항에서 평가")
        ax.set_ylim(min(0, min(values) - .03), max(values) * 1.24 + .03)
        ax.legend()
        ax.grid(axis="y", color=".9", linewidth=.5)
        ax.set_axisbelow(True)
        fig.tight_layout()
        fig.savefig(folder / f"{metric}_comparison_full.png", dpi=220, bbox_inches="tight")
        plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    specifications = [(-.30, "euclidean", "holdout_test", ".82", "//", "유클리드 · 기존 테스트80"),
                      (-.10, "euclidean", "full_265", ".65", None, "유클리드 · 전체265 동일자료"),
                      (.10, "spherical", "holdout_test", ".45", "//", "코사인 · 기존 테스트80"),
                      (.30, "spherical", "full_265", ".2", None, "코사인 · 전체265 동일자료")]
    for ax, metric in zip(axes, ("ari", "nmi")):
        all_values = []
        for offset, method, source, color, hatch, label in specifications:
            values = [float(comparison_index[level, method][source + "_" + metric]) for level in LEVELS]
            all_values += values
            bars = ax.bar([i + offset for i in range(len(LEVELS))], values, .19,
                          color=color, edgecolor="black", linewidth=.5, hatch=hatch, label=label)
            ax.bar_label(bars, fmt="%.3f", padding=2, fontsize=7, rotation=90)
        ax.set(xticks=range(len(names)), xticklabels=names, ylabel=metric.upper(), title=metric.upper())
        ax.set_ylim(min(0, min(all_values) - .03), max(all_values) * 1.3 + .04)
        ax.grid(axis="y", color=".9", linewidth=.5)
        ax.set_axisbelow(True)
    axes[0].legend(loc="upper left", fontsize=8)
    fig.suptitle("평가 범위 비교: 185문항 학습→테스트80 vs 전체265 학습→동일265 관찰\n"
                 "서로 다른 연구 질문이며, 점수 차이를 일반화 성능 향상으로 해석하지 않음", fontsize=12)
    fig.tight_layout()
    fig.savefig(folder / "comparison_with_holdout.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def _type_case_sections(root, output, members):
    """실제 유형을 대상으로 순도·혼합·분산의 관찰 근거와 ID를 고른다."""
    sections = []
    for method in METHODS:
        documents = [row for row in members if row["level"] == "type" and row["method"] == method]
        groups, labels = defaultdict(list), defaultdict(list)
        for row in documents:
            groups[int(row["cluster"])].append(row)
            labels[row["actual_label"]].append(row)

        def group_stats(rows):
            counts = Counter(row["actual_label"] for row in rows)
            majority = sorted(counts, key=lambda label: (-counts[label], label))[0]
            return counts, majority, counts[majority] / len(rows)

        candidates = [(cluster, rows) for cluster, rows in groups.items() if len(rows) >= 3]
        if not candidates:
            candidates = list(groups.items())
        good_cluster, good = max(candidates,
                                 key=lambda item: (group_stats(item[1])[2], len(item[1]), -item[0]))
        mixed_cluster, mixed = max(groups.items(), key=lambda item: (
            len(group_stats(item[1])[0]), -group_stats(item[1])[2], len(item[1]), -item[0]))
        split_candidates = [(label, rows) for label, rows in labels.items()
                            if len({row["cluster"] for row in rows}) >= 2]

        sections += ["", f"### {METHOD_NAMES[method]} · 문제 유형 k=70", "",
                     "아래 선정은 저장된 문항 배정의 수적 특징에 따른 관찰용 사례다. "
                     "순도가 높다는 사실이 풀이 방식까지 동일하다는 뜻은 아니므로 링크의 원문을 직접 비교한다.", ""]
        for name, cluster, rows in (("A. 실제 유형이 비교적 잘 모인 군집", good_cluster, good),
                                    ("B. 서로 다른 유형이 섞인 군집", mixed_cluster, mixed)):
            counts, majority, purity = group_stats(rows)
            sections += [f"**{name}: 군집 {cluster}, {len(rows)}문항, {len(counts)}개 유형**", "",
                         f"최빈 유형 비율은 {counts[majority]}/{len(rows)}={purity:.1%}다. "
                         f"[이 실험의 전체 군집 목록](experiments/type_{method}/clusters.md#cluster-{cluster})에서 모든 문항을 확인한다.", "",
                         "|실제 유형의 전체 경로|빈도|비율|해당 문항 읽기|", "|---|---:|---:|---|"]
            for label, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
                ids = [row["id"] for row in rows if row["actual_label"] == label]
                links = ", ".join(_question_link(root, output, identifier) for identifier in ids)
                sections.append(f"|{label}|{count}|{count / len(rows):.1%}|{links}|")
            sections.append("")
        sections += ["**C. 같은 실제 유형이 여러 군집으로 나뉜 사례**", ""]
        if split_candidates:
            def dispersion_key(item):
                counts = Counter(row["cluster"] for row in item[1])
                proportions = [n / len(item[1]) for n in counts.values()]
                entropy = -sum(p * math.log2(p) for p in proportions)
                return len(counts), len(item[1]), entropy, item[0]
            label, rows = max(split_candidates, key=dispersion_key)
            counts = Counter(row["cluster"] for row in rows)
            sections += [f"실제 유형 **{label}**의 {len(rows)}문항이 {len(counts)}개 군집으로 나뉘었다.", "",
                         "|군집|문항 수|해당 문항 읽기|", "|---|---:|---|"]
            for cluster, count in sorted(counts.items(), key=lambda item: int(item[0])):
                links = ", ".join(_question_link(root, output, row["id"]) for row in rows if row["cluster"] == cluster)
                sections.append(f"|{cluster}|{count}|{links}|")
            sections += ["", "분산은 유형과 BoW 군집의 차이를 보여 주지만, 이를 잘못된 군집이라고 확정하지 않는다. "
                         "표현 길이·문자/수식 빈도·동일 유형 내 조건 차이는 원문을 읽고 검토할 가설이다.", ""]
        else:
            sections += ["이 배정에서는 한 유형이 두 군집 이상에 걸친 사례가 없다.", ""]
    return sections


def report_results(root, output, summaries, members, dispersion):
    """최종 8개 실험을 읽기 위한 요약을 새 탐색 실험 폴더에만 저장한다."""
    root, output = Path(root), Path(output)
    expected = {(level, method) for level in LEVELS for method in METHODS}
    index = {(row["level"], row["method"]): row for row in summaries}
    if len(summaries) != 8 or set(index) != expected:
        raise ValueError("전체 데이터 탐색 보고서에는 4개 분류 × 2개 거리의 고유 결과 8개가 필요합니다.")
    for key in expected:
        documents = [row for row in members if (row["level"], row["method"]) == key]
        if len(documents) != 265 or len({row["id"] for row in documents}) != 265:
            raise ValueError(f"{key}: 보고서 문항은 중복 없이 265개여야 합니다.")
    holdout_path = output.parent / "summary.csv"
    holdout = {(row["level"], row["method"]): row for row in _csv(holdout_path) if row["split"] == "test"}
    if set(holdout) != expected or any(int(row["n"]) != 80 for row in holdout.values()):
        raise ValueError(f"{holdout_path}: 기존 8개 실험의 테스트 80문항 평가를 확인할 수 없습니다.")
    comparisons = []
    for level in LEVELS:
        for method in METHODS:
            previous, current = holdout[level, method], index[level, method]
            comparisons.append({"experiment": current["experiment"], "level": level, "method": method,
                                "k": current["k"], "holdout_training_count": 185, "holdout_test_n": 80,
                                "full_fit_and_evaluation_n": 265, "holdout_test_ari": float(previous["ari"]),
                                "full_265_ari": float(current["ari"]), "holdout_test_nmi": float(previous["nmi"]),
                                "full_265_nmi": float(current["nmi"]),
                                "interpretation": "different evaluation scopes; no generalization improvement claim"})
    write_csv(output / "comparison_with_holdout.csv", comparisons)
    _summary_figures(output, summaries, comparisons)

    warning = ("**실험 A(기존 분리)**는 185문항으로 중심과 대표 라벨을 정하고 별도 테스트 80문항을 평가했다. "
               "**실험 B(이 폴더)**는 전체 265문항으로 중심과 대표 라벨을 정하고 같은 265문항을 관찰한다. "
               "따라서 B의 점수가 높더라도 새로운 문제에 대한 일반화 성능이 개선됐다는 뜻이 아니다.")
    reader = Path(os.path.relpath(root / "results/final_experiment/03_gemini/report.html", output)).as_posix()
    readme = ["# 전체 265문항 K-means · 탐색 실험 B", "", warning, "",
              "## 확인 순서", "",
              "1. [ARI·NMI 요약](summary.csv)와 [기존 테스트 비교표](comparison_with_holdout.csv)를 본다.",
              "2. 아래 표에서 분류 수준·거리 방식의 군집별 실제 문제를 연다.",
              "3. [혼합·동일 유형 분산 사례](analysis.md#문항을-직접-읽는-관찰-사례)를 원문과 비교한다.",
              "4. 각 실험 안내에서 교차표·혼동행렬·구성비·PCA를 확인한다.", "",
              f"문항 ID 링크는 기존 [수식 읽기 화면]({reader})의 해당 문제로 이동한다. "
              "화면에 표시되는 학습/테스트와 A/B/C는 기존 연구의 출처 정보이며, 이 군집화의 학습 구분이 아니다. 추가 Gemini 호출은 없다.", "",
              "## 핵심 수치 · 평가 범위를 구분해서 읽기", "", *_comparison_table(comparisons), "",
              "ARI는 우연 일치를 보정한 군집/실제 분류의 일치도, NMI는 두 분류의 정보 공유 정도다. "
              "군집 번호는 임의 번호이며 실제 유형 번호처럼 비교하지 않는다. "
              "전체 자료의 군집 최빈 라벨 일치율은 `summary.csv`의 `full_majority_match_rate`이며 동일 자료에서 계산한 설명용 보조 지표다.", "",
              "[전체265 ARI 그림](figures/ari_comparison_full.png) · [전체265 NMI 그림](figures/nmi_comparison_full.png) · "
              "[기존 테스트/전체자료 범위 비교 그림](figures/comparison_with_holdout.png)", "",
              "## 8개 실험 · 문제 목록과 그림", "",
              "|분류 수준 · k|유클리드|코사인(구면)|", "|---|---|---|"]
    for level in LEVELS:
        k = index[level, "euclidean"]["k"]
        cells = []
        for method in METHODS:
            path = f"experiments/{level}_{method}"
            cells.append(f"[안내·그림]({path}/README.md) · [군집별 문제]({path}/clusters.md) · "
                         f"[혼동행렬]({path}/figures/confusion_matrix_all.png)")
        readme.append(f"|{LEVEL_NAMES[level]} · {k}|{cells[0]}|{cells[1]}|")
    readme += ["", "## 원자료와 계산 기준", "",
               "- [전체 문항 배정](cluster_members.csv): 기존 출처 분할은 `original_split`로 보존한다.",
               "- [군집별 실제 라벨 빈도·비율](cluster_label_distribution.csv) · [실제 분류의 군집 분산](label_dispersion.csv)",
               "- [실험 설정·입력 해시](config.json): 고정 346차원 어휘, 42~46 시드, 재시작 5회, 최대 100회, 기존 수렴 기준.",
               "- 각 실험의 `model.pt`, `experiment.json`에 최적 학습 목적함수·중심·배정·선택 시드와 재현 근거를 남긴다.", "",
               "교차표 히트맵은 **실제 분류 × 군집 번호**를 보여 준다. 혼동행렬은 전체 265문항의 군집별 최빈 라벨을 "
               "예측 분류로 대응한 **실제 분류 × 대응 분류**다. 후자는 같은 자료로 대표 라벨을 만들고 평가한 설명용이며 테스트 정확도가 아니다.", "",
               "## PCA · 표시용 2차원 투영", "",
               "|표시 분류|유클리드 원시 빈도 공간|코사인 L2 정규화 공간|", "|---|---|---|",
               "|과목|[실제 분류·군집 PCA](figures/pca_curriculum_euclidean.png)|[실제 분류·군집 PCA](figures/pca_curriculum_spherical.png)|",
               "|단원|[실제 분류·군집 PCA](figures/pca_unit_euclidean.png)|[실제 분류·군집 PCA](figures/pca_unit_spherical.png)|", "",
               "PCA는 전체 265문항에서 맞춘 2차원 표시용 투영이다. K-means 자체는 고정된 346차원 입력에서 학습했다. "
               "원시 빈도와 L2 정규화 표현의 PCA는 각각의 표시 공간이며 좌표를 직접 비교하지 않는다.", "",
               "기존 모델·배정·지표·원본 데이터·어휘·회귀·Gemini 결과는 이 탐색 실험에서 변경하지 않는다.", "",
               "## 실행과 재사용", "",
               "프로젝트 루트에서 `python -m mathhint_learning.full_dataset_265`를 실행한다. "
               "이 탐색 폴더에만 결과를 저장하며, 같은 입력·설정의 완료 산출물이 있으면 파일 해시를 검증하고 재학습 없이 반환한다. "
               "알고리즘은 기존 `TorchKMeans.py`를 공통으로 사용하고 이 실험의 데이터 결합·평가·저장 절차만 별도 패키지에 둔다. "
               "Gemini 호출과 회귀 학습은 포함하지 않는다."]
    (output / "README.md").write_text("\n".join(readme) + "\n", encoding="utf-8")

    analysis = ["# 전체 265문항 탐색 결과와 직접 관찰", "", warning, "",
                "## 실험 방법", "",
                "기존 학습185·테스트80의 문제 BoW 행을 ID에 맞춰 합쳐 265×346 행렬로 사용했다. "
                "새 토큰화·어휘 재학습은 없으며 실제 분류 라벨은 중심 갱신에 넣지 않았다. "
                "고유 계층 경로 수로 k=2·8·25·70을 확인했다. "
                "기존 알고리즘과 동일하게 시드42~46의 5개 실행 중 유클리드는 거리 제곱합, 구면 방식은 1−코사인 합이 최소인 실행을 골랐다. "
                "ARI·NMI로 초기화를 선택하지 않았다.", "",
                "## 저장 결과에서 확인한 수치", "", *_comparison_table(comparisons), ""]
    for metric in ("ari", "nmi"):
        differences = [float(index[level, "spherical"][metric]) - float(index[level, "euclidean"][metric]) for level in LEVELS]
        higher = [LEVEL_NAMES[level] for level, difference in zip(LEVELS, differences) if difference > 0]
        equal = [LEVEL_NAMES[level] for level, difference in zip(LEVELS, differences) if difference == 0]
        lower = [LEVEL_NAMES[level] for level, difference in zip(LEVELS, differences) if difference < 0]
        analysis.append(f"- 관찰: 전체265 {metric.upper()}에서 코사인 방식이 유클리드보다 높은 수준은 "
                        f"{', '.join(higher) or '없음'}, 같은 수준은 {', '.join(equal) or '없음'}, 낮은 수준은 {', '.join(lower) or '없음'}이다.")
    analysis += ["", "관찰과 해석을 구분한다. 코사인 방식의 차이가 문항 길이의 영향 감소 때문일 수 있다는 설명은 가설이며, "
                 "이번 두 거리 비교만으로 원인을 확정하지 않는다. 고정 어휘가 원래185문항에서 정해졌으므로 전체265 실험도 "
                 "전체 자료에서 새로 어휘를 맞춘 실험과는 다르다.", "",
                 "[ARI·NMI와 평가 범위 그림](figures/comparison_with_holdout.png)", "",
                 "## 문항을 직접 읽는 관찰 사례", "",
                 "다음 사례의 모든 ID는 실제 저장 배정에 속한다. 전체 목록·정확한 계층 분류명은 각 실험의 `members.csv`, "
                 "`clusters.md`, `label_key.csv`에서 확인할 수 있다."]
    analysis += _type_case_sections(root, output, members)
    analysis += ["## 해석의 한계", "",
                 "- 현재265개를 한꺼번에 학습·평가한 탐색이다. 기존 테스트80 결과와 동일한 일반화 평가가 아니다.",
                 "- 유형70개에 비해 전체265문항으로 유형별 사례 수가 적다. 단일 문항 군집은 높은 순도를 쉽게 보이므로 사례 선정에는 우선3문항 이상인 군집을 사용했다.",
                 "- 시드5개는 초기화 변동을 줄이는 장치이며 독립 데이터 반복 실험5회라는 뜻은 아니다. 최적화 목적함수의 값은 서로 다른 거리 간 직접 비교하지 않는다.",
                 "- BoW는 토큰 순서·수식 구조를 보존하지 않는다. 빈도와 문항 길이·표기 방식이 실제 교육과정 분류와 다른 군집을 만들 수 있지만 추가 검증 없이 인과를 확정하지 않는다.",
                 "- 군집 최빈 라벨 기반 동일자료 일치율·혼동행렬은 설명용이다. 대표 라벨을 평가 자료에서 계산한 만큼 테스트 정확도라는 표현을 사용하지 않는다.", "",
                 "추가 불용어·TF-IDF·신경망·회귀 변경·Gemini 재실험은 수행하지 않았다. 이 결과를 직접 검토한 뒤 다음 개선을 별도로 결정한다."]
    (output / "analysis.md").write_text("\n".join(analysis) + "\n", encoding="utf-8")
    return comparisons
