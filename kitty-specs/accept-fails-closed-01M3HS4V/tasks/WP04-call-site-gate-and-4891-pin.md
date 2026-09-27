---
work_package_id: WP04
title: 'Call-site gate and #4891 CLI pin'
dependencies:
- WP02
requirement_refs:
- FR-006
- FR-008
planning_base_branch: claude/project-thread-zj01ct
merge_target_branch: claude/project-thread-zj01ct
branch_strategy: Planning artifacts for this mission were generated on claude/project-thread-zj01ct. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/project-thread-zj01ct unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-accept-fails-closed-01M3HS4V
base_commit: 8b07d554784a27d76aa2319b829a5339baf20004
created_at: '2026-09-27T18:45:52.395274+00:00'
subtasks:
- T014
- T015
phase: Phase 1 - Implementation
history:
- at: '2026-09-27T16:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/architectural/
create_intent:
- tests/architectural/test_acceptance_matrix_write_seam.py
- tests/specify_cli/cli/commands/test_issue_4891_accept_missing_lanes.py
execution_mode: code_change
model: sonnet
owned_files:
- tests/architectural/test_acceptance_matrix_write_seam.py
- tests/specify_cli/cli/commands/test_issue_4891_accept_missing_lanes.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP04 – Call-site gate and #4891 CLI pin

## Do This First: Load Agent Profile

Load `packs/built-in/agent_profiles/python-pedro.agent.yaml` and follow it.

Mission: `accept-fails-closed-01M3HS4V`. Read `../spec.md`, `../plan.md`, `../research.md`.

## Objectives & Success Criteria

- `tests/architectural/test_acceptance_matrix_write_seam.py`: AST-scan every `.py` under `src/` for calls to `write_acceptance_matrix` or `write_and_commit_acceptance_matrix` in Name form, Attribute form (`matrix.write_acceptance_matrix(...)`) and via import aliases (`from ... import write_acceptance_matrix as w`). Allowed callers are a shrink-only per-FUNCTION allowlist keyed `path::qualname` with a one-line rationale each: the seam itself, `scaffold_acceptance_matrix` (and any commit wrapper it uses) — "create-if-absent at finalize", `verify_deferred_invariants` — "no production caller; post-consolidation seam routing deferred (C-005)", plus whatever else the scan finds that is genuinely a blind creator (justify each). Stale allowlist entries fail (shrink-only). Non-vacuity: a concrete-floor assertion that the scan found the seam's own call, and a self-mutation test that plants an aliased call and an attribute call in a tmp source tree and asserts both are caught (FR-006, SC-002). Copy the census style of `tests/architectural/test_guard_capability_call_sites.py`.
- `tests/specify_cli/cli/commands/test_issue_4891_accept_missing_lanes.py` (`@pytest.mark.regression`, ratchet): through the real `spec-kitty accept` CLI, a mission without `lanes.json` exits non-zero, no `accepted_at`, JSON names the blocked `lanes_manifest` check; positive control on the same fixture with `lanes.json` and a passing matrix accepts (FR-008).

## Validation

```bash
PWHEADLESS=1 .venv/bin/python -m pytest tests/architectural/test_acceptance_matrix_write_seam.py tests/specify_cli/cli/commands/test_issue_4891_accept_missing_lanes.py -q
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

- Allowlist entries by name: `src/specify_cli/acceptance/matrix.py::write_and_commit_acceptance_matrix` (wraps the raw writer), `::scaffold_acceptance_matrix`, the new seam function, and `src/specify_cli/acceptance/post_consolidation.py::verify_deferred_invariants`. Anything else the scan finds is a finding to report, not to silently allowlist.
- Add a second census in the same file: production callers of `record_acceptance` are exactly the guarded sites (`acceptance/__init__.py` `_commit_acceptance_meta` and `orchestrator_api/commands.py` `accept_mission`), each inside `locked_acceptance_verdict_guard`.
