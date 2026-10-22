"""Regression: a committed or unreadable review lock refuses ``agent action review`` before the claim (#6386).

Per ADR 2026-07-17-1 (regression-test discipline) this file reproduces #6386
against the REAL CLI in the LANES topology. The reported run committed a
``.spec-kitty/review-lock.json`` holding ``{}`` to the lane branch. Then
``agent action review`` recorded ``chore: Start WP01 review`` and moved the WP
to ``in_review``, and only afterwards read the lock and crashed with
``ReviewLock.__init__() missing 5 required positional arguments``. A re-run
added another start-review commit and crashed again.

After the fix the lock that the review would acquire (the file in an existing
workspace, or the blob a new workspace checks out) is inspected before the
claim. A lock git tracks is refused with ``REVIEW_LOCK_COMMITTED`` whatever its
content (operator ruling on the PR: a tracked lock is rewritten by every review
and deleted by its release, which left the lane dirty and blocked
``consolidate``); an untracked lock that cannot be read is refused with
``REVIEW_LOCK_UNREADABLE``. Either way the refusal names the file and the
remedy, and nothing is mutated. A re-run after the remedy succeeds.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.review.lock import LOCK_DIR, LOCK_FILE, ReviewLock
from specify_cli.status.store import read_events
from tests.terminus import conftest as harness
from tests.terminus.conftest import CoordMission, git_rev, run_terminus
from tests.terminus.lanes_fixture import build_lanes_mission
from tests.terminus.test_review_sees_teammate_fix import _make_for_review
from tests._support.two_clone import isolated_git_env

pytestmark = [pytest.mark.regression, pytest.mark.integration, pytest.mark.git_repo]

REVIEWER = "reviewer-renata"
_LOCK_REL = f"{LOCK_DIR}/{LOCK_FILE}"


def _review(m: CoordMission) -> tuple[int, str]:
    result = run_terminus(m, ["agent", "action", "review", "WP01", "--agent", REVIEWER, "--mission", m.slug])
    return result.returncode, " ".join((result.stdout + result.stderr).split())


def _lane_worktree(m: CoordMission) -> Path:
    return m.repo / ".worktrees" / f"{m.slug}-lane-a"


def _commit_lock_on_lane(m: CoordMission, scratch: Path, content: str | None) -> None:
    """Commit (or, with ``None``, delete) the lock file on the lane branch, as an agent's ``git add -A`` would."""
    harness._git(m.repo, "worktree", "add", "-q", str(scratch), m.lane_branches["WP01"])
    lock = scratch / _LOCK_REL
    if content is None:
        harness._git(scratch, "rm", "-q", _LOCK_REL)
    else:
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text(content)
        harness._git(scratch, "add", "-A")
    harness._git(scratch, "commit", "-qm", "agent commit")
    harness._git(m.repo, "worktree", "remove", "--force", str(scratch))


def _review_events(m: CoordMission) -> list[tuple[str, str]]:
    return [(str(e.from_lane), str(e.to_lane)) for e in read_events(m.feature_dir)]


