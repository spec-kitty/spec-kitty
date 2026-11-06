"""Unit tests for ``specify_cli.consolidation.write_branch_bound`` (S8 tier 2, #7283).

Every content commit of a ``single_branch`` Mission branch must lie in some approved work
package's window ``(O_k, S_k]``. Real throwaway git repos, synthetic status events carrying
real SHAs as stamps.
"""

from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from specify_cli.consolidation.approved_bound import BoundRefusal, BoundRefusalCode, refusal_codes
from specify_cli.consolidation.write_branch_bound import (
    ApprovalWindow,
    approval_windows,
    check_write_branch,
    commits_outside_windows,
    render_write_branch_refusals,
)
from specify_cli.status import LANE_HEAD_KEY, Lane, StatusEvent

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_SLUG = "write-branch-bound-01M6QY1M"
_BRANCH = "kitty/mission-write-branch-bound-01M6QY1M"
_LANE = "lane-planning"


def _is_bookkeeping(path: str) -> bool:
    return path.startswith(f"kitty-specs/{_SLUG}/")


@dataclass
class _Repo:
    root: Path
    seq: int = 0
    events: list[StatusEvent] = field(default_factory=list)

    def git(self, *args: str) -> str:
        return subprocess.run(["git", "-C", str(self.root), *args], capture_output=True, text=True, check=True).stdout.strip()

    def commit(self, rel: str) -> str:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"x{self.seq}\n", encoding="utf-8")
        self.seq += 1
        self.git("add", rel)
        self.git("commit", "-qm", f"change {rel}")
        return self.head

    @property
    def head(self) -> str:
        return self.git("rev-parse", "HEAD")

    def event(self, wp_id: str, from_lane: Lane, to_lane: Lane, *, stamped: bool = True) -> None:
        self.seq += 1
        self.events.append(
            StatusEvent(
                event_id=f"e{self.seq}",
                mission_slug=_SLUG,
                wp_id=wp_id,
                from_lane=from_lane,
                to_lane=to_lane,
                at=f"2026-11-06T00:{self.seq // 60:02d}:{self.seq % 60:02d}Z",
                actor="bob",
                force=False,
                execution_mode="direct_repo",
                policy_metadata={LANE_HEAD_KEY: self.head} if stamped else None,
            )
        )

    def claim(self, wp_id: str, *, stamped: bool = True) -> None:
        self.event(wp_id, Lane.PLANNED, Lane.IN_PROGRESS, stamped=stamped)

    def approve(self, wp_id: str) -> None:
        self.event(wp_id, Lane.IN_REVIEW, Lane.APPROVED)

    def check(self, approved: tuple[str, ...] = ("WP01", "WP02"), anchors: tuple[str, ...] = ()) -> tuple[BoundRefusal, ...]:
        return check_write_branch(
            self.root,
            events=self.events,
            lane_id=_LANE,
            branch=_BRANCH,
            approved_wp_ids=approved,
            claim_base="base",
            anchors=anchors,
            is_bookkeeping=_is_bookkeeping,
        )


@pytest.fixture
def repo(tmp_path: Path) -> _Repo:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-qb", "main", str(root)], check=True)
    made = _Repo(root)
    for key, value in (("user.email", "t@t.test"), ("user.name", "T"), ("commit.gpgsign", "false")):
        made.git("config", key, value)
    made.commit("README.md")
    made.git("branch", "base")
    made.git("checkout", "-qb", _BRANCH)
    return made


def _build(repo: _Repo, wp_id: str, path: str) -> str:
    repo.claim(wp_id)
    work = repo.commit(path)
    repo.approve(wp_id)
    return work


def test_sequential_work_packages_pass(repo: _Repo) -> None:
    _build(repo, "WP01", "src/m1.py")
    _build(repo, "WP02", "src/m2.py")

    assert repo.check() == ()


def test_commit_after_the_last_approval_refuses(repo: _Repo) -> None:
    """Tier 1: content beyond every approval stamp."""
    _build(repo, "WP01", "src/m1.py")
    _build(repo, "WP02", "src/m2.py")
    late = repo.commit("src/late.py")

    (refusal,) = repo.check()

    assert refusal.code is BoundRefusalCode.LANE_MOVED_AFTER_APPROVAL
    assert late in refusal.commits


def test_commit_between_two_approvals_refuses_naming_the_preceding_work_package(repo: _Repo) -> None:
    """Tier 2: X follows WP01's approval and precedes WP02's claim, so it lies in no window."""
    _build(repo, "WP01", "src/m1.py")
    between = repo.commit("src/between.py")
    _build(repo, "WP02", "src/m2.py")

    refusals = check_write_branch(
        repo.root,
        events=repo.events,
        lane_id=_LANE,
        branch=_BRANCH,
        approved_wp_ids=("WP01", "WP02"),
        claim_base="base",
        anchors=(),
        is_bookkeeping=_is_bookkeeping,
    )

    assert [(r.code, r.wp_ids, r.commits, r.path) for r in refusals] == [
        (BoundRefusalCode.LANE_MOVED_AFTER_APPROVAL, ("WP01",), (between,), "src/between.py")
    ]
    text = render_write_branch_refusals(refusals, _SLUG)
    assert refusal_codes(text) == ["LANE_MOVED_AFTER_APPROVAL"]
    assert between[:7] in text and "WP01" in text
    assert "Send WP01 back for review and approve it again, or revert the commit" in text
    assert f"spec-kitty agent tasks move-task WP01 --to in_progress --mission {_SLUG}" in text
    assert "spec-kitty upgrade" in text


