# Mission Specification: Retry a residue-safe successor when its predecessor did not settle

**Mission Branch**: `issue-6688-residue-successor-retry`
**Created**: 2026-10-30
**Status**: Draft
**Input**: Issue spec-kitty/spec-kitty#6688 — "Residue-safe successors never retry on a pre-ledger project whose predecessor recorded skipped or failed".

## Intent Summary

**Primary actor**: a maintainer (or CI job) running `spec-kitty upgrade` on a project that predates the
migration ledger. **Trigger**: the project's `metadata.yaml` records one of the four superseded residue
predecessors as `failed` or `skipped` while the legacy `kitty-specs/` state that migration repairs is still
present. **Desired outcome**: the residue-safe successor runs and repairs the Missions, and a project whose
repair is already done is never re-applied. **Invariant**: a successor is settled by its predecessor's
recorded outcome, never by an adoption-baseline record alone; `detect()` alone decides that work is needed.
**Confirmed by**: the operator's task statement (`make the retry rule honest — retry where the predecessor's
outcome does not prove the work is done, and never re-run something that genuinely completed`) and the issue's
`Expected` paragraph. **Assumptions**: the four successors are the only declared successors of a shipped
migration; adoption-provenance marking (route 1) and manifest-semantics changes (route 3) are out of scope.

## Context

PR #6680 (#6669) replaced four shipped, byte-frozen migrations—`0.9.0_frontmatter_only_lanes`,
`0.9.1_complete_migration`, `2.0.6_consistency_sweep`, `3.1.1_normalize_status_json`—with residue-aware
successors that repair the same Missions and leave `kitty-specs/` residue folders untouched. Each successor
sits in its predecessor's manifest slot and its `detect()` returns False when the predecessor is settled in
the selection view, so a project that already ran the predecessor never runs the successor on top of it.

On a **pre-ledger** project (one stamped at 3.2.0 whose `.kittify/metadata.yaml` records a predecessor as
`failed` or `skipped`), that pair of guards produces a stuck project:

1. the frozen adoption backfill (`4.0.0rc8_backfill_migration_ledger`) settles every registered migration
   whose `target_version` is below the recorded version — including the successor id — with a real
   `success` record, because the version stamp is the only evidence a pre-ledger project has;
2. the predecessor is selected (a `failed`/`skipped` record never settles), but it is now a
   `SupersededMigration` no-op, so nothing is repaired;
3. the successor is not selected: the runner's skip gate and ledger-diff selection both read the backfilled
   `success` record.

Before #6680 the predecessor itself re-detected and retried in exactly this state. The repair is therefore
lost on first adoption: a recoverable project stays stuck, with a `success` record asserting work that never
happened. #6680 pinned the behaviour as a strict `xfail`
(`test_c006_an_unsettled_predecessor_record_still_lets_the_successor_run[failed|skipped]`, red under
`--runxfail`) and recorded it as residual `C-006` in ADR `2026-10-17-1`, Amendment 2026-10-25b.

Reproduced on current `main` before any change: the pinned test fails on its own first assertion — the
successor `3.1.1_residue_safe_normalize_status_json` is missing from the selected set, which instead holds
the superseded predecessor and the adoption backfill.

## Decision recorded by this mission

The issue named three routes; this mission takes route 2 and rejects the other two on governance grounds:

- **Chosen — widen the settlement rule (route 2).** A successor is settled when its *predecessor's* recorded
  outcome proves the repair ran. A successor's own record cannot prove it, because first adoption can stamp
  it without the work having happened. This needs no edit to a frozen module and no change to manifest
  semantics.
- **Rejected — mark adoption-baseline records (route 1).** It edits the frozen backfill (DIRECTIVE_044), so it
  needs a supersession of the adoption migration itself plus a new ledger record field — a far larger blast
  radius than the defect.
- **Rejected — move each successor's `target_version` above the adoption ceiling (route 3).** It changes
  manifest semantics and would drop the repair from every upgrade targeted between the successor's version
  and rc8.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A recoverable pre-ledger project gets the repair retried (Priority: P1)

A maintainer upgrades a project stamped 3.2.0 whose `metadata.yaml` records one of the four predecessors as
`failed` (or `skipped`). The project still holds the legacy `kitty-specs/` state that migration repairs. First
adoption must not convert that unproven state into a `success`; the residue-safe successor runs and repairs
the Missions, exactly as the predecessor would have on `main` before #6680.

**Why this priority**: This is the reported defect. Until it is fixed, a recoverable project is permanently
stranded behind a ledger record that claims a repair it never received.

**Independent Test**: Build a pre-ledger project at 3.2.0 with the predecessor recorded `failed` (and,
separately, `skipped`) and a dirty Mission, run `MigrationRunner.upgrade`, and assert the successor is
selected, is reported applied, and the Mission is repaired — no `xfail`.

**Acceptance Scenarios**:

1. **Given** a pre-ledger project stamped above a successor's `target_version` whose metadata records its
   predecessor `failed`, **When** selection runs, **Then** the successor is in the selected set and the
   selection view reports it unsettled.
2. **Given** the same project, **When** `upgrade` runs, **Then** the successor applies, the dirty Mission is
   repaired, and the predecessor is still recorded as the no-op it is.
3. **Given** a metadata record of `skipped` rather than `failed`, **When** the run happens, **Then** the same
   retry occurs (a `skipped` record never proves the work was done).

### User Story 2 - A completed repair is never re-applied (Priority: P1)

The same maintainer upgrades that project a second time, and upgrades a project whose successor genuinely
completed earlier. Nothing is re-applied: `detect()` stays the idempotency guard, no Mission file changes,
and no new repair is reported.

**Why this priority**: The retry rule must not become a replay rule. Re-running a completed repair is the
regression this fix is most likely to introduce, and `2.0.6`/`3.1.1` write to Mission metadata and state.

**Independent Test**: After the successful repair from User Story 1, snapshot the tree, run `upgrade` again,
and assert `changes_made == []`, the successor is not reported applied, and the tree is byte-identical.

**Acceptance Scenarios**:

1. **Given** a repaired project whose predecessor is still unsettled, **When** `upgrade` runs again, **Then**
   the successor is not applied and no file under `kitty-specs/` changes.
2. **Given** a project where the successor itself applied and recorded `success` while the predecessor never
   settled, **When** selection runs, **Then** the successor is selected for re-evaluation and its `detect()`
   — not its record — decides that no work is needed.

### User Story 3 - A settled predecessor still makes the successor inert (Priority: P2)

A project whose predecessor recorded `success`, in the ledger or through the adoption projection, keeps the
successor inert in selection, live run and dry run.

**Why this priority**: This is the #6680 guarantee that protects ledger-era projects; the retry rule must not
weaken it.

**Independent Test**: Record the predecessor `success`, assert the successor is settled in the selection view,
`detect()` is False, and a live run neither applies nor changes anything.

**Acceptance Scenarios**:

1. **Given** a ledger-era project with the predecessor `success`, **When** selection and a live upgrade run,
   **Then** the successor is not applied and no file changes.
2. **Given** a pre-ledger project with the predecessor `success` in `metadata.yaml`, **When** the successor's
   `detect()` is called, **Then** it is False (adoption will settle the predecessor).

### Edge Cases

- The predecessor has no `predecessor_id` (every ordinary migration): the widened rule is inert — no extra
  ledger read, no behaviour change.
- The predecessor id is no longer registered: the recorded `success` keeps settling the successor (no
  invented replay for an id the codebase cannot evaluate).
- The successor has no record at all: unchanged — it is selected, and `detect()` decides.
- Adoption runs in the same upgrade pass as the retry (the backfill is first in the manifest): the runner's
  skip gate sees the freshly backfilled record and must still not skip the successor.
- A superseded predecessor records `failed`, then `skipped` with its `superseded_by` note in the same run: the
  successor's rule reads the outcome, never the note.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Retry is derived from the predecessor's outcome | As a maintainer of a pre-ledger project, I want a successor selected whenever its predecessor's recorded outcome does not prove the repair ran, so that a recoverable project is repaired instead of stranded. | High | Open | [build] | no — the pinned `C-006` test is red on `main` and green only with the rule |
| FR-002 | The runner's skip gate agrees with selection | As a maintainer, I want the run that adopted the ledger to still apply the successor, so that the retry is not lost between selection and apply. | High | Open | [build] | no — a backfilled `success` record exists by apply time |
| FR-003 | A successor's own record never proves its repair ran | As an auditor, I want a `success` stamped by first adoption to stop settling a successor whose predecessor is unsettled, so that the ledger stops asserting work that never happened. | High | Open | [build] | no — the record is present on `main` |
| FR-004 | A settled predecessor keeps the successor inert | As a maintainer of a ledger-era project, I want the #6680 gate unchanged, so that a completed predecessor is never followed by its successor. | High | Open | [ratchet] | no — paired with FR-001 on the same fixture family |
| FR-005 | A completed repair is never re-applied | As a maintainer, I want `detect()` to remain the idempotency guard, so that a second upgrade applies nothing and changes nothing. | High | Open | [ratchet] | no — the same-fixture second run must report no changes |
| FR-006 | The strict xfail becomes a passing pin | As a maintainer, I want the `C-006` case pinned without `xfail`, so that a regression fails the suite instead of being absorbed. | Medium | Open | [build] | no — `--runxfail` red on `main` |
| FR-007 | The rule is recorded in the ADR and the changelog | As a reader, I want ADR `2026-10-17-1` to carry the retry rule instead of the `C-006` residual, so that the ledger's selection semantics stay documented. | Medium | Open | [build] | no — the ADR today records `C-006` as an accepted residual |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No added ledger cost for ordinary migrations | The widened rule adds zero ledger reads for a migration that declares no predecessor: `reselect_when_recorded` returns without touching the ledger when `predecessor_id` is empty, measured by the existing selection timing staying within noise on the upgrade suite. | Performance | Medium | Open |
| NFR-002 | One predicate, one rule | Selection (`get_applicable`) and the runner's skip gate decide "settled" through one shared predicate; no second copy of the retry rule is introduced, verified by review of the diff and the existing registry tests. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No shipped migration module is edited | `git diff --diff-filter=MDR origin/main -- 'src/specify_cli/upgrade/migrations/m_*.py'` stays empty for shipped modules (DIRECTIVE_044); the frozen backfill in particular is untouched. | Technical | High | Open |
| C-002 | No manifest or ceiling semantics change | The four successors keep their `target_version` and manifest slot; the adoption ceiling in the backfill is unchanged. | Technical | High | Open |
| C-003 | No ledger schema change | No new record field and no change to what first adoption writes; the fix reads the existing records. | Technical | High | Open |
| C-004 | The fix is scoped to declared successors | Only a migration that declares a superseded predecessor is affected; every other migration keeps its current settlement and reselection behaviour. | Technical | High | Open |

### Key Entities

- **Successor migration**: a registered migration that replaces a superseded one (`predecessor_id`), re-implementing the same repair residue-safely. Its `detect()` is state-based and is the only thing that may decide work is needed.
- **Predecessor outcome**: the last authoritative ledger record (or the pending adoption projection) for the superseded id — `success`, `skipped`, `failed`.
- **Adoption baseline**: the first-adoption `success` records the frozen backfill writes for ids below the recorded version, evidence from the version stamp rather than from a run.
- **Selection view**: the single predicate (`registry.settled_in_selection_view`) that answers whether a migration is settled for a project, shared by ledger-diff selection and by each successor's `detect()` gate.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `test_c006_an_unsettled_predecessor_record_still_lets_the_successor_run[failed|skipped]` passes without `xfail` and fails (red) when the retry rule is reverted — [build] · no-op passable: no
- **SC-002**: For all four successors, a second upgrade after the repair reports zero applied migrations and changes zero bytes under `kitty-specs/` — [ratchet] · no-op passable: no
- **SC-003**: Every existing test in `tests/specify_cli/upgrade/` and the migration architectural gates stay green, with the shipped-module diff empty — [ratchet] · no-op passable: no
