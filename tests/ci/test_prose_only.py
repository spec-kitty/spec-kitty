"""Contract tests for the pure prose-only classifier (mission
``ci-prose-only-downroute-01M31T5S``, WP01).

``scripts/ci/prose_only.py`` decides whether a changed Python source differs
only in comments/docstrings from its base version. This suite pins the full
contract table from
``kitty-specs/ci-prose-only-downroute-01M31T5S/contracts/prose-only-classifier.md``:
the True/False cases, the semantically-live comment guards (``# type:`` /
``# noqa`` / ``# pragma``), the doctest guard, the encoding-cookie/shebang
guard, the fail-closed cases, and the ``reduced_paths`` aggregate helper.

Two cases are the load-bearing regressions the contract calls out explicitly:

* ``test_type_comment_no_space_is_detected`` — a bare ``ast.dump`` compare
  (no tokenize guard) sees an identical tree for a changed ``#type:``
  annotation (no space after ``#``) because default parsing discards type
  comments as ordinary comments; this proves the tokenize-based guard is
  required and normalizes the no-space spelling.
* ``test_fstring_first_statement_is_code_not_docstring`` — an f-string used
  as the first statement of a module is an ``ast.Expr(ast.JoinedStr(...))``,
  not ``ast.Expr(ast.Constant(str))``; a naive stripper that removes any
  bare ``Expr`` in docstring position (instead of checking for a literal
  string ``Constant``) would wrongly erase a real code difference.
"""

from __future__ import annotations

import pytest

from scripts.ci.prose_only import is_prose_only, prose_only_reason, reduced_paths


# ---------------------------------------------------------------------------
# True (prose-only) cases
# ---------------------------------------------------------------------------


def test_module_docstring_edit_is_prose_only() -> None:
    base = '"""Original module docstring."""\n\nx = 1\n'
    head = '"""Rewritten module docstring, still no examples."""\n\nx = 1\n'
    assert is_prose_only(base, head) is True
    assert prose_only_reason(base, head) == "prose_only"


def test_function_docstring_edit_is_prose_only() -> None:
    base = 'def f(x):\n    """Old doc."""\n    return x\n'
    head = 'def f(x):\n    """New, clearer doc."""\n    return x\n'
    assert is_prose_only(base, head) is True


def test_class_docstring_edit_is_prose_only() -> None:
    base = 'class C:\n    """Old."""\n\n    def m(self):\n        return 1\n'
    head = 'class C:\n    """New."""\n\n    def m(self):\n        return 1\n'
    assert is_prose_only(base, head) is True


def test_comment_edit_is_prose_only() -> None:
    base = "x = 1  # explain x\ny = 2\n"
    head = "x = 1  # explain x more clearly\ny = 2\n"
    assert is_prose_only(base, head) is True


def test_added_comment_line_is_prose_only() -> None:
    base = "x = 1\ny = 2\n"
    head = "# a helpful note\nx = 1\ny = 2\n"
    assert is_prose_only(base, head) is True


def test_reflowed_but_token_identical_code_is_prose_only() -> None:
    base = "x = 1+2\n"
    head = "x = 1 + 2\n"
    assert is_prose_only(base, head) is True


# ---------------------------------------------------------------------------
# False (code) cases
# ---------------------------------------------------------------------------


def test_changed_default_is_code_diff() -> None:
    base = "def f(x=1):\n    return x\n"
    head = "def f(x=2):\n    return x\n"
    assert is_prose_only(base, head) is False
    assert prose_only_reason(base, head) == "code_diff"


def test_added_branch_is_code_diff() -> None:
    base = "def f(x):\n    return x\n"
    head = "def f(x):\n    if x:\n        return x\n    return x\n"
    assert is_prose_only(base, head) is False
    assert prose_only_reason(base, head) == "code_diff"


def test_changed_non_docstring_string_literal_is_code_diff() -> None:
    base = 'def f():\n    raise ValueError("bad input")\n'
    head = 'def f():\n    raise ValueError("worse input")\n'
    assert is_prose_only(base, head) is False
    assert prose_only_reason(base, head) == "code_diff"


def test_string_used_as_value_is_never_stripped_like_a_docstring() -> None:
    # A bare string that is a value (assigned to a name), not a docstring-
    # position expression statement — never eligible for stripping.
    base = 'MESSAGE = "old text"\n'
    head = 'MESSAGE = "new text"\n'
    assert is_prose_only(base, head) is False
    assert prose_only_reason(base, head) == "code_diff"


def test_non_first_statement_string_expr_is_not_a_docstring() -> None:
    # A bare string *expression statement* that is not body[0] is never a
    # docstring, even though it looks like one syntactically.
    base = 'x = 1\n"just a stray string expression"\n'
    head = 'x = 1\n"a changed stray string expression"\n'
    assert is_prose_only(base, head) is False
    assert prose_only_reason(base, head) == "code_diff"


# ---------------------------------------------------------------------------
# False (semantically-live comments, R5)
# ---------------------------------------------------------------------------


