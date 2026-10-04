"""Seam pins for extracted ``tasks_move_task`` seams (#5629, DIRECTIVE_041).

Per seam module in ``MOVE_TASK_SEAMS``:

* every native symbol is an IDENTITY re-export on ``tasks_move_task``;
* ``tasks_move_task`` keeps no native shadow definition of it;
* the seam never imports ``tasks_move_task`` at module scope (no import cycle).
"""

from __future__ import annotations

import ast
import inspect
from types import ModuleType

import pytest

from specify_cli.cli.commands.agent import (
    tasks_move_task,
    tasks_move_task_executor,
    tasks_move_task_gates,
    tasks_move_task_hops,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

#: Every extracted ``tasks_move_task`` seam module; add new seams here.
MOVE_TASK_SEAMS: list[ModuleType] = [tasks_move_task_gates, tasks_move_task_hops, tasks_move_task_executor]

_MOVE_TASK_MODULE = tasks_move_task.__name__


def _native_callables(seam: ModuleType) -> set[str]:
    return {name for name, obj in vars(seam).items() if callable(obj) and getattr(obj, "__module__", None) == seam.__name__}


_CASES = [(seam, name) for seam in MOVE_TASK_SEAMS for name in sorted(_native_callables(seam))]
_CASE_IDS = [f"{seam.__name__.rsplit('.', 1)[-1]}.{name}" for seam, name in _CASES]


@pytest.mark.parametrize("seam", MOVE_TASK_SEAMS, ids=lambda m: m.__name__.rsplit(".", 1)[-1])
def test_seam_is_non_empty(seam: ModuleType) -> None:
    assert _native_callables(seam)


@pytest.mark.parametrize("seam,name", _CASES, ids=_CASE_IDS)
def test_move_task_reexports_seam_symbol_by_identity(seam: ModuleType, name: str) -> None:
    assert getattr(tasks_move_task, name) is getattr(seam, name)


@pytest.mark.parametrize("seam,name", _CASES, ids=_CASE_IDS)
def test_move_task_defines_no_native_shadow(seam: ModuleType, name: str) -> None:
    assert getattr(getattr(tasks_move_task, name), "__module__", None) != _MOVE_TASK_MODULE


@pytest.mark.parametrize("seam", MOVE_TASK_SEAMS, ids=lambda m: m.__name__.rsplit(".", 1)[-1])
def test_seam_never_imports_move_task_at_module_scope(seam: ModuleType) -> None:
    tree = ast.parse(inspect.getsource(seam))
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            assert node.module != _MOVE_TASK_MODULE, f"module-scope import of {_MOVE_TASK_MODULE} at line {node.lineno}"
