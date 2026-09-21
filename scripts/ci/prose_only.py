"""Pure prose-only classifier for a single Python source diff (#4842 WP01).

``is_prose_only(base_src, head_src)`` decides whether ``head_src`` differs
from ``base_src`` **only** in comments and docstrings — a proven, fail-closed
predicate over two source strings, with no filesystem, git, or network IO and
no ``yaml``/``fnmatch`` import (NFR-001). It is the *content* half of the
CI down-route: ``scripts/ci/gate_selection.py`` stays a pure path->group
router (#2476 single authority) and is never touched here or imported from
here.

Mechanism (see
``kitty-specs/ci-prose-only-downroute-01M31T5S/contracts/prose-only-classifier.md``
and ``research.md`` R4/R5):

1. Parse both sides with ``ast.parse(src, type_comments=True)``.
2. Strip *only* a bare docstring-position string-expression statement —
   ``body[0]`` of a ``Module``/``ClassDef``/``FunctionDef``/
   ``AsyncFunctionDef`` that is ``Expr(Constant(str))`` — never a
   ``JoinedStr`` (f-string), never a ``BinOp`` concatenation, never a
   non-first statement, never a string used as a value.
3. Compare ``ast.dump(stripped, include_attributes=False)`` on both sides
   (position-insensitive, so an added comment line never diffs). Any
   difference here is a real code change (``code_diff``) — return ``False``
   immediately; the guards below can only turn a would-be ``True`` into
   ``False``, never the reverse.
4. Semantically-live comment guard (R5): a ``tokenize`` pass collects every
   ``# type:`` / ``# noqa`` / ``# pragma`` / ``# ruff:`` / ``# fmt:`` /
   ``# mypy:`` / ``# pyright:`` / ``# isort:`` comment (normalized: ``#``
   stripped, whitespace stripped, lowercased) on each side; any multiset
   delta is not prose-only.
5. Encoding-cookie / shebang guard: a PEP 263 ``coding:``/``coding=`` cookie
   or a ``#!`` shebang on line 1 or 2 is compared verbatim; any delta is not
   prose-only.
6. Doctest guard (R4): for every docstring that differs between sides
   (paired positionally — safe only because step 3 already proved the
   non-docstring structure identical), a ``>>>`` prompt on *either* side
   means the doctest content is live code, not prose-only.

Fail-closed (FR-006): a ``None``/empty base, a parse error on either side, or
any other exception resolves to ``False`` — this predicate never raises.
"""

from __future__ import annotations

import ast
import fnmatch
import io
import re
import tokenize
from collections import Counter
from collections.abc import Callable, Iterable, Sequence

__all__ = [
    "is_prose_only",
    "prose_only_pr_verdict",
    "prose_only_reason",
    "reduced_paths",
]

# Reason vocabulary (T-#### convenience surface; the boolean is the contract).
_REASON_PROSE_ONLY = "prose_only"
_REASON_CODE_DIFF = "code_diff"
_REASON_TYPE_COMMENT = "type_comment"
_REASON_NOQA_PRAGMA = "noqa_pragma"
_REASON_ENCODING_COOKIE = "encoding_cookie"
_REASON_DOCTEST = "doctest"
_REASON_PARSE_ERROR = "parse_error"
_REASON_NO_BASE = "no_base"

_TYPE_COMMENT_PREFIX = "type:"
_OTHER_DIRECTIVE_PREFIXES = (
    "noqa",
    "pragma",
    "ruff:",
    "fmt:",
    "mypy:",
    "pyright:",
    "isort:",
)
_DOCSTRING_HOLDER_TYPES = (
    ast.Module,
    ast.ClassDef,
    ast.FunctionDef,
    ast.AsyncFunctionDef,
)
_ENCODING_COOKIE_RE = re.compile(r"coding[:=]\s*([-\w.]+)")
_DOCTEST_PROMPT = ">>>"


def is_prose_only(base_src: str | None, head_src: str | None) -> bool:
    """True iff ``head_src`` differs from ``base_src`` only in comments and
    docstrings.

    Pure: no filesystem, git, or network IO; no ``yaml``/``fnmatch`` import.
    Fail-closed: returns ``False`` on ANY uncertainty, never raises.
    """
    return _evaluate(base_src, head_src)[0]


def prose_only_reason(base_src: str | None, head_src: str | None) -> str:
    """The machine-checkable reason behind :func:`is_prose_only`'s verdict.

    Convenience surface over the same evaluation; the boolean remains the
    contract, this exists so callers/tests can assert *why*.
    """
    return _evaluate(base_src, head_src)[1]


