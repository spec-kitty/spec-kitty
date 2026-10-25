"""Writes gate over every event log the event-native-core ADR names (#6603).

ADR 2026-10-14-1's Confirmation, as amended by ADR 2026-10-22-1, asks for a
Python writes gate over every event log that ends with no appender left: one
module (the Java write service) persists events. This gate is that gate's
first form. It is frozen at today's writers, so a NEW writer fails, and it
drains as each log moves behind the EventBridge (#6193 hands each file over
whole). ``status.events.jsonl`` keeps its own, stricter gate
(``test_status_events_writes_gate.py``) and is not scanned here.

Two censuses, both keyed without line numbers:

* **Door callers.** Every call of the interim locked append
  (``kernel.event_log_append.append_event_log_lines`` / ``event_log_lock``,
  #6606) or of the contract writer ``spec_kitty_events.persistence.append_event``,
  under any import alias, is ledgered in ``EXPECTED_DOOR_CALLERS`` by
  ``(module, function, door)`` with a count. Each entry retires at the #6193
  handover of its log.
* **Raw writers.** A raw write-mode file operation whose path names a gated
  log (a literal, a module constant, a ``self`` attribute, a same-module path
  helper, or a local assigned from one) is ledgered in
  ``EXPECTED_RAW_LOG_WRITERS`` with the reason it is not an append bypass. The
  ledger is empty today: on the tree before #6606 this census reports exactly
  the eight unlocked appends that change routed.

Residual: a raw write whose path arrives only as a parameter (a shared
line-appender helper called with several logs) is not attributed to a log by
the raw census; the door census still sees the routed form.

``canonical-events.jsonl`` is written through ``specify_cli.status.store``
under the status lock and the ``status/_unsafe.py`` allowlist; its raw writes
are therefore owned by the store and not ledgered here, but a new raw writer
outside the store still fails.

Both ledgers are shrink-only in spirit: a stale entry fails, so a retired
writer must leave the ledger in the change that retires it. Non-vacuity
floors feed synthetic writers to the same scanners.
"""

from __future__ import annotations

import ast
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

import pytest

from tests.architectural._write_site_scan import classify_call, module_name_for
from tests.architectural.conftest import SourceFile

pytestmark = [pytest.mark.architectural, pytest.mark.fast]

#: Gated logs: family label -> path tails a literal must end with.
LOG_FAMILIES: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "run journal": ("run.events.jsonl",),
        "decision log": ("decisions.events.jsonl",),
        "Mission v1 events": ("mission-events.jsonl",),
        "canonical events": ("canonical-events.jsonl",),
        "Op lifecycle": ("lifecycle.jsonl",),
        "propagation errors": ("propagation-errors.jsonl",),
        "Op index": ("ops-index.jsonl",),
        "Op closures": ("op-closures.jsonl",),
        "policy audit": ("policy-audit.jsonl",),
        "archive registry": ("archived-missions.jsonl",),
        "encoding provenance": ("encoding-provenance/global.jsonl", ".encoding-provenance.jsonl"),
        "glossary": (".events.jsonl",),
    }
)
_STATUS_LOG = "status.events.jsonl"

#: Door name -> module that defines it.
DOORS: Mapping[str, str] = MappingProxyType(
    {
        "append_event_log_lines": "kernel.event_log_append",
        "event_log_lock": "kernel.event_log_append",
        "append_event": "spec_kitty_events.persistence",
    }
)
#: Modules that own a door and so never count as its caller.
_DOOR_OWNERS: frozenset[str] = frozenset({"kernel.event_log_append"})
#: Modules whose raw writes are the durability mechanism, not a writer.
_RAW_OWNERS: frozenset[str] = frozenset({"kernel.event_log_append", "specify_cli.status.store"})

_INTERIM = "interim locked append; retires at the #6193 handover"

_LOCKED = "append_event_log_lines"

