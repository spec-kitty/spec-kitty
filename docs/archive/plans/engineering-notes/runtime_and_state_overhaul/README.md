---
title: Runtime & State Overhaul — Engineering Notes
description: 'Landing page for the runtime and state overhaul engineering notes: design exploration complete and handed off for ADR finalization (epic #1619).'
doc_status: deprecated
updated: '2026-06-03'
related:
- docs/archive/plans/engineering-notes/runtime_and_state_overhaul/01-ticket-capture.md
- docs/archive/plans/engineering-notes/runtime_and_state_overhaul/02-current-state-map.md
- docs/archive/plans/engineering-notes/runtime_and_state_overhaul/03-architecture-context.md
- docs/archive/plans/engineering-notes/runtime_and_state_overhaul/04-doctrine-constraints.md
- docs/archive/plans/engineering-notes/runtime_and_state_overhaul/05-architectural-synthesis.md
- docs/plans/engineering-notes/runtime_and_state_overhaul/06-proposed-domains-and-splits.md
- docs/archive/plans/engineering-notes/runtime_and_state_overhaul/07-existing-pattern-and-domain-extraction.md
- docs/archive/plans/engineering-notes/runtime_and_state_overhaul/08-architecture-phase-1-summary.md
- docs/archive/plans/engineering-notes/runtime_and_state_overhaul/09-context-decomposition-model.md
- docs/archive/plans/engineering-notes/runtime_and_state_overhaul/10-context-needs-capture.md
- docs/archive/plans/engineering-notes/runtime_and_state_overhaul/11-dialectic-and-revised-claims.md
- docs/archive/plans/engineering-notes/runtime_and_state_overhaul/12-actor-mental-model.md
- docs/archive/plans/engineering-notes/runtime_and_state_overhaul/13-dialectic-mission-vs-missionrun.md
- docs/archive/plans/engineering-notes/runtime_and_state_overhaul/14-model-diagrams.md
- docs/archive/plans/engineering-notes/runtime_and_state_overhaul/15-dialectic-on-the-domain-model.md
- docs/archive/plans/engineering-notes/runtime_and_state_overhaul/16-codebase-reassessment-fanout.md
- docs/archive/plans/engineering-notes/runtime_and_state_overhaul/17-consolidated-domain-model.md
- docs/archive/plans/engineering-notes/runtime_and_state_overhaul/SESSION-RECAP.md
---
# Runtime & State Overhaul — Engineering Notes

