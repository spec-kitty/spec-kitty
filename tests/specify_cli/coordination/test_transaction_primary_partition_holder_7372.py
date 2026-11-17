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


def _tear_down_coordination(mission_root: Path, slug: str) -> str:
    """Remove the coordination worktree and delete its branch, as consolidation's cleanup does."""
    import json

    meta = json.loads((mission_root / "kitty-specs" / slug / "meta.json").read_text(encoding="utf-8"))
    coordination_branch: str = meta["coordination_branch"]
    coord_worktree = mission_root / ".worktrees" / f"{slug}-coord"
    if coord_worktree.exists():
        git(mission_root, "worktree", "remove", "--force", str(coord_worktree))
    git(mission_root, "branch", "-D", coordination_branch)
    return coordination_branch


def test_primary_holder_keeps_the_root_when_the_coordination_branch_was_deleted(tmp_path: Path) -> None:
    """#7664: a PRIMARY-target commit of a coordination Mission whose coordination branch was torn down.

    The PRIMARY partition never lives on the coordination branch, so its checkout must not depend on
    the coordination status surface. Since #7633 the holder asked the seam, whose PRIMARY-kind
    ``write_target`` resolved the coordination status surface first and raised
    ``COORDINATION_BRANCH_DELETED``; a PRIMARY write now keeps the repository root checkout.
    """
    from mission_runtime import ActionContextError, MissionArtifactKind, placement_seam

    mission = make_default_mission(tmp_path, THREE_LANES, standing_on="work", explicit="lanes_with_coord")
    target = git(mission.root, "branch", "--show-current")
    _tear_down_coordination(mission.root, mission.slug)

    assert transaction._primary_partition_holder(mission.root, mission.slug, target) == mission.root
    assert placement_seam(mission.root, mission.slug).write_target(MissionArtifactKind.WORK_PACKAGE_TASK).ref == target
    # The COORD leg still refuses: a status write of this Mission has nowhere to land.
    with pytest.raises(ActionContextError) as excinfo:
        placement_seam(mission.root, mission.slug).write_target(MissionArtifactKind.STATUS_STATE)
    assert excinfo.value.code == "COORDINATION_BRANCH_DELETED"


@pytest.mark.parametrize("topology", ["lanes", "single_branch"])
def test_probe_checkout_equals_the_status_write_checkout_without_coordination(tmp_path: Path, topology: str) -> None:
    """#5783 landing fold: ``write_checkout_refusal`` asks for the PRIMARY (``WORK_PACKAGE_TASK``)
    checkout, while a coordination-less ``done`` write commits in the ``STATUS_STATE`` checkout
    (``BookkeepingTransaction.acquire``). They must name the same checkout, or the up-front probe
    and the real write could disagree.
    """
    from mission_runtime import MissionArtifactKind

    mission = make_default_mission(tmp_path, THREE_LANES, standing_on="work", explicit=topology)
    target = git(mission.root, "branch", "--show-current")

    probe = transaction._primary_partition_holder(mission.root, mission.slug, target)
    write = transaction.seam_commit_checkout(mission.root, mission.slug, target, MissionArtifactKind.STATUS_STATE)
    assert probe == write
