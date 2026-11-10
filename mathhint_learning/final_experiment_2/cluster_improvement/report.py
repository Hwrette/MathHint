"""저장된 전체265 문제 군집화 결과만 읽어 한국어 안내와 비교 그림을 만든다.

모델 학습·배정·어휘 생성·API 호출은 이 모듈의 역할이 아니다.
"""

import csv
import json
import os
from pathlib import Path


LEVELS = {
    "curriculum": "과목", "unit": "단원", "subunit": "세부단원", "type": "문제 유형",
}
METHODS = {"euclidean": "유클리드", "spherical": "코사인(구면)"}
CLI = "python -m mathhint_learning.final_experiment_2.cluster_improvement"


def _csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _write_csv(path, rows):
    path = Path(path)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _f(value, digits=4):
    return "—" if value is None or value == "" else f"{float(value):.{digits}f}"


def _pct(value):
    return "—" if value is None or value == "" else f"{100 * float(value):.2f}%"


def _table(headers, rows):
    return ["| " + " | ".join(headers) + " |",
            "|" + "|".join("---" for _ in headers) + "|"] + [
                "| " + " | ".join(str(value) for value in row) + " |" for row in rows]


def _relative(path, folder):
    return os.path.relpath(path, folder).replace(os.sep, "/")


def _collision_note(data):
    groups = {}
    for part in ("train", "test"):
        rows = data["variants"]["filtered"]["arrays"]["problems"][part]
        rows = rows.tolist() if hasattr(rows, "tolist") else rows
        for identifier, row in zip(data["ids"][part], rows):
            groups.setdefault(tuple(row), []).append(identifier)
    collisions = [ids for ids in groups.values() if len(ids) > 1]
    if not collisions:
        return "불용어 제거 뒤 서로 다른 문항의 벡터가 같아진 사례는 없다."
    examples = []
    for ids in collisions:
        labels = {tuple(data["records"][identifier][field] for field in LEVELS) for identifier in ids}
        examples.append("·".join(f"`{identifier}`" for identifier in ids)
                        + ("(같은 실제 유형)" if len(labels) == 1 else "(서로 다른 실제 유형 포함)"))
    return ("불용어 제거 후 같은 벡터가 된 문항: " + ", ".join(examples) + ". "
            "숫자·변수 등 제거한 좌표의 차이가 사라진 정보 손실 사례다. "
            "같은 유형 안의 중복 표현이 생겼다는 사실을 유형 오분류가 발생했다는 주장과 구분한다.")


def comparison_rows(root, output):
    """기존 전체265 결과와 새 K0/K1을 연결한다. 수치를 재계산하지 않는다."""
    historical = _csv(Path(root) / "results/final_experiment/01_clustering/full_dataset_265/summary.csv")
    current = _csv(Path(output) / "01_clustering/summary.csv")
    old = {(row["level"], row["method"]): row for row in historical}
    new = {(row["condition"], row["level"], row["method"]): row for row in current}
    expected = {(condition, level, method) for condition in ("K0", "K1")
                for level in LEVELS for method in METHODS}
    if len(current) != len(expected) or set(new) != expected:
        raise ValueError("새 전체265 군집화16조건이 완성되지 않았습니다: 01_clustering/summary.csv")
    result = []
    for level in LEVELS:
        for method in METHODS:
            previous, raw, filtered = old[level, method], new["K0", level, method], new["K1", level, method]
            if any(int(row["n"]) != 265 for row in (previous, raw, filtered)):
                raise ValueError("기존/새 전체265 비교에 다른 평가 범위가 섞였습니다.")
            row = {"level": level, "level_name": LEVELS[level], "method": method,
                   "method_name": METHODS[method], "n": 265, "k": int(raw["k"]),
                   "historical_ari": float(previous["ari"]), "historical_nmi": float(previous["nmi"]),
                   "historical_majority_match_rate": float(previous["full_majority_match_rate"])}
            for condition, values in (("K0", raw), ("K1", filtered)):
                for metric in ("ari", "ami", "nmi", "majority_accuracy", "macro_f1", "weighted_f1"):
                    row[condition + "_" + metric] = float(values[metric])
                row[condition + "_occupied_clusters"] = int(values["occupied_clusters"])
                row[condition + "_selected_seed"] = int(values["selected_seed"])
                row[condition + "_feature_dim"] = int(values["feature_dim"])
            row["ari_change_K1_minus_K0"] = row["K1_ari"] - row["K0_ari"]
            row["ami_change_K1_minus_K0"] = row["K1_ami"] - row["K0_ami"]
            row["nmi_change_K1_minus_K0"] = row["K1_nmi"] - row["K0_nmi"]
            result.append(row)
    return result


