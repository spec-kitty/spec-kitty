"""The single door to raw cross-process file locking (FR-006/007/010, DIRECTIVE_043).

Every raw OS-level file lock (POSIX :func:`fcntl.flock`, Windows
:func:`msvcrt.locking`) and every third-party ``filelock`` construction in
this codebase is meant to route through this module. A repo-wide gate
(``tests/architectural/test_lock_primitive_ban.py``) bans the raw stdlib
calls and the ``filelock`` import/constructor everywhere else in ``src/``
(``tests/``/``scripts/`` are deliberately out of scope -- they legitimately
exercise raw locking to prove this module's own cross-OS parity, see that
gate's docstring for the rationale).

**Migration history**: this module is a *move*, not a rewrite, of
``specify_cli.core.file_lock.MachineFileLock`` (mission ``cross-os-primitive-
unification``, research R-01/A-04). That helper's only non-stdlib import was
already ``kernel.clock``, so moving it here makes that an intra-``kernel``
edge -- nothing drags ``specify_cli`` upward. Kernel is zero-third-party-dep
(C-001), which is exactly what forces this primitive to stay stdlib-only
(no ``filelock`` dependency) -- the enforcement mechanism for "one canonical
primitive" (NFR-001).

**Guarantees** (contracts/lock-primitive.md G1-G7):

- G1 -- **Caller supplies a dedicated lock-only path.** The caller passes
  ``lock_path`` -- a path that exists *only* to be locked; this exact path
  is opened, OS-locked, and **truncated** directly (see
  :func:`_atomic_write_under_lock`). Nothing is derived from it, and it
  must never be a payload path: passing a payload path here would truncate
  and overwrite that payload. The #4703 property is **G2** below, not this
  one.
- G2 -- **No payload handle is ever yielded.** Both the async
  (:class:`MachineFileLock`) and sync (:class:`SyncMachineFileLock`) context
  managers yield a :class:`LockRecord` (holder metadata only) -- there is no
  code path from either ``__aenter__``/``__enter__`` to a handle on the
  protected resource. This makes the #4703 footgun (reading a payload
  through a lock you hold, which is only safe on advisory POSIX and raises
  ``PermissionError`` on Windows' mandatory ``msvcrt.locking``) structurally
  impossible: there is nothing to read *through*.
- G3 -- **Release truncates, never unlinks** (preserves inode identity so a
  contender's ``O_CREAT`` cannot mint a rival inode and defeat mutual
  exclusion).
- G4 -- **Both sync + async over one shared core** (:class:`_LockCore`);
  ``blocking``/``timeout_s`` cover both a single non-blocking attempt and a
  bounded blocking-with-timeout wait (see :func:`_acquire_common`).
- G5 -- **Re-entrancy** (``reentrant=True``, thread-local) for callers such
  as ``status/locking.py`` (WP05) that rely on same-thread re-entrant
  acquisition.
- G6 -- **Test-double injection seam**: :func:`machine_file_lock` resolves
  :class:`SyncMachineFileLock` through this module's own namespace at call
  time, so a caller module that constructs locks via the factory can have
  its locking replaced wholesale in tests by monkeypatching
  ``kernel.locks.SyncMachineFileLock`` (mirrors ``review/verdict_commit_queue
  .py``'s pre-migration test-double pattern, R-04).
- G7 -- **Sole raw-primitive holder**, enforced by the FR-010 gate.

Not a distributed lock, not a datastore lock -- loopback/local filesystem
mutual exclusion only.
"""

from __future__ import annotations

import asyncio
import contextlib
import errno
import json
import os
import socket
import sys
import threading
import time
from dataclasses import dataclass
from importlib import metadata as importlib_metadata
from pathlib import Path
from types import TracebackType
from typing import Any

from kernel.clock import UTC, datetime, now_utc, parse_iso
from kernel.no_follow import open_no_follow
from kernel.paths import is_windows

