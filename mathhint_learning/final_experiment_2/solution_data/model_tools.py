"""두 지도 모델이 공유하는 원시 빈도 평가·동결·예측·읽기 자료.

학습 알고리즘이나 Gemini 호출은 포함하지 않는다.
"""

import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path

import torch

from ...TorchData import file_hash, identity_digest, read_json
from .common import write_csv as _atomic_csv, write_json
from ...VectorComparison import vector_metrics, top_tokens, token_overlap
from mathhint_analysis.token_analysis.roles import classify_token


ROOT = Path(__file__).resolve().parents[3]
TOP_K = 20


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def write_csv(path, rows):
    rows = list(rows)
    if not rows:
        raise ValueError(f"빈 표를 저장하지 않습니다: {path}")
    path = Path(path)
    fields = list(dict.fromkeys(key for row in rows for key in row))
    _atomic_csv(path, rows, fields=fields)


def metrics(prediction, actual, vocabulary):
    """빈도 척도의 오차와 양의 상위20개 집합을 분리한다. P@20 분모는20이다."""
    prediction, actual = torch.as_tensor(prediction).float(), torch.as_tensor(actual).float()
    if prediction.ndim == 1:
        prediction, actual = prediction[None, :], actual[None, :]
    if prediction.shape != actual.shape or prediction.shape[1] != len(vocabulary):
        raise ValueError("예측·실제 벡터와 출력 어휘의 차원이 다릅니다.")
    details = [token_overlap(top_tokens(answer, vocabulary), top_tokens(pred.clamp_min(0), vocabulary))
               for pred, answer in zip(prediction, actual)]
    count = len(details)
    recalls = [row["recall_of_actual_top20"] for row in details if row["recall_of_actual_top20"] is not None]
    return {**vector_metrics(prediction, actual),
            "precision_at_20": sum(row["precision_at_20"] for row in details) / count,
            "recall_at_20": sum(recalls) / len(recalls) if recalls else None,
            "mean_common_top20_count": sum(row["common_top20_count"] for row in details) / count,
            "actual_fewer_than_20": sum(row["actual_top_count"] < TOP_K for row in details),
            "predicted_fewer_than_20": sum(row["predicted_top_count"] < TOP_K for row in details),
            "n": count}


def rank_key(result, order=0):
    """최대 검증 P@20, 동률 최소 보정 MSE, 다시 동률 사전 후보 순서."""
    return (-result["precision_at_20"], result["mse"], order)


def save_checkpoint(output, data, model, model_type, selection, *, extra=None):
    """모델 확정 직후 저장한다. 이 호출에는 테스트 타깃이 필요하지 않다."""
    output = Path(output)
    path = output / "checkpoints/final.pt"
    path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint = {"schema_version": 1, "model_type": model_type,
                  "model_state_dict": model.state_dict(), "dataset_id": data["dataset_id"],
                  "input_dim": len(data["vocabularies"]["problems"]),
                  "output_dim": len(data["vocabularies"]["solutions"]),
                  "input_vocabulary": data["vocabularies"]["problems"],
                  "output_vocabulary": data["vocabularies"]["solutions"],
                  "train_ids": data["ids"]["train"], "test_ids": data["ids"]["test"],
                  "fit_ids": data["ids"]["fit"], "validation_ids": data["ids"]["validation"],
                  "data_identity": data["identity"], "selection": selection,
                  "saved_before_loading_test_targets": "test" not in data["arrays"]["solutions"],
                  "final_refit_training_count": len(data["ids"]["train"]),
                  "architecture": str(model), "saved_at": utc_now(), **(extra or {})}
    if not checkpoint["saved_before_loading_test_targets"]:
        raise ValueError("최종 체크포인트는 테스트 타깃을 읽기 전에 확정해야 합니다.")
    temporary = path.with_suffix(".tmp")
    torch.save(checkpoint, temporary)
    temporary.replace(path)
    return path


