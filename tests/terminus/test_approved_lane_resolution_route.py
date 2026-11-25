"""FR-008 / SC-001..SC-003 (Mission ``approved-lane-resolution-route``): the re-review route, end to end through the real CLI.

Every scenario starts from :func:`~tests.terminus.approved_lane_route_support.build_conflicting_lanes_mission`
(coordination topology): ``lane-a`` (``WP01``) and ``lane-b`` (``WP02``) are approved by an independent
reviewer and their edits of ``src/pkg/shared.py`` conflict.

* T048 -- the route lands the Mission under squash and under ``--strategy merge``: the stale refusal
  prints it, the operator runs the printed commands plus the two human acts (resolve and commit;
  the independent review), and a FRESH ``consolidate`` (never ``--resume``: the stale refusal's full
  restore re-baselines the record) exits 0 with the resolved text on the target. No in-process
  restamp, no ``--force``, distinct identities.
* T049 -- the negative controls on the same fixture: N1 an unreviewed hand resolution (with and
  without a novel line), N2 a second merge after the re-approval, N3 a forced or a self re-approval.
  The forced re-approval does not restamp (C-004); as landed, ``consolidate`` then refuses it at the
  review-artifact consistency gate (``REJECTED_REVIEW_ARTIFACT_CONFLICT``), before the claim, so the
  claim's ``RESOLUTION_MERGE_UNREVIEWED`` is never reached; the self re-approval is refused at the
  move with ``REVIEW_NOT_INDEPENDENT``.
  Each asserts its fixture's precondition (the merge exists, its own content is non-empty), the
  named code, and that no branch moved.
* T050 -- SC-003 with a discriminating control (a land-then-rollback DOES change reflog lengths),
  and the residual control: a reviewed resolution with a novel line lands (the review is the guard).
* WP06 binding addition -- the gate hint's partial shape: a dropped merge explains part of a gate
  FAIL and foreign content the rest.
* T047 -- a smoke test of WP14's three-lane builder.

No ``xfail`` and no ``skip`` anywhere: a route gap is reported, never marked.
"""

from __future__ import annotations

import re
import time
from pathlib import Path

import pytest

from specify_cli.consolidation.approved_bound import approval_stamp
from specify_cli.lanes import auto_rebase_record
from specify_cli.status.models import actor_full_identity, actor_identities_independent
from tests.terminus.approved_lane_route_support import (
    IMPLEMENTER,
    LANE_A,
    LANE_B,
    LANE_C,
    LANE_D,
    NOVEL_LINE,
    OTHER_PATH,
    RECONCILIATION_VERIFIED,
    RESOLUTION_MERGE_UNREVIEWED,
    RESOLVED_TEXT,
    REVIEWER,
    SHARED_PATH,
    RouteMission,
    Strategy,
    add_dependent_and_control_lanes,
    approval_event,
    assert_no_branch_moved,
    branch_reflog_lengths,
    build_conflicting_lanes_mission,
    cli,
    consolidate,
    consolidate_in_process,
    events,
    follow_route_to_review,
    git,
    hand_merge,
    independent_approval,
    lane_of,
    merge_own_paths,
    one_shot_gate_fail,
    output,
    ref_shas,
    refuse_as_stale,
    run_route,
    show,
    snapshot_written,
)
from tests.terminus.conftest import git_rev, sha_reachable

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

_HARNESS_VARIABLES = ("SPEC_KITTY_NO_NAG", "SPEC_KITTY_NON_INTERACTIVE")
_STRATEGIES = pytest.mark.parametrize("strategy", ["squash", "merge"])
#: The flags an attestation would carry (C-002: none appears anywhere on the route).
_ATTESTATION_FLAGS = ("--attest-approved-reviewed", "--attest-canceled-superseded", "--attest-no-implementation")
_FOREIGN_PATH = "vendor/foreign.py"
_DEPENDENCY_REF = "spec-kitty consolidate --dependency-ref <ref>"


@pytest.fixture(autouse=True)
def _unset_harness_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in _HARNESS_VARIABLES:
        monkeypatch.delenv(key, raising=False)


def _mid8(prefix: str, strategy: str, variant: str = "0") -> str:
    return f"01M7W{prefix}{strategy[0].upper()}{variant}"


def _assert_landed(route: RouteMission, strategy: Strategy, expected: str) -> str:
    """A fresh run exits 0 with the gate's banner, and the target holds *expected*."""
    assert not snapshot_written(route), "re-entry is a fresh run: the stale refusal's full restore left no snapshot"
    code, text = consolidate(route, strategy)
    assert code == 0, text
    assert RECONCILIATION_VERIFIED in text, f"an exit 0 without the gate's banner is a failure: {text}"
    landed = show(route.repo, route.mission.target_branch, SHARED_PATH)
    assert landed == expected, landed
    return text


