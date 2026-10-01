"""Tests for the show_origin module.

Covers:
- T025: collect_origins() function
- T027: Tier labels match actual resolution (1A-14, 1A-15)
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch


from specify_cli.runtime.show_origin import (
    OriginEntry,
    _discover_mission_names,
    collect_origins,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

def _create_file(path: Path, content: str = "placeholder") -> Path:
    """Create a file (and any missing parent dirs), return its path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


# ---------------------------------------------------------------------------
# T025 -- collect_origins() basic tests
# ---------------------------------------------------------------------------


class TestCollectOriginsBasic:
    """Test that collect_origins() returns entries for all known assets."""

    def test_returns_entries_for_all_asset_types(self, tmp_path: Path) -> None:
        """collect_origins returns entries covering templates, commands, missions, scripts, and files."""
        project = tmp_path / "project"
        (project / ".kittify").mkdir(parents=True)
        pkg_root = tmp_path / "pkg"

        # Create a minimal package layout so dynamic discovery works
        for name in ["spec-template.md", "plan-template.md", "tasks-template.md", "task-prompt-template.md"]:
            _create_file(pkg_root / "software-dev" / "templates" / name)
        for name in ["specify.md", "plan.md", "tasks.md", "implement.md"]:
            _create_file(pkg_root / "software-dev" / "command-templates" / name)
        for mission in ["software-dev", "research", "documentation"]:
            _create_file(pkg_root / mission / "mission.yaml")

        with (
            patch(
                "specify_cli.runtime.resolver.get_kittify_home",
                return_value=tmp_path / "no_home",
            ),
            patch(
                "specify_cli.runtime.resolver.get_package_asset_root",
                return_value=pkg_root,
            ),
            patch(
                "specify_cli.runtime.show_origin.get_package_asset_root",
                return_value=pkg_root,
            ),
        ):
            entries = collect_origins(project)

        asset_types = {e.asset_type for e in entries}
        # PRD §6.4 requires templates, commands, missions, scripts, and AGENTS.md (file)
        assert "template" in asset_types
        assert "command" in asset_types
        assert "mission" in asset_types
        assert "file" in asset_types  # AGENTS.md

    def test_all_entries_are_origin_entry_instances(self, tmp_path: Path) -> None:
        """All returned items are OriginEntry dataclass instances."""
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
                "specify_cli.runtime.show_origin.get_package_asset_root",
                side_effect=FileNotFoundError("no pkg"),
            ),
        ):
            entries = collect_origins(project)

        for entry in entries:
            assert isinstance(entry, OriginEntry)

    def test_missing_resolver_assets_have_error_and_no_path(self, tmp_path: Path) -> None:
        """When no tier provides a resolver-based asset, error is set and path/tier are None."""
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
                "specify_cli.runtime.show_origin.get_package_asset_root",
                side_effect=FileNotFoundError("no pkg"),
            ),
        ):
            entries = collect_origins(project)

        resolver_entries = [
            e for e in entries if e.asset_type in ("template", "command", "mission")
        ]
        assert len(resolver_entries) > 0
        for entry in resolver_entries:
            assert entry.resolved_path is None
            assert entry.tier is None
            assert entry.error is not None

    def test_asset_types_include_correct_entries(self, tmp_path: Path) -> None:
        """Each asset type category has the expected entries."""
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
                "specify_cli.runtime.show_origin.get_package_asset_root",
                side_effect=FileNotFoundError("no pkg"),
            ),
        ):
            entries = collect_origins(project)

        template_entries = [e for e in entries if e.asset_type == "template"]
        command_entries = [e for e in entries if e.asset_type == "command"]
        mission_entries = [e for e in entries if e.asset_type == "mission"]
        file_entries = [e for e in entries if e.asset_type == "file"]

        # Dynamic discovery falls back to hardcoded lists when package not available
        assert len(template_entries) >= 4  # At least the 4 fallback templates
        assert len(command_entries) >= 7  # At least the 7 fallback commands (dashboard removed, #5530)
        assert len(mission_entries) >= 3  # At least software-dev, research, documentation
        assert len(file_entries) >= 1  # AGENTS.md