def category_bucket(token):
    category = classify_token(token, region="solutions")["category"]
    if category in ("표시용 LaTeX 명령어", "괄호·수식 구조 기호", "해설지 고정 양식"):
        return "서식·괄호·고정 양식"
    if category in ("LaTeX 변수명", "LaTeX 숫자"):
        return "숫자·변수명"
    if category in ("수학 개념 자연어", "LaTeX 수학 명령어", "연산·관계 기호"):
        return "수학 개념·명령·연산"
    if category == "풀이 방법 자연어":
        return "풀이 방법 자연어"
    return "일반·불확실 토큰"


def export_final(root, output, data, model, selection, history, validation_prediction,
                 *, validation_history=None):
    """동결된 모델을 평가한다. 모델을 학습하거나 원시 실제 해설을 API에 넘기지 않는다."""
    root, output = Path(root), Path(output)
    output.mkdir(parents=True, exist_ok=True)
    checkpoint = output / "checkpoints/final.pt"
    saved = torch.load(checkpoint, map_location="cpu", weights_only=True)
    if saved["dataset_id"] != data["dataset_id"] or not saved["saved_before_loading_test_targets"]:
        raise ValueError("동결 체크포인트의 데이터/선행 확정 기록이 다릅니다.")
    if any(not torch.equal(value.detach().cpu(), saved["model_state_dict"][name])
           for name, value in model.state_dict().items()):
        raise ValueError("최종 체크포인트 이후 모델 가중치가 변경되었습니다.")
    vocabulary = data["vocabularies"]["solutions"]
    model.eval()
    with torch.no_grad():
        predictions = {part: model(data["arrays"]["problems"][part]).detach().cpu()
                       for part in ("train", "test")}
    summaries = []
    val_actual = data["arrays"]["solutions"]["validation"]
    val_mean = data["arrays"]["solutions"]["fit"].mean(0).expand_as(val_actual)
    for phase, actual, raw, mean in (
            ("validation", val_actual, validation_prediction, val_mean),
            *[(part, data["arrays"]["solutions"][part], predictions[part],
               data["arrays"]["solutions"]["train"].mean(0).expand_as(predictions[part]))
              for part in ("train", "test")]):
        for name, values in (("training_mean", mean), ("raw", raw), ("clipped_nonnegative", raw.clamp_min(0))):
            summaries.append({"split": phase, "method": name, **metrics(values, actual, vocabulary)})
    write_csv(output / "summary.csv", summaries)
    write_json(output / "summary.json", {"dataset_id": data["dataset_id"], "metrics": summaries,
        "prediction_rounding": "none", "negative_correction": "clip_min_0",
        "top20_policy": {"positive_only": True, "rank_before_rounding": True, "tie_break": "vocabulary index",
                         "precision_denominator": 20, "recall_denominator": "actual positive top20 count",
                         "fewer_than20": "use available positive tokens; do not pad"},
        "test_negative_prediction_ratio": float((predictions["test"] < 0).float().mean()),
        "train_negative_prediction_ratio": float((predictions["train"] < 0).float().mean()),
        "full265_vocabulary_transductive": True,
        "test_targets_used_for_model_selection": False})
    rows, categories = [], []
    for i, identifier in enumerate(data["ids"]["test"]):
        raw, actual = predictions["test"][i], data["arrays"]["solutions"]["test"][i]
        actual_top, predicted_top = top_tokens(actual, vocabulary), top_tokens(raw.clamp_min(0), vocabulary)
        average = data["arrays"]["solutions"]["train"].mean(0)
        row = {"id": identifier, **{key: data["records"][identifier].get(key, "") for key in
                 ("curriculum", "unit", "subunit", "type")},
               "problem_path": f"data/processed/problems/{identifier}.txt",
               "solution_path": f"data/processed/solutions/{identifier}.txt"}
        for name, values in (("training_mean", average), ("raw", raw), ("clipped_nonnegative", raw.clamp_min(0))):
            row.update({name + "_" + key: value for key, value in metrics(values, actual, vocabulary).items()})
        row.update(token_overlap(actual_top, predicted_top))
        row.update(actual_top20=json.dumps(actual_top, ensure_ascii=False),
                   predicted_top20=json.dumps(predicted_top, ensure_ascii=False))
        rows.append(row)
        for source, tokens in (("actual", actual_top), ("predicted", predicted_top)):
            for token in tokens:
                categories.append({"id": identifier, "source": source, "token": token["token"],
                                   "frequency": token["frequency"], "category": category_bucket(token["token"])})
    write_csv(output / "question_comparison.csv", rows)
    write_csv(output / "top20_tokens.csv", categories)
    category_rows = []
    for source in ("actual", "predicted"):
        relevant = [row for row in categories if row["source"] == source]
        for category in ("서식·괄호·고정 양식", "숫자·변수명", "수학 개념·명령·연산", "풀이 방법 자연어", "일반·불확실 토큰"):
            count = sum(row["category"] == category for row in relevant)
            category_rows.append({"source": source, "category": category, "count": count,
                                  "selected_tokens": len(relevant), "ratio": count / len(relevant) if relevant else None})
    write_csv(output / "top20_category_composition.csv", category_rows)
    documents = [{"id": identifier, "split": part, "raw_predicted_vector": predictions[part][i].tolist(),
                  "predicted_vector": predictions[part][i].clamp_min(0).tolist()}
                 for part in ("train", "test") for i, identifier in enumerate(data["ids"][part])]
    path = output / "predictions/all_predictions.json"
    write_json(path, {"dataset_id": data["dataset_id"], "vocabulary": vocabulary,
        "input_vocabulary": data["vocabularies"]["problems"], "documents": documents,
        "prediction_policy": "raw_float32_and_clip_min_zero; no_integer_rounding",
        "actual_solution_vectors_included": False})
    write_csv(output / "training_history.csv", history)
    if validation_history:
        write_csv(output / "validation_history.csv", validation_history)
    manifest = {"schema_version": 1, "frozen": True, "frozen_before_test": True,
        "dataset_id": data["dataset_id"], "architecture": str(model),
        "selection_basis": "internal_validation_precision_at_20",
        "selected_configuration": selection["selected_configuration"],
        "selection_sha256": file_hash(output / "selection.json"),
        "checkpoint": {"path": "checkpoints/final.pt", "sha256": file_hash(checkpoint)},
        "predictions": {"path": "predictions/all_predictions.json", "sha256": file_hash(path)},
        "train_ids": data["ids"]["train"], "test_ids": data["ids"]["test"],
        "test_predictions_count": len(data["ids"]["test"]), "train_predictions_count": len(data["ids"]["train"]),
        "frozen_at": selection["frozen_at"], "finalized_at": utc_now(),
        "test_metrics": next(r for r in summaries if r["split"] == "test" and r["method"] == "clipped_nonnegative"),
        "validation_metrics": next(r for r in summaries if r["split"] == "validation" and r["method"] == "clipped_nonnegative")}
    write_json(output / "model_manifest.json", manifest)
    write_model_reports(root, output, data)
    return manifest


