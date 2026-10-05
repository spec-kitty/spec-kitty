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
from specify_cli.status import LANE_HEAD_KEY, Lane, StatusEvent
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

    def event(self, wp_id: str, to_lane: Lane, stamp: str | None, *, actor: str = "claude", metadata: dict[str, str] | None = None) -> None:
        self.seq += 1
        policy = dict(metadata or {})
        if stamp:
            policy[LANE_HEAD_KEY] = stamp
        self.events.append(
            StatusEvent(
                event_id=f"e{self.seq}",
                mission_slug=_SLUG,
                wp_id=wp_id,
                from_lane=Lane.IN_REVIEW,
                to_lane=to_lane,
                at=f"2026-10-04T00:00:{self.seq:02d}Z",
                actor=actor,
                force=False,
                execution_mode="worktree",
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


@pytest.mark.parametrize(
    ("steps", "expected"),
    [
        pytest.param(
            [("approved", "s1", {}, "claude"), ("in_progress", "s2", {}, "claude"), ("approved", "s3", {}, "claude")], "s3", id="latest-approval-after-rework"
        ),
        pytest.param([("approved", "s1", {}, "claude"), ("approved", None, {}, "claude")], None, id="newer-unstamped-approval-hides-older-stamped-one"),
        pytest.param([("approved", "s1", {}, "claude"), ("approved", "s9", {}, "migration:backfill")], "s1", id="migration-event-ignored"),
        pytest.param([("approved", "s1", {}, "claude"), ("done", "s7", {}, "merge")], "s1", id="done-restamp-ignored"),
        pytest.param(
            [("approved", None, {}, "claude"), ("approved", "s5", {ATTESTATION_KEY: bound.APPROVED_REVIEWED}, "operator")], "s5", id="attestation-supplies-stamp"
        ),
        pytest.param([("done", "s7", {}, "merge")], None, id="done-without-approved-event"),
    ],
)
def test_approval_stamp_selection(steps: list[tuple[str, str | None, dict[str, str], str]], expected: str | None) -> None:
    holder = _Repo(Path("."))
    for lane, stamp, metadata, actor in steps:
        holder.event("WP01", Lane(lane), stamp, actor=actor, metadata=metadata)
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


def test_claim_measures_a_lane_from_the_target_tip_when_the_mission_branch_already_carries_its_late_commit(tmp_path: Path) -> None:
    """The interrupted-run case: the mission branch holds a post-approval lane commit, the target's pre-mutation tip does not."""
    mission = build_lanes_mission(tmp_path)
    lane = mission.lane_branches["WP01"]
    git = _Repo(mission.repo)
    git.git("checkout", "-q", lane)
    late = git.commit("src/late.py")
    git.git("checkout", "-q", mission.target_branch)
    git.git("update-ref", f"refs/heads/{mission.coord_branch}", late)

    from specify_cli.lanes.persistence import read_lanes_json

    manifest = read_lanes_json(mission.feature_dir)
    assert manifest is not None
    claim = build_approved_wp_set(
        mission.repo,
        mission.feature_dir,
        manifest,
        coord_base_ref=mission.coord_branch,
        excluded_window_base=git.tip(mission.target_branch),
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


def test_commits_beyond_needs_an_excluded_ref(repo: _Repo) -> None:
    with pytest.raises(ValueError, match="needs at least one excluded ref"):
        bound.commits_beyond(repo.root, "HEAD", [])


@pytest.mark.parametrize(
    ("to_lane", "stamp", "wp_id", "expected"),
    [
        pytest.param(
            Lane.APPROVED, None, "WP01", "WP01's approval; `spec-kitty consolidate` will refuse it (APPROVAL_STAMP_MISSING)", id="unstamped-code-lane-approval"
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
