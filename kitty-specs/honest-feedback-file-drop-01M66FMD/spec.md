# Mission Specification: honest feedback file drop

**Mission Branch**: `issue-6699-honest-feedback-file-drop`
**Created**: 2026-10-30
**Status**: Draft
**Input**: Issue spec-kitty/spec-kitty#6699 — "`move-task --review-feedback-file` is validated and then ignored on edges that write no review cycle (arbiter override, non-review edges)". Operator guidance: make the drop honest — either refuse the flag on those edges with a clear message, or record it where it survives; decide from the issue text and the surrounding contract, and pin the behaviour with a test per edge.

## Background (grounding, 2026-10-30, main@512567ee)

`move-task` resolves `--review-feedback-file` on every edge (`_mt_resolve_feedback` sets `st.resolved_feedback_source`; `_guard_feedback_file` refuses a missing/non-file path on every edge). After the #6652 fix, only two writers consume it: the rejection writer (`persist_rejected_review_cycle_for_rollback`, on review-rejection edges) and the approval writer (`_persist_approved_review_cycle`, on `→ approved`/`→ done`).

Live reproduction on `main@512567ee` (real CLI, rework-loop harness):

1. `in_progress → for_review` with `--review-feedback-file`: exit 0, no output about the file, no review cycle written. **Silent drop — reproduces.**
2. `for_review → in_review` with `--review-feedback-file`: exit 0, no output about the file. **Silent drop — reproduces.**
3. Arbiter override `planned --force → approved` with `--review-feedback-file`: the #6652 stderr warning **does** fire ("was not recorded … an arbiter override is recorded as a review override, not an approval"), the move succeeds, and the event-sourced `ReviewOverride` records only the `--note`. This edge already meets the issue's "at least warn on stderr" floor; it is pinned only at writer level (unit test), not end-to-end.

Not superseded: `git log -S` over `resolved_feedback_source`/`_warn_feedback_file_not_recorded` shows the #6652 mission (approval recording + skip-warning) landed after this issue was filed and never touched the non-review edges or the help text's over-claim.

## Terminology (which meaning applies)

