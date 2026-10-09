"""Unit tests for the per-run-dir cursor lock helper (WP01 T003, FR-003).

Pins the two guarantees of :mod:`runtime.next.run_lock`: the lock is taken on a
DEDICATED ``state.json.lock`` sidecar (never the ``state.json`` payload — lock
guarantee G1), and a held lock blocks a second blocking acquire until released.
Deterministic: a ``threading.Event`` gates release, never a sleep.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from kernel.locks import LockAcquireTimeout, SyncMachineFileLock
from runtime.next import run_lock

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def test_lock_path_is_the_state_json_sidecar(tmp_path: Path) -> None:
    lock = run_lock.run_cursor_lock(tmp_path)
    assert isinstance(lock, SyncMachineFileLock)
    assert lock.lock_path == tmp_path / "state.json.lock"
    # G1: the lock path is NOT the payload itself.
    assert lock.lock_path != tmp_path / "state.json"


def test_held_lock_blocks_a_second_blocking_acquire_until_released(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A held lock makes a second blocking acquire time out; once released, the
    same path acquires cleanly. Deterministic via a holder thread + Event."""
    monkeypatch.setattr(run_lock, "_LOCK_TIMEOUT_S", 0.3)

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
        # Contended: a second blocking acquire with the short timeout must give up.
        with pytest.raises(LockAcquireTimeout), run_lock.run_cursor_lock(tmp_path):
            pass
    finally:
        release.set()
        holder.join(timeout=5.0)

    assert not errors, errors
    # Uncontended again: the same path now acquires without raising.
    with run_lock.run_cursor_lock(tmp_path):
        pass
