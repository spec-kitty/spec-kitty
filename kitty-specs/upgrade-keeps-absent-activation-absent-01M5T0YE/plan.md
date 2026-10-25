# Implementation Plan: Upgrade keeps an absent activation key absent

**Branch**: `issue-6629-upgrade-seeded-activation-provenance` | **Date**: 2026-10-25 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/upgrade-keeps-absent-activation-absent-01M5T0YE/spec.md`

## Summary

`unify_charter_activation_promote_answers` (shipped at 3.2.6rc1) seeds an absent `activated_<kind>` key with the whole in-force set before it appends interview selections. On the #6629 shape this makes `charter synthesize` demand 38 companion tactics and skip the fresh-project seed. The plan has four parts:

- **Supersede the shipped migration** through `SUPERSEDED_MIGRATIONS`, with its module untouched.
- **Add a successor**, `4.0.0rc8_promote_interview_selections`, listed after `4.0.0rc8_activation_ledger`. It:
  - promotes answers-only ids into **present** lists only, through `resolve_activation_write_target` + `promote_activations`, so the deny guard and the activation ledger seam apply;
  - never materialises an absent key;
  - records `success` on its first run on a project with selections;
  - warns, without changing anything, when a present list looks seeded.
- **No changes to the readers.** Synthesis, the establishment probe and the activation ledger schema stay unchanged.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: ruamel.yaml, typer (existing)
**Storage**: `.kittify/charter/activation.yaml` (activation ledger), `.kittify/charter/interview/answers.yaml`, `.kittify/migration-ledger.jsonl`
**Testing**: pytest. A runner-driven integration test (end to end through `MigrationRunner` and `charter synthesize --dry-run --json`) plus focused unit tests of the successor.
**Target Platform**: the CLI on Linux, macOS and Windows
**Project Type**: single
**Performance Goals**: the in-force set is resolved at most once per run, and only for the seeded-list hint (NFR-002)
**Constraints**: DIRECTIVE_044 (no edit to a shipped migration); ADR 2026-10-17-1 (migration ledger, supersession amendment 2026-10-25); ADR 2026-10-19-1 (activation ledger: no new key, writes through the seam); #6499 (no silent activation change)
**Scale/Scope**: one new migration module, one supersession entry, one manifest line, test updates

## Charter Check

- **Single canonical authority:** the successor writes through the one write-target resolver and the one promotion primitive (`promote_activations`). It has no write path of its own. PASS.
- **Canonical sources / DIRECTIVE_044:** the shipped module stays byte-identical, and supersession uses the #6589 table. PASS.
- **ATDD / red-first:** `tests/specify_cli/upgrade/test_upgrade_keeps_absent_activation_6629.py` is red on main (it seeds a 38-entry directive list and a 14-entry paradigm list). It goes green with the fix. PASS.
- **Architectural gates:** `test_migration_order_manifest.py`, `test_deny_list_survives_upgrade.py` and `test_requires_git_repository_audit.py` are implicated and run targeted. PASS.
- **Terminology:** "activation ledger" vs "Migration Ledger" are named explicitly. PASS.

## Project Structure

### Documentation (this mission)

```
kitty-specs/upgrade-keeps-absent-activation-absent-01M5T0YE/
├── spec.md
├── plan.md
├── traces/              # tooling-friction, approach, design-decisions
├── decisions/
└── tasks.md             # /spec-kitty.tasks
```

### Source Code (repository root)

```
src/specify_cli/upgrade/
├── supersession.py                                   # + unify_charter_activation_promote_answers -> successor
└── migrations/
    ├── m_unify_charter_activation.py                 # UNCHANGED (shipped)
    ├── m_4_0_0rc8_promote_interview_selections.py    # NEW successor
    └── order_manifest.txt                            # + successor after 4.0.0rc8_activation_ledger (tie note)
