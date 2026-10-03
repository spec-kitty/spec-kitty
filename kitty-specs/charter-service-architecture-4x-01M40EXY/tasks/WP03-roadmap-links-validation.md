---
work_package_id: WP03
title: 4.x placement and validation
dependencies:
- WP01
- WP02
requirement_refs:
- FR-004
- FR-005
- FR-008
planning_base_branch: docs/charter-service-architecture
merge_target_branch: docs/charter-service-architecture
branch_strategy: Planning artifacts for this mission were generated on docs/charter-service-architecture. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into docs/charter-service-architecture unless the human explicitly redirects the landing branch.
subtasks:
- T009
- T010
- T011
- T012
phase: Promotion and validation
history:
- at: '2026-10-03T08:49:52Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: curator-carla
authoritative_surface: docs/
create_intent: []
execution_mode: code_change
owned_files:
- docs/plans/4-0-0-milestone-roadmap.md
- docs/architecture/vision/README.md
- docs/plans/charter-resolution/README.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 — 4.x placement and validation

## Objective

Place the ADR and C4 model in the active 4.x planning and navigation surfaces
without repeating their architecture, then validate the aggregate change.

## Context

Read the ADR and C4 pages from WP01 and WP02. The active planning tree is
`docs/plans`; there is no canonical `docs/planning` tree.

## Subtasks

### T009 — Roadmap placement

Update the strangler-prep spine and its explanation in
`docs/plans/4-0-0-milestone-roadmap.md`:

- Java charter read service → #645 / 4.x Work;
- later Java write migration → #2519 / CLI 4.x stable;
- neither gates milestone 11.

Keep this to one focused clause and one spine annotation. Link to the ADR.

### T010 — Architecture vision pointer

Add one forward-intent bullet to `docs/architecture/vision/README.md` linking to
the ADR and living C4 views. Do not repeat transition mechanics.

### T011 — Charter-domain plan pointer

Use `docs/plans/charter-resolution/README.md` only if it is the current
charter-domain plan. Add one link and placement sentence. If the file is
historical or has a narrower owner, do not force the edit; document the reason
in the Mission trace instead.

### T012 — Validate the aggregate

- Check all changed relative links.
- Inspect Mermaid blocks for coherent syntax and labels.
- Run `pytest tests/architectural/test_no_legacy_terminology.py`.
- Discover and run targeted documentation or architecture-index tests covering
  the changed paths.
- Confirm no changed page claims measured Java performance, inference savings,
  or adoption improvement.

## Definition of Done

- Roadmap placement is explicit and off the GA gate.
- Vision and domain-plan pages are pointers, not duplicate decisions.
- Links and targeted gates pass.
- Any unrelated baseline failure is classified, not fixed opportunistically.
- Exact validation commands and counts are recorded for review.

## Reviewer Guidance

Reject if:

- roadmap prose restates the ADR;
- the same work item is placed on both milestones;
- the change implies implementation already exists;
- Java ecosystem advantages are asserted as measured;
- `docs/planning` is introduced;
- a failed link or terminology check is waived without evidence.
