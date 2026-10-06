"""The single rollback authority on REAL temp git repos (WP02 / T010).

No git mocking. Contract guarantees (``contracts/rollback-authority.md``) covered:

* G1 (never moves an unsnapshotted branch): ``test_branch_outside_snapshot_is_never_touched``
* G2 (CAS on recorded post tip; UNCHANGED_BY_RUN; per-attempt targets):
  ``test_cas_conflict_*``, ``test_operator_fix_between_attempts_*``,
  ``test_restore_target_truth_table``, ``test_moved_without_recorded_post_tip_*``
* G3 (FR-011): ``test_verified_landing_*``; missing branches (F3): ``test_deleted_*``
* G4 (resync / dirty refusal): ``test_full_restore``, ``test_dirty_primary_checkout_*``
* G5 (bookkeeping only after full restore; idempotent): ``test_full_restore``,
  ``test_cas_conflict_*``, ``test_rollback_is_idempotent``
* NFR-001: ``test_four_lane_rollback_is_fast``
* Rollback anchor authority (#5686): unsettled branches and the classifier
  (``test_restore_target_truth_table``, ``test_begin_attempt_*``,
  ``test_own_move_*``), intent chains and the effective post (``test_intent_*``),
  FR-007 (``test_fr007_*``), operator release (``test_release_*``), settle /
  unsettle (``test_rollback_settles_*``, ``test_settle_branch_*``) and the
  read-only pre-check (``test_unexplained_branches_*``).
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import pytest

from specify_cli.consolidation.rollback import (
    BranchOutcomeKind,
    OwnMove,
    RollbackReport,
    _classify,
    begin_attempt,
    capture_pre_mutation_snapshot,
    clear_advance_intents,
    missing_snapshot_branches,
    note_advance_intent,
    record_post_mutation_tips,
    release_branch,
    rollback_to_snapshot,
    run_movable_branches,
    settle_branch,
    snapshot_branches,
    unexplained_branches,
)
from specify_cli.consolidation.state import UNSETTLED_ALL, ConsolidationState, get_state_path, load_state
from specify_cli.lanes.compute import lane_created_branch
from specify_cli.lanes.models import ExecutionLane, LanesManifest

pytestmark = [pytest.mark.git_repo, pytest.mark.fast]

_SLUG = "m-01ABCDEF"
_MISSION_BRANCH = f"kitty/mission-{_SLUG}"
_TARGET = "develop"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()


def _commit(repo: Path, name: str) -> str:
    (repo / f"{name.replace('/', '_')}.txt").write_text(f"{name}\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", name)
    return _git(repo, "rev-parse", "HEAD")


def _rev(repo: Path, branch: str) -> str:
    return _git(repo, "rev-parse", f"refs/heads/{branch}")


def _commit_on(repo: Path, branch: str, name: str) -> str:
    """Commit on ``branch`` without disturbing the primary checkout (uses a temp worktree if needed)."""
    if _git(repo, "rev-parse", "--abbrev-ref", "HEAD") == branch:
        return _commit(repo, name)
    wt = repo.parent / f"wt-{name}"
    _git(repo, "worktree", "add", "-q", str(wt), branch)
    try:
        return _commit(wt, name)
    finally:
        _git(repo, "worktree", "remove", "--force", str(wt))


@dataclass
class Env:
    repo: Path
    manifest: LanesManifest
    state: ConsolidationState
    lane_branches: list[str]


def _manifest(lane_ids: list[str], *, planning: bool = False) -> LanesManifest:
    lanes = [ExecutionLane(lane_id=lid, wp_ids=("WP01",), write_scope=(), predicted_surfaces=(), depends_on_lanes=(), parallel_group=0) for lid in lane_ids]
    if planning:
        lanes.append(ExecutionLane(lane_id="lane-planning", wp_ids=("WP99",), write_scope=(), predicted_surfaces=(), depends_on_lanes=(), parallel_group=0))
    return LanesManifest(
        version=1,
        mission_slug=_SLUG,
        mission_id="01ABCDEF" + "0" * 18,
        mission_branch=_MISSION_BRANCH,
        target_branch=_TARGET,
        lanes=lanes,
        computed_at="2026-01-01T00:00:00+00:00",
        computed_from="test",
    )


def make_env(tmp_path: Path, lane_ids: list[str] | None = None, *, planning: bool = False) -> Env:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-qb", _TARGET, str(repo)], check=True)
    for key, value in (("user.email", "t@t.com"), ("user.name", "T"), ("commit.gpgsign", "false")):
        _git(repo, "config", key, value)
    (repo / ".gitignore").write_text(".kittify/runtime/\n")  # as in real projects: merge state is never tracked
    _commit(repo, "base")
    manifest = _manifest(lane_ids or ["lane-a", "lane-b"], planning=planning)
    _git(repo, "branch", _MISSION_BRANCH)
    lane_branches = []
    for lane in manifest.lanes:
        branch = lane_created_branch(manifest, lane.lane_id)
        if branch != _TARGET:
            _git(repo, "branch", branch, _MISSION_BRANCH)
            lane_branches.append(branch)
    state = ConsolidationState(mission_id="M1", mission_slug=_SLUG, target_branch=_TARGET, wp_order=["WP01"])
    return Env(repo, manifest, state, lane_branches)


def _advance_run(env: Env) -> dict[str, str]:
    """Simulate a consolidation attempt: advance target + mission branch, record post tips."""
    _commit_on(env.repo, _MISSION_BRANCH, "mission-advance")
    _commit_on(env.repo, _TARGET, "target-advance")
    record_post_mutation_tips(env.repo, env.state)
    return dict(env.state.post_mutation_refs)


def _snapshot_and_begin(env: Env, coord_ref: str | None = None) -> dict[str, str]:
    snap = capture_pre_mutation_snapshot(env.repo, env.state, env.manifest, coord_ref=coord_ref)
    begin_attempt(env.repo, env.state)
    return snap


def _kinds(report: RollbackReport) -> dict[str, BranchOutcomeKind]:
    return {o.branch: o.kind for o in report.outcomes}


# ------------------------------------------------------------------ capture


def test_capture_snapshots_all_branches_and_persists(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    snap = _snapshot_and_begin(env)
    assert set(snap) == {_TARGET, _MISSION_BRANCH, *env.lane_branches}
    assert all(snap[b] == _rev(env.repo, b) for b in snap)
    persisted = load_state(env.repo, "M1")
    assert persisted is not None and persisted.pre_mutation_refs == snap


def test_capture_never_recaptures(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    first = _snapshot_and_begin(env)
    _advance_run(env)
    second = capture_pre_mutation_snapshot(env.repo, env.state, env.manifest, coord_ref=None)
    assert second == first


def test_capture_lanes_topology_dedupes_planning_lane_onto_target(tmp_path: Path) -> None:
    env = make_env(tmp_path, ["lane-a"], planning=True)
    snap = snapshot_branches(env.repo, env.manifest, coord_ref=None)
    assert list(snap).count(_TARGET) == 1
    assert set(snap) == {_TARGET, _MISSION_BRANCH, *env.lane_branches}


def test_capture_skips_missing_lane_branch_and_reports_it(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    _git(env.repo, "branch", "-D", env.lane_branches[0])
    snap = snapshot_branches(env.repo, env.manifest, coord_ref=None)
    assert env.lane_branches[0] not in snap
    assert missing_snapshot_branches(env.repo, env.manifest, coord_ref=None) == [env.lane_branches[0]]


def test_capture_seeds_target_and_coord_from_persisted_anchors(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    coord = "kitty/coord-x"
    _git(env.repo, "branch", coord)
    seed_target, seed_coord = "a" * 40, "b" * 40
    env.state.pre_mutation_target_sha = seed_target
    env.state.pre_mutation_coord_sha = seed_coord
    env.state.pre_mutation_coord_ref = coord
    snap = capture_pre_mutation_snapshot(env.repo, env.state, env.manifest, coord_ref=coord)
    assert snap[_TARGET] == seed_target
    assert snap[coord] == seed_coord


def test_resume_seeded_snapshot_is_marked_and_worded_as_such(tmp_path: Path) -> None:
    """Slice-10 F8: resuming a pre-fix record (no snapshot) captures the mission branch and lanes LIVE.

    Those entries are not "pre-consolidation" commits: they are marked in the state
    and the report words them as the snapshot taken when this record was resumed.
    The target, seeded from the persisted pre-mutation anchor, stays pre-consolidation.
    """
    env = make_env(tmp_path)
    env.state.pre_mutation_target_sha = _rev(env.repo, _TARGET)  # the older record's persisted anchor
    capture_pre_mutation_snapshot(env.repo, env.state, env.manifest, coord_ref=None, is_resume=True)
    begin_attempt(env.repo, env.state)
    assert env.state.resume_seeded_refs == [_MISSION_BRANCH, *env.lane_branches]
    persisted = load_state(env.repo, "M1")
    assert persisted is not None and persisted.resume_seeded_refs == env.state.resume_seeded_refs
    _advance_run(env)

    text = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET).render()

    mission_line = next(line for line in text.splitlines() if _MISSION_BRANCH in line and "lane" not in line)
    target_line = next(line for line in text.splitlines() if _TARGET in line)
    assert "snapshot taken when this record was resumed" in mission_line
    assert "snapshot taken when this record was resumed" not in target_line
    assert not text.startswith("Rollback to the pre-consolidation snapshot:")


def test_fresh_snapshot_is_not_marked_resume_seeded(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    _snapshot_and_begin(env)
    assert env.state.resume_seeded_refs == []
    _advance_run(env)
    text = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET).render()
    assert text.startswith("Rollback to the pre-consolidation snapshot:")
    assert "resumed" not in text


# ------------------------------------------------------------------ rollback


def test_full_restore(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    snap = _snapshot_and_begin(env)
    env.state.mission_number_baked = True
    env.state.completed_wps = ["WP01"]
    env.state.reconciliation_passed_target_sha = "f" * 40  # this attempt's own (non-matching) anchor
    _advance_run(env)
    report = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)

    assert report.fully_restored and not report.advanced_branches
    kinds = _kinds(report)
    assert kinds[_TARGET] is kinds[_MISSION_BRANCH] is BranchOutcomeKind.RESTORED
    restored = {o.branch: o for o in report.outcomes if o.kind is BranchOutcomeKind.RESTORED}
    assert all(o.restored_to_sha == snap[b] and o.snapshot_sha == snap[b] for b, o in restored.items())
    assert [kinds[b] for b in env.lane_branches] == [BranchOutcomeKind.ALREADY_AT_SNAPSHOT] * 2
    assert {b: _rev(env.repo, b) for b in snap} == snap
    # primary checkout (on develop) is resynced: HEAD == index == worktree
    assert _git(env.repo, "status", "--porcelain") == ""
    assert not (env.repo / "target-advance.txt").exists()
    # bookkeeping cleared, snapshot + restore targets kept
    assert env.state.completed_wps == [] and env.state.mission_number_baked is False
    assert env.state.reconciliation_passed_target_sha is None
    assert env.state.post_mutation_refs == {} and env.state.pre_mutation_refs == snap
    assert env.state.restore_targets == snap


def test_cas_conflict_reports_not_restored_and_keeps_bookkeeping(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    _snapshot_and_begin(env)
    env.state.completed_wps = ["WP01"]
    post = _advance_run(env)
    other = _commit_on(env.repo, _MISSION_BRANCH, "other-actor")

    report = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)

    assert not report.fully_restored
    outcome = next(o for o in report.outcomes if o.branch == _MISSION_BRANCH)
    assert outcome.kind is BranchOutcomeKind.NOT_RESTORED
    assert outcome.reason is not None and "moved by another actor" in outcome.reason
    assert outcome.expected_sha == post[_MISSION_BRANCH] == env.state.post_mutation_refs[_MISSION_BRANCH]
    assert outcome.observed_sha == other
    assert _rev(env.repo, _MISSION_BRANCH) == other
    assert env.state.completed_wps == ["WP01"]
    assert report.advanced_branches == (_MISSION_BRANCH,)


def test_partial_rollback_that_restores_the_target_drops_its_stale_pass_anchor(tmp_path: Path) -> None:
    """F4: the target was restored, so the landing the anchor verified no longer exists, even when another branch is NOT_RESTORED."""
    env = make_env(tmp_path)
    _snapshot_and_begin(env)
    env.state.reconciliation_passed_target_sha = "f" * 40  # stale: not the live target, so no FR-011 refusal
    _advance_run(env)
    _commit_on(env.repo, _MISSION_BRANCH, "other-actor")

    report = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)

    kinds = _kinds(report)
    assert kinds[_TARGET] is BranchOutcomeKind.RESTORED and kinds[_MISSION_BRANCH] is BranchOutcomeKind.NOT_RESTORED
    persisted = load_state(env.repo, "M1")
    assert persisted is not None and persisted.reconciliation_passed_target_sha is None


def test_partial_rollback_that_keeps_the_target_keeps_the_pass_anchor(tmp_path: Path) -> None:
    """F4 negative: a target NOT restored keeps whatever anchor the record holds."""
    env = make_env(tmp_path)
    _snapshot_and_begin(env)
    env.state.reconciliation_passed_target_sha = "f" * 40
    _advance_run(env)
    _commit_on(env.repo, _TARGET, "other-actor-on-target")

    report = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)

    assert _kinds(report)[_TARGET] is BranchOutcomeKind.NOT_RESTORED
    persisted = load_state(env.repo, "M1")
    assert persisted is not None and persisted.reconciliation_passed_target_sha == "f" * 40


def test_operator_fix_between_attempts_is_kept_and_never_reverted(tmp_path: Path) -> None:
    """An operator commit on a RUN-MOVABLE branch between attempts becomes that branch's restore target.

    Slice-10 F2 premise change: lane branches are report-only now, so a lane fix is
    kept trivially (never restored). The per-attempt restore target still matters
    for the mission branch, which the next attempt advances ON TOP of the fix: the
    rollback must return it to the fix, not to the snapshot.
    """
    env = make_env(tmp_path)
    lane = env.lane_branches[0]
    snap = _snapshot_and_begin(env)
    _advance_run(env)
    assert rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET).fully_restored

    fix = _commit_on(env.repo, _MISSION_BRANCH, "operator-fix")
    lane_fix = _commit_on(env.repo, lane, "operator-lane-fix")
    begin_attempt(env.repo, env.state)
    assert env.state.restore_targets[_MISSION_BRANCH] == fix
    assert env.state.restore_targets[_TARGET] == snap[_TARGET]

    _advance_run(env)  # the attempt advances target + mission (on top of the fix)
    report = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)

    assert report.fully_restored
    mission = next(o for o in report.outcomes if o.branch == _MISSION_BRANCH)
    assert mission.kind is BranchOutcomeKind.RESTORED and mission.restored_to_sha == fix
    assert _rev(env.repo, _MISSION_BRANCH) == fix, "the operator's fix survives; only this attempt's advance is undone"
    assert _rev(env.repo, _TARGET) == snap[_TARGET]
    assert _kinds(report)[lane] is BranchOutcomeKind.ALREADY_AT_SNAPSHOT  # at its attempt-start value
    assert _rev(env.repo, lane) == lane_fix


def test_operator_fix_without_attempt_in_flight_is_unchanged_by_run(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    lane = env.lane_branches[0]
    _snapshot_and_begin(env)
    _advance_run(env)
    assert rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET).fully_restored
    fix = _commit_on(env.repo, lane, "operator-fix")

    report = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)  # e.g. a later --abort

    assert report.fully_restored
    assert _kinds(report)[lane] is BranchOutcomeKind.UNCHANGED_BY_RUN
    assert _rev(env.repo, lane) == fix


def test_lane_branches_are_report_only_even_with_a_recorded_post_tip(tmp_path: Path) -> None:
    """Slice-10 F2: consolidation never moves a lane branch, so a lane move is another actor's and is never reverted."""
    env = make_env(tmp_path)
    _snapshot_and_begin(env)
    lane = env.lane_branches[0]
    _advance_run(env)
    foreign = _commit_on(env.repo, lane, "agent-late-commit")
    env.state.post_mutation_refs[lane] = foreign  # even a (legacy) record naming the lane must not make it restorable

    report = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)

    assert _rev(env.repo, lane) == foreign, "another actor's lane commit must never be rolled back"
    assert _kinds(report)[lane] is BranchOutcomeKind.UNCHANGED_BY_RUN
    assert report.fully_restored, "a report-only lane never blocks the restore of the run's own branches"
    assert "lane branch: not moved by consolidation" in report.render()


