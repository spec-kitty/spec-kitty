---
description: "Work package task list for mission safe-commit-hook-staged-paths"
---

# Work Packages: Guard `safe_commit` against hook-staged paths

**Inputs**: Design documents from `/kitty-specs/safe-commit-hook-staged-paths-01M4RKV7/`
**Prerequisites**: plan.md (required), spec.md (user stories), research/defect-diagnosis-5903.md

**Tests**: The red reproduction tests are already committed (ATDD red-first). This WP turns them
green and adds the FR-004 positive controls and the FR-006 shared-predicate assertion.

**Organization**: One independently-deliverable work package; it is the whole fix.

## Subtask Format: `[Txxx] [P?] Description`

- Subtasks are reference rows; completion is recorded in the event log.

## Path Conventions

- Single project: `src/specify_cli/`, `tests/`.

---

## Work Package WP01: Post-landing requested-paths guard in `safe_commit` (Priority: P0)

**Goal**: Stop `safe_commit` from silently committing paths a pre-commit hook staged, on both
affected routes, and report an already-landed mismatch the "landed, but" way while leaving the
operator's real index consistent — then register the new contract-visible error code.
**Independent Test**: The two reproduction tests
(`test_only_route_refuses_paths_a_hook_staged`, `test_index_deletions_route_refuses_paths_a_hook_staged`)
go RED→GREEN; the expected-parent and no-hook controls stay GREEN; the contract-parity and
contract-version gates pass.
**Prompt**: `/tasks/WP01-post-landing-requested-paths-guard.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, NFR-001, NFR-002, NFR-003, C-001, C-002, C-003

### Included Subtasks

T001 Add `SafeCommitUnrequestedPaths(SafeCommitRecoveryFailed)` with `error_code = "SAFE_COMMIT_UNREQUESTED_PATHS"`, carrying `commit_sha` + the extra paths (`src/specify_cli/git/commit_helpers.py`). [FR-001, FR-006]
T002 Add the shared `_assert_committed_paths_requested(...)` helper: `git diff-tree --name-only` of the new commit vs the requested set; on mismatch re-sync the real index for the extra paths and raise. [FR-001, FR-002, FR-003, NFR-001]
T003 Wire the helper into the `--only` success path and into `_commit_with_index_deletions` (after `_sync_real_index_after_commit`), passing `requested ∪ index_deletions` on the FR-022 route. [FR-001, FR-002]
T004 Leave the expected-parent route and a clean no-hook commit unchanged; prove via the controls. [FR-004, C-002, NFR-002]
T005 Register `SAFE_COMMIT_UNREQUESTED_PATHS` in `src/specify_cli/core/upstream_contract.json` and the JSON-equal mirror `docs/contracts/upstream-3.0.0-shape.json`; bump `CONTRACT_VERSION` 1.14.0→1.15.0 with a changelog-comment line in `orchestrator_api/envelope.py`; update the pinning test. [FR-005, C-001]
T006 Confirm no caller misreports the new outcome as failure-to-land (shared `SafeCommitRecoveryFailed` + `commit_sha` predicate); assert it in a focused test. [FR-006]

### Implementation Notes

- The helper is extracted so both `safe_commit` (`--only`) and `_commit_with_index_deletions` stay
  under the complexity ceiling (≤ 15).
- Index re-sync reuses the `git reset -q HEAD -- <paths>` pattern from `_sync_real_index_after_commit`.

### Dependencies

- None (single WP).

### Risks & Mitigations

- Risk: the check fires on a legitimate subset commit. Mitigation: only paths NOT in the requested
  set are "extra"; a subset (partial no-op) never triggers it — covered by the no-hook controls.
- Risk: contract/mirror drift. Mitigation: the JSON-equality gate and the parity gate are run by name.
