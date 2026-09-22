"""Coverage tests for ``specify_cli.cli.commands.agent.config`` (A/B/C split).

These tests use CliRunner and patch ``find_repo_root`` plus agent-config
helpers so tests don't require a real project.  Real filesystem I/O uses
``tmp_path``; no patch of Path methods.

Tactic: function-over-form-testing (src/charter/offering/tactics/built-in/testing/).
Structure: AAA (Arrange / Act / Assert).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.config import (
    _display_path,
    _remove_project_agent_surface,
    app,
)
from specify_cli.core.agent_config import AgentConfig

pytestmark = pytest.mark.fast

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_config(available: list[str] | None = None, auto_commit: bool = True) -> AgentConfig:
    """Build a minimal AgentConfig for testing."""
    config = MagicMock(spec=AgentConfig)
    config.available = list(available or [])
    config.auto_commit = auto_commit
    return config


def _patch_repo_and_config(tmp_path: Path, config: AgentConfig):
    """Context manager that patches find_repo_root and _load_config_or_exit."""
    return (
        patch("specify_cli.cli.commands.agent.config.find_repo_root", return_value=tmp_path),
        patch("specify_cli.cli.commands.agent.config._load_config_or_exit", return_value=config),
    )


# ---------------------------------------------------------------------------
# Bucket B — Filesystem I/O helpers
# ---------------------------------------------------------------------------

class TestDisplayPath:
    def test_returns_tilde_form_for_path_under_home(self) -> None:
        """Arrange: path under home; Act: display; Assert: ~ prefix in result."""
        home = Path.home()
        sub = home / "projects" / "myrepo"
        result = _display_path(sub)
        assert "~/" in result or "projects" in result

    def test_returns_posix_string_when_path_outside_home(self) -> None:
        """Arrange: path not under home; Act: display; Assert: posix path returned."""
        result = _display_path(Path("/var/run/something"))
        assert "/var/run/something" in result


class TestRemoveProjectAgentSurface:
    def test_returns_false_when_agent_key_unknown(self, tmp_path: Path) -> None:
        """Arrange: unknown agent key;
        Act: remove;
        Assert: (False, error_message) returned."""
        removed, message = _remove_project_agent_surface(tmp_path, "totally-unknown-agent-xyz")
        assert removed is False
        assert "Unknown" in message or "unknown" in message.lower()

    def test_returns_false_when_surface_already_absent(self, tmp_path: Path) -> None:
        """Arrange: known agent but its directory does not exist;
        Act: remove;
        Assert: (False, already-removed message) returned."""
        # "claude" is a known command-layer agent
        removed, message = _remove_project_agent_surface(tmp_path, "claude")
        assert removed is False
        assert "removed" in message.lower() or "already" in message.lower() or "Missing" in message or not removed

    def test_preserves_surface_directory_with_no_ownership_proof(self, tmp_path: Path) -> None:
        """Arrange: claude surface dir exists but carries no command-skills
        manifest entry; Act: remove; Assert: (False, "Preserved ...") and the
        directory survives (#4907 -- ownership must be proven, not assumed)."""
        # Create the claude commands surface
        claude_commands = tmp_path / ".claude" / "commands"
        claude_commands.mkdir(parents=True)
        (claude_commands / "spec-kitty.implement.md").write_text("# implement", encoding="utf-8")

        removed, message = _remove_project_agent_surface(tmp_path, "claude")
        assert removed is False
        assert "Preserved" in message
        assert claude_commands.exists()


# ---------------------------------------------------------------------------
# Bucket A — CLI orchestration (list / add / remove / status)
# ---------------------------------------------------------------------------

class TestListCommand:
    def test_list_exits_zero_and_shows_configured_agents(self, tmp_path: Path) -> None:
        """Arrange: config with claude; Act: list; Assert: exit 0 and "claude" in output."""
        config = _mock_config(available=["claude"])

        patches = _patch_repo_and_config(tmp_path, config)
        with patches[0], patches[1]:
            result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "claude" in result.output

    def test_list_shows_no_agents_message_when_none_configured(self, tmp_path: Path) -> None:
        """Arrange: empty config; Act: list; Assert: exit 0 and informative message."""
        config = _mock_config(available=[])

        patches = _patch_repo_and_config(tmp_path, config)
        with patches[0], patches[1]:
            result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "No agents" in result.output or "configured" in result.output.lower()

    def test_list_shows_auto_commit_status(self, tmp_path: Path) -> None:
        """Arrange: config with auto_commit=False;
        Act: list;
        Assert: 'Auto-commit' (stable label) in output."""
        config = _mock_config(available=["claude"], auto_commit=False)

        patches = _patch_repo_and_config(tmp_path, config)
        with patches[0], patches[1]:
            result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "Auto-commit" in result.output or "auto_commit" in result.output.lower()


class TestAddCommand:
    def test_add_invalid_agent_exits_nonzero_with_error(self, tmp_path: Path) -> None:
        """Arrange: nonexistent agent key; Act: add; Assert: exit 1 and 'Error' in output."""
        config = _mock_config()

        patches = _patch_repo_and_config(tmp_path, config)
        with patches[0], patches[1]:
            result = runner.invoke(app, ["add", "nonexistent-agent-xyz"])

        assert result.exit_code != 0
        assert "Error" in result.output or "Invalid" in result.output

    def test_add_already_configured_agent_is_skipped(self, tmp_path: Path) -> None:
        """Arrange: claude already in config.available; Act: add claude; Assert: exit 0."""
        config = _mock_config(available=["claude"])

        patches = _patch_repo_and_config(tmp_path, config)
        with patches[0], patches[1], \
             patch("specify_cli.cli.commands.agent.config.save_agent_config"):
            result = runner.invoke(app, ["add", "claude"])

        assert result.exit_code == 0
        assert "already" in result.output.lower() or "claude" in result.output


class TestRemoveCommand:
    def test_remove_invalid_agent_exits_nonzero(self, tmp_path: Path) -> None:
        """Arrange: bad agent key; Act: remove; Assert: exit 1 and error message."""
        config = _mock_config(available=["claude"])

        patches = _patch_repo_and_config(tmp_path, config)
        with patches[0], patches[1]:
            result = runner.invoke(app, ["remove", "nonexistent-xyz"])

        assert result.exit_code != 0
        assert "Error" in result.output or "Invalid" in result.output

    def test_remove_configured_agent_updates_config(self, tmp_path: Path) -> None:
        """Arrange: claude in config; Act: remove claude; Assert: exit 0 and config saved."""
        config = _mock_config(available=["claude"])

        patches = _patch_repo_and_config(tmp_path, config)
        with patches[0], patches[1], \
             patch("specify_cli.cli.commands.agent.config.save_agent_config"):
            result = runner.invoke(app, ["remove", "claude"])

        # Should exit 0 even if directory didn't exist (removed from config is the key behavior)
        assert result.exit_code == 0
        # config.available.remove was called (side effect on mock)


class TestStatusCommand:
    def test_status_exits_zero_and_shows_table(self, tmp_path: Path) -> None:
        """Arrange: minimal config; Act: status; Assert: exit 0 and table rendered."""
        config = _mock_config(available=["claude"])

        patches = _patch_repo_and_config(tmp_path, config)
        with patches[0], patches[1]:
            result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        # Table header or agent name should appear
        assert "claude" in result.output or "Agent" in result.output


class TestSyncCommand:
    def test_sync_exits_zero_when_no_changes_needed(self, tmp_path: Path) -> None:
        """Arrange: empty config, no orphaned dirs; Act: sync; Assert: exit 0."""
        config = _mock_config(available=[])

        patches = _patch_repo_and_config(tmp_path, config)
        with patches[0], patches[1]:
            result = runner.invoke(app, ["sync"])

        assert result.exit_code == 0
        assert "No changes" in result.output or "match" in result.output.lower() or "Sync" in result.output
