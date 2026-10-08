"""Real on-disk mission scaffolds for the ``runtime_bridge`` real-engine tests.

Shared by the board-authority acceptance tests
(``tests/runtime/test_next_board_authority.py``) and the #2531 two-run parity
oracle (``tests/runtime/test_bridge_parity.py``), so neither module duplicates
the git / mission-creation / WP-seeding fixtures. Never stubs the runtime
planner: ``advance_to_step`` drives the REAL engine forward.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from mission_runtime import MissionTopology as _MissionTopology
from runtime.next.decision import AnalysisVerdict
from tests.integration.test_placement_partition_golden_path import (
    _create_mission as _golden_create_mission,
    _init_git_repo as _golden_init_git_repo,
    _materialize_coord_worktree as _golden_materialize_coord_worktree,
)
from tests.lane_test_utils import write_single_lane_manifest

__all__ = [
    "add_wp_files",
    "advance_to_step",
    "analysis_is_current",
    "commit_all",
    "init_git_repo",
    "provision_mission_type_activations",
    "reject_wp_on_status_surface",
    "scaffold_coord_software_dev",
    "scaffold_software_dev",
    "seed_wp_lane",
    "write_spec_md",
    "write_wp_task_files",
]


# ---------------------------------------------------------------------------
# Repo scaffolding — mirrors the proven patterns in tests/next/test_runtime_
# bridge_unit.py, tests/next/test_finalized_task_routing.py, and
# tests/integration/test_{research,documentation}_runtime_walk.py.
# ---------------------------------------------------------------------------


def analysis_is_current() -> AnalysisVerdict:
    """An injected analysis-currency check that always reports a current report.

    The software-dev ``analyze`` step and the finalized-board override only hand
    out ``implement`` while the analysis report is current (WP07); a test that is
    about what happens AFTER that gate passes this as ``analysis_currency=``.
    """
    return AnalysisVerdict("current")


def init_git_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "--initial-branch=main"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, capture_output=True, check=True)
    (path / "README.md").write_text("# test\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, capture_output=True, check=True)


def commit_all(path: Path, message: str) -> None:
    subprocess.run(["git", "add", "."], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", message], cwd=path, capture_output=True, check=True)


def seed_wp_lane(feature_dir: Path, mission_slug: str, wp_id: str, lane: str) -> None:
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


def write_wp_task_files(feature_dir: Path, wps: dict[str, str], *, deps: bool = True) -> None:
    """Write realistic WP task files + the single-lane manifest — no lane-event
    seed here (WP01 / advancing-next-board-unification-01M3BGQ0: coord-topology
    fixtures need WP files on the PRIMARY dir but lane events on the
    coordination status surface, so the file-write and event-seed halves of
    the former ``add_wp_files`` are split; single_branch callers get both
    back via :func:`add_wp_files` below, byte-identical to before the split).

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


def add_wp_files(feature_dir: Path, mission_slug: str, wps: dict[str, str], *, deps: bool = True) -> None:
    """Write realistic WP files + seed their canonical lane state (single_branch
    shape: WP files and lane events share the same dir)."""
    write_wp_task_files(feature_dir, wps, deps=deps)
    for wp_id, lane in wps.items():
        seed_wp_lane(feature_dir, mission_slug, wp_id, lane)


def write_spec_md(feature_dir: Path, requirement_ids: list[str]) -> None:
    reqs = "\n".join(f"- {rid}: requirement {rid}" for rid in requirement_ids)
    (feature_dir / "spec.md").write_text(
        f"# Spec\n\n## Functional Requirements\n{reqs}\n",
        encoding="utf-8",
    )


def provision_mission_type_activations(repo_root: Path, mission_type: str) -> None:
    """Provision ``.kittify/config.yaml`` with ``mission_type`` activated.

    WP04 fail-closed (C-A1): composition (``_dispatch_via_composition``) calls
    ``resolve_mission_type_context`` for real, so every scaffold's mission
    type must be activated for that resolution to succeed.
    """
    kittify_dir = repo_root / ".kittify"
    kittify_dir.mkdir(exist_ok=True)
    (kittify_dir / "config.yaml").write_text(f"mission_type_activations:\n  - {mission_type}\n", encoding="utf-8")


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
    init_git_repo(repo_root)
    provision_mission_type_activations(repo_root, "software-dev")
    feature_dir = repo_root / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(json.dumps({"mission_type": "software-dev"}), encoding="utf-8")
    if with_spec:
        write_spec_md(feature_dir, requirement_ids or ["FR-001"])
    if with_plan:
        (feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    if with_tasks_md:
        (feature_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
    if wps:
        add_wp_files(feature_dir, mission_slug, wps, deps=wp_deps)
    commit_all(repo_root, "seed software-dev fixture")
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
    raise AssertionError(f"advance_to_step: never reached {target_step_id!r} within {max_steps} steps (mission={mission_slug!r} type={mission_type!r})")


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

    # coord-artifact-single-home-01M3V4BE WP09 (review cycle 2, same-family
    # B1-residual fix): the coordination log must CARRY FORWARD the root
    # checkout's already-committed status events before the WP-lane sentinel
    # events below are appended -- mirroring what the REAL coord_seed carry-
    # over does (``contracts/seed.md``). Before this, the coord log's ONLY
    # content was the hand-seeded ``seed-<wp>-<lane>`` sentinels with no
    # shared history at all with root's real ``MissionCreated``-style events --
    # an un-related-histories shape ``establish_coord_write_location``'s fork
    # detection correctly calls a genuine fork (``CoordSeedForkRefused``) once
    # a bare-slug ``write_dir`` call (e.g. ``_wrap_with_decision_git_log``)
    # actually resolves this Mission's real coordination surface instead of
    # silently degrading to PRIMARY for an unresolved handle (the bug this
    # same mission's WP09 fixes). This fixture never exercised that fork
    # check before, because the bug it fixes was masking it.
    root_status_log = result.feature_dir / "status.events.jsonl"
    if root_status_log.exists():
        (coord_mission_dir / "status.events.jsonl").write_bytes(root_status_log.read_bytes())

    write_wp_task_files(result.feature_dir, wps)
    (result.feature_dir / "spec.md").write_text("# Spec\n\n## Functional Requirements\n- FR-001: x\n", encoding="utf-8")
    (result.feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    (result.feature_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
    for wp_id, lane in wps.items():
        seed_wp_lane(coord_mission_dir, result.mission_slug, wp_id, lane)
    subprocess.run(["git", "-C", str(repo_root), "add", "-A"], capture_output=True, check=True)
    subprocess.run(
        ["git", "-C", str(repo_root), "commit", "-m", f"seed coord fixture for {mission_slug}"],
        capture_output=True,
        check=True,
    )
    return result.feature_dir, coord_mission_dir


def reject_wp_on_status_surface(status_dir: Path, mission_slug: str, wp_id: str) -> None:
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
