"""Pre-commit hook entry point.

Invoked by the git pre-commit hook installed by hook_installer.py.
Reads staged files, detects WP context from branch name and lanes.json,
loads policy, and runs the commit guard.

Exit code 0 = allow, 1 = block.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from kernel.git import GitCommandError, changed_paths

if TYPE_CHECKING:
    from specify_cli.policy.commit_guard import OwnershipScope


def _resolve_policy_root(worktree_root: Path) -> Path:
    """Resolve the repository root that owns this worktree's POLICY config.

    ``git rev-parse --git-common-dir`` names the shared git dir, which is
    ``<project>/.git`` only for a plain repository and a linked worktree
    (where it is the MAIN repo's ``.git``); a submodule
    (``<super>/.git/modules/<name>``) and a separate git dir live elsewhere,
    so their parents are not a project root. When the common dir is named
    ``.git`` its parent is the project root (the main repo for a linked
    worktree); otherwise the working tree itself is the best policy root
    (#5756).
    """
    result = subprocess.run(
        ["git", "-C", str(worktree_root), "rev-parse", "--git-common-dir"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return worktree_root
    common_dir = Path(result.stdout.strip())
    if not common_dir.is_absolute():
        common_dir = worktree_root / common_dir
    if common_dir.name == ".git":
        return common_dir.parent
    return worktree_root


def main() -> int:
    """Run the commit guard. Returns exit code."""
    from specify_cli.policy.commit_guard import validate_staged_files
    from specify_cli.policy.config import load_policy_config

    # Find repo root.
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return 0  # Not in a git repo — allow

    worktree_root = Path(result.stdout.strip())

    # Find the policy config root, resolved from the real git topology
    # (#5756) rather than by parent-joining the common git dir.
    repo_root = _resolve_policy_root(worktree_root)

    # Get current branch.
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return 0
    branch = result.stdout.strip()

    # Load policy first: a disabled guard must not fail on a staged-files probe.
    policy = load_policy_config(repo_root)
    if not policy.commit_guard.enabled or policy.commit_guard.mode == "off":
        return 0

    # Get staged files (NUL-delimited, so a quoted path is seen as it is).
    # Renames are detected as before: only the new path is listed.
    try:
        staged = [str(path) for path in changed_paths(worktree_root, cached=True, renames=True)]
    except GitCommandError as exc:
        # Guard (FR-013): a staged-files probe that failed must not read as
        # "nothing staged". Fail closed and say why.
        print(f"[spec-kitty guard] BLOCKED: could not list staged files: {exc}", file=sys.stderr)
        return 1
    if not staged:
        return 0

    # Try to find owned_files from active WP context.
    ownership_scope = _detect_ownership_scope(worktree_root, repo_root, branch)

    # Run guard.
    guard_result = validate_staged_files(
        staged,
        ownership_scope.owned_files,
        branch,
        policy.commit_guard,
        ownership_scope=ownership_scope,
    )

    if guard_result.warnings:
        for w in guard_result.warnings:
            print(f"[spec-kitty guard] WARNING: {w}", file=sys.stderr)

    if not guard_result.allowed:
        for v in guard_result.violations:
            print(f"[spec-kitty guard] BLOCKED: {v}", file=sys.stderr)
        print("[spec-kitty guard] Commit blocked by ownership policy.", file=sys.stderr)
        return 1

    return 0


def _detect_ownership_scope(
    worktree_root: Path,
    repo_root: Path,
    branch: str,
) -> OwnershipScope:
    """Resolve active WP ownership scope for the current lane branch."""
    from specify_cli.policy.commit_guard import OwnershipScope

    _ = worktree_root  # Reserved for future path-based diagnostics.
    try:
        from specify_cli.workspace.context import resolve_active_wp_for_branch

        resolved = resolve_active_wp_for_branch(repo_root, branch)
        return OwnershipScope(
            owned_files=list(resolved.owned_files),
            active_wp_id=resolved.wp_id,
            lane_id=resolved.lane_id,
            context_source=resolved.context_source,
            diagnostic_code=resolved.diagnostic_code,
            diagnostic_message=resolved.diagnostic_message,
            warnings=list(resolved.warnings),
        )
    except Exception as exc:
        return OwnershipScope(
            owned_files=[],
            context_source="workspace_context",
            diagnostic_code="ACTIVE_WP_CONTEXT_ERROR",
            diagnostic_message=f"ACTIVE_WP_CONTEXT_ERROR: Could not resolve active WP ownership: {exc}",
        )


if __name__ == "__main__":
    sys.exit(main())
