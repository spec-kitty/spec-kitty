# Implementation Plan: Repair historical sweep-created mission overrides

**Branch**: `repair-historical-sweep-mission-overrides-01M68ZHQ` | **Date**: 2026-10-31 | **Spec**: [`spec.md`](./spec.md)
**Input**: Mission specification from `kitty-specs/repair-historical-sweep-mission-overrides-01M68ZHQ/spec.md`

## Summary

An older build's `2.0.6_consistency_sweep` moved package-shipped mission files into
`.kittify/overrides/missions/<type>/…`, where they outrank the shipped copy at resolution tier 1.
The classifier that produced that move is fixed, and #5280 repaired 15 named
documentation/research template forks, but a **historical** override for any other mission (or any
other shipped mission file) is still there, and `2.0.7_fix_stale_overrides` — the migration that
exists to clean this class up — cannot see it: it joins a second `missions/` segment onto an asset
root that already ends in `missions/`, so it finds no shipped counterpart and reports
"not needed". That migration is a frozen shipped body (DIRECTIVE_044), so the repair must be a new
migration.

The mission delivers that new migration plus the one path-mapping helper both it and
`runtime/migrate.py` must share, so the join that caused #6548 cannot be written a third time:

- One public helper, `shipped_mission_counterpart(rel, package_root)` in `runtime/migrate.py`,
  maps a `.kittify/`-relative (or `.kittify/overrides/`-relative) `missions/<type>/<rest>` onto
  `<package missions root>/<type>/<rest>`. `_find_package_counterpart` delegates to it; the new
  migration resolves every override through it.
