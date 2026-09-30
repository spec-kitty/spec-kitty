---
title: 'User Journey: Ad-Hoc Specialist Session (Quick Task)'
description: Draft user journey for an ad-hoc specialist session (quick task), captured 2026-02-17, exploring lightweight specialist interaction in Spec Kitty.
doc_status: deprecated
updated: '2026-09-30'
---
# User Journey: Ad-Hoc Specialist Session (Quick Task)

**Status**: DRAFT  
**Date**: 2026-02-17  
**Primary Contexts**: Interactive Work, Specialist Profiles, Session Management  
**Supporting Contexts**: Mission System, Artifact Capture, Event Emission, Doctrine Packs  
**Related Spec**: (none yet — design exploration artefact)

---

## Scenario

A contributor or user wants to solve a small, concrete task (bugfix, CI tweak, refactor, quick question) without the overhead of starting a full mission workflow. They start a session with a named specialist agent (for example, QA, reviewer, architect) and work interactively. The system emits the usual events and a “memory-dump” file for continuity, but does not enforce full mission-grade tracing. If the user later decides the approach is worth repeating, they explicitly request formalization (“write down what we did”, “formalize”), which turns the session outcome into a repeatable artefact.

---

## System Boundaries

| ID | Boundary Name | Description |
|----|--------------|-------------|
| B1 | User Workspace | Local repo + working tree where changes and artefacts are produced |
| B2 | Spec Kitty Runtime | CLI/session orchestration, agent selection, and capture mechanics |
| B3 | LLM Execution Context | Specialist reasoning and response generation |
| B4 | Event/Artifact Sink | Where emitted events and memory-dump artefacts are stored (local files, logs, or telemetry pipeline) |

---

## Actors

| # | Actor | Type | Persona | Role in Journey |
|---|-------|------|---------|-----------------|
| 1 | Developer/Contributor | `human` | (TBD) | Initiates ad-hoc session, asks questions, approves handoffs, decides when to formalize |
| 2 | Spec Kitty CLI | `system` | (TBD) | Starts/maintains session, injects doctrine defaults, captures artefacts, emits events |
| 3 | Specialist Agent (e.g., Architect/QA/Reviewer) | `llm` | (TBD) | Provides expertise, suggests follow-ups/handoffs, proposes next actions while keeping human in charge |
| 4 | Event/Artifact Store | `system` | (TBD) | Receives events and “memory-dump” output for later reference |

---

## Preconditions

1. Spec Kitty is available in the repo and can start an interactive session.
2. Specialist agent profiles exist and are selectable (by name or alias).
3. A default doctrine baseline is available (directives/tactics/templates) for consistency across modes.
4. The repo is in a state suitable for quick work (branch exists or can be created; permissions available).

---

## Journey Map

| Phase | Driver | Active Actor(s) | System Boundary | Key Events |
|-------|--------|------------------|-----------------|------------|
| 1. Start Session | Developer/Contributor | 1, 2 | B2 | `AdHocSessionStarted` |
| 2. Select Specialist | Developer/Contributor | 1, 2 | B2 | `SpecialistSelected` |
| 3. Establish Context | Developer/Contributor | 1, 3 | B1, B3 | `ContextProvided` |
| 4. Interactive Work Loop | Developer/Contributor | 1, 3, 2 | B1, B2, B3 | `SuggestionProvided`, `ActionTaken` |
| 5. Optional Handoff Suggestion | Specialist Agent | 3, 1 | B3 | `HandoffSuggested` |
| 6. Human Approval (or Reject) | Developer/Contributor | 1, 2 | B2 | `HandoffApproved` or `HandoffRejected` |
| 7. Capture Session Output | Spec Kitty CLI | 2, 4 | B2, B4 | `MemoryDumpWritten`, `SessionCheckpointed` |
| 8. Close Session | Developer/Contributor | 1, 2 | B2 | `AdHocSessionClosed` |
| 9. Optional Formalize | Developer/Contributor | 1, 2, 3 | B2, B3, B4 | `FormalizationRequested`, `FormalizationWritten` |

---

## Coordination Rules

**Default posture**: Advisory

1. Specialist agents may **suggest** follow-ups or handoffs, but do not switch specialists automatically.
2. Any handoff requires explicit human approval (Human in charge).
3. Ad-hoc sessions do not advance mission state; they remain session-scoped unless the human requests formalization.
4. The system captures a “memory-dump” artefact by default, but does not enforce full mission-grade tracing.
5. Formalization only occurs when explicitly requested by the user (“formalize”, “write down what we did”, equivalent intent).

---

## Responsibilities

### Boundary B1 — User Workspace

1. Apply code/config edits resulting from the session (or decide not to).
2. Maintain local working state (branch, staging, partial changes).
3. Provide local context (files, logs, failing tests) as needed.

### Boundary B2 — Spec Kitty Runtime

1. Manage session lifecycle (start, checkpoint, close).
2. Load and apply specialist agent profile and baseline doctrine defaults.
3. Emit default events and write session artefacts (“memory-dump”).
4. Record human approvals for handoffs and formalization triggers.