def reduced_paths(
    changed: Iterable[str],
    blob_getter: Callable[[str], tuple[str | None, str | None]],
) -> list[str]:
    """Drop each ``.py`` path proven prose-only; keep everything else.

    ``blob_getter(path) -> (base_src, head_src)``. Pure: the caller owns all
    IO. Fail-closed: if ``blob_getter`` raises for a path, that path is kept
    (never dropped on uncertainty) — mirrors the workflow-side ``git show``
    failure handling in the wiring contract.
    """
    kept: list[str] = []
    for path in changed:
        if path.endswith(".py"):
            try:
                base_src, head_src = blob_getter(path)
            except Exception:
                kept.append(path)
                continue
            if is_prose_only(base_src, head_src):
                continue
        kept.append(path)
    return kept


def prose_only_pr_verdict(
    paths: Sequence[str],
    blob_getter: Callable[[str, str], str | None],
    doc_globs: Sequence[str],
) -> bool:
    """The PR-level "proven prose-only" verdict (mission
    ``ci-prose-only-downroute-01M31T5S``, architect MINOR-2 extraction).

    True iff every path in ``paths`` is either (a) a doc/corpus path —
    matched against ``doc_globs`` via ``fnmatch`` — or (b) a ``.py`` file
    proven prose-only by :func:`is_prose_only`, AND at least one path was a
    proven-prose ``.py`` (an all-doc, zero-``.py`` diff is NOT prose-only —
    it never needed this down-route in the first place).

    ``blob_getter(path, side)`` returns the source text for ``path`` on
    ``"base"`` or ``"head"`` (or raises/returns ``None`` if unavailable).
    The caller closes over the actual base/head refs (e.g. git SHAs) and
    performs the blob fetch itself, so this function stays IO-free
    (NFR-001): it never shells out, reads git, or reads the router YAML —
    ``doc_globs`` is the already-resolved glob tuple, injected by the
    caller (``scripts.ci.gate_selection.load_router().filters``).

    Matcher-equivalence assumption (architect MINOR-3a): ``doc_globs`` is
    matched here with stdlib ``fnmatch``, while the ``changes`` job in
    ``ci-router.yml`` matches the SAME glob strings against changed paths
    via ``dorny/paths-filter`` (picomatch under the hood). The two matchers
    are assumed equivalent for the live doc/corpus glob set (plain
    ``*``/``**``/literal-segment globs); this assumption would need
    re-checking if a future doc/corpus glob relies on a picomatch-only or
    fnmatch-only construct (e.g. brace expansion).

    Fail-closed, mirroring the aggregate this replaces (previously inlined
    in the ``prose-scan`` job's heredoc in ``.github/workflows/ci-router.yml``):
    a ``blob_getter`` exception, a non-prose-only ``.py``, a path that is
    neither doc/corpus nor ``.py``, or no proven-prose ``.py`` at all
    (including empty ``paths``) all resolve to ``False``. Never raises.
    """
    any_prose_py = False
    for path in paths:
        if path.endswith(".py"):
            try:
                base_src = blob_getter(path, "base")
                head_src = blob_getter(path, "head")
            except Exception:
                return False
            if is_prose_only(base_src, head_src):
                any_prose_py = True
                continue
            return False
        elif any(fnmatch.fnmatch(path, pattern) for pattern in doc_globs):
            continue
        else:
            return False
    return any_prose_py


def _evaluate(base_src: str | None, head_src: str | None) -> tuple[bool, str]:
    try:
        if not base_src or not head_src:
            return False, _REASON_NO_BASE

        base_tree = ast.parse(base_src, type_comments=True)
        head_tree = ast.parse(head_src, type_comments=True)

        # These two guards run over raw source, ahead of the dump compare,
        # so their specific reason wins even though ``type_comments=True``
        # also makes a recognized ``# type:`` delta show up as a structural
        # ``type_comment`` field difference below — the dump check alone
        # cannot distinguish "real code changed" from "only the type
        # comment changed", and the tokenize-based guard is required
        # regardless (research R5): it also catches ``# type:`` comments in
        # positions ``ast`` does not attach to any node.
        directive_reason = _directive_comment_delta(base_src, head_src)
        if directive_reason is not None:
            return False, directive_reason

        if _cookie_or_shebang_delta(base_src, head_src):
            return False, _REASON_ENCODING_COOKIE

        base_docstrings = _ordered_docstrings(base_tree)
        head_docstrings = _ordered_docstrings(head_tree)

        base_dump = ast.dump(_strip_docstrings(base_tree), include_attributes=False)
        head_dump = ast.dump(_strip_docstrings(head_tree), include_attributes=False)
        if base_dump != head_dump:
            return False, _REASON_CODE_DIFF

        if _doctest_content_changed(base_docstrings, head_docstrings):
            return False, _REASON_DOCTEST

        return True, _REASON_PROSE_ONLY
    except Exception:
        # Fail-closed (FR-006): any SyntaxError, ValueError, tokenizer error,
        # or unfamiliar construct resolves to False. Never raise.
        return False, _REASON_PARSE_ERROR


