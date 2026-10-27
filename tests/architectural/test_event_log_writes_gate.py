"""Writes gate over every event log the event-native-core ADR names (#6603).

ADR 2026-10-14-1's Confirmation, as amended by ADR 2026-10-22-1, asks for a
Python writes gate over every event log that ends with no appender left: one
module (the Java write service) persists events. This gate is that gate's
first form. It is frozen at today's writers, so a NEW writer fails, and it
drains as each log moves behind the EventBridge (#6193 hands each file over
whole). ``status.events.jsonl`` keeps its own, stricter gate
(``test_status_events_writes_gate.py``) and is not scanned here.

Three censuses, all keyed without line numbers:

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
  census resolves paths with the shared ``_write_site_scan`` resolver (the
  status gate's), with ``self.<method>()`` helpers followed as well. On the
  tree before #6606 it reports exactly the eight unlocked appends that change
  routed, plus the two Op-record appends in ``invocation/writer.py``: ten
  in all. Today it holds only writes that are not appends.
* **Unresolved writes.** A raw write whose path names no log but whose
  expression reads like one (``events``, ``jsonl``, ``ledger``, ``log``) is
  pinned in ``EXPECTED_UNRESOLVED_LOG_WRITES`` with its reason.

The door ledger is keyed by function, not by the path expression the WP
first named: one helper often appends to several logs through one parameter,
while the function is stable. A new caller in another function fails, and an
extra call in a ledgered function fails on the count. Accepted weakness: a
ledgered function redirected to a different log still passes.

Residuals the censuses cannot see: a path that arrives only as a parameter
whose call sites disagree (the door census still sees a routed form); a path
built from a glob (``m_3_3_0_op_record_schema_v2`` rewrites ``kitty-ops/*.jsonl``
found by ``glob``); a path from an imported constant with a neutral name; a
``self.<method>()`` helper whose name is defined in more than one class of the
module, or a path helper called on another receiver (``obj.path()``); a local
inside an ``async def`` (the shared resolver follows ``def`` only); a door
rebound to another name (``put = append_event_log_lines``) or captured as a
bound attribute (``fn = persistence.append_event``).

The gate's own scan of ``src/`` stays under NFR-004's 5 s
(``test_event_log_writes_gate_budget.py``, a ``timing``-only module).

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

from tests.architectural._write_site_scan import module_name_for, scan_attributed_write_sites
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
        # Last, so a named log wins: any other append-only JSON-lines file.
        "other .jsonl": (".jsonl",),
    }
)
_STATUS_LOG = "status.events.jsonl"
#: ``status.events.jsonl`` resolves to this family so a path naming it counts
#: as resolved; its writes belong to ``test_status_events_writes_gate.py``.
_STATUS_FAMILY = "status log (own gate)"
#: Words that make an unresolved write path look like an event log.
_LEDGER_WORDS: tuple[str, ...] = ("events", "jsonl", "ledger", "log")

#: Door name -> module that defines it.
DOORS: Mapping[str, str] = MappingProxyType(
    {
        "append_event_log_lines": "kernel.event_log_append",
        "event_log_lock": "kernel.event_log_append",
        "append_event": "spec_kitty_events.persistence",
    }
)
_DOOR_MODULES: frozenset[str] = frozenset(DOORS.values())
#: Calls that reach the EventBridge port's write door, which appends to
#: ``status.events.jsonl`` without the lane FSM or the Mission status lock.
_PORT_DOOR_NAMES: frozenset[str] = frozenset({"work_package_transition_port", "record_work_package_transition", "LocalFileEventBridge"})
#: The port and its local adapter define the door; they are not its callers.
_PORT_OWNERS: frozenset[str] = frozenset({"runtime.next.event_bridge", "specify_cli.events.event_bridge"})
#: The only functions that may reach the port's write door: the three
#: transition doors (the two flat ones through ``_record_work_package_transition``).
#: Debt: ``LEDGER_DEBT["port_callers"]``.
EXPECTED_PORT_CALLERS: frozenset[tuple[str, str]] = frozenset(
    {
        ("specify_cli.status.emit", "_record_work_package_transition"),
        ("specify_cli.coordination.transaction", "BookkeepingTransaction.append_events"),
    }
)
#: Modules that own a door and so never count as its caller.
_DOOR_OWNERS: frozenset[str] = frozenset({"kernel.event_log_append"})
#: Modules whose raw writes are the durability mechanism, not a writer.
_RAW_OWNERS: frozenset[str] = frozenset({"kernel.event_log_append", "specify_cli.status.store"})

_INTERIM = "interim locked append; retires at the #6193 handover"


@dataclass(frozen=True)
class LedgerDebt:
    """The price of one transient ledger family (charter standing order 5): its exit issue and owner."""

    exit_issue: str
    owner: str
    exit_when: str

    def __str__(self) -> str:
        return f"exit {self.exit_issue} ({self.exit_when}); owner: {self.owner}"


#: Every ledger below is transient debt that drains at the write-service
#: handover; #6193 owns that handover, one log at a time.
_HANDOVER_OWNER = "the #6193 write-service handover owner"
LEDGER_DEBT: Mapping[str, LedgerDebt] = MappingProxyType(
    {
        "door_callers": LedgerDebt("#6193", _HANDOVER_OWNER, "each entry goes when the write service takes its log over whole"),
        "raw_log_writers": LedgerDebt("#6193", _HANDOVER_OWNER, "each entry goes when the write service takes its log over whole"),
        "unresolved_log_writes": LedgerDebt("#6193", _HANDOVER_OWNER, "status.events.jsonl writes; they go when the write service takes that log over"),
        "port_callers": LedgerDebt("#6193", _HANDOVER_OWNER, "the port's local adapter is replaced by the write service's client (#6675 wires the port)"),
    }
)

_LOCKED = "append_event_log_lines"

#: Every caller of a door today: ``(module, function, door) -> call count``.
#: Each is an interim locked append (#6606) that retires at the #6193 handover
#: of its log; a new caller must be added here in the change that adds it.
#: Debt: ``LEDGER_DEBT["door_callers"]``.
EXPECTED_DOOR_CALLERS: Mapping[tuple[str, str, str], int] = MappingProxyType(
    {
        ("charter.activation._io", "_write_provenance", _LOCKED): 1,  # encoding provenance
        ("glossary.events", "append_event", "append_event"): 2,  # contract writer: the append, and its retry after a torn-tail repair
        ("glossary.events", "append_event", "event_log_lock"): 1,  # the contract writer runs under the interim lock
        ("glossary.events", "held_event_log", "event_log_lock"): 1,  # one interim lock across a loop of glossary emits (#6706)
        ("runtime.next._internal_runtime.engine", "_append_event", _LOCKED): 1,  # run journal
        ("specify_cli.events.decision_log", "DecisionGitLog._append_to_file", _LOCKED): 1,  # decisions.events.jsonl
        ("specify_cli.invocation.lifecycle", "append_lifecycle_record", _LOCKED): 1,  # kitty-ops/lifecycle.jsonl
        ("specify_cli.invocation.propagator", "_log_propagation_error", _LOCKED): 1,  # kitty-ops/propagation-errors.jsonl
        ("specify_cli.invocation.writer", "InvocationWriter._append_line_no_follow", _LOCKED): 1,  # Op index and closure spine
        ("specify_cli.invocation.writer", "InvocationWriter._append_validated", _LOCKED): 1,  # per-Op trails (family lock)
        ("specify_cli.invocation.writer", "InvocationWriter.write_started", "event_log_lock"): 1,  # per-Op trail create (family lock)
        ("specify_cli.mission_v1.events", "_write_event", _LOCKED): 1,  # mission-events.jsonl
        ("specify_cli.missions._archive", "append_archive_record", _LOCKED): 1,  # archived-missions.jsonl
        ("specify_cli.policy.audit", "append_audit_event", _LOCKED): 1,  # policy-audit.jsonl
    }
)

#: Every raw writer of a gated log today: ``(module, function, family) -> reason``.
#: No unlocked append is left since #6606 routed the last one through the
#: interim door; what remains is not an append. A whole-file rewrite, merge
#: driver or repair that names a gated log in its write path is ledgered here
#: with its reason. Debt: ``LEDGER_DEBT["raw_log_writers"]``.
EXPECTED_RAW_LOG_WRITERS: Mapping[tuple[str, str, str], str] = MappingProxyType(
    {
        ("glossary.events", "_repair_torn_tail", "glossary"): (
            "torn-tail repair: appends the torn fragment to the `.torn` sidecar and truncates the ledger to its last "
            "full line under its own repair lock; the append itself is the contract writer under the interim lock"
        ),
        ("specify_cli.invocation.writer", "InvocationWriter.write_started", "other .jsonl"): (
            "exclusive create (O_EXCL, mode 0600) of a new per-Op trail `kitty-ops/<op>.jsonl`; refuses an existing file, so it "
            "never appends to one. It writes under the `kitty-ops` family lock (`event_log_lock`, the trail appends' "
            "anchor), so a concurrent append never sees the file before the started row lands"
        ),
    }
)

_STATUS_GATE = "a status.events.jsonl write the status gate ledgers (test_status_events_writes_gate.py)"

#: Every raw write whose path the scanner cannot attribute to a log but whose
#: expression reads like one: ``(module, function, path expression) -> reason``.
#: Pinned so a new one is looked at; a shared appender that takes its path as a
#: parameter lands here. Debt: ``LEDGER_DEBT["unresolved_log_writes"]``.
EXPECTED_UNRESOLVED_LOG_WRITES: Mapping[tuple[str, str, str], str] = MappingProxyType(
    {
        ("specify_cli.consolidation.bookkeeping_projection", "_project_status_bookkeeping_to_target", "trusted_target_events_path"): _STATUS_GATE,
        ("specify_cli.status.mission_write", "_rollback_events_locked", "point.events_path"): _STATUS_GATE,
    }
)


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
    """``(qualified name, node)`` for each top-level function and method."""
    found: list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]] = []

    def visit(body: Iterable[ast.stmt], prefix: str) -> None:
        for node in body:
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                found.append((f"{prefix}{node.name}", node))
            elif isinstance(node, ast.ClassDef):
                visit(node.body, f"{prefix}{node.name}.")

    visit(tree.body, "")
    return found


def _call_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


class _DoorVisitor(ast.NodeVisitor):
    """One pass over a module: its door imports, and every call that may open a door, with its enclosing function."""

    def __init__(self) -> None:
        self.names: dict[str, str] = {}
        self.modules: dict[str, str] = {}
        self.scope: list[str] = []
        self.in_function = 0
        self.candidates: list[tuple[str, ast.expr]] = []
        self.port_callers: list[str] = []

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names if node.module else ():
            if DOORS.get(alias.name) == node.module:
                self.names[alias.asname or alias.name] = alias.name
            elif f"{node.module}.{alias.name}" in _DOOR_MODULES:
                self.modules[alias.asname or alias.name] = f"{node.module}.{alias.name}"

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name in _DOOR_MODULES:
                self.modules[alias.asname or alias.name] = alias.name

    def _enter(self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef, function: bool) -> None:
        self.scope.append(node.name)
        self.in_function += function
        self.generic_visit(node)
        self.in_function -= function
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._enter(node, True)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._enter(node, True)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._enter(node, False)

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        where = ".".join(self.scope) if self.in_function else "<module>"
        if isinstance(func, ast.Name) or (isinstance(func, ast.Attribute) and func.attr in DOORS):
            self.candidates.append((where, func))
        if _call_name(node) in _PORT_DOOR_NAMES:
            self.port_callers.append(where)
        self.generic_visit(node)

    def door_of(self, func: ast.expr) -> str | None:
        """The door ``func`` names, judged after the whole module (imports included) was visited."""
        if isinstance(func, ast.Name):
            return self.names.get(func.id)
        assert isinstance(func, ast.Attribute)
        owner = ast.unparse(func.value)
        if self.modules.get(owner, owner) == DOORS[func.attr]:
            return func.attr  # ``<door module or its alias>.<door>(...)``
        # The kernel door names are unique, so any ``x.<door>(...)`` counts; ``append_event`` is too common a name.
        return func.attr if func.attr != "append_event" else None


def _visit_doors(module: str, tree: ast.Module) -> tuple[list[DoorCall], set[tuple[str, str]]]:
    """``(door calls, port-door callers)`` of ``module`` from one pass."""
    visitor = _DoorVisitor()
    visitor.visit(tree)
    doors = (
        [] if module in _DOOR_OWNERS else [DoorCall(module, function, door) for function, func in visitor.candidates if (door := visitor.door_of(func)) is not None]
    )
    ports = set() if module in _PORT_OWNERS else {(module, function) for function in visitor.port_callers}
    return doors, ports


def scan_door_calls(module: str, tree: ast.Module) -> list[DoorCall]:
    """Every door call in ``module`` under any import alias, attributed to its innermost enclosing function."""
    return _visit_doors(module, tree)[0]


def scan_port_callers(module: str, tree: ast.Module) -> set[tuple[str, str]]:
    """``(module, function)`` for each call that reaches the EventBridge port's write door."""
    return _visit_doors(module, tree)[1]