@pytest.fixture
def mission(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> CoordMission:
    isolated_git_env(monkeypatch, tmp_path)
    return build_lanes_mission(tmp_path / "a", wps=("WP01",))


def test_committed_unreadable_lock_is_refused_before_the_claim(mission: CoordMission, tmp_path: Path) -> None:
    """The reported shape: ``{}`` committed on the lane; no review workspace exists yet."""
    m = mission
    _commit_lock_on_lane(m, tmp_path / "agent", "{}")
    _make_for_review(m)
    events_before = _review_events(m)
    target_before = git_rev(m.repo, m.target_branch)

    code, out = _review(m)

    assert code == 1, out
    assert "REVIEW_LOCK_COMMITTED" in out and "cannot be read (missing field(s)" in out
    assert "missing 5 required positional arguments" not in out
    assert _LOCK_REL in out and m.lane_branches["WP01"] in out
    assert f"git worktree add {_lane_worktree(m)} {m.lane_branches['WP01']}" in out
    assert f"git -C {_lane_worktree(m)} rm -q {_LOCK_REL}" in out, "the remedy removes the lock from the branch"
    assert _review_events(m) == events_before, "the claim must not run"
    assert git_rev(m.repo, m.target_branch) == target_before, "no start-review commit"
    assert not _lane_worktree(m).exists(), "no workspace is created for a refused review"

    # Re-running without the remedy is refused the same way and still mutates nothing.
    code, out = _review(m)
    assert code == 1 and "REVIEW_LOCK_COMMITTED" in out
    assert git_rev(m.repo, m.target_branch) == target_before

    # Remedy: remove the lock from the lane branch, then review again.
    _commit_lock_on_lane(m, tmp_path / "agent-fix", None)
    code, out = _review(m)
    assert code == 0, out
    assert _review_events(m)[-1] == ("for_review", "in_review")
    assert json.loads((_lane_worktree(m) / _LOCK_REL).read_text())["agent"] == REVIEWER


def test_committed_readable_lock_is_refused_and_the_lane_stays_clean(mission: CoordMission, tmp_path: Path) -> None:
    """A readable lock committed on the lane (stale PID) was overwritten in place, dirtying the tracked file."""
    m = mission
    stale = {"worktree_path": "/elsewhere", "wp_id": "WP01", "agent": "someone", "started_at": "2026-10-01T00:00:00+00:00", "pid": 1}
    _commit_lock_on_lane(m, tmp_path / "agent", json.dumps(stale))
    _make_for_review(m)
    events_before = _review_events(m)
    target_before = git_rev(m.repo, m.target_branch)

    code, out = _review(m)

    assert code == 1, out
    assert "REVIEW_LOCK_COMMITTED" in out and "is tracked by git." in out
    assert _review_events(m) == events_before
    assert git_rev(m.repo, m.target_branch) == target_before
    assert not _lane_worktree(m).exists()

    _commit_lock_on_lane(m, tmp_path / "agent-fix", None)
    code, out = _review(m)
    assert code == 0, out
    worktree = _lane_worktree(m)
    assert harness._git(worktree, "status", "--porcelain").stdout == ""
    ReviewLock.release(worktree)  # what an approval or rejection does
    assert harness._git(worktree, "status", "--porcelain").stdout == "", "release leaves no tracked deletion behind"


def test_rerun_after_the_crash_state_is_refused_then_recovers(mission: CoordMission) -> None:
    """The state the old crash left: WP ``in_review``, workspace present, corrupt lock on disk."""
    m = mission
    _make_for_review(m)
    code, out = _review(m)
    assert code == 0, out
    lock = _lane_worktree(m) / _LOCK_REL
    lock.write_text("{}")
    events_before = _review_events(m)
    target_before = git_rev(m.repo, m.target_branch)

    code, out = _review(m)

    assert code == 1, out
    assert "REVIEW_LOCK_UNREADABLE" in out
    assert str(lock) in out
    assert _review_events(m) == events_before
    assert git_rev(m.repo, m.target_branch) == target_before
    assert lock.read_text() == "{}", "the refusal never rewrites the lock it could not verify"

    lock.unlink()
    code, out = _review(m)
    assert code == 0, out
    assert json.loads(lock.read_text())["agent"] == REVIEWER


def test_review_workspace_keeps_the_lock_out_of_git(mission: CoordMission) -> None:
    """A workspace created by review excludes ``.spec-kitty/``, so ``git add -A`` cannot track the lock (#5434)."""
    m = mission
    _make_for_review(m)

    code, out = _review(m)

    assert code == 0, out
    worktree = _lane_worktree(m)
    assert (worktree / _LOCK_REL).exists()
    assert harness._git(worktree, "status", "--porcelain").stdout == ""
