---
title: How to Sync Workspaces
description: 'How to sync workspaces with Spec Kitty 3.2: Keep your workspace up to date with upstream changes from dependent work packages.'
doc_status: deprecated
updated: '2026-08-31T00:00:00Z'
audience: docs/context/audience/external/tech-lead-evaluator.md
related:
- docs/guides/how-to/missions/handle-dependencies.md
kind: How-To
---
# How to Sync Workspaces

> **Removed in 3.2.6; kept as historical record.** The workspace-sync workflow
> described here is retired. This page is scheduled for deletion in 3.2.7.

Keep your workspace up to date with upstream changes from dependent work packages.

---

## The Problem

You're working on WP02, and WP01 (which WP02 depends on) has changed. You need to update your workspace with the latest changes from upstream.

---

## Prerequisites

- Active workspace created via `spec-kitty agent action implement WP## --agent <name>`
- spec-kitty 3.2 or newer
- Changes committed in the upstream workspace

---

## Steps

### 1. Navigate to Your Workspace

```bash
cd <workspace path printed by spec-kitty agent action implement>
```

### 2. Run Sync

```bash
spec-kitty sync workspace
```

You'll see output like:

```
Sync Workspace
├── ● Update workspace state
└── ● Rebase local changes on upstream

✓ Synced successfully
  Rebased 3 commits onto new upstream
  No conflicts detected
```

### 3. Verify the Sync

Check that upstream changes are now present:

```bash
git log --oneline -10
```

---

## Conflict Handling

Sync may **fail** if conflicts are detected. You must resolve conflicts before proceeding.

---

## Using --verbose for Details

Add `--verbose` to see detailed sync information:

```bash
spec-kitty sync workspace --verbose
```

Output includes:
- Rebase operations performed
- Any conflicts detected

---

## Recovering with --repair

If your workspace is in a broken state (corrupted worktree, detached HEAD), use `--repair`:

```bash
spec-kitty sync workspace --repair
```

> **Warning**: `--repair` may lose uncommitted changes. Commit your work first when possible.

This attempts to:
1. Reset the workspace to a known good state
2. Rebase your commits on top of the upstream base

---

## Troubleshooting

### "Working copy is not clean"

Commit or stash your changes before syncing:

```bash
git add . && git commit -m "WIP: save before sync"
```

### "Cannot rebase: conflicts detected" (git only)

With git, you must resolve conflicts before sync completes:

```bash
# See conflicting files
git status

# Resolve conflicts in your editor
# Then mark as resolved
git add <resolved-files>
git rebase --continue
```

### "Failed to update base: branch not found"

The base branch may have been deleted or renamed. Check available branches:

```bash
git branch -a
```

If the base branch is missing, you may need to recreate it or use `--repair`.

### "Workspace not found"

Ensure you're in a valid workspace directory:

```bash
pwd
# Should be: /path/to/project/.worktrees/<feature>-lane-a/
```

---

## When to Sync

Sync your workspace:

- **Before starting new work**: Get the latest changes first
- **After a dependent WP is merged**: Incorporate those changes
- **Before code review**: Ensure you have the latest base
- **When CI fails**: Your workspace may be out of date

---

## See Also

- [Handle Dependencies](../missions/handle-dependencies.md) — Keeping dependent WPs in sync
- [CLI Commands Reference](../../../api/cli-commands.md#spec-kitty-sync) — Full command reference
