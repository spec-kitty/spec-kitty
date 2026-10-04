# Mission Specification: single_branch implement/review loop + commit-message hygiene

**Mission Branch**: `ccr-ba04d8aa-fx98ee`
**Created**: 2026-10-04
**Status**: Draft
**Input**: Issues #5459, #5655, #5647, #5648

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Agent claim on a single_branch mission is guarded (Priority: P1)

An agent runs `spec-kitty agent action implement WP01` on a `single_branch` mission. The claim records a claim base, so `move-task --to for_review` passes after a real commit, without `--force`. A second claim into a busy or dirty write checkout is refused, as `spec-kitty implement` already refuses it.

**Why this priority**: Release blocker (#5459). Every agent-driven single_branch mission needs `--force` to reach review, and the one-writer refusals are bypassed with exit 0.

**Independent Test**: The #5459 reproducer exits 0.

**Acceptance Scenarios**:

1. **Given** a single_branch mission, **When** `agent action implement WP01` runs, **Then** a claim-base ref exists for WP01.
2. **Given** WP01 `in_progress` in the write checkout, **When** `agent action implement WP02` runs, **Then** it refuses with `WRITE_CHECKOUT_OCCUPIED` and WP02 stays `planned`.
3. **Given** uncommitted operator edits and no WP in progress, **When** `agent action implement WP01` runs, **Then** it refuses with `WRITE_CHECKOUT_DIRTY`.
4. **Given** WP01 already `in_progress` with uncommitted work, **When** `agent action implement WP01` runs again, **Then** it resumes (no refusal, claim base unchanged).

### User Story 2 - Status mutations on single_branch commit themselves (Priority: P1)

`mark-status` and `move-task` on a single_branch mission commit the status files they write, so the write checkout is clean afterwards.

**Why this priority**: Release blocker (#5655). Left-over status files make a later `move-task` refuse, and the status surface drifts from HEAD.

**Independent Test**: After `mark-status` and after `move-task --to for_review`, `git status --porcelain` is empty.

**Acceptance Scenarios**:

1. **Given** a claimed single_branch WP, **When** `mark-status T01 --status done` runs, **Then** `status.events.jsonl` / `status.json` are committed.
2. **Given** a single_branch WP ready for review, **When** `move-task --to for_review` runs, **Then** no status file is left modified (including the implementer-identity annotation).

### User Story 3 - Repeated `-m` builds a multi-paragraph message (Priority: P2)

`spec-kitty safe-commit` / `spec-commit` accept `-m` several times and join the values with blank lines, as `git commit` does (#5647).

**Acceptance Scenarios**:

1. **Given** `-m "subject" -m "Co-Authored-By: X <x@y>"`, **When** safe-commit runs, **Then** the commit message is `subject\n\nCo-Authored-By: X <x@y>`.

### User Story 4 - The gate-mechanics doc names the supported writer (Priority: P3)

`docs/development/reference/ci-gate-mechanics.md` points to `spec-kitty agent acceptance-verdict` (including negative-invariant mode) instead of hand-editing `acceptance-matrix.json` (#5648).

### Edge Cases

- Resume of the same WP in a dirty checkout stays allowed.
- Lanes/coord missions keep their current claim path (the repo-root guard is single_branch-only).
- Flat/legacy missions keep uncommitted annotations (unchanged).

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Action-implement records the claim base | As an agent, I want `agent action implement` to record the claim base on single_branch so that for_review passes without --force. | High | Open | [build] | no — reproducer asserts the ref exists |
| FR-002 | Action-implement enforces write-checkout refusals | As an operator, I want OCCUPIED/DIRTY/WRONG_BRANCH refusals on the agent path so that one checkout has one writer. | High | Open | [build] | no — paired with the resume positive control |
| FR-003 | Status annotations commit on single_branch | As an operator, I want mark-status and move-task annotations committed on single_branch so that the checkout stays clean. | High | Open | [build] | no — asserts clean porcelain |
| FR-004 | Repeated -m joins paragraphs | As an agent, I want repeated `-m` joined with blank lines so that subject+trailer commits keep the subject. | Medium | Open | [build] | no — asserts the full message |
| FR-005 | Doc names acceptance-verdict | As an operator, I want the doc to name the supported writer so that I do not hand-edit the matrix. | Low | Open | [build] | no — doc text check |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No regression on other topologies | Existing lanes/coord claim and status tests pass unchanged (0 new failures). | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | One guard authority | Reuse `_ensure_repo_root_checkout_available` + `record_claim_base`; no second copy of the refusal order. | Technical | High | Open |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The #5459 reproducer exits 0 on this branch — [build] · no-op passable: no
- **SC-002**: A single_branch mark-status + move-task cycle leaves `git status --porcelain` empty — [build] · no-op passable: no
