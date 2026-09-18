"""Tests for ``kernel.locks`` -- the canonical cross-OS lock primitive.

Migrated (mission ``cross-os-primitive-unification``, WP03) from
``tests/core/test_file_lock.py`` + ``tests/core/test_file_lock_behavior.py``
verbatim in intent (the pre-move ``specify_cli.core.file_lock.MachineFileLock``
suite), with the import surface repointed to ``kernel.locks`` and coverage
added for the new sync facade (:class:`kernel.locks.SyncMachineFileLock`),
``blocking``/``timeout_s`` wait modes, re-entrancy (G5), and the test-double
injection seam (G6). The old ``tests/core/test_file_lock*.py`` files were
deleted rather than left as dead surface for a retired module (canonical-
source discipline) -- ``specify_cli.core.file_lock`` no longer exists.

The pure cross-OS PARITY proofs (structural read-safety, simulated-Windows-
mandatory-lock refusal, cross-process contention, release-truncates) live in
the sibling ``tests/kernel/test_lock_parity.py`` (T014) -- this module covers
the primitive's own async/sync behavior contract.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

import kernel.locks as locks
from kernel.clock import now_utc, now_utc_iso, timedelta
from kernel.locks import (
    LockAcquireTimeout,
    LockNotAcquired,
    LockRecord,
    MachineFileLock,
    SyncMachineFileLock,
    force_release,
    machine_file_lock,
    read_lock_record,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]


@pytest.fixture()
def lock_path(tmp_path: Path) -> Path:
    return tmp_path / "subdir" / "refresh.lock"


def _write_record(path: Path, *, age_s: float = 0.0, pid: int | None = None) -> None:
    """Write a synthetic lock record to ``path`` with ``age_s`` seconds in the past."""
    started = now_utc() - timedelta(seconds=age_s)
    payload: dict[str, Any] = {
        "schema_version": 1,
        "pid": pid if pid is not None else os.getpid(),
        "started_at": started.isoformat(),
        "host": "test-host",
        "version": "test",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True))


# ---------------------------------------------------------------------------
# Async facade (MachineFileLock) -- ported behaviour, verbatim contract
# ---------------------------------------------------------------------------


async def test_acquire_and_release(lock_path: Path) -> None:
    async with MachineFileLock(lock_path, acquire_timeout_s=2.0) as record:
        assert isinstance(record, LockRecord)
        assert record.pid == os.getpid()
        assert record.schema_version == 1
        on_disk = read_lock_record(lock_path)
        assert on_disk is not None
        assert on_disk.pid == os.getpid()

    # After the context exits the lock file is truncated and the record gone.
    assert read_lock_record(lock_path) is None


async def test_acquire_creates_parent_directory(tmp_path: Path) -> None:
    lock_path = tmp_path / "a" / "b" / "c" / "test.lock"

    async with MachineFileLock(lock_path, acquire_timeout_s=2.0):
        assert lock_path.parent.exists()


async def test_concurrent_acquire_serialized(lock_path: Path) -> None:
    sequence: list[str] = []

    async def hold(label: str, dwell_s: float) -> None:
        async with MachineFileLock(lock_path, acquire_timeout_s=5.0):
            sequence.append(f"enter-{label}")
            await asyncio.sleep(dwell_s)
            sequence.append(f"exit-{label}")

    a = asyncio.create_task(hold("a", 0.2))
    await asyncio.sleep(0.05)
    b = asyncio.create_task(hold("b", 0.05))
    await asyncio.gather(a, b)

    assert sequence == ["enter-a", "exit-a", "enter-b", "exit-b"]


async def test_acquire_timeout_raises(lock_path: Path) -> None:
    holder = MachineFileLock(lock_path, acquire_timeout_s=2.0)
    await holder.__aenter__()
    try:
        contender = MachineFileLock(lock_path, acquire_timeout_s=0.3)
        with pytest.raises(LockAcquireTimeout) as info:
            await contender.__aenter__()
        assert str(lock_path) in info.value.path
    finally:
        await holder.__aexit__(None, None, None)


async def test_timeout_error_exposes_path_attribute(lock_path: Path) -> None:
    holder = MachineFileLock(lock_path, acquire_timeout_s=5.0)
    await holder.__aenter__()
    try:
        exc: LockAcquireTimeout | None = None
        try:
            async with MachineFileLock(lock_path, acquire_timeout_s=0.05):
                pass
        except LockAcquireTimeout as e:
            exc = e
        assert exc is not None
        assert exc.path == str(lock_path)
    finally:
        await holder.__aexit__(None, None, None)


async def test_stale_lock_adopted(lock_path: Path) -> None:
    _write_record(lock_path, age_s=120.0, pid=999_999)
    assert read_lock_record(lock_path) is not None

    async with MachineFileLock(lock_path, acquire_timeout_s=1.0, stale_after_s=60.0) as record:
        assert record.pid == os.getpid()
        on_disk = read_lock_record(lock_path)
        assert on_disk is not None
        assert on_disk.pid == os.getpid()


async def test_stale_record_with_live_holder_does_not_admit_second_lock(lock_path: Path) -> None:
    holder = MachineFileLock(lock_path, acquire_timeout_s=1.0)
    await holder.__aenter__()
    contender = MachineFileLock(lock_path, acquire_timeout_s=0.15, stale_after_s=0.0)
    try:
        _write_record(lock_path, age_s=120.0, pid=999_999)
        with pytest.raises(LockAcquireTimeout):
            await contender.__aenter__()
    finally:
        await contender.__aexit__(None, None, None)
        await holder.__aexit__(None, None, None)


def test_force_release_missing_returns_false(lock_path: Path) -> None:
    assert force_release(lock_path, only_if_age_s=60.0) is False


def test_force_release_only_when_stuck(lock_path: Path) -> None:
    _write_record(lock_path, age_s=5.0)
    assert force_release(lock_path, only_if_age_s=60.0) is False
    assert lock_path.exists()

    _write_record(lock_path, age_s=120.0)
    assert force_release(lock_path, only_if_age_s=60.0) is True
    assert read_lock_record(lock_path) is None


async def test_force_release_does_not_unlink_when_stale_lock_is_held(lock_path: Path) -> None:
    holder = MachineFileLock(lock_path, acquire_timeout_s=1.0)
    await holder.__aenter__()
    try:
        _write_record(lock_path, age_s=120.0, pid=999_999)
        assert force_release(lock_path, only_if_age_s=60.0) is False
        assert read_lock_record(lock_path) is not None
    finally:
        await holder.__aexit__(None, None, None)


async def test_atomic_content_write_failure_leaves_no_partial(lock_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _exploding_write(fd: int, payload: bytes) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(locks, "_atomic_write_under_lock", _exploding_write)

    with pytest.raises(OSError, match="disk full"):
        async with MachineFileLock(lock_path, acquire_timeout_s=1.0):
            pytest.fail("body should not run when content write fails")  # pragma: no cover

    assert read_lock_record(lock_path) is None

    monkeypatch.undo()
    async with MachineFileLock(lock_path, acquire_timeout_s=1.0) as record:
        assert record.pid == os.getpid()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX-only path uses fcntl")
def test_platform_dispatch_posix() -> None:
    import fcntl  # noqa: F401  - presence assertion

    assert hasattr(fcntl, "flock")
    assert hasattr(fcntl, "LOCK_EX")
    assert hasattr(fcntl, "LOCK_NB")
    assert hasattr(fcntl, "LOCK_UN")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only path uses msvcrt")
def test_platform_dispatch_windows(tmp_path: Path) -> None:  # pragma: no cover - exercised on win32 CI only
    import msvcrt  # type: ignore[import-not-found]

    assert hasattr(msvcrt, "locking")
    path = tmp_path / "win.lock"

    async def _smoke() -> None:
        async with MachineFileLock(path, acquire_timeout_s=2.0) as record:
            assert record.pid == os.getpid()

    asyncio.run(_smoke())


def test_read_lock_record_rejects_corrupt_json(lock_path: Path) -> None:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text("not-json{")
    assert read_lock_record(lock_path) is None


def test_read_lock_record_rejects_missing_keys(lock_path: Path) -> None:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(json.dumps({"schema_version": 1, "pid": 1}))
    assert read_lock_record(lock_path) is None


def test_read_lock_record_rejects_bad_started_at(lock_path: Path) -> None:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "pid": 42,
                "started_at": "not-a-timestamp",
                "host": "h",
                "version": "v",
            }
        )
    )
    assert read_lock_record(lock_path) is None


def test_lock_record_age_and_is_stuck() -> None:
    fresh = LockRecord(schema_version=1, pid=1, started_at=now_utc(), host="h", version="v")
    assert fresh.age_s < 5.0
    assert fresh.is_stuck(60.0) is False

    stale = LockRecord(schema_version=1, pid=1, started_at=now_utc() - timedelta(seconds=120), host="h", version="v")
    assert stale.age_s > 60.0
    assert stale.is_stuck(60.0) is True


def test_read_lock_record_non_dict_returns_none(lock_path: Path) -> None:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(json.dumps([1, 2, 3]))
    assert read_lock_record(lock_path) is None


def test_read_lock_record_non_string_fields_returns_none(lock_path: Path) -> None:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "pid": 1,
                "started_at": now_utc_iso(),
                "host": 12345,  # wrong type
                "version": "v",
            }
        )
    )
    assert read_lock_record(lock_path) is None


def test_force_release_clear_failure(lock_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_record(lock_path, age_s=120.0)

    def _boom(_fd: int, _payload: bytes) -> None:
        raise OSError("permission denied")

    monkeypatch.setattr(locks, "_atomic_write_under_lock", _boom)
    assert force_release(lock_path, only_if_age_s=60.0) is False


def test_force_release_propagates_genuine_os_lock_error(lock_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_record(lock_path, age_s=120.0)

    genuine = OSError("input/output error")
    genuine.errno = 5  # EIO -- a genuine I/O error, never contention

    def _boom(_fd: int) -> None:
        raise genuine

    monkeypatch.setattr(locks, "_os_lock", _boom)
    with pytest.raises(OSError) as excinfo:
        force_release(lock_path, only_if_age_s=60.0)
    assert excinfo.value.errno == 5


def test_is_contention_error_distinguishes_genuine_io() -> None:
    assert locks._is_contention_error(OSError()) is False
    err = OSError()
    err.errno = 28  # ENOSPC
    assert locks._is_contention_error(err) is False
    err.errno = 13  # EACCES
    assert locks._is_contention_error(err) is True


async def test_aexit_is_idempotent_when_no_fd_held(lock_path: Path) -> None:
    lock = MachineFileLock(lock_path)
    await lock.__aexit__(None, None, None)


async def test_acquire_propagates_non_contention_oserror(lock_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(fd: int) -> None:
        err = OSError("disk full")
        err.errno = 28  # ENOSPC
        raise err

    monkeypatch.setattr(locks, "_os_lock", _boom)
    with pytest.raises(OSError, match="disk full"):
        async with MachineFileLock(lock_path, acquire_timeout_s=0.5):
            pytest.fail("body should not run")  # pragma: no cover


def test_get_package_version_falls_back_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def _missing(_name: str) -> str:
        raise locks.importlib_metadata.PackageNotFoundError("spec-kitty-cli")

    monkeypatch.setattr(locks.importlib_metadata, "version", _missing)
    assert locks._get_package_version() == "unknown"


def test_read_lock_record_handles_oserror(lock_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(json.dumps({"schema_version": 1, "pid": 1, "started_at": "x", "host": "h", "version": "v"}))

    def _boom(self: Path) -> bytes:
        raise PermissionError("denied")

    monkeypatch.setattr(Path, "read_bytes", _boom)
    assert read_lock_record(lock_path) is None


def test_read_lock_record_accepts_naive_timestamp(lock_path: Path) -> None:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    naive = now_utc().replace(tzinfo=None)
    lock_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "pid": 1,
                "started_at": naive.isoformat(),
                "host": "h",
                "version": "v",
            }
        )
    )
    record = read_lock_record(lock_path)
    assert record is not None
    assert record.started_at.tzinfo is not None


async def test_fd_is_closed_on_non_contention_error(lock_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression: a genuine OSError from ``_os_lock`` must still close the fd.

    Caught during T010 implementation: an early draft's ``_attempt_acquire``
    let a non-contention ``OSError`` propagate out of ``try_lock_once``
    *before* closing the just-opened fd, leaking it. ``os.close`` is
    monkeypatched to record every fd it is asked to close; the boomed fd
    must appear in that list even though the whole acquire ultimately raises.
    """
    closed: list[int] = []
    real_close = os.close

    def _tracking_close(fd: int) -> None:
        closed.append(fd)
        real_close(fd)

    def _boom(fd: int) -> None:
        err = OSError("disk full")
        err.errno = 28  # ENOSPC
        raise err

    monkeypatch.setattr(locks, "_os_lock", _boom)
    monkeypatch.setattr(locks.os, "close", _tracking_close)

    with pytest.raises(OSError, match="disk full"):
        async with MachineFileLock(lock_path, acquire_timeout_s=0.5):
            pytest.fail("body should not run")  # pragma: no cover

    assert len(closed) == 1


