# Mission Specification: Next dependency wedge — dispatch the review

**Mission Branch**: `kitty/mission-next-dependency-review-dispatch-01M46TJ7`
**Created**: 2026-10-05
**Status**: Draft
**Input**: Issues spec-kitty/spec-kitty#5669 (P1, the wedge + the lanes approval residue) and #5310 (folded — advance first-contact bypasses the finalized board). Cluster-tracked under epic #5797.

## Overview

The canonical `spec-kitty next` control loop cannot complete the most common mission
shape: one work package depending on another. The three defects below are all about
one promise — **advancing `next` and querying `next` must agree on a finalized task
board, and neither may wedge when the only actionable work is the review of a
`for_review` WP that a `planned` WP depends on.** A dependency between WPs for shared
files is exactly what `finalize-tasks` produces, so most real missions hit this at
their first review. No data is lost; the loop simply cannot leave the state on its own.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The dependency wedge: `next` dispatches the pending review (Priority: P1)

An operator drives a `lanes` or `coord` mission where `WP02` declares
`dependencies: [WP01]`. `WP01` is implemented and handed off to `for_review`; `WP02`
is still `planned` and dependency-walled (its dependency is not yet `approved`/`done`).
The operator advances the loop with `spec-kitty next --result success`. The loop should
dispatch the **review of WP01** — the only actionable work, and the only thing that can
ever unblock WP02. Today it instead returns `kind="blocked"`, `step_id="implement"`,
`reason="dependencies_not_satisfied"` (exit 1) forever, and query mode reports the same.

**Why this priority**: P1 / P0-candidate. The canonical control loop cannot complete the
ordinary dependency plan shape without a human stepping outside the loop.

**Independent Test**: A 2-WP mission (`WP02` deps `WP01`); drive to `implement WP01`,
implement + hand off WP01 to `for_review`; assert the next `next --result success`
returns `kind="step" action="review" wp_id="WP01"` (exit 0), matching the no-dependency
control arm. Testable via a direct unit on the routing authority and an end-to-end
advance on both `lanes` and `coord`.

**Acceptance Scenarios**:

1. **Given** WP01 `for_review` and WP02 `planned` with `dependencies:[WP01]`, **When**
   `next --result success` is advanced, **Then** it returns `kind="step"
   action="review" wp_id="WP01"` (exit 0) — not `blocked/dependencies_not_satisfied`.
2. **Given** the same board, **When** `next` is queried (no `--result`), **Then** it
   previews a `review` step (`preview_step="review"`, `wp_id="WP01"`), agreeing with the
   advance arm.
3. **Given** WP01 `for_review` and WP02 later also handed off, **When** advanced, **Then**
   the loop still reaches `review` for the earliest `for_review` WP (control-arm parity).

---

### User Story 2 - Advance honours the finalized board on first contact (#5310) (Priority: P1)

An operator advances `next` against a finalized board for which **no runtime run has been
persisted yet** (first advancing contact). Advancing should honour the finalized board —
the same board authority query mode applies — instead of booting a fresh `discovery`
runtime and reporting a stale early phase. Today query mode selects the board's WP while
advance starts `discovery`, so the two disagree.

**Why this priority**: P1. It is the second half of the same query↔advance parity
promise, in the same routing module. Left unfixed, Story 1's corrected board verdict
would still be bypassed on the no-persisted-run path.

**Independent Test**: A finalized board with no persisted run; assert advancing `next`
and querying `next` return the same board step rather than advance→`discovery`,
query→board.

**Acceptance Scenarios**:

1. **Given** a finalized board and no persisted runtime run, **When** `next --result
   success` is advanced, **Then** it dispatches the board's step (the same step query
   mode previews), not a fresh `discovery` step.
2. **Given** Story 1's corrected board verdict, **When** the no-persisted-run advance
   consults the board, **Then** it inherits that verdict (review of the walled board),
   i.e. the two fixes compose rather than contradict.

---

### User Story 3 - Lanes approval is not blocked by `next`'s own observability write (Priority: P1)

On `lanes` topology, after the loop wedges (Story 1), the operator's manual recovery is
to review and approve WP01 by hand (`agent action review` + `move-task WP01 --to
approved`). That approval is itself refused: a prior `next` call appended
`kitty-specs/<slug>/mission-events.jsonl` (its own legacy observability log) and left it
uncommitted, so the move-task dirty gate reports "Blocking: 1 uncommitted file(s)". The
operator must commit a file they never knowingly touched before the approval proceeds.

**Why this priority**: P1. It is the second, smaller defect inside #5669 and the thing
that makes even the manual workaround fail on the most common topology.

**Independent Test**: With `kitty-specs/<slug>/mission-events.jsonl` dirty in the write
checkout, assert `move-task <wp> --to approved` (and `--to for_review`/`--to done`) is not
refused over that file, while a genuinely operator-owned dirty file still blocks.

**Acceptance Scenarios**:

1. **Given** an uncommitted `kitty-specs/<slug>/mission-events.jsonl` (and no other dirty
   files), **When** `move-task <wp> --to approved` runs, **Then** it is not refused on
   that file.
2. **Given** an uncommitted `mission-events.jsonl` **and** an uncommitted
   operator-owned file, **When** the gate runs, **Then** the operator file still blocks
   (the exemption is narrow, not a blanket pass).

### Edge Cases

- A `planned` WP dependency-walled with **no** `for_review` and **no** `in_review` WP →
  the loop reports an honest "no actionable work package" block, not
  `implement`/`dependencies_not_satisfied`.
