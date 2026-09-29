"""Unit tests for _validate_ready_for_review (2.x contract).

Extracted from test_tasks.py during test-detection-remediation.
These test the active 2.x _validate_ready_for_review helper.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from tests.lane_test_utils import lane_branch_name, lane_worktree_path, write_single_lane_manifest


import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]
def _mark_fake_worktree(path: Path) -> None:
    """Create the minimal marker required by workspace-resolution guards."""
    path.mkdir(parents=True, exist_ok=True)
    (path / ".git").write_text("gitdir: ../fake\n", encoding="utf-8")


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
        mock_run.return_value = Mock(
            returncode=0,
            stdout=" M kitty-specs/008-research/data-model.md\n M kitty-specs/008-research/research/evidence-log.csv\n",
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
        mock_run.return_value = Mock(returncode=0, stdout="")

        is_valid, guidance = _validate_ready_for_review(tmp_path, "008-research", "WP01", force=False)

        assert is_valid is True
        assert guidance == []

    @patch("specify_cli.cli.commands.agent.tasks.get_main_repo_root")
    @patch("specify_cli.cli.commands.agent.tasks.get_mission_type")
    @patch("subprocess.run")
    @patch("specify_cli.core.git_ops.get_current_branch", return_value="kitty/mission-008-feature-lane-a")
    @patch("specify_cli.workspace.context.load_context", return_value=None)
    @patch("specify_cli.cli.commands.agent.tasks.get_feature_target_branch", return_value="main")
    def test_softwaredev_uncommitted_worktree_blocks_review(
        self,
        mock_target: Mock,
        mock_ws: Mock,
        mock_branch: Mock,
        mock_run: Mock,
        mock_mission_type: Mock,
        mock_main_root: Mock,
        tmp_path: Path,
    ):
        """Should detect uncommitted implementation changes in worktree."""
        from specify_cli.cli.commands.agent.tasks import _validate_ready_for_review

        # Setup mocks
        mock_main_root.return_value = tmp_path
        mock_mission_type.return_value = "software-dev"

        # Create feature and worktree directories
        feature_dir = tmp_path / "kitty-specs" / "008-feature"
        feature_dir.mkdir(parents=True)
        worktree_path = lane_worktree_path(tmp_path, "008-feature")
        _mark_fake_worktree(worktree_path)

        # Simulate: main clean, worktree has uncommitted changes
        def subprocess_side_effect(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            cwd = kwargs.get("cwd", tmp_path)

            if "status" in cmd and "--porcelain" in cmd:
                if cwd == worktree_path:
                    return Mock(returncode=0, stdout=" M src/main.py\n")
                else:
                    return Mock(returncode=0, stdout="")  # Main repo clean
            elif "rev-parse" in cmd and "--abbrev-ref" in cmd:
                # Return a branch name so we don't trigger detached HEAD
                return Mock(returncode=0, stdout=f"{lane_branch_name('008-feature')}\n")
            elif "rev-parse" in cmd and "--show-toplevel" in cmd:
                return Mock(returncode=0, stdout=f"{worktree_path}\n")
            elif "rev-parse" in cmd and "--git-common-dir" in cmd:
                # tmp_path is not a real git repository in this fixture — the
                # lanes.json lock's git-topology probe (kernel.git_topology)
                # must see a real "not a git repository" failure so it takes
                # its non-git lock fallback path instead of raising.
                return Mock(
                    returncode=128,
                    stdout="",
                    stderr="fatal: not a git repository (or any of the parent directories): .git\n",
                )
            elif "rev-parse" in cmd and "--verify" in cmd:
                # No in-progress operations (MERGE_HEAD, REBASE_HEAD, etc. don't exist)
                return Mock(returncode=1, stdout="")
            elif "rev-list" in cmd:
                cmd_str = " ".join(cmd)
                if "HEAD.." in cmd_str:
                    # Behind-base check (HEAD..branch) — not behind
                    return Mock(returncode=0, stdout="0\n")
                else:
                    # Forward-count (branch..HEAD) — has implementation commits
                    return Mock(returncode=0, stdout="5\n")
            return Mock(returncode=0, stdout="")

        mock_run.side_effect = subprocess_side_effect

        # write_single_lane_manifest locks lanes.json via the same
        # kernel.git_topology probe _validate_ready_for_review uses below, so
        # it must run only after subprocess_side_effect is wired up (#5408
        # landing: it previously ran before mock_run.side_effect was set,
        # hitting the unconfigured default MagicMock and raising
        # GitTopologyUnavailableError instead of exercising the intended
        # uncommitted-worktree assertion).
        write_single_lane_manifest(feature_dir, wp_ids=("WP01",), predicted_surfaces=("review",))

        is_valid, guidance = _validate_ready_for_review(tmp_path, "008-feature", "WP01", force=False)

        assert is_valid is False
        guidance_text = "\n".join(guidance)
        assert "uncommitted" in guidance_text.lower()
        assert "worktree" in guidance_text.lower()
        assert "spec-kitty safe-commit" in guidance_text

    @patch("specify_cli.cli.commands.agent.tasks.get_main_repo_root")
    @patch("specify_cli.cli.commands.agent.tasks.get_mission_type")
    @patch("subprocess.run")
    @patch("specify_cli.core.git_ops.get_current_branch", return_value="kitty/mission-008-feature-lane-a")
    @patch("specify_cli.workspace.context.load_context", return_value=None)
    @patch("specify_cli.cli.commands.agent.tasks.get_feature_target_branch", return_value="main")
    def test_softwaredev_no_commits_blocks_review(
        self,
        mock_target: Mock,
        mock_ws: Mock,
        mock_branch: Mock,
        mock_run: Mock,
        mock_mission_type: Mock,
        mock_main_root: Mock,
        tmp_path: Path,
    ):
        """Should detect when worktree has no implementation commits."""
        from specify_cli.cli.commands.agent.tasks import _validate_ready_for_review

        # Setup mocks
        mock_main_root.return_value = tmp_path
        mock_mission_type.return_value = "software-dev"

        # Create feature and worktree directories
        feature_dir = tmp_path / "kitty-specs" / "008-feature"
        feature_dir.mkdir(parents=True)
        worktree_path = lane_worktree_path(tmp_path, "008-feature")
        _mark_fake_worktree(worktree_path)

        # Simulate: main clean, worktree clean, but no commits beyond main
        def subprocess_side_effect(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            kwargs.get("cwd", tmp_path)

            if "status" in cmd and "--porcelain" in cmd:
                return Mock(returncode=0, stdout="")  # Both clean
            elif "rev-parse" in cmd and "--abbrev-ref" in cmd:
                return Mock(returncode=0, stdout=f"{lane_branch_name('008-feature')}\n")
            elif "rev-parse" in cmd and "--show-toplevel" in cmd:
                return Mock(returncode=0, stdout=f"{worktree_path}\n")
            elif "rev-parse" in cmd and "--git-common-dir" in cmd:
                # tmp_path is not a real git repository in this fixture — the
                # lanes.json lock's git-topology probe (kernel.git_topology)
                # must see a real "not a git repository" failure so it takes
                # its non-git lock fallback path instead of raising.
                return Mock(
                    returncode=128,
                    stdout="",
                    stderr="fatal: not a git repository (or any of the parent directories): .git\n",
                )
            elif "rev-parse" in cmd and "--verify" in cmd:
                # No in-progress operations
                return Mock(returncode=1, stdout="")
            elif "rev-list" in cmd:
                return Mock(returncode=0, stdout="0\n")  # No commits beyond main
            return Mock(returncode=0, stdout="")

        mock_run.side_effect = subprocess_side_effect

        # write_single_lane_manifest locks lanes.json via the same
        # kernel.git_topology probe _validate_ready_for_review uses below, so
        # it must run only after subprocess_side_effect is wired up (#5408
        # landing: it previously ran before mock_run.side_effect was set,
        # hitting the unconfigured default MagicMock and raising
        # GitTopologyUnavailableError instead of exercising the intended
        # no-commits assertion).
        write_single_lane_manifest(feature_dir, wp_ids=("WP01",), predicted_surfaces=("review",))

        is_valid, guidance = _validate_ready_for_review(tmp_path, "008-feature", "WP01", force=False)

        assert is_valid is False
        guidance_text = "\n".join(guidance)
        assert "no implementation commits" in guidance_text.lower()

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
        mock_run.return_value = Mock(returncode=0, stdout=" M kitty-specs/008-research/tasks/WP01-task.md\n")

        is_valid, guidance = _validate_ready_for_review(tmp_path, "008-research", "WP01", force=False)

        # Should pass - WP status files are filtered out
        assert is_valid is True
        assert guidance == []


class TestMoveTaskPreflightCheck:
    """Test that move-task command blocks on uncommitted changes.

    Extracted from test_workflow_instructions.py during test-detection-remediation.
    """

    def test_validate_ready_for_review_blocks_on_uncommitted_worktree_changes(self, tmp_path):
        """Verify validation blocks when worktree has uncommitted changes."""
        from specify_cli.cli.commands.agent.tasks import _validate_ready_for_review

        mission_slug = "001-test-feature"
        feature_dir = tmp_path / "kitty-specs" / mission_slug
        feature_dir.mkdir(parents=True)
        write_single_lane_manifest(feature_dir, wp_ids=("WP01",), predicted_surfaces=("review",))

        (feature_dir / "meta.json").write_text('{"mission_type": "software-dev", "target_branch": "main"}')

        worktree_path = lane_worktree_path(tmp_path, mission_slug)
        _mark_fake_worktree(worktree_path)

        with patch("subprocess.run") as mock_run:

            def git_command_side_effect(args, **kwargs):
                if "branch" in args and "--show-current" in args:
                    return MagicMock(returncode=0, stdout=f"{lane_branch_name(mission_slug)}\n", stderr="")
                elif "status" in args and "--porcelain" in args and "kitty-specs" in str(args):
                    return MagicMock(returncode=0, stdout="", stderr="")
                elif "rev-parse" in args and "--abbrev-ref" in args:
                    return MagicMock(returncode=0, stdout=f"{lane_branch_name(mission_slug)}\n", stderr="")
                elif "rev-parse" in args and "--show-toplevel" in args:
                    return MagicMock(returncode=0, stdout=f"{worktree_path}\n", stderr="")
                elif "rev-parse" in args and "--verify" in args:
                    return MagicMock(returncode=1, stdout="", stderr="")
                elif "rev-list" in args and "HEAD..main" in args:
                    return MagicMock(returncode=0, stdout="0\n", stderr="")
                elif "status" in args and "--porcelain" in args:
                    return MagicMock(returncode=0, stdout="M  src/test.py\n?? test_new.py\n", stderr="")
                elif "rev-list" in args and "main..HEAD" in args:
                    return MagicMock(returncode=0, stdout="2\n", stderr="")
                else:
                    return MagicMock(returncode=0, stdout="", stderr="")

            mock_run.side_effect = git_command_side_effect

            is_valid, guidance = _validate_ready_for_review(tmp_path, mission_slug, "WP01", False)

            assert is_valid is False, "Expected validation to fail"
            assert len(guidance) > 0, "Expected guidance messages"
            assert any(
                any(keyword in line.lower() for keyword in ["uncommitted", "staged", "unstaged"]) for line in guidance
            ), f"No uncommitted/staged message in: {guidance}"
            assert any("<deliverable-path-1> <deliverable-path-2>" in line for line in guidance), (
                f"No explicit staging guidance in: {guidance}"
            )
            assert any("spec-kitty safe-commit" in line for line in guidance), f"No 'spec-kitty safe-commit' in: {guidance}"

    def test_validate_ready_for_review_allows_clean_worktree(self, tmp_path):
        """Verify validation passes when worktree is clean."""
        from specify_cli.cli.commands.agent.tasks import _validate_ready_for_review

        mission_slug = "001-test-feature"
        feature_dir = tmp_path / "kitty-specs" / mission_slug
        feature_dir.mkdir(parents=True)
        write_single_lane_manifest(feature_dir, wp_ids=("WP01",), predicted_surfaces=("review",))

        (feature_dir / "meta.json").write_text('{"mission_type": "software-dev", "target_branch": "main"}')

        worktree_path = lane_worktree_path(tmp_path, mission_slug)
        _mark_fake_worktree(worktree_path)

        with patch("subprocess.run") as mock_run:

            def git_command_side_effect(args, **kwargs):
                if "branch" in args and "--show-current" in args:
                    return MagicMock(returncode=0, stdout=f"{lane_branch_name(mission_slug)}\n", stderr="")
                elif "status" in args and "--porcelain" in args and "kitty-specs" in str(args):
                    return MagicMock(returncode=0, stdout="", stderr="")
                elif "rev-parse" in args and "--abbrev-ref" in args:
                    return MagicMock(returncode=0, stdout=f"{lane_branch_name(mission_slug)}\n", stderr="")
                elif "rev-parse" in args and "--show-toplevel" in args:
                    return MagicMock(returncode=0, stdout=f"{worktree_path}\n", stderr="")
                elif "rev-parse" in args and "--verify" in args:
                    return MagicMock(returncode=1, stdout="", stderr="")
                elif "rev-list" in args and "HEAD..main" in args:
                    return MagicMock(returncode=0, stdout="0\n", stderr="")
                elif "status" in args and "--porcelain" in args:
                    return MagicMock(returncode=0, stdout="", stderr="")
                elif "rev-list" in args and "main..HEAD" in args:
                    return MagicMock(returncode=0, stdout="5\n", stderr="")
                else:
                    return MagicMock(returncode=0, stdout="", stderr="")

            mock_run.side_effect = git_command_side_effect

            is_valid, guidance = _validate_ready_for_review(tmp_path, mission_slug, "WP01", False)

            assert is_valid is True
            assert len(guidance) == 0

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
