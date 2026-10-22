"""Shrink-only allowlist gate for the raw ``status.events.jsonl`` append doors.

Mission ``fsm-write-path-integrity-01M1TZV6`` WP03 (FR-010, SC-004; contract
``contracts/write-gates.md`` section 1 and 3). The raw append primitives in
``specify_cli.status.store`` bypass the status FSM (no validation, no lock,
no fan-out). They left the public facade for ``specify_cli.status._unsafe``,
which enumerates every module that may reach them in ``ALLOWED_CALLERS``.
This gate keeps that enumeration honest:

* ``test_unsafe_importers_are_allowlisted`` -- every ``src/`` module that
  imports a raw-append *door* is in ``ALLOWED_CALLERS``.
* ``test_allowlist_is_shrink_only`` -- ``ALLOWED_CALLERS`` is a subset of the
  ``BASELINE`` committed here. Adding a writer needs an edit to BOTH sets, in
  a PR that says why the FSM is not the right door.
* ``test_allowlist_entries_are_live`` -- every entry still imports a door
  (a stale entry is a lie about the census and fails).
* ``test_allowlist_gate_is_not_vacuous`` -- synthetic sources exercising
  every door shape fed to the SAME scanner report violations; the real tree
  yields at least one importer.

What counts as a door (analysis finding I1 -- bypass closure)
--------------------------------------------------------------
The scanner does not only look for ``status._unsafe`` importers. A module
exempt from ``test_status_module_boundary.py`` (``coordination/
transaction.py``, ``coordination/status_transition.py``) may import
``status.store`` directly and would never appear as an ``_unsafe`` importer,
so every one of these shapes counts:

1. ``from specify_cli.status._unsafe import <anything>`` / ``import
   specify_cli.status._unsafe`` / ``from specify_cli.status import _unsafe``;
2. ``from specify_cli.status.store import <append_* primitive>`` (absolute or
   relative), ``import specify_cli.status.store``, ``from specify_cli.status
   import store`` -- the store module object hands out every primitive;
3. ``from specify_cli.status import <append_* primitive>`` -- the facade
   shape this WP retired; re-promoting a primitive onto the facade makes
   the facade package itself an importer and fails here;
4. ``from specify_cli.coordination.status_service import
   append_event_stream_log`` -- the coordination wrapper that delegates to
   the primitives (the door ``BookkeepingTransaction`` actually uses).

``store.py`` and ``_unsafe.py`` are the owners, not importers. Imports under
``if TYPE_CHECKING:`` create no runtime coupling and are ignored.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

import pytest

from specify_cli.status import _unsafe
from tests.architectural.conftest import SourceFile

pytestmark = [pytest.mark.architectural, pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = _REPO_ROOT / "src"
_STORE_PATH = _SRC / "specify_cli" / "status" / "store.py"

_STATUS_PKG = "specify_cli.status"
_STORE_MODULE = "specify_cli.status.store"
_UNSAFE_MODULE = "specify_cli.status._unsafe"
_COORD_SERVICE_MODULE = "specify_cli.coordination.status_service"
_OWNER_MODULES = frozenset({_STORE_MODULE, _UNSAFE_MODULE})

#: Every ``def append_*`` at the top level of ``status/store.py``. Pinned so a
#: new primitive in the store cannot appear without being enumerated here
#: (and in ``_unsafe.__all__`` unless it is the in-store-only helper below).
STORE_APPEND_PRIMITIVES: frozenset[str] = frozenset(
    {
        "append_annotations_atomic_verified",
        "append_event_stream_atomic_verified",
        "append_events_atomic",
        "append_events_atomic_verified",
        "append_primary_checkout_events_atomic_verified",
        "append_raw_rows_atomic",
    }
)

#: ``append_events_atomic`` is the unverified batch helper. No ``src/`` module
#: outside the store calls it (tests reach it through ``status.store``
#: directly), so ``_unsafe`` does not re-export it; the scanner still counts
#: an import of it as a door.
_STORE_ONLY_PRIMITIVES: frozenset[str] = frozenset({"append_events_atomic"})

#: Coordination-layer wrappers that delegate to the primitives (door shape 4).
COORD_WRAPPER_DOORS: frozenset[str] = frozenset({"append_event_stream_log"})

#: Committed baseline for the shrink-only rule (contract section 1). Mirrors
#: ``_unsafe.ALLOWED_CALLERS`` at the WP03 landing plus the WP07 addendum; the
#: module carries the per-entry census-family justification, this set carries
#: the ratchet.
BASELINE: frozenset[str] = frozenset(
    {
        "specify_cli.status.emit",
        "specify_cli.status.lifecycle_events",
        "specify_cli.coordination.status_service",
        "specify_cli.coordination.transaction",
        "specify_cli.retrospective.events",
        "specify_cli.retrospective.lifecycle_events",
        "specify_cli.migration.verdict_provenance_backfill",
        "specify_cli.migration.backfill_runtime_state",
        # WP07 census addendum (family 8): the one deliberate growth since the
        # WP03 landing -- a writer the gate itself found, hardened the WP01 way.
        "specify_cli.decisions.emit",
    }
)


@dataclass(frozen=True)
class DoorImport:
    """One import of a raw-append door found in ``module`` at ``lineno``."""

    module: str
    lineno: int
    door: str


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------


def module_name_for(path: Path, src_root: Path = _SRC) -> str:
    """Dotted module name of a ``src/`` file (``__init__`` names the package)."""
    parts = list(path.relative_to(src_root).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _resolve_import_from(module: str, is_package: bool, node: ast.ImportFrom) -> str:
    """Absolute module an ``ImportFrom`` names, resolving relative levels."""
    if node.level == 0:
        return node.module or ""
    base = module.split(".")
    if not is_package:
        base = base[:-1]
    if node.level > 1:
        base = base[: len(base) - (node.level - 1)]
    return ".".join([*base, node.module] if node.module else base)


def _type_checking_linenos(tree: ast.AST) -> set[int]:
    """Line numbers of every node under an ``if TYPE_CHECKING:`` guard."""
    linenos: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        guarded = (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING")
        if guarded:
            linenos.update(child.lineno for child in ast.walk(node) if hasattr(child, "lineno"))
    return linenos


def _doors_from_import_from(target: str, names: Iterable[ast.alias]) -> list[str]:
    """Door labels a resolved ``from <target> import <names>`` opens."""
    if target == _UNSAFE_MODULE:
        return [f"{_UNSAFE_MODULE}:{alias.name}" for alias in names]
    if target == _STORE_MODULE:
        return [f"{_STORE_MODULE}:{alias.name}" for alias in names if alias.name in STORE_APPEND_PRIMITIVES]
    if target == _STATUS_PKG:
        return [f"{_STATUS_PKG}:{alias.name}" for alias in names if alias.name in STORE_APPEND_PRIMITIVES or alias.name in {"store", "_unsafe"}]
    if target == _COORD_SERVICE_MODULE:
        return [f"{_COORD_SERVICE_MODULE}:{alias.name}" for alias in names if alias.name in COORD_WRAPPER_DOORS]
    return []


def _doors_for_node(module: str, is_package: bool, node: ast.Import | ast.ImportFrom) -> list[str]:
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names if alias.name in _OWNER_MODULES]
    return _doors_from_import_from(_resolve_import_from(module, is_package, node), node.names)


def scan_door_imports(module: str, tree: ast.AST, *, is_package: bool = False) -> list[DoorImport]:
    """Every raw-append door import in one module's AST (all four shapes)."""
    if module in _OWNER_MODULES:
        return []
    skip = _type_checking_linenos(tree)
    found: list[DoorImport] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Import | ast.ImportFrom) or node.lineno in skip:
            continue
        found.extend(DoorImport(module, node.lineno, door) for door in _doors_for_node(module, is_package, node))
    return found


