"""Commit-id probes of the consolidation gate are read once per consolidate run (#7848).

The reconciliation claim and the approved-bound check ask the same questions about the same
commits by id (a commit's parents, a commit range, an ancestry test, a commit's existence). Inside
the run's git read cache scope each answer is read once; a ref name is always asked again, and a
git error is never kept.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from kernel.git.read_cache import git_read_cache_scope
from specify_cli.consolidation import git_probes
from specify_cli.consolidation.git_probes import GitProbeError, commit_parents, commits_in_range, resolve_commit, sha_reachable_from

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]

_REAL_POPEN = subprocess.Popen


class _GitSpawns:
    def __init__(self) -> None:
        self.count = 0

    def __call__(self, args: Any, *rest: Any, **kwargs: Any) -> Any:
        argv = args if isinstance(args, (list, tuple)) else [args]
        if argv and Path(str(argv[0])).name.startswith("git"):
            self.count += 1
        return _REAL_POPEN(args, *rest, **kwargs)


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
    for text in ("a\n", "b\n"):
        (root / "a.txt").write_text(text)
        _git(root, "add", "a.txt")
        _git(root, "commit", "-qm", text.strip())
    return root


@pytest.fixture
def spawns() -> Iterator[_GitSpawns]:
    counter = _GitSpawns()
    with mock.patch.object(subprocess, "Popen", counter):
        yield counter


def _twice(spawns: _GitSpawns, read: Any) -> int:
    with git_read_cache_scope():
        before = spawns.count
        first = read()
        second = read()
    assert first == second
    return spawns.count - before


def test_commit_id_probes_are_read_once_per_run(repo: Path, spawns: _GitSpawns) -> None:
    one = _git(repo, "rev-parse", "main~1")
    two = _git(repo, "rev-parse", "main")
    assert _twice(spawns, lambda: commit_parents(repo, two)) == 1
    assert _twice(spawns, lambda: resolve_commit(repo, two)) == 1
    assert _twice(spawns, lambda: commits_in_range(repo, one, two)) == 1
    assert _twice(spawns, lambda: sha_reachable_from(repo, one, two)) == 1


def test_the_cached_answers_are_gits_answers(repo: Path) -> None:
    one = _git(repo, "rev-parse", "main~1")
    two = _git(repo, "rev-parse", "main")
    with git_read_cache_scope():
        for _ in range(2):
            assert commit_parents(repo, two) == [one]
            assert resolve_commit(repo, two) == two
            assert commits_in_range(repo, one, two) == [two]
            assert sha_reachable_from(repo, one, two)
            assert not sha_reachable_from(repo, two, one)


def test_a_ref_name_is_asked_again(repo: Path, spawns: _GitSpawns) -> None:
    one = _git(repo, "rev-parse", "main~1")
    assert _twice(spawns, lambda: resolve_commit(repo, "main")) == 2
    assert _twice(spawns, lambda: commits_in_range(repo, one, "main")) == 2
    assert _twice(spawns, lambda: sha_reachable_from(repo, one, "main")) == 2


def test_a_ref_name_moving_inside_the_run_is_seen(repo: Path) -> None:
    with git_read_cache_scope():
        before = resolve_commit(repo, "main")
        (repo / "a.txt").write_text("c\n")
        _git(repo, "commit", "-qam", "c")
        assert resolve_commit(repo, "main") != before


def test_a_git_error_is_never_kept(repo: Path, spawns: _GitSpawns) -> None:
    missing = "0" * 40
    with git_read_cache_scope():
        before = spawns.count
        for _ in range(2):
            with pytest.raises(GitProbeError):
                commit_parents(repo, missing)
            with pytest.raises(GitProbeError):
                commits_in_range(repo, missing, missing)
            assert not sha_reachable_from(repo, missing, missing)
    assert spawns.count - before == 6


def test_outside_a_run_every_probe_asks_git(repo: Path, spawns: _GitSpawns) -> None:
    two = _git(repo, "rev-parse", "main")
    before = spawns.count
    commit_parents(repo, two)
    commit_parents(repo, two)
    assert spawns.count - before == 2


def test_the_probes_keep_their_seam(repo: Path) -> None:
    """A probe still reads through ``run_command`` (the seam other tests patch)."""
    two = _git(repo, "rev-parse", "main")
    with mock.patch.object(git_probes, "run_command", return_value=(0, f"{two}\n", "")) as run:
        assert commit_parents(repo, two) == []
    run.assert_called_once()
