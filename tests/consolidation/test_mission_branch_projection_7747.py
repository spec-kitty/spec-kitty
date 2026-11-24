"""#7747 operator ruling A (2026-11-24): a lane whose work a later lane rewrote is proven landed through the Mission branch.

A squash landing's merge base is the pre-Mission tip, so a lane whose lines a dependent lane later
rewrote conflicts with the landing in ``merge-tree``: its exact version is not on the target, although
approved work superseded it. Before the coordination teardown, ``consolidate`` still holds the Mission
branch the lanes were consolidated into. A lane whose tip that branch reaches, where the branch's
product tree is the landing's and every Mission-file difference is accounted for, landed:
:class:`MissionBranchProjection` hands that proof to the guard. Real repositories; the process probe is
injected.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.consolidation.lane_cleanup import (
    LANE_CLEANUP_FAILED,
    GuardedLaneRemover,
    LaneCleanupItem,
    LaneCleanupOutcome,
    LaneCleanupReport,
    LaneCleanupResult,
    LocalTargetAtPass,
    MissionBranchProjection,
    _remove_one,
    mission_branch_projection,
)
from specify_cli.coordination.coherence import NothingIsResidue
from specify_cli.lanes.lane_tip import clear_tip, is_absorbed_but_for_mission_bookkeeping, is_landed_through_mission_branch, read_tip, record_tip, tip_ref
from specify_cli.lanes.worktree_allocator import DestroyedLaneError, _refuse_on_tip
from specify_cli.workspace.process_probe import ProcessProbeResult

pytestmark = [pytest.mark.git_repo]

_SLUG = "demo-01ABCDEF"
_MD = f"kitty-specs/{_SLUG}"
_MISSION = f"kitty/mission-{_SLUG}"
_LANE_A = f"{_MISSION}-lane-a"
_LANE_B = f"{_MISSION}-lane-b"
_TARGET = "refs/heads/main"


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    assert result.returncode == 0, f"git {' '.join(args)}: {result.stderr}"
    return result.stdout.strip()


def _commit(cwd: Path, message: str, files: dict[str, str]) -> str:
    for rel, text in files.items():
        (cwd / rel).parent.mkdir(parents=True, exist_ok=True)
        (cwd / rel).write_text(text, encoding="utf-8")
        _git(cwd, "add", rel)
    _git(cwd, "commit", "-q", "-m", message)
    return _git(cwd, "rev-parse", "HEAD")


def _idle(paths: object) -> ProcessProbeResult:
    return ProcessProbeResult(available=True)


class Landed:
    """Lane B built on lane A and rewrote its line; the Mission branch holds both; ``main`` is the squash."""

    def __init__(self, tmp_path: Path) -> None:
        self.root = tmp_path / "repo"
        self.root.mkdir()
        _git(self.root, "init", "-q", "-b", "main")
        _git(self.root, "config", "user.email", "t@example.invalid")
        _git(self.root, "config", "user.name", "T")
        _git(self.root, "config", "commit.gpgsign", "false")
        _commit(self.root, "base", {".gitignore": ".worktrees/\n", "README.md": "base\n"})
        _git(self.root, "branch", _MISSION)
        _git(self.root, "branch", _LANE_A, _MISSION)
        self.lane_a = self.root / ".worktrees" / "lane-a"
        self.lane_b = self.root / ".worktrees" / "lane-b"
        _git(self.root, "worktree", "add", "-q", str(self.lane_a), _LANE_A)
        _commit(self.lane_a, "feat(WP01)", {"src/one.py": "x = 1\n", f"{_MD}/status.json": '{"v": 1}\n'})
        _git(self.root, "worktree", "add", "-q", "-b", _LANE_B, str(self.lane_b), _LANE_A)
        _commit(self.lane_b, "feat(WP02): rewrites WP01's line", {"src/one.py": "x = 10\n", "src/two.py": "y = 2\n"})
        mission = self.root / ".worktrees" / "mission"
        _git(self.root, "worktree", "add", "-q", str(mission), _MISSION)
        _git(mission, "merge", "-q", "--no-ff", "--no-edit", _LANE_A)
        _git(mission, "merge", "-q", "--no-ff", "--no-edit", _LANE_B)
        _commit(mission, "done transitions", {f"{_MD}/status.json": '{"v": 2}\n'})
        self.mission_tip = _git(mission, "rev-parse", "HEAD")
        _git(self.root, "checkout", "-q", self.mission_tip, "--", ".")
        _git(self.root, "commit", "-q", "-m", "squash merge of the Mission")
        self.passed = _git(self.root, "rev-parse", "HEAD")

    def tip(self, lane: Path) -> str:
        return _git(lane, "rev-parse", "HEAD")

    def approved(self) -> tuple[str, ...]:
        """The consolidated lanes' tips (both lanes are approved and merged into the Mission branch)."""
        return (self.tip(self.lane_a), self.tip(self.lane_b))

    def through_mission(self, lane: Path, landing: str | None = None) -> bool:
        proven: bool = is_landed_through_mission_branch(self.root, self.tip(lane), self.mission_tip, landing or self.passed, _SLUG, approved_tips=self.approved())
        return proven


