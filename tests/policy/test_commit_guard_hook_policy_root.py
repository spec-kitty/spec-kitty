"""#5756: the commit guard must resolve its policy root from the real git
topology, not by joining ``.parent`` onto ``git rev-parse --git-common-dir``.

``_resolve_policy_root`` decides where ``load_policy_config`` looks for the
policy config. The old parent-join was right only for a plain repository
(common dir ``<repo>/.git``); it was wrong for every layout whose common dir
lives elsewhere:

- linked worktree — common dir is the MAIN repo's ``.git`` (its parent is the
  main repo root: correct by accident),
- submodule — common dir is ``<super>/.git/modules/<name>`` (its parent is
  ``.git/modules``: wrong),
- separate git dir — common dir is an operator-chosen directory (its parent is
  unrelated to the working tree: wrong).

The rule under test: when the common dir's own name is ``.git``, its parent is
the project root; otherwise the working-tree root itself is the policy root.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.policy.commit_guard_hook import _resolve_policy_root

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "seed.txt")
    _git(repo, "commit", "-q", "-m", "seed")


def test_plain_repository_policy_root_is_the_repo_root(tmp_path: Path) -> None:
    repo = tmp_path / "plain"
    _init_repo(repo)
    assert _resolve_policy_root(repo).resolve() == repo.resolve()


def test_linked_worktree_policy_root_is_the_main_repo_root(tmp_path: Path) -> None:
    main_repo = tmp_path / "main"
    _init_repo(main_repo)
    worktree = tmp_path / "wt"
    _git(main_repo, "worktree", "add", "-q", "-b", "topic", str(worktree))
    assert _resolve_policy_root(worktree).resolve() == main_repo.resolve()


def test_submodule_policy_root_is_the_submodule_worktree(tmp_path: Path) -> None:
    super_repo = tmp_path / "super"
    _init_repo(super_repo)
    sub_repo = tmp_path / "sub"
    _init_repo(sub_repo)
    _git(
        super_repo,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "add",
        "-q",
        "../sub",
        "subm",
    )
    _git(super_repo, "commit", "-q", "-m", "add submodule")
    sub_worktree = super_repo / "subm"
    assert _resolve_policy_root(sub_worktree).resolve() == sub_worktree.resolve()


def test_separate_git_dir_policy_root_is_the_worktree(tmp_path: Path) -> None:
    sep_git_dir = tmp_path / "elsewhere-sep"
    repo = tmp_path / "repo"
    _git(
        tmp_path,
        "init",
        "-q",
        "--separate-git-dir",
        str(sep_git_dir),
        str(repo),
    )
    assert _resolve_policy_root(repo).resolve() == repo.resolve()
