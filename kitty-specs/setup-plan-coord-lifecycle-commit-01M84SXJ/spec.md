# Mission Specification: setup-plan commits its lifecycle events on coordination Missions

**Mission Branch**: `kitty/mission-setup-plan-coord-lifecycle-commit-01M84SXJ`
**Created**: 2026-11-23
**Status**: Draft
**Input**: User description: "setup-plan commits its own lifecycle events on coordination topologies (#3933 Slice 1b): route SpecifyCompleted, PlanStarted and PlanCompleted through write_dir(STATUS_STATE) and commit them on the coordination branch; non-coordination topologies unchanged."

## Intent Summary (confirmed by the operator, 2026-11-23)

- **Actor**: an agent or operator running `spec-kitty agent mission setup-plan` on a Mission whose coordination branch already exists (created with an explicit `--topology coord` or `--topology lanes_with_coord`).
- **Trigger and outcome**: setup-plan records its three lifecycle events (`SpecifyCompleted`, `PlanStarted`, `PlanCompleted`) on the Mission's coordination record and commits them there in the same run. Afterwards the repository root checkout shows no uncommitted lifecycle-log change from setup-plan, and the coordination record holds all three events.
- **Rule**: a Mission without a coordination branch behaves exactly as today. Its lifecycle log rides the plan commit, and its bytes and commits are unchanged.
- **Exception**: when recording or committing on the coordination branch is refused or fails, setup-plan says so with a named, actionable error. It never reports success while its own lifecycle events stay uncommitted.
- **Stranded events** (operator ruling, Decision Moment `01M84SXYYJK8KRCW345X56VNQH`): the coordination health check reports a coordination Mission whose repository root checkout log holds lifecycle events that the coordination record lacks. It reports only: no repair, no migration.

## Premise correction (operator ruling, Decision Moment `01M853E34H1MN0CQGQ9209P8MR`, 2026-11-23)

A reproduction through the real CLI on an explicit `lanes_with_coord` Mission (main @ `1890a6c`) showed that setup-plan **already writes** its three lifecycle events to the coordination worktree's log; the repository root checkout stays clean. The defect is only that the events stay **uncommitted** in the coordination worktree. The operator ruled:

- FR-001 becomes a ratchet (the placement already holds); the writes move onto the single write-location authority for status records with no behaviour change.
- FR-005 is folded into the existing `doctor coordination` warning `COORDINATION_WORKTREE_DIRTY`, which already reports that residue; no new doctor check.

The Intent Summary above is kept as confirmed; where it says "repository root checkout" for the place the events land today, read "coordination worktree".

## User Scenarios & Testing *(mandatory)*

### User Story 1 - setup-plan leaves a coordination Mission clean (Priority: P1)

An agent finishes the specification of a coordination Mission and runs setup-plan. Today the plan is committed, and the three lifecycle events are written to the coordination worktree's status log but never committed there, so the coordination branch misses them and the coordination worktree stays dirty. The agent (or orchestrator) has to hand-commit `kitty-specs/`, or later commands refuse on the dirt.

**Why this priority**: it is the last open part of #3933 and recurs once per coordination Mission. Every hand commit is a step outside governed tooling.

**Independent Test**: create a coordination Mission, commit a substantive spec, run setup-plan, then inspect the repository root checkout and the coordination branch.

**Acceptance Scenarios**:

1. **Given** a coordination Mission with a committed substantive spec, **When** setup-plan runs and writes a substantive plan, **Then** the coordination branch holds `SpecifyCompleted`, `PlanStarted` and `PlanCompleted` for this Mission, committed, and neither the repository root checkout nor the coordination worktree has an uncommitted change to the Mission's status log.
2. **Given** the same Mission, **When** setup-plan reports its result, **Then** the result names the coordination commit that recorded the events.
3. **Given** a coordination Mission whose coordination commit is refused (for example a protected or diverged coordination surface), **When** setup-plan runs, **Then** it exits non-zero with a named error code and says which events were not recorded, instead of reporting success.

### User Story 2 - Missions without a coordination branch are unchanged (Priority: P1)

An agent runs setup-plan on a `single_branch` or `lanes` Mission, or on a default Mission before finalize-tasks settles its topology.

**Why this priority**: #7562 already fixed these topologies; this Mission must not regress them.

**Independent Test**: run setup-plan on each such topology before and after the change and compare the commits and the status log.

**Acceptance Scenarios**:

1. **Given** a `single_branch` Mission, **When** setup-plan runs, **Then** the lifecycle events ride the plan commit, the reported commit names it, and nothing is written to any other checkout.
2. **Given** a default Mission before settlement, **When** setup-plan runs, **Then** the behaviour is the same as before this Mission.

### User Story 3 - The health check names stranded events (Priority: P2)

An operator of a repository that ran setup-plan on coordination Missions before this fix runs the coordination health check.

**Why this priority**: existing Missions keep uncommitted lifecycle events in their coordination worktree; the operator needs to see them, but this Mission repairs nothing (operator rulings).

**Independent Test**: the existing `COORDINATION_WORKTREE_DIRTY` warning of `doctor coordination` already reports a coordination worktree with uncommitted changes (folded, ruling `01M853E34H1MN0CQGQ9209P8MR`); its existing tests cover it.

