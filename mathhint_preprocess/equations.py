r"""한글 전용 수식 스크립트를 정해진 규칙으로 LaTeX로 옮기는 모듈.

HWPX의 ``hp:script``에는 LaTeX가 아니라 한글 수식 편집기용 명령이 들어 있다.
예를 들어 ``{1} over {2}``는 이 모듈에서 ``\frac{1}{2}``로 바뀐다.
LLM에 식을 다시 해석시키거나, 식을 계산해서 다른 모양으로 바꾸지는 않는다.

처리 순서는 다음과 같다.
1. ``_tokenize``: 원본 문자열을 숫자, 명령, 괄호 등의 작은 단위인 토큰으로 나눈다.
2. ``_Parser``: 토큰을 순서대로 읽고, 중괄호 안에서는 같은 처리 함수를 다시 호출한다.
3. ``_Node``: 처리 중인 한 조각의 LaTeX와 그룹·첨자 정보를 잠시 보관한다.
4. ``convert_equation``: 완성된 문자열 또는 검토가 필요한 이유를 돌려준다.

현재 지원하는 규칙은 중첩 중괄호, 양옆 한 덩어리에 적용되는 ``over``, 위·아래
첨자, ``LEFT``/``RIGHT`` 괄호, 제곱근, ``root <지수> of <대상>`` 꼴의 근호,
숫자 대상의 ``ROOT7`` 제곱근 표기, 글꼴 선언, 일부 장식 기호·함수·그리스
문자·연산자·프라임·조건별 식·행렬식이 아닌 행별 정렬 구문이다.
한글 수식의 백틱(``)은 배치용 간격으로 취급하고, ``~``는 LaTeX의 넓은 간격
``\quad``로 바꾼다. 한글 수식 전체 문법이나 일반적인 수학 의미 분석기는 아니다.

중요한 한계: 변환 성공은 '이 프로그램이 지원하는 구문에 맞았다'는 뜻이다.
원본과 수학적으로 동등하다는 증명도, 교육과정 적합성의 확인도 아니다.
모르는 명령, 불완전한 근호, 맞지 않는 괄호는 그럴듯하게 고치지 않고 경고한다.
호출한 쪽에서 원본 문자열을 보존하고 이 경고를 함께 검토해야 한다.
"""
# 타입 힌트의 평가를 늦춘다. 아래의 str | None 같은 표기는 값의 종류를 설명한다.
from __future__ import annotations

# dataclass는 데이터를 담는 클래스를 간단히 만들고, re는 정규식 검색을 제공한다.
from dataclasses import dataclass
import re


@dataclass(frozen=True)
class ConversionResult:
    """다른 모듈에 전달하는 변환 결과.

    ``latex``는 성공하면 문자열, 변환할 수 없으면 ``None``이다. None은 빈 문자열과
    달리 '결과가 없음'을 명시한다. ``warnings``는 경고 문자열을 순서대로 담는
    튜플이며, ``tuple[str, ...]``의 ...은 문자열이 여러 개 올 수 있다는 뜻이다.
    기본값 ``()``는 경고가 없다는 뜻이다. ``frozen=True``인 dataclass이므로
    만들어진 결과의 필드를 나중에 실수로 바꾸지 못한다.
    """
    latex: str | None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class _Token:
    """원본에서 읽은 한 단위와 그 시작 위치.

    ``value``에는 'sqrt', '12', '{' 같은 내용, ``position``에는 원본 문자열에서
    시작한 글자 번호가 들어간다. 파이썬의 글자 번호는 0부터 센다. 이름 앞의
    밑줄(_)은 외부용 API가 아닌 모듈 내부 보조 자료라는 관례다.
    """
    value: str
    position: int


