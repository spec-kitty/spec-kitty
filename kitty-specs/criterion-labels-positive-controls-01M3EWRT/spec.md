# Mission Specification: Criterion delivery labels and positive-control review doctrine (#5061)

**Mission Branch**: `claude/research-squad-remediation-mission-fvdk93`
**Created**: 2026-09-26
**Status**: Draft
**Input**: Remediate #5061 — spec template per-criterion delivery labels `[build]`/`[ratchet]`/`[folded]` plus a "no-op passable?" mark; a new dedicated review tactic requiring positive controls on the same fixture for refusal/absence assertions, half-by-half proof for compound fixes, and production-path non-vacuity; the software-dev review prompt names the tactic; refresh the `.kittify` overrides.

## Intent Summary

- **Primary actors**: (1) the *spec author* (operator or agent running `/spec-kitty.specify`) who writes
  requirements and success criteria; (2) the *reviewer* (agent running the software-dev review step) who judges
  whether a work package's tests actually prove its criteria.
- **Trigger**: a mission is specified, then a work package is reviewed.
- **Desired outcome**: every requirement row declares whether it delivers new behaviour, pins existing behaviour,
  or is satisfied by another row, and whether a do-nothing change would already satisfy it. A reviewer has one
  named doctrine artifact that requires refusal/absence assertions to carry a positive control on the same
  fixture, compound fixes to be proven half by half, and non-vacuity tests to exercise the production path.
- **Invariant**: adding a label must never change which requirement ids are declared or how requirement
  coverage is gated.
- **Canonical terms**: *delivery label* (`[build]`, `[ratchet]`, `[folded]`), *no-op passable*, *positive control*,
  *half-by-half proof*. The label set is defined once, in the new tactic; the template legend points to it.
- **Operator decisions** (resolved Decision Moments): host = a **new dedicated tactic**
  (DM-01M3EWS6CVECE8C6JZ0QP6FH0S); the repo's `.kittify/overrides` copies are **refreshed** too
  (DM-01M3EWS93W9MRFDJV1QG1Y5WZK), and the refresh covers **every drifted override** under
  `.kittify/overrides/missions/software-dev/` that has a built-in counterpart (DM-01M3EX8WE96MHDTQTEE5M8WT85).
- **Evidence base**: the #5061 triage brief, the pre-spec research squad (`research/pre-spec-squad.md`) and the
  post-spec squad (`research/post-spec-squad.md`).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Spec author labels each criterion (Priority: P1)

A spec author filling the software-dev spec template sees, next to every functional requirement, a *Delivery*
column and a *No-op passable?* column, with a legend explaining the three labels and what a `yes` obliges.

**Why this priority**: The tracer evidence (13 of 29 requirements passable by a no-op in one mission) shows the
defect starts at authoring time; labelling cut undeclared no-ops from 45% to 6% where it was tried.

**Independent Test**: Scaffold a new software-dev spec and confirm the columns, the legend and one filled example
are present, and that the scaffold is still not treated as substantive.

**Acceptance Scenarios**:

1. **Given** a freshly scaffolded spec, **When** the author reads the Functional Requirements table, **Then** it
   shows `Delivery` and `No-op passable?` columns after `Status`, a legend, and one filled example row.
2. **Given** a requirement row labelled `[ratchet]` with `yes` in *No-op passable?*, **When** the author follows the
   legend, **Then** it tells them to reword the row or pair it with a positive control.
3. **Given** an unfilled scaffold row carrying the label placeholder, **When** the spec gate checks for substantive
   content, **Then** the scaffold is still reported as not substantive, **and** the same scaffold with only Title and
   User Story filled (labels still placeholders) is reported as substantive (positive control).
4. **Given** the filled example in the legend, **When** requirement ids are parsed from the unfilled template,
   **Then** the example declares no id (the template declares exactly the placeholder ids it declared before).

### User Story 2 - Labelled requirements keep their identity (Priority: P1)

Requirement-coverage tooling (`map-requirements`, `finalize-tasks`) keeps recognising every labelled row.

**Why this priority**: A label that silently undeclares an FR removes it from coverage gating — a worse defect than
the one being fixed.

**Independent Test**: One fixture holds a correctly labelled row and a mis-placed-label row (label inside the id
cell). The parser declares the first and not the second; running the labelled spec through the production
requirement-coverage seam (`map-requirements`) yields the same functional set as its unlabelled twin.

**Acceptance Scenarios**:

1. **Given** a spec whose FR rows carry trailing label columns, **When** requirement ids are parsed, **Then** every
   FR id is declared exactly as without the columns.
2. **Given** the same fixture's row whose label sits inside the id cell, **When** requirement ids are parsed,
   **Then** that id is not declared, while the correctly labelled row in the same fixture is (the pair proves the
   probe discriminates placement).
3. **Given** a labelled spec and its unlabelled twin, **When** each is run through the requirement-coverage command
   path, **Then** both yield the same declared functional set.

