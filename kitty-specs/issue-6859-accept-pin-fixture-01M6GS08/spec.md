# Mission Specification: Repair the #4891 accept pin's positive control fixture

**Mission Branch**: `issue-6859-accept-pin-fixture`
**Created**: 2026-11-03
**Status**: Draft
**Input**: GitHub issue #6859 — `test_issue_4891_accept_missing_lanes` positive control is red on `main`: the #6715 evidence gate refuses a fixture whose lane branch never existed.

## Context

`tests/specify_cli/cli/commands/test_issue_4891_accept_missing_lanes.py` is the CLI-level
standing pin for #4891: `spec-kitty accept` must fail closed when a Mission's `lanes.json` is
absent. It holds two controls built on one fixture:

- the **negative** control (no `lanes.json`) exits non-zero and names the blocked
  `lanes_manifest` check — this one is green;
- the **positive** control (`lanes.json` present, passing acceptance matrix) must succeed and
  stamp `accepted_at` — this one is **red on `main`** (reproduced on a pristine clone before
  any change: `1 failed, 1 passed`).

The red is in the **fixture, not the assertion**. Since #6715/#5939 every landing surface
(`accept`, `consolidate`, `move-task`) refuses an approved work package that has no readable
implementation-evidence window, no change to its `owned_files` inside that window, or no
approval by an identity other than its implementer. The pin's fixture — the shared
`_create_test_feature` helper plus `write_single_lane_manifest` — predates all three axes: its
work package declares no `owned_files`, its status log is one forced `planned -> done` hop under
a single actor, and its `lane-a` branch never existed, so the window `planning_commit_sha..<lane
branch>` cannot be read at all (`IMPLEMENTATION_UNREADABLE`).

Because the positive control is what proves the negative control is exercising the
`lanes.json`-absence path specifically, a positive control that is blocked by unrelated gates
makes the whole pin vacuous: the negative control could pass for the wrong reason and nobody
would know.

`main` is the correct authority here: `accept`'s refusal of an unreadable evidence window is
deliberate, documented behaviour (fail closed) and is covered by its own tests. The subject
that is wrong is the fixture that claims to be an acceptable Mission while supplying none of
the evidence a Mission carries.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The #4891 pin's two controls differ only by `lanes.json` (Priority: P1)

A maintainer who changes `accept`'s `lanes.json` handling runs the standing pin. The positive
control builds the same Mission the negative control does and adds only `lanes.json` + a
passing matrix; `accept` succeeds and stamps `accepted_at`. If any unrelated gate starts
refusing the fixture again, the positive control turns red and names that gate, instead of
silently reducing both controls to the same assertion.

**Why this priority**: it is the only reason the file exists; without it the pin cannot
distinguish "`lanes.json` missing" from "the fixture cannot be accepted at all".

**Independent Test**: `uv run pytest tests/specify_cli/cli/commands/test_issue_4891_accept_missing_lanes.py -q` reports `2 passed`.

**Acceptance Scenarios**:

1. **Given** the shared fixture Mission is implemented (owned files declared, a lane-branch
   implementation commit in the evidence window) and independently reviewed, **When**
   `lanes.json` and a passing acceptance matrix are added and the real `spec-kitty accept` CLI
   runs, **Then** it exits 0 and stamps `accepted_at`.
2. **Given** the same fixture without `lanes.json`, **When** `accept` runs, **Then** it exits
   non-zero, stamps nothing, and names the blocked `lanes_manifest` check.

### Edge Cases

- The fixture builder must not itself require `lanes.json` (the negative control has none), so
  the implementation commit is added by the positive control after the manifest exists.
- A lane branch whose commit does not touch the work package's `owned_files` is refused
  `IMPLEMENTATION_MISSING`; the implementation commit path must match the declared ownership.
- An approval recorded by the implementer's own identity is refused `REVIEW_NOT_INDEPENDENT`;
  the approving actor must be a distinct identity.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Positive control is green | As a maintainer, I want the pin's positive control to pass on `main` so that the pin proves what it claims. | High | Open | [ratchet] | no |
| FR-002 | One shared fixture, one difference | As a maintainer, I want both controls built by one helper that differs only by `lanes.json` so the positive control cannot drift into a different Mission. | High | Open | [ratchet] | no |
| FR-003 | Fixture states its evidence | As a maintainer, I want the fixture to declare WP01's `owned_files`, commit its implementation on the lane branch, and record a claim plus an approval by a distinct identity so the post-#6715 axes are satisfied by the fixture, not waived. | High | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Assertions unchanged | Every assertion of the standing pin is byte-identical before and after: no assertion is deleted, softened, skipped or xfailed. | Maintainability | High | Open |
| NFR-002 | Production entry point | Both controls continue to drive the real `spec-kitty accept` CLI (`typer.CliRunner` over the real command) against a real git repository, never a helper-only surface. | Test fidelity | High | Open |
| NFR-003 | Bounded runtime | The file completes locally in under 5 minutes on this host (measured 107 s for both controls after the change). | Performance | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Tests only | The diff changes test fixtures only; no product code is touched, because the product behaviour (`accept` fails closed) is correct. | Technical | High | Open |
| C-002 | Pin stays a pin | The test is not deleted, skipped, renamed away or reduced in scope; it remains the CLI-level pin for #4891. | Governance | High | Open |
| C-003 | Reuse the established shape | The fixture reuses the repositories' existing building blocks (`_create_test_feature`, `write_single_lane_manifest`, `commit_lane_implementation`, `seed_status_event`) rather than inventing a third fixture shape. | Technical | Medium | Open |

### Key Entities

- **Standing pin**: the two-control test module for #4891.
- **Accept-ready fixture**: a Mission repository whose work package is implemented, owned and
  independently reviewed, so only the gate under test can refuse it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The pin file reports `2 passed` locally and in CI on the PR head. — [ratchet] · no-op passable: no
- **SC-002**: Removing the fixture's lane-branch implementation commit, its `owned_files`
  declaration, or its independent approval each turns the positive control red with the
  corresponding evidence code (`IMPLEMENTATION_UNREADABLE`, `IMPLEMENTATION_MISSING`,
  `REVIEW_NOT_INDEPENDENT`). — [build] · no-op passable: no
- **SC-003**: The negative control still reports `lanes_manifest` among the blocked checks and
  stamps no `accepted_at`. — [ratchet] · no-op passable: no
