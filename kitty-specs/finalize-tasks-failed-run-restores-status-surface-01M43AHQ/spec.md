# Mission Specification: finalize-tasks: a failed run leaves the status surface as it found it

**Mission Branch**: `kitty/fix-5641-finalize-tasks-atomic-status`
**Created**: 2026-10-04
**Status**: Draft
**Input**: Operator brief for #5641 (P0, milestone "4.0.0 release scope", parent epic #3897): a failed `spec-kitty agent mission finalize-tasks` must leave both the working tree and the branch history as it found them, or report precisely which commits it made and could not undo. Discovery answers come from the brief and from the code-grounding run (`research/code-grounding.md`).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A failed finalize leaves no status commits behind (Priority: P1)

An operator runs `finalize-tasks`, and it fails at its final commit (a full disk, a lock, a rejecting hook). Today the Mission files are restored, but the per-WP `status transition` commits stay on the status surface. On `lanes` / `single_branch` Missions the checkout is also left dirty against its own HEAD. After this mission, the failed run leaves every branch tip and every checkout's tracked state exactly as it found them, on every topology that commits status: `coord`, `lanes_with_coord`, `lanes`, `single_branch` and owned checkouts.

**Why this priority**: it is the P0 itself. Branch history and working tree disagree, and the next status write either drops committed events or is refused (`COORD_STATUS_SURFACE_DIVERGED`).

