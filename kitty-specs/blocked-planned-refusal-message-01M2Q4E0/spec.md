# Mission Specification: Source-aware unblock refusal message

**Mission Branch**: `issue-3937-blocked-planned-refusal-message`  
**Created**: 2026-09-17  
**Status**: Draft  
**Input**: GitHub issue #3937 (F-51, P0/MVP) — "Failed implement claim leaves WP blocked with no sane unblock path"

## Context

When an operator tries to move a work package back to `planned`
(`spec-kitty agent tasks move-task <WP> --to planned`) without a review-feedback
file, the CLI refuses with a single, **source-agnostic** message:

> ❌ Moving <WP> to 'planned' requires review feedback. … This requirement cannot be bypassed with --force.

The refusal is emitted by `_guard_planned_rollback` (the guard that sits before
the state machine on the move path). It reads neither the work package's current
lane nor `--force`, so a **blocked** work package is told to fabricate a review
finding — even though review feedback would not help and the honest recovery is
to resume with `--to in_progress` (or cancel). This is the reported defect
(F-51). Issue #3937's sibling defect F-50 (a failed `implement` claim
manufacturing an unrecoverable `blocked`) already shipped in #4245 and is **out
of scope** here.

A prior attempt at F-51 was implemented, reviewed, and then **cut during
landing** because it turned the guard into a source-scoped early-return: for
`genesis`, `blocked`, `done`, and `canceled` the move fell through to the state
machine, where `--force` (often auto-supplied for `done` by backward-promotion)
overrode a non-existent edge and **resurrected a terminal, merged work package
to `planned`**. This mission redoes F-51 as a **message-only** change that keeps
the gate unconditional and force-proof.

**Operator decision (recorded 2026-09-17, decision `01M2Q4F897ANB84HA6EHA9DG98`):**
the state machine's allow/deny rules are **not** changed. `blocked → planned`
stays disallowed by design (`planned` means "not started"; a blocked work
package keeps its claim and resumes via the one-hop `blocked → in_progress`). The
message is made source-aware on a reachability basis.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Blocked work package gets the honest recovery path (Priority: P1)

An operator resolving a blocked work package runs `move-task <WP> --to planned`
and is refused. Today the refusal tells them to write a review-feedback file,
which is the wrong instrument. They need to be told the transition's real legal
targets so they can self-recover.

**Why this priority**: This is the reported P0/MVP defect. In the hosted factory
operators depend on these prompts to self-recover; the misleading message costs
round-trips and, in the original report, drove operators to fabricate a review
finding.

**Independent Test**: Invoke the move decision from a `blocked` source with no
review-feedback file and assert the refusal names `--to in_progress` (and
`--to canceled`) and does **not** demand review feedback, while the work package
stays `blocked`.

**Acceptance Scenarios**:

1. **Given** a work package in `blocked`, **When** the operator runs
   `move-task --to planned` with no review-feedback file, **Then** the command
   exits non-zero, the work package stays `blocked`, and the message names the
   legal targets from `blocked` (`in_progress`, `canceled`) and points to
   `--to in_progress` as the resume path — without citing review feedback.
2. **Given** a work package in `blocked`, **When** the operator adds `--force`,
   **Then** the refusal is unchanged and the work package stays `blocked`.

---

### User Story 2 - Terminal work packages cannot be resurrected (Priority: P1)

A `done` or `canceled` work package must never be moved back to `planned`. The
message change must not weaken this: the guard stays the sole, unconditional,
force-proof gate on the move-to-`planned` path.

**Why this priority**: This is the exact regression that cut the first F-51
attempt. A flagless `move-task done --to planned` self-manufactures the force
the state machine's override needs (backward auto-promotion), so if the guard
ever lets a terminal source through, a merged work package is silently
resurrected with a `force=true` event and a reason the operator never wrote.

**Independent Test**: Invoke the move decision from `done` and `canceled`
sources, with and without `--force`, and assert every case is refused with the
lane unchanged and no force/rewind event emitted.

**Acceptance Scenarios**:

1. **Given** a work package in `done`, **When** the operator runs
   `move-task --to planned` with **no flags**, **Then** it is refused, stays
   `done`, and no forced-rewind event is emitted.
2. **Given** a work package in `done`, **When** the operator adds `--force`,
   **Then** it is still refused and stays `done`.
3. **Given** a work package in `canceled`, **When** the operator runs
   `move-task --to planned` with or without `--force`, **Then** it is refused
   and stays `canceled`.

---

### User Story 3 - Legitimate review rollback still works and reads correctly (Priority: P2)

A reviewer rejecting work rolls the work package back from a review-family lane
to `planned` by supplying a review-feedback file. That path — and its refusal
wording when the file is missing — must be preserved unchanged.

**Why this priority**: Review rollback is the guard's original, legitimate
purpose. The source-aware split must not disturb it; the review-family message
stays as-is so existing behavior and its pinning test remain green.

**Independent Test**: From an `in_review` source, assert a valid non-empty
review-feedback file yields a successful move to `planned` (exit 0), and a
missing file yields the existing "requires review feedback" refusal.

**Acceptance Scenarios**:

1. **Given** a work package in `in_review`, **When** the operator runs
   `move-task --to planned` with a valid non-empty review-feedback file,
   **Then** the move succeeds (exit 0) and the work package is `planned`.
