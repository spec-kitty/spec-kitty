# Mission Specification: Coordination Doctor Branch Safety

**Mission Branch**: `issue-4920-coordination-doctor-branch-safety`
**Created**: 2026-09-22
**Status**: Verified
**Input**: GitHub issue #4920 and the operator request to document and resolve the
release-blocking coordination-doctor failure.

## User Scenarios & Testing

### User Story 1 - Refuse the wrong coordination branch (Priority: P1)

As a Spec Kitty operator, I want `doctor coordination --fix` to refuse a repair when
the recorded coordination worktree is not checked out on the declared coordination
branch, so the command cannot silently mutate an unrelated branch.

**Why this priority**: The former behavior corrupted branch intent, left the actual
coordination branch stale, reported success, and exited 0. This was a release-blocking
data-integrity failure.

**Independent Test**: In a real Git repository, make the declared coordination branch
a strict ancestor of the target, register a worktree path that has another branch
checked out, invoke the repair, and compare every involved ref before and after.

**Acceptance Scenarios**:

1. **Given** a stale declared coordination branch and a clean recorded worktree on a
   different branch, **When** `doctor coordination --fix` runs, **Then** it exits 1,
   emits a structured blocked-fix error naming the branch mismatch, mutates no branch,
   and does not print `Fast-forwarded`.
2. **Given** the recorded worktree is detached, **When** the repair runs, **Then** it
   fails closed under the same no-mutation contract.

---

### User Story 2 - Preserve the valid fast-forward (Priority: P1)

As a Spec Kitty operator, I want the repair to continue fast-forwarding a clean
coordination worktree that is checked out on the declared coordination branch, so the
safe recovery remains available.

**Why this priority**: Preventing corruption must not disable the command's intended
recovery path.

**Independent Test**: In a real Git repository, invoke the repair with the correct
coordination branch checked out and prove both worktree `HEAD` and the declared ref end
at the target SHA.

**Acceptance Scenarios**:

1. **Given** the declared coordination ref is a strict ancestor of the target and its
   clean worktree is checked out on that ref, **When** the repair runs, **Then** it exits
   0, advances the declared ref to the target SHA, and prints `Fast-forwarded` only
   after verifying that postcondition.

### Edge Cases

- An unreadable or detached symbolic `HEAD` is treated as a mismatch and is never
  mutated.
- A dirty correct-branch worktree retains the existing blocked-fix behavior.
- Diverged refs retain the existing blocked-fix behavior and unified diff.
- One mission's blocked repair does not prevent safe, unrelated mission fixes in the
  same command run.

## Requirements

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Validate worktree branch identity | As an operator, I want the repair to verify symbolic `HEAD` equals the declared coordination branch before mutation. | High | Verified |
| FR-002 | Block mismatched repairs | As an operator, I want a mismatch or detached `HEAD` to return a structured error and non-zero command result without mutating any ref. | High | Verified |
| FR-003 | Truthful success | As an operator, I want `Fast-forwarded` printed only after the declared coordination ref is verified at the target SHA. | High | Verified |
| FR-004 | Preserve safe recovery | As an operator, I want a clean, correct-branch, strict-ancestor worktree to keep fast-forwarding normally. | High | Verified |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Zero unintended mutation | For every blocked branch-identity case, all involved ref SHAs are byte-for-byte unchanged after the command. | Reliability | High | Verified |
| NFR-002 | Stable machine contract | The blocked repair uses a stable error code and exits 1 through the existing finding aggregation path. | Compatibility | High | Verified |
| NFR-003 | Focused regression coverage | Real-git acceptance coverage exercises both wrong-branch refusal and the existing correct-branch control; all owning-subsystem tests pass. | Quality | High | Verified |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Canonical branch check | Reuse `_coord_worktree_head_finding`; do not add a second symbolic-HEAD authority. | Architecture | High | Verified |
| C-002 | Minimized repair scope | Do not switch branches, reset refs, discard user changes, or expand `--fix` into general drift repair. | Safety | High | Verified |
| C-003 | Continue other missions | A blocked repair returns a finding rather than aborting the whole multi-mission fix loop. | Reliability | High | Verified |

### Key Entities

- **Declared coordination ref**: The only branch that this repair is authorized to
  advance.
- **Recorded coordination worktree**: The worktree path resolved for the mission; its
  symbolic `HEAD` must match the declared ref.
- **Target ref**: The desired fast-forward destination.
- **Blocked-fix finding**: The structured error that preserves no-mutation and
  cross-mission continuation semantics.

## Success Criteria

### Measurable Outcomes

- **SC-001**: The issue #4920 real-git regression exits 1 and leaves the declared
  coordination branch, wrong checked-out branch, and target branch at their original
  SHAs.
- **SC-002**: The regression output contains the blocked-fix error and branch mismatch,
  with zero `Fast-forwarded` messages.
- **SC-003**: The correct-branch control exits 0 and ends with the declared coordination
  ref exactly equal to the target SHA.
- **SC-004**: The focused file passes 30 tests, the owning coordination suite passes
  183 tests, and targeted Ruff lint and strict MyPy pass. Shared baseline failures are
  confirmed pre-existing and recorded on #4873 and #4506.
