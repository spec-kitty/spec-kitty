"""#5569 -- a CANCELED dependency WP's code must not land via a fast-forwarded dependent lane.

WP01 is rejected and canceled with operator provenance (as ``consolidate``'s own
refusal advises); WP02 depends on WP01 and is approved. The real allocator's
dependency step fast-forwards WP01's commit onto ``lane-b``'s ``--first-parent``
spine, so the gate used to count it as approved authorship and ship it while the
output said ``Skipping lane-a (... no branch to integrate)`` and the exit was 0.

Driven through the REAL ``spec-kitty consolidate`` CLI (default squash and
``--strategy merge``). The lanes are cut by the real ``allocate_lane_worktree`` and
every status transition runs through the production status shell -- never
``plant_canceled_commit`` (a true merge commit, which is why #4977 went green).
Each negative has a same-fixture positive control, so a refusal here cannot be
an artefact of the fixture.

The spec-kitty#5937 tests cover the other shape: WP01 is canceled while still
``planned``, so ``lane-a`` is never created, and approved WP02 must land (lanes,
lanes attested, and coord) instead of being refused for an unreadable branch.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.lanes.branch_naming import lane_branch_name
from tests.terminus.canceled_dependency_support import (
    LANE_A,
    LANE_B,
    WP01_PATH,
    WP02_PATH,
    CanceledDependencyMission,
    build_canceled_dependency_mission,
    build_never_started_dependency_mission,
    first_parent_shas,
    merge_commits,
    strip_lane_head_stamps,
)
from tests.terminus.conftest import _git as git
from tests.terminus.conftest import CoordMission, blob_present_at, run_terminus
from tests.terminus.lanes_fixture import build_lanes_mission_canceled_dependency
from tests.terminus.mixed_lane_support import ATTEST_FLAG, REFUSE_HEADER, collapse

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_STRATEGIES = ("squash", "merge")
_ERROR_CODE = "CANCELED_REACHABLE_VIA_DEPENDENCY"
_ATTEST_REASON = "checked by hand: WP01's canceled content is absent or superseded on lane-b"
_SUPERSEDING_BODY = "def wp01() -> int:\n    return 'superseded by WP02'\n"


def _assert_fast_forward_shape(built: CanceledDependencyMission) -> None:
    """Fixture precondition: WP01's commit rides lane-b's first-parent spine, no merge commit.

    An errored precondition (not a pass) when the allocator shape is not the
    fast-forward the issue describes.
    """
    mission = built.mission
    spine = first_parent_shas(mission.repo, mission.target_branch, built.lane_b_branch)
    assert built.wp01_sha in spine, "fixture precondition: WP01's commit must be on lane-b's --first-parent history"
    assert merge_commits(mission.repo, mission.target_branch, built.lane_b_branch) == [], (
        "fixture precondition: lane-b must hold no merge commit (the dependency step is a fast-forward)"
    )


def _consolidate(built: CanceledDependencyMission, strategy: str, *extra: str) -> tuple[int, str]:
    mission = built.mission
    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--strategy", strategy, "--yes", *extra])
    return result.returncode, collapse(result.stdout + "\n" + result.stderr)


@pytest.mark.parametrize("strategy", _STRATEGIES)
def test_canceled_dependency_code_must_not_ship(tmp_path: Path, strategy: str) -> None:
    built = build_canceled_dependency_mission(tmp_path)
    mission = built.mission
    _assert_fast_forward_shape(built)
    pre_target = mission.rev(mission.target_branch)

    rc, flat = _consolidate(built, strategy)

    assert rc != 0, f"canceled WP01 reachable through lane-b must be refused, got exit 0 ({strategy}):\n{flat}"
    assert _ERROR_CODE in flat, f"expected {_ERROR_CODE} in the refusal:\n{flat}"
    assert "WP01" in flat and LANE_B in flat, f"the refusal must name WP01 and the carrying lane {LANE_B}:\n{flat}"
    assert mission.rev(mission.target_branch) == pre_target, "target must be unchanged after the refusal"
    assert not blob_present_at(mission.repo, mission.target_branch, WP01_PATH), "canceled WP01 content must not be on the target"


@pytest.mark.parametrize("strategy", _STRATEGIES)
def test_attestation_does_not_lift_shipping_canceled_content(tmp_path: Path, strategy: str) -> None:
    """The override covers attribution evidence only; content that would ship still FAILs."""
    built = build_canceled_dependency_mission(tmp_path, mid8="01M5569B")
    mission = built.mission
    pre_target = mission.rev(mission.target_branch)

    rc, flat = _consolidate(built, strategy, ATTEST_FLAG, "WP01", "--attest-reason", _ATTEST_REASON)

    assert rc != 0, f"an attestation must not let canceled content ship ({strategy}):\n{flat}"
    assert _ERROR_CODE in flat, flat
    assert mission.rev(mission.target_branch) == pre_target
    assert not blob_present_at(mission.repo, mission.target_branch, WP01_PATH)


@pytest.mark.parametrize("strategy", _STRATEGIES)
def test_control_independent_wp_consolidates(tmp_path: Path, strategy: str) -> None:
    """Same fixture, WP02 does not depend on WP01: WP01 is never carried, so exit 0 and its code is absent."""
    built = build_canceled_dependency_mission(tmp_path, depends=False, mid8="01M5569C")
    mission = built.mission

    rc, flat = _consolidate(built, strategy)

    assert rc == 0, f"an independent canceled WP must not block consolidation ({strategy}):\n{flat}"
    assert blob_present_at(mission.repo, mission.target_branch, WP02_PATH)
    assert not blob_present_at(mission.repo, mission.target_branch, WP01_PATH)


@pytest.mark.parametrize("strategy", _STRATEGIES)
def test_control_approved_dependency_consolidates(tmp_path: Path, strategy: str) -> None:
    """Same fixture, WP01 stays approved: its carried code is approved authorship and ships."""
    built = build_canceled_dependency_mission(tmp_path, wp01_final="approved", mid8="01M5569D")
    mission = built.mission

    rc, flat = _consolidate(built, strategy)

    assert rc == 0, f"an approved dependency must consolidate ({strategy}):\n{flat}"
    assert blob_present_at(mission.repo, mission.target_branch, WP01_PATH)
    assert blob_present_at(mission.repo, mission.target_branch, WP02_PATH)


@pytest.mark.parametrize("strategy", _STRATEGIES)
def test_control_superseded_canceled_change_consolidates(tmp_path: Path, strategy: str) -> None:
    """Same fixture, a later approved WP overwrites every path WP01 touched: nothing of WP01 ships."""
    built = build_canceled_dependency_mission(tmp_path, wp02_overwrites_wp01=True, mid8="01M5569E")

    rc, flat = _consolidate(built, strategy)

    assert rc == 0, f"a fully superseded canceled change must not block ({strategy}):\n{flat}"
    assert _ERROR_CODE not in flat


def _assert_unattributable_refusal(flat: str) -> None:
    assert REFUSE_HEADER in flat and f"{ATTEST_FLAG} WP01" in flat, flat


@pytest.mark.parametrize("strategy", _STRATEGIES)
def test_unattributable_canceled_dependency_refuses_then_attestation_lifts_only_the_refusal(tmp_path: Path, strategy: str) -> None:
    """A legacy (unstamped) canceled WP whose commit a lane carries REFUSEs naming the override.

    The attestation lifts that attribution-evidence refusal and nothing else: here
    WP01's file is still live on the carrying lane, so the attested run FAILs with
    the content verdict and WP01's code does not reach the target.
    """
    built = build_canceled_dependency_mission(tmp_path, mid8="01M5569F")
    mission = built.mission
    strip_lane_head_stamps(mission, "WP01")
    pre_target = mission.rev(mission.target_branch)

    rc, flat = _consolidate(built, strategy)
    assert rc != 0, f"an unattributable carried canceled WP must refuse ({strategy}):\n{flat}"
    _assert_unattributable_refusal(flat)
    assert mission.rev(mission.target_branch) == pre_target

    rc, flat = _consolidate(built, strategy, ATTEST_FLAG, "WP01", "--attest-reason", _ATTEST_REASON)
    assert rc != 0, f"an attestation must not let a legacy canceled WP's live content ship ({strategy}):\n{flat}"
    assert _ERROR_CODE in flat, f"expected the content verdict {_ERROR_CODE} once the refusal is lifted:\n{flat}"
    assert REFUSE_HEADER not in flat, f"the attestation must have lifted the attribution-evidence refusal:\n{flat}"
    assert mission.rev(mission.target_branch) == pre_target, "target must be restored after the content verdict"
    assert not blob_present_at(mission.repo, mission.target_branch, WP01_PATH), "canceled WP01 content must not be on the target"


@pytest.mark.parametrize("strategy", _STRATEGIES)
def test_twin_attested_unattributable_canceled_dependency_consolidates_when_superseded(tmp_path: Path, strategy: str) -> None:
    """Same legacy fixture, but approved WP02 overwrote WP01's file: once attested, nothing of WP01 ships and it lands."""
    built = build_canceled_dependency_mission(tmp_path, wp02_overwrites_wp01=True, mid8="01M5569G")
    mission = built.mission
    strip_lane_head_stamps(mission, "WP01")
    pre_target = mission.rev(mission.target_branch)

    rc, flat = _consolidate(built, strategy)
    assert rc != 0, f"an unattributable carried canceled WP must refuse before it is attested ({strategy}):\n{flat}"
    _assert_unattributable_refusal(flat)
    assert mission.rev(mission.target_branch) == pre_target

    rc, flat = _consolidate(built, strategy, ATTEST_FLAG, "WP01", "--attest-reason", _ATTEST_REASON)
    assert rc == 0, f"the attested legacy mission whose canceled content is superseded must consolidate ({strategy}):\n{flat}"
    assert _ERROR_CODE not in flat
    assert git(mission.repo, "show", f"{mission.target_branch}:{WP01_PATH}").stdout == _SUPERSEDING_BODY, "only WP02's version of the file lands"
    assert blob_present_at(mission.repo, mission.target_branch, WP02_PATH)


