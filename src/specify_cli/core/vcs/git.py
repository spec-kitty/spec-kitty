"""
Git VCS Implementation
======================

Full implementation of GitVCS that wraps git CLI commands.
Implements VCSProtocol for workspace management, sync operations,
conflict detection, and commit operations.

This module wraps existing git operations from git_ops.py where appropriate
and adds VCS abstraction layer functionality.

Worktrees receive a full checkout; access control is handled at the ownership
layer.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from kernel.clock import from_epoch, now_utc, parse_iso

from .types import (
    ChangeInfo,
    ConflictInfo,
    ConflictType,
    GIT_CAPABILITIES,
    OperationInfo,
    VCSBackend,
    VCSCapabilities,
    WorkspaceCreateResult,
    WorkspaceInfo,
)

# Import existing git helpers where they provide reusable functionality
from ..git_preflight import run_git_preflight
from ..git_ops import get_current_branch, is_git_repo


class GitVCS:
    """
    Git VCS implementation.

    Implements VCSProtocol for git repositories, wrapping git CLI commands
    for workspace management, synchronization, conflict detection, and commits.
    """

    @property
    def backend(self) -> VCSBackend:
        """Return which backend this is."""
        return VCSBackend.GIT

    @property
    def capabilities(self) -> VCSCapabilities:
        """Return capabilities of this backend."""
        return GIT_CAPABILITIES

    # =========================================================================
    # Workspace Operations
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
        Create a new git worktree for a work package.

        Creates a full-checkout worktree. All files are visible in the
        workspace; access control is handled at the ownership layer.

        Args:
            workspace_path: Where to create the workspace
            workspace_name: Name for the workspace branch (e.g., "015-feature-lane-a")
            base_branch: Branch to base the workspace on
            base_commit: Specific commit to base on (alternative to branch)
            repo_root: Root of the git repository (auto-detected if not provided)

        Returns:
            WorkspaceCreateResult with workspace info or error
        """
        try:
            # Ensure parent directory exists
            workspace_path.parent.mkdir(parents=True, exist_ok=True)

            # Find repo root to run git commands from
            if repo_root is None:
                repo_root = self.get_repo_root(workspace_path.parent)
                if repo_root is None:
                    return WorkspaceCreateResult(
                        success=False,
                        workspace=None,
                        error="Could not find git repository root",
                    )

            preflight = run_git_preflight(repo_root, check_worktree_list=True)
            if not preflight.passed:
                issue = preflight.first_error
                detail = issue.message if issue else "Git preflight failed."
                if issue and issue.command:
                    detail = f"{detail} Run: {issue.command}"
                return WorkspaceCreateResult(
                    success=False,
                    workspace=None,
                    error=detail,
                    error_code=issue.code if issue else "GIT_PREFLIGHT_FAILED",
                )

            # Build the git worktree add command
            cmd = ["git", "worktree", "add"]

            # Determine the base point for the new branch
            if base_commit:
                # Branch from specific commit
                cmd.extend(["-b", workspace_name, str(workspace_path), base_commit])
            elif base_branch:
                # Branch from specified branch
                cmd.extend(["-b", workspace_name, str(workspace_path), base_branch])
            else:
                # Default: branch from current HEAD
                cmd.extend(["-b", workspace_name, str(workspace_path)])

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
                cwd=str(repo_root),
            )

            if result.returncode != 0:
                return WorkspaceCreateResult(
                    success=False,
                    workspace=None,
                    error=result.stderr.strip() or "Failed to create worktree",
                )

            # Get workspace info for the newly created workspace
            workspace_info = self.get_workspace_info(workspace_path)

            return WorkspaceCreateResult(
                success=True,
                workspace=workspace_info,
                error=None,
            )

        except subprocess.TimeoutExpired:
            return WorkspaceCreateResult(
                success=False,
                workspace=None,
                error="Worktree creation timed out",
            )
        except OSError as e:
            return WorkspaceCreateResult(
                success=False,
                workspace=None,
                error=f"OS error: {e}",
            )

    def _get_git_dir(self, workspace_path: Path) -> Path | None:
        """
        Get the .git directory for a workspace (handles worktrees).

        For worktrees, .git is a file pointing to the actual git directory.
        For regular repos, .git is a directory.

        Args:
            workspace_path: Path to the workspace

        Returns:
            Path to git directory, or None if not found
        """
        git_path = workspace_path / ".git"

        if not git_path.exists():
            return None

        # For worktrees, .git is a file with "gitdir: /path/to/git/dir"
        if git_path.is_file():
            try:
                git_content = git_path.read_text().strip()
                if git_content.startswith("gitdir:"):
                    git_dir_str = git_content.split(":", 1)[1].strip()
                    git_dir = Path(git_dir_str)
                    if git_dir.exists():
                        return git_dir
            except (OSError, IndexError):
                return None

        # For regular repos, .git is a directory
        elif git_path.is_dir():
            return git_path

        return None

    def remove_workspace(self, workspace_path: Path) -> bool:
        """
        Remove a git worktree.

        Args:
            workspace_path: Path to the workspace to remove

        Returns:
            True if successful, False otherwise
        """
        try:
            # Find repo root to run git commands from
            repo_root = self.get_repo_root(workspace_path)
            if repo_root is None:
                # Try parent directory if workspace_path is the worktree itself
                repo_root = self.get_repo_root(workspace_path.parent)
            if repo_root is None:
                return False

            result = subprocess.run(
                ["git", "worktree", "remove", str(workspace_path), "--force"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                cwd=str(repo_root),
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            return False

    def get_workspace_info(self, workspace_path: Path) -> WorkspaceInfo | None:
        """
        Get information about a workspace.

        Args:
            workspace_path: Path to the workspace

        Returns:
            WorkspaceInfo or None if not a valid workspace
        """
        workspace_path = workspace_path.resolve()

        if not workspace_path.exists():
            return None

        # Check if it's a worktree
        git_dir = workspace_path / ".git"
        if not git_dir.exists():
            return None

        try:
            # Get current branch using existing helper from git_ops.py
            # get_current_branch() already returns None for detached HEAD
            current_branch = get_current_branch(workspace_path)

            # Get current commit
            commit_result = subprocess.run(
                ["git", "-C", str(workspace_path), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
            )
            current_commit = commit_result.stdout.strip() if commit_result.returncode == 0 else ""

            # Check for uncommitted changes
            status_result = subprocess.run(
                ["git", "-C", str(workspace_path), "status", "--porcelain"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
            )
            has_uncommitted = bool(status_result.stdout.strip())

            # Check for conflicts
            has_conflicts = self.has_conflicts(workspace_path)

            # Derive workspace name from path
            workspace_name = workspace_path.name

            # Try to determine base branch from tracking
            base_branch = self._get_tracking_branch(workspace_path)

            return WorkspaceInfo(
                name=workspace_name,
                path=workspace_path,
                backend=VCSBackend.GIT,
                is_colocated=False,
                current_branch=current_branch,
                current_change_id=None,  # Git doesn't have change IDs
                current_commit_id=current_commit,
                base_branch=base_branch,
                base_commit_id=None,  # Would need to track this separately
                is_stale=self.is_workspace_stale(workspace_path),
                has_conflicts=has_conflicts,
                has_uncommitted=has_uncommitted,
            )

        except (subprocess.TimeoutExpired, OSError):
            return None

    def list_workspaces(self, repo_root: Path) -> list[WorkspaceInfo]:
        """
        List all worktrees for a repository.

        Args:
            repo_root: Root of the repository

        Returns:
            List of WorkspaceInfo for all worktrees
        """
        try:
            result = subprocess.run(
                ["git", "-C", str(repo_root), "worktree", "list", "--porcelain"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )

            if result.returncode != 0:
                return []

            workspaces = []
            lines = result.stdout.strip().split("\n")
            current_path = None

            for line in lines:
                if line.startswith("worktree "):
                    current_path = Path(line[9:])
                elif line == "" and current_path:
                    # End of entry
                    info = self.get_workspace_info(current_path)
                    if info:
                        workspaces.append(info)
                    current_path = None

            # Don't forget the last entry
            if current_path:
                info = self.get_workspace_info(current_path)
                if info:
                    workspaces.append(info)

            return workspaces

        except (subprocess.TimeoutExpired, OSError):
            return []

    def is_workspace_stale(self, workspace_path: Path) -> bool:
        """
        Check if workspace needs sync (base has changed).

        Args:
            workspace_path: Path to the workspace

        Returns:
            True if sync is needed, False if up-to-date
        """
        try:
            # Get the tracking branch
            base_branch = self._get_tracking_branch(workspace_path)
            if not base_branch:
                return False

            # Compare HEAD with upstream
            result = subprocess.run(
                [
                    "git",
                    "-C",
                    str(workspace_path),
                    "rev-list",
                    "--count",
                    f"HEAD..{base_branch}",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )

            if result.returncode != 0:
                return False

            # If there are commits in upstream not in HEAD, we're stale
            count = int(result.stdout.strip()) if result.stdout.strip() else 0
            return count > 0

        except (subprocess.TimeoutExpired, OSError, ValueError):
            return False

    # =========================================================================
    # Conflict Operations
    # =========================================================================

    def detect_conflicts(self, workspace_path: Path) -> list[ConflictInfo]:
        """
        Detect conflicts in a workspace.

        Args:
            workspace_path: Path to the workspace

        Returns:
            List of ConflictInfo for all conflicted files
        """
        try:
            # Get list of conflicted files
            result = subprocess.run(
                ["git", "-C", str(workspace_path), "diff", "--name-only", "--diff-filter=U"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )

            if result.returncode != 0 or not result.stdout.strip():
                # Also check git status for unmerged paths
                status_result = subprocess.run(
                    ["git", "-C", str(workspace_path), "status", "--porcelain"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=30,
                )

                conflicts = []
                for line in status_result.stdout.strip().split("\n"):
                    if line and line[:2] in ("UU", "AA", "DD", "AU", "UA", "DU", "UD"):
                        file_path = Path(line[3:].strip())
                        conflict_type = self._status_to_conflict_type(line[:2])
                        full_path = workspace_path / file_path

                        line_ranges = None
                        if full_path.exists() and conflict_type == ConflictType.CONTENT:
                            line_ranges = self._parse_conflict_markers(full_path)

                        conflicts.append(
                            ConflictInfo(
                                file_path=file_path,
                                conflict_type=conflict_type,
                                line_ranges=line_ranges,
                                sides=2,
                                is_resolved=False,
                                our_content=None,
                                their_content=None,
                                base_content=None,
                            )
                        )
                return conflicts

            conflicts = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue

                file_path = Path(line.strip())
                full_path = workspace_path / file_path

                # Parse conflict markers to get line ranges
                line_ranges = None
                if full_path.exists():
                    line_ranges = self._parse_conflict_markers(full_path)

                conflicts.append(
                    ConflictInfo(
                        file_path=file_path,
                        conflict_type=ConflictType.CONTENT,
                        line_ranges=line_ranges,
                        sides=2,
                        is_resolved=False,
                        our_content=None,  # Could extract from markers
                        their_content=None,
                        base_content=None,
                    )
                )

            return conflicts

        except (subprocess.TimeoutExpired, OSError):
            return []

    def has_conflicts(self, workspace_path: Path) -> bool:
        """
        Check if workspace has any unresolved conflicts.

        Args:
            workspace_path: Path to the workspace

        Returns:
            True if conflicts exist, False otherwise
        """
        try:
            result = subprocess.run(
                ["git", "-C", str(workspace_path), "diff", "--name-only", "--diff-filter=U"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )

            if result.returncode == 0 and result.stdout.strip():
                return True

            # Also check git status
            status_result = subprocess.run(
                ["git", "-C", str(workspace_path), "status", "--porcelain"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )

            for line in status_result.stdout.strip().split("\n"):
                if line and line[:2] in ("UU", "AA", "DD", "AU", "UA", "DU", "UD"):
                    return True

            return False

        except (subprocess.TimeoutExpired, OSError):
            return False

    # =========================================================================
    # Commit/Change Operations
    # =========================================================================

    def get_current_change(self, workspace_path: Path) -> ChangeInfo | None:
        """
        Get info about current working copy commit/change.

        Args:
            workspace_path: Path to the workspace

        Returns:
            ChangeInfo for current HEAD, None if invalid
        """
        try:
            result = subprocess.run(
                [
                    "git",
                    "-C",
                    str(workspace_path),
                    "log",
                    "-1",
                    "--format=%H|%an|%ae|%at|%s|%P|%B",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )

            if result.returncode != 0 or not result.stdout.strip():
                return None

            return self._parse_log_line(result.stdout.strip())

        except (subprocess.TimeoutExpired, OSError):
            return None

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
            revision_range: Git revision range (e.g., "main..HEAD")
            limit: Maximum number to return

        Returns:
            List of ChangeInfo
        """
        try:
            cmd = [
                "git",
                "-C",
                str(repo_path),
                "log",
                "--format=%H|%an|%ae|%at|%s|%P",
            ]

            if limit:
                cmd.append(f"-{limit}")

            if revision_range:
                cmd.append(revision_range)

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
            )

            if result.returncode != 0:
                return []

            changes = []
            for line in result.stdout.strip().split("\n"):
                if line:
                    change = self._parse_log_line_short(line)
                    if change:
                        changes.append(change)

            return changes

        except (subprocess.TimeoutExpired, OSError):
            return []

    def commit(
        self,
        workspace_path: Path,
        message: str,
        paths: list[Path] | None = None,
    ) -> ChangeInfo | None:
        """
        Create a commit with current changes.

        Args:
            workspace_path: Workspace to commit in
            message: Commit message
            paths: Specific paths to commit (None = all)

        Returns:
            ChangeInfo for new commit, None if nothing to commit
        """
        try:
            # Stage files
            if paths:
                for path in paths:
                    subprocess.run(
                        ["git", "-C", str(workspace_path), "add", str(path)],
                        capture_output=True,
                        timeout=30,
                    )
            else:
                subprocess.run(
                    ["git", "-C", str(workspace_path), "add", "-A"],
                    capture_output=True,
                    timeout=30,
                )

            # Check if there are staged changes
            status_result = subprocess.run(
                ["git", "-C", str(workspace_path), "diff", "--cached", "--quiet"],
                capture_output=True,
                timeout=30,
            )

            if status_result.returncode == 0:
                # No changes to commit
                return None

            # Commit
            commit_result = subprocess.run(
                ["git", "-C", str(workspace_path), "commit", "-m", message],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
            )

            if commit_result.returncode != 0:
                return None

            # Return info about the new commit
            return self.get_current_change(workspace_path)

        except (subprocess.TimeoutExpired, OSError):
            return None

    # =========================================================================
    # Repository Operations
    # =========================================================================

    def init_repo(self, path: Path, colocate: bool = True) -> bool:  # noqa: ARG002
        """
        Initialize a new git repository.

        Args:
            path: Where to initialize
            colocate: Ignored for git (only relevant for jj)

        Returns:
            True if successful, False otherwise
        """
        try:
            path.mkdir(parents=True, exist_ok=True)
            result = subprocess.run(
                ["git", "init"],
                cwd=str(path),
                capture_output=True,
                timeout=30,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            return False

    def is_repo(self, path: Path) -> bool:
        """
        Check if path is inside a git repository.

        Wraps existing is_git_repo from git_ops.py.

        Args:
            path: Path to check

        Returns:
            True if valid git repository
        """
        return is_git_repo(path)

    def get_repo_root(self, path: Path) -> Path | None:
        """
        Get root directory of repository containing path.

        Args:
            path: Path within the repository

        Returns:
            Repository root or None if not in a repo
        """
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=str(path),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
            )

            if result.returncode == 0 and result.stdout.strip():
                return Path(result.stdout.strip())
            return None

        except (subprocess.TimeoutExpired, OSError):
            return None

    # =========================================================================
    # Private Helper Methods
    # =========================================================================

    def _get_tracking_branch(self, workspace_path: Path) -> str | None:
        """Get the tracking branch for the current branch."""
        try:
            result = subprocess.run(
                [
                    "git",
                    "-C",
                    str(workspace_path),
                    "rev-parse",
                    "--abbrev-ref",
                    "--symbolic-full-name",
                    "@{u}",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except (subprocess.TimeoutExpired, OSError):
            return None

    def _parse_conflict_markers(self, file_path: Path) -> list[tuple[int, int]]:
        """Find line ranges with conflict markers."""
        ranges = []
        in_conflict = False
        start_line = 0

        try:
            with open(file_path, encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f, 1):
                    if line.startswith("<<<<<<<"):
                        in_conflict = True
                        start_line = i
                    elif line.startswith(">>>>>>>") and in_conflict:
                        ranges.append((start_line, i))
                        in_conflict = False
        except OSError:
            pass

        return ranges

    def _status_to_conflict_type(self, status: str) -> ConflictType:
        """Convert git status code to ConflictType."""
        if status == "UU":
            return ConflictType.CONTENT
        elif status == "AA":
            return ConflictType.ADD_ADD
        elif status == "DD" or status in ("AU", "UA") or status in ("DU", "UD"):
            return ConflictType.MODIFY_DELETE
        return ConflictType.CONTENT

    def _parse_log_line(self, line: str) -> ChangeInfo | None:
        """Parse a git log line with full body."""
        try:
            parts = line.split("|", 6)
            if len(parts) < 6:
                return None

            commit_id = parts[0]
            author = parts[1]
            author_email = parts[2]
            timestamp = from_epoch(int(parts[3]))
            message = parts[4]
            parents = parts[5].split() if parts[5] else []
            message_full = parts[6] if len(parts) > 6 else message

            return ChangeInfo(
                change_id=None,  # Git doesn't have change IDs
                commit_id=commit_id,
                message=message,
                message_full=message_full,
                author=author,
                author_email=author_email,
                timestamp=timestamp,
                parents=parents,
                is_merge=len(parents) > 1,
                is_conflicted=False,
                is_empty=False,
            )
        except (ValueError, IndexError):
            return None

    def _parse_log_line_short(self, line: str) -> ChangeInfo | None:
        """Parse a git log line without full body."""
        try:
            parts = line.split("|", 5)
            if len(parts) < 5:
                return None

            commit_id = parts[0]
            author = parts[1]
            author_email = parts[2]
            timestamp = from_epoch(int(parts[3]))
            message = parts[4]
            parents = parts[5].split() if len(parts) > 5 and parts[5] else []

            return ChangeInfo(
                change_id=None,
                commit_id=commit_id,
                message=message,
                message_full=message,
                author=author,
                author_email=author_email,
                timestamp=timestamp,
                parents=parents,
                is_merge=len(parents) > 1,
                is_conflicted=False,
                is_empty=False,
            )
        except (ValueError, IndexError):
            return None


# =============================================================================
# Git-Specific Standalone Functions
# =============================================================================


def git_get_reflog(repo_path: Path, limit: int = 20) -> list[OperationInfo]:
    """
    Get git reflog as operation history.

    git-specific: Less powerful than jj operation log, but provides
    some visibility into repository history.

    Args:
        repo_path: Repository path
        limit: Maximum number of entries to return

    Returns:
        List of OperationInfo from reflog
    """
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(repo_path),
                "reflog",
                f"-{limit}",
                "--format=%H|%gD|%gs|%ci",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )

        if result.returncode != 0:
            return []

        operations = []
        for i, line in enumerate(result.stdout.strip().split("\n")):
            if not line:
                continue
            try:
                parts = line.split("|", 3)
                if len(parts) < 4:
                    continue

                commit_id = parts[0]
                description = parts[2]
                timestamp_str = parts[3]

                # Parse timestamp
                try:
                    timestamp = parse_iso(timestamp_str.replace(" ", "T").replace(" ", ""))
                except ValueError:
                    timestamp = now_utc()

                operations.append(
                    OperationInfo(
                        operation_id=f"reflog-{i}",
                        timestamp=timestamp,
                        description=description,
                        heads=[commit_id],
                        working_copy_commit=commit_id,
                        is_undoable=False,  # Git reflog entries aren't truly undoable
                        parent_operation=f"reflog-{i + 1}" if i < limit - 1 else None,
                    )
                )
            except (ValueError, IndexError):
                continue

        return operations

    except (subprocess.TimeoutExpired, OSError):
        return []


def git_stash(workspace_path: Path, message: str | None = None) -> bool:
    """
    Stash working directory changes.

    git-specific: jj doesn't need stash (working copy always committed).

    Args:
        workspace_path: Workspace path
        message: Optional stash message

    Returns:
        True if successful
    """
    try:
        cmd = ["git", "-C", str(workspace_path), "stash", "push"]
        if message:
            cmd.extend(["-m", message])

        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=30,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def git_stash_pop(workspace_path: Path) -> bool:
    """
    Pop stashed changes.

    git-specific: jj doesn't need stash.

    Args:
        workspace_path: Workspace path

    Returns:
        True if successful
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(workspace_path), "stash", "pop"],
            capture_output=True,
            timeout=30,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


# =============================================================================
# Canonical merge-base / diff surface
# =============================================================================
#
# Single source of truth for the "git merge-base -> git diff --name-only"
# idiom (mission merge-base-diff-ssot-01KX44SD). Do NOT add another inline
# copy of this idiom elsewhere — consume these primitives instead. This is
# deliberately separate from GitVCS's internal merge-base usage for rebase
# statistics (~L415 above), which is a different comparison and out of scope.


def git_merge_base(repo: Path, ref_a: str, ref_b: str) -> str | None:
    """
    Return the merge-base commit SHA between two refs, or None.

    Runs ``git merge-base <ref_a> <ref_b>`` in ``repo``. Never raises for a
    git non-zero exit; degrades to None instead.

    Args:
        repo: Repository/worktree path to run the command in.
        ref_a: First ref (commit-ish).
        ref_b: Second ref (commit-ish).

    Returns:
        The stripped merge-base SHA, or None on non-zero exit or empty stdout.
    """
    result = subprocess.run(
        ["git", "merge-base", ref_a, ref_b],
        cwd=str(repo),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        return None
    merge_base = result.stdout.strip()
    return merge_base or None


def git_diff_names(
    repo: Path,
    base: str,
    head: str,
    *,
    pathspec: str | None = None,
    diff_filter: str | None = None,
    timeout: float | None = None,
) -> tuple[str, ...]:
    """
    Return the ``--name-only`` changed-file set between two refs.

    Runs ``git diff --name-only [--diff-filter=<diff_filter>] <base> <head>
    [-- <pathspec>]`` in ``repo``, using the two-arg ``<base> <head>`` form
    (equivalent to ``<base>..<head>`` for ``--name-only``). ``base``/``head``
    are explicit refs — this does not assume ``head`` is ``HEAD``, so callers
    that need to diff a non-HEAD branch target (e.g. an upstream-only
    planning check) can do so directly.

    Args:
        repo: Repository/worktree path to run the command in.
        base: Base ref (commit-ish), typically a merge-base SHA.
        head: Head ref (commit-ish) to diff against ``base``.
        pathspec: Optional pathspec restricting the diff (``-- <pathspec>``).
        diff_filter: Optional ``--diff-filter`` value (e.g. ``"AMR"``).
        timeout: Optional subprocess timeout (seconds). When set and the diff
            exceeds it, ``subprocess.TimeoutExpired`` propagates — callers that
            want empty-on-timeout must wrap the call (mirrors ``subprocess``
            semantics; the surface never silently swallows a timeout).

    Returns:
        Tuple of stripped, non-empty repo-relative paths; empty tuple on
        non-zero exit.
    """
    result = git_diff_names_checked(repo, base, head, pathspec=pathspec, diff_filter=diff_filter, timeout=timeout)
    return () if result is None else result


def git_diff_names_checked(
    repo: Path,
    base: str,
    head: str,
    *,
    pathspec: str | None = None,
    diff_filter: str | None = None,
    timeout: float | None = None,
) -> tuple[str, ...] | None:
    """Fail-distinguishing variant of :func:`git_diff_names`.

    Identical command and output to :func:`git_diff_names`, except the failure
    mode is *distinguishable*: returns ``None`` when the ``git diff`` command
    exits non-zero, versus an empty tuple when the diff genuinely reports no
    changed files. Use this from **fail-closed** callers that must treat an
    undetermined diff differently from an empty one (e.g. the dependency-graph
    upstream-only-planning check, where a failed diff must block rather than be
    read as "no changes"). Callers that want empty-on-failure should use
    :func:`git_diff_names`, which is a thin wrapper mapping ``None`` → ``()``.

    Args:
        repo: Repository/worktree path to run the command in.
        base: Base ref (commit-ish), typically a merge-base SHA.
        head: Head ref (commit-ish) to diff against ``base``.
        pathspec: Optional pathspec restricting the diff (``-- <pathspec>``).
        diff_filter: Optional ``--diff-filter`` value (e.g. ``"AMR"``).
        timeout: Optional subprocess timeout (seconds); ``TimeoutExpired``
            propagates (not swallowed).

    Returns:
        Tuple of stripped, non-empty repo-relative paths on success (possibly
        empty); ``None`` on non-zero exit.
    """
    cmd = ["git", "diff", "--name-only"]
    if diff_filter:
        cmd.append(f"--diff-filter={diff_filter}")
    cmd.extend([base, head])
    if pathspec:
        cmd.extend(["--", pathspec])

    result = subprocess.run(
        cmd,
        cwd=str(repo),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=timeout,
    )
    if result.returncode != 0:
        return None
    return tuple(line.strip() for line in result.stdout.splitlines() if line.strip())


def git_ls_tree_names_checked(
    repo: Path,
    rev: str,
    path: str,
    *,
    timeout: float | None = None,
) -> tuple[str, ...] | None:
    """Fail-distinguishing ``git ls-tree -r --name-only <rev> <path>``.

    Lists every blob recorded at *rev* under *path*, recursively (a
    directory path with a trailing ``/`` lists all files below it; a file
    path names the entry itself). The failure mode is *distinguishable*:
    returns ``None`` when ``git ls-tree`` exits non-zero (unknown *rev*,
    not a repository), versus an empty tuple when *rev* simply records
    nothing at *path*. Use it from fail-closed callers that must not read an
    unreadable base tree as "nothing there".

    Args:
        repo: Repository/worktree path to run the command in.
        rev: Tree-ish to inspect (commit-ish or tree SHA).
        path: Repo-relative path to list. Passed verbatim; callers own the
            safety of the segments they compose into it.
        timeout: Optional subprocess timeout (seconds); ``TimeoutExpired``
            propagates (not swallowed).

    Returns:
        Tuple of stripped, non-empty repo-relative entry names on success
        (possibly empty); ``None`` on non-zero exit.
    """
    result = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", rev, path],
        cwd=str(repo),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=timeout,
    )
    if result.returncode != 0:
        return None
    return tuple(line.strip() for line in result.stdout.splitlines() if line.strip())


def git_rev_list_count(
    repo: Path,
    rev_range: str,
    *,
    pathspecs: tuple[str, ...] | None = None,
    timeout: float | None = None,
) -> int | None:
    """Fail-closed ``git rev-list --count <rev_range> [-- <pathspecs>]``.

    Counts commits in a revision range, optionally restricted by pathspecs
    (a commit counts when its changed-path set intersects the pathspec
    match — exclude pathspecs such as ``":(exclude)kitty-specs"`` subtract
    a subtree from that match). Returns ``None`` when the command exits
    non-zero or its stdout is not a bare non-negative integer, so callers
    can fail closed instead of reading an undetermined count as zero
    (mirrors the ``*_checked`` fail-distinguishing primitives).

    Args:
        repo: Repository/worktree path to run the command in.
        rev_range: Revision range or rev-set argument, e.g. ``"HEAD..main"``.
        pathspecs: Optional pathspecs passed after ``--``; when given, only
            commits touching at least one matching path are counted.
        timeout: Optional subprocess timeout (seconds); ``TimeoutExpired``
            propagates (not swallowed).

    Returns:
        The commit count on success; ``None`` on non-zero exit or
        non-numeric stdout.
    """
    cmd = ["git", "rev-list", "--count", rev_range]
    if pathspecs:
        cmd.extend(["--", *pathspecs])
    result = subprocess.run(
        cmd,
        cwd=str(repo),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=timeout,
    )
    if result.returncode != 0:
        return None
    stdout = result.stdout.strip()
    if not stdout.isdigit():
        return None
    return int(stdout)


def merge_base_changed_files(
    worktree: Path,
    base_ref: str,
    *,
    pathspec: str | None = None,
    diff_filter: str | None = None,
) -> tuple[str, ...]:
    """
    HEAD-relative convenience: changed files since the merge-base with ``base_ref``.

    Composes ``git_merge_base(worktree, "HEAD", base_ref)`` then
    ``git_diff_names(worktree, merge_base, "HEAD", ...)``. Not for diff
    targets other than HEAD — callers that need to diff a non-HEAD branch
    target (e.g. an upstream-only planning check) must call
    ``git_merge_base``/``git_diff_names`` directly instead.

    Args:
        worktree: Repository/worktree path to run the commands in.
        base_ref: Ref to compute the merge-base against HEAD.
        pathspec: Optional pathspec restricting the diff (``-- <pathspec>``).
        diff_filter: Optional ``--diff-filter`` value (e.g. ``"AMR"``).

    Returns:
        Changed-file tuple; empty tuple on any failure (no merge-base, or
        diff failure).
    """
    merge_base = git_merge_base(worktree, "HEAD", base_ref)
    if merge_base is None:
        return ()
    return git_diff_names(worktree, merge_base, "HEAD", pathspec=pathspec, diff_filter=diff_filter)
