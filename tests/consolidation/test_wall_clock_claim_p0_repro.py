"""Regression guard for the P0 #4941: a rejection minted on a slower clock is not lost to the gate.

This began as the red-first reproduction (ADR 2026-07-17-1); it ran only in the
nightly ``p0-repro`` lane until the fix landed. The fix (spec-kitty-events#101,
consumed from ``spec-kitty-events>=10.5.1``) re-orders a non-seed departure from
``approved`` after the approval it followed, so the ``p0_repro`` marker is removed
and this is now an ordinary per-PR guard.

The gate's claim reads WP membership through ``status.reducer.materialize_snapshot``
→ ``spec_kitty_events.status.reduce`` (the diary reducer). Before the fix it
ordered lane transitions by their ``at`` timestamp alone, so a departure from
``approved`` carrying an earlier ``at`` than a clock-ahead approval sorted before
its own approval and was dropped as causally stale. The fixed reducer lifts such
a departure's sort key to its approval's ``at``.

The #4941 sequence, with real temp git and the real emitter:

1. Reviewer A approves WP02 from a machine whose clock is 10 minutes ahead, so
   the approval row carries an ``at`` in the future. The row is written by hand,
   which is also how a teammate's row arrives through ``git pull`` and the
   status-log union driver.
2. Reviewer B, on a correct clock, rejects WP02 through
   :func:`emit_status_transition` (``approved -> in_progress``). The emitter
   accepts it and stamps it with the real time, before the approval's ``at``.
3. The reducer orders the rejection before the approval, and the
   consolidation claim keeps WP02 as approved, so ``consolidate`` lands rejected
   content on the target.

The issue accepts either remedy, and so does this test: the rejection takes
effect (the claim drops WP02), or the emitter refuses it with a
``TransitionError`` and nothing is recorded. A control runs the same emit with
the approval stamped in the past, so a refusal for any other reason fails the
control, not the reproduction.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import tests.consolidation.test_reconciliation as recon_fixture
from kernel.clock import now_utc, timedelta
from specify_cli.consolidation.reconciliation import build_approved_wp_set
from specify_cli.lanes.models import LanesManifest
from specify_cli.status import TransitionError
from specify_cli.status.emit import emit_status_transition
from specify_cli.status.reducer import materialize_snapshot

pytestmark = [pytest.mark.git_repo]

#: How far reviewer A's clock runs ahead of reviewer B's.
_CLOCK_SKEW = timedelta(minutes=10)


def _mission_with_approval_at(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, approval_at: str | None) -> tuple[Path, Path, LanesManifest, str]:
    """Build WP01 + WP02 approved; restamp WP02's approval at *approval_at* (None keeps the fixture's past stamp).

    Every row is written without ``lamport_clock``, as the CLI writes lane transitions.
    """
    original = recon_fixture._commit_status_log

    def _write_like_the_cli(repo: Path, feature_dir: Path, events: list[dict[str, object]], message: str) -> None:
        rows = [{k: v for k, v in event.items() if k != "lamport_clock"} for event in events]
        for row in rows:
            if approval_at is not None and row["wp_id"] == "WP02" and row["to_lane"] == "approved":
                row["at"] = approval_at
        original(repo, feature_dir, rows, message)

    monkeypatch.setattr(recon_fixture, "_commit_status_log", _write_like_the_cli)
    tmp_path.mkdir()
    return recon_fixture._build_mission(tmp_path, approved_wps=("WP01", "WP02"))


def _reviewer_b_rejects(feature_dir: Path) -> TransitionError | None:
    """Reject WP02 through the real emitter on the real clock; return the refusal, if any."""
    try:
        emit_status_transition(
            feature_dir,
            wp_id="WP02",
            to_lane="in_progress",
            actor="reviewer-b",
            mission_slug=recon_fixture._MISSION_SLUG,
            reason="review: changes requested",
            review_ref="review-feedback-WP02",
        )
    except TransitionError as refusal:
        return refusal
    return None


def _wp02_lane(feature_dir: Path) -> str:
    return str((materialize_snapshot(feature_dir).work_packages or {}).get("WP02", {}).get("lane", ""))


def test_rejection_on_a_slower_clock_leaves_the_claim(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Control: approval stamped in the past, so the rejection is honored. This proves the
    # fixture, the emitter call and the claim wiring before the reproduction runs.
    repo, feature_dir, manifest, coord_base = _mission_with_approval_at(tmp_path / "control", monkeypatch, None)
    assert _wp02_lane(feature_dir) == "approved", "setup: WP02 is not approved before the rejection"
    refusal = _reviewer_b_rejects(feature_dir)
    assert refusal is None, f"setup: the emitter refused an ordinary rejection: {refusal}"
    claim = build_approved_wp_set(repo, feature_dir, manifest, coord_base_ref=coord_base)
    assert claim.surface_resolved, f"setup: the claim did not resolve: {claim.refusal}"
    assert set(claim.approved) == {"WP01"}, "setup: an on-time rejection was not honored"

    # Reproduction: the only change is that reviewer A's clock runs 10 minutes ahead.
    future = (now_utc() + _CLOCK_SKEW).isoformat()
    repo, feature_dir, manifest, coord_base = _mission_with_approval_at(tmp_path / "skewed", monkeypatch, future)
    assert _wp02_lane(feature_dir) == "approved", "setup: WP02 is not approved before the rejection"
    refusal = _reviewer_b_rejects(feature_dir)
    if refusal is not None:
        return  # the emitter refused the out-of-order rejection with a diagnostic: an accepted remedy
    claim = build_approved_wp_set(repo, feature_dir, manifest, coord_base_ref=coord_base)
    assert claim.surface_resolved, f"setup: the claim did not resolve: {claim.refusal}"
    assert "WP01" in claim.approved
    assert "WP02" not in claim.approved, (
        "#4941: the emitter accepted reviewer B's rejection, yet the consolidation claim keeps WP02 as "
        f"approved (WP02 reduces to {_wp02_lane(feature_dir)!r}), so consolidate would land rejected "
        "content on the target. The rejection was stamped on the real clock, before the approval's "
        "future 'at', and the reducer ordered it first."
    )
