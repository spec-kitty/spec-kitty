"""Single home of the validate_mission_paths single-caller census (#5015).

Both ``tests/specify_cli/test_validate_mission_paths_single_caller.py`` (out of matrix) and its always-on lift
``tests/architectural/test_lifted_root_validate_mission_paths_single_caller.py`` import these tests, so the per-PR gate
runs exactly what the source suite runs and the two cannot drift apart.
"""

from __future__ import annotations

import ast
from pathlib import Path

import specify_cli

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
