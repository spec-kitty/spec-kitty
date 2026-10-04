"""A canceled WP's content on a shared (mixed) lane never ships: consolidation FAILs or REFUSEs and restores the target.

A lane shared by an APPROVED survivor WP and a CANCELED WP that committed real
content (the "mixed lane" shape) must never let the canceled content land on
the target. Unsuperseded canceled content is a FAIL naming each path with its
own wording; a canceled WP whose work window cannot be resolved (no
``policy_metadata.lane_head`` stamp) is a fail-closed REFUSE. Either way the
target is restored to its pre-consolidation SHA
(contract ``kitty-specs/mixed-lane-authorship-soundness-01M3M7Y0/contracts/
attribution-and-verdicts.md``).

Every test drives the REAL ``spec-kitty consolidate`` CLI
(:func:`tests.terminus.conftest.run_terminus`, no git/subprocess mocking)
against a real on-disk coordination mission. Assertions are bound to the
VERDICT BLOCK (the text from the verdict header on), and each path/wording
pair to its own semicolon-delimited clause, so a gate that mislabels a path
cannot pass. ``test_mixed_lane_canceled_content_controls.py`` keeps a single smoke control;
the per-shape exit-0 controls are pinned in ``tests/consolidation/test_wp_attribution.py``
and ``tests/consolidation/test_reconciliation.py``.

Originally the real-CLI reproductions of #5046 (defect fixed; permanent guards) (mission
mixed-lane-authorship-soundness-01M3M7Y0).

One smoke per behaviour family (#5618 part 2): the add/modify/delete FAIL under the
default strategy stays end to end. The merge-strategy replay, the survivor-undone FAIL,
the no-attribution REFUSE and the dependency-lane FAIL-not-REFUSE are pinned at the seam:
``tests/consolidation/test_reconciliation.py`` and ``tests/consolidation/test_wp_attribution.py``
go red when the canceled-content axis is disabled, when a missing stamp stops being
``no_stamp``, and (for the dependency lane) when the approved dependency anchor is dropped
(``test_canceled_dependency_lane.py``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.terminus.conftest import (
    PlantedChange,
    blob_present_at,
    build_coord_mission_mixed_lane_canceled,
    run_terminus,
)
from tests.terminus.mixed_lane_support import (
    FAIL_HEADER,
    FAIL_WHO,
    LANE_NAME,
    clause_for_path,
    collapse,
    verdict_block,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

_WP02_NEW_PATH = "src/pkg/wp02_new.py"
_SHARED_PATH = "src/pkg/shared.py"
_LEGACY_PATH = "src/pkg/legacy.py"
_WP01_OWN_PATH = "src/pkg/wp01_survivor.py"

_SHARED_BASE_CONTENT = "SHARED = 'base'\n"
_LEGACY_BASE_CONTENT = "LEGACY = 'base'\n"
_WP01_OWN_CONTENT = "def wp01_survivor() -> str:\n    return 'wp01 owns this'\n"

_FAIL_ADD_MODIFY = "carries canceled WP02's change"
_FAIL_DELETE = "deleted by canceled WP02"
_RECOVERY_STEP = "re-run spec-kitty consolidate"


def _add_modify_delete_changes() -> list[PlantedChange]:
    return [
        PlantedChange(_WP02_NEW_PATH, "def wp02_new() -> str:\n    return 'wp02 leaked'\n"),
        PlantedChange(_SHARED_PATH, "SHARED = 'wp02 modified shared.py'\n"),
        PlantedChange(_LEGACY_PATH, None),
    ]


def _assert_fail_block_names_lane_and_recovery(block: str) -> None:
    assert FAIL_WHO in block, f"expected the FAIL verdict block to name '{FAIL_WHO}':\n{block}"
    assert LANE_NAME in block, f"expected the FAIL verdict block to name the lane '{LANE_NAME}':\n{block}"
    assert _RECOVERY_STEP in block, f"expected the FAIL verdict block to carry the recovery step '{_RECOVERY_STEP}':\n{block}"


def test_unsuperseded_canceled_add_modify_delete_fails_and_restores_target(tmp_path: Path) -> None:
    """Add + modify + delete by the canceled WP, under the default (squash) strategy.

    ``shared.py`` and ``legacy.py`` are seeded via ``extra_base_files`` so they
    genuinely PRE-DATE the mission (a plain "canceled WP modifies/deletes a
    pre-existing file" shape). WP01 (the survivor) authors its own unrelated
    commit so the lane carries genuine approved content.
    """
    mission = build_coord_mission_mixed_lane_canceled(
        tmp_path,
        extra_base_files={_SHARED_PATH: _SHARED_BASE_CONTENT, _LEGACY_PATH: _LEGACY_BASE_CONTENT},
        canceled_changes=_add_modify_delete_changes(),
        survivor_before=[PlantedChange(_WP01_OWN_PATH, _WP01_OWN_CONTENT)],
        stamp_attribution=True,
        mid8="01M5046A",
    )
    pre_sha = mission.rev(mission.target_branch)

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])

    flat = collapse(result.stdout + "\n" + result.stderr)
    assert result.returncode != 0, f"canceled WP02 content (add+modify+delete) must be refused by the reconciliation gate, got exit 0:\n{flat}"
    block = verdict_block(flat, FAIL_HEADER)
    _assert_fail_block_names_lane_and_recovery(block)
    assert _FAIL_ADD_MODIFY in clause_for_path(block, _WP02_NEW_PATH), f"expected '{_WP02_NEW_PATH}' clause rendered as '{_FAIL_ADD_MODIFY}':\n{block}"
    assert _FAIL_ADD_MODIFY in clause_for_path(block, _SHARED_PATH), f"expected '{_SHARED_PATH}' clause rendered as '{_FAIL_ADD_MODIFY}':\n{block}"
    assert _FAIL_DELETE in clause_for_path(block, _LEGACY_PATH), f"expected '{_LEGACY_PATH}' clause rendered as '{_FAIL_DELETE}':\n{block}"
    assert mission.rev(mission.target_branch) == pre_sha, "target must be restored to its pre-consolidation SHA on FAIL"
    assert blob_present_at(mission.repo, mission.target_branch, _WP02_NEW_PATH) is False, "canceled WP02's new file must never land on the target"
