"""
VCS Protocol Module
===================

This module defines the VCSProtocol interface that GitVCS implements.
The protocol uses Python's typing.Protocol for structural subtyping.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from .types import (
    ChangeInfo,
    ConflictInfo,
    VCSBackend,
    VCSCapabilities,
    WorkspaceCreateResult,
    WorkspaceInfo,
)


@runtime_checkable
class VCSProtocol(Protocol):
    """
    Interface contract for VCS backends.

    GitVCS must implement this protocol.
    Operations not supported by a backend should raise VCSCapabilityError.

    This protocol is runtime-checkable, so you can use:
        isinstance(obj, VCSProtocol)
    to verify an object implements the interface.
    """

    @property
    def backend(self) -> VCSBackend:
        """Return which backend this is (GIT)."""
        ...

    @property
    def capabilities(self) -> VCSCapabilities:
        """Return capabilities of this backend."""
        ...

    # =========================================================================
    # Workspace Operations (Core - Required)
    # =========================================================================

    def create_workspace(
        self,
        workspace_path: Path,
        workspace_name: str,
        base_branch: str | None = None,
        base_commit: str | None = None,
        repo_root: Path | None = None,
    ) -> WorkspaceCreateResult:
        """
        Create a new workspace for a work package.

        Creates a full-checkout workspace. Sparse checkout is not supported;
        all files are visible in every workspace. Access control is handled at
        the ownership layer.

        Args:
            workspace_path: Where to create the workspace
            workspace_name: Name for the workspace (e.g., "015-feature-lane-a")
            base_branch: Branch to base the workspace on
            base_commit: Specific commit to base on (alternative to branch)
            repo_root: Repository root for command execution when caller already knows it

        Returns:
            WorkspaceCreateResult with workspace info or error

        Implementation notes:
            - Git: Uses `git worktree add`
        """
        ...

    def get_workspace_info(self, workspace_path: Path) -> WorkspaceInfo | None:
        """
        Get information about a workspace.

        Args:
            workspace_path: Path to the workspace

        Returns:
            WorkspaceInfo or None if not a valid workspace
        """
        ...

    def list_workspaces(self, repo_root: Path) -> list[WorkspaceInfo]:
        """
        List all workspaces for a repository.

        Args:
            repo_root: Root of the repository

        Returns:
            List of WorkspaceInfo for all workspaces
        """
        ...

    # =========================================================================
    # Synchronization Operations (Core - Required)
    # =========================================================================

    def is_workspace_stale(self, workspace_path: Path) -> bool:
        """
        Check if workspace needs sync (base has changed).

        Args:
            workspace_path: Path to the workspace

        Returns:
            True if sync is needed, False if up-to-date
        """
        ...

    # =========================================================================
    # Conflict Operations (Core - Required)
    # =========================================================================

    def detect_conflicts(self, workspace_path: Path) -> list[ConflictInfo]:
        """
        Detect conflicts in a workspace.

        Args:
            workspace_path: Path to the workspace

        Returns:
            List of ConflictInfo for all conflicted files

        Implementation notes:
            - Git: Parse conflict markers in working tree
        """
        ...

    def has_conflicts(self, workspace_path: Path) -> bool:
        """
        Check if workspace has any unresolved conflicts.

        Args:
            workspace_path: Path to the workspace

        Returns:
            True if conflicts exist, False otherwise
        """
        ...

    # =========================================================================
    # Commit/Change Operations (Core - Required)
    # =========================================================================

    def get_current_change(self, workspace_path: Path) -> ChangeInfo | None:
        """
        Get info about current working copy commit/change.

        Args:
            workspace_path: Path to the workspace

        Returns:
            ChangeInfo for current HEAD/working copy, None if invalid
        """
        ...

    def get_changes(
        self,
        repo_path: Path,
        revision_range: str | None = None,
        limit: int | None = None,
    ) -> list[ChangeInfo]:
        """
        Get list of changes/commits.

        Args:
            repo_path: Repository path
            revision_range: Git revision range
            limit: Maximum number to return

        Returns:
            List of ChangeInfo
        """
        ...

    # =========================================================================
    # Repository Operations (Core - Required)
    # =========================================================================

    def init_repo(
        self,
        path: Path,
        colocate: bool = True,
    ) -> bool:
        """
        Initialize a new repository.

        Args:
            path: Where to initialize
            colocate: Whether to colocate

        Returns:
            True if successful, False otherwise
        """
        ...

    def is_repo(self, path: Path) -> bool:
        """
        Check if path is inside a repository of this backend type.

        Args:
            path: Path to check

        Returns:
            True if valid repository of this backend type
        """
        ...

    def get_repo_root(self, path: Path) -> Path | None:
        """
        Get root directory of repository containing path.

        Args:
            path: Path within the repository

        Returns:
            Repository root or None if not in a repo
        """
        ...
