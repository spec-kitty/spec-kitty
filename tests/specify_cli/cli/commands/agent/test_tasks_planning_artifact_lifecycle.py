"""Planning-artifact lifecycle tests for WP03."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.tasks import app
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.task_utils import WorkPackage
from tests._support.status_seed import seed_status_event

pytestmark = pytest.mark.fast

runner = CliRunner()


def _build_wp(tmp_path: Path, mission_slug: str, wp_id: str, execution_mode: str) -> tuple[Path, Path]:
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / ".kittify").mkdir(exist_ok=True)

    wp_file = tasks_dir / f"{wp_id}-test.md"
    wp_file.write_text(
        f"---\n"
        f"work_package_id: {wp_id}\n"
        f"title: Test {wp_id}\n"
        f"execution_mode: {execution_mode}\n"
        f"owned_files:\n  - src/{wp_id.lower()}/**\n"
        f"authoritative_surface: src/{wp_id.lower()}/\n"
        f"agent: testbot\n"
        f"---\n\n# {wp_id}\n\n## Activity Log\n",
        encoding="utf-8",
    )
    return feature_dir, wp_file


def _seed_event(feature_dir: Path, mission_slug: str, wp_id: str, from_lane: Lane, to_lane: Lane, execution_mode: str) -> None:
    seed_status_event(
        feature_dir,
        StatusEvent(
            event_id=f"{wp_id}-{to_lane}",
            mission_slug=mission_slug,
            wp_id=wp_id,
            from_lane=from_lane,
            to_lane=to_lane,
            at="2026-01-01T00:00:00+00:00",
            actor="test",
            force=False,
            execution_mode=execution_mode,
        ),
    )


def _make_wp_record(mission_slug: str, wp_file: Path, current_lane: str, execution_mode: str) -> WorkPackage:
    return WorkPackage(
        feature=mission_slug,
        path=wp_file,
        current_lane=current_lane,
        relative_subpath=Path(f"tasks/{wp_file.name}"),
        frontmatter=(
            f"work_package_id: {wp_file.stem.split('-')[0]}\n"
            f"title: Test {wp_file.stem.split('-')[0]}\n"
            f"execution_mode: {execution_mode}\n"
            f"lane: {current_lane}\n"
            "agent: testbot\n"
        ),
        body=f"\n# {wp_file.stem.split('-')[0]}\n\n## Activity Log\n",
        padding="",
    )


class TestPlanningArtifactLifecycle:
    @patch("specify_cli.cli.commands.agent.tasks.emit_status_transition_transactional")
    @patch("specify_cli.cli.commands.agent.tasks.feature_status_lock")
    @patch("specify_cli.cli.commands.agent.tasks._validate_ready_for_review")
    @patch("specify_cli.cli.commands.agent.tasks._check_unchecked_subtasks")
    @patch("specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out")
    @patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
    @patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
    @patch("specify_cli.cli.commands.agent.tasks.locate_work_package")
    def test_planning_artifact_can_move_to_approved(
        self,
        mock_locate_wp: MagicMock,
        mock_slug: MagicMock,
        mock_root: MagicMock,
        mock_branch: MagicMock,
        mock_unchecked: MagicMock,
        mock_review_valid: MagicMock,
        mock_lock: MagicMock,
        mock_emit: MagicMock,
        tmp_path: Path,
    ) -> None:
        mission_slug = "078-planning-approved"
        feature_dir, wp_file = _build_wp(tmp_path, mission_slug, "WP03", "planning_artifact")
        _seed_event(feature_dir, mission_slug, "WP03", Lane.PLANNED, Lane.FOR_REVIEW, "direct_repo")

        mock_root.return_value = tmp_path
        mock_slug.return_value = mission_slug
        mock_branch.return_value = (tmp_path, "main")
        mock_unchecked.return_value = []
        mock_review_valid.return_value = (True, [])
        mock_lock.return_value.__enter__ = MagicMock()
        mock_lock.return_value.__exit__ = MagicMock(return_value=False)
        mock_locate_wp.return_value = _make_wp_record(mission_slug, wp_file, "for_review", "planning_artifact")
        mock_emit.return_value = MagicMock(to_lane=Lane.APPROVED)

        result = runner.invoke(
            app,
            [
                "move-task",
                "WP03",
                "--to",
                "approved",
                "--agent",
                "testbot",
                "--mission",
                mission_slug,
                "--json",
                "--no-auto-commit",
            ],
        )

        assert result.exit_code == 0, f"CLI error: {result.output}"

    @patch("specify_cli.cli.commands.agent.tasks._wp_branch_merged_into_target")
    @patch("specify_cli.cli.commands.agent.tasks.emit_status_transition_transactional")
    @patch("specify_cli.cli.commands.agent.tasks.feature_status_lock")
    @patch("specify_cli.cli.commands.agent.tasks._validate_ready_for_review")
    @patch("specify_cli.cli.commands.agent.tasks._check_unchecked_subtasks")
    @patch("specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out")
    @patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
    @patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
    @patch("specify_cli.cli.commands.agent.tasks.locate_work_package")
    def test_planning_artifact_done_bypasses_merge_ancestry(
        self,
        mock_locate_wp: MagicMock,
        mock_slug: MagicMock,
        mock_root: MagicMock,
        mock_branch: MagicMock,
        mock_unchecked: MagicMock,
        mock_review_valid: MagicMock,
        mock_lock: MagicMock,
        mock_emit: MagicMock,
        mock_merge_check: MagicMock,
        tmp_path: Path,
    ) -> None:
        mission_slug = "078-planning-done"
        feature_dir, wp_file = _build_wp(tmp_path, mission_slug, "WP03", "planning_artifact")
        _seed_event(feature_dir, mission_slug, "WP03", Lane.FOR_REVIEW, Lane.APPROVED, "direct_repo")

        mock_root.return_value = tmp_path
        mock_slug.return_value = mission_slug
        mock_branch.return_value = (tmp_path, "main")
        mock_unchecked.return_value = []
        mock_review_valid.return_value = (True, [])
        mock_lock.return_value.__enter__ = MagicMock()
        mock_lock.return_value.__exit__ = MagicMock(return_value=False)
        mock_locate_wp.return_value = _make_wp_record(mission_slug, wp_file, "approved", "planning_artifact")
        mock_emit.return_value = MagicMock(to_lane=Lane.DONE)

        result = runner.invoke(
            app,
            [
                "move-task",
                "WP03",
                "--to",
                "done",
                "--agent",
                "testbot",
                "--mission",
                mission_slug,
                "--json",
                "--no-auto-commit",
            ],
        )

        assert result.exit_code == 0, f"CLI error: {result.output}"
        mock_merge_check.assert_not_called()

    @patch("specify_cli.cli.commands.agent.tasks.resolve_workspace_for_wp")
    @patch("specify_cli.cli.commands.agent.tasks._wp_branch_merged_into_target")
    @patch("specify_cli.cli.commands.agent.tasks.feature_status_lock")
    @patch("specify_cli.cli.commands.agent.tasks._validate_ready_for_review")
    @patch("specify_cli.cli.commands.agent.tasks._check_unchecked_subtasks")
    @patch("specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out")
    @patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
    @patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
    @patch("specify_cli.cli.commands.agent.tasks.locate_work_package")
    def test_code_change_done_still_requires_merge_ancestry(
        self,
        mock_locate_wp: MagicMock,
        mock_slug: MagicMock,
        mock_root: MagicMock,
        mock_branch: MagicMock,
        mock_unchecked: MagicMock,
        mock_review_valid: MagicMock,
        mock_lock: MagicMock,
        mock_merge_check: MagicMock,
        mock_resolve_workspace: MagicMock,
        tmp_path: Path,
    ) -> None:
        mission_slug = "078-code-change-done"
        feature_dir, wp_file = _build_wp(tmp_path, mission_slug, "WP03", "code_change")
        _seed_event(feature_dir, mission_slug, "WP03", Lane.FOR_REVIEW, Lane.APPROVED, "worktree")

        mock_root.return_value = tmp_path
        mock_slug.return_value = mission_slug
        mock_branch.return_value = (tmp_path, "main")
        mock_unchecked.return_value = []
        mock_review_valid.return_value = (True, [])
        mock_lock.return_value.__enter__ = MagicMock()
        mock_lock.return_value.__exit__ = MagicMock(return_value=False)
        mock_locate_wp.return_value = _make_wp_record(mission_slug, wp_file, "approved", "code_change")
        mock_resolve_workspace.return_value = SimpleNamespace(
            execution_mode="code_change",
            worktree_path=tmp_path,
        )
        mock_merge_check.return_value = (False, "Merge ancestry check failed: lane branch is not merged into main.")

        result = runner.invoke(
            app,
            [
                "move-task",
                "WP03",
                "--to",
                "done",
                "--agent",
                "testbot",
                "--mission",
                mission_slug,
                "--json",
                "--no-auto-commit",
            ],
        )

        assert result.exit_code != 0
        assert "verified merge ancestry" in result.output
        mock_merge_check.assert_called_once()
