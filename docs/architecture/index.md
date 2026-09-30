---
title: Architecture notes
description: 'Page index for docs/architecture/: the living C4 model, landscape and vision, explanations, models, assessments, templates, and the frozen per-era history.'
doc_status: active
updated: '2026-09-30'
audience: docs/context/audience/internal/system-architect.md
related:
- docs/adr/3.x/2026-04-06-2-connector-auth-binding-separation.md
- docs/adr/3.x/2026-04-06-3-github-app-installation-authority.md
- docs/architecture/README.md
- docs/architecture/feature-detection.md
- docs/architecture/gap-analysis-connector-installation-model.md
- docs/index.md
---
# Architecture notes

Internal architecture and design notes for Spec Kitty subsystems. These pages capture
design rationale and models; they are working engineering material rather than
end-user documentation. This index enumerates every page in `docs/architecture/`
(see [`README.md`](README.md) for the boundary rule and layout). The active release
cycle is 4.0.0; see the [4.0.0 milestone roadmap](../plans/4-0-0-milestone-roadmap.md).

## Living architecture (current + forward)

- [Architecture](README.md) — the corpus landing page: the decisions-vs-consumption boundary rule, living pages, and frozen history.
- [Architecture Vision (living)](vision/README.md) — current and future forward intent, including the 4.x forward signal.
- [Architecture Diagrams (living C4)](diagrams/README.md) — the living C4 model and how its modules map onto the enforced layer packages.
- [Diagrams: System Context (living)](diagrams/01_context/README.md) — C4 level 1, including Team Kitty and the Zeitgeist relay.
- [Diagrams: Containers (living)](diagrams/02_containers/README.md) — C4 level 2.
- [Diagrams: Runtime/Execution Domain (living)](diagrams/02_containers/runtime-execution-domain.md) — C4 level 2 container detail.
- [Diagrams: Components (living)](diagrams/03_components/README.md) — C4 level 3.
- [System Landscape (living)](00_landscape/README.md) — C4 level 0: domain containers and the packages that implement them.
- [Implementation Mapping (living)](04_implementation_mapping/README.md) — C4 level 4: where each architecture concept lives in the source tree.
- [Core Code Patterns Applied in the Codebase](04_implementation_mapping/code-patterns.md) — recurring implementation idioms mapped to components.

## Explanations

- [Explanation](explanation-index.md) — the Divio "understanding-oriented" hub for this section.
- [Spec-driven development](spec-driven-development.md) — the core methodology.
- [Mission system](mission-system.md) — how missions and work packages relate.
- [Mission-type resolution](mission-type-resolution.md) — the doctrine → charter → core seam.
- [Execution lanes](execution-lanes.md) — the lane-based parallel execution model.
- [Git worktrees](git-worktrees.md) — what worktrees share and keep separate.
- [Git workflow: who does what](git-workflow.md) — infrastructure git vs content git.
- [Multi-agent orchestration](multi-agent-orchestration.md) — coordinating work across agents.
- [Zeitgeist publisher and lease identity](zeitgeist-session-identity.md) — logical agents, SaaS leases, and relay session references.
- [Kanban workflow](kanban-workflow.md) — the nine lanes and their transitions.
- [Mission transition gates](mission-gates.md) — the declarative, asset-backed, trust-gated model for the checks that guard lane transitions.
- [The runtime loop](runtime-loop.md) — how `spec-kitty next` inverts control.
- [AI agent architecture](ai-agent-architecture.md) — how Spec Kitty stays agent-agnostic across the 17 supported agents.
- [Why the Divio documentation system?](divio-documentation.md) — tutorials/how-to/reference/explanation mapping.
- [Doctrine relationships](doctrine-relationships.md) — DRG relation types as typed graph edges.
- [Understanding the org doctrine layer](org-doctrine-layer.md) — built-in/org/project doctrine resolution.
- [Understanding Charter: synthesis, DRG, and governed context](charter-synthesis-drg.md).
- [Understanding governed profile invocation](governed-profile-invocation.md) — standalone dispatch under governance.
- [Profile-load reliability](profile-load-reliability.md) — why squads stopped loading charter agent profiles, and the stabilization design (partly shipped in 3.2.6; the rest is on 4.x Work).
- [Charter backend service (future)](charter-backend-service-future.md) — preliminary backlog design for a deployable charter/doctrine resolution endpoint.
- [Documentation Mission Guide](documentation-mission.md) — the Documentation Kitty mission.
- [Understanding the retrospective learning loop](retrospective-learning-loop.md) — the four-category model.
- [The Artifact Placement Seam](artifact-placement-seam.md) — the layer model deciding which physical tree a mission artifact resolves to, and where callers bypass it.
- [Post-merge partition authority](post-merge-partition-authority.md) — one model for the write half (which bytes win per artifact on squash) and the read half (which surface a post-merge reader trusts).
- [Branch-target routing](branch-target-routing.md) — which git branch receives each type of change.
- [WP runtime-state eviction](wp-runtime-state-eviction.md) — evicting runtime-mutable state into the event log.
- [Doctrine artifact kinds](doctrine-kinds.md) — what each of the eight doctrine artifact kinds is for, with a built-in example of each.
- [SPDD and the REASONS Canvas](spdd-reasons.md) — the opt-in Structured-Prompt-Driven Development doctrine pack and its change-intent canvas.
- [Team Kitty and Zeitgeist](../context/team-kitty.md) — the live hosted model: CLI → per-team Zeitgeist relay → Team Kitty Pulse, with the lane-transition sequence diagram.

