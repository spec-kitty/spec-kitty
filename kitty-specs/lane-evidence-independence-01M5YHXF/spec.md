# Mission Specification: Lane evidence and review independence

**Mission Branch**: `issue-6715-lane-evidence-independence`
**Created**: 2026-10-27
**Status**: Draft
**Input**: Issue #6715 (P0, epic #5001; the lanes/coordination counterpart of #5939) plus the
operator rulings of 2026-10-27 recorded below.

## Intent Summary (confirmed)

- **Primary actor**: an agent or operator moving a work package through review, then accepting
  and consolidating the Mission.
- **Trigger**: a work package of a lanes or coordination Mission (code lane or planning lane) is
  claimed, never implemented, and approved, possibly by the same identity that claimed it.
- **Desired outcome**: approve, accept and consolidate refuse with a named code; nothing lands as
  `done`; consolidate never prints its integrity banner while an owned deliverable is missing.
- **Invariant**: a work package lands as `done` only when (a) a committed change touches its
  owned files (or an operator attested that it has no deliverable) and (b) the approving identity
  differs from the implementing identity.
- **Operator rulings (binding)**:
  1. Independence keeps the #5939 identity unchanged on every topology: the recorded
     `tool:model:profile` of the latest implementer and of the latest approver must differ. The
     recorded role is stamped from the target lane, so it does not distinguish actors and is not
     compared. Decision recorded 2026-10-27.
  2. Missing implementation refuses by default; an operator attestation may lift it for a work
     package with no deliverable. It never lifts independence.
  3. At `move-task`, `--force` keeps bypassing the evidence check (today's escape hatch);
     accept and consolidate refuse regardless of `--force` and `--lenient` unless attested
     (decision `01M5YHYFRJPTE0SQ9V7SWGK26J`).
  4. Planning lanes are covered too, not left as a residual.
  5. One Mission, one PR.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A hollow approval is refused (Priority: P1)

An agent claims WP03 on a coordination Mission, commits nothing to its owned file
`tools/check.sh`, ticks its subtask and runs `move-task WP03 --to approved` under its own name.

**Why this priority**: this is the P0 itself; today every command exits 0 and the deliverable is
missing from the target.

**Independent Test**: the exact claimed-but-empty coordination fixture from the issue, driven
through the real CLI.

**Acceptance Scenarios**:

1. **Given** a coord Mission whose WP was claimed but has no commit touching its owned files,
   **When** the claimer runs an unforced `move-task --to approved`, **Then** the move refuses with
   `IMPLEMENTATION_MISSING` and the WP is not `approved`.
2. **Given** the same WP pushed to `approved` with `--force` by a different reviewer, **When**
   `accept` runs, **Then** it refuses with `IMPLEMENTATION_MISSING` and writes no acceptance.
3. **Given** the same state with accept bypassed, **When** `consolidate` runs, **Then** it refuses
   before any branch moves, prints no "Reconciliation verified" banner, and no WP is `done`.
4. **Given** a lanes Mission (no coordination branch), **When** the same flow runs, **Then** the
   same codes refuse.
5. **Given** a single_branch Mission, **When** the same flow runs, **Then** the existing #5939
   refusals still fire with their `SINGLE_BRANCH_*` codes.

### User Story 2 - Self-approval is refused (Priority: P1)

An implementer commits real work and approves it under the same identity.

**Acceptance Scenarios**:

1. **Given** a WP implemented and approved by the same `tool:model:profile`, **When** the
   approval is an unforced `move-task`, **Then** it refuses with `REVIEW_NOT_INDEPENDENT`.
2. **Given** the same self-approval recorded with `--force`, **When** accept or consolidate runs,
   **Then** it refuses with `REVIEW_NOT_INDEPENDENT`.
3. **Given** the same agent name with a different recorded profile, **When** it approves,
   **Then** independence holds.
4. **Given** a different reviewer approving real work (with or without `--force`), **When** the
   Mission is accepted and consolidated, **Then** it lands clean (positive control).

### User Story 3 - An operator lifts the refusal for a no-deliverable WP (Priority: P2)

A docs-only work package has nothing committed to its owned files by design.

**Acceptance Scenarios**:

1. **Given** an approved WP with no owned-file change, **When** the operator runs accept or
   consolidate with `--attest-no-implementation <WP> --attest-reason "<why>"`, **Then** a forced
   operator transition with `policy_metadata.attestation` is recorded and `IMPLEMENTATION_MISSING`
   is lifted for that WP only.
2. **Given** that attestation, **When** consolidate runs, **Then** its output names the attested
   WP.
3. **Given** an attested WP that was self-approved, **When** consolidate runs, **Then**
   `REVIEW_NOT_INDEPENDENT` still refuses.
4. **Given** `--attest-no-implementation` without a non-blank `--attest-reason`, **When** the
   command runs, **Then** it refuses and records nothing.

### Edge Cases

- An unreadable evidence range (missing lane branch, unreachable planning commit) refuses with
  `IMPLEMENTATION_UNREADABLE`; it never passes.
- A Mission with no recorded planning commit refuses with `EVIDENCE_WINDOW_UNCOMPUTABLE`.
- Status, issue-matrix, `meta.json` and `.kittify/` commits never count as implementation, even
  when an owned-file glob would match them.
- A commit that is later reverted leaves no owned-file change and does not count.
- Merges of sibling lanes into a lane do not count for this WP (owned files are disjoint).
- A canceled-with-provenance WP is outside the claim and is not checked.
- The attestation is never read as an approval, an approval stamp or the approving actor.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Move-task evidence gate on every topology | As an operator, I want an unforced move of a lanes or coord WP (code or planning lane) into a review lane to refuse `IMPLEMENTATION_MISSING` when no committed change touches its owned files, so that a hollow WP cannot walk to `approved`. | High | Open | [build] | no — paired with the real-implementation positive control on the same fixture |
| FR-002 | Move-task independence gate | As an operator, I want an unforced approval by the implementer's own `tool:model:profile` identity to refuse `REVIEW_NOT_INDEPENDENT` on every topology, so that self-review never counts. | High | Open | [build] | no — paired with a different-reviewer approval on the same fixture |
| FR-003 | Accept preflight | As an operator, I want `accept` to refuse, before writing anything and regardless of `--lenient`, any approved WP that fails the evidence or independence check, naming the code. | High | Open | [build] | no — the positive control accepts on the same fixture |
| FR-004 | Consolidate lane-evidence axis | As an operator, I want `consolidate` to refuse such a WP before any branch moves, so that the integrity banner is never printed with a missing owned deliverable. | High | Open | [build] | no — the positive control consolidates clean |
| FR-005 | Orchestrator consolidate-mission refusal | As an external orchestrator, I want `orchestrator-api consolidate-mission` to fail with `PREFLIGHT_FAILED` and the refusal codes in `data`, before any lane is merged. | High | Open | [build] | no — paired with a clean consolidate-mission run |
| FR-006 | No-implementation attestation | As an operator, I want `--attest-no-implementation <WP> --attest-reason "<why>"` on `accept` and `consolidate` to record a forced operator transition that lifts only `IMPLEMENTATION_MISSING` for that WP, and to see it named in consolidate output. | Medium | Open | [build] | no — the same WP refuses without the attestation |
| FR-007 | Topology-neutral codes | As a tool author, I want the codes `IMPLEMENTATION_MISSING`, `REVIEW_NOT_INDEPENDENT`, `IMPLEMENTATION_UNREADABLE` and `EVIDENCE_WINDOW_UNCOMPUTABLE`, with the `SINGLE_BRANCH_*` codes kept as aliases of the same meaning. | Medium | Open | [build] | no — asserted on each topology's refusal text |
| FR-008 | Decision record | As a maintainer, I want ADR `2026-10-04-5` amended (evidence is a separate axis; the approval bound is unchanged) with both rulings, and a changelog entry. | Medium | Open | [build] | yes — documentation; reviewed, not executed |
| FR-009 | Scenario coverage | As a maintainer, I want a Gherkin scenario under `tests/scenarios` for the hollow-approval refusal if a fitting feature exists, run on JDK 25. | Low | Open | [build] | no — the scenario fails before the fix |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Bounded cost | The evidence check runs at most one git tree diff per lane and one status-log read per command; accept and consolidate stay within the 2-second CLI budget for a 20-WP Mission on a local repository. | Performance | Medium | Open |
| NFR-002 | Fail closed | Every git or status-log read error in the check refuses (0 paths through which an unreadable range passes). | Reliability | High | Open |
| NFR-003 | Code quality | Touched code passes ruff, ruff format and mypy with 0 new suppressions; every touched function stays at complexity ≤ 15; diff coverage ≥ 90%. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Approval bound unchanged | `consolidation/approved_bound.py` semantics are not changed; evidence is a separate axis. | Technical | High | Open |
| C-002 | Identity unchanged | Independence reuses the #5939 comparison (`preflight._independent_reviewer_confirmed`); no new event field is introduced. | Technical | High | Open |
| C-003 | Single authority | One shared predicate serves move-task, accept, consolidate and orchestrator-api. | Technical | High | Open |
| C-004 | Move-time force | `move-task --force` keeps bypassing the evidence check (ruling 3). | Business | High | Open |
| C-005 | Delivery vehicle | One Mission, one PR to `main` via the topic branch; the operator merges. | Business | High | Open |

### Key Entities

- **Evidence window**: the commit range whose tree diff, restricted to a WP's owned files, is its
  implementation evidence. Code lane: recorded planning commit to the lane branch. Planning lane
  and single_branch: recorded planning commit to the Mission's landing branch.
- **No-implementation attestation**: a forced operator transition from a WP's lane to itself
  carrying `policy_metadata.attestation` and the operator's reason.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The issue's claimed-but-empty coordination fixture ends with 0 WPs `done` and a
  named refusal from approve, accept and consolidate (red before, green after). — [build] · no-op passable: no
- **SC-002**: The positive-control fixture (real work, independent review) still lands every WP
  `done` on lanes, coord and single_branch. — [ratchet] · no-op passable: yes — paired with SC-001 on the same fixture
- **SC-003**: An attested no-deliverable WP consolidates and is named in the output; the same WP
  without the attestation refuses. — [build] · no-op passable: no

## Assumptions

- Missions created by 4.x record `planning_commit_sha` at `finalize-tasks`; older Missions without
  it refuse with `EVIDENCE_WINDOW_UNCOMPUTABLE` and are repaired by re-running `finalize-tasks`.
- Owned-file globs are disjoint across WPs (the existing ownership invariant).
