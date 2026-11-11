# Mission Specification: Coordination closeout recovers from its own commits

**Mission Branch**: `kitty/mission-coord-closeout-recovery-01M75QCY`
**Created**: 2026-11-11
**Status**: Draft
**Input**: Sub-epic #7544 (part of #7543): coordination-topology (`lanes_with_coord`) closeout must
recover from its own commits. Core issues #7550, #5931, #5406 and #7540 items 1-3. Priority P1,
raised to **P0**: a minimal 6-lane `lanes_with_coord` closeout fails on `main`
(`research/code-grounding.md` §1).

Reader: the operator running `accept` and `consolidate` on a multi-lane Mission, and the maintainer
reviewing this change.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Accept records acceptance on a settled coordination Mission (Priority: P1)

An operator whose root checkout is on the Mission's target branch runs `spec-kitty accept` on a
Mission that `finalize-tasks` settled to `lanes_with_coord`. Today accept writes the record into the
coordination worktree and then crashes with a raw `git add` traceback from the root checkout.

**Why this priority**: every multi-lane Mission is `lanes_with_coord` by default (ADR `2026-11-06-3`),
and accept is the gate before consolidation; it cannot fail with a traceback.

**Independent Test**: build a settled `lanes_with_coord` Mission with every WP approved and the
acceptance matrix passed; run `spec-kitty accept`; check exit code, the commit on the Mission
branch, and the record's fields.

**Acceptance Scenarios**:

1. **Given** a settled `lanes_with_coord` Mission, all WPs approved, root checkout on the unprotected
   target, **When** the operator runs `spec-kitty accept`, **Then** it exits 0, the acceptance record
   is committed on the Mission (coordination) branch, the coordination worktree is clean, and the
   root checkout is untouched.
2. **Given** the same Mission, **When** accept records acceptance, **Then** `accepted_from_commit`
   names the Mission branch tip the record was written on, not the root checkout's HEAD.
3. **Given** the record cannot be committed, **When** accept runs, **Then** it exits non-zero with a
   named refusal code and a remedy, never a traceback.

---

### User Story 2 - A failed consolidate rolls back its own coordination commits (Priority: P1)

`consolidate` commits per-WP `done` transitions and the `mission_number` bake to the coordination
branch. When the run fails or is killed after those commits, the rollback must be able to undo them
and leave the coordination worktree in sync, without the operator touching git.

