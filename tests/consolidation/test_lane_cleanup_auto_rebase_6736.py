"""Cleanup expects an auto-rebased lane at the run's own merge, and nothing else (#6736, #7382).

A stale lane is auto-rebased while consolidate folds it into the mission branch: a ``--no-ff``
merge of the mission branch into the lane worktree. The lane tip then sits one merge commit past
the tip the claim validated (``pre_mutation_refs``). Cleanup used to expect that older tip, so the
landed-removal guard refused every auto-rebased lane with ``WORKTREE_TIP_MOVED`` and the report
called the move "uncommitted changes". These tests pin:

* the move is recognised only in the exact shape the auto-rebase makes (first parent the
  validated tip, second parent the mission tip read just before the lane was consolidated);
* cleanup follows a recorded move only from the tip it starts from;
* an auto-rebased lane is removed through the guard, while any other move is still kept;
* the kept line names a moved tip as a moved tip, not as uncommitted changes;
* the record field round-trips and loads fail closed;
* on a coordination topology the lane also carries an older copy of the Mission's status log,
  which the absorption proof sets aside only when every lane event is already on the target.

Real repositories; the process probe is injected.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from specify_cli.consolidation.lane_cleanup import (
    GuardedLaneRemover,
    LaneCleanupItem,
    LaneCleanupOutcome,
    LocalTargetAtPass,
    _refusal_detail,
    _absorbed_but_for_status_log,
    cleanup_expected_tips,
    own_auto_rebase_move,
)
from specify_cli.consolidation.phase_advance import _record_own_auto_rebase
from specify_cli.consolidation.rollback import rebaseline_after_full_restore
from specify_cli.consolidation.state import ConsolidationState, load_state
from specify_cli.coordination.coherence import NothingIsResidue
from specify_cli.git.destructive_guard import BRANCH_HAS_UNIQUE_COMMITS, NOT_LANDED_ON_NAMED_REMOTE, WORKTREE_TIP_MOVED, DestructiveOpRefused
from specify_cli.lanes.lane_tip import is_absorbed
from specify_cli.orchestrator_api.consolidation import _follow_own_auto_rebase
from specify_cli.workspace.process_probe import ProcessProbeResult

pytestmark = [pytest.mark.git_repo]

_LANE = "kitty/mission-demo-01ABCDEF-lane-a"
_MISSION = "kitty/mission-demo-01ABCDEF"


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    assert result.returncode == 0, f"git {' '.join(args)}: {result.stderr}"
    return result.stdout.strip()


def _commit(cwd: Path, name: str, content: str) -> str:
    (cwd / name).write_text(content, encoding="utf-8")
    _git(cwd, "add", name)
    _git(cwd, "commit", "-q", "-m", f"add {name}")
    return _git(cwd, "rev-parse", "HEAD")


def _idle(paths: object) -> ProcessProbeResult:
    return ProcessProbeResult(available=True)


@pytest.fixture
def stale_lane(tmp_path: Path) -> tuple[Path, Path, str, str]:
    """``(root, lane worktree, validated lane tip, mission tip)``: the mission branch moved after the lane was cut."""
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.invalid")
    _git(root, "config", "user.name", "T")
    _git(root, "config", "commit.gpgsign", "false")
    (root / ".gitignore").write_text(".worktrees/\n", encoding="utf-8")
    _git(root, "add", ".gitignore")
    _commit(root, "base.py", "x = 1\n")
    _git(root, "branch", _MISSION)
    worktree = root / ".worktrees" / "demo-lane-a"
    _git(root, "worktree", "add", "-q", "-b", _LANE, str(worktree))
    tip = _commit(worktree, "lane.py", "y = 2\n")
    _git(root, "checkout", "-q", _MISSION)
    mission_tip = _commit(root, "other.py", "z = 3\n")  # another lane already landed on the mission branch
    _git(root, "checkout", "-q", "main")
    return root, worktree, tip, mission_tip


def _auto_rebase(worktree: Path) -> str:
    """The merge ``lanes.auto_rebase`` makes in the lane worktree."""
    _git(worktree, "merge", "-q", "--no-ff", "--no-edit", _MISSION)
    return _git(worktree, "rev-parse", "HEAD")


def _land(root: Path) -> LocalTargetAtPass:
    """Lane into mission, mission into target, as consolidate does; the PASS anchor is the target tip."""
    _git(root, "checkout", "-q", _MISSION)
    _git(root, "merge", "-q", "--no-ff", "-m", "consolidate lane-a", _LANE)
    _git(root, "checkout", "-q", "main")
    _git(root, "merge", "-q", "--no-ff", "-m", "land mission", _MISSION)
    return LocalTargetAtPass(target_ref="main", passed_sha=_git(root, "rev-parse", "main"))


def _item(worktree: Path, tip: str) -> LaneCleanupItem:
    return LaneCleanupItem(lane_id="lane-a", worktree=worktree, branch=_LANE, expected_tip=tip)


# --- own_auto_rebase_move -------------------------------------------------------------------


def test_the_auto_rebase_merge_is_recognised(stale_lane: tuple[Path, Path, str, str]) -> None:
    root, worktree, tip, mission_tip = stale_lane
    merged = _auto_rebase(worktree)
    assert own_auto_rebase_move(root, _LANE, before=tip, mission_before=mission_tip) == [tip, merged]


def test_an_unmoved_lane_has_no_move(stale_lane: tuple[Path, Path, str, str]) -> None:
    root, _worktree, tip, mission_tip = stale_lane
    assert own_auto_rebase_move(root, _LANE, before=tip, mission_before=mission_tip) is None


def test_a_plain_commit_on_the_lane_is_not_the_run_s_move(stale_lane: tuple[Path, Path, str, str]) -> None:
    root, worktree, tip, mission_tip = stale_lane
    _commit(worktree, "late.py", "w = 4\n")
    assert own_auto_rebase_move(root, _LANE, before=tip, mission_before=mission_tip) is None


def test_a_commit_after_the_auto_rebase_is_not_the_run_s_move(stale_lane: tuple[Path, Path, str, str]) -> None:
    root, worktree, tip, mission_tip = stale_lane
    _auto_rebase(worktree)
    _commit(worktree, "late.py", "w = 4\n")
    assert own_auto_rebase_move(root, _LANE, before=tip, mission_before=mission_tip) is None


def test_a_merge_of_another_commit_is_not_the_run_s_move(stale_lane: tuple[Path, Path, str, str]) -> None:
    root, worktree, tip, _mission_tip = stale_lane
    _git(root, "branch", "side", "main")
    _git(worktree, "merge", "-q", "--no-ff", "--no-edit", "side")
    assert own_auto_rebase_move(root, _LANE, before=tip, mission_before=_git(root, "rev-parse", _MISSION)) is None


@pytest.mark.parametrize("missing", ["before", "mission_before"])
def test_an_unread_tip_proves_nothing(stale_lane: tuple[Path, Path, str, str], missing: str) -> None:
    root, worktree, tip, mission_tip = stale_lane
    _auto_rebase(worktree)
    tips: dict[str, str | None] = {"before": tip, "mission_before": mission_tip, missing: None}
    assert own_auto_rebase_move(root, _LANE, before=tips["before"], mission_before=tips["mission_before"]) is None


def test_a_deleted_lane_branch_has_no_move(stale_lane: tuple[Path, Path, str, str]) -> None:
    root, worktree, tip, mission_tip = stale_lane
    _git(root, "worktree", "remove", str(worktree))
    _git(root, "branch", "-D", _LANE)
    assert own_auto_rebase_move(root, _LANE, before=tip, mission_before=mission_tip) is None


# --- cleanup_expected_tips ------------------------------------------------------------------


def test_cleanup_follows_a_move_from_the_snapshot_tip() -> None:
    assert cleanup_expected_tips({_LANE: "a", "main": "m"}, {_LANE: ["a", "b"]}) == {_LANE: "b", "main": "m"}


def test_cleanup_ignores_a_move_recorded_from_another_tip() -> None:
    # a move from an earlier attempt whose snapshot was since re-captured at the moved tip
    assert cleanup_expected_tips({_LANE: "b"}, {_LANE: ["a", "b"]}) == {_LANE: "b"}
    assert cleanup_expected_tips({_LANE: "c"}, {_LANE: ["a", "b"]}) == {_LANE: "c"}


def test_cleanup_ignores_a_move_for_a_branch_without_a_snapshot_tip() -> None:
    assert cleanup_expected_tips({}, {_LANE: ["a", "b"]}) == {}
    assert cleanup_expected_tips({_LANE: "a"}, None) == {_LANE: "a"}


# --- through the guard ----------------------------------------------------------------------


def test_an_auto_rebased_lane_is_removed_at_its_followed_tip(stale_lane: tuple[Path, Path, str, str]) -> None:
    root, worktree, tip, mission_tip = stale_lane
    merged = _auto_rebase(worktree)
    move = own_auto_rebase_move(root, _LANE, before=tip, mission_before=mission_tip)
    assert move == [tip, merged]
    landing = _land(root)
    expected = cleanup_expected_tips({_LANE: tip}, {_LANE: move})[_LANE]
    assert expected == merged
    result = GuardedLaneRemover(root, context=NothingIsResidue(), probe=_idle).remove(_item(worktree, expected), landing=landing)
    assert result.outcome is LaneCleanupOutcome.REMOVED, result
    assert not worktree.exists()
    assert _git(root, "branch", "--list", _LANE) == ""


def test_an_auto_rebased_lane_checked_against_the_pre_rebase_tip_is_kept_as_moved(stale_lane: tuple[Path, Path, str, str]) -> None:
    """The #6736 shape (pre-rebase tip expected) still fails closed, and #7382: it says "moved", not "uncommitted"."""
    root, worktree, tip, _mission_tip = stale_lane
    _auto_rebase(worktree)
    landing = _land(root)
    result = GuardedLaneRemover(root, context=NothingIsResidue(), probe=_idle).remove(_item(worktree, tip), landing=landing)
    assert result.outcome is LaneCleanupOutcome.KEPT
    assert result.code == WORKTREE_TIP_MOVED
    assert result.detail is not None
    assert "uncommitted" not in result.detail
    assert "moved after its tip was validated" in result.detail
    assert worktree.exists()


