"""Regression guard: the page-inventory lockfile path STAYS PUT.

Mission B (Common Docs Structural Move, WP04 / FR-012) re-sections
``docs/development/`` per-file into the durable-vs-ephemeral structure, but the
operator directive is explicit: the page-inventory tooling artifact
``docs/development/3-2-page-inventory.yaml`` does **not** move with the pages,
and the four lockfile-tooling modules keep reading it at that exact path.

Moving the inventory re-opens the freshness-gate self-block that #2054 closed,
so this test pins the path against a future re-section silently relocating it.

The pin covers:

* the ``DEFAULT_INVENTORY_PATH`` constant in the three tooling modules that
  declare it (``inventory_lockfile``, ``check_docs_freshness``,
  ``version_leakage_check``);
* the ``_inventory`` loader's documented contract path (docstring reference);
* the file actually existing at the canonical path in the repo tree.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.docs import (
    _inventory,
    check_docs_freshness,
    inventory_lockfile,
    version_leakage_check,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]

# ``fast`` (gate-selected), not ``unit`` (authoring-only) — a unit-only marker
# leaves a new file selected by zero CI gates (orphan surface).
pytestmark = [pytest.mark.fast]

CANONICAL_INVENTORY_PATH = "docs/development/3-2-page-inventory.yaml"


@pytest.mark.parametrize(
    "default_inventory_path",
    [
        inventory_lockfile.DEFAULT_INVENTORY_PATH,
        check_docs_freshness.DEFAULT_INVENTORY_PATH,
        version_leakage_check.DEFAULT_INVENTORY_PATH,
    ],
    ids=["inventory_lockfile", "check_docs_freshness", "version_leakage_check"],
)
def test_default_inventory_path_constant_is_pinned(default_inventory_path: str) -> None:
    """Each tooling module's ``DEFAULT_INVENTORY_PATH`` stays at the canon path."""
    assert default_inventory_path == CANONICAL_INVENTORY_PATH


def test_inventory_loader_contract_path_is_pinned() -> None:
    """The ``_inventory`` loader documents the canonical inventory path."""
    assert _inventory.PageInventoryEntry.__doc__ is not None
    assert CANONICAL_INVENTORY_PATH in _inventory.PageInventoryEntry.__doc__


def test_inventory_file_exists_at_canonical_path() -> None:
    """The page-inventory artifact really sits at the pinned, stable path."""
    inventory_file = _REPO_ROOT / CANONICAL_INVENTORY_PATH
    assert inventory_file.is_file(), (
        f"page-inventory must stay put at {CANONICAL_INVENTORY_PATH}; a re-section moved it (re-opens the freshness-gate self-block, #2054)"
    )
