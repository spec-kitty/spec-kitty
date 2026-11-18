"""#7612: ``spec-kitty init`` on an unborn branch makes the repository's root commit.

``git init`` followed by ``spec-kitty init`` is the most common first run. #7555 made
init commit what it wrote, but only on a branch that already had a commit. Now:

* the root commit holds exactly the files init wrote; a file the operator already
  had (untracked or staged) stays out of it, and their staging is kept;
* ``--no-commit`` still opts out;
* with no git identity, init writes its files, skips the root commit and exits 0
  with the named note ``INIT_GIT_IDENTITY_MISSING`` (operator ruling: a note, not
  a refusal, as before #7612);
* when git refuses the commit (a rejecting hook), init exits 1 naming
  ``INIT_ROOT_COMMIT_FAILED``, the files it wrote, and the remedy.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.integration.cli_mission_fixture_7545 import dirty, flat, git, isolated_env, run_sk

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.timeout(600)]

_INIT = ("init", "--ai", "claude", "--non-interactive")


def _unborn_repo(tmp_path: Path, *, identity: bool = True) -> tuple[Path, dict[str, str]]:
    env = isolated_env(tmp_path)
    # No identity may leak in from the host or the harness.
    for key in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL", "EMAIL"):
        env.pop(key, None)
    env["GIT_CONFIG_GLOBAL"] = str(tmp_path / "no-global-gitconfig")
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "commit.gpgsign", "false")
    if identity:
        git(repo, "config", "user.name", "QA")
        git(repo, "config", "user.email", "qa@example.invalid")
    else:
        # Without this git may guess an identity from the host name (CI runners have one).
        git(repo, "config", "user.useConfigOnly", "true")
    return repo, env


def _git_env(repo: Path, env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, env=env, capture_output=True, text=True, check=False)


def _untracked_or_changed(repo: Path) -> list[str]:
    out = git(repo, "status", "--porcelain", "--untracked-files=all")
    return sorted(line[3:] for line in out.splitlines() if line)


def test_init_makes_a_root_commit_of_exactly_its_own_files(tmp_path: Path) -> None:
    repo, env = _unborn_repo(tmp_path)
    (repo / "notes.txt").write_text("operator scratch\n", encoding="utf-8")
    (repo / "staged.txt").write_text("mine\n", encoding="utf-8")
    git(repo, "add", "staged.txt")

    proc = run_sk(repo, env, *_INIT)

    assert proc.returncode == 0, flat(proc)[-2000:]
    commits = git(repo, "rev-list", "HEAD").split()
    assert len(commits) == 1
    # A root commit: no parent.
    assert git(repo, "rev-list", "--parents", "-n", "1", "HEAD").split() == commits
    assert git(repo, "log", "-1", "--format=%s").strip() == "chore: initialize spec-kitty project"
    committed = set(git(repo, "ls-tree", "-r", "--name-only", "HEAD").splitlines())
    for path in (".kittify/config.yaml", ".gitignore", ".gitattributes"):
        assert path in committed, sorted(committed)[:20]
    # Exactly init's files: the operator's untracked and staged files stay out ...
    assert "notes.txt" not in committed
    assert "staged.txt" not in committed
    # ... everything else init wrote is in it, and the operator's staging is kept.
    assert _untracked_or_changed(repo) == ["notes.txt", "staged.txt"]
    assert git(repo, "diff", "--cached", "--name-only").split() == ["staged.txt"]


def test_no_commit_leaves_the_branch_unborn(tmp_path: Path) -> None:
    repo, env = _unborn_repo(tmp_path)

    proc = run_sk(repo, env, *_INIT, "--no-commit")

    assert proc.returncode == 0, flat(proc)[-2000:]
    assert _git_env(repo, env, "rev-parse", "--verify", "-q", "HEAD").returncode != 0
    assert ".kittify/config.yaml" in dirty(repo)


def test_missing_identity_writes_the_files_and_skips_the_commit_with_a_named_note(tmp_path: Path) -> None:
    repo, env = _unborn_repo(tmp_path, identity=False)
    # The precondition this test relies on: git really refuses to commit here.
    assert _git_env(repo, env, "var", "GIT_COMMITTER_IDENT").returncode != 0

    proc = run_sk(repo, env, *_INIT)

    assert proc.returncode == 0, flat(proc)[-2000:]
    out = flat(proc)
    assert "INIT_GIT_IDENTITY_MISSING" in out
    assert "git config user.email" in out
    assert ".kittify/" in out
    assert (repo / ".kittify" / "config.yaml").is_file()
    assert _git_env(repo, env, "rev-parse", "--verify", "-q", "HEAD").returncode != 0
    assert ".kittify/config.yaml" in dirty(repo)


def test_missing_identity_does_not_block_no_commit(tmp_path: Path) -> None:
    repo, env = _unborn_repo(tmp_path, identity=False)

    proc = run_sk(repo, env, *_INIT, "--no-commit")

    assert proc.returncode == 0, flat(proc)[-2000:]
    assert (repo / ".kittify" / "config.yaml").is_file()


def test_rejecting_hook_refuses_with_a_named_code_and_keeps_staging(tmp_path: Path) -> None:
    repo, env = _unborn_repo(tmp_path)
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\necho 'policy hook says no' >&2\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)
    (repo / "staged.txt").write_text("mine\n", encoding="utf-8")
    git(repo, "add", "staged.txt")

    proc = run_sk(repo, env, *_INIT)

    assert proc.returncode == 1, flat(proc)[-2000:]
    out = flat(proc)
    assert "INIT_ROOT_COMMIT_FAILED" in out
    assert "policy hook says no" in out
    assert ".kittify/" in out
    assert "Remedy:" in out
    assert _git_env(repo, env, "rev-parse", "--verify", "-q", "HEAD").returncode != 0
    # The failed commit left init's files unstaged and the operator's staging as it was.
    assert git(repo, "diff", "--cached", "--name-only").split() == ["staged.txt"]
    assert (repo / ".kittify" / "config.yaml").is_file()