**Acceptance Scenarios**:

1. **Given** a coordination Mission whose coordination worktree holds uncommitted lifecycle events, **When** the coordination health check runs, **Then** it warns `COORDINATION_WORKTREE_DIRTY` for that worktree and changes no file.

### Edge Cases

- setup-plan re-run on a Mission whose events were already recorded: no duplicate events and no empty commit.
- A plan that is not yet substantive (scaffold only): the plan is not committed, as today; the lifecycle events recorded so far are still committed on the coordination branch rather than left dirty.
- The coordination worktree is not materialized when setup-plan runs: it is established through the existing write-location authority, or the run refuses with that authority's named error.
- An owned checkout: owned checkouts are `single_branch` only, so they fall under User Story 2.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Record on the coordination surface | As an agent running setup-plan on a coordination Mission, I want its three lifecycle events recorded on the coordination record, through the single write location for status records, so that the Mission's record is in one place. | High | Open | [ratchet] | yes — paired with FR-002 on the same coordination fixture, which a no-op fails |
| FR-002 | Commit in the same run | As an agent, I want those events committed on the coordination branch in the same setup-plan run, so that no checkout is left dirty by setup-plan. | High | Open | [build] | no — today they stay uncommitted |
| FR-003 | Non-coordination topologies unchanged | As an agent on a Mission without a coordination branch, I want the lifecycle log to keep riding the plan commit with the reported commit naming it, so that #7562's fix holds. | High | Open | [ratchet] | yes — paired with FR-001/FR-002 on the coordination fixture, which a no-op fails |
| FR-004 | Fail loud on a refused commit | As an agent, I want a refused or failed coordination commit to end setup-plan with a named error code that lists the unrecorded events, so that success is never reported while the events are uncommitted. | High | Open | [build] | no — today a refusal cannot occur because nothing is committed |
| FR-005 | Report stranded events | As an operator, I want the coordination health check to report a coordination worktree left with uncommitted lifecycle events, without changing any file, so that I can see the residue of the old behaviour. | Medium | Open | [folded] | yes — satisfied by the existing `COORDINATION_WORKTREE_DIRTY` warning (ruling `01M853E34H1MN0CQGQ9209P8MR`) |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Bounded commit count | A setup-plan run on a coordination Mission adds at most one commit to the coordination branch, and zero when every event it would record is already there. | Reliability | High | Open |
| NFR-002 | No regression on other topologies | For `single_branch`, `lanes` and a default Mission before settlement, the files setup-plan writes and the commits it makes are identical before and after this Mission (0 differences in the regression fixtures). | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Default Mission before settlement out of scope | A default Mission before finalize-tasks settles its topology is out of scope (operator ruling, Decision Moment `01M84SZDGPKXA5PBJ6HM6HQX08`); the open question is tracked in #7827. | Technical | High | Open |
| C-002 | No migration | Lifecycle events already stranded (uncommitted) in coordination worktrees are reported, never migrated, repaired or deleted, by this Mission; a setup-plan run's own commit of the whole status log may carry earlier lines along with its own events (operator ruling, Decision Moment `01M84SXYYJK8KRCW345X56VNQH`). | Business | High | Open |
| C-003 | Existing seams only | Placement uses the existing placement seam's write location for status records, and the commit goes through the existing mission commit entry point; no new seam and no ADR. | Technical | High | Open |

### Key Entities

- **Lifecycle event**: a Mission milestone (`SpecifyCompleted`, `PlanStarted`, `PlanCompleted`) appended to the Mission's status log.
- **Coordination record**: the Mission's status log on its coordination branch, the authority for status on a coordination topology.
- **Stranded event**: a lifecycle event written to a coordination Mission's coordination worktree log but left uncommitted there.

## Success Criteria *(mandatory)*

- **SC-001**: After setup-plan on a coordination Mission, 0 uncommitted changes to the Mission's status log remain in any checkout, and all 3 lifecycle events are on the coordination branch. — [build] · no-op passable: no
- **SC-002**: The regression fixtures for Missions without a coordination branch show 0 differences in written files and commits. — [ratchet] · no-op passable: yes (paired with SC-001)
- **SC-003**: A refused coordination commit produces a non-zero exit with a named error code in 100% of the refusal fixtures. — [build] · no-op passable: no
- **SC-004**: The coordination health check warns for a coordination worktree with uncommitted lifecycle events and changes 0 files. — [folded] · no-op passable: yes (existing `COORDINATION_WORKTREE_DIRTY` warning)

## Assumptions

- Missions with a coordination branch at setup-plan time are those created with an explicit coordination topology; a default Mission gains one only at finalize-tasks.
- The existing commit entry point already supports committing status records on the coordination branch (it does so for create and finalize-tasks).

## Out of Scope

- A default Mission before settlement: research and alignment follow-up #7827.
- Migrating, repairing or deleting stranded events.
- Other commands' lifecycle events: create and finalize-tasks already record theirs on the coordination surface.

## Related

- Parent defect: #3933 (last open part after PR #7562).
