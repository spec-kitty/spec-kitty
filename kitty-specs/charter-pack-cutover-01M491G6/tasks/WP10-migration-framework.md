---
work_package_id: WP10
title: Migration framework — run-first ordering and neutralised migrations
dependencies:
- WP01
requirement_refs:
- FR-012
- C-008
planning_base_branch: issue-3732-charter-pack-rename
merge_target_branch: issue-3732-charter-pack-rename
branch_strategy: Planning artifacts for this mission were generated on issue-3732-charter-pack-rename. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-3732-charter-pack-rename unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-pack-cutover-01M491G6
base_commit: c13d9c3e7cb03eb4452cc1d73ceba0f9fbf3de94
created_at: '2026-10-07T00:02:30.800411+00:00'
subtasks:
- T050
- T051
- T052
- T053
- T054
phase: Phase 3 - Upgrade migration
history:
- at: '2026-10-06T19:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/upgrade/registry.py
create_intent:
- tests/specify_cli/upgrade/test_registry_runs_first.py
- tests/specify_cli/upgrade/test_neutralised_migrations.py
- tests/specify_cli/upgrade/test_migration_discovery_without_retired_modules.py
execution_mode: code_change
owned_files:
- src/specify_cli/upgrade/migrations/base.py
- src/specify_cli/upgrade/registry.py
- src/specify_cli/upgrade/runner.py
- src/specify_cli/upgrade/migrations/m_3_2_0rc35_default_charter_pack.py
- src/specify_cli/upgrade/migrations/m_3_2_x_normalize_activation_absence.py
- src/specify_cli/upgrade/migrations/m_2_1_2_fix_glossary_context_skill.py
- src/specify_cli/upgrade/migrations/m_3_1_1_charter_rename.py
- src/specify_cli/upgrade/migrations/m_unify_charter_activation_finalize.py
- tests/specify_cli/upgrade/test_registry_runs_first.py
- tests/specify_cli/upgrade/test_neutralised_migrations.py
- tests/specify_cli/upgrade/test_migration_discovery_without_retired_modules.py
- tests/upgrade/test_m_3_2_0rc35_default_charter_pack.py
- tests/specify_cli/upgrade/test_normalize_activation_absence.py
- tests/specify_cli/upgrade/test_skill_update_external_symlinks.py
- tests/upgrade/test_charter_rename_migration.py
- tests/specify_cli/upgrade/migrations/test_m_3_1_1_charter_rename.py
- tests/specify_cli/upgrade/migrations/test_m_unify_charter_activation_finalize.py
- tests/upgrade/test_consolidate_charter_bundle_migration.py
- tests/charter/test_activation_vocabulary_setequal.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP10 – Migration framework — run-first ordering and neutralised migrations

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

