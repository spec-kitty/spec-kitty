"""Unit tests for the #7626 merge-derivation probes and the reviewed-merge authorship helpers.

The behavior through the gate is pinned in ``test_reconciliation.py`` (the three-lane,
lane-plus-target and reviewed-merge cases and their negatives). These tests pin the
building blocks directly, including their fail-closed branches.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from kernel.git import MergeTreeResult
from specify_cli.consolidation import git_probes
from specify_cli.consolidation import reconciliation_authorship as authorship
from specify_cli.consolidation.git_probes import GitProbeError

pytestmark = pytest.mark.git_repo


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()


def _commit_file(repo: Path, branch: str, name: str, body: str) -> str:
    _git(repo, "checkout", "-q", branch)
    (repo / name).write_text(body, encoding="utf-8")
    _git(repo, "add", name)
    _git(repo, "commit", "-qm", f"edit {name}")
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A base commit with ``f`` (three lines) and ``g`` (one line), on ``main``."""
    root = tmp_path / "repo"
    subprocess.run(["git", "init", "-qb", "main", str(root)], check=True)
    for key, value in (("user.email", "t@t.co"), ("user.name", "T"), ("commit.gpgsign", "false")):
        _git(root, "config", key, value)
    (root / "f").write_text("a\nb\nc\nd\ne\n", encoding="utf-8")
    (root / "g").write_text("x\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "base")
    for branch in ("one", "two", "three"):
        _git(root, "branch", branch)
    return root


def test_n_way_merge_blob_is_none_when_the_path_conflicts(repo: Path) -> None:
    one = _commit_file(repo, "one", "f", "ONE\nb\nc\nd\ne\n")
    two = _commit_file(repo, "two", "f", "TWO\nb\nc\nd\ne\n")
    assert git_probes.n_way_merge_blob(repo, [one, two], "f") is None


def test_n_way_merge_blob_ignores_a_conflict_on_another_path(repo: Path) -> None:
    """A conflict on ``g`` leaves ``f``'s clean merge in the written tree, at every step."""
    _commit_file(repo, "one", "g", "one\n")
    one = _commit_file(repo, "one", "f", "A\nb\nc\nd\ne\n")
    _commit_file(repo, "two", "g", "two\n")
    two = _commit_file(repo, "two", "f", "a\nb\nc\nd\nE\n")
    three = _commit_file(repo, "three", "f", "a\nb\nC\nd\ne\n")
    blob = git_probes.n_way_merge_blob(repo, [one, two, three], "f")
    assert blob is not None
    assert _git(repo, "cat-file", "-p", blob) == "A\nb\nC\nd\nE"
    assert git_probes.n_way_merge_blob(repo, [one, two, three], "g") is None


def test_n_way_merge_blob_trivial_inputs(repo: Path) -> None:
    one = _commit_file(repo, "one", "f", "A\nb\nc\nd\ne\n")
    assert git_probes.n_way_merge_blob(repo, [], "f") is None
    assert git_probes.n_way_merge_blob(repo, [one], "f") == _git(repo, "rev-parse", f"{one}:f")
    assert git_probes.n_way_merge_blob(repo, [one, "main"], "absent") is None


def test_n_way_merge_blob_raises_on_an_unresolvable_input(repo: Path) -> None:
    one = _commit_file(repo, "one", "f", "A\nb\nc\nd\ne\n")
    with pytest.raises(GitProbeError):
        git_probes.n_way_merge_blob(repo, [one, "deadbeef" * 5], "f")


def test_merge_tree_step_raises_when_git_prints_no_tree(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(git_probes, "merge_tree", lambda *_a, **_k: MergeTreeResult(tree="", conflicted=()))
    with pytest.raises(GitProbeError, match="no tree id"):
        git_probes._merge_tree_step(repo, "a", "b")


def test_synthetic_merge_commit_raises_on_a_git_error(repo: Path) -> None:
    with pytest.raises(GitProbeError, match="commit-tree"):
        git_probes._synthetic_merge_commit(repo, "deadbeef" * 5, ("main",))


def test_first_parent_changed_paths_lists_what_a_merge_brought_in(repo: Path) -> None:
    """A merge that took the second parent's blob verbatim lists that path (the combined diff omits it)."""
    _commit_file(repo, "two", "g", "two\n")
    _commit_file(repo, "one", "f", "A\nb\nc\nd\ne\n")
    _git(repo, "merge", "-q", "--no-ff", "--no-edit", "two")
    merge = _git(repo, "rev-parse", "HEAD")
    assert git_probes.first_parent_changed_paths(repo, merge) == ["g"]
    assert "g" not in git_probes.changed_paths_of(repo, merge)


def test_first_parent_changed_paths_raises_for_a_root_commit(repo: Path) -> None:
    root = _git(repo, "rev-list", "--max-parents=0", "HEAD")
    with pytest.raises(GitProbeError):
        git_probes.first_parent_changed_paths(repo, root)


def test_authoring_merges_requires_trusted_second_parents(repo: Path) -> None:
    """Only a merge whose every non-first parent a root reaches authors; a probe error or no roots authors nothing."""
    trusted_tip = _commit_file(repo, "two", "g", "two\n")
    _commit_file(repo, "three", "g", "three\n")
    lane_commit = _commit_file(repo, "one", "f", "A\nb\nc\nd\ne\n")
    _git(repo, "merge", "-q", "--no-ff", "--no-edit", "two")
    trusted_merge = _git(repo, "rev-parse", "HEAD")
    subprocess.run(["git", "-C", str(repo), "merge", "-q", "--no-ff", "--no-edit", "three"], capture_output=True, check=False)
    _git(repo, "checkout", "-q", "--theirs", "g")
    _git(repo, "add", "g")
    _git(repo, "commit", "-qm", "merge three")
    foreign_merge = _git(repo, "rev-parse", "HEAD")
    spine = [foreign_merge, trusted_merge, lane_commit, "deadbeef" * 5]

    assert authorship._authoring_merges(repo, spine, (trusted_tip,)) == frozenset({trusted_merge})
    assert authorship._authoring_merges(repo, spine, ()) == frozenset()


def test_final_authored_walk_reads_authoring_merges_by_first_parent_diff(repo: Path) -> None:
    trusted_tip = _commit_file(repo, "two", "g", "two\n")
    lane_commit = _commit_file(repo, "one", "f", "A\nb\nc\nd\ne\n")
    _git(repo, "merge", "-q", "--no-ff", "--no-edit", "two")
    merge = _git(repo, "rev-parse", "HEAD")
    g_blob = _git(repo, "rev-parse", f"{trusted_tip}:g")

    plain, _ = authorship._final_authored_walk(repo, [merge, lane_commit])
    widened, _ = authorship._final_authored_walk(repo, [merge, lane_commit], authoring_merges=frozenset({merge}))
    assert ("g", g_blob) not in plain
    assert ("g", g_blob) in widened
