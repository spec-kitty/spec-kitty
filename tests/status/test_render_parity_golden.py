"""SC-004 — event-sourced render parity against a legacy-sourced golden.

Proves "renders from events with no content loss" at the mission level: the
event-sourced render of a WP's ``## Activity Log`` notes, its ``## History``
(lane) rows, and its review-cycle verdict reproduce — byte-equal on the
meaningful content — what a legacy frontmatter/body-sourced render produced.

WP05 re-points the render source (its T019) and WP09 the review render; this is
the mission-level parity guard that those re-points lost nothing.

Two-sided (proof the guard bites): deliberately dropping ONE note / history /
review entry from the event stream turns the golden comparison red.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.status.emit import emit_inner_state_changed
from specify_cli.status.models import (
    Lane,
    ReviewOverride,
    StatusEvent,
    WPInnerStateDelta,
)
from specify_cli.status.reducer import reduce as reduce_snapshot
from specify_cli.status.store import append_event, read_event_stream
from specify_cli.task_utils.support import activity_entries

pytestmark = pytest.mark.integration

_MISSION_SLUG = "001-render-parity"
_WP_ID = "WP01"
_AGENT = "claude"


def _flag_on_feature_dir(tmp_path: Path) -> Path:
    fd = tmp_path / "kitty-specs" / _MISSION_SLUG
    fd.mkdir(parents=True)
    (fd / "meta.json").write_text('{"status_phase": 1}', encoding="utf-8")
    return fd


# The logical content, authored ONCE. Each history row is a lane transition
# (rendered note == its ``reason``); each activity row is a note annotation.
# Timestamps end in ``Z`` so the legacy body parser (which requires a
# ``...Z`` timestamp) can reproduce them from an authored golden body.
_HISTORY_ROWS = [
    ("2026-01-01T00:00:01Z", Lane.PLANNED, Lane.CLAIMED, "claim: picked up"),
    ("2026-01-01T00:00:02Z", Lane.CLAIMED, Lane.IN_PROGRESS, "started the work"),
    ("2026-01-01T00:00:03Z", Lane.IN_PROGRESS, Lane.FOR_REVIEW, "ready for review"),
]
_ACTIVITY_NOTES = [
    ("2026-01-01T00:00:04Z", "first activity note"),
    ("2026-01-01T00:00:05Z", "second activity note"),
]
_REVIEW = ("2026-01-01T00:00:06Z", "approved: looks good")


def _seed_history(feature_dir: Path, *, skip_note: str | None = None) -> None:
    """Seed the transitions (history) + note annotations (activity). When
    *skip_note* is given, that one activity note is dropped from the stream
    (the two-sided mutation)."""
    for idx, (at, frm, to, reason) in enumerate(_HISTORY_ROWS, start=1):
        append_event(
            feature_dir,
            StatusEvent(
                event_id=f"h{idx}",
                mission_slug=_MISSION_SLUG,
                wp_id=_WP_ID,
                from_lane=frm,
                to_lane=to,
                at=at,
                actor=_AGENT,
                force=True,
                execution_mode="worktree",
                reason=reason,
            ),
        )
    for at, text in _ACTIVITY_NOTES:
        if text == skip_note:
            continue
        emit_inner_state_changed(
            feature_dir,
            _WP_ID,
            WPInnerStateDelta(note=text),
            actor=_AGENT,
            mission_slug=_MISSION_SLUG,
            at=at,
        )


def _seed_review(feature_dir: Path) -> None:
    at, reason = _REVIEW
    emit_inner_state_changed(
        feature_dir,
        _WP_ID,
        WPInnerStateDelta(
            review=ReviewOverride(at=at, actor="reviewer-renata", wp_id=_WP_ID, reason=reason)
        ),
        actor="reviewer-renata",
        mission_slug=_MISSION_SLUG,
        at=at,
    )


def _serialize_activity(entries: list[dict[str, str]]) -> list[str]:
    """Canonical serialization of the MEANINGFUL content (timestamp, agent,
    note) of each rendered activity/history row — lane/shell_pid are volatile
    render-shape fields, not meaningful content, so they are excluded."""
    return sorted(f"{e['timestamp']}|{e['agent']}|{e['note']}" for e in entries)


def _legacy_golden_body(*, skip_note: str | None = None) -> str:
    """Author the legacy-sourced golden ``## Activity Log`` body: exactly the
    same logical rows, formatted as the pre-eviction body-render produced them.
    """
    lines = ["# WP01", "", "## Activity Log", ""]
    for at, _frm, to, reason in _HISTORY_ROWS:
        lines.append(f"- {at} – {_AGENT} – lane={to} – {reason}")
    for at, text in _ACTIVITY_NOTES:
        if text == skip_note:
            continue
        # A note row is authored with the WP's working lane so the legacy parser
        # (which requires a ``lane=``) reproduces it; lane is not meaningful
        # content and is excluded from the parity comparison.
        lines.append(f"- {at} – {_AGENT} – lane=in_progress – {text}")
    return "\n".join(lines) + "\n"


def _review_render(feature_dir: Path) -> dict[str, str] | None:
    """Event-sourced review render: the reduced snapshot's ``review`` slot."""
    stream = read_event_stream(feature_dir)
    snapshot = reduce_snapshot(stream.transitions, stream.annotations)
    wp_state = snapshot.work_packages.get(_WP_ID) or {}
    review = wp_state.get("review")
    return dict(review) if review else None


