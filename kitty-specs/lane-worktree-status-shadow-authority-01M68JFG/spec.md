# Mission Specification: Lane worktree status shadow authority

**Mission Branch**: `issue-6466-lane-status-shadow`
**Created**: 2026-10-31
**Status**: Draft
**Input**: GitHub issue spec-kitty/spec-kitty#6466 — "Lane-worktree vs root/mission-branch status.json divergence forces unnecessary --force on routine transitions"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A lane worktree can never answer a status read from its stale copy (Priority: P1)

An operator finishes a work package inside its lane worktree and drives the transition from
wherever they are — the repository root, the lane worktree, or a script that hands the lane
worktree path to spec-kitty as its repository root. Whichever checkout they stand in, the
status read answers from the mission's authoritative status surface (the coordination husk on
a coordination-routed mission, the primary/mission-branch copy on a branch-flat mission), so a
genuine `in_progress` work package is never reported as `planned` and the routine
`for_review` transition never needs `--force`.

**Why this priority**: The reported defect is exactly this: a stale per-checkout copy answers a
status read, the work package looks like it never started, and the operator's only escape is the
`--force` hatch reserved for genuine process exceptions — which then pollutes the mission's audit
trail and retrospective signal.

**Independent Test**: Build a `lanes` mission with a lane worktree, record a status transition
after the worktree exists, then read the work package's lane with the lane worktree root handed
in as the repository root. The read returns the authoritative lane; before the fix it returns the
fork-time lane from the lane worktree's stale copy.

**Acceptance Scenarios**:

1. **Given** a `lanes` mission whose lane worktree was cut before a `planned -> in_progress`
   transition, **When** a status read is anchored at the lane worktree root, **Then** it reports
   `in_progress` (the primary/mission-branch surface), not the lane copy's `planned`.
2. **Given** the same mission, **When** the operator moves the work package to `for_review` from
   the repository root after committing the lane work, **Then** the move succeeds without
   `--force`.
3. **Given** a coordination-routed mission (`lanes_with_coord`), **When** the lane worktree root
   is handed in as the repository root, **Then** the read still resolves the coordination husk —
   the coordination authority is not displaced by this change.

---

### Edge Cases

- The given root is the coordination worktree itself: it stays the authority (it is a registered
  coord worktree, not a lane worktree) — no re-anchoring.
- The given root is an independent clone of the repository: it is not a *linked* worktree of the
  mission's repository, so it keeps answering from its own checkout (its own clone's copy is the
  authority there).
- The given root is an unregistered husk under `.worktrees/`: not a registered lane worktree, so
  the existing husk behaviour is unchanged.
- The repository has no git registry available: the classification fails closed as today; the
  read path never guesses.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Lane worktree root is not a status surface | As an operator, I want a status read anchored at a lane worktree root to answer from the mission's authoritative status surface, so that a stale fork-time copy can never report the wrong lane. | High | Open | [build] | no — the paired same-fixture control reads the authoritative surface while the red leg reads the lane shadow, so a no-op fix fails the red leg |
| FR-002 | Coordination authority is preserved | As an operator on a coordination-routed mission, I want a lane-worktree-rooted read to keep resolving the coordination husk, so that this fix never re-introduces a primary stale read. | High | Open | [ratchet] | yes — the no-op passes only because the coord path already resolves today; the row exists to hold the boundary |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | One resolution authority | The re-anchoring is expressed once, in the guarded read-side seam, and consumes the existing worktree-topology classifier; no second lane-detection predicate and no new git shell-out per read. | Maintainability | High | Open |
| NFR-002 | Fail-closed on registry failure | When the worktree registry cannot be read the read path behaves exactly as before (the classified topology's fail-closed behaviour), never guessing a root. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|--------|--------|
| C-001 | No newest-timestamp-wins rule | The authoritative copy is the *resolved status surface*, never whichever `status.json` has the newer mtime; the fix must not introduce a copy/merge-the-newest behaviour. | Technical | High | Open |
| C-002 | No `--force` requirement removed | The fix removes a *spurious* `--force` demand; genuine guards (review evidence, dependency, verdict-gated exits) keep refusing unforced. | Technical | High | Open |

### Key Entities

- **Status surface**: the directory that owns `status.events.jsonl` and the derived `status.json` — the coordination husk on a coordination-routed mission, the primary/mission-branch copy otherwise.
- **Lane worktree**: a registered git worktree of the mission's repository that is not the primary checkout and not the coordination worktree. It carries a fork-time copy of the mission directory, which is never authoritative.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A status read anchored at a lane worktree root returns the authoritative lane for every lane represented in the mission (0 stale-lane reads in the reproduction fixture) — [build] · no-op passable: no
- **SC-002**: The `for_review` transition completes without `--force` in the reproduction fixture after the lane work is committed — [ratchet] · no-op passable: yes
- **SC-003**: Coordination-routed missions keep their coordination-husk authority for lane-worktree-rooted reads (1 fixture, both topologies) — [ratchet] · no-op passable: yes
