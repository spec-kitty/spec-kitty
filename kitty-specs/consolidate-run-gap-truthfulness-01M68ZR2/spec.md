# Mission Specification: Consolidate run-gap truthfulness

**Mission Branch**: `consolidate-run-gap-truthfulness-01M68ZR2`
**Created**: 2026-10-31
**Status**: Draft
**Input**: User description: "spec-kitty/spec-kitty#6450 — CLI tooling gaps seen in the 2026-10-19 mission run (commit trailers, lock sweep, worktree dirt, misleading hints). This Mission takes only the slice the 2026-10-27 remediation comment groups together: items (4), (6) and (7)."

## Problem

Three of the seven observations in #6450 share one shape: the consolidation/acceptance
end-of-mission surfaces either leave work behind uncommitted or tell the operator to do
something that does not apply to their Mission. Each was cheap to work around by hand and
expensive to diagnose, because the output pointed at the wrong cause.

- **Item (4) — worktree dirt after a successful merge.** `consolidate` tombstones a lane's
  `.kittify/workspaces/<slug>-<lane>.json` when it removes that lane's worktree
  (`consolidation/phase_teardown.py::_remove_lane_worktrees`). In a project where those JSON
  contexts are tracked, the unlink is a real content change — but the phase runs *after*
  `_phase_commit_and_assert`, the single bookkeeping commit that persists the run's changes. The
  deletion is therefore never committed and the target branch is left dirty by a command that
  reported success.
- **Item (6) — a pull-request hint on a topology that opens no pull request.** On coordination
  topology the coordination branch is landed by `consolidate`; nothing is pushed for review. When
  `accept --mode pr` records the acceptance commit while HEAD is on the Mission's target branch,
  `is_integration_branch` is true and `_build_acceptance_instructions` prints "Push and open a
  pull request if needed" — advice that cannot be followed and that contradicts the consolidation
  instruction the same run's docs give.
- **Item (7) — the issue-verdict remedy printed when no verdict is missing.** The `done`
  terminality gate reuses `issue_matrix_done_outcome`, which fails for two different reasons: a
  row that is missing or still `in-mission`/`unknown`, and a matrix that is fully verdicted but
  carries a validation diagnostic (for example `deferred-with-followup` whose `evidence_ref`
  holds no follow-up handle). Both paths print the header "has unresolved entries. Fill in
  verdicts before done." and the `spec-kitty agent issue-verdict` remedy, so an operator whose
  every row has a verdict is sent to re-record verdicts that are already recorded.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A landed consolidation leaves the target branch clean (Priority: P1)

A maintainer consolidates a Mission whose lane workspace contexts are tracked. The run lands,
removes the lane worktrees, and tombstones the contexts — and the tombstones are committed with
the rest of the run's bookkeeping, so the target branch is clean when the command exits.

**Why this priority**: A command that reports success while leaving tracked deletions in the
working tree hands the next operator a dirty tree they did not create. Dirty-tree guards then
refuse unrelated work (`MERGE_UNSAFE_WORKTREE_DIRTY`).

**Independent Test**: Build a real git repo with a tracked `.kittify/workspaces/<slug>-<lane>.json`,
drive `_phase_cleanup_worktrees_and_branches` on a merge run, and read `git status --porcelain`.

**Acceptance Scenarios**:

1. **Given** a tracked lane workspace context and a merge run that removes the lane worktree,
   **When** the cleanup phase completes, **Then** the context file is deleted from the working
   tree *and* the deletion is committed, leaving `git status --porcelain` empty.
2. **Given** an untracked (or absent) lane workspace context, **When** the cleanup phase completes,
   **Then** no commit is created and the phase still succeeds.
3. **Given** several lanes, **When** the cleanup phase completes, **Then** one commit carries every
   tombstoned context and nothing else.

### User Story 2 - Acceptance guidance matches the Mission's landing path (Priority: P2)

An operator accepts a coordination-topology Mission from the target branch. The next-step list
names the consolidation that lands the Mission, and never suggests pushing a branch or opening a
pull request that the topology does not use.

**Why this priority**: The misleading hint costs a manual recovery step in exactly the run the
issue reports. It is a message-truthfulness defect: the command's own summary contradicts how the
Mission lands.

**Independent Test**: Call `_build_acceptance_instructions` for a coordination-topology Mission
whose HEAD is the target branch, in `pr` mode, and assert no pull-request instruction is emitted
and the consolidation instruction is.

**Acceptance Scenarios**:

1. **Given** a coordination-topology Mission accepted on its target branch in `pr` mode, **When**
   the next steps are rendered, **Then** they name `spec-kitty consolidate` and contain no
   "pull request" instruction.
2. **Given** a non-coordination Mission accepted on an integration branch, **When** the next steps
   are rendered, **Then** the existing instruction is unchanged (positive control on the same
   helper).

### User Story 3 - The `done` issue-matrix refusal names the real cause (Priority: P3)

An operator whose issue matrix has a verdict on every row but a validation diagnostic in one row
sees a refusal that names the diagnostic and does not tell them to record verdicts that already
exist. A matrix that really is missing a verdict keeps the verdict-recording remedy.

**Why this priority**: The gate decision is correct; only the remedy is wrong. A wrong remedy
sends the operator into a loop (record a verdict → still refused → record it again) and hides the
one line that says what is actually broken.

**Independent Test**: Ask `issue_matrix_done_outcome` for a `done` judgement on a matrix where
every row is verdicted and one row is `deferred-with-followup` with no follow-up handle in its
`evidence_ref`.

**Acceptance Scenarios**:

1. **Given** every row carries a verdict and the only failures are validation diagnostics, **When**
   the `done` judgement is requested, **Then** the message names the artifact and the diagnostics,
   and contains neither "Fill in verdicts" nor the `agent issue-verdict` remedy.
