---
title: 'ADR 2026-06-03-1: Execution-State Domain Model'
description: 'Splits the CLI into four bounded modules — Governance, Mission Management, Execution/Runtime, Shared Kernel — giving execution state one domain owner.'
status: Accepted
doc_status: active
kind: ADR
date: '2026-06-03'
---

## Context

The spec-kitty runtime has accumulated approximately 40 command surfaces that
independently re-derive execution context (workspace path, feature directory,
branch name). This independent re-derivation is the root cause documented in
issue #1619: the same command produces divergent output depending on whether it is
invoked from the main checkout root or from a lane worktree, because each
surface reconstructs its own view of "where we are" rather than reading from a
single resolved context.

Prior symptom fixes (#1615, #1616, #1617, #1618, #1627) treated individual
surfaces without installing a domain owner. The root cause is architectural:
there is no single module that owns the execution-state domain, so each surface
re-derives context ad hoc.

The doc-01–doc-17 design analysis ratified in #1666 provides the authoritative
domain model for this mission. This ADR locks in the top-level bounded-module
decomposition and the status/kanban ownership decision before any implementation
begins (DIRECTIVE_032, C-001).

## Decision

### Four Bounded Modules

The spec-kitty CLI is organized into four bounded modules with explicit
domain ownership:

| Module | Domain responsibility |
|--------|----------------------|
| **Governance** | Charter and Doctrine artifacts — what the project is allowed to do and how |
| **Mission Management** | Mission lifecycle, WP status/kanban, status events, planning artifacts |
| **Execution / Runtime** | Workspace resolution, branch state, mission run lifecycle, CWD-invariant context |
| **Shared Kernel** | Value types, identifiers, and utilities shared across modules — no domain logic |

Modules communicate via Open Host Service (OHS) facades only. Direct
cross-module imports of internal submodules are prohibited by architectural
tests.

### Status and Kanban Are Owned Exclusively by Mission Management

The `status/` package (`src/specify_cli/status/`) is the OHS facade for all
status reads and writes. No module outside Mission Management may import
`specify_cli.status.<submodule>` directly. External callers use only
`from specify_cli.status import <symbol>`.

`coordination/status_transition.py` is internal Mission Management plumbing; it
may import `status/` internals directly and is explicitly exempt from the
boundary rule.

### Context Is Per-Domain

Each bounded module owns a context type that represents its resolved inputs for
a single operation:

| Context type | Owner | Resolved from |
|---|---|---|
| `GovernanceContext` | Governance module | Charter and Doctrine artifacts active for this project |
| `MissionExecutionContext` | Execution module (`core/execution_context.py`) | Workspace root, branch, feature directory, WP identity |
| `InfraContext` | Execution module | Git remote, CI endpoints, infrastructure credentials |

Context types are resolved once per operation and passed down. They are never
re-derived from CWD mid-operation.

### Keeper Invariants

- `Mission` is not `MissionRun`. A Mission (tracked item in `kitty-specs/<slug>/`)
  has a 1-to-many relationship with Mission Runs (runtime session instances in
  `.kittify/runtime/`).
- `MissionType` belongs to the Governance module. A Mission Type is a reusable
  workflow blueprint; it is not a tracked item. This distinction follows ADR
  `2026-04-04-2-mission-type-mission-and-mission-run-terminology-boundary.md`.

## Consequences

### What changes downstream

- All implementation WPs in this mission (#1663, #1664, #1667, #1673) build on
  this boundary model. None may merge before this ADR is committed (C-001).
- The `status/` module boundary is enforced by an architectural test (WP03).
  Existing bypass imports (~245 at issue-filing time) must be resolved before
  that test can be added.
- `MissionStatus` aggregate (WP04) becomes the authoritative status read/write
  entry point for Mission Management.
- All ~40 residue surfaces that re-derive execution context must route through
  `resolve_action_context` in `core/execution_context.py` (WP06).

### What stays the same

- The `status/` public API (`from specify_cli.status import ...`) is unchanged;
  only the boundary rule is made explicit and enforced.
- Legacy missions (pre-coordination-topology) continue to work without
  modification (NFR-001).
- `coordination/transaction.py` (`BookkeepingTransaction`) is unchanged
  (NFR-003, C-004).

### What is now explicit

- Status and kanban ownership is named: Mission Management, not ad hoc per-surface.
- Cross-module communication is constrained to OHS facades.
- Context derivation happens once per operation, not per surface.
- The Mission ≠ MissionRun keeper invariant is a named architectural constraint.

## Glossary Additions

This ADR introduces the following terms (full entries in project glossary):
`GovernanceContext`, `MissionExecutionContext`, `InfraContext`, `Effector`,
`communication artefact`.

## References

- Mission spec: `kitty-specs/execution-state-domain-remediation-01KT6HVH/spec.md`
- Issue #1619: root-cause analysis and Strangler Fig sequence
- Issue #1674: ADR gate requirement
- Issue #1666: doc-01–doc-17 design analysis (authoritative design basis)
- ADR [`2026-04-04-2-mission-type-mission-and-mission-run-terminology-boundary.md`](2026-04-04-2-mission-type-mission-and-mission-run-terminology-boundary.md): keeper invariants on Mission vs MissionType
- ADR [`2026-04-25-1-shared-package-boundary.md`](2026-04-25-1-shared-package-boundary.md): OHS facade pattern reference