After WP18 lands, the `/ad-hoc-profile-load` skill is deleted: load profiles with `spk-charter-profile-load` instead (use whichever exists in your checkout).

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status` or the Activity Log below).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

Prepare the upgrade framework so the cutover migration (WP11/WP12) can run **before every other pending migration** (FR-012, C-008), and so older migrations neither break discovery nor undo the cutover once FR-005/FR-008/FR-011 delete what they read:

1. `BaseMigration.runs_first` (class attribute, default `False`), applied in `MigrationRegistry.get_applicable`; `get_all()` stays in version order; a second `runs_first` class is refused at registration.
2. Neutralise (recorded no-op: `detect()` false → the runner records `skipped / "Not applicable"`) three migrations: `m_3_2_0rc35_default_charter_pack`, `m_3_2_x_normalize_activation_absence`, `m_2_1_2_fix_glossary_context_skill`. Ids unchanged.
3. No migration module imports, at module level, a module this mission deletes (an `ImportError` in any `m_*.py` raises `MigrationDiscoveryError` and blocks **every** upgrade).
4. `m_3_1_1_charter_rename` stops recreating the retired `spec-kitty-charter-doctrine` skill directory; the finalize migration (`m_unify_charter_activation_finalize`) drops its call to `apply_legacy_governance_selection_key_compat` (deleted by WP14).

Done when every acceptance test marked `pending_until("WP10")` is green with the marker removed, and the ordering, chain-integrity and "neutralised = recorded as skipped" tests pass.

## Context & Constraints

- Read first: `spec.md` FR-012 (first sentence and the rc35 sentence), C-008, US2 AS-6; `plan.md` key design decisions 1–2; `contracts/upgrade-migration.md` ("Identity and ordering", "Neutralised migrations"); **`research/runtime-seams.md` §1** in full — §1.1 (selection/ordering today, with file:line), §1.3 (the `runs_first` decision and rejected alternatives), §1.4 (rc35 as a recorded no-op), §1.5 (the table of older migrations and the action for each).
- This WP runs in a **parallel lane** beside WP02–WP05 and WP17. It depends only on WP01; WP06, WP09 and WP11 depend on it. Ownership splits to watch:
  - `m_unify_charter_activation.py`'s module-level `from charter.activation.default_pack import ...` (`:59`) is removed by **WP06**, which owns that file and rewrites its promotion. Do not edit it here. Your discovery guard (T052) therefore covers the modules this mission deletes **that WP10 is responsible for** (`specify_cli.charter_pack_registry`), and WP06 removes the other import.
  - `tests/specify_cli/cli/commands/test_init_provisioning.py` is owned by **WP09**, which runs after you (WP09 depends on WP10). It pins the old rc35 behaviour in one test (`test_rc35_default_charter_pack_migration_identity_and_idempotence_unchanged`, `:320-349`). Delete that one test function here as a logged out-of-ownership edit (minimal hunk; WP09 edits other hunks of the same file later).
  - `tests/architectural/charter_path_literal_allowlist.yaml:264-277` has two entries for `m_3_2_0rc35_default_charter_pack.py` (`DefaultCharterPackMigration.apply`, lines 161–162). Neutralising the body makes them stale; the gate's staleness twin-guard will fail. Remove exactly those two entries as a logged edit to the shared gate file.
- **C-001**: neutralised migrations keep module, class and `migration_id` (old metadata stays meaningful), but lose their bodies, their helpers and their direct-call tests. No compatibility branch "in case the body is needed".
- In-repo precedent for a recorded no-op stub: `src/specify_cli/upgrade/migrations/m_2_1_2_fix_charter_doctrine_skill.py` (22 lines). Match its shape.
- The cutover migration itself (`m_4_0_0rc6_charter_pack_cutover.py`, `target_version = "4.0.0rc6"`, the current version; no version bump) is **WP11**, not this WP. Here you only add the mechanism and test it with planted migration classes.

## Branch Strategy

- **Strategy**: lane-based; the lane for this WP is assigned in `lanes.json` by `spec-kitty agent mission finalize-tasks`.
- **Planning base branch**: `issue-3732-charter-pack-rename`
- **Merge target branch**: `issue-3732-charter-pack-rename`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Red-first (C-006 / C-011)

```bash
grep -rn 'pending_until("WP10")' tests/acceptance/charter_pack_cutover/
# remove only those markers; run; confirm red; commit
git commit -m "test(upgrade): flip run-first and neutralised-migration acceptance tests red (#3732)"
```

If WP01 assigned none to WP10 (possible: the end-to-end FR-012 rows belong to WP11/WP12), record that in the Activity Log and make your first commit the new red unit tests of T054 (ordering and neutralisation), committed before the implementation.

## Subtasks & Detailed Guidance

### Subtask T050 – `runs_first` on `BaseMigration`, applied in `get_applicable`

- **Purpose**: one ordering fact, applied at the single selector every caller already funnels through (runtime-seams §1.3: runner `:169`, `cli/commands/upgrade.py:1829` and `:2016-2064` (planner JSON / dry-run parity), `upgrade/detector.py:72`, `compat/planner.py:709-716`). A runner-only hook was rejected because the preview would diverge from the run.
- **Steps**:
  1. `src/specify_cli/upgrade/migrations/base.py` (`BaseMigration`, `:71-100`): add `runs_first: ClassVar[bool] = False` with a docstring comment: "Selected before every other applicable migration by `MigrationRegistry.get_applicable`; at most one registered migration may set it; `detect()` of such a migration must be content-driven, never version-driven (runtime-seams §1.2)". Note `min_version` (`:93-95`) is declared but unused; leave it.
  2. `src/specify_cli/upgrade/registry.py`:
     - `register()` (`:29-61`): if the class sets `runs_first` and another registered class already does, raise `ValueError` naming both classes.
     - `get_applicable()` (`:74-120`): keep the selection loop byte-for-byte; at the end return a **stable partition**: `[m for m in applicable if m.runs_first] + [m for m in applicable if not m.runs_first]`. Extract the partition into a tiny private helper so `get_applicable` stays under complexity 15.
     - `get_all()` (`:64-71`) unchanged (`tests/architectural/test_migration_chain_integrity.py` walks it and fails on any backward step).
  3. **Version-independent selection for `runs_first`** (orchestrator decision, fixes the "stamped above the cutover version" wedge reported for WP11): a `runs_first` migration is selected whenever its `detect()` is true and it is not recorded as applied, **regardless of the `from_version`/`target_version` window**.
     - **Re-selection when recorded as applied** (orchestrator decision, AR-B4): `BaseMigration` gains a hook `structural_detect(project_path) -> bool` (default `False`). A `runs_first` migration whose `structural_detect()` is true is selected **even when `metadata.yaml` records it as applied**: in `get_applicable` and in `runner.py`'s `_apply_migration`, whose recorded-result skip (`runner.py:314-321`) runs before `detect()` today. Otherwise a teammate who pulls a committed `metadata.yaml` while untracked legacy files remain, or a merge that brings legacy state back, is wedged: the FR-011 gate refuses and `spec-kitty upgrade` skips the migration. WP11 implements the split predicate (structural part only: legacy root, legacy keys, `doctrine_pack_id`); this WP implements the selection.
     - Test with a planted `runs_first` class: recorded as success, `structural_detect()` true → selected and applied; recorded as success, `structural_detect()` false and `detect()` true → not selected. Otherwise a project stamped at or above the cutover version that still carries legacy state would be refused by the WP14 CLI-root gate yet never migrated by `spec-kitty upgrade`. Implement it in the same helper as the partition (append a `runs_first` migration that the window excluded when `detect()` is true); add a test: project stamped above the migration's `target_version`, legacy content present → selected; same project without legacy content → not selected.
  4. Update `get_applicable`'s docstring: "Returns applicable migrations in version order, except that a `runs_first` migration is placed first and is selected on `detect()` alone, independent of the version window."
  4. Touch `runner.py` only for the re-selection rule in step 3: `_apply_migration` re-runs `detect()` at apply time (`runner.py:336`), so every later migration sees the post-cutover state; the worktree loop filters the same list.
- **Files**: `base.py`, `registry.py`.
- **Parallel?**: No (T054 tests it).
- **Notes — residual to document, not fix**: same-version migrations (`target == from`) evaluate `detect()` once at selection time, before the cutover runs (`registry.py:98-117`); a project stamped exactly at such a migration's version can have it deselected in that run, and the next upgrade picks it up (runtime-seams §1.3 "Residual"). Put one sentence in the docstring.
- **Validation**: planted classes in T054.

### Subtask T051 – Neutralise rc35, normalizer and glossary-context skill migrations

- **Purpose**: each would either fail every pre-X upgrade once its inputs are deleted, or undo the cutover's resets (runtime-seams §1.4–1.5; plan decision 2; DM-01M497EW60HNWWJQCXDFA99R0H for the normalizer).
- **Steps**:
  1. `m_3_2_0rc35_default_charter_pack.py` (221 lines): keep the module, `@MigrationRegistry.register`, class `DefaultCharterPackMigration`, `migration_id = "3.2.0rc35_default_charter_pack"`, `target_version = "3.2.0rc35"`. Replace the docstring with two lines ("Superseded by the charter-pack cutover; kept as a recorded no-op so upgrade history stays meaningful."). Delete the module-level `from specify_cli.charter_pack_registry import ...` (`:49-52`), `_PER_KIND_KEYS`, `_DEFAULT_YAML_PATH` (`:71-77`), every helper and import the body used. `detect()` → `False`; `can_apply()` → `(False, "Superseded by the charter-pack cutover")`; `apply()` → `MigrationResult(success=True, warnings=["Superseded by the charter-pack cutover"])`.
  2. `m_3_2_x_normalize_activation_absence.py` (426 lines): same treatment, `migration_id`/`target_version` unchanged (`MIGRATION_ID`, `TARGET_VERSION` constants; keep `runs_on_worktrees = False`). Rationale for the module docstring: it wrote `[]` (= nothing activated) for absent per-artifact keys, contradicting the live absent-means-all contract (`pack_context.py:734-738`, `ArtifactKind.effective_when_absent`), and on a pre-3.2.6 project it would rewrite the keys the cutover just reset (runtime-seams §1.5 row 3).
     - It **also** mints the `config.yaml` `charter:` pointer when a `charter.yaml` exists without one (`_ensure_pointer`, `apply` `:395-426`). Before deleting that, verify the pointer is minted elsewhere for every path that reaches it — the fold migration `m_unify_charter_activation_finalize` (`consolidate_charter_bundle_fold`) is the expected owner; grep for `_CHARTER_POINTER_KEY` / `charter:` pointer writes. If the fold covers it, neutralise fully. If not, keep **only** the pointer half (detect true only for "charter.yaml without pointer"), record it as a deviation from the contract's "bodies removed", and flag it in the review hand-off.
     - `_per_artifact_activation_keys` and `_COARSE_ACTIVATION_KEYS` are imported by `tests/charter/test_activation_vocabulary_setequal.py:107-125` (the "4th activation-key copy" guard). Delete that test function: the copy it guards no longer exists. Keep the rest of the file.
  3. `m_2_1_2_fix_glossary_context_skill.py` (116 lines): it reads `charter.offering/skills/spec-kitty-glossary-context/SKILL.md` (`:69-81`), which FR-008 deletes (WP18); `apply` would then return "Cannot locate canonical SKILL.md" and **pre-2.1.2 projects would fail to upgrade**. Stub it the same way (`detect()` false, ids unchanged). Delete `TestGlossaryContextMigrationToleratesExternalSymlink` and `TestGlossaryContextMigrationToleratesReadOnlyTarget` from `tests/specify_cli/upgrade/test_skill_update_external_symlinks.py` (`:193-230`, `:352-390`); keep the other classes.
  4. Delete the direct-call tests of removed bodies: `tests/upgrade/test_m_3_2_0rc35_default_charter_pack.py` (whole file), `tests/specify_cli/upgrade/test_normalize_activation_absence.py` (whole file, unless the pointer half survives — then keep only pointer tests). In `tests/upgrade/test_consolidate_charter_bundle_migration.py`, `test_registry_orders_fold_after_seed_migrations` (`:440-470`) keeps `3.2.0rc35_default_charter_pack` in its seed set (registration order is unchanged) — keep it; `test_fold_relocates_seed_migration_output` (`:472-...`) runs `DefaultCharterPackMigration().apply()` as a real seed: rewrite its pre-state by writing the seeded `config.yaml` directly (the post-seed shape it needs), not by calling the stub.
  5. `tests/architectural/test_no_dead_modules.py:173,216,309` lists the three modules as discovery-only glue; they stay (modules kept). Nothing to change there; run it.
- **Files**: the three migration modules; tests above; logged edit to `charter_path_literal_allowlist.yaml`.
- **Parallel?**: Independent of T050.
- **Validation**: T054.

### Subtask T052 – Remove module-level imports of to-be-deleted modules from older migrations

- **Purpose**: discovery must survive every deletion this mission makes (runtime-seams §1.1: `auto_discover_migrations()` → any `ImportError` → `MigrationDiscoveryError`, called from `upgrade.py:1634` and `compat/planner.py:95`).
- **Steps**:
  1. Inventory (record output in the Activity Log):
     ```bash
     cd src/specify_cli/upgrade/migrations
     grep -n "^from \|^import " m_*.py _*.py | grep -E "charter_pack_registry|charter\.activation\.default_pack|specify_cli\.doctrine|kernel\.doctrine_root|cli\.commands\.charter\._layer_roots|cli\.commands\.doctrine|charter\.activation\.sync"
     ```
     At base the module-level hits are `m_3_2_0rc35_default_charter_pack.py:49` (`specify_cli.charter_pack_registry`, removed in T051) and `m_unify_charter_activation.py:59` (`charter.activation.default_pack`, removed by WP06). Every other hit must be **function-scoped** (lazy) or absent. If you find another module-level import of a module this mission deletes or moves (WP02–WP05 move `kernel.doctrine_root`, `_layer_roots`, `specify_cli.doctrine.*`), and the file is not owned by another WP, make it lazy or repoint it here; if it is owned elsewhere, record it for that owner.
  2. Lazy imports inside migration **bodies** that this mission deletes later are fine for discovery but fail at apply time. Known case: `m_unify_charter_activation_finalize.py:230-247` imports `apply_legacy_governance_selection_key_compat` — handled in T053. Record any other lazy import of a to-be-deleted symbol you find.
  3. Add `tests/specify_cli/upgrade/test_migration_discovery_without_retired_modules.py`: in a subprocess (clean `sys.modules`), install a `sys.meta_path` finder that raises `ModuleNotFoundError` for `specify_cli.charter_pack_registry`, then `MigrationRegistry.clear(); auto_discover_migrations()`; assert it succeeds and the rc35 id is registered. Planted self-test in the same file: a temp module with a module-level import of the blocked name makes discovery fail (proves the harness can see the failure). Keep the blocked-module list a single module constant so later WPs (WP13 deletes the registry; WP06 already removed `default_pack`) can extend it.
- **Files**: new test file; any lazy-import fix in an unowned migration recorded rather than made.
- **Parallel?**: Yes ([P] in tasks.md).

### Subtask T053 – `m_3_1_1_charter_rename` and finalize migration fixes

- **Purpose**: two older migrations that would re-create retired state after the cutover (runtime-seams §1.5 rows 4–5).
- **Steps**:
  1. `m_3_1_1_charter_rename.py:407-433` renames a project-level `spec-kitty-constitution-doctrine` skill directory to `spec-kitty-charter-doctrine`, a name FR-008 retires (WP18). With run-first ordering it runs **after** the cutover, and project-root retirement is manifest-driven, so the recreated unmanaged directory would be kept forever. Change it to **not** create `spec-kitty-charter-doctrine`: leave `spec-kitty-constitution-doctrine` untouched (no rename, no content rewrite) and add nothing to `changes`. Do not delete the user's directory here — removal of stale skill copies is the cutover's hash-matched step (WP12) and the retired-name registry (WP18). Record in the Activity Log that WP18 should add `spec-kitty-constitution-doctrine` to `RETIRED_CANONICAL_SKILL_NAMES` alongside the five folded names. Keep the rest of the migration (command-file renames, metadata normalisation) unchanged. Update `tests/upgrade/test_charter_rename_migration.py:245-265` and `tests/specify_cli/upgrade/migrations/test_m_3_1_1_charter_rename.py` to assert the old directory is left alone and no `spec-kitty-charter-doctrine` appears.
  2. `m_unify_charter_activation_finalize.py:215-265`: delete the lazy import of `apply_legacy_governance_selection_key_compat` (`:230-232`) and its call (`:247`). Do **not** let the legacy key be silently dropped (`GovernanceConfig` has no `extra="forbid"`; runtime-seams §3 "This is required, not optional"): if `governance_data` still carries a top-level `doctrine` key, fail closed — return/raise the migration's existing structured error naming `governance.doctrine` in `.kittify/charter/governance.yaml` and stating that the charter-pack cutover migration rewrites it (it runs first). In a real upgrade that branch is unreachable once WP11 lands; it exists so the data is never lost silently. Update the CR-01 comment block (`:236-246`).
  3. The lazy `pack_manager.ACTIVATION_YAML_KEYS` import (`:124`) stays; WP17/WP20 repoint it if the module moves.
  4. Tests: `tests/upgrade/test_consolidate_charter_bundle_migration.py` fixtures write a standalone `governance.yaml` with a top-level `doctrine:` block (`:51`) — rewrite them to the canonical `charter:` key (the shape the cutover produces) and add one test asserting the fail-closed error when `doctrine:` is present. Check `tests/specify_cli/upgrade/migrations/test_m_unify_charter_activation_finalize.py` for the same legacy shape and update it.
- **Files**: the two migrations; tests above.
- **Parallel?**: Yes ([P]).

### Subtask T054 – Tests: ordering, chain integrity, neutralised migrations recorded as skipped

- **Steps**:
  1. `tests/specify_cli/upgrade/test_registry_runs_first.py` (new). Use a fixture that snapshots `MigrationRegistry._migrations`, clears it, and restores it afterwards (never leak planted classes). Planted classes: `A` (target `3.1.0`), `B` (`3.2.0`), `F` (`runs_first=True`, target `9.9.9`-style high version but selected via the window you set up, and a content-driven `detect`). Assert:
     - `get_applicable("3.0.0", <to>)` returns `F` first, then `A`, `B` in version order;
     - `get_all()` is still pure version order (F last);
     - same-version selection (`target == from` with `detect()` true) still works and `F` still comes first;
     - registering a second `runs_first` class raises `ValueError` naming both;
     - with no `runs_first` class present, `get_applicable` output equals the old ordering (regression pin).
  2. Same file, selector parity (runtime-seams §1.1 "Callers of the selector"): with a planted `runs_first` migration, `upgrade/detector.py`'s detection list and the compat planner's preview (`compat/planner.py:709-716`) report it first. If wiring the full planner is heavy, assert through the functions they call; `tests/compat/test_dry_run_parity.py` already pins planner ↔ run agreement — run it.
  3. `tests/specify_cli/upgrade/test_neutralised_migrations.py` (new), parametrised over the three neutralised ids: `detect()` false on (a) an empty tmp project, (b) a project with the exact shape the old body handled (absent per-kind keys for rc35/normalizer; an old glossary-context `SKILL.md` for 2.1.2); `can_apply()` returns `(False, <reason>)`; `apply()` succeeds with no file change (tree hash before/after); `migration_id` / `target_version` unchanged from the literals above. Then drive one through the runner's `_apply_migration` (or a small `MigrationRunner` run on a tmp project) and assert the recorded result is `skipped` with `"Not applicable"` (`runner.py:349-361`).
  4. Run the chain gate unchanged: `tests/architectural/test_migration_chain_integrity.py`.
  5. Remove `pending_until("WP10")` markers (red-first) and turn them green.

## Test Strategy

```bash
make test-fast
uv run --frozen pytest tests/acceptance/charter_pack_cutover/ -q
uv run --frozen pytest tests/specify_cli/upgrade/test_registry_runs_first.py tests/specify_cli/upgrade/test_neutralised_migrations.py tests/specify_cli/upgrade/test_migration_discovery_without_retired_modules.py -q
uv run --frozen pytest tests/upgrade/ tests/specify_cli/upgrade/ tests/compat/ tests/specify_cli/compat/ -q     # owning subsystem: upgrade + compat selectors
uv run --frozen pytest tests/specify_cli/cli/commands/test_upgrade_command.py tests/specify_cli/cli/commands/test_init_provisioning.py tests/charter/test_activation_vocabulary_setequal.py -q
uv run --frozen pytest tests/architectural/test_migration_chain_integrity.py tests/architectural/test_no_dead_modules.py tests/architectural/test_no_dead_symbols.py tests/architectural/test_charter_path_literal_authority.py tests/architectural/test_mutation_ownership_routing.py tests/architectural/test_remediation_effectiveness.py -q
uv run --frozen ruff check src/specify_cli/upgrade/ tests/upgrade/ tests/specify_cli/upgrade/
uv run --frozen ruff format --check --force-exclude <every file you touched>
uv run --frozen mypy src/specify_cli/upgrade/registry.py src/specify_cli/upgrade/migrations/base.py src/specify_cli/upgrade/migrations/m_3_2_0rc35_default_charter_pack.py src/specify_cli/upgrade/migrations/m_3_2_x_normalize_activation_absence.py src/specify_cli/upgrade/migrations/m_2_1_2_fix_glossary_context_skill.py src/specify_cli/upgrade/migrations/m_3_1_1_charter_rename.py src/specify_cli/upgrade/migrations/m_unify_charter_activation_finalize.py
uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q
```

`test_mutation_ownership_routing.py` and `test_remediation_effectiveness.py` reference `m_3_1_1_charter_rename` / the finalize migration (grep shows them); run them as the implicated gates. Record every command with pass/fail counts.

## Commit discipline

Conventional subjects with `#3732`: `feat(upgrade): runs_first ordering in get_applicable (#3732)`, `refactor(upgrade): neutralise rc35, normalizer and glossary-context migrations (#3732)`, `fix(upgrade): charter rename stops recreating a retired skill dir (#3732)`, `fix(upgrade): finalize fails closed on a legacy governance key (#3732)`. First commit is the red flip (or red unit tests). Never push to `main`.

## Risks & Mitigations

- **Planted classes leaking into the global registry**: snapshot/restore fixture; never call `MigrationRegistry.clear()` without restoring.
- **Normalizer's pointer half**: verify before deleting (T051 step 2); losing the pointer would strand migrated projects on the legacy config store.
- **Out-of-ownership hunks** in `test_init_provisioning.py` (WP09, downstream) and `charter_path_literal_allowlist.yaml` (any WP touching charter paths; WP17 runs in parallel with you): keep the hunks minimal; log them.
- **Chain gate**: you add no new `target_version`, so the terminal-version rule is unaffected; WP11 adds the cutover at the current `4.0.0rc6`, with no version bump.

## Definition of Done

- [ ] Red-first commit; every `pending_until("WP10")` test green.
- [ ] `runs_first` attribute, partition in `get_applicable`, duplicate refusal in `register`; `get_all()` unchanged.
- [ ] `structural_detect` hook; a recorded `runs_first` migration is re-selected (registry and runner) when it returns true; tested.
- [ ] Three migrations neutralised (ids unchanged), recorded as skipped by the runner; their body tests deleted; normalizer pointer decision recorded.
- [ ] Discovery survives a blocked `specify_cli.charter_pack_registry` (test with planted self-test).
- [ ] `m_3_1_1` no longer creates `spec-kitty-charter-doctrine`; finalize no longer imports the compat helper and fails closed on `governance.doctrine`.
- [ ] Stale allowlist entries removed; rc35 test removed from `test_init_provisioning.py`; both logged.
- [ ] All Test Strategy commands run and recorded; ruff/format/mypy clean; no new suppressions.

