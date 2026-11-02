"""The ceiling-aware ancestor-walk contract (#7056).

Pins the walk every root authority in the stack shares: a start directory and each
parent in order, never above a ``GIT_CEILING_DIRECTORIES`` entry, with the ceiling read
on every call. The deliberate deviation from git's exact rule for a ceiling directory is
part of the contract, not an accident (see
``kitty-specs/ceiling-aware-ancestor-walk-01M6EJNY/contracts/kernel-ancestor-walk.md``).
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

from kernel.ancestor_walk import (
    GIT_CEILING_ENV,
    find_ancestor,
    git_ceiling_dirs,
    iter_ancestors,
)

_REPO_SRC = Path(__file__).resolve().parents[2] / "src"


def _ceiling_env(monkeypatch: pytest.MonkeyPatch, *entries: Path | str) -> None:
    monkeypatch.setenv(GIT_CEILING_ENV, os.pathsep.join(str(entry) for entry in entries))


def test_env_name_is_the_git_variable() -> None:
    assert GIT_CEILING_ENV == "GIT_CEILING_DIRECTORIES"


def test_no_ceiling_walks_to_the_filesystem_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(GIT_CEILING_ENV, raising=False)
    start = (tmp_path / "a" / "b").resolve()

    assert list(iter_ancestors(start)) == [start, *start.parents]
    assert list(iter_ancestors(start))[-1].parent == list(iter_ancestors(start))[-1]


def test_a_ceiling_ancestor_is_examined_and_the_walk_stops_after_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _ceiling_env(monkeypatch, tmp_path)
    start = (tmp_path / "a" / "b").resolve()

    walked = list(iter_ancestors(start))

    assert walked[-1] == tmp_path.resolve(), "the ceiling directory itself must be examined"
    assert tmp_path.resolve() not in walked[:-1]
    assert all(candidate == tmp_path.resolve() or tmp_path.resolve() in candidate.parents for candidate in walked)


def test_a_walk_that_starts_at_a_ceiling_directory_stops_immediately(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _ceiling_env(monkeypatch, tmp_path)

    assert list(iter_ancestors(tmp_path)) == [tmp_path.resolve()]


def test_the_nearest_ceiling_ancestor_bounds_the_walk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    outer = (tmp_path / "outer").resolve()
    inner = (outer / "inner").resolve()
    inner.mkdir(parents=True)
    _ceiling_env(monkeypatch, inner, outer)

    assert list(iter_ancestors(inner / "deep"))[-1] == inner


def test_relative_ceiling_entries_are_ignored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    relative = os.path.relpath(tmp_path, Path.cwd())
    _ceiling_env(monkeypatch, relative)
    start = (tmp_path / "a").resolve()

    assert list(iter_ancestors(start)) == [start, *start.parents]


def test_empty_ceiling_entries_are_ignored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(GIT_CEILING_ENV, f"{os.pathsep}{tmp_path}{os.pathsep}")

    assert git_ceiling_dirs() == frozenset({tmp_path.resolve()})
    assert list(iter_ancestors(tmp_path)) == [tmp_path.resolve()]


def test_a_ceiling_outside_the_start_path_has_no_effect(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    elsewhere = (tmp_path / "elsewhere").resolve()
    elsewhere.mkdir()
    start = (tmp_path / "work" / "deep").resolve()
    _ceiling_env(monkeypatch, elsewhere)

    assert list(iter_ancestors(start)) == [start, *start.parents]


def test_a_symlinked_ceiling_still_matches_the_resolved_walk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    real = (tmp_path / "real").resolve()
    (real / "work").mkdir(parents=True)
    link = tmp_path / "link"
    try:
        link.symlink_to(real, target_is_directory=True)
    except (OSError, NotImplementedError):  # pragma: no cover - platform without symlinks
        pytest.skip("platform cannot create directory symlinks")
    _ceiling_env(monkeypatch, link)

    assert list(iter_ancestors(link / "work"))[-1] == real


def test_the_ceiling_is_read_on_every_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(GIT_CEILING_ENV, raising=False)
    start = (tmp_path / "a" / "b").resolve()
    assert list(iter_ancestors(start))[-1] == start.parents[-1]

    _ceiling_env(monkeypatch, tmp_path)

    assert list(iter_ancestors(start))[-1] == tmp_path.resolve()


def test_git_ceiling_dirs_resolves_absolute_entries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(GIT_CEILING_ENV, str(tmp_path))

    ceilings = git_ceiling_dirs()

    assert ceilings == frozenset({tmp_path.resolve()})
    assert all(isinstance(entry, Path) and entry.is_absolute() for entry in ceilings)


def test_git_ceiling_dirs_accepts_an_explicit_environment(tmp_path: Path) -> None:
    ceilings = git_ceiling_dirs({GIT_CEILING_ENV: f"{tmp_path}{os.pathsep}relative/entry"})

    assert ceilings == frozenset({tmp_path.resolve()})


def test_find_ancestor_returns_the_first_accepted_candidate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(GIT_CEILING_ENV, raising=False)
    target = (tmp_path / "a").resolve()
    target.mkdir()
    start = (target / "b" / "c").resolve()
    start.mkdir(parents=True)

    assert find_ancestor(start, lambda candidate: (candidate / "b").is_dir()) == target


def test_find_ancestor_returns_none_when_nothing_is_accepted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(GIT_CEILING_ENV, raising=False)

    assert find_ancestor(tmp_path, lambda candidate: (candidate / "absent").exists()) is None


def test_find_ancestor_respects_the_ceiling(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    outer = (tmp_path / "outer").resolve()
    (outer / ".marker").write_text("x", encoding="utf-8")
    work = (outer / "work").resolve()
    work.mkdir()
    _ceiling_env(monkeypatch, tmp_path)

    # The marker is real, so the walk must find it when it is below the ceiling ...
    assert find_ancestor(work, lambda candidate: (candidate / ".marker").exists()) == outer

    # ... and must not see it once the ceiling sits above the start but below the marker.
    _ceiling_env(monkeypatch, work)
    assert find_ancestor(work, lambda candidate: (candidate / ".marker").exists()) is None


def test_find_ancestor_does_not_continue_above_a_ceiling_for_a_later_match(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "above-marker").write_text("x", encoding="utf-8")
    below = (tmp_path / "below").resolve()
    below.mkdir()
    _ceiling_env(monkeypatch, below)

    assert find_ancestor(below, lambda candidate: (candidate / "above-marker").exists()) is None


def test_the_module_imports_nothing_above_the_kernel_floor() -> None:
    module = _REPO_SRC / "kernel" / "ancestor_walk.py"
    tree = ast.parse(module.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.append(node.module)

    forbidden = ("specify_cli", "charter", "runtime", "mission_runtime", "glossary")
    violations = [name for name in imported if name.split(".")[0] in forbidden]
    assert violations == [], f"kernel.ancestor_walk must stay at the floor, found {violations}"
