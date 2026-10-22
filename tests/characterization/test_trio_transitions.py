"""Status-reducer transition characterization for the coord-authority trio.

WP01 (coord-authority-trio-degod-01KX7094) -- T004. Two things are pinned
here:

1. ``acceptance._collect_snapshot_wps`` (the trio's sole read of the reduced
   status snapshot) across a genuine ``next``/decision-loop event sequence:
   claim -> implement -> review -> REJECT -> RESUME -> re-review -> approve
   -> done. Rejection carries a ``review_ref`` pointer (the rewind); resume
   is the implementer re-claiming after rejection; both must reduce to the
   correct current lane at every checkpoint.

2. The lenient not-exists DEGRADE contract of the trio's status reads
   (FR-008 / squad directive): ``acceptance._status_read_feature_dir``
   degrades to the primary ``feature_dir`` when the resolved status
   directory does not exist on disk -- it does NOT raise. This is
   explicitly contrasted with ``workflow._canonical_status_feature_dir``,
   which has NO such fallback and returns the (possibly nonexistent)
   resolved path directly. The trio's two status-dir readers behave
   DIFFERENTLY on a not-yet-materialized coordination worktree; that
   asymmetry is itself pinned behaviour, not an oversight to "fix" here.

Marker: unit only (no subprocess, no real git -- filesystem use is confined
to ``tmp_path``, per the ``unit`` marker's contract in ``pytest.ini``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kernel.clock import UTC, datetime, timedelta
from specify_cli.acceptance import AcceptanceError, _collect_snapshot_wps, _status_read_feature_dir
from specify_cli.cli.commands.agent.workflow import _canonical_status_feature_dir
from specify_cli.status import EVENTS_FILENAME, Lane, StatusEvent
from tests._support.status_seed import seed_status_event

pytestmark = [pytest.mark.unit]

_CORRUPTED_EVENTS_QUARANTINE = pytest.mark.quarantine(
    reason="spec-kitty#1021: flakes under the full parallel main baseline"
    " (main @a7b8bd306 2026-09-01T10:32Z and again @5396f812 2026-09-01T12:03Z);"
    " passes on the serial re-run and in isolation. Root cause (hidden"
    " cross-test nondeterminism in the status event-log read path) is tracked"
    " in the issue; this quarantine is debt, remove on root-cause fix."
)

# Fixed base instant + a monotonic per-event offset -- deterministic ordering
# for the reducer's ``(at, event_id)`` sort without any wall-clock read
# (repo-local guard: no live ``datetime.now()`` inside test assertions).
_BASE_INSTANT = datetime(2026, 1, 1, tzinfo=UTC)


# ===========================================================================
# Section A -- next/decision-loop reduction: claim -> ... -> reject -> resume
# ===========================================================================


def _event(
    *, wp_id: str, from_lane: Lane, to_lane: Lane, event_id: str, seq: int, review_ref: str | None = None, force: bool = False
) -> StatusEvent:
    return StatusEvent(
        event_id=event_id,
        mission_slug="trio-mission",
        wp_id=wp_id,
        from_lane=from_lane,
        to_lane=to_lane,
        at=(_BASE_INSTANT + timedelta(seconds=seq)).isoformat(),
        actor="test-actor",
        force=force,
        execution_mode="worktree",
        review_ref=review_ref,
    )


class TestCollectSnapshotWpsAcrossTheDecisionLoop:
    """``_collect_snapshot_wps`` wraps ``reduce(read_events(...))`` -- pin the
    lane it reports at every checkpoint of a full rejection/resume cycle."""

    def test_full_lifecycle_including_rejection_and_resume(self, tmp_path: Path) -> None:
        feature_dir = tmp_path / "kitty-specs" / "trio-mission"
        feature_dir.mkdir(parents=True)
        activity_issues: list[str] = []

        def _lane_after(event: StatusEvent) -> str | None:
            seed_status_event(feature_dir, event)
            snapshot = _collect_snapshot_wps("trio-mission", feature_dir, activity_issues)
            wp = snapshot.get("WP01")
            return wp.get("lane") if wp else None

        # Arrange + Act interleaved: each step is both an Act and an
        # Assumption-check for the next step (checkpoint style).

        # claim
        assert _lane_after(_event(wp_id="WP01", from_lane=Lane.PLANNED, to_lane=Lane.CLAIMED, event_id="01STEP0000000000000000001", seq=1)) == "claimed"
        # implement
        assert _lane_after(_event(wp_id="WP01", from_lane=Lane.CLAIMED, to_lane=Lane.IN_PROGRESS, event_id="01STEP0000000000000000002", seq=2)) == "in_progress"
        # submit for review
        assert _lane_after(_event(wp_id="WP01", from_lane=Lane.IN_PROGRESS, to_lane=Lane.FOR_REVIEW, event_id="01STEP0000000000000000003", seq=3)) == "for_review"
        # reviewer claims
        assert _lane_after(_event(wp_id="WP01", from_lane=Lane.FOR_REVIEW, to_lane=Lane.IN_REVIEW, event_id="01STEP0000000000000000004", seq=4)) == "in_review"
        # REJECT (rewind): in_review -> planned, carrying the review_ref pointer
        pointer = "review-cycle://trio-mission/WP01/review-cycle-1.md"
        assert (
            _lane_after(
                _event(wp_id="WP01", from_lane=Lane.IN_REVIEW, to_lane=Lane.PLANNED, event_id="01STEP0000000000000000005", seq=5, review_ref=pointer)
            )
            == "planned"
        )
        # RESUME: implementer re-claims after rejection
        assert _lane_after(_event(wp_id="WP01", from_lane=Lane.PLANNED, to_lane=Lane.IN_PROGRESS, event_id="01STEP0000000000000000006", seq=6)) == "in_progress"
        # re-submit, re-review, approve, done
        assert _lane_after(_event(wp_id="WP01", from_lane=Lane.IN_PROGRESS, to_lane=Lane.FOR_REVIEW, event_id="01STEP0000000000000000007", seq=7)) == "for_review"
        assert _lane_after(_event(wp_id="WP01", from_lane=Lane.FOR_REVIEW, to_lane=Lane.IN_REVIEW, event_id="01STEP0000000000000000008", seq=8)) == "in_review"
        assert _lane_after(_event(wp_id="WP01", from_lane=Lane.IN_REVIEW, to_lane=Lane.APPROVED, event_id="01STEP0000000000000000009", seq=9)) == "approved"
        assert _lane_after(_event(wp_id="WP01", from_lane=Lane.APPROVED, to_lane=Lane.DONE, event_id="01STEP0000000000000000010", seq=10)) == "done"

        # Assert: no activity issues accumulated across a clean, fully-reduced lifecycle
        assert activity_issues == []

    def test_blocked_then_force_reopen_is_reduced_correctly(self, tmp_path: Path) -> None:
        """A blocked WP force-reopened back to in_progress -- a second
        "rewind" shape distinct from a reviewer rejection."""
        feature_dir = tmp_path / "kitty-specs" / "trio-mission"
        feature_dir.mkdir(parents=True)
        seed_status_event(
            feature_dir,
            _event(wp_id="WP01", from_lane=Lane.IN_PROGRESS, to_lane=Lane.BLOCKED, event_id="01BLOCK000000000000000001", seq=1, force=True),
        )
        seed_status_event(
            feature_dir,
            _event(wp_id="WP01", from_lane=Lane.BLOCKED, to_lane=Lane.IN_PROGRESS, event_id="01BLOCK000000000000000002", seq=2, force=True),
        )
        activity_issues: list[str] = []

        snapshot = _collect_snapshot_wps("trio-mission", feature_dir, activity_issues)

        assert snapshot["WP01"]["lane"] == "in_progress"
        assert activity_issues == []

    def test_missing_events_file_appends_bootstrap_hint_and_returns_empty(self, tmp_path: Path) -> None:
        feature_dir = tmp_path / "kitty-specs" / "trio-mission"
        feature_dir.mkdir(parents=True)
        activity_issues: list[str] = []

        # Assumption check
        assert not (feature_dir / EVENTS_FILENAME).exists()

        snapshot = _collect_snapshot_wps("trio-mission", feature_dir, activity_issues)

        assert snapshot == {}
        assert len(activity_issues) == 1
        assert "finalize-tasks" in activity_issues[0]

    @_CORRUPTED_EVENTS_QUARANTINE
    def test_corrupted_events_file_raises_acceptance_error(self, tmp_path: Path) -> None:
        feature_dir = tmp_path / "kitty-specs" / "trio-mission"
        feature_dir.mkdir(parents=True)
        (feature_dir / EVENTS_FILENAME).write_text("not-json-at-all\n", encoding="utf-8")
        activity_issues: list[str] = []

        with pytest.raises(AcceptanceError, match="Status event log is corrupted"):
            _collect_snapshot_wps("trio-mission", feature_dir, activity_issues)

    def test_empty_events_file_appends_bootstrap_hint(self, tmp_path: Path) -> None:
        """An events file that exists but reduces to zero work packages
        (e.g. truncated to empty) is treated the same as "missing"."""
        feature_dir = tmp_path / "kitty-specs" / "trio-mission"
        feature_dir.mkdir(parents=True)
        (feature_dir / EVENTS_FILENAME).write_text("", encoding="utf-8")
        activity_issues: list[str] = []

        snapshot = _collect_snapshot_wps("trio-mission", feature_dir, activity_issues)

        assert snapshot == {}
        assert len(activity_issues) == 1
        assert "finalize-tasks" in activity_issues[0]


# ===========================================================================
# Section B -- the lenient not-exists DEGRADE contract (FR-008)
# ===========================================================================


class TestLenientStatusReadDegradeContract:
    """``acceptance._status_read_feature_dir`` degrades to ``feature_dir``
    when the resolved status directory does not exist; it never raises.
    ``workflow._canonical_status_feature_dir`` has NO such fallback -- this
    asymmetry between the trio's two status-dir readers is pinned here so a
    refactor cannot silently unify (or further diverge) them by accident."""

    def test_acceptance_degrades_to_feature_dir_when_resolved_status_dir_absent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        feature_dir = tmp_path / "kitty-specs" / "trio-mission"
        feature_dir.mkdir(parents=True)
        unmaterialized_coord = tmp_path / "coord-worktree" / "kitty-specs" / "trio-mission"

        # Assumption check
        assert not unmaterialized_coord.exists()
        assert feature_dir.exists()

        monkeypatch.setattr(
            "specify_cli.missions._read_path_resolver.resolve_handle_to_read_path",
            lambda _repo, _handle: unmaterialized_coord,
        )

        result = _status_read_feature_dir(tmp_path, "trio-mission", feature_dir)

        # Degrades to the primary anchor -- does NOT raise, does NOT return
        # the nonexistent coord candidate.
        assert result == feature_dir

    def test_acceptance_uses_resolved_dir_when_it_exists(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        feature_dir = tmp_path / "kitty-specs" / "trio-mission"
        feature_dir.mkdir(parents=True)
        materialized_coord = tmp_path / "coord-worktree" / "kitty-specs" / "trio-mission"
        materialized_coord.mkdir(parents=True)

        monkeypatch.setattr(
            "specify_cli.missions._read_path_resolver.resolve_handle_to_read_path",
            lambda _repo, _handle: materialized_coord,
        )

        result = _status_read_feature_dir(tmp_path, "trio-mission", feature_dir)

        assert result == materialized_coord

    def test_workflow_canonical_status_dir_has_no_fallback_and_returns_nonexistent_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Contrast case: ``workflow._canonical_status_feature_dir`` passes the
        seam's result straight through, unlike acceptance's degrade wrapper."""
        feature_dir = tmp_path / "kitty-specs" / "trio-mission"
        feature_dir.mkdir(parents=True)
        unmaterialized_coord = tmp_path / "coord-worktree" / "kitty-specs" / "trio-mission"

        assert not unmaterialized_coord.exists()

        monkeypatch.setattr(
            "specify_cli.missions._read_path_resolver.resolve_handle_to_read_path",
            lambda _repo, _handle: unmaterialized_coord,
        )

        result = _canonical_status_feature_dir(tmp_path, "trio-mission")

        # No degrade: the nonexistent coord candidate is returned as-is.
        assert result == unmaterialized_coord
        assert not result.exists()
