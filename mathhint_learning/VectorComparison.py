"""실수 회귀 예측을 검증하고 문항별 벡터·상위 토큰·그림을 저장한다.

실행: python -m mathhint_learning.VectorComparison
기존 고정 모델의 무결성을 확인해 재사용하며 모델을 다시 학습하지 않는다.
"""

import csv
import hashlib
import json
import os
from pathlib import Path

import torch
from torch import nn
from torch.nn.functional import cosine_similarity

if __package__:
    from .TorchData import load_fixed_dataset, read_json, write_json
else:
    from TorchData import load_fixed_dataset, read_json, write_json

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "results/model_comparison_2026-11-07"
OUTPUT = ROOT / "results/final_experiment/02_regression"
TOP_K = 20


def vector_metrics(prediction, answer):
    """MSE/MAE는 모든 좌표의 평균, 코사인은 문항별 값의 평균이다."""
    prediction, answer = prediction.float(), answer.float()
    error = prediction - answer
    if prediction.ndim == 1:
        prediction, answer = prediction.unsqueeze(0), answer.unsqueeze(0)
    return {"mse": error.square().mean().item(), "mae": error.abs().mean().item(),
            "cosine_similarity": cosine_similarity(prediction, answer, dim=1).mean().item()}


def top_tokens(vector, vocabulary, k=TOP_K):
    """양의 값만, 반올림 전 값 내림차순·동률은 고정 어휘 인덱스 오름차순."""
    values = vector.tolist() if hasattr(vector, "tolist") else list(vector)
    indices = sorted((j for j, value in enumerate(values) if value > 0), key=lambda j: (-values[j], j))[:k]
    return [{"index": j, "token": vocabulary[j], "frequency": values[j]} for j in indices]


def token_overlap(actual_tokens, predicted_tokens, k=TOP_K):
    actual = {item["index"] for item in actual_tokens}
    predicted = {item["index"] for item in predicted_tokens}
    common = len(actual & predicted)
    return {"actual_top_count": len(actual), "predicted_top_count": len(predicted),
            "common_top20_count": common, "precision_at_20": common / k,
            "precision_at_available_k": common / len(predicted) if predicted else None,
            "recall_of_actual_top20": common / len(actual) if actual else None,
            "top20_jaccard": common / len(actual | predicted) if actual | predicted else None}


