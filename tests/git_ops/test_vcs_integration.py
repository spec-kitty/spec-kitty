"""Scope: git_repo integration tests for VCS abstraction layer — git backend."""

import subprocess

import pytest

from specify_cli.core.vcs import (
    GIT_CAPABILITIES,
    VCSBackend,
    get_vcs,
)
from specify_cli.core.vcs import detection

pytestmark = pytest.mark.git_repo


@pytest.fixture(autouse=True)
def clear_detection_cache():
    """Clear detection caches before each test."""
    detection.is_git_available.cache_clear()
    yield
    # Clear again after test
    detection.is_git_available.cache_clear()


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def git_repo(tmp_path):
    """Create a minimal git repository for testing."""
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=tmp_path,
        capture_output=True,
    )

    # Create initial commit
    test_file = tmp_path / "README.md"
    test_file.write_text("# Test Repo\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=tmp_path,
        capture_output=True,
    )

    return tmp_path


@pytest.fixture
def mock_git_only():
    """Ensure only git detection is used (no-op now that jj is removed)."""
    yield


# =============================================================================
# VCS Detection Integration Tests
# =============================================================================


class TestVCSDetection:
    # TODO(conventions): retrofit test bodies
    """Integration tests for VCS detection."""

    def test_detect_git_repo(self, git_repo, mock_git_only):
        """Should detect git repository correctly."""
        vcs = get_vcs(git_repo)
        assert vcs.backend == VCSBackend.GIT
        assert vcs.is_repo(git_repo)

    def test_capabilities_match_backend(self, git_repo, mock_git_only):
        """Capabilities should match backend type."""
        vcs = get_vcs(git_repo)
        assert vcs.backend == VCSBackend.GIT
        assert vcs.capabilities == GIT_CAPABILITIES


# =============================================================================
# Workspace Creation Integration Tests
# =============================================================================


class TestWorkspaceCreation:
    """Integration tests for workspace creation."""

    def test_create_workspace(self, git_repo, mock_git_only):
        """Should create workspace successfully."""
        vcs = get_vcs(git_repo)
        workspace_path = git_repo / ".worktrees" / "test-lane-a"

        result = vcs.create_workspace(
            workspace_path=workspace_path,
            workspace_name="test-lane-a",
            repo_root=git_repo,
        )

        assert result.success, f"Create failed: {result.error}"
        assert workspace_path.exists()
        assert (workspace_path / ".git").exists()

    def test_create_workspace_with_base_branch(self, git_repo, mock_git_only):
        """Should create workspace from base branch."""
        vcs = get_vcs(git_repo)

        # Create a feature branch first
        subprocess.run(
            ["git", "checkout", "-b", "feature-base"],
            cwd=git_repo,
            capture_output=True,
            check=True,
        )
        (git_repo / "feature.txt").write_text("feature content")
        subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Feature commit"],
            cwd=git_repo,
            capture_output=True,
        )

        # Go back to main
        subprocess.run(
            ["git", "checkout", "-"],
            cwd=git_repo,
            capture_output=True,
        )

        # Create workspace from feature-base
        workspace_path = git_repo / ".worktrees" / "test-lane-b"
        result = vcs.create_workspace(
            workspace_path=workspace_path,
            workspace_name="test-lane-b",
            base_branch="feature-base",
            repo_root=git_repo,
        )

        assert result.success, f"Create failed: {result.error}"
        # Workspace should have the feature file
        assert (workspace_path / "feature.txt").exists()

    def test_list_workspaces(self, git_repo, mock_git_only):
        """Should list all workspaces."""
        vcs = get_vcs(git_repo)

        # Create two workspaces
        ws1 = git_repo / ".worktrees" / "wp01"
        ws2 = git_repo / ".worktrees" / "wp02"
        vcs.create_workspace(ws1, "wp01", repo_root=git_repo)
        vcs.create_workspace(ws2, "wp02", repo_root=git_repo)

        workspaces = vcs.list_workspaces(git_repo)

        # Should include main repo + 2 worktrees
        assert len(workspaces) >= 3
        workspace_names = [w.name for w in workspaces]
        assert "wp01" in workspace_names
        assert "wp02" in workspace_names


# =============================================================================
# Commit Operations Integration Tests
# =============================================================================


class TestCommitOperations:
    """Integration tests for commit operations."""

    def test_get_changes_history(self, git_repo, mock_git_only):
        """Should get commit history."""
        vcs = get_vcs(git_repo)

        # Add some commits
        for i in range(3):
            (git_repo / f"file{i}.txt").write_text(f"content {i}")
            subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", f"Commit {i}"],
                cwd=git_repo,
                capture_output=True,
            )

        changes = vcs.get_changes(git_repo, limit=5)

        assert len(changes) >= 3
        # Most recent first
        assert changes[0].message == "Commit 2"


