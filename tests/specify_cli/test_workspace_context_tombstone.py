"""Regression tests for the workspace-context tombstone on merge/cancel.

FR-005 / LC-6 (#1842 WP03): ``.kittify/workspaces/<slug>-<lane>.json`` must be
deleted once a mission's lane is fully wound down, either by:

* a ``canceled`` transition that leaves every WP sharing the lane terminal
  (``emit_status_transition_transactional``, T011/T012) — proven here on a
  COORD-TOPOLOGY mission (``coordination_branch`` set), because a flat/
  fallback mission instead routes through ``status.emit.emit_status_transition``
  directly and would give a false green if only the coord branch were hooked; or
* merge completion (``merge/executor.py``'s ``_phase_cleanup_worktrees_and_branches``,
  T013).

Also proves the tombstone is additive-only (C-004): a still-active lane keeps
its context, a mission with no ``lanes.json`` is unaffected, and an ordinary
(non-cancel) transition still returns the expected event.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

from specify_cli.coordination.status_service import (
    EventLogWriteContract,
    append_event_log,
)
from specify_cli.coordination.status_transition import emit_status_transition_transactional
from specify_cli.merge import executor as _executor
from specify_cli.merge.state import MergeState
from specify_cli.status.models import Lane, StatusEvent, TransitionRequest

# The cancel-hook tests drive real git via subprocess (``_git`` helper), so the
# file carries the ``git_repo`` marker at module level (Rule 1 of
# tests/architectural/test_pytest_marker_correctness.py). CI uses ``-m git_repo``
# to isolate git-plumbing breakage.
pytestmark = [pytest.mark.git_repo]

# ---------------------------------------------------------------------------
# Cancel-hook tests (T011/T012): emit_status_transition_transactional
# ---------------------------------------------------------------------------

MID8 = "01KWCTX1"
MISSION_ID = f"{MID8}00000000000000000"  # 26-char ULID-shaped id (8 + 18)
# Mirrors the real create-time convention (verified against this repo's own
# mission dirs): the human slug already embeds the mid8 suffix, so
# coord_mission_dir_name()'s idempotency check (mission_slug.endswith("-mid8"))
# holds and the coordination dir name equals MISSION_SLUG verbatim.
MISSION_SLUG = f"wsctx-tombstone-{MID8}"
COORD_BRANCH = f"kitty/mission-{MISSION_SLUG}"


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=check,
        capture_output=True,
        text=True,
    )


def _lanes_json_dict(lane_wp_ids: list[str]) -> dict[str, Any]:
    return {
        "version": 1,
        "mission_slug": MISSION_SLUG,
        "mission_id": MISSION_ID,
        "mission_branch": COORD_BRANCH,
        "target_branch": "main",
        "lanes": [
            {
                "lane_id": "lane-a",
                "wp_ids": lane_wp_ids,
                "write_scope": [],
                "predicted_surfaces": [],
                "depends_on_lanes": [],
                "parallel_group": 0,
            }
        ],
        "computed_at": "2026-05-31T00:00:00+00:00",
        "computed_from": "test",
    }


def _build_coord_repo(tmp_path: Path, *, lane_wp_ids: list[str], with_lanes_json: bool = True) -> Path:
    """A real coord-topology mission: git repo + meta.json (+ lanes.json)."""
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.email", "t@example.invalid")
    _git(r, "config", "user.name", "Test")
    _git(r, "config", "commit.gpgsign", "false")
    feature_dir = r / "kitty-specs" / MISSION_SLUG
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": MISSION_SLUG,
                "mission_id": MISSION_ID,
                "coordination_branch": COORD_BRANCH,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    if with_lanes_json:
        (feature_dir / "lanes.json").write_text(
            json.dumps(_lanes_json_dict(lane_wp_ids)) + "\n", encoding="utf-8"
        )
    _git(r, "add", "kitty-specs")
    _git(r, "commit", "-q", "-m", "seed mission")
    _git(r, "branch", COORD_BRANCH)
    return r


def _seed_planned_on_coord(repo: Path, wp_id: str, event_id: str) -> StatusEvent:
    """Seed *wp_id* out of the non-display 'genesis' state into 'planned'.

    Written directly to the coordination branch via a throwaway worktree (as
    ``finalize-tasks`` does), so it does not fan out — only the transition
    under test does.
    """
    seed_event = StatusEvent(
        event_id=event_id,
        mission_slug=MISSION_SLUG,
        mission_id=MISSION_ID,
        wp_id=wp_id,
        from_lane=Lane.GENESIS,
        to_lane=Lane.PLANNED,
        at="2026-05-31T00:00:00+00:00",
        actor="seed",
        force=False,
        reason="seed",
        execution_mode="worktree",
    )
    worktree = repo / ".worktrees" / f"seed-{wp_id.lower()}"
    _git(repo, "worktree", "add", "-q", str(worktree), COORD_BRANCH)
    coord_feature_dir = worktree / "kitty-specs" / MISSION_SLUG
    append_event_log(
        EventLogWriteContract.coordination_transaction_append(coord_feature_dir),
        seed_event,
    )
    _git(worktree, "add", "kitty-specs")
    _git(worktree, "commit", "-q", "-m", f"seed genesis->planned {wp_id}")
    _git(repo, "worktree", "remove", "-f", str(worktree))
    return seed_event


def _cancel_request(repo: Path, wp_id: str, to_lane: str = "canceled") -> TransitionRequest:
    return TransitionRequest(
        feature_dir=repo / "kitty-specs" / MISSION_SLUG,
        mission_slug=MISSION_SLUG,
        wp_id=wp_id,
        to_lane=to_lane,
        actor="tombstone-test",
        repo_root=repo,
    )


def _write_orphan_context(repo: Path, lane_id: str = "lane-a") -> Path:
    context_path = repo / ".kittify" / "workspaces" / f"{MISSION_SLUG}-{lane_id}.json"
    context_path.parent.mkdir(parents=True, exist_ok=True)
    context_path.write_text("{}", encoding="utf-8")
    return context_path


@pytest.mark.unit
@pytest.mark.git_repo
def test_cancel_tombstones_lane_context_when_all_lane_wps_terminal(tmp_path: Path) -> None:
    """Coord-topology mission, single-WP lane: cancel -> lane all-terminal -> tombstoned.

    Non-vacuous: the context file is seeded BEFORE the transition and only the
    hook under test removes it — if the cancel hook were absent, this assertion
    would red (the file would still be there).
    """
    repo = _build_coord_repo(tmp_path, lane_wp_ids=["WP01"])
    _seed_planned_on_coord(repo, "WP01", "01SEEDWP01TOMBSTONE00000A")
    context_path = _write_orphan_context(repo)

    event = emit_status_transition_transactional(_cancel_request(repo, "WP01"))

    assert event.to_lane == Lane.CANCELED
    assert not context_path.exists()


@pytest.mark.unit
@pytest.mark.git_repo
def test_cancel_does_not_tombstone_when_lane_still_active(tmp_path: Path) -> None:
    """A shared lane with a non-terminal sibling WP must keep its context.

    Two WPs share lane-a; only WP01 is canceled. WP02 is still 'planned', so
    the lane is not all-terminal and the context tombstone must be a no-op.
    """
    repo = _build_coord_repo(tmp_path, lane_wp_ids=["WP01", "WP02"])
    _seed_planned_on_coord(repo, "WP01", "01SEEDWP01TOMBSTONE00000B")
    _seed_planned_on_coord(repo, "WP02", "01SEEDWP02TOMBSTONE00000C")
    context_path = _write_orphan_context(repo)

    emit_status_transition_transactional(_cancel_request(repo, "WP01"))

    assert context_path.exists()


@pytest.mark.unit
@pytest.mark.git_repo
def test_tombstone_is_noop_for_still_active_mission_without_lanes_json(tmp_path: Path) -> None:
    """No lanes.json (flat/legacy execution) -> hook safely no-ops."""
    repo = _build_coord_repo(tmp_path, lane_wp_ids=["WP01"], with_lanes_json=False)
    _seed_planned_on_coord(repo, "WP01", "01SEEDWP01TOMBSTONE00000D")

    event = emit_status_transition_transactional(_cancel_request(repo, "WP01"))

    assert event.to_lane == Lane.CANCELED
    # No workspaces dir was ever created — the hook must not create one either.
    assert not (repo / ".kittify" / "workspaces").exists()


@pytest.mark.unit
@pytest.mark.git_repo
def test_non_cancel_transition_unaffected_by_tombstone_hook(tmp_path: Path) -> None:
    """C-004: an ordinary (non-cancel) transition is unaffected by the hook."""
    repo = _build_coord_repo(tmp_path, lane_wp_ids=["WP01"])
    _seed_planned_on_coord(repo, "WP01", "01SEEDWP01TOMBSTONE00000E")
    context_path = _write_orphan_context(repo)

    event = emit_status_transition_transactional(
        _cancel_request(repo, "WP01", to_lane="claimed")
    )

    assert event.to_lane == Lane.CLAIMED
    # A non-cancel transition must never touch an unrelated lane context.
    assert context_path.exists()


# ---------------------------------------------------------------------------
# Merge-hook tests (T013): merge.executor._phase_cleanup_worktrees_and_branches
# ---------------------------------------------------------------------------


def _make_merge_run(tmp_path: Path, *, lane_ids: list[str], remove_worktree: bool = True) -> _executor._MergeRunState:
    lanes_manifest = SimpleNamespace(
        mission_slug="m",  # run.mission_slug must equal lanes_manifest.mission_slug
        target_branch="main",
        mission_branch="kitty/mission-m",
        lanes=[SimpleNamespace(lane_id=lane_id, wp_ids=["WP01"]) for lane_id in lane_ids],
    )
    state = MergeState(mission_id="01ID", mission_slug="m", target_branch="main", wp_order=["WP01"])
    run = _executor._MergeRunState(
        main_repo=tmp_path,
        mission_slug="m",
        canonical_id="01ID",
        canonical_mission_id="01JQANARZAP70V8DVJZ8XN0M3T",
        feature_dir=tmp_path / "kitty-specs" / "m",
        target_feature_dir=tmp_path / "kitty-specs" / "m",
        lanes_manifest=lanes_manifest,
        all_wp_ids=["WP01"],
        push=False,
        delete_branch=False,
        remove_worktree=remove_worktree,
        strategy=_executor.MergeStrategy.SQUASH,
        assume_yes=True,
        planning_artifact_only=False,
        state=state,
        is_resume=False,
    )
    run.baseline_mission_id = "01ID"
    return run


def _run_cleanup_phase(run: _executor._MergeRunState) -> None:
    # The worktree-removal loop
    # resolves its path via ``_created_lane_worktree``
    # (``predict_lane_worktree``), never via a directly-imported
    # ``worktree_path`` reference this patch could intercept — the CREATED
    # path (``<tmp_path>/.worktrees/m-lane-a``) is already guaranteed absent
    # under a fresh ``tmp_path``, so no patch is needed to keep the
    # worktree-removal branch a no-op here.
    with (
        patch.object(_executor, "_worktree_removal_delay", return_value=0),
        patch.object(_executor, "run_command", return_value=(0, "", "")),
        patch("specify_cli.mission_metadata.load_meta", return_value={"mid8": "deadbeef"}),
        patch("specify_cli.post_merge.retrospective_terminus.run_retrospective_postcondition"),
        patch("specify_cli.coordination.workspace.CoordinationWorkspace"),
    ):
        _executor._phase_cleanup_worktrees_and_branches(run)


@pytest.mark.fast
def test_merge_completion_tombstones_lane_workspace_context(tmp_path: Path) -> None:
    """A merged mission's lane workspace-context JSON is removed (T013/FR-005)."""
    run = _make_merge_run(tmp_path, lane_ids=["lane-a"])
    context_path = tmp_path / ".kittify" / "workspaces" / "m-lane-a.json"
    context_path.parent.mkdir(parents=True, exist_ok=True)
    context_path.write_text("{}", encoding="utf-8")

    _run_cleanup_phase(run)

    assert not context_path.exists()


