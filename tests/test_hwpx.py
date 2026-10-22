"""작은 가상 HWPX로 문항 경계·문서 순서·원문 보존을 검증한다.

실제 문제은행 전체를 넣는 대신, 확인할 구조만 가진 XML을 테스트마다 만든다.
이런 최소 예제 데이터를 fixture라고 한다. 예를 들어 해설에만 넣은
SOLUTION_ONLY가 문제 본문에 나타나면, 해설이 섞였음을 명확하게 알 수 있다.

이 테스트들은 HWPX 읽기와 문항 분리의 동작을 확인한다. 수식이 LaTeX로
정확하게 변환되는지 검증하는 테스트와는 역할이 다르다.
"""
import hashlib
from pathlib import Path
import tempfile
import unittest
import zipfile

from mathhint_preprocess.hwpx import HWPXError, read_hwpx
from mathhint_preprocess.models import equation_ids, raw_text
from mathhint_preprocess.segment import split_problems


# hp:p와 hs:sec처럼 XML 태그의 소속을 구별하는 네임스페이스 주소다.
# 테스트 XML에서도 이 주소를 선언해 실제 HWPX와 같은 태그 형태를 만든다.
HP = 'http://www.hancom.co.kr/hwpml/2011/paragraph'
HS = 'http://www.hancom.co.kr/hwpml/2011/section'


def equation(script, caption='DO_NOT_INCLUDE_CAPTION'):
    """수식 원문과 본문에 들어가면 안 되는 caption을 가진 수식 XML을 만든다.

    원본 수식 id는 일부러 항상 같게 한다. id가 중복돼도 별도 출현 위치로
    각 수식을 구별하는지 다른 테스트에서 확인하기 위해서다.
    """
    return f'<hp:equation id="same-id"><hp:caption><hp:subList><hp:p><hp:run><hp:t>{caption}</hp:t></hp:run></hp:p></hp:subList></hp:caption><hp:script>{script}</hp:script></hp:equation>'


def paragraph(contents):
    """전달한 XML 내용을 문단(p)과 글자 속성 묶음(run)으로 감싼다."""
    return f'<hp:p><hp:run>{contents}</hp:run></hp:p>'


def note(number, answer='SOLUTION_ONLY'):
    """문제 번호와 해설용 글·수식이 들어 있는 endNote 미주 XML을 만든다."""
    return (f'<hp:ctrl><hp:endNote number="{number}"><hp:subList>'
            + paragraph('<hp:t>' + answer + '</hp:t>' + equation('999'))
            + '</hp:subList></hp:endNote></hp:ctrl>')


def table(contents):
    """한 행·한 셀짜리 표 XML을 만든다. 출처 표와 조건 표에 공통으로 쓴다."""
    return '<hp:tbl rowCnt="1" colCnt="1"><hp:tr><hp:tc><hp:subList>' + paragraph(contents) + '</hp:subList></hp:tc></hp:tr></hp:tbl>'


def make_hwpx(path, sections, order=None):
    """테스트에 필요한 최소 XML을 ZIP에 넣어 가상 HWPX 파일을 만든다.

    sections는 'ZIP 내부 경로: 해당 section의 본문' 형태의 사전이다.
    order가 주어지면 그 순서를 manifest와 spine에 명시한다. 파일명 순서와
    실제 문서 순서를 다르게 만들어 읽기 모듈이 무엇을 우선하는지 시험할 수 있다.
    """
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('mimetype', 'application/hwp+zip')
        for name, body in sections.items():
            archive.writestr(name, f'<hs:sec xmlns:hp="{HP}" xmlns:hs="{HS}">{body}</hs:sec>')
        if order is not None:
            # manifest는 id와 파일 경로의 연결표이고, spine은 id의 읽기 순서다.
            entries = ''.join(f'<item id="s{i}" href="{name}"/>' for i, name in enumerate(order))
            spine = ''.join(f'<itemref idref="s{i}"/>' for i in range(len(order)))
            archive.writestr('Contents/content.hpf', f'<package><manifest>{entries}</manifest><spine>{spine}</spine></package>')


