"""#7755 / #7754: the stale refusal names the sibling lane behind the overlap and the in-run auto-rebase halt.

Real git repositories: ``lane-a`` and ``lane-b`` both edit ``shared.txt`` from one
base; ``lane-a`` is merged into the Mission branch (as ``consolidate`` does first),
so ``lane-b`` is stale against a change only ``lane-a``'s branch keeps once a
rollback restores the Mission branch.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from kernel.git import GitPath
from kernel.git.runner import GitCommandError
from specify_cli.lanes import stale_check
from specify_cli.lanes.models import ExecutionLane
from specify_cli.lanes.stale_check import (
    SiblingLane,
    StaleCheckResult,
    _stale_remediation,
    check_lane_staleness,
    find_sibling_lanes,
    refine_stale_result,
)

pytestmark = pytest.mark.git_repo

MISSION = "kitty/mission-demo"
LANE_A = "kitty/mission-demo-lane-a"
LANE_B = "kitty/mission-demo-lane-b"
LANE_C = "kitty/mission-demo-lane-c"
SIBLING_A = SiblingLane("lane-a", LANE_A)
SIBLING_C = SiblingLane("lane-c", LANE_C)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True)


def _commit_on(repo: Path, branch: str, path: str, text: str) -> None:
    _git(repo, "switch", "-q", branch)
    (repo / path).write_text(text, encoding="utf-8")
    _git(repo, "add", path)
    _git(repo, "commit", "-qm", f"{branch}: {path}")


def _lane(lane_id: str = "lane-b", wp_ids: tuple[str, ...] = ("WP02",)) -> ExecutionLane:
    return ExecutionLane(
        lane_id=lane_id,
        wp_ids=wp_ids,
        write_scope=("**",),
        predicted_surfaces=(),
        depends_on_lanes=(),
        parallel_group=0,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """lane-a merged into the Mission branch; lane-b and lane-c unmerged; lane-c edits another file."""
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    for key, value in (("user.email", "t@example.com"), ("user.name", "t"), ("commit.gpgsign", "false")):
        _git(root, "config", key, value)
    (root / "shared.txt").write_text("one\ntwo\nthree\nfour\n", encoding="utf-8")
    (root / "other.txt").write_text("x\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "seed")
    for branch in (MISSION, LANE_A, LANE_B, LANE_C):
        _git(root, "branch", branch)
    _commit_on(root, LANE_A, "shared.txt", "ONE\ntwo\nthree\nfour\n")
    _commit_on(root, LANE_B, "shared.txt", "one\ntwo\nthree\nFOUR\n")
    _commit_on(root, LANE_C, "other.txt", "y\n")
    _git(root, "switch", "-q", MISSION)
    _git(root, "merge", "-q", "--no-ff", "--no-edit", LANE_A)
    _git(root, "switch", "-q", "main")
    return root


def test_the_merged_sibling_that_touches_a_stale_file_is_found(repo: Path) -> None:
    stale = check_lane_staleness(_lane(), LANE_B, MISSION, repo)
    assert stale.is_stale and stale.stale_files == ["shared.txt"]

    assert find_sibling_lanes(repo, LANE_B, MISSION, [SIBLING_A, SIBLING_C], stale.stale_files) == (SIBLING_A,)


def test_an_unmerged_sibling_is_not_named(repo: Path) -> None:
    """lane-c is not on the Mission branch, so it cannot be what made lane-b stale, even when it overlaps."""
    _commit_on(repo, LANE_C, "shared.txt", "one\nTWO\nthree\nfour\n")

    assert find_sibling_lanes(repo, LANE_B, MISSION, [SIBLING_C], ["shared.txt"]) == ()


def test_a_merged_sibling_already_in_the_lane_is_not_named(repo: Path) -> None:
    """A sibling the lane already holds adds nothing the lane lacks."""
    _git(repo, "switch", "-q", LANE_B)
    _git(repo, "merge", "-q", "--no-edit", "-X", "ours", LANE_A)
    _git(repo, "switch", "-q", "main")

    assert find_sibling_lanes(repo, LANE_B, MISSION, [SIBLING_A], ["shared.txt"]) == ()


def test_the_lane_itself_and_the_mission_branch_are_never_siblings(repo: Path) -> None:
    candidates = [SiblingLane("lane-b", LANE_B), SiblingLane("mission", MISSION)]
    assert find_sibling_lanes(repo, LANE_B, MISSION, candidates, ["shared.txt"]) == ()


def test_a_failed_probe_drops_only_that_candidate(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    real: Callable[[Path, str], tuple[GitPath, ...]] = stale_check.log_paths

    def _flaky(cwd: Path, rev_range: str) -> tuple[GitPath, ...]:
        if LANE_C in rev_range:
            raise GitCommandError(argv=("git", "log"), cwd=cwd, returncode=128, stderr="boom")
        return real(cwd, rev_range)

    _git(repo, "switch", "-q", MISSION)
    _git(repo, "merge", "-q", "--no-ff", "--no-edit", LANE_C)
    _git(repo, "switch", "-q", "main")
    monkeypatch.setattr(stale_check, "log_paths", _flaky)

    assert find_sibling_lanes(repo, LANE_B, MISSION, [SIBLING_C, SIBLING_A], ["shared.txt", "other.txt"]) == (SIBLING_A,)


def test_refine_leaves_a_fresh_result_alone() -> None:
    fresh = StaleCheckResult(is_stale=False)
    assert refine_stale_result(fresh, _lane(), LANE_B, MISSION, auto_rebase_halt="x", sibling_lanes=[SIBLING_A]) is fresh


def test_refined_remedy_leads_with_the_halt_and_names_the_sibling_branch(repo: Path) -> None:
    stale = check_lane_staleness(_lane(), LANE_B, MISSION, repo, mission_slug="demo")

    refined = refine_stale_result(
        stale, _lane(), LANE_B, MISSION, mission_slug="demo", auto_rebase_halt="no classifier rule matched shared.txt", sibling_lanes=[SIBLING_A]
    )

    text = refined.remediation or ""
    assert refined.auto_rebase_halt == "no classifier rule matched shared.txt"
    assert refined.sibling_lanes == (SIBLING_A,)
    assert text.startswith(f"The in-run auto-rebase of lane lane-b onto {MISSION} stopped: no classifier rule matched shared.txt. ")
    assert f"lane lane-a (branch {LANE_A})" in text
    assert f"incorporate changes from {MISSION}" not in text
    assert "git merge" not in text and "cd .worktrees" not in text
    reopen = "spec-kitty agent tasks move-task WP02 --to planned --review-feedback-file <file> --mission demo"
    # WP07 (ruling DM-01M88RZDBP57ZTYJHC5NP0ZH4R): the sibling is incorporated at its approval stamp, never ``git merge``d.
    route = [
        "spec-kitty agent action implement WP02 --mission demo --agent <agent>",
        "spec-kitty agent action implement WP02 --mission demo --incorporate lane-a --agent <agent>",
        "If it stops on a conflict, resolve it in the lane checkout that command names and commit the merge there.",
        "spec-kitty agent tasks move-task WP02 --to for_review --mission demo",
        "An independent reviewer reviews WP02 and approves it again; the new approval must reach the incorporation merge.",
        "spec-kitty consolidate --mission demo",
    ]
    assert text.index(reopen) < text.index("\n")
    assert text.splitlines()[1:] == [f"  {line}" for line in route]


def test_remedy_names_every_sibling_and_reopens_every_wp_of_a_multi_wp_lane() -> None:
    text = _stale_remediation(_lane(wp_ids=("WP02", "WP03")), LANE_B, MISSION, mission_slug="demo", sibling_lanes=(SIBLING_A, SIBLING_C))

    assert "git merge" not in text
    assert "those branches" in text
    assert "move-task WP02 --to planned" in text and "move-task WP03 --to planned" in text
    assert "reopen each of them first" in text
    assert "in-run auto-rebase" not in text
    # WP07: one --incorporate line per sibling, in sibling order, through one concrete WP (never ``<WP>``).
    assert "<WP>" not in text
    incorporate = [line.strip() for line in text.splitlines()[1:] if "--incorporate" in line]
    assert incorporate == [
        "spec-kitty agent action implement WP02 --mission demo --incorporate lane-a --agent <agent>",
        "spec-kitty agent action implement WP02 --mission demo --incorporate lane-c --agent <agent>",
    ]
    commands = [line.strip() for line in text.splitlines()[1:] if line.strip().startswith("spec-kitty ")]
    assert commands == [
        "spec-kitty agent action implement WP02 --mission demo --agent <agent>",
        *incorporate,
        "spec-kitty agent tasks move-task WP02 --to for_review --mission demo",
        "spec-kitty agent action implement WP03 --mission demo --agent <agent>",
        "spec-kitty agent tasks move-task WP03 --to for_review --mission demo",
        "spec-kitty consolidate --mission demo",
    ]
    assert "An independent reviewer reviews WP02 and WP03 and approves each of them again" in text


def test_remedy_without_a_sibling_keeps_the_auto_rebase_refresh_after_the_reopen_step() -> None:
    text = _stale_remediation(_lane(), LANE_B, MISSION)

    assert f"Lane lane-b must incorporate changes from {MISSION}" in text
    assert "refreshes the lane through auto-rebase" in text
    assert "git merge" not in text
    assert "--mission <mission>" in text


def test_planning_lane_remedy_is_unchanged_by_siblings_and_halt() -> None:
    planning = _lane("lane-planning")
    plain = _stale_remediation(planning, "main", MISSION)
    assert _stale_remediation(planning, "main", MISSION, auto_rebase_halt="x", sibling_lanes=(SIBLING_A,)) == plain
    assert "repository-root checkout" in plain