def _family_of_text(text: str) -> str | None:
    if text.endswith(_STATUS_LOG):
        return _STATUS_FAMILY
    for family, tails in LOG_FAMILIES.items():
        if any(text.endswith(tail) for tail in tails):
            return family
    return None


def _is_log_shaped(expression: str) -> bool:
    lowered = expression.lower()
    return any(word in lowered for word in _LEDGER_WORDS)


def scan_write_censuses(module: str, tree: ast.Module) -> tuple[set[tuple[str, str, str]], set[tuple[str, str, str]]]:
    """``(raw writers, unresolved writes)`` of ``module`` from one pass of the shared write-site scanner.

    A raw writer is ``(module, function, family)``: a write-mode file operation
    whose path the shared resolver (``_write_site_scan``: literals, f-strings,
    locals, module constants, ``self`` attributes, same-module path helpers and
    ``self.<method>()`` helpers, parameters every call site agrees on) resolves
    to a gated log or any other ``.jsonl``. ``status.events.jsonl`` is left to
    its own gate. An unresolved write is ``(module, function, path
    expression)``: its path names no log, but the expression reads like one.
    """
    if module in _RAW_OWNERS:
        return set(), set()
    raw: set[tuple[str, str, str]] = set()
    unresolved: set[tuple[str, str, str]] = set()
    for function, site in scan_attributed_write_sites(module, tree):
        family = _family_of_text(site.path_text) if site.path_text is not None else None
        if family is None:
            if _is_log_shaped(site.path_expr):
                unresolved.add((module, function, site.path_expr))
        elif family != _STATUS_FAMILY:
            raw.add((module, function, family))
    return raw, unresolved


