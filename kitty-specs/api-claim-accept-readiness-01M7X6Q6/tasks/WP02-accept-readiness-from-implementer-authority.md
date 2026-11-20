---
work_package_id: WP02
title: Accept readiness from the implementer authority
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-005
- FR-007
planning_base_branch: issue-5781-api-claim-accept-readiness
merge_target_branch: issue-5781-api-claim-accept-readiness
branch_strategy: Planning artifacts for this mission were generated on issue-5781-api-claim-accept-readiness. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5781-api-claim-accept-readiness unless the human explicitly redirects the landing branch.
subtasks:
- T008
- T009
- T010
- T011
- T012
- T013
- T014
- T015
- T007
phase: Phase 2 - Accept readiness
history:
- at: '2026-11-20T19:40:00Z'
  actor: claude::python-pedro
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/acceptance/
create_intent:
- tests/orchestrator_api/test_issue_5781_accept_readiness.py
- tests/specify_cli/acceptance/test_implementer_repair_hint.py
execution_mode: code_change
owned_files:
- src/specify_cli/acceptance/summary_core.py
- src/specify_cli/acceptance/__init__.py
- src/specify_cli/status/review_roles.py
- src/specify_cli/orchestrator_api/consolidation.py
- src/specify_cli/orchestrator_api/envelope.py
- src/charter/offering/skills/spec-kitty-orchestrator-api-operator/references/orchestrator-api-contract.md
- tests/utils.py
- tests/agent/test_orchestrator_commands_integration.py
- tests/specify_cli/test_acceptance_regressions.py
- tests/orchestrator_api/test_issue_4934_accept_mission_readiness.py
- tests/orchestrator_api/test_issue_5781_accept_readiness.py
- tests/specify_cli/acceptance/test_acceptance_cores.py
- tests/specify_cli/acceptance/test_implementer_repair_hint.py
- tests/acceptance/test_accept_gate_rejection_cycle.py
- tests/characterization/test_trio_pure_cores.py
- tests/unit/status/test_review_roles_7712.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# WP02 – Accept readiness from the implementer authority

Load the `python-pedro` profile first.

## Objective

The strict accept gate reads the implementer of record from `status/review_roles`, exempts a canceled WP with no implementer, and prints only a repair command that works. `accept-mission` decides terminality with the provenance-aware aggregate (#5818). See `../plan.md` IC-03 and `../research.md` D-01, D-02, D-03, D-06, D-09.

## Red first (separate commit, before any implementation)

- `tests/orchestrator_api/test_issue_5781_accept_readiness.py`, through the real `orchestrator-api` app and host `accept` on git fixtures:
  - an API-claimed WP01 (claim event with no `agent` sidecar, as older builds recorded it), reviewed and approved by an independent actor: `accept-mission` succeeds, on the plain lanes fixture and on a coordination-topology fixture;
  - cancel variants on WP02: host `move-task --to canceled --note` without `--agent`, the same with `--agent`, and `orchestrator-api transition --to canceled --note`. Host `accept` raises no metadata issue for WP02, and `accept-mission` succeeds;
  - a synthetic cancellation (forced, no note) is still in `incomplete_wps`.
- `tests/specify_cli/acceptance/test_implementer_repair_hint.py`: for each lane in the data-model table, build a WP with no implementing claim, and parse the hint. Where a command is printed, run it through the real CLI with `<name>` replaced and assert the issue clears. Where none is printed, assert the text names no `--to <lane>`.

## Implementation

1. `review_roles.implementer_claim_target(lane: str | Lane) -> Lane | None` (pure; added to `__all__`).
2. `acceptance/__init__._collect_snapshot_wps` also returns `{wp_id: latest_implementer_identity(transitions, wp_id)}` from the stream it already reads. `build_work_package_state(..., implementer=...)`: the gate issue fires only when `implementer is None` and the lane is not `canceled`. The hint comes from (1). The display `metadata["agent"]` is the slot, falling back to the implementer. Rewrite the false comment.
3. `accept_mission`: `ok, missing = mission_terminal_acceptability(snapshot.work_packages, expected_wp_ids=all_wp_ids)`. `incomplete_wps = missing`.
4. `tests/utils.py::_seed_canonical_wp_state`: for a target past `claimed` (not `planned`/`canceled`/`genesis`), seed a real `claimed` event by the actor first. Re-rule `test_never_claimed_wp_at_done_refuses_mission_not_ready_metadata`: a sidecar-less claim passes the metadata gate; a WP forced to `done` with no implementing event still refuses, with no command. Re-pin the hint strings in the three pinned tests.
5. `CONTRACT_VERSION = "1.30.0"`, with the comment block from `../contracts/orchestrator-api-1.30.0.md`; update the skill contract doc row.

## Validation

`make test-fast`; `pytest tests/orchestrator_api tests/acceptance tests/specify_cli/acceptance tests/status tests/characterization/test_trio_pure_cores.py`; every file `grep -rl "write_wp(" tests` lists; `tests/specify_cli/cli/commands -k accept`. ruff, `ruff format --check --force-exclude`, and mypy on the changed files.