@pytest.fixture
def landed(tmp_path: Path) -> Landed:
    return Landed(tmp_path)


def test_the_mission_branch_proves_every_lane_it_reaches(landed: Landed) -> None:
    # The control: the squash's pre-Mission merge base makes lane A's line a conflict for the content proof.
    assert not is_absorbed_but_for_mission_bookkeeping(landed.root, landed.tip(landed.lane_a), _TARGET, _SLUG)
    assert landed.through_mission(landed.lane_a)
    assert landed.through_mission(landed.lane_b)


def test_a_lane_commit_the_mission_branch_does_not_reach_is_not_proven(landed: Landed) -> None:
    _commit(landed.lane_a, "late work", {"src/late.py": "z = 3\n"})
    assert not landed.through_mission(landed.lane_a)


def test_a_landing_whose_product_differs_from_the_mission_branch_is_no_proof(landed: Landed) -> None:
    drifted = _commit(landed.root, "the target changes product code", {"src/one.py": "x = 99\n"})
    assert not landed.through_mission(landed.lane_a, drifted)


def test_the_targets_own_content_does_not_break_the_proof(landed: Landed) -> None:
    """The target keeps files the Mission branch never had (for example workspace contexts)."""
    landing = _commit(landed.root, "the target's own file", {".kittify/workspaces/demo-lane-a.json": "{}\n"})
    assert landed.through_mission(landed.lane_a, landing)


def test_a_mission_branch_with_no_common_history_is_no_proof(landed: Landed) -> None:
    orphan = _git(landed.root, "commit-tree", _git(landed.root, "rev-parse", "HEAD^{tree}"), "-m", "orphan")
    assert not landed.through_mission(landed.lane_a, orphan)


def test_a_mission_file_the_lane_wrote_that_did_not_land_is_no_proof(landed: Landed) -> None:
    """The projection covers product code; the lane's own Mission-file edits are still judged against the landing."""
    _commit(landed.lane_a, "the lane edits its prompt", {f"{_MD}/tasks/WP01.md": "lane edit\n"})
    mission = landed.root / ".worktrees" / "mission"
    _git(mission, "merge", "-q", "--no-ff", "--no-edit", _LANE_A)  # the Mission branch has it; the landing does not
    mission_tip = _git(mission, "rev-parse", "HEAD")
    assert not is_landed_through_mission_branch(landed.root, landed.tip(landed.lane_a), mission_tip, landed.passed, _SLUG, approved_tips=landed.approved())


def test_an_unknown_mission_tip_is_no_proof(landed: Landed) -> None:
    assert not is_landed_through_mission_branch(landed.root, landed.tip(landed.lane_a), "0" * 40, landed.passed, _SLUG, approved_tips=landed.approved())


