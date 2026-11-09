"""기존 어휘·벡터를 결합하여 전체 265문항을 군집화한다.

실행: python -m mathhint_learning.full_dataset_265
공통 TorchKMeans를 재사용한다. 기존 분리 실험·회귀·Gemini는 실행하지 않는다.
"""

from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path

import numpy as np
import torch
from sklearn.decomposition import PCA
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score

from ..TorchData import load_fixed_dataset, write_json
from ..TorchKMeans import fit_kmeans, fit_spherical_kmeans, l2_normalize
from ..FinalClustering import (LEVELS, LEVEL_NAMES, METHOD_NAMES, SEEDS, MAX_ITER,
                               TOLERANCE, hierarchy_label, majority_labels,
                               input_hashes, sha256, write_csv)
from ..ClusterReport import (cluster_problem_links, setup_final_plots,
                             plot_final_cross_tabs, plot_final_composition)

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "results/final_experiment/01_clustering/full_dataset_265"


def dataset(root, *, expected_count=265, expected_dimensions=346):
    """원래 분할의 순서를 보존하여 train 다음 test 행을 결합한다."""
    data = load_fixed_dataset(root)
    ids = data["ids"]["train"] + data["ids"]["test"]
    matrix = torch.cat([data["arrays"]["problems"][part] for part in ("train", "test")])
    if len(ids) != expected_count or len(set(ids)) != len(ids):
        raise ValueError(f"전체 문항 수/중복 오류: {len(ids)}개, 기대 {expected_count}개")
    if tuple(matrix.shape) != (expected_count, expected_dimensions):
        raise ValueError(f"전체 벡터 차원 오류: {tuple(matrix.shape)}, 기대 {(expected_count, expected_dimensions)}")
    for part in ("train", "test"):
        saved = json.loads((Path(root) / f"data/vectors/problems/{part}_vectors.json").read_text(encoding="utf-8-sig"))
        for document in saved["documents"]:
            if document.get("file") != f"{document['id']}.txt":
                raise ValueError(f"문제 벡터의 ID와 원문 파일명이 다릅니다: {document['id']}")
    for identifier in ids:
        if not (Path(root) / f"data/processed/problems/{identifier}.txt").is_file():
            raise FileNotFoundError(f"원본 문제 ID에 대응하는 파일이 없습니다: {identifier}")
    data.update(full_ids=ids, matrix=matrix,
                original_split={identifier: part for part in ("train", "test") for identifier in data["ids"][part]})
    return data


def count_artifacts(target, documents, labels, k):
    """설명용 대표 라벨은 전체 fit 집합에서 정하며 테스트 정확도라고 부르지 않는다."""
    codes = {label: f"L{i + 1:02d}" for i, label in enumerate(labels)}
    positions = {label: i for i, label in enumerate(labels)}
    matrix = np.zeros((len(labels), k), dtype=np.int64)
    for row in documents:
        matrix[positions[row["actual_label"]], row["cluster"]] += 1
    write_csv(target / "members.csv", documents)
    write_csv(target / "label_key.csv", [{"label_code": codes[label], "actual_label": label} for label in labels])
    write_csv(target / "cross_tab_all.csv", [
        {"label_code": codes[label], "actual_label": label, **{f"cluster_{c:02d}": int(matrix[i, c]) for c in range(k)}}
        for i, label in enumerate(labels)])
    summaries, distribution, dispersion = [], [], []
    for cluster in range(k):
        rows = [row for row in documents if row["cluster"] == cluster]
        majority = rows[0]["full_majority_label"] if rows else None
        summaries.append({"cluster": cluster, "n": len(rows), "full_majority_label": majority,
                          "ids": ",".join(row["id"] for row in rows),
                          "original_train_n": sum(row["original_split"] == "train" for row in rows),
                          "original_test_n": sum(row["original_split"] == "test" for row in rows)})
        for label, count in sorted(Counter(row["actual_label"] for row in rows).items(), key=lambda pair: (-pair[1], pair[0])):
            distribution.append({"experiment": documents[0]["experiment"], "level": documents[0]["level"],
                "method": documents[0]["method"], "cluster": cluster, "actual_label": label,
                "label_code": codes[label], "count": count, "cluster_n": len(rows), "ratio": count / len(rows),
                "full_majority_label": majority})
    for i, label in enumerate(labels):
        n = int(matrix[i].sum())
        proportions = [int(value) / n for value in matrix[i] if value] if n else []
        dispersion.append({"experiment": documents[0]["experiment"], "level": documents[0]["level"],
            "method": documents[0]["method"], "actual_label": label, "n": n,
            "occupied_clusters": int((matrix[i] > 0).sum()),
            "largest_cluster_share": float(matrix[i].max()) / n if n else None,
            "cluster_entropy_bits": -sum(value * math.log2(value) for value in proportions) if n else None,
            "cluster_ids": ",".join(str(c) for c in range(k) if matrix[i, c])})
    write_csv(target / "cluster_summary.csv", summaries)
    write_csv(target / "cluster_label_distribution.csv", distribution)
    write_csv(target / "label_dispersion.csv", dispersion)
    return matrix, codes, distribution, dispersion


