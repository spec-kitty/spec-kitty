# Mission Specification: doctor decisions reports tolerated duplicate openings

**Mission Branch**: `issue-6764-doctor-decisions-duplicate-openings`
**Created**: 2026-10-30
**Status**: Draft
**Input**: User description: "spec-kitty/spec-kitty#6764 — doctor decisions: report tolerated duplicate DecisionPointOpened rows as an informational finding"

**Tracker issue**: spec-kitty/spec-kitty#6764 (claimed by Ivan-Melck). Guidance from
the operator: informational only, exit code unchanged, `--json` shape consistent with
the other findings, mission/decision named, read-only.

## Context

`spec-kitty agent decision open` writes one `DecisionPointOpened` row per decision. Two
concurrent identical opens, or a retry of an interrupted open, could each append a row;
those rows are equal except `recorded_at`. #4848 (PR #6762, merged 2026-10-29) fixed the
write side and taught the read side to fold such duplicates: the canonical fold
(`specify_cli.decisions.index_fold._select_opened_event`) keeps the earliest opening and
`doctor decisions --repair` rebuilds the index without rewriting the log.

That tolerance is correct but silent. `doctor decisions` says nothing about the rows, so
an operator cannot tell a log written before the fix from a log written by the fixed
writer, and cannot see tolerated drift at all. The package reducer
(`spec_kitty_events.decisionpoint.reduce_decision_point_events`) records a second opening
as an `invalid_transition` anomaly; the CLI reports nothing.

#4848's pre-PR squad explicitly deferred this (`kitty-specs/decision-log-integrity-01M5ZAW0/research.md`
R-7: "Doctor silently tolerates identical duplicates (no informational finding) —
Deferred: optional; no reader currently needs it"). This mission pays that debt.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See tolerated duplicate openings in the doctor report (Priority: P1)

