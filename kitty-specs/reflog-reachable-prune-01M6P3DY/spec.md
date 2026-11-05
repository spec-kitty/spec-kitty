# Mission Specification: Prune keeps commits that only a reflog still reached

**Mission Branch**: `issue-7211-reflog-reachable-prune`
**Created**: 2026-11-05
**Status**: Draft
**Input**: User description: "Issue #7211 — `doctor workspaces --prune` drops commits reachable only from the worktree's HEAD reflog or the branch reflog. Treat the reachability rule as the subject; prove the fix with a test that would have caught the dropped commits."

## Problem

`spec-kitty doctor workspaces --prune` removes a landed worktree and deletes its branch. Two records of a commit disappear with them: `git worktree remove` deletes `.git/worktrees/<id>/logs/HEAD`, and `git branch -D` deletes the branch reflog. A commit made while the worktree was detached, and later left behind, or one dropped by `git reset --hard` on the branch, is then reached by no ref and by no reflog. The next `git gc` may collect it, and the prune prints nothing about it.

The landed proof covers the branch tip only: a tip whose commits exist on no other ref is recorded under `refs/spec-kitty/discarded/<branch>` (or `.../detached/<sha>`), but commits behind that tip that the reflog alone still reached are not.

## The rule this mission states

> Before the prune destroys a reflog, every commit that reflog reached is reachable from a ref afterwards, or it is provably still on the primary ref by patch.

"Provably still on the primary ref by patch" is the one deliberate narrowing, and it exists for a concrete reason: this repository lands by rebase, so a landed branch's reflog holds the pre-rebase commits, whose patches are on `origin/main` under the rebased shas. Recording a kept ref for each of those would add a ref per superseded commit on every landing and pin those objects forever, while preserving no content that is not already preserved. Any commit whose patch is not demonstrably on the primary ref — including merges, unreadable cases and errors — is recorded. The check therefore never decides to *drop* a commit it cannot prove; it only declines to duplicate one it can.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A worktree's detached-only commit survives the prune (Priority: P1)

An operator works detached in a task worktree, commits, switches the worktree back to its branch, and later runs `spec-kitty doctor workspaces --prune`. The commit made while detached is on no branch. Today it disappears with the worktree's HEAD reflog. After this mission the prune records it under `refs/spec-kitty/discarded/reflog/<sha>` before removing anything, and says so.

**Why this priority**: This is the reported data-loss path and the only one that silently loses unique content.

**Independent Test**: Build the reproduction from the issue in a scratch repository, run the prune through the CLI, then assert the detached commit is reachable from a ref, survives `git gc --prune=now`, and is named in the prune output.

**Acceptance Scenarios**:

1. **Given** a landed worktree whose HEAD reflog reaches a commit that no branch, tag or remote-tracking ref reaches, **When** `doctor workspaces --prune` removes it, **Then** a create-only ref under `refs/spec-kitty/discarded/reflog/` holds that commit, and `git gc --prune=now` keeps it readable.
2. **Given** the same worktree, **When** the prune reports, **Then** the outcome names the kept ref in text and in `--json`.

### User Story 2 - A branch reflog commit dropped by a reset survives the prune (Priority: P1)

An operator commits on a branch, `git reset --hard`s it back, and the branch lands anyway. The dropped commit exists only in the branch reflog. The prune deletes the branch and its reflog; the commit must not become unreachable.

**Why this priority**: The second reflog the issue names, and the one the branch delete destroys.

**Independent Test**: Reset the branch behind its landed tip, prune, assert the reset-away commit is reachable from a kept ref and survives `git gc --prune=now`.

**Acceptance Scenarios**:

1. **Given** a landed branch whose reflog reaches a commit no ref reaches, **When** the prune deletes the branch, **Then** that commit is held by a `refs/spec-kitty/discarded/reflog/` ref written before the delete.
2. **Given** a landing branch that was rebased onto the primary, **When** the prune runs, **Then** no kept ref appears for its pre-rebase commits, because their patches are on the primary ref.

### User Story 3 - A record that cannot be written removes nothing (Priority: P2)

**Why this priority**: The guard's existing contract for a detached tip: a failed record is a refusal, not a partial removal.

**Independent Test**: Make the ref write fail in a test double and assert the worktree and branch are still there, with the guard's refusal code.

**Acceptance Scenarios**:

1. **Given** a reflog-only commit that must be recorded, **When** the record cannot be written, **Then** the outcome is a refusal carrying the guard's error code and nothing is removed.

### Edge Cases

