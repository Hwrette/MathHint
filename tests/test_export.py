"""저장 기능과 명령행 실행을 검증하는 독립적인 자동 테스트다.

테스트는 작은 가짜 문서·HWPX를 만들어 정답 누출 방지, 원본 보존, 검토 상태,
종료 코드를 확인한다. unittest가 test_로 시작하는 메서드를 찾아 실행하며,
실제 연구 데이터나 사용자가 검토한 결과는 수정하지 않는다.
"""
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
    """추출이 끝난 중간 데이터부터 파일 저장 단계의 동작을 검증한다."""

    def setUp(self):
        """각 테스트 전에 서로 독립된 임시 폴더와 작은 원본 파일을 만든다."""
        self.temp = tempfile.TemporaryDirectory()
        # addCleanup에 등록한 함수는 테스트가 성공하거나 실패해도 실행된다.
        # 따라서 임시 파일이 다음 테스트 결과에 영향을 주지 않도록 정리할 수 있다.
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "수학.hwpx"
        self.original = b"unaltered source fixture"
        self.source.write_bytes(self.original)

    def document(self, script="x^{2}", *, body_media=False, solution_media=False):
        """저장 기능만 시험할 수 있도록 문항 하나의 중간 데이터를 만든다.

        실제 HWPX 해석은 생략하고, 원하는 본문 수식이나 본문/해설 이미지를
        넣어 해당 조건의 결과를 독립적으로 확인한다. * 뒤의 인자는 이름을 붙여
        전달해야 하므로 body_media와 solution_media를 혼동하기 어렵다.
        """
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
        # 원본 해시와 문제/해설의 수식 참조까지 갖춰 실제 저장 함수에 전달할 수 있다.
        raw = RawDocument(str(self.source), hashlib.sha256(self.original).hexdigest(),
                          ["Contents/section0.xml"], body_blocks,
                          {note.note_id: note}, equations, 2)
        problem = Problem("source-001", "1", [], body_blocks, solution_blocks, [note.note_id])
        return Document(raw, [problem], [], [])

    @staticmethod
    def report(destination):
        """저장된 report.json을 읽어 테스트에서 검사할 딕셔너리로 돌려준다.

        self의 상태를 쓰지 않는 보조 함수이므로 staticmethod로 선언했다.
        """
        return json.loads((destination / "report.json").read_text(encoding="utf-8"))

    def test_original_copy_and_body_solution_separation(self):
        """원본·사본이 같고 정답과 해설이 문제 텍스트에 들어가지 않아야 한다."""
        destination = export_document(self.document(), self.root / "output")
        self.assertEqual(self.source.read_bytes(), self.original)
        self.assertEqual((destination / "source.hwpx").read_bytes(), self.original)
        body = (destination / "problems/001.txt").read_text(encoding="utf-8")
        solution = (destination / "solutions/001.txt").read_text(encoding="utf-8")
        self.assertIn("$x^{2}$", body)
        # assertIn/assertNotIn은 문자열 포함 여부를 검사한다. 조건을 어기면
        # 테스트가 실패하므로 문제 입력으로 정답이 새는 변경을 알아낼 수 있다.
        self.assertNotIn("정답", body)
        self.assertNotIn("비공개", body)
        self.assertIn("비공개 해설", solution)
        report = self.report(destination)
        self.assertEqual(report["regions"]["body"]["total"], 1)
        self.assertEqual(report["regions"]["solutions"]["total"], 1)
        self.assertFalse(report["mathematical_equivalence_verified"])

    def test_unsupported_equation_has_placeholder_and_exact_raw_audit(self):
        """깨진 수식은 검토 표시로 나타나고 공백까지 포함한 원문은 기록에 남아야 한다."""
        # 닫히지 않은 중괄호와 양쪽 공백을 의도적으로 넣는다. 자동 보정하거나
        # 원문을 strip해서 잃어버리는 동작이 생기면 아래 검사가 실패한다.
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
        """해설에만 이미지가 있으면 본문은 여전히 텍스트 변환 지원 상태여야 한다."""
        destination = export_document(self.document(solution_media=True), self.root / "output")
        report = self.report(destination)
        self.assertTrue(report["supported_for_text_export"])
        self.assertFalse(report["problems"][0]["body_visual_review_required"])
        self.assertTrue(report["problems"][0]["solution_needs_review"])

    def test_body_image_requires_review(self):
        """본문에 이미지가 있으면 시각 자료 검토가 필요한 문항으로 보고해야 한다."""
        destination = export_document(self.document(body_media=True), self.root / "output")
        report = self.report(destination)
        self.assertFalse(report["supported_for_text_export"])
        self.assertTrue(report["problems"][0]["body_visual_review_required"])
        self.assertEqual(report["problems_needing_review"], 1)

    def test_existing_output_is_not_overwritten(self):
        """이미 저장한 결과를 다시 실행해도 사용자가 고친 파일을 덮어쓰지 않아야 한다."""
        document = self.document()
        destination = export_document(document, self.root / "output")
        sentinel = destination / "problems/001.txt"
        sentinel.write_text("사용자가 검토한 결과", encoding="utf-8")
        # assertRaises는 이 구간에서 지정한 오류가 실제로 발생해야 통과한다.
        with self.assertRaises(ExportError):
            export_document(document, self.root / "output")
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "사용자가 검토한 결과")

    def test_source_change_is_refused_before_export(self):
        """추출 뒤 원본 내용이 달라지면 새 출력 폴더를 만들기 전에 중단해야 한다."""
        document = self.document()
        self.source.write_bytes(b"changed after extraction")
        with self.assertRaises(ExportError):
            export_document(document, self.root / "output")
        self.assertFalse((self.root / "output").exists())

    def test_same_source_export_is_deterministic(self):
        """같은 원본을 다른 출력 위치에 저장해도 모든 결과 파일의 내용이 같아야 한다."""
        document = self.document()
        first = export_document(document, self.root / "first")
        second = export_document(document, self.root / "second")
        first_files = {p.relative_to(first): p.read_bytes() for p in first.rglob("*") if p.is_file()}
        # 출력 상위 폴더 이름은 달라도 각 파일의 상대 경로와 바이트를 비교한다.
        # 날짜·난수 같은 불필요한 차이가 결과에 들어오면 재현성 검사가 실패한다.
        second_files = {p.relative_to(second): p.read_bytes() for p in second.rglob("*") if p.is_file()}
        self.assertEqual(first_files, second_files)


