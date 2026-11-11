"""Non-destructive corrected-key grading fixtures; no API calls or model training."""
import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from mathhint_analysis.VerifiedAnswerKey import get_registry, regrade, read_csv


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def choice_row(identifier, split, grades=None):
    grades = grades or (True, True, True, True)
    reference = "④" if identifier == "trig_1_010" else "③"
    row = {"id": identifier, "split": split, "original_answer": reference}
    for condition, grade in zip("ABCD", grades):
        row[condition + "_status"] = "success"
        row[condition + "_answer"] = "②" if identifier == "trig_1_010" else "③"
        row[condition + "_correct_original"] = str(grade)
        row[condition + "_total_token_count"] = "500"
    return row


class VerifiedAnswerKeyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        src = self.root / "data/processed/solutions/trig_1_010.txt"
        src.parent.mkdir(parents=True)
        src.write_text("[정답] ④\nk tan t = 9/5\n", encoding="utf-8")
        content = src.read_bytes()
        blob = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()
        metadata = self.root / "data/processed/metadata.json"
        metadata.write_text(json.dumps({"records": [
            {"id": "trig_1_010", "answer_text": "④"}]}), encoding="utf-8")
        registry = self.root / "data/curation/answer_key_corrections.json"
        registry.parent.mkdir(parents=True)
        registry.write_text(json.dumps({"corrections": [{
            "id": "trig_1_010", "original_answer": "④", "corrected_answer": "②",
            "split": "test", "source_solution": "data/processed/solutions/trig_1_010.txt",
            "source_solution_blob_sha": blob}]}), encoding="utf-8")
        self.registry, self.corrections = get_registry(self.root)
        self.test80 = [choice_row("trig_1_010", "test", (False, False, False, False)),
                       choice_row("trig_2_022", "test", (False, True, True, True)),
                       choice_row("trig_3_034", "test", (True, False, False, False))]
        self.test80.extend(choice_row("test_%03d" % i, "test") for i in range(77))

    def test_80_corrected_scores_without_touching_original(self):
        source = self.root / "results/final_experiment_2/gemini_comparison/question_comparison.csv"
        write_csv(source, self.test80)
        before = source.read_bytes()
        result = regrade(self.root, "gemini_comparison", self.registry, self.corrections)
        self.assertEqual(result["rows"], 80)
        self.assertEqual(source.read_bytes(), before)
        summary = read_csv(source.parent / "key_corrected/summary.csv")
        self.assertEqual(len(summary), 4)
        self.assertTrue(all(x["correct_count_original"] == "78" for x in summary))
        self.assertTrue(all(x["correct_count_verified"] == "79" for x in summary))
        self.assertTrue(all(x["accuracy_verified"] == "0.9875" for x in summary))
        corrected = read_csv(source.parent / "key_corrected/question_comparison.csv")
        target = next(r for r in corrected if r["id"] == "trig_1_010")
        self.assertEqual(target["answer_for_scoring"], "②")
        self.assertEqual(target["A_correct_original"], "False")
        self.assertEqual(target["A_correct_verified"], "True")
        self.assertEqual(target["A_total_token_count"], "500")
        pairs = read_csv(source.parent / "key_corrected/paired_comparison.csv")
        ab = next(x for x in pairs if x["pair"] == "A-B")
        self.assertEqual(ab["both_correct"], "78")
        self.assertEqual(ab["first_correct_second_wrong"], "1")
        self.assertEqual(ab["first_wrong_second_correct"], "1")
        self.assertEqual(ab["both_wrong"], "0")

    def test_partial_full265_preserves_pending_and_in_sample_split(self):
        rows = list(self.test80)
        for i in range(185):
            row = choice_row("train_%03d" % i, "train")
            if i >= 49 or i == 48:
                for arm in ("ABCD" if i >= 49 else "D"):
                    row[arm + "_status"] = "not_run"
                    row[arm + "_answer"] = ""
                    row[arm + "_correct_original"] = ""
            rows.append(row)
        source = self.root / "results/final_experiment_2/gemini_full265/question_comparison.csv"
        write_csv(source, rows)
        before = source.read_bytes()
        regrade(self.root, "gemini_full265", self.registry, self.corrections)
        self.assertEqual(source.read_bytes(), before)
        summary = {(r["split"], r["condition"]): r for r in
                   read_csv(source.parent / "key_corrected/summary.csv")}
        self.assertEqual(summary["all265", "A"]["correct_count_verified"], "128")
        self.assertEqual(summary["all265", "A"]["graded_count"], "129")
        self.assertEqual(summary["all265", "D"]["correct_count_verified"], "127")
        self.assertEqual(summary["all265", "D"]["graded_count"], "128")
        self.assertEqual(summary["train", "A"]["graded_count"], "49")
        self.assertEqual(summary["train", "D"]["graded_count"], "48")
        self.assertEqual(summary["test", "B"]["correct_count_verified"], "79")
        self.assertEqual(summary["all265", "D"]["pending_or_failed"], "137")

    def test_registry_rejects_changed_original_solution(self):
        source = self.root / "data/processed/solutions/trig_1_010.txt"
        source.write_text("[정답] ②\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            get_registry(self.root)

    def test_regrade_rejects_original_key_drift(self):
        source = self.root / "results/final_experiment_2/gemini_comparison/question_comparison.csv"
        rows = list(self.test80)
        rows[0] = {**rows[0], "original_answer": "②"}
        write_csv(source, rows)
        with self.assertRaises(ValueError):
            regrade(self.root, "gemini_comparison", self.registry, self.corrections)


if __name__ == "__main__":
    unittest.main()