# NOTE: this module-scope import guard deliberately keeps the raw
# ``sys.platform == "win32"`` literal rather than routing through
# ``is_windows()`` (unlike every OTHER platform check in this module, just
# below). Two reasons, both load-bearing:
# 1. It is the PERMANENT "sanctioned-raw" idiom the OS-detection ban gate
#    (tests/architectural/test_os_detection_ban.py) explicitly carves out --
#    see tests/architectural/_exemptions/os-detect-ban-sanctioned-raw.txt --
#    matching the pre-move file_lock.py's own line 41.
# 2. mypy special-cases a LITERAL ``sys.platform``/``sys.version_info``
#    comparison to statically narrow (and skip-check) the unreachable branch
#    on the host platform; routing this specific guard through the
#    ``is_windows()`` function call defeats that narrowing and made
#    ``mypy --strict`` report spurious ``msvcrt`` attr-defined errors on a
#    non-Windows host during T010 development (verified: reverting this one
#    guard to the raw literal, while leaving every other check below on
#    ``is_windows()``, is what clears them).
if sys.platform == "win32":  # pragma: no cover - platform-specific
    import msvcrt
else:
    import fcntl  # noqa: F401  (imported lazily under POSIX guard)

__all__ = [
    "STALE_AFTER_S_DEFAULT",
    "LockAcquireTimeout",
    "LockNotAcquired",
    "LockRecord",
    "MachineFileLock",
    "SyncMachineFileLock",
    "force_release",
    "machine_file_lock",
    "read_lock_record",
]


STALE_AFTER_S_DEFAULT: float = 60.0
"""Default age threshold (seconds) above which a lock record is considered stale.

Stale locks may be safely adopted by new acquirers and removed via
:func:`force_release`. The default is 6x the NFR-002 hold ceiling (10 s) so
slow but legitimate transactions are never preempted.
"""

_ACQUIRE_TIMEOUT_DEFAULT: float = 10.0
_MAX_HOLD_DEFAULT: float = 10.0
_RETRY_SLEEP_S: float = 0.1
_SCHEMA_VERSION: int = 1


class LockAcquireTimeout(Exception):
    """Raised when a blocking acquire with a deadline cannot acquire in time.

    The lock path that timed out is exposed via :attr:`path` for diagnostics.
    """

    def __init__(self, *, path: str) -> None:
        super().__init__(f"Could not acquire machine lock at {path!r} within bounded wait")
        self.path = path


class LockNotAcquired(Exception):
    """Raised by a non-blocking (``blocking=False``) acquire on contention.

    Distinct from :class:`LockAcquireTimeout`: a non-blocking acquire never
    waits, so this is raised on the very first contended attempt, not after
    a deadline elapses (data-model.md's ``acquire (contended, non-blocking)
    -> NotAcquired`` transition).
    """

    def __init__(self, *, path: str) -> None:
        super().__init__(f"Machine lock at {path!r} is held by another holder (non-blocking attempt)")
        self.path = path


@dataclass(frozen=True)
class LockRecord:
    """Snapshot of the holder of a machine-wide file lock.

    Fields mirror the JSON record persisted under the lock file:

    - ``schema_version`` -- content schema version (currently ``1``).
    - ``pid`` -- operating-system process identifier of the holder.
    - ``started_at`` -- tz-aware UTC :class:`datetime` when the lock was taken.
    - ``host`` -- hostname of the machine that wrote the record.
    - ``version`` -- ``spec-kitty-cli`` package version (or ``"unknown"``).
    """

    schema_version: int
    pid: int
    started_at: datetime
    host: str
    version: str

    @property
    def age_s(self) -> float:
        """Return seconds elapsed since :attr:`started_at` (clamped at ``0``)."""
        delta = (now_utc() - self.started_at).total_seconds()
        return delta if delta > 0 else 0.0

    def is_stuck(self, threshold_s: float = STALE_AFTER_S_DEFAULT) -> bool:
        """Return ``True`` when :attr:`age_s` exceeds ``threshold_s``."""
        return self.age_s > threshold_s


def _get_package_version() -> str:
    """Return the installed ``spec-kitty-cli`` version, or ``"unknown"``."""
    try:
        return importlib_metadata.version("spec-kitty-cli")
    except importlib_metadata.PackageNotFoundError:
        return "unknown"