def scan_door_imports_from_source(module: str, source: str, *, is_package: bool = False) -> list[DoorImport]:
    """Source-string entry point (used by the non-vacuity floor)."""
    return scan_door_imports(module, ast.parse(source), is_package=is_package)


def scan_src_tree(src_source_tree: Mapping[Path, SourceFile]) -> list[DoorImport]:
    """Every door import across ``src/**/*.py`` (session-cached AST)."""
    found: list[DoorImport] = []
    for path, entry in src_source_tree.items():
        found.extend(scan_door_imports(module_name_for(path), entry.tree, is_package=path.name == "__init__.py"))
    return found


def _importer_modules(found: Iterable[DoorImport]) -> frozenset[str]:
    return frozenset(item.module for item in found)


# ---------------------------------------------------------------------------
# Gate
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def door_imports(src_source_tree: Mapping[Path, SourceFile]) -> list[DoorImport]:
    return scan_src_tree(src_source_tree)


def test_store_append_primitives_are_enumerated() -> None:
    """The store's ``append_*`` surface is pinned and ``_unsafe`` re-exports it."""
    tree = ast.parse(_STORE_PATH.read_text(encoding="utf-8"))
    defined = frozenset(node.name for node in tree.body if isinstance(node, ast.FunctionDef) and node.name.startswith("append_"))
    assert defined == STORE_APPEND_PRIMITIVES, (
        f"status/store.py append_* surface changed: {sorted(defined ^ STORE_APPEND_PRIMITIVES)}. "
        "Enumerate the new primitive in STORE_APPEND_PRIMITIVES and re-export it from status/_unsafe.py."
    )
    reexported = frozenset(_unsafe.__all__) - {"ALLOWED_CALLERS"}
    assert reexported == STORE_APPEND_PRIMITIVES - _STORE_ONLY_PRIMITIVES
    for name in reexported:
        assert getattr(_unsafe, name) is not None


