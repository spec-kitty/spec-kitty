# Mission Specification: Post-#4941 "Lamport-ordered status path" claim sweep

**Mission Branch**: `kitty/mission-post-4941-lamport-claim-sweep-01M66YJ6`
**Created**: 2026-10-30
**Status**: Draft
**Input**: Issue spec-kitty/spec-kitty#6604 — "Post-#4941 sweep: remove the remaining
'Lamport-ordered status path' claims (ADR amendments, living C4, CLAUDE.md)".

## Why

Since #4941 (PR #6261, `spec-kitty-events` 10.5.1) the CLI status path is ordered by
wall clock `(at, event_id)` with an approved-departure lift. `status.reducer.reduce`
and `materialize_snapshot` both reach the same `spec_kitty_events.diary.reduce_parsed`
fold; CLI lane rows carry no Lamport clock and the Lamport reducer
`spec_kitty_events.status.reduce_status_events` is not on the CLI path.

Several documents still describe the old, two-reducer world in which the status path
was Lamport-ordered. A maintainer who reads them designs against a guarantee the code
does not give — in the worst direction, they assume a rejection can never be
out-ordered. The remaining claims are documentation debt on a decision that has already
been amended; the sweep is factual wording plus one new ADR amendment, and adds a guard
so the retired wording cannot come back.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A maintainer reads a living page and gets the current ordering (Priority: P1)

A maintainer opens the C4 context page, the container page, or the API/dashboard domain
plan to decide how a new read surface should reduce status. Every sentence about
ordering names the wall-clock `(at, event_id)` fold and the approved-departure lift, and
names Lamport only to say what the CLI does *not* do.

**Why this priority**: these are the pages people read before designing; they are the
primary harm. They are also plain prose/diagram edits, so they can ship alone.

**Independent Test**: read the three pages and grep them for the retired wording; the
guard test in User Story 4 fails on the old text and passes on the new text.

**Acceptance Scenarios**:

1. **Given** the C4 context page, container page and API/dashboard domain plan **When**
   a maintainer reads their ordering statements **Then** each says the status path is
   ordered by wall clock `(at, event_id)` and that one reducer reaches it, with no
   surviving "Lamport reducer" / "Lamport reduction" / "the dashboard uses the Lamport
   reducer, so two read surfaces can disagree" claim.
2. **Given** the container diagram's reducer node **When** it is read with the prose
   around it **Then** the node labels the wall-clock fold it actually calls, and the
   alt-text agrees with the diagram.

---

### User Story 2 - The ADR that owns the read API records the current ordering (Priority: P1)