# ---------------------------------------------------------------------------
# Sync facade (SyncMachineFileLock / machine_file_lock) -- G4
# ---------------------------------------------------------------------------


def test_sync_lock_acquire_and_release(lock_path: Path) -> None:
    with SyncMachineFileLock(lock_path) as record:
        assert isinstance(record, LockRecord)
        assert record.pid == os.getpid()
        assert read_lock_record(lock_path) is not None

    assert read_lock_record(lock_path) is None


def test_sync_lock_default_is_non_blocking(lock_path: Path) -> None:
    """Default ``blocking=False``: contention raises immediately, never retries."""
    holder = SyncMachineFileLock(lock_path)
    holder.__enter__()
    try:
        contender = SyncMachineFileLock(lock_path)
        started = time.monotonic()
        with pytest.raises(LockNotAcquired) as info:
            contender.__enter__()
        elapsed = time.monotonic() - started
        assert str(lock_path) in info.value.path
        # A single non-blocking attempt must not spend a retry-loop sleep.
        assert elapsed < locks._RETRY_SLEEP_S
    finally:
        holder.__exit__(None, None, None)


def test_sync_lock_blocking_with_timeout_raises(lock_path: Path) -> None:
    holder = SyncMachineFileLock(lock_path)
    holder.__enter__()
    try:
        contender = SyncMachineFileLock(lock_path, blocking=True, timeout_s=0.2)
        with pytest.raises(LockAcquireTimeout):
            contender.__enter__()
    finally:
        holder.__exit__(None, None, None)


