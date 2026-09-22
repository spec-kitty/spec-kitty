"""Tests for agent config management commands."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.config import app
from specify_cli.core.config import AGENT_COMMAND_CONFIG
from specify_cli.core.agent_config import save_agent_config
from specify_cli.task_utils.support import TaskCliError

pytestmark = pytest.mark.fast

runner = CliRunner()


def _unwrapped_output(output: str) -> str:
    """Normalize Rich line wrapping in CLI output assertions."""
    return output.replace("\n", "")


@pytest.fixture(autouse=True)
def fake_global_command_dirs(tmp_path, monkeypatch):
    """Keep global command checks isolated from the developer's home directory."""
    global_root = tmp_path / "global-home"

    def _fake_global_command_dir(agent_key: str):
        if agent_key == "opencode":
            return global_root / ".config" / "opencode" / "commands"
        return global_root / AGENT_COMMAND_CONFIG[agent_key]["dir"]

    monkeypatch.setattr(
        "specify_cli.cli.commands.agent.config.get_global_command_dir",
        _fake_global_command_dir,
    )
    (global_root / ".config" / "opencode" / "commands").mkdir(parents=True)
    return global_root


@pytest.fixture
def mock_project(tmp_path):
    """Create a mock spec-kitty project."""
    # Create .kittify structure
    kittify = tmp_path / ".kittify"
    kittify.mkdir()

    config_file = kittify / "config.yaml"
    config_file.write_text("agents:\n  available:\n    - opencode\n")

    # Create mission templates
    missions = kittify / "missions" / "software-dev" / "command-templates"
    missions.mkdir(parents=True)

    (missions / "implement.md").write_text("# Implement Template")
    (missions / "review.md").write_text("# Review Template")

    # Create agent directories
    opencode = tmp_path / ".opencode" / "command"
    opencode.mkdir(parents=True)
    (opencode / "spec-kitty.implement.md").write_text("# Old Implement")

    return tmp_path


class TestListCommand:
    """Tests for 'spec-kitty agent config list' command."""

    def test_list_configured_agents(self, mock_project):
        """Test listing configured agents."""
        with patch("specify_cli.cli.commands.agent.config.find_repo_root", return_value=mock_project):
            result = runner.invoke(app, ["list"])

            assert result.exit_code == 0
            assert "opencode" in result.stdout
            assert ".config/opencode/commands/" in _unwrapped_output(result.stdout)
            assert "✓" in result.stdout  # opencode exists

    def test_list_uses_global_command_root_after_init(self, tmp_path):
        """A fresh 3.1.x project has config but no project-local command dir."""
        kittify = tmp_path / ".kittify"
        kittify.mkdir()
        (kittify / "config.yaml").write_text("agents:\n  available:\n    - opencode\n")

        with patch("specify_cli.cli.commands.agent.config.find_repo_root", return_value=tmp_path):
            result = runner.invoke(app, ["list"])

            assert result.exit_code == 0
            assert "✓ opencode" in result.stdout
            assert ".config/opencode/commands/" in _unwrapped_output(result.stdout)
            assert "(global)" in result.stdout
            assert not (tmp_path / ".opencode").exists()

    def test_list_no_agents_configured(self, tmp_path):
        """Test listing when no agents are configured."""
        kittify = tmp_path / ".kittify"
        kittify.mkdir()
        (kittify / "config.yaml").write_text("agents:\n  available: []\n")

        with patch("specify_cli.cli.commands.agent.config.find_repo_root", return_value=tmp_path):
            result = runner.invoke(app, ["list"])

            assert result.exit_code == 0
            assert "No agents configured" in result.stdout

    def test_list_shows_available_agents(self, mock_project):
        """Test that list shows available but not configured agents."""
        with patch("specify_cli.cli.commands.agent.config.find_repo_root", return_value=mock_project):
            result = runner.invoke(app, ["list"])

            assert result.exit_code == 0
            assert "Available but not configured:" in result.stdout
            assert "claude" in result.stdout


