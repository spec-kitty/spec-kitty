---
work_package_id: WP01
title: Governed artifact authoring
dependencies: []
requirement_refs:
- FR-001
- FR-003
- FR-004
- NFR-001
- NFR-002
planning_base_branch: issue-5846-orchestrator-two
merge_target_branch: issue-5846-orchestrator-two
branch_strategy: Planning artifacts for this mission were generated on
  issue-5846-orchestrator-two. During /spec-kitty.implement this WP may branch
  from a dependency-specific base, but completed changes must merge back into
  issue-5846-orchestrator-two unless the human explicitly redirects the landing
  branch.
base_branch: kitty/mission-orchestrator-two-planning-01M4AB7R
base_commit: 637fb2c028ccbb51f743600baadf2dc0308906da
created_at: '2026-10-07T04:59:02.422993+00:00'
subtasks:
- T001
history: []
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/
create_intent:
- src/specify_cli/design/__init__.py
- src/specify_cli/design/authoring.py
- src/specify_cli/design/validation.py
- src/specify_cli/design/errors.py
- src/specify_cli/design/receipts.py
- src/specify_cli/design/models.py
- src/specify_cli/orchestrator_api/design_authoring.py
- tests/specify_cli/orchestrator_api/test_design_authoring.py
execution_mode: code_change
owned_files:
- src/specify_cli/design/__init__.py
- src/specify_cli/design/authoring.py
- src/specify_cli/design/validation.py
- src/specify_cli/design/errors.py
- src/specify_cli/design/receipts.py
- src/specify_cli/design/models.py
- src/specify_cli/orchestrator_api/design_authoring.py
- src/specify_cli/orchestrator_api/design_phase.py
- src/specify_cli/cli/commands/agent/mission_setup_plan.py
- tests/specify_cli/orchestrator_api/test_design_authoring.py
- tests/specify_cli/design/**
- src/specify_cli/status/design.py
- src/specify_cli/status/__init__.py
- src/specify_cli/orchestrator_api/design_status.py
tags: []
task_type: implementation
tracker_refs: []
---

# WP01: Governed artifact authoring

## ⚡ Do This First: Load Agent Profile

Run `spec-kitty agent profile show implementer-ivan` and `spec-kitty charter context --action implement --json`. Apply the resolved initialization and boundaries.

## Objective

Implement the shared design application authority and thin authoring API. Closed kinds: spec, plan, supporting design documents/contracts, wps manifest, WP prompt. Resolve canonical placement, validate all targets/parents/context and bounds before mutation, per-mission cooperative lock/recheck, host-selected paths, narrow writable allowlist, no finalized/executing WP edits. Use existing guards/finalizer/commit router, no invented runtime ledger. Use exact sha256/absent expectations. Pending design decisions and stale planning lineage block completion. Scaffold success distinct from phase completion. Add red-first real API acceptance/refusal tests in owned files before production code. No contract registry edits (WP03 owns), export functions for registration.

## Implementation Command

`spec-kitty agent action implement WP01 --mission orchestrator-two-planning-01M4AB7R --agent codex`

## Definition of Done

Real acceptance starts red in a separate test commit, then turns green; all owned production branches have meaningful validation. Preserve existing application authorities and user scope. New branch complexity at most15; no broad suppressions. Record targeted commands/counts, do not run whole-repo/heavy suites. Reviewer is distinct from implementer. No merge or main push.

## Validation

Run owned API test files and directly implicated canonical service tests; existing API module fast tier and contract census at integration. Ruff on touched files, strict mypy as configured. Never full tests/architectural, e2e, performance or make test-full.

## Activity Log

- 2026-10-07: Created under mission #5846; see spec and plan for complete acceptance, interface and authority laws.
