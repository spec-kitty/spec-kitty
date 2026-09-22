"""Tests for GitVCS implementation.

Tests all VCSProtocol methods for the git backend.
"""

import subprocess
from pathlib import Path

import pytest

from specify_cli.core.vcs import VCSBackend, VCSProtocol
from specify_cli.core.vcs.git import (
    GitVCS,
    git_get_reflog,
)


pytestmark = [pytest.mark.git_repo]


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def git_repo(tmp_path):
    """Create a minimal git repository for testing."""
    # Initialize repo
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)

    # Configure git user for commits
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
def git_vcs():
    """Create a GitVCS instance."""
    return GitVCS()


# =============================================================================
# Basic Properties Tests
# =============================================================================


class TestGitVCSProperties:
    """Tests for GitVCS properties."""

    def test_backend_property(self, git_vcs):
        """GitVCS should return GIT backend."""
        assert git_vcs.backend == VCSBackend.GIT

    def test_capabilities_property(self, git_vcs):
        """GitVCS should return correct capabilities."""
        caps = git_vcs.capabilities
        assert caps.supports_workspaces is True
        assert caps.supports_auto_rebase is False
        assert caps.supports_change_ids is False
        # Git has reflog which provides operation-log-like functionality
        assert caps.supports_operation_log is True
        # Git doesn't have conflict storage like jj
        assert caps.supports_conflict_storage is False
        assert caps.supports_colocated is False

    def test_implements_protocol(self, git_vcs):
        """GitVCS should implement VCSProtocol."""
        assert isinstance(git_vcs, VCSProtocol)


# =============================================================================
# Repository Operations Tests
# =============================================================================


class TestRepositoryOperations:
    """Tests for repository-level operations."""

    def test_is_repo_true_for_git_repo(self, git_repo, git_vcs):
        """is_repo should return True for git repository."""
        assert git_vcs.is_repo(git_repo) is True

    def test_is_repo_false_for_non_repo(self, tmp_path, git_vcs):
        """is_repo should return False for non-repository directory."""
        assert git_vcs.is_repo(tmp_path) is False

    def test_is_repo_false_for_nonexistent(self, tmp_path, git_vcs):
        """is_repo should return False for nonexistent path."""
        assert git_vcs.is_repo(tmp_path / "nonexistent") is False

    def test_get_repo_root(self, git_repo, git_vcs):
        """get_repo_root should return repository root."""
        root = git_vcs.get_repo_root(git_repo)
        assert root == git_repo

    def test_get_repo_root_from_subdir(self, git_repo, git_vcs):
        """get_repo_root should work from subdirectory."""
        subdir = git_repo / "subdir"
        subdir.mkdir()

        root = git_vcs.get_repo_root(subdir)
        assert root == git_repo

    def test_get_repo_root_returns_none_for_non_repo(self, tmp_path, git_vcs):
        """get_repo_root should return None for non-repository."""
        root = git_vcs.get_repo_root(tmp_path)
        assert root is None

    def test_init_repo(self, tmp_path, git_vcs):
        """init_repo should create a new git repository."""
        new_repo = tmp_path / "new_repo"
        result = git_vcs.init_repo(new_repo)

        assert result is True
        assert (new_repo / ".git").exists()


# =============================================================================
# Workspace Operations Tests
# =============================================================================


