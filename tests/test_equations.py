"""Independent examples of mathematical scope, structure, and failure handling."""
import unittest

from mathhint_preprocess.equations import ConversionResult, convert_equation


class EquationConversionTests(unittest.TestCase):
    def assertConversion(self, source, latex):
        result = convert_equation(source)
        self.assertEqual(result, ConversionResult(latex, ()), source)

    def assertUnsupported(self, source):
        result = convert_equation(source)
        self.assertIsNone(result.latex, source)
        self.assertTrue(result.warnings, source)

    def test_nested_fraction_does_not_flatten(self):
        self.assertConversion(
            '{{1} over {2}} over {{3} over {4}}',
            r'\frac{\frac{1}{2}}{\frac{3}{4}}',
        )

    def test_fraction_only_consumes_adjacent_atoms(self):
        self.assertConversion('2log_{a}{x}over{y}+1', r'2 \log_{a} \frac{x}{y} + 1')
        self.assertConversion('pi over 2+theta', r'\frac{\pi}{2} + \theta')
        self.assertConversion('sqrt5 over 5', r'\frac{\sqrt{5}}{5}')

    def test_powers_and_log_base_keep_scope(self):
        self.assertConversion(
            'log` _{sqrt {2}} `a+log` _{2} `b',
            r'\log_{\sqrt{2}} a + \log_{2} b',
        )
        self.assertConversion('x^{{1} over {2}}', r'x^{\frac{1}{2}}')
        self.assertConversion('x_{12}^{n+1}', r'x_{12}^{n + 1}')
        self.assertConversion('x^2+x^{12}', r'x^{2} + x^{12}')

    def test_style_restore_does_not_reset_script_tracking(self):
        self.assertUnsupported("x^2 it ^3")
        self.assertUnsupported("x_2 it _3")
        self.assertUnsupported("x^2 prime it ^3")
        self.assertConversion("x^2 it _3", r"x^{2}_{3}")
        self.assertConversion("x_2 it ^3", r"x_{2}^{3}")

    def test_function_powers(self):
        self.assertConversion(
            'sin`^{2}theta+cos`^{2}theta',
            r'\sin^{2} \theta + \cos^{2} \theta',
        )

    def test_nested_delimiters(self):
        self.assertConversion(
            'cos LEFT ( pi over 2 + theta RIGHT )',
            r'\cos \left( \frac{\pi}{2} + \theta \right)',
        )
        self.assertConversion(
            'left|left(x-1right)right|',
            r'\left| \left( x - 1 \right) \right|',
        )

    def test_interval_mixed_delimiters_are_valid(self):
        self.assertConversion('left[0,1right)', r'\left[ 0 , 1 \right)')

    def test_invisible_delimiter_is_preserved(self):
        self.assertConversion('left(k right.', r'\left( k \right.')
        self.assertConversion('left. right }', r'\left.  \right\}')

    def test_roman_declaration_ends_at_it(self):
        self.assertConversion(
            'rm A it LEFT ( 0, log _a 3 RIGHT )',
            r'\mathrm{A} \left( 0 , \log_{a} 3 \right)',
        )
        self.assertConversion('{bar{rm{BC}it}}=a', r'{\bar{\mathrm{{B C}}}} = a')

    def test_indexed_root_requires_explicit_of(self):
        self.assertConversion('root {3} of {x+1}', r'\sqrt[3]{x + 1}')
        self.assertUnsupported('a^{2root{3}}=3')

    def test_limit_and_prime(self):
        self.assertConversion(
            'lim_{h``rarrow``0}{f left(x+h right)-f left(x right)} over {h}',
            r'\lim_{h \rightarrow 0} \frac{f \left( x + h \right) - f \left( x \right)}{h}',
        )
        self.assertConversion("f`prime LEFT(x RIGHT)", r"f' \left( x \right)")
        self.assertConversion("g''(x)", "g'' (x)")

    def test_case_rows_and_blank_alignment_column_preserved(self):
        self.assertConversion(
            'cases {x&&left(x<0 right)#x^2&&left(x ge 0 right)}',
            r'\left\{\begin{array}{lll}x &  & \left( x < 0 \right) \\ x^{2} &  & \left( x \ge 0 \right)\end{array}\right.',
        )

    def test_greek_case_does_not_change_symbol(self):
        self.assertConversion("pi+PI+Gamma+gamma", r"\pi + \Pi + \Gamma + \gamma")
        self.assertUnsupported("ALPHA")

    def test_uppercase_operator_aliases(self):
        self.assertConversion('A GEQ 0 TIMES 2 CDOT 3', r'A \geq 0 \times 2 \cdot 3')

    def test_unsupported_words_do_not_become_invented_commands(self):
        for source in ('foobar{x}', 'matrix {1&2#3&4}', 'unknown(x)', r'\sqrt{x}'):
            with self.subTest(source=source):
                self.assertUnsupported(source)

    def test_malformed_source_is_not_repaired(self):
        for source in ('=log`_{3^{2}}`ab}', 'a=3^{ {sqrt{3}} over {6}',
                       'left(x+1', 'x}', '^2', 'x^', 'x^^2', 'a over',
                       'over a', 'x^2^3', 'a over b over c', '{} over {}', 'sqrt{}'):
            with self.subTest(source=source):
                self.assertUnsupported(source)

    def test_empty_equations_are_reviewed(self):
        self.assertUnsupported('')
        self.assertUnsupported('  `` ')

    def test_spacing_does_not_remove_mathematical_operators(self):
        self.assertConversion('a`+`b~=`c', r'a + b \quad = c')
        self.assertConversion('x!=0', r'x \ne 0')
        self.assertConversion('x! =0', 'x ! = 0')
        self.assertConversion('x<=1', r'x \le 1')
        self.assertConversion('x>=1', r'x \ge 1')

    def test_source_is_never_modified(self):
        source = '  log`_{2}`a={1} over {3}` '
        original = source[:]
        convert_equation(source)
        self.assertEqual(source, original)

    def test_non_string_rejected(self):
        with self.assertRaises(TypeError):
            convert_equation(None)


if __name__ == '__main__':
    unittest.main()
