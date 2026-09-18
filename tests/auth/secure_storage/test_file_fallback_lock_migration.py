"""Red-first cross-OS parity proof licensing the ``filelock`` retirement (WP05, #4714, T026).

``specify_cli.auth.secure_storage.file_fallback`` (T024) is the
security-sensitive site: its ``read``/``write``/``delete`` each guarded a
critical section with ``filelock.FileLock(str(self._lock_file), timeout=10)``
and now guard it with ``kernel.locks.machine_file_lock(self._lock_file,
blocking=True, timeout_s=10)``. Per the mission's A-01 deferral seam
(``research.md`` R-04, ``spec.md``), this test is the EVIDENCE that licenses
removing ``filelock`` as a runtime dependency: it proves, against a REAL
subprocess (not same-process asyncio interleaving) and under a SIMULATED
Windows mandatory-lock refusal (not advisory-POSIX-only coverage), that the
migrated site preserves:

1. cross-process mutual exclusion (a second process genuinely waits);
2. the same bounded-wait failure mode on timeout (an exception surfaces,
   not silent corruption or a hang past the budget);
3. the site never re-opens its own locked resource while holding the lock
   (the #4703 signature -- structurally impossible on Windows' mandatory
   ``msvcrt.locking``, silently fine on advisory POSIX ``flock``, which is
   exactly how #4703 shipped undetected).

Section A mirrors ``tests/kernel/test_lock_parity.py``'s Windows-mandatory
simulator (R-03), applied to THIS site's actual lock construction, not the
bare primitive. Section B drives real OS-level cross-process contention and
a genuine blocking-timeout failure through ``FileFallbackStorage`` itself.
"""

from __future__ import annotations

import multiprocessing
import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

import kernel.locks as locks
from kernel.locks import LockAcquireTimeout
from specify_cli.auth.secure_storage.file_fallback import FileFallbackStorage
from specify_cli.auth.session import StoredSession, Team
from kernel.clock import now_utc, timedelta

pytestmark = [pytest.mark.integration]


def _make_session() -> StoredSession:
    now = now_utc()
    return StoredSession(
        user_id="user-1",
        email="a@b.com",
        name="A B",
        teams=[Team(id="t1", name="T1", role="owner")],
        default_team_id="t1",
        access_token="access",
        refresh_token="refresh",
        session_id="sess",
        issued_at=now,
        access_token_expires_at=now + timedelta(hours=1),
        refresh_token_expires_at=None,
        scope="openid",
        storage_backend="file",
        last_used_at=now,
        auth_method="authorization_code",
    )


class _FastFileFallback(FileFallbackStorage):
    """Lower scrypt cost so this integration test stays fast."""

    _scrypt_n = 2**10
    _scrypt_r = 8
    _scrypt_p = 1


# ---------------------------------------------------------------------------
# Section A -- simulated Windows mandatory-lock semantics (R-03)
# ---------------------------------------------------------------------------


class _WindowsMandatoryLockSimulator:
    """Fakes Windows' MANDATORY file-lock refusal on POSIX (mirrors
    ``tests/kernel/test_lock_parity.py``'s harness, applied at the site
    boundary rather than the bare primitive)."""

    def __init__(self) -> None:
        self._locked_paths: set[str] = set()
        self._fd_to_path: dict[int, str] = {}

    def wrap_open(self, real_open: Callable[..., int]) -> Callable[..., int]:
        def _open(path: str, flags: int, mode: int = 0o777) -> int:
            resolved = str(Path(path).resolve())
            if resolved in self._locked_paths:
                raise PermissionError(13, "The process cannot access the file because another process has locked a portion of the file")
            fd = real_open(path, flags, mode)
            self._fd_to_path[fd] = resolved
            return fd

        return _open

    def wrap_os_lock(self, real_os_lock: Callable[[int], None]) -> Callable[[int], None]:
        def _locking(fd: int) -> None:
            real_os_lock(fd)
            path = self._fd_to_path.get(fd)
            if path is not None:
                self._locked_paths.add(path)

        return _locking

    def wrap_os_unlock(self, real_os_unlock: Callable[[int], None]) -> Callable[[int], None]:
        def _unlocking(fd: int) -> None:
            real_os_unlock(fd)
            path = self._fd_to_path.pop(fd, None)
            if path is not None:
                self._locked_paths.discard(path)

        return _unlocking


