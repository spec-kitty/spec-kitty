"""The one host-aware mode equivalence (#4927, #4810; operator ruling 2026-11-20).

Whether an *observed* file-system mode satisfies a *planned* one depends on
the host. On POSIX the comparison is exact. On Windows (NTFS) CPython
synthesizes the mode from the file attributes -- a directory reads ``0o777``
(``0o555`` with the read-only attribute), a file ``0o666`` or ``0o444`` -- and
``chmod`` only toggles the read-only attribute. So on Windows a directory or
a symlink compares its kind only, and a file compares only its owner write
bit.

It lives at the kernel floor so every layer can use the same rule: the
tool-surface planners (through ``specify_cli.tool_surface.operations``, which
adds the ``FileState`` forms) and the charter YAML writer alike. The host is
read through ``kernel.paths.is_windows`` at call time, so tests can emulate
Windows. Two observations of the same node (a concurrency guard) or two
planned states (a conflict check) must NOT use it: those compare exactly on
every host.
"""

from __future__ import annotations

from kernel import paths as kernel_paths

__all__ = ["modes_equivalent"]

_OWNER_WRITE_BIT = 0o200
_KIND_ONLY_ON_WINDOWS = frozenset({"directory", "symlink"})


def modes_equivalent(kind: str, observed: int | None, planned: int | None) -> bool:
    """Return whether an *observed* mode satisfies a *planned* one for a node of *kind* on this host.

    POSIX, or either mode unknown, or a kind other than ``file``/``directory``/
    ``symlink``: exact equality. Windows: a directory or symlink is always
    equivalent; a file is equivalent when both modes agree on the owner write
    bit (the read-only attribute, the one permission NTFS stores).
    """
    if observed is None or planned is None or not kernel_paths.is_windows():
        return observed == planned
    if kind in _KIND_ONLY_ON_WINDOWS:
        return True
    if kind == "file":
        return bool(observed & _OWNER_WRITE_BIT) == bool(planned & _OWNER_WRITE_BIT)
    return observed == planned
