"""Tests for the 4-tier asset resolver.

Covers:
- T018: Resolution precedence tests (G2)
- T019: Legacy resolution tests (F-Legacy)
"""

from __future__ import annotations

import warnings
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from charter.activation.mission_type_profiles import ResolvedMissionType
from specify_cli.runtime.resolver import (
    ResolutionResult,
    ResolutionTier,
    TemplateConfigurationError,
    required_artifacts_for,
    resolve_command,
    resolve_configured_artifact_name,
    resolve_configured_template,
    resolve_mission,
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


def _setup_all_tiers(
    tmp_path: Path,
    name: str = "spec-template.md",
    subdir: str = "templates",
    mission: str = "software-dev",
    *,
    global_home: Path | None = None,
    pkg_root: Path | None = None,
) -> dict[str, Path]:
    """Create the asset at every tier and return a mapping of tier->path."""
    project = tmp_path / "project"
    kittify = project / ".kittify"

    paths: dict[str, Path] = {}

    # Tier 1 -- override
    paths["override"] = _create_file(kittify / "overrides" / subdir / name)
    # Tier 2 -- legacy
    paths["legacy"] = _create_file(kittify / subdir / name)
    # Tier 3 -- global
    gh = global_home or (tmp_path / "global_home")
    paths["global"] = _create_file(gh / "missions" / mission / subdir / name)
    # Tier 4 -- package
    pr = pkg_root or (tmp_path / "pkg")
    paths["package"] = _create_file(pr / mission / subdir / name)

    return paths


def _resolved_mission_type(
    *,
    mission_type: str | None = "software-dev",
    template_set: dict[str, str] | None = None,
) -> ResolvedMissionType:
    """Build a narrow activated-context fixture without reading doctrine files."""
    mapping = {"spec": "configured-spec.md"} if template_set is None else template_set
    return ResolvedMissionType(
        mission_type=mission_type,
        governance_text="",
        action_sequence=[],
        provenance="builtin",
        _template_set_thunk=lambda: mapping,
    )


# ---------------------------------------------------------------------------
# Configured content-template selection (issue #2658)
# ---------------------------------------------------------------------------


class TestConfiguredTemplateResolution:
    """Artifact keys resolve through activated mission configuration."""

    @pytest.mark.parametrize(
        "mission_type",
        [
            "",
            "   ",
            "../..",
            "/absolute/type",
            "nested/type",
            r"nested\type",
            r"C:\missions\type",
            "C:type",
            ".",
            ".hidden-type",
        ],
        ids=[
            "empty",
            "whitespace",
            "parent-traversal",
            "absolute-posix",
            "nested-forward-separator",
            "nested-windows-separator",
            "windows-absolute-drive",
            "windows-drive-relative",
            "dot-segment",
            "hidden-segment",
        ],
    )
    def test_unsafe_mission_type_fails_before_mapping_or_file_resolution(
        self,
        tmp_path: Path,
        mission_type: str,
    ) -> None:
        mapping_resolver = Mock(side_effect=AssertionError("unsafe mission type read its template mapping"))
        context = ResolvedMissionType(
            mission_type=mission_type,
            governance_text="",
            action_sequence=[],
            provenance="forged-test-context",
            _template_set_thunk=mapping_resolver,
        )

        with (
            patch("specify_cli.runtime.resolver.resolve_template") as file_resolver,
            pytest.raises(TemplateConfigurationError) as exc_info,
        ):
            resolve_configured_template("spec", tmp_path, context)

        error = exc_info.value
        assert error.mission_type == mission_type
        assert error.artifact_kind == "spec"
        assert error.mapped_filename is None
        assert "unsafe mission type" in str(error)
        assert repr(mission_type) in str(error)
        assert isinstance(error.__cause__, ValueError)
        mapping_resolver.assert_not_called()
        file_resolver.assert_not_called()

    def test_safe_unactivated_forged_mission_type_cannot_escape_paths(
        self,
        tmp_path: Path,
    ) -> None:
        """Path safety is local; activation authenticity remains caller-owned."""
        mission_type = "forged-but-safe-custom"
        mapped_filename = "spec-template.md"
        context = _resolved_mission_type(
            mission_type=mission_type,
            template_set={"spec": mapped_filename},
        )
        expected = ResolutionResult(
            path=tmp_path / mapped_filename,
            tier=ResolutionTier.PACKAGE_DEFAULT,
            mission=mission_type,
        )

        with patch(
            "specify_cli.runtime.resolver.resolve_template",
            return_value=expected,
        ) as file_resolver:
            result = resolve_configured_template("spec", tmp_path, context)

        assert result is expected
        file_resolver.assert_called_once_with(
            mapped_filename,
            tmp_path,
            mission=mission_type,
        )

    def test_mapped_filename_preserves_project_override_precedence(self, tmp_path: Path) -> None:
        project = tmp_path / "project"
        override = _create_file(
            project / ".kittify" / "overrides" / "templates" / "configured-spec.md",
            "override",
        )
        _create_file(
            tmp_path / "global_home" / "missions" / "software-dev" / "templates" / "configured-spec.md",
            "global",
        )

        with patch(
            "specify_cli.runtime.resolver.get_kittify_home",
            return_value=tmp_path / "global_home",
        ):
            result = resolve_configured_template("spec", project, _resolved_mission_type())

        assert result == ResolutionResult(
            path=override,
            tier=ResolutionTier.OVERRIDE,
            mission="software-dev",
        )

    def test_mapped_filename_preserves_package_default_tier(self, tmp_path: Path) -> None:
        project = tmp_path / "project"
        package_root = tmp_path / "package"
        configured = _create_file(
            package_root / "software-dev" / "templates" / "configured-spec.md",
            "package",
        )

        with (
            patch(
                "specify_cli.runtime.resolver.get_kittify_home",
                return_value=tmp_path / "empty-home",
            ),
            patch(
                "specify_cli.runtime.resolver.get_package_asset_root",
                return_value=package_root,
            ),
        ):
            result = resolve_configured_template("spec", project, _resolved_mission_type())

        assert result.path == configured
        assert result.tier is ResolutionTier.PACKAGE_DEFAULT
        assert result.mission == "software-dev"

    @pytest.mark.parametrize("template_set", [None, {}])
    def test_null_or_missing_mapping_fails_before_file_resolution(
        self,
        tmp_path: Path,
        template_set: dict[str, str] | None,
    ) -> None:
        context = ResolvedMissionType(
            mission_type="documentation",
            governance_text="",
            action_sequence=[],
            provenance="builtin",
            _template_set_thunk=lambda: template_set,
        )

        with (
            patch("specify_cli.runtime.resolver.resolve_template") as file_resolver,
            pytest.raises(TemplateConfigurationError) as exc_info,
        ):
            resolve_configured_template("spec", tmp_path, context)

        assert exc_info.value.mission_type == "documentation"
        assert exc_info.value.artifact_kind == "spec"
        assert "documentation" in str(exc_info.value)
        assert "spec" in str(exc_info.value)
        file_resolver.assert_not_called()

    @pytest.mark.parametrize("mapped_filename", ["", "   "])
    def test_blank_mapped_filename_fails_before_file_resolution(self, tmp_path: Path, mapped_filename: str) -> None:
        context = _resolved_mission_type(template_set={"plan": mapped_filename})

        with (
            patch("specify_cli.runtime.resolver.resolve_template") as file_resolver,
            pytest.raises(TemplateConfigurationError, match="software-dev.*plan"),
        ):
            resolve_configured_template("plan", tmp_path, context)

        file_resolver.assert_not_called()

    @pytest.mark.parametrize(
        "mapped_filename",
        [
            "/etc/spec-template.md",
            "../spec-template.md",
            "nested/spec-template.md",
            r"nested\spec-template.md",
            r"C:\templates\spec-template.md",
            "C:spec-template.md",
            ".",
            ".spec-template.md",
            " spec-template.md",
            "spec-template.md ",
        ],
        ids=[
            "absolute-posix",
            "parent-traversal",
            "nested-forward-separator",
            "nested-windows-separator",
            "windows-absolute-drive",
            "windows-drive-relative",
            "dot-segment",
            "hidden-file",
            "leading-whitespace",
            "trailing-whitespace",
        ],
    )
    def test_unsafe_mapped_filename_fails_before_file_resolution(
        self,
        tmp_path: Path,
        mapped_filename: str,
    ) -> None:
        context = _resolved_mission_type(template_set={"spec": mapped_filename})

        with (
            patch("specify_cli.runtime.resolver.resolve_template") as file_resolver,
            pytest.raises(TemplateConfigurationError) as exc_info,
        ):
            resolve_configured_template("spec", tmp_path, context)

        error = exc_info.value
        assert error.mission_type == "software-dev"
        assert error.artifact_kind == "spec"
        assert error.mapped_filename == mapped_filename
        assert "unsafe filename" in str(error)
        assert repr(mapped_filename) in str(error)
        assert isinstance(error.__cause__, ValueError)
        file_resolver.assert_not_called()

    @pytest.mark.parametrize(
        "mapped_filename",
        [
            "CON",
            "con.md",
            "PrN.txt",
            "AUX.tar.gz",
            "nul.md",
            "CLOCK$.yaml",
            "COM1.md",
            "com9.MD",
            "LPT1",
            "lPt9.template",
            "spec-template.md.",
            "plan-template.md ",
        ],
        ids=[
            "con-bare",
            "con-extension-lowercase",
            "prn-extension-mixed-case",
            "aux-multiple-extensions",
            "nul-extension-lowercase",
            "clock-dollar-extension",
            "com-first",
            "com-last-lowercase",
            "lpt-first",
            "lpt-last-mixed-case",
            "trailing-dot",
            "trailing-space",
        ],
    )
    def test_windows_unsafe_mapped_filename_fails_before_file_resolution(
        self,
        tmp_path: Path,
        mapped_filename: str,
    ) -> None:
        context = _resolved_mission_type(template_set={"spec": mapped_filename})

        with (
            patch("specify_cli.runtime.resolver.resolve_template") as file_resolver,
            pytest.raises(TemplateConfigurationError) as exc_info,
        ):
            resolve_configured_template("spec", tmp_path, context)

        error = exc_info.value
        assert error.mission_type == "software-dev"
        assert error.artifact_kind == "spec"
        assert error.mapped_filename == mapped_filename
        assert "unsafe filename" in str(error)
        assert repr(mapped_filename) in str(error)
        assert isinstance(error.__cause__, ValueError)
        file_resolver.assert_not_called()

    @pytest.mark.parametrize("mapped_filename", ["spec-template.md", "plan-template.md"])
    def test_portable_mapped_filename_reaches_file_resolution(
        self,
        tmp_path: Path,
        mapped_filename: str,
    ) -> None:
        context = _resolved_mission_type(template_set={"spec": mapped_filename})
        expected = ResolutionResult(
            path=tmp_path / mapped_filename,
            tier=ResolutionTier.PACKAGE_DEFAULT,
            mission="software-dev",
        )

        with patch(
            "specify_cli.runtime.resolver.resolve_template",
            return_value=expected,
        ) as file_resolver:
            result = resolve_configured_template("spec", tmp_path, context)

        assert result is expected
        file_resolver.assert_called_once_with(
            mapped_filename,
            tmp_path,
            mission="software-dev",
        )

    def test_unresolved_mapped_filename_adds_configuration_context(self, tmp_path: Path) -> None:
        context = _resolved_mission_type(template_set={"plan": "configured-plan.md"})

        with (
            patch(
                "specify_cli.runtime.resolver.get_kittify_home",
                return_value=tmp_path / "empty-home",
            ),
            patch(
                "specify_cli.runtime.resolver.get_package_asset_root",
                side_effect=FileNotFoundError("no package"),
            ),
            pytest.raises(TemplateConfigurationError) as exc_info,
        ):
            resolve_configured_template("plan", tmp_path / "project", context)

        error = exc_info.value
        assert error.mission_type == "software-dev"
        assert error.artifact_kind == "plan"
        assert error.mapped_filename == "configured-plan.md"
        assert "configured-plan.md" in str(error)
        assert isinstance(error.__cause__, FileNotFoundError)

    def test_typeless_context_fails_without_software_development_inference(self, tmp_path: Path) -> None:
        context = _resolved_mission_type(
            mission_type=None,
            template_set={"spec": "configured-spec.md"},
        )

        with (
            patch("specify_cli.runtime.resolver.resolve_template") as file_resolver,
            pytest.raises(TemplateConfigurationError) as exc_info,
        ):
            resolve_configured_template("spec", tmp_path, context)

        assert exc_info.value.mission_type == "<typeless>"
        assert exc_info.value.artifact_kind == "spec"
        assert "<typeless>" in str(exc_info.value)
        file_resolver.assert_not_called()

    def test_mission_shim_reexports_configured_template_seam(self) -> None:
        from specify_cli.cli.commands.agent import mission

        assert mission.resolve_configured_template is resolve_configured_template


# ---------------------------------------------------------------------------
# T018 -- Resolution precedence tests (G2)
# ---------------------------------------------------------------------------


class TestResolutionPrecedence:
    """Test that the 4-tier precedence chain is respected."""

    def test_override_takes_precedence(self, tmp_path: Path) -> None:
        """When the asset exists at all tiers, override (tier 1) wins."""
        project = tmp_path / "project"
        global_home = tmp_path / "global_home"
        pkg_root = tmp_path / "pkg"

        paths = _setup_all_tiers(
            tmp_path,
            name="spec-template.md",
            subdir="templates",
            global_home=global_home,
            pkg_root=pkg_root,
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

        assert result.tier == ResolutionTier.OVERRIDE
        assert result.path == paths["override"]

    def test_legacy_takes_precedence_over_global(self, tmp_path: Path) -> None:
        """When override is absent, legacy (tier 2) wins over global (tier 3)."""
        project = tmp_path / "project"
        kittify = project / ".kittify"
        global_home = tmp_path / "global_home"
        pkg_root = tmp_path / "pkg"

        # Create legacy, global, package -- but NOT override
        _create_file(kittify / "templates" / "spec-template.md")
        _create_file(global_home / "missions" / "software-dev" / "templates" / "spec-template.md")
        _create_file(pkg_root / "software-dev" / "templates" / "spec-template.md")

        with (
            patch(
                "specify_cli.runtime.resolver.get_kittify_home",
                return_value=global_home,
            ),
            patch(
                "specify_cli.runtime.resolver.get_package_asset_root",
                return_value=pkg_root,
            ),
            warnings.catch_warnings(record=True) as w,
        ):
            warnings.simplefilter("always")
            result = resolve_template("spec-template.md", project)

        assert result.tier == ResolutionTier.LEGACY
        # Should have emitted a DeprecationWarning
        deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(deprecation_warnings) >= 1

    def test_global_resolves_when_no_override_or_legacy(self, tmp_path: Path) -> None:
        """When override and legacy are absent, global (tier 3) wins."""
        project = tmp_path / "project"
        (project / ".kittify").mkdir(parents=True)
        global_home = tmp_path / "global_home"
        pkg_root = tmp_path / "pkg"

        _create_file(global_home / "missions" / "software-dev" / "templates" / "spec-template.md")
        _create_file(pkg_root / "software-dev" / "templates" / "spec-template.md")

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

        assert result.tier == ResolutionTier.GLOBAL_MISSION

    def test_package_default_resolves_when_no_other_tiers(self, tmp_path: Path) -> None:
        """When only the package default exists, it resolves there."""
        project = tmp_path / "project"
        (project / ".kittify").mkdir(parents=True)
        pkg_root = tmp_path / "pkg"

        pkg_path = _create_file(pkg_root / "software-dev" / "templates" / "spec-template.md")

        with (
            patch(
                "specify_cli.runtime.resolver.get_kittify_home",
                return_value=tmp_path / "nonexistent_home",
            ),
            patch(
                "specify_cli.runtime.resolver.get_package_asset_root",
                return_value=pkg_root,
            ),
        ):
            result = resolve_template("spec-template.md", project)

        assert result.tier == ResolutionTier.PACKAGE_DEFAULT
        assert result.path == pkg_path

    def test_file_not_found_when_no_tier_has_asset(self, tmp_path: Path) -> None:
        """FileNotFoundError raised when no tier has the requested asset."""
        project = tmp_path / "project"
        (project / ".kittify").mkdir(parents=True)

        with (
            patch(
                "specify_cli.runtime.resolver.get_kittify_home",
                return_value=tmp_path / "empty_home",
            ),
            patch(
                "specify_cli.runtime.resolver.get_package_asset_root",
                side_effect=FileNotFoundError("no pkg"),
            ),
            pytest.raises(FileNotFoundError, match="not found in any resolution tier"),
        ):
            resolve_template("nonexistent.md", project)


# ---------------------------------------------------------------------------
# FR-001 / SC-002 -- converge the forked _resolve_asset tier-1 probe
# ---------------------------------------------------------------------------


class TestMissionScopedOverrideParity:
    """FR-001 / SC-002 (up-org-template-fsm-01M06F9K, WP01).

    ``charter.offering.resolver._resolve_asset`` (the doctrine-layer "sole door",
    used by ``charter list`` / ``show-origin``) has always probed a
    mission-scoped override at
    ``.kittify/overrides/missions/{mission}/{subdir}/{name}`` before the
    flat, non-mission-scoped override. ``specify_cli.runtime.resolver.
    _resolve_asset`` (the production ``mission create`` / plan-setup lane)
    did not -- a template installed at the mission-scoped path resolved for
    ``charter list`` but raised ``FileNotFoundError`` through ``mission
    create``. These tests prove both resolver modules now agree.
    """

    @pytest.mark.parametrize(
        "mission",
        ["software-dev", "research"],
        ids=["software-dev-mission", "research-mission"],
    )
    def test_mission_scoped_override_resolves_at_override_tier_in_both_resolvers(self, tmp_path: Path, mission: str) -> None:
        """A mission-scoped override resolves at ``ResolutionTier.OVERRIDE``
        through ``specify_cli.runtime.resolver``, with ``(path, tier)``
        identical to ``charter.offering.resolver``'s resolution of the same fixture.

        Before FR-001 lands, ``specify_cli.runtime.resolver.resolve_template``
        raises ``FileNotFoundError`` on this fixture (it only probes the
        flat, non-mission-scoped override path) while
        ``charter.offering.resolver.resolve_template`` already resolves it at
        ``ResolutionTier.OVERRIDE`` -- the exact regression documented by
        User Story 2's Independent Test.
        """
        import charter.offering.resolver as doctrine_resolver

        project = tmp_path / "project"
        mission_scoped_path = _create_file(project / ".kittify" / "overrides" / "missions" / mission / "templates" / "spec-template.md")

        with (
            patch(
                "specify_cli.runtime.resolver.get_kittify_home",
                return_value=tmp_path / "empty_home",
            ),
            patch(
                "specify_cli.runtime.resolver.get_package_asset_root",
                side_effect=FileNotFoundError("no pkg"),
            ),
        ):
            specify_result = resolve_template("spec-template.md", project, mission)

        doctrine_result = doctrine_resolver.resolve_template("spec-template.md", project, mission)

        assert specify_result.tier == ResolutionTier.OVERRIDE
        assert specify_result.path == mission_scoped_path
        assert (specify_result.path, specify_result.tier) == (
            doctrine_result.path,
            doctrine_result.tier,
        )

    def test_flat_override_still_wins_when_no_mission_scoped_override_exists(self, tmp_path: Path) -> None:
        """NFR-005: a project with no mission-scoped override resolves the
        flat ``.kittify/overrides/{subdir}/{name}`` override exactly as
        before -- the new probe must not change behavior for the common,
        non-mission-scoped case.
        """
        project = tmp_path / "project"
        flat_override_path = _create_file(project / ".kittify" / "overrides" / "templates" / "spec-template.md")

        with (
            patch(
                "specify_cli.runtime.resolver.get_kittify_home",
                return_value=tmp_path / "empty_home",
            ),
            patch(
                "specify_cli.runtime.resolver.get_package_asset_root",
                side_effect=FileNotFoundError("no pkg"),
            ),
        ):
            result = resolve_template("spec-template.md", project, "software-dev")

        assert result.tier == ResolutionTier.OVERRIDE
        assert result.path == flat_override_path


# ---------------------------------------------------------------------------
# T018 -- resolve_command and resolve_mission tests
# ---------------------------------------------------------------------------


class TestResolveCommand:
    """Test resolve_command follows the same 4-tier chain for command-templates/."""

    def test_override_wins_for_command(self, tmp_path: Path) -> None:
        project = tmp_path / "project"
        kittify = project / ".kittify"
        pkg_root = tmp_path / "pkg"

        override_path = _create_file(kittify / "overrides" / "command-templates" / "plan.md")
        _create_file(pkg_root / "software-dev" / "command-templates" / "plan.md")

        with (
            patch(
                "specify_cli.runtime.resolver.get_kittify_home",
                return_value=tmp_path / "no_home",
            ),
            patch(
                "specify_cli.runtime.resolver.get_package_asset_root",
                return_value=pkg_root,
            ),
        ):
            result = resolve_command("plan.md", project)

        assert result.tier == ResolutionTier.OVERRIDE
        assert result.path == override_path

    def test_package_fallback_for_command(self, tmp_path: Path) -> None:
        project = tmp_path / "project"
        (project / ".kittify").mkdir(parents=True)
        pkg_root = tmp_path / "pkg"

        pkg_path = _create_file(pkg_root / "software-dev" / "command-templates" / "implement.md")

        with (
            patch(
                "specify_cli.runtime.resolver.get_kittify_home",
                return_value=tmp_path / "no_home",
            ),
            patch(
                "specify_cli.runtime.resolver.get_package_asset_root",
                return_value=pkg_root,
            ),
        ):
            result = resolve_command("implement.md", project)

        assert result.tier == ResolutionTier.PACKAGE_DEFAULT
        assert result.path == pkg_path


class TestResolveMission:
    """Test resolve_mission for mission.yaml resolution."""

    def test_override_wins_for_mission(self, tmp_path: Path) -> None:
        project = tmp_path / "project"
        kittify = project / ".kittify"
        pkg_root = tmp_path / "pkg"

        override_path = _create_file(kittify / "overrides" / "missions" / "software-dev" / "mission.yaml")
        _create_file(pkg_root / "software-dev" / "mission.yaml")

        with (
            patch(
                "specify_cli.runtime.resolver.get_kittify_home",
                return_value=tmp_path / "no_home",
            ),
            patch(
                "specify_cli.runtime.resolver.get_package_asset_root",
                return_value=pkg_root,
            ),
        ):
            result = resolve_mission("software-dev", project)

        assert result.tier == ResolutionTier.OVERRIDE
        assert result.path == override_path
        assert result.mission == "software-dev"

    def test_legacy_mission_emits_warning(self, tmp_path: Path) -> None:
        project = tmp_path / "project"
        kittify = project / ".kittify"

        _create_file(kittify / "missions" / "research" / "mission.yaml")

        with (
            patch(
                "specify_cli.runtime.resolver.get_kittify_home",
                return_value=tmp_path / "no_home",
            ),
            patch(
                "specify_cli.runtime.resolver.get_package_asset_root",
                side_effect=FileNotFoundError("no pkg"),
            ),
            warnings.catch_warnings(record=True) as w,
        ):
            warnings.simplefilter("always")
            result = resolve_mission("research", project)

        assert result.tier == ResolutionTier.LEGACY
        assert result.mission == "research"
        deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(deprecation_warnings) >= 1

    def test_mission_not_found(self, tmp_path: Path) -> None:
        project = tmp_path / "project"
        (project / ".kittify").mkdir(parents=True)

        with (
            patch(
                "specify_cli.runtime.resolver.get_kittify_home",
                return_value=tmp_path / "no_home",
            ),
            patch(
                "specify_cli.runtime.resolver.get_package_asset_root",
                side_effect=FileNotFoundError("no pkg"),
            ),
            pytest.raises(FileNotFoundError, match="not found in any resolution tier"),
        ):
            resolve_mission("nonexistent", project)


# ---------------------------------------------------------------------------
# T019 -- Legacy resolution tests (F-Legacy)
# ---------------------------------------------------------------------------


class TestLegacyResolution:
    """Tests for the F-Legacy family of acceptance criteria."""

    def test_legacy_customized_resolves_with_warning(self, tmp_path: Path) -> None:
        """F-Legacy-001: A customized file in .kittify/templates/ resolves
        with a DeprecationWarning pointing the user to 'spec-kitty migrate'.
        """
        project = tmp_path / "project"
        kittify = project / ".kittify"

        legacy_path = _create_file(
            kittify / "templates" / "spec-template.md",
            content="# Custom override content\nUser-modified template.",
        )

        with (
            patch(
                "specify_cli.runtime.resolver.get_kittify_home",
                return_value=tmp_path / "no_home",
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
        assert result.path == legacy_path

        # Verify the exact DeprecationWarning shape
        deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(deprecation_warnings) == 1
        assert "spec-kitty migrate" in str(deprecation_warnings[0].message)
        assert "Legacy asset resolved" in str(deprecation_warnings[0].message)
        assert "next major version" in str(deprecation_warnings[0].message)

    def test_legacy_no_customization_resolves_with_warning(self, tmp_path: Path) -> None:
        """F-Legacy-002: Even an unmodified file at the legacy path resolves
        with the same deprecation warning (we don't diff against defaults).
        """
        project = tmp_path / "project"
        kittify = project / ".kittify"

        # Identical to package default -- still legacy tier
        legacy_path = _create_file(
            kittify / "command-templates" / "plan.md",
            content="# Default plan template",
        )

        pkg_root = tmp_path / "pkg"
        _create_file(
            pkg_root / "software-dev" / "command-templates" / "plan.md",
            content="# Default plan template",  # same content
        )

        with (
            patch(
                "specify_cli.runtime.resolver.get_kittify_home",
                return_value=tmp_path / "no_home",
            ),
            patch(
                "specify_cli.runtime.resolver.get_package_asset_root",
                return_value=pkg_root,
            ),
            warnings.catch_warnings(record=True) as w,
        ):
            warnings.simplefilter("always")
            result = resolve_command("plan.md", project)

        assert result.tier == ResolutionTier.LEGACY
        assert result.path == legacy_path

        deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(deprecation_warnings) == 1
        assert "Legacy asset resolved" in str(deprecation_warnings[0].message)

    def test_legacy_stale_differing_resolves_legacy_version(self, tmp_path: Path) -> None:
        """F-Legacy-003: When the legacy file differs from the global/package
        version, the legacy version is used (not global or package).
        """
        project = tmp_path / "project"
        kittify = project / ".kittify"
        global_home = tmp_path / "global_home"
        pkg_root = tmp_path / "pkg"

        legacy_path = _create_file(
            kittify / "templates" / "tasks-template.md",
            content="# Old stale legacy version",
        )
        _create_file(
            global_home / "missions" / "software-dev" / "templates" / "tasks-template.md",
            content="# Updated global version",
        )
        _create_file(
            pkg_root / "software-dev" / "templates" / "tasks-template.md",
            content="# Latest package default",
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
            warnings.catch_warnings(record=True) as w,
        ):
            warnings.simplefilter("always")
            result = resolve_template("tasks-template.md", project)

        # Legacy wins over global and package
        assert result.tier == ResolutionTier.LEGACY
        assert result.path == legacy_path
        assert result.path.read_text() == "# Old stale legacy version"

        deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(deprecation_warnings) == 1


# ---------------------------------------------------------------------------
# T018 -- ResolutionResult dataclass tests
# ---------------------------------------------------------------------------


class TestResolutionResult:
    """Verify ResolutionResult is frozen and has correct defaults."""

    def test_frozen(self, tmp_path: Path) -> None:
        r = ResolutionResult(path=tmp_path, tier=ResolutionTier.OVERRIDE)
        with pytest.raises(AttributeError):
            r.path = tmp_path / "other"  # type: ignore[misc]

    def test_mission_defaults_to_none(self, tmp_path: Path) -> None:
        r = ResolutionResult(path=tmp_path, tier=ResolutionTier.GLOBAL)
        assert r.mission is None

    def test_mission_can_be_set(self, tmp_path: Path) -> None:
        r = ResolutionResult(path=tmp_path, tier=ResolutionTier.PACKAGE_DEFAULT, mission="research")
        assert r.mission == "research"


# ---------------------------------------------------------------------------
# Init integration -- _resolve_mission_command_templates_dir uses 4-tier
# ---------------------------------------------------------------------------


class TestInitResolverIntegration:
    """Prove that init template discovery respects the full 4-tier chain.

    The helper ``_resolve_mission_command_templates_dir`` from ``init.py``
    should honour override and global tiers, not just project-local and
    package defaults.
    """

    def test_override_template_selected_over_package(self, tmp_path: Path) -> None:
        """An override-tier command template is used instead of the package default."""
        from specify_cli.cli.commands.init import _resolve_mission_command_templates_dir

        project = tmp_path / "project"
        kittify = project / ".kittify"
        pkg_root = tmp_path / "pkg"

        # Package default
        _create_file(
            pkg_root / "software-dev" / "command-templates" / "plan.md",
            content="# Package default plan",
        )

        # Override tier -- should win
        _create_file(
            kittify / "overrides" / "command-templates" / "plan.md",
            content="# Custom override plan",
        )

        with (
            patch(
                "specify_cli.runtime.resolver.get_kittify_home",
                return_value=tmp_path / "no_home",
            ),
            patch(
                "specify_cli.runtime.resolver.get_package_asset_root",
                return_value=pkg_root,
            ),
            # Also patch at the init module level (used in the discovery scan)
            patch(
                "specify_cli.cli.commands.init.get_kittify_home",
                return_value=tmp_path / "no_home",
            ),
            patch(
                "specify_cli.cli.commands.init.get_package_asset_root",
                return_value=pkg_root,
            ),
        ):
            resolved_dir = _resolve_mission_command_templates_dir(
                project,
                "software-dev",
                scratch_parent=tmp_path / "scratch",
            )

        plan_file = resolved_dir / "plan.md"
        assert plan_file.exists(), "plan.md should be in the resolved directory"
        assert plan_file.read_text() == "# Custom override plan"

    def test_global_template_selected_over_package(self, tmp_path: Path) -> None:
        """A global-tier command template is used when no override or legacy exists."""
        from specify_cli.cli.commands.init import _resolve_mission_command_templates_dir

        project = tmp_path / "project"
        (project / ".kittify").mkdir(parents=True)

        global_home = tmp_path / "global_home"
        pkg_root = tmp_path / "pkg"

        # Package default
        _create_file(
            pkg_root / "software-dev" / "command-templates" / "implement.md",
            content="# Package default implement",
        )

        # Global tier -- should win (no override, no legacy)
        _create_file(
            global_home / "missions" / "software-dev" / "command-templates" / "implement.md",
            content="# Global custom implement",
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
            patch(
                "specify_cli.cli.commands.init.get_kittify_home",
                return_value=global_home,
            ),
            patch(
                "specify_cli.cli.commands.init.get_package_asset_root",
                return_value=pkg_root,
            ),
        ):
            resolved_dir = _resolve_mission_command_templates_dir(
                project,
                "software-dev",
                scratch_parent=tmp_path / "scratch",
            )

        impl_file = resolved_dir / "implement.md"
        assert impl_file.exists(), "implement.md should be in the resolved directory"
        assert impl_file.read_text() == "# Global custom implement"

    def test_mixed_tiers_each_file_resolved_independently(self, tmp_path: Path) -> None:
        """Different files can be resolved from different tiers simultaneously."""
        from specify_cli.cli.commands.init import _resolve_mission_command_templates_dir

        project = tmp_path / "project"
        kittify = project / ".kittify"
        global_home = tmp_path / "global_home"
        pkg_root = tmp_path / "pkg"

        # plan.md -- override wins
        _create_file(
            kittify / "overrides" / "command-templates" / "plan.md",
            content="# Override plan",
        )
        _create_file(
            pkg_root / "software-dev" / "command-templates" / "plan.md",
            content="# Package plan",
        )

        # implement.md -- global wins (no override, no legacy)
        _create_file(
            global_home / "missions" / "software-dev" / "command-templates" / "implement.md",
            content="# Global implement",
        )
        _create_file(
            pkg_root / "software-dev" / "command-templates" / "implement.md",
            content="# Package implement",
        )

        # review.md -- only at package level
        _create_file(
            pkg_root / "software-dev" / "command-templates" / "review.md",
            content="# Package review",
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
            patch(
                "specify_cli.cli.commands.init.get_kittify_home",
                return_value=global_home,
            ),
            patch(
                "specify_cli.cli.commands.init.get_package_asset_root",
                return_value=pkg_root,
            ),
        ):
            resolved_dir = _resolve_mission_command_templates_dir(
                project,
                "software-dev",
                scratch_parent=tmp_path / "scratch",
            )

        assert (resolved_dir / "plan.md").read_text() == "# Override plan"
        assert (resolved_dir / "implement.md").read_text() == "# Global implement"
        assert (resolved_dir / "review.md").read_text() == "# Package review"

    def test_empty_result_when_no_tiers_have_templates(self, tmp_path: Path) -> None:
        """Returns an empty directory when no templates exist anywhere."""
        from specify_cli.cli.commands.init import _resolve_mission_command_templates_dir

        project = tmp_path / "project"
        (project / ".kittify").mkdir(parents=True)

        with (
            patch(
                "specify_cli.runtime.resolver.get_kittify_home",
                return_value=tmp_path / "no_home",
            ),
            patch(
                "specify_cli.runtime.resolver.get_package_asset_root",
                side_effect=FileNotFoundError("no pkg"),
            ),
            patch(
                "specify_cli.cli.commands.init.get_kittify_home",
                return_value=tmp_path / "no_home",
            ),
            patch(
                "specify_cli.cli.commands.init.get_package_asset_root",
                side_effect=FileNotFoundError("no pkg"),
            ),
        ):
            resolved_dir = _resolve_mission_command_templates_dir(
                project,
                "software-dev",
                scratch_parent=tmp_path / "scratch",
            )

        assert resolved_dir.is_dir()
        assert list(resolved_dir.glob("*.md")) == []


# ---------------------------------------------------------------------------
# WP03 (FR-004, FR-005) -- org tier in specify_cli.runtime.resolver's
# _resolve_asset and resolve_mission, routed through the production
# resolve_configured_template lane. Slots between LEGACY and GLOBAL_MISSION,
# sourced from charter.drg.resolve_org_roots via the lazy facade import
# (DEC-003) -- never a direct doctrine.* import from this module.
# ---------------------------------------------------------------------------


def _write_org_pack_config(repo_root: Path, *, pack_name: str, local_path: Path) -> None:
    """Write a canonical ``doctrine.org.packs[].local_path`` config.yaml entry."""
    config_dir = repo_root / ".kittify"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.yaml").write_text(
        f"doctrine:\n  org:\n    packs:\n      - name: {pack_name}\n        local_path: {local_path}\n",
        encoding="utf-8",
    )


class TestOrgTierResolution:
    """WP03 -- org tier through both _resolve_asset and resolve_mission."""

    def test_org_tier_resolves_configured_template_through_production_lane(self, tmp_path: Path) -> None:
        """FR-004: an org-pack ``spec-template.md`` resolves at
        ``ResolutionTier.ORG`` through the exact production
        ``resolve_configured_template`` call ``mission create`` uses.

        Before this WP: no tier between LEGACY and GLOBAL_MISSION probed org
        roots, so this fixture fell through to PACKAGE_DEFAULT (see the WP
        report for the exact pre-fix measurement).
        """
        project = tmp_path / "project"
        project.mkdir()
        org_root = tmp_path / "org-pack"
        org_template = org_root / "missions" / "software-dev" / "templates" / "spec-template.md"
        org_template.parent.mkdir(parents=True)
        org_template.write_text("org template", encoding="utf-8")

        _write_org_pack_config(project, pack_name="acme", local_path=org_root)

        context = _resolved_mission_type(template_set={"spec": "spec-template.md"})

        with patch(
            "specify_cli.runtime.resolver.get_kittify_home",
            return_value=tmp_path / "no_home",
        ):
            result = resolve_configured_template("spec", project, context)

        assert result.tier == ResolutionTier.ORG
        assert result.path == org_template
        assert result.mission == "software-dev"

    def test_org_tier_resolves_mission_yaml(self, tmp_path: Path) -> None:
        """FR-005: an org-pack ``mission.yaml`` resolves at
        ``ResolutionTier.ORG``, at the same relative position as the
        template case."""
        project = tmp_path / "project"
        project.mkdir()
        org_root = tmp_path / "org-pack"
        org_mission = org_root / "missions" / "software-dev" / "mission.yaml"
        org_mission.parent.mkdir(parents=True)
        org_mission.write_text("name: org\n", encoding="utf-8")

        _write_org_pack_config(project, pack_name="acme", local_path=org_root)

        with patch(
            "specify_cli.runtime.resolver.get_kittify_home",
            return_value=tmp_path / "no_home",
        ):
            result = resolve_mission("software-dev", project)

        assert result.tier == ResolutionTier.ORG
        assert result.path == org_mission
        assert result.mission == "software-dev"

    def test_org_tier_sits_below_project_override(self, tmp_path: Path) -> None:
        """User Story 1, Acceptance Scenario 2: a project override still
        wins over an org-pack asset -- the org tier sits below OVERRIDE, not
        above it."""
        project = tmp_path / "project"
        org_root = tmp_path / "org-pack"
        org_template = org_root / "missions" / "software-dev" / "templates" / "spec-template.md"
        org_template.parent.mkdir(parents=True)
        org_template.write_text("org template", encoding="utf-8")

        _write_org_pack_config(project, pack_name="acme", local_path=org_root)

        override_asset = _create_file(
            project / ".kittify" / "overrides" / "missions" / "software-dev" / "templates" / "spec-template.md",
            content="project override",
        )

        with patch(
            "specify_cli.runtime.resolver.get_kittify_home",
            return_value=tmp_path / "no_home",
        ):
            result = resolve_template("spec-template.md", project, "software-dev")

        assert result.tier == ResolutionTier.OVERRIDE
        assert result.path == override_asset

    def test_org_tier_falls_through_when_org_pack_missing_asset(self, tmp_path: Path) -> None:
        """A configured org pack that does not contain the requested asset
        is a miss, not an error -- resolution falls through to the next
        tier."""
        project = tmp_path / "project"
        project.mkdir()
        org_root = tmp_path / "org-pack"
        org_root.mkdir()  # configured, but has no missions/ subtree at all

        _write_org_pack_config(project, pack_name="acme", local_path=org_root)

        global_home = tmp_path / "global_home"
        global_template = _create_file(global_home / "missions" / "software-dev" / "templates" / "spec-template.md")

        with patch(
            "specify_cli.runtime.resolver.get_kittify_home",
            return_value=global_home,
        ):
            result = resolve_template("spec-template.md", project, "software-dev")

        assert result.tier == ResolutionTier.GLOBAL_MISSION
        assert result.path == global_template

    def test_no_org_packs_configured_is_a_noop(self, tmp_path: Path) -> None:
        """NFR-005/SC-007: with zero ``doctrine.org.packs`` entries (no
        ``.kittify/config.yaml`` at all -- the overwhelmingly common case),
        resolution is byte-identical to before this WP: same path, same
        tier."""
        project = tmp_path / "project"
        project.mkdir()
        global_home = tmp_path / "global_home"
        global_template = _create_file(global_home / "missions" / "software-dev" / "templates" / "spec-template.md")

        with patch(
            "specify_cli.runtime.resolver.get_kittify_home",
            return_value=global_home,
        ):
            result = resolve_template("spec-template.md", project, "software-dev")

        assert result.tier == ResolutionTier.GLOBAL_MISSION
        assert result.path == global_template

    def test_malformed_org_config_still_resolves_package_default(self, tmp_path: Path) -> None:
        """NFR-001(b): a malformed ``.kittify/config.yaml`` still resolves
        built-in templates through the production lane, with zero org roots
        contributed (``load_pack_registry``'s pre-existing fail-soft,
        exercised through the new org tier -- not a new try/except added by
        this WP).

        Regression guard (pre-merge lens, mission
        ``up-org-template-fsm-01M06F9K``): resolution is a hot path that may
        run many times per invocation. A project with no readable org-pack
        intent (this config can't even be parsed) must see ZERO new warning
        output -- NFR-005/SC-007 requires byte-identical behaviour, explicitly
        including "same log output, no new warnings", for a project with no
        org pack configured. Before the fix this asserted the opposite
        (``pytest.warns(UserWarning)``), codifying the regression as
        expected."""
        project = tmp_path / "project"
        kittify = project / ".kittify"
        kittify.mkdir(parents=True)
        (kittify / "config.yaml").write_text("not: [valid, doctrine.org.packs shape\n", encoding="utf-8")

        pkg_root = tmp_path / "pkg"
        pkg_template = _create_file(pkg_root / "software-dev" / "templates" / "spec-template.md")

        with (
            patch(
                "specify_cli.runtime.resolver.get_kittify_home",
                return_value=tmp_path / "no_home",
            ),
            patch(
                "specify_cli.runtime.resolver.get_package_asset_root",
                return_value=pkg_root,
            ),
            warnings.catch_warnings(record=True) as caught,
        ):
            warnings.simplefilter("always")
            result = resolve_template("spec-template.md", project, "software-dev")

        assert caught == []
        assert result.tier == ResolutionTier.PACKAGE_DEFAULT
        assert result.path == pkg_template

    def test_declared_but_broken_org_pack_still_warns(self, tmp_path: Path) -> None:
        """Positive case for the fix above: a config that DOES declare
        ``doctrine.org.packs`` but fails schema validation (two packs
        sharing the same ``name``) is a genuinely misconfigured org pack --
        the operator demonstrably opted in and deserves to know it's
        broken. Unlike the unparseable-file case above, that signal must
        remain a loud ``UserWarning`` through this same resolution hot
        path."""
        project = tmp_path / "project"
        kittify = project / ".kittify"
        kittify.mkdir(parents=True)
        acme_one = tmp_path / "acme-one"
        acme_two = tmp_path / "acme-two"
        (kittify / "config.yaml").write_text(
            f"doctrine:\n  org:\n    packs:\n      - name: acme\n        local_path: {acme_one}\n      - name: acme\n        local_path: {acme_two}\n",
            encoding="utf-8",
        )

        pkg_root = tmp_path / "pkg"
        pkg_template = _create_file(pkg_root / "software-dev" / "templates" / "spec-template.md")

        with (
            patch(
                "specify_cli.runtime.resolver.get_kittify_home",
                return_value=tmp_path / "no_home",
            ),
            patch(
                "specify_cli.runtime.resolver.get_package_asset_root",
                return_value=pkg_root,
            ),
            warnings.catch_warnings(record=True) as caught,
        ):
            warnings.simplefilter("always")
            result = resolve_template("spec-template.md", project, "software-dev")

        assert len(caught) == 1
        assert "Invalid org-pack config" in str(caught[0].message)
        assert result.tier == ResolutionTier.PACKAGE_DEFAULT
        assert result.path == pkg_template

    def test_org_tier_propagates_subdir_escape_error(self, tmp_path: Path) -> None:
        """NFR-001(a)/DEC-005: OrgPackSubdirEscapeError is not swallowed by
        the new org tier -- it propagates out of resolve_template exactly as
        it does out of resolve_org_roots itself. A blanket
        ``except Exception`` around resolve_org_roots() would silently
        regress this."""
        from charter.offering.drg.org_pack_config import OrgPackSubdirEscapeError

        project = tmp_path / "project"
        pack_root = tmp_path / "org-pack"
        pack_root.mkdir(parents=True)
        outside_dir = tmp_path / "outside"
        outside_dir.mkdir()
        (pack_root / "escape").symlink_to(outside_dir)

        config_dir = project / ".kittify"
        config_dir.mkdir(parents=True)
        (config_dir / "config.yaml").write_text(
            f"doctrine:\n  org:\n    packs:\n      - name: acme\n        local_path: {pack_root}\n        subdir: escape\n",
            encoding="utf-8",
        )

        with pytest.raises(OrgPackSubdirEscapeError):
            resolve_template("spec-template.md", project, "software-dev")

    def test_org_tier_matches_doctrine_resolver_for_same_fixture(self, tmp_path: Path) -> None:
        """Position-parity spot check: given the identical org-pack fixture,
        ``specify_cli.runtime.resolver`` and ``charter.offering.resolver`` resolve
        the same ``(path, tier)`` -- mirroring
        ``TestMissionScopedOverrideParity``'s parity discipline for the org
        tier."""
        import charter.offering.resolver as doctrine_resolver

        project = tmp_path / "project"
        project.mkdir()
        org_root = tmp_path / "org-pack"
        org_template = org_root / "missions" / "software-dev" / "templates" / "spec-template.md"
        org_template.parent.mkdir(parents=True)
        org_template.write_text("org template", encoding="utf-8")

        _write_org_pack_config(project, pack_name="acme", local_path=org_root)

        with patch(
            "specify_cli.runtime.resolver.get_kittify_home",
            return_value=tmp_path / "no_home",
        ):
            specify_result = resolve_template("spec-template.md", project, "software-dev")

        doctrine_result = doctrine_resolver.resolve_template("spec-template.md", project, "software-dev")

        assert specify_result.tier == ResolutionTier.ORG
        assert (specify_result.path, specify_result.tier.name) == (
            doctrine_result.path,
            doctrine_result.tier.name,
        )


# ---------------------------------------------------------------------------
# Manifest-schema error boundary parity (planning#249)
# ---------------------------------------------------------------------------


class TestExpectedArtifactManifestSchemaErrorBoundary:
    """A schema-invalid ``expected-artifacts.yaml`` must fail loud through
    ``ManifestSchemaError`` -- the same domain-error shape
    ``specify_cli.dossier.manifest.ManifestRegistry.load_manifest`` raises
    for its own manifest-load boundary -- rather than leaking the raw
    ``pydantic.ValidationError`` this seam's ``try`` block used to swallow
    into a bare ``False``/``None`` (squad finding on #233, this issue)."""

    _TYPO_FIXTURE_PATH = Path(__file__).parent.parent / "dossier" / "fixtures" / "expected_artifacts_typo.yaml"

    def _patch_schema_invalid_manifest(self, monkeypatch: pytest.MonkeyPatch, origin: str) -> None:
        import ruamel.yaml

        from charter.activation import manifest_loader
        from charter.offering.missions.repository import ConfigResult

        content = self._TYPO_FIXTURE_PATH.read_text(encoding="utf-8")
        parsed = ruamel.yaml.YAML(typ="safe").load(content)

        class _FakeRepository:
            def get_expected_artifacts(self, mission: str) -> ConfigResult | None:
                return ConfigResult(content=content, origin=origin, parsed=parsed)

        monkeypatch.setattr(
            manifest_loader,
            "_doctrine_repository",
            lambda: _FakeRepository(),
        )

    def test_resolve_configured_artifact_name_raises_manifest_schema_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from pydantic import ValidationError

        from specify_cli.dossier.manifest import ManifestSchemaError

        distinctive_origin = "doctrine/typo-fixture/expected-artifacts.yaml"
        self._patch_schema_invalid_manifest(monkeypatch, origin=distinctive_origin)

        with pytest.raises(ManifestSchemaError) as exc_info:
            resolve_configured_artifact_name("input.spec.main", "typo-fixture")

        assert exc_info.value.mission_type == "typo-fixture"
        assert exc_info.value.origin == distinctive_origin
        assert isinstance(exc_info.value.__cause__, ValidationError)

    def test_required_artifacts_for_raises_manifest_schema_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from specify_cli.dossier.manifest import ManifestSchemaError

        self._patch_schema_invalid_manifest(monkeypatch, origin="test-fixture")

        with pytest.raises(ManifestSchemaError):
            required_artifacts_for("specify", "typo-fixture")
