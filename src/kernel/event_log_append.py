"""Interim locked append for event logs (#6606; retires at the #6193 handover).

Why this module exists
----------------------
ADR 2026-10-14-1, as amended by ADR 2026-10-22-1, makes the Java write
service the one canonical event writer. Until it owns a log, the CLI still
appends to it. Several writers used a plain ``open("a")``: no lock, no
refusal of a torn last line, and a buffered write that can interleave with a
second writer. A torn line in ``decisions.events.jsonl`` is committed and
travels to other clones.

This module is the ONE interim lock contract that every such append takes
(``kitty-specs/eventbridge-gate-and-locked-appends-01M5T0TN/contracts/interim-ledger-lock.md``),
so the Java writer has one contract to interoperate with. ADR 2026-10-22-1 D-4
says it takes the same OS lock files with ``flock(2)`` semantics.

0. **Anchor.** The log itself. For a family of one-file-per-record logs
   (``kitty-ops/<op>.jsonl``), the family directory, so the number of lock
   files does not grow with the number of records.
1. **Lock file** (:func:`event_log_lock_path`):
   ``<git-common-dir>/spec-kitty-locks/event-logs/<digest>.lock``, where
   ``<digest>`` is the first 32 hex characters of the SHA-256 of the anchor's
   resolved, ``os.path.normcase``-d path (UTF-8). Every worktree of a
   repository shares the git common dir, so every writer of one log takes one
   lock.
   - Outside a git repository, the lock is ``<anchor>.event-log.lock``.
   - When git cannot be invoked at all, the append refuses
     (:class:`EventLogLockUnavailableError`) rather than lock where other
     writers do not.
2. **Lock.** An exclusive :func:`kernel.locks.machine_file_lock`, with a
   bounded wait (:data:`EVENT_LOG_LOCK_TIMEOUT_S`). It is re-entrant within
   one thread: a nested :func:`event_log_lock` on the same anchor reuses the
   held lock, so a writer may hold it across a loop of appends (#6706). It
   is never held across a wait on a person.
3. **Torn tail.** Under the lock, a log whose last byte is not LF is refused
   (:class:`EventLogTornTailError`), and nothing is written.
4. **Write.** The whole unit in one ``os.write`` on an ``O_APPEND``
   descriptor, then ``os.fsync``.

It validates line framing only, never row content. The write service is the
validation authority (operator ruling 2026-10-25, #6117), so each caller keeps
serialising its own row bytes. ``status.events.jsonl`` and
``canonical-events.jsonl`` are not appended here: they keep the Mission status
lock and the ``status.store`` primitives.

Every refusal subclasses :class:`OSError`, so a caller that already treats an
I/O failure as non-fatal keeps doing so.

Retirement: each log's interim append is deleted when the write service takes
that log over whole (ADR 2026-10-22-1 D-4, "Handover"). This module goes with
the last one. ``tests/architectural/test_event_log_writes_gate.py`` ledgers
every caller.
"""

from __future__ import annotations

import os
import threading
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

from kernel.content_digest import sha256_digest
from kernel.git_topology import GitTopologyUnavailableError, NotAGitRepositoryError, git_common_dir
from kernel.locks import LOCK_DIRECTORY, LockAcquireTimeout, machine_file_lock
from kernel.no_follow import NoFollowPathError, open_no_follow

# Only names another src/ module imports are exported; the rest stay importable (tests use them).
__all__ = [
    "EventLogAppendError",
    "EventLogSymlinkError",
    "EventLogTornTailError",
    "append_event_log_lines",
    "event_log_lock",
    "event_log_lock_path",
]

#: Directory under ``<git-common-dir>/spec-kitty-locks/`` that holds the per-log lock files.
EVENT_LOG_LOCK_SUBDIRECTORY = "event-logs"

#: Suffix of the lock file beside the anchor outside a git repository. It differs
#: from the glossary repair lock (``<log>.lock``), which is taken while this
#: lock is held, so the two never name the same file.
NON_GIT_LOCK_SUFFIX = ".event-log.lock"

#: Bounded wait for the lock, in seconds.
EVENT_LOG_LOCK_TIMEOUT_S = 10.0

_DIGEST_LENGTH = 32

#: Lock files this thread holds, keyed by the resolved anchor (#6706).
_held = threading.local()


def _drop_inherited_held_locks() -> None:
    """Forget locks the parent held: a forked child does not own them."""
    _held.__dict__.clear()


if hasattr(os, "register_at_fork"):  # absent on Windows
    os.register_at_fork(after_in_child=_drop_inherited_held_locks)