def scan_raw_log_writers(module: str, tree: ast.Module) -> set[tuple[str, str, str]]:
    return scan_write_censuses(module, tree)[0]


def scan_unresolved_log_writes(module: str, tree: ast.Module) -> set[tuple[str, str, str]]:
    return scan_write_censuses(module, tree)[1]


@dataclass(frozen=True)
class TreeScan:
    door_calls: tuple[DoorCall, ...]
    raw_writers: frozenset[tuple[str, str, str]]
    unresolved_writes: frozenset[tuple[str, str, str]]
    port_callers: frozenset[tuple[str, str]]


def scan_src_tree(src_source_tree: Mapping[Path, SourceFile]) -> TreeScan:
    door_calls: list[DoorCall] = []
    raw: set[tuple[str, str, str]] = set()
    unresolved: set[tuple[str, str, str]] = set()
    port_callers: set[tuple[str, str]] = set()
    for path, entry in src_source_tree.items():
        tree = entry.tree
        assert isinstance(tree, ast.Module)
        module = module_name_for(path)
        module_doors, module_ports = _visit_doors(module, tree)
        door_calls.extend(module_doors)
        port_callers |= module_ports
        module_raw, module_unresolved = scan_write_censuses(module, tree)
        raw |= module_raw
        unresolved |= module_unresolved
    return TreeScan(tuple(door_calls), frozenset(raw), frozenset(unresolved), frozenset(port_callers))


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
        f"until its log moves (#6193), a ledgered interim locked append ({_INTERIM}; {LEDGER_DEBT['door_callers']}): {over}"
    )


