"""Branch advance reads git paths as data (#5392): quoting, non-ASCII, arrows.

``git status --porcelain`` prints a path with a space or a non-ASCII byte
quoted (``!! "src/local data/"``) and a rename as ``old -> new``. The advance
used to compare that display text against ``ls-tree`` output, so a quoted
obstruction never matched and the resync overwrote the operator's file. These
tests drive :func:`advance_branch_ref` and :func:`reset_would_obstruct_untracked`
against real git with ``core.quotePath=true`` (git's default).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.git import destructive_guard
from specify_cli.git.destructive_guard import DestructiveOpRefused
from specify_cli.git.ref_advance import (
    RefAdvanceDirtyWorktreeError,
    RefAdvanceError,
    _dirty_entries,
    _target_tree_paths,
    advance_branch_ref,
    reset_would_obstruct_untracked,
    restore_branch_ref,
)

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]

_BRANCH = "develop"
_LOCAL = "operator local bytes\n"
_INCOMING = "incoming tracked bytes\n"


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def _write(root: Path, rel: str, text: str) -> None:
    dest = root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-qb", _BRANCH)
    for key, value in (("user.email", "p@example.com"), ("user.name", "P"), ("commit.gpgsign", "false"), ("core.quotePath", "true")):
        _git(root, "config", key, value)
    _write(root, "src/README.md", "src\n")
    _write(root, ".gitignore", "src/local data/\nsrc/données/\n")
    _git(root, "add", "--", "src/README.md", ".gitignore")
    _git(root, "commit", "-qm", "base")
    return root


def _incoming_with(repo: Path, rel: str) -> str:
    """A commit on top of ``develop`` that force-adds tracked *rel*, without moving the checkout."""
    incoming = repo.parent / "incoming"
    _git(repo, "worktree", "add", "--detach", str(incoming), _BRANCH)
    _write(incoming, rel, _INCOMING)
    _git(incoming, "add", "-f", "--", rel)
    _git(incoming, "commit", "-qm", f"track {rel}")
    sha = _git(incoming, "rev-parse", "HEAD")
    _git(repo, "worktree", "remove", "--force", str(incoming))
    return sha


@pytest.mark.parametrize(
    ("rel", "shown"),
    [
        ("src/local data/notes.txt", '!! "src/local data/"'),
        ("src/données/notes.txt", '!! "src/donn\\303\\251es/"'),
    ],
)
def test_quoted_ignored_directory_blocks_the_advance(repo: Path, rel: str, shown: str) -> None:
    new_sha = _incoming_with(repo, rel)
    _write(repo, rel, _LOCAL)
    assert shown in _git(repo, "status", "--porcelain", "--ignored")
    before = _git(repo, "rev-parse", _BRANCH)

    with pytest.raises(RefAdvanceDirtyWorktreeError) as excinfo:
        advance_branch_ref(repo, _BRANCH, new_sha)

    directory = rel.rsplit("/", 1)[0]
    assert any(entry.startswith(f"!! {directory}/ (would be overwritten") for entry in excinfo.value.dirty_entries), excinfo.value.dirty_entries
    assert _git(repo, "rev-parse", _BRANCH) == before
    assert (repo / rel).read_text(encoding="utf-8") == _LOCAL
    assert reset_would_obstruct_untracked(repo, new_sha) is True


def test_quoted_untracked_file_blocks_the_advance(repo: Path) -> None:
    rel = "src/local data/notes.txt"
    _write(repo, ".gitignore", "")
    _git(repo, "commit", "-qam", "stop ignoring")
    new_sha = _incoming_with(repo, rel)
    _write(repo, rel, _LOCAL)

    with pytest.raises(RefAdvanceDirtyWorktreeError) as excinfo:
        advance_branch_ref(repo, _BRANCH, new_sha)

    assert any(entry.startswith("?? src/local data/") for entry in excinfo.value.dirty_entries), excinfo.value.dirty_entries
    assert (repo / rel).read_text(encoding="utf-8") == _LOCAL


def test_unrelated_quoted_ignored_file_does_not_block(repo: Path) -> None:
    new_sha = _incoming_with(repo, "src/other.txt")
    _write(repo, "src/local data/notes.txt", _LOCAL)

    advance_branch_ref(repo, _BRANCH, new_sha)

    assert _git(repo, "rev-parse", _BRANCH) == new_sha
    assert (repo / "src/local data/notes.txt").read_text(encoding="utf-8") == _LOCAL
    assert reset_would_obstruct_untracked(repo, "HEAD") is False


def test_file_named_like_a_rename_is_one_path(repo: Path) -> None:
    rel = "src/p -> q"
    _write(repo, rel, "tracked\n")
    _git(repo, "add", "--", rel)
    _git(repo, "commit", "-qm", "odd name")
    _write(repo, rel, "edited\n")

    dirty = _dirty_entries(repo, None, new_sha="HEAD", target_paths=frozenset())

    assert dirty == [" M src/p -> q"]


def test_residue_classifier_sees_the_real_path(repo: Path) -> None:
    rel = "src/local data/status.json"
    _write(repo, ".gitignore", "")
    _git(repo, "commit", "-qam", "stop ignoring")
    _write(repo, rel, "{}\n")
    seen: list[str] = []

    def is_residue(path: str) -> bool:
        seen.append(path)
        return True

    assert _dirty_entries(repo, None, new_sha="HEAD", target_paths=frozenset(), is_residue=is_residue, treat_untracked_as_dirty=True) == []
    # Untracked files are listed one by one, so the classifier sees the file, not a collapsed directory.
    assert seen == ["src/local data/status.json"]


def test_git_failure_is_a_ref_advance_error(tmp_path: Path) -> None:
    outside = tmp_path / "not-a-repo"
    outside.mkdir()
    with pytest.raises(RefAdvanceError, match="Could not inspect target tree"):
        _target_tree_paths(outside, "HEAD", None)
    with pytest.raises(RefAdvanceError, match="Could not inspect worktree state"):
        _dirty_entries(outside, None, new_sha="HEAD", target_paths=frozenset())
    assert reset_would_obstruct_untracked(outside) is True


def _stop_ignoring(repo: Path) -> None:
    _write(repo, ".gitignore", "")
    _git(repo, "commit", "-qam", "stop ignoring")


def _ignore(repo: Path, pattern: str) -> None:
    _write(repo, ".gitignore", f"{pattern}\n")
    _git(repo, "commit", "-qam", f"ignore {pattern}")


@pytest.mark.parametrize("ignored", [False, True], ids=["untracked", "ignored"])
def test_local_directory_named_with_an_arrow_blocks_when_target_has_that_path_as_a_file(repo: Path, ignored: bool) -> None:
    """#5400 ancestor half on a hostile name: local ``src/p -> q/notes.txt``, incoming FILE ``src/p -> q``.

    Passes wrongly if the name is split on `` -> `` (rename reading) or if only paths
    *inside* the local entry are compared, leaving the incoming-ancestor case unseen.
    """
    if ignored:
        _ignore(repo, "src/p -> q/")
    else:
        _stop_ignoring(repo)
    new_sha = _incoming_with(repo, "src/p -> q")
    _write(repo, "src/p -> q/notes.txt", _LOCAL)
    before = _git(repo, "rev-parse", _BRANCH)

    with pytest.raises(RefAdvanceDirtyWorktreeError):
        advance_branch_ref(repo, _BRANCH, new_sha)

    assert _git(repo, "rev-parse", _BRANCH) == before
    assert (repo / "src/p -> q/notes.txt").read_text(encoding="utf-8") == _LOCAL
    assert reset_would_obstruct_untracked(repo, new_sha) is True


def test_untracked_non_ascii_file_blocks_the_advance(repo: Path) -> None:
    """Git prints ``"src/caf\\303\\251.txt"``; passes wrongly if the quoted text is compared with ``ls-tree``'s real name."""
    rel = "src/café.txt"
    _stop_ignoring(repo)
    new_sha = _incoming_with(repo, rel)
    _write(repo, rel, _LOCAL)
    assert '"src/caf\\303\\251.txt"' in _git(repo, "status", "--porcelain")

    with pytest.raises(RefAdvanceDirtyWorktreeError):
        advance_branch_ref(repo, _BRANCH, new_sha)

    assert (repo / rel).read_text(encoding="utf-8") == _LOCAL
    assert reset_would_obstruct_untracked(repo, new_sha) is True


