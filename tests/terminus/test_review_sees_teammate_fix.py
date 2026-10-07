"""Regression: ``agent action review`` reviews the teammate's pushed fix, not the stale local lane (#5758).

Per ADR 2026-07-17-1 (regression-test discipline) this file reproduces the P0
shape from #5758 against the REAL CLI and a REAL bare remote, in the LANES
topology (status lives on the target branch):

* clone A is the reviewer's clone: its local lane holds ``v1``;
* clone B is the implementer's clone: it pushes ``v2`` ("fix after rejection")
  to the lane on the shared remote;
* A pulls the target branch only (that carries the ``for_review`` status, never
  the lane) and runs ``agent action review`` again.

Before the fix the review workspace stayed on ``v1`` (the rejected code), and an
approval then stamped and consolidated ``v1``. After the fix review brings the
lane to the remote tip first (or creates the workspace from the remote lane when
no local lane exists), so ``v2`` is what is reviewed and what lands.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from specify_cli.review.lock import ReviewLock
from tests.terminus import conftest as harness
from tests.terminus.conftest import CoordMission, git_rev, run_terminus
from tests.terminus.lanes_fixture import build_lanes_mission
from tests._support.two_clone import attach_and_push, clone_from, isolated_git_env, make_bare_remote

pytestmark = [pytest.mark.regression, pytest.mark.integration, pytest.mark.git_repo]

REVIEWER = "reviewer-renata"
_CODE = "src/pkg/wp01.py"
_V2 = "def wp01() -> int:\n    return 2\n"


@dataclass
class TwoClone:
    """Reviewer clone A (the fixture repo), the shared bare remote, and implementer clone B."""

    mission: CoordMission
    bare: Path
    clone_b: Path

    @property
    def lane(self) -> str:
        return self.mission.lane_branches["WP01"]

    @property
    def lane_worktree(self) -> Path:
        return self.mission.repo / ".worktrees" / f"{self.mission.slug}-lane-a"

    def review(self) -> tuple[int, str]:
        result = run_terminus(self.mission, ["agent", "action", "review", "WP01", "--agent", REVIEWER, "--mission", self.mission.slug])
        return result.returncode, result.stdout + result.stderr

    def push_fix_from_b(self) -> str:
        """Clone B commits ``v2`` on the lane and pushes it; return the new tip."""
        b = self.clone_b
        harness._git(b, "fetch", "-q", "origin")
        harness._git(b, "checkout", "-q", "-B", self.lane, f"origin/{self.lane}")
        (b / _CODE).write_text(_V2)
        harness._git(b, "commit", "-qam", "fix v2 after rejection")
        harness._git(b, "push", "-q", "origin", f"{self.lane}:refs/heads/{self.lane}")
        return git_rev(b, "HEAD")

    def a_fetches_target_only(self) -> None:
        """A learns the target (and so the ``for_review`` status) but nothing about the lane."""
        harness._git(self.mission.repo, "fetch", "-q", "origin", self.mission.target_branch)


def _make_for_review(m: CoordMission) -> None:
    """Rewrite the fixture's approved status log so WP01 is ``for_review`` and ignore ``.worktrees/``."""
    chain = harness._APPROVE_CHAIN[:3]
    claim_head = git_rev(m.repo, m.lane_branches["WP01"])
    events = [harness._event(m, "WP01", frm, to, policy_metadata={"lane_head": claim_head}) for frm, to in chain]
    (m.feature_dir / "status.events.jsonl").write_text("".join(json.dumps(e, sort_keys=True) + "\n" for e in events))
    (m.repo / ".gitignore").write_text(".worktrees/\n")
    harness._git(m.repo, "add", ".")
    harness._git(m.repo, "commit", "-qm", "chore: WP01 for_review")
    harness._git(m.repo, "branch", "-f", m.coord_branch, m.target_branch)


@pytest.fixture
def two_clone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TwoClone:
    isolated_git_env(monkeypatch, tmp_path)
    m = build_lanes_mission(tmp_path / "a", wps=("WP01",))
    _make_for_review(m)
    bare = make_bare_remote(tmp_path)
    attach_and_push(m.repo, bare, [m.target_branch, m.coord_branch, m.lane_branches["WP01"]])
    clone_b = clone_from(bare, tmp_path / "clone-b")
    return TwoClone(mission=m, bare=bare, clone_b=clone_b)