def _ari_table(rows):
    return _table(["실제 분류", "거리", "기존 전체265 ARI", "K0 새 원시 ARI", "K1 불용어 적용 ARI", "K1−K0"],
                  [(row["level_name"], row["method_name"], _f(row["historical_ari"]), _f(row["K0_ari"]),
                    _f(row["K1_ari"]), f"{row['ari_change_K1_minus_K0']:+.4f}") for row in rows])


def _association_table(rows):
    return _table(["실제 분류", "거리", "K0 AMI", "K1 AMI", "K0 NMI", "K1 NMI"],
                  [(row["level_name"], row["method_name"], _f(row["K0_ami"]), _f(row["K1_ami"]),
                    _f(row["K0_nmi"]), _f(row["K1_nmi"])) for row in rows])


def _label_table(rows):
    values = []
    for row in rows:
        for condition in ("K0", "K1"):
            values.append((row["level_name"], row["method_name"], condition,
                           _pct(row[condition + "_majority_accuracy"]), _f(row[condition + "_macro_f1"]),
                           _f(row[condition + "_weighted_f1"]),
                           f"{row[condition + '_occupied_clusters']}/{row['k']}"))
    return _table(["실제 분류", "거리", "조건", "동일265문항 대표 라벨 일치율", "Macro-F1", "Weighted-F1", "점유/k"], values)


def _seed_table(rows, seeds):
    indexed = {(row["condition"], row["level"], row["method"]): row
               for row in seeds if row["metric"] == "ari"}
    values = []
    for row in rows:
        scores = [indexed[condition, row["level"], row["method"]] for condition in ("K0", "K1")]
        values.append((row["level_name"], row["method_name"], *[
            f"{float(score['mean']):.4f} ± {float(score['std_ddof0']):.4f}" for score in scores]))
    return _table(["실제 분류", "거리", "K0 시드 ARI 평균 ± 표준편차", "K1 시드 ARI 평균 ± 표준편차"], values)


def _dataset_table(summary):
    region = summary["regions"]["problems"]
    return _table(["항목", "문제 BoW"], [
        ("원본 문항", "265문항 (기존185/80 분할은 출처로 보존)"),
        ("기존 학습 전용 어휘", region["legacy_vocab_count"]),
        ("K0 전체265 원시 어휘", region["raw_vocab_count"]),
        ("복원된 토큰 종류", region["restored_token_count"]),
        ("사용자 등록 불용어", region["registered_stopword_count"]),
        ("실제로 제거한 토큰 종류", region["removed_token_count"]),
        ("K1 활성 차원", region["filtered_vocab_count"]),
        ("전체 등장 횟수: 제거 전 → 후", f"{region['total_tf_before']:,} → {region['total_tf_after']:,}"),
        ("제거된 총 등장 횟수 (TF)", f"{region['removed_tf']:,}"),
    ])