**Why this priority**: today a kill in the done-recording window wedges the Mission (#5931): every
route exits 1 and recovery needs hand-run git.

**Independent Test**: kill or fail `consolidate` after its own coordination commits; run
`consolidate --abort`; check every branch is restored and nothing is reported "moved by another
actor".

**Acceptance Scenarios**:

1. **Given** a settled `lanes_with_coord` Mission whose `consolidate` was killed while recording
   WPs done, **When** the operator runs `consolidate --abort`, **Then** every snapshotted branch is
   restored (the run's own `status transition` commits are explained by its record), the
   coordination checkout is resynced (its own status log/snapshot residue discarded), and the record
   is re-baselined.
2. **Given** a late-phase failure after the done commits, **When** the rollback runs, **Then** it
   restores the coordination branch and resyncs its checkout instead of refusing "uncommitted local
   changes".
3. **Given** a foreign commit on the coordination branch or a non-residue edit in its checkout,
   **When** the rollback runs, **Then** it still refuses exactly as today (no widening).

---

### User Story 3 - The next consolidate after `--abort` just runs (Priority: P1)

`consolidate --abort` tears down the coordination worktree (binding ruling on #5406). The next
`consolidate` must rematerialize it on demand and proceed; if it cannot, the refusal must name a
remedy that works for the Mission's topology.

**Why this priority**: today the next run refuses with a `git checkout <mission branch>` remedy that
cannot work for `lanes_with_coord`.

**Independent Test**: `consolidate` → injected failure → `--abort` → `consolidate`; the last run
exits 0 and lands every lane.

**Acceptance Scenarios**:

1. **Given** a settled `lanes_with_coord` Mission after `consolidate --abort` (coordination worktree
   removed, branch kept), **When** the operator runs `consolidate`, **Then** the coordination
   worktree is rematerialized from the local coordination branch and the run completes.
2. **Given** the coordination branch exists only on a remote, **When** the next run starts, **Then**
   it refuses with the materializer's named code and a coordination-topology remedy, not a
   `git checkout` of the branch in the repository root checkout.
3. **Given** a protected `single_branch` Mission whose files live only on its minted branch, **When**
   consolidate runs from another checkout, **Then** the existing `git checkout <branch>` remedy is
   unchanged.

---

### User Story 4 - End-to-end closeout with no hand-run git (Priority: P1)

The Done-when of #7544, as one integration test: a 6-lane `lanes_with_coord` Mission goes through
`accept`, `consolidate`, an injected late-phase failure, rollback, `--abort` and a re-run, through
the CLI, with no hand-run git and no in-process workaround beyond the injected failure.

**Independent Test**: the integration test itself.

**Acceptance Scenarios**:

1. **Given** the fixture, **When** the sequence runs, **Then** every step exits as expected and the
   target branch carries every lane's content at the end.

### Edge Cases

- A kill between the done write and its commit: the coordination worktree holds the run's own
  uncommitted status log/snapshot lines. They are this Mission's status state in its own
  coordination checkout, residue by the existing classifier rule; the rollback resyncs them.
- A kill after the CAS ref move but before the index sync: the checkout's content equals the run's
  own (intent-proven) tip; the restore resyncs it.
- A commit by another actor on the coordination branch during the run: it carries no intent; the
  rollback keeps reporting it NOT restored, and the next run keeps refusing `UNEXPLAINED_BRANCH_MOVE`.
- A Mission whose `meta.json` is unreadable everywhere: the residue context stays the strictest
  (nothing is residue), as today.
- Accept with the root checkout on a protected branch: unchanged router path.
- A `single_branch` Mission accepted on its own Mission branch in the root checkout: the record
  commit lands on that branch, as before.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Accept commits its record through the placement seam | As an operator, I want accept to commit its acceptance record on the surface the placement seam resolves for `PRIMARY_METADATA`, through the commit router, so that a settled `lanes_with_coord` Mission does not crash on a raw `git add` from the root checkout. | High | Open | [build] | no --- red through `spec-kitty accept` on a settled fixture, green after |
| FR-002 | `accepted_from_commit` names the Mission branch tip | As a reviewer, I want `accepted_from_commit` to be the tip of the branch that holds the record, so that the acceptance provenance points at the Mission, not the target. | High | Open | [build] | no --- paired with FR-001 on the same fixture; asserts the SHA |
| FR-003 | Accept's commit failure is a named refusal | As an operator, I want a failing record commit to exit with a named code and remedy, so that I never see a traceback. | Medium | Open | [build] | no --- a forced router failure asserts the code and no traceback |
| FR-004 | Residue context reads the stored topology where the Mission's metadata lives | As an operator, I want the destructive guards' residue context to read the Mission's stored topology through the placement seam, so that a settled Mission (meta.json only on its Mission branch) gets its real residue rules instead of the strictest fallback. | High | Open | [build] | no --- `ResidueContext.for_mission` on a root without meta.json returns the stored topology |
| FR-005 | Rollback resyncs the run's own coordination residue | As an operator, I want a rollback after consolidate's own coordination commits to restore the coordination branch and resync its checkout, so that I do not stash or reset by hand. | High | Open | [build] | no --- red through `consolidate --abort` after a kill, green after; paired with a foreign-edit control that still refuses |
| FR-006 | In-span coordination commits persist their advance intent | As an operator, I want every commit `consolidate` makes inside its rollback span to persist its advance intent before the branch moves, so that a kill never turns the run's own commit into an "unexplained" move. | High | Open | [build] | no --- a kill at the WP02 done commit; `--abort` restores; a foreign commit control stays unexplained |
| FR-007 | The next consolidate rematerializes the coordination worktree | As an operator, I want the consolidate after `--abort` to rematerialize the coordination worktree on demand, so that the Mission re-runs with no manual step. | High | Open | [build] | no --- red through `consolidate` after `--abort`, green after |
| FR-008 | Topology-aware remedy for a missing lanes manifest | As an operator, I want the missing-lanes refusal to name a remedy that works for the Mission's stored topology, so that a coordination Mission is never told to check out its coordination branch in the root checkout. | Medium | Open | [build] | no --- coordination branch remote-only asserts the coordination remedy; single_branch control keeps the checkout remedy |
| FR-009 | End-to-end coordination closeout | As a maintainer, I want one integration test that drives a 6-lane `lanes_with_coord` Mission through accept, consolidate, an injected late failure, rollback, `--abort` and a re-run via the CLI, so that the #7544 Done-when stays pinned. | High | Open | [build] | no --- fails on `main` at accept (P0 repro) |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Fast tier unaffected | The new unit tests run in under 5 s each; the end-to-end test is marked slow/e2e so `make test-fast` does not run it, and builds its fixture once per module. | Performance | High | Open |
| NFR-002 | No extra git calls outside the span | `safe_commit` outside a consolidate rollback span performs the same git calls as before (verified by test). | Performance | Medium | Open |
| NFR-003 | Quality gates | `ruff check`, `ruff format --check --force-exclude` on changed files and `mypy` clean; every touched function complexity ≤ 15. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | One rollback authority | No second rollback or restore path; extend `consolidation/rollback.py`'s authority only. `test_single_rollback_authority.py` stays green unchanged. | Technical | High | Open |
| C-002 | CAS stays | Compare-and-swap is never weakened; the change only adds CAS to commits that had none. | Technical | High | Open |
| C-003 | Foreign edits are never residue | Only files a spec-kitty command itself wrote and can prove (by the existing status-state rule or by an intent record) are resynced. | Technical | High | Open |
| C-004 | #5406 ruling | `consolidate --abort` keeps its coordination teardown; rematerialization goes through `materialize_coord_surface_for_write`. | Business | High | Open |
| C-005 | No new gates | No new size or ratchet gates. | Technical | Medium | Open |
| C-006 | `git/ref_advance.py` stays git plumbing | No `specify_cli` imports in `git/ref_advance.py` (C-003 of that module). | Technical | Medium | Open |

### Key Entities

- **Acceptance record**: the `meta.json` acceptance fields (`accepted_by`, `accepted_from_commit`,
  `accept_commit`, `acceptance_history`), a `PRIMARY_METADATA` artifact.
- **Consolidation record**: `ConsolidationState` (`pre_mutation_refs`, `post_mutation_refs`,
  `advance_intents`, `unsettled_refs`).
- **Residue context**: `ResidueContext` (checkout role, Mission slug, stored topology).
- **Coordination surface**: the coordination branch and its worktree.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a settled 6-lane `lanes_with_coord` Mission, `accept` → `consolidate` → injected late failure → `--abort` → `consolidate` completes with every lane landed and zero hand-run git commands --- [build] · no-op passable: no
- **SC-002**: A `consolidate` killed at its WP02 done commit is recoverable with `consolidate --abort` then `consolidate` (exit 0 both) --- [build] · no-op passable: no
- **SC-003**: No refusal in the closeout path tells a coordination Mission to `git checkout` its coordination branch in the repository root checkout --- [build] · no-op passable: no
