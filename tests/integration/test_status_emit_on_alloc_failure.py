"""Integration tests for allocation-failure status handling (F-50, #3937).

``create_lane_workspace`` runs BEFORE the claim transition, so the WP is still
``planned`` when allocation raises; the allocator self-cleans (abort +
``reset --hard``, no ``lanes.json`` write). Manufacturing a ``planned -> blocked``
transition on that failure created an unrecoverable state (``blocked -> planned``
is illegal), so ``implement`` must instead leave the WP ``planned`` and surface
the exception's actionable ``next_step`` — at parity with the orchestrator-api
path, which never emits ``blocked``.

These tests pin observable STATE (the reduced lane and the real
``status.events.jsonl``), not message substrings alone, so a cosmetic message
edit cannot fake them (NFR-001). They run the real command against a real git
repository (the characterization fixture). The dependency-lane conflict is a
real allocator failure; the two planning-pin failures need a pinned planning
commit the fixture cannot build cheaply, so they are injected at the allocator
through the characterization dispatch map (``allocate``), which this test is
allowed to use (implement-degod FR-011).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from specify_cli.lanes.planning_commit_classify import PinClass
from specify_cli.lanes.worktree_allocator import (
    DependencyLaneMergeConflictError,
    OrphanedPlanningCommitError,
    PlanningCommitMergeConflictError,
)
from specify_cli.status.reducer import wp_snapshot_state
from tests.specify_cli.cli.commands._implement_dispatch import patch_collaborator
from tests.specify_cli.cli.commands._implement_fixtures import (
    ARGS,
    LANE_WORKTREE,
    LATE,
    MISSION_ID,
    SLUG,
    Mission,
    activated_repo,
    build_mission,
    flat,
    git,
    implement_cli,
)
from tests.utils import _seed_canonical_wp_state

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

MISSION_BRANCH = f"kitty/mission-{SLUG}"
DEP_LANE_BRANCH = f"kitty/mission-{SLUG}-lane-a"
LANE_B_WORKTREE = f".worktrees/{SLUG}-lane-b"


@pytest.fixture()
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    return activated_repo(tmp_path, monkeypatch)


def _read_events(mission: Mission) -> list[dict[str, Any]]:
    if not mission.events_path.exists():
        return []
    lines = mission.events_path.read_text(encoding="utf-8").splitlines()
    return [event for event in map(json.loads, filter(str.strip, lines)) if "kind" not in event]


def _dependency_conflict_mission(repo: Path) -> Mission:
    """WP02 (lane-b) depends on an approved WP01 (lane-a) whose lane conflicts with the mission branch."""
    mission = build_mission(
        repo,
        SLUG,
        MISSION_ID,
        wps={"WP01": ("code_change", []), "WP02": ("code_change", ["WP01"])},
        layout=(("lane-a", ("WP01",), ()), ("lane-b", ("WP02",), ("lane-a",))),
    )
    claim = implement_cli(*ARGS)
    assert claim.exit_code == 0, claim.output
    lane_a = repo / LANE_WORKTREE
    (lane_a / "src").mkdir()
    (lane_a / "src" / "x.py").write_text("A\n", encoding="utf-8")
    git(lane_a, "add", "-A")
    git(lane_a, "commit", "-q", "-m", "lane a content")
    checkout = repo.parent / "mission-branch-checkout"
    git(repo, "worktree", "add", "-q", str(checkout), MISSION_BRANCH)
    (checkout / "src").mkdir()
    (checkout / "src" / "x.py").write_text("B\n", encoding="utf-8")
    git(checkout, "add", "-A")
    git(checkout, "commit", "-q", "-m", "mission branch content")
    git(repo, "worktree", "remove", "--force", str(checkout))
    for lane in ("for_review", "approved"):
        _seed_canonical_wp_state(repo, SLUG, "WP01", lane, actor="reviewer", assignee="Owner", shell_pid="1", timestamp=LATE)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "approve WP01")
    return mission


def _assert_left_planned_with_next_step(mission: Mission, output: str, wp_id: str, next_step: str, events_before: int) -> None:
    # Observable STATE 1: the reduced lane is still ``planned`` — recoverable.
    reduced = wp_snapshot_state(mission.feature_dir, wp_id)
    assert reduced is not None
    assert reduced["lane"] == "planned"

    # Observable STATE 2: NO manufactured ``planned -> blocked`` transition, no
    # ``blocked`` lane ever entered, and no lifecycle event at all for this run.
    events = _read_events(mission)
    assert all(e["to_lane"] != "blocked" for e in events)
    assert [e for e in events if e["wp_id"] == wp_id and e.get("actor") == "tester"] == []
    assert len(mission.events_path.read_text(encoding="utf-8").splitlines()) == events_before

    # Observable STATE 3: the actionable next_step is surfaced verbatim, through the
    # PROMINENT ``Next step:`` affordance — not merely incidentally present because the
    # generic "Workspace allocation failed: {exc}" line also embeds next_step in str(exc).
    text = flat(output)
    assert next_step
    assert f"Next step: {next_step}" in text, text


def test_a_real_dependency_lane_conflict_leaves_the_wp_planned_and_prints_the_next_step(repo: Path) -> None:
    """F-50 (C1), real allocator failure: the dependency-lane merge conflicts during allocation."""
    mission = _dependency_conflict_mission(repo)
    events_before = mission.event_count()

    result = implement_cli("WP02", "--mission", SLUG, "--actor", "tester")

    assert result.exit_code == 1, result.output
    expected = DependencyLaneMergeConflictError("lane-b", "lane-a", DEP_LANE_BRANCH)
    _assert_left_planned_with_next_step(mission, result.output, "WP02", expected.next_step, events_before)


@pytest.mark.parametrize(
    "exc",
    [
        PlanningCommitMergeConflictError("lane-a", "deadbeefcafef00d"),
        OrphanedPlanningCommitError("lane-a", "deadbeefcafef00d", PinClass.ORPHANED),
    ],
    ids=["planning-commit-conflict", "orphaned-planning-commit"],
)
def test_a_planning_pin_failure_leaves_the_wp_planned_and_prints_the_next_step(
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    exc: PlanningCommitMergeConflictError | OrphanedPlanningCommitError,
) -> None:
    """F-50 (C1), pinned-planning-commit failures. Covers ``OrphanedPlanningCommitError`` (#4827
    pre-PR finding: it carries a ``next_step`` too but was missing from the printed-affordance tuple)."""
    mission = build_mission(repo, SLUG, MISSION_ID)
    events_before = mission.event_count()
    calls: list[str] = []

    def _fail(**kwargs: Any) -> Any:
        calls.append(kwargs["wp_id"])
        raise exc

    patch_collaborator(monkeypatch, "allocate", _fail)

    result = implement_cli(*ARGS)

    assert calls == ["WP01"]
    assert result.exit_code == 1, result.output
    _assert_left_planned_with_next_step(mission, result.output, "WP01", exc.next_step, events_before)
    assert not (repo / ".worktrees").exists()


def test_rerun_after_resolution_acquires_no_review_cycle_pointer(repo: Path) -> None:
    """F-50 (C2): once the conflict is resolved, re-running ``implement`` on the
    still-``planned`` WP proceeds through the normal claim — with NO intermediate
    unblock step and NO ``review-cycle://`` feedback pointer (Fix mode is not
    triggered)."""
    mission = _dependency_conflict_mission(repo)

    # Run 1: allocation conflicts -> WP stays planned, nothing emitted.
    first = implement_cli("WP02", "--mission", SLUG, "--actor", "tester")
    assert first.exit_code == 1, first.output
    assert (wp_snapshot_state(mission.feature_dir, "WP02") or {}).get("lane") == "planned"

    # The operator follows the printed next step: merge the dependency lane into
    # lane-b by hand, resolve the conflict, commit.
    lane_b = repo / LANE_B_WORKTREE
    merge = subprocess.run(["git", "-C", str(lane_b), "merge", "--no-edit", DEP_LANE_BRANCH], capture_output=True, text=True, check=False)
    assert merge.returncode != 0, merge.stdout
    (lane_b / "src" / "x.py").write_text("A\nB\n", encoding="utf-8")
    git(lane_b, "add", "-A")
    git(lane_b, "commit", "-q", "--no-edit")

    # Run 2: the real allocation and the real claim succeed.
    second = implement_cli("WP02", "--mission", SLUG, "--actor", "tester")
    assert second.exit_code == 0, second.output

    events = _read_events(mission)
    # The normal claim actually happened (proceeded, not an unblock detour).
    assert (wp_snapshot_state(mission.feature_dir, "WP02") or {}).get("lane") == "in_progress"
    wp02_claim = [(e["from_lane"], e["to_lane"]) for e in events if e.get("actor") == "tester" and e["wp_id"] == "WP02"]
    assert wp02_claim == [("planned", "claimed"), ("claimed", "in_progress")]
    # No ``blocked`` lane was ever entered across both runs.
    assert all(e["to_lane"] != "blocked" for e in events)
    # Fix mode was never triggered: no event carries a ``review-cycle://`` pointer.
    assert all(not str(e.get("review_ref") or "").startswith("review-cycle://") for e in events)
