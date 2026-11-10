# Mission Specification: Close stale WP lifecycle records

**Mission Branch**: `kitty/mission-close-stale-lifecycle-records-01M72B89` (lands on `feat/7346-close-stale-lifecycle-records`)
**Created**: 2026-11-10
**Status**: Draft
**Input**: Issue #7346 (P1, parent epic #3897): a work package's lifecycle record under `kitty-ops/lifecycle/` cannot be closed through the CLI without also advancing the Mission state, so it ships open.

## Intent Summary (confirmed by the operator, 2026-11-10)

An operator running `spec-kitty doctor ops --close-stale [--threshold N]` gets every orphaned work-package lifecycle record closed as **abandoned**, alongside the stale Ops the sweep already closes. A record is orphaned when its `started` record has no paired completion; it is closed when that `started` record is older than the threshold (`0` closes all). The sweep writes a new `abandoned` lifecycle record paired with it, whose reason names the sweep and the threshold, and commits the closure files the way the Op sweep commits its closure spine. The sweep never touches Mission status, `meta.json` or any other Mission artifact.

Decision Moments: `01M72B8TCVPNVSD9NMVTS2W84E` (close route: extend `doctor ops --close-stale`), `01M72B8Z4FQ7J02B2HJ0ZNTC25` (a new `abandoned` phase), `01M72B942EZG713N48E0ERWE9K` (auto-commit like the Op sweep), `01M72B9FER5AYKRVXF0QX06XK1` (Intent Summary and defaults).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Close an abandoned work package's lifecycle record (Priority: P1)

A maintainer finishes a Mission whose work package WP04 was started through `spec-kitty next` but never reported a result. Its lifecycle record stays open, and `spec-kitty doctor invocation-pairing` reports it as an orphan. The only way to pair it today is `spec-kitty next --result`, which also advances the Mission. The maintainer runs `spec-kitty doctor ops --close-stale` and the record is closed as abandoned; the Mission is untouched.

**Why this priority**: it is the defect in #7346; without it orphaned records ship open in pull requests.

**Independent Test**: seed a stale orphaned lifecycle record, run `doctor ops --close-stale`, and check that an `abandoned` record pairs it, `doctor invocation-pairing` no longer reports it, and the Mission's status log and `meta.json` are byte-identical.

**Acceptance Scenarios**:

1. **Given** a `started` lifecycle record older than the threshold with no completion, **When** the operator runs `doctor ops --close-stale`, **Then** a new `abandoned` record pairs it, with a reason naming the doctor sweep and the threshold.
2. **Given** the same record, **When** the sweep runs, **Then** the Mission's status event log, `meta.json` and work package files are unchanged.
3. **Given** a closed orphan, **When** `doctor invocation-pairing` runs, **Then** it no longer reports that orphan and counts the `abandoned` record as a completion.
4. **Given** a `started` record younger than the threshold, **When** the sweep runs, **Then** it is reported as left open and the command exits 1, as it does for a fresh Op.
5. **Given** `--threshold 0`, **When** the sweep runs, **Then** every orphaned lifecycle record is closed.

---

### User Story 2 - The closures are committed (Priority: P1)

The maintainer wants the closures in the pull request without committing them by hand. The sweep commits the closure files on the current branch, as the Op sweep commits its closure spine.

**Why this priority**: operator ruling; uncommitted closures would leave the same open record on every other checkout.

**Independent Test**: run the sweep on an unprotected branch in a repository that tracks `kitty-ops/lifecycle/`, and check one commit containing only the new closure files.

**Acceptance Scenarios**:

