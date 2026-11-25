"""#7747 Tier R confirm pass (2026-11-24): proof A credits only later approved work built on the lane's version.

Operator ruling 2026-11-24 on Tier R B1, option (b): a lane counts as landed through the Mission branch
only when every product path it changed landed with its own final blob, or was changed later by an
approved lane. "Later approved work" means a non-merge commit that is the other lane's OWN commit (the
same first-parent walk the authorship rule uses) and descends from this lane's last commit changing
that path. The reviewer's probes:

* B1: a parallel lane that edited another line of the same file is not "later";
* B2: an out-of-workflow commit that another lane only merged in (a resync) is not that lane's work;
* N1: a fast-forwarded lane has no authored product path, so the per-path check reads the lane's
  changes from ``diff <merge-base> <tip>`` instead.

Real repositories, the public ``lane_tip`` predicates.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

from specify_cli.lanes.lane_tip import is_absorbed_but_for_mission_bookkeeping, is_landed_through_mission_branch

pytestmark = [pytest.mark.git_repo]

_SLUG = "demo-01ABCDEF"
_COORD = f"kitty/mission-{_SLUG}"
_LANE_A = f"{_COORD}-lane-a"
_LANE_B = f"{_COORD}-lane-b"
_FILE = "src/p.py"
_BASE_TEXT = "".join(f"l{n} = {n}\n" for n in range(1, 11))


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    assert result.returncode == 0, f"git {' '.join(args)}: {result.stderr}"
    return result.stdout.strip()


def _write(cwd: Path, rel: str, text: str, message: str) -> str:
    (cwd / rel).parent.mkdir(parents=True, exist_ok=True)
    (cwd / rel).write_text(text, encoding="utf-8")
    _git(cwd, "add", rel)
    _git(cwd, "commit", "-q", "-m", message)
    return _git(cwd, "rev-parse", "HEAD")


def _edit_line(cwd: Path, line: int, value: str, message: str) -> str:
    text = (cwd / _FILE).read_text(encoding="utf-8").splitlines(keepends=True)
    text[line - 1] = f"l{line} = {value}\n"
    return _write(cwd, _FILE, "".join(text), message)


@dataclass
class Repo:
    root: Path
    coord: Path
    lane_a: Path
    lane_b: Path

    def tip(self, checkout: Path) -> str:
        return _git(checkout, "rev-parse", "HEAD")

    def squash(self) -> str:
        """The squash landing: the coordination tip's tree on ``main``."""
        _git(self.root, "checkout", "-q", self.tip(self.coord), "--", ".")
        _git(self.root, "commit", "-q", "--allow-empty", "-m", "squash merge of the Mission")
        return _git(self.root, "rev-parse", "HEAD")

    def proof_a(self, lane: Path, landing: str) -> bool:
        approved = (self.tip(self.lane_a), self.tip(self.lane_b))
        proven: bool = is_landed_through_mission_branch(self.root, self.tip(lane), self.tip(self.coord), landing, _SLUG, approved_tips=approved)
        return proven


@pytest.fixture
def repo(tmp_path: Path) -> Repo:
    """Two lanes forked from the coordination branch, both carrying ``src/p.py``."""
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.invalid")
    _git(root, "config", "user.name", "T")
    _git(root, "config", "commit.gpgsign", "false")
    _write(root, ".gitignore", ".worktrees/\n", "ignore")
    _write(root, _FILE, _BASE_TEXT, "base")
    coord = root / ".worktrees" / "coord"
    _git(root, "worktree", "add", "-q", "-b", _COORD, str(coord))
    lane_a = root / ".worktrees" / "lane-a"
    lane_b = root / ".worktrees" / "lane-b"
    _git(root, "worktree", "add", "-q", "-b", _LANE_A, str(lane_a), _COORD)
    _git(root, "worktree", "add", "-q", "-b", _LANE_B, str(lane_b), _COORD)
    return Repo(root=root, coord=coord, lane_a=lane_a, lane_b=lane_b)


def test_b1_a_parallel_lane_editing_another_line_does_not_supersede(repo: Repo) -> None:
    """Lanes A and B edit different lines of one file; an operator reverts A's line on coord."""
    _edit_line(repo.lane_a, 1, "'A'", "feat(WP01): line 1")
    _edit_line(repo.lane_b, 8, "'B'", "feat(WP02): line 8")
    _git(repo.coord, "merge", "-q", "--no-ff", "--no-edit", _LANE_A)
    _git(repo.coord, "merge", "-q", "--no-ff", "--no-edit", _LANE_B)
    _edit_line(repo.coord, 1, "1", "operator: revert lane A's line")
    landing = repo.squash()
    assert not is_absorbed_but_for_mission_bookkeeping(repo.root, repo.tip(repo.lane_a), landing, _SLUG)
    assert not repo.proof_a(repo.lane_a, landing)