def test_record_never_records_a_lane_branch(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    _snapshot_and_begin(env)
    lane = env.lane_branches[0]
    _commit_on(env.repo, lane, "lane-move")
    _advance_run(env)
    assert lane not in env.state.post_mutation_refs
    assert set(env.state.post_mutation_refs) == {_TARGET, _MISSION_BRANCH}


@pytest.mark.parametrize(
    ("previous_target", "effective_post", "live", "unsettled", "expected"),
    [
        # The previous target is the snapshot (the old truth table's rows, on a settled branch):
        ("S", None, "S", False, ("S", False)),  # attempt starts at the snapshot
        ("S", "P", "P", False, ("S", False)),  # attempt starts at consolidation's own previous post tip
        ("S", "P", "X", False, ("X", False)),  # somebody else moved a settled branch: keep (ADR A2)
        ("S", None, "X", False, ("X", False)),
        # The same rows on an unsettled branch: an explained tip keeps the target,
        ("S", None, "S", True, ("S", False)),
        ("S", "P", "P", True, ("S", False)),
        # and a tip that is neither the target nor the effective post is unexplained (FR-004).
        ("S", "P", "X", True, ("S", True)),
        ("S", None, "X", True, ("S", True)),
        # A previous target fixed by an earlier attempt stays in force (FR-007).
        ("M", "P", "P", True, ("M", False)),
        ("M", None, "M", True, ("M", False)),
        ("M", "P", "S", True, ("M", True)),
        ("M", "P", "S", False, ("S", False)),
    ],
)
def test_restore_target_truth_table(previous_target: str, effective_post: str | None, live: str, unsettled: bool, expected: tuple[str, bool]) -> None:
    assert _classify(previous_target, effective_post, live, unsettled) == expected


def test_moved_without_recorded_post_tip_is_not_restored_and_blocks(tmp_path: Path) -> None:
    """Slice-10 F1: a run-movable branch that moved but has no recorded post tip is NOT reported unchanged.

    The kill window: ``begin_attempt`` resets the post tips, a phase advances the
    mission branch, and the process dies before the phase's recorder runs. The
    authority cannot tell this run's advance from another actor's, so it must not
    restore it AND must not report it as untouched (which let ``--abort`` clear
    the record over an advanced branch).
    """
    env = make_env(tmp_path)
    _snapshot_and_begin(env)
    env.state.completed_wps = ["WP01"]
    tip = _commit_on(env.repo, _MISSION_BRANCH, "advanced-without-post")  # no record_post_mutation_tips
    report = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)
    assert not report.fully_restored
    outcome = next(o for o in report.outcomes if o.branch == _MISSION_BRANCH)
    assert outcome.kind is BranchOutcomeKind.NOT_RESTORED
    assert outcome.reason is not None and "no post-mutation tip was recorded" in outcome.reason
    assert "inspect before re-running" in outcome.reason
    assert _rev(env.repo, _MISSION_BRANCH) == tip
    assert report.advanced_branches == (_MISSION_BRANCH,)
    assert env.state.completed_wps == ["WP01"], "bookkeeping is kept when a branch was not restored"


