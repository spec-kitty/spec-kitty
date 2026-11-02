"""Behavioural contract for the lane-adoption seam (#6898).

``worktree_allocator.adopt_lane_ancestry`` is the one public owner of "make a
reused lane worktree current": it merges the recorded finalize-tasks planning
commit, then the approved dependency lane tips, under an explicit clean-worktree
policy. ``implement_support.reenter_lane_self_heal`` delegates to it -- a code
lane with ``allow-dirty`` (the agent's work-in-progress is legitimate), a
planning lane with ``refuse-dirty`` (the shared root must be clean).

Real git, no plumbing mocks: the seam's behaviour IS git ancestry, so a mocked
repo would prove nothing. The fixture reuses the ancestry-gate builder so both
suites describe the same mission shape.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.lanes.branch_naming import code_lane_branch_name
from specify_cli.lanes.implement_support import reenter_lane_self_heal
from specify_cli.lanes.persistence import read_lanes_json
from specify_cli.lanes.worktree_allocator import (
    DirtyWorktreeError,
    adopt_lane_ancestry,
)
from specify_cli.status.models import Lane
from tests.specify_cli.cli.commands.agent.test_claim_ancestry_gate import (
    _MISSION_ID,
    _MISSION_SLUG,
    _WP_DEP,
    _WP_SELF,
    _create_lane_a_branch,
    _feature_dir,
    _git,
    _init_repo,
    _seed_wp_lane,
)

pytestmark = [pytest.mark.fast, pytest.mark.git_repo]


@pytest.fixture(autouse=True)
def _enable_saas_sync_feature_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")


def _write_two_lane_manifest(repo: Path, planning_commit_sha: str) -> None:
    """Legacy-topology mission with a dependent lane-b and a recorded pin.

    Same shape as ``test_claim_ancestry_gate._write_meta_and_lanes`` (lane-a is
    the approved dependency, lane-b depends on it) plus the recorded
    ``planning_commit_sha`` this seam exists to adopt.
    """
    feature_dir = _feature_dir(repo)
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": _MISSION_ID,
                "mission_slug": _MISSION_SLUG,
                "mid8": _MISSION_ID[:8].lower(),
                "mission_type": "software-dev",
                "target_branch": "main",
                "created_at": "2026-08-26T00:00:00+00:00",
                "friendly_name": "lane adoption seam test",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    lanes_payload = {
        "version": 1,
        "mission_slug": _MISSION_SLUG,
        "mission_id": _MISSION_ID,
        "mission_branch": f"kitty/mission-{_MISSION_SLUG}",
        "target_branch": "main",
        "lanes": [
            {
                "lane_id": "lane-a",
                "wp_ids": [_WP_DEP],
                "write_scope": ["src/**"],
                "predicted_surfaces": ["core"],
                "depends_on_lanes": [],
                "parallel_group": 0,
            },
            {
                "lane_id": "lane-b",
                "wp_ids": [_WP_SELF],
                "write_scope": ["src/**"],
                "predicted_surfaces": ["core"],
                "depends_on_lanes": ["lane-a"],
                "parallel_group": 1,
            },
        ],
        "computed_at": "2026-08-26T00:00:00+00:00",
        "computed_from": "test",
        "planning_artifact_wps": [],
        "planning_commit_sha": planning_commit_sha,
    }
    (feature_dir / "lanes.json").write_text(json.dumps(lanes_payload, indent=2), encoding="utf-8")
    _git(repo, "add", "kitty-specs")
    _git(repo, "commit", "-qm", "chore: planning artifacts")


def _is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    return (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", ancestor, descendant],
            cwd=str(repo),
            capture_output=True,
        ).returncode
        == 0
    )


def _head_parents(repo: Path) -> list[str]:
    """``[HEAD, parent-1, parent-2, ...]`` for the tip of *repo*'s checkout."""
    return _git(repo, "rev-list", "--parents", "-n", "1", "HEAD").split()


