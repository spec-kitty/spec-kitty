"""The consolidate claim builder runs the evidence axis on a lanes Mission (#6715).

``tests/integration/test_6715_consolidate_lane_evidence.py`` drives the whole command; this file
pins the axis where ``consolidate`` actually asks it — inside
:func:`~specify_cli.consolidation.reconciliation.build_approved_wp_set`, over the real LANES
fixture (real git, real lane branches, real approval stamps) — so a refusal is proven to happen at
claim time, before any branch moves, and the admitting case is proven on the same fixture.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.consolidation import wp_evidence
from specify_cli.consolidation.reconciliation import ApprovedWpCommitSet, build_approved_wp_set
from specify_cli.lanes.persistence import read_lanes_json, write_lanes_json
from tests.terminus.conftest import CoordMission, _git, git_rev
from tests.terminus.lanes_fixture import build_lanes_mission

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _claim(mission: CoordMission) -> ApprovedWpCommitSet:
    manifest = read_lanes_json(mission.feature_dir)
    assert manifest is not None
    return build_approved_wp_set(mission.repo, mission.feature_dir, manifest, coord_base_ref=mission.coord_branch)


def _empty_the_lane(mission: CoordMission, wp_id: str = "WP01") -> None:
    """Reset the work package's lane branch to the commit it was cut from: an approved, empty lane."""
    branch = mission.lane_branches[wp_id]
    _git(mission.repo, "update-ref", f"refs/heads/{branch}", git_rev(mission.repo, mission.coord_branch))


def test_claim_admits_an_approved_lane_with_an_owned_commit_and_an_independent_review(tmp_path: Path) -> None:
    mission = build_lanes_mission(tmp_path, wps=("WP01", "WP02"))

    claim = _claim(mission)

    assert claim.refusal is None
    assert set(claim.approved) == {"WP01", "WP02"}
    assert claim.no_implementation_attested_wp_ids == frozenset()


def test_claim_refuses_an_approved_lane_with_no_owned_commit(tmp_path: Path) -> None:
    mission = build_lanes_mission(tmp_path, wps=("WP01", "WP02"))
    _empty_the_lane(mission, "WP01")

    claim = _claim(mission)

    assert claim.refusal is not None
    assert wp_evidence._refusal_codes(claim.refusal) == [wp_evidence.IMPLEMENTATION_MISSING]
    assert "IMPLEMENTATION_MISSING: WP01" in claim.refusal
    assert "IMPLEMENTATION_MISSING: WP02" not in claim.refusal
    assert not claim.approved, "a refused claim carries no approved commits"


def test_claim_refuses_a_lanes_mission_with_no_recorded_planning_commit(tmp_path: Path) -> None:
    mission = build_lanes_mission(tmp_path, wps=("WP01",))
    manifest = read_lanes_json(mission.feature_dir)
    assert manifest is not None
    manifest.planning_commit_sha = None
    write_lanes_json(mission.feature_dir, manifest)

    claim = _claim(mission)

    assert claim.refusal is not None
    assert wp_evidence._refusal_codes(claim.refusal) == [wp_evidence.EVIDENCE_WINDOW_UNCOMPUTABLE]
    assert "finalize-tasks" in claim.refusal


def test_an_attested_work_package_is_admitted_and_named(tmp_path: Path) -> None:
    """A no-implementation attestation (WP02's record shape) lifts the refusal for its work package only."""
    mission = build_lanes_mission(tmp_path, wps=("WP01", "WP02"))
    _empty_the_lane(mission, "WP01")
    log = mission.feature_dir / "status.events.jsonl"
    events = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
    attestation = {
        **events[-1],
        "event_id": "01HXYZ6715000000000000ATTE",
        "wp_id": "WP01",
        "from_lane": "approved",
        "to_lane": "approved",
        "force": True,
        "actor": "operator",
        "reason_source": "operator",
        "reason": "operator attests no implementation is owed: WP01 ships no deliverable",
        "policy_metadata": {"attestation": wp_evidence.NO_IMPLEMENTATION},
    }
    log.write_text("\n".join(json.dumps(event) for event in [*events, attestation]) + "\n", encoding="utf-8")
    _git(mission.repo, "add", "--", str(log.relative_to(mission.repo)))
    _git(mission.repo, "commit", "-qm", "chore: record the no-implementation attestation")

    claim = _claim(mission)

    assert claim.refusal is None
    assert claim.no_implementation_attested_wp_ids == frozenset({"WP01"})