def test_verified_landing_refuses_and_moves_nothing(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    _snapshot_and_begin(env)
    _advance_run(env)
    tips = {b: _rev(env.repo, b) for b in env.state.pre_mutation_refs}
    env.state.reconciliation_passed_target_sha = _rev(env.repo, _TARGET)

    report = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)

    assert report.refused_verified_landing and not report.fully_restored
    assert {b: _rev(env.repo, b) for b in tips} == tips
    assert "nothing was rolled back" in report.render()


def test_deleted_lane_branch_is_reported_with_a_recreate_hint_and_does_not_block(tmp_path: Path) -> None:
    """Slice-10 F3: a vanished LANE branch no longer wedges the rollback (was: refuse everything)."""
    env = make_env(tmp_path)
    snap = _snapshot_and_begin(env)
    _advance_run(env)
    lane = env.lane_branches[0]
    _git(env.repo, "branch", "-D", lane)

    report = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)

    assert report.fully_restored, "the run's own branches are restored; the missing lane is only reported"
    assert _kinds(report)[lane] is BranchOutcomeKind.LANE_MISSING
    assert _kinds(report)[_TARGET] is _kinds(report)[_MISSION_BRANCH] is BranchOutcomeKind.RESTORED
    assert {b: _rev(env.repo, b) for b in (_TARGET, _MISSION_BRANCH)} == {b: snap[b] for b in (_TARGET, _MISSION_BRANCH)}
    text = report.render()
    assert f"lane branch {lane} no longer exists" in text
    assert f"snapshot {snap[lane]}" in text and f"`git branch {lane} {snap[lane]}`" in text
    assert "nothing was rolled back" not in text.lower() and "Kept the landing" not in text


