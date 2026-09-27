---
work_package_id: "WP07"
title: "Coordination-materialization remedy text (#5113, remedy-only)"
task_type: "implement"
execution_mode: "code_change"
phase: "Phase 1 - Remediation"
dependencies: []
owned_files:
  - "src/specify_cli/coordination/surface_resolver.py"
  - "src/specify_cli/cli/commands/decision.py"
  - "tests/coordination/test_unmaterialized_remedy_text.py"
authoritative_surface: "src/specify_cli/coordination/surface_resolver.py"
create_intent:
  - "tests/coordination/test_unmaterialized_remedy_text.py"
subtasks:
  - "T022"
  - "T023"
  - "T024"
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

# Work Package Prompt: WP07 – Coordination-materialization remedy text (#5113, remedy-only)

## Objectives & Success Criteria

Correct the CoordinationWorktreeUnmaterialized remedy text to name a working `git worktree add` command; optionally add a defensive CLI except arm. Materialize-before-write is OUT OF SCOPE (deferred to #5108) per C-002.

**Requirement Refs**: FR-010, C-002

## Context & Constraints

- Mission spec: `kitty-specs/tooling-friction-fresh-env-remediation-01M3GN66/spec.md`
- Plan + concern map: `kitty-specs/tooling-friction-fresh-env-remediation-01M3GN66/plan.md`
- Manifest: `kitty-specs/tooling-friction-fresh-env-remediation-01M3GN66/tasks.md`
- Charter: `.kittify/charter/charter.md` (single canonical authority; canonical sources only; no test skip/disable to green).

## Branch Strategy

- **Planning base branch**: claude/tooling-friction-investigation-gpb1yl
- **Merge target branch**: claude/tooling-friction-investigation-gpb1yl

## Implementation Guidance

Compose `git -C <repo> worktree add <worktree> <coord_branch>` in CoordinationWorktreeUnmaterialized.__init__/next_step, mirroring the #2240 _coordination_doctor.py hint, via CoordinationWorkspace.worktree_path/branch_name. Do NOT touch CoordinationWorkspace.resolve.

## Test Strategy

- Red-first regression proving the bug, then green after the fix (no-op passable: no).
- Run the owning module's tests plus blast radius; cross-cutting changes additionally run `tests/architectural/`.
- Lint/type: `ruff check .`, `ruff format --check .`, and mypy on changed files — zero issues.

## Risks & Mitigations

- Honor the constraints in spec.md (C-001..C-004). Keep new/edited functions <=15 complexity (NFR-004).

## Activity Log

- 2026-09-27T05:30:00Z – system – Prompt created.