_DIGEST_PREFIX = "sha256:"
_LF = b"\n"
_LINE_TERMINATORS = ("\n", "\r")

#: Called with the log's current bytes while the lock is held; raises to refuse the append.
Precondition = Callable[[bytes], None]


class EventLogAppendError(OSError):
    """Base class of every refusal of the interim event-log append.

    The message ends with ``Error code: <CODE>.`` (the consolidate
    convention), so an operator can quote the refusal by its ``code``.
    """

    code = "EVENT_LOG_APPEND_FAILED"

    def __init__(self, message: str) -> None:
        super().__init__(f"{message} Error code: {self.code}.")


class EventLogTornTailError(EventLogAppendError):
    """The log's last byte is not LF (a torn line); nothing was appended."""

    code = "EVENT_LOG_TORN_TAIL"


class EventLogLockTimeoutError(EventLogAppendError):
    """The event-log lock was not acquired within the bounded wait; nothing was appended."""

    code = "EVENT_LOG_LOCK_TIMEOUT"


class EventLogLockUnavailableError(EventLogAppendError):
    """Git could not be invoked to place the lock; nothing was appended."""

    code = "EVENT_LOG_LOCK_UNAVAILABLE"


class EventLogSymlinkError(EventLogAppendError):
    """The log is a final-component symlink and the caller asked not to follow it."""

    code = "EVENT_LOG_SYMLINK"


class EventLogShortWriteError(EventLogAppendError):
    """``os.write`` wrote fewer bytes than the unit (impossible on a regular local file)."""

    code = "EVENT_LOG_SHORT_WRITE"


def event_log_lock_path(anchor: Path) -> Path:
    """Return the lock file that every append anchored on *anchor* takes (contract rule 1).

    Raises:
        EventLogLockUnavailableError: git could not be invoked.
    """
    resolved = anchor.resolve()
    try:
        common_dir = git_common_dir(resolved.parent)
    except NotAGitRepositoryError:
        return resolved.with_name(resolved.name + NON_GIT_LOCK_SUFFIX)
    except GitTopologyUnavailableError as exc:
        raise EventLogLockUnavailableError(
            f"{anchor}: cannot place the event-log lock because git could not be invoked ({exc}). Make git runnable in this checkout, then retry."
        ) from exc
    digest = sha256_digest(os.path.normcase(str(resolved)).encode("utf-8")).removeprefix(_DIGEST_PREFIX)[:_DIGEST_LENGTH]
    return common_dir / LOCK_DIRECTORY / EVENT_LOG_LOCK_SUBDIRECTORY / f"{digest}.lock"


@contextmanager
def event_log_lock(anchor: Path, *, timeout_s: float = EVENT_LOG_LOCK_TIMEOUT_S) -> Iterator[Path]:
    """Hold the interim event-log lock anchored on *anchor*; yield the lock file path.

    For a writer that appends through another sanctioned primitive (the
    glossary's ``spec_kitty_events.persistence.append_event``) but must still
    exclude the other writers of the same log.

    Re-entrant within one thread, like an ``RLock``: a nested call on the same
    anchor yields the lock already held, with no second acquire and no git
    probe, so a writer can hold the lock across a loop of appends (#6706).

    Re-entrancy is per thread and per resolved anchor. Never nest this lock on
    a different anchor: two anchors have no lock order, so two threads nesting
    them in opposite orders can deadlock until the timeout.
    """
    key = anchor.resolve()
    held: dict[Path, Path] = _held.__dict__.setdefault("locks", {})
    if key in held:
        yield held[key]
        return
    lock_path = event_log_lock_path(anchor)
    try:
        with machine_file_lock(lock_path, blocking=True, timeout_s=timeout_s):
            held[key] = lock_path
            try:
                yield lock_path
            finally:
                del held[key]
    except LockAcquireTimeout as exc:
        raise EventLogLockTimeoutError(
            f"{anchor}: event-log lock {lock_path} was not acquired within {timeout_s}s because another writer holds it. Retry, or stop the other writer."
        ) from exc


