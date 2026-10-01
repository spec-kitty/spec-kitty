# Mission Specification: Coordination status log stays off the target branch

**Mission Branch**: `claude/project-thread-oymt0g`  
**Created**: 2026-10-01  
**Status**: Draft  
**Input**: Remediate P0 issue #5440 using the red-first reproduction in PR #5518 (`tests/core/test_mission_create_coord_status_placement.py`).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Creating a coordination mission keeps the status log off the target branch (Priority: P1)

An operator creates a mission with a coordination topology (`coord` or `lanes_with_coord`) that targets a topic branch. The create commit on the target branch carries the primary-partition scaffold (`meta.json`, `tasks/`) only. The mission's status log (`status.events.jsonl`, holding `MissionCreated` and `SpecifyStarted`) is committed on the mission's coordination branch.

**Why this priority**: The target-branch copy of the status log is what makes the final squash fail with `TARGET_BRANCH_CONTENT_CONFLICT` (#5440). It is a P0 on the 4.0.0 release scope.

**Independent Test**: Create a coord mission through the real create entry point over a real git repository, then read the target branch's tree and the coordination branch's tree.

**Acceptance Scenarios**:

1. **Given** a project on a non-protected topic branch, **When** the operator creates a `coord` mission targeting it, **Then** the target branch's tree has the mission's `meta.json` and no `status.events.jsonl` or `status.json`.
2. **Given** the same create, **When** the coordination branch's tree is read, **Then** it carries the mission's `status.events.jsonl` with exactly one `MissionCreated` and one `SpecifyStarted` event.
3. **Given** the same create, **When** the canonical status surface is resolved for the mission, **Then** it points at the coordination copy of the log.

---

### User Story 2 - Later lifecycle commits keep the status log off the target branch (Priority: P1)

After create, the operator runs the normal lifecycle: setup-plan, finalize-tasks, implement, and lane moves. None of these commits put a status byte-set on the target branch, because the status surface is the coordination worktree from birth.

**Why this priority**: Issue #5440 also reports the `implement` and `accept` legs. Their status writes followed the status surface, which fell back to the primary checkout while the coordination worktree had no mission directory.

**Independent Test**: Drive the lifecycle through the CLI in a temporary project and read the target branch's tree after each step.

**Acceptance Scenarios**:

1. **Given** a freshly created coord mission, **When** setup-plan, finalize-tasks, implement and move-task run, **Then** after each step the target branch carries no `status.events.jsonl` or `status.json` for the mission.
2. **Given** the same lifecycle, **When** the primary checkout's mission directory is listed, **Then** it holds no status log, so accept's primary-residual commit has none to pick up.

---

### User Story 3 - Branch-flat missions are unchanged (Priority: P2)

A `single_branch` or `lanes` mission has no coordination surface. Its status log still lives in the primary mission directory and rides the scaffold commit, as today.

**Why this priority**: Regression guard. These topologies are correct today.

**Independent Test**: Create a `single_branch` mission and read the scaffold commit's tree.

**Acceptance Scenarios**:

1. **Given** a `single_branch` create, **When** the scaffold commit is read, **Then** it carries `meta.json`, `status.events.jsonl` and `tasks/`.

---

### Edge Cases

- The target is protected (`main`), so the target-branch scaffold commit is a disclosed bootstrap skip. The status log is still committed on the coordination branch, because coordination branches are never protected.
- The operator is checked out on a branch other than the target (`SafeCommitHeadMismatch` bootstrap skip). Same as above.
- The target does not resolve to a ref, so the coordination-branch mint is skipped. There is no coordination surface; the status log keeps the primary home and rides the scaffold commit, as today.
- A later create step fails (for example the origin-binding commit). The create rollback removes the coordination worktree before deleting the orphan coordination branch, and carries the status log next to the retained partial scaffold for diagnosis.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Scaffold commit excludes the status log | As an operator creating a coordination mission, I want the target-branch scaffold commit to exclude `status.events.jsonl` so that consolidation never meets a CLI-committed target copy. | High | Open | [build] | no — the PR #5518 reproduction is red on `main` on the same fixture |
| FR-002 | Status log seeded on the coordination branch | As an operator, I want the create to commit the status log (with `MissionCreated` and `SpecifyStarted`) on the coordination branch so that the mission's status has one durable home from birth. | High | Open | [build] | no — asserted on the coordination branch's tree, absent on `main` |
| FR-003 | Status surface resolves to the coordination copy after create | As an agent running later lifecycle commands, I want the canonical status surface to resolve to the coordination copy right after create so that implement, move-task and accept never write the log on the primary checkout. | High | Open | [build] | no — on `main` the surface falls back to primary while the coordination worktree is empty |
| FR-004 | Lifecycle commits keep status off the target | As an operator, I want setup-plan, finalize-tasks, implement and lane moves to leave the target branch without a status byte-set so that the issue's implement and accept legs are closed too. | High | Open | [build] | no — the end-to-end check is red on `main` at the create step |
| FR-005 | Failed create leaves no orphan coordination worktree | As an operator whose create failed late, I want the rollback to remove the coordination worktree and keep the status log next to the retained scaffold so that a retry is not blocked and the diagnosis evidence survives. | Medium | Open | [build] | no — without the change the orphan branch cannot be deleted while checked out |
| FR-007 | Finalize writes lifecycle events to the canonical log | As an operator of a coordination mission, I want `finalize-tasks` to record `TasksStarted`, `WPCreated` and `TasksCompleted` in the status log the surface reads, and to leave no `status.json` in the primary mission dir, so that no stray status byte-set waits in the primary checkout for someone to commit to the target. | High | Open | [build] | no — the lifecycle guard finds both stray files on the same e2e run without the change |
| FR-006 | Branch-flat topologies unchanged | As an operator of a `single_branch` or `lanes` mission, I want the status log to keep riding the scaffold commit so that nothing changes for missions without a coordination surface. | Medium | Open | [ratchet] | yes — paired with FR-001 on the same create fixture, which differs only in topology |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Create cost | A coordination create adds at most one worktree materialization and one commit, both of which the first coordination write already performed before this change. | Performance | Medium | Open |
| NFR-002 | Code quality gates | Changed code passes `ruff check`, `ruff format --check` and `mypy` with zero new findings; every function stays at complexity 15 or below. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Reuse the canonical seams | Placement comes from `routes_through_coordination`, `resolve_placement_only(STATUS_STATE)` and `materialize_coord_surface_for_write`; no new placement authority and no hand-rolled `git worktree add`. | Technical | High | Open |
| C-002 | Stay out of the commit router | `coordination/commit_router.py` and `cli/commands/accept.py` belong to the sibling #5513 remediation (PR #5520) and are not edited here. | Technical | High | Open |
| C-003 | Red-first test stays as written | The PR #5518 reproduction test is adopted unchanged and turns green; it is never skipped, xfailed or weakened. | Technical | High | Open |
| C-004 | No heavy suites in the mission | Validation runs targeted test files only; full architectural, e2e and `test-full` sweeps are left to CI. | Process | Medium | Open |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `tests/core/test_mission_create_coord_status_placement.py` passes on the mission branch and fails on `main`. — [build] · no-op passable: no
- **SC-002**: An end-to-end lifecycle run of a coord mission leaves zero status byte-sets on the target branch after every step, and fails on `main`. — [build] · no-op passable: no
- **SC-003**: The targeted mission-create test files pass, with the re-pinned characterisation tests asserting the new placement per topology. — [ratchet] · no-op passable: no

## Assumptions

- Seeding the status log on the coordination branch at create is the chosen fix (decision recorded in `decisions/`). The alternative, reconciling a target-side copy at consolidate, would keep a COORD-partition kind on the target and was rejected.
- The coordination worktree's mission directory holds only the status log (no `meta.json`), which is the documented shape of the coordination status husk (`tests/integration/coord_topology_fixture.py`).
- Issue #5513 (commit-router silent skip, PR #5520) and the wider `coord-artifact-single-home` scope (#5519, #5501, #2533, #5023) are handled elsewhere.
