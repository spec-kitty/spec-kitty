"""Single source of truth for Windows runtime state paths.

Windows-specific logic lives here so that consumers (auth, tracker, sync,
daemon, CLI) can remain platform-agnostic.  On POSIX platforms this module
returns the existing ~/.spec-kitty convention unchanged.
"""

from __future__ import annotations

from specify_cli.paths.windows_paths import (
    RuntimeRoot,
    ensure_runtime_root,
    get_runtime_root,
    render_runtime_path,
)

__all__ = [
    "RuntimeRoot",
    "ensure_runtime_root",
    "get_runtime_root",
    "render_runtime_path",
]
