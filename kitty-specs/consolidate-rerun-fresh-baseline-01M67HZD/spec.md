# Mission Specification: A clean rollback leaves no stale consolidation baseline (#6770)

**Mission Branch**: `issue-6770-consolidate-rerun-fresh-baseline`
**Created**: 2026-10-30
**Status**: Draft
**Input**: User description: "spec-kitty/spec-kitty#6770 — consolidate re-run after a failed reconciliation reuses attempt 1's `pre_mutation_target_sha`, so commits made on the target in between are re-flagged (#5667 recurrence); a plain `--abort` then refuses. Reproduce, then make the re-run derive a fresh, honest baseline while keeping the abort path usable."

## Intent Summary

`spec-kitty consolidate --strategy merge` runs one transaction: it snapshots the
branches it may move, lands the lanes on the target, verifies the landing
(reconciliation), and only then tears down. Any failure between the first
mutation and the teardown runs through the single rollback door (#5385), which
restores every branch it moved. Today that door leaves the transaction record
(`.kittify/runtime/merge/<mission_id>/state.json`) on disk even when it restored
*everything*, and the loader treats an existing record as an interrupted run, so
the next plain `consolidate` silently *resumes* attempt 1 rather than starting
fresh. Two consequences follow from the record's `pre_mutation_target_sha` being
the *only* reconciliation window base it will use:

1. **A stale baseline.** Attempt 1 captured the target tip at `T0`. After the
   rollback the operator (or a teammate, or another mission) commits `T0..T1` on
   the target. Attempt 2's reconciliation window still starts at `T0`, so those
   already-landed commits are offered to the verifier as mission content and are
   reported "un-attributable". Attempt 2 FAILs for content it did not author, and
   its own rollback restores the target to the record's restore target — erasing
   commits that landed between the attempts.
2. **A wedged abort.** A fully restored rollback also clears the recorded
   post-mutation tips, so a later plain `spec-kitty consolidate --abort` finds the
   target at a tip that is neither the restore target nor a recorded post and
   refuses with "moved since the snapshot but no post-mutation tip was recorded".
   The only way out is `--abort --release-branch <target> --release-reason ...`.

The invariant this Mission delivers: **a transaction record survives only while
some of its attempt is still on the target.** A rollback door that fully undoes
its attempt leaves nothing to resume or to abort, so it clears the record; the
next run is then genuinely fresh, and a fresh run's window base is the target's
current tip. A partial rollback keeps the record (nothing is lost), and while the
record survives, attempt 1's persisted base is still the honest one because
attempt 1's landing is still on the target.

- **Primary actor**: the operator recovering a Mission whose consolidation failed.
- **Trigger**: a post-mutation failure (a reconciliation FAIL/REFUSE, a bookkeeping
  refusal, an interrupt) whose rollback restores every branch the run moved.
- **Outcome**: the record is gone, a plain re-run derives its baseline from the
  live target tip, and a plain `--abort` is a clean no-op instead of a refusal.
- **Rule that must always hold**: the rollback authority never adopts a move it
  cannot explain, and never clears a record that still holds un-restored content.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A re-run after a clean failed attempt derives the target's current tip (Priority: P1)

An operator runs `spec-kitty consolidate --mission <slug> --strategy merge`. The
landing FAILs reconciliation and the rollback restores every branch, so the target
is back at `T0` and nothing of the attempt remains. The operator fixes the cause on
the target, committing `T1` (`T0` is an ancestor). They run the same command again.

**Why this priority**: this is the reported defect and its data-loss consequence.
Without it, the recorded remediation path destroys the operator's own fix and the
Mission cannot be consolidated by re-running.

**Independent Test**: build a real single-repo Mission whose first consolidation is
forced to FAIL reconciliation once, let the door restore it fully, commit on the
target, then re-run through the real entry point and assert the re-run passes with
the target's pre-run tip as its reconciliation window base.

**Acceptance Scenarios**:

1. **Given** a fully restored rollback of a reconciliation FAIL, **When** the door
   finishes, **Then** the Mission's transaction record no longer exists (neither
   `state.json` nor its reconciliation marker).
2. **Given** that restored state and a new commit `T1` on the target, **When** the
   operator re-runs `consolidate`, **Then** the run is fresh (not a resume), its
   reconciliation window base is `T1`, and the run succeeds with `T1` still an
   ancestor of the target.
3. **Given** the same failure, **When** the operator runs a plain
   `spec-kitty consolidate --abort` instead of a re-run, **Then** it exits 0 and
   reports that no active merge state exists, instead of refusing and keeping the
   record.

### User Story 2 - A partial rollback keeps the record and its honest baseline (Priority: P1)

A post-mutation failure rolls back, but one branch cannot be restored (a dirty
checkout, a commit another actor landed, a verified landing kept). The operator
runs the Mission again.

**Why this priority**: the fix must not trade the reported bug for a lost record.
The kept record is what makes the un-restored branch recoverable, and while it is
kept, attempt 1's landing *is* still on the target — so its persisted base remains
the truthful window base.

**Independent Test**: reuse the existing dirty-target-checkout fixture; assert the
record survives with empty per-attempt bookkeeping, the pre-mutation base is
unchanged, and the re-run still refuses or restores rather than adopting the
unexplained move.

**Acceptance Scenarios**:

