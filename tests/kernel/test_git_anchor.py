"""The one ``.git`` classifier: repository, residue or unknown (#7262, operator ruling 2026-11-06).

Every class of the ruling is pinned here on real directory shapes, with the filesystem-error
cases injected at the read seam so the verdict is the same for every uid (#5622). The consumer
contract (refuse on unknown, never mint over a repository) is pinned at the identity entry
points in ``tests/specify_cli/upgrade/test_read_tracked_meta_6673.py`` and
``tests/specify_cli/migration/test_backfill_identity_tracked_absent_6673.py``.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from kernel.git_anchor import GIT_REDIRECT_ENV, AnchorKind, GitAnchor, classify_git_entry, find_git_anchor

pytestmark = pytest.mark.fast

_CEILING_ENV = "GIT_CEILING_DIRECTORIES"


def _git_dir(tmp_path: Path, *entries: str) -> Path:
    """A ``.git`` directory holding the named sub-directories."""
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    for entry in entries:
        (git_dir / entry).mkdir()
    return git_dir


@pytest.mark.parametrize(
    "entries",
    [(), ("hooks",), ("spec-kitty-locks",), ("hooks", "spec-kitty-locks")],
    ids=["empty", "hooks", "locks", "hooks-and-locks"],
)
def test_an_empty_or_hook_and_lock_only_directory_is_residue(tmp_path: Path, entries: tuple[str, ...]) -> None:
    assert classify_git_entry(_git_dir(tmp_path, *entries)).kind is AnchorKind.RESIDUE


def test_an_absent_entry_is_residue(tmp_path: Path) -> None:
    assert classify_git_entry(tmp_path / ".git").kind is AnchorKind.RESIDUE


def test_a_pointer_file_is_a_repository(tmp_path: Path) -> None:
    (tmp_path / ".git").write_text("gitdir: /nowhere/worktrees/x\n", encoding="utf-8")

    assert classify_git_entry(tmp_path / ".git").kind is AnchorKind.REPOSITORY


def test_a_directory_holding_head_is_a_repository(tmp_path: Path) -> None:
    git_dir = _git_dir(tmp_path, "hooks", "objects", "refs")
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")

    verdict = classify_git_entry(git_dir)

    assert verdict == GitAnchor(AnchorKind.REPOSITORY, git_dir, "a repository directory")


def _head_symlink_dangling(git_dir: Path) -> None:
    (git_dir / "HEAD").symlink_to(git_dir / "missing-target")


def _head_symlink_live(git_dir: Path) -> None:
    (git_dir / "real-head").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (git_dir / "HEAD").symlink_to(git_dir / "real-head")


def _head_directory(git_dir: Path) -> None:
    (git_dir / "HEAD").mkdir()


def _head_deleted(git_dir: Path) -> None:
    """A real repository that lost its ``HEAD``: objects and refs are still there (#7117)."""


@pytest.mark.parametrize(
    "damage",
    [_head_deleted, _head_symlink_dangling, _head_symlink_live, _head_directory],
    ids=["head-deleted", "head-dangling-symlink", "head-symlink", "head-directory"],
)
def test_a_repository_whose_head_is_lost_or_odd_is_unknown(tmp_path: Path, damage: Callable[[Path], None]) -> None:
    """#7117's safety case: a lost ``HEAD`` never turns a repository into residue."""
    git_dir = _git_dir(tmp_path, "hooks", "objects", "refs")
    damage(git_dir)

    assert classify_git_entry(git_dir).kind is AnchorKind.UNKNOWN


def test_a_directory_with_other_contents_and_no_head_is_unknown(tmp_path: Path) -> None:
    git_dir = _git_dir(tmp_path, "hooks")
    (git_dir / "config").write_text("[core]\n", encoding="utf-8")

    assert classify_git_entry(git_dir).kind is AnchorKind.UNKNOWN


@pytest.mark.parametrize("live", [False, True], ids=["dangling", "live"])
def test_a_git_symlink_is_unknown(tmp_path: Path, live: bool) -> None:
    target = tmp_path / "elsewhere"
    if live:
        (target / "objects").mkdir(parents=True)
        (target / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (tmp_path / ".git").symlink_to(target, target_is_directory=True)

    assert classify_git_entry(tmp_path / ".git").kind is AnchorKind.UNKNOWN


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="needs a POSIX fifo")
def test_an_entry_that_is_neither_file_nor_directory_is_unknown(tmp_path: Path) -> None:
    os.mkfifo(tmp_path / ".git")

    assert classify_git_entry(tmp_path / ".git").kind is AnchorKind.UNKNOWN


def test_an_entry_that_cannot_be_inspected_is_unknown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from tests._support.eacces import deny_path_method

    git_dir = _git_dir(tmp_path)
    deny_path_method(monkeypatch, "lstat", git_dir)

    assert classify_git_entry(git_dir).kind is AnchorKind.UNKNOWN


@pytest.mark.parametrize(
    "error",
    [PermissionError(13, "Permission denied"), FileNotFoundError(2, "No such file or directory")],
    ids=["unreadable", "disappeared"],
)
def test_a_directory_that_cannot_be_listed_is_unknown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: OSError) -> None:
    """Unreadable, or removed between the ``lstat`` and the listing: never residue."""
    git_dir = _git_dir(tmp_path)
    real_scandir = os.scandir

    def denied(path: Any) -> Any:
        if not isinstance(path, int) and Path(path) == git_dir:
            raise error
        return real_scandir(path)

    monkeypatch.setattr(os, "scandir", denied)

    assert classify_git_entry(git_dir).kind is AnchorKind.UNKNOWN


