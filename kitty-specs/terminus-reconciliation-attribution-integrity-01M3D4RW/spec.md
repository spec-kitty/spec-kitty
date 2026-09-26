# Mission Specification: Terminus Reconciliation Attribution Integrity

**Mission Branch**: `fix/terminus-reconciliation-attribution-integrity`
**Created**: 2026-09-25
**Status**: Draft
**Input**: Epic #5001 follow-ups — #5022, #5018, #5021, #5038 (reconciliation-gate attribution / over-reach)

## Summary

`spec-kitty merge` runs a pre-teardown **reconciliation gate** that decides whether the tree the merge produced faithfully carries exactly the approved work and none of the canceled work. Four independent defects in that gate mean it currently either **destroys committed work while exiting 0** (a canceled work package's deletion rides onto the target under squash) or **refuses a legitimate merge of a supported topology** (a mixed approved+canceled lane, a completed-but-interrupted squash on resume, or a clean single-lane squash's bookkeeping-projection proof). This mission fixes the gate's **attribution granularity** so it neither ships unattributed content nor blocks valid merges — without weakening any fail-closed safety the gate provides.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A canceled work package's file deletion must never silently ship (Priority: P1) — #5022

The operator merges a mission (default `squash`) whose lane carries an approved survivor work package **and** a canceled sibling. The canceled sibling deleted a pre-existing product file that no approved lane re-authors. The whole lane is integrated by the executor, so the deletion is present in the squashed tree.

**Why this priority**: This is the only facet that fails in the **data-loss** direction — a file silently disappears from the target branch at exit 0. It is sequenced first.

**Independent Test**: A real-CLI mission where a canceled WP deletes a pre-existing file, integrated via a carrier lane, merged with the default squash strategy. The gate must **FAIL** and compare-and-swap-revert the target instead of shipping the deletion.

**Acceptance Scenarios**:

1. **Given** a squash merge whose window deletes a pre-existing path that no approved lane's first-parent history deletes, **When** the reconciliation gate runs, **Then** it FAILs (names the unattributable deletion) and the target is CAS-reverted to its pre-merge tip.
2. **Given** a squash merge that deletes a path an approved lane's first-parent spine also deletes (legitimate approved removal), **When** the gate runs, **Then** it PASSes.
3. **Given** a squash merge that deletes a mission-bookkeeping path under the anchored mission prefixes, **When** the gate runs, **Then** the deletion is treated as bookkeeping and does not FAIL.

### User Story 2 - A valid merge of a mixed approved+canceled write-scope lane must complete (Priority: P2) — #5018

The operator merges (strategy `merge` or `rebase`) a mission whose single write-scope lane holds both an approved/done WP and a canceled-with-provenance sibling. The executor integrates the survivor's commits. The gate must not block this.

**Why this priority**: Fail-closed (no data loss) availability regression — the operator cannot complete a legitimate merge of a supported topology without a workaround.

**Independent Test**: A real-CLI mixed write-scope lane merged under `--strategy merge`; the gate must PASS. Adversarially: a canceled-only lane, and canceled code smuggled via a carrier merge's second parent, must still be excluded.

**Acceptance Scenarios**:

