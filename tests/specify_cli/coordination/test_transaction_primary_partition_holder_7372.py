"""#7372 / FR-061: the transaction's PRIMARY-target arm commits in a topic holder only for a default Mission.

``BookkeepingTransaction.acquire(commit_to_primary_target=True)`` commits a PRIMARY-partition
group on the caller's ``destination_ref``. Before a default Mission lands that ref is its topic
branch, held by the coordination worktree, so the commit must run there. For every other Mission
the commit stays in the repository root checkout, even when some other checkout (an operator's own
worktree) happens to hold the destination branch.

Since #7633 the arm takes its checkout from the placement seam (``write_dir(...).surface_root``),
so each case is a real Mission built with the create core and the real ``finalize-tasks``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.coordination import transaction
from tests.specify_cli.cli.commands.agent.test_finalize_topology_settlement import (
    THREE_LANES,
    _quiet_status_fanout,
    git,
    make_default_mission,
    run_finalize,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox]
__all__ = ["_quiet_status_fanout"]


def test_default_mission_commits_in_the_holder_of_its_topic_branch(tmp_path: Path) -> None:
    mission = make_default_mission(tmp_path, THREE_LANES, standing_on="work")
    code, payload = run_finalize(mission)
    assert code == 0, payload
    holder = mission.root / ".worktrees" / f"{mission.slug}-coord"
    assert transaction._primary_partition_holder(mission.root, mission.slug, mission.topic).resolve() == holder.resolve()


def test_mission_that_is_not_default_keeps_the_root_even_when_another_checkout_holds_the_ref(tmp_path: Path) -> None:
    """The reviewer's M2 scenario: an operator's own worktree holds the destination branch."""
    mission = make_default_mission(tmp_path, THREE_LANES, standing_on="work", explicit="lanes_with_coord")
    target = git(mission.root, "branch", "--show-current")
    git(mission.root, "checkout", "-q", "--detach")
    git(mission.root, "worktree", "add", "-q", str(tmp_path / "operator"), target)
    assert transaction._primary_partition_holder(mission.root, mission.slug, target) == mission.root


def test_holder_that_does_not_hold_the_destination_keeps_the_root(tmp_path: Path) -> None:
    """A ref the seam does not name for the PRIMARY partition (here the landing target) keeps the root."""
    mission = make_default_mission(tmp_path, THREE_LANES, standing_on="work")
    code, payload = run_finalize(mission)
    assert code == 0, payload
    assert transaction._primary_partition_holder(mission.root, mission.slug, "work") == mission.root
