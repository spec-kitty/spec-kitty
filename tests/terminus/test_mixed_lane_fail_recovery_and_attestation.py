"""The operator recovery paths out of a mixed-lane FAIL work end to end: re-run and supersede-and-re-run.

* A re-run after a FAIL repeats the FAIL: the ``migration:backfill_runtime_state``
  seed events the first run's birth-cutover backfill appends (``planned ->
  claimed``, no ``lane_head`` stamp) never re-open a work window (spec FR-011).
* The FAIL's printed recovery -- supersede the canceled content through a
  surviving WP's governed rework, re-run -- consolidates at exit 0.

The canceled-superseded attestation replays (an unstamped lane REFUSEs naming the flag,
then consolidates with it and records the operator-provenance event; the flag refused for
a WP that is not canceled; the ``--dry-run`` not-applied notice) are pinned at the seam
(#5618 part 2): ``tests/consolidation/test_canceled_attestation.py`` and
``tests/consolidation/test_reconciliation.py`` go red when the not-canceled check is
removed, the dry-run notice is dropped, an attested WP no longer lifts the overridable
REFUSE, or the recorded event loses ``force`` / ``reason_source``. They do NOT go red when
``executor._record_operator_attestations`` stops recording the flag at all; that is caught by
``tests/terminus/test_canceled_dependency_fast_forward_verdicts.py`` and
``tests/terminus/test_mixed_lane_closed_world.py::test_straggler_after_the_attestation_still_refuses``.

Every test drives the REAL ``spec-kitty consolidate`` CLI
(:func:`tests.terminus.conftest.run_terminus`) against a real on-disk
coordination mission; the surviving WP's rework goes through the production
transactional status shell, never a hand-written stamp.

Originally the #5046 post-acceptance landing-blocker reproductions (mission
mixed-lane-authorship-soundness-01M3M7Y0).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.status.models import ReviewResult
from tests.terminus.conftest import (
    CoordMission,
    PlantedChange,
    blob_present_at,
    build_coord_mission_mixed_lane_canceled,
    run_terminus,
)
from tests.terminus.conftest import _git as git
from tests.terminus.mixed_lane_support import (
    FAIL_HEADER,
    collapse,
    ensure_wp01_subtasks_roster,
    transition,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

_LEAKED_PATH = "src/pkg/wp02_new.py"
_WP01_PATH = "src/pkg/wp01.py"
_OPEN_WINDOW = "never closed"
_ACTOR = "landing-recovery-test"


def _consolidate(mission: CoordMission, *extra: str) -> tuple[int, str]:
    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes", *extra])
    return result.returncode, collapse(result.stdout + "\n" + result.stderr)


def _build_failing_mixed_lane(tmp_path: Path, mid8: str) -> CoordMission:
    """Stamped mixed lane: WP01 approved, WP02 added an unsuperseded file, then canceled."""
    return build_coord_mission_mixed_lane_canceled(
        tmp_path,
        canceled_changes=[PlantedChange(_LEAKED_PATH, "def wp02_new() -> str:\n    return 'wp02 leaked'\n")],
        survivor_before=[PlantedChange(_WP01_PATH, "def wp01() -> str:\n    return 'ok'\n")],
        stamp_attribution=True,
        mid8=mid8,
    )


def _supersede_through_wp01_rework(mission: CoordMission) -> None:
    """WP01 (recorded ``done`` by the first, failed run's bookkeeping) is reopened and
    reworked through the production shell: its rework deletes WP02's leaked file."""
    lane_branch = mission.lane_branches["WP01"]
    transition(mission, "WP01", "in_progress", actor=_ACTOR, force=True, reason="rework: remove canceled WP02's leftover file")
    git(mission.repo, "checkout", "-q", lane_branch)
    git(mission.repo, "rm", "-q", _LEAKED_PATH)
    git(mission.repo, "commit", "-qm", "wp01 rework removes canceled wp02's file")
    git(mission.repo, "checkout", "-q", mission.target_branch)
    transition(mission, "WP01", "for_review", actor=_ACTOR, subtasks_complete=True)
    transition(mission, "WP01", "in_review", actor=_ACTOR)
    transition(
        mission,
        "WP01",
        "approved",
        actor=_ACTOR,
        review_result=ReviewResult(reviewer=_ACTOR, verdict="approved", reference="review-wp01-recovery"),
    )


def test_rerun_after_fail_fails_again_not_open_window_refuse(tmp_path: Path) -> None:
    """A re-run with no change reports the SAME FAIL -- the backfill seed events
    the first run appended must not turn it into an ``open_window`` REFUSE."""
    mission = _build_failing_mixed_lane(tmp_path, "01M5046T")
    pre_sha = mission.rev(mission.target_branch)

    first_rc, first = _consolidate(mission)
    assert first_rc != 0 and FAIL_HEADER in first, f"first run must FAIL on WP02's leaked file:\n{first}"
    assert mission.rev(mission.target_branch) == pre_sha

    second_rc, second = _consolidate(mission)
    assert second_rc != 0, f"re-run with no change must not exit 0:\n{second}"
    assert _OPEN_WINDOW not in second, f"migration seed events must not re-open a work window (FR-011):\n{second}"
    assert FAIL_HEADER in second, f"re-run must repeat the FAIL verdict:\n{second}"
    assert f"'{_LEAKED_PATH}'" in second
    assert mission.rev(mission.target_branch) == pre_sha


def test_supersede_after_fail_then_rerun_passes(tmp_path: Path) -> None:
    """The FAIL's own recovery (revert through a surviving WP's governed work,
    re-run) succeeds -- exit 0, and the canceled file is not on the target."""
    mission = _build_failing_mixed_lane(tmp_path, "01M5046U")
    ensure_wp01_subtasks_roster(mission)

    first_rc, first = _consolidate(mission)
    assert first_rc != 0 and FAIL_HEADER in first, f"first run must FAIL on WP02's leaked file:\n{first}"

    _supersede_through_wp01_rework(mission)

    rc, out = _consolidate(mission)
    assert rc == 0, f"after a superseding WP01 rework the re-run must consolidate cleanly:\n{out}"
    assert blob_present_at(mission.repo, mission.target_branch, _LEAKED_PATH) is False
    assert blob_present_at(mission.repo, mission.target_branch, _WP01_PATH) is True
