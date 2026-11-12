"""``write_dir(kind).surface_root`` names the checkout that holds ``write_dir(kind).path`` (#7546, FR-001).

After ``finalize-tasks`` settles a default Mission to ``lanes_with_coord``, the repository root
checkout is back on ``create_return_branch`` and the coordination worktree holds the topic
branch, so every declared-PRIMARY kind reads (and writes) its directory inside that worktree.
The seam must then report that worktree as the write checkout, not the repository root checkout
(data-model invariant 1: ``path`` lies inside ``surface_root``). A Mission settled to
``single_branch`` is the positive control: its write checkout stays the repository root checkout.
Both rows drive the real ``agent mission create`` core and the real ``finalize-tasks`` command.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mission_runtime import MissionArtifactKind, placement_seam
from tests.specify_cli.cli.commands.agent.test_finalize_topology_settlement import (
    THREE_LANES,
    _quiet_status_fanout,
    make_default_mission,
    run_finalize,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox]

# Re-export so pytest discovers the imported autouse fixture (chdir + silenced status fan-out).
__all__ = ["_quiet_status_fanout"]

_PRIMARY_KINDS = (
    MissionArtifactKind.SPEC,
    MissionArtifactKind.TASKS_INDEX,
    MissionArtifactKind.WORK_PACKAGE_TASK,
    MissionArtifactKind.PRIMARY_METADATA,
)


def _assert_write_checkout(root: Path, slug: str, expected_checkout: Path) -> None:
    seam = placement_seam(root, slug)
    for kind in _PRIMARY_KINDS:
        location = seam.write_dir(kind)
        assert location.path.resolve().is_relative_to(location.surface_root.resolve()), (kind, location)
        assert location.surface_root.resolve() == expected_checkout.resolve(), (kind, location)


def test_settled_default_mission_writes_in_the_coordination_worktree(tmp_path: Path) -> None:
    mission = make_default_mission(tmp_path, THREE_LANES)
    code, payload = run_finalize(mission)
    assert code == 0, payload
    decision = payload["topology_decision"]
    assert isinstance(decision, dict) and decision["settled_topology"] == "lanes_with_coord"

    _assert_write_checkout(mission.root, mission.slug, mission.coord_mission_dir.parents[1])


def test_single_branch_mission_writes_in_the_repository_root_checkout(tmp_path: Path) -> None:
    mission = make_default_mission(tmp_path, ("src/one.py", "src/two.py"))
    code, payload = run_finalize(mission)
    assert code == 0, payload
    decision = payload["topology_decision"]
    assert isinstance(decision, dict) and decision["settled_topology"] == "single_branch"

    _assert_write_checkout(mission.root, mission.slug, mission.root)
