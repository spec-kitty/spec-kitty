"""#5287: a remote-only coordination branch gets one complete, truthful remedy.

A fresh clone (or any checkout with no local head for the coordination branch)
used to be told the branch "has not fetched" (false: the clone has fetched it),
was always pointed at ``origin`` (the fixture's only remote is ``coord-remote``),
and was never told to create the local branch, the step that actually unblocks
reads. These tests drive the pre-existing entry point,
``CoordinationWorktreeUnmaterialized.for_mission``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from mission_runtime import MissionTopology
from specify_cli.coordination.surface_resolver import CoordinationWorktreeUnmaterialized
from tests._factories.coord_mission import CoordMission, make_prefix_coord_mission

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

_REMOTE = "coord-remote"


def _remote_only(tmp_path: Path) -> CoordMission:
    return make_prefix_coord_mission(tmp_path, MissionTopology.LANES_WITH_COORD, worktree="absent", remote_only=True)


def _refusal(coord: CoordMission) -> CoordinationWorktreeUnmaterialized:
    return CoordinationWorktreeUnmaterialized.for_mission(
        repo_root=coord.repo_root,
        mission_slug=coord.mission_dir_name,
        mid8=coord.mid8,
        coordination_branch=coord.coordination_branch,
        primary_candidate=coord.root_mission_dir,
    )


def test_remote_only_refusal_names_the_resolved_remote_and_the_branch_step(tmp_path: Path) -> None:
    coord = _remote_only(tmp_path)
    branch = coord.coordination_branch

    next_step = _refusal(coord).next_step

    assert f"branch {branch} {_REMOTE}/{branch}" in next_step
    assert f"spec-kitty doctor coordination --mission {coord.mission_dir_name} --fix" in next_step
    assert "has not fetched" not in next_step
    assert "not yet fetched" not in next_step
    assert " origin" not in next_step
    assert "origin/" not in next_step
    # The clone already holds refs/remotes/coord-remote/<b>: no fetch step is needed.
    assert " fetch " not in next_step


def test_remote_only_refusal_leads_with_a_targeted_fetch_when_the_tracking_ref_is_absent(tmp_path: Path) -> None:
    coord = _remote_only(tmp_path)
    branch = coord.coordination_branch
    subprocess.run(
        ["git", "-C", str(coord.repo_root), "update-ref", "-d", f"refs/remotes/{_REMOTE}/{branch}"],
        check=True,
        capture_output=True,
    )

    next_step = _refusal(coord).next_step

    fetch_step = f"fetch {_REMOTE} {branch}"
    branch_step = f"branch {branch} {_REMOTE}/{branch}"
    assert fetch_step in next_step
    assert branch_step in next_step
    assert next_step.index(fetch_step) < next_step.index(branch_step)