def test_deleted_run_movable_branch_is_not_restored_with_a_recreate_hint(tmp_path: Path) -> None:
    """Slice-10 F3: a vanished target/mission/coordination branch is NOT_RESTORED (never recreated silently)."""
    env = make_env(tmp_path)
    snap = _snapshot_and_begin(env)
    _advance_run(env)
    _git(env.repo, "branch", "-D", _MISSION_BRANCH)

    report = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)

    assert not report.fully_restored
    mission = next(o for o in report.outcomes if o.branch == _MISSION_BRANCH)
    assert mission.kind is BranchOutcomeKind.NOT_RESTORED
    assert f"`git branch {_MISSION_BRANCH} {snap[_MISSION_BRANCH]}`" in (mission.reason or "")
    assert _kinds(report)[_TARGET] is BranchOutcomeKind.RESTORED, "the other branches are still restored"
    assert report.advanced_branches == (_MISSION_BRANCH,)


def test_dirty_primary_checkout_is_not_restored(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    _snapshot_and_begin(env)
    post = _advance_run(env)
    (env.repo / "target-advance.txt").write_text("operator edit\n")

    report = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)

    assert not report.fully_restored
    assert _kinds(report)[_TARGET] is BranchOutcomeKind.NOT_RESTORED
    assert _rev(env.repo, _TARGET) == post[_TARGET]
    assert (env.repo / "target-advance.txt").read_text() == "operator edit\n"


def test_pre_fix_record_without_snapshot_is_a_noop(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    tips = {b: _rev(env.repo, b) for b in (_TARGET, _MISSION_BRANCH)}
    report = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)
    assert not report.fully_restored and report.outcomes == ()
    assert "pre-fix record" in (report.reason or "")
    assert {b: _rev(env.repo, b) for b in tips} == tips


def test_branch_outside_snapshot_is_never_touched(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    _git(env.repo, "branch", "unrelated")
    _snapshot_and_begin(env)
    _advance_run(env)
    tip = _commit_on(env.repo, "unrelated", "unrelated-work")
    rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)
    assert _rev(env.repo, "unrelated") == tip


def test_rollback_is_idempotent(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    _snapshot_and_begin(env)
    _advance_run(env)
    assert rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET).fully_restored
    again = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)
    assert again.fully_restored
    assert set(_kinds(again).values()) == {BranchOutcomeKind.ALREADY_AT_SNAPSHOT}


def test_coord_restore_clears_pending_coord_reconcile(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    coord = "kitty/coord-x"
    _git(env.repo, "branch", coord)
    env.state.pre_mutation_coord_ref = coord
    _snapshot_and_begin(env, coord_ref=coord)
    _commit_on(env.repo, coord, "coord-advance")
    _advance_run(env)
    env.state.pending_coord_reconcile = {"coord_ref": coord}
    assert rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET).fully_restored
    assert env.state.pending_coord_reconcile is None


def test_coord_cas_conflict_keeps_pending_coord_reconcile(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    coord = "kitty/coord-x"
    _git(env.repo, "branch", coord)
    env.state.pre_mutation_coord_ref = coord
    _snapshot_and_begin(env, coord_ref=coord)
    _commit_on(env.repo, coord, "coord-advance")
    _advance_run(env)
    _commit_on(env.repo, coord, "other-actor-on-coord")  # the coord CAS now conflicts
    env.state.pending_coord_reconcile = {"coord_ref": coord}

    report = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)

    assert not report.fully_restored
    assert _kinds(report)[coord] is BranchOutcomeKind.NOT_RESTORED
    assert env.state.pending_coord_reconcile == {"coord_ref": coord}, "the marker must survive a coord ref that was NOT restored"


_COORD_STATUS = f"kitty-specs/{_SLUG}/status.events.jsonl"


def _stranded_coord_checkout(env: Env) -> tuple[str, Path]:
    """#5638: a coord branch the rollback cannot restore, its worktree byte-restored to pre-``done`` bytes.

    The run commits a ``done`` line on the coordination branch, the bookkeeping
    byte-restore writes the pre-``done`` bytes back into the coordination
    worktree, and another actor commits on the branch so the CAS restore refuses.
    """
    coord = "kitty/coord-x"
    _git(env.repo, "branch", coord)
    worktree = env.repo.parent / "coord-wt"
    _git(env.repo, "worktree", "add", "-q", str(worktree), coord)
    status = worktree / _COORD_STATUS
    status.parent.mkdir(parents=True)
    status.write_text('{"to_lane":"approved"}\n')
    _git(worktree, "add", "-A")
    _git(worktree, "commit", "-qm", "approved")
    env.state.pre_mutation_coord_ref = coord
    _snapshot_and_begin(env, coord_ref=coord)
    status.write_text('{"to_lane":"approved"}\n{"to_lane":"done"}\n')
    _git(worktree, "commit", "-qam", "done bake")
    _advance_run(env)
    _commit(worktree, "other-actor-on-coord")
    status.write_text('{"to_lane":"approved"}\n')  # the bookkeeping byte-restore
    return coord, worktree


