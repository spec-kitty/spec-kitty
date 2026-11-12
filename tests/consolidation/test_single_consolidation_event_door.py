"""AST pin: consolidation reads the status log through one door (#7578, ruling Q8).

``commit_to_target_stamps.consolidation_events`` drops the window stamps of a commit-to-target
``single_branch`` Mission. A reader that scans ``consolidation/`` for raw ``read_events*`` calls
must find only the door itself and the readers below, each allowlisted with the reason it needs
the raw log. A new raw reader fails here until it routes through the door or is allowlisted.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import specify_cli

pytestmark = pytest.mark.fast

_CONSOLIDATION = Path(specify_cli.__file__).resolve().parent / "consolidation"
_RAW_READERS = frozenset({"read_events", "read_events_lenient", "read_events_from_text"})
_DOOR = "commit_to_target_stamps.py"
#: Readers of window stamps: each must call the door, never a raw reader.
_STAMP_READERS = ("reconciliation_kernel.py", "reconciliation_closed_world.py", "approved_attestation.py")

#: file -> why the raw, unfiltered log is the right input. None of them reads ``lane_head`` / ``wp_window``.
_RAW_ALLOWLIST: dict[str, str] = {
    "bookkeeping_projection.py": "projects the log text it is handed onto the coordination branch; bookkeeping needs every event verbatim",
    "done_bookkeeping.py": "reduces the log text it is about to commit; bookkeeping needs every event verbatim",
    "entry_preflight.py": "reduces lanes to decide whether a run may start; reads no stamp",
    "no_implementation_attestation.py": "the evidence axis reads actors and lanes, never window stamps",
    "phase_claim.py": "reduces lanes and lists lifted notices; reads no stamp",
    "preflight.py": "lenient read of implementer identities for the review preflight; reads no stamp",
    "wp_evidence.py": "the evidence axis reads actors and lanes, never window stamps",
}


def _raw_calls(source: str) -> list[str]:
    """The ``read_events*`` names *source* calls (a bare name or an attribute)."""
    names: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
            if name in _RAW_READERS:
                names.append(name)
    return names


def _raw_imports(source: str) -> list[str]:
    """The ``read_events*`` names *source* imports (covers aliasing and passing the function as a value)."""
    return [alias.name for node in ast.walk(ast.parse(source)) if isinstance(node, ast.ImportFrom) for alias in node.names if alias.name in _RAW_READERS]


def _files_with_raw_calls() -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for path in sorted(_CONSOLIDATION.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        uses = _raw_calls(source) + _raw_imports(source)
        if uses:
            found[path.name] = uses
    return found


def test_raw_event_readers_are_the_door_or_allowlisted() -> None:
    found = _files_with_raw_calls()

    assert set(found) - {_DOOR} == set(_RAW_ALLOWLIST), "a raw read_events* caller is neither the door nor allowlisted (or an allowlist entry is stale)"
    assert _DOOR in found, "the door no longer reads the log"


def test_stamp_readers_go_through_the_door() -> None:
    for name in _STAMP_READERS:
        source = (_CONSOLIDATION / name).read_text(encoding="utf-8")
        assert not _raw_calls(source), f"{name} reads the raw log"
        assert "consolidation_events(" in source, f"{name} does not read through consolidation_events"


def test_the_scanner_sees_a_raw_call() -> None:
    assert _raw_calls("def f(d):\n    return read_events(d)\n") == ["read_events"]
    assert _raw_calls("def f(d):\n    return store.read_events_lenient(d)\n") == ["read_events_lenient"]
    assert _raw_calls("def f(d):\n    return consolidation_events(d)\n") == []


def test_the_scanner_sees_an_aliased_import() -> None:
    assert _raw_imports("from specify_cli.status import read_events as load\n") == ["read_events"]
    assert _raw_imports("from specify_cli.status import reduce\n") == []


_STAMP_TOKENS = ("LANE_HEAD_KEY", "WP_WINDOW_KEY", "stamp_of", "window_open_of", "lane_head", "wp_window")


@pytest.mark.parametrize("name", sorted(_RAW_ALLOWLIST))
def test_allowlisted_modules_read_no_window_stamp(name: str) -> None:
    source = (_CONSOLIDATION / name).read_text(encoding="utf-8")

    assert not [token for token in _STAMP_TOKENS if token in source], f"{name} touches a window stamp but reads the raw log"
