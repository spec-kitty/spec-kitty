---
work_package_id: "WP06"
title: "Planning-action feature_dir primary anchor (#5160 friction 3)"
task_type: "implement"
execution_mode: "code_change"
phase: "Phase 1 - Remediation"
dependencies: []
owned_files:
  - "src/mission_runtime/resolution.py"
  - "tests/mission_runtime/test_resolve_action_context_feature_dir.py"
authoritative_surface: "src/mission_runtime/resolution.py"
create_intent:
  - "tests/mission_runtime/test_resolve_action_context_feature_dir.py"
subtasks:
  - "T019"
  - "T020"
  - "T021"
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

# Work Package Prompt: WP06 – Planning-action feature_dir primary anchor (#5160 friction 3)

## Objectives & Success Criteria

Make `context resolve --action tasks` agree with `check-prerequisites` on the primary feature_dir for planning actions; keep the coord surface for status actions.

**Requirement Refs**: FR-009

## Context & Constraints

- Mission spec: `kitty-specs/tooling-friction-fresh-env-remediation-01M3GN66/spec.md`
- Plan + concern map: `kitty-specs/tooling-friction-fresh-env-remediation-01M3GN66/plan.md`
- Manifest: `kitty-specs/tooling-friction-fresh-env-remediation-01M3GN66/tasks.md`
- Charter: `.kittify/charter/charter.md` (single canonical authority; canonical sources only; no test skip/disable to green).

## Branch Strategy

- **Planning base branch**: claude/tooling-friction-investigation-gpb1yl
- **Merge target branch**: claude/tooling-friction-investigation-gpb1yl

## Implementation Guidance

Route planning-action feature_dir through the primary anchor (_primary_anchored_feature_dir / primary_feature_dir_for_mission) in resolve_action_context/_resolve_mission_slug; coord fallback only when no primary dir exists. Red-first surface-disagreement test on a coord mission; regression that status/analyze/accept still resolve coord.

## Test Strategy

- Red-first regression proving the bug, then green after the fix (no-op passable: no).
- Run the owning module's tests plus blast radius; cross-cutting changes additionally run `tests/architectural/`.
- Lint/type: `ruff check .`, `ruff format --check .`, and mypy on changed files — zero issues.

## Risks & Mitigations

- Honor the constraints in spec.md (C-001..C-004). Keep new/edited functions <=15 complexity (NFR-004).

## Activity Log

- 2026-09-27T05:30:00Z – system – Prompt created.