def test_type_comment_change_is_detected() -> None:
    base = "x = []  # type: List[int]\n"
    head = "x = []  # type: List[str]\n"
    assert is_prose_only(base, head) is False
    assert prose_only_reason(base, head) == "type_comment"


def test_type_comment_no_space_is_detected() -> None:
    """Load-bearing regression: no space after ``#`` must still normalize.

    A bare ``ast.dump`` comparison (default ``ast.parse``, no ``type_comments``
    flag, no tokenize pass) sees these two sources as producing an identical
    tree, because a plain comment carries no AST node at all — it would
    wrongly report ``True``. The tokenize-based directive guard, with comment
    normalization that strips the leading ``#`` before checking the
    ``type:`` prefix, is what makes this fail-closed.
    """
    base = "x = []  #type: List[int]\n"
    head = "x = []  #type: List[str]\n"
    assert is_prose_only(base, head) is False
    assert prose_only_reason(base, head) == "type_comment"


def test_noqa_added_is_detected() -> None:
    base = "import os  # unused for now\n"
    head = "import os  # noqa: F401\n"
    assert is_prose_only(base, head) is False
    assert prose_only_reason(base, head) == "noqa_pragma"


def test_noqa_removed_is_detected() -> None:
    base = "import os  # noqa: F401\n"
    head = "import os\n"
    assert is_prose_only(base, head) is False
    assert prose_only_reason(base, head) == "noqa_pragma"


def test_pragma_change_is_detected() -> None:
    base = "if True:\n    x = 1  # pragma: no cover\n"
    head = "if True:\n    x = 1  # pragma: no branch\n"
    assert is_prose_only(base, head) is False
    assert prose_only_reason(base, head) == "noqa_pragma"


# ---------------------------------------------------------------------------
# False (doctest, R4)
# ---------------------------------------------------------------------------


def test_doctest_example_content_change_is_detected() -> None:
    base = 'def f(x):\n    """f.\n\n    >>> f(1)\n    1\n    """\n    return x\n'
    head = 'def f(x):\n    """f.\n\n    >>> f(1)\n    2\n    """\n    return x\n'
    assert is_prose_only(base, head) is False
    assert prose_only_reason(base, head) == "doctest"


def test_doctest_added_to_previously_plain_docstring_is_detected() -> None:
    base = 'def f(x):\n    """Plain description."""\n    return x\n'
    head = 'def f(x):\n    """Plain description.\n\n    >>> f(1)\n    1\n    """\n    return x\n'
    assert is_prose_only(base, head) is False
    assert prose_only_reason(base, head) == "doctest"


def test_plain_docstring_edit_elsewhere_in_file_with_untouched_doctest_is_prose_only() -> None:
    # Two functions: g's doctest is untouched, f's plain docstring changes.
    base = 'def f(x):\n    """Old plain doc."""\n    return x\n\n\ndef g(x):\n    """g.\n\n    >>> g(1)\n    1\n    """\n    return x\n'
    head = 'def f(x):\n    """New plain doc, unrelated to doctests."""\n    return x\n\n\ndef g(x):\n    """g.\n\n    >>> g(1)\n    1\n    """\n    return x\n'
    assert is_prose_only(base, head) is True


# ---------------------------------------------------------------------------
# False (encoding cookie / shebang delta)
# ---------------------------------------------------------------------------


def test_encoding_cookie_change_is_detected() -> None:
    base = "# -*- coding: utf-8 -*-\nx = 1\n"
    head = "# -*- coding: latin-1 -*-\nx = 1\n"
    assert is_prose_only(base, head) is False
    assert prose_only_reason(base, head) == "encoding_cookie"


def test_shebang_change_is_detected() -> None:
    base = "#!/usr/bin/env python3\nx = 1\n"
    head = "#!/usr/bin/env python\nx = 1\n"
    assert is_prose_only(base, head) is False
    assert prose_only_reason(base, head) == "encoding_cookie"


# ---------------------------------------------------------------------------
# False (fail-closed, FR-006)
# ---------------------------------------------------------------------------


def test_head_syntax_error_is_fail_closed() -> None:
    base = "x = 1\n"
    head = "def f(:\n"
    assert is_prose_only(base, head) is False
    assert prose_only_reason(base, head) == "parse_error"


def test_base_syntax_error_is_fail_closed() -> None:
    base = "def f(:\n"
    head = "x = 1\n"
    assert is_prose_only(base, head) is False
    assert prose_only_reason(base, head) == "parse_error"


def test_new_file_no_base_is_fail_closed() -> None:
    assert is_prose_only(None, "x = 1\n") is False
    assert prose_only_reason(None, "x = 1\n") == "no_base"


def test_empty_string_base_is_fail_closed() -> None:
    assert is_prose_only("", "x = 1\n") is False
    assert prose_only_reason("", "x = 1\n") == "no_base"


def test_never_raises_on_arbitrary_garbage() -> None:
    # Fail-closed means "never raise" — not just "never raise SyntaxError".
    assert is_prose_only("x = 1\n", "\x00\x01garbage") is False