def _navigation(root, output):
    parent = output.parent
    parent.mkdir(parents=True, exist_ok=True)
    (parent / "README.md").write_text(
        "# MathHint 2차 후속 실험\n\n"
        "| 연구 | 범위 | 먼저 열 자료 |\n|---|---|---|\n"
        "| cluster_improvement | 전체265문항의 문제 BoW 재구성·사용자 불용어 적용·K-means 비교 | "
        "[실험 요약·표·그림](cluster_improvement/README.md) · [종합 보고서](cluster_improvement/final_report.md) |\n\n"
        "이번 결과는 전체265문항으로 군집을 만들고 같은265문항의 구조를 관찰한 탐색 실험이다. "
        "새 테스트 성능이나 회귀·Gemini 결과를 포함하지 않는다. "
        "[기존 1차 최종 실험](../final_experiment/README.md)과 [토큰 분석](../token_analysis/README.md)은 보존한다.\n",
        encoding="utf-8")
    index = Path(root) / "results/README.md"
    text = index.read_text(encoding="utf-8")
    start, end = "<!-- final-experiment-2:start -->", "<!-- final-experiment-2:end -->"
    block = (start + "\n\n**새 후속 실험:** [2차 실험 목차](final_experiment_2/README.md) → "
             "[cluster_improvement 결과](final_experiment_2/cluster_improvement/README.md). "
             "전체265문항의 문제 BoW와 사용자 불용어 적용 전·후 K-means를 비교했다. "
             "같은265문항의 탐색 결과이며, 기존 1차 최종 실험·토큰 분석은 그대로 보존한다.\n\n" + end)
    if start in text:
        a, b = text.index(start), text.index(end) + len(end)
        text = text[:a] + block + text[b:]
    else:
        first, rest = text.split("\n", 1)
        text = first + "\n\n" + block + "\n" + rest
    index.write_text(text, encoding="utf-8")


