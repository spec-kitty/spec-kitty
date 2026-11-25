# Mission Specification: Recoverable stale-lane refusal after a halted in-run auto-rebase

**Mission Branch**: `kitty/mission-stale-lane-sibling-recovery-01M7X1QS` (lands on `fix/7755-stale-lane-auto-rebase-recovery`)
**Created**: 2026-11-20
**Status**: Draft
**Input**: Bugfix for #7755 (P0) folding #7754 (P2). Discovery was answered from the issue text and code-grounding (unattended scheduled run); see `decisions/`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A stale refusal caused by a sibling lane can be recovered (Priority: P1)

An operator runs `spec-kitty consolidate` on a lanes Mission whose two approved, independent lanes edit the same file. The first lane is consolidated into the Mission branch; the second is then stale, and its in-run auto-rebase stops on a conflict with the first lane's change. The run refuses the second lane and rolls the Mission branch back to its pre-run tip, which removes the first lane's change. Today the refusal names the rolled-back Mission branch, so refreshing from it brings in nothing, and every later run refuses the same way.

**Why this priority**: it is a P0: the Mission cannot be landed through any in-tool route.

**Independent Test**: through `spec-kitty consolidate`, refuse the stale lane, follow the printed remedy, re-run, and observe the lane pass and the Mission land.

**Acceptance Scenarios**:

1. **Given** the conflicting sibling-lane Mission, **When** the operator runs `consolidate`, **Then** the refusal says the in-run auto-rebase stopped and why, and names the sibling lane and its branch as the change to incorporate.
2. **Given** that refusal, **When** the operator follows the printed steps (reopen the work package, re-enter it, incorporate the named sibling branch, resolve, commit, review and approve again), **Then** the next `consolidate` passes the lane and lands the Mission.

### User Story 2 - The remedy runs for an approved work package (Priority: P2)

At `consolidate` every work package is approved, and `agent action implement` refuses an approved work package. The remedy today names that command as the first step, so it can never run as given.

**Why this priority**: the printed remedy fails on its first command for every stale refusal at consolidate.

**Independent Test**: render the stale remedy for a code lane and check that its first command is the reopen step and that it states the review cost.

**Acceptance Scenarios**:

1. **Given** a stale code lane at consolidate, **When** the refusal prints, **Then** it first names the reopen command (`move-task <WP> --to planned --review-feedback-file <file>`), says it costs a re-review, and only then names `agent action implement`.

### Edge Cases

- The stale lane has no worktree: the in-run auto-rebase is not attempted; the refusal names no halt, still names the sibling lane, and the re-entry recreates the checkout.
- The auto-rebase stops for a reason other than a content conflict (for example local changes that a merge abort would discard): the refusal carries that reason verbatim.
- The overlapping change is on the Mission branch but comes from no sibling lane: the remedy keeps the auto-rebase refresh through `implement`, after the reopen step.
- A planning (repository-root) lane: its remedy is unchanged.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Requirement | Status | Delivery | No-op passable? |
|----|-------------|--------|----------|-----------------|
| FR-001 | When the in-run auto-rebase of a stale lane stops, the stale refusal states that the auto-rebase ran and stopped, with its halt reason. | Accepted | [build] | no |
| FR-002 | The stale refusal names every sibling lane, with its branch, whose consolidated change overlaps the stale files and is missing from the stale lane. | Accepted | [build] | no |
| FR-003 | When sibling lanes are named, the remedy tells the operator to incorporate the named sibling branch in the lane checkout, not to refresh from the Mission branch the rollback restores. | Accepted | [build] | no |
| FR-004 | For a code lane, the remedy first names the reopen command for its work package(s) with its review cost, before any `agent action implement` step, and ends with re-running `consolidate`. | Accepted | [build] | no |
| FR-005 | After the operator follows the remedy, the next `consolidate` run passes the previously stale lane (and lands the Mission when nothing else refuses). | Accepted | [build] | no |
| FR-006 | The #7755 reproduction runs as a per-PR guard (its `p0_repro` marker removed). | Accepted | [ratchet] | no |

### Non-Functional Requirements

| ID | Requirement | Status |
|----|-------------|--------|
| NFR-001 | Identifying sibling lanes adds at most two git probes per other lane of the Mission, run only on the stale path. | Accepted |
| NFR-002 | Changed functions stay at cyclomatic complexity 15 or below and pass `ruff` and `mypy` with no new suppression. | Accepted |

### Constraints

| ID | Constraint | Status |
|----|------------|--------|
| C-001 | Rollback semantics, the single rollback authority (`consolidation/rollback.py`), CAS ref discipline and the approved-bound refusals are unchanged. | Accepted |
| C-002 | Lane branch names come from the canonical branch-naming composer, never a hand-built string. | Accepted |
| C-003 | Out of scope: dry-run forecasting of this refusal (#7324) and reconciliation attribution of unreviewed merges (#5604 / #5053). | Accepted |

## Success Criteria *(mandatory)*

- SC-001: In the reproduced scenario, an operator who follows the printed remedy lands the Mission on the next run (1 run after recovery, not an endless refusal loop). — [build] · no-op passable: no
- SC-002: 100% of stale refusals at consolidate print a first step that runs for an approved work package. — [build] · no-op passable: no

## Assumptions

- Every work package is approved when `consolidate` runs its stale check (consolidate gates on review approval), so the remedy can always assume an approved work package.
- Incorporating a sibling lane is new content and needs a fresh review; the reopen step is the sanctioned route (an unreviewed merge fails reconciliation, #5604).
