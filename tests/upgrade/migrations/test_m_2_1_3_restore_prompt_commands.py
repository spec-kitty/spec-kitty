"""Tests for the 2.1.3 restore-prompt-commands migration.

Covers:
- T016: Migration file exists and is properly structured
- T017: Migration is idempotent (second run returns empty changes)
- T018: Migration replaces thin shims for prompt-driven commands only,
        leaves CLI-driven thin shims untouched, handles dry-run mode
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.fast

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

THIN_SHIM_TEMPLATE = (
    "Run this exact command and treat its output as authoritative.\n"
    "Do not rediscover context from branches, files, or prompt contents.\n"
    "\n"
    '`spec-kitty agent shim {cmd} --agent claude --raw-args "$ARGUMENTS"`\n'
)

FULL_PROMPT_CONTENT = ("# Full workflow prompt\n\n" + "Details.\n" * 15)

ALL_COMMANDS = [
    "specify",
    "plan",
    "tasks",
    "tasks-outline",
    "tasks-packages",
    "checklist",
    "analyze",
    "research",
    "charter",
    "feedback",
    "implement",
    "review",
    "accept",
    "consolidate",
    "status",
    "dashboard",
    "tasks-finalize",
]


def _setup_project(tmp_path: Path, agents: list[str] | None = None) -> Path:
    """Create a minimal project with .kittify/config.yaml."""
    project = tmp_path / "project"
    project.mkdir()
    kittify = project / ".kittify"
    kittify.mkdir()

    selected_agents = agents if agents is not None else ["claude"]
    config_content = "agents:\n  available:\n"
    for agent in selected_agents:
        config_content += f"  - {agent}\n"
    (kittify / "config.yaml").write_text(config_content, encoding="utf-8")

    return project


def _create_thin_shims(agent_dir: Path, commands: list[str]) -> None:
    """Write thin 3-line shim files for every command in *commands*."""
    agent_dir.mkdir(parents=True, exist_ok=True)
    for cmd in commands:
        content = THIN_SHIM_TEMPLATE.format(cmd=cmd)
        (agent_dir / f"spec-kitty.{cmd}.md").write_text(content, encoding="utf-8")


def _make_fake_template_dir(tmp_path: Path, commands: list[str]) -> Path:
    """Create a fake command-templates directory with minimal .md files."""
    tmpl_dir = tmp_path / "command-templates"
    tmpl_dir.mkdir(parents=True, exist_ok=True)
    for cmd in commands:
        (tmpl_dir / f"{cmd}.md").write_text(
            f"# {cmd} workflow\n\n" + "Step details.\n" * 20,
            encoding="utf-8",
        )
    return tmpl_dir


def _patch_render(fake_content: str = FULL_PROMPT_CONTENT):
    """Return a patch for render_command_template that returns *fake_content*."""
    return patch(
        "specify_cli.upgrade.migrations.m_2_1_3_restore_prompt_commands._render_full_prompt",
        return_value=fake_content,
    )


# ---------------------------------------------------------------------------
# Tests: _is_thin_shim helper
# ---------------------------------------------------------------------------


class TestIsThinShim:
    def test_thin_shim_detected(self, tmp_path: Path) -> None:
        """A 4-line file containing SHIM_MARKER is a thin shim."""
        from specify_cli.upgrade.migrations.m_2_1_3_restore_prompt_commands import _is_thin_shim

        f = tmp_path / "spec-kitty.specify.md"
        f.write_text(THIN_SHIM_TEMPLATE.format(cmd="specify"), encoding="utf-8")
        assert _is_thin_shim(f) is True

    def test_full_prompt_not_a_shim(self, tmp_path: Path) -> None:
        """A long file is not detected as a thin shim even if SHIM_MARKER appears."""
        from specify_cli.upgrade.migrations.m_2_1_3_restore_prompt_commands import _is_thin_shim

        f = tmp_path / "spec-kitty.specify.md"
        long_content = FULL_PROMPT_CONTENT
        f.write_text(long_content, encoding="utf-8")
        assert _is_thin_shim(f) is False

    def test_short_file_without_marker_not_a_shim(self, tmp_path: Path) -> None:
        """A short file WITHOUT the shim marker is not detected as a thin shim."""
        from specify_cli.upgrade.migrations.m_2_1_3_restore_prompt_commands import _is_thin_shim

        f = tmp_path / "spec-kitty.specify.md"
        f.write_text("# specify\nDo stuff.\n", encoding="utf-8")
        assert _is_thin_shim(f) is False

    def test_missing_file_returns_false(self, tmp_path: Path) -> None:
        """_is_thin_shim returns False for non-existent files (no exception)."""
        from specify_cli.upgrade.migrations.m_2_1_3_restore_prompt_commands import _is_thin_shim

        assert _is_thin_shim(tmp_path / "nonexistent.md") is False


# ---------------------------------------------------------------------------
# Tests: detect()
# ---------------------------------------------------------------------------


class TestDetect:
    def test_detect_true_when_thin_shims_present(self, tmp_path: Path) -> None:
        """detect() returns True when prompt-driven commands have thin shims."""
        from specify_cli.upgrade.migrations.m_2_1_3_restore_prompt_commands import (
            RestorePromptCommandsMigration,
        )

        project = _setup_project(tmp_path)
        claude_dir = project / ".claude" / "commands"
        _create_thin_shims(claude_dir, ALL_COMMANDS)

        assert RestorePromptCommandsMigration().detect(project) is True

    def test_detect_false_when_no_shims(self, tmp_path: Path) -> None:
        """detect() returns False when no agent directories exist."""
        from specify_cli.upgrade.migrations.m_2_1_3_restore_prompt_commands import (
            RestorePromptCommandsMigration,
        )

        project = _setup_project(tmp_path)
        assert RestorePromptCommandsMigration().detect(project) is False

    def test_detect_false_when_already_full_prompts(self, tmp_path: Path) -> None:
        """detect() returns False when prompt-driven files are already full prompts."""
        from specify_cli.shims.registry import PROMPT_DRIVEN_COMMANDS
        from specify_cli.upgrade.migrations.m_2_1_3_restore_prompt_commands import (
            RestorePromptCommandsMigration,
        )

        project = _setup_project(tmp_path)
        claude_dir = project / ".claude" / "commands"
        claude_dir.mkdir(parents=True)
        # Write full prompts for prompt-driven commands
        for cmd in PROMPT_DRIVEN_COMMANDS:
            (claude_dir / f"spec-kitty.{cmd}.md").write_text(FULL_PROMPT_CONTENT, encoding="utf-8")

        assert RestorePromptCommandsMigration().detect(project) is False


# ---------------------------------------------------------------------------
# Tests: can_apply()
# ---------------------------------------------------------------------------


class TestCanApply:
    def test_can_apply_true_when_templates_exist(self, tmp_path: Path) -> None:
        """can_apply() returns True when runtime templates are available."""
        from specify_cli.upgrade.migrations.m_2_1_3_restore_prompt_commands import (
            RestorePromptCommandsMigration,
        )

        project = _setup_project(tmp_path)
        fake_tmpl_dir = _make_fake_template_dir(tmp_path, ["specify"])

        with patch(
            "specify_cli.upgrade.migrations.m_2_1_3_restore_prompt_commands._get_runtime_command_templates_dir",
            return_value=fake_tmpl_dir,
        ):
            ok, reason = RestorePromptCommandsMigration().can_apply(project)

        assert ok is True
        assert reason == ""

    def test_can_apply_false_when_templates_missing(self, tmp_path: Path) -> None:
        """can_apply() returns False when runtime templates cannot be found."""
        from specify_cli.upgrade.migrations.m_2_1_3_restore_prompt_commands import (
            RestorePromptCommandsMigration,
        )

        project = _setup_project(tmp_path)

        with patch(
            "specify_cli.upgrade.migrations.m_2_1_3_restore_prompt_commands._get_runtime_command_templates_dir",
            return_value=None,
        ):
            ok, reason = RestorePromptCommandsMigration().can_apply(project)

        assert ok is False
        assert "not found" in reason


# ---------------------------------------------------------------------------
# Tests: apply() — main scenario
# ---------------------------------------------------------------------------


class TestApply:
    def test_replaces_prompt_driven_shims_leaves_cli_driven_intact(
        self, tmp_path: Path
    ) -> None:
        """apply() replaces 9 prompt-driven thin shims, leaves 7 CLI-driven shims untouched."""
        from specify_cli.shims.registry import CLI_DRIVEN_COMMANDS, PROMPT_DRIVEN_COMMANDS
        from specify_cli.upgrade.migrations.m_2_1_3_restore_prompt_commands import (
            RestorePromptCommandsMigration,
        )

        project = _setup_project(tmp_path)
        claude_dir = project / ".claude" / "commands"
        _create_thin_shims(claude_dir, ALL_COMMANDS)

        fake_tmpl_dir = _make_fake_template_dir(tmp_path, list(PROMPT_DRIVEN_COMMANDS))

        with patch(
            "specify_cli.upgrade.migrations.m_2_1_3_restore_prompt_commands._get_runtime_command_templates_dir",
            return_value=fake_tmpl_dir,
        ), _patch_render():
            result = RestorePromptCommandsMigration().apply(project)

        assert result.success is True

        # Prompt-driven commands must now be full prompts (not thin shims)
        for cmd in PROMPT_DRIVEN_COMMANDS:
            f = claude_dir / f"spec-kitty.{cmd}.md"
            assert f.exists(), f"spec-kitty.{cmd}.md should exist"
            content = f.read_text(encoding="utf-8")
            assert "spec-kitty agent shim" not in content, (
                f"{cmd} should be a full prompt, not a shim"
            )

        # CLI-driven commands must remain as thin shims (untouched)
        for cmd in CLI_DRIVEN_COMMANDS:
            f = claude_dir / f"spec-kitty.{cmd}.md"
            assert f.exists(), f"spec-kitty.{cmd}.md should exist"
            content = f.read_text(encoding="utf-8")
            assert "spec-kitty agent shim" in content, (
                f"{cmd} should remain a thin CLI shim"
            )

        # changes_made should list exactly the 9 prompt-driven commands
        assert len(result.changes_made) == len(PROMPT_DRIVEN_COMMANDS)

    def test_idempotent_second_run_makes_no_changes(self, tmp_path: Path) -> None:
        """Running apply() twice produces zero changes on the second run.

        After the first run, prompt-driven files are full prompts (many lines,
        no shim marker), so _is_thin_shim() returns False and they are skipped.
        """
        from specify_cli.shims.registry import PROMPT_DRIVEN_COMMANDS
        from specify_cli.upgrade.migrations.m_2_1_3_restore_prompt_commands import (
            RestorePromptCommandsMigration,
        )

        project = _setup_project(tmp_path)
        claude_dir = project / ".claude" / "commands"
        _create_thin_shims(claude_dir, ALL_COMMANDS)

        fake_tmpl_dir = _make_fake_template_dir(tmp_path, list(PROMPT_DRIVEN_COMMANDS))
        migration = RestorePromptCommandsMigration()

        with patch(
            "specify_cli.upgrade.migrations.m_2_1_3_restore_prompt_commands._get_runtime_command_templates_dir",
            return_value=fake_tmpl_dir,
        ), _patch_render():
            result1 = migration.apply(project)
            result2 = migration.apply(project)

        assert result1.success is True
        assert len(result1.changes_made) == len(PROMPT_DRIVEN_COMMANDS)

        # Second run: no thin shims remain for prompt-driven commands
        assert result2.success is True
        assert any("nothing to do" in c.lower() for c in result2.changes_made), (
            f"Second run should report 'nothing to do', got: {result2.changes_made}"
        )

    def test_dry_run_reports_changes_but_writes_nothing(self, tmp_path: Path) -> None:
        """apply(dry_run=True) lists planned changes but does not modify files."""
        from specify_cli.shims.registry import PROMPT_DRIVEN_COMMANDS
        from specify_cli.upgrade.migrations.m_2_1_3_restore_prompt_commands import (
            RestorePromptCommandsMigration,
        )

        project = _setup_project(tmp_path)
        claude_dir = project / ".claude" / "commands"
        _create_thin_shims(claude_dir, ALL_COMMANDS)

        original_contents = {
            cmd: (claude_dir / f"spec-kitty.{cmd}.md").read_text(encoding="utf-8")
            for cmd in ALL_COMMANDS
        }

        fake_tmpl_dir = _make_fake_template_dir(tmp_path, list(PROMPT_DRIVEN_COMMANDS))

        with patch(
            "specify_cli.upgrade.migrations.m_2_1_3_restore_prompt_commands._get_runtime_command_templates_dir",
            return_value=fake_tmpl_dir,
        ), _patch_render():
            result = RestorePromptCommandsMigration().apply(project, dry_run=True)

        assert result.success is True
        # Changes are reported
        assert len(result.changes_made) == len(PROMPT_DRIVEN_COMMANDS)
        assert all("Would restore" in c for c in result.changes_made)

        # No files were actually changed
        for cmd in ALL_COMMANDS:
            current = (claude_dir / f"spec-kitty.{cmd}.md").read_text(encoding="utf-8")
            assert current == original_contents[cmd], (
                f"{cmd}.md was modified during dry run — should be unchanged"
            )

    def test_skips_nonexistent_agent_dirs(self, tmp_path: Path) -> None:
        """apply() does not create agent directories that don't exist."""
        from specify_cli.upgrade.migrations.m_2_1_3_restore_prompt_commands import (
            RestorePromptCommandsMigration,
        )

        # Project configured with two agents, but only claude dir exists
        project = _setup_project(tmp_path, agents=["claude", "codex"])
        # No agent directories created

        fake_tmpl_dir = _make_fake_template_dir(tmp_path, ALL_COMMANDS)

        with patch(
            "specify_cli.upgrade.migrations.m_2_1_3_restore_prompt_commands._get_runtime_command_templates_dir",
            return_value=fake_tmpl_dir,
        ):
            result = RestorePromptCommandsMigration().apply(project)

        assert result.success is True
        # No directories should have been created
        assert not (project / ".claude" / "commands").exists()
        assert not (project / ".codex" / "prompts").exists()

    def test_skips_unconfigured_agents(self, tmp_path: Path) -> None:
        """apply() only processes configured agents; ignores others even if dirs exist."""
        from specify_cli.shims.registry import PROMPT_DRIVEN_COMMANDS
        from specify_cli.upgrade.migrations.m_2_1_3_restore_prompt_commands import (
            RestorePromptCommandsMigration,
        )

        # Only claude is configured
        project = _setup_project(tmp_path, agents=["claude"])

        # Create both claude and codex dirs with thin shims
        claude_dir = project / ".claude" / "commands"
        codex_dir = project / ".codex" / "prompts"
        _create_thin_shims(claude_dir, ALL_COMMANDS)
        _create_thin_shims(codex_dir, ALL_COMMANDS)

        # Snapshot codex shims before migration
        codex_shims_before = {
            cmd: (codex_dir / f"spec-kitty.{cmd}.md").read_text(encoding="utf-8")
            for cmd in ALL_COMMANDS
        }

        fake_tmpl_dir = _make_fake_template_dir(tmp_path, list(PROMPT_DRIVEN_COMMANDS))

        with patch(
            "specify_cli.upgrade.migrations.m_2_1_3_restore_prompt_commands._get_runtime_command_templates_dir",
            return_value=fake_tmpl_dir,
        ), _patch_render():
            result = RestorePromptCommandsMigration().apply(project)

        assert result.success is True

        # claude prompt-driven commands should be restored
        for cmd in PROMPT_DRIVEN_COMMANDS:
            f = claude_dir / f"spec-kitty.{cmd}.md"
            content = f.read_text(encoding="utf-8")
            assert "spec-kitty agent shim" not in content, (
                f"claude/{cmd} should be a full prompt"
            )

        # codex shims should be untouched (not in config)
        for cmd in ALL_COMMANDS:
            current = (codex_dir / f"spec-kitty.{cmd}.md").read_text(encoding="utf-8")
            assert current == codex_shims_before[cmd], (
                f"codex/{cmd} should be untouched (not in agent config)"
            )

    def test_returns_error_when_no_templates_dir(self, tmp_path: Path) -> None:
        """apply() returns success=False when runtime templates are unavailable."""
        from specify_cli.upgrade.migrations.m_2_1_3_restore_prompt_commands import (
            RestorePromptCommandsMigration,
        )

        project = _setup_project(tmp_path)
        claude_dir = project / ".claude" / "commands"
        _create_thin_shims(claude_dir, ALL_COMMANDS)

        with patch(
            "specify_cli.upgrade.migrations.m_2_1_3_restore_prompt_commands._get_runtime_command_templates_dir",
            return_value=None,
        ):
            result = RestorePromptCommandsMigration().apply(project)

        assert result.success is False
        assert len(result.errors) > 0

    def test_full_prompt_passthrough_not_replaced(self, tmp_path: Path) -> None:
        """Files that are already full prompts are left completely unchanged."""
        from specify_cli.shims.registry import PROMPT_DRIVEN_COMMANDS
        from specify_cli.upgrade.migrations.m_2_1_3_restore_prompt_commands import (
            RestorePromptCommandsMigration,
        )

        project = _setup_project(tmp_path)
        claude_dir = project / ".claude" / "commands"
        claude_dir.mkdir(parents=True)

        # Write full prompts for prompt-driven commands already
        custom_content = "# Custom project override\n\nThis is a custom workflow.\n" * 10
        for cmd in PROMPT_DRIVEN_COMMANDS:
            (claude_dir / f"spec-kitty.{cmd}.md").write_text(custom_content, encoding="utf-8")

        fake_tmpl_dir = _make_fake_template_dir(tmp_path, list(PROMPT_DRIVEN_COMMANDS))

        with patch(
            "specify_cli.upgrade.migrations.m_2_1_3_restore_prompt_commands._get_runtime_command_templates_dir",
            return_value=fake_tmpl_dir,
        ), _patch_render():
            result = RestorePromptCommandsMigration().apply(project)

        assert result.success is True
        # Nothing changed — the "nothing to do" sentinel should be present
        assert any("nothing to do" in c.lower() for c in result.changes_made), (
            f"Expected 'nothing to do' sentinel, got: {result.changes_made}"
        )

        # Custom content preserved
        for cmd in PROMPT_DRIVEN_COMMANDS:
            content = (claude_dir / f"spec-kitty.{cmd}.md").read_text(encoding="utf-8")
            assert content == custom_content, f"{cmd}: custom content should be preserved"


# ---------------------------------------------------------------------------
# Tests: registration
# ---------------------------------------------------------------------------


class TestRegistration:
    def test_migration_is_registered(self) -> None:
        """RestorePromptCommandsMigration is discoverable via MigrationRegistry."""
        from specify_cli.upgrade.registry import MigrationRegistry
        from specify_cli.upgrade.migrations import auto_discover_migrations

        MigrationRegistry.clear()
        auto_discover_migrations()

        all_ids = list(MigrationRegistry._migrations.keys())
        assert "2.1.3_restore_prompt_commands" in all_ids

    def test_migration_has_correct_target_version(self) -> None:
        """target_version is '2.1.3'."""
        from specify_cli.upgrade.migrations.m_2_1_3_restore_prompt_commands import (
            RestorePromptCommandsMigration,
        )

        assert RestorePromptCommandsMigration.target_version == "2.1.3"

    def test_migration_has_description(self) -> None:
        """description is a non-empty string."""
        from specify_cli.upgrade.migrations.m_2_1_3_restore_prompt_commands import (
            RestorePromptCommandsMigration,
        )

        assert RestorePromptCommandsMigration.description != ""
