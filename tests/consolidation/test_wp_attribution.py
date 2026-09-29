"""Tests for ``specify_cli.consolidation.wp_attribution`` (WP04, #5046).

Core domain logic — tiered rigour, exhaustive git-backed tests (plan.md D-2/
D-3; data-model.md; contracts/attribution-and-verdicts.md; research.md R-1..
R-10). Builds throwaway repos in ``tmp_path`` with real commits; synthetic
``StatusEvent``s use the canonical event shape with real SHAs as stamps.

Window/stamp tests that need no git repo exercise ``_windows`` directly
(module-private, same-package access — mirrors the ``git_probes`` seam test's
own pattern of testing private helpers by qualified name). Content/contest/
merge/error tests exercise the public ``resolve_canceled_wp`` end-to-end
against a real repo, since they must prove actual git behavior (merge
filtering, stamp ancestry, blob resolution).
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

from specify_cli.consolidation import wp_attribution as wpa
from specify_cli.consolidation.git_probes import GitProbeError
from specify_cli.status import LANE_HEAD_KEY, Lane, StatusEvent

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_MISSION_SLUG = "mixed-lane-authorship-soundness-01M3M7Y0"
_LANE_ID = "lane-a"
_NO_BOOKKEEPING = staticmethod(lambda _path: False)


# ---------------------------------------------------------------------------
# Shared git + event helpers
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-qb", "main", str(repo)], check=True)
    _git(repo, "config", "user.email", "wp-attribution@test.local")
    _git(repo, "config", "user.name", "WP Attribution Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("init\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "init")
    return repo


def _commit_file(repo: Path, rel: str, body: str, message: str) -> str:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    _git(repo, "add", rel)
    _git(repo, "commit", "-qm", message)
    return _git(repo, "rev-parse", "HEAD")


def _delete_file(repo: Path, rel: str, message: str) -> str:
    (repo / rel).unlink()
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", message)
    return _git(repo, "rev-parse", "HEAD")


def _event(
    event_id: str,
    wp_id: str,
    from_lane: Lane,
    to_lane: Lane,
    at: str,
    *,
    stamp: str | None = None,
    actor: str = "claude",
) -> StatusEvent:
    return StatusEvent(
        event_id=event_id,
        mission_slug=_MISSION_SLUG,
        wp_id=wp_id,
        from_lane=from_lane,
        to_lane=to_lane,
        at=at,
        actor=actor,
        force=False,
        execution_mode="worktree",
        policy_metadata={LANE_HEAD_KEY: stamp} if stamp else None,
    )


# ---------------------------------------------------------------------------
# T016 — window reconstruction (pure; no git needed)
# ---------------------------------------------------------------------------


def test_claimed_and_in_progress_share_one_implementation_window() -> None:
    events = [
        _event("e1", "WP02", Lane.PLANNED, Lane.CLAIMED, "2026-01-01T00:00:00Z", stamp="sha-open"),
        _event("e2", "WP02", Lane.CLAIMED, Lane.IN_PROGRESS, "2026-01-01T00:01:00Z", stamp="sha-mid"),
        _event("e3", "WP02", Lane.IN_PROGRESS, Lane.FOR_REVIEW, "2026-01-01T00:02:00Z", stamp="sha-close"),
    ]
    windows = wpa._windows(events, frozenset({"WP02"}))
    assert windows["WP02"] == [
        wpa.WorkWindow(
            wp_id="WP02",
            kind=wpa.WindowKind.IMPLEMENTATION,
            open_head="sha-open",
            close_head="sha-close",
            still_open=False,
        ),
        wpa.WorkWindow(
            wp_id="WP02",
            kind=wpa.WindowKind.REVIEW,
            open_head="sha-close",
            close_head=None,
            still_open=True,
        ),
    ]


def test_rework_round_opens_a_new_implementation_window() -> None:
    events = [
        _event("e1", "WP02", Lane.PLANNED, Lane.CLAIMED, "t0", stamp="s0"),
        _event("e2", "WP02", Lane.IN_PROGRESS, Lane.FOR_REVIEW, "t1", stamp="s1"),
        _event("e3", "WP02", Lane.FOR_REVIEW, Lane.IN_REVIEW, "t2", stamp="s1b"),
        _event("e4", "WP02", Lane.IN_REVIEW, Lane.IN_PROGRESS, "t3", stamp="s2"),
        _event("e5", "WP02", Lane.IN_PROGRESS, Lane.FOR_REVIEW, "t4", stamp="s3"),
    ]
    windows = wpa._windows(events, frozenset({"WP02"}))
    impl_windows = [w for w in windows["WP02"] if w.kind is wpa.WindowKind.IMPLEMENTATION]
    assert impl_windows == [
        wpa.WorkWindow(wp_id="WP02", kind=wpa.WindowKind.IMPLEMENTATION, open_head="s0", close_head="s1", still_open=False),
        wpa.WorkWindow(wp_id="WP02", kind=wpa.WindowKind.IMPLEMENTATION, open_head="s2", close_head="s3", still_open=False),
    ]


def test_blocked_is_counted_as_implementation() -> None:
    events = [
        _event("e1", "WP02", Lane.PLANNED, Lane.CLAIMED, "t0", stamp="s0"),
        _event("e2", "WP02", Lane.CLAIMED, Lane.BLOCKED, "t1", stamp="s-blocked"),
        _event("e3", "WP02", Lane.BLOCKED, Lane.IN_PROGRESS, "t2", stamp="s-unblocked"),
        _event("e4", "WP02", Lane.IN_PROGRESS, Lane.FOR_REVIEW, "t3", stamp="s1"),
    ]
    windows = wpa._windows(events, frozenset({"WP02"}))
    impl_windows = [w for w in windows["WP02"] if w.kind is wpa.WindowKind.IMPLEMENTATION]
    assert len(impl_windows) == 1
    assert impl_windows[0].open_head == "s0"
    assert impl_windows[0].close_head == "s1"


def test_window_with_missing_stamp_records_none_head() -> None:
    events = [
        _event("e1", "WP02", Lane.PLANNED, Lane.CLAIMED, "t0", stamp=None),
        _event("e2", "WP02", Lane.IN_PROGRESS, Lane.FOR_REVIEW, "t1", stamp="s1"),
    ]
    windows = wpa._windows(events, frozenset({"WP02"}))
    impl = windows["WP02"][0]
    assert impl.open_head is None
    assert impl.close_head == "s1"
    assert impl.still_open is False


def test_window_with_no_closing_event_is_still_open() -> None:
    events = [
        _event("e1", "WP02", Lane.PLANNED, Lane.CLAIMED, "t0", stamp="s0"),
    ]
    windows = wpa._windows(events, frozenset({"WP02"}))
    impl = windows["WP02"][0]
    assert impl.close_head is None
    assert impl.still_open is True


def test_windows_processes_events_in_append_order_not_sorted_by_at() -> None:
    """Review cycle 1, issue 3: the closing event is SECOND in the (append-
    order) list even though its ``at`` timestamp is EARLIER than the opening
    event's -- if ``_windows`` ever sorted by ``at`` instead of consuming
    events in append/causal order (the reducer-duality caveat, CLAUDE.md),
    this would silently read as a still-open window instead.
    """
    events = [
        _event("e1", "WP02", Lane.PLANNED, Lane.CLAIMED, "2026-01-02T00:00:00Z", stamp="A"),
        _event("e2", "WP02", Lane.IN_PROGRESS, Lane.FOR_REVIEW, "2026-01-01T00:00:00Z", stamp="B"),
    ]
    windows = wpa._windows(events, frozenset({"WP02"}))
    impl = windows["WP02"][0]
    assert impl.open_head == "A"
    assert impl.close_head == "B"
    assert impl.still_open is False


# ---------------------------------------------------------------------------
# T017 — stamp validity (R8), git-backed
# ---------------------------------------------------------------------------


def test_fork_point_open_stamp_of_first_wp_is_valid(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    coord_base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-qb", "lane-a")
    c1 = _commit_file(repo, "src/pkg/a.py", "v1\n", "wp02 work")

    events = [
        _event("e1", "WP02", Lane.PLANNED, Lane.CLAIMED, "t0", stamp=coord_base),
        _event("e2", "WP02", Lane.IN_PROGRESS, Lane.CANCELED, "t1", stamp=c1),
    ]
    outcome = wpa.resolve_canceled_wp(
        repo,
        events=events,
        lane_id=_LANE_ID,
        lane_wp_ids=["WP02"],
        canceled_wp_id="WP02",
        lane_branch="lane-a",
        coord_base_ref=coord_base,
        is_bookkeeping=_NO_BOOKKEEPING,
    )
    assert isinstance(outcome, wpa.Attributed)
    assert outcome.commits == frozenset({c1})


def test_rewritten_history_stamp_is_invalid(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    coord_base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-qb", "lane-a")
    stale_c1 = _commit_file(repo, "src/pkg/a.py", "v1\n", "wp02 original")
    # Rewrite history: amend changes the commit's SHA, orphaning stale_c1
    # (it is no longer an ancestor of the new lane tip).
    (repo / "src/pkg/a.py").write_text("v1-amended\n", encoding="utf-8")
    _git(repo, "add", "src/pkg/a.py")
    _git(repo, "commit", "-qm", "wp02 original (amended)", "--amend")
    new_tip = _git(repo, "rev-parse", "HEAD")
    assert new_tip != stale_c1

    events = [
        _event("e1", "WP02", Lane.PLANNED, Lane.CLAIMED, "t0", stamp=coord_base),
        _event("e2", "WP02", Lane.IN_PROGRESS, Lane.FOR_REVIEW, "t1", stamp=stale_c1),
    ]
    outcome = wpa.resolve_canceled_wp(
        repo,
        events=events,
        lane_id=_LANE_ID,
        lane_wp_ids=["WP02"],
        canceled_wp_id="WP02",
        lane_branch="lane-a",
        coord_base_ref=coord_base,
        is_bookkeeping=_NO_BOOKKEEPING,
    )
    assert outcome == wpa.Unattributable(
        wpa.UnattributableReason.STAMP_NOT_ANCESTOR_OF_LANE_TIP,
        wpa._detail_for(wpa.UnattributableReason.STAMP_NOT_ANCESTOR_OF_LANE_TIP, _LANE_ID, "WP02"),
    )


# ---------------------------------------------------------------------------
# Merges — never attributed, never supersede (R3/B4)
# ---------------------------------------------------------------------------


def test_merge_commit_inside_window_is_not_attributed_and_does_not_supersede(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _commit_file(repo, "src/pkg/merge_target.py", "base\n", "seed target")
    coord_base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-qb", "lane-a")
    open_head = _git(repo, "rev-parse", "HEAD")

    m1 = _commit_file(repo, "src/pkg/merge_target.py", "canceled-A\n", "wp02 change")

    # A concurrent side branch with an UNRELATED change, merged --no-ff into
    # the lane inside WP02's window: a clean auto-merge, so `git show` on the
    # merge commit prints an empty diff (nothing to attribute or supersede).
    _git(repo, "checkout", "-qb", "side")
    _commit_file(repo, "src/pkg/side_only.py", "side\n", "unrelated side work")
    _git(repo, "checkout", "-q", "lane-a")
    _git(repo, "merge", "-q", "--no-ff", "--no-edit", "side")
    merge_sha = _git(repo, "rev-parse", "HEAD")
    assert merge_sha != m1

    events = [
        _event("e1", "WP02", Lane.PLANNED, Lane.CLAIMED, "t0", stamp=open_head),
        _event("e2", "WP02", Lane.IN_PROGRESS, Lane.CANCELED, "t1", stamp=merge_sha),
    ]
    outcome = wpa.resolve_canceled_wp(
        repo,
        events=events,
        lane_id=_LANE_ID,
        lane_wp_ids=["WP02"],
        canceled_wp_id="WP02",
        lane_branch="lane-a",
        coord_base_ref=coord_base,
        is_bookkeeping=_NO_BOOKKEEPING,
    )
    assert isinstance(outcome, wpa.Attributed)
    assert outcome.commits == frozenset({m1})
    assert merge_sha not in outcome.commits
    paths = {c.path: c for c in outcome.canceled_content}
    assert paths["src/pkg/merge_target.py"].canceled_state == _git(repo, "rev-parse", f"{m1}:src/pkg/merge_target.py")


def test_conflict_resolved_merge_listing_the_path_does_not_supersede(tmp_path: Path) -> None:
    """Review cycle 1, issue 2: unlike the clean-auto-merge test above, this
    merge commit's own diff DOES list the canceled path (a real lane-sync
    conflict resolution) -- so the merge filter in the content walk is doing
    real work here, not vacuously passing because the merge never touched the
    path. Manually verified locally (not committed) that removing the merge
    check in ``_canceled_content_walk`` turns this red.
    """
    repo = _init_repo(tmp_path)
    _commit_file(repo, "src/pkg/m.py", "base\n", "seed target")
    coord_base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-qb", "coord")
    _commit_file(repo, "src/pkg/m.py", "coord\n", "coord change")
    _git(repo, "checkout", "-qb", "lane-a", coord_base)
    open_head = _git(repo, "rev-parse", "HEAD")
    m1 = _commit_file(repo, "src/pkg/m.py", "canceled\n", "wp02 change")
    subprocess.run(["git", "-C", str(repo), "merge", "-q", "--no-edit", "coord"], capture_output=True, check=False)
    (repo / "src/pkg/m.py").write_text("resolved\n", encoding="utf-8")
    _git(repo, "add", "src/pkg/m.py")
    _git(repo, "commit", "-qm", "sync merge resolves conflict")
    merge_sha = _git(repo, "rev-parse", "HEAD")
    assert wpa.is_merge_commit(repo, merge_sha)
    assert "src/pkg/m.py" in _git(repo, "show", "--name-only", "--format=", "--no-renames", merge_sha)

    events = [
        _event("e1", "WP02", Lane.PLANNED, Lane.CLAIMED, "t0", stamp=open_head),
        _event("e2", "WP02", Lane.IN_PROGRESS, Lane.CANCELED, "t1", stamp=merge_sha),
    ]
    outcome = wpa.resolve_canceled_wp(
        repo,
        events=events,
        lane_id=_LANE_ID,
        lane_wp_ids=["WP02"],
        canceled_wp_id="WP02",
        lane_branch="lane-a",
        coord_base_ref=coord_base,
        is_bookkeeping=_NO_BOOKKEEPING,
    )
    assert isinstance(outcome, wpa.Attributed)
    assert outcome.commits == frozenset({m1})
    assert merge_sha not in outcome.commits
    by_path = {c.path: c for c in outcome.canceled_content}
    # The newest toucher is m1 (the canceled commit) -- the merge, even
    # though its diff lists the path, is skipped and never supersedes it.
    assert by_path["src/pkg/m.py"].canceled_state == _git(repo, "rev-parse", f"{m1}:src/pkg/m.py")


# ---------------------------------------------------------------------------
# Review cycle 1, issue 1 (HIGH, fail-open) -- an unresolvable SIBLING window
# must REFUSE the whole resolution, not be silently skipped as "no overlap".
# RED-FIRST: these two tests were committed failing against the pre-fix code
# (strict=False for siblings), then the fix landed in a follow-up commit.
# ---------------------------------------------------------------------------


def test_sibling_missing_open_stamp_refuses_whole_resolution(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _commit_file(repo, "src/pkg/y.py", "v0\n", "seed y.py")
    coord_base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-qb", "lane-a")
    fork = _git(repo, "rev-parse", "HEAD")
    survivor_sha = _commit_file(repo, "src/pkg/y.py", "v1\n", "wp01 sets v1")  # survivor
    canceled_sha = _commit_file(repo, "src/pkg/y.py", "v0\n", "wp02 undoes to v0")  # canceled

    events = [
        # WP01 (sibling, survivor): claims with NO stamp (C1 legal: best-effort
        # stamping) -- its implementation window can never be bounded.
        _event("e1", "WP01", Lane.PLANNED, Lane.CLAIMED, "t0", stamp=None),
        _event("e2", "WP01", Lane.IN_PROGRESS, Lane.APPROVED, "t1", stamp=survivor_sha),
        # WP02 (canceled): fully stamped and resolvable on its own.
        _event("e3", "WP02", Lane.PLANNED, Lane.CLAIMED, "t2", stamp=fork),
        _event("e4", "WP02", Lane.IN_PROGRESS, Lane.CANCELED, "t3", stamp=canceled_sha),
    ]
    outcome = wpa.resolve_canceled_wp(
        repo,
        events=events,
        lane_id=_LANE_ID,
        lane_wp_ids=["WP01", "WP02"],
        canceled_wp_id="WP02",
        lane_branch="lane-a",
        coord_base_ref=coord_base,
        is_bookkeeping=_NO_BOOKKEEPING,
    )
    assert outcome == wpa.Unattributable(
        wpa.UnattributableReason.NO_STAMP,
        wpa._detail_for(wpa.UnattributableReason.NO_STAMP, _LANE_ID, "WP01"),
    )


def test_sibling_rewritten_history_stamp_refuses_whole_resolution(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    coord_base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-qb", "lane-a")
    stale_sha = _commit_file(repo, "src/pkg/s.py", "v1\n", "wp01 original")
    # Rewrite history: amend orphans stale_sha (no longer an ancestor of the
    # new lane tip).
    (repo / "src/pkg/s.py").write_text("v1-amended\n", encoding="utf-8")
    _git(repo, "add", "src/pkg/s.py")
    _git(repo, "commit", "-qm", "wp01 original (amended)", "--amend")
    survivor_tip = _git(repo, "rev-parse", "HEAD")
    assert survivor_tip != stale_sha
    canceled_sha = _commit_file(repo, "src/pkg/y.py", "canceled\n", "wp02 work")

    events = [
        # WP01 (sibling): its recorded open stamp is the now-orphaned SHA.
        _event("e1", "WP01", Lane.PLANNED, Lane.CLAIMED, "t0", stamp=stale_sha),
        _event("e2", "WP01", Lane.IN_PROGRESS, Lane.APPROVED, "t1", stamp=survivor_tip),
        # WP02 (canceled): fully stamped and resolvable on its own.
        _event("e3", "WP02", Lane.PLANNED, Lane.CLAIMED, "t2", stamp=survivor_tip),
        _event("e4", "WP02", Lane.IN_PROGRESS, Lane.CANCELED, "t3", stamp=canceled_sha),
    ]
    outcome = wpa.resolve_canceled_wp(
        repo,
        events=events,
        lane_id=_LANE_ID,
        lane_wp_ids=["WP01", "WP02"],
        canceled_wp_id="WP02",
        lane_branch="lane-a",
        coord_base_ref=coord_base,
        is_bookkeeping=_NO_BOOKKEEPING,
    )
    assert outcome == wpa.Unattributable(
        wpa.UnattributableReason.STAMP_NOT_ANCESTOR_OF_LANE_TIP,
        wpa._detail_for(wpa.UnattributableReason.STAMP_NOT_ANCESTOR_OF_LANE_TIP, _LANE_ID, "WP01"),
    )


# ---------------------------------------------------------------------------
# Review cycle 2, issue 6 (MEDIUM, false REFUSE) -- a sibling that never
# ENTERED implementation (planned -> blocked -> canceled, never claimed/
# in_progress) must be skipped in the sibling loop the same way the canceled
# WP itself is (T020 / plan.md D-3 step 2), not have its (legal, R6) blocked
# window resolved and mistaken for real overlap. RED-FIRST: both tests below
# were committed failing against the pre-fix code (the sibling loop resolved
# every sibling's windows unconditionally), then the fix landed in a
# follow-up commit.
# ---------------------------------------------------------------------------


def _sibling_never_entered_implementation_events(coord_base: str, survivor_sha: str, canceled_sha: str, *, stamped: bool) -> list[StatusEvent]:
    blocked_open = coord_base if stamped else None
    blocked_close = canceled_sha if stamped else None
    return [
        _event("a", "WP01", Lane.PLANNED, Lane.CLAIMED, "t0", stamp=coord_base),
        _event("b", "WP01", Lane.IN_PROGRESS, Lane.FOR_REVIEW, "t1", stamp=survivor_sha),
        _event("c", "WP01", Lane.FOR_REVIEW, Lane.APPROVED, "t2", stamp=survivor_sha),
        _event("d", "WP02", Lane.PLANNED, Lane.CLAIMED, "t3", stamp=survivor_sha),
        _event("e", "WP02", Lane.IN_PROGRESS, Lane.CANCELED, "t4", stamp=canceled_sha),
        # WP03: planned -> blocked -> canceled, NEVER claimed/in_progress.
        # Its (legal, R6) "blocked" interval covers WP02's own window even
        # though WP03 authored nothing.
        _event("f", "WP03", Lane.PLANNED, Lane.BLOCKED, "t5", stamp=blocked_open),
        _event("g", "WP03", Lane.BLOCKED, Lane.CANCELED, "t6", stamp=blocked_close),
    ]


def _build_sibling_never_entered_repo(tmp_path: Path) -> tuple[Path, str, str, str]:
    repo = _init_repo(tmp_path)
    _commit_file(repo, "src/pkg/y.py", "v0\n", "seed y.py")
    coord_base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-qb", "lane-a")
    survivor_sha = _commit_file(repo, "src/pkg/y.py", "v1\n", "wp01 sets v1")
    canceled_sha = _commit_file(repo, "src/pkg/q.py", "canceled content\n", "wp02 work")
    return repo, coord_base, survivor_sha, canceled_sha


def test_sibling_only_reached_blocked_stamped_does_not_refuse(tmp_path: Path) -> None:
    repo, coord_base, survivor_sha, canceled_sha = _build_sibling_never_entered_repo(tmp_path)
    events = _sibling_never_entered_implementation_events(coord_base, survivor_sha, canceled_sha, stamped=True)
    outcome = wpa.resolve_canceled_wp(
        repo,
        events=events,
        lane_id=_LANE_ID,
        lane_wp_ids=["WP01", "WP02", "WP03"],
        canceled_wp_id="WP02",
        lane_branch="lane-a",
        coord_base_ref=coord_base,
        is_bookkeeping=_NO_BOOKKEEPING,
    )
    assert isinstance(outcome, wpa.Attributed), outcome
    assert canceled_sha in outcome.commits


def test_sibling_only_reached_blocked_unstamped_does_not_refuse(tmp_path: Path) -> None:
    repo, coord_base, survivor_sha, canceled_sha = _build_sibling_never_entered_repo(tmp_path)
    events = _sibling_never_entered_implementation_events(coord_base, survivor_sha, canceled_sha, stamped=False)
    outcome = wpa.resolve_canceled_wp(
        repo,
        events=events,
        lane_id=_LANE_ID,
        lane_wp_ids=["WP01", "WP02", "WP03"],
        canceled_wp_id="WP02",
        lane_branch="lane-a",
        coord_base_ref=coord_base,
        is_bookkeeping=_NO_BOOKKEEPING,
    )
    assert isinstance(outcome, wpa.Attributed), outcome
    assert canceled_sha in outcome.commits


# ---------------------------------------------------------------------------
# T018 — contested commits (R5/R7)
# ---------------------------------------------------------------------------


def test_overlapping_implementation_windows_are_contested(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    coord_base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-qb", "lane-a")
    _commit_file(repo, "a.py", "1\n", "c1")
    c2 = _commit_file(repo, "b.py", "2\n", "c2")
    c3 = _commit_file(repo, "c.py", "3\n", "c3")
    c4 = _commit_file(repo, "d.py", "4\n", "c4")

    events = [
        _event("e1", "WP01", Lane.PLANNED, Lane.CLAIMED, "t0", stamp=coord_base),
        _event("e2", "WP01", Lane.IN_PROGRESS, Lane.APPROVED, "t1", stamp=c3),
        _event("e3", "WP02", Lane.PLANNED, Lane.CLAIMED, "t2", stamp=c2),
        _event("e4", "WP02", Lane.IN_PROGRESS, Lane.CANCELED, "t3", stamp=c4),
    ]
    outcome = wpa.resolve_canceled_wp(
        repo,
        events=events,
        lane_id=_LANE_ID,
        lane_wp_ids=["WP01", "WP02"],
        canceled_wp_id="WP02",
        lane_branch="lane-a",
        coord_base_ref=coord_base,
        is_bookkeeping=_NO_BOOKKEEPING,
    )
    assert isinstance(outcome, wpa.Unattributable)
    assert outcome.reason is wpa.UnattributableReason.CONTESTED_COMMIT
    assert "lane WPs ran concurrently" in outcome.detail


def test_review_window_commit_contested_by_sibling_review_window(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    coord_base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-qb", "lane-a")
    c1 = _commit_file(repo, "a.py", "1\n", "c1")
    c2 = _commit_file(repo, "b.py", "2\n", "c2")
    c3 = _commit_file(repo, "c.py", "3\n", "c3")

    events = [
        # WP02 (canceled): claims and immediately moves to review AT c1 (an
        # empty implementation window — no overlap risk there), then a review
        # window spans c1..c3 (commits {c2, c3}).
        _event("e1", "WP02", Lane.PLANNED, Lane.CLAIMED, "t0", stamp=c1),
        _event("e2", "WP02", Lane.IN_PROGRESS, Lane.FOR_REVIEW, "t1", stamp=c1),
        _event("e3", "WP02", Lane.FOR_REVIEW, Lane.IN_REVIEW, "t2", stamp=c1),
        _event("e4", "WP02", Lane.IN_REVIEW, Lane.APPROVED, "t3", stamp=c3),
        # WP01 (sibling): review window spans c1..c2 (commit {c2}) — overlaps.
        _event("e5", "WP01", Lane.PLANNED, Lane.CLAIMED, "t0b", stamp=coord_base),
        _event("e6", "WP01", Lane.IN_PROGRESS, Lane.FOR_REVIEW, "t1b", stamp=c1),
        _event("e7", "WP01", Lane.FOR_REVIEW, Lane.IN_REVIEW, "t2b", stamp=c1),
        _event("e8", "WP01", Lane.IN_REVIEW, Lane.APPROVED, "t3b", stamp=c2),
    ]
    outcome = wpa.resolve_canceled_wp(
        repo,
        events=events,
        lane_id=_LANE_ID,
        lane_wp_ids=["WP01", "WP02"],
        canceled_wp_id="WP02",
        lane_branch="lane-a",
        coord_base_ref=coord_base,
        is_bookkeeping=_NO_BOOKKEEPING,
    )
    assert outcome == wpa.Unattributable(
        wpa.UnattributableReason.CONTESTED_COMMIT,
        wpa._contested_detail(_LANE_ID, "WP02", frozenset({c2})),
    )


def test_uncontested_review_fixup_is_attributed(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    coord_base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-qb", "lane-a")
    c1 = _commit_file(repo, "a.py", "1\n", "c1")
    c2 = _commit_file(repo, "review-fix.py", "2\n", "review fixup")

    events = [
        _event("e1", "WP02", Lane.PLANNED, Lane.CLAIMED, "t0", stamp=coord_base),
        _event("e2", "WP02", Lane.IN_PROGRESS, Lane.FOR_REVIEW, "t1", stamp=c1),
        _event("e3", "WP02", Lane.FOR_REVIEW, Lane.IN_REVIEW, "t2", stamp=c1),
        _event("e4", "WP02", Lane.IN_REVIEW, Lane.APPROVED, "t3", stamp=c2),
    ]
    outcome = wpa.resolve_canceled_wp(
        repo,
        events=events,
        lane_id=_LANE_ID,
        lane_wp_ids=["WP02"],
        canceled_wp_id="WP02",
        lane_branch="lane-a",
        coord_base_ref=coord_base,
        is_bookkeeping=_NO_BOOKKEEPING,
    )
    assert isinstance(outcome, wpa.Attributed)
    assert c2 in outcome.commits
    assert c1 in outcome.commits


# ---------------------------------------------------------------------------
# T019 — canceled content (R1, R7, bookkeeping filter)
# ---------------------------------------------------------------------------


def _cancel_window_events(open_stamp: str, close_stamp: str, *, wp_id: str = "WP02") -> list[StatusEvent]:
    return [
        _event("e1", wp_id, Lane.PLANNED, Lane.CLAIMED, "t0", stamp=open_stamp),
        _event("e2", wp_id, Lane.IN_PROGRESS, Lane.CANCELED, "t1", stamp=close_stamp),
    ]


def test_add_modify_delete_unsuperseded(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    coord_base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-qb", "lane-a")
    # WP01 (survivor) adds old.py ON THE LANE, BEFORE WP02's window opens —
    # so it is on the spine (visible to the content walk) but NOT inside
    # WP02's own declared window (window membership is interval-based).
    _commit_file(repo, "src/pkg/old.py", "kept-by-wp01\n", "wp01 adds old.py")
    open_head = _git(repo, "rev-parse", "HEAD")
    _commit_file(repo, "src/pkg/new.py", "v1\n", "wp02 adds new.py")
    _commit_file(repo, "src/pkg/new.py", "v2\n", "wp02 modifies new.py")
    delete_sha = _delete_file(repo, "src/pkg/old.py", "wp02 deletes old.py")

    outcome = wpa.resolve_canceled_wp(
        repo,
        events=_cancel_window_events(open_head, delete_sha),
        lane_id=_LANE_ID,
        lane_wp_ids=["WP01", "WP02"],
        canceled_wp_id="WP02",
        lane_branch="lane-a",
        coord_base_ref=coord_base,
        is_bookkeeping=_NO_BOOKKEEPING,
        # Content semantics only: the survivor commits carry no WP01 events, so
        # the whole lane is anchored (exempt from the FR-013 closed world, which
        # is pinned in its own tests below).
        closed_world_anchors=["lane-a"],
    )
    assert isinstance(outcome, wpa.Attributed)
    by_path = {c.path: c for c in outcome.canceled_content}

    new_state = by_path["src/pkg/new.py"]
    assert new_state.canceled_state == _git(repo, "rev-parse", "HEAD:src/pkg/new.py")
    assert new_state.pre_state is None
    assert new_state.pre_state_by_survivor is False

    old_state = by_path["src/pkg/old.py"]
    assert old_state.canceled_state is None  # deleted
    assert old_state.pre_state == _git(repo, "rev-parse", f"{open_head}:src/pkg/old.py")
    assert old_state.pre_state_by_survivor is True  # WP01 authored the pre-state on the lane


def test_superseded_by_later_survivor_commit_produces_no_entry(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    coord_base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-qb", "lane-a")
    open_head = _git(repo, "rev-parse", "HEAD")
    _commit_file(repo, "src/pkg/shared.py", "canceled-version\n", "wp02 modifies shared.py")
    cancel_sha = _git(repo, "rev-parse", "HEAD")
    # A later, non-canceled (survivor) commit rewrites the same path.
    _commit_file(repo, "src/pkg/shared.py", "survivor-version\n", "wp01 rewrites shared.py")

    events = _cancel_window_events(open_head, cancel_sha)
    outcome = wpa.resolve_canceled_wp(
        repo,
        events=events,
        lane_id=_LANE_ID,
        lane_wp_ids=["WP01", "WP02"],
        canceled_wp_id="WP02",
        lane_branch="lane-a",
        coord_base_ref=coord_base,
        is_bookkeeping=_NO_BOOKKEEPING,
        # Content semantics only: the survivor commits carry no WP01 events, so
        # the whole lane is anchored (exempt from the FR-013 closed world, which
        # is pinned in its own tests below).
        closed_world_anchors=["lane-a"],
    )
    assert isinstance(outcome, wpa.Attributed)
    assert not any(c.path == "src/pkg/shared.py" for c in outcome.canceled_content)


def test_self_revert_dropped(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _commit_file(repo, "src/pkg/x.py", "v0\n", "seed x.py")
    coord_base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-qb", "lane-a")
    open_head = _git(repo, "rev-parse", "HEAD")
    _commit_file(repo, "src/pkg/x.py", "v1\n", "wp02 changes x.py")
    revert_sha = _commit_file(repo, "src/pkg/x.py", "v0\n", "wp02 reverts x.py")

    outcome = wpa.resolve_canceled_wp(
        repo,
        events=_cancel_window_events(open_head, revert_sha),
        lane_id=_LANE_ID,
        lane_wp_ids=["WP02"],
        canceled_wp_id="WP02",
        lane_branch="lane-a",
        coord_base_ref=coord_base,
        is_bookkeeping=_NO_BOOKKEEPING,
    )
    assert isinstance(outcome, wpa.Attributed)
    assert not any(c.path == "src/pkg/x.py" for c in outcome.canceled_content)


def test_survivor_v1_canceled_v0_is_survivor_undone(tmp_path: Path) -> None:
    """R1: survivor sets v1, canceled WP later sets v0 (undoing it) -> entry."""
    repo = _init_repo(tmp_path)
    coord_base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-qb", "lane-a")
    # WP01 (survivor) sets v1 BEFORE WP02's window opens (on the spine, but
    # outside WP02's own interval).
    _commit_file(repo, "src/pkg/y.py", "v1\n", "wp01 sets v1")
    open_head = _git(repo, "rev-parse", "HEAD")
    cancel_sha = _commit_file(repo, "src/pkg/y.py", "v0\n", "wp02 undoes to v0")

    outcome = wpa.resolve_canceled_wp(
        repo,
        events=_cancel_window_events(open_head, cancel_sha),
        lane_id=_LANE_ID,
        lane_wp_ids=["WP01", "WP02"],
        canceled_wp_id="WP02",
        lane_branch="lane-a",
        coord_base_ref=coord_base,
        is_bookkeeping=_NO_BOOKKEEPING,
        # Content semantics only: the survivor commits carry no WP01 events, so
        # the whole lane is anchored (exempt from the FR-013 closed world, which
        # is pinned in its own tests below).
        closed_world_anchors=["lane-a"],
    )
    assert isinstance(outcome, wpa.Attributed)
    by_path = {c.path: c for c in outcome.canceled_content}
    state = by_path["src/pkg/y.py"]
    assert state.canceled_state == _git(repo, "rev-parse", "HEAD:src/pkg/y.py")
    assert state.pre_state == _git(repo, "rev-parse", f"{cancel_sha}^:src/pkg/y.py")
    assert state.pre_state_by_survivor is True


def test_bookkeeping_path_is_ignored(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    coord_base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-qb", "lane-a")
    open_head = _git(repo, "rev-parse", "HEAD")
    (repo / "kitty-specs" / "m").mkdir(parents=True)
    (repo / "kitty-specs/m/status.json").write_text("{}\n", encoding="utf-8")
    (repo / "src/pkg").mkdir(parents=True)
    (repo / "src/pkg/real.py").write_text("real\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "wp02 touches bookkeeping and real content")
    cancel_sha = _git(repo, "rev-parse", "HEAD")

    outcome = wpa.resolve_canceled_wp(
        repo,
        events=_cancel_window_events(open_head, cancel_sha),
        lane_id=_LANE_ID,
        lane_wp_ids=["WP02"],
        canceled_wp_id="WP02",
        lane_branch="lane-a",
        coord_base_ref=coord_base,
        is_bookkeeping=lambda p: p.startswith("kitty-specs/"),
    )
    assert isinstance(outcome, wpa.Attributed)
    paths = {c.path for c in outcome.canceled_content}
    assert "kitty-specs/m/status.json" not in paths
    assert "src/pkg/real.py" in paths


# ---------------------------------------------------------------------------
# T020 — entered_implementation short-circuit + errors
# ---------------------------------------------------------------------------


def test_never_entered_implementation_returns_empty_attributed(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    events = [
        _event("e1", "WP02", Lane.GENESIS, Lane.PLANNED, "t0", stamp=None),
    ]
    outcome = wpa.resolve_canceled_wp(
        repo,
        events=events,
        lane_id=_LANE_ID,
        lane_wp_ids=["WP02"],
        canceled_wp_id="WP02",
        # Deliberately bogus refs: this must short-circuit BEFORE any git read.
        lane_branch="no-such-branch",
        coord_base_ref="no-such-ref-xyz",
        is_bookkeeping=_NO_BOOKKEEPING,
    )
    assert outcome == wpa.Attributed(commits=frozenset(), canceled_content=frozenset())


def test_only_reaching_blocked_is_not_entered_implementation(tmp_path: Path) -> None:
    """Review cycle 1, issue 4: plan.md D-3 step 2 defines "entered
    implementation" as a transition into claimed/in_progress specifically.
    blocked still counts INSIDE an already-open window (R6), but a WP that
    reaches blocked directly from planned -- never claimed/in_progress --
    has done no implementation work to attribute.
    """
    repo = _init_repo(tmp_path)
    events = [
        _event("e1", "WP02", Lane.PLANNED, Lane.BLOCKED, "t0", stamp=None),
        _event("e2", "WP02", Lane.BLOCKED, Lane.CANCELED, "t1", stamp=None),
    ]
    outcome = wpa.resolve_canceled_wp(
        repo,
        events=events,
        lane_id=_LANE_ID,
        lane_wp_ids=["WP02"],
        canceled_wp_id="WP02",
        # Deliberately bogus refs: this must short-circuit BEFORE any git read.
        lane_branch="no-such-branch",
        coord_base_ref="no-such-ref-xyz",
        is_bookkeeping=_NO_BOOKKEEPING,
    )
    assert outcome == wpa.Attributed(commits=frozenset(), canceled_content=frozenset())


def test_unreadable_spine_maps_to_spine_unreadable(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    events = [
        _event("e1", "WP02", Lane.PLANNED, Lane.CLAIMED, "t0", stamp="deadbeef"),
        _event("e2", "WP02", Lane.IN_PROGRESS, Lane.FOR_REVIEW, "t1", stamp="deadbeef"),
    ]
    outcome = wpa.resolve_canceled_wp(
        repo,
        events=events,
        lane_id=_LANE_ID,
        lane_wp_ids=["WP02"],
        canceled_wp_id="WP02",
        lane_branch="main",
        coord_base_ref="no-such-ref-xyz",
        is_bookkeeping=_NO_BOOKKEEPING,
    )
    assert isinstance(outcome, wpa.Unattributable)
    assert outcome.reason is wpa.UnattributableReason.SPINE_UNREADABLE


def test_missing_stamp_reason(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    coord_base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-qb", "lane-a")
    _commit_file(repo, "a.py", "1\n", "c1")

    events = [
        _event("e1", "WP02", Lane.PLANNED, Lane.CLAIMED, "t0", stamp=None),
        _event("e2", "WP02", Lane.IN_PROGRESS, Lane.FOR_REVIEW, "t1", stamp="s1"),
    ]
    outcome = wpa.resolve_canceled_wp(
        repo,
        events=events,
        lane_id=_LANE_ID,
        lane_wp_ids=["WP02"],
        canceled_wp_id="WP02",
        lane_branch="lane-a",
        coord_base_ref=coord_base,
        is_bookkeeping=_NO_BOOKKEEPING,
    )
    assert isinstance(outcome, wpa.Unattributable)
    assert outcome.reason is wpa.UnattributableReason.NO_STAMP


def test_open_window_reason(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    coord_base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-qb", "lane-a")
    open_head = _git(repo, "rev-parse", "HEAD")
    _commit_file(repo, "a.py", "1\n", "c1")

    events = [
        _event("e1", "WP02", Lane.PLANNED, Lane.CLAIMED, "t0", stamp=open_head),
    ]
    outcome = wpa.resolve_canceled_wp(
        repo,
        events=events,
        lane_id=_LANE_ID,
        lane_wp_ids=["WP02"],
        canceled_wp_id="WP02",
        lane_branch="lane-a",
        coord_base_ref=coord_base,
        is_bookkeeping=_NO_BOOKKEEPING,
    )
    assert isinstance(outcome, wpa.Unattributable)
    assert outcome.reason is wpa.UnattributableReason.OPEN_WINDOW


# ---------------------------------------------------------------------------
# FR-011 — migration-synthesized events never affect attribution
# ---------------------------------------------------------------------------

_BACKFILL_ACTOR = "migration:backfill_runtime_state"


def test_migration_actor_prefix_names_the_backfill_actor() -> None:
    """The module constant is the ``migration:<module>`` convention the backfill uses."""
    from specify_cli.migration.backfill_runtime_state import BACKFILL_ACTOR

    assert BACKFILL_ACTOR.startswith(wpa.MIGRATION_ACTOR_PREFIX)
    assert _BACKFILL_ACTOR == BACKFILL_ACTOR


def test_seed_event_after_cancel_does_not_reopen_a_window() -> None:
    """FR-011: a backfill seed ``planned -> claimed`` appended after the cancel
    (unstamped) must not open a never-closing window."""
    events = [
        _event("e1", "WP02", Lane.PLANNED, Lane.CLAIMED, "t0", stamp="s-open"),
        _event("e2", "WP02", Lane.IN_PROGRESS, Lane.CANCELED, "t1", stamp="s-close"),
        _event("e3", "WP02", Lane.PLANNED, Lane.CLAIMED, "t2", actor=_BACKFILL_ACTOR),
    ]
    windows = wpa._windows(events, frozenset({"WP02"}))
    assert windows["WP02"] == [
        wpa.WorkWindow(wp_id="WP02", kind=wpa.WindowKind.IMPLEMENTATION, open_head="s-open", close_head="s-close", still_open=False),
    ]


def test_seed_event_for_wp_canceled_from_planned_is_not_entered_implementation() -> None:
    """FR-011: a seed ``planned -> claimed`` for a WP canceled straight from
    ``planned`` does NOT make it "entered implementation"."""
    events = [
        _event("e1", "WP02", Lane.PLANNED, Lane.CANCELED, "t0"),
        _event("e2", "WP02", Lane.PLANNED, Lane.CLAIMED, "t1", actor=_BACKFILL_ACTOR),
    ]
    assert wpa._entered_implementation(events, "WP02") is False
    assert wpa._entered_implementation([*events, _event("e3", "WP02", Lane.PLANNED, Lane.CLAIMED, "t2")], "WP02") is True


def test_seed_events_after_fail_keep_resolution_attributed(tmp_path: Path) -> None:
    """FR-011 end to end through the resolver: seeds for BOTH lane WPs appended
    after the cancel leave the canceled content resolvable (no ``open_window``)."""
    repo = _init_repo(tmp_path)
    coord_base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-qb", "lane-a")
    open_head = _git(repo, "rev-parse", "HEAD")
    cancel_sha = _commit_file(repo, "src/pkg/leak.py", "leak\n", "wp02 leaks")
    events = [
        *_cancel_window_events(open_head, cancel_sha),
        _event("s1", "WP01", Lane.PLANNED, Lane.CLAIMED, "t8", actor=_BACKFILL_ACTOR),
        _event("s2", "WP02", Lane.PLANNED, Lane.CLAIMED, "t9", actor=_BACKFILL_ACTOR),
    ]
    outcome = wpa.resolve_canceled_wp(
        repo,
        events=events,
        lane_id=_LANE_ID,
        lane_wp_ids=["WP01", "WP02"],
        canceled_wp_id="WP02",
        lane_branch="lane-a",
        coord_base_ref=coord_base,
        is_bookkeeping=_NO_BOOKKEEPING,
    )
    assert isinstance(outcome, wpa.Attributed)
    assert {c.path for c in outcome.canceled_content} == {"src/pkg/leak.py"}


# ---------------------------------------------------------------------------
# FR-013 — closed world on mixed lanes
# ---------------------------------------------------------------------------


def test_detail_for_is_total_over_every_reason() -> None:
    """Every UnattributableReason renders (no KeyError) and names lane + WP."""
    for reason in wpa.UnattributableReason:
        detail = wpa._detail_for(reason, _LANE_ID, "WP02", commits=["a" * 40], path="src/x.py")
        assert _LANE_ID in detail, reason
        assert "WP02" in detail, reason


def test_short_sha_sample_summarises_the_rest() -> None:
    shas = [f"{i:040d}" for i in range(5)]
    assert wpa._short_shas(shas).endswith("and 2 more")
    assert wpa._short_shas([]) == "(none recorded)"


def _survivor_then_canceled_lane(repo: Path) -> tuple[str, list[StatusEvent]]:
    """WP01 commits inside its own stamped window; WP02 commits inside its own; returns coord base + events."""
    coord_base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-qb", "lane-a")
    wp01_sha = _commit_file(repo, "src/pkg/wp01.py", "wp01\n", "wp01 work")
    wp02_sha = _commit_file(repo, "src/pkg/wp02.py", "wp02\n", "wp02 work")
    events = [
        _event("e1", "WP01", Lane.PLANNED, Lane.CLAIMED, "t0", stamp=coord_base),
        _event("e2", "WP01", Lane.IN_PROGRESS, Lane.FOR_REVIEW, "t1", stamp=wp01_sha),
        _event("e3", "WP01", Lane.IN_REVIEW, Lane.APPROVED, "t2", stamp=wp01_sha),
        _event("e4", "WP02", Lane.PLANNED, Lane.CLAIMED, "t3", stamp=wp01_sha),
        _event("e5", "WP02", Lane.IN_PROGRESS, Lane.CANCELED, "t4", stamp=wp02_sha),
    ]
    return coord_base, events


def _no_bookkeeping(_path: str) -> bool:
    return False


def _resolve(
    repo: Path,
    coord_base: str,
    events: list[StatusEvent],
    *,
    anchors: Sequence[str] = (),
    bookkeeping: Callable[[str], bool] = _no_bookkeeping,
) -> wpa.AttributionOutcome:
    return wpa.resolve_canceled_wp(
        repo,
        events=events,
        lane_id=_LANE_ID,
        lane_wp_ids=["WP01", "WP02"],
        canceled_wp_id="WP02",
        lane_branch="lane-a",
        coord_base_ref=coord_base,
        is_bookkeeping=bookkeeping,
        closed_world_anchors=anchors,
    )


def test_every_commit_inside_a_window_passes_the_closed_world(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    coord_base, events = _survivor_then_canceled_lane(repo)
    outcome = _resolve(repo, coord_base, events)
    assert isinstance(outcome, wpa.Attributed)
    assert {c.path for c in outcome.canceled_content} == {"src/pkg/wp02.py"}


def test_straggler_after_cancel_is_commit_outside_windows(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    coord_base, events = _survivor_then_canceled_lane(repo)
    straggler = _commit_file(repo, "src/pkg/straggler.py", "late\n", "straggler after cancel")
    outcome = _resolve(repo, coord_base, events)
    assert isinstance(outcome, wpa.Unattributable)
    assert outcome.reason is wpa.UnattributableReason.COMMIT_OUTSIDE_WINDOWS
    assert straggler[:10] in outcome.detail
    assert "'src/pkg/straggler.py'" in outcome.detail
    assert _LANE_ID in outcome.detail


def test_attestation_anchor_exempts_earlier_stragglers_and_keeps_canceled_content(tmp_path: Path) -> None:
    """FR-012: an attestation stamp anchors the closed world; visible canceled content stays."""
    repo = _init_repo(tmp_path)
    coord_base, events = _survivor_then_canceled_lane(repo)
    attest_stamp = _commit_file(repo, "src/pkg/straggler.py", "late\n", "straggler after cancel")
    outcome = _resolve(repo, coord_base, events, anchors=[attest_stamp])
    assert isinstance(outcome, wpa.Attributed)
    assert {c.path for c in outcome.canceled_content} == {"src/pkg/wp02.py"}


def test_bookkeeping_only_commit_outside_windows_is_not_flagged(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    coord_base, events = _survivor_then_canceled_lane(repo)
    _commit_file(repo, "kitty-specs/m/status.json", "{}\n", "bookkeeping after cancel")
    outcome = _resolve(repo, coord_base, events, bookkeeping=lambda p: p.startswith("kitty-specs/"))
    assert isinstance(outcome, wpa.Attributed)


def test_merge_commit_outside_windows_is_not_flagged(tmp_path: Path) -> None:
    """An "evil merge" -- a merge commit that introduces its OWN non-bookkeeping
    content beyond a clean resolution of its two parents -- is still exempt
    from the closed-world content check (R3/B4: merges never attribute or
    supersede, even when the merge commit carries its own diff)."""
    repo = _init_repo(tmp_path)
    coord_base, events = _survivor_then_canceled_lane(repo)
    _git(repo, "checkout", "-qb", "side", coord_base)
    _commit_file(repo, "kitty-specs/m/notes.md", "n\n", "side note")
    _git(repo, "checkout", "-q", "lane-a")
    _git(repo, "merge", "-q", "--no-ff", "--no-commit", "side")
    _commit_file(repo, "src/pkg/merge_only.py", "merge only\n", "evil merge: adds content of its own")
    outcome = _resolve(repo, coord_base, events, bookkeeping=lambda p: p.startswith("kitty-specs/"))
    assert isinstance(outcome, wpa.Attributed)
    assert {c.path for c in outcome.canceled_content} == {"src/pkg/wp02.py"}


def test_never_implemented_canceled_wp_with_resolved_sibling_is_closed_world_checked(tmp_path: Path) -> None:
    """The never-claimed residual: WP02 canceled from planned, an out-of-workflow commit outside WP01's window."""
    repo = _init_repo(tmp_path)
    coord_base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-qb", "lane-a")
    wp01_sha = _commit_file(repo, "src/pkg/wp01.py", "wp01\n", "wp01 work")
    stray = _commit_file(repo, "src/pkg/stray.py", "stray\n", "out-of-workflow commit")
    events = [
        _event("e1", "WP01", Lane.PLANNED, Lane.CLAIMED, "t0", stamp=coord_base),
        _event("e2", "WP01", Lane.IN_PROGRESS, Lane.FOR_REVIEW, "t1", stamp=wp01_sha),
        _event("e3", "WP01", Lane.IN_REVIEW, Lane.APPROVED, "t2", stamp=wp01_sha),
        _event("e4", "WP02", Lane.PLANNED, Lane.CANCELED, "t3"),
    ]
    outcome = _resolve(repo, coord_base, events)
    assert isinstance(outcome, wpa.Unattributable)
    assert outcome.reason is wpa.UnattributableReason.COMMIT_OUTSIDE_WINDOWS
    assert stray[:10] in outcome.detail