def test_sync_lock_blocking_waits_for_release(lock_path: Path) -> None:
    """``blocking=True`` with a generous timeout acquires once the holder releases."""
    holder = SyncMachineFileLock(lock_path)
    holder.__enter__()

    def _release_shortly() -> None:
        time.sleep(0.1)
        holder.__exit__(None, None, None)

    releaser = threading.Thread(target=_release_shortly)
    releaser.start()
    try:
        with SyncMachineFileLock(lock_path, blocking=True, timeout_s=5.0) as record:
            assert record.pid == os.getpid()
    finally:
        releaser.join(timeout=5)


def test_sync_lock_rejects_timeout_without_blocking(lock_path: Path) -> None:
    lock = SyncMachineFileLock(lock_path, blocking=False, timeout_s=1.0)
    with pytest.raises(ValueError, match="blocking=True"):
        lock.__enter__()


def test_sync_lock_reentrant_same_thread_nests(lock_path: Path) -> None:
    """G5: the same thread may re-enter a ``reentrant=True`` lock without deadlocking."""
    outer = SyncMachineFileLock(lock_path, reentrant=True)
    outer_record = outer.__enter__()
    try:
        inner = SyncMachineFileLock(lock_path, reentrant=True)
        inner_record = inner.__enter__()
        try:
            # Same underlying holding is returned, not a fresh acquire.
            assert inner_record == outer_record
            # A non-reentrant contender from a different "identity" (this
            # process) still could not acquire OS-level; but that is a
            # deliberately not exercised here -- the reentrancy holding
            # never actually calls the OS lock twice, which this asserts by
            # construction: the second __enter__ returned without deadlock.
        finally:
            inner.__exit__(None, None, None)
        # After the inner exit, the outer still holds -- record still on disk.
        assert read_lock_record(lock_path) is not None
    finally:
        outer.__exit__(None, None, None)

    # Only the outermost exit actually releases.
    assert read_lock_record(lock_path) is None


