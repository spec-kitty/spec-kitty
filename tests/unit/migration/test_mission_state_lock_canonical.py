"""``migration/mission_state.py`` lock canonicalization (#4811, WP05, T017/T018).

The hand-rolled ``_git_lock`` used ``os.open(O_CREAT | O_EXCL | O_WRONLY)`` --
a latent FR-010 lock-primitive-ban instance with no ``O_NOFOLLOW`` guard. T017
routes it through the canonical ``kernel.locks.machine_file_lock`` (WP01's
``O_NOFOLLOW``-hardened primitive) instead. This module is the isolated-HOME
evidence for that migration:

- ``test_lock_is_acquired_through_machine_file_lock_factory`` -- the lock
  construction routes through ``kernel.locks.machine_file_lock`` (the
  canonical door), not a raw ``os.open``.
- ``test_lock_refuses_symlink_at_lock_path_and_preserves_victim_bytes`` --
  SC-001: a symlink planted at the resolved lock path is refused via the
  canonical primitive's ``O_NOFOLLOW`` guard (``NoFollowPathError``/
  ``OSError``), never followed, and the victim file's bytes are untouched.
  RED-FIRST FINDING (empirically verified, see below): against the pre-T017
  hand-rolled predecessor this test is ALSO red, but not for the "bytes
  corrupted" reason a naive symlink-attack narrative would predict --
  ``O_EXCL`` independently refuses any pre-existing path component (symlink
  or not) with ``EEXIST`` per POSIX, *by accident* of that flag combination,
  before ever following it. So the predecessor also never corrupts the
  victim -- it fails this test instead on **exception identity**: it raises
  ``MissionStateRepairError`` (its generic "another repair running" path),
  not ``NoFollowPathError``/``OSError``, so ``pytest.raises`` here does not
  match and the assertion never reaches the byte-preservation check. The
  real, generalizable property this test pins is the canonical primitive's
  *designed* ``O_NOFOLLOW`` refusal -- not an incidental side effect of a
  flag combination that would NOT protect a truncate-and-reuse primitive
  (like ``machine_file_lock`` itself, and unlike the retired exclusive-create
  shape) opened without it.
- ``test_lock_semantics_parity_with_hand_rolled_predecessor`` -- the explicit
  lock-semantics PARITY test the WP calls for: a second concurrent acquirer
  is refused immediately (not blocked), and the lock is scope-bound /
  non-re-entrant across *sequential* (non-nested) uses, exactly like the
  hand-rolled ``os.open(O_EXCL)`` predecessor.

**Reproducing the RED-FIRST run**: checking out the pre-T017 revision of
``src/specify_cli/migration/mission_state.py`` and running
``test_lock_refuses_symlink_at_lock_path_and_preserves_victim_bytes`` and
``test_lock_is_acquired_through_machine_file_lock_factory`` fails (3 of 4
tests in this module go red; see the finding above for the precise cause of
each). The PR's "Tests run" section records this failing-before /
passing-after pair.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from kernel.locks import LockNotAcquired
from kernel.locks import machine_file_lock as _real_machine_file_lock
from kernel.no_follow import NoFollowPathError
from specify_cli.migration.mission_state import MissionStateRepairError, _git_lock

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]


def _init_git_repo(repo: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "lock-test@spec-kitty.test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "lock test"], cwd=repo, check=True)


def test_lock_is_acquired_through_machine_file_lock_factory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``_git_lock`` constructs its lock via ``kernel.locks.machine_file_lock`` (the door).

    Monkeypatches the factory as imported into ``mission_state`` and asserts
    it is called with the resolved ``.git/spec-kitty-mission-state.lock``
    path and a single non-blocking attempt (``blocking=False``) -- proving
    the canonical primitive is actually reached, not merely importable.
    """
    _init_git_repo(tmp_path)

    calls: list[tuple[Path, bool]] = []

    def _spy(lock_path: Path, *, blocking: bool = False, **kwargs: object) -> object:
        calls.append((lock_path, blocking))
        return _real_machine_file_lock(lock_path, blocking=blocking, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr("specify_cli.migration.mission_state.machine_file_lock", _spy)

    with _git_lock(tmp_path):
        pass

    assert len(calls) == 1
    lock_path, blocking = calls[0]
    assert lock_path == tmp_path / ".git" / "spec-kitty-mission-state.lock"
    assert blocking is False


def test_lock_refuses_symlink_at_lock_path_and_preserves_victim_bytes(tmp_path: Path) -> None:
    """SC-001: a symlink planted at the lock path is refused, never followed.

    Pins the canonical primitive's ``O_NOFOLLOW`` guard at this call site:
    the acquire must raise a *specific* no-follow refusal
    (``NoFollowPathError``/``OSError``), and the victim's original bytes must
    be byte-for-byte intact afterward. See the module docstring's RED-FIRST
    FINDING for why this is the property worth pinning: the retired
    ``os.open(O_CREAT | O_EXCL | O_WRONLY)`` predecessor also never corrupts
    the victim here (``O_EXCL`` incidentally refuses any pre-existing path,
    symlink or not, via ``EEXIST``) -- but it does so by accident of a flag
    combination that would NOT protect ``machine_file_lock``'s own
    truncate-and-reuse (no-``O_EXCL``) shape, so this test asserts the
    designed guard, not the accidental one, and is RED against the
    predecessor on exception identity (it raises the generic
    ``MissionStateRepairError``, never ``NoFollowPathError``/``OSError``).
    """
    _init_git_repo(tmp_path)

    victim = tmp_path / "victim.txt"
    victim_bytes = b"do-not-touch-these-bytes\n"
    victim.write_bytes(victim_bytes)

    lock_path = tmp_path / ".git" / "spec-kitty-mission-state.lock"
    lock_path.symlink_to(victim)

    with pytest.raises((NoFollowPathError, OSError)), _git_lock(tmp_path):
        pass  # pragma: no cover - must never be reached

    # The symlink itself must still point at the victim (never replaced),
    # and the victim's bytes must be untouched by the refused acquire.
    assert lock_path.is_symlink()
    assert victim.read_bytes() == victim_bytes


def test_lock_semantics_parity_with_hand_rolled_predecessor(tmp_path: Path) -> None:
    """Explicit contention + scope parity with the retired ``os.open(O_EXCL)`` lock.

    The hand-rolled predecessor was exclusive-create: a second *concurrent*
    acquirer failed because the lock file already existed, and the lock was
    strictly scope-bound to one ``with`` block -- a fresh, *sequential*
    (non-nested) acquisition after the first released always succeeded. Both
    properties must hold for the canonical replacement, even though its
    underlying primitive is advisory truncate-and-reuse rather than
    exclusive-create.
    """
    _init_git_repo(tmp_path)

    # --- Concurrent contention: second acquirer is refused immediately,
    # never blocked, while the first is still held. -----------------------
    first = _git_lock(tmp_path)
    first.__enter__()
    try:
        second = _git_lock(tmp_path)
        with pytest.raises(MissionStateRepairError, match="Another mission-state repair appears to be running"):
            second.__enter__()
    finally:
        first.__exit__(None, None, None)

    # --- Scope: after the first releases, a brand-new sequential
    # (non-nested) acquisition on the same repo succeeds -- the lock is not
    # left held, and the underlying kernel.locks primitive is designed for
    # exactly this "release truncates, never unlinks" reuse across separate
    # ``with`` blocks. -------------------------------------------------
    with _git_lock(tmp_path):
        pass

    with _git_lock(tmp_path):
        pass


def test_lock_translates_kernel_contention_error_to_mission_state_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``LockNotAcquired`` from the kernel primitive surfaces as ``MissionStateRepairError``.

    Callers of ``repair_repo``/``repair_duplicate_key_artifacts`` have always
    caught ``MissionStateRepairError`` on lock contention (pre-#4811
    behavior: a raw ``FileExistsError`` translated to the same type). This
    pins that translation still holds through the kernel primitive, using a
    monkeypatched double so the assertion is independent of real OS-level
    lock timing.
    """
    _init_git_repo(tmp_path)

    class _AlwaysContendedLock:
        def __init__(self, lock_path: Path) -> None:
            self._lock_path = lock_path

        def __enter__(self) -> object:
            raise LockNotAcquired(path=str(self._lock_path))

        def __exit__(self, *args: object) -> None:  # pragma: no cover - never entered
            pass

    def _factory(lock_path: Path, *, blocking: bool = False, **kwargs: object) -> object:
        return _AlwaysContendedLock(lock_path)

    monkeypatch.setattr("specify_cli.migration.mission_state.machine_file_lock", _factory)

    with pytest.raises(MissionStateRepairError, match="Another mission-state repair appears to be running"), _git_lock(tmp_path):
        pass  # pragma: no cover - must never be reached
