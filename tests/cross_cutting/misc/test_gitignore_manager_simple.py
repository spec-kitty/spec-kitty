#!/usr/bin/env python3
"""
Simple tests for GitignoreManager that can run without pytest.
"""

import sys
import tempfile
from pathlib import Path

import pytest
from specify_cli import gitignore_manager

pytestmark = [pytest.mark.integration]

GitignoreManager = gitignore_manager.GitignoreManager
ProtectionResult = gitignore_manager.ProtectionResult
TOTAL_PROTECTED_ENTRIES = len(gitignore_manager.AGENT_DIRECTORIES) + len(gitignore_manager.RUNTIME_PROTECTED_ENTRIES)
AGENT_DIRS = [agent.directory for agent in gitignore_manager.AGENT_DIRECTORIES]


def run_tests():
    """Run all tests and report results."""
    passed = 0
    failed = 0

    tests = [
        test_basic_functionality,
        test_all_agents_protected,
        test_duplicate_detection,
        test_error_handling,
    ]

    for test in tests:
        try:
            test()
            print(f"✓ {test.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"✗ {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test.__name__}: Unexpected error: {e}")
            failed += 1

    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0


def test_basic_functionality():
    """Test basic GitignoreManager functionality."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # Test initialization
        manager = GitignoreManager(tmppath)
        assert manager.project_path == tmppath, "Project path not set correctly"
        assert manager.gitignore_path == tmppath / ".gitignore", ".gitignore path not set"

        # Test protect_all_agents
        result = manager.protect_all_agents()
        assert result.success, "protect_all_agents failed"
        assert result.modified, "File should be modified on first run"
        assert len(result.entries_added) == TOTAL_PROTECTED_ENTRIES, f"Expected {TOTAL_PROTECTED_ENTRIES} entries, got {len(result.entries_added)}"

        # Verify file created
        assert manager.gitignore_path.exists(), ".gitignore not created"


def test_all_agents_protected():
    """Test that all 13 agent directories are protected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        manager = GitignoreManager(tmppath)

        manager.protect_all_agents()

        content = manager.gitignore_path.read_text()
        for dir_name in AGENT_DIRS:
            assert dir_name in content, f"{dir_name} not found in .gitignore"

        # Check for marker
        assert "# Added by Spec Kitty CLI" in content, "Marker comment not found"


def test_duplicate_detection():
    """Test that duplicates are not created."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        manager = GitignoreManager(tmppath)

        # First run
        result1 = manager.protect_all_agents()
        assert result1.modified, "First run should modify file"
        assert len(result1.entries_added) == TOTAL_PROTECTED_ENTRIES, f"Should add {TOTAL_PROTECTED_ENTRIES} entries"

        # Second run
        result2 = manager.protect_all_agents()
        assert not result2.modified, "Second run should not modify file"
        assert len(result2.entries_skipped) == TOTAL_PROTECTED_ENTRIES, f"Should skip {TOTAL_PROTECTED_ENTRIES} entries"
        assert len(result2.entries_added) == 0, "Should add 0 new entries"


def test_error_handling():
    """Test error handling for invalid inputs."""
    # Test with non-existent directory
    try:
        GitignoreManager(Path("/nonexistent/path"))
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "does not exist" in str(e), "Wrong error message"

    # Test with file instead of directory
    with tempfile.NamedTemporaryFile() as tmpfile:
        try:
            GitignoreManager(Path(tmpfile.name))
            raise AssertionError("Should have raised ValueError")
        except ValueError as e:
            assert "not a directory" in str(e), "Wrong error message"


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