class HWPXTests(unittest.TestCase):
    """unittest가 test_로 시작하는 메서드들을 각각 독립된 검사로 실행한다."""

    def setUp(self):
        """각 테스트 전에 독립된 임시 폴더와 원본 파일 경로를 준비한다."""
        self.temp = tempfile.TemporaryDirectory()
        # 테스트가 성공하든 실패하든 종료할 때 임시 폴더를 정리한다.
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'test.hwpx'

    def write(self, body):
        """가상 문서 하나를 만든 뒤 실제 읽기·문항 분리 함수를 실행한다."""
        make_hwpx(self.path, {'Contents/section0.xml': body}, ['Contents/section0.xml'])
        return split_problems(read_hwpx(self.path))

    def test_mixed_text_tails_preserve_choices_and_line_breaks(self):
        """탭·줄바꿈 요소 뒤의 tail에도 선택지 글자가 남는지 확인한다."""
        doc = self.write(paragraph(note(1) + '<hp:t>① a<hp:tab/><hp:tab/>② b<hp:lineBreak/>③ c</hp:t>'))
        text = raw_text(doc.problems[0].blocks)
        self.assertEqual(text, '① a\t\t② b\n③ c')
        self.assertTrue(any(s.location.endswith('tail()') for b in doc.problems[0].blocks for s in b.spans))

    def test_solutions_and_quick_answers_never_enter_problem_body(self):
        """미주 해설·빠른 정답·수식 caption이 문제 입력으로 새어 나오지 않는다."""
        # 본문, 미주, 빠른 정답에 서로 구별되는 문자열과 수식을 넣는다.
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
        # 본문에서 빼는 것과 원본 수식 정보를 잃어버리는 것은 다르다.
        # 해설·빠른 정답 수식도 원시 수식 목록에는 따로 추적돼야 한다.
        self.assertEqual(len(doc.raw.equations), doc.raw.xml_script_count)

    def test_next_source_table_is_not_attached_to_previous_question(self):
        """문제 사이의 출처 표가 앞 문제가 아닌 다음 문제에 연결되는지 검사한다."""
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
        """조건 표를 출처처럼 제거하지 않고 글·수식·조건 순서를 보존한다."""
        condition = table('<hp:t>(가) </hp:t>' + equation('x=1') + '<hp:t><hp:lineBreak/>(나) 조건</hp:t>')
        doc = self.write(paragraph(note(1) + '<hp:t>START</hp:t>') + paragraph(condition) + paragraph('<hp:t>END</hp:t>'))
        text = raw_text(doc.problems[0].blocks)
        # 단어가 모두 있는지만 보면 순서가 뒤집힌 오류를 놓칠 수 있다.
        # index로 각 내용의 위치를 비교해 START → (가) → 수식 → (나) → END를 확인한다.
        self.assertLess(text.index('START'), text.index('(가)'))
        self.assertLess(text.index('(가)'), text.index('$x=1$'))
        self.assertLess(text.index('$x=1$'), text.index('(나)'))
        self.assertLess(text.index('(나)'), text.index('END'))
        self.assertTrue(any(s.kind == 'table_start' for b in doc.problems[0].blocks for s in b.spans))

    def test_duplicate_hwp_equation_ids_still_have_unique_source_references(self):
        """원본 id가 같은 두 수식도 내부 키와 원본 경로는 서로 달라야 한다."""
        doc = self.write(paragraph(note(1) + equation('a') + equation('b')))
        ids = equation_ids(doc.problems[0].blocks)
        self.assertEqual(len(ids), 2)
        self.assertNotEqual(*ids)
        equations = [doc.raw.equations[i] for i in ids]
        self.assertNotEqual(equations[0].location, equations[1].location)
        self.assertEqual([e.hwp_id for e in equations], ['same-id', 'same-id'])

    def test_graphic_in_solution_does_not_become_a_body_graphic(self):
        """해설 그림만 있는 문제를 본문에도 그림이 있는 것으로 잘못 읽지 않는다."""
        body = paragraph(note(1, '<![CDATA[SOLUTION]]>') + '<hp:t>PLAIN PROBLEM</hp:t>')
        body = body.replace('<hp:t><![CDATA[SOLUTION]]></hp:t>', '<hp:t>SOLUTION</hp:t><hp:pic id="p1"/>')
        doc = self.write(body)
        self.assertFalse(any(s.kind == 'media' for b in doc.problems[0].blocks for s in b.spans))
        self.assertTrue(any(s.kind == 'media' for b in doc.problems[0].solution_blocks for s in b.spans))

    def test_body_graphic_remains_visible_as_review_marker(self):
        """본문 그림은 조용히 지우지 않고 원본 확인용 표시와 media 조각을 남긴다."""
        doc = self.write(paragraph(note(1) + '<hp:t>그림 참조</hp:t><hp:pic id="p1"/>'))
        self.assertIn('원본 확인 필요', raw_text(doc.problems[0].blocks))
        self.assertTrue(any(s.kind == 'media' for b in doc.problems[0].blocks for s in b.spans))

    def test_no_endnote_fails_instead_of_guessing_boundaries(self):
        """미주 표지가 없으면 글 속 숫자만으로 문제 경계를 추측하지 않는다."""
        # assertRaisesRegex는 지정한 오류가 발생하고 오류 메시지도 조건에
        # 맞는지 확인한다. 이 경우 '오류로 멈추는 것'이 기대한 정상 동작이다.
        with self.assertRaisesRegex(HWPXError, 'endNote'):
            self.write(paragraph('<hp:t>1. first 2. second</hp:t>'))

    def test_mid_paragraph_note_is_ambiguous_and_rejected(self):
        """미주 앞에 본문이 있는 모호한 문단을 임의로 잘라 처리하지 않는다."""
        with self.assertRaisesRegex(HWPXError, '미주 앞'):
            self.write(paragraph('<hp:t>PREVIOUS CONTENT</hp:t>' + note(1) + '<hp:t>QUESTION</hp:t>'))

    def test_duplicate_note_numbers_rejected(self):
        """중복된 문제 번호를 서로 다른 정상 문제처럼 그대로 내보내지 않는다."""
        with self.assertRaisesRegex(HWPXError, '중복 문제 번호'):
            self.write(paragraph(note(1) + '<hp:t>ONE</hp:t>') + paragraph(note(1) + '<hp:t>TWO</hp:t>'))

    def test_problem_anchor_after_answer_region_rejected(self):
        """정답 영역이 시작된 뒤 다시 문제가 나타나는 지원 밖 배치는 거부한다."""
        body = paragraph(note(1) + '<hp:t>ONE</hp:t>')
        body += paragraph('<hp:t>[정답] ONE ANSWER</hp:t>') + paragraph(note(2) + '<hp:t>TWO</hp:t>')
        with self.assertRaisesRegex(HWPXError, '정답 영역 뒤'):
            self.write(body)

    def test_spine_overrides_lexical_section_order(self):
        """파일명 숫자순보다 content.hpf의 spine에 지정된 읽기 순서를 따른다."""
        # section10 → section2를 명시해, 번호순 정렬과 반대인 문서를 만든다.
        sections = {'Contents/section10.xml': paragraph(note(1) + '<hp:t>FIRST</hp:t>'),
                    'Contents/section2.xml': paragraph(note(2) + '<hp:t>SECOND</hp:t>')}
        make_hwpx(self.path, sections, ['Contents/section10.xml', 'Contents/section2.xml'])
        doc = split_problems(read_hwpx(self.path))
        self.assertEqual([p.number for p in doc.problems], ['1', '2'])
        self.assertEqual(doc.raw.warnings, [])

    def test_missing_spine_section_rejected(self):
        """실제 section 중 일부가 spine에 빠졌으면 순서를 임의 보완하지 않는다."""
        make_hwpx(self.path, {'Contents/section0.xml': '', 'Contents/section1.xml': ''}, ['Contents/section0.xml'])
        with self.assertRaisesRegex(HWPXError, '누락'):
            read_hwpx(self.path)

    def test_archive_and_raw_equations_are_unchanged(self):
        """읽는 동안 원본 파일과 수식의 공백·백틱까지 그대로 유지되는지 검사한다."""
        script = '  log`_{2}`x={1} over {3}` '
        doc = self.write(paragraph(note(1) + equation(script)))
        before = self.path.read_bytes()
        # 수식 문자열의 정확한 일치와 원본 바이트의 해시를 각각 비교한다.
        self.assertEqual(doc.raw.equations[equation_ids(doc.problems[0].blocks)[0]].raw, script)
        self.assertEqual(doc.raw.source_sha256, hashlib.sha256(before).hexdigest())
        read_hwpx(self.path)
        self.assertEqual(self.path.read_bytes(), before)


if __name__ == '__main__':
    # 이 파일을 Python으로 직접 실행했을 때도 테스트를 시작할 수 있다.
    unittest.main()
