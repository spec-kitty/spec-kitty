# Mission Specification: Issue-matrix reference over-matching

**Mission Branch**: `kitty/mission-issue-matrix-over-matching-01M81KK0`
**Created**: 2026-11-22
**Status**: Draft
**Input**: Issue #7808: hex colour values are read as issue references (bundled with #5297 and #5516, operator ruling "One Mission, all three")

## Purpose

The issue-matrix approval gate asks an operator for a verdict row for every issue reference
a Mission's artefacts carry. Three kinds of text are read as issue references the Mission owes
work for, although they are not:

- a hex colour value (`#` followed by an all-digit run, with or without a leading zero) is read as
  an issue, including the impossible issue 0 (#7808);
- a commit citation, where an issue number stands next to the backticked commit SHA that
  evidences it, is read as an implementation target (#5297);
- every `#N` in research notes, plan prose, contracts and tables, including ordinal ids such as a
  planted-break label, is read as an implementation target (#5516).

Each false positive costs an operator a hand-recorded `not-applicable` row before the first
approval. Past Missions recorded ten and ten such rows. The gate's cost grows with the quality of
the evidence a Mission cites, which is the wrong incentive.

This Mission narrows what counts as an issue reference and which references gate, so the gate
asks only for rows the Mission really owes.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Colour values are not issue references (Priority: P1)

A Mission author documents a UI palette in `research.md` or `spec.md`, with an all-zero colour
and an all-digit colour in CSS declaration form. Approval asks for no issue-matrix row for them.

**Why this priority**: issue 0 can never exist, and a colour is never an issue; this is the
cheapest, least ambiguous false positive.

**Independent Test**: discover references over a Mission directory whose artefacts carry only
colour values; the result is empty.

**Acceptance Scenarios**:

1. **Given** an artefact containing an all-zero colour (six or three zeros after `#`), **When**
   references are discovered, **Then** no reference is returned for it.
2. **Given** an artefact containing `color: #` followed by six digits with no leading zero,
   **When** references are discovered, **Then** no reference is returned for it.
3. **Given** a line that mentions a CSS word and also cites a real issue as `#N`, **When**
   references are discovered, **Then** the real issue is still returned.

### User Story 2 - Commit citations are cited, not owed (Priority: P1)

A remediation Mission's `spec.md` explains each re-pin by citing the commit that caused it,
in the shape ``(`<sha>`, #N)``. Approval does not ask for a row for those issues.

**Why this priority**: remediation and re-pin Missions cite causal commits on nearly every row.

**Independent Test**: classify an occurrence whose line carries a backticked 7-40 character hex
SHA next to the citation; the class is the non-gating PR/commit class.

**Acceptance Scenarios**:

1. **Given** a `spec.md` line ``(`<9-char sha>`, #N)``, **When** classified, **Then** the reference
   is non-gating (PR/commit reference).
2. **Given** a `spec.md` line where a backticked SHA sits far from the citation, or the backticked
   token is all digits, **When** classified, **Then** the reference still gates (fail-safe).

### User Story 3 - Scope decides what gates (Priority: P1)

A Mission's `research.md` and `plan.md` mention issue numbers as background, and its quickstart
labels planted breaks with ordinal ids. Approval asks for rows only for references in `spec.md`
and `tasks/`, and for any reference a closing keyword names in any scanned artefact.

**Why this priority**: operator ruling "Scope decides"; it removes the largest class of false
positives.

**Independent Test**: discover references over a Mission whose `research.md` carries a
planted-break label and whose `spec.md` carries a closing keyword; only the closing-keyword
reference gates.

**Acceptance Scenarios**:

1. **Given** `research.md` text "Break #N", **When** references are discovered, **Then** the
   reference is returned as cited (non-gating).
2. **Given** `spec.md` text "Closes #N", **When** references are discovered, **Then** the reference
   gates.
3. **Given** `plan.md` text "Fixes #N", **When** references are discovered, **Then** the reference
   gates (a closing keyword gates in any scanned artefact).
4. **Given** a bare `#N` in `spec.md` or a `tasks/` file, **When** references are discovered,
   **Then** the reference gates as before (default-gating fail-safe inside the gating scope).
5. **Given** "does not fix #N" in `plan.md`, **When** references are discovered, **Then** the
   reference is cited (a negated closing keyword is not a closing statement).

### Edge Cases

- A 4-digit `#RGBA` colour outside declaration form is indistinguishable from a 4-digit issue and
  stays a reference (a keyword-anywhere filter would silently drop real references).
- A number with a leading zero is never an issue reference, in any of the three number patterns
  (the general detector, the Mission source-description lead and the closing keyword).
- The Mission's own source issue still gates wherever it is cited (the existing source-issue
  promotion is unchanged).
- A closing keyword wins over a commit SHA beside the same citation.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Requirement | Status | Delivery | No-op passable? |
|----|-------------|--------|----------|-----------------|
| FR-001 | A `#` followed by a digit run that starts with `0` is never an issue reference, in every issue-number pattern. | Draft | [build] | no |
| FR-002 | An all-digit hex colour in CSS declaration form (a colour-bearing property or a custom property, a colon, then the value) is never an issue reference; a real reference on the same line is still found. | Draft | [build] | no |
| FR-003 | An occurrence whose citation has a backticked 7-40 character hex SHA (at least one letter a-f) within a short window on either side classifies as the non-gating PR/commit class. | Draft | [build] | no |
| FR-004 | An occurrence found outside the gating scope (`spec.md`, `tasks/`) classifies as cited (non-gating), unless a closing keyword leads into its citation. | Draft | [build] | no |
| FR-005 | A non-negated closing keyword (close/fix/resolve family) leading into a citation classifies that occurrence as an implementation target in any scanned artefact, ahead of every demoting rule. | Draft | [build] | no |
| FR-006 | The closing-keyword and source-description patterns recognise numbers only through the one canonical detector and its filter; there is one number-recognition authority and one classifier. | Draft | [build] | no |
| FR-007 | ADR `2026-09-20-1` records the scope rule as an amendment to its FR-011 fail-safe default. | Draft | [build] | no |

### Non-Functional Requirements

| ID | Requirement | Status |
|----|-------------|--------|
| NFR-001 | Classification stays pure and deterministic: discovery reads no file beyond those it reads today. | Draft |
| NFR-002 | Every reference that gated before and is in `spec.md` or `tasks/` and is not a colour, leading-zero number or commit citation still gates (no new fail-open path inside the gating scope). | Draft |
| NFR-003 | New and changed code passes ruff, ruff format and mypy with no suppressions; diff coverage at least 90%. | Draft |

### Constraints

| ID | Constraint | Status |
|----|------------|--------|
| C-001 | No new `GatingClass` value: "cited" maps to the existing non-gating context-only class, so the persisted vocabulary and scaffold verdicts are unchanged. | Draft |
| C-002 | Direct `Occurrence(source_file, line_text)` construction keeps today's outcome (in gating scope by default). | Draft |
| C-003 | Backticks stay an allowed citation prefix. | Draft |

### Key Entities

- **Occurrence**: one site where an issue number was found; gains whether its artefact is inside
  the gating scope.
- **GatingClass**: unchanged three-value vocabulary (implementation target, context only,
  PR/commit reference).

## Success Criteria *(mandatory)*

| ID | Criterion | Delivery | No-op passable? |
|----|-----------|----------|-----------------|
| SC-001 | Colour values in any scanned artefact produce zero references. | [build] | no |
| SC-002 | A commit-citation line in `spec.md` produces zero gating references. | [build] | no |
| SC-003 | A planted-break label in `research.md` produces a cited reference; a closing keyword in `spec.md` produces a gating one. | [build] | no |
| SC-004 | The existing issue-matrix test families stay green unchanged, except tests that pinned the old over-matching, which are re-pinned with a stated reason. | [ratchet] | yes |

## Assumptions

- A real issue number in this repository never starts with `0`.
- Six-digit all-digit values outside CSS declaration form remain references (fail-safe).