def _is_contention_error(exc: OSError) -> bool:
    """Return ``True`` when ``exc`` is a normal non-blocking lock contention.

    Non-contention :class:`OSError` instances (genuine I/O errors such as
    ``ENOSPC``) propagate to the caller -- the helper does not silently treat
    them as contention.
    """
    if isinstance(exc, BlockingIOError):
        return True
    if exc.errno is None:
        return False
    if is_windows():
        return exc.errno in {errno.EACCES, errno.EDEADLK}
    return exc.errno in {errno.EACCES, errno.EAGAIN}


def _os_lock(fd: int) -> None:
    """Acquire a non-blocking exclusive OS-level lock on ``fd``.

    Raises :class:`OSError` on contention; callers must use
    :func:`_is_contention_error` to distinguish contention from genuine errors.

    NOTE: like the module-scope import guard above, this dispatch stays on
    the raw ``sys.platform == "win32"`` literal rather than ``is_windows()``
    -- it is the same sanctioned-raw idiom (tests/architectural/_exemptions/
    os-detect-ban-sanctioned-raw.txt), extended from "which module do I
    import" to "which module's attribute do I call", for the identical
    mypy-narrowing reason: routing THIS specific literal through a function
    call leaves ``msvcrt``/``fcntl`` attribute access unresolvable under
    ``mypy --strict`` on whichever platform mypy is not modelling.
    """
    if sys.platform == "win32":  # pragma: no cover - platform-specific
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
    else:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)


def _os_unlock(fd: int) -> None:
    """Release an OS-level lock on ``fd`` previously acquired via :func:`_os_lock`.

    See :func:`_os_lock`'s note: the same sanctioned-raw ``sys.platform``
    dispatch, for the same mypy-narrowing reason.
    """
    if sys.platform == "win32":  # pragma: no cover - platform-specific
        # Best-effort: release errors do not invalidate caller invariants.
        with contextlib.suppress(OSError):
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    else:
        with contextlib.suppress(OSError):
            fcntl.flock(fd, fcntl.LOCK_UN)


def _atomic_write_under_lock(fd: int, payload: bytes) -> None:
    """Replace the contents of the locked ``fd`` with ``payload`` atomically.

    Atomic for concurrent readers in practice: readers that race the truncate
    window observe an empty file (handled as "no record"); readers that
    arrive after the single ``write`` see the complete record. Sub-PIPE_BUF
    writes to regular files are atomic on POSIX, ruling out partial-record
    observation. We do NOT use ``kernel.atomic``'s helper here because that
    helper rotates the inode via ``os.replace``, which would detach the OS
    lock from the live file path and break mutual exclusion.
    """
    os.ftruncate(fd, 0)
    os.lseek(fd, 0, os.SEEK_SET)
    written = 0
    while written < len(payload):
        chunk = os.write(fd, payload[written:])
        if chunk <= 0:  # pragma: no cover - defensive
            raise OSError(errno.EIO, "short write while persisting lock record")
        written += chunk
    os.fsync(fd)


def _ensure_dir(path: Path) -> None:
    """Create the parent directory of ``path``, hardening it ONLY if this call created it.

    Harden a freshly-created dedicated lock directory to ``0o700`` on POSIX,
    but never chmod a directory that already existed -- it may be a SHARED
    directory this primitive does not own (e.g. a managed cache dir a
    caller keeps at a wider mode alongside other tracked state), and
    narrowing it out from under that owner on every acquire is a real,
    observable write, not a safe default. ``mkdir(parents=True)`` without
    ``exist_ok`` is the atomic test: it raises ``FileExistsError`` when the
    final path component already exists, so the "did I create it" check
    never races a concurrent creator. (Review origin: #4714 WP04 review --
    the caller-side workaround this replaced narrowed a shared dir on every
    lock acquire.)
    """
    parent = path.parent
    try:
        parent.mkdir(parents=True)
    except FileExistsError:
        return
    if not is_windows():
        # On filesystems that do not honour POSIX modes we silently accept.
        with contextlib.suppress(OSError):
            os.chmod(parent, 0o700)


