"""The Mission write primitive: one lock, one verified rollback (#5819).

A Mission's status files (``status.events.jsonl``, ``status.json``) and the
shared planning files beside them are written by several actors in parallel.
This module is the **only** module in ``src/specify_cli`` that truncates or
unlinks a Mission's ``status.events.jsonl`` (pinned by the Mission write
discipline gate), and the single way a non-status writer takes the lock that
serialises those writes.

* :func:`mission_write_lock` is :func:`~specify_cli.status.locking.feature_status_lock`
  keyed on the Mission directory name, re-entrant per thread.
* :func:`locked_rewrite_text` is a locked read-modify-write whose transform
  never sees a stale read.
* :func:`capture_rollback_point` records the log size and ``status.json`` bytes
  and **refuses unless the calling thread holds the lock**, so a capture made
  outside the hold can never be written back.
* :func:`rollback_events_log` / :func:`rollback_status_artifacts` cut the rows a
  failed operation appended. They verify before they cut and **never extend**
  the file: the log is opened once, the same descriptor is measured and
  truncated, and a log that is shorter than at capture, vanished, holds a tail
  that is not whole JSON rows, holds rows the caller did not append, or whose
  tail is already committed at ``HEAD`` is left byte-identical and reported as
  :data:`STATUS_ROLLBACK_REFUSED`.

Design: ``kitty-specs/concurrent-mission-writers-01M4BT23/plan.md`` (D1 and
amendments A1-A3).
"""

from __future__ import annotations

import json
import logging
import os
from collections import Counter
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import BinaryIO

from kernel.atomic import atomic_write
from kernel.git import GitCommandError, blob_at, run_git
from specify_cli.status.locking import (
    BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS,
    feature_status_lock,
    feature_status_lock_path,
    holds_status_lock,
)
from specify_cli.status.reducer import SNAPSHOT_FILENAME as _STATUS_FILENAME
from specify_cli.status.store import EVENTS_FILENAME as _EVENTS_FILENAME
from specify_cli.workspace.root_resolver import resolve_status_lock_root

__all__ = [
    "MISSION_WRITE_LOCK_TIMEOUT_SECONDS",
    "STATUS_ROLLBACK_REFUSED",
    "RollbackOutcome",
    "RollbackPoint",
    "RollbackRefusal",
    "append_refusal_to_error",
    "appended_event_ids",
    "capture_rollback_point",
    "locked_rewrite_text",
    "mission_write_lock",
    "rollback_io_failure",
    "rollback_events_log",
    "rollback_status_artifacts",
]

logger = logging.getLogger(__name__)

#: Default bound for a Mission write lock take (reuses the shared 10 s bound; plan A1).
MISSION_WRITE_LOCK_TIMEOUT_SECONDS: float = BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS

#: Error code printed with every refused rollback.
STATUS_ROLLBACK_REFUSED = "STATUS_ROLLBACK_REFUSED"

_EVENT_ID_KEY = "event_id"
_HEAD = "HEAD"
_NOT_A_REPOSITORY = b"not a git repository"


@contextmanager
def mission_write_lock(
    feature_dir: Path,
    *,
    repo_root: Path | None = None,
    timeout: float = MISSION_WRITE_LOCK_TIMEOUT_SECONDS,
) -> Iterator[Path]:
    """Hold the Mission write lock for *feature_dir*; re-entrant per thread.

    The lock is keyed on the Mission directory name (``feature_dir.name``) under
    the git common dir of the canonical repo root, so every writer of the same
    Mission converges on one lock file. A timeout raises
    :class:`~specify_cli.status.locking.FeatureStatusLockTimeoutError`.
    """
    with feature_status_lock(resolve_status_lock_root(feature_dir, repo_root), feature_dir.name, timeout=timeout) as held:
        yield held


