---
work_package_id: WP02
title: Living C4 views
dependencies:
- WP01
requirement_refs:
- FR-003
- FR-008
planning_base_branch: docs/charter-service-architecture
merge_target_branch: docs/charter-service-architecture
branch_strategy: Planning artifacts for this mission were generated on docs/charter-service-architecture. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into docs/charter-service-architecture unless the human explicitly redirects the landing branch.
subtasks:
- T005
- T006
- T007
- T008
phase: Architecture models
history:
- at: '2026-10-03T08:49:52Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: diagram-daisy
authoritative_surface: docs/architecture/diagrams/
create_intent: []
execution_mode: code_change
owned_files:
- docs/architecture/diagrams/01_context/README.md
- docs/architecture/diagrams/02_containers/README.md
- docs/architecture/diagrams/03_components/README.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 — Living C4 views

## Objective

Update the living C4 model so it depicts the planned charter read service and
later write migration consistently with the ADR, without turning diagrams into
a second decision record.

## Context

Read the ADR produced by WP01 before editing. The living C4 corpus is under
`docs/architecture/diagrams/`; the similarly named 2.x directories are frozen.

## Subtasks

### T005 — System context

Show:

- operators and agent harnesses;
- Spec Kitty CLI;
- planned Charter Service;
- authored charter/pack sources;
- Mission Status Read service as a sibling;
- external Mission UI as a status-service consumer, not a charter consumer.

### T006 — Container view

Show:

- Python CLI with its stable charter API seam and current write adapter;
- planned per-worktree Java Charter Service;
- shared schemas and conformance corpus;
- authored YAML;
- read projection or future storage as an implementation detail;
- separate Mission Status Read service.

The Java container is planned. Do not imply a `services/` implementation exists.

### T007 — Component view

Inside the planned Java service show:

- inbound REST and MCP adapters;
- read and later write application modules;
- pure domain models, policies, and repository ports;
- outbound lossless YAML adapter;
- outbound document projection adapter;
- future SQL adapter as deferred.

All dependency arrows point inward. Infrastructure libraries do not enter the
domain.

### T008 — Cross-link and label

Link each page to the ADR. Use the smallest prose needed to define diagram
scope. Mark planned elements and distinguish current from future behavior.

## Definition of Done

- Context, container, and component views refine one another.
- Every planned Java element is visibly planned.
- The Python write seam and Java read path match the ADR stages.
- The Mission Status Read service is a sibling, not a shared process.
- Mermaid syntax is reviewable and uses consistent names.

## Reviewer Guidance

Reject if diagrams:

- show two simultaneous production read authorities without transition labels;
- show Java write as current;
- put the Java service in shipped implementation mapping;
- make MCP or REST a bypass around the canonical charter seam;
- duplicate ADR rationale.
