"""What a Codex home looks like inside a project's ``.codex/`` folder (#7729).

Spec Kitty once told users to ``export CODEX_HOME=<project>/.codex``, so a
project's ``.codex/`` can be either of two things:

- a **project folder** that a team commits (``config.toml``, its own rules), or
- a **Codex home**: Codex's personal state for one user, which must never be
  committed (credentials, session logs and databases, caches, approval rules).

The committed ``.gitignore`` is the same in every clone, so it can only ignore
the paths that are personal state in both readings
(:data:`CODEX_HOME_STATE_ENTRIES`). ``config.toml`` is team config in the first
reading and personal config in the second; whether a clone's ``.codex/`` is a
Codex home (:func:`is_codex_home`) is decided per clone, and the clone-local
upgrade step ``4.0.0rc9_exclude_project_local_codex_home`` then keeps the
whole folder out of that clone's ``git status``.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

__all__ = [
    "CODEX_DIR",
    "CODEX_HOME_STATE_ENTRIES",
    "is_codex_home",
]

#: The project folder Codex reads, and that a project-local ``CODEX_HOME`` points at.
CODEX_DIR = ".codex/"

#: ``.gitignore`` patterns for Codex home state that is never team configuration.
#: ``config.toml`` is deliberately absent: in a plain project folder it is shared config.
CODEX_HOME_STATE_ENTRIES: tuple[str, ...] = (
    ".codex/auth.json",
    ".codex/history.jsonl",
    ".codex/sessions/",
    ".codex/archived_sessions/",
    ".codex/log/",
    ".codex/*.sqlite*",
    ".codex/models_cache.json",
    ".codex/version.json",
    ".codex/rules/default.rules",
    ".codex/tmp/",
    ".codex/shell_snapshots/",
    ".codex/memories/",
    ".codex/skills/.system/",
)

#: Top-level names that only a Codex home holds; any one of them marks the folder as one.
_HOME_MARKER_NAMES: frozenset[str] = frozenset(
    {
        "auth.json",
        "history.jsonl",
        "sessions",
        "archived_sessions",
        "log",
        "models_cache.json",
        "version.json",
        "shell_snapshots",
    }
)

_SQLITE_SUFFIX = ".sqlite"


def is_codex_home(project_path: Path, environ: Mapping[str, str] | None = None) -> bool:
    """Whether *project_path*'s ``.codex/`` folder is a Codex home.

    True when ``CODEX_HOME`` (read from *environ*, default ``os.environ``)
    points at that folder, or when the folder holds a file or folder only a
    Codex home has (``auth.json``, ``version.json``, session folders, a Codex
    ``*.sqlite*`` database ...). A missing folder is never a Codex home.
    """
    folder = project_path / CODEX_DIR.rstrip("/")
    if not folder.is_dir():
        return False
    if _codex_home_env_points_at(folder, os.environ if environ is None else environ):
        return True
    try:
        names = {child.name for child in folder.iterdir()}
    except OSError:
        return False
    return bool(names & _HOME_MARKER_NAMES) or any(_SQLITE_SUFFIX in name for name in names)


def _codex_home_env_points_at(folder: Path, environ: Mapping[str, str]) -> bool:
    value = environ.get("CODEX_HOME", "").strip()
    if not value:
        return False
    try:
        return Path(value).expanduser().resolve() == folder.resolve()
    except OSError:
        return False