1. **Given** a rollback that leaves a branch NOT restored, **When** the door
   finishes, **Then** the record is kept and still carries attempt 1's
   `pre_mutation_target_sha`.
2. **Given** that kept record, **When** the operator re-runs, **Then** the run
   still refuses an unexplained move (`UNEXPLAINED_BRANCH_MOVE`) rather than
   re-baselining over it.

### Edge Cases

- The rollback is refused because the current target tip is a landing verified by
  an **earlier** reconciliation (the `rollback.py` verified-landing guard of
  `consolidation-claim-rollback-integrity-01M3PD1T`). Nothing was restored, so the record must
  be kept: the verified landing is still on the target.
- The rollback is fully restored but the process is killed between the restore and
  the record clear. The record that remains claims no per-attempt progress, which is
  the pre-fix zero-progress residue #5372 owns; the clear must never make that
  residue *worse* (no new state shape, no marker-less state).
- The record clear itself fails (permissions, a held file). The original failure
  must still be the operator's headline; a half-cleared record is at worst an
  orphan marker the next fresh run re-stamps (the same rule
  `_clear_fresh_record_on_pre_mutation_exit` already follows).
- A coordination mission: the coordination branch is restored in the same door, so
  its `pending_coord_reconcile` marker and the record go together.
- A `--resume` whose attempt rolls back fully: it is treated exactly like a fresh
  attempt, because after a full restore there is nothing left to resume.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | A fully restored rollback clears the transaction record | As an operator recovering a failed consolidation, I want a rollback that undid everything to leave nothing behind so that the next run cannot inherit attempt 1's baseline. | High | Open | [build] | no — the pre-fix door leaves `state.json` in place, which the regression test observes directly |
| FR-002 | The next run is fresh and re-baselines on the live target tip | As an operator, I want the re-run's reconciliation window base to be the target's current tip so that commits made between attempts are not judged as mission content. | High | Open | [build] | no — the pre-fix run resolves `T0` from the record; the test pins `T1` |
| FR-003 | A plain `--abort` after a clean rollback does not refuse | As an operator, I want `spec-kitty consolidate --abort` to be usable after a clean failure so that I am not forced into `--release-branch`. | High | Open | [build] | no — pre-fix abort exits 1 and keeps the record |
| FR-004 | A partial rollback keeps the record and its pre-mutation base | As an operator, I want a record that still carries un-restored content to survive, with attempt 1's window base intact, so nothing is lost and no foreign move is adopted. | High | Open | [ratchet] | no — paired on the same fixture with FR-001: one fully restored case, one partial case |
| FR-005 | A failed clear never replaces the original error | As an operator, I want the failure I hit to stay the headline so that cleanup trouble does not hide the real cause. | Medium | Open | [build] | no — the door re-raises the original `typer.Exit`/exception; the clear is attempted in a guarded step |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|--------|--------|
| NFR-001 | No new state shape or migration | The fix adds no persisted field, no new file and no migration: a record written by an older release loads and behaves exactly as before, and the clear reuses `clear_state`, the single owner of clearing a record (`state.json` plus its marker). | Maintainability | High | Open |
| NFR-002 | No widened rollback authority | The rollback authority's decisions are unchanged: no branch is moved that it would not already move, and the target is never left restored-verified or un-restored beyond today's outcomes. | Reliability | High | Open |
| NFR-003 | Targeted test budget | The changed surface's targeted suites stay green in the mission (the termination/rollback integration files named in the task list, plus the consolidation rollback unit files); no full heavy suite is run locally. | Performance | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|--------|--------|
| C-001 | One owner for clearing a record | The clear goes through `specify_cli.consolidation.state.clear_state`; no second unlink path is added. | Technical | High | Open |
| C-002 | The door stays the only rollback site | The behaviour is delivered inside the existing single rollback door and its report, not by adding a second rollback or a second failure hook. | Technical | High | Open |
| C-003 | Out of scope: the kill residue and the release flow | The zero-progress record a hard kill leaves (#5372) and the `--release-branch` recovery for a genuinely unexplained move (#5687) keep their current contracts; this Mission neither closes nor changes them. | Business | High | Open |

### Key Entities

- **Consolidation record** (`ConsolidationState`): the persisted transaction record
  for one Mission's consolidation. Owns the pre-mutation anchors, the snapshot, the
  per-attempt restore targets and post tips, and progress bookkeeping.
- **Rollback report** (`RollbackReport`): the door's aggregate outcome. Its
  `fully_restored` verdict is the signal that the attempt left nothing behind.
- **Reconciliation window base** (`run.target_expected_old_sha`): the commit the
  reconciliation verifier treats as the pre-mutation target tip. It is the
  persisted `pre_mutation_target_sha` when a record is resumed, and a live
  `rev-parse` on a fresh run.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the regression fixture, a reconciliation FAIL whose rollback restores every branch leaves no transaction record, and a re-run after one target commit succeeds with that commit as its window base — [build] · no-op passable: no
- **SC-002**: On the same fixture, a plain `consolidate --abort` after the clean failure exits 0 with "no active merge state" — [build] · no-op passable: no
- **SC-003**: On the dirty-checkout fixture, the record survives a partial rollback with attempt 1's `pre_mutation_target_sha` and empty per-attempt bookkeeping — [ratchet] · no-op passable: no
- **SC-004**: The named targeted suites pass and the changed lines are covered — [build] · no-op passable: no
