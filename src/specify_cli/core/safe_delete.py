"""Canonical safe-delete util for managed, possibly-read-only assets (#4714).

Managed content is materialized read-only (e.g. ``_write_asset``'s ``or
0o444`` and agent-skill assets that strip ``0o222``). On Windows,
``DeleteFile``/``RemoveDirectory`` REFUSE a read-only target with
``PermissionError`` — POSIX ignores the mode on unlink/rmdir, the same
POSIX-ignores-but-Windows-enforces divergence as the #4703 lock read — so a
managed-asset delete must clear the write bit before removing it.

The contract is NO-FOLLOW + MASKED: :func:`force_writable` chmods via
``path.lstat()`` (never resolves a final-component symlink) and masks the
mode with :func:`stat.S_IMODE` (payload permission bits only, not the
``S_IFMT`` file-type bits) before ORing in the owner-write bit. A
managed-asset delete must never chmod through a symlink onto a target that
may live outside the managed tree — a boundary leak, CWE-59-adjacent (SC-006).
"""

from __future__ import annotations

import stat
from contextlib import suppress
from pathlib import Path

# force_writable is intentionally NOT re-exported here: it is the shared
# lstat+mask chmod primitive that safe_unlink/safe_rmdir apply before their
# delete retry, referenced only intra-module (dead-symbol gate #470 -- an
# __all__ member is held to a stricter cross-module-caller bar than a plain
# public name). It stays importable directly for a caller that needs the
# chmod-restore step alone without an accompanying delete.
#
# No safe_rmtree: a managed-asset recursive delete has no src consumer today
# (the three pre-#4714 copies' rmtree helpers were all dead, and the only
# managed-tree delete pattern lives in the frozen m_3_2_0rc45 migration, which
# keeps its own inline copy per C-002). Adding it as canonical API before a
# consumer exists is dead code the #470 gate rightly rejects; add it (with the
# read-only onerror shim) when the first non-frozen managed-tree delete lands.
__all__ = ["safe_rmdir", "safe_unlink"]


def force_writable(path: Path) -> None:
    """Best-effort restore the owner write bit before removing a managed asset.

    NO-FOLLOW (``lstat``) + MASKED (``S_IMODE``): never touches a symlink
    target outside the managed tree. Two structural guards enforce this:
    ``lstat`` (never ``stat``) reads the entry's own mode without resolving a
    final-component symlink, and — because ``Path.chmod`` itself resolves a
    symlink argument and would mutate whatever it points to (POSIX has no
    portable ``lchmod`` for this) — an entry that ``lstat`` reports as a
    symlink is skipped entirely rather than chmod'd. A symlink's own mode
    bits are not meaningful for delete permission on either OS, so skipping
    it costs nothing and closes the boundary leak (CWE-59-adjacent, SC-006).
    Any other chmod failure — including a path that has already vanished (a
    raced concurrent delete) — is swallowed; the delete retry that follows
    surfaces any real failure.
    """
    with suppress(OSError):
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode):
            return
        path.chmod(stat.S_IMODE(info.st_mode) | stat.S_IWRITE)


def safe_unlink(path: Path) -> None:
    """Remove a file, clearing a read-only bit first if the OS refuses it."""
    try:
        path.unlink()
    except PermissionError:
        force_writable(path)
        path.unlink()


def safe_rmdir(path: Path) -> None:
    """Remove a directory, clearing a read-only bit first if the OS refuses it."""
    try:
        path.rmdir()
    except PermissionError:
        force_writable(path)
        path.rmdir()