def test_the_projection_names_the_proven_tips(landed: Landed) -> None:
    _commit(landed.lane_b, "late work", {"src/late.py": "z = 3\n"})
    landing = LocalTargetAtPass(target_ref="main", passed_sha=landed.passed)
    projection = mission_branch_projection(landed.root, _MISSION, landing, [landed.tip(landed.lane_a), landed.tip(landed.lane_b)], _SLUG)
    assert projection == MissionBranchProjection(mission_tip=landed.mission_tip, proven_tips=frozenset({landed.tip(landed.lane_a)}), anchor_sha=landed.passed)


def test_no_mission_branch_means_no_projection(landed: Landed) -> None:
    landing = LocalTargetAtPass(target_ref="main", passed_sha=landed.passed)
    assert mission_branch_projection(landed.root, "kitty/mission-gone", landing, [landed.tip(landed.lane_a)], _SLUG) is None


def test_no_pass_anchor_means_no_projection(landed: Landed) -> None:
    landing = LocalTargetAtPass(target_ref="main", passed_sha="")
    assert mission_branch_projection(landed.root, _MISSION, landing, [landed.tip(landed.lane_a)], _SLUG) is None


def _remove_lane_a(landed: Landed, landing: LocalTargetAtPass) -> LaneCleanupOutcome:
    remover = GuardedLaneRemover(landed.root, context=NothingIsResidue(), probe=_idle, mission_slug=_SLUG)
    item = LaneCleanupItem(lane_id="lane-a", worktree=landed.lane_a, branch=_LANE_A, expected_tip=landed.tip(landed.lane_a))
    return remover.remove(item, landing=landing).outcome


# --- R24 adversarial squad folds (2026-11-24) -----------------------------------------------------


def test_a_prompt_the_lane_wrote_and_the_mission_branch_moved_past_is_landed(tmp_path: Path) -> None:
    """A squash keeps only the Mission branch's last version; the lane's earlier one is in that branch's history."""
    landed = Landed(tmp_path)
    prompt = f"{_MD}/tasks/WP01.md"
    _commit(landed.lane_a, "the lane edits its prompt", {prompt: "lane edit\n"})
    mission = landed.root / ".worktrees" / "mission"
    _git(mission, "merge", "-q", "--no-ff", "--no-edit", _LANE_A)
    mission_tip = _commit(mission, "a rework note on the prompt", {prompt: "lane edit, then a rework note\n"})
    _git(landed.root, "checkout", "-q", mission_tip, "--", ".")
    _git(landed.root, "commit", "-q", "-m", "squash again")
    passed = _git(landed.root, "rev-parse", "HEAD")
    assert is_landed_through_mission_branch(landed.root, landed.tip(landed.lane_a), mission_tip, passed, _SLUG, approved_tips=landed.approved())


def test_a_projection_proven_against_another_anchor_is_not_used(landed: Landed) -> None:
    """The proof names the PASS anchor it was proven against; a landing with another anchor ignores it."""
    projection = MissionBranchProjection(mission_tip=landed.mission_tip, proven_tips=frozenset({landed.tip(landed.lane_a)}), anchor_sha="0" * 40)
    outcome = _remove_lane_a(landed, LocalTargetAtPass(target_ref="main", passed_sha=landed.passed, projection=projection))
    assert outcome is LaneCleanupOutcome.KEPT


def test_a_projection_stays_valid_when_the_pass_anchor_is_carried_over_an_own_commit(landed: Landed) -> None:
    """Consolidate advances the PASS anchor over its own post-landing commits (FR-035)."""
    projection = MissionBranchProjection(mission_tip=landed.mission_tip, proven_tips=frozenset({landed.tip(landed.lane_a)}), anchor_sha=landed.passed)
    carried = _commit(landed.root, "flatten coordination metadata", {f"{_MD}/meta.json": '{"flattened": true}\n'})
    outcome = _remove_lane_a(landed, LocalTargetAtPass(target_ref="main", passed_sha=carried, projection=projection))
    assert outcome is LaneCleanupOutcome.REMOVED