class TestAddCommand:
    """Tests for 'spec-kitty agent config add' command."""

    def test_add_single_agent(self, mock_project):
        """Adding a slash-command agent registers global commands without local dirs."""
        with patch("specify_cli.cli.commands.agent.config.find_repo_root", return_value=mock_project):
            result = runner.invoke(app, ["add", "claude"])

            assert result.exit_code == 0
            assert "Registered claude" in result.stdout
            assert "global commands" in result.stdout
            assert "Updated config.yaml" in result.stdout

            # Slash-command files are global in 3.1.x, not project-local.
            assert not (mock_project / ".claude").exists()

            # Verify config was updated
            config_file = mock_project / ".kittify" / "config.yaml"
            config_content = config_file.read_text()
            assert "claude" in config_content

    def test_add_multiple_agents(self, mock_project):
        """Test adding multiple agents at once."""
        with patch("specify_cli.cli.commands.agent.config.find_repo_root", return_value=mock_project):
            result = runner.invoke(app, ["add", "claude", "codex"])

            assert result.exit_code == 0
            assert "Registered claude" in result.stdout
            assert "Registered codex" in result.stdout
            assert ".agents/skills/" in result.stdout

            # Claude is globally managed; Codex uses project-local command skills.
            assert not (mock_project / ".claude").exists()
            assert (mock_project / ".agents" / "skills").exists()

    def test_add_already_configured_agent(self, mock_project):
        """Test adding an agent that's already configured."""
        with patch("specify_cli.cli.commands.agent.config.find_repo_root", return_value=mock_project):
            result = runner.invoke(app, ["add", "opencode"])

            assert result.exit_code == 0
            assert "Already configured: opencode" in result.stdout

    def test_add_invalid_agent(self, mock_project):
        """Test adding an invalid agent key."""
        with patch("specify_cli.cli.commands.agent.config.find_repo_root", return_value=mock_project):
            result = runner.invoke(app, ["add", "invalid-agent"])

            assert result.exit_code == 1
            assert "Invalid agent keys: invalid-agent" in result.stdout
            assert "Valid agents:" in result.stdout

    def test_add_does_not_create_project_command_templates(self, mock_project):
        """Adding a global command agent must not recreate local command files."""
        with patch("specify_cli.cli.commands.agent.config.find_repo_root", return_value=mock_project):
            result = runner.invoke(app, ["add", "claude"])

            assert result.exit_code == 0

            claude_dir = mock_project / ".claude" / "commands"
            assert not claude_dir.exists()


class TestRemoveCommand:
    """Tests for 'spec-kitty agent config remove' command."""

    def test_remove_agent(self, mock_project):
        """Removing an agent preserves its unproven managed surface (#4907):
        `opencode/command/spec-kitty.implement.md` carries no command-skills
        manifest entry, so ownership is unprovable and the directory survives."""
        with patch("specify_cli.cli.commands.agent.config.find_repo_root", return_value=mock_project):
            result = runner.invoke(app, ["remove", "opencode"])

            assert result.exit_code == 0
            assert "Removed" not in result.stdout
            assert "Preserved" in result.stdout
            assert "Updated config.yaml" in result.stdout

            # Verify directory was preserved, not deleted
            assert (mock_project / ".opencode").exists()

    def test_remove_multiple_agents(self, mock_project):
        """Removing multiple agents preserves each unproven managed surface."""
        # Add another agent first (if not exists)
        claude = mock_project / ".claude" / "commands"
        if not claude.exists():
            claude.mkdir(parents=True)

        # Update config to include claude
        from specify_cli.core.agent_config import load_agent_config
        config = load_agent_config(mock_project)
        config.available.append("claude")
        save_agent_config(mock_project, config)

        with patch("specify_cli.cli.commands.agent.config.find_repo_root", return_value=mock_project):
            result = runner.invoke(app, ["remove", "opencode", "claude"])

            assert result.exit_code == 0
            assert "Removed" not in result.stdout
            assert result.stdout.count("Preserved") == 2
            assert (mock_project / ".opencode").exists()
            assert (mock_project / ".claude").exists()

    def test_remove_nonexistent_directory(self, mock_project):
        """Test removing an agent whose directory doesn't exist."""
        # Add gemini to config but not filesystem
        from specify_cli.core.agent_config import load_agent_config
        config = load_agent_config(mock_project)
        config.available.append("gemini")
        save_agent_config(mock_project, config)

        with patch("specify_cli.cli.commands.agent.config.find_repo_root", return_value=mock_project):
            result = runner.invoke(app, ["remove", "gemini"])

            assert result.exit_code == 0
            assert "already removed" in result.stdout.lower()
            assert "Updated config.yaml" in result.stdout

            config = load_agent_config(mock_project)
            assert "gemini" not in config.available

    def test_remove_with_keep_config(self, mock_project):
        """Test removing agent with --keep-config flag preserves the unproven
        surface (#4907) while still dropping the config.yaml entry."""
        with patch("specify_cli.cli.commands.agent.config.find_repo_root", return_value=mock_project):
            result = runner.invoke(app, ["remove", "opencode", "--keep-config"])

            assert result.exit_code == 0
            assert "Removed" not in result.stdout
            assert "Preserved" in result.stdout

            # Verify directory was preserved and config still has it
            assert (mock_project / ".opencode").exists()

            from specify_cli.core.agent_config import load_agent_config
            config = load_agent_config(mock_project)
            assert "opencode" in config.available

    def test_remove_copilot_preserves_github_workflows(self, tmp_path):
        """Removing Copilot must not delete unrelated .github content -- and,
        per the #4907 ownership gate, must not delete the unproven managed
        prompts surface either (AGENT_DIRS generality, T008)."""
        kittify = tmp_path / ".kittify"
        kittify.mkdir()
        (kittify / "config.yaml").write_text("agents:\n  available:\n    - copilot\n")
        workflows = tmp_path / ".github" / "workflows"
        prompts = tmp_path / ".github" / "prompts"
        workflows.mkdir(parents=True)
        prompts.mkdir(parents=True)
        (workflows / "ci.yml").write_text("name: ci\n")
        (prompts / "spec-kitty.example.prompt.md").write_text("# prompt\n")

        with patch("specify_cli.cli.commands.agent.config.find_repo_root", return_value=tmp_path):
            result = runner.invoke(app, ["remove", "copilot"])

            assert result.exit_code == 0
            assert "Removed" not in result.stdout
            assert "Preserved" in result.stdout
            assert prompts.exists()
            assert (workflows / "ci.yml").exists()


