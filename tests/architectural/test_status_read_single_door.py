"""#7310 / #7408 (FR-006 of Mission ``lane-worktree-model-hardening-01M6QY1M``): one status read door.

ADR ``docs/adr/4.x/2026-11-06-2-one-status-read-contract.md`` invariant 4: no status read runs
outside :func:`specify_cli.status.read_surface.resolve_status_read`. A reader that finds its own
status source re-derives topology, coordination state and "has landed" by itself, and that is how
``agent tasks status`` came to show a different log than the door readers (#7335).

The gate scans ``src/`` (AST only) for the legacy ways of finding a status *source*:

* ``resolve_status_surface`` / ``resolve_status_surface_with_anchor`` (the legacy path projection;
  a ``for_write=True`` call is the write seam and is not a read);
* ``read_event_log`` / ``read_event_stream_log`` (the transaction read contract);
* ``resolve_surface_dir_or_typed_error`` (the Path-typed delegator);
* any ``STATUS_STATE`` read off the placement seam: ``seam.read_dir(STATUS_STATE)``,
  ``resolve_partition_read_dir(..., STATUS_STATE)``, ``resolve_artifact_surface(..., STATUS_STATE)``
  and ``ctx.artifact(STATUS_STATE)`` unless only its ``write_dir`` / ``commit_target`` is used.

Every hit must be in :data:`LEGACY_READ_ALLOWLIST`. The allowlist is **transient, priced debt**
(charter Standing Order #5, ADR ``2026-09-30-1``): issue #7310 owns it, the follow-up Mission of
#7310 drains it, and the drain date is :data:`ALLOWLIST_DRAIN_BY`. It is **shrink-only**: a new
hit fails, and an entry that no longer matches a hit fails too, so a migrated reader must take its
entry out in the same change. The allowlist IS the census (one entry per enclosing function and
form, grouped by reason); ADR 2026-11-06-2, Amendment 2026-11-08, records its shape at landing.

A second, positive check pins the modules already moved onto the door (:data:`DOOR_ONLY_MODULES`):
they may not call a legacy source finder *or* a path-typed log reader (``read_events``,
``reconstruct_wp_view``, ``get_wp_lane`` ...). That set only grows.

Non-vacuity (DIRECTIVE_043): the planted-violation tests below prove each scanned form is caught,
and :func:`test_scan_sees_the_real_tree` proves the live scan matched the recorded floor of hits.
"""

from __future__ import annotations

import ast
import functools
from dataclasses import dataclass
from pathlib import Path

import pytest

pytestmark = pytest.mark.architectural

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = _REPO_ROOT / "src"

#: The owning issue and the date by which the follow-up Mission drains the allowlist.
#: The 2026-12-31 drain date is operator-confirmed; #7310 owns it, and moving it
#: is the operator's call, recorded on that issue, never a change made here to keep a gate green.
ALLOWLIST_ISSUE = "#7310"
ALLOWLIST_DRAIN_BY = "2026-12-31"

#: Legacy source finders matched by callee name alone.
_LEGACY_FINDERS = frozenset(
    {
        "resolve_status_surface",
        "resolve_status_surface_with_anchor",
        "read_event_log",
        "read_event_stream_log",
        "resolve_surface_dir_or_typed_error",
    }
)

#: Seam forms that are a status read only when they name ``STATUS_STATE``.
_STATUS_STATE_READ_FORMS = frozenset({"read_dir", "resolve_partition_read_dir", "resolve_artifact_surface", "artifact"})

#: Attributes of ``ctx.artifact(STATUS_STATE)`` that are the write seam, not a read.
_WRITE_ATTRS = frozenset({"write_dir", "commit_target"})

#: Path-typed log readers a door-only module may not call (it reads a surface instead).
_PATH_TYPED_READERS = frozenset(
    {
        "read_events",
        "read_event_stream",
        "wp_snapshot_state",
        "reconstruct_wp_view",
        "has_event_log",
        "get_wp_lane",
        "get_all_wp_lanes",
        "event_sourced_review_result",
        "get_arbiter_overrides_for_wp",
    }
)


@dataclass(frozen=True, order=True)
class Hit:
    """One legacy status read: ``<path>::<enclosing function>::<form>`` is its allowlist key."""

    path: str
    function: str
    form: str
    line: int

    @property
    def key(self) -> str:
        return f"{self.path}::{self.function}::{self.form}"


