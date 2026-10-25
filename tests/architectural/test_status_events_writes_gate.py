"""AST writes-gate for ``status.events.jsonl`` (FR-011, R14).

Mission ``fsm-write-path-integrity-01M1TZV6`` WP03 (contract
``contracts/write-gates.md`` sections 2 and 3). ``status/store.py`` is the
only module that may write the mission event log. This gate scans every
``src/**/*.py`` for write-mode file operations whose path resolves
statically to a ``status.events.jsonl`` file and fails when one lives
anywhere else:

* ``open(p, "a" | "w" | ...)``, ``p.open("ab")``, ``p.write_text(...)``,
  ``p.write_bytes(...)``;
* ``os.open(p, O_WRONLY | O_APPEND | O_TRUNC | ...)``;
* ``os.replace(tmp, p)`` / ``os.rename(tmp, p)`` / ``shutil.move(tmp, p)``
  -- the atomic-rename landing step IS the durable write, so a destination
  that is the event log counts.

The out-of-store sites that legitimately exist are ledgered in
``ALLOWED_OUT_OF_STORE_WRITE_SITES`` with a per-key site COUNT, so a second
write of an already-ledgered shape in the same module is reported (WP07).

Path resolution is static and best-effort. Resolved shapes: string
constants; f-strings; ``Path(...) / "status.events.jsonl"``; ``feature_dir /
EVENTS_FILENAME`` (the store constant under any import alias, or a module
constant holding the literal); names assigned in the same function or at
module level; ``self.<attr>`` assigned anywhere in the module; calls to
same-module functions whose every ``return`` resolves; and function
PARAMETERS, resolved through every same-module call site of that function
(all callers must agree). A write whose path the scanner still cannot
resolve is NOT a pass (contract section 2): every unresolved write whose
path expression is event-named (``events_path``, ``self._events_path``,
...) is pinned in ``EXPECTED_UNRESOLVED_EVENT_NAMED_WRITE_SITES``, and the
dynamic event-log writers that rule cannot name are pinned in
``KNOWN_DYNAMIC_EVENT_LOG_WRITE_SITES`` (each must still be live).

Positive census (section 2): the scanner must find the store's own writes;
a scan that matches zero writers anywhere is itself a failure.

Lock-composition census (R14): every module with a ``feature_status_lock(``
call site is pinned in ``EXPECTED_LOCK_COMPOSITION_SITES``. A new
lock-plus-append composition anywhere else is a new writer shell and fails
with a pointer to ``contracts/emit-pipeline.md`` section 2.

Non-vacuity floor (section 3): synthetic sources for every write shape and
every path-resolution rule are fed to the SAME scanner and must each
report exactly one event-log write.
"""

from __future__ import annotations

import ast
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

import pytest

from tests.architectural._write_site_scan import (
    STORE_MODULE,
    classify_call,
    WriteSite,
    module_name_for,
    scan_write_sites,
    scan_write_sites_from_source,
)
from tests.architectural.conftest import SourceFile

