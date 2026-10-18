---
title: 'ADR: IGNORED-Surface Backfill Migration Pattern'
description: 'Every new `GitClass.IGNORED` surface ships a frozen companion gitignore backfill migration in the same pull request, covering entry variants and lane worktrees.'
status: Accepted
date: '2026-07-07'
---

## Context

When a new `IGNORED` `StateSurface` is added to `src/specify_cli/state/contract.py`,
fresh `spec-kitty init` immediately covers new projects via
`GitignoreManager.protect_all_agents()` — which derives its runtime entries
from `get_runtime_gitignore_entries()` at module load.  But **existing projects
never receive the entry** until they run `spec-kitty upgrade`; those projects
continue to commit machine-local artefacts until the next upgrade.

Three separate incidents exposed this gap before this ADR was written:

| Issue | Surface added | PR adding surface | PR adding backfill |
|-------|--------------|-------------------|--------------------|
| #2369 | `.kittify/encoding-provenance/` | unknown | #2370 |
| #2384 | `.kittify/migrations/`, `.kittify/logs/` | #2384 | #2388 |
| #2412 | `.agents/skills/<skill_name>/`, `.kittify/skills-manifest.json` | #2412 | #2423 |

Each time, the defect was discovered independently, and an ad-hoc backfill
migration was authored to remedy existing projects.  The three migrations are
structurally identical: detect the missing entries, add them, record the
migration so repeat runs skip it.  Without a standing pattern the same mistake
will recur on the fourth new surface.

### Why not a live-contract migration?

An alternative would be a single "live contract" migration that always checks
whether every current `IGNORED` surface is present in `.gitignore` and adds
missing entries.  This approach was considered and rejected:

1. **Non-determinism under concurrent development**: a live migration re-runs
   whenever any new surface is added, making the migration's behaviour
   change retroactively for projects that already ran it.  Upgrade runners
   record migrations by `migration_id`; a live migration would be recorded once
   and never re-fire, creating silent coverage gaps as new surfaces land.
2. **Hard-to-audit change sets**: a migration that adds N entries in a single
   apply() call makes it impossible to attribute which surface caused which
   gitignore entry to appear, complicating reversal or review.
3. **Regression risk for `runs_on_worktrees`**: worktree-scoped upgrade runs
   replay migrations flagged `runs_on_worktrees=True`.  A live migration would
   need its own idempotency logic to avoid re-running on every worktree upgrade
   as the surface list grows.
4. **Frozen migrations are the established pattern**: every other migration in
   `src/specify_cli/upgrade/migrations/` is frozen — it detects a concrete
   historical gap and closes it once.  Introducing a live migration would be
   the only dynamic one in the registry, requiring special-case handling.

## Decision

**One frozen backfill migration per IGNORED-surface addition** is the standing
pattern.  Whenever a new `GitClass.IGNORED` surface is added to the state
contract and its gitignore entry is not already guaranteed by an existing
migration, a companion migration MUST be authored in the same PR.

The migration:

1. Has a `migration_id` of the form `"X.Y.Z_<slug>_gitignore_backfill"`.
2. Declares `target_version` that matches the release that introduces the surface.
3. Does NOT override `runs_on_worktrees`; inherits the `True` default so lane
   worktrees receive the same gitignore protection on upgrade.
4. Implements `_EQUIVALENT_ENTRIES` covering all reasonable variant forms of
   the entry (trailing-slash, no-slash, parent-directory wholesale) for
   idempotency against hand-edited gitignores.
5. Uses `GitignoreManager` for the write so section headers are consistent.
6. Registers automatically via `auto_discover_migrations()` — no manual
   `MIGRATIONS` list edit required.

The companion ADR (this document) is not required for every backfill — it is
the single reference that all future backfills cite in their docstrings or PR
descriptions.

## Consequences

- Authors receive a clear checklist (see below) instead of rediscovering the
  pattern.
- The three existing backfill migrations
  (`m_3_2_3_encoding_provenance_gitignore_backfill`, `m_3_2_4_runtime_dirs_gitignore_backfill`,
  `m_3_2_5_agents_skills_gitignore_backfill`) are the reference implementations.
- A live migration or a blanket "always re-sync everything" approach remains
  explicitly out of scope.
- Any future work that introduces a second mutable class of surfaces (e.g.,
  surfaces that should always be tracked) should author its own ADR rather
  than extending this one.

## Author Checklist

When adding a `GitClass.IGNORED` surface to `state/contract.py`:

- [ ] **Contract**: add `StateSurface` with `git_class=GitClass.IGNORED` in
  `src/specify_cli/state/contract.py`.  Include a `notes` field that
  cross-references any visually similar TRACKED surfaces to prevent naming
  confusion.
- [ ] **Init coverage**: confirm `get_runtime_gitignore_entries()` emits the
  new entry.  The test
  `tests/specify_cli/test_gitignore_contract.py::test_contract_runtime_entries_include_skill_projection_surfaces`
  shows the assertion pattern.
