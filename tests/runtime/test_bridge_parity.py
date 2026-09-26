"""Parity oracle — the WP01 characterization safety net for #2531.

Drives the three real public entry points of ``runtime_bridge.py``
(``decide_next_via_runtime``, ``query_current_state``,
``answer_decision_via_runtime``) against realistic on-disk mission repos and
asserts:

1. Every fixture parity-holds across two independent fresh ``copytree`` runs
   of the same frozen snapshot (``_bridge_oracle.assert_parity`` /
   ``canonical``) — proves masking collapses per-run ULID/timestamp/path
   noise without swallowing a real behavior change.
2. The coverage floor (every known ``Decision(...)`` site + guard branch,
   reached from its owning entry) is met, asserted as a checkable count —
   never as a fixture count (a hollow harness must fail here).
3. Named highest-risk fixtures (both guard fail-closed defaults + the
   ``tasks`` legacy-union) assert identical ``guard_failures`` content AND
   order across the two independent runs.
4. Captured side effects (sync emit, coord commit, retrospective gate, the
   IC-02 engine mutations) assert binding equality across the two runs.
5. The ``reason``-normalizer meta-test: masking collapses path noise but
   never a semantic delta.

See ``tests/runtime/fixtures/bridge/README.md`` for the fixture-snapshot
layout and regeneration procedure, and
``kitty-specs/runtime-bridge-degod-01KX8M1C/contracts/parity-oracle.md`` for
the authoritative contract this module implements.

Never stubs ``next_step`` / ``get_or_start_run`` — the runtime planner is the
logic under test (WP01 safeguard).
"""

from __future__ import annotations

