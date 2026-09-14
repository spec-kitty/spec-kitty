"""Single-production-caller invariant for ``validate_mission_paths`` (#3016, WP02, NFR-004b).

STRICTLY TEST-ONLY. The whole point of the #3016 fix is that the project path-convention override resolves
at *one* shared seam. That guarantee is only as strong as the number of production call sites: if a second
caller of ``validators.paths.validate_mission_paths`` appears in ``src/`` that does not route through
``acceptance.summary_core.evaluate_path_conventions``, the override could be silently bypassed on that path.

This guard walks the shipped ``specify_cli`` package with the AST and asserts the set of *production* call
sites is exactly ``{evaluate_path_conventions}``. It is deliberately placed OUTSIDE ``tests/architectural/``
so it does not trip that suite's shard-orphan cascade (and, before its retirement by #4315, the
golden-count cascade too) (WP02 guidance); it is a plain module-scoped guard. The assertions are
set/equality based (never ``len() == N``), so a violation names the offending caller instead of an
opaque count mismatch.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import specify_cli

pytestmark = [pytest.mark.unit, pytest.mark.non_sandbox]

_TARGET = "validate_mission_paths"
# The sole sanctioned production caller, as ``<module-rel-path>::<enclosing function>``.
_EXPECTED_CALLERS: frozenset[str] = frozenset({"acceptance/summary_core.py::evaluate_path_conventions"})


def _package_root() -> Path:
    return Path(specify_cli.__file__).resolve().parent


class _CallSiteVisitor(ast.NodeVisitor):
    """Collect ``<module>::<enclosing function>`` for every call to ``_TARGET`` in one module."""

    def __init__(self, module_rel: str) -> None:
        self._module_rel = module_rel
        self._func_stack: list[str] = []
        self.callers: set[str] = set()

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._func_stack.append(node.name)
        self.generic_visit(node)
        self._func_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        name: str | None = None
        if isinstance(func, ast.Name):
            name = func.id
        elif isinstance(func, ast.Attribute):
            name = func.attr
        if name == _TARGET:
            enclosing = self._func_stack[-1] if self._func_stack else "<module>"
            self.callers.add(f"{self._module_rel}::{enclosing}")
        self.generic_visit(node)


def _production_callers() -> set[str]:
    root = _package_root()
    callers: set[str] = set()
    for path in root.rglob("*.py"):
        module_rel = path.relative_to(root).as_posix()
        visitor = _CallSiteVisitor(module_rel)
        visitor.visit(ast.parse(path.read_text(encoding="utf-8")))
        callers.update(visitor.callers)
    return callers


def test_validate_mission_paths_has_single_production_caller() -> None:
    """NFR-004b: exactly one production call site, and it is ``evaluate_path_conventions``.

    Equality (not a count) so a regression is reported as the exact offending ``module::function`` set — a
    new caller shows up as an unexpected element, a removed seam shows up as a missing one.
    """
    assert _production_callers() == set(_EXPECTED_CALLERS)
