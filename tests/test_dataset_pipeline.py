"""분할 누출·행 대응·학습 전용 어휘처럼 실험 결과에 영향을 주는 조건 검사."""
from collections import Counter
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mathhint_analysis.PrepareDataset import (
    load_original_number_maps, prepare_records, split_records, validate_records,
)


def fixture(number, *, unit="unit-a", type_name="type-a", file_number=1,
            source=None, problem=None, current_number=None):
    return {"id": f"diff_{file_number}_{number:03d}", "subject": "미분",
            "file_number": file_number, "original_number": number,
            "current_number": current_number or number, "curriculum": "curriculum",
            "unit": unit, "subunit": "subunit", "type": type_name,
            "source": source or f"SOURCE_MARKER_{number}",
            "problem_text": problem or f"problem p{number}",
            "solution_text": f"solution s{number}", "answer_text": str(number),
            "equations": [], "warnings": [], "has_body_graphic": False}


class DatasetSplitTests(unittest.TestCase):
    def test_seed_is_reproducible_and_input_order_does_not_change_ids(self):
        records = [fixture(i) for i in range(1, 11)]
        first = split_records(records)
        second = split_records(list(reversed(records)))
        self.assertEqual(first, second)
        self.assertEqual(len(first["test_ids"]), 3)
        self.assertFalse(set(first["train_ids"]) & set(first["test_ids"]))
        self.assertEqual(set(first["train_ids"] + first["test_ids"]), {r["id"] for r in records})

    def test_singleton_stays_in_train_and_small_types_are_represented(self):
        records = [fixture(1, type_name="single")]
        records += [fixture(i, type_name="two") for i in (2, 3)]
        records += [fixture(i, type_name="many") for i in range(4, 11)]
        result = split_records(records)
        self.assertIn("diff_1_001", result["train_ids"])
        self.assertEqual(len(set(result["test_ids"]) & {"diff_1_002", "diff_1_003"}), 1)
        for row in result["types"]:
            if row["type"] != "single":
                self.assertGreaterEqual(row["train"], 1)
                self.assertGreaterEqual(row["test"], 1)
        self.assertEqual(result["units"][0]["actual_test"], result["units"][0]["target_test"])

    def test_type_constraints_are_reported_when_unit_target_is_impossible(self):
        records = [fixture(i, type_name=f"pair-{(i - 1) // 2}") for i in range(1, 7)]
        result = split_records(records)
        self.assertEqual(result["units"][0]["target_test"], 2)
        self.assertEqual(result["units"][0]["actual_test"], 3)
        self.assertEqual(result["units"][0]["target_deviation"], 1)

    def test_duplicate_source_or_body_never_crosses_split(self):
        records = [fixture(1, source="shared exam", problem="first"),
                   fixture(2, source="shared exam", problem="second"),
                   fixture(3, problem="same   body"), fixture(4, problem="same\nbody"),
                   fixture(5), fixture(6)]
        result = split_records(records)
        for ids in [("diff_1_001", "diff_1_002"), ("diff_1_003", "diff_1_004")]:
            self.assertEqual(ids[0] in result["test_ids"], ids[1] in result["test_ids"])
        self.assertEqual(len(result["duplicate_groups"]), 2)

    def test_duplicate_with_conflicting_type_is_not_silently_relabelled(self):
        records = [fixture(1, problem="same", type_name="a"), fixture(2, problem="same", type_name="b")]
        with self.assertRaisesRegex(ValueError, "분류가 서로"):
            split_records(records)


