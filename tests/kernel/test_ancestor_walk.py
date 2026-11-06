"""The ceiling-aware ancestor-walk contract (#7056).

Pins the walk every root authority in the stack shares: a start directory and each
parent in order, never above a ``GIT_CEILING_DIRECTORIES`` entry, with the ceiling read
on every call. The deliberate deviation from git's exact rule for a ceiling directory is
part of the contract, not an accident (see the ``kernel.ancestor_walk`` module docstring).
"""

from __future__ import annotations

import errno
import os
from pathlib import Path

import pytest

from kernel.ancestor_walk import (
    GIT_CEILING_ENV,
    find_ancestor,
    git_ceiling_dirs,
    iter_ancestors,
)


def _ceiling_env(monkeypatch: pytest.MonkeyPatch, *entries: Path | str) -> None:
    monkeypatch.setenv(GIT_CEILING_ENV, os.pathsep.join(str(entry) for entry in entries))


def test_no_ceiling_walks_to_the_filesystem_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(GIT_CEILING_ENV, raising=False)
    start = (tmp_path / "a" / "b").resolve()

    assert list(iter_ancestors(start)) == [start, *start.parents]


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


@pytest.mark.parametrize("looping_child", [False, True], ids=["healthy", "looping-child"])
def test_a_symlinked_ceiling_still_matches_the_resolved_walk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, looping_child: bool) -> None:
    real = (tmp_path / "real").resolve()
    (real / "work").mkdir(parents=True)
    link = tmp_path / "link"
    try:
        link.symlink_to(real, target_is_directory=True)
    except (OSError, NotImplementedError):  # pragma: no cover - platform without symlinks
        pytest.skip("platform cannot create directory symlinks")
    start = link / "work"
    if looping_child:
        # A real symlink loop: the start cannot be resolved, so the walk falls back to its
        # lexical path, where the ceiling is reachable only through the alias.
        (real / "work" / "loop").symlink_to(Path("loop"))
        start = start / "loop" / "deep"
    _ceiling_env(monkeypatch, link)

    walked = list(iter_ancestors(start))

    assert walked[-1] == (link if looping_child else real), "the walk ends at its one ceiling identity"
    if looping_child:
        (tmp_path / "above-ceiling").write_text("x", encoding="utf-8")
        assert find_ancestor(start, lambda candidate: (candidate / "above-ceiling").exists()) is None


def test_the_ceiling_is_read_on_every_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(GIT_CEILING_ENV, raising=False)
    start = (tmp_path / "a" / "b").resolve()
    assert list(iter_ancestors(start))[-1] == start.parents[-1]

    _ceiling_env(monkeypatch, tmp_path)

    assert list(iter_ancestors(start))[-1] == tmp_path.resolve()


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
    outer.mkdir()
    (outer / ".marker").write_text("x", encoding="utf-8")
    work = (outer / "work").resolve()
    work.mkdir()
    _ceiling_env(monkeypatch, tmp_path)

    # The marker is real, so the walk must find it when it is below the ceiling ...
    assert find_ancestor(work, lambda candidate: (candidate / ".marker").exists()) == outer

    # ... and must not see it once the ceiling sits above the start but below the marker.
    _ceiling_env(monkeypatch, work)
    assert find_ancestor(work, lambda candidate: (candidate / ".marker").exists()) is None


@pytest.mark.parametrize("error", [OSError(errno.ELOOP, "Too many levels of symbolic links"), PermissionError(13, "Permission denied")])
def test_a_start_that_cannot_be_resolved_is_walked_as_written(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
    """A resolve failure never escapes the walk: it continues lexically, still bounded by the ceiling."""
    start = tmp_path / "a" / "b"
    real_resolve = Path.resolve

    def failing(self: Path, strict: bool = False) -> Path:
        if self == start:
            raise error
        return real_resolve(self, strict=strict)

    monkeypatch.setattr(Path, "resolve", failing)
    _ceiling_env(monkeypatch, tmp_path)

    assert list(iter_ancestors(start)) == [start, tmp_path / "a", tmp_path]


def test_a_ceiling_entry_that_cannot_be_resolved_is_kept_as_written(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Dropping it would widen the walk; keeping it unresolved can only stop the walk earlier."""
    ceiling = tmp_path / "ceiling"
    real_resolve = Path.resolve

    def failing(self: Path, strict: bool = False) -> Path:
        if self == ceiling:
            raise OSError(errno.ELOOP, "Too many levels of symbolic links")
        return real_resolve(self, strict=strict)

    monkeypatch.setattr(Path, "resolve", failing)

    assert git_ceiling_dirs({GIT_CEILING_ENV: str(ceiling)}) == frozenset({ceiling})