# --- Tier R B1, operator ruling 2026-11-24 (b): supersession must come from an approved lane ------


def test_a_probe_error_while_attributing_keeps_the_lane(landed: Landed, monkeypatch: pytest.MonkeyPatch) -> None:
    from kernel.git import GitCommandError
    from specify_cli.lanes import lane_tip

    def fail(*args: object, **kwargs: object) -> list[str]:
        raise GitCommandError(argv=("rev-list",), cwd=landed.root, returncode=128, stderr="boom")

    monkeypatch.setattr(lane_tip, "_git_lines", fail)
    assert not landed.through_mission(landed.lane_a)


# --- Operator ruling 2026-11-24: a lane removed on proof A keeps its lane-tip ref ---------------------


def _projection_of_both(landed: Landed, approved: tuple[str, ...] | None = None) -> LocalTargetAtPass:
    proven = frozenset(approved or landed.approved())
    projection = MissionBranchProjection(mission_tip=landed.mission_tip, proven_tips=proven, anchor_sha=landed.passed)
    return LocalTargetAtPass(target_ref="main", passed_sha=landed.passed, projection=projection)


def _remove(landed: Landed, lane: Path, branch: str, lane_id: str) -> LaneCleanupResult:
    remover = GuardedLaneRemover(landed.root, context=NothingIsResidue(), probe=_idle, mission_slug=_SLUG)
    item = LaneCleanupItem(lane_id=lane_id, worktree=lane, branch=branch, expected_tip=landed.tip(lane))
    return remover.remove(item, landing=_projection_of_both(landed))


def test_a_lane_removed_on_the_mission_branch_proof_keeps_its_lane_tip_ref(landed: Landed) -> None:
    """Lane A's line is not on the target (lane B rewrote it): its removed tip stays recoverable from the ref."""
    tip = landed.tip(landed.lane_a)
    clear_tip(landed.root, _LANE_A)  # recorder inactive: cleanup writes the ref itself
    result = _remove(landed, landed.lane_a, _LANE_A, "lane-a")
    assert result.outcome is LaneCleanupOutcome.REMOVED
    assert not landed.lane_a.exists()
    assert _git(landed.root, "branch", "--list", _LANE_A) == ""
    assert read_tip(landed.root, _LANE_A) == tip
    assert result.recoverable == tip_ref(_LANE_A)
    assert f"(recoverable: {tip_ref(_LANE_A)})" in LaneCleanupReport(results=(result,)).render_lines()[1]


def test_a_lane_removed_on_the_content_proof_still_clears_its_lane_tip_ref(landed: Landed) -> None:
    """Control: lane B's content is on the target, so nothing needs recovering; the content proof is tried first."""
    record_tip(landed.root, _LANE_B, landed.tip(landed.lane_b))
    result = _remove(landed, landed.lane_b, _LANE_B, "lane-b")
    assert result.outcome is LaneCleanupOutcome.REMOVED
    assert read_tip(landed.root, _LANE_B) is None
    assert result.recoverable is None
    assert "recoverable" not in LaneCleanupReport(results=(result,)).render_lines()[1]


def test_a_kept_lane_tip_ref_does_not_block_a_cleanup_rerun_and_recreates_the_lane(landed: Landed) -> None:
    """A re-run finds nothing left and leaves the ref; ``git branch <b> <ref>`` brings the lane back."""
    tip = landed.tip(landed.lane_a)
    approved = landed.approved()
    _remove(landed, landed.lane_a, _LANE_A, "lane-a")
    rerun = _remove_again(landed, approved)
    assert rerun.outcome is LaneCleanupOutcome.REMOVED
    assert read_tip(landed.root, _LANE_A) == tip
    _git(landed.root, "branch", _LANE_A, tip_ref(_LANE_A))
    assert _git(landed.root, "rev-parse", _LANE_A) == tip


