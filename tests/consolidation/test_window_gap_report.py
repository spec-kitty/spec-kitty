"""The window gap report renderer (Mission consolidation-window-provenance-01M6Y84D, WP20, FR-010).

Pure unit tests: no git, no I/O. :func:`gap_report_lines` is what the fresh run, the resume and
the human forecast print; :func:`gap_report_json` is the ``window_gaps`` value of the dry-run payload.
"""

from __future__ import annotations

import subprocess
import sys

import pytest
from rich.console import Console

from specify_cli.consolidation.window_gap_report import WINDOW_GAPS_KEY, gap_report_json, gap_report_lines, print_gap_report
from specify_cli.consolidation.wp_attribution import GapEntry
from specify_cli.status import WindowGap, WindowGapReason

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


_OFF_LANE_SHA = "3f1c0d9e8b7a6f5e4d3c2b1a0f9e8d7c6b5a4f3e"


def test_not_on_lane_gap_names_its_recorded_sha() -> None:
    """M4: the recorded SHA a ``not on lane`` gap could not find on the lane is part of the report."""
    entry = GapEntry.from_gap("WP04", "lane-a", WindowGap(WindowGapReason.NOT_ON_LANE, sha=_OFF_LANE_SHA))

    assert entry.sha == _OFF_LANE_SHA
    assert gap_report_lines((entry,))[1] == "  - WP04 (lane-a): not on lane: recorded 3f1c0d9"
    assert gap_report_json((entry,)) == [{"wp_id": "WP04", "lane_id": "lane-a", "reason": "not on lane", "sha": _OFF_LANE_SHA}]


def test_malformed_not_recorded_gap_carries_the_malformed_note() -> None:
    """M4 / data-model section 3: a value that violates the contract reads as not recorded, with a note."""
    entry = GapEntry.from_gap("WP02", "lane-a", WindowGap(WindowGapReason.NOT_RECORDED, malformed=True))

    assert entry.malformed is True
    assert gap_report_lines((entry,))[1] == "  - WP02 (lane-a): not recorded (malformed wp_window value ignored)"
    assert gap_report_json((entry,)) == [{"wp_id": "WP02", "lane_id": "lane-a", "reason": "not recorded", "malformed": True}]


def test_print_gap_report_prints_every_line_and_nothing_for_no_entries() -> None:
    """M6: the one printer the fresh run, the resume and the human forecast share."""
    console = Console(record=True, width=200, color_system=None)
    print_gap_report(console, ())
    assert console.export_text() == ""

    entries = (_entry("WP02", "lane-a", WindowGapReason.CAPTURE_FAILED, cause="git_error", detail="[bold]not markup[/bold]"),)
    print_gap_report(console, entries)

    assert console.export_text().splitlines() == gap_report_lines(entries)


def test_forecast_does_not_load_the_claim_phase() -> None:
    """M6: the dry-run forecast prints the gap report without importing the branch-moving phase modules."""
    probe = "import sys, specify_cli.consolidation.forecast; print('specify_cli.consolidation.phase_claim' in sys.modules)"
    result = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "False", result.stdout + result.stderr