# ===========================================================================
# Activity + History parity
# ===========================================================================


def test_activity_and_history_render_matches_legacy_golden(tmp_path: Path) -> None:
    feature_dir = _flag_on_feature_dir(tmp_path)
    _seed_history(feature_dir)

    # Event-sourced render (empty body -> snapshot fold only, flag ON).
    event_rows = _serialize_activity(
        activity_entries("", feature_dir=feature_dir, wp_id=_WP_ID)
    )
    # Legacy-sourced golden (body-parsed, no feature_dir -> pure legacy path).
    golden_rows = _serialize_activity(activity_entries(_legacy_golden_body()))

    assert event_rows, "event-sourced render produced no rows (drive never fired)"
    assert event_rows == golden_rows, (
        "event-sourced activity/history render diverged from the legacy golden:\n"
        f"  event : {event_rows}\n  golden: {golden_rows}"
    )


def test_dropped_activity_note_turns_parity_red(tmp_path: Path) -> None:
    """Two-sided: an event stream MISSING one note no longer matches the full
    golden — the parity guard bites on real content loss."""
    feature_dir = _flag_on_feature_dir(tmp_path)
    _seed_history(feature_dir, skip_note="second activity note")

    event_rows = _serialize_activity(
        activity_entries("", feature_dir=feature_dir, wp_id=_WP_ID)
    )
    full_golden = _serialize_activity(activity_entries(_legacy_golden_body()))

    assert event_rows != full_golden, (
        "dropping a note from the event stream did NOT change the render — the "
        "parity guard is vacuous"
    )
    # And it matches exactly the golden with the SAME note dropped (precise loss).
    partial_golden = _serialize_activity(
        activity_entries(_legacy_golden_body(skip_note="second activity note"))
    )
    assert event_rows == partial_golden


# ===========================================================================
# Review parity
# ===========================================================================


def test_review_render_matches_legacy_golden(tmp_path: Path) -> None:
    feature_dir = _flag_on_feature_dir(tmp_path)
    _seed_history(feature_dir)
    _seed_review(feature_dir)

    at, reason = _REVIEW
    golden = ReviewOverride(at=at, actor="reviewer-renata", wp_id=_WP_ID, reason=reason).to_dict()

    rendered = _review_render(feature_dir)
    assert rendered is not None, "event-sourced review render is empty (review never emitted)"
    assert rendered == golden, (
        f"event-sourced review render diverged from the legacy golden:\n"
        f"  event : {rendered}\n  golden: {golden}"
    )


def test_dropped_review_turns_parity_red(tmp_path: Path) -> None:
    """Two-sided: with no review event the review render is empty and cannot
    reproduce the golden verdict — content loss is caught."""
    feature_dir = _flag_on_feature_dir(tmp_path)
    _seed_history(feature_dir)  # history only, review event deliberately omitted

    at, reason = _REVIEW
    golden = ReviewOverride(at=at, actor="reviewer-renata", wp_id=_WP_ID, reason=reason).to_dict()

    rendered = _review_render(feature_dir)
    assert rendered != golden, (
        "review render matched the golden with NO review event seeded — the guard "
        "is vacuous"
    )