2. **Given** a row is missing or still `in-mission`, **When** the `done` judgement is requested,
   **Then** the message keeps the existing header, the missing/in-mission row list and the
   verdict-recording remedy (positive control on the same helper).
3. **Given** either input, **When** the terminality gate evaluates it, **Then** the gate still
   returns FAIL with the same blocking mode — the decision is never relaxed.

### Edge Cases

- A tracked workspace context that is already deleted when the cleanup phase starts: no commit,
  no error.
- A lane whose worktree was never created (planning-artifact lane): nothing to tombstone, nothing
  to commit.
- `--keep-worktree`: the context is preserved, so no tombstone and no commit.
- The tombstone commit itself fails (protected-ref refusal, concurrent move): the run keeps its
  current behaviour — surfaces the failure and never claims a clean tree.
- A coordination-topology Mission accepted in `local`/`checklist` mode: unchanged, since the
  misleading sentence only exists in the `pr` arm.
- An issue matrix whose rows are all `unknown` placeholders: that is a missing verdict
  (`unknown` is not a terminal verdict), so the verdict remedy must stay.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Tombstoned contexts are committed | As a maintainer, I want `consolidate` to commit the tracked `.kittify/workspaces/*.json` it tombstones so that a landed merge leaves the target branch clean. | High | Open | [build] | no |
| FR-002 | Tombstone commit is scoped and no-op safe | As a maintainer, I want the tombstone commit to carry only the tombstoned contexts, and to be skipped when nothing tracked was removed, so that cleanup never sweeps unrelated paths or creates empty commits. | High | Open | [ratchet] | no — positive control is FR-001 on the same fixture (one tracked context committed, one untracked context not) |
| FR-003 | Accept guidance follows the landing path | As an operator, I want `accept` on a coordination-topology Mission to point at `spec-kitty consolidate` instead of pushing a branch and opening a pull request. | Medium | Open | [build] | no |
| FR-004 | Other topologies' guidance unchanged | As an operator, I want the existing accept instructions for non-coordination Missions preserved, so that the fix cannot silently drop guidance elsewhere. | Medium | Open | [ratchet] | no — paired with FR-003 on the same helper (integration-branch positive control) |
| FR-005 | Done refusal names its cause | As an operator, I want the `done` issue-matrix refusal to print the verdict-recording remedy only when a verdict is actually missing or unresolved, and otherwise to name the validation diagnostics. | Medium | Open | [build] | no |
| FR-006 | Gate decision never relaxed | As a maintainer, I want FR-005 to change only the message: every input that failed before still fails, with the same blocking mode. | High | Open | [ratchet] | no — same-fixture FAIL assertions before and after the message change |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No new write surface | The tombstone commit lands through the existing `commit_merge_bookkeeping` seam; no new guarded commit call site and no direct `git commit` is added. | Technical | High | Open |
| NFR-002 | One extra commit at most | The cleanup phase adds at most one commit per consolidation run, and none when no tracked context was removed. | Performance | Medium | Open |
| NFR-003 | Message length bounded | The rewritten `done` refusal stays within the size of the message it replaces (same diagnostic lines, one header swap, at most one remedy line removed). | Technical | Low | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Bundle items 1, 2, 3 and 5 out of scope | Commit trailers/signing (item 1), the `spec-commit` lock-file sweep (item 2), the tracked review-lock deletion (item 3, the duplicate of #6386) and the stale-assertion `min_version` false positive (item 5) stay in #6450's backlog with the reasons recorded in the PR's `## Deferred` section. | Business | High | Open |
| C-002 | Decisions frozen | No requirement here may change a gate's pass/fail decision, a protection policy, or a ref destination; only persisted-content completeness and message truthfulness change. | Technical | High | Open |
| C-003 | Changelog and docs | The `[Unreleased]` changelog entry cites #6450; the affected recovery/how-to docs mention that consolidation commits the tombstoned contexts. | Business | Medium | Open |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After the cleanup phase of a merge run with one tracked and one untracked lane
  context, `git status --porcelain` is empty and exactly one commit exists on the target whose
  path list is the tracked context alone. — [build] · no-op passable: no
- **SC-002**: Zero "pull request" instructions in the rendered next steps for a
  coordination-topology Mission accepted on its target branch, and exactly one
  `spec-kitty consolidate` instruction. — [build] · no-op passable: no
- **SC-003**: The diagnostic-only `done` refusal contains zero occurrences of "Fill in verdicts"
  and of `agent issue-verdict`, while the missing-verdict refusal on the same helper still
  contains both. — [ratchet] · no-op passable: no
- **SC-004**: Every pre-existing `issue_matrix_verdict_terminality` gate test keeps its verdict and
  blocking mode — 0 changed decisions across the existing suite. — [ratchet] · no-op passable: no

## Out of Scope

- Items (1), (2), (3) and (5) of #6450, for the reasons in C-001.
- Any change to `review/lock.py` (item 3's subject; tracked by #6386).
- Any change to commit trailers, signing, or the commit-authoring core (item 1).
- The `spec-commit` input surface and its lock-file handling (item 2).
- The stale-assertion analyzer (`post_merge/stale_assertions.py`) (item 5).

## Traceability

| Source | Requirement |
|--------|-------------|
| #6450 scope item (4) | FR-001, FR-002, SC-001 |
| #6450 scope item (6) | FR-003, FR-004, SC-002 |
| #6450 scope item (7) | FR-005, FR-006, SC-003, SC-004 |
| #6450 remediation comment 2026-10-27 (items 4/6/7 grouped as one slice) | C-001, this Mission's boundary |
| #6450 remediation comment (items 1/2/3/5 deferred) | C-001 |
