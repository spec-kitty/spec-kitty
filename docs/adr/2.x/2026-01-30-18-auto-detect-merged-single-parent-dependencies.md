---
title: Auto-Detect Merged Single-Parent Dependencies
description: Recognised that an integrated dependency already sits in the target branch and branched from there, rather than failing because its worktree had been cleaned up.
status: Superseded
date: '2026-01-30'
doc_status: superseded
kind: ADR
updated: '2026-01-30T00:00:00Z'
---

> Superseded on 2026-04-05 by
> `2026-04-03-1-execution-lanes-own-worktrees-and-mission-branches.md`.
> The lane-only runtime removed per-WP base-branch selection entirely.
> Dependent WPs that must share code context are co-located in a single lane,
> so `implement` no longer switches between target-branch and per-WP branch
> bases.

---

## Context and Problem Statement

During implementation of feature 025-cli-event-log-integration, we encountered a workflow blocker:

**What happened:**
```
1. WP01 completed and merged to 2.x branch ✅
2. WP01 workspace/branch cleaned up post-merge ✅ (correct behavior)
3. WP02 declares dependency on WP01 in frontmatter
4. Agent ran: spec-kitty implement WP02
5. FAILED: "Base workspace WP01 does not exist"
6. Required manual frontmatter edit to remove dependency
```

**The gap:**
The `implement` command doesn't distinguish between:
- **In-progress dependency** (WP01 lane = doing/for_review) → Branch exists, branch from it
- **Merged dependency** (WP01 lane = done) → Branch cleaned up, work already in target

**Current behavior:**
```python
# In implement.py (simplified)
if wp.dependencies == ["WP01"]:
    base_branch = "025-feature-WP01"  # ← Doesn't exist if WP01 merged!
```

**Expected behavior:**
```python
if wp.dependencies == ["WP01"] and WP01.lane == "done":
    base_branch = target_branch  # ← Use 2.x (WP01's work already there)
else:
    base_branch = "025-feature-WP01"  # ← Use workspace branch
```

