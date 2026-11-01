---
title: Target Branch Routing for Status Commits
description: Replaced status commits hard-wired to main with an explicit target_branch recorded in meta.json, ending the silent divergence between the two release tracks.
status: Superseded
doc_status: superseded
kind: ADR
date: '2026-01-29'
---

> Superseded on 2026-04-05 by
> `2026-04-03-1-execution-lanes-own-worktrees-and-mission-branches.md`.
> `target_branch` remains the feature's merge destination, but the runtime no
> longer models implementation/status ancestry as "target branch plus one WP
> branch". Mission and lane branches now derive from the target branch instead.

---

## Context and Problem Statement

ADR-12 established a two-branch strategy: `main` (1.x product) and `2.x` (SaaS product). However, spec-kitty's status commit logic was **hard-coded to commit to `main`**, causing race conditions and branch divergence for 2.x features.

**Manifestation (Feature 025 on 2.x):**
```
t=0: Feature 025 created, targets 2.x branch
t=1: WP01 implement creates branch from main (WRONG - should be 2.x)
t=2: Status commits go to main (WRONG - should be 2.x)
t=3: Implementation commits go to WP01 branch
t=4: 2.x advances with new commits (diverges from WP01 base)
t=5: Review fails: git merge-base --is-ancestor 2.x HEAD → FAIL
t=6: Manual rebase onto 2.x required
t=7: More status commits to main (race repeats)
```

**Problem:** How do we route status commits (move-task, mark-status) to the correct target branch (main for 1.x features, 2.x for SaaS features) instead of hard-coding to main?

## Decision Drivers

* **Dual-branch development** - Must support parallel 1.x and 2.x development (ADR-12)
* **Branch isolation** - Main and 2.x must not contaminate each other
* **Race condition prevention** - Status commits must share ancestry with implementation commits
* **Backward compatibility** - Existing features (pre-0.13.8) must continue working
* **Explicit configuration** - Target branch should be visible in metadata (no magic)
* **Hotfix urgency** - Need minimal changes to ship quickly (defer full git state machine to 2.0)

## Considered Options

* **Option 1:** Metadata-driven routing with `target_branch` field in meta.json
* **Option 2:** Git branch detection (infer target from current branch)
* **Option 3:** Environment variable (SPEC_KITTY_TARGET_BRANCH)
* **Option 4:** Feature number convention (025+ → 2.x, 001-024 → main)

## Decision Outcome

**Chosen option:** "Option 1: Metadata-driven routing with target_branch field", because:
* Explicit and visible in meta.json (debugging-friendly)
* Deterministic (same feature → same target)
* Flexible (can change per feature, not per number)
* Self-documenting (grep for "target_branch": "2.x")
* Supports future multi-branch scenarios (3.x, dev, staging)

### Consequences

#### Positive

* **Branch isolation maintained** - Main never sees 2.x status commits
* **Race condition eliminated** - Status and implementation share target branch
* **Explicit configuration** - Target visible in `cat meta.json`
* **Backward compatible** - Legacy features default to "main"
* **Debuggable** - Can grep for features by target: `grep -r '"target_branch": "2.x"'`
* **Flexible** - Can route any feature to any branch (not just 1.x/2.x)

#### Negative

* **Migration required** - Must add target_branch to existing features (m_0_13_8_target_branch)
* **Manual specification** - Users must set target_branch during feature creation
* **Potential confusion** - Users might forget to set for 2.x features
* **Not fully automated** - Could infer from branch, but chose explicit over implicit

#### Neutral

* **Default to "main"** - Safe fallback for legacy features
* **Detection function** - `get_feature_target_branch(repo_root, feature_slug)` → string
* **Routing pattern** - Checkout target, commit, restore original branch

### Confirmation

We validated this decision by:
* ✅ 12 integration tests for dual-branch routing (all passing)
* ✅ Feature 025 successfully developing on 2.x
* ✅ Main branch completely isolated (zero 2.x commits)
* ✅ git merge-base --is-ancestor checks passing
* ✅ Migration adds target_branch to all existing features

## Pros and Cons of the Options

### Option 1: Metadata-driven routing (CHOSEN)

Explicit `target_branch` field in meta.json, read by status commands.

**Pros:**
* Explicit and visible (cat meta.json shows config)
* Deterministic (not environment-dependent)
* Self-documenting (grep finds features by target)
* Flexible (supports any branch name)
* Testable (can mock meta.json)

**Cons:**
* Requires migration (add field to existing features)
* Manual specification during feature creation
* Could forget to set for new features
* Adds to meta.json schema

### Option 2: Git branch detection

Infer target from current git branch (if on 2.x, route to 2.x).

**Pros:**
* No metadata changes required
* Automatic (no user input needed)
* Follows current context

**Cons:**
* Implicit and invisible (debugging hard)
* Environment-dependent (CWD affects behavior)
* Ambiguous (what if on feature branch?)
* Not self-documenting

### Option 3: Environment variable

Set `SPEC_KITTY_TARGET_BRANCH=2.x` in environment.

**Pros:**
* Override capability
* No file changes
* Easy to test

**Cons:**
* Not persisted (lost on shell restart)
* Not visible in feature metadata
* Easy to forget or misconfigure
* Environment pollution

### Option 4: Feature number convention

Features 025+ automatically route to 2.x.

**Pros:**
* No configuration needed
* Clear convention
* Automatic

**Cons:**
* Magic number threshold (not explicit)
* Inflexible (what about 3.x?)
* Not self-documenting
* Assumes numeric ordering = product split

## More Information

**Implementation:**
* `src/specify_cli/core/feature_detection.py::get_feature_target_branch()`
* `src/specify_cli/cli/commands/agent/tasks.py` (lines 669-728: move_task routing)
* `src/specify_cli/cli/commands/agent/tasks.py` (lines 839-887: mark_status routing)
* `src/specify_cli/upgrade/migrations/m_0_13_8_target_branch.py`

**Tests:**
* `tests/integration/test_dual_branch_status_routing.py` (9 tests)
* `tests/integration/test_feature_025_workflow.py` (3 tests)
* `tests/specify_cli/core/test_feature_detection.py::test_get_feature_target_branch_*` (6 tests)
* `tests/specify_cli/upgrade/test_m_0_13_8_target_branch.py` (11 tests)

**Related ADRs:**
* ADR-12: Two-Branch Strategy for SaaS Transformation (establishes need for dual-branch support)

**Version:** 0.13.8 (hotfix enabling 2.x development)

**Supersedes:** None (new capability)

**Superseded by:** Will be replaced by full Git State Machine in 2.0 (Phase 2 plan deferred to 2.x branch)
