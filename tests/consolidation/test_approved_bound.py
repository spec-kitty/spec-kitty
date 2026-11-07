"""Unit tests for ``specify_cli.consolidation.approved_bound`` (#5668, plan D-1/D-2).

The rule: a code lane may hold nothing but what review approved. The approval stamp
(``policy_metadata.lane_head`` of the newest ``approved`` event) is the bound; tool-made
movement (merges from an anchor, bookkeeping-only commits, a later approval of another
work package on the same lane) is not a violation. Real throwaway git repos, synthetic
status events carrying real SHAs as stamps.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from specify_cli.consolidation import approved_bound as bound
from specify_cli.consolidation.approved_bound import (
    ATTEST_APPROVED_FLAG,
    BoundRefusal,
    BoundRefusalCode,
    approval_stamp,
    check_lane,
    refusal_codes,
    render_refusals,
)
from specify_cli.consolidation.canceled_attestation import ATTESTATION_KEY
from specify_cli.consolidation.git_probes import GitProbeError
from specify_cli.consolidation.reconciliation import ApprovedWpCommitSet, approval_stamp_anchors, build_approved_wp_set, lane_tips_moved_refusal
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.status import LANE_HEAD_KEY, DoneEvidence, Lane, ReviewResult, StatusEvent
from specify_cli.status.models import ReviewApproval
from tests.terminus.conftest import CoordMission
from tests.terminus.lanes_fixture import build_lanes_mission

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_SLUG = "approved-bound-01M444QR"
_BOOKKEEPING_PREFIX = f"kitty-specs/{_SLUG}/"
_LANE = "lane-a"
_BRANCH = "lane-a"


def _is_bookkeeping(path: str) -> bool:
    return path.startswith(_BOOKKEEPING_PREFIX)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Setup:
    """What a scenario tells :meth:`_Repo.check` about the lane beyond its git history."""

    anchors: tuple[str, ...] = ()
    approved: tuple[str, ...] = ("WP01",)


@dataclass
class _Repo:
    root: Path
    seq: int = 0
    events: list[StatusEvent] = field(default_factory=list)

    def git(self, *args: str) -> str:
        done = subprocess.run(["git", "-C", str(self.root), *args], capture_output=True, text=True, check=True)
        return done.stdout.strip()

    def commit(self, rel: str, body: str = "x\n") -> str:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body + str(self.seq), encoding="utf-8")
        self.seq += 1
        self.git("add", rel)
        self.git("commit", "-qm", f"change {rel}")
        return self.git("rev-parse", "HEAD")

    def branch_from(self, name: str, base: str) -> None:
        self.git("checkout", "-qb", name, base)

    def merge(self, other: str) -> str:
        self.git("merge", "--no-ff", "-qm", f"merge {other}", other)
        return self.git("rev-parse", "HEAD")

    def tip(self, ref: str) -> str:
        return self.git("rev-parse", ref)

    def event(
        self,
        wp_id: str,
        to_lane: Lane,
        stamp: str | None,
        *,
        actor: str = "claude",
        metadata: dict[str, str] | None = None,
        from_lane: Lane = Lane.IN_REVIEW,
        force: bool = False,
        review_ref: str | None = None,
        evidence: DoneEvidence | None = None,
        review_result: ReviewResult | None = None,
    ) -> None:
        self.seq += 1
        policy = dict(metadata or {})
        if stamp:
            policy[LANE_HEAD_KEY] = stamp
        self.events.append(
            StatusEvent(
                event_id=f"e{self.seq}",
                mission_slug=_SLUG,
                wp_id=wp_id,
                from_lane=from_lane,
                to_lane=to_lane,
                at=f"2026-10-04T00:00:{self.seq:02d}Z",
                actor=actor,
                force=force,
                execution_mode="worktree",
                review_ref=review_ref,
                evidence=evidence,
                review_result=review_result,
                policy_metadata=policy or None,
            )
        )

    def check(self, setup: _Setup | None = None) -> BoundRefusal | None:
        setup = setup or _Setup()
        return check_lane(
            self.root,
            events=self.events,
            lane_id=_LANE,
            branch=_BRANCH,
            approved_wp_ids=setup.approved,
            claim_base="base",
            anchors=setup.anchors,
            is_bookkeeping=_is_bookkeeping,
        )


@pytest.fixture
def repo(tmp_path: Path) -> _Repo:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-qb", "main", str(root)], check=True)
    made = _Repo(root)
    for key, value in (("user.email", "t@t.test"), ("user.name", "T"), ("commit.gpgsign", "false")):
        made.git("config", key, value)
    made.commit("README.md")
    made.git("branch", "base")
    made.branch_from(_BRANCH, "base")
    return made


def _approved_lane(repo: _Repo) -> str:
    """lane-a holds one content commit and WP01 is approved at it; returns that commit."""
    work = repo.commit("src/a.py")
    repo.event("WP01", Lane.APPROVED, work)
    return work


# ---------------------------------------------------------------------------
# approval_stamp
# ---------------------------------------------------------------------------


_RUN_DONE = {"from_lane": Lane.APPROVED}  # the ``approved -> done`` record the run itself writes
_FORCED = {"force": True}
# What ``move-task <WP> --to approved --force`` really writes (traces/design-decisions.md, #5721): an
# ``evidence.review`` whose reviewer is auto-detected (``git config user.name``) and whose reference is the
# synthetic ``auto-approval:`` token, no ``review_result``, no ``review_ref``.
_DETECTED_REVIEWER = "Real Operator"
_BARE_EVIDENCE = DoneEvidence(review=ReviewApproval(reviewer=_DETECTED_REVIEWER, verdict="approved", reference="auto-approval:WP01:20261007"))


def _forced_from(lane: str) -> dict[str, Any]:
    return {"force": True, "from_lane": Lane(lane), "evidence": _BARE_EVIDENCE}


_REJECTION = {"from_lane": Lane.FOR_REVIEW, "review_ref": "feedback://WP01/review-cycle-1.md"}
_REVIEWED_FORCE = {  # a reviewer forcing past an unrelated gate: the hop out of in_review carries a review_result
    "force": True,
    "from_lane": Lane.IN_REVIEW,
    "evidence": _BARE_EVIDENCE,
    "review_result": ReviewResult(reviewer=_DETECTED_REVIEWER, verdict="approved", reference="auto-approval:WP01:20261007"),
}
# A reviewer's claim: ``agent action review`` records an unforced ``for_review -> in_review``.
_GENUINE_CLAIM = ("in_review", None, {}, "reviewer", {"from_lane": Lane.FOR_REVIEW, "review_ref": "action-review-claim"})
# An operator forcing the work package into in_review: no reviewer claimed it.
_FORCED_CLAIM = ("in_review", None, {}, "operator", {"from_lane": Lane.APPROVED, "force": True})
_EXPLICIT_APPROVAL_REF = {  # --approval-ref PR#42: a reference the operator typed is no review (#5721)
    "force": True,
    "from_lane": Lane.FOR_REVIEW,
    "evidence": DoneEvidence(review=ReviewApproval(reviewer=_DETECTED_REVIEWER, verdict="approved", reference="PR#42")),
}
# --self-review-fallback writes the same bare evidence on the approval event (its own record is a separate lifecycle event).
_SELF_REVIEW_FALLBACK = _forced_from("for_review")
_REGRESSION = pytest.mark.regression


@pytest.mark.parametrize(
    ("steps", "expected"),
    [
        pytest.param(
            [("approved", "s1", {}, "claude", {}), ("in_progress", "s2", {}, "claude", {}), ("approved", "s3", {}, "claude", {})],
            "s3",
            id="latest-approval-after-rework",
        ),
        pytest.param([("approved", "s1", {}, "claude", {}), ("approved", None, {}, "claude", {})], None, id="newer-unstamped-approval-hides-older-stamped-one"),
        pytest.param([("approved", "s1", {}, "claude", {}), ("approved", "s9", {}, "migration:backfill", {})], "s1", id="migration-event-ignored"),
        pytest.param([("approved", "s1", {}, "claude", {}), ("done", "s7", {}, "merge", _RUN_DONE)], "s1", id="done-restamp-ignored"),
        pytest.param(
            [("approved", None, {}, "claude", {}), ("approved", "s5", {ATTESTATION_KEY: bound.APPROVED_REVIEWED}, "operator", {})],
            "s5",
            id="attestation-supplies-stamp",
        ),
        pytest.param([("done", "s7", {}, "merge", _RUN_DONE)], None, id="done-without-approved-event"),
        pytest.param([("done", "s7", {}, "claude", _FORCED)], None, id="forced-done-is-no-approval"),
        pytest.param(
            [("approved", "s1", {}, "claude", {}), ("in_progress", "s2", {}, "claude", {}), ("done", "s8", {}, "claude", {})],
            "s8",
            id="unforced-review-straight-to-done-is-the-approval",
        ),
        pytest.param(
            [
                ("approved", "s1", {}, "claude", {}),
                ("canceled", None, {}, "claude", {"from_lane": Lane.APPROVED}),
                ("approved", "s3", {}, "claude", _forced_from("canceled")),
            ],
            "s1",
            id="forced-canceled-to-approved-is-no-stamp",
            marks=_REGRESSION,
        ),
        pytest.param(
            [
                ("approved", "s1", {}, "claude", {}),
                ("in_progress", None, {}, "claude", {"from_lane": Lane.APPROVED}),
                ("approved", "s3", {}, "claude", _forced_from("in_progress")),
            ],
            "s1",
            id="forced-in-progress-to-approved-is-no-stamp",
            marks=_REGRESSION,
        ),
        pytest.param(
            [("approved", "s3", {}, "claude", _forced_from("in_progress"))],
            None,
            id="forced-approval-alone-leaves-no-stamp",
            marks=_REGRESSION,
        ),
        pytest.param(
            [
                ("approved", "s1", {}, "claude", {}),
                ("planned", None, {}, "claude", _REJECTION),
                ("approved", "s3", {}, "claude", {**_forced_from("planned"), "evidence": None}),
            ],
            "s3",
            id="arbiter-override-counts",
        ),
        pytest.param(
            [("approved", "s1", {}, "claude", {}), ("approved", "s5", {ATTESTATION_KEY: bound.APPROVED_REVIEWED}, "operator", _forced_from("approved"))],
            "s5",
            id="forced-attestation-counts",
        ),
        pytest.param(
            [("approved", "s1", {}, "claude", {}), _GENUINE_CLAIM, ("approved", "s4", {}, "claude", _REVIEWED_FORCE)],
            "s4",
            id="review-result-after-a-genuine-claim-counts",
        ),
        pytest.param(
            [("approved", "s1", {}, "claude", {}), _FORCED_CLAIM, ("approved", "s4", {}, "claude", _REVIEWED_FORCE)],
            "s1",
            id="review-result-after-a-forced-in-review-entry-is-no-stamp",
            marks=_REGRESSION,
        ),
        pytest.param(
            [("approved", "s1", {}, "claude", {}), _GENUINE_CLAIM, _FORCED_CLAIM, ("approved", "s4", {}, "claude", _REVIEWED_FORCE)],
            "s1",
            id="only-the-latest-in-review-entry-decides",
            marks=_REGRESSION,
        ),
        pytest.param(
            [("approved", "s1", {}, "claude", {}), ("approved", "s4", {}, "claude", _REVIEWED_FORCE)],
            "s1",
            id="review-result-with-no-claim-on-record-is-no-stamp",
            marks=_REGRESSION,
        ),
        pytest.param(
            [("approved", "s1", {}, "claude", {}), _GENUINE_CLAIM, ("approved", "s4", {}, "operator", _EXPLICIT_APPROVAL_REF)],
            "s1",
            id="explicit-approval-ref-is-no-stamp",
            marks=_REGRESSION,
        ),
        pytest.param(
            [
                ("approved", "s1", {}, "claude", {}),
                _GENUINE_CLAIM,
                (
                    "approved",
                    "s4",
                    {},
                    "claude",
                    _forced_from("in_review")
                    | {"evidence": DoneEvidence(review=ReviewApproval(reviewer="rev", verdict="approved", reference="review-cycle://m/WP01/review-cycle-2.md"))},
                ),
            ],
            "s1",
            id="own-review-cycle-pointer-without-a-review-result-is-no-stamp",
            marks=_REGRESSION,
        ),
        pytest.param(
            [("approved", "s1", {}, "claude", {}), ("approved", "s4", {}, "operator", _SELF_REVIEW_FALLBACK)],
            "s1",
            id="self-review-fallback-is-no-stamp",
            marks=_REGRESSION,
        ),
    ],
)
def test_approval_stamp_selection(steps: list[tuple[str, str | None, dict[str, str], str, dict[str, Any]]], expected: str | None) -> None:
    holder = _Repo(Path("."))
    for lane, stamp, metadata, actor, extra in steps:
        holder.event("WP01", Lane(lane), stamp, actor=actor, metadata=metadata, **extra)
    assert approval_stamp(holder.events, "WP01") == expected
    assert approval_stamp(holder.events, "WP99") is None


# ---------------------------------------------------------------------------
# the three refusals
# ---------------------------------------------------------------------------


def test_missing_stamp_refuses_and_names_the_work_package_and_the_override(repo: _Repo) -> None:
    repo.commit("src/a.py")
    repo.event("WP01", Lane.APPROVED, None)

    refusal = repo.check()

    assert refusal is not None and refusal.code is BoundRefusalCode.APPROVAL_STAMP_MISSING
    text = refusal.render(_SLUG)
    assert text.startswith("APPROVAL_STAMP_MISSING: ")
    assert "WP01" in text and _LANE in text and f"{ATTEST_APPROVED_FLAG} WP01" in text


def test_stamp_not_on_lane_refuses_and_names_the_stamp(repo: _Repo) -> None:
    repo.git("checkout", "-q", "main")
    elsewhere = repo.commit("src/elsewhere.py")
    repo.git("checkout", "-q", _BRANCH)
    repo.commit("src/a.py")
    repo.event("WP01", Lane.APPROVED, elsewhere)

    refusal = repo.check()

    assert refusal is not None and refusal.code is BoundRefusalCode.APPROVAL_STAMP_NOT_ON_LANE
    text = refusal.render(_SLUG)
    assert text.startswith("APPROVAL_STAMP_NOT_ON_LANE: ")
    assert elsewhere[:7] in text and "WP01" in text and _BRANCH in text


def test_content_after_approval_refuses_and_names_commits_and_path(repo: _Repo) -> None:
    _approved_lane(repo)
    late = [repo.commit(f"src/late{i}.py") for i in range(4)]

    refusal = repo.check()

    assert refusal is not None and refusal.code is BoundRefusalCode.LANE_MOVED_AFTER_APPROVAL
    text = refusal.render(_SLUG)
    assert text.startswith("LANE_MOVED_AFTER_APPROVAL: ")
    assert all(sha[:7] in text for sha in reversed(late[-3:])) and late[0][:7] not in text
    assert "and 1 more" in text and "src/late3.py" in text and "WP01" in text and _LANE in text


def test_several_work_packages_render_one_line_each_and_one_recovery_block() -> None:
    """Twelve unstamped work packages and a three-package moved lane: short lines, one block, runnable commands, the term defined once."""
    unstamped = tuple(f"WP{n:02d}" for n in range(1, 13))
    missing = BoundRefusal(BoundRefusalCode.APPROVAL_STAMP_MISSING, _LANE, _BRANCH, unstamped)
    moved = BoundRefusal(BoundRefusalCode.LANE_MOVED_AFTER_APPROVAL, "lane-b", "branch-b", ("WP13", "WP14", "WP15"), commits=("c" * 40,), path="src/b.py")

    text = render_refusals([missing, moved], "demo-mission")

    assert text.startswith("APPROVAL_STAMP_MISSING: WP01 (lane-a) has no approval stamp (the lane commit recorded when review approved it)")
    assert max(map(len, text.splitlines())) < 500 and text.count("approval stamp (the lane commit") == 1
    assert text.count(f"{ATTEST_APPROVED_FLAG} ") == 12 and text.count("spec-kitty consolidate --mission demo-mission ") == 1
    assert [wp for wp in unstamped if f"{wp} (lane-a) has no approval stamp" not in text] == []
    assert "\nLANE_MOVED_AFTER_APPROVAL: branch 'branch-b' (lane-b carries WP13, WP14, WP15) holds content" in text
    assert "see one with `git show ccccccc`" in text
    assert all(f"move-task {wp} --to in_progress --mission demo-mission" in text for wp in (*unstamped, "WP13", "WP14", "WP15"))
    assert "<mission>" not in text
    for code in BoundRefusalCode:  # one command template for all three codes: running it once proves the remedy of every code
        single = BoundRefusal(code, _LANE, _BRANCH, ("WP01",), commits=("a" * 40,), path="src/a.py", stamp="b" * 40).render("demo-mission")
        assert "\n  spec-kitty agent tasks move-task WP01 --to in_progress --mission demo-mission\n" in single


def test_refusal_codes_lists_each_code_that_leads_a_block_once_in_text_order() -> None:
    """A code named inside a sentence, or by a second lane of the same code, adds no entry (#5720)."""
    refusals = [
        BoundRefusal(BoundRefusalCode.LANE_MOVED_AFTER_APPROVAL, "lane-a", "branch-a", ("WP01",), commits=("a" * 40,), path="src/a.py"),
        BoundRefusal(BoundRefusalCode.APPROVAL_STAMP_MISSING, "lane-b", "branch-b", ("WP02",)),
        BoundRefusal(BoundRefusalCode.LANE_MOVED_AFTER_APPROVAL, "lane-c", "branch-c", ("WP03",), commits=("c" * 40,), path="src/c.py"),
    ]
    text = render_refusals(refusals, "demo-mission")

    assert refusal_codes(text) == ["LANE_MOVED_AFTER_APPROVAL", "APPROVAL_STAMP_MISSING"]
    assert refusal_codes(f"intro: APPROVAL_STAMP_NOT_ON_LANE: inside a line\n{text}") == ["LANE_MOVED_AFTER_APPROVAL", "APPROVAL_STAMP_MISSING"]
    assert refusal_codes("no code here") == []


def test_a_later_approval_of_a_lane_that_took_this_lane_in_covers_its_late_commit(repo: _Repo) -> None:
    """Deliberate (ADR 2026-10-04-5): every bounded lane's approval stamps are anchors, so reviewed content stays reviewed wherever it first appeared.

    Lane-a gets a commit after WP01's approval and lane-b takes lane-a in. While WP02's
    approval predates that merge, lane-a refuses. Once WP02 is approved again, its new
    stamp reaches the late commit and lane-a no longer refuses.
    """
    _approved_lane(repo)
    late = repo.commit("src/late.py")
    repo.branch_from("lane-b", "base")
    stale = repo.commit("src/b.py")
    repo.event("WP02", Lane.APPROVED, stale)
    lanes = [
        ExecutionLane(lane_id=lane_id, wp_ids=(wp,), write_scope=("src",), predicted_surfaces=("code",), depends_on_lanes=(), parallel_group=0)
        for lane_id, wp in (("lane-a", "WP01"), ("lane-b", "WP02"))
    ]
    work_packages = {"WP01": {"lane": "approved"}, "WP02": {"lane": "approved"}}

    def lane_a_refusal() -> BoundRefusal | None:
        anchors = tuple(approval_stamp_anchors(repo.events, lanes, work_packages, frozenset()))
        return repo.check(_Setup(anchors=anchors))

    control = lane_a_refusal()
    assert control is not None and control.code is BoundRefusalCode.LANE_MOVED_AFTER_APPROVAL and control.commits == (late,)

    repo.merge("lane-a")
    repo.event("WP02", Lane.APPROVED, repo.tip("lane-b"))

    assert lane_a_refusal() is None


def test_unresolvable_claim_base_fails_closed_instead_of_passing(repo: _Repo) -> None:
    _approved_lane(repo)

    with pytest.raises(GitProbeError):
        check_lane(
            repo.root,
            events=repo.events,
            lane_id=_LANE,
            branch=_BRANCH,
            approved_wp_ids=("WP01",),
            claim_base="no-such-base-xyz",
            anchors=(),
            is_bookkeeping=_is_bookkeeping,
        )


# ---------------------------------------------------------------------------
# FR-009: tool-made movement is not a violation; one more content commit still is
# ---------------------------------------------------------------------------

_Scenario = Callable[[_Repo], _Setup]


def _dependency_lane_merge(repo: _Repo) -> _Setup:
    repo.git("checkout", "-q", "main")
    repo.branch_from("lane-dep", "base")
    repo.commit("src/dep.py")
    dep_tip = repo.tip("lane-dep")
    repo.git("checkout", "-q", _BRANCH)
    _approved_lane(repo)
    repo.merge("lane-dep")
    return _Setup(anchors=(dep_tip,))


def _mission_branch_merge(repo: _Repo) -> _Setup:
    """The resume case: the tool merges the mission branch (holding earlier consolidated lanes) into a stale lane."""
    repo.git("checkout", "-q", "main")
    repo.branch_from("mission", "base")
    repo.commit("src/consolidated.py")
    mission_tip = repo.tip("mission")
    repo.git("checkout", "-q", _BRANCH)
    _approved_lane(repo)
    repo.merge("mission")
    return _Setup(anchors=(mission_tip,))


def _target_merge(repo: _Repo) -> _Setup:
    repo.git("checkout", "-q", "main")
    repo.commit("src/on_target.py")
    target_tip = repo.tip("main")
    repo.git("checkout", "-q", _BRANCH)
    _approved_lane(repo)
    repo.merge("main")
    return _Setup(anchors=(target_tip,))


def _bookkeeping_only_commit(repo: _Repo) -> _Setup:
    _approved_lane(repo)
    repo.commit(f"{_BOOKKEEPING_PREFIX}status.json")
    return _Setup()


def _second_wp_approved_later(repo: _Repo) -> _Setup:
    _approved_lane(repo)
    second = repo.commit("src/b.py")
    repo.event("WP02", Lane.APPROVED, second)
    return _Setup(approved=("WP01", "WP02"))


def _conflict_resolved_merge(repo: _Repo) -> _Setup:
    """The auto-rebase case: the tool merges an anchor that edits the same file and resolves the conflict itself.

    ``git show`` lists such a merge commit as changing the resolved path, so counting merge commits as content would
    refuse a lane whose only post-approval movement is the tool's own resolution.
    """
    repo.git("checkout", "-q", "main")
    repo.branch_from("lane-dep", "base")
    repo.commit("src/shared.py")
    dep_tip = repo.tip("lane-dep")
    repo.git("checkout", "-q", _BRANCH)
    repo.commit("src/shared.py")
    _approved_lane(repo)
    conflicted = subprocess.run(["git", "-C", str(repo.root), "merge", "--no-ff", "-qm", "merge lane-dep", "lane-dep"], capture_output=True, text=True)
    assert conflicted.returncode != 0, "the fixture must produce a conflict"
    (repo.root / "src/shared.py").write_text("resolved by the tool\n", encoding="utf-8")
    repo.git("add", "src/shared.py")
    repo.git("commit", "-qm", "auto-rebase(lane=lane-a): 1 conflicts resolved by classifier rules")
    assert "src/shared.py" in repo.git("show", "--name-only", "--format=", "HEAD").split()
    return _Setup(anchors=(dep_tip,))


@pytest.mark.parametrize(
    "scenario",
    [_dependency_lane_merge, _mission_branch_merge, _target_merge, _conflict_resolved_merge, _bookkeeping_only_commit, _second_wp_approved_later],
    ids=lambda fn: fn.__name__.strip("_"),
)
def test_tool_made_movement_passes_and_one_content_commit_still_refuses(repo: _Repo, scenario: _Scenario) -> None:
    setup = scenario(repo)

    assert repo.check(setup) is None, "tool-made lane movement must not be refused"

    repo.commit("src/late.py")
    refusal = repo.check(setup)
    assert refusal is not None and refusal.code is BoundRefusalCode.LANE_MOVED_AFTER_APPROVAL


def test_content_arriving_through_a_merge_from_a_non_anchor_is_found(repo: _Repo) -> None:
    """A first-parent walk sees only the merge commit; the full range finds the side branch's own commit."""
    _approved_lane(repo)
    repo.git("checkout", "-q", "main")
    repo.branch_from("side", "base")
    smuggled = repo.commit("src/smuggled.py")
    repo.git("checkout", "-q", _BRANCH)
    repo.merge("side")

    refusal = repo.check()

    assert refusal is not None and refusal.code is BoundRefusalCode.LANE_MOVED_AFTER_APPROVAL
    assert refusal.commits == (smuggled,)


# ---------------------------------------------------------------------------
# through the production claim builder
# ---------------------------------------------------------------------------


def _claim(mission: CoordMission) -> ApprovedWpCommitSet:
    from specify_cli.lanes.persistence import read_lanes_json

    manifest = read_lanes_json(mission.feature_dir)
    assert manifest is not None
    return build_approved_wp_set(mission.repo, mission.feature_dir, manifest, coord_base_ref=mission.coord_branch)


def test_claim_skips_a_planning_lane_and_a_planning_work_package_never_refuses(tmp_path: Path) -> None:
    """A planning lane has no lane branch and its events are never stamped: it must not trip the missing-stamp refusal."""
    mission = build_lanes_mission(tmp_path, with_planning_lane_wp=True)

    claim = _claim(mission)

    assert claim.refusal is None
    assert [branch for branch, _sha in claim.bound_lane_tips] == [mission.lane_branches["WP01"]]


def test_claim_refuses_a_rewritten_lane(tmp_path: Path) -> None:
    mission = build_lanes_mission(tmp_path)
    lane = mission.lane_branches["WP01"]
    mission_git = _Repo(mission.repo)
    mission_git.git("checkout", "-q", lane)
    mission_git.git("commit", "-q", "--amend", "-m", "rewritten after approval")
    mission_git.git("checkout", "-q", mission.target_branch)

    claim = _claim(mission)

    assert claim.refusal is not None and claim.refusal.startswith("APPROVAL_STAMP_NOT_ON_LANE: ")


@pytest.mark.parametrize("target_already_advanced", [False, True], ids=["fresh_run", "resume_after_the_target_advanced"])
def test_claim_measures_a_lane_from_the_target_tip_when_the_mission_branch_already_carries_its_late_commit(tmp_path: Path, target_already_advanced: bool) -> None:
    """The interrupted-run case: the mission branch holds a post-approval lane commit, the target's pre-mutation tip does not.

    On a resume the interrupted run may also have advanced the live target to that commit. A
    planning lane the code lane depends on resolves to that live target branch, which must
    never serve as an anchor: it would exempt the very commit the bound exists to find.
    """
    from dataclasses import replace

    mission = build_lanes_mission(tmp_path, with_planning_lane_wp=True, planning_depends_on_code=False)
    lane = mission.lane_branches["WP01"]
    git = _Repo(mission.repo)
    pre_mutation_target = git.tip(mission.target_branch)
    git.git("checkout", "-q", lane)
    late = git.commit("src/late.py")
    git.git("checkout", "-q", mission.target_branch)
    git.git("update-ref", f"refs/heads/{mission.coord_branch}", late)
    if target_already_advanced:
        git.git("update-ref", f"refs/heads/{mission.target_branch}", late)

    from specify_cli.lanes.persistence import read_lanes_json

    manifest = read_lanes_json(mission.feature_dir)
    assert manifest is not None
    depends_on_planning = [replace(item, depends_on_lanes=("lane-planning",)) if item.lane_id == "lane-a" else item for item in manifest.lanes]
    manifest = replace(manifest, lanes=depends_on_planning)
    claim = build_approved_wp_set(
        mission.repo,
        mission.feature_dir,
        manifest,
        coord_base_ref=mission.coord_branch,
        excluded_window_base=pre_mutation_target,
    )

    assert claim.refusal is not None and claim.refusal.startswith("LANE_MOVED_AFTER_APPROVAL: ")
    assert late[:7] in claim.refusal


def test_claim_refuses_when_the_event_log_cannot_be_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.status import StoreError

    def _unreadable(*_args: object, **_kwargs: object) -> object:
        raise StoreError("status.events.jsonl is unreadable")

    mission = build_lanes_mission(tmp_path)
    monkeypatch.setattr("specify_cli.status.read_events", _unreadable)

    claim = _claim(mission)

    assert claim.refusal is not None
    assert "the approvals of lane lane-a cannot be bounded to what was reviewed" in claim.refusal
    assert "repair or restore status.events.jsonl, then re-run" in claim.refusal


# ---------------------------------------------------------------------------
# lane_tips_moved_refusal (the gate re-check)
# ---------------------------------------------------------------------------


def _two_lane_manifest(repo: _Repo) -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug=_SLUG,
        mission_id="01M444QR0000000000000000AA",
        mission_branch="mission",
        target_branch="main",
        lanes=[
            ExecutionLane(lane_id=lane_id, wp_ids=(wp,), write_scope=("src",), predicted_surfaces=("code",), depends_on_lanes=(), parallel_group=0)
            for lane_id, wp in (("lane-a", "WP01"), ("lane-b", "WP02"))
        ],
        computed_at="2026-10-04T00:00:00Z",
        computed_from="approved-bound-unit",
    )


