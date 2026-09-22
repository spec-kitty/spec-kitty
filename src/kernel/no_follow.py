"""Text-file helpers that refuse to follow a final symlink component.

Also home to the host-safe ``follow_symlinks=False`` apply primitives
(``utime_no_follow``, ``chmod_no_follow``): on Windows neither ``os.utime``
nor ``os.chmod`` is listed in :data:`os.supports_follow_symlinks`, so passing
that flag unconditionally raises ``NotImplementedError: utime: follow_symlinks
unavailable on this platform`` (#4923). Each primitive honors the flag only
where the host actually lists that function in
:data:`os.supports_follow_symlinks` -- so a symlink effect lands on the link
itself rather than its target (FR-003) on those hosts. Support is per-function,
not per-OS: Linux lists ``os.utime`` but not ``os.chmod`` (no ``lchmod``),
macOS lists both, Windows lists neither. Where the flag is unsupported the
fallback drops it (default-follow); the skills call sites only reach the
symlink path when the mode already diverges, which never happens for a Linux
symlink, so no link-relative chmod is silently lost.
"""

from __future__ import annotations

import errno
import os
from pathlib import Path

__all__ = [
    "NoFollowPathError",
    "chmod_fd",
    "chmod_no_follow",
    "fd_relative_dir_ops_supported",
    "open_no_follow",
    "read_text_no_follow",
    "utime_no_follow",
    "write_text_no_follow",
]


class NoFollowPathError(RuntimeError):
    """Raised when a requested path is a symlink and must not be followed."""


def chmod_fd(fd: int, path: Path, mode: int) -> None:
    """Apply *mode* to an open descriptor, falling back to a path-based chmod.

    ``os.fchmod`` does not exist on Windows. Platforms without it get a
    plain :meth:`Path.chmod` on *path* instead, mirroring the existing
    ``hasattr(os, "fchmod")`` dance in ``charter_yaml_io.py`` and
    ``status/store.py``.
    """
    if hasattr(os, "fchmod"):
        os.fchmod(fd, mode)
    else:  # pragma: no cover - exercised only on platforms without fchmod
        path.chmod(mode)


def utime_no_follow(path: Path, *, ns: tuple[int, int]) -> None:
    """Apply *ns* mtime/atime to *path*, skipping ``follow_symlinks`` where unsupported.

    Mirrors :func:`chmod_no_follow`: on a host where :func:`os.utime` supports
    ``follow_symlinks`` the timestamps land on the node itself, preserving
    symlink semantics (FR-003). Elsewhere (Windows) the flag is not passed at
    all rather than raising ``NotImplementedError`` (#4923); for a regular
    file the two forms are equivalent, so nothing is lost there.
    """
    if os.utime in os.supports_follow_symlinks:
        os.utime(path, ns=ns, follow_symlinks=False)
    else:
        # Host cannot express follow_symlinks (e.g. Windows): fall back to a
        # default-follow utime. For a regular file this is identical; for a
        # symlink the timestamps would land on the target, but such hosts
        # cannot apply link-relative times at all — see #4923.
        os.utime(path, ns=ns)


def chmod_no_follow(path: Path, mode: int) -> None:
    """Apply *mode* to *path*, skipping ``follow_symlinks`` where unsupported.

    On a host where ``os.chmod`` is listed in
    :data:`os.supports_follow_symlinks` (e.g. macOS) the mode lands on the node
    itself, preserving symlink semantics (FR-003). Where it is not -- which
    includes **Linux** (no ``lchmod``) as well as Windows -- the flag is not
    passed at all rather than raising ``NotImplementedError`` (#4923); for a
    regular file the two forms are equivalent, so nothing is lost there.
    """
    if os.chmod in os.supports_follow_symlinks:
        path.chmod(mode, follow_symlinks=False)
    else:
        # Host cannot express follow_symlinks for chmod (this includes Linux,
        # where os.chmod is not in os.supports_follow_symlinks, as well as
        # Windows): fall back to a default-follow chmod. For a regular file
        # this is identical; for a symlink the mode would follow to the target,
        # but link-relative chmod is unavailable on these hosts — see #4923.
        path.chmod(mode)


def fd_relative_dir_ops_supported() -> bool:
    """Whether dir_fd-relative directory operations are available here.

    Windows lacks ``os.O_DIRECTORY`` / ``os.O_NOFOLLOW`` and does not list
    :func:`os.open` in :data:`os.supports_dir_fd`, so the fd-relative
    containment dance (open a parent directory with ``O_NOFOLLOW``, then
    address children via ``dir_fd=``) cannot run there. This is the single
    authority for that capability check; ``coordination.atomic_write`` and the
    session-presence / tool-surface writers all route through it.
    """
    return os.open in os.supports_dir_fd and hasattr(os, "O_DIRECTORY") and hasattr(os, "O_NOFOLLOW")


def open_no_follow(path: Path, flags: int, mode: int = 0o666) -> int:
    """Open *path* without following a final symlink component.

    On platforms exposing :data:`os.O_NOFOLLOW`, the kernel enforces this on
    the open syscall, closing the check-then-use window. Other platforms get a
    best-effort pre-open symlink check.

    Args:
        path: File path to open.
        flags: Flags accepted by :func:`os.open`.
        mode: Creation mode used when *flags* includes ``os.O_CREAT``.

    Returns:
        An owned file descriptor; callers must close it.

    Raises:
        NoFollowPathError: If *path* is a final-component symlink.
        OSError: If the operating system cannot open the path for another
            reason.
    """
    no_follow = getattr(os, "O_NOFOLLOW", 0)
    if no_follow == 0 and path.is_symlink():
        raise NoFollowPathError(f"{path} is a symlink; refusing to open it")
    try:
        return os.open(path, flags | no_follow, mode)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise NoFollowPathError(f"{path} is a symlink; refusing to open it") from exc
        raise


def read_text_no_follow(path: Path, encoding: str = "utf-8", errors: str | None = None) -> str:
    """Read text from a regular file without following a symlink."""
    fd = open_no_follow(path, os.O_RDONLY)
    with os.fdopen(fd, "r", encoding=encoding, errors=errors) as handle:
        return handle.read()


def write_text_no_follow(path: Path, content: str, encoding: str = "utf-8") -> None:
    """Write *content* to a regular file without following a symlink."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    fd = open_no_follow(path, flags)
    with os.fdopen(fd, "w", encoding=encoding) as handle:
        handle.write(content)