def run(root, output, data):
    """cluster/report에서 저장한 결과를 연결한다. 학습 함수는 호출하지 않는다."""
    root, output = Path(root), Path(output)
    summary = _json(output / "00_dataset/summary.json")
    region = summary["regions"]["problems"]
    collision_note = _collision_note(data)
    rows = comparison_rows(root, output)
    euclidean = [row for row in rows if row["method"] == "euclidean"]
    higher = sum(row["ari_change_K1_minus_K0"] > 1e-12 for row in euclidean)
    lower = sum(row["ari_change_K1_minus_K0"] < -1e-12 for row in euclidean)
    seeds = _csv(output / "01_clustering/seed_summary.csv")
    evaluation = output / "02_evaluation"
    evaluation.mkdir(exist_ok=True)
    _write_csv(evaluation / "comparison_with_original.csv", rows)
    restored = _csv(output / "00_dataset/restored_tokens.csv")
    tokens = {row["token"] for row in restored}
    examples = [token for token in (r"latex:\gamma", r"latex:\log", r"latex:\circ", "kiwi:곱", "kiwi:닫힌구간") if token in tokens]
    example_text = ", ".join(f"`{token}`" for token in examples) or "전체 목록에서 정확한 문자열을 확인한다"
    lookup = {(row["level"], row["method"]): row for row in rows}
    curriculum = lookup["curriculum", "euclidean"]
    unit = lookup["unit", "euclidean"]
    kind = lookup["type", "euclidean"]
    subunit = lookup["subunit", "euclidean"]
    macro_change = subunit["K1_macro_f1"] - subunit["K0_macro_f1"]
    up_counts = {metric: sum(row["K1_" + metric] - row["K0_" + metric] > 1e-12 for row in rows)
                 for metric in ("ari", "ami", "nmi")}
    structured = (f"선택된 모델에서 K0 대비 상승한 조건 수는 ARI {up_counts['ari']}/{len(rows)}, "
                  f"AMI {up_counts['ami']}/{len(rows)}, NMI {up_counts['nmi']}/{len(rows)}다. "
                  f"하지만 유클리드 단원 ARI 변화는 {unit['ari_change_K1_minus_K0']:+.4f}로, "
                  f"과목 {curriculum['ari_change_K1_minus_K0']:+.4f}와 유형 {kind['ari_change_K1_minus_K0']:+.4f}보다 작았다.")
    macro_direction = "하락" if macro_change < 0 else "상승" if macro_change > 0 else "동일"
    exception = (f"유클리드 세부단원의 Macro-F1은 {subunit['K0_macro_f1']:.6f}→{subunit['K1_macro_f1']:.6f}"
                 f"({macro_change:+.6f})로 아주 작게 {macro_direction}했다. 같은 조건의 ARI·Weighted-F1 상승이 "
                 "모든 실제 분류를 균등하게 더 잘 구별한다는 뜻은 아니다. 이 미세 차이의 통계적 유의성은 검정하지 않았다.")
    vocabulary_deltas = [row["K0_ari"] - row["historical_ari"] for row in rows]
    old_up = sum(value > 1e-12 for value in vocabulary_deltas)
    old_down = sum(value < -1e-12 for value in vocabulary_deltas)
    old_same = len(rows) - old_up - old_down
    spherical_type = lookup["type", "spherical"]
    restoration = (f"어휘만 복원한 K0는 기존 전체265 결과 대비 ARI가 {old_same}조건에서 같고 "
                   f"{old_up}조건에서 상승·{old_down}조건에서 하락했다. 구면 방식의 유형 ARI는 "
                   f"{spherical_type['historical_ari']:.4f}→{spherical_type['K0_ari']:.4f}였다. "
                   "표현을 복원하는 것과 군집 일치도가 높아지는 것은 같은 결과가 아니다.")
    seed_index = {(row["condition"], row["level"], row["method"]): row
                  for row in seeds if row["metric"] == "ari"}
    k0_seed, k1_seed = [seed_index[condition, "curriculum", "euclidean"] for condition in ("K0", "K1")]
    seed_note = (f"유클리드 과목 ARI의 시드 표준편차는 K0 {float(k0_seed['std_ddof0']):.5f}→"
                 f"K1 {float(k1_seed['std_ddof0']):.5f}로 커졌다. 선택된 모델의 점수 상승과 "
                 "초기화 안정성 개선은 구분해야 한다. 선택 모델은 학습 목적함수가 최소인 실행이며 ARI가 최대인 실행을 고르지 않았다. "
                 "표는 같은265문항의5시드 평균±모집단 표준편차(ddof=0)이고, 독립 데이터 반복·신뢰구간이 아니다.")
    common_limits = [
        "전체265문항으로 어휘와 군집 중심을 만들고 같은265문항을 평가했다. 새로운 문항에 대한 테스트 정확도·일반화 성능이 아니다.",
        "군집 대표 라벨도 같은265문항의 최빈 실제 라벨이다. 대표 라벨 일치율과 F1은 동일 자료 내 설명용 분류 지표이며, ARI·AMI·NMI는 군집 구조의 일치도다.",
        "사용자가 전체265의 토큰 통계·η²를 보고 불용어를 선택했으므로 완전히 미관측인 독립 검증으로 주장할 수 없다. 새 문항으로 추가 검증해야 한다.",
        "K1과 기존 결과의 차이에는 어휘 재구성과 불용어 적용이 함께 포함된다. 불용어 적용 효과는 같은 전체 어휘에서 출발한 K0↔K1로 구분한다.",
        "BoW는 순서·분자/분모·밑/지수·논리 관계를 빈도 합으로 잃는다. 실제 분류와 비슷한 군집이 수학적 이해나 풀이 능력을 증명하지 않는다.",
        "Spherical 방식은 L2 정규화와 중심 갱신·정규화가 함께 다르다. 이번 결과만으로 차이의 원인을 입력 정규화 하나로 확정하지 않는다.",
        "다중 시드는 초기화 변동을 관찰하기 위한 것이며 독립 데이터 반복 검증이나 통계적 유의성 검정이 아니다. 유형70개와 희귀 유형 때문에 높은 NMI만으로 분류 품질을 판단하지 않는다.",
    ]
    old_summary = root / "results/final_experiment/01_clustering/full_dataset_265/summary.csv"
    comparison = ["# 기존 전체265 탐색 실험과의 비교", "",
                  "**세 열 모두 같은265문항에서 학습·평가한 탐색 실험이다. 기존185/80 테스트 결과와 섞지 않는다.**", "",
                  f"기존 수치는 [기존 전체265 원본 요약]({_relative(old_summary, evaluation)})에서 그대로 읽었다. "
                  "기존 모델·배정·지표·그림을 수정하지 않았다.", "",
                  "| 조건 | 문제 어휘 | 불용어 | 군집 학습·평가 |", "|---|---|---|---|",
                  f"| 기존 전체265 탐색 | 과거 학습185에서 만든 {region['legacy_vocab_count']}차원 | 미적용 | 같은265문항 |",
                  f"| K0 | 전체265 원문에서 재구성한 {region['raw_vocab_count']}차원 | 미적용 | 같은265문항 |",
                  f"| K1 | K0의 활성 {region['filtered_vocab_count']}차원 | 사용자 문제 목록만 적용 | 같은265문항 |", "",
                  "## ARI", "", *_ari_table(rows), "",
                  "## AMI·NMI", "", *_association_table(rows), "",
                  "기존 CSV는 AMI·F1을 제공하지 않는다. 이번에 과거 모델을 다시 학습·평가하여 값을 채우지 않았으며, 기존 NMI는 [원본 요약]"
                  f"({_relative(old_summary, evaluation)})과 [전체 비교 CSV](comparison_with_original.csv)에서 확인한다.", "",
                  "## 동일 자료 내 대표 라벨과 F1", "", *_label_table(rows), "",
                  structured, "", exception, "", restoration, "",
                  "## 초기화 시드에 따른 ARI 변동", "", *_seed_table(rows, seeds), "", seed_note, "",
                  "## 해석 범위", "", *["- " + value for value in common_limits], "",
                  "[ARI 비교 그림](../01_clustering/figures/ari_comparison.png) · [NMI 비교 그림](../01_clustering/figures/nmi_comparison.png) · "
                  "[원자료와 세 조건 전체 수치](comparison_with_original.csv)", ""]
    (evaluation / "comparison_with_original.md").write_text("\n".join(comparison), encoding="utf-8")
    (evaluation / "README.md").write_text(
        "# 같은265문항 군집 구조의 비교\n\n"
        "[읽기용 비교표·해석](comparison_with_original.md)에서 기존 전체265 결과와 새 K0/K1을 나란히 읽는다. "
        "[전체 수치 CSV](comparison_with_original.csv)는 소수 반올림 전 값을 보존한다.\n\n"
        "![전체265 ARI 비교](../01_clustering/figures/ari_comparison.png)\n\n"
        "![전체265 NMI 비교](../01_clustering/figures/nmi_comparison.png)\n\n"
        "모두 학습한265문항을 다시 설명하는 결과다. 테스트80문항의 일반화 성능이나 회귀·Gemini 성능을 뜻하지 않는다.\n",
        encoding="utf-8")
    experiment_links = _table(["실제 분류", "유클리드 K0 / K1", "코사인(구면) K0 / K1"], [
        (name,
         f"[K0 군집·혼동행렬](01_clustering/experiments/K0_{level}_euclidean/README.md) / "
         f"[K1 군집·혼동행렬](01_clustering/experiments/K1_{level}_euclidean/README.md)",
         f"[K0 군집·혼동행렬](01_clustering/experiments/K0_{level}_spherical/README.md) / "
         f"[K1 군집·혼동행렬](01_clustering/experiments/K1_{level}_spherical/README.md)")
        for level, name in LEVELS.items()])
    commands = [f"{CLI} prepare", f"{CLI} cluster", f"{CLI} report", f"{CLI} verify"]
    readme = ["# MathHint 2차 후속 실험 · 전체265 문제 BoW와 불용어 전처리", "",
              "**이번 범위는 전체265문항의 문제 BoW와 K-means 비교다.** 풀이 BoW 재구성·회귀 학습·Gemini 호출은 수행하지 않는다. "
              "기존 `final_experiment`·`token_analysis`와 사용자 불용어 목록은 보존한다.", "",
              "처음에는 아래 표·그림을 보고, 관심 있는 분류의 군집 목록과 혼동행렬을 연다. 전체 설명은 [종합 보고서](final_report.md)에서 읽는다.", "",
              "## 1. 무엇을 바꾸었는가?", "",
              "기존 학습185문항 전용 어휘에서 빠졌던 표현을 전체265 원문 재토큰화로 복원했다. "
              "같은 재토큰화 결과를 K0 원시 빈도와 K1 사용자 문제 불용어 적용 조건으로 나누었다. "
              "토큰화·K-means 알고리즘·5시드 학습 목적함수 선택 규칙은 기존 구현을 재사용한다.", "",
              "## 2. 데이터는 어떻게 달라졌는가?", "", *_dataset_table(summary), "",
              f"복원된 토큰 사례: {example_text}. 수학 기호가 복원됐다는 사실만으로 군집 성능 향상을 의미하지 않는다.", "",
              "[어휘 비교와 생성 정책](00_dataset/vocabulary_comparison.md) · [복원 토큰 전체](00_dataset/restored_tokens.csv) · "
              "[제거 토큰·TF 전체](00_dataset/stopword_audit.csv) · [남은 토큰 전체](00_dataset/retained_tokens.csv) · "
              "[문항별 제거 전·후 TF](00_dataset/question_token_counts.csv)", "",
              collision_note, "",
              "## 3. 군집 구조 일치도는 어떻게 달라졌는가?", "",
              "**전체265문항 탐색 — 새로운 문항에 대한 일반화 성능이 아님.** 유클리드 결과를 주로 해석하고 코사인(구면)은 비교 자료로 본다.", "",
              *_ari_table(rows), "", structured, "", restoration, "",
              "![기존 전체265·K0·K1 ARI](01_clustering/figures/ari_comparison.png)", "",
              "### AMI·NMI", "", *_association_table(rows), "",
              "![K0·K1 AMI](01_clustering/figures/ami_comparison.png)", "",
              "![기존 전체265·K0·K1 NMI](01_clustering/figures/nmi_comparison.png)", "",
              "### 군집 대표 라벨 일치율·F1", "",
              "군집의 최빈 실제 라벨을 같은265문항에서 정한 설명용 지표다. 임의 군집 번호를 실제 분류 번호로 간주하지 않는다.", "",
              *_label_table(rows), "",
              "![동일265 대표 라벨 일치율](01_clustering/figures/majority_accuracy_comparison.png)", "",
              "![동일265 Macro-F1](01_clustering/figures/macro_f1_comparison.png)", "",
              "![동일265 Weighted-F1](01_clustering/figures/weighted_f1_comparison.png)", "",
              exception, "",
              "### 초기화에 따른 변동도 함께 보기", "", *_seed_table(rows, seeds), "", seed_note, "",
              "[5시드 전체 지표·평균·표준편차](01_clustering/seed_summary.csv)", "",
              "## 4. 군집 문항과 혼동행렬 직접 보기", "", *experiment_links, "",
              "각 실험 README에서 혼동행렬 PNG/CSV, 실제분류×군집 교차표, 분류 코드, 군집별 라벨 분포와 모든 문항을 연다. "
              "혼동행렬은 행·열에 같은 순서의 실제 분류를 사용하며 대각선이 일치 문항 수다. 교차표의 열은 군집 번호이므로 서로 다른 그림이다.", "",
              "[군집화 전체 안내·요약](01_clustering/README.md) · [새16조건 전체 지표](01_clustering/summary.csv) · "
              "[기존/새 비교표](02_evaluation/comparison_with_original.md)", "",
              "문항 ID는 기존 수식 읽기 화면에 연결된다. 이 화면의 옛 Gemini 응답은 이번 군집화의 새 성능 결과가 아니다. "
              "GitHub에서 HTML은 소스 보기이므로 저장소 ZIP을 압축 해제한 뒤 기존 `final_experiment/03_gemini/report.html`을 "
              "브라우저에서 연다. 로컬 `viewer_assets`도 필요하며 인터넷/API 연결은 필요 없다.", "",
              "## 5. 해석의 한계", "", *["- " + value for value in common_limits], "",
              "이번에는 회귀·풀이 예측·Gemini를 평가하지 않았으므로 해당 성능의 개선 여부는 알 수 없다. "
              "후속 비선형·어텐션 표현이나 출력 검증은 가능성으로만 남기며 새 실험은 별도 요청을 따른다.", "",
              "## 6. 실행·재생성", "", "프로젝트 루트에서 실행한다. 완료된 동일 입력 실험은 해시를 확인한 뒤 재사용한다.", "",
              "```bash", *commands, "```", "",
              "- `prepare`: 원본 문제를 전체265 기준으로 토큰화하고 승인 목록을 적용한 별도 어휘·벡터를 저장한다.",
              "- `cluster`: 새 K0/K1 전체265 군집 모델을 학습한다. 기존 모델을 덮어쓰지 않는다.",
              "- `report`: 저장된 결과만 읽어 표·그림·문서를 만든다. 학습·새 군집 배정·API 호출은 없다.",
              "- `verify`: 저장된 데이터·지표·혼동행렬·원본 보존을 확인한다. 모델을 재학습하지 않는다.", "",
              "입력·선택 목록·설정이 바뀌면 과거 캐시를 조용히 재사용하지 않는다. 불용어 목록 자체를 자동 수정하지 않는다.", "",
              "[실험 설정·입력 해시](config.json) · [검증 기록](validation.json) · "
              "[기존 결과와의 종합 비교](02_evaluation/README.md)", ""]
    (output / "README.md").write_text("\n".join(readme), encoding="utf-8")
    report = ["# MathHint 전체265 문제 BoW·불용어 전처리 군집화 보고서", "",
              "## 1. 연구 배경과 목적", "",
              "원시 BoW에서 자주 등장하는 서식·변수·숫자가 거리 계산을 크게 차지할 수 있다. "
              "사용자가 직접 승인한 문제 불용어를 적용했을 때 실제 교육과정 분류와의 군집 구조 일치도가 "
              "어떻게 변하는지 탐색했다. 개선을 미리 가정하지 않고 상승·하락·변화 없음을 함께 기록한다.", "",
              "## 2. 기존 실험의 한계와 전체 어휘 재구성", "", *_dataset_table(summary), "",
              "기존 전체265 군집화도 입력 어휘는 과거 학습185문항에서 만들었다. 테스트 전용 토큰이 이미 빠진 벡터를 합치는 대신 "
              "기존 문제 본문을 같은 Kiwi·LaTeX 함수로 다시 토큰화했다. 분류 메타데이터는 입력 토큰에 섞지 않았다. "
              f"복원 사례는 {example_text}이며 전체 목록과 출현 수는 [데이터 안내](00_dataset/README.md)를 따른다.", "",
              "## 3. 사용자 불용어 적용과 실험 방법", "",
              "K0/K1은 동일한 전체 원문과 토큰화에서 출발한다. K1은 사용자가 승인한 문제 목록만 적용하고 "
              "해당 차원을 제외한 활성 어휘를 사용한다. 원시 TF는 정수로 유지하며 추가 정규화·새 토큰화·자동 불용어 선정은 하지 않았다. "
              "기존185/80 분할은 문항 출처로 보존했지만 이번 중심은 두 집합을 합친265문항에서 학습했다.", "",
              "계층 라벨은 curriculum→unit→subunit→type의 경로다. subject의 자료군을 과목으로 사용하지 않았다. "
              "라벨은 k 검증과 사후 평가·대표 라벨 정하기에만 쓰고 K-means 빈도 벡터에 포함하지 않았다. "
              "시드42~46의5회 초기화, 최대100회·기존 수렴 기준을 유지하고 각 방법의 학습 목적함수가 최소인 실행을 선택한다. "
              "ARI·NMI나 실제 분류를 보고 시드를 선택하지 않는다. 서로 다른 방법의 목적함수 크기는 직접 비교하지 않는다.", "",
              "## 4. 군집 구조 비교 결과", "", *_ari_table(rows), "", structured, "",
              "AMI·NMI와 대표 라벨/F1의 전체 수치는 [첫 README](README.md)와 "
              "[기존/새 비교](02_evaluation/comparison_with_original.md)에 같은 저장값으로 연결된다. "
              "ARI·AMI는 우연한 일치를 조정하는 구조 지표이고 NMI는 정보 공유량을 정규화한 지표다. "
              "유형처럼 k가 큰 경우 NMI가 상대적으로 높아질 수 있으므로 ARI·AMI·F1을 함께 읽는다.", "",
              "## 5. 군집과 혼동행렬 직접 관찰", "", *experiment_links, "",
              "실제분류×군집번호 교차표는 여러 유형의 혼합과 한 유형의 분산을 보여준다. "
              "실제분류×군집대표라벨 혼동행렬은 군집을 실제 라벨로 매핑한 뒤의 일치 문항 수를 보여준다. "
              "서로 다른 군집이 같은 최빈 라벨을 가지면 같은 예측 열에 합쳐진다. 행과 열의 라벨 순서는 같아서 "
              "대각선 합/265가 저장된 대표 라벨 일치율과 대응한다. 각 군집의 원문을 읽어 수식·자연어의 공통점과 차이를 확인한다.", "",
              "## 6. 관찰과 가능한 해석", "",
              "**확인한 사실:** " + structured, "", exception, "", restoration, "", collision_note, "",
              "### 선택 모델과 5시드 평균은 다른 요약이다", "", *_seed_table(rows, seeds), "", seed_note, "",
              "**가능한 해석:** 빈도 규모가 큰 좌표를 제거하면 유클리드 공간의 상대 가중치가 달라진다. "
              "이 변화가 어떤 분류에는 도움이 되고 다른 분류의 단서를 잃게 할 수 있다. "
              "하지만 여러 종류의 승인 토큰을 한꺼번에 제거했으므로 개별 토큰의 인과 효과를 분리해 검증한 것은 아니다. "
              "코사인 방식도 같은 좌표 제거 뒤 방향이 바뀌므로 서식 제거 효과가 항상 같은 방향일 필요는 없다.", "",
              "## 7. 기존 연구와의 차이", "",
              "이번 비교의 역사적 기준선은 기존 전체265 탐색 실험이다. 기존 학습185·테스트80 평가와 "
              "이번 동일265 평가를 같은 의미의 성능으로 비교하지 않는다. 기존 회귀·Gemini 응답과 평가값은 읽기 화면에 남아 있으며 "
              "이번 연구의 새 결과로 다시 보고하지 않았다.", "",
              "## 8. 정보 사용과 데이터 규모의 한계", "", *["- " + value for value in common_limits], "",
              "## 9. BoW의 표현 한계와 후속 연구", "",
              "토큰 빈도는 개념·연산·문제 표현의 존재를 간단히 비교할 수 있지만 토큰 순서와 수식 구조를 직접 다루지 못한다. "
              "다층 비선형 모델이나 어텐션 기반 표현을 검토할 수는 있으나 이번 결과가 그 필요성이나 성능 향상을 증명하지 않는다. "
              "층을 늘리는 것만으로 BoW에서 사라진 수식 구조가 복원되지도 않는다. "
              "문맥 기반 표현·디코딩 제약·Lean 같은 출력 검증으로 확장하더라도 새로운 데이터에서의 검증이 필요하며 "
              "형식 검증 성공과 고등학교 교육과정 적합성은 구분해야 한다. 이번에는 그러한 구현을 하지 않았다.", "",
              "## 10. 범위와 재현성", "",
              f"실험 ID: `{data['dataset_id']}`. [설정·해시](config.json), [데이터 검증](00_dataset/README.md), "
              "[전체 검증](validation.json)과 각 실험의 모델·5시드 기록으로 결과를 추적한다. "
              "원본 데이터·기존 1차 결과·토큰 분석·사용자 선택 JSON은 보존한다. "
              "새 회귀 학습·풀이 BoW 생성·신경망·Gemini 호출은 이번 범위에 없다. "
              "실행·보고서 재생성 명령은 [첫 README](README.md#6-실행재생성)에 정리했다.", ""]
    (output / "final_report.md").write_text("\n".join(report), encoding="utf-8")
    _navigation(root, output)
    return {"comparison_rows": len(rows), "euclidean_ari_higher_levels": higher,
            "euclidean_ari_lower_levels": lower, "training_performed": False,
            "api_calls": 0, "output": str(output)}