#: Every caller of a door today: ``(module, function, door) -> call count``.
#: Each is an interim locked append (#6606) that retires at the #6193 handover
#: of its log; a new caller must be added here in the change that adds it.
EXPECTED_DOOR_CALLERS: Mapping[tuple[str, str, str], int] = MappingProxyType(
    {
        ("charter.activation._io", "_write_provenance", _LOCKED): 1,  # encoding provenance
        ("glossary.events", "append_event", "append_event"): 2,  # contract writer: the append, and its retry after a torn-tail repair
        ("glossary.events", "append_event", "event_log_lock"): 1,  # the contract writer runs under the interim lock
        ("runtime.next._internal_runtime.engine", "_append_event", _LOCKED): 1,  # run journal
        ("specify_cli.events.decision_log", "DecisionGitLog._append_to_file", _LOCKED): 1,  # decisions.events.jsonl
        ("specify_cli.invocation.lifecycle", "append_lifecycle_record", _LOCKED): 1,  # kitty-ops/lifecycle.jsonl
        ("specify_cli.invocation.propagator", "_log_propagation_error", _LOCKED): 1,  # kitty-ops/propagation-errors.jsonl
        ("specify_cli.invocation.writer", "InvocationWriter._append_line_no_follow", _LOCKED): 1,  # Op index and closure spine
        ("specify_cli.invocation.writer", "InvocationWriter._append_validated", _LOCKED): 1,  # per-Op trails (family lock)
        ("specify_cli.mission_v1.events", "_write_event", _LOCKED): 1,  # mission-events.jsonl
        ("specify_cli.missions._archive", "append_archive_record", _LOCKED): 1,  # archived-missions.jsonl
        ("specify_cli.policy.audit", "append_audit_event", _LOCKED): 1,  # policy-audit.jsonl
    }
)

#: Every raw writer of a gated log today: ``(module, function, family) -> reason``.
#: Empty since #6606 routed the last unlocked append through the interim door;
#: a whole-file rewrite, merge driver or repair that names a gated log in its
#: write path must be ledgered here with its reason.
EXPECTED_RAW_LOG_WRITERS: Mapping[tuple[str, str, str], str] = MappingProxyType({})


# ---------------------------------------------------------------------------
# Scanners
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DoorCall:
    module: str
    function: str
    door: str

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.module, self.function, self.door)


def _functions(tree: ast.Module) -> list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
    """``(qualified name, node)`` for each top-level function, method and nested function."""
    found: list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]] = []

    def visit(body: Iterable[ast.stmt], prefix: str) -> None:
        for node in body:
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                found.append((f"{prefix}{node.name}", node))
            elif isinstance(node, ast.ClassDef):
                visit(node.body, f"{prefix}{node.name}.")

    visit(tree.body, "")
    return found


def _door_aliases(tree: ast.Module) -> dict[str, str]:
    """Local name -> door, for every ``from <owner> import <door> [as alias]``."""
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                if DOORS.get(alias.name) == node.module:
                    aliases[alias.asname or alias.name] = alias.name
    return aliases


def _call_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _door_of(node: ast.AST, aliases: Mapping[str, str]) -> str | None:
    """The door a call opens: an imported alias, or ``<module>.<door>`` attribute access."""
    if not isinstance(node, ast.Call):
        return None
    name = _call_name(node)
    if name is not None and name in aliases:
        return aliases[name]
    func = node.func
    if isinstance(func, ast.Attribute) and func.attr in DOORS and func.attr != "append_event":
        return func.attr  # e.g. ``event_log_append.append_event_log_lines(...)``
    return None


def scan_door_calls(module: str, tree: ast.Module) -> list[DoorCall]:
    """Every door call in ``module``, attributed to its innermost enclosing function (``<module>`` at top level)."""
    if module in _DOOR_OWNERS:
        return []
    aliases = _door_aliases(tree)
    owner_of: dict[int, str] = {}
    for qual, fn in _functions(tree):
        for node in ast.walk(fn):
            owner_of[id(node)] = qual  # nested functions are visited later and overwrite their own nodes
    nested: list[tuple[str, ast.AST]] = []
    for qual, fn in _functions(tree):
        nested.extend((f"{qual}.{inner.name}", inner) for inner in ast.walk(fn) if inner is not fn and isinstance(inner, ast.FunctionDef | ast.AsyncFunctionDef))
    for qual, inner in nested:
        for node in ast.walk(inner):
            owner_of[id(node)] = qual
    calls: list[DoorCall] = []
    for node in ast.walk(tree):
        door = _door_of(node, aliases)
        if door is not None:
            calls.append(DoorCall(module, owner_of.get(id(node), "<module>"), door))
    return calls