### User Story 3 - Reviewer applies one non-vacuity tactic (Priority: P1)

A reviewer reviewing a software-dev work package is pointed, by the review prompt and the review action's
doctrine context, to one tactic that tells them how to prove a test is not vacuous.

**Why this priority**: Without a named artifact, reviewers approve refusal probes that could not have seen the
thing they assert is absent, and compound fixes where one half is never exercised.

**Independent Test**: Render the review prompt from the built-in pack (not the override) and confirm the tactic id
is named and that the named id resolves through `spec-kitty charter context --include tactic:<id>`; confirm the
regenerated doctrine graph has a direct scope edge from the software-dev review action to the tactic.

**Acceptance Scenarios**:

1. **Given** the built-in review prompt, **When** it is rendered for an agent, **Then** it contains a non-vacuity
   check naming the tactic id and its fetch command.
2. **Given** the regenerated doctrine graph, **When** the software-dev review action's context is resolved at
   compact depth, **Then** the new tactic is present through a direct scope edge (not via a `suggests` chain).
3. **Given** the tactic, **When** a reviewer reads it, **Then** it states the three rules (same-fixture positive
   control, half-by-half proof, production-path non-vacuity) and defines the delivery labels.

### User Story 4 - This repository dogfoods the change (Priority: P2)

Spec Kitty's own repository shadows the software-dev mission with local overrides that have drifted from the
built-in sources; after this mission every override with a built-in counterpart equals that source, so the core
team runs the same doctrine the product ships.

**Independent Test**: Compare every file under `.kittify/overrides/missions/software-dev/` with its built-in
counterpart and resolve the spec template and review prompt through the project resolver.

**Acceptance Scenarios**:

1. **Given** an override file with a built-in counterpart, **When** it is compared after the refresh, **Then** it is
   byte-identical to the built-in source.
2. **Given** an override with no built-in counterpart, **When** the refresh runs, **Then** it is left untouched and
   listed in the follow-up issue.
3. **Given** this repository, **When** the review prompt and review action index are resolved, **Then** both carry
   the new tactic.

### Edge Cases

- A row whose *No-op passable?* is `yes` and that is intentionally kept (e.g. a `[ratchet]` pinning existing
  behaviour): the legend requires a named positive control rather than forbidding the row.
- A `[folded]` row: the legend requires naming the row that satisfies it, so folding cannot hide a gap.
- Success criteria are bullets, not a table: labels go as a trailing suffix after the criterion text.
- Legacy specs without the columns keep parsing and gating exactly as before (labels are optional).

## Requirements *(mandatory)*

