---
title: Centralized Workspace Context Storage
description: Centralised runtime workspace context in a shared .kittify directory in the main checkout, so agents could read it from anywhere and it outlived the worktree.
status: Superseded
doc_status: superseded
kind: ADR
date: '2026-01-23'
---

> Superseded by `architecture/2.x/adr/2026-04-03-1-execution-lanes-own-worktrees-and-mission-branches.md`.
> This ADR was written for the legacy filtered-worktree era. The current
> runtime uses mandatory execution lanes, mission/lane branches, and
> lane-scoped runtime context instead of per-WP workspace metadata.

## Context and Problem Statement

LLM agents working in worktrees need runtime visibility into workspace state
(base branch, dependencies, creation time, etc.). In the legacy
filtered-worktree model, base-branch metadata in frontmatter was not visible
inside every workspace.

This creates a visibility problem:
- Agents in worktrees cannot read their own WP frontmatter
- Must query main repo to get workspace metadata
- No consolidated runtime context available in worktree
- Context information scattered across multiple sources

Where should we store runtime context information that is:
- Accessible from both main repo and worktrees
- Not hidden by workspace-local filtering
- Survives worktree deletion (for audit trail)
- Doesn't create merge conflicts

## Decision Drivers

- Agents in worktrees need runtime access to workspace metadata
- Context should be readable without querying main repo files
- Need audit trail that persists after worktree deletion
- Must not create merge conflicts or git state issues
- Should align with existing architecture patterns
- Want single query to get all workspace context

## Considered Options

- **Option 1:** Per-worktree `.spec-kitty-context` file
- **Option 2:** Centralized storage in `.kittify/workspaces/`
- **Option 3:** Environment variables only
- **Option 4:** Store in git config

## Decision Outcome

**Chosen option:** "Option 2: Centralized storage in `.kittify/workspaces/`", because:
- Aligns with existing `.kittify/` pattern (config, metadata, merge-state all in `.kittify/`)
- Survives worktree deletion (audit trail)
- Avoids workspace-local filtering complexity
- Queryable from anywhere (main repo and worktrees)
- Simple cleanup on merge
- No risk of merge conflicts (files in main repo, not worktrees)

### Consequences

#### Positive

- Context accessible from both main repo and worktrees via relative path
- Persists after worktree deletion (post-mortem debugging)
- No .gitignore or workspace-filtering complexity
- Consistent with existing architecture (all state in `.kittify/`)
- Simple cleanup (delete JSON file)
- Queryable via CLI (`spec-kitty context info`)

#### Negative

- Context files stored separately from worktrees
- Agents must use relative path (`../../.kittify/workspaces/`)
- Could become orphaned if worktree deleted without cleanup

#### Neutral

- JSON format for context files
- One file per workspace: `###-feature-WP##.json`
- Cleanup command: `spec-kitty context cleanup`

### Confirmation

We'll validate this decision by:
- Agents successfully reading context from worktrees
- No reports of context visibility issues
- Orphaned context detection working correctly
- Performance acceptable (< 50ms to read context)

## Pros and Cons of the Options

### Option 1: Per-Worktree `.spec-kitty-context` File

**Pros:**
- High visibility (in worktree root)
- No relative path needed
- Colocated with workspace files

**Cons:**
- Lost when worktree deleted (no audit trail)
- Requires gitignoring (untracked, ephemeral)
- Duplicates info from frontmatter
- Adds .gitignore complexity
- Could be accidentally committed
- Not accessible from main repo

### Option 2: Centralized Storage in `.kittify/workspaces/`

**Pros:**
- Survives worktree deletion (audit trail)
- No .gitignore complexity
- Consistent with `.kittify/` pattern
- Queryable from anywhere
- Simple cleanup
- No merge conflicts

**Cons:**
- Requires relative path from worktree
- Context stored separately from workspace
- Could become orphaned

### Option 3: Environment Variables Only

**Pros:**
- No files to manage
- Available to all processes
- Traditional Unix approach

**Cons:**
- Ephemeral (lost when shell exits)
- Not queryable after command finishes
- No audit trail
- Must be set manually
- Not accessible to new shells/processes

### Option 4: Store in Git Config

**Pros:**
- Git-native approach
- Persistent across shell sessions

**Cons:**
- Pollutes git config namespace
- Difficult to query programmatically
- Not human-readable
- Cleanup complex
- Non-standard use of git config

## More Information

### Implementation Summary

**Context file location:** `.kittify/workspaces/###-feature-WP##.json`

**Context includes:**
- WP ID, feature slug, worktree path, branch name
- Base branch and commit SHA
- Dependencies list
- Creation timestamp and VCS backend

**CLI commands:**
- `spec-kitty context info` - Show context for workspace
- `spec-kitty context list` - List all workspaces
- `spec-kitty context cleanup` - Remove orphaned contexts

**Test coverage:** 9 tests for persistence, orphaned detection, and visibility

### Related Decisions

- [2026-01-23-2-explicit-base-branch-tracking](2026-01-23-2-explicit-base-branch-tracking.md) - Provides base branch data for context
- [2026-01-23-5-decorator-based-context-validation](2026-01-23-5-decorator-based-context-validation.md) - Uses context for validation

### Code References

- `src/specify_cli/workspace_context.py` - Context management (save, load, list, cleanup)
- `src/specify_cli/cli/commands/context.py` - CLI commands
- `tests/unit/test_base_branch_tracking.py` - Test suite