def test_a_commit_after_the_auto_rebase_still_keeps_the_lane(stale_lane: tuple[Path, Path, str, str]) -> None:
    root, worktree, tip, mission_tip = stale_lane
    merged = _auto_rebase(worktree)
    move = own_auto_rebase_move(root, _LANE, before=tip, mission_before=mission_tip)
    assert move == [tip, merged]
    landing = _land(root)
    _commit(worktree, "late.py", "w = 4\n")  # someone committed on the lane after the run's merge
    expected = cleanup_expected_tips({_LANE: tip}, {_LANE: move})[_LANE]
    result = GuardedLaneRemover(root, context=NothingIsResidue(), probe=_idle).remove(_item(worktree, expected), landing=landing)
    assert result.outcome is LaneCleanupOutcome.KEPT
    assert result.code == WORKTREE_TIP_MOVED
    assert worktree.exists()


def test_a_dirty_lane_is_still_reported_as_uncommitted_changes(stale_lane: tuple[Path, Path, str, str]) -> None:
    root, worktree, tip, _mission_tip = stale_lane
    landing = _land(root)
    (worktree / "lane.py").write_text("y = 99\n", encoding="utf-8")
    result = GuardedLaneRemover(root, context=NothingIsResidue(), probe=_idle).remove(_item(worktree, tip), landing=landing)
    assert result.outcome is LaneCleanupOutcome.KEPT
    assert result.detail == f"{worktree} has uncommitted changes."


