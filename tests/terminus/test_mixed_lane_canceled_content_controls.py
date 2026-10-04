"""Mixed lanes whose canceled WP left no unsuperseded content consolidate cleanly (exit 0) with the survivor's content on the target.

Positive controls for ``test_mixed_lane_canceled_content_verdicts.py``: the
same builder (``build_coord_mission_mixed_lane_canceled`` /
``build_coord_mission_mixed_lane_with_dependency``) and the same real-CLI entry
point (:func:`tests.terminus.conftest.run_terminus`, no git/subprocess
mocking), but each shape here must PASS -- so every refusal/absence assertion
in the verdicts file is non-vacuous against a builder proven sound here.

Originally the #5046 positive controls (mission
mixed-lane-authorship-soundness-01M3M7Y0).

One smoke per behaviour family (#5618 part 2): the superseded-by-survivor PASS under the
default strategy stays end to end. The merge-strategy replay and the other controls are
pinned at the seam by OVER-trigger breaks (each turns the named guard red because the
check starts flagging what it must pass), in ``tests/consolidation/test_wp_attribution.py``,
``test_reconciliation.py`` and ``test_canceled_dependency_lane.py``:

* canceled self-revert -- the net-zero drop (``test_self_revert_dropped``);
* lane-sync merge inside the canceled session -- merges never attribute or supersede;
* never-implemented cancel -- ``_entered_implementation``;
* all-approved legacy lane without a stamp -- the mixed-lane predicate;
* dependency-lane commits are not outside windows -- the approved dependency anchor.
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


def _read_target_blob(mission: CoordMission, path: str) -> str:
    return git(mission.repo, "show", f"{mission.target_branch}:{path}").stdout


def test_superseded_by_survivor_passes(tmp_path: Path) -> None:
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
        mid8="01M5046E",
    )

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])

    assert result.returncode == 0, f"a superseded canceled change must PASS:\n{result.stdout}\n{result.stderr}"
    assert _read_target_blob(mission, _SHARED_PATH) == "SHARED = 'wp01 rework final'\n"
    assert blob_present_at(mission.repo, mission.target_branch, _TMP_PATH) is False