- [ ] **Manager test**: add a `test_gitignore_manager_protects_<surface>` test
  that calls `GitignoreManager(tmp_path).protect_all_agents()` and asserts
  the surface path is git-ignored.
- [ ] **Backfill migration**: create
  `src/specify_cli/upgrade/migrations/m_<X_Y_Z>_<slug>_gitignore_backfill.py`
  following the structure of `m_3_2_5_agents_skills_gitignore_backfill.py`.
  Include `_EQUIVALENT_ENTRIES` for idempotency.  Do NOT override
  `runs_on_worktrees` — the `True` default is correct.
- [ ] **Migration tests**: cover `apply()`, `detect()`, equivalence variants,
  idempotency, dry-run, end-to-end via `MigrationRunner`, and the worktree
  composition path (`include_worktrees=True`).
- [ ] **Order-manifest entry** (ledger model, ADR
  [`2026-10-17-1`](../4.x/2026-10-17-1-explicit-migration-ledger.md)): add the
  `migration_id` to `src/specify_cli/upgrade/migrations/order_manifest.txt` in
  execution order — the single ordering authority. Annotate an intentional
  equal-`target_version` run with a trailing `# tie: <reason>`. The build-time
  gate `tests/architectural/test_migration_order_manifest.py` requires every
  registered migration to appear in the manifest exactly once. Selection is now
  **ledger-diff**, not the version window, so a migration is reconsidered until
  it records `success` in its ledger partition — `detect()` stays the
  idempotency guard, never the selection authority.
- [ ] **Ledger routing** (ledger model, ADR
  [`2026-10-17-1`](../4.x/2026-10-17-1-explicit-migration-ledger.md)): a gitignore
  backfill lands in the TRACKED `.gitignore`, so keep the `clone_local_effect`
  ClassVar at its `False` default — its applied record goes to the tracked
  `.kittify/migration-ledger.jsonl` and correctly propagates to every clone.
  ONLY a migration whose effect lives outside version control
  (`.git/info/exclude`, `git config --local`, `.git/hooks`) sets
  `clone_local_effect = True`, routing its record to the per-clone
  `.kittify/migrations/clone-local.jsonl`. Optionally declare `identity` (a
  stable drift key) / `content_hash_sources` (multi-file hash input); drift is
  audit-only. `spec-kitty migrate ledger` reports what ran.
- [ ] **Ratchet baseline**: (superseded 2026-09, mission
  ratchet-baseline-census-gate-remediation-01M3EW3Z: the `category_1` baseline
  leaf was retired; adding the migration to `_CATEGORY_1_AUTO_DISCOVERED_MIGRATIONS`
  is sufficient)
- [ ] **Dead-module allowlist**: add the new migration to the allowlist in
  `tests/architectural/test_no_dead_modules.py`.
- [ ] **Repo .gitignore**: add the entry to the repo root `.gitignore` under the
  `# Project specific` or `# Added by Spec Kitty CLI (auto-managed)` section
  so the repo itself does not accumulate the surface.

## References

- `src/specify_cli/state/contract.py` — `GitClass`, `StateSurface`,
  `get_runtime_gitignore_entries()`
- `src/specify_cli/gitignore_manager.py` — `RUNTIME_PROTECTED_ENTRIES`,
  `GitignoreManager.protect_all_agents()`
- Reference implementations:
  - [`src/specify_cli/upgrade/migrations/m_3_2_3_encoding_provenance_gitignore_backfill.py`](../../../src/specify_cli/upgrade/migrations/m_3_2_3_encoding_provenance_gitignore_backfill.py)
  - [`src/specify_cli/upgrade/migrations/m_3_2_4_runtime_dirs_gitignore_backfill.py`](../../../src/specify_cli/upgrade/migrations/m_3_2_4_runtime_dirs_gitignore_backfill.py)
  - [`src/specify_cli/upgrade/migrations/m_3_2_5_agents_skills_gitignore_backfill.py`](../../../src/specify_cli/upgrade/migrations/m_3_2_5_agents_skills_gitignore_backfill.py)
- Contract tests:
  [`tests/specify_cli/test_gitignore_contract.py`](../../../tests/specify_cli/test_gitignore_contract.py)
- Migration tests:
  [`tests/specify_cli/upgrade/migrations/test_m_3_2_5_agents_skills_gitignore.py`](../../../tests/specify_cli/upgrade/migrations/test_m_3_2_5_agents_skills_gitignore.py)
- PR #2370 (provenance backfill), PR #2388 (runtime-dirs backfill),
  PR #2423 (agents-skills backfill — defect-class trigger for this ADR)

## Amendment 2026-10-04 (#5457)

