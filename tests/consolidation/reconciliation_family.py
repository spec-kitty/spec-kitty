"""Patch a collaborator everywhere the consolidation reconciliation family looks it up.

Mission consolidation-window-provenance-01M6Y84D splits
``consolidation/reconciliation.py`` (4,096 lines) into flat
``reconciliation_<unit>.py`` modules behind a re-exporting facade. Before the
split a test patched ``reconciliation.<name>`` and every reconciliation
function saw the fake, because they all looked ``<name>`` up in that one module
namespace. After the split the same lookups are spread over the family modules.
These helpers patch ``<name>`` in every family module whose namespace binds it,
which is exactly the old interception set (a module that binds a name it never
looks up is unaffected by the patch). Tests that need only one family module
patch that module directly.

Scope notes:

- The patch-lookup guard (``test_reconciliation_family_guard.py``) covers only
  ``specify_cli.consolidation.reconciliation*`` modules. The by-name consumers
  below sit outside that scope: they are covered by this helper (a family patch
  reaches their same-object bindings), not by the guard, and a direct string
  patch on ``specify_cli.consolidation.phase_claim.<name>`` (as WP02 T007
  step 4 uses) is likewise outside the guard's scope.
- ``RECONCILIATION_FAMILY`` grows as later work packages of the mission create
  the split modules; each new module must be appended there.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from types import ModuleType
from typing import Any
from unittest import mock

import pytest

from specify_cli.consolidation import (
    forecast,
    phase_claim,
    phase_gate,
    reconciliation,
)

# Today only the facade exists; later work packages of the mission append
# reconciliation_kernel, reconciliation_bound, ... here as they create them.
RECONCILIATION_FAMILY: tuple[ModuleType, ...] = (reconciliation,)

# The ONE explicit list of modules outside the family that bind reconciliation
# names by name at import time (verified: phase_claim.py, phase_gate.py and
# forecast.py import reconciliation names directly, so a family-only patch does
# not reach their bindings). A new by-name consumer must be added here.
RECONCILIATION_CONSUMERS: tuple[ModuleType, ...] = (phase_claim, phase_gate, forecast)


def family_modules_binding(name: str) -> tuple[ModuleType, ...]:
    """Every family module whose namespace binds *name*, plus same-object consumers.

    Refuses a name no family module binds. Consumers only extend a family patch
    (a consumer binding a different object of the same name is left alone);
    they never stand in for one.
    """
    modules = [module for module in RECONCILIATION_FAMILY if name in vars(module)]
    if not modules:
        raise AttributeError(f"no consolidation reconciliation-family module binds {name!r}")
    for consumer in RECONCILIATION_CONSUMERS:
        if name in vars(consumer) and any(vars(consumer)[name] is vars(module)[name] for module in modules):
            modules.append(consumer)
    return tuple(modules)


def setattr_reconciliation_family(monkeypatch: pytest.MonkeyPatch, name: str, value: object) -> None:
    """``monkeypatch.setattr(reconciliation, name, value)`` across the split reconciliation family."""
    for module in family_modules_binding(name):
        monkeypatch.setattr(module, name, value)


@contextmanager
def patch_reconciliation_family(name: str, new: Any = mock.DEFAULT, **kwargs: Any) -> Iterator[Any]:
    """``mock.patch("...consolidation.reconciliation.<name>", ...)`` across the split family.

    The first binding module gets the real ``mock.patch.object``; every other one is
    patched with the SAME object, so call assertions see every call.
    """
    first, *rest = family_modules_binding(name)
    with ExitStack() as stack:
        patched = stack.enter_context(mock.patch.object(first, name, new, **kwargs))
        for module in rest:
            stack.enter_context(mock.patch.object(module, name, patched))
        yield patched
