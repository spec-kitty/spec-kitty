"""An interrupted consolidation keeps its original cleanup choice."""

import pytest

from specify_cli.consolidation.executor import _resume_cleanup_choice
from specify_cli.consolidation.resolve import _load_or_create_merge_state
from specify_cli.consolidation.state import ConsolidationState


@pytest.mark.parametrize("choice", [True, False])
def test_resume_replays_persisted_choice(choice: bool) -> None:
    assert _resume_cleanup_choice(None, choice, "--keep-branch") is choice
    assert _resume_cleanup_choice(choice, choice, "--keep-branch") is choice


def test_resume_refuses_conflicting_explicit_choice() -> None:
    with pytest.raises(ValueError, match="conflicts with the interrupted consolidation"):
        _resume_cleanup_choice(True, False, "--delete-branch")


def test_legacy_state_without_choice_uses_current_resolution() -> None:
    assert _resume_cleanup_choice(None, None, "--keep-branch") is None


def test_retention_choices_survive_state_round_trip() -> None:
    state = ConsolidationState(
        mission_id="m1",
        mission_slug="mission",
        target_branch="main",
        wp_order=[],
        delete_branch=False,
        remove_worktree=True,
    )
    restored = ConsolidationState.from_dict(state.to_dict())
    assert restored.delete_branch is False
    assert restored.remove_worktree is True


def test_fresh_state_records_effective_choices_and_resume_preserves_them(tmp_path) -> None:
    kwargs = {
        "main_repo": tmp_path,
        "mission_slug": "mission",
        "canonical_id": "m1",
        "target_branch": "main",
        "wp_order": [],
        "push_requested": False,
    }
    state, is_resume = _load_or_create_merge_state(
        **kwargs,
        delete_branch=False,
        remove_worktree=True,
    )
    assert not is_resume
    assert state.delete_branch is False
    assert state.remove_worktree is True

    resumed, is_resume = _load_or_create_merge_state(
        **kwargs,
        delete_branch=True,
        remove_worktree=False,
    )
    assert is_resume
    assert resumed.delete_branch is False
    assert resumed.remove_worktree is True
