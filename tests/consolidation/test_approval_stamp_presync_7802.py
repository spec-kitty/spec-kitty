"""#7802: the approval stamp survives the review's own sync merge (ADR 2026-10-04-5, Amendment 2026-11-22).

The scenario, with real git and two clones:

1. The implementer pushes the lane tip X to origin.
2. The reviewer's clone claims the review: ``attempt_auto_rebase`` merges the
   coordination branch into the lane locally (``--no-ff``), creating merge M.
3. The reviewer approves through the real status pipeline (``emit_status_transition``
   with the real lane-head reader): the approval stamps ``lane_head = M``. The
   reviewer pushes nothing but the status, so origin never receives M.
4. The integrator clones origin: its lane is at X, and M does not exist there.

Before the fix, ``check_lane`` refused that lane ``APPROVAL_STAMP_NOT_ON_LANE``. After it:

* (a) the approval also records ``lane_head_presync = X``, and the bound passes;
* (b) the bound is not weakened: a non-merge commit after X still refuses
  ``LANE_MOVED_AFTER_APPROVAL``;
* (c) an approval whose stamps are both absent from the clone gets its own remedy:
  push the lane from the reviewer's clone, or rework, review and approve again.
"""

from __future__ import annotations

import dataclasses
import subprocess
from pathlib import Path

import pytest

from specify_cli.consolidation.approved_bound import BoundRefusal, BoundRefusalCode, StampDetail, StampVerdict, check_lane, effective_stamp, render_refusals
from specify_cli.consolidation.write_branch_bound import ApprovalWindow, check_lane_windows
from specify_cli.lanes.auto_rebase import attempt_auto_rebase
from specify_cli.lanes.branch_naming import lane_branch_name
from specify_cli.lanes.persistence import read_lanes_json
from specify_cli.status import LANE_HEAD_KEY, LANE_HEAD_PRESYNC_KEY, ReviewResult, StatusEvent, TransitionRequest, read_events, review_presync_ref
from specify_cli.status.emit import emit_status_transition
from tests.integration.coord_topology_fixture import FlatTopologyContext, _git, build_flat_topology_mission

pytestmark = [pytest.mark.git_repo]

#: The new key, spelled out so this file fails on assertions (not on an import) before the fix.
_PRESYNC_KEY = "lane_head_presync"
_LANE_ID = "lane-a"
_WP = "WP01"
_SYNC_SOURCE = "kitty/coord-sync-source"
_ABSENT_SHA = "f" * 40


def _is_bookkeeping(path: str) -> bool:
    return path.startswith(("kitty-specs/", ".kittify/"))


@dataclasses.dataclass(frozen=True)
class _Scenario:
    reviewer: FlatTopologyContext
    integrator: Path
    branch: str
    implemented_tip: str
    sync_merge: str
    claim_base: str
    events: list[StatusEvent]
    #: The pre-sync tip the approval must record: X, or the implementer's later commit Y.
    expected_presync: str

    @property
    def approval(self) -> StatusEvent:
        return next(event for event in reversed(self.events) if event.wp_id == _WP and str(event.to_lane) == "approved")


def _emit(
    ctx: FlatTopologyContext,
    to_lane: str,
    *,
    force: bool = False,
    actor: str = "presync-implementer",
    evidence: dict[str, object] | None = None,
    review_result: ReviewResult | None = None,
) -> StatusEvent:
    return emit_status_transition(
        TransitionRequest(
            feature_dir=ctx.primary_feature_dir,
            mission_slug=ctx.slug,
            wp_id=_WP,
            to_lane=to_lane,
            actor=actor,
            force=force,
            reason="fixture: manufacture reviewable state" if force else None,
            repo_root=ctx.repo,
            evidence=evidence,
            review_result=review_result,
        )
    )


def _approve(ctx: FlatTopologyContext) -> StatusEvent:
    review = ReviewResult(reviewer="reviewer-renata", verdict="approved", reference=f"review-{_WP}")
    return _emit(
        ctx,
        "approved",
        actor="presync-reviewer",
        evidence={"review": {"reviewer": "reviewer-renata", "verdict": "approved", "reference": f"review-{_WP}"}},
        review_result=review,
    )


