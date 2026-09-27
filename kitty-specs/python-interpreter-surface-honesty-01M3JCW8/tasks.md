# Work Packages: Python interpreter surface honesty

**Inputs**: `kitty-specs/python-interpreter-surface-honesty-01M3JCW8/` (spec.md, plan.md, research.md)

**Scope note**: FR-006 and FR-007 (declared-versus-tested guard, advisory 3.14 job) are sequenced after PR #5244 (spec C-001) and have no work package in this mission.

Subtasks are reference rows; record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first tests for the kernel primitive | WP01 |  |
| T002 | Implement `kernel.resolution` | WP01 |  |
| T003 | Kernel README entry | WP01 |  |
| T004 | Four-interpreter parity run | WP01 |  |
| T005 | Red-first seam tests | WP02 | [P] |
| T006 | Route `ensure_within_*` through the primitive | WP02 | [P] |
| T007 | Caller audit for the ValueError refusal | WP02 | [P] |
| T008 | command_installer sites | WP02 | [P] |
| T009 | Witnessed reds + parity | WP02 | [P] |
| T010 | atomic_write confinement | WP03 | [P] |
| T011 | decisions/ownership | WP03 | [P] |
| T012 | charter org_pack_config + path_guard | WP03 | [P] |
| T013 | skill_update.is_external_symlink | WP03 | [P] |
| T014 | analysis_report | WP03 | [P] |
| T015 | saas_client project root | WP03 | [P] |
| T016 | Gate scanner | WP04 |  |
| T017 | Allowlist with reasons | WP04 |  |
| T018 | Non-vacuity tests | WP04 |  |

## Work Package WP01: Kernel loop-aware resolution primitive

**Prompt**: `tasks/WP01-kernel-loop-aware-resolution.md`
**Requirement Refs**: FR-001, NFR-001, NFR-002, C-004
**Dependencies**: none

### Included Subtasks

T001 Red-first tests for the kernel primitive (WP01)
T002 Implement `kernel.resolution` (WP01)
T003 Kernel README entry (WP01)
T004 Four-interpreter parity run (WP01)

## Work Package WP02: Containment seams and the two witnessed 3.13 reds

**Prompt**: `tasks/WP02-containment-seams-and-witnessed-reds.md`
**Requirement Refs**: FR-002, FR-003
**Dependencies**: WP01

### Included Subtasks

T005 Red-first seam tests (WP02)
T006 Route `ensure_within_*` through the primitive (WP02)
T007 Caller audit for the ValueError refusal (WP02)
T008 command_installer sites (WP02)
T009 Witnessed reds + parity (WP02)

## Work Package WP03: Remaining loop-sensitive guards

**Prompt**: `tasks/WP03-remaining-loop-sensitive-guards.md`
**Requirement Refs**: FR-004
**Dependencies**: WP01

### Included Subtasks

T010 atomic_write confinement (WP03)
T011 decisions/ownership (WP03)
T012 charter org_pack_config + path_guard (WP03)
T013 skill_update.is_external_symlink (WP03)
T014 analysis_report (WP03)
T015 saas_client project root (WP03)

## Work Package WP04: Architectural gate for loop-aware resolution

**Prompt**: `tasks/WP04-loop-aware-resolution-gate.md`
**Requirement Refs**: FR-005
**Dependencies**: WP02, WP03

### Included Subtasks

T016 Gate scanner (WP04)
T017 Allowlist with reasons (WP04)
T018 Non-vacuity tests (WP04)

## Orchestrator-owned

SC-004 (the one-off 3.14 fast/unit measurement against a 3.12 baseline) is owned by the mission orchestrator and recorded in the PR body, not by a work package.

## Parallel Opportunities

WP02 and WP03 both depend only on WP01 and own disjoint files, so they can run in parallel lanes. WP04 runs last.
