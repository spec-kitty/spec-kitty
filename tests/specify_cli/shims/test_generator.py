"""Tests for shims/generator.py -- direct canonical command generation."""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.shims.generator import (
    AGENT_ARG_PLACEHOLDERS,
    SHIM_DESCRIPTIONS,
    _canonical_command,
    generate_shim_content,
    generate_shim_content_toml,
    generate_shim_content_for_agent,
    generate_all_shims,
)
from specify_cli.core.config import AGENT_COMMAND_CONFIG
from specify_cli.shims.registry import CLI_DRIVEN_COMMANDS, CONSUMER_SKILLS, PROMPT_DRIVEN_COMMANDS


# ---------------------------------------------------------------------------
# _canonical_command
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.unit, pytest.mark.fast]
class TestCanonicalCommand:
    def test_implement(self) -> None:
        cmd = _canonical_command("implement", "claude", "$ARGUMENTS")
        assert cmd == "spec-kitty agent action implement $ARGUMENTS --agent claude"

    def test_review(self) -> None:
        cmd = _canonical_command("review", "codex", "$PROMPT")
        assert cmd == "spec-kitty agent action review $PROMPT --agent codex"

    def test_accept(self) -> None:
        cmd = _canonical_command("accept", "claude", "$ARGUMENTS")
        assert cmd == "spec-kitty agent mission accept $ARGUMENTS"

    def test_status(self) -> None:
        cmd = _canonical_command("status", "claude", "$ARGUMENTS")
        assert cmd == "spec-kitty agent tasks status $ARGUMENTS"

    def test_consolidate(self) -> None:
        cmd = _canonical_command("consolidate", "claude", "$ARGUMENTS")
        assert cmd == "spec-kitty consolidate $ARGUMENTS"

    def test_dashboard(self) -> None:
        cmd = _canonical_command("dashboard", "claude", "$ARGUMENTS")
        assert cmd == "spec-kitty dashboard $ARGUMENTS"

    def test_tasks_finalize(self) -> None:
        cmd = _canonical_command("tasks-finalize", "claude", "$ARGUMENTS")
        assert cmd == "spec-kitty agent mission finalize-tasks $ARGUMENTS"

    def test_unknown_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown CLI-driven command"):
            _canonical_command("nonexistent", "claude", "$ARGUMENTS")

    def test_all_cli_driven_commands_mapped(self) -> None:
        """Every command in CLI_DRIVEN_COMMANDS must have a canonical mapping."""
        for cmd in CLI_DRIVEN_COMMANDS:
            result = _canonical_command(cmd, "claude", "$ARGUMENTS")
            assert "spec-kitty" in result


# ---------------------------------------------------------------------------
# generate_shim_content
# ---------------------------------------------------------------------------