- A `claimed` or `in_progress` WP still routes to `implement` (genuine resume) even when a
  sibling `planned` WP is dependency-walled.
- An `in_review` WP present (and nothing claimable) → the existing
  `review_in_progress` block is unchanged.
- The #4860 guard is preserved: a dependency-walled `planned` WP is **never** dispatched
  for `implement`.
- The `mission-events.jsonl` exemption is anchored to `kitty-specs/<slug>/mission-events.jsonl`
  and must not match a user file named `mission-events.jsonl` elsewhere, nor widen the
  global toolchain-churn owner (which feeds destructive consolidate/accept/merge gates and
  whose file has live research-gate readers).
- Query↔advance parity holds across `lanes`, `coord`, and `single_branch`.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | `next` dispatches the review of a `for_review` WP when the only claimable work is dependency-walled (dispatch **and** query mode) | As an operator, I want `next` to dispatch the pending review so the loop can unblock a dependent WP without my intervention. | High | Open | [build] | no — a no-op still returns `blocked/dependencies_not_satisfied`; paired with the no-dependency control arm on the same fixture |
| FR-002 | A dependency-walled `planned` WP is never dispatched for `implement` (preserve #4860) | As an operator, I want `next` to never dispatch a WP whose dependencies are unmet so review ordering is honoured. | High | Open | [ratchet] | no — paired against a claimable-planned positive control |
| FR-003 | A `planned`-walled board with no reviewable WP reports an honest no-actionable-WP block | As an operator, I want a truthful "nothing to do" signal instead of a misleading implement/dependencies block. | Medium | Open | [build] | no |
| FR-004 | `claimed`/`in_progress` WPs still route to `implement` (resume) regardless of a sibling walled `planned` WP | As an operator, I want in-flight implementation work to resume normally. | High | Open | [ratchet] | no — positive control on the same routing authority |
| FR-005 | Advancing `next` on first contact against a finalized board agrees with query mode (consults the finalized-board authority, not a fresh discovery run) (#5310) | As an operator, I want advance and query to agree on a finalized board. | High | Open | [build] | no — a no-op leaves advance→discovery, query→board |
| FR-006 | `next`'s uncommitted `mission-events.jsonl` does not refuse a `move-task` transition (`for_review`/`approved`/`done`) (#5669 part 2) | As an operator, I want to approve a WP without first committing a file `next` wrote on my behalf. | High | Open | [build] | no — a no-op still refuses the approval |
| FR-007 | The `mission-events.jsonl` exemption is scoped to the review/move-task dirty gate and anchored to `kitty-specs/<slug>/mission-events.jsonl` (not the global churn owner; not a user file elsewhere) | As a maintainer, I want the exemption narrow so destructive gates and research-gate readers are unaffected. | High | Open | [build] | no — paired with a negative control (operator file still blocks) and a global-owner-unchanged assertion |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Query↔advance parity | For a finalized board, `next` query and `next --result success` advance resolve the same step across `lanes`, `coord`, and `single_branch`. | Reliability | High | Open |
| NFR-002 | No routing regression | Existing finalized-board routing outcomes (`done`/`accept`/`review_in_progress`/`no_actionable_wp`, and genuinely-claimable `implement`) remain unchanged; unaffected cases byte-identical. | Reliability | High | Open |
| NFR-003 | No hot-path cost regression | Defect-1 routing adds no run-start or extra git cost beyond the single idempotent `preview_claimable_wp` read already performed downstream in the implement resolver. | Performance | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Single claimability authority | Defect 1 routes through the existing `preview_claimable_wp` authority inside the one routing seam (`_finalized_task_board_override_step`); no second claimability predicate is minted. | Technical | High | Open |
| C-002 | `mission-events.jsonl` stays globally non-benign | The file must remain real dirt for the destructive consolidate/accept/merge gates (global churn owner) and keep its live research-gate readers; only the scoped review/move-task dirty gate treats it as a benign survivor. | Technical | High | Open |
| C-003 | ATDD red-first | Each defect lands an issue-pinned `@pytest.mark.regression` reproduction that is RED on the merge-base through the pre-existing entry point and GREEN after the fix (ADR 2026-07-17-1). | Technical | High | Open |

### Key Entities

- **Finalized task board**: the `tasks.md` + `tasks/WP*.md` + canonical lane state a mission has after `finalize-tasks`; the authority `next` routes against.
- **WP lane state**: the per-WP lane (`planned`→…→`done`/`canceled`) read from the canonical status event log.
- **Claimable preview**: the dependency-aware answer to "which WP would `implement` auto-claim", and the `dependencies_not_satisfied` selection reason when none is.
- **`mission-events.jsonl`**: `next`'s legacy per-mission observability log (tracked, write-only for lifecycle rows; also read for research-mission gate primitives), distinct from `status.events.jsonl`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a 2-WP mission (`WP02` deps `WP01`) with WP01 in `for_review`, `next --result success` returns `kind="step" action="review" wp_id="WP01"` (exit 0) on both `lanes` and `coord`. — [build] · no-op passable: no
- **SC-002**: On that same board, `next` query mode previews a `review` step for WP01, matching the advance arm (no `dependencies_not_satisfied`). — [build] · no-op passable: no
- **SC-003**: With a finalized board and no persisted runtime run, advancing `next` dispatches the board's step rather than a fresh `discovery` step (#5310). — [build] · no-op passable: no
- **SC-004**: On `lanes`, after a `next` call left `mission-events.jsonl` uncommitted, `move-task <wp> --to approved` succeeds without a manual commit, while an operator-owned dirty file still blocks. — [build] · no-op passable: no
