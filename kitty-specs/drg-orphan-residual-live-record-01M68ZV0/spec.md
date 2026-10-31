# Mission Specification: DRG orphan residual — a live, non-frozen record

**Mission Branch**: `issue-6513-drg-orphan-residual-live-record`
**Created**: 2026-10-31
**Status**: Draft
**Input**: Issue #6513 — "Red on main: DRG orphan count 25 exceeds documented residual 21"

## Context and grounding (read this first)

`tests/specify_cli/cli/commands/test_doctrine_regenerate_graph.py::test_shipped_graph_orphan_count_within_documented_residual`
asserts `orphans <= DOCUMENTED_ORPHAN_RESIDUAL`. Issue #6513 reported it red at `f1663393`
(count 25 vs ceiling 21).

The literal red is **already gone**: `bd7fdb7f36` (the #6437 fold of #6432) raised the constant
21 -> 25 for the four `mission_step_contract:plan/*` nodes vendored by #6379. That raise is
**honest and must stay**: every step-contract node ships `edges: []` and is resolved by the
`(mission_type, action)` join, never by traversal (`_EDGELESS_BY_CONSTRUCTION` in
`tests/charter_offering/drg/migration/test_extractor_projection.py`). Wiring a manufactured edge
to zero the metric is exactly what D-C2 / C-003 forbid. **This mission does not touch the
ceiling and does not author an edge.**

What is still broken is the *documented* half of the issue's own remedy ("...or update
drg-orphan-residual.md and raise the ceiling with rationale"):

1. The record the failure message and the test docstring name —
   `kitty-specs/mission-lifecycle-dispatch-drg-closeout-01KV0S99/drg-orphan-residual.md` — lives
   under `kitty-specs/`, an **immutable archive root** (`tests/architectural/test_archive_root_byte_identical.py`,
   only narrow append exceptions). The instruction "update drg-orphan-residual.md" is unexecutable:
   following it trips the archive-freeze gate.
2. That frozen file's last state says ceiling **29** then **30** over **17** step contracts. With
   `glossary_pack:spec-kitty-core` and `asset:common-docs-structural-lint` moving in and out since,
   the shipped reality is **25** over **21** step contracts. A curator reading the canonical #1923
   record is misled by five nodes.
3. The 21 -> 25 rationale was recorded only in a *mission-scoped* file
   (`kitty-specs/charter-synthesis-graph-and-languages-01M59RZ5/research/orphan-residual-addendum.md`,
   also frozen). Nothing live, operator-readable, records the current membership.
4. **Nothing binds the constant to any record.** `DOCUMENTED_ORPHAN_RESIDUAL = N` can be bumped
   with a one-line comment and go green — the exact failure mode #6513 warns against. The pure-view
   ledger `_SHIPPED_ORPHANS` pins membership, but the *shipped* view the ceiling measures has no
   membership record of its own beyond a numeric ceiling.

So the honest fix is documentation plus a guard, not a code edge and not a higher ceiling.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An operator reading a red orphan gate learns where the record actually is (Priority: P1)

An operator sees `test_shipped_graph_orphan_count_within_documented_residual` fail. The message
must point at a live, writable, current-state record and at the pinned membership ledger, and must
say that raising the ceiling requires a recorded row — never at a frozen archive file.

**Why this priority**: this is the issue's operator-visible defect; without it the gate's own remedy
is wrong and the next curator either edits a frozen file (gate failure) or bumps the number silently.

**Independent Test**: assert the failure message and the module docstring reference the live record
path and do not instruct an edit under `kitty-specs/`.

**Acceptance Scenarios**:

1. **Given** the ceiling test module, **When** an operator reads the constant's docstring and the
   assertion message, **Then** both name the live record and the ledger, and neither says to update
   the frozen `kitty-specs/.../drg-orphan-residual.md`.

### User Story 2 - The shipped-graph residual has a live current-state record (Priority: P1)

A curator needs to see every shipped orphan, why it is orphaned, and whether it may be wired or
must stay residual — from a live doc that can be updated as the graph changes.

**Why this priority**: the record is the deliverable the issue asks for; the ceiling is only its number.

**Independent Test**: read the live doc; it enumerates exactly the measured orphan URNs, grouped by
disposition, including the 21 -> 25 ceiling ledger with its rationale and issue references.

**Acceptance Scenarios**:

1. **Given** the live record, **When** it is compared with `load_built_in_graph()`, **Then** the set
   of URNs it records equals the measured shipped orphan set exactly.
2. **Given** the record, **When** a reader wants the history of the ceiling, **Then** the 21 -> 25
   raise, its cause (#6379 / #6432), and the frozen archive record's as-of-date status are stated.

### User Story 3 - A silent ceiling raise cannot go green (Priority: P2)

A future change that adds an orphan, or bumps the constant, must fail a test until the live record is
updated to match.

**Why this priority**: this is the anti-recidivism half; without it the issue returns as soon as the
next artifact lands.

**Independent Test**: temporarily add an orphan (or a record row) and observe the guard fail in both
directions; restore and observe it pass.

**Acceptance Scenarios**:

1. **Given** a measured orphan absent from the record, **When** the guard runs, **Then** it fails
   naming that URN.
2. **Given** a record row whose URN is no longer an orphan, **When** the guard runs, **Then** it
   fails naming that URN (a shrink must be recorded too).
3. **Given** the shipped tree unchanged, **When** the guard runs, **Then** it passes and the ceiling
   stays 25.

### Edge Cases

- The record is parsed from Markdown: only backticked URNs inside the record's own fenced
  current-state block count, so prose and historical sections cannot accidentally satisfy the guard.
- A legitimately wired orphan (a later curation pass removes one) must fail the guard until the
  record and the ceiling are updated together — that is intended, not a false positive.
- A future `graph.yaml` monolith vs `*.graph.yaml` fragment flip must not change the guard: it reads
  the loaded graph, never a path shape.
- Docs surfaces: the live record must satisfy the docs gates (frontmatter, page inventory, ToC,
  spelling) without a whole-reference regeneration.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Live current-state residual record | As a curator, I want the shipped-graph orphan residual recorded in a live doc so that I can update it as the graph changes. | High | Open | [build] | no |
| FR-002 | Record enumerates the measured set | As a curator, I want every measured shipped orphan URN listed with its disposition so that no orphan rides along unexamined. | High | Open | [build] | no |
| FR-003 | Ceiling test points at the live record | As an operator whose gate just failed, I want the message and docstring to name the live record and the ledger so that I follow a remedy that the archive-freeze gate permits. | High | Open | [build] | no |
| FR-004 | Membership guard binds record to measurement | As a maintainer, I want the recorded set to equal the measured shipped orphan set so that a silent ceiling raise or an unrecorded new orphan fails a test. | High | Open | [build] | no |
| FR-005 | Ceiling ledger carries the rationale | As a reader, I want the 21 -> 25 raise, its cause (#6379 / #6432) and the frozen archive status recorded so that the number is never bare. | Medium | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Guard cost | The new guard adds at most 2 s of wall time over the existing module load of the shipped graph (one doc read + one set comparison; no second graph load). | Performance | Medium | Open |
| NFR-002 | Deterministic, offline | The guard performs no network access and no clock/day dependence; two consecutive runs on the same tree give the same verdict. | Reliability | High | Open |
| NFR-003 | Docs gates stay green | `scripts.docs.check_docs_freshness --ci` reports 0 errors and the record passes the page-inventory/ToC/spelling gates without a whole-reference regeneration. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Ceiling unchanged | `DOCUMENTED_ORPHAN_RESIDUAL` stays 25; this mission neither raises nor lowers it, and authors no DRG edge and no artifact change. | Technical | High | Open |
| C-002 | Frozen archive untouched | No file under `kitty-specs/` is modified; the historical residual record stays byte-identical and is cited, not edited. | Technical | High | Open |
| C-003 | No gate weakened | No test is skipped, xfailed, deleted or loosened; the new guard is additive and the existing ceiling assertion keeps its `<=` semantics. | Technical | High | Open |
| C-004 | Out-of-scope reds cited, not fixed | Pre-existing reds owned by other issues (#6798 next-mission discovery, #6801 birth-cutover evidence window, #6816 router-gate incomplete conclusion, #5927 mission-status reality contract) are cited where CI shows them and are not fixed here. | Business | Medium | Open |

### Key Entities

- **Shipped orphan**: a DRG node with no inbound and no outbound edge in `load_built_in_graph()`.
- **Residual record**: the live Markdown page that enumerates the shipped orphans, their grouped
  dispositions and the ceiling ledger.
- **Ceiling**: `DOCUMENTED_ORPHAN_RESIDUAL`, the numeric regression guard in the ceiling test module.
- **Membership ledger**: `_INTENTIONAL_ORPHANS` / `_SHIPPED_ORPHANS` in
  `tests/charter_offering/drg/migration/test_extractor_projection.py`, the pure-extractor view.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The live record's URN set equals the measured shipped orphan set exactly (25 URNs), proven by the new guard passing on the shipped tree — [build] · no-op passable: no
- **SC-002**: `DOCUMENTED_ORPHAN_RESIDUAL` is unchanged at 25 and no DRG edge is authored (`packs/built-in/` untouched) — [build] · no-op passable: no
- **SC-003**: The ceiling assertion message and module docstring name no `kitty-specs/` path as an edit target — [build] · no-op passable: no
- **SC-004**: The touched test module and the docs gates (`check_docs_freshness --ci`) pass with 0 errors — [build] · no-op passable: no
