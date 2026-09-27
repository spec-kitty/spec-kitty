"""Unit tests for merge workspace lifecycle management.

Tests dedicated merge worktree creation and cleanup under
.kittify/runtime/merge/<mission_id>/workspace/.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]  # non_sandbox: trampoline bug: subprocess
from specify_cli.consolidation.workspace import (
    cleanup_merge_workspace,
    create_merge_workspace,
    get_merge_runtime_dir,
    get_merge_workspace,
    get_merge_workspace_path,
)


MISSION_ID = "057-test-feature"


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a minimal git repository for testing."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    # Initial commit so we have a branch to check out
    (tmp_path / "README.md").write_text("# Test\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    return tmp_path


class TestPathHelpers:
    """Tests for workspace path helper functions."""

    def test_get_merge_runtime_dir(self, tmp_path: Path):
        result = get_merge_runtime_dir(MISSION_ID, tmp_path)
        assert result == tmp_path / ".kittify" / "runtime" / "merge" / MISSION_ID

    def test_get_merge_workspace_path(self, tmp_path: Path):
        result = get_merge_workspace_path(MISSION_ID, tmp_path)
        assert result == (
            tmp_path / ".kittify" / "runtime" / "merge" / MISSION_ID / "workspace"
        )

    def test_workspace_not_under_worktrees(self, tmp_path: Path):
        """Workspace path must be under .kittify/runtime, NOT .worktrees."""
        workspace_path = get_merge_workspace_path(MISSION_ID, tmp_path)
        assert ".worktrees" not in workspace_path.parts


class TestCreateMergeWorkspace:
    """Tests for create_merge_workspace function."""

    def test_workspace_created_at_canonical_path(self, git_repo: Path):
        # Discover the current branch name (may be 'main' or 'master')
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=git_repo,
            capture_output=True,
            text=True,
            check=True,
        )
        branch = result.stdout.strip()

        workspace = create_merge_workspace(MISSION_ID, branch, git_repo)

        expected = git_repo / ".kittify" / "runtime" / "merge" / MISSION_ID / "workspace"
        assert workspace == expected
        assert workspace.exists()

    def test_workspace_is_valid_git_worktree(self, git_repo: Path):
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=git_repo,
            capture_output=True,
            text=True,
            check=True,
        )
        branch = result.stdout.strip()

        workspace = create_merge_workspace(MISSION_ID, branch, git_repo)

        # Check git rev-parse works inside the worktree
        check = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=workspace,
            capture_output=True,
            check=False,
        )
        assert check.returncode == 0, "Workspace is not a valid git directory"

    def test_target_branch_commit_in_workspace(self, git_repo: Path):
        """Workspace HEAD commit should match the target branch tip."""
        target_branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=git_repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        branch_sha = subprocess.run(
            ["git", "rev-parse", target_branch],
            cwd=git_repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        workspace = create_merge_workspace(MISSION_ID, target_branch, git_repo)

        workspace_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=workspace,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        assert workspace_sha == branch_sha

    def test_main_repo_branch_unchanged(self, git_repo: Path):
        """Creating a workspace must NOT change main repo's checked-out branch."""
        original_branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=git_repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        create_merge_workspace(MISSION_ID, original_branch, git_repo)

        after_branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=git_repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        assert after_branch == original_branch, (
            "Main repo branch changed after creating merge workspace!"
        )

    def test_returns_path_if_already_exists(self, git_repo: Path):
        """Calling create_merge_workspace twice returns the existing path."""
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=git_repo,
            capture_output=True,
            text=True,
            check=True,
        )
        branch = result.stdout.strip()

        path1 = create_merge_workspace(MISSION_ID, branch, git_repo)
        path2 = create_merge_workspace(MISSION_ID, branch, git_repo)
        assert path1 == path2


class TestGetMergeWorkspace:
    """Tests for get_merge_workspace function."""

    def test_returns_none_when_not_exists(self, tmp_path: Path):
        result = get_merge_workspace(MISSION_ID, tmp_path)
        assert result is None

    def test_returns_path_when_valid_worktree(self, git_repo: Path):
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=git_repo,
            capture_output=True,
            text=True,
            check=True,
        )
        branch = result.stdout.strip()

        create_merge_workspace(MISSION_ID, branch, git_repo)
        found = get_merge_workspace(MISSION_ID, git_repo)

        expected = git_repo / ".kittify" / "runtime" / "merge" / MISSION_ID / "workspace"
        assert found == expected

    def test_returns_none_after_cleanup(self, git_repo: Path):
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=git_repo,
            capture_output=True,
            text=True,
            check=True,
        )
        branch = result.stdout.strip()

        create_merge_workspace(MISSION_ID, branch, git_repo)
        cleanup_merge_workspace(MISSION_ID, git_repo)

        found = get_merge_workspace(MISSION_ID, git_repo)
        assert found is None


class TestCleanupMergeWorkspace:
    """Tests for cleanup_merge_workspace function."""

    def test_cleanup_removes_workspace_directory(self, git_repo: Path):
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=git_repo,
            capture_output=True,
            text=True,
            check=True,
        )
        branch = result.stdout.strip()

        workspace = create_merge_workspace(MISSION_ID, branch, git_repo)
        assert workspace.exists()

        cleanup_merge_workspace(MISSION_ID, git_repo)

        assert not workspace.exists()

    def test_cleanup_removes_runtime_dir(self, git_repo: Path):
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=git_repo,
            capture_output=True,
            text=True,
            check=True,
        )
        branch = result.stdout.strip()

        create_merge_workspace(MISSION_ID, branch, git_repo)
        runtime_dir = get_merge_runtime_dir(MISSION_ID, git_repo)
        assert runtime_dir.exists()

        cleanup_merge_workspace(MISSION_ID, git_repo)

        assert not runtime_dir.exists()

    def test_cleanup_removes_git_worktree_registration(self, git_repo: Path):
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=git_repo,
            capture_output=True,
            text=True,
            check=True,
        )
        branch = result.stdout.strip()

        workspace = create_merge_workspace(MISSION_ID, branch, git_repo)

        # Verify registered
        worktree_list = subprocess.run(
            ["git", "worktree", "list"],
            cwd=git_repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        assert str(workspace) in worktree_list

        cleanup_merge_workspace(MISSION_ID, git_repo)

        worktree_list_after = subprocess.run(
            ["git", "worktree", "list"],
            cwd=git_repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        assert str(workspace) not in worktree_list_after

    def test_cleanup_is_idempotent(self, git_repo: Path):
        """cleanup_merge_workspace should not raise if already cleaned up."""
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=git_repo,
            capture_output=True,
            text=True,
            check=True,
        )
        branch = result.stdout.strip()

        create_merge_workspace(MISSION_ID, branch, git_repo)
        cleanup_merge_workspace(MISSION_ID, git_repo)
        # Second call should not raise
        cleanup_merge_workspace(MISSION_ID, git_repo)

    def test_cleanup_noop_when_workspace_never_created(self, git_repo: Path):
        """cleanup_merge_workspace should not raise if workspace was never created."""
        # Should not raise
        cleanup_merge_workspace(MISSION_ID, git_repo)
