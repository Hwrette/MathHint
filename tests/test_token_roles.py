"""설명용 역할 분류가 불용어 확정이나 원시 토큰 변환을 하지 않는지 확인한다."""

import json
from pathlib import Path
import unittest

from mathhint_analysis.token_analysis.roles import CATEGORIES, classify_token


class TokenRoleTests(unittest.TestCase):
    def test_math_and_display_commands_are_distinguished_without_deletion_decisions(self):
        expected = {r"latex:\lim": "LaTeX 수학 명령어", r"latex:\sin": "LaTeX 수학 명령어",
                    r"latex:\frac": "LaTeX 수학 명령어", r"latex:\left": "표시용 LaTeX 명령어",
                    "latex:{": "괄호·수식 구조 기호", "latex:}": "괄호·수식 구조 기호",
                    r"latex:\{": "괄호·수식 구조 기호", r"latex:\begin": "괄호·수식 구조 기호",
                    "latex:2": "LaTeX 숫자", "latex:x": "LaTeX 변수명", r"latex:\theta": "LaTeX 변수명"}
        for token, category in expected.items():
            with self.subTest(token=token):
                value = classify_token(token)
                self.assertEqual(value["category"], category)
                self.assertEqual(set(value), {"source", "category", "meaning", "ambiguity_note", "information_loss_if_removed"})

    def test_ambiguous_kiwi_forms_are_not_asserted_to_be_particles(self):
        for form in ("가", "이", "수", "각", "해", "한", "차"):
            value = classify_token("kiwi:" + form, region="problems")
            self.assertEqual(value["category"], "분류 불확실·검토 필요")
            self.assertIn("품사·문맥", value["ambiguity_note"])
        self.assertEqual(classify_token("kiwi:대입")["category"], "풀이 방법 자연어")
        self.assertEqual(classify_token("kiwi:판별식")["category"], "수학 개념 자연어")

    def test_solution_layout_label_is_region_specific_and_context_uncertain(self):
        self.assertEqual(classify_token("kiwi:정답", region="solutions")["category"], "해설지 고정 양식")
        self.assertNotEqual(classify_token("kiwi:정답", region="problems")["category"], "해설지 고정 양식")
        self.assertIn("제목 용법", classify_token("kiwi:해설", region="solutions")["ambiguity_note"])
        self.assertIn("논리적 역할", classify_token("kiwi:따라서")["ambiguity_note"])

    def test_existing_777_coordinates_have_nonempty_descriptions_and_no_mutation(self):
        root = Path(__file__).resolve().parents[1]
        count = 0
        for region, size in (("problems", 346), ("solutions", 431)):
            path = root / "data/vectors" / region / "vocabulary.json"
            before = path.read_bytes()
            vocabulary = json.loads(before)
            self.assertEqual(len(vocabulary), size)
            for token in vocabulary:
                role = classify_token(token, region=region)
                self.assertIn(role["category"], CATEGORIES)
                self.assertTrue(all(isinstance(value, str) and value for value in role.values()))
                count += 1
            self.assertEqual(path.read_bytes(), before)
        self.assertEqual(count, 777)

    def test_oov_math_roles_are_described_without_extending_a_vocabulary(self):
        self.assertEqual(classify_token(r"latex:\gamma")["category"], "LaTeX 변수명")
        self.assertEqual(classify_token(r"latex:\log")["category"], "LaTeX 수학 명령어")
        self.assertEqual(classify_token(r"latex:\circ")["category"], "연산·관계 기호")
        self.assertEqual(classify_token(r"latex:\unknown")["category"], "분류 불확실·검토 필요")
        with self.assertRaises(ValueError):
            classify_token("unprefixed")