def _remove_again(landed: Landed, approved: tuple[str, ...]) -> LaneCleanupResult:
    remover = GuardedLaneRemover(landed.root, context=NothingIsResidue(), probe=_idle, mission_slug=_SLUG)
    item = LaneCleanupItem(lane_id="lane-a", worktree=landed.lane_a, branch=_LANE_A, expected_tip=None)
    return remover.remove(item, landing=_projection_of_both(landed, approved))


def test_a_reopened_work_package_on_a_kept_ref_is_classified_destroyed_not_unknown(landed: Landed) -> None:
    """The kept tip is not on the target, so the allocator's guard names it (DESTROYED_LANE), never LANE_WORK_TIP_UNKNOWN."""
    tip = landed.tip(landed.lane_a)
    _remove(landed, landed.lane_a, _LANE_A, "lane-a")
    with pytest.raises(DestroyedLaneError) as refused:
        _refuse_on_tip(landed.root, lane_id="lane-a", wp_id="WP01", branch=_LANE_A, target_branch="main", tip=read_tip(landed.root, _LANE_A), context=None)
    assert refused.value.error_code == "DESTROYED_LANE"
    assert tip in str(refused.value)


# --- Tier R confirm 4 nit 1: the lane-tip ref is written before the branch is removed ------------------


def _item_a(landed: Landed) -> LaneCleanupItem:
    return LaneCleanupItem(lane_id="lane-a", worktree=landed.lane_a, branch=_LANE_A, expected_tip=landed.tip(landed.lane_a))


def test_a_lane_tip_write_failure_keeps_the_lane_and_its_branch(landed: Landed, monkeypatch: pytest.MonkeyPatch) -> None:
    """The ref is written first, so a failed write stops the removal: the branch is never gone without a named tip."""

    def fail(*args: object, **kwargs: object) -> str:
        raise OSError("ref store unwritable")

    monkeypatch.setattr("specify_cli.lanes.lane_tip.record_tip", fail)
    remover = GuardedLaneRemover(landed.root, context=NothingIsResidue(), probe=_idle, mission_slug=_SLUG)
    result = _remove_one(remover, _item_a(landed), _projection_of_both(landed))
    assert result.outcome is LaneCleanupOutcome.KEPT
    assert result.code == LANE_CLEANUP_FAILED
    assert _git(landed.root, "branch", "--list", _LANE_A) != ""
    assert landed.lane_a.exists()


def test_an_interruption_after_the_branch_removal_leaves_the_tip_named(landed: Landed) -> None:
    """Killed right after the guard removed worktree and branch (recorder inactive): the ref already names the tip."""
    tip = landed.tip(landed.lane_a)
    landing = _projection_of_both(landed)
    clear_tip(landed.root, _LANE_A)

    def interrupted() -> None:
        raise KeyboardInterrupt

    remover = GuardedLaneRemover(landed.root, context=NothingIsResidue(), probe=_idle, mission_slug=_SLUG, after_worktree_removed=interrupted)
    with pytest.raises(KeyboardInterrupt):
        remover.remove(_item_a(landed), landing=landing)
    assert _git(landed.root, "branch", "--list", _LANE_A) == ""
    assert read_tip(landed.root, _LANE_A) == tip


def test_a_lane_the_guard_keeps_has_its_earlier_lane_tip_ref_restored(landed: Landed) -> None:
    """Control: without the projection lane A is kept, and the ref written before the guard ran is put back."""
    record_tip(landed.root, _LANE_A, _git(landed.root, "rev-parse", f"{landed.tip(landed.lane_a)}^"))
    before = read_tip(landed.root, _LANE_A)
    assert _remove_lane_a(landed, LocalTargetAtPass(target_ref="main", passed_sha=landed.passed)) is LaneCleanupOutcome.KEPT
    assert landed.lane_a.exists()
    assert read_tip(landed.root, _LANE_A) == before
    clear_tip(landed.root, _LANE_A)
    assert _remove_lane_a(landed, LocalTargetAtPass(target_ref="main", passed_sha=landed.passed)) is LaneCleanupOutcome.KEPT
    assert read_tip(landed.root, _LANE_A) is None