def _family_of_text(text: str) -> str | None:
    if text.endswith(_STATUS_LOG):
        return None
    for family, tails in LOG_FAMILIES.items():
        if any(text.endswith(tail) for tail in tails):
            return family
    return None


def _docstring_ids(tree: ast.Module) -> set[int]:
    found: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            first = node.body[0] if node.body else None
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                found.add(id(first.value))
    return found


def _literal_families(node: ast.AST, docstrings: set[int]) -> set[str]:
    families: set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str) and id(sub) not in docstrings:
            family = _family_of_text(sub.value)
            if family is not None:
                families.add(family)
    return families


def _module_constants(tree: ast.Module, docstrings: set[int]) -> dict[str, set[str]]:
    """Module-level names and ``self.<attr>`` attributes whose value names a gated log -> its families."""
    constants: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self":
                    families = _literal_families(node.value, docstrings)
                    if families:
                        constants.setdefault(target.attr, set()).update(families)
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) and node.value is not None else []
        value = node.value if isinstance(node, ast.Assign | ast.AnnAssign) else None
        if value is None:
            continue
        families = _literal_families(value, docstrings)
        for target in targets:
            if isinstance(target, ast.Name) and families:
                constants[target.id] = families
    return constants


def _referenced_families(fn: ast.AST, constants: Mapping[str, set[str]], docstrings: set[int]) -> set[str]:
    families = _literal_families(fn, docstrings)
    for node in ast.walk(fn):
        name = node.id if isinstance(node, ast.Name) else node.attr if isinstance(node, ast.Attribute) else None
        if name is not None and name in constants:
            families |= constants[name]
    return families


def _helper_families(
    functions: list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]], constants: Mapping[str, set[str]], docstrings: set[int]
) -> dict[str, set[str]]:
    """Short name -> gated logs a same-module path helper returns (from what its ``return`` statements name)."""
    helpers: dict[str, set[str]] = {}
    for qual, fn in functions:
        families: set[str] = set()
        for node in ast.walk(fn):
            if isinstance(node, ast.Return) and node.value is not None:
                families |= _referenced_families(node.value, constants, docstrings)
        if families:
            helpers[qual.rsplit(".", 1)[-1]] = families
    return helpers


def _last_assignment(fn: ast.AST, name: str) -> ast.expr | None:
    found: ast.expr | None = None
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            found = node.value
    return found


def _path_families(path: ast.expr, fn: ast.AST, names: Mapping[str, set[str]], docstrings: set[int], depth: int = 0) -> set[str]:
    """Gated logs a write's path expression names: literals, constants, ``self`` attributes, path helpers, locals."""
    families = _referenced_families(path, names, docstrings)
    for node in ast.walk(path):
        if isinstance(node, ast.Name) and depth < 4 and not families:
            assigned = _last_assignment(fn, node.id)
            if assigned is not None and assigned is not path:
                families |= _path_families(assigned, fn, names, docstrings, depth + 1)
        if isinstance(node, ast.Call) and (called := _call_name(node)) is not None and called in names:
            families |= names[called]
    return families


def scan_raw_log_writers(module: str, tree: ast.Module) -> set[tuple[str, str, str]]:
    """``(module, function, family)`` for each raw write-mode file operation whose path names a gated log.

    The path names a log through a literal, a module constant, a ``self``
    attribute set from one, a same-module path helper that returns one, or a
    local variable assigned from any of those. Judged per write site, so a
    function that writes one file and calls a helper naming another is not
    reported.
    """
    if module in _RAW_OWNERS:
        return set()
    docstrings = _docstring_ids(tree)
    constants = _module_constants(tree, docstrings)
    functions = _functions(tree)
    names = {**constants, **_helper_families(functions, constants, docstrings)}
    found: set[tuple[str, str, str]] = set()
    for qual, fn in functions:
        for node in ast.walk(fn):
            classified = classify_call(node) if isinstance(node, ast.Call) else None
            if classified is not None:
                found.update((module, qual, family) for family in _path_families(classified[2], fn, names, docstrings))
    return found


@dataclass(frozen=True)
class TreeScan:
    door_calls: tuple[DoorCall, ...]
    raw_writers: frozenset[tuple[str, str, str]]