# ---------------------------------------------------------------------------
# T027 -- Tier labels match actual resolution (1A-14, 1A-15)
# ---------------------------------------------------------------------------


class TestShowOriginTierLabels:
    """Each tier label corresponds to actual resolved file (1A-14, 1A-15)."""

    def test_override_tier_label(self, tmp_path: Path) -> None:
        """Override-tier asset gets 'override' label."""
        project = tmp_path / "project"
        override_path = _create_file(
            project / ".kittify" / "overrides" / "templates" / "spec-template.md",
            content="override",
        )
        pkg_root = tmp_path / "pkg"
        _create_file(pkg_root / "software-dev" / "templates" / "spec-template.md")

        with (
            patch(
                "specify_cli.runtime.resolver.get_kittify_home",
                return_value=tmp_path / "no_home",
            ),
            patch(
                "specify_cli.runtime.resolver.get_package_asset_root",
                return_value=pkg_root,
            ),
            patch(
                "specify_cli.runtime.show_origin.get_package_asset_root",
                return_value=pkg_root,
            ),
        ):
            entries = collect_origins(project)

        spec_entry = next(e for e in entries if e.name == "spec-template.md")
        assert spec_entry.tier == "override"
        assert spec_entry.resolved_path == override_path

    def test_global_tier_label(self, tmp_path: Path) -> None:
        """Global-tier asset gets 'global' label."""
        project = tmp_path / "project"
        (project / ".kittify").mkdir(parents=True)
        global_home = tmp_path / "global_home"

        global_path = _create_file(
            global_home / "missions" / "software-dev" / "templates" / "plan-template.md",
            content="global",
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
            patch(
                "specify_cli.runtime.show_origin.get_package_asset_root",
                side_effect=FileNotFoundError("no pkg"),
            ),
        ):
            entries = collect_origins(project)

        plan_entry = next(e for e in entries if e.name == "plan-template.md")
        assert plan_entry.tier == "global_mission"
        assert plan_entry.resolved_path == global_path

    def test_package_default_tier_label(self, tmp_path: Path) -> None:
        """Package-default-tier asset gets 'package_default' label."""
        project = tmp_path / "project"
        (project / ".kittify").mkdir(parents=True)
        pkg_root = tmp_path / "pkg"

        pkg_path = _create_file(
            pkg_root / "software-dev" / "templates" / "tasks-template.md",
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
            patch(
                "specify_cli.runtime.show_origin.get_package_asset_root",
                return_value=pkg_root,
            ),
        ):
            entries = collect_origins(project)

        tasks_entry = next(e for e in entries if e.name == "tasks-template.md")
        assert tasks_entry.tier == "package_default"
        assert tasks_entry.resolved_path == pkg_path

    def test_mixed_tiers_in_single_call(self, tmp_path: Path) -> None:
        """Different assets can resolve at different tiers in the same call."""
        project = tmp_path / "project"
        global_home = tmp_path / "global_home"
        pkg_root = tmp_path / "pkg"

        # Ensure all 3 templates exist at package level so dynamic discovery finds them
        for name in ["spec-template.md", "plan-template.md", "tasks-template.md"]:
            _create_file(pkg_root / "software-dev" / "templates" / name, content="package")

        # spec-template.md at override tier (wins over package)
        _create_file(
            project / ".kittify" / "overrides" / "templates" / "spec-template.md",
            content="override",
        )

        # plan-template.md at global tier (wins over package)
        _create_file(
            global_home / "missions" / "software-dev" / "templates" / "plan-template.md",
            content="global",
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
                "specify_cli.runtime.show_origin.get_package_asset_root",
                return_value=pkg_root,
            ),
        ):
            entries = collect_origins(project)

        spec_entry = next(e for e in entries if e.name == "spec-template.md")
        plan_entry = next(e for e in entries if e.name == "plan-template.md")
        tasks_entry = next(e for e in entries if e.name == "tasks-template.md")

        assert spec_entry.tier == "override"
        assert plan_entry.tier == "global_mission"
        assert tasks_entry.tier == "package_default"

    def test_command_tier_labels(self, tmp_path: Path) -> None:
        """Command templates also get correct tier labels."""
        project = tmp_path / "project"
        pkg_root = tmp_path / "pkg"

        # Ensure both commands exist at package level so dynamic discovery finds them
        _create_file(pkg_root / "software-dev" / "command-templates" / "specify.md")
        _create_file(pkg_root / "software-dev" / "command-templates" / "plan.md")

        # Put specify.md at override (wins over package)
        _create_file(
            project / ".kittify" / "overrides" / "command-templates" / "specify.md",
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
            patch(
                "specify_cli.runtime.show_origin.get_package_asset_root",
                return_value=pkg_root,
            ),
        ):
            entries = collect_origins(project)

        specify_cmd = next(
            e for e in entries if e.asset_type == "command" and e.name == "specify.md"
        )
        plan_cmd = next(
            e for e in entries if e.asset_type == "command" and e.name == "plan.md"
        )

        assert specify_cmd.tier == "override"
        assert plan_cmd.tier == "package_default"

    def test_mission_tier_labels(self, tmp_path: Path) -> None:
        """Mission configs get correct tier labels."""
        project = tmp_path / "project"
        pkg_root = tmp_path / "pkg"

        # Ensure both missions exist at package level so dynamic discovery finds them
        _create_file(pkg_root / "software-dev" / "mission.yaml")
        _create_file(pkg_root / "research" / "mission.yaml")

        # software-dev at override (wins over package)
        _create_file(
            project / ".kittify" / "overrides" / "missions" / "software-dev" / "mission.yaml",
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
            patch(
                "specify_cli.runtime.show_origin.get_package_asset_root",
                return_value=pkg_root,
            ),
        ):
            entries = collect_origins(project)

        sw_entry = next(
            e for e in entries if e.asset_type == "mission" and e.name == "software-dev"
        )
        res_entry = next(
            e for e in entries if e.asset_type == "mission" and e.name == "research"
        )

        assert sw_entry.tier == "override"
        assert res_entry.tier == "package_default"

    def test_custom_mission_parameter(self, tmp_path: Path) -> None:
        """collect_origins respects the mission parameter for templates/commands."""
        project = tmp_path / "project"
        (project / ".kittify").mkdir(parents=True)
        pkg_root = tmp_path / "pkg"

        # Create template under research mission
        _create_file(
            pkg_root / "research" / "templates" / "spec-template.md",
        )
        _create_file(
            pkg_root / "research" / "mission.yaml",
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
            patch(
                "specify_cli.runtime.show_origin.get_package_asset_root",
                return_value=pkg_root,
            ),
        ):
            entries = collect_origins(project, mission="research")

        spec_entry = next(e for e in entries if e.name == "spec-template.md")
        assert spec_entry.tier == "package_default"
        assert spec_entry.resolved_path is not None


class TestDiscoverMissionNamesFallback:
    """The OSError fallback is single-sourced from the doctrine roster (#2669)."""

    def test_oserror_fallback_returns_canonical_roster_including_plan(self) -> None:
        from charter.offering.missions.mission_type_repository import builtin_mission_type_ids

        with patch(
            "specify_cli.runtime.show_origin.get_package_asset_root",
            side_effect=OSError("no package assets"),
        ):
            names = _discover_mission_names()

        # Derived from the single source, not a hand-kept partial list. The old
        # literal was missing ``plan``; the fallback must now include it.
        assert names == sorted(builtin_mission_type_ids())
        assert "plan" in names
