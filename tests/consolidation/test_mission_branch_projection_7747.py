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
    GuardedLaneRemover,
    LaneCleanupItem,
    LaneCleanupOutcome,
    LocalTargetAtPass,
    MissionBranchProjection,
    mission_branch_projection,
)
from specify_cli.coordination.coherence import NothingIsResidue
from specify_cli.lanes.lane_tip import is_absorbed_but_for_mission_bookkeeping, is_landed_through_mission_branch
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

    def through_mission(self, lane: Path, landing: str | None = None) -> bool:
        proven: bool = is_landed_through_mission_branch(self.root, self.tip(lane), self.mission_tip, landing or self.passed, _SLUG)
        return proven


@pytest.fixture
def landed(tmp_path: Path) -> Landed:
    return Landed(tmp_path)


def test_a_lane_a_later_lane_rewrote_is_not_absorbed_by_the_content_proof(landed: Landed) -> None:
    """The control: the squash's pre-Mission merge base makes lane A's line a conflict."""
    assert not is_absorbed_but_for_mission_bookkeeping(landed.root, landed.tip(landed.lane_a), _TARGET, _SLUG)


def test_the_mission_branch_proves_every_lane_it_reaches(landed: Landed) -> None:
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
    assert not is_landed_through_mission_branch(landed.root, landed.tip(landed.lane_a), mission_tip, landed.passed, _SLUG)


def test_an_unknown_mission_tip_is_no_proof(landed: Landed) -> None:
    assert not is_landed_through_mission_branch(landed.root, landed.tip(landed.lane_a), "0" * 40, landed.passed, _SLUG)


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


def test_the_guard_removes_a_lane_the_projection_proves(landed: Landed) -> None:
    projection = MissionBranchProjection(mission_tip=landed.mission_tip, proven_tips=frozenset({landed.tip(landed.lane_a)}), anchor_sha=landed.passed)
    outcome = _remove_lane_a(landed, LocalTargetAtPass(target_ref="main", passed_sha=landed.passed, projection=projection))
    assert outcome is LaneCleanupOutcome.REMOVED
    assert not landed.lane_a.exists()
    assert _git(landed.root, "branch", "--list", _LANE_A) == ""


def test_without_the_projection_the_rewritten_lane_is_kept(landed: Landed) -> None:
    assert _remove_lane_a(landed, LocalTargetAtPass(target_ref="main", passed_sha=landed.passed)) is LaneCleanupOutcome.KEPT
    assert landed.lane_a.exists()


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
    assert is_landed_through_mission_branch(landed.root, landed.tip(landed.lane_a), mission_tip, passed, _SLUG)


def test_a_projection_proven_against_another_anchor_is_not_used(landed: Landed) -> None:
    """The proof names the PASS anchor it was proven against; a landing with another anchor ignores it."""
    projection = MissionBranchProjection(mission_tip=landed.mission_tip, proven_tips=frozenset({landed.tip(landed.lane_a)}), anchor_sha="0" * 40)
    outcome = _remove_lane_a(landed, LocalTargetAtPass(target_ref="main", passed_sha=landed.passed, projection=projection))
    assert outcome is LaneCleanupOutcome.KEPT
