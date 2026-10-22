"""Test-only seeding of ``status.events.jsonl`` through the atomic store primitive.

Production writes the status log only through the status FSM
(``emit_status_transition`` / ``BookkeepingTransaction``), which persists
through ``status.store``'s atomic primitives. Tests that need a pre-seeded
log use this helper so fixtures take the same write path. Rows are
serialized by ``store.serialize_event_line``.

The atomic path replaces the file (new inode, mode 0600), adds a trailing
newline to an existing log that lacks one, reads and writes in text mode (so
line endings follow the platform's newline translation) and refuses a symlinked log with ``StoreError``.
Do not seed into a log whose raw bytes the test asserts on.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from specify_cli.status import store
from specify_cli.status.models import StatusEvent

__all__ = ["seed_status_event", "seed_status_events"]


def seed_status_events(feature_dir: Path, events: Iterable[StatusEvent]) -> None:
    """Append *events* to ``feature_dir``'s status log as one atomic write."""
    store.append_events_atomic(feature_dir, list(events))


def seed_status_event(feature_dir: Path, event: StatusEvent) -> None:
    """Append one *event* to ``feature_dir``'s status log atomically."""
    seed_status_events(feature_dir, [event])
