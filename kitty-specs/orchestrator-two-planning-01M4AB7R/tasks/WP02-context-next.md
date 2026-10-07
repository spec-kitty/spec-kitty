---
work_package_id: WP02
title: Governed context interviews and native next
dependencies: []
requirement_refs:
- FR-002
- FR-005
- FR-006
- FR-007
planning_base_branch: issue-5846-orchestrator-two
merge_target_branch: issue-5846-orchestrator-two
branch_strategy: Planning artifacts for this mission were generated on issue-5846-orchestrator-two.
  During /spec-kitty.implement this WP may branch from a dependency-specific base,
  but completed changes must merge back into issue-5846-orchestrator-two unless the
  human explicitly redirects the landing branch.
base_branch: kitty/mission-orchestrator-two-planning-01M4AB7R
base_commit: 637fb2c028ccbb51f743600baadf2dc0308906da
created_at: '2026-10-07T04:59:15.862099+00:00'
subtasks:
- T002
history: []
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/
create_intent:
- src/specify_cli/orchestrator_api/design_context.py
- src/specify_cli/orchestrator_api/runtime_next.py
- tests/specify_cli/orchestrator_api/test_design_context.py
- tests/specify_cli/orchestrator_api/test_runtime_next.py
- src/specify_cli/design/context.py
execution_mode: code_change
owned_files:
- src/specify_cli/orchestrator_api/design_context.py
- src/specify_cli/orchestrator_api/runtime_next.py
- tests/specify_cli/orchestrator_api/test_design_context.py
- tests/specify_cli/orchestrator_api/test_runtime_next.py
- src/specify_cli/design/context.py
- src/specify_cli/missions/plan/interview_questions.py
- src/specify_cli/cli/commands/lifecycle.py
tags: []
task_type: implementation
tracker_refs: []
---

# WP02: Governed context interviews and native next

## ⚡ Do This First: Load Agent Profile

Run `spec-kitty agent profile show implementer-ivan` and `spec-kitty charter context --action implement --json`. Apply the resolved initialization and boundaries.

## Objective

Implement bounded read-only planning context/template/mission-type discovery and canonical interview recording using existing decision authority (resolved/nonempty required, terminal deferred/canceled is incomplete). Native next query/advance adapter must invoke existing next application in process with explicit args, preserve query read-only and lifecycle pairing. Return prompt content so client needs no filesystem access. Robust multiline JSON parse. Policy metadata required for mutations. Add red-first tests before implementation. Coordinate interfaces with WP01; no registry edits (WP03 owns).

## Implementation Command

`spec-kitty agent action implement WP02 --mission orchestrator-two-planning-01M4AB7R --agent codex`

## Definition of Done

Real acceptance starts red in a separate test commit, then turns green; all owned production branches have meaningful validation. Preserve existing application authorities and user scope. New branch complexity at most15; no broad suppressions. Record targeted commands/counts, do not run whole-repo/heavy suites. Reviewer is distinct from implementer. No merge or main push.

## Validation

Run owned API test files and directly implicated canonical service tests; existing API module fast tier and contract census at integration. Ruff on touched files, strict mypy as configured. Never full tests/architectural, e2e, performance or make test-full.

## Activity Log

- 2026-10-07: Created under mission #5846; see spec and plan for complete acceptance, interface and authority laws.
- 2026-10-07T05:25:41Z – codex-review – shell_pid=34985 – Scoped coverage evidence: 40 owned tests pass; design/context.py95%, orchestrator_api/design_context.py100%, runtime_next.py96%. Real API early research permits initial native discovery issuance; scaffold specify completion refuses, accepted substantive spec advances to plan. No production changes after reviewed f9d627b98.