def _commit_file(worktree: Path, name: str, text: str, message: str) -> str:
    (worktree / name).write_text(text, encoding="utf-8")
    _git(worktree, "add", "-A")
    _git(worktree, "commit", "-q", "-m", message)
    return _git(worktree, "rev-parse", "HEAD")


def _move_coordination(repo: Path, tmp_path: Path, name: str) -> None:
    """The coordination branch moves on (a review claim's own commit, another WP's status commit)."""
    if subprocess.run(["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", _SYNC_SOURCE], check=False, capture_output=True).returncode != 0:
        _git(repo, "branch", _SYNC_SOURCE, "main")
    sync_worktree = tmp_path / f"sync-worktree-{name}"
    _git(repo, "worktree", "add", "-q", str(sync_worktree), _SYNC_SOURCE)
    _commit_file(sync_worktree, f"{name}.txt", f"{name}\n", f"chore: coordination {name}")
    _git(repo, "worktree", "remove", "-f", str(sync_worktree))


def _review_sync(ctx: FlatTopologyContext, branch: str, worktree: Path) -> str:
    """The review claim's sync: merge the coordination branch into the lane; returns the new merge commit."""
    before = _git(ctx.repo, "rev-parse", f"refs/heads/{branch}")
    manifest = read_lanes_json(ctx.primary_feature_dir)
    assert manifest is not None
    lane = next(entry for entry in manifest.lanes if entry.lane_id == _LANE_ID)
    report = attempt_auto_rebase(lane, branch, _SYNC_SOURCE, ctx.repo, worktree, mission_slug=ctx.slug)
    assert report.succeeded, report.halt_reason
    merge = _git(ctx.repo, "rev-parse", f"refs/heads/{branch}")
    assert merge != before
    assert _git(ctx.repo, "rev-parse", f"{merge}^1") == before
    return merge


def _build_scenario(tmp_path: Path, *, syncs: int = 1, implementer_commit_between: bool = False) -> _Scenario:
    ctx = build_flat_topology_mission(tmp_path, topology="lanes")
    repo = ctx.repo
    _git(repo, "rm", "-q", "--", str(ctx.status_events_path.relative_to(repo)))
    _git(repo, "commit", "-qm", "test: start WP01 with no status log")
    claim_base = _git(repo, "rev-parse", "main")

    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-q", "-b", "main", str(origin)], check=True)
    _git(repo, "remote", "add", "origin", str(origin))
    _git(repo, "push", "-q", "origin", "main")

    branch = lane_branch_name(ctx.slug, _LANE_ID, target_branch="main")
    worktree = tmp_path / "lane-a-worktree"
    _git(repo, "worktree", "add", "-q", "-b", branch, str(worktree), "main")

    # The implementer claims, implements, and pushes the lane tip X.
    _emit(ctx, "planned", force=True)
    _emit(ctx, "claimed")
    _emit(ctx, "in_progress")
    implemented_tip = _commit_file(worktree, "impl.txt", "lane work\n", "feat: lane work")
    _git(repo, "push", "-q", "origin", branch)
    _emit(ctx, "for_review", force=True)

    # The coordination branch moved on, and the reviewer's review claim merges it into the lane (merge M1).
    expected_presync = implemented_tip
    _move_coordination(repo, tmp_path, "coord-1")
    sync_merge = _review_sync(ctx, branch, worktree)
    for index in range(2, syncs + 1):
        if implementer_commit_between:
            # New implementer work on top of the sync merge, pushed: the record moves to it.
            expected_presync = _commit_file(worktree, f"impl-{index}.txt", "more lane work\n", "feat: more lane work")
            _git(repo, "push", "-q", "origin", branch)
        # The coordination branch moves again (a parallel review), and the review claim syncs again (M2).
        _move_coordination(repo, tmp_path, f"coord-{index}")
        sync_merge = _review_sync(ctx, branch, worktree)

    _emit(ctx, "in_review")
    _approve(ctx)

    # The integrator clones origin: the lane is at X, and M never left the reviewer's clone.
    integrator = tmp_path / "integrator"
    subprocess.run(["git", "clone", "-q", str(origin), str(integrator)], check=True)
    _git(integrator, "config", "user.email", "integrator@spec-kitty.test")
    _git(integrator, "config", "user.name", "Integrator")
    _git(integrator, "config", "commit.gpgsign", "false")
    _git(integrator, "branch", "-q", branch, f"origin/{branch}")
    absent = subprocess.run(["git", "-C", str(integrator), "cat-file", "-e", f"{sync_merge}^{{commit}}"], check=False, capture_output=True)
    assert absent.returncode != 0, "the sync merge must not exist in the integrator's clone"

    return _Scenario(
        reviewer=ctx,
        integrator=integrator,
        branch=branch,
        implemented_tip=implemented_tip,
        sync_merge=sync_merge,
        claim_base=claim_base,
        events=list(read_events(ctx.primary_feature_dir)),
        expected_presync=expected_presync,
    )


