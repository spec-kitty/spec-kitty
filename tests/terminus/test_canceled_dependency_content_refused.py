"""Repro #5569 -- a fully-canceled dependency lane's content must not ship.

``lanes/worktree_allocator.py`` merges a dependency lane into the dependent lane
WITHOUT ``--no-ff``, so a fresh dependent lane fast-forwards and the canceled
WP's commit lands on the approved lane's first-parent spine. The authored claim
then counted that commit as approved authorship, so ``consolidate`` exited 0 and
the canceled WP's file reached the target (rc5 missed it: the #4977 repro
planted a true merge, never a fast-forward).

Driven through the real CLI (:func:`tests.terminus.conftest.run_terminus`) on a
mission whose lane worktrees come from the real allocator; no git or subprocess
seam is mocked.

One smoke per behaviour family (#5618 part 2): the default squash strategy only. The
merge-strategy replays were dropped because the canceled-dependency axis is
strategy-independent: the guards in
``tests/consolidation/test_canceled_dependency_lane.py`` take no strategy at all, and
planted breaks (the dependency tip exempt again, the deleted-branch refusal removed, the
approved dependency anchor dropped) turn them red.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.terminus.conftest import blob_present_at, run_terminus
from tests.terminus.lanes_fixture import build_lanes_mission_canceled_dependency

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

_CANCELED_PATH = "src/alpha/mod.py"
_APPROVED_PATH = "src/beta/mod.py"
_MID8 = "01M5569A"


def test_canceled_dependency_lane_content_never_ships(tmp_path: Path) -> None:
    mission = build_lanes_mission_canceled_dependency(tmp_path, cancel_dependency=True, mid8=_MID8)

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])

    output = result.stdout + result.stderr
    assert result.returncode != 0, f"canceled WP01 content must not land at exit 0:\n{output}"
    assert "WP01" in output, f"the refusal must name the canceled WP:\n{output}"
    assert "CANCELED_REACHABLE_VIA_DEPENDENCY" in output, f"the refusal must carry its stable code:\n{output}"
    assert blob_present_at(mission.repo, mission.target_branch, _CANCELED_PATH) is False


def test_approved_dependency_lane_content_ships(tmp_path: Path) -> None:
    """Positive control: the same fixture with WP01 approved lands both files."""
    mission = build_lanes_mission_canceled_dependency(tmp_path, cancel_dependency=False, mid8=_MID8)

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])

    assert result.returncode == 0, f"an approved dependency lane must consolidate:\n{result.stdout}\n{result.stderr}"
    assert blob_present_at(mission.repo, mission.target_branch, _CANCELED_PATH) is True
    assert blob_present_at(mission.repo, mission.target_branch, _APPROVED_PATH) is True


def test_canceled_dependency_lane_with_deleted_branch_refuses(tmp_path: Path) -> None:
    """A fully-canceled dependency lane whose branch is gone must fail closed, not PASS.

    The dependent approved lane still carries the canceled commit on its first-parent
    spine (the allocator fast-forwarded it), so without the canceled lane's tip there is
    nothing to subtract and the canceled content would be attributed as authored.
    """
    mission = build_lanes_mission_canceled_dependency(tmp_path, cancel_dependency=True, mid8=_MID8)
    branch_a = mission.lane_branches["WP01"]
    subprocess.run(
        ["git", "worktree", "remove", "--force", str(mission.repo / ".worktrees" / f"{mission.slug}-lane-a")], cwd=mission.repo, check=True, capture_output=True
    )
    subprocess.run(["git", "branch", "-D", branch_a], cwd=mission.repo, check=True, capture_output=True)

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])

    output = result.stdout + result.stderr
    assert result.returncode != 0, f"canceled WP01 content must not land at exit 0 when its lane branch is gone:\n{output}"
    assert "lane-a" in output, f"the refusal must name the unreadable canceled dependency lane:\n{output}"
    assert blob_present_at(mission.repo, mission.target_branch, _CANCELED_PATH) is False
