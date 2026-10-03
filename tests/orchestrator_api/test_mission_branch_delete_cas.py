"""orchestrator-api mission-branch delete is a compare-and-swap, not ``git branch -D``.

``_apply_lane_merge_cleanup`` used to run ``git branch -D <mission_branch>`` with
``check_return=False``: a commit that landed on the mission branch after the merge
finished (a concurrent status emit) was made unreachable and the command still
reported success -- the same defect the CLI consolidation fixed with
``delete_branch_ref``. The branch tip is now read at the start of the cleanup and
the delete only proceeds while the branch is still there; a moved tip keeps the
branch and the merge reports a failure.

Drives the REAL ``_apply_lane_merge_cleanup``; the only seam is a concurrency
injection that makes a real commit on the mission branch while the (real) lane
worktree removal runs, i.e. inside the window the compare-and-swap protects.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from specify_cli.core.paths import RetentionDecision
from specify_cli.git import destructive_guard
from specify_cli.git.destructive_guard import RemoveResult
from specify_cli.lanes.branch_naming import worktree_path
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.orchestrator_api.commands import _apply_lane_merge_cleanup

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox, pytest.mark.regression]

SLUG = "orch-cas-fixture-01M5570O"
MISSION_BRANCH = f"kitty/mission-{SLUG}"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def _branch_tip(repo: Path) -> str | None:
    ref = f"refs/heads/{MISSION_BRANCH}"
    probe = subprocess.run(["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", ref], capture_output=True, text=True, check=False)
    return probe.stdout.strip() if probe.returncode == 0 else None


def _manifest() -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug=SLUG,
        mission_id=SLUG,
        mission_branch=MISSION_BRANCH,
        target_branch="main",
        lanes=[ExecutionLane(lane_id="lane-a", wp_ids=("WP01",), write_scope=(), predicted_surfaces=(), depends_on_lanes=(), parallel_group=0)],
        computed_at="2026-01-01T00:00:00+00:00",
        computed_from="test",
    )


def _retention() -> RetentionDecision:
    return RetentionDecision(
        delete_branch=True,
        remove_worktree=True,
        teardown_coordination=False,
        branch_source="cli",
        worktree_source="cli",
        warnings=(),
        override_notices=(),
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    path = tmp_path / "repo"
    path.mkdir()
    _git(path, "init", "-q", "-b", "main")
    _git(path, "config", "user.email", "t@example.com")
    _git(path, "config", "user.name", "Test")
    _git(path, "config", "commit.gpgsign", "false")
    (path / "README.md").write_text("seed\n", encoding="utf-8")
    _git(path, "add", "-A")
    _git(path, "commit", "-q", "-m", "seed")
    _git(path, "branch", MISSION_BRANCH)
    _git(path, "worktree", "add", "--detach", str(worktree_path(path, SLUG, lane_id="lane-a")))
    return path


def _land_commit_on_mission_branch(repo: Path) -> str:
    tree = _git(repo, "rev-parse", f"{MISSION_BRANCH}^{{tree}}")
    late = _git(repo, "-c", "user.name=Late", "-c", "user.email=late@example.com", "commit-tree", tree, "-p", MISSION_BRANCH, "-m", "late status emit")
    _git(repo, "update-ref", f"refs/heads/{MISSION_BRANCH}", late)
    return late


def test_unmoved_mission_branch_is_deleted(repo: Path) -> None:
    _apply_lane_merge_cleanup(repo, SLUG, _manifest(), retention=_retention(), mission_branch_deletable=True)

    assert _branch_tip(repo) is None


def test_mission_branch_that_moved_during_cleanup_is_kept_and_the_merge_fails(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    real_remove = destructive_guard.guarded_worktree_remove
    landed: list[str] = []

    def remove_after_late_commit(worktree: Path, *, retain: bool, is_residue: Callable[[str], bool]) -> RemoveResult:
        landed.append(_land_commit_on_mission_branch(repo))
        return real_remove(worktree, retain=retain, is_residue=is_residue)

    monkeypatch.setattr(destructive_guard, "guarded_worktree_remove", remove_after_late_commit)

    with pytest.raises(RuntimeError) as raised:  # merge_mission envelopes a RuntimeError as a failure
        _apply_lane_merge_cleanup(repo, SLUG, _manifest(), retention=_retention(), mission_branch_deletable=True)

    assert landed, "the injection never ran"
    assert _branch_tip(repo) == landed[0], "the late commit must stay reachable on the kept branch"
    assert MISSION_BRANCH in str(raised.value)
    assert f"git log main..{MISSION_BRANCH}" in str(raised.value)


def test_retained_mission_branch_is_never_touched(repo: Path) -> None:
    before = _branch_tip(repo)

    _apply_lane_merge_cleanup(repo, SLUG, _manifest(), retention=_retention(), mission_branch_deletable=False)

    assert _branch_tip(repo) == before


def test_mission_branch_already_gone_is_not_an_error(repo: Path) -> None:
    _git(repo, "branch", "-D", MISSION_BRANCH)

    _apply_lane_merge_cleanup(repo, SLUG, _manifest(), retention=_retention(), mission_branch_deletable=True)

    assert _branch_tip(repo) is None