@pytest.fixture
def scenario(tmp_path: Path) -> _Scenario:
    return _build_scenario(tmp_path)


@pytest.mark.parametrize("implementer_commit_between", [False, True], ids=["merges-only", "implementer-commit-between"])
def test_a_second_merge_creating_sync_keeps_the_pushed_pre_sync_tip(tmp_path: Path, implementer_commit_between: bool) -> None:
    """Review cycle 1, blocking 1: a second sync must not replace the record with the first, unpushed, sync merge.

    Merges only since the record: the record stays X, and an integrator clone without M1 or M2
    passes on X. A new implementer commit Y between the syncs: the record moves to Y.
    """
    two_syncs = _build_scenario(tmp_path, syncs=2, implementer_commit_between=implementer_commit_between)
    metadata = two_syncs.approval.policy_metadata or {}

    assert metadata.get(LANE_HEAD_KEY) == two_syncs.sync_merge
    assert metadata.get(_PRESYNC_KEY) == two_syncs.expected_presync
    assert _ref(two_syncs.reviewer.repo, review_presync_ref(two_syncs.branch)) == two_syncs.expected_presync
    assert _check(two_syncs, two_syncs.events) is None


def _check(scenario: _Scenario, events: list[StatusEvent]) -> BoundRefusal | None:
    return check_lane(
        scenario.integrator,
        events=events,
        lane_id=_LANE_ID,
        branch=scenario.branch,
        approved_wp_ids=[_WP],
        claim_base=scenario.claim_base,
        anchors=[scenario.claim_base],
        is_bookkeeping=_is_bookkeeping,
    )


def test_the_approval_records_the_pre_sync_tip_and_the_bound_passes_in_another_clone(scenario: _Scenario) -> None:
    """(a) The approval stamps both M and X; the integrator's clone, which has only X, passes the bound."""
    metadata = scenario.approval.policy_metadata or {}
    assert metadata.get(LANE_HEAD_KEY) == scenario.sync_merge
    assert metadata.get(_PRESYNC_KEY) == scenario.implemented_tip

    assert _check(scenario, scenario.events) is None


def test_a_non_merge_commit_after_the_pre_sync_tip_still_refuses(scenario: _Scenario) -> None:
    """(b) The bound is not weakened: content committed after X refuses LANE_MOVED_AFTER_APPROVAL."""
    worktree = scenario.integrator.parent / "integrator-lane"
    _git(scenario.integrator, "worktree", "add", "-q", str(worktree), scenario.branch)
    late = _commit_file(worktree, "late.txt", "unreviewed\n", "feat: unreviewed late work")

    refusal = _check(scenario, scenario.events)

    assert refusal is not None
    assert refusal.code is BoundRefusalCode.LANE_MOVED_AFTER_APPROVAL
    assert refusal.commits == (late,)


def test_an_approval_whose_stamps_are_both_absent_gets_the_push_remedy(scenario: _Scenario) -> None:
    """(c) Neither recorded stamp exists in this clone: the refusal names the WP and the SHA and says to push the lane."""
    approval = scenario.approval
    metadata = {**(approval.policy_metadata or {}), _PRESYNC_KEY: _ABSENT_SHA}
    events = [dataclasses.replace(event, policy_metadata=metadata) if event.event_id == approval.event_id else event for event in scenario.events]

    refusal = _check(scenario, events)

    assert refusal is not None
    assert refusal.code is BoundRefusalCode.APPROVAL_STAMP_NOT_ON_LANE
    text = render_refusals([refusal], scenario.reviewer.slug)
    assert text.startswith(f"{BoundRefusalCode.APPROVAL_STAMP_NOT_ON_LANE.value}: ")
    assert _WP in text
    assert scenario.sync_merge[:7] in text
    assert "not in this clone" in text
    assert f"git push <remote> {scenario.branch}" in text
    assert "spec-kitty agent tasks move-task WP01 --to in_progress" in text


