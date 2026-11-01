"""A small GitHub Actions expression evaluator for the label-event wiring tests (#7019).

``_gh_if`` models only the ``needs.*.outputs`` subset the router gates use. The label-event tests
must evaluate whole job ``if:`` conditions, ``concurrency.group`` strings and job ``name:``
expressions under a synthetic ``github`` context, so this evaluator also models ``!``, the
status functions ``always()`` / ``cancelled()`` / ``success()`` / ``failure()``, ``contains()``
and ``format()``. Value semantics follow the runner: ``a && b`` is ``b`` when ``a`` is truthy,
else ``a``; ``a || b`` is ``a`` when truthy, else ``b``; ``null`` and ``''`` are falsy. A
reference the context does not model is an assertion failure, never a silent ``null``, so a
condition that starts reading a new input goes red until the test models it.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

_TOKEN = re.compile(r"\s*(\|\||&&|==|!=|!|\(|\)|,|'[^']*'|[A-Za-z_][A-Za-z0-9_.*\-]*)")
_EXPR = re.compile(r"\$\{\{(.*?)\}\}", re.DOTALL)

#: Job-run status the status functions report. Every tested job is evaluated as if its needs
#: were skipped or failed and the run was not cancelled, which is when a guard has to hold.
_STATUS = {"always": True, "cancelled": False, "success": False, "failure": False}


class _Evaluator:
    def __init__(self, text: str, context: Mapping[str, Any]) -> None:
        self._tokens = _TOKEN.findall(text)
        assert "".join(self._tokens).replace(" ", "") == re.sub(r"\s+", "", text), f"unlexable expression: {text!r}"
        self._pos = 0
        self._context = context

    def evaluate(self) -> Any:
        value = self._or()
        assert self._pos == len(self._tokens), f"unconsumed tokens: {self._tokens[self._pos :]!r}"
        return value

    def _peek(self) -> str | None:
        return self._tokens[self._pos] if self._pos < len(self._tokens) else None

    def _take(self) -> str:
        token = self._tokens[self._pos]
        self._pos += 1
        return token

    def _or(self) -> Any:
        value = self._and()
        while self._peek() == "||":
            self._take()
            right = self._and()
            value = value if value else right
        return value

    def _and(self) -> Any:
        value = self._cmp()
        while self._peek() == "&&":
            self._take()
            right = self._cmp()
            value = right if value else value
        return value

    def _cmp(self) -> Any:
        left = self._unary()
        if self._peek() in {"==", "!="}:
            op = self._take()
            right = self._unary()
            return (left == right) == (op == "==")
        return left

    def _unary(self) -> Any:
        if self._peek() == "!":
            self._take()
            return not self._unary()
        return self._operand()

    def _operand(self) -> Any:
        token = self._take()
        if token == "(":
            value = self._or()
            assert self._take() == ")", "unbalanced parens in expression"
            return value
        if token.startswith("'"):
            return token[1:-1]
        if self._peek() == "(":
            return self._call(token)
        assert token in self._context, f"expression context does not model {token!r}"
        return self._context[token]

    def _call(self, function: str) -> Any:
        self._take()
        args: list[Any] = []
        while self._peek() != ")":
            args.append(self._or())
            if self._peek() == ",":
                self._take()
        self._take()
        if function in _STATUS:
            assert not args, f"{function}() takes no arguments"
            return _STATUS[function]
        if function == "contains":
            haystack, needle = args
            return needle in haystack if isinstance(haystack, (list, tuple)) else str(needle).lower() in str(haystack).lower()
        if function == "format":
            template, *values = args
            return re.sub(r"\{(\d+)\}", lambda m: _render(values[int(m.group(1))]), template)
        raise AssertionError(f"unmodeled function {function}()")


def _render(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def evaluate(raw: str, context: Mapping[str, Any]) -> Any:
    """Evaluate one ``if:`` condition (with or without the ``${{ }}`` wrapper)."""
    text = raw.strip()
    match = re.fullmatch(r"\$\{\{(.*)\}\}", text, re.DOTALL)
    return _Evaluator(match.group(1) if match else text, context).evaluate()


def interpolate(raw: str, context: Mapping[str, Any]) -> str:
    """Render a string that embeds ``${{ }}`` expressions (a ``name:`` or a ``concurrency.group``)."""
    return _EXPR.sub(lambda m: _render(_Evaluator(m.group(1), context).evaluate()), raw)


def github_context(
    event_name: str,
    *,
    action: str | None = None,
    label: str | None = None,
    labels: Sequence[str] = (),
    repository: str = "spec-kitty/spec-kitty",
    ref: str = "refs/pull/7/merge",
    sha: str = "a" * 40,
    run_id: int = 1001,
    state: str = "open",
) -> dict[str, Any]:
    """The ``github.*`` references the PR workflows read, for one synthetic event."""
    return {
        "github.repository": repository,
        "github.event_name": event_name,
        "github.event.action": action,
        "github.event.label.name": label,
        "github.event.pull_request.labels.*.name": list(labels) if event_name == "pull_request" else [],
        "github.event.pull_request.state": state if event_name == "pull_request" else None,
        "github.ref": ref,
        "github.sha": sha,
        "github.run_id": run_id,
    }


#: The label-event guard (#7019) every self-starting job of the required-check workflows carries
#: as the conjunct after the fork guard: a run started by a label other than ``pr:pause-ci``, or by
#: any label on a closed PR (no merge ref to test), skips.
LABEL_EVENT_GUARD = (
    "((github.event.label.name == 'pr:pause-ci' && github.event.pull_request.state == 'open') "
    "|| (github.event.action != 'labeled' && github.event.action != 'unlabeled'))"
)

#: The ``concurrency.group`` suffix that gives such a no-op run its own group (#7019).
LABEL_NO_OP_GROUP_SUFFIX = (
    "${{ (github.event.action == 'labeled' || github.event.action == 'unlabeled') "
    "&& (github.event.label.name != 'pr:pause-ci' || github.event.pull_request.state != 'open') "
    "&& format('-label-no-op-{0}', github.run_id) || '' }}"
)