**Independent Test**: the reproduction `test_final_commit_failure_leaves_every_branch_and_checkout_as_found` (PR #5657) turns green with its `regression` marker removed.

**Acceptance Scenarios**:

1. **Given** a non-owned `coord` or `lanes_with_coord` Mission ready to finalize, **When** the final commit fails, **Then** the coordination branch tip, the coordination worktree's tracked state and the repository root checkout are unchanged.
2. **Given** a non-owned `lanes` or `single_branch` Mission on a topic branch, **When** the final commit fails, **Then** the current branch tip is unchanged and the checkout is clean against its own HEAD.
3. **Given** an owned checkout, **When** a later gate refuses after the bootstrap committed, **Then** P's HEAD is restored as before (no regression of the owned guard).

---

### User Story 2 - A commit the run cannot undo is reported, never forced (Priority: P2)

If the status surface's branch moved after the run's own last status commit (a foreign commit landed), the run must not rewrite it. It reports exactly which commits it made and could not undo, and it still exits non-zero.

**Why this priority**: forcing the ref back would destroy someone else's commit. Reporting is the honest fallback the issue names.

**Independent Test**: move the status surface's branch between the bootstrap and the restore, then check that the branch keeps the foreign commit and that the failure output names the left-over commits.

**Acceptance Scenarios**:

1. **Given** a foreign commit lands on the status surface after the seeds, **When** the run fails and restores, **Then** the branch keeps the foreign commit, the output names the branch and the seeded commits that remain, and the exit code is non-zero.

---

### User Story 3 - A retry after a failed run seeds once (Priority: P3)

After a failed run, a second `finalize-tasks` must seed each WP exactly once. Today a `lanes` / `single_branch` retry seeds again on top of the kept commits.

**Why this priority**: it follows from Story 1 and needs evidence, not a separate mechanism.

**Independent Test**: fail once, run again, and count the seed commits and the `planned` events on the status surface.

**Acceptance Scenarios**:

1. **Given** a failed run on a `lanes` Mission, **When** finalize-tasks runs again and succeeds, **Then** the history carries one `status transition` commit per WP and the log holds one `planned` seed per WP.

### Edge Cases

- The bootstrap itself raises after seeding some WPs. The restore must still cover the commits already made.
- The status surface is the repository root checkout, and the Mission directory restore has already put the pre-run bytes back. The index must match HEAD again without a `reset --hard`.
- The status surface lives in the coordination worktree, outside the Mission directory snapshot. Its status files must get their pre-run bytes back.
- The run fails before the bootstrap (an ownership or lane gate refusing early). Nothing was committed, and the restore must be a no-op.
- The run fails after the finalize commit landed. Nothing may be unwound (the existing `commit_landed` rule).
- The branch is detached or unreadable. The run cannot guard it, and must say so rather than guess.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Restore the status surface on failure | As an operator, I want a finalize-tasks run that fails before its final commit lands to put the status surface's branch tip, index and status files back to their pre-run state on every topology, so that history and working tree agree. | High | Open | [build] | no — the reproduction is red on main for coord, lanes_with_coord, lanes and single_branch |
| FR-002 | Compare-and-swap only | As an operator, I want the branch restored only while it still points at the run's own last status commit, through the sanctioned compare-and-swap route, so that a foreign commit is never discarded. | High | Open | [build] | no — paired with the foreign-commit row on the same fixture |
| FR-003 | Report what could not be undone | As an operator, I want a failed run that cannot undo its status commits to name the branch and the commits it left, and to exit non-zero, so that I can repair by hand. | High | Open | [build] | no — the foreign-commit test asserts the report |
| FR-004 | One restore authority for owned and non-owned runs | As a maintainer, I want the owned-checkout HEAD restore and the new restore to be one mechanism, so that the atomicity guard has one owner. | Medium | Open | [folded] | yes — owned behaviour must stay green on its existing tests |
| FR-005 | Retry seeds once | As an operator, I want a retry after a failed run to seed each WP once, so that the status log and history stay consistent. | Medium | Open | [build] | no — evidence recorded before (double seed) and after |
| FR-006 | Truth in code and docs | As a maintainer, I want the "NOT COVERED" comment, the FR-015/NFR-001 wording and the changelog to state what a failed run now leaves behind. | Medium | Open | [build] | yes — documentation |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No new destructive sites | Zero new `git reset --hard`, `worktree remove --force`, `merge --abort` or `stash push` literals; zero new allowlist entries in the destructive-op, rollback-authority, git-path-listing or status-write gates. | Safety | High | Open |
| NFR-002 | Bounded overhead | The guard adds at most four git subprocess calls per surface on the success path (rev-parse, symbolic-ref, write-tree, and the post-bootstrap rev-parse). | Performance | Medium | Open |
| NFR-003 | Quality gates | Changed code passes ruff, ruff format, mypy, and complexity of 15 or less per function. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Not the redesign | The #5343 plan/apply redesign is out of scope; if the honest fix needs it, stop and report. | Technical | High | Open |
| C-002 | Do not touch executor or the p0 lane | No change to `consolidation/executor.py` (#5650), `pytest.ini`, `tests/conftest.py` or `tests/_support/p0_repro.py` (#5639). | Technical | High | Open |
| C-003 | Keep refusal contracts | Existing refusal text and exit codes that other tests assert stay unchanged; the new report is an additional note. | Technical | High | Open |
| C-004 | Test economy | Add a test only when it guards real behaviour through the existing entry point; prefer strengthening an existing test. | Process | High | Open |

### Key Entities

- **Status surface**: the checkout and branch the transactional status writer commits to. That is the coordination worktree and branch for `coord` / `lanes_with_coord`, the current branch of the repository root checkout for `lanes` / `single_branch`, and P's branch for an owned checkout.
- **Status surface snapshot**: the branch name, pre-run tip, pre-run index tree and pre-run bytes of the status directory, captured before the first status write of a run, plus the tip after the run's last status commit.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The #5641 reproduction passes for all four non-owned topologies with its `regression` marker removed. — [build] · no-op passable: no
- **SC-002**: A foreign commit on the status surface survives a failed run, and the run's output names the commits it could not undo. — [build] · no-op passable: no
- **SC-003**: A retry after a failed `lanes` run leaves exactly one seed commit and one `planned` event per WP. — [build] · no-op passable: no
- **SC-004**: The existing finalize atomicity and owned-checkout tests stay green. — [ratchet] · no-op passable: yes
