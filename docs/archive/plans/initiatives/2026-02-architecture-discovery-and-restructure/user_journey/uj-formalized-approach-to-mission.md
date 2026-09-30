---
title: 'User Journey: Formalized Approach → Mission Recipe'
description: Draft user journey turning a formalized approach into a mission recipe, captured 2026-02-17 for the architecture-discovery initiative.
doc_status: deprecated
updated: '2026-09-30'
---
# User Journey: Formalized Approach → Mission Recipe

**Status**: DRAFT  
**Date**: 2026-02-17  
**Primary Contexts**: Formalization, Mission Composition, Step Registry, Doctrine Packs  
**Supporting Contexts**: Ad-Hoc Sessions, Artifact Capture, Event Emission, Recipe Versioning  
**Related Spec**: User Journey – Formalization at Session End (Experiment → Repeatable Approach)

---

## Scenario

A contributor has completed an ad-hoc experimental session and formalized the approach into a repeatable description. The contributor now decides this approach should become a first-class, runnable Spec Kitty mission. The system assists in transforming the formalized description into a structured mission recipe composed of step modules and associated doctrine defaults. The contributor reviews and approves the generated mission definition before it becomes available for structured execution.

---

## System Boundaries

| ID | Boundary Name | Description |
|----|--------------|-------------|
| B1 | User Workspace | Local repo containing specs, steps, missions, and formalization artefacts |
| B2 | Spec Kitty Runtime | Orchestrates conversion of formalized approach into mission recipe |
| B3 | LLM Execution Context | Assists in mapping description → structured recipe |
| B4 | Event/Artifact Sink | Stores formalization artefacts, generated recipe files, and emitted events |
| B5 | Step Registry | Shared step repository (local or remote) providing versioned step modules |

---

## Actors

| # | Actor | Type | Persona | Role in Journey |
|---|-------|------|---------|-----------------|
| 1 | Contributor | `human` | (TBD) | Decides to convert formalized approach into mission |
| 2 | Spec Kitty CLI | `system` | (TBD) | Coordinates recipe generation, validation, and registration |
| 3 | Recipe Generator Specialist | `llm` | (TBD) | Maps formalized approach into structured mission recipe |
| 4 | Step Registry | `system` | (TBD) | Supplies candidate step modules and version metadata |
| 5 | Event/Artifact Store | `system` | (TBD) | Persists generated recipe and related artefacts |

---

## Preconditions

1. A formalized approach artefact exists from a prior session.
2. Step modules are defined in a shared registry (with stable IDs and contracts).
3. Doctrine packs are available for binding defaults.
4. Contributor has write access to mission definition location (e.g., `missions/`).

---

## Journey Map

| Phase | Driver | Active Actor(s) | System Boundary | Key Events |
|-------|--------|------------------|-----------------|------------|
| 1. Request Mission Conversion | Contributor | 1, 2 | B2 | `MissionConversionRequested` |
| 2. Analyze Formalized Approach | Spec Kitty | 2, 3 | B2, B3 | `ApproachParsed` |
| 3. Identify Candidate Steps | Recipe Generator Specialist | 3, 4 | B3, B5 | `CandidateStepsIdentified` |
| 4. Compose Draft Recipe | Spec Kitty | 2, 3 | B2, B3 | `MissionRecipeDrafted` |
| 5. Bind Doctrine Defaults | Spec Kitty | 2 | B2 | `DoctrinePackBound` |
| 6. Present Draft for Review | Spec Kitty | 2, 1 | B2 | `MissionRecipePresented` |
| 7. Contributor Edits/Approves | Contributor | 1 | B1 | `MissionRecipeApproved` or `MissionRecipeRejected` |
| 8. Persist Mission Definition | Spec Kitty | 2, 5 | B2, B4 | `MissionRecipeWritten` |
| 9. Register Mission | Spec Kitty | 2 | B2 | `MissionRegistered` |

---

## Coordination Rules

**Default posture**: Gated

1. No mission is registered without explicit contributor approval.
2. Step references must include version identifiers (pinned or resolved).
3. Recipe generator may suggest alternative step compositions but does not finalize automatically.
4. Doctrine pack binding must be visible and editable before approval.
5. If step registry lacks required modules, the process halts (no silent fallback).

