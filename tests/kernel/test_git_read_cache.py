"""Tests for :mod:`kernel.git.read_cache` (#7689) against real git repositories.

Every test answers one question: after a given git mutation, does a cached read
still return what git itself returns? Each mutation class consolidate performs
(ref update, branch create and delete, checkout, worktree add and remove,
config write, ``pack-refs``, a write by another process) is driven through real
git, and the cached answer is compared with a fresh, uncached git call.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from kernel.git.read_cache import (
    Depends,
    cached_git_read,
    cached_object_read,
    cached_ref_read,
    git_read_cache_active,
    git_read_cache_scope,
    is_object_id,
)

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]


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


class _Counter:
    """A read that counts how often it really ran git."""

    def __init__(self, cwd: Path, *argv: str) -> None:
        self.cwd = cwd
        self.argv = argv
        self.calls = 0

    def __call__(self) -> str:
        self.calls += 1
        result = subprocess.run(["git", *self.argv], cwd=self.cwd, capture_output=True, text=True, check=False)
        return f"{result.returncode}:{result.stdout.strip()}"


def _tip(cwd: Path, ref: str) -> _Counter:
    return _Counter(cwd, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")


def _read_tip(repo: Path, read: _Counter, ref: str) -> str:
    return cached_ref_read(repo, ref, "tip", read)


# --------------------------------------------------------------------------- scope


def test_outside_a_scope_every_read_runs_git(repo: Path) -> None:
    read = _tip(repo, "refs/heads/main")
    _read_tip(repo, read, "refs/heads/main")
    _read_tip(repo, read, "refs/heads/main")
    assert read.calls == 2


def test_a_repeat_inside_a_scope_spawns_nothing(repo: Path) -> None:
    read = _tip(repo, "refs/heads/main")
    with git_read_cache_scope() as stats:
        first = _read_tip(repo, read, "refs/heads/main")
        second = _read_tip(repo, read, "refs/heads/main")
    assert first == second
    assert read.calls == 1
    assert (stats.hits, stats.misses) == (1, 1)


def test_a_nested_scope_shares_the_outer_entries(repo: Path) -> None:
    read = _tip(repo, "refs/heads/main")
    with git_read_cache_scope() as outer:
        _read_tip(repo, read, "refs/heads/main")
        with git_read_cache_scope() as inner:
            _read_tip(repo, read, "refs/heads/main")
        assert inner is outer
    assert read.calls == 1


def test_the_scope_ends_with_its_block(repo: Path) -> None:
    read = _tip(repo, "refs/heads/main")
    with git_read_cache_scope():
        _read_tip(repo, read, "refs/heads/main")
    _read_tip(repo, read, "refs/heads/main")
    assert read.calls == 2


def test_a_read_that_raises_is_not_cached(repo: Path) -> None:
    calls = 0

    def boom() -> str:
        nonlocal calls
        calls += 1
        raise subprocess.TimeoutExpired(["git"], 1)

    with git_read_cache_scope():
        for _ in range(2):
            with pytest.raises(subprocess.TimeoutExpired):
                cached_ref_read(repo, "refs/heads/main", "boom", boom)
    assert calls == 2


# --------------------------------------------------------------------------- invalidation by mutation


def test_a_ref_update_invalidates_that_ref(repo: Path) -> None:
    read = _tip(repo, "refs/heads/main")
    with git_read_cache_scope():
        before = _read_tip(repo, read, "refs/heads/main")
        (repo / "a.txt").write_text("b\n")
        _git(repo, "commit", "-qam", "two")
        after = _read_tip(repo, read, "refs/heads/main")
    assert before != after
    assert after == f"0:{_git(repo, 'rev-parse', 'main')}"
    assert read.calls == 2


def test_a_compare_and_swap_update_ref_invalidates_that_ref(repo: Path) -> None:
    old = _git(repo, "rev-parse", "main")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "two")
    new = _git(repo, "rev-parse", "main")
    _git(repo, "update-ref", "refs/heads/main", old, new)
    read = _tip(repo, "refs/heads/main")
    with git_read_cache_scope():
        assert _read_tip(repo, read, "refs/heads/main") == f"0:{old}"
        _git(repo, "update-ref", "refs/heads/main", new, old)
        assert _read_tip(repo, read, "refs/heads/main") == f"0:{new}"


def test_an_unrelated_ref_update_keeps_a_per_ref_entry(repo: Path) -> None:
    read = _tip(repo, "refs/heads/main")
    with git_read_cache_scope():
        _read_tip(repo, read, "refs/heads/main")
        _git(repo, "update-ref", "refs/heads/other", "HEAD")
        _read_tip(repo, read, "refs/heads/main")
    assert read.calls == 1


def test_branch_create_and_delete_invalidate_an_existence_read(repo: Path) -> None:
    read = _tip(repo, "refs/heads/fresh")
    with git_read_cache_scope():
        assert _read_tip(repo, read, "refs/heads/fresh").startswith("1:")
        _git(repo, "branch", "fresh")
        assert _read_tip(repo, read, "refs/heads/fresh").startswith("0:")
        _git(repo, "branch", "-D", "fresh")
        assert _read_tip(repo, read, "refs/heads/fresh").startswith("1:")
    assert read.calls == 3


def test_pack_refs_keeps_answers_right(repo: Path) -> None:
    read = _tip(repo, "refs/heads/side")
    with git_read_cache_scope():
        before = _read_tip(repo, read, "refs/heads/side")
        _git(repo, "pack-refs", "--all")
        assert _read_tip(repo, read, "refs/heads/side") == before
        _git(repo, "commit", "-q", "--allow-empty", "-m", "two")
        _git(repo, "update-ref", "refs/heads/side", "HEAD")
        assert _read_tip(repo, read, "refs/heads/side") == f"0:{_git(repo, 'rev-parse', 'HEAD')}"


def test_a_checkout_invalidates_a_head_read(repo: Path) -> None:
    read = _Counter(repo, "branch", "--show-current")
    with git_read_cache_scope():
        assert cached_git_read(repo, "branch", read, depends=Depends(head=True)) == "0:main"
        _git(repo, "checkout", "-q", "side")
        assert cached_git_read(repo, "branch", read, depends=Depends(head=True)) == "0:side"
        _git(repo, "checkout", "-q", "--detach")
        assert cached_git_read(repo, "branch", read, depends=Depends(head=True)) == "0:"


def test_a_head_read_is_per_checkout(repo: Path, tmp_path: Path) -> None:
    linked = tmp_path / "linked"
    _git(repo, "worktree", "add", "-q", str(linked), "side")
    with git_read_cache_scope():
        main_read = _Counter(repo, "branch", "--show-current")
        linked_read = _Counter(linked, "branch", "--show-current")
        assert cached_git_read(repo, "branch", main_read, depends=Depends(head=True)) == "0:main"
        assert cached_git_read(linked, "branch", linked_read, depends=Depends(head=True)) == "0:side"
        _git(linked, "checkout", "-q", "--detach")
        assert cached_git_read(linked, "branch", linked_read, depends=Depends(head=True)) == "0:"
        assert cached_git_read(repo, "branch", main_read, depends=Depends(head=True)) == "0:main"
    assert main_read.calls == 1


def test_worktree_add_lock_and_remove_invalidate_the_registry(repo: Path, tmp_path: Path) -> None:
    read = _Counter(repo, "worktree", "list", "--porcelain")
    linked = tmp_path / "wt"
    with git_read_cache_scope():
        before = cached_git_read(repo, "worktrees", read)
        _git(repo, "worktree", "add", "-q", str(linked), "side")
        added = cached_git_read(repo, "worktrees", read)
        assert added != before and str(linked) in added
        _git(repo, "worktree", "lock", str(linked))
        assert "locked" in cached_git_read(repo, "worktrees", read)
        _git(repo, "worktree", "unlock", str(linked))
        _git(repo, "worktree", "remove", "--force", str(linked))
        assert cached_git_read(repo, "worktrees", read) == before
    assert read.calls == 4


def test_a_deleted_linked_checkout_shows_as_prunable(repo: Path, tmp_path: Path) -> None:
    import shutil

    linked = tmp_path / "gone"
    _git(repo, "worktree", "add", "-q", str(linked), "side")
    read = _Counter(repo, "worktree", "list", "--porcelain")
    with git_read_cache_scope():
        assert "prunable" not in cached_git_read(repo, "worktrees", read)
        shutil.rmtree(linked)
        assert "prunable" in cached_git_read(repo, "worktrees", read)


def test_a_config_write_invalidates_a_config_read(repo: Path) -> None:
    read = _Counter(repo, "config", "--local", "--get", "spec.key")
    with git_read_cache_scope():
        assert cached_git_read(repo, "cfg", read, depends=Depends(config=True)) == "1:"
        _git(repo, "config", "--local", "spec.key", "v1")
        assert cached_git_read(repo, "cfg", read, depends=Depends(config=True)) == "0:v1"
        assert cached_git_read(repo, "cfg", read, depends=Depends(config=True)) == "0:v1"
    assert read.calls == 2


def test_a_symbolic_ref_dependency_follows_its_target(repo: Path) -> None:
    _git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
    _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    read = _tip(repo, "refs/remotes/origin/HEAD")
    with git_read_cache_scope():
        before = _read_tip(repo, read, "refs/remotes/origin/HEAD")
        _git(repo, "commit", "-q", "--allow-empty", "-m", "two")
        _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
        assert _read_tip(repo, read, "refs/remotes/origin/HEAD") != before
        _git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/heads/side")
        assert _read_tip(repo, read, "refs/remotes/origin/HEAD") == f"0:{_git(repo, 'rev-parse', 'side')}"


def test_a_write_while_the_read_runs_is_not_stored(repo: Path) -> None:
    calls = 0

    def racing_read() -> str:
        nonlocal calls
        calls += 1
        answer = _git(repo, "rev-parse", "main")
        _git(repo, "commit", "-q", "--allow-empty", "-m", f"race {calls}")
        return answer

    with git_read_cache_scope() as stats:
        cached_ref_read(repo, "refs/heads/main", "racing", racing_read)
        cached_ref_read(repo, "refs/heads/main", "racing", racing_read)
    assert calls == 2
    assert stats.hits == 0


def test_a_short_ref_name_depends_on_everything(repo: Path) -> None:
    read = _tip(repo, "main")
    with git_read_cache_scope():
        _read_tip(repo, read, "main")
        _git(repo, "update-ref", "refs/heads/other", "HEAD")
        _read_tip(repo, read, "main")
    assert read.calls == 2


# --------------------------------------------------------------------------- bypass


@pytest.mark.parametrize("variable", ["GIT_DIR", "GIT_COMMON_DIR", "GIT_WORK_TREE", "GIT_OBJECT_DIRECTORY"])
def test_a_redirecting_process_variable_bypasses_the_cache(repo: Path, monkeypatch: pytest.MonkeyPatch, variable: str) -> None:
    monkeypatch.setenv(variable, str(repo / ".git" if variable != "GIT_WORK_TREE" else repo))
    if variable == "GIT_OBJECT_DIRECTORY":
        monkeypatch.setenv(variable, str(repo / ".git" / "objects"))
    calls = 0

    def read() -> str:
        nonlocal calls
        calls += 1
        return "x"

    with git_read_cache_scope() as stats:
        cached_ref_read(repo, "refs/heads/main", "k", read)
        cached_ref_read(repo, "refs/heads/main", "k", read)
    assert calls == 2
    assert stats.bypassed == 2


def test_a_redirecting_variable_in_the_passed_env_bypasses_the_cache(repo: Path) -> None:
    calls = 0

    def read() -> str:
        nonlocal calls
        calls += 1
        return "x"

    env = {"GIT_DIR": str(repo / ".git")}
    with git_read_cache_scope() as stats:
        cached_ref_read(repo, "refs/heads/main", "k", read, env=env)
        cached_ref_read(repo, "refs/heads/main", "k", read, env=env)
    assert calls == 2
    assert stats.bypassed == 2


def test_injected_config_does_not_bypass_the_cache(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "core.pager")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "cat")
    read = _tip(repo, "refs/heads/main")
    with git_read_cache_scope():
        _read_tip(repo, read, "refs/heads/main")
        _read_tip(repo, read, "refs/heads/main")
    assert read.calls == 1


def test_a_directory_outside_any_repository_bypasses_the_cache(tmp_path: Path) -> None:
    outside = tmp_path / "plain"
    outside.mkdir()
    calls = 0

    def read() -> str:
        nonlocal calls
        calls += 1
        return "x"

    with git_read_cache_scope() as stats:
        cached_git_read(outside, "k", read)
        cached_git_read(outside, "k", read)
    assert calls == 2
    assert stats.bypassed == 2


def test_a_linked_checkout_shares_ref_entries_with_its_repository(repo: Path, tmp_path: Path) -> None:
    linked = tmp_path / "linked"
    _git(repo, "worktree", "add", "-q", str(linked), "side")
    read = _tip(repo, "refs/heads/main")
    with git_read_cache_scope():
        _read_tip(repo, read, "refs/heads/main")
        cached_ref_read(linked, "refs/heads/main", "tip", read)
    assert read.calls == 1


# --------------------------------------------------------------------------- landing folds (#7689)


def test_a_reftable_repository_runs_every_read_uncached(repo: Path) -> None:
    """The fingerprint models the files ref backend only; a reftable repository bypasses the cache."""
    config = repo / ".git" / "config"
    config.write_text(config.read_text(encoding="utf-8") + "[extensions]\n\trefStorage = reftable\n", encoding="utf-8")
    calls = 0

    def compute() -> str:
        nonlocal calls
        calls += 1
        return "answer"

    with git_read_cache_scope() as stats:
        assert cached_git_read(repo, "q", compute, depends=Depends(head=True)) == "answer"
        assert cached_git_read(repo, "q", compute, depends=Depends(head=True)) == "answer"
    assert calls == 2, "a reftable repository must never answer from the cache"
    assert stats.bypassed == 2


def test_store_if_keeps_a_rejected_answer_out_of_the_cache(repo: Path) -> None:
    answers = iter([None, None, "main", "never"])
    calls = 0

    def compute() -> str | None:
        nonlocal calls
        calls += 1
        return next(answers)

    def read() -> str | None:
        return cached_git_read(repo, "remote-default", compute, depends=Depends(config=True), store_if=lambda value: value is not None)

    with git_read_cache_scope():
        assert read() is None
        assert read() is None
        assert read() == "main"
        assert read() == "main"
    assert calls == 3, "None is asked again each time; the first real answer is then reused"


# --------------------------------------------------------------------------- immutable-object reads (#7848)


def _log_of(repo: Path, rev: str) -> _Counter:
    return _Counter(repo, "rev-list", rev)


def test_an_object_read_repeat_inside_a_scope_spawns_nothing(repo: Path) -> None:
    sha = _git(repo, "rev-parse", "main")
    read = _log_of(repo, sha)
    with git_read_cache_scope():
        first = cached_object_read(repo, (sha,), "log", read)
        (repo / "a.txt").write_text("b\n")
        _git(repo, "commit", "-qam", "two")  # a ref move does not change what a commit id names
        _git(repo, "checkout", "-q", "side")
        second = cached_object_read(repo, (sha,), "log", read)
    assert first == second == f"0:{sha}"
    assert read.calls == 1


def test_an_object_read_of_a_ref_name_is_never_cached(repo: Path) -> None:
    read = _log_of(repo, "main")
    with git_read_cache_scope() as stats:
        cached_object_read(repo, ("main",), "log", read)
        cached_object_read(repo, ("main",), "log", read)
    assert read.calls == 2
    assert stats.hits == 0


def test_an_object_read_of_a_short_or_negated_id_is_never_cached(repo: Path) -> None:
    sha = _git(repo, "rev-parse", "main")
    read = _log_of(repo, sha[:12])
    with git_read_cache_scope():
        cached_object_read(repo, (sha[:12],), "log", read)
        cached_object_read(repo, (sha[:12],), "log", read)
    assert read.calls == 2


def test_a_replace_ref_invalidates_an_object_read(repo: Path) -> None:
    one = _git(repo, "rev-parse", "main")
    (repo / "a.txt").write_text("b\n")
    _git(repo, "commit", "-qam", "two")
    two = _git(repo, "rev-parse", "main")
    read = _Counter(repo, "rev-list", two)
    with git_read_cache_scope():
        before = cached_object_read(repo, (two,), "log", read)
        _git(repo, "replace", two, _git(repo, "commit-tree", "-m", "root", f"{two}^{{tree}}"))  # cuts the history
        after = cached_object_read(repo, (two,), "log", read)
    assert before == f"0:{two}\n{one}"
    assert after == f"0:{_git(repo, 'rev-list', two)}" == f"0:{two}"
    assert read.calls == 2


def test_a_shallow_or_graft_write_invalidates_an_object_read(repo: Path) -> None:
    sha = _git(repo, "rev-parse", "main")
    read = _log_of(repo, sha)
    with git_read_cache_scope():
        cached_object_read(repo, (sha,), "log", read)
        (repo / ".git" / "shallow").write_text(f"{sha}\n")
        cached_object_read(repo, (sha,), "log", read)
        (repo / ".git" / "info").mkdir(exist_ok=True)
        (repo / ".git" / "info" / "grafts").write_text(f"{sha}\n")
        cached_object_read(repo, (sha,), "log", read)
    assert read.calls == 3


def test_an_object_read_takes_store_if(repo: Path) -> None:
    sha = _git(repo, "rev-parse", "main")
    calls = 0

    def compute() -> int:
        nonlocal calls
        calls += 1
        return 128

    with git_read_cache_scope():
        cached_object_read(repo, (sha,), "status", compute, store_if=lambda code: code in (0, 1))
        cached_object_read(repo, (sha,), "status", compute, store_if=lambda code: code in (0, 1))
    assert calls == 2


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("0" * 40, True),
        ("a" * 64, True),
        ("A" * 40, False),
        ("0" * 39, False),
        ("0" * 41, False),
        ("^" + "0" * 40, False),
        ("main", False),
        ("refs/heads/main", False),
        ("", False),
    ],
)
def test_is_object_id_accepts_only_full_lowercase_ids(text: str, expected: bool) -> None:
    assert is_object_id(text) is expected


def test_git_read_cache_active_reports_the_scope() -> None:
    assert not git_read_cache_active()
    with git_read_cache_scope():
        assert git_read_cache_active()
    assert not git_read_cache_active()


def test_a_replace_setting_or_reftable_stack_write_invalidates_an_object_read(repo: Path) -> None:
    sha = _git(repo, "rev-parse", "main")
    read = _log_of(repo, sha)
    with git_read_cache_scope():
        cached_object_read(repo, (sha,), "log", read)
        _git(repo, "config", "core.useReplaceRefs", "false")
        cached_object_read(repo, (sha,), "log", read)
        (repo / ".git" / "reftable").mkdir()
        (repo / ".git" / "reftable" / "tables.list").write_text("x\n")
        cached_object_read(repo, (sha,), "log", read)
    assert read.calls == 3


@pytest.mark.parametrize(
    "variable", ["GIT_REPLACE_REF_BASE", "GIT_NO_REPLACE_OBJECTS", "GIT_GRAFT_FILE", "GIT_SHALLOW_FILE", "GIT_CONFIG_PARAMETERS", "GIT_CONFIG_COUNT"]
)
def test_a_history_variable_bypasses_an_object_read(repo: Path, monkeypatch: pytest.MonkeyPatch, variable: str) -> None:
    sha = _git(repo, "rev-parse", "main")
    read = _log_of(repo, sha)
    monkeypatch.setenv(variable, "1")
    with git_read_cache_scope() as stats:
        cached_object_read(repo, (sha,), "log", read)
        cached_object_read(repo, (sha,), "log", read)
    assert read.calls == 2
    assert stats.bypassed == 2


def test_a_history_variable_in_the_passed_env_bypasses_an_object_read(repo: Path) -> None:
    sha = _git(repo, "rev-parse", "main")
    read = _log_of(repo, sha)
    with git_read_cache_scope():
        cached_object_read(repo, (sha,), "log", read, env={"GIT_NO_REPLACE_OBJECTS": "1"})
        cached_object_read(repo, (sha,), "log", read, env={"GIT_NO_REPLACE_OBJECTS": "1"})
    assert read.calls == 2


def test_a_history_variable_does_not_bypass_a_ref_read(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_NO_REPLACE_OBJECTS", "1")
    read = _tip(repo, "refs/heads/main")
    with git_read_cache_scope():
        _read_tip(repo, read, "refs/heads/main")
        _read_tip(repo, read, "refs/heads/main")
    assert read.calls == 1