# --- spec-kitty#5937: a canceled dependency that never started -------------------

_LANES_WP01_PATH = "src/alpha/mod.py"
_LANES_WP02_PATH = "src/beta/mod.py"
_NEVER_STARTED_ATTEST_REASON = "WP01 was canceled before it started; it has no lane branch and no commits"


def _consolidate_mission(mission: CoordMission, *extra: str) -> tuple[int, str]:
    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes", *extra])
    return result.returncode, collapse(result.stdout + "\n" + result.stderr)


def _wp_lane(mission: CoordMission, wp_id: str) -> str:
    """WP state through the topology-neutral CLI reader (the coord worktree is torn down after a coord consolidate)."""
    status = run_terminus(mission, ["agent", "tasks", "status", "--mission", mission.slug, "--json"])
    assert status.returncode == 0, status.stderr
    payload = json.loads(status.stdout)
    return str(next(wp["lane"] for wp in payload["work_packages"] if wp["id"] == wp_id))


def _assert_branch_never_existed(mission: CoordMission, branch: str) -> None:
    listed = git(mission.repo, "branch", "--list", branch).stdout.strip()
    assert listed == "", f"fixture precondition: the never-started lane branch {branch!r} must not exist, got {listed!r}"


def _assert_dependent_landed(mission: CoordMission, rc: int, flat: str, *, wp01_path: str, wp02_path: str) -> None:
    assert rc == 0, f"an approved WP whose canceled dependency never started must consolidate:\n{flat}"
    assert blob_present_at(mission.repo, mission.target_branch, wp02_path), "WP02's approved work must be on the target"
    assert not blob_present_at(mission.repo, mission.target_branch, wp01_path), "canceled WP01 has no content to ship"
    assert _wp_lane(mission, "WP01") == "canceled", "WP01 must stay canceled"