def test_coord_not_restored_leaves_its_checkout_status_files_at_the_coord_tip(tmp_path: Path) -> None:
    """#5638: the coordination checkout ends consistent with the coordination tip the rollback ends on."""
    env = make_env(tmp_path)
    coord, worktree = _stranded_coord_checkout(env)
    tip = _rev(env.repo, coord)

    report = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)

    assert _kinds(report)[coord] is BranchOutcomeKind.NOT_RESTORED
    assert _rev(env.repo, coord) == tip, "the coordination ref must never move when it is not restored"
    assert _git(worktree, "status", "--porcelain") == "", "the coordination checkout must not be left dirty against its own HEAD"
    assert '"done"' in (worktree / _COORD_STATUS).read_text(), "the committed `done` must be what the checkout shows"


def test_coord_not_restored_keeps_an_operator_edit_and_its_status_bytes(tmp_path: Path) -> None:
    """#5638: a non-toolchain edit in the coordination checkout blocks the resync; nothing there is discarded."""
    env = make_env(tmp_path)
    coord, worktree = _stranded_coord_checkout(env)
    (worktree / "other-actor-on-coord.txt").write_text("operator edit\n")

    report = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)

    assert _kinds(report)[coord] is BranchOutcomeKind.NOT_RESTORED
    assert (worktree / "other-actor-on-coord.txt").read_text() == "operator edit\n"
    assert (worktree / _COORD_STATUS).read_text() == '{"to_lane":"approved"}\n'
    rendered = report.render()
    assert "coordination checkout" in rendered, "a resync that was refused must be reported"
    assert "commit or stash" in rendered and "consolidate --resume" in rendered, "the refusal must carry an operator remedy"


# -------------------------------------------------------------------- render


def test_render_full_restore_and_conflict_text(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    _snapshot_and_begin(env)
    _advance_run(env)
    text = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET).render()
    assert text.startswith("Rollback to the pre-consolidation snapshot:")
    assert "restored" in text and "unchanged" in text
    assert "no refs/worktrees were mutated" not in text

    env2 = make_env(tmp_path / "second")
    _snapshot_and_begin(env2)
    _advance_run(env2)
    _commit_on(env2.repo, _MISSION_BRANCH, "other-actor")
    conflict = rollback_to_snapshot(env2.repo, env2.state, target_branch=_TARGET).render()
    assert "NOT restored" in conflict and "moved by another actor" in conflict
    assert "no refs/worktrees were mutated" not in conflict


def test_render_no_snapshot_and_kept_lane(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    assert "pre-fix record" in rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET).render()
    _snapshot_and_begin(env)
    _commit_on(env.repo, env.lane_branches[0], "kept")
    assert "kept" in rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET).render()


# ------------------------------------------------------------------- NFR-001


def test_four_lane_rollback_is_fast(tmp_path: Path) -> None:
    """NFR-001: a 4-lane rollback (3 restores with checkout resync, 4 report-only lanes) completes in < 2 s.

    Slice-10 F2: lanes are report-only, so the restored set is the run-movable one
    (target, mission, coordination), each checked out and resynced.
    """
    env = make_env(tmp_path, ["lane-a", "lane-b", "lane-c", "lane-d"])
    coord = "kitty/coord-x"
    _git(env.repo, "branch", coord)
    _snapshot_and_begin(env, coord_ref=coord)
    for index, lane in enumerate(env.lane_branches):  # each lane checked out in its own linked worktree
        wt = tmp_path / f"lane-wt-{index}"
        _git(env.repo, "worktree", "add", "-q", str(wt), lane)
        _commit(wt, f"adv-{index}")
    checkouts = {_MISSION_BRANCH: tmp_path / "mission-wt", coord: tmp_path / "coord-wt"}
    for branch, wt in checkouts.items():
        _git(env.repo, "worktree", "add", "-q", str(wt), branch)
        _commit(wt, f"adv-{wt.name}")
    _commit(env.repo, "target-advance")
    record_post_mutation_tips(env.repo, env.state)  # target, mission, coord -- never the lanes

    started = time.monotonic()
    report = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)
    elapsed = time.monotonic() - started

    restored = [o for o in report.outcomes if o.kind is BranchOutcomeKind.RESTORED]
    assert report.fully_restored and {o.branch for o in restored} == {_TARGET, _MISSION_BRANCH, coord}
    assert all(_kinds(report)[lane] is BranchOutcomeKind.UNCHANGED_BY_RUN for lane in env.lane_branches)
    assert all(_git(wt, "status", "--porcelain") == "" for wt in checkouts.values())
    print(f"NFR-001 measured rollback time: {elapsed:.3f}s for {len(restored)} restored branches")
    assert elapsed < 2.0, f"rollback took {elapsed:.3f}s (NFR-001 bound 2s)"


def test_begin_attempt_carries_forward_a_post_tip_for_a_branch_still_at_it(tmp_path: Path) -> None:
    """A resumed attempt that re-moves nothing keeps attempt 1's CAS expectation (restores, no wedge)."""
    env = make_env(tmp_path)
    snap = _snapshot_and_begin(env)
    posts = _advance_run(env)  # attempt 1 advanced target + mission branch and recorded them
    begin_attempt(env.repo, env.state)  # attempt 2 (resume) starts; no phase re-moves anything
    assert env.state.post_mutation_refs == posts, "tips still at attempt 1's post tip are carried forward"
    report = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)
    assert report.fully_restored, report.render()
    assert _rev(env.repo, _TARGET) == snap[_TARGET]
    assert _rev(env.repo, _MISSION_BRANCH) == snap[_MISSION_BRANCH]


def test_begin_attempt_refuses_to_re_anchor_an_unsettled_branch_moved_between_attempts(tmp_path: Path) -> None:
    """FR-004 (re-pinned): a commit on an UNSETTLED branch between attempts is unexplained, never adopted.

    Before #5686 the commit became the new restore target, which is how an
    unrecorded landing was later reported as already restored. Now
    ``begin_attempt`` returns the branch, changes nothing in the record, and the
    rollback reports it NOT restored and keeps the commit.
    """
    env = make_env(tmp_path)
    snap = _snapshot_and_begin(env)
    posts = _advance_run(env)
    foreign = _commit_on(env.repo, _MISSION_BRANCH, "between-attempts")
    before = _record(env)

    assert begin_attempt(env.repo, env.state) == [_MISSION_BRANCH]

    assert _record(env) == before, "a refusing begin_attempt changes nothing in the record"
    assert env.state.restore_targets[_MISSION_BRANCH] == snap[_MISSION_BRANCH]
    assert env.state.post_mutation_refs == posts
    report = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)
    assert _rev(env.repo, _MISSION_BRANCH) == foreign, "never overwritten"
    assert _kinds(report)[_MISSION_BRANCH] is BranchOutcomeKind.NOT_RESTORED
    assert not report.fully_restored


