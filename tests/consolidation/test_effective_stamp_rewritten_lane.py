"""A pre-sync stamp never stands in for a lane_head that is in this clone but off the lane (#7802, Tier R N1).

The pre-sync fallback exists for one shape: ``lane_head`` is the reviewer's sync merge, a
commit this clone never received. When ``lane_head`` IS in the clone and the lane no longer
reaches it, the lane was rewritten after the approval (force-pushed back to the pre-sync tip
plus new work). That must refuse ``not_on_lane``, never pass on the pre-sync stamp.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.consolidation.approved_bound import StampDetail, effective_stamp
from specify_cli.status import LANE_HEAD_KEY, LANE_HEAD_PRESYNC_KEY

pytestmark = pytest.mark.fast

_ABSENT = "e" * 40


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    (root / "a.txt").write_text("base\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")
    return root


def _branch_commit(repo: Path, branch: str, name: str) -> str:
    _git(repo, "switch", "-q", branch)
    (repo / f"{name}.txt").write_text(f"{name}\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", name)
    return _git(repo, "rev-parse", "HEAD")


def _merge(repo: Path, into: str, other: str) -> str:
    _git(repo, "switch", "-q", into)
    _git(repo, "merge", "-q", "--no-ff", "--no-edit", other)
    return _git(repo, "rev-parse", "HEAD")


def test_rewritten_lane_with_lane_head_in_clone_refuses_not_on_lane(repo: Path) -> None:
    _git(repo, "branch", "coord")
    _git(repo, "branch", "lane")
    presync = _branch_commit(repo, "lane", "implementer-x")
    _branch_commit(repo, "coord", "coord-1")
    lane_head = _merge(repo, "lane", "coord")  # the review sync merge M, approved
    # The lane is rewritten after the approval: back to X, then a new merge M' with other content.
    _git(repo, "reset", "-q", "--hard", presync)
    _branch_commit(repo, "coord", "coord-2")
    _merge(repo, "lane", "coord")
    assert _git(repo, "cat-file", "-t", lane_head) == "commit"  # M is still in this clone

    verdict = effective_stamp(repo, {LANE_HEAD_KEY: lane_head, LANE_HEAD_PRESYNC_KEY: presync}, "lane")

    assert verdict.stamp is None
    assert verdict.detail is StampDetail.NOT_ON_LANE


def test_lane_head_absent_from_clone_still_falls_back_to_the_presync_stamp(repo: Path) -> None:
    """Positive control on the same fixture shape: the reviewer's merge never reached this clone."""
    _git(repo, "branch", "lane")
    presync = _branch_commit(repo, "lane", "implementer-x")

    verdict = effective_stamp(repo, {LANE_HEAD_KEY: _ABSENT, LANE_HEAD_PRESYNC_KEY: presync}, "lane")

    assert verdict.stamp == presync
