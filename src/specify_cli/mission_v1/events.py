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
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from kernel.event_log_append import append_event_log_lines
from kernel.clock import now_utc_iso
from kernel.paths import to_posix

if TYPE_CHECKING:
    from runtime.next.next_invocation_lifecycle import MissionNextInvokedWrite

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
    to surface, never raised. The one exception is a
    :class:`~specify_cli.git.commit_helpers.SafeCommitRecoveryFailed` that names an
    orphan stash: that ref holds the operator's staged changes, so it propagates;
    callers go through :func:`commit_event_row`, which always surfaces it.
    """
    import subprocess

    from mission_runtime import MissionArtifactKind, resolve_placement_only
    from specify_cli.core.commit_guard import GuardCapability
    from specify_cli.git.commit_helpers import (
        SafeCommitEmptyChangeset,
        SafeCommitRecoveryFailed,
        SafeCommitStagedTreeUnchanged,
        safe_commit,
    )

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
    except SafeCommitRecoveryFailed as exc:
        if exc.orphan_stash_ref:
            raise
        return f"could not commit {log_path} ({type(exc).__name__}: {exc}); commit it before consolidate."
    except (RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        return f"could not commit {log_path} ({type(exc).__name__}: {exc}); commit it before consolidate."
    return None


def commit_event_row(
    repo_root: Path,
    mission_slug: str,
    event_row: MissionNextInvokedWrite,
    *,
    warn: Callable[[str], None],
) -> None:
    """Commit the row ``next`` / ``answer-decision`` wrote and hand every message the operator needs to ``warn``.

    A refused commit blocks ``consolidate`` only for the coordination worktree's
    copy, so it is surfaced only there; a refusal in the repository root checkout
    (e.g. a protected target) stays quiet because the claim gate already exempts
    this Mission's log. A failed staging restore is surfaced for every checkout:
    the operator's staged changes sit in an orphan stash that only this message
    names (the shape of ``init``'s recovery note).
    """
    from specify_cli.git.commit_helpers import SafeCommitRecoveryFailed

    try:
        warning = commit_mission_event_log(repo_root, mission_slug, event_row.log_path, event_row.surface_root)
    except SafeCommitRecoveryFailed as exc:
        landed = f"Commit {exc.commit_sha} did land." if exc.commit_sha else "No commit landed."
        stash = (
            f" Your staged changes were stashed at {exc.orphan_stash_ref!r}; restore them with `git stash pop --index {exc.orphan_stash_ref}`."
            if exc.orphan_stash_ref
            else ""
        )
        warn(f"committing {event_row.log_path} could not restore your staging: {exc}. {landed}{stash}")
        return
    if warning is not None and event_row.in_coordination_worktree:
        warn(warning)


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