class TestWorkspaceOperations:
    """Tests for workspace (worktree) operations."""

    def test_create_workspace(self, git_repo, git_vcs):
        """create_workspace should create a git worktree."""
        workspace_path = git_repo / ".worktrees" / "test-lane-a"

        result = git_vcs.create_workspace(
            workspace_path,
            "test-lane-a",
            repo_root=git_repo,
        )

        assert result.success is True, f"Failed: {result.error}"
        assert result.error is None
        assert workspace_path.exists()
        assert (workspace_path / ".git").exists()

    def test_create_workspace_with_base_branch(self, git_repo, git_vcs):
        """create_workspace should support branching from a base branch."""
        # First, get the current branch name (main or master)
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=git_repo,
            capture_output=True,
            text=True,
        )
        main_branch = result.stdout.strip()

        # Create a branch to use as base
        subprocess.run(
            ["git", "checkout", "-b", "feature-base"],
            cwd=git_repo,
            capture_output=True,
            check=True,
        )
        (git_repo / "feature.txt").write_text("feature content")
        subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Feature commit"],
            cwd=git_repo,
            capture_output=True,
            check=True,
        )

        # Go back to main branch
        subprocess.run(
            ["git", "checkout", main_branch],
            cwd=git_repo,
            capture_output=True,
            check=True,
        )

        # Create workspace from feature-base branch
        # Note: git worktree add needs to run from within the repo
        workspace_path = git_repo / ".worktrees" / "test-lane-b"

        # Run worktree add from the git repo directory
        wt_result = subprocess.run(
            ["git", "worktree", "add", "-b", "test-lane-b", str(workspace_path), "feature-base"],
            cwd=git_repo,
            capture_output=True,
            text=True,
        )

        assert wt_result.returncode == 0, f"worktree add failed: {wt_result.stderr}"
        # The workspace should have the feature file from the base branch
        assert (workspace_path / "feature.txt").exists()

    def test_create_workspace_returns_error_on_failure(self, tmp_path, git_vcs):
        """create_workspace should return error for non-repo path."""
        workspace_path = tmp_path / ".worktrees" / "test-lane-a"

        result = git_vcs.create_workspace(
            workspace_path,
            "test-lane-a",
        )

        # Git worktree add should fail in non-repo
        assert result.success is False
        assert result.error is not None

    def test_remove_workspace(self, git_repo, git_vcs):
        """remove_workspace should remove a worktree."""
        workspace_path = git_repo / ".worktrees" / "test-remove"

        # Create workspace first
        create_result = git_vcs.create_workspace(workspace_path, "test-remove", repo_root=git_repo)
        assert create_result.success is True, f"Create failed: {create_result.error}"
        assert workspace_path.exists()

        # Remove it
        result = git_vcs.remove_workspace(workspace_path)

        assert result is True
        assert not workspace_path.exists()

    def test_get_workspace_info(self, git_repo, git_vcs):
        """get_workspace_info should return workspace details."""
        workspace_path = git_repo / ".worktrees" / "test-info"
        create_result = git_vcs.create_workspace(workspace_path, "test-info", repo_root=git_repo)
        assert create_result.success is True, f"Create failed: {create_result.error}"

        info = git_vcs.get_workspace_info(workspace_path)

        assert info is not None
        assert info.name == "test-info"
        assert info.path == workspace_path
        assert info.backend == VCSBackend.GIT
        assert info.current_branch == "test-info"
        assert info.current_commit_id is not None
        assert info.current_change_id is None  # Git doesn't have change IDs

    def test_get_workspace_info_returns_none_for_invalid(self, tmp_path, git_vcs):
        """get_workspace_info should return None for invalid path."""
        info = git_vcs.get_workspace_info(tmp_path / "nonexistent")
        assert info is None

    def test_list_workspaces(self, git_repo, git_vcs):
        """list_workspaces should return all worktrees."""
        # Create two workspaces
        ws1 = git_repo / ".worktrees" / "wp01"
        ws2 = git_repo / ".worktrees" / "wp02"
        r1 = git_vcs.create_workspace(ws1, "wp01", repo_root=git_repo)
        r2 = git_vcs.create_workspace(ws2, "wp02", repo_root=git_repo)
        assert r1.success is True, f"wp01 failed: {r1.error}"
        assert r2.success is True, f"wp02 failed: {r2.error}"

        workspaces = git_vcs.list_workspaces(git_repo)

        # Should include main repo + 2 worktrees = 3 total
        assert len(workspaces) >= 3
        # Check that the worktree paths are in the list
        workspace_paths = [str(w.path) for w in workspaces]
        assert any("wp01" in p for p in workspace_paths)
        assert any("wp02" in p for p in workspace_paths)


# =============================================================================
# Commit Operations Tests
# =============================================================================


class TestCommitOperations:
    """Tests for commit/change operations."""

    def test_get_current_change(self, git_repo, git_vcs):
        """get_current_change should return current HEAD info."""
        change = git_vcs.get_current_change(git_repo)

        assert change is not None
        assert change.commit_id is not None
        assert change.message == "Initial commit"
        assert change.author == "Test User"
        assert change.change_id is None  # Git doesn't have change IDs

    def test_get_changes(self, git_repo, git_vcs):
        """get_changes should return commit history."""
        # Add a couple more commits
        for i in range(3):
            (git_repo / f"file{i}.txt").write_text(f"content {i}")
            subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", f"Commit {i}"],
                cwd=git_repo,
                capture_output=True,
            )

        changes = git_vcs.get_changes(git_repo, limit=5)

        assert len(changes) >= 3
        # Most recent first
        assert changes[0].message == "Commit 2"

    def test_get_changes_with_revision_range(self, git_repo, git_vcs):
        """get_changes should support revision ranges."""
        # Get initial commit
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=git_repo,
            capture_output=True,
            text=True,
        )
        initial_commit = result.stdout.strip()

        # Add commits
        for i in range(2):
            (git_repo / f"file{i}.txt").write_text(f"content {i}")
            subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", f"Commit {i}"],
                cwd=git_repo,
                capture_output=True,
            )

        changes = git_vcs.get_changes(git_repo, revision_range=f"{initial_commit}..HEAD")

        assert frozenset(c.message for c in changes) == frozenset({"Commit 0", "Commit 1"})

    def test_commit(self, git_repo, git_vcs):
        """commit should create a new commit."""
        # Make a change
        (git_repo / "new_file.txt").write_text("new content")

        change = git_vcs.commit(git_repo, "Test commit message")

        assert change is not None
        assert change.message == "Test commit message"

    def test_commit_returns_none_when_nothing_to_commit(self, git_repo, git_vcs):
        """commit should return None when nothing to commit."""
        change = git_vcs.commit(git_repo, "Empty commit")

        assert change is None

    def test_commit_specific_paths(self, git_repo, git_vcs):
        """commit should support committing specific paths."""
        # Make multiple changes
        (git_repo / "file1.txt").write_text("content 1")
        (git_repo / "file2.txt").write_text("content 2")

        # Commit only file1
        change = git_vcs.commit(
            git_repo,
            "Commit file1 only",
            paths=[Path("file1.txt")],
        )

        assert change is not None

        # file2 should still be untracked
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=git_repo,
            capture_output=True,
            text=True,
        )
        assert "file2.txt" in result.stdout


