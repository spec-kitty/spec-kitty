# Mission Specification: Declaration-first repo_root/branch resolution entry (Increment 1)

**Mission Branch**: `kitty/mission-declaration-first-repo-root-resolution-01M4TB21`
**Created**: 2026-10-13
**Status**: Draft
**Input**: Issue #6142 — "Increment 1: one declaration-first repo_root/branch resolution entry at the command-entry layer (scoped-shadow-workspace Option B)". Governed by Accepted ADR `docs/adr/4.x/2026-10-10-1-scoped-shadow-workspace-write-boundary-layers-onto-the-partition.md`; parent design spike #3129 (stays open).

## Overview

The artifact-placement seam (`src/mission_runtime/resolution.py`, `artifacts.py`) is
already CWD-invariant: given a `repo_root` + `mission_slug` it derives the physical
read/write surface from the Mission's **stored declaration** (`meta.json` `target_branch`
+ topology), never from the current checkout. Ambient location (cwd / the invoking
worktree / the checked-out HEAD) enters **upstream** of it, in the way command entries
compute the `repo_root`/branch they hand in. Today the "write/read target follows the
Mission's stored declaration, not ambient location" invariant is held by **hand-placed
"never `Path.cwd()`" assertions and a caller-contract, not by construction** — so any new
mutating command re-exposes the 14-issue class by default.

This mission introduces **one typed, declaration-first `repo_root`/branch resolution
entry** at the command-entry layer (`specify_cli`), routes a bounded, named set of
command-entry seeds through it, and folds the invariant in by construction. It is the
ADR's **Increment 1** (Option C's structural step, subsumed as Option B's first,
independently-valuable increment).

**Terminology (named explicitly, per the ADR):** `primary` = the PRIMARY partition /
repository-root checkout (never the Primary Branch `main`); `merge` = lane consolidation
/ branch integration (never publish-to-origin); `routing` = branch-target routing +
placement (never dispatch/model/event routing).

**Non-goals (explicit):** NOT Increment 2 (the capability-scoped write handle in
`mission_runtime` generalising #3128 to the whole mutating surface); NOT Option A (the
shadow-outside-the-store engine); NO change to lane consolidation / branch integration /
rollback / approval-stamp / blob-attribution / coordination-teardown; NO change to what a
lane fundamentally is; NO new size/ratchet gate.

