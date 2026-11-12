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

from specify_cli.consolidation import write_branch_bound
from specify_cli.consolidation.approved_bound import BoundRefusal, BoundRefusalCode, check_lane, refusal_codes
from specify_cli.consolidation.wp_attribution import GapEntry, lane_exempt_commits
from specify_cli.consolidation.write_branch_bound import (
    ApprovalWindow,
    bind_lane_predicates,
    check_lane_windows,
    check_write_branch,
    classify_windows,
    lane_windows,
    render_lane_window_refusals,
    render_write_branch_refusals,
)
from specify_cli.status import LANE_HEAD_KEY, WP_WINDOW_KEY, Lane, StatusEvent, WindowGap, WindowGapReason, WindowOpen

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

    def event(self, wp_id: str, from_lane: Lane, to_lane: Lane, *, stamped: bool = True, window: bool = False) -> None:
        self.seq += 1
        metadata: dict[str, object] | None = {LANE_HEAD_KEY: self.head} if stamped else None
        if window:
            metadata = {**(metadata or {}), WP_WINDOW_KEY: {"schema_version": 1, "open_sha": self.head}}
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
                policy_metadata=metadata,
            )
        )

    def claim(self, wp_id: str, *, stamped: bool = True, window: bool = False) -> None:
        self.event(wp_id, Lane.PLANNED, Lane.IN_PROGRESS, stamped=stamped, window=window)

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

    assert [(r.code, r.wp_ids, r.commits, r.path) for r in refusals] == [(BoundRefusalCode.LANE_MOVED_AFTER_APPROVAL, ("WP01",), (between,), "src/between.py")]
    text = render_write_branch_refusals(refusals, _SLUG)
    assert refusal_codes(text) == ["LANE_MOVED_AFTER_APPROVAL"]
    assert between[:7] in text and "WP01" in text
    assert "Send WP01 back for review and approve it again" in text
    assert "revert" not in text  # M8: a revert is new content of its own; it never clears a window refusal
    assert "was committed after WP01's approval" in text
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


def test_commit_before_every_approval_gets_its_own_text(repo: _Repo) -> None:
    """M8: a commit no approval precedes is not "committed after" anything, and approving again cannot cover it."""
    early = repo.commit("src/early.py")
    _build(repo, "WP01", "src/m1.py")

    text = render_write_branch_refusals(repo.check(approved=("WP01",)), _SLUG)

    assert refusal_codes(text) == ["LANE_MOVED_AFTER_APPROVAL"]
    assert early[:7] in text
    assert "after WP01's approval" not in text
    assert "before WP01's review window opened" in text and "no work package's newest approval comes before it" in text
    assert "approving again moves a window's end, never its start" in text
    assert "move-task" not in text and "revert" not in text


def test_following_the_window_recovery_clears_the_refusal(repo: _Repo) -> None:
    """M8: the printed recovery (send WP01 back, approve it again) leads to a passing check."""
    _build(repo, "WP01", "src/m1.py")
    repo.commit("src/between.py")
    _build(repo, "WP02", "src/m2.py")
    text = render_write_branch_refusals(repo.check(), _SLUG)
    assert f"spec-kitty agent tasks move-task WP01 --to in_progress --mission {_SLUG}" in text

    repo.event("WP01", Lane.APPROVED, Lane.IN_PROGRESS)
    repo.approve("WP01")

    assert repo.check() == ()


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
    repo.commit("src/early.py")
    repo.claim("WP01", stamped=False)
    repo.commit("src/m1.py")
    repo.approve("WP01")

    with caplog.at_level(logging.INFO, logger="specify_cli.consolidation.write_branch_bound"):
        refusals = repo.check(approved=("WP01",))

    # The degraded window (claim_base, S_k] covers the early commit, so nothing is outside it.
    assert refusals == ()
    assert "WP01 has no stamped claim" in caplog.text


