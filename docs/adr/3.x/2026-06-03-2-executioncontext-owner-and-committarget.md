---
title: 'ADR 2026-06-03-2: ExecutionContext Owner and CommitTarget Atomicity'
description: 'Names `resolve_action_context` the single canonical ExecutionContext resolver, and adopts CommitTarget as ergonomic hardening rather than a correctness fix.'
status: Accepted
doc_status: active
kind: ADR
date: '2026-06-03'
---

## Context

Two related structural decisions are needed before implementation WPs can begin:

**Problem 1 — ExecutionContext ownership**: Approximately 40 command surfaces
independently resolve workspace root, branch name, and feature directory from
CWD. This produces divergent behavior when the same command is invoked from
different directories (main checkout vs. lane worktree). A single canonical
resolver is required.

**Problem 2 — CommitTarget safety**: The `safe_commit` function in the
execution domain accepts a worktree root and a destination ref as separate
parameters. A forensic pass of the `safe_commit` call graph (7 direct call
sites, all examined) confirmed the invariant `(worktree_root, destination_ref)`
is always structurally enforced by `safe_commit` itself. Introducing
`CommitTarget` as a named value type is ergonomic hardening of already-clean
code, not a correctness fix.

The design analysis in doc-06 of #1666 evaluated three options for the
ExecutionContext resolver (A: full rewrite, B: new canonical resolver,
C: Strangler Fig via existing OHS). This ADR records the chosen option.

## Decision

### Decision 1: `resolve_action_context` Is the Canonical OHS Entry Point

`resolve_action_context` in `src/specify_cli/core/execution_context.py` is the
single canonical resolver for `ExecutionContext`. It fuses planning context
(mission slug, WP identity read from mission artifacts) with execution context
(workspace path, branch) and returns a fully resolved `ExecutionContext` object.

**Rules:**
- Execution context is resolved once per operation by calling
  `resolve_action_context`.
- The resolved context is passed down to all callees as a value object.
- No callee may independently re-derive workspace path, branch, or feature
  directory from CWD after context has been resolved.
- New surfaces must call `resolve_action_context` first; they must not
  construct `kitty-specs/<slug>` paths directly (FR-031).

**Migration strategy — Strangler Fig Option C → B**:

The implementation uses the Strangler Fig pattern:

1. `resolve_action_context` already exists as an OHS entry point (Option C).
2. The migration routes each residue surface through the existing entry point
   one at a time, without a big-bang rewrite (Option B execution).
3. Once all residue surfaces are routed through `resolve_action_context`,
   duplicated path-builder functions that become unreachable are deleted
   (FR-034).

This approach was chosen over Option A (full rewrite) because the existing OHS
entry point is structurally correct; it needs consumers, not replacement.

### Decision 2: `CommitTarget` Is a Planned Value Type — Strangler Step 7

`CommitTarget` is a self-validating value type pairing `(worktree_root: Path,
destination_ref: str)`. It will replace the two-argument calling convention of
`safe_commit` with a single atomic argument.

**Key facts confirmed by the forensic pass:**
- `safe_commit` has 7 direct call sites in the codebase.
- All 7 call sites supply consistent, correct `(worktree_root, destination_ref)`
  pairs; the invariant is already structurally enforced by `safe_commit` itself.
- There is no active correctness defect in the call graph.

**Status**: `CommitTarget` is Strangler step 7 (the final step). It is
ergonomic hardening, not a correctness fix. It carries no design risk to steps
1–6 and must not block them. The type will be introduced after steps 1–6 are
complete.

## Consequences

### What changes downstream

- WP06 (ExecutionContext hardening) routes `runtime_bridge` query-mode and
  `workflow.py` fix-mode through `resolve_action_context`.
- All residue surfaces that construct `kitty-specs/<slug>` paths directly are
  removed and replaced with `resolve_action_context` calls.
- `CommitTarget` is introduced as the final hardening step after the other
  surfaces are routed.

### What stays the same

- `resolve_action_context` in `core/execution_context.py` is unchanged; this
  ADR names it as canonical rather than replacing it.
- All 7 existing `safe_commit` call sites are correct; they need no functional
  change before `CommitTarget` is introduced.
- `BookkeepingTransaction` internals are not modified (NFR-003, C-004).

### What is now explicit

- `resolve_action_context` is the named OHS entry point for `ExecutionContext`.
  This is no longer implicit.
- The Strangler Fig migration order is declared: route surfaces → delete dead
  code → introduce `CommitTarget`.
