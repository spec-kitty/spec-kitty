"""Tests for automatic migration discovery system.

Validates that migrations are auto-discovered from filesystem
without requiring manual imports in __init__.py.
"""

import tomllib
from pathlib import Path
from unittest.mock import patch

import pytest
from packaging.version import Version


from specify_cli.upgrade.migrations import MigrationDiscoveryError, auto_discover_migrations
from specify_cli.upgrade.registry import MigrationRegistry

pytestmark = pytest.mark.fast
REPO_ROOT = Path(__file__).parent.parent.parent
MIGRATIONS_DIR = REPO_ROOT / "src" / "specify_cli" / "upgrade" / "migrations"


class TestAutoDiscovery:
    """Test automatic migration discovery."""

    def test_auto_discover_finds_all_migrations(self):
        """All migration files matching m_*.py pattern are discovered."""
        # Clear registry
        MigrationRegistry.clear()

        # Count migration files in directory
        migration_files = list(MIGRATIONS_DIR.glob("m_*.py"))
        expected_count = len(migration_files)

        # Run auto-discovery
        auto_discover_migrations()

        # Verify all discovered
        discovered = MigrationRegistry.get_all()
        assert len(discovered) == expected_count, (
            f"Expected {expected_count} migrations (matching m_*.py pattern), but discovered {len(discovered)}"
        )

    def test_auto_discover_is_idempotent(self):
        """Running auto-discovery multiple times doesn't cause issues."""
        MigrationRegistry.clear()

        # Run discovery twice
        auto_discover_migrations()
        count_first = len(MigrationRegistry.get_all())

        auto_discover_migrations()
        count_second = len(MigrationRegistry.get_all())

        # Should have same count (no duplicates)
        assert count_first == count_second

    def test_auto_discover_skips_non_migration_files(self):
        """Files not matching m_*.py pattern are skipped."""
        MigrationRegistry.clear()
        auto_discover_migrations()

        # Get all migration IDs
        migration_ids = [m.migration_id for m in MigrationRegistry.get_all()]

        # Should not include base.py, __init__.py, or test files
        assert "base" not in migration_ids
        assert "__init__" not in migration_ids
        assert "test_" not in " ".join(migration_ids)

    def test_auto_discover_raises_on_import_errors(self):
        """Import errors fail fast so broken migrations cannot be skipped silently."""
        MigrationRegistry.clear()

        # Mock pkgutil to return a fake module that will fail import
        with patch("specify_cli.upgrade.migrations.pkgutil.iter_modules") as mock_iter:
            # Create a fake module info
            class FakeModuleInfo:
                name = "m_fake_broken"

            mock_iter.return_value = [FakeModuleInfo()]

            with pytest.raises(MigrationDiscoveryError, match="m_fake_broken"):
                auto_discover_migrations()

    def test_auto_discover_imports_base_module(self):
        """The base.py module is also imported (needed for BaseMigration)."""
        # This is implicitly tested - if base.py isn't imported,
        # the migration classes won't have BaseMigration available
        # and the whole system would crash

        MigrationRegistry.clear()
        auto_discover_migrations()

        # If we got here without crashing, base.py was imported correctly
        assert len(MigrationRegistry.get_all()) > 0

    def test_discovered_migrations_have_required_attributes(self):
        """All discovered migrations have required attributes."""
        MigrationRegistry.clear()
        auto_discover_migrations()

        for migration in MigrationRegistry.get_all():
            # Check required attributes exist
            assert hasattr(migration, "migration_id")
            assert hasattr(migration, "description")
            assert hasattr(migration, "target_version")

            # Check they're not empty
            assert migration.migration_id
            assert migration.description
            assert migration.target_version

            # Contract gate: compat-planner.json caps description at maxLength: 256
            # (#2419 / WP01 — guards future migrations from drifting over the limit)
            assert len(migration.description) <= 256, (
                f"{migration.migration_id!r}: description is {len(migration.description)} chars "
                f"(contract maxLength is 256): {migration.description!r}"
            )

    def test_discovered_migrations_follow_manifest_order(self):
        """Migrations are returned in ``order_manifest.txt`` order, not version order.

        The order authority moved from a target_version sort to the explicit
        manifest (ADR 2026-10-17-1, WP02): ``get_all()`` mirrors
        ``load_order_manifest()`` exactly, with the ``# runs-first:`` lead block
        (the adoption backfill at index 0) ahead of version order.
        """
        from specify_cli.upgrade.manifest import load_order_manifest

        MigrationRegistry.clear()
        auto_discover_migrations()

        migrations = MigrationRegistry.get_all()

        assert [m.migration_id for m in migrations] == load_order_manifest()
        assert migrations[0].migration_id == "4.0.0rc8_backfill_migration_ledger"

    def test_discovered_migration_targets_do_not_exceed_package_version(self):
        """Migrations newer than the installed package are skipped by upgrade."""
        project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
        package_version = Version(project["project"]["version"])

        MigrationRegistry.clear()
        auto_discover_migrations()

        ahead = [
            migration
            for migration in MigrationRegistry.get_all()
            if Version(migration.target_version) > package_version
        ]

        assert ahead == [], (
            f"Migration target(s) exceed package version {package_version}: "
            + ", ".join(
                f"{migration.migration_id} -> {migration.target_version}"
                for migration in ahead
            )
            + ". A user upgrading to the current package will not run them."
        )

    def test_import_does_not_auto_discover(self):
        """Importing the migrations package does not load every migration."""
        MigrationRegistry.clear()

        from specify_cli.upgrade import migrations  # noqa: F401

        assert len(MigrationRegistry.get_all()) == 0

    def test_auto_discover_does_not_reload_base_module(self):
        """clear() + auto-discover must NOT reload ``base`` (class identity).

        ``base`` holds the shared migration base classes (``BaseMigration``,
        ``MigrationResult``, ``PartialWrite``) that both the migration modules
        and external callers hold live references to, and it registers no
        migration. Before the fix, auto-discover always fell through the
        "not registered -> reload" branch for ``base`` and ``importlib.reload``
        minted fresh class objects — silently breaking ``isinstance`` across the
        process (a reloaded ``m_zz`` constructed the new ``base.PartialWrite``
        while a caller still held the original, so ``isinstance(write, PartialWrite)``
        went False). This is the cross-file pollution that flaked
        ``tests/upgrade/test_backfill_report_on_abort.py`` under ``--dist loadfile``.
        """
        import specify_cli.upgrade.migrations.base as base_module
        from specify_cli.upgrade.migrations.base import PartialWrite

        original_base = base_module
        original_partial_write = PartialWrite

        # The exact test scenario that used to trigger the base reload.
        MigrationRegistry.clear()
        auto_discover_migrations()

        import specify_cli.upgrade.migrations.base as base_after

        assert base_after is original_base, "auto-discover reloaded the base module"
        assert base_after.PartialWrite is original_partial_write, (
            "base.PartialWrite identity changed — a base reload broke isinstance()"
        )
        # A freshly-constructed record is an instance of the caller's imported class.
        assert isinstance(base_after.PartialWrite(mission="m", path="/p"), PartialWrite)

    def test_all_migration_files_have_registration_decorator(self):
        """All m_*.py files use @MigrationRegistry.register decorator."""
        for migration_file in MIGRATIONS_DIR.glob("m_*.py"):
            # Read file content
            content = migration_file.read_text()

            # Check for @MigrationRegistry.register
            assert "@MigrationRegistry.register" in content, (
                f"Migration {migration_file.name} missing @MigrationRegistry.register decorator"
            )


