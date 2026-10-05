"""Residual pin for the approved-bound check (#5668): content inside a merge commit is not seen.

The approved-bound check, at claim time and again at the gate, asks which commits a
lane holds beyond what review approved, and it skips merge commits: the tool itself
makes merge commits (a dependency lane merged into a dependent lane, a mission branch
merged forward), and a merge commit carries no content of its own when it merges two
histories. A merge commit CAN carry content, though: one whose tree adds a file that
neither parent has (an "evil merge"). The check does not see that file, so a lane
approved at one tip and then given such a merge commit still consolidates.

The shape is out of scope for mission approved-claim-bound (spec, Known residuals). Dropping
the merge skip would not close it cleanly: ``git show`` lists a merge commit's paths that differ
from every parent, so it would see this file, but it would also see a source file the lane
auto-rebase resolved after approval (``test_approved_bound.py::_conflict_resolved_merge`` pins
that the tool's own resolution passes), and refuse a legitimate mission. A sound check has to
tell a tool-made resolution from an operator-made one. This test pins the ideal behaviour (the
refusal ``LANE_MOVED_AFTER_APPROVAL``) as a strict expected failure, so the day the
check learns to see it the test turns red and the marker is removed.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.terminus.conftest import CoordMission, git_rev, run_terminus
from tests.terminus.mixed_lane_support import collapse
from tests.terminus.post_approval_support import LATE_CONTENT, LATE_PATH, build_post_approval_mission, lane_worktree

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_CODE = "LANE_MOVED_AFTER_APPROVAL"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()


def _add_evil_merge(mission: CoordMission) -> str:
    """Make lane-a's tip a merge commit of its approved tip and the mission branch tip whose tree adds ``LATE_PATH``.

    The second parent is an ancestor of the lane (the lane was cut from the mission branch), so the merge
    commit changes nothing but the added file: a tree that left out a parent's own changes would revert them.
    """
    worktree = lane_worktree(mission, "lane-a")
    anchor = git_rev(mission.repo, mission.coord_branch)
    late_file = worktree / LATE_PATH
    late_file.parent.mkdir(parents=True, exist_ok=True)
    late_file.write_text(LATE_CONTENT, encoding="utf-8")
    _git(worktree, "add", LATE_PATH)
    tree = _git(worktree, "write-tree")
    merge = _git(worktree, "commit-tree", tree, "-p", "HEAD", "-p", anchor, "-m", "merge: carries a file neither parent has")
    _git(worktree, "reset", "--hard", merge)
    return merge


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="content inside a merge commit is not seen by the approved-bound check; tracked in #5721 as a named residual of mission approved-claim-bound",
)
def test_content_inside_a_merge_commit_after_approval_is_refused(tmp_path: Path) -> None:
    mission = build_post_approval_mission(tmp_path, "lanes")
    _add_evil_merge(mission)

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])
    flat = collapse(result.stdout + "\n" + result.stderr)

    assert result.returncode != 0, f"a merge commit that adds content after approval must be refused, got exit 0:\n{flat}"
    assert _CODE in flat, f"expected {_CODE}:\n{flat}"
