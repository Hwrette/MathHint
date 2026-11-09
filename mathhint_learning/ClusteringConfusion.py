"""저장된 군집 대표 라벨로 혼동행렬을 그린다. 학습·군집 배정은 실행하지 않는다.

실행: python -m mathhint_learning.ClusteringConfusion
기존 학습/테스트 실험에는 학습 문항으로 정한 대표 라벨만 사용한다.
"""

from collections import Counter, defaultdict
import csv
import json
from pathlib import Path

import numpy as np

from .ClusterReport import setup_final_plots

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "results/final_experiment/01_clustering"
LEVEL_NAMES = {"curriculum": "과목", "unit": "단원", "subunit": "세부단원", "type": "문제 유형"}
METHOD_NAMES = {"euclidean": "유클리드 K-means", "spherical": "코사인 Spherical K-means"}


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def build_confusion_matrix(actual, predicted, labels):
    """행=실제 분류, 열=대표 라벨 예측. 분류 경로의 내용과 순서를 유지한다."""
    actual, predicted, labels = list(actual), list(predicted), list(labels)
    if len(actual) != len(predicted) or len(labels) != len(set(labels)):
        raise ValueError("실제/예측 문항 수 또는 고유 분류 순서가 잘못됐습니다.")
    index = {label: i for i, label in enumerate(labels)}
    matrix = np.zeros((len(labels), len(labels)), dtype=np.int64)
    for observed, forecast in zip(actual, predicted):
        if observed not in index or forecast not in index:
            raise ValueError(f"기존 분류 목록에 없는 실제/예측 라벨입니다: {observed!r}, {forecast!r}")
        matrix[index[observed], index[forecast]] += 1
    return matrix