> **Retired (deprecated).** Design shipped/superseded via the open-core delivery plan §1.2 "G2 — strangle the core domains onto SSOTs" (execution-context unification, epic #1619) — see `docs/archive/plans/3-2-x-open-core-delivery-plan.md`. Preserved as a historical record.

**Status:** Design exploration complete; handed to @robertDouglass for ADR finalization
**Owner:** Architecture (Architect Alphonso persona) + Stijn Dejongh
**Parent epic:** [Priivacy-ai/spec-kitty#992](https://github.com/Priivacy-ai/spec-kitty/issues/992) — *Epic: drain the bug queue by repairing domain boundaries* (this is its execution-state / context-ownership slice)
**Redesign tracker:** [Priivacy-ai/spec-kitty#1666](https://github.com/Priivacy-ai/spec-kitty/issues/1666) — *Execution-state & context domain-boundary redesign* (child of #992, **blocks** #1619)
**Anchor issue:** [Priivacy-ai/spec-kitty#1619](https://github.com/Priivacy-ai/spec-kitty/issues/1619) — *Epic: Unify mission execution context across coord/main/lane topology*
**Down-payments:** [#1663](https://github.com/Priivacy-ai/spec-kitty/issues/1663) (MissionRun→Mission ref) · [#1664](https://github.com/Priivacy-ai/spec-kitty/issues/1664) (status/ boundary enforcement)
**Started:** 2026-06-03

---

## Why this directory exists

Spec Kitty keeps shipping point-fixes for the same structural failure class: command surfaces
independently re-derive *where* mission state lives, *which* branch is authoritative, and *what*
the agent should be told — so reads, writes, and prompts disagree. PR #1627 closed four concrete
child bugs (#1615–#1618) but the **parent epic #1619 stays open for the structural fix**: one
canonical execution-context authority resolved once and threaded through every surface.

These notes are the **grounding layer** for co-authoring that to-be design. They capture the
problem, the current code, the architectural intent, and the governing doctrine *before* we commit
to a design, so the design conversation is anchored in evidence rather than memory.

> **This is not a decision record yet.** No design option is selected here. The final document
> (`06`) proposes candidate domains/splits and frames the open design questions we will resolve
> together. ADRs follow once we choose.

## Reading order

| # | Document | Purpose |
|---|----------|---------|
| 00 | [README.md](README.md) | This index |
| 01 | [01-ticket-capture.md](01-ticket-capture.md) | Failure modes, evidence, and suggested implementations from #1619 + children (#1615–#1618) + related (#1602, #1348) + the #1627 fix |
| 02 | [02-current-state-map.md](02-current-state-map.md) | How the codebase derives "mission execution context" today, per surface, with the post-#1627 residue |
| 03 | [03-architecture-context.md](03-architecture-context.md) | 3.x architectural intent (ADRs), the 2026-05-25 deep-dive review, and the CAACS audits |
| 04 | [04-doctrine-constraints.md](04-doctrine-constraints.md) | The binding DDD doctrine (DIRECTIVE_001/031/032, paradigms, tactics) that constrains any domain split |
| 05 | [05-architectural-synthesis.md](05-architectural-synthesis.md) | Aggregated architectural reading: root cause, forces, invariants the design must satisfy |
| 06 | [06-proposed-domains-and-splits.md](../../../../plans/engineering-notes/runtime_and_state_overhaul/06-proposed-domains-and-splits.md) | **Technical concretization** (rewritten) — maps the validated model (`17`) to package homes + API entry points; net-new vs existing; the communication-artefact + Effector targets; Strangler sequencing tied to #1663/#1664 |
| 07 | [07-existing-pattern-and-domain-extraction.md](07-existing-pattern-and-domain-extraction.md) | The existing doctrine/charter infra-context pattern to mirror; the `OperationalContext` naming collision; MissionStatus aggregate + MissionFlow FSM extraction assessments (refines `06` §2/§6) |
| 08 | [08-architecture-phase-1-summary.md](08-architecture-phase-1-summary.md) | **Phase 1 checkpoint** — standalone summary of problem, findings, invariants, decided vs open |
| 09 | [09-context-decomposition-model.md](09-context-decomposition-model.md) | **Phase 2** — the conceptual model: Context as composition of domain-owned fragments (infra/filesystem/VC/preferences/state) → fit-for-purpose composites |
| 10 | [10-context-needs-capture.md](10-context-needs-capture.md) | **Phase 2 requirements** — what each actor (code/user/agent) must know at each lifecycle step, across the six dimensions. Lens 1 = intuition; lens 2/3 corroboration in `11` |
| 11 | [11-dialectic-and-revised-claims.md](11-dialectic-and-revised-claims.md) | **Dialectic** — corroborate-vs-refute pass on our claims. Key correction: harden the existing `ActionContext` (ADR 2026-03-09-1), don't greenfield; policy frozen-at-plan; behaviour single-owner; phase derived-not-added |
| 12 | [12-actor-mental-model.md](12-actor-mental-model.md) | **Abstraction level up** — the actor mental model: human / LLM / external system × {sense of self, purpose, environment} mapped to AgentProfile, Charter, Mission, Context. §5a: the Mission is layered (mission + WP state) |
| 13 | [13-dialectic-mission-vs-missionrun.md](13-dialectic-mission-vs-missionrun.md) | **Dialectic** — "Mission ≡ MissionRun?" **Refuted** (1:many cardinality; distinct storage/id/lifecycle). Salvaged: the layered state belongs to Mission; MissionRun is the ephemeral driver and is degenerate in code today |
| 17 | [17-consolidated-domain-model.md](17-consolidated-domain-model.md) | **Consolidated model (baseline)** — code-validated; supersedes `14` Tier 1. Per-domain Contexts (Governance/Execution/Infra) + Shared Kernel code module; Status/kanban shared context; Actor↔**Effector**; prompt = **communication artefact**. Maps to `06` next |
| 16 | [16-codebase-reassessment-fanout.md](16-codebase-reassessment-fanout.md) | **Codebase reassessment** (Debbie/Pedro fan-out, H1–H6) — code confirms every dialectic refutation + 5 emergent findings (Status is a shared context; Actor fragmented; 3 projections; MissionRun gap; runtime home stale). Evidence base for `06` mapping |
| 15 | [15-dialectic-on-the-domain-model.md](15-dialectic-on-the-domain-model.md) | **Dialectic on the design** — core (Mission≠MissionRun aggregate) survives; **refuted**: Context-as-Execution-subdomain (→ Shared Kernel/OHS), Actor-in-Execution (→ cross-domain), Prompt-as-DTO (→ Published Language). Consolidation checklist before mapping to `06` |
| 14 | [14-model-diagrams.md](14-model-diagrams.md) | **Multi-tier diagrams** (Mermaid) — Tier 1 domains (Governance · Mission Management · Execution/Runtime, with Context as a subdomain; Actor realized in Execution; Executor Prompt as boundary DTO) + interrelations; Tier 2 drill-downs; BPMN swimlane; governed-invocation sequence; three-senses overlay |
| — | [SESSION-RECAP.md](SESSION-RECAP.md) | Narrative of how this thinking unfolded — for contributors joining the thread |

## Source provenance

- Ticket bodies and comments fetched from `Priivacy-ai/spec-kitty` issues #1619, #1615, #1616, #1617, #1618, #1602, #1348, and PR #1627 on 2026-06-03.
- Code citations against working tree at the rc35 development checkout (commit context: `main` @ `48a687db3`).
- Architecture digest from `docs/adr/3.x/*` + `docs/plans/engineering-notes/architectural-review/2026-05-25-deep-dive-architectural-review.md` + `docs/plans/engineering-notes/architecture-audits/2026-05-*caacs*`.
- Doctrine digest from `src/doctrine/{directives,paradigms,tactics,styleguides}/built-in/*`.

All `path:line` citations are point-in-time; verify before acting on any single line.
