---
title: 2.x ADRs
description: Index and era history for the 2.x decisions — event-sourced status, doctrine and glossary governance, tracker connectors, and the canonical runtime next command loop.
doc_status: active
updated: '2026-08-10'
type: explanation
audience: docs/context/audience/internal/system-architect.md
---

# 2.x ADRs

Architectural Decision Records for the 2.x track. **Not the current track —
see [`docs/adr/3.x/`](../3.x/index.md) for current decisions.**

## Era history

The 2.x era transformed Spec Kitty from a local-first CLI into a governed,
event-sourced mission runtime with optional hosted projection. Five behavioral domains
crystallized in this era and still frame the architecture:

- **Project and governance onboarding** — capturing project intent and compiling
  governance defaults so missions start under an explicit charter rather than ad-hoc
  conventions.
- **Mission runtime and flow control** — the canonical `next` command loop, runtime-owned
  mission discovery and loading, and rich JSON outputs for agent-driven commands.
- **Doctrine and knowledge governance** — the doctrine artifact governance model and the
  living glossary/context curation model that supply validated policy context to the
  runtime.
- **Work-package state and evidence** — the canonical WP status model, the lifecycle state
  machine, and event-log merge semantics that made lifecycle state append-only and
  auditable. Runtime **decides** what should happen next; the status/event model
  **validates and persists** what did happen — a separation this era made load-bearing.
- **External integration boundaries** — orchestrator and tracker connector surfaces that
  project host state outward without ceding lifecycle authority, including the
  tracker-agnostic connector architecture and Docker-sandboxed / fresh-context execution
  modes.

Two invariants from this era carry forward: **runtime decisioning is separate from state
mutation**, and **branch/target-line routing is authored in mission metadata**, not
inferred from the invocation location. The era also introduced the versioned 1.x/2.x
docs-site posture without committing to a hosted platform, and hardened the
verify/doctor command taxonomy and post-merge audit primitives.

This track captured the architecture through the 2.x → 3.x cutover. The current track is
[3.x](../3.x/index.md); the foundational decisions are [1.x](../1.x/index.md).

## Naming

- `YYYY-MM-DD-N-descriptive-title-with-dashes.md` where `N` increments per ADR landed on a
  given date (1, 2, 3…).

## Source of Truth

This folder is canonical for 2.x decisions (dates before 2026-03-30, the
3.0.0 release). ADRs dated on or after 2026-03-30 were moved to
[`docs/adr/3.x/`](../3.x/index.md). The `architecture/` tree was removed by the
Common Docs structural move (PR #2225); existing references using the old
`architecture/2.x/adr/<filename>` or `architecture/adrs/` paths should be updated to the
new `docs/adr/` paths.

## Status Conventions

- `Accepted` means the decision remains current policy.
- `Superseded` means a newer ADR replaced the decision; keep the file for history, but do not implement from it.
- `Deprecated` means the direction is in active retirement and should not receive new work.