def _seamed_repo(tmp_path: Path) -> tuple[Path, str, str]:
    """A mission whose plan commit is already recorded but not yet merged.

    Returns ``(repo, base_commit, planning_commit_sha)``. The lane worktree is
    cut from ``base_commit`` -- BEFORE the planning commit -- so adopting the
    recorded pin is a real merge, exactly the stale-lane shape the self-heal
    exists for. Because the pin IS an ancestor of the target-branch tip,
    ``_merge_recorded_planning_commit`` accepts it (``ADVANCED``): a seam that
    captured a lane HEAD as the target tip instead would classify it
    ``ORPHANED`` and refuse, which is what test 3's merge proves cannot happen.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    base = _git(repo, "rev-parse", "HEAD")
    (repo / "plan.md").write_text("planning artifacts\n", encoding="utf-8")
    _git(repo, "add", "plan.md")
    _git(repo, "commit", "-qm", "finalize-tasks: planning commit")
    planning_sha = _git(repo, "rev-parse", "HEAD")
    _write_two_lane_manifest(repo, planning_sha)
    return repo, base, planning_sha


def _lane_b_worktree(repo: Path, base: str) -> Path:
    """Cut lane-b's worktree from *base*, WITHOUT the planning commit."""
    branch = code_lane_branch_name(_MISSION_SLUG, "lane-b")
    worktree = repo / ".worktrees" / f"{_MISSION_SLUG}-lane-b"
    worktree.parent.mkdir(parents=True, exist_ok=True)
    _git(repo, "worktree", "add", "-q", "-b", branch, str(worktree), base)
    return worktree


def _lane(repo: Path):  # noqa: ANN202 - test helper
    manifest = read_lanes_json(_feature_dir(repo))
    lane = manifest.lane_for_wp(_WP_SELF)
    assert lane is not None
    return manifest, lane


def test_refuse_dirty_policy_refuses_before_any_merge(tmp_path: Path) -> None:
    """``refuse-dirty``: the refusal lands first, so nothing is merged."""
    repo, base, planning_sha = _seamed_repo(tmp_path)
    worktree = _lane_b_worktree(repo, base)
    manifest, lane = _lane(repo)
    (worktree / "wip.txt").write_text("uncommitted work\n", encoding="utf-8")
    head_before = _git(worktree, "rev-parse", "HEAD")

    with pytest.raises(DirtyWorktreeError) as refused:
        adopt_lane_ancestry(
            repo,
            worktree,
            _MISSION_SLUG,
            lane,
            manifest,
            clean_worktree_policy="refuse-dirty",
        )

    assert lane.lane_id in str(refused.value)
    assert _git(worktree, "rev-parse", "HEAD") == head_before
    assert not _is_ancestor(worktree, planning_sha, "HEAD")
    assert (worktree / "wip.txt").read_text(encoding="utf-8") == "uncommitted work\n"


def test_allow_dirty_policy_merges_the_recorded_planning_commit(tmp_path: Path) -> None:
    """``allow-dirty``: the pin is merged and the agent's WIP is untouched.

    The pin is an ancestor of the target-branch tip but NOT of this worktree,
    so a seam that captured the lane HEAD as ``target_tip`` would classify it
    ``ORPHANED`` and refuse; the successful merge here is the behavioural proof
    that ``target_tip=None`` captures ``lanes_manifest.target_branch``.
    """
    repo, base, planning_sha = _seamed_repo(tmp_path)
    worktree = _lane_b_worktree(repo, base)
    manifest, lane = _lane(repo)
    (worktree / "wip.txt").write_text("uncommitted work\n", encoding="utf-8")
    assert not _is_ancestor(worktree, planning_sha, "HEAD")

    adopt_lane_ancestry(
        repo,
        worktree,
        _MISSION_SLUG,
        lane,
        manifest,
        clean_worktree_policy="allow-dirty",
    )

    assert _is_ancestor(worktree, planning_sha, "HEAD")
    assert (worktree / "wip.txt").read_text(encoding="utf-8") == "uncommitted work\n"


