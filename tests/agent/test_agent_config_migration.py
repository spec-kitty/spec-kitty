"""Integration tests for config-driven agent management migrations.

Tests validate that migrations respect user's agent configuration and don't
recreate deleted agent directories.

Key behaviors tested:
1. Migrations read config.yaml to get available agents
2. Migrations skip missing directories (respect deletions)
3. Migrations only process configured agents
4. get_agent_dirs_for_project() filters correctly
"""

from __future__ import annotations


import pytest

from specify_cli.core.agent_config import AgentConfig, save_agent_config
from specify_cli.upgrade.migrations.m_0_9_1_complete_lane_migration import (
    AGENT_DIR_TO_KEY,
    CompleteLaneMigration,
    get_agent_dirs_for_project,
)
from specify_cli.upgrade.migrations.m_0_11_1_improved_workflow_templates import (
    ImprovedWorkflowTemplatesMigration,
)


pytestmark = [pytest.mark.fast]


@pytest.fixture
def mock_project_with_config(tmp_path):
    """Create a mock spec-kitty project with agent config."""
    # Create .kittify structure
    kittify = tmp_path / ".kittify"
    kittify.mkdir()

    # Create config with only opencode configured
    config = AgentConfig(available=["opencode"])
    save_agent_config(tmp_path, config)

    # Create mission templates (must contain /spec-kitty.implement so migration
    # deploys recognizable content; package command-templates/ removed in FR-010)
    missions = kittify / "missions" / "software-dev" / "command-templates"
    missions.mkdir(parents=True)
    (missions / "implement.md").write_text("/spec-kitty.implement\n\n# Implement Template\n\nscroll to the BOTTOM")
    (missions / "review.md").write_text("/spec-kitty.review\n\n# Review Template\n\nscroll to the BOTTOM")

    # Create opencode directory (configured)
    opencode = tmp_path / ".opencode" / "command"
    opencode.mkdir(parents=True)
    (opencode / "spec-kitty.implement.md").write_text("# Old Implement")

    # Create kitty-specs for migration detection
    kitty_specs = tmp_path / "kitty-specs"
    kitty_specs.mkdir()

    return tmp_path


class TestGetAgentDirsForProject:
    """Tests for get_agent_dirs_for_project() helper function."""

    def test_returns_only_configured_agents(self, mock_project_with_config):
        """Test that only configured agents are returned."""
        agent_dirs = get_agent_dirs_for_project(mock_project_with_config)

        # Should only return opencode
        assert len(agent_dirs) == 1
        assert agent_dirs[0] == (".opencode", "command")

    def test_fallback_to_all_agents_when_no_config(self, tmp_path):
        """Test fallback to all agents when config.yaml missing."""
        # Create .kittify but no config
        kittify = tmp_path / ".kittify"
        kittify.mkdir()

        agent_dirs = get_agent_dirs_for_project(tmp_path)

        # Should return all 13 slash-command agents (fallback).
        # Count went 12 post roo removal (2026-05-15, C-007) and back to 13 when
        # llxprt registered; command-skill agents use AGENT_SKILL_CONFIG and are
        # not listed in AGENT_DIRS.
        assert len(agent_dirs) == 13
        assert (".claude", "commands") in agent_dirs
        assert (".opencode", "command") in agent_dirs
        assert (".kiro", "prompts") in agent_dirs
        assert (".llxprt", "commands") in agent_dirs

    def test_fallback_when_config_empty(self, tmp_path):
        """Test fallback when config.available is empty."""
        kittify = tmp_path / ".kittify"
        kittify.mkdir()

        config = AgentConfig(available=[])
        save_agent_config(tmp_path, config)

        agent_dirs = get_agent_dirs_for_project(tmp_path)

        # Should return all 13 slash-command agents (fallback for empty).
        # See test_fallback_to_all_agents_when_no_config for count history.
        assert len(agent_dirs) == 13


