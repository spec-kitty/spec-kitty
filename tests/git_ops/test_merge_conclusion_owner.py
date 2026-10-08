"""The merge-conclusion owner against real git (#5443, FR-013, C-005).

Each test pins a git behaviour the owner relies on, or a refusal it adds,
through the outcome in the repository (commits, parents, subjects, the index),
never through the argv it builds.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from specify_cli.git.merge_conclusion import (
    FreshWorktree,
    MergeConclusionRefused,
    conclude_in_progress_op,
    mint_fresh_worktree,
    run_committing_op,
)

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]

BRANCH = "work"
SQUASH_SUBJECT = "feat(side): squash merge of mission"


def _git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    if check and result.returncode != 0:
        raise AssertionError(f"git {args} failed: {result.stderr}")
    return result


def _out(cwd: Path, *args: str) -> str:
    return _git(cwd, *args).stdout.strip()


@pytest.fixture(autouse=True)
def _hermetic_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for key in list(os.environ):
        if key.startswith(("GIT_", "SPEC_KITTY_")):
            monkeypatch.delenv(key)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("SPEC_KITTY_NO_UPGRADE_CHECK", "1")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "--template=", "-b", BRANCH)
    _git(r, "config", "user.email", "t@example.com")
    _git(r, "config", "user.name", "T")
    _git(r, "config", "commit.gpgsign", "false")
    (r / "shared.txt").write_text("base\n")
    _git(r, "add", "--", "shared.txt")
    _git(r, "commit", "-m", "init")
    return r


def _commit_file(repo: Path, name: str, text: str, message: str) -> str:
    (repo / name).write_text(text)
    _git(repo, "add", "--", name)
    _git(repo, "commit", "-m", message)
    return _out(repo, "rev-parse", "HEAD")


def _side_branch(repo: Path, name: str = "side.txt", text: str = "side\n") -> None:
    _git(repo, "checkout", "-q", "-b", "side")
    _commit_file(repo, name, text, "side work")
    _git(repo, "checkout", "-q", BRANCH)


def _conflicted_merge(repo: Path, merge_message: str) -> None:
    """Leave a conflicted ``merge --no-commit -m <merge_message> side`` in progress, resolved and staged."""
    _git(repo, "checkout", "-q", "-b", "side")
    _commit_file(repo, "shared.txt", "theirs\n", "side edit")
    _git(repo, "checkout", "-q", BRANCH)
    _commit_file(repo, "shared.txt", "ours\n", "work edit")
    assert _git(repo, "merge", "--no-commit", "--no-edit", "-m", merge_message, "side", check=False).returncode != 0
    (repo / "shared.txt").write_text("resolved\n")
    _git(repo, "add", "--", "shared.txt")


def _parents(repo: Path, rev: str = "HEAD") -> list[str]:
    return _out(repo, "rev-list", "--parents", "-n", "1", rev).split()[1:]


def _subject(repo: Path) -> str:
    return _out(repo, "log", "-1", "--format=%s")


def _count(repo: Path) -> int:
    return int(_out(repo, "rev-list", "--count", "HEAD"))


def _staged(repo: Path) -> set[str]:
    return set(_out(repo, "diff", "--cached", "--name-only").splitlines())


def _has_ref(repo: Path, ref: str) -> bool:
    return _git(repo, "rev-parse", "-q", "--verify", ref, check=False).returncode == 0


def _linked_worktree(repo: Path, tmp_path: Path, name: str = "wt") -> Path:
    wt = tmp_path / name
    _git(repo, "worktree", "add", "--detach", str(wt), BRANCH)
    return wt


def _break_signing(repo: Path) -> None:
    _git(repo, "config", "commit.gpgsign", "true")
    _git(repo, "config", "gpg.program", "/bin/false")


# 1 ---------------------------------------------------------------------------


def test_nothing_in_progress_is_refused_and_commits_nothing(repo: Path) -> None:
    (repo / "loose.txt").write_text("x\n")
    _git(repo, "add", "--", "loose.txt")
    before = _count(repo)
    with pytest.raises(MergeConclusionRefused, match="no merge, revert, cherry-pick or squash is in progress"):
        conclude_in_progress_op(repo, env=None)
    assert _count(repo) == before
    assert _staged(repo) == {"loose.txt"}


# 2 ---------------------------------------------------------------------------


def test_conclusion_keeps_the_merge_message_and_both_parents(repo: Path) -> None:
    _conflicted_merge(repo, "Merge side into work (given to git merge)")
    side_tip = _out(repo, "rev-parse", "side")

    result = conclude_in_progress_op(repo, env=None)

    assert result.returncode == 0, result.stderr
    assert _subject(repo) == "Merge side into work (given to git merge)"
    assert _parents(repo)[1] == side_tip
    assert len(_parents(repo)) == 2
    assert not _has_ref(repo, "MERGE_HEAD")


def test_explicit_message_replaces_the_merge_message(repo: Path) -> None:
    _conflicted_merge(repo, "the merge's own message")
    result = conclude_in_progress_op(repo, env=None, message="X")
    assert result.returncode == 0, result.stderr
    assert _subject(repo) == "X"
    assert len(_parents(repo)) == 2


def test_conflicted_revert_is_concluded(repo: Path) -> None:
    target = _commit_file(repo, "shared.txt", "one\n", "edit one")
    _commit_file(repo, "shared.txt", "two\n", "edit two")
    assert _git(repo, "revert", "--no-edit", target, check=False).returncode != 0
    (repo / "shared.txt").write_text("resolved\n")
    _git(repo, "add", "--", "shared.txt")

    result = conclude_in_progress_op(repo, env=None)

    assert result.returncode == 0, result.stderr
    assert _subject(repo) == 'Revert "edit one"'
    assert not _has_ref(repo, "REVERT_HEAD")


def test_conflicted_cherry_pick_is_concluded(repo: Path) -> None:
    _git(repo, "checkout", "-q", "-b", "side")
    picked = _commit_file(repo, "shared.txt", "theirs\n", "picked edit")
    _git(repo, "checkout", "-q", BRANCH)
    _commit_file(repo, "shared.txt", "ours\n", "work edit")
    assert _git(repo, "cherry-pick", picked, check=False).returncode != 0
    (repo / "shared.txt").write_text("resolved\n")
    _git(repo, "add", "--", "shared.txt")

    result = conclude_in_progress_op(repo, env=None)

    assert result.returncode == 0, result.stderr
    assert _subject(repo) == "picked edit"
    assert len(_parents(repo)) == 1
    assert not _has_ref(repo, "CHERRY_PICK_HEAD")


# 3 / 4 -----------------------------------------------------------------------


def test_squash_in_a_fresh_worktree_is_concluded(repo: Path, tmp_path: Path) -> None:
    _side_branch(repo)
    wt = _linked_worktree(repo, tmp_path)
    proof = mint_fresh_worktree(wt, None)
    base = _out(wt, "rev-parse", "HEAD")
    _git(wt, "merge", "--squash", "side")

    result = conclude_in_progress_op(wt, env=None, message=SQUASH_SUBJECT, fresh=proof)

    assert result.returncode == 0, result.stderr
    assert _subject(wt) == SQUASH_SUBJECT
    assert _parents(wt) == [base]
    assert _out(wt, "show", "HEAD:side.txt") == "side"


def test_squash_without_proof_is_refused(repo: Path, tmp_path: Path) -> None:
    _side_branch(repo)
    wt = _linked_worktree(repo, tmp_path)
    head = _out(wt, "rev-parse", "HEAD")
    _git(wt, "merge", "--squash", "side")
    squash_msg = Path(_out(wt, "rev-parse", "--path-format=absolute", "--git-path", "SQUASH_MSG"))

    with pytest.raises(MergeConclusionRefused, match="needs a FreshWorktree proof"):
        conclude_in_progress_op(wt, env=None, message=SQUASH_SUBJECT)

    assert squash_msg.exists()
    assert _out(wt, "rev-parse", "HEAD") == head


# 5 ---------------------------------------------------------------------------


def test_squash_proof_is_void_once_head_moves(repo: Path, tmp_path: Path) -> None:
    _side_branch(repo)
    wt = _linked_worktree(repo, tmp_path)
    proof = mint_fresh_worktree(wt, None)
    moved = _commit_file(wt, "extra.txt", "x\n", "moved HEAD")
    _git(wt, "merge", "--squash", "side")

    with pytest.raises(MergeConclusionRefused, match="HEAD moved"):
        conclude_in_progress_op(wt, env=None, message=SQUASH_SUBJECT, fresh=proof)

    assert _out(wt, "rev-parse", "HEAD") == moved


def test_squash_proof_from_another_worktree_is_refused(repo: Path, tmp_path: Path) -> None:
    _side_branch(repo)
    wt_a = _linked_worktree(repo, tmp_path, "wt-a")
    wt_b = _linked_worktree(repo, tmp_path, "wt-b")
    proof_a = mint_fresh_worktree(wt_a, None)
    head_b = _out(wt_b, "rev-parse", "HEAD")
    _git(wt_b, "merge", "--squash", "side")

    with pytest.raises(MergeConclusionRefused, match="minted for"):
        conclude_in_progress_op(wt_b, env=None, message=SQUASH_SUBJECT, fresh=proof_a)

    assert _out(wt_b, "rev-parse", "HEAD") == head_b


# 6 ---------------------------------------------------------------------------


def test_primary_checkout_is_never_fresh(repo: Path) -> None:
    _git(repo, "checkout", "-q", "--detach")
    with pytest.raises(MergeConclusionRefused, match="not a linked worktree"):
        mint_fresh_worktree(repo, None)


def test_worktree_on_a_branch_is_never_fresh(repo: Path, tmp_path: Path) -> None:
    wt = tmp_path / "attached"
    _git(repo, "worktree", "add", "-b", "attached", str(wt), BRANCH)
    with pytest.raises(MergeConclusionRefused, match="HEAD is on a branch"):
        mint_fresh_worktree(wt, None)


@pytest.mark.parametrize("rel", ["stray.txt", "shared.txt"], ids=["staged-new", "staged-edit"])
def test_worktree_with_a_staged_change_is_never_fresh(repo: Path, tmp_path: Path, rel: str) -> None:
    wt = _linked_worktree(repo, tmp_path)
    (wt / rel).write_text("operator work\n")
    _git(wt, "add", "--", rel)
    with pytest.raises(MergeConclusionRefused, match=f"index differs from HEAD: {rel}"):
        mint_fresh_worktree(wt, None)


def test_worktree_with_an_unmerged_index_is_never_fresh(repo: Path, tmp_path: Path) -> None:
    """A conflicted merge leaves ``UU`` entries: the index differs from HEAD, so no freshness proof (#5443 fold)."""
    _git(repo, "checkout", "-q", "-b", "side")
    _commit_file(repo, "shared.txt", "theirs\n", "side edit")
    _git(repo, "checkout", "-q", BRANCH)
    _commit_file(repo, "shared.txt", "ours\n", "work edit")
    wt = _linked_worktree(repo, tmp_path)
    assert _git(wt, "merge", "--no-commit", "--no-edit", "side", check=False).returncode != 0
    assert _out(wt, "status", "--porcelain", "--untracked-files=no") == "UU shared.txt"  # precondition: really unmerged
    with pytest.raises(MergeConclusionRefused, match="index differs from HEAD: shared.txt"):
        mint_fresh_worktree(wt, None)


def test_worktree_with_a_staged_deletion_is_never_fresh(repo: Path, tmp_path: Path) -> None:
    wt = _linked_worktree(repo, tmp_path)
    _git(wt, "rm", "-q", "--", "shared.txt")
    with pytest.raises(MergeConclusionRefused, match="index differs from HEAD: shared.txt"):
        mint_fresh_worktree(wt, None)


def test_untracked_and_unstaged_changes_do_not_void_freshness_nor_leak_into_the_squash(repo: Path, tmp_path: Path) -> None:
    """Only the index counts: ``merge --squash`` + ``commit -m`` commits staged content alone (#5443 WP05 fold)."""
    _side_branch(repo)
    wt = _linked_worktree(repo, tmp_path)
    (wt / ".env.local").write_text("SECRET=operator\n")
    (wt / "shared.txt").write_text("unstaged edit\n")
    proof = mint_fresh_worktree(wt, None)
    base = _out(wt, "rev-parse", "HEAD")
    _git(wt, "merge", "--squash", "side")

    result = conclude_in_progress_op(wt, env=None, message=SQUASH_SUBJECT, fresh=proof)

    assert result.returncode == 0, result.stderr
    assert _parents(wt) == [base]
    assert _out(wt, "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").splitlines() == ["side.txt"]
    assert _out(wt, "show", "HEAD:shared.txt") == "base"
    assert (wt / ".env.local").read_text() == "SECRET=operator\n"


def test_fresh_proof_records_the_worktree_head(repo: Path, tmp_path: Path) -> None:
    wt = _linked_worktree(repo, tmp_path)
    proof = mint_fresh_worktree(wt, None)
    assert isinstance(proof, FreshWorktree)
    assert proof.worktree == wt
    assert proof.head == _out(wt, "rev-parse", "HEAD")


def test_squash_keeps_a_stray_staged_file_which_is_why_the_proof_exists(repo: Path, tmp_path: Path) -> None:
    """Git fact 5: ``merge --squash`` accepts an unrelated staged file, so only a clean worktree may conclude one."""
    _side_branch(repo)
    wt = _linked_worktree(repo, tmp_path)
    (wt / "stray.txt").write_text("operator work\n")
    _git(wt, "add", "--", "stray.txt")
    assert _git(wt, "merge", "--squash", "side", check=False).returncode == 0
    assert {"side.txt", "stray.txt"} <= _staged(wt)


# 7 ---------------------------------------------------------------------------


def test_committing_merge_refuses_over_a_stray_staged_file(repo: Path) -> None:
    _side_branch(repo)
    _commit_file(repo, "mine.txt", "mine\n", "diverge")
    (repo / "stray.txt").write_text("operator work\n")
    _git(repo, "add", "--", "stray.txt")
    before = _count(repo)

    result = run_committing_op(repo, "merge", ["--no-edit", "-m", "m", "side"], env=None, disable_gpgsign=False)

    assert result.returncode != 0
    assert "stray.txt" in _staged(repo)
    assert _count(repo) == before


def test_committing_revert_refuses_over_a_stray_staged_file(repo: Path) -> None:
    target = _commit_file(repo, "reverted.txt", "r\n", "to revert")
    (repo / "stray.txt").write_text("operator work\n")
    _git(repo, "add", "--", "stray.txt")
    before = _count(repo)

    result = run_committing_op(repo, "revert", ["--no-edit", target], env=None, disable_gpgsign=False)

    assert result.returncode != 0
    assert "stray.txt" in _staged(repo)
    assert _count(repo) == before


def test_committing_merge_records_its_message_and_parents(repo: Path) -> None:
    _side_branch(repo)
    _commit_file(repo, "mine.txt", "mine\n", "diverge")
    result = run_committing_op(repo, "merge", ["side", "--no-edit", "-m", "Merge side into work"], env=None, disable_gpgsign=False)
    assert result.returncode == 0, result.stderr
    assert _subject(repo) == "Merge side into work"
    assert len(_parents(repo)) == 2


# 8 ---------------------------------------------------------------------------


def test_rejecting_pre_commit_hook_runs_once_and_leaves_the_merge_in_progress(repo: Path, tmp_path: Path) -> None:
    _conflicted_merge(repo, "merge msg")
    calls = tmp_path / "hook.calls"
    hooks = repo / ".git" / "hooks"
    hooks.mkdir(exist_ok=True)
    hook = hooks / "pre-commit"
    hook.write_text(f"#!/bin/sh\necho called >> '{calls}'\nexit 1\n")
    hook.chmod(0o755)
    before = _count(repo)

    result = conclude_in_progress_op(repo, env=None)

    assert result.returncode != 0
    assert calls.read_text().splitlines() == ["called"]
    assert _has_ref(repo, "MERGE_HEAD")
    assert _count(repo) == before


# 9 ---------------------------------------------------------------------------


def test_conclusion_signing_follows_the_flag(repo: Path) -> None:
    _conflicted_merge(repo, "merge msg")
    _break_signing(repo)
    before = _count(repo)

    signed = conclude_in_progress_op(repo, env=None, disable_gpgsign=False)
    assert signed.returncode != 0
    assert _count(repo) == before
    assert _has_ref(repo, "MERGE_HEAD")

    unsigned = conclude_in_progress_op(repo, env=None, disable_gpgsign=True)
    assert unsigned.returncode == 0, unsigned.stderr
    assert len(_parents(repo)) == 2


def test_committing_op_signing_follows_the_flag(repo: Path) -> None:
    _side_branch(repo)
    _commit_file(repo, "mine.txt", "mine\n", "diverge")
    _break_signing(repo)
    before = _count(repo)

    signed = run_committing_op(repo, "merge", ["--no-edit", "-m", "m", "side"], env=None, disable_gpgsign=False)
    assert signed.returncode != 0
    assert _count(repo) == before
    _git(repo, "merge", "--abort", check=False)

    unsigned = run_committing_op(repo, "merge", ["--no-edit", "-m", "m", "side"], env=None, disable_gpgsign=True)
    assert unsigned.returncode == 0, unsigned.stderr
    assert len(_parents(repo)) == 2


def test_env_is_passed_to_git(repo: Path, tmp_path: Path) -> None:
    """``env`` reaches git: a hook sees a variable only the caller's env carries."""
    _conflicted_merge(repo, "merge msg")
    seen = tmp_path / "seen"
    hooks = repo / ".git" / "hooks"
    hooks.mkdir(exist_ok=True)
    hook = hooks / "pre-commit"
    hook.write_text(f"#!/bin/sh\nprintf '%s' \"$OWNER_PROBE\" > '{seen}'\n")
    hook.chmod(0o755)

    result = conclude_in_progress_op(repo, env={**os.environ, "OWNER_PROBE": "from-caller"})

    assert result.returncode == 0, result.stderr
    assert seen.read_text() == "from-caller"