def _gate_recheck(repo: _Repo, manifest: LanesManifest, validated: dict[str, str], anchors: Sequence[str]) -> str | None:
    refusal: str | None = lane_tips_moved_refusal(
        repo.root, manifest, validated_tips=validated, anchor_shas=anchors, planning_prefix=_BOOKKEEPING_PREFIX.rstrip("/")
    )
    return refusal


def test_gate_recheck_refuses_content_after_the_validated_tip_but_not_a_merge_of_a_validated_tip_or_an_anchor(repo: _Repo) -> None:
    from specify_cli.lanes.compute import lane_created_branch

    manifest = _two_lane_manifest(repo)
    branch_a, branch_b = (lane_created_branch(manifest, lane_id) for lane_id in ("lane-a", "lane-b"))
    repo.git("branch", "-m", _BRANCH, branch_a)
    repo.commit("src/a.py")
    repo.git("checkout", "-q", "main")
    repo.branch_from(branch_b, "base")
    repo.commit("src/b.py")
    repo.git("checkout", "-q", "main")
    repo.branch_from("mission", "base")
    repo.commit("src/consolidated.py")
    anchor = repo.tip("mission")
    validated = {branch_a: repo.tip(branch_a), branch_b: repo.tip(branch_b)}
    repo.git("checkout", "-q", branch_a)

    repo.merge(branch_b)  # another lane's validated tip
    repo.merge("mission")  # an anchor
    assert _gate_recheck(repo, manifest, validated, [anchor]) is None

    late = repo.commit("src/late.py")
    refusal = _gate_recheck(repo, manifest, validated, [anchor])
    assert refusal is not None and refusal.startswith("LANE_MOVED_AFTER_APPROVAL: ")
    assert late[:7] in refusal and "lane-a" in refusal and "WP01" in refusal


