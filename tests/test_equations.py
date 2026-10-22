"""수식 변환 규칙이 중요한 구조를 유지하는지 확인하는 단위 테스트.

unittest는 파이썬 기본 라이브러리의 테스트 도구다. 아래의 test_로 시작하는
메서드는 각각 작은 입력에 대해 사람이 정해 둔 기대 결과와 실제 결과를 비교한다.
분수의 중첩, 로그의 밑, 첨자의 범위처럼 잘못 바뀌면 수학적 의미가 달라지는
사례와, 확신할 수 없는 입력을 조용히 고치지 않는지를 함께 확인한다.

이 테스트를 통과해도 모든 한글 수식의 변환 정확성이 증명되는 것은 아니다.
여기 적힌 사례와 규칙의 동작을 확인하는 것으로, 실제 원본과의 대조 검토는 별도다.
프로젝트 루트에서 다음과 같이 실행할 수 있다.
python -m unittest discover -s tests -p test_equations.py -v
"""
# 외부 패키지 설치 없이 테스트를 작성·실행하는 표준 라이브러리다.
import unittest

from mathhint_preprocess.equations import ConversionResult, convert_equation


class EquationConversionTests(unittest.TestCase):
    """변환 성공과 검토 대상 처리를 같은 기준으로 확인하는 테스트 묶음.

    TestCase를 상속하면 assertEqual, assertIsNone 같은 비교 메서드를 사용할 수
    있다. 조건을 만족하지 못하면 해당 테스트가 실패하며 원인을 표시한다.
    아래의 도우미 메서드 두 개는 반복되는 검사를 한곳에 모은 것이다.
    """
    def assertConversion(self, source, latex):
        """예상 LaTeX와 정확히 같고 경고도 없는 성공 결과인지 확인한다.

        마지막 source 인자는 실패 메시지에 원본을 보여 주기 위한 것이다.
        ConversionResult끼리의 == 비교는 dataclass가 필드별로 처리한다.
        """
        result = convert_equation(source)
        self.assertEqual(result, ConversionResult(latex, ()), source)

    def assertUnsupported(self, source):
        """지원하지 않는 입력이 빈 성공값 대신 None과 경고를 남기는지 확인한다."""
        result = convert_equation(source)
        self.assertIsNone(result.latex, source)
        self.assertTrue(result.warnings, source)

    def test_nested_fraction_does_not_flatten(self):
        """분자와 분모 안의 분수가 각각 유지되는지 확인한다. 단순 문자열 평탄화를 막는다."""
        # 기대값을 변환기 출력에서 자동 생성하지 않고, 사람이 판단한 구조로 적는다.
        # r'...'는 LaTeX의 백슬래시를 그대로 넣기 위한 raw 문자열 표기다.
        self.assertConversion(
            '{{1} over {2}} over {{3} over {4}}',
            r'\frac{\frac{1}{2}}{\frac{3}{4}}',
        )

    def test_fraction_only_consumes_adjacent_atoms(self):
        """over가 식 전체를 삼키지 않고 바로 앞뒤 한 덩어리만 분수로 만드는지 확인한다."""
        self.assertConversion('2log_{a}{x}over{y}+1', r'2 \log_{a} \frac{x}{y} + 1')
        self.assertConversion('pi over 2+theta', r'\frac{\pi}{2} + \theta')
        self.assertConversion('sqrt5 over 5', r'\frac{\sqrt{5}}{5}')

    def test_powers_and_log_base_keep_scope(self):
        """근호가 있는 로그의 밑, 분수 지수, 여러 글자 첨자의 적용 범위를 확인한다."""
        self.assertConversion(
            'log` _{sqrt {2}} `a+log` _{2} `b',
            r'\log_{\sqrt{2}} a + \log_{2} b',
        )
        self.assertConversion('x^{{1} over {2}}', r'x^{\frac{1}{2}}')
        self.assertConversion('x_{12}^{n+1}', r'x_{12}^{n + 1}')
        self.assertConversion('x^2+x^{12}', r'x^{2} + x^{12}')

    def test_style_restore_does_not_reset_script_tracking(self):
        """it 글꼴 복귀 뒤에도 기존 첨자를 기억하고 같은 종류의 중복 첨자를 거부하는지 확인한다."""
        # 같은 위첨자를 다시 붙이는 것은 거부하지만, 위·아래 첨자를 하나씩 붙이는 것은 허용한다.
        self.assertUnsupported("x^2 it ^3")
        self.assertUnsupported("x_2 it _3")
        self.assertUnsupported("x^2 prime it ^3")
        self.assertConversion("x^2 it _3", r"x^{2}_{3}")
        self.assertConversion("x_2 it ^3", r"x_{2}^{3}")

    def test_function_powers(self):
        """sin 제곱과 cos 제곱의 첨자가 함수에 붙고 theta가 바깥에 남는지 확인한다."""
        self.assertConversion(
            'sin`^{2}theta+cos`^{2}theta',
            r'\sin^{2} \theta + \cos^{2} \theta',
        )

    def test_nested_delimiters(self):
        """삼각함수 괄호와 절댓값 안쪽의 괄호처럼 중첩된 짝이 유지되는지 확인한다."""
        self.assertConversion(
            'cos LEFT ( pi over 2 + theta RIGHT )',
            r'\cos \left( \frac{\pi}{2} + \theta \right)',
        )
        self.assertConversion(
            'left|left(x-1right)right|',
            r'\left| \left( x - 1 \right) \right|',
        )

    def test_interval_mixed_delimiters_are_valid(self):
        """닫힌 쪽과 열린 쪽이 다른 [0,1) 구간도 정상적인 괄호 조합으로 허용하는지 확인한다."""
        self.assertConversion('left[0,1right)', r'\left[ 0 , 1 \right)')

    def test_invisible_delimiter_is_preserved(self):
        """RIGHT . 또는 LEFT .의 점을 마침표로 출력하지 않고 보이지 않는 괄호로 옮기는지 확인한다."""
        self.assertConversion('left(k right.', r'\left( k \right.')
        self.assertConversion('left. right }', r'\left.  \right\}')

    def test_roman_declaration_ends_at_it(self):
        """rm의 직립체 범위가 it에서 끝나고, 선분 이름의 윗줄 장식도 유지되는지 확인한다."""
        self.assertConversion(
            'rm A it LEFT ( 0, log _a 3 RIGHT )',
            r'\mathrm{A} \left( 0 , \log_{a} 3 \right)',
        )
        self.assertConversion('{bar{rm{BC}it}}=a', r'{\bar{\mathrm{{B C}}}} = a')

    def test_indexed_root_requires_explicit_of(self):
        """명시적인 세제곱근은 변환하되 of가 빠진 근호의 뜻은 추측하지 않는지 확인한다."""
        self.assertConversion('root {3} of {x+1}', r'\sqrt[3]{x + 1}')
        self.assertUnsupported('a^{2root{3}}=3')

    def test_limit_and_prime(self):
        """극한의 아래첨자·분수 범위와 미분을 나타내는 프라임 한 개·두 개를 확인한다."""
        self.assertConversion(
            'lim_{h``rarrow``0}{f left(x+h right)-f left(x right)} over {h}',
            r'\lim_{h \rightarrow 0} \frac{f \left( x + h \right) - f \left( x \right)}{h}',
        )
        self.assertConversion("f`prime LEFT(x RIGHT)", r"f' \left( x \right)")
        self.assertConversion("g''(x)", "g'' (x)")

    def test_case_rows_and_blank_alignment_column_preserved(self):
        """조건별 식의 행과 열, && 사이의 빈 정렬용 칸을 임의로 없애지 않는지 확인한다."""
        self.assertConversion(
            'cases {x&&left(x<0 right)#x^2&&left(x ge 0 right)}',
            r'\left\{\begin{array}{lll}x &  & \left( x < 0 \right) \\ x^{2} &  & \left( x \ge 0 \right)\end{array}\right.',
        )

    def test_greek_case_does_not_change_symbol(self):
        """소문자 pi와 대문자 PI를 구별하고, 미지원 대문자 그리스 이름은 검토로 보내는지 확인한다."""
        self.assertConversion("pi+PI+Gamma+gamma", r"\pi + \Pi + \Gamma + \gamma")
        self.assertUnsupported("ALPHA")

    def test_uppercase_operator_aliases(self):
        """실제 입력에 있는 GEQ, TIMES, CDOT 같은 대문자 명령의 명시적 대응을 확인한다."""
        self.assertConversion('A GEQ 0 TIMES 2 CDOT 3', r'A \geq 0 \times 2 \cdot 3')

    def test_unsupported_words_do_not_become_invented_commands(self):
        """모르는 명령이나 이미 LaTeX인 입력을 한글 수식인 것처럼 임의로 통과시키지 않는지 확인한다."""
        for source in ('foobar{x}', 'matrix {1&2#3&4}', 'unknown(x)', r'\sqrt{x}'):
            # subTest는 반복문 안의 어느 원본에서 실패했는지 별도로 표시한다.
            with self.subTest(source=source):
                self.assertUnsupported(source)

    def test_malformed_source_is_not_repaired(self):
        """남는 괄호·빠진 괄호·빠진 대상·범위가 불명확한 분수를 자동 수정하지 않는지 확인한다."""
        for source in ('=log`_{3^{2}}`ab}', 'a=3^{ {sqrt{3}} over {6}',
                       'left(x+1', 'x}', '^2', 'x^', 'x^^2', 'a over',
                       'over a', 'x^2^3', 'a over b over c', '{} over {}', 'sqrt{}'):
            with self.subTest(source=source):
                self.assertUnsupported(source)

    def test_empty_equations_are_reviewed(self):
        """빈 문자열이나 배치용 간격만 있는 입력을 정상 수식으로 세지 않는지 확인한다."""
        self.assertUnsupported('')
        self.assertUnsupported('  `` ')

    def test_spacing_does_not_remove_mathematical_operators(self):
        """간격 처리 중 연산자를 잃지 않고, 붙어 있는 !=와 분리된 ! =를 구별하는지 확인한다."""
        self.assertConversion('a`+`b~=`c', r'a + b \quad = c')
        self.assertConversion('x!=0', r'x \ne 0')
        self.assertConversion('x! =0', 'x ! = 0')
        self.assertConversion('x<=1', r'x \le 1')
        self.assertConversion('x>=1', r'x \ge 1')

    def test_source_is_never_modified(self):
        """변환을 호출한 뒤에도 원본 수식 문자열의 내용이 그대로인지 확인한다."""
        source = '  log`_{2}`a={1} over {3}` '
        # [:]는 문자열 전체 범위를 읽는 슬라이스다. 원래의 내용을 비교 기준으로 남긴다.
        original = source[:]
        convert_equation(source)
        self.assertEqual(source, original)

    def test_non_string_rejected(self):
        """문자열이 아닌 입력은 원본 구문 경고와 구별하여 호출 오류인 TypeError로 알리는지 확인한다."""
        # with 블록 안에서 지정한 오류가 발생해야 테스트가 성공한다.
        with self.assertRaises(TypeError):
            convert_equation(None)


# 이 파일을 직접 실행했을 때도 테스트를 시작한다. 다른 모듈이 import할 때는 실행하지 않는다.
if __name__ == '__main__':
    unittest.main()
