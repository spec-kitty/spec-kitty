"""#7746 — a collapsed ignored directory is judged by the files in it, not by its name.

``git status --ignored`` reports a wholly ignored directory as one ``!! dir/``
entry. The repository-root checkout of a Mission whose planning moved to its
coordination branch keeps ``kitty-specs/<mission>/`` holding only the decisions
runtime lock (``decisions/index.json.lock``, excluded by spec-kitty's own
``info/exclude`` line, #5925 / #6628). That directory overlaps the incoming
``kitty-specs/<mission>/spec.md`` as a directory, so ``advance_branch_ref``
refused, although ``git reset --hard`` overwrites nothing in it.

The guard must still refuse when a file under a collapsed ignored directory
does collide with incoming tracked content (#5392 / #5400). These tests drive
the real git binary.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from kernel.git import GitPath
from specify_cli.coordination.coherence import is_decisions_runtime_lock
from specify_cli.git.ref_advance import (
    RefAdvanceDirtyWorktreeError,
    _dirty_verdicts,
    _path_obstructs_target_tree,
    _TargetOverlapIndex,
    _target_tree_paths,
    advance_branch_ref,
    reset_would_obstruct_untracked,
)
from tests.residue_predicate import residue_when

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]

_BRANCH = "develop"
_MISSION = "kitty-specs/demo-mission"
_LOCK = f"{_MISSION}/decisions/index.json.lock"
_LOCK_EXCLUDE = "**/kitty-specs/*/decisions/index.json.lock"
_LOCAL = "operator local bytes\n"


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {result.stderr.strip() or result.stdout.strip()}")
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
    for key, value in (("user.email", "p@example.com"), ("user.name", "P"), ("commit.gpgsign", "false")):
        _git(root, "config", key, value)
    _write(root, "README.md", "base\n")
    # Another Mission is tracked, so the collapsed entry is ``kitty-specs/<mission>/`` as in #7746.
    _write(root, "kitty-specs/other-mission/spec.md", "other\n")
    _git(root, "add", "--", "README.md", "kitty-specs/other-mission/spec.md")
    _git(root, "commit", "-qm", "base")
    exclude = Path(_git(root, "rev-parse", "--git-common-dir"))
    exclude = (exclude if exclude.is_absolute() else root / exclude) / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    with exclude.open("a", encoding="utf-8") as handle:
        handle.write(f"{_LOCK_EXCLUDE}\n")
    return root


def _incoming_with(repo: Path, *rels: str) -> str:
    """A commit on top of ``develop`` that force-adds tracked *rels*, without moving the checkout."""
    incoming = repo.parent / "incoming"
    _git(repo, "worktree", "add", "--detach", str(incoming), _BRANCH)
    for rel in rels:
        _write(incoming, rel, f"incoming {rel}\n")
    _git(incoming, "add", "-f", "--", *rels)
    _git(incoming, "commit", "-qm", "land the mission")
    sha = _git(incoming, "rev-parse", "HEAD")
    _git(repo, "worktree", "remove", "--force", str(incoming))
    return sha


def _plant_lock_only_mission_dir(repo: Path) -> None:
    lock = repo / _LOCK
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_bytes(b"")
    (repo / _MISSION / "research").mkdir()


@pytest.mark.regression
def test_lock_only_mission_directory_does_not_block_the_advance(repo: Path) -> None:
    """The #7746 shape: ``!! kitty-specs/<mission>/`` holds only the decisions lock."""
    new_sha = _incoming_with(repo, f"{_MISSION}/spec.md", f"{_MISSION}/decisions/index.json")
    _plant_lock_only_mission_dir(repo)
    assert f"!! {_MISSION}/" in _git(repo, "status", "--porcelain", "--ignored").splitlines()
    inode = (repo / _LOCK).stat().st_ino

    assert reset_would_obstruct_untracked(repo, new_sha) is False
    advance_branch_ref(repo, _BRANCH, new_sha)

    assert _git(repo, "rev-parse", _BRANCH) == new_sha
    assert (repo / f"{_MISSION}/spec.md").read_text(encoding="utf-8") == f"incoming {_MISSION}/spec.md\n"
    assert (repo / _LOCK).stat().st_ino == inode
    assert (repo / _LOCK).read_bytes() == b""


@pytest.mark.regression
def test_colliding_file_under_a_collapsed_ignored_directory_still_refuses(repo: Path) -> None:
    """Expansion must not open #5392: a colliding ignored file blocks, named by its collapsed directory."""
    rel = "build/out/notes.txt"
    _write(repo, ".gitignore", "build/\n")
    _git(repo, "add", "--", ".gitignore")
    _git(repo, "commit", "-qm", "ignore build")
    new_sha = _incoming_with(repo, rel)
    _write(repo, rel, _LOCAL)
    _write(repo, "build/out/unrelated.txt", _LOCAL)
    before = _git(repo, "rev-parse", _BRANCH)

    with pytest.raises(RefAdvanceDirtyWorktreeError) as excinfo:
        advance_branch_ref(repo, _BRANCH, new_sha)

    assert any(entry.startswith("!! build/ (would be overwritten") for entry in excinfo.value.dirty_entries), excinfo.value.dirty_entries
    assert _git(repo, "rev-parse", _BRANCH) == before
    assert (repo / rel).read_text(encoding="utf-8") == _LOCAL
    assert reset_would_obstruct_untracked(repo, new_sha) is True


