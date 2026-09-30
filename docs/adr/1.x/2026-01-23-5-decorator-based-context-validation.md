---
title: Decorator-Based Context Validation
description: Guards location-sensitive commands with a declarative decorator, blocking the nested-worktree invocations that used to corrupt workspace state silently.
status: Accepted
date: '2026-01-23'
---

## Context and Problem Statement

Certain spec-kitty commands must run in specific locations to work correctly:
- `implement` must run from **main repository** (creates worktrees)
- `merge` must run from **main repository** (merges multiple worktree branches)
- Hypothetical workspace commands must run from **inside worktrees**

Running commands in the wrong location causes critical failures:

**Nested Worktree Problem** (Critical):
```bash
$ cd .worktrees/010-feature-WP02/  # Inside worktree
$ spec-kitty implement WP03         # Tries to create worktree from worktree
# Result: Nested worktrees, corrupted git state, repo unusable
```

**Previous solution:** Manual guard code in each command (20+ lines):
```python
def implement(wp_id: str):
    cwd = Path.cwd().resolve()
    if ".worktrees" in cwd.parts:
        console.print("Error: Cannot create worktrees from inside a worktree!")
        # ... 15 more lines of error handling ...
        raise typer.Exit(1)
    # ... actual implementation
```

**Problems with manual guards:**
- Verbose boilerplate in every command
- Easy to forget when adding new commands
- Inconsistent error messages
- Could be accidentally removed during refactoring
- No systematic framework for location validation

How do we enforce location requirements consistently and reliably?

## Decision Drivers

- **Critical: Must prevent nested worktrees** (causes git corruption)
- Need consistent location validation across all commands
- Want declarative approach (clear from function signature)
- Should reduce boilerplate code
- Must provide clear, actionable error messages
- Can't rely on agent discipline (need enforcement)
- Want reusable framework for all location-aware commands

## Considered Options

- **Option 1:** Manual guards in each command (status quo)
- **Option 2:** Decorator-based validation (`@require_main_repo`)
- **Option 3:** Pre-command hooks (global validation)
- **Option 4:** Wrapper scripts that validate before execution

## Decision Outcome

**Chosen option:** "Option 2: Decorator-based validation", because:
- Declarative (clear from function definition)
- Reusable (single decorator for all commands)
- Can't be accidentally removed (part of function signature)
- Provides consistent error messages
- Minimal boilerplate (1 line vs 20+ lines)
- Pythonic approach (familiar to developers)
- Easy to test in isolation

### Consequences

#### Positive

- Prevents nested worktrees automatically (critical bug prevention)
- Consistent error messages across all commands
- Declarative validation (self-documenting code)
- Reduces code duplication (20+ lines → 1 line per command)
- Easy to add validation to new commands
- Clear from function signature what location is required
- Testable in isolation (23 dedicated tests)

#### Negative

- Adds decorator import to command files
- Runtime overhead (context detection on each call, ~1ms)
- Could be bypassed by calling function directly (not via CLI)

#### Neutral

- Three decorators: `@require_main_repo`, `@require_worktree`, `@require_either`
- Error messages include current location, required location, and fix command
- Context detection based on filesystem path analysis

### Confirmation

We'll validate this decision by:
- Zero instances of nested worktree creation
- No reports of commands running in wrong location
- Error messages successfully guiding users to correct location
- New commands correctly decorated
- Performance impact negligible (< 1ms)

## Pros and Cons of the Options

### Option 1: Manual Guards in Each Command

**Pros:**
- Full control over error messages per command
- No framework overhead
- Simple to understand (explicit code)

**Cons:**
- Verbose boilerplate (20+ lines per command)
- Easy to forget for new commands
- Inconsistent error messages
- Can be accidentally removed
- No reusable framework
- Duplicated code across commands

### Option 2: Decorator-Based Validation

**Pros:**
- Declarative (clear from signature)
- Reusable (DRY principle)
- Can't be accidentally removed
- Consistent error messages
- Minimal boilerplate (1 line)
- Testable in isolation
- Pythonic approach

**Cons:**
- Adds import overhead
- Runtime detection cost (~1ms)
- Could be bypassed if function called directly

### Option 3: Pre-Command Hooks (Global Validation)

**Pros:**
- Centralized validation logic
- No per-command changes needed
- Could validate multiple aspects

**Cons:**
- Magic behavior (not clear from function)
- Hard to customize per command
- Difficult to test
- Framework complexity
- Unclear which commands are protected

### Option 4: Wrapper Scripts

**Pros:**
- Language-agnostic
- Could add shell-level checks

**Cons:**
- Extra layer of indirection
- Harder to maintain
- Not integrated with Python code
- Difficult to test
- Breaks direct Python imports

## More Information

### Implementation Summary

**Decorators provided:**
- `@require_main_repo` - Command must run from main repository
- `@require_worktree` - Command must run from inside a worktree
- `@require_either` - Command can run in either location (documentation only)

> **Note (2026-09-30):** `@require_worktree`, `@require_either` and the
> `SPEC_KITTY_CONTEXT` env-var helpers (`set_context_env_vars` /
> `get_context_env_vars`) never gained a production caller and were removed in
> the 2026-09-30 dead-code sweep. Only `@require_main_repo` remains.

**Context detection:**
- Checks if ".worktrees" is in current path
- Extracts worktree name and repo root automatically
- Works from any subdirectory

**Environment variables:**
- `SPEC_KITTY_CONTEXT` - "main" or "worktree"
- `SPEC_KITTY_WORKTREE_NAME` - Worktree name (if in worktree)
- `SPEC_KITTY_REPO_ROOT` - Repository root path

**Test coverage:** 23 tests including critical nested worktree prevention tests

### Related Decisions

- Works with [2026-01-23-2-explicit-base-branch-tracking](2026-01-23-2-explicit-base-branch-tracking.md) for complete context
- Works with [2026-01-23-3-centralized-workspace-context-storage](2026-01-23-3-centralized-workspace-context-storage.md) for runtime queries
- Enables [2026-01-23-4-auto-merge-multi-parent-dependencies](2026-01-23-4-auto-merge-multi-parent-dependencies.md) by ensuring merge runs in main repo

### Code References

- `src/specify_cli/core/context_validation.py` - Decorator framework and context detection
- `src/specify_cli/cli/commands/implement.py:562` - `@require_main_repo` applied to implement
- `src/specify_cli/cli/commands/merge.py:383` - `@require_main_repo` applied to merge
- `tests/unit/test_context_validation.py` - Test suite with critical nesting prevention tests

### Critical Bug Prevention

This decision **prevents nested worktrees**, which corrupts git state:
- Nested worktrees make repo unusable
- Requires manual recovery
- Could lose work if not detected

The decorator framework makes prevention **automatic and unforgeable** (can't be accidentally removed during refactoring).