def test_door_ledger_is_live(tree_scan: TreeScan) -> None:
    found = Counter(call.key for call in tree_scan.door_calls)
    stale = {key: (count, found[key]) for key, count in EXPECTED_DOOR_CALLERS.items() if found[key] < count}
    assert not stale, f"Ledgered door callers that no longer exist (shrink the ledger): {stale}"


def test_no_new_raw_log_writers(tree_scan: TreeScan) -> None:
    new = sorted(tree_scan.raw_writers - EXPECTED_RAW_LOG_WRITERS.keys())
    assert not new, f"Raw writes to a gated event log; append through kernel.event_log_append ({_INTERIM}; {LEDGER_DEBT['raw_log_writers']}): {new}"


def test_raw_ledger_is_live(tree_scan: TreeScan) -> None:
    stale = sorted(EXPECTED_RAW_LOG_WRITERS.keys() - tree_scan.raw_writers)
    assert not stale, f"Ledgered raw writers that no longer exist (shrink the ledger): {stale}"


def test_no_new_unresolved_log_writes(tree_scan: TreeScan) -> None:
    new = sorted(tree_scan.unresolved_writes - EXPECTED_UNRESOLVED_LOG_WRITES.keys())
    assert not new, (
        "Raw writes whose path reads like an event log but names none the gate knows; route an event-log append through "
        f"kernel.event_log_append ({_INTERIM}), or pin the write with its reason ({LEDGER_DEBT['unresolved_log_writes']}): {new}"
    )


