"""Writer -> reader round trip of ``policy_metadata["wp_window"]`` (pre-PR fold M5).

The status pipeline writes the value and consolidation reads it back, both through the one
codec in ``status/wp_window.py``. Every reading the writer can take (a sha, and a failure of
every ``CaptureCause``) must come back from the reader as the window or gap it records, so the
two ends can never drift apart again.
"""

from __future__ import annotations

from typing import Any

import pytest

from specify_cli.status import (
    WP_WINDOW_KEY,
    Lane,
    RecordedGapReason,
    StatusEvent,
    WindowGap,
    WindowGapReason,
    WindowOpen,
    parse_wp_window,
    window_open_of,
)
from specify_cli.status.lane_head import LaneHeadReading
from specify_cli.status.models import TransitionRequest
from specify_cli.status.transition_pipeline import _wp_window_value
from specify_cli.status.wp_window import GAP_DETAIL_MAX_LENGTH, CaptureCause

pytestmark = [pytest.mark.fast]

_SHA1 = "3f1c0d9e8b7a6f5e4d3c2b1a0f9e8d7c6b5a4f3e"
_SHA256 = "a1" * 32
_LONG_DETAIL = "d" * (GAP_DETAIL_MAX_LENGTH + 400)


def _written(reading: LaneHeadReading) -> dict[str, Any]:
    request = TransitionRequest(mission_slug="m", wp_id="WP01", to_lane="claimed", actor="claude")
    value = _wp_window_value(request, reading, Lane.CLAIMED)
    assert value is not None
    return value


def _read_back(value: dict[str, Any], *, on_lane: bool = True) -> WindowOpen | WindowGap:
    event = StatusEvent(
        event_id="01M6Y84D000000000000000001",
        mission_slug="m",
        wp_id="WP01",
        from_lane=Lane.PLANNED,
        to_lane=Lane.CLAIMED,
        at="2026-11-09T10:00:00+00:00",
        actor="claude",
        force=False,
        execution_mode="worktree",
        policy_metadata={WP_WINDOW_KEY: value},
    )
    return window_open_of([event], "WP01", on_lane=lambda _sha: on_lane, is_ancestor=lambda a, b: a == b)


@pytest.mark.parametrize("sha", [_SHA1, _SHA256])
def test_recorded_sha_round_trips_to_the_window(sha: str) -> None:
    assert _read_back(_written(LaneHeadReading.of_sha(sha))) == WindowOpen(sha)


_EXPECTED_GAP: dict[CaptureCause, tuple[WindowGapReason, str | None]] = {
    CaptureCause.LANE_BRANCH_MISSING: (WindowGapReason.LANE_BRANCH_MISSING, None),
    CaptureCause.GIT_ERROR: (WindowGapReason.CAPTURE_FAILED, "git_error"),
    CaptureCause.PROBE_ERROR: (WindowGapReason.CAPTURE_FAILED, "probe_error"),
}


def test_every_capture_cause_has_an_expected_gap() -> None:
    assert set(_EXPECTED_GAP) == set(CaptureCause)
    assert {reason.value for reason, _ in _EXPECTED_GAP.values()} == {reason.value for reason in RecordedGapReason}


@pytest.mark.parametrize("cause", list(CaptureCause))
@pytest.mark.parametrize("detail", ["", "fatal: bad object", _LONG_DETAIL])
def test_every_capture_cause_round_trips_to_its_gap(cause: CaptureCause, detail: str) -> None:
    written = _written(LaneHeadReading.failed(cause, detail))
    reason, expected_cause = _EXPECTED_GAP[cause]

    assert parse_wp_window(written) is not None, written
    assert _read_back(written) == WindowGap(reason, cause=expected_cause, detail=detail[:GAP_DETAIL_MAX_LENGTH])


def test_recorded_sha_off_the_lane_reads_as_not_on_lane() -> None:
    assert _read_back(_written(LaneHeadReading.of_sha(_SHA1)), on_lane=False) == WindowGap(WindowGapReason.NOT_ON_LANE, sha=_SHA1)
