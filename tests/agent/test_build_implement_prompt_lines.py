"""T011 (#5024, WP02): direct coverage for ``build_implement_prompt_lines``.

FR-005 positive control (SC-003 success path + SC-005 render assertion):
``build_implement_prompt_lines`` (``workflow_executor.py``) previously had NO
direct test -- it was only exercised indirectly through the full ``implement``
CLI flow. This module covers both branches directly: feedback-present (the
recorded reviewer text/reference must appear in the rendered lines) and
feedback-absent (no crash, no spurious feedback banner).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.cli.commands.agent.workflow_executor import build_implement_prompt_lines
from specify_cli.status import AgentAssignment
from specify_cli.task_utils import WorkPackage
from specify_cli.workspace.context import ResolvedWorkspace

pytestmark = pytest.mark.unit


def _wp(repo: Path, mission_slug: str) -> WorkPackage:
    wp_path = repo / "kitty-specs" / mission_slug / "tasks" / "WP01.md"
    wp_path.parent.mkdir(parents=True, exist_ok=True)
    wp_path.write_text("---\nwork_package_id: WP01\ntitle: Test Task\n---\n\n# WP01\n", encoding="utf-8")
    return WorkPackage(
        feature=mission_slug,
        path=wp_path,
        current_lane="in_progress",
        relative_subpath=Path("tasks/WP01.md"),
        frontmatter="",
        body="",
        padding="",
    )


def _workspace(repo: Path, mission_slug: str) -> ResolvedWorkspace:
    return ResolvedWorkspace(
        mission_slug=mission_slug,
        wp_id="WP01",
        execution_mode="code_change",
        mode_source="lane",
        resolution_kind="lane_workspace",
        workspace_name=f"{mission_slug}-lane-a",
        worktree_path=repo / ".worktrees" / f"{mission_slug}-lane-a",
        branch_name=f"kitty/mission-{mission_slug}-lane-a",
        lane_id="lane-a",
        lane_wp_ids=["WP01"],
    )


def _agent_assignment() -> AgentAssignment:
    return AgentAssignment(tool="claude", model="claude-opus", profile_id=None, role=None)


def test_feedback_present_renders_reference_and_read_instruction(tmp_path: Path) -> None:
    """(a) feedback-present: the canonical feedback reference and the exact
    ``cat`` instruction pointing at the resolved artifact must both appear in
    the produced prompt lines."""
    repo = tmp_path / "repo"
    repo.mkdir()
    mission_slug = "001-test-mission"
    feedback_file = tmp_path / "review-cycle-2.md"
    feedback_file.write_text("**Issue**: fix the off-by-one\n", encoding="utf-8")
    pointer = f"review-cycle://{mission_slug}/WP01/review-cycle-2.md"

    lines = build_implement_prompt_lines(
        normalized_wp_id="WP01",
        wp=_wp(repo, mission_slug),
        workspace=_workspace(repo, mission_slug),
        workspace_path=repo / ".worktrees" / f"{mission_slug}-lane-a",
        wp_agent_assignment=_agent_assignment(),
        repo_root=repo,
        mission_slug=mission_slug,
        target_branch="main",
        subtask_cmd="T001",
        has_feedback=True,
        review_feedback_ref=pointer,
        review_feedback_file=feedback_file,
        mission_type="software-dev",
        deliverables_path=None,
    )

    text = "\n".join(lines)
    assert "IMPLEMENT: WP01" in text
    assert "⚠️  This work package has review feedback." in text
    assert f"Canonical feedback reference: {pointer}" in text
    assert f'Read it first: cat "{feedback_file}"' in text


def test_feedback_absent_renders_no_crash_no_spurious_feedback(tmp_path: Path) -> None:
    """(b) feedback-absent: no crash, and no feedback banner is spuriously
    rendered when ``has_feedback`` is ``False``."""
    repo = tmp_path / "repo"
    repo.mkdir()
    mission_slug = "001-test-mission"

    lines = build_implement_prompt_lines(
        normalized_wp_id="WP01",
        wp=_wp(repo, mission_slug),
        workspace=_workspace(repo, mission_slug),
        workspace_path=repo / ".worktrees" / f"{mission_slug}-lane-a",
        wp_agent_assignment=_agent_assignment(),
        repo_root=repo,
        mission_slug=mission_slug,
        target_branch="main",
        subtask_cmd="T001",
        has_feedback=False,
        review_feedback_ref=None,
        review_feedback_file=None,
        mission_type="software-dev",
        deliverables_path=None,
    )

    text = "\n".join(lines)
    assert "IMPLEMENT: WP01" in text
    assert "review feedback" not in text.lower()


def test_implement_footer_recipe_names_lane_branch_not_target_branch(tmp_path: Path) -> None:
    """The printed commit recipe in the
    "WHEN YOU'RE DONE" footer must name ``--to-branch`` with the LANE branch
    (``workspace.branch_name``), never the mission's merge ``target_branch`` --
    naming the wrong one prints a recipe safe-commit's own HEAD-match guard
    then refuses to run. ``target_branch`` ("main") and ``workspace.branch_name``
    ("kitty/mission-001-test-mission-lane-a") are deliberately distinct here so
    a regression that reverts the site back to ``target_branch`` fails this
    assertion.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    mission_slug = "001-test-mission"
    workspace = _workspace(repo, mission_slug)

    lines = build_implement_prompt_lines(
        normalized_wp_id="WP01",
        wp=_wp(repo, mission_slug),
        workspace=workspace,
        workspace_path=repo / ".worktrees" / f"{mission_slug}-lane-a",
        wp_agent_assignment=_agent_assignment(),
        repo_root=repo,
        mission_slug=mission_slug,
        target_branch="main",
        subtask_cmd="T001",
        has_feedback=False,
        review_feedback_ref=None,
        review_feedback_file=None,
        mission_type="software-dev",
        deliverables_path=None,
    )

    text = "\n".join(lines)
    assert f"--to-branch {workspace.branch_name}" in text
    assert workspace.branch_name != "main"
    assert "--to-branch main" not in text
