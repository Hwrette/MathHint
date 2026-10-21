"""Conservative, rule-based Hancom equation-script conversion.

Supported: nested braces, atom-scoped infix ``over``, sub/superscripts,
explicit LEFT/RIGHT delimiters (including invisible ``.``), sqrt, indexed
``root <index> of <radicand>``, roman/italic declarations, accents, common
functions/Greek letters/operators, primes, and cases. Backticks are layout
spacing, while ``~`` becomes a LaTeX quad. No LLM or symbolic rewriting is used.

A successful result means the script fits these explicit syntax rules; it is
not a proof that the conversion is mathematically equivalent to the source.
Unknown commands, incomplete roots, and unbalanced structures fail closed.
"""
from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class ConversionResult:
    latex: str | None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class _Token:
    value: str
    position: int


@dataclass(frozen=True)
class _Node:
    latex: str
    kind: str = "atom"
    inner: str | None = None
    scripts: frozenset[str] = frozenset()


class _ConversionError(ValueError):
    pass


_FUNCTIONS = {name: "\\" + name for name in (
    "log", "ln", "sin", "cos", "tan", "cot", "sec", "csc", "sinh", "cosh",
    "tanh", "lim", "max", "min", "sup", "inf", "exp", "det", "gcd",
)}
_SYMBOLS = {name: "\\" + name for name in (
    "alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta",
    "iota", "kappa", "lambda", "mu", "nu", "xi", "pi", "rho", "sigma",
    "tau", "upsilon", "phi", "chi", "psi", "omega", "times", "cdot",
    "cdots", "ldots", "vdots", "ddots", "pm", "mp", "le", "ge", "ne",
    "approx", "equiv", "sim", "cup", "cap", "subset", "supset", "subseteq",
    "supseteq", "in", "notin", "forall", "exists", "partial", "nabla",
    "sum", "prod", "int", "infty", "emptyset", "therefore", "because",
)}
_SYMBOLS.update({"rarrow": r"\rightarrow", "larrow": r"\leftarrow",
                 "lrarrow": r"\leftrightarrow", "bot": r"\perp",
                 "leq": r"\leq", "geq": r"\geq", "neq": r"\neq"})
_GREEK = {"alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta",
          "iota", "kappa", "lambda", "mu", "nu", "xi", "pi", "rho", "sigma",
          "tau", "upsilon", "phi", "chi", "psi", "omega"}
_CAPITAL_GREEK = {name: name.title() for name in
                  ("gamma", "delta", "theta", "lambda", "xi", "pi", "sigma",
                   "upsilon", "phi", "psi", "omega")}
_SYMBOLS.update({capital: "\\" + capital for capital in _CAPITAL_GREEK.values()})
_SPECIAL = {"over", "left", "right", "sqrt", "root", "of", "rm", "it",
            "bar", "vec", "hat", "dot", "ddot", "tilde", "underline",
            "cases", "prime"}
_WORDS = sorted({name.lower() for name in set(_FUNCTIONS) | set(_SYMBOLS) | _SPECIAL}, key=lambda v: -len(v))
_ALLOWED_PUNCTUATION = set("{}()[]^_+-=<>.,:;|!/'&#~")
_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def _tokenize(script: str) -> list[_Token]:
    tokens: list[_Token] = []
    i = 0
    while i < len(script):
        char = script[i]
        if char.isspace() or char == "`":
            i += 1
            continue
        number = _NUMBER.match(script, i)
        if number:
            tokens.append(_Token(number.group(), i))
            i = number.end()
            continue
        if char.isascii() and char.isalpha():
            # Hancom permits concatenated commands, e.g. rmbar{BC} and sqrt5.
            command = next((word for word in _WORDS
                            if script[i:i + len(word)].lower() == word), None)
            if command:
                original = script[i:i + len(command)]
                if command in _GREEK and original != original.lower():
                    if command not in _CAPITAL_GREEK:
                        raise _ConversionError(f"unsupported uppercase Greek name {original!r} at offset {i}")
                    command = _CAPITAL_GREEK[command]
                tokens.append(_Token(command, i))
                i += len(command)
                continue
            word = re.match(r"[A-Za-z]+", script[i:]).group()
            # Short adjacent letters are conventional implicit products; longer
            # unidentified words could be unsupported commands and are rejected.
            if len(word) > 2 and not (word.isupper() and len(word) <= 4):
                raise _ConversionError(f"unsupported word {word!r} at offset {i}")
            tokens.extend(_Token(c, i + offset) for offset, c in enumerate(word))
            i += len(word)
            continue
        if script[i:i + 2] in {"!=", "<=", ">="}:
            tokens.append(_Token(script[i:i + 2], i))
            i += 2
            continue
        if char in _ALLOWED_PUNCTUATION:
            tokens.append(_Token(char, i))
            i += 1
            continue
        raise _ConversionError(f"unsupported character {char!r} at offset {i}")
    return tokens


def _argument(node: _Node) -> str:
    return node.inner if node.kind == "group" else node.latex


def _join(nodes: list[_Node]) -> str:
    # Spaces terminate LaTeX control words; mathematical spacing stays TeX's job.
    return " ".join(n.latex for n in nodes if n.latex)


