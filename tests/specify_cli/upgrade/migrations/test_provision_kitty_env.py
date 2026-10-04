"""Tests for m_3_2_8_provision_kitty_env (T017/T020, C-MIG-1, C-MIG-2).

Mirrors the established migration-test pattern (see
``tests/specify_cli/upgrade/migrations/test_heal_provenance.py``): every test
calls ``detect()``/``can_apply()``/``apply()`` directly on a migration
instance against a synthetic project, never through the upgrade pipeline.
"""

from __future__ import annotations

import os
import sys
import stat
import threading
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from kernel.paths import get_package_asset_root
from specify_cli.upgrade.migrations import m_3_2_8_provision_kitty_env as provision_module
from specify_cli.upgrade.migrations.m_3_2_8_provision_kitty_env import (
    ClaudeignorePathError,
    GOVERNED_SECRET_VARS,
    MIGRATION_ID,
    NEVER_SEED_VARS,
    ProvisionKittyEnvMigration,
    _read_ignore_file_text,
    _atomic_write_claudeignore,
    _append_claudeignore_entry,
    _open_claudeignore_no_follow,
)
from specify_cli.upgrade.migrations import auto_discover_migrations
from specify_cli.upgrade.registry import MigrationRegistry

pytestmark = [pytest.mark.unit]


def _env_file_path(project_path: Path) -> Path:
    return project_path / ".kittify" / ".kitty.env"


def _config_yaml_path(project_path: Path) -> Path:
    return project_path / ".kittify" / "config.yaml"


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def test_migration_is_registered() -> None:
    found = MigrationRegistry.get_by_id(MIGRATION_ID)
    assert found is not None
    assert found.migration_id == MIGRATION_ID
    assert found.runs_on_worktrees is False


def test_target_version_does_not_exceed_package_version() -> None:
    """Guards the module docstring's own stated invariant directly (belt-and-
    suspenders alongside the repo-wide
    ``test_discovered_migration_targets_do_not_exceed_package_version`` gate)."""
    from packaging.version import Version

    migration = ProvisionKittyEnvMigration()
    assert Version(migration.target_version) <= Version("3.2.6rc2")


# ---------------------------------------------------------------------------
# detect() / can_apply()
# ---------------------------------------------------------------------------


class TestDetect:
    def test_detect_true_on_fresh_project(self, tmp_path: Path) -> None:
        migration = ProvisionKittyEnvMigration()
        assert migration.detect(tmp_path) is True

    def test_can_apply_true_on_fresh_project(self, tmp_path: Path) -> None:
        migration = ProvisionKittyEnvMigration()
        can_apply, reason = migration.can_apply(tmp_path)
        assert can_apply is True
        assert reason == ""

    def test_can_apply_false_once_fully_provisioned(self, tmp_path: Path) -> None:
        migration = ProvisionKittyEnvMigration()
        migration.apply(tmp_path, dry_run=False)

        can_apply, reason = migration.can_apply(tmp_path)
        assert can_apply is False
        assert reason != ""


# ---------------------------------------------------------------------------
# C-MIG-1: idempotency
# ---------------------------------------------------------------------------


class TestIdempotency:
    def test_second_apply_makes_no_further_changes(self, tmp_path: Path) -> None:
        migration = ProvisionKittyEnvMigration()

        first = migration.apply(tmp_path, dry_run=False)
        assert first.success is True
        assert any("Created" in change for change in first.changes_made)

        second = migration.apply(tmp_path, dry_run=False)
        assert second.success is True
        assert second.changes_made == ["already provisioned"]

    def test_detect_false_after_apply(self, tmp_path: Path) -> None:
        migration = ProvisionKittyEnvMigration()
        migration.apply(tmp_path, dry_run=False)
        assert migration.detect(tmp_path) is False

    def test_second_apply_does_not_rewrite_existing_env_file_content(self, tmp_path: Path) -> None:
        """A hand-edited .kitty.env survives re-running the migration untouched."""
        migration = ProvisionKittyEnvMigration()
        migration.apply(tmp_path, dry_run=False)

        env_path = _env_file_path(tmp_path)
        env_path.write_text("# hand-edited\nCUSTOM_VAR=keep-me\n", encoding="utf-8")

        migration.apply(tmp_path, dry_run=False)

        assert env_path.read_text(encoding="utf-8") == "# hand-edited\nCUSTOM_VAR=keep-me\n"

    def test_dry_run_makes_no_filesystem_changes(self, tmp_path: Path) -> None:
        migration = ProvisionKittyEnvMigration()
        result = migration.apply(tmp_path, dry_run=True)

        assert result.success is True
        assert not _env_file_path(tmp_path).exists()
        assert not _config_yaml_path(tmp_path).exists()
        assert migration.detect(tmp_path) is True


