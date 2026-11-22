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

from specify_cli.consolidation.approved_bound import BoundRefusal, BoundRefusalCode, check_lane, render_refusals
from specify_cli.lanes.auto_rebase import attempt_auto_rebase
from specify_cli.lanes.branch_naming import lane_branch_name
from specify_cli.lanes.persistence import read_lanes_json
from specify_cli.status import LANE_HEAD_KEY, ReviewResult, StatusEvent, TransitionRequest, read_events
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


@pytest.fixture
def scenario(tmp_path: Path) -> _Scenario:
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

    # The coordination branch moved on (the review claim's own commit lands there).
    _git(repo, "branch", _SYNC_SOURCE, "main")
    sync_worktree = tmp_path / "sync-worktree"
    _git(repo, "worktree", "add", "-q", str(sync_worktree), _SYNC_SOURCE)
    _commit_file(sync_worktree, "coord.txt", "coordination\n", "chore: review claim")
    _git(repo, "worktree", "remove", "-f", str(sync_worktree))

    # The reviewer's review claim merges the coordination branch into the lane (merge M).
    manifest = read_lanes_json(ctx.primary_feature_dir)
    assert manifest is not None
    lane = next(entry for entry in manifest.lanes if entry.lane_id == _LANE_ID)
    report = attempt_auto_rebase(lane, branch, _SYNC_SOURCE, repo, worktree, mission_slug=ctx.slug)
    assert report.succeeded, report.halt_reason
    sync_merge = _git(repo, "rev-parse", f"refs/heads/{branch}")
    assert sync_merge != implemented_tip
    assert _git(repo, "rev-parse", f"{sync_merge}^1") == implemented_tip

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
    )


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