@pytest.mark.regression
def test_lock_beside_a_colliding_file_still_refuses(repo: Path) -> None:
    """The lock exempts only itself: a real collision in the same Mission directory still blocks."""
    new_sha = _incoming_with(repo, f"{_MISSION}/spec.md")
    _plant_lock_only_mission_dir(repo)
    exclude = Path(_git(repo, "rev-parse", "--git-path", "info/exclude"))
    exclude = exclude if exclude.is_absolute() else repo / exclude
    with exclude.open("a", encoding="utf-8") as handle:
        handle.write(f"{_MISSION}/spec.md\n")
    _write(repo, f"{_MISSION}/spec.md", _LOCAL)

    with pytest.raises(RefAdvanceDirtyWorktreeError) as excinfo:
        advance_branch_ref(repo, _BRANCH, new_sha)

    assert any(entry.startswith(f"!! {_MISSION}/ (would be overwritten") for entry in excinfo.value.dirty_entries), excinfo.value.dirty_entries
    assert (repo / f"{_MISSION}/spec.md").read_text(encoding="utf-8") == _LOCAL


@pytest.mark.regression
def test_nested_repository_in_an_overlapping_ignored_directory_still_refuses(repo: Path) -> None:
    """Fail-closed: content git reports only as a directory keeps the directory-level verdict."""
    _write(repo, ".gitignore", "vendor/\n")
    _git(repo, "add", "--", ".gitignore")
    _git(repo, "commit", "-qm", "ignore vendor")
    new_sha = _incoming_with(repo, "vendor/lib/tracked.txt")
    nested = repo / "vendor" / "lib"
    nested.mkdir(parents=True)
    _git(nested, "init", "-q")
    _write(nested, "local.txt", _LOCAL)

    with pytest.raises(RefAdvanceDirtyWorktreeError):
        advance_branch_ref(repo, _BRANCH, new_sha)

    assert (nested / "local.txt").read_text(encoding="utf-8") == _LOCAL


_MANY_IGNORED = 400
_MANY_TRACKED = 2000


def test_expansion_cost_does_not_scale_with_files_times_target_paths(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Judging an expanded directory must not compare every ignored file with every target path.

    The guard used to test each ignored file against the whole target tree,
    ``O(files x tracked paths)``: 2,000 ignored files against 40,000 tracked
    paths took about 95 s. The bound is a count of pairwise path comparisons,
    not wall-clock time, so it cannot flake.
    """
    _write(repo, ".gitignore", "dist/\n")
    _git(repo, "add", "--", ".gitignore")
    _git(repo, "commit", "-qm", "ignore dist")
    new_sha = _incoming_with(repo, "dist/tracked.txt")
    for index in range(_MANY_IGNORED):
        _write(repo, f"dist/build/{index:04d}.o", "object\n")
    target_paths = frozenset(_target_tree_paths(repo, new_sha, None)) | frozenset(
        GitPath.parse(f"src/pkg{index // 100}/mod{index}.py") for index in range(_MANY_TRACKED)
    )
    comparisons = 0
    original = GitPath.overlaps

    def counting(self: GitPath, other: GitPath) -> bool:
        nonlocal comparisons
        comparisons += 1
        return original(self, other)

    monkeypatch.setattr(GitPath, "overlaps", counting)

    verdicts = _dirty_verdicts(repo, None, new_sha=new_sha, target_paths=target_paths)

    assert verdicts == []
    assert comparisons <= len(target_paths) + _MANY_IGNORED, comparisons


def test_injected_classifier_exempts_the_lock_even_where_it_would_collide(repo: Path) -> None:
    """The expanded lock path reaches the injected ``is_disposable`` (#6628), not only the overlap test.

    A target that tracks the lock path itself makes the lock a real obstruction,
    so only the classifier can exempt it: without one the advance refuses, with
    :func:`is_decisions_runtime_lock` injected it proceeds.
    """
    new_sha = _incoming_with(repo, f"{_MISSION}/spec.md", _LOCK)
    _plant_lock_only_mission_dir(repo)
    assert f"!! {_MISSION}/" in _git(repo, "status", "--porcelain", "--ignored").splitlines()

    with pytest.raises(RefAdvanceDirtyWorktreeError):
        advance_branch_ref(repo, _BRANCH, new_sha)

    advance_branch_ref(repo, _BRANCH, new_sha, context=residue_when(is_decisions_runtime_lock))

    assert _git(repo, "rev-parse", _BRANCH) == new_sha


_TARGETS = ("src/store", "src/local data/notes.txt", "kitty-specs/m/spec.md", "README.md")


@pytest.mark.parametrize(
    "local",
    [
        "src/store",  # exact
        "src/store/local.txt",  # under a target file (#5400)
        "src/local data",  # contains a target (#5392)
        "src",  # contains targets
        "src/storehouse",  # shares text, not a component
        "kitty-specs/m/decisions/index.json.lock",  # sibling of a target
        "kitty-specs/m",  # contains a target
        "docs",  # unrelated
        "README.md/x",  # under a target file
    ],
)
def test_overlap_index_matches_pairwise_overlaps(local: str) -> None:
    targets = frozenset(GitPath.parse(path) for path in _TARGETS)
    path = GitPath.parse(local)
    index = _TargetOverlapIndex(targets)

    assert index.overlaps(path) is any(path.overlaps(target) for target in targets)
    assert _path_obstructs_target_tree(path, index) is _path_obstructs_target_tree(path, targets)
    assert set(index) == targets and len(index) == len(targets) and GitPath.parse("README.md") in index
