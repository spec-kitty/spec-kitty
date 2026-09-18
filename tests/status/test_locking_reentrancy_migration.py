"""Nested acquire/release depth-count regression coverage (WP05, #4714, T022).

``status/locking.py`` used to hand-roll its own ``(FileLock, depth)``
thread-local bookkeeping around ``filelock.FileLock``. Migrated onto
``kernel.locks.machine_file_lock``'s own ``reentrant=True`` mode (G5), the
OS-level re-entrancy itself now lives in ``kernel.locks``, but
``status/locking.py`` still tracks its own narrower depth counter (via
``_get_thread_locks``) to gate the holder-sidecar writes (see that module's
docstring). These tests pin, directly against the public
``feature_status_lock``/``project_event_log_lock`` surface, that:

- nested acquisition of the SAME lock path never re-attempts the OS lock
  (no deadlock, no contention) and keeps exactly the depth this module
  tracked before the migration;
- the outermost release -- and only the outermost release -- actually drops
  the OS lock and clears the holder sidecar, so a THIRD, independent
  acquirer is excluded until the outermost releases, not any inner one;
- ``_get_thread_locks()`` (the key-only membership contract many other
  test suites import by this exact name) reports the lock path held while
  ANY depth is outstanding and absent once fully released.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from specify_cli.status.locking import (
    _get_thread_locks,
    _holder_path,
    feature_status_lock,
    feature_status_lock_path,
    project_event_log_lock,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def test_nested_acquire_release_keeps_the_correct_depth_count(tmp_path: Path) -> None:
    """Three nested levels increment then decrement the tracked depth by one each."""
    lock_path = feature_status_lock_path(tmp_path, "017-test-mission")
    lock_key = str(lock_path)

    assert lock_key not in _get_thread_locks()

    with feature_status_lock(tmp_path, "017-test-mission"):
        assert _get_thread_locks()[lock_key] == 1
        with feature_status_lock(tmp_path, "017-test-mission"):
            assert _get_thread_locks()[lock_key] == 2
            with feature_status_lock(tmp_path, "017-test-mission"):
                assert _get_thread_locks()[lock_key] == 3
            assert _get_thread_locks()[lock_key] == 2
        assert _get_thread_locks()[lock_key] == 1

    assert lock_key not in _get_thread_locks()


def test_only_outermost_release_drops_the_holder_sidecar(tmp_path: Path) -> None:
    """An inner block's exit must not clear the holder record while the outer still holds it."""
    lock_path = feature_status_lock_path(tmp_path, "017-test-mission")
    holder_sidecar = _holder_path(lock_path)

    with feature_status_lock(tmp_path, "017-test-mission"):
        with feature_status_lock(tmp_path, "017-test-mission"):
            pass
        # The inner block released its nested depth, but the outer still
        # holds the lock -- the holder sidecar must still name it.
        assert holder_sidecar.exists()

    assert not holder_sidecar.exists()


def test_nested_reentry_never_blocks_or_reattempts_the_os_lock(tmp_path: Path) -> None:
    """A second thread is excluded while the depth-1 holder is inside a nested block.

    Proves the migration did not accidentally turn the "same-thread
    re-entry" fast path into a real (even if immediately-won) OS-lock
    contention retry: a nested acquire on the SAME thread must return
    instantly, while a genuinely DIFFERENT thread attempting the SAME lock
    path is still correctly excluded for as long as any depth is held.
    """
    lock_path_key = "017-nested-thread-test"
    contender_result: dict[str, bool] = {}
    contender_done = threading.Event()

    def _contender() -> None:
        from specify_cli.status.locking import FeatureStatusLockTimeoutError

        try:
            with feature_status_lock(tmp_path, lock_path_key, timeout=0.2):
                contender_result["acquired"] = True
        except FeatureStatusLockTimeoutError:
            contender_result["timed_out"] = True
        finally:
            contender_done.set()

    with feature_status_lock(tmp_path, lock_path_key), feature_status_lock(tmp_path, lock_path_key):
        thread = threading.Thread(target=_contender)
        thread.start()
        assert contender_done.wait(10), "contender thread never finished its bounded attempt"
        thread.join(timeout=10)

    assert "acquired" not in contender_result
    assert contender_result.get("timed_out") is True


def test_project_event_log_lock_shares_the_same_reentrancy_contract(tmp_path: Path) -> None:
    """``project_event_log_lock`` (the other ``_named_status_lock`` caller) is covered too.

    Same-thread nested re-entry succeeds instantly at every depth (G5,
    delegated to ``kernel.locks``), and the sidecar-holder gating mirrors
    :func:`feature_status_lock`'s (outermost acquire/release only).
    """
    project_lock_path = Path(tmp_path) / ".kittify" / "spec-kitty-locks" / "__project__.status.lock"
    holder_sidecar = _holder_path(project_lock_path)

    with project_event_log_lock(tmp_path):
        with project_event_log_lock(tmp_path):
            assert holder_sidecar.exists()
        # Still held by the outer block.
        assert holder_sidecar.exists()

    assert not holder_sidecar.exists()
