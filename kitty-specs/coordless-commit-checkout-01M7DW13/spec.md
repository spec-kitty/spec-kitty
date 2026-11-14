# Mission Specification: Coordination-less status commits take their checkout from the placement seam

**Mission Branch**: `kitty/mission-coordless-commit-checkout-01M7DW13`
**Created**: 2026-11-14
**Status**: Draft
**Input**: Operator dispatch brief for #7633, #7637 and #7648 (one runner, one PR), with operator ruling Q8 for #7633 shape (b). Grounding: `docs/plans/engineering-notes/2026-11-14-7633-7637-7648-coordless-commit-checkout.md`. #7633 is slice 2 of Mission `checkout-verdict-agreement-01M7B1GG` (slice 1, #7594, landed as PR #7638).

## Intent Summary

- **Primary actor:** an operator (or an agent acting for one) running lifecycle commands (`agent action implement` / `review`, `move-task`, status emits) on a Mission.
- **Trigger:** the command records a status change and commits it.
- **Desired outcome:** the status commit lands in the checkout the status read door reads, or the command refuses up front with a named code that says why and what to do. A review claim on a `lanes_with_coord` Mission targeting protected `main` succeeds. An unchanged follow-up commit is a no-op, never a rollback of rows that are already committed.
- **Rule that must always hold:** the placement seam is the one authority for where a Mission write lands; no raw "who holds this branch" probe chooses a commit checkout.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Status commits land where the read door reads (Priority: P1)

An operator records a status change on a Mission that has no coordination branch. The commit runs in the checkout the placement seam names for status writes, which is the checkout the status read door reads. When that checkout is not on the write branch (another checkout or a lane worktree holds it, or the holder has no Mission directory), the command refuses before writing anything, with a named code and a remedy.

**Why this priority**: today such a commit can land in a checkout that status reads never look at, so the operator's board silently disagrees with history (#7633).

**Independent Test**: the 11-row characterization matrix of #7633, each row built with the real Mission-create core in a real git repository.

**Acceptance Scenarios**:

1. **Given** an explicit `single_branch`, commit-to-target, explicit `lanes`, unsettled default, settled default or landed Mission whose write branch is held by the repository root checkout, **When** a status commit is acquired, **Then** it runs in the repository root checkout (unchanged).
2. **Given** a default Mission whose topic branch is held by another non-lane checkout that carries the Mission directory, **When** a status commit is acquired, **Then** it runs in that checkout (unchanged).
3. **Given** a default Mission whose topic holder carries no Mission directory (shape (b)), **When** a status commit is acquired, **Then** it refuses with `STATUS_WRITE_CHECKOUT_NOT_ON_WRITE_BRANCH` and writes nothing.
4. **Given** a commit-to-target or explicit `single_branch` Mission whose write branch is held by another checkout (shape (a)), or a Mission whose write branch a lane worktree holds, **When** a status commit is acquired, **Then** it refuses with the same code and writes nothing.

---

### User Story 2 - The review claim succeeds on a protected target (Priority: P1)