def test_begin_attempt_keeps_a_move_between_attempts_on_a_settled_branch(tmp_path: Path) -> None:
    """ADR A2 stays pinned: after a full restore, a between-attempts move becomes the new restore target."""
    env = make_env(tmp_path)
    _snapshot_and_begin(env)
    _advance_run(env)
    assert rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET).fully_restored
    foreign = _commit_on(env.repo, _MISSION_BRANCH, "between-attempts")

    assert begin_attempt(env.repo, env.state) == []

    assert _MISSION_BRANCH not in env.state.post_mutation_refs
    assert env.state.restore_targets[_MISSION_BRANCH] == foreign, "the between-attempts commit is the new restore target"
    report = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)
    assert _rev(env.repo, _MISSION_BRANCH) == foreign, "never overwritten"
    assert _kinds(report)[_MISSION_BRANCH] is BranchOutcomeKind.ALREADY_AT_SNAPSHOT


# ------------------------------------------------- rollback anchor authority (#5686)


def _record(env: Env) -> dict[str, object]:
    """The in-memory record without its save stamp (a refusing call must leave it identical)."""
    data = env.state.to_dict()
    data.pop("updated_at", None)
    return data


def _disk(env: Env) -> str:
    return get_state_path(env.repo, "M1").read_text(encoding="utf-8")


def _commit_tree(repo: Path, parent: str, name: str) -> str:
    """A commit object on top of ``parent`` that no branch points at (an advance not yet written)."""
    tree = _git(repo, "rev-parse", f"{parent}^{{tree}}")
    return _git(repo, "commit-tree", tree, "-p", parent, "-m", name)


def test_begin_attempt_marks_every_run_movable_branch_unsettled(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    coord = "kitty/coord-x"
    _git(env.repo, "branch", coord)
    _snapshot_and_begin(env, coord_ref=coord)
    assert sorted(env.state.unsettled_refs) == sorted([_TARGET, _MISSION_BRANCH, coord])
    assert sorted(run_movable_branches(env.state)) == sorted([_TARGET, _MISSION_BRANCH, coord])
    persisted = load_state(env.repo, "M1")
    assert persisted is not None and persisted.unsettled_refs == env.state.unsettled_refs


def test_intent_adoption_restores_a_kill_left_advance_by_cas_against_the_live_tip(tmp_path: Path) -> None:
    """FR-006: an advance this run wrote, with a persisted intent whose base is the expected tip, is RESTORED."""
    env = make_env(tmp_path)
    snap = _snapshot_and_begin(env)
    landed = _commit_tree(env.repo, snap[_MISSION_BRANCH], "squash")
    note_advance_intent(env.repo, env.state, _MISSION_BRANCH, snap[_MISSION_BRANCH], landed)
    persisted = load_state(env.repo, "M1")
    assert persisted is not None and persisted.advance_intents == {_MISSION_BRANCH: [snap[_MISSION_BRANCH], landed]}
    _git(env.repo, "update-ref", f"refs/heads/{_MISSION_BRANCH}", landed)  # killed before the recorder ran

    report = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)

    mission = next(o for o in report.outcomes if o.branch == _MISSION_BRANCH)
    assert mission.kind is BranchOutcomeKind.RESTORED and mission.adopted_intent
    assert mission.expected_sha == landed and mission.restored_to_sha == snap[_MISSION_BRANCH]
    assert _rev(env.repo, _MISSION_BRANCH) == snap[_MISSION_BRANCH]
    assert report.fully_restored
    assert "(adopted interrupted advance)" in report.render()
    assert env.state.advance_intents == {} and env.state.unsettled_refs == []


def test_intent_adoption_on_the_checked_out_target(tmp_path: Path) -> None:
    """Positive control on the primary checkout: the kill came after the resync, so the checkout is clean."""
    env = make_env(tmp_path)
    snap = _snapshot_and_begin(env)
    landed = _commit_on(env.repo, _TARGET, "squash-landed")
    note_advance_intent(env.repo, env.state, _TARGET, snap[_TARGET], landed)

    report = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)

    assert _kinds(report)[_TARGET] is BranchOutcomeKind.RESTORED and report.fully_restored
    assert _rev(env.repo, _TARGET) == snap[_TARGET]
    assert _git(env.repo, "status", "--porcelain") == ""


def test_intent_with_a_foreign_base_is_not_adopted(tmp_path: Path) -> None:
    """An intent whose base is not the tip the record expected proves nothing: NOT_RESTORED."""
    env = make_env(tmp_path)
    snap = _snapshot_and_begin(env)
    foreign_base = _commit_on(env.repo, _MISSION_BRANCH, "foreign")
    landed = _commit_tree(env.repo, foreign_base, "squash")
    note_advance_intent(env.repo, env.state, _MISSION_BRANCH, foreign_base, landed)
    _git(env.repo, "update-ref", f"refs/heads/{_MISSION_BRANCH}", landed)

    report = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)

    assert _kinds(report)[_MISSION_BRANCH] is BranchOutcomeKind.NOT_RESTORED
    assert _rev(env.repo, _MISSION_BRANCH) == landed
    assert snap[_MISSION_BRANCH] != foreign_base
    assert _MISSION_BRANCH in env.state.unsettled_refs


def test_intent_chain_adopts_the_first_write_of_two(tmp_path: Path) -> None:
    """Two advances in one span, killed after the first write: live == new1 is still provable."""
    env = make_env(tmp_path)
    snap = _snapshot_and_begin(env)
    first = _commit_tree(env.repo, snap[_MISSION_BRANCH], "first")
    second = _commit_tree(env.repo, first, "second")
    note_advance_intent(env.repo, env.state, _MISSION_BRANCH, snap[_MISSION_BRANCH], first)
    _git(env.repo, "update-ref", f"refs/heads/{_MISSION_BRANCH}", first)
    note_advance_intent(env.repo, env.state, _MISSION_BRANCH, first, second)  # killed before this write
    assert env.state.advance_intents[_MISSION_BRANCH] == [snap[_MISSION_BRANCH], first, second]

    report = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)

    mission = next(o for o in report.outcomes if o.branch == _MISSION_BRANCH)
    assert mission.kind is BranchOutcomeKind.RESTORED and mission.expected_sha == first
    assert _rev(env.repo, _MISSION_BRANCH) == snap[_MISSION_BRANCH]


