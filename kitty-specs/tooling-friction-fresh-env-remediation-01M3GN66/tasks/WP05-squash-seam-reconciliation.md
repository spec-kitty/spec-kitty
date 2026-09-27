---
work_package_id: "WP05"
title: "Squash-seam reconciliation, driver registry & C-006 guard (#4955)"
task_type: "implement"
execution_mode: "code_change"
phase: "Phase 1 - Remediation"
dependencies:
  - "WP03"
owned_files:
  - "src/specify_cli/lanes/merge.py"
  - "src/specify_cli/cli/commands/merge_driver.py"
  - "src/specify_cli/cli/commands/init.py"
  - "src/mission_runtime/artifacts.py"
  - ".gitattributes"
  - "src/specify_cli/upgrade/migrations/m_4_0_0_mission_events_merge_driver.py"
  - "tests/architectural/test_merge_reconciliation_class_guard.py"
  - "tests/lanes/test_squash_seam_reconciliation.py"
authoritative_surface: "src/specify_cli/lanes/merge.py"
create_intent:
  - "src/specify_cli/upgrade/migrations/m_4_0_0_mission_events_merge_driver.py"
  - "tests/lanes/test_squash_seam_reconciliation.py"
subtasks:
  - "T012"
  - "T013"
  - "T014"
  - "T015"
  - "T016"
  - "T017"
  - "T018"
planning_base_branch: "claude/tooling-friction-investigation-gpb1yl"
merge_target_branch: "claude/tooling-friction-investigation-gpb1yl"
branch_strategy: "Planning artifacts were generated on claude/tooling-friction-investigation-gpb1yl; completed changes must merge back into claude/tooling-friction-investigation-gpb1yl."
agent_profile: ""
role: "implementer"
agent: "claude"
model: ""
assignee: ""
shell_pid: ""
history:
  - at: "2026-09-27T05:30:00Z"
    actor: "system"
    action: "Prompt generated for the tooling-friction remediation mission"
---

# Work Package Prompt: WP05 – Squash-seam reconciliation, driver registry & C-006 guard (#4955)

## Objectives & Success Criteria

Reconcile derived/append-only mission state on the mission->target squash: re-materialize status.json (WP03 helper) + re-fold decisions/index.json; add a union driver for mission-events.jsonl across all four bound surfaces; decide kitty-ops/lifecycle.jsonl (bespoke union OR documented block); correct the C-006 completeness guard so no artifact is silently exempt.

**Requirement Refs**: FR-004, FR-005, FR-006, FR-007, FR-008, NFR-001

## Context & Constraints

- Mission spec: `kitty-specs/tooling-friction-fresh-env-remediation-01M3GN66/spec.md`
- Plan + concern map: `kitty-specs/tooling-friction-fresh-env-remediation-01M3GN66/plan.md`
- Manifest: `kitty-specs/tooling-friction-fresh-env-remediation-01M3GN66/tasks.md`
- Charter: `.kittify/charter/charter.md` (single canonical authority; canonical sources only; no test skip/disable to green).

## Branch Strategy

- **Planning base branch**: claude/tooling-friction-investigation-gpb1yl
- **Merge target branch**: claude/tooling-friction-investigation-gpb1yl

## Implementation Guidance

Post-squash hook alongside `_preserve_target_newer_planning_artifacts` in `_merge_branch_into`. mission-events.jsonl reuses the `spec-kitty-event-log` driver (like decisions.events.jsonl); seed .gitattributes + init seed + a MergeDriverSeedingMigration subclass; add it to `_MISSION_FILE_KIND_BY_BASENAME`. Re-decide the guard classification explicitly (CLAUDE.md tension). Keep the four test_*_superset*/test_declared_* guards green.

## Test Strategy

- Red-first regression proving the bug, then green after the fix (no-op passable: no).
- Run the owning module's tests plus blast radius; cross-cutting changes additionally run `tests/architectural/`.
- Lint/type: `ruff check .`, `ruff format --check .`, and mypy on changed files — zero issues.

## Risks & Mitigations

- Honor the constraints in spec.md (C-001..C-004). Keep new/edited functions <=15 complexity (NFR-004).

## Activity Log

- 2026-09-27T05:30:00Z – system – Prompt created.
