# Implementation Plan: Retire the stale `issue-matrix.md` merge-driver row

**Branch**: `issue-7217-retire-stale-issue-matrix-md-driver-row` | **Date**: 2026-11-05
**Spec**: `kitty-specs/retire-stale-issue-matrix-md-driver-row-01M6P3EE/spec.md`
**Governing issue**: [#7217](https://github.com/spec-kitty/spec-kitty/issues/7217)

## Summary

`3.2.6_gate_artifact_merge_drivers` (`clone_local_effect = True`) re-applies on every fresh
clone because the driver's `git config --local` half never travels with the commit; its
`apply()` then re-appends `kitty-specs/**/issue-matrix.md merge=spec-kitty-issue-matrix`, a row
whose artifact no code path writes and whose mapped driver parses `issue-matrix.json`'s `rows`
array. The row is retired, the driver is not.

A shipped migration cannot be edited (DIRECTIVE_044), so the historical migration is
**superseded** (`SUPERSEDED_MIGRATIONS`) by a new `4.0.0rc8_retire_issue_matrix_md_row`
migration that:

1. seeds the two gate-artifact rows that still route real artifacts
   (`acceptance-matrix.json`, `issue-matrix.json`) with their canonical driver names — the
   half of the superseded migration that must not be lost (#2804);
2. removes the retired `.md` row wherever it was already written, idempotently;
3. leaves a project whose file is already canonical untouched (byte-level no-op).

Because the superseded module is then no longer a live `MergeDriverSeedingMigration`,
`merge_attribute_seed_lines()` (the `init` seed, #6416) stops writing the inert line with no
new special case, and `init`-then-`upgrade` stays a no-op.

## Which side is wrong — settled before the change

| Evidence | Where | Verdict |
|---|---|---|
| No code path creates `issue-matrix.md` | `tests/architectural/test_issue_matrix_json_migration_completeness.py` (T027b) | The artifact is legacy read-only |
| The declared driver pattern is `.json` only | `_MERGE_DRIVERS` in `src/specify_cli/lanes/consolidation.py` | The row is an orphan |
| The orphan row is rejected as drift | `test_declared_merge_drivers_are_registered_in_gitattributes` | The row must go |
| The driver parses a JSON `rows` array | `consolidation/drivers.py::run_issue_matrix_driver` | Re-pointing it at Markdown would be wrong even if it fired |
| The `.json` repoint is the fix, and is complete | `m_3_2_6_issue_matrix_driver_repoint.py` | The `.json` side is right; it just does not remove the predecessor row |

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: existing upgrade stack (`MigrationRegistry`, `supersession`,
`MergeDriverSeedingMigration`); no new dependency
**Storage**: the project's `.gitattributes` (tracked) and `.git/config` (clone-local)
**Testing**: pytest — unit tests over the successor's `detect()`/`apply()`, an integration
test through `MigrationRunner`, an end-to-end CLI test through the `upgrade` typer command
**Target Platform**: POSIX + Windows (no platform-specific code)
**Project Type**: single Python package (`src/specify_cli`)
**Constraints**: DIRECTIVE_044 (no edits to shipped migration modules); `order_manifest.txt`
stays the ordering authority; `.gitattributes` bytes are the contract
**Scale/Scope**: 1 new migration module, 1 supersession entry, 1 manifest line, 1 docstring,
~5 test files

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Note |
|------|--------|------|
| Single canonical authority | Pass | `_MERGE_DRIVERS` stays the one driver declaration; the manifest stays the order authority; `SUPERSEDED_MIGRATIONS` stays the one supersession table |
| ATDD-first / red-first (DIRECTIVE_034) | Pass | The end-to-end and guard tests fail on `origin/main` before the fix (measured in research.md) |
| DIRECTIVE_044 (shipped migrations immutable) | Pass | Both 3.2.6 modules keep their bytes; the fix is additive |
| `change-apply-smallest-viable-diff` | Pass | No new CLI surface, no new artifact, no new flag |
| DIRECTIVE_041 (test only real behaviour) | Pass | Every new test pins the reported defect, the healing path or the no-driver-loss invariant |
| NO_FULL_HEAVY_SUITES_IN_MISSION | Pass | Targeted `tests/upgrade`, `tests/init`, and the two architectural guards |
| Terminology Canon | Pass | "retired" / "superseded" are the documented upgrade nouns; no new operator noun |

## Project Structure

```
kitty-specs/retire-stale-issue-matrix-md-driver-row-01M6P3EE/
├── spec.md              # this mission's specification
├── research.md          # grounding: reproduction, the "which side is wrong" evidence
├── plan.md              # this file
├── issue-matrix.json    # #7217 row, verdict at close-out
├── tasks/               # work-package prompts
└── tasks.md             # work-package index

src/specify_cli/upgrade/
├── supersession.py                                   # + the retirement entry
├── init_seed.py                                      # docstring: the workaround is gone
├── runner.py                                         # − the dead SEQUENCED_AFTER entry
└── migrations/
    ├── order_manifest.txt                            # + the successor's slot
    └── m_4_0_0rc8_retire_issue_matrix_md_row.py      # new
```

## Phase 1 — Design decisions

- **D-001: supersede, do not edit.** `SUPERSEDED_MIGRATIONS["3.2.6_gate_artifact_merge_drivers"]
  = "4.0.0rc8_retire_issue_matrix_md_row"`. The substitute keeps the shipped identity, routing
  key and `content_hash`; recorded history never reads as drift.
- **D-002: the successor owns both live rows.** `drivers` = `acceptance-matrix.json` and
  `issue-matrix.json`, with the canonical names from `_MERGE_DRIVERS` (`filled-side` for
  acceptance, `row-aware` for the issue matrix). This is what makes the supersession safe for a
  project upgrading from before 3.2.6.
- **D-003: removal lives in the successor, not in the shared seeding helper.** The helper
  (`_merge_driver_seeding.py`) is used by every merge-driver migration; teaching it a retired
  row would split the truth across `detect()`, `apply()`, the `init` union and the
  architectural seed-superset guard. The successor overrides `detect()`/`apply()` instead.
- **D-004: remove the dead declaration.** `SEQUENCED_AFTER` declared
  `3.2.6_issue_matrix_driver_repoint → 3.2.6_gate_artifact_merge_drivers`; with the gate
  migration superseded it can never apply, so the declaration can never fire. The mapping goes,
  and the dry-run modules' prediction proofs are re-anchored on a synthetic pair of the same
  shape (they pin the mechanism, not the historical ids).
- **D-005: `target_version = 4.0.0rc8`.** The installed package is 4.0.0rc8 and the runner
  refuses migrations above it; the successor must run after `3.2.6_issue_matrix_driver_repoint`
  (3.2.6rc1), which the version slot guarantees.
- **D-006: removal is line-exact.** Drop lines whose stripped text equals the retired entry;
  never rewrite or re-sort the rest of the file, and never collapse blank lines.

## Phase 2 — Test strategy

| Story | Test | Red on `origin/main`? |
|---|---|---|
| US1 no-op upgrade | `tests/upgrade/test_issue_matrix_md_row_retirement_7217.py` (CLI, committed project) | yes — the row is appended |
| US1 idempotence | second upgrade in the same test / successor `detect()` unit | yes (same cause) |
| US2 healing | seeded-row project, upgrade, line-level diff | yes — the row survives |
| US3 no driver loss | same fixtures: both rows present, both `git config --local` entries | no — ratchet (guards the retirement) |
| FR-004 init seed | `tests/init/test_init_then_upgrade_is_noop.py` inverted assertion | yes — `init` writes the row today |
| FR-006 supersession | `tests/specify_cli/upgrade/test_gitignore_backfills_superseded_6589.py` table | yes (table equality) |

## Risks & Mitigations

- **Losing the acceptance-matrix half** → FR-002/SC-002 assert both rows and both configs after
  an upgrade from a project with no gate-artifact state; the test also asserts the historical
  migration did not run (`3.2.6_gate_artifact_merge_drivers` records `skipped`).
- **Re-adding the row through another surface** (init seed, a future seeding migration) → the
  architectural guard plus the inverted `init` test; the init union drops the line only because
  the superseded module is no longer a live seeding migration, so the mechanism is not special
  cased.
- **Dry-run and CLI witness modules lost their real pair** → re-anchored on a synthetic pair of
  the same shape; every assertion is preserved (D-004).
- **Manifest/order gate** → the successor is inserted in its version slot with a `# tie:` note
  and `tests/architectural/test_migration_order_manifest.py` stays green.