def _is_docstring_expr(stmt: ast.stmt) -> bool:
    """True only for a bare ``Expr(Constant(str))`` — never a ``JoinedStr``
    (f-string), never a ``BinOp``, never any other expression shape."""
    return isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str)


def _docstring_text(node: ast.AST) -> str | None:
    body = getattr(node, "body", None)
    if body and _is_docstring_expr(body[0]):
        value = body[0].value
        assert isinstance(value, ast.Constant)
        text = value.value
        assert isinstance(text, str)
        return text
    return None


def _ordered_docstrings(tree: ast.AST) -> list[str | None]:
    """Pre-order docstring text (or ``None``) for every docstring-eligible
    node, in a stable traversal order.

    Paired positionally between base/head: safe only when the caller has
    already proven the non-docstring AST structure identical (same count,
    same order, same nesting of Module/Class/Function/AsyncFunction nodes),
    which ``_evaluate`` guarantees by checking the stripped-dump equality
    first.
    """
    texts: list[str | None] = []
    for node in ast.walk(tree):
        if isinstance(node, _DOCSTRING_HOLDER_TYPES):
            texts.append(_docstring_text(node))
    return texts


class _DocstringStripper(ast.NodeTransformer):
    """Removes only a genuine docstring-position statement from ``body[0]``
    of Module/Class/Function/AsyncFunction nodes — everything else in the
    tree (including non-first bare string statements) is left untouched."""

    def _strip_body(self, node: ast.AST) -> ast.AST:
        self.generic_visit(node)
        body = getattr(node, "body", None)
        if body and _is_docstring_expr(body[0]):
            node.body = body[1:]  # type: ignore[attr-defined]
        return node

    def visit_Module(self, node: ast.Module) -> ast.AST:
        return self._strip_body(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
        return self._strip_body(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        return self._strip_body(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        return self._strip_body(node)


def _strip_docstrings(tree: ast.AST) -> ast.AST:
    stripped = _DocstringStripper().visit(tree)
    assert isinstance(stripped, ast.AST)
    return stripped


def _normalize_comment(raw_comment: str) -> str:
    return raw_comment.lstrip("#").strip().lower()


def _directive_comment_multisets(src: str) -> tuple[Counter[str], Counter[str]]:
    """Return ``(type_comments, other_directive_comments)`` multisets of
    normalized comment text, collected via a raw ``tokenize`` pass (so a
    comment is seen regardless of whether ``ast`` happens to attach it to a
    node as a PEP 484 type comment)."""
    type_comments: Counter[str] = Counter()
    other_directives: Counter[str] = Counter()
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type != tokenize.COMMENT:
            continue
        normalized = _normalize_comment(tok.string)
        if normalized.startswith(_TYPE_COMMENT_PREFIX):
            type_comments[normalized] += 1
        elif normalized.startswith(_OTHER_DIRECTIVE_PREFIXES):
            other_directives[normalized] += 1
    return type_comments, other_directives


def _directive_comment_delta(base_src: str, head_src: str) -> str | None:
    base_type, base_other = _directive_comment_multisets(base_src)
    head_type, head_other = _directive_comment_multisets(head_src)
    if base_type != head_type:
        return _REASON_TYPE_COMMENT
    if base_other != head_other:
        return _REASON_NOQA_PRAGMA
    return None


def _cookie_or_shebang_lines(src: str) -> tuple[str, str]:
    """The line-1 shebang and the line-1/2 PEP 263 encoding cookie, each as
    exact text (or ``""`` if absent)."""
    shebang = ""
    cookie = ""
    for index, line in enumerate(src.splitlines()[:2]):
        stripped = line.strip()
        if index == 0 and stripped.startswith("#!"):
            shebang = stripped
        if stripped.startswith("#") and _ENCODING_COOKIE_RE.search(stripped):
            cookie = stripped
    return shebang, cookie


def _cookie_or_shebang_delta(base_src: str, head_src: str) -> bool:
    return _cookie_or_shebang_lines(base_src) != _cookie_or_shebang_lines(head_src)


def _has_doctest_prompt(text: str | None) -> bool:
    return text is not None and _DOCTEST_PROMPT in text


def _doctest_content_changed(base_docstrings: list[str | None], head_docstrings: list[str | None]) -> bool:
    for base_text, head_text in zip(base_docstrings, head_docstrings, strict=False):
        if base_text != head_text and (_has_doctest_prompt(base_text) or _has_doctest_prompt(head_text)):
            return True
    return False
