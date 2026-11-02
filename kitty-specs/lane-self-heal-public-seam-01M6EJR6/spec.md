# Mission Specification: Lane self-heal public seam (#6898)

**Mission Branch**: `issue-6898-lane-self-heal-public-seam`
**Created**: 2026-11-02
**Status**: Draft
**Input**: Issue #6898 — "lanes: `reenter_lane_self_heal` reaches into allocator privates instead of a public lane self-heal seam" (found by the #6745 workaround audit, research §4 row S5).
**Guidance**: One issue, one seam. No behaviour change is in scope: `reenter_lane_self_heal`'s
observable contract (a code-lane re-entry tolerates an agent's uncommitted work-in-progress; a
planning-lane re-entry refuses a dirty or protected repository-root checkout) must stay exactly
as it is. The fix is a move of authority, not a change of policy.

## Problem Statement

`specify_cli/lanes/implement_support.py::reenter_lane_self_heal` performs the two-step
"make this reused lane worktree current" operation — merge the recorded finalize-tasks planning
commit, then merge each fully approved dependency lane tip — by importing three **private**
helpers from `specify_cli/lanes/worktree_allocator.py`:

```python
from specify_cli.lanes.worktree_allocator import (
    _merge_dependency_lane_tips,
    _merge_recorded_planning_commit,
    _validate_worktree_clean,
)
```

Two authorities therefore exist for the same decision: the allocator's own reuse /
crash-recovery / fresh routes perform the same two merges inline, and this caller-side re-entry
does it again from outside. They can drift on the merge **ordering**, on the clean-worktree
**pre-condition**, and on what is recorded afterwards. A private-name import is also invisible
to the allocator's own review surface: renaming or reordering those helpers breaks a caller in
another package at runtime rather than at the seam.

The workaround exists for a real reason — `allocate_lane_worktree()` additionally runs
`_validate_worktree_clean`, which is a *different* concern (guarding a NEW WP against a dirty
worktree left by a previous WP in the same lane) and which a retry self-heal for the SAME
in-flight WP must not inherit. The fix keeps that distinction but moves the *decision* inside
the allocator, where it can be documented and reviewed, instead of encoding it as an import of
internals from outside.

## Grounding (existing code survey)

- `src/specify_cli/lanes/worktree_allocator.py` (2 069 lines) — the same two merges run inline
  at four sites: REUSE (`~:1123`), CRASH_RECOVERY (`~:1189`), FRESH_COORD / FRESH_LEGACY
  (`~:1319`), and `implement_support.reenter_lane_self_heal` (`~:684`).
- `reenter_lane_self_heal` also threads `capture_branch_tip(repo_root, manifest.target_branch)`
  by hand; the allocator captures the same tip once per allocation (`~:1065`). That is a third
  duplicated decision the seam can own.
- The `reenter_lane_self_heal` docstring already explains, at length, why the re-entry is not
  simply `allocate_lane_worktree()`. That rationale is the documentation the seam must carry.
- Structural-gate precedent: `tests/architectural/test_lane_allocation_single_seam.py` polices
  the *parent-ref* seam with an AST guard plus self-mutation fixtures. This mission's gate
  follows the same shape for the *adoption* seam.
- Behavioural coverage that must stay green: `tests/lanes/test_planning_claim_self_heal.py`
  (planning lane merges the approved dependency; protected root refused without mutation; dirty
  root refused without losing work), `tests/lanes/test_lane_tip_record_points.py` (M4 code-lane
  re-entry records the tip), `tests/agent/test_agent_action_lane_context_refresh.py`.

## User Scenarios & Testing

### User Story 1 - One public seam owns "adopt the recorded planning commit and the approved dependency tips" (Priority: P1)

As a maintainer of the lane allocator, I want the "make a reused lane worktree current"
operation to be a single public seam of the allocator, with the clean-worktree policy an
explicit parameter of that seam, so that the allocator's own routes and a caller-side self-heal
re-entry cannot drift on ordering or on the pre-condition, and a rename of an internal helper
cannot break another package at runtime.

**Why this priority**: it is the whole of the issue. Without it, the defect class (a second
entry into allocator internals standing in for a seam) stays open and the next self-heal caller
copies the import again.

