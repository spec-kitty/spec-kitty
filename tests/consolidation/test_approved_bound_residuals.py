"""Content inside a merge commit after approval is refused at claim time (#5668 residual, closed by FR-004).

The approved-bound check skips merge commits (``content_commits``): the tool makes them (a dependency lane
merged into a dependent lane, the Mission branch merged forward, a lane auto-rebase that resolved a conflict),
and a merge carries no content of its own when it merges two histories. A merge CAN carry content, though:
one whose tree adds a file neither parent has (an "evil merge"). ADR 2026-10-04-5 listed that shape as a
residual ("content inside a merge commit").

FR-004 closes it with its own code, ``RESOLUTION_MERGE_UNREVIEWED``, at claim time, before any branch moves.
A merge on an approved lane's spine that no approval stamp of its own lane reaches is judged by what it adds
beyond git's re-merge of its parents (``git show --remerge-diff``). The tool's own auto-rebase merges are
told apart by their auto-rebase record (``refs/spec-kitty/auto-rebase/<lane>/<sha>``, exact SHA), never by
the commit message or the parent shape: the merge below has the auto-rebase parent shape (lane tip, then
the Mission branch tip) and no record, so it is a hand merge and refuses.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from tests.terminus.conftest import CoordMission, git_rev, run_terminus
from tests.terminus.mixed_lane_support import collapse
from tests.terminus.post_approval_support import LATE_CONTENT, LATE_PATH, Topology, build_post_approval_mission, lane_worktree
from tests.terminus.rollback_harness import reflog_shas, state_path

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_CODE = "RESOLUTION_MERGE_UNREVIEWED"


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


def _reflog_lengths(mission: CoordMission) -> dict[str, int]:
    branches = dict.fromkeys([mission.target_branch, mission.coord_branch, *mission.lane_branches.values()])
    return {branch: len(reflog_shas(mission, branch)) for branch in branches}


@pytest.mark.parametrize("topology", ["lanes", "coord"])
def test_content_inside_a_merge_commit_after_approval_is_refused(tmp_path: Path, topology: Topology) -> None:
    mission = build_post_approval_mission(tmp_path, topology)
    merge = _add_evil_merge(mission)
    before = _reflog_lengths(mission)

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])
    flat = collapse(result.stdout + "\n" + result.stderr)

    assert result.returncode != 0, f"a merge commit that adds content after approval must be refused, got exit 0:\n{flat}"
    assert _CODE in flat, f"expected {_CODE}:\n{flat}"
    assert f"merge {merge[:7]}" in flat, flat
    # No mutation: no branch moved (a land-then-rollback leaves reflog entries even when the tip comes back) and no snapshot.
    assert _reflog_lengths(mission) == before, flat
    record = state_path(mission)
    assert record is None or not json.loads(record.read_text(encoding="utf-8")).get("pre_mutation_refs")