def locked_rewrite_text(
    path: Path,
    transform: Callable[[str | None], str],
    *,
    feature_dir: Path,
    repo_root: Path | None = None,
    timeout: float = MISSION_WRITE_LOCK_TIMEOUT_SECONDS,
    encoding: str = "utf-8",
) -> str:
    """Rewrite *path* as ``transform(current_text)`` under the Mission write lock.

    ``current_text`` is ``None`` when the file is missing. The file is replaced
    atomically and only when the text changed. Returns the resulting text.
    """
    with mission_write_lock(feature_dir, repo_root=repo_root, timeout=timeout):
        current = path.read_text(encoding=encoding) if path.exists() else None
        updated = transform(current)
        if updated != current:
            atomic_write(path, updated.encode(encoding))
        return updated


@dataclass(frozen=True)
class RollbackPoint:
    """Pre-operation state of a Mission's status files, captured under the write lock."""

    events_path: Path
    status_path: Path
    pre_event_size: int
    pre_status_bytes: bytes | None
    events_existed: bool

    @classmethod
    def measured_under_held_lock(cls, *, events_path: Path, status_path: Path, pre_event_size: int, events_existed: bool) -> RollbackPoint:
        """A point from measurements the caller already took while holding the Mission write lock.

        For a caller that measured the log before this call (``BookkeepingTransaction``
        measures inside its own lock hold): it does not re-read the files and does not
        check the lock, so the CALLER must hold it, and must also hold it for the
        rollback. ``status.json`` bytes are not captured (``None``): the caller restores
        ``status.json`` from its own snapshot. Prefer :func:`capture_rollback_point`.
        """
        return cls(events_path=events_path, status_path=status_path, pre_event_size=pre_event_size, pre_status_bytes=None, events_existed=events_existed)


def _holds_mission_lock(feature_dir: Path, repo_root: Path | None) -> bool:
    lock_path = feature_status_lock_path(resolve_status_lock_root(feature_dir, repo_root), feature_dir.name)
    return holds_status_lock(lock_path)


def capture_rollback_point(feature_dir: Path, *, repo_root: Path | None = None) -> RollbackPoint:
    """Capture the Mission's log size and ``status.json`` bytes.

    Raises:
        RuntimeError: the calling thread does not hold the Mission write lock for
            *feature_dir*. A capture taken outside the hold could be written back
            over another writer's rows.
    """
    if not _holds_mission_lock(feature_dir, repo_root):
        raise RuntimeError(
            f"capture_rollback_point({feature_dir.name}) requires the Mission write lock; wrap the capture, the write and the rollback in mission_write_lock()"
        )
    events_path = feature_dir / _EVENTS_FILENAME
    status_path = feature_dir / _STATUS_FILENAME
    events_existed = events_path.exists()
    return RollbackPoint(
        events_path=events_path,
        status_path=status_path,
        pre_event_size=events_path.stat().st_size if events_existed else 0,
        pre_status_bytes=status_path.read_bytes() if status_path.exists() else None,
        events_existed=events_existed,
    )


def appended_event_ids(point: RollbackPoint) -> list[str] | None:
    """Event ids of the rows appended after *point*, or ``None`` when the tail is not whole JSON rows.

    Read it while the Mission write lock is held to learn which rows are this
    operation's own, then hand it to the rollback as ``expected_event_ids`` so a
    rollback made later, under a re-acquired lock, still refuses a foreign row.
    """
    try:
        with point.events_path.open("rb") as fh:
            fh.seek(point.pre_event_size)
            return _parse_tail_event_ids(fh.read())
    except FileNotFoundError:
        return []


class RollbackRefusal(StrEnum):
    """Why a rollback left the Mission files untouched."""

    LOG_VANISHED = "the event log existed at capture and is gone"
    LOG_SHRANK = "the event log is shorter than at capture"
    TAIL_UNPARSEABLE = "the rows after the capture point are not whole JSON event rows"
    TAIL_NOT_OWNED = "the rows after the capture point are not the rows this operation appended"
    TAIL_ALREADY_COMMITTED = "the rows after the capture point are already committed at HEAD"
    HEAD_UNREADABLE = "HEAD could not be read to prove the rows are uncommitted"
    IO_ERROR = "the rollback hit an I/O error before it could finish"