# =============================================================================
# Operation History Integration Tests
# =============================================================================


class TestOperationHistory:
    """Integration tests for operation history."""

    def test_git_reflog(self, git_repo):
        """git_get_reflog should return operation history."""
        from specify_cli.core.vcs.git import git_get_reflog

        # Make some commits
        for i in range(3):
            (git_repo / f"ref{i}.txt").write_text(f"content {i}")
            subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", f"Reflog commit {i}"],
                cwd=git_repo,
                capture_output=True,
            )

        operations = git_get_reflog(git_repo, limit=10)

        assert len(operations) >= 3
        # Should have commit operations
        assert any("commit" in op.description.lower() for op in operations)


# =============================================================================
# Full Workflow Integration Tests
# =============================================================================


class TestFullWorkflow:
    """End-to-end integration tests for complete workflows."""

    def test_init_implement_sync_workflow(self, git_repo, mock_git_only):
        """Test init → implement → sync workflow."""
        vcs = get_vcs(git_repo)

        # Step 1: Create workspace (simulates implement)
        workspace_path = git_repo / ".worktrees" / "feature-lane-a"
        result = vcs.create_workspace(
            workspace_path=workspace_path,
            workspace_name="kitty/mission-feature-lane-a",
            repo_root=git_repo,
        )
        assert result.success

        # Step 2: Make changes in workspace
        (workspace_path / "feature_code.py").write_text("# Feature code")

        # Step 3: Commit in workspace
        subprocess.run(["git", "-C", str(workspace_path), "add", "--", "feature_code.py"], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(workspace_path), "-c", "commit.gpgsign=false", "commit", "-m", "Implement feature", "--", "feature_code.py"],
            check=True,
            capture_output=True,
        )

        # Step 4: Verify workspace info
        info = vcs.get_workspace_info(workspace_path)
        assert info is not None
        assert info.name == "feature-lane-a"

    def test_create_workspace_from_explicit_base_branch(self, git_repo, mock_git_only):
        """VCS layer can create a worktree from an explicitly supplied base branch."""
        vcs = get_vcs(git_repo)

        # Create lane-a
        wp01_path = git_repo / ".worktrees" / "feature-lane-a"
        result = vcs.create_workspace(
            workspace_path=wp01_path,
            workspace_name="kitty/mission-feature-lane-a",
            repo_root=git_repo,
        )
        assert result.success

        # Add some code in lane-a
        (wp01_path / "wp01_code.py").write_text("# WP01 code")
        subprocess.run(["git", "add", "."], cwd=wp01_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "WP01 implementation"],
            cwd=wp01_path,
            capture_output=True,
        )

        # Create lane-b from the lane-a branch
        wp02_path = git_repo / ".worktrees" / "feature-lane-b"
        result = vcs.create_workspace(
            workspace_path=wp02_path,
            workspace_name="kitty/mission-feature-lane-b",
            base_branch="kitty/mission-feature-lane-a",
            repo_root=git_repo,
        )
        assert result.success

        # WP02 should have WP01's code
        assert (wp02_path / "wp01_code.py").exists()


# =============================================================================
# Conflict Detection Integration Tests
# =============================================================================


class TestConflictDetection:
    """Integration tests for conflict detection."""

    def test_no_conflicts_clean_repo(self, git_repo, mock_git_only):
        """Clean repo should have no conflicts."""
        vcs = get_vcs(git_repo)
        assert vcs.has_conflicts(git_repo) is False
        assert vcs.detect_conflicts(git_repo) == []

    def test_detect_merge_conflicts(self, git_repo, mock_git_only):
        """Should detect conflicts during merge."""
        vcs = get_vcs(git_repo)

        # Get current branch name
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=git_repo,
            capture_output=True,
            text=True,
        )
        main_branch = result.stdout.strip()

        # Create conflict: modify same file on main and branch
        (git_repo / "conflict.txt").write_text("main content")
        subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Main change"],
            cwd=git_repo,
            capture_output=True,
        )

        # Create branch from before the change
        subprocess.run(
            ["git", "checkout", "-b", "conflict-branch", "HEAD~1"],
            cwd=git_repo,
            capture_output=True,
        )
        (git_repo / "conflict.txt").write_text("branch content")
        subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Branch change"],
            cwd=git_repo,
            capture_output=True,
        )

        # Try to merge (will conflict)
        subprocess.run(
            ["git", "merge", main_branch],
            cwd=git_repo,
            capture_output=True,
        )

        # Now detect conflicts
        assert vcs.has_conflicts(git_repo) is True
        conflicts = vcs.detect_conflicts(git_repo)
        assert len(conflicts) >= 1
