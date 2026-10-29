"""Test-only probe: does the ``spec_kitty_events`` reducer treat an actor as a reconstruction seed?

Behavioural, through the package's public reducer (``spec_kitty_events.diary.reduce``),
so a rename of the package-private seed predicate cannot let a test pass silently.

The probe log: a forced ``planned -> for_review`` row by *actor*, then a later unforced
live ``planned -> claimed``. The live row does not continue from ``for_review``: a real
decision rejects it (the WP stays ``for_review``), a reconstruction seed yields to it
(the WP ends ``claimed``).
"""

from __future__ import annotations

from typing import Any

from spec_kitty_events.diary import reduce as package_reduce

__all__ = ["reduces_as_reconstruction_seed"]

_LIVE_ACTOR = {"tool": "claude", "role": "implementer", "profile": None, "model": None}


def _row(event_id: str, from_lane: str, to_lane: str, at: str, actor: object, *, force: bool) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "mission_slug": "seed-probe",
        "wp_id": "WP01",
        "from_lane": from_lane,
        "to_lane": to_lane,
        "at": at,
        "actor": actor,
        "force": force,
        "execution_mode": "worktree",
        "evidence": None,
        "reason": None,
        "review_ref": None,
    }


def reduces_as_reconstruction_seed(actor: object) -> bool:
    """True when the package reducer lets a later live transition override *actor*'s row."""
    rows = [
        _row("01SEEDPROBE000000000000001", "planned", "for_review", "2026-01-01T00:00:01+00:00", actor, force=True),
        _row("01SEEDPROBE000000000000002", "planned", "claimed", "2026-01-01T00:00:02+00:00", _LIVE_ACTOR, force=False),
    ]
    lane: str = package_reduce(rows).work_packages["WP01"]["lane"]
    return lane == "claimed"