- **Review-rejection edge**: `is_review_rejection_edge` — any `* → planned`, plus `in_review → in_progress` (#4899, frozen contract).
- **Approval edge**: target lane `approved` or `done`.
- **Non-review edge**: every other FSM edge (e.g. `planned → claimed`, `claimed → in_progress`, `in_progress → for_review`, `for_review → in_review`, moves into `blocked`). No review cycle is written and no on-wire `review_ref` exists there.
- **Arbiter override**: `--force` from `planned` to `approved`/`done` over a standing rejection (I-4: never recorded as an approval, in either store).

## Per-edge decision (from the issue text and the surrounding contract)

- **Non-review edges**: there is nowhere the file survives — no review cycle is written, no `review_ref` is emitted. The honest remedy is to **refuse the flag (exit 1)** with a clear, edge-naming message, before any lane hop or durable write. This matches the flag's already-strict validation (`_guard_feedback_file` refuses a missing path on every edge) and the issue's own ordering ("refuse it (exit 1), or at least warn").
- **Arbiter override into `approved`/`done`**: the existing #6652 stderr warning is kept and pinned end-to-end. Recording the file in the arbiter decision artifact would require either a fifth field on the frozen four-field `ReviewOverride` shape (its model docstring forbids this) or folding file content/path into the `--note`-derived reason that `parse_category_from_note` parses back for the kanban display — a contract change needing a maintainer decision; deferred with a follow-up issue.
- **Help text**: the `--review-feedback-file` help currently says the file is "Recorded as the transition's on-wire review_ref rationale" without qualifying the edge. It is narrowed to state the refusal on non-review edges.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Refuse the feedback file on non-review edges (Priority: P1)

As a reviewer or implementer driving `move-task`, when I supply `--review-feedback-file` on an edge that writes no review cycle (e.g. `in_progress → for_review`, `for_review → in_review`), the command must refuse with exit 1 and a message naming the edge and the edges that do record the file, instead of validating the file and then silently dropping it.

**Why this priority**: this is the silent-drop defect the issue reports; every other edge already records or warns.

**Independent Test**: run `move-task WP --to for_review --review-feedback-file f.md` through the real CLI on a WP at `in_progress`; assert exit 1, the refusal message, and that no lane hop or review cycle was written.

**Acceptance Scenarios**:

1. **Given** WP01 at `in_progress` and an existing feedback file, **When** `move-task WP01 --to for_review --review-feedback-file <file>`, **Then** exit 1 with a message naming the `in_progress -> for_review` edge and stating the flag is not recorded there; the WP stays at `in_progress`; no review-cycle artifact appears.
2. **Given** WP01 at `for_review` (claimed by a reviewer), **When** `move-task WP01 --to in_review --review-feedback-file <file>`, **Then** exit 1 with the same class of message; the WP stays at `for_review`.
3. **Given** WP01 at `in_progress`, **When** `move-task WP01 --to for_review` (no flag), **Then** the move succeeds exactly as today (the refusal only arms when the flag is supplied).
4. **Given** the same move as scenario 1, **When** the operator removes the flag (or folds the rationale into `--note`), **Then** the move proceeds.

### User Story 2 - Keep the arbiter-override drop announced and pinned (Priority: P2)

As an operator running an arbiter override (`planned --force → approved`/`done` over a standing rejection) with `--review-feedback-file`, the move must continue to succeed (the `--note` is recorded in the arbiter decision) and must warn on stderr that the file was not recorded — pinned end-to-end through the real CLI, not only at writer level.

**Why this priority**: this edge is already honest at the "warn" floor, but the behaviour is only pinned by a writer-level unit test; the issue asks for a test per edge.

**Independent Test**: drive a real rejection then an arbiter override with the flag; assert exit 0, the stderr warning, the recorded arbiter decision carrying the note, and that no approval review-cycle was fabricated for the file.

**Acceptance Scenarios**:

1. **Given** WP01 rejected back to `planned` (standing rejection with `review_ref`), **When** `move-task WP01 --to approved --force --note "<why>" --review-feedback-file <file>`, **Then** exit 0; stderr carries "was not recorded"; the event log records the arbiter `ReviewOverride` with the note; the existing rejection review-cycle is the only cycle artifact.
2. **Given** the same state, **When** the same override runs without the flag, **Then** exit 0 and no warning (the warning arms only when a file was supplied).

### User Story 3 - Help text matches the behaviour (Priority: P3)

As an operator reading `move-task --help`, the `--review-feedback-file` help must state that the flag is refused on edges that write no review cycle, so the documented contract matches the enforced one.

**Why this priority**: the issue names "narrow the help text" as part of the remedy; it is documentation of the P1 behaviour.

**Independent Test**: the rendered `--help` output (and its golden fixture) contains the narrowed wording.

**Acceptance Scenarios**:

1. **Given** any checkout, **When** `spec-kitty agent tasks move-task --help`, **Then** the `--review-feedback-file` help names the recording edges and states the flag is refused on every other edge.

### Edge Cases

- Feedback file supplied on a non-review edge **and** the path is missing/not a file: the edge refusal fires (the flag is useless on that edge regardless of the path's validity); still exit 1.
- `* → planned` and `in_review → in_progress` (review-rejection edges): unchanged — the file remains required.
- `→ approved`/`→ done` (approval edges, including arbiter overrides): unchanged — record-when-written, warn-when-skipped (#6652).
- Forced rework (`planned --force → claimed`/`in_progress`/`for_review`): non-review edges; the flag is refused there too.
- `--json` output on the new refusal: the existing `RefuseExit1` error envelope applies; no lane hop, no durable write happens before the refusal (the override/arbiter persists only arm on approval edges).

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Refuse `--review-feedback-file` on non-review edges | As an operator, I want `move-task` to refuse `--review-feedback-file` with exit 1 and an edge-naming message on edges that write no review cycle, so that a validated file is never silently dropped. | High | Open | [build] | no |
| FR-002 | Keep rejection/approval edge behaviour unchanged | As an operator, I want the flag's behaviour on review-rejection edges (required) and approval edges (record-or-warn, #6652) unchanged, so the fix adds no regression. | High | Open | [ratchet] | no — pinned by same-fixture positive controls on both edge families |
| FR-003 | Pin the arbiter-override warning end-to-end | As an operator, I want the arbiter-override drop of `--review-feedback-file` pinned by an end-to-end test, so the stderr warning cannot silently regress. | Medium | Open | [ratchet] | no — paired with the no-flag negative control on the same fixture |
| FR-004 | Narrow the `--help` text | As an operator, I want the `--review-feedback-file` help to state the refusal on non-review edges, so the documented contract matches the enforced one. | Medium | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|--------|--------|
| NFR-001 | No durable writes on refusal | A refused non-review-edge move writes no lane hop, no review cycle, and no override/arbiter artifact before exit 1 (verifiable on the event log in the same fixture). | Reliability | High | Open |
| NFR-002 | Message quality | The refusal message names the WP, the actual `old -> new` edge, and the edge families that record the file; it suggests the operator action (remove the flag / use `--note`). | Usability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|--------|--------|
| C-001 | Frozen `ReviewOverride` shape | The event-sourced `ReviewOverride` keeps its frozen four-field shape (`at`/`actor`/`wp_id`/`reason`); no fifth field is added for feedback. Recording the file in the arbiter decision artifact is deferred (follow-up issue). | Technical | High | Open |
| C-002 | Guard-order stability | The new refusal must not change the OLD-timing partial-write signals (`override_persist_signal`, `arbiter_persist_signal`) — both only arm on approval edges where the new refusal is inert. | Technical | High | Open |
| C-003 | Frozen `--help` surface process | The `--help` change updates the golden fixture (`tests/specify_cli/cli/commands/agent/fixtures/tasks_cli/help/move-task.help`) in the same change. | Technical | Medium | Open |

### Key Entities

- **`_guard_feedback_file`** (`tasks_transition_core.py`): the pure guard that validates the supplied file; gains the edge-applicability arm.
- **`is_review_rejection_edge` / approval lanes**: the two edge families where the flag is consumed; the refusal is the complement of their union.
- **`_warn_feedback_file_not_recorded`** (`tasks_verdict_persistence.py`): the #6652 stderr warning kept on skip arms of the approval writer.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A real-CLI move with `--review-feedback-file` on `in_progress → for_review` and on `for_review → in_review` exits 1 with the edge-naming refusal and writes no lane hop or review cycle — [build] · no-op passable: no
- **SC-002**: The same moves without the flag still succeed (positive control on the same fixtures) — [ratchet] · no-op passable: no
- **SC-003**: Review-rejection edges still require the file and approval edges still record-or-warn it (#6652 tests stay green unmodified) — [ratchet] · no-op passable: no
- **SC-004**: An end-to-end arbiter override with the flag exits 0, warns on stderr, records the note in the arbiter decision, and fabricates no approval cycle — [ratchet] · no-op passable: no
- **SC-005**: `move-task --help` (and its golden fixture) states the refusal on non-review edges — [build] · no-op passable: no