def test_note_advance_intent_starts_a_new_chain_when_the_old_sha_breaks_it(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    _snapshot_and_begin(env)
    note_advance_intent(env.repo, env.state, _MISSION_BRANCH, "a" * 40, "b" * 40)
    note_advance_intent(env.repo, env.state, _MISSION_BRANCH, "c" * 40, "d" * 40)
    assert env.state.advance_intents == {_MISSION_BRANCH: ["c" * 40, "d" * 40]}


def test_note_advance_intent_ignores_lane_and_unknown_branches(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    _snapshot_and_begin(env)
    note_advance_intent(env.repo, env.state, env.lane_branches[0], "a" * 40, "b" * 40)
    note_advance_intent(env.repo, env.state, "unrelated", "a" * 40, "b" * 40)
    assert env.state.advance_intents == {}


def test_clear_advance_intents_drops_only_the_named_branches(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    _snapshot_and_begin(env)
    note_advance_intent(env.repo, env.state, _MISSION_BRANCH, "a" * 40, "b" * 40)
    note_advance_intent(env.repo, env.state, _TARGET, "c" * 40, "d" * 40)
    clear_advance_intents(env.state, [_MISSION_BRANCH, "not-there"])
    assert env.state.advance_intents == {_TARGET: ["c" * 40, "d" * 40]}


def test_begin_attempt_explains_a_live_tip_by_its_intent_and_carries_it_as_the_post(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    snap = _snapshot_and_begin(env)
    landed = _commit_tree(env.repo, snap[_MISSION_BRANCH], "squash")
    note_advance_intent(env.repo, env.state, _MISSION_BRANCH, snap[_MISSION_BRANCH], landed)
    _git(env.repo, "update-ref", f"refs/heads/{_MISSION_BRANCH}", landed)

    assert begin_attempt(env.repo, env.state) == []

    assert env.state.restore_targets[_MISSION_BRANCH] == snap[_MISSION_BRANCH]
    assert env.state.post_mutation_refs[_MISSION_BRANCH] == landed
    assert env.state.advance_intents == {}, "every intent is cleared once its proof is carried as a post tip"


def test_fr007_restore_target_survives_three_attempts(tmp_path: Path) -> None:
    """US4 AS1: the operator's commit M stays the restore target; a rollback restores to M, never the pre-M snapshot."""
    env = make_env(tmp_path)
    snap = _snapshot_and_begin(env)  # attempt 1
    _advance_run(env)
    assert rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET).fully_restored
    operator = _commit_on(env.repo, _MISSION_BRANCH, "operator-m")

    assert begin_attempt(env.repo, env.state) == []  # attempt 2
    assert env.state.restore_targets[_MISSION_BRANCH] == operator
    _commit_on(env.repo, _MISSION_BRANCH, "attempt-2-advance")
    record_post_mutation_tips(env.repo, env.state)  # killed after recording P

    assert begin_attempt(env.repo, env.state) == []  # attempt 3 starts at P
    assert env.state.restore_targets[_MISSION_BRANCH] == operator, "never reset to the pre-M snapshot"

    report = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)
    assert _kinds(report)[_MISSION_BRANCH] is BranchOutcomeKind.RESTORED
    assert _rev(env.repo, _MISSION_BRANCH) == operator != snap[_MISSION_BRANCH]


def test_release_keeps_a_not_restored_branch_and_lets_the_record_clear(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    snap = _snapshot_and_begin(env)
    _advance_run(env)
    foreign = _commit_on(env.repo, _MISSION_BRANCH, "teammate")
    release_branch(env.state, _MISSION_BRANCH, foreign, "keep teammate commit")

    report = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)

    mission = next(o for o in report.outcomes if o.branch == _MISSION_BRANCH)
    assert mission.kind is BranchOutcomeKind.KEPT_BY_OPERATOR
    assert _rev(env.repo, _MISSION_BRANCH) == foreign
    assert _kinds(report)[_TARGET] is BranchOutcomeKind.RESTORED and _rev(env.repo, _TARGET) == snap[_TARGET]
    assert report.fully_restored and report.advanced_branches == ()
    line = next(line for line in report.render().splitlines() if _MISSION_BRANCH in line)
    assert "kept" in line and "released by operator: keep teammate commit" in line
    assert f"at {foreign[:7]}" in line and "may contain this consolidation's unverified changes" in line
    assert env.state.released_refs == {} and env.state.release_reasons == {} and env.state.unsettled_refs == []


def test_release_is_ignored_for_a_restorable_branch(tmp_path: Path) -> None:
    """US3 AS3: a release never keeps a provable landing of this run."""
    env = make_env(tmp_path)
    snap = _snapshot_and_begin(env)
    posts = _advance_run(env)
    release_branch(env.state, _MISSION_BRANCH, posts[_MISSION_BRANCH], "keep it")

    report = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)

    assert _kinds(report)[_MISSION_BRANCH] is BranchOutcomeKind.RESTORED
    assert _rev(env.repo, _MISSION_BRANCH) == snap[_MISSION_BRANCH]


def test_release_binds_to_the_sha_recorded_at_release_time(tmp_path: Path) -> None:
    """US3 AS4: a released branch that moved after the release is NOT restored again."""
    env = make_env(tmp_path)
    _snapshot_and_begin(env)
    _advance_run(env)
    foreign = _commit_on(env.repo, _MISSION_BRANCH, "teammate")
    release_branch(env.state, _MISSION_BRANCH, foreign, "keep teammate commit")
    _commit_on(env.repo, _MISSION_BRANCH, "later")

    report = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)

    assert _kinds(report)[_MISSION_BRANCH] is BranchOutcomeKind.NOT_RESTORED
    assert not report.fully_restored


def test_rollback_settles_restored_branches_and_keeps_not_restored_ones_unsettled(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    _snapshot_and_begin(env)
    _advance_run(env)
    _commit_on(env.repo, _MISSION_BRANCH, "teammate")
    env.state.unsettled_refs = [UNSETTLED_ALL]  # a malformed record: everything unsettled

    report = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)

    assert not report.fully_restored
    assert env.state.unsettled_refs == [_MISSION_BRANCH]
    persisted = load_state(env.repo, "M1")
    assert persisted is not None and persisted.unsettled_refs == [_MISSION_BRANCH], "a partial restore is saved too"


def test_rollback_re_adds_a_not_restored_branch_to_the_unsettled_set(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    _snapshot_and_begin(env)
    _advance_run(env)
    _commit_on(env.repo, _MISSION_BRANCH, "teammate")
    env.state.unsettled_refs = []

    rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)

    assert env.state.unsettled_refs == [_MISSION_BRANCH]


