"""Unit tests for accept and merge feature lifecycle commands."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import typer

from specify_cli.cli.commands.agent.mission import (
    _find_latest_feature_worktree,
    _get_current_branch,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

ACCEPTANCE_MODE_CHECKLIST = "checklist"


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_repo_with_worktrees(tmp_path: Path) -> Path:
    """Create a mock repository with worktrees."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    # Initialize git
    subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_root, check=True, capture_output=True)

    # Create initial commit
    (repo_root / "README.md").write_text("# Test Repo")
    subprocess.run(["git", "add", "."], cwd=repo_root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_root, check=True, capture_output=True)

    # Create worktrees directory
    worktrees = repo_root / ".worktrees"
    worktrees.mkdir()

    # Create mock worktrees
    (worktrees / "001-first-feature").mkdir()
    (worktrees / "003-latest-feature").mkdir()
    (worktrees / "002-middle-feature").mkdir()
    (worktrees / "not-a-feature").mkdir()  # Should be ignored

    return repo_root


# =============================================================================
# Unit Tests: Helper Functions (T073)
# =============================================================================


@pytest.mark.git_repo
def test_find_latest_feature_worktree(mock_repo_with_worktrees: Path):
    """Test finding latest worktree by number."""
    latest = _find_latest_feature_worktree(mock_repo_with_worktrees)

    assert latest is not None
    assert latest.name == "003-latest-feature"


def test_find_latest_feature_worktree_no_worktrees(tmp_path: Path):
    """Test when no worktrees directory exists."""
    latest = _find_latest_feature_worktree(tmp_path)
    assert latest is None


@pytest.mark.git_repo
def test_find_latest_feature_worktree_ignores_non_feature(mock_repo_with_worktrees: Path):
    """Test that non-feature directories are ignored."""
    latest = _find_latest_feature_worktree(mock_repo_with_worktrees)

    assert latest is not None
    assert latest.name != "not-a-feature"


@pytest.mark.git_repo
def test_get_current_branch(mock_repo_with_worktrees: Path):
    """Test getting current branch name."""
    branch = _get_current_branch(mock_repo_with_worktrees)

    # Default branch varies (main or master)
    assert branch in ["main", "master"]


@pytest.mark.git_repo
def test_get_current_branch_non_git(tmp_path: Path):
    """Test branch detection in non-git directory."""
    branch = _get_current_branch(tmp_path)
    assert branch == "main"


# =============================================================================
# Unit Tests: Accept Command (T073)
# =============================================================================


@patch("specify_cli.cli.commands.agent.mission.top_level_accept")
@patch("specify_cli.core.paths.locate_project_root")
def test_accept_command_delegates_to_toplevel(mock_locate: MagicMock, mock_accept: MagicMock, tmp_path: Path):
    """Test that accept command delegates to top-level accept() command."""
    # Setup mocks
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    mock_locate.return_value = repo_root

    # Import and call directly (avoid CliRunner issues)
    from specify_cli.cli.commands.agent.mission import accept_feature

    accept_feature(feature=None, mode="auto", json_output=True, lenient=False, no_commit=False)

    # Verify top-level accept was called
    mock_accept.assert_called_once_with(
        mission=None,
        mode="auto",
        actor=None,
        test=[],
        json_output=True,
        lenient=False,
        no_commit=False,
        diagnose=False,
        allow_fail=False,
        merge_commit=None,  # #4231: PR-merge evidence passthrough
        target_branch=None,  # #4231: PR base-branch passthrough
        attest_first_landing=False,  # #4231: anchor attestation passthrough
    )


@patch("specify_cli.cli.commands.agent.mission.top_level_accept")
@patch("specify_cli.core.paths.locate_project_root")
def test_accept_command_passes_flags(mock_locate: MagicMock, mock_accept: MagicMock, tmp_path: Path):
    """Test that accept command passes all flags to top-level accept()."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    mock_locate.return_value = repo_root

    from specify_cli.cli.commands.agent.mission import accept_feature

    accept_feature(
        feature="001-test",
        mode=ACCEPTANCE_MODE_CHECKLIST,
        json_output=True,
        lenient=True,
        no_commit=True,
    )

    # Verify all flags passed to top-level accept
    mock_accept.assert_called_once_with(
        mission="001-test",
        mode=ACCEPTANCE_MODE_CHECKLIST,
        actor=None,
        test=[],
        json_output=True,
        lenient=True,
        no_commit=True,
        diagnose=False,
        allow_fail=False,
        merge_commit=None,  # #4231: PR-merge evidence passthrough
        target_branch=None,  # #4231: PR base-branch passthrough
        attest_first_landing=False,  # #4231: anchor attestation passthrough
    )


# =============================================================================
# Unit Tests: Merge Command (T073)
# =============================================================================


@patch("specify_cli.cli.commands.agent.mission.top_level_merge")
@patch("specify_cli.cli.commands.agent.mission._get_current_branch")
@patch("specify_cli.core.paths.locate_project_root")
def test_merge_command_delegates_to_toplevel(mock_locate: MagicMock, mock_get_branch: MagicMock, mock_merge: MagicMock, tmp_path: Path):
    """Test that merge command delegates to top-level merge() command."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    mock_locate.return_value = repo_root
    mock_get_branch.return_value = "001-test-feature"  # On feature branch

    from specify_cli.cli.commands.agent.mission import merge_feature

    merge_feature(
        feature=None,
        target="main",
        strategy="merge",
        push=False,
        dry_run=False,
        keep_branch=False,
        keep_worktree=False,
        auto_retry=False,
    )

    # Verify top-level merge was called
    mock_merge.assert_called_once_with(
        strategy="merge",
        delete_branch=True,  # Inverted from keep_branch=False
        remove_worktree=True,  # Inverted from keep_worktree=False
        push=False,
        target_branch="main",
        dry_run=False,
        json_output=False,
        mission="",
        resume=False,
        abort=False,
        context_token=None,
        keep_workspace=False,
    )