def _rows(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def verify_manifest(output, dataset_id):
    output = Path(output)
    manifest = read_json(output / "model_manifest.json")
    if not manifest["frozen"] or manifest["dataset_id"] != dataset_id:
        raise ValueError("모델이 확정되지 않았거나 데이터 ID가 다릅니다.")
    for key in ("checkpoint", "predictions"):
        if file_hash(output / manifest[key]["path"]) != manifest[key]["sha256"]:
            raise ValueError(f"동결 모델 {key} 파일이 변경되었습니다.")
    if file_hash(output / "selection.json") != manifest["selection_sha256"]:
        raise ValueError("모델 선택 기록이 변경되었습니다.")
    return manifest


def write_model_reports(root, output, data):
    """저장한 CSV·JSON만으로 모델 설명과 그림을 다시 생성한다."""
    output, root = Path(output), Path(root)
    manifest = verify_manifest(output, data["dataset_id"])
    summary = _rows(output / "summary.csv")
    comparison = _rows(output / "model_comparison.csv")
    questions = _rows(output / "question_comparison.csv")
    info = read_json(output / "summary.json")
    labels = {"training_mean": "학습 평균 기준선", "raw": "원시 예측", "clipped_nonnegative": "음수→0 보정"}
    lines = [f"# {'선형회귀' if output.name == 'regression' else 'nn.Sequential 비선형 모델'} · 원본 해설 빈도 예측", "",
        "최종 구조:", "", "```text", manifest["architecture"], "```", "",
        "검증 Precision@20을 최대화하고 동률이면 음수 보정 MSE, 사전 후보 순서로 선택했다. 테스트80의 실제 해설은 선택·조기 종료에 사용하지 않았다.", "",
        "## 검증과 최종 테스트", "",
        "|범위|방법|MSE ↓|MAE ↓|코사인 ↑|Precision@20 ↑|Recall@20 ↑|공통 토큰 수/20|", "|---|---|---:|---:|---:|---:|---:|---:|"]
    for phase in ("validation", "test"):
        for row in summary:
            if row["split"] == phase:
                values = [f"{float(row[key]):.4f}" if row[key] != "" else "—" for key in
                          ("mse", "mae", "cosine_similarity", "precision_at_20", "recall_at_20", "mean_common_top20_count")]
                lines.append(f"|{'내부 검증37' if phase == 'validation' else '최종 테스트80'}|{labels[row['method']]}|" + "|".join(values) + "|")
    if output.name == "regression":
        selected = manifest["selected_configuration"]
        if selected["family"] == "ridge":
            lines += ["", f"최종 계열은 **Ridge(α={selected['alpha']:g})**다. 초기 nn.Linear/Adam500에폭, 원시 좌표 Ridge, fit148에서만 구한 표준편차로 푸는 Ridge를 비교하고 검증 최적 α의 근방2개를 추가했다. "
                "표준화는 정보가 사라지는 문항별 L2 정규화가 아니며, 풀어진 계수를 다시 원시 입력의 선형 가중치·절편으로 변환했다. 최종185 리핏에서도185만으로 평균·스케일을 추정했다.", "",
                "Ridge는 닫힌 해를 계산하므로 최종 모델에 반복 학습 에폭이 없다. 아래 손실 곡선은 초기 Adam 후보의 경과와 저장된 후보별 검증 비교이며, 닫힌 해의 epoch0을 가짜 반복 곡선으로 표시하지 않는다."]
    fit_row = next(row for row in summary if row["split"] == "train" and row["method"] == "clipped_nonnegative")
    test_row = next(row for row in summary if row["split"] == "test" and row["method"] == "clipped_nonnegative")
    baseline = next(row for row in summary if row["split"] == "test" and row["method"] == "training_mean")
    improvement = float(test_row["precision_at_20"]) - float(baseline["precision_at_20"])
    lines += ["", f"테스트 P@20의 평균 기준선 대비 차이: **{improvement:+.4f}**. 학습185의 보정 MSE {float(fit_row['mse']):.4f}와 테스트80 MSE {float(test_row['mse']):.4f}의 차이를 함께 읽는다. 학습 성능만 좋아진 것을 개선으로 간주하지 않는다.", "",
        f"테스트 원시 출력의 음수 비율은 {info['test_negative_prediction_ratio']:.2%}다. 실제 빈도는 정수이며 회귀 예측은 반올림하지 않은 실수로 보존한다.", "",
        "![원시 타깃 척도의 테스트 지표](figures/test_metrics.png)", "",
        "![학습·검증 손실 기록](figures/learning_history.png)", "",
        "## 개선 과정", "", "|후보|검증 P@20|검증 MSE|설정|", "|---|---:|---:|---|"]
    for row in comparison:
        lines.append(f"|{row.get('candidate_id', row.get('candidate', ''))}|{float(row['precision_at_20']):.4f}|{float(row['mse']):.4f}|`{row.get('configuration', '')}`|")
    lines += ["", "[모든 후보 비교](model_comparison.csv) · [모델 선택·중단 규칙](selection.json) · [학습 기록](training_history.csv)", "",
        "## 문항과 상위 토큰", "", "[테스트80 문항별 오차·실제/예측 토큰](question_comparison.csv) · [상위토큰 범주](top20_category_composition.csv) · [전 문항 예측·모델 출처](model_manifest.json)", "",
        "![문항별 상위20 공통 토큰 수](figures/top20_distribution.png)", "",
        "![상위20의 설명용 범주](figures/top20_categories.png)", "",
        "범주는 토큰 역할의 검토 보조 분류다. 빈도가 높거나 집합이 많이 겹치는 것이 풀이 전략의 타당성을 입증하지 않는다.", "",
        "|관찰 사례|문항|코사인|공통 토큰 수|", "|---|---|---:|---:|"]
    ordered = sorted(questions, key=lambda row: (float(row["clipped_nonnegative_cosine_similarity"]), row["id"]))
    for title, chosen in (("낮은 코사인", ordered[:2]), ("높은 코사인", ordered[-2:])):
        for row in chosen:
            link = os.path.relpath(root / f"data/processed/problems/{row['id']}.txt", output)
            lines.append(f"|{title}|[{row['id']}]({link})|{float(row['clipped_nonnegative_cosine_similarity']):.4f}|{row['common_top20_count']}|")
    lines += ["", "## 대표 문항의 실제·예측 빈도", ""]
    for row in (ordered[0], ordered[-1]):
        lines += [f"![{row['id']} 실제·예측 상위 토큰](figures/example_{row['id']}.png)", ""]
    lines += ["전체265의 어휘를 미리 구성한 탐색적 조건이다. 테스트 표현이 어휘와 불용어 검토에 포함됐으므로 완전히 미관측인 일반화 검증이 아니다. 한 문제의 특정 원본 해설을 타깃으로 삼았으며 다른 올바른 풀이의 토큰은 다를 수 있다.", "",
        "새 Gemini 효과는 이 벡터 지표와 다른 평가 대상이다. 이 문서만으로 풀이 정확도·시스템 계산 효율 향상을 주장하지 않는다.", "",
        "[전체2차 연구](../README.md) · [공통 데이터](../solution_data/README.md)", ""]
    text = "\n".join(lines)
    (output / "README.md").write_text(text, encoding="utf-8")
    target_missing = int((data["arrays"]["solutions"]["train"].sum(0) == 0).sum())
    input_missing = int((data["arrays"]["problems"]["train"].sum(0) == 0).sum())
    analysis = ["# 모델 평가의 해석과 한계", "", "[핵심 수치·구조·그림](README.md) · [전체 후보](model_comparison.csv) · [테스트80 문항 비교](question_comparison.csv)", "",
        "## 확인한 결과", "",
        f"학습185의 보정 MSE={float(fit_row['mse']):.6f}, 테스트80 MSE={float(test_row['mse']):.6f}다. 학습셋 P@20={float(fit_row['precision_at_20']):.6f}, 테스트 P@20={float(test_row['precision_at_20']):.6f}이며, 테스트의 평균 기준선 대비 P@20 차이는{improvement:+.6f}다.", "",
        "학습과 테스트 성능 차이는 과적합 가능성과 자료 난이도 차이를 함께 반영한다. 내부 검증과 테스트는 서로 다른 문항이므로 테스트가 검증보다 좋다는 사실을 모델 선택 근거로 되돌려 사용하지 않는다.", "",
        "## 모델 선택", "",
        "검증37은 원래 학습185에서만 분리했다. 검증의 평균 기준선은 fit148의 해설 평균이고 테스트 기준선은 최종 학습185 평균이다. P@20의 동률만 MSE로 판정했다. 더 낮은 MSE를 얻은 후보가 있어도 P@20이 더 낮으면 선택하지 않았다. 모든 주요 시도와 개선/중단 근거는 selection.json과 model_comparison.csv에 남겼다.", "",
        "## 표현의 한계", "",
        f"전체 어휘에는 최종 학습185에서 빈도가 항상0인 문제 좌표{input_missing}개와 해설 좌표{target_missing}개도 있다. 전체265의 어휘를 복원했다고 해서185개 학습만으로 그 좌표의 관계를 학습할 수 있는 것은 아니다.", "",
        "상위20은 양의 빈도를 반올림 전 정렬하며 동률은 출력 어휘 순서다. P@20은 고정20을 분모로 사용하고 Recall@20은 실제 양의 상위토큰 개수를 분모로 사용한다. 실제 양의 토큰이20개 미만이면 P@20의 최대값도1보다 작을 수 있다. 범주 비율은 빈도 가중치가 아닌 선택된 토큰 좌표 수의 비율이다.", "",
        "원본 해설과 빈도가 다르다는 이유로 수학적으로 틀린 풀이라고 판정하지 않는다. 다른 올바른 해법이 존재할 수 있으며, Gemini의 실제 정답률·토큰 사용량은 별도 실험으로 평가한다.", ""]
    (output / "analysis.md").write_text("\n".join(analysis), encoding="utf-8")
    _plots(output, summary, questions)
    return manifest


def _plots(output, summaries, questions):
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/mathhint-mpl")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    font = Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
    if font.exists():
        font_manager.fontManager.addfont(str(font))
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=str(font)).get_name()
    plt.rcParams.update({"axes.unicode_minus": False, "font.size": 9})
    folder = output / "figures"
    folder.mkdir(exist_ok=True)
    rows = [row for row in summaries if row["split"] == "test"]
    fig, axes = plt.subplots(1, 4, figsize=(15, 4))
    for ax, metric, title in zip(axes, ("mse", "mae", "cosine_similarity", "precision_at_20"),
                                ("MSE ↓", "MAE ↓", "코사인 ↑", "Precision@20 ↑")):
        bars = ax.bar(["평균 기준선", "원시", "음수 보정"], [float(row[metric]) for row in rows], color=[".8", ".5", ".2"])
        ax.bar_label(bars, fmt="%.3f", fontsize=8)
        ax.set_title(title)
        ax.set_ylim(0, max(float(row[metric]) for row in rows) * 1.18)
    fig.suptitle("테스트80 · 원본 해설의 빈도 척도 · 정답률 지표 아님")
    fig.tight_layout(); fig.savefig(folder / "test_metrics.png", dpi=180); plt.close(fig)
    history = _rows(output / "training_history.csv")
    fig, (ax, comparison_ax) = plt.subplots(1, 2, figsize=(14, 4.7))
    groups = {}
    for row in history:
        groups.setdefault(row.get("candidate_id", row.get("phase", "model")), []).append(row)
    for name, points in groups.items():
        usable = [row for row in points if row.get("train_mse", "") != ""]
        if len(usable) > 1:
            ax.plot([int(row.get("epoch", i)) for i, row in enumerate(usable)], [float(row["train_mse"]) for row in usable], label=name, linewidth=.9)
    validation_path = output / "validation_history.csv"
    if validation_path.exists():
        saved_vals = _rows(validation_path)
        validation_field = "validation_mse" if any(row.get("validation_mse", "") != "" for row in saved_vals) else "validation_clipped_mse"
        vals = [row for row in saved_vals if row.get(validation_field, "") != ""]
        if vals:
            ax.plot([int(row["epoch"]) for row in vals], [float(row[validation_field]) for row in vals], "k--o", markersize=3,
                    label="선택 구성 검증 MSE" if validation_field == "validation_mse" else "선택 구성 검증 음수 보정 MSE")
    ax.set(xlabel="epoch · 닫힌 해의 반복 곡선 없음", ylabel="MSE", title="학습 손실과 저장 검증 기록")
    if ax.get_legend_handles_labels()[0]:
        ax.legend(fontsize=7, ncol=2)
    candidate_rows = _rows(output / "model_comparison.csv")
    candidate_names = [row.get("candidate_id", row.get("candidate", "")) for row in candidate_rows]
    comparison_ax.bar(range(len(candidate_rows)), [float(row["precision_at_20"]) for row in candidate_rows], color=".45")
    comparison_ax.set_xticks(range(len(candidate_rows)), candidate_names, rotation=60, ha="right", fontsize=7)
    comparison_ax.set(ylabel="검증 Precision@20", title="검증 결과만으로 후보 개선·선택")
    fig.tight_layout(); fig.savefig(folder / "learning_history.png", dpi=180); plt.close(fig)
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist([int(row["common_top20_count"]) for row in questions], bins=range(22), color=".4", edgecolor="white")
    ax.set(xlabel="실제·예측 상위20 공통 토큰 수", ylabel="테스트 문항 수", title="테스트80 · 양의 빈도 상위 토큰")
    fig.tight_layout(); fig.savefig(folder / "top20_distribution.png", dpi=180); plt.close(fig)
    cats = _rows(output / "top20_category_composition.csv")
    labels = list(dict.fromkeys(row["category"] for row in cats))
    fig, ax = plt.subplots(figsize=(10, 4))
    for offset, source, name, color in ((-.18, "actual", "원본 해설", ".8"), (.18, "predicted", "예측 해설", ".3")):
        values = [next(float(row["ratio"]) for row in cats if row["source"] == source and row["category"] == category) for category in labels]
        ax.bar([i + offset for i in range(len(labels))], values, width=.35, label=name, color=color)
    ax.set_xticks(range(len(labels)), labels, rotation=12)
    ax.set(ylabel="선택된 토큰 좌표 중 비율", title="테스트80 · 실제/예측 상위20의 설명용 범주")
    ax.legend(); fig.tight_layout(); fig.savefig(folder / "top20_categories.png", dpi=180); plt.close(fig)
    ordered = sorted(questions, key=lambda row: (float(row["clipped_nonnegative_cosine_similarity"]), row["id"]))
    for row in (ordered[0], ordered[-1]):
        actual = {item["token"]: item["frequency"] for item in json.loads(row["actual_top20"])}
        predicted = {item["token"]: item["frequency"] for item in json.loads(row["predicted_top20"])}
        chosen = sorted(set(actual) | set(predicted), key=lambda token: (-max(actual.get(token, 0), predicted.get(token, 0)), token))
        fig, ax = plt.subplots(figsize=(10, max(5, len(chosen) * .23)))
        ax.barh([i - .18 for i in range(len(chosen))], [actual.get(token, 0) for token in chosen], height=.35, color=".8", label="실제 빈도")
        ax.barh([i + .18 for i in range(len(chosen))], [predicted.get(token, 0) for token in chosen], height=.35, color=".3", label="예측 빈도")
        ax.set_yticks(range(len(chosen)), chosen); ax.invert_yaxis()
        ax.set(xlabel="실제/예측 빈도 · 예측값 정수 반올림 없음", title=f"테스트 {row['id']} · 각 상위20의 합집합")
        ax.legend(); fig.tight_layout(); fig.savefig(folder / f"example_{row['id']}.png", dpi=180); plt.close(fig)
