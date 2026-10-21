"""Regression checks based on the independently inspected supplied documents.

The original HWPX files are local data, not package dependencies. These tests
skip when data/raw is unavailable; fixture tests still run on any machine.
"""
from pathlib import Path
import re
import unittest

from mathhint_preprocess.export import convert_document_equations, render_text
from mathhint_preprocess.hwpx import read_hwpx
from mathhint_preprocess.models import equation_ids, raw_text
from mathhint_preprocess.segment import split_problems


SAMPLE_ROOT = Path(__file__).resolve().parents[1] / 'data' / 'raw'


class SuppliedSampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        paths = sorted(SAMPLE_ROOT.glob('*.hwpx'))
        if len(paths) != 2 or not paths[0].name.startswith('1-') or not paths[1].name.startswith('2-'):
            raise unittest.SkipTest('두 첨부 HWPX 원본이 data/raw에 있을 때 실행하는 검사입니다.')
        cls.documents = [split_problems(read_hwpx(p)) for p in paths]
        for document in cls.documents:
            convert_document_equations(document)

    def test_independently_counted_scope_inventories(self):
        for document, expected in zip(self.documents, ((30, 272, 349, 2), (20, 284, 768, 9))):
            problems, body_count, solution_count, appendix_count = expected
            with self.subTest(source=document.raw.source_file):
                self.assertEqual(len(document.problems), problems)
                body = [i for p in document.problems for i in equation_ids(p.blocks)]
                solution = [i for p in document.problems for i in equation_ids(p.solution_blocks)]
                appendix = equation_ids(document.appendix_blocks)
                self.assertEqual((len(body), len(solution), len(appendix)), (body_count, solution_count, appendix_count))
                self.assertFalse(set(body) & set(solution))
                self.assertFalse(set(body) & set(appendix))
                self.assertEqual(set(body + solution + appendix), set(document.raw.equations))
                self.assertEqual(document.raw.xml_script_count, body_count + solution_count + appendix_count)
                self.assertEqual(document.raw.warnings + document.warnings, [])

    def test_first_sample_choices_and_final_question(self):
        document = self.documents[0]
        text = render_text(document.problems[1].blocks, document.raw.equations)
        for choice in '①②③④⑤':
            self.assertIn(choice, text)
        self.assertIn(r'\log_{3} a = 2 \log_{a} \sqrt{3}', text)
        last = render_text(document.problems[-1].blocks, document.raw.equations)
        self.assertIn(r'\frac{\sin \theta}{1 - \cos \theta} + \frac{\sin \theta}{1 + \cos \theta}', last)
        self.assertNotIn('[정답]', last)
        self.assertNotIn('빠른 정답', last)

    def test_second_sample_conditions_and_split_math_are_preserved(self):
        document = self.documents[1]
        for number in (9, 16, 17, 20):
            problem = document.problems[number - 1]
            text = raw_text(problem.blocks)
            self.assertIn('(가)', text)
            self.assertIn('(나)', text)
            self.assertTrue(any(s.kind == 'table_start' for b in problem.blocks for s in b.spans))
        problem = document.problems[10]
        spans = [s for b in problem.blocks for s in b.spans]
        natural_index = next(i for i, s in enumerate(spans) if '은 자연수' in s.text)
        self.assertEqual(spans[natural_index - 1].kind, 'equation')
        self.assertEqual(spans[natural_index + 1].kind, 'equation')
        self.assertTrue(document.raw.equations[spans[natural_index - 1].reference].warnings)
        self.assertIn('left|', document.raw.equations[spans[natural_index - 1].reference].raw)

    def test_all_fifty_bodies_exclude_answers_caption_noise_and_graphics(self):
        for document in self.documents:
            for problem in document.problems:
                with self.subTest(source=document.raw.source_file, problem=problem.number):
                    text = render_text(problem.blocks, document.raw.equations)
                    for leakage in ('[정답]', '[해설]', '빠른 정답', '작업공간', '[출처]'):
                        self.assertNotIn(leakage, text)
                    self.assertIsNone(re.search(r'[A-Za-z0-9+/]{80,}={0,2}', text))
                    self.assertFalse(any(s.kind == 'media' for b in problem.blocks for s in b.spans))


if __name__ == '__main__':
    unittest.main()