def _record_to_json(record: LockRecord) -> str:
    payload: dict[str, Any] = {
        "schema_version": record.schema_version,
        "pid": record.pid,
        "started_at": record.started_at.isoformat(),
        "host": record.host,
        "version": record.version,
    }
    return json.dumps(payload, sort_keys=True)


def _record_from_payload(payload: object) -> LockRecord | None:
    if not isinstance(payload, dict):
        return None
    try:
        schema_version = int(payload["schema_version"])
        pid = int(payload["pid"])
        started_raw = payload["started_at"]
        host = payload["host"]
        version = payload["version"]
    except (KeyError, TypeError, ValueError):
        return None
    if not isinstance(started_raw, str) or not isinstance(host, str) or not isinstance(version, str):
        return None
    try:
        started_at = parse_iso(started_raw)
    except ValueError:
        return None
    if started_at.tzinfo is None:
        # Treat naive timestamps as UTC for backwards compatibility.
        started_at = started_at.replace(tzinfo=UTC)
    return LockRecord(
        schema_version=schema_version,
        pid=pid,
        started_at=started_at,
        host=host,
        version=version,
    )


def _record_from_bytes(raw: bytes) -> LockRecord | None:
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return _record_from_payload(payload)


def _read_lock_record_from_fd(fd: int) -> LockRecord | None:
    try:
        os.lseek(fd, 0, os.SEEK_SET)
        raw = os.read(fd, 65536)
    except OSError:
        return None
    return _record_from_bytes(raw)


def read_lock_record(lock_path: Path) -> LockRecord | None:
    """Return the lock record at ``lock_path`` without acquiring the OS lock.

    Returns ``None`` when:

    - the file does not exist;
    - the file is empty or contains malformed JSON;
    - the JSON is missing required keys or has wrong types.

    This reads the *sidecar record* only -- never a payload -- so it never
    interferes with an in-flight transaction. On POSIX (advisory locks) it
    always returns the current holder's record whether or not the lock is
    held. On Windows the record file carries a *mandatory* byte-range lock
    while held, so a concurrent read is refused, caught, and reported as
    ``None`` -- the holder is surfaced only once the lock releases. Used by
    ``auth doctor`` to name the holding process, degrading gracefully to
    "no holder shown" during the held window on Windows.
    """
    try:
        raw = lock_path.read_bytes()
    except OSError:
        return None
    return _record_from_bytes(raw)


def force_release(lock_path: Path, *, only_if_age_s: float = STALE_AFTER_S_DEFAULT) -> bool:
    """Clear the lock record at ``lock_path`` iff it is older than ``only_if_age_s``.

    Returns ``True`` when the record was cleared (it existed and was stuck);
    ``False`` when the file is missing, unreadable, held, or still considered fresh.

    A lock cannot be ripped out from under a running process: force release
    first proves the OS lock is available, then truncates the existing inode
    under that lock instead of unlinking the path.
    """
    record = read_lock_record(lock_path)
    if record is None:
        return False
    if record.age_s <= only_if_age_s:
        return False
    try:
        # Same no-follow routing as ``_LockCore.open_fd`` above: a planted
        # symlink at ``lock_path`` must raise ``NoFollowPathError`` rather
        # than being followed and truncated. This intentionally propagates
        # past the surrounding ``except OSError`` (``NoFollowPathError`` is a
        # ``RuntimeError``, not an ``OSError``) -- a symlinked lock path is a
        # security signal the caller must see, not a routine "lock missing/
        # unreadable" outcome silently folded into a ``False`` return.
        # ``open_no_follow`` ORs ``O_NOFOLLOW`` in itself -- the door owns the
        # flag, so callers pass only their own intent.
        fd = open_no_follow(lock_path, os.O_RDWR)
    except OSError:
        return False
    try:
        try:
            _os_lock(fd)
        except OSError as exc:
            if not _is_contention_error(exc):
                # Genuine FS error (e.g. EIO/ENOSPC) must propagate, per the module
                # contract (_is_contention_error/_os_lock docstrings) and its twin
                # in _LockCore.try_lock_once. Only true contention -> False (the
                # lock is held, so it cannot be force-released).
                raise
            return False
        locked_record = _read_lock_record_from_fd(fd)
        if locked_record is None or locked_record.age_s <= only_if_age_s:
            return False
        try:
            _atomic_write_under_lock(fd, b"")
        except OSError:
            return False
        return True
    finally:
        _os_unlock(fd)
        with contextlib.suppress(OSError):
            os.close(fd)