def test_a_first_claim_that_predates_stamps_degrades_the_window(repo: _Repo, caplog: pytest.LogCaptureFixture) -> None:
    """In-flight Mission: WP01's claim and commit predate stamps; a stamped rework must not narrow its window (A-8)."""
    repo.claim("WP01", stamped=False)
    repo.commit("src/m1.py")
    repo.event("WP01", Lane.IN_PROGRESS, Lane.FOR_REVIEW, stamped=False)
    repo.event("WP01", Lane.FOR_REVIEW, Lane.IN_PROGRESS)
    repo.commit("src/m1_rework.py")
    repo.event("WP01", Lane.IN_PROGRESS, Lane.FOR_REVIEW)
    repo.event("WP01", Lane.FOR_REVIEW, Lane.IN_REVIEW)
    repo.approve("WP01")

    with caplog.at_level(logging.INFO, logger="specify_cli.consolidation.write_branch_bound"):
        refusals = repo.check(approved=("WP01",))

    assert refusals == ()
    assert "WP01 has no stamped claim" in caplog.text


def test_stamped_open_excludes_what_preceded_the_claim(repo: _Repo) -> None:
    early = repo.commit("src/early.py")
    _build(repo, "WP01", "src/m1.py")

    assert [(r.wp_ids, r.commits) for r in repo.check(approved=("WP01",))] == [(("WP01",), (early,))]


def test_a_blocked_move_does_not_open_a_work_package_window(repo: _Repo) -> None:
    """WP03 is blocked at the very start, so its blocked stamp must not widen its window over X."""
    repo.event("WP03", Lane.PLANNED, Lane.BLOCKED)
    _build(repo, "WP01", "src/m1.py")
    between = repo.commit("src/between.py")
    _build(repo, "WP02", "src/m2.py")
    repo.event("WP03", Lane.BLOCKED, Lane.IN_PROGRESS)
    repo.commit("src/m3.py")
    repo.approve("WP03")

    refusals = repo.check(approved=("WP01", "WP02", "WP03"))

    assert [(r.code, r.wp_ids, r.commits) for r in refusals] == [(BoundRefusalCode.LANE_MOVED_AFTER_APPROVAL, ("WP01",), (between,))]


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


# --------------------------------------------------------------------------- the lane leg (WP19, FR-007)


def _lane_windows_of(repo: _Repo, approved: tuple[str, ...]) -> tuple[ApprovalWindow, ...]:
    on_lane, is_ancestor = bind_lane_predicates(repo.root, repo.head)
    classes = classify_windows(repo.events, approved, on_lane=on_lane, is_ancestor=is_ancestor)
    stamps = {wp_id: next(e.policy_metadata[LANE_HEAD_KEY] for e in reversed(repo.events) if e.wp_id == wp_id and e.to_lane == Lane.APPROVED) for wp_id in approved}
    windows: tuple[ApprovalWindow, ...] = lane_windows(classes, stamps)
    return windows


def _check_lane_windows(
    repo: _Repo, approved: tuple[str, ...] = ("WP01", "WP02"), anchors: tuple[str, ...] = ()
) -> tuple[tuple[BoundRefusal, ...], tuple[BoundRefusal, ...]]:
    tiers: tuple[tuple[BoundRefusal, ...], tuple[BoundRefusal, ...]] = check_lane_windows(
        repo.root,
        events=repo.events,
        lane_id="lane-a",
        branch=_BRANCH,
        approved_wp_ids=approved,
        claim_base="base",
        exemption_anchors=anchors,
        windows=_lane_windows_of(repo, approved),
        is_bookkeeping=_is_bookkeeping,
        tip=repo.head,
    )
    return tiers


def _build_windowed(repo: _Repo, wp_id: str, path: str) -> str:
    repo.claim(wp_id, window=True)
    work = repo.commit(path)
    repo.approve(wp_id)
    return work


def test_bind_lane_predicates_unresolvable_sha_is_not_on_lane(repo: _Repo) -> None:
    """FR-022: an unresolvable SHA reads as not on the lane, and neither predicate raises."""
    on_lane_commit = repo.commit("src/on.py")
    tip = repo.commit("src/tip.py")
    repo.git("checkout", "-qb", "elsewhere", "base")
    off_lane = repo.commit("src/off.py")
    on_lane, is_ancestor = bind_lane_predicates(repo.root, tip)

    assert on_lane(on_lane_commit) and on_lane(tip)
    assert not on_lane(off_lane)
    assert not on_lane("f" * 40)
    assert is_ancestor(on_lane_commit, tip) and is_ancestor(tip, tip)
    assert not is_ancestor(tip, on_lane_commit)
    assert not is_ancestor("f" * 40, tip)


