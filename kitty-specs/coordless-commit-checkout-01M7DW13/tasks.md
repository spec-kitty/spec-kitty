# Work Packages: Coordination-less status commits take their checkout from the placement seam

**Inputs**: `kitty-specs/coordless-commit-checkout-01M7DW13/` (spec.md, plan.md, research.md)
**Grounding**: `docs/plans/engineering-notes/2026-11-14-7633-7637-7648-coordless-commit-checkout.md`

**Tests**: required. Every fix is red-first through its pre-existing entry point (C-004); the red tests were reproduced on `d7cedd7e` during grounding.

**Organization**: two work packages, split by owned file so they never overlap. WP01 owns `coordination/transaction.py` (both #7648 and #7633 live there); WP02 owns the CLI commit callers (`workflow_executor.py`, `workflow.py`).

## Subtask Format: `[Txxx] [P?] Description`

Subtasks are reference rows; record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

---

## Work Package WP01: Bookkeeping transaction takes its checkout from the seam and treats an unchanged tree as a no-op (Priority: P1)

**Goal**: `commit_idempotent` returns the no-op receipt on `SafeCommitStagedTreeUnchanged` (#7648); the coordination-less and PRIMARY arms of `BookkeepingTransaction.acquire` take their checkout from the placement seam and the coordination-less arm refuses with `STATUS_WRITE_CHECKOUT_NOT_ON_WRITE_BRANCH` when that checkout is not on the write branch (#7633).
**Independent Test**: `tests/coordination/test_coordless_status_commit_checkout.py` (11 rows) and the two `commit_idempotent` tests in `tests/specify_cli/coordination/test_transaction.py`.
**Prompt**: `tasks/WP01-transaction-seam-checkout-and-idempotent-noop.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-005, FR-007, NFR-001, NFR-002, NFR-003, C-001, C-002, C-003, C-004

### Included Subtasks

T001 Commit the red #7648 tests (no-op on an unreadable pending check; strict-commit control) (WP01)
T002 `commit_idempotent` returns the no-op receipt on `SafeCommitStagedTreeUnchanged`, strict `commit()` unchanged (WP01)
T003 Commit the red #7633 characterization matrix (11 rows) and the error-code constant (WP01)
T004 Route the coordination-less arm through the seam and add the up-front hold check (WP01)
T005 Route `_primary_partition_holder` through the seam; delete `_write_branch_holder` (WP01)
T006 [P] Docstring `git/commit_helpers.py:213`, gate allowlist entry #2453 -> #1878, changelog fragments (WP01)
T007 Run the transaction blast radius and classify every red (WP01)

### Dependencies

- None.

### Risks & Mitigations

- Existing transaction tests may build Missions whose root checkout is not on the destination ref; classify each (stale shape vs regression) and surface any expectation edit to the operator.

---

## Work Package WP02: Claim and legacy follow-up commits never fail on unchanged content (Priority: P1)

**Goal**: the review claim commits only its status pair, so a `lanes_with_coord` claim on protected `main` exits 0 (#7637); the legacy commit leaf's pre-check runs in the checkout the commit runs in (the `_resolve_legacy_porcelain_root` residual).
**Independent Test**: `tests/integration/review/test_review_range_acceptance_action.py` with the `lanes_with_coord` protection lift removed; `tests/specify_cli/cli/commands/agent/test_coord_commit_integrity_e2e.py`.
**Prompt**: `tasks/WP02-claim-and-legacy-followup-commits.md`
**Requirement Refs**: FR-004, FR-006, C-004

### Included Subtasks

T008 Commit the red #7637 test change (drop the `lanes_with_coord` protection lift in `_review_args`) (WP02)
T009 `review_claim_transition` commits `claim_status_pair_paths(...)` only (WP02)
T010 Replace the T004 helper tests with legacy-leaf behaviour tests (red first) (WP02)
T011 Legacy pre-check runs in `repo_root` and answers only for paths inside it; delete `_resolve_legacy_porcelain_root` (WP02)
T012 Changelog fragment and the WP02 blast radius (WP02)

### Dependencies

- None (independent of WP01; disjoint owned files).

### Risks & Mitigations

- The deleted helper is pinned by three tests; their replacement is an asserted-expectation edit raised to the operator.