def test_unsafe_importers_are_allowlisted(door_imports: list[DoorImport]) -> None:
    """Every module reaching a door is enumerated in ``_unsafe.ALLOWED_CALLERS``."""
    rogue = [item for item in door_imports if item.module not in _unsafe.ALLOWED_CALLERS]
    assert not rogue, (
        "Modules reach a raw status.events.jsonl append door without being in "
        "specify_cli.status._unsafe.ALLOWED_CALLERS:\n"
        + "\n".join(f"  {item.module}:{item.lineno} imports {item.door}" for item in rogue)
        + "\n\nRoute the write through the status FSM (emit_status_transition / "
        "BookkeepingTransaction). Direct status.store imports from boundary-exempt "
        "modules and the coordination.status_service wrappers count too (finding I1)."
    )


def test_allowlist_is_shrink_only() -> None:
    """``ALLOWED_CALLERS`` may only lose entries relative to the committed baseline."""
    grown = _unsafe.ALLOWED_CALLERS - BASELINE
    assert not grown, f"ALLOWED_CALLERS grew beyond the committed BASELINE: {sorted(grown)}. A new raw writer is a regression of FR-010; use the FSM."
    assert len(_unsafe.ALLOWED_CALLERS) >= 1


def test_allowlist_entries_are_live(door_imports: list[DoorImport]) -> None:
    """A listed module that no longer imports a door is a stale census entry."""
    stale = _unsafe.ALLOWED_CALLERS - _importer_modules(door_imports)
    assert not stale, f"Stale ALLOWED_CALLERS entries (no door import found): {sorted(stale)}. Remove them from _unsafe.ALLOWED_CALLERS and from BASELINE."


def test_facade_no_longer_exports_raw_appends() -> None:
    """``from specify_cli.status import append_raw_rows_atomic`` is an ImportError (FR-010)."""
    import specify_cli.status as facade

    for name in STORE_APPEND_PRIMITIVES:
        assert name not in facade.__all__, f"{name} is back on the status facade __all__"
        assert not hasattr(facade, name), f"{name} is reachable as an attribute of specify_cli.status"
    with pytest.raises(ImportError):
        from specify_cli.status import append_raw_rows_atomic  # noqa: F401


