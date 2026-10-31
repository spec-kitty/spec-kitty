# Implementation Plan: Retry a residue-safe successor when its predecessor did not settle

**Branch**: `issue-6688-residue-successor-retry` | **Date**: 2026-10-30 | **Spec**: `kitty-specs/residue-successor-retry-on-unsettled-predecessor-01M67J1B/spec.md`
**Input**: Mission specification from `kitty-specs/residue-successor-retry-on-unsettled-predecessor-01M67J1B/spec.md`

## Summary

First adoption settles a successor with a baseline `success` record even when the successor's superseded
predecessor recorded `failed`/`skipped`, so the repair is never retried (C-006 of ADR `2026-10-17-1`,
pinned as a strict `xfail` by #6680). The fix makes the settlement rule follow the predecessor: a migration
that declares a `predecessor_id` is settled only when that predecessor's recorded outcome proves the repair
ran (a `success` in the predecessor's authoritative partition, or a pending adoption that will write one).
The rule lives in the one selection-view predicate and is reused by `reselect_when_recorded`, which both
ledger-diff selection and the runner's skip gate already consult, so the retry cannot be lost between
selection and apply. `detect()` stays the idempotency guard: a repaired project is re-evaluated, never
re-applied.

## Technical Context

**Language/Version**: Python 3.11+ (repo floor; `from __future__ import annotations` throughout)
**Primary Dependencies**: none new — `packaging.version`, `pathlib`; `pytest` for tests
**Storage**: `.kittify/migration-ledger.jsonl` (tracked partition), `.kittify/migrations/clone-local.jsonl` (per-clone), `.kittify/metadata.yaml` (pre-ledger `applied_migrations`)
**Testing**: pytest; `tests/specify_cli/upgrade/test_residue_safe_successors_6669.py` (`integration`, `git_repo` markers) for the successors and the fix, plus the existing registry/runner suites
**Target Platform**: the `spec-kitty` CLI (`spec-kitty upgrade`), any OS the CLI supports
**Project Type**: single Python package (`src/specify_cli/`)
**Performance Goals**: no added ledger read for a migration that declares no predecessor (guard before any read); at most one extra ledger/metadata probe per declared successor per run
**Constraints**: no edit to a shipped migration module (DIRECTIVE_044); no `target_version`, manifest-slot or adoption-ceiling change; no ledger schema change
**Scale/Scope**: one registry predicate (~20 lines), one `BaseMigration` hook change, one classvar on two successor modules, tests, ADR amendment and one changelog entry

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Evidence |
|------|--------|----------|
| Single canonical authority | Pass | "settled" stays one predicate (`registry._settled_in_view`); `reselect_when_recorded` calls the same helper instead of restating the rule |
| DIRECTIVE_044 (no edit to a shipped/frozen migration) | Pass | the frozen backfill and the four shipped predecessors are untouched; `git diff --diff-filter=MDR origin/main -- 'src/specify_cli/upgrade/migrations/m_*.py'` covers only the two new successor modules (a classvar each) |
| ATDD-first / test-first bug fixing (DIRECTIVE_034) | Pass | the red is the existing strict `xfail`, run with `--runxfail`; the fix removes the marker only after the assertion passes |
| Locality of change (DIRECTIVE_024) | Pass | registry + base hook + two one-line declarations; no caller changes |
| No full heavy suites (NO_FULL_HEAVY_SUITES_IN_MISSION) | Pass | scoped upgrade/registry/runner suites locally; CI owns the rest |
| Docs freshness | Pass | ADR amendment + changelog entry; docs index does not list changelog entries, `check_docs_freshness --ci` run after the edit |
| Supply chain (DIRECTIVE_051) | N/A | no dependency decision |

## Project Structure

### Documentation (this mission)

```
kitty-specs/residue-successor-retry-on-unsettled-predecessor-01M67J1B/
├── spec.md          # mission requirements
├── research.md      # discovery + traced record flow, decisions D1-D4
├── plan.md          # this file
├── quickstart.md    # how to reproduce and verify
└── tasks/           # work packages (created by /spec-kitty.tasks)
```

### Source Code (repository root)

```
src/specify_cli/upgrade/
├── registry.py                                # selection view: the retry rule + one public helper
├── migrations/base.py                         # `predecessor_id` ClassVar; `reselect_when_recorded` qualification
├── migrations/_residue_successor.py           # lane mixin: declares the predecessor (unchanged semantics)
├── migrations/m_0_9_0_residue_safe_*.py       # already declare `predecessor_id`
├── migrations/m_0_9_1_residue_safe_*.py       # already declare `predecessor_id`
├── migrations/m_2_0_6_residue_safe_*.py       # declare `predecessor_id = PREDECESSOR_ID`
└── migrations/m_3_1_1_residue_safe_*.py       # declare `predecessor_id = PREDECESSOR_ID`

tests/specify_cli/upgrade/test_residue_safe_successors_6669.py   # red-first pin + runner coverage
docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md           # amendment: the retry rule replaces C-006
docs/changelog/CHANGELOG.md                                      # [Unreleased] entry (#6688)
```

**Structure Decision**: the change stays inside the upgrade subsystem's existing seams — the registry
(authority for selection), `BaseMigration` (the documented reselection hook) and the four successor modules
(which already name their predecessor). No new module is needed.

## Phase 0 — research outcome

Recorded in `research.md`: the reproduction, the traced record flow (backfill plan → adoption projection →
selection → runner gate), decisions D1-D4 and the rejected routes. No `NEEDS CLARIFICATION` remains.

## Phase 1 — design

### The rule

```
settled(m) =
    (recorded_success(m) or pending_adoption_settles(m))     # unchanged evidence for m
    AND predecessor_outcome_settles(m)                       # new, only when m.predecessor_id is set

predecessor_outcome_settles(m) =
    m.predecessor_id == ""                                   -> True   # every ordinary migration
    registry lookup of m.predecessor_id is None              -> True   # cannot evaluate: keep the record's word
    else  settled_success(predecessor) or pending_adoption_settles(predecessor)
```

- `registry._settled_in_view(ledger, migration, adopting)` gains the second conjunct; it stays the one
  predicate behind `MigrationRegistry.get_applicable`, `settled_in_selection_view` and the successors'
  `detect()` gate.
- A public helper `registry.predecessor_outcome_settled(project_path, migration)` answers the second
  conjunct with the same adoption projection `settled_in_selection_view` uses (so a dry run and a live run
  agree on a pre-ledger project).
- `BaseMigration.reselect_when_recorded(project_path)` returns True for a migration with a declared
  predecessor whose outcome does not settle it. The runner's skip gate
  (`migration_settled(...) and not reselect_when_recorded(...)`) and ledger-diff selection
  (`not settled or reselect_when_recorded(...)`) therefore agree. The empty `predecessor_id` guard runs
  before any ledger read, so the ~200 other migrations pay one attribute check.

### Why this cannot replay a completed repair

`detect()` is unchanged and state-based for all four successors; a repaired project's `detect()` returns
False, so `apply()` never runs and `_record_ledger_result` appends nothing new (`(id, result)` is
idempotent). The rule changes only *who is re-evaluated*, never *what is re-applied*.

### Successor declarations

`_residue_successor.ResidueSafeLaneSuccessorMixin` keeps `predecessor_id` (0.9.0/0.9.1 set it);
`m_2_0_6_residue_safe_consistency_sweep` and `m_3_1_1_residue_safe_normalize_status_json` add
`predecessor_id = PREDECESSOR_ID` next to their `migration_id`, matching the constant their `detect()`
already reads.

### Tests (red-first)

1. `test_c006_an_unsettled_predecessor_record_still_lets_the_successor_run[failed|skipped]` — drop the
   strict `xfail`; it is red on `main` under `--runxfail` and green after the rule.
2. A new runner-level case: pre-ledger project at 3.2.0, predecessor `failed` (and `skipped`), dirty
   Mission; `MigrationRunner.upgrade` applies the successor and repairs the Mission, for all four pairs
   (0.9.0/0.9.1 prefer the tracked-project fixture; 2.0.6 needs the `quiet_runtime_assets` fixture).
3. Second-run idempotency on the same fixture: no applied migration, `changes_made == []`, tree
   byte-identical — the "never re-run a completed repair" half of the rule.
4. A positive control in the same test family: with the predecessor `success`, the successor stays inert
   (existing `test_a_settled_predecessor_makes_the_successor_inert` and the dry-run/live cases), so the
   retry assertions cannot pass vacuously.

## Risks and mitigations

| Risk | Mitigation |
|------|------------|
| The rule silently widens to every migration | Guarded on a declared `predecessor_id`; §C-004 and a test asserting an ordinary migration's reselection is unchanged |
| A successor re-evaluates forever after repairing under an unsettled predecessor | Accepted and documented: identical to the already-accepted "inert successor is re-listed" residual; `detect()` is the guard and nothing is re-applied |
| Recursion through a chained successor | One level only, documented: the named predecessor must be a shipped migration; a registry miss keeps the record's word |
| The apply-time gate drifts from selection | Both go through `reselect_when_recorded`, which calls the registry helper — no second copy of the rule |
| Docs drift | ADR amendment replaces the C-006 residual with the rule; `check_docs_freshness --ci` after the edit |

## Complexity Tracking

No charter violations; no complexity justification needed.

## Implementation Concern Map

- **IC-01 — the selection view answers for the predecessor.** `_settled_in_view` gains
  `predecessor_outcome_settles`; the public helper mirrors `settled_in_selection_view`'s adoption
  projection. Touches `registry.py` only.
- **IC-02 — the apply-time gate agrees.** `BaseMigration.predecessor_id` (documented ClassVar) and the
  qualification in `reselect_when_recorded`, delegating to the registry helper. Touches `migrations/base.py`.
- **IC-03 — the four successors declare their predecessor.** The lane mixin already declares it for
  0.9.0/0.9.1; the re-implemented pair (`2.0.6`, `3.1.1`) declares it beside its `migration_id`, reusing the
  `PREDECESSOR_ID` constant its `detect()` already reads.
- **IC-04 — red-first pins.** Remove the strict `xfail`; add the runner-level retry case (all four pairs,
  both predecessor outcomes) and the second-run idempotency case on the same fixture.
- **IC-05 — documentation.** ADR `2026-10-17-1` amendment (rule + revised residual list) and the
  `[Unreleased]` changelog entry with `(#6688)`.
