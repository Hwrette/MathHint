"""군집의 읽기 링크·분할 표기와 표시 갱신의 원본 보호를 확인한다."""

import hashlib
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import unquote

from mathhint_learning.ClusterReport import (
    cluster_problem_links, refresh_cluster_reading_links, save_final_cluster_members,
)


class ClusterReaderLinksTests(unittest.TestCase):
    def test_all_split_labels_and_original_links_are_kept_with_math_reader(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "results/run/01_clustering"
            target = output / "experiments/type_spherical"
            target.mkdir(parents=True)
            reader = output.parent / "03_gemini/report.html"
            reader.parent.mkdir()
            reader.write_text("reader placeholder")
            documents = []
            for identifier, split in (("train_a", "train"), ("test_b", "test")):
                path = root / f"data/processed/problems/{identifier}.txt"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(r"문제 $\frac{1}{x}$")
                documents.append({"id": identifier, "split": split, "cluster": 0,
                                  "train_majority_label": "유형", "curriculum": "과목",
                                  "unit": "단원", "subunit": "세부단원", "type": "유형"})
            save_final_cluster_members(root, output, target, documents, 2)
            text = (target / "clusters.md").read_text()
            self.assertIn("[train_a](../../../03_gemini/report.html#train_a)", text)
            self.assertIn("[test_b](../../../03_gemini/report.html#test_b)", text)
            self.assertIn("| 학습 |", text)
            self.assertIn("| 테스트 |", text)
            self.assertIn("생성 실험 대상 아님", text)
            self.assertIn("| 실제 과목 | 단원 | 세부단원 | 유형 |", text)
            self.assertIn("## 군집 01", text)
            self.assertIn("문항 없음", text)
            for url in re.findall(r"\]\(([^)]+)\)", text):
                self.assertTrue((target / unquote(url.split("#")[0])).exists(), url)
            self.assertEqual((root / "data/processed/problems/train_a.txt").read_text(), r"문제 $\frac{1}{x}$")

    def test_selected_data_root_with_spaces_is_linked_instead_of_default_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "results/새 실험/01_clustering"
            source = output / "experiments/type_euclidean"
            selected = root / "선택 데이터"
            text = cluster_problem_links(root, output, source, "train_a", data_root=selected)
            self.assertIn("%20", text)
            original = re.findall(r"\]\(([^)]+)\)", text)[1]
            self.assertEqual((source / unquote(original)).resolve(),
                             (selected / "processed/problems/train_a.txt").resolve())

    def test_tampered_saved_result_is_not_blessed_by_document_refresh(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "results/run/01_clustering"
            output.mkdir(parents=True)
            path = output / "members.csv"
            path.write_text("original")
            expected = hashlib.sha256(path.read_bytes()).hexdigest()
            (output / "manifest.json").write_text(json.dumps({"files": {"members.csv": expected}}))
            path.write_text("user change")
            with self.assertRaisesRegex(ValueError, "members.csv"):
                refresh_cluster_reading_links(root, output)
            self.assertEqual(path.read_text(), "user change")

    def test_incompatible_selected_data_fails_before_rewriting_documents(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "results/run/01_clustering"
            output.mkdir(parents=True)
            selected = root / "other_data"
            metadata = selected / "processed/metadata.json"
            metadata.parent.mkdir(parents=True)
            metadata.write_text("different dataset")
            metrics = output / "metrics.json"
            metrics.write_text(json.dumps({"config": {"input_hashes": {
                "data/processed/metadata.json": hashlib.sha256(b"original dataset").hexdigest(),
            }}, "experiments": []}))
            (output / "manifest.json").write_text(json.dumps({"files": {
                "metrics.json": hashlib.sha256(metrics.read_bytes()).hexdigest(),
            }}))
            (output / "analysis.md").write_text("keep this document")
            with self.assertRaisesRegex(ValueError, "metadata.json"):
                refresh_cluster_reading_links(root, output, data_root=selected)
            self.assertEqual((output / "analysis.md").read_text(), "keep this document")

    def test_selected_dataset_drives_tiny_fit_cache_and_same_dimension_vocabulary_guard(self):
        from contextlib import ExitStack
        from mathhint_learning.FinalClustering import run, validate_saved_results
        from mathhint_learning.TorchData import write_json
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            selected = root / "chosen data"
            output = root / "results/isolated/01_clustering"
            ids = {"train": ["a", "b", "c", "d"], "test": ["e", "f"]}
            values = {"train": [[1, 0], [2, 0], [0, 1], [0, 2]], "test": [[1, 1], [3, 0]]}
            records = [{"id": identifier, "subject": "자료군", "curriculum": "과목",
                        "unit": "단원 A" if identifier in "abe" else "단원 B",
                        "subunit": "소단원", "type": "유형"}
                       for identifier in ids["train"] + ids["test"]]
            write_json(selected / "processed/metadata.json", {"generation_id": "isolated-fixture", "records": records})
            # 기본 위치는 유효한 데이터조차 아니다. 선택한 데이터만 읽어야 한다.
            write_json(root / "data/processed/metadata.json", {"do_not_read": True})
            for part in ids:
                write_json(selected / f"processed/splits/{part}.json", ids[part])
            for region in ("problems", "solutions"):
                write_json(selected / f"vectors/{region}/vocabulary.json", ["x", "y"])
                for part in ids:
                    write_json(selected / f"vectors/{region}/{part}_vectors.json", {
                        "generation_id": "isolated-fixture", "vocabulary_fitted_on": "train",
                        "documents": [{"id": identifier, "vector": vector}
                                      for identifier, vector in zip(ids[part], values[part])]})
            # 이 테스트는 임시 정수 벡터의 모델 연결만 확인한다. 그림과 연구 결과는 생성하지 않는다.
            with ExitStack() as stack:
                for name in ("mathhint_learning.ClusterReport.plot_final_cross_tabs",
                             "mathhint_learning.ClusterReport.plot_final_composition",
                             "mathhint_learning.FinalClustering.plot_final_comparison",
                             "mathhint_learning.FinalClustering.save_pca_views"):
                    stack.enter_context(patch(name))
                result = run(root, output, seeds=[2], max_iter=10, data_root=selected)
            self.assertEqual(result["config"]["generation_id"], "isolated-fixture")
            self.assertEqual(result["config"]["data_source"]["data_root"], str(selected))
            self.assertTrue(all(row["problem_path"].startswith("chosen data/processed/problems/")
                                for report in result["experiments"] for row in report["documents"]))
            with patch("mathhint_learning.FinalClustering.fit_kmeans", side_effect=AssertionError("fit forbidden")), \
                 patch("mathhint_learning.FinalClustering.fit_spherical_kmeans", side_effect=AssertionError("fit forbidden")):
                self.assertEqual(run(root, output, seeds=[2], max_iter=10, data_root=selected), result)
                write_json(selected / "vectors/problems/vocabulary.json", ["y", "x"])
                with self.assertRaisesRegex(ValueError, "vocabulary.json"):
                    run(root, output, seeds=[2], max_iter=10, data_root=selected)
                with self.assertRaisesRegex(ValueError, "vocabulary.json"):
                    validate_saved_results(root, output, data_root=selected)


if __name__ == "__main__":
    unittest.main()
