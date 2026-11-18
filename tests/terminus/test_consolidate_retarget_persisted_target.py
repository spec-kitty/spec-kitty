"""A persisted retarget binds every later run, with or without ``--retarget`` (#7692, mission review RISK-1).

A retarget run that fails inside the rollback door re-baselines its merge record with the
retarget still in it (``main -> develop``, ``committed: False``). A later run that names any
other target, ``--target main`` (the recorded target) included, must refuse up front with
``RETARGET_RESUME_MISMATCH``: before this fix the entry preflight judged ``main`` and found no
retarget, then the locked run silently re-applied the persisted one, committed the record on the
Mission branch and rolled it back (a branch moved and came back), and ``--dry-run`` forecast a
clean run. Scenario and fixtures: ``test_consolidate_retarget.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.terminus.conftest import _git as git
from tests.terminus.conftest import blob_present_at, run_terminus
from tests.terminus.retarget_support import CODE_FILE, NEW, OLD, RETARGET, dry_run, kitty_specs_status, merge_record, run_patched, tip
from tests.terminus.rollback_harness import flat, reflog_shas
from tests.terminus.test_target_override_recorded_target_unwritable import _branches, _check_out_override, _coord, _lanes

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_CODE = "RETARGET_RESUME_MISMATCH"


@pytest.mark.parametrize("build", [_lanes, _coord], ids=["lanes", "coord"])
def test_target_naming_the_recorded_target_after_a_failed_retarget_is_refused_up_front(tmp_path: Path, build) -> None:  # type: ignore[no-untyped-def]
    mission = build(tmp_path, "01M7692T")
    _check_out_override(mission)
    failed = run_patched(mission, "executor", "_phase_merge_lanes", *RETARGET, kill=False)
    assert failed.returncode != 0, flat(failed)
    record_before = merge_record(mission)
    assert record_before is not None and (record_before["retarget"]["from"], record_before["retarget"]["to"]) == (OLD, NEW), record_before

    git(mission.repo, "checkout", "-q", OLD)
    watched = (OLD, NEW, mission.coord_branch)
    before = _branches(mission)
    reflogs_before = {branch: reflog_shas(mission, branch) for branch in watched}
    status_before = kitty_specs_status(mission)

    forecast, payload = dry_run(mission, "--target", OLD)
    assert forecast.returncode == 1, flat(forecast)
    assert payload.get("error_code") == _CODE, payload

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes", "--target", OLD])

    output = flat(result)
    assert result.returncode == 1, output
    assert _CODE in output, output
    assert f"'{OLD}' to '{NEW}'" in output and f"--target {NEW} --retarget" in output, output
    assert "Traceback" not in result.stderr, result.stderr
    assert "Retarget recorded" not in output, f"the persisted retarget must not run again. output={output}"
    assert _branches(mission) == before, output
    assert {branch: reflog_shas(mission, branch) for branch in watched} == reflogs_before, f"no branch may move and come back. output={output}"
    assert merge_record(mission) == record_before, "the refusal leaves the merge record as it was"
    assert kitty_specs_status(mission) == status_before, output
    assert not blob_present_at(mission.repo, OLD, CODE_FILE) and not blob_present_at(mission.repo, NEW, CODE_FILE), output
    assert tip(mission, NEW) == before[NEW]


def test_abort_is_the_escape_route_back_to_the_old_target(tmp_path: Path) -> None:
    """Review item 6: after the refusal, ``--abort`` drops the persisted retarget and ``--target main`` lands there."""
    mission = _lanes(tmp_path, "01M7692E")
    _check_out_override(mission)
    pre_new = tip(mission, NEW)
    failed = run_patched(mission, "executor", "_phase_merge_lanes", *RETARGET, kill=False)
    assert failed.returncode != 0, flat(failed)
    git(mission.repo, "checkout", "-q", OLD)

    aborted = run_terminus(mission, ["consolidate", "--abort", "--mission", mission.slug])
    assert aborted.returncode == 0, flat(aborted)
    assert merge_record(mission) is None

    landed = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes", "--target", OLD])

    assert landed.returncode == 0, flat(landed)
    assert blob_present_at(mission.repo, OLD, CODE_FILE), flat(landed)
    assert tip(mission, NEW) == pre_new and not blob_present_at(mission.repo, NEW, CODE_FILE)
