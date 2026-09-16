"""Integration tests for spec-kitty profiles CLI command."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli import app as cli_app

# Marked for mutmut sandbox skip — subprocess CLI invocation.
pytestmark = [pytest.mark.non_sandbox, pytest.mark.fast]

runner = CliRunner()

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "profiles"


def _strip_readiness_banner(output: str) -> str:
    """Drop environment-specific connected-teamspace readiness banner."""
    lines = output.splitlines()
    if lines and lines[0].startswith("spec-kitty: logged_out_on_connected_teamspace "):
        return "\n".join(lines[1:]) + ("\n" if output.endswith("\n") else "")
    return output


def _json_payload(output: str):
    return json.loads(_strip_readiness_banner(output))


def _setup_project(tmp_path: Path) -> Path:
    """Set up a minimal project structure with fixture profiles."""
    kittify_dir = tmp_path / ".kittify"
    kittify_dir.mkdir(parents=True)
    profiles_dir = kittify_dir / "profiles"
    profiles_dir.mkdir()
    for yaml_file in FIXTURES_DIR.glob("*.agent.yaml"):
        shutil.copy(yaml_file, profiles_dir / yaml_file.name)
    return tmp_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestProfilesListJsonOutput:
    def test_exits_zero_and_returns_valid_json(self, tmp_path: Path) -> None:
        project = _setup_project(tmp_path)
        with patch("specify_cli.cli.commands.profiles_cmd.find_repo_root", return_value=project):
            result = runner.invoke(cli_app, ["profiles", "list", "--json"])
        assert result.exit_code == 0, result.output
        data = _json_payload(result.output)
        assert isinstance(data, list)

    def test_json_output_has_required_fields(self, tmp_path: Path) -> None:
        project = _setup_project(tmp_path)
        with patch("specify_cli.cli.commands.profiles_cmd.find_repo_root", return_value=project):
            result = runner.invoke(cli_app, ["profiles", "list", "--json"])
        assert result.exit_code == 0
        profiles = _json_payload(result.output)
        assert len(profiles) >= 1
        for p in profiles:
            assert "profile_id" in p
            assert "identifier" in p
            assert p["identifier"] == p["profile_id"]
            assert "name" in p
            assert "role" in p
            assert "action_domains" in p
            assert "source" in p

    def test_json_output_includes_fixture_profiles(self, tmp_path: Path) -> None:
        project = _setup_project(tmp_path)
        with patch("specify_cli.cli.commands.profiles_cmd.find_repo_root", return_value=project):
            result = runner.invoke(cli_app, ["profiles", "list", "--json"])
        profiles = _json_payload(result.output)
        profile_ids = [p["profile_id"] for p in profiles]
        assert "implementer-fixture" in profile_ids


class TestProfilesListTableOutput:
    def test_exits_zero_with_table_output(self, tmp_path: Path) -> None:
        project = _setup_project(tmp_path)
        with patch("specify_cli.cli.commands.profiles_cmd.find_repo_root", return_value=project):
            result = runner.invoke(cli_app, ["profiles", "list"])
        assert result.exit_code == 0, result.output
        # Table title should appear in output
        assert "Profile" in result.output or "profile" in result.output.lower()

    def test_table_output_contains_profile_ids(self, tmp_path: Path) -> None:
        project = _setup_project(tmp_path)
        with patch("specify_cli.cli.commands.profiles_cmd.find_repo_root", return_value=project):
            result = runner.invoke(cli_app, ["profiles", "list"])
        assert result.exit_code == 0
        assert "implementer-fixture" in _strip_readiness_banner(result.output)


class TestProfilesListNoProfiles:
    def test_no_profiles_json_returns_empty_array(self, tmp_path: Path) -> None:
        """When no profiles are returned, --json outputs empty array."""
        project = tmp_path
        (project / ".kittify").mkdir(parents=True)

        # R3: the display catalog now derives from ``_profile_catalog`` (the
        # ungated built-in + legacy + doctrine view), not the gated routing
        # ``ProfileRegistry``. Patch the catalog seam to simulate emptiness.
        with (
            patch("specify_cli.cli.commands.profiles_cmd.find_repo_root", return_value=project),
            patch(
                "specify_cli.cli.commands.profiles_cmd._profile_catalog",
                return_value=([], {}, {}),
            ),
        ):
            result = runner.invoke(cli_app, ["profiles", "list", "--json"])
        assert result.exit_code == 0
        assert _strip_readiness_banner(result.output).strip() == "[]"

    def test_no_profiles_table_shows_helpful_message(self, tmp_path: Path) -> None:
        """When no profiles found, a helpful message is shown."""
        project = tmp_path
        (project / ".kittify").mkdir(parents=True)

        with (
            patch("specify_cli.cli.commands.profiles_cmd.find_repo_root", return_value=project),
            patch(
                "specify_cli.cli.commands.profiles_cmd._profile_catalog",
                return_value=([], {}, {}),
            ),
        ):
            result = runner.invoke(cli_app, ["profiles", "list"])
        assert result.exit_code == 0
        output = _strip_readiness_banner(result.output)
        assert "No profiles" in output or "charter" in output.lower()


class TestProfilesHelp:
    def test_profiles_help_exits_zero(self) -> None:
        result = runner.invoke(cli_app, ["profiles", "--help"])
        assert result.exit_code == 0
        assert "profiles" in result.output.lower()


class TestAgentProfileCompatibilityAlias:
    def test_agent_profile_list_json_routes_to_profiles_list(self, tmp_path: Path) -> None:
        project = _setup_project(tmp_path)
        with patch("specify_cli.cli.commands.profiles_cmd.find_repo_root", return_value=project):
            result = runner.invoke(cli_app, ["agent", "profile", "list", "--json"])
        assert result.exit_code == 0, result.output
        profiles = _json_payload(result.output)
        profile_ids = [p["profile_id"] for p in profiles]
        assert "implementer-fixture" in profile_ids
        assert all(p["identifier"] == p["profile_id"] for p in profiles)


class TestMissionFlagAcceptedAndIgnored:
    """Profiles are mission-agnostic; ``--mission`` must not be rejected (#3953)."""

    def test_agent_profile_list_accepts_mission_flag(self, tmp_path: Path) -> None:
        project = _setup_project(tmp_path)
        with patch("specify_cli.cli.commands.profiles_cmd.find_repo_root", return_value=project):
            result = runner.invoke(cli_app, ["agent", "profile", "list", "--mission", "042-some-mission", "--json"])
        assert result.exit_code == 0, result.output
        profile_ids = [p["profile_id"] for p in _json_payload(result.output)]
        assert "implementer-fixture" in profile_ids

    def test_profiles_show_accepts_mission_flag(self, tmp_path: Path) -> None:
        project = _setup_project(tmp_path)
        with patch("specify_cli.cli.commands.profiles_cmd.find_repo_root", return_value=project):
            result = runner.invoke(
                cli_app,
                ["profiles", "show", "implementer-fixture", "--mission", "042-some-mission", "--json"],
            )
        assert result.exit_code == 0, result.output
        assert _json_payload(result.output)["profile_id"] == "implementer-fixture"