def reading_documents(root, output, target, documents, labels, k):
    reader = Path(root) / "results/final_experiment/03_gemini/report.html"
    lines = [f"# {documents[0]['experiment']} · 전체 {len(documents)}문항의 군집", "",
        "전체 데이터로 중심과 대표 라벨을 정한 탐색 실험이다. 원래 학습/테스트 구분은 출처 확인용이며 이 실험의 평가 분할이 아니다.",
        "문항 ID는 기존 수식 읽기 화면을 연다. 해당 화면의 A/B/C는 기존 분리 연구의 응답이며 이번 탐색 실험에서 새로 생성하지 않았다.", ""]
    for cluster in range(k):
        rows = [row for row in documents if row["cluster"] == cluster]
        frequencies = Counter(row["actual_label"] for row in rows)
        majority = rows[0]["full_majority_label"] if rows else None
        lines += [f'<a id="cluster-{cluster}"></a>', "", f"## 군집 {cluster:02d} · {len(rows)}문항", "", f"전체 데이터 대표 라벨: {majority or '없음'}", "",
                  "|실제 분류|문항 수|군집 내 비율|", "|---|---:|---:|"]
        lines += [f"|{label}|{count}|{count / len(rows):.1%}|" for label, count in frequencies.most_common()]
        lines += ["", "|문항 ID / 수식 · 원문|원래 분할(출처)|과목|단원|세부단원|유형|", "|---|---|---|---|---|---|"]
        for row in rows:
            links = cluster_problem_links(root, output, target, row["id"], reader_path=reader)
            lines.append(f"|{links}|{row['original_split']}|{row['curriculum']}|{row['unit']}|{row['subunit']}|{row['type']}|")
        lines.append("")
    (target / "clusters.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    figure_lines = []
    for prefix, title in (("cross_tab_all", "실제 분류 × 군집 번호"), ("label_composition_all", "군집 구성 비율")):
        pages = sorted((target / "figures").glob(prefix + "_*.png"))
        figure_lines.append(f"- {title}: " + " · ".join(f"[{i}쪽]({path.relative_to(target).as_posix()})" for i, path in enumerate(pages, 1)))
    lines = [f"# {documents[0]['experiment']} · 전체 {len(documents)}문항 · k={k}", "",
        f"{len(documents)}문항 전체를 학습하고 같은 문항의 구조를 설명하는 탐색 실험이다. 새로운 문항에 대한 테스트 성능이 아니다.", "",
        "[군집별 실제 문제](clusters.md) · [문항별 배정](members.csv) · [군집 요약](cluster_summary.csv)",
        "[교차표](cross_tab_all.csv) · [전체 라벨 경로](label_key.csv) · [라벨 구성 빈도·비율](cluster_label_distribution.csv) · [라벨 분산](label_dispersion.csv)", "",
        *figure_lines, "- [동일 데이터 설명용 혼동행렬](figures/confusion_matrix_all.png) · [정확한 행렬 수치](confusion_matrix_all.csv)", "",
        "교차표 가로축은 군집 번호다. 혼동행렬 가로축은 전체 데이터에서 정한 군집 최빈 실제 라벨이다. 이 대표 라벨 일치율은 같은 자료로 대표 라벨을 정하고 평가한 설명용 일치율이며 테스트 정확도가 아니다.",
        "혼동행렬의 행과 열은 전체 계층 경로의 사전순 라벨 코드로 동일하게 정렬한다. 실제/예측 빈도가 0인 축도 남긴다. 전체 이름은 label_key.csv에서 확인한다.", "",
        "[중심·원래 분할·어휘 체크포인트](model.pt) · [설정·시드별 목적함수·평가](experiment.json)", "",
        "군집화는 원래 BoW 차원에서 수행했다. PCA는 상위 폴더의 그림/투영 JSON으로 확인하며 고차원 결과의 표시만을 위한 것이다."]
    (target / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def save_pca(output, data, reports):
    """전체 자료로 맞춘 PCA. 두 표현 공간을 별도로 투영하며 좌표를 직접 비교하지 않는다."""
    plt = setup_final_plots()
    for method in METHOD_NAMES:
        matrix = data["matrix"] if method == "euclidean" else l2_normalize(data["matrix"])
        if min(matrix.shape) < 2:
            continue
        array = matrix.numpy()
        pca = PCA(n_components=2, svd_solver="full").fit(array)
        coordinates = pca.transform(array)
        write_json(output / f"pca_{method}.json", {
            "fit_scope": "all", "n": len(data["full_ids"]),
            "representation": "raw counts" if method == "euclidean" else "L2 normalized counts",
            "explained_variance_ratio": pca.explained_variance_ratio_.tolist(),
            "components": pca.components_.tolist(), "mean": pca.mean_.tolist(),
            "documents": [{"id": identifier, "original_split": data["original_split"][identifier],
                           "pc1": float(coordinates[i, 0]), "pc2": float(coordinates[i, 1])}
                          for i, identifier in enumerate(data["full_ids"])],
            "note": "Display only. Fit on all data in this exploratory run; K-means fitted in the original BoW dimension."})
        for level in ("curriculum", "unit"):
            report = next(row for row in reports if row["level"] == level and row["method"] == method)
            documents = report["documents"]
            figure, axes = plt.subplots(1, 2, figsize=(11, 4.6), constrained_layout=True)
            for side, field in enumerate(("actual_label", "cluster")):
                values = sorted({row[field] for row in documents})
                for index, value in enumerate(values):
                    mask = np.array([row[field] == value for row in documents])
                    axes[side].scatter(coordinates[mask, 0], coordinates[mask, 1], s=24,
                        color=str(.08 + .8 * index / max(1, len(values) - 1)), edgecolors="black", linewidths=.25,
                        marker=["o", "s", "^", "D", "v", "P", "X", "*"][index % 8],
                        label=value.split(" / ")[-1] if side == 0 else f"군집 {value}")
                axes[side].set(xlabel="주성분 1", ylabel="주성분 2", title="실제 분류" if side == 0 else "전체 데이터 군집")
                axes[side].legend(fontsize=6.3, ncol=2)
            figure.suptitle(f"전체 {len(documents)}문항 PCA · {LEVEL_NAMES[level]} · {METHOD_NAMES[method]}\n표시용 2차원 투영 / 군집화는 {data['matrix'].shape[1]}차원")
            figure.savefig(output / "figures" / f"pca_{level}_{method}.png", dpi=180)
            plt.close(figure)


def validate(output, data, reports):
    """저장된 배정으로 지표·교차표·혼동행렬을 독립 재계산한다."""
    from ..ClusteringConfusion import build_confusion_matrix
    checks = []
    for report in reports:
        documents = report["documents"]
        ids = [row["id"] for row in documents]
        labels = sorted({row["actual_label"] for row in documents})
        assignments = [row["cluster"] for row in documents]
        actual = [row["actual_label"] for row in documents]
        predicted = [row["full_majority_label"] for row in documents]
        matrix = build_confusion_matrix(actual, predicted, labels)
        recalculated = {"ari": float(adjusted_rand_score(actual, assignments)),
                        "nmi": float(normalized_mutual_info_score(actual, assignments)),
                        "full_majority_match_rate": float(np.trace(matrix) / matrix.sum())}
        assert ids == data["full_ids"] and len(set(ids)) == len(ids), report["experiment"]
        assert int(matrix.sum()) == len(ids), report["experiment"]
        for key, value in recalculated.items():
            assert math.isclose(value, report["metrics"][key], abs_tol=1e-12), (report["experiment"], key)
        checks.append({"experiment": report["experiment"], "n": len(ids), "k": report["k"],
                       "recalculated_metrics_match": True, "confusion_total": int(matrix.sum()),
                       "confusion_diagonal": int(np.trace(matrix)), "fit_and_evaluate_scope": "same_all_documents"})
    result = {"passed": True, "experiments": checks, "n": len(data["full_ids"]),
              "dimensions": data["matrix"].shape[1], "data_identity": data["identity"],
              "existing_split_preserved_as_provenance": {part: len(ids) for part, ids in data["ids"].items()},
              "labels_excluded_from_fit_features": True, "test_generalization_claim": False}
    write_json(output / "validation.json", result)
    return result


def run(root=ROOT, output=OUTPUT, *, seeds=SEEDS, max_iter=MAX_ITER, tolerance=TOLERANCE,
        expected_count=265, expected_dimensions=346, make_figures=True):
    """새 경로에서만 학습한다. 완료 체크포인트는 검증 후 재사용한다."""
    root, output = Path(root).resolve(), Path(output).resolve()
    if output == root / "results/final_experiment/01_clustering":
        raise ValueError("기존 분리 실험 폴더에는 저장할 수 없습니다.")
    torch.set_num_threads(2)
    data = dataset(root, expected_count=expected_count, expected_dimensions=expected_dimensions)
    labels_by_level = {level: [hierarchy_label(data["records"][identifier], level) for identifier in data["full_ids"]]
                       for level in LEVELS}
    config = {"experiment": "full_dataset_bow_structure_v1", "fit_scope": "all", "evaluation_scope": "same_all_documents",
        "generation_id": data["generation_id"], "data_identity": data["identity"], "input_hashes": input_hashes(root),
        "full_ids": data["full_ids"], "original_splits": data["ids"],
        "n": len(data["full_ids"]), "input_dimensions": data["matrix"].shape[1],
        "vocabulary_source": "existing training-only vocabulary; no refitting or new tokenization",
        "vocabulary": data["vocabularies"]["problems"], "seeds": list(seeds), "initialization_restarts": len(seeds),
        "max_iter": max_iter, "tolerance": tolerance, "k": {level: len(set(labels)) for level, labels in labels_by_level.items()},
        "selection": {"euclidean": "minimum inertia on all input vectors", "spherical": "minimum cosine_loss on all input vectors"},
        "labels_used_for_center_fitting": False, "majority_scope": "all; descriptive resubstitution only",
        "torch_version": str(torch.__version__), "make_figures": make_figures,
        "algorithm_sources": {"mathhint_learning/TorchKMeans.py": sha256(Path(__file__).resolve().parents[1] / "TorchKMeans.py")},
        "execution_sources": {name: sha256(path) for name, path in {
            "mathhint_learning/full_dataset_265/run.py": Path(__file__).resolve(),
            "mathhint_learning/full_dataset_265/reporting.py": Path(__file__).with_name("reporting.py"),
            "mathhint_learning/ClusterReport.py": Path(__file__).resolve().parents[1] / "ClusterReport.py",
            "mathhint_learning/ClusteringConfusion.py": Path(__file__).resolve().parents[1] / "ClusteringConfusion.py",
        }.items()}}
    if expected_count == 265 and config["k"] != {"curriculum": 2, "unit": 8, "subunit": 25, "type": 70}:
        raise ValueError(f"전체 데이터의 실제 계층 분류 수가 기존 연구와 다릅니다: {config['k']}")
    signature = hashlib.sha256(json.dumps(config, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    output.mkdir(parents=True, exist_ok=True)
    manifest_path = output / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        if manifest.get("config_sha256") != signature:
            raise ValueError("전체 데이터 실험 입력/설정이 다릅니다. 별도 폴더를 사용하세요.")
        if not all((output / path).is_file() and sha256(output / path) == value for path, value in manifest["files"].items()):
            raise ValueError("완료된 전체 데이터 산출물의 무결성이 다릅니다. 덮어쓰지 않습니다.")
        print("전체 데이터 완료 결과 재사용:", output, flush=True)
        return json.loads((output / "metrics.json").read_text())
    if (output / "config.json").exists():
        if json.loads((output / "config.json").read_text()) != config:
            raise ValueError("중간 체크포인트의 입력/설정이 다릅니다.")
    elif any(output.iterdir()):
        raise ValueError("출처를 확인할 수 없는 파일이 있어 덮어쓰지 않습니다.")
    write_json(output / "config.json", config)
    (output / "figures").mkdir(exist_ok=True)
    inventory = {level: {"fields": list(LEVELS[level]), "k": config["k"][level], "labels": sorted(set(values))}
                 for level, values in labels_by_level.items()}
    write_json(output / "label_inventory.json", inventory)
    write_csv(output / "label_counts.csv", [{"level": level, "label_code": f"L{i + 1:02d}", "actual_label": label,
              "all_count": Counter(values)[label]} for level, values in labels_by_level.items() for i, label in enumerate(sorted(set(values)))])
    reports = []
    for level, actual in labels_by_level.items():
        labels, k = inventory[level]["labels"], config["k"][level]
        for method in METHOD_NAMES:
            experiment = f"{level}_{method}"
            target = output / "experiments" / experiment
            target.mkdir(parents=True, exist_ok=True)
            checkpoint_path = target / "experiment.json"
            if checkpoint_path.exists():
                report = json.loads(checkpoint_path.read_text())
                if report["config_sha256"] != signature or not all(sha256(target / path) == h for path, h in report["artifact_hashes"].items()):
                    raise ValueError(f"전체 실험 체크포인트가 다릅니다: {target}")
                print("완료 전체 군집 재사용:", experiment, flush=True)
            else:
                if any(target.iterdir()):
                    raise ValueError(f"미완료 실험 폴더에 출처 불명 파일이 있습니다: {target}")
                fit = fit_kmeans if method == "euclidean" else fit_spherical_kmeans
                objective = "inertia" if method == "euclidean" else "cosine_loss"
                trials = [fit(data["matrix"], k, max_iter, tolerance, seed) for seed in seeds]
                best = min(range(len(trials)), key=lambda i: trials[i][objective])
                fitted = trials[best]
                assignments = fitted["assignments"].tolist()
                majorities = majority_labels(assignments, actual)
                documents = [{"experiment": experiment, "level": level, "method": method,
                    "id": identifier, "original_split": data["original_split"][identifier], "cluster": cluster,
                    "actual_label": label, "full_majority_label": majorities.get(cluster),
                    "matches_full_majority": label == majorities.get(cluster),
                    **{field: data["records"][identifier].get(field, "") for field in
                       ("subject", "curriculum", "unit", "subunit", "type", "source", "source_file", "original_number", "current_number")},
                    "problem_path": f"data/processed/problems/{identifier}.txt", "annotated_path": f"data/processed/annotated/{identifier}.txt"}
                    for identifier, cluster, label in zip(data["full_ids"], assignments, actual)]
                torch.save({"experiment": experiment, "config_sha256": signature, "centers": fitted["centers"],
                    "assignments": fitted["assignments"], "fit_ids": data["full_ids"], "fit_scope": "all",
                    "input_vocabulary": data["vocabularies"]["problems"], "data_identity": data["identity"],
                    "original_splits": data["ids"], "method": method, "k": k}, target / "model.pt")
                counts, codes, distribution, dispersion = count_artifacts(target, documents, labels, k)
                metrics = {"ari": float(adjusted_rand_score(actual, assignments)),
                    "nmi": float(normalized_mutual_info_score(actual, assignments)),
                    "full_majority_match_rate": sum(row["matches_full_majority"] for row in documents) / len(documents),
                    "n": len(documents), "occupied_clusters": len(set(assignments)),
                    "cluster_sizes": {str(cluster): assignments.count(cluster) for cluster in range(k)}}
                if make_figures:
                    (target / "figures").mkdir(exist_ok=True)
                    scope_names = {"all": f"전체 {len(documents)}문항 · 동일 데이터 설명"}
                    prefix = f"{LEVEL_NAMES[level]} · {METHOD_NAMES[method]} · "
                    plot_final_cross_tabs(target / "figures", {"all": counts}, labels, codes, k,
                                          scope_names=scope_names, title_prefix=prefix)
                    plot_final_composition(target / "figures", {"all": counts}, labels, codes, k,
                                           source_part="all", scope_names=scope_names, title_prefix=prefix)
                reading_documents(root, output, target, documents, labels, k)
                report = {"experiment": experiment, "level": level, "method": method, "k": k,
                    "config_sha256": signature, "fit_scope": "all", "evaluation_scope": "same_all_documents",
                    "selected_seed": seeds[best], "training_objective_name": objective,
                    "selected_training_objective": fitted[objective],
                    "restarts": [{"seed": seed, "training_objective": trial[objective], "iterations": trial["iterations"]}
                                 for seed, trial in zip(seeds, trials)], "metrics": metrics,
                    "documents": documents, "distribution": distribution, "dispersion": dispersion}
                report["artifact_hashes"] = {path.relative_to(target).as_posix(): sha256(path) for path in target.rglob("*") if path.is_file()}
                write_json(checkpoint_path, report)
                print("전체 군집 저장:", experiment, metrics, flush=True)
            reports.append(report)
    summaries = [{"experiment": report["experiment"], "level": report["level"], "level_name": LEVEL_NAMES[report["level"]],
                  "method": report["method"], "method_name": METHOD_NAMES[report["method"]], "k": report["k"],
                  **{key: report["metrics"][key] for key in ("n", "ari", "nmi", "full_majority_match_rate", "occupied_clusters")},
                  "selected_seed": report["selected_seed"], "selected_training_objective": report["selected_training_objective"]}
                 for report in reports]
    members = [row for report in reports for row in report["documents"]]
    distributions = [row for report in reports for row in report["distribution"]]
    dispersion = [row for report in reports for row in report["dispersion"]]
    write_csv(output / "summary.csv", summaries)
    write_csv(output / "cluster_members.csv", members)
    write_csv(output / "cluster_label_distribution.csv", distributions)
    write_csv(output / "label_dispersion.csv", dispersion)
    from ..ClusteringConfusion import build_confusion_matrix, plot_confusion_matrix
    for level in LEVELS:
        level_reports = [report for report in reports if report["level"] == level]
        labels = inventory[level]["labels"]
        matrices = {report["method"]: build_confusion_matrix(
            [row["actual_label"] for row in report["documents"]],
            [row["full_majority_label"] for row in report["documents"]], labels) for report in level_reports}
        maximum = max(int(matrix.max()) for matrix in matrices.values())
        for report in level_reports:
            target = output / "experiments" / report["experiment"]
            codes = [f"L{i + 1:02d}" for i in range(len(labels))]
            matrix = matrices[report["method"]]
            write_csv(target / "confusion_matrix_all.csv", [{"label_code": codes[i], "actual_label": label,
                **{code: int(matrix[i, j]) for j, code in enumerate(codes)}} for i, label in enumerate(labels)])
            if make_figures:
                plot_confusion_matrix(target / "figures/confusion_matrix_all.png", matrix, labels, codes,
                    experiment=report["experiment"], level=level, method=report["method"],
                    n=len(data["full_ids"]), k=report["k"], scope="all", vmax=maximum)
            report["artifact_hashes"] = {path.relative_to(target).as_posix(): sha256(path)
                for path in target.rglob("*") if path.is_file() and path.name != "experiment.json"}
            write_json(target / "experiment.json", report)
    if make_figures:
        save_pca(output, data, reports)
    from .reporting import report_results
    report_results(root, output, summaries, members, dispersion)
    validate(output, data, reports)
    result = {"config_sha256": signature, "summaries": summaries, "experiments": reports,
              "fit_scope": "all", "evaluation_scope": "same_all_documents"}
    write_json(output / "metrics.json", result)
    files = {path.relative_to(output).as_posix(): sha256(path) for path in output.rglob("*")
             if path.is_file() and path.name != "manifest.json"}
    write_json(manifest_path, {"config_sha256": signature, "files": files})
    return result