def test_classify_windows_gap_and_open(repo: _Repo) -> None:
    repo.claim("WP01", window=True)
    opened_at = repo.head
    repo.commit("src/m1.py")
    repo.claim("WP02")
    on_lane, is_ancestor = bind_lane_predicates(repo.root, repo.head)

    classes = classify_windows(repo.events, ("WP01", "WP02"), on_lane=on_lane, is_ancestor=is_ancestor)

    assert classes == {"WP01": WindowOpen(opened_at), "WP02": WindowGap(WindowGapReason.NOT_RECORDED)}
    assert list(classes) == ["WP01", "WP02"]


def test_lane_windows_open_a_gap_at_the_claim_base_and_skip_unstamped(repo: _Repo) -> None:
    classes: dict[str, WindowOpen | WindowGap] = {"WP01": WindowOpen("a" * 40), "WP02": WindowGap(WindowGapReason.CAPTURE_FAILED), "WP03": WindowOpen("c" * 40)}

    windows = lane_windows(classes, {"WP01": "s1", "WP02": "s2", "WP03": None})

    assert windows == (ApprovalWindow("WP01", "a" * 40, "s1"), ApprovalWindow("WP02", None, "s2"))
    assert windows[1].degraded


def test_gap_entry_from_gap_reports_the_reason_text() -> None:
    gap = WindowGap(WindowGapReason.CAPTURE_FAILED, cause="git_error", detail="boom")

    assert GapEntry.from_gap("WP02", "lane-a", gap) == GapEntry("WP02", "lane-a", "capture failed", "git_error", "boom")
    assert GapEntry.from_gap("WP01", "lane-b", WindowGap(WindowGapReason.NOT_RECORDED)).reason == "not recorded"


def test_check_lane_windows_passes_sequential_windows(repo: _Repo) -> None:
    _build_windowed(repo, "WP01", "src/m1.py")
    _build_windowed(repo, "WP02", "src/m2.py")

    assert _check_lane_windows(repo) == ((), ())


def test_check_lane_windows_tier_one_refusal_returned_alone(repo: _Repo) -> None:
    """A tier-1 refusal (content after every approval) is returned without running tier 2, even with a stray between windows."""
    _build_windowed(repo, "WP01", "src/m1.py")
    repo.commit("src/between.py")
    _build_windowed(repo, "WP02", "src/m2.py")
    late = repo.commit("src/late.py")

    tier_one, tier_two = _check_lane_windows(repo)

    assert tier_two == ()
    (refusal,) = tier_one
    assert refusal.code is BoundRefusalCode.LANE_MOVED_AFTER_APPROVAL
    assert refusal.commits == (late,)
    assert refusal.wp_ids == ("WP01", "WP02")


def test_check_lane_windows_stray_between_windows_names_preceding_wp(repo: _Repo) -> None:
    """Tier 2: X lies after WP01's window and before WP02's recorded open, so it is refused naming WP01."""
    _build_windowed(repo, "WP01", "src/m1.py")
    between = repo.commit("src/between.py")
    _build_windowed(repo, "WP02", "src/m2.py")

    tier_one, tier_two = _check_lane_windows(repo)

    assert tier_one == ()
    (refusal,) = tier_two
    assert (refusal.code, refusal.commits, refusal.wp_ids, refusal.path) == (BoundRefusalCode.LANE_MOVED_AFTER_APPROVAL, (between,), ("WP01",), "src/between.py")
    text = render_lane_window_refusals(tier_two, _SLUG)
    assert text.startswith(f"LANE_MOVED_AFTER_APPROVAL: commit {between[:7]} ('src/between.py')")
    assert "spec-kitty agent tasks move-task WP01 --to in_progress" in text
    assert "spec-kitty upgrade" not in text, "the single_branch tool-commit hint is not part of the lane text"
    assert render_write_branch_refusals(tier_two, _SLUG).startswith(f"{text}\n"), "the single_branch text is the lane text plus its hint"