**Independent Test**: the structural gate fails on `origin/main` (private-name import present,
no public seam defined, the allocator's own routes do not call the seam) and passes after the
change; the allocator's module exposes the seam and every adoption site goes through it.

**Acceptance Scenarios**:

1. **Given** the allocator module on `main`, **When** the structural gate runs, **Then** it
   reports (a) an external import of an adoption helper, (b) no `adopt_lane_ancestry` symbol,
   and (c) fewer than three allocator-route call sites — so the gate is genuinely red-first.
2. **Given** the seam, **When** a caller passes `clean_worktree_policy="refuse-dirty"` and the
   worktree has uncommitted changes, **Then** the seam raises the allocator's own
   `DirtyWorktreeError` before any merge, naming the lane.
3. **Given** the seam, **When** a caller passes `clean_worktree_policy="allow-dirty"` and the
   recorded planning commit is not yet an ancestor, **Then** the seam merges it anyway and the
   planning commit becomes an ancestor of the worktree HEAD.

### User Story 2 - `reenter_lane_self_heal` keeps its behaviour through the seam (Priority: P1)

As an operator re-entering an in-flight work package, I want the self-heal to keep working
exactly as it does today — my uncommitted work-in-progress is not destroyed or refused, the
approved dependency lane's code and the recorded planning commit are merged, and a protected or
dirty planning-lane repository root is still refused before anything mutates — so that a
refactor does not turn a working retry into a hard failure.

**Why this priority**: the seam change touches the code path every `spec-kitty agent action
implement` retry runs; a silent policy change here corrupts agent work.

**Independent Test**: the existing self-heal suite (`tests/lanes/test_planning_claim_self_heal.py`,
`tests/lanes/test_lane_tip_record_points.py`) stays green with no test edits, and a new test
proves the dirty code-lane re-entry still merges (i.e. the permissive policy is still the one the
code lane gets).

**Acceptance Scenarios**:

1. **Given** a code-lane worktree mid-WP with an uncommitted file, **When** `reenter_lane_self_heal`
   runs and the recorded planning commit is missing from HEAD, **Then** the merge happens, the
   uncommitted file is untouched, and `reenter_lane_self_heal` returns the worktree path.
2. **Given** a planning-lane repository root that is protected or dirty, **When**
   `reenter_lane_self_heal` runs, **Then** it raises before any merge, exactly as today
   (`ProtectedBranchCommitError` / `DirtyWorktreeError`), with no mutation.
3. **Given** a workspace whose ancestry is already correct, **When** the self-heal runs twice,
   **Then** HEAD is unchanged after the second call (idempotent no-op, #1832/#1833).

### Edge Cases

- A mission with no `lanes.json`, a WP in no lane, or a not-yet-materialized workspace: the
  self-heal still returns `None` and the seam is never reached.
- A `lanes.json` with no `planning_commit_sha` and no `depends_on_lanes`: the seam short-circuits
  on the helpers' own no-op checks (unchanged).
- A planning lane whose dependency tips are only partially approved: the self-heal keeps merging
  only the fully approved tips (the existing filtered-lane substitution), so the seam must
  receive the same filtered lane.
- A genuine merge conflict: it still propagates as the allocator's structured exceptions
  (`PlanningCommitMergeConflictError`, `DependencyLaneMergeConflictError`); no swallowing.

## Requirements

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Public adoption seam | As an allocator maintainer, I want one public `adopt_lane_ancestry()` seam that merges the recorded planning commit and then the approved dependency lane tips, so that the "make this lane current" operation has a single owner. | High | Open | [build] | no — the seam must exist and be called, so an empty implementation cannot pass |
| FR-002 | Explicit clean-worktree policy | As an allocator maintainer, I want the clean-worktree precondition of FR-001's seam to be a required, documented argument (`refuse-dirty` / `allow-dirty`, no default, and any other value refused with `ValueError`), so that the tolerance decision is reviewed inside the allocator instead of implied by which private helper a caller imports. | High | Open | [build] | no — a default that silently permits dirty worktrees is refused by the gate |
| FR-003 | Target-tip capture owned by the seam | As an allocator maintainer, I want the seam to capture the planning target tip itself when the caller does not supply one, so that a caller can no longer pass a lane HEAD where the target tip belongs. | Medium | Open | [build] | no — the seam must capture from `lanes_manifest.target_branch` when `target_tip` is `None` |
| FR-004 | Allocator routes adopt the seam | As an allocator maintainer, I want the REUSE, CRASH_RECOVERY and FRESH allocation routes to call the seam rather than repeating the two merges inline, so that ordering cannot drift between routes. | High | Open | [build] | no — the gate requires at least the three route call sites |
| FR-005 | No external import of adoption internals | As a reviewer, I want a non-vacuous structural gate that fails when a module outside `worktree_allocator.py` imports `_merge_recorded_planning_commit`, `_merge_dependency_lane_tips` or `_validate_worktree_clean`, so that the second-entry defect class cannot return. | High | Open | [ratchet] | no — the gate is red on `main` and must be green after |
| FR-006 | Behaviour preserved | As an operator, I want `reenter_lane_self_heal` to keep exactly its current observable behaviour (dirty code lane tolerated, dirty/protected planning root refused, idempotent no-op, `None` for nothing-to-heal), so that the refactor cannot corrupt in-flight agent work. | High | Open | [build] | no — the dirty-code-lane merge and the two refusals are asserted directly |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No extra git work on the self-heal path | `reenter_lane_self_heal` performs no more `git` subprocess calls per call than on `main` (the target-tip capture it already makes moves into the seam; no new probe is added). | Performance | High | Open |
| NFR-002 | Typed and documented seam | `mypy --strict` passes and the seam carries a docstring naming both policies and the ordering guarantee. | Maintainability | High | Open |
| NFR-003 | Changed-line coverage | Diff coverage on changed lines is at least 90 percent (the CI `diff-cover` gate). | Testability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No policy change | No new refusal and no new permissiveness: the code lane keeps `allow-dirty`, the planning lane keeps `refuse-dirty` plus its protected-branch guard. | Technical | High | Open |
| C-002 | Single authority | The merge ordering and the clean-worktree decision live in `worktree_allocator.py`; `implement_support.py` keeps no copy of either. | Technical | High | Open |
| C-003 | Scoped test surface | Only the lane/agent/architectural files the change implicates are run locally; no full `tests/architectural/`, e2e or `make test-full` sweep (`NO_FULL_HEAVY_SUITES_IN_MISSION`). Owned by WP01/T007's named verification set. | Process | High | Open |
| C-004 | Changelog shape | A per-PR fragment `docs/changelog/unreleased/<pr>.internal.md` (tech-debt, not user-facing); no edit to `docs/changelog/CHANGELOG.md`. Owned by WP01/T007. | Process | Medium | Open |
| C-005 | Gate scope honesty | The structural gate polices the adoption trio named in the issue; it does not claim to police every private helper in the module (other private imports such as `_read_coordination_branch` are out of scope and are not silently baselined). | Technical | Medium | Open |

### Key Entities

- **Adoption seam**: the allocator's public entry point that makes a lane worktree current
  (recorded planning commit, then approved dependency lane tips), parameterised by the
  clean-worktree policy.
- **Clean-worktree policy**: `refuse-dirty` (allocator-owned disposable lane checkouts, planning
  root reconciliation) vs `allow-dirty` (re-entry of an in-flight code lane, where the agent's
  WIP is legitimate and git's own merge machinery is the only correct gate).

## Success Criteria

### Measurable Outcomes

- **SC-001**: The structural gate is red on `origin/main` and green on the mission head, with a self-mutation fixture proving it fires on a synthetic external import — [ratchet] · no-op passable: no
- **SC-002**: Zero private-name imports of the adoption trio remain outside `worktree_allocator.py` (`grep` count 0, asserted by the gate) — [build] · no-op passable: no
- **SC-003**: The existing self-heal, lane-tip and lane-context test files pass unmodified — [build] · no-op passable: no
- **SC-004**: `reenter_lane_self_heal` on a dirty code-lane worktree still merges the recorded planning commit and leaves the dirty file untouched (new assertion) — [build] · no-op passable: no
