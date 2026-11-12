"""Provisional emit_event interface for mission event logging.

This is a Phase 1B provisional interface. Phase 2 will replace the JSONL
backend with a proper event store. Events are written to
``<feature_dir>/mission-events.jsonl``, one JSON object per line.

Key design constraints:
- emit_event failures log a warning but NEVER raise or block.
- Single-process CLI -- no file locking needed, use append mode.
- Keep interface minimal; do not add features Phase 2 won't need.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path, PurePosixPath

from kernel.event_log_append import append_event_log_lines
from kernel.clock import now_utc_iso
from kernel.paths import to_posix

logger = logging.getLogger(__name__)

MISSION_EVENTS_FILE = "mission-events.jsonl"


def is_mission_event_log_path(path: str | Path) -> bool:
    """True for a Mission's own event log, ``kitty-specs/<mission>/mission-events.jsonl`` (depth-exact).

    The one structural recognition of this file. It is tool-written and
    append-only, never authored by an implementer. It is deliberately NOT an
    artifact kind and NOT residue for the dirty gates: it has live readers, so
    an uncommitted copy stays real dirt (#5669). Callers that use this predicate
    decide something narrower; for example, the lane guard tolerates the copy a
    lane inherits from its coordination branch, where ``next`` commits it (#5938).
    A file of the same name anywhere else (``src/app/mission-events.jsonl``,
    ``kitty-specs/<m>/research/mission-events.jsonl``) does not match.
    """
    parts = PurePosixPath(to_posix(path)).parts
    return len(parts) == 3 and parts[0] == "kitty-specs" and parts[2] == MISSION_EVENTS_FILE


def commit_mission_event_log(repo_root: Path, mission_slug: str, log_path: Path, surface_root: Path) -> str | None:
    """Commit a Mission's event log where it was appended, staging that one file only (#5938).

    ``spec-kitty next`` (and ``orchestrator-api answer-decision``, which mirrors
    it) append a ``MissionNextInvoked`` row to the coordination worktree's copy
    of the log; nothing else ever committed it, so ``consolidate`` refused to tear
    the worktree down (``MERGE_UNSAFE_WORKTREE_DIRTY``). The #5669 ruling keeps
    the log real dirt for every gate, so the writer commits it instead of any
    gate exempting it. Only ``log_path`` is staged, so an operator's own edit in
    that checkout stays uncommitted (#5905). The target comes from the placement
    seam for the log's kind (``STATUS_STATE``), the same shape as the status
    door's coordination commit.

    Best-effort, like the row itself: an already-committed row is a no-op, and a
    refused or failed commit is returned as a one-line warning for the caller
    to surface, never raised.
    """
    import subprocess

    from mission_runtime import MissionArtifactKind, resolve_placement_only
    from specify_cli.core.commit_guard import GuardCapability
    from specify_cli.git.commit_helpers import SafeCommitEmptyChangeset, SafeCommitStagedTreeUnchanged, safe_commit

    try:
        safe_commit(
            repo_root=repo_root,
            worktree_root=surface_root,
            target=resolve_placement_only(repo_root, mission_slug, kind=MissionArtifactKind.STATUS_STATE),
            message=f"chore(next): record next invocation for {mission_slug}",
            paths=(log_path,),
            capability=GuardCapability.STANDARD,
        )
    except (SafeCommitEmptyChangeset, SafeCommitStagedTreeUnchanged):
        return None
    except (RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        return f"could not commit {log_path} ({type(exc).__name__}: {exc}); commit it before consolidate."
    return None


def emit_event(
    event_type: str,
    payload: dict,
    mission_name: str = "",
    feature_dir: Path | None = None,
) -> None:
    """Emit a mission event to the local JSONL log.

    This is a provisional interface for Phase 1B. Phase 2 will replace
    the backend with a proper event store.

    Args:
        event_type: Event type (e.g., "phase_entered", "guard_failed").
        payload: Event-specific data.
        mission_name: Name of the mission.
        feature_dir: Feature directory for the JSONL file location.
            If ``None``, the event is not persisted (debug-logged only).
    """
    event = {
        "type": event_type,
        "timestamp": now_utc_iso(),
        "mission": mission_name,
        "payload": payload,
    }

    if feature_dir is None:
        logger.debug("No feature_dir -- event not persisted: %s", event_type)
        return

    try:
        _write_event(feature_dir, event)
    except Exception:
        logger.warning("Failed to emit event: %s", event_type, exc_info=True)


def _write_event(feature_dir: Path, event: dict) -> None:
    """Append event as a JSON line to the mission events log."""
    events_file = feature_dir / MISSION_EVENTS_FILE
    # interim-locked-append: retires at the #6193 handover (kernel.event_log_append).
    append_event_log_lines(events_file, [json.dumps(event, sort_keys=True)])


def _read_events(feature_dir: Path) -> list[dict]:
    """Read all events from the mission events log (test/tooling helper).

    No production caller remains since the legacy DSL readers in
    ``runtime/next/decision.py`` were deleted (mission
    ``dead-port-disposition-01M1TZVN``, WP04); kept underscore-private for the
    event-log tests.

    Returns empty list if the log does not exist.

    Args:
        feature_dir: Feature directory containing the JSONL file.

    Returns:
        List of event dicts parsed from each JSONL line.
    """
    events_file = feature_dir / MISSION_EVENTS_FILE
    if not events_file.exists():
        return []

    events: list[dict] = []
    with open(events_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    logger.warning("Corrupt event line: %s", line[:100])
    return events
