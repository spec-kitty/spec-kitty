"""Unit tests for _validate_ready_for_review (2.x contract).

Extracted from test_tasks.py during test-detection-remediation.
These test the active 2.x _validate_ready_for_review helper.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

from tests.lane_test_utils import lane_branch_name, lane_worktree_path, write_single_lane_manifest


import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]
_SOFTWARE_SLUG = "008-feature"
_MOVE_TASK_SLUG = "001-test-feature"


def _status_z(porcelain: str = "") -> Mock:
    """A ``git status --porcelain=v1 -z`` result built from classic porcelain lines.

    ``kernel.git`` reads NUL-delimited bytes, so each ``XY path`` line becomes one record.
    """
    records = [line for line in porcelain.splitlines() if line.strip()]
    return Mock(returncode=0, stdout="".join(f"{record}\0" for record in records).encode(), stderr=b"")


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def _real_lane_mission(tmp_path: Path, mission_slug: str) -> tuple[Path, Path]:
    """A real git repo on ``main`` with a software-dev mission and its lane worktree.

    Nothing about git is scripted: the review gate reads real porcelain status
    and real commit counts from the lane worktree.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-qb", "main")
    _git(repo, "config", "user.email", "tests@example.invalid")
    _git(repo, "config", "user.name", "Spec Kitty Tests")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / ".gitignore").write_text(".worktrees/\n", encoding="utf-8")
    (repo / "src").mkdir()
    (repo / "src" / "main.py").write_text("x = 1\n", encoding="utf-8")
    feature_dir = repo / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True)
    write_single_lane_manifest(feature_dir, wp_ids=("WP01",), predicted_surfaces=("review",))
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "init")
    worktree = lane_worktree_path(repo, mission_slug)
    _git(repo, "worktree", "add", "-q", "-b", lane_branch_name(mission_slug), str(worktree), "main")
    return repo, worktree


def _commit_in_worktree(worktree: Path, content: str) -> None:
    (worktree / "src" / "main.py").write_text(content, encoding="utf-8")
    _git(worktree, "commit", "-qam", "feat(WP01): implement")


class TestValidateReadyForReview:
    """Tests for _validate_ready_for_review helper."""

    def test_force_bypasses_validation(self, tmp_path: Path):
        """Should skip all checks when force=True."""
        from specify_cli.cli.commands.agent.tasks import _validate_ready_for_review

        # Don't need to set up anything - force should bypass all checks
        is_valid, guidance = _validate_ready_for_review(tmp_path, "008-test", "WP01", force=True)

        assert is_valid is True
        assert guidance == []

    @patch("specify_cli.cli.commands.agent.tasks.get_main_repo_root")
    @patch("specify_cli.cli.commands.agent.tasks.get_mission_type")
    @patch("subprocess.run")
    def test_research_uncommitted_artifacts_blocks_review(
        self, mock_run: Mock, mock_mission_type: Mock, mock_main_root: Mock, tmp_path: Path
    ):
        """Should detect uncommitted research artifacts and provide actionable guidance."""
        from specify_cli.cli.commands.agent.tasks import _validate_ready_for_review

        # Setup mocks
        mock_main_root.return_value = tmp_path
        mock_mission_type.return_value = "research"

        # Create feature directory
        feature_dir = tmp_path / "kitty-specs" / "008-research"
        feature_dir.mkdir(parents=True)

        # Simulate uncommitted research artifacts
        mock_run.return_value = _status_z(
            " M kitty-specs/008-research/data-model.md\n M kitty-specs/008-research/research/evidence-log.csv\n"
        )

        is_valid, guidance = _validate_ready_for_review(tmp_path, "008-research", "WP01", force=False)

        assert is_valid is False
        assert len(guidance) > 0
        # Check actionable guidance is present
        guidance_text = "\n".join(guidance)
        assert "uncommitted" in guidance_text.lower()
        assert "spec-kitty safe-commit" in guidance_text
        assert "research(WP01)" in guidance_text  # Research-specific commit format

    @patch("specify_cli.cli.commands.agent.tasks.get_main_repo_root")
    @patch("specify_cli.cli.commands.agent.tasks.get_mission_type")
    @patch("subprocess.run")
    def test_research_committed_artifacts_allows_review(
        self, mock_run: Mock, mock_mission_type: Mock, mock_main_root: Mock, tmp_path: Path
    ):
        """Should pass when research artifacts are committed."""
        from specify_cli.cli.commands.agent.tasks import _validate_ready_for_review

        # Setup mocks
        mock_main_root.return_value = tmp_path
        mock_mission_type.return_value = "research"

        # Create feature directory
        feature_dir = tmp_path / "kitty-specs" / "008-research"
        feature_dir.mkdir(parents=True)

        # Simulate no uncommitted changes
        mock_run.return_value = _status_z("")

        is_valid, guidance = _validate_ready_for_review(tmp_path, "008-research", "WP01", force=False)

        assert is_valid is True
        assert guidance == []

    def test_softwaredev_uncommitted_worktree_blocks_review(self, tmp_path: Path):
        """Uncommitted implementation changes in the lane worktree block review."""
        from specify_cli.cli.commands.agent.tasks import _validate_ready_for_review

        repo, worktree = _real_lane_mission(tmp_path, _SOFTWARE_SLUG)
        _commit_in_worktree(worktree, "x = 2\n")
        (worktree / "src" / "main.py").write_text("x = 3\n", encoding="utf-8")

        is_valid, guidance = _validate_ready_for_review(repo, _SOFTWARE_SLUG, "WP01", force=False)

        assert is_valid is False
        guidance_text = "\n".join(guidance)
        assert "uncommitted" in guidance_text.lower()
        assert "worktree" in guidance_text.lower()
        assert "M src/main.py" in guidance_text
        assert "spec-kitty safe-commit" in guidance_text

    def test_softwaredev_no_commits_blocks_review(self, tmp_path: Path):
        """A clean lane worktree with no commits beyond the target blocks review."""
        from specify_cli.cli.commands.agent.tasks import _validate_ready_for_review

        repo, _worktree = _real_lane_mission(tmp_path, _SOFTWARE_SLUG)

        is_valid, guidance = _validate_ready_for_review(repo, _SOFTWARE_SLUG, "WP01", force=False)

        assert is_valid is False
        assert "no implementation commits" in "\n".join(guidance).lower()

    @patch("specify_cli.cli.commands.agent.tasks.get_main_repo_root")
    @patch("specify_cli.cli.commands.agent.tasks.get_mission_type")
    @patch("subprocess.run")
    def test_filters_out_wp_status_files(
        self, mock_run: Mock, mock_mission_type: Mock, mock_main_root: Mock, tmp_path: Path
    ):
        """Should ignore WP status files in tasks/ (auto-committed by move-task)."""
        from specify_cli.cli.commands.agent.tasks import _validate_ready_for_review

        # Setup mocks
        mock_main_root.return_value = tmp_path
        mock_mission_type.return_value = "research"

        # Create feature directory
        feature_dir = tmp_path / "kitty-specs" / "008-research"
        feature_dir.mkdir(parents=True)

        # Simulate only WP status files modified (should be filtered out)
        mock_run.return_value = _status_z(" M kitty-specs/008-research/tasks/WP01-task.md\n")

        is_valid, guidance = _validate_ready_for_review(tmp_path, "008-research", "WP01", force=False)

        # Should pass - WP status files are filtered out
        assert is_valid is True
        assert guidance == []