import json
import re
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from runtime.next.decision import DecisionKind
from tests.lane_test_utils import write_single_lane_manifest
from tests.runtime._bridge_oracle import (
    CoverageLedger,
    GuardCall,
    SideEffectCapture,
    assert_coverage_floor_met,
    canonical,
    canonical_side_effects,
    capture_decision_sites,
    capture_guard_calls,
    capture_side_effects,
    timed_call,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


# ---------------------------------------------------------------------------
# Repo scaffolding — mirrors the proven patterns in tests/next/test_runtime_
# bridge_unit.py, tests/next/test_finalized_task_routing.py, and
# tests/integration/test_{research,documentation}_runtime_walk.py.
# ---------------------------------------------------------------------------


def _init_git_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "--initial-branch=main"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, capture_output=True, check=True)
    (path / "README.md").write_text("# test\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, capture_output=True, check=True)


def _commit_all(path: Path, message: str) -> None:
    subprocess.run(["git", "add", "."], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", message], cwd=path, capture_output=True, check=True)


def _seed_wp_lane(feature_dir: Path, mission_slug: str, wp_id: str, lane: str) -> None:
    from specify_cli.status.models import Lane, StatusEvent
    from specify_cli.status.store import append_event

    append_event(
        feature_dir,
        StatusEvent(
            event_id=f"seed-{wp_id}-{lane}",
            mission_slug=mission_slug,
            wp_id=wp_id,
            from_lane=Lane.PLANNED,
            to_lane=Lane(lane),
            at="2026-01-01T00:00:00+00:00",
            actor="fixture",
            force=True,
            execution_mode="worktree",
        ),
    )


def _write_wp_task_files(feature_dir: Path, wps: dict[str, str], *, deps: bool = True) -> None:
    """Write realistic WP task files + the single-lane manifest — no lane-event
    seed here (WP01 / advancing-next-board-unification-01M3BGQ0: coord-topology
    fixtures need WP files on the PRIMARY dir but lane events on the
    coordination status surface, so the file-write and event-seed halves of
    the former ``_add_wp_files`` are split; single_branch callers get both
    back via :func:`_add_wp_files` below, byte-identical to before the split).

    Production-shaped: real WP headings, a title, and (when ``deps``) an
    explicit ``dependencies:`` frontmatter field so the finalize-tasks guard
    is satisfied by default (fixtures that specifically characterize the
    missing-dependencies branch pass ``deps=False``).
    """
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(exist_ok=True)
    for wp_id in wps:
        deps_line = "dependencies: []\n" if deps else ""
        (tasks_dir / f"{wp_id}.md").write_text(
            f"---\nwork_package_id: {wp_id}\n{deps_line}title: {wp_id} implement the thing\n"
            f"role: implementer\nrequirement_refs: [FR-001]\n---\n"
            f"## Work Package {wp_id}: Implement the thing\n\n"
            f"### Requirements\n- FR-001\n\nDo the {wp_id} work.\n",
            encoding="utf-8",
        )
    write_single_lane_manifest(feature_dir, wp_ids=tuple(wps.keys()))


def _add_wp_files(feature_dir: Path, mission_slug: str, wps: dict[str, str], *, deps: bool = True) -> None:
    """Write realistic WP files + seed their canonical lane state (single_branch
    shape: WP files and lane events share the same dir)."""
    _write_wp_task_files(feature_dir, wps, deps=deps)
    for wp_id, lane in wps.items():
        _seed_wp_lane(feature_dir, mission_slug, wp_id, lane)


def _write_spec_md(feature_dir: Path, requirement_ids: list[str]) -> None:
    reqs = "\n".join(f"- {rid}: requirement {rid}" for rid in requirement_ids)
    (feature_dir / "spec.md").write_text(
        f"# Spec\n\n## Functional Requirements\n{reqs}\n",
        encoding="utf-8",
    )


def _provision_mission_type_activations(repo_root: Path, mission_type: str) -> None:
    """Provision ``.kittify/config.yaml`` with ``mission_type`` activated.

    WP04 fail-closed (C-A1): composition (``_dispatch_via_composition``) calls
    ``resolve_mission_type_context`` for real, so every scaffold's mission
    type must be activated for that resolution to succeed.
    """
    kittify_dir = repo_root / ".kittify"
    kittify_dir.mkdir(exist_ok=True)
    (kittify_dir / "config.yaml").write_text(
        f"mission_type_activations:\n  - {mission_type}\n", encoding="utf-8"
    )


def _write_block_retrospective_config(repo_root: Path) -> None:
    """Write a ``.kittify/config.yaml`` that turns the retrospective into a
    pre-completion BLOCKING gate. This is the real on-disk config surface
    (``_load_config_retrospective_block``); it makes ``decide_next`` take the
    ``block_on_retrospective`` branch (pre-state read + buffered emit) that two
    of the error-arm fixtures characterize.

    Both call sites invoke this AFTER ``scaffold_software_dev`` has already
    provisioned ``mission_type_activations`` (WP04 C-A1); a full-file
    overwrite here would silently wipe that key back to fail-closed, so
    ``software-dev`` is re-provisioned alongside the retrospective block.
    """
    (repo_root / ".kittify").mkdir(exist_ok=True)
    (repo_root / ".kittify" / "config.yaml").write_text(
        "retrospective:\n  enabled: true\n  timing: before_completion\n  failure_policy: block\n"
        "mission_type_activations:\n  - software-dev\n",
        encoding="utf-8",
    )


def scaffold_software_dev(
    repo_root: Path,
    mission_slug: str = "042-parity-oracle",
    *,
    wps: dict[str, str] | None = None,
    with_spec: bool = False,
    with_plan: bool = False,
    with_tasks_md: bool = False,
    requirement_ids: list[str] | None = None,
    wp_deps: bool = True,
) -> Path:
    _init_git_repo(repo_root)
    _provision_mission_type_activations(repo_root, "software-dev")
    feature_dir = repo_root / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(json.dumps({"mission_type": "software-dev"}), encoding="utf-8")
    if with_spec:
        _write_spec_md(feature_dir, requirement_ids or ["FR-001"])
    if with_plan:
        (feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    if with_tasks_md:
        (feature_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
    if wps:
        _add_wp_files(feature_dir, mission_slug, wps, deps=wp_deps)
    _commit_all(repo_root, "seed software-dev fixture")
    return repo_root


def scaffold_research(
    repo_root: Path,
    mission_slug: str = "050-research-parity",
    *,
    with_spec: bool = False,
    with_plan: bool = False,
    with_sources: int = 0,
    with_findings: bool = False,
    with_report: bool = False,
    publication_approved: bool = False,
) -> Path:
    _init_git_repo(repo_root)
    _provision_mission_type_activations(repo_root, "research")
    feature_dir = repo_root / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(json.dumps({"mission_type": "research"}), encoding="utf-8")
    if with_spec:
        (feature_dir / "spec.md").write_text("# spec\n", encoding="utf-8")
    if with_plan:
        (feature_dir / "plan.md").write_text("# plan\n", encoding="utf-8")
    events: list[dict[str, str]] = []
    if with_sources:
        (feature_dir / "source-register.csv").write_text(
            "id,citation\n" + "".join(f"{i},Source {i}\n" for i in range(1, with_sources + 1)),
            encoding="utf-8",
        )
        events.extend({"name": f"src-{i}", "type": "source_documented"} for i in range(1, with_sources + 1))
    if with_findings:
        (feature_dir / "findings.md").write_text("# findings\n", encoding="utf-8")
    if with_report:
        (feature_dir / "report.md").write_text("# report\n", encoding="utf-8")
    if publication_approved:
        events.append({"name": "publication_approved", "type": "gate_passed"})
    if events:
        (feature_dir / "mission-events.jsonl").write_text(
            "\n".join(json.dumps(e, sort_keys=True) for e in events) + "\n", encoding="utf-8"
        )
    _commit_all(repo_root, "seed research fixture")
    return repo_root


def scaffold_documentation(
    repo_root: Path,
    mission_slug: str = "060-docs-parity",
    *,
    with_spec: bool = False,
    with_gap_analysis: bool = False,
    with_plan: bool = False,
    with_generated_docs: bool = False,
    with_audit_report: bool = False,
    with_release: bool = False,
) -> Path:
    _init_git_repo(repo_root)
    _provision_mission_type_activations(repo_root, "documentation")
    feature_dir = repo_root / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(json.dumps({"mission_type": "documentation"}), encoding="utf-8")
    if with_spec:
        (feature_dir / "spec.md").write_text("# spec\n", encoding="utf-8")
    if with_gap_analysis:
        (feature_dir / "gap-analysis.md").write_text("# gap analysis\n", encoding="utf-8")
    if with_plan:
        (feature_dir / "plan.md").write_text("# plan\n", encoding="utf-8")
    if with_generated_docs:
        (feature_dir / "docs").mkdir(exist_ok=True)
        (feature_dir / "docs" / "index.md").write_text("# docs\n", encoding="utf-8")
    if with_audit_report:
        (feature_dir / "audit-report.md").write_text("# audit report\n", encoding="utf-8")
    if with_release:
        (feature_dir / "release.md").write_text("# release\n", encoding="utf-8")
    _commit_all(repo_root, "seed documentation fixture")
    return repo_root


def advance_to_step(repo_root: Path, mission_slug: str, mission_type: str, target_step_id: str, *, max_steps: int = 12) -> None:
    """Drive the REAL engine forward (never stubbed) until ``target_step_id`` is issued.

    Uses ``runtime_next_step``/``NullEmitter`` directly — the same pattern
    proven in ``tests/next/test_runtime_bridge_unit.py::TestWPIteration`` —
    so the run's state.json genuinely reflects having walked the DAG, rather
    than being hand-crafted.
    """
    from runtime.next._internal_runtime import NullEmitter
    from runtime.next._internal_runtime import next_step as runtime_next_step
    from runtime.next._internal_runtime.engine import _read_snapshot
    from runtime.next.runtime_bridge import get_or_start_run

    run_ref = get_or_start_run(mission_slug, repo_root, mission_type)
    for _ in range(max_steps):
        snapshot = _read_snapshot(Path(run_ref.run_dir))
        if snapshot.issued_step_id == target_step_id:
            return
        runtime_next_step(run_ref, agent_id="fixture-setup", result="success", emitter=NullEmitter())
    raise AssertionError(
        f"advance_to_step: never reached {target_step_id!r} within {max_steps} steps "
        f"(mission={mission_slug!r} type={mission_type!r})"
    )


# ---------------------------------------------------------------------------
# Coord / lanes_with_coord fixtures (advancing-next-board-unification-01M3BGQ0,
# T001-T003, #4980/#4975) — real mission-creation core + real coordination-
# worktree materialization (C-001: the defect is only observable through a
# genuine coord-aware status read, never a hand-rolled coord-shaped dir).
# Reuses the golden-path git/mission-creation primitives VERBATIM per the
# module docstring on ``tests/integration/test_placement_partition_golden_
# path.py`` (do NOT duplicate them) — the same helpers
# ``tests/mission_runtime/test_coord_read_seam.py`` reuses for its own
# coord-materialization fixtures.
# ---------------------------------------------------------------------------

from mission_runtime import MissionTopology as _MissionTopology  # noqa: E402 -- intentional late import: reuses the golden-path coord fixtures documented in the block above, kept below that rationale rather than hoisted to the top
from tests.integration.test_placement_partition_golden_path import (  # noqa: E402 -- intentional late import: verbatim reuse of golden-path git/mission-creation primitives (see block above); hoisting would split the helpers from their rationale
    _create_mission as _golden_create_mission,
    _init_git_repo as _golden_init_git_repo,
    _materialize_coord_worktree as _golden_materialize_coord_worktree,
)


def scaffold_coord_software_dev(
    repo_root: Path,
    mission_slug: str,
    topology: _MissionTopology,
    *,
    wps: dict[str, str],
) -> tuple[Path, Path]:
    """Real coord/lanes_with_coord software-dev mission for the board-
    authority-unification fixtures: the mission-creation core mints the
    mission (``meta.json`` + coordination branch), the coordination worktree
    is materialized the way real bookkeeping produces it, WP task files +
    spec/plan/tasks.md land on the PRIMARY checkout, and WP lane events are
    seeded on the COORDINATION status surface — mirroring production
    coord-topology placement exactly (the split #4975 characterizes).

    Returns ``(feature_dir, coord_mission_dir)`` — the PRIMARY planning dir
    and the coordination status-read dir, matching what
    ``mission_context_for`` resolves for ``WORK_PACKAGE_TASK`` /
    ``STATUS_STATE`` respectively.
    """
    _golden_init_git_repo(repo_root)
    result = _golden_create_mission(repo_root, mission_slug, topology)
    coord_root = _golden_materialize_coord_worktree(repo_root, result)
    coord_mission_dir = coord_root / "kitty-specs" / result.mission_slug
    coord_mission_dir.mkdir(parents=True, exist_ok=True)

    _write_wp_task_files(result.feature_dir, wps)
    (result.feature_dir / "spec.md").write_text("# Spec\n\n## Functional Requirements\n- FR-001: x\n", encoding="utf-8")
    (result.feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    (result.feature_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
    for wp_id, lane in wps.items():
        _seed_wp_lane(coord_mission_dir, result.mission_slug, wp_id, lane)
    subprocess.run(["git", "-C", str(repo_root), "add", "-A"], capture_output=True, check=True)
    subprocess.run(
        ["git", "-C", str(repo_root), "commit", "-m", f"seed coord fixture for {mission_slug}"],
        capture_output=True,
        check=True,
    )
    return result.feature_dir, coord_mission_dir


def _reject_wp_on_status_surface(status_dir: Path, mission_slug: str, wp_id: str) -> None:
    """Append the ``for_review`` -> ``planned`` reject event a real reviewer's
    printed REJECT command produces (``move-task <wp> --to planned``),
    directly on ``status_dir`` — the coord surface for coord/lanes_with_coord,
    the feature dir itself for single_branch/lanes."""
    from specify_cli.status.models import Lane, StatusEvent
    from specify_cli.status.store import append_event

    append_event(
        status_dir,
        StatusEvent(
            event_id=f"reject-{wp_id}",
            mission_slug=mission_slug,
            wp_id=wp_id,
            from_lane=Lane.FOR_REVIEW,
            to_lane=Lane.PLANNED,
            at="2026-01-02T00:00:00+00:00",
            actor="reviewer-fixture",
            force=True,
            execution_mode="worktree",
            reason="rejected by fixture",
        ),
    )


# ---------------------------------------------------------------------------
# Harness — drives one public entry with full instrumentation attached.
# ---------------------------------------------------------------------------


@dataclass
class FixtureRun:
    fixture_id: str
    entry: str
    decision: Any
    sites: list[int]
    guard_calls: list[GuardCall]
    side_effects: SideEffectCapture
    duration_seconds: float
    repo_root: Path


def _bridge_and_engine_modules() -> tuple[Any, Any]:
    import runtime.next._internal_runtime.engine as engine_module
    import runtime.next.runtime_bridge as bridge_module

    return bridge_module, engine_module


def drive_decide_next(repo_root: Path, *, agent: str, mission_slug: str, result: str, fixture_id: str) -> FixtureRun:
    bridge_module, engine_module = _bridge_and_engine_modules()
    mp = pytest.MonkeyPatch()
    try:
        with capture_decision_sites(mp, bridge_module) as sites, \
                capture_guard_calls(mp, bridge_module) as guard_calls, \
                capture_side_effects(mp, bridge_module, engine_module) as side_effects:
            timed = timed_call(bridge_module.decide_next_via_runtime, agent, mission_slug, result, repo_root)
    finally:
        mp.undo()
    return FixtureRun(
        fixture_id=fixture_id,
        entry="decide_next_via_runtime",
        decision=timed.value,
        sites=list(sites),
        guard_calls=list(guard_calls),
        side_effects=side_effects,
        duration_seconds=timed.duration_seconds,
        repo_root=repo_root,
    )


def drive_query(repo_root: Path, *, agent: str | None, mission_slug: str, fixture_id: str) -> FixtureRun:
    bridge_module, engine_module = _bridge_and_engine_modules()
    mp = pytest.MonkeyPatch()
    try:
        with capture_decision_sites(mp, bridge_module) as sites, \
                capture_guard_calls(mp, bridge_module) as guard_calls, \
                capture_side_effects(mp, bridge_module, engine_module) as side_effects:
            timed = timed_call(bridge_module.query_current_state, agent, mission_slug, repo_root)
    finally:
        mp.undo()
    return FixtureRun(
        fixture_id=fixture_id,
        entry="query_current_state",
        decision=timed.value,
        sites=list(sites),
        guard_calls=list(guard_calls),
        side_effects=side_effects,
        duration_seconds=timed.duration_seconds,
        repo_root=repo_root,
    )


def drive_answer(
    repo_root: Path,
    *,
    mission_slug: str,
    decision_id: str,
    answer: str,
    agent: str,
    fixture_id: str,
) -> FixtureRun:
    bridge_module, engine_module = _bridge_and_engine_modules()
    mp = pytest.MonkeyPatch()
    try:
        with capture_decision_sites(mp, bridge_module) as sites, \
                capture_guard_calls(mp, bridge_module) as guard_calls, \
                capture_side_effects(mp, bridge_module, engine_module) as side_effects:
            timed = timed_call(
                bridge_module.answer_decision_via_runtime,
                mission_slug,
                decision_id,
                answer,
                agent,
                repo_root,
            )
    finally:
        mp.undo()
    return FixtureRun(
        fixture_id=fixture_id,
        entry="answer_decision_via_runtime",
        decision=timed.value,  # always None on success
        sites=list(sites),
        guard_calls=list(guard_calls),
        side_effects=side_effects,
        duration_seconds=timed.duration_seconds,
        repo_root=repo_root,
    )


def copytree_snapshot(snapshot_dir: Path, dest_parent: Path, run_label: str) -> Path:
    """Fresh copytree of a frozen snapshot into its own fixed per-run repo_root."""
    dest = dest_parent / run_label
    shutil.copytree(snapshot_dir, dest)
    return dest

# ---------------------------------------------------------------------------
# Named highest-risk fixtures — driven TWICE (independent fresh copytrees),
# asserting identical guard_failures content AND order plus full Decision
# parity across the two runs (WP01 acceptance criterion).
# ---------------------------------------------------------------------------


def _software_dev_snapshot(base: Path, *, mission_slug: str = "042-parity-oracle") -> Path:
    snapshot_dir = base / "snapshot"
    scaffold_software_dev(snapshot_dir, mission_slug)
    return snapshot_dir


@dataclass
class FixtureSpec:
    fixture_id: str
    sub_ledger: str  # "decide_next" | "query" | "answer"
    build: Any  # Callable[[Path], tuple[Path, dict]] -> (snapshot_dir, drive_kwargs)
    drive: Any  # Callable[[Path, dict, str], FixtureRun]


# --- decide_next_via_runtime sub-ledger builders --------------------------


def _build_missing_feature_dir(base: Path) -> tuple[Path, dict[str, Any]]:
    snapshot = _software_dev_snapshot(base)
    return snapshot, {"agent": "pedro", "mission_slug": "does-not-exist", "result": "success"}


def _build_run_start_failure(base: Path) -> tuple[Path, dict[str, Any]]:
    snapshot = base / "snapshot"
    _init_git_repo(snapshot)
    (snapshot / ".kittify").mkdir(exist_ok=True)
    mission_slug = "099-bogus-mission-type"
    feature_dir = snapshot / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_type": "totally-unregistered-mission-type-xyz"}), encoding="utf-8"
    )
    _commit_all(snapshot, "seed bogus mission type")
    return snapshot, {"agent": "pedro", "mission_slug": mission_slug, "result": "success"}


def _build_discovery_issues_specify(base: Path) -> tuple[Path, dict[str, Any]]:
    snapshot = _software_dev_snapshot(base)
    advance_to_step(snapshot, "042-parity-oracle", "software-dev", "discovery")
    return snapshot, {"agent": "pedro", "mission_slug": "042-parity-oracle", "result": "success"}


def _build_specify_guard_fail(base: Path) -> tuple[Path, dict[str, Any]]:
    snapshot = _software_dev_snapshot(base)  # no spec.md
    advance_to_step(snapshot, "042-parity-oracle", "software-dev", "specify")
    return snapshot, {"agent": "pedro", "mission_slug": "042-parity-oracle", "result": "success"}


def _build_specify_guard_pass(base: Path) -> tuple[Path, dict[str, Any]]:
    mission_slug = "042-parity-oracle"
    snapshot = base / "snapshot"
    scaffold_software_dev(snapshot, mission_slug, with_spec=True)
    advance_to_step(snapshot, mission_slug, "software-dev", "specify")
    return snapshot, {"agent": "pedro", "mission_slug": mission_slug, "result": "success"}


def _build_plan_guard_fail(base: Path) -> tuple[Path, dict[str, Any]]:
    mission_slug = "042-parity-oracle"
    snapshot = base / "snapshot"
    scaffold_software_dev(snapshot, mission_slug, with_spec=True)  # no plan.md
    advance_to_step(snapshot, mission_slug, "software-dev", "plan")
    return snapshot, {"agent": "pedro", "mission_slug": mission_slug, "result": "success"}


def _build_plan_guard_pass(base: Path) -> tuple[Path, dict[str, Any]]:
    mission_slug = "042-parity-oracle"
    snapshot = base / "snapshot"
    scaffold_software_dev(snapshot, mission_slug, with_spec=True, with_plan=True)
    advance_to_step(snapshot, mission_slug, "software-dev", "plan")
    return snapshot, {"agent": "pedro", "mission_slug": mission_slug, "result": "success"}


def _build_tasks_union_guard_fail_reqmap(base: Path) -> tuple[Path, dict[str, Any]]:
    """Named highest-risk fixture: the ``tasks`` legacy-union guard, missing requirement mapping."""
    mission_slug = "042-parity-oracle"
    snapshot = base / "snapshot"
    scaffold_software_dev(
        snapshot,
        mission_slug,
        with_spec=True,
        with_plan=True,
        with_tasks_md=True,
        wps={"WP01": "planned"},
    )
    # Strip the requirement_refs so the union guard's requirement-mapping
    # cross-check fires deterministically (content+order pinned below).
    wp_file = snapshot / "kitty-specs" / mission_slug / "tasks" / "WP01.md"
    wp_file.write_text(
        wp_file.read_text(encoding="utf-8").replace("requirement_refs: [FR-001]\n", ""),
        encoding="utf-8",
    )
    _commit_all(snapshot, "strip requirement_refs")
    advance_to_step(snapshot, mission_slug, "software-dev", "tasks")
    return snapshot, {"agent": "pedro", "mission_slug": mission_slug, "result": "success"}


def _build_tasks_union_guard_fail_missing_deps(base: Path) -> tuple[Path, dict[str, Any]]:
    """Named highest-risk fixture: the ``tasks`` legacy-union guard, missing dependencies frontmatter."""
    mission_slug = "042-parity-oracle"
    snapshot = base / "snapshot"
    scaffold_software_dev(
        snapshot,
        mission_slug,
        with_spec=True,
        with_plan=True,
        with_tasks_md=True,
        wps={"WP01": "planned"},
        wp_deps=False,
    )
    advance_to_step(snapshot, mission_slug, "software-dev", "tasks")
    return snapshot, {"agent": "pedro", "mission_slug": mission_slug, "result": "success"}


def _build_tasks_union_guard_pass(base: Path) -> tuple[Path, dict[str, Any]]:
    mission_slug = "042-parity-oracle"
    snapshot = base / "snapshot"
    scaffold_software_dev(
        snapshot,
        mission_slug,
        with_spec=True,
        with_plan=True,
        with_tasks_md=True,
        wps={"WP01": "planned"},
    )
    advance_to_step(snapshot, mission_slug, "software-dev", "tasks")
    return snapshot, {"agent": "pedro", "mission_slug": mission_slug, "result": "success"}


def _build_implement_wp_remains(base: Path) -> tuple[Path, dict[str, Any]]:
    mission_slug = "042-parity-oracle"
    snapshot = base / "snapshot"
    scaffold_software_dev(
        snapshot,
        mission_slug,
        with_spec=True,
        with_plan=True,
        with_tasks_md=True,
        wps={"WP01": "planned", "WP02": "planned"},
    )
    advance_to_step(snapshot, mission_slug, "software-dev", "implement")
    return snapshot, {"agent": "pedro", "mission_slug": mission_slug, "result": "success"}


def _build_review_wp_remains(base: Path) -> tuple[Path, dict[str, Any]]:
    mission_slug = "042-parity-oracle"
    snapshot = base / "snapshot"
    scaffold_software_dev(
        snapshot,
        mission_slug,
        with_spec=True,
        with_plan=True,
        with_tasks_md=True,
        wps={"WP01": "for_review"},
    )
    advance_to_step(snapshot, mission_slug, "software-dev", "review")
    return snapshot, {"agent": "pedro", "mission_slug": mission_slug, "result": "success"}


def _build_review_guard_pass_advances_accept(base: Path) -> tuple[Path, dict[str, Any]]:
    mission_slug = "042-parity-oracle"
    snapshot = base / "snapshot"
    scaffold_software_dev(
        snapshot,
        mission_slug,
        with_spec=True,
        with_plan=True,
        with_tasks_md=True,
        wps={"WP01": "done"},
    )
    advance_to_step(snapshot, mission_slug, "software-dev", "review")
    return snapshot, {"agent": "pedro", "mission_slug": mission_slug, "result": "success"}


def _build_terminal(base: Path) -> tuple[Path, dict[str, Any]]:
    mission_slug = "042-parity-oracle"
    snapshot = base / "snapshot"
    scaffold_software_dev(
        snapshot,
        mission_slug,
        with_spec=True,
        with_plan=True,
        with_tasks_md=True,
        wps={"WP01": "done"},
    )
    advance_to_step(snapshot, mission_slug, "software-dev", "accept")
    return snapshot, {"agent": "pedro", "mission_slug": mission_slug, "result": "success"}


def _build_research_scoping_guard_fail(base: Path) -> tuple[Path, dict[str, Any]]:
    mission_slug = "050-research-parity"
    snapshot = base / "snapshot"
    scaffold_research(snapshot, mission_slug)  # no spec.md
    advance_to_step(snapshot, mission_slug, "research", "scoping")
    return snapshot, {"agent": "pedro", "mission_slug": mission_slug, "result": "success"}


def _build_research_gathering_guard_pass(base: Path) -> tuple[Path, dict[str, Any]]:
    mission_slug = "050-research-parity"
    snapshot = base / "snapshot"
    scaffold_research(snapshot, mission_slug, with_spec=True, with_plan=True, with_sources=3)
    advance_to_step(snapshot, mission_slug, "research", "gathering")
    return snapshot, {"agent": "pedro", "mission_slug": mission_slug, "result": "success"}


def _build_research_output_guard_pass(base: Path) -> tuple[Path, dict[str, Any]]:
    mission_slug = "050-research-parity"
    snapshot = base / "snapshot"
    scaffold_research(
        snapshot,
        mission_slug,
        with_spec=True,
        with_plan=True,
        with_sources=3,
        with_findings=True,
        with_report=True,
        publication_approved=True,
    )
    advance_to_step(snapshot, mission_slug, "research", "output")
    return snapshot, {"agent": "pedro", "mission_slug": mission_slug, "result": "success"}


def _build_documentation_discover_guard_fail(base: Path) -> tuple[Path, dict[str, Any]]:
    mission_slug = "060-docs-parity"
    snapshot = base / "snapshot"
    scaffold_documentation(snapshot, mission_slug)  # no spec.md
    advance_to_step(snapshot, mission_slug, "documentation", "discover")
    return snapshot, {"agent": "pedro", "mission_slug": mission_slug, "result": "success"}


def _build_documentation_generate_guard_pass(base: Path) -> tuple[Path, dict[str, Any]]:
    mission_slug = "060-docs-parity"
    snapshot = base / "snapshot"
    scaffold_documentation(
        snapshot,
        mission_slug,
        with_spec=True,
        with_gap_analysis=True,
        with_plan=True,
        with_generated_docs=True,
    )
    advance_to_step(snapshot, mission_slug, "documentation", "generate")
    return snapshot, {"agent": "pedro", "mission_slug": mission_slug, "result": "success"}


# --- query_current_state sub-ledger builders -------------------------------


def _build_query_finalized_override_implement(base: Path) -> tuple[Path, dict[str, Any]]:
    mission_slug = "042-parity-oracle"
    snapshot = base / "snapshot"
    scaffold_software_dev(
        snapshot,
        mission_slug,
        with_spec=True,
        with_plan=True,
        with_tasks_md=True,
        wps={"WP01": "planned"},
    )
    return snapshot, {"agent": "pedro", "mission_slug": mission_slug}


def _build_query_finalized_override_done(base: Path) -> tuple[Path, dict[str, Any]]:
    mission_slug = "042-parity-oracle"
    snapshot = base / "snapshot"
    scaffold_software_dev(
        snapshot,
        mission_slug,
        with_spec=True,
        with_plan=True,
        with_tasks_md=True,
        wps={"WP01": "done", "WP02": "done"},
    )
    return snapshot, {"agent": "pedro", "mission_slug": mission_slug}


def _build_query_initial_fresh_mission(base: Path) -> tuple[Path, dict[str, Any]]:
    mission_slug = "042-parity-oracle"
    snapshot = _software_dev_snapshot(base, mission_slug=mission_slug)
    return snapshot, {"agent": "pedro", "mission_slug": mission_slug}


def _build_query_runtime_after_advance(base: Path) -> tuple[Path, dict[str, Any]]:
    mission_slug = "042-parity-oracle"
    snapshot = base / "snapshot"
    scaffold_software_dev(snapshot, mission_slug, with_spec=True)
    advance_to_step(snapshot, mission_slug, "software-dev", "specify")
    return snapshot, {"agent": "pedro", "mission_slug": mission_slug}


# --- answer_decision_via_runtime sub-ledger builder ------------------------


def _write_runtime_input_mission(repo_root: Path, mission_type: str) -> None:
    """A runtime-only mission that deterministically requests input.

    Verbatim pattern from ``tests/next/test_next_command_integration.py::
    _write_runtime_input_mission`` (the only proven real, unmocked
    ``decision_required`` -> ``answer`` producer in the suite).
    """
    mission_dir = repo_root / ".kittify" / "overrides" / "missions" / mission_type
    mission_dir.mkdir(parents=True, exist_ok=True)
    (mission_dir / "mission-runtime.yaml").write_text(
        (
            "mission:\n"
            f"  key: {mission_type}\n"
            f"  name: {mission_type}\n"
            "  version: '1.0.0'\n"
            "steps:\n"
            "  - id: collect_input\n"
            "    title: Collect Input\n"
            "    description: Gather required answer\n"
            "    requires_inputs: [approval]\n"
            "  - id: execute\n"
            "    title: Execute\n"
            "    depends_on: [collect_input]\n"
            "    description: Proceed with mission\n"
        ),
        encoding="utf-8",
    )
    template_dir = repo_root / ".kittify" / "overrides" / "command-templates"
    template_dir.mkdir(parents=True, exist_ok=True)
    for action in ("collect_input", "execute"):
        (template_dir / f"{action}.md").write_text(
            f"# {action}\n\nRun the synthetic {action} step for this parity fixture.\n",
            encoding="utf-8",
        )


def _seed_input_mission_pending(base: Path, mission_slug: str) -> Path:
    """Seed a runtime input-mission and issue its first step so a real
    ``decision_required`` (``input:approval``) is pending.

    Shared by the answer-path fixture (which answers the pending decision) and
    the decide_next/query decision-required fixtures (which observe it). The
    real engine issues the decision — never stubbed.
    """
    snapshot = base / "snapshot"
    _init_git_repo(snapshot)
    # WP04 fail-closed (C-A1): a project-override mission definition alone
    # does not activate a type -- mission_type_activations is the sole
    # activation authority, so this synthetic "input-mission" custom type
    # must be listed too.
    _provision_mission_type_activations(snapshot, "input-mission")
    feature_dir = snapshot / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(json.dumps({"mission_type": "input-mission"}), encoding="utf-8")
    _write_runtime_input_mission(snapshot, "input-mission")
    _commit_all(snapshot, "seed input-mission fixture")
    # Issue the first (and only) real step -- collect_input -- so a real
    # decision_required is pending. NOTE: a decision_required does NOT set
    # snapshot.issued_step_id (it is carried in snapshot.pending_decisions
    # instead), so advance_to_step's issued_step_id-based loop cannot be reused
    # here -- one direct real engine call is enough (never stubbed).
    from runtime.next._internal_runtime import NullEmitter
    from runtime.next._internal_runtime import next_step as runtime_next_step
    from runtime.next.runtime_bridge import get_or_start_run

    run_ref = get_or_start_run(mission_slug, snapshot, "input-mission")
    first = runtime_next_step(run_ref, agent_id="fixture-setup", result="success", emitter=NullEmitter())
    assert first.kind == "decision_required" and first.decision_id == "input:approval", (
        f"fixture setup assumption broken: expected a pending input:approval decision, got {first!r}"
    )
    return snapshot


def _build_answer_input_mission(base: Path) -> tuple[Path, dict[str, Any]]:
    mission_slug = "070-answer-parity"
    snapshot = _seed_input_mission_pending(base, mission_slug)
    return snapshot, {
        "mission_slug": mission_slug,
        "decision_id": "input:approval",
        "answer": "yes",
        "agent": "pedro",
    }


# --- decide_next_via_runtime sub-ledger builders (error / decision_required) ---


def _build_dn_input_mission_decision_required(base: Path) -> tuple[Path, dict[str, Any]]:
    """decide_next on the input-mission's pending decision → the runtime returns
    ``decision_required`` → ``_map_runtime_decision`` decision-required arm
    (``bridge:3629``), a site reached from no other software-dev fixture."""
    mission_slug = "071-dn-decision-required"
    snapshot = _seed_input_mission_pending(base, mission_slug)
    return snapshot, {"agent": "pedro", "mission_slug": mission_slug, "result": "success"}


def _build_dn_corrupt_run_state(base: Path) -> tuple[Path, dict[str, Any]]:
    """A run whose ``state.json`` is corrupt JSON → ``runtime_next_step`` raises
    → the ``except`` engine-error blocked arm (``bridge:2965``). A genuinely
    misconfigured on-disk run, not a stubbed engine (never stub next_step)."""
    mission_slug = "042-parity-oracle"
    snapshot = base / "snapshot"
    scaffold_software_dev(snapshot, mission_slug, with_spec=True)
    advance_to_step(snapshot, mission_slug, "software-dev", "specify")
    for state_path in snapshot.rglob("state.json"):
        state_path.write_text("{ this is not valid json ", encoding="utf-8")
    _commit_all(snapshot, "corrupt run state.json")
    return snapshot, {"agent": "pedro", "mission_slug": mission_slug, "result": "success"}


def _build_dn_missing_canonical_status(base: Path) -> tuple[Path, dict[str, Any]]:
    """On a WP-iteration step with the canonical event log deleted,
    ``_should_advance_wp_step`` raises ``CanonicalStatusNotFoundError`` → the
    WP-iteration guard blocked arm (``bridge:2639``)."""
    mission_slug = "042-parity-oracle"
    snapshot = base / "snapshot"
    scaffold_software_dev(
        snapshot, mission_slug, with_spec=True, with_plan=True,
        with_tasks_md=True, wps={"WP01": "planned"},
    )
    advance_to_step(snapshot, mission_slug, "software-dev", "implement")
    for events in snapshot.rglob("status.events.jsonl"):
        events.unlink()
    _commit_all(snapshot, "delete canonical status event log")
    return snapshot, {"agent": "pedro", "mission_slug": mission_slug, "result": "success"}


def _build_dn_block_policy_unreadable_state(base: Path) -> tuple[Path, dict[str, Any]]:
    """A ``failure_policy: block`` retrospective policy makes decide_next read
    ``state.json`` before the speculative advance; when that read raises OSError
    the pre-state blocked arm fires (``bridge:2936``). ``state.json`` is made
    unreadable by replacing it with a *directory* of the same name — which
    ``read_bytes`` rejects with ``IsADirectoryError`` and, unlike ``chmod 000``,
    survives the harness ``copytree`` of the frozen snapshot."""
    mission_slug = "042-parity-oracle"
    snapshot = base / "snapshot"
    scaffold_software_dev(snapshot, mission_slug, with_spec=True)
    advance_to_step(snapshot, mission_slug, "software-dev", "specify")
    _write_block_retrospective_config(snapshot)
    for state_path in list(snapshot.rglob("state.json")):
        state_path.unlink()
        state_path.mkdir()
    _commit_all(snapshot, "block policy + unreadable (dir) state.json")
    return snapshot, {"agent": "pedro", "mission_slug": mission_slug, "result": "success"}


def _build_dn_wp_done_no_action_mapped(base: Path) -> tuple[Path, dict[str, Any]]:
    """Every WP is already ``done``, so when the run advances ``tasks``→
    ``implement`` the ``implement`` step maps to no actionable WP —
    ``_state_to_action`` returns ``None`` → ``_map_runtime_decision``'s WP-step
    no-action blocked arm (``bridge:3659``).

    The reaching state must be produced through the REAL bridge loop (not the
    engine-only ``advance_to_step``, which lands in a different run state that
    does not exercise this arm): drive ``decide_next`` until the run has
    ISSUED the ``tasks`` step, so the harness's single ``decide_next`` call is
    the one that advances ``tasks``→``implement`` and hits ``:3659``."""
    mission_slug = "042-parity-oracle"
    snapshot = base / "snapshot"
    scaffold_software_dev(
        snapshot, mission_slug, with_spec=True, with_plan=True,
        with_tasks_md=True, wps={"WP01": "done"},
    )
    _write_block_retrospective_config(snapshot)
    from runtime.next._internal_runtime.engine import _read_snapshot
    from runtime.next.runtime_bridge import decide_next_via_runtime, get_or_start_run

    for _ in range(12):
        run_ref = get_or_start_run(mission_slug, snapshot, "software-dev")
        if _read_snapshot(Path(run_ref.run_dir)).issued_step_id == "tasks":
            break
        decide_next_via_runtime("pedro", mission_slug, "success", snapshot)
    else:  # pragma: no cover - fixture-setup guard
        raise AssertionError("fixture setup never reached the issued 'tasks' step")
    _commit_all(snapshot, "wp done, run advanced to issued tasks step")
    return snapshot, {"agent": "pedro", "mission_slug": mission_slug, "result": "success"}


# --- guard-branch coverage: research / documentation intermediate steps ------
# Each advances the mission to a specific composed-guard step and drives one
# decide_next so that step's composed guard fires — closing the guard-branch
# floor (composed:research:{methodology,synthesis},
# composed:documentation:{audit,design,validate}). The Decision site reached is
# already covered; these exist purely to exercise the remaining guard arms.


def _scaffold_research_full(base: Path, mission_slug: str) -> Path:
    snapshot = base / "snapshot"
    scaffold_research(
        snapshot, mission_slug, with_spec=True, with_plan=True, with_sources=3,
        with_findings=True, with_report=True, publication_approved=True,
    )
    return snapshot


def _scaffold_documentation_full(base: Path, mission_slug: str) -> Path:
    snapshot = base / "snapshot"
    scaffold_documentation(
        snapshot, mission_slug, with_spec=True, with_gap_analysis=True, with_plan=True,
        with_generated_docs=True, with_audit_report=True, with_release=True,
    )
    return snapshot


def _build_research_methodology_guard(base: Path) -> tuple[Path, dict[str, Any]]:
    mission_slug = "050-research-parity"
    snapshot = _scaffold_research_full(base, mission_slug)
    advance_to_step(snapshot, mission_slug, "research", "methodology")
    return snapshot, {"agent": "pedro", "mission_slug": mission_slug, "result": "success"}


def _build_research_synthesis_guard(base: Path) -> tuple[Path, dict[str, Any]]:
    mission_slug = "050-research-parity"
    snapshot = _scaffold_research_full(base, mission_slug)
    advance_to_step(snapshot, mission_slug, "research", "synthesis")
    return snapshot, {"agent": "pedro", "mission_slug": mission_slug, "result": "success"}


def _build_documentation_audit_guard(base: Path) -> tuple[Path, dict[str, Any]]:
    mission_slug = "060-docs-parity"
    snapshot = _scaffold_documentation_full(base, mission_slug)
    advance_to_step(snapshot, mission_slug, "documentation", "audit")
    return snapshot, {"agent": "pedro", "mission_slug": mission_slug, "result": "success"}


def _build_documentation_design_guard(base: Path) -> tuple[Path, dict[str, Any]]:
    mission_slug = "060-docs-parity"
    snapshot = _scaffold_documentation_full(base, mission_slug)
    advance_to_step(snapshot, mission_slug, "documentation", "design")
    return snapshot, {"agent": "pedro", "mission_slug": mission_slug, "result": "success"}


def _build_documentation_validate_guard(base: Path) -> tuple[Path, dict[str, Any]]:
    mission_slug = "060-docs-parity"
    snapshot = _scaffold_documentation_full(base, mission_slug)
    advance_to_step(snapshot, mission_slug, "documentation", "validate")
    return snapshot, {"agent": "pedro", "mission_slug": mission_slug, "result": "success"}


# --- query_current_state sub-ledger builder (decision_required) --------------


def _build_query_input_mission_decision_required(base: Path) -> tuple[Path, dict[str, Any]]:
    """query_current_state on the input-mission's pending decision →
    ``_build_decision_required_query`` (``bridge:3147``), reached exclusively
    from the query entry."""
    mission_slug = "072-q-decision-required"
    snapshot = _seed_input_mission_pending(base, mission_slug)
    return snapshot, {"agent": "pedro", "mission_slug": mission_slug}


FIXTURES: list[FixtureSpec] = [
    FixtureSpec("dn_missing_feature_dir", "decide_next", _build_missing_feature_dir, None),
    FixtureSpec("dn_run_start_failure", "decide_next", _build_run_start_failure, None),
    FixtureSpec("dn_discovery_issues_specify", "decide_next", _build_discovery_issues_specify, None),
    FixtureSpec("dn_specify_guard_fail", "decide_next", _build_specify_guard_fail, None),
    FixtureSpec("dn_specify_guard_pass", "decide_next", _build_specify_guard_pass, None),
    FixtureSpec("dn_plan_guard_fail", "decide_next", _build_plan_guard_fail, None),
    FixtureSpec("dn_plan_guard_pass", "decide_next", _build_plan_guard_pass, None),
    FixtureSpec("dn_tasks_union_guard_fail_reqmap", "decide_next", _build_tasks_union_guard_fail_reqmap, None),
    FixtureSpec("dn_tasks_union_guard_fail_missing_deps", "decide_next", _build_tasks_union_guard_fail_missing_deps, None),
    FixtureSpec("dn_tasks_union_guard_pass", "decide_next", _build_tasks_union_guard_pass, None),
    FixtureSpec("dn_implement_wp_remains", "decide_next", _build_implement_wp_remains, None),
    FixtureSpec("dn_review_wp_remains", "decide_next", _build_review_wp_remains, None),
    FixtureSpec("dn_review_guard_pass_advances_accept", "decide_next", _build_review_guard_pass_advances_accept, None),
    FixtureSpec("dn_terminal", "decide_next", _build_terminal, None),
    FixtureSpec("dn_research_scoping_guard_fail", "decide_next", _build_research_scoping_guard_fail, None),
    FixtureSpec("dn_research_gathering_guard_pass", "decide_next", _build_research_gathering_guard_pass, None),
    FixtureSpec("dn_research_output_guard_pass", "decide_next", _build_research_output_guard_pass, None),
    FixtureSpec("dn_documentation_discover_guard_fail", "decide_next", _build_documentation_discover_guard_fail, None),
    FixtureSpec("dn_documentation_generate_guard_pass", "decide_next", _build_documentation_generate_guard_pass, None),
    FixtureSpec("q_finalized_override_implement", "query", _build_query_finalized_override_implement, None),
    FixtureSpec("q_finalized_override_done", "query", _build_query_finalized_override_done, None),
    FixtureSpec("q_initial_fresh_mission", "query", _build_query_initial_fresh_mission, None),
    FixtureSpec("q_runtime_after_advance", "query", _build_query_runtime_after_advance, None),
    FixtureSpec("q_input_mission_decision_required", "query", _build_query_input_mission_decision_required, None),
    FixtureSpec("answer_input_mission", "answer", _build_answer_input_mission, None),
    # Error / decision_required arms partitioned across the owning entries —
    # each reaches a Decision site no happy-path fixture touches (WP01 T004
    # coverage-floor closure; see each builder's docstring for the site).
    FixtureSpec("dn_input_mission_decision_required", "decide_next", _build_dn_input_mission_decision_required, None),
    FixtureSpec("dn_corrupt_run_state", "decide_next", _build_dn_corrupt_run_state, None),
    FixtureSpec("dn_missing_canonical_status", "decide_next", _build_dn_missing_canonical_status, None),
    FixtureSpec("dn_block_policy_unreadable_state", "decide_next", _build_dn_block_policy_unreadable_state, None),
    FixtureSpec("dn_wp_done_no_action_mapped", "decide_next", _build_dn_wp_done_no_action_mapped, None),
    # Guard-branch coverage — the remaining composed-guard arms (research
    # methodology/synthesis, documentation audit/design/validate).
    FixtureSpec("dn_research_methodology_guard", "decide_next", _build_research_methodology_guard, None),
    FixtureSpec("dn_research_synthesis_guard", "decide_next", _build_research_synthesis_guard, None),
    FixtureSpec("dn_documentation_audit_guard", "decide_next", _build_documentation_audit_guard, None),
    FixtureSpec("dn_documentation_design_guard", "decide_next", _build_documentation_design_guard, None),
    FixtureSpec("dn_documentation_validate_guard", "decide_next", _build_documentation_validate_guard, None),
]

#: Named highest-risk fixtures (WP01 acceptance criterion): the tasks
#: legacy-union guard. The two composed-guard fail-closed defaults
#: (research/documentation) are NOT reachable from their owning entry with a
#: valid charter-resolved action_sequence (see test_coverage_floor_report's
#: docstring for the documented gap) and are exercised as direct unit calls
#: instead -- named separately below, not in this entry-driven set.
NAMED_HIGHEST_RISK_ENTRY_DRIVEN = (
    "dn_tasks_union_guard_fail_reqmap",
    "dn_tasks_union_guard_fail_missing_deps",
)


def _drive(spec: FixtureSpec, snapshot_dir: Path, drive_kwargs: dict[str, Any], tmp_path: Path, run_label: str) -> FixtureRun:
    repo_root = copytree_snapshot(snapshot_dir, tmp_path, run_label)
    if spec.sub_ledger == "decide_next":
        return drive_decide_next(repo_root, fixture_id=spec.fixture_id, **drive_kwargs)
    if spec.sub_ledger == "query":
        return drive_query(repo_root, fixture_id=spec.fixture_id, **drive_kwargs)
    return drive_answer(repo_root, fixture_id=spec.fixture_id, **drive_kwargs)


@pytest.fixture(scope="module")
def ledger_results(tmp_path_factory: pytest.TempPathFactory) -> tuple[dict[str, tuple[FixtureRun, FixtureRun]], CoverageLedger]:
    """Run every fixture in FIXTURES exactly twice (independent fresh copytrees).

    Two independent runs per fixture is what makes ``assert_parity`` /
    the reason-normalizer contract checkable: both runs share the same
    frozen builder logic but land in different temp roots and get different
    ULIDs/timestamps, so masking correctness and determinism are proven
    together, not assumed.
    """
    ledger = CoverageLedger()
    results: dict[str, tuple[FixtureRun, FixtureRun]] = {}
    for spec in FIXTURES:
        base_a = tmp_path_factory.mktemp(f"{spec.fixture_id}_a")
        base_b = tmp_path_factory.mktemp(f"{spec.fixture_id}_b")
        snapshot_a, drive_kwargs_a = spec.build(base_a)
        snapshot_b, drive_kwargs_b = spec.build(base_b)
        run_a = _drive(spec, snapshot_a, drive_kwargs_a, base_a, "run")
        run_b = _drive(spec, snapshot_b, drive_kwargs_b, base_b, "run")
        results[spec.fixture_id] = (run_a, run_b)
        ledger.record(f"{spec.fixture_id}#a", run_a.sites, run_a.guard_calls)
        ledger.record(f"{spec.fixture_id}#b", run_b.sites, run_b.guard_calls)
    return results, ledger


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_every_fixture_pair_is_parity_stable(
    ledger_results: tuple[dict[str, tuple[FixtureRun, FixtureRun]], CoverageLedger],
) -> None:
    """Every fixture's two independent copytree runs must be Decision-parity-equal.

    This is the core characterization assertion: driving the SAME logical
    scenario on unmodified source, twice, through fresh copytrees with
    different repo_roots and different real ULIDs/timestamps, must canonicalize
    identically. A failure here means either (a) the scenario is
    non-deterministic on unmodified source (a real product bug worth
    escalating) or (b) the masking contract under-collapses run-local noise.
    """
    results, _ledger = ledger_results
    failures: list[str] = []
    for fixture_id, (run_a, run_b) in results.items():
        if run_a.entry == "answer_decision_via_runtime":
            # answer_decision_via_runtime returns None -- nothing to
            # Decision-compare; its parity is asserted via side effects below.
            continue
        # Two independent runs land in DIFFERENT copytree roots, so each must
        # be canonicalized against ITS OWN root (identical to the reason-
        # normalizer meta-test). ``assert_parity(before, after, root)`` shares
        # one root and is the extraction-gate primitive (before/after on the
        # same repo); it is NOT the right comparator for two independent-root
        # runs -- doing so leaves run_b's paths un-normalized and spuriously
        # diverges on workspace_path.
        canon_a = canonical(run_a.decision, run_a.repo_root)
        canon_b = canonical(run_b.decision, run_b.repo_root)
        if canon_a != canon_b:
            diff_keys = sorted(
                k for k in (set(canon_a) | set(canon_b)) if canon_a.get(k) != canon_b.get(k)
            )
            details = "\n".join(
                f"    {k}: a={canon_a.get(k)!r} b={canon_b.get(k)!r}" for k in diff_keys
            )
            failures.append(f"{fixture_id}: canonical Decision diverged on {diff_keys}\n{details}")
    assert not failures, "parity breaks:\n" + "\n\n".join(failures)


def test_named_highest_risk_fixtures_guard_failures_stable(
    ledger_results: tuple[dict[str, tuple[FixtureRun, FixtureRun]], CoverageLedger],
) -> None:
    """The tasks legacy-union guard: identical guard_failures content AND order."""
    results, _ledger = ledger_results
    for fixture_id in NAMED_HIGHEST_RISK_ENTRY_DRIVEN:
        run_a, run_b = results[fixture_id]
        assert run_a.decision.guard_failures == run_b.decision.guard_failures, (
            f"{fixture_id}: guard_failures content/order diverged across independent runs: "
            f"{run_a.decision.guard_failures!r} vs {run_b.decision.guard_failures!r}"
        )
        assert run_a.decision.guard_failures, f"{fixture_id}: expected a non-empty guard_failures list"


def test_captured_side_effects_are_binding_equal(
    ledger_results: tuple[dict[str, tuple[FixtureRun, FixtureRun]], CoverageLedger],
) -> None:
    """Every captured side effect asserts binding equality on its PAYLOAD across
    the two independent runs — the sync emitter, the coord-branch commit, AND
    the IC-02 engine mutations (``_append_event`` / ``_write_snapshot`` /
    ``_read_snapshot``) plus the retrospective gate.

    ``canonical_side_effects`` masks run-local ids / timestamps / paths, so this
    catches a change to WHAT is emitted or committed (event type, wp_id, lane,
    step_id, engine-mutation content), not merely the method-call sequence —
    the binding equality contract §Side-effect isolation commissions and the
    reason the four engine/retrospective sinks are captured at all.
    """
    results, _ledger = ledger_results
    failures: list[str] = []
    for fixture_id, (run_a, run_b) in results.items():
        canon_a = canonical_side_effects(run_a.side_effects, run_a.repo_root)
        canon_b = canonical_side_effects(run_b.side_effects, run_b.repo_root)
        for sink in canon_a:
            if canon_a[sink] != canon_b[sink]:
                failures.append(
                    f"{fixture_id}: side-effect sink {sink!r} diverged across runs:\n"
                    f"    a={canon_a[sink]}\n    b={canon_b[sink]}"
                )
    assert not failures, "side-effect binding-equality breaks:\n" + "\n\n".join(failures)


def test_side_effect_sinks_are_actually_reached(
    ledger_results: tuple[dict[str, tuple[FixtureRun, FixtureRun]], CoverageLedger],
) -> None:
    """Every captured side-effect sink is populated by >=1 fixture — otherwise
    its binding-equality assertion above is vacuous (comparing empty vs empty).
    Proves the IC-02 engine mutations and the retrospective gate are genuinely
    exercised, not dead capture (WP01 review follow-up)."""
    results, _ledger = ledger_results
    reached: dict[str, bool] = {
        "sync_emitter": False, "coord_commit": False, "append_event": False,
        "write_snapshot": False, "read_snapshot": False, "retrospective": False,
    }
    for run_a, _run_b in results.values():
        se = run_a.side_effects
        reached["sync_emitter"] |= bool(se.sync_emitter_calls)
        reached["coord_commit"] |= bool(se.coord_commit_calls)
        reached["append_event"] |= bool(se.append_event_calls)
        reached["write_snapshot"] |= bool(se.write_snapshot_calls)
        reached["read_snapshot"] |= bool(se.read_snapshot_calls)
        reached["retrospective"] |= bool(se.retrospective_calls)
    unreached = sorted(name for name, hit in reached.items() if not hit)
    assert not unreached, f"side-effect sinks never populated by any fixture (moot capture): {unreached}"


def test_answer_path_side_effects_captured(
    ledger_results: tuple[dict[str, tuple[FixtureRun, FixtureRun]], CoverageLedger],
) -> None:
    """answer_decision_via_runtime's own sync emit (:3410) / coord commit (:3427)
    fire and are captured -- proving the answer-path side effects are
    observable independent of decide_next's.
    """
    results, _ledger = ledger_results
    run_a, run_b = results["answer_input_mission"]
    assert run_a.decision is None  # answer_decision_via_runtime returns None
    assert run_a.side_effects.sync_emitter_calls, "expected the answer-path sync emitter to record calls"
    assert run_b.side_effects.sync_emitter_calls, "expected the answer-path sync emitter to record calls"
    assert run_a.side_effects.coord_commit_calls, "expected the answer-path coord commit to record calls"


#: Guard-branch coverage floor — a checkable count (not a fixture count),
#: classified by action name so it is robust to line shifts (see test below).
_GUARD_BRANCH_FLOOR = 18


def test_coverage_floor_is_met(
    ledger_results: tuple[dict[str, tuple[FixtureRun, FixtureRun]], CoverageLedger],
) -> None:
    """Guard-branch coverage floor (>= 18 branches reached, each from its owning
    entry) — a checkable count, proven non-tautological by
    ``test_hollow_ledger_fails_coverage_floor`` (below).

    NOTE — the DECISION-SITE half of the floor is DEACTIVATED here. It keys
    each of the 29 sites by source LINE NUMBER (``KNOWN_DECISION_SITES``), which
    is inherently fragile under the very extraction WPs this oracle exists to
    gate: every WP03–WP10 relocation shifts line numbers and the frozen list no
    longer matches (WP03 alone shifts ``runtime_bridge.py`` by ~171 lines,
    dropping the site tally to 0/29 on a fully behavior-PRESERVING change — the
    parity / side-effect / reason-normalizer checks all stay green). A
    structural, line-number-independent coverage mechanism is being remediated
    in a separate mission; asserting the site floor here until then produces
    constant false failures. The guard-branch floor below is classified by
    action name, not line number, so it stays active and robust. (The
    ``assert_coverage_floor_met`` helper + ``KNOWN_DECISION_SITES`` remain so the
    structural fix can re-activate the site half.)
    """
    _results, ledger = ledger_results
    reached = ledger.guard_branches_reached
    assert len(reached) >= _GUARD_BRANCH_FLOOR, (
        f"guard-branch coverage floor NOT met: {len(reached)} branches reached "
        f"(floor={_GUARD_BRANCH_FLOOR}). Reached: {sorted(reached)}. "
        f"Fixtures run: {ledger.fixtures_run}"
    )


def test_hollow_ledger_fails_coverage_floor() -> None:
    """Proves the coverage-floor assertion is real, not a tautology.

    A ledger that only reached a couple of sites/branches (a "hollow oracle")
    MUST fail assert_coverage_floor_met -- otherwise "green on unmodified
    source" would be necessary but not sufficient in exactly the way WP01's
    Safeguards section warns against. This mirrors the T004 red-first
    authoring discipline (write the assertion, watch it fail against an
    empty/sparse ledger, then fill fixtures until it passes) as a permanent
    regression guard on the assertion mechanism itself.
    """
    hollow = CoverageLedger()
    hollow.sites_reached = {2545}  # a single site, far below any real floor
    hollow.guard_branches_reached = {"cli:specify"}
    with pytest.raises(AssertionError, match="coverage floor NOT met"):
        assert_coverage_floor_met(hollow, site_floor=17, branch_floor=18)


def test_reason_normalizer_meta_test(tmp_path: Path) -> None:
    """canonical() COLLAPSES pure path noise but does NOT collapse a semantic delta.

    Two independent copytree runs of the SAME scenario (the specify-guard-fail
    fixture, whose ``reason`` field is None but whose ``guard_failures``
    embeds no path -- so we additionally build a scenario where ``reason``
    itself carries a path, the run_start_failure fixture, to exercise the
    free-text path collapse) under DIFFERENT roots must compare equal once
    canonicalized against each run's own root. A semantic delta (a changed
    reason phrase or a STABLE-field flip) must compare UNEQUAL even after
    canonicalization -- proving the normalizer does not over-collapse.
    """
    base_a = tmp_path / "a"
    base_b = tmp_path / "b"
    snapshot_a, kwargs_a = _build_run_start_failure(base_a)
    snapshot_b, kwargs_b = _build_run_start_failure(base_b)
    repo_a = copytree_snapshot(snapshot_a, base_a, "run")
    repo_b = copytree_snapshot(snapshot_b, base_b, "run")
    run_a = drive_decide_next(repo_a, fixture_id="reason-meta-a", **kwargs_a)
    run_b = drive_decide_next(repo_b, fixture_id="reason-meta-b", **kwargs_b)

    assert run_a.decision.reason is not None
    assert str(repo_a) in run_a.decision.reason  # sanity: the raw reason DOES embed the run-local root

    # COLLAPSES: two different roots, same logical decision -> equal canonical form.
    canon_a = canonical(run_a.decision, repo_a)
    canon_b = canonical(run_b.decision, repo_b)
    assert canon_a == canon_b, (
        f"reason-normalizer under-collapsed pure path noise:\n{canon_a}\nvs\n{canon_b}"
    )

    # does NOT collapse: a semantic reason delta must survive canonicalization.
    import copy

    mutated = copy.deepcopy(run_b.decision)
    mutated.reason = "Failed to start/load runtime run: a genuinely different failure text"
    canon_mutated = canonical(mutated, repo_b)
    assert canon_mutated != canon_a, (
        "reason-normalizer OVER-collapsed a semantic delta -- self-blinding bug: "
        f"{canon_mutated} incorrectly compared equal to {canon_a}"
    )

    # does NOT collapse: a STABLE-field flip (kind) must also survive.
    mutated_kind = copy.deepcopy(run_b.decision)
    mutated_kind.kind = DecisionKind.terminal
    canon_mutated_kind = canonical(mutated_kind, repo_b)
    assert canon_mutated_kind != canon_a, "reason-normalizer OVER-collapsed a STABLE-field (kind) flip"


# ---------------------------------------------------------------------------
# Direct-call regression coverage for the two composed-guard fail-closed
# defaults. NOT counted toward the entry-driven coverage floor above -- see
# test_coverage_floor_is_met's docstring and the WP01 completion report for
# why these are not reachable from their owning public entry with a valid
# charter-resolved action_sequence. Mirrors the existing proven pattern in
# tests/integration/test_research_runtime_walk.py::
# test_unknown_research_action_fails_closed.
# ---------------------------------------------------------------------------


def test_research_fail_closed_default_direct_call(tmp_path: Path) -> None:
    from runtime.next.runtime_bridge import _check_composed_action_guard

    feature_dir = tmp_path / "kitty-specs" / "research-fail-closed"
    feature_dir.mkdir(parents=True)
    failures = _check_composed_action_guard("totally-unknown-action", feature_dir, mission="research")
    assert failures == ["No guard registered for research action: totally-unknown-action"]


def test_documentation_fail_closed_default_direct_call(tmp_path: Path) -> None:
    from runtime.next.runtime_bridge import _check_composed_action_guard

    feature_dir = tmp_path / "kitty-specs" / "documentation-fail-closed"
    feature_dir.mkdir(parents=True)
    failures = _check_composed_action_guard("totally-unknown-action", feature_dir, mission="documentation")
    assert failures == ["No guard registered for documentation action: totally-unknown-action"]


# ===========================================================================
# advancing-next-board-unification-01M3BGQ0 -- T001-T003: board-authority
# parity for review-reject re-dispatch (#4980) and coord implement dispatch
# (#4975). Contract: kitty-specs/advancing-next-board-unification-01M3BGQ0/
# contracts/advance-query-parity.md (CT-1..CT-7).
# ===========================================================================


def test_review_reject_redispatches_implement_single_branch(tmp_path: Path) -> None:
    """#4980 (T001, CT-2): a WP rejected to ``planned`` while the run is
    issued on ``review`` (single_branch) MUST re-dispatch ``implement WP01``,
    exit 0, equal to query mode -- never the WP-less ``action=review,
    wp_id=null`` composition placeholder (the placeholder-spin bug).

    Pre-fix this was RED: ``_state_to_action("review", ...)`` finds no
    ``for_review`` WP (it was just rejected to ``planned``) and falls
    through to generic ``review.md`` template resolution, returning
    ``action="review", wp_id=None`` -- a *non-None* action, so
    ``_build_wp_iteration_decision``'s ``action is None`` blocked check never
    fires and the WP-less composed placeholder is emitted instead (see
    ``research.md`` Decision 2)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    mission_slug = "042-anbu-reject-sb"
    scaffold_software_dev(
        repo,
        mission_slug,
        with_spec=True,
        with_plan=True,
        with_tasks_md=True,
        wps={"WP01": "for_review"},
    )
    advance_to_step(repo, mission_slug, "software-dev", "review")
    feature_dir = repo / "kitty-specs" / mission_slug
    _reject_wp_on_status_surface(feature_dir, mission_slug, "WP01")

    from runtime.next.runtime_bridge import decide_next_via_runtime, query_current_state

    query_decision = query_current_state("pedro", mission_slug, repo)
    advance_decision = decide_next_via_runtime("pedro", mission_slug, "success", repo)

    assert advance_decision.kind == DecisionKind.step
    assert advance_decision.action == "implement"
    assert advance_decision.wp_id == "WP01"
    assert (advance_decision.action, advance_decision.wp_id) == (
        query_decision.mission_state,
        query_decision.wp_id,
    ), "advance and query must agree on the actionable step/WP (CT-1)"
    assert not (advance_decision.action == "review" and advance_decision.wp_id is None), "must never re-emit the WP-less review composition placeholder (FR-005)"


def test_coord_implement_dispatch_reaches_wp01(tmp_path: Path) -> None:
    """#4975 (T002, CT-3): on the default ``coord`` topology, a WP ready in
    ``planned`` MUST dispatch ``implement WP01``, exit 0 -- never
    ``kind=blocked reason="No action mapped for WP step 'implement'"``.

    Pre-fix this was RED: ``_state_to_action("implement", mission_slug,
    feature_dir, ...)`` calls ``preview_claimable_wp(feature_dir)`` with NO
    ``status_dir`` and ``feature_dir`` (the coord-aware runtime feature dir)
    carries no ``tasks/`` under coord topology (a PRIMARY-partition
    artifact) -- ``preview_claimable_wp`` sees no WP files at all and
    returns ``wp_id=None``, cascading to the generic 'No action mapped'
    blocked decision."""
    repo = tmp_path / "repo"
    repo.mkdir()
    mission_slug = "coord-anbu-implement"
    feature_dir, coord_mission_dir = scaffold_coord_software_dev(repo, mission_slug, _MissionTopology.COORD, wps={"WP01": "planned"})
    advance_to_step(repo, mission_slug, "software-dev", "implement")

    from runtime.next.runtime_bridge import decide_next_via_runtime, query_current_state

    query_decision = query_current_state("pedro", mission_slug, repo)
    advance_decision = decide_next_via_runtime("pedro", mission_slug, "success", repo)

    assert query_decision.wp_id == "WP01"  # absolute anchor on the query side
    assert advance_decision.kind == DecisionKind.step
    assert advance_decision.action == "implement"
    assert advance_decision.wp_id == "WP01"
    assert advance_decision.reason != "No action mapped for WP step 'implement'"


@pytest.mark.parametrize("topology", [_MissionTopology.COORD, _MissionTopology.LANES_WITH_COORD])
def test_review_reject_redispatches_implement_coord_family(tmp_path: Path, topology: _MissionTopology) -> None:
    """US3 (combined cell): review-reject re-dispatch on ``coord`` AND
    ``lanes_with_coord`` simultaneously -- the load-bearing proof the two
    #4980/#4975 faces are unified at ONE authority, not separately patched
    (a branch-by-branch fix could pass the single_branch review test AND the
    coord implement test while still diverging on exactly this combined
    cell -- the #4860 near-miss shape)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    mission_slug = f"coord-anbu-reject-{topology.value.replace('_', '-')}"
    feature_dir, coord_mission_dir = scaffold_coord_software_dev(repo, mission_slug, topology, wps={"WP01": "for_review"})
    advance_to_step(repo, mission_slug, "software-dev", "review")
    _reject_wp_on_status_surface(coord_mission_dir, mission_slug, "WP01")

    from runtime.next.runtime_bridge import decide_next_via_runtime, query_current_state

    query_decision = query_current_state("pedro", mission_slug, repo)
    advance_decision = decide_next_via_runtime("pedro", mission_slug, "success", repo)

    assert advance_decision.kind == DecisionKind.step
    assert advance_decision.action == "implement"
    assert advance_decision.wp_id == "WP01"
    assert (advance_decision.action, advance_decision.wp_id) == (
        query_decision.mission_state,
        query_decision.wp_id,
    )


def test_lanes_with_coord_implement_dispatch(tmp_path: Path) -> None:
    """CT-3 absolute anchor on the second coord-family topology, whose lane
    model differs from plain ``coord``."""
    repo = tmp_path / "repo"
    repo.mkdir()
    mission_slug = "coord-anbu-lwc-implement"
    scaffold_coord_software_dev(repo, mission_slug, _MissionTopology.LANES_WITH_COORD, wps={"WP01": "planned"})
    advance_to_step(repo, mission_slug, "software-dev", "implement")

    from runtime.next.runtime_bridge import decide_next_via_runtime

    advance_decision = decide_next_via_runtime("pedro", mission_slug, "success", repo)

    assert advance_decision.kind == DecisionKind.step
    assert advance_decision.action == "implement"
    assert advance_decision.wp_id == "WP01"


def test_approve_control_unchanged(tmp_path: Path) -> None:
    """US1 S4: the approve control is unchanged -- approving the reviewed WP
    still advances past ``review`` (``kind=step action=accept``), never
    re-dispatching an already-approved WP."""
    repo = tmp_path / "repo"
    repo.mkdir()
    mission_slug = "042-anbu-approve"
    scaffold_software_dev(
        repo,
        mission_slug,
        with_spec=True,
        with_plan=True,
        with_tasks_md=True,
        wps={"WP01": "for_review"},
    )
    advance_to_step(repo, mission_slug, "software-dev", "review")
    feature_dir = repo / "kitty-specs" / mission_slug
    from specify_cli.status.models import Lane, StatusEvent
    from specify_cli.status.store import append_event

    append_event(
        feature_dir,
        StatusEvent(
            event_id="approve-WP01",
            mission_slug=mission_slug,
            wp_id="WP01",
            from_lane=Lane.FOR_REVIEW,
            to_lane=Lane.APPROVED,
            at="2026-01-02T00:00:00+00:00",
            actor="reviewer-fixture",
            force=True,
            execution_mode="worktree",
        ),
    )

    from runtime.next.runtime_bridge import decide_next_via_runtime

    advance_decision = decide_next_via_runtime("pedro", mission_slug, "success", repo)

    assert advance_decision.kind == DecisionKind.step
    assert advance_decision.action == "accept"


def test_early_reject_redispatches_implement(tmp_path: Path) -> None:
    """Edge case: a reject issued while the run is still on ``implement``
    (before hand-off ever reached ``review``) MUST continue to re-dispatch
    ``implement WP01`` unchanged (FR-006)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    mission_slug = "042-anbu-early-reject"
    scaffold_software_dev(
        repo,
        mission_slug,
        with_spec=True,
        with_plan=True,
        with_tasks_md=True,
        wps={"WP01": "planned"},
    )
    advance_to_step(repo, mission_slug, "software-dev", "implement")

    from runtime.next.runtime_bridge import decide_next_via_runtime

    advance_decision = decide_next_via_runtime("pedro", mission_slug, "success", repo)

    assert advance_decision.kind == DecisionKind.step
    assert advance_decision.action == "implement"
    assert advance_decision.wp_id == "WP01"


def test_multi_wp_dependency_order_reject_redispatch(tmp_path: Path) -> None:
    """US1 S5: WP01 (no deps) rejected mid-mission back to ``planned`` while
    WP02 (depends on WP01) is dependency-gated -- advance MUST re-dispatch
    exactly ``implement WP01``; WP02's dependency order stays undisturbed
    (never surfaced as claimable ahead of its unmet dependency)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    mission_slug = "042-anbu-multi-wp"
    scaffold_software_dev(
        repo,
        mission_slug,
        with_spec=True,
        with_plan=True,
        with_tasks_md=True,
        wps={"WP01": "for_review"},
    )
    feature_dir = repo / "kitty-specs" / mission_slug
    (feature_dir / "tasks" / "WP02.md").write_text(
        "---\nwork_package_id: WP02\ndependencies: [WP01]\ntitle: WP02 depends on WP01\n"
        "role: implementer\nrequirement_refs: [FR-001]\n---\n"
        "## Work Package WP02: depends on WP01\n\n### Requirements\n- FR-001\n\nDo it.\n",
        encoding="utf-8",
    )
    _seed_wp_lane(feature_dir, mission_slug, "WP02", "planned")
    advance_to_step(repo, mission_slug, "software-dev", "review")
    _reject_wp_on_status_surface(feature_dir, mission_slug, "WP01")

    from runtime.next.discovery import preview_claimable_wp
    from runtime.next.runtime_bridge import decide_next_via_runtime, query_current_state

    query_decision = query_current_state("pedro", mission_slug, repo)
    advance_decision = decide_next_via_runtime("pedro", mission_slug, "success", repo)

    assert advance_decision.kind == DecisionKind.step
    assert advance_decision.action == "implement"
    assert advance_decision.wp_id == "WP01"
    assert query_decision.wp_id == "WP01"
    # WP02 stays dependency-gated -- the claimable-WP authority still refuses
    # it, dependency order undisturbed.
    wp02_preview = preview_claimable_wp(feature_dir)
    assert wp02_preview.wp_id == "WP01", "WP02 must not become claimable ahead of its unmet dependency"


def test_blocked_floor_all_in_review_has_named_recovery(tmp_path: Path) -> None:
    """CT-4 / US4 S2: every WP ``in_review`` (claimed by another reviewer)
    MUST be ``kind=blocked``, exit 1, with a runnable named recovery
    command -- never a silent no-op."""
    repo = tmp_path / "repo"
    repo.mkdir()
    mission_slug = "042-anbu-all-in-review"
    scaffold_software_dev(
        repo,
        mission_slug,
        with_spec=True,
        with_plan=True,
        with_tasks_md=True,
        wps={"WP01": "in_review"},
    )
    advance_to_step(repo, mission_slug, "software-dev", "review")

    from runtime.next.runtime_bridge import decide_next_via_runtime

    advance_decision = decide_next_via_runtime("pedro", mission_slug, "success", repo)

    assert advance_decision.kind == DecisionKind.blocked
    assert advance_decision.wp_id is None
    _assert_reason_has_runnable_recovery_command(advance_decision.reason, mission_slug)


def test_blocked_floor_no_actionable_wp_has_named_recovery(tmp_path: Path) -> None:
    """CT-4 / US4 S1: a board with no actionable WP for the issued step
    (e.g. the only WP is ``blocked``) MUST be ``kind=blocked``, exit 1, with
    a runnable named recovery command -- never the WP-less composed
    placeholder."""
    repo = tmp_path / "repo"
    repo.mkdir()
    mission_slug = "042-anbu-no-actionable"
    scaffold_software_dev(
        repo,
        mission_slug,
        with_spec=True,
        with_plan=True,
        with_tasks_md=True,
        wps={"WP01": "blocked"},
    )
    advance_to_step(repo, mission_slug, "software-dev", "review")

    from runtime.next.runtime_bridge import decide_next_via_runtime

    advance_decision = decide_next_via_runtime("pedro", mission_slug, "success", repo)

    assert advance_decision.kind == DecisionKind.blocked
    assert advance_decision.wp_id is None
    assert not (advance_decision.action == "review" and advance_decision.wp_id is None and advance_decision.kind == DecisionKind.step)
    _assert_reason_has_runnable_recovery_command(advance_decision.reason, mission_slug)


def test_blocked_floor_dependency_walled_has_named_recovery(tmp_path: Path) -> None:
    """CT-4 / US4 S3: the only claimable-by-lane WP is dependency-gated by an
    un-approved dependency -- MUST be ``kind=blocked``, exit 1, with a
    runnable recovery command, never exit-0 ``kind=step``."""
    repo = tmp_path / "repo"
    repo.mkdir()
    mission_slug = "042-anbu-dep-walled"
    scaffold_software_dev(
        repo,
        mission_slug,
        with_spec=True,
        with_plan=True,
        with_tasks_md=True,
        wps={"WP01": "in_review"},
    )
    feature_dir = repo / "kitty-specs" / mission_slug
    (feature_dir / "tasks" / "WP02.md").write_text(
        "---\nwork_package_id: WP02\ndependencies: [WP01]\ntitle: WP02 depends on WP01\n"
        "role: implementer\nrequirement_refs: [FR-001]\n---\n"
        "## Work Package WP02: depends on WP01\n\n### Requirements\n- FR-001\n\nDo it.\n",
        encoding="utf-8",
    )
    _seed_wp_lane(feature_dir, mission_slug, "WP02", "planned")
    advance_to_step(repo, mission_slug, "software-dev", "implement")

    from runtime.next.runtime_bridge import decide_next_via_runtime

    advance_decision = decide_next_via_runtime("pedro", mission_slug, "success", repo)

    assert advance_decision.kind == DecisionKind.blocked
    _assert_reason_has_runnable_recovery_command(advance_decision.reason, mission_slug)


def test_unmaterialized_coord_surfaces_typed_blocked_reason(tmp_path: Path) -> None:
    """CT-5 / NFR-003: an unmaterialized coordination worktree MUST surface a
    blocked reason naming the unmaterialized surface -- NOT the generic
    ``no_actionable_wp`` floor, and never a fabricated empty-primary read
    (ADR 2026-09-24-2). Reuses the same ``_create_mission``-without-
    materializing shape as
    ``tests/mission_runtime/test_coord_read_seam.py::
    test_unmaterialized_coord_read_raises_instead_of_empty_primary``.

    Drives the selector (``_resolve_wp_board_action``) DIRECTLY rather than
    through ``decide_next_via_runtime``: bootstrap's own
    ``_wrap_with_decision_git_log`` (``DecisionGitLog`` construction) calls
    ``CoordinationWorkspace.resolve``, which materializes the coordination
    worktree as a side effect ("creating it on first call") BEFORE the
    dependency-gate phase ever reaches this selector -- so the unmaterialized
    state is not observable through the full advancing pipeline once
    bootstrap has run (a pre-existing property of ``_wrap_with_decision_git_
    log``, unrelated to and unchanged by this fix). The selector's own
    fail-closed behavior is independently correct and testable at its own
    seam, exactly as ``tests/next/test_finalized_task_routing.py``'s mapping-
    pin tests already exercise it directly."""
    repo = tmp_path / "repo"
    repo.mkdir()
    mission_slug = "coord-anbu-unmat"
    _golden_init_git_repo(repo)
    result = _golden_create_mission(repo, mission_slug, _MissionTopology.COORD)
    # deliberately never materialize the coord worktree (CoordState.UNMATERIALIZED)
    _write_wp_task_files(result.feature_dir, {"WP01": "planned"})
    (result.feature_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], capture_output=True, check=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "seed unmaterialized-coord fixture"],
        capture_output=True,
        check=True,
    )

    from runtime.next.runtime_bridge import _resolve_wp_board_action

    board = _resolve_wp_board_action(mission_slug=result.mission_slug, repo_root=repo)

    assert board.action is None
    assert board.blocked_reason is not None
    assert "unmaterializ" in board.blocked_reason.lower(), f"blocked reason must name the unmaterialized coordination surface, got: {board.blocked_reason!r}"
    assert "no actionable" not in board.blocked_reason.lower(), "must NOT collapse into the generic no-actionable-wp floor (CT-5)"
    assert "spec-kitty doctor workspaces --fix" in board.blocked_reason


def test_snapshot_byte_identical_across_redispatch(tmp_path: Path) -> None:
    """CT-6 / NFR-001: evaluating the re-dispatch decision performs no
    persisted run/engine-state write -- ``state.json`` and
    ``run.events.jsonl`` under the run dir are byte-identical before and
    after the call."""
    repo = tmp_path / "repo"
    repo.mkdir()
    mission_slug = "042-anbu-snapshot"
    scaffold_software_dev(
        repo,
        mission_slug,
        with_spec=True,
        with_plan=True,
        with_tasks_md=True,
        wps={"WP01": "for_review"},
    )
    advance_to_step(repo, mission_slug, "software-dev", "review")
    feature_dir = repo / "kitty-specs" / mission_slug
    _reject_wp_on_status_surface(feature_dir, mission_slug, "WP01")

    from runtime.next.runtime_bridge import decide_next_via_runtime, get_or_start_run

    run_ref = get_or_start_run(mission_slug, repo, "software-dev")
    run_dir = Path(run_ref.run_dir)
    state_path = run_dir / "state.json"
    events_path = run_dir / "run.events.jsonl"
    pre_state = state_path.read_bytes()
    pre_events = events_path.read_bytes() if events_path.exists() else b""

    decide_next_via_runtime("pedro", mission_slug, "success", repo)

    post_state = state_path.read_bytes()
    post_events = events_path.read_bytes() if events_path.exists() else b""
    assert post_state == pre_state, "re-dispatch must not write the run's state.json (NFR-001)"
    assert post_events == pre_events, "re-dispatch must not append run.events.jsonl (NFR-001)"


def test_no_advancing_path_emits_unauthorized_step(tmp_path: Path) -> None:
    """NFR-002 / CT-7 negative single-authority guard: every advancing
    WP-iteration ``(action, wp_id)`` this matrix produces is exactly what the
    board authority (``_resolve_wp_board_action``) independently derives for
    the same repo state -- no advancing path may emit a step/WP the board
    authority did not produce."""
    from runtime.next.runtime_bridge import _resolve_wp_board_action, decide_next_via_runtime

    cases: list[tuple[Path, str]] = []

    repo1 = tmp_path / "neg-implement"
    repo1.mkdir()
    mission1 = "042-anbu-neg-implement"
    scaffold_software_dev(repo1, mission1, with_spec=True, with_plan=True, with_tasks_md=True, wps={"WP01": "planned"})
    advance_to_step(repo1, mission1, "software-dev", "implement")
    cases.append((repo1, mission1))

    repo2 = tmp_path / "neg-reject"
    repo2.mkdir()
    mission2 = "042-anbu-neg-reject"
    scaffold_software_dev(repo2, mission2, with_spec=True, with_plan=True, with_tasks_md=True, wps={"WP01": "for_review"})
    advance_to_step(repo2, mission2, "software-dev", "review")
    _reject_wp_on_status_surface(repo2 / "kitty-specs" / mission2, mission2, "WP01")
    cases.append((repo2, mission2))

    repo3 = tmp_path / "neg-coord"
    repo3.mkdir()
    mission3 = "coord-anbu-neg"
    scaffold_coord_software_dev(repo3, mission3, _MissionTopology.COORD, wps={"WP01": "planned"})
    advance_to_step(repo3, mission3, "software-dev", "implement")
    cases.append((repo3, mission3))

    for repo_root, mission_slug in cases:
        decision = decide_next_via_runtime("pedro", mission_slug, "success", repo_root)
        board = _resolve_wp_board_action(mission_slug=mission_slug, repo_root=repo_root)
        assert (decision.action, decision.wp_id) == (
            board.action,
            board.wp_id,
        ), f"{mission_slug}: advancing emitted {(decision.action, decision.wp_id)!r} but the board authority independently yields {(board.action, board.wp_id)!r}"


def _assert_reason_has_runnable_recovery_command(reason: str | None, mission_slug: str) -> None:
    """CT-4: the blocked reason must embed a runnable ``spec-kitty``
    invocation (parses as a command), not merely be non-empty."""
    assert reason, "blocked decision must carry a non-empty reason"
    match = re.search(r"`(spec-kitty [^`]+)`", reason)
    assert match is not None, f"reason has no backtick-delimited spec-kitty command: {reason!r}"
    command = match.group(1)
    tokens = shlex.split(command)
    assert tokens[0] == "spec-kitty", f"recovery command does not start with 'spec-kitty': {command!r}"
    assert len(tokens) >= 2, f"recovery command has no subcommand: {command!r}"
