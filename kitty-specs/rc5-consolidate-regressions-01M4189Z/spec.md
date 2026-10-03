# Mission Specification: rc5 consolidate regressions

**Mission Branch**: `kitty/rc5-consolidate-regressions`
**Created**: 2026-10-03
**Status**: Draft
**Input**: Operator kick-off brief (milestone 11, 4.0.0): four regressions of fixes that the rc5
changelog says already hold — #5569, #5571, #5570, #5572. Evidence and root causes:
[research.md](research.md).

## Intent Summary

An operator or orchestrating agent runs `spec-kitty consolidate` (and, after a failure,
`spec-kitty doctor coordination --fix`) and trusts the exit status. In four shapes the
command reports success while the target branch or the status log is wrong. This mission
makes each of those four shapes either produce the correct outcome or refuse with a
non-zero exit and honest advice. Invariant: consolidate never exits 0 while rejected or
canceled work landed, approved work is missing, or an acknowledged status change was lost.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Canceled dependency work never ships (Priority: P1, #5569)

A reviewer rejects WP01 and the operator cancels it, as consolidate's own refusal advises.
WP02 depends on WP01 and was started after WP01 was approved, so its lane carries WP01's
commit. The operator consolidates.

**Why this priority**: P0 — rejected code lands on the target at exit 0 by following the
tool's own advice.

**Independent Test**: real `implement` for both WPs (so the dependency merge is produced by
the product), cancel WP01, approve WP02, run `consolidate` under the default and
`--strategy merge`.

**Acceptance Scenarios**:

1. **Given** a fully-canceled lane whose commits are reachable on a dependent approved lane,
   **When** the operator consolidates (either strategy), **Then** the command exits non-zero,
   names the canceled WP, and the target does not hold the canceled WP's content.
2. **Given** the same dependency shape where the dependency WP is approved (not canceled),
   **When** the operator consolidates, **Then** both WPs' content lands, exit 0 (positive control).

### User Story 2 - Resume after an interruption never drops a lane (Priority: P1, #5571)

Consolidation is interrupted after advancing the mission branch and before refreshing the
coordination worktree. The operator runs `consolidate --resume`.

**Why this priority**: P0 — the printed remedy loses an approved WP's code permanently.

**Independent Test**: produce the post-advance, pre-refresh coordination worktree state with
real git, then run `consolidate --resume`.

**Acceptance Scenarios**:

1. **Given** a coordination worktree that only lags its own HEAD, **When** the operator runs
   `consolidate --resume`, **Then** the worktree is refreshed in place and the resume
   completes with every approved lane's content on the target.
2. **Given** a coordination worktree with genuine local edits, **When** the operator resumes,
   **Then** it refuses non-zero and the advice never tells the operator to commit the staged
   deletions of an integrated lane.

### User Story 3 - Teardown never destroys a late status change (Priority: P2, #5570)

During coordination teardown a reviewer records a status change on the coordination branch
after teardown's safety check.

**Why this priority**: P1 — an acknowledged status write disappears silently; narrow window.

**Independent Test**: commit to the coordination branch inside the teardown window, then
observe the branch and the exit status.

**Acceptance Scenarios**:

1. **Given** the coordination branch moved after the teardown check, **When** teardown
   deletes the branch, **Then** the delete is refused, the branch and the late commit remain,
   and the command exits non-zero with recovery advice.
2. **Given** the branch did not move, **When** teardown runs, **Then** the branch is deleted
   as before (positive control).

### User Story 4 - Doctor repair never reverts a reviewer's reopen (Priority: P2, #5572)

A failed consolidation left a stranded `done` and a repair marker. A reviewer then reopens a
WP. The operator runs `doctor coordination --fix`.

**Why this priority**: P1 — a repair claims "Healed" while erasing a reviewer's decision.

**Independent Test**: real stranded `done`, marker, real reopen status commit, then
`doctor coordination --fix` through the CLI.

**Acceptance Scenarios**:

1. **Given** a later status commit that is not part of the strand, **When** the operator runs
   `--fix`, **Then** no commit is reverted, "Healed" is not printed, the reopen survives, the
   marker is kept, and the exit is non-zero with manual-reconcile advice.
2. **Given** only the strand's own commits after the capture point, **When** `--fix` runs,
   **Then** exactly those are reverted and the marker cleared (positive control).
3. **Given** a marker written before this fix (no recorded commits), **When** `--fix` runs,
   **Then** it refuses rather than guessing.

### Edge Cases

- A canceled lane that no surviving lane depends on: still skipped cleanly (existing control).
- A fully-canceled lane reachable from a *mixed* lane: residual 7 — must also not ship.
- Resume where the coordination worktree lag is not pure (extra untracked/edited files): refuse.
- Teardown on a non-coordination mission: same compare-and-delete path, unchanged outcome when
  nothing moved.
- `consolidate --resume` reaching the strand heal: inherits the same recorded-commits rule.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Canceled dependency content refused | As an operator, I want consolidate to refuse when a fully-canceled lane's commits are reachable from a surviving lane so that rejected work never lands at exit 0 (#5569), under default and merge strategies. | High | Open | [build] | no — paired with the approved-dependency positive control on the same fixture |
| FR-002 | Residual 7 closed | As a maintainer, I want the mixed-lane variant (residual 7) to stop shipping canceled dependency content so that the strict xfail becomes a passing regular test. | High | Open | [build] | no — strict xfail XPASS turns red until the test is promoted |
| FR-003 | Coordination lag recovered on resume | As an operator, I want `consolidate --resume` to refresh a coordination worktree that only lags its own HEAD so that the resume completes with every approved lane's content on the target (#5571). | High | Open | [build] | no — today's behaviour refuses with MERGE_UNSAFE_WORKTREE_DIRTY |
| FR-004 | No reverting-commit advice for coordination worktree | As an operator, I want a coordination-worktree refusal on resume never to advise committing staged deletions of an integrated lane so that following advice cannot drop a lane (#5571). | High | Open | [build] | no — paired with the genuine-dirt fixture |
| FR-005 | Compare-and-delete coordination branch | As a reviewer, I want teardown to delete the coordination branch only if it still points at the checked tip so that a status change committed after the check survives (#5570). | Medium | Open | [build] | no — paired with the unmoved-branch positive control |
| FR-006 | Teardown refusal is visible | As an operator, I want a refused teardown delete to exit non-zero with recovery advice so that the outcome is never silent (#5570). | Medium | Open | [build] | no |
| FR-007 | Strand commits recorded at write time | As an operator, I want the repair marker to record the strand's own commits when written so that the heal can tell them from later commits (#5572). | Medium | Open | [build] | no |
| FR-008 | Heal reverts only recorded commits or refuses | As a reviewer, I want `doctor coordination --fix` (and the resume heal) to revert only recorded strand commits, and refuse without "Healed" when other status commits or a legacy marker are present, so that my reopen survives (#5572). | Medium | Open | [build] | no — paired with the strand-only positive control |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Red-first through real entry points | Each FR has a test that fails on the mission base and passes on the fix, driven through `consolidate`, `consolidate --resume`, the teardown path, or `doctor coordination --fix`; 4/4 issues covered. | Reliability | High | Open |
| NFR-002 | Quality gates | Touched code passes `ruff check`, `ruff format --check --force-exclude`, and `mypy` with 0 new findings; no new suppressions; functions stay at complexity ≤ 15. | Maintainability | High | Open |
| NFR-003 | No regression of existing consolidation tests | `tests/consolidation/`, `tests/terminus/`, `tests/coordination/` targeted modules show 0 new failures vs the mission base. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Fail-closed preserved | No fix weakens compare-and-swap ref handling or the closed-world rule; any such need is escalated to the operator. | Technical | High | Open |
| C-002 | Hard scope | Only the four shapes; closed originals (#4977 #4982 #4981 #4973) are evidence only; other strict-xfail residuals stay xfail. | Business | High | Open |
| C-003 | No attestation as fix | `--attest-canceled-superseded` is not presented as the product fix for any shape. | Technical | High | Open |
| C-004 | Single authority | Reuse existing seams (reconciliation claim, `classify_resume_dirty_remedy`, `repair_coord_strand`, ref CAS helpers); no parallel revert or delete path. | Technical | High | Open |

### Key Entities

- **Fully-canceled lane**: an execution lane whose every WP is `canceled`.
- **Approved authorship claim**: the commits/blobs the reconciliation gate attributes to approved lanes.
- **Coordination worktree lag**: the coordination checkout's index/files trailing its own branch tip after an interrupted advance.
- **Strand marker**: the `pending_coord_reconcile` record of a stranded coordination `done`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In all four reproduced shapes, consolidate/doctor exits 0 only when the target and status log are correct (0 of 4 false-success outcomes, from 4 of 4 today). — [build] · no-op passable: no
- **SC-002**: Each shape's positive control still succeeds (4 of 4). — [ratchet] · no-op passable: yes — guards against over-refusal only
- **SC-003**: Residual 7 is a passing regular test; the other pinned residuals remain strict xfail (count unchanged at 4). — [build] · no-op passable: no

## Assumptions

- Fix directions follow research.md; the plan may refine them without widening scope.
- `orchestrator_api` branch-delete site (same TOCTOU as #5570) is assessed in plan; folded only if it reuses the same helper with no new surface.
