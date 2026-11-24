"""#7325: a lane with no usable landing proof is kept, never handed to the older remover.

``GuardedLaneRemover`` used to send these legs to ``MainTodayRemover``, whose branch delete compares
against the lane's own expected tip, so an unlanded lane's unique commit was a blind spot:

* no landing proof;
* a local proof whose reconciliation PASS anchor is empty;
* a lane whose worktree is gone while its branch remains;
* no tip to name.

Each is now kept with ``LANDING_PROOF_UNAVAILABLE`` and its branch is left as it is. A lane whose
worktree and branch are both gone is reported removed (nothing remains). The retained-branch leg
(worktree removed, branch kept by policy) keeps today's guarded worktree removal: it deletes no
branch (plan decision PD-1). Real repositories; the process probe is injected.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.consolidation import lane_cleanup
from specify_cli.consolidation.lane_cleanup import (
    BACKSTOP_COMMAND,
    GuardedLaneRemover,
    LaneCleanupItem,
    LaneCleanupOutcome,
    LaneCleanupReport,
    LaneRetention,
    LocalTargetAtPass,
    RemoteRef,
)
from specify_cli.coordination.coherence import NothingIsResidue
from specify_cli.workspace.process_probe import ProcessProbeResult

pytestmark = [pytest.mark.git_repo]

#: The kept code (a contract string, ``contracts/landing-proof.md``).
LANDING_PROOF_UNAVAILABLE = "LANDING_PROOF_UNAVAILABLE"

_LANE = "kitty/mission-demo-01ABCDEF-lane-a"


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    assert result.returncode == 0, f"git {' '.join(args)}: {result.stderr}"
    return result.stdout.strip()


def _commit(cwd: Path, name: str, content: str) -> str:
    (cwd / name).write_text(content, encoding="utf-8")
    _git(cwd, "add", name)
    _git(cwd, "commit", "-q", "-m", f"add {name}")
    return _git(cwd, "rev-parse", "HEAD")


def _idle(paths: object) -> ProcessProbeResult:
    return ProcessProbeResult(available=True)


@pytest.fixture
def landed(tmp_path: Path) -> tuple[Path, Path, str]:
    """A lane consolidated into ``main``; its worktree is still in place."""
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.invalid")
    _git(root, "config", "user.name", "T")
    _git(root, "config", "commit.gpgsign", "false")
    (root / ".gitignore").write_text(".worktrees/\n", encoding="utf-8")
    _git(root, "add", ".gitignore")
    _commit(root, "base.py", "x = 1\n")
    worktree = root / ".worktrees" / "demo-lane-a"
    _git(root, "worktree", "add", "-q", "-b", _LANE, str(worktree))
    tip = _commit(worktree, "lane.py", "y = 2\n")
    _git(root, "merge", "-q", "--no-ff", "-m", "consolidate lane-a", _LANE)
    return root, worktree, tip


def _remover(root: Path) -> GuardedLaneRemover:
    return GuardedLaneRemover(root, context=NothingIsResidue(), probe=_idle)


def _at_pass(root: Path) -> LocalTargetAtPass:
    return LocalTargetAtPass(target_ref="main", passed_sha=_git(root, "rev-parse", "main"))


def _item(worktree: Path | None, tip: str | None, branch: str | None = _LANE) -> LaneCleanupItem:
    return LaneCleanupItem(lane_id="lane-a", worktree=worktree, branch=branch, expected_tip=tip)


def _branch_tip(root: Path) -> str:
    return _git(root, "rev-parse", "--verify", "--quiet", f"refs/heads/{_LANE}")


def test_a_gone_worktree_with_a_unique_commit_keeps_the_branch(landed: tuple[Path, Path, str]) -> None:
    """The #7325 blind spot: the branch delete used to compare against the lane's own tip."""
    root, worktree, tip = landed
    _git(root, "worktree", "remove", str(worktree))
    unique = _git(root, "commit-tree", f"{tip}^{{tree}}", "-p", tip, "-m", "unlanded work")
    _git(root, "update-ref", f"refs/heads/{_LANE}", unique, tip)
    result = _remover(root).remove(_item(worktree, unique), landing=_at_pass(root))
    assert result.outcome is LaneCleanupOutcome.KEPT, result
    assert result.code == LANDING_PROOF_UNAVAILABLE
    assert _branch_tip(root) == unique
    assert result.command is None  # no worktree left for the prune backstop to judge
    assert _LANE in (result.remedy or "") and f"git diff main {_LANE}" in (result.remedy or "")
    assert "git log" not in (result.remedy or "")  # a squash landing rewrites commits: compare content
    [kept] = LaneCleanupReport(results=(result,)).render_lines()[1:3][1:]
    assert kept.strip() == f"Remedy: {result.remedy}", kept  # review cycle 1: never "then run: None"