@patch("specify_cli.cli.commands.agent.mission._find_feature_worktree")
@patch("specify_cli.cli.commands.agent.mission._get_current_branch")
@patch("subprocess.run")
@patch("specify_cli.cli.commands.agent.mission.locate_project_root")
def test_merge_command_auto_retry_logic(
    mock_locate: MagicMock,
    mock_subprocess: MagicMock,
    mock_get_branch: MagicMock,
    mock_find_feature_worktree: MagicMock,
    tmp_path: Path,
):
    """Test merge auto-retry when not on feature branch with explicit --feature."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    latest_worktree = tmp_path / "repo" / ".worktrees" / "002-feature"
    latest_worktree.mkdir(parents=True)

    mock_locate.return_value = repo_root
    mock_get_branch.return_value = "main"  # Not a feature branch
    mock_find_feature_worktree.return_value = latest_worktree
    mock_subprocess.return_value = MagicMock(returncode=0, stdout="", stderr="")

    from specify_cli.cli.commands.agent.mission import merge_feature

    with pytest.raises(SystemExit):
        merge_feature(
            feature="002-feature",
            target="main",
            strategy="merge",
            push=False,
            dry_run=False,
            keep_branch=False,
            keep_worktree=False,
            auto_retry=True,  # Enable auto-retry
        )

    # Verify deterministic worktree resolution happened
    mock_find_feature_worktree.assert_called_once_with(repo_root, "002-feature")

    # Verify command was re-run in worktree
    for call in mock_subprocess.call_args_list:
        call_args = call[0][0] if call[0] else []
        if "spec-kitty" in str(call_args):
            call_kwargs = call[1]
            assert call_kwargs.get("cwd") == latest_worktree
            break


@patch("specify_cli.cli.commands.agent.mission.top_level_merge")
@patch("specify_cli.cli.commands.agent.mission._get_current_branch")
@patch("specify_cli.core.paths.locate_project_root")
def test_merge_command_passes_all_flags(mock_locate: MagicMock, mock_get_branch: MagicMock, mock_merge: MagicMock, tmp_path: Path):
    """Test that merge command passes all flags to top-level merge()."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    mock_locate.return_value = repo_root
    mock_get_branch.return_value = "001-test"  # On feature branch

    from specify_cli.cli.commands.agent.mission import merge_feature

    merge_feature(
        feature="001-test",
        target="develop",
        strategy="squash",
        push=True,
        dry_run=True,
        keep_branch=True,
        keep_worktree=True,
        auto_retry=False,
    )

    # Verify all flags passed to top-level merge (with parameter mapping)
    mock_merge.assert_called_once_with(
        strategy="squash",
        delete_branch=False,  # Inverted from keep_branch=True
        remove_worktree=False,  # Inverted from keep_worktree=True
        push=True,
        target_branch="develop",  # Parameter name differs
        dry_run=True,
        json_output=False,
        mission="001-test",
        resume=False,
        abort=False,
        context_token=None,
        keep_workspace=False,
    )


# =============================================================================
# Error Path Tests (T073 - Coverage boost)
# =============================================================================


@patch("specify_cli.cli.commands.agent.mission.top_level_accept")
@patch("specify_cli.core.paths.locate_project_root")
def test_accept_command_propagates_errors(mock_locate: MagicMock, mock_accept: MagicMock, tmp_path: Path):
    """Test accept command propagates errors from top-level accept()."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    mock_locate.return_value = repo_root

    # Make top-level raise an exception
    mock_accept.side_effect = Exception("Acceptance failed")

    from specify_cli.cli.commands.agent.mission import accept_feature

    # Should catch exception and raise typer.Exit
    import typer

    with pytest.raises(typer.Exit) as exc_info:
        accept_feature(feature=None, mode="auto", json_output=True, lenient=False, no_commit=False)

    # Should exit with error
    assert exc_info.value.exit_code == 1


@patch("specify_cli.cli.commands.agent.mission.top_level_merge")
@patch("specify_cli.cli.commands.agent.mission._get_current_branch")
@patch("specify_cli.core.paths.locate_project_root")
def test_merge_command_propagates_errors(mock_locate: MagicMock, mock_get_branch: MagicMock, mock_merge: MagicMock, tmp_path: Path):
    """Test merge command propagates errors from top-level merge()."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    mock_locate.return_value = repo_root
    mock_get_branch.return_value = "001-test-feature"

    # Make top-level raise an exception
    mock_merge.side_effect = Exception("Merge failed")

    from specify_cli.cli.commands.agent.mission import merge_feature

    # Should catch exception and raise typer.Exit
    import typer

    with pytest.raises(typer.Exit) as exc_info:
        merge_feature(
            feature=None,
            target="main",
            strategy="merge",
            push=False,
            dry_run=False,
            keep_branch=False,
            keep_worktree=False,
            auto_retry=False,
        )

    # Should exit with error
    assert exc_info.value.exit_code == 1


