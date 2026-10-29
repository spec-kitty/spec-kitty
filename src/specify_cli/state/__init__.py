"""State model diagnostics and contract for spec-kitty CLI.

This package provides project-scoped state health checks and the
machine-readable state surface registry, distinct from the
feature-scoped status checks in specify_cli.status.
"""

from .contract import (
    CLEANUP_EVENT_LOGS_COMMAND,
    AuthorityClass,
    CleanupPolicy,
    GitClass,
    RetentionRule,
    STATE_SURFACES,
    StateFormat,
    StateRoot,
    StateSurface,
    get_runtime_gitignore_entries,
    get_surfaces_by_authority,
    get_surfaces_by_git_class,
    get_surfaces_by_retention,
    get_surfaces_by_root,
)

__all__ = [
    "CLEANUP_EVENT_LOGS_COMMAND",
    "AuthorityClass",
    "CleanupPolicy",
    "GitClass",
    "RetentionRule",
    "STATE_SURFACES",
    "StateFormat",
    "StateRoot",
    "StateSurface",
    "get_runtime_gitignore_entries",
    "get_surfaces_by_authority",
    "get_surfaces_by_git_class",
    "get_surfaces_by_retention",
    "get_surfaces_by_root",
]