class TestAutoDiscoveryIntegration:
    """Integration tests for auto-discovery with upgrade workflow."""

    def test_upgrade_command_uses_auto_discovered_migrations(self, tmp_path):
        """The upgrade command can use auto-discovered migrations."""
        from specify_cli.upgrade.detector import VersionDetector

        # Create a fake project
        kittify_dir = tmp_path / ".kittify"
        kittify_dir.mkdir()

        # Create metadata with old version
        metadata_file = kittify_dir / "metadata.json"
        metadata_file.write_text('{"version": "0.1.0", "applied_migrations": []}')

        # Get applicable migrations
        detector = VersionDetector(tmp_path)
        detector.detect_version()

        # This should work with auto-discovered migrations
        auto_discover_migrations()
        applicable = MigrationRegistry.get_applicable(
            from_version="0.1.0",
            to_version="999.0.0",  # Get all migrations
            project_path=tmp_path,
        )

        # Should have many migrations
        assert len(applicable) > 20, "Should have discovered many migrations"

    @pytest.mark.performance
    def test_auto_discovery_performance(self):
        """Auto-discovery completes quickly (< 1 second)."""
        import time

        MigrationRegistry.clear()

        start = time.monotonic()
        auto_discover_migrations()
        duration = time.monotonic() - start

        # Should be very fast (usually < 100ms, but allow 1s for CI)
        assert duration < 1.0, f"Auto-discovery took {duration:.2f}s (should be < 1s)"


class TestBackwardCompatibility:
    """Ensure auto-discovery doesn't break existing behavior."""

    def test_manual_registration_still_works(self):
        """Manual @MigrationRegistry.register still works for tests."""
        from specify_cli.upgrade.migrations.base import BaseMigration, MigrationResult

        MigrationRegistry.clear()

        @MigrationRegistry.register
        class TestMigration(BaseMigration):
            migration_id = "test_manual"
            description = "Test manual registration"
            target_version = "999.0.0"

            def detect(self, project_path):
                return False

            def can_apply(self, project_path):
                return True, ""

            def apply(self, project_path, dry_run=False):
                return MigrationResult(success=True)

        # Verify it registered
        assert MigrationRegistry.get_by_id("test_manual") is not None

    def test_clear_registry_still_works(self):
        """MigrationRegistry.clear() still works (needed for test isolation)."""
        auto_discover_migrations()
        assert len(MigrationRegistry.get_all()) > 0

        MigrationRegistry.clear()
        assert len(MigrationRegistry.get_all()) == 0

        # Can re-discover
        auto_discover_migrations()
        assert len(MigrationRegistry.get_all()) > 0
