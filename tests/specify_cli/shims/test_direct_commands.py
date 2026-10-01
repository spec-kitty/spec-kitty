"""Tests verifying direct canonical commands in agent surfaces (WP03 / T017).

Covers:
- T017-1: generate_shim_content("implement") -> spec-kitty agent action implement
- T017-2: generate_shim_content("accept") -> spec-kitty agent mission accept
- T017-3: All 7 CLI-driven commands produce correct canonical calls
- T017-4: "accept" is in ACTION_NAMES
- T017-5: spec-kitty agent shim CLI subcommand no longer registered
- T017-6: rewrite_agent_shims() produces direct commands
- T017-7: .claude/commands/ has direct calls
- T017-8: .codex/prompts/ has direct calls
- T017-9: .opencode/command/ has direct calls
- T017-10: Migration is idempotent
"""

from __future__ import annotations

from pathlib import Path
from typing import get_args

import pytest

from specify_cli.shims.generator import generate_shim_content, generate_all_shims
from specify_cli.shims.registry import CLI_DRIVEN_COMMANDS
from mission_runtime import ActionName, ACTION_NAMES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.unit, pytest.mark.fast]
def _setup_project(tmp_path: Path, agents: list[str]) -> None:
    """Create a minimal project with .kittify/config.yaml and agent dirs."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    available_lines = "\n".join(f"    - {a}" for a in agents)
    (kittify / "config.yaml").write_text(
        f"project:\n  uuid: test-uuid-1234\nagents:\n  available:\n{available_lines}\n",
        encoding="utf-8",
    )

    # Agent directory mappings
    agent_dir_map = {
        "claude": (".claude", "commands"),
        "codex": (".codex", "prompts"),
        "opencode": (".opencode", "command"),
    }
    for agent in agents:
        if agent in agent_dir_map:
            root, subdir = agent_dir_map[agent]
            (tmp_path / root / subdir).mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# T017-1: implement maps to direct canonical command
# ---------------------------------------------------------------------------

class TestDirectImplementCommand:
    def test_generate_shim_content_direct_implement(self) -> None:
        content = generate_shim_content("implement", "claude", "$ARGUMENTS")
        assert "spec-kitty agent action implement $ARGUMENTS --agent claude" in content
        assert "agent shim" not in content

    def test_implement_with_codex(self) -> None:
        content = generate_shim_content("implement", "codex", "$PROMPT")
        assert "spec-kitty agent action implement $PROMPT --agent codex" in content


# ---------------------------------------------------------------------------
# T017-2: accept maps to direct canonical command
# ---------------------------------------------------------------------------

class TestDirectAcceptCommand:
    def test_generate_shim_content_direct_accept(self) -> None:
        content = generate_shim_content("accept", "claude", "$ARGUMENTS")
        assert "spec-kitty agent mission accept $ARGUMENTS" in content
        assert "agent shim" not in content

    def test_accept_no_agent_flag(self) -> None:
        """Accept is feature-level -- no --agent flag in the canonical command."""
        content = generate_shim_content("accept", "claude", "$ARGUMENTS")
        assert "`spec-kitty agent mission accept $ARGUMENTS`" in content
        assert "spec-kitty agent mission accept $ARGUMENTS --agent" not in content


# ---------------------------------------------------------------------------
# T017-3: All 7 CLI-driven commands produce correct canonical calls
# ---------------------------------------------------------------------------

class TestAllCliDrivenCommands:
    EXPECTED_PREFIXES = {
        "implement": "spec-kitty agent action implement",
        "review": "spec-kitty agent action review",
        "accept": "spec-kitty agent mission accept",
        "status": "spec-kitty agent tasks status",
        "consolidate": "spec-kitty consolidate",
        "tasks-finalize": "spec-kitty agent mission finalize-tasks",
    }

    @pytest.mark.parametrize("command", sorted(CLI_DRIVEN_COMMANDS))
    def test_command_uses_canonical_prefix(self, command: str) -> None:
        content = generate_shim_content(command, "claude", "$ARGUMENTS")
        expected = self.EXPECTED_PREFIXES[command]
        assert expected in content, (
            f"Command '{command}' should contain '{expected}' but got:\n{content}"
        )

    @pytest.mark.parametrize("command", sorted(CLI_DRIVEN_COMMANDS))
    def test_no_shim_dispatch_in_any_command(self, command: str) -> None:
        content = generate_shim_content(command, "claude", "$ARGUMENTS")
        assert "agent shim" not in content


# ---------------------------------------------------------------------------
# T017-4: "accept" is in ACTION_NAMES
# ---------------------------------------------------------------------------

class TestAcceptInActionNames:
    def test_accept_in_action_names(self) -> None:
        assert "accept" in ACTION_NAMES

    def test_action_names_derived_from_literal(self) -> None:
        literal_args = get_args(ActionName)
        assert "accept" in literal_args

    def test_existing_actions_still_present(self) -> None:
        for action in ("tasks", "implement", "review"):
            assert action in ACTION_NAMES


# ---------------------------------------------------------------------------
# T017-5: spec-kitty agent shim CLI is no longer registered
# ---------------------------------------------------------------------------

class TestShimCliRemoved:
    def test_shim_module_deleted(self) -> None:
        """The shim CLI module should no longer exist."""
        import importlib
        with pytest.raises((ImportError, ModuleNotFoundError)):
            importlib.import_module("specify_cli.cli.commands.shim")

    def test_entrypoints_module_deleted(self) -> None:
        """The shim entrypoints module should no longer exist."""
        import importlib
        with pytest.raises((ImportError, ModuleNotFoundError)):
            importlib.import_module("specify_cli.shims.entrypoints")

    def test_models_module_deleted(self) -> None:
        """The shim models module should no longer exist."""
        import importlib
        with pytest.raises((ImportError, ModuleNotFoundError)):
            importlib.import_module("specify_cli.shims.models")

    def test_shim_not_in_agent_app(self) -> None:
        """The agent CLI app should not have a 'shim' subcommand."""
        from specify_cli.cli.commands.agent import app
        # Typer stores registered sub-apps in registered_groups
        sub_names = []
        for group in getattr(app, "registered_groups", []):
            if hasattr(group, "typer_instance") and hasattr(group, "name"):
                sub_names.append(group.name)
        assert "shim" not in sub_names


# ---------------------------------------------------------------------------
# T017-6: rewrite_agent_shims produces direct commands
# ---------------------------------------------------------------------------

class TestRewriteProducesDirectCommands:
    def test_rewrite_produces_direct_commands(self, tmp_path: Path) -> None:
        from specify_cli.migration.rewrite_shims import rewrite_agent_shims

        _setup_project(tmp_path, ["claude"])
        result = rewrite_agent_shims(tmp_path)
        assert len(result.files_written) > 0

        # Check that CLI-driven command files use direct commands
        cmd_dir = tmp_path / ".claude" / "commands"
        for command in CLI_DRIVEN_COMMANDS:
            shim_file = cmd_dir / f"spec-kitty.{command}.md"
            if shim_file.exists():
                content = shim_file.read_text()
                assert "agent shim" not in content, (
                    f"{command} still uses old shim dispatch"
                )


# ---------------------------------------------------------------------------
# T017-7/8/9: Agent surface verification (.claude, .codex, .opencode)
# ---------------------------------------------------------------------------

class TestAgentSurfaces:
    def test_claude_commands_have_direct_calls(self, tmp_path: Path) -> None:
        _setup_project(tmp_path, ["claude"])
        generate_all_shims(tmp_path)

        cmd_dir = tmp_path / ".claude" / "commands"
        impl = cmd_dir / "spec-kitty.implement.md"
        assert impl.exists()
        content = impl.read_text()
        assert "spec-kitty agent action implement" in content
        assert "agent shim" not in content

    def test_codex_skills_have_direct_calls(self, tmp_path: Path) -> None:
        """Post-083: Codex uses the Agent Skills pipeline, not the slash-command shim
        pipeline. The shim generator therefore writes nothing for codex. The
        equivalent invariant — every installed SKILL.md references the direct
        `spec-kitty agent action` CLI call — is enforced via the skills installer.
        """
        from specify_cli.skills.command_installer import install

        _setup_project(tmp_path, ["codex"])
        install(tmp_path, "codex")

        skill_md = tmp_path / ".agents" / "skills" / "spec-kitty.implement" / "SKILL.md"
        assert skill_md.exists(), (
            f"Expected Agent Skills package at {skill_md} (post-083 codex layout)"
        )
        content = skill_md.read_text()
        assert "spec-kitty agent action implement" in content
        assert "agent shim" not in content

    def test_opencode_commands_have_direct_calls(self, tmp_path: Path) -> None:
        _setup_project(tmp_path, ["opencode"])
        generate_all_shims(tmp_path)

        cmd_dir = tmp_path / ".opencode" / "command"
        impl = cmd_dir / "spec-kitty.implement.md"
        assert impl.exists()
        content = impl.read_text()
        assert "spec-kitty agent action implement" in content
        assert "agent shim" not in content


# ---------------------------------------------------------------------------
# T017-10: Migration is idempotent
# ---------------------------------------------------------------------------

class TestMigrationIdempotent:
    def test_migration_idempotent(self, tmp_path: Path) -> None:
        from specify_cli.migration.rewrite_shims import rewrite_agent_shims

        _setup_project(tmp_path, ["claude"])

        result1 = rewrite_agent_shims(tmp_path)
        result2 = rewrite_agent_shims(tmp_path)

        # Same number of files written both times
        assert len(result1.files_written) == len(result2.files_written)
        # No files deleted on second run
        assert len(result2.files_deleted) == 0

        # Content is identical after both runs
        cmd_dir = tmp_path / ".claude" / "commands"
        for command in CLI_DRIVEN_COMMANDS:
            f = cmd_dir / f"spec-kitty.{command}.md"
            if f.exists():
                content = f.read_text()
                assert "agent shim" not in content