# ---------------------------------------------------------------------------
# Load-bearing regression: f-string as body[0] is never a docstring
# ---------------------------------------------------------------------------


def test_fstring_first_statement_is_code_not_docstring() -> None:
    """An f-string in docstring position is ``Expr(JoinedStr(...))``, not
    ``Expr(Constant(str))`` — it must never be treated as a docstring, or a
    real content change inside it would be wrongly classified prose-only."""
    base = 'f"first {1}"\nx = 1\n'
    head = 'f"first {2}"\nx = 1\n'
    assert is_prose_only(base, head) is False
    assert prose_only_reason(base, head) == "code_diff"


def test_adjacent_string_literal_concat_first_statement_is_a_real_docstring() -> None:
    base = '"a" "b"\nx = 1\n'
    head = '"a" "c"\nx = 1\n'
    # Adjacent string literals are folded to a single Constant by the parser
    # itself (compile-time concatenation), so this *is* a bare Constant-str
    # body[0] and IS a real docstring position — the classifier treats it as
    # prose-only. Contrast with the runtime ``+`` BinOp case below, which is
    # never a Constant and is never eligible for stripping.
    assert is_prose_only(base, head) is True


def test_runtime_binop_concat_first_statement_is_code_not_docstring() -> None:
    base = '("a" + "b")\nx = 1\n'
    head = '("a" + "c")\nx = 1\n'
    # A real BinOp (``+``) is never a Constant, so it is never eligible for
    # docstring stripping — the change is a real code diff.
    assert is_prose_only(base, head) is False
    assert prose_only_reason(base, head) == "code_diff"


# ---------------------------------------------------------------------------
# reduced_paths aggregate
# ---------------------------------------------------------------------------


_PROSE_BASE = '"""Old."""\nx = 1\n'
_PROSE_HEAD = '"""New."""\nx = 1\n'
_CODE_BASE = "def f(x=1):\n    return x\n"
_CODE_HEAD = "def f(x=2):\n    return x\n"


def test_reduced_paths_drops_a_proven_prose_only_py_file() -> None:
    changed = ["scripts/ci/foo.py"]

    def blob_getter(path: str) -> tuple[str | None, str | None]:
        assert path == "scripts/ci/foo.py"
        return _PROSE_BASE, _PROSE_HEAD

    assert reduced_paths(changed, blob_getter) == []


def test_reduced_paths_keeps_a_code_changed_py_file() -> None:
    changed = ["scripts/ci/foo.py"]

    def blob_getter(path: str) -> tuple[str | None, str | None]:
        return _CODE_BASE, _CODE_HEAD

    assert reduced_paths(changed, blob_getter) == ["scripts/ci/foo.py"]


def test_reduced_paths_keeps_every_non_py_path_unconditionally() -> None:
    changed = ["docs/guide.md", "README.md"]

    def blob_getter(path: str) -> tuple[str | None, str | None]:
        raise AssertionError("blob_getter must not be called for non-.py paths")

    assert reduced_paths(changed, blob_getter) == changed


def test_reduced_paths_mixed_set_drops_only_the_prose_only_py() -> None:
    changed = ["scripts/ci/prose.py", "scripts/ci/code.py", "docs/guide.md"]

    def blob_getter(path: str) -> tuple[str | None, str | None]:
        if path == "scripts/ci/prose.py":
            return _PROSE_BASE, _PROSE_HEAD
        if path == "scripts/ci/code.py":
            return _CODE_BASE, _CODE_HEAD
        raise AssertionError("blob_getter must not be called for non-.py paths")

    assert reduced_paths(changed, blob_getter) == ["scripts/ci/code.py", "docs/guide.md"]


def test_reduced_paths_all_prose_only_set_reduces_to_empty() -> None:
    changed = ["scripts/ci/a.py", "scripts/ci/b.py"]

    def blob_getter(path: str) -> tuple[str | None, str | None]:
        return _PROSE_BASE, _PROSE_HEAD

    assert reduced_paths(changed, blob_getter) == []


def test_reduced_paths_docs_only_set_is_unchanged() -> None:
    changed = ["docs/a.md", "docs/b.md"]

    def blob_getter(path: str) -> tuple[str | None, str | None]:
        raise AssertionError("blob_getter must not be called for non-.py paths")

    assert reduced_paths(changed, blob_getter) == changed


def test_reduced_paths_blob_getter_failure_keeps_path_fail_closed() -> None:
    changed = ["scripts/ci/unreadable.py"]

    def blob_getter(path: str) -> tuple[str | None, str | None]:
        raise RuntimeError("git show failed")

    assert reduced_paths(changed, blob_getter) == ["scripts/ci/unreadable.py"]


@pytest.mark.parametrize("changed", [[], ()])
def test_reduced_paths_empty_input_returns_empty_list(
    changed: list[str] | tuple[str, ...],
) -> None:
    def blob_getter(path: str) -> tuple[str | None, str | None]:
        raise AssertionError("blob_getter must not be called")

    assert reduced_paths(changed, blob_getter) == []