- `CommitTarget` introduction is explicitly deferred to step 7 to unblock steps
  1–6.

## References

- Mission spec: `kitty-specs/execution-state-domain-remediation-01KT6HVH/spec.md`
- Issue #1619: Strangler Fig sequence
- Issue #1673: ExecutionContext hardening implementation
- Issue #1666 doc-06: ExecutionContext resolver options A/B/C analysis
- ADR [`2026-06-03-1-execution-state-domain-model.md`](2026-06-03-1-execution-state-domain-model.md): domain model gate
- `src/specify_cli/core/execution_context.py`: canonical OHS entry point file

## Addendum (2026-06-10 — missions 01KTPKST + 01KTRC04)

This addendum records what was actually delivered against this ADR's sketch. It
is an append-only record of canonical drift — the body above is preserved as the
original decision; this section is the binding correction.

### (a) `resolve_action_context`'s actual home

The ADR body names `src/specify_cli/core/execution_context.py` as the canonical
OHS entry point for `resolve_action_context`. That path is now **retired**. Post
shared-package-boundary (ADR `2026-04-25-1-shared-package-boundary.md`), the
runtime context surface moved into the shared package: `resolve_action_context`
lives in **`src/mission_runtime/resolution.py`** (with `CommitTarget` /
`ExecutionContext` in `src/mission_runtime/context.py`). References above to the
`specify_cli/core/execution_context.py` path are historical.

### (b) Delivered `CommitTarget` shape — deliberate, canonical drift

The ADR sketched `CommitTarget` as `(worktree_root, destination_ref)`. The
delivered, now-canonical shape is:

```python
CommitTarget(ref: str, kind: CommitTargetKind)   # kind ∈ {PRIMARY, COORDINATION, FLATTENED}
```

`ref` is the single destination authority (the short branch name); `kind`
classifies the topology. This is a **deliberate drift**, not an oversight:
`worktree_root` did not vanish — it enters the guard via `ProtectionState`
(the pure value object the `git.commit_helpers` facade probes from the repo and
hands to `core.commit_guard.evaluate`), keeping `CommitTarget` an I/O-free value
and `evaluate` free of git/env/filesystem calls. The `(ref, kind)` shape is the
canonical contract going forward.

### (c) Step 7 delivered

The ADR deferred `CommitTarget` introduction to "step 7" of the Strangler Fig
sequence to unblock steps 1–6. Step 7 is now **delivered** across two missions:

- **01KTPKST** built `CommitTarget` (the `(ref, kind)` value object in
  `mission_runtime`) and the resolver path that produces it.
- **01KTRC04** made `safe_commit` *consume* `CommitTarget` (the
  `git.commit_helpers` facade is the single C-GUARD-1 entry point), **folded the
  five legacy privilege channels** — `_is_protected_branch_exception`,
  `allow_protected_branch_in_test_mode`,
  `allow_completed_op_on_protected_branch`, `_is_completed_op_record_exception`,
  `_test_mode_allows_protected_branch` — into the asserted-at-the-surface
  **`GuardCapability`** (authorization is now an explicit caller argument, never
  derived from message text, file content, env, or op records), and **extracted
  the SK policy module `src/specify_cli/core/commit_guard.py`** whose
  `evaluate()` is the ONE protected-branch decision.

The single-authority + capability model is permanently ratcheted by
`tests/architectural/test_safe_commit_import_boundary.py` (#1355): `evaluate` has
exactly two blessed importers (the facade + `coordination.policy`), the five
deleted channels must have zero references in `src/`, and the residual two-arg
`safe_commit(destination_ref=...)` compat shim is allowlisted to its single
remaining call site so it cannot regrow a userbase before retirement.

### Addendum references

- Mission spec: `kitty-specs/tooling-stability-guard-coherence-01KTRC04/spec.md` (FR-008, FR-009, NFR-004)
- Contracts: `kitty-specs/tooling-stability-guard-coherence-01KTRC04/contracts/` (C-GUARD-1, C-GUARD-2)
- ADR [`2026-04-25-1-shared-package-boundary.md`](2026-04-25-1-shared-package-boundary.md): the boundary that retired the `specify_cli/core/execution_context.py` path
- Issue #1355: import-boundary ratchet
- `src/mission_runtime/resolution.py` + `src/mission_runtime/context.py`: canonical `resolve_action_context` / `CommitTarget` home
- `src/specify_cli/core/commit_guard.py`: the extracted SK policy module (single `evaluate` decision)
