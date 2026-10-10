"""WP09 (#5965 / #5966): Mission-type, husk, worktree-memory, coordination-seed and pack-cache sites.

Each site group has a clean path that behaves as it did before routing, and a
refusal (or a kept result) when the target holds the only copy of something.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from kernel.tree_removal import ToolOwnedPathUnproven
from specify_cli.charter_packs.sources import git_source
from specify_cli.charter_packs.sources.git_source import GitSource
from specify_cli.cli.commands import mission_type
from specify_cli.coordination import coord_seed
from specify_cli.core import worktree as core_worktree
from specify_cli.git.destructive_guard import DestructiveOpRefused
from specify_cli.status import doctor_husks

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_SLUG = "demo-mission-01ABCDEF"


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=False)
    assert result.returncode == 0, f"git {' '.join(args)}: {result.stderr}"
    return result.stdout.strip()


def _init_repo(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.invalid")
    _git(root, "config", "user.name", "T")
    _git(root, "config", "commit.gpgsign", "false")
    (root / "README.md").write_text("seed\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "seed")
    return root


def _commit_file(root: Path, name: str, text: str = "x\n") -> None:
    (root / name).write_text(text, encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", f"add {name}")


# --------------------------------------------------------------------------- mission_type: branches


def test_branch_delete_clean_branch_is_removed(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    _git(repo, "branch", "lane-a")

    assert mission_type._force_delete_branch_if_exists(repo, "lane-a", creation_base="main") is True
    assert _git(repo, "branch", "--list", "lane-a") == ""


def test_branch_delete_missing_branch_is_false(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")

    assert mission_type._force_delete_branch_if_exists(repo, "nope") is False


def test_branch_delete_refuses_unique_commit_and_keeps_branch(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    _git(repo, "checkout", "-q", "-b", "lane-a")
    _commit_file(repo, "only-copy.txt")
    _git(repo, "checkout", "-q", "main")

    with pytest.raises(DestructiveOpRefused) as refusal:
        mission_type._force_delete_branch_if_exists(repo, "lane-a", creation_base="main")

    assert refusal.value.error_code == "BRANCH_HAS_UNIQUE_COMMITS"
    assert _git(repo, "branch", "--list", "lane-a") != ""


def test_branch_delete_allows_commits_reachable_from_another_ref(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    _git(repo, "checkout", "-q", "-b", "lane-a")
    _commit_file(repo, "landed.txt")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "-q", "--ff-only", "lane-a")

    assert mission_type._force_delete_branch_if_exists(repo, "lane-a") is True


def test_existing_ref_handles_blank_and_unknown(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")

    assert mission_type._existing_ref(repo, None) is None
    assert mission_type._existing_ref(repo, "") is None
    assert mission_type._existing_ref(repo, "ghost") is None
    assert mission_type._existing_ref(repo, "main") == "main"


def test_delete_lane_branches_keeps_lane_with_only_copy(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    _git(repo, "branch", "kitty/mission-demo")
    lane_branch = mission_type_lane_branch(_SLUG, "lane-a")
    _git(repo, "checkout", "-q", "-b", lane_branch, "kitty/mission-demo")
    _commit_file(repo, "lane-work.txt")
    _git(repo, "checkout", "-q", "main")
    manifest = SimpleNamespace(
        mission_branch="kitty/mission-demo",
        target_branch="main",
        lanes=[SimpleNamespace(lane_id="lane-a")],
    )

    with pytest.raises(DestructiveOpRefused):
        mission_type._delete_lane_branches(repo, _SLUG, manifest)

    assert _git(repo, "branch", "--list", lane_branch) != ""


def _coord_branch_with(repo: Path, branch: str, relpath: str) -> None:
    _git(repo, "checkout", "-q", "-b", branch)
    target = repo / relpath
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("data\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "coordination commit")
    _git(repo, "checkout", "-q", "main")


def test_coordination_branch_with_only_status_files_may_be_discarded(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    _coord_branch_with(repo, "kitty/mission-demo", f"kitty-specs/{_SLUG}/status.events.jsonl")

    base = mission_type._bookkeeping_branch_base(repo, "kitty/mission-demo", "main")

    assert base == _git(repo, "rev-parse", "kitty/mission-demo")
    assert mission_type._force_delete_branch_if_exists(repo, "kitty/mission-demo", creation_base=base) is True


def test_coordination_branch_with_code_commit_is_still_refused(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    _coord_branch_with(repo, "kitty/mission-demo", "src/feature.py")

    base = mission_type._bookkeeping_branch_base(repo, "kitty/mission-demo", "main")

    assert base == "main"
    with pytest.raises(DestructiveOpRefused):
        mission_type._force_delete_branch_if_exists(repo, "kitty/mission-demo", creation_base=base)


def test_bookkeeping_base_without_a_target_or_branch_falls_back(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")

    assert mission_type._bookkeeping_branch_base(repo, "kitty/mission-demo", None) is None
    assert mission_type._bookkeeping_branch_base(repo, "kitty/mission-demo", "main") == "main"


def test_legacy_coordination_branch_with_unique_code_is_refused(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    _coord_branch_with(repo, "kitty/coord-legacy", "src/feature.py")
    meta_dir = repo / "kitty-specs" / _SLUG
    meta_dir.mkdir(parents=True)
    meta = meta_dir / "meta.json"
    meta.write_text(json.dumps({"mission_slug": _SLUG, "coordination_branch": "kitty/coord-legacy", "target_branch": "main"}), encoding="utf-8")

    with pytest.raises(DestructiveOpRefused):
        mission_type._delete_legacy_coordination_branch(repo, meta)

    assert _git(repo, "branch", "--list", "kitty/coord-legacy") != ""


def test_option_shaped_branch_name_never_reaches_git(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")

    assert mission_type._force_delete_branch_if_exists(repo, "--bogus") is False


def mission_type_lane_branch(slug: str, lane_id: str) -> str:
    from specify_cli.lanes.branch_naming import code_lane_branch_name

    return code_lane_branch_name(slug, lane_id)


# --------------------------------------------------------------------------- mission_type: worktrees


def _mission_repo_with_lane_worktree(tmp_path: Path) -> tuple[Path, Path, SimpleNamespace]:
    repo = _init_repo(tmp_path / "repo")
    mission_dir = repo / "kitty-specs" / _SLUG
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text(json.dumps({"mission_slug": _SLUG, "topology": "lanes"}), encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "mission")
    from specify_cli.lanes.branch_naming import worktree_dir_name

    worktree = repo / ".worktrees" / worktree_dir_name(_SLUG, lane_id="lane-a")
    _git(repo, "worktree", "add", "-q", "-b", "lane-a-branch", str(worktree))
    manifest = SimpleNamespace(lanes=[SimpleNamespace(lane_id="lane-a")])
    return repo, worktree, manifest


def test_remove_lane_worktrees_clean_worktree_is_removed(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo, worktree, manifest = _mission_repo_with_lane_worktree(tmp_path)

    mission_type._remove_lane_worktrees(repo, _SLUG, manifest)

    assert not worktree.exists()


def test_remove_lane_worktrees_refuses_untracked_only_copy(tmp_path: Path) -> None:
    repo, worktree, manifest = _mission_repo_with_lane_worktree(tmp_path)
    (worktree / "operator-notes.txt").write_text("only copy\n", encoding="utf-8")

    with pytest.raises(DestructiveOpRefused):
        mission_type._remove_lane_worktrees(repo, _SLUG, manifest)

    assert (worktree / "operator-notes.txt").read_text(encoding="utf-8") == "only copy\n"


def test_remove_lane_worktrees_leaves_unregistered_empty_directory(tmp_path: Path) -> None:
    repo, worktree, manifest = _mission_repo_with_lane_worktree(tmp_path)
    _git(repo, "worktree", "remove", "--force", str(worktree))
    worktree.mkdir()

    mission_type._remove_lane_worktrees(repo, _SLUG, manifest)

    assert worktree.exists()


def test_remove_lane_worktrees_refuses_unregistered_directory_with_files(tmp_path: Path) -> None:
    repo, worktree, manifest = _mission_repo_with_lane_worktree(tmp_path)
    _git(repo, "worktree", "remove", "--force", str(worktree))
    worktree.mkdir()
    (worktree / "stray.txt").write_text("not a worktree\n", encoding="utf-8")

    with pytest.raises(DestructiveOpRefused):
        mission_type._remove_lane_worktrees(repo, _SLUG, manifest)

    assert (worktree / "stray.txt").exists()


def test_discard_mission_turns_a_refusal_into_exit_one(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import typer

    def refuse(**_kwargs: object) -> str | None:
        raise DestructiveOpRefused(error_code="DESTRUCTIVE_OP_ONLY_COPY", remediation="keep it")

    monkeypatch.setattr(mission_type, "_discard_mission_steps", refuse)

    with pytest.raises(typer.Exit) as exit_info:
        mission_type._discard_mission(repo_root=tmp_path, feature_dir=tmp_path, mission_slug=_SLUG, mid8_value="", meta_path=tmp_path / "meta.json", force=True)

    assert exit_info.value.exit_code == 1


# --------------------------------------------------------------------------- doctor_husks


def _stub_scan(monkeypatch: pytest.MonkeyPatch, repo: Path, names: list[str]) -> None:
    report = doctor_husks.HuskReport(
        worktrees_dir=str(repo / ".worktrees"),
        husks=[doctor_husks.HuskEntry(f".worktrees/{name}", False) for name in names],
    )
    monkeypatch.setattr(doctor_husks, "scan_workspace_husks", lambda _root: report)


def test_fix_husks_removes_empty_husk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _init_repo(tmp_path / "repo")
    husk = repo / ".worktrees" / "empty"
    (husk / "empty-subdir").mkdir(parents=True)
    _stub_scan(monkeypatch, repo, ["empty"])

    _, result = doctor_husks.fix_workspace_husks(repo)

    assert result.removed == [".worktrees/empty"]
    assert result.skipped_unsafe == []
    assert not husk.exists()


def test_fix_husks_preserves_husk_holding_only_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _init_repo(tmp_path / "repo")
    husk = repo / ".worktrees" / "holds-work"
    husk.mkdir(parents=True)
    (husk / "unsaved.py").write_text("print('only copy')\n", encoding="utf-8")
    _stub_scan(monkeypatch, repo, ["holds-work"])

    _, result = doctor_husks.fix_workspace_husks(repo)

    assert result.removed == []
    assert result.skipped_unsafe == [".worktrees/holds-work"]
    assert result.to_dict()["skipped_unsafe"] == [".worktrees/holds-work"]
    assert (husk / "unsaved.py").exists()


def test_husk_residue_context_disposes_of_nothing(tmp_path: Path) -> None:
    context = doctor_husks._HuskResidue()

    assert context.is_disposable("kitty-specs/m/meta.json") is False
    assert context.for_checkout(tmp_path, tmp_path) is context


# --------------------------------------------------------------------------- core/worktree memory


def _worktree_with_memory_dir(tmp_path: Path) -> tuple[Path, Path, Path]:
    repo = tmp_path / "repo"
    (repo / ".kittify" / "memory").mkdir(parents=True)
    (repo / ".kittify" / "memory" / "shared.md").write_text("shared\n", encoding="utf-8")
    worktree = tmp_path / "wt"
    memory = worktree / ".kittify" / "memory"
    memory.mkdir(parents=True)
    (memory / "stale.md").write_text("stale checkout copy\n", encoding="utf-8")
    feature_dir = worktree / "kitty-specs" / "001-demo"
    return repo, worktree, feature_dir


def test_setup_feature_directory_replaces_memory_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, worktree, feature_dir = _worktree_with_memory_dir(tmp_path)
    monkeypatch.setattr(core_worktree, "is_windows", lambda: False)

    core_worktree.setup_feature_directory(feature_dir, worktree, repo)

    memory = worktree / ".kittify" / "memory"
    assert memory.is_symlink()
    assert not (memory / "stale.md").exists()


def test_setup_feature_directory_copy_mode_replaces_memory_directory(tmp_path: Path) -> None:
    repo, worktree, feature_dir = _worktree_with_memory_dir(tmp_path)

    core_worktree.setup_feature_directory(feature_dir, worktree, repo, create_symlinks=False)

    memory = worktree / ".kittify" / "memory"
    assert not memory.is_symlink()
    assert (memory / "shared.md").exists()
    assert not (memory / "stale.md").exists()


def test_setup_feature_directory_refuses_memory_that_is_a_git_checkout(tmp_path: Path) -> None:
    repo, worktree, feature_dir = _worktree_with_memory_dir(tmp_path)
    memory = worktree / ".kittify" / "memory"
    (memory / ".git").mkdir()

    with pytest.raises(ToolOwnedPathUnproven):
        core_worktree.setup_feature_directory(feature_dir, worktree, repo, create_symlinks=False)

    assert (memory / "stale.md").exists()


# --------------------------------------------------------------------------- coord_seed scratch


def test_seed_scratch_removal_is_confined_to_the_scratch_root(tmp_path: Path) -> None:
    scratch_root = tmp_path / "coord" / ".spec-kitty-seed-tmp"
    stale = scratch_root / "m.seed-1-abc"
    stale.mkdir(parents=True)
    (stale / "f.txt").write_text("x", encoding="utf-8")
    outside = tmp_path / "coord" / "kitty-specs" / "m"
    outside.mkdir(parents=True)
    (outside / "keep.txt").write_text("keep", encoding="utf-8")

    coord_seed._remove_tree(stale, owned_root=scratch_root)

    assert not stale.exists()
    with pytest.raises(ToolOwnedPathUnproven):
        coord_seed._remove_tree(outside, owned_root=scratch_root)
    assert (outside / "keep.txt").exists()


def test_seed_scratch_removal_of_missing_path_is_a_noop(tmp_path: Path) -> None:
    coord_seed._remove_tree(tmp_path / "gone", owned_root=tmp_path)


# --------------------------------------------------------------------------- charter pack git source


def _pack_remote(tmp_path: Path) -> Path:
    remote = _init_repo(tmp_path / "remote")
    _commit_file(remote, "pack.yaml", "id: demo\n")
    return remote


def test_git_source_first_install_then_update_resets_through_guard(tmp_path: Path) -> None:
    remote = _pack_remote(tmp_path)
    target = tmp_path / "cache" / "pack"
    source = GitSource(url=str(remote), inject_token=False)

    first = source.fetch(target)
    assert first.ok, first.errors
    _commit_file(remote, "second.yaml", "id: two\n")

    second = source.fetch(target)

    assert second.ok, second.errors
    assert (target / "second.yaml").exists()
    assert not list((tmp_path / "cache").glob(".tmp-*"))
    assert not list((tmp_path / "cache").glob(".old-*"))


def test_git_source_update_keeps_uncommitted_pack_edit(tmp_path: Path) -> None:
    remote = _pack_remote(tmp_path)
    target = tmp_path / "cache" / "pack"
    source = GitSource(url=str(remote), inject_token=False)
    assert source.fetch(target).ok
    (target / "pack.yaml").write_text("id: hand-edited\n", encoding="utf-8")

    result = source.fetch(target)

    assert not result.ok
    assert (target / "pack.yaml").read_text(encoding="utf-8") == "id: hand-edited\n"


def test_git_source_update_reports_guard_refusal_without_resetting(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    remote = _pack_remote(tmp_path)
    target = tmp_path / "cache" / "pack"
    source = GitSource(url=str(remote), inject_token=False)
    assert source.fetch(target).ok

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise DestructiveOpRefused(error_code="DESTRUCTIVE_OP_ONLY_COPY", remediation="keep it")

    monkeypatch.setattr(git_source, "guarded_reset_hard", refuse)

    result = source.fetch(target)

    assert not result.ok
    assert "DESTRUCTIVE_OP_ONLY_COPY" in result.errors[0]


def test_discard_tool_owned_tree_removes_clone_and_plain_scratch(tmp_path: Path) -> None:
    clone = _init_repo(tmp_path / "cache" / ".tmp-clone")
    plain = tmp_path / "cache" / ".tmp-plain"
    plain.mkdir()
    (plain / "partial").write_text("x", encoding="utf-8")

    git_source._discard_tool_owned_tree(clone)
    git_source._discard_tool_owned_tree(plain)

    assert not clone.exists()
    assert not plain.exists()


def test_discard_tool_owned_tree_swallows_refusals(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    clone = _init_repo(tmp_path / "cache" / ".tmp-clone")

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise DestructiveOpRefused(error_code="DESTRUCTIVE_OP_ONLY_COPY", remediation="keep it")

    monkeypatch.setattr(git_source, "guarded_tree_delete", refuse)

    git_source._discard_tool_owned_tree(clone)

    assert clone.exists()
