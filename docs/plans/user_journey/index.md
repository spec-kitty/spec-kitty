---
title: 'Spec Kitty Architecture: User Journeys'
description: 'Landing page for the Spec Kitty architecture user journeys: end-to-end narratives that drive the evolution and refinement of the system.'
doc_status: draft
updated: '2026-09-30'
audience: docs/context/audience/internal/system-architect.md
related:
- docs/archive/plans/user_journey/001-project-onboarding-bootstrap.md
- docs/archive/plans/user_journey/002-system-architecture-design.md
- docs/archive/plans/user_journey/003-system-design-and-shared-understanding.md
- docs/archive/plans/user_journey/004-curating-external-practice-into-governance.md
- docs/archive/plans/user_journey/005-governance-mission-charter-operations.md
- docs/archive/plans/user_journey/evaluation.md
- docs/plans/user_journey/init-doctrine-flow.md
---
# Spec Kitty Architecture: User Journeys

> **Current state (2026-09-30).** Every design journey below is a 2.x-era vision snapshot
> from early 2026 and has been retired as historical; none has been re-validated against
> the 4.x CLI. The active cycle is 4.0.0 — see the [4.0.0 roadmap](../4-0-0-milestone-roadmap.md).
> New journeys still follow the template and lifecycle described here.

> This directory contains **user journey descriptions** that contribute to
> the evolution and refinement of the Spec Kitty system.
>
> These are architectural design artifacts — they capture how users (human
> and AI) interact with spec-kitty across phases, system boundaries, and
> coordination concerns. They inform mission design, mission templates,
> and CLI command structure.

## Purpose

User journeys in this directory serve three roles:

1. **Design input** — They describe how the system *should* work, driving
   mission specifications and implementation priorities.
2. **Alignment check** — They validate that new capabilities serve the end-to-end
   user experience, not just isolated commands.
3. **Living documentation** — They evolve as spec-kitty evolves, capturing
   the intended workflow at each stage of the system's maturity.

## Template

Journeys follow the [User Journey Template](../../../src/charter/offering/templates/architecture/user-journey-template.md),
which captures:

- **Actors** (with type annotations and persona links)
- **Journey Map** (phase table with events)
- **Coordination Rules**
- **Responsibilities** (split by system boundary)
- **Acceptance Scenarios** (BDD format)
- **Design Decisions** (linked to ADRs)

Persona references in actor tables should point to
`docs/context/audience/internal/*.md` or `docs/context/audience/external/*.md`.

## Status Lifecycle

| Status | Meaning |
|--------|---------|
| `DRAFT` | Proposed journey, under discussion |
| `REVIEW` | Journey reviewed against implementation feasibility |
| `ACCEPTED` | Journey approved as target design — drives mission work |
| `IMPLEMENTED` | Journey fully realized in spec-kitty commands and workflows |

## Implementation Status Field

Each journey metadata table also carries an `Implementation Status` field:

| Value | Meaning |
|---|---|
| `VISION` | Target-state proposal; not yet runtime-implemented |
| `PARTIAL` | Parts implemented, parts still target-state |
| `REALITY` | Matches currently supported runtime behavior |

## Live

- [Init and Project Charter — User Journey](init-doctrine-flow.md) — current, user-facing walkthrough
  of `spec-kitty init` followed by `charter interview` and `charter generate`. It is product
  documentation rather than a design journey and does not follow the template above.

No design journey is currently live.

## Historical (2.x-era vision snapshots)

| Journey | Status | Implementation Status | Description |
|---------|--------|-----------------------|-------------|
| [Project Onboarding & Bootstrap](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/user_journey/001-project-onboarding-bootstrap.md) | DRAFT | VISION | New project setup: init → bootstrap (vision + charter) → first mission |
| [System Architecture Design](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/user_journey/002-system-architecture-design.md) | DRAFT | VISION | Architectural structure and boundary design after bootstrap |
| [System Design & Shared Understanding](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/user_journey/003-system-design-and-shared-understanding.md) | DRAFT | VISION | Design mission flow for glossary, journeys, and ADR alignment |
| [Curating External Practice into Governance](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/user_journey/004-curating-external-practice-into-governance.md) | DRAFT | VISION | Pull-based adoption flow for external practices (e.g., ZOMBIES TDD) via curation + charter activation |
| [Governance Mission Creation and Charter Operations](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/user_journey/005-governance-mission-charter-operations.md) | DRAFT | VISION | Bootstrap flow for governance mission: curation, charter review/alter/sync, and directive-compliant traceability |

## Relationship to Other Architecture Artifacts

- **ADRs** (`docs/adr/`, one folder per era) — Individual design decisions; journeys may reference multiple ADRs
- **Audience personas** (`docs/context/audience/`) — Deep stakeholder/actor profiles linked from journey actor tables
- **Mission specs** (`kitty-specs/`) — Per-mission specifications; journeys span multiple missions
- **Mission Templates** (`src/specify_cli/missions/`) — Journeys inform which missions and phases are needed

## Evaluation

See the [2.x User Journey Evaluation](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/user_journey/evaluation.md) (historical) for the canonical-vs-initiative assessment.