def test_check_lane_windows_work_committed_before_the_claim_is_not_after_its_own_approval(repo: _Repo) -> None:
    """A commit made before the claim lies before the window even when it IS the approval stamp.

    The work package is approved with nothing committed after its claim, so its approval stamp is
    the pre-claim commit itself and its window ``(open, stamp]`` is empty. The commit is refused
    (ADR 2026-11-08-2, section 4: content before the window refuses unless an exemption anchor
    reaches it), but it was not committed after that approval: it is the approval's own head.
    """
    early = repo.commit("src/m1.py")
    repo.claim("WP01", window=True)
    repo.approve("WP01")

    tier_one, tier_two = _check_lane_windows(repo, approved=("WP01",))

    assert tier_one == ()
    (refusal,) = tier_two
    assert (refusal.commits, refusal.wp_ids, refusal.precedes_approvals) == ((early,), ("WP01",), True)
    text = render_lane_window_refusals(tier_two, _SLUG)
    assert "after WP01's approval" not in text
    assert "before WP01's review window opened" in text


def test_check_lane_windows_anchor_exempts_the_stray(repo: _Repo) -> None:
    """WW-2a: a commit an exemption anchor (another lane's stamp) reaches is exempt from tier 2."""
    _build_windowed(repo, "WP01", "src/m1.py")
    between = repo.commit("src/between.py")
    _build_windowed(repo, "WP02", "src/m2.py")

    assert _check_lane_windows(repo, anchors=(between,)) == ((), ())


def test_check_lane_windows_without_windows_runs_tier_one_only(repo: _Repo) -> None:
    _build_windowed(repo, "WP01", "src/m1.py")
    repo.commit("src/between.py")

    tier_one, tier_two = check_lane_windows(
        repo.root,
        events=repo.events,
        lane_id="lane-a",
        branch=_BRANCH,
        approved_wp_ids=("WP01",),
        claim_base="base",
        exemption_anchors=(),
        windows=(),
        is_bookkeeping=_is_bookkeeping,
        tip=repo.head,
    )

    assert len(tier_one) == 1 and tier_two == ()


def test_check_lane_exempt_keyword_matches_computed_exempt(repo: _Repo) -> None:
    """``check_lane(exempt=...)`` with the set computed from the same anchors gives the verdict ``check_lane`` computes itself."""
    _build_windowed(repo, "WP01", "src/m1.py")
    anchored = repo.commit("src/anchored.py")
    repo.commit("src/late.py")

    def _check(exempt: frozenset[str] | None) -> BoundRefusal | None:
        return check_lane(
            repo.root,
            events=repo.events,
            lane_id="lane-a",
            branch=_BRANCH,
            approved_wp_ids=("WP01",),
            claim_base="base",
            anchors=(anchored,),
            is_bookkeeping=_is_bookkeeping,
            tip=repo.head,
            exempt=exempt,
        )

    computed = _check(None)
    supplied = _check(lane_exempt_commits(repo.root, "base", (anchored,)))

    assert computed == supplied
    assert computed is not None and anchored not in computed.commits


# --------------------------------------------------------------------------- the single_branch leg reads the recorded window (WP20, FR-011)


def _check_windows(repo: _Repo, approved: tuple[str, ...] = ("WP01", "WP02")) -> tuple[tuple[BoundRefusal, ...], tuple[GapEntry, ...]]:
    # Through the module: the name is new in WP20, so the red commit fails per test, not at collection.
    found: tuple[tuple[BoundRefusal, ...], tuple[GapEntry, ...]] = write_branch_bound.check_write_branch_windows(
        repo.root,
        events=repo.events,
        lane_id=_LANE,
        branch=_BRANCH,
        approved_wp_ids=approved,
        claim_base="base",
        anchors=(),
        is_bookkeeping=_is_bookkeeping,
        tip=repo.head,
    )
    return found


def _rewound(repo: _Repo) -> tuple[str, str, str]:
    """WP01 claimed at S0, an abandoned commit, a rewind to ``planned``, a recorded re-claim at S1, the work, the approval."""
    repo.claim("WP01", window=True)
    first_open = repo.head
    abandoned = repo.commit("src/abandoned.py")
    repo.event("WP01", Lane.IN_PROGRESS, Lane.PLANNED)
    repo.claim("WP01", window=True)
    second_open = repo.head
    repo.commit("src/m1.py")
    repo.approve("WP01")
    if second_open != abandoned or first_open == second_open:
        raise RuntimeError("fixture: the re-claim must open at the abandoned commit, after the first claim")
    return first_open, abandoned, second_open


