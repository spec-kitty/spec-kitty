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
import tempfile
from pathlib import Path

from kernel.atomic import notify_written

__all__ = [
    "atomic_write",
]


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
        notify_written(path, raw)  # the finalize write ledger, when a run installed one
    except BaseException:
        with contextlib.suppress(OSError):
            os.close(fd)
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise
