"""#5668 -- a commit added to a lane AFTER review approved it must not land under a verified banner.

``consolidate`` used to build an approved work package's claim from the live lane
tip, so a content commit made after the ``approved`` transition was approved
authorship on every axis: exit 0, "Reconciliation verified", the unreviewed file on
the target. The approval stamp (``policy_metadata.lane_head`` of the ``approved``
event) names the commit review saw; a lane with content beyond it must be refused
before any branch moves.

Driven through the REAL ``spec-kitty consolidate`` CLI (a subprocess), for the lanes
and coordination topologies and for the squash and merge strategies. Every cell has a
same-fixture positive control, so a refusal cannot be an artefact of the fixture.

Known gap: no harness drives ``implement`` and the review transitions through the CLI
end to end. The transitions run through the in-process production status shell
(:mod:`tests.terminus.post_approval_support`); the consolidation is a real subprocess.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.terminus.conftest import CoordMission, blob_present_at, git_rev, run_terminus
from tests.terminus.mixed_lane_support import collapse
from tests.terminus.post_approval_support import (
    LATE_PATH,
    REWORK_PATH,
    Topology,
    WP01_PATH,
    add_post_approval_commit,
    build_post_approval_mission,
    rework_and_reapprove,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

_TOPOLOGIES: tuple[Topology, ...] = ("lanes", "coord")
_STRATEGIES = ("squash", "merge")
_CODE = "LANE_MOVED_AFTER_APPROVAL"
_BANNER = "Reconciliation verified"


def _consolidate(mission: CoordMission, strategy: str | None = None) -> tuple[int, str]:
    args = ["consolidate", "--mission", mission.slug, "--yes"]
    if strategy is not None:
        args += ["--strategy", strategy]
    result = run_terminus(mission, args)
    return result.returncode, collapse(result.stdout + "\n" + result.stderr)


def _branch_tips(mission: CoordMission) -> dict[str, str]:
    refs = [mission.target_branch, mission.coord_branch]
    return {ref: git_rev(mission.repo, ref) for ref in refs}


@pytest.mark.parametrize("strategy", _STRATEGIES)
@pytest.mark.parametrize("topology", _TOPOLOGIES)
def test_post_approval_commit_is_refused_before_any_branch_moves(tmp_path: Path, topology: Topology, strategy: str) -> None:
    control = build_post_approval_mission(tmp_path / "control", topology)
    rc, flat = _consolidate(control, strategy)
    assert rc == 0, f"positive control: an untouched approved mission must consolidate ({topology}/{strategy}):\n{flat}"
    assert _BANNER in flat
    assert blob_present_at(control.repo, control.target_branch, WP01_PATH)

    mission = build_post_approval_mission(tmp_path / "late", topology)
    late_sha = add_post_approval_commit(mission)
    pre = _branch_tips(mission)

    rc, flat = _consolidate(mission, strategy)

    assert rc != 0, f"a commit added after approval must be refused, got exit 0 ({topology}/{strategy}):\n{flat}"
    assert _CODE in flat, f"expected {_CODE}:\n{flat}"
    assert late_sha[:7] in flat and "WP01" in flat, f"the refusal must name the late commit and WP01:\n{flat}"
    assert _BANNER not in flat
    assert _branch_tips(mission) == pre, "the refusal must fire before any branch moves"
    assert not blob_present_at(mission.repo, mission.target_branch, LATE_PATH), "the unreviewed file must not be on the target"


@pytest.mark.parametrize("topology", _TOPOLOGIES)
def test_rework_and_reapproval_consolidates(tmp_path: Path, topology: Topology) -> None:
    """A lane that moved and was approved AGAIN is within its (newest) approval."""
    mission = build_post_approval_mission(tmp_path, topology)
    rework_and_reapprove(mission, "WP01")

    rc, flat = _consolidate(mission)

    assert rc == 0, f"a re-approved lane must consolidate:\n{flat}"
    assert blob_present_at(mission.repo, mission.target_branch, REWORK_PATH)