def test_never_implemented_canceled_wp_with_unstamped_sibling_keeps_legacy_behaviour(tmp_path: Path) -> None:
    """SC-004: a legacy (unstamped) lane whose canceled WP never entered implementation is unchanged."""
    repo = _init_repo(tmp_path)
    coord_base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-qb", "lane-a")
    _commit_file(repo, "src/pkg/wp01.py", "wp01\n", "wp01 work")
    events = [
        _event("e1", "WP01", Lane.PLANNED, Lane.CLAIMED, "t0"),
        _event("e2", "WP01", Lane.IN_PROGRESS, Lane.FOR_REVIEW, "t1"),
        _event("e3", "WP02", Lane.PLANNED, Lane.CANCELED, "t3"),
    ]
    assert _resolve(repo, coord_base, events) == wpa.Attributed(commits=frozenset(), canceled_content=frozenset())


def _dep_lane_repo(repo: Path) -> tuple[str, str]:
    """``dep`` carries a dependency WP's commit; returns (coord_base, dep_sha)."""
    coord_base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-qb", "dep", coord_base)
    dep_sha = _commit_file(repo, "src/pkg/dep.py", "dep\n", "WP03 dependency-lane work")
    return coord_base, dep_sha


def _two_wp_events(open_stamp: str, wp01_close: str, wp02_close: str) -> list[StatusEvent]:
    return [
        _event("e1", "WP01", Lane.PLANNED, Lane.CLAIMED, "t0", stamp=open_stamp),
        _event("e2", "WP01", Lane.IN_PROGRESS, Lane.FOR_REVIEW, "t1", stamp=wp01_close),
        _event("e3", "WP01", Lane.IN_REVIEW, Lane.APPROVED, "t2", stamp=wp01_close),
        _event("e4", "WP02", Lane.PLANNED, Lane.CLAIMED, "t3", stamp=wp01_close),
        _event("e5", "WP02", Lane.IN_PROGRESS, Lane.CANCELED, "t4", stamp=wp02_close),
    ]


