---
title: Two-Branch Strategy for SaaS Transformation
description: Ships stable local-only 1.x while 2.x develops event sourcing and sync on greenfield, deferring the state migration until the distributed design proves itself.
status: Accepted
date: '2026-01-27'
doc_status: active
kind: ADR
updated: '2026-01-27T00:00:00Z'
---

## Context and Problem Statement

Spec-kitty 1.x is nearing production readiness as a local-only CLI tool. Meanwhile, the SaaS transformation (Features 001-004+) requires fundamental changes:
- Event sourcing with Lamport clocks (replacing YAML activity logs)
- Distributed state management with CRDT merge rules
- Sync protocol for CLI ↔ Django communication
- Private dependency on spec-kitty-events library

**Constraints:**
- Users are actively using 1.x features (cannot break existing workflows)
- SaaS features will take months to complete (Event Log → Sync Protocol → Connector Hub)
- Progressive migration would require maintaining dual state systems (YAML + events)
- No team resources for parallel 1.x feature development during 2.x transformation

**Question:** How do we ship a stable 1.x release while building the SaaS-enabled 2.x without breaking current users or accumulating migration debt?

## Decision Drivers

- **User stability** - 1.x users need a stable, supported version without forced upgrades
- **Development velocity** - 2.x needs greenfield freedom without 1.x compatibility constraints
- **Migration complexity** - Deferred migration is simpler than progressive migration
- **Resource constraints** - Solo developer cannot maintain two active feature branches
- **Release pressure** - Need to ship 1.x soon, but 2.x will take months to complete
- **Dependency management** - 2.x has private dependencies (spec-kitty-events) that 1.x doesn't need

## Considered Options

- **Option 1:** Two-branch strategy with deferred migration
- **Option 2:** Progressive migration (dual state systems in single branch)
- **Option 3:** Postpone 1.x release until 2.x is complete
- **Option 4:** Feature flags for SaaS features (gradual rollout)

## Decision Outcome

**Chosen option:** "Two-branch strategy with deferred migration", because it:
- Allows shipping stable 1.x immediately without SaaS complexity
- Gives 2.x greenfield development freedom (no backward compatibility burden)
- Defers migration complexity until 2.x is substantially complete and proven
- Avoids maintaining dual state systems during transition period
- Cleanly separates concerns (local-only vs. distributed architecture)

### Consequences

#### Positive

- **Stable 1.x release** - Ship production-ready local-only tool without SaaS dependencies
- **Greenfield 2.x** - No backward compatibility constraints during fundamental architecture changes
- **Deferred migration** - Build migration tools when 2.x is proven and stable
- **Clear user expectations** - 1.x users know they're on maintenance-only track
- **No dual state systems** - Avoid complexity of maintaining YAML + events simultaneously
- **Resource focus** - Solo developer concentrates fully on 2.x without 1.x feature requests

#### Negative

- **Branch divergence** - 1.x and 2.x will accumulate differences (harder to cherry-pick fixes)
- **Duplicate bug fixes** - Critical bugs may need fixing in both branches during transition
- **User fragmentation** - Some users stay on 1.x, others adopt 2.x (split community)
- **Migration effort** - Must build migration tools later (deferred cost, not avoided)
- **Documentation split** - Need separate docs for 1.x and 2.x

#### Neutral

- **1.x maintenance** - Security/critical fixes only, no new features
- **No forced migration** - Users can stay on 1.x indefinitely if they don't need SaaS
- **2.x release timeline** - Months away (Event Log → Sync Protocol → Connector Hub → Beta)

### Confirmation

**Validation signals:**
- 1.x release ships cleanly without SaaS infrastructure (validation: no spec-kitty-events dependency)
- 2.x development proceeds without 1.x compatibility PRs (validation: no "support both" code)
- Migration tools work when 2.x nears completion (validation: automated migration script succeeds)
- Users understand branch strategy (validation: clear documentation, no confusion issues)

**Confidence level:** High - This is a standard strategy for major version transitions (Python 2→3, Angular 1→2, etc.)

## Pros and Cons of the Options

### Option 1: Two-Branch Strategy with Deferred Migration

**1.x Branch:**
- Local-only CLI tool
- YAML activity logs (existing system)
- No event sourcing, no sync protocol
- Maintenance-only after initial release (security + critical bugs)
- PyPI releases continue (1.0.0, 1.0.1, 1.0.2, etc.)

**2.x Branch:**
- Greenfield SaaS transformation
- Event sourcing with spec-kitty-events library
- Sync protocol for CLI ↔ Django
- No backward compatibility with 1.x state
- No PyPI releases until substantially complete

**Migration Strategy:**
- Deferred until 2.x nears beta/stable
- Migration tool: `spec-kitty migrate-to-2x` command (to be built later)
- Converts 1.x YAML logs → 2.x event log
- User-initiated (not automatic)

**Pros:**

- Clean separation of concerns (local vs. distributed)
- Greenfield freedom for 2.x (no compatibility constraints)
- Stable 1.x immediately available
- Simpler than dual state systems
- Clear user expectations (maintenance vs. active development)

**Cons:**

- Branch divergence accumulates over time
- Bug fixes may need applying to both branches
- Migration effort deferred (cost paid later)
- Community fragmentation during transition

### Option 2: Progressive Migration (Dual State Systems)

Single `main` branch with both YAML and event log systems active. Feature flags control which system is used.

