---
work_package_id: WP01
title: Canonical charter redesign ADR
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-006
- FR-007
planning_base_branch: docs/charter-service-architecture
merge_target_branch: docs/charter-service-architecture
branch_strategy: Planning artifacts for this mission were generated on docs/charter-service-architecture. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into docs/charter-service-architecture unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
phase: Decision
history:
- at: '2026-10-03T08:49:52Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: architect-alphonso
authoritative_surface: docs/adr/4.x/
create_intent:
- docs/adr/4.x/2026-10-03-1-charter-read-write-service-strangler.md
execution_mode: code_change
owned_files:
- docs/adr/4.x/2026-10-03-1-charter-read-write-service-strangler.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 — Canonical charter redesign ADR

## Objective

Author one Proposed 4.x ADR that owns the staged charter redesign. Replace the
competing designs in the investigation notes with the final operator direction.

## Context

Read the Mission `spec.md`, `plan.md`, `research.md`, and
`contracts/promotion-contract.md`. The original gitignored research corpus is
evidence, not canonical text. The final adjudication is:

- Python remains the production write path and the CLI transition seam.
- Java becomes the production read implementation after conformance.
- Python may be a temporary loud fallback, then production Python reads retire.
- Java writes move operation-by-operation after lossless YAML evidence.
- Schemas, semantic rules, identifiers, diagnostics, and fixtures form the
  language-neutral contract.

The Mission Status Read service is a sibling precedent. Do not amend its ADR or
put charter semantics into its domain.

## Subtasks

### T001 — Separate current decision from investigation history

Identify and explicitly reject the earlier projection-server interpretation
where Python remains the permanent semantic compiler. Do not copy measurements,
token guesses, or unverified library selections into the ADR.

### T002 — Author the decision

Use the canonical ADR shape in `docs/architecture/adr-template.md`. Include:

- context and 4.x placement;
- decision and staged ownership table;
- hexagonal dependency direction;
- read/write infrastructure module separation;
- pure domain model and inward repository ports;
- cross-language contract;
- sibling relationship to Mission Status Read.

### T003 — Make the gates non-fakeable

Read cut-over:

- shadow comparison against Python;
- Java-primary stage with loud fallback;
- explicit fallback-retirement criteria;
- Java-only production reads as the intended end state.

Write cut-over:

- codec identity;
- mapping identity;
- confined mutation proving the domain object participates;
- operation-by-operation migration.

Keep read conformance and write parity as separate milestones.

### T004 — Consequences and deferrals

Record:

- temporary double implementation;
- separate release artifact and cross-OS matrix;
- per-worktree lifecycle and security implications;
- no 4.0.0 GA impact;
- stack, build tool, SQL, exact YAML library, performance, and adoption benefit
  as deferred.

## Definition of Done

- ADR status is Proposed.
- One owner is named for reads and writes at every stage.
- The projection-server design cannot be mistaken for the current decision.
- No unverified implementation detail is presented as settled.
- All related links are relative and valid.

## Reviewer Guidance

Reject if the ADR:

- leaves Python as an unspecified permanent fallback;
- claims Java performance or adoption benefits as measured;
- makes round-trip identity the only write gate;
- duplicates the Mission Status Read decision;
- places the work on milestone 11.
