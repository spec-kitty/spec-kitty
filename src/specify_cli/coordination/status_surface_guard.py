"""Refuse a coordination status write that would drop committed events (#5572).

A rolled-back consolidation byte-restores the coordination worktree's
``status.events.jsonl`` / ``status.json`` to their pre-``done`` bytes while the
coordination branch HEAD still carries the committed ``done`` strand. A status
write built on those bytes commits a log that no longer holds the strand: the
event is silently lost. The transactional door calls
:func:`committed_events_missing_from_worktree` before it opens a coordination
write and refuses, rather than build on a tree that diverges from HEAD this way.
Since #5638 the rollback authority resyncs that checkout to the coordination tip
it leaves in place, so this guard is the backstop for whatever path it misses.

Only *loss* is refused: a worktree log that holds extra, uncommitted lines (an
interrupted write the surgical truncate rollback owns) is not a divergence here.

Fail closed (#5613): a committed log that cannot be read or parsed is refused
(:class:`BookkeepingStatusSurfaceUnreadable`), never reported as "nothing missing".
"""

from __future__ import annotations

import json
from pathlib import Path

from kernel.git import GitCommandError, blob_at
from specify_cli.coordination.event_prefix import DuplicateEventIdError, MalformedEventLogLineError, event_ids_of
from specify_cli.coordination.transaction_errors import BookkeepingStatusSurfaceUnreadable
from specify_cli.status import jsonl_lines

__all__ = ["committed_events_missing_from_worktree"]


def _working_tree_event_ids(raw: bytes) -> set[str]:
    """Event ids present in the working-tree log, read tolerantly: a torn trailing line from an interrupted append is legitimate there."""
    ids: set[str] = set()
    for _, line in jsonl_lines(raw.decode("utf-8", "replace")):
        try:
            event = json.loads(line)
        except (ValueError, RecursionError):
            continue
        if isinstance(event, dict) and "event_id" in event:
            ids.add(str(event["event_id"]))
    return ids


def committed_events_missing_from_worktree(worktree_root: Path, events_path: Path) -> list[str]:
    """Event ids committed at the worktree's HEAD but absent from its working-tree log.

    Empty when the log is absent at HEAD (nothing committed to lose) or the working
    tree still holds every committed event.

    Raises:
        BookkeepingStatusSurfaceUnreadable: HEAD or its committed log could not be read,
            the committed log is malformed or repeats an event id, or the working-tree
            log could not be read. The loss check cannot be answered, so nothing may be written.
    """
    try:
        relative = events_path.relative_to(worktree_root).as_posix()
    except ValueError:
        return []

    def _unreadable(reason: str) -> BookkeepingStatusSurfaceUnreadable:
        return BookkeepingStatusSurfaceUnreadable(worktree_root=worktree_root, events_path=events_path, reason=reason)

    try:
        committed = blob_at(worktree_root, "HEAD", relative)
    except GitCommandError as exc:
        raise _unreadable(f"the log at HEAD could not be read ({exc})") from exc
    if committed is None:
        return []
    try:
        # The single strict parser (``event_prefix``): a committed log is never torn.
        committed_ids = event_ids_of(line for _, line in jsonl_lines(committed.decode("utf-8", "replace")))
    except (MalformedEventLogLineError, DuplicateEventIdError) as exc:
        raise _unreadable(f"the log committed at HEAD is not a valid event log ({exc})") from exc
    try:
        present = _working_tree_event_ids(events_path.read_bytes()) if events_path.exists() else set()
    except OSError as exc:
        raise _unreadable(f"the working-tree log could not be read ({exc})") from exc
    return [event_id for event_id in committed_ids if event_id not in present]