def _build_record() -> LockRecord:
    return LockRecord(
        schema_version=_SCHEMA_VERSION,
        pid=os.getpid(),
        started_at=now_utc(),
        host=socket.gethostname(),
        version=_get_package_version(),
    )


class _LockCore:
    """Shared open/OS-lock/write-record/truncate/unlock primitive (G4).

    Not part of the public API. Both facades (:class:`MachineFileLock`,
    :class:`SyncMachineFileLock`) delegate every filesystem/OS-lock operation
    to one instance of this core so the two facades cannot drift in their
    locking semantics -- only their *waiting strategy* (``asyncio.sleep`` vs
    ``time.sleep``) differs, in :func:`_async_acquire`/:func:`_sync_acquire`.
    """

    __slots__ = ("lock_path", "fd", "record")

    def __init__(self, lock_path: Path) -> None:
        self.lock_path = lock_path
        self.fd: int | None = None
        self.record: LockRecord | None = None

    def open_fd(self) -> int:
        _ensure_dir(self.lock_path)
        flags = os.O_RDWR | os.O_CREAT
        # ``0o600`` keeps the lock file readable only by the owner on POSIX.
        # Routed through ``open_no_follow`` (rather than a second raw
        # ``os.open``) so there is exactly one no-follow implementation
        # (#4756, FR-001) that owns the ``O_NOFOLLOW`` flag itself -- callers
        # pass only their own flags: a planted symlink at ``lock_path`` raises
        # ``NoFollowPathError`` instead of being followed and later
        # truncated/overwritten by ``commit_record``/``release``. No
        # ``O_EXCL`` -- lock files are re-opened by every later acquirer
        # (release truncates, never unlinks, per G3); ``O_EXCL`` would make
        # every re-acquisition after the first fail (C-003).
        return open_no_follow(self.lock_path, flags, 0o600)

    def try_lock_once(self, fd: int) -> bool:
        """Attempt one non-blocking OS-level lock. ``True``=acquired, ``False``=contended."""
        try:
            _os_lock(fd)
        except OSError as exc:
            if not _is_contention_error(exc):
                raise
            return False
        return True

    def commit_record(self, fd: int) -> LockRecord:
        """Write a fresh :class:`LockRecord` to the just-locked ``fd`` and bind state."""
        record = _build_record()
        try:
            _atomic_write_under_lock(fd, _record_to_json(record).encode("utf-8"))
        except BaseException:
            # Roll back the OS lock so we never leave it held without content.
            _os_unlock(fd)
            os.close(fd)
            raise
        self.fd = fd
        self.record = record
        return record

    def release(self) -> None:
        fd = self.fd
        if fd is None:
            return
        try:
            # TRUNCATE rather than unlink so the on-disk inode survives and
            # concurrent acquirers serialise against our OS lock until
            # ``_os_unlock`` runs below (G3). Unlinking would let a
            # contender's ``os.open(O_CREAT)`` mint a fresh inode and lock
            # that instead, defeating mutual exclusion.
            with contextlib.suppress(OSError):
                os.ftruncate(fd, 0)
        finally:
            try:
                _os_unlock(fd)
            finally:
                with contextlib.suppress(OSError):
                    os.close(fd)
                self.fd = None
                self.record = None


def _validate_wait_mode(*, blocking: bool, timeout_s: float | None) -> None:
    """Fail fast on a nonsensical ``(blocking, timeout_s)`` combination.

    ``timeout_s`` is only meaningful for a blocking wait (data-model.md:
    ``acquire (contended, non-blocking) -> NotAcquired`` never has a
    deadline; ``acquire (contended, blocking, deadline) -> TimeoutError``
    does).
    """
    if not blocking and timeout_s is not None:
        raise ValueError("timeout_s is only meaningful when blocking=True")


