# Implementation Plan: Upgrade dry-run reports the sequenced verdict a real run reaches

**Branch**: `issue-6552-upgrade-dry-run-sequenced-verdict` | **Date**: 2026-10-31 | **Spec**: `kitty-specs/upgrade-dry-run-sequenced-verdict-01M68J9V/spec.md`
**Input**: Mission specification from `kitty-specs/upgrade-dry-run-sequenced-verdict-01M68J9V/spec.md`
**Research**: `kitty-specs/upgrade-dry-run-sequenced-verdict-01M68J9V/research.md`

## Summary

`upgrade --dry-run` runs the real, ordered migration loop but every `apply(dry_run=True)`
returns without writing, so a migration whose `detect()` reads state an earlier migration in
the same run writes is judged against the pre-run tree and reported
`not needed (project already in target state)` while the real run applies it (#6552).

The fix gives the runner **one sequencing decision**: it remembers which migrations this
dry run has reported applied, and a migration that declares the predecessors its `detect()`
reads (`BaseMigration.sequenced_after`, a detect-input declaration, never an ordering
authority) is reported **applied** — with a `dry-run: would apply after <id>` change line —
when one of those predecessors is in that set. The measured
`3.2.6_issue_matrix_driver_repoint` → `3.2.6_gate_artifact_merge_drivers` pair declares the
relationship. An *undeclared* dry-run skip stops claiming target state and claims only the
current tree. Real runs are untouched: the prediction branch is reachable only under
`dry_run`, where the predecessor's writes have not landed.

## Technical Context

**Language/Version**: Python 3.11 (`src/specify_cli/upgrade/runner.py`,
`src/specify_cli/upgrade/migrations/base.py`)
**Primary Dependencies**: stdlib + existing upgrade stack (`MigrationRegistry`,
`MigrationLedger`, `ProjectMetadata`); no new dependency
**Storage**: the project tree, `.git/config`, and the two ledger partitions
(`.kittify/migration-ledger.jsonl`, `.kittify/migrations/clone-local.jsonl`) — read-only
under `--dry-run`
**Testing**: pytest; unit tests over the real `MigrationRunner` loop with the two real
migrations registered, plus a CLI-level witness through the `upgrade` typer command
**Target Platform**: any platform the CLI supports (POSIX + Windows); no platform-specific code
**Project Type**: single Python package (`src/specify_cli`)
**Performance Goals**: no project copy, no extra `detect()`/`apply()` call; the decision is an
O(number of declarations) set membership test per migration
**Constraints**: dry run writes nothing; real-run verdicts, warnings and ledger records
unchanged; `order_manifest.txt` stays the only execution-order authority
**Scale/Scope**: ~3 source files, 1 test module, 1 doc paragraph, 1 changelog entry

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Note |
|------|--------|------|
| Single canonical authority | Pass | The runner stays the one verdict authority; the ledger stays the applied authority; the manifest stays the order authority |
| ATDD-first / red-first (DIRECTIVE_034) | Pass | The parity test fails on `origin/main` before the fix (measured, see research.md) |
| `change-apply-smallest-viable-diff`, `DIRECTIVE_024` locality | Pass | No new module, no new CLI surface, no new JSON field |
| DIRECTIVE_041 (test only real behaviour/invariants) | Pass | Every new test pins the reported defect or the no-writes invariant |
| Complexity ceiling 15 (`C901`) | Pass (to verify) | The prediction reuses the existing `can_apply` block; extract a helper if `_apply_migration` crosses the ceiling |
| NO_FULL_HEAVY_SUITES_IN_MISSION | Pass | Targeted `tests/upgrade` + `tests/compat` files only |
| Terminology Canon / no legacy terms | Pass | No new operator-facing noun; the change line reuses "dry-run:" and migration ids |

## Project Structure

### Documentation (this mission)

```
kitty-specs/upgrade-dry-run-sequenced-verdict-01M68J9V/
├── spec.md              # mission specification
├── research.md          # Phase 0 output (discovery, decisions D-001..D-004)
├── plan.md              # this file
├── data-model.md        # Phase 1 output (declaration + sequenced state)
├── quickstart.md        # Phase 1 output (how to see the fix)
├── issue-matrix.json    # #6552 row, verdict at close-out
├── tasks/               # Phase 2 output (/spec-kitty.tasks)
└── tasks.md             # Phase 2 output
```

No `contracts/` directory: this Mission adds no interface, endpoint or payload shape (it
keeps the existing `migrations_applied`/`migrations_skipped` shape). `meta.json` records
`"contracts": "none"` with a rationale.

### Source Code (repository root)

```
src/specify_cli/upgrade/
├── runner.py                                  # the one sequencing decision (dry run only)
└── migrations/
    ├── base.py                                # BaseMigration.sequenced_after declaration
    ├── README.md                              # one paragraph: declaring detect inputs
    └── m_3_2_6_issue_matrix_driver_repoint.py # declares the gate-artifact predecessor

tests/
├── upgrade/test_dry_run_sequenced_verdict.py   # new: parity, honest wording, can_apply, no writes
├── upgrade/test_runner_status_classification.py# existing: real-run skip wording stays
└── compat/test_dry_run_parity.py               # existing: pending-set parity stays green

docs/changelog/CHANGELOG.md                     # [Unreleased] entry (#6552)
```

**Structure Decision**: single project; the change lives entirely inside the existing
upgrade subsystem (`src/specify_cli/upgrade/`), and its tests inside the existing
`tests/upgrade/` and `tests/compat/` homes. No new package, module or directory.

## Phase 0: Research

Complete — see `research.md`. Decisions D-001..D-004 (no project copy; declared detect
inputs; predicted verdict is `applied`; real runs untouched) are carried into the design
below.

## Phase 1: Design

### The one sequencing decision

`MigrationRunner` keeps a per-run set of the migration ids it has *reported applied*
(`migrations_applied`) — the run's sequenced view of "what has already happened by the time
we reach the next migration". In a real run that view is implied by the tree itself; in a
dry run the tree is unchanged, so the set is the only record of it.

The decision lives in one place, `MigrationRunner._apply_migration`:

1. `detect()` answers as today.
2. If `detect()` is False **and** `dry_run` **and** one of the migration's
   `sequenced_after` predecessors is in the run's applied set, the migration is
   **predicted**: it runs the same `can_apply` gate the real run runs (so a refusal still
   skips with its own reason) and is reported `applied` with the change line
   `dry-run: would apply after <id>`.
3. Otherwise a False `detect()` skips as today, except that under `dry_run` the warning
   reads `not needed on the current tree` — a real run keeps
   `not needed (project already in target state)`.

No second authority: the prediction never adds a migration the ledger did not select, never
reorders the loop, and never runs on a real run.

### Declaration

`BaseMigration.sequenced_after: ClassVar[tuple[str, ...]] = ()` — "the migration ids whose
application, earlier in the same run, changes what this migration's `detect()` reads".
Unknown ids are ignored; a declaration never fails a run and never reorders it.

### Error handling

The predicted path reuses the existing `can_apply` exception handling
(`NotInsideRepositoryError`, `GitCommonDirUnavailableError`), so a prediction cannot crash
where a real run would not. A prediction is only ever a verdict and a change line; it
writes nothing, records nothing, and stamps nothing.

## Phase 2: Task planning approach

Two work packages:

- **WP01 — the sequencing decision**: `sequenced_after` on `BaseMigration`, the runner
  prediction + dry-run wording, the repoint declaration, and the red-first test module
  (`tests/upgrade/test_dry_run_sequenced_verdict.py`) covering parity, honest wording,
  `can_apply`, settled predecessors, and the no-writes invariant.
- **WP02 — the operator surface and the witness**: a CLI-level witness through
  `spec-kitty upgrade --dry-run` (production-path non-vacuity), the `migrations/README.md`
  paragraph for authors, and the `[Unreleased]` changelog entry.

## Complexity Tracking

No charter violations. `_apply_migration` grows by one guarded branch; if `ruff` `C901`
reports it above 15, the prediction and the dry-run wording are extracted into small
helpers rather than left over the ceiling.

## Implementation Concern Map

### IC-01 — Sequencing decision in the runner

- **Purpose**: Make the dry run's per-migration verdict follow the run's own applied set,
  so the preview cannot report work the run then does.
- **Relevant requirements**: FR-001, FR-003, FR-004, NFR-002, NFR-003, C-002, C-003
- **Affected surfaces**: `src/specify_cli/upgrade/runner.py` (`_apply_migration`, the run's
  applied set), `src/specify_cli/upgrade/migrations/base.py`
- **Sequencing/depends-on**: none
- **Risks**: a real-run branch added by accident (guarded by C-002 tests); the
  `not needed` wording pinned by two existing tests (both keep the substring `not needed`).

### IC-02 — Declaring the measured pair

- **Purpose**: Turn the reported 3.2.6 relationship from a docstring note into a
  declaration the preview can consume.
- **Relevant requirements**: FR-002, FR-005, C-001
- **Affected surfaces**: `src/specify_cli/upgrade/migrations/m_3_2_6_issue_matrix_driver_repoint.py`,
  `src/specify_cli/upgrade/migrations/_merge_driver_seeding.py` (docstring pointer only)
- **Sequencing/depends-on**: IC-01 (the attribute must exist)
- **Risks**: the declaration must not be mistaken for ordering; the docstring says so
  explicitly and the manifest is unchanged.

### IC-03 — Witness and operator-facing documentation

- **Purpose**: Prove the fix on the production path and tell an operator and a migration
  author what changed.
- **Relevant requirements**: FR-006, SC-001..SC-004
- **Affected surfaces**: `tests/upgrade/test_dry_run_sequenced_verdict.py`,
  `src/specify_cli/upgrade/migrations/README.md`, `docs/changelog/CHANGELOG.md`
- **Sequencing/depends-on**: IC-01, IC-02
- **Risks**: a helper-only witness would be vacuous (tactic
  `acceptance-criteria-non-vacuity`); the CLI test must assert the rendered human output.
