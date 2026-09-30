"""#5400 — keep ignored descendants when a commit replaces their directory with a file.

``advance_branch_ref`` refuses an untracked or ignored path that is a target
leaf, or a directory that contains one, before it moves the ref. It did not
refuse the other containment direction: a local file living *under* a target
path. That is the shape of a tracked directory replaced by a tracked file
(``src/store/default.txt`` becomes ``src/store``) while an ignored
``src/store/local.txt`` still sits in the checkout. ``git reset --hard``
deletes those bytes. These tests drive the real git binary.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.git.ref_advance import (
    RefAdvanceDirtyWorktreeError,
    _path_obstructs_target_tree,
    advance_branch_ref,
    reset_would_obstruct_untracked,
)

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]

_BRANCH = "develop"
_PARENT = "tracked parent\n"
_KEEP = "keep\n"
_LOCAL = "operator local bytes\n"
_COLLAPSED = "collapsed\n"


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise AssertionError(f"git {' '.join(args)} failed ({result.returncode}): {detail}")
    return result.stdout.strip()


def _git_rc(cwd: Path, *args: str) -> int:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode


def _write(root: Path, rel: str, text: str) -> None:
    dest = root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-qb", _BRANCH)
    _git(path, "config", "user.email", "obstruction@example.com")
    _git(path, "config", "user.name", "Obstruction Test")
    _git(path, "config", "commit.gpgsign", "false")


def _commit(repo: Path, paths: list[str], message: str) -> str:
    _git(repo, "add", "--", *paths)
    _git(repo, "commit", "-qm", message)
    return _git(repo, "rev-parse", "HEAD")


def _commit_in_detached(repo: Path, mutate) -> str:
    """Commit *mutate(detached)* on top of ``develop`` without moving the checkout."""
    incoming = repo.parent / "incoming"
    _git(repo, "worktree", "add", "--detach", str(incoming), _BRANCH)
    mutate(incoming)
    sha = _git(incoming, "rev-parse", "HEAD")
    _git(repo, "worktree", "remove", "--force", str(incoming))
    return sha


def _collapse_store_directory(repo: Path) -> str:
    """Replace tracked ``src/store/`` with tracked file ``src/store``."""

    def mutate(incoming: Path) -> None:
        _git(incoming, "rm", "-qr", "--", "src/store")
        _write(incoming, "src/store", _COLLAPSED)
        _commit(incoming, ["src/store"], "replace store directory with a file")

    return _commit_in_detached(repo, mutate)


def _seed_store_directory(repo: Path, *, ignore: str | None = None) -> None:
    """Commit a tracked ``src/store/`` directory, including a nested tracked file."""
    paths = ["src/store/default.txt", "src/store/nested/deeper/keep.txt"]
    _write(repo, "src/store/default.txt", _PARENT)
    _write(repo, "src/store/nested/deeper/keep.txt", _KEEP)
    if ignore is not None:
        _write(repo, ".gitignore", ignore if ignore.endswith("\n") else f"{ignore}\n")
        paths.append(".gitignore")
    _commit(repo, paths, "track store directory")


class _CheckoutState:
    def __init__(self, repo: Path) -> None:
        self.ref = _git(repo, "rev-parse", f"refs/heads/{_BRANCH}")
        self.head = _git(repo, "rev-parse", "HEAD")
        self.index = _git(repo, "write-tree")

    def assert_unchanged(self, repo: Path, *, files: dict[str, str]) -> None:
        assert _git(repo, "rev-parse", f"refs/heads/{_BRANCH}") == self.ref
        assert _git(repo, "rev-parse", "HEAD") == self.head
        assert _git(repo, "write-tree") == self.index
        assert _git_rc(repo, "diff", "--cached", "--quiet") == 0
        assert _git_rc(repo, "diff", "--quiet") == 0
        for rel, text in files.items():
            assert (repo / rel).read_text(encoding="utf-8") == text


def _refuse(repo: Path, new_sha: str) -> RefAdvanceDirtyWorktreeError:
    with pytest.raises(RefAdvanceDirtyWorktreeError) as excinfo:
        advance_branch_ref(repo, _BRANCH, new_sha)
    return excinfo.value


@pytest.mark.regression
def test_5400_ignored_descendant_blocks_directory_to_file_replacement(tmp_path: Path) -> None:
    """P0: replacing ``src/store/`` with file ``src/store`` must not delete ignored ``local.txt``."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    _seed_store_directory(repo, ignore="src/store/local.txt")
    new_sha = _collapse_store_directory(repo)
    local = "src/store/local.txt"
    _write(repo, local, _LOCAL)
    before = _CheckoutState(repo)

    error = _refuse(repo, new_sha)

    assert local in str(error)
    assert any(local in entry for entry in error.dirty_entries)
    before.assert_unchanged(
        repo,
        files={
            "src/store/default.txt": _PARENT,
            "src/store/nested/deeper/keep.txt": _KEEP,
            local: _LOCAL,
        },
    )
    assert (repo / "src" / "store").is_dir()


