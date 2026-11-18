"""``consolidate --target develop --retarget``: a failure after the record commit, a re-run, ``--abort`` (#7692, WP04 T019).

The failure is a ``RuntimeError`` raised from ``executor._phase_merge_lanes``, the phase right
after ``_phase_retarget_record``, through a ``-c`` wrapper (``retarget_support.run_patched``), so
it lands inside the one rollback door. Scenario and fixtures: ``test_consolidate_retarget.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.terminus.retarget_support import NEW, OLD, RETARGET, assert_landed_on_new_target, merge_record, meta_at, run_patched, tip
from tests.terminus.rollback_harness import assert_report_is_truthful, flat
from tests.terminus.conftest import run_terminus
from tests.terminus.test_target_override_recorded_target_unwritable import (
    _assert_refused_before_any_mutation,
    _branches,
    _check_out_override,
    _consolidate,
    _coord,
    _lanes,
    _merge_records,
    _reflogs,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


@pytest.mark.parametrize("build", [_lanes, _coord], ids=["lanes", "coord"])
def test_failure_after_the_retarget_commit_rolls_it_back_and_a_rerun_lands_once(tmp_path: Path, build) -> None:  # type: ignore[no-untyped-def]
    """SC-003 + NFR-002: a failure inside the door undoes the record on every holder; the re-run commits it once."""
    mission = build(tmp_path, "01M7692F")
    _check_out_override(mission)
    pre_new, pre_mission = tip(mission, NEW), tip(mission, mission.coord_branch)

    failed = run_patched(mission, "executor", "_phase_merge_lanes", *RETARGET, kill=False)

    output = flat(failed)
    assert failed.returncode != 0, output
    assert "Retarget recorded: main -> develop" in output, f"the failure must come after the retarget commit. output={output}"
    assert_report_is_truthful(output)
    assert tip(mission, NEW) == pre_new, f"the new target is back at its pre-run tip. output={output}"
    assert meta_at(mission, NEW)["target_branch"] == OLD, output
    # Both holders took the record (the coord Mission branch carries meta.json too): both are restored.
    assert tip(mission, mission.coord_branch) == pre_mission, output
    assert meta_at(mission, mission.coord_branch)["target_branch"] == OLD, output
    record = merge_record(mission)
    assert record is not None and isinstance(record.get("retarget"), dict), record
    assert (record["retarget"]["from"], record["retarget"]["to"], record["retarget"]["committed"]) == (OLD, NEW, False), record

    rerun = _consolidate(mission, *RETARGET)

    assert_landed_on_new_target(mission, rerun, pre_new)


def test_abort_after_a_failed_retarget_restores_and_a_plain_override_is_refused_again(tmp_path: Path) -> None:
    """``--abort`` leaves no record and ``develop`` at its pre-run tip; without ``--retarget`` the #5783 refusal stands."""
    mission = _lanes(tmp_path, "01M7692A")
    _check_out_override(mission)
    pre_new = tip(mission, NEW)
    failed = run_patched(mission, "executor", "_phase_merge_lanes", *RETARGET, kill=False)
    assert failed.returncode != 0, flat(failed)

    aborted = run_terminus(mission, ["consolidate", "--abort", "--mission", mission.slug])

    assert aborted.returncode == 0, flat(aborted)
    assert _merge_records(mission) == [], flat(aborted)
    assert tip(mission, NEW) == pre_new, flat(aborted)
    before, reflogs_before = _branches(mission), _reflogs(mission)

    plain = _consolidate(mission, "--target", NEW)

    _assert_refused_before_any_mutation(mission, plain, before, reflogs_before)


def _attestations(mission, ref: str) -> int:  # type: ignore[no-untyped-def]
    from tests.terminus.retarget_support import events_at

    return sum(1 for event in events_at(mission, ref) if (event.get("policy_metadata") or {}).get("attestation") == "no_implementation")


def test_a_retargeted_attestation_is_undone_with_the_failed_run_and_recorded_once_on_the_rerun(tmp_path: Path) -> None:
    """Mission review RISK-2: on a coordination-less Mission the attestation lands on ``develop``.

    It is part of the run, so the one rollback authority undoes it with the run: ``develop`` is
    back at its pre-run tip after the failure and stays there after ``--abort``; the re-run then
    records the attestation exactly once and lands.
    """
    from tests.terminus.retarget_support import REASON, log_subjects

    attest = ("--attest-no-implementation", "WP01", "--attest-reason", REASON)
    mission = _lanes(tmp_path, "01M7692W")
    _check_out_override(mission)
    pre_new = tip(mission, NEW)
    assert _attestations(mission, NEW) == 0

    failed = run_patched(mission, "executor", "_phase_merge_lanes", *RETARGET, *attest, kill=False)

    output = flat(failed)
    assert failed.returncode != 0, output
    assert "Retarget recorded: main -> develop" in output, output
    assert_report_is_truthful(output)
    assert tip(mission, NEW) == pre_new, f"the attestation is undone with the run. log={log_subjects(mission, f'{pre_new}..{NEW}')} output={output}"
    assert _attestations(mission, NEW) == 0, output
    assert meta_at(mission, NEW)["target_branch"] == OLD, output

    aborted = run_terminus(mission, ["consolidate", "--abort", "--mission", mission.slug])

    assert aborted.returncode == 0, flat(aborted)
    assert _merge_records(mission) == [], flat(aborted)
    assert tip(mission, NEW) == pre_new, flat(aborted)

    rerun = _consolidate(mission, *RETARGET, *attest)

    assert_landed_on_new_target(mission, rerun, pre_new)
    assert _attestations(mission, NEW) == 1, flat(rerun)