class _Parser:
    def __init__(self, tokens: list[_Token]):
        self.tokens = tokens
        self.i = 0

    def peek(self) -> str | None:
        return self.tokens[self.i].value if self.i < len(self.tokens) else None

    def take(self) -> str:
        if self.i >= len(self.tokens):
            raise _ConversionError("unexpected end of equation")
        value = self.tokens[self.i].value
        self.i += 1
        return value

    def expect(self, value: str) -> None:
        actual = self.take()
        if actual != value:
            raise _ConversionError(f"expected {value!r}, found {actual!r}")

    def sequence(self, stops: set[str] | None = None) -> list[_Node]:
        stops = stops or set()
        nodes: list[_Node] = []
        while self.peek() is not None and self.peek() not in stops:
            token = self.peek()
            if token == "it":
                # Restore default math italic; can occur after a closed rm group.
                self.take()
                continue
            if token in {"^", "_", "prime", "'"}:
                if not nodes or nodes[-1].kind in {"operator", "space"}:
                    raise _ConversionError(f"{token!r} has no preceding base")
                nodes[-1] = self.postfix(nodes[-1])
                continue
            if token == "over":
                self.take()
                if not nodes or nodes[-1].kind in {"operator", "space"}:
                    raise _ConversionError("fraction has no numerator")
                numerator = nodes.pop()
                if numerator.kind == "fraction":
                    raise _ConversionError("chained over requires explicit grouping")
                denominator = self.atom()
                if denominator.kind in {"operator", "space"}:
                    raise _ConversionError("fraction denominator must be an atom or group")
                denominator = self.postfix(denominator)
                nodes.append(_Node(r"\frac{" + _argument(numerator) + "}{" + _argument(denominator) + "}", "fraction"))
                continue
            nodes.append(self.postfix(self.atom()))
        return nodes

    def postfix(self, node: _Node) -> _Node:
        scripts = set(node.scripts)
        while self.peek() in {"^", "_", "prime", "'"}:
            mark = self.take()
            if mark in {"prime", "'"}:
                node = _Node(node.latex + "'", "scripted", scripts=frozenset(scripts))
                continue
            if mark in scripts:
                raise _ConversionError(f"duplicate {mark!r} script without grouping")
            scripts.add(mark)
            if self.peek() == "it":
                self.take()
            argument = self.atom(script_argument=True)
            if argument.kind in {"operator", "space"}:
                raise _ConversionError(f"{mark!r} requires an argument")
            node = _Node(node.latex + mark + "{" + _argument(argument) + "}", "scripted", scripts=frozenset(scripts))
        return node

    def atom(self, script_argument: bool = False) -> _Node:
        token = self.take()
        if token == "{":
            content = _join(self.sequence({"}"}))
            self.expect("}")
            if not content:
                raise _ConversionError("empty group requires source review")
            return _Node("{" + content + "}", "group", content)
        if token in {"(", "["}:
            closing = ")" if token == "(" else "]"
            content = _join(self.sequence({closing}))
            self.expect(closing)
            return _Node(token + content + closing)
        if token == "left":
            opening = self.take()
            if opening not in {"(", "[", "{", "|", "."}:
                raise _ConversionError(f"unsupported LEFT delimiter {opening!r}")
            content = _join(self.sequence({"right"}))
            self.expect("right")
            closing = self.take()
            if closing not in {")", "]", "}", "|", "."}:
                raise _ConversionError(f"unsupported RIGHT delimiter {closing!r}")
            left = "\\{" if opening == "{" else opening
            right = "\\}" if closing == "}" else closing
            return _Node(r"\left" + left + " " + content + r" \right" + right)
        if token in {"}", ")", "]", "right", "over", "&", "#", "of"}:
            raise _ConversionError(f"unexpected {token!r}; check grouping")
        if token == "rm":
            # Declaration remains active until explicit it, or this group's end.
            content = _join(self.sequence({"it", "}", ")", "]", "right", "&", "#"}))
            if self.peek() == "it":
                self.take()
            if not content:
                raise _ConversionError("rm has no following content")
            return _Node(r"\mathrm{" + content + "}")
        if token == "sqrt":
            radicand = self.atom()
            if radicand.kind in {"operator", "space"}:
                raise _ConversionError("sqrt requires a radicand")
            return _Node(r"\sqrt{" + _argument(radicand) + "}")
        if token == "root":
            index = self.atom()
            if self.peek() != "of":
                raise _ConversionError("indexed root requires 'root <index> of <radicand>'; no implicit repair")
            self.take()
            radicand = self.atom()
            return _Node(r"\sqrt[" + _argument(index) + "]{" + _argument(radicand) + "}")
        if token in {"bar", "vec", "hat", "dot", "ddot", "tilde", "underline"}:
            arg = self.atom()
            if arg.kind in {"operator", "space"}:
                raise _ConversionError(f"{token} requires an argument")
            return _Node("\\" + token + "{" + _argument(arg) + "}")
        if token == "cases":
            return self.cases()
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
                # Unbraced signed scripts are ambiguous; do not guess scope.
                raise _ConversionError("signed script requires braces")
            return _Node(token, "operator")
        if token == "it":
            raise _ConversionError("it cannot be used as an equation atom")
        if token in {"^", "_", "prime", "'"}:
            raise _ConversionError(f"{token!r} has no preceding base")
        if token in {"&", "#"}:
            raise _ConversionError("alignment separators require cases")
        return _Node(token)

    def cases(self) -> _Node:
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
        columns = max(map(len, rows))
        content = r" \\ ".join(" & ".join(row + [""] * (columns - len(row))) for row in rows)
        # HWP commonly uses &&: retain the blank alignment column explicitly.
        return _Node(r"\left\{\begin{array}{" + "l" * columns + "}" + content + r"\end{array}\right.")


def convert_equation(script: str) -> ConversionResult:
    """Convert supported source syntax, returning warnings instead of guessing."""
    if not isinstance(script, str):
        raise TypeError("script must be a string")
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
    except (_ConversionError, RecursionError) as error:
        return ConversionResult(None, (str(error),))
