#!/usr/bin/env python3
"""
Integration tests for the spec-kitty init flow with GitignoreManager.

Tests the complete end-to-end flow of protecting agent directories during init.
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest
from specify_cli import gitignore_manager
from specify_cli.agent_utils.ignore_entries import agent_ignore_entries
from specify_cli.core.config import AI_CHOICES

pytestmark = pytest.mark.git_repo

GitignoreManager = gitignore_manager.GitignoreManager
# Without an agent list every agent's generated files are protected (#6474).
AGENT_DIRS = agent_ignore_entries(Path("/nonexistent"), tuple(AI_CHOICES))
TOTAL_PROTECTED_ENTRIES = len(AGENT_DIRS) + len(gitignore_manager.RUNTIME_PROTECTED_ENTRIES)


def test_init_flow_fresh_project():
    """Test init flow with a fresh project (no .gitignore)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir)

        # Simulate spec-kitty init flow
        manager = GitignoreManager(project_path)
        result = manager.protect_all_agents()

        # Verify success
        assert result.success, "Init flow should succeed"
        assert result.modified, "Should create new .gitignore"
        assert len(result.entries_added) == TOTAL_PROTECTED_ENTRIES, "Should add all protected agent/runtime paths"

        # Verify file exists and has correct content
        gitignore_path = project_path / ".gitignore"
        assert gitignore_path.exists(), ".gitignore should be created"

        content = gitignore_path.read_text()
        assert "# Added by Spec Kitty CLI" in content

        # Verify all agents are protected
        for entry in result.entries_added:
            assert entry in content, f"{entry} should be in .gitignore"

        print("✓ test_init_flow_fresh_project")


def test_init_flow_existing_gitignore():
    """Test init flow with existing .gitignore."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir)
        gitignore_path = project_path / ".gitignore"

        # Create existing .gitignore with some content
        existing_content = """# Existing project gitignore
node_modules/
*.log
.env
dist/
"""
        gitignore_path.write_text(existing_content)

        # Simulate spec-kitty init flow
        manager = GitignoreManager(project_path)
        result = manager.protect_all_agents()

        # Verify success
        assert result.success, "Init flow should succeed"
        assert result.modified, "Should modify existing .gitignore"
        assert len(result.entries_added) == TOTAL_PROTECTED_ENTRIES, "Should add all protected agent/runtime paths"

        # Verify existing content is preserved
        content = gitignore_path.read_text()
        assert "node_modules/" in content
        assert "*.log" in content
        assert ".env" in content
        assert "dist/" in content

        # Verify Spec Kitty's agent files are added, never whole agent folders (#6474)
        lines = content.splitlines()
        assert ".claude/commands/spec-kitty.*" in lines
        assert ".codex/auth.json" in lines
        assert ".claude/" not in lines
        assert ".codex/" not in lines

        print("✓ test_init_flow_existing_gitignore")


def test_init_flow_idempotency():
    """Test that running init multiple times is safe (idempotent)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir)

        # First init
        manager1 = GitignoreManager(project_path)
        result1 = manager1.protect_all_agents()
        assert result1.success
        assert result1.modified
        assert len(result1.entries_added) == TOTAL_PROTECTED_ENTRIES

        # Second init (should do nothing)
        manager2 = GitignoreManager(project_path)
        result2 = manager2.protect_all_agents()
        assert result2.success
        assert not result2.modified, "Should not modify on second run"
        assert len(result2.entries_skipped) == TOTAL_PROTECTED_ENTRIES
        assert len(result2.entries_added) == 0

        # Third init (still should do nothing)
        manager3 = GitignoreManager(project_path)
        result3 = manager3.protect_all_agents()
        assert result3.success
        assert not result3.modified

        # Verify file content hasn't changed
        content = manager3.gitignore_path.read_text()
        # Should have exactly one marker comment
        assert content.count("# Added by Spec Kitty CLI") == 1

        print("✓ test_init_flow_idempotency")


def test_init_flow_partial_existing():
    """Test init flow when some agent directories already exist in .gitignore."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir)
        gitignore_path = project_path / ".gitignore"

        # Create .gitignore with some protected entries and an operator's own agent folder
        existing_content = """# Project gitignore