def test_a_retargeted_attestation_is_undone_on_a_rerun_after_the_failure(tmp_path: Path) -> None:
    """The same attestation undone by the failure, then the re-run (no ``--abort``) records it once and lands."""
    from tests.terminus.retarget_support import REASON

    attest = ("--attest-no-implementation", "WP01", "--attest-reason", REASON)
    mission = _lanes(tmp_path, "01M7692V")
    _check_out_override(mission)
    pre_new = tip(mission, NEW)
    failed = run_patched(mission, "executor", "_phase_merge_lanes", *RETARGET, *attest, kill=False)
    assert failed.returncode != 0 and tip(mission, NEW) == pre_new, flat(failed)

    rerun = _consolidate(mission, *RETARGET, *attest)

    assert_landed_on_new_target(mission, rerun, pre_new)
    assert _attestations(mission, NEW) == 1, flat(rerun)


@pytest.mark.parametrize(
    ("module", "name"),
    [("phase_claim", "_capture_snapshot_and_begin_attempt"), ("rollback", "begin_attempt")],
    ids=["before-the-snapshot", "between-snapshot-and-attempt"],
)
def test_a_kill_after_the_attestation_still_lets_the_resume_undo_it(tmp_path: Path, module: str, name: str) -> None:
    """Review R2-a: a SIGKILL between the attestation commit and the attempt's start must not make it permanent.

    The killed run leaves the record (and, past the snapshot, the snapshot). A ``--resume`` that then
    fails inside the door restores ``develop`` to its tip from before the attestation.
    """
    from tests.terminus.retarget_support import REASON, kill

    attest = ("--attest-no-implementation", "WP01", "--attest-reason", REASON)
    mission = _lanes(tmp_path, "01M7692J")
    _check_out_override(mission)
    pre_new = tip(mission, NEW)

    killed = kill(mission, module, name, *RETARGET, *attest)

    assert killed.returncode != 0, flat(killed)
    assert _attestations(mission, NEW) == 1, "the kill came after the attestation commit"
    resumed = run_patched(mission, "executor", "_phase_merge_lanes", "--resume", kill=False)

    assert resumed.returncode != 0, flat(resumed)
    assert tip(mission, NEW) == pre_new, f"the resume's rollback undoes the attestation. output={flat(resumed)}"
    assert _attestations(mission, NEW) == 0


def test_abort_after_a_kill_past_the_snapshot_undoes_the_attestation(tmp_path: Path) -> None:
    """Review R2-a: ``--abort`` after a SIGKILL between the snapshot and the attempt start restores ``develop``."""
    from tests.terminus.retarget_support import REASON, kill

    attest = ("--attest-no-implementation", "WP01", "--attest-reason", REASON)
    mission = _lanes(tmp_path, "01M7692H")
    _check_out_override(mission)
    pre_new = tip(mission, NEW)
    killed = kill(mission, "rollback", "begin_attempt", *RETARGET, *attest)
    assert killed.returncode != 0, flat(killed)

    aborted = run_terminus(mission, ["consolidate", "--abort", "--mission", mission.slug])

    assert aborted.returncode == 0, flat(aborted)
    assert tip(mission, NEW) == pre_new, flat(aborted)
    assert _merge_records(mission) == []


def test_a_rerun_with_the_flags_after_a_kill_undoes_both_attestations(tmp_path: Path) -> None:
    """Re-review MEDIUM-1: kill before the snapshot, re-run WITH the ``--attest-*`` flags, then fail.

    The re-run attests again (a1 -> a2); the undo must chain to the first attestation's origin, so
    the rollback leaves ``develop`` at its pre-run tip with no attestation event.
    """
    from tests.terminus.retarget_support import REASON, kill

    attest = ("--attest-no-implementation", "WP01", "--attest-reason", REASON)
    mission = _lanes(tmp_path, "01M7692G")
    _check_out_override(mission)
    pre_new = tip(mission, NEW)
    killed = kill(mission, "phase_claim", "_capture_snapshot_and_begin_attempt", *RETARGET, *attest)
    assert killed.returncode != 0 and _attestations(mission, NEW) == 1, flat(killed)

    rerun = run_patched(mission, "executor", "_phase_merge_lanes", *RETARGET, *attest, kill=False)

    assert rerun.returncode != 0, flat(rerun)
    assert tip(mission, NEW) == pre_new, f"both attestations are undone. output={flat(rerun)}"
    assert _attestations(mission, NEW) == 0
