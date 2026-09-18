"""WP04 migration coverage: bootstrap's owner-lock acquisition on
``kernel.locks`` (cross-os-primitive-unification, #4714).

Pre-migration, ``bootstrap.py`` carried its own raw ``_lock_exclusive``
(``fcntl.flock``/``msvcrt.locking``), imported lazily by
``asset_preparation.py``'s ``recheck_assets``/``_apply_retained_assets``.
WP04 retires that function outright: both call sites now construct
``kernel.locks.machine_file_lock`` directly. This module proves two
properties end to end through the real ``ensure_runtime()`` entry point:

- a genuinely blocking acquire against the persistent ``.update.lock`` --
  ``ensure_runtime()`` must wait for a concurrent holder rather than racing
  or raising, and must proceed once that holder releases;
- the #4703 no-self-read invariant survives the migration: this process
  never reads ``.update.lock``'s own bytes while it holds the lock.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from kernel.locks import machine_file_lock
import specify_cli.runtime.asset_preparation as ap
import specify_cli.runtime.bootstrap as bootstrap
from specify_cli.runtime.bootstrap import assess_runtime, ensure_runtime

pytestmark = [pytest.mark.unit, pytest.mark.fast]

FAKE_VERSION = "99.0.0-test"


@pytest.fixture()
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "kittify"
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home))
    return home


@pytest.fixture()
def fake_assets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    pkg_root = tmp_path / "package"
    missions = pkg_root / "missions"
    (missions / "software-dev").mkdir(parents=True)
    (missions / "software-dev" / "mission.yaml").write_text("test-mission")
    (missions / "software-dev" / "templates").mkdir()
    (missions / "software-dev" / "templates" / "spec.md").write_text("test-template")
    scripts = pkg_root / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "validate.py").write_text("# validate")
    (pkg_root / "AGENTS.md").write_text("# Agents")
    monkeypatch.setenv("SPEC_KITTY_TEMPLATE_ROOT", str(missions))
    return missions


def _warm_home_with_pending_effects(fake_home: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Materialize a warm home, then re-arm a pending effect while keeping
    the persistent owner lock on disk -- mirrors the pre-migration fixture
    of the same name in test_windows_self_held_lock_read.py."""
    monkeypatch.setattr(bootstrap, "_get_cli_version", lambda: FAKE_VERSION)
    ensure_runtime()  # cold: materializes home, creates cache/.update.lock + version.lock

    lock_path = fake_home / "cache" / ".update.lock"
    assert lock_path.exists(), "cold bootstrap must create the persistent owner lock"

    (fake_home / "cache" / "version.lock").unlink()

    reassessment = assess_runtime()
    assert reassessment.effects, "setup guard: the re-armed assessment must carry effects"
    prepared = reassessment.prepared
    assert lock_path in set(prepared.lock_paths), "setup guard: .update.lock must be an owner lock path"
    return lock_path


class TestNoLocalRawLockPrimitive:
    """FR-010: bootstrap.py no longer carries its own raw lock helper."""

    def test_lock_exclusive_is_removed(self) -> None:
        assert not hasattr(bootstrap, "_lock_exclusive")


class TestUpdateLockBlockingAcquire:
    """The canonical primitive's ``blocking=True`` acquire is real,
    cross-thread OS-level contention -- not a cooperative fast-path only."""

    def test_ensure_runtime_blocks_until_update_lock_released(
        self,
        fake_home: Path,
        fake_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        lock_path = _warm_home_with_pending_effects(fake_home, monkeypatch)

        acquired = threading.Event()
        release = threading.Event()

        def hold_lock() -> None:
            with machine_file_lock(lock_path, blocking=True):
                # kernel.locks._ensure_dir (post-#4714 WP04 review fix) only
                # hardens a directory it actually CREATES -- the managed
                # cache dir already exists here (ensure_runtime()'s cold
                # bootstrap created it), so this acquire never narrows its
                # mode. No caller-side restore step is needed any more.
                acquired.set()
                release.wait(timeout=5)

        holder = threading.Thread(target=hold_lock)
        holder.start()
        try:
            assert acquired.wait(timeout=5), "setup guard: the holder thread must acquire the lock"

            done = threading.Event()

            def run_ensure() -> None:
                ensure_runtime()
                done.set()

            waiter = threading.Thread(target=run_ensure)
            waiter.start()
            try:
                # The waiter must NOT complete while the holder still has the lock.
                assert not done.wait(timeout=0.3), "ensure_runtime() must block on a held .update.lock"
                release.set()
                assert done.wait(timeout=5), "ensure_runtime() must proceed once the holder releases"
            finally:
                waiter.join(timeout=5)
        finally:
            release.set()
            holder.join(timeout=5)


class TestUpdateLockNeverReadWhileHeld:
    """#4703 (carried through the migration): ensure_runtime()'s own
    under-lock recheck must never read .update.lock's bytes."""

    def test_ensure_runtime_never_content_reads_its_own_held_lock(
        self,
        fake_home: Path,
        fake_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        lock_path = _warm_home_with_pending_effects(fake_home, monkeypatch)

        real_node_state = ap.node_state
        content_reads: list[Path] = []

        def guarded_node_state(path: Path, *, read_content: bool = True) -> object:
            if read_content and path in ap._HELD_LOCKS.get():
                content_reads.append(path)
                raise PermissionError(13, "Permission denied")
            return real_node_state(path, read_content=read_content)

        monkeypatch.setattr(ap, "node_state", guarded_node_state)

        ensure_runtime()  # must not raise despite the simulated mandatory-lock read failure

        assert lock_path not in content_reads, "the held .update.lock must never be content-read"
