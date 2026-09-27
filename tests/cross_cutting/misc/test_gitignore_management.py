#!/usr/bin/env python3
"""
Test cases for the gitignore management functionality using GitignoreManager.

Updated to use the new GitignoreManager class instead of the old functions.
"""

import sys
import tempfile
from pathlib import Path

import pytest
from specify_cli import gitignore_manager

pytestmark = [pytest.mark.integration]

GitignoreManager = gitignore_manager.GitignoreManager
ProtectionResult = gitignore_manager.ProtectionResult

# Total entries: agents + runtime (derived from state contract)
_TOTAL_ENTRIES = len(gitignore_manager.AGENT_DIRECTORIES) + len(gitignore_manager.RUNTIME_PROTECTED_ENTRIES)
_AGENT_DIRS = [agent.directory for agent in gitignore_manager.AGENT_DIRECTORIES]


def test_gitignore_manager_creates_new_file():
    """Test that GitignoreManager creates a new .gitignore file with entries."""
    with tempfile.TemporaryDirectory() as temp_dir:
        project_path = Path(temp_dir)

        # Use GitignoreManager
        manager = GitignoreManager(project_path)
        result = manager.ensure_entries([".codex/"])

        # Check that it returned True (file was modified)
        assert result

        # Check that .gitignore file was created
        gitignore_path = project_path / ".gitignore"
        assert gitignore_path.exists()

        # Check the content
        content = gitignore_path.read_text()
        assert "# Added by Spec Kitty CLI (auto-managed)" in content
        assert ".codex/" in content


def test_gitignore_manager_adds_to_existing_file():
    """Test that GitignoreManager adds entries to existing .gitignore file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        project_path = Path(temp_dir)
        gitignore_path = project_path / ".gitignore"

        # Create an existing .gitignore file
        existing_content = "node_modules/\n*.log\n"
        gitignore_path.write_text(existing_content)

        # Use GitignoreManager
        manager = GitignoreManager(project_path)
        result = manager.ensure_entries([".codex/"])

        # Check that it returned True (file was modified)
        assert result

        # Check the content
        content = gitignore_path.read_text()
        assert existing_content.strip() in content
        assert "# Added by Spec Kitty CLI (auto-managed)" in content
        assert ".codex/" in content


def test_gitignore_manager_skips_existing_entries():
    """Test that GitignoreManager doesn't duplicate existing entries."""
    with tempfile.TemporaryDirectory() as temp_dir:
        project_path = Path(temp_dir)
        gitignore_path = project_path / ".gitignore"

        # Create an existing .gitignore file with .codex/ already present
        existing_content = "node_modules/\n*.log\n.codex/\n"
        gitignore_path.write_text(existing_content)

        # Use GitignoreManager
        manager = GitignoreManager(project_path)
        result = manager.ensure_entries([".codex/"])

        # Check that it returned False (file was not modified)
        assert not result

        # Check that content is unchanged
        content = gitignore_path.read_text()
        assert content == existing_content


def test_gitignore_manager_handles_multiple_entries():
    """Test that GitignoreManager handles multiple entries correctly."""
    with tempfile.TemporaryDirectory() as temp_dir:
        project_path = Path(temp_dir)
        gitignore_path = project_path / ".gitignore"

        # Create an existing .gitignore file
        existing_content = "node_modules/\n*.log\n"
        gitignore_path.write_text(existing_content)

        entries = [".codex/", ".env", "secrets.txt"]

        # Use GitignoreManager
        manager = GitignoreManager(project_path)
        result = manager.ensure_entries(entries)

        # Check that it returned True (file was modified)
        assert result

        # Check the content
        content = gitignore_path.read_text()
        assert existing_content.strip() in content
        assert "# Added by Spec Kitty CLI (auto-managed)" in content
        assert ".codex/" in content
        assert ".env" in content
        assert "secrets.txt" in content


