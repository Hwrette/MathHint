"""HML 문항·해설 경계와 삭제 전 번호를 실제 XML 구조로 검증한다."""
from pathlib import Path
import hashlib
import tempfile
import unittest
from xml.sax.saxutils import escape

from mathhint_preprocess.hml import HMLError, read_hml


def paragraph(content):
    return '<P><TEXT>' + content + '</TEXT></P>'


def text(value):
    return '<CHAR>' + escape(value) + '</CHAR>'


def equation(script):
    return ('<EQUATION><CAPTION><P><TEXT><CHAR>ENCODED_CAPTION_NOT_INPUT</CHAR>'
            '</TEXT></P></CAPTION><SCRIPT>' + escape(script) + '</SCRIPT></EQUATION>')


def heading(type_name='01 그래프1 (주기)'):
    labels = ['09 대수', '06 삼각함수의 그래프', '01 삼각함수의 그래프', type_name]
    return paragraph('<TABLE><ROW>' + ''.join('<CELL>' + paragraph(text(s)) + '</CELL>'
                                             for s in labels) + '</ROW></TABLE>')


def source(value):
    return paragraph('<TABLE><ROW><CELL>' + paragraph(text('[출처]')) + '</CELL><CELL>'
                     + paragraph(text(value)) + '</CELL></ROW></TABLE>')


def note(number, answer='9', with_picture=False):
    auto = f'<AUTONUM Number="{number}" NumberType="Endnote"/>'
    return ('<ENDNOTE><PARALIST>'
            + paragraph(auto + text('[정답] ') + equation(answer))
            + paragraph(text('[해설] SOLUTION_ONLY ') + equation('x+999')
                        + ('<PICTURE/>' if with_picture else ''))
            + '</PARALIST></ENDNOTE>')


def document(body):
    return '<HWPML><HEAD/><BODY><SECTION>' + body + '</SECTION></BODY><TAIL/></HWPML>'


class HMLTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / '모의고사_삼각함수_문제_1.hml'

    def read(self, body, mapping=None):
        self.path.write_text(document(body), encoding='utf-8')
        return read_hml(self.path, mapping)

    def test_classification_inheritance_and_clean_pairing(self):
        body = heading() + source('2025년 교육청 > 1')
        body += paragraph(note(1, with_picture=True) + text('QUESTION_ONE ') + equation('sin x'))
        body += source('2025년 교육청 > 2')
        body += paragraph(note(2, '10') + text('QUESTION_TWO ') + equation('cos x'))
        body += paragraph(text('제목(빠른 정답)'))
        body += paragraph(text('QUICK_ANSWER_NOT_INPUT') + equation('123456'))
        rows = self.read(body)
        self.assertEqual([r['id'] for r in rows], ['trig_1_001', 'trig_1_002'])
        self.assertEqual([r['type'] for r in rows], ['01 그래프1 (주기)'] * 2)
        self.assertEqual(rows[0]['answer_text'], '$9$')
        self.assertEqual(rows[1]['answer_text'], '$10$')
        self.assertIn('QUESTION_ONE', rows[0]['problem_text'])
        self.assertNotIn('QUESTION_TWO', rows[0]['problem_text'])
        for r in rows:
            for unwanted in ['ENCODED_CAPTION_NOT_INPUT', 'SOLUTION_ONLY', 'QUICK_ANSWER_NOT_INPUT', '[출처]', '그래프1']:
                self.assertNotIn(unwanted, r['problem_text'])
            self.assertIn('SOLUTION_ONLY', r['solution_text'])
            self.assertNotIn('ENCODED_CAPTION_NOT_INPUT', r['solution_text'])
            self.assertFalse(r['has_body_graphic'])
        self.assertTrue(rows[0]['has_solution_graphic'])
        self.assertEqual({e['region'] for e in rows[0]['equations']}, {'problem', 'solution'})

    def test_deleted_question_does_not_shift_original_id(self):
        self.path = self.path.with_name('모의고사_미분_문제_3.hml')
        body = heading() + source('SOURCE17') + paragraph(note(16) + text('kept question'))
        row = self.read(body, {16: 17})[0]
        self.assertEqual((row['id'], row['current_number'], row['original_number']), ('diff_3_017', 16, 17))
        with self.assertRaisesRegex(HMLError, '매핑이 없습니다'):
            self.read(body, {})
        with self.assertRaisesRegex(HMLError, '중복된 원래 번호'):
            self.read(body, {16: 17, 17: 17})

    def test_table_conditions_and_mixed_text_tails_survive(self):
        condition = '<TABLE><ROW><CELL>' + paragraph(text('(가) ') + equation('x>0')) + '</CELL></ROW>'
        condition += '<ROW><CELL>' + paragraph(text('(나) 둘째 조건')) + '</CELL></ROW></TABLE>'
        body = heading() + source('SOURCE')
        body += paragraph(note(1) + '<CHAR>① a<TAB/>② b<LINEBREAK/>③ c</CHAR>')
        body += paragraph(condition)
        r = self.read(body)[0]
        self.assertIn('① a\t② b\n③ c', r['problem_text'])
        self.assertIn('(가)', r['problem_text'])
        self.assertIn('(나) 둘째 조건', r['problem_text'])
        self.assertIn('$x > 0$', r['problem_text'])

    def test_unconverted_equation_preserves_raw_and_warning(self):
        raw = 'COMMAND_NOT_SUPPORTED x'
        body = heading() + source('SOURCE') + paragraph(note(1) + equation(raw))
        row = self.read(body)[0]
        eq = next(e for e in row['equations'] if e['region'] == 'problem')
        self.assertEqual(eq['raw'], raw)
        self.assertIsNone(eq['latex'])
        self.assertTrue(eq['warnings'])
        self.assertTrue(row['warnings'])
        self.assertIn(raw, row['problem_text'])

    def test_audited_layout_transcription_adds_no_artificial_number(self):
        raw = 'pile{`#`}'
        body = heading() + source('SOURCE') + paragraph(note(1) + text('question ') + equation(raw))
        self.path.write_text(document(body), encoding='utf-8')
        entry = {'question_id': 'trig_1_001', 'region': 'problem',
                 'raw_sha256': hashlib.sha256(raw.encode()).hexdigest(), 'expected_raw': raw,
                 'latex': '', 'layout_only': True, 'reason': '검증한 빈 서식'}
        row = read_hml(self.path, transcriptions=[entry])[0]
        self.assertEqual(row['problem_text'], 'question')
        self.assertFalse(row['warnings'])
        self.assertEqual(row['equations'][0]['raw'], raw)
        with self.assertRaisesRegex(HMLError, '빈 전사'):
            read_hml(self.path, transcriptions=[{**entry, 'layout_only': False}])
        with self.assertRaisesRegex(HMLError, '해시'):
            read_hml(self.path, transcriptions=[{**entry, 'expected_raw': 'changed source'}])

    def test_missing_classification_or_note_is_rejected(self):
        with self.assertRaisesRegex(HMLError, '분류표보다 먼저'):
            self.read(source('SOURCE') + paragraph(note(1) + text('question')))
        with self.assertRaisesRegex(HMLError, 'ENDNOTE 미주가 하나'):
            self.read(heading() + source('SOURCE') + paragraph(text('question without note')))

    def test_body_picture_is_flagged_without_solution_contamination(self):
        body = heading() + source('SOURCE') + paragraph(note(1) + text('question') + '<PICTURE/>')
        row = self.read(body)[0]
        self.assertTrue(row['has_body_graphic'])
        self.assertTrue(any('그림/도형' in w for w in row['warnings']))

    def test_filtered_real_corpus_has_stable_ids_and_answer_pairs(self):
        root = Path(__file__).resolve().parents[1] / 'data' / 'raw'
        paths = sorted(root.glob('*.hml'))
        if not paths:
            self.skipTest('필터링한 HML 원본을 제공한 환경에서 실행')
        self.assertEqual(len(paths), 6)
        rows = []
        counts = []
        for path in paths:
            mapping = {n: n if n < 16 else n + 1 for n in range(1, 49)} if '미분_문제_3' in path.name else None
            rr = read_hml(path, mapping)
            rows.extend(rr)
            counts.append(len(rr))
        self.assertEqual(sorted(counts), [37, 40, 43, 48, 48, 49])
        self.assertEqual(len(rows), 265)
        self.assertEqual(len({r['id'] for r in rows}), 265)
        ids = {r['id'] for r in rows}
        self.assertNotIn('diff_3_016', ids)
        row17 = next(r for r in rows if r['id'] == 'diff_3_017')
        self.assertEqual(row17['current_number'], 16)
        self.assertEqual(len({r['source'] for r in rows}), 265)
        for r in rows:
            self.assertTrue(r['answer_text'])
            self.assertTrue(r['solution_text'])
            self.assertFalse(r['has_body_graphic'])
            self.assertNotIn('[정답]', r['problem_text'])
            self.assertNotIn('[해설]', r['problem_text'])
            self.assertNotIn('[출처]', r['problem_text'])


if __name__ == '__main__':
    unittest.main()
