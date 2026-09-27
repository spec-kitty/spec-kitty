"""Runtime package extraction import invariants."""

from __future__ import annotations

import importlib
import sys

import pytest


pytestmark = [pytest.mark.unit, pytest.mark.fast]


def test_runtime_next_is_canonical_decision_home() -> None:
    decision = importlib.import_module("runtime.next.decision")

    assert decision.Decision.__module__ == "runtime.next.decision"


def test_legacy_specify_cli_next_shim_is_gone(monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-003 (unshim wave 2): the ``specify_cli.next`` shim is deleted.

    Replaces ``test_legacy_next_package_import_warns_and_aliases_submodules``,
    which exercised the shim's aliasing behavior and was removed with the shim
    itself. This negative invariant pins the removal so the legacy import path
    cannot silently return (refactor-stable: converts the shim-behavior pin
    into an absence pin instead of deleting coverage outright).
    """
    for name in [n for n in sys.modules if n == "specify_cli.next" or n.startswith("specify_cli.next.")]:
        monkeypatch.setitem(sys.modules, name, None)
        monkeypatch.delitem(sys.modules, name)

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("specify_cli.next")
