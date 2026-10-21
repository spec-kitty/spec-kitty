---
work_package_id: WP08
title: Ledger migration, upgrade-only scope, dogfood
dependencies:
- WP07
requirement_refs:
- FR-003
- FR-004
- FR-017
- NFR-001
- NFR-002
- C-001
- SC-002
- FR-021
planning_base_branch: core-align-3-persistent-deactivation
merge_target_branch: core-align-3-persistent-deactivation
branch_strategy: Planning artifacts for this mission were generated on core-align-3-persistent-deactivation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into core-align-3-persistent-deactivation unless the human explicitly redirects the landing branch.
subtasks:
- T043
- T044
- T045
- T046
- T047
- T048
- T049
- T050
- T051
- T052
phase: Phase 5 - Migration
history:
- at: '2026-10-19T12:17:27Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/upgrade/
create_intent:
- src/charter/activation/activation_ledger.py
- src/specify_cli/upgrade/migrations/m_4_0_0rc8_activation_ledger.py
- tests/upgrade/migrations/test_m_4_0_0rc8_activation_ledger.py
- tests/upgrade/test_legacy_activation_scope.py
- tests/upgrade/test_rc5_full_manifest_activation_ledger.py
- .kittify/charter/activation.yaml
- tests/specify_cli/upgrade/test_migrate_activation_ledger_cmd.py
- tests/specify_cli/upgrade/test_upgrade_keyless_project_gets_ledger.py
- tests/specify_cli/upgrade/test_init_reseed_keeps_rc8_pending.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/upgrade/migrations/base.py
- src/specify_cli/upgrade/migrations/m_4_0_0rc8_activation_ledger.py
- src/specify_cli/upgrade/migrations/order_manifest.txt
- src/specify_cli/upgrade/registry.py
- src/specify_cli/upgrade/runner.py
- src/specify_cli/cli/commands/upgrade.py
- src/specify_cli/cli/commands/migrate_cmd.py
- src/charter/activation/activation_ledger.py
- src/charter/activation/api.py
- tests/architectural/test_charter_activation_api_reexport.py
- tests/upgrade/migrations/test_m_4_0_0rc8_activation_ledger.py
- tests/upgrade/test_legacy_activation_scope.py
- tests/upgrade/test_rc5_full_manifest_activation_ledger.py
- .kittify/charter/activation.yaml
- .kittify/charter/charter.yaml
- .kittify/charter/synthesis-manifest.yaml
- .kittify/config.yaml
- src/specify_cli/upgrade/assessment.py
- tests/specify_cli/upgrade/test_upgrade_provisions_mission_type_activations.py
- tests/charter_offering/test_project_charter_single_owner.py
- tests/conftest.py
- tests/charter/test_config_stem_parity.py
- src/specify_cli/_completion_manifest.json
- tests/specify_cli/upgrade/test_migrate_activation_ledger_cmd.py
- src/specify_cli/upgrade/init_seed.py
- tests/specify_cli/upgrade/test_upgrade_keyless_project_gets_ledger.py
- tests/specify_cli/upgrade/test_init_reseed_keeps_rc8_pending.py
- src/specify_cli/cli/commands/init.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP08 – Ledger migration, upgrade-only scope, dogfood

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro` (`packs/built-in/agent_profiles/python-pedro.agent.yaml`)
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

- Check `review_ref` in the event log; address every item; record with `spec-kitty agent tasks add-history WP08 --note "..."`.

---

## Objective

Move existing projects onto the ledger with a new idempotent, crash-recoverable upgrade
migration `4.0.0rc8_activation_ledger`, keep every **shipped** migration behaving byte-for-byte
through an upgrade-only legacy scope entered by `BaseMigration` and the selection entry points,
and dogfood: migrate this repository's own `.kittify/` and commit the result.

## Context

- Plan IC-08; data-model.md §5, §8 (`ledger_migration` rows); research.md D-03, D-12; spec US2, FR-003, FR-004, FR-017, NFR-001, NFR-002, C-001, SC-002.
- Migration Ledger model (CLAUDE.md, ADR 2026-10-17-1): tracked partition (`clone_local_effect = False`), selection by ledger-diff, entry required in `order_manifest.txt`, `detect()` / `can_apply` are the idempotency guard.
- **C-001 / DIRECTIVE_044: never edit a shipped migration.** The scope wrapper lives in `base.py`; shipped migrations get it by inheritance. If any shipped migration's behaviour changes, that is a defect in the wrapper, not a reason to edit the migration.
- `base.py` imports the scope from **kernel** (`kernel.activation_ledger_store.legacy_activation_scope`) directly; the canonical root is resolved in specify_cli and passed in (M3).
- Mission order: WP08 of 15 (strictly linear). Builds on WP02 (resolver, scope, `prepare_ledger_write`), WP03 (write target, rendering identity), WP04–WP07 (nothing in their behaviour changes here).
- Transition model D0: the migration must work in both modes. In strict mode the shipped migrations see the legacy surface only because they run inside `legacy_activation_scope`; in tolerant mode they see it anyway. New tests run strict through `SWEPT_PREFIXES`, and the shipped-migration behaviour inside the scope is what they prove. Existing upgrade tests stay green unchanged in tolerant mode.
- Shared files (ordered): `activation_ledger.py`, `api.py`, the API re-export gate (from WP02/WP05; →WP09); `upgrade/assessment.py` (from WP03). `cli/commands/upgrade.py` is owned by this WP only (it also receives the m6 ordering item, T049).
- Operator rulings: `stray_config_copy` → refuse as divergent; `unmigrated_projects` / `pre_ledger_seam` → no runtime fallback, upgrade-only legacy target.

## Branch Strategy

- **Strategy**: single_branch; sequential in the repository root checkout on `core-align-3-persistent-deactivation`.
- **Planning base branch**: `core-align-3-persistent-deactivation`
- **Merge target branch**: `core-align-3-persistent-deactivation`

```bash
spec-kitty agent action implement WP08 --agent claude --mission persistent-deactivation-ledger-01M59YAA
```

## ATDD (red first)

T043 writes the migration acceptance tests (every `ledger_migration` fixture shape, divergence
refusals with byte-identity, idempotent re-run, crash recovery), the scope tests (shipped
migrations act on legacy surfaces inside the scope; a lane-worktree upgrade matches the canonical
root) and the rc5-era full-manifest upgrade (SC-002). Commit before implementation; record the
red summary.

## Subtasks

### Subtask T043: Failing acceptance tests

**Steps**:
1. `tests/upgrade/migrations/test_m_4_0_0rc8_activation_ledger.py`, parametrised over fixture shapes:
   - pointer `charter.yaml` holding `activated_directives: []`, `activated_tactics: [T]`, `mission_type_activations` → ledger holds them verbatim (three-state, `[]` preserved), `charter.yaml` lost them, effective sets unchanged (compare `PackContext` before/after);
   - no-pointer legacy `config.yaml` → same;
   - leftover `config.yaml` copy equal to the authority → copy removed;
   - leftover copy differing → refusal naming key + both files; all three files byte-identical (NFR-001);
   - stray copy where the authority lacks the key → refusal (`stray_config_copy`);
   - existing ledger + equal legacy keys → legacy stripped (re-run after crash, P9);
   - existing ledger + differing legacy key → refusal;
   - second run on every fixture → 0 bytes changed, "nothing to do" (NFR-002);
   - bundle hash restamped after the move (`synthesis-manifest.yaml` `bundle_content_hash` matches).
2. Crash injection: monkeypatch each step boundary (after ledger write, after charter.yaml strip, after config.yaml strip) to raise; re-run completes and the end state equals the uninterrupted run.
3. `tests/upgrade/test_legacy_activation_scope.py`:
   - every public `project_path`-first method a subclass defines in `cls.__dict__` (`detect`, `can_apply`, `apply`, rc6 `structural_detect` / `is_first_application` / `reselect_when_recorded`) runs inside `in_legacy_activation_scope(project)`; assert by a spy migration subclass in the test;
   - re-entrancy; `functools.wraps` preserves names/signatures;
   - `MigrationRegistry.get_applicable`, runner selection, `migrate ledger`, `spec-kitty upgrade --dry-run` all enter it;
   - worktree: lane worktree upgrade while the main checkout is unmigrated → scope matches the canonical root;
   - **transition-mode pin, rewritten by WP14 T082**: outside the scope, in the in-Mission strict test mode (the file is listed in `SWEPT_PREFIXES`), an ordinary read raises naming `spec-kitty upgrade`. The shipped semantics differ: amended US2.6 reads the legacy allow keys. The same fixture inside the scope reads LEGACY (positive control);
   - `get_applicable(None)` (no project path) enters no scope and resolves nothing; the wrapper matches the project path **by position** (first positional parameter after `self`/`cls`), never by parameter name.
4. `tests/upgrade/test_rc5_full_manifest_activation_ledger.py`: build an rc5-era fixture (reuse `tests/upgrade/_legacy_upgrade_fixture.py`), run the whole manifest via the runner; the shipped migrations act on the legacy surface and the ledger migration then moves the result (US2.6 second half, SC-002); `spec-kitty migrate ledger --json` lists `4.0.0rc8_activation_ledger` as applied.

### Subtask T044: `BaseMigration.__init_subclass__` scope wrapper (M4)

**Steps**:
1. In `upgrade/migrations/base.py` (`:74`, `apply` `:199`) add `__init_subclass__` that wraps each public callable defined in the subclass's own `cls.__dict__` whose first positional parameter after `self` is the project path. Use `functools.wraps`; the wrapper resolves the canonical root (`charter.resolution.resolve_canonical_repo_root` via the existing allowed import path, or the specify_cli helper that already wraps it) and enters `legacy_activation_scope(project_path, canonical_root=...)`; pass the path positionally.
2. Static/class methods and private names are not wrapped; document the rule in the docstring.
3. Keep the wrapper pure and small (complexity ≤ 15); unit-test `_wraps_project_method(fn) -> bool` directly.

### Subtask T045: Selection entry points enter the scope

**Steps**: enter the scope in `MigrationRegistry.get_applicable` (`upgrade/registry.py:87-130`; with `project_path=None` it enters no scope), `MigrationRunner.upgrade` (`runner.py:170-312`, entry at `:209`, selection at `:364`), `upgrade_worktrees_only` (`runner.py:313`), worktree selection (`:573`), `spec-kitty migrate ledger` (`cli/commands/migrate_cmd.py:1773`, scope only) and the `spec-kitty upgrade` command body (`cli/commands/upgrade.py`: dry-run preview `:515`, repairs). The **finalizer provisioning** (`:1050`) runs **after the legacy scope closes**, as T049.3 requires (pass-9 M1).

### Subtask T046: Migration planner/apply in the seam

**Steps** (in `activation_ledger.py`):
0. **Legacy deny keys refuse (H2/H3)**: if any legacy surface holds a `deactivated_<kind>` key (possible only in the in-mission tolerant mode, which never ships), the plan is a refusal naming the key and the file, and nothing is written, like a divergence. Add a fixture row for it in T043.
1. **Spellings move verbatim** (`mission_pivot_option_b` adjustment): the migration copies every id exactly as written, with no stem normalisation and no de-duplication. That keeps NFR-002 and the three-state rule; canonical spelling is the future ACL's job (R11: stems stored by new writes, declared ids emitted on export). A case with a declared-id allow entry and a stem deny entry moves both as is.
1a. `plan_ledger_migration(repo_root) -> LedgerMigrationPlan` (pure): surfaces = authority (pointer `charter.yaml`, else `config.yaml`), leftover `config.yaml` copy, existing ledger; per-key order-insensitive comparison keeping three states; refusal object naming key and files on any difference (incl. authority-lacks-key); when a ledger exists, legacy keys equal to it are scheduled for stripping.
2. `apply_ledger_migration(repo_root, plan)`: (a) ledger write — **allow keys only**, `deny_change=None` (the guard proves the deny set is untouched; no migration ever touches deny keys, operator ruling `deny_writers`); (b) strip `charter.yaml` via `prepare_charter_yaml_section(..., remove=)` (`charter_yaml_io.py:649`); (c) strip `config.yaml`; (d) `restamp_bundle_hash` (`bundle_restamp.py:25`).
3. Keep each function ≤ 15 complexity: split surface collection, comparison, and apply steps.

### Subtask T047: The migration module and manifest entry

**Steps**:
1. **Version check first** (`mission_pivot_option_b` adjustment): read `pyproject.toml` `version` on the rebased branch before minting.
   - If it is no longer `4.0.0rc8`, use the current version for `target_version`, and name the id, module and manifest entry after it (`<version>_activation_ledger`).
   - Update every reference in the same commit: the `order_manifest.txt` entry, tests, the WP14/WP15 prompts' mentions (record them in your history note for the orchestrator), and the `migrate activation-ledger` ledger row.
   - Below, `4.0.0rc8` stands for that version.
   `upgrade/migrations/m_4_0_0rc8_activation_ledger.py`: `migration_id = "4.0.0rc8_activation_ledger"`, `target_version = "4.0.0rc8"` (matches `pyproject.toml:3` today), `clone_local_effect = False`, no `runs_first`, `runs_on_worktrees = False`; `detect()` = legacy activation keys present (any surface); `apply()` = plan → refuse (structured failure, nothing written) or apply. A thin shell over T046 via `charter.activation.api`.
2. Append `4.0.0rc8_activation_ledger` after `4.0.0rc7_track_charter_pack_yaml` in `order_manifest.txt` (no `# tie:` — its target version is higher).

