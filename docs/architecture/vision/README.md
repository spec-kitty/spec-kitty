---
title: Architecture Vision (living)
description: 'Landing page for the living architecture vision: the current and future, still-changeable forward intent for Spec Kitty, above the per-era history slots.'
doc_status: active
updated: '2026-10-03'
audience: docs/context/audience/internal/system-architect.md
related:
- docs/architecture/README.md
- docs/plans/4-0-0-milestone-roadmap.md
- docs/plans/code-quality/index.md
---
# Architecture Vision (living)

This directory holds the **current and future** architecture vision for Spec Kitty —
forward intent that may still change. It is one of the living architecture surfaces
(see [`../README.md`](../README.md) for the boundary and decay rules).

## What belongs here

- The synthesized "where the architecture is going" narrative for the active era.
- Forward-looking structural intent that has not yet been ratified as an ADR.

## What does NOT belong here

- **Ratified decisions** — those are ADRs under `docs/adr/<era>/` (immutable, era-stamped).
- **Explorations / spikes** — those are research notes under `docs/plans/research/`.
- **Historical vision** — when a vision statement is no longer current/future it is
  *demoted* into its era's history slot, `vision/README-<era>.md` (the decay path; nothing is deleted).

## Vision vs Decision vs Spike

| Artifact | Meaning | Home | Mutability |
|---|---|---|---|
| Vision | Forward intent | `docs/architecture/vision/` (top-level, living) | May change |
| Decision (ADR) | Ratified decision | `docs/adr/<era>/` | Immutable, era-stamped |
| Spike | Exploration | `docs/plans/research/` | Dated record |

## Forward signal for the 4.x line (2026-09-30)

4.0.0 is the active cycle, at release-candidate stage. The authority for its intent is the
[4.0.0 milestone roadmap](../../plans/4-0-0-milestone-roadmap.md); in architecture terms it
points at:

- **Hosted collaboration over Zeitgeist.** Team Kitty is the hosted product, and the only
  outbound hosted path is one bounded moment per lane transition to the team's relay, opt-in
  on the client. The retired sync transport stays retired. See
  [Team Kitty and Zeitgeist](../../context/team-kitty.md).
- **Structural finish.** Post-convergence client surfaces (`zeitgeist_client/`, `saas_client/`)
  settle onto their upstream authorities, and one canonical event store stays the single
  source of lifecycle truth.
- **One governed front door.** A stable, versioned application API that the CLI, UI, MCP
  and SDK consumers build against, rather than parallel ad-hoc surfaces.
- **Charter service strangler.** Move charter reads, then writes, behind the stable
  boundary described by [ADR 2026-10-03-1](../../adr/4.x/2026-10-03-1-charter-read-write-service-strangler.md)
  and the [living C4 model](../diagrams/README.md).
- **No new shadow paths.** Route or extract onto an existing authority; never build a
  parallel one.

The 3.x-era forward signal (2026-08-12) was demoted to the [3.x history slot](README-3.x.md).
