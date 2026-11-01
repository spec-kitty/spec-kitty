---
title: Worktree Cleanup at Merge, Not Eager
description: Rejected eager deletion of a finished dependency's worktree so parallel and diamond-shaped work stayed runnable; cleanup waited for lane consolidation.
status: Superseded
doc_status: superseded
kind: ADR
date: '2026-01-26'
---

> Superseded by `../2.x/adr/2026-04-03-1-execution-lanes-own-worktrees-and-mission-branches.md`.
> This ADR assumed one worktree per work package. The current execution model
> uses one worktree per execution lane and one mission integration branch.

## Context and Problem Statement

In the workspace-per-work-package model (0.11.0+), each WP gets an isolated worktree. When WP02 depends on WP01 and is created with `spec-kitty implement WP02 --base WP01`, a natural question arises: **Why don't we immediately delete WP01's worktree since its branch is now a parent of WP02's branch?**

The appeal of "eager cleanup":
- **Disk space**: Worktrees accumulate quickly with many WPs
- **Mental model**: "WP01 is done, it's merged into WP02, delete it"
- **Simplicity**: Cleanup happens at creation time, not later

However, investigation reveals critical edge cases that make eager cleanup **unsafe for parallel workflows**.

## Decision Drivers

- Git branches persist independently of worktrees (worktrees are just working directories)
- Parallel development patterns (multiple WPs depend on same base)
- Diamond dependency patterns (WP needs same base as sibling)
- Review rework scenarios (WP back to "planned" after dependent created)
- Current validation expects worktrees to exist
- Legacy file filtering kept worktrees small enough that disk pressure was not the primary risk

## Considered Options

- **Option 1:** Keep current behavior (cleanup at merge) - CHOSEN
- **Option 2:** Eager cleanup with safety checks (when dependent created)
- **Option 3:** Manual cleanup command (user-triggered)

## Decision Outcome

**Chosen option:** "Option 1: Keep current behavior (cleanup at merge)", because:
- Parallel workflows are safe (multiple WPs can use same base simultaneously)
- Diamond dependencies work correctly (all deps available at creation time)
- Review rework doesn't break workflows (worktree available if WP reopened)
- Current validation logic is correct (checks worktree existence)
- Worktrees were small enough that disk usage was not the primary concern
- Merge cleanup is automatic, safe, and default behavior

### Consequences

#### Positive

- **Parallel development is safe**: WP02 and WP03 can both use WP01 as base simultaneously
- **Diamond patterns work**: All dependencies available when WP04 needs WP02+WP03
- **Review rework resilient**: If WP01 reopened after WP02 created, worktree still exists
- **Validation logic correct**: `implement.py:640` checks worktrees exist (not just branches)
- **No race conditions**: Multiple agents can create dependencies concurrently
- **Automatic cleanup**: `spec-kitty merge` handles cleanup by default
- **Deterministic behavior**: Same deps → same results regardless of timing

#### Negative

- **Disk usage**: Worktrees accumulate until merge (historically mitigated by filtered worktrees)
- **Mental model mismatch**: Users may think worktree unnecessary after dependent created
- **No explicit feedback**: Users don't see "worktree cleaned" during implement

#### Neutral

