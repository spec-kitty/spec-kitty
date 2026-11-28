"""Real-git helpers shared by tests that drive an on-disk repository."""

from __future__ import annotations

import subprocess
from pathlib import Path


def git_out(repo: Path, *args: str) -> str:
    """Run ``git -C repo <args>`` and return its stripped stdout; raise on failure."""
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def commit_init_leftovers(repo: Path, message: str) -> bool:
    """Commit whatever ``spec-kitty init`` left uncommitted in *repo*; return whether it committed.

    ``init`` commits its own writes: in a repository with a commit since #7555, and on an
    unborn branch, as the root commit, since #7612. That leaves a clean tree, and a plain
    ``git commit`` then fails with "nothing to commit". A fixture that wants every file
    ``init`` wrote committed calls this instead: it commits only what is still uncommitted
    (``--no-commit``, or a path ``init`` does not commit) and never makes an empty commit,
    so the history stays the one a user would have. This is the #7634 fixture rule.
    """
    if not git_out(repo, "status", "--porcelain", "--untracked-files=all"):
        return False
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", message], check=True, capture_output=True)
    return True


def real_git_command(cmd: list[str] | tuple[str, ...], cwd: Path) -> tuple[int, str, str]:
    """Run *cmd* (a ``git ...`` argv) for real in *cwd* and return ``run_command``'s triple.

    For a ``run_command`` double that fakes most git but must answer ref lookups with
    objects that exist: the consolidation claim feeds every resolved tip into further
    real git probes (``rev-list``, ``cat-file``), which fail closed on a made-up SHA.
    """
    result = subprocess.run(list(cmd), cwd=cwd, check=False, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr
