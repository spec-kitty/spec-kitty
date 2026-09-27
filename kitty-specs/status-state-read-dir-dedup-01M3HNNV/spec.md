# Mission Specification: Single STATUS_STATE read-dir resolver with phantom-coord degrade

**Mission Branch**: `claude/project-thread-5t7sqy`
**Created**: 2026-09-27
**Status**: Draft
**Input**: GitHub issue [#5180](https://github.com/spec-kitty/spec-kitty/issues/5180) (P1, milestone "4.0.0 release scope") — dedup the STATUS_STATE feature-dir resolvers onto the canonical partition resolver and gain its phantom-coord `.exists()` degrade.

## Background

Three places answer the same question — *"which mission directory holds this mission's
status event log?"* — and they do not answer it the same way:

1. The post-merge review-artifact consistency gate owns the canonical answer. It routes
   through the placement seam and, when the seam hands back a directory that does not
   exist while the directory it was handed does, it degrades to the handed directory
   (the #154 phantom-path guard).
2. The implement/fix render path (review-feedback lookup and prior-rejection check) got
   its own copy in #5024 / PR #5177.
3. The move-task verdict-persistence path has an older copy the render copy mirrors.

Copies 2 and 3 lack the phantom-path guard. When the placement seam resolves to a
directory that is not really there, the event log read finds nothing, the reader
swallows the absence, and the operator's rejected-review feedback silently disappears
from the next implement prompt — the exact silent-loss class #4899/#5024 exist to
prevent. The render path runs on every implement/fix cycle.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Review feedback survives a phantom status partition (Priority: P1)

An implementer agent re-runs `implement` on a work package whose last review was a
rejection. The mission's status partition resolves to a directory that is not actually
present on disk (the canonical-root walk anchored on a foreign ancestor checkout, #154),
while the mission directory the command was handed is real and holds the event log.

**Why this priority**: This is the silent feedback-loss the issue was raised to P1 for;
the agent otherwise re-implements without ever seeing why it was rejected.

**Independent Test**: Build a mission fixture whose placement resolution points at a
non-existent directory while the handed mission directory holds a rejection event with a
review reference; ask for the latest review feedback and the prior-rejection verdict.

**Acceptance Scenarios**:

1. **Given** a mission whose status partition resolves to a non-existent directory and
   whose handed mission directory holds a rejection event, **When** the render path
   looks up the latest review feedback, **Then** it returns that rejection's feedback
   reference (not "no feedback").
2. **Given** the same fixture, **When** the render path's prior-rejection check reads
   the event log, **Then** it reads it from the same directory the feedback lookup
   uses (one resolver for both).
3. **Given** a mission whose status partition resolves to a real, materialised
   coordination directory, **When** either lookup runs, **Then** it reads the
   coordination directory's log exactly as today.

---

### User Story 2 - Move-task verdict reads the same authority (Priority: P1)

A reviewer or orchestrator moves a work package; the verdict-persistence step reads the
existing review verdict from the status event log.

**Why this priority**: Same silent-loss hazard on the verdict path; it is the older of
the two copies and the one the render copy was cloned from.

**Independent Test**: Same phantom fixture; ask the verdict-persistence read for the
feature directory it will read events from.

**Acceptance Scenarios**:

1. **Given** a phantom status partition and a real handed mission directory, **When**
   the verdict read resolves its directory, **Then** it resolves the handed mission
   directory.
2. **Given** a non-git bare fixture, **When** the verdict read resolves its directory,
   **Then** it returns the handed mission directory unchanged (existing behaviour).

---

### User Story 3 - One authority for the answer (Priority: P2)

A maintainer changing how status-partition reads resolve edits exactly one function.

**Why this priority**: Prevents the next drift; the guard gap existed only because the
answer had been cloned.

**Independent Test**: Search the source tree for private re-implementations of the
STATUS_STATE feature-dir resolution in the three owning modules.

**Acceptance Scenarios**:

1. **Given** the change is merged, **When** the three call paths resolve their status
   read directory, **Then** all three delegate to the same single resolver.

### Edge Cases

- No workspace root derivable (bare non-git fixture): return the handed directory unchanged.
- Resolved partition does not exist **and** the handed directory does not exist either:
  return the resolved path (no guessing; the degrade only fires when the handed dir
  provably holds the mission).
- Coordination branch deleted, or coordination worktree never materialised: keep the
  seam's existing fail-loud behaviour (`CoordinationBranchDeleted` /
  `CoordinationWorktreeUnmaterialized`); the degrade must not swallow either.
- Flat / single-branch / lanes topology: PRIMARY == status home; behaviour unchanged.
- The render path's artifact-pointer resolution stays on the PRIMARY directory (the
  #5024 "split, not a whole-dir swap" invariant).

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Render feedback lookup degrades on phantom partition | As an implementer agent, I want the latest-review-feedback lookup to read the handed mission directory when the resolved status partition does not exist, so that rejection feedback is never silently dropped. | High | Open | [build] | no — red on main with the phantom fixture; paired with the materialised-coord positive control |
| FR-002 | Prior-rejection check reads the same degraded log | As an implementer agent, I want the prior-rejection check's event-log read to resolve through the same degraded STATUS_STATE resolver as the feedback lookup, so that the two render reads can never disagree about where the log lives. | High | Open | [folded] | no — folded into FR-004's structural delegation check; the review-cycle artifact-dir leg of this check has its own phantom exposure, recorded as out of scope (C-005) |
| FR-003 | Verdict read degrades on phantom partition | As a reviewer, I want the move-task verdict read to resolve the handed mission directory under a phantom partition, so that an existing verdict is not treated as absent. | High | Open | [build] | no — red on main with the same phantom fixture |
| FR-004 | Single resolver authority | As a maintainer, I want the render path, the verdict path and the post-merge gate to delegate to one STATUS_STATE read-dir resolver, so that the guard cannot drift again. | Medium | Open | [build] | no — a structural test asserts delegation and fails if a private copy reappears |
| FR-005 | Materialised-coord and flat reads unchanged | As an operator, I want the materialised-coordination and flat-topology reads to resolve exactly as before, so that the #5024 fix is preserved. | High | Open | [ratchet] | yes — positive control; paired with FR-001's phantom row on the same fixture family |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No added filesystem cost | At most one extra existence probe per resolution versus today. | Performance | Low | Open |
| NFR-002 | Quality gates | New/changed code passes ruff, ruff format, mypy with zero new suppressions; touched functions stay at complexity ≤ 15; diff coverage ≥ 90%. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Keep the render split | Only the event-log read re-routes; review-cycle artifact pointer resolution stays on the PRIMARY directory. | Technical | High | Open |
| C-002 | Keep fail-loud cells | A deleted coordination branch and an unmaterialised coordination worktree still raise; the degrade applies only to a non-existent resolved path with an existing handed dir. | Technical | High | Open |
| C-003 | No new layer edges | The shared resolver must not introduce an import that the architectural layer rules forbid. | Technical | High | Open |
| C-005 | Review-cycle artifact dir not folded | The review-cycle artifact directory resolvers (WORK_PACKAGE_TASK kind) have the same foreign-anchor exposure; they are a different kind and authority and are recorded as a follow-up, not folded. | Technical | Medium | Open |
| C-004 | Out of scope | Other STATUS_STATE read sites with a different input shape (repo root + slug rather than a handed feature dir) are not folded here. | Business | Medium | Open |

### Key Entities

- **Handed mission directory**: the `kitty-specs/<slug>` directory a caller already holds.
- **STATUS_STATE home**: the directory the placement seam declares for the status event log (coord husk when materialised, PRIMARY otherwise).
- **Phantom partition**: a resolved STATUS_STATE home that does not exist on disk while the handed mission directory does. In the live seam only a foreign-anchored canonical root produces one (an unmaterialised coord raises, a materialised coord exists by construction, EMPTY/NONE resolve PRIMARY).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Under a phantom status partition, the render feedback lookup and the move-task verdict read both return the rejection feedback / verdict present in the handed mission directory (neither does today); the fix-mode prior-rejection trigger remains exposed through the review-cycle artifact dir (C-005) — [build] · no-op passable: no
- **SC-002**: Under a materialised coordination partition, the three read paths return identical results to before the change — [ratchet] · no-op passable: yes (positive control for SC-001)
- **SC-003**: Exactly one STATUS_STATE read-dir resolver implementation remains across the three owning modules (three today) — [build] · no-op passable: no

## Assumptions

- The issue text is the brief; the operator's P1 ruling and milestone stand. No
  discovery interview was held beyond the issue (autonomous run from the issue).
- The shared resolver lives on a public, layer-legal home inside `specify_cli`; the exact
  module is a plan decision.