An operator runs `agent action review WP02 --agent <name>` on a `lanes_with_coord` Mission whose target is protected `main`. The claim records `in_review` on the coordination branch and the command exits 0 with the review prompt (#7637).

**Why this priority**: today the claim is recorded but the command exits 1 on a refused second commit to `main`, so no review prompt is printed.

**Independent Test**: the review-range acceptance tests on the `lanes_with_coord` fixture with `main` left protected (the fixture's protection lift removed).

**Acceptance Scenarios**:

1. **Given** a `lanes_with_coord` Mission on protected `main` with WP02 in `for_review`, **When** the operator claims the review, **Then** the command exits 0, prints the review prompt, and makes no commit attempt on `main`.

---

### User Story 3 - An unchanged follow-up commit is a no-op (Priority: P2)

A lifecycle command's follow-up commit finds its staged status files already committed. When the pending-changes check cannot read the checkout, the commit still resolves to a no-op at the current commit, keeps the committed rows, and the command succeeds (#7648).

**Why this priority**: latent today; when hit, it rolls back an already-committed claim and fails the command.

**Independent Test**: drive `commit_idempotent` with an unreadable pending-changes check over an already-committed status log.

**Acceptance Scenarios**:

1. **Given** status rows already committed at HEAD and a pending-changes check that cannot read git, **When** the idempotent follow-up commit runs, **Then** it returns a no-op receipt pinned at HEAD and the log bytes are unchanged.
2. **Given** the same state, **When** the strict commit runs, **Then** it still raises, as documented.

---

### User Story 4 - The legacy leaf's pre-check asks the checkout it commits in (Priority: P3)

On a Mission without a coordination branch that has a leftover `.worktrees/<slug>-coord` directory, the legacy commit leaf's "already committed" pre-check runs in the checkout the commit runs in, never in the leftover directory, and never creates a worktree.

**Independent Test**: legacy-leaf tests with and without a leftover coordination directory.

**Acceptance Scenarios**:

1. **Given** a leftover coordination directory and status paths already committed in the repository root checkout, **When** the legacy leaf runs, **Then** the pre-check short-cuts to the already-committed receipt.
2. **Given** a status path inside another checkout, **When** the legacy leaf runs, **Then** the pre-check never reports it as already committed.

### Edge Cases

- A caller passes a destination ref the seam does not name: the repository root checkout is used, under the same "must hold the ref" check.
- An owned Mission: the owned checkout is used, as today.
- A genuinely-legacy Mission (pre-coordination, lane worktree arm): unchanged.
- The PRIMARY-partition commit of a coordination Mission (`commit_to_primary_target`): takes its checkout from the seam's PRIMARY write location; a default Mission's topic holder before landing, the repository root checkout otherwise (FR-061 / #7372 unchanged).

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Seam-chosen status checkout | As an operator, I want a coordination-less status commit to run in the checkout the placement seam names for status writes (the repository root checkout for a ref the seam does not name), so that it lands where the status read door reads. | High | Open | [build] | no — the matrix rows "default topic held by another checkout" (seam answer) and the 7 agreeing rows are the same-fixture positive controls for the refusal rows |
| FR-002 | Refuse when the checkout is not on the write branch | As an operator, I want that commit to refuse before any write with `STATUS_WRITE_CHECKOUT_NOT_ON_WRITE_BRANCH` and a remedy when the chosen checkout does not hold the destination ref (shapes (a), (b) and the lane-holder row), so that a status write never lands where the read door does not read. | High | Open | [build] | no — red on the base for the 4 diverging matrix rows |
| FR-003 | No raw holder probe | As a maintainer, I want no raw branch-holder probe left in the bookkeeping transaction (status and PRIMARY arms both consume the seam), so that one placement authority decides every commit checkout. | High | Open | [build] | no — the PRIMARY-arm #7372 tests are the positive control |
| FR-004 | Review claim commits only the status pair | As an operator, I want the review claim to commit only the status files it wrote, so that a `lanes_with_coord` claim on protected `main` exits 0 and routes nothing to `main`. | High | Open | [build] | no — red on the base for the 8 `lanes_with_coord` cells once the fixture lift is removed |
| FR-005 | Idempotent commit treats an unchanged tree as a no-op | As an operator, I want the idempotent follow-up commit to return a no-op receipt when the staged tree is unchanged even if the pending-changes check could not read the checkout, so that committed rows are never rolled back. | Medium | Open | [build] | no — paired with the strict-commit control on the same fixture |
| FR-006 | Legacy pre-check asks the commit's own checkout | As an operator, I want the legacy leaf's pre-check to run in the checkout the commit runs in and to answer only for paths inside it, so that a leftover coordination directory neither diverts it nor gets materialized. | Low | Open | [build] | no — paired with the phantom-guard case |
| FR-007 | Allowlist entry names an open issue | As a maintainer, I want the write-side re-derivation gate's allowlist entry to cite an open tracking issue instead of closed #2453. | Low | Open | [build] | no — the gate file is re-run |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No write before refusal | A refused status commit leaves 0 bytes changed in every checkout (status log and snapshot byte-identical before and after). | Reliability | High | Open |
| NFR-002 | Bounded cost | The seam lookup adds at most one seam construction per acquire; the 11-row matrix stays under 200 s wall time with 6 workers. | Performance | Medium | Open |
| NFR-003 | Quality gates | ruff, ruff format and mypy report 0 issues on every changed file; no new suppression. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | One placement authority | The fix consumes `write_target` / `write_dir`; it does not add a second resolver (DIRECTIVE_044). | Technical | High | Open |
| C-002 | Strict commit unchanged | The strict commit keeps raising on an empty or unchanged changeset (#2861 contract). | Technical | High | Open |
| C-003 | Ruled fallback | For shape (b), never fall back to the repository root checkout (operator ruling Q8). | Business | High | Open |
| C-004 | Red first | Each fix lands after a test that is red on the base through the pre-existing entry point. | Technical | High | Open |
| C-005 | Scope | Only the three tickets and the named legacy-leaf residual; other directory-exists picks and the removed-coordination-worktree seam shape are filed, not changed. | Business | Medium | Open |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 11 rows of the #7633 characterization matrix pass, 4 of which are red on the base — [build] · no-op passable: no
- **SC-002**: All `lanes_with_coord` review-range acceptance cells pass with `main` protected (8 red on the base) — [build] · no-op passable: no
- **SC-003**: The idempotent-commit no-op test passes (red on the base) while the strict-commit control still raises — [build] · no-op passable: no

## Assumptions

- Shape (a) and the lane-holder row refuse up front with the same code as shape (b). Surfaced to the operator as Decision Moment `01M7DW21P5D4WNVCGC6ARASAV3`; this spec proceeds on the recommended option until it is answered.
- The review claim writes no byte to the WP file (the #2816 cutover), so dropping it from the commit loses nothing.