pytestmark = [pytest.mark.architectural, pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = _REPO_ROOT / "src"


#: Resolved event-log writes outside ``store.py`` that exist today, each with
#: the number of sites the ledger covers. Keyed on (module, kind, path
#: expression) -- line numbers move, expressions do not -- and COUNTED, so a
#: second write of the same shape in an allowed module is a new site the
#: gate reports, not a free ride on the ledger (WP03 review finding, closed
#: in WP07). Shrink-only (``test_allowed_out_of_store_sites_are_live`` drops
#: stale or under-counted entries): each entry says why the site is not an
#: FSM append bypass.
ALLOWED_OUT_OF_STORE_WRITE_SITES: Mapping[tuple[str, str, str], int] = MappingProxyType(
    {
        # (The two rollback truncates of ``coordination.transaction`` and
        # ``coordination.status_transition`` left this ledger in
        # concurrent-mission-writers WP01 (#5819): both roll back through the
        # Mission write primitive, ``status.mission_write``, below.)
        # Checkout materializations (not appends): write bytes git already
        # holds for the log into a worktree so materialize() can read them
        # (sparse-checkout hydration from the index). mission-writer-followups
        # WP08 (#5883) changed this create-if-missing from ``write_text`` to an
        # exclusive ``open(events_path, "x")`` so a concurrent writer's log is
        # never clobbered (the mission-write-discipline gate's non-clobber rule);
        # the key's kind is now ``open``.
        ("specify_cli.lanes.auto_rebase", "open", "events_path"): 1,
        # Legacy whole-log rebuild migration (writer census family 9, WP07):
        # rewrites a reconciled log atomically (tmp + ``os.replace``) with
        # the read -> reconcile -> rewrite under ONE acquisition of the
        # mission status lock keyed on the mission directory name, so a
        # concurrent locked append waits and lands after the rewrite. Not an
        # append, so not a store primitive; the rename shape stays here.
        ("specify_cli.migration.rebuild_state", "os.replace", "str(events_file)"): 1,
        # ``specify_cli.decisions.emit`` (family 8) left this ledger in WP07:
        # its raw ``open("a")`` became ``append_raw_rows_atomic`` under L1
        # behind ``status/_unsafe`` (see ``test_status_unsafe_allowlist.py``).
    }
)

#: Unresolved write sites whose path expression is event-named. Pinned so a
#: new dynamic event-log write cannot slip in as "unresolved" (contract
#: section 2). Each is explained; a change here is a change to the write
#: surface and must be reviewed, not absorbed.
EXPECTED_UNRESOLVED_EVENT_NAMED_WRITE_SITES: frozenset[tuple[str, str, str]] = frozenset(
    {
        # Merge-time union projection: writes source-union-original bytes of
        # the log onto the trusted target checkout. The path comes from a
        # trust helper called with several filenames, so callers disagree.
        ("specify_cli.consolidation.bookkeeping_projection", "write_bytes", "trusted_target_events_path"),
        # The Mission write primitive's verified rollback (#5819): opens the log
        # ``r+b`` once, measures and truncates that same descriptor, never
        # extends it. The only truncating site in ``src/specify_cli`` (the Mission
        # write discipline gate pins that). The path is a ``RollbackPoint`` field.
        ("specify_cli.status.mission_write", "Path.open", "point.events_path"),
    }
)

#: Dynamic event-log writers the event-name rule cannot see (parameter
#: paths named ``path`` / ``target``). Each must still be found unresolved
#: on the tree; a resolved or vanished entry fails the live check.
KNOWN_DYNAMIC_EVENT_LOG_WRITE_SITES: frozenset[tuple[str, str, str]] = frozenset(
    {
        # Lifecycle-envelope migration: whole-file atomic replace over a
        # parameter path (mission log or project canonical log).
        ("specify_cli.status.migrate_lifecycle_envelope", "os.replace", "path"),
        # Three-way event-log merge driver output (``output_path or ours``).
        ("specify_cli.status.event_log_merge", "Path.open", "target"),
        # #2804 gate-artifact restore after a squash merge (the log is one of
        # the preserved gate artifacts).
        ("specify_cli.consolidation.phase_advance", "write_bytes", "path"),
    }
)

#: Modules with a ``feature_status_lock(`` call site (R14 census). Built
#: from the tree at the WP03 landing; each line says what the shell is.
EXPECTED_LOCK_COMPOSITION_SITES: frozenset[str] = frozenset(
    {
        # concurrent-mission-writers WP01 (#5819): the Mission write primitive
        # (``mission_write_lock``) is the one door non-status writers take.
        "specify_cli.status.mission_write",
        # mission-writer-followups WP02 (#5883): every ``meta.json`` read-modify-write
        # (``locked_update_meta``, the setters, the CAS ``restore_meta_text``) takes the
        # Mission write lock; it appends no event-log row.
        "specify_cli.mission_metadata",
        # mission-writer-followups WP03 (#5883): the remaining ``meta.json`` read-modify-writes
        # (documentation state, the migrations and the upgrade helper) hold the Mission write
        # lock around a whole-file replace; none appends an event-log row.
        "specify_cli.doc_analysis.doc_state",
        "specify_cli.migration.backfill_identity",
        "specify_cli.migration.mission_state",
        "specify_cli.migration.runtime_state_cutover",
        "specify_cli.upgrade.feature_meta",
        # mission-writer-followups WP04 (#5883): the work-package frontmatter, finalize and matrix
        # writers hold the Mission write lock around their read-modify-write
        # (``locked_update_frontmatter``, the finalize flush and write-scope restore,
        # map-requirements, the issue-matrix scaffold, ``validate-tasks`` repair and the 2.0.6
        # sweep); none appends an event-log row.
        "specify_cli.frontmatter",
        "specify_cli.cli.commands.agent.tasks_map_requirements",
        "specify_cli.cli.commands.agent.mission_finalize_bootstrap",
        "specify_cli.cli.commands.agent.mission_finalize_commit",
        "specify_cli.tasks.issue_matrix",
        "specify_cli.task_metadata_validation",
        # mission-loader: the custom-mission meta.json writer holds the Mission write lock; it appends no event-log row.
        "specify_cli.mission_loader.command",
        "specify_cli.upgrade.migrations.m_2_0_6_consistency_sweep",
        # concurrent-mission-writers WP03 (#5468, #5796): ``implement`` holds the
        # Mission write lock from the claim emit through the claim commit, and
        # ``ensure_vcs_locked`` runs its meta.json read-modify-write under it.
        "specify_cli.cli.commands.implement_phases",
        "specify_cli.lanes.implement_support",
        # concurrent-mission-writers WP04 (#5467): tracer-append holds the
        # Mission write lock across read -> merge -> write -> commit.
        "specify_cli.retrospective.tracer_writer",
        # Family 1 flat shell + batch door + emit_inner_state_changed.
        "specify_cli.status.emit",
        # Family 2 lifecycle appender (_lifecycle_write_lock).
        "specify_cli.status.lifecycle_events",
        # Family 3 BookkeepingTransaction (lock held for the txn lifetime).
        "specify_cli.coordination.transaction",
        # Coord fallback: L1 (``mission_write_lock``) covers snapshot, emit,
        # commit and rollback.
        "specify_cli.coordination.status_transition",
        # Family 5 retro_status_lock helper (family 4 composes through it).
        "specify_cli.retrospective.lifecycle_events",
        # Family 6 verdict-provenance backfill (one-shot migration).
        "specify_cli.migration.verdict_provenance_backfill",
        # Family 7 runtime-state backfill (one-shot migration).
        "specify_cli.migration.backfill_runtime_state",
        # Family 8 decision-point rows (WP07 census addendum): one L1 take
        # around ``append_raw_rows_atomic`` + the Lamport readback.
        "specify_cli.decisions.emit",
        # Family 9 legacy whole-log rebuild (WP07 census addendum): one L1
        # take around the read -> reconcile -> ``os.replace`` rewrite.
        "specify_cli.migration.rebuild_state",
        # Work-package lifecycle helpers (WP01 lock-key audit section 4).
        "specify_cli.status.work_package_lifecycle",
        # Lifecycle-envelope migration lock (already key-compliant).
        "specify_cli.status.migrate_lifecycle_envelope",
        # Verdict-save-queue scopes: bounded L1 takes (lock rule a).
        "specify_cli.review.cycle",
        # CLI command shells that hold L1 around a status commit.
        "specify_cli.cli.commands.agent.status",
        "specify_cli.cli.commands.agent.workflow_executor",
        "specify_cli.cli.commands.agent.tasks_mark_status",
        "specify_cli.cli.commands.agent.tasks_move_task_executor",
        # accept-fails-closed-01M3HS4V (#4887): the #4858 locked re-read +
        # single-row splice + write-and-commit critical section moved OUT of
        # ``acceptance_verdict`` into the ONE shared seam, ``acceptance.
        # matrix.locked_reread_splice_and_write`` -- every acceptance-matrix
        # writer (the verdict command AND the accept gate's pre-stamp guard)
        # now composes through it instead of each holding L1 privately.
        "specify_cli.acceptance.matrix",
        # #4884: issue-verdict holds L1 around the same locked re-read +
        # single-row splice + write-and-commit critical section, mirroring
        # #4858 for the issue-matrix twin of the lost-update race.
        "specify_cli.cli.commands.agent.issue_verdict",
        # coord-artifact-single-home-01M3V4BE WP07 (WP03 regression; ruling
        # recorded at traces/design-decisions.md entry
        # design-decisions-71f124fc4627): the single write-location
        # accessor's one-time
        # coordination seed (``coord_seed._seed_coord_surface``) composes
        # ``feature_status_lock`` around a byte-level CARRY of events the
        # root checkout already persisted onto the coordination branch
        # (contracts/seed.md) -- it is not a transition emitter and never
        # calls ``prepare_transition``/``validate_transition``. Routing it
        # through either of the two emit-pipeline shells above would
        # re-validate and re-stamp (new event_id/Lamport) every carried row,
        # which breaks the event-id identity the seed's own fork/prefix
        # check depends on (the merged root and coordination streams must
        # agree on event_id, not merely on content). The lock composition
        # here guards the SAME critical section (merge, write, commit) the
        # two shells guard for a live transition; it is a third, narrower
        # family (one-time administrative replay), not a third transition
        # emitter.
        "specify_cli.coordination.coord_seed",
        # #5641 landing fold: ``finalize-tasks``' status-surface guard holds L1
        # across its status-write window (``StatusSurfaceGuard.recording``) so
        # no other process's status write for the Mission lands inside the
        # range the failure restore would move the branch back over. It
        # appends nothing itself: the writers inside the window re-enter the
        # lock; this is a holder, not a fourth emit shell.
        "specify_cli.cli.commands.agent.finalize_status_surface",
        # mission-writer-followups WP08 (#5883): the consolidation bookkeeping
        # projection's coord->target status-log read-modify-write now runs under
        # the Mission write lock (``mission_write_lock``), fixing the unlocked
        # RMW. It composes the lock but is not a store append shell: the merged
        # bytes are written through the projection's own whole-file replace
        # (already pinned in EXPECTED_UNRESOLVED_EVENT_NAMED_WRITE_SITES), not an
        # event-log append primitive.
        "specify_cli.consolidation.bookkeeping_projection",
        # mission-writer-followups WP15 (#5883): the Mission-creation birth write
        # (``_write_create_meta``) holds the Mission write lock
        # (``mission_write_lock(feature_dir, fallback_to_dir_name=True)`` because
        # ``meta.json`` does not exist yet) around the initial meta + documentation
        # -state write; it appends no event-log row.
        "specify_cli.core.mission_creation_meta",
    }
)


@dataclass(frozen=True)
class TreeScan:
    events_writes: tuple[WriteSite, ...]
    unresolved_writes: tuple[WriteSite, ...]
    lock_composition_modules: frozenset[str]


#: Call names that compose the Mission status lock (``mission_write_lock`` is a thin
#: delegate of ``feature_status_lock``; both count as a lock composition site).
LOCK_COMPOSITION_CALLS: frozenset[str] = frozenset({"feature_status_lock", "mission_write_lock"})


def has_lock_call_site(tree: ast.AST) -> bool:
    """True when ``tree`` calls ``feature_status_lock(`` or ``mission_write_lock(``, bare or as an attribute."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
        if name in LOCK_COMPOSITION_CALLS:
            return True
    return False


def scan_src_tree(src_source_tree: Mapping[Path, SourceFile]) -> TreeScan:
    events_writes: list[WriteSite] = []
    unresolved: list[WriteSite] = []
    lock_modules: set[str] = set()
    for path, entry in src_source_tree.items():
        module = module_name_for(path)
        tree = entry.tree
        assert isinstance(tree, ast.Module)
        sites = scan_write_sites(module, tree)
        events_writes.extend(site for site in sites if site.targets_events_log)
        unresolved.extend(site for site in sites if site.path_text is None)
        if module != "specify_cli.status.locking" and has_lock_call_site(tree):
            lock_modules.add(module)
    return TreeScan(tuple(events_writes), tuple(unresolved), frozenset(lock_modules))


def out_of_store_site_counts(events_writes: Iterable[WriteSite]) -> Counter[tuple[str, str, str]]:
    """How many event-log write sites each (module, kind, path_expr) key carries outside the store."""
    return Counter(site.key for site in events_writes if site.module != STORE_MODULE)


def out_of_store_violations(events_writes: Iterable[WriteSite]) -> list[WriteSite]:
    """Every out-of-store site whose key is absent from the ledger or carries more sites than it allows.

    An over-counted key reports ALL of its sites (the ledger is line-number
    independent, so no single site is "the extra one"); the failure message
    carries the allowed/found counts.
    """
    sites = list(events_writes)
    found = out_of_store_site_counts(sites)
    over = {key for key, count in found.items() if count > ALLOWED_OUT_OF_STORE_WRITE_SITES.get(key, 0)}
    return [site for site in sites if site.key in over]


def ledger_shortfall(events_writes: Iterable[WriteSite]) -> dict[tuple[str, str, str], tuple[int, int]]:
    """Ledger keys with fewer live sites than allowed: ``{key: (allowed, found)}`` (stale or under-counted)."""
    found = out_of_store_site_counts(events_writes)
    return {key: (allowed, found[key]) for key, allowed in ALLOWED_OUT_OF_STORE_WRITE_SITES.items() if found[key] < allowed}


# ---------------------------------------------------------------------------
# Gate
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def tree_scan(src_source_tree: Mapping[Path, SourceFile]) -> TreeScan:
    return scan_src_tree(src_source_tree)


def test_no_out_of_store_writes(tree_scan: TreeScan) -> None:
    """Every resolved write of a status.events.jsonl path lives in store.py (or the ledger)."""
    violations = out_of_store_violations(tree_scan.events_writes)
    found = out_of_store_site_counts(tree_scan.events_writes)
    assert not violations, (
        "status.events.jsonl is written outside specify_cli.status.store:\n"
        + "\n".join(
            f"  {site.module}:{site.lineno} {site.kind}({site.path_expr}, {site.mode!r})"
            f" [ledger allows {ALLOWED_OUT_OF_STORE_WRITE_SITES.get(site.key, 0)}, found {found[site.key]}]"
            for site in violations
        )
        + "\n\nRoute the write through the status FSM (emit_status_transition / BookkeepingTransaction); "
        "raw appends go through store.py behind status/_unsafe.py (FR-010/FR-011)."
    )


def test_store_writes_are_found(tree_scan: TreeScan) -> None:
    """Positive census: the scanner sees the store's own writes, so the gate is not empty."""
    store_sites = [site for site in tree_scan.events_writes if site.module == STORE_MODULE]
    assert store_sites, "the scanner found no status.events.jsonl write in store.py -- the gate matches nothing"
    # The store's only write to the event log is the atomic rename in append_raw_rows_atomic
    # (``os.replace(tmp, path)``); the plain in-place append door was deleted (#6614).
    assert {(site.kind, site.mode) for site in store_sites} == {("os.replace", "replace")}, store_sites
    assert {site.module for site in tree_scan.events_writes if site.key not in ALLOWED_OUT_OF_STORE_WRITE_SITES} == {STORE_MODULE}


def test_allowed_out_of_store_sites_are_live(tree_scan: TreeScan) -> None:
    """A ledger entry with fewer live sites than it allows is stale and must shrink (shrink-only)."""
    shortfall = ledger_shortfall(tree_scan.events_writes)
    assert not shortfall, f"stale or over-counted ALLOWED_OUT_OF_STORE_WRITE_SITES entries {{key: (allowed, found)}}: {shortfall}"
    assert all(allowed >= 1 for allowed in ALLOWED_OUT_OF_STORE_WRITE_SITES.values())


def test_unresolved_write_paths_are_pinned(tree_scan: TreeScan) -> None:
    """Unresolved is not a pass: event-named dynamic writes and the known dynamic writers are pinned.

    Contract section 2. A new unresolved write whose path expression is
    event-named is a change to the write surface and must be reviewed; a
    known dynamic writer that resolves (or disappears) must be re-classified.
    """
    unresolved = {site.key for site in tree_scan.unresolved_writes}
    event_named = {site.key for site in tree_scan.unresolved_writes if site.is_event_named}
    assert event_named == EXPECTED_UNRESOLVED_EVENT_NAMED_WRITE_SITES, (
        "event-named unresolved write sites changed.\n"
        f"  new: {sorted(event_named - EXPECTED_UNRESOLVED_EVENT_NAMED_WRITE_SITES)}\n"
        f"  gone: {sorted(EXPECTED_UNRESOLVED_EVENT_NAMED_WRITE_SITES - event_named)}"
    )
    missing = KNOWN_DYNAMIC_EVENT_LOG_WRITE_SITES - unresolved
    assert not missing, f"known dynamic event-log writers no longer found unresolved: {sorted(missing)}"


def test_lock_composition_census(tree_scan: TreeScan) -> None:
    """R14: the set of modules composing ``feature_status_lock(`` is exactly the census."""
    found = tree_scan.lock_composition_modules
    assert found, "no feature_status_lock( call site found anywhere -- the census scan is vacuous"
    assert found == EXPECTED_LOCK_COMPOSITION_SITES, (
        "feature_status_lock composition sites changed.\n"
        f"  new: {sorted(found - EXPECTED_LOCK_COMPOSITION_SITES)}\n"
        f"  gone: {sorted(EXPECTED_LOCK_COMPOSITION_SITES - found)}\n"
        "A new lock + append composition is a new writer shell: route through the two shells in "
        "kitty-specs/fsm-write-path-integrity-01M1TZV6/contracts/emit-pipeline.md section 2, or "
        "update the census here AND design-notes/WP03-gates.md with the justification."
    )


# ---------------------------------------------------------------------------
# Non-vacuity floor (contract section 3)
# ---------------------------------------------------------------------------

_SYNTHETIC_WRITERS: tuple[tuple[str, str, str], ...] = (
    (
        "open-append-local-name",
        'from pathlib import Path\ndef bad(root: Path) -> None:\n    p = root / "status.events.jsonl"\n    with open(p, "a") as fh:\n        fh.write("x")\n',
        "open",
    ),
    ("path-open-ab", 'def bad(root):\n    (root / "status.events.jsonl").open("ab").truncate(0)\n', "Path.open"),
    ("write-text", 'def bad(root):\n    Path(str(root / "status.events.jsonl")).write_text("")\n', "write_text"),
    ("write-bytes-fstring", 'def bad(root):\n    Path(f"{root}/status.events.jsonl").write_bytes(b"")\n', "write_bytes"),
    ("os-open-flags", 'import os\ndef bad(root):\n    os.open(root / "status.events.jsonl", os.O_WRONLY | os.O_APPEND)\n', "os.open"),
    ("os-replace-destination", 'import os\ndef bad(root, tmp):\n    os.replace(tmp, root / "status.events.jsonl")\n', "os.replace"),
    ("shutil-move-keyword", 'import shutil\ndef bad(root, tmp):\n    shutil.move(tmp, dst=str(root / "status.events.jsonl"))\n', "shutil.move"),
    (
        "events-filename-alias",
        'from specify_cli.status import EVENTS_FILENAME as _EV\ndef bad(d):\n    with (d / _EV).open("a") as fh:\n        fh.write("")\n',
        "Path.open",
    ),
    ("module-constant", 'LOG = "status.events.jsonl"\ndef bad(d):\n    open(d / LOG, "w")\n', "open"),
    (
        "self-attribute",
        'class T:\n    def __init__(self, d):\n        self._p = d / "status.events.jsonl"\n    def roll(self):\n        self._p.open("ab").truncate(0)\n',
        "Path.open",
    ),
    (
        "same-module-function-return",
        'EV = "status.events.jsonl"\ndef _p(d):\n    return d / EV\ndef bad(d):\n    with _p(d).open("a") as fh:\n        fh.write("")\n',
        "Path.open",
    ),
    (
        "parameter-via-call-site",
        'def _w(p, row):\n    with p.open("a") as fh:\n        fh.write(row)\ndef bad(d):\n    _w(d / "status.events.jsonl", "x")\n',
        "Path.open",
    ),
    (
        "keyword-only-parameter-via-call-site",
        'def _w(*, events_path):\n    events_path.open("ab").truncate(0)\ndef bad(d):\n    _w(events_path=d / "status.events.jsonl")\n',
        "Path.open",
    ),
    (
        "constructor-parameter-via-self",
        "class T:\n    def __init__(self, events_path):\n        self._e = events_path\n"
        '    def roll(self):\n        self._e.open("ab").truncate(0)\n'
        'def mk(d):\n    return T(d / "status.events.jsonl")\n',
        "Path.open",
    ),
    ("unknown-mode-is-fail-closed", 'def bad(d, mode):\n    open(d / "status.events.jsonl", mode)\n', "open"),
)


@pytest.mark.parametrize(("case", "source", "kind"), _SYNTHETIC_WRITERS, ids=[case for case, _, _ in _SYNTHETIC_WRITERS])
def test_writes_gate_is_not_vacuous(case: str, source: str, kind: str, tree_scan: TreeScan) -> None:
    """Every write shape and resolution rule reports exactly one event-log write in a rogue module."""
    sites = scan_write_sites_from_source("specify_cli.synthetic.rogue_writer", source)
    hits = [site for site in sites if site.targets_events_log]
    assert len(hits) == 1, f"{case}: expected one event-log write, scanner reported {sites}"
    assert hits[0].kind == kind
    assert out_of_store_violations(hits) == hits
    assert tree_scan.events_writes, "real-tree scan matched zero writers"


#: One allowed write shape per ledger kind, as a function template: ``{name}``
#: lets the floor duplicate the SAME site shape (same key) under a second
#: function in the SAME module, which is exactly what a per-key count must catch.
_LEDGERED_SHAPES: tuple[tuple[str, str, tuple[str, str, str]], ...] = (
    (
        "open-exclusive-checkout-materialization",
        'def {name}(d):\n    events_path = d / "status.events.jsonl"\n    with open(events_path, "x", encoding="utf-8") as handle:\n        handle.write("")\n',
        ("specify_cli.lanes.auto_rebase", "open", "events_path"),
    ),
    (
        "os-replace-rewrite",
        'import os\ndef {name}(d, tmp):\n    events_file = d / "status.events.jsonl"\n    os.replace(str(tmp), str(events_file))\n',
        ("specify_cli.migration.rebuild_state", "os.replace", "str(events_file)"),
    ),
)


@pytest.mark.parametrize(("case", "template", "key"), _LEDGERED_SHAPES, ids=[case for case, _, _ in _LEDGERED_SHAPES])
def test_writes_gate_counts_ledgered_sites(case: str, template: str, key: tuple[str, str, str]) -> None:
    """A second identical write shape in an allowed module is reported; the single ledgered one is not."""
    module = key[0]
    assert ALLOWED_OUT_OF_STORE_WRITE_SITES[key] == 1
    single = scan_write_sites_from_source(module, template.format(name="one"))
    assert [site.key for site in single if site.targets_events_log] == [key], f"{case}: template does not produce the ledger key"
    assert out_of_store_violations(single) == []
    doubled = scan_write_sites_from_source(module, template.format(name="one") + template.format(name="two"))
    hits = [site for site in doubled if site.targets_events_log]
    assert out_of_store_site_counts(hits)[key] == 2
    violations = out_of_store_violations(hits)
    assert violations == hits, f"{case}: a duplicated allowed write shape slipped through on the ledger key"
    assert key not in ledger_shortfall(hits)
    assert ledger_shortfall(single[:0]) == dict.fromkeys(ALLOWED_OUT_OF_STORE_WRITE_SITES, (1, 0)), "an empty scan must report every ledger key short"


def test_writes_gate_ignores_reads_and_other_files() -> None:
    """Reads of the event log and writes of other files are not reported."""
    benign = (
        'def ok(d):\n    with open(d / "status.events.jsonl", "r") as fh:\n        fh.read()\n'
        '    (d / "status.events.jsonl").read_text()\n'
        '    with open(d / "other.jsonl", "a") as fh:\n        fh.write("")\n'
        '    (d / "status.events.jsonl.tmp").open("w").write("")\n'
    )
    sites = scan_write_sites_from_source("specify_cli.synthetic.reader", benign)
    assert [site for site in sites if site.targets_events_log] == []
    assert [site.path_text for site in sites] == ["other.jsonl", "status.events.jsonl.tmp"]


def test_writes_gate_reports_unresolved_paths_instead_of_passing() -> None:
    """A parameter with no or disagreeing call sites is reported unresolved, never as clean."""
    orphan = scan_write_sites_from_source("specify_cli.synthetic.dynamic", 'def w(events_path):\n    with open(events_path, "a") as fh:\n        fh.write("")\n')
    assert len(orphan) == 1 and orphan[0].path_text is None and orphan[0].is_event_named
    disagreeing = 'def w(p):\n    p.write_text("")\ndef a(d):\n    w(d / "status.events.jsonl")\ndef b(d):\n    w(d / "status.json")\n'
    sites = scan_write_sites_from_source("specify_cli.synthetic.dynamic", disagreeing)
    assert len(sites) == 1 and sites[0].path_text is None and not sites[0].targets_events_log


def test_lock_census_scanner_sees_both_call_shapes() -> None:
    """Bare and attribute ``feature_status_lock(`` calls are both census hits."""
    assert has_lock_call_site(ast.parse("with feature_status_lock(root, name):\n    pass\n"))
    assert has_lock_call_site(ast.parse("with _tasks.feature_status_lock(root, name):\n    pass\n"))
    assert has_lock_call_site(ast.parse("with mission_write_lock(feature_dir):\n    pass\n"))
    assert has_lock_call_site(ast.parse("with _mw.mission_write_lock(feature_dir):\n    pass\n"))
    assert not has_lock_call_site(ast.parse("lock = feature_status_lock\nfeature_status_lock_path(root, name)\n"))


# ---------------------------------------------------------------------------
# Invocation index single writer (#6614)
# ---------------------------------------------------------------------------

#: The only function in ``src/`` that may append to ``kitty-ops/ops-index.jsonl``.
EXPECTED_INDEX_WRITERS: frozenset[tuple[str, str]] = frozenset({("specify_cli.invocation.writer", "InvocationWriter._append_to_index")})

_INDEX_LITERALS: frozenset[str] = frozenset({"ops-index.jsonl", "kitty-ops/ops-index.jsonl"})
_INDEX_CONSTANT_NAMES: frozenset[str] = frozenset({"INDEX_PATH"})


def _docstring_nodes(tree: ast.Module) -> set[int]:
    """``id()`` of every docstring ``Constant`` node, so prose mentions are never matched."""
    found: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            first = node.body[0] if node.body else None
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                found.add(id(first.value))
    return found


def _module_index_constants(tree: ast.Module) -> frozenset[str]:
    """Module-level names bound to an exact index path literal, plus ``INDEX_PATH`` under any import alias."""
    names = set(_INDEX_CONSTANT_NAMES)
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and node.value.value in _INDEX_LITERALS:
            names.update(target.id for target in node.targets if isinstance(target, ast.Name))
        elif isinstance(node, ast.ImportFrom):
            names.update(alias.asname for alias in node.names if alias.name in _INDEX_CONSTANT_NAMES and alias.asname)
    return frozenset(names)


def _top_level_functions(tree: ast.Module) -> list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
    """``(qualified name, node)`` for each top-level function and each method of a top-level class."""
    found: list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            found.append((node.name, node))
        elif isinstance(node, ast.ClassDef):
            found.extend((f"{node.name}.{item.name}", item) for item in node.body if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef))
    return found


