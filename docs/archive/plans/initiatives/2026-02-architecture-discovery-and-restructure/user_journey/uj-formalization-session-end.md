---
title: 'User Journey: Formalization at Session End (Experiment → Repeatable Approach)'
description: Draft user journey for formalizing an experiment into a repeatable approach at session end, captured 2026-02-17 for the architecture-discovery initiative.
doc_status: deprecated
updated: '2026-09-30'
---
# User Journey: Formalization at Session End (Experiment → Repeatable Approach)

**Status**: DRAFT  
**Date**: 2026-02-17  
**Primary Contexts**: Ad-Hoc Sessions, Specialist Handoffs, Approach Discovery, Formalization  
**Supporting Contexts**: Doctrine Packs, Artifact Capture, Architecture Documentation, Test Suite Evolution  
**Related Spec**: (none yet — design exploration artefact)

---

## Scenario

A user runs an ad-hoc specialist session to experiment with a novel approach: infer functional requirements and non-functional requirements by having a specialist agent read only the test suite and reconstruct expected behavior. An architect specialist then checks the inferred requirements against the actual system design and writes an analysis. At the end of the session, the user decides the approach is valuable and explicitly requests formalization (“write down what we did” / “formalize so it’s repeatable”). The system produces a repeatable description of the approach and optionally proposes follow-up handoffs: updating architecture documentation and/or passing the analysis to development or QA specialists to adjust the test suite.

---

## System Boundaries

| ID | Boundary Name | Description |
|----|--------------|-------------|
| B1 | User Workspace | Local repo: codebase, test suite, architecture docs, working tree changes |
| B2 | Spec Kitty Runtime | Session orchestration, specialist selection, capture, and formalization tooling |
| B3 | LLM Execution Context | Specialist reasoning: test inference, architecture validation, analysis synthesis |
| B4 | Event/Artifact Sink | Where events, memory-dumps, analyses, and formalized approaches are stored |
| B5 | Documentation Surface | Architecture documents / knowledge base location (could be repo docs, ADRs, etc.) |

---

## Actors

| # | Actor | Type | Persona | Role in Journey |
|---|-------|------|---------|-----------------|
| 1 | Developer/Contributor | `human` | (TBD) | Runs experiment, approves handoffs, triggers formalization, decides what to update |
| 2 | Spec Kitty CLI | `system` | (TBD) | Starts session, routes to specialists, captures artefacts, executes formalization |
| 3 | Test-Inference Specialist | `llm` | (TBD) | Reads only tests, reconstructs FRs/NFRs, states assumptions and confidence |
| 4 | Architect Specialist | `llm` | (TBD) | Validates inferred requirements against architecture/design, writes analysis and gaps |
| 5 | Dev Specialist | `llm` | (TBD) | Uses analysis to update implementation guidance or refactor targets (optional) |
| 6 | QA Specialist | `llm` | (TBD) | Uses analysis to update tests: coverage gaps, intent clarity, missing constraints (optional) |
| 7 | Event/Artifact Store | `system` | (TBD) | Persists memory-dumps, analysis report, formalized approach, and key events |

---

## Preconditions

1. Repo contains a test suite that meaningfully encodes behavior.
2. Architecture documentation exists (even if incomplete) OR there is a known design source (ADRs, diagrams, docs).
3. Specialist profiles exist for: test-inference, architect, dev, QA.
4. Session capture is enabled (memory-dump + artifact write-out).
5. The user agrees to “read-only tests” constraint for the inference phase (explicit boundary).

---

## Journey Map

