"""Text-file helpers that refuse to follow a final symlink component.

Canonical implementation moved to :mod:`kernel.no_follow` (mission
``local-write-safety-01M2ZPZD``, WP01/FR-001/FR-003): ``kernel.locks`` needed
this primitive to close the lock-path symlink-follow hole (#4756) but cannot
import ``specify_cli`` (the enforced layer direction is
``kernel <- specify_cli``, never the reverse). This module now re-exports the
kernel implementation so every existing importer keeps working unchanged.

``NoFollowPathError`` is re-exported, not redefined -- it is the SAME class
object as :class:`kernel.no_follow.NoFollowPathError`. Redefining it here
would silently break ``except NoFollowPathError`` at every call site (e.g.
``specify_cli/gitignore_manager.py``), since a caller catching this module's
class would no longer match an exception raised by the kernel module.
"""

from __future__ import annotations

from kernel.no_follow import (
    NoFollowPathError,
    chmod_fd,
    fd_relative_dir_ops_supported,
    open_no_follow,
    read_text_no_follow,
    write_text_no_follow,
)

__all__ = [
    "NoFollowPathError",
    "chmod_fd",
    "fd_relative_dir_ops_supported",
    "open_no_follow",
    "read_text_no_follow",
    "write_text_no_follow",
]
