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

from specify_cli.consolidation.approved_attestation import record_approved_reviewed_attestation
from specify_cli.consolidation.approved_bound import APPROVED_REVIEWED, ATTEST_APPROVED_FLAG
from specify_cli.coordination.status_transition import emit_status_transition_transactional
from specify_cli.coordination.surface_resolver import resolve_status_surface
from specify_cli.status import TransitionRequest
from tests.terminus.canceled_dependency_support import ACTOR, LANE_A
from tests.terminus.conftest import CoordMission, blob_present_at, git_rev, run_terminus
from tests.terminus.conftest import _git as run_git
from tests.terminus.mixed_lane_support import collapse
from tests.terminus.post_approval_support import (
    LATE_PATH,
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


def _is_approval_of(line: str, wp_id: str) -> bool:
    event = json.loads(line)
    return bool(event["wp_id"] == wp_id and event["to_lane"] == "approved")


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
    lane_tip = git_rev(mission.repo, mission.lane_branches["WP01"])

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
    assert _metadata(attestation)["lane_head"] == lane_tip


def test_commit_after_the_attestation_is_refused(tmp_path: Path) -> None:
    mission = build_post_approval_mission(tmp_path, "lanes")
    strip_approval_stamps(mission, "WP01")
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


@pytest.mark.parametrize("lane_merged_into_mission", [False, True])
def test_repeating_the_attestation_after_a_late_commit_is_refused(tmp_path: Path, lane_merged_into_mission: bool) -> None:
    """Attest, commit unreviewed content, attest again: the repeat must not read as approving the new content.

    Also when the lane (late commit included) was merged into the mission branch in between:
    the mission branch reaching the late commit must not exempt it.
    """
    mission = build_post_approval_mission(tmp_path, "lanes")
    strip_approval_stamps(mission, "WP01")
    record_approved_reviewed_attestation(
        repo_root=mission.repo,
        feature_dir=mission.feature_dir,
        mission_slug=mission.slug,
        wp_id="WP01",
        current_lane="approved",
        reason=_REASON,
        actor="landing-test-operator",
    )
    add_post_approval_commit(mission, LANE_A)
    if lane_merged_into_mission:
        scratch = tmp_path / "mission-scratch"
        run_git(mission.repo, "worktree", "add", "-q", str(scratch), mission.coord_branch)
        run_git(scratch, "merge", "-q", "--no-ff", "--no-edit", mission.lane_branches["WP01"])
        run_git(mission.repo, "worktree", "remove", "--force", str(scratch))
    log_before = _status_log(mission)
    target = git_rev(mission.repo, mission.target_branch)

    rc, flat = _consolidate(mission, *_attest("WP01"))

    assert rc == 1 and "cannot be repeated for WP01" in flat, f"a repeated attestation must refuse once the lane moved:\n{flat}"
    assert "moved past the earlier attestation" in flat and "Nothing was recorded." in flat, flat
    assert _status_log(mission) == log_before, "a refused repeat records nothing"
    assert git_rev(mission.repo, mission.target_branch) == target
    assert not blob_present_at(mission.repo, mission.target_branch, LATE_PATH)


def test_attestation_is_refused_for_an_approval_that_already_has_a_stamp(tmp_path: Path) -> None:
    mission = build_post_approval_mission(tmp_path, "lanes")
    add_post_approval_commit(mission, LANE_A)
    log_before = _status_log(mission)
    target = git_rev(mission.repo, mission.target_branch)

    rc, flat = _consolidate(mission, *_attest("WP01"))

    assert rc == 1 and "already has one" in flat and "Move it back for review instead. Nothing was recorded." in flat, flat
    assert _status_log(mission) == log_before, "a refused attestation records nothing"
    assert git_rev(mission.repo, mission.target_branch) == target


def test_forced_done_without_an_approval_refuses_as_unstamped(tmp_path: Path) -> None:
    """A work package that counts as approved without any ``approved`` transition has no stamp; the ``done`` record is never the bound."""
    mission = build_post_approval_mission(tmp_path, "lanes")
    log = resolve_status_surface(mission.repo, mission.slug)
    kept = [line for line in log.read_text(encoding="utf-8").splitlines() if not _is_approval_of(line, "WP01")]
    log.write_text("\n".join(kept) + "\n", encoding="utf-8")
    for command in (["add", str(log)], ["commit", "-qm", "test: drop the approval of WP01"]):
        run_git(mission.repo, *command)
    emit_status_transition_transactional(
        TransitionRequest(
            feature_dir=mission.feature_dir,
            mission_slug=mission.slug,
            wp_id="WP01",
            to_lane="done",
            actor=ACTOR,
            repo_root=mission.repo,
            force=True,
            reason="forced to done with no approval",
            evidence={"review": {"reviewer": ACTOR, "verdict": "approved", "reference": "forced"}},
        )
    )

    rc, flat = _consolidate(mission)

    assert rc != 0 and _MISSING in flat and "WP01" in flat, f"a forced done is not an approval:\n{flat}"


def test_an_earlier_attestation_is_re_recorded_by_the_repeated_command(tmp_path: Path) -> None:
    """A run that attested WP01 and then refused for WP02 is repeatable: the second run attests both."""
    mission = build_post_approval_mission(tmp_path, "lanes")
    strip_approval_stamps(mission, "WP01")
    strip_approval_stamps(mission, "WP02")

    rc, flat = _consolidate(mission, *_attest("WP01"))
    assert rc != 0 and _MISSING in flat and "WP02" in flat, f"WP02 is still unstamped:\n{flat}"
    assert len(_attestations(mission, "WP01")) == 1

    rc, flat = _consolidate(mission, ATTEST_APPROVED_FLAG, "WP01", ATTEST_APPROVED_FLAG, "WP02", "--attest-reason", _REASON)
    assert rc == 0, f"the repeated command must be accepted:\n{flat}"
    assert len(_attestations(mission, "WP01")) == 2, "the earlier attestation is re-recorded, not refused as already stamped"
    assert len(_attestations(mission, "WP02")) == 1