# --- the record field -----------------------------------------------------------------------


def _state(**extra: object) -> dict[str, object]:
    return {"mission_id": "01ABCDEF0000000000000000AA", "mission_slug": "demo", "target_branch": "main", "wp_order": [], **extra}


def test_lane_rebase_moves_round_trip() -> None:
    state = ConsolidationState.from_dict(_state(lane_rebase_moves={_LANE: ["a", "b"]}))
    assert state.lane_rebase_moves == {_LANE: ["a", "b"]}
    assert ConsolidationState.from_dict(state.to_dict()).lane_rebase_moves == {_LANE: ["a", "b"]}


@pytest.mark.parametrize("malformed", [["a", "b"], {_LANE: ["a"]}, {_LANE: "a"}, {_LANE: ["a", 1]}, "x"])
def test_malformed_lane_rebase_moves_load_empty(malformed: object) -> None:
    assert ConsolidationState.from_dict(_state(lane_rebase_moves=malformed)).lane_rebase_moves == {}


def test_an_older_record_loads_without_moves() -> None:
    assert ConsolidationState.from_dict(_state()).lane_rebase_moves == {}


# --- the absorption proof sets aside the Mission's status log (coordination topology) -------

_SLUG = "demo-01ABCDEF"
_LOG = f"kitty-specs/{_SLUG}/status.events.jsonl"
_SNAPSHOT = f"kitty-specs/{_SLUG}/status.json"


