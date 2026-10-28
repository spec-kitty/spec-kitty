"""The non-blocking run-cursor lock used by local event-log retention (#6610).

:func:`runtime.next.run_lock.try_run_cursor_lock` takes the same
``state.json.lock`` sidecar as the blocking :func:`run_cursor_lock`, but makes
one attempt only: retention cleanup deletes a run directory while it holds that
lock, and reports the run as kept when an advance holds it. Deterministic: a
``threading.Event`` gates the holder, never a sleep.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from kernel.locks import LockNotAcquired, SyncMachineFileLock
from runtime.next import run_lock

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def test_try_lock_targets_the_run_cursor_sidecar(tmp_path: Path) -> None:
    lock = run_lock.try_run_cursor_lock(tmp_path)
    assert isinstance(lock, SyncMachineFileLock)
    assert lock.lock_path == run_lock.run_cursor_lock(tmp_path).lock_path
    assert lock.blocking is False


def test_try_lock_acquires_a_free_run_dir(tmp_path: Path) -> None:
    with run_lock.try_run_cursor_lock(tmp_path) as record:
        assert record is not None
    # Released: a second attempt acquires again.
    with run_lock.try_run_cursor_lock(tmp_path):
        pass


def test_try_lock_refuses_at_once_while_the_run_cursor_lock_is_held(tmp_path: Path) -> None:
    holding = threading.Event()
    release = threading.Event()
    errors: list[BaseException] = []

    def _hold() -> None:
        try:
            with run_lock.run_cursor_lock(tmp_path):
                holding.set()
                release.wait(timeout=5.0)
        except BaseException as exc:  # pragma: no cover - surfaced via errors
            errors.append(exc)
            holding.set()

    holder = threading.Thread(target=_hold)
    holder.start()
    try:
        assert holding.wait(timeout=5.0), "holder never acquired the lock"
        with pytest.raises(LockNotAcquired), run_lock.try_run_cursor_lock(tmp_path):
            pass  # pragma: no cover - the enter must raise
    finally:
        release.set()
        holder.join(timeout=5.0)

    assert not errors, errors
    with run_lock.try_run_cursor_lock(tmp_path):
        pass