def _refers_to_index(fn: ast.AST, constants: frozenset[str], docstrings: set[int]) -> bool:
    for node in ast.walk(fn):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in _INDEX_LITERALS and id(node) not in docstrings:
            return True
        if isinstance(node, ast.Name) and node.id in constants:
            return True
        if isinstance(node, ast.Attribute) and node.attr in constants:
            return True
    return False


def _called_names(fn: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                names.add(func.id)
            elif isinstance(func, ast.Attribute):
                names.add(func.attr)
    return names


#: The interim locked append door (#6606, ``kernel.event_log_append``): a call to
#: it is a write, though it holds no raw write-mode file operation of its own.
_LOCKED_APPEND_DOORS: frozenset[str] = frozenset({"append_event_log_lines"})


def _is_write_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
    return name in _LOCKED_APPEND_DOORS or classify_call(node) is not None


def _writing_function_names(functions: list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]) -> set[str]:
    """Short names of module functions that write (a write-mode file operation or the locked door), directly or via a same-module callee."""
    direct = {qual.rsplit(".", 1)[-1] for qual, fn in functions if any(_is_write_call(n) for n in ast.walk(fn))}
    writing = set(direct)
    grew = True
    while grew:
        grew = False
        for qual, fn in functions:
            short = qual.rsplit(".", 1)[-1]
            if short not in writing and _called_names(fn) & writing:
                writing.add(short)
                grew = True
    return writing


