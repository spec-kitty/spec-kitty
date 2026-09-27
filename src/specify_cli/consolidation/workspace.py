"""Dedicated merge worktree lifecycle management.

Implements FR-012: merge operations use a dedicated git worktree at
.kittify/runtime/merge/<mission_id>/workspace/ so the main repo's
checked-out branch is never changed.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# Files in the runtime directory that must survive cleanup for recovery.
_PRESERVED_FILES = {"state.json", "lock"}

__all__ = [
    "create_merge_workspace",
    "cleanup_merge_workspace",
    "get_merge_workspace",
    "get_merge_workspace_path",
    "get_merge_runtime_dir",
    "_worktree_removal_delay",
]


def get_merge_runtime_dir(mission_id: str, repo_root: Path) -> Path:
    """Return the per-mission runtime directory under .kittify/runtime/merge/."""
    return repo_root / ".kittify" / "runtime" / "merge" / mission_id


def get_merge_workspace_path(mission_id: str, repo_root: Path) -> Path:
    """Return the path for the merge worktree workspace."""
    return get_merge_runtime_dir(mission_id, repo_root) / "workspace"


def create_merge_workspace(mission_id: str, target_branch: str, repo_root: Path) -> Path:
    """Create a dedicated git worktree for merge operations.

    The worktree is placed at .kittify/runtime/merge/<mission_id>/workspace/
    so the main repository's checked-out branch is never changed.

    Args:
        mission_id: Mission/feature slug identifier (e.g. "057-feature-name")
        target_branch: The branch to check out in the worktree (e.g. "main")
        repo_root: Path to the repository root

    Returns:
        Path to the created workspace directory
    """
    workspace_path = get_merge_workspace_path(mission_id, repo_root)
    workspace_path.parent.mkdir(parents=True, exist_ok=True)

    if workspace_path.exists():
        # Already exists — verify it is a valid git worktree
        if get_merge_workspace(mission_id, repo_root) is not None:
            return workspace_path
        # Invalid state: remove and recreate
        shutil.rmtree(workspace_path, ignore_errors=True)

    # Use --detach so the worktree isn't bound to the branch name.
    # This allows adding a worktree for a branch that is currently checked out
    # in the main repository (e.g. "main" while still on "main").
    subprocess.run(
        ["git", "worktree", "add", "--detach", str(workspace_path), target_branch],
        cwd=str(repo_root),
        check=True,
    )
    return workspace_path


def _worktree_removal_delay() -> float:
    """Return the delay (in seconds) between worktree removals.

    macOS FSEvents needs time to catch up after worktree removal;
    configurable via SPEC_KITTY_WORKTREE_REMOVAL_DELAY env var.
    """
    env_val = os.environ.get("SPEC_KITTY_WORKTREE_REMOVAL_DELAY")
    if env_val is not None:
        return float(env_val)
    return 2.0 if sys.platform == "darwin" else 0.0


def cleanup_merge_workspace(mission_id: str, repo_root: Path) -> None:
    """Remove the dedicated merge worktree and non-state runtime artifacts.

    Preserves ``state.json`` and ``lock`` files in the runtime directory so
    that interrupted merges can be resumed.  Call :func:`clear_state` after
    confirmed full completion to remove the state file.

    Args:
        mission_id: Mission/feature slug identifier
        repo_root: Path to the repository root
    """
    workspace_path = get_merge_workspace_path(mission_id, repo_root)
    runtime_dir = get_merge_runtime_dir(mission_id, repo_root)

    if workspace_path.exists():
        # Try graceful removal first, then force
        result = subprocess.run(
            ["git", "worktree", "remove", str(workspace_path)],
            cwd=str(repo_root),
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(workspace_path)],
                cwd=str(repo_root),
                capture_output=True,
                check=False,
            )
    elif logger.isEnabledFor(logging.DEBUG):
        logger.debug("Workspace %s does not exist, skipping worktree removal", workspace_path)

    # Selectively delete runtime directory contents, preserving state files.
    if runtime_dir.exists():
        for child in list(runtime_dir.iterdir()):
            if child.name in _PRESERVED_FILES:
                continue
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink(missing_ok=True)

        # Remove the directory itself only if it is now truly empty
        remaining = list(runtime_dir.iterdir())
        if not remaining:
            runtime_dir.rmdir()


def get_merge_workspace(mission_id: str, repo_root: Path) -> Path | None:
    """Return the merge workspace path if it exists and is a valid git worktree.

    Args:
        mission_id: Mission/feature slug identifier
        repo_root: Path to the repository root

    Returns:
        Path to the workspace if valid, None otherwise
    """
    workspace_path = get_merge_workspace_path(mission_id, repo_root)

    if not workspace_path.exists():
        return None

    # Verify it is a registered git worktree
    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        return None

    # Check if our workspace path appears in the worktree list
    workspace_str = str(workspace_path.resolve())
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            listed_path = line[len("worktree "):].strip()
            if listed_path == workspace_str:
                return workspace_path

    return None
