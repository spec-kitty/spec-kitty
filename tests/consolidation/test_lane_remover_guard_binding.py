"""The lane remover bound to the landed-removal guard (S5, WP16, FR-037, C-004, NFR-008).

``GuardedLaneRemover`` hands every lane removal that has a landing proof to
``guarded_landed_removal`` (ADR 2026-11-06-1): consolidate proves the landing with
the O3-local variant (the local target sits at the reconciliation PASS tip), pr-mode
with a named remote ref. A guard refusal keeps the lane with the guard's code.
Real repositories; the process probe is injected.
"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path

import pytest

from specify_cli.consolidation.lane_cleanup import (
    GuardedLaneRemover,
    LaneCleanupItem,
    LaneCleanupOutcome,
    LocalTargetAtPass,
    RemoteRef,
)
from specify_cli.coordination.coherence import NothingIsResidue
from specify_cli.git.destructive_guard import (
    LOCAL_TARGET_NOT_AT_PASS,
    NOT_LANDED_ON_NAMED_REMOTE,
    PROCESS_PROOF_UNAVAILABLE,
    WORKTREE_TIP_MOVED,
    DestructiveOpRefused,
    LandedRemoval,
    guarded_landed_removal,
)
from specify_cli.workspace.process_probe import ProcessProbeResult

pytestmark = [pytest.mark.git_repo]

_LANE_BRANCH = "kitty/mission-demo-01ABCDEF-lane-a"
_SRC = Path(__file__).resolve().parents[2] / "src" / "specify_cli" / "consolidation" / "lane_cleanup.py"


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


def _unavailable(paths: object) -> ProcessProbeResult:
    return ProcessProbeResult(available=False, detail="no /proc on this platform")


@pytest.fixture
def landed(tmp_path: Path) -> tuple[Path, Path, str]:
    """A repo whose lane (worktree under ``.worktrees/``) was consolidated into ``main``."""
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
    _git(root, "worktree", "add", "-q", "-b", _LANE_BRANCH, str(worktree))
    _git(worktree, "config", "user.email", "t@example.invalid")
    tip = _commit(worktree, "lane.py", "y = 2\n")
    _git(root, "merge", "-q", "--no-ff", "-m", "consolidate lane-a", _LANE_BRANCH)
    return root, worktree, tip


def _item(worktree: Path, tip: str) -> LaneCleanupItem:
    return LaneCleanupItem(lane_id="lane-a", worktree=worktree, branch=_LANE_BRANCH, expected_tip=tip)


def _at_pass(root: Path) -> LocalTargetAtPass:
    return LocalTargetAtPass(target_ref="main", passed_sha=_git(root, "rev-parse", "main"))


def test_absorbed_lane_removed_through_the_guard(landed: tuple[Path, Path, str]) -> None:
    root, worktree, tip = landed
    result = GuardedLaneRemover(root, context=NothingIsResidue(), probe=_idle).remove(_item(worktree, tip), landing=_at_pass(root))
    assert result.outcome is LaneCleanupOutcome.REMOVED, result
    assert not worktree.exists()
    assert _git(root, "branch", "--list", _LANE_BRANCH) == ""
    assert result.recreate and tip in result.recreate


def test_detached_mid_rebase_lane_kept_worktree_tip_moved(landed: tuple[Path, Path, str]) -> None:
    root, worktree, tip = landed
    _git(worktree, "checkout", "-q", "--detach")
    result = GuardedLaneRemover(root, context=NothingIsResidue(), probe=_idle).remove(_item(worktree, tip), landing=_at_pass(root))
    assert result.outcome is LaneCleanupOutcome.KEPT
    assert result.code == WORKTREE_TIP_MOVED
    assert worktree.exists()


def test_branch_advanced_after_claim_kept(landed: tuple[Path, Path, str]) -> None:
    root, worktree, tip = landed
    _commit(worktree, "late.py", "z = 3\n")
    result = GuardedLaneRemover(root, context=NothingIsResidue(), probe=_idle).remove(_item(worktree, tip), landing=_at_pass(root))
    assert result.outcome is LaneCleanupOutcome.KEPT
    assert result.code == WORKTREE_TIP_MOVED
    assert worktree.exists()
    assert _git(root, "branch", "--list", _LANE_BRANCH) != ""


def test_probe_unavailable_keeps_and_reports(landed: tuple[Path, Path, str]) -> None:
    root, worktree, tip = landed
    result = GuardedLaneRemover(root, context=NothingIsResidue(), probe=_unavailable).remove(_item(worktree, tip), landing=_at_pass(root))
    assert result.outcome is LaneCleanupOutcome.KEPT
    assert result.code == PROCESS_PROOF_UNAVAILABLE
    assert result.command == "spec-kitty doctor workspaces --prune"
    assert worktree.exists()


def test_local_target_moved_off_the_pass_tip_kept(landed: tuple[Path, Path, str]) -> None:
    root, worktree, tip = landed
    landing = LocalTargetAtPass(target_ref="main", passed_sha=_git(root, "rev-parse", "main~1"))
    result = GuardedLaneRemover(root, context=NothingIsResidue(), probe=_idle).remove(_item(worktree, tip), landing=landing)
    assert result.outcome is LaneCleanupOutcome.KEPT
    assert result.code == LOCAL_TARGET_NOT_AT_PASS
    assert worktree.exists()


def test_remote_ref_without_the_lane_kept_not_landed(landed: tuple[Path, Path, str], tmp_path: Path) -> None:
    root, worktree, tip = landed
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    _git(root, "remote", "add", "origin", str(origin))
    _git(root, "push", "-q", "origin", "main~1:refs/heads/main")
    _git(root, "fetch", "-q", "origin")
    landing = RemoteRef(remote="origin", ref="refs/remotes/origin/main")
    result = GuardedLaneRemover(root, context=NothingIsResidue(), probe=_idle).remove(_item(worktree, tip), landing=landing)
    assert result.outcome is LaneCleanupOutcome.KEPT
    assert result.code == NOT_LANDED_ON_NAMED_REMOTE
    assert worktree.exists()


def test_guard_local_variant_refuses_a_ref_outside_refs_heads(landed: tuple[Path, Path, str]) -> None:
    root, worktree, tip = landed
    removal = LandedRemoval(worktree=worktree, branch=_LANE_BRANCH, tip=tip, remote="", landing_ref="main", passed_sha=_git(root, "rev-parse", "main"))
    with pytest.raises(DestructiveOpRefused) as refused:
        guarded_landed_removal(root, removal, context=NothingIsResidue(), processes_in=lambda _p: False, absorbed=lambda _t, _r: True)
    assert refused.value.error_code == LOCAL_TARGET_NOT_AT_PASS
    assert worktree.exists()


def test_never_force_pin() -> None:
    """The bound remover never forces a removal: no ``--force`` / ``force=True`` in the module (C-004, O7)."""
    tree = ast.parse(_SRC.read_text(encoding="utf-8"))
    forced = [
        node.lineno
        for node in ast.walk(tree)
        if (isinstance(node, ast.Constant) and node.value in {"--force", "-f", "-D"})
        or (isinstance(node, ast.keyword) and node.arg == "force" and isinstance(node.value, ast.Constant) and node.value.value is True)
    ]
    assert forced == []
    called = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    assert "guarded_landed_removal" in called
