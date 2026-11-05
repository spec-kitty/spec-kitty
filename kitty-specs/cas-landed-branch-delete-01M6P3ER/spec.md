# Mission Specification: Compare-and-swap branch delete for `doctor workspaces --prune`

**Mission Branch**: `issue-7212-cas-landed-branch-delete`
**Created**: 2026-11-05
**Status**: Draft
**Input**: Issue #7212, "doctor workspaces --prune: branch delete after the tip check is not compare-and-swap", found by the landing review of #7196 (PR for #7173).

## Intent Summary (confirmed 2026-11-05)

- **Actor:** an operator running `spec-kitty doctor workspaces --prune` in a clone where someone (another agent, another terminal, a background script) may still be working on a branch.
- **Trigger:** the prune has proven a worktree landed, removed it, and is about to delete its local branch.
- **Outcome:** the branch is deleted only while it still points at the tip whose absorption the prune proved. A branch that moves in the window is kept, with its new commit intact, and reported.
- **Invariant:** no path of the prune makes a commit unreachable that was not the assessed, provably-absorbed tip.

### Established intent, before the change

The prune's ordering is deliberate and stays: prove landed → re-assess at the same tip → remove the worktree → delete the branch (`landed_worktrees.py` module docstring, WP03 of the #7173 Mission, `kitty-specs/landed-worktree-cleanup-01M6KZNP/tasks/WP03-landed-assessment-and-prune.md`). The branch cannot be deleted first: git refuses to delete a branch a worktree has checked out. So the order is correct; what is wrong is *where the check lives*. `_delete_landed_branch` reads the tip, compares it, and then calls a delete primitive that reads the tip again and removes it unconditionally (`git branch -D`). No caller-side check can bind a later delete; the check must be the delete. This repository already owns that primitive — `specify_cli.git.ref_advance.delete_branch_ref` (`git update-ref -d <ref> <expected>`) — added for #5570 and reused by the orchestrator-api mission-branch delete (`b37f3f9085`). The landed prune is the third delete site and reintroduced read-then-delete. The wrong side is therefore the **delete primitive**, not the prune's ordering: the fix binds the delete to the assessed tip rather than moving the order.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A branch that moves during the prune survives (Priority: P1)

An operator runs `--prune`. After the prune has re-assessed a landed worktree and read its branch tip, but before the guard deletes the branch, another actor commits to that branch. The prune must not delete the branch: it keeps it, keeps the new commit reachable, and reports the worktree's branch with the existing `BRANCH_MOVED` refusal.

**Why this priority**: This is the data-loss defect the issue records; everything else is supporting.

**Independent Test**: Real-git fixture from the existing prune suite; a wrapper around the guard's delete advances the branch to a fresh commit (one that no other ref reaches, created with `commit-tree`) immediately before delegating to the real guard. Run `prune_landed`; assert the branch still exists at the new tip, the new commit is still reachable, and the outcome reports `BRANCH_MOVED` with `branch_deleted` false.

**Acceptance Scenarios**:

1. **Given** a landed, clean, idle worktree whose branch moves after the prune's tip read and before the guard's delete, **When** `--prune` runs, **Then** the branch is kept at its moved tip, the new commit is reachable, and the outcome carries `BRANCH_MOVED`.
2. **Given** the same fixture with the branch not moving, **When** `--prune` runs, **Then** the branch is deleted (positive control on the same fixture shape: the probe can observe deletion).
3. **Given** a branch moved to a tip whose commits already exist on another local ref, **When** `--prune` runs in the same window, **Then** the branch is kept too (the CAS is unconditional, not only for unique commits).

### User Story 2 - The guard cannot issue an unbound landed delete (Priority: P1)

A future caller of `guarded_branch_delete(..., operator_intent=LANDED_INTENT)` must name the tip it approved. A LANDED delete without an expected tip is refused before anything is touched, so the race cannot be reintroduced by a new call site.