### Subtask T048: Idempotency and crash-recovery hardening

**Carry-forward**:
- In strict mode a fresh project resolved to the ledger can get an empty `{}` file if a caller applies `prepare_activation_write(repo, {})`. Make empty writes a no-op when nothing changes.
- Drop the underscore on `_legacy_activation_scope` now that this WP adds its consumers (WP02 note).

**Steps**: make T043's crash-injection and re-run tests green; verify `detect()` is False after a full run and that a refused run leaves no `success` ledger record (so it retries after the operator fixes the divergence).

### Subtask T049: m6 — re-prepare provisioning after migrations

**Purpose**: moved here from the old WP02 by the post-tasks squad (D1). `upgrade/assessment.prepare_upgrade_repairs` (`assessment.py:121-127`) builds a CAS provisioning write before migrations run; inside the scope with no ledger it targets the legacy surface, which this WP's migration then moves, so the CAS is stale.

**Steps**:
1. In `cli/commands/upgrade.py` `_finalizer_step_provision` (`:1050-1100`), re-prepare the provisioning write **after** the migrations ran (re-resolve the target through the seam).
2. Add a test in `tests/specify_cli/upgrade/test_upgrade_provisions_mission_type_activations.py` pinning the order: a legacy fixture upgraded end to end ends with `mission_type_activations` in the ledger and no stale-CAS error.
3. **Keyless pre-ledger project (pass-8 M3)**: on a project with **no** activation keys anywhere and no ledger, rc8 has nothing to move (`detect()` False). The final provisioning step must not land on the legacy surface.
   - Resolve the provisioning target **outside** `legacy_activation_scope`, after the migrations. A project with no legacy keys is then "fresh", and the write goes to the ledger.
   - Red-first test, in a new file `tests/specify_cli/upgrade/test_upgrade_keyless_project_gets_ledger.py` listed in `SWEPT_PREFIXES`: a keyless fixture → full `spec-kitty upgrade` → `.kittify/charter/activation.yaml` holds `mission_type_activations`, and `config.yaml` / `charter.yaml` hold no activation key.
   - Add a positive control: a legacy-keyed fixture still gets its keys moved by rc8.
   - WP14's one-mode resolver keeps this: its "fresh" row covers the finalizer.

