"""Unit coverage for the shared ``meta.json`` write mechanics (``consolidation/meta_write.py``, #7692).

The mission-number bake uses them today and the retarget phase reuses them; these pin
each helper directly on real git repositories.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from specify_cli.consolidation import meta_write
from specify_cli.consolidation.meta_write import MetaBranchOutcome, MetaBranchRefusal

pytestmark = [pytest.mark.fast]

_SLUG = "meta-write-probe"
_BRANCH = "kitty/mission-meta-write-probe"
_REL_META = Path("kitty-specs") / _SLUG / "meta.json"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def _repo(tmp_path: Path, *, with_meta: bool = True) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    if with_meta:
        (repo / _REL_META).parent.mkdir(parents=True)
        (repo / _REL_META).write_text(json.dumps({"mission_slug": _SLUG, "target_branch": "main"}, indent=2) + "\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed")
    return repo


def _set(key: str, value: object) -> meta_write.MetaMutate:
    def mutate(meta: dict[str, Any]) -> bool:
        if meta.get(key) == value:
            return False
        meta[key] = value
        return True

    return mutate


# --- locked_update_meta_capturing / undo_meta_write ----------------------------------


def test_locked_update_returns_the_bytes_before_and_written(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    feature_dir = (repo / _REL_META).parent
    before_on_disk = (repo / _REL_META).read_bytes()

    captured = meta_write.locked_update_meta_capturing(feature_dir, _set("target_branch", "develop"), repo_root=repo)

    assert captured is not None
    before, written = captured
    assert before == before_on_disk
    assert written == (repo / _REL_META).read_bytes()
    assert json.loads(written)["target_branch"] == "develop"


def test_locked_update_is_none_when_mutate_changes_nothing(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    feature_dir = (repo / _REL_META).parent
    before_on_disk = (repo / _REL_META).read_bytes()

    assert meta_write.locked_update_meta_capturing(feature_dir, _set("target_branch", "main"), repo_root=repo) is None
    assert (repo / _REL_META).read_bytes() == before_on_disk, "an unchanged meta is never rewritten"


def test_undo_restores_the_file_while_it_still_holds_what_was_written(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    meta_path = repo / _REL_META
    captured = meta_write.locked_update_meta_capturing(meta_path.parent, _set("target_branch", "develop"), repo_root=repo)
    assert captured is not None

    assert meta_write.undo_meta_write(meta_path, captured[0], captured[1], repo) is None
    assert meta_path.read_bytes() == captured[0]


def test_undo_leaves_a_file_another_writer_changed(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    meta_path = repo / _REL_META
    captured = meta_write.locked_update_meta_capturing(meta_path.parent, _set("target_branch", "develop"), repo_root=repo)
    assert captured is not None
    other = meta_write.locked_update_meta_capturing(meta_path.parent, _set("friendly_name", "other writer"), repo_root=repo)
    assert other is not None

    note = meta_write.undo_meta_write(meta_path, captured[0], captured[1], repo)

    assert note is not None and "changed by another writer" in note
    assert meta_path.read_bytes() == other[1], "a field another writer set is never erased"


# --- primary_checkout_refusal --------------------------------------------------------


def test_primary_checkout_refusal_is_none_for_a_clean_tracked_meta_on_target(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    assert meta_write.primary_checkout_refusal(repo, _REL_META, "main") is None


def test_primary_checkout_refusal_names_a_detached_head(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _git(repo, "checkout", "-q", "--detach")
    assert meta_write.primary_checkout_refusal(repo, _REL_META, "main") == "primary checkout is on a detached HEAD"


def test_primary_checkout_refusal_names_another_branch(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _git(repo, "checkout", "-qb", "develop")
    assert meta_write.primary_checkout_refusal(repo, _REL_META, "main") == "primary checkout is on 'develop', not the merge target 'main'"


def test_primary_checkout_refusal_names_an_untracked_meta(tmp_path: Path) -> None:
    repo = _repo(tmp_path, with_meta=False)
    (repo / _REL_META).parent.mkdir(parents=True)
    (repo / _REL_META).write_text("{}\n", encoding="utf-8")
    assert meta_write.primary_checkout_refusal(repo, _REL_META, "main") == f"{_REL_META} is not tracked on 'main'"


def test_primary_checkout_refusal_names_a_dirty_meta(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / _REL_META).write_text("{}\n", encoding="utf-8")
    assert meta_write.primary_checkout_refusal(repo, _REL_META, "main") == f"{_REL_META} has uncommitted changes on the primary checkout"


def test_primary_checkout_refusal_names_a_skip_worktree_edit(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _git(repo, "update-index", "--skip-worktree", _REL_META.as_posix())
    (repo / _REL_META).write_text("{}\n", encoding="utf-8")
    refusal = meta_write.primary_checkout_refusal(repo, _REL_META, "main")
    assert refusal is not None and "skip-worktree" in refusal


# --- commit_meta_on_branch -----------------------------------------------------------


def test_commit_meta_on_branch_advances_the_branch_with_a_one_file_commit(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _git(repo, "branch", _BRANCH)
    tip_before = _git(repo, "rev-parse", _BRANCH)

    result = meta_write.commit_meta_on_branch(repo, _BRANCH, _SLUG, _set("target_branch", "develop"), message="chore(probe): retarget main -> develop")

    assert result.outcome is MetaBranchOutcome.WRITTEN
    assert result.new_sha == _git(repo, "rev-parse", _BRANCH)
    assert _git(repo, "rev-parse", f"{_BRANCH}^") == tip_before
    assert _git(repo, "show", "--name-only", "--format=", _BRANCH) == _REL_META.as_posix()
    assert _git(repo, "log", "-1", "--format=%s", _BRANCH) == "chore(probe): retarget main -> develop"
    assert json.loads(_git(repo, "show", f"{_BRANCH}:{_REL_META.as_posix()}"))["target_branch"] == "develop"
    assert json.loads((repo / _REL_META).read_text(encoding="utf-8"))["target_branch"] == "main", "the root checkout is untouched"
    assert "kitty-metawrite-" not in _git(repo, "worktree", "list"), "the scratch worktree (default prefix) is removed"


def test_commit_meta_on_branch_reports_a_branch_without_the_meta(tmp_path: Path) -> None:
    repo = _repo(tmp_path, with_meta=False)
    _git(repo, "branch", _BRANCH)
    tip_before = _git(repo, "rev-parse", _BRANCH)

    result = meta_write.commit_meta_on_branch(repo, _BRANCH, _SLUG, _set("target_branch", "develop"), message="m")

    assert result.outcome is MetaBranchOutcome.NO_META_ON_BRANCH
    assert _git(repo, "rev-parse", _BRANCH) == tip_before


def test_commit_meta_on_branch_reports_an_unchanged_meta(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _git(repo, "branch", _BRANCH)
    tip_before = _git(repo, "rev-parse", _BRANCH)

    result = meta_write.commit_meta_on_branch(repo, _BRANCH, _SLUG, _set("target_branch", "main"), message="m")

    assert result.outcome is MetaBranchOutcome.UNCHANGED
    assert result.unchanged_on_read is True
    assert _git(repo, "rev-parse", _BRANCH) == tip_before


def test_commit_meta_on_branch_refuses_a_meta_that_is_not_an_object(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / _REL_META).write_text("[1, 2]\n", encoding="utf-8")
    _git(repo, "commit", "-qam", "list meta")
    _git(repo, "branch", _BRANCH)

    result = meta_write.commit_meta_on_branch(repo, _BRANCH, _SLUG, _set("target_branch", "develop"), message="m")

    assert result.outcome is MetaBranchOutcome.REFUSED
    assert result.refusal is MetaBranchRefusal.NOT_A_JSON_OBJECT


def test_commit_meta_on_branch_refuses_when_the_scratch_worktree_cannot_be_made(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    result = meta_write.commit_meta_on_branch(repo, "no-such-branch", _SLUG, _set("target_branch", "develop"), message="m")

    assert result.outcome is MetaBranchOutcome.REFUSED
    assert result.refusal is MetaBranchRefusal.WORKTREE_UNAVAILABLE
    assert result.detail