def scan_src_tree(src_source_tree: Mapping[Path, SourceFile]) -> TreeScan:
    door_calls: list[DoorCall] = []
    raw: set[tuple[str, str, str]] = set()
    for path, entry in src_source_tree.items():
        tree = entry.tree
        assert isinstance(tree, ast.Module)
        module = module_name_for(path)
        door_calls.extend(scan_door_calls(module, tree))
        raw |= scan_raw_log_writers(module, tree)
    return TreeScan(tuple(door_calls), frozenset(raw))


@pytest.fixture(scope="module")
def tree_scan(src_source_tree: Mapping[Path, SourceFile]) -> TreeScan:
    return scan_src_tree(src_source_tree)


# ---------------------------------------------------------------------------
# Gate
# ---------------------------------------------------------------------------


def test_no_new_door_callers(tree_scan: TreeScan) -> None:
    found = Counter(call.key for call in tree_scan.door_calls)
    over = {key: (EXPECTED_DOOR_CALLERS.get(key, 0), count) for key, count in found.items() if count > EXPECTED_DOOR_CALLERS.get(key, 0)}
    assert not over, (
        "New event-log writers (key: (ledgered, found)). An event-log append goes through the EventBridge port or, "
        f"until its log moves (#6193), a ledgered interim locked append ({_INTERIM}): {over}"
    )


def test_door_ledger_is_live(tree_scan: TreeScan) -> None:
    found = Counter(call.key for call in tree_scan.door_calls)
    stale = {key: (count, found[key]) for key, count in EXPECTED_DOOR_CALLERS.items() if found[key] < count}
    assert not stale, f"Ledgered door callers that no longer exist (shrink the ledger): {stale}"


def test_no_new_raw_log_writers(tree_scan: TreeScan) -> None:
    new = sorted(tree_scan.raw_writers - EXPECTED_RAW_LOG_WRITERS.keys())
    assert not new, f"Raw writes to a gated event log; append through kernel.event_log_append ({_INTERIM}): {new}"


def test_raw_ledger_is_live(tree_scan: TreeScan) -> None:
    stale = sorted(EXPECTED_RAW_LOG_WRITERS.keys() - tree_scan.raw_writers)
    assert not stale, f"Ledgered raw writers that no longer exist (shrink the ledger): {stale}"


def test_the_gate_sees_todays_writers(tree_scan: TreeScan) -> None:
    """Non-vacuity on the real tree: the census must find the known door callers."""
    assert len({call.key for call in tree_scan.door_calls}) >= 10


# ---------------------------------------------------------------------------
# Non-vacuity floors (synthetic sources through the same scanners)
# ---------------------------------------------------------------------------

_RAW_FAMILY_CASES: tuple[tuple[str, str], ...] = tuple((family, tails[0]) for family, tails in LOG_FAMILIES.items())


@pytest.mark.parametrize(("family", "tail"), _RAW_FAMILY_CASES, ids=[family for family, _tail in _RAW_FAMILY_CASES])
def test_a_raw_append_to_each_log_is_reported(family: str, tail: str) -> None:
    source = f"def w(root):\n    with open(root / 'x' / 'm{tail}', 'a') as f:\n        f.write('x')\n"
    assert scan_raw_log_writers("specify_cli.rogue", ast.parse(source)) == {("specify_cli.rogue", "w", family)}


def test_a_raw_write_through_a_constant_and_a_local_is_reported() -> None:
    source = (
        "LOG = Path('kitty-ops') / 'propagation-errors.jsonl'\n"
        "def log_error(root):\n    error_log = root / LOG\n    with error_log.open('a') as f:\n        f.write('x')\n"
    )
    assert scan_raw_log_writers("specify_cli.rogue", ast.parse(source)) == {("specify_cli.rogue", "log_error", "propagation errors")}


def test_a_write_to_another_file_beside_a_log_helper_is_not_reported() -> None:
    source = "def journal(run):\n    return run / 'run.events.jsonl'\ndef step(run):\n    (run / 'state.json').write_text('x')\n    journal(run)\n"
    assert scan_raw_log_writers("specify_cli.rogue", ast.parse(source)) == set()


