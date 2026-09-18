"""CLI startup encoding helpers.

On Windows, forces UTF-8 stdout/stderr to avoid crashes on non-UTF-8 code
pages when printing paths or status lines that contain non-ASCII characters.
"""

from __future__ import annotations

import sys

from kernel.paths import is_windows


def ensure_utf8_on_windows() -> None:
    """Reconfigure stdout/stderr to UTF-8 on Windows. No-op on POSIX."""
    if not is_windows():
        return
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            # Stream may not be a TextIOWrapper (e.g. redirected). Safe to skip.
            continue