def _never_started_lanes_mission(tmp_path: Path, mid8: str) -> CoordMission:
    mission = build_lanes_mission_canceled_dependency(tmp_path, cancel_dependency=True, dependency_never_started=True, mid8=mid8)
    _assert_branch_never_existed(mission, lane_branch_name(mission.slug, LANE_A, target_branch=mission.target_branch))
    return mission


def test_never_started_canceled_dependency_lands_dependent_work_lanes(tmp_path: Path) -> None:
    mission = _never_started_lanes_mission(tmp_path, "01M5937A")

    rc, flat = _consolidate_mission(mission)

    _assert_dependent_landed(mission, rc, flat, wp01_path=_LANES_WP01_PATH, wp02_path=_LANES_WP02_PATH)


def test_never_started_canceled_dependency_lands_dependent_work_lanes_attested(tmp_path: Path) -> None:
    """The attestation changes nothing here: the never-started lane is accepted with or without it."""
    mission = _never_started_lanes_mission(tmp_path, "01M5937B")

    rc, flat = _consolidate_mission(mission, ATTEST_FLAG, "WP01", "--attest-reason", _NEVER_STARTED_ATTEST_REASON)

    _assert_dependent_landed(mission, rc, flat, wp01_path=_LANES_WP01_PATH, wp02_path=_LANES_WP02_PATH)


def test_never_started_canceled_dependency_lands_dependent_work_coord(tmp_path: Path) -> None:
    built = build_never_started_dependency_mission(tmp_path, mid8="01M5937C")
    mission = built.mission
    _assert_branch_never_existed(mission, built.lane_a_branch)

    rc, flat = _consolidate_mission(mission)

    _assert_dependent_landed(mission, rc, flat, wp01_path=WP01_PATH, wp02_path=WP02_PATH)
