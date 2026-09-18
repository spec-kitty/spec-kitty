"""Focused unit coverage for the shared ``checkout_file_lock`` primitive (#3773 item 4).

``specify_cli.review.verdict_commit_queue`` and ``specify_cli.status.locking``
each build a ``kernel.locks`` machine-file lock under
``<git-common-dir>/spec-kitty-locks/`` and translate a bounded-wait timeout
into their own typed exception. This module is the single place that
enter/translate sequence now lives; these tests exercise it directly,
independent of either caller's git-topology resolution or re-entrancy
bookkeeping (which stay in each caller by design -- see the module
docstring).

Migrated (mission cross-os-primitive-unification WP05/#4714) off
``filelock.FileLock`` onto ``kernel.locks.machine_file_lock`` -- the
canonical primitive's G6 test-double injection seam.
"""

from __future__ import annotations

import multiprocessing
from pathlib import Path
from typing import Any

import pytest

from kernel.locks import LockAcquireTimeout, LockRecord, machine_file_lock
from specify_cli.core.checkout_file_lock import LOCK_DIRECTORY, acquire_or_raise


class _CustomTimeoutError(RuntimeError):
    """A stand-in for a caller's own typed timeout exception."""


@pytest.mark.unit
@pytest.mark.fast
def test_lock_directory_is_the_single_named_constant() -> None:
    """The literal both callers used to hardcode now lives in exactly one place."""
    assert LOCK_DIRECTORY == "spec-kitty-locks"


@pytest.mark.unit
@pytest.mark.fast
def test_acquire_or_raise_creates_parent_directory_and_acquires(tmp_path: Path) -> None:
    """A fresh, nested lock path gets its parent directory created and locked."""
    lock_path = tmp_path / "nested" / "checkout" / "example.lock"
    lock = machine_file_lock(lock_path, blocking=True, timeout_s=1.0)

    record = acquire_or_raise(
        lock,
        build_timeout_error=lambda: pytest.fail("must not time out against an unheld lock"),
    )
    try:
        assert lock_path.parent.is_dir()
        assert isinstance(record, LockRecord)
    finally:
        lock.__exit__(None, None, None)


@pytest.mark.unit
@pytest.mark.fast
def test_acquire_or_raise_raises_callers_typed_error_on_timeout(tmp_path: Path) -> None:
    """A live holder excludes a contender past its budget with the CALLER's exception type."""
    lock_path = tmp_path / LOCK_DIRECTORY / "contended.lock"
    holder = machine_file_lock(lock_path, blocking=True, timeout_s=5.0)
    holder.__enter__()
    try:
        contender = machine_file_lock(lock_path, blocking=True, timeout_s=0.2)

        with pytest.raises(_CustomTimeoutError) as raised:
            acquire_or_raise(
                contender,
                build_timeout_error=lambda: _CustomTimeoutError("busy"),
            )

        # The typed exception is chained from the underlying
        # kernel.locks.LockAcquireTimeout, so a caller's own diagnostics can
        # still inspect the real cause.
        assert isinstance(raised.value.__cause__, LockAcquireTimeout)
    finally:
        holder.__exit__(None, None, None)


@pytest.mark.unit
@pytest.mark.fast
def test_acquire_or_raise_does_not_release_a_lock_it_never_acquired(tmp_path: Path) -> None:
    """On a failed acquire, the helper must not touch ``__exit__`` at all.

    Mirrors the contract ``verdict_commit_queue``'s own test suite pins for
    its call site: a lock that was never successfully entered must not be
    released by this primitive -- that would be a caller bug (or, at the OS
    level, drop someone else's lock).
    """
    lock_path = tmp_path / LOCK_DIRECTORY / "refused.lock"

    class _RefusingLock:
        def __enter__(self) -> object:
            raise LockAcquireTimeout(path=str(lock_path))

        def __exit__(self, *_exc: object) -> None:
            pytest.fail("a lock that was never entered must not be released")

    with pytest.raises(_CustomTimeoutError):
        acquire_or_raise(
            _RefusingLock(),  # type: ignore[arg-type]  # duck-typed SyncMachineFileLock double
            build_timeout_error=lambda: _CustomTimeoutError("refused"),
        )


@pytest.mark.unit
@pytest.mark.fast
def test_acquire_or_raise_is_reusable_across_two_independent_lock_files(tmp_path: Path) -> None:
    """The shared helper has no hidden global state.

    Two distinct lock paths -- as two independent callers, each with their own
    lock filename, would use -- acquire independently without interfering with
    each other.
    """
    lock_path_a = tmp_path / LOCK_DIRECTORY / "caller-a.lock"
    lock_path_b = tmp_path / LOCK_DIRECTORY / "caller-b.lock"
    lock_a = machine_file_lock(lock_path_a, blocking=True, timeout_s=1.0)
    lock_b = machine_file_lock(lock_path_b, blocking=True, timeout_s=1.0)

    record_a = acquire_or_raise(lock_a, build_timeout_error=AssertionError)
    record_b = acquire_or_raise(lock_b, build_timeout_error=AssertionError)
    try:
        assert isinstance(record_a, LockRecord)
        assert isinstance(record_b, LockRecord)
    finally:
        lock_a.__exit__(None, None, None)
        lock_b.__exit__(None, None, None)


def _hold_then_release_on_signal(lock_path_str: str, ready: Any, release: Any) -> None:
    """Spawn-safe worker: acquire ``lock_path_str``, signal readiness, then
    release once the parent sets ``release``.

    A real second OS process is required here (not a background thread in
    this same process): cross-process contention has no thread-local
    release-from-wrong-thread gotcha -- the OS-level ``flock``/``msvcrt``
    lock genuinely serializes independent processes.
    """
    lock = machine_file_lock(Path(lock_path_str), blocking=True, timeout_s=5.0)
    lock.__enter__()
    ready.set()
    release.wait(10)
    lock.__exit__(None, None, None)


@pytest.mark.integration
def test_acquire_or_raise_bounded_wait_unblocks_promptly_after_release(tmp_path: Path) -> None:
    """A contender queued behind a live holder acquires as soon as it releases.

    Proves this is a real bounded WAIT (not an immediate refusal): the
    contender's ``acquire_or_raise`` call blocks until the release, well
    inside its own timeout budget. Uses a real spawned process as the holder
    (see ``_hold_then_release_on_signal``'s docstring for why a thread will
    not do).
    """
    lock_path = tmp_path / LOCK_DIRECTORY / "handoff.lock"
    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    release = context.Event()
    holder = context.Process(target=_hold_then_release_on_signal, args=(str(lock_path), ready, release))
    holder.start()
    try:
        assert ready.wait(10), "spawned holder never acquired the lock"

        contender = machine_file_lock(lock_path, blocking=True, timeout_s=5.0)
        release.set()
        record = acquire_or_raise(
            contender,
            build_timeout_error=lambda: pytest.fail("must acquire once the holder releases"),
        )
        try:
            assert isinstance(record, LockRecord)
        finally:
            contender.__exit__(None, None, None)
        holder.join(timeout=10)
        assert not holder.is_alive()
        assert holder.exitcode == 0
    finally:
        release.set()
        if holder.is_alive():
            holder.terminate()
            holder.join(timeout=10)
