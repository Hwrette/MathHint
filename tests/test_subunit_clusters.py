"""소단원 수 결정과 군집별 결과 내보내기의 데이터 대응을 확인한다."""

import contextlib
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

try:
    import torch
except ModuleNotFoundError:
    torch = None

if torch is not None:
    from mathhint_learning import TorchKMeans
    from mathhint_learning.ClusterReport import save_cluster_reports


def make_dataset(root):
    def save(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    ids = {"train": ["a", "b", "c", "d"], "test": ["e", "f", "g"]}
    values = {"a": 0, "b": 10, "c": 100, "d": 110, "e": 2, "f": 102, "g": 500}
    records = []
    for identifier in values:
        unit = "U1" if identifier in "abe" else "U2" if identifier in "cdf" else "U3"
        records.append({"id": identifier, "subject": "수학", "curriculum": "과목", "unit": unit,
                        "subunit": "같은 소단원 이름", "type": "유형", "source": "원본 출처",
                        "source_file": "original.hml", "original_number": 7, "current_number": 6})
        path = root / "data/processed/problems" / f"{identifier}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{identifier} 문제 $x+1$", encoding="utf-8")
    save(root / "data/processed/metadata.json", {"generation_id": "fixture", "records": records})
    for part, identifiers in ids.items():
        save(root / f"data/processed/splits/{part}.json", identifiers)
    for region in ("problems", "solutions"):
        save(root / f"data/vectors/{region}/vocabulary.json", ["token"])
        for part, identifiers in ids.items():
            save(root / f"data/vectors/{region}/{part}_vectors.json", {
                "generation_id": "fixture", "vocabulary_fitted_on": "train",
                "documents": [{"id": i, "vector": [values[i]]} for i in identifiers]})


@unittest.skipIf(torch is None, "Requires optional torch dependency")
class SubunitClusteringTests(unittest.TestCase):
    def test_cluster_count_and_majority_mapping_use_training_subunits_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_dataset(root)
            output = root / "result"
            with mock.patch.multiple(TorchKMeans, ROOT=root, OUTPUT=output, N_CLUSTERS=None, RESTARTS=2), \
                 contextlib.redirect_stdout(io.StringIO()):
                TorchKMeans.main()
            metrics = json.loads((output / "clustering_metrics.json").read_text())
            self.assertEqual(metrics["config"]["n_clusters"], 2)
            self.assertEqual(metrics["config"]["train_subunit_count"], 2)
            self.assertEqual(metrics["config"]["test_subunit_count"], 3)
            self.assertEqual(metrics["config"]["all_subunit_count"], 3)
            self.assertAlmostEqual(metrics["metrics"]["test"]["subunit"]["accuracy_using_train_cluster_majority"], 2 / 3)
            clusters = json.loads((output / "clusters.json").read_text())
            self.assertEqual({row["id"] for row in clusters["documents"]}, set("abcdefg"))
            self.assertFalse(any("U3" in label for label in clusters["train_majority_label_maps"]["subunit"].values()))
            summaries = json.loads((output / "cluster_groups.json").read_text())["clusters"]
            self.assertEqual(sum(row["train_count"] for row in summaries), 4)
            self.assertEqual(sum(row["test_count"] for row in summaries), 3)
            text = "\n".join(p.read_text() for p in (output / "clusters").glob("*.md"))
            for identifier in "abcdefg":
                self.assertIn(f"### {identifier}", text)
                self.assertIn(f"{identifier} 문제 $x+1$", text)
            self.assertIn("원본 출처", text)
            with (output / "cluster_assignments.csv").open(encoding="utf-8-sig") as stream:
                self.assertEqual(len(list(csv.DictReader(stream))), 7)
            for suffix in ("png", "pdf"):
                self.assertGreater((output / f"subunit_cluster_heatmap.{suffix}").stat().st_size, 100)

    def test_same_subunit_name_in_different_units_is_not_merged(self):
        a = {"curriculum": "과목", "unit": "단원 A", "subunit": "01 정의"}
        b = {"curriculum": "과목", "unit": "단원 B", "subunit": "01 정의"}
        self.assertNotEqual(TorchKMeans.subunit_label(a), TorchKMeans.subunit_label(b))

    def test_empty_cluster_is_exported_explicitly(self):
        row = {"id": "a", "split": "train", "cluster": 0,
               "actual_labels": {"subunit": "소단원"}, "train_majority_predicted_labels": {"subunit": "소단원"},
               "curriculum": "과목", "unit": "단원", "subunit": "소단원", "type": "유형", "source": "출처",
               "source_file": "source.hml", "original_number": 1, "current_number": 1}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            save_cluster_reports(root, root, [row], 2)
            groups = json.loads((root / "cluster_groups.json").read_text())["clusters"]
            self.assertEqual(groups[1]["train_count"], 0)
            self.assertEqual(groups[1]["test_count"], 0)
            self.assertIsNone(groups[1]["train_majority_subunit"])
            self.assertIn("문항 없음", (root / "clusters/cluster_01.md").read_text())


if __name__ == "__main__":
    unittest.main()