---

## Responsibilities

### Boundary B1 — User Workspace

1. Store mission recipe files.
2. Allow contributor to review and edit draft recipe.
3. Maintain version control over mission definitions.

### Boundary B2 — Spec Kitty Runtime

1. Parse formalized approach into structural elements (phases, artefacts, decisions).
2. Orchestrate step identification and composition.
3. Bind doctrine defaults and validate compatibility.
4. Enforce approval gate before registration.

### Boundary B3 — LLM Execution Context

1. Translate narrative description into step-aligned structure.
2. Map described actions to existing step modules where possible.
3. Flag ambiguous or unsupported steps explicitly.

### Boundary B5 — Step Registry

1. Provide list of available steps with contracts.
2. Support version resolution.
3. Indicate compatibility or missing dependencies.

---

## Observability Guarantees

### Event Logging

- Mission conversion request and approval events are emitted.
- Draft generation and registration events are logged.
- Doctrine pack binding is recorded.

### State Visibility

- Draft recipe content is visible before approval.
- Bound step versions are visible and reviewable.
- Contributor sees whether recipe references local or shared steps.

### Presence & Coordination Signals

- If required steps are missing, system surfaces blocking notice.
- If doctrine pack mismatches step expectations, system surfaces conflict.

### Audit Guarantees

- Final mission recipe references source formalization artefact.
- Step versions are pinned for reproducibility.
- Conversion process is traceable via emitted events.

---

## Scope: MVP (Formalization → Mission Recipe)

### In Scope

1. **Observe**:
   - Draft recipe structure
   - Selected step IDs and versions
   - Bound doctrine pack
   - Source formalization reference

2. **Decide**:
   - Edit recipe before approval
   - Approve or reject recipe creation
   - Adjust doctrine pack binding

### Out of Scope (Deferred)

- Automatic publishing of mission to shared registry
- Auto-generation of new step modules
- Automatic cross-repo propagation
- Complex dependency resolution beyond direct step references

---

## Required Event Set

| # | Event | Emitted By | Boundary | Phase |
|---|-------|-----------|----------|-------|
| 1 | `MissionConversionRequested` | Contributor | B2 | 1 |
| 2 | `ApproachParsed` | Spec Kitty CLI | B2 | 2 |
| 3 | `CandidateStepsIdentified` | Recipe Generator Specialist | B3 | 3 |
| 4 | `MissionRecipeDrafted` | Spec Kitty CLI | B2 | 4 |
| 5 | `DoctrinePackBound` | Spec Kitty CLI | B2 | 5 |
| 6 | `MissionRecipePresented` | Spec Kitty CLI | B2 | 6 |
| 7 | `MissionRecipeApproved` | Contributor | B1 | 7 |
| 8 | `MissionRecipeWritten` | Spec Kitty CLI | B2/B4 | 8 |
| 9 | `MissionRegistered` | Spec Kitty CLI | B2 | 9 |

---

## Acceptance Scenarios

1. **Formalized Approach Can Be Converted to Draft Recipe**
   Given a formalized approach artefact exists,
   when the contributor requests mission conversion,
   then a structured draft recipe referencing candidate steps is generated.

2. **Recipe Requires Explicit Approval**
   Given a drafted mission recipe,
   when the contributor reviews and approves it,
   then the recipe is written to the missions directory and registered.

3. **Missing Steps Block Conversion**
   Given the formalized approach references behavior not covered by existing step modules,
   when conversion is attempted,
   then the system surfaces the missing steps and does not register a mission.

---

## Design Decisions

| Decision | Rationale | ADR |
|----------|-----------|-----|
| Formalized approaches are convertible but not automatically executable | Preserves review and architectural discipline | pending |
| Mission recipes reference versioned step modules | Ensures reproducibility and avoids drift | pending |
| Doctrine pack binding is explicit and reviewable | Keeps behavioral layer transparent and adjustable | pending |
| Conversion is gated (not advisory) | Prevents accidental mission proliferation | pending |

---

## Product Alignment

1. Enables iterative discovery → experimentation → formalization → structured execution.
2. Keeps mission layer opinionated and review-driven.
3. Encourages reusable, composable step ecosystem without losing human control.
