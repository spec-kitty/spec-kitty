# Mission Specification: Every post-mutation consolidate exit rolls back through one authority

**Mission Branch**: `claude/5385-single-rollback-authority-qqt180`  
**Created**: 2026-09-30  
**Status**: Draft  
**Input**: GitHub issue #5385 (P1 bug, milestone 4.0.0, parent epic #5001) and the operator's triage ruling of 2026-09-30 (issue comment 5904427409): deliver as one mission. Route every non-zero exit between consolidate's first mutation and its reconciliation gate through the single rollback authority, retire the deprecated per-phase revert paths, and refuse a protected-target consolidation that cannot write its bookkeeping before anything moves.

## Intent Summary

- **Primary actor**: an operator (human or agent) running `spec-kitty consolidate` on an accepted mission.
- **Trigger**: consolidate fails after it has started moving branches (lane consolidation onto the mission branch, the mission-number bake, the mission-to-target squash, done bookkeeping, the bookkeeping commit) and before the reconciliation gate.
- **Desired outcome**: the failure leaves every branch consolidate moved back where it was before the run (target, mission, coordination), prints the one rollback report, and exits non-zero with a readable error; a re-run starts clean.
- **Rule that must always hold**: there is exactly one way consolidate undoes its own branch moves, the compare-and-swap restore to the pre-mutation snapshot. No failure path between the first mutation and the gate leaves a branch advanced without saying so.
- **Up-front refusal**: a mission whose done bookkeeping would be refused on its target (the #5385 shape: a LANES mission, or a SINGLE_BRANCH mission without a mission branch, targeting a protected branch) is refused before any branch moves, with the same refusal code and remedy the bookkeeping write would have raised.

Decisions recorded: `DM-01M3RCPP2CR19QH3GZVPJT52BH` (scope, from the triage ruling) and `DM-01M3RCRDBS2RKWVVZH07AZ1B4M` (committed bookkeeping after a failure is rolled back with everything else; the older keep-done contract is re-pinned).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A failure after the squash leaves no branch advanced (Priority: P1)

An operator consolidates a mission. The squash lands on the target, then a later step fails (the done bookkeeping is refused, the working-tree invariant trips, the bookkeeping commit fails). Today the target stays advanced, sometimes with canceled work on it, `--abort` does not restore it, and the next run fails with "squash produced no changes". After this mission the same failure restores the target, the mission branch and the coordination branch to their pre-run tips, prints the rollback report, and exits 1.

**Why this priority**: this is the P1 defect. A terminus command must never leave committed-but-unverified content on the target.

**Independent Test**: inject a failure in each post-mutation phase of a real consolidate run over a real git repository and compare every branch tip to its pre-run value.

**Acceptance Scenarios**:

1. **Given** a mission whose consolidation squashes onto the target, **When** a step after the squash and before the reconciliation gate fails, **Then** the target, mission and coordination branches are back at their pre-run tips, the rollback moves no lane branch, and the output carries the rollback report and a non-zero exit.
2. **Given** the same failure raised as an unexpected exception (not a handled refusal), **When** consolidate exits, **Then** the rollback still runs before the exception leaves consolidate.
3. **Given** a failure during lane consolidation itself, **When** consolidate exits, **Then** the mission or coordination branch is back at its pre-run tip even when several lanes had already been merged (merge commits in the range).
4. **Given** the rollback ran in full, **When** the operator re-runs consolidate after fixing the cause, **Then** the run resumes the kept merge record from the pre-run branch state and succeeds (no "produced no changes" wedge).
5. **Given** the post-merge working-tree invariant fails because the target checkout carries unexpected changes, **When** consolidate exits, **Then** the target is reported NOT restored (the checkout is dirty, and the rollback never overwrites it), every other movable branch is restored, the merge record is kept, and the exit is non-zero.

### User Story 2 - A protected-target mission that cannot write its bookkeeping is refused up front (Priority: P1)

An operator consolidates a LANES mission whose target is `main` (protected by default). Today the run squashes onto `main` and then crashes on the done bookkeeping. After this mission, consolidate refuses before the first branch move with the protected-branch refusal code and its remedy, and every branch is byte-identical to before the run. `--dry-run` reports the same refusal.

**Why this priority**: it is the live #5385 trigger and the refusal is cheap and certain before any mutation.

**Independent Test**: build a LANES mission targeting protected `main`, run consolidate and `consolidate --dry-run`, and check the exit code, the refusal code in the output, and that no branch moved and no merge record was written.

**Acceptance Scenarios**:

1. **Given** a LANES mission targeting a protected branch, **When** the operator runs consolidate, **Then** it exits 1 before any branch moves, names the protected-branch refusal code and the remedy, and leaves no merge record behind.
2. **Given** the same mission, **When** the operator runs `consolidate --dry-run`, **Then** the forecast reports the same refusal code.
3. **Given** a coordination-topology mission, a SINGLE_BRANCH mission with its own mission branch, a SINGLE_BRANCH mission with the commit-to-target opt-out, or the operator's protected-branch hatch, **When** the operator runs consolidate on a protected target, **Then** the preflight does not refuse (same verdict the bookkeeping write itself gives).
4. **Given** a LANES mission targeting an unprotected branch, **When** the operator runs consolidate, **Then** the preflight does not refuse.

### User Story 3 - One rollback door, pinned (Priority: P2)

A maintainer changing consolidate cannot quietly add a second rollback mechanism or leave a post-mutation exit uncovered: an architectural pin fails the build.

**Why this priority**: closes the defect class by construction, not only the known symptoms.

**Independent Test**: the pin's self-mutation cases show it fails on a synthetic driver with an unwrapped post-mutation phase and on a reintroduced revert-based rollback helper.

**Acceptance Scenarios**:

1. **Given** the driver, **When** the pin scans it, **Then** every phase call from the first mutation through the reconciliation gate sits inside the one wrapper that calls the rollback authority on a non-zero exit or an exception.
2. **Given** a synthetic source that calls a mutating phase outside the wrapper, or that defines a revert-based rollback helper, **When** the pin runs over it, **Then** the pin fails.

### Edge Cases

- A failure before the first branch actually moved (for example the first lane merge refuses): the rollback reports every branch unchanged and consolidate still exits 1 with the original error.
- A landing already verified by an earlier reconciliation (a resume): the authority keeps it (existing FR-011 guarantee), and says so.
- A branch another actor moved during the run, or one whose post tip was never recorded: reported NOT restored, the merge record is kept for inspection, exit stays non-zero.
- A dirty checkout of a branch the rollback restores: reported NOT restored rather than overwritten (existing authority guarantee).
- The rollback itself raises: the original failure is still the one reported; the rollback failure is printed alongside it, never swallowed silently.
- A `--resume` of a partially consolidated run whose earlier attempt was fully rolled back starts again from the snapshot (lane merges re-run).
- An interrupt (Ctrl-C) inside the span also triggers the rollback; a hard kill does not, and leaves the record for `--abort`.
- A resume whose work packages are all already `done` writes no done bookkeeping, so the preflight does not refuse it.
- A `--target` override does not change where status bookkeeping is written (the mission's recorded target), so the preflight judges the recorded target.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Every post-mutation non-zero exit rolls back | As an operator, I want every non-zero exit between consolidate's first branch move and its reconciliation gate to restore the target, mission and coordination branches to the pre-run snapshot through the single rollback authority, so that a failed run never leaves a branch advanced. | High | Open | [build] | no — a planted failure in each phase must show the branch tips restored where today they stay advanced |
| FR-002 | Unexpected exceptions roll back too | As an operator, I want an unexpected exception raised in that span (for example the bookkeeping policy refusal) to trigger the same rollback before it leaves consolidate, so that a crash is not a worse outcome than a handled refusal. | High | Open | [build] | no — the #5385 exception today leaves the target advanced |
| FR-003 | Readable error for a policy refusal | As an operator, I want a bookkeeping policy refusal that escapes the executor to print its refusal code, message and remedy and exit 1 instead of a traceback. | Medium | Open | [build] | no — today it prints a traceback |
| FR-004 | Retire the revert-based coordination reset | As a maintainer, I want the revert-based coordination reset (and its wrappers) removed, so that consolidate has one way to undo its own branch moves. | High | Open | [build] | no — the helpers exist today; the pin fails if they return |
| FR-005 | Retire the orphan-bake revert | As a maintainer, I want the revert of an orphan mission-number bake commit on the target removed, its job done by the snapshot restore. | High | Open | [build] | no — same as FR-004 |
| FR-006 | Protected-target preflight | As an operator, I want consolidate to refuse, before any branch moves, a mission whose done bookkeeping the workflow mutation policy would refuse on its status write target, reusing that policy's verdict (code, message, remedy) rather than a second protection rule. | High | Open | [build] | no — today the run squashes first |
| FR-007 | Dry-run parity | As an operator, I want `consolidate --dry-run` to report the same protected-target refusal code. | Medium | Open | [build] | no — today the forecast is clean |
| FR-008 | AST pin covers the new door | As a maintainer, I want the single-rollback-authority pin to require the post-mutation span to sit inside the wrapper and to forbid revert-based rollback helpers in the executor, with self-mutation cases proving it can fail. | High | Open | [build] | no — self-mutation cases |
| FR-009 | Truthful record after rollback | As an operator, I want the merge record after a full rollback to claim no completed work packages, no bake, and no pending coordination strand, so that a resume or fresh run starts from the snapshot. | Medium | Open | [ratchet] | yes — the authority already clears these on a full restore; paired with FR-001's planted failures on the same fixture |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Byte-identical refusal | A preflight refusal leaves 0 branch tips moved and 0 merge-record files written. | Reliability | High | Open |
| NFR-002 | No new complexity debt | Every function touched stays at cyclomatic complexity 15 or below; ruff, ruff format and mypy report 0 new issues on changed files. | Maintainability | High | Open |
| NFR-003 | Coverage | Changed and new lines are at least 90% covered by the targeted tests (the CI diff-cover gate). | Maintainability | High | Open |
| NFR-004 | Real-git evidence | Every rollback and preflight acceptance test drives real git and asserts real branch SHAs; at most the failure injection itself is patched. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Single protection authority | The preflight reuses the existing workflow mutation policy verdict; it does not define its own list of protected branches or topology rule. | Technical | High | Open |
| C-002 | Authority unchanged | The rollback authority's guarantees (CAS restore, lane branches report-only, verified landing kept, dirty checkout refused) are reused, not weakened. | Technical | High | Open |
| C-003 | Out of scope | Resume residuals #5371 and #5372, the commit router's LANES bookkeeping behaviour on protected branches (#3536), the coordination strand repair primitive, and the post-gate teardown/push phases are out of scope. | Business | High | Open |
| C-004 | Mission test policy | No full heavy suite runs during work packages; targeted files and named architectural gates only. | Technical | Medium | Open |
| C-005 | No version bump | No version change past the untagged release candidate. | Business | Medium | Open |

### Key Entities

- **Pre-mutation snapshot**: the branch tips captured once before the first mutation; the only restore target.
- **Rollback authority**: the single compare-and-swap restore that undoes this run's branch moves and reports per branch.
- **Post-mutation span**: from lane consolidation (first mutation) through the reconciliation gate.
- **Protected-target verdict**: the workflow mutation policy's answer for a done-bookkeeping write on the mission's status write target.

## Assumptions

- An unexpected exception keeps its type after the rollback runs (callers that catch specific exception types keep working); only the bookkeeping policy refusal gets a dedicated readable rendering at the command layer.
- Working-tree byte restores of bookkeeping files that run before the branch restore stay; they touch only toolchain-generated files the authority's checkout resync tolerates.
- Tests that pinned the older keep-done-on-failure contract (#1826 resume truthfulness, #2367 strand shape, #2786 revert-failure strands) are re-pinned to the snapshot-restore contract per DM-01M3RCRDBS2RKWVVZH07AZ1B4M.
- Existing `--abort` repro fixtures that relied on the #5385 crash to leave residue get an explicit, documented crash-residue injection instead.

## Known residuals (named, not closed here)

- A stale lane auto-rebased during lane consolidation receives a merge commit on the lane branch. The rollback never moves lane branches, so that commit stays after a rollback (report-only lanes, authority guarantee 2a).
- The resume-start coordination strand heal is a forward revert that runs before the attempt begins; a later rollback treats that commit as the restore floor.
- A checkout whose resync failed after its branch moved looks dirty to the rollback and is reported NOT restored.
- On a protected SINGLE_BRANCH landing, the write checkout that was switched to the target stays there after a rollback.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For each post-mutation phase, a planted failure leaves 0 of the target, mission and coordination branches advanced past their pre-run tips (today at least 1 stays advanced). — [build] · no-op passable: no
- **SC-002**: A LANES mission targeting a protected branch moves 0 branches and writes 0 merge-record files before refusing. — [build] · no-op passable: no
- **SC-003**: The executor defines 0 revert-based rollback helpers, and the pin fails on each of its self-mutation cases. — [build] · no-op passable: no
- **SC-004**: After fixing the cause, a re-run of a failed consolidation succeeds on the first attempt. — [build] · no-op passable: no
