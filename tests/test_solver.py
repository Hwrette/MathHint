"""Gemini 호출을 모의 처리해 입력 보존, 실험 기록, 결과 충돌 방지를 검사한다."""

from contextlib import redirect_stdout
import hashlib
from io import StringIO
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

try:
    from mathhint_solver import GoogleAPI as solver
except ModuleNotFoundError as error:
    if error.name not in {"google", "google.genai"}:
        raise
    solver = None


@unittest.skipIf(solver is None, "Gemini 저장 검사는 solver 선택 설치 후 실행하세요.")
class SolverReportTests(unittest.TestCase):
    def run_solver(self, root, problem_path, *, answer=None, prompt="이 문제 풀어줘"):
        if answer is None:
            answer = r"해는 \(x = 2\)이다. 검산: \[2 + 1 = 3\]"
        response = SimpleNamespace(
            text=answer, model_version="test-model-version",
            usage_metadata=SimpleNamespace(
                prompt_token_count=123, thoughts_token_count=None,
                candidates_token_count=45, total_token_count=168,
            ),
        )
        with patch.multiple(solver, ROOT=root, OUTPUT=root / "outputs/solutions"), \
                patch.object(solver, "PROBLEM_FILE", str(problem_path)), \
                patch.object(solver, "SYSTEM_PROMPT", prompt), \
                patch.dict("os.environ", {"GEMINI_API_KEY": "test-only"}), \
                patch.object(solver.genai, "Client") as client, \
                redirect_stdout(StringIO()):
            client.return_value.__enter__.return_value.models.generate_content.return_value = response
            solver.main()
            request = client.return_value.__enter__.return_value.models.generate_content
            self.assertEqual(request.call_count, 1)
        return request.call_args.kwargs

    def test_repeated_runs_and_same_number_from_other_documents_never_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = []
            for name in ("문서 A", "문서 B"):
                path = root / "outputs" / "preprocess" / name / "problems" / "001.txt"
                path.parent.mkdir(parents=True)
                path.write_text(f"{name}: $x + 1 = 3$", encoding="utf-8-sig")
                inputs.append(path)
            self.run_solver(root, inputs[0], prompt="첫 번째 프롬프트")
            first = next((root / "outputs" / "solutions").rglob("run.json"))
            before = first.read_bytes()
            self.run_solver(root, inputs[0], prompt="두 번째 프롬프트")
            self.run_solver(root, inputs[1])
            records = list((root / "outputs" / "solutions").rglob("run.json"))
            self.assertEqual(len(records), 3)
            self.assertEqual(first.read_bytes(), before)
            self.assertEqual(len({path.parents[2] for path in records}), 2)
            prompts = [json.loads(path.read_text(encoding="utf-8"))["system_prompt"] for path in records]
            self.assertIn("첫 번째 프롬프트", prompts)
            self.assertIn("두 번째 프롬프트", prompts)

    def test_report_preserves_input_and_usage_with_markdown_preview(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            problem = root / "문제 1.txt"
            problem.write_text("식 $x+1=3$을 풀어라.\n", encoding="utf-8-sig")
            original = problem.read_bytes()
            request = self.run_solver(root, problem)
            record_path = next((root / "outputs" / "solutions").rglob("run.json"))
            record = json.loads(record_path.read_text(encoding="utf-8"))
            self.assertEqual(record["input_sha256"], hashlib.sha256(original).hexdigest())
            self.assertEqual(record["thinking_level"], "minimal")
            self.assertEqual(record["usage"]["total_token_count"], 168)
            self.assertIsNone(record["usage"]["thoughts_token_count"])
            self.assertEqual((record_path.parent / "input.txt").read_bytes(), original)
            self.assertEqual(problem.read_bytes(), original)
            plain = (record_path.parent / "solution.txt").read_text(encoding="utf-8")
            markdown = (record_path.parent / "solution.md").read_text(encoding="utf-8")
            self.assertIn("추론 토큰: 미제공", plain)
            self.assertIn("전체 토큰: 168", markdown)
            self.assertIn("$x = 2$", markdown)
            self.assertIn("\n$$\n2 + 1 = 3\n$$\n", markdown)
            self.assertEqual(request["contents"], original.decode("utf-8-sig"))
            self.assertEqual(request["config"].thinking_config.thinking_level.value.lower(), "minimal")

    def test_empty_response_creates_no_successful_run(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            problem = root / "001.txt"
            problem.write_text("$x+1=3$", encoding="utf-8")
            with self.assertRaisesRegex(SystemExit, "텍스트 응답이 없어"):
                self.run_solver(root, problem, answer="   ")
            self.assertFalse((root / "outputs" / "solutions").exists())


if __name__ == "__main__":
    unittest.main()