- Worktrees were small in the legacy model because not every file surface was present in every workspace
- Merge cleanup happens automatically unless `--no-cleanup` specified
- Branches persist independently (worktree deletion doesn't affect git history)

### Confirmation

We'll validate this decision by:
- No reports of parallel implementation failures due to missing worktrees
- Diamond dependency patterns complete successfully
- Review rework scenarios don't require worktree recreation
- Disk usage remains manageable under the legacy model
- Users find merge cleanup behavior intuitive

## Pros and Cons of the Options

### Option 1: Keep Current (Cleanup at Merge)

**Pros:**
- Parallel workflows safe (WP02, WP03 both use WP01 simultaneously)
- Diamond deps work (all bases available at WP04 creation)
- Review rework resilient (WP01 worktree exists if reopened)
- Current validation correct (checks worktree not just branch)
- No race conditions (concurrent dependency creation safe)
- Automatic cleanup (merge handles by default)
- Simple implementation (no additional logic needed)

**Cons:**
- Worktrees accumulate until merge (disk usage)
- Mental model mismatch (seems wasteful to keep WP01)
- No explicit feedback during implement

### Option 2: Eager Cleanup with Safety Checks

Delete worktree when dependent created, with extensive validation.

**Pros:**
- Immediate disk reclamation
- Matches mental model ("WP01 done → delete")
- Cleanup happens at natural boundary (dependent creation)

**Cons:**
- **BREAKS PARALLEL WORKFLOWS**: If WP02 deletes WP01, WP03 creation fails
- **BREAKS DIAMOND DEPS**: WP04 can't validate WP01 exists (deleted by WP02)
- **BREAKS REVIEW REWORK**: WP01 back to "planned" but worktree gone
- Requires extensive safety checks:
  - Lock mechanism for concurrent access
  - Dependency graph traversal (check for other dependents)
  - Inverse dependency tracking (who else needs this base?)
  - Worktree recreation logic (if WP reopened)
- Changes validation semantics (`implement.py:640` must check branches not worktrees)
- Race conditions (WP02, WP03 both check "no other deps" then delete)
- 20+ new tests for edge cases
- Complex implementation vs minimal benefit

**Critical edge cases:**

1. **Parallel Development Race**:
```
Timeline:
1. WP02 created with --base WP01 (deletes WP01 worktree)
2. WP03 tries to create with --base WP01
3. Validation fails: worktree doesn't exist
```

2. **Diamond Dependency**:
```
WP01 → WP02 ─┐
    → WP03 ─┴→ WP04

Timeline:
1. WP01 done
2. WP02 created (deletes WP01 worktree)
3. WP03 tries to create → FAIL (WP01 worktree missing)
```

3. **Review Rework**:
```
Timeline:
1. WP01 done → WP02 created (deletes WP01 worktree)
2. Reviewer finds bug in WP01 → back to "planned"
3. Agent needs to implement WP01 → worktree missing
4. Must recreate worktree (complexity)
```

### Option 3: Manual Cleanup Command

Provide `spec-kitty cleanup-worktrees` for user-triggered cleanup.

**Pros:**
- User control over disk usage
- Can cleanup specific worktrees or all
- No automatic behavior (explicit intent)
- Safe (user decides when ready)

**Cons:**
- Extra command to learn and remember
- No automatic cleanup (relies on user discipline)
- Still accumulates worktrees (most users won't use)
- Doesn't solve disk usage problem (users forget)
- Additional implementation complexity

## More Information

### Implementation Summary

**Current Behavior:**
1. Worktrees created on-demand via `spec-kitty implement WP##`
2. Worktrees persist throughout feature development
3. Merge command cleans up all worktrees by default
4. Cleanup can be skipped with `--no-cleanup` flag

**Validation Logic:**
- `implement.py:640-646`: Validates worktree exists (not just branch)
- `multi_parent_merge.py:94-111`: Validates all dependency worktrees exist
- `dependency_graph.py`: Tracks dependency relationships

**Cleanup Logic:**
- `merge.py:334-377`: Removes worktrees after successful merge
- Default behavior: cleanup enabled
- Optional: `--no-cleanup` preserves worktrees

**Worktree Size:**
- Sparse checkout excludes `kitty-specs/` (large directory)
- Typical worktree: ~1-10 MB (code only)
- Even with 10 WPs: ~100 MB total (negligible)

### Code References

- `src/specify_cli/cli/commands/implement.py:640-646` - Worktree validation (checks existence)
- `src/specify_cli/cli/commands/merge.py:334-377` - Cleanup logic (removes worktrees)
- `src/specify_cli/core/multi_parent_merge.py:94-111` - Multi-parent validation (needs all deps)
- `src/specify_cli/core/dependency_graph.py` - Dependency tracking (build graph)
- `tests/integration/test_parallel_implementation.py` - Parallel workflow tests

### Related Decisions

- [2026-01-23-2-explicit-base-branch-tracking](2026-01-23-2-explicit-base-branch-tracking.md) - Stores base_branch in frontmatter
- [2026-01-23-4-auto-merge-multi-parent-dependencies](2026-01-23-4-auto-merge-multi-parent-dependencies.md) - Multi-parent merge needs all dependency branches
- [2026-01-23-6-config-driven-agent-management](2026-01-23-6-config-driven-agent-management.md) - Parallel agent execution patterns

### Why Current Behavior is Correct

**Git Architecture:**
- Worktrees are working directories (filesystem concept)
- Branches are git refs (independent of worktrees)
- Deleting worktree doesn't delete branch
- Branches persist and remain mergeable

**Validation Semantics:**
- Current code validates worktree existence (correct for parallel workflows)
- Changing to branch-only validation would miss parallel conflicts
- Example: WP02 and WP03 both use WP01 base (worktree needed until both done)

**Parallel Workflow Example:**
```bash
# Agent A
spec-kitty implement WP02 --base WP01 &  # Starts, checks WP01 worktree ✓

# Agent B (concurrent)
spec-kitty implement WP03 --base WP01 &  # Starts, checks WP01 worktree ✓

# Both succeed because WP01 worktree exists
# If WP02 deleted WP01 worktree → WP03 would fail
```

**Diamond Workflow Example:**
```
        WP01
       /    \
    WP02    WP03
       \    /
        WP04

Timeline:
1. WP01 done
2. WP02, WP03 created in parallel (both use WP01 base)
3. WP04 created (needs both WP02 and WP03)
4. Validation checks all worktrees exist ✓
5. Merge cleans up all worktrees together
```

### If Implementing Eager Cleanup (Not Recommended)

Would require:

1. **Change validation semantics**:
   - `implement.py:640`: Check branch exists (not worktree)
   - Risk: Misses parallel conflicts

2. **Add safety checks**:
   - Lock mechanism (prevent race conditions)
   - Inverse dependency tracking (`get_dependents()`)
   - Check if other WPs need this base
   - Only delete if no other WPs depend on it

3. **Handle race conditions**:
```python
# Pseudocode for safety check
def safe_to_delete_worktree(wp_id, feature_dir):
    with worktree_lock:
        dependents = get_all_dependents(wp_id)
        if any(d.status != "done" for d in dependents):
            return False  # Other WPs still need this
        return True
```

4. **Recreate worktrees on rework**:
   - If WP back to "planned", recreate worktree
   - Additional complexity, error-prone

5. **Testing**:
   - 20+ new tests for edge cases
   - Parallel race condition tests
   - Diamond dependency tests
   - Review rework tests

**Estimated effort:** ~5-8 hours implementation + testing vs **0 hours** for current behavior.

**Benefit:** Minimal (the legacy model already kept worktrees small).

### Disk Usage Analysis

**Sparse Checkout Configuration:**
```bash
# legacy filtered-worktree metadata file
/*
!/kitty-specs/
```

**Typical Worktree Size:**
- Source code: ~1-5 MB
- Dependencies (node_modules, .venv): Usually sparse-checked out
- Total: ~1-10 MB per worktree

**Worst Case:**
- 20 WPs in parallel: ~200 MB
- Modern dev machine: 512 GB - 2 TB storage
- Percentage: 0.01% - 0.04% (negligible)

**Conclusion:** Disk usage not a critical concern.
