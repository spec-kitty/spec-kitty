"""The labeled repository-watcher fallback (spec-kitty#4268).

The issue's rule, verbatim: "A repository watcher is a labeled fallback for
changed-file observation only; it cannot attribute edits to a particular
agent or claim file reads. Unknown actors/bindings remain visible as
unknown." This module is exactly that and nothing more:

* one-shot ``git status``/``git diff --numstat`` observation of the
  working tree's uncommitted changes — operations (edit/create/delete/
  rename) and byte deltas, metadata only, never content;
* every observation carries ``attribution='sampled'``, an
  :class:`~live_work.models.UnknownActor`, and a provenance limitation
  naming what this fallback cannot see (the editing agent, file reads);
* no baseline state, no polling loop, no daemon — a snapshot of "changed
  vs HEAD" at invocation time, published through the same one-off
  :func:`live_work.publisher.publish_observations` path.

Renames are the one operation the watcher sees that harness hooks do not
(``git status`` reports ``R`` with old and new paths) — the capability
matrix's delete/rename rows point here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final
from uuid import uuid4

from kernel.clock import now_utc
from kernel.git import GitCommandError, numstat_entries, status_entries

from .bindings import resolve_bindings
from .kinds import WorkEmissionKind
from .models import (
    ActivityBinding,
    FileDetail,
    FileOperation,
    Observation,
    Provenance,
    SessionBinding,
    UnknownActor,
)
from .redaction import relativize_path

__all__ = ["MAX_WATCHED_PATHS", "watch_changed_files"]


MAX_WATCHED_PATHS: Final[int] = 50
"""Bounded per invocation: the first N changed paths publish, the rest drop."""

_GIT_BUDGET_S: Final[float] = 3.0

_WATCHER_SESSION_PREFIX: Final[str] = "live-work-watcher"

_WATCHER_LIMITATION: Final[str] = (
    "changed-file observation only: cannot attribute edits to a particular "
    "agent and cannot observe file reads; displayed as sampled, linkable "
    "later with provenance"
)


def watch_changed_files(repo_root: Path) -> list[Observation]:
    """Observe the working tree's uncommitted changes as sampled frames.

    Returns observations for the bounded set of changed paths; an empty
    list when nothing changed, git is unavailable, or the path is not a
    repository. Never raises — a watcher failure is a capture gap, not an
    error for the caller.
    """
    changes = _collect_changes(repo_root)
    if not changes:
        return []
    bindings = resolve_bindings(repo_root)
    if bindings.repository is None:
        return []
    occurred_at = now_utc().isoformat()
    session_id = f"{_WATCHER_SESSION_PREFIX}-{occurred_at.replace(':', '').replace('-', '')[:20]}"
    observations: list[Observation] = []
    for operation, path, destination, added, removed in changes[:MAX_WATCHED_PATHS]:
        relative = relativize_path(path, repo_root)
        if relative.excluded:
            continue
        relative_dest: str | None = None
        if destination is not None:
            dest_result = relativize_path(destination, repo_root)
            if dest_result.excluded:
                # A rename into excluded material is itself excluded — the
                # destination's existence is never confirmed on the wire.
                continue
            relative_dest = dest_result.value
        observations.append(
            Observation(
                kind=WorkEmissionKind.FILE_EDITED,
                session=SessionBinding(session_id=session_id),
                actor=UnknownActor(),
                repository=bindings.repository,
                mission=bindings.mission,
                activity=ActivityBinding(activity_id=uuid4().hex),
                action=FileDetail(
                    operation=operation,
                    path=relative.value or "",
                    destination_path=relative_dest,
                    bytes_added=added,
                    bytes_removed=removed,
                    attribution="sampled",
                ),
                provenance=Provenance(
                    source="cli_wrapper",
                    capability="live-work.watcher.fallback",
                    limitation=_WATCHER_LIMITATION,
                ),
                occurred_at=occurred_at,
            )
        )
    return observations


def _collect_changes(repo_root: Path) -> list[tuple[FileOperation, str, str | None, int, int]]:
    """(operation, path, destination, added, removed) per changed path.

    Operations come from ``git status --porcelain``; byte deltas from
    ``git diff --numstat`` where the path is tracked. Untracked files
    report no deltas (their content length is not diff metadata).
    """
    try:
        entries = status_entries(repo_root, untracked=None, optional_locks=False, timeout=_GIT_BUDGET_S)
    except GitCommandError:
        # Advisory observation: a failed probe publishes nothing rather than guessing.
        return []
    try:
        deltas = {str(stat.path): (stat.added or 0, stat.deleted or 0) for stat in numstat_entries(repo_root, "HEAD", timeout=_GIT_BUDGET_S)}
    except GitCommandError:
        # Advisory: byte deltas are optional metadata (for example no HEAD yet).
        deltas = {}

    changes: list[tuple[FileOperation, str, str | None, int, int]] = []
    for entry in entries[: MAX_WATCHED_PATHS * 2]:
        operation, is_rename = _operation_from_code(entry.xy)
        # A rename entry names the destination (``entry.path``) and carries the
        # origin (``entry.orig_path``); the observation's ``path`` is the origin.
        path, destination = str(entry.path), None
        if is_rename and entry.orig_path is not None:
            destination = path
            path = str(entry.orig_path)
        elif is_rename:
            operation = FileOperation.EDIT
        # A rename observation carries no byte deltas (the origin path is gone
        # from the diff); every other operation looks its path up.
        added, removed = (0, 0) if destination is not None else deltas.get(path, (0, 0))
        changes.append((operation, path, destination, added, removed))
    return changes


def _operation_from_code(code: str) -> tuple[FileOperation, bool]:
    """Map a porcelain XY status code to (operation, is_rename)."""
    worktree = code[1] if len(code) > 1 else " "
    staged = code[0]
    combined = staged + worktree
    if "R" in combined:
        return FileOperation.RENAME, True
    if "D" in combined:
        return FileOperation.DELETE, False
    if "A" in combined or "?" in combined:
        return FileOperation.CREATE, False
    return FileOperation.EDIT, False
