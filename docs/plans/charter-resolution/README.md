---
title: Charter-Resolution Program
description: 'Program overview, mission map (M1-M6) and run instructions for the charter-resolution defect cluster: org/project doctrine that loads healthy but reaches no consumer.'
doc_status: active
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
---

# Charter-Resolution Program

> **Status (2026-09-30): resumed for 4.x, tracked by #5431 on 4.x Work.** No mission in
> this program has moved since 2026-08-19. Many of the issues it targets have since closed,
> so the first step is to re-baseline the mission map below. M1 stopped after plan setup
> (`PlanStarted`) and M2 after specify (`SpecifyStarted`); M3–M6 are still seeds. The state
> column and "ready for `/spec-kitty.plan`" below are the 2026-08-19 picture.

Authored governance — org-pack and project-tier doctrine — silently fails to reach the dispatched agent. This program closes that class of defect. It rolls up to reach epic **#3530** and fail-loud epic **#3410**.

**One meta-cause:** the resolution surface restates canonical facts (recursion policy, kind vocab, name-vs-id) instead of deriving them from a single authority, and reads doctrine through a second DRG path that never reaches the consumer — every divergence failing green.

See [`program-brief.md`](program-brief.md) for the full investigation-grounded brief (root causes, WP decomposition, sequencing, risks, and the 10 spec-time operator decisions).

## Missions

| # | Mission | Closes | State | Artifact |
|---|---------|--------|-------|----------|
| M1 | Single-Authority Resolution Parity | #3490, #3426, #2981 | **spec'd** | `kitty-specs/single-authority-resolution-parity-01M0CEBQ/` |
| M2 | DRG Read-Path Bridge | #3572, #3573 | **spec'd** | `kitty-specs/drg-read-path-bridge-01M0CHVZ/` |
| M3 | Operating-Procedures Validate→Triage→Data-Drive | #2994, #3352, #3488(edges) | seed | [`seeds/seed-m3-operating-procedures.md`](seeds/seed-m3-operating-procedures.md) |
| M4 | Deliver Loaded Doctrine to the Agent | #3489, #3176, #3389, #3488(render) | seed | [`seeds/seed-m4-doctrine-delivery.md`](seeds/seed-m4-doctrine-delivery.md) |
| M5 | Kind-Complete Cascade + Orphan Wiring | #2829, #3009 residual | seed | [`seeds/seed-m5-kind-complete-cascade.md`](seeds/seed-m5-kind-complete-cascade.md) |
| M6 | Project-Tier DRG Node Emission | #3038 | seed | [`seeds/seed-m6-project-tier-nodes.md`](seeds/seed-m6-project-tier-nodes.md) |

## Sequencing

```
M1 ─┐   (enabling; no golden ripple)          M1 ─► M6   (carve-out; kind-admission)
M2 ─┼─► M3 ─► M4(org reach)
    └─► M4(render/builder) ───►
                          M5   (LAST — re-ledgers golden counts once, atop M2)
```

- **M1 ∥ M2** are the enabling fixes — full specs, ready for `/spec-kitty.plan`.
- **M3–M6** are seeds — each future session runs `/spec-kitty.specify` from its seed, making that mission's operator decisions with fresh context (they depend on enabling-mission outcomes).

## How to run a mission (fresh session)

- **M1 / M2 (already spec'd):** `/spec-kitty.plan` for the mission, then `/spec-kitty.tasks`, then `spec-kitty next`.
- **M3–M6 (seeds):** open the seed, run `/spec-kitty.specify` with it as intake, resolve the seed's open decisions, then plan→tasks→implement.
