---
work_package_id: WP03
title: Contract integration and API-only acceptance
dependencies:
- WP01
- WP02
requirement_refs:
- FR-001
- FR-004
- FR-006
- FR-007
- NFR-003
- C-001
- C-002
- C-003
- SC-001
- SC-002
- SC-003
planning_base_branch: issue-5846-orchestrator-two
merge_target_branch: issue-5846-orchestrator-two
branch_strategy: Planning artifacts for this mission were generated on issue-5846-orchestrator-two.
  During /spec-kitty.implement this WP may branch from a dependency-specific base,
  but completed changes must merge back into issue-5846-orchestrator-two unless the
  human explicitly redirects the landing branch.
subtasks:
- T003
history: []
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/
create_intent:
- tests/specify_cli/orchestrator_api/test_planning_client_journey.py
execution_mode: code_change
owned_files:
- src/specify_cli/orchestrator_api/commands.py
- src/specify_cli/orchestrator_api/envelope.py
- src/specify_cli/core/upstream_contract.json
- docs/api/orchestrator-api.md
- docs/adr/4.x/**
- tests/specify_cli/orchestrator_api/test_planning_client_journey.py
- tests/contract/test_orchestrator_api.py
- tests/docs/test_orchestrator_api_verb_doc_presence.py
- src/specify_cli/orchestrator_api/runtime_next.py
- tests/specify_cli/orchestrator_api/test_runtime_next.py
- tests/specify_cli/orchestrator_api/test_contract_version.py
- tests/specify_cli/orchestrator_api/test_resolve_mission_dir_or_fail_invariant.py
- docs/changelog/CHANGELOG.md
- docs/api/cli-commands.md
- docs/development/docs-retrieval-index.yaml
- docs/development/page-inventory.yaml
- docs/api/agent-subcommands.md
- src/runtime/next/runtime_bridge_query.py
tags: []
task_type: implementation
tracker_refs: []
---

# WP03: Contract integration and API-only acceptance

## ⚡ Do This First: Load Agent Profile

Run `spec-kitty agent profile show implementer-ivan` and `spec-kitty charter context --action implement --json`. Apply the resolved initialization and boundaries.

## Objective

Register new concern-module commands, update upstream contract census/envelope version compatibly, publish Python semantic delivery profile and Go mappings, no false Go conformance. Write red-first black-box journey tests before registry changes; fixture init precedes first API, thereafter all content/commit via API. Cover single_branch and coordination topology, invalid/stale/decision cases and ready work. Run existing targeted API/contracts/doc census plus directly affected services, ruff/mypy; independent reviewer checks aggregate before ready-for-squad. Publish PR to main and request Stijn/Nik without merging.

## Implementation Command

`spec-kitty agent action implement WP03 --mission orchestrator-two-planning-01M4AB7R --agent codex`

## Definition of Done

Real acceptance starts red in a separate test commit, then turns green; all owned production branches have meaningful validation. Preserve existing application authorities and user scope. New branch complexity at most15; no broad suppressions. Record targeted commands/counts, do not run whole-repo/heavy suites. Reviewer is distinct from implementer. No merge or main push.

## Validation

Run owned API test files and directly implicated canonical service tests; existing API module fast tier and contract census at integration. Ruff on touched files, strict mypy as configured. Never full tests/architectural, e2e, performance or make test-full.

## Activity Log

- 2026-10-07: Created under mission #5846; see spec and plan for complete acceptance, interface and authority laws.


Integration scope clarification: WP03 owns additive contract census/version updates, generated CLI references, changelog and index entries, and the public next query mission-guard correction. Approved dependency lane heads remain immutable.

Completion-fact correction: expose a narrow read-only native issued-step fact from the existing query, run-index and snapshot authorities; pending design inputs remain unissued. No second cursor or runtime mutation.