class TestGenerateShimContent:
    def test_total_line_count(self) -> None:
        content = generate_shim_content("implement", "claude", "$ARGUMENTS")
        lines = content.rstrip("\n").splitlines()
        assert len(lines) <= 10
        assert "## Startup Upgrade Check" not in lines

    def test_starts_with_yaml_frontmatter(self) -> None:
        """Line 1 must be ``---`` so Claude Code parses the description."""
        content = generate_shim_content("implement", "claude", "$ARGUMENTS")
        lines = content.splitlines()
        assert lines[0] == "---"
        assert lines[1] == "description: Execute a work package implementation"
        assert lines[2] == "---"

    def test_description_uses_shim_descriptions_map(self) -> None:
        for command, expected in SHIM_DESCRIPTIONS.items():
            content = generate_shim_content(command, "claude", "$ARGUMENTS")
            assert f"description: {expected}" in content

    def test_description_fallback_for_unknown_command(self) -> None:
        # Unknown commands still receive a description (defensive default).
        # Use "implement" via the canonical map for the CLI body but pass an
        # unmapped key to the description map by monkey-patching: we exercise
        # the fallback branch directly here.
        from specify_cli.shims import generator as gen

        original = gen.SHIM_DESCRIPTIONS
        try:
            gen.SHIM_DESCRIPTIONS = {}
            content = generate_shim_content("implement", "claude", "$ARGUMENTS")
        finally:
            gen.SHIM_DESCRIPTIONS = original
        assert "description: spec-kitty implement" in content

    def test_version_marker_after_frontmatter(self) -> None:
        """Marker must follow the closing ``---`` so YAML frontmatter parses cleanly."""
        content = generate_shim_content("implement", "claude", "$ARGUMENTS")
        lines = content.splitlines()
        assert lines[3].startswith("<!-- spec-kitty-command-version:")

    def test_command_instruction_after_version_marker(self) -> None:
        content = generate_shim_content("implement", "claude", "$ARGUMENTS")
        lines = content.splitlines()
        assert lines[3].startswith("<!-- spec-kitty-command-version:")
        assert lines[4] == "Run this exact command and treat its output as authoritative."
        assert "spec-kitty upgrade --agent-check --json" not in content

    def test_invariant_line_position(self) -> None:
        content = generate_shim_content("implement", "claude", "$ARGUMENTS")
        lines = content.splitlines()
        assert lines.index("Run this exact command and treat its output as authoritative.") == 4

    def test_prohibition_line_position(self) -> None:
        content = generate_shim_content("implement", "claude", "$ARGUMENTS")
        lines = content.splitlines()
        assert (
            "Do not rediscover context from branches, files, prompt contents, or separate charter loads."
        ) in lines

    def test_direct_implement_command(self) -> None:
        content = generate_shim_content("implement", "claude", "$ARGUMENTS")
        assert "spec-kitty agent action implement $ARGUMENTS --agent claude" in content

    def test_direct_review_command(self) -> None:
        content = generate_shim_content("review", "codex", "$PROMPT")
        assert "spec-kitty agent action review $PROMPT --agent codex" in content

    def test_direct_accept_command(self) -> None:
        content = generate_shim_content("accept", "claude", "$ARGUMENTS")
        assert "spec-kitty agent mission accept $ARGUMENTS" in content

    def test_no_shim_dispatch(self) -> None:
        """Generated content must NOT reference the old shim dispatch path."""
        for cmd in CLI_DRIVEN_COMMANDS:
            content = generate_shim_content(cmd, "claude", "$ARGUMENTS")
            assert "agent shim" not in content

    def test_arg_placeholder_substituted(self) -> None:
        content = generate_shim_content("review", "codex", "$PROMPT")
        assert "$PROMPT" in content
        assert "$ARGUMENTS" not in content

    def test_agent_name_in_implement_review(self) -> None:
        for agent in ["claude", "codex", "opencode", "gemini"]:
            content = generate_shim_content("implement", agent, "$ARGUMENTS")
            assert f"--agent {agent}" in content

    def test_no_workflow_logic(self) -> None:
        """Command files must not contain workflow keywords."""
        content = generate_shim_content("implement", "claude", "$ARGUMENTS")
        forbidden = ["worktree", "git checkout", "if [", "mkdir"]
        for token in forbidden:
            assert token not in content, f"Workflow logic leaked: {token!r}"

    def test_shim_content_mentions_mission(self) -> None:
        content = generate_shim_content("status", "claude", "$ARGUMENTS")
        assert "--mission" in content

    def test_shim_content_mission_hint_line(self) -> None:
        content = generate_shim_content("implement", "claude", "$ARGUMENTS")
        lines = content.splitlines()
        assert (
            "When mission selection is required, pass --mission <handle> (mission_id, mid8, or mission_slug)."
        ) in lines

    def test_shim_content_version_marker_present_in_head(self) -> None:
        """Marker must appear in the file head (no longer line 0 — line 3)."""
        content = generate_shim_content("implement", "claude", "$ARGUMENTS")
        head = content.splitlines()[:6]
        assert any(line.startswith("<!-- spec-kitty-command-version:") for line in head)

    def test_every_cli_driven_command_has_description(self) -> None:
        for command in CLI_DRIVEN_COMMANDS:
            assert command in SHIM_DESCRIPTIONS, (
                f"CLI-driven command '{command}' missing entry in SHIM_DESCRIPTIONS"
            )


# ---------------------------------------------------------------------------
# Agent-specific placeholder mapping
# ---------------------------------------------------------------------------