def test_seam_merges_the_planning_commit_before_the_dependency_tip(tmp_path: Path) -> None:
    """Ordering belongs to the seam: planning first, dependency tips on top.

    The lane worktree carries its own commit so BOTH adoptions are real merge
    commits rather than fast-forwards -- which is what makes the order
    observable: the dependency-tip merge's first parent is the planning merge.
    """
    repo, base, planning_sha = _seamed_repo(tmp_path)
    lane_a_tip = _create_lane_a_branch(repo)
    _seed_wp_lane(repo, _WP_DEP, Lane.APPROVED)
    worktree = _lane_b_worktree(repo, base)
    (worktree / "lane_b_work.py").write_text("lane-b in progress\n", encoding="utf-8")
    _git(worktree, "add", "lane_b_work.py")
    _git(worktree, "commit", "-qm", "lane-b: in-flight work")
    manifest, lane = _lane(repo)
    assert lane.depends_on_lanes == ("lane-a",)

    adopt_lane_ancestry(
        repo,
        worktree,
        _MISSION_SLUG,
        lane,
        manifest,
        clean_worktree_policy="refuse-dirty",
    )

    assert _is_ancestor(worktree, planning_sha, "HEAD")
    assert _is_ancestor(worktree, lane_a_tip, "HEAD")
    _head, *parents = _head_parents(worktree)
    assert len(parents) == 2, "the dependency tip must arrive as its own merge commit here"
    first_parent, second_parent = parents
    assert second_parent == lane_a_tip
    # The dependency merge sits ON TOP of the planning adoption: the planning
    # commit is already in the first parent, and the dependency tip is not.
    assert _is_ancestor(worktree, planning_sha, first_parent)
    assert not _is_ancestor(worktree, lane_a_tip, first_parent)


def test_second_adoption_is_a_no_op(tmp_path: Path) -> None:
    """Idempotence: an already-current worktree gains no new commit."""
    repo, base, planning_sha = _seamed_repo(tmp_path)
    worktree = _lane_b_worktree(repo, base)
    manifest, lane = _lane(repo)
    adopt_lane_ancestry(repo, worktree, _MISSION_SLUG, lane, manifest, clean_worktree_policy="allow-dirty")
    head_after_first = _git(worktree, "rev-parse", "HEAD")

    adopt_lane_ancestry(repo, worktree, _MISSION_SLUG, lane, manifest, clean_worktree_policy="allow-dirty")

    assert _git(worktree, "rev-parse", "HEAD") == head_after_first
    assert _is_ancestor(worktree, planning_sha, "HEAD")


def test_unknown_clean_worktree_policy_is_refused(tmp_path: Path) -> None:
    """A policy value outside the two named ones can never be a silent no-op."""
    repo, base, planning_sha = _seamed_repo(tmp_path)
    worktree = _lane_b_worktree(repo, base)
    manifest, lane = _lane(repo)

    with pytest.raises(ValueError, match="clean_worktree_policy"):
        adopt_lane_ancestry(
            repo,
            worktree,
            _MISSION_SLUG,
            lane,
            manifest,
            clean_worktree_policy="trust-me",  # type: ignore[arg-type]
        )

    assert not _is_ancestor(worktree, planning_sha, "HEAD")


def test_code_lane_reentry_tolerates_work_in_progress(tmp_path: Path) -> None:
    """SC-004: the self-heal still adopts the pin over an agent's dirty tree.

    This is the behaviour the ``allow-dirty`` policy exists for: re-entering a
    CODE lane for the SAME in-flight work package must not refuse because the
    agent has legitimate uncommitted work, and it must not discard that work.
    """
    repo, base, planning_sha = _seamed_repo(tmp_path)
    worktree = _lane_b_worktree(repo, base)
    (worktree / "wip.txt").write_text("uncommitted work\n", encoding="utf-8")

    healed = reenter_lane_self_heal(repo, _MISSION_SLUG, _WP_SELF)

    assert healed == worktree
    assert _is_ancestor(worktree, planning_sha, "HEAD")
    assert (worktree / "wip.txt").read_text(encoding="utf-8") == "uncommitted work\n"


def test_self_heal_returns_none_for_a_non_lane_mission(tmp_path: Path) -> None:
    """Nothing to heal: no ``lanes.json`` means no seam call, no repo mutation."""
    repo = tmp_path / "repo"
    _init_repo(repo)

    assert reenter_lane_self_heal(repo, _MISSION_SLUG, _WP_SELF) is None