class TestStatusCommand:
    """Tests for 'spec-kitty agent config status' command."""

    def test_status_shows_all_agents(self, mock_project):
        """Test status command shows all agents."""
        with patch("specify_cli.cli.commands.agent.config.find_repo_root", return_value=mock_project):
            result = runner.invoke(app, ["status"])

            assert result.exit_code == 0
            assert "Agent Status" in result.stdout
            assert "opencode" in result.stdout
            assert "claude" in result.stdout

    def test_status_shows_ok_for_configured_and_present(self, mock_project):
        """Test status shows OK for agents that are configured and present."""
        with patch("specify_cli.cli.commands.agent.config.find_repo_root", return_value=mock_project):
            result = runner.invoke(app, ["status"])

            assert result.exit_code == 0
            # opencode is configured and present
            assert "OK" in result.stdout

    def test_status_uses_global_command_root_after_init(self, tmp_path):
        """Configured global command agents should not be missing after init."""
        kittify = tmp_path / ".kittify"
        kittify.mkdir()
        (kittify / "config.yaml").write_text("agents:\n  available:\n    - opencode\n")

        with patch("specify_cli.cli.commands.agent.config.find_repo_root", return_value=tmp_path):
            result = runner.invoke(app, ["status"])

            assert result.exit_code == 0
            assert "opencode" in result.stdout
            assert "global" in result.stdout
            assert "OK" in result.stdout
            assert "Missing" not in result.stdout
            assert not (tmp_path / ".opencode").exists()

    def test_status_shows_orphaned(self, mock_project):
        """Test status shows orphaned agents (present but not configured)."""
        # Create claude directory but don't add to config (if not exists)
        claude = mock_project / ".claude" / "commands"
        if not claude.exists():
            claude.mkdir(parents=True)

        with patch("specify_cli.cli.commands.agent.config.find_repo_root", return_value=mock_project):
            result = runner.invoke(app, ["status"])

            assert result.exit_code == 0
            assert "Orphaned" in result.stdout
            assert "orphaned directories found" in result.stdout