@patch("specify_cli.cli.commands.agent.mission._find_feature_worktree")
@patch("specify_cli.cli.commands.agent.mission._get_current_branch")
@patch("specify_cli.cli.commands.agent.mission.locate_project_root")
def test_merge_command_auto_retry_no_worktree_found(
    mock_locate: MagicMock,
    mock_get_branch: MagicMock,
    mock_find_feature_worktree: MagicMock,
    tmp_path: Path,
):
    """Test merge when auto-retry enabled but target feature worktree does not exist."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    mock_locate.return_value = repo_root
    mock_get_branch.return_value = "main"  # Not a feature branch
    mock_find_feature_worktree.return_value = None  # No worktree for requested feature

    from specify_cli.cli.commands.agent.mission import merge_feature

    with patch("specify_cli.cli.commands.agent.mission.top_level_merge") as mock_merge:
        with pytest.raises(typer.Exit) as exc_info:
            merge_feature(
                feature="002-feature",
                target="main",
                strategy="merge",
                push=False,
                dry_run=False,
                keep_branch=False,
                keep_worktree=False,
                auto_retry=True,
            )

        assert exc_info.value.exit_code == 1
        mock_find_feature_worktree.assert_called_once_with(repo_root, "002-feature")
        mock_merge.assert_not_called()


@patch("specify_cli.cli.commands.agent.mission.top_level_accept")
@patch("specify_cli.core.paths.locate_project_root")
def test_accept_command_no_repo_root(mock_locate: MagicMock, mock_accept: MagicMock):
    """Test accept command when repo root cannot be located."""
    mock_locate.return_value = None

    # Make top-level accept raise TaskCliError (what find_repo_root does)
    from specify_cli.task_utils import TaskCliError

    mock_accept.side_effect = TaskCliError("Not in a git repository")

    from specify_cli.cli.commands.agent.mission import accept_feature

    # Should catch exception and raise typer.Exit
    import typer

    with pytest.raises(typer.Exit) as exc_info:
        accept_feature(feature=None, mode="auto", json_output=True, lenient=False, no_commit=False)

    assert exc_info.value.exit_code == 1


@patch("specify_cli.cli.commands.agent.mission.top_level_merge")
@patch("specify_cli.cli.commands.agent.mission._get_current_branch")
@patch("specify_cli.core.paths.locate_project_root")
def test_merge_command_no_repo_root(mock_locate: MagicMock, mock_get_branch: MagicMock, mock_merge: MagicMock):
    """Test merge command when repo root cannot be located."""
    mock_locate.return_value = None
    mock_get_branch.return_value = "001-test-feature"

    # Make top-level merge raise TaskCliError (what find_repo_root does)
    from specify_cli.task_utils import TaskCliError

    mock_merge.side_effect = TaskCliError("Not in a git repository")

    from specify_cli.cli.commands.agent.mission import merge_feature

    # Should catch exception and raise typer.Exit
    import typer

    with pytest.raises(typer.Exit) as exc_info:
        merge_feature(
            feature=None,
            target="main",
            strategy="merge",
            push=False,
            dry_run=False,
            keep_branch=False,
            keep_worktree=False,
            auto_retry=False,
        )

    assert exc_info.value.exit_code == 1


@patch("specify_cli.cli.commands.agent.mission.top_level_accept")
@patch("specify_cli.core.paths.locate_project_root")
def test_accept_command_with_all_flags_console_output(mock_locate: MagicMock, mock_accept: MagicMock, tmp_path: Path):
    """Test accept command with console output (non-JSON)."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    mock_locate.return_value = repo_root

    from specify_cli.cli.commands.agent.mission import accept_feature

    accept_feature(
        feature="001-test",
        mode=ACCEPTANCE_MODE_CHECKLIST,
        json_output=False,  # Console output mode
        lenient=True,
        no_commit=True,
    )

    # Verify top-level accept was called
    mock_accept.assert_called_once_with(
        mission="001-test",
        mode=ACCEPTANCE_MODE_CHECKLIST,
        actor=None,
        test=[],
        json_output=False,
        lenient=True,
        no_commit=True,
        diagnose=False,
        allow_fail=False,
        merge_commit=None,  # #4231: PR-merge evidence passthrough
        target_branch=None,  # #4231: PR base-branch passthrough
        attest_first_landing=False,  # #4231: anchor attestation passthrough
    )
