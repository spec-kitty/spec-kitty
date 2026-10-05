"""#5668 -- an approval that recorded no lane head refuses, and only the operator can lift that, and only that.

``consolidate`` refuses a work package in the approved claim whose approval carries no
``lane_head`` stamp (``APPROVAL_STAMP_MISSING``): without a stamp nothing bounds the claim.
The operator who checked the lane by hand records that with
``--attest-approved-reviewed <WP> --attest-reason "<why>"``. The attestation is a forced
operator transition in the mission's status log whose own ``lane_head`` becomes the bound,
so a commit added after it is still refused.

Driven through the REAL ``spec-kitty consolidate`` CLI (a subprocess). The stamp-less
approval is the production shape of a mission approved before the stamp existed:
:func:`tests.terminus.post_approval_support.strip_approval_stamps` removes it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.consolidation.approved_bound import APPROVED_REVIEWED, ATTEST_APPROVED_FLAG
from specify_cli.coordination.surface_resolver import resolve_status_surface
from tests.terminus.canceled_dependency_support import LANE_A
from tests.terminus.conftest import CoordMission, blob_present_at, git_rev, run_terminus
from tests.terminus.mixed_lane_support import collapse
from tests.terminus.post_approval_support import (
    WP01_PATH,
    Topology,
    add_post_approval_commit,
    build_post_approval_mission,
    strip_approval_stamps,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

_BANNER = "Reconciliation verified"
_MISSING = "APPROVAL_STAMP_MISSING"
_REASON = "read every line of lane-a; it is the reviewed work"


def _consolidate(mission: CoordMission, *flags: str) -> tuple[int, str]:
    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes", *flags])
    return result.returncode, collapse(result.stdout + "\n" + result.stderr)


def _attest(wp_id: str, reason: str = _REASON) -> tuple[str, ...]:
    return (ATTEST_APPROVED_FLAG, wp_id, "--attest-reason", reason)


def _status_log(mission: CoordMission) -> list[dict[str, object]]:
    log = resolve_status_surface(mission.repo, mission.slug)
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]


def _metadata(event: dict[str, object]) -> dict[str, object]:
    metadata = event.get("policy_metadata")
    return metadata if isinstance(metadata, dict) else {}


def _attestations(mission: CoordMission, wp_id: str) -> list[dict[str, object]]:
    return [event for event in _status_log(mission) if event["wp_id"] == wp_id and _metadata(event).get("attestation") == APPROVED_REVIEWED]


@pytest.mark.parametrize("topology", ["lanes", "coord"])
def test_unstamped_approval_refuses_then_attestation_consolidates(tmp_path: Path, topology: Topology) -> None:
    mission = build_post_approval_mission(tmp_path, topology)
    strip_approval_stamps(mission, "WP01")
    target = git_rev(mission.repo, mission.target_branch)

    rc, flat = _consolidate(mission)
    assert rc != 0 and _MISSING in flat, f"an unstamped approval must refuse:\n{flat}"
    assert "WP01" in flat and f"{ATTEST_APPROVED_FLAG} WP01" in flat and "move-task WP01" in flat, f"both remedies must be named:\n{flat}"
    assert _BANNER not in flat
    assert git_rev(mission.repo, mission.target_branch) == target

    rc, flat = _consolidate(mission, ATTEST_APPROVED_FLAG, "WP01")
    assert rc == 2 and "requires --attest-reason" in flat, f"the attestation needs a reason:\n{flat}"
    assert not _attestations(mission, "WP01")

    log_before = _status_log(mission)
    rc, flat = _consolidate(mission, "--dry-run", *_attest("WP01"))
    assert f"{ATTEST_APPROVED_FLAG} is not applied with --dry-run" in flat, flat
    assert _status_log(mission) == log_before, "a dry run records nothing"

    rc, flat = _consolidate(mission, *_attest("WP01"))
    assert rc == 0, f"an attested approval must consolidate:\n{flat}"
    assert _BANNER in flat
    assert blob_present_at(mission.repo, mission.target_branch, WP01_PATH)
    (attestation,) = _attestations(mission, "WP01")
    assert attestation["reason_source"] == "operator" and attestation["force"] is True
    assert _REASON in str(attestation["reason"])
    assert _metadata(attestation)["lane_head"] == git_rev(mission.repo, mission.lane_branches["WP01"])


def test_commit_after_the_attestation_is_refused(tmp_path: Path) -> None:
    mission = build_post_approval_mission(tmp_path, "lanes")
    strip_approval_stamps(mission, "WP01")
    rc, _ = _consolidate(mission, "--dry-run")
    assert rc == 0
    from specify_cli.consolidation.approved_attestation import record_approved_reviewed_attestation

    record_approved_reviewed_attestation(
        repo_root=mission.repo,
        feature_dir=mission.feature_dir,
        mission_slug=mission.slug,
        wp_id="WP01",
        current_lane="approved",
        reason=_REASON,
        actor="landing-test-operator",
    )
    late = add_post_approval_commit(mission, LANE_A)

    rc, flat = _consolidate(mission)

    assert rc != 0 and "LANE_MOVED_AFTER_APPROVAL" in flat and late[:7] in flat, f"a commit after the attestation must refuse:\n{flat}"
