# Mission Specification: Late teardown verdict projection

**Mission Branch**: `late-teardown-verdict-projection-01M67J85`
**Created**: 2026-10-30
**Status**: Draft
**Input**: User description: "spec-kitty/spec-kitty#6791 — `consolidate --resume` after `COORD_TEARDOWN_KEPT_ONLY_COPY` projects only part of the coordination commits, then deletes the coordination branch: an issue-verdict commit is lost"

## Problem

`consolidate` refuses coordination teardown with `COORD_TEARDOWN_KEPT_ONLY_COPY` (exit 76)
when the coordination worktree holds untracked review-cycle artifacts. The refusal's own
instruction is to commit them on the coordination branch and re-run `--resume`. An operator who
does that, and then records the terminal issue verdict the gate also complained about
(`spec-kitty agent issue-verdict`, which commits to the coordination surface), hands the resume
**two** commits: the artifacts commit (A) and the verdict commit (B, A's child).

`--resume` projects only part of that window. It prints "Projected the coordination commit(s)
that landed during teardown", deletes the coordination branch, and lands the mission with the
issue-matrix row still `in-mission`. Commit B is unreachable afterwards
(`git fsck --lost-found` finds it). The gate that validated the resume read the verdict from the
coordination surface — the same commit the projection then dropped.

The window is `pre_mutation_coord_sha..coordination-tip`, and the projection seam deliberately
excludes the gate matrices (`IssueMatrix`/`AcceptanceMatrix`) because in the *mid-merge* window
the coordination ref holds only a stale finalize-time placeholder and the accepted copy is
authored on the target. That exclusion is correct there and wrong after teardown has begun: every
commit in this window is newer than anything the target holds, and it is the operator's attempt
to obey the refusal.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A verdict recorded between a teardown refusal and the resume lands (Priority: P1)

An operator obeys a `COORD_TEARDOWN_KEPT_ONLY_COPY` refusal: they commit the kept files on the
coordination branch and record the outstanding issue verdict. They run
`spec-kitty consolidate --mission <slug> --resume --yes`. The mission lands, the coordination
branch is gone, and the target's `issue-matrix.json` carries the verdict they recorded.

**Why this priority**: Silent data loss on a documented recovery path. The mission lands `done`
claiming success while the evidence the operator just recorded is destroyed — the exact class of
failure `--resume` exists to prevent.

**Independent Test**: Build a coord-topology mission, drive a real teardown refusal, commit a
review-cycle artifact, run the real `agent issue-verdict`, then `consolidate --resume` and read
`issue-matrix.json` from the target branch.

**Acceptance Scenarios**:

1. **Given** a refused teardown whose coordination branch carries an artifacts commit and a later
   `issue-verdict` commit, **When** the operator runs `consolidate --resume`, **Then** the target's
   `issue-matrix.json` carries the recorded verdict and the coordination branch is deleted.
2. **Given** the same shape, **When** the resume completes, **Then** no commit reachable from the
   pre-resume coordination tip is left unprojected for any coordination record in the window.
3. **Given** a late coordination commit whose content the target already holds, **When** the
   resume runs, **Then** nothing is committed twice and the branch is still deleted.

---

### User Story 2 - A resume that cannot land a late commit refuses instead of deleting it (Priority: P2)

An operator's late coordination commit touches a coordination record the resume cannot prove is
preserved. The resume says so, names the path, keeps the branch, worktree and marker together, and
exits non-zero.

**Why this priority**: The issue accepts either "project everything" or "refuse while unprojected
commits exist". A refusal keeps the operator's work recoverable; a silent delete does not.

**Independent Test**: Plant a late commit on a coordination record the projection cannot carry,
run `consolidate --resume`, assert a non-zero exit naming the path and an intact branch.

**Acceptance Scenarios**:

1. **Given** a refused teardown and a late coordination commit the projection cannot carry,
   **When** the operator runs `consolidate --resume`, **Then** the run exits non-zero naming the
   path, and the branch, worktree and marker all survive.
2. **Given** such a refusal, **When** the operator lands the content on the target themselves and
   re-runs `--resume`, **Then** teardown completes.

---

### User Story 3 - An established judgement is never overturned by a projection (Priority: P3)

A projection brings the coordination copy of a gate matrix forward only when doing so cannot lose
or overturn a judgement the target already holds.

**Why this priority**: The exclusion being lifted exists to protect accepted evidence. Lifting it
without a preservation guard would trade one data-loss mode for another.

**Independent Test**: Seed the target with a terminal verdict the coordination copy lacks, plant
the corresponding late commit, resume, and assert the target keeps its established judgement.

**Acceptance Scenarios**:

1. **Given** the target holds a terminal issue verdict the coordination copy would replace with a
   non-terminal one, **When** the resume tries to project that copy, **Then** the projection
   refuses and the branch survives.
2. **Given** the target holds the same terminal verdict and the coordination copy also holds it (or
   a newer one), **When** the resume runs, **Then** the projection proceeds.

---

### Edge Cases

- The late window contains nothing but the status pair: the union/rematerialize path owns it, and
  the completeness check must not double-report it.
- A coordination record was **deleted** by a late commit: the projection cannot carry a deletion
  (it is forward-only), so it refuses rather than resurrecting or silently dropping it.
- The coordination branch carries a late commit outside `kitty-specs/<slug>/`: the existing
  stranded-path refusal still wins (unchanged behaviour).
- A resumed mission whose target already holds the exact coordination content: no empty commit is
  made.
- `--keep-branch` / retained worktree shapes never reach the delete, so the refusal is the only
  new behaviour they can see.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Late gate-matrix commit projected | As an operator, I want a gate-matrix commit made after a teardown refusal projected onto the target so that the verdict I recorded is not lost. | High | Open | [build] | no |
| FR-002 | Whole late window proven landed | As an operator, I want the resume to prove every coordination record in the late window reached the target (or refuse) so that no commit is silently dropped. | High | Open | [build] | no |
| FR-003 | Refusal keeps the coordination triple | As an operator, I want a failed late projection to exit non-zero naming the path with branch, worktree and marker intact so that my work stays recoverable. | High | Open | [ratchet] | no — paired with FR-001 on the same fixture (the projection's positive control) |
| FR-004 | No established judgement overturned | As a maintainer, I want a projection to refuse when it would lose a judgement the target already holds so that lifting the exclusion cannot regress accepted evidence. | High | Open | [build] | no |
| FR-005 | Forward-only projection | As an operator, I want a late deletion of a coordination record to refuse rather than resurrect or drop it so that the target is never silently rewritten. | Medium | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Bounded window | The extra work stays O(paths changed in `pre_mutation_coord_sha..coord tip`), with no full-history walk. | Performance | Medium | Open |
| NFR-002 | Fail closed | Any unreadable git diff, unparsable coordination matrix, or unmatched path raises before the branch delete; no path in this flow ever reads an error as "nothing to project". | Reliability | High | Open |
| NFR-003 | No new write surface | Every projection still goes through the existing bookkeeping-commit seam on the target; no new writer, no direct commit. | Technical | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Mid-merge behaviour unchanged | The mid-merge projection (the #4981/S-B window, feeding the squash proof) keeps its current exclusion set; only the post-teardown window widens. | Technical | High | Open |
| C-002 | Provider surface untouched | Do not touch `mission_runtime`, the placement seam, or the `--push` path; this is a projection-window fix inside `specify_cli.consolidation`. | Technical | High | Open |

### Key Entities

- **Late window**: the commit range `pre_mutation_coord_sha..coordination-tip` read by
  `consolidate --resume` teardown; every commit in it landed after the merge verified the landing.
- **Coordination record**: a file inside `kitty-specs/<slug>/` that `is_coordination_kind_file`
  classifies as a COORD-partition artifact (status pair, decision log, tracer files,
  review-cycle files, the two gate matrices).
- **Gate matrix**: `issue-matrix.json` / `acceptance-matrix.json`, the accept-time evidence
  documents. Their rows carry verdicts/statuses whose terminal values are established judgements.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The reproduction from #6791 lands the recorded verdict on the target: `issue-matrix.json` on the target reads the terminal verdict the operator recorded, and the coordination branch is gone. — [build] · no-op passable: no
- **SC-002**: For every coordination record changed in the late window, the target's byte content equals the coordination tip's after a successful resume — zero unprojected coordination records, asserted by the resume itself. — [build] · no-op passable: no
- **SC-003**: A late commit that cannot be projected produces a non-zero exit naming the path with the branch, worktree and coordination marker intact — 0 branches deleted on that path. — [ratchet] · no-op passable: no — positive control is SC-001's successful projection on the same fixture family
- **SC-004**: An established terminal verdict on the target is never replaced by a non-terminal one: 0 regressions in the guard's fixtures, and the guard refuses (non-zero) when it would be. — [build] · no-op passable: no

## Out of Scope

- The `#6653` sibling path (terminality gate passing while a row is `in-mission`) — closed separately.
- Making `move-task` commit review-cycle artifacts before teardown with auto-commit disabled
  (mentioned in the issue's Notes as worth its own look). The refusal semantics for that are
  correct; only the recovery path is in scope.
- Any change to how `issue-verdict` routes its commit.

## Traceability

| Source | Requirement |
|--------|-------------|
| #6791 "Expected behavior" | FR-001, FR-002, FR-003 |
| #6791 "Actual behavior" / dangling commit | FR-001, SC-001 |
| #6791 "the workaround in the registry for #6653" | FR-004 |
| Issue "Notes" (untracked artifacts, auto-commit) | Out of scope |
