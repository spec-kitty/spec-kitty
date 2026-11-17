"""``consolidate --target develop --retarget`` interrupted by a SIGKILL, then resumed (#7692, WP04 T019).

The kill is a self-SIGKILL at one module-level callable (``retarget_support.kill``); the stale
global merge lock the killed run leaves is removed, as the operator is told to. Scenario and
fixtures: ``test_consolidate_retarget.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.terminus.conftest import _git as git
from tests.terminus.conftest import run_terminus
from tests.terminus.retarget_support import (
    NEW,
    OLD,
    RETARGET,
    assert_landed_on_new_target,
    kill,
    merge_record,
    meta_at,
    retarget_commits,
    tip,
)
from tests.terminus.rollback_harness import flat
from tests.terminus.test_target_override_recorded_target_unwritable import _branches, _check_out_override, _lanes, _reflogs

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def test_resume_after_a_kill_between_the_record_commit_and_its_save_finishes_the_retarget_once(tmp_path: Path) -> None:
    """The kill window between the record commit and the ``committed`` save (plan flag 3).

    The plan documented this window as a residual (``--resume`` refusing ``UNEXPLAINED_BRANCH_MOVE``).
    Witnessed end to end, it is not one: the record commits ran inside the door's advance intents,
    so the resume adopts both moves, the deduplicating record mutate leaves both copies unchanged,
    and the run lands with exactly one retarget commit (NFR-002).
    """
    mission = _lanes(tmp_path, "01M7692K")
    _check_out_override(mission)
    pre_new, pre_old = tip(mission, NEW), tip(mission, OLD)

    killed = kill(mission, "phase_advance", "_persist_retarget_committed", *RETARGET)

    assert killed.returncode != 0, flat(killed)
    record = merge_record(mission)
    assert record is not None and record["retarget"]["committed"] is False, record
    assert retarget_commits(mission, f"{pre_new}..{NEW}") == 1, "the kill came after the record commit"
    assert meta_at(mission, mission.coord_branch)["target_branch"] == NEW, "the Mission branch already holds the record"

    resumed = run_terminus(mission, ["consolidate", "--resume", "--mission", mission.slug, "--yes"])

    assert_landed_on_new_target(mission, resumed, pre_new)
    assert tip(mission, OLD) == pre_old


def test_resume_after_a_kill_past_the_record_finishes_the_retarget_once(tmp_path: Path) -> None:
    """A kill after the record was committed and saved: a mismatching ``--retarget`` refuses; ``--resume`` lands once."""
    mission = _lanes(tmp_path, "01M7692R")
    _check_out_override(mission)
    pre_new, pre_old = tip(mission, NEW), tip(mission, OLD)

    killed = kill(mission, "executor", "_phase_merge_lanes", *RETARGET)

    assert killed.returncode != 0, flat(killed)
    record = merge_record(mission)
    assert record is not None and record["retarget"]["committed"] is True, record
    # The record is on every holder: the Mission branch and the new target.
    assert meta_at(mission, mission.coord_branch)["target_branch"] == NEW
    assert meta_at(mission, NEW)["target_branch"] == NEW

    # T019.4: RETARGET_RESUME_MISMATCH, nothing moved.
    git(mission.repo, "branch", "other", OLD)
    before, reflogs_before = _branches(mission), _reflogs(mission)
    mismatch = run_terminus(mission, ["consolidate", "--resume", "--mission", mission.slug, "--yes", "--target", "other", "--retarget"])
    output = flat(mismatch)
    assert mismatch.returncode == 1, output
    assert "RETARGET_RESUME_MISMATCH" in output, output
    assert "Traceback" not in mismatch.stderr, mismatch.stderr
    assert _branches(mission) == before and _reflogs(mission) == reflogs_before, output

    resumed = run_terminus(mission, ["consolidate", "--resume", "--mission", mission.slug, "--yes"])

    assert_landed_on_new_target(mission, resumed, pre_new)
    assert tip(mission, OLD) == pre_old