# ---------------------------------------------------------------------------
# C-MIG-2: never seed SPEC_KITTY_PACKS_ROOT
# ---------------------------------------------------------------------------


def _has_active_assignment(content: str, var: str) -> bool:
    """True iff *content* has an un-commented ``VAR=...`` assignment line.

    Deliberately narrower than a bare substring check: the generated file's
    own explanatory header legitimately *names* ``SPEC_KITTY_PACKS_ROOT`` in
    a comment (documenting why it is excluded) -- what must never appear is
    an ACTIVE assignment a loader would pick up.
    """
    prefix = f"{var}="
    return any(line.strip().startswith(prefix) and not line.strip().startswith("#") for line in content.splitlines())


class TestNeverSeedPacksRoot:
    def test_env_file_never_mentions_packs_root_even_when_set(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        assert "SPEC_KITTY_PACKS_ROOT" in NEVER_SEED_VARS

        monkeypatch.setenv("SPEC_KITTY_PACKS_ROOT", str(tmp_path / "some" / "packs"))

        migration = ProvisionKittyEnvMigration()
        migration.apply(tmp_path, dry_run=False)

        content = _env_file_path(tmp_path).read_text(encoding="utf-8")
        assert not _has_active_assignment(content, "SPEC_KITTY_PACKS_ROOT")

    def test_env_file_never_mentions_packs_root_when_unset(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SPEC_KITTY_PACKS_ROOT", raising=False)

        migration = ProvisionKittyEnvMigration()
        migration.apply(tmp_path, dry_run=False)

        content = _env_file_path(tmp_path).read_text(encoding="utf-8")
        assert not _has_active_assignment(content, "SPEC_KITTY_PACKS_ROOT")

    def test_template_root_still_governs_asset_resolution_with_scaffold_present(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Regression: a provisioned .kitty.env must never flip the TEMPLATE_ROOT
        gate (kernel/paths.py) even though the loader merges it into
        os.environ via setdefault. Mirrors
        tests/kernel/test_paths.py::TestGetPackageAssetRoot's own fixture shape.
        """
        project = tmp_path / "project"
        project.mkdir()
        missions = tmp_path / "missions"
        templates = missions / "software-dev" / "templates"
        templates.mkdir(parents=True)
        (templates / "plan-template.md").write_text("# Plan\n", encoding="utf-8")

        monkeypatch.setenv("SPEC_KITTY_TEMPLATE_ROOT", str(missions))
        monkeypatch.delenv("SPEC_KITTY_PACKS_ROOT", raising=False)

        migration = ProvisionKittyEnvMigration()
        migration.apply(project, dry_run=False)

        # The scaffold exists on disk but was never loaded into os.environ in
        # this test (that is the pre-import loader's job, not the
        # migration's) -- so this proves the *file content itself* carries no
        # PACKS_ROOT that a subsequent load could apply. Cross-check directly:
        content = _env_file_path(project).read_text(encoding="utf-8")
        assert not _has_active_assignment(content, "SPEC_KITTY_PACKS_ROOT")

        # And TEMPLATE_ROOT still resolves the real asset root as expected --
        # unaffected by the scaffold's presence.
        assert get_package_asset_root() == missions

    def test_secret_vars_never_seeded_by_value_even_when_set(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        for var in GOVERNED_SECRET_VARS:
            monkeypatch.setenv(var, "super-secret-value-should-never-land-on-disk")

        migration = ProvisionKittyEnvMigration()
        migration.apply(tmp_path, dry_run=False)

        content = _env_file_path(tmp_path).read_text(encoding="utf-8")
        assert "super-secret-value-should-never-land-on-disk" not in content
        for var in GOVERNED_SECRET_VARS:
            # Named as a commented template line, never an active assignment.
            assert f"# {var}=" in content
            assert f"\n{var}=" not in content

    def test_operator_var_seeded_when_already_set(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SPEC_KITTY_NON_INTERACTIVE", "1")

        migration = ProvisionKittyEnvMigration()
        migration.apply(tmp_path, dry_run=False)

        content = _env_file_path(tmp_path).read_text(encoding="utf-8")
        assert "SPEC_KITTY_NON_INTERACTIVE=1" in content


# ---------------------------------------------------------------------------
# config.yaml env_file pointer
# ---------------------------------------------------------------------------


class TestConfigYamlPointer:
    def test_registers_env_file_pointer_on_fresh_config(self, tmp_path: Path) -> None:
        migration = ProvisionKittyEnvMigration()
        migration.apply(tmp_path, dry_run=False)

        yaml = YAML()
        data = yaml.load(_config_yaml_path(tmp_path).read_text(encoding="utf-8"))
        assert data["env_file"] == "${SPEC_KITTY_HOME}/.kitty.env"

    def test_preserves_existing_config_yaml_content(self, tmp_path: Path) -> None:
        config_path = _config_yaml_path(tmp_path)
        config_path.parent.mkdir(parents=True)
        config_path.write_text("vcs:\n  type: git\nagents:\n  available:\n  - claude\n", encoding="utf-8")

        migration = ProvisionKittyEnvMigration()
        migration.apply(tmp_path, dry_run=False)

        yaml = YAML()
        data = yaml.load(config_path.read_text(encoding="utf-8"))
        assert data["vcs"]["type"] == "git"
        assert data["agents"]["available"] == ["claude"]
        assert data["env_file"] == "${SPEC_KITTY_HOME}/.kitty.env"

    def test_does_not_overwrite_an_operator_customized_pointer(self, tmp_path: Path) -> None:
        config_path = _config_yaml_path(tmp_path)
        config_path.parent.mkdir(parents=True)
        config_path.write_text("env_file: /custom/path/.kitty.env\n", encoding="utf-8")

        migration = ProvisionKittyEnvMigration()
        migration.apply(tmp_path, dry_run=False)

        yaml = YAML()
        data = yaml.load(config_path.read_text(encoding="utf-8"))
        assert data["env_file"] == "/custom/path/.kitty.env"


# ---------------------------------------------------------------------------
# .gitignore / .claudeignore coverage (C-SEC-2)
# ---------------------------------------------------------------------------


class TestIgnoreCoverage:
    def test_adds_gitignore_entry(self, tmp_path: Path) -> None:
        migration = ProvisionKittyEnvMigration()
        migration.apply(tmp_path, dry_run=False)

        gitignore = (tmp_path / ".gitignore").read_text(encoding="utf-8")
        assert ".kittify/.kitty.env" in gitignore.splitlines()

    def test_adds_claudeignore_entry(self, tmp_path: Path) -> None:
        migration = ProvisionKittyEnvMigration()
        migration.apply(tmp_path, dry_run=False)

        claudeignore = (tmp_path / ".claudeignore").read_text(encoding="utf-8")
        assert ".kittify/.kitty.env" in claudeignore.splitlines()

    def test_idempotent_against_pre_existing_gitignore_entry(self, tmp_path: Path) -> None:
        (tmp_path / ".gitignore").write_text(".kittify/.kitty.env\n", encoding="utf-8")

        migration = ProvisionKittyEnvMigration()
        result = migration.apply(tmp_path, dry_run=False)

        assert not any("gitignore" in change.lower() for change in result.changes_made)
        gitignore = (tmp_path / ".gitignore").read_text(encoding="utf-8")
        assert gitignore.count(".kittify/.kitty.env") == 1

    def test_idempotent_against_pre_existing_claudeignore_entry(self, tmp_path: Path) -> None:
        (tmp_path / ".claudeignore").write_text(".kittify/.kitty.env\n", encoding="utf-8")

        migration = ProvisionKittyEnvMigration()
        result = migration.apply(tmp_path, dry_run=False)

        assert not any("claudeignore" in change.lower() for change in result.changes_made)
        claudeignore = (tmp_path / ".claudeignore").read_text(encoding="utf-8")
        assert claudeignore.count(".kittify/.kitty.env") == 1

    def test_appends_to_existing_claudeignore_without_clobbering_it(self, tmp_path: Path) -> None:
        (tmp_path / ".claudeignore").write_text("node_modules/\n*.log\n", encoding="utf-8")

        migration = ProvisionKittyEnvMigration()
        migration.apply(tmp_path, dry_run=False)

        lines = (tmp_path / ".claudeignore").read_text(encoding="utf-8").splitlines()
        assert "node_modules/" in lines
        assert "*.log" in lines
        assert ".kittify/.kitty.env" in lines


# ---------------------------------------------------------------------------
# #656: FIFO/non-regular-file ignore files must fail closed, never hang.
#
# A FIFO substituted for .gitignore/.claudeignore hangs a bare
# path.read_text()/write_text() forever: open() on a FIFO blocks until a
# peer connects unless O_NONBLOCK is set. `@pytest.mark.timeout(5)` turns a
# regression back into "this test hangs" into "this test fails fast"
# instead of freezing the whole suite.
#
# Asserted as ``OSError`` (the stable builtin base), not the module's own
# ``NonRegularIgnoreFileError``: sibling tests in this directory call
# ``auto_discover_migrations()``, which -- per this module's own __init__.py
# reload guard -- can ``importlib.reload()`` this migration module mid-run
# and mint a fresh, distinct ``NonRegularIgnoreFileError`` class object.
# Depending on test order, the instance actually raised may fail an
# ``isinstance`` check against the class object this file imported at
# collection time. ``OSError`` itself is never reloaded, so it is immune to
# that ordering hazard while still proving the fail-closed contract.
# ---------------------------------------------------------------------------


@pytest.mark.skipif(sys.platform == "win32", reason="os.mkfifo is POSIX-only")
class TestNonRegularIgnoreFiles:
    @staticmethod
    def _provision_then_swap_for_fifo(tmp_path: Path, ignore_filename: str) -> None:
        """Run apply() once so every OTHER precondition is satisfied, then
        replace one ignore file with a FIFO -- so detect()'s ``or``-chain
        actually reaches the ignore-file check under test instead of
        short-circuiting on an earlier (still-missing) precondition."""
        migration = ProvisionKittyEnvMigration()
        migration.apply(tmp_path, dry_run=False)
        ignore_path = tmp_path / ignore_filename
        ignore_path.unlink()
        os.mkfifo(ignore_path)

    @pytest.mark.timeout(5)
    def test_detect_rejects_fifo_gitignore_without_hanging(self, tmp_path: Path) -> None:
        self._provision_then_swap_for_fifo(tmp_path, ".gitignore")
        migration = ProvisionKittyEnvMigration()

        with pytest.raises(OSError):
            migration.detect(tmp_path)

    @pytest.mark.timeout(5)
    def test_detect_rejects_fifo_claudeignore_without_hanging(self, tmp_path: Path) -> None:
        self._provision_then_swap_for_fifo(tmp_path, ".claudeignore")
        migration = ProvisionKittyEnvMigration()

        with pytest.raises(OSError):
            migration.detect(tmp_path)

    @pytest.mark.timeout(5)
    def test_can_apply_rejects_fifo_gitignore_without_hanging(self, tmp_path: Path) -> None:
        self._provision_then_swap_for_fifo(tmp_path, ".gitignore")
        migration = ProvisionKittyEnvMigration()

        with pytest.raises(OSError):
            migration.can_apply(tmp_path)

    @pytest.mark.timeout(5)
    def test_apply_rejects_fifo_claudeignore_without_hanging(self, tmp_path: Path) -> None:
        # First apply() satisfies every OTHER precondition (env file, config
        # pointer, .gitignore), so a second apply() call reaches the
        # .claudeignore write step (_append_claudeignore_entry) directly --
        # apply() re-checks _claudeignore_missing_entry unconditionally, not
        # gated behind detect().
        migration = ProvisionKittyEnvMigration()
        migration.apply(tmp_path, dry_run=False)
        claudeignore = tmp_path / ".claudeignore"
        claudeignore.unlink()
        os.mkfifo(claudeignore)

        with pytest.raises(OSError):
            migration.apply(tmp_path, dry_run=False)

    @pytest.mark.timeout(5)
    def test_read_ignore_file_text_rejects_fifo_without_hanging(self, tmp_path: Path) -> None:
        fifo_path = tmp_path / ".gitignore"
        os.mkfifo(fifo_path)

        with pytest.raises(OSError):
            _read_ignore_file_text(fifo_path)

    @pytest.mark.timeout(5)
    def test_atomic_write_claudeignore_rejects_fifo_without_hanging(self, tmp_path: Path) -> None:
        fifo_path = tmp_path / ".claudeignore"
        os.mkfifo(fifo_path)

        with pytest.raises(OSError):
            _atomic_write_claudeignore(fifo_path, "irrelevant\n")

    def test_read_ignore_file_text_rejects_symlink(self, tmp_path: Path) -> None:
        target = tmp_path / "real.gitignore"
        target.write_text("node_modules/\n", encoding="utf-8")
        link = tmp_path / ".gitignore"
        link.symlink_to(target)

        with pytest.raises(OSError):
            _read_ignore_file_text(link)

    def test_read_ignore_file_text_returns_empty_string_for_missing_file(self, tmp_path: Path) -> None:
        assert _read_ignore_file_text(tmp_path / "does-not-exist") == ""

    def test_atomic_write_then_read_claudeignore_round_trips_on_a_regular_file(self, tmp_path: Path) -> None:
        path = tmp_path / ".claudeignore"
        _atomic_write_claudeignore(path, "node_modules/\n*.log\n")

        assert _read_ignore_file_text(path) == "node_modules/\n*.log\n"

    def test_atomic_write_windows_fchmod_fallback_preserves_existing_mode(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Simulated Windows (no ``os.fchmod``): rewriting an existing file still works.

        Before the fix, the unconditional ``os.fchmod(fd, existing_mode)``
        call raised ``AttributeError: module 'os' has no attribute
        'fchmod'`` on a platform without the syscall.
        """
        monkeypatch.delattr(os, "fchmod", raising=False)
        path = tmp_path / ".claudeignore"
        path.write_text("old content\n", encoding="utf-8")
        path.chmod(0o640)

        _atomic_write_claudeignore(path, "node_modules/\n*.log\n")

        assert _read_ignore_file_text(path) == "node_modules/\n*.log\n"
        assert stat.S_IMODE(path.stat().st_mode) == 0o640

    @pytest.mark.skipif(sys.platform != "linux", reason="counts descriptors through /proc/self/fd")
    def test_atomic_write_closes_temp_fd_when_mode_change_fails(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A pre-write mode-change failure must not leak the temporary-file fd."""

        def fail_mode_change(*args: object, **kwargs: object) -> None:
            raise OSError("mode change failed")

        monkeypatch.setattr(provision_module.os, "chmod", fail_mode_change)
        monkeypatch.setattr(provision_module.os, "fchmod", fail_mode_change)

        path = tmp_path / ".claudeignore"
        path.touch()

        def open_fd_count() -> int:
            return len(os.listdir("/proc/self/fd"))

        before = open_fd_count()
        for _ in range(20):
            with pytest.raises(OSError, match="mode change failed"):
                _atomic_write_claudeignore(path, "irrelevant\n")
        after = open_fd_count()

        assert after == before
        assert list(tmp_path.glob(".claudeignore.*.tmp")) == []

    def test_atomic_write_treats_file_vanishing_after_existence_check_as_new(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A delete between the existence/probe syscalls must take the new-file path."""

        path = tmp_path / ".claudeignore"
        path.write_text("existing\n", encoding="utf-8")
        original_open = provision_module._open_claudeignore_no_follow

        def delete_then_open(probe_path: Path, flags: int) -> int:
            probe_path.unlink()
            return original_open(probe_path, flags)

        monkeypatch.setattr(provision_module, "_open_claudeignore_no_follow", delete_then_open)
        _atomic_write_claudeignore(path, "replacement\n")

        assert path.read_text(encoding="utf-8") == "replacement\n"

    def test_atomic_write_existing_file_does_not_change_process_umask(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Existing-file writes must not open even a momentary global umask window."""

        def fail_umask_change(*args: object, **kwargs: object) -> None:
            raise AssertionError("process umask was changed")

        monkeypatch.setattr(provision_module.os, "umask", fail_umask_change)
        path = tmp_path / ".claudeignore"
        path.write_text("existing\n", encoding="utf-8")

        _atomic_write_claudeignore(path, "replacement\n")

        assert path.read_text(encoding="utf-8") == "replacement\n"


# ---------------------------------------------------------------------------
# .claudeignore symlink safety (issue #627, sibling of #582/#618's fix for
# the same class of bug in GitignoreManager's .gitignore handling)
# ---------------------------------------------------------------------------


class TestClaudeignoreSymlinkSafety:
    def _make_symlinked_claudeignore(self, tmp_path: Path) -> Path:
        """Point .claudeignore at an outside-the-project target via a symlink."""
        outside_target = tmp_path.parent / f"outside-claudeignore-target-{os.getpid()}.txt"
        outside_target.write_text("do-not-touch\n", encoding="utf-8")
        (tmp_path / ".claudeignore").symlink_to(outside_target)
        return outside_target

    def test_apply_rejects_symlinked_claudeignore(self, tmp_path: Path) -> None:
        """apply() must refuse to write through a symlinked .claudeignore."""
        outside_target = self._make_symlinked_claudeignore(tmp_path)
        try:
            migration = ProvisionKittyEnvMigration()
            with pytest.raises(ClaudeignorePathError):
                migration.apply(tmp_path, dry_run=False)
            # The symlink's target must be untouched.
            assert outside_target.read_text(encoding="utf-8") == "do-not-touch\n"
        finally:
            outside_target.unlink(missing_ok=True)

    def test_dangling_symlink_is_also_rejected(self, tmp_path: Path) -> None:
        """A symlink to a target that doesn't exist must still be rejected.

        `Path.exists()` follows symlinks and returns False for a dangling
        one, so the guard must trigger on `is_symlink()` directly, not
        `exists()`.
        """
        missing_target = tmp_path.parent / f"missing-claudeignore-target-{os.getpid()}.txt"
        (tmp_path / ".claudeignore").symlink_to(missing_target)

        migration = ProvisionKittyEnvMigration()
        with pytest.raises(ClaudeignorePathError):
            migration.apply(tmp_path, dry_run=False)

    def test_vanishing_symlink_is_still_rejected(self, tmp_path: Path, monkeypatch) -> None:
        missing_target = tmp_path.parent / f"missing-claudeignore-target-{os.getpid()}.txt"
        (tmp_path / ".claudeignore").symlink_to(missing_target)

        def readlink_raises(*args, **kwargs):
            raise FileNotFoundError(f"simulated vanished symlink: {args}")

        monkeypatch.setattr(os, "readlink", readlink_raises)

        migration = ProvisionKittyEnvMigration()
        with pytest.raises(ClaudeignorePathError):
            migration.apply(tmp_path, dry_run=False)

    def test_normal_claudeignore_write_survives_symlink_guard(self, tmp_path: Path) -> None:
        """Sanity check: a regular (non-symlink) .claudeignore still works."""
        migration = ProvisionKittyEnvMigration()
        migration.apply(tmp_path, dry_run=False)

        claudeignore = tmp_path / ".claudeignore"
        assert not claudeignore.is_symlink()
        assert ".kittify/.kitty.env" in claudeignore.read_text(encoding="utf-8").splitlines()

    def test_write_preserves_existing_claudeignore_mode(self, tmp_path: Path) -> None:
        """The atomic replace should not narrow an existing .claudeignore's mode."""
        claudeignore = tmp_path / ".claudeignore"
        claudeignore.write_text("existing\n", encoding="utf-8")
        os.chmod(claudeignore, 0o640)

        migration = ProvisionKittyEnvMigration()
        migration.apply(tmp_path, dry_run=False)

        mode = claudeignore.stat().st_mode & 0o777
        assert mode == 0o640

    def test_permission_denied_still_raised_on_readonly_claudeignore(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """os.replace() ignores the target's mode bits; the migration must not.

        A read-only `.claudeignore` must still surface `PermissionError` --
        an `os.replace()`-only implementation would silently clobber it
        instead, since rename() only checks the parent directory's
        permissions.

        The denial is injected at the write-probe seam
        (``_open_claudeignore_no_follow`` with ``O_WRONLY``) rather than via
        ``chmod(0o444)``: root bypasses file mode bits, so a chmod-based setup
        gave a different verdict per uid (#5622).
        """
        claudeignore = tmp_path / ".claudeignore"
        claudeignore.touch()
        original_open = provision_module._open_claudeignore_no_follow

        def deny_write_probe(path: Path, flags: int) -> int:
            if path == claudeignore and flags & os.O_WRONLY:
                raise PermissionError(13, "Permission denied", str(path))
            fd: int = original_open(path, flags)
            return fd

        monkeypatch.setattr(provision_module, "_open_claudeignore_no_follow", deny_write_probe)

        migration = ProvisionKittyEnvMigration()
        with pytest.raises(PermissionError):
            migration.apply(tmp_path, dry_run=False)

    def test_brand_new_claudeignore_respects_process_umask(self, tmp_path: Path) -> None:
        """A first-time .claudeignore must land at the umask-respecting mode
        `Path.write_text()` would give it, not `tempfile.mkstemp()`'s
        unconditional 0o600 (squad finding, PR#637 pass 1 MAJOR #1)."""
        previous_umask = os.umask(0o022)
        try:
            migration = ProvisionKittyEnvMigration()
            migration.apply(tmp_path, dry_run=False)
        finally:
            os.umask(previous_umask)

        claudeignore = tmp_path / ".claudeignore"
        mode = stat.S_IMODE(claudeignore.stat().st_mode)
        assert mode == 0o644, f"expected umask-0o022-respecting 0o644, got {oct(mode)}"

    def test_brand_new_claudeignore_respects_a_looser_umask_too(self, tmp_path: Path) -> None:
        previous_umask = os.umask(0o002)
        try:
            migration = ProvisionKittyEnvMigration()
            migration.apply(tmp_path, dry_run=False)
        finally:
            os.umask(previous_umask)

        claudeignore = tmp_path / ".claudeignore"
        mode = stat.S_IMODE(claudeignore.stat().st_mode)
        assert mode == 0o664, f"expected umask-0o002-respecting 0o664, got {oct(mode)}"

    def test_open_no_follow_rejects_symlink_without_touching_target(self, tmp_path: Path) -> None:
        """Direct unit test of the no-follow guard the read/probe now use --
        the guard and the open() are the same syscall, so there is no
        separate check-then-use window a swapped-in symlink can win."""
        secret_target = tmp_path.parent / f"no-follow-secret-{os.getpid()}.txt"
        secret_target.write_text("SUPER-SECRET-CONTENT\n", encoding="utf-8")
        claudeignore = tmp_path / ".claudeignore"
        claudeignore.symlink_to(secret_target)
        try:
            with pytest.raises(ClaudeignorePathError):
                os.close(_open_claudeignore_no_follow(claudeignore, os.O_RDONLY))
        finally:
            secret_target.unlink(missing_ok=True)

    def test_append_does_not_leak_symlink_target_content_under_race(self, tmp_path: Path) -> None:
        """Regression for the TOCTOU squad found (PR#637 pass 1 MAJOR #2):
        a `.claudeignore` swapped for a symlink between the guard and the
        read must never have its target's bytes read through and merged
        into the (now regular) `.claudeignore`. The guard and the read
        used to be separate syscalls (`_reject_claudeignore_symlink()` then
        `path.read_text()`); a racer thread flipping the file between a
        regular file and a symlink to an outside-the-project secret,
        exactly as the squad reproduced it, must never observe the
        secret's content land in `.claudeignore`.
        """
        project_path = tmp_path
        claudeignore = project_path / ".claudeignore"
        claudeignore.write_text("existing\n", encoding="utf-8")
        secret_target = tmp_path.parent / f"race-secret-{os.getpid()}.txt"
        secret_target.write_text("SUPER-SECRET-CONTENT\n", encoding="utf-8")

        stop = threading.Event()
        leaked = threading.Event()

        def racer() -> None:
            while not stop.is_set():
                claudeignore.unlink(missing_ok=True)
                try:
                    claudeignore.symlink_to(secret_target)
                except FileExistsError:
                    continue
                claudeignore.unlink(missing_ok=True)
                try:
                    claudeignore.write_text("regular\n", encoding="utf-8")
                except FileExistsError:
                    continue

        thread = threading.Thread(target=racer, daemon=True)
        thread.start()
        try:
            for _ in range(300):
                try:
                    _append_claudeignore_entry(project_path)
                except ClaudeignorePathError:
                    pass
                except OSError:
                    # Benign under this synthetic thrash: the racer can
                    # delete/replace the file between an existence check
                    # and a subsequent open() elsewhere in the write path.
                    # That's a plain "file vanished" race, unrelated to the
                    # symlink-follow content leak this test targets.
                    pass
                # Check through the same no-follow primitive under test --
                # a separate is_symlink() + read_text() here would carry
                # exactly the TOCTOU this test exists to catch, just in the
                # assertion instead of the production code.
                try:
                    fd = _open_claudeignore_no_follow(claudeignore, os.O_RDONLY)
                except (ClaudeignorePathError, FileNotFoundError):
                    continue
                with os.fdopen(fd, encoding="utf-8") as handle:
                    content = handle.read()
                if "SUPER-SECRET-CONTENT" in content:
                    leaked.set()
                    break
        finally:
            stop.set()
            thread.join(timeout=5)
            secret_target.unlink(missing_ok=True)

        assert not leaked.is_set(), "secret symlink target content leaked into .claudeignore"


# ---------------------------------------------------------------------------
# Ordering vs. the heal migration + #3381
# ---------------------------------------------------------------------------


class TestOrdering:
    @pytest.fixture(autouse=True, scope="class")
    def _discover_migrations(self) -> None:
        """Register both migrations this class asserts on, every time it runs.

        The module imports only the provision migration, so the heal migration
        was registered only as a side effect of some earlier test (#5186). A
        module-level import would not survive either: other tests call
        ``MigrationRegistry.clear()``, and ``auto_discover_migrations()`` is
        the rediscovery path that re-registers cleared modules exactly once.
        """
        auto_discover_migrations()

    def test_shares_target_version_with_heal_migration(self) -> None:
        """Both migrations are capped at the same installed package version --
        the tie is deliberate (see module docstring), not an oversight."""
        heal = MigrationRegistry.get_by_id("3.2.7_heal_provenance_paths")
        provision = MigrationRegistry.get_by_id(MIGRATION_ID)
        assert heal is not None
        assert provision is not None
        assert heal.target_version == provision.target_version == "3.2.6rc2"

    def test_registration_order_between_heal_and_provision_is_import_sequence_dependent(self) -> None:
        """Documents (does not paper over) the finding in the module docstring:
        registration order between the two same-target_version migrations
        follows import order, which is NOT a fixed contract either module
        controls alone -- it depends on which auto-discovery chain (doctor.py's
        sibling scan vs. upgrade's own migrations-dir scan) happens to run
        first in a given process. Both orders are legitimate and observed:
        this test pins that BOTH migrations end up registered exactly once
        regardless, never raising a duplicate-ID error, which is the actual
        invariant that matters (order-independence is covered separately by
        ``test_order_between_heal_and_provision_is_immaterial``).
        """
        heal = MigrationRegistry.get_by_id("3.2.7_heal_provenance_paths")
        provision = MigrationRegistry.get_by_id(MIGRATION_ID)
        assert heal is not None
        assert provision is not None

        ids = [migration.migration_id for migration in MigrationRegistry.get_all()]
        assert ids.count("3.2.7_heal_provenance_paths") == 1
        assert ids.count(MIGRATION_ID) == 1

    def test_order_between_heal_and_provision_is_immaterial(self, tmp_path: Path) -> None:
        """The real regression guard: heal and provision are function-disjoint
        (heal touches charter.yaml/agent_profiles_manifest.json only;
        provision touches .kitty.env/config.yaml's env_file key/the two
        ignore files only), so applying them in either order against the
        same project produces an identical provision-owned end state.
        """
        from specify_cli.upgrade.migrations.m_3_2_7_heal_provenance_paths import (
            HealProvenancePathsMigration,
        )

        heal_first = tmp_path / "heal_first"
        heal_first.mkdir()
        HealProvenancePathsMigration().apply(heal_first, dry_run=False)
        ProvisionKittyEnvMigration().apply(heal_first, dry_run=False)

        provision_first = tmp_path / "provision_first"
        provision_first.mkdir()
        ProvisionKittyEnvMigration().apply(provision_first, dry_run=False)
        HealProvenancePathsMigration().apply(provision_first, dry_run=False)

        assert _env_file_path(heal_first).read_text(encoding="utf-8") == _env_file_path(provision_first).read_text(encoding="utf-8")
        heal_config = YAML().load(_config_yaml_path(heal_first).read_text(encoding="utf-8"))
        provision_config = YAML().load(_config_yaml_path(provision_first).read_text(encoding="utf-8"))
        assert heal_config["env_file"] == provision_config["env_file"]

    def test_module_docstring_documents_3381_ordering_coordination(self) -> None:
        """T017 explicitly calls out coordinating ordering with #3381 (the open
        hosted-sync consent migration bug); pin that the documentation exists
        so a future #3381 migration author has somewhere to look."""
        from specify_cli.upgrade.migrations import m_3_2_8_provision_kitty_env as module

        assert module.__doc__ is not None
        assert "#3381" in module.__doc__