@pytest.mark.regression
@pytest.mark.parametrize(
    ("ignored", "local_rel"),
    [
        pytest.param(True, "src/store/local.txt", id="ignored-child"),
        pytest.param(False, "src/store/local.txt", id="untracked-child"),
        pytest.param(True, "src/store/nested/deeper/local.txt", id="ignored-nested"),
        pytest.param(False, "src/store/nested/deeper/extra.txt", id="untracked-nested"),
    ],
)
def test_local_descendant_of_replaced_directory_refuses(tmp_path: Path, ignored: bool, local_rel: str) -> None:
    """Ancestor collision: ignored and untracked descendants, including more than one level."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    _seed_store_directory(repo, ignore=local_rel if ignored else None)
    new_sha = _collapse_store_directory(repo)
    _write(repo, local_rel, _LOCAL)
    before = _CheckoutState(repo)

    error = _refuse(repo, new_sha)

    assert local_rel in str(error)
    assert any(local_rel in entry for entry in error.dirty_entries)
    before.assert_unchanged(
        repo,
        files={
            "src/store/default.txt": _PARENT,
            "src/store/nested/deeper/keep.txt": _KEEP,
            local_rel: _LOCAL,
        },
    )


def test_exact_ignored_leaf_still_refuses(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    _write(repo, ".gitignore", "secret.env\n")
    _write(repo, "README.md", "init\n")
    _commit(repo, [".gitignore", "README.md"], "init")

    def mutate(incoming: Path) -> None:
        _write(incoming, "secret.env", "tracked secret\n")
        _git(incoming, "add", "-f", "--", "secret.env")
        _git(incoming, "commit", "-qm", "track ignored leaf")

    new_sha = _commit_in_detached(repo, mutate)
    _write(repo, "secret.env", "operator secret\n")
    before = _CheckoutState(repo)

    error = _refuse(repo, new_sha)

    assert "secret.env" in str(error)
    before.assert_unchanged(repo, files={"secret.env": "operator secret\n", "README.md": "init\n"})


def test_local_file_obstructing_target_descendant_still_refuses(tmp_path: Path) -> None:
    """A local file at ``src/store`` blocks a target leaf inside that directory.

    ``src/keep.txt`` is already tracked so git reports the obstructing file
    itself (``?? src/store``) instead of collapsing it into an untracked ``src/``.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    _write(repo, "src/keep.txt", "keep\n")
    _commit(repo, ["src/keep.txt"], "init")

    def mutate(incoming: Path) -> None:
        _write(incoming, "src/store/default.txt", _PARENT)
        _commit(incoming, ["src/store/default.txt"], "add store directory")

    new_sha = _commit_in_detached(repo, mutate)
    _write(repo, "src/store", "blocking file\n")
    before = _CheckoutState(repo)

    error = _refuse(repo, new_sha)

    assert any(entry.split(" (", 1)[0][3:].rstrip("/") == "src/store" for entry in error.dirty_entries)
    before.assert_unchanged(repo, files={"src/store": "blocking file\n", "src/keep.txt": "keep\n"})
    assert (repo / "src" / "store").is_file()


