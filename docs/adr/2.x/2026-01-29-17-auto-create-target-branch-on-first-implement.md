---
title: Auto-Create Target Branch on First Implement
description: Broke the bootstrap paradox by creating a missing target branch on the first implement call, which removed the hand-written branch-creation task from WP01.
status: Superseded
date: '2026-01-29'
doc_status: superseded
kind: ADR
updated: '2026-01-29T00:00:00Z'
---

> Superseded on 2026-04-05 by
> `2026-04-03-1-execution-lanes-own-worktrees-and-mission-branches.md`.
> The lane-only runtime no longer falls back to `main` or auto-creates an
> arbitrary target branch during `implement`. Features are expected to target an
> existing planning branch, and runtime-created execution branches are the
> mission branch plus its lane branches.

---

## Context and Problem Statement

When a feature targets a non-existent branch (e.g., Feature 002 → 3.x), we have a bootstrap paradox:

**The Problem:**
1. Feature metadata says: `target_branch: "3.x"`
2. Branch 3.x doesn't exist yet
3. LLM planning agent creates WP01 with task: "T001: Create 3.x branch"
4. Implementing agent runs: `spec-kitty implement WP01`
5. spec-kitty creates worktree from main (fallback, because 3.x missing)
6. Agent is on WP01 branch, prompt says "Create 3.x"
7. **Confusion:** "How do I create 3.x from inside WP01 worktree?"

**Current fallback behavior:**
- WP01 branches from main (safe degradation)
- Status commits try 3.x, fallback to main with warning
- Branch 3.x never gets created (nobody owns this responsibility)
- Agent confused about workflow

**Question:** Should spec-kitty **automatically create the target branch** when implementing the first WP if the branch doesn't exist?

## Decision Drivers

- **Eliminate bootstrap paradox** - Remove "Create branch" from WP01's responsibilities
- **Just-in-time creation** - Create branch when first needed (implement), not earlier
- **Automatic** - No user prompts or manual steps required
- **Correct routing** - Enable status commits to route to target_branch from the start
- **Clear ownership** - spec-kitty creates infrastructure, WPs create features
- **Agent-friendly** - Remove confusing bootstrap tasks from WP prompts

## Considered Options

- **Option 1:** Auto-create target branch during first implement (just-in-time)
- **Option 2:** Auto-create during /spec-kitty.specify (early creation)
- **Option 3:** Document bootstrap workflow in WP01 prompt (manual instructions)
- **Option 4:** Remove branch creation from WP01, require manual creation
- **Option 5:** Status quo (fallback to main, WP01 creates branch manually)

## Decision Outcome

**Chosen option:** "Option 1: Auto-create during first implement", because:
- Just-in-time (creates branch when first needed)
- Automatic (no user prompts, no manual steps)
- Eliminates bootstrap task from WP01 (cleaner prompts)
- Enables correct routing from the start
- Clear ownership (spec-kitty creates infrastructure)

### Consequences

#### Positive

- **Bootstrap paradox eliminated** - WP01 doesn't need "Create 3.x" task
- **Automatic** - No user prompts or manual steps
- **Just-in-time** - Branch created when first implement runs
- **Correct routing** - Status commits go to target_branch from WP01 onward
- **Agent-friendly** - Clear workflow, no confusing bootstrap instructions
- **Separation of concerns** - spec-kitty creates infrastructure, WPs create features

#### Negative

- **Implicit branch creation** - Users might not notice branch was created
- **Naming conflicts** - What if branch name already exists? (check and error)
- **No user choice** - Branch created automatically (cannot opt-out)
- **Magic behavior** - Branch appears without explicit user action

#### Neutral

- **Creation location** - `git branch <target> main` in main repo before worktree creation
- **Timing** - Only on FIRST implement for feature (subsequent WPs find existing branch)
- **Message** - Console: "[cyan]Creating target branch: 3.x[/cyan]"
- **Fallback** - If creation fails (conflict, permissions), fall back to main

### Confirmation

We'll validate this decision by:
- ✅ Feature 002 WP01 implements without manual branch creation
- ✅ Status commits route to 3.x (not fallback to main)
- ✅ WP01 prompt doesn't mention "Create branch"
- ✅ Tests: test_auto_create_target_branch_on_implement
- ✅ No errors when target_branch already exists (idempotent)

## Pros and Cons of the Options

### Option 1: Auto-create during first implement (CHOSEN)

Just-in-time: Create target branch automatically when first WP is implemented.

**Pros:**
- Automatic (no user input)
- Just-in-time (created when needed)
- Eliminates bootstrap task from WP01
- Enables correct routing immediately
- Clear ownership (tool creates infrastructure)

**Cons:**
- Implicit (might surprise users)
- No opt-out mechanism
- Naming conflict risk (must check existence)

### Option 2: Auto-create during /spec-kitty.specify

Early creation: Create target branch when feature is specified.

**Pros:**
- Branch exists before any implementation
- Explicit timing (during specify)
- No bootstrap paradox

**Cons:**
- Creates branch too early (might not be needed)
- Requires user prompt ("Create 3.x now?")
- Specify becomes interactive (slower)
- Branch created even if feature never implemented

### Option 3: Document bootstrap workflow

Instruct agent in WP01 prompt how to create branch manually.

**Pros:**
- Explicit instructions
- Agent has control
- No code changes

**Cons:**
- Complex workflow (worktree → main repo → worktree)
- Error-prone (agent must get steps right)
- Confusing (not standard WP workflow)
- Still manual (defeats automation)

### Option 4: Remove from WP01, require manual creation

Don't assign branch creation to WP01, require user to create manually.

**Pros:**
- Clean separation (WP01 focuses on features)
- User has control

**Cons:**
- Manual step (user must remember)
- Easy to forget (causes fallback)
- Not automated

### Option 5: Status quo (fallback to main)

Keep current behavior, let WP01 create branch manually if needed.

**Pros:**
- No changes needed
- Graceful degradation

**Cons:**
- Bootstrap paradox persists
- Agent confusion continues
- Fallback routing (not ideal)
- Manual branch creation required

## More Information

**Implementation:**
- `src/specify_cli/cli/commands/implement.py` (auto-create logic before worktree creation)
- Check branch existence: `git rev-parse --verify <branch>`
- Create branch: `git branch <target> main` (from main as base)
- Error handling: If branch exists, proceed normally; if creation fails, fallback to main

**Tests (to be written):**
- `test_auto_create_target_branch_on_first_implement`
- `test_subsequent_implement_uses_existing_target`
- `test_auto_create_fails_gracefully_on_conflict`
- `test_target_branch_routing_after_auto_create`

**Affected Workflows:**
- Feature 002, 003, 004 in ~/tmp (all have non-existent targets)
- Any future feature targeting a new branch

**Related ADRs:**
- ADR-13: Target Branch Routing (uses target_branch for status commits)
- ADR-14: Explicit Metadata Fields (target_branch always set)

**Version:** To be implemented in 0.13.9 or 0.14.0

**Pattern:** "Just-in-Time Infrastructure Creation" - Let tool create infrastructure automatically when first needed
