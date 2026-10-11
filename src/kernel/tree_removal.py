"""Remove a directory tree the tool itself owns, after proving it is owned (#5965 / #5966).

A bare ``shutil.rmtree`` cannot tell a temp or staging tree from a user's git
checkout. :func:`remove_tool_owned_tree` makes the caller name the root it owns
(``tool_root``) and proves, at run time, that ``path`` lies inside it and that
no directory between them is a git checkout. A git checkout is deleted only by
``specify_cli.git.destructive_guard.guarded_tree_delete``, which scans it for
the only copy of a file first.

Standard library only: this module sits in the kernel layer and imports nothing
from ``specify_cli`` or ``charter``.
"""

from __future__ import annotations

import logging
import os
import shutil
import stat
import sys
from collections.abc import Callable
from pathlib import Path

__all__ = ["ToolOwnedPathUnproven", "remove_tool_owned_tree"]

_TOOL_OWNED_PATH_UNPROVEN = "TOOL_OWNED_PATH_UNPROVEN"

_LOG = logging.getLogger(__name__)


class ToolOwnedPathUnproven(ValueError):
    """``path`` is not provably a tool-owned tree; nothing was deleted (a programming error)."""

    error_code = _TOOL_OWNED_PATH_UNPROVEN


def _retry_writable(function: Callable[[str], object], name: str, _exc: object) -> None:
    """``shutil.rmtree`` error hook: clear a read-only bit and retry once (Windows, read-only trees)."""
    for target in (Path(name), Path(name).parent):
        os.chmod(target, stat.S_IRWXU)  # removal is governed by the parent's write bit on POSIX
    function(name)


def _rmtree(path: Path) -> None:
    # ``onexc`` replaced the deprecated ``onerror`` in 3.12; the project floor is 3.11.
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_retry_writable)
    else:
        shutil.rmtree(path, onerror=_retry_writable)


def _prove_owned(path: Path, tool_root: Path, reason: str) -> Path:
    """Return ``path`` resolved, or raise :class:`ToolOwnedPathUnproven`."""
    resolved = path.resolve()
    root = tool_root.resolve()
    if resolved != root and root not in resolved.parents:
        raise ToolOwnedPathUnproven(f"{_TOOL_OWNED_PATH_UNPROVEN}: {path} is not inside the owned root {tool_root} ({reason}); nothing was deleted")
    cursor = resolved
    while True:
        if (cursor / ".git").exists() or (cursor / ".git").is_symlink():
            raise ToolOwnedPathUnproven(
                f"{_TOOL_OWNED_PATH_UNPROVEN}: {cursor} is a git checkout ({reason}); delete it through guarded_tree_delete, nothing was deleted"
            )
        if cursor == root:
            return resolved
        cursor = cursor.parent


def _delete(path: Path, resolved: Path) -> None:
    if path.is_symlink():
        path.unlink()  # the link itself; its (proven in-root) target is another call's business
    elif resolved.is_dir():
        _rmtree(resolved)
    else:
        resolved.unlink()


def remove_tool_owned_tree(
    path: Path,
    *,
    tool_root: Path,
    reason: str,
    missing_ok: bool = True,
    best_effort: bool = False,
) -> bool:
    """Delete ``path`` when it is provably a tool-owned tree; return whether anything was removed.

    Refuses with :class:`ToolOwnedPathUnproven` when ``path`` does not resolve
    inside ``tool_root`` (a symlink resolving outside it included), or when ``path`` or
    any directory up to and including ``tool_root`` holds a ``.git`` entry.
    Errors are never swallowed silently: a missing path returns ``False`` when
    ``missing_ok`` and raises ``FileNotFoundError`` otherwise; a failed removal
    raises unless ``best_effort``, which logs at debug level and returns ``False``.
    """
    if not (path.exists() or path.is_symlink()):
        if missing_ok:
            return False
        raise FileNotFoundError(path)
    resolved = _prove_owned(path, tool_root, reason)
    try:
        _delete(path, resolved)
    except OSError:
        if not best_effort:
            raise
        _LOG.debug("best-effort removal of %s failed (%s)", path, reason, exc_info=True)
        return False
    return True