def _attempt_acquire(core: _LockCore) -> LockRecord | None:
    """One non-blocking attempt: acquire+commit, or ``None`` on contention.

    The fd is closed on EVERY non-acquiring path -- contention (``False``)
    and a genuine, re-raised :class:`OSError` alike -- mirroring the
    pre-move ``MachineFileLock.__aenter__`` loop body exactly (it never
    leaked a fd on a non-contention I/O error such as ``ENOSPC``).
    """
    fd = core.open_fd()
    try:
        acquired = core.try_lock_once(fd)
    except OSError:
        os.close(fd)
        raise
    if acquired:
        return core.commit_record(fd)
    os.close(fd)
    return None


async def _async_acquire(core: _LockCore, *, blocking: bool, timeout_s: float | None) -> LockRecord:
    """Async waiting strategy over :func:`_attempt_acquire` (G4)."""
    _validate_wait_mode(blocking=blocking, timeout_s=timeout_s)
    loop = asyncio.get_running_loop()
    deadline = None if timeout_s is None else loop.time() + timeout_s
    while True:
        record = _attempt_acquire(core)
        if record is not None:
            return record
        if not blocking:
            raise LockNotAcquired(path=str(core.lock_path))
        if deadline is not None and loop.time() >= deadline:
            raise LockAcquireTimeout(path=str(core.lock_path))
        await asyncio.sleep(_RETRY_SLEEP_S)


def _sync_acquire(core: _LockCore, *, blocking: bool, timeout_s: float | None) -> LockRecord:
    """Sync waiting strategy over :func:`_attempt_acquire` (G4)."""
    _validate_wait_mode(blocking=blocking, timeout_s=timeout_s)
    deadline = None if timeout_s is None else time.monotonic() + timeout_s
    while True:
        record = _attempt_acquire(core)
        if record is not None:
            return record
        if not blocking:
            raise LockNotAcquired(path=str(core.lock_path))
        if deadline is not None and time.monotonic() >= deadline:
            raise LockAcquireTimeout(path=str(core.lock_path))
        time.sleep(_RETRY_SLEEP_S)


class MachineFileLock:
    """Async context manager guarding a machine-wide advisory lock.

    Usage::

        async with MachineFileLock(lock_path) as record:
            # protected critical section
            ...

    Preserves the pre-move ``specify_cli.core.file_lock.MachineFileLock``
    behaviour verbatim: the acquire path opens ``lock_path`` for write, takes a
    non-blocking OS-level exclusive lock, and writes a :class:`LockRecord`
    describing the current process directly to the locked FD. On exit the OS
    lock is released unconditionally via ``try/finally`` and the file is
    truncated (G3). Internally this maps onto the shared ``blocking=True,
    timeout_s=acquire_timeout_s`` wait mode (G4) -- a bounded retry-until-
    deadline wait, unchanged from the original implementation.

    Bounded-wait semantics: the acquire loop retries every
    ``_RETRY_SLEEP_S`` seconds for at most ``acquire_timeout_s`` seconds. If
    contention persists past the timeout :class:`LockAcquireTimeout` is raised.

    The protected block is the caller's responsibility; ``max_hold_s`` is
    advisory and callers SHOULD wrap the work in :func:`asyncio.wait_for` to
    enforce the NFR-002 10 s ceiling.
    """

    def __init__(
        self,
        lock_path: Path,
        *,
        max_hold_s: float = _MAX_HOLD_DEFAULT,
        stale_after_s: float = STALE_AFTER_S_DEFAULT,
        acquire_timeout_s: float = _ACQUIRE_TIMEOUT_DEFAULT,
    ) -> None:
        self.lock_path = lock_path
        self.max_hold_s = max_hold_s
        self.stale_after_s = stale_after_s
        self.acquire_timeout_s = acquire_timeout_s
        self._core: _LockCore | None = None

    async def __aenter__(self) -> LockRecord:
        core = _LockCore(self.lock_path)
        record = await _async_acquire(core, blocking=True, timeout_s=self.acquire_timeout_s)
        self._core = core
        return record

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._core is not None:
            self._core.release()
            self._core = None


