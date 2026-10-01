"""GitHub Actions ``if:`` golden-test evaluator, shared by the ``tests/ci`` and ``tests/architectural`` guards.

The wiring tests must not merely grep for the guard text a workflow carries; they evaluate the REAL
``if:`` string under a synthetic ``needs`` context using ordinary boolean semantics (``&&`` binds tighter
than ``||``, parentheses group), the same subset ``ci-router.yml``'s job gates use
(``needs.<job>.outputs.<name> == 'true'`` / ``!= 'true'``). Promoted out of ``test_ci_module_wiring.py``
so a consumer imports a helper module, not a sibling test module.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

_COND_RE = re.compile(r"needs\.([A-Za-z0-9_-]+)\.outputs\.([A-Za-z0-9_]+)\s*(==|!=)\s*'true'")


def strip_expr_wrapper(raw: str) -> str:
    text = raw.strip()
    if text.startswith("${{") and text.endswith("}}"):
        text = text[3:-2].strip()
    return text


def tokenize_gh_if(expr: str) -> list[str]:
    tokens: list[str] = []
    for chunk in re.findall(r"\(|\)|&&|\|\||[^()&|]+", expr):
        stripped = chunk.strip()
        if stripped:
            tokens.append(stripped)
    return tokens


class GhIfEvaluator:
    """Recursive-descent evaluator: `or_expr := and_expr ('||' and_expr)*`,
    `and_expr := atom ('&&' atom)*`, `atom := '(' or_expr ')' | condition`."""

    def __init__(self, tokens: list[str], context: dict[str, bool]) -> None:
        self._tokens = tokens
        self._pos = 0
        self._context = context

    def evaluate(self) -> bool:
        value = self._or_expr()
        assert self._pos == len(self._tokens), f"unconsumed if: tokens: {self._tokens[self._pos :]!r}"
        return value

    def _or_expr(self) -> bool:
        value = self._and_expr()
        while self._peek() == "||":
            self._advance()
            value = self._and_expr() or value
        return value

    def _and_expr(self) -> bool:
        value = self._atom()
        while self._peek() == "&&":
            self._advance()
            value = self._atom() and value
        return value

    def _atom(self) -> bool:
        token = self._peek()
        if token == "(":
            self._advance()
            value = self._or_expr()
            assert self._peek() == ")", f"unbalanced parens in if: near {self._tokens[self._pos :]!r}"
            self._advance()
            return value
        assert token is not None, "ran out of if: tokens"
        self._advance()
        return self._eval_condition(token)

    def _peek(self) -> str | None:
        return self._tokens[self._pos] if self._pos < len(self._tokens) else None

    def _advance(self) -> None:
        self._pos += 1

    def _eval_condition(self, text: str) -> bool:
        match = _COND_RE.fullmatch(text.strip())
        assert match, f"unmodeled if: condition fragment: {text!r}"
        job, name, op = match.group(1), match.group(2), match.group(3)
        key = f"{job}.{name}"
        assert key in self._context, f"golden test context does not model {key!r}"
        value = self._context[key]
        return value if op == "==" else not value


def eval_gh_if(raw_if: str, context: dict[str, bool]) -> bool:
    tokens = tokenize_gh_if(strip_expr_wrapper(raw_if))
    return GhIfEvaluator(tokens, context).evaluate()


_VALUE_TOKEN = re.compile(r"\s*(\|\||&&|==|!=|\(|\)|'[^']*'|[A-Za-z0-9_.\-]+)")


class GhValueExpr:
    """GitHub expression evaluator with VALUE semantics, for a job ``outputs:`` fold.

    ``a && b`` is ``b`` when ``a`` is truthy else ``a``; ``a || b`` is ``a`` when truthy else ``b``;
    the empty string is falsy and a non-empty string (including ``'false'``) is truthy, exactly as on
    the runner. Operands are string literals and dotted context references; ``==`` / ``!=`` compare
    them. A reference the golden context does not model is an assertion failure (never a silent
    empty string), so an expression that starts reading a new input goes red until the test models it.
    """

    def __init__(self, text: str, context: Mapping[str, str]) -> None:
        self._tokens = _VALUE_TOKEN.findall(text)
        assert "".join(self._tokens).replace(" ", "") == re.sub(r"\s+", "", text), f"unlexable expression: {text!r}"
        self._pos = 0
        self._context = context

    def evaluate(self) -> str:
        value = self._or()
        assert self._pos == len(self._tokens), f"unconsumed tokens: {self._tokens[self._pos :]!r}"
        return str(value)

    def _peek(self) -> str | None:
        return self._tokens[self._pos] if self._pos < len(self._tokens) else None

    def _take(self) -> str:
        token = str(self._tokens[self._pos])
        self._pos += 1
        return token

    def _or(self) -> str | bool:
        value = self._and()
        while self._peek() == "||":
            self._take()
            right = self._and()
            value = value if value else right
        return value

    def _and(self) -> str | bool:
        value = self._cmp()
        while self._peek() == "&&":
            self._take()
            right = self._cmp()
            value = right if value else value
        return value

    def _cmp(self) -> str | bool:
        left = self._operand()
        if self._peek() in {"==", "!="}:
            op = self._take()
            right = self._operand()
            return (left == right) == (op == "==")
        return left

    def _operand(self) -> str | bool:
        token = self._take()
        if token == "(":
            value = self._or()
            assert self._take() == ")", "unbalanced parens in expression"
            return value
        if token.startswith("'"):
            return token[1:-1]
        assert token in self._context, f"expression context does not model {token!r}"
        return self._context[token]


def eval_gh_value(raw_expr: str, context: Mapping[str, str]) -> str:
    """The string a ``${{ ... }}`` expression evaluates to (booleans render as ``True``/``False``)."""
    return GhValueExpr(strip_expr_wrapper(raw_expr), context).evaluate()


#: Every router ``changes.*`` filter output, all false; tests flip the group under test.
BASE_CONTEXT_ALL_FALSE: dict[str, bool] = {
    "changes.consolidation": False,
    "changes.auth": False,
    "changes.missions": False,
    "changes.post_merge": False,
    "changes.release": False,
    "changes.status": False,
    "changes.review": False,
    "changes.next": False,
    "changes.lanes": False,
    "changes.dashboard": False,
    "changes.upgrade": False,
    "changes.cli": False,
    "changes.charter": False,
    "changes.agent": False,
    "changes.kernel": False,
    "changes.glossary": False,
    "changes.execution_context": False,
    "changes.core_misc": False,
    "changes.unit": False,
    "changes.specify_cli_runtime": False,
    "changes.docs": False,
    "changes.architectural": False,
    "changes.ci_config": False,
}
