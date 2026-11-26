"""AST pin: consolidation reads the status log through one door (#7578, ruling Q8; vocabulary #7667).

``commit_to_target_stamps.consolidation_events`` drops the window stamps of a commit-to-target
``single_branch`` Mission. A reader that scans ``consolidation/`` for raw status reads must find
only the door itself and the readers below, each allowlisted with the reason it needs the raw log.
A new raw reader fails here until it routes through the door or is allowlisted.

Both vocabularies are derived from the source tree, not hand-listed (#7667):

* **Raw readers** (the source side) are the public functions of ``status/store.py`` and
  ``status/read_surface.py`` whose return annotation names ``StatusEvent`` or ``EventStream``,
  plus the two readers that hand back the log without typing it: ``read_status_text`` (the log
  text) and ``read_events_raw`` (the log as dicts, ``policy_metadata`` included).
* **Stamp helpers** (the sink side) are the fixpoint, over ``consolidation/`` and
  ``status/wp_window_selector.py``, of the functions that take an ``events`` / ``event`` /
  ``load_events`` parameter and reference a seed (``stamp_of``, ``window_open_of``,
  ``window_opener_events``, ``parse_wp_window``, ``LANE_HEAD_KEY``, ``WP_WINDOW_KEY``) or an
  already-derived helper. It is deliberately not the plain transitive closure of callers: that
  closure also flags ``phase_claim.py``, which reaches the stamps only through ``build_claim``
  (the claim reads through the door), and the ``done_bookkeeping`` writer path.

An allowlisted raw reader must reference no derived stamp helper (by name, attribute or import)
and spell no raw stamp key.

``materialize_snapshot`` is not a third event source: the shared reducer copies only the claim
slots (``shell_pid``, ``shell_pid_created_at``, ``agent``) out of ``policy_metadata`` into a work
package entry, never ``lane_head`` or ``wp_window``.

Out of scope (they live outside ``consolidation/`` and read stamps on purpose):

* ``review/wp_range.py`` reads ``stamp_of`` / ``window_open_of`` to build the review range; a
  review shows the work as recorded, so it wants every stamp.
* ``cli/commands/agent/tasks_move_task_executor.py`` and ``cli/commands/agent/status.py`` call
  ``approved_bound.approval_warnings``: an advisory stderr line at transition time, not a verdict.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable, Mapping
from functools import cache
from pathlib import Path

import pytest

import specify_cli

pytestmark = pytest.mark.fast

_SPECIFY_CLI = Path(specify_cli.__file__).resolve().parent
_CONSOLIDATION = _SPECIFY_CLI / "consolidation"
_SELECTOR = _SPECIFY_CLI / "status" / "wp_window_selector.py"
_READER_MODULES = (_SPECIFY_CLI / "status" / "store.py", _SPECIFY_CLI / "status" / "read_surface.py")

#: Return-type names that mark a status reader.
_EVENT_TYPES = frozenset({"StatusEvent", "EventStream"})
#: Readers whose return annotation does not name an event type but which hand back the log.
_UNTYPED_RAW_READERS = frozenset({"read_status_text", "read_events_raw"})
#: The parameter names through which a helper receives status events.
_EVENT_PARAMS = frozenset({"events", "event", "load_events"})
#: The primitives that read a window stamp off an event.
_STAMP_SEEDS = frozenset({"stamp_of", "window_open_of", "window_opener_events", "parse_wp_window", "LANE_HEAD_KEY", "WP_WINDOW_KEY"})
#: Raw stamp keys a module could spell instead of using a helper.
_STAMP_KEYS = ("lane_head", "wp_window")

#: Non-vacuity floors: a derivation that loses one of these has gone blind.
_RAW_READER_FLOOR = frozenset(
    {
        "read_events",
        "read_events_lenient",
        "read_events_from_text",
        "read_events_raw",
        "read_event_stream",
        "read_event_stream_from_text",
        "read_status_events",
        "read_status_stream",
        "read_status_text",
    }
)
_STAMP_HELPER_FLOOR = frozenset(
    {
        "attestation_stamps",
        "approval_window_open_stamp",
        "first_governed_open_stamp",
        "approval_stamp",
        "approval_stamps",
        "approval_stamp_anchors",
        "approval_windows",
        "check_lane",
        "check_lane_windows",
        "check_write_branch",
        "check_write_branch_windows",
        "classify_windows",
        "validate_approved_attestation_request",
        "window_opener_events",
    }
)

#: The door, relative to ``consolidation/``.
_DOOR = "commit_to_target_stamps.py"
#: Readers of window stamps: each must call the door, never a raw reader.
_STAMP_READERS = ("reconciliation_kernel.py", "reconciliation_closed_world.py", "approved_attestation.py", "wp_evidence.py")

#: path relative to ``consolidation/`` -> why the raw, unfiltered log is the right input.
#: None of them reads ``lane_head`` / ``wp_window``.
_RAW_ALLOWLIST: dict[str, str] = {
    "bookkeeping_projection.py": "projects the log text it is handed onto the coordination branch; bookkeeping needs every event verbatim",
    "done_bookkeeping.py": "reduces the log text it is about to commit; bookkeeping needs every event verbatim",
    "entry_preflight.py": "reduces lanes to decide whether a run may start; reads no stamp",
    "no_implementation_attestation.py": "the evidence axis reads actors and lanes, never window stamps",
    "phase_claim.py": "reduces lanes and lists lifted notices; reads no stamp",
    "preflight.py": "lenient read of implementer identities for the review preflight; reads no stamp",
}


# --------------------------------------------------------------------------- derivation


def _annotation_names(node: ast.expr | None) -> set[str]:
    """Every identifier an annotation mentions (names, attributes and string forward references)."""
    names: set[str] = set()
    for sub in ast.walk(node) if node is not None else ():
        if isinstance(sub, ast.Name):
            names.add(sub.id)
        elif isinstance(sub, ast.Attribute):
            names.add(sub.attr)
        elif isinstance(sub, ast.Constant) and isinstance(sub.value, str):
            names |= _annotation_names(ast.parse(sub.value, mode="eval").body)
    return names


def derive_raw_readers(sources: Iterable[str]) -> frozenset[str]:
    """Public top-level functions of the reader *sources* that return status events, plus the untyped readers."""
    found = {
        node.name
        for source in sources
        for node in ast.parse(source).body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and not node.name.startswith("_") and _annotation_names(node.returns) & _EVENT_TYPES
    }
    return frozenset(found | _UNTYPED_RAW_READERS)


def _referenced(node: ast.AST) -> set[str]:
    """Names, attributes and imported names inside *node*."""
    names: set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name):
            names.add(sub.id)
        elif isinstance(sub, ast.Attribute):
            names.add(sub.attr)
        elif isinstance(sub, ast.ImportFrom):
            names |= {alias.name for alias in sub.names}
    return names


def derive_stamp_helpers(sources: Iterable[str]) -> frozenset[str]:
    """The seeds plus the fixpoint of event-taking functions that reference a seed or a derived helper."""
    takes_events: dict[str, bool] = {}
    refs: dict[str, set[str]] = {}
    for source in sources:
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                args = node.args
                params = {a.arg for a in (*args.posonlyargs, *args.args, *args.kwonlyargs)}
                takes_events[node.name] = takes_events.get(node.name, False) or bool(params & _EVENT_PARAMS)
                refs.setdefault(node.name, set()).update(_referenced(node))
    derived = set(_STAMP_SEEDS)
    while new := {name for name, events in takes_events.items() if events and name not in derived and refs[name] & derived}:
        derived |= new
    return frozenset(derived)


def _consolidation_sources() -> dict[str, str]:
    """Every module of ``consolidation/``, keyed by its path relative to it (two files are ``__init__.py``)."""
    return {path.relative_to(_CONSOLIDATION).as_posix(): path.read_text(encoding="utf-8") for path in sorted(_CONSOLIDATION.rglob("*.py"))}


@cache
def _raw_readers() -> frozenset[str]:
    return derive_raw_readers(path.read_text(encoding="utf-8") for path in _READER_MODULES)


@cache
def _stamp_helpers() -> frozenset[str]:
    return derive_stamp_helpers([*_consolidation_sources().values(), _SELECTOR.read_text(encoding="utf-8")])


# --------------------------------------------------------------------------- scanners


def _raw_calls(source: str, readers: frozenset[str] | None = None) -> list[str]:
    """The raw reader names *source* calls (a bare name or an attribute)."""
    readers = _raw_readers() if readers is None else readers
    names: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
            if name in readers:
                names.append(name)
    return names


def _raw_imports(source: str, readers: frozenset[str] | None = None) -> list[str]:
    """The raw reader names *source* imports (covers aliasing and passing the function as a value)."""
    readers = _raw_readers() if readers is None else readers
    return [alias.name for node in ast.walk(ast.parse(source)) if isinstance(node, ast.ImportFrom) for alias in node.names if alias.name in readers]


def _stamp_uses(source: str, helpers: frozenset[str] | None = None) -> set[str]:
    """Derived stamp helpers *source* references, plus any raw stamp key it spells."""
    helpers = _stamp_helpers() if helpers is None else helpers
    return (_referenced(ast.parse(source)) & helpers) | {key for key in _STAMP_KEYS if key in source}


def _files_with_raw_reads(sources: Mapping[str, str]) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for rel, source in sources.items():
        uses = _raw_calls(source) + _raw_imports(source)
        if uses:
            found[rel] = uses
    return found


# --------------------------------------------------------------------------- the gate


def test_raw_event_readers_are_the_door_or_allowlisted() -> None:
    found = _files_with_raw_reads(_consolidation_sources())

    assert set(found) - {_DOOR} == set(_RAW_ALLOWLIST), "a raw status reader is neither the door nor allowlisted (or an allowlist entry is stale)"
    assert _DOOR in found, "the door no longer reads the log"


def test_stamp_readers_go_through_the_door() -> None:
    for name in _STAMP_READERS:
        source = (_CONSOLIDATION / name).read_text(encoding="utf-8")
        assert not _raw_calls(source), f"{name} reads the raw log"
        assert "consolidation_events(" in source, f"{name} does not read through consolidation_events"


@pytest.mark.parametrize("rel", sorted(_RAW_ALLOWLIST))
def test_allowlisted_modules_read_no_window_stamp(rel: str) -> None:
    source = (_CONSOLIDATION / rel).read_text(encoding="utf-8")

    assert not _stamp_uses(source), f"{rel} touches a window stamp but reads the raw log"


# --------------------------------------------------------------------------- non-vacuity


def test_derived_raw_readers_meet_the_floor() -> None:
    assert _raw_readers() >= _RAW_READER_FLOOR, f"raw readers lost: {sorted(_RAW_READER_FLOOR - _raw_readers())}"


def test_derived_stamp_helpers_meet_the_floor() -> None:
    assert _stamp_helpers() >= _STAMP_HELPER_FLOOR, f"stamp helpers lost: {sorted(_STAMP_HELPER_FLOOR - _stamp_helpers())}"


def test_derivation_is_not_the_plain_caller_closure() -> None:
    """The claim phase reaches the stamps only through ``build_claim``; it must not be derived."""
    helpers = _stamp_helpers()

    assert "build_claim" not in helpers
    assert "build_approved_wp_set" not in helpers


def test_the_stamp_scanner_sees_a_real_stamp_reader() -> None:
    """Positive control on the real tree: a module that reads stamps is seen to."""
    assert _stamp_uses((_CONSOLIDATION / "approved_bound.py").read_text(encoding="utf-8")) >= {"stamp_of", "approval_stamps"}


def test_files_are_keyed_by_relative_path() -> None:
    keys = set(_consolidation_sources())

    assert {"__init__.py", "mission_number/__init__.py"} <= keys


# --------------------------------------------------------------------------- self-mutation


def test_the_scanner_sees_a_raw_call() -> None:
    assert _raw_calls("def f(d):\n    return read_events(d)\n") == ["read_events"]
    assert _raw_calls("def f(d):\n    return store.read_events_lenient(d)\n") == ["read_events_lenient"]
    assert _raw_calls("def f(d):\n    return consolidation_events(d)\n") == []


def test_the_scanner_sees_a_raw_read_status_events_call() -> None:
    planted = "def f(repo, slug):\n    return read_status_events(resolve_status_read(repo, slug))\n"

    assert _raw_calls(planted) == ["read_status_events"]
    found = _files_with_raw_reads({**_consolidation_sources(), "planted.py": planted})
    assert "planted.py" in set(found) - {_DOOR} - set(_RAW_ALLOWLIST), "a planted raw read_status_events caller is not flagged"


def test_the_scanner_sees_an_aliased_import() -> None:
    assert _raw_imports("from specify_cli.status import read_events as load\n") == ["read_events"]
    assert _raw_imports("from specify_cli.status import read_status_text\n") == ["read_status_text"]
    assert _raw_imports("from specify_cli.status import reduce\n") == []


def test_a_planted_reader_module_function_is_derived() -> None:
    planted = "def read_events_fast(feature_dir: Path) -> list[StatusEvent]:\n    ...\n"

    assert "read_events_fast" in derive_raw_readers([planted])
    assert "_private" not in derive_raw_readers(["def _private(d) -> list[StatusEvent]:\n    ...\n"])


def test_a_planted_wrapper_of_stamp_of_is_derived() -> None:
    wrapper = "def lane_stamps(events):\n    return [stamp_of(e) for e in events]\n"
    caller = "def first_lane_stamp(events):\n    return lane_stamps(events)[0]\n"
    no_events = "def build(feature_dir):\n    return lane_stamps(load(feature_dir))\n"

    derived = derive_stamp_helpers([wrapper, caller, no_events])

    assert {"lane_stamps", "first_lane_stamp"} <= derived
    assert "build" not in derived, "a function without an events parameter is not a stamp helper"


def test_an_allowlisted_source_reading_attestation_stamps_is_flagged() -> None:
    planted = "def f(d):\n    return attestation_stamps(read_events(d))\n"

    assert _stamp_uses(planted) == {"attestation_stamps"}
    assert _stamp_uses("from specify_cli.consolidation.canceled_attestation import attestation_stamps as a\n") == {"attestation_stamps"}
    assert _stamp_uses("def f(m):\n    return m['lane_head']\n") == {"lane_head"}
    assert not _stamp_uses("def f(d):\n    return reduce(read_events(d))\n")
