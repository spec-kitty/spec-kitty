"""Public runtime-state path facade for the CLI.

Windows-specific logic lives here so that consumers (auth, tracker, sync,
daemon, CLI) can remain platform-agnostic. On POSIX platforms this module
returns the existing ~/.spec-kitty convention unchanged. The directory name
itself is owned by ``kernel.paths`` and re-exported here for compatibility.
"""

from __future__ import annotations

from kernel.paths import RUNTIME_STATE_DIR_NAME
from specify_cli.paths.windows_paths import (
    RuntimeRoot,
    ensure_runtime_root,
    get_runtime_config_toml_path,
    get_runtime_root,
    render_runtime_path,
)

__all__ = [
    "RUNTIME_STATE_DIR_NAME",
    "RuntimeRoot",
    "ensure_runtime_root",
    "get_runtime_config_toml_path",
    "get_runtime_root",
    "render_runtime_path",
]