def test_commit_before_the_first_claim_names_the_first_approval_after_it(repo: _Repo) -> None:
    early = repo.commit("src/early.py")
    _build(repo, "WP01", "src/m1.py")

    refusals = check_write_branch(
        repo.root,
        events=repo.events,
        lane_id=_LANE,
        branch=_BRANCH,
        approved_wp_ids=("WP01",),
        claim_base="base",
        anchors=(),
        is_bookkeeping=_is_bookkeeping,
    )

    assert [(r.wp_ids, r.commits) for r in refusals] == [(("WP01",), (early,))]


def test_overlapping_windows_pass(repo: _Repo) -> None:
    """WP02 committed while WP01 was in review: both approved, every commit is in some window."""
    repo.claim("WP01")
    repo.commit("src/m1.py")
    repo.claim("WP02")
    repo.commit("src/m2.py")
    repo.approve("WP01")
    repo.approve("WP02")

    assert repo.check() == ()


def test_rework_after_a_later_approval_passes(repo: _Repo) -> None:
    _build(repo, "WP01", "src/m1.py")
    _build(repo, "WP02", "src/m2.py")
    repo.commit("src/m1_rework.py")
    repo.approve("WP01")

    assert repo.check() == ()


def test_bookkeeping_merges_and_anchored_commits_are_exempt(repo: _Repo) -> None:
    _build(repo, "WP01", "src/m1.py")
    repo.commit(f"kitty-specs/{_SLUG}/status.events.jsonl")
    repo.git("checkout", "-q", "main")
    side = repo.commit("docs/side.md")
    repo.git("checkout", "-q", _BRANCH)
    repo.git("merge", "-q", "--no-ff", "--no-edit", "main")
    _build(repo, "WP02", "src/m2.py")

    assert repo.check(anchors=(side,)) == ()


def test_missing_open_stamp_degrades_to_the_claim_base_and_is_logged(repo: _Repo, caplog: pytest.LogCaptureFixture) -> None:
    """A-8: a work package with no stamped claim gets the window (claim_base, S_k]; no new refusal."""
    early = repo.commit("src/early.py")
    repo.claim("WP01", stamped=False)
    repo.commit("src/m1.py")
    repo.approve("WP01")

    with caplog.at_level(logging.INFO, logger="specify_cli.consolidation.write_branch_bound"):
        windows = approval_windows(repo.events, {"WP01": repo.head})
        outside = commits_outside_windows(repo.root, tip=_BRANCH, claim_base="base", windows=windows)

    assert windows == (ApprovalWindow("WP01", None, repo.head),)
    assert windows[0].degraded
    assert early not in outside and outside == []
    assert "WP01 has no stamped claim" in caplog.text
    assert repo.check(approved=("WP01",)) == ()


def test_stamped_open_excludes_what_preceded_the_claim(repo: _Repo) -> None:
    early = repo.commit("src/early.py")
    _build(repo, "WP01", "src/m1.py")
    windows = approval_windows(repo.events, {"WP01": repo.head})

    assert not windows[0].degraded
    assert commits_outside_windows(repo.root, tip=_BRANCH, claim_base="base", windows=windows) == [early]


def test_unstamped_approval_refuses_stamp_missing(repo: _Repo) -> None:
    repo.claim("WP01")
    repo.commit("src/m1.py")
    repo.event("WP01", Lane.IN_REVIEW, Lane.APPROVED, stamped=False)

    (refusal,) = repo.check(approved=("WP01",))

    assert refusal.code is BoundRefusalCode.APPROVAL_STAMP_MISSING


def test_tier_one_refusal_renders_through_the_lane_text(repo: _Repo) -> None:
    repo.claim("WP01")
    repo.commit("src/m1.py")
    repo.event("WP01", Lane.IN_REVIEW, Lane.APPROVED, stamped=False)
    refusals = check_write_branch(
        repo.root,
        events=repo.events,
        lane_id=_LANE,
        branch=_BRANCH,
        approved_wp_ids=("WP01",),
        claim_base="base",
        anchors=(),
        is_bookkeeping=_is_bookkeeping,
    )

    text = render_write_branch_refusals(refusals, _SLUG)

    assert refusal_codes(text) == ["APPROVAL_STAMP_MISSING"]
    assert "--attest-approved-reviewed WP01" in text


@pytest.mark.timing
def test_bound_cost_10wp_200_commits(repo: _Repo) -> None:
    """NFR-007: the tier-2 check stays well under 2 s for 10 work packages and 200 commits."""
    for index in range(10):
        wp_id = f"WP{index + 1:02d}"
        repo.claim(wp_id)
        for step in range(20):
            repo.commit(f"src/{wp_id}/f{step}.py")
        repo.approve(wp_id)
    approved = tuple(f"WP{index + 1:02d}" for index in range(10))

    started = time.perf_counter()
    refusals = check_write_branch(
        repo.root,
        events=repo.events,
        lane_id=_LANE,
        branch=_BRANCH,
        approved_wp_ids=approved,
        claim_base="base",
        anchors=(),
        is_bookkeeping=_is_bookkeeping,
    )
    elapsed = time.perf_counter() - started

    assert refusals == ()
    assert elapsed < 2.0, f"NFR-007: the claim check took {elapsed:.2f} s"
