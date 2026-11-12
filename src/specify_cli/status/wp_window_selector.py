"""The one FR-021 window-opener selector (contract R-1 to R-5, ADR ``2026-11-08-2``).

:func:`window_opener_events` picks the status events that may open a work package's
window, and :func:`window_open_of` binds them to a :class:`WindowOpen` or a typed
:class:`WindowGap`. Mission ``review-context-wp-diff-01M774QF`` moved this block verbatim
from ``consolidation/wp_attribution.py`` so that ``runtime`` and ``review`` share the one
definition with consolidation; ``wp_attribution`` re-exports every name.

Pure: no git and no I/O. The caller passes the events in log order plus predicates bound
to the lane tip it resolved. It sits beside the ``wp_window`` codec rather than inside it,
because that codec imports nothing from ``specify_cli`` and this module needs
:class:`~specify_cli.status.models.StatusEvent`. Consumers outside ``specify_cli.status``
import these names through the facade (SR-2).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum

from .models import StatusEvent, is_migration_actor
from .wp_window import WINDOW_OPENING_LANES, WP_WINDOW_KEY, ParsedWpWindow, RecordedGapReason, parse_wp_window

__all__ = [
    "OpenerSelection",
    "WindowGap",
    "WindowGapReason",
    "WindowOpen",
    "is_migration_event",
    "window_open_of",
    "window_opener_events",
]

# A move into ``claimed`` / ``in_progress`` enters implementation; ``blocked`` never opens a
# window (R-1(b)). Derived from the codec's constant, so it is not a second definition.
_ENTERED_IMPLEMENTATION_LANES: frozenset[str] = WINDOW_OPENING_LANES


def is_migration_event(event: StatusEvent) -> bool:
    """True for a migration-synthesized event (:func:`specify_cli.status.is_migration_actor`, FR-011)."""
    return bool(is_migration_actor(event.actor))


# --------------------------------------------------------------------------- #
# Window opener reader (Mission consolidation-window-provenance-01M6Y84D, WP08)
# --------------------------------------------------------------------------- #
#
# data-model.md section 3 and contracts/status-event-wp-window.md R-1..R-5 (FR-004,
# FR-021, FR-022). Pure: the caller passes the events in log order and two predicates
# bound to the one lane tip the approved bound resolves; nothing here reads git.

# A move to ``planned`` out of one of these lanes is review rework (a rejection), not a
# rewind, so it does not start a new window cycle (spec Assumption "Returned to planned
# excludes review rejections").
_REWORK_FROM_LANES: frozenset[str] = frozenset({"for_review", "in_review", "approved", "done"})
_PLANNED = "planned"


class WindowGapReason(StrEnum):
    """Why a work package's window-open SHA is not usable (closed set, data-model section 3)."""

    NOT_RECORDED = "not_recorded"
    CAPTURE_FAILED = RecordedGapReason.CAPTURE_FAILED.value
    LANE_BRANCH_MISSING = RecordedGapReason.LANE_BRANCH_MISSING.value
    NOT_ON_LANE = "not_on_lane"

    @property
    def report_text(self) -> str:
        """The gap report's reason string ("not recorded", "capture failed", ...)."""
        return self.value.replace("_", " ")


@dataclass(frozen=True, slots=True)
class WindowOpen:
    """The work package's window opens (exclusively) at ``sha``, a commit on the lane."""

    sha: str


@dataclass(frozen=True, slots=True)
class WindowGap:
    """No usable window-open SHA; the work package is judged by its degraded window.

    ``cause`` and ``detail`` echo a recorded ``capture_failed`` / ``lane_branch_missing``
    gap; ``sha`` names the recorded SHA of a ``not_on_lane`` gap; ``malformed`` flags a
    ``not_recorded`` gap whose opener carried a value violating the contract (R-5).
    """

    reason: WindowGapReason
    cause: str | None = None
    detail: str = ""
    sha: str | None = None
    malformed: bool = False


@dataclass(frozen=True, slots=True)
class OpenerSelection:
    """The events that may open a window, in log order, plus the leading ones skipped.

    ``skipped`` holds the leading ``lane_branch_missing`` candidates dropped by the
    ``cycle=True`` selection (R-1(c)); it is always empty for ``cycle=False``.
    """

    candidates: tuple[StatusEvent, ...]
    skipped: tuple[StatusEvent, ...] = ()

    @property
    def skipped_branch_missing(self) -> int:
        """How many leading ``lane_branch_missing`` candidates were skipped."""
        return len(self.skipped)


def _window_value(event: StatusEvent) -> tuple[ParsedWpWindow | None, bool]:
    """The event's parsed ``wp_window`` and whether a present value was malformed (read per event, R-2).

    Parsing goes through the one codec the status writer also uses (``parse_wp_window``).
    """
    metadata = event.policy_metadata
    if not metadata or WP_WINDOW_KEY not in metadata:
        return None, False
    parsed = parse_wp_window(metadata[WP_WINDOW_KEY])
    return parsed, parsed is None


def _branch_missing_detail(event: StatusEvent) -> str | None:
    """The detail of a valid ``lane_branch_missing`` gap on *event*; ``None`` when it records none."""
    parsed, _ = _window_value(event)
    if parsed is None or parsed.gap_reason is not RecordedGapReason.LANE_BRANCH_MISSING:
        return None
    # Annotated local: under ``follow_imports = "skip"`` for ``specify_cli.*`` the facade's
    # ``ParsedWpWindow`` reads as ``Any`` here; the codec declares ``detail: str``.
    detail: str = parsed.detail
    return detail


