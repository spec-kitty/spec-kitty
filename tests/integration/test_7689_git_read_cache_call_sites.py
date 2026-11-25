"""Each git read routed through the run-scoped read cache sees the mutation that changes its answer (#7689).

``spec-kitty consolidate`` runs inside one :func:`kernel.git.read_cache.git_read_cache_scope`.
For every read it now caches, these tests prime the cache, perform the mutation consolidate (or an
outside process) can make between two reads, and require the cached call site to return what git
itself says afterwards. Each test also checks that the repeat before the mutation spawned no git
process, so a call site that silently stops caching goes red too.
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from kernel.git.read_cache import git_read_cache_scope
from kernel.git.remote import configured_remotes
from mission_runtime.lifecycle_phase import _target_ref_exists
from specify_cli.consolidation.rollback import _live_tip
from specify_cli.coordination.policy import _local_branch_exists
from specify_cli.coordination.surface_resolver import read_worktree_registry
from specify_cli.core.git_ops import _origin_head_branch, get_current_branch
from specify_cli.git.protection_policy import _remote_default_branch
from specify_cli.git.ref_advance import advance_branch_ref, worktrees_with_branch_checked_out
from specify_cli.lanes.consolidation import _git_common_dir, _git_config_get, _set_local_git_config

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox]

_REAL_POPEN = subprocess.Popen


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@e", "-c", "commit.gpgsign=false", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for name in ("GIT_DIR", "GIT_COMMON_DIR", "GIT_WORK_TREE", "GIT_NAMESPACE", "GIT_OBJECT_DIRECTORY", "GIT_CONFIG"):
        monkeypatch.delenv(name, raising=False)
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    (root / "a.txt").write_text("a\n")
    _git(root, "add", "a.txt")
    _git(root, "commit", "-qm", "one")
    _git(root, "branch", "side")
    return root


class _GitSpawns:
    """Counts git processes started while active."""

    def __init__(self) -> None:
        self.count = 0

    def __call__(self, args: Any, *rest: Any, **kwargs: Any) -> Any:
        argv = args if isinstance(args, (list, tuple)) else [args]
        if argv and Path(str(argv[0])).name.startswith("git"):
            self.count += 1
        return _REAL_POPEN(args, *rest, **kwargs)


@pytest.fixture
def spawns() -> Iterator[_GitSpawns]:
    counter = _GitSpawns()
    with mock.patch("subprocess.Popen", side_effect=counter):
        yield counter


def _no_spawn_on_repeat(spawns: _GitSpawns, read: Callable[[], object]) -> object:
    """Call *read* twice; the second call must start no git process. Returns the answer."""
    first = read()
    before = spawns.count
    second = read()
    assert spawns.count == before, "the repeat spawned git: the call site is not cached"
    assert second == first
    return first


def test_live_tip_follows_a_compare_and_swap_advance(repo: Path, spawns: _GitSpawns) -> None:
    with git_read_cache_scope():
        old = _no_spawn_on_repeat(spawns, lambda: _live_tip(repo, "side"))
        _git(repo, "commit", "-q", "--allow-empty", "-m", "two")
        new = _git(repo, "rev-parse", "HEAD")
        advance_branch_ref(repo, "side", new, expected_old_sha=str(old))
        assert _live_tip(repo, "side") == new


def test_live_tip_sees_a_deleted_branch(repo: Path, spawns: _GitSpawns) -> None:
    with git_read_cache_scope():
        assert _no_spawn_on_repeat(spawns, lambda: _live_tip(repo, "side"))
        _git(repo, "branch", "-D", "side")
        assert _live_tip(repo, "side") is None


def test_local_branch_exists_sees_create_and_delete(repo: Path, spawns: _GitSpawns) -> None:
    with git_read_cache_scope():
        assert _no_spawn_on_repeat(spawns, lambda: _local_branch_exists(repo, "fresh")) is False
        _git(repo, "branch", "fresh")
        assert _local_branch_exists(repo, "fresh") is True
        _git(repo, "branch", "-D", "fresh")
        assert _local_branch_exists(repo, "fresh") is False


def test_target_ref_exists_sees_create_and_delete(repo: Path, spawns: _GitSpawns) -> None:
    with git_read_cache_scope():
        assert _no_spawn_on_repeat(spawns, lambda: _target_ref_exists(repo, "work")) is False
        _git(repo, "branch", "work")
        assert _target_ref_exists(repo, "work") is True
        _git(repo, "branch", "-D", "work")
        assert _target_ref_exists(repo, "work") is False


def test_current_branch_follows_a_checkout(repo: Path, spawns: _GitSpawns) -> None:
    with git_read_cache_scope():
        assert _no_spawn_on_repeat(spawns, lambda: get_current_branch(repo)) == "main"
        _git(repo, "checkout", "-q", "side")
        assert get_current_branch(repo) == "side"
        _git(repo, "checkout", "-q", "--detach")
        assert get_current_branch(repo) is None


def test_origin_head_follows_set_head(repo: Path, spawns: _GitSpawns) -> None:
    _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    _git(repo, "update-ref", "refs/remotes/origin/side", "side")
    with git_read_cache_scope():
        assert _no_spawn_on_repeat(spawns, lambda: _origin_head_branch(repo)) is None
        _git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
        assert _origin_head_branch(repo) == "main"
        _git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/side")
        assert _origin_head_branch(repo) == "side"


def test_remote_default_branch_follows_origin_head_and_config(repo: Path, spawns: _GitSpawns) -> None:
    with git_read_cache_scope():
        assert _no_spawn_on_repeat(spawns, lambda: _remote_default_branch(repo)) is None, "no origin is a definitive answer"
        _git(repo, "update-ref", "refs/remotes/origin/trunk", "HEAD")
        _git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/trunk")
        assert _no_spawn_on_repeat(spawns, lambda: _remote_default_branch(repo)) == "trunk"
        _git(repo, "symbolic-ref", "-d", "refs/remotes/origin/HEAD")
        _git(repo, "config", "--local", "remote.origin.url", str(repo))
        before = spawns.count
        assert _remote_default_branch(repo) == "main"
        assert spawns.count > before, "a config write must invalidate the remote default branch"


def test_worktree_registry_follows_add_remove_and_prune(repo: Path, tmp_path: Path, spawns: _GitSpawns) -> None:
    linked = tmp_path / "linked"
    with git_read_cache_scope():
        before = _no_spawn_on_repeat(spawns, lambda: read_worktree_registry(repo))
        _git(repo, "worktree", "add", "-q", str(linked), "side")
        assert linked.resolve() in read_worktree_registry(repo)
        shutil.rmtree(linked)
        _git(repo, "worktree", "prune")
        assert read_worktree_registry(repo) == before


def test_ref_advance_worktree_listing_follows_a_checkout_switch(repo: Path, tmp_path: Path, spawns: _GitSpawns) -> None:
    linked = tmp_path / "linked"
    _git(repo, "worktree", "add", "-q", str(linked), "side")
    with git_read_cache_scope():
        assert _no_spawn_on_repeat(spawns, lambda: worktrees_with_branch_checked_out(repo, "side")) == [linked.resolve()]
        _git(linked, "checkout", "-q", "--detach")
        assert worktrees_with_branch_checked_out(repo, "side") == []
        _git(repo, "worktree", "remove", "--force", str(linked))
        assert worktrees_with_branch_checked_out(repo, "side") == []


def test_merge_driver_config_read_follows_a_config_write(repo: Path, spawns: _GitSpawns) -> None:
    key = "merge.spec-kitty-test.name"
    with git_read_cache_scope():
        assert _no_spawn_on_repeat(spawns, lambda: _git_config_get(repo, key)) is None
        _set_local_git_config(repo, key, "v1")
        assert _git_config_get(repo, key) == "v1"
        before = spawns.count
        _set_local_git_config(repo, key, "v1")  # already current: answered from the cache, no write
        assert spawns.count == before
        _git(repo, "config", "--local", key, "v2")
        assert _git_config_get(repo, key) == "v2"


def test_a_failed_lookup_of_a_configured_origin_is_asked_again(repo: Path, spawns: _GitSpawns, tmp_path: Path) -> None:
    """#7689 landing fold: an unreachable configured origin may be transient, so its None is never reused."""
    _git(repo, "remote", "add", "origin", str(tmp_path / "does-not-exist.git"))
    with git_read_cache_scope():
        assert _remote_default_branch(repo) is None
        before = spawns.count
        assert _remote_default_branch(repo) is None
        assert spawns.count > before, "a failed lookup of a configured origin must be asked again, never reused"


