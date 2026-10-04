"""Seam pins for the transition-gate family extracted from ``tasks_move_task`` (#5629).

The gate family moved VERBATIM into ``tasks_move_task_gates``. These pins keep
the extraction honest:

* every native gate symbol is still an IDENTITY re-export on
  ``tasks_move_task`` (the compat surface ``tasks.<name>`` rides on it);
* the gates module never imports ``tasks_move_task`` at module scope (the
  back-references are type-only or lazy, so there is no import cycle);
* ``tasks_move_task`` keeps no native gate definition of its own (no
  shadow copy drifting from the seam).
"""

from __future__ import annotations

import ast
import inspect

import pytest

from specify_cli.cli.commands.agent import tasks_move_task, tasks_move_task_gates

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_GATES_MODULE = tasks_move_task_gates.__name__
_MOVE_TASK_MODULE = tasks_move_task.__name__


def _native_gate_callables() -> set[str]:
    return {name for name, obj in vars(tasks_move_task_gates).items() if callable(obj) and getattr(obj, "__module__", None) == _GATES_MODULE}


def test_gate_family_is_non_empty() -> None:
    assert {"_mt_run_pre_review_gate", "_mt_run_transition_gates", "_TransitionGateEffect"} <= _native_gate_callables()


@pytest.mark.parametrize("name", sorted(_native_gate_callables()))
def test_move_task_reexports_gate_symbol_by_identity(name: str) -> None:
    assert getattr(tasks_move_task, name) is getattr(tasks_move_task_gates, name)


def test_move_task_defines_no_native_gate_symbol() -> None:
    shadows = {name for name in _native_gate_callables() if getattr(getattr(tasks_move_task, name), "__module__", None) == _MOVE_TASK_MODULE}
    assert not shadows


def test_gates_module_never_imports_move_task_at_module_scope() -> None:
    tree = ast.parse(inspect.getsource(tasks_move_task_gates))
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            assert node.module != _MOVE_TASK_MODULE, f"module-scope import of {_MOVE_TASK_MODULE} at line {node.lineno}"
