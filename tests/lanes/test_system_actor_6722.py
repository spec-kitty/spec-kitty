"""The lane recovery catch-up records the structured system actor (#6722, FR-003).

``reconcile_status`` walks a crashed work package forward with best-effort transitions.
Since #6722 each one carries ``{"tool": "recovery", "role": "system", "profile": null,
"model": null}`` instead of the bare ``"recovery"`` string, while ``RECOVERY_ACTOR``
stays the identity string the guard context needs and the snapshot ``actor`` slot still
reads ``recovery``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.lanes.recovery import RECOVERY_ACTOR, RecoveryState, reconcile_status
from specify_cli.status.models import actor_identity_str
from specify_cli.status.store import read_events
from tests.lanes.test_implementation_recovery import (
    _create_lane_branch_with_commits,
    _make_git_repo,
    _setup_feature,
)

pytestmark = [pytest.mark.git_repo]

_SYSTEM_RECOVERY_ACTOR = {"tool": "recovery", "role": "system", "profile": None, "model": None}


def _crashed_state() -> RecoveryState:
    return RecoveryState(
        wp_id="WP01",
        lane_id="lane-a",
        branch_name="kitty/mission-010-feat-lane-a",
        branch_exists=True,
        worktree_exists=True,
        context_exists=True,
        status_lane="planned",
        has_commits=True,
        recovery_action="emit_transitions",
    )


@pytest.fixture()
def crashed_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _make_git_repo(repo)
    _setup_feature(repo)
    _create_lane_branch_with_commits(repo)
    return repo


def test_recovery_actor_constant_stays_the_identity_the_guard_needs(crashed_repo: Path) -> None:
    """`RECOVERY_ACTOR` is still a `str`: `GuardContext(actor=...)` and the guards take one."""
    assert RECOVERY_ACTOR == "recovery"
    assert isinstance(RECOVERY_ACTOR, str)

    reconcile_status(crashed_repo, "010-feat", _crashed_state())
    events = read_events(crashed_repo / "kitty-specs" / "010-feat")
    recovery_events = [e for e in events if e.wp_id == "WP01" and actor_identity_str(e.actor) == RECOVERY_ACTOR]
    assert [str(e.from_lane) for e in recovery_events] == ["planned", "claimed"]
    assert [str(e.to_lane) for e in recovery_events] == ["claimed", "in_progress"]


def test_recovery_events_are_not_a_migration_seed(crashed_repo: Path) -> None:
    """`recovery` is a system write, not a reconstruction: the seed gates still say no."""
    from specify_cli.status.models import is_migration_actor

    reconcile_status(crashed_repo, "010-feat", _crashed_state())
    events = read_events(crashed_repo / "kitty-specs" / "010-feat")
    for event in events:
        if event.wp_id == "WP01" and actor_identity_str(event.actor) == RECOVERY_ACTOR:
            assert is_migration_actor(event.actor) is False
