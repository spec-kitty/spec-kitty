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
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import pytest

from specify_cli.consolidation.rollback import (
    BranchOutcomeKind,
    RollbackReport,
    _restore_target,
    begin_attempt,
    capture_pre_mutation_snapshot,
    missing_snapshot_branches,
    record_post_mutation_tips,
    rollback_to_snapshot,
    snapshot_branches,
)
from specify_cli.consolidation.state import ConsolidationState, load_state
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
    ("snapshot", "previous_post", "attempt_start", "expected"),
    [
        ("S", None, "S", "S"),  # attempt starts at the snapshot
        ("S", "P", "P", "S"),  # attempt starts at consolidation's own previous post tip
        ("S", "P", "X", "X"),  # somebody else moved it: keep
        ("S", None, "X", "X"),
    ],
)
def test_restore_target_truth_table(snapshot: str, previous_post: str | None, attempt_start: str, expected: str) -> None:
    assert _restore_target(snapshot, previous_post, attempt_start) == expected


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
