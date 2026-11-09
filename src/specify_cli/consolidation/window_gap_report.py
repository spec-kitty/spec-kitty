"""The window gap report (Mission consolidation-window-provenance-01M6Y84D, WP20, FR-010, FR-011).

A work package whose window-open SHA is not usable (a :class:`~specify_cli.consolidation.wp_attribution.WindowGap`)
is still judged, by its approval-stamp bound: a weaker check. The claim names every such work package
(``ApprovedWpCommitSet.window_gaps``, a sorted tuple of :class:`~specify_cli.consolidation.wp_attribution.GapEntry`),
and the fresh run, the resume and the forecast make it visible through this one renderer: the human
block (:func:`gap_report_lines`), printed by the one printer :func:`print_gap_report` on the
console the caller passes, and the dry-run payload value (:func:`gap_report_json`, under
:data:`WINDOW_GAPS_KEY`). No git and no file I/O; the only output is the caller's console.
"""

from __future__ import annotations

from collections.abc import Sequence

from rich.console import Console
from rich.markup import escape

from .wp_attribution import GapEntry, WindowGapReason

_GAP_REPORT_HEADING = "Window gaps (judged by the approval-stamp bound)"
WINDOW_GAPS_KEY = "window_gaps"

_CAPTURE_FAILED = WindowGapReason.CAPTURE_FAILED.report_text


def _shows_cause(entry: GapEntry) -> bool:
    """A cause is part of a ``capture failed`` gap only (contract R-5); any other reason never shows one."""
    return entry.cause is not None and entry.reason == _CAPTURE_FAILED


_SHORT_SHA = 7
_MALFORMED_NOTE = " (malformed wp_window value ignored)"


def _line(entry: GapEntry) -> str:
    text = f"  - {entry.wp_id} ({entry.lane_id}): {entry.reason}"
    if entry.malformed:
        text += _MALFORMED_NOTE
    if _shows_cause(entry):
        text += f" ({entry.cause})"
    if entry.sha:
        text += f": recorded {entry.sha[:_SHORT_SHA]}"
    if entry.detail:
        text += f": {entry.detail}"
    return text


def gap_report_lines(entries: Sequence[GapEntry]) -> list[str]:
    """The heading, then one line per entry in the given order; ``[]`` when there is no entry."""
    if not entries:
        return []
    return [_GAP_REPORT_HEADING, *(_line(entry) for entry in entries)]


def print_gap_report(console: Console, entries: Sequence[GapEntry]) -> None:
    """Print the gap report on *console*: the heading in yellow, then each entry verbatim; nothing when *entries* is empty.

    The fresh run, the resume and the human forecast all print through this one call (FR-010).
    """
    lines = gap_report_lines(entries)
    if not lines:
        return
    console.print(f"[yellow]{escape(lines[0])}[/yellow]", soft_wrap=True)
    for line in lines[1:]:
        console.print(line, markup=False, soft_wrap=True)


def gap_report_json(entries: Sequence[GapEntry]) -> list[dict[str, str | bool]]:
    """One ``{wp_id, lane_id, reason, cause?, detail?, sha?, malformed?}`` per entry.

    ``cause`` and ``sha`` only when set, ``detail`` only when non-empty, ``malformed`` (``true``)
    only on a gap whose recorded value violated the contract.
    """
    rendered: list[dict[str, str | bool]] = []
    for entry in entries:
        item: dict[str, str | bool] = {"wp_id": entry.wp_id, "lane_id": entry.lane_id, "reason": entry.reason}
        if entry.cause is not None:
            item["cause"] = entry.cause
        if entry.detail:
            item["detail"] = entry.detail
        if entry.sha:
            item["sha"] = entry.sha
        if entry.malformed:
            item["malformed"] = True
        rendered.append(item)
    return rendered


__all__ = [
    "WINDOW_GAPS_KEY",
    "gap_report_json",
    "gap_report_lines",
    "print_gap_report",
]
