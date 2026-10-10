"""Routing of lane-allocation and Mission-creation destructive sites through the guard (WP05, #5965 / #5966).

Each site group has a clean-path case (behaviour as before) and a refusal case
(an only copy of someone's work is kept). The Mission-creation group also pins
the FR-009 positive control: a just-created branch with no commit of its own
is still deleted.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mission_runtime import MissionTopology
from specify_cli.cli.commands.agent import mission_create as agent_mission_create
from specify_cli.core import mission_creation as mc
from specify_cli.core.mission_creation_rollback import (
    _CoordCreateRollbackContext,
    _base_covering_own_seed,
    _delete_created_branch,
    _remove_orphan_mission_scaffolds,
    _rollback_coordination_surface,
)
from specify_cli.git.destructive_guard import DestructiveOpRefused
from specify_cli.lanes import worktree_allocator as allocator
from specify_cli.lanes.branch_naming import code_lane_branch_name, worktree_path
from specify_cli.lanes.worktree_allocator import (
    PlanningCommitMergeConflictError,
    _abort_merge_guarded,
    _lane_residue_context,
    _merge_dependency_lane_tips,
    _remove_lane_worktree,
    allocate_lane_worktree,
)
from tests._factories.coord_mission import _init_repo_with_target
from tests.lanes.test_worktree_allocator_atomicity import (
    MISSION_SLUG,
    _commit_on_branch,
    _git,
    _make_git_repo,
    _setup_fresh_path_planning_conflict,
    _setup_two_dep_conflict,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_TOPIC = "topic"


def _out(repo: Path, *args: str) -> str:
    return _git(repo, *args).stdout.strip()


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _make_git_repo(repo)
    return repo


def _start_conflicting_merge(repo: Path, worktree: Path) -> None:
    """Leave ``worktree`` mid-merge with a conflict on ``shared.txt``."""
    _commit_on_branch(repo, "other", "main", "shared.txt", "other\n")
    _git(repo, "worktree", "add", "-b", "side", str(worktree), "main")
    (worktree / "shared.txt").write_text("side\n")
    _git(worktree, "add", "shared.txt")
    _git(worktree, "commit", "-m", "side")
    assert _git(worktree, "merge", "other", check=False).returncode != 0
    assert (worktree / ".git").exists()


# ---------------------------------------------------------------------------
# T026 - lane allocation (worktree_allocator)
# ---------------------------------------------------------------------------


def test_lane_context_falls_back_to_strictest_topology_without_meta(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    wt = repo / ".worktrees" / "lane-x"
    _git(repo, "worktree", "add", "-b", "lane-x", str(wt), "main")

    context = _lane_residue_context(repo, wt, MISSION_SLUG)

    assert context.topology is MissionTopology.LANES
    assert context.role.value == "lane"
    assert _lane_residue_context(repo, repo, MISSION_SLUG).role.value == "repository_root"


def test_abort_merge_guarded_is_a_noop_without_a_merge_in_progress(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    _abort_merge_guarded(repo, repo, MISSION_SLUG, None)

    assert _out(repo, "status", "--porcelain") == ""


def test_abort_merge_guarded_aborts_a_conflicted_merge_on_a_clean_worktree(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    wt = repo / ".worktrees" / "lane-x"
    _start_conflicting_merge(repo, wt)

    _abort_merge_guarded(repo, wt, MISSION_SLUG, None)

    assert _git(wt, "rev-parse", "-q", "--verify", "MERGE_HEAD", check=False).returncode != 0
    assert (wt / "shared.txt").read_text() == "side\n"


def test_abort_merge_guarded_refuses_over_an_operator_edit(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    wt = repo / ".worktrees" / "lane-x"
    _start_conflicting_merge(repo, wt)
    (wt / "README.md").write_text("operator rework\n")

    with pytest.raises(DestructiveOpRefused):
        _abort_merge_guarded(repo, wt, MISSION_SLUG, None)

    assert (wt / "README.md").read_text() == "operator rework\n"
    assert _git(wt, "rev-parse", "-q", "--verify", "MERGE_HEAD", check=False).returncode == 0


def test_dependency_conflict_retry_refuses_to_reset_over_unique_work(tmp_path: Path) -> None:
    """The lane retry reset used to force through dirty state; it now keeps the operator's edit."""
    repo = _repo(tmp_path)
    lane_c_wt, manifest, lane_c, _pre_loop = _setup_two_dep_conflict(repo)
    (lane_c_wt / "README.md").write_text("operator rework\n")

    with pytest.raises(DestructiveOpRefused):
        _merge_dependency_lane_tips(repo, lane_c_wt, MISSION_SLUG, lane_c, manifest)

    assert (lane_c_wt / "README.md").read_text() == "operator rework\n"