def _stamps(repo: _Repo, approved: tuple[str, ...]) -> dict[str, str]:
    return {wp_id: next(e.policy_metadata[LANE_HEAD_KEY] for e in reversed(repo.events) if e.wp_id == wp_id and e.to_lane == Lane.APPROVED) for wp_id in approved}


def test_approval_windows_without_classes_is_todays_derivation(repo: _Repo) -> None:
    first_open, _abandoned, _second_open = _rewound(repo)
    stamps = _stamps(repo, ("WP01",))

    windows = write_branch_bound.approval_windows(repo.events, stamps, classes=None)

    assert windows == write_branch_bound.approval_windows(repo.events, stamps)
    assert windows == (ApprovalWindow("WP01", first_open, stamps["WP01"]),)


def test_approval_windows_reads_recorded_open_after_rewind(repo: _Repo) -> None:
    """FR-021 cycle rule: the recorded opener after the rewind (S1) opens the window, not the first claim (S0)."""
    first_open, _abandoned, second_open = _rewound(repo)
    stamps = _stamps(repo, ("WP01",))
    on_lane, is_ancestor = bind_lane_predicates(repo.root, repo.head)
    classes = classify_windows(repo.events, ("WP01",), on_lane=on_lane, is_ancestor=is_ancestor)

    (window,) = write_branch_bound.approval_windows(repo.events, stamps, classes=classes)

    assert classes == {"WP01": WindowOpen(second_open)}
    assert window.open_stamp == second_open != first_open


def test_approval_windows_gap_keeps_the_first_claim_derivation(repo: _Repo) -> None:
    first_open, _abandoned, _second_open = _rewound(repo)
    stamps = _stamps(repo, ("WP01",))
    gap: dict[str, WindowOpen | WindowGap] = {"WP01": WindowGap(WindowGapReason.NOT_RECORDED)}

    (window,) = write_branch_bound.approval_windows(repo.events, stamps, classes=gap)

    assert window.open_stamp == first_open


def test_check_write_branch_windows_reports_gap_and_keeps_derivation(repo: _Repo) -> None:
    """No ``wp_window`` on any opener: the verdict is today's derived-window verdict, and every work package is a gap."""
    _build(repo, "WP01", "src/m1.py")
    between = repo.commit("src/between.py")
    _build(repo, "WP02", "src/m2.py")

    refusals, gaps = _check_windows(repo)

    assert refusals == repo.check()
    assert [(r.wp_ids, r.commits) for r in refusals] == [(("WP01",), (between,))]
    assert gaps == (GapEntry("WP01", _LANE, "not recorded"), GapEntry("WP02", _LANE, "not recorded"))


def test_check_write_branch_windows_refuses_the_abandoned_cycle(repo: _Repo) -> None:
    """NFR-002 (c) single_branch: the abandoned commit lies before the recorded re-claim, so no window covers it."""
    _first_open, abandoned, _second_open = _rewound(repo)

    refusals, gaps = _check_windows(repo, ("WP01",))

    assert [(r.code, r.wp_ids, r.commits) for r in refusals] == [(BoundRefusalCode.LANE_MOVED_AFTER_APPROVAL, ("WP01",), (abandoned,))]
    assert gaps == ()


def test_check_write_branch_wrapper_unchanged(repo: _Repo) -> None:
    """``check_write_branch`` keeps its signature and returns exactly the refusals of the windowed check."""
    _first_open, abandoned, _second_open = _rewound(repo)

    wrapped = check_write_branch(
        repo.root,
        events=repo.events,
        lane_id=_LANE,
        branch=_BRANCH,
        approved_wp_ids=("WP01",),
        claim_base="base",
        anchors=(),
        is_bookkeeping=_is_bookkeeping,
    )

    assert wrapped == _check_windows(repo, ("WP01",))[0]
    assert [r.commits for r in wrapped] == [(abandoned,)]