A maintainer consulting ADR `2026-10-01-2` (Mission Status Read API) for the read path's
ordering finds the original decision text intact and a factual amendment stating what
the code does now: wall clock `(at, event_id)`, from-lane continuity, the
approved-departure lift, and that Lamport-primary ordering is a post-GA direction
(#6609) needing its own ADR.

**Why this priority**: the ADR is the architectural intent an implementer must follow;
leaving it asserting "the service ports the Lamport reduction" contradicts the code the
service must conform to.

**Independent Test**: read the ADR; the historical decision statements are still there,
and a new amendment section names #4941/#6261, the lift, and #6609.

**Acceptance Scenarios**:

1. **Given** ADR `2026-10-01-2` **When** its amendment history is read **Then** an
   amendment dated in this mission records the wall-clock ordering as the accepted
   current decision and credits the shipped #4941 fix, without rewriting any original
   decision or consequence paragraph.
2. **Given** the same ADR's `status`/`updated` frontmatter **When** the docs freshness
   gates run **Then** the record is consistent with the new amendment.

---

### User Story 3 - The agent guidelines stop repeating the retired claim (Priority: P1)

An agent reading `AGENTS.md` (and `CLAUDE.md`, its symlink) "Status Model Patterns"
learns: one wall-clock reducer; the approved-departure lift ships; the
`consolidation/` docstrings were corrected; the one remaining residual is a
**non-approval** transition minted on a clock behind the event it follows.

**Why this priority**: `AGENTS.md` is the file every agent is told to read first, and it
currently teaches the opposite of the shipped behaviour plus a stale `#6213` to-do.

**Independent Test**: read the section; the guard test fails if the "docstrings still
call this the Lamport wrapper" / "`#6213` tracks correcting them" / "#4941 is still
open as described" wording returns.

**Acceptance Scenarios**:

1. **Given** `AGENTS.md` "Status Model Patterns" **When** it is read **Then** it credits
   the shipped lift and the corrected `consolidation/` docstrings, keeps the narrower
   non-approval skew residual, and cites the amended ADRs rather than an open #4941.
2. **Given** `CLAUDE.md` **When** it is resolved **Then** it shows the same corrected
   content (it is a symlink to `AGENTS.md`), and no second copy exists to drift.

---

### User Story 4 - The retired wording cannot silently return (Priority: P1)

A future contributor (or agent) reintroduces a "Lamport reducer" claim on a living page
or in the code comment that the sweep corrected, and CI fails with a message naming the
file, the line and the replacement fact.

**Why this priority**: without the guard this is the fourth sweep of the same claim
(#6213 closed after step 1 only). The guard converts a recurring documentation-debt
pattern into a one-time fix.

**Independent Test**: revert one corrected line and run the guard — it fails; restore it
and it passes; feed the detector a synthetic stale line and a synthetic negated line and
it classifies each correctly.

**Acceptance Scenarios**:

1. **Given** the guard test **When** any retired phrasing is put back in a covered file
   **Then** the test fails and names the file, the line and the correct statement.
2. **Given** the guard test **When** a *negated* mention ("CLI lane rows carry no
   Lamport clock", "not Lamport-ordered") is added or kept **Then** the test passes —
   the guard bans the affirmative claim, not the word.
3. **Given** the guard test's own detector **When** it is fed a stale sample and a
   negated sample **Then** both are classified correctly (non-vacuity), and a stale
   sample is not merely "not found".

---

### Edge Cases

- **The ADR body still contains the old wording.** That is intended: ADR bodies are
  history. The guard must therefore cover living pages and the corrected code comment,
  and assert the ADR's *amendment* rather than its body. Excluding `docs/adr/` from a
  blanket scan must not become a hole: the amendment assertion is explicit.
- **`CLAUDE.md` is a symlink to `AGENTS.md`.** A guard that reads both paths must not
  double-report or fail on the symlink; a correction applied to one is applied to both.
- **Other logs do use Lamport values.** Retrospective lifecycle events tick a Lamport
  counter and decision-point rows use a line count as a proxy. The guard must not ban
  the word `Lamport` in `src/`; it targets the status-path phrasing only.
- **Gap table drift.** `docs/architecture/event-ledger-writers-and-readers.md` G-3 is
  the tracker line for this work; if it still reads "file new (#6213 closed after step 1
  only)" the sweep is not done.
- **Historical trees** (`docs/archive/`, `docs/reports/`, `research/`, `kitty-specs/**`)
  keep their old wording. They are records, not claims about today.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | C4 living pages corrected | As a maintainer, I want the context and container pages to describe the wall-clock fold so that I design read surfaces against the code. | High | Open | [build] | no — the pages currently say "Lamport reducer" |
| FR-002 | Domain plan corrected | As a maintainer, I want the API/dashboard domain plan's known-gap entry to stop claiming two different reducers so that I do not plan a reconciliation that is not needed. | High | Open | [build] | no — the gap entry asserts the two-reducer split |
| FR-003 | ADR 2026-10-01-2 factual amendment | As an architect, I want that ADR to record wall-clock ordering as the accepted current decision, with history intact, so that the record matches the code. | High | Open | [build] | no — no amendment exists today |
| FR-004 | AGENTS.md / CLAUDE.md refreshed | As an agent, I want the Status Model Patterns section to credit the shipped lift and the corrected docstrings and keep only the narrow residual, so that I do not design against a guarantee the code lacks. | High | Open | [build] | no — the section currently contradicts the code |
| FR-005 | Code comment corrected | As an implementer, I want `consolidation/preflight.py`'s actor-lookup docstring to cite the amended record so that the reason it reads append order is not a stale ADR claim. | Medium | Open | [build] | no — it cites the Lamport-primary rule as current |
| FR-006 | Gap G-3 closed | As a maintainer, I want the event-ledger gap table to record this sweep as closed with its residual so that the gap is not re-filed a fourth time. | Medium | Open | [build] | no — G-3 still says "file new" |
| FR-007 | Guard test | As a maintainer, I want a test that fails when the retired status-path wording returns to a living page, the agent guidelines, or the corrected comment, so that this does not recur. | High | Open | [ratchet] | no — no such guard exists |
| FR-008 | Changelog entry | As an operator, I want an `[Unreleased]` entry stating that the docs now match the wall-clock status path, so that the correction is visible in the release notes. | Medium | Open | [build] | no — no entry exists |
| FR-009 | Tracker coordination recorded | As the operator, I want the #5528/#6117 issue-body corrections left to their own pass and named in the PR, so that this mission does not silently take on issue edits. | Low | Open | [folded] | yes — a pointer in the PR body satisfies it |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|--------|--------|
| NFR-001 | Guard runs on a docs-only PR | The guard test must execute under the repository's docs-only CI trim (so a docs-only PR cannot newly red it), completing in under 5 seconds. | Testability | High | Open |
| NFR-002 | No unbounded scan | The guard scans a named, bounded corpus (living pages, agent guidelines, one source module) rather than the whole tree, and every covered path must exist (a missing path fails). | Reliability | High | Open |
| NFR-003 | Docs gates stay green | The committed docs index, ADR inventory and docs-freshness checks report zero errors after the edit set. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|-------------|----------|--------|--------|
| C-001 | No ordering decision | The mission changes wording and records an amendment only. It must not change the reducer, the ordering key, or propose Lamport-primary. | Technical | High | Open |
| C-002 | ADR history preserved | Original ADR decision, context and consequence text is not rewritten; the correction lands as a dated amendment, matching that record's existing amendment pattern. | Process | High | Open |
| C-003 | Historical trees untouched | `docs/archive/`, `docs/reports/`, `research/` and `kitty-specs/**` past missions keep their wording. | Process | Medium | Open |
| C-004 | Out-of-scope tracker edits | The #5528 and #6117 issue bodies are not edited by this mission. | Process | Medium | Open |

### Key Entities

- **Status path claim**: a sentence in prose, a diagram node label or a docstring that
  asserts how CLI status reads are ordered or which reducer they use.
- **Living page**: a document that describes the current system and must be true today,
  as opposed to an ADR body, a report, a past mission or an archive.
- **Retired phrasing**: the affirmative wording this mission removes (for example the
  status path/reducer being "Lamport"), as distinct from a negation that teaches the
  correct fact.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zero affirmative "Lamport reducer / Lamport reduction / Lamport wrapper" claims about the CLI status path remain in the covered living corpus — [build] · no-op passable: no
- **SC-002**: Reverting any single corrected line makes the guard test fail with a message naming the file and the correct statement — [ratchet] · no-op passable: no
- **SC-003**: ADR `2026-10-01-2` contains an amendment recording wall clock `(at, event_id)` plus the approved-departure lift, and still contains its original D-5 "moves them onto the Lamport reducer" sentence — [build] · no-op passable: no
- **SC-004**: The narrower residual (a non-approval transition minted on a clock behind the event it follows still sorts before it) is stated in the agent guidelines and in the closed G-3 row — [build] · no-op passable: no
- **SC-005**: Docs freshness, docs index and ADR inventory gates report zero errors on the mission head — [ratchet] · no-op passable: no

## Out of scope

- Making the CLI status path Lamport-primary (#6609; needs its own ADR and a clock on CLI
  rows, spec-kitty-events#72).
- Editing the #5528 / #6117 issue bodies.
- `docs/operations/manual-test-plan.md` §2.2 (retired SaaS sync surface) and the
  `docs/context/system-events.md` "Lamport Clock" glossary definition — neither is a
  claim about the CLI status path.
