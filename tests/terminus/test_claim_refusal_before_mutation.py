"""A claim-integrity REFUSE stops the consolidation BEFORE any mutation.

``_capture_reconciliation_claim`` builds the fail-closed approved-WP claim at
transaction start. A claim carrying a ``refusal`` (e.g. an approved lane branch
that no longer exists), an unresolved surface, or a vacuous claim must act there,
not at the post-mutation gate after lane consolidation, the bake, and the
mission->target squash already moved refs.

Contract (FR-001/FR-002): a claim-integrity refusal exits non-zero with recovery
guidance BEFORE the first mutating phase; the target, coordination/mission
branch and lane branch SHAs, ``state.json`` bookkeeping and the status event
logs are unchanged. A resume whose reconciliation already PASSed for the current
target tip is NOT refused.

Driven through the REAL ``spec-kitty consolidate`` CLI over real git (NFR-004,
nothing mocked). ``pytest.mark.regression`` here means "issue-pinned e2e".

Provenance: #5338 (claim-time refusal), #5021 (already-PASSed resume exemption).

One smoke per behaviour family (#5618 part 2): the resume replay stays end to end. The
fresh-run "leaves no state.json" replay and the already-PASSed resume exemption are
pinned at the seam, each proven by a planted break that turns its guard red: the
claim-integrity refusal not acted on before the first mutation, the fresh record not
cleared on a pre-mutation exit, and ``_resume_reconciliation_already_passed`` always
false. Guards: ``tests/consolidation/test_executor_phase_boundary.py``,
``tests/consolidation/test_claim_integrity_refusal.py``,
``tests/consolidation/test_fresh_record_cleared_on_pre_mutation_exit.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.terminus.conftest import (
    blob_present_at,
    build_coord_mission,
    plant_canceled_commit,
    run_terminus,
)
from tests.terminus.rollback_harness import delete_lane_branch, full_snapshot

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]


def test_resume_claim_refuse_acts_before_any_mutation(tmp_path: Path) -> None:
    """US1-AS1: fresh gate FAIL, then an approved lane branch is deleted, then
    ``--resume``: the claim now REFUSEs and the run must stop pre-mutation."""
    mission = build_coord_mission(tmp_path, wps=("WP01", "WP02"), mid8="01M5338A")
    _, _, planted = plant_canceled_commit(mission, canceled_wp="WP03", carrier_wp="WP02")

    first = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])
    assert first.returncode != 0, f"fixture precondition: the fresh run must gate-FAIL. stdout={first.stdout}\nstderr={first.stderr}"
    assert not blob_present_at(mission.repo, mission.target_branch, planted), "fixture precondition: the failed fresh run must restore the target"

    delete_lane_branch(mission, "WP01")
    before = full_snapshot(mission)
    assert before["state"] is not None, "fixture precondition: the failed fresh run must leave a resumable state.json"

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--resume", "--yes"])
    output = " ".join((result.stdout + result.stderr).split())  # rich wraps long lines

    assert result.returncode != 0, f"a claim-time REFUSE must exit non-zero. output={output}"
    after = full_snapshot(mission)
    assert after["target"] == before["target"], f"target moved during a refused resume ({before['target']} -> {after['target']}). output={output}"
    assert after["coord"] == before["coord"], f"coordination/mission branch moved during a refused resume. output={output}"
    assert after["lanes"] == before["lanes"], f"a lane branch moved during a refused resume. output={output}"
    assert after["state"] == before["state"], f"state.json bookkeeping changed during a refused resume: {before['state']} -> {after['state']}"
    assert after["target_events"] == before["target_events"], "the target status event log changed"
    assert after["coord_events"] == before["coord_events"], "the coordination status event log changed"
    assert not blob_present_at(mission.repo, mission.target_branch, planted), "the canceled file reached the target"
    assert "efused" in output and "does not exist in git" in output, f"expected recovery guidance naming the lane-branch reason. output={output}"
    assert "Squashing" not in output, f"the run reached the squash phase before refusing. output={output}"
