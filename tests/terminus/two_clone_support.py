"""Shared bare-remote + second-clone helpers for the second-clone regression tests.

Not a test module (no ``test_`` prefix). Used by ``tests/kernel/test_git_remote.py``
and the origin-reconciliation regression tests: a REAL bare ``file://``-style
remote, a working clone, and a second clone that can push ahead of the first.
No network beyond the local filesystem.
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

__all__ = [
    "attach_and_push",
    "clone_from",
    "isolated_git_env",
    "make_bare_remote",
    "unreachable_remote",
]

_IDENTITY = (("user.name", "Test User"), ("user.email", "test@example.com"))


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def _set_identity(repo: Path) -> None:
    for key, value in _IDENTITY:
        _git(repo, "config", key, value)


def isolated_git_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Isolate global git config so the host's settings cannot leak in (#5602)."""
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_TERMINAL_PROMPT", "0")


def make_bare_remote(tmp_path: Path) -> Path:
    """Create an empty bare repository (``origin.git``) under *tmp_path*."""
    bare = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-q", "-b", "main", str(bare)], check=True, capture_output=True)
    return bare


def attach_and_push(repo: Path, bare: Path, refs: Sequence[str], name: str = "origin") -> None:
    """Add *bare* as remote *name* of *repo* and push each of *refs* to it."""
    _git(repo, "remote", "add", name, str(bare))
    for ref in refs:
        _git(repo, "push", "-q", name, f"{ref}:refs/heads/{ref}")


def clone_from(bare: Path, dest: Path) -> Path:
    """Clone *bare* into *dest* and set a local committer identity."""
    subprocess.run(["git", "clone", "-q", str(bare), str(dest)], check=True, capture_output=True)
    _set_identity(dest)
    return dest


def unreachable_remote(repo: Path, name: str = "origin") -> None:
    """Re-point remote *name* at a deleted path so every contact fails."""
    gone = repo.parent / f"{name}-gone.git"
    gone.mkdir(exist_ok=True)
    shutil.rmtree(gone)
    _git(repo, "remote", "set-url", name, str(gone))