def test_ignored_directory_obstructing_target_descendant_still_refuses(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    _write(repo, ".gitignore", "vendor/\n")
    _write(repo, "README.md", "init\n")
    _commit(repo, [".gitignore", "README.md"], "init")

    def mutate(incoming: Path) -> None:
        _write(incoming, "vendor/lib.txt", "tracked lib\n")
        _git(incoming, "add", "-f", "--", "vendor/lib.txt")
        _git(incoming, "commit", "-qm", "track vendor leaf")

    new_sha = _commit_in_detached(repo, mutate)
    _write(repo, "vendor/notes.txt", "operator notes\n")
    before = _CheckoutState(repo)

    error = _refuse(repo, new_sha)

    assert "vendor" in str(error)
    before.assert_unchanged(repo, files={"vendor/notes.txt": "operator notes\n", "README.md": "init\n"})


def test_storehouse_does_not_obstruct_store_and_survives_advance(tmp_path: Path) -> None:
    """``store`` and ``storehouse`` share text and no slash-component boundary."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    _seed_store_directory(repo)
    new_sha = _collapse_store_directory(repo)
    _write(repo, "src/storehouse/notes.txt", "unrelated\n")

    advance_branch_ref(repo, _BRANCH, new_sha)

    assert _git(repo, "rev-parse", f"refs/heads/{_BRANCH}") == new_sha
    assert _git(repo, "rev-parse", "HEAD") == new_sha
    assert _git(repo, "write-tree") == _git(repo, "rev-parse", "HEAD^{tree}")
    assert (repo / "src" / "store").is_file()
    assert (repo / "src" / "store").read_text(encoding="utf-8") == _COLLAPSED
    assert not (repo / "src" / "store" / "default.txt").exists()
    assert (repo / "src" / "storehouse" / "notes.txt").read_text(encoding="utf-8") == "unrelated\n"


def test_common_prefix_file_names_do_not_obstruct(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    _write(repo, "README.md", "init\n")
    _commit(repo, ["README.md"], "init")

    def mutate(incoming: Path) -> None:
        _write(incoming, "store", "tracked store\n")
        _commit(incoming, ["store"], "add store file")

    new_sha = _commit_in_detached(repo, mutate)
    _write(repo, "storehouse", "unrelated file\n")

    advance_branch_ref(repo, _BRANCH, new_sha)

    assert _git(repo, "rev-parse", "HEAD") == new_sha
    assert (repo / "store").read_text(encoding="utf-8") == "tracked store\n"
    assert (repo / "storehouse").read_text(encoding="utf-8") == "unrelated file\n"


def test_ignored_sibling_survives_when_directory_remains_a_directory(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    _seed_store_directory(repo, ignore="src/store/local.txt")

    def mutate(incoming: Path) -> None:
        _write(incoming, "README.md", "advanced\n")
        _commit(incoming, ["README.md"], "advance readme")

    new_sha = _commit_in_detached(repo, mutate)
    _write(repo, "src/store/local.txt", _LOCAL)

    advance_branch_ref(repo, _BRANCH, new_sha)

    assert _git(repo, "rev-parse", f"refs/heads/{_BRANCH}") == new_sha
    assert _git(repo, "rev-parse", "HEAD") == new_sha
    assert (repo / "src" / "store" / "default.txt").read_text(encoding="utf-8") == _PARENT
    assert (repo / "src" / "store" / "local.txt").read_text(encoding="utf-8") == _LOCAL
    assert (repo / "src" / "store").is_dir()


def test_empty_path_and_empty_target_set_do_not_obstruct() -> None:
    assert _path_obstructs_target_tree("", {"src/store"}) is False
    assert _path_obstructs_target_tree("src/store/local.txt", set()) is False
    assert _path_obstructs_target_tree("", set()) is False
    assert _path_obstructs_target_tree("store", {"storehouse"}) is False
    assert _path_obstructs_target_tree("storehouse", {"store"}) is False
    assert _path_obstructs_target_tree("src/storehouse/local.txt", {"src/store"}) is False


def test_reset_would_obstruct_untracked_true_for_ancestor_collision_without_mutation(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    _seed_store_directory(repo, ignore="src/store/local.txt")
    new_sha = _collapse_store_directory(repo)
    _write(repo, "src/store/local.txt", _LOCAL)
    before = _CheckoutState(repo)

    assert reset_would_obstruct_untracked(repo, new_sha) is True

    before.assert_unchanged(
        repo,
        files={
            "src/store/default.txt": _PARENT,
            "src/store/local.txt": _LOCAL,
        },
    )
    assert _git(repo, "rev-parse", "HEAD") != new_sha


def test_reset_would_obstruct_untracked_false_for_unrelated_local_files(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    _seed_store_directory(repo, ignore="src/store/local.txt")

    def mutate(incoming: Path) -> None:
        _write(incoming, "README.md", "advanced\n")
        _commit(incoming, ["README.md"], "advance readme")

    new_sha = _commit_in_detached(repo, mutate)
    _write(repo, "src/store/local.txt", _LOCAL)
    _write(repo, "notes.txt", "unrelated\n")
    before = _CheckoutState(repo)

    assert reset_would_obstruct_untracked(repo, new_sha) is False

    before.assert_unchanged(
        repo,
        files={
            "src/store/default.txt": _PARENT,
            "src/store/local.txt": _LOCAL,
            "notes.txt": "unrelated\n",
        },
    )