**Pros:**

- No branch divergence
- Users can opt-in to event log incrementally
- Single codebase to maintain

**Cons:**

- ❌ **Complexity explosion** - Maintaining two state systems simultaneously (YAML + events)
- ❌ **Testing burden** - Must test all combinations (YAML-only, events-only, hybrid)
- ❌ **Performance overhead** - Dual writes to both systems during transition
- ❌ **Migration never completes** - Technical debt accumulates (when can we remove YAML?)
- ❌ **Confusing for users** - Unclear which mode they're in, hybrid state bugs

### Option 3: Postpone 1.x Release Until 2.x Complete

Delay 1.x release until SaaS features are complete, ship only 2.x.

**Pros:**

- No branch management complexity
- Users get best-in-class SaaS experience immediately
- No migration needed (never shipped 1.x)

**Cons:**

- ❌ **Delays stable release by months** - Users waiting for production-ready tool
- ❌ **Higher risk** - First release includes complex SaaS features (more bugs)
- ❌ **Lost feedback** - Cannot learn from 1.x users before building SaaS
- ❌ **All-or-nothing** - Forces SaaS on users who only need local tool

### Option 4: Feature Flags for SaaS Features

Single branch with feature flags: `--enable-events`, `--enable-sync`.

**Pros:**

- Gradual rollout possible
- Users control adoption pace
- Single codebase

**Cons:**

- ❌ **Combinatorial explosion** - Testing matrix: events ON/OFF × sync ON/OFF × ...
- ❌ **Default dilemma** - What should be default? (Forces decision prematurely)
- ❌ **Incomplete features** - Half-working SaaS features confuse users
- ❌ **Technical debt** - When can flags be removed? (Never clear)
- ❌ **Still requires dual state** - Same complexity as Option 2

## More Information

**Implementation Details:**

**Branch Naming Decision:** After analysis, we chose to create **separate `2.x` branch** (not reuse main):

**main Branch (becomes 1.x):**
- Current: v0.13.x (stable development)
- Future: v1.x (maintenance-only after v1.0.0 release)
- No formal "1.x branch" created (main IS the 1.x line)
- Branch protection: Only security/critical fixes merged after v1.0.0
- No new features (frozen feature set)
- YAML activity logs (existing system)
- Documentation: "Spec Kitty 1.x (Local Mode)"

**2.x Branch (created 2026-01-27):**
- Branch: `2.x` (NEW branch created from main)
- Created from: main at v0.13.7 (commit c11ae57)
- Active development: Features 025+ (Event Log → Sync Protocol → SaaS)
- Private dependency: spec-kitty-events via Git (ADR-11)
- Greenfield architecture (incompatible with 1.x)
- No PyPI releases until substantially complete
- Documentation: "Spec Kitty 2.x (SaaS Mode) - Beta"

**Rationale for separate branch**:
- Avoids confusion (main clearly remains stable)
- Enables parallel PRs (1.x fixes on main, 2.x features on 2.x)
- Clearer git history (2.x commits don't pollute main)
- Option to rebase 2.x periodically from main (cherry-pick critical fixes)

**Migration Plan (Deferred to Future Feature):**
- Feature: "2.x Migration Tool" (build when 2.x nears beta)
- Command: `spec-kitty migrate-to-2x`
- Behavior:
  1. Detect 1.x project (`.kittify/activity.yaml` exists)
  2. Parse YAML activity logs
  3. Convert to event log with synthetic Lamport clocks (ordered by timestamp)
  4. Write to `.kittify/events/YYYY-MM-DD.jsonl`
  5. Mark project as 2.x (version flag in config)
  6. Archive 1.x state to `.kittify/1x-backup/`

**Communication Strategy:**
- README badge: "Spec Kitty 1.x (Maintenance Mode)" vs. "Spec Kitty 2.x (Active Development)"
- CHANGELOG: Clear separation of 1.x and 2.x changes
- Documentation: Separate sections for 1.x and 2.x
- GitHub Issues: Tags `1.x` and `2.x` for triage

**Related Decisions:**
- ADR-11: Dual-Repository Pattern (spec-kitty-events dependency)
- Feature 001: SaaS Transformation Research (roadmap)
- Feature 002: Event Log Storage Research (LWW flaw discovery)
- Feature 003: Event Log Library (spec-kitty-events implementation)
- Feature 004: CLI Event Log Integration (2.x foundation)

**Future Considerations:**
- If 2.x adoption is slow, consider maintaining 1.x longer
- If critical 1.x bugs are frequent, reconsider maintenance-only policy
- If migration proves too complex, may need hybrid transition period (dual state)
- Community feedback will determine 1.x end-of-life timeline

**Code References:**
- **1.x line**: `git checkout main` (current: v0.13.x, future: v1.x after v1.0.0 release)
  - No separate "1.x branch" created (main IS the 1.x line)
- **2.x branch**: `git checkout 2.x` (created 2026-01-27 from main at c11ae57)
  - Branch created: `git checkout -b 2.x && git push origin 2.x`
- **Migration script**: `src/specify_cli/cli/commands/migrate_to_2x.py` (to be created later)

**How to contribute**:
- **For stable 1.x fixes**: Branch from main, PR to main
- **For 2.x SaaS features**: Branch from 2.x, PR to 2.x
- **See branches**: `git branch -a | grep -E "(main|2.x)"`
