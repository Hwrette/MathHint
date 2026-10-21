"""Independent export/CLI checks for traceability and review boundaries."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from xml.etree import ElementTree as ET
import zipfile

from mathhint_preprocess.__main__ import main
from mathhint_preprocess.export import ExportError, export_document
from mathhint_preprocess.models import Block, Document, Equation, Note, Problem, RawDocument, Span


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "수학.hwpx"
        self.original = b"unaltered source fixture"
        self.source.write_bytes(self.original)

    def document(self, script="x^{2}", *, body_media=False, solution_media=False):
        body = [Span("text", "문제 ", "p/t"),
                Span("equation", script, "p/equation", "eq00001")]
        solution = [Span("text", "[정답] 비공개 해설 ", "note/t"),
                    Span("equation", "7", "note/equation", "eq00002")]
        if body_media:
            body.append(Span("media", "[시각 자료: pic; 원본 확인 필요]", "p/pic"))
        if solution_media:
            solution.append(Span("media", "[시각 자료: pic; 원본 확인 필요]", "note/pic"))
        body_blocks = [Block("p", body)]
        solution_blocks = [Block("note/p", solution)]
        equations = {"eq00001": Equation("eq00001", script, "p/equation"),
                     "eq00002": Equation("eq00002", "7", "note/equation")}
        note = Note("note00001", "1", "note", solution_blocks)
        raw = RawDocument(str(self.source), hashlib.sha256(self.original).hexdigest(),
                          ["Contents/section0.xml"], body_blocks,
                          {note.note_id: note}, equations, 2)
        problem = Problem("source-001", "1", [], body_blocks, solution_blocks, [note.note_id])
        return Document(raw, [problem], [], [])

    @staticmethod
    def report(destination):
        return json.loads((destination / "report.json").read_text(encoding="utf-8"))

    def test_original_copy_and_body_solution_separation(self):
        destination = export_document(self.document(), self.root / "output")
        self.assertEqual(self.source.read_bytes(), self.original)
        self.assertEqual((destination / "source.hwpx").read_bytes(), self.original)
        body = (destination / "problems/001.txt").read_text(encoding="utf-8")
        solution = (destination / "solutions/001.txt").read_text(encoding="utf-8")
        self.assertIn("$x^{2}$", body)
        self.assertNotIn("정답", body)
        self.assertNotIn("비공개", body)
        self.assertIn("비공개 해설", solution)
        report = self.report(destination)
        self.assertEqual(report["regions"]["body"]["total"], 1)
        self.assertEqual(report["regions"]["solutions"]["total"], 1)
        self.assertFalse(report["mathematical_equivalence_verified"])

    def test_unsupported_equation_has_placeholder_and_exact_raw_audit(self):
        script = "  sqrt{  "
        destination = export_document(self.document(script), self.root / "output")
        body = (destination / "problems/001.txt").read_text(encoding="utf-8")
        self.assertIn("[수식 변환 검토 필요: eq00001]", body)
        record = json.loads((destination / "records.jsonl").read_text(encoding="utf-8"))
        self.assertEqual(record["equations"][0]["raw"], script)
        self.assertEqual(record["blocks"][0]["spans"][1]["text"], script)
        self.assertIsNone(record["equations"][0]["latex"])
        self.assertTrue(record["equations"][0]["warnings"])
        report = self.report(destination)
        self.assertFalse(report["supported_for_text_export"])
        self.assertEqual(report["problems_needing_review"], 1)
        self.assertEqual(report["regions"]["body"]["needs_review"], 1)

    def test_solution_image_does_not_mark_problem_visual_or_unsupported(self):
        destination = export_document(self.document(solution_media=True), self.root / "output")
        report = self.report(destination)
        self.assertTrue(report["supported_for_text_export"])
        self.assertFalse(report["problems"][0]["body_visual_review_required"])
        self.assertTrue(report["problems"][0]["solution_needs_review"])

    def test_body_image_requires_review(self):
        destination = export_document(self.document(body_media=True), self.root / "output")
        report = self.report(destination)
        self.assertFalse(report["supported_for_text_export"])
        self.assertTrue(report["problems"][0]["body_visual_review_required"])
        self.assertEqual(report["problems_needing_review"], 1)

    def test_existing_output_is_not_overwritten(self):
        document = self.document()
        destination = export_document(document, self.root / "output")
        sentinel = destination / "problems/001.txt"
        sentinel.write_text("사용자가 검토한 결과", encoding="utf-8")
        with self.assertRaises(ExportError):
            export_document(document, self.root / "output")
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "사용자가 검토한 결과")

    def test_source_change_is_refused_before_export(self):
        document = self.document()
        self.source.write_bytes(b"changed after extraction")
        with self.assertRaises(ExportError):
            export_document(document, self.root / "output")
        self.assertFalse((self.root / "output").exists())

    def test_same_source_export_is_deterministic(self):
        document = self.document()
        first = export_document(document, self.root / "first")
        second = export_document(document, self.root / "second")
        first_files = {p.relative_to(first): p.read_bytes() for p in first.rglob("*") if p.is_file()}
        second_files = {p.relative_to(second): p.read_bytes() for p in second.rglob("*") if p.is_file()}
        self.assertEqual(first_files, second_files)


class CLITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def hwpx(self, script="x^{2}", anchored=True):
        hp = "http://www.hancom.co.kr/hwpml/2011/paragraph"
        hs = "http://www.hancom.co.kr/hwpml/2011/section"
        opf = "http://www.idpf.org/2007/opf/"
        q = lambda name: "{" + hp + "}" + name
        section = ET.Element("{" + hs + "}sec")
        paragraph = ET.SubElement(section, q("p"))
        run = ET.SubElement(paragraph, q("run"))
        if anchored:
            note = ET.SubElement(ET.SubElement(run, q("ctrl")), q("endNote"), number="1")
            sublist = ET.SubElement(note, q("subList"))
            note_run = ET.SubElement(ET.SubElement(sublist, q("p")), q("run"))
            ET.SubElement(note_run, q("t")).text = "[정답] 원본 해설"
        equation = ET.SubElement(run, q("equation"))
        ET.SubElement(equation, q("script")).text = script
        ET.SubElement(run, q("t")).text = "의 값을 구하시오."
        package = ET.Element("{" + opf + "}package")
        manifest = ET.SubElement(package, "{" + opf + "}manifest")
        ET.SubElement(manifest, "{" + opf + "}item", id="section0", href="Contents/section0.xml")
        spine = ET.SubElement(package, "{" + opf + "}spine")
        ET.SubElement(spine, "{" + opf + "}itemref", idref="section0")
        path = self.root / "fixture.hwpx"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("Contents/section0.xml", ET.tostring(section, encoding="utf-8"))
            archive.writestr("Contents/content.hpf", ET.tostring(package, encoding="utf-8"))
        return path

    def run_cli(self, source, output, strict=False):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            status = main([str(source), "-o", str(output)] + (["--strict"] if strict else []))
        return status, stdout.getvalue(), stderr.getvalue()

    def test_strict_returns_two_after_writing_review_outputs(self):
        source = self.hwpx("sqrt{")
        output = self.root / "strict_output"
        status, stdout, stderr = self.run_cli(source, output, strict=True)
        self.assertEqual(status, 2, stderr)
        reports = list(output.glob("*/report.json"))
        self.assertEqual(len(reports), 1)
        self.assertEqual(json.loads(reports[0].read_text(encoding="utf-8"))["problems_needing_review"], 1)
        self.assertTrue((reports[0].parent / "problems/001.txt").exists())
        self.assertIn("검토 1문항", stdout)

    def test_default_returns_zero_and_reports_review(self):
        status, stdout, stderr = self.run_cli(self.hwpx("sqrt{"), self.root / "default_output")
        self.assertEqual(status, 0, stderr)
        self.assertIn("검토 1문항", stdout)

    def test_no_anchor_returns_one_and_writes_no_document(self):
        output = self.root / "invalid_output"
        status, stdout, stderr = self.run_cli(self.hwpx(anchored=False), output)
        self.assertEqual(status, 1)
        self.assertIn("endNote", stderr)
        self.assertFalse(list(output.glob("*/report.json")))


if __name__ == "__main__":
    unittest.main()