def plot_confusion_matrix(path, matrix, labels, codes, *, experiment, level, method,
                          k, scope, n=None, vmax=None):
    """두 실험에서 동일한 labels/codes/vmax를 전달해 비교 가능한 그림을 저장한다."""
    matrix = np.asarray(matrix)
    labels, codes = list(labels), list(codes)
    if (matrix.shape != (len(labels), len(labels)) or len(codes) != len(labels)
            or np.any(matrix < 0) or np.any(matrix != np.floor(matrix))):
        raise ValueError("혼동행렬은 분류 목록에 맞는 음이 아닌 정수 정방행렬이어야 합니다.")
    total = int(matrix.sum())
    if n is not None and total != n:
        raise ValueError(f"혼동행렬 합계 {total}가 표시 문항 수 {n}와 다릅니다.")
    if scope not in ("test", "all"):
        raise ValueError("scope는 test 또는 all이어야 합니다.")
    plt = setup_final_plots()
    size = len(labels)
    figure_size = (max(9, min(22, 6 + .21 * size)), max(8, min(21, 5 + .21 * size)))
    fig, ax = plt.subplots(figsize=figure_size)
    limit = max(1, int(matrix.max())) if vmax is None else max(1, vmax)
    if limit < int(matrix.max()):
        raise ValueError("공통 색상 범위가 실제 문항 수보다 작습니다.")
    image = ax.imshow(matrix, cmap="Blues", vmin=0, vmax=limit, interpolation="nearest")
    if size <= 8:
        ticks = [f"{code} · {label.split(' / ')[-1]}" for code, label in zip(codes, labels)]
    else:
        ticks = codes
    ax.set_xticks(range(size), ticks, rotation=45 if size <= 8 else 90, ha="right" if size <= 8 else "center")
    ax.set_yticks(range(size), ticks)
    ax.tick_params(axis="both", labelsize=9 if size <= 25 else 8)
    ax.set_xlabel("예측 분류 (군집 대표 라벨)", fontsize=12, labelpad=12)
    ax.set_ylabel("실제 분류", fontsize=12, labelpad=12)
    if size <= 8:
        ax.set_xticks(np.arange(-.5, size, 1), minor=True)
        ax.set_yticks(np.arange(-.5, size, 1), minor=True)
        ax.grid(which="minor", color="white", linewidth=.7)
        ax.tick_params(which="minor", bottom=False, left=False)
    for row in range(size):
        for column in range(size):
            count = int(matrix[row, column])
            if size <= 8 or count:
                ax.text(column, row, str(count), ha="center", va="center",
                        fontsize=11 if size <= 8 else (8 if size <= 25 else 7),
                        color="white" if count > limit * .55 else "black")
    colorbar = fig.colorbar(image, ax=ax, fraction=.038, pad=.025)
    colorbar.set_label("문항 수", fontsize=11)
    from matplotlib.ticker import MaxNLocator
    colorbar.locator = MaxNLocator(integer=True)
    colorbar.update_ticks()
    absent_actual = [code for code, count in zip(codes, matrix.sum(axis=1)) if not count]
    absent_predicted = [code for code, count in zip(codes, matrix.sum(axis=0)) if not count]
    scope_name = "테스트 80문항" if scope == "test" and total == 80 else (f"테스트 {total}문항" if scope == "test" else f"전체 {total}문항 · 동일 데이터 내 설명용")
    majority_note = "대표 라벨: 학습 데이터만 사용" if scope == "test" else "대표 라벨: 전체 데이터 사용 · 테스트 성능 아님"
    ax.set_title(f"{experiment} · {LEVEL_NAMES.get(level, level)} 혼동행렬\n"
                 f"{METHOD_NAMES.get(method, method)} · k={k} · {scope_name}", fontsize=14, pad=18)
    fig.text(.5, .035, f"{majority_note}\n"
             f"동일한 전체 {size}분류를 행·열에 포함 (실제 미등장 {len(absent_actual)}, 예측 미등장 {len(absent_predicted)}분류)\n"
             "라벨 코드의 전체 계층 경로: 같은 실험 폴더 label_key.csv · 빈 칸=0문항",
             ha="center", fontsize=10)
    fig.tight_layout(rect=(0, .095, 1, 1))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=220, facecolor="white")
    plt.close(fig)
    return {"n": total, "diagonal": int(np.trace(matrix)), "axis_label_count": size,
            "zero_actual_codes": absent_actual, "zero_predicted_codes": absent_predicted,
            "vmin": 0, "vmax": limit, "scope": scope}


def _holdout_matrix(target, global_members, summary):
    members = read_csv(target / "members.csv")
    key = read_csv(target / "label_key.csv")
    labels, codes = [r["actual_label"] for r in key], [r["label_code"] for r in key]
    if members != global_members:
        raise ValueError(f"{target}: 전체 문항 배정과 실험별 members.csv가 다릅니다.")
    by_cluster = defaultdict(Counter)
    for row in members:
        if row["split"] == "train":
            by_cluster[row["cluster"]][row["actual_label"]] += 1
    majorities = {cluster: min(counts, key=lambda label: (-counts[label], label))
                  for cluster, counts in by_cluster.items()}
    ids = set()
    for row in members:
        if row["split"] not in ("train", "test") or row["id"] in ids:
            raise ValueError(f"{target}: 분할 또는 중복 문항 ID가 잘못됐습니다.")
        ids.add(row["id"])
        if row["train_majority_label"] != majorities.get(row["cluster"]):
            raise ValueError(f"{target}: 학습 문항으로 다시 확인한 대표 라벨과 다릅니다: {row['id']}")
    selected = [row for row in members if row["split"] == "test"]
    matrix = build_confusion_matrix([row["actual_label"] for row in selected],
                                    [row["train_majority_label"] for row in selected], labels)
    if len(selected) != int(summary["n"]) or int(matrix.sum()) != 80:
        raise ValueError(f"{target}: 기존 테스트 문항 수와 다릅니다.")
    if abs(float(np.trace(matrix)) / len(selected) - float(summary["train_majority_accuracy"])) > 1e-12:
        raise ValueError(f"{target}: 대각선 합과 기존 학습 최빈 라벨 정확도가 다릅니다.")
    return matrix, labels, codes