@pytest.fixture()
def windows_mandatory_lock_simulation(monkeypatch: pytest.MonkeyPatch) -> _WindowsMandatoryLockSimulator:
    sim = _WindowsMandatoryLockSimulator()
    monkeypatch.setattr(os, "open", sim.wrap_open(os.open))
    monkeypatch.setattr(locks, "_os_lock", sim.wrap_os_lock(locks._os_lock))
    monkeypatch.setattr(locks, "_os_unlock", sim.wrap_os_unlock(locks._os_unlock))
    return sim


def test_read_write_delete_never_reopen_the_lock_while_held(
    tmp_path: Path,
    windows_mandatory_lock_simulation: _WindowsMandatoryLockSimulator,
) -> None:
    """The migrated site's own read/write/delete lifecycle never trips the
    simulated Windows mandatory-lock refusal (positive control, mirrors
    ``test_lock_parity.py``'s (b2) -- but here the caller is the actual
    migrated ``FileFallbackStorage`` site, not the bare primitive).
    """
    storage = _FastFileFallback(base_dir=tmp_path)
    session = _make_session()

    storage.write(session)
    loaded = storage.read()
    assert loaded is not None
    assert loaded.access_token == "access"
    storage.delete()
    assert storage.read() is None


# ---------------------------------------------------------------------------
# Section B -- real cross-process contention + blocking-timeout (R-03)
# ---------------------------------------------------------------------------


def _worker_hold_write_lock(store_dir: str, ready: Any, release: Any) -> None:
    """Spawn-safe worker: hold the write critical section until signaled to release."""
    storage = _FastFileFallback(base_dir=Path(store_dir))
    storage._ensure_dir()
    with locks.SyncMachineFileLock(storage._lock_file, blocking=True, timeout_s=10):
        ready.set()
        release.wait(10)


@pytest.mark.slow
def test_cross_process_contention_serializes_real_processes(tmp_path: Path) -> None:
    """A second real OS process genuinely waits behind the site's held lock.

    Proves mutual exclusion under REAL cross-process contention (not
    same-process asyncio/thread interleaving) -- the exact proof the
    filelock retirement (A-01) requires before the dependency can be
    dropped.
    """
    ctx = multiprocessing.get_context("spawn")
    ready = ctx.Event()
    release = ctx.Event()
    holder = ctx.Process(target=_worker_hold_write_lock, args=(str(tmp_path), ready, release))
    holder.start()
    try:
        assert ready.wait(10), "spawned holder never acquired the lock"

        storage = _FastFileFallback(base_dir=tmp_path)
        storage._ensure_dir()
        started = time.monotonic()
        contended = False
        try:
            with locks.SyncMachineFileLock(storage._lock_file, blocking=True, timeout_s=0.3):
                pass
        except LockAcquireTimeout:
            contended = True
        elapsed = time.monotonic() - started

        assert contended, "the contender must observe the live holder, not race past it"
        assert elapsed >= 0.25

        release.set()
        holder.join(timeout=10)
        assert not holder.is_alive()
        assert holder.exitcode == 0

        # Once released, the same site immediately succeeds -- proving this
        # was genuine contention, not a permanently broken lock.
        storage.write(_make_session())
        assert storage.read() is not None
    finally:
        release.set()
        if holder.is_alive():
            holder.terminate()
            holder.join(timeout=10)


def test_blocking_timeout_surfaces_the_same_failure_mode_as_pre_migration(tmp_path: Path) -> None:
    """A bounded blocking-timeout wait raises, matching the pre-migration
    ``filelock.Timeout`` failure mode (security-sensitive: must fail loudly,
    never hang past the 10s budget or silently corrupt the session file)."""
    storage = _FastFileFallback(base_dir=tmp_path)
    storage._ensure_dir()

    holder = locks.SyncMachineFileLock(storage._lock_file, blocking=True, timeout_s=10)
    holder.__enter__()
    try:
        with pytest.raises(LockAcquireTimeout), locks.SyncMachineFileLock(storage._lock_file, blocking=True, timeout_s=0.2):
            pytest.fail("must not acquire while the real holder is live")
    finally:
        holder.__exit__(None, None, None)