@dataclass(frozen=True)
class _Node:
    """변환 중인 한 덩어리의 문자열과 필요한 최소한의 상태.

    ``kind``는 일반 원자(atom), 그룹(group), 연산자(operator) 등을 구별한다.
    여기서 원자는 '현재 규칙에서 하나로 다루는 수식 조각'이라는 뜻이다.
    ``inner``는 그룹의 바깥 중괄호를 제외한 내용이고, ``scripts``는 이미 붙인
    첨자 기호인 ^와 _를 기록한다. ``frozenset``은 중복을 없애는 집합(set)의
    수정 불가능한 형태다. 완전한 수학 표현식 트리를 만드는 클래스는 아니다.
    """
    latex: str
    kind: str = "atom"
    inner: str | None = None
    scripts: frozenset[str] = frozenset()


class _ConversionError(ValueError):
    """지원하지 않는 구문이나 불완전한 수식을 내부에서 알리는 전용 오류.

    ValueError를 상속하여 잘못된 값이라는 성격을 유지한다. 아래의 pass는 이
    클래스에 추가 동작이 없다는 뜻이며, 오류 메시지는 발생 지점에서 넣는다.
    """
    pass


# 사전(dict)은 '원본 명령 -> LaTeX 명령'을 연결한다. 사전 내포(comprehension)는
# 목록의 각 이름에 같은 작업을 적용하는 문법이다. 예를 들어 log의 값은 \log다.
# 일반 문자열에서 백슬래시 두 개는 실제 백슬래시 한 개를 나타낸다.
_FUNCTIONS = {name: "\\" + name for name in (
    "log", "ln", "sin", "cos", "tan", "cot", "sec", "csc", "sinh", "cosh",
    "tanh", "lim", "max", "min", "sup", "inf", "exp", "det", "gcd",
)}
# 함수와 달리 그리스 문자, 연산, 관계 기호 등에 쓰는 명령을 모은다.
_SYMBOLS = {name: "\\" + name for name in (
    "alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta",
    "iota", "kappa", "lambda", "mu", "nu", "xi", "pi", "rho", "sigma",
    "tau", "upsilon", "phi", "chi", "psi", "omega", "times", "cdot",
    "cdots", "ldots", "vdots", "ddots", "pm", "mp", "le", "ge", "ne",
    "approx", "equiv", "sim", "cup", "cap", "subset", "supset", "subseteq",
    "supseteq", "in", "notin", "forall", "exists", "partial", "nabla",
    "sum", "prod", "int", "infty", "emptyset", "therefore", "because", "circ",
)}
# 한글 명령과 LaTeX 명령의 이름이 다르면 별도의 대응표를 덧붙인다.
# r"..."는 백슬래시를 일반 문자로 읽는 raw 문자열이라 LaTeX 표기에 편리하다.
_SYMBOLS.update({"rarrow": r"\rightarrow", "larrow": r"\leftarrow",
                 "lrarrow": r"\leftrightarrow", "bot": r"\perp",
                 "leq": r"\leq", "geq": r"\geq", "neq": r"\neq",
                 "nearrow": r"\nearrow", "searrow": r"\searrow",
                 "vert": r"\vert", "divide": r"\div"})
# 중괄호로 값을 나열한 set은 '이름이 포함되는가?'를 확인할 때 사용한다.
# 그리스 문자는 대소문자가 바뀌면 다른 기호가 될 수 있어 별도로 분류한다.
_GREEK = {"alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta",
          "iota", "kappa", "lambda", "mu", "nu", "xi", "pi", "rho", "sigma",
          "tau", "upsilon", "phi", "chi", "psi", "omega"}
# 확실하게 대응시킬 수 있는 대문자 그리스 이름만 허용한다. pi는 π, PI는 Π다.
_CAPITAL_GREEK = {name: name.title() for name in
                  ("gamma", "delta", "theta", "lambda", "xi", "pi", "sigma",
                   "upsilon", "phi", "psi", "omega")}