- The branch has no reflog (`git reflog show` exits non-zero): it contributes no candidates; the worktree HEAD reflog is still read.
- The worktree has no HEAD reflog (git may not keep one for a never-moved HEAD): no candidates from it; the branch reflog is still read.
- A candidate is a merge commit: `git cherry` reports nothing for it, which is treated as "not provably on the primary", so it is recorded.
- A candidate is already reachable from another ref once the worktree and branch are gone: nothing is recorded for it.
- The same reflog-only commit is seen twice (both reflogs): one ref is written, because the write is create-only and idempotent.
- A prune of a normal rebase landing: no kept ref, no behaviour change beyond the reflog read.
- The primary ref is unresolved: the prune does not reach these worktrees (the assessment returns `unproven`), so nothing is recorded.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Record reflog-only commits before removal | As an operator, I want every commit that only a worktree HEAD reflog or a branch reflog still reached to be held by a ref before the prune destroys those reflogs, so that `git gc` cannot collect it. | High | Open | [build] | no |
| FR-002 | Candidates come from both reflogs, read first | As an operator, I want the candidate set read from the worktree HEAD reflog and the branch reflog before anything is removed or deleted, so that a crashed prune cannot leave a commit unrecorded. | High | Open | [build] | no |
| FR-003 | Keep only the reflog shas no ref reaches | As an operator, I want only commits that no ref reaches recorded, so that the prune does not create a ref for work another ref still holds. The test is the issue's own: `rev-list <shas> --not --all`, intersected with the candidate entries. | High | Open | [build] | no |
| FR-004 | Patch-equivalent commits are not recorded | As an operator, I want a commit whose patch is already on the primary ref not recorded, so that a rebase landing does not add a kept ref per superseded commit, and any commit whose content cannot be proven present recorded — including a merge, whose own resolution no patch carries, even when every non-merge commit between the primary and it reads patch-equivalent. | High | Open | [build] | no |
| FR-005 | A failed record refuses the removal | As an operator, I want the prune to remove nothing when it cannot record a reflog-only commit, so that safety never degrades to a silent loss. | High | Open | [build] | no |
| FR-006 | The outcome names the kept refs | As an operator, I want the prune outcome to name each kept reflog ref in text and in `--json`, so that I can find and restore the work. | Medium | Open | [build] | no |
| FR-007 | A normal rebase landing keeps nothing extra | As a maintainer, I want a landed rebase branch to still prune with no kept ref, so that the fix costs the common case nothing. | Medium | Open | [ratchet] | yes — positive control is FR-001/SC-001: the same fixture records a ref only for the commit with no patch on the primary |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No remote contact | The prune issues no network operation in any reflog or patch check; a test runs it against a repository with no remote configured and asserts success. | Reliability | High | Open |
| NFR-002 | Bounded git invocations | At most one `rev-list` for reachability and at most two git checks per unreachable candidate (a merge probe and `git cherry`); a fixture with N candidates is pruned with fewer than 4 + 2N git processes beyond the existing prune. | Performance | Medium | Open |
| NFR-003 | Additive JSON | Every existing key of the `pruned[]` entries keeps its name and meaning; the new key is additive, and the whole payload stays valid JSON for a caller that ignores it. | Compatibility | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | The landing proof is unchanged | The prune removes only worktrees the existing rule calls `landed`; this mission adds a record step and never relaxes a verdict, a guard or a gate. | Technical | High | Open |
| C-002 | The record is create-only | Kept refs are written with the guard's create-only bookkeeping write, never moving an existing ref, and re-running the prune is idempotent. | Technical | High | Open |
| C-003 | Stacked on #7196 | The pruner exists only on the unmerged, green PR #7196; this branch is stacked on its head and the PR targets that branch, retargeting to `main` when #7196 lands. | Business | High | Open |

### Key Entities

- **Reflog-only commit**: A commit reached by a worktree HEAD reflog or a branch reflog at prune time, and by no ref once that worktree and branch are gone, whose patch is not on the primary ref.
- **Kept reflog ref**: `refs/spec-kitty/discarded/reflog/<sha>`, create-only, written before the worktree removal, naming one reflog-only commit.
- **Prune outcome**: The existing per-worktree record (`PruneOutcome`) that gains the list of kept reflog refs.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The issue's reproduction — a detached commit reachable only from a worktree HEAD reflog, its landed branch, then `doctor workspaces --prune` — leaves that commit reachable from a ref and readable after `git gc --prune=now`, asserted through the CLI entry point. — [build] · no-op passable: no
- **SC-002**: The same assertion holds for a commit reachable only from the branch reflog after a `reset --hard` behind a landed tip. — [build] · no-op passable: no
- **SC-003**: A rebased landing branch with three pre-rebase commits prunes with zero kept reflog refs, and `git for-each-ref refs/spec-kitty/discarded/reflog` is empty afterwards. — [ratchet] · no-op passable: yes (positive control: SC-001/SC-002 on the same fixture family record exactly the commits with no patch on the primary)
- **SC-004**: With the record step disabled (its write forced to fail), the prune refuses, the worktree and branch still exist, and the outcome carries the guard's error code — a test that fails if the write is not load-bearing. — [build] · no-op passable: no
- **SC-005**: `git cat-file -e` and `git for-each-ref --contains` prove reachability from a ref, not from a reflog, in every test above; no test asserts on a reflog after the prune. — [ratchet] · no-op passable: no