tests/specify_cli/upgrade/
├── test_upgrade_keeps_absent_activation_6629.py      # end-to-end red-first reproduction
├── test_m_4_0_0rc8_promote_interview_selections.py   # NEW focused unit tests
└── test_unify_charter_activation_migration.py        # + registered substitute assertion
tests/architectural/test_deny_list_survives_upgrade.py  # old id -> ORDER_EXEMPT, successor -> BUILDERS
docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md  # amendment line for this supersession
docs/changelog/CHANGELOG.md                           # [Unreleased] Fixed entry
```

**Structure Decision**: one successor module beside the other rc8 migrations. It reuses `_compute_promotions`-style resolution through public charter seams (`resolve_selected_id_to_stem`, `resolve_offering_root`), not private helpers of the shipped module, so the superseded module can be retired later without breaking an import.

## Design

**Detection (`detect`)**: True when `answers.yaml` holds a non-empty `selected_<kind>` for any of the 8 promoted kinds. It reads only `answers.yaml`. Because `apply` then succeeds, the runner records `success` and the migration settles (FR-007, NFR-001).

**Apply**:
1. Load the answers. Resolve each id to a built-in stem (`resolve_selected_id_to_stem`). An unresolved id becomes a warning (FR-006).
2. `resolve_activation_write_target(project)` gives the authoritative surface: the activation ledger after `4.0.0rc8_activation_ledger`, or the legacy pointer/config target on a project that has no keys and therefore no ledger.
3. For each kind whose key is **present**, normalise the list entries to stems (identity space, #6423). The promotion is the resolved answer stems that are not in it. A kind whose key is **absent** is skipped (FR-001).
4. If any promotions exist, call `promote_activations(..., effective_sets={}, repo_root=project)`. Denied ids are skipped there (FR-006). Then `restamp_bundle_hash(project)` (FR-009).
5. Seeded-list hint (FR-008): for each present list whose stems are set-equal to the in-force set of that kind, while the answer stems are a strict subset, add a warning naming `charter interview --narrow-activation` and `charter activate <kind> <id> --only`. The in-force set is resolved once for the candidate kinds through `resolve_effective_sets(project, keys)`. Because a key is present, `resolve_effective_sets` is asked for what would be in force *if* the key were absent, which is the full set.
6. Dry run: report `would promote {key: ids}` and the warnings, and write nothing (FR-010).

**Supersession**: `SUPERSEDED_MIGRATIONS["unify_charter_activation_promote_answers"] = "4.0.0rc8_promote_interview_selections"`.

**Flags**: `target_version = "4.0.0rc8"`, `runs_on_worktrees = False`, `clone_local_effect = False`. `requires_git_repository` stays False: the architect probe found no `resolve_canonical_repo_root` call on this path, and the audit test is run to confirm.

## Complexity Tracking

No charter violations.

## Implementation Concern Map

### IC-01 — Successor promotion migration

- **Purpose**: promote interview selections into present lists through the activation ledger seam, never materialise an absent key, and settle after one run.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004, FR-006, FR-007, FR-008, FR-009, FR-010, NFR-001, NFR-002, NFR-003
- **Affected surfaces**: `src/specify_cli/upgrade/migrations/m_4_0_0rc8_promote_interview_selections.py`, `order_manifest.txt`, new unit tests, the end-to-end test
- **Sequencing/depends-on**: none
- **Risks**: the legacy-scope resolution inside `BaseMigration` (`legacy_upgrade_scope`) must still name the activation ledger on a migrated project (the architect confirmed `_one_mode` resolves LEDGER once the file exists).

### IC-02 — Supersede the shipped promotion and update its pins

- **Purpose**: register the shipped migration as a recorded no-op, and move the tests and gates that drove it to the successor.
- **Relevant requirements**: FR-005, C-001, C-006
- **Affected surfaces**: `supersession.py`, `tests/architectural/test_deny_list_survives_upgrade.py`, `tests/specify_cli/upgrade/test_unify_charter_activation_migration.py`, `tests/upgrade/test_consolidate_charter_bundle_migration.py` docstrings, the ADR amendment, the CHANGELOG
- **Sequencing/depends-on**: IC-01
- **Risks**: the fold's "relocates seed output" contract (MG6) becomes vacuous for this seed. Its docstring is updated and its assertions are kept.