def test_a_raw_write_through_a_path_helper_and_a_self_attribute_is_reported() -> None:
    source = (
        "def log_path(root):\n    return root / 'kitty-ops' / 'lifecycle.jsonl'\n"
        "def append(root, line):\n    with log_path(root).open('a') as f:\n        f.write(line)\n"
        "class D:\n    def __init__(self, d):\n        self._file = d / 'decisions.events.jsonl'\n"
        "    def put(self, line):\n        with self._file.open('a') as f:\n            f.write(line)\n"
    )
    found = scan_raw_log_writers("specify_cli.rogue", ast.parse(source))
    assert {("specify_cli.rogue", "append", "Op lifecycle"), ("specify_cli.rogue", "D.put", "decision log")} <= found


def test_reads_docstrings_and_the_status_log_are_not_reported() -> None:
    source = (
        "def r(root):\n    '''Appends to run.events.jsonl.'''\n    return (root / 'run.events.jsonl').read_text()\n"
        "def s(root):\n    open(root / 'status.events.jsonl', 'a').write('x')\n"
    )
    assert scan_raw_log_writers("specify_cli.rogue", ast.parse(source)) == set()


def test_door_calls_are_found_under_any_alias() -> None:
    source = (
        "from kernel.event_log_append import append_event_log_lines as _put, event_log_lock\n"
        "from spec_kitty_events.persistence import append_event as _ledger\n"
        "import kernel.event_log_append as ela\n"
        "class C:\n    def m(self, p):\n        _put(p, ['x'])\n"
        "def f(p):\n    with event_log_lock(p):\n        _ledger({}, p)\n    ela.append_event_log_lines(p, ['y'])\n"
        "def g(p):\n    def inner():\n        _put(p, ['z'])\n    inner()\n"
    )
    keys = Counter(call.key for call in scan_door_calls("specify_cli.rogue", ast.parse(source)))
    assert keys == Counter(
        {
            ("specify_cli.rogue", "C.m", _LOCKED): 1,
            ("specify_cli.rogue", "f", "event_log_lock"): 1,
            ("specify_cli.rogue", "f", "append_event"): 1,
            ("specify_cli.rogue", "f", _LOCKED): 1,
            ("specify_cli.rogue", "g.inner", _LOCKED): 1,
        }
    )


def test_an_unrelated_append_event_is_not_a_door() -> None:
    source = "from specify_cli.status import append_event\ndef f(p):\n    append_event(p)\n"
    assert scan_door_calls("specify_cli.rogue", ast.parse(source)) == []


# ---------------------------------------------------------------------------
# The three work package transition doors call the EventBridge port (T018)
# ---------------------------------------------------------------------------

_PORT_CALLERS: tuple[tuple[str, str], ...] = (
    ("specify_cli/status/emit.py", "_record_work_package_transition"),
    ("specify_cli/coordination/transaction.py", "BookkeepingTransaction.append_events"),
)
_FLAT_DOORS: tuple[tuple[str, str], ...] = (
    ("specify_cli/status/emit.py", "_persist_prepared"),
    ("specify_cli/status/emit.py", "emit_status_transition_batch"),
)
_BYPASS_NAMES = frozenset({"append_event_stream_atomic_verified", "append_event_stream_log"})
_REPO_SRC = Path(__file__).resolve().parents[2] / "src"


def _function(relpath: str, qualname: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    tree = ast.parse((_REPO_SRC / relpath).read_text(encoding="utf-8"))
    matches = [fn for qual, fn in _functions(tree) if qual == qualname]
    assert len(matches) == 1, f"{relpath}::{qualname} not found exactly once"
    return matches[0]


def _calls(fn: ast.AST) -> set[str]:
    return {name for node in ast.walk(fn) if isinstance(node, ast.Call) and (name := _call_name(node)) is not None}


@pytest.mark.parametrize(("relpath", "qualname"), _PORT_CALLERS)
def test_transition_doors_call_the_port(relpath: str, qualname: str) -> None:
    calls = _calls(_function(relpath, qualname))
    assert "record_work_package_transition" in calls
    assert not calls & _BYPASS_NAMES, f"{qualname} bypasses the EventBridge port: {sorted(calls & _BYPASS_NAMES)}"


@pytest.mark.parametrize(("relpath", "qualname"), _FLAT_DOORS)
def test_flat_doors_hand_their_unit_to_the_port(relpath: str, qualname: str) -> None:
    calls = _calls(_function(relpath, qualname))
    assert "_record_work_package_transition" in calls
    assert not calls & _BYPASS_NAMES