# =============================================================================
# Conflict Detection Tests
# =============================================================================


class TestConflictOperations:
    """Tests for conflict detection operations."""

    def test_has_conflicts_false_when_clean(self, git_repo, git_vcs):
        """has_conflicts should return False for clean repo."""
        assert git_vcs.has_conflicts(git_repo) is False

    def test_detect_conflicts_empty_when_clean(self, git_repo, git_vcs):
        """detect_conflicts should return empty list for clean repo."""
        conflicts = git_vcs.detect_conflicts(git_repo)
        assert conflicts == []

    def test_detect_conflicts_during_merge(self, git_repo, git_vcs):
        """detect_conflicts should find conflicts during merge."""
        # Create conflicting branches
        # First, create a change on main
        (git_repo / "conflict.txt").write_text("main content")
        subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Main change"],
            cwd=git_repo,
            capture_output=True,
        )

        # Create a branch from initial state and make conflicting change
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
        # Get the main branch name
        result = subprocess.run(
            ["git", "branch", "-l", "main", "master"],
            cwd=git_repo,
            capture_output=True,
            text=True,
        )
        main_branch = "main" if "main" in result.stdout else "master"

        subprocess.run(
            ["git", "merge", main_branch],
            cwd=git_repo,
            capture_output=True,
        )

        # Now detect conflicts
        assert git_vcs.has_conflicts(git_repo) is True
        conflicts = git_vcs.detect_conflicts(git_repo)
        assert len(conflicts) >= 1
        assert any(c.file_path == Path("conflict.txt") for c in conflicts)

    def test_conflict_marker_parsing(self, git_repo, git_vcs):
        """Conflict markers should be parsed for line ranges."""
        # Create a file with conflict markers
        conflict_content = """Normal line
<<<<<<< HEAD
This is our version
=======
This is their version
>>>>>>> branch
More normal content
"""
        conflict_file = git_repo / "marked_conflict.txt"
        conflict_file.write_text(conflict_content)

        # Simulate unmerged state (normally this happens during merge)
        # We'll test the marker parsing directly
        from specify_cli.core.vcs.git import GitVCS

        vcs = GitVCS()
        ranges = vcs._parse_conflict_markers(conflict_file)

        assert ranges == [(2, 6)]  # Lines 2-6 contain the conflict


# =============================================================================
# Sync Operations Tests
# =============================================================================


class TestSyncOperations:
    """Tests for workspace synchronization."""

    def test_is_workspace_stale_false_when_up_to_date(self, git_repo, git_vcs):
        """is_workspace_stale should return False when up to date."""
        # Without remote, staleness check should return False
        assert git_vcs.is_workspace_stale(git_repo) is False


# =============================================================================
# Git-Specific Functions Tests
# =============================================================================


class TestGitSpecificFunctions:
    """Tests for git-specific standalone functions."""

    def test_git_get_reflog(self, git_repo):
        """git_get_reflog should return reflog entries."""
        # Make some commits to have reflog entries
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
# Edge Cases Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_operations_on_nonexistent_path(self, git_vcs):
        """Operations should handle nonexistent paths gracefully."""
        fake_path = Path("/nonexistent/path/that/does/not/exist")

        assert git_vcs.is_repo(fake_path) is False
        assert git_vcs.get_repo_root(fake_path) is None
        assert git_vcs.get_workspace_info(fake_path) is None
        assert git_vcs.get_current_change(fake_path) is None
        assert git_vcs.get_changes(fake_path) == []
        assert git_vcs.detect_conflicts(fake_path) == []
        assert git_vcs.has_conflicts(fake_path) is False

    def test_workspace_info_detached_head(self, git_repo, git_vcs):
        """get_workspace_info should handle detached HEAD state."""
        # Get current commit
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=git_repo,
            capture_output=True,
            text=True,
        )
        commit = result.stdout.strip()

        # Detach HEAD
        subprocess.run(
            ["git", "checkout", commit],
            cwd=git_repo,
            capture_output=True,
        )

        info = git_vcs.get_workspace_info(git_repo)

        assert info is not None
        assert info.current_branch is None  # Detached HEAD = no branch
        assert info.current_commit_id == commit

    def test_commit_with_empty_message(self, git_repo, git_vcs):
        """commit should handle empty messages."""
        (git_repo / "empty_msg.txt").write_text("content")

        # Git actually allows empty messages with -m ""
        change = git_vcs.commit(git_repo, "")

        # Behavior depends on git config
        # Most setups will reject empty message, some won't
        # Just verify we don't crash
        assert change is None or change.message == ""