def test_gate_recheck_names_only_the_approved_work_packages_when_given_them(repo: _Repo) -> None:
    manifest = _two_lane_manifest(repo)
    lane = manifest.lanes[0]
    mixed = LanesManifest(
        version=manifest.version,
        mission_slug=manifest.mission_slug,
        mission_id=manifest.mission_id,
        mission_branch=manifest.mission_branch,
        target_branch=manifest.target_branch,
        lanes=[ExecutionLane(**{**lane.__dict__, "wp_ids": ("WP01", "WP02")})],
        computed_at=manifest.computed_at,
        computed_from=manifest.computed_from,
    )
    from specify_cli.lanes.compute import lane_created_branch

    branch = lane_created_branch(mixed, "lane-a")
    repo.git("branch", "-m", _BRANCH, branch)
    validated = {branch: repo.tip(branch)}
    repo.commit("src/late.py")

    refusal = lane_tips_moved_refusal(
        repo.root,
        mixed,
        validated_tips=validated,
        anchor_shas=[],
        planning_prefix=_BOOKKEEPING_PREFIX.rstrip("/"),
        approved_wp_ids={"lane-a": ["WP01"]},
    )

    assert refusal is not None
    assert "move-task WP01 " in refusal and "WP02" not in refusal


def test_gate_recheck_turns_a_git_probe_error_into_a_refusal_and_passes_an_unmoved_lane(repo: _Repo, monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    from specify_cli.consolidation import phase_gate
    from specify_cli.consolidation.reconciliation import VerifyStatus

    manifest = _two_lane_manifest(repo)
    run: Any = SimpleNamespace(main_repo=repo.root, lanes_manifest=manifest, validated_lane_tips={}, bound_anchor_shas=())
    claim = ApprovedWpCommitSet(approved={"WP01": ("a" * 40,)}, planning_prefix=_BOOKKEEPING_PREFIX.rstrip("/"))

    assert phase_gate._lane_recheck_verdict(run, claim) is None

    def _probe_failed(*_args: object, **_kwargs: object) -> str:
        raise GitProbeError("rev-list failed")

    monkeypatch.setattr(phase_gate, "lane_tips_moved_refusal", _probe_failed)
    verdict = phase_gate._lane_recheck_verdict(run, claim)

    assert verdict is not None and verdict.status is VerifyStatus.REFUSE
    assert verdict.refusal_reason == "a git probe failed while re-checking the lane tips against their approval: rev-list failed"


def test_bound_anchor_shas_leave_out_a_reference_that_does_not_resolve(repo: _Repo) -> None:
    from types import SimpleNamespace

    from specify_cli.consolidation import phase_claim

    manifest = _two_lane_manifest(repo)
    target = repo.tip("main")
    run: Any = SimpleNamespace(main_repo=repo.root, lanes_manifest=manifest, target_expected_old_sha=target)

    anchors = phase_claim._bound_anchor_shas(run, "no-such-coordination-base")

    assert anchors == (target,), "the unresolvable mission branch and coordination base are left out, the target is not repeated"


@pytest.mark.parametrize(
    ("to_lane", "stamp", "wp_id", "expected"),
    [
        pytest.param(
            Lane.APPROVED, None, "WP01", "WP01's approval; `spec-kitty consolidate` will refuse it (APPROVAL_STAMP_MISSING)", id="unstamped-code-lane-approval"
        ),
        pytest.param(
            Lane.DONE, None, "WP01", "WP01's approval; `spec-kitty consolidate` will refuse it (APPROVAL_STAMP_MISSING)", id="unstamped-review-straight-to-done"
        ),
        pytest.param(Lane.APPROVED, "a" * 40, "WP01", None, id="stamped-approval"),
        pytest.param(Lane.IN_PROGRESS, None, "WP01", None, id="not-an-approval"),
        pytest.param(Lane.APPROVED, None, "WP99", None, id="work-package-on-no-lane"),
    ],
)
def test_unstamped_approval_warning_names_only_an_unstamped_code_lane_approval(
    tmp_path: Path, to_lane: Lane, stamp: str | None, wp_id: str, expected: str | None
) -> None:
    mission = build_lanes_mission(tmp_path)
    holder = _Repo(Path("."))
    holder.event(wp_id, to_lane, stamp)

    warning = bound.unstamped_approval_warning(holder.events[0], repo_root=mission.repo, mission_slug=mission.slug)

    assert (warning is not None and expected is not None and expected in warning) or (warning is None and expected is None)


def test_unstamped_approval_warning_is_silent_when_the_lane_map_cannot_be_read_and_without_an_event(tmp_path: Path) -> None:
    holder = _Repo(Path("."))
    holder.event("WP01", Lane.APPROVED, None)

    assert bound.unstamped_approval_warning(holder.events[0], repo_root=tmp_path / "no-repo", mission_slug="no-mission") is None
    assert bound.unstamped_approval_warning(None, repo_root=tmp_path, mission_slug="no-mission") is None


def test_the_public_entry_reads_a_lane_whose_branch_is_gone_as_empty_and_names_a_late_commit(tmp_path: Path) -> None:
    """``approved_bound_refusal`` is what ``consolidate-mission`` calls: a vanished lane branch is not a refusal, a late commit is."""
    from specify_cli.consolidation.reconciliation import approved_bound_refusal
    from specify_cli.lanes.persistence import read_lanes_json

    mission = build_lanes_mission(tmp_path)
    manifest = read_lanes_json(mission.feature_dir)
    assert manifest is not None
    lane = mission.lane_branches["WP01"]
    git = _Repo(mission.repo)
    base = git.tip(mission.target_branch)

    def refusal() -> str | None:
        text: str | None = approved_bound_refusal(mission.repo, mission.feature_dir, manifest, coord_base_ref=mission.coord_branch, excluded_window_base=base)
        return text

    assert refusal() is None
    git.git("checkout", "-q", lane)
    late = git.commit("src/late.py")
    git.git("checkout", "-q", mission.target_branch)
    text = refusal()
    assert text is not None and text.startswith("LANE_MOVED_AFTER_APPROVAL: ") and late[:7] in text

    git.git("branch", "-D", lane)
    assert refusal() is None


# ---------------------------------------------------------------------------
# the forced-approval warning (#5721)
# ---------------------------------------------------------------------------


def _forced_event(holder: _Repo, **extra: Any) -> StatusEvent:
    holder.event("WP01", Lane.APPROVED, "s2", **extra)
    return holder.events[-1]


def test_forced_approval_warning_names_a_forced_approval_that_records_no_review() -> None:
    holder = _Repo(Path("."))
    event = _forced_event(holder, **_forced_from("in_progress"))

    warning = bound.forced_approval_warning(event, lambda: holder.events)

    assert warning is not None and "forced approval of WP01 is not a review approval" in warning
    assert "last review approval" in warning and "LANE_MOVED_AFTER_APPROVAL" in warning


def test_a_forced_non_review_approval_prints_only_the_forced_warning(tmp_path: Path) -> None:
    """Classified once: the forced warning already says an unstamped work package refuses, so the unstamped line is not repeated."""
    mission = build_lanes_mission(tmp_path)
    holder = _Repo(Path("."))
    holder.event("WP01", Lane.APPROVED, None, **_forced_from("in_progress"))

    warnings = bound.approval_warnings(holder.events[0], lambda: holder.events, repo_root=mission.repo, mission_slug=mission.slug)

    assert len(warnings) == 1 and "is not a review approval" in warnings[0]


@_REGRESSION
def test_an_unstamped_arbiter_override_still_warns(tmp_path: Path) -> None:
    """#5721: an arbiter override is a review approval, so the forced warning is silent and the unstamped warning must print."""
    mission = build_lanes_mission(tmp_path)
    holder = _Repo(Path("."))
    holder.event("WP01", Lane.PLANNED, None, **_REJECTION)
    holder.event("WP01", Lane.APPROVED, None, force=True, from_lane=Lane.PLANNED)
    override = holder.events[-1]

    warnings = bound.approval_warnings(override, lambda: holder.events, repo_root=mission.repo, mission_slug=mission.slug)

    assert len(warnings) == 1 and "APPROVAL_STAMP_MISSING" in warnings[0]
    assert bound.unstamped_approval_warning(override, repo_root=mission.repo, mission_slug=mission.slug) is not None


def test_an_unclassifiable_forced_approval_falls_back_to_the_unstamped_warning(tmp_path: Path) -> None:
    """When the log cannot be read the forced warning is silent, so an unstamped approval still warns."""
    mission = build_lanes_mission(tmp_path)
    holder = _Repo(Path("."))
    holder.event("WP01", Lane.APPROVED, None, **_forced_from("in_progress"))

    def unreadable() -> list[StatusEvent]:
        raise OSError("log gone")

    warnings = bound.approval_warnings(holder.events[0], unreadable, repo_root=mission.repo, mission_slug=mission.slug)

    assert len(warnings) == 1 and "APPROVAL_STAMP_MISSING" in warnings[0]
    assert bound.approval_warnings(None, unreadable, repo_root=mission.repo, mission_slug=mission.slug) == []


@pytest.mark.parametrize(
    "extra",
    [
        pytest.param(_REVIEWED_FORCE, id="review-result-after-a-genuine-claim"),
        pytest.param({"force": True, "from_lane": Lane.APPROVED, "metadata": {ATTESTATION_KEY: bound.APPROVED_REVIEWED}}, id="attestation"),
        pytest.param({"force": False, "from_lane": Lane.IN_REVIEW}, id="unforced"),
    ],
)
def test_forced_approval_warning_is_silent_for_a_review_or_an_unforced_approval(extra: dict[str, Any]) -> None:
    holder = _Repo(Path("."))
    lane, stamp, metadata, actor, claim = _GENUINE_CLAIM
    holder.event("WP01", Lane(lane), stamp, actor=actor, metadata=metadata, **claim)
    event = _forced_event(holder, **extra)

    assert bound.forced_approval_warning(event, lambda: holder.events) is None


@_REGRESSION
@pytest.mark.parametrize(
    ("claim", "extra"),
    [
        pytest.param(_GENUINE_CLAIM, _EXPLICIT_APPROVAL_REF, id="explicit-approval-ref"),
        pytest.param(_FORCED_CLAIM, _REVIEWED_FORCE, id="review-result-after-a-forced-in-review-entry"),
    ],
)
def test_forced_approval_warning_names_a_stated_reference_and_a_forced_review_entry(
    claim: tuple[str, str | None, dict[str, str], str, dict[str, Any]], extra: dict[str, Any]
) -> None:
    """#5721: neither a typed reference nor a review_result after a forced entry into in_review is a review."""
    holder = _Repo(Path("."))
    lane, stamp, metadata, actor, claim_extra = claim
    holder.event("WP01", Lane(lane), stamp, actor=actor, metadata=metadata, **claim_extra)
    event = _forced_event(holder, **extra)

    warning = bound.forced_approval_warning(event, lambda: holder.events)

    assert warning is not None and "is not a review approval" in warning


def test_a_force_override_reference_is_not_review_evidence() -> None:
    """#5721: ``_approval_evidence`` falls back to ``force-override`` when no ``--approval-ref`` is given."""
    holder = _Repo(Path("."))
    evidence = DoneEvidence(review=ReviewApproval(reviewer=_DETECTED_REVIEWER, verdict="approved", reference="force-override"))
    event = _forced_event(holder, force=True, from_lane=Lane.FOR_REVIEW, evidence=evidence)

    warning = bound.forced_approval_warning(event, lambda: holder.events)

    assert warning is not None and "is not a review approval" in warning


def test_forced_approval_warning_is_silent_for_an_arbiter_override_and_when_the_log_is_unreadable() -> None:
    holder = _Repo(Path("."))
    holder.event("WP01", Lane.PLANNED, None, **_REJECTION)
    override = _forced_event(holder, force=True, from_lane=Lane.PLANNED)

    def unreadable() -> list[StatusEvent]:
        raise OSError("log gone")

    assert bound.forced_approval_warning(override, lambda: holder.events) is None
    assert bound.forced_approval_warning(_forced_event(_Repo(Path(".")), **_forced_from("approved")), unreadable) is None
    assert bound.forced_approval_warning(None, lambda: []) is None


def test_forced_approval_warning_never_fails_on_an_event_it_cannot_classify(monkeypatch: pytest.MonkeyPatch) -> None:
    """The warning is advisory and printed after the move landed: a classification error is no warning (#5721)."""
    event = _forced_event(_Repo(Path(".")), **_forced_from("approved"))

    def broken(*_args: object, **_kwargs: object) -> bool:
        raise ValueError("not a valid Lane")

    monkeypatch.setattr(bound, "_is_forced_review_approval", broken)
    assert bound.forced_approval_warning(event, lambda: []) is None


def test_move_task_prints_the_forced_approval_warning_on_stderr(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    from specify_cli.cli.commands.agent import tasks as tasks_module
    from specify_cli.cli.commands.agent.tasks_move_task_executor import _mt_warn_approval

    holder = _Repo(Path("."))
    event = _forced_event(holder, **_forced_from("in_progress"))
    monkeypatch.setattr(tasks_module, "read_events_transactional", lambda **_: holder.events)
    monkeypatch.setattr(bound, "_maps_to_code_lane", lambda *_args: True)
    state: Any = SimpleNamespace(event=event, feature_dir=Path("."), mission_slug=_SLUG, main_repo_root=Path("."), owned=None)

    _mt_warn_approval(state)

    captured = capsys.readouterr()
    assert "forced approval of WP01 is not a review approval" in captured.err and captured.out == ""

    state.event = None
    _mt_warn_approval(state)
    assert capsys.readouterr().err == ""


def test_approval_warnings_never_fail_on_an_event_they_cannot_classify() -> None:
    """The warnings are advisory and printed after the move landed: an unclassifiable event is no warning (#5721)."""
    from types import SimpleNamespace
    from typing import cast

    odd_event = cast(StatusEvent, SimpleNamespace(wp_id="WP01", to_lane="approved"))  # no force / evidence / policy_metadata
    assert bound.approval_warnings(odd_event, lambda: [], repo_root=Path("."), mission_slug="m") == []


def test_approval_warnings_are_silent_outside_a_code_lane(monkeypatch: pytest.MonkeyPatch) -> None:
    """A lane that is not bounded (a ``lanes`` planning lane, or a ``single_branch`` Mission with no minted Mission branch) gets neither warning (#5721, #7283)."""
    holder = _Repo(Path("."))
    event = _forced_event(holder, **_forced_from("in_progress"))

    monkeypatch.setattr(bound, "_maps_to_code_lane", lambda *_args: True)
    assert bound.approval_warnings(event, lambda: holder.events, repo_root=Path("."), mission_slug=_SLUG)

    monkeypatch.setattr(bound, "_maps_to_code_lane", lambda *_args: False)
    assert bound.approval_warnings(event, lambda: holder.events, repo_root=Path("."), mission_slug=_SLUG) == []
