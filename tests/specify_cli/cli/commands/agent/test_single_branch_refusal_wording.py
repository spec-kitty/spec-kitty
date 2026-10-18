"""The single_branch move-side refusal names the missing implementation commit (#6369, scenario 6).

``_mt_require_single_branch_implementation`` (#5939) refuses a review-ward move of a
plain single_branch work package with no committed implementation. It runs before
``lanes/for_review_gate.py``, so its wording is what an operator (and the
``single-branch.feature`` scenario) reads; it says "no implementation commit" like
``for_review_gate`` and the consolidate axis. The code is pinned with the phrase because
the non-owned ``move-task --json`` envelope carries the message only.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mission_runtime import ActionContextError
from specify_cli.cli.commands.agent import tasks_move_task as move_task_module
from specify_cli.core.vcs import git as vcs_git
from specify_cli.lanes import persistence, single_branch_landing
from specify_cli.status.models import Lane

pytestmark = [pytest.mark.unit]

_WINDOW = ("plan0000", "mission-branch")


def _state(target_lane: Lane) -> move_task_module._MoveTaskState:
    """An unforced, non-owned move of WP01 out of ``in_progress``."""
    return move_task_module._MoveTaskState(
        task_id="WP01",
        to=target_lane.value,
        mission="sb",
        agent="claude",
        assignee=None,
        shell_pid=None,
        note=None,
        review_feedback_file=None,
        approval_ref=None,
        reviewer=None,
        self_review_fallback=False,
        intended_reviewer=None,
        reviewer_failure_reason=None,
        done_override_reason=None,
        force=False,
        tracker_ref=None,
        skip_review_artifact_check=False,
        auto_commit=None,
        json_output=True,
        target_lane=target_lane,
        feature_dir=Path("kitty-specs/sb"),
        old_lane=Lane.IN_PROGRESS,
    )


@pytest.fixture
def single_branch_window(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """A single_branch mission with a computable window; the returned list is the window's changed paths."""
    changed: list[str] = []
    monkeypatch.setattr(persistence, "require_lanes_json", lambda _feature_dir: object())
    monkeypatch.setattr(single_branch_landing, "is_single_branch_mission", lambda _repo, _manifest: True)
    monkeypatch.setattr(single_branch_landing, "single_branch_evidence_window", lambda _repo, _manifest, **_kw: _WINDOW)
    monkeypatch.setattr(vcs_git, "git_diff_names_checked", lambda _repo, _base, _tip, **_kw: list(changed))
    monkeypatch.setattr(move_task_module, "_mt_owned_file_patterns", lambda _st: ("src/wp01/**",))
    return changed


@pytest.mark.parametrize("target_lane", [Lane.FOR_REVIEW, Lane.APPROVED])
def test_refusal_without_implementation_names_the_missing_commit(single_branch_window: list[str], target_lane: Lane) -> None:
    single_branch_window.append("kitty-specs/sb/tasks.md")  # planning edits are not implementation

    with pytest.raises(ActionContextError) as refused:
        move_task_module._mt_require_single_branch_implementation(_state(target_lane))

    assert refused.value.code == "SINGLE_BRANCH_IMPLEMENTATION_MISSING"
    message = str(refused.value)
    assert "no implementation commit" in message
    assert "WP01" in message
    assert "owned_files" in message


def test_committed_owned_work_is_not_refused(single_branch_window: list[str]) -> None:
    single_branch_window.append("src/wp01/greeting.py")

    move_task_module._mt_require_single_branch_implementation(_state(Lane.FOR_REVIEW))