def _write(cwd: Path, rel: str, content: str) -> None:
    path = cwd / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    _git(cwd, "add", rel)


@pytest.fixture
def coord_landed(tmp_path: Path) -> tuple[Path, Path, str]:
    """``(root, lane worktree, lane tip)``: the lane carries an older copy of the status log; main squash-landed and appended."""
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.invalid")
    _git(root, "config", "user.name", "T")
    _git(root, "config", "commit.gpgsign", "false")
    (root / ".gitignore").write_text(".worktrees/\n", encoding="utf-8")
    _git(root, "add", ".gitignore")
    _commit(root, "base.py", "x = 1\n")
    _git(root, "checkout", "-q", "-b", _MISSION)
    _write(root, _LOG, '{"event_id": "e1"}\n{"event_id": "e2"}\n')
    _write(root, _SNAPSHOT, '{"lanes": {"WP01": "in_progress"}}\n')
    _git(root, "commit", "-q", "-m", "status")
    _git(root, "checkout", "-q", "main")
    worktree = root / ".worktrees" / "demo-lane-a"
    _git(root, "worktree", "add", "-q", "-b", _LANE, str(worktree), "main")
    _commit(worktree, "lane.py", "y = 2\n")
    _git(worktree, "merge", "-q", "--no-ff", "--no-edit", _MISSION)  # the lane sync brings the status files in
    tip = _git(worktree, "rev-parse", "HEAD")
    _git(root, "checkout", "-q", _MISSION)
    _write(root, _LOG, '{"event_id": "e1"}\n{"event_id": "e2"}\n{"event_id": "e3"}\n')  # the mission log grew
    _git(root, "commit", "-q", "-m", "more status")
    _git(root, "merge", "-q", "--no-ff", "-m", "consolidate lane-a", _LANE)
    _git(root, "checkout", "-q", "main")
    _git(root, "merge", "-q", "--squash", _MISSION)
    _git(root, "commit", "-q", "-m", "squash merge of mission")
    _write(root, _LOG, '{"event_id": "e1"}\n{"event_id": "e2"}\n{"event_id": "e3"}\n{"event_id": "e4-done"}\n')
    _write(root, _SNAPSHOT, '{"lanes": {"WP01": "done"}}\n')
    _git(root, "commit", "-q", "-m", "record done transitions")
    return root, worktree, tip


def test_a_lane_carrying_an_older_status_log_is_absorbed_but_for_it(coord_landed: tuple[Path, Path, str]) -> None:
    root, _worktree, tip = coord_landed
    assert not is_absorbed(root, tip, "refs/heads/main", base=None)  # the plain proof cannot see it (the #6736 refusal)
    assert _absorbed_but_for_status_log(root, tip, "refs/heads/main", _SLUG)


def test_another_mission_s_status_log_is_not_set_aside(coord_landed: tuple[Path, Path, str]) -> None:
    root, _worktree, tip = coord_landed
    assert not _absorbed_but_for_status_log(root, tip, "refs/heads/main", "other-01ABCDEF")