def append_event_log_lines(
    log: Path,
    lines: Sequence[str],
    *,
    lock_anchor: Path | None = None,
    create: bool = True,
    create_parents: bool = False,
    no_follow: bool = False,
    mode: int = 0o666,
    precondition: Precondition | None = None,
    timeout_s: float = EVENT_LOG_LOCK_TIMEOUT_S,
) -> None:
    """Append *lines* to *log* as one unit under the interim event-log lock.

    Args:
        log: The event log.
        lines: Pre-serialised rows, each without a line terminator.
        lock_anchor: The family directory for a one-file-per-record log;
            defaults to *log*.
        create: Create the log when it is missing; otherwise raise ``FileNotFoundError``.
        create_parents: Create the log's parent directories first. Without
            it, a missing parent raises ``FileNotFoundError`` before any lock
            is placed, so the lock never creates a directory.
        no_follow: Refuse a final-component symlink at *log*.
        mode: Permission bits of a newly created log, before the umask
            applies (the default follows the umask, like ``open("a")``).
        precondition: Called with the log's current bytes under the lock. An
            exception it raises propagates, and nothing is written.
        timeout_s: Bounded wait for the lock.

    Raises:
        ValueError: *lines* is empty, or a line holds a line terminator.
        FileNotFoundError: The parent (or, with ``create=False``, the log) is missing.
        EventLogTornTailError: The log's last byte is not LF.
        EventLogLockTimeoutError: The lock was not acquired in time.
        EventLogLockUnavailableError: Git could not be invoked to place the lock.
        EventLogSymlinkError: ``no_follow`` and *log* is a symlink.
        EventLogShortWriteError: The write landed partially.
    """
    payload = _encode_unit(lines)
    if create_parents:
        log.parent.mkdir(parents=True, exist_ok=True)
    elif not log.parent.is_dir():
        raise FileNotFoundError(f"{log}: parent directory does not exist")
    with event_log_lock(lock_anchor or log, timeout_s=timeout_s):
        fd = _open_for_append(log, create=create, no_follow=no_follow, mode=mode)
        try:
            pre_size = _check_existing(fd, log, precondition)
            _write_unit(fd, log, payload, pre_size)
        finally:
            os.close(fd)


def _encode_unit(lines: Sequence[str]) -> bytes:
    if isinstance(lines, str) or not lines:
        raise ValueError("append_event_log_lines needs a non-empty sequence of lines")
    if not all(isinstance(line, str) for line in lines):
        raise TypeError("event-log lines must be str (pre-serialised rows)")
    if any(terminator in line for line in lines for terminator in _LINE_TERMINATORS):
        raise ValueError("an event-log line must not contain a line terminator")
    return "".join(f"{line}\n" for line in lines).encode("utf-8")


def _open_for_append(log: Path, *, create: bool, no_follow: bool, mode: int) -> int:
    flags = os.O_RDWR | os.O_APPEND | getattr(os, "O_BINARY", 0) | (os.O_CREAT if create else 0)
    if not no_follow:
        return os.open(log, flags, mode)
    try:
        return open_no_follow(log, flags, mode)
    except NoFollowPathError as exc:
        raise EventLogSymlinkError(f"{log}: refusing to append through a symbolic link.") from exc


def _check_existing(fd: int, log: Path, precondition: Precondition | None) -> int:
    """Refuse a torn tail or a failed precondition; return the log's size before the write."""
    size = os.fstat(fd).st_size
    existing = _read_range(fd, 0 if precondition is not None else max(size - 1, 0), size)
    if size and existing[-1:] != _LF:
        raise EventLogTornTailError(
            f"{log}: the last line is torn (no trailing newline), so the append was refused. Inspect the file and cut the bytes after its last newline, then retry."
        )
    if precondition is not None:
        precondition(existing)
    return size


def _read_range(fd: int, offset: int, end: int) -> bytes:
    """Read ``[offset, end)`` of *fd* with ``lseek`` + ``read`` (``os.pread`` is POSIX-only)."""
    os.lseek(fd, offset, os.SEEK_SET)
    chunks: list[bytes] = []
    remaining = end - offset
    while remaining > 0:
        chunk = os.read(fd, remaining)
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _write_unit(fd: int, log: Path, payload: bytes, pre_size: int) -> None:
    """Write the unit; on a partial write, cut the log back to *pre_size* before re-raising.

    The lock is still held, so no other writer appended since *pre_size* was
    read. Without the cut, a short write (or ``ENOSPC`` after a partial write)
    leaves a torn tail that refuses every later append.
    """
    try:
        written = os.write(fd, payload)
        if written != len(payload):
            raise EventLogShortWriteError(f"{log}: short write ({written} of {len(payload)} bytes); the append was refused.")
    except OSError as exc:
        _truncate_to(fd, pre_size, exc)
        raise
    os.fsync(fd)


def _truncate_to(fd: int, size: int, cause: OSError) -> None:
    """Cut *fd* back to *size* and fsync; if that fails, raise *cause* chained to the failure."""
    try:
        os.ftruncate(fd, size)
        os.fsync(fd)
    except OSError as truncate_exc:
        raise cause from truncate_exc
