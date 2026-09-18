"""Tests for specify_cli.runtime.bootstrap — ensure_runtime() and helpers.

Covers:
- T010: ensure_runtime() fast path, slow path, version matching, temp cleanup
- T012: Interrupted update recovery (F-Bootstrap-001, 1A-07)
- T028: Version pin warning (F-Pin-001, 1A-16)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import warnings
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from specify_cli.runtime.bootstrap import (
    _cleanup_orphaned_update_dirs,
    _get_cli_version,
    check_version_pin,
    ensure_runtime,
    populate_from_package,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.unit, pytest.mark.integration]

FAKE_VERSION = "99.0.0-test"


@pytest.fixture()
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Set SPEC_KITTY_HOME to a temp dir and return the path."""
    home = tmp_path / "kittify"
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home))
    return home


@pytest.fixture()
def fake_assets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a fake package asset root and override discovery.

    Returns the missions directory (what get_package_asset_root returns).
    """
    pkg_root = tmp_path / "package"
    missions = pkg_root / "missions"
    (missions / "software-dev").mkdir(parents=True)
    (missions / "software-dev" / "mission.yaml").write_text("test-mission")
    (missions / "software-dev" / "templates").mkdir()
    (missions / "software-dev" / "templates" / "spec.md").write_text("test-template")
    (missions / "research").mkdir(parents=True)
    (missions / "research" / "mission.yaml").write_text("test-research")
    (missions / "research" / "templates").mkdir()
    (missions / "research" / "templates" / "spec.md").write_text("test-research-template")

    # Scripts directory (sibling of missions)
    scripts = pkg_root / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "validate.py").write_text("# validate")

    # AGENTS.md (sibling of missions)
    (pkg_root / "AGENTS.md").write_text("# Agents")

    monkeypatch.setenv("SPEC_KITTY_TEMPLATE_ROOT", str(missions))
    return missions


# ---------------------------------------------------------------------------
# T010: _get_cli_version() tests
# ---------------------------------------------------------------------------


class TestGetCliVersion:
    """_get_cli_version() returns the specify_cli.__version__ string."""

    def test_returns_string(self) -> None:
        version = _get_cli_version()
        assert isinstance(version, str)
        assert len(version) > 0

    def test_matches_package_version(self) -> None:
        from specify_cli import __version__

        assert _get_cli_version() == __version__


# ---------------------------------------------------------------------------
# WP04 (cross-os-primitive-unification): bootstrap._lock_exclusive() was
# retired outright -- both its call sites (asset_preparation.py's
# recheck_assets/_apply_retained_assets) now construct
# kernel.locks.machine_file_lock directly. Its own cross-platform parity is
# owned by tests/kernel/test_locks.py (WP03); the bootstrap-scoped migration
# behaviour (blocking acquire + .update.lock no-self-read) is covered by
# tests/runtime/test_bootstrap_lock_migration.py.
# ---------------------------------------------------------------------------


def test_lock_exclusive_no_longer_exists() -> None:
    """FR-010: bootstrap.py carries no raw lock helper any more."""
    import specify_cli.runtime.bootstrap as bootstrap_module

    assert not hasattr(bootstrap_module, "_lock_exclusive")


# ---------------------------------------------------------------------------
# T010: populate_from_package() tests
# ---------------------------------------------------------------------------


class TestPopulateFromPackage:
    """populate_from_package() copies package assets to target."""

    def test_copies_missions(self, tmp_path: Path, fake_assets: Path) -> None:
        target = tmp_path / "staging"
        populate_from_package(target)
        assert (target / "missions" / "software-dev" / "mission.yaml").exists()
        assert (target / "missions" / "research" / "mission.yaml").exists()

    def test_copies_scripts(self, tmp_path: Path, fake_assets: Path) -> None:
        target = tmp_path / "staging"
        populate_from_package(target)
        assert (target / "scripts" / "validate.py").exists()

    def test_copies_agents_md(self, tmp_path: Path, fake_assets: Path) -> None:
        target = tmp_path / "staging"
        populate_from_package(target)
        assert (target / "AGENTS.md").exists()
        assert (target / "AGENTS.md").read_text() == "# Agents"

    def test_creates_target_dir(self, tmp_path: Path, fake_assets: Path) -> None:
        target = tmp_path / "nonexistent" / "staging"
        populate_from_package(target)
        assert target.is_dir()


# ---------------------------------------------------------------------------
# T010: ensure_runtime() unit tests
# ---------------------------------------------------------------------------


class TestEnsureRuntimeFastPath:
    """Healthy content and marker: no writes or lock acquisition."""

    def test_fast_path_version_matches(
        self,
        fake_home: Path,
        fake_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When content and marker match, no populate/merge occurs."""
        monkeypatch.setattr(
            "specify_cli.runtime.bootstrap._get_cli_version",
            lambda: FAKE_VERSION,
        )

        # Pre-populate version.lock
        cache_dir = fake_home / "cache"
        cache_dir.mkdir(parents=True)
        (cache_dir / "version.lock").write_text(FAKE_VERSION)

        ensure_runtime()
        # Track whether the retained writer boundary is called on a healthy home.
        with patch("specify_cli.runtime.bootstrap.populate_from_package") as mock_pop:
            ensure_runtime()
            mock_pop.assert_not_called()

    def test_fast_path_no_lock_acquired(
        self,
        fake_home: Path,
        fake_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A complete healthy installation does not acquire the file lock."""
        monkeypatch.setattr(
            "specify_cli.runtime.bootstrap._get_cli_version",
            lambda: FAKE_VERSION,
        )

        cache_dir = fake_home / "cache"
        cache_dir.mkdir(parents=True)
        (cache_dir / "version.lock").write_text(FAKE_VERSION)

        ensure_runtime()
        with patch("specify_cli.runtime.asset_preparation.machine_file_lock") as mock_lock:
            ensure_runtime()
            mock_lock.assert_not_called()


class TestEnsureRuntimeSlowPath:
    """Slow path: version.lock missing or stale -- full update occurs."""

    def test_slow_path_version_lock_missing(
        self,
        fake_home: Path,
        fake_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Missing version.lock triggers full populate + merge."""
        monkeypatch.setattr(
            "specify_cli.runtime.bootstrap._get_cli_version",
            lambda: FAKE_VERSION,
        )

        ensure_runtime()

        version_file = fake_home / "cache" / "version.lock"
        assert version_file.exists()
        assert version_file.read_text().strip() == FAKE_VERSION

    def test_slow_path_version_lock_stale(
        self,
        fake_home: Path,
        fake_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Stale version.lock triggers update and writes new version."""
        monkeypatch.setattr(
            "specify_cli.runtime.bootstrap._get_cli_version",
            lambda: FAKE_VERSION,
        )

        # Pre-populate with old version
        cache_dir = fake_home / "cache"
        cache_dir.mkdir(parents=True)
        (cache_dir / "version.lock").write_text("0.1.0-old")

        ensure_runtime()

        assert (cache_dir / "version.lock").read_text().strip() == FAKE_VERSION

    def test_slow_path_creates_home_dir(
        self,
        fake_home: Path,
        fake_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Slow path creates ~/.kittify/ if it doesn't exist."""
        monkeypatch.setattr(
            "specify_cli.runtime.bootstrap._get_cli_version",
            lambda: FAKE_VERSION,
        )

        assert not fake_home.exists()
        ensure_runtime()
        assert fake_home.is_dir()

    def test_slow_path_populates_managed_dirs(
        self,
        fake_home: Path,
        fake_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Slow path copies managed directories into ~/.kittify/."""
        monkeypatch.setattr(
            "specify_cli.runtime.bootstrap._get_cli_version",
            lambda: FAKE_VERSION,
        )

        ensure_runtime()

        assert (fake_home / "missions" / "software-dev" / "mission.yaml").exists()
        assert (fake_home / "missions" / "research" / "mission.yaml").exists()

    def test_slow_path_refuses_changed_batch_after_lock(
        self,
        fake_home: Path,
        fake_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A concurrent stamp cannot certify the previously assessed batch."""
        monkeypatch.setattr(
            "specify_cli.runtime.bootstrap._get_cli_version",
            lambda: FAKE_VERSION,
        )

        # Simulate: version.lock doesn't exist before lock but does after.
        # WP04: injected via kernel.locks' own G6 test-double seam
        # (SyncMachineFileLock looked up through kernel.locks' module
        # namespace at call time) rather than the retired
        # bootstrap._lock_exclusive -- firing the side effect on the FIRST
        # lock actually acquired (the cold-install sentinel), mirroring the
        # pre-migration test's interception of the anchor-flock acquisition.
        import kernel.locks as kernel_locks

        real_lock_cls = kernel_locks.SyncMachineFileLock
        call_count = 0

        class _VersionMaterializingLock(real_lock_cls):  # type: ignore[misc]
            def __enter__(self) -> Any:
                nonlocal call_count
                record = super().__enter__()
                call_count += 1
                if call_count == 1:
                    # Simulate another process finishing while we waited.
                    cache_dir = fake_home / "cache"
                    cache_dir.mkdir(parents=True, exist_ok=True)
                    (cache_dir / "version.lock").write_text(FAKE_VERSION)
                return record

        monkeypatch.setattr(kernel_locks, "SyncMachineFileLock", _VersionMaterializingLock)

        with patch("specify_cli.runtime.bootstrap.populate_from_package") as mock_pop:
            with pytest.raises(RuntimeError, match="Global asset input changed"):
                ensure_runtime()
            mock_pop.assert_not_called()
        assert not (fake_home / "missions").exists()


class TestEnsureRuntimeTempDirCleanup:
    """Temp directory is cleaned up even if an error occurs."""

    def test_temp_dir_cleaned_on_success(
        self,
        fake_home: Path,
        fake_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Temp directory is removed after successful update."""
        monkeypatch.setattr(
            "specify_cli.runtime.bootstrap._get_cli_version",
            lambda: FAKE_VERSION,
        )

        ensure_runtime()

        # No .kittify_update_* directories should remain
        parent = fake_home.parent
        update_dirs = list(parent.glob(".kittify_update_*"))
        assert len(update_dirs) == 0

    def test_temp_dir_cleaned_on_exception(
        self,
        fake_home: Path,
        fake_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Temp directory is removed even when populate raises."""
        monkeypatch.setattr(
            "specify_cli.runtime.bootstrap._get_cli_version",
            lambda: FAKE_VERSION,
        )

        def exploding_populate(*args: object, **kwargs: object) -> None:
            raise OSError("Simulated failure during source preparation")

        monkeypatch.setattr(
            "specify_cli.runtime.asset_preparation.AssetPreparation.source",
            exploding_populate,
        )

        with pytest.raises(RuntimeError, match="Simulated failure"):
            ensure_runtime()

        # Temp dir must be cleaned up
        parent = fake_home.parent
        update_dirs = list(parent.glob(".kittify_update_*"))
        assert len(update_dirs) == 0


class TestEnsureRuntimeVersionLockWrittenLast:
    """version.lock is the last file written during update."""

    def test_version_lock_written_after_merge(
        self,
        fake_home: Path,
        fake_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """version.lock does not exist until merge completes."""
        monkeypatch.setattr(
            "specify_cli.runtime.bootstrap._get_cli_version",
            lambda: FAKE_VERSION,
        )

        write_order: list[str] = []
        from specify_cli.runtime import asset_preparation

        original_write = asset_preparation._write_asset

        def tracking_merge(write: asset_preparation.AssetWrite) -> None:
            original_write(write)
            write_order.append(write.effect.destination.name)
            # At this point version.lock should NOT exist yet
            version_file = fake_home / "cache" / "version.lock"
            if write.effect.destination != version_file:
                assert not version_file.exists(), "version.lock written before asset work completed"

        monkeypatch.setattr(
            "specify_cli.runtime.asset_preparation._write_asset",
            tracking_merge,
        )

        ensure_runtime()

        assert write_order[-1] == "version.lock"
        # Now version.lock should exist
        assert (fake_home / "cache" / "version.lock").exists()


# ---------------------------------------------------------------------------
# T012: Interrupted update recovery (F-Bootstrap-001, 1A-07)
# ---------------------------------------------------------------------------


class TestInterruptedUpdateRecovery:
    """Interrupted update (no version.lock) triggers full bootstrap on next run."""

    def test_interrupted_update_recovery(
        self,
        fake_home: Path,
        fake_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Missing version.lock after partial update triggers re-bootstrap (F-Bootstrap-001, 1A-07)."""
        monkeypatch.setattr(
            "specify_cli.runtime.bootstrap._get_cli_version",
            lambda: FAKE_VERSION,
        )

        # Simulate interrupted update: ~/.kittify/ exists with some files
        # but no version.lock
        fake_home.mkdir(parents=True)
        (fake_home / "missions" / "software-dev").mkdir(parents=True)
        (fake_home / "missions" / "software-dev" / "stale.yaml").write_text("stale")
        # No version.lock -- simulates interrupted update

        ensure_runtime()

        # Recovery complete: version.lock written
        version_file = fake_home / "cache" / "version.lock"
        assert version_file.exists()
        assert version_file.read_text().strip() == FAKE_VERSION

    def test_interrupted_update_preserves_user_data(
        self,
        fake_home: Path,
        fake_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Recovery from interrupted update preserves user-owned files."""
        monkeypatch.setattr(
            "specify_cli.runtime.bootstrap._get_cli_version",
            lambda: FAKE_VERSION,
        )

        # Simulate partial state with user data
        fake_home.mkdir(parents=True)
        (fake_home / "config.yaml").write_text("user: settings")
        (fake_home / "missions" / "custom").mkdir(parents=True)
        (fake_home / "missions" / "custom" / "mine.yaml").write_text("my mission")

        ensure_runtime()

        # User data preserved
        assert (fake_home / "config.yaml").read_text() == "user: settings"
        assert (fake_home / "missions" / "custom" / "mine.yaml").read_text() == "my mission"

    def test_empty_kittify_treated_as_needing_bootstrap(
        self,
        fake_home: Path,
        fake_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Empty ~/.kittify/ directory triggers full bootstrap."""
        monkeypatch.setattr(
            "specify_cli.runtime.bootstrap._get_cli_version",
            lambda: FAKE_VERSION,
        )

        fake_home.mkdir(parents=True)

        ensure_runtime()

        version_file = fake_home / "cache" / "version.lock"
        assert version_file.exists()
        assert version_file.read_text().strip() == FAKE_VERSION
        # Managed dirs should be populated
        assert (fake_home / "missions" / "software-dev").is_dir()


# ---------------------------------------------------------------------------
# _cleanup_orphaned_update_dirs() tests
# ---------------------------------------------------------------------------


class TestCleanupOrphanedUpdateDirs:
    """Orphaned .kittify_update_* directories are removed at startup."""

    def test_removes_orphaned_dirs(self, tmp_path: Path) -> None:
        """Orphaned .kittify_update_* dirs are cleaned up."""
        orphan1 = tmp_path / ".kittify_update_12345"
        orphan1.mkdir()
        (orphan1 / "missions").mkdir()
        (orphan1 / "missions" / "stale.yaml").write_text("stale")

        orphan2 = tmp_path / ".kittify_update_99999"
        orphan2.mkdir()

        _cleanup_orphaned_update_dirs(tmp_path)

        assert (orphan1 / "missions/stale.yaml").read_text() == "stale"
        assert orphan2.is_dir()

    def test_leaves_non_update_dirs_alone(self, tmp_path: Path) -> None:
        """Directories not matching .kittify_update_* are untouched."""
        safe_dir = tmp_path / ".kittify"
        safe_dir.mkdir()
        (safe_dir / "config.yaml").write_text("keep me")

        other_dir = tmp_path / ".other_dir"
        other_dir.mkdir()

        _cleanup_orphaned_update_dirs(tmp_path)

        assert safe_dir.exists()
        assert other_dir.exists()

    def test_noop_on_nonexistent_parent(self, tmp_path: Path) -> None:
        """No error when parent directory does not exist."""
        nonexistent = tmp_path / "nonexistent"
        _cleanup_orphaned_update_dirs(nonexistent)  # should not raise

    def test_cleanup_called_during_ensure_runtime(
        self,
        fake_home: Path,
        fake_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """ensure_runtime() cleans orphaned dirs under the lock."""
        monkeypatch.setattr(
            "specify_cli.runtime.bootstrap._get_cli_version",
            lambda: FAKE_VERSION,
        )

        # Pre-create an orphaned staging dir
        fake_home.mkdir(parents=True)
        orphan = fake_home.parent / ".kittify_update_old_crash"
        orphan.mkdir()
        (orphan / "leftover.txt").write_text("crash artifact")

        ensure_runtime()

        # Orphan should be cleaned up
        assert (orphan / "leftover.txt").read_text() == "crash artifact"
        # And the runtime should be functional
        assert (fake_home / "cache" / "version.lock").exists()


# ---------------------------------------------------------------------------
# T028 -- Version pin warning (F-Pin-001)
# ---------------------------------------------------------------------------


class TestCheckVersionPin:
    """Tests for check_version_pin() -- acceptance criterion 1A-16."""

    def test_pin_version_emits_warning(self, tmp_path: Path) -> None:
        """F-Pin-001: runtime.pin_version emits warning, uses latest global."""
        project = tmp_path / "project"
        config = project / ".kittify" / "config.yaml"
        config.parent.mkdir(parents=True)
        config.write_text("runtime:\n  pin_version: '1.0.0'\n")

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            check_version_pin(project)

        assert any("pinning is not yet supported" in str(warning.message) for warning in w)

    def test_pin_version_warning_contains_pin_value(self, tmp_path: Path) -> None:
        """Warning message includes the actual pinned version."""
        project = tmp_path / "project"
        config = project / ".kittify" / "config.yaml"
        config.parent.mkdir(parents=True)
        config.write_text("runtime:\n  pin_version: '2.5.3'\n")

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            check_version_pin(project)

        user_warnings = [x for x in w if issubclass(x.category, UserWarning)]
        assert len(user_warnings) == 1
        assert "2.5.3" in str(user_warnings[0].message)

    def test_pin_version_warning_says_not_silently_honored(self, tmp_path: Path) -> None:
        """Warning explicitly says the pin will NOT be silently honored."""
        project = tmp_path / "project"
        config = project / ".kittify" / "config.yaml"
        config.parent.mkdir(parents=True)
        config.write_text("runtime:\n  pin_version: '1.0.0'\n")

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            check_version_pin(project)

        user_warnings = [x for x in w if issubclass(x.category, UserWarning)]
        assert len(user_warnings) == 1
        assert "NOT be silently honored" in str(user_warnings[0].message)

    def test_no_warning_without_pin_version(self, tmp_path: Path) -> None:
        """No warning emitted when runtime.pin_version is absent."""
        project = tmp_path / "project"
        config = project / ".kittify" / "config.yaml"
        config.parent.mkdir(parents=True)
        config.write_text("runtime:\n  some_other_key: value\n")

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            check_version_pin(project)

        user_warnings = [x for x in w if issubclass(x.category, UserWarning)]
        assert len(user_warnings) == 0

    def test_no_warning_without_runtime_section(self, tmp_path: Path) -> None:
        """No warning when config has no runtime section."""
        project = tmp_path / "project"
        config = project / ".kittify" / "config.yaml"
        config.parent.mkdir(parents=True)
        config.write_text("agents:\n  available:\n    - claude\n")

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            check_version_pin(project)

        user_warnings = [x for x in w if issubclass(x.category, UserWarning)]
        assert len(user_warnings) == 0

    def test_no_warning_without_config_file(self, tmp_path: Path) -> None:
        """No warning when .kittify/config.yaml doesn't exist."""
        project = tmp_path / "project"
        (project / ".kittify").mkdir(parents=True)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            check_version_pin(project)

        user_warnings = [x for x in w if issubclass(x.category, UserWarning)]
        assert len(user_warnings) == 0

    def test_no_warning_without_kittify_dir(self, tmp_path: Path) -> None:
        """No warning when .kittify directory doesn't exist at all."""
        project = tmp_path / "project"
        project.mkdir(parents=True)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            check_version_pin(project)

        user_warnings = [x for x in w if issubclass(x.category, UserWarning)]
        assert len(user_warnings) == 0

    def test_empty_config_file(self, tmp_path: Path) -> None:
        """Empty config file doesn't cause errors."""
        project = tmp_path / "project"
        config = project / ".kittify" / "config.yaml"
        config.parent.mkdir(parents=True)
        config.write_text("")

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            check_version_pin(project)

        user_warnings = [x for x in w if issubclass(x.category, UserWarning)]
        assert len(user_warnings) == 0

    def test_malformed_yaml_does_not_crash(self, tmp_path: Path) -> None:
        """Malformed YAML doesn't crash -- config errors handled elsewhere."""
        project = tmp_path / "project"
        config = project / ".kittify" / "config.yaml"
        config.parent.mkdir(parents=True)
        config.write_text(": : : bad yaml [[[")

        # Should not raise
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            check_version_pin(project)

        user_warnings = [x for x in w if issubclass(x.category, UserWarning)]
        assert len(user_warnings) == 0

    def test_runtime_not_a_dict(self, tmp_path: Path) -> None:
        """If runtime is a string or other non-dict, no crash."""
        project = tmp_path / "project"
        config = project / ".kittify" / "config.yaml"
        config.parent.mkdir(parents=True)
        config.write_text("runtime: 'just a string'\n")

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            check_version_pin(project)

        user_warnings = [x for x in w if issubclass(x.category, UserWarning)]
        assert len(user_warnings) == 0

    def test_pin_version_numeric(self, tmp_path: Path) -> None:
        """Pin version specified as a number (not string) still warns."""
        project = tmp_path / "project"
        config = project / ".kittify" / "config.yaml"
        config.parent.mkdir(parents=True)
        config.write_text("runtime:\n  pin_version: 1.0\n")

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            check_version_pin(project)

        user_warnings = [x for x in w if issubclass(x.category, UserWarning)]
        assert len(user_warnings) == 1
        assert "1.0" in str(user_warnings[0].message)


# ---------------------------------------------------------------------------
# T028b -- Version pin check wired into CLI callback (1A-16)
# ---------------------------------------------------------------------------


class TestVersionPinWiredIntoCallback:
    """Verify check_version_pin is called from the root CLI callback."""

    def test_main_callback_calls_check_version_pin_when_project_found(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """main_callback() calls check_version_pin when locate_project_root finds a project."""
        mock_pin = MagicMock()

        with (
            patch(
                "specify_cli.locate_project_root",
                return_value=tmp_path,
            ),
            patch(
                "specify_cli.runtime.bootstrap.check_version_pin",
                mock_pin,
            ),
            patch("specify_cli.runtime.bootstrap.ensure_runtime"),
            patch("specify_cli.root_callback"),
        ):
            from specify_cli import main_callback

            main_callback(MagicMock(), version=False)

        mock_pin.assert_called_once_with(tmp_path)

    def test_main_callback_skips_check_version_pin_outside_project(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """main_callback() skips check_version_pin when not inside a spec-kitty project."""
        mock_pin = MagicMock()

        with (
            patch(
                "specify_cli.locate_project_root",
                return_value=None,
            ),
            patch(
                "specify_cli.runtime.bootstrap.check_version_pin",
                mock_pin,
            ),
            patch("specify_cli.runtime.bootstrap.ensure_runtime"),
            patch("specify_cli.root_callback"),
        ):
            from specify_cli import main_callback

            main_callback(MagicMock(), version=False)

        mock_pin.assert_not_called()

    def test_main_callback_skips_bootstrap_before_migrate(self) -> None:
        """The migrate command must relocate legacy state before global reads."""
        root_callback_mock = MagicMock()

        with (
            patch("specify_cli.root_callback", root_callback_mock),
            patch("specify_cli._run_startup_project_gates") as startup_gates_mock,
        ):
            from specify_cli import main_callback

            main_callback(
                MagicMock(meta={"defer_root_bootstrap": True}),
                version=False,
            )

        root_callback_mock.assert_not_called()
        startup_gates_mock.assert_not_called()

    def test_main_callback_skips_runtime_bootstrap_for_next(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """next is startup-sensitive but still runs project safety gates."""
        ensure_runtime_mock = MagicMock()
        ensure_skills_mock = MagicMock()
        ensure_commands_mock = MagicMock()
        root_callback_mock = MagicMock()
        check_schema_mock = MagicMock()
        check_pin_mock = MagicMock()
        project_root = Path("/nonexistent/spec-kitty-project")

        monkeypatch.setattr(
            sys,
            "argv",
            ["spec-kitty", "next", "--agent", "test", "--mission", "demo", "--json"],
        )

        with (
            patch("specify_cli.runtime.bootstrap.ensure_runtime", ensure_runtime_mock),
            patch("specify_cli.runtime.agent_skills.ensure_global_agent_skills", ensure_skills_mock),
            patch("specify_cli.runtime.agent_commands.ensure_global_agent_commands", ensure_commands_mock),
            patch("specify_cli.runtime.bootstrap.check_version_pin", check_pin_mock),
            patch("specify_cli.migration.gate.check_schema_version", check_schema_mock),
            patch("specify_cli.locate_project_root", return_value=project_root),
            patch("specify_cli.root_callback", root_callback_mock),
        ):
            from specify_cli import main_callback

            main_callback(MagicMock(invoked_subcommand="next"), version=False)

        root_callback_mock.assert_not_called()
        ensure_runtime_mock.assert_not_called()
        ensure_skills_mock.assert_not_called()
        ensure_commands_mock.assert_not_called()
        check_pin_mock.assert_called_once_with(project_root)
        check_schema_mock.assert_called_once_with(project_root, invoked_subcommand="next")

    def test_library_import_does_not_eagerly_load_cli_command_graph(self) -> None:
        """Library imports should not pay full CLI command registration cost.

        (The original probe imported ``specify_cli.sync.daemon``, which died
        with the sync transport, issue #5; a surviving CORE leaf module pins
        the same lazy-import discipline.)
        """
        script = """
import json
import sys

import specify_cli.status.store  # noqa: F401

print(json.dumps({
    "commands_loaded": "specify_cli.cli.commands" in sys.modules,
    "init_loaded": "specify_cli.cli.commands.init" in sys.modules,
}))
"""
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=str(Path(__file__).resolve().parents[2]),
            env={
                **os.environ,
                "PYTHONPATH": str(Path(__file__).resolve().parents[2] / "src"),
            },
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload == {
            "commands_loaded": False,
            "init_loaded": False,
        }
