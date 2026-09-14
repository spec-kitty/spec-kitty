"""Edit-burst coalescing for Live Work file observations (spec-kitty#4268).

LIVE-WORK.md §3.2's coalescing rule, verbatim: "File operations emit
promptly, coalescing repeated writes in a short editing burst into an update
with count/interval/final revision; meaningful start/completion and
structural operations are preserved." §3.5: coalescing "must not discard
distinct lifecycle/narrative actions."

Emission semantics: the **first** edit of a burst publishes immediately
(the capture-to-paint target is ~1 s — waiting for a window to close would
miss it); repeated edits to the same path within the window are absorbed;
when the burst closes — the next edit to the same path falls outside the
window, or the session ends — one honest update frame goes out carrying the
count, the window interval, and the final cumulative deltas. Structural
operations (create/delete/rename) and test outcomes never enter the
coalescer; every non-file observation passes through untouched.

This is in-memory, window-only state — there is no journal, spool, or
durable offset anywhere (the 2026-09-14 NOW/DONE re-scope), and no
background timer: a still-open burst is closed lazily by the next offer or
by :meth:`BurstCoalescer.flush_all` at session end. A process that dies
mid-burst loses the pending update frame — the accepted-losses posture for
a now-view.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from kernel.clock import now_epoch

from .models import FileDetail, FileOperation, Observation

__all__ = [
    "BURST_WINDOW_S",
    "BurstCoalescer",
    "CoalescedEdit",
    "is_structural",
]


BURST_WINDOW_S: Final[float] = 5.0
"""Short editing-burst window: repeated edits to one path inside it coalesce."""

_STRUCTURAL_OPERATIONS: Final[frozenset[FileOperation]] = frozenset({FileOperation.CREATE, FileOperation.DELETE, FileOperation.RENAME})
"""Structural operations are preserved distinctly — never coalesced (§3.5)."""


def is_structural(detail: FileDetail) -> bool:
    """True when a file detail is structural (create/delete/rename)."""
    return detail.operation in _STRUCTURAL_OPERATIONS


@dataclass(frozen=True)
class CoalescedEdit:
    """The result of offering one observation to the coalescer.

    ``frames`` is what to publish now (empty when the observation was
    absorbed into a still-open burst); ``absorbed`` names that case.
    """

    frames: tuple[Observation, ...]
    absorbed: bool


@dataclass
class _PendingEdit:
    observation: Observation
    opened_at: float
    total_added: int
    total_removed: int
    edits: int = 1


class BurstCoalescer:
    """Coalesce repeated edits to the same path within :data:`BURST_WINDOW_S`.

    One instance per capture process. Only ``action.file_edited`` file
    details with ``operation='edit'`` are coalescible; structural
    operations and every non-file observation pass straight through.
    """

    def __init__(self, window_s: float = BURST_WINDOW_S, *, clock: Callable[[], float] = now_epoch) -> None:
        if window_s < 0:
            msg = "window_s must be non-negative"
            raise ValueError(msg)
        self._window_s = window_s
        self._clock = clock
        self._pending: dict[tuple[str, str], _PendingEdit] = {}

    def offer(self, observation: Observation) -> CoalescedEdit:
        """Offer one observation; get the frames to publish now."""
        if observation.kind.value != "action.file_edited":
            # Non-file observations are structurally distinct — pass through.
            return CoalescedEdit((observation,), absorbed=False)
        detail = observation.action
        if not isinstance(detail, FileDetail) or is_structural(detail):
            return CoalescedEdit((observation,), absorbed=False)

        key = (observation.session.session_id, detail.path)
        now = self._clock()
        pending = self._pending.get(key)
        if pending is not None and (now - pending.opened_at) <= self._window_s:
            # Same burst: absorb, accumulate deltas, keep the final revision.
            pending.total_added += detail.bytes_added
            pending.total_removed += detail.bytes_removed
            pending.edits += 1
            return CoalescedEdit((), absorbed=True)

        # First edit of a burst, or a new burst after the window closed: the
        # incoming observation publishes immediately, and any open burst for
        # this path closes with its honest update frame alongside it.
        frames: list[Observation] = []
        if pending is not None:
            flushed = self._flush(key, now)
            if flushed is not None:
                frames.append(flushed)
        self._pending[key] = _PendingEdit(
            observation=observation,
            opened_at=now,
            total_added=detail.bytes_added,
            total_removed=detail.bytes_removed,
        )
        frames.append(observation)
        return CoalescedEdit(tuple(frames), absorbed=False)

    def flush_all(self) -> list[Observation]:
        """Close every open burst and return their coalesced update frames.

        Called at session end (the ``Stop`` hook) so a burst still open when
        the session ends still produces its honest update.
        """
        frames: list[Observation] = []
        now = self._clock()
        for key in list(self._pending):
            flushed = self._flush(key, now)
            if flushed is not None:
                frames.append(flushed)
        return frames

    def _flush(self, key: tuple[str, str], now: float) -> Observation | None:
        pending = self._pending.pop(key, None)
        if pending is None:
            return None
        if pending.edits <= 1:
            return None
        final = pending.observation.action
        if not isinstance(final, FileDetail):  # pragma: no cover - model enforces
            return None
        coalesced_detail = FileDetail(
            operation=final.operation,
            path=final.path,
            destination_path=None,
            bytes_added=pending.total_added,
            bytes_removed=pending.total_removed,
            coalesced_edits=pending.edits,
            coalesced_window_s=round(now - pending.opened_at, 3),
            attribution=final.attribution,
        )
        return pending.observation.model_copy(update={"action": coalesced_detail})