@dataclass
class _ReentrantHolding:
    """Thread-local bookkeeping for one re-entrant sync-lock holding."""

    core: _LockCore
    record: LockRecord
    depth: int = 1


class _ReentrancyState(threading.local):
    """Thread-local map of resolved-lock-path -> current holding.

    A genuine ``threading.local`` subclass (not a module dict keyed by
    thread id) so each thread's holdings are isolated by construction --
    two threads independently re-entering the SAME lock path must be
    treated as ordinary contention, never as one shared re-entrant holding.
    """

    def __init__(self) -> None:
        self.holdings: dict[str, _ReentrantHolding] = {}


_reentrancy_state = _ReentrancyState()


class SyncMachineFileLock:
    """Sync context manager guarding a machine-wide advisory lock (G4).

    Usage::

        with SyncMachineFileLock(lock_path) as record:
            # protected critical section
            ...

    Unlike :class:`MachineFileLock`, ``blocking``/``timeout_s`` are the
    caller-facing wait-mode knobs (G4): ``blocking=False`` (the default) is
    a single non-blocking attempt that raises :class:`LockNotAcquired`
    immediately on contention; ``blocking=True`` retries until ``timeout_s``
    elapses (raising :class:`LockAcquireTimeout`) or forever when
    ``timeout_s`` is ``None``.

    ``reentrant=True`` (G5) lets the SAME thread re-enter a lock it already
    holds over the same resolved lock path without deadlocking or
    re-attempting the OS lock -- each nested ``with`` increments a
    thread-local depth counter; only the outermost ``__exit__`` actually
    releases the OS lock and truncates the sidecar (status/locking.py's
    pre-migration contract, R-04).
    """

    def __init__(
        self,
        lock_path: Path,
        *,
        blocking: bool = False,
        timeout_s: float | None = None,
        reentrant: bool = False,
    ) -> None:
        self.lock_path = lock_path
        self.blocking = blocking
        self.timeout_s = timeout_s
        self.reentrant = reentrant
        self._core: _LockCore | None = None
        self._key: str | None = None

    def _reentrant_key(self) -> str:
        return str(self.lock_path.resolve())

    def __enter__(self) -> LockRecord:
        if not self.reentrant:
            core = _LockCore(self.lock_path)
            record = _sync_acquire(core, blocking=self.blocking, timeout_s=self.timeout_s)
            self._core = core
            return record

        key = self._reentrant_key()
        self._key = key
        existing = _reentrancy_state.holdings.get(key)
        if existing is not None:
            existing.depth += 1
            return existing.record

        core = _LockCore(self.lock_path)
        record = _sync_acquire(core, blocking=self.blocking, timeout_s=self.timeout_s)
        _reentrancy_state.holdings[key] = _ReentrantHolding(core=core, record=record)
        return record

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if not self.reentrant:
            if self._core is not None:
                self._core.release()
                self._core = None
            return

        key = self._key
        if key is None:
            return
        holding = _reentrancy_state.holdings.get(key)
        if holding is None:
            return
        holding.depth -= 1
        if holding.depth <= 0:
            del _reentrancy_state.holdings[key]
            holding.core.release()


def machine_file_lock(
    lock_path: Path,
    *,
    blocking: bool = False,
    timeout_s: float | None = None,
    reentrant: bool = False,
) -> SyncMachineFileLock:
    """Construct the canonical sync lock context manager (G6 test-double seam).

    Callers (e.g. a future ``review.verdict_commit_queue`` migration, R-04)
    should invoke this factory rather than constructing
    :class:`SyncMachineFileLock` directly: because the class is looked up
    through this module's OWN namespace at call time (not closed over at
    import time), a test can substitute the whole lock behaviour by
    monkeypatching ``kernel.locks.SyncMachineFileLock`` with a double before
    calling this factory -- the exact test-double seam
    ``review/verdict_commit_queue.py`` relies on today against the concrete
    ``filelock.FileLock`` type.
    """
    return SyncMachineFileLock(lock_path, blocking=blocking, timeout_s=timeout_s, reentrant=reentrant)
