"""Atomic file write utility (specify_cli surface).

Guarantees: file is either complete old content or complete new content,
never partial. Uses write-to-temp-then-rename on the same filesystem.

The canonical *no-op-stable* comparison core (umbrella #1914) —
:func:`kernel.atomic.substantively_equal` and the
:func:`kernel.atomic.write_if_changed` convenience — lives in
:mod:`kernel.atomic` so the dependency-free root layer owns it and the
``charter`` layer can adopt it without crossing the ``charter ↛ specify_cli``
boundary (see ``tests/architectural/test_layer_rules.py`` Invariant 3).
specify_cli-level callers import that surface directly from ``kernel.atomic``;
this module deliberately does NOT re-export it (a re-export with no
specify_cli-side consumer would be dead public surface — the Phase-2
status/upgrade convergence will import from ``kernel.atomic`` at its call site).
"""

from __future__ import annotations

import contextlib
import os
import stat
import tempfile
from pathlib import Path

from kernel.atomic import notify_written

__all__ = [
    "atomic_write",
]


def _clear_readonly_for_replace(path: Path) -> int | None:
    """Make a read-only destination replaceable; return its mode to re-apply.

    NO-FOLLOW + MASKED (mirrors ``core.safe_delete.force_writable``): a symlink
    destination is skipped (never chmod through the link onto a target that may
    live outside the managed tree), and only the ``S_IMODE`` permission bits are
    considered. Returns the destination's original mode when its owner write bit
    had to be restored (so the caller re-applies it after the replace), or
    ``None`` when the destination is absent, a symlink, or already writable (the
    cases where today's behaviour is unchanged).
    """
    if path.is_symlink() or not path.exists():
        return None
    original = stat.S_IMODE(path.lstat().st_mode)
    if original & stat.S_IWRITE:
        return None
    path.chmod(original | stat.S_IWRITE)
    return original


def atomic_write(path: Path, content: str | bytes, *, mkdir: bool = False) -> None:
    """Write *content* atomically to *path*.

    Parameters
    ----------
    path : Path
        Target file path.
    content : str | bytes
        File content. ``str`` is encoded to UTF-8; ``bytes`` is written raw.
    mkdir : bool
        If True, create parent directories before writing.
    """
    if mkdir:
        path.parent.mkdir(parents=True, exist_ok=True)

    raw = content.encode("utf-8") if isinstance(content, str) else content

    # On Windows ``os.replace`` REFUSES a read-only destination with WinError 5;
    # POSIX ignores the target mode (#6228). Restore the destination's owner
    # write bit before the replace so the overwrite succeeds on every platform,
    # then re-apply its original mode afterward so a managed read-only file (e.g.
    # a project SKILL.md the installer re-marks read-only every run) stays
    # read-only and the upgrade self-converges. NO-FOLLOW + MASKED, mirroring
    # ``core.safe_delete.force_writable``: a symlink destination is left untouched
    # (never chmod through the link) and only the permission bits are considered.
    restore_mode = _clear_readonly_for_replace(path)

    fd, tmp_path = tempfile.mkstemp(
        dir=path.parent,
        prefix=".atomic-",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(raw)
        # fd is now closed by the context manager
        os.replace(tmp_path, str(path))
        if restore_mode is not None:
            with contextlib.suppress(OSError):
                path.chmod(restore_mode)
        notify_written(path, raw)  # the finalize write ledger, when a run installed one
    except BaseException:
        with contextlib.suppress(OSError):
            os.close(fd)
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise
