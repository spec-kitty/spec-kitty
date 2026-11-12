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
import shlex
import subprocess

import pytest

from specify_cli.cli.commands.agent import workflow_executor
from specify_cli.cli.commands.agent.workflow_executor import build_implement_prompt_lines
from specify_cli.review.lane_test_invocation import LANE_TEST_INVOCATION_HEADER
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


def _assert_subtask_context(text: str, mission_slug: str, subtask: str) -> None:
    recipes = [shlex.split(line.strip()) for line in text.splitlines() if line.strip().startswith("spec-kitty agent tasks mark-status ")]
    assert recipes
    for argv in recipes:
        assert subtask in argv
        assert argv[argv.index("--wp") + 1] == "WP01"
        assert argv[argv.index("--mission") + 1] == mission_slug
        assert argv[argv.index("--status") + 1] == "done"


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
        subtask_cmd="<subtask-ids>",
        has_feedback=False,
        review_feedback_ref=None,
        review_feedback_file=None,
        mission_type="software-dev",
        deliverables_path=None,
    )

    text = "\n".join(lines)
    assert "IMPLEMENT: WP01" in text
    assert "review feedback" not in text.lower()
    _assert_subtask_context(text, mission_slug, "<subtask-ids>")


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


# ---------------------------------------------------------------------------
# Lane test invocation block (mission lane-code-verification #7547, WP02, FR-005 / SC-003)
# ---------------------------------------------------------------------------


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True)


def _real_lane(repo: Path, mission_slug: str) -> Path:
    """A real git checkout at the lane path, with one tracked source-layout package."""
    lane = repo / ".worktrees" / f"{mission_slug}-lane-a"
    (lane / "src" / "pkg").mkdir(parents=True)
    (lane / "src" / "pkg" / "__init__.py").write_text("V = 1\n", encoding="utf-8")
    _git(lane, "init", "-q", "-b", "main")
    _git(lane, "add", "-A")
    _git(lane, "-c", "user.email=t@example.com", "-c", "user.name=T", "commit", "-q", "-m", "seed")
    return lane


def _implement_prompt(repo: Path, mission_slug: str, workspace: ResolvedWorkspace) -> str:
    lines = build_implement_prompt_lines(
        normalized_wp_id="WP01",
        wp=_wp(repo, mission_slug),
        workspace=workspace,
        workspace_path=workspace.worktree_path,
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
    return "\n".join(lines)


def test_implement_prompt_states_the_lane_test_invocation_and_probe(tmp_path: Path) -> None:
    """SC-003: the prompt names the lane, the declared command and the probe result, re-derived at render time."""
    repo = tmp_path / "repo"
    mission_slug = "001-test-mission"
    lane = _real_lane(repo, mission_slug)
    (repo / ".kittify").mkdir()
    (repo / ".kittify" / "config.yaml").write_text("review:\n  test_command: make test-fast\n", encoding="utf-8")

    text = _implement_prompt(repo, mission_slug, _workspace(repo, mission_slug))

    assert LANE_TEST_INVOCATION_HEADER in text
    assert f"   cd {lane}" in text
    assert "   unset PYTHONPATH UV_PROJECT_ENVIRONMENT VIRTUAL_ENV" in text
    assert f"   export PYTHONPATH={lane / 'src'}" in text
    assert "   export SPEC_KITTY_TEST_DB_NAME=test_001_test_mission_lane_a" in text
    assert "   make test-fast" in text
    assert "   probe: verified — pkg → src/pkg/__init__.py" in text


def test_implement_prompt_for_planning_artifact_work_has_no_invocation_block(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    mission_slug = "001-test-mission"
    workspace = ResolvedWorkspace(
        mission_slug=mission_slug,
        wp_id="WP01",
        execution_mode="planning_artifact",
        mode_source="frontmatter",
        resolution_kind="repo_root",
        workspace_name=f"{mission_slug}-lane-planning",
        worktree_path=repo,
        branch_name=None,
        lane_id="lane-planning",
        lane_wp_ids=["WP01"],
    )

    text = _implement_prompt(repo, mission_slug, workspace)

    assert LANE_TEST_INVOCATION_HEADER not in text


def test_implement_prompt_survives_an_adapter_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail-open, like the topology block: an adapter error renders as an unverified probe."""
    repo = tmp_path / "repo"
    repo.mkdir()
    mission_slug = "001-test-mission"

    def boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("config exploded")

    monkeypatch.setattr(workflow_executor, "workspace_lane_test_invocation", boom)

    text = _implement_prompt(repo, mission_slug, _workspace(repo, mission_slug))

    assert LANE_TEST_INVOCATION_HEADER in text
    assert "   probe: unverified — could not build the lane test invocation: config exploded" in text
    assert "IMPLEMENTATION COMPLETE?" in text
