"""Positive controls for #5046 (mixed-lane-authorship-soundness-01M3M7Y0, WP02).

Same builder (``build_coord_mission_mixed_lane_canceled``) and real-CLI entry
point (``run_terminus`` -- no ``_run_git`` / subprocess mocking) as
``test_repro_5046.py``'s defect cases, but each shape here consolidates
cleanly (exit 0) -- both on the mission base today AND after WP05/WP07 land
(non-vacuity tactic: every refusal/absence assertion in the sibling defect
file has a positive control here, on the same builder).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.terminus.conftest import (
    CoordMission,
    PlantedChange,
    blob_present_at,
    build_coord_mission_mixed_lane_canceled,
    run_terminus,
)
from tests.terminus.conftest import _git as git

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

_SHARED_PATH = "src/pkg/shared.py"
_TMP_PATH = "src/pkg/tmp.py"
_WP01_PATH = "src/pkg/wp01.py"
_WP02_NEW_PATH = "src/pkg/wp02_new.py"


def _read_target_blob(mission: CoordMission, path: str) -> str:
    return git(mission.repo, "show", f"{mission.target_branch}:{path}").stdout


def test_superseded_by_survivor_default_squash(tmp_path: Path) -> None:
    """T009.1 (default strategy) -- everything WP02 touched is later fully
    rewritten/deleted by WP01's own rework -- must PASS, and the target must
    carry WP01's final content, not WP02's.

    ``shared.py`` is seeded via ``extra_base_files`` so WP02's edit is a
    genuine MODIFY of a pre-existing file (review cycle 1, Issue 2), not an
    add -- the superseded-control twin of T006's base-seeded modify.
    """
    mission = build_coord_mission_mixed_lane_canceled(
        tmp_path,
        extra_base_files={_SHARED_PATH: "SHARED = 'base'\n"},
        canceled_changes=[
            PlantedChange(_SHARED_PATH, "SHARED = 'wp02 modified'\n"),
            PlantedChange(_TMP_PATH, "TMP = 'wp02 added'\n"),
        ],
        survivor_after=[
            PlantedChange(_SHARED_PATH, "SHARED = 'wp01 rework final'\n"),
            PlantedChange(_TMP_PATH, None),
        ],
        stamp_attribution=True,
        mid8="01M5046E",
    )

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])

    assert result.returncode == 0, f"a superseded canceled change must PASS:\n{result.stdout}\n{result.stderr}"
    assert _read_target_blob(mission, _SHARED_PATH) == "SHARED = 'wp01 rework final'\n"
    assert blob_present_at(mission.repo, mission.target_branch, _TMP_PATH) is False


def test_superseded_by_survivor_strategy_merge(tmp_path: Path) -> None:
    """T009.1 (``--strategy merge``) -- mirrors the default-squash control above."""
    mission = build_coord_mission_mixed_lane_canceled(
        tmp_path,
        extra_base_files={_SHARED_PATH: "SHARED = 'base'\n"},
        canceled_changes=[
            PlantedChange(_SHARED_PATH, "SHARED = 'wp02 modified'\n"),
            PlantedChange(_TMP_PATH, "TMP = 'wp02 added'\n"),
        ],
        survivor_after=[
            PlantedChange(_SHARED_PATH, "SHARED = 'wp01 rework final'\n"),
            PlantedChange(_TMP_PATH, None),
        ],
        stamp_attribution=True,
        mid8="01M5046F",
    )

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--strategy", "merge", "--yes"])

    assert result.returncode == 0, f"a superseded canceled change must PASS under --strategy merge:\n{result.stdout}\n{result.stderr}"
    assert _read_target_blob(mission, _SHARED_PATH) == "SHARED = 'wp01 rework final'\n"
    assert blob_present_at(mission.repo, mission.target_branch, _TMP_PATH) is False


def test_canceled_self_revert(tmp_path: Path) -> None:
    """T009.2 (default) -- WP02 modifies shared.py then sets it back to its
    own pre-state within its own session: the final observable content is
    attributable to WP01 (via ``survivor_before``), not to WP02 -- must PASS.
    """
    mission = build_coord_mission_mixed_lane_canceled(
        tmp_path,
        canceled_changes=[
            PlantedChange(_SHARED_PATH, "SHARED = 'wp02 temp'\n"),
            PlantedChange(_SHARED_PATH, "SHARED = 'wp01 base'\n"),
        ],
        survivor_before=[PlantedChange(_SHARED_PATH, "SHARED = 'wp01 base'\n")],
        stamp_attribution=True,
        mid8="01M5046G",
    )

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])

    assert result.returncode == 0, f"a canceled self-revert must PASS:\n{result.stdout}\n{result.stderr}"
    assert _read_target_blob(mission, _SHARED_PATH) == "SHARED = 'wp01 base'\n"


def test_lane_sync_merge_inside_canceled_session_not_flagged(tmp_path: Path) -> None:
    """T009.3 (default) -- a workflow-shaped merge commit inside WP02's own
    session, plus a superseded canceled change, must not itself be mistaken
    for canceled content -- must PASS.
    """
    mission = build_coord_mission_mixed_lane_canceled(
        tmp_path,
        canceled_changes=[PlantedChange(_TMP_PATH, "TMP = 'wp02 added'\n")],
        survivor_after=[PlantedChange(_TMP_PATH, None)],
        lane_sync_merge_in_canceled_session=True,
        stamp_attribution=True,
        mid8="01M5046H",
    )

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])

    assert result.returncode == 0, (
        f"a workflow lane-sync merge commit inside the canceled WP's session must not be flagged as canceled content:\n{result.stdout}\n{result.stderr}"
    )
    assert blob_present_at(mission.repo, mission.target_branch, _TMP_PATH) is False


def test_never_implemented_cancel_squash_twin(tmp_path: Path) -> None:
    """T009.4 (default) -- the default-strategy twin of
    ``test_repro_5018.py``'s merge-only pin: WP02 canceled straight from
    ``planned`` with no commits at all -- must PASS.
    """
    mission = build_coord_mission_mixed_lane_canceled(
        tmp_path,
        canceled_changes=(),
        survivor_before=[PlantedChange(_WP01_PATH, "def wp01() -> str:\n    return 'ok'\n")],
        canceled_entered_implementation=False,
        stamp_attribution=True,
        mid8="01M5046I",
    )

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])

    assert result.returncode == 0, f"a WP02 canceled before it entered implementation must PASS:\n{result.stdout}\n{result.stderr}"


def test_legacy_all_approved_lane_no_attribution(tmp_path: Path) -> None:
    """T009.5 (default) -- pairs with ``test_repro_5046.py``'s T008 REFUSE on
    the SAME builder: when WP02 is ``approved`` (not canceled), the lane is
    not "mixed" (contract C2) and no attribution stamp is required -- must
    PASS even with ``stamp_attribution=False``.
    """
    mission = build_coord_mission_mixed_lane_canceled(
        tmp_path,
        canceled_changes=[PlantedChange(_WP02_NEW_PATH, "def wp02_new() -> str:\n    return 'wp02 shipped legit'\n")],
        wp02_final="approved",
        stamp_attribution=False,
        mid8="01M5046J",
    )

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])

    assert result.returncode == 0, (
        f"an all-approved lane must PASS even without attribution stamping "
        f"(the canceled twin refuses in T008 -- this proves the builder itself "
        f"is sound):\n{result.stdout}\n{result.stderr}"
    )
    assert blob_present_at(mission.repo, mission.target_branch, _WP02_NEW_PATH) is True