@dataclass(frozen=True)
class RollbackOutcome:
    """Result of a rollback attempt; a refusal left every file byte-identical."""

    rolled_back: bool
    refusal: RollbackRefusal | None
    events_path: Path

    def message(self) -> str:
        """Operator text for a refusal (empty when the rollback succeeded)."""
        if self.refusal is None:
            return ""
        state = "may be partly rewritten" if self.refusal is RollbackRefusal.IO_ERROR else "left unchanged"
        return f"{STATUS_ROLLBACK_REFUSED}: {self.refusal.value}; {self.events_path} {state}. Inspect with: git diff HEAD -- {self.events_path}"


def _refuse(events_path: Path, refusal: RollbackRefusal) -> RollbackOutcome:
    outcome = RollbackOutcome(rolled_back=False, refusal=refusal, events_path=events_path)
    logger.warning("%s", outcome.message())
    return outcome


def append_refusal_to_error(exc: BaseException, refusal: str) -> None:
    """Append the refused-rollback text *refusal* to *exc* so callers that print the error show it (once).

    Rewrites the first string argument as ``"<message> [<refusal>]"``; an exception
    without one carries the text as a note instead.
    """
    if not refusal or refusal in str(exc):
        return
    if exc.args and isinstance(exc.args[0], str):
        exc.args = (f"{exc.args[0]} [{refusal}]", *exc.args[1:])
    else:
        exc.add_note(refusal)


def rollback_io_failure(point: RollbackPoint, exc: OSError) -> RollbackOutcome:
    """The refusal outcome for a rollback that raised *exc*, so the caller prints a coded message instead of a traceback.

    The files may be partly rewritten (the failure came from the filesystem), so the
    message tells the operator to inspect them.
    """
    logger.warning("rollback of %s failed: %s", point.events_path, exc)
    return _refuse(point.events_path, RollbackRefusal.IO_ERROR)


def _done(events_path: Path) -> RollbackOutcome:
    return RollbackOutcome(rolled_back=True, refusal=None, events_path=events_path)


def _parse_tail_event_ids(tail: bytes) -> list[str] | None:
    """Event ids of the whole JSON rows in *tail*, or ``None`` when it is not whole rows.

    Blank lines are legal (``append_raw_rows_atomic`` inserts a leading newline when
    the log lacked a trailing one); a last row without its newline is torn.
    """
    if tail and not tail.endswith(b"\n"):
        return None
    ids: list[str] = []
    for raw in tail.split(b"\n"):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except ValueError:
            return None
        event_id = row.get(_EVENT_ID_KEY) if isinstance(row, dict) else None
        if not isinstance(event_id, str):
            return None
        ids.append(event_id)
    return ids


def _head_is_unborn(root: Path) -> bool:
    """Whether HEAD names a branch that has no commit yet (a corrupt ref is not unborn: it stays unreadable)."""
    branch = run_git(root, "symbolic-ref", "--quiet", _HEAD, check=False)
    if branch.returncode != 0:
        return False  # detached HEAD (or an error): let the blob read decide, fail closed
    ref = branch.stdout.decode("utf-8", "replace").strip()
    return run_git(root, "show-ref", "--verify", "--quiet", ref, check=False).returncode == 1


def _committed_event_ids(events_path: Path) -> frozenset[str]:
    """Event ids of the log committed at ``HEAD`` of the checkout holding *events_path*.

    Empty when the path is not in a git checkout, HEAD is unborn, or HEAD does not
    track the log.

    Raises:
        GitCommandError: git failed in a way that leaves the committed log unknown.
        ValueError: the committed log holds a line that is not JSON (the committed ids are unknown).
    """
    cwd = events_path.parent
    # LC_ALL=C pins git's diagnostics to English so the non-repository probe below is locale-independent.
    top = run_git(cwd, "rev-parse", "--show-toplevel", env={**os.environ, "LC_ALL": "C"}, check=False)
    if top.returncode != 0:
        if _NOT_A_REPOSITORY in top.stderr:
            return frozenset()
        raise GitCommandError(argv=("rev-parse", "--show-toplevel"), cwd=cwd, returncode=top.returncode, stderr=top.stderr.decode("utf-8", "replace"))
    root = Path(top.stdout.decode("utf-8", "replace").strip())
    if _head_is_unborn(root):
        return frozenset()
    relative = events_path.resolve().relative_to(root.resolve()).as_posix()
    committed = blob_at(root, _HEAD, relative)
    if committed is None:
        return frozenset()
    ids: set[str] = set()
    for raw in committed.split(b"\n"):
        row = json.loads(raw) if raw.strip() else None  # a malformed committed line raises ValueError: the caller fails closed
        if isinstance(row, dict) and isinstance(row.get(_EVENT_ID_KEY), str):
            ids.add(row[_EVENT_ID_KEY])
    return frozenset(ids)


