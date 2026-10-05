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
