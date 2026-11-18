---
name: spk-admin-git-workflow
description: "Operate Spec Kitty git workflows, worktrees, safe commits, consolidation preflights, stale state checks, and recovery."
---

# spk-admin-git-workflow

Use this skill when Spec Kitty work involves git operations, worktree lifecycle,
branch state, commits, consolidation blockers, or stale repository state.

## Flow

1. Inspect the active mission, branch, worktree, and target branch.
2. Let Spec Kitty-managed git operations run through the CLI when available.
3. Perform manual git operations only when the workflow explicitly requires it.
4. Preserve user changes and avoid destructive repair.
5. Return to `spk-gate-consolidate` or `spk-run-blocked-recovery` after repair.

## Legacy Alias

For detailed git operation matrices and safe-commit guidance, use
`spec-kitty-git-workflow` when available.