def test_an_empty_pass_anchor_keeps_the_lane(landed: tuple[Path, Path, str]) -> None:
    root, worktree, tip = landed
    result = _remover(root).remove(_item(worktree, tip), landing=LocalTargetAtPass(target_ref="main", passed_sha=""))
    assert result.outcome is LaneCleanupOutcome.KEPT, result
    assert result.code == LANDING_PROOF_UNAVAILABLE
    assert worktree.exists() and _branch_tip(root) == tip
    assert result.command == BACKSTOP_COMMAND  # the worktree remains for the prune to judge
    lines = LaneCleanupReport(results=(result,)).render_lines()
    assert lines[2].strip() == f"Remedy: {result.remedy}, then run: {BACKSTOP_COMMAND}", lines


def test_no_landing_proof_keeps_the_lane(landed: tuple[Path, Path, str]) -> None:
    root, worktree, tip = landed
    result = _remover(root).remove(_item(worktree, tip), landing=None)
    assert result.outcome is LaneCleanupOutcome.KEPT, result
    assert result.code == LANDING_PROOF_UNAVAILABLE
    assert worktree.exists() and _branch_tip(root) == tip
    # Review cycle 1: no command naming a ref that is not one ("git log the target branch..").
    assert "git log" not in (result.remedy or ""), result.remedy
    assert _LANE in (result.remedy or "")


def test_no_tip_to_name_keeps_the_lane(landed: tuple[Path, Path, str]) -> None:
    """The worktree is there but its branch ref is gone and no tip was validated."""
    root, worktree, _tip = landed
    _git(worktree, "checkout", "-q", "--detach")
    _git(root, "branch", "-D", _LANE)
    result = _remover(root).remove(_item(worktree, None), landing=_at_pass(root))
    assert result.outcome is LaneCleanupOutcome.KEPT, result
    assert result.code == LANDING_PROOF_UNAVAILABLE
    assert worktree.exists()
    # Review cycle 1: the branch ref is gone, so the remedy must not name it as a revision.
    remedy = result.remedy or ""
    assert f"main..{_LANE}" not in remedy, remedy
    assert f"git rev-parse refs/spec-kitty/lane-tip/{_LANE}" in remedy and "git fsck --lost-found" in remedy, remedy
    assert "reflog" not in remedy  # a worktree still on the deleted branch has no reflog to read


def test_a_lane_with_nothing_left_is_removed(landed: tuple[Path, Path, str]) -> None:
    root, worktree, tip = landed
    _git(root, "worktree", "remove", str(worktree))
    _git(root, "branch", "-D", _LANE)
    result = _remover(root).remove(_item(worktree, tip), landing=_at_pass(root))
    assert result.outcome is LaneCleanupOutcome.REMOVED, result


def test_a_retained_branch_keeps_todays_worktree_removal(landed: tuple[Path, Path, str]) -> None:
    """PD-1: the worktree-only leg deletes no branch, so it stays on the guarded worktree removal."""
    root, worktree, tip = landed
    report = lane_cleanup.apply([_item(worktree, tip)], _remover(root), landing=_at_pass(root), retention=LaneRetention(delete_branch=False))
    [result] = report.results
    assert result.outcome is LaneCleanupOutcome.RETAINED_BY_POLICY, result
    assert "worktree removed; branch retained" in (result.detail or "")
    assert not worktree.exists()
    assert _branch_tip(root) == tip


def test_a_remote_landing_names_the_remote_ref_in_the_remedy(landed: tuple[Path, Path, str]) -> None:
    """``accept --mode pr`` / ``--push`` pass a remote ref: the remedy compares against that ref."""
    root, worktree, tip = landed
    _git(root, "worktree", "remove", str(worktree))
    result = _remover(root).remove(_item(worktree, tip), landing=RemoteRef(remote="origin", ref="refs/remotes/origin/main"))
    assert result.outcome is LaneCleanupOutcome.KEPT, result
    assert result.code == LANDING_PROOF_UNAVAILABLE
    assert f"git diff refs/remotes/origin/main {_LANE}" in (result.remedy or ""), result.remedy
    assert _branch_tip(root) == tip