.codex/auth.json
.kittify/runtime/
.gemini/
node_modules/
"""
        gitignore_path.write_text(existing_content)

        # Simulate spec-kitty init flow
        manager = GitignoreManager(project_path)
        result = manager.protect_all_agents()

        # Verify success
        assert result.success
        assert result.modified, "Should add the missing entries"

        # Check that existing were skipped
        assert ".codex/auth.json" in result.entries_skipped
        assert ".kittify/runtime/" in result.entries_skipped

        expected_new_entries = TOTAL_PROTECTED_ENTRIES - 2
        assert len(result.entries_added) == expected_new_entries
        assert ".cursor/rules/spec-kitty.mdc" in result.entries_added

        # The operator's own line is kept as written, and runtime entries are not duplicated
        lines = gitignore_path.read_text().splitlines()
        assert lines.count(".gemini/") == 1
        assert lines.count(".kittify/runtime/") == 1

        print("✓ test_init_flow_partial_existing")


def test_init_flow_mixed_content():
    """Test init with various types of existing gitignore content."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir)
        gitignore_path = project_path / ".gitignore"

        # Create complex existing .gitignore
        existing_content = """# Python
__pycache__/
*.pyc
*.pyo

# Node
node_modules/
npm-debug.log*

# IDE
.vscode/
.idea/

# Already has one agent dir
.codex/

# Environment
.env
.env.local
"""
        gitignore_path.write_text(existing_content)

        # Simulate spec-kitty init flow
        manager = GitignoreManager(project_path)
        result = manager.protect_all_agents()

        # Verify success
        assert result.success
        assert result.modified

        # Verify content structure
        content = gitignore_path.read_text()

        # Original content should be preserved
        assert "__pycache__/" in content
        assert "node_modules/" in content
        assert ".vscode/" in content

        # Marker should be added
        assert "# Added by Spec Kitty CLI" in content

        # Every agent's generated files should be present
        lines = content.splitlines()
        for entry in AGENT_DIRS:
            assert entry in lines

        print("✓ test_init_flow_mixed_content")


def test_init_flow_readonly_gitignore():
    """Test init flow when .gitignore is read-only."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir)
        gitignore_path = project_path / ".gitignore"

        # Create read-only .gitignore
        gitignore_path.write_text("# Read-only file\n")
        os.chmod(gitignore_path, 0o444)  # Read-only

        try:
            # Simulate spec-kitty init flow
            manager = GitignoreManager(project_path)
            result = manager.protect_all_agents()

            # Should fail gracefully
            assert not result.success, "Should fail with read-only file"
            assert len(result.errors) > 0, "Should have error messages"

            # Check for helpful error message
            error_text = " ".join(result.errors)
            assert "Permission denied" in error_text or "chmod" in error_text

            print("✓ test_init_flow_readonly_gitignore")

        finally:
            # Restore permissions for cleanup
            os.chmod(gitignore_path, 0o644)


def test_init_flow_console_simulation():
    """Simulate the console output that would be shown during init."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir)

        # Simulate spec-kitty init flow
        manager = GitignoreManager(project_path)
        result = manager.protect_all_agents()

        # Simulate console output (what the user would see)
        if result.modified:
            print("\n[Simulated Console Output]")
            print("[cyan]Updated .gitignore to exclude AI agent directories:[/cyan]")
            for entry in result.entries_added:
                print(f"  • {entry}")
            if result.entries_skipped:
                print(f"  ({len(result.entries_skipped)} already protected)")

        # Show warnings (especially for .github/)
        for warning in result.warnings:
            print(f"[yellow]⚠️  {warning}[/yellow]")

        # Verify warning about .github/ is shown

        print("\n✓ test_init_flow_console_simulation")


def run_integration_tests():
    """Run all integration tests."""
    tests = [
        test_init_flow_fresh_project,
        test_init_flow_existing_gitignore,
        test_init_flow_idempotency,
        test_init_flow_partial_existing,
        test_init_flow_mixed_content,
        test_init_flow_readonly_gitignore,
        test_init_flow_console_simulation,
    ]

    print("Running Integration Tests")
    print("=" * 40)

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"✗ {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test.__name__}: Unexpected error: {e}")
            failed += 1

    print("=" * 40)
    print(f"Results: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    success = run_integration_tests()
    sys.exit(0 if success else 1)