def test_protect_all_agents_adds_all_directories():
    """Test that protect_all_agents adds all 13 agent directories."""
    with tempfile.TemporaryDirectory() as temp_dir:
        project_path = Path(temp_dir)

        # Use GitignoreManager
        manager = GitignoreManager(project_path)
        result = manager.protect_all_agents()

        # Check success
        assert result.success
        assert result.modified

        # Check that all entries were added (agents + contract-derived runtime paths)
        assert len(result.entries_added) == _TOTAL_ENTRIES

        # Check that .gitignore was updated
        gitignore_path = project_path / ".gitignore"
        assert gitignore_path.exists()
        content = gitignore_path.read_text()

        # Verify all expected directories are present
        for dir_name in _AGENT_DIRS:
            assert dir_name in content
        assert ".kittify/.dashboard" in content
        assert ".kittify/missions/__pycache__/" in content


def test_protect_all_agents_with_existing_directory():
    """Test that protect_all_agents skips existing entries."""
    with tempfile.TemporaryDirectory() as temp_dir:
        project_path = Path(temp_dir)
        gitignore_path = project_path / ".gitignore"

        # Create .gitignore with some agent directories already present
        existing_content = ".codex/\n.claude/\n"
        gitignore_path.write_text(existing_content)

        # Use GitignoreManager
        manager = GitignoreManager(project_path)
        result = manager.protect_all_agents()

        # Check success
        assert result.success
        assert result.modified  # Should still be modified (adding other 11)

        # Check that existing entries were skipped
        assert ".codex/" in result.entries_skipped
        assert ".claude/" in result.entries_skipped

        # Check that new entries were added (total - 2 existing)
        assert len(result.entries_added) == _TOTAL_ENTRIES - 2


def test_protect_selected_agents():
    """Test that protect_selected_agents only adds specified agents."""
    with tempfile.TemporaryDirectory() as temp_dir:
        project_path = Path(temp_dir)

        # Use GitignoreManager
        manager = GitignoreManager(project_path)
        result = manager.protect_selected_agents(["codex", "claude", "gemini"])

        # Check success
        assert result.success
        assert result.modified

        # Check that only selected agents were added
        assert len(result.entries_added) == 3
        assert ".codex/" in result.entries_added
        assert ".claude/" in result.entries_added
        assert ".gemini/" in result.entries_added

        # Verify in file
        content = manager.gitignore_path.read_text()
        assert ".codex/" in content
        assert ".claude/" in content
        assert ".gemini/" in content
        assert ".cursor/" not in content  # Not selected


def test_protect_selected_agents_cursor_is_narrow():
    """#2498: selecting cursor must not blanket-ignore .cursor/, only the
    paths Spec Kitty itself generates there."""
    with tempfile.TemporaryDirectory() as temp_dir:
        project_path = Path(temp_dir)

        manager = GitignoreManager(project_path)
        result = manager.protect_selected_agents(["cursor"])

        assert result.success
        assert result.modified

        content = manager.gitignore_path.read_text()
        assert ".cursor/rules/spec-kitty.mdc" in content
        assert ".cursor/commands/" in content
        assert ".cursor/skills/" in content

        # No line blocks the whole .cursor/ directory.
        blanket_lines = [line for line in content.splitlines() if line.strip() in (".cursor", ".cursor/")]
        assert blanket_lines == []


def test_protect_selected_agents_with_unknown():
    """Test that protect_selected_agents handles unknown agent names."""
    with tempfile.TemporaryDirectory() as temp_dir:
        project_path = Path(temp_dir)

        # Use GitignoreManager
        manager = GitignoreManager(project_path)
        result = manager.protect_selected_agents(["codex", "unknown_agent"])

        # Check success
        assert result.success
        assert result.modified

        # Check that valid agent was added
        assert ".codex/" in result.entries_added

        # Check for warning about unknown agent
        assert any("unknown_agent" in w for w in result.warnings)


# Run tests if executed directly
if __name__ == "__main__":
    tests = [
        test_gitignore_manager_creates_new_file,
        test_gitignore_manager_adds_to_existing_file,
        test_gitignore_manager_skips_existing_entries,
        test_gitignore_manager_handles_multiple_entries,
        test_protect_all_agents_adds_all_directories,
        test_protect_all_agents_with_existing_directory,
        test_protect_selected_agents,
        test_protect_selected_agents_cursor_is_narrow,
        test_protect_selected_agents_with_unknown,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            print(f"✓ {test.__name__}")
            passed += 1
        except Exception as e:
            print(f"✗ {test.__name__}: {e}")
            failed += 1

    print(f"\nResults: {passed} passed, {failed} failed")
    if failed > 0:
        sys.exit(1)
