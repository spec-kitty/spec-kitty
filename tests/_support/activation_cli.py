"""Real-subprocess helpers for the activation-ledger acceptance tests (WP14).

Each call starts the CLI the way a user does: a separate process with a real
``argv`` and the full CLI startup. The entry point is the ``spec-kitty``
console script beside the running interpreter (``.venv/bin/spec-kitty``), with
``python -m specify_cli`` from the same interpreter as the fallback, and
``PYTHONPATH`` pinned to this checkout's ``src`` so a stale install is never
tested by mistake.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

__all__ = ["REPO_ROOT", "cli", "git", "init_git_repo", "snapshot", "unwrapped"]

REPO_ROOT = Path(__file__).resolve().parents[2]
_TIMEOUT = 300
_GIT_DIR = ".git"
#: The per-test CLI home and its sibling lock directories (``.spec-kitty-home-cold-install``).
_HOME_PREFIX = ".spec-kitty-home"


def _entry_point() -> list[str]:
    script = Path(sys.executable).parent / "spec-kitty"
    return [str(script)] if script.is_file() else [sys.executable, "-m", "specify_cli"]


def cli(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run ``spec-kitty *args`` in *cwd* as a separate process."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    # Assign, never setdefault: an inherited home would leak a developer's real one.
    env["SPEC_KITTY_HOME"] = str(cwd / ".spec-kitty-home")
    return subprocess.run(
        [*_entry_point(), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=_TIMEOUT,
        env=env,
        stdin=subprocess.DEVNULL,
    )


def git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run ``git *args`` in *cwd*, raising on failure."""
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)


def init_git_repo(repo: Path) -> Path:
    """Create *repo* as a git repository on ``main`` with a committer identity."""
    repo.mkdir(parents=True, exist_ok=True)
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test")
    return repo


def unwrapped(result: subprocess.CompletedProcess[str]) -> str:
    """Combined stdout and stderr with Rich's hard wrapping collapsed."""
    return " ".join((result.stdout + " " + result.stderr).split())


def snapshot(root: Path) -> dict[str, bytes]:
    """``{relative path: bytes}`` of every file under *root*, outside ``.git`` and the CLI home directories."""
    found: dict[str, bytes] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        top = relative.parts[0]
        if top == _GIT_DIR or top.startswith(_HOME_PREFIX) or not path.is_file():
            continue
        found[relative.as_posix()] = path.read_bytes()
    return found