### Boundary B3 — LLM Execution Context

1. Respond as a specialist with bounded scope and explicit assumptions.
2. Offer suggestions, handoffs, and next actions without taking control.
3. When formalization is requested, translate the session into a repeatable description.

### Boundary B4 — Event/Artifact Sink

1. Persist emitted events as a lightweight audit trail.
2. Persist the “memory-dump” file(s) for later retrieval and optional formalization.
3. Make captured outputs discoverable (by timestamp/session id/feature association).

---

## Observability Guarantees

### Event Logging

- Session lifecycle events are emitted for: session start, specialist selection, checkpoint/capture, and session close.
- Handoff suggestions and human approval/rejection are emitted as events.
- Formalization request and formalization output emission are captured as events.
- Events are attributable to: Actor (human/system/llm) and Boundary ID (B1–B4).

### State Visibility

- The currently active specialist is visible to the user during the session.
- The session has an identifiable handle (session id or timestamp) used for capture outputs.
- Whether “formalization” has occurred is visible and recorded.

### Presence & Coordination Signals

- The system can surface when a handoff is suggested and requires explicit acknowledgement.
- There is no strict concurrency control in ad-hoc mode by default (advisory posture).

### Audit Guarantees

- Ad-hoc mode provides **lightweight trace** (events + memory-dump artefact), not deep structured tracing.
- Formalization produces a repeatable artefact that can be referenced and reviewed later.

---

## Scope: MVP (Ad-Hoc Specialist Sessions)

### In Scope

1. **Observe**:
   - Active specialist identity
   - Session lifecycle state (started/checkpointed/closed)
   - Captured memory-dump file location
   - Lightweight emitted events

2. **Decide**:
   - Select specialist
   - Accept/reject suggested handoffs
   - Request capture/checkpoint
   - Request formalization explicitly

### Out of Scope (Deferred)

- Automatic mission creation or mission state progression from ad-hoc sessions
- Full mission-grade tracing and step-by-step provenance in ad-hoc mode
- Hard locking / lease-based coordination for concurrent ad-hoc sessions
- Automatic cross-session memory stitching beyond the memory-dump artefacts

---

## Required Event Set

| # | Event | Emitted By | Boundary | Phase |
|---|-------|-----------|----------|-------|
| 1 | `AdHocSessionStarted` | Spec Kitty CLI | B2 | 1 |
| 2 | `SpecialistSelected` | Spec Kitty CLI | B2 | 2 |
| 3 | `ContextProvided` | Developer/Contributor | B1 | 3 |
| 4 | `SuggestionProvided` | Specialist Agent | B3 | 4 |
| 5 | `ActionTaken` | Developer/Contributor | B1 | 4 |
| 6 | `HandoffSuggested` | Specialist Agent | B3 | 5 |
| 7 | `HandoffApproved` | Developer/Contributor | B2 | 6 |
| 8 | `HandoffRejected` | Developer/Contributor | B2 | 6 |
| 9 | `MemoryDumpWritten` | Spec Kitty CLI | B2/B4 | 7 |
| 10 | `SessionCheckpointed` | Spec Kitty CLI | B2/B4 | 7 |
| 11 | `AdHocSessionClosed` | Spec Kitty CLI | B2 | 8 |
| 12 | `FormalizationRequested` | Developer/Contributor | B2 | 9 |
| 13 | `FormalizationWritten` | Spec Kitty CLI | B2/B4 | 9 |

---

## Acceptance Scenarios

1. **Start and Complete a Quick Task Session**
   Given Spec Kitty is available and a specialist profile exists,
   when the user starts an ad-hoc session and works through a small task,
   then the system records session start/close events and writes a memory-dump artefact.

2. **Suggested Handoff Requires Human Approval**
   Given a specialist suggests consulting another specialist,
   when the user rejects the suggestion,
   then no specialist switch occurs and a `HandoffRejected` event is emitted.

3. **Formalization Happens Only on Explicit Request**
   Given a completed ad-hoc session with captured memory-dump output,
   when the user requests “formalize”,
   then a formalization artefact is generated and a `FormalizationWritten` event is emitted.

---

## Design Decisions

| Decision | Rationale | ADR |
|----------|-----------|-----|
| Ad-hoc sessions are session-based by default | Supports quick tasks without mission overhead; preserves lightweight interaction | pending |
| Emit default events + memory-dump files, but no deep tracing | Maintains continuity and minimal auditability without complexity creep | pending |
| Handoffs are suggestion-only and require explicit approval | Preserves Human in charge and avoids agent-driven mode drift | pending |
| Formalization is explicit (“write down what we did”) | Prevents surprise process creation and respects user intent | pending |

---

## Product Alignment

1. Preserves Spec Kitty’s mission identity while supporting lightweight quick-task work.
2. Maintains doctrine consistency across structured and ad-hoc modes without conflating them.
3. Keeps governance and control with the user (Human in charge).