def test_an_event_only_the_lane_holds_is_not_absorbed(coord_landed: tuple[Path, Path, str]) -> None:
    root, worktree, _tip = coord_landed
    _write(worktree, _LOG, '{"event_id": "e1"}\n{"event_id": "e2"}\n{"event_id": "lane-only"}\n')
    _git(worktree, "commit", "-q", "-m", "an event the target never got")
    assert not _absorbed_but_for_status_log(root, _git(worktree, "rev-parse", "HEAD"), "refs/heads/main", _SLUG)


def test_unlanded_work_beside_the_status_log_is_not_absorbed(coord_landed: tuple[Path, Path, str]) -> None:
    root, worktree, _tip = coord_landed
    _commit(worktree, "late.py", "z = 3\n")
    assert not _absorbed_but_for_status_log(root, _git(worktree, "rev-parse", "HEAD"), "refs/heads/main", _SLUG)


def test_a_lane_without_the_log_but_with_a_stale_snapshot_is_absorbed(coord_landed: tuple[Path, Path, str]) -> None:
    root, worktree, _tip = coord_landed
    _git(worktree, "rm", "-q", _LOG)
    _git(worktree, "commit", "-q", "-m", "drop the log copy")
    assert _absorbed_but_for_status_log(root, _git(worktree, "rev-parse", "HEAD"), "refs/heads/main", _SLUG)


def test_an_unknown_tip_is_not_absorbed(coord_landed: tuple[Path, Path, str]) -> None:
    root, _worktree, _tip = coord_landed
    assert not _absorbed_but_for_status_log(root, "0" * 40, "refs/heads/main", _SLUG)


def test_the_remover_given_the_mission_slug_removes_the_coordination_lane(coord_landed: tuple[Path, Path, str]) -> None:
    root, worktree, tip = coord_landed
    landing = LocalTargetAtPass(target_ref="main", passed_sha=_git(root, "rev-parse", "main"))
    remover = GuardedLaneRemover(root, context=NothingIsResidue(), probe=_idle, mission_slug=_SLUG)
    result = remover.remove(_item(worktree, tip), landing=landing)
    assert result.outcome is LaneCleanupOutcome.REMOVED, result
    assert not worktree.exists()
    assert _git(root, "branch", "--list", _LANE) == ""


def test_the_remover_without_a_mission_slug_keeps_the_plain_proof(coord_landed: tuple[Path, Path, str]) -> None:
    root, worktree, tip = coord_landed
    landing = LocalTargetAtPass(target_ref="main", passed_sha=_git(root, "rev-parse", "main"))
    result = GuardedLaneRemover(root, context=NothingIsResidue(), probe=_idle).remove(_item(worktree, tip), landing=landing)
    assert result.outcome is LaneCleanupOutcome.KEPT
    assert result.code == NOT_LANDED_ON_NAMED_REMOTE
    assert worktree.exists()


# --- the producers: consolidate's phase_advance and orchestrator-api ------------------------


def _run(root: Path, pre: dict[str, str]) -> Any:
    """A minimal stand-in for the executor's run state: the two attributes the recorder reads."""
    state = ConsolidationState.from_dict(_state(pre_mutation_refs=pre))
    return SimpleNamespace(main_repo=root, state=state)


def test_phase_advance_records_and_saves_the_run_s_own_auto_rebase(stale_lane: tuple[Path, Path, str, str]) -> None:
    root, worktree, tip, mission_tip = stale_lane
    merged = _auto_rebase(worktree)
    run = _run(root, {_LANE: tip})
    _record_own_auto_rebase(run, _LANE, before=tip, mission_before=mission_tip)
    assert run.state.lane_rebase_moves == {_LANE: [tip, merged]}
    saved = load_state(root, run.state.mission_id)
    assert saved is not None and saved.lane_rebase_moves == {_LANE: [tip, merged]}


def test_phase_advance_records_nothing_for_an_unmoved_lane(stale_lane: tuple[Path, Path, str, str]) -> None:
    root, _worktree, tip, mission_tip = stale_lane
    run = _run(root, {_LANE: tip})
    _record_own_auto_rebase(run, _LANE, before=tip, mission_before=mission_tip)
    assert run.state.lane_rebase_moves == {}


