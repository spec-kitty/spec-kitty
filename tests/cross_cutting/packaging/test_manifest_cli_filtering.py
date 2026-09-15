"""Test that CLI commands in frontmatter are not treated as missing scripts.

TDD test to verify the issue described in PR #82:
When command templates have frontmatter like 'ps: spec-kitty agent --json',
the system should NOT treat 'spec-kitty' as a missing script file.

Also validates that FileManifest no longer exposes an ``active_mission``
attribute (feature 054 – state architecture cleanup phase 2, WP02).
"""

import platform
from pathlib import Path

import pytest

from specify_cli.manifest import FileManifest

pytestmark = [pytest.mark.integration]

def test_cli_commands_not_treated_as_scripts(tmp_path: Path):
    """
    GIVEN a command template with 'sh: spec-kitty agent --json' frontmatter
    WHEN _get_referenced_scripts() is called
    THEN 'spec-kitty' should NOT be in the returned scripts list
    """
    # Setup: Create minimal .kittify structure
    kittify_dir = tmp_path / ".kittify"
    missions_dir = kittify_dir / "missions" / "software-dev"
    commands_dir = missions_dir / "command-templates"
    commands_dir.mkdir(parents=True)

    # Create mission.yaml
    (missions_dir / "mission.yaml").write_text("name: software-dev\n")

    # Create a command template with CLI command in frontmatter
    # This is the pattern that was reportedly causing false positives
    command_content = """---
description: Test command that references CLI tools
ps: spec-kitty agent --json
sh: spec-kitty agent --json
---

# Test Command

This command uses spec-kitty CLI.
"""
    (commands_dir / "test-command.md").write_text(command_content)

    # Test: Get referenced scripts — pass mission_type explicitly
    manifest = FileManifest(kittify_dir, mission_type="software-dev")
    scripts = manifest._get_referenced_scripts()

    # Assert: CLI commands should NOT be treated as scripts
    assert "spec-kitty" not in scripts, f"'spec-kitty' should not be in scripts list, got: {scripts}"
    assert len(scripts) == 0, f"No scripts should be detected for CLI commands, got: {scripts}"


def test_actual_kittify_scripts_are_included(tmp_path: Path):
    """
    GIVEN a command template referencing an actual .kittify/scripts/ file
    WHEN _get_referenced_scripts() is called
    THEN the script should be included in the returned list
    """
    # Setup
    kittify_dir = tmp_path / ".kittify"
    missions_dir = kittify_dir / "missions" / "software-dev"
    commands_dir = missions_dir / "command-templates"
    commands_dir.mkdir(parents=True)

    (missions_dir / "mission.yaml").write_text("name: software-dev\n")

    # Create actual script file
    scripts_dir = kittify_dir / "scripts"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "helper.sh").write_text("#!/bin/bash\necho 'test'")
    (scripts_dir / "helper.ps1").write_text("Write-Host 'test'")

    # Create command template referencing actual script
    command_content = """---
description: Test command with actual script
ps: .kittify/scripts/helper.ps1
sh: .kittify/scripts/helper.sh
---

# Test Command
"""
    (commands_dir / "test-command.md").write_text(command_content)

    # Test — pass mission_type explicitly
    manifest = FileManifest(kittify_dir, mission_type="software-dev")
    scripts = manifest._get_referenced_scripts()

    # Assert: Actual scripts SHOULD be included (platform-specific)
    if platform.system() == "Windows":
        assert "scripts/helper.ps1" in scripts
    else:
        assert "scripts/helper.sh" in scripts


def test_noncanonical_kittify_script_paths_are_excluded(tmp_path: Path):
    """Only files below the canonical scripts directory may enter the manifest."""
    kittify_dir = tmp_path / ".kittify"
    missions_dir = kittify_dir / "missions" / "software-dev"
    commands_dir = missions_dir / "command-templates"
    commands_dir.mkdir(parents=True)
    (missions_dir / "mission.yaml").write_text("name: software-dev\n")

    command_content = """---
description: Paths outside scripts must not be accepted
sh: .kittify/scripts/../templates/injected.sh
---
# Invalid script reference
"""
    (commands_dir / "invalid-script-path.md").write_text(command_content)

    manifest = FileManifest(kittify_dir, mission_type="software-dev")

    assert manifest._get_referenced_scripts() == []


def test_other_system_commands_filtered(tmp_path: Path):
    """
    GIVEN command templates with various system CLI commands
    WHEN _get_referenced_scripts() is called
    THEN none of them should be treated as scripts
    """
    kittify_dir = tmp_path / ".kittify"
    missions_dir = kittify_dir / "missions" / "software-dev"
    commands_dir = missions_dir / "command-templates"
    commands_dir.mkdir(parents=True)

    (missions_dir / "mission.yaml").write_text("name: software-dev\n")

    # Test various CLI commands that might appear in frontmatter
    command_content = """---
description: Test with git command
sh: git status
ps: git status
---
# Git command
"""
    (commands_dir / "git-cmd.md").write_text(command_content)

    command_content2 = """---
description: Test with python command
sh: python3 -c "print('test')"
ps: python -c "print('test')"
---
# Python command
"""
    (commands_dir / "python-cmd.md").write_text(command_content2)

    manifest = FileManifest(kittify_dir, mission_type="software-dev")
    scripts = manifest._get_referenced_scripts()

    assert "git" not in scripts
    assert "python" not in scripts
    assert "python3" not in scripts
    assert len(scripts) == 0


# --------------------------------------------------------------------------- #
# WP02 – Active-mission fallback removal tests
# --------------------------------------------------------------------------- #

def test_manifest_no_active_mission_attribute(tmp_path: Path):
    """FileManifest must not expose an ``active_mission`` attribute."""
    kittify_dir = tmp_path / ".kittify"
    kittify_dir.mkdir()

    manifest = FileManifest(kittify_dir)
    assert not hasattr(manifest, "active_mission"), (
        "FileManifest should no longer have an active_mission attribute"
    )


def test_manifest_without_mission_type_has_no_mission_dir(tmp_path: Path):
    """When no mission_type is provided, mission_dir should be None."""
    kittify_dir = tmp_path / ".kittify"
    kittify_dir.mkdir()

    manifest = FileManifest(kittify_dir)
    assert manifest.mission_dir is None


def test_manifest_with_explicit_mission_type(tmp_path: Path):
    """When mission_type is provided, mission_dir should point to that mission."""
    kittify_dir = tmp_path / ".kittify"
    kittify_dir.mkdir()

    manifest = FileManifest(kittify_dir, mission_type="research")
    assert manifest.mission_dir == kittify_dir / "missions" / "research"
