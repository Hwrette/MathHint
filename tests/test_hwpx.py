"""Small HWPX fixtures test boundary and ordering behavior independently."""
import hashlib
from pathlib import Path
import tempfile
import unittest
import zipfile

from mathhint_preprocess.hwpx import HWPXError, read_hwpx
from mathhint_preprocess.models import equation_ids, raw_text
from mathhint_preprocess.segment import split_problems


HP = 'http://www.hancom.co.kr/hwpml/2011/paragraph'
HS = 'http://www.hancom.co.kr/hwpml/2011/section'


def equation(script, caption='DO_NOT_INCLUDE_CAPTION'):
    return f'<hp:equation id="same-id"><hp:caption><hp:subList><hp:p><hp:run><hp:t>{caption}</hp:t></hp:run></hp:p></hp:subList></hp:caption><hp:script>{script}</hp:script></hp:equation>'


def paragraph(contents):
    return f'<hp:p><hp:run>{contents}</hp:run></hp:p>'


def note(number, answer='SOLUTION_ONLY'):
    return (f'<hp:ctrl><hp:endNote number="{number}"><hp:subList>'
            + paragraph('<hp:t>' + answer + '</hp:t>' + equation('999'))
            + '</hp:subList></hp:endNote></hp:ctrl>')


def table(contents):
    return '<hp:tbl rowCnt="1" colCnt="1"><hp:tr><hp:tc><hp:subList>' + paragraph(contents) + '</hp:subList></hp:tc></hp:tr></hp:tbl>'


def make_hwpx(path, sections, order=None):
    """sections maps archive names to section body; order is an explicit OPF spine."""
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('mimetype', 'application/hwp+zip')
        for name, body in sections.items():
            archive.writestr(name, f'<hs:sec xmlns:hp="{HP}" xmlns:hs="{HS}">{body}</hs:sec>')
        if order is not None:
            entries = ''.join(f'<item id="s{i}" href="{name}"/>' for i, name in enumerate(order))
            spine = ''.join(f'<itemref idref="s{i}"/>' for i in range(len(order)))
            archive.writestr('Contents/content.hpf', f'<package><manifest>{entries}</manifest><spine>{spine}</spine></package>')


class HWPXTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'test.hwpx'

    def write(self, body):
        make_hwpx(self.path, {'Contents/section0.xml': body}, ['Contents/section0.xml'])
        return split_problems(read_hwpx(self.path))

    def test_mixed_text_tails_preserve_choices_and_line_breaks(self):
        doc = self.write(paragraph(note(1) + '<hp:t>① a<hp:tab/><hp:tab/>② b<hp:lineBreak/>③ c</hp:t>'))
        text = raw_text(doc.problems[0].blocks)
        self.assertEqual(text, '① a\t\t② b\n③ c')
        self.assertTrue(any(s.location.endswith('tail()') for b in doc.problems[0].blocks for s in b.spans))

    def test_solutions_and_quick_answers_never_enter_problem_body(self):
        body = paragraph(note(1) + '<hp:t>QUESTION_ONLY</hp:t>' + equation('x+1'))
        body += paragraph(table('<hp:t>제목(빠른 정답)</hp:t>'))
        body += paragraph('<hp:ctrl><hp:autoNum num="1" numType="ENDNOTE"/></hp:ctrl><hp:t>[정답] 999</hp:t>')
        doc = self.write(body)
        self.assertEqual(len(doc.problems), 1)
        question = raw_text(doc.problems[0].blocks)
        self.assertIn('QUESTION_ONLY', question)
        for leaked in ('SOLUTION_ONLY', '999', '빠른 정답', 'DO_NOT_INCLUDE_CAPTION', '[정답]'):
            self.assertNotIn(leaked, question)
        self.assertIn('SOLUTION_ONLY', raw_text(doc.problems[0].solution_blocks))
        self.assertIn('999', raw_text(doc.appendix_blocks))
        self.assertEqual(len(doc.raw.equations), doc.raw.xml_script_count)

    def test_next_source_table_is_not_attached_to_previous_question(self):
        source1 = table('<hp:t>[출처]</hp:t><hp:t>FIRST SOURCE</hp:t>')
        source2 = table('<hp:t>[출처]</hp:t><hp:t>SECOND SOURCE</hp:t>')
        doc = self.write(paragraph('<hp:t>TITLE</hp:t>' + source1)
                         + paragraph(note(1) + '<hp:t>FIRST QUESTION</hp:t>')
                         + paragraph(source2)
                         + paragraph(note(2) + '<hp:t>SECOND QUESTION</hp:t>'))
        self.assertEqual(len(doc.problems), 2)
        self.assertIn('FIRST SOURCE', raw_text(doc.problems[0].source_blocks))
        self.assertIn('SECOND SOURCE', raw_text(doc.problems[1].source_blocks))
        for p in doc.problems:
            self.assertNotIn('SOURCE', raw_text(p.blocks))

    def test_condition_table_keeps_text_equations_and_order(self):
        condition = table('<hp:t>(가) </hp:t>' + equation('x=1') + '<hp:t><hp:lineBreak/>(나) 조건</hp:t>')
        doc = self.write(paragraph(note(1) + '<hp:t>START</hp:t>') + paragraph(condition) + paragraph('<hp:t>END</hp:t>'))
        text = raw_text(doc.problems[0].blocks)
        self.assertLess(text.index('START'), text.index('(가)'))
        self.assertLess(text.index('(가)'), text.index('$x=1$'))
        self.assertLess(text.index('$x=1$'), text.index('(나)'))
        self.assertLess(text.index('(나)'), text.index('END'))
        self.assertTrue(any(s.kind == 'table_start' for b in doc.problems[0].blocks for s in b.spans))

    def test_duplicate_hwp_equation_ids_still_have_unique_source_references(self):
        doc = self.write(paragraph(note(1) + equation('a') + equation('b')))
        ids = equation_ids(doc.problems[0].blocks)
        self.assertEqual(len(ids), 2)
        self.assertNotEqual(*ids)
        equations = [doc.raw.equations[i] for i in ids]
        self.assertNotEqual(equations[0].location, equations[1].location)
        self.assertEqual([e.hwp_id for e in equations], ['same-id', 'same-id'])

    def test_graphic_in_solution_does_not_become_a_body_graphic(self):
        body = paragraph(note(1, '<![CDATA[SOLUTION]]>') + '<hp:t>PLAIN PROBLEM</hp:t>')
        body = body.replace('<hp:t><![CDATA[SOLUTION]]></hp:t>', '<hp:t>SOLUTION</hp:t><hp:pic id="p1"/>')
        doc = self.write(body)
        self.assertFalse(any(s.kind == 'media' for b in doc.problems[0].blocks for s in b.spans))
        self.assertTrue(any(s.kind == 'media' for b in doc.problems[0].solution_blocks for s in b.spans))

    def test_body_graphic_remains_visible_as_review_marker(self):
        doc = self.write(paragraph(note(1) + '<hp:t>그림 참조</hp:t><hp:pic id="p1"/>'))
        self.assertIn('원본 확인 필요', raw_text(doc.problems[0].blocks))
        self.assertTrue(any(s.kind == 'media' for b in doc.problems[0].blocks for s in b.spans))

    def test_no_endnote_fails_instead_of_guessing_boundaries(self):
        with self.assertRaisesRegex(HWPXError, 'endNote'):
            self.write(paragraph('<hp:t>1. first 2. second</hp:t>'))

    def test_mid_paragraph_note_is_ambiguous_and_rejected(self):
        with self.assertRaisesRegex(HWPXError, '미주 앞'):
            self.write(paragraph('<hp:t>PREVIOUS CONTENT</hp:t>' + note(1) + '<hp:t>QUESTION</hp:t>'))

    def test_duplicate_note_numbers_rejected(self):
        with self.assertRaisesRegex(HWPXError, '중복 문제 번호'):
            self.write(paragraph(note(1) + '<hp:t>ONE</hp:t>') + paragraph(note(1) + '<hp:t>TWO</hp:t>'))

    def test_problem_anchor_after_answer_region_rejected(self):
        body = paragraph(note(1) + '<hp:t>ONE</hp:t>')
        body += paragraph('<hp:t>[정답] ONE ANSWER</hp:t>') + paragraph(note(2) + '<hp:t>TWO</hp:t>')
        with self.assertRaisesRegex(HWPXError, '정답 영역 뒤'):
            self.write(body)

    def test_spine_overrides_lexical_section_order(self):
        sections = {'Contents/section10.xml': paragraph(note(1) + '<hp:t>FIRST</hp:t>'),
                    'Contents/section2.xml': paragraph(note(2) + '<hp:t>SECOND</hp:t>')}
        make_hwpx(self.path, sections, ['Contents/section10.xml', 'Contents/section2.xml'])
        doc = split_problems(read_hwpx(self.path))
        self.assertEqual([p.number for p in doc.problems], ['1', '2'])
        self.assertEqual(doc.raw.warnings, [])

    def test_missing_spine_section_rejected(self):
        make_hwpx(self.path, {'Contents/section0.xml': '', 'Contents/section1.xml': ''}, ['Contents/section0.xml'])
        with self.assertRaisesRegex(HWPXError, '누락'):
            read_hwpx(self.path)

    def test_archive_and_raw_equations_are_unchanged(self):
        script = '  log`_{2}`x={1} over {3}` '
        doc = self.write(paragraph(note(1) + equation(script)))
        before = self.path.read_bytes()
        self.assertEqual(doc.raw.equations[equation_ids(doc.problems[0].blocks)[0]].raw, script)
        self.assertEqual(doc.raw.source_sha256, hashlib.sha256(before).hexdigest())
        read_hwpx(self.path)
        self.assertEqual(self.path.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
