"""Patch a collaborator everywhere the consolidation executor family looks it up.

Epic #2026 split ``consolidation/executor.py`` along its phase boundaries. Before
the split a test patched ``executor.<name>`` and every executor function saw the
fake, because they all looked ``<name>`` up in that one module namespace. After
the split the same lookups are spread over the phase modules. These helpers patch
``<name>`` in every family module whose namespace binds it, which is exactly the
old interception set (a module that binds a name it never looks up is unaffected
by the patch). Tests that need only one phase module patch that module directly.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from types import ModuleType
from typing import Any
from unittest import mock

import pytest

from specify_cli.consolidation import (
    coord_strand,
    entry_preflight,
    executor,
    phase_advance,
    phase_bookkeeping,
    phase_claim,
    phase_finalize,
    phase_gate,
    phase_teardown,
    resume_recovery,
    run_state,
)

EXECUTOR_FAMILY: tuple[ModuleType, ...] = (
    executor,
    run_state,
    coord_strand,
    phase_claim,
    phase_advance,
    phase_bookkeeping,
    phase_gate,
    phase_teardown,
    phase_finalize,
    entry_preflight,
    resume_recovery,
)


def family_modules_binding(name: str) -> tuple[ModuleType, ...]:
    """Every family module whose namespace binds *name*; refuses a name none of them binds."""
    modules = tuple(module for module in EXECUTOR_FAMILY if name in vars(module))
    if not modules:
        raise AttributeError(f"no consolidation executor-family module binds {name!r}")
    return modules


def setattr_executor_family(monkeypatch: pytest.MonkeyPatch, name: str, value: object) -> None:
    """``monkeypatch.setattr(executor, name, value)`` across the split executor family."""
    for module in family_modules_binding(name):
        monkeypatch.setattr(module, name, value)


@contextmanager
def patch_executor_family(name: str, new: Any = mock.DEFAULT, **kwargs: Any) -> Iterator[Any]:
    """``mock.patch("...consolidation.executor.<name>", ...)`` across the split executor family.

    The first binding module gets the real ``mock.patch.object``; every other one is
    patched with the SAME object, so call assertions see every call.
    """
    first, *rest = family_modules_binding(name)
    with ExitStack() as stack:
        patched = stack.enter_context(mock.patch.object(first, name, new, **kwargs))
        for module in rest:
            stack.enter_context(mock.patch.object(module, name, patched))
        yield patched
