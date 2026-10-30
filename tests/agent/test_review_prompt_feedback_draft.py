"""#6632: the review prompt must describe what the rejection command does.

The prompt used to advertise the reviewer's feedback file as "in-repo, committed with the project" and
to promise that "The Python script handles all file updates automatically". Neither was true: the
rejection committed only the derived ``review-cycle-N.md`` and left the advertised file untracked,
which then blocked the work package's next ``move-task --to for_review``. #3430 already showed what a
prompt that promises something the command does not do costs: a whole review cycle.

This pins the rendered text (not the source literals): one assertion per claim the prompt must stop
making, plus the replacement claim it must make, and the advertised path still coming from the
owning helper.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.cli.commands.agent import workflow_executor
from specify_cli.review.cycle import review_feedback_source_path
from specify_cli.task_utils import WorkPackage
from specify_cli.workspace.context import ResolvedWorkspace

pytestmark = [pytest.mark.unit]

_MISSION_SLUG = "001-prompt-wording"
_WP_SLUG = "WP01-core"


def _work_package(repo: Path) -> WorkPackage:
    path = repo / "kitty-specs" / _MISSION_SLUG / "tasks" / f"{_WP_SLUG}.md"
    path.parent.mkdir(parents=True)
    path.write_text("---\nwork_package_id: WP01\n---\n\n# WP01\n", encoding="utf-8")
    return WorkPackage(
        feature=_MISSION_SLUG,
        path=path,
        current_lane="for_review",
        relative_subpath=Path("tasks") / f"{_WP_SLUG}.md",
        frontmatter="---\nwork_package_id: WP01\n---\n",
        body="# WP01\n",
        padding="",
    )


def _workspace(repo: Path) -> ResolvedWorkspace:
    return ResolvedWorkspace(
        mission_slug=_MISSION_SLUG,
        wp_id="WP01",
        execution_mode="worktree",
        mode_source="test",
        resolution_kind="lane",
        workspace_name="lane-a",
        worktree_path=repo / ".worktrees" / "lane-a",
        branch_name="kitty/mission-001-prompt-wording-lane-a",
        lane_id="lane-a",
        lane_wp_ids=["WP01"],
    )


def _render_prompt(repo: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """Render the real ``REVIEW: <WP>`` prompt body.

    Only the environment lookups that need a populated Mission (charter context, baseline-test cache,
    reviewer identity) are stubbed: the assertions below are about the prompt's wording, which is the
    production renderer's own output.
    """
    monkeypatch.setattr(workflow_executor, "render_charter_context_text", lambda *_a, **_k: "")
    monkeypatch.setattr(workflow_executor, "_review_baseline_context_lines", lambda **_k: [])
    monkeypatch.setattr(workflow_executor, "resolve_review_completion_reviewer", lambda **_k: "reviewer")
    monkeypatch.setattr(workflow_executor, "shared_artifact_guidance", lambda *_a, **_k: [])

    wp = _work_package(repo)
    feedback_path = review_feedback_source_path(wp.path.parent.parent / "tasks" / _WP_SLUG, 1)
    lines = workflow_executor.build_review_prompt_lines(
        normalized_wp_id="WP01",
        wp=wp,
        workspace=_workspace(repo),
        workspace_path=repo / ".worktrees" / "lane-a",
        review_agent_assignment=None,
        repo_root=repo,
        mission_slug=_MISSION_SLUG,
        target_branch="issue-6632-prompt",
        dependents_warning=[],
        review_ctx={"base_branch": "unknown", "branch_name": "b", "commit_count": 0},
        main_repo_root=repo,
        review_feedback_path=feedback_path,
    )
    return "\n".join(lines)


def test_review_prompt_drops_the_committed_with_the_project_claim(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The draft is not committed with the project — the record is."""
    prompt = _render_prompt(tmp_path, monkeypatch)

    assert "committed with the project" not in prompt
    assert "review-cycle-N.md" in prompt, "the prompt must name the record that keeps the reviewer's text"
    assert "removes" in prompt, "the prompt must say the rejection command removes the draft once recorded"


def test_review_prompt_drops_the_handles_everything_claim(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The script does not handle every file update; it records and retires this one."""
    prompt = _render_prompt(tmp_path, monkeypatch)

    assert "handles all file updates automatically" not in prompt


def test_review_prompt_still_advertises_the_helper_owned_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The advertised draft path is unchanged — it still comes from the owning helper."""
    prompt = _render_prompt(tmp_path, monkeypatch)
    expected = str(review_feedback_source_path(tmp_path / "kitty-specs" / _MISSION_SLUG / "tasks" / _WP_SLUG, 1))

    assert expected in prompt
    assert "review-feedback-1.md" in prompt