**Decision item 3 no longer reaches integrating worktrees.** Item 3 said the migration inherits `runs_on_worktrees=True` "so lane worktrees receive the same gitignore protection on upgrade". Since [ADR 2026-10-04-4](../4.x/2026-10-04-4-upgrade-writes-project-global-state-once.md), `spec-kitty upgrade` skips an integrating worktree: a worktree whose branch is a `kitty/mission-…` mission, lane or coordination branch, or whose branch cannot be read (`_is_integrating_worktree`, `_worktrees_to_upgrade` in `src/specify_cli/upgrade/runner.py`). The `True` default therefore still applies to worktrees that upgrade does visit (a worktree on any other branch), and the migration is still correct to inherit it.

Lanes receive the gitignore protection through integration instead: the repository root checkout carries the backfilled `.gitignore`, and a lane picks it up when it next merges the Mission branch.

**Residual window.** Between the upgrade and that merge, an integrating worktree keeps its pre-upgrade `.gitignore` (and `.gitattributes`). A new `IGNORED` surface that the backfill covers can be untracked-visible in that worktree until the lane integrates. The original decision text above is unchanged.

## Amendment 2026-10-17 (#6233) — the "recorded-once, frozen" choice assumes a TRACKED effect

The frozen-migration decision above records a migration by `migration_id` and skips it on every later run (the runner short-circuits at `metadata.has_migration(id)` before it ever calls `detect()`). That is sound **only because a gitignore backfill lands in the TRACKED `.gitignore`**: the effect travels with the commit, so the shared, pushed `metadata.yaml` ledger is a faithful record of the effect's presence on every clone.

For a migration whose effect lives **outside version control** — clone-local state such as `.git/info/exclude`, `git config --local`, or `.git/hooks` — the ledger is **not** authoritative. It records one clone's untracked state yet propagates to every clone, so a pulled clone whose own `detect()` reports the effect absent would skip the migration forever and never gain the local effect.

The fix tags such migrations `clone_local_effect = True` (`BaseMigration`, default `False`) and routes the skip decision to **this checkout's own `detect()`** at **two** layers — both are required, because the ledger is consulted at two distinct points:

1. **Selection** (`MigrationRegistry.get_applicable`): the version window selects only in-window migrations (`from_v < target <= to_v`) or a `target == from_v` migration whose `detect()` is True. On a pulled clone fully stamped at the current version (`from_v == to_v == current`), a clone-local migration whose `target` is **below** the current version would never be selected — so the skip-gate route below would never be reached for it. A sub-current (`target < from_v`) branch now pulls a `clone_local_effect` migration back into the applicable set when the shared ledger **records it applied** yet `detect()` reports the effect absent. Keying on the ledger record targets exactly the pulled-clone case: the ledger is tracked and pushed, so a pulled clone carries the record without the clone-local effect. A migration the ledger never recorded keeps the version-window authority (its version stamp is past it) and is not re-selected, so a project that genuinely never ran it is left to the version window — this preserves the no-migrations no-op contract. These migrations are not `runs_first`, so they keep normal version order. The detector preview delegates to `get_applicable`, so `--dry-run` reports them in parity.
2. **Skip gate** (`runner._apply_migration`): a selected migration recorded in the ledger is normally skipped before `detect()` runs; `reselect_when_recorded()` overrides that for a clone-local migration whose effect is absent. This gate is itself reached only for a recorded migration (`has_migration`), which is why the selection branch keys on the same record.

Together: a recorded clone-local migration re-applies whenever its effect is absent on this checkout, and settles once `detect()` reports it present. A TRACKED-effect migration (the backfills this ADR governs included) keeps the default `False` and is excluded at **both** layers — the sub-current selection branch skips it and the skip gate trusts the ledger — so it stays recorded-once-and-skipped. Reselection requires an idempotent `apply()`; the `tests/upgrade/test_clone_local_migration_idempotent.py` gate pins the clone-local member set and its idempotency.

This is a per-clone reselection seam, not the explicit, machine-readable clone-local ledger that would record the effect's presence directly; that longer-term home is tracked by epic **#2933**.

> **Superseded 2026-10-17 (#5230 / epic #2933) — the explicit ledger has landed.** The per-clone reselection seam described in this amendment is retired. ADR [`2026-10-17-1`](../4.x/2026-10-17-1-explicit-migration-ledger.md) replaced `metadata.yaml.applied_migrations` and the version window with an explicit two-partition applied-migration ledger (tracked `.kittify/migration-ledger.jsonl` + per-clone `.kittify/migrations/clone-local.jsonl`). `clone_local_effect` is now the ledger's **routing key**, no longer a reselection trigger: the sub-window selection branch (`_clone_local_selected_below_window`) is removed and `reselect_when_recorded` collapses to a ledger lookup. Selection is **ledger-diff**; `detect()` remains only the runner's idempotency guard. See the Author Checklist above and ADR `2026-10-17-1`.
