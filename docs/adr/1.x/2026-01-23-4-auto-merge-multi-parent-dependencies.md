---
title: Auto-Merge Multi-Parent Dependencies
description: Resolves the diamond-dependency ambiguity by combining every declared parent into one temporary commit, so a work package always starts from a deterministic tree.
status: Accepted
date: '2026-01-23'
doc_status: active
kind: ADR
updated: '2026-01-23T00:00:00Z'
---

## Context and Problem Statement

Work packages can depend on multiple other work packages (diamond dependency pattern). For example:

```
        WP01 (database)
       /    \
    WP02    WP03
  (users)  (auth)
       \    /
        WP04
     (admin UI)
```

WP04 depends on **both** WP02 and WP03. However, git worktrees can only branch from a **single** base commit. This created ambiguity:

**Previous approach:**
```bash
$ spec-kitty implement WP04
Error: WP04 has dependencies: ['WP02', 'WP03']
Specify --base: spec-kitty implement WP04 --base WP03
Then manually merge: git merge 010-feature-WP02
```

**Problems:**
- Arbitrary choice (why WP03 over WP02?)
- Manual merge steps required (error-prone)
- No validation that all dependencies were merged
- Non-deterministic (two runs could create different git histories)
- Burdens agents with manual merge operations

How do we handle multi-parent dependencies deterministically and automatically?

## Decision Drivers

- Git limitation: can only branch from one base commit
- Need deterministic behavior (same inputs → same outputs)
- Want to eliminate manual merge steps for agents
- Must validate all dependencies are included
- Should create reproducible git history
- Need clear conflict detection and reporting

## Considered Options

- **Option 1:** Require manual --base selection and manual merge (status quo)
- **Option 2:** Auto-merge all dependencies into temporary merge commit
- **Option 3:** Topological-first parent selection (pick earliest dependency)
- **Option 4:** Dependency weight-based selection (pick largest dependency)

## Decision Outcome

**Chosen option:** "Option 2: Auto-merge all dependencies into temporary merge commit", because:
- Fully deterministic (same deps → same git tree)
- No manual merge steps required
- Validates all dependencies merged automatically
- Clear error on merge conflicts
- Reproducible builds

### Consequences

#### Positive

- Fully deterministic multi-parent handling
- No manual merge steps for agents
- All dependencies validated before workspace creation
- Clear conflict detection and reporting
- Reproducible git history
- Eliminates arbitrary base selection

#### Negative

- Creates additional merge commits (increases git graph complexity)
- Merge conflicts must be resolved before workspace creation
- Temporary branches persist after workspace creation
- Sequential merges (not octopus merge, slightly more commits)

#### Neutral

- Temporary merge base branch: `###-feature-WP##-merge-base`
- Dependencies sorted for deterministic merge order
- Merge strategy: sequential binary merges (not octopus)

### Confirmation

We'll validate this decision by:
- Multi-parent WPs create successfully without manual intervention
- Same dependencies produce same git tree hash
- Conflict detection catches incompatible dependencies early
- No reports of missing dependency code in merged workspaces
- Users find multi-parent workflow intuitive

## Pros and Cons of the Options

### Option 1: Manual --base Selection + Manual Merge

**Pros:**
- Simple implementation (no auto-merge logic)
- User has full control over merge order
- Minimal git operations

**Cons:**
- Arbitrary base selection (non-deterministic)
- Manual merge steps burden agents
- No validation of complete dependency merge
- Error-prone (agents may forget to merge all deps)
- Inconsistent git histories across runs

### Option 2: Auto-Merge All Dependencies

**Pros:**
- Fully deterministic (sorted deps → same tree)
- No manual steps required
- All dependencies validated automatically
- Clear conflict detection
- Reproducible builds
- Agents don't need merge knowledge

**Cons:**
- Additional merge commits created
- Conflicts block workspace creation
- Temporary branches persist
- More complex implementation

### Option 3: Topological-First Parent Selection

**Pros:**
- Deterministic ordering (earliest dependency)
- Single base branch (simpler than merge)
- Fewer merge commits

**Cons:**
- Still requires manual merge of remaining deps
- Not all dependencies included automatically
- Partial solution (doesn't eliminate manual steps)

### Option 4: Dependency Weight-Based Selection

**Pros:**
- Intelligent base selection (largest impact)
- Potentially fewer merge conflicts

**Cons:**
- Still requires manual merge
- Non-deterministic if weights equal
- Complex heuristic (file count? lines changed?)
- Doesn't solve fundamental problem

## More Information

### Implementation Summary

**Algorithm:**
1. Sort dependencies for deterministic ordering
2. Create temp branch from first dependency
3. Merge remaining dependencies sequentially
4. Return merge commit SHA as base branch

**Temporary branch naming:** `###-feature-WP##-merge-base`

**Conflict handling:**
- Detects conflicts automatically
- Lists conflicting files in error message
- Aborts merge cleanly
- Cleans up temporary branch

**Test coverage:** 8 unit tests (merge logic, conflicts, diamond pattern) + 3 integration tests (end-to-end workflows)

### Related Decisions

- Requires [2026-01-23-2-explicit-base-branch-tracking](2026-01-23-2-explicit-base-branch-tracking.md) for recording merge base
- Requires [2026-01-23-3-centralized-workspace-context-storage](2026-01-23-3-centralized-workspace-context-storage.md) for tracking merge metadata
- Works with [2026-01-23-5-decorator-based-context-validation](2026-01-23-5-decorator-based-context-validation.md) for location validation

### Code References

- `src/specify_cli/core/multi_parent_merge.py` - Auto-merge implementation (create_multi_parent_base function)
- `src/specify_cli/cli/commands/implement.py:622-789` - Multi-parent detection and integration
- `tests/unit/test_multi_parent_merge.py` - Test suite
- `tests/integration/test_implement_multi_parent.py` - End-to-end tests
