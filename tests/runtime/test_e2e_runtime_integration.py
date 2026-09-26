"""End-to-end tests for the centralized runtime lifecycle.

Covers:
- T043: Fresh install flow (ensure_runtime -> init -> resolve)
- T044: Upgrade with legacy project (ensure_runtime -> legacy -> migrate -> resolve)

These tests exercise the full lifecycle from cold start through resolution,
verifying that all WP01-WP07 components work together end-to-end.
"""

from __future__ import annotations

import warnings
from pathlib import Path

from specify_cli.runtime.bootstrap import ensure_runtime, check_version_pin
from specify_cli.runtime.resolver import (
    ResolutionTier,
    resolve_template,
    resolve_command,
    resolve_mission,
)
from specify_cli.runtime.migrate import execute_migration

import pytest

pytestmark = pytest.mark.git_repo

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FAKE_VERSION = "99.0.0-e2e-test"

@pytest.fixture()
def isolated_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create an isolated global runtime directory via SPEC_KITTY_HOME.

    Returns the path that will become ~/.kittify/ (not yet created).
    """
    global_home = tmp_path / "global_kittify"
    monkeypatch.setenv("SPEC_KITTY_HOME", str(global_home))
    return global_home

@pytest.fixture()
def fake_package_assets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a fake package asset root with missions/software-dev structure.

    Returns the missions directory (what get_package_asset_root returns).
    """
    pkg_root = tmp_path / "package"
    missions = pkg_root / "missions"

    # software-dev mission with templates and command-templates
    sw_dev = missions / "software-dev"
    (sw_dev / "templates").mkdir(parents=True)
    (sw_dev / "templates" / "spec-template.md").write_text(
        "# Spec Template\nThis is the default spec template."
    )
    (sw_dev / "templates" / "plan-template.md").write_text(
        "# Plan Template\nThis is the default plan template."
    )
    (sw_dev / "command-templates").mkdir(parents=True)
    (sw_dev / "command-templates" / "plan.md").write_text(
        "# Plan Command\nDefault plan command template."
    )
    (sw_dev / "mission.yaml").write_text(
        "name: Software Development\nkey: software-dev\n"
    )

    # Scripts directory (sibling of missions)
    scripts = pkg_root / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "validate.py").write_text("# validate script")

    # AGENTS.md (sibling of missions)
    (pkg_root / "AGENTS.md").write_text("# Agents\nDefault agents list.")

    monkeypatch.setenv("SPEC_KITTY_TEMPLATE_ROOT", str(missions))
    return missions

# ---------------------------------------------------------------------------
# T043: Fresh install end-to-end flow
# ---------------------------------------------------------------------------