def make_holdout_confusions(output=OUTPUT, *, update_readmes=True):
    """기존 CSV만 읽어 8개 테스트 혼동행렬을 추가한다. 기존 수치·배정은 쓰지 않는다."""
    output = Path(output)
    summaries = {r["experiment"]: r for r in read_csv(output / "summary.csv") if r["split"] == "test"}
    global_members = read_csv(output / "cluster_members.csv")
    prepared = {}
    for name, summary in summaries.items():
        target = output / "experiments" / name
        expected = [row for row in global_members if row["experiment"] == name]
        prepared[name] = _holdout_matrix(target, expected, summary)
    results = []
    for name, summary in summaries.items():
        matrix, labels, codes = prepared[name]
        same_level = [value[0] for exp, value in prepared.items() if summaries[exp]["level"] == summary["level"]]
        if any(value[1:] != (labels, codes) for exp, value in prepared.items() if summaries[exp]["level"] == summary["level"]):
            raise ValueError("같은 분류 수준의 두 방법에서 축 순서가 다릅니다.")
        target = output / "experiments" / name
        figure = target / "figures/confusion_matrix_test.png"
        if figure.exists():
            raise FileExistsError(f"기존 혼동행렬을 덮어쓰지 않습니다: {figure}")
        result = plot_confusion_matrix(figure, matrix, labels, codes, experiment=name,
                                      level=summary["level"], method=summary["method"],
                                      k=int(summary["k"]), scope="test", n=80,
                                      vmax=max(int(m.max()) for m in same_level))
        result.update(experiment=name, figure=figure.relative_to(output).as_posix(),
                      train_majority_accuracy=float(summary["train_majority_accuracy"]),
                      label_key=(target / "label_key.csv").relative_to(output).as_posix(),
                      labels=labels, codes=codes)
        results.append(result)
        if update_readmes:
            path = target / "README.md"
            with path.open("a", encoding="utf-8") as stream:
                stream.write("\n## 테스트 혼동행렬\n\n"
                             "[실제 분류 × 예측 분류 혼동행렬](figures/confusion_matrix_test.png) · "
                             "[전체 라벨 경로](label_key.csv)\n\n"
                             f"테스트 80문항을 행=실제 분류, 열=학습 문항의 군집별 최빈 라벨로 대응한 예측 분류로 셌다. "
                             f"전체 {len(labels)}분류를 같은 순서의 두 축에 포함한다. "
                             f"실제 미등장 {len(result['zero_actual_codes'])}분류·예측 미등장 {len(result['zero_predicted_codes'])}분류도 0행·0열로 남긴다. "
                             "같은 분류 수준의 두 거리 방식은 축 순서와 색상 범위가 같다. "
                             "큰 행렬은 코드를 사용한 고해상도 그림이며 숫자를 생략한 칸은 0이다.\n\n"
                             "기존 교차표 히트맵의 가로축은 군집 번호다. 이 혼동행렬은 가로축을 학습 대표 분류로 대응하여, "
                             "분류 간 혼동을 보여준다. 대표 라벨을 정할 때 테스트 실제 라벨을 사용하지 않았다.\n")
    record = {"definition": "row=actual hierarchical label; column=train-only cluster-majority label",
              "source": "unchanged saved members.csv, cluster_members.csv, label_key.csv, summary.csv",
              "training_or_assignment_performed": False, "experiments": results}
    (output / "confusion_matrix_validation.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return record


def main():
    result = make_holdout_confusions()
    print(json.dumps({"added_confusion_matrices": len(result["experiments"]),
                      "sums": [r["n"] for r in result["experiments"]],
                      "diagonals": [r["diagonal"] for r in result["experiments"]]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
