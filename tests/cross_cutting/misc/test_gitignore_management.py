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
from specify_cli.agent_utils.ignore_entries import agent_ignore_entries
from specify_cli.core.config import AI_CHOICES

pytestmark = [pytest.mark.integration]

GitignoreManager = gitignore_manager.GitignoreManager
ProtectionResult = gitignore_manager.ProtectionResult

# Total entries: the agent-files block (every agent when no list is configured,
# #6474) + runtime entries (derived from state contract)
_AGENT_DIRS = agent_ignore_entries(Path("/nonexistent"), tuple(AI_CHOICES))
_TOTAL_ENTRIES = len(_AGENT_DIRS) + len(gitignore_manager.RUNTIME_PROTECTED_ENTRIES)


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
    """Without an agent list, protect_all_agents lists every agent's generated files."""
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

        # Verify all expected entries are present, as whole lines
        lines = content.splitlines()
        for entry in _AGENT_DIRS:
            assert entry in lines
        assert ".kittify/missions/__pycache__/" in content


def test_protect_all_agents_with_existing_directory():
    """Test that protect_all_agents skips existing entries."""
    with tempfile.TemporaryDirectory() as temp_dir:
        project_path = Path(temp_dir)
        gitignore_path = project_path / ".gitignore"

        # Create .gitignore with some protected entries already present
        existing_content = ".codex/auth.json\n.kittify/runtime/\n"
        gitignore_path.write_text(existing_content)

        # Use GitignoreManager
        manager = GitignoreManager(project_path)
        result = manager.protect_all_agents()

        # Check success
        assert result.success
        assert result.modified  # Should still be modified (adding the others)

        # Check that existing entries were skipped
        assert ".codex/auth.json" in result.entries_skipped
        assert ".kittify/runtime/" in result.entries_skipped

        # Check that new entries were added (total - 2 existing)
        assert len(result.entries_added) == _TOTAL_ENTRIES - 2


def test_protect_all_agents_cursor_is_narrow():
    """#2498: protecting cursor must not blanket-ignore .cursor/, only the
    paths Spec Kitty itself generates there."""
    with tempfile.TemporaryDirectory() as temp_dir:
        project_path = Path(temp_dir)

        manager = GitignoreManager(project_path)
        result = manager.protect_all_agents()

        assert result.success
        assert result.modified

        content = manager.gitignore_path.read_text()
        assert ".cursor/rules/spec-kitty.mdc" in content
        assert ".cursor/commands/spec-kitty.*" in content  # only Spec Kitty's files (#6474)

        # No line blocks the whole .cursor/ directory.
        blanket_lines = [line for line in content.splitlines() if line.strip() in (".cursor", ".cursor/")]
        assert blanket_lines == []


# Run tests if executed directly
if __name__ == "__main__":
    tests = [
        test_gitignore_manager_creates_new_file,
        test_gitignore_manager_adds_to_existing_file,
        test_gitignore_manager_skips_existing_entries,
        test_gitignore_manager_handles_multiple_entries,
        test_protect_all_agents_adds_all_directories,
        test_protect_all_agents_with_existing_directory,
        test_protect_all_agents_cursor_is_narrow,
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
