"""A content commit on a mixed lane that lies in no WP's work window is REFUSEd, unless an operator attestation recorded after it covers it.

A mixed lane (approved WP01 + canceled WP02) whose every WP work window
resolved, but which carries a non-merge content commit in NO WP's window -- a
straggler landed on the lane after the cancel -- is owned by no governed WP, so
consolidation must REFUSE, naming the lane, the commit, the path and the
override flag, and restore the target (spec FR-013, ADR
``docs/adr/3.x/2026-09-29-1-closed-world-refuse-on-mixed-lanes.md``). An
``--attest-canceled-superseded`` attestation exempts only the stragglers up to
its own ``lane_head`` stamp from the closed world; a later straggler still REFUSEs.
It covers no commit of the approval-stamp bound (#5720, ADR
``docs/adr/4.x/2026-10-04-5-approval-stamp-bounds-the-approved-claim.md``): a commit made
after the approved work package's approval needs that work package approved again.

Driven through the REAL ``spec-kitty consolidate`` CLI
(:func:`tests.terminus.conftest.run_terminus`).

Originally the #5046 closed-world reproductions (mission
mixed-lane-authorship-soundness-01M3M7Y0).

KEPT whole (#5618 part 2): this is the only end-to-end proof of the FR-013 closed world,
so it is not trimmed; it carries the ``slow`` tier marker (each replay exceeds 30 s).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.consolidation.canceled_attestation import record_canceled_superseded_attestation
from tests.terminus.conftest import (
    CoordMission,
    PlantedChange,
    blob_present_at,
    build_coord_mission_mixed_lane_canceled,
    git_rev,
    run_terminus,
)
from tests.terminus.conftest import _git as git
from tests.terminus.mixed_lane_support import ATTEST_FLAG, REFUSE_HEADER, collapse, ensure_wp01_subtasks_roster, reapprove_wp01, verdict_block

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression, pytest.mark.slow]

_ACTOR = "closed-world-test"


def _plant_straggler(mission: CoordMission, path: str) -> str:
    """Commit real content on WP02's lane after every WP window closed; return its SHA."""
    repo = mission.repo
    git(repo, "checkout", "-q", mission.lane_branches["WP02"])
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(f"{path}\n", encoding="utf-8")
    git(repo, "add", path)
    git(repo, "commit", "-qm", f"straggler {path}")
    sha = git_rev(repo, "HEAD")
    git(repo, "checkout", "-q", mission.target_branch)
    return sha


def _reapprove_wp01(mission: CoordMission) -> None:
    ensure_wp01_subtasks_roster(mission)
    reapprove_wp01(mission, actor=_ACTOR)


def test_commit_outside_every_window_on_mixed_lane_is_refused(tmp_path: Path) -> None:
    straggler_path = "src/pkg/straggler.py"
    mission = build_coord_mission_mixed_lane_canceled(
        tmp_path,
        canceled_changes=(),
        stamp_attribution=True,
        mid8="01M5046V",
    )
    straggler_sha = _plant_straggler(mission, straggler_path)

    pre_sha = mission.rev(mission.target_branch)
    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])
    flat = collapse(result.stdout + "\n" + result.stderr)

    assert result.returncode != 0, f"a commit outside every WP window on a mixed lane must not ship at exit 0:\n{flat}"
    verdict = verdict_block(flat, REFUSE_HEADER)
    assert "lane-a" in verdict, f"REFUSE must name the lane:\n{verdict}"
    assert straggler_sha[:10] in verdict, f"REFUSE must name the commit {straggler_sha[:10]}:\n{verdict}"
    assert f"'{straggler_path}'" in verdict, f"REFUSE must name the path:\n{verdict}"
    assert f"{ATTEST_FLAG} WP02" in verdict, f"REFUSE must name the override flag:\n{verdict}"
    assert mission.rev(mission.target_branch) == pre_sha, "REFUSE must restore the target"