Delivery labels (defined in tactic `acceptance-criteria-non-vacuity`): `[build]` new behaviour, `[ratchet]`
existing behaviour pinned against regression, `[folded]` satisfied by another item. *No-op passable?* `yes`
means a do-nothing change would pass the row's check, so it is reworded or paired with a positive control.

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Template delivery columns | As a spec author, I want the software-dev spec template's Functional Requirements table to carry trailing `Delivery` and `No-op passable?` columns, with a legend and one filled example row, so that every requirement declares what it delivers and whether a no-op would satisfy it. | High | Open | [build] | no |
| FR-002 | Success-criterion labels | As a spec author, I want the template's success criteria to show a trailing delivery-label and no-op suffix, so that measurable outcomes are labelled the same way as requirements. | Medium | Open | [build] | no |
| FR-003 | Labelled rows stay declared | As a mission operator, I want a labelled requirement row to remain declared by the requirement-id parser and to yield the same functional set through the production requirement-coverage path as its unlabelled twin, proven on one fixture that also holds a mis-placed-label row that is not declared, so that labelling never drops a requirement from coverage. | High | Open | [ratchet] | yes — paired with the mis-placed-label row on the same fixture |
| FR-004 | Scaffold stays non-substantive | As a mission operator, I want the live spec-template scaffold (including its label placeholders and filled example) to still be reported as not substantive and to declare exactly the placeholder ids it declared before, so that the new columns cannot let an unfilled spec pass the spec-commit boundary or add a phantom requirement. | High | Open | [ratchet] | yes — paired with the same scaffold with Title/User Story filled, which is substantive |
| FR-005 | Dedicated non-vacuity tactic | As a reviewer, I want one built-in tactic that requires refusal/absence assertions to be paired with a positive control on the same fixture, compound fixes to be proven half by half, and non-vacuity tests to exercise the production path, and that defines the delivery labels and the no-op mark, so that there is one canonical authority for these rules. | High | Open | [build] | no |
| FR-006 | Tactic reaches the review action | As a reviewer, I want the new tactic listed in the software-dev review action's doctrine so that the regenerated doctrine graph carries a direct scope edge from the review action to it, so that the review context surfaces it. | High | Open | [build] | no |
| FR-007 | Review prompt names the tactic | As a reviewer, I want the software-dev review prompt to carry a non-vacuity check that names the tactic id and its fetch command, and that named id to resolve through the fetch command, so that every review applies it. | High | Open | [build] | no |
| FR-008 | Sibling tactics point to it | As a doctrine curator, I want `acceptance-test-first` and `atdd-adversarial-acceptance` to reference the new tactic from the step where acceptance or refusal assertions are written, without copying its content, so that authors reach the rule where they need it. | Medium | Open | [build] | no |
| FR-009 | Specify guidance uses the columns | As a spec author running `/spec-kitty.specify`, I want the specify prompt's requirement-generation guidance to ask for the delivery label and no-op mark on each FR row and success criterion, so that generated specs actually use the columns. | Medium | Open | [build] | no |
| FR-010 | Repository overrides refreshed | As a core-team member dogfooding in this repository, I want every file under `.kittify/overrides/missions/software-dev/` that has a built-in counterpart to be byte-identical to that counterpart after this mission (including the new tactic, template and prompt changes), with overrides lacking a counterpart left untouched and listed for follow-up, the inert deprecated `expected-artifacts.yaml` override deleted (DM-01M3EXVSGFRQ8YKVFCCBWVSVZD), and any override line newer than its built-in source ported into the built-in source first, so that missions run here use the doctrine the product ships. | Medium | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No coverage regression | 0 existing mission specs change their declared requirement-id set (before/after diff over `kitty-specs/*/spec.md`) and the bare-prose corpus ratchet stays green with no baseline bump. Ratchet; no-op passable by design, controlled by FR-003's mis-placed-label row. | Reliability | High | Open |
| NFR-002 | Doctrine integrity | 100% of doctrine, charter and doctrine-graph freshness/manifest tests pass after regeneration; the tactic validates against the tactic schema with 0 errors. | Reliability | High | Open |
| NFR-003 | Terminology canon | The terminology guard reports 0 violations on all changed prose. | Maintainability | High | Open |
| NFR-004 | Lint and types | 0 new `ruff` / `ruff format` / `mypy` findings on changed Python files. | Maintainability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Consumer pack tier | All doctrine and template changes land in `packs/built-in/` (they govern consumers); nothing moves to `packs/internal/`. | Technical | High | Open |
| C-002 | No gate enforcement | The labels are guidance only; no gate may refuse a spec for a missing or wrong label. | Business | High | Open |
| C-003 | No relabelling | Past missions' specs are not relabelled. | Business | Medium | Open |
| C-004 | Label placement | A label never appears inside or before the requirement-id cell, and FR bullet/heading forms get no inline label; the id-parser patterns are not widened. | Technical | High | Open |
| C-005 | Edit sources only | Only source templates/prompts and the declared overrides are edited; generated agent copies are not. | Technical | High | Open |
| C-006 | Single definition | The delivery labels and the no-op mark are defined in exactly one artifact (the new tactic); other surfaces reference it and may carry at most a one-line gloss explicitly marked as a summary of that tactic. | Technical | High | Open |
| C-007 | Example declares nothing | The template's filled example uses an id that the requirement-id parser does not declare (e.g. `FR-EXAMPLE`), so it never adds a phantom requirement or makes the scaffold substantive. | Technical | High | Open |

### Key Entities

- **Delivery label**: per-criterion tag with values `[build]`, `[ratchet]`, `[folded]`.
- **No-op passable mark**: per-criterion `yes`/`no`; `yes` obliges rewording or a named positive control.
- **Positive control**: a check on the same fixture that proves the probe can observe the thing a refusal/absence
  assertion says is missing.
- **Half-by-half proof**: for a fix made of several independent changes, reverting any one change turns a test red.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A newly scaffolded software-dev spec shows the two label columns, the legend and exactly one filled example row. — [build] · no-op passable: no
- **SC-002**: 100% of requirement ids declared in existing mission specs before the change are still declared after it. — [ratchet] · no-op passable: yes (paired with the mis-placed-label control in FR-003)
- **SC-003**: A reviewer can reach the non-vacuity rules from the review prompt in one fetch command. — [build] · no-op passable: no
- **SC-004**: The three rules and the label definitions exist in exactly one doctrine artifact. — [build] · no-op passable: no

## Assumptions

- `acceptance-criteria-non-vacuity` is the tactic id (testing category); the operator may rename it at review.
- Tracker hygiene is part of closeout: #5061 gets a comment naming this mission; the broader override-drift gap
  and the coordination-worktree materialization friction hit during specify are filed as follow-up issues.

## Out of Scope

- Enforcing labels in any gate; relabelling past missions; the documentation, research and plan mission spec
  templates (only software-dev is labelled); architectural-gate non-vacuity (already covered by
  `architectural-gate-non-vacuity`); the accept lane-gate bug (see #4891); the ATDD red-shape sibling (see #5068) under parent epic #5107.
