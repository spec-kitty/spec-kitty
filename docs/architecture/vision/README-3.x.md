---
title: 3.x — vision (history slot)
description: Per-era vision record for the 3.x architecture track, the prior era that closed with the 3.2.7 release; forward vision lives in the living vision page.
doc_status: active
updated: '2026-09-30'
audience: docs/context/audience/internal/system-architect.md
---
# 3.x — vision (history slot)

Per-era **vision** record for the 3.x architecture track. This is part of the
**versioned history beneath** the living architecture (see the
[architecture README](../README.md) for the boundary and decay rules).

3.x is the **prior era**: its last release was 3.2.7 (2026-09-10), and 4.0.0 is the active
cycle. Forward vision lives in the living [vision page](README.md); 3.x-era ADRs are in
`docs/adr/3.x/`. This page is the slot that receives 3.x vision statements once they are
**demoted** from the living page. History accrues by era; nothing is deleted.

## 3.x-era forward signal (2026-08-12)

Demoted from the living vision page on 2026-09-30 under the decay rule. It was the last
forward signal written during the 3.x era.

Forward intent, corroborated by the 2026-08-12 code-health measurement (full detail:
[Code Quality — Working Collection](../../plans/code-quality/index.md)). Not yet an ADR.

The 3.x north-star — a **doctrine-governed, charter-activated runtime with a hardened
execution model** — is showing up in the measurements, not just the design:

- **The stabilization cycle is converging.** Coverage recovered from a mid-2026 trough
  of ~47% to a project-high **84%**, reliability bugs cleared to **0**, and duplication
  holds at **0.5%**. The `next` control loop and the execution-lane / coord-primary
  model are built and canonical; the health signal now tracks the "hardened execution
  model" intent rather than lagging it.
- **The remaining structural debt is scoped, not drifting.** The one standing red — a
  SonarCloud `security_rating` of E from ~21 pre-existing subprocess/path findings —
  concentrates in the lane / coordination / sync surfaces the 3.x execution model built
  out, and maps almost 1:1 onto the **already-planned** Wave 2 / Wave 4 degod slices.
  The forward intent is to burn that backlog down *through* the degod program (with
  characterization tests first), not as cosmetic passes, and to keep the
  charter-as-sole-door and governance-honesty through-lines as the gate on new debt.
- **Governance honesty holds as a design principle.** "Red main is honest; CI is the
  release authority" (ADR 2026-07-17-1) is what lets an honest standing red coexist
  with a cuttable release candidate — the release posture is read from the *functional*
  gates, with the Sonar backlog tracked as known/deferred.
