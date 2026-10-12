---
work_package_id: WP01
title: Post-landing requested-paths guard in safe_commit
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
planning_base_branch: issue-5903-safe-commit-hook-staged-paths
merge_target_branch: issue-5903-safe-commit-hook-staged-paths
branch_strategy: Planning artifacts for this mission were generated on issue-5903-safe-commit-hook-staged-paths. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5903-safe-commit-hook-staged-paths unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Fix
history:
- timestamp: '2026-10-12T18:00:00Z'
  agent: planner-priti
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/specify_cli/
create_intent: []
execution_mode: code_change
owned_files:
- src/specify_cli/git/commit_helpers.py
- src/specify_cli/core/upstream_contract.json
- src/specify_cli/orchestrator_api/envelope.py
- docs/contracts/upstream-3.0.0-shape.json
- docs/changelog/CHANGELOG.md
- tests/specify_cli/git/test_commit_helpers.py
- tests/specify_cli/orchestrator_api/test_contract_version.py
tags: []
tracker_refs: []
---

# Work Package Prompt: WP01 – Post-landing requested-paths guard in `safe_commit`

## Objective

Close #5903: `safe_commit` must never silently commit paths the operation did not request when a
pre-commit hook stages files (`git add -u`). Cover the `--only` route and the FR-022 temp-index
route with one shared post-landing check; leave the expected-parent route (negative control) and a
clean no-hook commit unchanged.

## Red-first (already committed)

`tests/specify_cli/git/test_commit_helpers.py` carries the failing reproduction
(`test_only_route_refuses_paths_a_hook_staged`, `test_index_deletions_route_refuses_paths_a_hook_staged`)
and the GREEN controls. Witnessed RED on origin/main behaviour before this WP.

## Subtasks

- **T001 [FR-001, FR-006]** Add `SafeCommitUnrequestedPaths(SafeCommitRecoveryFailed)` in
  `src/specify_cli/git/commit_helpers.py`, `error_code = "SAFE_COMMIT_UNREQUESTED_PATHS"`, carrying
  `commit_sha` and the extra paths (mirror `SafeCommitIndexResidue`).
- **T002 [FR-001, FR-002, FR-003, NFR-001]** Add `_assert_committed_paths_requested(worktree_root,
  destination_ref, sha, requested)`: `git diff-tree --no-commit-id --name-only -r <sha>` vs the
  requested set; if extra paths exist, `git reset -q HEAD -- <extra>` to re-sync the real index,
  then raise `SafeCommitUnrequestedPaths`. No index mutation and no raise when there are no extras.
- **T003 [FR-001, FR-002]** Call the helper from the `--only` success path in `safe_commit` and from
  `_commit_with_index_deletions` after `_sync_real_index_after_commit`, passing `normalized_files`
  (`--only`) or `requested ∪ deletions` (FR-022) as the requested set.
- **T004 [FR-004, C-002, NFR-002]** Do not touch the expected-parent route; do not pass
  `--no-verify`. Prove the clean path is unchanged with the no-hook controls.
- **T005 [FR-005, C-001]** Register `SAFE_COMMIT_UNREQUESTED_PATHS` in
  `src/specify_cli/core/upstream_contract.json` and the JSON-equal mirror
  `docs/contracts/upstream-3.0.0-shape.json`; bump `CONTRACT_VERSION` 1.14.0→1.15.0 with a changelog
  comment line in `src/specify_cli/orchestrator_api/envelope.py`; update
  `tests/specify_cli/orchestrator_api/test_contract_version.py`.
- **T006 [FR-006]** Add a focused test asserting the raised error satisfies the shared caller
  predicate `isinstance(exc, SafeCommitRecoveryFailed) and exc.commit_sha is not None`.

## Validation (targeted surface)

- `.venv/bin/python -m pytest tests/specify_cli/git/test_commit_helpers.py -p no:xdist`
- `.venv/bin/python -m pytest tests/contract/test_orchestrator_api.py tests/specify_cli/core/test_contract_gate.py tests/specify_cli/orchestrator_api/test_contract_version.py`
- `.venv/bin/python -m pytest tests/git_ops tests/specify_cli/git_commit_scope`
- `make test-fast`
- `ruff check .`, `make format-check-files FILES=<changed>`, `mypy` on changed files; complexity ≤ 15.

## Done when

The two reproduction tests pass, the controls still pass, the contract-parity and contract-version
gates pass, the operator's index is consistent after the call, and no caller misreports the new
outcome as failure-to-land.
