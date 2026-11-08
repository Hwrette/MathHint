"""고정 분할로 두 모델을 학습하고, 성능 지표와 그림을 한꺼번에 저장한다.

계산 과정은 TorchRegression·TorchKMeans에 있고, 이 파일은 실험을 연결한다.
상단 설정을 바꾼 뒤 python -m mathhint_learning.RunTraining 으로 실행한다.
"""

from __future__ import annotations

from collections import Counter
import csv
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import torch

from .TorchKMeans import assign_clusters, fit_kmeans
from .TorchData import load_fixed_dataset, write_json
from .TorchRegression import train_regression as fit_fixed_regression
from .TorchRegression import evaluate as regression_metrics


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs/model_comparison/training"
EPOCHS = 500
LEARNING_RATE = 0.01
SEED = 42
RESTARTS = 5


def cluster_metrics(assignments: list[int], labels: list[str]) -> dict:
    from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score
    members: dict[int, list[str]] = {}
    for cluster, label in zip(assignments, labels):
        members.setdefault(cluster, []).append(label)
    return {"adjusted_rand_index": float(adjusted_rand_score(labels, assignments)),
            "normalized_mutual_information": float(normalized_mutual_info_score(labels, assignments)),
            "purity": sum(max(Counter(values).values()) for values in members.values()) / len(labels),
            "n_labels": len(set(labels)), "n_occupied_clusters": len(members), "n": len(labels)}


def majority_labels(train_assignments: list[int], train_labels: list[str]) -> dict[int, str]:
    """학습 군집의 다수 라벨을 정한다. 동률은 라벨 순서로 정한다."""
    members: dict[int, list[str]] = {}
    for cluster, label in zip(train_assignments, train_labels):
        members.setdefault(cluster, []).append(label)
    return {cluster: sorted(Counter(labels).items(), key=lambda pair: (-pair[1], pair[0]))[0][0]
            for cluster, labels in members.items()}