_SYMBOLS.update({capital: "\\" + capital for capital in _CAPITAL_GREEK.values()})
# 아래 명령은 단순 치환으로 끝나지 않고 괄호나 다음 대상을 더 읽어야 한다.
_SPECIAL = {"over", "left", "right", "sqrt", "root", "of", "rm", "it", "bold",
            "bar", "overline", "vec", "hat", "dot", "ddot", "tilde", "underline",
            "cases", "prime", "eqalign", "pile", "rpile", "lpile"}
# 후보 이름의 합집합(|)을 만든 뒤 긴 이름부터 검사한다. 예를 들어 subseteq를
# subset과 나머지 글자로 잘못 나누지 않기 위해서다. lambda는 짧은 익명 함수이고,
# -len(v)를 정렬 기준으로 쓰면 긴 단어가 앞에 온다.
_WORDS = sorted({name.lower() for name in set(_FUNCTIONS) | set(_SYMBOLS) | _SPECIAL}, key=lambda v: -len(v))
# 허용한 구두점만 통과시켜, 모르는 문자가 조용히 삭제되는 일을 막는다.
_ALLOWED_PUNCTUATION = set("{}()[]^_+-=<>.,:;|!/'&#~")
# 정규식: 숫자 한 개 이상(\d+), 선택적으로 소수점과 숫자가 뒤따르는 형태.
# compile로 패턴을 한 번 준비하고 토큰을 읽을 때마다 재사용한다.
_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def _tokenize(script: str) -> list[_Token]:
    """원본을 왼쪽부터 읽어 토큰 목록으로 만든다. 수학적 계산은 하지 않는다.

    i는 아직 처리하지 않은 첫 글자의 위치인 '커서'다. 토큰을 하나 읽으면 그
    길이만큼 i를 전진시킨다. 명령의 범위를 결정할 수 없으면 오류를 발생시키며,
    이 오류는 공개 함수 convert_equation에서 검토 경고로 바뀐다.
    """
    tokens: list[_Token] = []
    i = 0
    while i < len(script):
        char = script[i]
        # 공백·백틱은 이 단계에서 의미를 담는 토큰으로 남기지 않는다.
        # 단, 아래의 두 글자 연산자 검사는 원본 문자열을 보므로 !=와 ! =는 구별된다.
        if char.isspace() or char == "`":
            i += 1
            continue
        # These are explicit HWP character aliases, not guessed punctuation fixes.
        unicode_symbols = {"≤": "leq", "≥": "geq", "≠": "neq", "∞": "infty",
                           "→": "rarrow", "←": "larrow", "↔": "lrarrow"}
        if char in unicode_symbols:
            tokens.append(_Token(unicode_symbols[char], i))
            i += 1
            continue
        if char in "㉠㉡㉢㉣㉤㉥㉦㉧㉨㉩":
            tokens.append(_Token(char, i))
            i += 1
            continue
        # match는 현재 커서에서 패턴이 시작하는지 확인한다. 숫자가 잡히면 여러
        # 글자로 된 12나 3.14도 하나의 토큰으로 보관하고 마지막 위치로 이동한다.
        number = _NUMBER.match(script, i)
        if number:
            tokens.append(_Token(number.group(), i))
            i = number.end()
            continue
        if char.isascii() and char.isalpha():
            # 한글 수식에는 rmbar{BC}, sqrt5처럼 명령과 대상이 붙어서 나오기도 한다.
            # next(..., None)은 조건을 만족하는 첫 후보를 찾고, 없으면 None을 준다.
            command = next((word for word in _WORDS
                            if script[i:i + len(word)].lower() == word), None)
            if command:
                original = script[i:i + len(command)]
                # Uppercase INF is the HWP infinity glyph. Lowercase inf keeps
                # its separate infimum-function meaning.
                if original == "INF":
                    command = "infty"
                # 연산자 명령의 대소문자는 같은 것으로 읽더라도 그리스 기호는
                # 실제 대문자 표기를 따로 확인한다. 모르는 대응을 소문자로 바꾸지 않는다.
                if command in _GREEK and original != original.lower():
                    if command not in _CAPITAL_GREEK:
                        raise _ConversionError(f"unsupported uppercase Greek name {original!r} at offset {i}")
                    command = _CAPITAL_GREEK[command]
                tokens.append(_Token(command, i))
                i += len(original)
                continue
            word = re.match(r"[A-Za-z]+", script[i:]).group()
            # 짧은 글자 나열 ab, ax나 짧은 대문자 점 이름은 글자별로 나눈다.
            # 긴 미확인 단어는 미지원 명령일 수 있어 임의의 변수 곱으로 바꾸지 않는다.
            if len(word) > 2 and not (word.isupper() and len(word) <= 4):
                raise _ConversionError(f"unsupported word {word!r} at offset {i}")
            # enumerate는 각 글자와 0부터 시작하는 번호를 함께 준다. extend는
            # 이렇게 만든 여러 토큰을 기존 목록 끝에 한꺼번에 추가한다.
            tokens.extend(_Token(c, i + offset) for offset, c in enumerate(word))
            i += len(word)
            continue
        # [i:i + 2]는 현재 위치부터 두 글자를 자르는 슬라이스다. !=는 부등호지만
        # x! =0의 !는 팩토리얼이므로, 붙어 있는 원본 두 글자만 하나로 묶는다.
        if script[i:i + 3] == "<->":
            tokens.append(_Token("lrarrow", i))
            i += 3
            continue
        if script[i:i + 2] in {"->", "<-"}:
            tokens.append(_Token({"->": "rarrow", "<-": "larrow"}[script[i:i + 2]], i))
            i += 2
            continue
        if script[i:i + 2] in {"!=", "<=", ">="}:
            tokens.append(_Token(script[i:i + 2], i))
            i += 2
            continue
        if char in _ALLOWED_PUNCTUATION:
            tokens.append(_Token(char, i))
            i += 1
            continue
        # 어떤 허용 규칙에도 맞지 않으면 원본 글자를 버리지 않고 검토를 요청한다.
        raise _ConversionError(f"unsupported character {char!r} at offset {i}")
    return tokens