## Status, trail & workflow models

- [Status model (operator reference)](status-model.md) — the append-only event-log lane state machine, the `--mission` selector, and `mission_id` ULID identity.
- [Trail model](trail-model.md) — how every standalone dispatch writes an auditable JSONL trail for accountability and provenance.
- [Host-surface parity matrix](host-surface-parity.md) — how each supported host surface teaches the governance-injection contract, with per-surface parity status.
- [Spec Kitty mission workflow (canonical authority)](spec-kitty-mission-workflow.md) — the nine-phase end-to-end mission workflow and the focused-PR path.

## Connector & installation decisions

- [Connector auth / binding separation](../adr/3.x/2026-04-06-2-connector-auth-binding-separation.md) — separating connector authentication from binding.
- [GitHub App installation authority](../adr/3.x/2026-04-06-3-github-app-installation-authority.md) — installation-authority model for the GitHub App.

## Assessments

- [Code as a Crime Scene — High-Level Overview](assessments/code-as-a-crime-scene-overview.md) — pedagogical overview of the CaaCS auditing technique (durable methodology explainer; the dated 2026-05 forensic run itself lives under [`docs/plans/engineering-notes/architecture-audits/`](../plans/engineering-notes/architecture-audits/)).

## Calibration reports

- [Calibration Report Template](calibration/README.md) — the per-mission-type DRG context calibration template: does context resolution return what each step needs, and nothing irrelevant?
- [Calibration Report: documentation](calibration/documentation.md).
- [Calibration Report: erp-custom](calibration/erp-custom.md).
- [Calibration Report: research](calibration/research.md).
- [Calibration Report: software-dev](calibration/software-dev.md).

## Ownership & charter models

- [Unified Charter Bundle](06_unified_charter_bundle.md) — the single-file authoritative `charter.yaml` model.
- [Charter Pack Usage Journey](charter-pack-usage-journey.md) — the `apply` → `generate` two-step and the empty-charter dispatch safety net.

## Templates & reference

- [ADR template](adr-template.md) — the shared ADR authoring template used by all eras.
- [Pip vs pipx vs uv](pip-vs-pipx-vs-uv.md) — which installer to use for the Spec Kitty CLI.

## Historical / prior cycle

Kept as records; not maintained as current.

- [Vision history slot — 3.x](vision/README-3.x.md) — the prior era's settled vision, including the 2026-08-12 forward signal.
- [Vision history slot — 2.x](vision/README-2.x.md) — per-era vision record for 2.x.
- [Vision history slot — 1.x](vision/README-1.x.md) — per-era vision record for 1.x.
- [2.x System Context](01_context/README.md) — frozen 2.x C4 level 1 snapshot.
- [2.x Containers](02_containers/README.md) — frozen 2.x C4 level 2 snapshot.
- [2.x Runtime/Execution Domain](02_containers/runtime-execution-domain.md) — frozen 2.x C4 level 2 container detail.
- [2.x Components](03_components/README.md) — frozen 2.x C4 level 3 snapshot.
- [Functional Ownership Map (demoted)](05_ownership_map.md) — superseded narrative; module boundaries are owned by the enforced pyproject package list and layer rules.
- [Architecture: centralized feature detection](feature-detection.md) — the v0.14.0 centralized mission-selection design, superseded by `mission_id` identity.
- [Launch-readiness behavior (coming soon)](launch-readiness-future.md) — superseded pre-Zeitgeist launch plan built on the retired sync gate.
- [Team Kitty (SaaS): the hosted-sync flow](team-kitty-saas.md) — the deleted sync transport, kept as a record.
- [Gap analysis: connector installation model](gap-analysis-connector-installation-model.md) — point-in-time 2026-03 gap analysis against the pre-convergence code.
- [Architecture Documentation Guide](ARCHITECTURE_DOCS_GUIDE.md) — retired 2.x-era guide; redirects to the documentation home and `llms.txt`.
- [Architecture Navigation Guide](NAVIGATION_GUIDE.md) — retired 2.x-era guide; redirects to the documentation home and `llms.txt`.

## See also

- [Documentation home](../index.md)
- [Architecture Decision Records](../adr/index.md)
