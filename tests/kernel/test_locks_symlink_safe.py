"""Symlink-plant regression for the canonical lock primitive (#4756, FR-001/FR-003).

``kernel.locks._LockCore.open_fd`` opens the caller-supplied ``lock_path`` with
``os.O_RDWR | os.O_CREAT`` and no ``O_NOFOLLOW``. A planted symlink at that
path is followed, and ``_LockCore.commit_record``/``release`` then write and
truncate the *followed* inode -- silently corrupting whatever file the
attacker pointed the link at. This module proves both halves of the fix:
the victim's bytes survive untouched, and the acquire attempt raises
``kernel.no_follow.NoFollowPathError`` rather than succeeding (SC-001).

The isolated per-worker ``HOME``/``SPEC_KITTY_HOME`` is applied automatically
by the autouse fixtures in ``tests/conftest.py`` -- this module never reads or
writes the real ``~/.spec-kitty``; ``lock_path``/``victim_path`` below are
rooted at ``tmp_path`` regardless.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kernel.locks import LockAcquireTimeout, LockNotAcquired, SyncMachineFileLock, force_release
from kernel.no_follow import NoFollowPathError

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_VICTIM_BYTES = b"do not disclose -- attacker-chosen victim content\n"


@pytest.fixture()
def victim_path(tmp_path: Path) -> Path:
    """A file elsewhere on disk the attacker wants truncated/overwritten."""
    victim = tmp_path / "victim-secret.txt"
    victim.write_bytes(_VICTIM_BYTES)
    return victim


@pytest.fixture()
def planted_lock_path(tmp_path: Path, victim_path: Path) -> Path:
    """A lock path the attacker has pre-planted as a symlink to ``victim_path``.

    Mirrors the real attack shape: the caller computes a lock path (e.g. under
    a predictable coordination directory) and the attacker races to swap that
    path for a symlink before the lock is acquired.
    """
    lock_path = tmp_path / "subdir" / "refresh.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.symlink_to(victim_path)
    return lock_path


def test_sync_lock_acquire_on_planted_symlink_leaves_victim_untouched_and_raises(planted_lock_path: Path, victim_path: Path) -> None:
    """Acquiring a lock at a symlinked path must refuse, not follow-and-truncate.

    Before the fix: ``SyncMachineFileLock.__enter__`` follows the symlink,
    takes the OS lock on the victim inode, and ``commit_record`` overwrites it
    with a serialized ``LockRecord`` -- exit code 0, victim silently
    destroyed. After the fix: the open itself refuses the final-component
    symlink and raises ``NoFollowPathError`` before any write happens.
    """
    with pytest.raises(NoFollowPathError), SyncMachineFileLock(planted_lock_path):
        pytest.fail("lock acquisition must not succeed against a symlinked lock path")

    assert victim_path.read_bytes() == _VICTIM_BYTES, "victim file must be byte-for-byte unchanged"


def test_sync_lock_acquire_on_planted_symlink_does_not_raise_lock_contention_errors(
    planted_lock_path: Path,
) -> None:
    """The refusal must be the no-follow signal, not a masquerading lock-contention error.

    A caller catching only ``LockNotAcquired``/``LockAcquireTimeout`` (the
    ordinary contention exceptions) must NOT accidentally swallow the
    symlink-refusal as if it were routine contention.
    """
    with pytest.raises(NoFollowPathError) as exc_info, SyncMachineFileLock(planted_lock_path):
        pass

    assert not isinstance(exc_info.value, (LockNotAcquired, LockAcquireTimeout))


def test_force_release_on_planted_symlink_leaves_victim_untouched(planted_lock_path: Path, victim_path: Path) -> None:
    """``force_release``'s raw ``os.open`` must not follow a planted symlink either.

    ``force_release`` reads the record via ``read_lock_record`` first; against
    a symlink pointing at a file with no valid ``LockRecord`` payload, that
    read returns ``None`` and ``force_release`` reports ``False`` without
    reaching its own ``os.open`` -- the real risk. Exercise the ``os.open``
    call directly by planting a *valid, stale* record at the victim so
    ``read_lock_record`` succeeds and ``force_release`` proceeds to open the
    (symlinked) path itself.
    """
    from kernel.locks import LockRecord, STALE_AFTER_S_DEFAULT, _record_to_json
    from kernel.clock import now_utc, timedelta

    stale_record = LockRecord(
        schema_version=1,
        pid=999999,
        started_at=now_utc() - timedelta(seconds=STALE_AFTER_S_DEFAULT + 60),
        host="stale-host",
        version="0.0.0",
    )
    victim_path.write_bytes(_record_to_json(stale_record).encode("utf-8"))

    with pytest.raises(NoFollowPathError):
        force_release(planted_lock_path)

    assert victim_path.read_bytes() == _record_to_json(stale_record).encode("utf-8")