@pytest.mark.parametrize("snapshot", ["0" * 40, None])
def test_phase_advance_records_nothing_unless_the_lane_started_at_its_snapshot_tip(stale_lane: tuple[Path, Path, str, str], snapshot: str | None) -> None:
    root, worktree, tip, mission_tip = stale_lane
    _auto_rebase(worktree)
    run = _run(root, {_LANE: snapshot} if snapshot else {})
    _record_own_auto_rebase(run, _LANE, before=tip, mission_before=mission_tip)
    assert run.state.lane_rebase_moves == {}


def test_phase_advance_records_nothing_for_an_unread_lane_tip(stale_lane: tuple[Path, Path, str, str]) -> None:
    root, worktree, tip, mission_tip = stale_lane
    _auto_rebase(worktree)
    run = _run(root, {_LANE: tip})
    _record_own_auto_rebase(run, _LANE, before=None, mission_before=mission_tip)
    assert run.state.lane_rebase_moves == {}


def test_orchestrator_api_follows_only_the_run_s_own_auto_rebase(stale_lane: tuple[Path, Path, str, str]) -> None:
    root, worktree, tip, mission_tip = stale_lane
    merged = _auto_rebase(worktree)
    tips = {_LANE: tip}
    _follow_own_auto_rebase(root, tips, (_LANE, tip, mission_tip))
    assert tips == {_LANE: merged}


def test_orchestrator_api_keeps_the_validated_tip_for_any_other_move(stale_lane: tuple[Path, Path, str, str]) -> None:
    root, worktree, tip, mission_tip = stale_lane
    _commit(worktree, "late.py", "w = 4\n")
    tips = {_LANE: tip}
    _follow_own_auto_rebase(root, tips, (_LANE, tip, mission_tip))
    assert tips == {_LANE: tip}
    other = {_LANE: "0" * 40}  # the lane was not at its validated tip when it was consolidated
    _follow_own_auto_rebase(root, other, (_LANE, tip, mission_tip))
    assert other == {_LANE: "0" * 40}
    _follow_own_auto_rebase(root, tips, (_LANE, None, mission_tip))
    assert tips == {_LANE: tip}


def test_a_full_restore_rebaseline_drops_recorded_moves() -> None:
    state = ConsolidationState.from_dict(_state(pre_mutation_refs={_LANE: "a"}, lane_rebase_moves={_LANE: ["a", "b"]}))
    rebaseline_after_full_restore(state, ())
    assert state.lane_rebase_moves == {}


# --- the kept line's detail -----------------------------------------------------------------


def test_other_refusals_name_their_entries_not_uncommitted_changes(tmp_path: Path) -> None:
    refusal = DestructiveOpRefused(error_code=BRANCH_HAS_UNIQUE_COMMITS, current_branch=_LANE, dirty_entries=["abc123 (only on lane)"], remediation="keep it")
    assert _refusal_detail(refusal, tmp_path) == f"{tmp_path} was not removed: abc123 (only on lane)."
    bare = DestructiveOpRefused(error_code=BRANCH_HAS_UNIQUE_COMMITS, current_branch=_LANE, remediation="keep it")
    assert _refusal_detail(bare, tmp_path) == f"{tmp_path} was not removed."


def test_a_binary_conflict_beside_the_status_log_is_not_absorbed(coord_landed: tuple[Path, Path, str]) -> None:
    """git keeps the target's side of a binary conflict in the merged tree; the conflict list still refuses it."""
    root, worktree, _tip = coord_landed
    (root / "blob.bin").write_bytes(b"\x00target\x00")
    _git(root, "add", "blob.bin")
    _git(root, "commit", "-q", "-m", "target binary")
    (worktree / "blob.bin").write_bytes(b"\x00lane\x00")
    _git(worktree, "add", "blob.bin")
    _git(worktree, "commit", "-q", "-m", "lane binary")
    assert not _absorbed_but_for_status_log(root, _git(worktree, "rev-parse", "HEAD"), "refs/heads/main", _SLUG)