def scan_index_writers(module: str, tree: ast.Module) -> set[tuple[str, str]]:
    """Functions that refer to the invocation index (code constant, not prose) and perform a file write."""
    functions = _top_level_functions(tree)
    constants = _module_index_constants(tree)
    docstrings = _docstring_nodes(tree)
    writing = _writing_function_names(functions)
    return {(module, qual) for qual, fn in functions if qual.rsplit(".", 1)[-1] in writing and _refers_to_index(fn, constants, docstrings)}


def scan_index_writers_from_source(module: str, source: str) -> set[tuple[str, str]]:
    return scan_index_writers(module, ast.parse(source))


def test_invocation_index_has_a_single_writer(src_source_tree: Mapping[Path, SourceFile]) -> None:
    """Only ``InvocationWriter._append_to_index`` appends to ``kitty-ops/ops-index.jsonl``.

    A function census rather than a path census: the plain path resolver cannot
    follow ``INDEX_PATH`` across modules, and the writer's shared
    ``_append_line_no_follow`` staticmethod is called with different paths. A
    function is reported when it names the index in code (never in a docstring)
    and contains, or calls a same-module function that contains, a write-mode
    file operation.

    Known limits (recorded at review, not worth a cross-module call graph): a
    write delegated to a helper in another module, a method of a nested class,
    and module-level code are not followed.
    """
    found: set[tuple[str, str]] = set()
    for path, entry in src_source_tree.items():
        assert isinstance(entry.tree, ast.Module)
        found |= scan_index_writers(module_name_for(path), entry.tree)
    assert found == EXPECTED_INDEX_WRITERS, (
        f"kitty-ops/ops-index.jsonl is written outside specify_cli.invocation.writer: {sorted(found - EXPECTED_INDEX_WRITERS)}; "
        f"missing expected writer: {sorted(EXPECTED_INDEX_WRITERS - found)}"
    )


