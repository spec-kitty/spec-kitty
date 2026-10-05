# Mission Specification: Rollback anchor authority (#5686, #5666)

**Mission Branch**: `issue-5686-rollback-anchor` (lanes topology; consolidates locally into it)
**Created**: 2026-10-05
**Status**: Draft
**Input**: Operator brief (orchestrating session, 2026-10-05): deliver #5686 and #5666, the two P0 consolidate rollback-anchor defects of milestone 11 ("4.0.0 release scope", rc6 blockers), as one mission. Make the red-first reproductions of PR #5762 green and drop their `p0_repro` markers. Structural aim: one anchor authority. Grounding: [`research/code-grounding.md`](research/code-grounding.md).

## Intent Summary (confirmed)

- **Primary actor**: an operator (human or agent) running `spec-kitty consolidate`, `consolidate --resume` and `consolidate --abort` on a repository where other actors (teammates, other missions' status commits) may commit concurrently, and where a consolidate process can be killed.
- **Trigger**:
  - a consolidate killed after it moved a branch but before it recorded that move (#5686); or
  - a reconciliation gate FAIL/REFUSE while another actor's commit sits on top of the landing (#5666).
- **Desired outcome**: every rollback and every `--abort` restores a branch only from this run's persisted record. It compare-and-swaps against a tip this run recorded, or provably wrote. It never treats a live tip it cannot explain as a restore anchor, and it never reports "restored" for a branch it did not restore.
- **Rule / invariant**: one rollback authority (`consolidation/rollback.py::rollback_to_snapshot`). No second restore path. A move the record cannot explain is never silently re-anchored: it is adopted only on proof, refused otherwise, or explicitly released by the operator.
- **Operator decision (2026-10-05)**: adopt when provable plus refuse, plus an explicit operator release (`--abort --release-branch`).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A reconciliation FAIL never discards a concurrent commit (Priority: P1, #5666)

While consolidate runs, a teammate or another mission commits on the target after this run's squash landed. The gate FAILs, and the rollback must not erase that commit.

**Why this priority**: data loss on the protected target, hidden behind a report that says `unchanged main`.

**Independent Test**: drive the FAIL/REFUSE gate inside the real rollback door (the driver's span `try`) with a foreign commit on top of the recorded landing. Assert that the commit is still reachable from the target and that the report names the target as NOT restored (moved by another actor).

**Acceptance Scenarios**:

1. **Given** the squash landed and was recorded as this run's post tip, and a foreign commit F then landed on the target, **When** the reconciliation gate FAILs or REFUSEs, **Then** F stays reachable from the target, the target is reported `NOT restored ... moved by another actor`, and the run exits non-zero.
2. **Given** F landed on the target *between* two recorded phases, and a later recorded phase of this run committed on top of F, **When** the run then fails and the door rolls back, **Then** F stays reachable. The later phase's tip is never recorded as this run's post tip, because the phase's entry tip was not the tip the record expected.
3. **Given** no foreign commit landed, with the primary checkout on the target, **When** the gate FAILs or REFUSEs, **Then** the single door restores the target to its pre-mutation snapshot by compare-and-swap against the recorded post tip, the report is a full restore, and the primary checkout is left clean at the snapshot. This is the positive control on the same fixture.

### User Story 2 - A kill-left landing is never reported as restored (Priority: P1, #5686)

A consolidate is killed after `update-ref` landed the squash on the target but before the phase recorded it. Then the operator runs `--abort`, a re-run or `--resume`, and `--abort` again.

**Why this priority**: today `--abort` exits 0 with "Branches restored to their pre-consolidation commits" and deletes the record, while the target keeps a squash that never passed reconciliation (canceled WP content included).

**Independent Test**: the #5762 reproduction (snapshot, `begin_attempt`, landing, abort, `begin_attempt`, abort), with its `p0_repro` marker removed. Plus kill-window scenarios through the real `advance_branch_ref` path.

**Acceptance Scenarios**:

1. **Given** a landing this run wrote through `advance_branch_ref`, whose intended SHA was persisted before the write with a base equal to the tip the record expected, **When** `--abort` runs after the kill (whether the kill came before or after the checkout resync), **Then** the target's outcome is RESTORED: observed tip = the intent, restored to the snapshot, compare-and-swap against the adopted intent. The primary checkout is clean at the snapshot and the record is cleared.
2. **Given** the same fixture, but with the landing made by a plain commit (no persisted intent), **When** a re-run or `--resume` starts, **Then** it refuses with error code `UNEXPLAINED_BRANCH_MOVE` before running any step that could move a branch (before the coord-strand heal and before the operator attestations). It names the branch, its restore target and the live SHA, keeps the record (the unsettled mark, the restore target and the intents are unchanged), and prints only non-destructive remedies. A second re-run refuses identically.
3. **Given** the same unexplained move, **When** `--abort` runs any number of times, with re-runs in between, **Then** it reports the branch `NOT restored` and keeps the record. It never reports `unchanged`/`already at`, and never a full restore.

### User Story 3 - `--abort` never deadlocks (Priority: P2, #5687 fold-in)

A branch can be NOT restored indefinitely: an unprovable kill-left move, or a foreign commit on top of this run's landing. The operator needs a non-destructive way to keep the current tip and clear the record.

**Why this priority**: refusing on every call (#5687) leaves the operator with only a destructive manual git reset.

**Independent Test**: `consolidate --abort --release-branch <b> --release-reason "..."` on a record whose `<b>` is NOT restored.

**Acceptance Scenarios**:

1. **Given** a record where branch B would be reported NOT restored, **When** the operator runs `--abort --release-branch B --release-reason "keep teammate commit"`, **Then**:
   - B is left untouched at its live tip and reported `kept by operator`, with the reason and a warning that the kept tip may contain this consolidation's unverified changes;
   - every other branch is restored as usual;
   - the record is cleared only if every other branch is restored;
   - the success line names B as kept and never says all branches were restored.
2. **Given** `--release-branch` without `--abort`, or without `--release-reason`, or naming a branch that is not a snapshotted run-movable branch (a lane branch or an unknown name), **When** the command runs, **Then** it refuses with `RELEASE_BRANCH_INVALID` (exit 2) and changes nothing.
3. **Given** a release of a branch that would in fact be restorable (at its recorded post tip, or a provable intent), **When** `--abort` runs, **Then** the branch is restored, not kept: a release never keeps a provable landing of this run.
4. **Given** a released branch whose tip moves after the release, **When** a later `--abort` runs, **Then** the release no longer applies (it binds to the SHA recorded at release time).

### User Story 4 - The restore target is the record's, across attempts (Priority: P2)

An operator's commit made between two attempts, on a branch the record holds no unsettled run content for, stays the restore target of every later attempt. It is never reset to the snapshot because a later attempt started at its own post tip.

**Independent Test**: unit tests of `begin_attempt` across three attempts.

**Acceptance Scenarios**:

1. **Given** attempt 1 was fully restored, the operator committed M on the mission branch, and attempt 2 advanced it to P and was killed after recording P, **When** attempt 3 starts at P, **Then** the mission branch's restore target is still M, and a rollback restores to M, never to the pre-M snapshot.
2. **Given** a branch the record holds as unsettled (this record's run moved it and no rollback restored it), **When** an attempt starts with that branch at a tip that is neither its restore target, its recorded post tip, nor a provable intent, **Then** the move is unexplained (US2 AS2), even if the previous attempt exited in an orderly way.

### Edge Cases

- **Kill between phases (the recorder ran):** the move is recorded, so nothing changes.
- **Kill inside a nested recorded phase:** the unsettled mark is per branch and per record, not per phase, so the nesting does not matter. Intents are cleared per branch.
- **Kill before any mutation (zero-progress record, #5372):** every live tip equals its restore target, so nothing is unexplained.
- **The run's own pre-claim moves (the coord-strand heal, operator attestation status commits):** the unexplained-move check runs before them. A branch they move afterwards is this process's own move and is accepted, as today.
- **After a reconciliation PASS:** the target is settled (verified). Post-PASS bookkeeping commits and a later `git pull` (#5687) are therefore not unexplained.
- **Truncated `state.json` from a kill during a save:** the write is atomic, so the old or the new record survives intact.
- **Older record with no unsettled list:** loads as "nothing unsettled", which is today's behaviour.
- **A branch that no longer exists:** existing F3 behaviour (recreate hint), unchanged.
- **A landing verified by an earlier reconciliation (FR-011 refusal):** unchanged.
- **Kill between `update-ref` and the checkout resync** (the primary checkout is behind its own HEAD, with worktree and index at the snapshot content): the restore treats a checkout whose index and worktree already match the restore target as clean.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | FAIL/REFUSE rollback goes only through the single door | As an operator, I want a reconciliation FAIL/REFUSE to restore the target only through `rollback_to_snapshot` (CAS against the recorded post tip) so that a concurrent commit is never discarded. `_rollback_target_after_failed_reconciliation` is retired. | High | Open | [build] | no — the #5666 test is red today; paired with the US1 AS3 positive control |
| FR-002 | One restore path is pinned | As a maintainer, I want the AST pin to forbid any `restore_branch_ref` call in the consolidation executor family (not elsewhere in src) outside `rollback.py`, and to list the retired helper, so that a second restore path cannot return. | High | Open | [build] | no — self-mutation case |
| FR-003 | Unsettled branches | As an operator, I want the record to persist, per run-movable branch, whether this record's run may have left unrestored, unverified moves on it. A branch becomes unsettled when `begin_attempt` opens an attempt. It is settled by a rollback outcome RESTORED / ALREADY_AT_SNAPSHOT / KEPT_BY_OPERATOR and, for the target, by a reconciliation PASS. A NOT_RESTORED outcome leaves it unsettled. | High | Open | [build] | no |
| FR-004 | No re-anchoring over an unexplained move | As an operator, I want `begin_attempt` to keep the record's restore target and leave the branch unrecorded when the branch is unsettled and its live tip is neither its restore target, its recorded post tip, nor a provable intent, so that `--abort` never reports such a tip as already restored. | High | Open | [build] | no — the #5686 test is red today |
| FR-005 | Named refusal ahead of every run move | As an operator, I want a re-run or `--resume` facing an unexplained move to refuse with `UNEXPLAINED_BRANCH_MOVE` before the coord-strand heal, the operator attestations and the claim. It names the branch and SHAs, keeps the record unchanged (idempotent on repeat) and offers only non-destructive remedies. | High | Open | [build] | no |
| FR-006 | Adopt a provable kill-left advance | As an operator, I want every `advance_branch_ref` / `advance_branch_ref_for_commit` inside the post-mutation span to persist, fail-closed and before the compare-and-swap write, its (base, new) pair as a per-branch intent chain. The authority then counts a live tip in the chain as this run's post tip, but only when the chain's base equals the tip the record expected for that branch. Intents are cleared per branch when a recorder records or rejects that branch, at `begin_attempt`, and on a full restore. | High | Open | [build] | no — paired with US2 AS2 on the same fixture |
| FR-007 | Restore target carried across attempts | As an operator, I want a restore target fixed by an earlier attempt to stay in force while the branch sits at that target or at this run's (effective) post tip. | Medium | Open | [build] | no |
| FR-008 | Operator release on `--abort` | As an operator, I want `consolidate --abort --release-branch <b> --release-reason <text>` (repeatable) to keep a branch that would be NOT restored at its live tip (bound to that SHA), report it as kept by the operator, and let the record clear when everything else is restored, so that `--abort` never deadlocks. | Medium | Open | [build] | no |
| FR-009 | Truthful abort text | As an operator, I want the `--abort` success line to name every branch kept by the operator and say "restored" only for restored branches. | Medium | Open | [build] | no |
| FR-010 | P0 reproductions become per-PR guards | As a maintainer, I want both #5762 tests green with their `p0_repro` markers removed. The #5666 test drives the gate through the door, because the helper it called is retired. | High | Open | [build] | no |
| FR-011 | No post tip over a foreign interleave | As an operator, I want the phase recorder to refuse to record a branch whose tip at phase entry was not the tip the record expected (its recorded post tip, else its restore target), so that a foreign commit landing between two phases is never adopted underneath this run's later commit. | High | Open | [build] | no — US1 AS2 |
| FR-012 | Restore over a lagging checkout | As an operator, I want the checkout resync of a restore to accept a checkout whose index and worktree already equal the restore target, so that a kill between `update-ref` and the resync does not leave `--abort` refusing a provable landing. | High | Open | [build] | no — US2 AS1 kill-after-update-ref variant |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Atomic merge record | `save_state` writes `state.json` atomically (temp file + rename via `kernel.atomic.atomic_write`). A kill at any point leaves either the previous or the new record, fully parseable. | Reliability | High | Open |
| NFR-002 | Rollback latency | The existing NFR-001 rollback bound still holds (< 2 s for the full-topology restore test). The intent write adds at most one record save per advance inside the span. | Performance | Medium | Open |
| NFR-003 | Code quality | New and changed code is ruff/format/mypy clean, with cyclomatic complexity ≤ 15 per function and no new suppressions. | Maintainability | High | Open |
| NFR-004 | Backward-compatible record | A `state.json` written before this change loads with the new fields at safe defaults (nothing unsettled, no intents, no releases). An older binary reading a newer record ignores the new keys. | Compatibility | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Single rollback authority | Never add a restore path; this mission removes one. The AST pin may only shrink callers and grow the retired list. | Technical | High | Open |
| C-002 | No destructive recipe | No refusal, warning or report prints a destructive git recipe (`reset --hard`, `branch -f`, `update-ref` to an older SHA) (#3931 / #5078). | Technical | High | Open |
| C-003 | Coordinate with PR #5724 | Do not edit `consolidation/reconciliation.py`. Do not change the meaning of `target_expected_old_sha` / the excluded window base. | Process | High | Open |
| C-004 | Coordinate with #5611 | Do not touch the coordination status-write seam (`coordination/status_surface_guard.py`, coord status files at teardown). #5638 stays out of scope. | Process | High | Open |
| C-005 | No new size/ratchet gates | No new size or ratchet gate, and no issue priority changes. | Process | Medium | Open |
| C-006 | Layering | `git/ref_advance.py` stays git plumbing. It reports intents to an injected sink and never imports consolidation state. | Technical | High | Open |

### Key Entities

- **Pre-mutation snapshot** (`pre_mutation_refs`): branch → SHA, captured once per record. Unchanged.
- **Restore target** (`restore_targets`): branch → SHA. It now comes only from the record (snapshot, an earlier attempt's target, or a move made between attempts on a settled branch).
- **Post-mutation tip** (`post_mutation_refs`): branch → SHA this attempt left the branch at. It is the compare-and-swap expectation of every restore.
- **Unsettled branches** (new, `unsettled_refs`): run-movable branches that may carry this record's unrestored, unverified moves.
- **Advance intent chain** (new, `advance_intents`): branch → [base, new₁, new₂, …], persisted ahead of each advance in the span.
- **Operator release** (new, `released_refs` / `release_reasons`): branch → SHA (and reason) the operator chose to keep.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `pytest tests/consolidation/test_rollback_anchor_p0_repro.py` reports 2 passed both with and without `SPEC_KITTY_RUN_P0_REPRO=1`, and the file carries no `p0_repro` marker — [build] · no-op passable: no
- **SC-002**: across every new kill/FAIL scenario, no `consolidate`/`--abort` invocation exits 0 or prints "restored"/"unchanged" for a branch at an unexplained, unreleased tip — [build] · no-op passable: no
- **SC-003**: in every new and existing scenario, no commit that another actor landed on the target after this run's recorded post tip becomes unreachable from the target — [build] · no-op passable: no
- **SC-004**: the existing rollback, resume and abort suites (`tests/consolidation`, `tests/terminus`, `tests/git`, `tests/specify_cli/cli/commands/test_consolidate_abort_rollback.py`) stay green, every re-pinned test is justified in the PR, and the FR-002 self-mutation case is included — [ratchet] · no-op passable: yes — positive control: SC-001

## Out of Scope / Cross-references

- #5372: stale `--target`/`--strategy`/`--push` adopted from an auto-resumed record (record-loading seam). Cross-ref.
- #5667 half: a stale `pre_mutation_target_sha` window base causes a false FAIL after a full restore. No data loss once FR-001 lands. Deferred because it changes `target_expected_old_sha` (C-003).
- #5048(a): PASS-anchor re-arm. Cross-ref.
- #5638: coord status files dirty after a rollback (C-004). Out of scope.
- #5686 operator-attested *undo* of an unprovable landing (a tool-mediated CAS restore of a tip the record cannot prove): not built; filed as a follow-up. Today the operator either keeps it (release) or moves the branch by hand.
- Resume recovery (`resume_recovery._recover_behind_head_primary_on_resume`) may reset a provably behind-HEAD checkout to its HEAD before the refusal of FR-005. This is a checkout resync, not a ref move, and is documented as a residual.
- #5687: the part where a resume re-bases its window after `git pull` and then pushes. Out of scope; only the reset and the deadlock are folded in.