| Phase | Driver | Active Actor(s) | System Boundary | Key Events |
|-------|--------|------------------|-----------------|------------|
| 1. Start Ad-Hoc Session | Human | 1, 2 | B2 | `AdHocSessionStarted` |
| 2. Set Experiment Constraints | Human | 1, 2 | B2 | `ExperimentConstraintSet` |
| 3. Run Test-Only Inference | Human | 1, 3 | B1, B3 | `TestSuiteScanned`, `RequirementsInferred` |
| 4. Capture Inferred FRs/NFRs | Spec Kitty | 2, 7 | B2, B4 | `InferenceArtifactWritten` |
| 5. Architect Validates vs Design | Human | 1, 4 | B1, B3, B5 | `ArchitectureReviewed`, `GapAnalysisProduced` |
| 6. Capture Architect Analysis | Spec Kitty | 2, 7 | B2, B4 | `AnalysisArtifactWritten` |
| 7. Decide Follow-Ups (Docs vs Tests vs Both) | Human | 1, 4 | B2, B3 | `FollowUpDecided` |
| 8. Optional Handoff to Dev / QA | Human | 1, 5 and/or 6, 2 | B2, B3 | `HandoffSuggested`, `HandoffApproved` |
| 9. Apply Updates (Docs and/or Tests) | Human | 1, 2, (5/6) | B1, B5 | `DocsUpdated` and/or `TestsUpdated` |
| 10. End Session + Request Formalization | Human | 1, 2 | B2 | `FormalizationRequested` |
| 11. Formalize Approach into Repeatable Recipe | Spec Kitty | 2, 7, (3/4) | B2, B3, B4 | `ApproachFormalized`, `FormalizationWritten` |
| 12. Close Session | Human | 1, 2 | B2 | `AdHocSessionClosed` |

---

## Coordination Rules

**Default posture**: Advisory

1. Experiment constraints (for example “tests-only inference”) must be explicitly declared before inference begins.
2. Specialist handoffs are suggestions only; the user must approve before switching or engaging additional specialists.
3. Inference and validation outputs must clearly separate:
   - Observed evidence (from tests / docs)
   - Assumptions
   - Confidence level
4. Updates to docs or tests are human-approved actions; specialists can propose diffs but do not apply changes unilaterally.
5. Formalization happens only upon explicit user instruction at session end.
6. Formalization captures what was done as a repeatable approach without implying mission-grade tracing was present.

---

## Responsibilities

### Boundary B1 — User Workspace

1. Provide test suite access and relevant repo context.
2. Accept or reject proposed updates to tests and code.
3. Maintain working tree consistency (branching/staging decisions).

### Boundary B2 — Spec Kitty Runtime

1. Maintain session lifecycle, capture points, and artefact output.
2. Enforce experiment constraints at the tool level where feasible (for example, scope file access to tests directory).
3. Provide explicit “formalize” command handling and artifact generation.
4. Record handoff approvals and follow-up decisions.

### Boundary B3 — LLM Execution Context

1. Infer requirements from tests under declared constraints; state assumptions and uncertainty.
2. Architect validates inferred requirements against architecture/design artefacts; produce a gap analysis and recommendations.
3. Dev/QA specialists translate analysis into actionable doc/test update proposals.

### Boundary B4 — Event/Artifact Sink

1. Persist:
   - inference output (FRs/NFRs)
   - architect analysis
   - session memory-dump
   - formalized approach artefact
2. Provide discoverability by session id/timestamp.

### Boundary B5 — Documentation Surface

1. Accept updates to architecture documents and/or ADRs.
2. Provide a stable reference target for analysis links and follow-up work.

---

## Observability Guarantees

### Event Logging

- Session lifecycle and formalization events are always emitted.
- Key experiment milestones are emitted:
  - constraints set
  - inference produced
  - analysis produced
  - follow-up decision made
- Handoff suggestions and approvals are captured as events.

### State Visibility

- The active specialist and active constraint set are visible during the session.
- The user can see where inference and analysis artefacts were written.
- The user can see whether formalization has occurred and where it was stored.

### Presence & Coordination Signals

- The system surfaces when constraints are active (e.g., “tests-only mode”).
- The system surfaces when proposed updates touch:
  - docs boundary (B5)
  - tests boundary (B1)
  so the user understands impact.

### Audit Guarantees

- Outputs explicitly distinguish evidence vs assumption.
- Formalized approach references the produced artefacts (inference + analysis) as examples.
- This journey does not require mission-grade tracing, but guarantees:
  - memory-dump exists
  - final formalization artefact exists
  - key milestone events exist

---

## Scope: MVP (Formalization at Session End)

### In Scope