@pytest.mark.parametrize("ignored", [False, True], ids=["untracked", "ignored"])
def test_local_directory_with_no_overlapping_target_path_does_not_block(repo: Path, ignored: bool) -> None:
    """Positive control. Passes wrongly only for a guard that refuses every local entry (fails closed too far)."""
    if ignored:
        _ignore(repo, "src/local-data/")
    new_sha = _incoming_with(repo, "src/other.txt")
    _write(repo, "src/local-data/notes.txt", _LOCAL)

    advance_branch_ref(repo, _BRANCH, new_sha)

    assert _git(repo, "rev-parse", _BRANCH) == new_sha
    assert (repo / "src/local-data/notes.txt").read_text(encoding="utf-8") == _LOCAL
    assert reset_would_obstruct_untracked(repo, "HEAD") is False


def _quoted_collision(repo: Path) -> str:
    """Ignored ``src/local data/notes.txt`` locally; the returned commit tracks it."""
    rel = "src/local data/notes.txt"
    new_sha = _incoming_with(repo, rel)
    _write(repo, rel, _LOCAL)
    assert '!! "src/local data/"' in _git(repo, "status", "--porcelain", "--ignored")
    return new_sha


def test_assert_worktree_clean_refuses_a_quoted_collision(repo: Path) -> None:
    """Passes wrongly if the guard forwards git's quoted text instead of a real path to the tree comparison."""
    new_sha = _quoted_collision(repo)

    with pytest.raises(DestructiveOpRefused) as excinfo:
        destructive_guard.assert_worktree_clean(repo, new_sha=new_sha, is_residue=lambda _path: False)

    assert any(entry.startswith("!! src/local data/") for entry in excinfo.value.dirty_entries), excinfo.value.dirty_entries


def test_guarded_worktree_remove_refuses_a_quoted_untracked_file(repo: Path) -> None:
    """A removal discards any untracked file; passes wrongly if the quoted entry is dropped before the verdict."""
    _stop_ignoring(repo)
    linked = repo.parent / "linked"
    _git(repo, "worktree", "add", "-b", "lane", str(linked), _BRANCH)
    _write(linked, "src/local data/notes.txt", _LOCAL)

    with pytest.raises(DestructiveOpRefused):
        destructive_guard.guarded_worktree_remove(linked, retain=False, is_residue=lambda _path: False)

    assert (linked / "src/local data/notes.txt").read_text(encoding="utf-8") == _LOCAL
    retained = destructive_guard.guarded_worktree_remove(linked, retain=True, is_residue=lambda _path: False)
    assert retained.outcome is destructive_guard.RemoveOutcome.RETAINED_DIRTY
    assert linked.exists()


def test_restore_branch_ref_with_resync_refuses_a_quoted_collision(repo: Path) -> None:
    """Passes wrongly if the rollback path skips the dirty check, or runs it on text git quoted."""
    new_sha = _quoted_collision(repo)
    before = _git(repo, "rev-parse", _BRANCH)

    with pytest.raises(RefAdvanceDirtyWorktreeError):
        restore_branch_ref(repo, _BRANCH, new_sha, expected_current_sha=before, resync_checkouts=True)

    assert _git(repo, "rev-parse", _BRANCH) == before
    assert (repo / "src/local data/notes.txt").read_text(encoding="utf-8") == _LOCAL


def test_residue_inside_a_new_untracked_directory_is_still_residue(repo: Path) -> None:
    """With the default ``normal`` setting git collapses ``newdir/`` to one entry; the check must still see the file.

    Passes wrongly only if the listing stays collapsed, so the classifier sees ``newdir`` and the
    residue file is reported as dirty.
    """
    _git(repo, "config", "status.showUntrackedFiles", "normal")
    _write(repo, "newdir/status.json", "{}\n")
    assert "?? newdir/" in _git(repo, "status", "--porcelain").splitlines()
    seen: list[str] = []

    def is_residue(path: str) -> bool:
        seen.append(path)
        return path.endswith("status.json")

    assert _dirty_entries(repo, None, new_sha="HEAD", target_paths=frozenset(), is_residue=is_residue, treat_untracked_as_dirty=True) == []
    assert seen == ["newdir/status.json"]
