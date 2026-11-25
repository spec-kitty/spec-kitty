"""Consolidation's git probes reuse object-id answers within a run (#7848).

``commit_parents``, ``resolve_commit``, ``commits_in_range``, the ancestry probes,
``changed_paths_of`` and ``path_state_at`` are functions of the objects they name. Inside the
run's git read cache (:func:`kernel.git.read_cache.git_read_cache_scope`) a repeat with full
object ids starts no git; a branch name is read every time; a failure is asked again.
Real repositories.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from kernel.git.read_cache import git_read_cache_scope
from specify_cli.consolidation import git_probes
from specify_cli.consolidation.git_probes import GitProbeError

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


@contextmanager
def _git_spawns() -> Iterator[list[list[str]]]:
    spawned: list[list[str]] = []
    real = subprocess.Popen.__init__

    def counting(self: Any, args: Any, *rest: Any, **kwargs: Any) -> None:
        argv = [str(a) for a in args] if isinstance(args, (list, tuple)) else [str(args)]
        if argv and Path(argv[0]).name.lower().startswith("git"):
            spawned.append(argv)
        real(self, args, *rest, **kwargs)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(subprocess.Popen, "__init__", counting)
        yield spawned


@pytest.fixture
def repo(tmp_path: Path) -> tuple[Path, str, str]:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    for key, value in (("user.email", "t@example.invalid"), ("user.name", "T"), ("commit.gpgsign", "false")):
        _git(root, "config", key, value)
    (root / "a.txt").write_text("a\n")
    _git(root, "add", "a.txt")
    _git(root, "commit", "-qm", "one")
    base = _git(root, "rev-parse", "HEAD")
    (root / "a.txt").write_text("b\n")
    _git(root, "commit", "-qam", "two")
    return root, base, _git(root, "rev-parse", "HEAD")


def _probes(base: str, tip: str) -> list[Callable[[Path], object]]:
    return [
        lambda root: git_probes.commit_parents(root, tip),
        lambda root: git_probes.resolve_commit(root, tip),
        lambda root: git_probes.commits_in_range(root, base, tip),
        lambda root: git_probes.is_ancestor_strict(root, base, tip),
        lambda root: git_probes.sha_reachable_from(root, base, tip),
        lambda root: git_probes.changed_paths_of(root, tip),
        lambda root: git_probes.path_state_at(root, tip, "a.txt"),
    ]


def test_an_object_id_probe_repeated_in_a_run_starts_no_git(repo: tuple[Path, str, str]) -> None:
    root, base, tip = repo
    with git_read_cache_scope():
        first = [probe(root) for probe in _probes(base, tip)]
        _git(root, "commit", "-q", "--allow-empty", "-m", "three")  # moving a branch changes no object
        with _git_spawns() as spawned:
            again = [probe(root) for probe in _probes(base, tip)]
    assert again == first
    assert spawned == []
    assert first[0] == [base] and first[2] == [tip] and first[3] is True and first[4] is True


def test_the_ancestry_probes_share_one_answer(repo: tuple[Path, str, str]) -> None:
    root, base, tip = repo
    with git_read_cache_scope():
        assert git_probes.is_ancestor_strict(root, tip, base) is False
        with _git_spawns() as spawned:
            assert git_probes.sha_reachable_from(root, tip, base) is False
    assert spawned == []


def test_a_branch_name_is_read_every_time(repo: tuple[Path, str, str]) -> None:
    root, base, _tip = repo
    with git_read_cache_scope():
        assert git_probes.resolve_commit(root, "main") == _git(root, "rev-parse", "main")
        _git(root, "commit", "-q", "--allow-empty", "-m", "three")
        assert git_probes.resolve_commit(root, "main") == _git(root, "rev-parse", "main")
        with _git_spawns() as spawned:
            git_probes.commits_in_range(root, base, "main")
            git_probes.sha_reachable_from(root, base, "main")
    assert len(spawned) == 2


def test_a_failed_probe_is_asked_again(repo: tuple[Path, str, str]) -> None:
    root, _base, tip = repo
    absent = "0" * 40
    with git_read_cache_scope(), _git_spawns() as spawned:
        for _ in range(2):
            with pytest.raises(GitProbeError):
                git_probes.commit_parents(root, absent)
            with pytest.raises(GitProbeError):
                git_probes.is_ancestor_strict(root, absent, tip)
            assert git_probes.sha_reachable_from(root, absent, tip) is False
    assert len(spawned) == 6
