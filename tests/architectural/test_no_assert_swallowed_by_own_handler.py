"""Ratchet (spec-kitty#4697): no ``assert`` inside a ``try`` that catches ``AssertionError``.

SonarCloud ``python:S5779``. When an ``assert`` sits in a ``try`` body whose
``except`` also names ``AssertionError``, the handler catches the failure of
that same assertion. When the handler continues or passes, the check can
never fail; in a test this disables the test's own guard. #6169 converted the last three live sites (in
``test_archive_root_byte_identical.py``) to ``raise ValueError(...)`` and
narrowed the caught tuples. The SonarCloud API is not reachable from every
agent session, so this local gate holds the count at zero.

Scope is the S5779 shape only: an ``assert`` anywhere in the ``try`` body
(nested ``if``/``for``/``with`` included, nested ``def``/``lambda``/``class``
excluded because they do not run there), with a handler that names
``AssertionError`` directly or in a tuple. A handler that catches only
``Exception``/``BaseException`` or is bare is out of scope. As of the gate's
introduction there are two: one in ``tests/`` records the failure in a worker
thread and re-raises it in the test thread, and one in ``src/``
(``mission_finalize.py``) wraps type-narrowing asserts. A ``try`` that catches ``AssertionError`` raised by a *called*
helper (no ``assert`` in its own body) is also allowed, for example
``_terminal_lifecycle_paths`` in the archive-root gate, which uses that as
skip control flow.

The gate is deliberately stricter than "swallowed": it also flags a handler
that re-raises, because whether an ``assert`` fails should not depend on what
its handler does (and ``python -O`` strips the ``assert`` anyway). Known blind
spots, unused today: an alias (``AE = AssertionError``), a starred or nested
tuple in the ``except`` clause, and ``self.assert*`` calls.

Fix a violation by narrowing the handler, or by raising a non-assertion
error (``ValueError``/``TypeError``) inside the ``try`` and letting the
handler re-raise it as an ``AssertionError``. No exemption file: the live
count is zero.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.architectural, pytest.mark.fast]

REPO_ROOT = Path(__file__).resolve().parents[2]
SCAN_ROOTS: tuple[Path, ...] = (REPO_ROOT / "src", REPO_ROOT / "tests")

#: Per-root floors: a detector silently scanning zero files (or losing one
#: root) must go red, not pass vacuously.
MIN_SCANNED_FILES: dict[str, int] = {"src": 1000, "tests": 3000}

_SCOPE_BARRIERS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)


def iter_python_files() -> list[Path]:
    """Every ``.py`` file under ``src/`` and ``tests/``, ``__pycache__`` excluded."""
    return sorted(path for root in SCAN_ROOTS if root.exists() for path in root.rglob("*.py") if "__pycache__" not in path.parts)


def relpath(path: Path) -> str:
    """POSIX-style repo-relative path string for violation messages."""
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def _caught_names(handler: ast.ExceptHandler) -> set[str]:
    """Final names of the exception classes ``handler`` names (``x.AssertionError`` -> ``AssertionError``)."""
    if handler.type is None:
        return set()
    nodes = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
    return {node.id if isinstance(node, ast.Name) else node.attr for node in nodes if isinstance(node, (ast.Name, ast.Attribute))}


def _asserts_in(body: list[ast.stmt]) -> list[ast.Assert]:
    """``assert`` statements that run in ``body`` itself, not in nested scopes."""
    found: list[ast.Assert] = []
    stack: list[ast.AST] = [node for node in body if not isinstance(node, _SCOPE_BARRIERS)]
    while stack:
        node = stack.pop()
        if isinstance(node, ast.Assert):
            found.append(node)
        stack.extend(child for child in ast.iter_child_nodes(node) if not isinstance(child, _SCOPE_BARRIERS))
    return found


def swallowed_assert_linenos(source: str, filename: str = "<string>") -> list[int]:
    """Line numbers of every ``assert`` caught by its own ``try``'s ``AssertionError`` handler."""
    linenos: list[int] = []
    for node in ast.walk(ast.parse(source, filename=filename)):
        if isinstance(node, (ast.Try, ast.TryStar)) and any("AssertionError" in _caught_names(h) for h in node.handlers):
            linenos.extend(assertion.lineno for assertion in _asserts_in(node.body))
    return sorted(linenos)


