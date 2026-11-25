"""The #7747 landing proofs read git in batches, and give the same verdicts (#7848).

``spec-kitty consolidate`` started 582 git processes for one approved work package after the
#7747 landing proofs, against a ceiling of 500 (``tests/integration/test_7689_consolidate_git_spawn_ceiling.py``).
The authorship walk read a lane merge's version of every path it changed one ``ls-tree`` at a
time, plus one per merged-in parent, and both proofs walked the same commits again.

These tests pin the fix: a merge's paths are read in one tree read per commit, a second walk of the
same commits inside a run reuses the first, and the verdict is what reading one path at a time gave.

Real repositories; no CLI.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from kernel.git import tree_entry
from kernel.git.read_cache import git_read_cache_scope
from specify_cli.lanes import lane_tip

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    assert result.returncode == 0, f"git {' '.join(args)}: {result.stderr}"
    return result.stdout.strip()


def _write(cwd: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        path = cwd / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    _git(cwd, "add", "-A")


def _commit(cwd: Path, message: str, files: dict[str, str]) -> str:
    _write(cwd, files)
    _git(cwd, "commit", "-q", "-m", message)
    return _git(cwd, "rev-parse", "HEAD")


@contextmanager
def _git_spawns() -> Iterator[list[list[str]]]:
    """Record every ``git`` process the code under test starts."""
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


def _lane_with_sync_merge(root: Path, synced_paths: int) -> tuple[str, str]:
    """A lane that merged in a coordination branch which changed ``synced_paths`` files.

    The merge also resolves two paths itself (the lane's own authoring): ``x`` became a
    directory on the coordination branch and the merge adds ``x/own`` beside its ``x/y``, so
    the merge's tree for ``x`` is neither side's; and ``resolved.txt`` is neither side's copy.
    Returns ``(lane tip, landing ref)``.
    """
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    for key, value in (("user.email", "t@example.invalid"), ("user.name", "T"), ("commit.gpgsign", "false")):
        _git(root, "config", key, value)
    landing = _commit(root, "init", {"x": "file\n", "resolved.txt": "base\n", "README.md": "base\n"})
    _git(root, "branch", "coord")
    _git(root, "checkout", "-q", "-b", "lane")
    _commit(root, "lane work", {"src/lane.py": "lane\n"})
    _git(root, "checkout", "-q", "coord")
    _git(root, "rm", "-q", "x")
    _commit(root, "coord sync", {"x/y": "y\n", "resolved.txt": "coord\n", **{f"kitty-specs/m/f{i}.md": f"{i}\n" for i in range(synced_paths)}})
    _git(root, "checkout", "-q", "lane")
    _git(root, "merge", "-q", "--no-ff", "--no-commit", "coord")
    _write(root, {"x/own": "merge's own\n", "resolved.txt": "resolved\n"})
    _git(root, "commit", "-q", "-m", "merge coord")
    return _git(root, "rev-parse", "HEAD"), landing


def _authored_one_path_at_a_time(repo: Path, tip: str, landing: str) -> frozenset[str]:
    """The #7747 rule as first written: every version read alone with ``tree_entry``."""

    def blob(rev: str, path: str) -> str | None:
        entry = tree_entry(repo, rev, path)
        return entry.oid if entry is not None else None

    authored: set[str] = set()
    for line in _git(repo, "rev-list", "--first-parent", "--parents", tip, f"^{landing}").splitlines():
        commit, *parents = line.split()
        merged_in = parents[1:]
        taken = {sha for parent in merged_in for sha in _git(repo, "rev-list", "--first-parent", parent, f"^{landing}").splitlines()}
        if commit in taken:
            continue
        changed = _git(repo, "diff", "--name-only", "--no-renames", parents[0], commit).splitlines() if parents else []
        for path in changed:
            if merged_in and any(blob(parent, path) == blob(commit, path) for parent in merged_in):
                continue
            authored.add(path)
    return frozenset(authored)


def test_the_authorship_walk_gives_the_one_path_at_a_time_answer(tmp_path: Path) -> None:
    tip, landing = _lane_with_sync_merge(tmp_path / "repo", synced_paths=6)

    authored = lane_tip._authored_paths(tmp_path / "repo", tip, landing)

    assert authored == _authored_one_path_at_a_time(tmp_path / "repo", tip, landing)
    # The merge's own resolutions are authored; what it took whole from the coordination branch is not.
    assert {"src/lane.py", "x", "x/own", "resolved.txt"} <= authored
    assert "x/y" not in authored and "kitty-specs/m/f0.md" not in authored


def _walk_spawns(tmp_path: Path, synced_paths: int) -> int:
    root = tmp_path / f"repo-{synced_paths}"
    tip, landing = _lane_with_sync_merge(root, synced_paths)
    with _git_spawns() as spawned:
        lane_tip._authored_paths(root, tip, landing)
    return len(spawned)


def test_the_authorship_walk_reads_a_merge_in_one_tree_read_per_commit(tmp_path: Path) -> None:
    """The git processes a walk starts do not grow with the number of paths a merge changed."""
    assert _walk_spawns(tmp_path, synced_paths=3) == _walk_spawns(tmp_path, synced_paths=30)


def test_a_second_walk_of_the_same_commits_in_a_run_starts_no_git(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    tip, landing = _lane_with_sync_merge(root, synced_paths=4)
    with git_read_cache_scope():
        first = lane_tip._authored_paths(root, tip, landing)
        with _git_spawns() as spawned:
            again = lane_tip._authored_paths(root, tip, landing)
    assert again == first
    assert spawned == []


@pytest.mark.parametrize("scoped", [False, True], ids=["no-run-cache", "run-cache"])
def test_the_content_proof_reads_one_snapshot_of_a_named_landing_ref(tmp_path: Path, scoped: bool) -> None:
    """The landing ref is resolved once; the verdict matches the proof run against its commit id.

    A squash landing is not an ancestor of the lane, so the proof walks the whole lane.
    """
    root = tmp_path / "repo"
    tip, _landing = _lane_with_sync_merge(root, synced_paths=2)
    _git(root, "checkout", "-q", "main")
    _git(root, "merge", "-q", "--squash", "lane")
    _git(root, "commit", "-q", "-m", "squash land")
    landed = _git(root, "rev-parse", "HEAD")

    def run(proof: Callable[[], bool]) -> bool:
        if not scoped:
            return proof()
        with git_read_cache_scope():
            return proof()

    by_name = run(lambda: lane_tip.is_absorbed_but_for_mission_bookkeeping(root, tip, "refs/heads/main", "m"))
    by_id = run(lambda: lane_tip.is_absorbed_but_for_mission_bookkeeping(root, tip, landed, "m"))
    assert by_name is by_id is True
    with _git_spawns() as spawned:
        lane_tip.is_absorbed_but_for_mission_bookkeeping(root, tip, "refs/heads/main", "m")
    assert sum("refs/heads/main" in " ".join(argv) for argv in spawned) == 1
    assert lane_tip.is_absorbed_but_for_mission_bookkeeping(root, tip, "refs/heads/no-such-branch", "m") is False


#: A DAG (parent indexes, committer-date offset) where ``rev-list --first-parent c4 c2 ^c7`` prints
#: ``c2`` although ``c2`` is an ancestor of ``c7`` (through second parents) and each single-tip call
#: excludes it: the multi-tip walk's date-ordered stop differs (#7848 review LOW-1, git 2.43).
_SKEWED_DAG: tuple[tuple[tuple[int, ...], int], ...] = (
    ((), 26),
    ((0,), 11),
    ((1, 0), 19),
    ((2,), -10),
    ((0, 3), 15),
    ((1,), 6),
    ((0, 4), 4),
    ((6, 5), -21),
)


def _skewed_dag(root: Path) -> list[str]:
    root.mkdir()
    _git(root, "init", "-q")
    tree = subprocess.run(["git", "mktree"], cwd=root, input="", capture_output=True, text=True, check=True).stdout.strip()
    commits: list[str] = []
    for index, (parents, offset) in enumerate(_SKEWED_DAG):
        date = f"{1_700_000_000 + offset} +0000"
        env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@e", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@e"}
        env |= {"GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date, "PATH": os.environ["PATH"]}
        argv = ["git", "commit-tree", tree, *(arg for parent in parents for arg in ("-p", commits[parent])), "-m", str(index)]
        commits.append(subprocess.run(argv, cwd=root, env=env, capture_output=True, text=True, check=True).stdout.strip())
    return commits


def test_merged_in_lines_are_the_per_parent_union_within_the_lane_chain(tmp_path: Path) -> None:
    """The one multi-tip read keeps only commits of the lane's own chain, as the per-parent calls did."""
    root = tmp_path / "repo"
    commits = _skewed_dag(root)
    landing, merged_in = commits[7], [commits[4], commits[2]]
    union = {sha for parent in merged_in for sha in _git(root, "rev-list", "--first-parent", parent, f"^{landing}").splitlines()}
    chain = frozenset(commits) - set(_git(root, "rev-list", landing).splitlines())

    taken = lane_tip._merged_in_first_parent_lines(root, merged_in, landing, chain)

    assert taken == union & chain
    assert commits[2] not in taken  # an ancestor of the landing ref is never "taken" history