class TestMigrationRespectsConfig:
    """Tests that migrations respect agent configuration."""

    def test_migration_only_processes_configured_agents(self, mock_project_with_config):
        """Test that migration only processes agents in config.yaml."""
        migration = ImprovedWorkflowTemplatesMigration()

        # Create old template for opencode (will be updated)
        opencode_implement = mock_project_with_config / ".opencode" / "command" / "spec-kitty.implement.md"
        opencode_implement.write_text("# Old implement without scroll warning")

        # Create old template for claude (should NOT be updated - not configured)
        claude_dir = mock_project_with_config / ".claude" / "commands"
        claude_dir.mkdir(parents=True)
        claude_implement = claude_dir / "spec-kitty.implement.md"
        claude_implement.write_text("# Old claude implement without scroll warning")

        # Run migration
        result = migration.apply(mock_project_with_config, dry_run=False)

        assert result.success

        # opencode should be updated (configured)
        opencode_content = opencode_implement.read_text()
        assert "/spec-kitty.implement" in opencode_content

        # claude should NOT be updated (not configured)
        claude_content = claude_implement.read_text()
        assert "/spec-kitty.implement" not in claude_content
        assert "Old claude" in claude_content

    def test_migration_skips_missing_directories(self, mock_project_with_config):
        """Test that migration skips missing directories instead of creating them."""
        # Add claude to config but don't create directory
        config = AgentConfig(available=["opencode", "claude"])
        save_agent_config(mock_project_with_config, config)

        migration = ImprovedWorkflowTemplatesMigration()

        # Run migration
        result = migration.apply(mock_project_with_config, dry_run=False)

        assert result.success

        # Claude directory should NOT be created
        claude_dir = mock_project_with_config / ".claude" / "commands"
        assert not claude_dir.exists()

    def test_migration_does_not_recreate_deleted_agents(self, mock_project_with_config):
        """Critical test: Verify deleted agents are not recreated."""
        # Simulate user deleting codex directory
        # (It was never in config, but migration should not create it)

        migration = ImprovedWorkflowTemplatesMigration()

        # Run migration
        result = migration.apply(mock_project_with_config, dry_run=False)

        assert result.success

        # codex should NOT be created (not in config)
        codex_dir = mock_project_with_config / ".codex" / "prompts"
        assert not codex_dir.exists()

        # gemini should NOT be created (not in config)
        gemini_dir = mock_project_with_config / ".gemini" / "commands"
        assert not gemini_dir.exists()


class TestMigrationDetection:
    """Tests that migration detection respects config."""

    def test_detect_ignores_unconfigured_agents(self, tmp_path):
        """Test that detect doesn't trigger on unconfigured agents with old templates."""
        migration = ImprovedWorkflowTemplatesMigration()

        # Create .kittify with config for only opencode
        kittify = tmp_path / ".kittify"
        kittify.mkdir()

        config = AgentConfig(available=["opencode"])
        save_agent_config(tmp_path, config)

        # Create mission templates (updated)
        missions = kittify / "missions" / "software-dev" / "command-templates"
        missions.mkdir(parents=True)
        (missions / "implement.md").write_text("# Updated\n\nscroll to the BOTTOM of output")
        (missions / "review.md").write_text("# Updated\n\nscroll to the BOTTOM of output")

        # Create kitty-specs
        (tmp_path / "kitty-specs").mkdir()

        # Create opencode with updated templates (configured - up to date)
        opencode = tmp_path / ".opencode" / "command"
        opencode.mkdir(parents=True)
        (opencode / "spec-kitty.implement.md").write_text("# Updated\n\nscroll to the BOTTOM of output")
        (opencode / "spec-kitty.review.md").write_text("# Updated\n\nscroll to the BOTTOM of output")

        # Create claude with OLD templates (not configured - should be completely ignored)
        claude_dir = tmp_path / ".claude" / "commands"
        claude_dir.mkdir(parents=True)
        (claude_dir / "spec-kitty.implement.md").write_text("# Old template")
        (claude_dir / "spec-kitty.review.md").write_text("# Old template")

        # Detect should only check opencode (configured)
        # Since opencode is up-to-date and claude is not configured, should return False
        # Note: This test might be sensitive to exact template content matching
        # The key behavior is that claude (unconfigured) doesn't trigger detection
        result = migration.detect(tmp_path)

        # If result is True, it's because opencode needs update (not claude)
        # This is acceptable - the important thing is that claude didn't cause detection
        # So we just verify that if we remove claude, the result stays the same
        import shutil

        shutil.rmtree(claude_dir)

        result_without_claude = migration.detect(tmp_path)

        # Results should be the same whether claude exists or not
        # because claude is not configured
        assert result == result_without_claude