def test_dependency_lane_fast_forwarded_before_first_claim_is_not_outside(tmp_path: Path) -> None:
    """Review BLOCKER: the allocator merges a dependency lane without --no-ff before work starts."""
    repo = _init_repo(tmp_path)
    coord_base, _dep_sha = _dep_lane_repo(repo)
    _git(repo, "checkout", "-qb", "lane-a", coord_base)
    _git(repo, "merge", "-q", "--no-edit", "dep")  # fast-forward
    open_stamp = _git(repo, "rev-parse", "HEAD")
    wp01 = _commit_file(repo, "src/pkg/wp01.py", "wp01\n", "wp01 work")
    wp02 = _commit_file(repo, "src/pkg/wp02.py", "wp02\n", "wp02 work")
    outcome = _resolve(repo, coord_base, _two_wp_events(open_stamp, wp01, wp02))
    assert isinstance(outcome, wpa.Attributed), outcome
    assert {c.path for c in outcome.canceled_content} == {"src/pkg/wp02.py"}


def test_dependency_lane_merged_after_work_began_is_off_spine_without_an_anchor(tmp_path: Path) -> None:
    """The allocator's reuse path merges the dependency lane again later. The
    merge commit itself is on the first-parent spine (and skipped, R3/B4),
    but the dependency commit it carries is on the merge's SECOND parent
    only — off the first-parent spine entirely — so there is nothing to
    exempt and no anchor is needed."""
    repo = _init_repo(tmp_path)
    coord_base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-qb", "lane-a")
    wp01 = _commit_file(repo, "src/pkg/wp01.py", "wp01\n", "wp01 work")
    _git(repo, "checkout", "-qb", "dep", coord_base)
    _commit_file(repo, "src/pkg/dep.py", "dep\n", "WP03 dependency-lane work")
    _git(repo, "checkout", "-q", "lane-a")
    _git(repo, "merge", "-q", "--no-edit", "-m", "Merge dependency lane", "dep")
    wp02_open = _git(repo, "rev-parse", "HEAD")
    wp02 = _commit_file(repo, "src/pkg/wp02.py", "wp02\n", "wp02 work")
    events = _two_wp_events(coord_base, wp01, wp02)
    events[3] = _event("e4", "WP02", Lane.PLANNED, Lane.CLAIMED, "t3", stamp=wp02_open)
    outcome = _resolve(repo, coord_base, events)
    assert isinstance(outcome, wpa.Attributed), outcome
    assert {c.path for c in outcome.canceled_content} == {"src/pkg/wp02.py"}


