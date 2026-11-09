"""고정 학습/테스트 분할로 4단계 × 2거리 군집화 실험을 저장한다.

실행: python -m mathhint_learning.holdout
기존 명령 python -m mathhint_learning.FinalClustering도 같은 구현을 실행한다.
같은 입력·설정의 완료된 실험은 파일 해시를 검증한 뒤 재사용한다.
"""

from collections import Counter
import csv
import hashlib
import json
import os
from pathlib import Path

import torch
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score

from ..TorchData import load_fixed_dataset, write_json
from ..TorchKMeans import (assign_clusters, assign_spherical, fit_kmeans,
                         fit_spherical_kmeans, l2_normalize)
from ..ClusterReport import save_final_cluster_reports, plot_final_comparison, save_pca_views

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "results/final_experiment/01_clustering"
LEVELS = {"curriculum": ("curriculum",), "unit": ("curriculum", "unit"),
          "subunit": ("curriculum", "unit", "subunit"),
          "type": ("curriculum", "unit", "subunit", "type")}
LEVEL_NAMES = {"curriculum": "과목", "unit": "단원", "subunit": "세부단원", "type": "문제 유형"}
METHOD_NAMES = {"euclidean": "유클리드", "spherical": "코사인(구면)"}
SEEDS = [42, 43, 44, 45, 46]
MAX_ITER = 100
TOLERANCE = .0001


def hierarchy_label(record, level):
    """과목은 curriculum이다. subject(미분/삼각함수 자료군)와 구분한다."""
    values = [record[field] for field in LEVELS[level]]
    if any(not value for value in values):
        raise ValueError(f"문항 {record['id']}의 {level} 경로가 비었습니다.")
    return " / ".join(values)