_INDEX_WRITER_SOURCE = (
    "INDEX_PATH = 'kitty-ops/ops-index.jsonl'\n"
    "def append_to_index(repo_root, record):\n"
    "    index_path = repo_root / INDEX_PATH\n"
    "    with index_path.open('a', encoding='utf-8') as f:\n"
    "        f.write('x')\n"
)


def test_index_census_is_not_vacuous() -> None:
    """Planted writers are reported; read-only and prose-only mentions are not."""
    planted = scan_index_writers_from_source("specify_cli.cli.commands.invocations_cmd", _INDEX_WRITER_SOURCE)
    assert planted == {("specify_cli.cli.commands.invocations_cmd", "append_to_index")}
    literal = scan_index_writers_from_source("specify_cli.rogue", "def w(d):\n    open(d / 'ops-index.jsonl', 'a').write('x')\n")
    assert literal == {("specify_cli.rogue", "w")}
    locked = scan_index_writers_from_source("specify_cli.rogue", "def w(d):\n    append_event_log_lines(d / 'ops-index.jsonl', ['x'])\n")
    assert locked == {("specify_cli.rogue", "w")}
    delegated = scan_index_writers_from_source(
        "specify_cli.rogue",
        "INDEX = 'kitty-ops/ops-index.jsonl'\ndef _w(p):\n    p.write_text('x')\ndef w(d):\n    _w(d / INDEX)\n",
    )
    assert ("specify_cli.rogue", "w") in delegated
    aliased = scan_index_writers_from_source(
        "specify_cli.rogue",
        "from specify_cli.invocation.writer import INDEX_PATH as _IDX\ndef w(root):\n    (root / _IDX).open('a').write('x')\n",
    )
    assert aliased == {("specify_cli.rogue", "w")}
    read_only = (
        "from specify_cli.invocation.writer import INDEX_PATH\n"
        "def _iter_records(repo_root, events_dir):\n"
        "    if repo_root is not None:\n"
        "        index_path = repo_root / INDEX_PATH\n"
        "    else:\n"
        "        index_path = events_dir / 'ops-index.jsonl'\n"
        "    return index_path.read_text()\n"
    )
    assert scan_index_writers_from_source("specify_cli.reader", read_only) == set()
    prose = 'def started(p):\n    """Appends to kitty-ops/ops-index.jsonl afterwards."""\n    with p.open("x") as f:\n        f.write("")\n'
    assert scan_index_writers_from_source("specify_cli.prose", prose) == set()


def test_index_census_floor_finds_the_live_writer(src_source_tree: Mapping[Path, SourceFile]) -> None:
    """The live scan sees the writer's own function, so the census is not matching nothing."""
    writer = next(path for path in src_source_tree if module_name_for(path) == "specify_cli.invocation.writer")
    entry = src_source_tree[writer]
    assert isinstance(entry.tree, ast.Module)
    assert ("specify_cli.invocation.writer", "InvocationWriter._append_to_index") in scan_index_writers("specify_cli.invocation.writer", entry.tree)
