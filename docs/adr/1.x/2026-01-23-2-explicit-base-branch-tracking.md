---
title: Explicit Base Branch Tracking in Work Package Frontmatter
description: Stores each work package's base branch in its frontmatter instead of recomputing it from git, making workspace provenance visible, auditable, and recreatable.
status: Accepted
doc_status: active
kind: ADR
date: '2026-01-23'
---

## Context and Problem Statement

When implementing work packages in isolated worktrees, agents and users need to know which branch a workspace was created from (the "base branch"). This information is critical for:
- Understanding dependency relationships
- Debugging merge conflicts
- Validating workspace state
- Recreating workspaces if deleted

Previously, base branch information was **computed at runtime** from:
- Git worktree tracking branch metadata
- Dependency relationships in frontmatter
- Git queries (`git rev-parse --abbrev-ref @{u}`)

This runtime-derived approach created visibility problems:
- Agents couldn't answer "What is my base branch?" without git queries
- No single source of truth for base branch information
- Debugging dependency chains required manual graph traversal
- Base branch invisible in work package metadata

## Decision Drivers

- LLM agents need explicit base branch information without git queries
- Users debugging issues need clear base branch visibility
- Workspace recreation requires knowing original base branch
- Dependency tracking needs audit trail
- Git queries are slow and error-prone for agents
- Need single source of truth for base branch information

## Considered Options

- **Option 1:** Continue runtime derivation (status quo)
- **Option 2:** Store base branch in WP frontmatter
- **Option 3:** Store base branch in git commit message
- **Option 4:** Store base branch in separate metadata file

## Decision Outcome

**Chosen option:** "Option 2: Store base branch in WP frontmatter", because:
- WP frontmatter is already the source of truth for WP metadata
- Visible to agents reading planning artifacts
- Tracked in git history (auditability)
- No new files or infrastructure needed
- Consistent with existing dependency tracking pattern

### Consequences

#### Positive

- Agents can read base branch from frontmatter (no git queries needed)
- Single source of truth for base branch information
- Git history shows when base branch was set/changed
- Enables validation (check if base commit still exists)
- Consistent with existing frontmatter-based metadata pattern
- Simplifies debugging dependency chains

#### Negative

- Frontmatter could diverge from actual git state (if manual branch switching)
- Additional fields in frontmatter (slightly more complex schema)
- Requires updating during workspace creation (minor overhead)

#### Neutral

- Three new frontmatter fields: `base_branch`, `base_commit`, `created_at`
- Fields written automatically during `spec-kitty implement`
- Backward compatible (optional fields)

### Confirmation

We'll validate this decision by:
- Agents successfully querying base branch from frontmatter
- No reports of base branch confusion or debugging issues
- Successful workspace recreation using base branch information
- Positive feedback from users about base branch visibility

## Pros and Cons of the Options

### Option 1: Continue Runtime Derivation

**Pros:**
- No schema changes required
- Minimal implementation effort
- Flexible (no persistent state to manage)

**Cons:**
- Base branch invisible to agents without git queries
- No audit trail for base branch changes
- Debugging requires inferring from git metadata
- Complex logic to derive base branch correctly
- Error-prone (depends on git state being correct)

### Option 2: Store Base Branch in WP Frontmatter

**Pros:**
- Single source of truth
- Visible to agents reading planning artifacts
- Tracked in git history (auditability)
- No new files or infrastructure
- Consistent with existing metadata patterns
- Enables validation and debugging

**Cons:**
- Could diverge from git state
- Additional frontmatter fields
- Minor overhead during workspace creation

### Option 3: Store Base Branch in Git Commit Message

**Pros:**
- Already in git history
- No schema changes needed

**Cons:**
- Difficult to query programmatically
- Not visible in WP files
- Agents would need to parse git log
- Coupling metadata to git commit messages

### Option 4: Store Base Branch in Separate Metadata File

**Pros:**
- Doesn't pollute frontmatter
- Could store additional metadata

**Cons:**
- New file to manage (.kittify/workspace-metadata/ directory)
- Not visible in WP files
- Another file to track and sync
- More complex than using existing frontmatter

## More Information

### Implementation Summary

**Frontmatter fields added:**
- `base_branch` - Branch this WP was created from (e.g., "010-feature-WP01" or "main")
- `base_commit` - Git SHA snapshot at creation (for validation)
- `created_at` - ISO timestamp when workspace was created

**Test coverage:** 17 tests validating frontmatter updates, backward compatibility, orphaned detection

### Related Decisions

- [2026-01-23-3-centralized-workspace-context-storage](2026-01-23-3-centralized-workspace-context-storage.md) - Complements this with runtime context files
- Enables [2026-01-23-4-auto-merge-multi-parent-dependencies](2026-01-23-4-auto-merge-multi-parent-dependencies.md) by providing base branch info

### Code References

- `src/specify_cli/frontmatter.py:38-52` - Frontmatter schema
- `src/specify_cli/cli/commands/implement.py:833-845` - Writes base tracking on workspace creation
- `src/specify_cli/workspace_context.py` - WorkspaceContext dataclass and persistence
- `tests/unit/test_base_branch_tracking.py` - Test suite