# ---------------------------------------------------------------------------
# Non-vacuity floor (contract section 3)
# ---------------------------------------------------------------------------

_SYNTHETIC_DOORS: tuple[tuple[str, str], ...] = (
    ("from specify_cli.status._unsafe import append_annotations_atomic_verified\n", f"{_UNSAFE_MODULE}:append_annotations_atomic_verified"),
    ("from specify_cli.status import _unsafe\n", f"{_STATUS_PKG}:_unsafe"),
    ("import specify_cli.status._unsafe\n", _UNSAFE_MODULE),
    ("from specify_cli.status.store import append_event_stream_atomic_verified\n", f"{_STORE_MODULE}:append_event_stream_atomic_verified"),
    ("from specify_cli.status.store import append_events_atomic\n", f"{_STORE_MODULE}:append_events_atomic"),
    ("import specify_cli.status.store\n", _STORE_MODULE),
    ("from specify_cli.status import store as _store\n", f"{_STATUS_PKG}:store"),
    ("from specify_cli.status import append_raw_rows_atomic\n", f"{_STATUS_PKG}:append_raw_rows_atomic"),
    ("from specify_cli.coordination.status_service import append_event_stream_log\n", f"{_COORD_SERVICE_MODULE}:append_event_stream_log"),
    ("def f():\n    from specify_cli.status._unsafe import append_raw_rows_atomic\n", f"{_UNSAFE_MODULE}:append_raw_rows_atomic"),
)


@pytest.mark.parametrize(("source", "door"), _SYNTHETIC_DOORS, ids=[door for _, door in _SYNTHETIC_DOORS])
def test_allowlist_gate_is_not_vacuous(source: str, door: str, door_imports: list[DoorImport]) -> None:
    """Every door shape, in a module that is not allowed, is reported by the same scanner."""
    found = scan_door_imports_from_source("specify_cli.synthetic.rogue_writer", source)
    assert [item.door for item in found] == [door], f"scanner missed door shape {door!r}: {found}"
    assert found[0].module not in _unsafe.ALLOWED_CALLERS
    assert len(door_imports) >= 1, "the scanner found no door importer on the real tree -- the gate is vacuous"


def test_allowlist_gate_relative_imports_inside_status_count() -> None:
    """The in-package shapes the flat shell and lifecycle appender use are doors too."""
    emit_shape = scan_door_imports_from_source("specify_cli.status.emit", "from . import store as _store\n")
    assert [item.door for item in emit_shape] == [f"{_STATUS_PKG}:store"]
    lifecycle_shape = scan_door_imports_from_source("specify_cli.status.lifecycle_events", "from .store import append_raw_rows_atomic\n")
    assert [item.door for item in lifecycle_shape] == [f"{_STORE_MODULE}:append_raw_rows_atomic"]
    facade_reads = scan_door_imports_from_source(_STATUS_PKG, "from .store import EVENTS_FILENAME, read_events\n", is_package=True)
    assert facade_reads == []


def test_allowlist_gate_ignores_benign_and_type_checking_imports() -> None:
    """Facade reads and ``TYPE_CHECKING``-guarded imports are not doors."""
    benign = "from specify_cli.status import read_events, feature_status_lock\nfrom specify_cli.status.store import EVENTS_FILENAME\n"
    assert scan_door_imports_from_source("specify_cli.synthetic.reader", benign) == []
    guarded = "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from specify_cli.status._unsafe import append_raw_rows_atomic\n"
    assert scan_door_imports_from_source("specify_cli.synthetic.typed", guarded) == []
    assert scan_door_imports_from_source(_STORE_MODULE, "from specify_cli.status._unsafe import append_raw_rows_atomic\n") == []
