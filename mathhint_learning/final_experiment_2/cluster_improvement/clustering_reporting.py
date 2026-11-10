"""전체265 군집 배정의 읽기 자료. 기존 교차표·혼동행렬·PCA 표시를 재사용한다."""

from collections import Counter, defaultdict
import csv
import math
from pathlib import Path

import numpy as np

from ...ClusterReport import (plot_final_composition, plot_final_cross_tabs,
                              setup_final_plots, cluster_problem_links)
from ...ClusteringConfusion import build_confusion_matrix, plot_confusion_matrix
from ...full_dataset_265.run import count_artifacts, reading_documents, save_pca
from ...holdout.run import LEVEL_NAMES, METHOD_NAMES, write_csv
from ...TorchData import write_json
from .clustering import CONDITIONS, full_matrix


def _read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def summary_row(result, feature_dim):
    return {"experiment": result["experiment"], "condition": result["condition"],
        "level": result["level"], "level_name": LEVEL_NAMES[result["level"]],
        "method": result["method"], "method_name": METHOD_NAMES[result["method"]],
        "scope": "all", "fit_scope": "all_265", "evaluation_scope": "same_all_documents",
        "k": result["k"], "feature_dim": feature_dim,
        **{key: value for key, value in result["metrics"].items() if key != "cluster_sizes"},
        "selected_seed": result["selected_seed"],
        "training_objective_name": result["training_objective_name"],
        "selected_training_objective": result["selected_training_objective"]}


def _comparison_figures(folder, summaries, old):
    plt = setup_final_plots()
    figures = folder / "figures"
    figures.mkdir(exist_ok=True)
    lookup = {(row["condition"], row["level"], row["method"]): row for row in summaries}
    for metric in ("ari", "ami", "nmi", "majority_accuracy", "macro_f1", "weighted_f1"):
        fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), constrained_layout=True)
        values = [row[metric] for row in summaries]
        for ax, method in zip(axes, METHOD_NAMES):
            for offset, condition, color in ((-.18, "K0", ".8"), (.18, "K1", ".3")):
                points = [lookup[condition, level, method][metric] for level in LEVEL_NAMES]
                bars = ax.bar(np.arange(4) + offset, points, .34, color=color, edgecolor="black",
                              linewidth=.5, label="K0 전체어휘 원시" if condition == "K0" else "K1 승인불용어 적용")
                ax.bar_label(bars, fmt="%.3f", padding=3, fontsize=8)
            if metric in ("ari", "nmi", "majority_accuracy"):
                historical = "full_majority_match_rate" if metric == "majority_accuracy" else metric
                points = [float(old[level, method][historical]) for level in LEVEL_NAMES]
                values += points
                ax.plot(np.arange(4), points, "--o", color=".45", linewidth=1, markersize=4,
                        label="기존 학습어휘 · 전체265")
            ax.set(xticks=range(4), xticklabels=list(LEVEL_NAMES.values()), ylabel=metric.upper(),
                   title=METHOD_NAMES[method])
            ax.set_ylim(min(0, min(values) - .04), min(1.16, max(values) + .16))
            ax.axhline(0, color=".7", linewidth=.5)
            ax.grid(axis="y", color=".9", linewidth=.5)
            ax.set_axisbelow(True)
        axes[0].legend(fontsize=8)
        title = "동일자료 대표 라벨 일치율" if metric == "majority_accuracy" else metric.upper()
        fig.suptitle(f"전체265 문제 BoW · {title}\n전체265로 군집과 대표 라벨을 정한 탐색 · 테스트 성능 아님")
        fig.savefig(figures / f"{metric}_comparison.png", dpi=200)
        plt.close(fig)