class DatasetOutputTests(unittest.TestCase):
    def test_matching_ids_and_train_only_vocabularies_with_metadata_excluded(self):
        records = [fixture(i) for i in range(1, 9)]
        split = split_records(records)
        test_id = split["test_ids"][0]
        next(r for r in records if r["id"] == test_id)["problem_text"] += " TEST_ONLY_TOKEN"
        next(r for r in records if r["id"] == test_id)["solution_text"] += " SOLUTION_TEST_ONLY"
        calls = []

        def count(text):
            calls.append(text)
            return Counter(text.split())

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder);processed = root / "processed";vectors = root / "vectors"
            report = prepare_records(records, processed, vectors, count_fn=count)
            metadata = json.loads((processed / "metadata.json").read_text())["records"]
            self.assertEqual({r["id"] for r in metadata}, {r["id"] for r in records})
            self.assertEqual(len(calls), len(records) * 2)
            self.assertFalse(any("SOURCE_MARKER" in text or "curriculum" in text for text in calls))
            p_vocab = json.loads((vectors / "problems/vocabulary.json").read_text())
            s_vocab = json.loads((vectors / "solutions/vocabulary.json").read_text())
            self.assertNotIn("TEST_ONLY_TOKEN", p_vocab)
            self.assertNotIn("SOLUTION_TEST_ONLY", s_vocab)
            self.assertNotIn("solution", p_vocab)
            self.assertNotIn("problem", s_vocab)
            for part in ("train", "test"):
                ids = json.loads((processed / "splits" / f"{part}.json").read_text())
                p_data = json.loads((vectors / "problems" / f"{part}_vectors.json").read_text())
                s_data = json.loads((vectors / "solutions" / f"{part}_vectors.json").read_text())
                self.assertEqual(ids, [doc["id"] for doc in p_data["documents"]])
                self.assertEqual(ids, [doc["id"] for doc in s_data["documents"]])
                self.assertEqual(p_data["shape"], [len(ids), len(p_vocab)])
                self.assertEqual(s_data["shape"], [len(ids), len(s_vocab)])
                for region, data in (("problems", p_data), ("solutions", s_data)):
                    for doc in data["documents"]:
                        self.assertEqual(doc["file"], doc["id"] + ".txt")
                        text_path = vectors / region / data["input_folder"] / doc["file"]
                        self.assertTrue(text_path.is_file())
                        self.assertEqual(sum(doc["vector"]) + doc["ignored_token_count"], doc["token_count"])
            test_vectors = json.loads((vectors / "problems/test_vectors.json").read_text())["documents"]
            test_doc = next(doc for doc in test_vectors if doc["id"] == test_id)
            self.assertGreaterEqual(test_doc["ignored_token_count"], 1)
            manifest = json.loads((processed / "manifest.json").read_text())
            self.assertEqual(manifest["question_ids"], sorted(r["id"] for r in records))
            self.assertEqual(manifest["generation_id"], report["generation_id"])
            self.assertEqual(p_data["generation_id"], s_data["generation_id"])
            self.assertEqual(p_data["generation_id"], report["generation_id"])
            self.assertTrue(report["checks"]["paired_problem_solution_ids_and_row_order"])

    def test_original_number_is_not_replaced_by_renumbered_position(self):
        records = [fixture(17, file_number=3, current_number=16), fixture(18, file_number=3, current_number=17)]
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            prepare_records(records, root / "processed", root / "vectors", count_fn=lambda text: Counter(text.split()))
            text = (root / "processed/annotated/diff_3_017.txt").read_text()
            self.assertIn("[원래 문제 번호] 17", text)
            self.assertIn("[현재 문제 번호] 16", text)
            self.assertTrue((root / "processed/problems/diff_3_017.txt").exists())
            self.assertTrue((root / "processed/solutions/diff_3_017.txt").exists())
            self.assertFalse((root / "processed/problems/diff_3_016.txt").exists())

    def test_warning_graphic_and_bad_id_fail_before_outputs(self):
        for field, value in [("warnings", ["equation unconverted"]),
                             ("has_body_graphic", True), ("id", "diff_1_999")]:
            with self.subTest(field=field):
                records = [fixture(1), fixture(2)]
                records[0][field] = value
                with tempfile.TemporaryDirectory() as folder:
                    root = Path(folder)
                    with self.assertRaises(ValueError):
                        prepare_records(records, root / "processed", root / "vectors", count_fn=Counter)
                    self.assertFalse((root / "processed").exists())

    def test_existing_results_require_explicit_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder);output = root / "processed";output.mkdir()
            sentinel = output / "keep.txt";sentinel.write_text("keep")
            with self.assertRaisesRegex(ValueError, "덮어쓰지"):
                prepare_records([fixture(1), fixture(2)], output, root / "vectors", count_fn=Counter)
            self.assertEqual(sentinel.read_text(), "keep")

    def test_original_number_map_skips_deleted_row(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "map.json"
            path.write_text(json.dumps([
                {"파일": "file.hml", "원래번호": 16, "현재번호": "", "상태": "삭제"},
                {"파일": "file.hml", "원래번호": 17, "현재번호": 16, "상태": "유지"},
            ], ensure_ascii=False))
            self.assertEqual(load_original_number_maps(path), {"file.hml": {16: 17}})

    def test_failed_replacement_restores_both_previous_outputs(self):
        records = [fixture(1), fixture(2)]
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder);processed = root / "processed";vectors = root / "vectors"
            prepare_records(records, processed, vectors, count_fn=lambda text: Counter(text.split()))
            before = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            changed = copy.deepcopy(records)
            changed[0]["problem_text"] += " NEW_GENERATION"
            original_rename = Path.rename

            def fail_second_publication(path, target):
                if path.name.startswith(".vectors-") and Path(target) == vectors:
                    raise OSError("simulated second-directory publish failure")
                return original_rename(path, target)

            with patch.object(Path, "rename", fail_second_publication):
                with self.assertRaisesRegex(OSError, "simulated"):
                    prepare_records(changed, processed, vectors, count_fn=lambda text: Counter(text.split()), overwrite=True)
            after = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
