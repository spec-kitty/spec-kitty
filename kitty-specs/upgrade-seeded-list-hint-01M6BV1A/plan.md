# Implementation Plan: The upgrade hint recognises an activation list a released preset wrote

**Branch**: `issue-6684-upgrade-seeded-list-hint` | **Date**: 2026-11-01 | **Spec**: `kitty-specs/upgrade-seeded-list-hint-01M6BV1A/spec.md`
**Input**: Mission specification from `kitty-specs/upgrade-seeded-list-hint-01M6BV1A/spec.md`

## Summary

`4.0.0rc8_promote_interview_selections` warns about a machine-written activation list by comparing it
with **today's** full in-force set. A list an earlier CLI wrote from a *released* `default` activation
preset is smaller than today's set (19 directives instead of 38), so it gets no hint at all. The fix
widens the provenance test in `_seeded_list_hints` to the released preset lists that are already frozen
in-tree (`_charter_pack_cutover_snapshots.DEFAULT_SNAPSHOTS`, the same comparand
`_charter_pack_cutover_resets` uses) and gives that provenance its own honest warning text. Nothing is
written, narrowed or reset: the operator ruling on #6684 (option (b)) refuses a reset migration, and the
warning remains the whole upgrade-side remedy. The decision is recorded as an ADR amendment plus a
changelog entry so it does not live only in this diff.

## Technical Context

