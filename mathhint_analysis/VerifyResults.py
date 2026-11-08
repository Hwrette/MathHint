"""저장된 최종 표·벡터·응답의 대응을 검증한다. 학습·API 호출은 하지 않는다."""

import csv
import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results/final_experiment"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def rows(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def verify(root=ROOT, results=RESULTS):
    root, results = Path(root), Path(results)
    checks = []

    def check(name, condition):
        checks.append({"check": name, "passed": bool(condition)})

    train = read(root / "data/processed/splits/train.json")
    test = read(root / "data/processed/splits/test.json")
    check("fixed_split_185_80_disjoint", len(train) == 185 and len(test) == 80 and not set(train) & set(test))
    legacy = root / "results/model_comparison_2026-11-07"
    legacy_files = read(legacy / "manifest.json")["files"]
    check("legacy_930_artifacts_unchanged", len(legacy_files) == 930 and all(
        hashlib.sha256((legacy / path).read_bytes()).hexdigest() == expected
        for path, expected in legacy_files.items()))
    for region in ("problems", "solutions"):
        vocabulary = read(root / f"data/vectors/{region}/vocabulary.json")
        for part, identifiers in (("train", train), ("test", test)):
            data = read(root / f"data/vectors/{region}/{part}_vectors.json")
            check(f"{region}_{part}_rows_and_integer_counts",
                  data["vocabulary_fitted_on"] == "train"
                  and [r["id"] for r in data["documents"]] == identifiers
                  and all(len(r["vector"]) == len(vocabulary)
                          and all(type(x) is int and x >= 0 for x in r["vector"])
                          for r in data["documents"]))

    cluster = results / "01_clustering"
    members = rows(cluster / "cluster_members.csv")
    summaries = rows(cluster / "summary.csv")
    check("clustering_8_experiments_16_metrics_2120_members", len(summaries) == 16 and len(members) == 2120)
    for name in sorted({r["experiment"] for r in members}):
        selected = [r for r in members if r["experiment"] == name]
        check(name + "_id_coverage", Counter(r["id"] for r in selected) == Counter(train + test))
    manifest = read(cluster / "manifest.json")
    # Manifest schema is recorded by FinalClustering; it hashes every other artifact.
    entries = manifest.get("files", manifest)
    if isinstance(entries, dict):
        check("clustering_artifact_hashes", all(
            hashlib.sha256((cluster / path).read_bytes()).hexdigest()
            == (value["sha256"] if isinstance(value, dict) else value)
            for path, value in entries.items()))

    regression = results / "02_regression"
    vectors = read(regression / "vectors.json")
    check("regression_test_id_order", [r["id"] for r in vectors["documents"]] == test)
    actual = np.array([r["actual_vector"] for r in vectors["documents"]], dtype=float)
    raw = np.array([r["raw_predicted_vector"] for r in vectors["documents"]], dtype=float)
    saved_truth = read(root / "data/vectors/solutions/test_vectors.json")
    check("regression_truth_exact_and_integer", np.array_equal(actual, [r["vector"] for r in saved_truth["documents"]])
          and np.array_equal(actual, actual.astype(int)))
    mean = np.array([r["vector"] for r in read(root / "data/vectors/solutions/train_vectors.json")["documents"]], dtype=float).mean(axis=0)
    for row in rows(regression / "summary.csv"):
        prediction = {"raw": raw, "clipped_nonnegative": np.maximum(raw, 0),
                      "training_mean": np.broadcast_to(mean, actual.shape)}[row["method"]]
        cosine = np.divide((prediction * actual).sum(axis=1),
                           np.maximum(np.linalg.norm(prediction, axis=1), 1e-8)
                           * np.maximum(np.linalg.norm(actual, axis=1), 1e-8)).mean()
        check("regression_" + row["method"] + "_independent_metrics",
              math.isclose(float(row["mse"]), ((prediction - actual) ** 2).mean(), rel_tol=2e-6)
              and math.isclose(float(row["mae"]), abs(prediction - actual).mean(), rel_tol=2e-6)
              and math.isclose(float(row["cosine_similarity"]), cosine, rel_tol=2e-6))

    gemini = results / "03_gemini"
    manifest = read(gemini / "config.json")
    check("gemini_config_digest", digest(manifest["config"]) == manifest["config_id"])
    records = [json.loads(line) for line in (gemini / "responses.jsonl").read_text().splitlines() if line.strip()]
    keys = [(r["id"], r["method"]) for r in records]
    check("gemini_no_duplicate_success", max(Counter((r["id"], r["method"]) for r in records if r["status"] == "success").values(), default=0) <= 1)
    check("gemini_expected_response_keys", all(i in test and m in manifest["config"]["methods"] for i, m in keys))
    check("gemini_all_records_same_config", all(r["config_id"] == manifest["config_id"] for r in records))
    for condition in "ABC":
        requests = [read(gemini / f"prompt_audit/requests/{i}/{condition}.json") for i in test]
        check(f"gemini_{condition}_80_exact_request_hashes", all(
            digest(r["user_message"]) == r["input_sha256"]
            and digest(r["sdk_request"]) == r["sdk_request_sha256"]
            and r["problem_text"] == (root / f"data/processed/problems/{r['id']}.txt").read_text(encoding="utf-8-sig")
            for r in requests))
    table = rows(gemini / "question_comparison.csv")
    check("gemini_comparison_all_80_ids", [r["id"] for r in table] == test)
    latest = {(r["id"], r["method"]): r for r in records}
    for row in rows(gemini / "summary.csv"):
        selected = [r for r in latest.values() if r["method"] == row["method"] and r["status"] == "success"]
        graded = [r for r in selected if type(r.get("evaluation", {}).get("correct")) is bool]
        correct = sum(r["evaluation"]["correct"] for r in graded)
        check("gemini_" + row["condition"] + "_summary_counts",
              int(row["successful"]) == len(selected) and int(row["graded"]) == len(graded)
              and int(row["correct_original_key"]) == correct
              and (not graded or math.isclose(float(row["accuracy_original_key"]), correct / len(graded))))
    for row in rows(gemini / "token_summary.csv"):
        values = [r.get("usage", {}).get(row["token_field"]) for r in latest.values()
                  if r["method"] == row["method"] and r["status"] == "success"]
        known = [v for v in values if v is not None]
        check("gemini_" + row["condition"] + "_" + row["token_field"] + "_table",
              int(row["provided_responses"]) == len(known)
              and row["sum_when_all_provided"] == (str(sum(known)) if values and len(known) == len(values) else "")
              and (not known or math.isclose(float(row["mean_of_known"]), sum(known) / len(known))))
    for row in table:
        for condition, method in zip("ABC", manifest["config"]["methods"]):
            saved = latest.get((row["id"], method))
            check(f"table_{row['id']}_{condition}", row[condition + "_status"] == (saved["status"] if saved else "not_run")
                  and (not saved or (
                      row[condition + "_input_sha256"] == saved["input_sha256"]
                      and row[condition + "_answer"] == str(saved.get("evaluation", {}).get("predicted_answer") or "")
                      and row[condition + "_correct_original"] == (str(saved["evaluation"]["correct"])
                          if type(saved.get("evaluation", {}).get("correct")) is bool else "")
                      and row[condition + "_total_tokens"] == (str(saved.get("usage", {}).get("total_token_count"))
                          if saved.get("usage", {}).get("total_token_count") is not None else ""))))
    expected = len(test) * 3
    successful = sum(r["status"] == "success" for r in latest.values())
    report = {"verified_at": datetime.now(timezone.utc).isoformat(),
              "checks": checks, "passed": sum(c["passed"] for c in checks),
              "failed": sum(not c["passed"] for c in checks),
              "gemini_successful": successful, "gemini_expected": expected,
              "experiment_complete": successful == expected and all(c["passed"] for c in checks),
              "limits": "Stored artifact consistency; mathematical solution validity and future network access are separate."}
    (results / "validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return report


def main():
    report = verify()
    print(json.dumps({k: v for k, v in report.items() if k not in ("checks", "limits")}, ensure_ascii=False))
    if report["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