def test_sync_lock_reentrant_only_releases_at_depth_zero(lock_path: Path) -> None:
    lock_a = SyncMachineFileLock(lock_path, reentrant=True)
    lock_b = SyncMachineFileLock(lock_path, reentrant=True)
    lock_a.__enter__()
    lock_b.__enter__()

    lock_a.__exit__(None, None, None)
    # Still held -- lock_b's depth has not been released yet.
    assert read_lock_record(lock_path) is not None

    lock_b.__exit__(None, None, None)
    assert read_lock_record(lock_path) is None


def test_sync_lock_reentrant_across_threads_is_ordinary_contention(lock_path: Path) -> None:
    """G5 boundary: re-entrancy is per-thread; a different thread still contends."""
    holder = SyncMachineFileLock(lock_path, reentrant=True)
    holder.__enter__()
    try:
        outcomes: list[str] = []

        def _try_from_other_thread() -> None:
            contender = SyncMachineFileLock(lock_path, reentrant=True)
            try:
                contender.__enter__()
                outcomes.append("acquired")
                contender.__exit__(None, None, None)
            except LockNotAcquired:
                outcomes.append("contended")

        thread = threading.Thread(target=_try_from_other_thread)
        thread.start()
        thread.join(timeout=5)

        assert outcomes == ["contended"]
    finally:
        holder.__exit__(None, None, None)