def test_unresolved_ledger_is_live(tree_scan: TreeScan) -> None:
    stale = sorted(EXPECTED_UNRESOLVED_LOG_WRITES.keys() - tree_scan.unresolved_writes)
    assert not stale, f"Pinned unresolved writes that no longer exist (shrink the ledger): {stale}"


def test_only_the_transition_doors_reach_the_port(tree_scan: TreeScan) -> None:
    """The port's write door appends to ``status.events.jsonl`` with no FSM and no Mission lock (pre-PR squad)."""
    assert tree_scan.port_callers == EXPECTED_PORT_CALLERS, (
        f"Only the work package transition doors may reach the EventBridge port's write door ({LEDGER_DEBT['port_callers']}) "
        f"(new: {sorted(tree_scan.port_callers - EXPECTED_PORT_CALLERS)}, gone: {sorted(EXPECTED_PORT_CALLERS - tree_scan.port_callers)})"
    )


def test_every_ledger_is_priced() -> None:
    """Every transient ledger names its exit issue, owner and exit condition (charter standing order 5)."""
    ledgers = {name.removeprefix("EXPECTED_").lower() for name in globals() if name.startswith("EXPECTED_")}
    assert ledgers == LEDGER_DEBT.keys()
    assert all(debt.exit_issue and debt.owner and debt.exit_when for debt in LEDGER_DEBT.values())


def test_a_new_port_caller_is_found() -> None:
    source = (
        "from specify_cli.events.event_bridge import LocalFileEventBridge, work_package_transition_port\n"
        "def rogue(t):\n    work_package_transition_port().record_work_package_transition(t)\n"
        "class R:\n    def m(self, t):\n        LocalFileEventBridge().record_work_package_transition(t)\n"
    )
    assert scan_port_callers("specify_cli.rogue", ast.parse(source)) == {("specify_cli.rogue", "rogue"), ("specify_cli.rogue", "R.m")}
    assert scan_port_callers("specify_cli.events.event_bridge", ast.parse(source)) == set()


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


