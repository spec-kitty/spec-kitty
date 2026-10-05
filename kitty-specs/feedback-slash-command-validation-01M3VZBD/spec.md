# Mission Specification: Feedback slash command and input hardening

**Mission Branch**: `feedback-slash-command-validation-01M3VZBD`
**Created**: 2026-10-01
**Status**: Draft
**Input**: User description: "Add a slash command (in-harness) to show the feedback form. Validate input: the 5-star question only accepts 1-5, not text or any other number; sanitize any text input (open question, email); validate email format. The UI must tell the user about the 2000-character comment limit before they type."

**Stacking**: This mission builds on the unmerged in-harness feedback survey (PR #5540, branch `feat/in-harness-feedback-survey`). It extends `src/specify_cli/feedback/` and reuses its hidden agent handshake.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Open the feedback form on demand (Priority: P1)

A user working inside a supported harness types `/spec-kitty.feedback`. The agent asks the feedback questions through the harness's own question UI and submits the answers through the existing hidden agent handshake. The weekly throttle is skipped because the user asked for the form. There is no terminal-form fallback.

**Why this priority**: It is the main new capability. Today the form appears only on throttled triggers, so users cannot give feedback when they want to.

**Independent Test**: Run the handshake as the command does (check, ask, submit) with a fake endpoint, and confirm one valid submission is sent even when the weekly throttle would suppress an offer.

**Acceptance Scenarios**:

1. **Given** the throttle has already claimed this week's offer, **When** the user runs `/spec-kitty.feedback`, **Then** the form is still shown and the agent starts the survey.
2. **Given** feedback is disabled or no endpoint is configured, **When** the user runs the command, **Then** the agent tells the user plainly that feedback is unavailable, and nothing is sent.
3. **Given** the command is installed for any of the 13 slash-command agents and the 4 Agent Skills agents, **When** the user lists commands, **Then** `/spec-kitty.feedback` is present and generated from a single pack source.

---

### User Story 2 - Rating accepts only 1 to 5 (Priority: P1)

The rating answer is accepted only if it is one of the integers 1, 2, 3, 4 or 5. Anything else is rejected and the user is asked the rating question again.

**Why this priority**: It is an explicit requirement, and an out-of-range rating corrupts the data.

**Independent Test**: Feed each invalid rating to the shared validator and to the agent submit path, and confirm each is refused with a structured error and nothing is sent.

**Acceptance Scenarios**:

1. **Given** a rating of `0`, `6`, `-1`, `4.5`, `"five"`, `"5 stars"`, `true` or an empty value, **When** it is submitted, **Then** it is rejected with `rating_out_of_range` and no request is made.
2. **Given** a rating of `1` through `5`, **When** it is submitted, **Then** it is accepted unchanged.

---

### User Story 3 - Comment is sanitized and its limit is visible (Priority: P1)

The comment prompt states the 2000-character limit before the user types. Whatever the user types is cleaned: control characters, terminal escape sequences and invisible characters are removed, and Unicode and whitespace are normalized. Markup is left as typed. Over-length text is truncated to the limit and the user is told.

**Why this priority**: The limit notice is an explicit requirement, and unsanitized text could carry terminal escape sequences or hidden characters.

**Independent Test**: Check that every comment prompt contains the limit before input, and submit crafted strings to confirm what is stripped and what is kept.

**Acceptance Scenarios**:

1. **Given** the comment question is displayed in any flow, **When** the user has not typed yet, **Then** the prompt already says the comment can be at most 2000 characters.
2. **Given** a comment containing ANSI escape sequences, NUL or other control characters, and zero-width characters, **When** it is submitted, **Then** the sent text contains none of them.
3. **Given** a comment `use <b>bold</b> and a < b`, **When** it is submitted, **Then** the text is sent as typed.
4. **Given** a comment longer than 2000 characters, **When** it is submitted, **Then** it is truncated to 2000 characters and the user is told it was shortened.

---

### User Story 4 - Email is strictly validated (Priority: P2)

The email is optional. If provided, it must be one well-formed address. A malformed value is rejected and the user is asked again, or can skip. The value is never silently "fixed".

**Why this priority**: It is an explicit requirement, but the field is optional so it affects fewer submissions.

**Independent Test**: Feed valid and invalid addresses to the shared validator.

**Acceptance Scenarios**:

1. **Given** `a@b`, `a b@example.test`, `a@@example.test`, `a@example.test, b@example.test`, an address with control characters, or one over 254 characters, **When** it is submitted, **Then** it is rejected with `email_malformed`.
2. **Given** `person@example.test` or an empty value, **When** it is submitted, **Then** it is accepted (empty means no email).

---

### User Story 5 - One validator for every flow (Priority: P2)

The slash command, the terminal form, the inline survey hooks and the `--agent-submit` handshake all use the same validator, so no flow accepts what another rejects.

**Why this priority**: It prevents a weaker path from bypassing the rules.

**Independent Test**: Run the same table of valid and invalid inputs through each of the four entry points and compare results.

**Acceptance Scenarios**:

1. **Given** any input from the shared test table, **When** it goes through each flow, **Then** all four flows return the same accept or reject result and the same sanitized value.

---

### Edge Cases

- Rating given as a numeric string with surrounding whitespace, such as `" 5 "`: rejected (strict).
- A comment that becomes empty after cleaning: treated as no comment.
- A comment of exactly 2000 characters: accepted unchanged. 2001 characters: truncated.
- Multi-byte characters near the limit: the count is in characters, and truncation never splits a character.
- Several invalid fields in one submission: all errors are returned together and only the failing questions are re-asked.
- The user cancels midway: nothing is sent.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | On-demand feedback command | As a user, I want to run `/spec-kitty.feedback` so that I can give feedback whenever I choose. | High | Open | [build] | no |
| FR-002 | Agent-rendered form | As a user, I want the questions shown in my harness's own question UI so that I never leave my session. | High | Open | [build] | no |
| FR-003 | Throttle bypass for explicit requests | As a user, I want the form shown even if this week's offer was already used so that my request is honored. | High | Open | [build] | no |
| FR-004 | Single pack source for all harnesses | As a maintainer, I want the command defined once in the pack and generated for all supported agents so that surfaces never drift. | High | Open | [build] | no |
| FR-005 | Unavailable-feedback message | As a user, I want a clear message when feedback is disabled or has no endpoint so that I know why nothing was sent. | Medium | Open | [build] | no |
| FR-006 | Strict rating | As a maintainer, I want only the integers 1 to 5 accepted so that ratings are trustworthy. | High | Open | [ratchet] | no |
| FR-007 | Rating rejection error | As a user, I want a clear error and a re-ask when my rating is invalid so that I can correct it. | High | Open | [build] | no |
| FR-008 | Comment sanitization | As a maintainer, I want control characters, terminal escape sequences and invisible characters removed, and Unicode and whitespace normalized, so that stored text is clean. | High | Open | [build] | no |
| FR-009 | Markup preserved | As a user, I want my text kept exactly as typed apart from cleaning so that code snippets and symbols are not altered. | Medium | Open | [ratchet] | no |
| FR-010 | Comment limit shown first | As a user, I want to see the 2000-character limit before I type so that I can plan my message. | High | Open | [build] | no |
| FR-011 | Over-length handling | As a user, I want to be told when my comment is shortened so that I am not surprised. | Medium | Open | [build] | no |
| FR-012 | Strict optional email | As a maintainer, I want any provided email to be one well-formed address so that contact data is usable. | High | Open | [build] | no |
| FR-013 | Email never auto-corrected | As a user, I want an invalid email rejected rather than altered so that no wrong address is stored. | Medium | Open | [ratchet] | no |
| FR-014 | Shared validator | As a maintainer, I want one validator used by the slash command, terminal form, inline hooks and agent submit so that all flows agree. | High | Open | [build] | no |
| FR-015 | No send on invalid input | As a user, I want nothing sent when any answer fails validation so that bad data never leaves my machine. | High | Open | [ratchet] | no |
| FR-016 | Structured errors for agents | As an agent, I want machine-readable error codes for each failing field so that I can re-ask only that question. | High | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Validation speed | Validating one submission takes under 10 ms at the 95th percentile on a developer machine. | Performance | Medium | Open |
| NFR-002 | Sanitizer safety | For a table of at least 20 hostile inputs (escape sequences, NUL, bidi and zero-width characters), the output contains zero control or invisible characters. | Security | High | Open |
| NFR-003 | Flow parity | The shared input table yields identical results across all four entry points, with zero differences. | Reliability | High | Open |
| NFR-004 | Coverage | New and changed code has at least 90% line coverage. | Quality | High | Open |
| NFR-005 | Static quality | New code passes ruff check, ruff format and mypy strict with zero issues, and no function exceeds complexity 15. | Quality | High | Open |
| NFR-006 | Wording consistency | The 2000-character limit text comes from one wording source, so it is stated identically in every flow. | Maintainability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No new egress | The change must not add a new network call. Sending still uses the existing single, consented, fire-and-forget request. | Technical | High | Open |
| C-002 | Submission allowlist unchanged | The set of fields sent (`ALLOWED_KEYS`) must not grow. | Technical | High | Open |
| C-003 | Edit sources only | The command is authored in the pack source templates. Generated agent copies are never edited by hand. | Technical | High | Open |
| C-004 | Vendor-neutral wording | Specs, prompts and docs name no company other than Spec Kitty, and examples use only `example.test` or loopback hosts. | Business | High | Open |
| C-005 | Lean command surface | The command adds no new CLI flags beyond what the agent handshake needs, and the consent text stays "Send feedback". | Technical | Medium | Open |
| C-006 | Gates | Pack source edits must pass `spec-kitty doctrine regenerate-graph --check`, and the CLI-reference and completion-manifest freshness checks. | Technical | Medium | Open |
| C-007 | Stacked delivery | Work targets `feat/in-harness-feedback-survey` and ships as a draft PR. Nothing is pushed to `main`. | Business | High | Open |

### Key Entities *(include if the mission involves data)*

- **Feedback answers**: rating (1 to 5), optional comment (cleaned, at most 2000 characters), optional email (one well-formed address).
- **Validation result**: per-field outcome carrying the cleaned value or a structured error code (`rating_out_of_range`, `email_malformed`, and a notice when a comment was truncated).
- **Feedback command**: the single pack-defined `/spec-kitty.feedback` instruction generated for every supported agent.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In an end-to-end run, `/spec-kitty.feedback` produces exactly one valid submission to a fake endpoint, even when the weekly throttle is already used — [build] · no-op passable: no
- **SC-002**: 100% of the invalid-rating table (at least 10 cases) is rejected and zero requests are made — [ratchet] · no-op passable: no
- **SC-003**: 100% of the hostile-comment table has all control and invisible characters removed, while a markup sample is returned byte-for-byte unchanged — [build] · no-op passable: no
- **SC-004**: The 2000-character limit appears in the comment prompt of every flow before any input is read — [build] · no-op passable: no
- **SC-005**: 100% of the invalid-email table (at least 10 cases) is rejected and all valid cases are accepted — [build] · no-op passable: no
- **SC-006**: `/spec-kitty.feedback` exists for all 13 slash-command agents and the 4 Agent Skills agents, generated from one pack source — [build] · no-op passable: no
