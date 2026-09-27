---
work_package_id: "WP02"
title: "Dev-dependency packaging mirror (#5160 friction 2)"
task_type: "implement"
execution_mode: "code_change"
phase: "Phase 1 - Remediation"
dependencies: []
owned_files:
  - "pyproject.toml"
  - "uv.lock"
  - "tests/architectural/test_pyproject_shape.py"
authoritative_surface: "pyproject.toml"
create_intent: []
subtasks:
  - "T004"
  - "T005"
  - "T006"
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

# Work Package Prompt: WP02 – Dev-dependency packaging mirror (#5160 friction 2)

## Objectives & Success Criteria

Ensure a plain `uv sync`/`uv run --frozen` lane venv carries `pytestarch`; add a pyproject-shape guard that fails closed if a plugin needed without --all-extras is missing from [dependency-groups].dev.

**Requirement Refs**: FR-002

## Context & Constraints

- Mission spec: `kitty-specs/tooling-friction-fresh-env-remediation-01M3GN66/spec.md`
- Plan + concern map: `kitty-specs/tooling-friction-fresh-env-remediation-01M3GN66/plan.md`
- Manifest: `kitty-specs/tooling-friction-fresh-env-remediation-01M3GN66/tasks.md`
- Charter: `.kittify/charter/charter.md` (single canonical authority; canonical sources only; no test skip/disable to green).

## Branch Strategy

- **Planning base branch**: claude/tooling-friction-investigation-gpb1yl
- **Merge target branch**: claude/tooling-friction-investigation-gpb1yl

## Implementation Guidance

Add `pytestarch>=4.0.0` to [dependency-groups].dev mirroring the existing pytest-xdist/pytest-timeout entries (same pin as the `test` extra). Regenerate uv.lock via `uv lock`. Cross-cutting: run tests/architectural/ in full.

## Test Strategy

- Red-first regression proving the bug, then green after the fix (no-op passable: no).
- Run the owning module's tests plus blast radius; cross-cutting changes additionally run `tests/architectural/`.
- Lint/type: `ruff check .`, `ruff format --check .`, and mypy on changed files — zero issues.

## Risks & Mitigations

- Honor the constraints in spec.md (C-001..C-004). Keep new/edited functions <=15 complexity (NFR-004).

## Activity Log

- 2026-09-27T05:30:00Z – system – Prompt created.
