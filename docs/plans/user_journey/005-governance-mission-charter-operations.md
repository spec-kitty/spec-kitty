---
title: 'User Journey: Governance Mission Creation and Charter Operations'
description: 'User journey for governance mission creation and charter operations: how charters are interviewed, compiled, and operated, in a field-table record.'
doc_status: deprecated
updated: '2026-09-30'
audience: docs/context/audience/internal/system-architect.md
---
# User Journey: Governance Mission Creation and Charter Operations

> **Historical (2.x-era vision snapshot).** Written in early 2026 and not re-validated against the 4.x CLI. `spec-kitty charter interview` and `charter generate` now exist, while `spec-kitty charter sync` is a no-op kept for compatibility (governance is hand-authored in `charter.yaml`), so the sync steps below no longer apply. Kept as a record. The active cycle is 4.0.0 — see the [4.0.0 roadmap](../4-0-0-milestone-roadmap.md).

| Field | Value |
|---|---|
| **Status** | DRAFT |
| **Implementation Status** | VISION (target-state proposal; not current runtime reality) |
| **Date** | 2026-02-22 |
| **Primary Contexts** | Governance, Charter, Doctrine Curation |
| **Supporting Contexts** | Agent Profiles, Mission Design, CLI Operations |
| **Related Spec / ADR** | `kitty-specs/047-agent-profile-domain-model/spec.md` (not currently present on this branch) |

---

## Scenario

A project maintainer wants a dedicated governance mission workflow that starts
from doctrine curation and ends with charter-level activation. The workflow
must preserve traceability, include explicit charter review/alter commands,
and enforce operational logging behavior through Directive 014 and Directive 015.

---

## Actors

| # | Actor                      | Type     | Persona     | Role in Journey                                                   |
|---|----------------------------|----------|-------------|-------------------------------------------------------------------|
| 1 | Maintainer                 | `human`  | [Maintainer](../../context/audience/internal/maintainer.md) | Defines governance outcome and approves changes                   |
| 2 | codex generic: kitty-aware | `llm`    | [AI Collaboration Agent](../../context/audience/internal/ai-collaboration-agent.md) | Executes curation, updates artifacts, and reports outcomes        |
| 3 | Spec Kitty CLI             | `system` | [Spec Kitty CLI Runtime](../../context/audience/internal/spec-kitty-cli-runtime.md) | Validates commands, updates charter extracts, reports status |

---

## Preconditions

1. Doctrine artifacts exist under `src/doctrine/`.
2. Charter exists at `.kittify/charter/charter.md` (or legacy fallback).
3. Directive 011, Directive 014, and Directive 015 are available and readable.
4. Curation source material is available (for example via `doctrine_ref`).

---

## Journey Map

| Phase                               | Actor(s)                               | System                                                                                               | Key Events                                                         |
|-------------------------------------|----------------------------------------|------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------|
| 1. Clarify governance scope         | Maintainer, codex generic: kitty-aware | Read directives and curation scope before edits                                                      | `GovernanceMissionScopeDefined`                                    |
| 2. Curate candidate inputs          | codex generic: kitty-aware             | Run `/spec-kitty.doctrine curate` and update import candidates per `src/doctrine/curation/README.md` | `GovernanceCurationRequested`, `ImportCandidateUpdated`            |
| 3. Draft governance mission journey | codex generic: kitty-aware             | Write journey and acceptance contract for governance mission flow                                    | `GovernanceMissionJourneyDrafted`                                  |
| 4. Review current charter      | Maintainer, codex generic: kitty-aware | Run `spec-kitty charter status` to inspect current selected doctrine elements                   | `CharterReviewRequested`, `CharterReviewCompleted`       |
| 5. Alter charter selection     | Maintainer, codex generic: kitty-aware | Use `/spec-kitty.charter` to adjust selected directives/profiles/tools/template set             | `CharterChangeProposed`                                       |
| 6. Apply charter extraction    | codex generic: kitty-aware             | Run `spec-kitty charter sync` to update extracted governance YAML                               | `CharterChangeApplied`                                        |
| 7. Validate and document            | codex generic: kitty-aware             | Run tests and produce work-log + optional prompt documentation                                       | `GovernanceMissionValidationPassed`, `DirectiveComplianceRecorded` |

