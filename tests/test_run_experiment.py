"""작은 임시 자료로 실행기 연결을 검사한다. 연구 자료와 외부 API는 쓰지 않는다."""

from dataclasses import replace
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

try:
    import torch
except ModuleNotFoundError:
    torch = None

if torch is not None:
    from mathhint_learning.Experiment import Experiment
    from mathhint_learning.RunExperiment import run
    from mathhint_learning.TorchData import file_hash, read_dataset
    from test_fixed_training import write_fixture


@unittest.skipIf(torch is None, "Requires optional torch dependency")
class RunExperimentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        write_fixture(self.root)
        path = self.root / "data/processed/metadata.json"
        metadata = json.loads(path.read_text())
        for record in metadata["records"]:
            record.update(answer_text="$1$", curriculum="가짜 과목", unit="가짜 단원", subunit="가짜 소단원", type="가짜 유형")
            for region, text in (("problems", r"$\frac{1}{2}+\frac{1}{2}$의 값은?"),
                                 ("solutions", "**가짜 검사 해설**\n\n최종정답: 1")):
                folder = self.root / "data/processed" / region
                folder.mkdir(exist_ok=True)
                (folder / (record["id"] + ".txt")).write_text(text, encoding="utf-8")
        path.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")
        self.exp = Experiment(name="toy", project_root=self.root, epochs=2, seed=7)

    def invoke(self, action, experiment=None):
        with contextlib.redirect_stdout(io.StringIO()):
            return run(action, experiment or self.exp, make_figures=False)

    def test_train_evaluate_prepare_view_share_selected_model_and_predictions_without_api(self):
        with patch("google.genai.Client", side_effect=AssertionError("live SDK forbidden")):
            trained = self.invoke("train")
            self.assertTrue(trained["result"]["training_performed"])
            evaluated = self.invoke("evaluate")
            self.assertFalse(evaluated["result"]["training_performed"])
            predictions = Path(evaluated["experiment"]["predictions"])
            self.assertEqual(predictions, self.exp.predictions)
            prepared = self.invoke("prepare")
            self.assertEqual(prepared["result"]["new_calls_needed"], 3)
            config_path = self.exp.result_root / "03_gemini/config.json"
            config = json.loads(config_path.read_text())["config"]
            self.assertEqual(config["predictions_source"], str(predictions))
            self.assertEqual(config["predictions_sha256"], file_hash(predictions))
            self.assertEqual(config["checkpoint_sha256"], file_hash(self.exp.checkpoint))
            self.assertEqual(config["data_identity"], read_dataset(self.root)["identity"])
            request = json.loads((self.exp.result_root / "03_gemini/prompt_audit/requests/c/B.json").read_text())
            self.assertEqual(request["sources"]["vector"], str(predictions))
            self.assertEqual(request["problem_text"], (self.exp.data_root / "processed/problems/c.txt").read_text())
            hashes = {p: file_hash(p) for p in (self.exp.checkpoint, predictions, config_path)}
            with patch("mathhint_learning.TorchRegression.train_regression", side_effect=AssertionError("view must not train")), \
                 patch("mathhint_learning.VectorComparison.evaluate_for_experiment", side_effect=AssertionError("view must not infer")), \
                 patch.object(torch, "load", side_effect=AssertionError("view must not load a model")):
                viewed = self.invoke("view")
            self.assertFalse(viewed["report"]["complete"])
            self.assertEqual(viewed["report"]["successful_conditions"], 0)
            self.assertTrue(all(file_hash(p) == value for p, value in hashes.items()))
        report = (self.exp.result_root / "final_report.md").read_text()
        self.assertIn("학습 2개 / 테스트 1개", report)
        self.assertNotIn("80문항", report)
        self.assertNotIn("346", report)
        self.assertTrue((self.exp.result_root / "03_gemini/report.html").is_file())
        self.assertFalse((self.exp.result_root / "03_gemini/responses.jsonl").exists())
        rows = json.loads((self.exp.result_root / "03_gemini/analysis.json").read_text())
        self.assertEqual(rows["review"]["ai_review"], {})
        self.assertEqual(rows["supplemental_key"]["conflicts"], [])

    def test_regression_only_view_is_honest_and_does_not_prepare_api_inputs(self):
        self.invoke("train")
        result = self.invoke("view")
        self.assertFalse(result["report"]["generation_prepared"])
        self.assertFalse((self.exp.result_root / "03_gemini/config.json").exists())
        self.assertIn("생성 실험은 준비·실행하지 않았다", (self.exp.result_root / "final_report.md").read_text())

    def test_checkpoint_change_and_missing_prediction_do_not_fall_back_to_old_results(self):
        self.invoke("train")
        original = self.exp.checkpoint.read_bytes()
        checkpoint = torch.load(self.exp.checkpoint, weights_only=True)
        checkpoint["model_state_dict"]["bias"] += 1
        torch.save(checkpoint, self.exp.checkpoint)
        for action in ("prepare", "generate"):
            with self.subTest(action=action), self.assertRaisesRegex(ValueError, "체크포인트|checkpoint"):
                self.invoke(action)
        self.exp.checkpoint.write_bytes(original)
        self.exp.predictions.unlink()
        with self.assertRaisesRegex(FileNotFoundError, "predictions"):
            self.invoke("prepare")

    def test_first_view_rejects_changed_vocabulary_even_with_same_metadata_and_generation(self):
        # 신원 필드 도입 전의 최종 결과를 모사한다. metadata만으로는 구분할 수 없다.
        canonical = replace(self.exp, name="final_experiment", result_root=self.root / "results/final_experiment", checkpoint=None, predictions=None)
        original = read_dataset(self.root)["identity"]["fingerprint"]
        output = canonical.result_root / "03_gemini"
        output.mkdir(parents=True)
        meta_path = canonical.data_root / "processed/metadata.json"
        (output / "config.json").write_text(json.dumps({"config": {"generation_id": "fixture", "metadata_sha256": file_hash(meta_path)}}))
        vocabulary = canonical.data_root / "vectors/solutions/vocabulary.json"
        vocabulary.write_text('["s2", "s1"]')
        with patch("mathhint_learning.RunExperiment.LEGACY_DATA_FINGERPRINT", original), \
             patch.object(torch, "load", side_effect=AssertionError("view must not load model")), \
             patch("google.genai.Client", side_effect=AssertionError("view must not call SDK")):
            with self.assertRaisesRegex(ValueError, "데이터 신원"):
                self.invoke("view", canonical)
        self.assertFalse((canonical.result_root / "experiment.json").exists())

    def test_selected_model_path_cannot_change_inside_bound_run(self):
        self.invoke("train")
        with self.assertRaisesRegex(ValueError, "checkpoint"):
            self.invoke("view", replace(self.exp, checkpoint=self.root / "another.pt"))

    def test_train_rejects_changed_data_in_a_viewed_run_before_learning(self):
        self.exp.result_root.mkdir(parents=True)
        self.invoke("view")
        vocabulary = self.exp.data_root / "vectors/solutions/vocabulary.json"
        vocabulary.write_text('["s2", "s1"]')
        with patch("mathhint_learning.TorchRegression.train_regression", side_effect=AssertionError("must reject before learning")):
            with self.assertRaisesRegex(ValueError, "데이터/어휘"):
                self.invoke("train")

    def test_first_view_checks_gemini_config_model_and_prediction_hashes_before_binding(self):
        # prepare 뒤 manifest 저장 전에 중단된 상황을 모사한다.
        self.exp.result_root.mkdir(parents=True)
        folder = self.exp.result_root / "03_gemini"
        folder.mkdir()
        self.exp.checkpoint.parent.mkdir()
        self.exp.checkpoint.write_bytes(b"original model")
        self.exp.predictions.write_bytes(b"original predictions")
        saved = {"data_identity": read_dataset(self.root)["identity"],
                 "checkpoint_sha256": file_hash(self.exp.checkpoint), "predictions_sha256": file_hash(self.exp.predictions)}
        (folder / "config.json").write_text(json.dumps({"config": saved}))
        for key in ("checkpoint", "predictions"):
            with self.subTest(key=key):
                source = getattr(self.exp, key)
                original = source.read_bytes()
                source.write_bytes(b"different bytes")
                with patch.object(torch, "load", side_effect=AssertionError("view must not load model")):
                    with self.assertRaisesRegex(ValueError, "config.json.*" + key):
                        self.invoke("view")
                self.assertFalse((self.exp.result_root / "experiment.json").exists())
                source.write_bytes(original)

    def test_final_experiment_name_with_other_valid_data_uses_generic_report(self):
        self.invoke("train")
        self.invoke("prepare")
        canonical = self.root / "results/final_experiment"
        self.exp.result_root.rename(canonical)
        from mathhint_analysis.AnalyzeThreeWay import build_report
        with patch("mathhint_analysis.AnalyzeThreeWay._build_final_report", side_effect=AssertionError("old research report forbidden")):
            result = build_report(canonical, project_root=self.root, data_root=self.exp.data_root)
        self.assertEqual(result["expected_conditions"], 3)
        text = (canonical / "final_report.md").read_text()
        self.assertIn("학습 2개 / 테스트 1개", text)
        self.assertNotIn("185", text)
        self.assertNotIn("80문항", text)


if __name__ == "__main__":
    unittest.main()
