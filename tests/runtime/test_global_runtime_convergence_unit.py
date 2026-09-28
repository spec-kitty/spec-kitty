"""Tests for WP08: Global runtime convergence (~/.kittify).

Covers:
- T034: Audit (verified by existing tests + new tier naming)
- T035: Resolution chain includes ~/.kittify/ (global-mission AND global tiers)
- T036: Legacy warnings suppressed after migration
- T037: One-time migrate nudge when ~/.kittify/ not configured
- T038: Migrate idempotency (ensure_runtime + per-project)
- T039: Resolution chain end-to-end tests

Resolution chain order:
1. OVERRIDE        -- .kittify/overrides/{subdir}/{name}
2. LEGACY          -- .kittify/{subdir}/{name}  (warns/nudges)
3. GLOBAL_MISSION  -- ~/.kittify/missions/{mission}/{subdir}/{name}
4. GLOBAL          -- ~/.kittify/{subdir}/{name}
5. PACKAGE_DEFAULT -- <package>/missions/{mission}/{subdir}/{name}
"""

from __future__ import annotations

import warnings
from pathlib import Path
from unittest.mock import patch

import pytest

from specify_cli.runtime.resolver import (
    ResolutionTier,
    _is_global_runtime_configured,
    _reset_migrate_nudge,
    resolve_command,
    resolve_template,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _create_file(path: Path, content: str = "placeholder") -> Path:
    """Create a file (and any missing parent dirs), return its path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


@pytest.fixture(autouse=True)
def _reset_nudge():
    """Reset the one-time migrate nudge flag before each test."""
    _reset_migrate_nudge()
    yield
    _reset_migrate_nudge()


# ---------------------------------------------------------------------------
# T035 -- Resolution chain includes ~/.kittify/ with GLOBAL tier
# ---------------------------------------------------------------------------


class TestGlobalTierResolution:
    """Verify GLOBAL (non-mission) tier resolves from ~/.kittify/{subdir}/{name}."""

    def test_global_non_mission_resolves_when_no_mission_specific(self, tmp_path: Path) -> None:
        """When only ~/.kittify/templates/{name} exists, GLOBAL tier wins."""
        project = tmp_path / "project"
        (project / ".kittify").mkdir(parents=True)

        global_home = tmp_path / "global_home"
        # Only non-mission global path
        global_path = _create_file(
            global_home / "templates" / "spec-template.md",
            content="global non-mission template",
        )

        with (
            patch(
                "specify_cli.runtime.resolver.get_kittify_home",
                return_value=global_home,
            ),
            patch(
                "specify_cli.runtime.resolver.get_package_asset_root",
                side_effect=FileNotFoundError("no pkg"),
            ),
        ):
            result = resolve_template("spec-template.md", project)

        assert result.tier == ResolutionTier.GLOBAL
        assert result.path == global_path
        assert result.path.read_text() == "global non-mission template"

    def test_global_mission_takes_precedence_over_global_non_mission(self, tmp_path: Path) -> None:
        """~/.kittify/missions/{m}/templates/ wins over ~/.kittify/templates/."""
        project = tmp_path / "project"
        (project / ".kittify").mkdir(parents=True)

        global_home = tmp_path / "global_home"
        # Mission-specific
        mission_path = _create_file(
            global_home / "missions" / "software-dev" / "templates" / "spec-template.md",
            content="global mission-specific",
        )
        # Non-mission
        _create_file(
            global_home / "templates" / "spec-template.md",
            content="global non-mission",
        )

        with (
            patch(
                "specify_cli.runtime.resolver.get_kittify_home",
                return_value=global_home,
            ),
            patch(
                "specify_cli.runtime.resolver.get_package_asset_root",
                side_effect=FileNotFoundError("no pkg"),
            ),
        ):
            result = resolve_template("spec-template.md", project)

        assert result.tier == ResolutionTier.GLOBAL_MISSION
        assert result.path == mission_path

    def test_global_non_mission_takes_precedence_over_package(self, tmp_path: Path) -> None:
        """~/.kittify/templates/ wins over package defaults."""
        project = tmp_path / "project"
        (project / ".kittify").mkdir(parents=True)

        global_home = tmp_path / "global_home"
        pkg_root = tmp_path / "pkg"

        global_path = _create_file(
            global_home / "templates" / "spec-template.md",
            content="global non-mission",
        )
        _create_file(
            pkg_root / "software-dev" / "templates" / "spec-template.md",
            content="package default",
        )

        with (
            patch(
                "specify_cli.runtime.resolver.get_kittify_home",
                return_value=global_home,
            ),
            patch(
                "specify_cli.runtime.resolver.get_package_asset_root",
                return_value=pkg_root,
            ),
        ):
            result = resolve_template("spec-template.md", project)

        assert result.tier == ResolutionTier.GLOBAL
        assert result.path == global_path

    def test_global_command_templates_resolve(self, tmp_path: Path) -> None:
        """Command templates also resolve from ~/.kittify/command-templates/."""
        project = tmp_path / "project"
        (project / ".kittify").mkdir(parents=True)

        global_home = tmp_path / "global_home"
        global_path = _create_file(
            global_home / "command-templates" / "plan.md",
            content="global command template",
        )

        with (
            patch(
                "specify_cli.runtime.resolver.get_kittify_home",
                return_value=global_home,
            ),
            patch(
                "specify_cli.runtime.resolver.get_package_asset_root",
                side_effect=FileNotFoundError("no pkg"),
            ),
        ):
            result = resolve_command("plan.md", project)

        assert result.tier == ResolutionTier.GLOBAL
        assert result.path == global_path


# ---------------------------------------------------------------------------
# T036 -- Legacy warnings suppressed after migration
# ---------------------------------------------------------------------------


class TestLegacyWarningSuppression:
    """After global runtime is configured, legacy warnings become nudges."""

    def test_no_deprecation_warning_when_global_runtime_configured(self, tmp_path: Path) -> None:
        """When ~/.kittify/cache/version.lock exists, no DeprecationWarning."""
        project = tmp_path / "project"
        kittify = project / ".kittify"
        _create_file(kittify / "templates" / "spec-template.md", "legacy content")

        global_home = tmp_path / "global_home"
        # Mark global runtime as configured
        _create_file(global_home / "cache" / "version.lock", "1.0.0")

        with (
            patch(
                "specify_cli.runtime.resolver.get_kittify_home",
                return_value=global_home,
            ),
            patch(
                "specify_cli.runtime.resolver.get_package_asset_root",
                side_effect=FileNotFoundError("no pkg"),
            ),
            warnings.catch_warnings(record=True) as w,
        ):
            warnings.simplefilter("always")
            result = resolve_template("spec-template.md", project)

        assert result.tier == ResolutionTier.LEGACY
        # No DeprecationWarning should have been emitted
        deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(deprecation_warnings) == 0

    def test_deprecation_warning_when_global_runtime_not_configured(self, tmp_path: Path) -> None:
        """When ~/.kittify/ has no version.lock, DeprecationWarning is emitted."""
        project = tmp_path / "project"
        kittify = project / ".kittify"
        _create_file(kittify / "templates" / "spec-template.md", "legacy content")

        global_home = tmp_path / "global_home"
        # No version.lock -- not configured
        global_home.mkdir(parents=True, exist_ok=True)

        with (
            patch(
                "specify_cli.runtime.resolver.get_kittify_home",
                return_value=global_home,
            ),
            patch(
                "specify_cli.runtime.resolver.get_package_asset_root",
                side_effect=FileNotFoundError("no pkg"),
            ),
            warnings.catch_warnings(record=True) as w,
        ):
            warnings.simplefilter("always")
            result = resolve_template("spec-template.md", project)

        assert result.tier == ResolutionTier.LEGACY
        # DeprecationWarning SHOULD have been emitted
        deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(deprecation_warnings) >= 1
        assert "spec-kitty migrate" in str(deprecation_warnings[0].message)


# ---------------------------------------------------------------------------
# T037 -- One-time migrate nudge
# ---------------------------------------------------------------------------


class TestMigrateNudge:
    """One-time stderr nudge when legacy assets resolve post-migration."""

    def test_nudge_printed_once_to_stderr(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """After migration, legacy resolution prints a single nudge to stderr."""
        project = tmp_path / "project"
        kittify = project / ".kittify"
        _create_file(kittify / "templates" / "spec-template.md", "legacy")
        _create_file(kittify / "templates" / "plan-template.md", "legacy plan")

        global_home = tmp_path / "global_home"
        _create_file(global_home / "cache" / "version.lock", "1.0.0")

        with (
            patch(
                "specify_cli.runtime.resolver.get_kittify_home",
                return_value=global_home,
            ),
            patch(
                "specify_cli.runtime.resolver.get_package_asset_root",
                side_effect=FileNotFoundError("no pkg"),
            ),
        ):
            # Resolve two legacy assets
            resolve_template("spec-template.md", project)
            resolve_template("plan-template.md", project)

        captured = capsys.readouterr()
        # Nudge should appear exactly once (not twice)
        assert captured.err.count("spec-kitty migrate") == 1
        assert "global runtime" in captured.err.lower() or "~/.kittify/" in captured.err

    def test_no_nudge_when_no_legacy_assets(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """No nudge when resolution doesn't hit legacy tier."""
        project = tmp_path / "project"
        (project / ".kittify").mkdir(parents=True)

        global_home = tmp_path / "global_home"
        _create_file(global_home / "cache" / "version.lock", "1.0.0")
        _create_file(
            global_home / "missions" / "software-dev" / "templates" / "spec-template.md",
            "global",
        )

        with (
            patch(
                "specify_cli.runtime.resolver.get_kittify_home",
                return_value=global_home,
            ),
            patch(
                "specify_cli.runtime.resolver.get_package_asset_root",
                side_effect=FileNotFoundError("no pkg"),
            ),
        ):
            resolve_template("spec-template.md", project)

        captured = capsys.readouterr()
        assert "spec-kitty migrate" not in captured.err


# ---------------------------------------------------------------------------
# T038 -- _is_global_runtime_configured helper
# ---------------------------------------------------------------------------


class TestIsGlobalRuntimeConfigured:
    """Test the _is_global_runtime_configured() helper."""

    def test_true_when_version_lock_exists(self, tmp_path: Path) -> None:
        """Returns True when cache/version.lock exists."""
        global_home = tmp_path / "global_home"
        _create_file(global_home / "cache" / "version.lock", "1.0.0")

        with patch(
            "specify_cli.runtime.resolver.get_kittify_home",
            return_value=global_home,
        ):
            assert _is_global_runtime_configured() is True

    def test_false_when_no_version_lock(self, tmp_path: Path) -> None:
        """Returns False when cache/version.lock does not exist."""
        global_home = tmp_path / "global_home"
        global_home.mkdir(parents=True)

        with patch(
            "specify_cli.runtime.resolver.get_kittify_home",
            return_value=global_home,
        ):
            assert _is_global_runtime_configured() is False

    def test_false_when_home_missing(self, tmp_path: Path) -> None:
        """Returns False when ~/.kittify/ doesn't exist at all."""
        with patch(
            "specify_cli.runtime.resolver.get_kittify_home",
            return_value=tmp_path / "nonexistent",
        ):
            assert _is_global_runtime_configured() is False

    def test_false_when_get_kittify_home_raises(self) -> None:
        """Returns False when get_kittify_home() raises RuntimeError."""
        with patch(
            "specify_cli.runtime.resolver.get_kittify_home",
            side_effect=RuntimeError("no home"),
        ):
            assert _is_global_runtime_configured() is False


# ---------------------------------------------------------------------------
# T039 -- Full resolution chain order verification
# ---------------------------------------------------------------------------


class TestFullResolutionChainOrder:
    """Verify the complete 5-tier precedence for templates."""

    def test_full_chain_override_wins(self, tmp_path: Path) -> None:
        """With all 5 tiers present, OVERRIDE wins."""
        project = tmp_path / "project"
        kittify = project / ".kittify"
        global_home = tmp_path / "global_home"
        pkg_root = tmp_path / "pkg"
        name = "spec-template.md"
        mission = "software-dev"

        # All 5 tiers
        override_path = _create_file(kittify / "overrides" / "templates" / name, "override")
        _create_file(kittify / "templates" / name, "legacy")
        _create_file(global_home / "missions" / mission / "templates" / name, "global-mission")
        _create_file(global_home / "templates" / name, "global")
        _create_file(pkg_root / mission / "templates" / name, "package")

        with (
            patch("specify_cli.runtime.resolver.get_kittify_home", return_value=global_home),
            patch("specify_cli.runtime.resolver.get_package_asset_root", return_value=pkg_root),
        ):
            result = resolve_template(name, project, mission=mission)

        assert result.tier == ResolutionTier.OVERRIDE
        assert result.path == override_path

    def test_full_chain_legacy_second(self, tmp_path: Path) -> None:
        """Without override, LEGACY wins (with warning)."""
        project = tmp_path / "project"
        kittify = project / ".kittify"
        global_home = tmp_path / "global_home"
        pkg_root = tmp_path / "pkg"
        name = "spec-template.md"
        mission = "software-dev"

        # Tiers 2-5 (no override)
        legacy_path = _create_file(kittify / "templates" / name, "legacy")
        _create_file(global_home / "missions" / mission / "templates" / name, "global-mission")
        _create_file(global_home / "templates" / name, "global")
        _create_file(pkg_root / mission / "templates" / name, "package")

        with (
            patch("specify_cli.runtime.resolver.get_kittify_home", return_value=global_home),
            patch("specify_cli.runtime.resolver.get_package_asset_root", return_value=pkg_root),
            warnings.catch_warnings(record=True),
        ):
            warnings.simplefilter("always")
            result = resolve_template(name, project, mission=mission)

        assert result.tier == ResolutionTier.LEGACY
        assert result.path == legacy_path

    def test_full_chain_global_mission_third(self, tmp_path: Path) -> None:
        """Without override or legacy, GLOBAL_MISSION wins."""
        project = tmp_path / "project"
        (project / ".kittify").mkdir(parents=True)
        global_home = tmp_path / "global_home"
        pkg_root = tmp_path / "pkg"
        name = "spec-template.md"
        mission = "software-dev"

        # Tiers 3-5 (no override or legacy)
        gm_path = _create_file(global_home / "missions" / mission / "templates" / name, "global-mission")
        _create_file(global_home / "templates" / name, "global")
        _create_file(pkg_root / mission / "templates" / name, "package")

        with (
            patch("specify_cli.runtime.resolver.get_kittify_home", return_value=global_home),
            patch("specify_cli.runtime.resolver.get_package_asset_root", return_value=pkg_root),
        ):
            result = resolve_template(name, project, mission=mission)

        assert result.tier == ResolutionTier.GLOBAL_MISSION
        assert result.path == gm_path

    def test_full_chain_global_fourth(self, tmp_path: Path) -> None:
        """Without override/legacy/global-mission, GLOBAL wins."""
        project = tmp_path / "project"
        (project / ".kittify").mkdir(parents=True)
        global_home = tmp_path / "global_home"
        pkg_root = tmp_path / "pkg"
        name = "spec-template.md"
        mission = "software-dev"

        # Tiers 4-5 (no override, legacy, or global-mission)
        global_path = _create_file(global_home / "templates" / name, "global")
        _create_file(pkg_root / mission / "templates" / name, "package")

        with (
            patch("specify_cli.runtime.resolver.get_kittify_home", return_value=global_home),
            patch("specify_cli.runtime.resolver.get_package_asset_root", return_value=pkg_root),
        ):
            result = resolve_template(name, project, mission=mission)

        assert result.tier == ResolutionTier.GLOBAL
        assert result.path == global_path

    def test_full_chain_package_fifth(self, tmp_path: Path) -> None:
        """When no other tier has the asset, PACKAGE_DEFAULT wins."""
        project = tmp_path / "project"
        (project / ".kittify").mkdir(parents=True)
        pkg_root = tmp_path / "pkg"
        name = "spec-template.md"
        mission = "software-dev"

        pkg_path = _create_file(pkg_root / mission / "templates" / name, "package")

        with (
            patch(
                "specify_cli.runtime.resolver.get_kittify_home",
                return_value=tmp_path / "empty_home",
            ),
            patch("specify_cli.runtime.resolver.get_package_asset_root", return_value=pkg_root),
        ):
            result = resolve_template(name, project, mission=mission)

        assert result.tier == ResolutionTier.PACKAGE_DEFAULT
        assert result.path == pkg_path


# ---------------------------------------------------------------------------
# T038 -- Migrate command idempotency (ensure_runtime integration)
# ---------------------------------------------------------------------------


class TestMigrateIdempotency:
    """Verify ensure_runtime + execute_migration are idempotent together."""

    def test_ensure_runtime_populates_version_lock(self, tmp_path: Path) -> None:
        """After ensure_runtime, cache/version.lock exists."""
        global_home = tmp_path / "global_home"
        pkg_root = tmp_path / "pkg"
        # Create a minimal package asset
        _create_file(
            pkg_root / "software-dev" / "templates" / "spec-template.md",
            "package template",
        )
        _create_file(
            pkg_root / "software-dev" / "mission.yaml",
            "name: software-dev",
        )

        with (
            patch("specify_cli.runtime.home.get_kittify_home", return_value=global_home),
            patch("specify_cli.runtime.bootstrap.get_kittify_home", return_value=global_home),
            patch("specify_cli.runtime.bootstrap.get_package_asset_root", return_value=pkg_root),
            patch("specify_cli.runtime.bootstrap._get_cli_version", return_value="99.0.0"),
        ):
            from specify_cli.runtime.bootstrap import ensure_runtime

            ensure_runtime()

        assert (global_home / "cache" / "version.lock").exists()
        assert (global_home / "cache" / "version.lock").read_text().strip() == "99.0.0"

    def test_ensure_runtime_idempotent(self, tmp_path: Path) -> None:
        """Running ensure_runtime twice produces identical state."""
        global_home = tmp_path / "global_home"
        pkg_root = tmp_path / "pkg"
        _create_file(
            pkg_root / "software-dev" / "templates" / "spec-template.md",
            "package template",
        )
        _create_file(
            pkg_root / "software-dev" / "mission.yaml",
            "name: software-dev",
        )

        with (
            patch("specify_cli.runtime.home.get_kittify_home", return_value=global_home),
            patch("specify_cli.runtime.bootstrap.get_kittify_home", return_value=global_home),
            patch("specify_cli.runtime.bootstrap.get_package_asset_root", return_value=pkg_root),
            patch("specify_cli.runtime.bootstrap._get_cli_version", return_value="99.0.0"),
        ):
            from specify_cli.runtime.bootstrap import ensure_runtime

            ensure_runtime()

            # Capture state after first run
            state_1 = {str(p.relative_to(global_home)): p.read_text() for p in global_home.rglob("*") if p.is_file()}

            ensure_runtime()

            # Capture state after second run
            state_2 = {str(p.relative_to(global_home)): p.read_text() for p in global_home.rglob("*") if p.is_file()}

        assert state_1 == state_2

    def test_migrate_then_resolve_no_warnings(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """After migration, template resolution produces zero warnings."""
        global_home = tmp_path / "global_home"
        # Set up global runtime as if ensure_runtime ran
        _create_file(global_home / "cache" / "version.lock", "99.0.0")
        _create_file(
            global_home / "missions" / "software-dev" / "templates" / "spec-template.md",
            "global content",
        )
        monkeypatch.setenv("SPEC_KITTY_HOME", str(global_home))

        # Project with NO legacy files (post-migration state)
        project = tmp_path / "project"
        (project / ".kittify").mkdir(parents=True)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = resolve_template("spec-template.md", project, mission="software-dev")

        assert result.tier == ResolutionTier.GLOBAL_MISSION
        deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(deprecation_warnings) == 0


# ---------------------------------------------------------------------------
# Credential path documentation
# ---------------------------------------------------------------------------


class TestCredentialPathDecision:
    """Verify credential path stays separate from ~/.kittify/."""

    def test_credential_path_not_in_kittify(self) -> None:
        """~/.spec-kitty/credentials is NOT under ~/.kittify/.

        This is a design decision test -- credentials have a different
        security model (tighter permissions, never synced, never in git).
        """
        from specify_cli.runtime.home import get_kittify_home

        home = get_kittify_home()
        # The credential path should NOT be under ~/.kittify/
        cred_path = Path.home() / ".spec-kitty" / "credentials"
        assert not str(cred_path).startswith(str(home)), "Credentials must NOT be under ~/.kittify/ -- different security model"