**Language/Version**: Python 3.11 (project floor; `from __future__ import annotations` in the touched module)
**Primary Dependencies**: ruamel.yaml (activation surface round-trip), `charter.activation.api` (`SelectionResolver`, `resolve_effective_sets`, `resolve_activation_write_target`), `_charter_pack_cutover_snapshots` (frozen released preset lists)
**Storage**: read-only here — `.kittify/charter/activation.yaml` (or the legacy `charter.yaml`/`config.yaml` before the ledger move) is read; the hint writes nothing
**Testing**: pytest, unit/fast, driven directly through `PromoteInterviewSelectionsMigration.detect`/`.apply` on synthetic projects built from real built-in ids (the existing module's pattern)
**Target Platform**: Linux/macOS/Windows developer workstations and CI — pure data comparison, no platform surface
**Project Type**: single Python package (`src/specify_cli/upgrade/migrations`), with an architectural-test suite
**Performance Goals**: unchanged for the common case (no candidate kinds ⇒ no doctrine service built); when candidates exist the effective-set resolution already happens today, so the added work is a handful of set operations over frozen literals
**Constraints**: warn-only; no new frozen data file; the frozen preset lists stay owned by `_charter_pack_cutover_snapshots`; `DEFAULT_SNAPSHOTS` must not gain a second copy elsewhere
**Scale/Scope**: one migration module, one test module, one ADR amendment, one changelog entry

## Charter Check

*GATE: passed before Phase 0; re-checked after Phase 1.*

- **Single canonical authority** — the released preset lists stay owned by
  `_charter_pack_cutover_snapshots.DEFAULT_SNAPSHOTS`; the hint reads it, nothing re-freezes or re-shapes it
  (C-001). The hint still resolves "in force" only through `charter.activation.api.resolve_effective_sets`.
- **ATDD-first / DIRECTIVE_034** — the red test drives the **pre-existing** entry point
  (`PromoteInterviewSelectionsMigration.apply`) on a project whose list is set-equal to a released
  `default` preset list, and asserts the hint the issue asks for; it fails on `main` because `main`
  compares only with today's set.
- **Locality of change (DIRECTIVE_024)** — one helper (`_seeded_list_hints`) gains the second provenance;
  the promotion, resolution and write paths are untouched.
- **`NO_FULL_HEAVY_SUITES_IN_MISSION`** — targeted suites only: the migration's own test module, plus the
  cutover-snapshot test that guards the frozen data it now reads.
- **Campps cleaning / DIRECTIVE_025** — the module docstring states the two provenances and the residual
  (a whole-catalogue seed after the catalogue grows) so the next maintainer does not re-derive it.
- **DIRECTIVE_044 / no shipped-migration edits** — `4.0.0rc8_*` is the *current* unreleased candidate
  step and is the file the issue names; the superseded `unify_charter_activation_promote_answers` is not
  touched.
- **Adversarial review discipline** — the diff is small but user-visible (a warning operators read) and
  touches a migration the fleet runs on every upgrade, so it gets an independent review pass over the
  integrated diff rather than a self-approval.

## Project Structure

### Documentation (this mission)

```
kitty-specs/upgrade-seeded-list-hint-01M6BV1A/
├── spec.md
├── plan.md
├── tasks.md
├── tasks/
│   ├── WP01-released-preset-hint.md
│   └── WP02-decision-record.md
└── traces/            # approach.md, design-decisions.md, tooling-friction.md
```

### Source code (repository root)

```
src/specify_cli/upgrade/migrations/
├── m_4_0_0rc8_promote_interview_selections.py   # MODIFIED: _seeded_list_hints gains the released-preset provenance
├── _charter_pack_cutover_snapshots.py           # READ ONLY: DEFAULT_SNAPSHOTS is the frozen comparand
tests/upgrade/migrations/
└── test_m_4_0_0rc8_promote_interview_selections.py  # MODIFIED: red-first hint cases
docs/adr/4.x/2026-10-19-1-activation-ledger-persists-deactivation.md   # MODIFIED: amendment for #6684
docs/changelog/CHANGELOG.md                      # MODIFIED: [Unreleased] entry
```

## Phase 0 — Research (already answered)

- **Which lists could an earlier build have written?** The superseded
  `unify_charter_activation_promote_answers` seeded an absent key from
  `charter.default_pack.load_default_pack_activation_ids`, i.e. the **released** `default.yaml` of the
  CLI that ran the upgrade (3.2.6rc1 → the #4400 effective-set rewrite). Later versions seeded the whole
  in-force set. Both shapes are therefore covered by (a) today's in-force equality, which exists, and
  (b) released preset equality, which this mission adds.
- **Do we need new frozen data?** No. `_charter_pack_cutover_snapshots.DEFAULT_SNAPSHOTS` already holds
  every distinct released `default.yaml` list per key (174 PyPI releases, sha256-verified, with
  provenance in the module docstring).
- **Is the residual (whole-catalogue seed, catalogue later grows) reachable today?** No: the built-in
  catalogue at 4.0.0rc6/4.0.0rc7 (the effective-set seeding era) is identical to today's for every kind
  (38 directives, 14 paradigms, 121 tactics, 25 styleguides, 23 procedures, 18 toolguides, 26 agent
  profiles). It is recorded in the ADR as the condition to watch, with the follow-up shape named.
- **Why not a reset?** Operator ruling, option (b), 2026-10-26: a reset would silently undo a deliberate
  activate-all (#6499) and no provenance is recorded to tell the two apart (the ledger's L1 validation
  refuses a provenance key, and it cannot be backfilled).

## Phase 1 — Design

One function changes shape:

```
_seeded_list_hints(project_path, present, selections, resolver) -> list[str]
    candidates  = kinds where len(listed) > len(selected)          (unchanged)
    in_force[]  = resolve_effective_sets(project_path, candidates) (unchanged, lazy)
    for each kind:
        today_hint      : listed == in_force(kind)                      -> existing message
        preset_hint     : exists D in DEFAULT_SNAPSHOTS[key] with
                          D <= listed <= in_force(kind)
                          and listed <= (D | selected)                  -> new message
                          (i.e. the released preset, plus at most the interview's own ids)
        emit at most one hint per kind, today's taking precedence
```

Design decisions:

- **D-1: the preset hint is a superset test, not set-equality.** The superseded seeding promoted the
  interview's ids onto the preset list, so a seeded list can be the preset ∪ selected. `D ⊆ listed` plus
  `listed ⊆ (D ∪ selected)` accepts both the bare preset shape and that one, and rejects a hand-picked
  list that merely happens to overlap.
- **D-2: still bounded by today's in-force set.** A list naming a retired id is not "in force"; without
  the bound the hint could tell an operator to narrow a list whose real problem is a dead id.
- **D-3: one warning per kind, today's provenance first.** Two hints for one key would double the noise
  and say the same thing twice; the today's-set case is the stronger claim.
- **D-4: no write path is added.** `_SEEDED_LIST_HINT` and its new sibling are formatted strings only;
  `apply` returns `MigrationResult(warnings=...)` exactly as now.
- **D-5: identity space.** Both sides are stems (`resolver.stems`), so a list spelled by declared id
  (`DIRECTIVE_003`) is not a false miss.

## Phase 2 — Implementation strategy

1. Red: add the released-preset cases to
   `tests/upgrade/migrations/test_m_4_0_0rc8_promote_interview_selections.py` (bare preset list, preset +
   interview id, hand-picked list that must stay silent, byte-identical surface assertion). Run them; they
   fail on `main`'s behaviour.
2. Green: add the second provenance to `_seeded_list_hints` and its message; keep both messages naming
   `charter interview --narrow-activation` and `charter activate <kind> <id> --only`.
3. Record: ADR amendment (`## Amendment 2026-11-01 (#6684)`), changelog entry, module docstring.
4. Trap: the existing today's-in-force tests must stay green unchanged — the new check must not shadow or
   weaken them.

## Risks

- **False positive:** an operator who deliberately activated exactly a released preset. Mitigation: the
  warning is informational, says which provenance it believes, and names the narrowing commands; the
  ruling accepts warn-only noise over a silent block.
- **Frozen-data drift:** if `DEFAULT_SNAPSHOTS` is regenerated, the hint follows it automatically (it reads
  the module, not a copy). The cutover-snapshot test guards its shape.
- **Reading a private-looking snapshot from another migration:** `_charter_pack_cutover_resets` already
  does exactly this, so the direction is established; no new import cycle (both are migrations, and the
  snapshot module imports only `charter.drg`).