---

## Coordination Rules

**Default posture**: Gated

1. If governance ambiguity or conflicting instruction appears, escalate under Directive 011 before applying charter changes.
2. All implementation work in this journey records execution traces following Directive 014.
3. Prompt quality observations are documented following Directive 015 when ambiguity or reuse value is present.
4. Charter review (`spec-kitty charter status`) must happen before charter alteration.
5. Charter extraction sync (`spec-kitty charter sync`) must happen after charter alteration and before acceptance.

---

## Responsibilities

### Human and LLM Coordination

1. Maintainer defines acceptance boundary for governance mission behavior.
2. codex generic: kitty-aware proposes minimal diffs with explicit rationale and escalation points.
3. Both confirm whether prompt documentation is warranted per Directive 015.

### CLI and Repository Runtime

1. Persist curation records under `src/doctrine/curation/imports/`.
2. Report charter status and stale/synced state through `spec-kitty charter status`.
3. Regenerate extracted charter data through `spec-kitty charter sync`.

---

## Scope: Governance Mission Bootstrap

### In Scope

1. Doctrine curation updates for governance mission enablement.
2. Charter review and charter change command flow.
3. Acceptance contract updates for governance mission path.
4. Directive 011, Directive 014, and Directive 015 adherence checks.

### Out of Scope (Deferred)

- Full governance mission runtime implementation in `src/specify_cli/missions/`.
- Automated policy optimization based on telemetry trends.
- Multi-repository governance rollout orchestration.

---

## Required Event Set

| # | Event                           | Emitted By                 | Phase |
|---|---------------------------------|----------------------------|-------|
| 1 | `GovernanceMissionScopeDefined` | Maintainer                 | 1     |
| 2 | `GovernanceCurationRequested`   | codex generic: kitty-aware | 2     |
| 3 | `CharterReviewRequested`   | codex generic: kitty-aware | 4     |
| 4 | `CharterReviewCompleted`   | Spec Kitty CLI             | 4     |
| 5 | `CharterChangeProposed`    | codex generic: kitty-aware | 5     |
| 6 | `CharterChangeApplied`     | Spec Kitty CLI             | 6     |
| 7 | `DirectiveComplianceRecorded`   | codex generic: kitty-aware | 7     |

---

## Acceptance Scenarios

1. **Governance mission bootstrap follows curation-to-charter flow**
   Given curation inputs are available,
   when `/spec-kitty.doctrine curate` is used and the journey artifacts are updated,
   then charter review runs via `spec-kitty charter status`,
   and charter alteration is applied and extracted via `/spec-kitty.charter` then `spec-kitty charter sync`.

2. **HIC escalation on unresolved governance ambiguity**
   Given an unresolved conflict between curation output and charter selection intent,
   when the implementer cannot resolve scope safely,
   then execution pauses and escalation follows Directive 011 before applying changes.

3. **Directive 014/015 compliance captured for implementation work**
   Given governance-mission changes are implemented,
   when execution completes,
   then a work-log aligned with Directive 014 exists,
   and prompt documentation aligned with Directive 015 is recorded when prompt-quality learning value is present.

---

## Design Decisions

| Decision                                  | Rationale                                                    | ADR     |
|-------------------------------------------|--------------------------------------------------------------|---------|
| Use command-explicit charter control | Keeps governance review and mutation auditable               | pending |
| Gate ambiguity through Directive 011      | Prevents unsafe silent policy drift                          | pending |
| Require Directive 014/015 adherence       | Preserves execution traceability and prompt quality learning | pending |

---

## Product Alignment

1. Keeps governance changes explicit, testable, and reversible.
2. Preserves SSOT behavior through doctrine and charter boundaries.
3. Strengthens agent operating discipline for curation-heavy feature work.
