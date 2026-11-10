"""#7310: the lane-worktree shared-writer advisory reads status through the one read door.

``agent action implement`` / ``review`` print an advisory naming other actors on the same
lane worktree (#5099). For a coordination Mission whose coordination worktree is not
materialized (the branch exists, the worktree does not), the advisory read the placement
seam's ``read_dir(STATUS_STATE)``. That raises ``CoordinationWorktreeUnmaterialized``, which the
advisory's guard does not catch, so an advisory crashed the command. The read door
(ADR 2026-11-06-2) reads the committed coordination branch instead.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from mission_runtime import MissionArtifactKind, MissionTopology, placement_seam
from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.lanes.checkout_occupancy import SharedWorkspaceWriter, shared_workspace_writers
from specify_cli.workspace.context import ResolvedWorkspace
from tests.integration.test_placement_partition_golden_path import _create_mission, _init_git_repo
from tests.runtime._next_mission_scaffold import seed_wp_lane

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True)


def _lane_workspace(mission_slug: str, wp_ids: tuple[str, ...]) -> ResolvedWorkspace:
    return ResolvedWorkspace(
        mission_slug=mission_slug,
        wp_id=wp_ids[0],
        execution_mode="code_change",
        mode_source="test",
        resolution_kind="lane_workspace",
        workspace_name="lane-a",
        worktree_path=Path("."),
        branch_name=None,
        lane_id="lane-a",
        lane_wp_ids=list(wp_ids),
    )


def _coord_mission_with_mate_in_progress(tmp_path: Path) -> tuple[Path, str]:
    """A ``lanes_with_coord`` Mission whose WP02 is ``in_progress`` on the coordination branch,
    with the coordination worktree removed (branch kept): ``CoordState.UNMATERIALIZED``."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    result = _create_mission(repo, "lane-mates-door", MissionTopology.LANES_WITH_COORD)
    mission_slug = result.mission_slug
    status_dir = placement_seam(repo, mission_slug).read_dir(MissionArtifactKind.STATUS_STATE)
    seed_wp_lane(status_dir, mission_slug, "WP02", "in_progress")
    coord_root = CoordinationWorkspace.worktree_path(repo, mission_slug, str(result.meta["mid8"]))
    _git(coord_root, "add", "-A")
    _git(coord_root, "commit", "-q", "--no-verify", "-m", "status: WP02 in_progress")
    _git(repo, "worktree", "remove", "--force", str(coord_root))
    assert not coord_root.exists()
    return repo, mission_slug


def test_advisory_reads_the_coordination_branch_when_the_worktree_is_unmaterialized(tmp_path: Path) -> None:
    repo, mission_slug = _coord_mission_with_mate_in_progress(tmp_path)

    writers = shared_workspace_writers(repo, mission_slug, "WP01", _lane_workspace(mission_slug, ("WP01", "WP02")), "me")

    assert writers == [SharedWorkspaceWriter(mission_slug, "WP02", "in_progress", "fixture")]