#### T049 (continued): the init seed

**Init seed (pass-8 M4, owned here because it is the rc8 migration's selection)**. `src/specify_cli/upgrade/init_seed.py` `seed_migration_ledger_for_init` (`:66-97`) records every tracked migration as success, unconditionally.
- **Fix** (pass-9 H1): skip the `4.0.0rc8_activation_ledger` record only when legacy activation keys **existed before this `init` run started** and no ledger exists.
  - `src/specify_cli/cli/commands/init.py` computes `pre_existing_legacy_keys` (through the kernel resolver's legacy-key probe) **before** it calls `provision_default_mission_type_activations` (`init.py:1456`), and passes it to `seed_migration_ledger_for_init(project_root, *, pre_existing_legacy_keys)`.
  - Keys that this run's own provisioning writes into `config.yaml` (tolerant mode, on a fresh project) never count. A fresh init therefore still seeds rc8 as success.
  - Every other migration is seeded as today.
- **Red-first test** (new file `tests/specify_cli/upgrade/test_init_reseed_keeps_rc8_pending.py`, listed in `SWEPT_PREFIXES`): an unmigrated fixture (legacy keys, no ledger).
  - Re-run `spec-kitty init` → `spec-kitty migrate ledger --json` still lists rc8 pending → `spec-kitty upgrade` moves the keys into the ledger.
  - Positive control: a fresh `init` still seeds rc8 as success (its own provisioning keys do not count), so `upgrade` is a no-op. The existing `tests/upgrade/test_init_ledger_seed_idempotency.py` must stay green unchanged.

### Subtask T050: API exports

**Steps**: export `plan_ledger_migration`, `apply_ledger_migration`, `LedgerMigrationPlan` (and the refusal type if the migration needs it) on `charter.activation.api`; update `tests/architectural/test_charter_activation_api_reexport.py`. No boundary-baseline growth.

### Subtask T051: `spec-kitty migrate activation-ledger` (FR-021, operator ruling `dogfood_migration_path`)

**Purpose**: a narrow command that runs exactly the ledger migration's move, without the rest of
the upgrade. It serves this repository's dogfood and any project an older CLI wrote legacy keys
into again.

**Steps**:
1. In `src/specify_cli/cli/commands/migrate_cmd.py`, beside the existing `migrate backfill-*` commands, add `migrate activation-ledger [--dry-run] [--json]`.
   - It is a thin shell over `charter.activation.api.plan_ledger_migration` / `apply_ledger_migration`, the same functions the rc8 migration calls.
   - It applies the same divergence refusal (FR-004) and the same legacy-deny-key refusal.
   - It is idempotent: a re-run reports nothing to do and writes nothing.
   - `--dry-run` lists the moves (key, from-file, to-file) and writes nothing.
   - It runs inside `legacy_activation_scope` (canonical-root aware, like the migration).
2. **Migration-ledger record** (analyze pass 5, M2: decided). Write the `success` row for
   `4.0.0rc8_activation_ledger` **only when `.kittify/migration-ledger.jsonl` already exists**
   (the project is ledger-adopted). Use the ledger module's own record builder and append path.
   When the file is absent, record nothing and report `"ledger_record": "not_recorded"`.
   Reason: creating the file flips `metadata._ledger_adopted` (`metadata.py:372`), and
   `ProjectMetadata.save()` would then drop the `migrations:` list (`:241`) before the backfill
   reads it, losing the applied-migration history. Not recording is safe: a later `spec-kitty upgrade` still **selects** rc8 by ledger-diff,
   its `detect()` is False, it is reported "not needed", nothing moves, and the runner records
   `skipped` (a harmless, idempotent re-skip; carry-forward M1/L2). Tests
   cover both branches. This repository has no migration ledger, so the dogfood records
   nothing.
3. Exit codes:
   - 0: moved, or nothing to do;
   - 1: refused (divergence or legacy deny key), with nothing written;
   - 2: usage error.

   `--json` emits `{"result": "moved"|"noop"|"refused"|"dry_run", "moves": [{"key", "from", "to"}], "refusal": {"key", "files", "reason"}|null, "ledger_record": "written"|"not_recorded"}`.
4. Help text with at least one usage example (the charter requires examples in CLI help), then regenerate `src/specify_cli/_completion_manifest.json` (`.venv/bin/python -m specify_cli.completion --regenerate`) and run `tests/architectural/test_completion_manifest_freshness.py`.
5. Tests in a new `tests/specify_cli/upgrade/test_migrate_activation_ledger_cmd.py`, listed in `SWEPT_PREFIXES`:
   - dry run;
   - move;
   - re-run is a no-op;
   - divergence refusal (byte-identical files, exit 1);
   - legacy deny key refusal;
   - exit codes;
   - JSON shape;
   - ledger record written when the migration ledger exists, `not_recorded` when it does not;
   - a later `upgrade --dry-run`:
     - with a migration ledger that the command wrote the success row into, rc8 is **not selected**;
     - with no migration ledger, rc8 **is selected**, reported not needed, nothing moves, and the runner records `skipped`;
   - `metadata.yaml` `migrations:` is untouched when no migration ledger exists.
6. WP15 documents the command (`docs/api/cli-commands.md`).

### Subtask T052: Dogfood this repository (last task)

**Steps**:
1. **Dogfood path (H1, operator ruling `dogfood_migration_path`)**: **never run `spec-kitty upgrade` here.** **Re-measure first** on the rebased branch:
   - run `.venv/bin/spec-kitty migrate ledger --json` and record `total` / `applied` / `pending` in `traces/approach.md`;
   - check that `.kittify/migration-ledger.jsonl` is absent.

   It measured 125/125 pending with no ledger file on 2026-10-19. If a migration ledger now exists, T051.2 writes the success row, so say which branch applied.
2. Run `.venv/bin/spec-kitty migrate activation-ledger --dry-run` and inspect the listed moves. **STOP** if it reports a divergence or a legacy deny key: report it in the history note and `traces/tooling-friction.md`, do not hand-edit, and hand back to the orchestrator. (Today `mission_type_activations` is equal in `.kittify/config.yaml` and the pointer `.kittify/charter/charter.yaml`, so it is stripped from both.)
3. Run `.venv/bin/spec-kitty migrate activation-ledger`. Inspect the result:
   - `.kittify/charter/activation.yaml` is created;
   - the activation keys are gone from `charter.yaml` (and from `config.yaml`, which held keys), with non-activation keys untouched and comments preserved;
   - `synthesis-manifest.yaml` is restamped;
   - the migration-ledger record exists, if one was written (T051.2).
4. `spec-kitty charter context --action implement` output is identical before and after (diff it).
5. **Repository-reading tests (H1)**: two tests read **this** repository's own `.kittify/` activation keys raw. They were measured with a grep for live-root reads (`_REPO_ROOT` / `parents[N]` / `_find_repo_root()` / the session `repo_root` fixture of `tests/charter/conftest.py`, joined to `.kittify` and an activation key, with no `tmp_path` project):
   - `tests/charter/test_config_stem_parity.py`: `_load_config` reads `config.yaml` and the pointer `charter.yaml`;
   - `tests/charter_offering/test_project_charter_single_owner.py`: reads `.kittify/charter/charter.yaml`.

   In this dogfood commit, re-point both to the seam (`load_activation_ledger` through `charter.activation.api`). This WP owns them (the canceled sweep's census excluded them). Then run them plus `tests/charter_offering/`. Other live-repo readers go through the seam already (for example `tests/charter/test_model_task_routing_resolves.py` passes `repo_root=REPO_ROOT` to the context builder); they need no change, but run them.
6. Commit **only** these files with message `chore(WP08): migrate this repository onto the activation ledger`:
   - `.kittify/charter/activation.yaml`;
   - the edited `.kittify/charter/charter.yaml`, and `.kittify/config.yaml` if it held keys;
   - the restamped `.kittify/charter/synthesis-manifest.yaml`;
   - (no migration-ledger file: this repository has none, so T051.2 writes nothing; if the re-measure in step 1 finds one, record that out-of-map edit with a one-line rationale);
   - the two re-pointed tests.

## Validation / targeted test surface

```bash
cd /home/user/spec-kitty
.venv/bin/python -m pytest -q tests/upgrade/migrations/test_m_4_0_0rc8_activation_ledger.py tests/upgrade/test_legacy_activation_scope.py tests/upgrade/test_rc5_full_manifest_activation_ledger.py
.venv/bin/python -m pytest -q -n auto --dist loadfile -m "not timing and not stress" tests/upgrade tests/specify_cli/upgrade tests/migration tests/migrate
.venv/bin/python -m pytest -q tests/cli/test_migrate_backfill_wp_status.py tests/cli/test_migrate_cmd_messaging.py tests/cli/test_migrate_group_flags_4964.py tests/cli/test_migrate_project_conflicts.py tests/integration/test_migration_backfill.py tests/architectural/test_lifted_cli_bytecode_heal_startup.py
.venv/bin/python -m pytest -q -n auto --dist loadfile -m "not timing and not stress" tests/charter_offering
.venv/bin/python -m pytest -q tests/specify_cli/upgrade/test_migrate_ledger_cmd.py tests/specify_cli/upgrade/test_unify_charter_activation_migration.py tests/specify_cli/upgrade/test_upgrade_provisions_mission_type_activations.py tests/upgrade/test_activate_builtin_types_migration.py
.venv/bin/python -m pytest -q -n auto --dist loadfile -m "not timing and not stress" tests/charter
.venv/bin/python -m pytest -q tests/architectural/test_migration_order_manifest.py tests/architectural/test_layer_rules.py tests/architectural/test_charter_activation_api_reexport.py tests/architectural/test_runtime_charter_activation_boundary.py tests/architectural/test_no_dead_symbols.py tests/architectural/test_charter_path_literal_authority.py
make test-fast
uv run --frozen ruff check <touched files>
uv run --frozen ruff format --check --force-exclude <touched files>
uv run --frozen mypy src/specify_cli/upgrade/migrations/base.py src/specify_cli/upgrade/migrations/m_4_0_0rc8_activation_ledger.py src/specify_cli/upgrade/registry.py src/specify_cli/upgrade/runner.py src/charter/activation/activation_ledger.py
.venv/bin/python -m pytest -q tests/upgrade/test_init_ledger_seed_idempotency.py tests/specify_cli/upgrade/test_upgrade_keyless_project_gets_ledger.py tests/specify_cli/upgrade/test_init_reseed_keeps_rc8_pending.py tests/specify_cli/upgrade/test_migrate_activation_ledger_cmd.py tests/architectural/test_completion_manifest_freshness.py
.venv/bin/spec-kitty migrate activation-ledger --dry-run --json
```

## Standing orders

- python-pedro; complexity ≤ 15; ruff/format(`--force-exclude`)/mypy clean; no suppressions.
- **Do not edit any shipped migration** (`git diff --stat src/specify_cli/upgrade/migrations/` must show only `base.py`, the new module and `order_manifest.txt`).
- Append dated entries to the Mission's `traces/*.md` (dogfood outcome in `approach.md`; any refusal in `tooling-friction.md`).

## Definition of Done

- Migration moves every fixture shape, refuses every divergent one byte-identically, is idempotent and crash-recoverable.
- Shipped migrations behave as before inside the scope (rc5 full-manifest test green).
- This repository migrated and committed.
- Gates green; subtasks marked done.

## Risks

- rc35's raw `yaml.dump` (`m_3_2_0rc35_activate_builtin_mission_types.py:221`) writes legacy surfaces before the ledger exists — expected; the ledger migration moves the result. Do not "fix" rc35.
- Wrapping by signature inspection can miss a method with a renamed first parameter: test with a spy subclass and with the real rc6 migration.
- A selection-time exception turned into `True` by rc6 `structural_detect` silently re-selects: the scope must be active during selection.

## Reviewer Guidance

- Run `git diff --stat` on the migrations folder (C-001).
- Check refusal byte-identity assertions cover all three files.
- Check the dogfood commit touches only the listed `.kittify/` files.

## Test-mode rules (analyze pass 2, binding)

- **New test files run strict through `SWEPT_PREFIXES`.** Every new test file this WP adds is
  appended, by exact path, to `SWEPT_PREFIXES` in `tests/conftest.py`, in the same commit as the
  file. The edit is append-only; this WP co-owns `tests/conftest.py`, dependency-ordered.
- **How strict mode is set (M1).** A `pytest_runtest_setup(item)` hookimpl (`tryfirst=True`) in
  `tests/conftest.py` sets or clears `os.environ["SPEC_KITTY_ACTIVATION_STRICT"]` from the
  item's path **before any fixture of that item is set up**, so function- and module-scoped
  fixtures see the item's mode. `test` means strict, and a stray legacy key raises. A matching
  `pytest_runtest_teardown` restores the previous value.
- **Session-scoped activation-seeding fixtures must be mode-independent (L1).** A session fixture
  is set up once, by its first user, in that item's mode. No such fixture exists today (grep).
  Any future one must be function-scoped, or go through the
  `tests/_factories/activation_ledger.py`, which works in both modes.
- **No test file references `SPEC_KITTY_ACTIVATION_STRICT`.** That covers `setenv`, `delenv`
  and string mentions. There are two exceptions: the kernel resolver test
  `tests/kernel/test_activation_ledger_store.py` (WP02 creates it, WP14 rewrites it), and the
  swept-prefix fixture in `tests/conftest.py` itself (WP02 creates it, WP14 deletes it).
- **No new tolerant-mode-only test.** Tolerant behaviour is pinned only by the existing tests,
  which stay unchanged (the sweeps were canceled by `mission_pivot_option_b`; WP14 re-seeds only what its reduced flip turns red), and by the kernel resolver test. An existing test
  file this WP modifies must stay correct in tolerant mode. Tests for new behaviour go in new,
  ledger-seeded files.