def test_straggler_after_the_attestation_needs_the_approval_again(tmp_path: Path) -> None:
    """The attestation is bounded by its own ``lane_head`` stamp: a straggler
    committed after it still REFUSEs. The recovery is two acts, because the
    attestation says canceled work is absent and does not approve new content:
    WP01 is approved again at the lane tip (the new approval stamp covers both
    stragglers), and the attestation is supplied again (its new stamp covers
    them for the closed world). Then ``consolidate`` exits 0.
    """
    mission = build_coord_mission_mixed_lane_canceled(tmp_path, canceled_changes=(), stamp_attribution=True, mid8="01M5046N")
    _plant_straggler(mission, "src/pkg/straggler_one.py")
    refused = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])
    assert refused.returncode != 0
    pre_sha = mission.rev(mission.target_branch)
    # The operator attests (production recording seam), THEN a second straggler lands.
    record_canceled_superseded_attestation(
        repo_root=mission.repo,
        feature_dir=mission.feature_dir,
        mission_slug=mission.slug,
        wp_id="WP02",
        reason="checked: straggler_one carries no canceled work",
        actor="landing-test-operator",
    )
    late = _plant_straggler(mission, "src/pkg/straggler_two.py")
    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])
    flat = collapse(result.stdout + "\n" + result.stderr)
    assert result.returncode != 0, f"a straggler after the attestation must still refuse:\n{flat}"
    assert late[:10] in flat and "'src/pkg/straggler_two.py'" in flat, flat
    assert mission.rev(mission.target_branch) == pre_sha
    assert f"{ATTEST_FLAG} WP02" in flat, flat
    # The re-approval alone is not enough (straggler_two is past the attestation's stamp) and the
    # attestation alone is not enough (the approval stamp does not reach the stragglers).
    _reapprove_wp01(mission)
    attest = [ATTEST_FLAG, "WP02", "--attest-reason", "checked: straggler_two carries no canceled work"]
    recovered = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes", *attest])
    flat = collapse(recovered.stdout + "\n" + recovered.stderr)
    assert recovered.returncode == 0, f"approving WP01 again and attesting must succeed:\n{flat}"


def test_canceled_attestation_does_not_approve_a_commit_made_after_the_approval(tmp_path: Path) -> None:
    """``--attest-canceled-superseded`` says canceled work is absent, not that new content was reviewed (#5668).

    A late content commit lands on the mixed lane after WP01's approval. The attestation
    lifts the closed-world refusal, but its own ``lane_head`` stamp covers no commit
    of the approved bound: the run still refuses with ``LANE_MOVED_AFTER_APPROVAL`` and
    the late file stays off the target.
    """
    late_path = "src/pkg/late_after_approval.py"
    mission = build_coord_mission_mixed_lane_canceled(tmp_path, canceled_changes=(), stamp_attribution=True, mid8="01M5668M")
    late_sha = _plant_straggler(mission, late_path)
    pre_sha = mission.rev(mission.target_branch)
    attest = [ATTEST_FLAG, "WP02", "--attest-reason", "checked: nothing of WP02 is on the lane"]

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes", *attest])
    flat = collapse(result.stdout + "\n" + result.stderr)

    assert result.returncode != 0, f"a canceled-work attestation must not approve a late commit:\n{flat}"
    assert "LANE_MOVED_AFTER_APPROVAL" in flat and late_sha[:7] in flat, flat
    assert mission.rev(mission.target_branch) == pre_sha
    assert not blob_present_at(mission.repo, mission.target_branch, late_path), "the unreviewed file must not be on the target"


def test_a_forced_recancel_does_not_cover_a_commit_made_after_the_approval(tmp_path: Path) -> None:
    """A further event of the canceled work package must not cover a late commit (#5720).

    The operator sequence a reviewer proved: a late content commit lands after WP01's
    approval; WP02 is forced ``canceled -> canceled`` (stamped at the lane tip); then the
    canceled-superseded attestation is supplied. WP01 was never approved again, so the
    late file must still not land.
    """
    late_path = "src/pkg/late_after_approval.py"
    mission = build_coord_mission_mixed_lane_canceled(tmp_path, canceled_changes=(), stamp_attribution=True, mid8="01M5720R")
    late_sha = _plant_straggler(mission, late_path)
    pre_sha = mission.rev(mission.target_branch)

    moved = run_terminus(
        mission,
        ["agent", "tasks", "move-task", "WP02", "--to", "canceled", "--force", "--note", "still canceled", "--no-auto-commit", "--mission", mission.slug],
    )
    assert moved.returncode == 0, moved.stdout + moved.stderr
    attest = [ATTEST_FLAG, "WP02", "--attest-reason", "checked: nothing of WP02 is on the lane"]
    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes", *attest])
    flat = collapse(result.stdout + "\n" + result.stderr)

    assert result.returncode != 0, f"a forced re-cancel plus the attestation must not approve a late commit:\n{flat}"
    assert "LANE_MOVED_AFTER_APPROVAL" in flat and late_sha[:7] in flat, flat
    assert mission.rev(mission.target_branch) == pre_sha
    assert not blob_present_at(mission.repo, mission.target_branch, late_path), "the unreviewed file must not be on the target"


