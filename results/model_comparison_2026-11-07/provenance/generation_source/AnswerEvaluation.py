"""원본 정답과 모델의 명시적 최종 답을 비교하는 보수적인 채점 도구.

풀이 중간에 등장한 숫자나 문제의 선택지 목록으로 답을 추측하지 않는다.
지원 범위는 선택지 ①~⑤와 숫자·분수·제곱근·pi로 된 상수식이다.
판독할 수 없는 출력은 오답으로 단정하지 않고 ``ungradable``로 남긴다.
객관식에서 명시적 '최종정답: 3'은 요청한 선택지 번호 ③으로 해석하며,
수식 상자 안의 3은 값 3으로 해석한다. 선택지 기호를 출력하면 모호함이 없다.
"""

from __future__ import annotations

import ast
import math
import re
from typing import Any


CHOICES = "①②③④⑤"
_FINAL = re.compile(r"(?:최종\s*정답|최종\s*답|final\s*answer)\s*(?:은|는|이|가)?\s*[:：=]?\s*(.*)", re.I)
_ANSWER = re.compile(r"(?:정답|답)\s*(?:은|는|이|가)?\s*[:：=]?\s*(.*)")


def _group(text: str, pos: int) -> tuple[str, int]:
    """중괄호 그룹 하나를 읽는다. 수식 변환에만 쓰며 코드를 실행하지 않는다."""
    while pos < len(text) and text[pos].isspace():
        pos += 1
    if pos >= len(text) or text[pos] != "{":
        raise ValueError("중괄호 그룹이 없습니다.")
    depth = 1
    start = pos + 1
    pos += 1
    while pos < len(text):
        if text[pos] == "{":
            depth += 1
        elif text[pos] == "}":
            depth -= 1
            if depth == 0:
                return text[start:pos], pos + 1
        pos += 1
    raise ValueError("닫히지 않은 중괄호입니다.")


def _latex_expression(text: str, depth: int = 0) -> str:
    if depth > 12 or len(text) > 500:
        raise ValueError("상수식이 너무 깁니다.")
    if re.search(r"\d\s+\d", text):
        raise ValueError("공백으로 분리된 숫자를 하나의 수로 합치지 않습니다.")
    text = text.replace("−", "-").replace("–", "-").replace("π", "pi")
    for token in (r"\left", r"\right", r"\,", r"\;", r"\!", r"\quad", r"\qquad", "$"):
        text = text.replace(token, "")
    text = text.replace(r"\(", "").replace(r"\)", "").replace(r"\[", "").replace(r"\]", "")
    output = []
    pos = 0
    while pos < len(text):
        if text[pos] == "\\":
            command = re.match(r"\\([A-Za-z]+)", text[pos:])
            if not command:
                raise ValueError("지원하지 않는 수식 기호입니다.")
            name = command.group(1)
            pos += len(command.group())
            if name in {"frac", "dfrac", "tfrac"}:
                a, pos = _group(text, pos)
                b, pos = _group(text, pos)
                output.append(f"(({_latex_expression(a, depth + 1)})/({_latex_expression(b, depth + 1)}))")
            elif name == "sqrt":
                a, pos = _group(text, pos)
                output.append(f"sqrt({_latex_expression(a, depth + 1)})")
            elif name in {"mathbf", "mathrm", "text", "boxed", "boldsymbol", "operatorname"}:
                a, pos = _group(text, pos)
                output.append(f"({_latex_expression(a, depth + 1)})")
            elif name == "pi":
                output.append("pi")
            elif name in {"cdot", "times"}:
                output.append("*")
            else:
                raise ValueError(f"지원하지 않는 수식 명령: {name}")
        else:
            char = text[pos]
            output.append("(" if char == "{" else ")" if char == "}" else "**" if char == "^" else char)
            pos += 1
    expression = re.sub(r"\s+", "", "".join(output))
    # 2pi, 3sqrt(2), (2)(3), pi(2) 같은 생략된 곱셈만 복원한다.
    expression = re.sub(r"(?<=[\d)])(?=(?:pi|sqrt|\())", "*", expression)
    expression = re.sub(r"(?<=pi)(?=[\d(])", "*", expression)
    return expression


