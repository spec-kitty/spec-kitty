"""One neutral MoveTaskRequest factory for transition and recipe tests."""

from dataclasses import replace
from typing import Any

from specify_cli.cli.commands.agent.tasks_transition_core import MoveTaskRequest


def base_request(**overrides: Any) -> MoveTaskRequest:
    """A passing in-progress -> review request, perturbed only by the caller."""
    req = MoveTaskRequest(
        task_id="WP01",
        target_lane="for_review",
        old_lane="in_progress",
        force=False,
        agent=None,
        current_agent=None,
        note=None,
        auto_commit=False,
        target_branch="feature/work",
        skip_target_branch_commit=False,
        tracker_ref_values=(),
        assignee=None,
        shell_pid=None,
        self_review_fallback=False,
        intended_reviewer=None,
        reviewer_failure_reason=None,
        protected_error=None,
        review_verdict=None,
        review_artifact_name=None,
        skip_review_artifact_check=False,
        feedback_provided=False,
        feedback_source=None,
        feedback_exists=False,
        feedback_is_file=False,
        feedback_content=None,
        unchecked_subtasks=(),
        review_ready=True,
        review_guidance=(),
        done_execution_mode=None,
        done_merged=False,
        done_merge_msg="",
        done_override_reason=None,
        issue_matrix_blocker=None,
        is_arbiter_override=False,
        effective_reviewer=None,
        effective_approval_ref=None,
    )
    return replace(req, **overrides)