def test_an_unresolved_log_shaped_write_is_pinned_and_others_are_not() -> None:
    source = (
        "def put(events_path, line):\n    with events_path.open('a') as f:\n        f.write(line)\n"
        "def save(out_path):\n    out_path.write_text('x')\n"
        "def run(run_dir):\n    (run_dir / 'run.events.jsonl').open('a').write('x')\n"
        "def status(d):\n    p = d / 'status.events.jsonl'\n    p.open('a').write('x')\n"
    )
    tree = ast.parse(source)
    assert scan_unresolved_log_writes("specify_cli.rogue", tree) == {("specify_cli.rogue", "put", "events_path")}
    assert scan_raw_log_writers("specify_cli.rogue", tree) == {("specify_cli.rogue", "run", "run journal")}


def test_unresolved_writes_skip_the_raw_owners() -> None:
    source = "def put(log_path):\n    log_path.open('a').write('x')\n"
    assert scan_unresolved_log_writes("kernel.event_log_append", ast.parse(source)) == set()


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


def test_a_raw_write_through_a_method_helper_and_a_helper_local_is_reported() -> None:
    """Review cycle 1: the per-Op trail resolves through ``self.invocation_path(...)``; a helper may return a local."""
    source = (
        "class W:\n"
        "    def invocation_path(self, op):\n        candidate = self._dir / f'{op}.jsonl'\n        return candidate\n"
        "    def rogue(self, op):\n        path = self.invocation_path(op)\n        with path.open('a') as f:\n            f.write('x')\n"
        "def journal(run):\n    p = run / 'run.events.jsonl'\n    return p\n"
        "def step(run):\n    journal(run).open('a').write('x')\n"
    )
    assert scan_raw_log_writers("specify_cli.rogue", ast.parse(source)) == {
        ("specify_cli.rogue", "W.rogue", "other .jsonl"),
        ("specify_cli.rogue", "step", "run journal"),
    }


def test_a_helper_returning_one_of_two_logs_is_reported() -> None:
    source = (
        "def route(d):\n    if d:\n        return d / '.encoding-provenance.jsonl'\n    return Path('.kittify/encoding-provenance/global.jsonl')\n"
        "def put(d):\n    p = route(d)\n    with p.open('a') as f:\n        f.write('x')\n"
    )
    assert scan_raw_log_writers("specify_cli.rogue", ast.parse(source)) == {("specify_cli.rogue", "put", "other .jsonl")}


def test_a_module_level_raw_write_is_reported() -> None:
    source = "open('kitty-ops/lifecycle.jsonl', 'a').write('x')\n"
    assert scan_raw_log_writers("specify_cli.rogue", ast.parse(source)) == {("specify_cli.rogue", "<module>", "Op lifecycle")}


@pytest.mark.parametrize(
    "imports",
    [
        "import spec_kitty_events.persistence as p\n",
        "from spec_kitty_events import persistence as p\n",
    ],
)
def test_the_contract_writer_is_a_door_in_attribute_form(imports: str) -> None:
    source = f"{imports}def f(row, log):\n    p.append_event(row, log)\n"
    assert [call.key for call in scan_door_calls("specify_cli.rogue", ast.parse(source))] == [("specify_cli.rogue", "f", "append_event")]


def test_the_contract_writer_is_a_door_under_its_full_dotted_name() -> None:
    source = "import spec_kitty_events.persistence\ndef f(row, log):\n    spec_kitty_events.persistence.append_event(row, log)\n"
    assert [call.key for call in scan_door_calls("specify_cli.rogue", ast.parse(source))] == [("specify_cli.rogue", "f", "append_event")]


def test_a_door_imported_after_its_use_is_still_found() -> None:
    source = "def f(p):\n    put(p, ['x'])\nfrom kernel.event_log_append import append_event_log_lines as put\n"
    assert [call.key for call in scan_door_calls("specify_cli.rogue", ast.parse(source))] == [("specify_cli.rogue", "f", _LOCKED)]


def test_an_unrelated_append_event_is_not_a_door() -> None:
    source = "from specify_cli.status import append_event\nimport specify_cli.status as st\ndef f(p):\n    append_event(p)\n    st.append_event(p)\n"
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