@pytest.mark.fast
def test_merge_completion_tombstone_covers_every_lane(tmp_path: Path) -> None:
    """Multi-lane mission: every lane's context is tombstoned, not just the first."""
    run = _make_merge_run(tmp_path, lane_ids=["lane-a", "lane-b"])
    context_a = tmp_path / ".kittify" / "workspaces" / "m-lane-a.json"
    context_b = tmp_path / ".kittify" / "workspaces" / "m-lane-b.json"
    for path in (context_a, context_b):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")

    _run_cleanup_phase(run)

    assert not context_a.exists()
    assert not context_b.exists()


@pytest.mark.fast
def test_merge_completion_tombstone_is_noop_when_no_context_exists(tmp_path: Path) -> None:
    """No context file for the lane -> delete_context no-ops; phase does not raise."""
    run = _make_merge_run(tmp_path, lane_ids=["lane-a"])

    _run_cleanup_phase(run)  # must not raise

    assert not (tmp_path / ".kittify" / "workspaces" / "m-lane-a.json").exists()


@pytest.mark.fast
def test_merge_completion_keeps_context_when_keep_worktree_requested(tmp_path: Path) -> None:
    """``--keep-worktree`` (remove_worktree=False) skips the tombstone too.

    The tombstone lives in the same ``if run.remove_worktree:`` block as the
    worktree removal it accompanies (C-004): when the operator opts to keep
    the lane worktree around, its describing context file is preserved too.
    """
    run = _make_merge_run(tmp_path, lane_ids=["lane-a"], remove_worktree=False)
    context_path = tmp_path / ".kittify" / "workspaces" / "m-lane-a.json"
    context_path.parent.mkdir(parents=True, exist_ok=True)
    context_path.write_text("{}", encoding="utf-8")

    _run_cleanup_phase(run)

    assert context_path.exists()