def _setup_plots(output: Path) -> None:
    os.environ.setdefault("MPLCONFIGDIR", str(output / ".matplotlib_cache"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    font_path = Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
    if font_path.exists():
        font_manager.fontManager.addfont(str(font_path))
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=str(font_path)).get_name()
    plt.rcParams.update({"axes.unicode_minus": False, "axes.spines.top": False,
                         "axes.spines.right": False, "figure.dpi": 140, "font.size": 9})


def _save_plot(fig, path: Path) -> None:
    import matplotlib.pyplot as plt
    fig.tight_layout()
    fig.savefig(path.with_suffix(".png"), bbox_inches="tight")
    fig.savefig(path.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def run(root: Path, output: Path, *, epochs: int = 500, learning_rate: float = .01,
        seed: int = 42, restarts: int = 5) -> dict:
    torch.set_num_threads(2)
    output.mkdir(parents=True, exist_ok=True)
    dataset = load_fixed_dataset(root)
    ids, records, arrays = dataset["ids"], dataset["records"], dataset["arrays"]
    X_train, Y_train = arrays["problems"]["train"], arrays["solutions"]["train"]
    X_test, Y_test = arrays["problems"]["test"], arrays["solutions"]["test"]
    model, history = fit_fixed_regression(X_train, Y_train, epochs=epochs, learning_rate=learning_rate, seed=seed)
    with torch.no_grad():
        predictions = {"train": model(X_train), "test": model(X_test)}
    training_mean = Y_train.mean(dim=0)
    regression_report = {"model": "linear_regression", "architecture": f"nn.Linear({X_train.shape[1]},{Y_train.shape[1]})",
                         "optimizer": "Adam", "loss": "MSE", "epochs": epochs, "learning_rate": learning_rate,
                         "seed": seed, "split_source": "data/processed/splits/*.json", "test_used_for_training_or_selection": False,
                         "initial_train_mse": history[0]["train_mse"], "negative_prediction_policy": "clip_to_zero_without_rounding_for_nonnegative_frequency_input",
                         "metrics": {}}
    for part in ("train", "test"):
        actual = arrays["solutions"][part]
        regression_report["metrics"][part] = {"raw": regression_metrics(predictions[part], actual),
            "clipped_nonnegative": regression_metrics(predictions[part].clamp_min(0), actual),
            "training_mean_baseline": regression_metrics(training_mean.expand_as(actual), actual)}
    torch.save({"model_type": "multioutput_linear_regression", "model_state_dict": model.state_dict(),
                "input_vocabulary": dataset["vocabularies"]["problems"],
                "output_vocabulary": dataset["vocabularies"]["solutions"], "input_dim": X_train.shape[1], "output_dim": Y_train.shape[1],
                "generation_id": dataset["generation_id"], "train_ids": ids["train"],
                "epochs": epochs, "seed": seed, "learning_rate": learning_rate}, output / "regression_model.pt")
    model_sha256 = hashlib.sha256((output / "regression_model.pt").read_bytes()).hexdigest()
    write_json(output / "regression_predictions.json", {"generation_id": dataset["generation_id"], "split": "test",
        "train_ids": ids["train"], "model_sha256": model_sha256,
        "config": {"epochs": epochs, "learning_rate": learning_rate, "seed": seed, "architecture": regression_report["architecture"]},
        "vocabulary": dataset["vocabularies"]["solutions"], "prediction_policy": regression_report["negative_prediction_policy"],
        "documents": [{"id": item_id, "raw_predicted_vector": predictions["test"][i].tolist(),
                       "predicted_vector": predictions["test"][i].clamp_min(0).tolist(), "actual_vector": Y_test[i].tolist()}
                      for i, item_id in enumerate(ids["test"])]})
    write_json(output / "regression_learning_curve.json", history)
    write_json(output / "regression_metrics.json", regression_report)
    print("Regression complete: predictions for all fixed test IDs saved.", flush=True)

    labels_by_part = {part: {field: [records[item_id][field] for item_id in ids[part]]
                            for field in ("subject", "unit", "type")} for part in ("train", "test")}
    label_prior_baselines = {}
    for field in ("subject", "unit", "type"):
        train_majority = sorted(Counter(labels_by_part["train"][field]).items(), key=lambda pair: (-pair[1], pair[0]))[0][0]
        label_prior_baselines[field] = {"training_majority_label": train_majority,
            "test_accuracy": sum(label == train_majority for label in labels_by_part["test"][field]) / len(ids["test"])}
    # These k values are counts from training metadata, not optimized on test labels.
    configurations = [("subject", len(set(labels_by_part["train"]["subject"]))),
                      ("unit", len(set(labels_by_part["train"]["unit"]))),
                      ("type", len(set(labels_by_part["train"]["type"])))]
    clustering_reports = []
    clustered = {}
    for target_level, k in configurations:
        trials = [fit_kmeans(X_train, n_clusters=k, seed=seed + restart, max_iter=100) for restart in range(restarts)]
        best_index = min(range(restarts), key=lambda index: trials[index]["inertia"])
        fitted = trials[best_index]
        assignments = {"train": fitted["assignments"].tolist(), "test": assign_clusters(X_test, fitted["centers"]).tolist()}
        report = {"k": k, "nominal_target_level": target_level, "fit_split": "train", "feature_transform": "raw_counts",
                  "distance": "euclidean", "restarts": restarts, "seeds": [seed + i for i in range(restarts)],
                  "selected_seed": seed + best_index, "selection": "lowest_training_inertia_only",
                  "train_inertia": fitted["inertia"], "iterations": fitted["iterations"],
                  "restart_train_inertias": [trial["inertia"] for trial in trials], "metrics": {}}
        maps = {field: majority_labels(assignments["train"], labels_by_part["train"][field])
                for field in ("subject", "unit", "type")}
        documents = []
        for part in ("train", "test"):
            report["metrics"][part] = {}
            for field in ("subject", "unit", "type"):
                labels = labels_by_part[part][field]
                field_metrics = cluster_metrics(assignments[part], labels)
                field_metrics["accuracy_using_train_cluster_majority"] = sum(
                    maps[field].get(cluster) == label for cluster, label in zip(assignments[part], labels)) / len(labels)
                report["metrics"][part][field] = field_metrics
            for i, item_id in enumerate(ids[part]):
                cluster = assignments[part][i]
                documents.append({"id": item_id, "split": part, "cluster": cluster,
                    "actual_labels": {field: records[item_id][field] for field in ("subject", "unit", "type")},
                    "train_majority_predicted_labels": {field: maps[field].get(cluster) for field in maps}})
        write_json(output / f"kmeans_k{k}_assignments.json", {"generation_id": dataset["generation_id"],
            "k": k, "train_majority_label_maps": maps, "documents": documents})
        torch.save({"centers": fitted["centers"], "vocabulary": dataset["vocabularies"]["problems"],
                    "k": k, "train_ids": ids["train"], "feature_transform": "raw_counts",
                    "seed": seed + best_index, "generation_id": dataset["generation_id"]}, output / f"kmeans_k{k}_model.pt")
        clustering_reports.append(report)
        clustered[k] = assignments
        print(f"K-means k={k} complete; train-selected seed={seed + best_index}.", flush=True)
    write_json(output / "clustering_metrics.json", {"configurations": clustering_reports,
        "training_label_prior_baselines": label_prior_baselines,
        "interpretation": "Purity tends to increase with k. Compare ARI/NMI and held-out train-majority accuracy too. Raw-count results do not rule out other vector transforms or embeddings."})

    _setup_plots(output)
    import matplotlib.pyplot as plt
    from sklearn.decomposition import PCA
    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.plot([row["epoch"] for row in history], [row["train_mse"] for row in history], color="black")
    ax.axhline(regression_report["metrics"]["train"]["training_mean_baseline"]["mse"], color=".45", linestyle="--", label="학습 평균벡터 기준선")
    ax.set(xlabel="학습 반복(epoch)", ylabel="학습 MSE", title="선형회귀 학습 곡선 · 테스트는 학습에 사용하지 않음")
    ax.legend(); _save_plot(fig, output / "regression_learning_curve")
    fig, axs = plt.subplots(1, 2, figsize=(9, 3.5))
    for ax, metric, title in zip(axs, ("mse", "mean_cosine_similarity"), ("평균제곱오차 (낮을수록 좋음)", "코사인 유사도 (높을수록 좋음)")):
        values = [regression_report["metrics"]["test"][method][metric] for method in ("training_mean_baseline", "raw", "clipped_nonnegative")]
        bars = ax.bar(["학습 평균벡터", "회귀 원출력", "회귀 음수→0"], values, color=["white", ".6", ".2"], edgecolor="black")
        ax.set_title(title); ax.set_ylabel("테스트 80문항")
        for bar, value in zip(bars, values):
            ax.annotate(f"{value:.3f}", (bar.get_x() + bar.get_width()/2, bar.get_height()), ha="center", va="bottom", fontsize=8)
    _save_plot(fig, output / "regression_test_metrics")
    k_labels = [str(row["k"]) for row in clustering_reports]
    fig, axs = plt.subplots(1, 3, figsize=(12, 3.5), sharey=False)
    for ax, field, title in zip(axs, ("subject", "unit", "type"), ("대분류(미분/삼각함수)", "단원", "세부 유형")):
        for metric, linestyle, marker, label in (("adjusted_rand_index", "-", "o", "ARI"),
                ("normalized_mutual_information", "--", "s", "NMI"),
                ("accuracy_using_train_cluster_majority", ":", "^", "학습 다수 라벨로 예측한 정확도")):
            ax.plot(k_labels, [row["metrics"]["test"][field][metric] for row in clustering_reports],
                    color="black", linestyle=linestyle, marker=marker, label=label)
        ax.set(title=title, xlabel="군집 수 k", ylim=(-.1, 1.05)); ax.axhline(0, color=".8", linewidth=.7)
    axs[-1].legend(fontsize=7, loc="upper right"); _save_plot(fig, output / "clustering_heldout_scores")

    pca = PCA(n_components=2).fit(X_train.numpy())
    projections = {"train": pca.transform(X_train.numpy()), "test": pca.transform(X_test.numpy())}
    length_diagnostics = {"train_pc1_vs_total_token_count_pearson_r": float(np.corrcoef(projections["train"][:, 0], X_train.sum(dim=1).numpy())[0, 1]),
        "train_pc1_vs_vector_l2_norm_pearson_r": float(np.corrcoef(projections["train"][:, 0], torch.linalg.vector_norm(X_train, dim=1).numpy())[0, 1]),
        "interpretation": "Raw counts and Euclidean distance can reflect document length as well as mathematical content.",
        "test_used_to_choose_transform": False}
    write_json(output / "raw_count_length_diagnostics.json", length_diagnostics)
    write_json(output / "pca_projection.json", {"fit_split": "train", "explained_variance_ratio": pca.explained_variance_ratio_.tolist(),
        "documents": [{"id": item_id, "split": part, "coordinates": projections[part][i].tolist()}
                      for part in ("train", "test") for i, item_id in enumerate(ids[part])],
        "note": "2D display only; K-means was fitted in the original 346-dimensional raw-count space."})
    for field, title, k in (("subject", "대분류", configurations[0][1]), ("unit", "단원", configurations[1][1])):
        fig, axs = plt.subplots(1, 2, figsize=(10, 4))
        unique = sorted(set(labels_by_part["train"][field]))
        for index, label in enumerate(unique):
            mask = np.array([value == label for value in labels_by_part["test"][field]])
            axs[0].scatter(projections["test"][mask, 0], projections["test"][mask, 1], label=label,
                           s=32, marker=["o", "s", "^", "v", "D", "P", "X", "*"][index % 8],
                           facecolors=str(.1 + .75 * index/max(1,len(unique)-1)), edgecolors="black", linewidths=.4)
        for cluster in range(k):
            mask = np.array(clustered[k]["test"]) == cluster
            axs[1].scatter(projections["test"][mask, 0], projections["test"][mask, 1], label=f"군집 {cluster}",
                           s=32, marker=["o", "s", "^", "v", "D", "P", "X", "*"][cluster % 8],
                           facecolors=str(.1 + .75*cluster/max(1,k-1)), edgecolors="black", linewidths=.4)
        for ax, subtitle in zip(axs, (f"실제 {title} 라벨", f"훈련에서 찾은 군집 k={k}")):
            ax.set(xlabel="주성분 1", ylabel="주성분 2", title=subtitle); ax.legend(fontsize=6)
        fig.suptitle("테스트 80문항 · 학습 데이터에서만 맞춘 PCA (군집화는 원래 차원에서 수행)", fontsize=10)
        _save_plot(fig, output / f"pca_{field}_vs_clusters")
    # A label-by-cluster count heatmap makes exact type membership inspectable.
    type_k = configurations[-1][1]
    type_labels = sorted(set(labels_by_part["train"]["type"]))
    matrix = np.zeros((len(type_labels), type_k), dtype=int)
    for label, cluster in zip(labels_by_part["test"]["type"], clustered[type_k]["test"]):
        matrix[type_labels.index(label), cluster] += 1
    occupied = np.flatnonzero(matrix.sum(axis=0))
    fig, ax = plt.subplots(figsize=(13, 15))
    image = ax.imshow(matrix[:, occupied], cmap="Greys", aspect="auto", interpolation="nearest")
    ax.set_yticks(range(len(type_labels)), type_labels, fontsize=6)
    ax.set_xticks(range(len(occupied)), occupied, fontsize=6)
    ax.set(xlabel="군집 번호", ylabel="원본 세부 유형", title=f"테스트 유형별 군집 분포 · k={type_k} (빈 칸은 0문항)")
    fig.colorbar(image, ax=ax, label="문항 수", shrink=.4); _save_plot(fig, output / "type_cluster_heatmap")
    with (output / "cluster_assignments.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream); writer.writerow(["id", "split", "subject", "unit", "type"] + [f"cluster_k{k}" for _, k in configurations])
        for part in ("train", "test"):
            for i, item_id in enumerate(ids[part]):
                writer.writerow([item_id, part] + [records[item_id][field] for field in ("subject", "unit", "type")] +
                                [clustered[k][part][i] for _, k in configurations])
    summary = {"generation_id": dataset["generation_id"], "train_count": len(ids["train"]), "test_count": len(ids["test"]),
               "problem_dimensions": X_train.shape[1], "solution_dimensions": Y_train.shape[1],
               "regression": regression_report, "clustering": clustering_reports,
               "training_label_prior_baselines": label_prior_baselines, "raw_count_length_diagnostics": length_diagnostics,
               "pca_variance_explained_by_two_components": float(pca.explained_variance_ratio_.sum()),
               "test_target_exposure": "evaluation only after fixed training configuration; no test-based tuning",
               "torch_version": torch.__version__}
    write_json(output / "training_summary.json", summary)
    lines = ["# 고정 학습/테스트 모델 실험", "", f"학습 {len(ids['train'])}문항 · 테스트 {len(ids['test'])}문항. 입력 {X_train.shape[1]}차원, 해설 {Y_train.shape[1]}차원.",
        "빈도는 원시 횟수이며 정규화·TF-IDF·임베딩을 사용하지 않았다. 테스트 정답/해설은 학습이나 모델 선택에 쓰지 않았다.", "",
        "## 회귀", "", f"선형층 + Adam, {epochs}회, 학습률 {learning_rate}, seed={seed}. 테스트 MSE(원출력): {regression_report['metrics']['test']['raw']['mse']:.4f}; 학습 평균벡터 기준선: {regression_report['metrics']['test']['training_mean_baseline']['mse']:.4f}.",
        "생성 실험에 전달할 예측 빈도는 음수를 0으로 바꾸며 반올림하지 않았다. 실제 테스트 해설 벡터는 평가용으로만 저장했다.", "",
        "## 군집", "", f"k는 학습 라벨 종류 수에서 2/8/70으로 미리 정했다. 각 {restarts}회 초기화 중 학습 inertia가 최소인 결과만 선택했다.",
        "테스트 정확도는 학습 군집의 다수 라벨을 테스트 군집에 적용한 값이다. 군집 번호는 유형 번호가 아니다.",
        "k가 커지면 purity와 NMI가 높아질 수 있으므로 ARI·학습 다수 라벨 기반 테스트 정확도를 함께 봐야 한다.", "",
        "|k|단원 ARI|유형 ARI|유형 NMI|유형 예측 정확도|", "|---:|---:|---:|---:|---:|"]
    for row in clustering_reports:
        u, t = row["metrics"]["test"]["unit"], row["metrics"]["test"]["type"]
        lines.append(f"|{row['k']}|{u['adjusted_rand_index']:.3f}|{t['adjusted_rand_index']:.3f}|{t['normalized_mutual_information']:.3f}|{t['accuracy_using_train_cluster_majority']:.1%}|")
    lines += ["", f"PCA 두 축이 설명하는 학습 분산은 {100*pca.explained_variance_ratio_.sum():.1f}%다. 산점도는 표시용이며 실제 군집은 원래 차원에서 계산했다.",
              "원시 빈도+유클리드 K-means 한 가지 설정의 결과이므로 다른 빈도 변환이나 임베딩의 성능까지 결론내릴 수 없다."]
    (output / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "train": len(ids["train"]), "test": len(ids["test"]),
                      "regression_test_mse": regression_report["metrics"]["test"]["raw"]["mse"]}), flush=True)
    return summary


def main() -> None:
    # 데이터 읽기 → 두 모델 학습 → 테스트 평가 → 그림과 결과 저장
    run(ROOT, OUTPUT, epochs=EPOCHS, learning_rate=LEARNING_RATE, seed=SEED, restarts=RESTARTS)


if __name__ == "__main__":
    main()