def _import_aliases(tree: ast.AST) -> dict[str, str]:
    """``{local alias: imported name}`` for every ``from x import name as alias`` in the module.

    A call through an alias (``read_events as rw_read_events``) is matched by the name it
    imports, so an alias cannot hide a read from the scan.
    """
    return {alias.asname: alias.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) for alias in node.names if alias.asname}


def _callee(func: ast.expr, aliases: dict[str, str] | None = None) -> str | None:
    if isinstance(func, ast.Name):
        return (aliases or {}).get(func.id, func.id)
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _names_status_state(call: ast.Call) -> bool:
    for arg in [*call.args, *(kw.value for kw in call.keywords)]:
        if isinstance(arg, ast.Attribute) and arg.attr == "STATUS_STATE":
            return True
        if isinstance(arg, ast.Name) and arg.id == "STATUS_STATE":
            return True
    return False


def _is_for_write(call: ast.Call) -> bool:
    return any(kw.arg == "for_write" and isinstance(kw.value, ast.Constant) and kw.value.value is True for kw in call.keywords)


def _parents(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    return {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}


def _enclosing_function(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> str:
    names: list[str] = []
    current: ast.AST | None = node
    while current is not None:
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.append(current.name)
        current = parents.get(current)
    return ".".join(reversed(names)) or "<module>"


def _legacy_form(call: ast.Call, parents: dict[ast.AST, ast.AST], aliases: dict[str, str]) -> str | None:
    """The legacy-read form of *call*, or ``None`` when it is not a legacy status read."""
    name = _callee(call.func, aliases)
    if name in _LEGACY_FINDERS:
        return None if _is_for_write(call) else name
    if name in _STATUS_STATE_READ_FORMS and _names_status_state(call):
        parent = parents.get(call)
        if name == "artifact" and isinstance(parent, ast.Attribute) and parent.attr in _WRITE_ATTRS:
            return None
        return f"{name}(STATUS_STATE)"
    return None


def scan_source(source: str, rel_path: str, *, forms: frozenset[str] | None = None) -> list[Hit]:
    """Every legacy status read in *source*; with *forms*, also calls named in that set."""
    tree = ast.parse(source)
    parents = _parents(tree)
    aliases = _import_aliases(tree)
    hits: list[Hit] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        form = _legacy_form(node, parents, aliases)
        if form is None and forms is not None:
            name = _callee(node.func, aliases)
            form = name if name in forms else None
        if form is not None:
            hits.append(Hit(rel_path, _enclosing_function(node, parents), form, node.lineno))
    return sorted(hits)


@functools.cache
def _scan_tree() -> tuple[Hit, ...]:
    hits: list[Hit] = []
    for path in sorted(_SRC.rglob("*.py")):
        rel = path.relative_to(_REPO_ROOT).as_posix()
        hits.extend(scan_source(path.read_text(encoding="utf-8"), rel))
    return tuple(hits)


# ---------------------------------------------------------------------------
# The transient allowlist (issue #7310, drain by ALLOWLIST_DRAIN_BY). Shrink-only.
# Each value says why the reader has not moved yet.
# ---------------------------------------------------------------------------

_SEAM_ARM = "STATUS_STATE read_dir arm of the placement seam is Path-typed and cannot express a ref source; callers move to the door first"
_PATH_CONSUMER = "Path-typed consumer (get_wp_lane / read_events / has_event_log on a dir); needs a surface-typed read"
_RUNTIME = "runtime decision path reads STATUS_STATE through the mission context; moves with the runtime bridge readers"
_DELEGATOR = "legacy Path projection shared by mission_runtime callers; deleted once its callers read the door"
_WRITE_SIDE = "write-side transaction reads its own target (writer cut-over #6195/#6608 owns it)"
_PIN = "finalize planning pin reads the status dir as a Path (#5702 decides its fail-open polarity first)"
_WRITES_THROUGH_READ = "writes the review override through a read_dir(STATUS_STATE) path (census hazard); must move to the write seam, not the door"
_PARTITION = "handed-dir partition authority (#5180) consumed as a Path by verdict/feedback readers"
_HANDED_REF = "consolidation strand authority reads the committed coordination ref the rollback handed it (no re-resolution drift)"
_IDENTITY = "identity check compares the owned Mission dir with the STATUS_STATE dir; not a log read"
_DRIFT = "tasks_are_finalized cross-checks status.json beside the log (SNAPSHOT_DRIFT); needs a surface-typed drift check"
_FAIL_LOUD = "lane-destroyed guard depends on the seam raising for an unmaterialized coordination worktree (#4889)"
_AGGREGATE = "MissionStatus keeps a Path read dir for its create-window gate (#3462)"
_WORKPACKAGE = "WorkPackage.status_dir / reconstruct_wp_view are Path-typed (20 + 15 callers in the census)"
_DOCTOR = "fail-closed / existence probe that relies on CoordinationWorktreeUnmaterialized; needs a door-level probe"

LEGACY_READ_ALLOWLIST: dict[str, str] = {
    "src/mission_runtime/resolution.py::_resolve_status_surface_dir::resolve_status_surface": _SEAM_ARM,
    "src/runtime/next/decision.py::_with_guard_failure_paths::artifact(STATUS_STATE)": _RUNTIME,
    "src/runtime/next/next_invocation_lifecycle.py::emit_mission_next_invoked::artifact(STATUS_STATE)": _RUNTIME,
    "src/runtime/next/runtime_bridge.py::_dn_bootstrap::artifact(STATUS_STATE)": _RUNTIME,
    "src/runtime/next/runtime_bridge_decision_mapping.py::_resolve_wp_board_action::artifact(STATUS_STATE)": _RUNTIME,
    "src/runtime/next/runtime_bridge_decision_mapping.py::_resolve_wp_board_action::read_dir(STATUS_STATE)": _DOCTOR,
    "src/runtime/next/runtime_bridge_io.py::_artifact_presence_seam::read_dir(STATUS_STATE)": _DOCTOR,
    "src/runtime/next/runtime_bridge_query.py::_build_finalized_override_query_decision::artifact(STATUS_STATE)": _RUNTIME,
    "src/runtime/next/runtime_bridge_query.py::query_current_state::artifact(STATUS_STATE)": _RUNTIME,
    "src/specify_cli/acceptance/__init__.py::_status_read_feature_dir::read_dir(STATUS_STATE)": _PATH_CONSUMER,
    "src/specify_cli/agent_utils/status.py::build_kanban_status::read_dir(STATUS_STATE)": _PATH_CONSUMER,
    "src/specify_cli/charter_pack_synthesizer/apply.py::_feature_dir::read_dir(STATUS_STATE)": _PATH_CONSUMER,
    "src/specify_cli/cli/commands/_decisions_doctor.py::_mission_dir::read_dir(STATUS_STATE)": _DOCTOR,
    "src/specify_cli/cli/commands/accept.py::_evidence_status_dir::read_dir(STATUS_STATE)": _PATH_CONSUMER,
    "src/specify_cli/cli/commands/agent/mission_check_prerequisites.py::_status_events_log_path::read_dir(STATUS_STATE)": _DOCTOR,
    "src/specify_cli/cli/commands/agent/mission_finalize_lanes.py::_missing_status_surface_cause::read_dir(STATUS_STATE)": _DOCTOR,
    "src/specify_cli/cli/commands/agent/mission_finalize_planning_pin.py::_resolve_status_read_dir::read_dir(STATUS_STATE)": _PIN,
    "src/specify_cli/cli/commands/agent/mission_finalize_planning_pin.py::_resolve_status_read_dir::resolve_status_surface_with_anchor": _PIN,
    "src/specify_cli/cli/commands/agent/tasks.py::list_tasks::read_dir(STATUS_STATE)": _PATH_CONSUMER,
    "src/specify_cli/cli/commands/agent/tasks.py::validate_workflow::read_dir(STATUS_STATE)": _PATH_CONSUMER,
    "src/specify_cli/cli/commands/agent/tasks_dependency_graph.py::_check_dependent_warnings::read_dir(STATUS_STATE)": _PATH_CONSUMER,
    "src/specify_cli/cli/commands/agent/tasks_materialization.py::_persist_review_artifact_override::read_dir(STATUS_STATE)": _WRITES_THROUGH_READ,
    "src/specify_cli/cli/commands/agent/tasks_verdict_persistence.py::_resolve_verdict_read_feature_dir::resolve_partition_read_dir(STATUS_STATE)": _PARTITION,
    "src/specify_cli/cli/commands/agent/workflow_cores.py::_resolve_status_state_read_dir::resolve_partition_read_dir(STATUS_STATE)": _PARTITION,
    "src/specify_cli/coordination/coherence.py::coord_incoherent_done_wps::read_event_log": _HANDED_REF,
    "src/specify_cli/coordination/status_transition.py::_canonical_primary_feature_dir::resolve_status_surface_with_anchor": _WRITE_SIDE,
    "src/specify_cli/coordination/status_transition.py::_read_event_stream_from_transaction_target::read_event_stream_log": _WRITE_SIDE,
    "src/specify_cli/coordination/status_transition.py::_read_events_from_transaction_target::read_event_log": _WRITE_SIDE,
    "src/specify_cli/coordination/status_transition.py::read_current_wp_state_transactional::read_event_stream_log": _WRITE_SIDE,
    "src/specify_cli/coordination/surface_resolver.py::resolve_status_surface::resolve_status_surface_with_anchor": _DELEGATOR,
    "src/specify_cli/core/owned_charter.py::charter_scope_for_owned::artifact(STATUS_STATE)": _IDENTITY,
    "src/specify_cli/design/validation.py::_tasks_finalized::read_dir(STATUS_STATE)": _DRIFT,
    "src/specify_cli/lanes/checkout_occupancy.py::_lane_mates_writing::read_dir(STATUS_STATE)": _PATH_CONSUMER,
    "src/specify_cli/lanes/checkout_occupancy.py::_writers_in_write_checkout::read_dir(STATUS_STATE)": _PATH_CONSUMER,
    "src/specify_cli/lanes/implement_support.py::_ensure_repo_root_checkout_available::read_dir(STATUS_STATE)": _PATH_CONSUMER,
    "src/specify_cli/lanes/implement_support.py::reenter_lane_self_heal::read_dir(STATUS_STATE)": _PATH_CONSUMER,
    "src/specify_cli/lanes/recovery.py::scan_recovery_state::read_dir(STATUS_STATE)": _PATH_CONSUMER,
    "src/specify_cli/lanes/worktree_allocator.py::_canonical_wp_lane_value::read_dir(STATUS_STATE)": _FAIL_LOUD,
    "src/specify_cli/missions/_read_path_resolver.py::resolve_surface_dir_or_typed_error::resolve_status_surface": _DELEGATOR,
    "src/specify_cli/post_merge/review_artifact_consistency.py::_resolve_lane_state_read_dir::resolve_partition_read_dir(STATUS_STATE)": _PARTITION,
    "src/specify_cli/release/changelog.py::_resolve_status_read_dir::read_dir(STATUS_STATE)": _DOCTOR,
    "src/specify_cli/status/aggregate.py::MissionStatus._resolve_read_dir::resolve_surface_dir_or_typed_error": _AGGREGATE,
    "src/specify_cli/task_utils/support.py::locate_work_package::read_dir(STATUS_STATE)": _WORKPACKAGE,
    "src/specify_cli/task_utils/support.py::locate_work_package::resolve_status_surface": _WORKPACKAGE,
    "src/specify_cli/workspace/context.py::resolve_active_wp_for_branch::read_dir(STATUS_STATE)": _PATH_CONSUMER,
}


# ---------------------------------------------------------------------------
# Door-only modules: already on the door, pinned so they never regress. Grow-only.
# ---------------------------------------------------------------------------

DOOR_ONLY_MODULES: frozenset[str] = frozenset(
    {
        # #7335: the status board reads one door surface and reduces it once.
        "src/specify_cli/cli/commands/agent/tasks_status_cmd.py",
        # #7408: the first lane readers moved onto the door. (workflow_executor.py moved one
        # reader but still makes path-typed reads, so it is not door-only yet.)
        "src/specify_cli/git/origin_freshness.py",
        "src/specify_cli/lanes/claim_base.py",
        # #7433: the merged_at backfill and its terminal-WP evidence read the door only.
        "src/specify_cli/migration/backfill_merged_at.py",
        "src/specify_cli/status/landing_evidence.py",
    }
)

#: The live scan must see at least this many hits (anti-vacuity floor; lower it as the allowlist drains).
_LIVE_HIT_FLOOR = 40


def test_no_status_read_bypasses_the_door() -> None:
    unexpected = sorted({hit.key: hit for hit in _scan_tree() if hit.key not in LEGACY_READ_ALLOWLIST}.values())
    assert not unexpected, (
        "status read(s) bypass the one read door (ADR 2026-11-06-2, #7310). Read through "
        "specify_cli.status.resolve_status_read + read_status_events / read_status_stream / materialize_status:\n"
        + "\n".join(f"  {hit.path}:{hit.line} {hit.function} -> {hit.form}" for hit in unexpected)
    )


def test_allowlist_is_shrink_only() -> None:
    live = {hit.key for hit in _scan_tree()}
    stale = sorted(set(LEGACY_READ_ALLOWLIST) - live)
    assert not stale, "allowlist entries no longer match a legacy read; remove them (shrink-only, #7310):\n" + "\n".join(f"  {key}" for key in stale)


def test_every_allowlist_entry_has_a_reason() -> None:
    assert all(reason.strip() for reason in LEGACY_READ_ALLOWLIST.values())


@pytest.mark.parametrize("module", sorted(DOOR_ONLY_MODULES))
def test_door_only_module_reads_no_path_typed_status(module: str) -> None:
    source = (_REPO_ROOT / module).read_text(encoding="utf-8")
    hits = scan_source(source, module, forms=_PATH_TYPED_READERS)
    listing = "\n".join(f"  line {hit.line} {hit.function} -> {hit.form}" for hit in hits)
    assert not hits, f"{module} is pinned door-only (#7408) but reads status without the door:\n{listing}"


def test_scan_sees_the_real_tree() -> None:
    assert len(_scan_tree()) >= _LIVE_HIT_FLOOR


# ---------------------------------------------------------------------------
# Planted violations (non-vacuity): every scanned form is caught; the write seam is not.
# ---------------------------------------------------------------------------

_PLANTED = {
    "resolve_status_surface": "def f(r, m):\n    return resolve_status_surface(r, m)\n",
    "resolve_status_surface_with_anchor": "def f(r, m):\n    return resolve_status_surface_with_anchor(r, m).surface_path\n",
    "read_event_log": "def f(c):\n    return read_event_log(c)\n",
    "read_event_stream_log": "def f(c):\n    return status_service.read_event_stream_log(c)\n",
    "resolve_surface_dir_or_typed_error": "def f(r, m):\n    return resolve_surface_dir_or_typed_error(r, m)\n",
    "read_dir(STATUS_STATE)": "def f(r, m):\n    return placement_seam(r, m).read_dir(MissionArtifactKind.STATUS_STATE)\n",
    "resolve_partition_read_dir(STATUS_STATE)": "def f(d):\n    return resolve_partition_read_dir(d, MissionArtifactKind.STATUS_STATE)\n",
    "resolve_artifact_surface(STATUS_STATE)": "def f(r, m):\n    return resolve_artifact_surface(r, m, kind=K.STATUS_STATE).path\n",
    "artifact(STATUS_STATE)": "def f(ctx):\n    return ctx.artifact(MissionArtifactKind.STATUS_STATE).read_dir\n",
}


@pytest.mark.parametrize("form", sorted(_PLANTED))
def test_planted_violation_is_caught(form: str) -> None:
    hits = scan_source(_PLANTED[form], "planted.py")
    assert [(hit.function, hit.form, hit.line) for hit in hits] == [("f", form, 2)]


@pytest.mark.parametrize(
    "benign",
    [
        "def f(r, m):\n    return resolve_status_surface(r, m, for_write=True)\n",
        "def f(r, m):\n    return placement_seam(r, m).write_dir(MissionArtifactKind.STATUS_STATE)\n",
        "def f(ctx):\n    return ctx.artifact(MissionArtifactKind.STATUS_STATE).commit_target\n",
        "def f(ctx):\n    return ctx.artifact(MissionArtifactKind.STATUS_STATE).write_dir\n",
        "def f(r, m):\n    return placement_seam(r, m).read_dir(MissionArtifactKind.WORK_PACKAGE_TASK)\n",
        "def f(r, m):\n    return materialize_status(resolve_status_read(r, m))\n",
    ],
)
def test_write_seam_and_the_door_are_not_flagged(benign: str) -> None:
    assert scan_source(benign, "benign.py") == []


def test_door_only_forms_catch_path_typed_readers() -> None:
    planted = "class S:\n    def g(self, d):\n        return read_events(d)\n"
    hits = scan_source(planted, "planted.py", forms=_PATH_TYPED_READERS)
    assert [(hit.function, hit.form) for hit in hits] == [("S.g", "read_events")]


def test_an_import_alias_does_not_hide_a_read() -> None:
    planted = (
        "from specify_cli.coordination.status_service import read_event_log as rel\n"
        "from specify_cli.status import read_events as rw_read_events\n"
        "def f(c, d):\n"
        "    rel(c)\n"
        "    return rw_read_events(d)\n"
    )
    assert [(hit.form, hit.line) for hit in scan_source(planted, "planted.py")] == [("read_event_log", 4)]
    assert [(hit.form, hit.line) for hit in scan_source(planted, "planted.py", forms=_PATH_TYPED_READERS)] == [
        ("read_event_log", 4),
        ("read_events", 5),
    ]


def test_allowlist_check_reds_on_an_unlisted_hit() -> None:
    hit = scan_source(_PLANTED["read_event_log"], "src/planted.py")[0]
    assert hit.key not in LEGACY_READ_ALLOWLIST
    assert hit.key == "src/planted.py::f::read_event_log"
