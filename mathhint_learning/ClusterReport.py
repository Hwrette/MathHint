"""군집별 문항 목록과 실제 소단원 분포를 표·문서·그림으로 저장한다."""

from collections import Counter
import csv
import json
import os
from pathlib import Path


def save_cluster_reports(root, output, documents, n_clusters):
    output = Path(output)
    folder = output / "clusters"
    folder.mkdir(parents=True, exist_ok=True)
    summaries = []
    labels = sorted({row["actual_labels"]["subunit"] for row in documents})
    counts = {part: [[0] * n_clusters for _ in labels] for part in ("train", "test")}
    label_index = {label: i for i, label in enumerate(labels)}
    for row in documents:
        counts[row["split"]][label_index[row["actual_labels"]["subunit"]]][row["cluster"]] += 1

    for cluster in range(n_clusters):
        members = [row for row in documents if row["cluster"] == cluster]
        groups = {part: [row for row in members if row["split"] == part] for part in ("train", "test")}
        distribution = {part: Counter(row["actual_labels"]["subunit"] for row in rows) for part, rows in groups.items()}
        majority = members[0]["train_majority_predicted_labels"]["subunit"] if members else None
        summaries.append({"cluster": cluster, "train_count": len(groups["train"]), "test_count": len(groups["test"]),
                          "train_majority_subunit": majority,
                          "train_ids": [row["id"] for row in groups["train"]],
                          "test_ids": [row["id"] for row in groups["test"]],
                          "subunit_distribution": distribution})
        lines = [f"# 군집 {cluster:02d}", "", f"학습 {len(groups['train'])}문항 · 테스트 {len(groups['test'])}문항", "",
                 "학습 다수 소단원: " + (majority or "학습 문항 없음"), "",
                 "군집 번호는 임의 번호이며 소단원 번호가 아니다. 다수 라벨은 학습에서만 정했다.", ""]
        for part, title in [("train", "학습"), ("test", "테스트")]:
            lines += [f"## {title} 소단원 구성", "", "| 소단원 | 문항 수 |", "|---|---:|"]
            lines += [f"| {label} | {count} |" for label, count in distribution[part].most_common()]
            lines += ["", f"## {title} 문항", ""]
            if not groups[part]:
                lines += ["문항 없음", ""]
            for row in groups[part]:
                problem = Path(root) / "data/processed/problems" / f"{row['id']}.txt"
                lines += [f"### {row['id']}", "", "- 소단원: " + row["actual_labels"]["subunit"],
                          "- 유형: " + row["type"], "- 출처: " + row["source"],
                          f"- 원래 번호: {row['original_number']} / 현재 번호: {row['current_number']}", "",
                          problem.read_text(encoding="utf-8-sig") if problem.exists() else "문제 본문 파일 없음", ""]
        (folder / f"cluster_{cluster:02d}.md").write_text("\n".join(lines), encoding="utf-8")

    (output / "cluster_groups.json").write_text(json.dumps({"n_clusters": n_clusters, "clusters": summaries}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (output / "cluster_summary.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["cluster", "train_count", "test_count", "train_majority_subunit", "train_subunits", "test_subunits"])
        for row in summaries:
            writer.writerow([row[key] for key in ("cluster", "train_count", "test_count", "train_majority_subunit")] +
                            [json.dumps(row["subunit_distribution"][part], ensure_ascii=False) for part in ("train", "test")])
    with (output / "cluster_assignments.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        fields = ["id", "split", "cluster", "curriculum", "unit", "subunit", "type", "source", "source_file", "original_number", "current_number"]
        writer = csv.writer(stream)
        writer.writerow(fields + ["train_majority_subunit", "subunit_matches_train_majority"])
        for row in documents:
            predicted = row["train_majority_predicted_labels"]["subunit"]
            writer.writerow([row[key] for key in fields] + [predicted, predicted == row["actual_labels"]["subunit"]])
    with (output / "subunit_cluster_counts.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["split", "subunit"] + [f"cluster_{i:02d}" for i in range(n_clusters)])
        for part in ("train", "test"):
            writer.writerows([part, label, *counts[part][i]] for i, label in enumerate(labels))
    lines = ["# 실제 소단원 수를 사용한 군집화", "",
             f"군집 {n_clusters}개. 학습 {sum(row['split'] == 'train' for row in documents)}문항 / 테스트 {sum(row['split'] == 'test' for row in documents)}문항.", "",
             "소단원은 과목·단원·소단원의 전체 경로로 구분했다. 학습에서 만든 중심과 다수 라벨만 테스트에 적용했다.", "",
             "[일치도 수치](clustering_metrics.json) · [문항별 배정 CSV](cluster_assignments.csv) · [소단원 분포 그림](subunit_cluster_heatmap.png)", "",
             "| 군집 | 학습 | 테스트 | 학습 다수 소단원 | 문항 목록 |", "|---:|---:|---:|---|---|"]
    for row in summaries:
        lines.append(f"| {row['cluster']} | {row['train_count']} | {row['test_count']} | {row['train_majority_subunit'] or '학습 문항 없음'} | [보기](clusters/cluster_{row['cluster']:02d}.md) |")
    (output / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    plot_subunits(output, labels, counts, n_clusters)


def plot_subunits(output, labels, counts, n_clusters):
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/mathhint-clustering-mpl")
    os.environ.setdefault("XDG_CACHE_HOME", "/tmp/mathhint-clustering-cache")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    font_path = Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
    if font_path.exists():
        font_manager.fontManager.addfont(str(font_path))
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=str(font_path)).get_name()
    fig, axes = plt.subplots(1, 2, figsize=(19, max(7, .32 * len(labels))), constrained_layout=True)
    maximum = max(value for matrix in counts.values() for row in matrix for value in row) or 1
    for ax, part, title in zip(axes, ("train", "test"), ("학습", "테스트")):
        image = ax.imshow(counts[part], cmap="Greys", vmin=0, vmax=maximum, aspect="auto")
        ax.set_title(f"{title} 실제 소단원 × 군집 (k={n_clusters})")
        ax.set_xticks(range(n_clusters), [str(i) for i in range(n_clusters)], fontsize=7)
        ax.set_yticks(range(len(labels)), labels, fontsize=7)
        ax.set_xlabel("군집 번호")
        for row, values in enumerate(counts[part]):
            for column, count in enumerate(values):
                if count:
                    ax.text(column, row, str(count), ha="center", va="center", fontsize=7,
                            color="white" if count > maximum / 2 else "black")
    fig.colorbar(image, ax=axes, label="문항 수", shrink=.7)
    for suffix in ("png", "pdf"):
        fig.savefig(Path(output) / f"subunit_cluster_heatmap.{suffix}", dpi=160)
    plt.close(fig)


def setup_final_plots():
    """외부 서비스 없이 저장 가능한 한글 그래프 설정."""
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/mathhint-clustering-mpl")
    os.environ.setdefault("XDG_CACHE_HOME", "/tmp/mathhint-clustering-cache")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    font_path = Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
    if font_path.exists():
        font_manager.fontManager.addfont(str(font_path))
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=str(font_path)).get_name()
    plt.rcParams.update({"axes.unicode_minus": False, "axes.spines.top": False,
                         "axes.spines.right": False, "figure.dpi": 160, "font.size": 9})
    return plt


def save_final_cluster_reports(root, output, target, documents, n_clusters, labels):
    """현재 분류 단계의 문항 목록·빈도/비율·라벨 분산도·교차표를 저장한다."""
    import math
    import numpy as np
    from .FinalClustering import write_csv
    target = Path(target)
    figures = target / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    label_codes = {label: f"L{i + 1:02d}" for i, label in enumerate(labels)}
    write_csv(target / "members.csv", documents)
    write_csv(target / "label_key.csv", [{"label_code": label_codes[label], "actual_label": label} for label in labels])
    counts = {part: np.zeros((len(labels), n_clusters), dtype=int) for part in ("train", "test")}
    label_index = {label: i for i, label in enumerate(labels)}
    for row in documents:
        counts[row["split"]][label_index[row["actual_label"]], row["cluster"]] += 1
    groups, distribution, dispersion = [], [], []
    cluster_lines = ["# 군집별 실제 문항", "", "문항 ID 링크는 문제 본문을 연다. 대표 라벨은 학습에서만 정했으며, 군집 번호는 임의 번호다.", ""]
    base = os.path.relpath(root, target).replace(os.sep, "/")
    for cluster in range(n_clusters):
        members = [row for row in documents if row["cluster"] == cluster]
        by_part = {part: [r for r in members if r["split"] == part] for part in counts}
        training_majority = next((row["train_majority_label"] for row in members), None)
        groups.append({"cluster": cluster, "train_count": len(by_part["train"]), "test_count": len(by_part["test"]),
                       "train_majority_label": training_majority,
                       "train_ids": ",".join(row["id"] for row in by_part["train"]),
                       "test_ids": ",".join(row["id"] for row in by_part["test"])})
        cluster_lines += [f"## 군집 {cluster:02d}", "", f"학습 {len(by_part['train'])}문항 · 테스트 {len(by_part['test'])}문항 · 학습 다수 라벨: {training_majority or '없음'}", "",
                          "| 구분 | 문항 ID / 문제 | 실제 과목 | 단원 | 세부단원 | 유형 |", "|---|---|---|---|---|---|"]
        for part in counts:
            frequencies = Counter(row["actual_label"] for row in by_part[part])
            for label, count in frequencies.most_common():
                distribution.append({"experiment": documents[0]["experiment"], "level": documents[0]["level"], "method": documents[0]["method"],
                                     "split": part, "cluster": cluster, "actual_label": label, "label_code": label_codes[label],
                                     "count": count, "cluster_n": len(by_part[part]), "ratio": count / len(by_part[part]),
                                     "train_majority_label": training_majority})
            for row in by_part[part]:
                cluster_lines.append(f"| {'학습' if part == 'train' else '테스트'} | [{row['id']}]({base}/{row['problem_path']}) | {row['curriculum']} | {row['unit']} | {row['subunit']} | {row['type']} |")
        if not members:
            cluster_lines.append("| - | 문항 없음 | | | | |")
        cluster_lines.append("")
    for part, matrix in counts.items():
        write_csv(target / f"cross_tab_{part}.csv", [
            {"label_code": label_codes[label], "actual_label": label, **{f"cluster_{c:02d}": int(matrix[i, c]) for c in range(n_clusters)}}
            for i, label in enumerate(labels)])
        for i, label in enumerate(labels):
            n = int(matrix[i].sum())
            proportions = [int(x) / n for x in matrix[i] if x] if n else []
            dispersion.append({"experiment": documents[0]["experiment"], "level": documents[0]["level"], "method": documents[0]["method"],
                               "split": part, "actual_label": label, "n": n,
                               "occupied_clusters": int((matrix[i] > 0).sum()),
                               "largest_cluster_share": float(matrix[i].max()) / n if n else None,
                               "cluster_entropy_bits": -sum(p * math.log2(p) for p in proportions) if n else None,
                               "cluster_ids": ",".join(str(c) for c in range(n_clusters) if matrix[i, c])})
    write_csv(target / "cluster_summary.csv", groups)
    (target / "clusters.md").write_text("\n".join(cluster_lines) + "\n", encoding="utf-8")
    plot_final_cross_tabs(figures, counts, labels, label_codes, n_clusters)
    plot_final_composition(figures, counts, labels, label_codes, n_clusters)
    (target / "README.md").write_text("\n".join([
        f"# {documents[0]['experiment']} · k={n_clusters}", "", "[군집별 문항 목록](clusters.md) · [문항별 CSV](members.csv) · [군집 요약/문항 ID](cluster_summary.csv)", "",
        "[학습 교차표](cross_tab_train.csv) · [테스트 교차표](cross_tab_test.csv) · [라벨 코드 전체 경로](label_key.csv)", "",
        "그림은 `figures/`에 있다. 라벨이 많으면 최대 20행으로 히트맵을 나누었다. 라벨 코드는 전체 경로의 사전순 번호이며 라벨 번호와 군집 번호는 다르다.",
        "구성비 그림은 학습 빈도 상위 8개 라벨과 기타를 사용한다. 모든 실제 라벨의 정확한 비율은 상위 폴더의 `cluster_label_distribution.csv`에 보존했다.",
        "테스트 그림에 실제 라벨을 표시하는 것은 평가·관찰을 위한 것이며 중심 계산이나 대표 라벨 선정에 사용하지 않았다.", ""]) , encoding="utf-8")
    return distribution, dispersion


def plot_final_cross_tabs(folder, counts, labels, codes, k):
    """유형이 많은 표는 20행 단위로 분할한다. 전체 라벨 경로는 CSV로 연결한다."""
    import numpy as np
    plt = setup_final_plots()
    for part, matrix in counts.items():
        active_rows = [i for i in range(len(labels)) if matrix[i].sum()]
        occupied = np.flatnonzero(matrix.sum(axis=0))
        if not len(occupied):
            continue
        maximum = max(1, matrix.max())
        for page, start in enumerate(range(0, len(active_rows), 20), 1):
            rows = active_rows[start:start + 20]
            shown = matrix[np.ix_(rows, occupied)]
            fig, ax = plt.subplots(figsize=(max(9, .24 * len(occupied) + 5), max(3, .40 * len(rows) + 1.5)), constrained_layout=True)
            im = ax.imshow(shown, cmap="Greys", vmin=0, vmax=maximum, aspect="auto", interpolation="nearest")
            row_names = [f"{codes[labels[i]]}  {labels[i].split(' / ')[-1][:38]}" for i in rows]
            ax.set_yticks(range(len(rows)), row_names, fontsize=8)
            ax.set_xticks(range(len(occupied)), occupied, fontsize=7)
            for i in range(len(rows)):
                for j in range(len(occupied)):
                    value = shown[i, j]
                    if value:
                        ax.text(j, i, str(value), ha="center", va="center", fontsize=7,
                                color="white" if value > maximum / 2 else "black")
            ax.set(xlabel="군집 번호 (빈 군집 제외)", ylabel="실제 분류 · 라벨 코드", title=f"{'학습' if part == 'train' else '테스트'} 분류 × 군집 · k={k} · {page}쪽")
            fig.colorbar(im, ax=ax, label="문항 수", shrink=.7)
            fig.savefig(folder / f"cross_tab_{part}_{page:02d}.png", dpi=180)
            plt.close(fig)


def plot_final_composition(folder, counts, labels, codes, k):
    import numpy as np
    plt = setup_final_plots()
    top = np.argsort(-counts["train"].sum(axis=1), kind="stable")[:8].tolist()
    for part, matrix in counts.items():
        totals = matrix.sum(axis=0)
        for page, first in enumerate(range(0, k, 25), 1):
            clusters = np.arange(first, min(first + 25, k))
            fig, ax = plt.subplots(figsize=(10, 4.8), constrained_layout=True)
            bottom = np.zeros(len(clusters))
            for index, label_index in enumerate(top):
                values = np.divide(matrix[label_index, clusters], totals[clusters], out=np.zeros(len(clusters)), where=totals[clusters] != 0)
                ax.bar(clusters, values, bottom=bottom, label=codes[labels[label_index]] + " " + labels[label_index].split(" / ")[-1][:22],
                       color=str(.08 + index * .09), edgecolor="white", linewidth=.3)
                bottom += values
            others = np.where(totals[clusters] > 0, 1 - bottom, 0)
            if len(labels) > len(top):
                ax.bar(clusters, others, bottom=bottom, label="기타 라벨", color="white", edgecolor="black", hatch="///", linewidth=.4)
            for cluster, n in zip(clusters, totals[clusters]):
                ax.text(cluster, 1.015, str(n), ha="center", va="bottom", fontsize=7)
            ax.set_xticks(clusters, clusters, fontsize=7)
            ax.set(xlabel="군집 번호 · 위 숫자는 문항 수", ylabel="군집 내부 실제 라벨 비율", ylim=(0, 1.12),
                   title=f"{'학습' if part == 'train' else '테스트'} 군집별 라벨 구성 · k={k} · {page}쪽")
            ax.legend(fontsize=6.8, loc="upper center", bbox_to_anchor=(.5, -.2), ncol=3)
            fig.savefig(folder / f"label_composition_{part}_{page:02d}.png", dpi=180, bbox_inches="tight")
            plt.close(fig)


def plot_final_comparison(output, rows):
    import numpy as np
    plt = setup_final_plots()
    folder = Path(output) / "figures"
    folder.mkdir(exist_ok=True)
    levels = ["curriculum", "unit", "subunit", "type"]
    names = ["과목", "단원", "세부단원", "문제 유형"]
    for metric, title in (("ari", "ARI · 우연 일치 보정 군집 지수"), ("nmi", "NMI · 정규화 상호정보량"),
                          ("train_majority_accuracy", "학습 다수 라벨 기반 분류 정확도")):
        fig, axes = plt.subplots(1, 2, figsize=(10, 3.8), constrained_layout=True)
        for ax, part in zip(axes, ("train", "test")):
            for i, (method, label, color) in enumerate((("euclidean", "유클리드", "white"), ("spherical", "코사인(구면)", ".3"))):
                values = [next(row[metric] for row in rows if row["level"] == level and row["method"] == method and row["split"] == part) for level in levels]
                x = np.arange(4) + (i - .5) * .34
                bars = ax.bar(x, values, width=.34, label=label, color=color, edgecolor="black", linewidth=.8)
                for bar, value in zip(bars, values):
                    ax.text(bar.get_x() + bar.get_width() / 2, value + .018, f"{value:.3f}", ha="center", va="bottom", fontsize=8)
            ax.set_xticks(range(4), names)
            ax.set(ylim=(-.1 if metric == "ari" else 0, 1.13), title="학습" if part == "train" else "테스트", ylabel=metric.upper() if metric != "train_majority_accuracy" else "정확도")
            ax.axhline(0, color=".7", linewidth=.5)
        axes[0].legend(fontsize=8)
        fig.suptitle(title)
        fig.savefig(folder / f"{metric}_comparison.png", dpi=180)
        plt.close(fig)


def save_pca_views(output, matrices, ids, records, reports):
    """각 표현 공간에서 학습으로만 PCA를 맞춘다. K-means는 원래 차원이다."""
    import numpy as np
    from sklearn.decomposition import PCA
    from .TorchKMeans import l2_normalize
    plt = setup_final_plots()
    for method in ("euclidean", "spherical"):
        arrays = {part: (matrix if method == "euclidean" else l2_normalize(matrix)).numpy() for part, matrix in matrices.items()}
        if min(arrays["train"].shape) < 2:
            continue
        pca = PCA(n_components=2, svd_solver="full").fit(arrays["train"])
        projections = {part: pca.transform(matrix) for part, matrix in arrays.items()}
        rows = [{"id": identifier, "split": part, "pc1": float(projections[part][i, 0]), "pc2": float(projections[part][i, 1])}
                for part in ("train", "test") for i, identifier in enumerate(ids[part])]
        projection = {"fit_split": "train", "representation": "raw counts" if method == "euclidean" else "L2 normalized counts",
                      "explained_variance_ratio": pca.explained_variance_ratio_.tolist(), "documents": rows,
                      "components": pca.components_.tolist(), "mean": pca.mean_.tolist(),
                      "note": "Display only. K-means trained in original feature dimension, not these two coordinates."}
        (Path(output) / f"pca_{method}.json").write_text(json.dumps(projection, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        for level in ("curriculum", "unit"):
            report = next(row for row in reports if row["method"] == method and row["level"] == level)
            test_members = [r for r in report["documents"] if r["split"] == "test"]
            labels = sorted({r["actual_label"] for r in test_members})
            fig, axes = plt.subplots(1, 2, figsize=(10, 4.3), constrained_layout=True)
            for side, field in enumerate(("actual_label", "cluster")):
                values = labels if side == 0 else sorted({row["cluster"] for row in test_members})
                for index, value in enumerate(values):
                    mask = np.array([row[field] == value for row in test_members])
                    axes[side].scatter(projections["test"][mask, 0], projections["test"][mask, 1], s=35,
                                       color=str(.08 + .8 * index / max(1, len(values) - 1)), edgecolors="black", linewidths=.4,
                                       marker=["o", "s", "^", "D", "v", "P", "X", "*"][index % 8],
                                       label=value.split(" / ")[-1] if side == 0 else f"군집 {value}")
                axes[side].set(xlabel="주성분 1", ylabel="주성분 2", title="실제 분류" if side == 0 else "학습 중심으로 배정한 군집")
                axes[side].legend(fontsize=6.5)
            fig.suptitle(f"테스트 PCA · {method} · {level} · 학습으로만 투영 학습 / 군집화는 원래 차원", fontsize=10)
            fig.savefig(Path(output) / "figures" / f"pca_{level}_{method}.png", dpi=180)
            plt.close(fig)