## Review Guidance

- Red → green for the WP10 acceptance tests (or, if none, the red-first unit tests were committed before the implementation).
- `get_all()` order unchanged (chain gate green); `get_applicable` changes only by the partition.
- Neutralised modules contain no import of `charter_pack_registry`, no `default.yaml` path, no `[]` writer.
- The finalize change cannot silently drop a `governance.doctrine` selection.
- Confirm mypy ran on touched typed sources.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

**When adding an entry**:

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)
5. Agent ID should identify who made the change (claude-sonnet-4-5, codex, etc.)

**Initial entry**:

- 2026-10-06T19:30:00Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
- 2026-10-07T01:04:44Z – claude – shell_pid=6236 – T052 inventory: module-level hits at base were m_3_2_0rc35_default_charter_pack.py:49 (specify_cli.charter_pack_registry, removed here) and m_unify_charter_activation.py:59 (charter.activation.default_pack, WP06 owns). Lazy: m_3_2_0rc35_unified_bundle.py:155 imports charter.activation.sync.ensure_charter_bundle_fresh (function-scoped; flag for whoever deletes/moves charter.activation.sync). Normalizer: charter: pointer half was unreachable (only resolved a store when the pointer was already present), neutralised fully. WP18 should add spec-kitty-constitution-doctrine to RETIRED_CANONICAL_SKILL_NAMES. test_fr012_cutover_runs_first re-tagged pending_until WP11 per WP01 plan table (assertions unchanged).