def test_re_review_reviews_the_teammate_fix(two_clone: TwoClone) -> None:
    """Arm A: a workspace already exists at v1; B pushes v2; the re-review shows v2."""
    code, out = two_clone.review()
    assert code == 0, out
    assert "return 2" not in (two_clone.lane_worktree / _CODE).read_text()

    new_tip = two_clone.push_fix_from_b()
    two_clone.a_fetches_target_only()
    code, out = two_clone.review()

    assert code == 0, out
    assert (two_clone.lane_worktree / _CODE).read_text() == _V2, "review must show the pushed fix, not the stale lane"
    assert git_rev(two_clone.mission.repo, two_clone.lane) == new_tip
    assert f"Updated {two_clone.lane} from origin/{two_clone.lane}" in out


def test_review_without_local_lane_creates_workspace_from_the_remote_lane(two_clone: TwoClone) -> None:
    """Arm B: no local lane in A at all; the workspace is created from the remote lane, not from HEAD."""
    new_tip = two_clone.push_fix_from_b()
    harness._git(two_clone.mission.repo, "branch", "-D", two_clone.lane)
    two_clone.a_fetches_target_only()  # NOT a full fetch: the review step must refresh the lane itself

    code, out = two_clone.review()

    assert code == 0, out
    assert (two_clone.lane_worktree / _CODE).read_text() == _V2
    assert git_rev(two_clone.mission.repo, two_clone.lane) == new_tip
    assert f"Created review workspace from origin/{two_clone.lane}" in out


def test_consolidate_lands_the_reviewed_fix(two_clone: TwoClone) -> None:
    """Arm C (SC-002): the approved-and-consolidated code is v2, never the rejected v1."""
    m = two_clone.mission
    code, out = two_clone.review()
    assert code == 0, out
    two_clone.push_fix_from_b()
    two_clone.a_fetches_target_only()
    code, out = two_clone.review()
    assert code == 0, out

    ReviewLock.release(two_clone.lane_worktree)  # approval releases the reviewer's lock
    approved = harness._event(m, "WP01", "in_review", "approved", policy_metadata={"lane_head": git_rev(m.repo, two_clone.lane)})
    log = m.feature_dir / "status.events.jsonl"
    log.write_text(log.read_text() + json.dumps(approved, sort_keys=True) + "\n")
    harness._git(m.repo, "add", "-A", "kitty-specs")
    harness._git(m.repo, "commit", "-qm", "chore: WP01 approved at the reviewed tip")

    result = run_terminus(m, ["consolidate", "--mission", m.slug, "--yes"])

    assert result.returncode == 0, result.stdout + result.stderr
    landed = harness._git(m.repo, "show", f"{m.target_branch}:{_CODE}").stdout
    assert landed == _V2


def test_refused_review_leaves_status_and_lock_untouched(two_clone: TwoClone) -> None:
    """A diverged lane is refused before the review claim: no ``in_review`` event, no review lock."""
    m = two_clone.mission
    code, out = two_clone.review()
    assert code == 0, out
    ReviewLock.release(two_clone.lane_worktree)
    # The lane moves both ways: A commits locally, B pushes a different fix.
    two_clone.push_fix_from_b()
    (two_clone.lane_worktree / _CODE).write_text("def wp01() -> int:\n    return 99\n")
    harness._git(two_clone.lane_worktree, "commit", "-qam", "local only")
    log = m.feature_dir / "status.events.jsonl"
    events_before = log.read_text()
    local_tip = git_rev(m.repo, two_clone.lane)

    code, out = two_clone.review()

    assert code == 1
    assert "ORIGIN_LANE_DIVERGED" in " ".join(out.split())
    assert log.read_text() == events_before
    assert git_rev(m.repo, two_clone.lane) == local_tip
    assert not (two_clone.lane_worktree / ".spec-kitty" / "review-lock.json").exists()
