"""#7311: a mission-side change the lane already contains is not an overlap.

Fixture (criss-cross, as in the real consolidation): the planning lane P and
lane L1 fork from main. L0 incorporates P and touches only ``src/x.py``; L1
changes ``src/f.py``. L2 depends on L1 and P (it merges both) and then edits
``src/f.py`` further. The mission branch merges L0 then L1. L2 and the mission
branch have two merge bases (P's and L1's tips); from P's tip both sides show
``src/f.py`` changed, yet the only mission-side change to it is L1's commit,
which L2 already contains.
"""

import os
import subprocess

import pytest

from specify_cli.lanes import stale_check
from specify_cli.lanes.models import ExecutionLane
from specify_cli.lanes.stale_check import check_lane_staleness

pytestmark = pytest.mark.git_repo

MISSION = "kitty/mission-m"
L2 = "kitty/mission-m-lane-f"


def _env():
    return {**os.environ, "GIT_EDITOR": "true", "GIT_MERGE_AUTOEDIT": "no"}


def _git(repo, *args):
    return subprocess.run(["git", *args], cwd=str(repo), capture_output=True, check=True, env=_env(), text=True).stdout.strip()


@pytest.fixture(autouse=True)
def _planning_merge_base(monkeypatch):
    """Pin the merge base git reports to the planning tip.

    L2 and the mission branch have two merge bases (the planning tip and L1's
    tip); ``git merge-base`` reports one of them, and which one depends on
    commit ordering. The real #7311 run got the older one, so pin it here.
    """
    monkeypatch.setattr(stale_check, "git_merge_base", lambda repo, a, b: _git(repo, "rev-parse", "planning"))


def _commit(repo, path, content, msg):
    (repo / path).parent.mkdir(parents=True, exist_ok=True)
    (repo / path).write_text(content)
    _git(repo, "add", path)
    _git(repo, "commit", "-m", msg)


def _lane():
    return ExecutionLane(
        lane_id="lane-f",
        wp_ids=("WP09",),
        write_scope=("src/**",),
        predicted_surfaces=(),
        depends_on_lanes=("lane-e",),
        parallel_group=1,
    )


def _build(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "T")
    _commit(repo, "src/f.py", "base\n", "init")
    _git(repo, "branch", MISSION)
    _git(repo, "checkout", "-b", "l1", "main")
    _commit(repo, "src/f.py", "l1\n", "L1 change to f")
    _git(repo, "checkout", "-b", "planning", "main")
    _commit(repo, "kitty-specs/m/plan.md", "plan\n", "planning")
    _git(repo, "checkout", "-b", "l0", "main")
    _git(repo, "merge", "--no-ff", "-m", "dep P into l0", "planning")
    _commit(repo, "src/x.py", "x\n", "L0 change")
    _git(repo, "checkout", "-b", L2, "l1")
    _git(repo, "merge", "--no-ff", "-m", "dep P into l2", "planning")
    _commit(repo, "src/f.py", "l1\nl2\n", "L2 change to f")
    _git(repo, "checkout", MISSION)
    _git(repo, "merge", "--no-ff", "-m", "merge l0", "l0")
    _git(repo, "merge", "--no-ff", "-m", "merge l1", "l1")
    _git(repo, "checkout", "main")
    return repo


def test_change_lane_already_contains_is_not_stale(tmp_path):
    repo = _build(tmp_path)
    result = check_lane_staleness(_lane(), L2, MISSION, repo)
    assert result.is_stale is False, result.stale_files


def test_mission_change_lane_lacks_still_stale(tmp_path):
    repo = _build(tmp_path)
    _git(repo, "checkout", MISSION)
    _commit(repo, "src/f.py", "l1\nmission\n", "mission-side change to f")
    _git(repo, "checkout", "main")
    result = check_lane_staleness(_lane(), L2, MISSION, repo)
    assert result.is_stale is True
    assert result.stale_files == ["src/f.py"]


def test_mission_merge_resolution_lane_lacks_still_stale(tmp_path):
    """A change introduced only by a merge's conflict resolution still counts."""
    repo = _build(tmp_path)
    _git(repo, "checkout", "-b", "l3", "main")
    _commit(repo, "src/f.py", "l3\n", "L3 change to f")
    _git(repo, "checkout", MISSION)
    subprocess.run(["git", "merge", "--no-ff", "-m", "merge l3", "l3"], cwd=str(repo), capture_output=True, env=_env())
    (repo / "src/f.py").write_text("resolved\n")
    _git(repo, "add", "src/f.py")
    _git(repo, "commit", "--no-edit")
    _git(repo, "checkout", "main")
    result = check_lane_staleness(_lane(), L2, MISSION, repo)
    assert result.is_stale is True
    assert "src/f.py" in result.stale_files


def test_mission_octopus_merge_own_change_lane_lacks_still_stale(tmp_path):
    """git skips an octopus merge's own resolution under ``--diff-merges=remerge``.

    A 3-parent merge on the mission branch whose tree folds in ``src/f.py`` (and
    nothing the parents carry) is mission-side work the lane lacks.
    """
    repo = _build(tmp_path)
    _git(repo, "checkout", MISSION)
    head = _git(repo, "rev-parse", "HEAD")
    side1 = _git(repo, "commit-tree", f"{head}^{{tree}}", "-p", head, "-m", "side one")
    side2 = _git(repo, "commit-tree", f"{head}^{{tree}}", "-p", head, "-m", "side two")
    (repo / "src/f.py").write_text("l1\noctopus\n")
    _git(repo, "add", "src/f.py")
    tree = _git(repo, "write-tree")
    octo = _git(repo, "commit-tree", tree, "-p", head, "-p", side1, "-p", side2, "-m", "octopus")
    _git(repo, "reset", "-q", "--hard", octo)
    _git(repo, "checkout", "main")
    result = check_lane_staleness(_lane(), L2, MISSION, repo)
    assert result.is_stale is True
    assert result.stale_files == ["src/f.py"]
