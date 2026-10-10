"""WP04 (#5965 / #5966): the consolidation family's destructive sites run behind the guard.

One clean-path test and one only-copy refusal per site group, against real git
repositories. The sites: the post-merge checkout refresh and the behind-own-HEAD resume
recovery (``reset --hard HEAD``), the scratch worktrees and trees the consolidation
creates and removes itself (tool-owned), and the ``merge --abort`` of a failed lane
auto-rebase.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from specify_cli.consolidation import git_probes, resume_recovery
from specify_cli.consolidation import preflight as pf
from specify_cli.consolidation.state import ConsolidationState, save_state
from specify_cli.consolidation.workspace import (
    abort_scratch_merge,
    cleanup_merge_workspace,
    create_merge_workspace,
    _discard_scratch_tree,
    get_merge_runtime_dir,
    get_merge_workspace_path,
    remove_scratch_worktree,
)
from specify_cli.coordination.coherence import CheckoutRole, ResidueContext
from specify_cli.git.destructive_guard import MERGE_UNSAFE_PRIMARY_DIRTY, DestructiveOpRefused
from specify_cli.lanes import auto_rebase
from specify_cli.lanes.consolidation import _merge_branch_into

pytestmark = [pytest.mark.git_repo]

_MISSION = "m-01ABCDEF"
_MISSION_ID = "01ABCDEFGHJKMNPQRSTVWXYZ00"
_MISSION_BRANCH = "kitty/mission-m"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()


def _init(repo: Path) -> Path:
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "alpha.txt").write_text("alpha\n", encoding="utf-8")
    _git(repo, "add", "alpha.txt")
    _git(repo, "commit", "-qm", "base")
    return repo


def _write_meta(repo: Path, slug: str = _MISSION) -> None:
    mission_dir = repo / "kitty-specs" / slug
    mission_dir.mkdir(parents=True, exist_ok=True)
    (mission_dir / "meta.json").write_text(json.dumps({"mission_slug": slug, "mission_id": _MISSION_ID}), encoding="utf-8")


def _lagging_repo(tmp_path: Path) -> tuple[Path, str]:
    """A repository whose ``main`` was advanced by ``update-ref`` while the checkout stayed at ``base``."""
    repo = _init(tmp_path / "repo")
    base = _git(repo, "rev-parse", "HEAD")
    (repo / "lane.py").write_text("lane\n", encoding="utf-8")
    _git(repo, "add", "lane.py")
    _git(repo, "commit", "-qm", "advance")
    advanced = _git(repo, "rev-parse", "HEAD")
    _git(repo, "reset", "-q", "--hard", base)
    _git(repo, "update-ref", "refs/heads/main", advanced, base)
    _git(repo, "branch", _MISSION_BRANCH, base)
    return repo, base


# --- post-merge refresh (git_probes) ------------------------------------------------


def test_refresh_resets_a_checkout_that_only_lags_the_advanced_target(tmp_path: Path) -> None:
    repo, base = _lagging_repo(tmp_path)

    git_probes._refresh_primary_checkout_after_merge(repo, "main", lag_base_sha=base)

    assert (repo / "lane.py").read_text(encoding="utf-8") == "lane\n"
    assert _git(repo, "status", "--porcelain") == ""


def test_refresh_keeps_an_operator_edit_and_does_not_reset(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo, base = _lagging_repo(tmp_path)
    (repo / "alpha.txt").write_text("only copy of the operator's edit\n", encoding="utf-8")

    git_probes._refresh_primary_checkout_after_merge(repo, "main", lag_base_sha=base)

    assert (repo / "alpha.txt").read_text(encoding="utf-8") == "only copy of the operator's edit\n"
    assert not (repo / "lane.py").exists(), "nothing may be reset when the checkout holds an only copy"
    assert "skipping post-merge working-tree refresh" in " ".join(capsys.readouterr().out.split())


def test_refresh_without_a_lag_anchor_refuses_over_a_lagging_checkout(tmp_path: Path) -> None:
    repo, _base = _lagging_repo(tmp_path)

    git_probes._refresh_primary_checkout_after_merge(repo, "main")

    assert not (repo / "lane.py").exists(), "no anchor and no Mission: the strictest context resets nothing dirty"


def test_lag_residue_context_excludes_a_lag_path_the_operator_edited(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    base = _git(repo, "rev-parse", "HEAD")
    (repo / "alpha.txt").write_text("newer in HEAD\n", encoding="utf-8")
    (repo / "beta.txt").write_text("beta\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "advance")
    _git(repo, "checkout", "-q", base, "--", "alpha.txt")
    (repo / "alpha.txt").write_text("operator edit on the stale copy\n", encoding="utf-8")
    _git(repo, "rm", "-q", "--cached", "beta.txt")

    context = git_probes.lag_residue_context(repo, base)

    assert not context.is_disposable("alpha.txt"), "an edit on top of the stale copy is not regenerable"
    assert context.is_disposable("beta.txt")
    assert not context.is_disposable("unrelated.txt")


def test_lag_residue_context_is_strictest_without_an_anchor_or_when_git_cannot_say(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")

    assert git_probes.lag_residue_context(repo, None).lag_paths == frozenset()
    assert git_probes.lag_residue_context(repo, "0" * 40).lag_paths == frozenset()


def test_lag_residue_context_adds_the_mission_residue_and_follows_the_checkout(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    _write_meta(repo)
    inner = git_probes.mission_residue_context(repo, _MISSION)
    assert isinstance(inner, ResidueContext) and inner.role is CheckoutRole.REPOSITORY_ROOT

    context = git_probes.lag_residue_context(repo, None, inner)

    assert context.is_disposable(f"kitty-specs/{_MISSION}/meta.json")
    assert not context.is_disposable("src/app.py")
    assert context.for_checkout(repo, repo).is_disposable(f"kitty-specs/{_MISSION}/meta.json")
    assert git_probes.lag_residue_context(repo, None).for_checkout(repo, repo).lag_paths == frozenset()


def test_mission_residue_context_is_none_without_a_slug_or_a_readable_topology(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")

    assert git_probes.mission_residue_context(repo, None) is None
    assert git_probes.mission_residue_context(repo, "absent-mission") is None
    (repo / "kitty-specs" / "broken").mkdir(parents=True)
    (repo / "kitty-specs" / "broken" / "meta.json").write_text("[1, 2]", encoding="utf-8")
    assert git_probes.mission_residue_context(repo, "broken") is None


# --- behind-own-HEAD resume recovery (resume_recovery) --------------------------------


def _resume_state(repo: Path, base: str) -> None:
    state = ConsolidationState(mission_id=_MISSION_ID, mission_slug="m", target_branch="main", wp_order=["WP01"])
    state.pre_mutation_target_sha = base
    save_state(state, repo)


def _primary_refusal(repo: Path) -> DestructiveOpRefused:
    return DestructiveOpRefused(error_code=MERGE_UNSAFE_PRIMARY_DIRTY, remediation="commit", worktree_path=repo, dirty_entries=["D  lane.py"])


def test_resume_recovery_resets_a_provably_pure_lag(tmp_path: Path) -> None:
    repo, base = _lagging_repo(tmp_path)
    _resume_state(repo, base)

    recovered = resume_recovery._recover_behind_head_primary_on_resume(_primary_refusal(repo), repo, _MISSION_ID, mission_branch=_MISSION_BRANCH)

    assert recovered is True
    assert (repo / "lane.py").read_text(encoding="utf-8") == "lane\n"


def test_resume_recovery_guard_refuses_an_edit_the_proof_did_not_see(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo, base = _lagging_repo(tmp_path)
    _resume_state(repo, base)
    (repo / "alpha.txt").write_text("edited after the proof\n", encoding="utf-8")

    with patch.object(pf, "is_pure_behind_head_lag", return_value=True):
        recovered = resume_recovery._recover_behind_head_primary_on_resume(_primary_refusal(repo), repo, _MISSION_ID, mission_branch=_MISSION_BRANCH)

    assert recovered is False
    assert (repo / "alpha.txt").read_text(encoding="utf-8") == "edited after the proof\n"
    assert not (repo / "lane.py").exists()
    assert "would discard local changes" in " ".join(capsys.readouterr().out.split())


# --- scratch worktrees and trees the consolidation owns -------------------------------


def _scratch_worktree(repo: Path, name: str) -> Path:
    path = repo.parent / name
    _git(repo, "worktree", "add", "-q", "--detach", str(path), "HEAD")
    return path


def test_scratch_worktree_is_removed(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    scratch = _scratch_worktree(repo, "scratch")

    assert remove_scratch_worktree(scratch) is True

    assert not scratch.exists()
    assert str(scratch) not in _git(repo, "worktree", "list", "--porcelain")


def test_scratch_worktree_with_tool_output_is_removed(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    scratch = _scratch_worktree(repo, "scratch")
    (scratch / "alpha.txt").write_text("generated by the merge\n", encoding="utf-8")
    (scratch / "junk.log").write_text("log\n", encoding="utf-8")

    assert remove_scratch_worktree(scratch) is True

    assert not scratch.exists()


def test_scratch_removal_of_something_that_is_not_a_worktree_keeps_it(tmp_path: Path) -> None:
    not_a_worktree = tmp_path / "plain"
    not_a_worktree.mkdir()
    (not_a_worktree / "file.txt").write_text("keep\n", encoding="utf-8")

    assert remove_scratch_worktree(not_a_worktree) is False

    assert (not_a_worktree / "file.txt").read_text(encoding="utf-8") == "keep\n"


def test_discard_scratch_tree_removes_a_plain_tree_under_its_tool_root(tmp_path: Path) -> None:
    owned = tmp_path / "runtime"
    tree = owned / "child"
    (tree / "deep").mkdir(parents=True)
    (tree / "deep" / "f.txt").write_text("x\n", encoding="utf-8")

    assert _discard_scratch_tree(tree, tool_root=owned, reason="test") is True

    assert not tree.exists()


def test_discard_scratch_tree_refuses_a_path_outside_its_tool_root(tmp_path: Path) -> None:
    owned = tmp_path / "runtime"
    owned.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "f.txt").write_text("keep\n", encoding="utf-8")

    assert _discard_scratch_tree(outside, tool_root=owned, reason="test") is False

    assert (outside / "f.txt").read_text(encoding="utf-8") == "keep\n"


def test_discard_scratch_tree_removes_a_checkout_through_the_guard(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    owned = tmp_path / "runtime"
    owned.mkdir()
    scratch = owned / "workspace"
    _git(repo, "worktree", "add", "-q", "--detach", str(scratch), "HEAD")
    (scratch / "generated.txt").write_text("tool output\n", encoding="utf-8")

    assert _discard_scratch_tree(scratch, tool_root=owned, reason="test") is True

    assert not scratch.exists()


def test_discard_scratch_tree_drops_a_dangling_gitlink(tmp_path: Path) -> None:
    owned = tmp_path / "runtime"
    stale = owned / "workspace"
    stale.mkdir(parents=True)
    (stale / ".git").write_text(f"gitdir: {tmp_path}/gone/.git/worktrees/workspace\n", encoding="utf-8")
    (stale / "left.txt").write_text("left over\n", encoding="utf-8")

    assert _discard_scratch_tree(stale, tool_root=owned, reason="test") is True

    assert not stale.exists()


def test_discard_scratch_tree_keeps_a_directory_whose_git_dir_cannot_be_read(tmp_path: Path) -> None:
    owned = tmp_path / "runtime"
    broken = owned / "workspace"
    (broken / ".git").mkdir(parents=True)
    (broken / "work.txt").write_text("nothing proves this disposable\n", encoding="utf-8")

    assert _discard_scratch_tree(broken, tool_root=owned, reason="test") is False

    assert (broken / "work.txt").read_text(encoding="utf-8") == "nothing proves this disposable\n"


def test_cleanup_merge_workspace_removes_the_worktree_and_keeps_the_state_file(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    workspace = create_merge_workspace("m1", "main", repo)
    runtime = get_merge_runtime_dir("m1", repo)
    (runtime / "state.json").write_text("{}", encoding="utf-8")
    (runtime / "scratch-dir").mkdir()
    (runtime / "scratch-dir" / "f.txt").write_text("x\n", encoding="utf-8")
    (runtime / "scratch-file.txt").write_text("x\n", encoding="utf-8")

    cleanup_merge_workspace("m1", repo)

    assert not workspace.exists()
    assert not (runtime / "scratch-dir").exists() and not (runtime / "scratch-file.txt").exists()
    assert (runtime / "state.json").exists()


def test_cleanup_merge_workspace_force_removes_a_dirty_workspace(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    workspace = create_merge_workspace("m2", "main", repo)
    (workspace / "alpha.txt").write_text("half-merged\n", encoding="utf-8")

    cleanup_merge_workspace("m2", repo)

    assert not workspace.exists()
    assert str(get_merge_workspace_path("m2", repo)) not in _git(repo, "worktree", "list", "--porcelain")


def test_create_merge_workspace_replaces_a_stale_unregistered_directory(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    stale = get_merge_workspace_path("m3", repo)
    stale.mkdir(parents=True)
    (stale / "leftover.txt").write_text("stale\n", encoding="utf-8")

    workspace = create_merge_workspace("m3", "main", repo)

    assert workspace == stale
    assert not (stale / "leftover.txt").exists()
    assert (stale / "alpha.txt").exists()


# --- merge --abort ---------------------------------------------------------------------


def _conflicted_merge(repo: Path) -> None:
    """Leave ``repo`` mid-merge with a conflict in ``alpha.txt``."""
    _git(repo, "checkout", "-q", "-b", "other")
    (repo / "alpha.txt").write_text("other\n", encoding="utf-8")
    _git(repo, "commit", "-qam", "other change")
    _git(repo, "checkout", "-q", "main")
    (repo / "alpha.txt").write_text("main\n", encoding="utf-8")
    _git(repo, "commit", "-qam", "main change")
    merged = subprocess.run(["git", "merge", "--no-commit", "other"], cwd=repo, capture_output=True, text=True, check=False)
    assert merged.returncode != 0
    assert (repo / ".git" / "MERGE_HEAD").exists()


def test_scratch_merge_abort_ends_the_merge(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    _conflicted_merge(repo)

    assert abort_scratch_merge(repo) is True

    assert not (repo / ".git" / "MERGE_HEAD").exists()
    assert (repo / "alpha.txt").read_text(encoding="utf-8") == "main\n"


def test_scratch_merge_abort_without_a_merge_in_progress_is_a_logged_no_op(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")

    assert abort_scratch_merge(repo) is False


def test_auto_rebase_failure_aborts_the_merge_in_a_clean_lane_worktree(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    _conflicted_merge(repo)

    report = auto_rebase._abort_with_failure(auto_rebase._abort_context(repo, None), repo, "lane-a", [], "halt")

    assert report.succeeded is False and report.halt_reason == "halt"
    assert not (repo / ".git" / "MERGE_HEAD").exists()


def test_auto_rebase_failure_leaves_the_merge_when_an_operator_edit_would_be_lost(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    (repo / "notes.txt").write_text("notes\n", encoding="utf-8")
    _git(repo, "add", "notes.txt")
    _git(repo, "commit", "-qm", "notes")
    _conflicted_merge(repo)
    (repo / "notes.txt").write_text("the operator's only copy\n", encoding="utf-8")

    report = auto_rebase._abort_with_failure(auto_rebase._abort_context(repo, None), repo, "lane-a", [], "halt")

    assert report.succeeded is False
    assert "left in progress" in (report.halt_reason or "")
    assert (repo / ".git" / "MERGE_HEAD").exists(), "the guard refused, so the merge is still in progress"
    assert (repo / "notes.txt").read_text(encoding="utf-8") == "the operator's only copy\n"


def test_auto_rebase_abort_context_follows_the_mission_when_it_is_readable(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    _write_meta(repo)

    readable = auto_rebase._abort_context(repo, _MISSION)
    unreadable = auto_rebase._abort_context(repo, "no-such-mission")

    assert isinstance(readable, ResidueContext) and readable.role is CheckoutRole.LANE
    assert unreadable is auto_rebase._NOTHING_DISPOSABLE
    assert auto_rebase._abort_context(repo, None) is auto_rebase._NOTHING_DISPOSABLE


# --- lane merge ref advance (lanes/consolidation) ---------------------------------------


def _feature_branch(repo: Path) -> None:
    _git(repo, "checkout", "-q", "-b", "feature")
    (repo / "feature.py").write_text("feature\n", encoding="utf-8")
    _git(repo, "add", "feature.py")
    _git(repo, "commit", "-qm", "feature work")
    _git(repo, "checkout", "-q", "main")


def test_lane_merge_advances_the_target_and_resyncs_a_clean_checkout(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    _write_meta(repo)
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "mission meta")
    _feature_branch(repo)

    changed = _merge_branch_into(repo, "feature", "main", mission_slug=_MISSION)

    assert changed is True
    assert (repo / "feature.py").read_text(encoding="utf-8") == "feature\n"


def test_lane_merge_refuses_to_resync_over_an_operator_edit(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    _write_meta(repo)
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "mission meta")
    _feature_branch(repo)
    main_before = _git(repo, "rev-parse", "main")
    (repo / "alpha.txt").write_text("the operator's only copy\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="alpha.txt"):
        _merge_branch_into(repo, "feature", "main", mission_slug=_MISSION)

    assert (repo / "alpha.txt").read_text(encoding="utf-8") == "the operator's only copy\n"
    assert _git(repo, "rev-parse", "main") == main_before


def test_discard_scratch_tree_keeps_a_live_registered_worktree_when_the_guard_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A refusal over a gitlink whose git dir still exists is never answered by dropping the link."""
    repo = _init(tmp_path / "repo")
    owned = tmp_path / "runtime"
    owned.mkdir()
    scratch = owned / "workspace"
    _git(repo, "worktree", "add", "-q", "--detach", str(scratch), "HEAD")
    (scratch / "alpha.txt").write_text("uncommitted only copy\n", encoding="utf-8")

    def _refuse(path: Path, **_: object) -> None:
        raise DestructiveOpRefused(error_code="DESTRUCTIVE_OP_ONLY_COPY", worktree_path=path, dirty_entries=["alpha.txt"], remediation="keep")

    monkeypatch.setattr("specify_cli.consolidation.workspace.guarded_tree_delete", _refuse)

    assert _discard_scratch_tree(scratch, tool_root=owned, reason="test") is False

    assert (scratch / "alpha.txt").read_text(encoding="utf-8") == "uncommitted only copy\n"
    assert (scratch / ".git").is_file()