def _cycle_start_index(wp_events: Sequence[StatusEvent]) -> int:
    """Index just after the last rewind to ``planned`` (R-1(a)); 0 when there is none (genesis)."""
    start = 0
    for index, event in enumerate(wp_events):
        if event.to_lane == _PLANNED and event.from_lane not in _REWORK_FROM_LANES:
            start = index + 1
    return start


def _candidates(wp_events: Sequence[StatusEvent]) -> tuple[StatusEvent, ...]:
    """Moves into ``claimed`` / ``in_progress`` in log order; ``blocked`` is never one (R-1(b))."""
    return tuple(event for event in wp_events if event.to_lane in _ENTERED_IMPLEMENTATION_LANES)


def _skip_leading_branch_missing(candidates: tuple[StatusEvent, ...]) -> OpenerSelection:
    """Drop leading candidates that recorded a valid ``lane_branch_missing`` gap (R-1(c))."""
    index = 0
    while index < len(candidates) and _branch_missing_detail(candidates[index]) is not None:
        index += 1
    return OpenerSelection(candidates=candidates[index:], skipped=candidates[:index])


def window_opener_events(events: Sequence[StatusEvent], wp_id: str, *, cycle: bool) -> OpenerSelection:
    """The one window opener selector (FR-021, contract R-1(a)-(c)).

    *events* must be in event-log order (as ``read_events`` returns them); they are never
    re-sorted by ``at``. Migration events are ignored: they never open a window and never
    start a cycle. ``cycle=True`` keeps only the events after the work package's last move
    to ``planned`` out of a non-review lane (a rewind; a review rejection to ``planned`` is
    rework and keeps the cycle) and skips leading ``lane_branch_missing`` openers.
    ``cycle=False`` is the first-claim rule over the whole history, with no skip.
    """
    wp_events = [event for event in events if event.wp_id == wp_id and not is_migration_event(event)]
    if not cycle:
        return OpenerSelection(candidates=_candidates(wp_events))
    return _skip_leading_branch_missing(_candidates(wp_events[_cycle_start_index(wp_events) :]))


def _topological_first(shas: Sequence[str], is_ancestor: Callable[[str, str], bool]) -> str:
    """The SHA that is an ancestor of (or equal to) every other; the first in log order when none is."""
    for sha in shas:
        if all(is_ancestor(sha, other) for other in shas if other != sha):
            return sha
    return shas[0]


def _bind(
    candidates: tuple[StatusEvent, ...],
    *,
    on_lane: Callable[[str], bool],
    is_ancestor: Callable[[str, str], bool],
) -> WindowOpen | WindowGap:
    """Bind a non-empty candidate tuple to an outcome (contract R-1(d), R-2..R-5).

    *candidates* come from a ``cycle=True`` selection, so no leading ``lane_branch_missing``
    candidate is left: the first one carries an ``open_sha``, a ``capture_failed`` gap, or no usable value.
    """
    first, malformed = _window_value(candidates[0])
    if first is None:
        # An unrecorded opener is never replaced by a later recorded one.
        return WindowGap(WindowGapReason.NOT_RECORDED, malformed=malformed)
    if first.open_sha is None:
        # A leading lane_branch_missing was skipped (cycle=True), so this is a capture_failed gap.
        assert first.gap_reason is RecordedGapReason.CAPTURE_FAILED, "a cycle=True selection never leads with lane_branch_missing"
        return WindowGap(WindowGapReason.CAPTURE_FAILED, cause=first.cause, detail=first.detail)
    shas = [parsed.open_sha for parsed, _ in map(_window_value, candidates) if parsed is not None and parsed.open_sha is not None]
    chosen = _topological_first(shas, is_ancestor)
    if not on_lane(chosen):
        return WindowGap(WindowGapReason.NOT_ON_LANE, sha=chosen)
    return WindowOpen(chosen)


def window_open_of(
    events: Sequence[StatusEvent],
    wp_id: str,
    *,
    on_lane: Callable[[str], bool],
    is_ancestor: Callable[[str, str], bool],
) -> WindowOpen | WindowGap:
    """The window-open SHA of *wp_id*'s current cycle, or the typed gap (data-model section 3).

    *events* are in event-log order. ``on_lane(sha)`` is true iff *sha* resolves in this
    clone and is an ancestor of the one lane tip the approved bound resolved (FR-022);
    ``is_ancestor(a, b)`` is true iff *a* is an ancestor of or equal to *b*. Both are bound
    by the caller to that one tip; a SHA that is not in this clone reads as False, so it is
    ``not_on_lane``, never a probe error (R-4), while a git failure on a SHA that is in the
    clone, raised by a predicate, propagates through this function for the approved bound to refuse on. Among
    the cycle's recorded SHAs the topological first wins, so a rework stamped on a skewed
    clock cannot narrow the window; unrelated SHAs fall back to event-log order. This
    function performs no git read.
    """
    selection = window_opener_events(events, wp_id, cycle=True)
    if selection.candidates:
        return _bind(selection.candidates, on_lane=on_lane, is_ancestor=is_ancestor)
    if selection.skipped:
        return WindowGap(WindowGapReason.LANE_BRANCH_MISSING, detail=_branch_missing_detail(selection.skipped[-1]) or "")
    return WindowGap(WindowGapReason.NOT_RECORDED)