def write_csv(path, rows, fields=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fields or list(rows[0])
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def majority_labels(assignments, labels):
    groups = {}
    for cluster, label in zip(assignments, labels):
        groups.setdefault(cluster, Counter())[label] += 1
    # 동률도 테스트를 보지 않고 라벨 문자열 순서로 결정한다.
    return {cluster: sorted(counts, key=lambda label: (-counts[label], label))[0]
            for cluster, counts in groups.items()}


def evaluate_assignments(assignments, labels, training_majorities, k):
    predictions = [training_majorities.get(cluster) for cluster in assignments]
    counts = Counter(assignments)
    return {"ari": float(adjusted_rand_score(labels, assignments)),
            "nmi": float(normalized_mutual_info_score(labels, assignments)),
            "train_majority_accuracy": sum(a == b for a, b in zip(predictions, labels)) / len(labels),
            "occupied_clusters": len(counts), "n": len(labels),
            "cluster_sizes": {str(i): counts[i] for i in range(k)}}


def input_hashes(root, data_root=None):
    root = Path(root)
    selected = Path(data_root).resolve() if data_root is not None else root / "data"
    paths = ["data/processed/metadata.json", "data/processed/splits/train.json", "data/processed/splits/test.json",
             "data/vectors/problems/vocabulary.json", "data/vectors/problems/train_vectors.json",
             "data/vectors/problems/test_vectors.json"]
    return {path: sha256(selected / Path(path).relative_to("data")) for path in paths}


def run(root=ROOT, output=OUTPUT, seeds=SEEDS, max_iter=MAX_ITER, tolerance=TOLERANCE, *, data_root=None):
    root, output = Path(root), Path(output)
    selected_data = Path(data_root).resolve() if data_root is not None else (root / "data").resolve()
    torch.set_num_threads(2)
    data = load_fixed_dataset(root, data_root=selected_data)
    ids, records, matrices = data["ids"], data["records"], data["arrays"]["problems"]
    output.mkdir(parents=True, exist_ok=True)
    config = {"experiment": "four_hierarchy_euclidean_vs_spherical_v1",
              "generation_id": data["generation_id"], "input_hashes": input_hashes(root, selected_data),
              "seeds": list(seeds), "max_iter": max_iter, "tolerance": tolerance,
              "levels": {key: list(value) for key, value in LEVELS.items()},
              "fit_split": "train", "majority_label_split": "train",
              "training_count": len(ids["train"]), "test_count": len(ids["test"]),
              "input_vocabulary_size": len(data["vocabularies"]["problems"]),
              "test_used_to_select_parameters": False,
              "initialization": "same sorted unique raw rows and torch.randperm(seed) for both methods",
              "selection": {"euclidean": "minimum training squared Euclidean distance sum",
                            "spherical": "minimum training sum(1-cosine similarity)"},
              "transforms": {"euclidean": "raw counts, arithmetic mean centers",
                             "spherical": "L2-normalized rows, normalized sum/mean centers after every update"},
              "zero_vector_policy": "L2 zero remains zero; all cosine similarities=0; ties choose lowest cluster ID",
              "empty_cluster_policy": "reinitialize from training row farthest from its nearest center; spherical uses nonzero rows",
              "label_majority_tie_rule": "label ascending lexical order",
              "source_subject_warning": "subject is the source group, not course; actual course uses curriculum",
              "torch_version": str(torch.__version__)}
    if selected_data != (root / "data").resolve():
        config["data_source"] = {"data_root": str(selected_data), "paths_are_provenance": True}
    print("군집 입력 데이터:", selected_data, "· 결과:", output, flush=True)
    # 이동한 폴더의 위치만으로 같은 입력 바이트의 완료 모델을 다시 학습하지 않는다.
    config_identity = {key: value for key, value in config.items() if key != "data_source"}
    config_hash = hashlib.sha256(json.dumps(config_identity, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    manifest_path = output / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        if manifest.get("config_sha256") != config_hash:
            previous = json.loads((output / "config.json").read_text()) if (output / "config.json").exists() else {}
            changed = next((name for name, value in config["input_hashes"].items()
                            if previous.get("input_hashes", {}).get(name) != value), None)
            detail = f" 입력 파일: {selected_data / Path(changed).relative_to('data')}" if changed else ""
            raise ValueError("기존 군집화 결과의 설정 또는 입력이 다릅니다. 새 실험 폴더를 지정하세요." + detail)
        if all((output / name).exists() and sha256(output / name) == value
               for name, value in manifest["files"].items()):
            print("군집화 완료 결과 재사용: 해시 검증 통과", output)
            return json.loads((output / "metrics.json").read_text())
        raise ValueError("완료 결과가 누락되거나 변형되었습니다. 덮어쓰지 않고 중단합니다.")
    if any(output.iterdir()) and not (output / "config.json").exists():
        raise ValueError("출처가 불명확한 기존 파일이 있어 결과를 덮어쓰지 않습니다.")
    if (output / "config.json").exists():
        previous = json.loads((output / "config.json").read_text())
        if {key: value for key, value in previous.items() if key != "data_source"} != config_identity:
            raise ValueError("미완료 결과의 입력/설정이 다릅니다. 새 폴더를 쓰세요.")
    write_json(output / "config.json", config)
    label_inventory, label_counts = {}, []
    for level in LEVELS:
        by_split = {part: [hierarchy_label(records[identifier], level) for identifier in ids[part]]
                    for part in ("train", "test")}
        all_counts = Counter(by_split["train"] + by_split["test"])
        train_counts, test_counts = Counter(by_split["train"]), Counter(by_split["test"])
        label_inventory[level] = {"fields": list(LEVELS[level]), "k": len(train_counts),
                                  "all_unique": len(all_counts), "train_unique": len(train_counts),
                                  "test_unique": len(test_counts), "labels": sorted(all_counts),
                                  "test_only_labels": sorted(set(test_counts) - set(train_counts))}
        for index, label in enumerate(sorted(all_counts)):
            label_counts.append({"level": level, "label_code": f"L{index + 1:02d}", "label": label,
                                 "all_count": all_counts[label], "train_count": train_counts[label],
                                 "test_count": test_counts[label], "k_from_training_labels": len(train_counts)})
    write_json(output / "label_inventory.json", label_inventory)
    write_csv(output / "label_counts.csv", label_counts)

    summaries, experiment_reports = [], []
    all_members, all_cluster_labels, all_dispersion = [], [], []
    for level in LEVELS:
        labels = {part: [hierarchy_label(records[identifier], level) for identifier in ids[part]]
                  for part in ("train", "test")}
        k = label_inventory[level]["k"]
        for method in METHOD_NAMES:
            experiment_id = f"{level}_{method}"
            target = output / "experiments" / experiment_id
            target.mkdir(parents=True, exist_ok=True)
            completed = target / "experiment.json"
            # Checkpoint each experiment so interrupted runs do not retrain finished fits.
            if completed.exists():
                report = json.loads(completed.read_text())
                if report.get("config_sha256") != config_hash:
                    raise ValueError("군집화 체크포인트의 설정 해시가 다릅니다.")
                if not all((target / p).exists() and sha256(target / p) == h
                           for p, h in report["artifact_hashes"].items()):
                    raise ValueError("군집화 체크포인트가 변형되었습니다.")
                members = report["documents"]
                print("완료 군집 재사용:", experiment_id, flush=True)
            else:
                fit = fit_kmeans if method == "euclidean" else fit_spherical_kmeans
                assign = assign_clusters if method == "euclidean" else assign_spherical
                objective = "inertia" if method == "euclidean" else "cosine_loss"
                trials = [fit(matrices["train"], k, max_iter, tolerance, seed) for seed in seeds]
                best = min(range(len(trials)), key=lambda i: trials[i][objective])
                fitted = trials[best]
                assignments = {"train": fitted["assignments"].tolist(),
                               "test": assign(matrices["test"], fitted["centers"]).tolist()}
                majorities = majority_labels(assignments["train"], labels["train"])
                members = []
                for part in ("train", "test"):
                    for identifier, cluster, label in zip(ids[part], assignments[part], labels[part]):
                        record = records[identifier]
                        members.append({"experiment": experiment_id, "level": level, "method": method,
                                        "id": identifier, "split": part, "cluster": cluster,
                                        "actual_label": label, "train_majority_label": majorities.get(cluster),
                                        "matches_train_majority": label == majorities.get(cluster),
                                        **{field: record.get(field, "") for field in ("subject", "curriculum", "unit", "subunit", "type", "source", "source_file", "original_number", "current_number")},
                                        "problem_path": Path(os.path.relpath(selected_data / f"processed/problems/{identifier}.txt", root)).as_posix(),
                                        "annotated_path": Path(os.path.relpath(selected_data / f"processed/annotated/{identifier}.txt", root)).as_posix()})
                report = {"config_sha256": config_hash, "experiment": experiment_id,
                          "level": level, "method": method, "k": k,
                          "selected_seed": seeds[best], "training_objective_name": objective,
                          "selected_training_objective": fitted[objective],
                          "restarts": [{"seed": seed, "training_objective": trial[objective], "iterations": trial["iterations"]}
                                       for seed, trial in zip(seeds, trials)],
                          "metrics": {part: evaluate_assignments(assignments[part], labels[part], majorities, k)
                                      for part in ("train", "test")},
                          "train_majority_labels": majorities, "documents": members}
                torch.save({"centers": fitted["centers"], "method": method, "level": level,
                            "training_ids": ids["train"], "generation_id": data["generation_id"],
                            "vocabulary": data["vocabularies"]["problems"], "config_sha256": config_hash}, target / "model.pt")
                distribution, dispersion = save_final_cluster_reports(root, output, target, members, k,
                                                                       label_inventory[level]["labels"], data_root=selected_data)
                write_json(target / "cluster_label_distribution.json", distribution)
                write_json(target / "label_dispersion.json", dispersion)
                report["artifact_hashes"] = {p.relative_to(target).as_posix(): sha256(p)
                                             for p in target.rglob("*") if p.is_file()}
                write_json(completed, report)
                print(f"{experiment_id}: k={k}, selected seed={seeds[best]}, test ARI={report['metrics']['test']['ari']:.4f}", flush=True)
            distribution = json.loads((target / "cluster_label_distribution.json").read_text())
            dispersion = json.loads((target / "label_dispersion.json").read_text())
            all_members.extend(members)
            all_cluster_labels.extend(distribution)
            all_dispersion.extend(dispersion)
            experiment_reports.append(report)
            for part in ("train", "test"):
                summaries.append({"experiment": experiment_id, "level": level, "level_name": LEVEL_NAMES[level],
                                  "method": method, "method_name": METHOD_NAMES[method], "split": part,
                                  "k": k, "all_label_count": label_inventory[level]["all_unique"],
                                  "train_label_count": label_inventory[level]["train_unique"],
                                  "test_label_count": label_inventory[level]["test_unique"],
                                  **{name: value for name, value in report["metrics"][part].items() if name != "cluster_sizes"},
                                  "selected_seed": report["selected_seed"],
                                  "training_objective_name": report["training_objective_name"],
                                  "selected_training_objective": report["selected_training_objective"]})
    write_csv(output / "summary.csv", summaries)
    write_csv(output / "cluster_members.csv", all_members)
    write_csv(output / "cluster_label_distribution.csv", all_cluster_labels)
    write_csv(output / "label_dispersion.csv", all_dispersion)
    write_json(output / "metrics.json", {"config": config, "label_inventory": label_inventory,
                                        "experiments": experiment_reports})
    plot_final_comparison(output, summaries)
    save_pca_views(output, matrices, ids, records, experiment_reports)
    save_analysis(output, summaries, all_members, all_dispersion, project_root=root, data_root=selected_data)
    validate_saved_results(root, output, data_root=selected_data)
    files = {path.relative_to(output).as_posix(): sha256(path)
             for path in output.rglob("*") if path.is_file() and path.name != "manifest.json"}
    write_json(manifest_path, {"config_sha256": config_hash, "files": files})
    print("군집화 결과 완료:", output, flush=True)
    return json.loads((output / "metrics.json").read_text())


def validate_saved_results(root, output, *, data_root=None):
    """저장된 중심으로 재배정하고 학습 다수 라벨·교차표·기존 중심을 대조한다."""
    root, output = Path(root), Path(output)
    data = load_fixed_dataset(root, data_root=data_root)
    metrics = json.loads((output / "metrics.json").read_text())
    for name, actual in input_hashes(root, data["data_root"]).items():
        if metrics["config"]["input_hashes"].get(name) != actual:
            path = Path(data["data_root"]) / Path(name).relative_to("data")
            raise ValueError(f"{path}: 저장된 군집 모델과 입력 데이터가 다릅니다.")
    reports = metrics["experiments"]
    checks = []
    legacy = []
    for report in reports:
        folder = output / "experiments" / report["experiment"]
        saved = torch.load(folder / "model.pt", weights_only=True)
        if (saved.get("vocabulary") != data["vocabularies"]["problems"]
                or saved.get("training_ids") != data["ids"]["train"]
                or saved.get("generation_id") != data["generation_id"]
                or saved.get("config_sha256") != report["config_sha256"]):
            raise ValueError(f"{folder / 'model.pt'}: 어휘 순서·학습 ID·데이터 버전 또는 설정이 입력과 다릅니다.")
        k = report["k"]
        if list(saved["centers"].shape) != [k, len(data["vocabularies"]["problems"])]:
            raise ValueError("저장된 군집 중심 차원이 다릅니다.")
        if report["method"] == "spherical":
            norms = torch.linalg.vector_norm(saved["centers"], dim=1)
            if not torch.allclose(norms, torch.ones(k), atol=1e-5):
                raise ValueError("실제 데이터의 구면 중심이 단위벡터가 아닙니다.")
        assign = assign_clusters if report["method"] == "euclidean" else assign_spherical
        train_members = [row for row in report["documents"] if row["split"] == "train"]
        for cluster in range(k):
            actual_counts = Counter(row["actual_label"] for row in train_members if row["cluster"] == cluster)
            expected = sorted(actual_counts, key=lambda label: (-actual_counts[label], label))[0] if actual_counts else None
            if report["train_majority_labels"].get(str(cluster)) != expected:
                raise ValueError("군집 대표 라벨이 학습 문항의 다수와 다릅니다.")
        for part in ("train", "test"):
            members = [row for row in report["documents"] if row["split"] == part]
            if [row["id"] for row in members] != data["ids"][part]:
                raise ValueError("문항 ID 순서가 다릅니다.")
            if assign(data["arrays"]["problems"][part], saved["centers"]).tolist() != [row["cluster"] for row in members]:
                raise ValueError("저장된 중심과 문항 배정이 다릅니다.")
            with (folder / f"cross_tab_{part}.csv").open(encoding="utf-8-sig") as stream:
                cross = list(csv.DictReader(stream))
            frequencies = Counter((row["actual_label"], row["cluster"]) for row in members)
            if any(int(row[f"cluster_{cluster:02d}"]) != frequencies[(row["actual_label"], cluster)]
                   for row in cross for cluster in range(k)):
                raise ValueError("교차표가 실제 배정과 다릅니다.")
        checks.append({"experiment": report["experiment"], "model_reassignment_matches": True,
                       "training_only_majority_matches": True, "cross_tables_match_members": True})
        old_path = root / f"results/model_comparison_2026-11-07/models/kmeans_k{k}_model.pt"
        if report["method"] == "euclidean" and old_path.exists() and Path(data["data_root"]).resolve() == (root / "data").resolve():
            old = torch.load(old_path, weights_only=True)
            legacy.append({"experiment": report["experiment"], "legacy_model_path": old_path.relative_to(root).as_posix(),
                           "legacy_model_sha256": sha256(old_path),
                           "same_generation": old["generation_id"] == data["generation_id"],
                           "same_train_ids": old["train_ids"] == data["ids"]["train"],
                           "same_vocabulary": old["vocabulary"] == data["vocabularies"]["problems"],
                           "centers_exactly_equal": bool(torch.equal(old["centers"], saved["centers"])),
                           "reused_without_refitting_in_this_execution": False})
    note = ("유클리드 k=2/8/70은 새 구면 비교 구현의 공통 조건을 확인하는 검증 실행에서 재계산했다. 기존 중심과의 정확 일치 여부를 기록하며 단순 재사용으로 보고하지 않는다. 완료 후 동일 설정 재실행은 manifest 해시를 검사해 재학습 없이 반환한다."
            if legacy else "선택한 데이터에 대해 호환되는 과거 군집 모델을 비교하지 않았다. 저장한 중심·배정·학습 대표 라벨·교차표를 검증했다.")
    result = {"checks": checks, "legacy_model_equivalence": legacy, "legacy_note": note}
    write_json(output / "validation.json", result)
    return result


def save_analysis(output, summaries, members, dispersion, *, project_root=ROOT, data_root=None, reader_path=None):
    from ..ClusterReport import cluster_problem_links
    output = Path(output)
    train_n = len({row["id"] for row in members if row["split"] == "train"})
    test_n = len({row["id"] for row in members if row["split"] == "test"})
    def problem_link(row):
        return cluster_problem_links(project_root, output, output, row["id"],
                                     data_root=data_root, reader_path=reader_path)
    rows = [row for row in summaries if row["split"] == "test"]
    type_k = next((row["k"] for row in rows if row["level"] == "type"), "확인한")
    config_path = output / "config.json"
    config = json.loads(config_path.read_text()) if config_path.exists() else {}
    dimension = config.get("input_vocabulary_size", "저장된 고차원")
    seed_n = len(config.get("seeds", SEEDS))
    lines = ["# 유클리드·코사인 군집화 비교", "", f"학습 {train_n}문항에서 중심과 군집의 대표 라벨을 만들고 고정 테스트 {test_n}문항에 적용했다. 과목은 curriculum을 사용하며 subject는 자료군이다.", "",
             "[문항별 군집 배정](cluster_members.csv) · [군집별 라벨 비율](cluster_label_distribution.csv) · [실제 라벨의 분산도](label_dispersion.csv) · [분류 수](label_counts.csv)", "",
             "ARI는 우연 일치를 보정한 군집 일치도, NMI는 분류와 군집이 공유하는 정보다. 다수 라벨 정확도는 학습 군집의 대표 라벨로 테스트 분류를 맞힌 비율이다.", "",
             "| 분류 | 거리 | k | ARI | NMI | 학습 다수 라벨 정확도 | 점유 군집 |", "|---|---|---:|---:|---:|---:|---:|"]
    for row in rows:
        lines.append(f"| {row['level_name']} | {row['method_name']} | {row['k']} | {row['ari']:.4f} | {row['nmi']:.4f} | {row['train_majority_accuracy']:.1%} | {row['occupied_clusters']} |")
    lines += ["", "## 수치에서 확인한 사실", ""]
    for level in LEVELS:
        a, b = [next(r for r in rows if r["level"] == level and r["method"] == method) for method in METHOD_NAMES]
        lines.append(f"- {LEVEL_NAMES[level]} 테스트 ARI는 유클리드 {a['ari']:.4f}, 구면 {b['ari']:.4f}; NMI는 {a['nmi']:.4f}, {b['nmi']:.4f}다.")
    lines += ["", "## 해석과 한계", "", "원시 빈도와 유클리드 거리는 문서 길이·전체 등장 횟수의 영향을 받을 수 있다. 구면 방식은 방향을 비교하므로 길이 영향을 줄이지만, 이번 비교 하나로 모든 차이의 원인을 길이로 확정할 수 없다.",
              f"유형 {type_k}개에 학습 {train_n}문항이다. 작은 군집과 k가 커질 때 NMI가 높아지는 경향, 테스트에 나타나지 않은 라벨을 함께 고려해야 한다. 학습·테스트 점수 차이도 확인해야 한다.",
              f"{seed_n}개 시드 중 각 방법의 학습 목적함수로만 결과를 선택했다. 두 방법의 목적함수 값은 단위와 의미가 다르므로 서로 비교하지 않는다. 테스트 지표로 시드나 k를 선택하지 않았다.",
              "기존 테스트 성능을 관찰한 뒤 설계한 후속 비교이며, 전혀 보지 않은 독립 최종 평가로 주장하지 않는다.", "",
              "## 직접 확인할 성공·혼합·분산 사례", "", "사례는 결과를 읽기 위한 기술적 예시이며 통계적 일반화를 위한 별도 표본이 아니다.", ""]
    for level in ("subunit", "type"):
        for method in METHOD_NAMES:
            relevant = [r for r in members if r["method"] == method and r["level"] == level]
            training = [r for r in relevant if r["split"] == "train"]
            group_counts = Counter((r["cluster"], r["actual_label"]) for r in training)
            cluster_n = Counter(r["cluster"] for r in training)
            successes = sorted([r for r in relevant if r["split"] == "test" and r["matches_train_majority"]],
                               key=lambda r: (-group_counts[(r["cluster"], r["actual_label"])] / cluster_n[r["cluster"]], r["id"]))
            failures = sorted([r for r in relevant if r["split"] == "test" and not r["matches_train_majority"]], key=lambda r: r["id"])
            lines += [f"### {METHOD_NAMES[method]} · {LEVEL_NAMES[level]}", "",
                      f"[이 실험의 군집 문항·그림](experiments/{level}_{method}/README.md)", ""]
            if successes:
                row = successes[0]
                lines += [f"- 학습 다수 라벨과 일치: {problem_link(row)} · 군집 {row['cluster']} · 실제 `{row['actual_label']}`. 학습 내 같은 라벨은 {group_counts[(row['cluster'], row['actual_label'])]}/{cluster_n[row['cluster']]}문항이다. 이 사례가 전체 유형의 완전 분리를 뜻하지는 않는다."]
            if failures:
                row = failures[0]
                other = next((r for r in training if r["cluster"] == row["cluster"] and r["actual_label"] == row["train_majority_label"]), None)
                lines += [f"- 서로 다른 라벨이 같은 군집: {problem_link(row)} · 실제 `{row['actual_label']}` · 군집 {row['cluster']}의 학습 다수 `{row['train_majority_label']}`."]
                if other:
                    lines += [f"  같은 군집의 학습 문항 {problem_link(other)}의 실제 라벨은 `{other['actual_label']}`이다. 대표 라벨은 테스트 문항을 보지 않고 학습에서 정했다."]
            ds = [r for r in dispersion if r["level"] == level and r["method"] == method and r["split"] == "train"]
            dispersed = sorted(ds, key=lambda r: (-r["occupied_clusters"], -r["n"], r["actual_label"]))[0]
            matches = [r for r in training if r["actual_label"] == dispersed["actual_label"]]
            examples = ", ".join(f"{problem_link(r)}→{r['cluster']}" for r in matches[:8])
            remainder = f" 외 {len(matches) - 8}문항" if len(matches) > 8 else ""
            lines += [f"- 같은 라벨이 여러 군집으로 분산: `{dispersed['actual_label']}` 학습 {dispersed['n']}문항이 {dispersed['occupied_clusters']}군집으로 나뉨. 예: {examples}{remainder}. 전체 ID와 군집은 [문항별 배정](cluster_members.csv), 분산 수치는 [분산도 표](label_dispersion.csv)에서 이 라벨로 확인한다.", ""]
    (output / "analysis.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    readme = ["# 군집화 결과", "", "먼저 [전체 비교표](summary.csv)와 [해석·사례](analysis.md)를 보고, [문항별 군집 배정](cluster_members.csv)을 실험명·군집 번호로 필터링하세요.", "",
              "문항 목록의 ID는 수식·Markdown 읽기 화면으로 연결됩니다. 학습 문항은 생성 실험 대상 아님으로 표시하고, 저장된 원문은 별도 링크에서 확인할 수 있습니다.", "",
              "- [ARI 비교](figures/ari_comparison.png), [NMI 비교](figures/nmi_comparison.png)",
              "- [분류별 문항 수](label_counts.csv), [군집별 실제 라벨 빈도·비율](cluster_label_distribution.csv)",
              "- [동일 분류의 군집 분산도](label_dispersion.csv)", "", "| 분류 | 유클리드 | 코사인(구면) |", "|---|---|---|"]
    for level in LEVELS:
        readme.append(f"| {LEVEL_NAMES[level]} | [군집 문항·교차표·그림](experiments/{level}_euclidean/README.md) | [군집 문항·교차표·그림](experiments/{level}_spherical/README.md) |")
    readme += ["", "`config.json`은 입력 해시와 공통 설정, 각 실험의 `experiment.json`은 모든 시드의 학습 목적함수·선택 결과, `model.pt`는 중심과 학습 ID를 보존한다. `manifest.json`은 산출물 무결성 검사 목록이다.",
               f"PCA는 학습 자료에서만 맞춘 표시용 2차원 투영이다. 군집화 자체는 원래 {dimension}차원에서 수행했다. 원시 빈도와 L2 정규화 공간은 별도로 투영했으며 서로 다른 PCA 좌표를 직접 비교하지 않는다."]
    from . import preserve_navigation
    (output / "README.md").write_text(preserve_navigation(output / "README.md", "\n".join(readme) + "\n"), encoding="utf-8")


def main():
    from ..Experiment import EXPERIMENT
    return run(EXPERIMENT.project_root, EXPERIMENT.result_root / "01_clustering",
               data_root=EXPERIMENT.data_root)


if __name__ == "__main__":
    main()
