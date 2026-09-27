"""Shared AST detector for the loop-aware resolution gate (#3189, WP04/T016).

Not a test module (mirrors the existing underscore-prefixed non-test helpers
already in this directory -- ``_no_follow_symlinks_apply_scan.py``,
``_os_detection_scan.py``): pytest never collects it, so it carries no
``pytestmark``.

**Scope, stated honestly (FR-005).** This gate blocks *hand-rolled*
``RuntimeError``/``ELOOP`` translation around path resolution -- the exact
pattern ``src/specify_cli/skills/command_installer.py`` used before WP02/WP03
migrated it onto ``kernel.resolution.resolve_rejecting_loops``. It does
**not** detect the wider resolve-then-contain shape (``try: p.resolve()
except OSError`` followed by a separate ``relative_to`` containment check
with no ``RuntimeError``/``ELOOP`` handling at all) -- the post-tasks review
counted about 88 such functions. That wider class is a follow-up, out of
scope for this gate; do not describe this module as closing it.

**What is banned.** Any ``try`` block whose body (walked without descending
into a nested ``def``/``lambda``/``class`` -- a resolve call inside a locally
defined helper is that helper's own concern, not this ``try``'s) calls
``resolve`` or ``realpath`` (as a bare-name call or an attribute call, e.g.
``path.resolve()`` or ``os.path.realpath(...)``), where at least one of its
``except`` handlers either:

* names ``RuntimeError`` in its exception type (a bare ``except
  RuntimeError:`` or a ``RuntimeError`` inside a tuple of caught types), or
* references the name ``ELOOP`` anywhere in the handler body (a bare
  ``ELOOP`` name or an ``errno.ELOOP`` attribute access).

This is exactly the shape CPython 3.11/3.12's non-strict ``Path.resolve()``
produces on a symlink loop (a ``RuntimeError`` wrapping the ``OSError(ELOOP,
...)``) and that 3.13+ silently stops producing -- so a hand-rolled catch of
either shape has an interpreter-dependent verdict unless it routes through
``resolve_rejecting_loops`` instead.

**What is NOT banned (over-fire boundary).** ``try: os.open(path,
os.O_NOFOLLOW) except OSError as e: if e.errno == errno.ELOOP: ...`` --
this is the *O_NOFOLLOW* sense of ``ELOOP`` (a single-component symlink
refusal on ``open``, nothing to do with ``resolve``/``realpath``), and the
try body never calls ``resolve``/``realpath``, so the detector never fires
on it. See ``test_o_nofollow_negative_does_not_fire`` in the paired test
module for the concrete self-mutation proof.

**Excluded module.** ``src/kernel/resolution.py`` -- the primitive itself
(``resolve_rejecting_loops``) legitimately contains exactly this
``try/except RuntimeError`` shape (that IS the fix), so it is excluded from
``SCAN_ROOTS`` outright rather than needing a per-line allowlist entry, the
same way the no-follow-symlinks-apply gate excludes ``kernel/no_follow.py``
by scan-root rather than by exemption.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"

#: The loop-aware resolution primitive (WP01). Its own body is the sanctioned
#: door this gate exists to force everything else through, so it is excluded
#: by scan root rather than by allowlist entry.
_PRIMITIVE_MODULE = SRC_ROOT / "kernel" / "resolution.py"

#: NOTE (mirrors the no-follow-symlinks-apply gate's NOTE-3): a detector
#: silently scanning zero files must go red, not pass vacuously. 1318 ``.py``
#: files live under ``src/`` at T016 landing time (observed via
#: ``find src -name '*.py' -not -path '*__pycache__*' | wc -l``); the floor
#: stays comfortably below that so ordinary file churn does not flake the
#: gate, while still catching a scan-root typo or an accidentally-emptied
#: ``SRC_ROOT``.
MIN_SCANNED_FILES = 1000

_RESOLUTION_ATTRS = frozenset({"resolve", "realpath"})
_LOOP_CALL_NAME = "resolve_rejecting_loops"

#: Statement/expression node types a body walk must NOT descend past: a
#: resolve call inside a nested helper is that helper's own try-block
#: concern, not the enclosing try's.
_NESTED_SCOPE_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)


@dataclass(frozen=True)
class Violation:
    """One offending ``try`` block, keyed by content rather than line number.

    ``key`` is ``(relpath, enclosing_function, ordinal)`` -- T017's required
    allowlist key shape, stable across line-number-shifting edits elsewhere
    in the file. ``lineno`` is carried only for human-readable failure
    messages, never for identity or lookup.
    """

    relpath: str
    enclosing_function: str
    ordinal: int
    lineno: int

    @property
    def key(self) -> tuple[str, str, int]:
        return (self.relpath, self.enclosing_function, self.ordinal)


def iter_python_files() -> list[Path]:
    """Every ``.py`` file under ``src/``, ``__pycache__`` and the primitive module excluded."""
    files: list[Path] = []
    for path in SRC_ROOT.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        if path.resolve() == _PRIMITIVE_MODULE:
            continue
        files.append(path)
    return sorted(files)


def relpath(path: Path) -> str:
    """POSIX-style repo-relative path string -- the allowlist key's path component."""
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def _walk_body_no_nested_scopes(stmts: list[ast.stmt]) -> Iterator[ast.AST]:
    """Every node reachable from ``stmts`` without descending into a nested scope.

    A statement that IS itself a nested scope (``def``/``async def``/
    ``lambda``/``class``) is excluded outright, top-level or not -- it is
    filtered both when seeding the stack from ``stmts`` and when expanding a
    node's children, so a resolve() call written inside a locally-defined
    helper is never attributed to the enclosing try (a helper's whole
    subtree is opaque, not just its immediate children).
    """
    stack: list[ast.AST] = [stmt for stmt in stmts if not isinstance(stmt, _NESTED_SCOPE_TYPES)]
    while stack:
        node = stack.pop()
        yield node
        for child in ast.iter_child_nodes(node):
            if isinstance(child, _NESTED_SCOPE_TYPES):
                continue
            stack.append(child)


