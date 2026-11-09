"""The window gap report renderer (Mission consolidation-window-provenance-01M6Y84D, WP20, FR-010).

Pure unit tests: no git, no I/O. :func:`gap_report_lines` is what the fresh run, the resume and
the human forecast print; :func:`gap_report_json` is the ``window_gaps`` value of the dry-run payload.
"""

from __future__ import annotations

import pytest

from specify_cli.consolidation.window_gap_report import GAP_REPORT_HEADING, WINDOW_GAPS_KEY, gap_report_json, gap_report_lines
from specify_cli.consolidation.wp_attribution import GapEntry, WindowGap, WindowGapReason

pytestmark = [pytest.mark.unit]


def _entry(wp_id: str, lane_id: str, reason: WindowGapReason, *, cause: str | None = None, detail: str = "") -> GapEntry:
    return GapEntry.from_gap(wp_id, lane_id, WindowGap(reason, cause=cause, detail=detail))


def test_no_entries_renders_nothing() -> None:
    assert gap_report_lines(()) == []
    assert gap_report_json(()) == []


def test_heading_then_one_line_per_entry_in_order() -> None:
    entries = (
        _entry("WP02", "lane-a", WindowGapReason.NOT_RECORDED),
        _entry("WP03", "lane-b", WindowGapReason.CAPTURE_FAILED, cause="git_error", detail="boom"),
        _entry("WP04", "lane-a", WindowGapReason.NOT_ON_LANE, detail="abc1234"),
    )

    assert gap_report_lines(entries) == [
        "Window gaps (judged by the approval-stamp bound)",
        "  - WP02 (lane-a): not recorded",
        "  - WP03 (lane-b): capture failed (git_error): boom",
        "  - WP04 (lane-a): not on lane: abc1234",
    ]
    assert GAP_REPORT_HEADING == "Window gaps (judged by the approval-stamp bound)"
    assert WINDOW_GAPS_KEY == "window_gaps"


def test_cause_shown_only_for_capture_failed() -> None:
    """A cause on any other reason is not the contract's (R-5); it is never shown as one."""
    stray_cause = GapEntry(wp_id="WP05", lane_id="lane-a", reason=WindowGapReason.LANE_BRANCH_MISSING.report_text, cause="git_error", detail="gone")

    assert gap_report_lines((stray_cause,))[1] == "  - WP05 (lane-a): lane branch missing: gone"
    probe_error = _entry("WP06", "lane-a", WindowGapReason.CAPTURE_FAILED, cause="probe_error")

    assert gap_report_lines((probe_error,))[1] == "  - WP06 (lane-a): capture failed (probe_error)"


def test_detail_omitted_when_empty() -> None:
    assert gap_report_lines((_entry("WP02", "lane-a", WindowGapReason.LANE_BRANCH_MISSING),))[1] == "  - WP02 (lane-a): lane branch missing"


def test_json_omits_absent_cause_and_detail() -> None:
    entries = (
        _entry("WP02", "lane-a", WindowGapReason.NOT_RECORDED),
        _entry("WP03", "lane-b", WindowGapReason.CAPTURE_FAILED, cause="git_error", detail="boom"),
        _entry("WP04", "lane-a", WindowGapReason.LANE_BRANCH_MISSING, detail="deleted"),
    )

    assert gap_report_json(entries) == [
        {"wp_id": "WP02", "lane_id": "lane-a", "reason": "not recorded"},
        {"wp_id": "WP03", "lane_id": "lane-b", "reason": "capture failed", "cause": "git_error", "detail": "boom"},
        {"wp_id": "WP04", "lane_id": "lane-a", "reason": "lane branch missing", "detail": "deleted"},
    ]


@pytest.mark.parametrize("reason", list(WindowGapReason), ids=lambda reason: reason.value)
def test_json_reason_strings_are_the_report_texts(reason: WindowGapReason) -> None:
    (rendered,) = gap_report_json((_entry("WP01", "lane-a", reason),))

    assert rendered["reason"] == reason.report_text
    assert "_" not in rendered["reason"]
    assert gap_report_lines((_entry("WP01", "lane-a", reason),))[1].startswith(f"  - WP01 (lane-a): {reason.report_text}")