1. **Given** a mixed lane whose survivor's first-parent commits legitimately landed on the target, **When** the gate runs under `merge`/`rebase`, **Then** those commits are attributed as approved authorship and are NOT reported as reachable-excluded, so the gate PASSes.
2. **Given** a canceled WP's commit that is NOT part of any approved lane's first-parent authorship (e.g. second-parent-smuggled) and IS reachable from the target, **When** the gate runs, **Then** it still FAILs (the #4977 safety net holds).
3. **Given** a fully-canceled lane (no approved WP), **When** the gate runs, **Then** all of its tip commits remain excluded.

### User Story 3 - A completed squash merge interrupted mid-teardown must resume cleanly (Priority: P2) — #5021 residual 1

The operator's squash merge advanced the target and PASSed reconciliation, then crashed during coordination teardown. `spec-kitty merge --resume` must recognise the completed-but-mid-teardown state and finish teardown — not re-run the content axis against a now-partial authorship claim and false-FAIL.

**Why this priority**: Fail-closed (target reverted to a consistent tip) but a false-refuse on the recovery path for work that already merged correctly.

**Independent Test**: A real-CLI squash merge interrupted after the reconciliation PASS, during coord teardown; `--resume` must complete without re-failing.

**Acceptance Scenarios**:

1. **Given** a persisted merge state whose target already advanced and whose reconciliation already PASSed, and whose coord teardown is partially done, **When** `merge --resume` runs, **Then** it completes teardown and exits 0 without re-running the content axis against a post-teardown-partial claim.
2. **Given** a genuinely incomplete merge (target not advanced / reconciliation not run), **When** `merge --resume` runs, **Then** it still runs the full gate (no tolerance leak that would skip verification of unfinished work).

### User Story 4 - A clean single-lane squash must not be refused by the bookkeeping-projection proof (Priority: P2) — #5038

The operator merges (default `squash`) a clean single-approved-lane mission whose deliverable integrated correctly. A coord-partition bookkeeping path (a verdict / notes / trace file) that the target legitimately does not carry must not cause `_assert_squash_projected_content_landed` to refuse, and `merge --resume` must not dead-end on `TARGET_BRANCH_CONTENT_CONFLICT`.

**Why this priority**: Fail-closed (nothing torn down) but a clean, correctly-merged mission cannot be completed.

**Independent Test**: A real-CLI clean single-approved-lane squash mission with a post-checkpoint coord-bookkeeping path; `spec-kitty merge` must PASS and `--resume` must complete.

**Acceptance Scenarios**:

1. **Given** a coord-partition bookkeeping path the target legitimately does not carry, **When** the squash projection proof runs, **Then** it does not refuse on that path alone.
2. **Given** an approved-content path that genuinely failed to land on the target, **When** the projection proof runs, **Then** it still refuses (the divergence-detection the proof exists for is preserved).
3. **Given** a completed-but-projection-mismatched state, **When** `merge --resume` runs, **Then** it does not dead-end on `TARGET_BRANCH_CONTENT_CONFLICT`.

### Edge Cases

- A path deleted then re-added within one approved lane (final first-parent state is present) must NOT count as an authored deletion.
- A rename observed under `--no-renames` (delete + add) must attribute each half correctly.
- A cherry-picked / re-lettered copy of canceled code (patch-id match) must still be excluded after the #5018 commit-level narrowing.
- The 3-way merge-resolution content case (a resolved blob equal to neither parent) is **out of scope** and remains a documented `xfail(strict)` (#5021 residual 2).

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Attribute squash deletions | The squash content axis attributes Deleted paths, not only Added/Modified: an unattributable deletion FAILs + CAS-reverts, matching the add/modify path (#5022). | High | Open |
| FR-002 | Authored-deletion authority | The approved-lane first-parent authorship set records paths whose FINAL first-parent state is deleted, so a legitimate approved deletion PASSes (#5022). | High | Open |
| FR-003 | Bookkeeping deletion tolerance | A deletion of a mission-bookkeeping path under the anchored prefixes is not treated as unattributable content (#5022). | High | Open |
| FR-004 | Commit-level exclusion | The excluded set subtracts the approved lanes' first-parent authored SHAs/patch-ids, so a mixed lane's survivor commits are not double-counted as excluded (#5018). | High | Open |
| FR-005 | Excluded safety preserved | Canceled code not part of any approved lane's first-parent authorship (e.g. second-parent-smuggled) remains excluded and still FAILs when reachable (#5018 / #4977). | High | Open |
| FR-006 | Resume tolerates completed-but-mid-teardown | `merge --resume` recognises a target-advanced + reconciliation-PASSed state whose teardown was interrupted and completes it without re-running the content axis against a partial claim (#5021 r1). | Medium | Open |
| FR-007 | Projection proof precision | The squash bookkeeping-projection proof distinguishes a coord-partition path the target legitimately does not carry from a genuine failed projection, and `--resume` does not dead-end on `TARGET_BRANCH_CONTENT_CONFLICT` for a completed clean merge (#5038). | Medium | Deferred → #5038 |
| FR-008 | 3-way case stays honest | The 3-way merge-resolution content case remains `xfail(strict)`; it is documented as a tracked Epic #5001 follow-up and is not green-washed (#5021 r2). | Medium | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No false-fail of legitimate merges | Each fix that removes an over-reach must be proven, by a real-CLI test, to PASS the legitimate case it unblocks while a sibling adversarial test proves the unsafe case still FAILs (0 regressions in `tests/terminus/` + `tests/merge/`). | Reliability | High | Open |
| NFR-002 | No unattributed content ships | For every fix, an adversarial data-loss test confirms unattributable content/deletions still FAIL + CAS-revert (the gate stays fail-closed in the data-loss direction). | Reliability | High | Open |
| NFR-003 | Bounded probes | New attribution work stays bounded by the squash/merge window (no O(repo history) scans); merge remains within the CLI < 2s typical-project budget. | Performance | Medium | Open |
| NFR-004 | Zero new lint/type debt | New code passes `ruff check`, `ruff format --check`, and `mypy --strict` with no new suppressions; any new branch/helper carries focused tests in the same commit; complexity ≤ 15. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Fix granularity, not strictness | Fixes correct attribution granularity; they must NEVER weaken a fail-closed gate into a false-PASS. A naive "approved wins over excluded" that reopens the #4977 data-loss class is prohibited. | Technical | High | Open |
| C-002 | Red-first ATDD | Each facet lands an issue-pinned `@pytest.mark.regression` real-CLI repro that is RED through the pre-existing `spec-kitty merge` entry point before the fix, GREEN after (ADR 2026-07-17-1, charter C-011). | Technical | High | Open |
| C-003 | Honest-red discipline | `xfail(strict)` repros are flipped to pass only by a real fix; a case not actually fixed stays an honest xfail (charter Standing Order #9). WP1's deletion work must not silently un-strict the 3-way xfail. | Technical | High | Open |
| C-004 | Disjoint-write-scope invariant | The squash blob/deletion attribution rests on lanes being sliced by disjoint write-scope; this assumption is preserved and must be revisited before it is relaxed (the 3-way case is its known boundary). | Technical | Medium | Open |
| C-005 | Blast radius | Edits are confined to `src/specify_cli/merge/` (`reconciliation.py`, `executor.py`, `bookkeeping_projection.py`) + their tests; no edits to `lanes/` (parallel-safety with Epic #4883 / #4857 `lanes/merge.py::_rev_parse`). | Technical | Medium | Open |

### Key Entities

- **Reconciliation gate** (`MergeOutcomeVerifier.verify`): decides PASS / FAIL(divergence) / REFUSE for the merged tree before teardown.
- **ApprovedWpCommitSet**: the claim the gate attributes against — approved SHAs, excluded SHAs/patch-ids, first-parent `authored_shas` / `authored_patch_ids` / `authored_blobs`, and (new, #5022) `authored_deletions`.
- **Squash content axis** (`_unattributable_content_squash`): attributes each window path's content/deletion against the approved authorship.
- **Bookkeeping-projection proof** (`_assert_squash_projected_content_landed` → `projected_content_matches_target`): proves coord-partition bookkeeping the projection carried actually landed.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A canceled WP's unattributable file deletion under squash is refused (FAIL + revert) in 100% of runs — 0 silent data-loss escapes (#5022).
- **SC-002**: A legitimate mixed approved+canceled write-scope lane merges successfully under `merge`/`rebase` with 0 false-FAILs, while second-parent-smuggled canceled code is still refused (#5018).
- **SC-003**: A completed squash merge interrupted mid-teardown resumes to exit 0 without re-failing; a genuinely incomplete merge still runs the full gate (#5021 r1).
- **SC-004**: A clean single-approved-lane squash merge completes without a spurious `TARGET_BRANCH_CONTENT_CONFLICT`, while a genuine failed projection still refuses (#5038).
- **SC-005**: `tests/terminus/` and `tests/merge/` pass with the four new red-first repros GREEN and the 3-way `xfail(strict)` still xfailing (honest-red preserved).