# --------------------------------------------------------------------------- #
# The pieces: the recorded ref, effective_stamp, the rewritten-lane text, tier 2
# --------------------------------------------------------------------------- #


def _ref(repo: Path, ref: str) -> str | None:
    result = subprocess.run(["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", ref], check=False, capture_output=True, text=True)
    return result.stdout.strip() or None


def test_the_review_sync_records_the_pre_merge_tip_and_a_no_op_sync_records_nothing(scenario: _Scenario) -> None:
    repo = scenario.reviewer.repo
    ref = review_presync_ref(scenario.branch)
    assert _ref(repo, ref) == scenario.implemented_tip

    _git(repo, "update-ref", "-d", ref)
    manifest = read_lanes_json(scenario.reviewer.primary_feature_dir)
    assert manifest is not None
    lane = next(entry for entry in manifest.lanes if entry.lane_id == _LANE_ID)
    worktree = scenario.integrator.parent / "lane-a-worktree"
    report = attempt_auto_rebase(lane, scenario.branch, _SYNC_SOURCE, repo, worktree, mission_slug=scenario.reviewer.slug)

    assert report.succeeded, report.halt_reason
    assert _git(repo, "rev-parse", f"refs/heads/{scenario.branch}") == scenario.sync_merge
    assert _ref(repo, ref) is None


def test_effective_stamp_reads_the_newest_recorded_stamp_each_clone_holds(scenario: _Scenario) -> None:
    metadata = {LANE_HEAD_KEY: scenario.sync_merge, LANE_HEAD_PRESYNC_KEY: scenario.implemented_tip}

    assert effective_stamp(scenario.reviewer.repo, metadata, scenario.branch) == StampVerdict(scenario.sync_merge, scenario.sync_merge)
    assert effective_stamp(scenario.integrator, metadata, scenario.branch) == StampVerdict(scenario.implemented_tip, scenario.sync_merge)
    # A pre-sync stamp alone never stands in for a missing lane_head: the approval is unstamped.
    assert effective_stamp(scenario.integrator, {LANE_HEAD_PRESYNC_KEY: scenario.implemented_tip}, scenario.branch) == StampVerdict(None, None)
    assert effective_stamp(scenario.integrator, None, scenario.branch) == StampVerdict(None, None)


def test_a_rewritten_lane_keeps_the_rewritten_remedy_without_a_push(scenario: _Scenario) -> None:
    """The pre-sync tip is in this clone but the lane no longer reaches it: ``not_on_lane``, never the push remedy."""
    worktree = scenario.integrator.parent / "integrator-lane"
    _git(scenario.integrator, "worktree", "add", "-q", str(worktree), scenario.branch)
    _git(worktree, "reset", "-q", "--hard", scenario.claim_base)
    _commit_file(worktree, "impl.txt", "rewritten lane work\n", "feat: rewritten lane work")

    refusal = _check(scenario, scenario.events)

    assert refusal is not None
    assert refusal.code is BoundRefusalCode.APPROVAL_STAMP_NOT_ON_LANE
    assert refusal.stamp_detail is StampDetail.NOT_ON_LANE
    text = render_refusals([refusal], scenario.reviewer.slug)
    assert "the lane was rewritten" in text
    assert "git push" not in text


def test_tier_two_ends_each_window_at_the_effective_stamp(scenario: _Scenario) -> None:
    """A window recorded at the unpushed sync merge does not make tier 2 read a commit this clone lacks."""
    windows = (ApprovalWindow(_WP, None, scenario.sync_merge),)

    tiers = check_lane_windows(
        scenario.integrator,
        events=scenario.events,
        lane_id=_LANE_ID,
        branch=scenario.branch,
        approved_wp_ids=[_WP],
        claim_base=scenario.claim_base,
        exemption_anchors=[scenario.claim_base],
        windows=windows,
        is_bookkeeping=_is_bookkeeping,
        tip=_git(scenario.integrator, "rev-parse", scenario.branch),
    )

    assert tiers == ((), ())
