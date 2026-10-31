"""End-to-end repro for #6771: a lane's merged dependency branch, through the real CLI.

A mission built on another in-flight branch picks that branch's newer head up by merging it
into the lane that depends on it (a true two-parent merge, so the reviewed commits are not
rewritten), and review approves the merged tree. Before this mission, ``consolidate
--strategy merge`` landed the mission, flagged every second-parent commit as
un-attributable, and rolled back — while ``--dry-run`` exited 0, so the refusal appeared
only on the real run and there was no supported way to restack a mission at all.

These tests drive ``python -m specify_cli consolidate`` (no mocking) and pin the four
verdicts the fix owes: the undeclared merge is refused by BOTH surfaces and moves nothing,
and the declared merge lands under BOTH strategies.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.terminus.conftest import (
    build_coord_mission,
    restamp_approvals_at_lane_tips,
    run_terminus,
    sha_reachable,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

DEP_BRANCH = "dep-branch"
DEP_PATH = "src/dep/mod0.py"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()


def _restack_lane_b_onto_a_dependency(mission: object, tmp_path: Path, *, reapprove: bool = True) -> str:
    """Cut an external branch from the repo root, merge it --no-ff into WP02's lane, re-approve.

    ``src/dep/*`` is content no work package owns, and the branch is not an ancestor of the
    target's pre-run tip — exactly the shape #6771 reports.
    """
    repo: Path = mission.repo  # type: ignore[attr-defined]
    root = _git(repo, "rev-list", "--max-parents=0", "HEAD")
    _git(repo, "branch", DEP_BRANCH, root)
    dep_wt = tmp_path / "dep-wt"
    _git(repo, "worktree", "add", dep_wt.as_posix(), DEP_BRANCH)
    for idx in range(2):
        target = dep_wt / "src" / "dep" / f"mod{idx}.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"DEP = {idx}\n", encoding="utf-8")
        _git(dep_wt, "add", "-A")
        _git(dep_wt, "commit", "-qm", f"feat(dep): mod{idx}")
    _git(repo, "worktree", "remove", dep_wt.as_posix())

    lane_wt = tmp_path / "lane-wt"
    _git(repo, "worktree", "add", lane_wt.as_posix(), mission.lane_branch("WP02"))  # type: ignore[attr-defined]
    _git(lane_wt, "merge", "-q", "--no-ff", "--no-edit", DEP_BRANCH)
    _git(repo, "worktree", "remove", lane_wt.as_posix())
    if reapprove:
        restamp_approvals_at_lane_tips(mission)  # type: ignore[arg-type]
    return _git(repo, "rev-parse", DEP_BRANCH)


def _consolidate(mission: object, *extra: str) -> subprocess.CompletedProcess[str]:
    return run_terminus(
        mission,  # type: ignore[arg-type]
        ["consolidate", "--mission", mission.slug, "--yes", *extra],  # type: ignore[attr-defined]
    )


def _blob_present(repo: Path, ref: str, path: str) -> bool:
    probe = subprocess.run(["git", "cat-file", "-e", f"{ref}:{path}"], cwd=repo, capture_output=True)
    return probe.returncode == 0


def test_undeclared_dependency_merge_is_refused_by_dry_run_and_real_run(tmp_path: Path) -> None:
    """The reported defect: the two surfaces disagreed. Now they agree, and nothing moves."""
    mission = build_coord_mission(tmp_path, wps=("WP01", "WP02"), mid8="01M6771K")
    dep_tip = _restack_lane_b_onto_a_dependency(mission, tmp_path)
    pre_target = mission.rev(mission.target_branch)

    dry = _consolidate(mission, "--strategy", "merge", "--dry-run")
    assert dry.returncode != 0, f"the forecast must predict the refusal, exited 0:\n{dry.stdout[-2000:]}"
    assert dep_tip[:10] in dry.stdout
    assert mission.rev(mission.target_branch) == pre_target, "a dry run must move no ref"

    real = _consolidate(mission, "--strategy", "merge")
    assert real.returncode != 0, f"an undeclared dependency merge must stay refused (fail-closed):\n{real.stdout[-2000:]}"
    assert "un-attributable" in real.stdout
    assert dep_tip[:10] in real.stdout
    assert mission.rev(mission.target_branch) == pre_target, "the refused landing must be rolled back"
    assert "--dependency-ref" in real.stdout, "the refusal must name the supported recovery"


def test_declared_dependency_merge_lands_under_merge_strategy(tmp_path: Path) -> None:
    """The restack path the issue asked for: declare the ref, and the reviewed tree lands."""
    mission = build_coord_mission(tmp_path, wps=("WP01", "WP02"), mid8="01M6771M")
    _restack_lane_b_onto_a_dependency(mission, tmp_path)
    lane_commit = mission.approved_shas_from_lane_tips(["WP02"])["WP02"][0]

    dry = _consolidate(mission, "--strategy", "merge", "--dry-run", "--dependency-ref", DEP_BRANCH)
    assert dry.returncode == 0, dry.stdout[-2000:]

    real = _consolidate(mission, "--strategy", "merge", "--dependency-ref", DEP_BRANCH)
    assert real.returncode == 0, real.stdout[-3000:]
    target = mission.target_branch
    assert _blob_present(mission.repo, target, DEP_PATH), "the dependency content the lanes were reviewed on must land"
    assert _blob_present(mission.repo, target, "src/pkg/wp02.py"), "the work package's own content must land too"
    assert sha_reachable(mission.repo, lane_commit, target)


def test_declared_dependency_merge_lands_under_squash_strategy(tmp_path: Path) -> None:
    """The same declaration covers the squash blob axis, so the class is closed twice."""
    mission = build_coord_mission(tmp_path, wps=("WP01", "WP02"), mid8="01M6771N")
    _restack_lane_b_onto_a_dependency(mission, tmp_path)

    real = _consolidate(mission, "--strategy", "squash", "--dependency-ref", DEP_BRANCH)

    assert real.returncode == 0, real.stdout[-3000:]
    assert _blob_present(mission.repo, mission.target_branch, DEP_PATH)
    assert _blob_present(mission.repo, mission.target_branch, "src/pkg/wp02.py")


def test_declared_dependency_merge_after_approval_is_still_refused_by_the_approved_bound(tmp_path: Path) -> None:
    """The declaration exempts closed-world authorship only: a merge made AFTER review approved the lane stays refused."""
    mission = build_coord_mission(tmp_path, wps=("WP01", "WP02"), mid8="01M6771Q")
    _restack_lane_b_onto_a_dependency(mission, tmp_path, reapprove=False)
    pre_target = mission.rev(mission.target_branch)

    real = _consolidate(mission, "--strategy", "merge", "--dependency-ref", DEP_BRANCH)

    assert real.returncode != 0, real.stdout[-2000:]
    assert "LANE_MOVED_AFTER_APPROVAL" in real.stdout
    assert mission.rev(mission.target_branch) == pre_target


def test_a_declaration_naming_mission_work_is_refused_end_to_end(tmp_path: Path) -> None:
    """No bypass: declaring a lane branch (mission-authored work) refuses with its stable code before any ref moves."""
    mission = build_coord_mission(tmp_path, wps=("WP01", "WP02"), mid8="01M6771P")
    _restack_lane_b_onto_a_dependency(mission, tmp_path)
    pre_target = mission.rev(mission.target_branch)

    real = _consolidate(mission, "--strategy", "merge", "--dependency-ref", mission.lane_branch("WP02"))

    assert real.returncode != 0
    assert "Error code: DEPENDENCY_REF_COVERS_MISSION_WORK." in real.stdout
    assert mission.rev(mission.target_branch) == pre_target