class TestAgentDirMapping:
    """Tests for agent directory to key mapping."""

    def test_agent_dir_to_key_complete(self):
        """Verify all agents have key mappings."""
        # All 13 slash-command agents should be mapped (roo removed 2026-05-15,
        # C-007; llxprt added) — command-skill agents use AGENT_SKILL_CONFIG,
        # not AGENT_DIR_TO_KEY.
        assert len(AGENT_DIR_TO_KEY) == 13

        # Verify special mappings
        assert AGENT_DIR_TO_KEY[".github"] == "copilot"
        assert AGENT_DIR_TO_KEY[".augment"] == "auggie"
        assert AGENT_DIR_TO_KEY[".amazonq"] == "q"
        assert AGENT_DIR_TO_KEY[".kiro"] == "kiro"
        assert AGENT_DIR_TO_KEY[".claude"] == "claude"
        assert AGENT_DIR_TO_KEY[".opencode"] == "opencode"
        assert AGENT_DIR_TO_KEY[".llxprt"] == "llxprt"

    def test_all_agent_dirs_have_keys(self):
        """Verify all AGENT_DIRS have corresponding keys."""
        for agent_dir, _ in CompleteLaneMigration.AGENT_DIRS:
            assert agent_dir in AGENT_DIR_TO_KEY, f"{agent_dir} missing from AGENT_DIR_TO_KEY"


class TestLegacyProjectSupport:
    """Tests for legacy project support (pre-agent-config)."""

    def test_legacy_project_without_config_processes_all(self, tmp_path):
        """Legacy projects without config should process all agents."""
        # Create old-style project (no config.yaml)
        kittify = tmp_path / ".kittify"
        kittify.mkdir()

        # Create mission templates (must contain /spec-kitty.implement so migration
        # deploys recognizable content; package command-templates/ removed in FR-010)
        missions = kittify / "missions" / "software-dev" / "command-templates"
        missions.mkdir(parents=True)
        (missions / "implement.md").write_text("/spec-kitty.implement\n\n# Implement\nscroll to the BOTTOM")

        # Create agent directories (all 12)
        for agent_dir, subdir in CompleteLaneMigration.AGENT_DIRS:
            agent_path = tmp_path / agent_dir / subdir
            agent_path.mkdir(parents=True)
            (agent_path / "spec-kitty.implement.md").write_text("# Old")

        # Create kitty-specs
        (tmp_path / "kitty-specs").mkdir()

        migration = ImprovedWorkflowTemplatesMigration()

        # Run migration
        result = migration.apply(tmp_path, dry_run=False)

        assert result.success

        # All agents should be updated (legacy fallback)
        for agent_dir, subdir in CompleteLaneMigration.AGENT_DIRS:
            agent_implement = tmp_path / agent_dir / subdir / "spec-kitty.implement.md"
            if agent_implement.exists():
                content = agent_implement.read_text()
                assert "/spec-kitty.implement" in content


class TestDryRunBehavior:
    """Tests for dry-run mode behavior."""

    def test_dry_run_respects_config(self, mock_project_with_config):
        """Test that dry-run also respects config."""
        migration = ImprovedWorkflowTemplatesMigration()

        # Create old template for opencode
        opencode_implement = mock_project_with_config / ".opencode" / "command" / "spec-kitty.implement.md"
        opencode_implement.write_text("# Old implement")

        # Run dry-run
        result = migration.apply(mock_project_with_config, dry_run=True)

        assert result.success

        # Should mention opencode update
        changes_text = "\n".join(result.changes_made)
        assert "opencode" in changes_text.lower()

        # Should NOT mention other agents
        assert "claude" not in changes_text.lower()
        assert "codex" not in changes_text.lower()

        # File should NOT be modified (dry-run)
        content = opencode_implement.read_text()
        assert content == "# Old implement"
