"""Regression tests for agent wrapper delegation into top-level commands."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.mission import app
from specify_cli.cli.commands.agent import workflow
from specify_cli.cli.commands.consolidate import ConsolidateOptions
from specify_cli.consolidation.config import MergeStrategy
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.store import append_event

pytestmark = pytest.mark.fast

runner = CliRunner()


def _workspace(exists: bool) -> SimpleNamespace:
    return SimpleNamespace(
        exists=exists,
        # #1833 husk guard reads is_husk before the exists check.
        is_husk=False,
        worktree_path=Path("/nonexistent/spec-kitty-test-worktree"),
        resolution_kind="repo_root",
        # #5100: ResolvedWorkspace.status_execution_mode, read by the review
        # claim/gate resolver alongside resolution_kind.
        status_execution_mode="direct_repo",
    )


def _scaffold_implement_mission(repo_root: Path, mission_slug: str, wp_id: str = "WP01") -> Path:
    feature_dir = repo_root / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")
    (feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    (feature_dir / "tasks.md").write_text(f"## {wp_id}\n", encoding="utf-8")
    wp_path = tasks_dir / f"{wp_id}-test.md"
    wp_path.write_text(
        "---\n"
        f"work_package_id: {wp_id}\n"
        "subtasks: [T001]\n"
        "title: Test WP\n"
        "dependencies: []\n"
        "execution_mode: code_change\n"
        "owned_files:\n  - src/**\n"
        "authoritative_surface: src/\n"
        "---\n"
        "# Test WP\n",
        encoding="utf-8",
    )
    append_event(
        feature_dir,
        StatusEvent(
            event_id=f"test-{wp_id}-planned",
            mission_slug=mission_slug,
            wp_id=wp_id,
            from_lane=Lane.PLANNED,
            to_lane=Lane.PLANNED,
            at="2026-01-01T00:00:00+00:00",
            actor="test",
            force=True,
            execution_mode="worktree",
        ),
    )
    return wp_path


@patch("specify_cli.cli.commands.agent.mission.top_level_accept")
def test_agent_mission_accept_passes_explicit_feature_none(
    mock_top_level_accept: MagicMock,
) -> None:
    """Wrapper must pass explicit values for hidden Typer params.

    Without ``feature=None``, the delegated top-level command receives Typer's
    ``OptionInfo`` sentinel and selector resolution crashes before acceptance.
    """

    result = runner.invoke(
        app,
        ["accept", "--mission", "077-mission-terminology-cleanup", "--json"],
    )

    assert result.exit_code == 0, result.output
    mock_top_level_accept.assert_called_once_with(
        mission="077-mission-terminology-cleanup",
        mode="auto",
        actor=None,
        test=[],
        json_output=True,
        lenient=False,
        no_commit=False,
        diagnose=False,
        allow_fail=False,
        merge_commit=None,  # #4231: PR-merge evidence passthrough
        target_branch=None,  # #4231: PR base branch passthrough
        attest_first_landing=False,  # #4231: anchor attestation passthrough
    )


@patch("specify_cli.cli.commands.agent.mission.top_level_accept")
def test_agent_mission_accept_passes_diagnose_flag(
    mock_top_level_accept: MagicMock,
) -> None:
    result = runner.invoke(
        app,
        ["accept", "--mission", "077-mission-terminology-cleanup", "--diagnose", "--json"],
    )

    assert result.exit_code == 0, result.output
    mock_top_level_accept.assert_called_once_with(
        mission="077-mission-terminology-cleanup",
        mode="auto",
        actor=None,
        test=[],
        json_output=True,
        lenient=False,
        no_commit=False,
        diagnose=True,
        allow_fail=False,
        merge_commit=None,  # #4231: PR-merge evidence passthrough
        target_branch=None,  # #4231: PR base branch passthrough
        attest_first_landing=False,  # #4231: anchor attestation passthrough
    )


@patch("specify_cli.cli.commands.consolidate.run_consolidate")
@patch("specify_cli.core.context_validation.get_current_context")
@patch("specify_cli.cli.commands.agent.mission.get_feature_target_branch")
@patch("specify_cli.cli.commands.agent.mission.locate_project_root")
def test_agent_mission_merge_reaches_consolidate_with_real_option_values(
    mock_locate_project_root: MagicMock,
    mock_get_feature_target_branch: MagicMock,
    mock_get_current_context: MagicMock,
    mock_run_consolidate: MagicMock,
    tmp_path: Path,
) -> None:
    """The real Typer ``consolidate`` must receive real values, never ``OptionInfo``.

    The wrapper delegates to the Typer command as a plain function call, so every
    option it does not pass would arrive as an unresolved ``typer.OptionInfo``
    sentinel (#3457) and ``--skip-review-artifact-check``'s note guard would die
    with ``AttributeError: 'OptionInfo' object has no attribute 'strip'``. This
    runs the real command (only its body, ``run_consolidate``, is intercepted) and
    pins the options it hands over: the mapped values plus every other option at
    its real default.
    The unset keep/delete choices stay ``None`` so the top-level retention gate
    sees that the caller made no choice.
    """
    from specify_cli.core.context_validation import ExecutionContext

    mock_locate_project_root.return_value = tmp_path
    mock_get_feature_target_branch.return_value = "main"
    mock_get_current_context.return_value = SimpleNamespace(location=ExecutionContext.MAIN_REPO)

    result = runner.invoke(
        app,
        ["merge", "--mission", "077-mission-terminology-cleanup", "--dry-run"],
    )

    assert result.exit_code == 0, result.output
    mock_run_consolidate.assert_called_once_with(
        ConsolidateOptions(
            strategy=MergeStrategy.MERGE,
            target_branch="main",
            dry_run=True,
            mission="077-mission-terminology-cleanup",
        )
    )


@patch("specify_cli.cli.commands.agent.workflow.top_level_implement")
@patch("specify_cli.cli.commands.agent.workflow.resolve_workspace_for_wp")
@patch("specify_cli.cli.commands.agent.workflow.locate_work_package")
@patch("specify_cli.cli.commands.agent.workflow._require_current_analysis_report")
@patch("specify_cli.cli.commands.agent.workflow._ensure_target_branch_checked_out")
@patch("specify_cli.cli.commands.agent.workflow.get_main_repo_root")
@patch("specify_cli.cli.commands.agent.workflow.locate_project_root")
@patch("specify_cli.cli.commands.agent.workflow._find_mission_slug")
@patch("specify_cli.cli.commands.agent.workflow.is_worktree_context", return_value=False)
def test_agent_action_implement_passes_acknowledge_default_false(
    mock_is_worktree_context: MagicMock,
    mock_find_mission_slug: MagicMock,
    mock_locate_project_root: MagicMock,
    mock_get_main_repo_root: MagicMock,
    mock_ensure_target_branch_checked_out: MagicMock,
    mock_require_current_analysis_report: MagicMock,
    mock_locate_work_package: MagicMock,
    mock_resolve_workspace_for_wp: MagicMock,
    mock_top_level_implement: MagicMock,
    tmp_path: Path,
) -> None:
    """Wrapper must forward the default acknowledgement value explicitly.

    ``is_worktree_context`` is patched to ``False`` so this test is invariant
    to the CWD — it may run inside a worktree during development without the
    workspace-creation guard firing before delegation.
    """

    mock_find_mission_slug.return_value = "demo-mission"
    mock_locate_project_root.return_value = tmp_path
    mock_get_main_repo_root.return_value = tmp_path
    mock_ensure_target_branch_checked_out.return_value = (tmp_path, "main")
    wp_path = _scaffold_implement_mission(tmp_path, "demo-mission")
    mock_locate_work_package.return_value = SimpleNamespace(path=wp_path)
    mock_require_current_analysis_report.return_value = None
    mock_resolve_workspace_for_wp.return_value = _workspace(exists=False)
    mock_top_level_implement.side_effect = RuntimeError("stop after delegation")

    with pytest.raises(typer.Exit) as exc_info:
        workflow.implement(wp_id="WP01", mission="demo-mission", agent="claude")

    assert exc_info.value.exit_code == 1
    mock_top_level_implement.assert_called_once_with(
        wp_id="WP01",
        mission="demo-mission",
        json_output=False,
        recover=False,
        acknowledge_not_bulk_edit=False,
        actor="claude",
    )


@patch("specify_cli.cli.commands.agent.workflow.top_level_implement")
@patch("specify_cli.cli.commands.agent.workflow.resolve_workspace_for_wp")
@patch("specify_cli.cli.commands.agent.workflow.locate_work_package")
@patch("specify_cli.cli.commands.agent.workflow._require_current_analysis_report")
@patch("specify_cli.cli.commands.agent.workflow._ensure_target_branch_checked_out")
@patch("specify_cli.cli.commands.agent.workflow.get_main_repo_root")
@patch("specify_cli.cli.commands.agent.workflow.locate_project_root")
@patch("specify_cli.cli.commands.agent.workflow._find_mission_slug")
@patch("specify_cli.cli.commands.agent.workflow.is_worktree_context", return_value=False)
def test_agent_action_implement_passes_acknowledge_true_when_requested(
    mock_is_worktree_context: MagicMock,
    mock_find_mission_slug: MagicMock,
    mock_locate_project_root: MagicMock,
    mock_get_main_repo_root: MagicMock,
    mock_ensure_target_branch_checked_out: MagicMock,
    mock_require_current_analysis_report: MagicMock,
    mock_locate_work_package: MagicMock,
    mock_resolve_workspace_for_wp: MagicMock,
    mock_top_level_implement: MagicMock,
    tmp_path: Path,
) -> None:
    """Wrapper must forward the explicit acknowledgement override.

    ``is_worktree_context`` is patched to ``False`` so this test is invariant
    to the CWD — it may run inside a worktree during development without the
    workspace-creation guard firing before delegation.
    """

    mock_find_mission_slug.return_value = "demo-mission"
    mock_locate_project_root.return_value = tmp_path
    mock_get_main_repo_root.return_value = tmp_path
    mock_ensure_target_branch_checked_out.return_value = (tmp_path, "main")
    wp_path = _scaffold_implement_mission(tmp_path, "demo-mission")
    mock_locate_work_package.return_value = SimpleNamespace(path=wp_path)
    mock_require_current_analysis_report.return_value = None
    mock_resolve_workspace_for_wp.return_value = _workspace(exists=False)
    mock_top_level_implement.side_effect = RuntimeError("stop after delegation")

    with pytest.raises(typer.Exit) as exc_info:
        workflow.implement(
            wp_id="WP01",
            mission="demo-mission",
            agent="claude",
            acknowledge_not_bulk_edit=True,
        )

    assert exc_info.value.exit_code == 1
    mock_top_level_implement.assert_called_once_with(
        wp_id="WP01",
        mission="demo-mission",
        json_output=False,
        recover=False,
        acknowledge_not_bulk_edit=True,
        actor="claude",
    )
