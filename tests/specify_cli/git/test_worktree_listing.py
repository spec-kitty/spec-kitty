"""``_parse_worktree_porcelain`` (the private pure parser) / ``worktree_entries`` (#7173, WP01).

The parser cases use ``git worktree list --porcelain`` record text in the shape
git 2.43 prints it; the last test builds a real repository with linked,
detached and locked worktrees and reads it back through :func:`worktree_entries`.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from specify_cli.git.worktree_listing import WorktreeEntry, _parse_worktree_porcelain, worktree_entries
from kernel.git.runner import GitCommandError

_SHA_A = "a" * 40
_SHA_B = "b" * 40


def _entry(
    path: str,
    *,
    head: str | None = _SHA_A,
    branch: str | None = None,
    detached: bool = False,
    bare: bool = False,
    locked: bool = False,
    prunable: bool = False,
) -> WorktreeEntry:
    return WorktreeEntry(
        path=Path(path),
        head=head,
        branch=branch,
        detached=detached,
        bare=bare,
        locked=locked,
        prunable=prunable,
    )


@pytest.mark.fast
def test_main_and_linked_worktree_with_branches() -> None:
    text = f"worktree /repo\nHEAD {_SHA_A}\nbranch refs/heads/main\n\nworktree /repo/.worktrees/lane-a\nHEAD {_SHA_B}\nbranch refs/heads/kitty/mission-x-lane-a\n\n"
    assert _parse_worktree_porcelain(text) == (
        _entry("/repo", branch="main"),
        _entry("/repo/.worktrees/lane-a", head=_SHA_B, branch="kitty/mission-x-lane-a"),
    )


@pytest.mark.fast
def test_detached_entry_has_no_branch() -> None:
    text = f"worktree /repo/wt\nHEAD {_SHA_A}\ndetached\n"
    assert _parse_worktree_porcelain(text) == (_entry("/repo/wt", detached=True),)


@pytest.mark.fast
def test_bare_entry_has_no_head_and_no_branch() -> None:
    assert _parse_worktree_porcelain("worktree /srv/repo.git\nbare\n\n") == (_entry("/srv/repo.git", head=None, bare=True),)


@pytest.mark.parametrize("locked_line", ["locked", "locked reason with spaces"])
@pytest.mark.fast
def test_locked_with_and_without_reason(locked_line: str) -> None:
    text = f"worktree /repo/wt\nHEAD {_SHA_A}\nbranch refs/heads/b\n{locked_line}\n"
    assert _parse_worktree_porcelain(text) == (_entry("/repo/wt", branch="b", locked=True),)


@pytest.mark.parametrize("prunable_line", ["prunable", "prunable gitdir file points to non-existent location"])
@pytest.mark.fast
def test_prunable_with_and_without_reason(prunable_line: str) -> None:
    text = f"worktree /repo/gone\nHEAD {_SHA_A}\ndetached\n{prunable_line}\n\n"
    assert _parse_worktree_porcelain(text) == (_entry("/repo/gone", detached=True, prunable=True),)


@pytest.mark.fast
def test_path_with_spaces_is_kept_whole() -> None:
    text = f"worktree /home/me/my repo/.worktrees/a b\nHEAD {_SHA_A}\nbranch refs/heads/x\n"
    assert _parse_worktree_porcelain(text)[0].path == Path("/home/me/my repo/.worktrees/a b")


@pytest.mark.fast
def test_unknown_lines_are_ignored() -> None:
    text = f"worktree /repo\nHEAD {_SHA_A}\nfuture-attribute value\nbranch refs/heads/main\n"
    assert _parse_worktree_porcelain(text) == (_entry("/repo", branch="main"),)


@pytest.mark.fast
def test_record_without_worktree_line_is_skipped() -> None:
    text = f"HEAD {_SHA_B}\nbranch refs/heads/orphan\n\nworktree /repo\nHEAD {_SHA_A}\nbranch refs/heads/main\n"
    assert _parse_worktree_porcelain(text) == (_entry("/repo", branch="main"),)


@pytest.mark.fast
def test_non_heads_branch_ref_is_kept_verbatim() -> None:
    text = f"worktree /repo\nHEAD {_SHA_A}\nbranch refs/remotes/origin/x\n"
    assert _parse_worktree_porcelain(text)[0].branch == "refs/remotes/origin/x"


@pytest.mark.parametrize("text", ["", "\n", "\n\n"])
@pytest.mark.fast
def test_empty_input_is_empty(text: str) -> None:
    assert _parse_worktree_porcelain(text) == ()


# ---------------------------------------------------------------------------
# Real git
# ---------------------------------------------------------------------------


def _env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_AUTHOR_NAME="t",
        GIT_AUTHOR_EMAIL="t@example.invalid",
        GIT_COMMITTER_NAME="t",
        GIT_COMMITTER_EMAIL="t@example.invalid",
    )
    return env


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, env=_env(), check=True, capture_output=True, text=True).stdout.strip()


@pytest.mark.git_repo
def test_worktree_entries_reads_a_real_repository(tmp_path: Path) -> None:
    repo = tmp_path / "main repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "init")
    head = _git(repo, "rev-parse", "HEAD")
    linked = tmp_path / "linked wt"
    detached = tmp_path / "detached"
    _git(repo, "worktree", "add", "-q", "-b", "feature/x", str(linked))
    _git(repo, "worktree", "add", "-q", "--detach", str(detached))
    _git(repo, "worktree", "lock", "--reason", "kept for test", str(detached))

    entries = worktree_entries(repo, env=_env())

    seen = [(entry.path.resolve(), entry.branch, entry.detached, entry.locked) for entry in entries]
    # The main worktree comes first; git orders the linked ones by their admin-dir name.
    assert seen[0] == (repo.resolve(), "main", False, False)
    assert sorted(seen[1:], key=str) == sorted(
        [
            (linked.resolve(), "feature/x", False, False),
            (detached.resolve(), None, True, True),
        ],
        key=str,
    )
    assert {entry.head for entry in entries} == {head}
    assert not any(entry.bare or entry.prunable for entry in entries)


@pytest.mark.git_repo
def test_worktree_entries_raises_outside_a_repository(tmp_path: Path) -> None:
    with pytest.raises(GitCommandError):
        worktree_entries(tmp_path, env={**_env(), "GIT_CEILING_DIRECTORIES": str(tmp_path.parent)})
