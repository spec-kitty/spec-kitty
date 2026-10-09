"""Single authority for which branch a coordination worktree is on.

Leaf module (stdlib only) so both ``workspace`` and ``coherence`` can import it
without a cycle.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

_COORD_BRANCH_PROBE_TIMEOUT_SECONDS = 30
DETACHED_OR_UNREADABLE_HEAD = "<detached or unreadable HEAD>"


def _head_ref_from_gitdir_file(path: Path) -> str | None:
    """Read ``HEAD`` of a linked worktree without spawning git.

    Only the ``.git`` *file* shape (``gitdir: <dir>``) is handled; any other
    shape (a ``.git`` directory, missing or unparsable file, non-ref ``HEAD``)
    returns ``None`` so the caller falls back to ``git symbolic-ref``.
    """
    try:
        pointer = (path / ".git").read_text(encoding="utf-8").strip()
        if not pointer.startswith("gitdir:"):
            return None
        gitdir = Path(pointer.removeprefix("gitdir:").strip())
        if not gitdir.is_absolute():
            gitdir = path / gitdir
        head = (gitdir / "HEAD").read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return None
    if not head.startswith("ref: "):
        return None
    return head.removeprefix("ref: ").strip() or None


def probe_coord_branch(path: Path, env: dict[str, str] | None) -> tuple[str | None, str]:
    """Return ``(symbolic_ref, failure_label)``; the label is used only when the ref is ``None``."""
    ref = _head_ref_from_gitdir_file(path)
    if ref is not None:
        return ref, ""
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "symbolic-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            env=env,
            timeout=_COORD_BRANCH_PROBE_TIMEOUT_SECONDS,
        )
    except OSError as exc:
        return None, f"<git unavailable: {exc}>"
    except subprocess.SubprocessError:
        return None, DETACHED_OR_UNREADABLE_HEAD
    if result.returncode != 0:
        return None, DETACHED_OR_UNREADABLE_HEAD
    return result.stdout.strip() or None, DETACHED_OR_UNREADABLE_HEAD


def coord_worktree_branch(path: Path, *, env: dict[str, str] | None = None) -> str | None:
    """Return the symbolic ref a coordination worktree has checked out.

    Single authority for "which branch is this worktree on". ``None`` means a
    detached or unreadable HEAD (including an unavailable git binary).
    """
    return probe_coord_branch(path, env)[0]


def normalize_ref(ref: str) -> str:
    """Strip ``refs/heads/`` prefix so HEAD comparisons use short names."""
    return ref.removeprefix("refs/heads/")