class TestAgentArgPlaceholders:
    def test_claude_uses_arguments(self) -> None:
        assert AGENT_ARG_PLACEHOLDERS["claude"] == "$ARGUMENTS"

    def test_codex_uses_prompt(self) -> None:
        assert AGENT_ARG_PLACEHOLDERS["codex"] == "$PROMPT"

    def test_claude_content_has_arguments(self) -> None:
        content = generate_shim_content("implement", "claude", AGENT_ARG_PLACEHOLDERS["claude"])
        assert "$ARGUMENTS" in content

    def test_codex_content_has_prompt(self) -> None:
        content = generate_shim_content("implement", "codex", AGENT_ARG_PLACEHOLDERS["codex"])
        assert "$PROMPT" in content


# ---------------------------------------------------------------------------
# generate_all_shims (filesystem)
# ---------------------------------------------------------------------------

def _setup_kittify_config(tmp_path: Path, agents: list[str]) -> None:
    """Write a minimal .kittify/config.yaml selecting specific agents."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    available_lines = "\n".join(f"    - {a}" for a in agents)
    (kittify / "config.yaml").write_text(
        f"project:\n  uuid: test-uuid-1234\nagents:\n  available:\n{available_lines}\n",
        encoding="utf-8",
    )


class TestGenerateAllShims:
    def test_returns_list_of_paths(self, tmp_path: Path) -> None:
        _setup_kittify_config(tmp_path, ["claude"])
        (tmp_path / ".claude" / "commands").mkdir(parents=True)
        result = generate_all_shims(tmp_path)
        assert isinstance(result, list)
        assert all(isinstance(p, Path) for p in result)

    def test_creates_files_for_configured_agents(self, tmp_path: Path) -> None:
        _setup_kittify_config(tmp_path, ["claude", "codex"])
        (tmp_path / ".claude" / "commands").mkdir(parents=True)
        (tmp_path / ".codex" / "prompts").mkdir(parents=True)

        written = generate_all_shims(tmp_path)

        # Only CLI-driven skills should get command files
        written_names = {p.name for p in written}
        for skill in CLI_DRIVEN_COMMANDS:
            assert f"spec-kitty.{skill}.md" in written_names

    def test_prompt_driven_skills_not_written(self, tmp_path: Path) -> None:
        """Prompt-driven commands must NOT receive command files."""
        _setup_kittify_config(tmp_path, ["claude"])
        (tmp_path / ".claude" / "commands").mkdir(parents=True)
        generate_all_shims(tmp_path)

        cmd_dir = tmp_path / ".claude" / "commands"
        for skill in PROMPT_DRIVEN_COMMANDS:
            assert not (cmd_dir / f"spec-kitty.{skill}.md").exists(), (
                f"Prompt-driven skill '{skill}' should not get a command file"
            )

    def test_generates_exactly_seven_files_per_agent(self, tmp_path: Path) -> None:
        _setup_kittify_config(tmp_path, ["claude"])
        (tmp_path / ".claude" / "commands").mkdir(parents=True)
        written = generate_all_shims(tmp_path)
        assert len(written) == len(CLI_DRIVEN_COMMANDS)
        assert len(CLI_DRIVEN_COMMANDS) == 7

    def test_files_have_direct_commands(self, tmp_path: Path) -> None:
        _setup_kittify_config(tmp_path, ["claude"])
        (tmp_path / ".claude" / "commands").mkdir(parents=True)
        generate_all_shims(tmp_path)

        impl_file = tmp_path / ".claude" / "commands" / "spec-kitty.implement.md"
        assert impl_file.exists()
        content = impl_file.read_text(encoding="utf-8")
        assert "Run this exact command and treat its output as authoritative." in content
        assert "Do not rediscover context" in content
        assert "spec-kitty agent action implement" in content
        assert "agent shim" not in content

    def test_correct_placeholder_per_agent(self, tmp_path: Path) -> None:
        """Each agent receives its native argument handling.

        Claude (slash-command pipeline): shim generator writes $ARGUMENTS to
        .claude/commands/spec-kitty.*.md.

        Codex (Agent Skills pipeline, post-083): skills installer renders
        .agents/skills/spec-kitty.*/SKILL.md with NO $ARGUMENTS token — the
        renderer's contract (see command_renderer.render docstring) guarantees
        no stray $ARGUMENTS survives; user input is delivered via the canonical
        "User Input" section of the SKILL.md body instead.
        """
        from specify_cli.skills.command_installer import install

        _setup_kittify_config(tmp_path, ["claude", "codex"])
        (tmp_path / ".claude" / "commands").mkdir(parents=True)
        generate_all_shims(tmp_path)
        install(tmp_path, "codex")

        claude_file = tmp_path / ".claude" / "commands" / "spec-kitty.implement.md"
        codex_file = (
            tmp_path / ".agents" / "skills" / "spec-kitty.implement" / "SKILL.md"
        )

        assert "$ARGUMENTS" in claude_file.read_text()
        codex_text = codex_file.read_text()
        assert "$ARGUMENTS" not in codex_text, (
            "command_renderer contract violated: SKILL.md must not contain "
            "stray $ARGUMENTS tokens."
        )
        # The canonical user-input section must still be present.
        assert "User Input" in codex_text

    def test_result_is_sorted(self, tmp_path: Path) -> None:
        _setup_kittify_config(tmp_path, ["claude"])
        (tmp_path / ".claude" / "commands").mkdir(parents=True)
        result = generate_all_shims(tmp_path)
        assert result == sorted(result)

    def test_unconfigured_agent_not_written(self, tmp_path: Path) -> None:
        _setup_kittify_config(tmp_path, ["claude"])
        (tmp_path / ".codex" / "prompts").mkdir(parents=True)
        (tmp_path / ".claude" / "commands").mkdir(parents=True)

        generate_all_shims(tmp_path)

        codex_impl = tmp_path / ".codex" / "prompts" / "spec-kitty.implement.md"
        assert not codex_impl.exists()

    def test_existing_files_overwritten(self, tmp_path: Path) -> None:
        _setup_kittify_config(tmp_path, ["claude"])
        cmd_dir = tmp_path / ".claude" / "commands"
        cmd_dir.mkdir(parents=True)
        target = cmd_dir / "spec-kitty.implement.md"
        target.write_text("old content", encoding="utf-8")

        generate_all_shims(tmp_path)

        assert target.read_text(encoding="utf-8") != "old content"

    def test_opencode_uses_command_subdir(self, tmp_path: Path) -> None:
        _setup_kittify_config(tmp_path, ["opencode"])
        (tmp_path / ".opencode" / "command").mkdir(parents=True)
        generate_all_shims(tmp_path)

        impl_file = tmp_path / ".opencode" / "command" / "spec-kitty.implement.md"
        assert impl_file.exists()

    def test_windsurf_uses_workflows_subdir(self, tmp_path: Path) -> None:
        _setup_kittify_config(tmp_path, ["windsurf"])
        (tmp_path / ".windsurf" / "workflows").mkdir(parents=True)
        generate_all_shims(tmp_path)

        impl_file = tmp_path / ".windsurf" / "workflows" / "spec-kitty.implement.md"
        assert impl_file.exists()

    def test_internal_skills_not_written(self, tmp_path: Path) -> None:
        _setup_kittify_config(tmp_path, ["claude"])
        (tmp_path / ".claude" / "commands").mkdir(parents=True)
        generate_all_shims(tmp_path)

        cmd_dir = tmp_path / ".claude" / "commands"
        for internal_skill in ["doctor", "materialize", "debug"]:
            assert not (cmd_dir / f"spec-kitty.{internal_skill}.md").exists()


# ---------------------------------------------------------------------------
# generate_shim_content_toml
# ---------------------------------------------------------------------------


class TestGenerateShimContentToml:
    def test_is_valid_toml(self) -> None:
        import tomllib

        content = generate_shim_content_toml("implement", "gemini", "{{args}}")
        parsed = tomllib.loads(content)
        assert "description" in parsed
        assert "prompt" in parsed

    def test_arg_placeholder_in_prompt(self) -> None:
        import tomllib

        content = generate_shim_content_toml("implement", "gemini", "{{args}}")
        parsed = tomllib.loads(content)
        assert "{{args}}" in parsed["prompt"]
        assert "$ARGUMENTS" not in parsed["prompt"]

    def test_description_from_shim_descriptions_map(self) -> None:
        content = generate_shim_content_toml("implement", "gemini", "{{args}}")
        assert content.startswith('description = "Execute a work package implementation"')

    def test_description_fallback_for_unknown_command(self) -> None:
        content = generate_shim_content_toml("status", "gemini", "{{args}}")
        assert content.startswith('description = "Show mission and work package status"')

    def test_flat_schema_no_frontmatter(self) -> None:
        content = generate_shim_content_toml("status", "gemini", "{{args}}")
        assert "---" not in content
        assert "[[commands]]" not in content

    def test_flat_schema_structure(self) -> None:
        content = generate_shim_content_toml("status", "gemini", "{{args}}")
        assert content.startswith('description = "')
        assert 'prompt = """' in content

    def test_version_marker_in_prompt(self) -> None:
        import tomllib

        content = generate_shim_content_toml("implement", "gemini", "{{args}}")
        parsed = tomllib.loads(content)
        assert "spec-kitty-command-version:" in parsed["prompt"]

    def test_invariant_lines_in_prompt(self) -> None:
        import tomllib

        content = generate_shim_content_toml("implement", "gemini", "{{args}}")
        parsed = tomllib.loads(content)
        assert "Run this exact command and treat its output as authoritative." in parsed["prompt"]
        assert "Do not rediscover context" in parsed["prompt"]
        assert "spec-kitty upgrade --agent-check --json" not in parsed["prompt"]

    def test_canonical_cli_call_in_prompt(self) -> None:
        import tomllib

        content = generate_shim_content_toml("implement", "gemini", "{{args}}")
        parsed = tomllib.loads(content)
        assert "spec-kitty agent action implement {{args}} --agent gemini" in parsed["prompt"]