def test_the_first_refusal_names_both_problems_and_following_it_reaches_exit_zero(tmp_path: Path) -> None:
    """One run names the closed-world refusal and the approval-stamp refusal; doing both as printed lands the mission (#5720).

    No intermediate refusal that the first message did not announce: the work package is
    approved again first, then ``consolidate`` runs once with the attestation the first
    refusal named.
    """
    late_path = "src/pkg/late_after_approval.py"
    mission = build_coord_mission_mixed_lane_canceled(tmp_path, canceled_changes=(), stamp_attribution=True, mid8="01M5720C")
    _plant_straggler(mission, late_path)
    pre_sha = mission.rev(mission.target_branch)

    first = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])
    flat = collapse(first.stdout + "\n" + first.stderr)

    assert first.returncode != 0, flat
    announced = [f"{ATTEST_FLAG} WP02", "This Mission also has:", "LANE_MOVED_AFTER_APPROVAL:", "move-task WP01 --to in_progress"]
    positions = [flat.find(text) for text in announced]
    assert all(position >= 0 for position in positions) and positions == sorted(positions), f"both problems, in this order:\n{flat}"
    assert mission.rev(mission.target_branch) == pre_sha

    _reapprove_wp01(mission)
    attest = [ATTEST_FLAG, "WP02", "--attest-reason", "checked: nothing of WP02 is on the lane"]
    recovered = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes", *attest])
    flat = collapse(recovered.stdout + "\n" + recovered.stderr)

    assert recovered.returncode == 0, f"doing both announced steps must land the mission:\n{flat}"
    assert REFUSE_HEADER not in flat
    assert blob_present_at(mission.repo, mission.target_branch, late_path), "the re-approved file lands"


def _force_wp02(mission: CoordMission, to_lane: str) -> None:
    """Force canceled WP02 into *to_lane* through the real ``move-task`` shell (the event is stamped at the lane tip)."""
    moved = run_terminus(
        mission,
        ["agent", "tasks", "move-task", "WP02", "--to", to_lane, "--force", "--note", f"forced to {to_lane}", "--no-auto-commit", "--mission", mission.slug],
    )
    assert moved.returncode == 0, moved.stdout + moved.stderr


@pytest.mark.parametrize("forced_lane", ["blocked", "for_review"])
def test_a_forced_window_of_a_canceled_work_package_does_not_cover_a_commit_made_after_the_approval(tmp_path: Path, forced_lane: str) -> None:
    """A forced status move of the canceled work package around a late commit must not cover it (#5720).

    WP02 was canceled from ``planned`` and never did implementation work. The operator
    forces it into a lane that opens a work window, commits after WP01's approval, and cancels it again. The
    first refusal already names ``LANE_MOVED_AFTER_APPROVAL``, and the attestation that
    refusal names does not land the late file: WP01 was never approved again.
    """
    late_path = "src/pkg/late_after_approval.py"
    mission = build_coord_mission_mixed_lane_canceled(tmp_path, canceled_changes=(), canceled_entered_implementation=False, mid8=f"01M5720{forced_lane[0].upper()}")
    _force_wp02(mission, forced_lane)
    late_sha = _plant_straggler(mission, late_path)
    _force_wp02(mission, "canceled")
    pre_sha = mission.rev(mission.target_branch)

    first = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])
    flat = collapse(first.stdout + "\n" + first.stderr)
    assert first.returncode != 0, flat
    assert "LANE_MOVED_AFTER_APPROVAL: " in flat and late_sha[:7] in flat, f"the first refusal must already name the late commit:\n{flat}"

    attest = [ATTEST_FLAG, "WP02", "--attest-reason", "checked: nothing of WP02 is on the lane"]
    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes", *attest])
    flat = collapse(result.stdout + "\n" + result.stderr)

    assert result.returncode != 0, f"a forced window plus the attestation must not approve a late commit:\n{flat}"
    assert "LANE_MOVED_AFTER_APPROVAL" in flat and late_sha[:7] in flat, flat
    assert mission.rev(mission.target_branch) == pre_sha
    assert not blob_present_at(mission.repo, mission.target_branch, late_path), "the unreviewed file must not be on the target"