class CLITests(unittest.TestCase):
    """작은 HWPX를 직접 만들어 명령행 전체 처리 흐름과 종료 코드를 검증한다."""

    def setUp(self):
        """각 명령행 테스트 전용 임시 작업 폴더를 준비한다."""
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def hwpx(self, script="x^{2}", anchored=True):
        """문항 경계용 미주와 수식 하나를 포함하는 최소 HWPX 파일을 만든다.

        HWPX는 ZIP 안에 XML 파일을 넣은 구조다. ElementTree로 문서 내용을
        만들고 ZipFile로 묶어 실제 읽기 함수에 전달한다. anchored=False는
        경계가 없는 입력을 만들기 위한 의도적인 오류 조건이다.
        """
        hp = "http://www.hancom.co.kr/hwpml/2011/paragraph"
        hs = "http://www.hancom.co.kr/hwpml/2011/section"
        opf = "http://www.idpf.org/2007/opf/"
        q = lambda name: "{" + hp + "}" + name
        # {네임스페이스주소}태그이름은 ElementTree가 XML 태그를 구별하는 표현이다.
        # q는 매번 긴 주소를 쓰지 않고 hp:p, hp:run 같은 태그를 만드는 보조 함수다.
        section = ET.Element("{" + hs + "}sec")
        paragraph = ET.SubElement(section, q("p"))
        run = ET.SubElement(paragraph, q("run"))
        if anchored:
            # 미주는 문제 시작을 표시하고 안에는 분리할 해설을 둔다.
            note = ET.SubElement(ET.SubElement(run, q("ctrl")), q("endNote"), number="1")
            sublist = ET.SubElement(note, q("subList"))
            note_run = ET.SubElement(ET.SubElement(sublist, q("p")), q("run"))
            ET.SubElement(note_run, q("t")).text = "[정답] 원본 해설"
        equation = ET.SubElement(run, q("equation"))
        ET.SubElement(equation, q("script")).text = script
        ET.SubElement(run, q("t")).text = "의 값을 구하시오."
        package = ET.Element("{" + opf + "}package")
        # content.hpf의 manifest와 spine은 들어 있는 section과 읽을 순서를 알려준다.
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
        """CLI 함수를 호출하고 종료 코드·일반 출력·오류 출력을 함께 돌려준다.

        별도 터미널 프로세스를 띄우지 않아도 main에 실제와 같은 인자 목록을
        전달할 수 있다. StringIO는 화면 출력을 메모리 문자열로 받아 검사하게 한다.
        """
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            # with 구간에서만 출력 대상을 바꾸고 구간을 벗어나면 원래 상태로 복구한다.
            status = main([str(source), "-o", str(output)] + (["--strict"] if strict else []))
        return status, stdout.getvalue(), stderr.getvalue()

    def test_strict_returns_two_after_writing_review_outputs(self):
        """엄격 모드의 검토 필요 종료 코드 2라도 결과와 보고서는 먼저 저장되어야 한다."""
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
        """기본 모드는 결과 저장에 성공하면 코드 0을 주고 검토 필요 사실을 화면에 알린다."""
        status, stdout, stderr = self.run_cli(self.hwpx("sqrt{"), self.root / "default_output")
        self.assertEqual(status, 0, stderr)
        self.assertIn("검토 1문항", stdout)

    def test_no_anchor_returns_one_and_writes_no_document(self):
        """문항 경계를 찾지 못한 파일은 코드 1로 실패하고 임의의 문항을 저장하지 않아야 한다."""
        output = self.root / "invalid_output"
        status, stdout, stderr = self.run_cli(self.hwpx(anchored=False), output)
        self.assertEqual(status, 1)
        self.assertIn("endNote", stderr)
        self.assertFalse(list(output.glob("*/report.json")))


if __name__ == "__main__":
    # 이 파일을 직접 실행해도 테스트를 수행한다. 전체 테스트 검색으로 불러올 때는
    # 이 구간을 실행하지 않고 unittest가 위 클래스의 테스트들을 수집한다.
    unittest.main()