def test_b2_an_out_of_workflow_rewrite_carried_in_by_a_resync_is_not_the_lanes_work(repo: Repo) -> None:
    """An operator rewrite on coord reaches lane B only through B's resync merge."""
    _edit_line(repo.lane_a, 1, "'A'", "feat(WP01): line 1")
    _write(repo.lane_b, "src/other.py", "b = 1\n", "feat(WP02): another file")
    _git(repo.coord, "merge", "-q", "--no-ff", "--no-edit", _LANE_A)
    _edit_line(repo.coord, 1, "'X'", "operator: rewrite lane A's line")
    _git(repo.lane_b, "merge", "-q", "--no-ff", "--no-edit", _COORD)  # the resync (auto-rebase)
    _git(repo.coord, "merge", "-q", "--no-ff", "--no-edit", _LANE_B)
    landing = repo.squash()
    assert not repo.proof_a(repo.lane_a, landing)


def test_b2_the_revert_variant_is_not_credited_either(repo: Repo) -> None:
    """Same as B2 with a revert: not credited because a resync merge is never the other lane's own work."""
    _edit_line(repo.lane_a, 1, "'A'", "feat(WP01): line 1")
    _write(repo.lane_b, "src/other.py", "b = 1\n", "feat(WP02): another file")
    _git(repo.coord, "merge", "-q", "--no-ff", "--no-edit", _LANE_A)
    _edit_line(repo.coord, 1, "1", "operator: revert lane A's line")
    _git(repo.lane_b, "merge", "-q", "--no-ff", "--no-edit", _COORD)
    _git(repo.coord, "merge", "-q", "--no-ff", "--no-edit", _LANE_B)
    landing = repo.squash()
    assert not repo.proof_a(repo.lane_a, landing)


def test_n1_a_fast_forwarded_lane_is_still_judged_per_path(repo: Repo) -> None:
    """Lane A is fast-forwarded onto the coordination merge holding its commit; an operator then reverts."""
    _edit_line(repo.lane_a, 1, "'A'", "feat(WP01): line 1")
    _git(repo.coord, "merge", "-q", "--no-ff", "--no-edit", _LANE_A)
    _git(repo.lane_a, "merge", "-q", "--ff-only", _COORD)  # the hand fast-forward
    _edit_line(repo.coord, 1, "1", "operator: revert lane A's line")
    landing = repo.squash()
    assert not repo.proof_a(repo.lane_a, landing)


def test_a_dependent_lane_building_on_the_lanes_line_still_supersedes_it(repo: Repo) -> None:
    """Positive control: lane B merges lane A, then rewrites A's line; lane A landed through B."""
    _edit_line(repo.lane_a, 1, "'A'", "feat(WP01): line 1")
    _git(repo.lane_b, "merge", "-q", "--no-ff", "--no-edit", _LANE_A)
    _edit_line(repo.lane_b, 1, "'B on A'", "feat(WP02): rework line 1")
    _git(repo.coord, "merge", "-q", "--no-ff", "--no-edit", _LANE_A)
    _git(repo.coord, "merge", "-q", "--no-ff", "--no-edit", _LANE_B)
    landing = repo.squash()
    assert not is_absorbed_but_for_mission_bookkeeping(repo.root, repo.tip(repo.lane_a), landing, _SLUG)
    assert repo.proof_a(repo.lane_a, landing)


def _rename(cwd: Path, new: str, message: str) -> str:
    _git(cwd, "mv", _FILE, new)
    _git(cwd, "commit", "-q", "-m", message)
    return _git(cwd, "rev-parse", "HEAD")


@pytest.mark.parametrize(
    "operator_change",
    [
        pytest.param(lambda coord: _edit_line(coord, 1, "'X'", "operator: rewrite lane A's line"), id="rewrite"),
        pytest.param(lambda coord: _edit_line(coord, 1, "1", "operator: revert lane A's line"), id="revert"),
        pytest.param(lambda coord: _rename(coord, "src/r.py", "operator: rename lane A's file"), id="rename"),
        pytest.param(lambda coord: _git(coord, "revert", "-m", "1", "--no-edit", "HEAD"), id="merge-revert"),
    ],
)
def test_confirm2_b1_coordination_history_a_lane_forked_from_is_not_its_own_work(repo: Repo, operator_change: Callable[[Path], str]) -> None:
    """Tier R confirm 2, B1: lane B forks from coord after an operator change to A's line, then edits only q.py.

    The coordination commits before B's fork point sit on B's first-parent chain; they are the
    Mission branch's history, not B's own work, so they never supersede lane A.
    """
    _edit_line(repo.lane_a, 1, "'A'", "feat(WP01): line 1")
    _git(repo.coord, "merge", "-q", "--no-ff", "--no-edit", _LANE_A)
    operator_change(repo.coord)
    _git(repo.lane_b, "merge", "-q", "--ff-only", _COORD)  # lane B forks from the coordination tip
    _write(repo.lane_b, "src/q.py", "q = 1\n", "feat(WP02): q.py only")
    _git(repo.coord, "merge", "-q", "--no-ff", "--no-edit", _LANE_B)
    landing = repo.squash()
    assert not is_absorbed_but_for_mission_bookkeeping(repo.root, repo.tip(repo.lane_a), landing, _SLUG)
    assert not repo.proof_a(repo.lane_a, landing)
