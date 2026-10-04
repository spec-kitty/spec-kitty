---
work_package_id: WP03
title: Pure dry-run attestation notice (sequenced on PR 5650)
dependencies: []
requirement_refs:
- FR-008
planning_base_branch: issue-5552-friction-remediation
merge_target_branch: issue-5552-friction-remediation
branch_strategy: Planning artifacts for this mission were generated on issue-5552-friction-remediation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5552-friction-remediation unless the human explicitly redirects the landing branch.
subtasks:
- T011
- T012
- T013
phase: Phase 2 - Sequenced
history:
- at: '2026-10-04T12:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/canceled_attestation.py
create_intent: []
execution_mode: code_change
owned_files:
- src/specify_cli/consolidation/canceled_attestation.py
- src/specify_cli/cli/commands/consolidate.py
- tests/consolidation/test_canceled_attestation.py
- tests/terminus/test_mixed_lane_fail_recovery_and_attestation.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#5653'
---
# Work Package Prompt: WP03 – Pure dry-run attestation notice

## ⚡ Do This First: Load Agent Profile

Load the `python-pedro` profile and follow it.

## Gate (binding)

T011: run `git fetch origin main` and check whether PR #5650 is merged.
- If it is NOT merged: do not start. Cancel this WP with the rationale "deferred: waits on PR #5650 (rewrites consolidate())", and leave #5653 open (`Refs`).
- If it IS merged: merge origin/main into the branch first.

## Objective (tidy-first, behaviour-preserving)

- Extract `dry_run_attestation_notice(attested_wps, *, dry_run, json_output) -> str | None` into `consolidation/canceled_attestation.py`. Build the text from `ATTEST_FLAG`, byte-identical to today's output.
- The CLI calls the new function.
- Unit-test all four cases.
- Replace `_invoke_consolidate_dry_run` with unit tests plus at most one smoke test.
- Update the docstring at `tests/terminus/test_mixed_lane_fail_recovery_and_attestation.py:8-14`.
- Do not widen the C901 suppression.
- Run the dead-symbol gate and `tests/consolidation/test_single_rollback_authority.py`.