def _assert_unreviewed_refusal(route: RouteMission, text: str, merge: str, wp_id: str = "WP02", lane: str = LANE_B) -> None:
    """The claim-time ``RESOLUTION_MERGE_UNREVIEWED`` names *merge*, *lane* and *wp_id*, and prints the re-review route."""
    assert RESOLUTION_MERGE_UNREVIEWED in text, text
    assert re.search(rf"\b{merge[:7]}", text), f"the refusal names the merge {merge}: {text}"
    assert lane in text and wp_id in text, text
    assert f"move-task {wp_id} --to in_progress --mission {route.slug}" in text, f"the re-review route is printed: {text}"
    assert RECONCILIATION_VERIFIED not in text


def _assert_merge_has_own_content(route: RouteMission, merge: str) -> None:
    """Anti-vacuity: the merge is on lane-b and carries content of its own (``--remerge-diff`` lists the shared file)."""
    assert sha_reachable(route.repo, merge, route.lane_branches[LANE_B]), f"fixture: {merge} is on lane-b"
    assert len(git(route.repo, "rev-list", "--parents", "-n", "1", merge).split()) == 3, f"fixture: {merge} is a merge"
    assert SHARED_PATH in merge_own_paths(route, merge), f"fixture: {merge} carries own content"


# --------------------------------------------------------------------------- T048


@_STRATEGIES
def test_route_lands_after_independent_re_review(tmp_path: Path, strategy: Strategy) -> None:
    started = time.monotonic()
    route = build_conflicting_lanes_mission(tmp_path, "coord", mid8=_mid8("R", strategy))
    stale_stamp = approval_stamp(events(route), "WP02")

    outcome = run_route(route, lane=LANE_B, wp_id="WP02", sibling=LANE_A, strategy=strategy)

    for argv in [outcome.reopen_command, *outcome.printed]:
        assert not any(flag in argv for flag in (*_ATTESTATION_FLAGS, "--force")), f"C-002: {argv}"
    merge_label = "RESOLUTION MERGE (operator-authored, review these bytes): git "
    listed = [line for line in outcome.review_prompt.splitlines() if merge_label in line]
    command = next((line for line in listed if line.rstrip().endswith(f" {outcome.resolution_merge}")), None)
    assert command is not None, f"WP10: the review context lists the resolution merge {outcome.resolution_merge}: {listed}"
    assert command.rstrip().endswith(f"show --remerge-diff --no-ext-diff --no-textconv {outcome.resolution_merge}"), command
    assert f"--attr-source={git_rev(route.repo, route.mission.target_branch)}" in command, command
    approval = outcome.approval
    assert approval.force is False
    assert approval.review_result is not None and approval.review_result.verdict == "approved"
    assert actor_identities_independent(actor_full_identity(approval.actor), IMPLEMENTER), approval.actor
    assert actor_full_identity(approval.actor) == REVIEWER, approval.actor
    lane_head = approval.policy_metadata["lane_head"]
    assert lane_head != stale_stamp and sha_reachable(route.repo, outcome.resolution_merge, lane_head), "the new approval reaches the resolution merge"

    _assert_landed(route, strategy, RESOLVED_TEXT)
    print(f"route[{strategy}] wall time {time.monotonic() - started:.1f}s")


# --------------------------------------------------------------------------- T049


@_STRATEGIES
@pytest.mark.parametrize("resolution", ["keep_both", "novel_line"])
def test_n1_unreviewed_hand_resolution_is_refused_whatever_it_contains(tmp_path: Path, strategy: Strategy, resolution: str) -> None:
    route = build_conflicting_lanes_mission(tmp_path, "coord", mid8=_mid8("N", strategy, "1" if resolution == "keep_both" else "2"))
    merge = hand_merge(route, lane=LANE_B, sibling=LANE_A, novel_line=resolution == "novel_line")
    _assert_merge_has_own_content(route, merge)
    assert lane_of(route, "WP02") == "approved", "fixture: WP02 was never sent back, so no re-approval can follow"
    before = branch_reflog_lengths(route)

    code, text = consolidate(route, strategy)

    assert code == 1, text
    _assert_unreviewed_refusal(route, text, merge)
    assert_no_branch_moved(route, before)