def _argument(node: _Node) -> str:
    r"""이미 그룹인 대상의 바깥 중괄호만 벗겨 명령의 인자로 넣는다.

    예를 들어 {a+b}를 분자에 넣을 때 \frac가 자체 중괄호를 추가하므로 내용인
    a+b만 사용한다. 식 내부의 중첩 괄호를 평탄화하는 작업은 아니다.
    """
    return node.inner if node.kind == "group" else node.latex


def _join(nodes: list[_Node]) -> str:
    """조각들의 LaTeX를 공백으로 이어 하나의 문자열로 만든다."""
    # \log와 a를 바로 붙이면 \loga라는 다른 명령처럼 읽힐 수 있으므로 구분한다.
    # 실제 수식의 시각적 간격은 LaTeX가 처리한다. 빈 조각은 연결에서 제외한다.
    return " ".join(n.latex for n in nodes if n.latex)


class _Parser:
    """토큰을 읽으며 지원하는 괄호·분수·첨자 구조를 복원하는 내부 처리기.

    self.tokens는 입력 목록, self.i는 다음에 읽을 토큰의 위치다. self는 현재
    객체 자신을 가리키므로 여러 메서드가 같은 커서 상태를 공유할 수 있다.
    재귀 호출은 괄호 안의 작은 문제를 같은 규칙으로 처리하기 위해 사용한다.
    """
    def __init__(self, tokens: list[_Token]):
        """객체가 만들어질 때 입력을 보관하고 커서를 처음인 0에 둔다."""
        self.tokens = tokens
        self.i = 0

    def peek(self) -> str | None:
        """커서를 움직이지 않고 다음 값을 본다. 끝이면 None을 준다."""
        return self.tokens[self.i].value if self.i < len(self.tokens) else None

    def take(self) -> str:
        """토큰 하나를 소비하고 커서를 전진시킨다. 이미 끝이면 오류다."""
        if self.i >= len(self.tokens):
            raise _ConversionError("unexpected end of equation")
        value = self.tokens[self.i].value
        self.i += 1
        return value

    def expect(self, value: str) -> None:
        """다음 토큰을 소비하되 예상한 닫는 기호 등이 맞는지 확인한다.

        예상과 다르면 누락된 괄호를 자동으로 추가하지 않는다. 반환값의 None은
        별도의 계산 결과 대신 '검사를 마쳤다'는 동작만 수행한다는 뜻이다.
        """
        actual = self.take()
        if actual != value:
            raise _ConversionError(f"expected {value!r}, found {actual!r}")

    def sequence(self, stops: set[str] | None = None) -> list[_Node]:
        """현재 범위의 수식 조각들을 읽고, 멈춤 기호 직전에서 끝낸다.

        stops가 {"}"}라면 닫는 중괄호 앞까지 처리하고 괄호 자체는 남겨 둔다.
        호출한 쪽이 expect로 그것을 소비한다. 기본값 None 대신 매번 새 set을
        만드는 이유는 함수 호출 사이에 수정 가능한 기본 집합을 공유하지 않기 위해서다.
        nodes는 현재 범위에서 이미 처리한 조각을 순서대로 보관하는 목록이다.
        """
        stops = stops or set()
        nodes: list[_Node] = []
        while self.peek() is not None and self.peek() not in stops:
            token = self.peek()
            # HWP emits a layout-only empty group immediately after a limit
            # and its subscript. Do not allow empty operands elsewhere.
            if (token == "{" and self.i + 1 < len(self.tokens)
                    and self.tokens[self.i + 1].value == "}"
                    and nodes and nodes[-1].latex.startswith(r"\lim")
                    and nodes[-1].kind in {"atom", "scripted"}):
                self.take()
                self.take()
                continue
            if token == "it":
                # 기본 수학 이탤릭체로 복귀한다. rm 그룹이 이미 끝난 뒤에도
                # 나타날 수 있다. 글꼴만 복귀하며 이전 조각의 첨자 정보는 유지한다.
                self.take()
                continue
            if token in {"^", "_", "prime", "'"}:
                if not nodes or nodes[-1].kind in {"operator", "space"}:
                    raise _ConversionError(f"{token!r} has no preceding base")
                # [-1]은 목록의 마지막 원소다. 직전 대상에 붙는 첨자를 처리한다.
                nodes[-1] = self.postfix(nodes[-1])
                continue
            if token == "over":
                self.take()
                if not nodes or nodes[-1].kind in {"operator", "space"}:
                    raise _ConversionError("fraction has no numerator")
                # over는 현재 범위 전체가 아니라 바로 앞의 한 덩어리를 분자로 쓴다.
                # 예: 2log_a{x}over{y}+1 -> 2 log_a (x/y) + 1.
                # 여러 항을 분자에 넣으려면 {a+b}처럼 명시적인 그룹이 있어야 한다.
                # pop은 마지막 조각을 목록에서 꺼내면서 제거한다.
                numerator = nodes.pop()
                # a over b over c는 어느 분수를 다시 나누는지 범위가 불명확하다.
                # {{a} over {b}} over {c}처럼 원본이 범위를 명시해야 통과시킨다.
                if numerator.kind == "fraction":
                    raise _ConversionError("chained over requires explicit grouping")
                denominator = self.atom()
                if denominator.kind in {"operator", "space"}:
                    raise _ConversionError("fraction denominator must be an atom or group")
                denominator = self.postfix(denominator)
                nodes.append(_Node(r"\frac{" + _argument(numerator) + "}{" + _argument(denominator) + "}", "fraction"))
                continue
            # 먼저 하나의 기본 덩어리를 읽고, 바로 뒤에 붙은 첨자까지 처리한다.
            nodes.append(self.postfix(self.atom()))
        return nodes

    def postfix(self, node: _Node) -> _Node:
        """직전 덩어리 뒤에 붙은 위첨자(^), 아래첨자(_), 프라임을 처리한다.

        scripts는 이미 사용한 ^와 _의 집합이다. 새 호출에서도 기존 node의 기록을
        복사하므로 x^2 it ^3처럼 글꼴 선언을 사이에 둔 중복 첨자도 잡을 수 있다.
        반면 x^2 it _3는 서로 다른 첨자이므로 허용한다.
        """
        # 수정 가능한 set으로 작업하고, 새 결과에는 다시 frozenset으로 넣는다.
        scripts = set(node.scripts)
        while self.peek() in {"^", "_", "prime", "'"}:
            mark = self.take()
            if mark in {"prime", "'"}:
                node = _Node(node.latex + "'", "scripted", scripts=frozenset(scripts))
                continue
            if mark in scripts:
                raise _ConversionError(f"duplicate {mark!r} script without grouping")
            scripts.add(mark)
            # 첨자 기호 뒤의 글꼴 복귀 명령을 처리해도 첨자의 수학적 범위는 같다.
            if self.peek() == "it":
                self.take()
            argument = self.atom(script_argument=True)
            if argument.kind in {"operator", "space"}:
                raise _ConversionError(f"{mark!r} requires an argument")
            node = _Node(node.latex + mark + "{" + _argument(argument) + "}", "scripted", scripts=frozenset(scripts))
        return node

    def atom(self, script_argument: bool = False) -> _Node:
        """숫자·변수·명령·괄호 그룹 등의 기본 조각 하나를 읽는다.

        괄호를 만나면 sequence를 다시 호출한다. 그 호출이 안쪽 괄호를 모두
        처리하고 돌아온 뒤 바깥 처리를 이어가므로 중첩 구조가 유지된다.
        script_argument는 지금 읽는 대상이 첨자인지 알려 주는 bool(참/거짓)이다.
        """
        token = self.take()
        if token == "{":
            # 일반 중괄호는 보이는 괄호가 아니라 적용 범위를 묶는다. inner를 함께
            # 저장하여 나중에 분자·분모·첨자의 인자로 넣어도 안쪽 구조를 유지한다.
            content = _join(self.sequence({"}"}))
            self.expect("}")
            if not content and not script_argument:
                raise _ConversionError("empty group requires source review")
            return _Node("{" + content + "}", "group", content)
        # 일반 소괄호·대괄호는 보이는 기호이므로 결과에도 그대로 남긴다.
        if token in {"(", "["}:
            closing = ")" if token == "(" else "]"
            content = _join(self.sequence({closing}))
            self.expect(closing)
            return _Node(token + content + closing)
        if token == "left":
            # LEFT/RIGHT는 크기가 조정되는 괄호 한 쌍을 만든다. 구간 [0,1)처럼
            # 양쪽 모양은 달라도 된다. 점(.)은 마침표가 아니라 '보이지 않는 괄호'다.
            opening = self.take()
            if opening not in {"(", "[", "{", "|", "."}:
                raise _ConversionError(f"unsupported LEFT delimiter {opening!r}")
            content = _join(self.sequence({"right"}))
            self.expect("right")
            closing = self.take()
            if closing not in {")", "]", "}", "|", "."}:
                raise _ConversionError(f"unsupported RIGHT delimiter {closing!r}")
            # LaTeX에서 보이는 중괄호는 범위용 { }와 구별되도록 백슬래시가 필요하다.
            left = "\\{" if opening == "{" else opening
            right = "\\}" if closing == "}" else closing
            return _Node(r"\left" + left + " " + content + r" \right" + right)
        if token in {"}", ")", "]", "right", "over", "&", "#", "of"}:
            raise _ConversionError(f"unexpected {token!r}; check grouping")
        if token == "rm":
            # rm은 직립체 글꼴 선언이다. 명시적인 it 복귀 또는 현재 그룹의 끝까지
            # 범위를 읽어 \mathrm{...}로 묶는다. 다른 수학적 식으로 계산하지 않는다.
            content = _join(self.sequence({"it", "}", ")", "]", "right", "&", "#"}))
            if self.peek() == "it":
                self.take()
            if not content:
                raise _ConversionError("rm has no following content")
            return _Node(r"\mathrm{" + content + "}")
        if token == "bold":
            # Explicit groups and the HWP BOLD12 numeric shorthand have an
            # unambiguous extent. Do not invent the scope of a bare variable.
            if self.peek() != "{" and not (self.peek() and _NUMBER.fullmatch(self.peek())):
                raise _ConversionError("bold requires a grouped or numeric argument")
            arg = self.atom()
            return _Node(r"\mathbf{" + _argument(arg) + "}")
        if token == "sqrt":
            # sqrt 뒤의 한 조각을 근호 안에 넣는다. 여러 항이면 {x+1}처럼 묶어야 한다.
            radicand = self.atom()
            if radicand.kind in {"operator", "space"}:
                raise _ConversionError("sqrt requires a radicand")
            return _Node(r"\sqrt{" + _argument(radicand) + "}")
        if token == "root":
            # root 3 of {x+1}는 세제곱근이다. of가 빠진 root{3}을 보고
            # 제곱근인지 다른 근호인지 추측해서 고치지 않는다.
            numeric_shorthand = self.peek() is not None and _NUMBER.fullmatch(self.peek())
            index = self.atom()
            if self.peek() != "of":
                # HWP also spells an ordinary square root as ROOT7 / ROOT 10.
                # Limit the shorthand to an ungrouped numeric radicand so the
                # historically ambiguous root{3} is still sent for review.
                if numeric_shorthand:
                    return _Node(r"\sqrt{" + _argument(index) + "}")
                raise _ConversionError("indexed root requires 'root <index> of <radicand>'; no implicit repair")
            self.take()
            radicand = self.atom()
            return _Node(r"\sqrt[" + _argument(index) + "]{" + _argument(radicand) + "}")
        # 장식 명령도 바로 다음 한 조각에만 적용한다. 예: bar{AB}는 AB 위의 선이다.
        if token in {"bar", "overline", "vec", "hat", "dot", "ddot", "tilde", "underline"}:
            arg = self.atom()
            if arg.kind in {"operator", "space"}:
                raise _ConversionError(f"{token} requires an argument")
            return _Node("\\" + token + "{" + _argument(arg) + "}")
        if token == "cases":
            return self.cases()
        if token in {"eqalign", "pile", "rpile", "lpile"}:
            return self.alignment(token)
        if token in "㉠㉡㉢㉣㉤㉥㉦㉧㉨㉩":
            return _Node(r"\text{" + token + "}")
        # 다음 명령들은 뒤의 범위를 직접 소비하지 않고 대응하는 LaTeX 조각을 준다.
        # 예를 들어 log 뒤의 _{2}는 postfix가 처리한다.
        if token in _FUNCTIONS:
            return _Node(_FUNCTIONS[token])
        if token in _SYMBOLS:
            kind = "operator" if token in {"times", "cdot", "le", "ge", "ne", "leq", "geq", "neq", "rarrow", "larrow"} else "atom"
            return _Node(_SYMBOLS[token], kind)
        if token in {"!=", "<=", ">="}:
            return _Node({"!=": r"\ne", "<=": r"\le", ">=": r"\ge"}[token], "operator")
        if token == "~":
            return _Node(r"\quad", "space")
        if token in "+-=<>:,;":
            if script_argument and token in "+-":
                # 괄호 없는 부호 첨자는 범위를 추측하지 않는다. x^{-2}처럼
                # 부호까지 중괄호로 명시한 입력을 사용해야 한다.
                raise _ConversionError("signed script requires braces")
            return _Node(token, "operator")
        if token == "it":
            raise _ConversionError("it cannot be used as an equation atom")
        if token in {"^", "_", "prime", "'"}:
            raise _ConversionError(f"{token!r} has no preceding base")
        if token in {"&", "#"}:
            raise _ConversionError("alignment separators require cases")
        return _Node(token)

    def alignment(self, command: str) -> _Node:
        """Preserve HWP alignment rows, including layout-only empty rows."""
        self.expect("{")
        rows: list[list[str]] = [[]]
        while True:
            rows[-1].append(_join(self.sequence({"&", "#", "}"})))
            separator = self.take()
            if separator == "}":
                break
            if separator == "#":
                rows.append([])
        columns = max(map(len, rows))
        content = r" \\ ".join(
            " & ".join((cell or "{}") for cell in row + [""] * (columns - len(row)))
            for row in rows
        )
        if command == "eqalign":
            return _Node(r"\begin{aligned}" + content + r"\end{aligned}")
        align = {"pile": "c", "lpile": "l", "rpile": "r"}[command]
        return _Node(r"\begin{array}{" + align * columns + "}" + content + r"\end{array}")

    def cases(self) -> _Node:
        """조건별 식의 행·열 구분을 보존하여 LaTeX array로 옮긴다.

        한글 수식의 &는 다음 열, #은 다음 행을 뜻한다. rows는 '행 목록 안에
        각 행의 칸 목록이 들어 있는' 이중 리스트다. 빈 정렬용 칸도 보존한다.
        """
        self.expect("{")
        rows: list[list[str]] = [[]]
        while True:
            rows[-1].append(_join(self.sequence({"&", "#", "}"})))
            separator = self.take()
            if separator == "}":
                break
            if separator == "#":
                rows.append([])
        if not rows or any(not any(cell for cell in row) for row in rows):
            raise _ConversionError("empty cases row")
        # map(len, rows)는 각 행의 칸 개수를 구하고 max는 가장 큰 값을 고른다.
        # 부족한 칸에는 빈 문자열을 채워 모든 행의 열 수를 맞춘다.
        columns = max(map(len, rows))
        content = r" \\ ".join(" & ".join(row + [""] * (columns - len(row))) for row in rows)
        # &&처럼 &가 연속되면 가운데는 내용 없는 칸이다. 이를 임의로 삭제하지 않는다.
        # LaTeX에서는 &가 열을, 백슬래시 두 개가 행을 구분한다. l은 열의 왼쪽 정렬이다.
        return _Node(r"\left\{\begin{array}{" + "l" * columns + "}" + content + r"\end{array}\right.")