# ---------------------------------------------------------------------------
# generate_shim_content_for_agent
# ---------------------------------------------------------------------------


class TestGenerateShimContentForAgent:
    @pytest.mark.parametrize("agent_key", sorted(AGENT_COMMAND_CONFIG))
    def test_command_shims_do_not_embed_upgrade_check(self, agent_key: str) -> None:
        import tomllib

        content = generate_shim_content_for_agent("implement", agent_key)
        searchable = tomllib.loads(content)["prompt"] if AGENT_COMMAND_CONFIG[agent_key]["ext"] == "toml" else content
        assert "## Startup Upgrade Check" not in searchable
        assert "spec-kitty upgrade --agent-check --json" not in searchable

    def test_gemini_returns_toml(self) -> None:
        import tomllib

        content = generate_shim_content_for_agent("implement", "gemini")
        parsed = tomllib.loads(content)
        assert "description" in parsed
        assert "prompt" in parsed

    def test_gemini_uses_mustache_placeholder(self) -> None:
        import tomllib

        content = generate_shim_content_for_agent("status", "gemini")
        parsed = tomllib.loads(content)
        assert "{{args}}" in parsed["prompt"]
        assert "$ARGUMENTS" not in parsed["prompt"]

    def test_qwen_returns_toml(self) -> None:
        import tomllib

        content = generate_shim_content_for_agent("implement", "qwen")
        parsed = tomllib.loads(content)
        assert "description" in parsed
        assert "prompt" in parsed

    def test_qwen_uses_mustache_placeholder(self) -> None:
        import tomllib

        content = generate_shim_content_for_agent("status", "qwen")
        parsed = tomllib.loads(content)
        assert "{{args}}" in parsed["prompt"]
        assert "$ARGUMENTS" not in parsed["prompt"]

    def test_claude_returns_markdown(self) -> None:
        content = generate_shim_content_for_agent("implement", "claude")
        assert content.startswith("---\n")
        assert "$ARGUMENTS" in content
        assert "{{args}}" not in content

    def test_opencode_returns_markdown(self) -> None:
        content = generate_shim_content_for_agent("implement", "opencode")
        assert content.startswith("---\n")
        assert "$ARGUMENTS" in content

    def test_unknown_agent_returns_markdown_with_default_placeholder(self) -> None:
        content = generate_shim_content_for_agent("implement", "unknown_agent")
        assert content.startswith("---\n")
        assert "$ARGUMENTS" in content

    def test_codex_uses_prompt_placeholder(self) -> None:
        """codex is in AGENT_ARG_PLACEHOLDERS with $PROMPT but not in AGENT_COMMAND_CONFIG."""
        # codex is migrated to skills pipeline; not in AGENT_COMMAND_CONFIG
        # so falls back to Markdown with default $ARGUMENTS placeholder
        content = generate_shim_content_for_agent("implement", "codex")
        # codex not in AGENT_COMMAND_CONFIG → falls back to Markdown / $ARGUMENTS
        assert content.startswith("---\n")

    def test_all_cli_driven_commands_valid_for_gemini(self) -> None:
        """All CLI-driven commands must produce valid TOML for Gemini."""
        import tomllib

        for command in sorted(CLI_DRIVEN_COMMANDS):
            content = generate_shim_content_for_agent(command, "gemini")
            parsed = tomllib.loads(content)
            assert "description" in parsed
            assert "prompt" in parsed
            assert "{{args}}" in parsed["prompt"]

    def test_all_cli_driven_commands_valid_for_qwen(self) -> None:
        """All CLI-driven commands must produce valid TOML for Qwen."""
        import tomllib

        for command in sorted(CLI_DRIVEN_COMMANDS):
            content = generate_shim_content_for_agent(command, "qwen")
            parsed = tomllib.loads(content)
            assert "description" in parsed
            assert "prompt" in parsed
            assert "{{args}}" in parsed["prompt"]