2. **Given** a work package in `in_review`, **When** no review-feedback file is
   supplied (with or without `--force`), **Then** the refusal still names the
   review-feedback requirement, including that it cannot be bypassed with
   `--force`.
3. **Given** a work package in `blocked`, **When** the operator supplies a
   fabricated (non-empty) review-feedback file, **Then** the move is still
   refused and the work package stays `blocked` (a review artifact cannot
   launder a structurally illegal transition).

### Edge Cases

- **`genesis` source**: `planned` *is* reachable from `genesis` (seed edge), so
  it stays in the review-feedback-message partition and remains refused without
  feedback — with or without `--force`. It must not fall through to the state
  machine.
- **`uninitialized` source**: has no legal targets; refusal must not raise or
  emit a malformed target list.
- **Lane alias input**: a source lane supplied via an alias (e.g. `doing`) must
  resolve before the legal-target lookup so the message is computed from the
  canonical lane.
- **Empty legal-target set** (`done`, `canceled`): the message must read
  correctly (name the source as terminal / not-reachable) rather than printing
  an empty list.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Source-aware refusal for unreachable-`planned` lanes | As an operator, when I try to move a `blocked`, `canceled`, or `done` work package to `planned`, I want the refusal to name the legal targets for that lane (e.g. `blocked` → resume via `--to in_progress` or cancel via `--to canceled`) so that I know the real recovery path instead of being told to provide review feedback. | High | Open |
| FR-002 | Review-family refusal preserved | As a reviewer, when I try to move a work package to `planned` from a lane where `planned` is reachable (`in_review`, `in_progress`, `approved`, `genesis`) without a review-feedback file, I want the existing "requires review feedback … cannot be bypassed with --force" wording so that legitimate review rollback guidance is unchanged. | High | Open |
| FR-003 | Legal targets sourced from the state machine | As a maintainer, I want the legal-target list computed from the source lane's own `allowed_targets()` accessor (read-only) so that the message stays correct if the lane's targets change and no allow/deny logic is duplicated. | Medium | Open |
| FR-004 | Blocked resume path named explicitly | As an operator, I want the `blocked` refusal to name `--to in_progress` as the resume path (not merely list target lanes) so that I can act without consulting docs. | Medium | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Unconditional, force-proof gate | Every `move-task --to planned` without a valid, non-empty review-feedback file is refused (exit non-zero, lane unchanged) for **all** source lanes with and without `--force`; 0 of the source×flag cases reach the state machine. Verified by a regression matrix covering `{done, canceled, genesis, blocked, in_review}` × `{none, --force}`. | Correctness/Security | High | Open |
| NFR-002 | No resurrection event | A refused `move-task done --to planned` (flagless, i.e. the backward auto-force path) emits **no** forced-rewind status event; the event log gains no `force=true` transition out of `done`. | Correctness | High | Open |
| NFR-003 | State machine unchanged | `wp_state.py` allow/deny (`allowed_targets`, force-override) and the finalize-order tables are byte-unchanged; the state-machine parity baseline (`fsm_parity_baseline.jsonl`) changes 0 rows. | Reliability | High | Open |
| NFR-004 | No regression in existing pins | The existing pinning assertions on the review-family refusal text (`test_tasks_transition_core.py`) stay green; the change is additive/source-branched, not a rewrite of the review-family branch. | Reliability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Message-enrichment only | `_guard_planned_rollback` stays unconditional: the four feedback-field checks (allow/deny) are unchanged. No source-scoped early-return; every branch for a `--to planned` move without valid feedback returns a refusal. | Technical | High | Open |
| C-002 | No guard reordering | The `_GUARDS` tuple order and identity are unchanged (guard-index constants depend on it). | Technical | High | Open |
| C-003 | Scope boundary | Out of scope: F-50 (shipped #4245), issue #1711 (cause-tagged `blocked → in_progress` recovery driver), any state-machine allow/deny change (incl. legalizing `blocked → planned`), and the `blocked → planned` decision recorded 2026-09-17. | Business | High | Open |
| C-004 | Terminology canon | New message prose uses canonical lane names and the `--to` vocabulary; no forbidden legacy terms. | Technical | Medium | Open |

### Key Entities

- **Move request**: carries the target lane, the source lane (`old_lane`), the
  `--force` flag, and the review-feedback file facts. The guard reads the source
  lane (read-only) to shape the message; it does not use it to decide whether to
  refuse.
- **Lane state**: exposes a read-only `allowed_targets()` set per lane; the
  source of truth for the legal-target list in the enriched message.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator moving a `blocked` work package to `planned` without a
  review-feedback file sees a message that names `--to in_progress` and does not
  mention review feedback — resolving the recovery path in one read, with no
  fabricated review file.
- **SC-002**: 100% of the `{done, canceled, genesis, blocked, in_review}` ×
  `{none, --force}` regression cases refuse with the lane unchanged; the
  flagless `done → planned` case emits no forced-rewind event.
- **SC-003**: The legitimate `in_review + valid review-feedback → planned`
  rollback still succeeds (exit 0).
- **SC-004**: The state-machine parity baseline and the existing review-family
  refusal pins are unchanged (0 rows / 0 assertions regressed).