1. **Given** an unprotected branch that tracks lifecycle records, **When** the sweep closes records, **Then** it commits exactly the new closure files and reports `committed`.
2. **Given** a repository whose lifecycle records are ignored or untracked by the primary branch (the #6410 rules), **When** the sweep closes records, **Then** it writes them, skips the commit and reports the skip reason.
3. **Given** a protected branch, **When** the sweep closes records, **Then** the commit is refused, the refusal is reported, the files stay written and nothing bypasses the protection.

---

### User Story 3 - Every checkout is swept (Priority: P2)

Lifecycle records live in the checkout that wrote them (an owned checkout, a lane worktree). The sweep closes orphans in every checkout of the repository, each closure written and committed in the checkout that holds the record, as the Op sweep does (#6661).

**Why this priority**: parity with the Op sweep; less common than the root-checkout case.

**Independent Test**: seed a stale orphan in a linked worktree and check that its closure lands and is committed there, not in the repository root checkout.

**Acceptance Scenarios**:

1. **Given** a stale orphan in a linked worktree, **When** the sweep runs from the repository root checkout, **Then** the `abandoned` record is written and committed in that worktree.

---

### Edge Cases

- A `started` record whose `at` cannot be parsed is treated as stale, with a parse warning, as an Op's unparseable `started_at` is.
- A group with several unpaired `started` records gets one `abandoned` record per unpaired `started` record that is stale.
- A second sweep finds nothing new to close in the groups it already balanced (idempotent).
- An older CLI that does not know the `abandoned` phase skips that record and still reports the orphan (accepted with the phase choice).
- A record that cannot be written is reported per entry, and the sweep continues with the rest.

## Domain Language

- **Lifecycle record**: one phase of a public action `spec-kitty next` issued, stored one file per record under `kitty-ops/lifecycle/` (ADR 2026-11-01-2). Phases: `started`, `completed`, `failed`, and now `abandoned`.
- **Orphan**: a `(mission_id, canonical_action_id)` group with more `started` records than completions.
- **Op record**: a governed Op's record under `kitty-ops/<id>.jsonl`. Not a lifecycle record; do not conflate the two.
- **Abandoned**: closed by the doctor sweep, not by the action's result. Not a failure of the action.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Abandoned lifecycle phase | As a maintainer, I want an `abandoned` lifecycle phase that pairs a `started` record so that a closure by the sweep is distinguishable from the action's own result. | High | Open | [build] | no |
| FR-002 | Abandoned pairs a started record | As a maintainer, I want an `abandoned` record to count as a completion in pairing, orphan detection and the pairing rate so that a closed orphan is no longer reported. | High | Open | [build] | no |
| FR-003 | Sweep closes stale orphans | As a maintainer, I want `doctor ops --close-stale` to write an `abandoned` record for every orphaned lifecycle record whose `started` record is older than `--threshold` (all at `0`) so that orphans can be closed without advancing the Mission. | High | Open | [build] | no |
| FR-004 | Mission untouched | As a maintainer, I want the sweep to leave the Mission's status log, `meta.json` and work package files unchanged so that closing a record never advances or alters the Mission. | High | Open | [build] | yes — paired with FR-003 on the same fixture: the closure is written while the Mission files stay byte-identical |
| FR-005 | Closure reason | As a reviewer, I want each `abandoned` record to carry a reason naming the doctor sweep and the threshold so that the closure is traceable. | Medium | Open | [build] | no |
| FR-006 | Closures committed | As a maintainer, I want the sweep to commit the closure files it wrote on the current branch, with the #6410 skip rules and a reported, never bypassed, protected-branch refusal, so that the closures reach the pull request. | High | Open | [build] | no |
| FR-007 | Every checkout | As a maintainer, I want orphans in every checkout of the repository swept, each closure written and committed in the checkout that holds the record, so that linked worktrees are covered as the Op sweep covers them. | Medium | Open | [build] | no |
| FR-008 | Fresh orphans reported | As a maintainer, I want orphans younger than the threshold reported as left open and to make the sweep exit 1, as fresh Ops do, so that open work is not hidden. | Medium | Open | [build] | no |
| FR-009 | Additive JSON | As a tool author, I want the `--json` sweep report to gain a `lifecycle_records` key listing each orphan (action, Mission, work package, agent, started time, age, action taken, commit outcome, error) while every existing key keeps its meaning so that existing consumers keep working. | Medium | Open | [build] | no |
| FR-010 | Documentation | As a maintainer, I want the docs that say lifecycle records have no close command, the CLI reference and the lifecycle ADR updated so that the docs match the shipped behavior. | Medium | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Append-only store | A sweep creates new record files only: 0 existing files under `kitty-ops/lifecycle/` are modified or removed (ADR 2026-11-01-2 preservation rule). | Reliability | High | Open |
| NFR-002 | Idempotence | A second sweep with the same threshold right after the first writes 0 new lifecycle records. | Reliability | High | Open |
| NFR-003 | Sweep cost | Sweeping 2,000 lifecycle records with no orphans adds under 2 seconds to `doctor ops --close-stale` on a developer machine. | Performance | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No new command | The close route is `doctor ops --close-stale`; no new command or flag is added (operator ruling). | Business | High | Open |
| C-002 | One lifecycle writer seam | Lifecycle records are written only through the existing locked lifecycle append; no raw append is added (the event-log writes gate). | Technical | High | Open |
| C-003 | Existing JSON keys unchanged | `open_ops`, `swept`, `skipped_fresh`, `threshold_hours` and `closure_spine` keep their meaning and stay Op-only. | Technical | High | Open |
| C-004 | Pairing key unchanged | Pairing stays keyed on `(mission_id, canonical_action_id)`; the work package id does not join the key. | Technical | Medium | Open |
| C-005 | Protection is never bypassed | A protected-branch refusal is reported; the sweep never uses a protected-branch override. | Technical | High | Open |

### Key Entities

- **Lifecycle record**: `canonical_action_id`, `phase`, `at`, `agent`, `mission_id`, optional `wp_id`, `reason`, `metadata`.
- **Sweep report**: the Op entries (unchanged) plus one lifecycle entry per orphaned `started` record.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After one `doctor ops --close-stale --threshold 0` on a repository with orphaned lifecycle records, `doctor invocation-pairing` reports 0 orphans — [build] · no-op passable: no
- **SC-002**: The same sweep leaves 100% of the Mission's status, `meta.json` and work package files byte-identical — [build] · no-op passable: yes — paired with SC-001 on the same fixture
- **SC-003**: On an unprotected branch that tracks lifecycle records, the sweep leaves 0 uncommitted closure files — [build] · no-op passable: no

## Assumptions

- The threshold, its default (24 hours) and its `0` meaning are shared with the Op sweep.
- The `abandoned` record copies the `started` record's action id, agent, Mission and work package, as a completion does today.
- Older CLIs skipping an `abandoned` record is acceptable (operator ruling on the phase).
- The sweep's own commit message names the doctor sweep; its co-author trailer follows the repository's commit settings, as the Op sweep's does.

## Out of Scope

- A distinct close command, or closing a single record by id.
- Changing how `spec-kitty next` pairs its own records.
- The doctor-ops sweep performance budget (#5052).
- Uncommitted `next` writes dirtying consolidate (#5938) and the broader abandon/resume semantics (#3969).
