---
work_package_id: "WP03"
title: "Shared status.json re-materialization authority (NFR-002)"
task_type: "implement"
execution_mode: "code_change"
phase: "Phase 1 - Remediation"
dependencies: []
owned_files:
  - "src/specify_cli/merge/bookkeeping_projection.py"
  - "tests/specify_cli/merge/test_rematerialization_authority.py"
authoritative_surface: "src/specify_cli/merge/"
create_intent:
  - "tests/specify_cli/merge/test_rematerialization_authority.py"
subtasks:
  - "T007"
  - "T008"
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

# Work Package Prompt: WP03 – Shared status.json re-materialization authority (NFR-002)

## Objectives & Success Criteria

Provide ONE shared helper that regenerates status.json from a union-merged event log (reduce -> materialize_to_json), reused by lane allocation (WP04) and the squash seam (WP05). Also house the decisions/index.json re-fold helper here if WP05 re-derives it.

**Requirement Refs**: NFR-002

## Context & Constraints

- Mission spec: `kitty-specs/tooling-friction-fresh-env-remediation-01M3GN66/spec.md`
- Plan + concern map: `kitty-specs/tooling-friction-fresh-env-remediation-01M3GN66/plan.md`
- Manifest: `kitty-specs/tooling-friction-fresh-env-remediation-01M3GN66/tasks.md`
- Charter: `.kittify/charter/charter.md` (single canonical authority; canonical sources only; no test skip/disable to green).

## Branch Strategy

- **Planning base branch**: claude/tooling-friction-investigation-gpb1yl
- **Merge target branch**: claude/tooling-friction-investigation-gpb1yl

## Implementation Guidance

Extract/hoist from `_rematerialize_status_snapshot`, keeping the T012 AST-lint-sanctioned write shape. Unit-test the helper directly (union -> reduce -> snapshot equality). Single authority: no forked reduce/materialize logic.

## Test Strategy

- Red-first regression proving the bug, then green after the fix (no-op passable: no).
- Run the owning module's tests plus blast radius; cross-cutting changes additionally run `tests/architectural/`.
- Lint/type: `ruff check .`, `ruff format --check .`, and mypy on changed files — zero issues.

## Risks & Mitigations

- Honor the constraints in spec.md (C-001..C-004). Keep new/edited functions <=15 complexity (NFR-004).

## Activity Log

- 2026-09-27T05:30:00Z – system – Prompt created.
