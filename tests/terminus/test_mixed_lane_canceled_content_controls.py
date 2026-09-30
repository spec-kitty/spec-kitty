"""Mixed lanes whose canceled WP left no unsuperseded content consolidate cleanly (exit 0) with the survivor's content on the target.

Positive controls for ``test_mixed_lane_canceled_content_verdicts.py``: the
same builder (``build_coord_mission_mixed_lane_canceled`` /
``build_coord_mission_mixed_lane_with_dependency``) and the same real-CLI entry
point (:func:`tests.terminus.conftest.run_terminus`, no git/subprocess
mocking), but each shape here must PASS -- so every refusal/absence assertion
in the verdicts file is non-vacuous against a builder proven sound here.

Originally the #5046 positive controls (mission
mixed-lane-authorship-soundness-01M3M7Y0).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.terminus.conftest import (
    CoordMission,
    PlantedChange,
    blob_present_at,
    build_coord_mission_mixed_lane_canceled,
    build_coord_mission_mixed_lane_with_dependency,
    run_terminus,
)
from tests.terminus.conftest import _git as git
from tests.terminus.mixed_lane_support import collapse

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

_SHARED_PATH = "src/pkg/shared.py"
_TMP_PATH = "src/pkg/tmp.py"
_WP01_PATH = "src/pkg/wp01.py"
_WP02_NEW_PATH = "src/pkg/wp02_new.py"


def _read_target_blob(mission: CoordMission, path: str) -> str:
    return git(mission.repo, "show", f"{mission.target_branch}:{path}").stdout


@pytest.mark.parametrize(
    ("strategy_args", "mid8"),
    [([], "01M5046E"), (["--strategy", "merge"], "01M5046F")],
    ids=["default-squash", "merge"],
)
def test_superseded_by_survivor_passes(tmp_path: Path, strategy_args: list[str], mid8: str) -> None:
    """Everything WP02 touched is later fully rewritten/deleted by WP01's own
    rework: PASS, and the target carries WP01's final content, not WP02's.

    ``shared.py`` is seeded via ``extra_base_files`` so WP02's edit is a
    genuine MODIFY of a pre-existing file, not an add.
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
        mid8=mid8,
    )

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, *strategy_args, "--yes"])

    assert result.returncode == 0, f"a superseded canceled change must PASS:\n{result.stdout}\n{result.stderr}"
    assert _read_target_blob(mission, _SHARED_PATH) == "SHARED = 'wp01 rework final'\n"
    assert blob_present_at(mission.repo, mission.target_branch, _TMP_PATH) is False


def test_canceled_self_revert(tmp_path: Path) -> None:
    """WP02 modifies shared.py then sets it back to its own pre-state within its
    own session: the final content is attributable to WP01 -- PASS.
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
    """A workflow-shaped merge commit inside WP02's own session, plus a
    superseded canceled change, is not mistaken for canceled content -- PASS.
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
    """Default-strategy twin of ``test_repro_5018.py``'s merge-only pin: WP02
    canceled straight from ``planned`` with no commits at all -- PASS.
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
    """Pairs with the verdicts file's no-attribution REFUSE on the SAME builder:
    when WP02 is ``approved`` (not canceled) the lane is not mixed and no
    attribution stamp is required -- PASS even with ``stamp_attribution=False``.
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
        f"(the canceled twin refuses -- this proves the builder itself "
        f"is sound):\n{result.stdout}\n{result.stderr}"
    )
    assert blob_present_at(mission.repo, mission.target_branch, _WP02_NEW_PATH) is True


def test_dependency_lane_commits_are_not_outside_windows(tmp_path: Path) -> None:
    """``lanes/worktree_allocator.py`` merges a dependency lane into the dependent
    lane without ``--no-ff``, so the dependency lane's WP commits fast-forward
    onto the dependent lane's first-parent spine. They lie in no window of the
    dependent lane's own WPs, yet are not closed-world stragglers -- a clean
    dependent mixed lane consolidates.
    """
    mission = build_coord_mission_mixed_lane_with_dependency(tmp_path, canceled_leaks=False, mid8="01M5046M")
    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])
    flat = collapse(result.stdout + "\n" + result.stderr)
    assert "outside every WP's recorded work window" not in flat, f"dependency-lane commits are not stragglers:\n{flat}"
    assert result.returncode == 0, f"a clean dependent mixed lane must consolidate:\n{flat}"
    assert blob_present_at(mission.repo, mission.target_branch, "src/pkg/wp03.py") is True
    assert blob_present_at(mission.repo, mission.target_branch, "src/pkg/wp01.py") is True
