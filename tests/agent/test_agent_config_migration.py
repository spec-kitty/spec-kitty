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

from specify_cli.agent_utils.directories import AGENT_DIRS
from specify_cli.core.agent_config import AgentConfig, AgentConfigError, save_agent_config
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

    def test_missing_config_returns_only_agents_present_on_disk(self, tmp_path, caplog):
        """No config.yaml is a legacy project: only the present agents (#6501)."""
        kittify = tmp_path / ".kittify"
        kittify.mkdir()
        (tmp_path / ".claude" / "commands").mkdir(parents=True)

        with caplog.at_level("WARNING"):
            agent_dirs = get_agent_dirs_for_project(tmp_path)

        assert agent_dirs == [(".claude", "commands")]
        # And the warning names the file, the key and the remedy instead of
        # silently reading "no list" as "every agent".
        assert ".kittify/config.yaml" in caplog.text
        assert "agents.available" in caplog.text
        assert "spec-kitty agent config" in caplog.text

    def test_legacy_warning_is_emitted_once_per_process_per_project(self, tmp_path, caplog, monkeypatch):
        """The upgrade chain reads this ~27 times; one line is enough (#6501, NFR-002)."""
        from specify_cli.agent_utils import directories

        monkeypatch.setattr(directories, "_LEGACY_PROJECTS_WARNED", set())
        (tmp_path / ".kittify").mkdir()
        (tmp_path / ".claude").mkdir()

        with caplog.at_level("WARNING"):
            for _ in range(3):
                get_agent_dirs_for_project(tmp_path)

        warnings = [record for record in caplog.records if "has no agents.available list" in record.getMessage()]
        assert len(warnings) == 1

    def test_missing_config_follows_the_agents_actually_present(self, tmp_path):
        """The observed set is read from disk, not a constant (#6501)."""
        (tmp_path / ".kittify").mkdir()
        (tmp_path / ".claude" / "commands").mkdir(parents=True)
        (tmp_path / ".cursor" / "commands").mkdir(parents=True)

        agent_dirs = get_agent_dirs_for_project(tmp_path)

        assert (".claude", "commands") in agent_dirs
        assert (".cursor", "commands") in agent_dirs
        assert len(agent_dirs) == 2

    def test_missing_config_with_no_agent_dirs_returns_nothing(self, tmp_path):
        """A project with no agent surface gets no agents, never the registry (#6501)."""
        (tmp_path / ".kittify").mkdir()
        (tmp_path / "kitty-specs").mkdir()

        assert get_agent_dirs_for_project(tmp_path) == []

    def test_ci_github_dir_is_not_a_copilot_surface(self, tmp_path):
        """A CI-only .github/ is not a Copilot surface; .github/prompts is (#6501)."""
        (tmp_path / ".kittify").mkdir()
        (tmp_path / ".github" / "workflows").mkdir(parents=True)

        assert get_agent_dirs_for_project(tmp_path) == []

        (tmp_path / ".github" / "prompts").mkdir()
        assert get_agent_dirs_for_project(tmp_path) == [(".github", "prompts")]

    def test_agent_root_without_its_managed_subdir_is_still_in_use(self, tmp_path):
        """A pre-3.1.2 layout keeps its agent dir and no commands/ yet (#6501).

        The agent-specific project dir is the evidence, so command files that
        still need repairing are not skipped just because the managed subdir is
        absent; only ``.github`` needs its ``prompts/`` surface (above).
        """
        (tmp_path / ".kittify").mkdir()
        (tmp_path / ".gemini").mkdir()

        assert get_agent_dirs_for_project(tmp_path) == [(".gemini", "commands")]

    def test_explicit_empty_list_means_no_agents(self, tmp_path):
        """An explicit ``available: []`` means no CLI-managed agents (#6494)."""
        kittify = tmp_path / ".kittify"
        kittify.mkdir()

        config = AgentConfig(available=[])
        save_agent_config(tmp_path, config)

        assert get_agent_dirs_for_project(tmp_path) == []

    def test_agents_section_without_available_key_uses_present_agents(self, tmp_path):
        """A section without ``available`` is the legacy case #6501 owns."""
        kittify = tmp_path / ".kittify"
        kittify.mkdir()
        (kittify / "config.yaml").write_text("agents:\n  auto_commit: true\n", encoding="utf-8")
        (tmp_path / ".gemini" / "commands").mkdir(parents=True)

        assert get_agent_dirs_for_project(tmp_path) == [(".gemini", "commands")]

    def test_config_without_agents_section_uses_present_agents(self, tmp_path):
        """A config with no agents section is the same legacy shape (#6501)."""
        kittify = tmp_path / ".kittify"
        kittify.mkdir()
        (kittify / "config.yaml").write_text("vcs:\n  type: git\n", encoding="utf-8")
        (tmp_path / ".opencode" / "command").mkdir(parents=True)

        assert get_agent_dirs_for_project(tmp_path) == [(".opencode", "command")]

    def test_unreadable_config_fails_closed_with_remedy(self, tmp_path):
        """A corrupt config never widens to every agent (#6494)."""
        kittify = tmp_path / ".kittify"
        kittify.mkdir()
        (kittify / "config.yaml").write_text("agents: [unclosed\n", encoding="utf-8")

        with pytest.raises(AgentConfigError, match="spec-kitty agent config list"):
            get_agent_dirs_for_project(tmp_path)


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
        # Cross-registry relation, not a re-pinned count: AGENT_DIR_TO_KEY's
        # key set must exactly match the canonical AGENT_DIRS directory set
        # (the slash-command dirs of `specify_cli.agent_utils.directories`
        # are the authority — command-skill agents use AGENT_SKILL_CONFIG,
        # not AGENT_DIR_TO_KEY). A legitimate new agent, added consistently to
        # both registries, needs 0 edits here (NFR-003).
        assert set(AGENT_DIR_TO_KEY) == {agent_dir for agent_dir, _subdir in AGENT_DIRS}

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

    def test_legacy_project_without_config_repairs_only_the_present_agents(self, tmp_path):
        """A legacy project gets the agents it has, and no others (#6501)."""
        # Create old-style project (no config.yaml)
        kittify = tmp_path / ".kittify"
        kittify.mkdir()

        # Create mission templates (must contain /spec-kitty.implement so migration
        # deploys recognizable content; package command-templates/ removed in FR-010)
        missions = kittify / "missions" / "software-dev" / "command-templates"
        missions.mkdir(parents=True)
        (missions / "implement.md").write_text("/spec-kitty.implement\n\n# Implement\nscroll to the BOTTOM")

        # Two of the twelve agent directories exist; the other ten must stay absent.
        present = [(".claude", "commands"), (".opencode", "command")]
        for agent_dir, subdir in present:
            agent_path = tmp_path / agent_dir / subdir
            agent_path.mkdir(parents=True)
            (agent_path / "spec-kitty.implement.md").write_text("# Old")

        # Create kitty-specs
        (tmp_path / "kitty-specs").mkdir()

        migration = ImprovedWorkflowTemplatesMigration()

        # Run migration
        result = migration.apply(tmp_path, dry_run=False)

        assert result.success

        for agent_dir, subdir in present:
            content = (tmp_path / agent_dir / subdir / "spec-kitty.implement.md").read_text()
            assert "/spec-kitty.implement" in content
        absent = [pair for pair in CompleteLaneMigration.AGENT_DIRS if pair not in present]
        for agent_dir, _subdir in absent:
            assert not (tmp_path / agent_dir).exists(), f"{agent_dir} was created for an agent the project does not have"


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