# ---------------------------------------------------------------------------
# generate_all_shims — TOML extension for Gemini/Qwen
# ---------------------------------------------------------------------------


class TestGenerateAllShimsTomlAgents:
    def test_gemini_shims_have_toml_extension(self, tmp_path: Path) -> None:
        _setup_kittify_config(tmp_path, ["gemini"])
        (tmp_path / ".gemini" / "commands").mkdir(parents=True)
        written = generate_all_shims(tmp_path)
        names = {p.name for p in written}
        for skill in CLI_DRIVEN_COMMANDS:
            assert f"spec-kitty.{skill}.toml" in names, (
                f"Expected spec-kitty.{skill}.toml for gemini, got: {names}"
            )

    def test_gemini_shims_are_valid_toml(self, tmp_path: Path) -> None:
        import tomllib

        _setup_kittify_config(tmp_path, ["gemini"])
        (tmp_path / ".gemini" / "commands").mkdir(parents=True)
        generate_all_shims(tmp_path)
        cmd_dir = tmp_path / ".gemini" / "commands"
        for skill in CLI_DRIVEN_COMMANDS:
            toml_file = cmd_dir / f"spec-kitty.{skill}.toml"
            assert toml_file.exists(), f"Missing {toml_file}"
            parsed = tomllib.loads(toml_file.read_text(encoding="utf-8"))
            assert "description" in parsed
            assert "prompt" in parsed

    def test_qwen_shims_have_toml_extension(self, tmp_path: Path) -> None:
        _setup_kittify_config(tmp_path, ["qwen"])
        (tmp_path / ".qwen" / "commands").mkdir(parents=True)
        written = generate_all_shims(tmp_path)
        names = {p.name for p in written}
        for skill in CLI_DRIVEN_COMMANDS:
            assert f"spec-kitty.{skill}.toml" in names, (
                f"Expected spec-kitty.{skill}.toml for qwen, got: {names}"
            )

    def test_claude_shims_still_have_md_extension(self, tmp_path: Path) -> None:
        _setup_kittify_config(tmp_path, ["claude"])
        (tmp_path / ".claude" / "commands").mkdir(parents=True)
        written = generate_all_shims(tmp_path)
        names = {p.name for p in written}
        for skill in CLI_DRIVEN_COMMANDS:
            assert f"spec-kitty.{skill}.md" in names