def test_n2_merge_after_re_approval_is_refused(tmp_path: Path) -> None:
    route = build_conflicting_lanes_mission(tmp_path, "coord", mid8="01M7WN2S")
    outcome = run_route(route, lane=LANE_B, wp_id="WP02", sibling=LANE_A, strategy="squash")
    checkout = route.checkouts[LANE_B]
    merged = git(checkout, "merge", "--no-ff", "--no-commit", route.mission.target_branch)
    assert "Automatic merge went well" in merged or merged == "", merged
    (checkout / SHARED_PATH).write_text(RESOLVED_TEXT + "LATE = 'hand-edited in the second merge'\n", encoding="utf-8")
    git(checkout, "add", SHARED_PATH)
    git(checkout, "commit", "-q", "--no-edit")
    second = git_rev(checkout, "HEAD")
    assert second != outcome.resolution_merge
    _assert_merge_has_own_content(route, second)
    assert not sha_reachable(route.repo, second, outcome.approval.policy_metadata["lane_head"]), "fixture: the second merge is after the re-approval"
    before = branch_reflog_lengths(route)

    code, text = consolidate(route, "squash")

    assert code == 1, text
    _assert_unreviewed_refusal(route, text, second)
    assert outcome.resolution_merge[:7] not in text.split(RESOLUTION_MERGE_UNREVIEWED, 1)[1].split(".")[0], "the refusal names the second merge"
    assert_no_branch_moved(route, before)


def test_n3_forced_re_approval_does_not_restamp(tmp_path: Path) -> None:
    route = build_conflicting_lanes_mission(tmp_path, "coord", mid8="01M7WN3F")
    old_stamp = approval_stamp(events(route), "WP02")
    refusal = refuse_as_stale(route, lane=LANE_B, sibling=LANE_A, strategy="squash")
    _reopen, _commands, merge = follow_route_to_review(route, refusal, wp_id="WP02", sibling=LANE_A)

    forced = cli(route, "agent", "tasks", "move-task", "WP02", "--to", "approved", "--force", "--agent", REVIEWER, "--mission", route.slug)

    assert forced.returncode == 0, output(forced)
    event = approval_event(route, "WP02")
    assert event.force is True and event.review_result is None, event
    assert approval_stamp(events(route), "WP02") == old_stamp, "a forced approval does not restamp the lane (C-004)"
    _assert_merge_has_own_content(route, merge)
    before = branch_reflog_lengths(route)
    code, text = consolidate(route, "squash")
    assert code == 1, text
    # Landed behaviour: the reopen recorded a changes_requested review cycle and a forced approval writes no
    # approved one, so the review-artifact consistency gate refuses first, before the claim and any branch move.
    assert "REJECTED_REVIEW_ARTIFACT_CONFLICT" in text and "WP02" in text, text
    assert RECONCILIATION_VERIFIED not in text
    assert_no_branch_moved(route, before)


def test_n3_self_re_approval_is_refused(tmp_path: Path) -> None:
    route = build_conflicting_lanes_mission(tmp_path, "coord", mid8="01M7WN3S")
    target_before = git_rev(route.repo, route.mission.target_branch)
    refusal = refuse_as_stale(route, lane=LANE_B, sibling=LANE_A, strategy="squash")
    follow_route_to_review(route, refusal, wp_id="WP02", sibling=LANE_A)

    review_output, approve = independent_approval(route, "WP02", reviewer=IMPLEMENTER)

    text = f"{review_output}\n{output(approve)}"
    assert approve.returncode != 0, text
    assert "REVIEW_NOT_INDEPENDENT" in text, text
    assert lane_of(route, "WP02") != "approved"
    code, landed = consolidate(route, "squash")
    assert code != 0 and RECONCILIATION_VERIFIED not in landed, landed
    assert git_rev(route.repo, route.mission.target_branch) == target_before
    assert show(route.repo, route.mission.target_branch, SHARED_PATH) != RESOLVED_TEXT


# --------------------------------------------------------------------------- T050


@_STRATEGIES
def test_unreviewed_merge_refuses_before_any_branch_moves(tmp_path: Path, strategy: Strategy, monkeypatch: pytest.MonkeyPatch) -> None:
    route = build_conflicting_lanes_mission(tmp_path / "refused", "coord", mid8=_mid8("C", strategy))
    merge = hand_merge(route, lane=LANE_B, sibling=LANE_A)
    _assert_merge_has_own_content(route, merge)
    before = branch_reflog_lengths(route)

    code, text = consolidate(route, strategy)

    assert code == 1 and RESOLUTION_MERGE_UNREVIEWED in text, text
    assert_no_branch_moved(route, before)

    # Control: on a mission whose lanes land cleanly and then fail at the gate, the end-state SHAs come back
    # but the reflog lengths do not, so the assertion above is not vacuous.
    control = build_conflicting_lanes_mission(tmp_path / "control", "coord", mid8=_mid8("K", strategy))
    hand_merge(control, lane=LANE_B, sibling=LANE_A)
    _review_hand_merge(control)
    shas, lengths = ref_shas(control), branch_reflog_lengths(control)
    calls = one_shot_gate_fail(monkeypatch)
    code, text = consolidate_in_process(control, strategy, monkeypatch)
    assert calls == [1] and code != 0, text
    assert ref_shas(control) == shas, "the rollback restores every end-state SHA"
    assert branch_reflog_lengths(control) != lengths, "but the land-then-rollback shows in the reflogs"