def _csv(path, rows):
    with Path(path).open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def export_comparison(ids, vocabulary, actual, raw, mean, output, *, records=None, project_root=None, history=None):
    """평가에서 정수 반올림하지 않는다. 상위 토큰 선택도 원래 실수로 한다."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    records = records or {}
    variants = {"training_mean": mean, "raw": raw, "clipped_nonnegative": raw.clamp_min(0)}
    rows, documents = [], []
    for i, identifier in enumerate(ids):
        meta = records.get(identifier, {})
        row = {"id": identifier, **{key: meta.get(key, "") for key in ("subject", "curriculum", "unit", "subunit", "type")},
               "problem_path": f"data/processed/problems/{identifier}.txt",
               "solution_path": f"data/processed/solutions/{identifier}.txt"}
        for name, values in variants.items():
            row.update({name + "_" + key: value for key, value in vector_metrics(values[i], actual[i]).items()})
        actual_top, predicted_top = top_tokens(actual[i], vocabulary), top_tokens(raw[i].clamp_min(0), vocabulary)
        row.update(token_overlap(actual_top, predicted_top))
        row.update(actual_top20=json.dumps(actual_top, ensure_ascii=False), predicted_top20=json.dumps(predicted_top, ensure_ascii=False))
        rows.append(row)
        documents.append({"id": identifier, "actual_vector": actual[i].to(torch.int64).tolist(),
                          "raw_predicted_vector": raw[i].tolist(), "predicted_vector": raw[i].clamp_min(0).tolist()})
    _csv(output / "question_comparison.csv", rows)
    write_json(output / "vectors.json", {"vocabulary": vocabulary,
        "prediction_policy": "raw_float32_and_negative_clipped_float32; no_integer_rounding", "documents": documents})
    summary_rows = [{"method": name, "test_count": len(ids), **vector_metrics(values, actual)} for name, values in variants.items()]
    _csv(output / "summary.csv", summary_rows)
    summary = {"test_ids": ids, "test_count": len(ids), "vocabulary_size": len(vocabulary),
        "evaluation_rounding": "none", "actual_counts": "nonnegative integers", "metrics": {row["method"]: row for row in summary_rows},
        "top_tokens": {"k": TOP_K, "positive_only": True, "selection_values": "unrounded frequency",
            "ties": "ascending fixed training vocabulary index", "fewer_than_k": "select all positive tokens, no zero padding",
            "precision_at_20_denominator": 20, "precision_at_available_k_denominator": "number of selected predicted tokens; null if zero",
            "recall_denominator": "number of selected actual tokens; null if zero",
            "mean_common_top20_count": sum(row["common_top20_count"] for row in rows) / len(ids),
            "mean_precision_at_20": sum(row["precision_at_20"] for row in rows) / len(ids),
            "actual_fewer_than_20_count": sum(row["actual_top_count"] < TOP_K for row in rows),
            "predicted_fewer_than_20_count": sum(row["predicted_top_count"] < TOP_K for row in rows)},
        "cosine_zero_vector_convention": "torch cosine_similarity epsilon=1e-8, either zero vector gives 0",
        "note": "MSE·MAE·코사인은 벡터 예측 지표이며 수학 문제의 정답률이 아니다."}
    write_json(output / "summary.json", summary)
    _plots(actual, raw, mean, ids, vocabulary, rows, output, history)
    _analysis(rows, summary_rows, output, project_root)
    return summary


def _plots(actual, raw, mean, ids, vocabulary, rows, output, history):
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/mathhint-mpl")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    font = Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
    if font.exists():
        font_manager.fontManager.addfont(str(font))
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=str(font)).get_name()
    plt.rcParams.update({"axes.unicode_minus": False, "axes.spines.top": False, "axes.spines.right": False, "font.size": 10})
    figures = output / "figures"
    figures.mkdir(exist_ok=True)

    def save(fig, name):
        fig.tight_layout()
        fig.savefig(figures / (name + ".png"), dpi=180, bbox_inches="tight")
        plt.close(fig)

    variants = [mean, raw, raw.clamp_min(0)]
    labels = ["학습 평균 기준선", "원시 예측", "음수→0 보정"]
    fig, axes = plt.subplots(1, 3, figsize=(13, 4))
    for ax, metric, title in zip(axes, ["mse", "mae", "cosine_similarity"], ["MSE ↓", "MAE ↓", "코사인 유사도 ↑"]):
        scores = [vector_metrics(values, actual)[metric] for values in variants]
        bars = ax.bar(labels, scores, color=[".8", ".55", ".25"], edgecolor="black", linewidth=.5)
        ax.bar_label(bars, fmt="%.4f", fontsize=9)
        ax.set_title(title)
        ax.tick_params(axis="x", labelrotation=15)
        ax.set_ylim(0, max(scores) * 1.18 if max(scores) else 1)
    fig.suptitle(f"동일 테스트 {len(ids)}문항의 실수 해설 벡터 예측 · 정수 반올림 없음")
    save(fig, "metrics")

    if history:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.plot([item["epoch"] for item in history], [item["train_mse"] for item in history], color="black")
        ax.set(xlabel="학습 epoch", ylabel="학습 MSE", title="기존 선형회귀의 학습 손실 (테스트로 학습·선택하지 않음)")
        save(fig, "learning_curve")

    fig, axes = plt.subplots(1, 3, figsize=(13, 4))
    for ax, metric, title in zip(axes, ["mse", "mae", "cosine_similarity"], ["MSE", "MAE", "코사인 유사도"]):
        scores = [row["clipped_nonnegative_" + metric] for row in rows]
        ax.hist(scores, bins=min(15, len(rows)), color=".55", edgecolor="white")
        ax.axvline(sum(scores) / len(scores), color="black", linestyle="--", label=f"평균 {sum(scores) / len(scores):.4f}")
        ax.set(xlabel=title, ylabel="문항 수", title="음수 보정 예측의 문항별 " + title)
        ax.legend(fontsize=8)
    save(fig, "question_distribution")

    ordered = sorted(range(len(ids)), key=lambda i: (rows[i]["clipped_nonnegative_cosine_similarity"], ids[i]))
    for category, indices in [("low_cosine", ordered[:2]), ("high_cosine", list(reversed(ordered[-2:])) )]:
        for i in indices:
            chosen = sorted({item["index"] for item in top_tokens(actual[i], vocabulary)} |
                            {item["index"] for item in top_tokens(raw[i].clamp_min(0), vocabulary)},
                            key=lambda j: (-max(actual[i, j].item(), raw[i, j].item()), j))
            fig, ax = plt.subplots(figsize=(11, max(5, len(chosen) * .23)))
            y = list(range(len(chosen)))
            ax.barh([j - .18 for j in y], actual[i, chosen].tolist(), height=.36, color=".8", edgecolor="black", linewidth=.5, label="실제 빈도")
            ax.barh([j + .18 for j in y], raw[i, chosen].clamp_min(0).tolist(), height=.36, color=".3", label="음수 보정 예측 (실수)")
            ax.set_yticks(y, [vocabulary[j] for j in chosen])
            ax.invert_yaxis()
            ax.set(xlabel="빈도 / 예측값", title=f"{ids[i]} · 실제·예측 각 상위20토큰의 합집합\n코사인 {rows[i]['clipped_nonnegative_cosine_similarity']:.4f}; 높은 빈도가 수학적 중요도를 뜻하지 않음")
            ax.legend()
            save(fig, f"top_tokens_{category}_{ids[i]}")


def _analysis(rows, summary_rows, output, project_root):
    summary = read_json(output / "summary.json")
    ordered = sorted(rows, key=lambda row: (row["clipped_nonnegative_cosine_similarity"], row["id"]))
    lines = ["# 회귀 모델 검증", "", "기존 학습 185문항·테스트 80문항과 346→431차원 선형층을 유지했다. 최종 실험에서 재학습하지 않고 무결성을 검증한 기존 모델·예측·학습곡선을 재사용했다.", "",
        "|방법|MSE ↓|MAE ↓|평균 코사인 유사도 ↑|", "|---|---:|---:|---:|"]
    names = {"training_mean": "학습 평균 기준선", "raw": "원시 회귀 출력", "clipped_nonnegative": "음수→0 보정"}
    for row in summary_rows:
        lines.append(f"|{names[row['method']]}|{row['mse']:.6f}|{row['mae']:.6f}|{row['cosine_similarity']:.6f}|")
    lines += ["", "MSE는 큰 오차에 더 민감한 평균제곱오차, MAE는 평균절대오차다. 코사인은 벡터의 방향 유사도이며 퍼센트 정답률이 아니다. 음수 보정은 MSE·코사인을 개선했지만, MAE는 단순 평균 기준선보다 약간 크다. 이 지표만으로 LLM 풀이 개선을 결론낼 수 없다.", "",
        "## 상위 20개 토큰의 일치", "",
        f"평균 공통 토큰 수는 **{summary['top_tokens']['mean_common_top20_count']:.3f}개**, 평균 Precision@20은 **{summary['top_tokens']['mean_precision_at_20']:.6f}**다.",
        "양의 빈도만 반올림 전 값으로 내림차순 정렬하고, 동률은 학습 어휘 인덱스 오름차순으로 처리한다. 20개 미만이면 양의 토큰 전부를 고르며 0으로 채우지 않는다. Precision@20은 공통 수/20, 추가 열 precision_at_available_k는 공통 수/실제 선택된 예측 토큰 수다. 후자의 분모가 0이면 null이다. 실제 상위 토큰 회수율의 분모는 실제 선택 수이며 0이면 null이다.",
        f"실제 양의 토큰이 20개 미만인 문항은 {summary['top_tokens']['actual_fewer_than_20_count']}개, 예측은 {summary['top_tokens']['predicted_fewer_than_20_count']}개다.", "",
        "## 소수점 처리와 자료 확인", "",
        "실제 빈도는 정수로 보존한다. 원시 예측·음수 보정 예측과 MSE·MAE·코사인 평가는 실수 값을 그대로 사용하며 정수 반올림하지 않는다. Gemini는 양수 상위20개를 먼저 선택한 뒤 소수점 세 자리로 표시한다. 표시 반올림으로 0이 되면 기존 전송 정책상 생략될 수 있으며, 실제 전송 값·토큰 수는 prompt_audit에서 확인한다. 회귀 평가에는 이 표시용 반올림을 적용하지 않는다.", "",
        "- [문항별 지표·상위20토큰 CSV](question_comparison.csv): clipped_nonnegative_cosine_similarity나 MAE로 정렬할 수 있다.",
        "- [전체 실제·원시·보정 벡터 JSON](vectors.json): vocabulary[j]와 각 문항 벡터[j]가 대응한다.",
        "- [재사용 검증과 원본 경로](provenance.json): 모델과 원본 예측을 중복 복사하지 않고 연결한다.",
        "- [요약 지표](summary.csv), [시각자료](figures/metrics.png), [기존 학습 손실](figures/learning_curve.png)", "",
        "## 대표 문항", "", "다음은 코사인 유사도 기준의 상·하위 사례다. 수학적 풀이의 정오나 토큰 중요성을 판정한 순위는 아니다."]
    for title, selected in [("유사도가 높은 사례", list(reversed(ordered[-3:]))), ("유사도가 낮은 사례", ordered[:3])]:
        lines += ["", "### " + title, "", "|ID|과목 / 단원 / 세부단원 / 유형|MSE|MAE|코사인|공통 토큰|실제·예측 토큰 그림|", "|---|---|---:|---:|---:|---:|---|"]
        for row in selected:
            relative = os.path.relpath(Path(project_root) / row["problem_path"], output) if project_root else row["problem_path"]
            label = " / ".join(row[key] for key in ("curriculum", "unit", "subunit", "type"))
            figures = sorted((output / "figures").glob(f"top_tokens_*_{row['id']}.png"))
            figure = f"[빈도 비교 그림]({figures[0].relative_to(output).as_posix()})" if figures else "[토큰 CSV](question_comparison.csv)"
            lines.append(f"|[{row['id']}]({relative})|{label}|{row['clipped_nonnegative_mse']:.4f}|{row['clipped_nonnegative_mae']:.4f}|{row['clipped_nonnegative_cosine_similarity']:.4f}|{row['common_top20_count']}|{figure}|")
    by_id = {row["id"]: row for row in rows}
    if "trig_2_016" in by_id and "trig_1_043" in by_id:
        good, bad = by_id["trig_2_016"], by_id["trig_1_043"]
        actual = {r["token"].replace("\\", ""): r["frequency"] for r in json.loads(bad["actual_top20"])}
        predicted = {r["token"].replace("\\", ""): r["frequency"] for r in json.loads(bad["predicted_top20"])}
        lines += ["", "## 실제 토큰으로 보는 예측의 차이", "",
            f"`trig_2_016`은 상위20개 중 {good['common_top20_count']}개가 겹친다. 실제·예측 모두 sin, cos, sqrt, theta, frac와 괄호·숫자 등 여러 수식 조각을 포함한다. [실제·예측 빈도 그림](figures/top_tokens_high_cosine_trig_2_016.png)에서 같은 토큰의 빈도 크기는 여전히 다른 것도 확인할 수 있다.", "",
            f"반면 `trig_1_043`은 공통 토큰이 {bad['common_top20_count']}개다. 실제 상위20개에는 pi가 {actual['latex:pi']:.0f}회 등장하고 theta·frac·숫자4와8이 포함되지만, 이 토큰들은 예측 상위20개에서 빠졌다. 예측에는 0이 {predicted['latex:0']:.3f}, cos가 {predicted['latex:cos']:.3f}로 높게 나타났다. [이 문항의 빈도 비교 그림](figures/top_tokens_low_cosine_trig_1_043.png)으로 대조할 수 있다.", "",
            "이 사례는 함께 등장하는 기호·표현의 빈도 구성은 일부 예측하지만, 문항별 수식 조각의 구성과 횟수에는 차이가 남는다는 관찰이다. 상위20개에서 빠졌다는 것은 전체 예측 벡터의 값이 0이라는 뜻이 아니다. 높은 빈도·상위토큰 일치와 수학적으로 중요한 풀이 원리의 예측을 같은 의미로 해석하지 않는다."]
    lines += ["", "## 해석과 한계", "", "확인한 사실: 보정 후 코사인은 기준선보다 높지만, 선형회귀의 MAE 개선은 나타나지 않았다. 단어 빈도는 순서와 수식 구조를 보존하지 않는다. 일반적인 연결어·기호의 높은 빈도를 예측하는 것과 문제별 풀이 원리를 예측하는 것은 다르다. 상위토큰 그림에서 차이를 직접 확인해야 한다.",
        "학습 MSE와 테스트 MSE 차이는 일반화의 제한을 보여준다. 185개 학습·80개 테스트의 한 분할만 사용했다. 이전 테스트 결과를 본 뒤 분석을 설계했으므로 전혀 관찰하지 않은 독립 최종 평가라고 주장하지 않는다. 최종 테스트를 사용한 재학습·모델 선택·어휘 추가는 하지 않았다."]
    (output / "analysis.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(root=ROOT, source=SOURCE, output=OUTPUT):
    """해시·ID·고정 어휘·모델 추론 일치를 확인한 후 기존 결과를 분석한다."""
    root, source, output = Path(root), Path(source), Path(output)
    torch.set_num_threads(2)
    data = load_fixed_dataset(root)
    source_paths = ["models/regression_model.pt", "01_회귀모델/regression_predictions.json", "provenance/regression_learning_curve.json", "01_회귀모델/regression_metrics.json"]
    manifest = read_json(source / "manifest.json")["files"]
    hashes = {name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in source_paths}
    if any(hashes[name] != manifest[name] for name in source_paths):
        raise ValueError("기존 회귀 결과의 manifest 해시가 일치하지 않습니다.")
    checkpoint = torch.load(source / source_paths[0], map_location="cpu", weights_only=True)
    saved = read_json(source / source_paths[1])
    for container in (checkpoint, saved):
        if container["generation_id"] != data["generation_id"] or container["train_ids"] != data["ids"]["train"]:
            raise ValueError("기존 모델/예측의 데이터 버전 또는 학습 ID가 다릅니다.")
    if checkpoint["input_vocabulary"] != data["vocabularies"]["problems"] or checkpoint["output_vocabulary"] != data["vocabularies"]["solutions"] or saved["vocabulary"] != data["vocabularies"]["solutions"]:
        raise ValueError("기존 모델/예측의 고정 어휘가 다릅니다.")
    if saved["model_sha256"] != hashes[source_paths[0]] or [doc["id"] for doc in saved["documents"]] != data["ids"]["test"]:
        raise ValueError("기존 예측의 모델 해시 또는 테스트 행 ID 순서가 다릅니다.")
    model = nn.Linear(checkpoint["input_dim"], checkpoint["output_dim"])
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    with torch.no_grad():
        reproduced = model(data["arrays"]["problems"]["test"])
    raw = torch.tensor([doc["raw_predicted_vector"] for doc in saved["documents"]], dtype=torch.float32)
    actual = data["arrays"]["solutions"]["test"]
    saved_actual = torch.tensor([doc["actual_vector"] for doc in saved["documents"]], dtype=torch.float32)
    saved_clipped = torch.tensor([doc["predicted_vector"] for doc in saved["documents"]], dtype=torch.float32)
    if not torch.equal(raw, reproduced) or not torch.equal(actual, saved_actual) or not torch.equal(saved_clipped, raw.clamp_min(0)):
        raise ValueError("기존 실제/예측 벡터가 데이터 또는 모델 재추론과 정확히 일치하지 않습니다.")
    if not torch.equal(actual, actual.round()) or (actual < 0).any():
        raise ValueError("실제 빈도 벡터는 음이 아닌 정수여야 합니다.")
    history = read_json(source / source_paths[2])
    mean = data["arrays"]["solutions"]["train"].mean(dim=0).expand_as(actual)
    result = export_comparison(data["ids"]["test"], saved["vocabulary"], actual, raw, mean, output,
                               records=data["records"], project_root=root, history=history)
    provenance = {"generation_id": data["generation_id"], "train_ids": data["ids"]["train"], "test_ids": data["ids"]["test"],
        "model_source": str((source / source_paths[0]).relative_to(root)), "prediction_source": str((source / source_paths[1]).relative_to(root)),
        "learning_curve_source": str((source / source_paths[2]).relative_to(root)), "source_sha256": hashes,
        "validation": {"manifest_hashes": True, "train_test_disjoint": not bool(set(data["ids"]["train"]) & set(data["ids"]["test"])),
            "training_vocabulary_and_id_order_match": True, "model_reinference_exactly_matches_all_80_saved_raw_vectors": True,
            "actual_vectors_match_fixed_test_vectors": True, "clipped_vectors_match_saved_vectors": True, "actual_vectors_are_nonnegative_integers": True},
        "model_config": saved["config"], "training_metrics": read_json(source / source_paths[3])["metrics"]["train"],
        "training_repeated": False, "test_used_for_parameter_selection": False,
        "torch_version_for_validation": torch.__version__, "forecast_storage": "float32 raw and clipped; no evaluation rounding"}
    write_json(output / "provenance.json", provenance)
    print(json.dumps({"reused_model": provenance["model_source"], "test_count": len(actual), "metrics": result["metrics"], "top_tokens": result["top_tokens"], "output": str(output)}, ensure_ascii=False, indent=2))
    return result


if __name__ == "__main__":
    run()