1. **Observe**:
   - Active constraint set (“tests-only”)
   - Inference artifact location
   - Architect analysis artifact location
   - Follow-up decision (docs/tests/both)
   - Formalization artifact location

2. **Decide**:
   - Approve constraints
   - Approve handoffs
   - Choose follow-up targets (docs/tests/both)
   - Trigger formalization at session end

### Out of Scope (Deferred)

- Automatic conversion into a Spec Kitty Mission recipe without review
- Guaranteed reproducibility without human editing of the formalized approach
- Hard enforcement of file-access constraints across all environments/tools
- Rich structured tracing comparable to missions (step-by-step provenance)

---

## Required Event Set

| # | Event | Emitted By | Boundary | Phase |
|---|-------|-----------|----------|-------|
| 1 | `AdHocSessionStarted` | Spec Kitty CLI | B2 | 1 |
| 2 | `ExperimentConstraintSet` | Developer/Contributor | B2 | 2 |
| 3 | `TestSuiteScanned` | Test-Inference Specialist | B3 | 3 |
| 4 | `RequirementsInferred` | Test-Inference Specialist | B3 | 3 |
| 5 | `InferenceArtifactWritten` | Spec Kitty CLI | B2/B4 | 4 |
| 6 | `ArchitectureReviewed` | Architect Specialist | B3 | 5 |
| 7 | `GapAnalysisProduced` | Architect Specialist | B3 | 5 |
| 8 | `AnalysisArtifactWritten` | Spec Kitty CLI | B2/B4 | 6 |
| 9 | `FollowUpDecided` | Developer/Contributor | B2 | 7 |
| 10 | `HandoffSuggested` | Specialist Agent | B3 | 8 |
| 11 | `HandoffApproved` | Developer/Contributor | B2 | 8 |
| 12 | `DocsUpdated` | Developer/Contributor | B5 | 9 |
| 13 | `TestsUpdated` | Developer/Contributor | B1 | 9 |
| 14 | `FormalizationRequested` | Developer/Contributor | B2 | 10 |
| 15 | `ApproachFormalized` | Spec Kitty CLI | B2/B3 | 11 |
| 16 | `FormalizationWritten` | Spec Kitty CLI | B2/B4 | 11 |
| 17 | `AdHocSessionClosed` | Spec Kitty CLI | B2 | 12 |

---

## Acceptance Scenarios

1. **Constraint-Limited Inference Produces Requirements Draft**
   Given a repo with a test suite and an active “tests-only” constraint,
   when the user runs the test-inference specialist,
   then FRs and NFRs are inferred, assumptions are stated, and an inference artefact is written.

2. **Architect Validation Produces Gap Analysis**
   Given inferred FRs/NFRs from tests,
   when the architect specialist validates them against architecture/design artefacts,
   then a gap analysis is produced and captured as an analysis artefact.

3. **Formalization at Session End Generates a Repeatable Approach**
   Given inference and analysis artefacts exist for the session,
   when the user requests “formalize” at session end,
   then the system writes a repeatable approach artefact that references the session outputs as exemplars.

4. **Follow-Up Targets Are Human-Decided**
   Given the gap analysis suggests changes to docs and tests,
   when the system suggests handoffs to dev/QA specialists,
   then no updates occur without explicit human approval and the chosen targets are recorded.

---

## Design Decisions

| Decision | Rationale | ADR |
|----------|-----------|-----|
| Ad-hoc sessions support explicit experiment constraints | Enables deliberate technique testing and supports “read-only tests” inference posture | pending |
| Formalization is a session-end, user-triggered operation | Preserves human intent; avoids accidental workflow creation | pending |
| Output artefacts (inference + analysis) are captured by default | Enables later formalization and knowledge reuse without mission overhead | pending |
| Follow-up actions are handoff-based and human-approved | Maintains Human in charge and keeps ad-hoc mode non-invasive | pending |

---

## Product Alignment

1. Encourages disciplined experimentation without mission overhead.
2. Converts emergent practice into repeatable technique via explicit formalization.
3. Maintains doctrine consistency through specialist profiles and structured artefacts, while keeping human control central.