def test_the_walk_passes_residue_and_stops_at_the_first_repository(tmp_path: Path) -> None:
    outer = tmp_path / "outer"
    (outer / ".git").mkdir(parents=True)
    (outer / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    inner = outer / "project"
    (inner / ".git" / "hooks").mkdir(parents=True)
    start = inner / "kitty-specs" / "001-x"
    start.mkdir(parents=True)

    verdict = find_git_anchor(start, environ={})

    assert verdict is not None
    assert (verdict.kind, verdict.path) == (AnchorKind.REPOSITORY, (outer / ".git").resolve())


def test_the_walk_returns_none_when_only_residue_is_found(tmp_path: Path) -> None:
    (tmp_path / ".git" / "spec-kitty-locks").mkdir(parents=True)
    start = tmp_path / "a" / "b"
    start.mkdir(parents=True)

    assert find_git_anchor(start, environ={_CEILING_ENV: str(tmp_path)}) is None


def _repository_above_a_ceiling(tmp_path: Path) -> tuple[Path, Path, Path]:
    """``(repository_root, ceiling, start)`` with a real-shaped repository above the ceiling."""
    repository = tmp_path / "repo"
    (repository / ".git").mkdir(parents=True)
    (repository / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    ceiling = repository / "ceiling"
    start = ceiling / "work"
    start.mkdir(parents=True)
    return repository, ceiling, start


def test_the_walk_stops_at_the_git_ceiling(tmp_path: Path) -> None:
    """A repository above ``GIT_CEILING_DIRECTORIES`` is not this folder's (#7056)."""
    _repository, ceiling, start = _repository_above_a_ceiling(tmp_path)

    assert find_git_anchor(start, environ={_CEILING_ENV: str(ceiling)}) is None


def test_a_symlinked_ceiling_after_an_empty_entry_does_not_stop_the_walk(tmp_path: Path) -> None:
    """Git leaves entries after an empty entry unresolved, so a symlinked one never stops it.

    Stopping there anyway would read the repository git found as "nothing here" and let a
    caller mint over the identity it holds (#6673 NFR-002). Before the empty entry the same
    symlink is resolved and does stop the walk, as it stops git.
    """
    repository, ceiling, start = _repository_above_a_ceiling(tmp_path)
    link = tmp_path / "link-to-ceiling"
    link.symlink_to(ceiling, target_is_directory=True)

    after_empty = find_git_anchor(start, environ={_CEILING_ENV: f"{os.pathsep}{link}"})
    resolved = find_git_anchor(start, environ={_CEILING_ENV: str(link)})

    assert after_empty is not None and after_empty.path == (repository / ".git").resolve()
    assert resolved is None


@pytest.mark.parametrize("variable", GIT_REDIRECT_ENV)
def test_an_explicit_git_redirect_is_unknown(tmp_path: Path, variable: str) -> None:
    verdict = find_git_anchor(tmp_path, environ={variable: str(tmp_path / "store")})

    assert verdict is not None
    assert (verdict.kind, verdict.path) == (AnchorKind.UNKNOWN, None)
    assert variable in verdict.reason


def test_a_start_that_cannot_be_resolved_still_classifies_every_git_above_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A symlink loop or unreadable component never hides a repository above the folder."""
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    start = tmp_path / "loop"
    real_resolve = Path.resolve

    def looping(self: Path, strict: bool = False) -> Path:
        if self == start:
            raise RuntimeError("Symlink loop")
        return real_resolve(self, strict=strict)

    monkeypatch.setattr(Path, "resolve", looping)

    verdict = find_git_anchor(start, environ={})

    assert verdict is not None
    assert (verdict.kind, verdict.path) == (AnchorKind.REPOSITORY, tmp_path / ".git")
