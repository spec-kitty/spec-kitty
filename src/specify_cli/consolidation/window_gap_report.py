"""The window gap report (Mission consolidation-window-provenance-01M6Y84D, WP20, FR-010, FR-011).

A work package whose window-open SHA is not usable (a :class:`~specify_cli.consolidation.wp_attribution.WindowGap`)
is still judged, by its approval-stamp bound: a weaker check. The claim names every such work package
(``ApprovedWpCommitSet.window_gaps``, a sorted tuple of :class:`~specify_cli.consolidation.wp_attribution.GapEntry`),
and the fresh run, the resume and the forecast make it visible through this one renderer: the human
block (:func:`gap_report_lines`) and the dry-run payload value (:func:`gap_report_json`, under
:data:`WINDOW_GAPS_KEY`). Pure: no git, no I/O, no console; the callers print.
"""

from __future__ import annotations

from collections.abc import Sequence

from .wp_attribution import GapEntry, WindowGapReason

GAP_REPORT_HEADING = "Window gaps (judged by the approval-stamp bound)"
WINDOW_GAPS_KEY = "window_gaps"

_CAPTURE_FAILED = WindowGapReason.CAPTURE_FAILED.report_text


def _shows_cause(entry: GapEntry) -> bool:
    """A cause is part of a ``capture failed`` gap only (contract R-5); any other reason never shows one."""
    return entry.cause is not None and entry.reason == _CAPTURE_FAILED


def _line(entry: GapEntry) -> str:
    text = f"  - {entry.wp_id} ({entry.lane_id}): {entry.reason}"
    if _shows_cause(entry):
        text += f" ({entry.cause})"
    if entry.detail:
        text += f": {entry.detail}"
    return text


def gap_report_lines(entries: Sequence[GapEntry]) -> list[str]:
    """The heading, then one line per entry in the given order; ``[]`` when there is no entry."""
    if not entries:
        return []
    return [GAP_REPORT_HEADING, *(_line(entry) for entry in entries)]


def gap_report_json(entries: Sequence[GapEntry]) -> list[dict[str, str]]:
    """One ``{wp_id, lane_id, reason, cause?, detail?}`` per entry: ``cause`` only when set, ``detail`` only when non-empty."""
    rendered: list[dict[str, str]] = []
    for entry in entries:
        item = {"wp_id": entry.wp_id, "lane_id": entry.lane_id, "reason": entry.reason}
        if entry.cause is not None:
            item["cause"] = entry.cause
        if entry.detail:
            item["detail"] = entry.detail
        rendered.append(item)
    return rendered


__all__ = [
    "WINDOW_GAPS_KEY",
    "gap_report_json",
    "gap_report_lines",
]
