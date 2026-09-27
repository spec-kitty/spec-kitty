"""Integration tests for hybrid init: full prompts + thin shims.

WP03: Verify that after init, prompt-driven commands get full prompt files
(100+ lines) and CLI-driven commands get thin shim files (<5 lines).

Subtasks: T012, T013, T014, T015
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.fast


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fake_global_runtime(global_home: Path) -> None:
    """Create a minimal global runtime structure for testing.

    Mimics what ensure_runtime() produces at ~/.kittify/.
    Includes command-templates/ so the 4-tier resolver can find them.
    """
    for mission in ("software-dev", "research"):
        mission_yaml = global_home / "missions" / mission / "mission.yaml"
        mission_yaml.parent.mkdir(parents=True, exist_ok=True)
        mission_yaml.write_text(f"name: {mission}\n")

    cache = global_home / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "version.lock").write_text("0.99.0")


def _make_package_asset_root_with_templates(pkg_root: Path) -> Path:
    """Create a fake package mission root with 9 command-template files.

    Returns the missions directory path (suitable for SPEC_KITTY_TEMPLATE_ROOT).
    Command templates are multi-line realistic files (>10 lines each).
    """
    cmd_templates = pkg_root / "software-dev" / "command-templates"
    cmd_templates.mkdir(parents=True, exist_ok=True)

    # Create 9 realistic multi-line prompt-driven command templates.
    # Each file must have frontmatter-compatible content (no scripts: block).
    prompt_commands = [
        "specify",
        "plan",
        "tasks",
        "tasks-outline",
        "tasks-packages",
        "checklist",
        "analyze",
        "research",
        "charter",
    ]

    for cmd in prompt_commands:
        lines = [f"# Spec Kitty — {cmd}"]
        lines.append("")
        lines.append("You are a senior software architect.")
        lines.append("Follow these steps to complete the task.")
        lines.append("")
        for i in range(1, 20):
            lines.append(f"## Step {i}: Do important thing {i}")
            lines.append("")
            lines.append(f"Perform detailed analysis for step {i}.")
            lines.append(f"Consider edge cases in step {i}.")
            lines.append("")
        lines.append("---END---")
        content = "\n".join(lines)
        # Must have > 100 lines for the integration assertion
        assert len(content.splitlines()) >= 100, f"Test template for {cmd} must have >=100 lines, got {len(content.splitlines())}"
        (cmd_templates / f"{cmd}.md").write_text(content, encoding="utf-8")

    return pkg_root


# ---------------------------------------------------------------------------
# T013: _resolve_mission_command_templates_dir was removed in feature 076.
# The 4-tier resolution class (TestResolveMissionCommandTemplatesDir) is deleted.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# T015: Integration test — hybrid install produces correct file types
# ---------------------------------------------------------------------------


class TestHybridInstallOutputShape:
    """Verify generate_agent_assets + generate_all_shims produces the hybrid layout."""

    def test_generate_agent_assets_produces_full_prompts(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """generate_agent_assets() writes 9 multi-line files for a single agent."""
        pkg_root = tmp_path / "pkg"
        _make_package_asset_root_with_templates(pkg_root)
        monkeypatch.setenv("SPEC_KITTY_TEMPLATE_ROOT", str(pkg_root))

        project = tmp_path / "project"
        project.mkdir()

        cmd_templates_dir = pkg_root / "software-dev" / "command-templates"

        from specify_cli.template.asset_generator import generate_agent_assets

        generate_agent_assets(
            command_templates_dir=cmd_templates_dir,
            project_path=project,
            agent_key="claude",
            script_type="sh",
        )

        claude_dir = project / ".claude" / "commands"
        assert claude_dir.is_dir()
        files = list(claude_dir.glob("spec-kitty.*.md"))
        assert len(files) == 9, f"Expected 9 prompt files, got {len(files)}: {[f.name for f in files]}"

        # Each file should be full-length (>=100 lines)
        for f in files:
            lines = f.read_text().splitlines()
            assert len(lines) >= 100, f"{f.name} has only {len(lines)} lines (expected >=100)"

    def test_generate_all_shims_produces_thin_cli_shims(self, tmp_path: Path) -> None:
        """generate_all_shims() writes 7 thin shim files per agent."""
        from specify_cli.core.agent_config import AgentConfig, save_agent_config
        from specify_cli.shims.generator import generate_all_shims

        project = tmp_path / "project"
        project.mkdir()
        (project / ".kittify").mkdir()

        # Configure only claude agent
        save_agent_config(project, AgentConfig(available=["claude"]))

        generate_all_shims(project)

        claude_dir = project / ".claude" / "commands"
        shim_files = list(claude_dir.glob("spec-kitty.*.md"))
        assert len(shim_files) == 7, f"Expected 7 shim files, got {len(shim_files)}: {[f.name for f in shim_files]}"

        for f in shim_files:
            lines = f.read_text().splitlines()
            assert len(lines) < 10, f"{f.name} is too long for a shim: {len(lines)} lines"

    def test_hybrid_layout_full_prompts_plus_cli_shims(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """After generate_agent_assets() + generate_all_shims(), directory has 16 files.

        Layout:
        - 9 full prompt files (prompt-driven commands, >=100 lines each)
        - 7 thin shim files (CLI-driven commands, <10 lines each)
        = 16 total files
        """
        pkg_root = tmp_path / "pkg"
        _make_package_asset_root_with_templates(pkg_root)
        monkeypatch.setenv("SPEC_KITTY_TEMPLATE_ROOT", str(pkg_root))

        project = tmp_path / "project"
        project.mkdir()
        (project / ".kittify").mkdir()

        from specify_cli.core.agent_config import AgentConfig, save_agent_config
        from specify_cli.shims.generator import generate_all_shims
        from specify_cli.shims.registry import PROMPT_DRIVEN_COMMANDS, CLI_DRIVEN_COMMANDS
        from specify_cli.template.asset_generator import generate_agent_assets

        # Save agent config with claude only
        save_agent_config(project, AgentConfig(available=["claude"]))

        cmd_templates_dir = pkg_root / "software-dev" / "command-templates"

        # Step 1: generate full prompts (clears and fills the agent dir)
        generate_agent_assets(
            command_templates_dir=cmd_templates_dir,
            project_path=project,
            agent_key="claude",
            script_type="sh",
        )

        # Step 2: add thin shims (does NOT clear, just overwrites individual files)
        generate_all_shims(project)

        claude_dir = project / ".claude" / "commands"
        all_files = {f.stem.removeprefix("spec-kitty."): f for f in claude_dir.glob("spec-kitty.*.md")}

        assert len(all_files) == 16, f"Expected 16 files total, got {len(all_files)}: {sorted(all_files.keys())}"

        # Prompt-driven commands: full prompts (>=100 lines)
        for cmd in PROMPT_DRIVEN_COMMANDS:
            assert cmd in all_files, f"Missing prompt-driven command: {cmd}"
            lines = all_files[cmd].read_text().splitlines()
            assert len(lines) >= 100, f"spec-kitty.{cmd}.md should have >=100 lines (full prompt), got {len(lines)}"

        # CLI-driven commands: thin shims (<10 lines)
        for cmd in CLI_DRIVEN_COMMANDS:
            assert cmd in all_files, f"Missing CLI-driven command: {cmd}"
            lines = all_files[cmd].read_text().splitlines()
            assert len(lines) < 10, f"spec-kitty.{cmd}.md should have <10 lines (thin shim), got {len(lines)}"

    def test_specify_md_has_100_plus_lines(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """spec-kitty.specify.md must be a full prompt (>=100 lines)."""
        pkg_root = tmp_path / "pkg"
        _make_package_asset_root_with_templates(pkg_root)
        monkeypatch.setenv("SPEC_KITTY_TEMPLATE_ROOT", str(pkg_root))

        project = tmp_path / "project"
        project.mkdir()
        (project / ".kittify").mkdir()

        from specify_cli.core.agent_config import AgentConfig, save_agent_config
        from specify_cli.shims.generator import generate_all_shims
        from specify_cli.template.asset_generator import generate_agent_assets

        save_agent_config(project, AgentConfig(available=["claude"]))
        cmd_templates_dir = pkg_root / "software-dev" / "command-templates"

        generate_agent_assets(
            command_templates_dir=cmd_templates_dir,
            project_path=project,
            agent_key="claude",
            script_type="sh",
        )
        generate_all_shims(project)

        specify_file = project / ".claude" / "commands" / "spec-kitty.specify.md"
        assert specify_file.exists(), "spec-kitty.specify.md must exist"
        lines = specify_file.read_text().splitlines()
        assert len(lines) >= 100, f"spec-kitty.specify.md should have >=100 lines, got {len(lines)}"

    def test_implement_md_is_thin_shim(self, tmp_path: Path) -> None:
        """spec-kitty.implement.md must be a thin shim (<=10 lines).

        The threshold accommodates the YAML frontmatter (``---``,
        ``description: ...``, ``---``) that the shim now emits so the
        slash-command picker UI has a real description to display.
        """
        from specify_cli.core.agent_config import AgentConfig, save_agent_config
        from specify_cli.shims.generator import generate_all_shims

        project = tmp_path / "project"
        project.mkdir()
        (project / ".kittify").mkdir()
        save_agent_config(project, AgentConfig(available=["claude"]))

        generate_all_shims(project)

        implement_file = project / ".claude" / "commands" / "spec-kitty.implement.md"
        assert implement_file.exists(), "spec-kitty.implement.md must exist"
        content = implement_file.read_text()
        lines = content.splitlines()
        assert len(lines) <= 10, f"spec-kitty.implement.md should be a thin shim (<=10 lines), got {len(lines)}"
        # The frontmatter must be on line 1 so Claude Code's picker can read it.
        assert lines[0] == "---"
        assert lines[1].startswith("description:")
        assert lines[2] == "---"


# ---------------------------------------------------------------------------
# T014: ensure_runtime() deploys command-templates to ~/.kittify/
# ---------------------------------------------------------------------------


class TestEnsureRuntimeDeploysCommandTemplates:
    """Verify ensure_runtime() copies command-templates/ to ~/.kittify/missions/."""

    def test_populate_from_package_copies_command_templates(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """populate_from_package() includes command-templates/ in the missions copy.

        ensure_runtime() is already handles command-templates/ via recursive
        shutil.copytree of the missions/ directory — no explicit glob needed.
        This test verifies that assumption holds.
        """
        pkg_root = tmp_path / "pkg"
        _make_package_asset_root_with_templates(pkg_root)
        monkeypatch.setenv("SPEC_KITTY_TEMPLATE_ROOT", str(pkg_root))

        target = tmp_path / "runtime"

        from specify_cli.runtime.bootstrap import populate_from_package

        populate_from_package(target)

        deployed_cmd_tmpl = target / "missions" / "software-dev" / "command-templates"
        assert deployed_cmd_tmpl.is_dir(), "populate_from_package() must copy command-templates/ to the runtime directory"

        deployed_files = list(deployed_cmd_tmpl.glob("*.md"))
        assert len(deployed_files) == 9, f"Expected 9 command-template files deployed, got {len(deployed_files)}: {[f.name for f in deployed_files]}"
