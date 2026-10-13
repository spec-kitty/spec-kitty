"""Shared ``status.json`` refresh-if-present helper for the migration backfills.

One authority for "re-materialize an existing snapshot after a backfill
appended events" (spec-kitty#5862 runtime-state backfill, spec-kitty#5869
verdict-provenance backfill). It never creates a snapshot where none existed,
and it reports a failure instead of raising: the caller's append is already
committed by the time this runs.

Imports ``materialize`` through the :mod:`specify_cli.status` facade only.
"""

from __future__ import annotations

from pathlib import Path

from specify_cli.core.paths import MissionMetaReadError
from specify_cli.status import StoreError, materialize

#: Per-mission read failures a backfill reports instead of raising: an unreadable
#: event log, an I/O fault, or a ``meta.json`` that exists but is corrupt
#: (fail-closed read).
MISSION_STATUS_ERRORS = (StoreError, OSError, MissionMetaReadError)


def refresh_snapshot_if_present(feature_dir: Path) -> tuple[bool, str | None]:
    """Regenerate ``status.json`` iff it already exists; return ``(refreshed, error)``."""
    if not (feature_dir / "status.json").is_file():
        return False, None
    try:
        materialize(feature_dir)
    except MISSION_STATUS_ERRORS as exc:
        return False, f"status.json refresh failed after seeding: {type(exc).__name__}: {exc}"
    return True, None