def _case_studies(root, folder, results):
    lines = ["# 군집이 모인 사례·혼합 사례·같은 유형의 분산", "",
        "동일265문항의 저장 배정으로 관찰할 사례를 선정했다. 이 사례는 전체 지표를 대신하지 않는다. "
        "수식 화면의 기존 A/B/C 응답은 과거 연구 기록이며 이번 연구의 생성 결과가 아니다.", ""]
    for result in results:
        if result["level"] != "type":
            continue
        documents = result["documents"]
        groups, actual_groups = defaultdict(list), defaultdict(list)
        for row in documents:
            groups[row["cluster"]].append(row)
            actual_groups[row["actual_label"]].append(row)

        def stats(rows):
            counts = Counter(row["actual_label"] for row in rows)
            return counts, max(counts.values()) / len(rows)

        eligible = [(cluster, rows) for cluster, rows in groups.items() if len(rows) >= 3] or list(groups.items())
        clean, clean_rows = max(eligible, key=lambda item: (stats(item[1])[1], len(item[1]), -item[0]))
        mixed, mixed_rows = max(groups.items(), key=lambda item: (len(stats(item[1])[0]), -stats(item[1])[1], len(item[1])))
        lines += [f"## {result['condition']} · {METHOD_NAMES[result['method']]} · 유형70", ""]
        for title, cluster, rows in (("실제 유형이 주로 모인 군집", clean, clean_rows),
                                      ("여러 실제 유형이 섞인 군집", mixed, mixed_rows)):
            counts, purity = stats(rows)
            lines += [f"### {title}: 군집{cluster}", "",
                f"{len(rows)}문항 · {len(counts)}개 실제유형 · 최빈 유형 비율 {purity:.1%}. "
                f"[해당 군집 전체](experiments/{result['experiment']}/clusters.md#cluster-{cluster})", "",
                "|실제 유형 전체 경로|문항 수|문항 수식·원문|", "|---|---:|---|"]
            for label, n in counts.most_common():
                links = ", ".join(cluster_problem_links(root, folder, folder, row["id"],
                    reader_path=Path(root) / "results/final_experiment/03_gemini/report.html")
                    for row in rows if row["actual_label"] == label)
                lines.append(f"|{label}|{n}|{links}|")
            lines.append("")
        split = [(label, rows) for label, rows in actual_groups.items() if len({row['cluster'] for row in rows}) > 1]
        lines += ["### 같은 실제 유형이 여러 군집에 나뉜 사례", ""]
        if split:
            label, rows = max(split, key=lambda item: (len({row["cluster"] for row in item[1]}), len(item[1]), item[0]))
            lines += [f"실제 유형: {label}", "", "|문항 수식·원문|배정 군집|", "|---|---:|"]
            for row in rows:
                link = cluster_problem_links(root, folder, folder, row["id"],
                    reader_path=Path(root) / "results/final_experiment/03_gemini/report.html")
                lines.append(f"|{link}|{row['cluster']}|")
        else:
            lines.append("해당 결과에서 같은 유형이 여러 군집으로 나뉜 사례는 없다.")
        lines.append("")
    (folder / "case_studies.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def render(root, output, data, results):
    """저장된 결과만 수치표·그림·원문 링크로 표현한다. fit/assign/model load 없음."""
    root, output = Path(root), Path(output)
    folder = output / "01_clustering"
    folder.mkdir(parents=True, exist_ok=True)
    summaries, all_members, all_distribution, all_dispersion, all_seeds, seed_summary = [], [], [], [], [], []
    matrices = {}
    old_path = root / "results/final_experiment/01_clustering/full_dataset_265/summary.csv"
    old = {(row["level"], row["method"]): row for row in _read_csv(old_path)}
    for result in results:
        target = folder / "experiments" / result["experiment"]
        target.mkdir(parents=True, exist_ok=True)
        (target / "figures").mkdir(exist_ok=True)
        documents = result["documents"]
        labels = sorted({row["actual_label"] for row in documents})
        counts, codes, distribution, dispersion = count_artifacts(target, documents, labels, result["k"])
        all_members.extend(documents)
        all_distribution.extend(distribution)
        all_dispersion.extend(dispersion)
        matrix = build_confusion_matrix([row["actual_label"] for row in documents],
                                        [row["full_majority_label"] for row in documents], labels)
        if int(matrix.sum()) != len(documents) or not math.isclose(
                float(np.trace(matrix)) / len(documents), result["metrics"]["majority_accuracy"], abs_tol=1e-12):
            raise ValueError(f"혼동행렬 합계/대각선이 저장 지표와 다릅니다: {target}")
        matrices[result["experiment"]] = (matrix, labels, codes)
        title = f"{result['condition']} · {LEVEL_NAMES[result['level']]} · {METHOD_NAMES[result['method']]} · "
        scopes = {"all": f"전체 {len(documents)}문항 · 동일자료 탐색"}
        plot_final_cross_tabs(target / "figures", {"all": counts}, labels, codes, result["k"],
                              scope_names=scopes, title_prefix=title)
        plot_final_composition(target / "figures", {"all": counts}, labels, codes, result["k"],
                               source_part="all", scope_names=scopes, title_prefix=title)
        reading_documents(root, folder, target, documents, labels, result["k"])
        listing = target / "clusters.md"
        listing.write_text(listing.read_text(encoding="utf-8").rstrip() + "\n", encoding="utf-8")
        feature_dim = len(data["variants"][CONDITIONS[result["condition"]]]["vocabularies"]["problems"])
        summaries.append(summary_row(result, feature_dim))
        for restart in result["restarts"]:
            all_seeds.append({"experiment": result["experiment"], "condition": result["condition"],
                "level": result["level"], "method": result["method"], "seed": restart["seed"],
                "selected": restart["seed"] == result["selected_seed"],
                "training_objective_name": result["training_objective_name"],
                "training_objective": restart["training_objective"], "iterations": restart["iterations"],
                **{key: value for key, value in restart["metrics"].items() if key != "cluster_sizes"}})
        for metric in ("ari", "ami", "nmi", "majority_accuracy", "macro_f1", "weighted_f1"):
            values = [restart["metrics"][metric] for restart in result["restarts"]]
            seed_summary.append({"experiment": result["experiment"], "condition": result["condition"],
                "level": result["level"], "method": result["method"], "metric": metric,
                "seed_count": len(values), "mean": float(np.mean(values)), "std_ddof0": float(np.std(values))})
    for result in results:
        target = folder / "experiments" / result["experiment"]
        matrix, labels, codes = matrices[result["experiment"]]
        code_list = [codes[label] for label in labels]
        same_level = [value[0] for name, value in matrices.items()
                      if next(r for r in results if r["experiment"] == name)["level"] == result["level"]]
        maximum = max(int(value.max()) for value in same_level)
        write_csv(target / "confusion_matrix_all.csv", [{"label_code": code_list[i], "actual_label": label,
            **{code: int(matrix[i, j]) for j, code in enumerate(code_list)}} for i, label in enumerate(labels)])
        plot_confusion_matrix(target / "figures/confusion_matrix_all.png", matrix, labels, code_list,
            experiment=result["experiment"], level=result["level"], method=result["method"],
            k=result["k"], scope="all", n=len(result["documents"]), vmax=maximum)
        # 기존 표시 함수의 문서에 이번 전처리 조건과 비교 가능한 축 범위를 덧붙인다.
        with (target / "README.md").open("a", encoding="utf-8") as stream:
            stream.write(f"\n## 이번 실험의 처리와 평가\n\n"
                f"{result['condition']}: {'전체265 어휘 원시 빈도' if result['condition'] == 'K0' else '승인된 문제 불용어만 제거한 원시 빈도'}. "
                f"활성 입력 {len(result['config']['vocabulary'])}차원, 전체265에서 중심과 대표 라벨을 정했다. "
                "원래185/80 분할은 문항 출처뿐이며 새 테스트 평가는 없다. "
                "혼동행렬의 행·열 라벨 순서와 색상 상한은 같은 분류수준의 K0/K1·유클리드/코사인 네 조건에 공통이다. "
                "Macro-F1은 실제 또는 대표 예측에 등장한 라벨 합집합, zero_division=0으로 계산했다.\n\n"
                "[모든 초기화 시드의 평가](../../seed_metrics.csv) · [시드 평균·표준편차](../../seed_summary.csv) · "
                "[군집화 종합 비교](../../README.md)\n")
    write_csv(folder / "summary.csv", summaries)
    write_csv(folder / "cluster_members.csv", all_members)
    write_csv(folder / "cluster_label_distribution.csv", all_distribution)
    write_csv(folder / "label_dispersion.csv", all_dispersion)
    write_csv(folder / "seed_metrics.csv", all_seeds)
    write_csv(folder / "seed_summary.csv", seed_summary)
    write_json(folder / "metrics.json", {"scope": "same_all_265_exploratory", "summaries": summaries,
        "experiments": [result["experiment"] for result in results],
        "note": "Same documents determine centers and majority labels; not test/generalization accuracy."})
    _comparison_figures(folder, summaries, old)
    _case_studies(root, folder, results)
    for condition, variant in CONDITIONS.items():
        ids, matrix, _ = full_matrix(data, variant)
        projection_folder = folder / "projections" / condition
        (projection_folder / "figures").mkdir(parents=True, exist_ok=True)
        original = {identifier: part for part, values in data["ids"].items() for identifier in values}
        save_pca(projection_folder, {"matrix": matrix, "full_ids": ids, "original_split": original},
                 [result for result in results if result["condition"] == condition])
    _index(folder, summaries, old)
    return summaries


def _index(folder, summaries, old):
    lookup = {(r["condition"], r["level"], r["method"]): r for r in summaries}
    lines = ["# 전체265 문제 BoW 군집화: K0 원시 / K1 사용자 불용어", "",
        "**전체265문항으로 중심과 대표 라벨을 정하고 같은265에서 구조를 관찰한 탐색 실험이다. "
        "새로운 문항의 일반화 또는 테스트 성능이 아니다. 기존185/80 소속은 출처 열에만 남겼다.**", "",
        "K0와 K1은 같은265 원문의 토큰화에서 출발한다. 공통 TorchKMeans 알고리즘·시드42~46의5회 초기화·"
        "최대100회·수렴1e-4를 유지했고 최저 학습 목적함수만으로 최종 시드를 골랐다. "
        "ARI/AMI/NMI를 보고 모델을 고르지 않았다.", "",
        "## 먼저 볼 비교", "",
        "|분류|거리|기존 전체265 ARI|K0 ARI|K1 ARI|K1−K0|K1 AMI|K1 NMI|K1 대표일치율|혼동행렬|",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---|"]
    for level in LEVEL_NAMES:
        for method in METHOD_NAMES:
            raw, filtered = lookup["K0", level, method], lookup["K1", level, method]
            lines.append(f"|{LEVEL_NAMES[level]}|{METHOD_NAMES[method]}|{float(old[level,method]['ari']):.4f}|"
                f"{raw['ari']:.4f}|{filtered['ari']:.4f}|{filtered['ari']-raw['ari']:+.4f}|"
                f"{filtered['ami']:.4f}|{filtered['nmi']:.4f}|{filtered['majority_accuracy']:.4f}|"
                f"[K0](experiments/{raw['experiment']}/figures/confusion_matrix_all.png) · "
                f"[K1](experiments/{filtered['experiment']}/figures/confusion_matrix_all.png)|")
    lines += ["", "기존 수치는 학습185 어휘를 유지해 전체265를 군집화했던 보존 실험이다. "
        "기존→K0는 어휘 범위 차이를, K0→K1은 같은 전체어휘 조건에서 승인 불용어 적용 차이를 살핀다. "
        "K1과 기존 결과의 차이를 불용어만의 효과로 해석하지 않는다.", "",
        "[전체 지표16행](summary.csv) · [실제 문항 배정4240행](cluster_members.csv) · "
        "[시드별80회 결과](seed_metrics.csv) · [시드 평균·표준편차](seed_summary.csv) · "
        "[모인·혼합·분산 사례](case_studies.md)", "",
        "## 지표와 그림", "",
        "ARI·AMI·NMI는 임의 군집번호와 실제 계층 분류의 일치도다. "
        "대표 일치율/F1은 각 군집의 최빈 실제라벨로 바꾼 동일자료 설명용 수치다. "
        "최빈 동률은 전체 계층 경로 문자열 순서로 결정한다. 서로 다른 군집이 같은 대표라벨이면 "
        "혼동행렬의 같은 열로 합산한다. 두 축은 같은 라벨 순서라 대각선이 일치 문항 수다.", "",
        "|읽을 지표|그림|", "|---|---|"]
    lines += [f"|{metric.upper()}|[열기](figures/{metric}_comparison.png)|"
              for metric in ("ari", "ami", "nmi", "majority_accuracy", "macro_f1", "weighted_f1")]
    lines += ["", "## 16개 실험의 군집과 원문", "",
        "각 실험에는 전체 문항·실제 계층 분류·원래 분할·군집·대표라벨, 교차표/혼동행렬의 CSV/PNG와 "
        "라벨 코드 대응표가 있다. 큰 교차표는20라벨씩, 구성비는25군집씩 분할했다. "
        "유형70 혼동행렬은 고해상도이며 라벨 코드는 바로 옆 대응표로 확인한다.", "",
        "|조건|분류|거리|군집·원문·모델·설정|혼동행렬 CSV|라벨 코드|", "|---|---|---|---|---|---|"]
    for row in summaries:
        path = f"experiments/{row['experiment']}"
        lines.append(f"|{row['condition']}|{LEVEL_NAMES[row['level']]}|{METHOD_NAMES[row['method']]}|"
                     f"[실험 안내]({path}/README.md) · [군집 목록]({path}/clusters.md)|"
                     f"[CSV]({path}/confusion_matrix_all.csv)|[전체 경로]({path}/label_key.csv)|")
    lines += ["", "## PCA는 표시용", "",
        "원시 또는 L2 정규화된 전체265 입력에 각각 PCA를 맞췄다. 실제 군집화는 축소 전의 BoW 전체 활성차원에서 수행했다. "
        "서로 다른 표현의 PCA 좌표 축을 직접 비교하지 않는다.", "",
        "|조건|과목 유클리드|과목 코사인|단원 유클리드|단원 코사인|", "|---|---|---|---|---|"]
    for condition in CONDITIONS:
        paths = [f"[열기](projections/{condition}/figures/pca_{level}_{method}.png)"
                 for level in ("curriculum", "unit") for method in METHOD_NAMES]
        lines.append(f"|{condition}|" + "|".join(paths) + "|")
    lines += ["", "[이번 연구 시작점](../README.md)", ""]
    (folder / "README.md").write_text("\n".join(lines), encoding="utf-8")