**Why this priority**: The defect returned once already (#5570's CAS exists, and the prune still used `branch -D`). A structural refusal is what keeps it fixed.

**Independent Test**: Call the guard with `LANDED_INTENT` and no expected tip in a real repository; assert `ValueError` and an unchanged branch. Call it with the expected tip; assert the branch is gone. Call it with a moved ref; assert `DestructiveOpRefused` naming the move and an unchanged branch.

**Acceptance Scenarios**:

1. **Given** `guarded_branch_delete(..., operator_intent=LANDED_INTENT)` with no `expected_tip`, **When** it is called, **Then** it raises `ValueError` and the branch is untouched.
2. **Given** the same call with `expected_tip` equal to the branch tip, **When** it is called, **Then** the branch is deleted and its unique tip is recorded under `refs/spec-kitty/discarded/<branch>` first, as today.
3. **Given** the same call with a stale `expected_tip`, **When** it is called, **Then** it raises `DestructiveOpRefused` (a moved-tip code), nothing is deleted, and the branch is still at its moved tip.

### User Story 3 - Every other delete keeps its current behaviour (Priority: P2)

The plain guard path, `--force-recreate` and `mission close --discard` keep deleting exactly as they do today; the prune's report, recreate command and JSON shape are unchanged. A moved branch is still reported as `BRANCH_MOVED`, not a new operator-facing code.

**Why this priority**: The blast radius must stay a safety tightening, not a behaviour change for other commands.

**Independent Test**: The existing guard, routing-gate, prune and CLI suites pass unchanged apart from the new expectation; the prune's JSON keys and `PruneOutcome.refusal` vocabulary are exercised by the existing tests.

**Acceptance Scenarios**:

1. **Given** `guarded_branch_delete` with no operator intent, **When** the branch has unique commits, **Then** it still refuses with `BRANCH_HAS_UNIQUE_COMMITS`; when it has none, it still deletes.
2. **Given** `--force-recreate` and `mission close --discard`, **When** they delete, **Then** nothing about their argv or refusal codes changes.
3. **Given** a prune whose branch moved before the prune's own tip read, **When** it runs, **Then** the outcome is still `BRANCH_MOVED` (the existing fast path), not the guard's internal code.

### Edge Cases

- **The branch is gone before the guard looks at it** (deleted by hand in the window): the delete is a no-op, exactly as today; the outcome reports no branch deletion and no refusal. If it disappears *while* the compare-and-swap runs, the delete is still a no-op (nothing is deleted) and the outcome reports `BRANCH_MOVED`: the branch is no longer at the tip the prune approved.
- **The branch is a symbolic ref** (someone ran `git symbolic-ref refs/heads/<branch> refs/heads/<other>`): only the named ref is deleted; the ref it points at — possibly a checked-out primary branch — is never touched, exactly as `git branch -D` behaved.
- **The branch is checked out in another worktree** in the window: the CAS primitive's own checked-out protection refuses; the prune records `BRANCH_IN_OTHER_WORKTREE`.
- **The delete is refused after the tip was recorded** under `refs/spec-kitty/discarded/<branch>`: the record is create-only and harmless; the branch still holds its own tip, so no commit is lost, and the refusal is reported.
- **A branch moved to a tip that is already on the primary ref**: still kept; the CAS is decided by the ref value, not by reachability.
- **The branch tip is a tag-only commit**: unchanged — the tip is recorded before deletion exactly as today.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | CAS landed branch delete | As an operator, I want the prune's branch delete to succeed only while the branch is at the assessed tip, so that a commit added in the window is never made unreachable. | High | Open | [build] | no |
| FR-002 | Refuse a moved branch inside the delete | As an operator, I want a branch that moves between the tip read and the delete to be kept and reported, so that the race is visible instead of destructive. | High | Open | [build] | no |
| FR-003 | Expected tip is mandatory for LANDED | As a maintainer, I want a LANDED delete without an expected tip refused, so that a future call site cannot reintroduce read-then-delete. | High | Open | [build] | no |
| FR-004 | Other delete intents unchanged | As a maintainer, I want the plain, force-recreate and discard deletes unchanged, so that the fix does not alter other commands. | Medium | Open | [ratchet] | yes — guarded by the existing guard tests on the same fixtures |
| FR-005 | Prune report vocabulary unchanged | As an operator, I want a moved branch reported as `BRANCH_MOVED` with the same JSON shape and recreate command, so that scripts and habits do not change. | Medium | Open | [ratchet] | yes — guarded by the existing prune outcome tests |
| FR-006 | Routing gate pins the expected tip | As a maintainer, I want the destructive-op routing gate to fail if a LANDED caller omits the expected tip, so that the invariant is enforced structurally, not by comment. | Medium | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No new destructive argv owner | The only `update-ref -d` argv remains in the guard-internal modules (`git/ref_advance.py`, `git/destructive_guard.py`); the destructive-op census stays green with zero unexpected sites. | Maintainability | High | Open |
| NFR-002 | Deterministic proof | The red test reproduces the window without sleeps or timing: it forces the ref move inside the guarded delete call, and fails on the pre-fix tree every run. | Reliability | High | Open |
| NFR-003 | Bounded cost per branch | The prune's branch delete issues at most two more git invocations per pruned branch than the read-then-`branch -D` path (one tip re-read for the bound refusal, one worktree scan replacing the checked-out protection `update-ref -d` bypasses); it adds no network access and no per-worktree loop. | Performance | Low | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Stacked base | `src/specify_cli/workspace/landed_worktrees.py` and the guard extensions exist only on the open #7196 branch, so this Mission branches from `issue-7173-landed-worktree-cleanup` and its PR targets that branch until it lands. | Technical | High | Open |
| C-002 | Reuse the owned primitive | The CAS delete reuses `specify_cli.git.ref_advance.delete_branch_ref`; no second `update-ref -d` implementation is added. | Technical | High | Open |
| C-003 | Guard refusal is typed | Every refusal leaves the guard as `DestructiveOpRefused` with an error code; no raw `subprocess`/`GitCommandError` escapes to the prune for an expected race. | Technical | High | Open |
| C-004 | Never merge | The Mission stops at a green, ready-for-review PR; the operator merges by hand. | Business | High | Open |

### Key Entities

- **WorktreeVerdict / PruneOutcome**: unchanged shapes; `PruneOutcome.refusal` carries `BRANCH_MOVED` for both the pre-read fast path and the in-delete refusal.
- **Expected tip**: the assessed `verdict.tip` — the commit whose absorption into `origin/<primary>` the prune proved. It is the compare-and-swap old value.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A deterministic real-git test moves the branch between the prune's tip read and the guard's delete and observes the branch retained at the moved tip with `BRANCH_MOVED`; the same test deletes the branch when it does not move (positive control). — [build] · no-op passable: no
- **SC-002**: The guard refuses a LANDED delete with no expected tip (`ValueError`, branch unchanged) and with a stale one (`DestructiveOpRefused`, branch unchanged). — [build] · no-op passable: no
- **SC-003**: The destructive-op routing gate fails when the landed caller omits the expected tip, and passes on the shipped tree. — [build] · no-op passable: no
- **SC-004**: The existing landed-worktree, guard, routing-gate and prune CLI suites pass with no change to other callers or to the operator-facing vocabulary. — [ratchet] · no-op passable: yes — paired with the new-behaviour rows above on the same suites
