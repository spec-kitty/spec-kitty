# Mission Specification: Reach-only membership fails closed (#6454)

**Mission Branch**: `issue-6454-reach-only-fail-closed`  
**Created**: 2026-10-26  
**Status**: Draft  
**Input**: User description: "Fix #6454 per kitty-specs/reach-only-fail-closed-research-01M5WZCH/research.md: reach_only_ids falls back to the created-artifacts record when the synthesis manifest is unreadable, and fails closed (every synthesis-edge target is reach-only) with a warning when neither is readable."

Findings this specification builds on: `kitty-specs/reach-only-fail-closed-research-01M5WZCH/research.md`.

## Intent Summary (confirmed)

- **Primary actor**: an operator (or agent) whose project has synthesized charter artifacts and
  who loads action context (`spec-kitty charter context`, a work package prompt).
- **Trigger**: the synthesis manifest exists but cannot be read (corrupt YAML, schema mismatch,
  permission error).
- **Desired outcome**: a synthesized tactic or styleguide whose directive is inactive is still
  not delivered, and the operator is told the manifest is unreadable.
- **Invariant**: a reach-only artifact reaches action context only through its directive's
  suggests edge; a read failure never turns it into a root.
- Confirmed by the operator rulings relayed for this delivery (decision moments
  `01M5WZGJNDBHJC4JS215EJ9EGJ`, `01M5WZH28BW0HC6QNSRRGWX4JP`).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Corrupt manifest, readable record (Priority: P1)

Directive D is inactive; synthesized tactic T is linked from D. The synthesis manifest is
corrupt, the created-artifacts record lists T. Loading action context does not deliver T, and a
warning says the manifest is unreadable and membership was read from the record.

**Why this priority**: this is the fail-open the issue reports.

**Independent Test**: corrupt the manifest on the existing reach-only fixture, keep the record,
load the action governance bundle with D off.

**Acceptance Scenarios**:

1. **Given** D inactive, T recorded and edge-linked, manifest corrupt, **When** the bundle is
   loaded, **Then** T is not delivered and a hand-authored tactic still is.
2. **Given** the same project with D active, **When** the bundle is loaded, **Then** T is
   delivered through D's edge.

---

### User Story 2 - Neither source readable (Priority: P1)

Both the manifest and the record are unreadable (or the record is absent). Every artifact of the
kind that a synthesis-shaped edge links from a directive is treated as reach-only; a warning
names both files.

**Why this priority**: the second half of the issue's acceptance criteria (fail closed).

**Independent Test**: corrupt both files on the fixture; check `reach_only_ids` and delivery.

**Acceptance Scenarios**:

1. **Given** both files unreadable and D inactive, **When** the bundle is loaded, **Then** T is
   not delivered, and a warning is logged.
2. **Given** an org-required synthesized artifact, **When** both files are unreadable, **Then**
   it stays a root.

---

### User Story 3 - Styleguides behave the same (Priority: P2)

A synthesized styleguide sourced from its directive is covered by the same rules.

**Independent Test**: the compiled reference roots (`_direct_root_urns`) exclude it with a
corrupt manifest, for both the record-fallback and the neither-readable case.

### Edge Cases

- Absent manifest (never synthesized): unchanged, nothing is reach-only, no warning.
- Present manifest with no entries: unchanged, nothing is reach-only.
- Overlay without any synthesis-shaped edge of the kind: nothing to decide, no warning.
- A hand-authored edge to a hand-authored artifact never makes it reach-only, also when failing
  closed.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Record fallback | As an operator, I want reach-only membership read from the created-artifacts record when the synthesis manifest is unreadable, so that a synthesized artifact of an inactive directive is not delivered. | High | Open | [build] | no — red on main; paired with the directive-active delivery control on the same fixture |
| FR-002 | Fail closed when neither source is readable | As an operator, I want every overlay artifact of the kind that a synthesis-shaped edge links from a directive treated as reach-only when neither the manifest nor the record can be read, so that governance never fails open. | High | Open | [build] | no — red on main; paired with an edgeless/hand-authored root control |
| FR-003 | Operator warning | As an operator, I want a warning naming the unreadable file(s) and the membership source used, so that I can repair the manifest. | High | Open | [build] | no — asserted on the log record; no warning on the intact control |
| FR-004 | Styleguide parity | As an operator, I want FR-001..FR-003 to hold for synthesized styleguides as for tactics. | High | Open | [build] | no — red on main via the compiled reference roots |
| FR-005 | Absent manifest unchanged | As an operator who never synthesized, I want no change: nothing is reach-only and nothing is warned. | Medium | Open | [ratchet] | yes — pins existing behaviour; paired with FR-001's red case |
| FR-006 | Org-required stays a root | As an org pack owner, I want a required synthesized artifact to stay a root also when failing closed. | Medium | Open | [ratchet] | yes — pins existing subtraction; paired with FR-002 |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No extra reads when undecidable | Membership files are read only when the overlay has at least one synthesis-shaped edge of the kind (0 extra reads otherwise). | Performance | Medium | Open |
| NFR-002 | Quality gates | Touched files pass ruff, ruff format and mypy with 0 findings; no new suppressions; complexity at most 15 per function. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Single owner | The decision lives in `reach_only_ids`; consumers (action governance bundle, compiler) gain no graph filtering. | Technical | High | Open |
| C-002 | Append path unchanged | `_first_time_slugs` / `append_synthesized_activations` keep their current reading of an unreadable manifest. | Technical | Medium | Open |
| C-003 | Existing warning channel | The warning uses the module logging channel the bundle already uses (routed to the terminal by the CLI logging bootstrap). | Technical | Medium | Open |

### Key Entities

- **Synthesis manifest**: registry of synthesized artifacts (primary membership source).
- **Created-artifacts record**: every id synthesis has created, per kind (fallback source).
- **Synthesis-shaped edge**: a `directive --suggests--> <kind>` overlay edge stamped with the
  synthesis reason.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With a corrupt manifest, 0 synthesized tactics or styleguides of an inactive directive are delivered, in both the record-fallback and the neither-readable case — [build] · no-op passable: no
- **SC-002**: Every corrupt-manifest load emits exactly one warning per kind per membership read, and an intact or absent manifest emits 0 — [build] · no-op passable: no

## Assumptions

- An absent record counts as "not readable" for membership: it holds nothing to resolve.
- The record is a superset of the manifest's live entries; membership still requires the
  synthesis-shaped edge, so the superset cannot make a hand-authored artifact reach-only.