def _review_hand_merge(route: RouteMission) -> None:
    """Send WP02 back and approve it again at the hand merge, through the CLI, so the lanes land cleanly (control only)."""
    feedback = route.mission.home / "WP02-control.md"
    feedback.write_text("Review the hand merge.\n", encoding="utf-8")
    for argv in (
        ["agent", "tasks", "move-task", "WP02", "--to", "planned", "--review-feedback-file", str(feedback), "--mission", route.slug],
        ["agent", "action", "implement", "WP02", "--mission", route.slug, "--agent", IMPLEMENTER],
        ["agent", "tasks", "move-task", "WP02", "--to", "for_review", "--agent", IMPLEMENTER, "--mission", route.slug],
    ):
        result = cli(route, *argv)
        assert result.returncode == 0, output(result)
    review_output, approve = independent_approval(route, "WP02")
    assert approve.returncode == 0, f"{review_output}\n{output(approve)}"


@_STRATEGIES
def test_reviewed_resolution_with_a_novel_line_lands(tmp_path: Path, strategy: Strategy) -> None:
    """The residual by design (spec Edge Cases): the review is the only guard; no mechanical filter refuses a reviewed novel line."""
    route = build_conflicting_lanes_mission(tmp_path, "coord", mid8=_mid8("V", strategy))

    outcome = run_route(route, lane=LANE_B, wp_id="WP02", sibling=LANE_A, strategy=strategy, novel_line=True)

    assert NOVEL_LINE in show(route.repo, outcome.resolution_merge, SHARED_PATH)
    assert outcome.approval.force is False
    _assert_landed(route, strategy, RESOLVED_TEXT.replace("GAMMA = 2  # lane-b\n", f"GAMMA = 2  # lane-b\n{NOVEL_LINE}\n"))


# --------------------------------------------------------------------------- WP06 binding addition


def test_gate_hint_names_re_review_first_then_scopes_dependency_ref_to_foreign_content(tmp_path: Path) -> None:
    """The partial shape: a dropped merge explains part of a gate FAIL, foreign content the rest.

    The claim-time check exempts a tool-recorded merge (the auto-rebase record) whose merge attributes
    hold, so a tool merge with content of its own reaches the gate; no approval stamp of lane-b reaches
    it, so the claim drops it and names it in ``unreviewed_merges``. Foreign content committed on the
    coordination branch is the rest. The hint gives the re-review route for the merge first, then the
    ``--dependency-ref`` hint scoped to the one remaining item, exactly once.
    """
    route = build_conflicting_lanes_mission(tmp_path, "coord", mid8="01M7WPRT")
    merge = hand_merge(route, lane=LANE_B, sibling=LANE_A)
    _assert_merge_has_own_content(route, merge)
    assert auto_rebase_record.record(route.repo, route.lane_branches[LANE_B], merge)
    coordination = route.repo / ".worktrees" / f"{route.slug}-coord"
    (coordination / "vendor").mkdir()
    (coordination / _FOREIGN_PATH).write_text("FOREIGN = True\n", encoding="utf-8")
    git(coordination, "add", _FOREIGN_PATH)
    git(coordination, "commit", "-qm", "foreign content on the coordination branch")

    code, text = consolidate(route, "squash")

    assert code == 1, text
    assert RECONCILIATION_VERIFIED not in text
    re_review = f"Merge {merge[:7]} on lane {LANE_B} (WP02) was made after that lane's last review approval"
    remaining = "For the remaining content (1 item(s) no dropped merge explains):"
    assert re_review in text and remaining in text, text
    assert text.index(re_review) < text.index(f"spec-kitty agent tasks move-task WP02 --to in_progress --mission {route.slug}") < text.index(remaining), text
    assert text.count(_DEPENDENCY_REF) == 1, text
    assert text.index(remaining) < text.index(_DEPENDENCY_REF), text


# --------------------------------------------------------------------------- T047 smoke


def test_three_lane_builder_preconditions(tmp_path: Path) -> None:
    """WP14's builder: lane-c depends on lane-b and overlaps it on the shared file; lane-d overlaps nothing."""
    route = add_dependent_and_control_lanes(build_conflicting_lanes_mission(tmp_path, "coord", mid8="01M7W3LN"))

    assert set(route.lane_branches) == {LANE_A, LANE_B, LANE_C, LANE_D}
    assert {wp: lane_of(route, wp) for wp in ("WP01", "WP02", "WP03", "WP04")} == dict.fromkeys(("WP01", "WP02", "WP03", "WP04"), "approved")
    assert "GAMMA = 3  # lane-c" in show(route.repo, route.lane_branches[LANE_C], SHARED_PATH)
    assert show(route.repo, route.lane_branches[LANE_D], OTHER_PATH)
