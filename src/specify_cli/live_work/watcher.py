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

import subprocess
from pathlib import Path
from typing import Final
from uuid import uuid4

from kernel.clock import now_utc

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
    status = _git(repo_root, "status", "--porcelain=v1", "-z")
    if status is None:
        return []
    numstat = _git(repo_root, "diff", "HEAD", "--numstat", "-z")
    deltas = _parse_numstat(numstat)

    changes: list[tuple[FileOperation, str, str | None, int, int]] = []
    # -z output: NUL-separated entries; a rename entry is
    # "XY <old>\0<new>\0" (two NUL-separated fields after the status).
    fields = [field for field in status.split("\0") if field]
    index = 0
    while index < len(fields) and len(changes) < MAX_WATCHED_PATHS * 2:
        entry = fields[index]
        if len(entry) < 4:
            index += 1
            continue
        code, current_path = entry[:2], entry[3:]
        operation, is_rename = _operation_from_code(code)
        # porcelain -z rename entries are "XY <new>\0<orig>": the entry names
        # the destination, the following NUL field names the origin.
        path, destination = current_path, None
        if is_rename:
            if index + 1 < len(fields):
                destination = current_path
                path = fields[index + 1]
                index += 1
            else:
                operation = FileOperation.EDIT
        added, removed = deltas.get(path, (0, 0))
        changes.append((operation, path, destination, added, removed))
        index += 1
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


def _parse_numstat(raw: str | None) -> dict[str, tuple[int, int]]:
    """Parse ``git diff --numstat -z`` into {path: (added, removed)}."""
    if not raw:
        return {}
    deltas: dict[str, tuple[int, int]] = {}
    fields = [field for field in raw.split("\0") if field]
    index = 0
    while index < len(fields):
        field = fields[index]
        parts = field.split("\t")
        if len(parts) >= 3:
            added = _int_or_zero(parts[0])
            removed = _int_or_zero(parts[1])
            deltas[parts[2]] = (added, removed)
        index += 1
    return deltas


def _int_or_zero(raw: str) -> int:
    try:
        return int(raw)
    except ValueError:
        return 0


def _git(repo_root: Path, *args: str) -> str | None:
    """One bounded git invocation; ``None`` on any failure."""
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=_GIT_BUDGET_S,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout
