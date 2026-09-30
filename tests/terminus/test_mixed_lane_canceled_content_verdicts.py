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
cannot pass. The exit-0 positive controls for every shape here live in
``test_mixed_lane_canceled_content_controls.py``.

Originally the red-first real-CLI reproductions of #5046 (mission
mixed-lane-authorship-soundness-01M3M7Y0).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.terminus.conftest import (
    PlantedChange,
    blob_present_at,
    build_coord_mission_mixed_lane_canceled,
    build_coord_mission_mixed_lane_with_dependency,
    run_terminus,
)
from tests.terminus.mixed_lane_support import (
    FAIL_HEADER,
    FAIL_WHO,
    LANE_NAME,
    REFUSE_HEADER,
    REFUSE_NO_ATTRIBUTION,
    clause_for_path,
    collapse,
    verdict_block,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

_WP02_NEW_PATH = "src/pkg/wp02_new.py"
_SHARED_PATH = "src/pkg/shared.py"
_LEGACY_PATH = "src/pkg/legacy.py"
_SURVIVOR_PATH = "src/pkg/survivor.py"
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


@pytest.mark.parametrize(
    ("strategy_args", "mid8"),
    [([], "01M5046A"), (["--strategy", "merge"], "01M5046B")],
    ids=["default-squash", "merge"],
)
def test_unsuperseded_canceled_add_modify_delete_fails_and_restores_target(tmp_path: Path, strategy_args: list[str], mid8: str) -> None:
    """Add + modify + delete by the canceled WP, under both strategies.

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
        mid8=mid8,
    )
    pre_sha = mission.rev(mission.target_branch)

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, *strategy_args, "--yes"])

    flat = collapse(result.stdout + "\n" + result.stderr)
    assert result.returncode != 0, f"canceled WP02 content (add+modify+delete) must be refused by the reconciliation gate, got exit 0:\n{flat}"
    block = verdict_block(flat, FAIL_HEADER)
    _assert_fail_block_names_lane_and_recovery(block)
    assert _FAIL_ADD_MODIFY in clause_for_path(block, _WP02_NEW_PATH), f"expected '{_WP02_NEW_PATH}' clause rendered as '{_FAIL_ADD_MODIFY}':\n{block}"
    assert _FAIL_ADD_MODIFY in clause_for_path(block, _SHARED_PATH), f"expected '{_SHARED_PATH}' clause rendered as '{_FAIL_ADD_MODIFY}':\n{block}"
    assert _FAIL_DELETE in clause_for_path(block, _LEGACY_PATH), f"expected '{_LEGACY_PATH}' clause rendered as '{_FAIL_DELETE}':\n{block}"
    assert mission.rev(mission.target_branch) == pre_sha, "target must be restored to its pre-consolidation SHA on FAIL"
    assert blob_present_at(mission.repo, mission.target_branch, _WP02_NEW_PATH) is False, "canceled WP02's new file must never land on the target"


def test_survivor_undone_content_is_refused_as_fail(tmp_path: Path) -> None:
    """Two survivor-undone shapes in one build.

    Shape A: WP01 adds ``survivor.py``; canceled WP02 deletes it.
    Shape B: the mission base carries ``shared.py`` at v0; WP01 modifies it to
    v1; canceled WP02 writes it back to EXACTLY the base v0 bytes.

    A naive "compare with the mission base" check sees both final states as
    equal to the mission base and drops the finding, shipping the undo of
    WP01's approved work. The pre-state rule must compare against what a
    SURVIVING lane commit produced immediately before WP02's own change.
    """
    mission = build_coord_mission_mixed_lane_canceled(
        tmp_path,
        extra_base_files={_SHARED_PATH: _SHARED_BASE_CONTENT},
        canceled_changes=[
            PlantedChange(_SURVIVOR_PATH, None),
            PlantedChange(_SHARED_PATH, _SHARED_BASE_CONTENT),
        ],
        survivor_before=[
            PlantedChange(_SURVIVOR_PATH, "def survivor() -> str:\n    return 'wp01 survivor'\n"),
            PlantedChange(_SHARED_PATH, "SHARED = 'wp01 improvement v1'\n"),
        ],
        stamp_attribution=True,
        mid8="01M5046C",
    )
    pre_sha = mission.rev(mission.target_branch)

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])

    flat = collapse(result.stdout + "\n" + result.stderr)
    assert result.returncode != 0, f"a canceled WP02 undoing WP01's approved work (deletion + revert-to-mission-base) must be refused, got exit 0:\n{flat}"
    block = verdict_block(flat, FAIL_HEADER)
    _assert_fail_block_names_lane_and_recovery(block)
    assert _FAIL_DELETE in clause_for_path(block, _SURVIVOR_PATH), f"expected the deleted survivor.py clause rendered as '{_FAIL_DELETE}':\n{block}"
    assert _FAIL_ADD_MODIFY in clause_for_path(block, _SHARED_PATH), f"expected the reverted shared.py clause rendered as '{_FAIL_ADD_MODIFY}':\n{block}"
    assert mission.rev(mission.target_branch) == pre_sha, "target must be restored to its pre-consolidation SHA on FAIL"


def test_no_commit_attribution_is_refused_as_refuse(tmp_path: Path) -> None:
    """WP02 committed real content but no lifecycle event carries a
    ``policy_metadata.lane_head`` stamp: the gate cannot resolve a work window
    and must fail closed (REFUSE) rather than guess.
    """
    mission = build_coord_mission_mixed_lane_canceled(
        tmp_path,
        canceled_changes=[PlantedChange(_WP02_NEW_PATH, "def wp02_new() -> str:\n    return 'wp02 leaked'\n")],
        stamp_attribution=False,
        mid8="01M5046D",
    )
    pre_sha = mission.rev(mission.target_branch)

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])

    flat = collapse(result.stdout + "\n" + result.stderr)
    assert result.returncode != 0, f"canceled WP02 content with no commit-attribution stamp must be REFUSEd (fail-closed), got exit 0:\n{flat}"
    block = verdict_block(flat, REFUSE_HEADER)
    assert "WP02" in block, f"expected the REFUSE verdict block to name WP02:\n{block}"
    assert REFUSE_NO_ATTRIBUTION in block, f"expected the REFUSE verdict block to carry '{REFUSE_NO_ATTRIBUTION}':\n{block}"
    assert LANE_NAME in block, f"expected the REFUSE verdict block to name the lane '{LANE_NAME}':\n{block}"
    assert _RECOVERY_STEP in block, f"expected the REFUSE verdict block to carry the recovery step '{_RECOVERY_STEP}':\n{block}"
    assert mission.rev(mission.target_branch) == pre_sha, "target must be restored to its pre-consolidation SHA on REFUSE"


def test_dependency_lane_with_leaked_canceled_content_fails_not_refuses(tmp_path: Path) -> None:
    """A dependent mixed lane whose first-parent spine carries a dependency
    lane's fast-forwarded commits, plus leaked canceled content, is the content
    FAIL -- never a closed-world REFUSE over the dependency lane's commits.
    """
    mission = build_coord_mission_mixed_lane_with_dependency(tmp_path, canceled_leaks=True, mid8="01M5046K")
    pre_sha = mission.rev(mission.target_branch)
    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])
    flat = collapse(result.stdout + "\n" + result.stderr)
    assert result.returncode != 0
    assert REFUSE_HEADER not in flat, f"must be the content FAIL, not a closed-world REFUSE:\n{flat}"
    assert FAIL_HEADER in flat and f"'{_WP02_NEW_PATH}'" in flat, flat
    assert mission.rev(mission.target_branch) == pre_sha