def convert_equation(script: str) -> ConversionResult:
    """지원하는 수식은 변환하고, 확신할 수 없는 구문은 경고 결과로 돌려준다.

    다른 모듈이 사용하는 공개 진입점이다. 원본 문자열을 수정하지 않으며 결과는
    ConversionResult에 담는다. str | None 등의 타입 힌트만으로 입력 검사가
    자동 실행되는 것은 아니므로 isinstance로 실제 입력 종류도 확인한다.
    """
    if not isinstance(script, str):
        raise TypeError("script must be a string")
    # try 안의 처리 중 전용 구문 오류가 나면 except에서 경고로 바꾼다.
    # 잘못된 입력 타입(TypeError)은 호출 방법의 문제이므로 위에서 별도로 발생시킨다.
    try:
        tokens = _tokenize(script)
        if not tokens:
            return ConversionResult(None, ("empty equation script",))
        parser = _Parser(tokens)
        latex = _join(parser.sequence())
        if parser.peek() is not None:
            raise _ConversionError(f"unconsumed token {parser.peek()!r}")
        if not latex:
            raise _ConversionError("equation contains no mathematical content")
        return ConversionResult(latex)
    # 너무 깊이 중첩되어 파이썬의 재귀 한계를 넘는 경우도 임의로 일부를 버리지 않는다.
    # (문자열,)의 끝 쉼표는 원소가 하나인 튜플을 만드는 문법이다.
    except (_ConversionError, RecursionError) as error:
        return ConversionResult(None, (str(error),))