def _verify_tail(
    point: RollbackPoint,
    fh: BinaryIO,
    expected_event_ids: Sequence[str] | None,
) -> RollbackRefusal | None:
    """Return why the tail after ``point.pre_event_size`` may not be cut, or ``None`` when it may.

    Reads from *fh*, the descriptor that is truncated afterwards.
    """
    size = os.fstat(fh.fileno()).st_size
    if size < point.pre_event_size:
        return RollbackRefusal.LOG_SHRANK
    fh.seek(point.pre_event_size)
    tail_ids = _parse_tail_event_ids(fh.read(size - point.pre_event_size))
    if tail_ids is None:
        return RollbackRefusal.TAIL_UNPARSEABLE
    if expected_event_ids is not None and Counter(tail_ids) != Counter(expected_event_ids):
        return RollbackRefusal.TAIL_NOT_OWNED
    if not tail_ids:
        return None
    try:
        committed = _committed_event_ids(point.events_path)
    except (GitCommandError, ValueError, OSError):
        return RollbackRefusal.HEAD_UNREADABLE
    if committed.intersection(tail_ids):
        return RollbackRefusal.TAIL_ALREADY_COMMITTED
    return None


def _cut_tail(point: RollbackPoint, fh: BinaryIO) -> None:
    """Cut the log back to the capture point (never extends); unlink a log that did not exist at capture."""
    if not point.events_existed:
        fh.close()
        point.events_path.unlink(missing_ok=True)
        return
    if os.fstat(fh.fileno()).st_size > point.pre_event_size:
        os.ftruncate(fh.fileno(), point.pre_event_size)
        os.fsync(fh.fileno())


def _rollback_events_locked(
    point: RollbackPoint,
    expected_event_ids: Sequence[str] | None,
) -> RollbackOutcome:
    try:
        fh = point.events_path.open("r+b")
    except FileNotFoundError:
        if point.events_existed:
            return _refuse(point.events_path, RollbackRefusal.LOG_VANISHED)
        return _done(point.events_path)
    with fh:
        refusal = _verify_tail(point, fh, expected_event_ids)
        if refusal is not None:
            return _refuse(point.events_path, refusal)
        _cut_tail(point, fh)
    return _done(point.events_path)


def rollback_events_log(
    point: RollbackPoint,
    *,
    expected_event_ids: Sequence[str] | None = None,
    repo_root: Path | None = None,
) -> RollbackOutcome:
    """Cut the rows appended after *point*, or refuse and leave the log byte-identical.

    Runs inside the Mission write lock (re-entrant). *expected_event_ids*, when the
    caller knows the ids it appended, must equal the tail's ids as a multiset.
    """
    with mission_write_lock(point.events_path.parent, repo_root=repo_root):
        return _rollback_events_locked(point, expected_event_ids)


def _restore_status_bytes(point: RollbackPoint) -> None:
    if point.pre_status_bytes is None:
        point.status_path.unlink(missing_ok=True)
    else:
        atomic_write(point.status_path, point.pre_status_bytes, mkdir=True)


def rollback_status_artifacts(
    point: RollbackPoint,
    *,
    expected_event_ids: Sequence[str] | None = None,
    repo_root: Path | None = None,
) -> RollbackOutcome:
    """Roll the log back, then restore ``status.json``, only when the log half succeeded."""
    with mission_write_lock(point.events_path.parent, repo_root=repo_root):
        outcome = _rollback_events_locked(point, expected_event_ids)
        if outcome.rolled_back:
            _restore_status_bytes(point)
        return outcome