def test_settle_branch_removes_one_branch_and_saves(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    _snapshot_and_begin(env)
    settle_branch(env.repo, env.state, _TARGET)
    assert env.state.unsettled_refs == [_MISSION_BRANCH]
    persisted = load_state(env.repo, "M1")
    assert persisted is not None and persisted.unsettled_refs == [_MISSION_BRANCH]
    env.state.unsettled_refs = [UNSETTLED_ALL]
    settle_branch(env.repo, env.state, _MISSION_BRANCH)
    assert env.state.unsettled_refs == [_TARGET]


def test_begin_attempt_clears_releases_and_intents(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    _snapshot_and_begin(env)
    note_advance_intent(env.repo, env.state, _MISSION_BRANCH, "a" * 40, "b" * 40)
    release_branch(env.state, _MISSION_BRANCH, "c" * 40, "why")
    assert begin_attempt(env.repo, env.state) == []
    assert env.state.advance_intents == {} and env.state.released_refs == {} and env.state.release_reasons == {}


def test_unexplained_branches_is_read_only(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    snap = _snapshot_and_begin(env)
    landed = _commit_on(env.repo, _TARGET, "squash-landed")  # killed before the recorder
    before, on_disk = _record(env), _disk(env)

    assert unexplained_branches(env.repo, env.state) == [(_TARGET, snap[_TARGET], landed)]

    assert _record(env) == before and _disk(env) == on_disk


def test_unexplained_branches_is_empty_for_explained_tips(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    _snapshot_and_begin(env)
    _advance_run(env)
    assert unexplained_branches(env.repo, env.state) == []


def test_own_move_from_the_restore_target_re_anchors(tmp_path: Path) -> None:
    """own_moves case 1: this process moved the branch from its restore target (e.g. the coord-strand heal)."""
    env = make_env(tmp_path)
    snap = _snapshot_and_begin(env)
    healed = _commit_on(env.repo, _MISSION_BRANCH, "heal")

    assert begin_attempt(env.repo, env.state, own_moves={_MISSION_BRANCH: OwnMove(snap[_MISSION_BRANCH], healed)}) == []

    assert env.state.restore_targets[_MISSION_BRANCH] == healed
    assert _MISSION_BRANCH not in env.state.post_mutation_refs


def test_own_move_from_the_effective_post_keeps_the_target_and_carries_the_post(tmp_path: Path) -> None:
    """own_moves case 2: the pre-move tip was unreconciled run content; it is never laundered into the target."""
    env = make_env(tmp_path)
    snap = _snapshot_and_begin(env)
    posts = _advance_run(env)
    healed = _commit_on(env.repo, _MISSION_BRANCH, "heal")

    assert begin_attempt(env.repo, env.state, own_moves={_MISSION_BRANCH: OwnMove(posts[_MISSION_BRANCH], healed)}) == []

    assert env.state.restore_targets[_MISSION_BRANCH] == snap[_MISSION_BRANCH]
    assert env.state.post_mutation_refs[_MISSION_BRANCH] == healed
    report = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)
    assert _kinds(report)[_MISSION_BRANCH] is BranchOutcomeKind.RESTORED
    assert _rev(env.repo, _MISSION_BRANCH) == snap[_MISSION_BRANCH]


def test_own_move_from_an_unexplained_tip_is_unexplained(tmp_path: Path) -> None:
    """own_moves case 3: the pre-move tip itself is unexplained on an unsettled branch; nothing changes."""
    env = make_env(tmp_path)
    _snapshot_and_begin(env)
    unrecorded = _commit_on(env.repo, _MISSION_BRANCH, "unrecorded")
    healed = _commit_on(env.repo, _MISSION_BRANCH, "heal")
    before = _record(env)

    assert begin_attempt(env.repo, env.state, own_moves={_MISSION_BRANCH: OwnMove(unrecorded, healed)}) == [_MISSION_BRANCH]

    assert _record(env) == before


def test_own_move_on_a_settled_branch_re_anchors(tmp_path: Path) -> None:
    """A settled branch's between-attempts move is the operator's (A2); this process's own move on top re-anchors."""
    env = make_env(tmp_path)
    _snapshot_and_begin(env)
    _advance_run(env)
    assert rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET).fully_restored
    operator = _commit_on(env.repo, _MISSION_BRANCH, "operator")
    healed = _commit_on(env.repo, _MISSION_BRANCH, "heal")

    assert begin_attempt(env.repo, env.state, own_moves={_MISSION_BRANCH: OwnMove(operator, healed)}) == []

    assert env.state.restore_targets[_MISSION_BRANCH] == healed


def test_own_move_the_branch_left_since_is_classified_normally(tmp_path: Path) -> None:
    """P1: an own move counts only while the branch is still where this process left it; a commit on top is judged normally."""
    env = make_env(tmp_path)
    snap = _snapshot_and_begin(env)
    healed = _commit_on(env.repo, _MISSION_BRANCH, "heal")
    _commit_on(env.repo, _MISSION_BRANCH, "foreign")
    before = _record(env)

    assert begin_attempt(env.repo, env.state, own_moves={_MISSION_BRANCH: OwnMove(snap[_MISSION_BRANCH], healed)}) == [_MISSION_BRANCH]

    assert _record(env) == before


def test_render_names_the_record_restore_targets_when_a_restore_left_the_snapshot() -> None:
    """F5: an ADR-A2 restore target is not the pre-consolidation snapshot; the header must not claim it is."""
    from specify_cli.consolidation.rollback import BranchOutcome

    off = BranchOutcome(_TARGET, BranchOutcomeKind.RESTORED, "a" * 40, "c" * 40, "c" * 40, restored_to_sha="b" * 40)
    to_snapshot = BranchOutcome(_MISSION_BRANCH, BranchOutcomeKind.RESTORED, "d" * 40, "e" * 40, "e" * 40, restored_to_sha="d" * 40)

    text = RollbackReport(outcomes=(off, to_snapshot)).render()
    assert text.splitlines()[0] == "Rollback, restored to the record's restore targets:"
    assert "pre-consolidation" not in text
    unchanged = RollbackReport(outcomes=(to_snapshot,)).render().splitlines()[0]
    assert unchanged == "Rollback to the pre-consolidation snapshot:", "unchanged when every restore went to the snapshot"


def test_kill_left_landing_without_an_abort_stays_unexplained_at_the_next_attempt(tmp_path: Path) -> None:
    """F6: pins the ``begin_attempt`` unsettled mark alone (no intervening ``--abort`` re-marks the target).

    Kill after the landing, before the phase recorder; the operator re-runs
    straight away. The next attempt must report the target unexplained (and
    change nothing), and a rollback must report it NOT_RESTORED.
    """
    env = make_env(tmp_path)
    _snapshot_and_begin(env)
    landed = _commit_on(env.repo, _TARGET, "squash-landed")  # killed before record_post_mutation_tips ran
    before = _disk(env)

    assert begin_attempt(env.repo, env.state) == [_TARGET]
    assert _disk(env) == before, "begin_attempt changes nothing when it returns an unexplained branch"
    report = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)

    assert _kinds(report)[_TARGET] is BranchOutcomeKind.NOT_RESTORED and not report.fully_restored
    assert _rev(env.repo, _TARGET) == landed
