# Mission Specification: [MISSION NAME]
<!-- Replace [MISSION NAME] with the confirmed friendly title generated during /spec-kitty.specify. -->

**Mission Branch**: `[###-mission-name]`  
**Created**: [DATE]  
**Status**: Draft  
**Input**: User description: "$ARGUMENTS"

## User Scenarios & Testing *(mandatory)*

<!--
  IMPORTANT: User stories should be PRIORITIZED as user journeys ordered by importance.
  Each user story/journey must be INDEPENDENTLY TESTABLE - meaning if you implement just ONE of them,
  you should still have a viable MVP (Minimum Viable Product) that delivers value.
  
  Assign priorities (P1, P2, P3, etc.) to each story, where P1 is the most critical.
  Think of each story as a standalone slice of functionality that can be:
  - Developed independently
  - Tested independently
  - Deployed independently
  - Demonstrated to users independently
-->

### User Story 1 - [Brief Title] (Priority: P1)

[Describe this user journey in plain language]

**Why this priority**: [Explain the value and why it has this priority level]

**Independent Test**: [Describe how this can be tested independently - e.g., "Can be fully tested by [specific action] and delivers [specific value]"]

**Acceptance Scenarios**:

1. **Given** [initial state], **When** [action], **Then** [expected outcome]
2. **Given** [initial state], **When** [action], **Then** [expected outcome]

---

### User Story 2 - [Brief Title] (Priority: P2)

[Describe this user journey in plain language]

**Why this priority**: [Explain the value and why it has this priority level]

**Independent Test**: [Describe how this can be tested independently]

**Acceptance Scenarios**:

1. **Given** [initial state], **When** [action], **Then** [expected outcome]

---

### User Story 3 - [Brief Title] (Priority: P3)

[Describe this user journey in plain language]

**Why this priority**: [Explain the value and why it has this priority level]

**Independent Test**: [Describe how this can be tested independently]

**Acceptance Scenarios**:

1. **Given** [initial state], **When** [action], **Then** [expected outcome]

---

[Add more user stories as needed, each with an assigned priority]

### Edge Cases

<!--
  ACTION REQUIRED: The content in this section represents placeholders.
  Fill them out with the right edge cases.
-->

- What happens when [boundary condition]?
- How does system handle [error scenario]?

## Requirements *(mandatory)*

<!--
  ACTION REQUIRED:
  1) Keep requirement types separated (Functional / Non-Functional / Constraints)
  2) Use unique IDs per type (FR-###, NFR-###, C-###)
  3) Keep Status populated for every row
  4) Non-functional requirements must include measurable thresholds
  5) Delivery label + no-op mark on every FR row and success criterion (summary of
     tactic `acceptance-criteria-non-vacuity`): `[build]`/`[ratchet]`/`[folded]`
     delivery, `yes`/`no` no-op passable.
  6) The label set and the three non-vacuity rules (same-fixture positive control,
     half-by-half proof for compound fixes, production-path non-vacuity) are defined
     once, in tactic `acceptance-criteria-non-vacuity` -- fetch it with
     `spec-kitty charter context --include tactic:acceptance-criteria-non-vacuity`.
     Do not redefine the labels here; this comment only points to that tactic.
  7) A label never goes inside or before the ID cell, and never inline on an FR
     bullet/heading -- it is a trailing column (or success-criterion suffix) only.

  Filled example (summary of tactic acceptance-criteria-non-vacuity; `FR-EXAMPLE`
  does not match the `FR-###` id pattern, so it declares no requirement id):

  | FR-EXAMPLE | Refuses malformed input | As an operator, I want malformed input rejected so that downstream state stays consistent. | High | Open | [ratchet] | yes — paired with the well-formed-input row on the same fixture |
-->

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | [Short title] | As a [role], I want [goal] so that [benefit]. | High | Open | [build/ratchet/folded] | [yes/no] |
| FR-002 | [Short title] | As a [role], I want [goal] so that [benefit]. | Medium | Open | [build/ratchet/folded] | [yes/no] |
| FR-003 | [Short title] | As a [role], I want [goal] so that [benefit]. | Low | Open | [build/ratchet/folded] | [yes/no] |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | [Short title] | [Measurable threshold, e.g., p95 latency under 300ms] | Performance | High | Open |
| NFR-002 | [Short title] | [Measurable threshold] | Security | High | Open |
| NFR-003 | [Short title] | [Measurable threshold] | Reliability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | [Short title] | [Required boundary or limitation] | Technical | High | Open |
| C-002 | [Short title] | [Required boundary or limitation] | Business | Medium | Open |
| C-003 | [Short title] | [Required boundary or limitation] | Regulatory | Medium | Open |

### Key Entities *(include if feature involves data)*

- **[Entity 1]**: [What it represents, key attributes without implementation]
- **[Entity 2]**: [What it represents, relationships to other entities]

## Success Criteria *(mandatory)*

<!--
  ACTION REQUIRED: Define measurable success criteria.
  These must be technology-agnostic and measurable.
-->

### Measurable Outcomes

<!-- ACTION REQUIRED: append a delivery label + no-op mark to every success criterion,
     same as the FR table above -- "— [build/ratchet/folded] · no-op passable: [yes/no]". -->

- **SC-001**: [Measurable metric, e.g., "Users can complete account creation in under 2 minutes"] — [build/ratchet/folded] · no-op passable: [yes/no]
- **SC-002**: [Measurable metric, e.g., "System handles 1000 concurrent users without degradation"] — [build/ratchet/folded] · no-op passable: [yes/no]
- **SC-003**: [User satisfaction metric, e.g., "90% of users successfully complete primary task on first attempt"] — [build/ratchet/folded] · no-op passable: [yes/no]
- **SC-004**: [Business metric, e.g., "Reduce support tickets related to [X] by 50%"] — [build/ratchet/folded] · no-op passable: [yes/no]