An operator runs `spec-kitty doctor decisions --mission <slug>` on a mission whose event
log holds two identical `DecisionPointOpened` rows for one decision (written before
#4848). Today the command prints `ok: ... decisions index matches the event log` and
exits 0, with no hint that the log carries a duplicate. After the change the command
still prints the clean verdict and exits 0, and additionally names the decision as an
informational finding.

**Why this priority**: This is the whole mission. Without it the tolerated drift stays
invisible.

**Independent Test**: Build a mission whose `status.events.jsonl` holds two identical
openings for one decision, run the real `doctor decisions --json` CLI, and assert the
verdict is still clean (exit 0, `clean: true`) while `duplicate_openings_tolerated`
contains that decision id.

**Acceptance Scenarios**:

1. **Given** a mission whose event log holds one `DecisionPointOpened` row per decision,
   **When** the operator runs `doctor decisions`, **Then** the report shows no duplicate
   finding (the JSON field is an empty list) and the exit code is unchanged.
2. **Given** a mission whose event log holds two `DecisionPointOpened` rows for one
   decision that are equal apart from `recorded_at`, **When** the operator runs
   `doctor decisions`, **Then** the report is still clean and exits 0 (no error), and the
   decision id is named in the informational finding on both the human and the `--json`
   surface.
3. **Given** the same mission, **When** the operator runs `doctor decisions --repair`,
   **Then** the repair behaves exactly as before (the log is never rewritten) and the
   duplicate finding is still reported on the post-repair report.

### User Story 2 - Keep the informational finding honest and single-sourced (Priority: P2)

A reviewer must be able to trust that the finding means exactly what the fold tolerates:
identical openings, and nothing else. Openings that differ beyond `recorded_at` must stay
a malformed fold (the error path), never an informational duplicate.

**Why this priority**: A second, independently written duplicate rule would drift from the
fold and eventually report something the fold refuses, or miss something it accepts.

**Independent Test**: Feed the doctor a decision with two openings that differ in
`question`; assert the decision lands in `malformed_folds` and NOT in
`duplicate_openings_tolerated`.

**Acceptance Scenarios**:

1. **Given** a decision whose two openings differ beyond `recorded_at`, **When** the
   doctor runs, **Then** the decision is a malformed fold and is absent from the
   informational duplicate list.
2. **Given** three identical openings for one decision, **When** the doctor runs, **Then**
   the decision is named once in the informational list.

### Edge Cases

- A decision with duplicates that is MISSING from the index: the duplicate finding is
  still reported (it is a property of the log, not of index membership), and
  `missing_from_index` is unchanged.
- A decision with duplicates whose index entry disagrees on status: both the stale-status
  finding and the duplicate finding are reported; neither suppresses the other.
- A log with no decision events at all, or an unreadable/missing log (unmaterialized
  coordination worktree): no duplicates, empty list, no crash — the existing degradation
  path is unchanged.
- A `--repair` run that refuses to rewrite a slot_key-origin attribution: the duplicate
  finding is reported alongside the refusal, not instead of it.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Name tolerated duplicates in the human report | As an operator, I want `doctor decisions` to print the decisions whose log holds tolerated duplicate openings so that I can see drift the fold already accepts. | High | Open | [build] | no |
| FR-002 | Name tolerated duplicates in `--json` | As an operator or script, I want the same information as a `duplicate_openings_tolerated` list in the `--json` document so that I can consume it without parsing text. | High | Open | [build] | no |
| FR-003 | Stay informational: exit code and verdict unchanged | As an operator, I want the duplicate finding to never fail the command or flip `clean` so that existing automation keeps its meaning. | High | Open | [ratchet] | no — a run with duplicates must still exit 0 and report `clean: true` |
| FR-004 | Report nothing when there are no duplicates | As an operator, I want no duplicate finding on a healthy log so that the report stays quiet. | High | Open | [build] | no — paired with FR-001 on the same fixture |
| FR-005 | Derive the finding from the canonical fold rule | As a maintainer, I want the duplicate predicate to come from `index_fold` (the same rule `_select_opened_event` enforces) so that the report cannot drift from what the fold accepts. | High | Open | [ratchet] | no — differing duplicates must stay in `malformed_folds`, proven on the same fixture |
| FR-006 | Keep the duplicate finding after a repair | As an operator, I want `--repair` to still report the duplicate finding so a rebuild does not hide the log's shape. | Medium | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No extra log read | The duplicate detection adds no additional read of `status.events.jsonl` and no additional fold pass: it is computed from the event groups the diagnose path already reads, in the same per-decision loop as `malformed_folds`/`status_mismatch`. | Performance | Medium | Open |
| NFR-002 | Read-only | The diagnose path writes nothing: `status.events.jsonl` and `decisions/index.json` are byte-identical before and after a `doctor decisions` run, with and without duplicates. | Reliability | High | Open |
| NFR-003 | No measurable regression | The existing `doctor decisions` test module (`tests/decisions/test_decisions_reconciler.py`) stays green and the command's wall time on the module's fixtures does not grow by more than 10%. | Performance | Low | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | `--repair` behaviour is out of scope | The repair path's rebuild, refusal and exit-code rules are unchanged; only the reporting is extended. | Technical | High | Open |
| C-002 | Additive JSON only | Every existing `--json` key keeps its name, type and meaning; the new key is additive, exactly as `malformed_folds`/`status_mismatch` were (#4919). | Technical | High | Open |
| C-003 | No new dependency | The finding uses the existing `index_fold` module and the already-parsed event envelopes; no new package, no new module boundary. | Technical | Medium | Open |

### Key Entities

- **Tolerated duplicate opening**: two or more `DecisionPointOpened` envelopes for one
  `decision_point_id` whose payloads are equal after removing `recorded_at`. The fold
  accepts them and folds the earliest.
- **Informational finding**: a per-decision report line/field that names a tolerated
  condition. It never changes `clean`, never changes the exit code, and never triggers a
  write.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a log holding two identical openings, `doctor decisions --json` exits 0, reports `clean: true`, and lists that decision id in `duplicate_openings_tolerated`. — [build] · no-op passable: no
- **SC-002**: For a log with no duplicates, `duplicate_openings_tolerated` is `[]` and no duplicate line is printed. — [build] · no-op passable: no
- **SC-003**: For two openings differing beyond `recorded_at`, the decision appears in `malformed_folds` and not in `duplicate_openings_tolerated`. — [ratchet] · no-op passable: no
- **SC-004**: A `doctor decisions` run leaves both `status.events.jsonl` and `decisions/index.json` byte-identical. — [ratchet] · no-op passable: no
- **SC-005**: Every pre-existing test in `tests/decisions/test_decisions_reconciler.py` passes unchanged. — [ratchet] · no-op passable: no

## Assumptions

- The duplicate predicate lives beside the fold that already applies it, in
  `specify_cli/decisions/index_fold.py`, and is exported so the doctor imports one rule
  rather than re-deriving `recorded_at` exclusion.
- "Consistent with the other findings" means: a report dataclass field, a human line next
  to the existing `malformed_folds`/`status_mismatch` lines, and a same-named JSON key —
  the shape #4919 established.
