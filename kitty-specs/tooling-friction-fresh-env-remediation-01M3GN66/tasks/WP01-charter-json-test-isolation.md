---
work_package_id: "WP01"
title: "Charter JSON contract test isolation (#4873)"
task_type: "implement"
execution_mode: "code_change"
phase: "Phase 1 - Remediation"
dependencies: []
owned_files:
  - "tests/cli/commands/test_charter_json_error_contract.py"
authoritative_surface: "tests/cli/commands/"
create_intent: []
subtasks:
  - "T001"
  - "T002"
  - "T003"
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

# Work Package Prompt: WP01 – Charter JSON contract test isolation (#4873)

## Objectives & Success Criteria

Make the three charter JSON error-contract tests assert their intended contracts from any cwd (incl. an isolated linked worktree), by adding the canonical autouse `_isolate_cwd_from_worktree_guard` fixture. No production change (C-001 preserves the #4785 guard-before-find_repo_root invariant).

**Requirement Refs**: FR-001, C-001

## Context & Constraints

- Mission spec: `kitty-specs/tooling-friction-fresh-env-remediation-01M3GN66/spec.md`
- Plan + concern map: `kitty-specs/tooling-friction-fresh-env-remediation-01M3GN66/plan.md`
- Manifest: `kitty-specs/tooling-friction-fresh-env-remediation-01M3GN66/tasks.md`
- Charter: `.kittify/charter/charter.md` (single canonical authority; canonical sources only; no test skip/disable to green).

## Branch Strategy

- **Planning base branch**: claude/tooling-friction-investigation-gpb1yl
- **Merge target branch**: claude/tooling-friction-investigation-gpb1yl

## Implementation Guidance

Mirror `tests/specify_cli/cli/commands/test_charter_resynthesize.py:21-35`. Reproduce red from a `git worktree add` linked worktree first; verify green from both a linked worktree and a root checkout; confirm no production file changed.

## Test Strategy

- Red-first regression proving the bug, then green after the fix (no-op passable: no).
- Run the owning module's tests plus blast radius; cross-cutting changes additionally run `tests/architectural/`.
- Lint/type: `ruff check .`, `ruff format --check .`, and mypy on changed files — zero issues.

## Risks & Mitigations

- Honor the constraints in spec.md (C-001..C-004). Keep new/edited functions <=15 complexity (NFR-004).

## Activity Log

- 2026-09-27T05:30:00Z – system – Prompt created.