def test_machine_file_lock_factory_constructs_sync_lock(lock_path: Path) -> None:
    lock = machine_file_lock(lock_path)
    assert isinstance(lock, SyncMachineFileLock)
    with lock as record:
        assert isinstance(record, LockRecord)


def test_machine_file_lock_factory_forwards_kwargs(lock_path: Path) -> None:
    lock = machine_file_lock(lock_path, blocking=True, timeout_s=1.5, reentrant=True)
    assert lock.blocking is True
    assert lock.timeout_s == 1.5
    assert lock.reentrant is True


def test_machine_file_lock_injection_seam_is_patchable(lock_path: Path) -> None:
    """G6: a test double substituted at ``kernel.locks.SyncMachineFileLock`` is
    what ``machine_file_lock`` constructs -- because the factory resolves the
    class through the module's own namespace at call time (not a bound local
    captured at import time), monkeypatching the module attribute is enough.
    This is the seam a future ``review.verdict_commit_queue`` migration (R-04)
    relies on to keep its existing test-double pattern working.
    """

    @dataclass
    class _FakeLockRecord:
        pid: int = -1

    class _FakeLock:
        def __init__(self, lock_path: Path, **_kwargs: object) -> None:
            self.lock_path = lock_path
            self.entered = False

        def __enter__(self) -> _FakeLockRecord:
            self.entered = True
            return _FakeLockRecord()

        def __exit__(self, *_exc: object) -> None:
            self.entered = False

    original = locks.SyncMachineFileLock
    locks.SyncMachineFileLock = _FakeLock  # type: ignore[assignment,misc]
    try:
        built = machine_file_lock(lock_path)
        assert isinstance(built, _FakeLock)
        with built as record:
            assert isinstance(record, _FakeLockRecord)
    finally:
        locks.SyncMachineFileLock = original  # type: ignore[misc]
