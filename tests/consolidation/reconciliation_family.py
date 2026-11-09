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
- :func:`patch_callee_name` is the ONE AST helper both the surface-pin scanner
  (``test_reconciliation_surface_pin.py``) and the patch-lookup guard
  (``test_reconciliation_family_guard.py``) use to recognize a patch call
  (review cycle 1: it was duplicated verbatim between the two files and had
  drifted — the guard and the scanner disagreed on ``patch.object``).
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from types import ModuleType
from typing import Any
from unittest import mock

import pytest

from specify_cli.consolidation import (
    claim_inputs,
    forecast,
    phase_claim,
    phase_gate,
    reconciliation,
    reconciliation_authorship,
    reconciliation_bound,
    reconciliation_canceled,
    reconciliation_claim,
    reconciliation_claim_types,
    reconciliation_closed_world,
    reconciliation_kernel,
    reconciliation_rendering,
    reconciliation_verifier,
)

# The facade first, then the nine split modules in the order the work packages created them
# (kernel, claim types, rendering, closed world, bound, verifier, canceled, claim, authorship);
# the split is complete, so a module added later is appended here.
RECONCILIATION_FAMILY: tuple[ModuleType, ...] = (
    reconciliation,
    reconciliation_kernel,
    reconciliation_claim_types,
    reconciliation_rendering,
    reconciliation_closed_world,
    reconciliation_bound,
    reconciliation_verifier,
    reconciliation_canceled,
    reconciliation_claim,
    reconciliation_authorship,
)

# The ONE explicit list of modules outside the family that bind reconciliation
# names by name at import time (verified: phase_claim.py, phase_gate.py and
# forecast.py import reconciliation names directly, so a family-only patch does
# not reach their bindings). A new by-name consumer must be added here.
#
# Deliberately NOT listed (review cycle 1): approved_attestation.py (binds
# _APPROVED_MEMBERSHIP_LANES, _bound_approved_wp_ids, _bound_lanes,
# _closed_world_anchors, _is_bookkeeping, _lane_branch_for, _planning_prefix
# and approval_stamp_anchors through a relative import), resolve.py (binds
# write_post_fix_marker) and run_state.py (binds ApprovedWpCommitSet and
# VerifyResult). They do bind reconciliation names by name, but no name any
# test in the corpus patches is bound by them today, so listing them would
# widen every family patch to modules no patch needs to reach. WP08/WP09
# retargets: when a patched name becomes bound by one of these modules, add
# that module here.
RECONCILIATION_CONSUMERS: tuple[ModuleType, ...] = (phase_claim, phase_gate, forecast, claim_inputs)


def _is_patch_receiver(value: ast.expr) -> bool:
    """``patch`` or anything ending in ``.patch`` (``mock.patch``, ``unittest.mock.patch``)."""
    if isinstance(value, ast.Name):
        return value.id == "patch"
    return isinstance(value, ast.Attribute) and value.attr == "patch"


def patch_callee_name(func: ast.expr) -> str | None:
    """The patch-ish callee name: ``setattr``, ``patch`` or ``patch.object``.

    Covers every spelling the corpus uses: ``monkeypatch.setattr(...)``,
    ``mock.patch(...)`` / ``mock.patch.object(...)``, ``unittest.mock.patch(...)``
    / ``unittest.mock.patch.object(...)``, and the ``from unittest.mock import
    patch`` spellings ``patch(...)`` and ``patch.object(...)`` (review cycle 1:
    the bare-``patch`` ``patch.object`` form was missed).
    """
    if isinstance(func, ast.Attribute):
        if func.attr == "object" and _is_patch_receiver(func.value):
            return "patch.object"
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return None


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