def test_dependency_tip_anchor_exempts_a_later_fast_forward(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    coord_base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-qb", "lane-a")
    wp01 = _commit_file(repo, "src/pkg/wp01.py", "wp01\n", "wp01 work")
    # dep branches off lane-a's current head and adds work, then lane-a fast-forwards to it.
    _git(repo, "checkout", "-qb", "dep")
    _commit_file(repo, "src/pkg/dep.py", "dep\n", "WP03 dependency-lane work")
    _git(repo, "checkout", "-q", "lane-a")
    _git(repo, "merge", "-q", "--no-edit", "dep")  # fast-forward after work began
    wp02_open = _git(repo, "rev-parse", "HEAD")
    wp02 = _commit_file(repo, "src/pkg/wp02.py", "wp02\n", "wp02 work")
    events = _two_wp_events(coord_base, wp01, wp02)
    events[3] = _event("e4", "WP02", Lane.PLANNED, Lane.CLAIMED, "t3", stamp=wp02_open)
    refused = _resolve(repo, coord_base, events)
    assert isinstance(refused, wpa.Unattributable) and refused.reason is wpa.UnattributableReason.COMMIT_OUTSIDE_WINDOWS
    anchored = wpa.resolve_canceled_wp(
        repo,
        events=events,
        lane_id=_LANE_ID,
        lane_wp_ids=["WP01", "WP02"],
        canceled_wp_id="WP02",
        lane_branch="lane-a",
        coord_base_ref=coord_base,
        is_bookkeeping=_NO_BOOKKEEPING,
        closed_world_anchors=["dep", "no-such-anchor-ref"],  # an unreadable anchor is skipped
    )
    assert isinstance(anchored, wpa.Attributed), anchored


def test_target_tip_anchor_exempts_fast_forwarded_target_commits(tmp_path: Path) -> None:
    """Planning-commit merge shape: target-branch commits fast-forwarded onto the lane are already shipped."""
    repo = _init_repo(tmp_path)
    coord_base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-qb", "lane-a")
    wp01 = _commit_file(repo, "src/pkg/wp01.py", "wp01\n", "wp01 work")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "-q", "--no-edit", "lane-a")  # main moves to wp01 ...
    _commit_file(repo, "src/other.py", "someone else\n", "another developer's commit on main")
    _git(repo, "checkout", "-q", "lane-a")
    _git(repo, "merge", "-q", "--no-edit", "main")  # ... and the lane fast-forwards to it
    wp02_open = _git(repo, "rev-parse", "HEAD")
    wp02 = _commit_file(repo, "src/pkg/wp02.py", "wp02\n", "wp02 work")
    events = _two_wp_events(coord_base, wp01, wp02)
    events[3] = _event("e4", "WP02", Lane.PLANNED, Lane.CLAIMED, "t3", stamp=wp02_open)
    assert isinstance(_resolve(repo, coord_base, events), wpa.Unattributable)
    anchored = wpa.resolve_canceled_wp(
        repo,
        events=events,
        lane_id=_LANE_ID,
        lane_wp_ids=["WP01", "WP02"],
        canceled_wp_id="WP02",
        lane_branch="lane-a",
        coord_base_ref=coord_base,
        is_bookkeeping=_NO_BOOKKEEPING,
        closed_world_anchors=["main"],
    )
    assert isinstance(anchored, wpa.Attributed), anchored


def test_git_probe_error_type_still_available() -> None:
    """Sanity: the module re-uses the shared GitProbeError type (no shadow class)."""
    assert issubclass(GitProbeError, RuntimeError)
