"""실수 회귀 예측을 검증하고 문항별 벡터·상위 토큰·그림을 저장한다.

실행: python -m mathhint_learning.VectorComparison
기존 고정 모델의 무결성을 확인해 재사용하며 모델을 다시 학습하지 않는다.
"""

import csv
import hashlib
import json
import math
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


def export_comparison(ids, vocabulary, actual, raw, mean, output, *, records=None, project_root=None, history=None, make_figures=True, data_context=None, data_root=None):
    """평가에서 정수 반올림하지 않는다. 상위 토큰 선택도 원래 실수로 한다."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    records = records or {}
    variants = {"training_mean": mean, "raw": raw, "clipped_nonnegative": raw.clamp_min(0)}
    rows, documents = [], []
    for i, identifier in enumerate(ids):
        meta = records.get(identifier, {})
        base = Path(data_root) if data_root is not None else Path(project_root) / "data" if project_root else Path("data")
        problem = base / "processed/problems" / (identifier + ".txt")
        solution = base / "processed/solutions" / (identifier + ".txt")
        row = {"id": identifier, **{key: meta.get(key, "") for key in ("subject", "curriculum", "unit", "subunit", "type")},
               "problem_path": os.path.relpath(problem, project_root) if project_root else str(problem),
               "solution_path": os.path.relpath(solution, project_root) if project_root else str(solution)}
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
    if data_context:
        summary["data_context"] = data_context
    write_json(output / "summary.json", summary)
    if make_figures:
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
        ax.set(xlabel="학습 epoch", ylabel="학습 MSE", title="선택한 선형회귀의 학습 손실 (테스트로 학습·선택하지 않음)")
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
    context = summary.get("data_context", {})
    description = (f"선택한 데이터의 학습 {context.get('train_count', '미기록')}문항·테스트 {summary['test_count']}문항, "
                   f"{context.get('input_dimensions', '미기록')}→{summary['vocabulary_size']}차원 선형층을 평가했다. "
                   "이 평가 명령은 모델을 학습하지 않는다. 실제 선택한 모델·데이터는 provenance.json에서 확인한다.")
    lines = ["# 회귀 모델 검증", "", description, "",
        "|방법|MSE ↓|MAE ↓|평균 코사인 유사도 ↑|", "|---|---:|---:|---:|"]
    names = {"training_mean": "학습 평균 기준선", "raw": "원시 회귀 출력", "clipped_nonnegative": "음수→0 보정"}
    for row in summary_rows:
        lines.append(f"|{names[row['method']]}|{row['mse']:.6f}|{row['mae']:.6f}|{row['cosine_similarity']:.6f}|")
    lines += ["", "MSE는 큰 오차에 더 민감한 평균제곱오차, MAE는 평균절대오차다. 코사인은 벡터의 방향 유사도이며 퍼센트 정답률이 아니다. 세 기준의 실제 수치를 비교해야 하며, 이 지표만으로 LLM 풀이 개선을 결론낼 수 없다.", "",
        "## 상위 20개 토큰의 일치", "",
        f"평균 공통 토큰 수는 **{summary['top_tokens']['mean_common_top20_count']:.3f}개**, 평균 Precision@20은 **{summary['top_tokens']['mean_precision_at_20']:.6f}**다.",
        "양의 빈도만 반올림 전 값으로 내림차순 정렬하고, 동률은 학습 어휘 인덱스 오름차순으로 처리한다. 20개 미만이면 양의 토큰 전부를 고르며 0으로 채우지 않는다. Precision@20은 공통 수/20, 추가 열 precision_at_available_k는 공통 수/실제 선택된 예측 토큰 수다. 후자의 분모가 0이면 null이다. 실제 상위 토큰 회수율의 분모는 실제 선택 수이며 0이면 null이다.",
        f"실제 양의 토큰이 20개 미만인 문항은 {summary['top_tokens']['actual_fewer_than_20_count']}개, 예측은 {summary['top_tokens']['predicted_fewer_than_20_count']}개다.", "",
        "## 소수점 처리와 자료 확인", "",
        "실제 빈도는 정수로 보존한다. 원시 예측·음수 보정 예측과 MSE·MAE·코사인 평가는 실수 값을 그대로 사용하며 정수 반올림하지 않는다. Gemini는 양수 상위20개를 먼저 선택한 뒤 소수점 세 자리로 표시한다. 표시 반올림으로 0이 되면 기존 전송 정책상 생략될 수 있으며, 실제 전송 값·토큰 수는 prompt_audit에서 확인한다. 회귀 평가에는 이 표시용 반올림을 적용하지 않는다.", "",
        "- [문항별 지표·상위20토큰 CSV](question_comparison.csv): clipped_nonnegative_cosine_similarity나 MAE로 정렬할 수 있다.",
        "- [전체 실제·원시·보정 벡터 JSON](vectors.json): vocabulary[j]와 각 문항 벡터[j]가 대응한다.",
        "- [재사용 검증과 원본 경로](provenance.json): 모델과 원본 예측을 중복 복사하지 않고 연결한다.",
        "- [요약 지표](summary.csv)" + (", [시각자료](figures/metrics.png)" if (output / "figures/metrics.png").exists() else "")
        + (", [선택한 모델의 학습 손실](figures/learning_curve.png)" if (output / "figures/learning_curve.png").exists() else ""), "",
        "## 대표 문항", "", "다음은 코사인 유사도 기준의 상·하위 사례다. 수학적 풀이의 정오나 토큰 중요성을 판정한 순위는 아니다."]
    for title, selected in [("유사도가 높은 사례", list(reversed(ordered[-3:]))), ("유사도가 낮은 사례", ordered[:3])]:
        lines += ["", "### " + title, "", "|ID|과목 / 단원 / 세부단원 / 유형|MSE|MAE|코사인|공통 토큰|실제·예측 토큰 그림|", "|---|---|---:|---:|---:|---:|---|"]
        for row in selected:
            relative = os.path.relpath(Path(project_root) / row["problem_path"], output) if project_root else row["problem_path"]
            label = " / ".join(row[key] for key in ("curriculum", "unit", "subunit", "type"))
            figures = sorted((output / "figures").glob(f"top_tokens_*_{row['id']}.png"))
            figure = f"[빈도 비교 그림]({figures[0].relative_to(output).as_posix()})" if figures else "[토큰 CSV](question_comparison.csv)"
            lines.append(f"|[{row['id']}]({relative})|{label}|{row['clipped_nonnegative_mse']:.4f}|{row['clipped_nonnegative_mae']:.4f}|{row['clipped_nonnegative_cosine_similarity']:.4f}|{row['common_top20_count']}|{figure}|")
    selected_ids = [row["id"] for row in list(reversed(ordered[-1:])) + ordered[:1]]
    if selected_ids:
        lines += ["", "## 실제 토큰으로 보는 예측의 차이", ""]
    by_id = {row["id"]: row for row in rows}
    for identifier in dict.fromkeys(selected_ids):
        row = by_id[identifier]
        actual_tokens, predicted_tokens = json.loads(row["actual_top20"]), json.loads(row["predicted_top20"])
        actual_names = {item["token"] for item in actual_tokens}
        predicted_names = {item["token"] for item in predicted_tokens}
        actual_only = [f"`{item['token']}` ({item['frequency']:.3f})" for item in actual_tokens if item["token"] not in predicted_names][:5]
        predicted_only = [f"`{item['token']}` ({item['frequency']:.3f})" for item in predicted_tokens if item["token"] not in actual_names][:5]
        lines += [f"- `{identifier}`: 상위20 공통 {row['common_top20_count']}개. 실제 상위에만: {', '.join(actual_only) or '없음'}. 예측 상위에만: {', '.join(predicted_only) or '없음'}."]
    lines += ["", "## 해석과 한계", "",
        "단어 빈도는 순서와 수식 구조를 보존하지 않는다. 상위20에서 제외됐다는 것은 전체 벡터의 값이0이라는 뜻이 아니며, 높은 빈도와 수학적 중요성을 같은 의미로 해석하지 않는다.",
        f"학습 {context.get('train_count', '미기록')}문항·테스트 {summary['test_count']}문항의 고정 분할을 사용했다. 이 평가 함수는 모델을 다시 학습하거나 테스트 결과로 설정을 선택하지 않는다. 다른 실험과 비교할 때는 데이터·어휘·분할과 선택한 모델이 일치하는지 함께 확인한다."]
    (output / "analysis.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def evaluate_for_experiment(experiment, *, make_figures=True):
    """지정한 체크포인트로만 재추론한다. 과거 모델로 대체하거나 학습하지 않는다."""
    from .Experiment import load_checkpoint, validate_predictions
    from .TorchData import file_hash

    torch.set_num_threads(2)
    selected = load_checkpoint(experiment)
    data = load_fixed_dataset(experiment.project_root, experiment.data_root)
    if data["identity"] != selected["data"]["identity"]:
        raise ValueError("검증 중 데이터 파일이 바뀌었습니다. 동일한 데이터로 다시 실행하세요.")
    checkpoint = selected["checkpoint"]
    curve_reference = checkpoint.get("learning_curve")
    history_path = experiment.checkpoint.parent / (curve_reference["path"] if curve_reference else "regression_learning_curve.json")
    if curve_reference and file_hash(history_path) != curve_reference["sha256"]:
        raise ValueError(f"{history_path}: 선택한 체크포인트에 기록된 학습 곡선 SHA와 다릅니다.")
    history = read_json(history_path) if history_path.exists() else None
    model = nn.Linear(len(data["vocabularies"]["problems"]), len(data["vocabularies"]["solutions"]))
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    with torch.no_grad():
        raw = model(data["arrays"]["problems"]["test"])
        train_raw = model(data["arrays"]["problems"]["train"])
    if not torch.isfinite(raw).all():
        raise ValueError(f"{experiment.checkpoint}: 유한하지 않은 예측이 발생했습니다.")
    actual = data["arrays"]["solutions"]["test"]
    if experiment.predictions.exists():
        saved = validate_predictions(experiment)["predictions"]
        previous = torch.tensor([row["raw_predicted_vector"] for row in saved["documents"]], dtype=torch.float32)
        if not torch.equal(previous, raw):
            raise ValueError(f"{experiment.predictions}: 선택한 체크포인트의 재추론과 저장 예측이 다릅니다.")
    output = experiment.regression_dir
    selected_paths = {"checkpoint": str(experiment.checkpoint), "predictions": str(experiment.predictions),
                      "regression_dir": str(output), "data_identity": data["identity"]}
    # 이미 게시된 결과는 같은 모델·벡터임을 검증한 뒤 바이트 그대로 보존한다.
    if (output / "vectors.json").exists():
        existing = read_json(output / "vectors.json")
        provenance = read_json(output / "provenance.json")
        existing_model = provenance.get("model_sha256") or provenance.get("source_sha256", {}).get("models/regression_model.pt")
        same = (existing_model == selected["model_sha256"] and existing["vocabulary"] == data["vocabularies"]["solutions"]
                and [r["id"] for r in existing["documents"]] == data["ids"]["test"]
                and torch.equal(torch.tensor([r["raw_predicted_vector"] for r in existing["documents"]]), raw)
                and torch.equal(torch.tensor([r["actual_vector"] for r in existing["documents"]], dtype=torch.float32), actual)
                and torch.equal(torch.tensor([r["predicted_vector"] for r in existing["documents"]]), raw.clamp_min(0)))
        if not same:
            raise ValueError(f"{output}: 다른 모델·데이터의 결과가 있습니다. 별도 result_root를 지정하세요.")
        if not experiment.predictions.exists():
            raise FileNotFoundError(f"{experiment.predictions}: 선택한 예측 파일이 없습니다. 과거 파일로 대신하지 않습니다.")
        cached_summary = read_json(output / "summary.json")
        mean = data["arrays"]["solutions"]["train"].mean(dim=0).expand_as(actual)
        if cached_summary.get("test_ids") != data["ids"]["test"]:
            raise ValueError(f"{output / 'summary.json'}: 테스트 ID/순서가 선택한 데이터와 다릅니다.")
        for name, values in (("raw", raw), ("clipped_nonnegative", raw.clamp_min(0)), ("training_mean", mean)):
            for key, value in vector_metrics(values, actual).items():
                saved_value = cached_summary.get("metrics", {}).get(name, {}).get(key)
                if saved_value is None or not math.isclose(saved_value, value, rel_tol=1e-6, abs_tol=1e-7):
                    raise ValueError(f"{output / 'summary.json'}: {name}/{key}가 선택한 모델의 재평가와 다릅니다.")
        print(json.dumps({"operation": "evaluate_without_training", **selected_paths, "cache": "verified_unchanged"}, ensure_ascii=False))
        return {**selected_paths, "summary": cached_summary, "reused": True, "training_performed": False}
    output.mkdir(parents=True, exist_ok=True)
    prediction_path = experiment.predictions if experiment.predictions.is_relative_to(output) else output / "regression_predictions.json"
    model_config = checkpoint.get("config", {key: checkpoint[key] for key in ("epochs", "learning_rate", "seed") if key in checkpoint})
    predictions = {"generation_id": data["generation_id"], "train_ids": data["ids"]["train"], "test_ids": data["ids"]["test"],
        "model_sha256": selected["model_sha256"], "data_identity": data["identity"], "config": model_config,
        "input_vocabulary": data["vocabularies"]["problems"], "vocabulary": data["vocabularies"]["solutions"],
        "prediction_policy": "clip_negative_to_zero_without_rounding",
        "documents": [{"id": identifier, "raw_predicted_vector": raw[i].tolist(),
                       "predicted_vector": raw[i].clamp_min(0).tolist(), "actual_vector": actual[i].to(torch.int64).tolist()}
                      for i, identifier in enumerate(data["ids"]["test"])]}
    write_json(prediction_path, predictions)
    mean = data["arrays"]["solutions"]["train"].mean(dim=0).expand_as(actual)
    summary = export_comparison(data["ids"]["test"], data["vocabularies"]["solutions"], actual, raw, mean, output,
        records=data["records"], project_root=experiment.project_root, data_root=experiment.data_root, history=history, make_figures=make_figures,
        data_context={"train_count": len(data["ids"]["train"]), "input_dimensions": len(data["vocabularies"]["problems"])})
    provenance = {"experiment": experiment.as_dict(), "generation_id": data["generation_id"],
        "train_ids": data["ids"]["train"], "test_ids": data["ids"]["test"], "data_identity": data["identity"],
        "model_source": str(experiment.checkpoint), "prediction_source": str(prediction_path),
        "model_sha256": selected["model_sha256"], "prediction_sha256": file_hash(prediction_path),
        "model_config": model_config, "validation": selected["validation"], "training_repeated": False,
        "learning_curve_source": str(history_path.resolve()) if history is not None else None,
        "learning_curve_sha256": file_hash(history_path) if history is not None else None,
        "test_used_for_parameter_selection": False, "forecast_storage": "raw float32 and clipped float32; no evaluation rounding",
        "training_metrics": {"raw": vector_metrics(train_raw, data["arrays"]["solutions"]["train"])}}
    write_json(output / "provenance.json", provenance)
    result = {**selected_paths, "predictions": str(prediction_path), "summary": summary, "reused": False, "training_performed": False}
    print(json.dumps({"operation": "evaluate_without_training", "checkpoint": result["checkpoint"],
                      "predictions": result["predictions"], "data_fingerprint": data["identity"]["fingerprint"],
                      "output": str(output)}, ensure_ascii=False))
    return result


def run(experiment=None):
    from .Experiment import EXPERIMENT
    return evaluate_for_experiment(experiment or EXPERIMENT)


if __name__ == "__main__":
    run()
