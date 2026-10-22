"""Accept-gate topology/status behaviour (WP12 / FR-008 / FR-009 / #2084 / #2085a).

These tests drive the **observable accept-gate verdict** of
``collect_feature_summary`` — which paths land in ``summary.git_dirty`` and
whether ``summary.unchecked_tasks`` strands a mission — never the predicate-call
wiring.

FR-008 (#2084) — the dirty-tree gate is topology-aware: under coordination
topology recognized coordination residue on the primary checkout is ignored,
while a FLAT mission's real primary artifacts STILL block. Each "passes" cell is
paired with its negative control ("still blocks") so the over-allow mutant
cannot survive.

FR-009 (#2085a) — unchecked-tasks completion derives from WP terminal status:
an orchestrated mission whose WPs are all approved/done passes even with unticked
``tasks.md`` checkboxes, while a mission with a near-terminal (``in_review`` /
``for_review``) WP still reports its unchecked items.

The acceptance-MATRIX gate (C-010) is a separate concern and is NOT exercised or
altered here: these fixtures carry no ``lanes.json``, so the matrix path is
skipped (``_check_lane_gates`` returns early).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from ulid import ULID

from kernel.clock import now_utc_iso
from specify_cli.acceptance import AcceptanceSummary, collect_feature_summary
from specify_cli.status.models import Lane, StatusEvent
from tests._support.status_seed import seed_status_event

pytestmark = [pytest.mark.non_sandbox, pytest.mark.git_repo]

# Production-shaped identity: a real 26-char ULID and its derived 8-char mid8.
# The on-disk slug carries the mid8 (post-WP03 grammar) so the mission handle
# resolves through the canonical placement resolver without a husk fallback.
_MISSION_ID = str(ULID())
_MID8 = _MISSION_ID[:8].lower()
_SLUG = f"accept-gate-topology-{_MID8}"
_COORD_BRANCH = f"kitty/coordination-{_SLUG}"


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo_root), *args], check=True, capture_output=True)


def _meta(*, topology: str) -> dict[str, object]:
    """Production-shaped meta.json for the requested stored topology.

    ``coord`` stores ``topology: coord`` plus a ``coordination_branch`` (the
    realistic coordination shape). ``single_branch`` stores the flat topology
    with no coordination branch — its placement resolves to a primary/flattened
    :class:`CommitTarget`, so ``routes_through_coordination`` is ``False``.
    """
    meta: dict[str, object] = {
        "mission_id": _MISSION_ID,
        "mission_number": None,
        "slug": _SLUG,
        "mission_slug": _SLUG,
        "friendly_name": "Accept Gate Topology",
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-06-23T00:00:00Z",
        "topology": topology,
    }
    if topology == "coord":
        meta["coordination_branch"] = _COORD_BRANCH
    return meta


def _wp_frontmatter(wp_id: str, lane: str) -> str:
    return (
        "---\n"
        f'work_package_id: "{wp_id}"\n'
        f'title: "WP {wp_id}"\n'
        f'lane: "{lane}"\n'
        'assignee: "test-agent"\n'
        'agent: "test-agent"\n'
        'shell_pid: "12345"\n'
        "---\n"
        f"# {wp_id}\nBody.\n"
    )


def _emit_wp(feature_dir: Path, wp_id: str, to_lane: Lane) -> None:
    event = StatusEvent(
        event_id=str(ULID()),
        mission_slug=_SLUG,
        wp_id=wp_id,
        from_lane=Lane.PLANNED,
        to_lane=to_lane,
        at=now_utc_iso(),
        actor="test-agent",
        force=True,
        execution_mode="direct_repo",
        reason="Test setup",
    )
    seed_status_event(feature_dir, event)


def _create_mission(
    tmp_path: Path,
    *,
    topology: str,
    wp_lanes: dict[str, Lane],
    tasks_md: str = "# tasks\n\n- [x] T001 done\n",
) -> tuple[Path, Path]:
    """Build a committed, clean mission with the requested topology and WP lanes.

    Returns (repo_root, feature_dir). No ``lanes.json`` is written, so the
    acceptance-matrix gate (C-010) is skipped and the test isolates the
    dirty-tree / unchecked-tasks gates under examination.
    """
    repo_root = tmp_path
    _git(repo_root, "init")
    _git(repo_root, "config", "user.email", "test@example.com")
    _git(repo_root, "config", "user.name", "Test")

    feature_dir = repo_root / "kitty-specs" / _SLUG
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)

    (feature_dir / "meta.json").write_text(json.dumps(_meta(topology=topology), indent=2) + "\n")
    (feature_dir / "spec.md").write_text("# spec\nDone.\n")
    (feature_dir / "plan.md").write_text("# plan\nDone.\n")
    (feature_dir / "tasks.md").write_text(tasks_md)

    for wp_id, lane in wp_lanes.items():
        (tasks_dir / f"{wp_id}-test.md").write_text(_wp_frontmatter(wp_id, lane.value))
        _emit_wp(feature_dir, wp_id, lane)

    from specify_cli.status.reducer import materialize

    materialize(feature_dir)

    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-m", "init")

    if topology == "coord":
        # A coord mission declares ``coordination_branch`` in meta; the read-path
        # resolver refuses (CoordinationBranchDeleted) when the branch is absent
        # from git, so materialize it as a real branch (the realistic coord
        # shape: the branch exists, its stale primary copies are the residue).
        _git(repo_root, "branch", _COORD_BRANCH)

    return repo_root, feature_dir


def _summary(repo_root: Path) -> AcceptanceSummary:
    return collect_feature_summary(
        repo_root,
        _SLUG,
        strict_metadata=False,
        mutate_matrix=False,
    )


# ---------------------------------------------------------------------------
# FR-008 — topology-aware dirty gate (#2084)
# ---------------------------------------------------------------------------


def test_coord_topology_ignores_recognized_coordination_residue(tmp_path: Path) -> None:
    """Coord mission with ONLY a COORD-partition residue → dirty gate PASSES.

    write-surface-coherence WP01-04 narrowed the residue authority: planning
    SOURCE/finalized docs (``spec.md`` / ``plan.md`` / ``tasks.md``) are now
    PRIMARY-partition artifacts that live on ``target_branch``, so their stale
    primary copies are REAL dirt — NOT droppable residue (the new contract; see
    ``test_coord_topology_blocks_primary_planning_residue`` for that flip).

    Only a COORD-partition artifact's stale primary copy is residue. Here we edit
    ``issue-matrix.md`` (``ISSUE_MATRIX`` → coordination branch under coord
    topology) and assert the dirty gate ignores it. (Positive side of the FR-008
    cell — the negative control is ``test_flat_topology_still_blocks_same_residue_paths``.)
    Exemplar swapped from ``analysis-report.md``, which FR-003 re-homed to the
    PRIMARY partition (its stale primary copy is now REAL dirt, not residue), to a
    still-COORD residue member.
    """
    repo_root, feature_dir = _create_mission(
        tmp_path, topology="coord", wp_lanes={"WP01": Lane.DONE}
    )

    (feature_dir / "issue-matrix.md").write_text(
        "# issues\nEdited primary copy (coord residue).\n"
    )

    summary = _summary(repo_root)

    assert not any("issue-matrix.md" in line for line in summary.git_dirty), summary.git_dirty


def test_coord_topology_blocks_primary_planning_residue(tmp_path: Path) -> None:
    """write-surface-coherence WP01-04 flip: a stale ``plan.md`` primary copy BLOCKS.

    Under the pre-mission contract ``plan.md`` was coordination residue and the
    coord dirty gate ignored it. WP01-04 moved the planning + finalized kinds
    (``FINALIZED_EXECUTION_PLAN`` etc.) into ``_PRIMARY_ARTIFACT_KINDS``: they now
    live with the mission on ``target_branch`` for EVERY topology, so a stale
    primary copy is a real dirty-tree blocker even under coord topology. This is
    the narrowing the partition introduced — it proves the residue filter no
    longer over-allows planning artifacts.
    """
    repo_root, feature_dir = _create_mission(
        tmp_path, topology="coord", wp_lanes={"WP01": Lane.DONE}
    )

    (feature_dir / "plan.md").write_text(
        "# plan\nEdited primary copy (now a real dirty blocker — primary kind).\n"
    )

    summary = _summary(repo_root)

    assert any("plan.md" in line for line in summary.git_dirty), summary.git_dirty


def test_flat_topology_still_blocks_same_residue_paths(tmp_path: Path) -> None:
    """NEGATIVE CONTROL: a COORD-partition residue path under a FLAT mission → STILL blocks.

    This is the over-allow mutation-killer. The path is identical to the coord
    cell above (``analysis-report.md``); only the stored topology differs. A flat
    mission routes through PRIMARY, so ``routes_through_coordination`` is
    ``False`` — the residue filter never runs and the real primary edit blocks.
    Exercises WP04's ``is_coordination_artifact_residue_path`` flat→False
    behaviour at the gate.
    """
    repo_root, feature_dir = _create_mission(
        tmp_path, topology="single_branch", wp_lanes={"WP01": Lane.DONE}
    )

    (feature_dir / "analysis-report.md").write_text(
        "# analysis\nEdited primary copy (flat — real dirt).\n"
    )

    summary = _summary(repo_root)

    assert any("analysis-report.md" in line for line in summary.git_dirty), summary.git_dirty


def test_coord_topology_still_blocks_genuine_source_edit(tmp_path: Path) -> None:
    """NEGATIVE CONTROL: a real source edit under coord → STILL blocks.

    A non-residue path (a source file outside the mission's coordination-owned
    artifact set) is not recognized residue, so it blocks even under coord
    topology — the topology filter does not widen into author-owned dirt.
    """
    repo_root, _feature_dir = _create_mission(
        tmp_path, topology="coord", wp_lanes={"WP01": Lane.DONE}
    )

    source = repo_root / "src_module.py"
    source.write_text("x = 1\n")
    _git(repo_root, "add", "src_module.py")
    _git(repo_root, "commit", "-m", "seed source")
    source.write_text("x = 2  # uncommitted real edit\n")

    summary = _summary(repo_root)

    assert any("src_module.py" in line for line in summary.git_dirty), summary.git_dirty


def test_coord_topology_still_blocks_unknown_mission_file(tmp_path: Path) -> None:
    """NEGATIVE CONTROL: an unknown mission file under coord → STILL blocks.

    A scratch file inside the mission dir that is NOT in the residue authority is
    not recognized coordination residue, so it blocks even under coord topology.
    """
    repo_root, feature_dir = _create_mission(
        tmp_path, topology="coord", wp_lanes={"WP01": Lane.DONE}
    )

    scratch = feature_dir / "notes-scratch.md"
    scratch.write_text("scratch\n")
    _git(repo_root, "add", f"kitty-specs/{_SLUG}/notes-scratch.md")
    _git(repo_root, "commit", "-m", "seed scratch")
    scratch.write_text("scratch edited\n")

    summary = _summary(repo_root)

    assert any("notes-scratch.md" in line for line in summary.git_dirty), summary.git_dirty


# ---------------------------------------------------------------------------
# FR-009 — unchecked-tasks derives from WP terminal status (#2085a)
# ---------------------------------------------------------------------------

_UNTICKED_TASKS_MD = "# tasks\n\n- [ ] T001 still unticked\n- [ ] T002 also unticked\n"


def test_orchestrated_mission_passes_unchecked_tasks_with_unticked_boxes(tmp_path: Path) -> None:
    """All WPs approved/done + unticked tasks.md → unchecked-tasks gate PASSES.

    The work landed through the lane lifecycle, so the redundant checkbox
    bookkeeping must not strand the mission. (Positive side; negative control is
    ``test_non_terminal_wp_still_reports_unchecked_tasks``.)
    """
    repo_root, _feature_dir = _create_mission(
        tmp_path,
        topology="single_branch",
        wp_lanes={"WP01": Lane.APPROVED, "WP02": Lane.DONE},
        tasks_md=_UNTICKED_TASKS_MD,
    )

    summary = _summary(repo_root)

    assert summary.unchecked_tasks == [], summary.unchecked_tasks


def test_non_terminal_wp_still_reports_unchecked_tasks(tmp_path: Path) -> None:
    """NEGATIVE CONTROL: a near-terminal WP + unticked tasks.md → STILL reports.

    The non-terminal WP is ``in_review`` — a *near-terminal* boundary, not the
    trivially-non-terminal ``planned`` — so this kills the mutant that treats any
    non-done lane as complete. With one WP not yet approved/done, the unticked
    checkboxes are still surfaced.
    """
    repo_root, _feature_dir = _create_mission(
        tmp_path,
        topology="single_branch",
        wp_lanes={"WP01": Lane.DONE, "WP02": Lane.IN_REVIEW},
        tasks_md=_UNTICKED_TASKS_MD,
    )

    summary = _summary(repo_root)

    assert summary.unchecked_tasks, summary.unchecked_tasks
    assert any("T001" in item for item in summary.unchecked_tasks), summary.unchecked_tasks


def test_for_review_wp_still_reports_unchecked_tasks(tmp_path: Path) -> None:
    """NEGATIVE CONTROL (second near-terminal lane): ``for_review`` → STILL reports."""
    repo_root, _feature_dir = _create_mission(
        tmp_path,
        topology="single_branch",
        wp_lanes={"WP01": Lane.APPROVED, "WP02": Lane.FOR_REVIEW},
        tasks_md=_UNTICKED_TASKS_MD,
    )

    summary = _summary(repo_root)

    assert summary.unchecked_tasks, summary.unchecked_tasks