**Why this matters:**
- This is the NORMAL workflow (dependency completes before dependent starts)
- Forces error-prone manual frontmatter editing
- Blocks parallel development (WP02 can't start until WP01 merges)
- Confuses agents (error message suggests implementing non-existent WP)

## Decision Drivers

- **Normal workflow support** - Dependencies completing before dependents is expected
- **Post-merge cleanup** - Workspace branches are correctly deleted after merge (ADR-9)
- **User experience** - Manual frontmatter editing is error-prone
- **Agent guidance** - Error message "Implement WP01 first" is misleading when WP01 is done
- **Merge semantics** - Merged work is in target branch, so branching from target is correct
- **Backward compatibility** - Existing in-progress dependencies must still work
- **ADR-15 complement** - ADR-15 handles multi-parent all-done, this handles single-parent done

## Considered Options

- **Option 1:** Auto-detect merged dependency, branch from target (smart detection)
- **Option 2:** Require --force flag to override (explicit opt-in)
- **Option 3:** Manual frontmatter editing (status quo)
- **Option 4:** Prevent merge until all dependents implemented (restrictive)

## Decision Outcome

**Chosen option:** "Option 1: Auto-detect merged dependency, branch from target", because:
- **Matches user intent** - If WP01 is done, its work is in target branch
- **Zero manual intervention** - No frontmatter editing needed
- **Correct semantics** - Branching from target branch gives you merged WP01 work
- **Backwards compatible** - In-progress dependencies unchanged
- **Consistent with ADR-15** - Similar detection logic for multi-parent
- **Agent-friendly** - Workflow "just works" without special handling

### Consequences

#### Positive

- **Normal workflow works** - WP01 merge → WP02 implement (no manual edits)
- **Post-merge cleanup safe** - Deleting WP01 branch doesn't block WP02
- **Clear semantics** - "Merged" means "in target branch"
- **No user confusion** - Error messages accurate (no misleading "implement WP01")
- **Parallel development** - WP02/WP03 can start after WP01 merges (don't wait for WP04)
- **ADR-15 complement** - Single-parent covered, multi-parent already solved

#### Negative

- **Implicit behavior** - Branching point changes based on dependency lane status
- **Code complexity** - Must query dependency lane before resolving base branch
- **Frontmatter metadata** - `base_branch` field in frontmatter may become stale
- **Testing overhead** - Must test both in-progress and merged dependency paths

#### Neutral

- **Detection trigger** - Single dependency + lane == "done" → use target branch
- **Multi-parent unchanged** - ADR-15 logic still applies (merge-first suggestion)
- **No --force needed** - Unlike ADR-15, this is automatic (unambiguous case)
- **Frontmatter optional** - `base_branch` field becomes informational, not authoritative

### Confirmation

We will validate this decision by:
- ✅ Integration test: WP01 merge → WP02 implement (auto-detects merged dependency)
- ✅ Unit test: `resolve_base_branch()` checks lane status before workspace lookup
- ✅ Edge case: WP01 in-progress → WP02 still uses workspace branch
- ✅ Real-world: Feature 025 WP02/WP08 can implement after WP01 merge
- ✅ Error messages: No "implement WP01 first" when WP01 is done

**Success metrics:**
- Zero manual frontmatter edits for merged single-parent dependencies
- Agents report smooth workflow (WP01 merge → WP02 implement succeeds)
- No regression in in-progress dependency handling

## Pros and Cons of the Options

### Option 1: Auto-detect merged dependency, branch from target (CHOSEN)

Check if base WP is merged (lane == "done"), use target branch instead of workspace branch.

**Pros:**
- Zero manual intervention (workflow "just works")
- Correct semantics (merged work is in target)
- Backwards compatible (in-progress unchanged)
- Agent-friendly (no special cases)
- Matches user expectations (WP01 done → WP02 can start)
- Consistent with ADR-15 (multi-parent all-done detection)

**Cons:**
- Implicit behavior (branching point changes silently)
- Code complexity (lane status query before branch resolution)
- Frontmatter staleness (`base_branch` field may be outdated)
- Testing burden (both paths must be validated)

### Option 2: Require --force flag to override

Make user explicitly opt-in to branching from target when dependency is merged.

**Pros:**
- Explicit (user chooses behavior)
- No surprises (branching point always clear)
- Simpler code (no auto-detection)

**Cons:**
- Extra flag every time (WP02, WP03, WP08 all need --force)
- Poor UX (why require flag for normal case?)
- Inconsistent with ADR-15 (multi-parent suggests merge, not --force)
- Agent confusion (when to use --force?)

### Option 3: Manual frontmatter editing (status quo)

User manually updates `dependencies: []` and `base_branch: 2.x` when WP01 merges.

**Pros:**
- No code changes needed
- Explicit (frontmatter shows intent)
- Full control (user decides)

**Cons:**
- Error-prone (manual YAML editing)
- Workflow interruption (must edit, commit, then implement)
- Confusing (why remove dependency if it's real?)
- Poor agent UX (agents don't know when to edit)
- Breaks semantic meaning (dependency exists but not declared)

### Option 4: Prevent merge until all dependents implemented

Block WP01 merge if WP02/WP08 are not started/completed.

**Pros:**
- No stale branches (all WPs exist until merged together)
- Simple logic (all workspaces exist always)

**Cons:**
- Blocks parallel development (WP02 can't start until WP01 merges)
- Forces sequential workflow (no benefit of workspace-per-WP)
- Poor scaling (diamond dependencies deadlock)
- Breaks ADR-9 (worktree cleanup at merge)

## More Information

**Implementation location:**
- `src/specify_cli/cli/commands/implement.py` (around line 784, dependency resolution)
- Helper function: `resolve_base_branch(repo_root, feature_slug, base_wp_id) -> str`

**Implementation pseudocode:**
```python
def resolve_base_branch(repo_root: Path, feature_slug: str, base_wp_id: str) -> str:
    """
    Resolve base branch for dependent WP.

    Returns:
    - target_branch (e.g., "2.x") if base WP is merged (lane == "done")
    - workspace_branch (e.g., "025-feature-WP01") if base WP in progress
    """
    from specify_cli.core.work_package_utils import locate_work_package
    from specify_cli.core.feature_detection import get_feature_target_branch

    # Locate base WP to check lane status
    base_wp = locate_work_package(repo_root, feature_slug, base_wp_id)

    if base_wp.lane == "done":
        # Base WP merged - use target branch (work already there)
        return get_feature_target_branch(repo_root, feature_slug)
    else:
        # Base WP in progress - use workspace branch
        workspace_branch = f"{feature_slug}-{base_wp_id}"

        # Validate workspace exists
        if not workspace_exists(repo_root, workspace_branch):
            raise WorkspaceNotFoundError(
                f"Base workspace {base_wp_id} does not exist. "
                f"Current status: {base_wp.lane}. "
                f"Run: spec-kitty implement {base_wp_id}"
            )

        return workspace_branch
```

**Integration point:**
```python
# In implement.py, replace current base resolution
if base:
    base_branch = resolve_base_branch(repo_root, feature_slug, base)
else:
    # No base - use target branch
    base_branch = get_feature_target_branch(repo_root, feature_slug)
```

**Edge cases:**
1. **Multi-parent with one merged** (e.g., WP04 depends on WP01 [done], WP02 [doing])
   - ADR-15 logic takes precedence (suggest merge-first or auto-merge)
   - This ADR only applies to single-parent dependencies

2. **Base WP in for_review** (not done yet)
   - Use workspace branch (work not merged yet)
   - Reviewer may request changes (not safe to branch from target)

3. **Frontmatter base_branch mismatch** (frontmatter says WP01, logic says 2.x)
   - Detection overrides frontmatter (lane status is source of truth)
   - Frontmatter becomes informational only

**Testing requirements:**
- Unit: `test_resolve_base_branch_merged_dependency()`
- Unit: `test_resolve_base_branch_in_progress_dependency()`
- Integration: `test_implement_after_dependency_merged()`
- Edge: `test_implement_multi_parent_mixed_status()` (ensure ADR-15 logic prevails)

**Related ADRs:**
- **ADR-9:** Worktree Cleanup at Merge (establishes that merged branches are deleted)
- **ADR-15:** Merge-First Suggestion for Multi-Parent (handles all-done multi-parent case)
- **ADR-13:** Target Branch Routing (establishes target branch as source of truth)

**Enhances:** Historical per-WP workflow only

**Superseded by:** `2026-04-03-1-execution-lanes-own-worktrees-and-mission-branches.md`

**Version:** 0.13.20 (bugfix)

**Real-world validation:**
- Feature 025-cli-event-log-integration (WP02, WP08 blocked on merged WP01)
- Manual workaround applied: Remove dependencies, update base_branch, commit
- Post-fix: Automatic detection would eliminate manual steps
