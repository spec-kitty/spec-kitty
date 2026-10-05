"""Lane sync resolves primary-owned bookkeeping to the coordination side (#5457).

FR-008 / Story 4 AS-4: on a ``lanes_with_coord`` mission left in the broken
state by a pre-fix ``spec-kitty upgrade`` (a per-branch divergent
``.kittify/metadata.yaml``), the lane sync that follows every coordination
lifecycle commit must not refuse with ``LANE_AUTO_REBASE_FAILED``. The
primary-owned path takes stage 3 (the incoming coordination branch) under the
audited rule ``R-PRIMARY-OWNED-BOOKKEEPING``.

Entry point: :func:`sync_lane_after_coordination_commit`, the production
function the ``agent action review`` / ``implement`` paths call after a
coordination status commit. The fixture's lane worktree is the product
allocator's sparse checkout, so the sparse-aware staging helpers run for real.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from specify_cli.lanes.auto_rebase import AutoRebaseReport
from specify_cli.lanes.lifecycle_sync import (
    LANE_AUTO_REBASE_FAILED,
    LaneAutoRebaseSyncError,
    sync_lane_after_coordination_commit,
)
from tests.integration import primary_owned_fixtures as fx

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

PRIMARY_OWNED_RULE = "R-PRIMARY-OWNED-BOOKKEEPING"


def _git_out(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout


def _broken_coord_project(tmp_path: Path) -> fx.LanesProject:
    project = fx.build_older_version_lanes_project(tmp_path, topology="lanes_with_coord", lanes=1)
    fx.commit_broken_upgrade_state(project)
    return project


def _coordination_lifecycle_commit(project: fx.LanesProject) -> None:
    """Append one status event on the coordination branch (a lifecycle commit)."""
    assert project.coord_branch is not None
    fx.append_status_event_on_branch(project, project.coord_branch, "WP01", "approved", "done")


def _sync(project: fx.LanesProject) -> AutoRebaseReport | None:
    assert project.coord_branch is not None
    report: AutoRebaseReport | None = sync_lane_after_coordination_commit(
        repo_root=project.repo,
        mission_slug=project.slug,
        wp_id="WP01",
        coordination_branch=project.coord_branch,
    )
    return report


def _fail_git_show_of_stage_three(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make ``git show :3:<path>`` fail spuriously (exit 128); every other git call runs for real."""
    real_run = subprocess.run

    def fake_run(cmd: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(cmd, list) and cmd[:2] == ["git", "show"] and str(cmd[2]).startswith(":3:"):
            return subprocess.CompletedProcess(cmd, 128, stdout="", stderr="fatal: simulated failure")
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", fake_run)


@pytest.mark.parametrize("stage_three_unreadable", [False, True], ids=["takes-theirs", "spurious-stage-read-failure-deletes-nothing"])
def test_lane_sync_takes_coordination_metadata_under_primary_owned_rule(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stage_three_unreadable: bool,
) -> None:
    # Arrange
    project = _broken_coord_project(tmp_path)
    assert project.coord_branch is not None
    lane_branch = project.lane_branches["lane-a"]
    lane_worktree = project.lane_worktrees["lane-a"]
    assert fx.metadata_blob(project.repo, lane_branch) != fx.metadata_blob(project.repo, project.coord_branch)
    _coordination_lifecycle_commit(project)

    # Assumption: the lane worktree is a sparse checkout (product allocator).
    assert _git_out(lane_worktree, "config", "--bool", "core.sparseCheckout").strip() == "true"

    if stage_three_unreadable:
        # Reading stage 3 failing for a reason other than "the stage is absent"
        # must halt the sync, never be read as "theirs deleted it" and delete
        # the lane's metadata.
        own_metadata = fx.metadata_blob(project.repo, lane_branch)
        pre_sync_head = _git_out(lane_worktree, "rev-parse", "HEAD").strip()
        with monkeypatch.context() as stage_failure:
            _fail_git_show_of_stage_three(stage_failure)
            with pytest.raises(LaneAutoRebaseSyncError) as exc_info:
                _sync(project)
        assert exc_info.value.to_dict()["error_code"] == LANE_AUTO_REBASE_FAILED
        assert fx.metadata_blob(project.repo, lane_branch) == own_metadata
        assert _git_out(lane_worktree, "rev-parse", "HEAD").strip() == pre_sync_head
        return

    # Act
    report = _sync(project)

    # Assert
    assert report is not None
    assert report.succeeded is True, report.halt_reason
    assert fx.metadata_blob(project.repo, lane_branch) == fx.metadata_blob(project.repo, project.coord_branch)
    subject = _git_out(lane_worktree, "log", "-1", "--format=%s", lane_branch)
    assert PRIMARY_OWNED_RULE in subject


def test_lane_sync_still_refuses_a_source_conflict_byte_identically(
    tmp_path: Path,
) -> None:
    """Control (FR-008): a genuine source conflict still refuses, same text."""
    # Arrange
    project = _broken_coord_project(tmp_path)
    assert project.coord_branch is not None
    lane_branch = project.lane_branches["lane-a"]
    lane_worktree = project.lane_worktrees["lane-a"]
    fx.commit_file_on_branch(project.repo, project.coord_branch, "src/shared.txt", "coordination\n", "coord: shared")
    fx.commit_file_on_branch(project.repo, lane_branch, "src/shared.txt", "lane\n", "lane: shared")
    _coordination_lifecycle_commit(project)
    pre_sync_head = _git_out(lane_worktree, "rev-parse", "HEAD").strip()

    # Act
    with pytest.raises(LaneAutoRebaseSyncError) as exc_info:
        _sync(project)

    # Assert
    assert exc_info.value.to_dict()["error_code"] == LANE_AUTO_REBASE_FAILED
    assert str(exc_info.value) == (f"LANE_AUTO_REBASE_FAILED: auto-rebase refused for lane-a: no classifier rule matched {lane_worktree / 'src' / 'shared.txt'}")
    assert _git_out(lane_worktree, "rev-parse", "HEAD").strip() == pre_sync_head


def test_lane_sync_removes_primary_owned_path_deleted_on_coordination_side(
    tmp_path: Path,
) -> None:
    """Modify/delete: stage 3 is absent, so the path is removed in the lane."""
    # Arrange
    project = fx.build_older_version_lanes_project(tmp_path, topology="lanes_with_coord", lanes=1)
    assert project.coord_branch is not None
    lane_branch = project.lane_branches["lane-a"]
    lane_worktree = project.lane_worktrees["lane-a"]
    fx.commit_broken_upgrade_state(project, branches=[lane_branch])
    fx.delete_path_on_branch(project.repo, project.coord_branch, fx.METADATA_PATH)
    _coordination_lifecycle_commit(project)
    assert fx.metadata_blob(project.repo, project.coord_branch) is None
    assert fx.metadata_blob(project.repo, lane_branch) is not None

    # Act
    report = _sync(project)

    # Assert
    assert report is not None
    assert report.succeeded is True, report.halt_reason
    rule_ids = {getattr(c.resolution, "rule_id", None) for c in report.classifications}
    assert PRIMARY_OWNED_RULE in rule_ids
    assert fx.metadata_blob(project.repo, lane_branch) is None
    assert not (lane_worktree / fx.METADATA_PATH).exists()
    subject = _git_out(lane_worktree, "log", "-1", "--format=%s", lane_branch)
    assert PRIMARY_OWNED_RULE in subject