class TestFreshInstallE2E:
    """Fresh install: ensure_runtime -> verify populated -> resolve from global tier."""

    def test_ensure_runtime_populates_global_home(
        self,
        isolated_runtime: Path,
        fake_package_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """ensure_runtime() creates ~/.kittify/ and populates it from package assets."""
        monkeypatch.setattr(
            "specify_cli.runtime.bootstrap._get_cli_version",
            lambda: FAKE_VERSION,
        )

        # Before: global home does not exist
        assert not isolated_runtime.exists()

        # Act
        ensure_runtime()

        # After: global home exists with expected structure
        assert isolated_runtime.is_dir()
        assert (isolated_runtime / "cache" / "version.lock").exists()
        assert (isolated_runtime / "cache" / "version.lock").read_text().strip() == FAKE_VERSION
        assert (isolated_runtime / "missions" / "software-dev").is_dir()
        assert (isolated_runtime / "missions" / "software-dev" / "mission.yaml").exists()
        assert (isolated_runtime / "missions" / "software-dev" / "templates").is_dir()

    def test_resolution_works_from_global_tier(
        self,
        isolated_runtime: Path,
        fake_package_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """After ensure_runtime(), templates resolve from GLOBAL tier for a new project."""
        monkeypatch.setattr(
            "specify_cli.runtime.bootstrap._get_cli_version",
            lambda: FAKE_VERSION,
        )

        # Populate global runtime
        ensure_runtime()

        # Create a minimal project (no local templates)
        project = isolated_runtime.parent / "my_project"
        (project / ".kittify").mkdir(parents=True)

        # Resolve template -- should come from global tier
        result = resolve_template(
            "spec-template.md", project, mission="software-dev"
        )
        assert result.tier == ResolutionTier.GLOBAL_MISSION
        assert result.path.exists()
        assert "Spec Template" in result.path.read_text()

    def test_command_template_resolution_from_global(
        self,
        isolated_runtime: Path,
        fake_package_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Command templates also resolve from GLOBAL tier after ensure_runtime()."""
        monkeypatch.setattr(
            "specify_cli.runtime.bootstrap._get_cli_version",
            lambda: FAKE_VERSION,
        )

        ensure_runtime()

        project = isolated_runtime.parent / "my_project"
        (project / ".kittify").mkdir(parents=True)

        result = resolve_command("plan.md", project, mission="software-dev")
        assert result.tier == ResolutionTier.GLOBAL_MISSION
        assert result.path.exists()

    def test_mission_resolution_from_global(
        self,
        isolated_runtime: Path,
        fake_package_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Mission configs resolve from GLOBAL tier after ensure_runtime()."""
        monkeypatch.setattr(
            "specify_cli.runtime.bootstrap._get_cli_version",
            lambda: FAKE_VERSION,
        )

        ensure_runtime()

        project = isolated_runtime.parent / "my_project"
        (project / ".kittify").mkdir(parents=True)

        result = resolve_mission("software-dev", project)
        assert result.tier == ResolutionTier.GLOBAL_MISSION
        assert result.path.exists()

    def test_version_pin_check_no_crash_on_fresh_project(
        self,
        isolated_runtime: Path,
        fake_package_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """check_version_pin() does not crash on a fresh project without config.yaml."""
        monkeypatch.setattr(
            "specify_cli.runtime.bootstrap._get_cli_version",
            lambda: FAKE_VERSION,
        )

        ensure_runtime()

        project = isolated_runtime.parent / "my_project"
        (project / ".kittify").mkdir(parents=True)

        # Should not raise -- no config.yaml means no pin check
        check_version_pin(project)

# ---------------------------------------------------------------------------
# T044: Upgrade with legacy project end-to-end flow
# ---------------------------------------------------------------------------

class TestUpgradeLegacyProjectE2E:
    """Upgrade: ensure_runtime -> legacy project resolves with warnings -> migrate -> override."""

    def test_legacy_resolution_emits_nudge_when_global_configured(
        self,
        isolated_runtime: Path,
        fake_package_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Legacy project files resolve from LEGACY tier with a one-time
        stderr nudge (not DeprecationWarning) when global runtime is configured.
        """
        from specify_cli.runtime.resolver import _reset_migrate_nudge

        _reset_migrate_nudge()

        monkeypatch.setattr(
            "specify_cli.runtime.bootstrap._get_cli_version",
            lambda: FAKE_VERSION,
        )

        # Populate global runtime (creates cache/version.lock)
        ensure_runtime()

        # Create a legacy project with files in .kittify/templates/
        project = isolated_runtime.parent / "legacy_project"
        kittify = project / ".kittify"
        (kittify / "templates").mkdir(parents=True)
        (kittify / "templates" / "spec-template.md").write_text(
            "# Custom Spec\nThis is a legacy custom spec."
        )

        # Resolve -- should get legacy file with stderr nudge (no DeprecationWarning)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = resolve_template(
                "spec-template.md", project, mission="software-dev"
            )

        assert result.tier == ResolutionTier.LEGACY
        assert "Custom Spec" in result.path.read_text()

        # No DeprecationWarning when global runtime is configured
        deprecation_warnings = [
            x for x in w if issubclass(x.category, DeprecationWarning)
        ]
        assert len(deprecation_warnings) == 0

        # Instead, a nudge to stderr
        captured = capsys.readouterr()
        assert "spec-kitty migrate" in captured.err

    def test_migrate_moves_customized_to_overrides(
        self,
        isolated_runtime: Path,
        fake_package_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """After migration, user-created files (no package counterpart) land in overrides/."""
        monkeypatch.setattr(
            "specify_cli.runtime.bootstrap._get_cli_version",
            lambda: FAKE_VERSION,
        )

        ensure_runtime()

        # Create legacy project with user-created template (no package counterpart)
        project = isolated_runtime.parent / "legacy_project"
        kittify = project / ".kittify"
        (kittify / "templates").mkdir(parents=True)
        (kittify / "templates" / "my-custom-template.md").write_text(
            "# My Custom Spec\nThis is user-created content."
        )

        # Run migration
        report = execute_migration(project)

        # User-created file (no package counterpart) should move to overrides
        assert len(report.moved) >= 1
        assert (kittify / "overrides" / "templates" / "my-custom-template.md").exists()
        assert "My Custom Spec" in (
            kittify / "overrides" / "templates" / "my-custom-template.md"
        ).read_text()

    def test_migrate_supersedes_outdated_defaults(
        self,
        isolated_runtime: Path,
        fake_package_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A differing managed template (SUPERSEDED) is PRESERVED in place (#4961).

        It differs from the shipped counterpart, so the ownership guard cannot
        prove ownership and preserves it rather than deleting it — it is neither
        removed nor relocated to overrides/.
        """
        monkeypatch.setattr(
            "specify_cli.runtime.bootstrap._get_cli_version",
            lambda: FAKE_VERSION,
        )

        ensure_runtime()

        # Create legacy project with an old version of a managed template
        project = isolated_runtime.parent / "legacy_project"
        kittify = project / ".kittify"
        (kittify / "templates").mkdir(parents=True)
        customised = "# Old Spec Template v1\nThis is different from the current package default."
        (kittify / "templates" / "spec-template.md").write_text(customised)

        # Run migration
        report = execute_migration(project)

        # Differing default -> classified superseded, PRESERVED in place (not removed,
        # not moved to overrides).
        assert len(report.superseded) >= 1
        assert (kittify / "templates" / "spec-template.md").exists()
        assert (kittify / "templates" / "spec-template.md").read_text() == customised
        assert not (kittify / "overrides" / "templates" / "spec-template.md").exists()

    def test_after_migration_resolves_from_override_tier(
        self,
        isolated_runtime: Path,
        fake_package_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """After migration, user-created templates resolve from OVERRIDE tier (no warning)."""
        monkeypatch.setattr(
            "specify_cli.runtime.bootstrap._get_cli_version",
            lambda: FAKE_VERSION,
        )

        ensure_runtime()

        # Create legacy project with user-created template (no package counterpart)
        project = isolated_runtime.parent / "legacy_project"
        kittify = project / ".kittify"
        (kittify / "templates").mkdir(parents=True)
        (kittify / "templates" / "my-custom-template.md").write_text(
            "# My Custom Spec\nThis is user-created content."
        )

        # Migrate
        execute_migration(project)

        # Re-resolve -- should now come from OVERRIDE tier without deprecation warning
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = resolve_template(
                "my-custom-template.md", project, mission="software-dev"
            )

        assert result.tier == ResolutionTier.OVERRIDE
        assert "My Custom Spec" in result.path.read_text()
        # No deprecation warnings for override tier
        deprecation_warnings = [
            x for x in w if issubclass(x.category, DeprecationWarning)
        ]
        assert len(deprecation_warnings) == 0

    def test_migrate_removes_identical_files(
        self,
        isolated_runtime: Path,
        fake_package_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Migration removes files that are byte-identical to global."""
        monkeypatch.setattr(
            "specify_cli.runtime.bootstrap._get_cli_version",
            lambda: FAKE_VERSION,
        )

        ensure_runtime()

        # Create legacy project with identical template (same content as global)
        project = isolated_runtime.parent / "legacy_project"
        kittify = project / ".kittify"
        (kittify / "templates").mkdir(parents=True)
        (kittify / "templates" / "spec-template.md").write_text(
            "# Spec Template\nThis is the default spec template."
        )

        report = execute_migration(project)

        # Identical file should be removed
        assert len(report.removed) >= 1
        assert not (kittify / "templates" / "spec-template.md").exists()

    def test_after_removing_identical_resolves_from_global(
        self,
        isolated_runtime: Path,
        fake_package_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """After removing identical files, resolution falls through to GLOBAL tier."""
        monkeypatch.setattr(
            "specify_cli.runtime.bootstrap._get_cli_version",
            lambda: FAKE_VERSION,
        )

        ensure_runtime()

        # Create legacy project with identical template
        project = isolated_runtime.parent / "legacy_project"
        kittify = project / ".kittify"
        (kittify / "templates").mkdir(parents=True)
        (kittify / "templates" / "spec-template.md").write_text(
            "# Spec Template\nThis is the default spec template."
        )

        # Migrate (removes identical)
        execute_migration(project)

        # Re-resolve -- should fall through to GLOBAL tier
        result = resolve_template(
            "spec-template.md", project, mission="software-dev"
        )
        assert result.tier == ResolutionTier.GLOBAL_MISSION
        assert result.path.exists()

    def test_version_pin_warning_during_startup(
        self,
        isolated_runtime: Path,
        fake_package_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Version pin in config.yaml emits warning during startup flow."""
        monkeypatch.setattr(
            "specify_cli.runtime.bootstrap._get_cli_version",
            lambda: FAKE_VERSION,
        )

        ensure_runtime()

        # Create project with version pin
        project = isolated_runtime.parent / "pinned_project"
        kittify = project / ".kittify"
        kittify.mkdir(parents=True)
        (kittify / "config.yaml").write_text(
            "runtime:\n  pin_version: '1.2.3'\n"
        )

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            check_version_pin(project)

        user_warnings = [x for x in w if issubclass(x.category, UserWarning)]
        assert len(user_warnings) == 1
        assert "1.2.3" in str(user_warnings[0].message)
        assert "NOT be silently honored" in str(user_warnings[0].message)

    def test_full_upgrade_lifecycle(
        self,
        isolated_runtime: Path,
        fake_package_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Full lifecycle: ensure_runtime -> legacy -> migrate -> resolve cleanly.

        Simulates a complete upgrade path:
        1. Bootstrap global runtime
        2. Legacy project has mix of identical + customized files
        3. Migration classifies and moves appropriately
        4. Post-migration resolution works from correct tiers
        """
        monkeypatch.setattr(
            "specify_cli.runtime.bootstrap._get_cli_version",
            lambda: FAKE_VERSION,
        )

        # Step 1: Bootstrap
        ensure_runtime()
        assert (isolated_runtime / "missions" / "software-dev").is_dir()

        # Step 2: Create legacy project with mixed files
        project = isolated_runtime.parent / "legacy_project"
        kittify = project / ".kittify"

        # Identical to package (should be removed)
        (kittify / "templates").mkdir(parents=True)
        (kittify / "templates" / "spec-template.md").write_text(
            "# Spec Template\nThis is the default spec template."
        )

        # Superseded: old default that differs from current package.
        # Corrected contract (#4961): differing -> unprovable -> PRESERVED in place.
        plan_v1 = "# Old Plan Template v1\nThis is an outdated default."
        (kittify / "templates" / "plan-template.md").write_text(plan_v1)

        # Customized: user-created file with no package counterpart (should move to overrides)
        (kittify / "templates" / "my-custom-template.md").write_text(
            "# My Custom Template\nUser-created content."
        )

        # Project-specific (should be kept)
        (kittify / "config.yaml").write_text("agents:\n  available:\n    - claude\n")
        (kittify / "memory").mkdir(exist_ok=True)
        (kittify / "memory" / "notes.md").write_text("My project notes")

        # Step 3: Migrate
        report = execute_migration(project)

        assert len(report.removed) >= 1  # spec-template.md removed (identical)
        assert len(report.superseded) >= 1  # plan-template.md superseded (old default) -> preserved
        assert len(report.moved) >= 1  # my-custom-template.md moved (customized)
        assert len(report.kept) >= 2  # config.yaml + memory/notes.md kept

        # plan-template.md (SUPERSEDED) survives in place with content intact (#4961).
        assert (kittify / "templates" / "plan-template.md").read_text() == plan_v1

        # Step 4: Verify post-migration resolution
        # Identical file now resolves from GLOBAL_MISSION (mission-specific global)
        result_spec = resolve_template(
            "spec-template.md", project, mission="software-dev"
        )
        assert result_spec.tier == ResolutionTier.GLOBAL_MISSION

        # User-created file resolves from OVERRIDE (no deprecation warning)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result_custom = resolve_template(
                "my-custom-template.md", project, mission="software-dev"
            )
        assert result_custom.tier == ResolutionTier.OVERRIDE
        assert "My Custom Template" in result_custom.path.read_text()
        deprecation_warnings = [
            x for x in w if issubclass(x.category, DeprecationWarning)
        ]
        assert len(deprecation_warnings) == 0

        # Superseded file preserved in place (#4961) -> resolves from the LEGACY
        # tier (its own .kittify/templates/ copy), not GLOBAL_MISSION.
        result_plan = resolve_template(
            "plan-template.md", project, mission="software-dev"
        )
        assert result_plan.tier == ResolutionTier.LEGACY
        assert result_plan.path.read_text() == plan_v1

        # Project-specific files untouched
        assert (kittify / "config.yaml").exists()
        assert (kittify / "memory" / "notes.md").read_text() == "My project notes"
