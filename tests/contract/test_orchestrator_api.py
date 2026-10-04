"""Shape conformance tests for orchestrator-api responses against 3.0.0 contract.

Tests that CLI command output uses mission-era naming (mission_slug not
mission_slug), returns correct error codes, and rejects legacy commands/flags.

Run: python -m pytest tests/contract/test_orchestrator_api.py -v
"""

from __future__ import annotations

import importlib
import inspect
import json
import pkgutil
import re
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.git.commit_helpers import SafeCommitBackstopError, SafeCommitError
from specify_cli import orchestrator_api
from specify_cli.orchestrator_api.commands import app
from specify_cli.orchestrator_api.envelope import CONTRACT_VERSION

pytestmark = [pytest.mark.contract, pytest.mark.fast]

runner = CliRunner()


def _make_mission(tmp_path: Path, mission_slug: str = "099-test-mission") -> tuple[Path, Path]:
    """Create a minimal mission directory with tasks and meta.json.

    Returns (repo_root, mission_dir).
    """
    repo_root = tmp_path / "repo"
    mission_dir = repo_root / "kitty-specs" / mission_slug
    tasks_dir = mission_dir / "tasks"
    tasks_dir.mkdir(parents=True)

    for wp_id in ("WP01", "WP02"):
        (tasks_dir / f"{wp_id}.md").write_text(
            f"---\nwork_package_id: {wp_id}\ntitle: Test {wp_id}\n"
            f"lane: planned\ndependencies: []\n---\n\n# {wp_id}\n",
            encoding="utf-8",
        )

    meta = {
        "mission_number": mission_slug.split("-")[0],
        "slug": mission_slug,
        "mission_slug": mission_slug,
        "friendly_name": "Test Mission",
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-03-18T00:00:00+00:00",
        "status_phase": 2,
    }
    (mission_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    return repo_root, mission_dir


def _invoke(args: list[str], repo_root: Path) -> tuple[dict, int]:
    """Invoke orchestrator-api subcommand with mocked repo root.

    Returns (parsed_json, exit_code).
    """
    with patch(
        "specify_cli.orchestrator_api._common._get_main_repo_root",
        return_value=repo_root,
    ):
        result = runner.invoke(app, args, catch_exceptions=False)

    # Parse the JSON output (first line of stdout)
    output = result.output.strip()
    if output:
        envelope = json.loads(output.split("\n")[0])
    else:
        envelope = {}
    return envelope, result.exit_code


class TestMissionStateResponse:
    """Validate mission-state command output shape."""

    def test_response_contains_mission_slug(self, tmp_path, orchestrator_api_contract):
        repo_root, _ = _make_mission(tmp_path)
        envelope, code = _invoke(["mission-state", "--mission", "099-test-mission"], repo_root)

        assert envelope["success"] is True
        data = envelope["data"]
        assert "mission_slug" in data, "Response must contain 'mission_slug'"
        assert data["mission_slug"] == "099-test-mission"

    def test_response_does_not_contain_mission_slug(self, tmp_path, orchestrator_api_contract):
        repo_root, _ = _make_mission(tmp_path)
        envelope, _ = _invoke(["mission-state", "--mission", "099-test-mission"], repo_root)

        data = envelope["data"]
        for forbidden in orchestrator_api_contract["forbidden_payload_fields"]:
            assert forbidden not in data, f"Forbidden field '{forbidden}' found in response data"

    def test_command_field_uses_mission_era_name(self, tmp_path):
        repo_root, _ = _make_mission(tmp_path)
        envelope, _ = _invoke(["mission-state", "--mission", "099-test-mission"], repo_root)

        assert "command" in envelope
        # Command should reference mission-state, not feature-state
        assert "mission-state" in envelope["command"]
        assert "feature-state" not in envelope["command"]


class TestMissionNotFoundError:
    """Validate that not-found errors use MISSION_NOT_FOUND."""

    def test_error_code_is_mission_not_found(self, tmp_path):
        repo_root, _ = _make_mission(tmp_path)
        envelope, code = _invoke(
            ["mission-state", "--mission", "999-nonexistent"],
            repo_root,
        )

        assert envelope["success"] is False
        assert envelope["error_code"] == "MISSION_NOT_FOUND"

    def test_error_code_is_not_feature_not_found(self, tmp_path, orchestrator_api_contract):
        repo_root, _ = _make_mission(tmp_path)
        envelope, _ = _invoke(
            ["mission-state", "--mission", "999-nonexistent"],
            repo_root,
        )

        for forbidden_code in orchestrator_api_contract["forbidden_error_codes"]:
            assert envelope["error_code"] != forbidden_code, (
                f"Error code '{forbidden_code}' is forbidden by contract"
            )


class TestAcceptMissionNotReady:
    """Validate accept-mission returns MISSION_NOT_READY when WPs incomplete."""

    def test_mission_not_ready_error(self, tmp_path):
        repo_root, _ = _make_mission(tmp_path)
        envelope, code = _invoke(
            ["accept-mission", "--mission", "099-test-mission", "--actor", "test-agent"],
            repo_root,
        )

        assert envelope["success"] is False
        assert envelope["error_code"] == "MISSION_NOT_READY"


class TestForbiddenCommands:
    """Validate that legacy feature-era command names are rejected."""

    def test_feature_state_is_unknown_command(self, tmp_path):
        """Invoking 'feature-state' must fail -- it is not a valid subcommand."""
        repo_root, _ = _make_mission(tmp_path)

        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            result = runner.invoke(app, ["feature-state", "--mission", "099-test-mission"])

        # Must fail with non-zero exit code
        assert result.exit_code != 0, "feature-state should not be a valid command"


class TestForbiddenFlags:
    """Validate that --feature flag is rejected, --mission works."""

    def test_mission_flag_works(self, tmp_path):
        repo_root, _ = _make_mission(tmp_path)
        envelope, code = _invoke(
            ["mission-state", "--mission", "099-test-mission"],
            repo_root,
        )
        assert envelope.get("success") is True

    def test_feature_flag_is_rejected(self, tmp_path):
        """--feature flag must not be accepted by mission-state."""
        repo_root, _ = _make_mission(tmp_path)

        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            result = runner.invoke(app, ["mission-state", "--feature", "099-test-mission"])

        # Must fail with non-zero exit code since --feature is not a valid option
        assert result.exit_code != 0, "--feature flag should not be accepted"


class TestAllowedCommandNames:
    """Cross-check that allowed commands from contract exist as app subcommands."""

    def test_allowed_commands_are_registered(self, orchestrator_api_contract):
        """Every command in the contract must be a registered subcommand."""
        import typer.main

        group = typer.main.get_group(app)
        registered = set(group.commands.keys()) if hasattr(group, "commands") else set()

        allowed_commands = set(orchestrator_api_contract["allowed_commands"])
        for cmd_name in allowed_commands:
            assert cmd_name in registered, f"Allowed command '{cmd_name}' is not registered in orchestrator-api app"

    def test_registered_commands_are_contract_allowed(self, orchestrator_api_contract):
        """Every registered subcommand must be declared in the contract.

        The inverse of test_allowed_commands_are_registered: without it, a new
        command can register on the surface without ever entering
        upstream_contract.json (the artifact external consumers validate
        against) — #2338's resolve-workspace was the first live instance.
        """
        import typer.main

        group = typer.main.get_group(app)
        registered = set(group.commands.keys()) if hasattr(group, "commands") else set()

        allowed_commands = set(orchestrator_api_contract["allowed_commands"])
        undeclared = registered - allowed_commands
        assert not undeclared, (
            f"Registered orchestrator-api command(s) missing from upstream_contract.json "
            f"allowed_commands: {sorted(undeclared)}"
        )

    def test_forbidden_commands_are_not_registered(self, orchestrator_api_contract):
        """No forbidden command from the contract may be registered."""
        import typer.main

        group = typer.main.get_group(app)
        registered = set(group.commands.keys()) if hasattr(group, "commands") else set()

        for forbidden_cmd in orchestrator_api_contract["forbidden_commands"]:
            assert forbidden_cmd not in registered, (
                f"Forbidden command '{forbidden_cmd}' is registered in orchestrator-api app"
            )


class TestAllowedErrorCodes:
    """Cross-check emitted orchestrator-api failure codes against the contract."""

    def test_literal_failure_codes_are_contract_allowed(self, orchestrator_api_contract):
        # The verbs live in per-concern modules behind the ``commands`` facade, so the
        # scan must cover every module of the package, not the facade alone.
        source = "\n".join(
            inspect.getsource(importlib.import_module(f"{orchestrator_api.__name__}.{module.name}"))
            for module in pkgutil.iter_modules(orchestrator_api.__path__)
        )
        emitted = set(
            re.findall(
                r"_fail\(\s*[^,]+,\s*[\"']([A-Z0-9_]+)[\"']",
                source,
                flags=re.DOTALL,
            )
        )
        # Floor: a contract code that only a concern module emits. Naming one real
        # code (rather than a count) keeps the scan from going vacuous again without
        # breaking each time a code is legitimately added or retired.
        assert "MISSION_NOT_FOUND" in emitted
        allowed = set(orchestrator_api_contract["allowed_error_codes"])
        assert emitted <= allowed

    def test_safe_commit_failure_codes_are_contract_allowed(self, orchestrator_api_contract):
        emitted = {SafeCommitError.error_code, SafeCommitBackstopError.error_code}
        emitted.update(cls.error_code for cls in SafeCommitError.__subclasses__())
        allowed = set(orchestrator_api_contract["allowed_error_codes"])
        assert emitted <= allowed