class TestSyncCommand:
    """Tests for 'spec-kitty agent config sync' command."""

    def test_sync_removes_orphaned(self, mock_project):
        """An orphaned directory with no ownership proof is preserved, not
        removed, by the default orphan sweep (#2691 removal half)."""
        # Create orphaned claude directory (if not exists)
        claude = mock_project / ".claude" / "commands"
        if not claude.exists():
            claude.mkdir(parents=True)

        with patch("specify_cli.cli.commands.agent.config.find_repo_root", return_value=mock_project):
            result = runner.invoke(app, ["sync"])

            assert result.exit_code == 0
            assert "Removed orphaned" not in result.stdout
            assert "Preserved .claude/commands" in result.stdout
            assert (mock_project / ".claude").exists()

    def test_sync_removes_only_copilot_prompts(self, tmp_path):
        """Orphan cleanup must preserve unrelated .github files -- and, since
        the prompts dir itself carries no ownership proof, must preserve it
        too (#2691 removal half / AGENT_DIRS generality)."""
        kittify = tmp_path / ".kittify"
        kittify.mkdir()
        (kittify / "config.yaml").write_text("agents:\n  available: []\n")
        workflows = tmp_path / ".github" / "workflows"
        prompts = tmp_path / ".github" / "prompts"
        workflows.mkdir(parents=True)
        prompts.mkdir(parents=True)
        (workflows / "ci.yml").write_text("name: ci\n")
        (prompts / "spec-kitty.example.prompt.md").write_text("# prompt\n")

        with patch("specify_cli.cli.commands.agent.config.find_repo_root", return_value=tmp_path):
            result = runner.invoke(app, ["sync"])

            assert result.exit_code == 0
            assert "Removed orphaned" not in result.stdout
            assert "Preserved .github/prompts" in result.stdout
            assert prompts.exists()
            assert (workflows / "ci.yml").exists()

    def test_sync_keep_orphaned(self, mock_project):
        """Test sync with --keep-orphaned flag."""
        # Create orphaned claude directory (if not exists)
        claude = mock_project / ".claude" / "commands"
        if not claude.exists():
            claude.mkdir(parents=True)

        with patch("specify_cli.cli.commands.agent.config.find_repo_root", return_value=mock_project):
            result = runner.invoke(app, ["sync", "--keep-orphaned"])

            assert result.exit_code == 0
            # Should not remove claude
            assert (mock_project / ".claude" / "commands").exists()

    def test_sync_create_missing_skips_global_command_dirs(self, mock_project):
        """Sync should not recreate retired project-local command directories."""
        # Add gemini to config but don't create directory
        from specify_cli.core.agent_config import load_agent_config

        config = load_agent_config(mock_project)
        config.available.append("gemini")
        save_agent_config(mock_project, config)

        with patch("specify_cli.cli.commands.agent.config.find_repo_root", return_value=mock_project):
            result = runner.invoke(app, ["sync", "--create-missing"])

            assert result.exit_code == 0
            assert "Global commands missing for gemini" in result.stdout
            assert not (mock_project / ".gemini").exists()

    def test_sync_no_changes_needed(self, tmp_path):
        """Test sync when filesystem already matches config."""
        # Create fresh project with matching config and filesystem
        kittify = tmp_path / ".kittify"
        kittify.mkdir()

        # Config with only opencode
        config_file = kittify / "config.yaml"
        config_file.write_text("agents:\n  available:\n    - opencode\n")

        # Create only opencode directory
        opencode = tmp_path / ".opencode" / "command"
        opencode.mkdir(parents=True)

        with patch("specify_cli.cli.commands.agent.config.find_repo_root", return_value=tmp_path):
            result = runner.invoke(app, ["sync"])

            assert result.exit_code == 0
            assert "No changes needed" in result.stdout

    def test_sync_json_outside_project_emits_error_envelope(self):
        """Outside a project, ``--json`` must emit the adopted
        ``{ok: false, error: {code, message}}`` envelope on stdout instead of
        the plain-text ``Error: ...`` line the human path prints (#4915
        landing fold for PR #4936; see
        tests/architectural/test_json_contract_enumeration.py ADOPTED
        classification for "agent config sync")."""
        with patch(
            "specify_cli.cli.commands.agent.config.find_repo_root",
            side_effect=TaskCliError("Unable to locate repository root (missing .git or .kittify)."),
        ):
            result = runner.invoke(app, ["sync", "--json"])

        assert result.exit_code == 1
        payload = json.loads(result.stdout)
        assert payload["ok"] is False
        error = payload["error"]
        assert isinstance(error["code"], str) and error["code"]
        assert isinstance(error["message"], str) and error["message"]


class TestAgentKeyMapping:
    """Tests for agent key to directory mapping."""

    def test_special_agent_keys_register_global_commands(self, mock_project):
        """Special command-layer agent keys still register without local dirs."""
        # copilot -> .github
        # auggie -> .augment
        # q -> .amazonq

        with patch("specify_cli.cli.commands.agent.config.find_repo_root", return_value=mock_project):
            # Test copilot (maps to .github)
            result = runner.invoke(app, ["add", "copilot"])
            assert result.exit_code == 0
            assert "Registered copilot" in result.stdout
            assert not (mock_project / ".github" / "prompts").exists()

            # Test auggie (maps to .augment)
            result = runner.invoke(app, ["add", "auggie"])
            assert result.exit_code == 0
            assert "Registered auggie" in result.stdout
            assert not (mock_project / ".augment" / "commands").exists()

            # Test q (maps to .amazonq)
            result = runner.invoke(app, ["add", "q"])
            assert result.exit_code == 0
            assert "Registered q" in result.stdout
            assert not (mock_project / ".amazonq" / "prompts").exists()
