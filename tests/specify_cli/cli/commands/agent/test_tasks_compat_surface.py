"""Derived re-export identity guard for the ``tasks`` compat surface (#5629, DIRECTIVE_041).

The keyset is DERIVED from the seam modules, never hand-listed: each seam's
native definitions are the callables whose ``__module__`` is the seam plus the
declared non-callable constants. A behaviour-neutral move of a function between
seams therefore needs no edit here.

The real invariant: whatever ``tasks`` re-exports from a seam must be that
seam's object by identity, not a copy. Names native to a seam but NOT exposed
on ``tasks`` are allowed -- the compat surface is "whatever ``tasks``
re-exports must be the seam's object". A deleted re-export is deliberately out
of scope here: callers that still use it fail on their own import or patch.
"""

from __future__ import annotations

from types import ModuleType

import pytest

from specify_cli.cli.commands.agent import (
    tasks,
    tasks_finalize,
    tasks_map_requirements,
    tasks_mark_status,
    tasks_move_task,
    tasks_move_task_gates,
    tasks_shared,
    tasks_status_cmd,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_SEAM_MODULES: dict[str, ModuleType] = {
    "tasks_finalize": tasks_finalize,
    "tasks_map_requirements": tasks_map_requirements,
    "tasks_shared": tasks_shared,
    "tasks_status_cmd": tasks_status_cmd,
    "tasks_move_task": tasks_move_task,
    "tasks_move_task_gates": tasks_move_task_gates,
    "tasks_mark_status": tasks_mark_status,
}

#: Non-callable natively-defined symbols the callable-based scan would miss.
_EXTRA_NON_CALLABLE_NATIVE_DEFS: dict[str, frozenset[str]] = {
    "tasks_shared": frozenset({"_RUNTIME_STATE_DENY_LIST"}),
}


def is_identity_reexport(front: ModuleType, seam: ModuleType, name: str) -> bool:
    """True when ``front.<name>`` resolves and is the very object ``seam.<name>``."""
    return hasattr(front, name) and getattr(front, name) is getattr(seam, name)


def _native_module_defs(module_name: str) -> set[str]:
    module = _SEAM_MODULES[module_name]
    callable_defs = {name for name, obj in vars(module).items() if getattr(obj, "__module__", None) == module.__name__ and callable(obj)}
    return callable_defs | set(_EXTRA_NON_CALLABLE_NATIVE_DEFS.get(module_name, frozenset()))


def _derive_compat_keys() -> dict[str, str]:
    """symbol -> seam name, for native defs that ``tasks`` exposes."""
    mapping: dict[str, str] = {}
    for module_name in _SEAM_MODULES:
        for symbol in sorted(_native_module_defs(module_name)):
            if not hasattr(tasks, symbol):
                continue
            if symbol in mapping:
                raise AssertionError(f"symbol {symbol!r} natively defined in both {mapping[symbol]!r} and {module_name!r}")
            mapping[symbol] = module_name
    return mapping


SYMBOL_TO_MODULE = _derive_compat_keys()
_PARAMS = sorted(SYMBOL_TO_MODULE.items())
_IDS = [f"{mod}.{sym}" for sym, mod in _PARAMS]


@pytest.mark.parametrize("symbol,module_name", _PARAMS, ids=_IDS)
def test_tasks_binding_is_seam_object(symbol: str, module_name: str) -> None:
    seam_module = _SEAM_MODULES[module_name]
    assert is_identity_reexport(tasks, seam_module, symbol), (
        f"tasks.{symbol} is not the same object as {module_name}.{symbol} -- the compat re-export is missing or a copy (breaks patch interception on tasks.<name>)."
    )


def test_seam_natives_are_disjoint() -> None:
    seen: dict[str, str] = {}
    for module_name in _SEAM_MODULES:
        for symbol in _native_module_defs(module_name):
            assert symbol not in seen, f"{symbol!r} natively defined in both {seen[symbol]!r} and {module_name!r}"
            seen[symbol] = module_name


@pytest.mark.parametrize("module_name", sorted(_SEAM_MODULES))
def test_every_seam_contributes_at_least_one_symbol(module_name: str) -> None:
    assert module_name in set(SYMBOL_TO_MODULE.values()), f"{module_name} contributes no symbol to the compat surface"


def test_seam_maps_agree() -> None:
    """The seam set is a contract: dropping a whole seam must fail loudly."""
    assert set(_SEAM_MODULES) == {
        "tasks_finalize",
        "tasks_map_requirements",
        "tasks_shared",
        "tasks_status_cmd",
        "tasks_move_task",
        "tasks_move_task_gates",
        "tasks_mark_status",
    }


def test_identity_predicate_detects_a_copy() -> None:
    """Negative control: a same-named copy must be reported as NOT identical."""
    original = tasks_shared._output_result
    front = ModuleType("fake_front")
    seam = ModuleType("fake_seam")
    seam._output_result = original  # type: ignore[attr-defined]
    front._output_result = original  # type: ignore[attr-defined]
    assert is_identity_reexport(front, seam, "_output_result")

    def _copy(*args: object, **kwargs: object) -> object:
        return original(*args, **kwargs)

    _copy.__name__ = original.__name__
    front._output_result = _copy  # type: ignore[attr-defined]
    assert not is_identity_reexport(front, seam, "_output_result")
    assert not is_identity_reexport(ModuleType("empty"), seam, "_output_result")


def test_shadow_copy_on_tasks_stays_in_keyset_and_fails_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    """End-to-end negative control: a shadow copy planted on the real ``tasks``
    module stays in the derived keyset and fails the identity check."""
    name, module_name = sorted(_derive_compat_keys().items())[0]
    seam = _SEAM_MODULES[module_name]
    original = getattr(seam, name)

    def shadow(*args: object, **kwargs: object) -> object:  # pragma: no cover - never called
        return original(*args, **kwargs)

    shadow.__module__ = seam.__name__
    monkeypatch.setattr(tasks, name, shadow)
    assert name in _derive_compat_keys()
    assert not is_identity_reexport(tasks, seam, name)
