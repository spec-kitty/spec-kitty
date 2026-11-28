"""Workspace strategy for planning-artifact work packages.

Provides :func:`create_planning_workspace`, which returns the repository root
checkout path, the planning workspace of every Mission but one.

Planning-artifact WPs produce documentation/specification changes only (no
source-code changes). They do not need an isolated lane worktree: they work in
the planning surface, the checkout that holds the branch their planning lane
writes to:

* the repository root checkout, for an explicit-topology, landed or legacy
  Mission and for a ``single_branch`` Mission;
* the checkout holding the Mission branch (the coordination worktree once the
  topology is settled) before a default Mission lands (#7860). That shape is
  decided by :func:`specify_cli.coordination.planning_commit.planning_lane_target`
  in ``workspace.context``, not here.

The function returns ``repo_root`` so callers receive a consistent ``Path``
whether the WP is ``code_change`` (lane worktree) or ``planning_artifact``.
"""

from __future__ import annotations

from pathlib import Path


def create_planning_workspace(
    mission_slug: str,  # noqa: ARG001
    wp_code: str,  # noqa: ARG001
    owned_files: list[str],  # noqa: ARG001
    repo_root: Path,
) -> Path:
    """Return the repository root checkout path for a planning-artifact work package.

    No worktree is created. Before a default Mission lands its planning work
    package is worked in the checkout holding the Mission branch instead
    (#7860); ``workspace.context`` resolves that shape before it calls this.

    Args:
        mission_slug: Feature identifier (e.g. ``"057-canonical-context-architecture-cleanup"``).
        wp_code: Work-package code (e.g. ``"WP04"``).
        owned_files: Glob patterns describing files owned by this WP.  Not
            used for workspace creation but validated to be accessible under
            ``repo_root`` (informational only).
        repo_root: Absolute path to the repository root.

    Returns:
        ``repo_root`` — the in-repo workspace path.
    """
    if not repo_root.is_dir():
        raise ValueError(f"repo_root does not exist or is not a directory: {repo_root}")
    return repo_root