def test_configured_remotes_follows_remote_add_and_remove(repo: Path, spawns: _GitSpawns) -> None:
    """#7848: consolidate lists the remotes four times; the list is a function of the config."""
    with git_read_cache_scope():
        assert _no_spawn_on_repeat(spawns, lambda: configured_remotes(repo)) == []
        _git(repo, "remote", "add", "origin", str(repo))
        assert configured_remotes(repo) == ["origin"]
        _git(repo, "remote", "rename", "origin", "upstream")
        assert configured_remotes(repo) == ["upstream"]
        _git(repo, "remote", "remove", "upstream")
        assert configured_remotes(repo) == []


def test_git_common_dir_is_read_once_per_checkout(repo: Path, tmp_path: Path, spawns: _GitSpawns) -> None:
    """#7848: the merge-driver activation asks for the common dir around every lane merge."""
    linked = tmp_path / "linked"
    _git(repo, "worktree", "add", "-q", str(linked), "side")
    with git_read_cache_scope():
        main_dir = _no_spawn_on_repeat(spawns, lambda: _git_common_dir(repo))
        linked_dir = _no_spawn_on_repeat(spawns, lambda: _git_common_dir(linked))
    assert main_dir is not None and linked_dir is not None
    assert Path(str(main_dir)).resolve() == Path(str(linked_dir)).resolve() == (repo / ".git").resolve()
    plain = tmp_path / "plain"
    plain.mkdir()
    with git_read_cache_scope():
        assert _git_common_dir(plain) is None, "outside a repository there is no common dir, and none is kept"
        assert _git_common_dir(plain) is None