def test_planning_commit_conflict_still_removes_the_clean_fresh_worktree(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    manifest, _sha = _setup_fresh_path_planning_conflict(repo)

    with pytest.raises(PlanningCommitMergeConflictError):
        allocate_lane_worktree(repo, MISSION_SLUG, "WP-lane-a", manifest)

    assert not worktree_path(repo, MISSION_SLUG, lane_id="lane-a").exists()


def test_remove_lane_worktree_removes_a_clean_worktree(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    wt = repo / ".worktrees" / "lane-x"
    _git(repo, "worktree", "add", "-b", "lane-x", str(wt), "main")

    _remove_lane_worktree(repo, wt, MISSION_SLUG)

    assert not wt.exists()


def test_remove_lane_worktree_keeps_a_worktree_holding_an_untracked_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = _repo(tmp_path)
    wt = repo / ".worktrees" / "lane-x"
    _git(repo, "worktree", "add", "-b", "lane-x", str(wt), "main")
    (wt / "notes.md").write_text("only copy\n")

    _remove_lane_worktree(repo, wt, MISSION_SLUG)

    assert (wt / "notes.md").read_text() == "only copy\n"
    assert "kept leftover lane worktree" in capsys.readouterr().out


def test_remove_lane_worktree_reports_a_refusal_instead_of_raising(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = _repo(tmp_path)

    _remove_lane_worktree(repo, repo / ".worktrees" / "never-created", MISSION_SLUG)

    assert "failed to remove leftover lane worktree" in capsys.readouterr().out


def test_crash_recovery_prune_goes_through_the_guard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A retry after a removed worktree prunes through ``guarded_worktree_prune``; a refusal propagates."""
    repo = _repo(tmp_path)
    manifest, _sha = _setup_fresh_path_planning_conflict(repo)
    with pytest.raises(PlanningCommitMergeConflictError):
        allocate_lane_worktree(repo, MISSION_SLUG, "WP-lane-a", manifest)
    assert _out(repo, "branch", "--list", code_lane_branch_name(MISSION_SLUG, "lane-a"))
    seen: list[Path] = []
    real = allocator.guarded_worktree_prune

    def spy(repo_root: Path, **kwargs: object) -> None:
        seen.append(repo_root)
        real(repo_root)

    monkeypatch.setattr(allocator, "guarded_worktree_prune", spy)
    with pytest.raises(PlanningCommitMergeConflictError):
        allocate_lane_worktree(repo, MISSION_SLUG, "WP-lane-a", manifest)
    assert seen == [repo]
    _git(repo, "worktree", "remove", "--force", str(worktree_path(repo, MISSION_SLUG, lane_id="lane-a")))

    def refuse(repo_root: Path, **kwargs: object) -> None:
        raise DestructiveOpRefused(error_code="DESTRUCTIVE_OP_ONLY_COPY", remediation="keep it")

    monkeypatch.setattr(allocator, "guarded_worktree_prune", refuse)
    with pytest.raises(DestructiveOpRefused):
        allocate_lane_worktree(repo, MISSION_SLUG, "WP-lane-a", manifest)


# ---------------------------------------------------------------------------
# T027 - Mission-creation rollback and branch deletes (FR-009)
# ---------------------------------------------------------------------------


def test_created_branch_without_commits_of_its_own_is_deleted(tmp_path: Path) -> None:
    """FR-009 positive control."""
    repo = _repo(tmp_path)
    base = _out(repo, "rev-parse", "HEAD")
    _git(repo, "branch", "kitty/mission-fresh-01ABCDEF", "main")

    _delete_created_branch(repo, "kitty/mission-fresh-01ABCDEF", base)

    assert _out(repo, "branch", "--list", "kitty/mission-fresh-01ABCDEF") == ""


def test_created_branch_with_unique_work_is_kept(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    base = _out(repo, "rev-parse", "HEAD")
    _commit_on_branch(repo, "kitty/mission-work-01ABCDEF", "main", "src_work.py", "x = 1\n")

    _delete_created_branch(repo, "kitty/mission-work-01ABCDEF", base)

    assert _out(repo, "branch", "--list", "kitty/mission-work-01ABCDEF")


def test_base_covering_own_seed_spans_only_the_mission_directory(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    base = _out(repo, "rev-parse", "HEAD")
    branch = "kitty/mission-m-01ABCDEF"
    (repo / "kitty-specs" / "m-01ABCDEF").mkdir(parents=True)
    _commit_on_branch(repo, branch, "main", "kitty-specs/m-01ABCDEF/meta.json", "{}\n")
    tip = _out(repo, "rev-parse", branch)

    assert _base_covering_own_seed(repo, branch, base, "m-01ABCDEF") == tip
    assert _base_covering_own_seed(repo, branch, base, "other-mission") == base
    assert _base_covering_own_seed(repo, branch, None, "m-01ABCDEF") is None
    assert _base_covering_own_seed(repo, "missing-branch", base, "m-01ABCDEF") == base
    assert _base_covering_own_seed(repo, branch, "not-a-sha", "m-01ABCDEF") == "not-a-sha"


def test_orphan_scaffold_in_a_checkout_is_removed(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    scaffold = repo / "kitty-specs" / "orphan-01ABCDEF"
    scaffold.mkdir(parents=True)
    (scaffold / "meta.json").write_text("{}\n")

    _remove_orphan_mission_scaffolds((scaffold,))

    assert not scaffold.exists()


def test_orphan_scaffold_outside_a_git_checkout_is_kept(tmp_path: Path) -> None:
    scaffold = tmp_path / "plain" / "orphan"
    scaffold.mkdir(parents=True)
    (scaffold / "spec.md").write_text("not provably ours\n")

    _remove_orphan_mission_scaffolds((scaffold,))

    assert (scaffold / "spec.md").exists()


def _coord_surface(tmp_path: Path) -> tuple[Path, mc.MissionCreationResult]:
    repo = _init_repo_with_target(tmp_path, target_branch=_TOPIC, protected_primary=True)
    result = mc.create_mission_core(repo, "route-coord", topology=MissionTopology.COORD, target_branch=_TOPIC, allow_worktree_context=True)
    return repo, result


def test_rollback_of_a_reused_coordination_branch_keeps_unrecognised_files(tmp_path: Path) -> None:
    """A reused branch's coordination worktree is judged strictly: an unknown file is an only copy."""
    repo, result = _coord_surface(tmp_path)
    branch = str(result.meta["coordination_branch"])
    coord_dir = next(repo.glob(".worktrees/route-coord*-coord")) / "kitty-specs" / result.mission_slug
    (coord_dir / "operator-notes.md").write_text("only copy\n")

    _rollback_coordination_surface(
        _CoordCreateRollbackContext(
            repo_root=repo,
            mission_slug_formatted=result.mission_slug,
            mid8=str(result.meta["mid8"]),
            coordination_branch=branch,
            coordination_branch_created=False,
            pre_seed_coord_tip=_out(repo, "rev-parse", branch),
        )
    )

    assert (coord_dir / "operator-notes.md").read_text() == "only copy\n"


def test_rollback_of_a_minted_coordination_branch_clears_the_surface(tmp_path: Path) -> None:
    repo, result = _coord_surface(tmp_path)
    branch = str(result.meta["coordination_branch"])
    coord_dir = next(repo.glob(".worktrees/route-coord*-coord")) / "kitty-specs" / result.mission_slug
    (coord_dir / "interrupted-seed.md").write_text("partial\n")

    _rollback_coordination_surface(
        _CoordCreateRollbackContext(
            repo_root=repo,
            mission_slug_formatted=result.mission_slug,
            mid8=str(result.meta["mid8"]),
            coordination_branch=branch,
            coordination_branch_created=True,
            creation_base=_out(repo, "merge-base", branch, _TOPIC),
        )
    )

    assert not list(repo.glob(".worktrees/route-coord*"))
    assert _out(repo, "branch", "--list", branch) == ""


def _start_branch_state(repo: Path) -> agent_mission_create._StartBranchRollbackState:
    head = _out(repo, "rev-parse", "HEAD")
    _git(repo, "switch", "-c", "start-here")
    return agent_mission_create._StartBranchRollbackState(
        repo_root=repo,
        start_branch="start-here",
        start_branch_preexisted=False,
        start_branch_original_commit=None,
        original_branch="main",
        original_commit=head,
        original_index_tree=None,
    )


def test_start_branch_rollback_deletes_a_branch_without_commits_of_its_own(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    state = _start_branch_state(repo)

    agent_mission_create._restore_start_branch_after_failure(state)

    assert _out(repo, "branch", "--list", "start-here") == ""
    assert _out(repo, "branch", "--show-current") == "main"


def test_start_branch_rollback_refuses_to_delete_a_branch_with_commits(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    state = _start_branch_state(repo)
    (repo / "work.py").write_text("x = 1\n")
    _git(repo, "add", "work.py")
    _git(repo, "commit", "-m", "work on the start branch")

    with pytest.raises(DestructiveOpRefused):
        agent_mission_create._restore_start_branch_after_failure(state)

    assert _out(repo, "branch", "--list", "start-here")
    assert _out(repo, "branch", "--show-current") == "main"


def _fail_inside_start_branch_rollback(repo: Path) -> None:
    with agent_mission_create._rollback_start_branch_on_failure(repo, "start-here"):
        _git(repo, "switch", "-c", "start-here")
        (repo / "work.py").write_text("x = 1\n")
        _git(repo, "add", "work.py")
        _git(repo, "commit", "-m", "work")
        raise _CreateFailed("create failed")


class _CreateFailed(Exception):
    pass


def test_start_branch_rollback_context_manager_notes_a_refusal_and_keeps_the_original_error(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    with pytest.raises(_CreateFailed) as excinfo:
        _fail_inside_start_branch_rollback(repo)

    assert any("Failed to restore checkout" in note for note in excinfo.value.__notes__)
    assert _out(repo, "branch", "--list", "start-here")