class TestMoveTaskPreflightCheck:
    """Test that move-task command blocks on uncommitted changes.

    Extracted from test_workflow_instructions.py during test-detection-remediation.
    """

    def test_validate_ready_for_review_blocks_on_uncommitted_worktree_changes(self, tmp_path):
        """Staged and untracked worktree changes block review with explicit staging guidance."""
        from specify_cli.cli.commands.agent.tasks import _validate_ready_for_review

        repo, worktree = _real_lane_mission(tmp_path, _MOVE_TASK_SLUG)
        _commit_in_worktree(worktree, "x = 2\n")
        (worktree / "src" / "main.py").write_text("x = 3\n", encoding="utf-8")
        _git(worktree, "add", "src/main.py")
        (worktree / "test_new.py").write_text("", encoding="utf-8")

        is_valid, guidance = _validate_ready_for_review(repo, _MOVE_TASK_SLUG, "WP01", False)

        assert is_valid is False, "Expected validation to fail"
        assert any(
            any(keyword in line.lower() for keyword in ["uncommitted", "staged", "unstaged"]) for line in guidance
        ), f"No uncommitted/staged message in: {guidance}"
        assert any("<deliverable-path-1> <deliverable-path-2>" in line for line in guidance), (
            f"No explicit staging guidance in: {guidance}"
        )
        assert any("spec-kitty safe-commit" in line for line in guidance), f"No 'spec-kitty safe-commit' in: {guidance}"

    def test_validate_ready_for_review_allows_clean_worktree(self, tmp_path):
        """A clean lane worktree with implementation commits passes validation."""
        from specify_cli.cli.commands.agent.tasks import _validate_ready_for_review

        repo, worktree = _real_lane_mission(tmp_path, _MOVE_TASK_SLUG)
        _commit_in_worktree(worktree, "x = 2\n")

        is_valid, guidance = _validate_ready_for_review(repo, _MOVE_TASK_SLUG, "WP01", False)

        assert is_valid is True, guidance
        assert guidance == []

    def test_validate_ready_for_review_respects_force_flag(self, tmp_path):
        """Verify --force bypasses validation."""
        from specify_cli.cli.commands.agent.tasks import _validate_ready_for_review

        is_valid, guidance = _validate_ready_for_review(
            tmp_path,
            "001-test",
            "WP01",
            True,  # force=True
        )

        assert is_valid is True
        assert len(guidance) == 0