def numeric_constant(text: str) -> float | None:
    """제한된 상수식을 AST 허용 목록으로 계산한다. eval을 사용하지 않는다."""
    try:
        expression = _latex_expression(text.strip())
        if not expression or len(expression) > 1000 or not re.fullmatch(r"[0-9.+*/()epi\-sqrt]+", expression):
            return None
        root = ast.parse(expression, mode="eval")
        if sum(1 for _ in ast.walk(root)) > 150:
            return None

        def value(node: ast.AST, depth: int = 0) -> float:
            if depth > 25:
                raise ValueError("상수식이 너무 깊습니다.")
            if isinstance(node, ast.Expression):
                result = value(node.body, depth + 1)
            elif isinstance(node, ast.Constant) and type(node.value) in (int, float):
                result = float(node.value)
            elif isinstance(node, ast.Name) and node.id == "pi":
                result = math.pi
            elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
                result = value(node.operand, depth + 1) * (-1 if isinstance(node.op, ast.USub) else 1)
            elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)):
                a, b = value(node.left, depth + 1), value(node.right, depth + 1)
                if isinstance(node.op, ast.Add):
                    result = a + b
                elif isinstance(node.op, ast.Sub):
                    result = a - b
                elif isinstance(node.op, ast.Mult):
                    result = a * b
                elif isinstance(node.op, ast.Div):
                    result = a / b
                else:
                    if abs(b) > 12 or abs(a) > 1e10:
                        raise ValueError("거듭제곱 범위를 넘었습니다.")
                    result = a ** b
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "sqrt" and len(node.args) == 1 and not node.keywords:
                result = math.sqrt(value(node.args[0], depth + 1))
            else:
                raise ValueError("허용하지 않는 상수식입니다.")
            if not isinstance(result, (int, float)) or not math.isfinite(result) or abs(result) > 1e12:
                raise ValueError("유한한 상수식 범위를 넘었습니다.")
            return float(result)

        return value(root)
    except (ValueError, SyntaxError, TypeError, ZeroDivisionError, OverflowError, RecursionError):
        return None


def choice_options(problem_text: str) -> dict[str, str]:
    """문제의 ①~⑤ 뒤에 있는 보기 값을 추출한다. 보기 완비 때만 사용한다."""
    matches = list(re.finditer(r"[①②③④⑤]", problem_text))
    if [m.group() for m in matches] != list(CHOICES):
        return {}
    return {m.group(): problem_text[m.end():matches[i + 1].start() if i + 1 < 5 else len(problem_text)].strip()
            for i, m in enumerate(matches)}


def extract_reference(record: dict[str, Any], problem_text: str = "") -> dict[str, Any]:
    raw = str(record.get("answer_text", "")).strip()
    options = choice_options(problem_text)
    is_choice = raw in CHOICES and len(raw) == 1
    ref = {
        "answer_text": raw,
        "kind": "choice" if is_choice else "value",
        "choice": CHOICES.index(raw) + 1 if is_choice else None,
        "value_text": options.get(raw) if is_choice else raw,
        "source": {key: record.get(key) for key in ("id", "source_file", "source_sha256", "original_number", "current_number")},
    }
    ref["numeric_value"] = numeric_constant(ref["value_text"] or "")
    ref["gradable"] = is_choice or ref["numeric_value"] is not None
    return ref


def _boxed_answers(text: str) -> list[str]:
    answers = []
    for match in re.finditer(r"\\boxed\s*", text):
        try:
            candidate, _ = _group(text, match.end())
            answers.append(candidate)
        except ValueError:
            continue
    return answers