def test_a_commit_made_in_a_reopened_implementation_window_needs_the_approval_again(tmp_path: Path) -> None:
    """Reopening the canceled work package into ``in_progress`` does not cover a commit made after the approval (#5720).

    The commit lies in WP02's own stamped work window, and the approval-stamp bound counts
    it all the same: the run refuses at claim time, before any branch moves, attested or not.
    """
    late_path = "src/pkg/late_after_approval.py"
    mission = build_coord_mission_mixed_lane_canceled(tmp_path, canceled_changes=(), canceled_entered_implementation=False, mid8="01M5720W")
    _force_wp02(mission, "in_progress")
    late_sha = _plant_straggler(mission, late_path)
    _force_wp02(mission, "canceled")
    pre_sha = mission.rev(mission.target_branch)

    attest = [ATTEST_FLAG, "WP02", "--attest-reason", "checked: nothing of WP02 is on the lane"]
    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes", *attest])
    flat = collapse(result.stdout + "\n" + result.stderr)

    assert result.returncode != 0, f"canceled work committed in a reopened window must not ship:\n{flat}"
    assert "LANE_MOVED_AFTER_APPROVAL: " in flat and late_sha[:7] in flat, flat
    assert mission.rev(mission.target_branch) == pre_sha
    assert "at claim time, before any change" in flat, flat
    assert not blob_present_at(mission.repo, mission.target_branch, late_path), "the late file must not be on the target"


@pytest.mark.parametrize("attested", [False, True], ids=["unattested", "attested"])
def test_a_reopened_canceled_work_package_cannot_delete_an_approved_file(tmp_path: Path, attested: bool) -> None:
    """Canceled work made after the approval must not remove what review approved (#5720).

    WP02 wrote a file, WP01 rewrote it in a rework window and was approved again. The
    operator then reopens canceled WP02, deletes the file on the lane and cancels WP02
    again. The deletion restores WP02's own pre-state, so the canceled-content check sees
    nothing of WP02 to stop; WP01 was never approved again, so the run must refuse and the
    target must not move.
    """
    path = "src/pkg/shared.py"
    mission = build_coord_mission_mixed_lane_canceled(
        tmp_path,
        canceled_changes=[PlantedChange(path, "wp02\n")],
        survivor_after=[PlantedChange(path, "wp01 reviewed\n")],
        mid8="01M5720D" if attested else "01M5720E",
    )
    _force_wp02(mission, "in_progress")
    repo = mission.repo
    git(repo, "checkout", "-q", mission.lane_branches["WP02"])
    git(repo, "rm", "-q", path)
    git(repo, "commit", "-qm", "WP02 reopened: remove the file")
    late_sha = git_rev(repo, "HEAD")
    git(repo, "checkout", "-q", mission.target_branch)
    _force_wp02(mission, "canceled")
    pre_sha = mission.rev(mission.target_branch)

    attest = [ATTEST_FLAG, "WP02", "--attest-reason", "checked: nothing of WP02 is on the lane"] if attested else []
    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes", *attest])
    flat = collapse(result.stdout + "\n" + result.stderr)

    assert result.returncode != 0, f"a deletion made after the approval must not consolidate at exit 0:\n{flat}"
    assert "LANE_MOVED_AFTER_APPROVAL: " in flat and late_sha[:7] in flat, flat
    assert mission.rev(mission.target_branch) == pre_sha, "the target must not move"
