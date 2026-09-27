---
work_package_id: WP03
title: accept-mission applies the host readiness verdict
dependencies:
- WP02
requirement_refs:
- C-001
- C-002
- FR-007
- FR-009
planning_base_branch: claude/project-thread-zj01ct
merge_target_branch: claude/project-thread-zj01ct
branch_strategy: Planning artifacts for this mission were generated on claude/project-thread-zj01ct. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/project-thread-zj01ct unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-accept-fails-closed-01M3HS4V
base_commit: 8b07d554784a27d76aa2319b829a5339baf20004
created_at: '2026-09-27T18:45:23.544325+00:00'
subtasks:
- T010
- T011
- T012
- T013
phase: Phase 1 - Implementation
history:
- at: '2026-09-27T16:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/orchestrator_api/
create_intent:
- tests/orchestrator_api/test_issue_4934_accept_mission_readiness.py
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/orchestrator_api/commands.py
- src/specify_cli/orchestrator_api/envelope.py
- docs/api/orchestrator-api.md
- src/charter/offering/skills/spec-kitty-orchestrator-api-operator/SKILL.md
- src/charter/offering/skills/spec-kitty-orchestrator-api-operator/references/orchestrator-api-contract.md
- tests/orchestrator_api/test_issue_4934_accept_mission_readiness.py
- tests/agent/test_orchestrator_commands_integration.py
- tests/specify_cli/orchestrator_api/test_contract_version.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP03 – accept-mission applies the host readiness verdict

## Do This First: Load Agent Profile

Load `packs/built-in/agent_profiles/python-pedro.agent.yaml` and follow it.

Mission: `accept-fails-closed-01M3HS4V`. Read `../spec.md`, `../plan.md`, `../research.md`.

## Objectives & Success Criteria

- `accept_mission` (`orchestrator_api/commands.py` ~L2033): keep the existing incomplete-WP refusal (compat). After `collect_feature_summary(main_repo_root, mission, strict_metadata=True)` (pin explicitly), if `not summary.ok` → `_fail(cmd, "MISSION_NOT_READY", <message>, {**_mission_identity_payload(mission_dir), "outstanding": ..., "activity_issues": [...], "skipped_checks": [{check, detail}], "blocked_checks": [{check, detail}]})`. Check `AcceptanceSummary.outstanding()`'s return type and serialise it JSON-safely; keep `validate_outbound_payload` passing (FR-007, C-001, C-002).
- Record acceptance inside `locked_acceptance_verdict_guard(repo_root, summary.acceptance_matrix_dir)` (WP01/WP02); a guard refusal → `MISSION_NOT_READY`. Leave the payload `mode: "auto"` as is (deferred, C-005).
- `envelope.py`: `CONTRACT_VERSION` 1.6.0 → 1.7.0 with a ledger comment in the existing style; `MIN_PROVIDER_VERSION` unchanged; update `tests/specify_cli/orchestrator_api/test_contract_version.py` pins (FR-009). Fix the stale `1.5.0` in `docs/api/orchestrator-api.md` while there (campsite), document the new refusal cause + error data in the Acceptance section, `SKILL.md` accept-mission section and `references/orchestrator-api-contract.md` §8 (and remove/justify the `WORKFLOW_EVIDENCE_REQUIRED` line for accept-mission only if clearly unraised — else leave).
- Nothing recorded on refusal = no `accepted_at`, `acceptance_mode`, `acceptance_history` in `meta.json`; HEAD unchanged.

## Red-first tests (`tests/orchestrator_api/test_issue_4934_accept_mission_readiness.py`, `pytestmark = [pytest.mark.git_repo, pytest.mark.regression]`; copy conventions from `tests/orchestrator_api/test_issue_4889_caller_independence.py`)

- Shared acceptable fixture: real `git init` + commit, `write_single_lane_manifest` (`tests/lane_test_utils.py`), `spec.md`/`plan.md`, WPs approved via status events carrying an agent, path-convention dirs, matrix all-pass. Invoke the real CLI (`orchestrator-api accept-mission --mission --actor`).
- Pending matrix → `MISSION_NOT_READY`, nothing recorded. No `lanes.json` → same with blocked `lanes_manifest`. Acceptable fixture → success, `accepted_at` written. Late verdict between summary and stamp (wrap `record_acceptance` / guard entry) → refuse.
- Repair `test_all_done_accepted` / `test_all_approved_accepted` (`tests/agent/test_orchestrator_commands_integration.py` ~L1356/L1395) onto an acceptable fixture; do not weaken their assertions.

## Validation

```bash
PWHEADLESS=1 .venv/bin/python -m pytest tests/orchestrator_api/ tests/specify_cli/orchestrator_api/ tests/agent/test_orchestrator_commands_integration.py tests/contract/test_orchestrator_api.py tests/contract/test_machine_facing_canonical_fields.py tests/agent/test_json_envelope_contract_integration.py tests/specify_cli/core/test_contract_gate.py -q
PWHEADLESS=1 .venv/bin/python -m pytest tests/architectural/test_no_legacy_terminology.py -q
```

## Branch Strategy

- **Strategy**: single_branch
- **Planning base branch**: claude/project-thread-zj01ct
- **Merge target branch**: claude/project-thread-zj01ct

## Governance

- Load `.kittify/charter/charter.md` and `spec-kitty charter context --action implement --json`.
- ATDD / red-first: commit the issue-pinned `@pytest.mark.regression` test(s) first and show them RED against the pre-fix product code, then the fix.
- New code: ruff, `ruff format --check`, mypy clean; complexity ≤ 15; tests in the same commit as new branches/helpers. Terminology: Mission, never feature.
- Do NOT run `make test-full`, the whole `tests/architectural/` directory, or e2e/performance suites (`NO_FULL_HEAVY_SUITES_IN_MISSION`). Run the targeted files listed below plus the owning subsystem's fast tier.

## Post-tasks squad folds (binding)

- Call only WP01's guard; never `feature_status_lock` directly in `orchestrator_api/commands.py` (exact-set lock-composition census).
- Apply WP02's planning-artifact-only bypass rule identically; any other missing matrix dir fails closed.
- Map a guard `FeatureStatusLockTimeoutError` to `MISSION_NOT_READY` (no traceback).
- Serialise `skipped_checks` / `blocked_checks` with `AcceptanceCheckDiagnostic.to_dict()` (`gates_core.py` ~L62); `summary.outstanding()` returns `dict[str, list[str]]`.
- Also run `tests/doctrine/test_spk_skill_pack.py` (skill under `src/charter/offering/` edited).