def _candidate(text: str) -> tuple[str | None, str | None]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return None, None
    # 명시된 마지막 최종정답을 우선한다. 뒤에 상충하는 최종정답을 붙이면 마지막 것을 쓴다.
    for pattern, method in ((_FINAL, "final_answer_marker"), (_ANSWER, "answer_marker")):
        hits = [(i, pattern.search(line)) for i, line in enumerate(lines)]
        hits = [(i, m) for i, m in hits if m]
        if hits:
            i, hit = hits[-1]
            answer = hit.group(1).strip()
            if answer:
                return answer, method
            if i + 1 < len(lines):
                return lines[i + 1], method
    boxes = _boxed_answers(text)
    if boxes:
        return boxes[-1], "last_boxed_answer"
    # 마커 없는 출력 전체가 답 한 줄일 때만 허용한다. 풀이의 마지막 임의 숫자는 채택하지 않는다.
    if len(lines) == 1:
        return lines[0], "answer_only"
    return None, None


def _strip_prose(candidate: str) -> str:
    candidate = candidate.strip().replace("`", "")
    candidate = re.sub(r"\*\*(.+?)\*\*", r"\1", candidate)
    candidate = re.sub(r"\s*(?:입니다|이다|이므로|입니다\.|이다\.|입니다!|이다!)\s*[.!。]?\s*$", "", candidate)
    return candidate.strip().rstrip(".。")


def evaluate_answer(output_text: str, reference: dict[str, Any] | str, problem_text: str = "") -> dict[str, Any]:
    """최종 답만 채점한다. 과정 타당성/교과 범위는 이 함수의 평가 대상이 아니다."""
    if isinstance(reference, str):
        reference = extract_reference({"answer_text": reference}, problem_text)
    candidate, method = _candidate(output_text)
    result = {"predicted_answer": candidate, "correct": None, "status": "ungradable",
              "reason": "explicit_final_answer_not_found", "extraction_method": method,
              "reference_answer": reference.get("answer_text"), "predicted_kind": None}
    if not reference.get("gradable"):
        result["reason"] = "reference_answer_not_supported"
        return result
    if candidate is None:
        return result
    candidate = _strip_prose(candidate)
    result["predicted_answer"] = candidate
    symbols = re.findall(r"[①②③④⑤]", candidate)
    numbers = re.findall(r"(?:선택지\s*|보기\s*|option\s*)?([1-5])\s*번", candidate, re.I)
    explicit_choices = {CHOICES.index(symbol) + 1 for symbol in symbols} | {int(number) for number in numbers}
    if reference["kind"] == "choice" and len(explicit_choices) > 1:
        result["reason"] = "conflicting_final_choices"
        return result
    symbol = re.search(r"[①②③④⑤]", candidate)
    number = re.search(r"(?:선택지\s*|보기\s*|option\s*)?([1-5])\s*번", candidate, re.I)
    # '최종정답: 3'은 공통 프롬프트가 지정한 객관식 선택지 번호로 해석한다.
    bare_choice = re.fullmatch(r"\(?([1-5])\)?", candidate) if method in {"final_answer_marker", "answer_marker"} else None
    if reference["kind"] == "choice" and (symbol or number or bare_choice):
        predicted = CHOICES.index(symbol.group()) + 1 if symbol else int((number or bare_choice).group(1))
        result.update(predicted_kind="choice", predicted_choice=predicted,
                      correct=predicted == reference["choice"], reason="choice_index_comparison")
    else:
        boxes = _boxed_answers(candidate)
        value = numeric_constant(boxes[-1] if boxes else candidate)
        target = reference.get("numeric_value")
        result.update(predicted_kind="value", predicted_numeric_value=value)
        if value is None or target is None:
            result["reason"] = "final_answer_not_supported"
            return result
        result.update(correct=math.isclose(value, target, rel_tol=1e-9, abs_tol=1e-9),
                      reason="numeric_constant_comparison_tolerance_1e-9")
    result["status"] = "correct" if result["correct"] else "incorrect"
    return result


# 짧은 이름은 노트북/후속 실험에서도 같은 판정 규칙을 쓰기 위한 별칭이다.
grade_answer = evaluate_answer