def _is_resolution_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr in _RESOLUTION_ATTRS
    if isinstance(func, ast.Name):
        return func.id in _RESOLUTION_ATTRS
    return False


def _try_body_calls_resolution(node: ast.Try) -> bool:
    return any(_is_resolution_call(child) for child in _walk_body_no_nested_scopes(node.body))


def _handler_type_names_runtime_error(handler: ast.ExceptHandler) -> bool:
    exc_type = handler.type
    if exc_type is None:
        return False
    if isinstance(exc_type, ast.Name):
        return exc_type.id == "RuntimeError"
    if isinstance(exc_type, ast.Tuple):
        return any(isinstance(elt, ast.Name) and elt.id == "RuntimeError" for elt in exc_type.elts)
    return False


def _handler_body_references_eloop(handler: ast.ExceptHandler) -> bool:
    for node in _walk_body_no_nested_scopes(handler.body):
        if isinstance(node, ast.Attribute) and node.attr == "ELOOP":
            return True
        if isinstance(node, ast.Name) and node.id == "ELOOP":
            return True
    return False


def _handlers_match(node: ast.Try) -> bool:
    return any(_handler_type_names_runtime_error(handler) or _handler_body_references_eloop(handler) for handler in node.handlers)


def _is_offending_try(node: ast.Try) -> bool:
    return _try_body_calls_resolution(node) and _handlers_match(node)


def find_violations(tree: ast.AST, relative_path: str) -> list[Violation]:
    """Every offending ``try`` in ``tree``, keyed by ``(path, enclosing function, ordinal)``.

    Ordinal counts occurrences within the SAME enclosing function in source
    order (first offending ``try`` in a function is ordinal 1, the second is
    ordinal 2, and so on) -- this is what makes multiple offenders in one
    function (e.g. the four in ``m_0_10_8_fix_memory_structure.py``)
    distinguishable without relying on line numbers.
    """
    violations: list[Violation] = []
    ordinal_by_function: dict[str, int] = {}

    def visit(node: ast.AST, enclosing_function: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                visit(child, child.name)
                continue
            if isinstance(child, ast.Try):
                if _is_offending_try(child):
                    ordinal_by_function[enclosing_function] = ordinal_by_function.get(enclosing_function, 0) + 1
                    violations.append(
                        Violation(
                            relpath=relative_path,
                            enclosing_function=enclosing_function,
                            ordinal=ordinal_by_function[enclosing_function],
                            lineno=child.lineno,
                        )
                    )
                visit(child, enclosing_function)
                continue
            visit(child, enclosing_function)

    visit(tree, "<module>")
    return violations


def count_resolution_call_sites(tree: ast.AST) -> int:
    """Every ``resolve``/``realpath`` call anywhere in ``tree`` (name match, not semantic).

    Deliberately over-broad: matching on the bare attribute/function name
    also counts non-path ``.resolve()`` calls (e.g. a future/promise
    resolver, ``ProtectionPolicy.resolve``) -- there is no static way to
    exclude those without a type checker, and the floor below already
    accounts for the resulting slack (90%, not 100%).
    """
    return sum(1 for node in ast.walk(tree) if _is_resolution_call(node))


def count_resolve_rejecting_loops_call_sites(tree: ast.AST) -> int:
    """Every ``resolve_rejecting_loops(...)`` call site anywhere in ``tree``."""
    count = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (isinstance(func, ast.Name) and func.id == _LOOP_CALL_NAME) or (isinstance(func, ast.Attribute) and func.attr == _LOOP_CALL_NAME):
            count += 1
    return count
