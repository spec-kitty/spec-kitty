# Contract: Reconciliation Gate Behavior

Executable contract for the four facets. Each row is a real-CLI scenario a red-first repro pins.

## Squash strategy (`verify_reachability=False`) — content axis

| # | Scenario | Before (bug) | After (contract) | Facet |
|---|----------|--------------|------------------|-------|
| S1 | Canceled WP deletes a pre-existing product file no approved lane re-authors; carrier-lane squash | PASS (exit 0) — file silently removed from target | **FAIL** + CAS-revert; divergence names the unattributable deletion | #5022 |
| S2 | Approved lane's first-parent spine deletes path P; squash | (deletion skipped) PASS | **PASS** — P ∈ `authored_deletions` | #5022 |
| S3 | Deletion of a mission-bookkeeping path under anchored prefixes | PASS | **PASS** — bookkeeping, not content | #5022 |
| S4 | Add/modify path with no approved authorship | FAIL | **FAIL** (unchanged) | #5013 (regression guard) |

## Merge / rebase strategy (`verify_reachability=True`) — excluded axis

| # | Scenario | Before (bug) | After (contract) | Facet |
|---|----------|--------------|------------------|-------|
| M1 | Mixed write-scope lane (approved survivor + canceled sibling); survivor's first-parent commits landed | FAIL (survivor commits marked reachable-excluded) + revert + exit 1 | **PASS** — survivor commits attributed as authored, not excluded | #5018 |
| M2 | Canceled code smuggled via a carrier merge's 2nd parent, reachable from target | FAIL | **FAIL** (unchanged — not on any approved first-parent spine) | #5018 / #4977 |
| M3 | Cherry-picked / re-lettered canceled copy | FAIL (patch-id) | **FAIL** (unchanged) | #5018 |
| M4 | Fully-canceled lane (no approved WP) | FAIL if reachable | **FAIL** (unchanged) | #5018 |

## Resume path

| # | Scenario | Before (bug) | After (contract) | Facet |
|---|----------|--------------|------------------|-------|
| R1 | Squash merge interrupted AFTER target advanced + reconciliation PASSed, DURING coord teardown; `merge --resume` | FAIL (content axis re-run vs partial/post-teardown claim) → revert | **completes teardown, exit 0** | #5021 r1 |
| R2 | Genuinely incomplete merge (target not advanced) on `--resume` | full gate | **full gate** (no tolerance leak) | #5021 r1 (guard) |

## Squash bookkeeping-projection proof

| # | Scenario | Before (bug) | After (contract) | Facet |
|---|----------|--------------|------------------|-------|
| P1 | Clean single-approved-lane squash; a coord-partition bookkeeping path the target legitimately does not carry | REFUSE ("projected coordination bookkeeping content did not land"); `--resume` dead-ends on `TARGET_BRANCH_CONTENT_CONFLICT` | **Deferred → #5038** — ships as `xfail(strict=True)`, NOT green-washed. The clean-single-lane trigger did not reproduce (WP02 T009); the only reproducer is the 3-way coord-partition divergence, which converges with X1. FR-007 recorded Deferred → #5038. | #5038 |
| P2 | Approved content path genuinely failed to land on target | REFUSE | **REFUSE** (unchanged — divergence detection preserved) | #5038 (guard) |

## Out of scope — kept honest

| # | Scenario | Status | Facet |
|---|----------|--------|-------|
| X1 | 3-way merge-resolution: target blob equals neither parent | remains `xfail(strict=True)` — documented tracked follow-up, NOT green-washed | #5021 r2 |

## Universal invariants (all rows)

- The gate never weakens toward a false-PASS to unblock a false-FAIL (C-001).
- Every fix pairs a "legitimate case now PASSes" test with an "unsafe case still FAILs/REFUSEs" adversarial test.
- Every repro drives the REAL `spec-kitty merge` CLI (no `_run_git`/subprocess mocking) and is issue-pinned + RED-first.