def collect_violations(paths: list[Path]) -> list[tuple[Path, int]]:
    """``(path, lineno)`` for every swallowed ``assert`` across ``paths``.

    A file that never spells ``AssertionError`` cannot hold the shape, so it is
    not parsed; this keeps the gate to about a second.
    """
    violations: list[tuple[Path, int]] = []
    for path in paths:
        source = path.read_text(encoding="utf-8")
        if "AssertionError" in source:
            violations.extend((path, lineno) for lineno in swallowed_assert_linenos(source, str(path)))
    return violations


@pytest.mark.parametrize("root", sorted(MIN_SCANNED_FILES))
def test_scanned_file_floor_is_met(root: str) -> None:
    scanned = [path for path in iter_python_files() if path.is_relative_to(REPO_ROOT / root)]

    assert len(scanned) > MIN_SCANNED_FILES[root], f"only {len(scanned)} files scanned under {root}/ -- the gate would pass vacuously."


def test_no_assert_swallowed_by_own_handler() -> None:
    """spec-kitty#4697: no ``assert`` under src/ or tests/ is caught by its own ``try``."""
    violations = collect_violations(iter_python_files())

    assert violations == [], (
        "`assert` inside a `try` whose `except` catches AssertionError (Sonar S5779, "
        "spec-kitty#4697): the handler catches that assertion's own failure. Narrow "
        "the handler, or raise ValueError/TypeError inside the try and re-raise it "
        "as AssertionError in the handler.\nViolations:\n" + "\n".join(f"  {relpath(p)}:{lineno}" for p, lineno in violations)
    )


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param("try:\n    assert x\nexcept AssertionError:\n    pass\n", [2], id="bare-name"),
        pytest.param("try:\n    f()\n    assert x\nexcept (KeyError, AssertionError) as e:\n    raise\n", [3], id="tuple"),
        pytest.param("try:\n    for i in y:\n        if i:\n            assert i\nexcept builtins.AssertionError:\n    pass\n", [4], id="nested-block-attribute"),
        pytest.param("try:\n    assert x\nexcept* AssertionError:\n    pass\n", [2], id="except-star"),
        pytest.param("try:\n    assert x\nexcept ValueError:\n    pass\n", [], id="other-handler"),
        pytest.param("try:\n    helper()\nexcept AssertionError:\n    pass\n", [], id="called-helper-only"),
        pytest.param("try:\n    def g():\n        assert x\nexcept AssertionError:\n    pass\n", [], id="nested-def"),
        pytest.param("try:\n    f()\nexcept AssertionError:\n    assert y\n", [], id="assert-in-handler"),
        pytest.param("try:\n    assert x\nexcept Exception:\n    pass\n", [], id="broad-out-of-scope"),
    ],
)
def test_detector_flags_planted_shapes(source: str, expected: list[int]) -> None:
    """Self-mutation: the detector flags the S5779 shape and only that shape."""
    assert swallowed_assert_linenos(source) == expected


def test_collect_violations_reads_a_planted_file(tmp_path: Path) -> None:
    """Self-mutation through the file path, so a broken text prefilter cannot hide every file."""
    planted = tmp_path / "test_planted.py"
    planted.write_text("try:\n    assert x\nexcept AssertionError:\n    pass\n", encoding="utf-8")
    clean = tmp_path / "test_clean.py"
    clean.write_text("try:\n    assert x\nexcept ValueError:\n    pass\n", encoding="utf-8")

    assert collect_violations([planted, clean]) == [(planted, 2)]
