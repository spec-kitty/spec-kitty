"""Dependency-lane merge keeps the dependent lane's target-owned bookkeeping (#5457, WP04).

Story 4 AS-5 / FR-013 through the real ``spec-kitty implement`` CLI: lane-b
(WP02) depends on lane-a (WP01, approved). A pre-fix upgrade committed a
divergent ``.kittify/metadata.yaml`` on both lane branches, so the reuse-path
dependency merge (``worktree_allocator._merge_dependency_lane_tips``) conflicts
on that path. The control adds a genuine source conflict, which must still
raise ``DependencyLaneMergeConflictError`` (FR-009).
"""

from __future__ import annotations

import dataclasses
import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.lanes import worktree_allocator
from specify_cli.lanes.branch_naming import code_lane_branch_name
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import read_lanes_json
from specify_cli.lanes.worktree_allocator import (
    DependencyLaneMergeConflictError,
    PlanningCommitMergeConflictError,
    allocate_lane_worktree,
)
from specify_cli.status.reducer import materialize
from tests.integration.target_owned_fixtures import (
    LanesProject,
    build_older_version_lanes_project,
    commit_broken_upgrade_state,
    commit_file_on_branch,
    metadata_blob,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_SHARED_SOURCE = "src/shared.py"
_DEPENDENCY_CONFLICT = "cannot auto-merge dependency lane 'lane-a' (kitty/mission-target-owned-01M5457A-lane-a) into lane 'lane-b': the merge conflicts."


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout


def _normalised(result: subprocess.CompletedProcess[str]) -> str:
    return " ".join(((result.stdout or "") + (result.stderr or "")).split())


def _dependent_lane_project(tmp_path: Path, *, status_json_divergence: bool = False) -> LanesProject:
    """lane-b depends on lane-a; WP01 approved, WP02 planned; both lanes broken.

    Scenario setup: the fixture approves every WP, so WP02's history is cut
    back to ``planned`` (its claim re-recorded as the genesis transition) for
    ``implement`` to pick it up.
    """
    project = build_older_version_lanes_project(
        tmp_path,
        topology="lanes",
        lanes=2,
        depends_on_lanes={"lane-b": ("lane-a",)},
        status_json_divergence=status_json_divergence,
        with_analysis_report=True,
    )
    commit_broken_upgrade_state(project)
    events_path = project.feature_dir / "status.events.jsonl"
    kept: list[str] = []
    for line in events_path.read_text(encoding="utf-8").splitlines():
        event = json.loads(line)
        if event["wp_id"] != "WP02":
            kept.append(line)
        elif event["to_lane"] == "claimed":
            event.update(from_lane="genesis", to_lane="planned")
            kept.append(json.dumps(event, sort_keys=True))
    events_path.write_text("\n".join(kept) + "\n", encoding="utf-8")
    materialize(project.feature_dir)
    _git(project.repo, "commit", "-qm", "chore: WP02 planned", "--", str(project.feature_dir))
    return project


def test_implement_dependent_wp_keeps_its_own_metadata(tmp_path: Path) -> None:
    """AS-5 (FR-013): the dependency merge resolves metadata to the dependent lane's copy."""
    project = _dependent_lane_project(tmp_path)
    lane_b = project.lane_branches["lane-b"]
    lane_a_tip = _git(project.repo, "rev-parse", project.lane_branches["lane-a"]).strip()
    own_metadata = metadata_blob(project.repo, lane_b)

    result = project.run("implement", "WP02", "--mission", project.slug)

    output = _normalised(result)
    assert _DEPENDENCY_CONFLICT not in output, output
    assert result.returncode == 0, output
    subprocess.run(["git", "-C", str(project.repo), "merge-base", "--is-ancestor", lane_a_tip, lane_b], check=True)
    assert metadata_blob(project.repo, lane_b) == own_metadata
    assert _git(project.repo, "show", f"{lane_b}:src/lane_a/m.py")
    worktree = project.lane_worktrees["lane-b"]
    assert _git(worktree, "status", "--porcelain", "--untracked-files=no") == ""


def test_implement_dependent_wp_resolves_mixed_metadata_and_status_conflict(tmp_path: Path) -> None:
    """A MIXED dependency conflict (target-owned metadata + derived status.json) resolves and commits.

    The target-owned resolver takes the metadata to stage 2 but leaves the
    ``status.json`` conflict, so it declines to commit; the derived-snapshot
    reconcile then regenerates ``status.json`` from the dependent lane's event
    log and completes the dependency merge.
    """
    project = _dependent_lane_project(tmp_path, status_json_divergence=True)
    lane_b = project.lane_branches["lane-b"]
    lane_a_tip = _git(project.repo, "rev-parse", project.lane_branches["lane-a"]).strip()
    status_path = f"kitty-specs/{project.slug}/status.json"
    lane_a_status = _git(project.repo, "show", f"{lane_a_tip}:{status_path}")
    lane_b_status = _git(project.repo, "show", f"{lane_b}:{status_path}")
    assert lane_a_status != lane_b_status
    own_metadata = metadata_blob(project.repo, lane_b)

    result = project.run("implement", "WP02", "--mission", project.slug)

    output = _normalised(result)
    assert _DEPENDENCY_CONFLICT not in output, output
    assert result.returncode == 0, output
    subprocess.run(["git", "-C", str(project.repo), "merge-base", "--is-ancestor", lane_a_tip, lane_b], check=True)
    merge_parents = _git(project.repo, "log", "--merges", "--format=%P", "-1", lane_b).split()
    assert lane_a_tip in merge_parents
    assert metadata_blob(project.repo, lane_b) == own_metadata
    merged_status = json.loads(_git(project.repo, "show", f"{lane_b}:{status_path}"))
    # Regenerated from the event log -- neither side's planted ``{"side": ...}`` snapshot.
    assert "side" not in merged_status
    assert _git(project.lane_worktrees["lane-b"], "status", "--porcelain", "--untracked-files=no") == ""


def test_implement_dependent_wp_source_conflict_still_refused(tmp_path: Path) -> None:
    """Dependency control (FR-009): a genuine source conflict still raises, atomically."""
    project = _dependent_lane_project(tmp_path)
    lane_b = project.lane_branches["lane-b"]
    commit_file_on_branch(project.repo, project.lane_branches["lane-a"], _SHARED_SOURCE, "a = 1\n", "feat: lane-a shared")
    commit_file_on_branch(project.repo, lane_b, _SHARED_SOURCE, "b = 1\n", "feat: lane-b shared")
    lane_b_tip = _git(project.repo, "rev-parse", lane_b).strip()

    result = project.run("implement", "WP02", "--mission", project.slug)

    output = _normalised(result)
    assert result.returncode != 0, output
    assert _DEPENDENCY_CONFLICT in output, output
    assert _git(project.repo, "rev-parse", lane_b).strip() == lane_b_tip
    assert _git(project.lane_worktrees["lane-b"], "status", "--porcelain", "--untracked-files=no") == ""


@pytest.mark.parametrize("source_conflict", [False, True], ids=["bookkeeping-only", "plus-source-conflict"])
def test_recorded_planning_commit_merge_resolves_target_owned_bookkeeping(tmp_path: Path, source_conflict: bool) -> None:
    """The recorded planning-commit merge (FR-009) keeps the lane's own metadata (#5457).

    ``implement`` re-entry merges the recorded ``planning_commit_sha`` before the
    dependency merge. Once that pin sits at or after the target's pre-fix upgrade
    commit (a ``finalize-tasks`` re-run), the merge conflicts on the divergent
    ``.kittify/metadata.yaml``: it resolves to the lane's copy. A genuine source
    conflict beside it still refuses and leaves the lane untouched.
    """
    project = build_older_version_lanes_project(tmp_path, topology="lanes", lanes=1)
    commit_broken_upgrade_state(project)
    lane = project.lane_branches["lane-a"]
    if source_conflict:
        commit_file_on_branch(project.repo, lane, _SHARED_SOURCE, "lane = 1\n", "feat: lane shared")
        commit_file_on_branch(project.repo, project.target_branch, _SHARED_SOURCE, "target = 1\n", "feat: target shared")
    pin = _git(project.repo, "rev-parse", project.target_branch).strip()
    manifest = dataclasses.replace(read_lanes_json(project.feature_dir), planning_commit_sha=pin)
    lane_tip = _git(project.repo, "rev-parse", lane).strip()
    own_metadata = metadata_blob(project.repo, lane)

    if source_conflict:
        with pytest.raises(PlanningCommitMergeConflictError):
            allocate_lane_worktree(project.repo, project.slug, "WP01", manifest)
        assert _git(project.repo, "rev-parse", lane).strip() == lane_tip
        assert not (Path(_git(project.lane_worktrees["lane-a"], "rev-parse", "--absolute-git-dir").strip()) / "MERGE_HEAD").exists()
    else:
        allocate_lane_worktree(project.repo, project.slug, "WP01", manifest)
        subprocess.run(["git", "-C", str(project.repo), "merge-base", "--is-ancestor", pin, lane], check=True)
        assert _git(project.repo, "log", "-1", "--format=%s", lane).strip().startswith("Merge recorded planning-artifact commit into lane-a")
        assert metadata_blob(project.repo, lane) == own_metadata
    assert _git(project.lane_worktrees["lane-a"], "status", "--porcelain", "--untracked-files=no") == ""


# ---------------------------------------------------------------------------
# #1915 atomicity when the conflict resolver itself fails (closeout fold F1).
# ---------------------------------------------------------------------------

_UNIT_SLUG = "010-feat"


def _unit_lane(lane_id: str, *, depends: tuple[str, ...] = (), group: int = 0) -> ExecutionLane:
    return ExecutionLane(
        lane_id=lane_id,
        wp_ids=(f"WP-{lane_id}",),
        write_scope=("src/**",),
        predicted_surfaces=(),
        depends_on_lanes=depends,
        parallel_group=group,
    )


def _unit_branch(repo: Path, branch: str, filename: str, content: str) -> None:
    _git(repo, "branch", branch, "main")
    _git(repo, "checkout", "-q", branch)
    (repo / filename).write_text(content, encoding="utf-8")
    _git(repo, "add", filename)
    _git(repo, "commit", "-qm", f"{branch}: write {filename}")
    _git(repo, "checkout", "-q", "main")


def _clean_then_conflicting_deps(repo: Path) -> tuple[Path, LanesManifest, ExecutionLane, str]:
    """lane-c depends on lane-a (clean addition) and lane-b (conflicts on shared.txt)."""
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("init\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "init")
    lane_a, lane_b = _unit_lane("lane-a"), _unit_lane("lane-b", group=1)
    lane_c = _unit_lane("lane-c", depends=("lane-a", "lane-b"), group=2)
    manifest = LanesManifest(
        version=1,
        mission_slug=_UNIT_SLUG,
        mission_id=_UNIT_SLUG,
        mission_branch=f"kitty/mission-{_UNIT_SLUG}",
        target_branch="main",
        lanes=[lane_a, lane_b, lane_c],
        planning_commit_sha=None,
        computed_at="2026-10-04T12:00:00+00:00",
        computed_from="test",
    )
    _unit_branch(repo, code_lane_branch_name(_UNIT_SLUG, "lane-a"), "from_lane_a.txt", "lane-a\n")
    _unit_branch(repo, code_lane_branch_name(_UNIT_SLUG, "lane-b"), "shared.txt", "lane-b\n")
    worktree = repo / ".worktrees" / f"{_UNIT_SLUG}-lane-c"
    _git(repo, "worktree", "add", "-q", "-b", code_lane_branch_name(_UNIT_SLUG, "lane-c"), str(worktree), "main")
    (worktree / "shared.txt").write_text("lane-c\n", encoding="utf-8")
    _git(worktree, "add", "shared.txt")
    _git(worktree, "commit", "-qm", "lane-c: write shared.txt")
    return worktree, manifest, lane_c, _git(worktree, "rev-parse", "HEAD").strip()


def _raise_runtime_error(*_args: object) -> bool:
    raise RuntimeError("Could not inspect squash merge conflicts: simulated git failure")


@pytest.mark.parametrize(
    "resolver",
    ["_complete_merge_after_target_owned_resolution", "reconcile_derived_status_snapshot_conflicts"],
)
def test_resolver_failure_still_rolls_back_atomically(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, resolver: str) -> None:
    """A RuntimeError from a conflict resolver must not skip the #1915 abort + reset path."""
    repo = tmp_path / "repo"
    repo.mkdir()
    worktree, manifest, lane_c, pre_loop_head = _clean_then_conflicting_deps(repo)
    monkeypatch.setattr(worktree_allocator, resolver, _raise_runtime_error)

    with pytest.raises(DependencyLaneMergeConflictError):
        worktree_allocator._merge_dependency_lane_tips(repo, worktree, _UNIT_SLUG, lane_c, manifest)

    assert _git(worktree, "rev-parse", "HEAD").strip() == pre_loop_head
    assert not (worktree / "from_lane_a.txt").exists()
    assert _git(worktree, "status", "--porcelain", "--untracked-files=no") == ""
    assert not (Path(_git(worktree, "rev-parse", "--absolute-git-dir").strip()) / "MERGE_HEAD").exists()
