"""Real-git round trips for :mod:`kernel.git` (the fast tier pins argv and parsers).

Every query must return the path that is on disk, whatever git would print for
it in display form: a space (which ``git status`` quotes), non-ASCII with
``core.quotePath=true``, a file literally named ``p -> q``, and a file named
``*`` that must never be read as a pathspec pattern.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from kernel.git import (
    GitCommandError,
    GitPath,
    changed_entries,
    changed_paths,
    commit_paths,
    index_entries,
    is_tracked,
    log_paths,
    numstat_entries,
    status_entries,
    tracked_paths,
    tree_entry,
    tree_paths,
)

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]

P = GitPath.parse


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def _write(repo: Path, rel: str, text: str = "x\n") -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-qb", "main")
    for key, value in (("user.email", "k@example.com"), ("user.name", "K"), ("commit.gpgsign", "false"), ("core.quotePath", "true")):
        _git(root, "config", key, value)
    for rel in ("a b/f", "é/g", "p -> q", "star/*", "star/plain", "src/store/default.txt"):
        _write(root, rel)
    _write(root, ".gitignore", "src/local data/\nsrc/store/local.txt\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "init")
    return root


def test_status_sees_real_paths_for_quoted_names(repo: Path) -> None:
    _write(repo, "a b/f", "changed\n")
    _write(repo, "src/local data/notes.txt")
    _write(repo, "src/store/local.txt")
    _write(repo, "new dir/é.txt")

    entries = {e.path: e for e in status_entries(repo, ignored=True)}

    assert entries[P("a b/f")].xy == " M"
    assert entries[P("new dir")].is_untracked and entries[P("new dir")].is_directory
    every_file = {e.path for e in status_entries(repo, untracked="all")}
    assert P("new dir/é.txt") in every_file
    ignored = {path for path, e in entries.items() if e.is_ignored}
    assert ignored == {P("src/local data"), P("src/store/local.txt")}
    assert entries[P("src/local data")].is_directory


def test_status_rename_carries_original_path(repo: Path) -> None:
    _git(repo, "mv", "p -> q", "r s")
    (entry,) = status_entries(repo)
    assert (entry.xy, entry.path, entry.orig_path) == ("R ", P("r s"), P("p -> q"))


def test_status_pathspec_is_literal(repo: Path) -> None:
    _write(repo, "star/plain", "changed\n")
    assert status_entries(repo, pathspecs=("star/*",)) == ()
    assert [e.path for e in status_entries(repo, pathspecs=("star/*",), glob=True)] == [P("star/plain")]


def test_tree_and_tracked_paths(repo: Path) -> None:
    expected = {P(".gitignore"), P("a b/f"), P("é/g"), P("p -> q"), P("star/*"), P("star/plain"), P("src/store/default.txt")}
    assert tree_paths(repo, "HEAD") == expected
    assert set(tracked_paths(repo)) == expected
    assert tracked_paths(repo, pathspecs=("star/*",)) == (P("star/*"),)
    assert {e.path for e in index_entries(repo)} == expected


def test_changed_commit_and_log_paths(repo: Path) -> None:
    base = _git(repo, "rev-parse", "HEAD")
    _write(repo, "é/g", "changed\n")
    _git(repo, "mv", "p -> q", "r s")
    assert changed_paths(repo) == (P("é/g"),)
    assert set(changed_paths(repo, cached=True)) == {P("p -> q"), P("r s")}
    (renamed,) = changed_entries(repo, cached=True, renames=True)
    assert (renamed.status[:1], renamed.orig_path, renamed.path) == ("R", P("p -> q"), P("r s"))
    _git(repo, "commit", "-qam", "change")
    assert set(commit_paths(repo, "HEAD")) == {P("é/g"), P("p -> q"), P("r s")}
    assert set(changed_paths(repo, base, "HEAD")) == {P("é/g"), P("p -> q"), P("r s")}
    assert set(log_paths(repo, f"{base}..HEAD")) == {P("é/g"), P("p -> q"), P("r s")}


def test_numstat_tree_entry_and_merge_first_parent(repo: Path) -> None:
    _write(repo, "a b/f", "one\ntwo\n")
    (entry,) = numstat_entries(repo)
    assert (entry.added, entry.deleted, entry.path) == (2, 1, P("a b/f"))
    blob = tree_entry(repo, "HEAD", "a b/f")
    assert blob is not None and blob.type == "blob"
    folder = tree_entry(repo, "HEAD", "a b")
    assert folder is not None and folder.type == "tree"
    assert tree_entry(repo, "HEAD", "missing") is None
    _git(repo, "checkout", "-qb", "side")
    _git(repo, "commit", "-qam", "side")
    _git(repo, "checkout", "-q", "main")
    _write(repo, "é/g", "main\n")
    _git(repo, "commit", "-qam", "main")
    _git(repo, "merge", "-q", "--no-edit", "side")
    assert commit_paths(repo, "HEAD") == ()
    assert commit_paths(repo, "HEAD", first_parent=True) == (P("a b/f"),)


def test_file_named_like_a_branch_is_not_a_revision(repo: Path) -> None:
    _write(repo, "main")
    _git(repo, "add", "main")
    _git(repo, "commit", "-qm", "file named main")
    assert P("main") in set(changed_paths(repo, "HEAD~1", "main"))
    assert P("main") in set(log_paths(repo, "main"))
    assert P("main") in set(commit_paths(repo, "main"))


def test_paths_are_repository_relative_from_a_subdirectory(repo: Path) -> None:
    sub = repo / "a b"
    _git(repo, "config", "diff.relative", "true")
    _write(repo, "é/g", "changed\n")
    assert P("a b/f") in tree_paths(sub, "HEAD")
    # ls-files keeps git's cwd scoping (only the subdirectory), but names stay repo-relative.
    assert tracked_paths(sub) == (P("a b/f"),)
    assert {e.path for e in index_entries(sub)} == {P("a b/f")}
    assert changed_paths(sub) == (P("é/g"),)
    entry = tree_entry(sub, "HEAD", "star/*")
    assert entry is not None and entry.path == P("star/*")


def test_is_tracked(repo: Path) -> None:
    assert is_tracked(repo, "a b/f")
    assert is_tracked(repo, "star/*")
    _write(repo, "untracked.txt")
    assert not is_tracked(repo, "untracked.txt")
    assert not is_tracked(repo, "missing")


def test_queries_fail_closed_outside_a_repository(tmp_path: Path) -> None:
    outside = tmp_path / "not-a-repo"
    outside.mkdir()
    with pytest.raises(GitCommandError):
        status_entries(outside)
    with pytest.raises(GitCommandError):
        is_tracked(outside, "x")
    with pytest.raises(GitCommandError):
        tree_paths(outside, "HEAD")
