"""실제 첨부 문서의 조사 결과와 프로그램 출력을 대조하는 회귀 검사.

회귀 검사는 코드를 수정한 뒤에도 이전에 보존하던 정보가 그대로 남는지
확인하는 테스트다. 이 파일은 원본을 직접 조사해 확인한 30/20문항,
본문·미주·빠른 정답의 수식 개수, 선택지와 조건 등의 기준값을 사용한다.

원본 HWPX는 코드 패키지가 아닌 별도 데이터다. data/raw가 없는 환경에서는
이 파일의 실문서 검사만 건너뛰고, 다른 파일의 작은 가상 문서 검사는 실행한다.
"""
from pathlib import Path
import re
import unittest

from mathhint_preprocess.export import convert_document_equations, render_text
from mathhint_preprocess.hwpx import read_hwpx
from mathhint_preprocess.models import equation_ids, raw_text
from mathhint_preprocess.segment import split_problems


# __file__은 이 Python 파일의 경로다. parents[1]로 프로젝트 루트까지 올라간 뒤
# 원본 폴더를 찾으므로 터미널에서 어느 위치를 기준으로 실행했는지에 덜 의존한다.
SAMPLE_ROOT = Path(__file__).resolve().parents[1] / 'data' / 'raw'


class SuppliedSampleTests(unittest.TestCase):
    """두 원본의 실제 문항·수식·텍스트 보존 상태를 검사한다."""

    @classmethod
    def setUpClass(cls):
        """이 클래스의 테스트들이 공통으로 쓸 두 문서를 한 번 읽고 변환한다."""
        # @classmethod의 cls는 이 테스트 클래스를 가리킨다. cls.documents에
        # 준비 결과를 저장하면 각각의 test_ 함수가 같은 준비 자료를 읽을 수 있다.
        # 저장소에 보관한 원본 두 개는 조사 기준값의 순서대로 명시한다.
        paths = [
            SAMPLE_ROOT / '로그계산, 삼각함수 각변환.hwpx',
            SAMPLE_ROOT / '로그함수, 삼각함수, 미분.hwpx',
        ]
        if not all(path.is_file() for path in paths):
            # 이전 작업 폴더의 1-/2- 접두사 원본도 계속 검사할 수 있다.
            paths = sorted(SAMPLE_ROOT.glob('*.hwpx'))
            if len(paths) != 2 or not paths[0].name.startswith('1-') or not paths[1].name.startswith('2-'):
                # 데이터 미제공은 프로그램 실패가 아니므로 건너뛴 이유를 알린다.
                raise unittest.SkipTest('두 첨부 HWPX 원본이 data/raw에 있을 때 실행하는 검사입니다.')
        cls.documents = [split_problems(read_hwpx(p)) for p in paths]
        for document in cls.documents:
            convert_document_equations(document)

    def test_independently_counted_scope_inventories(self):
        """문항 수와 세 영역의 수식 수가 실제 조사값과 같고 서로 섞이지 않는가?"""
        # expected의 순서: 문제 수, 본문 수식 수, 미주 해설 수식 수, 부록 수식 수.
        for document, expected in zip(self.documents, ((30, 272, 349, 2), (20, 284, 768, 9))):
            problems, body_count, solution_count, appendix_count = expected
            with self.subTest(source=document.raw.source_file):
                # subTest는 어느 원본을 검사하다 실패했는지 따로 표시한다.
                self.assertEqual(len(document.problems), problems)
                body = [i for p in document.problems for i in equation_ids(p.blocks)]
                solution = [i for p in document.problems for i in equation_ids(p.solution_blocks)]
                appendix = equation_ids(document.appendix_blocks)
                self.assertEqual((len(body), len(solution), len(appendix)), (body_count, solution_count, appendix_count))
                self.assertFalse(set(body) & set(solution))
                # set은 중복 없는 집합, &는 교집합이다. 같은 수식 객체가 본문과
                # 해설 또는 부록에 동시에 연결됐다면 영역 분리가 잘못된 것이다.
                self.assertFalse(set(body) & set(appendix))
                self.assertEqual(set(body + solution + appendix), set(document.raw.equations))
                # 세 영역을 합치면 추출된 전체 수식을 빠짐없이 설명해야 한다.
                self.assertEqual(document.raw.xml_script_count, body_count + solution_count + appendix_count)
                self.assertEqual(document.raw.warnings + document.warnings, [])

    def test_first_sample_choices_and_final_question(self):
        """선택지 번호와 중첩 수식이 남고 마지막 문제에 빠른 정답이 섞이지 않는가?"""
        document = self.documents[0]
        text = render_text(document.problems[1].blocks, document.raw.equations)
        for choice in '①②③④⑤':
            # XML의 tab 뒤 문자열을 놓치면 ②·③ 등이 사라질 수 있어 따로 확인한다.
            self.assertIn(choice, text)
        self.assertIn(r'\log_{3} a = 2 \log_{a} \sqrt{3}', text)
        last = render_text(document.problems[-1].blocks, document.raw.equations)
        self.assertIn(r'\frac{\sin \theta}{1 - \cos \theta} + \frac{\sin \theta}{1 + \cos \theta}', last)
        self.assertNotIn('[정답]', last)
        self.assertNotIn('빠른 정답', last)

    def test_second_sample_conditions_and_split_math_are_preserved(self):
        """표의 (가)/(나) 조건과 자연어 사이에 나뉜 수식 객체의 순서가 남는가?"""
        document = self.documents[1]
        for number in (9, 16, 17, 20):
            problem = document.problems[number - 1]
            text = raw_text(problem.blocks)
            self.assertIn('(가)', text)
            self.assertIn('(나)', text)
            self.assertTrue(any(s.kind == 'table_start' for b in problem.blocks for s in b.spans))
        problem = document.problems[10]
        # Python 목록은 0부터 세므로 [10]은 11번째 문제다.
        spans = [s for b in problem.blocks for s in b.spans]
        natural_index = next(i for i, s in enumerate(spans) if '은 자연수' in s.text)
        # 실제 11번은 수식 → '은 자연수' → 수식으로 나뉜다. 이 사이 문장을
        # 삭제하거나 수식끼리 임의로 합치지 않았는지 위치를 확인한다.
        self.assertEqual(spans[natural_index - 1].kind, 'equation')
        self.assertEqual(spans[natural_index + 1].kind, 'equation')
        self.assertTrue(document.raw.equations[spans[natural_index - 1].reference].warnings)
        # 이 수식은 미지원 구문이므로 원문과 경고를 남기는 동작도 확인한다.
        self.assertIn('left|', document.raw.equations[spans[natural_index - 1].reference].raw)

    def test_all_fifty_bodies_exclude_answers_caption_noise_and_graphics(self):
        """50문항의 입력 본문에 정답·해설·출처 표·캡션 잡음이 들어가지 않았는가?"""
        for document in self.documents:
            for problem in document.problems:
                with self.subTest(source=document.raw.source_file, problem=problem.number):
                    text = render_text(problem.blocks, document.raw.equations)
                    for leakage in ('[정답]', '[해설]', '빠른 정답', '작업공간', '[출처]'):
                        self.assertNotIn(leakage, text)
                    self.assertIsNone(re.search(r'[A-Za-z0-9+/]{80,}={0,2}', text))
                    # 위 정규식은 실제 수식 캡션에 있던 긴 인코딩 문자열 같은 잡음을 찾는다.
                    # 이 두 자료의 문제 본문에는 그림이 없다는 조사값도 대조한다.
                    self.assertFalse(any(s.kind == 'media' for b in problem.blocks for s in b.spans))


if __name__ == '__main__':
    # 이 파일만 직접 실행해도 unittest가 test_ 함수들을 찾아 검사할 수 있다.
    unittest.main()
