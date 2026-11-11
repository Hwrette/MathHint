"""Derive corrected-key Gemini results without touching raw API records or original grades.

Usage: python -m mathhint_analysis.VerifiedAnswerKey
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from itertools import combinations
from pathlib import Path

ARMS = "ABCD"
CHOICES = "①②③④⑤"
EXPERIMENTS = ("gemini_comparison", "gemini_full265")


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def blob_sha(path):
    body = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(body)).encode() + b"\0" + body).hexdigest()


def grade_bool(value):
    if value is True or value == "True":
        return True
    if value is False or value == "False":
        return False
    if value is None or value == "":
        return None
    raise ValueError("Unexpected stored grade: " + repr(value))


def get_registry(root):
    path = root / "data/curation/answer_key_corrections.json"
    records = json.loads(path.read_text(encoding="utf-8"))["corrections"]
    metadata = json.loads((root / "data/processed/metadata.json").read_text(encoding="utf-8"))["records"]
    existing = {row["id"]: row["answer_text"] for row in metadata}
    changes = {}
    for item in records:
        key = item["id"]
        source = root / item["source_solution"]
        if key in changes or not source.is_file() or blob_sha(source) != item["source_solution_blob_sha"]:
            raise ValueError("Duplicate correction or changed source file: " + key)
        if item["corrected_answer"] not in CHOICES or existing.get(key) != item["original_answer"]:
            raise ValueError("Unsupported new key or changed metadata: " + key)
        changes[key] = item
    return path, changes


def exact_mcnemar(b, c):
    d = b + c
    return min(1.0, 2.0 * sum(math.comb(d, i) for i in range(min(b, c) + 1)) / 2**d) if d else 1.0


def summarize(rows, scope):
    summary = []
    for arm in ARMS:
        success = [r for r in rows if r[arm + "_status"] == "success"]
        gradable = [r for r in success if grade_bool(r[arm + "_correct_verified"]) is not None]
        old = sum(grade_bool(r[arm + "_correct_original"]) is True for r in gradable)
        new = sum(grade_bool(r[arm + "_correct_verified"]) is True for r in gradable)
        summary.append({
            "split": scope, "condition": arm, "expected_count": len(rows),
            "success_count": len(success), "graded_count": len(gradable),
            "correct_count_original": old, "correct_count_verified": new,
            "incorrect_count_verified": len(gradable) - new,
            "accuracy_original": old / len(gradable) if gradable else "",
            "accuracy_verified": new / len(gradable) if gradable else "",
            "correction_delta": new - old, "pending_or_failed": len(rows) - len(success),
        })
    pairs = []
    for a, b in combinations(ARMS, 2):
        counts = {(True, True): 0, (False, False): 0, (True, False): 0, (False, True): 0}
        for r in rows:
            if r[a + "_status"] == r[b + "_status"] == "success":
                ga, gb = grade_bool(r[a + "_correct_verified"]), grade_bool(r[b + "_correct_verified"])
                if ga is not None and gb is not None:
                    counts[ga, gb] += 1
        n = sum(counts.values())
        pairs.append({
            "split": scope, "pair": a + "-" + b, "matched_gradable_count": n,
            "excluded_count": len(rows) - n, "both_correct": counts[True, True],
            "first_correct_second_wrong": counts[True, False],
            "first_wrong_second_correct": counts[False, True],
            "both_wrong": counts[False, False],
            "p_exact_mcnemar": exact_mcnemar(counts[True, False], counts[False, True]) if n else "",
            "p_holm_within_split": "",
        })
    ranked = sorted([r for r in pairs if isinstance(r["p_exact_mcnemar"], float)],
                    key=lambda r: r["p_exact_mcnemar"])
    maximum = 0.0
    for i, r in enumerate(ranked):
        maximum = max(maximum, min(1.0, (len(ranked) - i) * r["p_exact_mcnemar"]))
        r["p_holm_within_split"] = maximum
    return summary, pairs


def regrade(root, experiment, registry_path, corrections):
    folder = root / "results/final_experiment_2" / experiment
    source = folder / "question_comparison.csv"
    if not source.is_file():
        return None
    rows = read_csv(source)
    expected = 80 if experiment == "gemini_comparison" else 265
    if len(rows) != expected or len(set(row["id"] for row in rows)) != expected:
        raise ValueError("Unexpected source question count or duplicate IDs: " + str(source))
    matched = set()
    for row in rows:
        correction = corrections.get(row["id"])
        row["answer_for_scoring"] = correction["corrected_answer"] if correction else row["original_answer"]
        row["key_status"] = ("verified_correction" if correction else "original_not_independently_verified")
        if correction:
            if row["original_answer"] != correction["original_answer"] or row["split"] != correction["split"]:
                raise ValueError("Stored original key/split changed: " + row["id"])
            matched.add(row["id"])
        for arm in ARMS:
            current = grade_bool(row[arm + "_correct_original"])
            if row[arm + "_status"] == "success" and current is not None and correction:
                # The saved final-answer field is explicit, not a substring of the generated reasoning.
                observed = (row[arm + "_answer"] or "").strip()
                if len(observed) != 1 or observed not in CHOICES:
                    raise ValueError("Cannot verify non-choice answer: " + row["id"] + "/" + arm)
                revised = observed == correction["corrected_answer"]
            else:
                revised = current
            if row[arm + "_status"] != "success" and current is not None:
                raise ValueError("Non-success has original boolean grade: " + row["id"] + "/" + arm)
            row[arm + "_correct_verified"] = str(revised) if revised is not None else ""
    if matched != set(corrections):
        raise ValueError("Correction ID missing from experiment: " + str(set(corrections) - matched))
    scopes = [("test", rows)]
    if experiment == "gemini_full265":
        scopes = [("all265", rows), ("train", [r for r in rows if r["split"] == "train"]),
                  ("test", [r for r in rows if r["split"] == "test"])]
        if [len(x[1]) for x in scopes] != [265, 185, 80]:
            raise ValueError("Unexpected full-dataset split")
    elif {r["split"] for r in rows} != {"test"}:
        raise ValueError("Unexpected test-only split")
    summary, paired = [], []
    for name, part in scopes:
        a, b = summarize(part, name)
        summary += a
        paired += b
    out = folder / "key_corrected"
    write_csv(out / "question_comparison.csv", rows)
    write_csv(out / "summary.csv", summary)
    write_csv(out / "paired_comparison.csv", paired)
    audit = {
        "schema_version": 1, "source_csv": str(source.relative_to(root)),
        "source_csv_sha256": sha256(source),
        "correction_registry": str(registry_path.relative_to(root)),
        "correction_registry_sha256": sha256(registry_path),
        "verified_correction_ids": sorted(matched), "question_count": len(rows),
        "source_mutated": False, "api_requests_made": 0,
        "grading_rule": "Regrade only verified key-conflict IDs from saved explicit answer; retain original score alongside corrected score",
        "caution": "Other source keys have not been independently mathematically proved. Unfinished requests are excluded.",
    }
    (out / "audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# Reviewed-key corrected Gemini scores", "",
        "Source data, original saved scores, response logs and prompt hashes remain immutable.",
        "Verified correction: trig_1_010 changes from ④ to ② (9/5).",
        "Other rows retain the existing original key; this is not independent proof for every solution.",
        "", "|Split|Condition|Gradable|Original correct|Corrected correct|Corrected accuracy|",
        "|---|---|---:|---:|---:|---:|"]
    for r in summary:
        value = r["accuracy_verified"]
        accuracy = f"{value:.2%}" if isinstance(value, float) else "—"
        lines.append(f"|{r['split']}|{r['condition']}|{r['graded_count']}|"
                     f"{r['correct_count_original']}|{r['correct_count_verified']}|{accuracy}|")
    lines.extend(["", "The full265 run includes 185 training (in-sample) and 80 test questions.",
                  "Pending requests are not counted as wrong. Partial completion is nonrandom.",
                  "", "Files: question_comparison.csv, summary.csv, paired_comparison.csv, audit.json.",
                  "Rebuild without API calls: python -m mathhint_analysis.VerifiedAnswerKey", ""])
    (out / "README.md").write_text("\n".join(lines), encoding="utf-8")
    return {"scope": experiment, "rows": len(rows), "summary": summary, "out": str(out.relative_to(root))}


def run(root=None):
    root = Path(root or Path(__file__).resolve().parents[1]).resolve()
    registry_path, corrections = get_registry(root)
    completed = []
    for experiment in EXPERIMENTS:
        record = regrade(root, experiment, registry_path, corrections)
        if record:
            completed.append(record)
    if not completed:
        raise FileNotFoundError("No saved Gemini comparison source CSVs")
    return completed


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=None)
    for result in run(parser.parse_args().root):
        print(result["out"], result["rows"])