- New migration `4.0.0rc8_repair_historical_sweep_overrides` scans only
  `.kittify/overrides/missions/**`. A file whose bytes are proven identical to its shipped
  counterpart is removed through `guard_destructive_removal` (the guard performs the removal; the
  module carries no raw destructive literal). A file that differs cannot be proven package-owned
  (#4961), so it is preserved byte-for-byte and named in the upgrade's warnings. A file with no
  shipped counterpart is never read.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: stdlib only (`pathlib`, `filecmp`-free exact byte compare via
`CanonicalContentProver`); `specify_cli.asset_preservation` (the ownership guard),
`specify_cli.runtime.home.get_package_asset_root`, `specify_cli.upgrade.registry.MigrationRegistry`
**Storage**: filesystem — project `.kittify/overrides/missions/**`, package missions root
**Testing**: pytest; fast-tier unit tests beside the existing migration tests, one integration
test driving the real `spec-kitty upgrade` CLI
**Target Platform**: CLI (Linux/macOS/Windows)
**Project Type**: single project (Python CLI)
**Performance Goals**: the scan is O(files under `.kittify/overrides/missions/**`); no history
walk, no network
**Constraints**: no shipped migration body may change (DIRECTIVE_044); no resolver tier change;
removal only on proven byte identity (#4961)
**Scale/Scope**: one new migration module (~150 lines), one helper extraction (~20 lines), one
architectural pin entry, one manifest line, one changelog entry, one docs note

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | How this plan satisfies it |
|---|---|
| Single canonical authority (DIRECTIVE_044) | The path mapping lives once, in `runtime/migrate.py`, and both call sites import it. The repair is a new migration id; `2.0.7_fix_stale_overrides` stays byte-identical. |
| Ownership guard, prove-or-preserve (charter L463–479, #4961) | Every removal goes through `guard_destructive_removal` with a canonical-bytes prover; differing bytes are preserved and named, never deleted. |
| ATDD-first / red-first (DIRECTIVE_034) | The first test drives the real `spec-kitty upgrade` CLI on the reproduced project shape and asserts the repair; it fails on the baseline (witnessed: both overrides survive) and passes only with the new migration. |
| Locality of change (DIRECTIVE_024) | Touches `runtime/migrate.py` (mapping extraction only), one new migration module, its manifest line, its tests, the architectural routed-module pin, changelog, and one docs note. |
| No full heavy suites in a mission (NO_FULL_HEAVY_SUITES_IN_MISSION) | Targeted module tests + `make test-fast`; CI owns the rest. |
| Pre-existing failure reporting | Any red on the base is classified against `origin/main` and cited, never masked. |

## Project Structure

### Documentation (this mission)

```
kitty-specs/repair-historical-sweep-mission-overrides-01M68ZHQ/
├── spec.md              # written
├── plan.md              # this file
├── tasks.md             # /spec-kitty.tasks output
├── traces/              # approach / design-decisions / tooling-friction tracers
├── decisions/           # decision-moment records
└── tasks/WP0N-*/        # per-work-package prompt + baseline evidence
```

### Source Code (repository root)

```
src/specify_cli/
├── runtime/migrate.py                                   # + shipped_mission_counterpart(); _find_package_counterpart delegates
└── upgrade/migrations/
    ├── order_manifest.txt                               # + one entry (tie: shares 4.0.0rc8)
    └── m_4_0_0rc8_repair_historical_sweep_overrides.py  # NEW — the repair

tests/
├── upgrade/test_migrate_integration.py                  # + helper + classifier-routing tests
├── upgrade/migrations/test_m_4_0_0rc8_repair_historical_sweep_overrides.py   # NEW — unit + CLI-level
└── architectural/test_mutation_ownership_routing.py     # + pin the new routed module
```

**Structure Decision**: single project; the migration sits beside
`m_4_0_0rc8_retire_stale_mission_template_forks.py` (its sibling repair) and the tests mirror the
existing `tests/upgrade/…` layout.

## Design Decisions

1. **A new migration id, not an edit to `2.0.7`.** DIRECTIVE_044 freezes shipped bodies and the
   ledger's drift audit exists to make an edit visible. `2.0.7` also cannot be re-run on a project
   that already settled it, whereas a new id is selected by ledger-diff on the next upgrade.
2. **Preserve-and-name for differing bytes, never a move-back.** The issue offers "move the
   override back to `.kittify/missions/`" or "name it for the operator". Moving a differing file
   into the legacy tree would rewrite operator bytes under a name tier 4 reads, which is an
   unproven-ownership mutation; #4961 rules that out. Preserve + name is the guard-conformant
   option, and the warning tells the operator exactly what to delete.
3. **Exact byte identity, no CRLF folding.** The classifier (`filecmp`, `classify_asset`) and
   `2.0.7` compare exact bytes; a CRLF working-tree copy of a shipped LF file is therefore
   `differs`, so it is preserved and named rather than deleted. Folding line endings would delete
   bytes the guard's prover cannot prove and would diverge from the classifier two lines away.
   The fork-repair migration folds CRLF for a different question (is this a *known shipped fork*?);
   this one asks "is this *this exact* shipped file?", so exact bytes is the honest comparison.
4. **The scan refuses symlinks and never removes directories.** A symlinked `.kittify`,
   `overrides` or `missions` component, or a symlinked override file, is named and skipped: the
   repair must not read or delete anything outside the project. Emptied directories stay (the
   sibling #5280 repair also creates and removes no directory), so nothing the resolver reads
   changes shape.
5. **`detect()` is true for a removable or an unprovable candidate.** The unproven ones must be
   *named*, and a not-needed step prints nothing. Because a successful `apply()` records the
   migration as settled, the naming happens once per project, not on every upgrade.
6. **The helper takes `rel`, not a mission name.** Both trees are `<tree>/missions/<type>/<rest>`,
   so one mapping serves the classifier and the repair; the mission comes from the path, which is
   also the bug `execute_migration`'s fixed `mission="software-dev"` default carried.

## Implementation Concern Map

### IC-01 — One path mapping for "which shipped file is this?"

- **Purpose**: Extract the `missions/<type>/<rest>` → package mapping into a public helper so the
  classifier and the repair cannot drift into two different joins again.
- **Relevant requirements**: FR-003, C-003
- **Affected surfaces**: `src/specify_cli/runtime/migrate.py`
  (`shipped_mission_counterpart`, `_find_package_counterpart`), `tests/upgrade/test_migrate_integration.py`
- **Sequencing/depends-on**: none (must land before IC-02 uses it)
- **Risks**: the classifier's behaviour must not change for any existing layout — the flat
  `templates/` / `command-templates/` / `scripts/` joins stay exactly as they are, and the existing
  #6548 regression test stays green.

### IC-02 — The repair migration

- **Purpose**: Remove historical overrides proven identical to the shipped file, preserve and name
  the rest, on the current baseline, without touching a shipped migration body.
- **Relevant requirements**: FR-001, FR-002, FR-004, FR-005, FR-006, FR-007, FR-008, NFR-001–003,
  C-001, C-002, C-004
- **Affected surfaces**:
  `src/specify_cli/upgrade/migrations/m_4_0_0rc8_repair_historical_sweep_overrides.py` (new),
  `src/specify_cli/upgrade/migrations/order_manifest.txt`,
  `tests/upgrade/migrations/test_m_4_0_0rc8_repair_historical_sweep_overrides.py` (new),
  `tests/architectural/test_mutation_ownership_routing.py` (routed-module pin)
- **Sequencing/depends-on**: IC-01
- **Risks**: the architectural ownership-routing gate pins every module that calls the guard, so
  the new module must be added to `_ROUTED_MODULES` in the same change; the module must carry no
  raw `unlink`/`rmtree`/`rmdir`. The CLI-level test must stay inside the 30-second budget.

### IC-03 — Operator-facing documentation

- **Purpose**: Tell an operator, in the changelog's upgrade notes, what the new upgrade step does,
  what it preserves, and what to do with a named override.
- **Relevant requirements**: FR-002 (the naming has to be actionable), FR-006
- **Affected surfaces**: `docs/changelog/CHANGELOG.md` (`[Unreleased]` → Upgrade Notes). No new
  `docs/migrations/` page: the sibling #5280 repair shipped one changelog note and no page, and
  `docs/migrations/index.md` lists runbook-shaped migrations, not single upgrade steps.
- **Sequencing/depends-on**: IC-02 (the behaviour and the warning text must exist to document)
- **Risks**: the docs-freshness gate; keep the entry under 1,200 characters with the bold
  impact-first lead and the `(#6548)` reference.

## Complexity Tracking

No charter violations. One extraction (IC-01) exists solely to satisfy the single-authority rule;
the alternative (a second copy of the join in the new migration) is exactly the drift this issue
reports.

## Verification Strategy

1. **Red first (production path)**: build a project at `4.0.0rc8` carrying a byte-identical and a
   differing `software-dev` template override, run the real `spec-kitty upgrade`, assert the repair.
   Red on the baseline — witnessed by hand on `dfe9efb0e8`: both files survive, both resolve
   `OVERRIDE`.
2. **Half-by-half**: revert the helper extraction and confirm the classifier-routing test still
   passes but the migration fails to import (the migration depends on the helper alone); revert the
   migration's manifest entry and confirm the CLI test goes red (the step is not selected).
3. **Positive controls on the same fixture**: the kept differing file proves the scan is not a
   blanket delete; the removed identical file proves the scan can see candidates at all.
4. **Gates**: new unit file, `tests/upgrade/test_migrate_integration.py`,
   `tests/upgrade/migrations/test_m_2_0_7_fix_stale_overrides.py`,
   `tests/architectural/test_mutation_ownership_routing.py`,
   `tests/architectural/test_migration_order_manifest.py`,
   `tests/upgrade/test_order_manifest.py`, `make test-fast`, `ruff check`/`ruff format --check`,
   `python -m scripts.docs.check_docs_freshness --ci`.
