"""Shared helpers for denied-access (EACCES) tests.

**Prefer seam injection.** ``deny_open_in`` and ``deny_path_method`` make ONE
named path raise ``PermissionError`` at the filesystem seam the code under test
reads through, and delegate to the original for every other path.
``deny_removal_from`` applies the POSIX "the parent must be writable" rule to
removals. They behave the same for every uid (root bypasses mode bits, so a
``chmod(0)`` setup gave a different verdict per uid, #5622, #5691), so they
need no skip.

Reach for the chmod-and-skip technique (``mode_bits_enforced``) only when the
test must exercise the real kernel permission check itself, for example
``tests/specify_cli/core/test_safe_stat_predicates.py``, which pins that a real
``stat()`` through a ``0o000`` directory raises (`#3194`; the pattern
``test_ownership_3111.py`` established for `#3111`/`#3177` before that test
was removed with the decisions resolver).

Paths are compared RESOLVED (``Path(p).resolve() == Path(target).resolve()``),
so a symlinked or relative spelling of the target is still denied. Arguments
that are not path-like fall through to the original.
"""

from __future__ import annotations

import builtins
import os
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


def _is_target(candidate: object, resolved_target: Path) -> bool:
    """Whether *candidate* names *resolved_target*; non-path arguments are never a match."""
    if not isinstance(candidate, (str, os.PathLike)):
        return False
    try:
        return Path(candidate).resolve() == resolved_target
    except (OSError, RuntimeError, ValueError):
        return False


def _denied(candidate: object) -> PermissionError:
    return PermissionError(13, "Permission denied", str(candidate))


def deny_open_in(monkeypatch: pytest.MonkeyPatch, module: ModuleType, target: Path) -> None:
    """Make ``open(target)`` inside *module* raise ``PermissionError``; every other path delegates.

    Patches the module-level name ``open`` (shadowing the builtin for that
    module only), so code in other modules is unaffected.
    """
    resolved_target = Path(target).resolve()
    real_open = builtins.open

    def guarded_open(file: Any, *args: Any, **kwargs: Any) -> Any:
        if _is_target(file, resolved_target):
            raise _denied(file)
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(module, "open", guarded_open, raising=False)


def deny_path_method(monkeypatch: pytest.MonkeyPatch, attr: str, target: Path) -> None:
    """Make ``Path.<attr>`` raise ``PermissionError`` when called on *target*; every other path delegates.

    *attr* is a ``Path`` method name such as ``"read_text"``, ``"exists"`` or
    ``"iterdir"``. Call it once per method to deny several.

    A ``follow_symlinks=False`` call on a symlink is not denied: it reads the
    link itself, which a regular uid can do even when the link's target sits
    in a ``0o000`` directory. So denying ``"stat"`` on such a link denies the
    stat through it while ``lstat()`` and ``is_symlink()`` still succeed, as
    they would for that uid.
    """
    resolved_target = Path(target).resolve()
    original: Callable[..., Any] = getattr(Path, attr)

    def guarded(self: Path, *args: Any, **kwargs: Any) -> Any:
        reads_the_link = kwargs.get("follow_symlinks") is False and os.path.islink(self)
        if not reads_the_link and _is_target(self, resolved_target):
            raise _denied(self)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, attr, guarded)


def _is_read_only_parent(path: object, dir_fd: int | None, identity: tuple[int, int]) -> bool:
    """Whether *path* (relative to *dir_fd* when given) exists in the directory *identity* while it lacks owner-write.

    A missing entry is never denied: the kernel reports ``ENOENT`` before it
    checks the parent's write bit, so the real call raises that instead.
    """
    if not isinstance(path, (str, bytes, os.PathLike)):
        return False
    name = os.fsdecode(os.fspath(path))
    try:
        if dir_fd is not None and not os.path.isabs(name):
            os.lstat(name, dir_fd=dir_fd)
            parent = os.path.dirname(name)
            st = os.stat(parent, dir_fd=dir_fd) if parent else os.fstat(dir_fd)
        else:
            os.lstat(name)
            st = os.stat(os.path.dirname(os.path.abspath(name)))
    except OSError:
        return False
    return (st.st_dev, st.st_ino) == identity and not st.st_mode & 0o200


def deny_removal_from(monkeypatch: pytest.MonkeyPatch, directory: Path) -> None:
    """Make removing an entry of *directory* raise ``PermissionError`` while *directory* lacks owner-write.

    On POSIX a process may unlink or rmdir an entry only when it may write the
    directory that holds it; root bypasses that check, so a ``chmod(0o555)``
    parent blocks the removal for a regular uid and allows it for uid 0. This
    applies the same rule for every uid, and lifts it as soon as the code under
    test restores the write bit, so a retry-after-chmod path runs as it would
    for a regular uid.

    It wraps ``os.unlink``, ``os.remove`` and ``os.rmdir``, which
    ``Path.unlink``, ``Path.rmdir`` and ``shutil.rmtree`` all call. Neither
    ``deny_open_in`` nor ``deny_path_method`` reaches ``shutil.rmtree``: it
    removes members with ``os.unlink(name, dir_fd=fd)``, a bare name relative to
    an open directory, so the containing directory is matched by device and
    inode rather than by path.

    POSIX semantics only. On Windows ``chmod(0o555)`` on a directory sets its
    read-only attribute, which Windows ignores for removing children; this
    helper still denies them there, so use it only where the code under test
    restores the parent's write bit before retrying (as every current caller
    does).
    """
    st = os.stat(directory)
    identity = (st.st_dev, st.st_ino)
    for name in ("unlink", "remove", "rmdir"):
        real: Callable[..., None] = getattr(os, name)

        def guarded(path: Any, *, dir_fd: int | None = None, _real: Callable[..., None] = real) -> None:
            if _is_read_only_parent(path, dir_fd, identity):
                raise _denied(path)
            _real(path, dir_fd=dir_fd)

        monkeypatch.setattr(os, name, guarded)


def mode_bits_enforced(probe: Path) -> bool:
    """Return ``True`` when the process is actually denied by *probe*'s mode bits.

    **Skip honestly.** Running as root, or on a filesystem that ignores mode
    bits, makes a ``0o000`` test pass while exercising nothing — the vacuous
    case. *probe* must be a **file** read *after* the directory containing it
    has been ``chmod``'d to ``0o000``: on a directory, opening it always raises
    ``IsADirectoryError`` (itself an ``OSError``), which would make this helper
    constant ``True`` and silently defeat the skip it exists to perform.
    """
    try:
        with probe.open("rb"):
            pass
    except OSError:
        return True
    return False