**Escalation surfaced (architectural seam).** The *design* of the typed entry and the
*scope* of the call-site migration are genuinely architectural decisions. They are
recorded here and in the plan for the operator to ratify at merge, not decided silently:
Increment 1 introduces the entry and routes the mission-scoped ambient seeds that are
safe now, and **files-and-links** the merge-target (consolidation non-goal), the
`implement_claim` protected-branch guard (#2453-deferred, ratchet-allowlisted),
create-time, project-scoped, and honest-invocation-identity sites.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A single typed declaration-first resolution entry (Priority: P1)

As a Spec Kitty maintainer adding or maintaining a mission-scoped command, I want one
typed entry that resolves a command's `(repo_root, target_branch)` from the Mission's
stored declaration, so that I never have to re-derive the target from ambient location or
copy the "never `Path.cwd()`" folklore by hand.

**Why this priority**: This is the structural enabler. Without the single typed producer
there is nothing to route the seeds through and nothing to fold the assertions into;
every other story depends on it. It is valuable standalone even if no further increment
lands (ADR Increment 1).

**Independent Test**: Call the entry directly in unit tests over `tmp_path` git fixtures
and assert each branch: declaration present → target is the declared `target_branch`;
declaration absent → the explicit validated primary-branch fallback (never the ambient
checked-out branch); `meta.json` corrupt → fail-closed error propagates; invoked from a
lane worktree → `repo_root` is the canonical primary (collapse), never the worktree; the
returned value carries provenance (declaration vs validated-fallback).

**Acceptance Scenarios**:

1. **Given** a Mission whose `meta.json` declares `target_branch: X`, **When** the entry
   resolves from any checkout, **Then** the resolved branch is `X` and the provenance is
   `declaration`.
2. **Given** a Mission with no declared `target_branch`, **When** the entry resolves,
   **Then** the branch is the repository's configured primary branch via an explicit,
   validated, provenance-marked fallback — never the ambient checked-out branch.
3. **Given** a `meta.json` that exists but is corrupt, **When** the entry resolves,
   **Then** it fails closed (the corruption-signalling error propagates), never silently
   defaulting.

---

### User Story 2 - Command-entry seeds route through the entry; invariant by construction (Priority: P1)

As a maintainer, I want the bounded, named set of mission-scoped command-entry
`Path.cwd()`/branch seeds to be produced by the typed entry, with the hand-placed "never
`Path.cwd()`" assertions at those sites folded into it, so that the invariant holds by
construction at those sites rather than by scattered guards.

**Why this priority**: The entry is only valuable once it is the actual producer at real
call sites; folding the assertions is what converts per-site folklore into a constructed
boundary (ADR Confirmation clause, Standing Order #5).

**Independent Test**: For each routed site, assert the command now obtains its
`repo_root`/branch target from the entry (the ambient `locate_project_root() or
Path.cwd()` seed is gone there), and that the hand-placed assertion/comment it carried is
replaced by the typed call. The entry is the only producer of a routed command's
`repo_root`/branch target.

**Acceptance Scenarios**:

1. **Given** a routed mission-scoped command, **When** it computes its write/read target,
   **Then** the target comes from the typed entry and no ambient `Path.cwd()`/branch seed
   remains at that site.
2. **Given** the routed sites, **When** the "never `Path.cwd()`" invariant is checked,
   **Then** it is held by the typed entry's construction (the folded assertion), not a
   duplicated per-site guard.

---

### User Story 3 - Ambient disagreement resolves to the declaration (or fails closed); fail-closed preserved (Priority: P2)

As a maintainer running a mission-scoped command from a checkout whose ambient location
disagrees with the Mission's stored declaration, I want the command to resolve to the
**declaration** (or fail closed), and I want the existing #3128 / #3328 fail-closed
refusals and worktree-invocation behaviour to be unchanged.

**Why this priority**: This is the behaviour correction the removal of the ambient seed
delivers. It is gated behind US1/US2 (the entry must exist and be wired) and is proven
red-first.

**Independent Test**: Red-first — a test that, before the fix, witnesses a routed command
resolving its target from ambient location when it disagrees with the declaration, and
after the fix resolves to the declaration (or fails closed). Negative tests assert that
`enforce_checkout_identity` (#3128) still refuses a foreign-lane WP write and
`resolve_checkout_identity` (#3328) still refuses a worktree WRITE invocation.

**Acceptance Scenarios**:

1. **Given** a routed mission-scoped command invoked where the checked-out branch /
   worktree disagrees with the Mission's declared target, **When** it resolves,
   **Then** it resolves to the stored declaration (or fails closed) — never to ambient
   location.
2. **Given** a WP-execution write invoked from a foreign lane worktree, **When**
   `enforce_checkout_identity` runs, **Then** it still raises `CheckoutIdentityError`
   (behaviour unchanged).
3. **Given** a WRITE invoked from a worktree, **When** `resolve_checkout_identity` runs,
   **Then** it still fails closed with `FailClosedRefusal` (behaviour unchanged).

### Edge Cases

- **No remote / never-pushed branch**: the primary-branch fallback must resolve
  deterministically without the ambient-HEAD bias (`resolve_primary_branch(... )` cascade),
  marked as validated-fallback provenance.
- **Mission dir absent / create-time window**: the entry is for mission-scoped commands
  that operate on an existing declaration; create-time seeds (declaration being minted)
  are explicitly out of scope and keep their current behaviour.
- **Corrupt `meta.json`**: fail-closed (`MissionMetaReadError` propagates), never a silent
  primary default.
- **Project-scoped command (no single mission)**: not routed — cwd remains the correct
  anchor; filed-and-linked.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Typed declaration-first resolution value + entry exists in `specify_cli`, built on the existing public resolvers | As a maintainer, I want one typed `(repo_root, target_branch, provenance)` producer so that mission-scoped targets come from the declaration, not ambient location. | High | Open | [build] | no — asserted by direct unit tests over each resolver branch |
| FR-002 | Branch resolution is declaration-first with an explicit validated fallback, never the ambient checked-out-branch bias | As a maintainer, I want the entry to read `meta.json` `target_branch` first and fall back to the configured primary branch only as a marked, validated path. | High | Open | [build] | no — negative test asserts ambient HEAD never wins when it disagrees with the declaration |
| FR-003 | `repo_root` is resolved CWD-invariantly (worktree→primary collapse) through the existing canonical resolvers | As a maintainer, I want the root half to stay checkout-identical so reads/writes do not follow a stale worktree. | High | Open | [build] | no — fixture invokes from a lane worktree and asserts the canonical primary root |
| FR-004 | The bounded, named set of mission-scoped command-entry seeds is routed through the entry (the entry is their only `repo_root`/branch producer) | As a maintainer, I want the scattered ambient seeds replaced at the in-scope sites. | High | Open | [build] | no — per-site test asserts the ambient seed is gone and the target comes from the entry |
| FR-005 | The hand-placed "never `Path.cwd()`" assertions at routed sites are folded into the entry (invariant by construction, not duplicated) | As a maintainer, I want the invariant held by the entry's construction at routed sites. | High | Open | [folded] | no — routed sites carry the typed call, not the hand comment; the entry holds the invariant |
| FR-006 | Ambient-disagreement behaviour correction: a routed command resolves to the declaration (or fails closed), proven red-first | As a maintainer, I want the removal of the ambient seed to actually change behaviour where ambient disagreed. | High | Open | [build] | no — red-first test fails on the pre-fix tree, passes on the post-fix tree |
| FR-007 | Existing fail-closed refusals (#3128 `enforce_checkout_identity`, #3328 `resolve_checkout_identity`) and worktree-invocation behaviour are preserved | As a maintainer, I want the entry to feed the fail-closed seams, not replace or weaken them. | High | Open | [ratchet] | no — negative tests prove both refusals still fire unchanged |
| FR-008 | Out-of-scope sibling surfaces are filed-and-linked, not silently widened or left unmentioned | As the operator, I want the deferred sites named with a reason so scope is explicit. | Medium | Open | [folded] | yes — paired with the Deferred section + follow-up issue reference |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Module-chain compliance | The new module lives in `specify_cli`, imports only down-chain (`core`, `mission_runtime`); `test_layer_rules.py` + `test_pyproject_shape.py` stay green with no package-set or layer change. | Architecture | High | Open |
| NFR-002 | Ratchet stays green honestly | `test_no_write_side_rederivation.py` stays green with no allowlist addition and no loosening: the entry adds no `get_current_branch(...) or <fallback>` / `coord_branch or current` grammar and constructs no checkout-derived `CommitTarget`/`safe_commit`. | Reliability | High | Open |
| NFR-003 | Quality gates | New code passes `ruff check`, `ruff format --check --force-exclude`, and `mypy` clean; cyclomatic complexity ≤ 15; no blanket suppressions. | Quality | High | Open |
| NFR-004 | No performance regression | The entry adds at most one `meta.json` read on the resolution path; CLI resolution stays < 2 s for typical projects. | Performance | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Consolidation untouched | No change to lane consolidation / branch integration / rollback / approval-stamp / blob-attribution / coordination-teardown; the merge-target derivation (`mission_accept_merge`) is out of scope. | Technical | High | Open |
| C-002 | Fail-closed seams untouched in behaviour | #3128 / #3328 refusals are preserved verbatim; the entry feeds them, Increment 2 generalises them. | Technical | High | Open |
| C-003 | Read-root stays read-only | `get_status_read_root`'s worktree-preferring READ contract is not collapsed to primary by the entry. | Technical | Medium | Open |
| C-004 | Terminology canon | `primary` / `merge` / `routing` senses named explicitly in code comments, docstrings, and prose; Mission (not Feature). | Regulatory | Medium | Open |

### Key Entities

- **CommandRepoTarget (typed value)**: the declaration-first resolution result — a frozen
  value carrying the canonical `repo_root` (worktree→primary collapsed), the resolved
  `target_branch`, and a `provenance` marker (`declaration` vs `validated_fallback`).
- **Mission declaration**: `meta.json` `target_branch` + topology — the single source of
  truth the entry reads, via `read_target_branch_from_meta` / `get_feature_target_branch`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A newly-added mission-scoped command cannot reach the collapse-to-primary /
  mis-routed-WRITE shapes for its `repo_root`/branch target without going through the
  single typed entry (the entry is the only producer at the routed command-entry sites). — [build] · no-op passable: no
- **SC-002**: The "never `Path.cwd()`" invariant at every routed site is held by the
  typed entry's construction; the per-site hand assertions there can begin to retire. — [folded] · no-op passable: no
- **SC-003**: 100% of the typed entry's resolution branches are covered by direct unit
  tests, and the red-first behaviour-correction test fails on the pre-fix tree and passes
  on the post-fix tree. — [build] · no-op passable: no
- **SC-004**: #3128 and #3328 fail-closed refusals and worktree-invocation behaviour are
  unchanged, proven by negative tests that still fire. — [ratchet] · no-op passable: no
