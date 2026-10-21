---
work_package_id: WP14
title: 'The reduced flip: one mode, no deny keys off the ledger, fresh projects on the ledger'
dependencies:
- WP10
requirement_refs:
- FR-017
- FR-019
- FR-020
- C-003
- SC-001
- SC-004
planning_base_branch: core-align-3-persistent-deactivation
merge_target_branch: core-align-3-persistent-deactivation
branch_strategy: Planning artifacts for this mission were generated on core-align-3-persistent-deactivation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into core-align-3-persistent-deactivation unless the human explicitly redirects the landing branch.
subtasks:
- T078
- T079
- T080
- T081
- T082
- T083
- T084
phase: Phase 9 - Reduced cutover (mission_pivot_option_b)
history:
- at: '2026-10-19T12:17:27Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks (revised after the post-tasks squad, D0/F2)
agent_profile: python-pedro
authoritative_surface: src/
create_intent:
- tests/architectural/test_no_activation_strict_env.py
- tests/acceptance/test_persistent_deactivation.py
- tests/acceptance/test_init_ledger_flow.py
- tests/acceptance/test_unmigrated_cli_still_runs.py
- src/kernel/activation_ledger_store.py
- src/charter/activation/activation_ledger.py
- tests/_factories/activation_ledger.py
- tests/kernel/test_activation_ledger_store.py
- tests/upgrade/test_legacy_activation_scope.py
- tests/doctor/test_doctor_activation_ledger.py
- tests/charter/activation/test_activation_write_target_ledger.py
- tests/specify_cli/cli/commands/test_init_writes_ledger.py
- tests/charter/activation/test_activation_ledger.py
- tests/specify_cli/cli/commands/charter/test_deactivate_records_exclusion.py
execution_mode: code_change
model: ''
owned_files:
- src/kernel/activation_ledger_store.py
- src/charter/activation/activation_ledger.py
- src/charter/activation/pack_manager.py
- src/charter/activation/charter_yaml_io.py
- src/specify_cli/provisioning/default_charter.py
- src/specify_cli/cli/commands/charter/deactivate.py
- src/specify_cli/charter_runtime/preflight/cli.py
- src/specify_cli/charter_runtime/preflight/hook.py
- src/specify_cli/cli/commands/charter/_synthesis.py
- tests/conftest.py
- tests/_factories/activation_ledger.py
- tests/kernel/test_activation_ledger_store.py
- tests/upgrade/test_legacy_activation_scope.py
- tests/doctor/test_doctor_activation_ledger.py
- tests/charter/activation/test_activation_write_target_ledger.py
- tests/specify_cli/cli/commands/test_init_writes_ledger.py
- tests/charter/activation/test_activation_ledger.py
- tests/specify_cli/cli/commands/charter/test_deactivate_records_exclusion.py
- tests/architectural/test_no_activation_strict_env.py
- tests/acceptance/test_persistent_deactivation.py
- tests/acceptance/test_init_ledger_flow.py
- tests/acceptance/test_unmigrated_cli_still_runs.py
- tests/review/test_gate_bindings.py
- tests/specify_cli/mission_step_contracts/test_executor.py
- tests/specify_cli/invocation/**
- tests/charter/**
- tests/charter_offering/**
- tests/specify_cli/**
- tests/upgrade/**
- tests/integration/**
- tests/core/**
- tests/acceptance/**
- tests/_factories/**
- src/charter/activation/compiler.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP14 – The reduced flip: one mode, no deny keys off the ledger, fresh projects on the ledger

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro` (`packs/built-in/agent_profiles/python-pedro.agent.yaml`)
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

- Check `review_ref` in the event log; address every item; record with `spec-kitty agent tasks add-history WP14 --note "..."`.

---

## Objective

Ship the **reduced flip** of operator ruling `mission_pivot_option_b` (2026-10-20).

- **Delete** the transition machinery: the `SPEC_KITTY_ACTIVATION_STRICT` environment variable, `activation_strict()` and `activation_strict_test()`, the tolerant/strict split, `legacy_save_accepts_deny()`, the `SWEPT_PREFIXES` list and both `pytest_runtest_*` hooks, and `tests/_support/activation_strict_mode.py`. There is one mode afterwards.
- **Keep** reads on an unmigrated project (legacy activation keys, no ledger) on the legacy **allow** keys: the same answer as `main`, nothing widened. Never apply a `deactivated_<kind>` key found there.
- **Refuse** every write that would record or change a deny entry on an unmigrated project, naming `spec-kitty upgrade` / `spec-kitty migrate activation-ledger`, with nothing written. Legacy saves never carry deny keys.
- **Give fresh projects the ledger**: a blank project (no activation keys anywhere, no ledger) and `spec-kitty init` on a fresh project. Never create a ledger implicitly on an unmigrated project (see the hole analysis).
- Prove it end to end: SC-001, the init flow, and a subprocess e2e on an unmigrated fixture.

The strict fail-closed read, the full fixture sweep (the canceled WP11–WP13), the
charter.yaml-bootstrap copy removal and the `CharterYaml` activation-field removal are **not** in
this WP. They move to the charter-contract alignment epic (milestone #11)
**(epic child #6535: retire the legacy activation reader)**.

## Context

- Spec: FR-017 (amended), FR-019, FR-020, C-003, SC-001, SC-004 (re-homed here from the canceled sweeps); edge cases "Unmigrated project" and "A fresh project".
- Plan IC-13 (rewritten for Option B); data-model.md §5 (one-mode resolver table) and §6.
- Decision records: `mission_pivot_option_b`, `unmigrated_projects`, `pre_ledger_seam` (amended for reads), `older_cli_downgrade`, `deny_writers`.
- Mission order: WP14 of 15. WP11–WP13 are **canceled**, so this WP depends on WP10. Today every test runs in tolerant mode, except the exact files listed in `SWEPT_PREFIXES`, which run strict test mode.
- Carry-forward (scratchpad `carry-forward.md`):
  - The hooks live in `tests/_support/activation_strict_mode.py`, bound into `tests/conftest.py` by assignment because `test_home_owner_behaviour.py` freezes conftest's defs. Delete that module, and include it in the no-env-var gate scope.
  - Rename `testlegacy_save_accepts_deny_follows_the_mode` (`tests/kernel/test_activation_ledger_store.py:~386`) when you rewrite that file.
  - Render the preflight error body (WP06 note): `spec-kitty charter preflight` (`preflight/cli.py`) prints only `preflight aborted: ACTIVE_CHARTER_CONFIG_INVALID`, and `run_preflight_or_abort` (`preflight/hook.py`) lets the error escape unrendered. Render it with `render_pack_config_error`.
  - The WP06 closeout LOWs (T084).
- Shared files (dependency-ordered):
  - `activation_ledger_store.py`, `activation_ledger.py`, `tests/_factories/activation_ledger.py`, `tests/conftest.py` (from WP02);
  - `pack_manager.py`, `charter_yaml_io.py`, `default_charter.py` (from WP03/WP04);
  - `deactivate.py` (from WP04);
  - the named transition tests (from WP02, WP03, WP08, WP09).

## Reduced-flip semantics (binding)

| Ledger file | Upgrade scope | Legacy activation keys | Read | Allow-only write | Deny write |
|---|---|---|---|---|---|
| exists | any | none | ledger | ledger | ledger |
| exists | any | present | ledger; FR-020 warning (the keys are ignored) | ledger | ledger |
| absent | inside | any | legacy (byte-for-byte, shipped migrations) | legacy | refused (no migration writes deny) |
| absent | outside | present (**unmigrated**) | legacy **allow** keys only | legacy target (as `main`) | **refused**, naming `spec-kitty upgrade` / `migrate activation-ledger`; nothing written |
| absent | outside | none (**fresh**) | ledger (`exists=False`) | ledger (created) | ledger (created) |

A **deny write** is any write whose result would contain a `deactivated_<kind>` key, or would
add, remove or change a deny entry. A `deny_change` value that changes nothing is **not** a deny
write. For example, `charter activate directive D`, `--preset X --force` and cascade
`--include-deactivated` on an unmigrated project clear nothing, so they succeed on the legacy
surface. Today's strict `_refuse_legacy_deny` (`pack_manager.py:692-709`) refuses on
`deny_change is not None` alone: change it to refuse only on an actual deny key or deny delta
(hole 1).

### Holes found in the tolerant-read + no-deny-in-legacy-save combination, and their fixes (all binding)

1. **Explicit choices with no deny effect.** Activate, `--force` presets and cascade `--include-deactivated` pass a non-`None` `deny_change` even when they clear nothing. The strict legacy save refuses them today, which would break plain activation on every unmigrated project (a regression vs `main`). Fix: refuse on a deny key or deny delta only (above).
2. **Cascade deactivation must be all-or-nothing.** `_render_cascade_deactivation` unselects children (`record_exclusion=False`) before or beside recording the named id's exclusion. On an unmigrated project the named id's deny write refuses, so children could be unselected while the command fails. Fix: `deactivate.py` checks "unmigrated" **before any write and before the required-floor read**, then refuses the whole command, naming the remedy. A test pins byte-identical files (NFR-001).
3. **Never create a ledger on an unmigrated project implicitly.** A new `activation.yaml` beside legacy keys turns those keys into ignored stray keys. Every kind would then fall back to "absent = all" (**widening**). This covers `spec-kitty init` re-run in an existing project, the provisioning finalizer and any first write. Fix: a writer may create the ledger only when the resolver says **fresh**. An unmigrated project gets its ledger only from `spec-kitty upgrade` or `spec-kitty migrate activation-ledger` (FR-021). `init` "writes the ledger" for **fresh** projects, and follows the resolver otherwise.
4. **The charter.yaml bootstrap copy must stay.** On an unmigrated project with no `charter:` pointer, `charter generate` bootstraps `charter.yaml`, mints the pointer, and copies the legacy allow keys from `config.yaml` (`compiler._bootstrap_charter_yaml` → `document.update(activation)`, `compiler.py:889-933`). Legacy reads follow the pointer. Deleting the copy (as the full-flip plan did) would silently drop every allow key, widening to "absent = all". Fix: keep the copy, **allow keys only** (never deny keys), and **only when the activation source is LEGACY**. With a ledger, or on a fresh project, it copies nothing, so it never duplicates the ledger's keys. This is the amended C-003 (copy scoped to the unmigrated source). Its removal is the epic's (#6535).
5. **The `CharterYaml` activation fields must stay.** Unmigrated projects still read activation from `charter.yaml`, and the model is `extra="forbid"`, so removing the ten fields would make every unmigrated `charter.yaml` invalid. Keep them; their removal is the epic's.
6. **A legacy `deactivated_<kind>` key is never applied.** Such a key can only come from a hand edit or a pre-release build of this Mission. The LEGACY projection drops it from the read and reports it: the FR-020 warning path, doctor `LEGACY_DENY_KEY` (WP09, error), and the rc8 migration and `migrate activation-ledger` refuse it, naming the key and file (WP08). The remedy text: remove the key by hand, then migrate.

## Branch Strategy

- **Strategy**: single_branch; sequential in the repository root checkout on `core-align-3-persistent-deactivation`.
- **Planning base branch**: `core-align-3-persistent-deactivation`
- **Merge target branch**: `core-align-3-persistent-deactivation`

```bash
spec-kitty agent action implement WP14 --agent claude --mission persistent-deactivation-ledger-01M59YAA
```

## ATDD (red first)

T078 writes the acceptance tests and the no-env-var gate, and records the red set. The red
commit runs **before** T079 deletes the transition machinery: append the new files to
`SWEPT_PREFIXES` as usual (strict test mode). The gate (scanning `src/` **and** `tests/`) and the
hole-1 to hole-3 assertions must be red on that commit. Record the red summary.

## Subtasks

**First step, before T078: precondition (H1).** Refuse to start unless
`.kittify/charter/activation.yaml` exists in this repository (WP08 T052 dogfooded it with
`spec-kitty migrate activation-ledger`). If it is missing, stop and hand back to the
orchestrator. Do not run `spec-kitty upgrade`.

### Subtask T078: Failing acceptance tests and the no-env-var gate

**Steps**:
1. `tests/acceptance/test_persistent_deactivation.py` (SC-001), in a tmp project created by `spec-kitty init` (fresh, so it gets the ledger):
   - **positive control**: D is served by `charter context --action implement`;
   - `charter deactivate directive D` with `activated_directives` absent;
   - then the interview promotion, `charter activate --preset default` (no `--force`), a synthesis promotion, mission-type seeding and a full `spec-kitty upgrade`;
   - after each step D is absent from the context and the effective set, and `deactivated_directives` still lists D;
   - `charter activate directive D` serves D again, with the allow list still absent.
2. `tests/acceptance/test_init_ledger_flow.py` (FR-019): `init` → `charter context` → `agent mission create` → `spec-kitty upgrade` changes no file.
   - `activation.yaml` exists, and `config.yaml` / `charter.yaml` carry no activation key.
   - On a project with no migration ledger, `upgrade --dry-run` may still list `4.0.0rc8_activation_ledger` as selected-but-not-needed (`detect()` False; the runner records `skipped`). Assert "nothing moved and no file changed", not "not selected" (carry-forward M1).
3. `tests/acceptance/test_unmigrated_cli_still_runs.py`: an unmigrated fixture (legacy keys in the pointer `charter.yaml` and in `config.yaml`, no ledger), through **real subprocesses** (`.venv/bin/spec-kitty`, full CLI startup):
   - `--version` exits 0;
   - `doctor charter-packs --json` → parseable JSON with an `ACTIVATION_UNMIGRATED` warning (WP09), healthy otherwise;
   - `migrate ledger --json` lists `4.0.0rc8_activation_ledger` pending;
   - `charter context --action implement` succeeds and equals the same command's output on `main` for this fixture (golden captured on the base);
   - `charter activate directive A` succeeds and writes allow keys only to the legacy surface (hole 1), with no `activation.yaml` created (hole 3);
   - `charter activate --preset default --force` succeeds, with no deny key written (hole 1);
   - `charter deactivate directive D` and a cascade deactivation exit 1, naming `spec-kitty upgrade`, with all three files byte-identical (hole 2, NFR-001);
   - `spec-kitty init` re-run on the fixture creates no `activation.yaml` (hole 3), **and** `migrate ledger --json` still lists rc8 pending, so `spec-kitty upgrade` then moves the keys (pass-8 M4; the init-seed fix is WP08 T049);
   - `charter activate mission-type software-dev --cascade all --include-deactivated` succeeds on the legacy surface with no deny key written (hole 1, pass-8 L1);
   - `charter generate` on a no-pointer variant keeps the allow keys in the bootstrapped `charter.yaml` (hole 4). After `migrate activation-ledger`, a `charter generate` that re-bootstraps copies **no** activation key into `charter.yaml` (M1, C-003);
   - hole 5 (pass-8 L1): an unmigrated `charter.yaml` holding all ten activation fields still loads through `CharterYaml` (`extra="forbid"`) without a validation error;
   - hole 2 ordering (pass-8 L1): an unmigrated fixture whose declared org pack is unreadable → `charter deactivate` refuses with the **unmigrated** message, not the floor error, proving the check runs before the floor read;
   - **positive control**: `migrate activation-ledger`, then `charter deactivate directive D` succeeds and the ledger records D.
4. Hole 6: a legacy fixture holding `deactivated_directives: [D]` in `charter.yaml` → D is still served (never applied), one warning names the key, and `migrate activation-ledger` refuses naming it.
5. `tests/architectural/test_no_activation_strict_env.py`:
   - no file under `src/` or `tests/` mentions `SPEC_KITTY_ACTIVATION_STRICT`, `activation_strict`, `legacy_save_accepts_deny`, `SWEPT_PREFIXES` or `activation_strict_mode`;
   - the gate file excludes itself;
   - a self-mutation case proves non-vacuity.

### Subtask T079: Delete the transition machinery

**Steps**:
1. `kernel/activation_ledger_store.py`:
   - delete `_STRICT_ENV`, `activation_strict()`, `activation_strict_test()`, `_tolerant`, and the `UNMIGRATED` refusal branch;
   - `resolve_activation_source` implements the one-mode table above. The unmigrated case is `LEGACY` with `unmigrated=True` (and its keys) on the result, so writers and doctor can tell it apart. The kernel still raises nothing activation-domain.
2. `activation_ledger.py`:
   - delete `legacy_save_accepts_deny`;
   - the `test`-mode raise in `report_stray_legacy_keys` goes, while the production FR-020 warning stays;
   - the LEGACY projection drops `deactivated_*` keys and reports them (hole 6).
3. `pack_manager.py` / `charter_yaml_io.py`:
   - delete every `# D0 transition: WP14 removes` branch;
   - legacy saves never write a deny key;
   - `_refuse_legacy_deny` refuses on a deny key or deny delta only (hole 1), with text naming `spec-kitty upgrade` and `spec-kitty migrate activation-ledger`;
   - creating the ledger file is allowed only when the resolver says **fresh** (hole 3).
4. `tests/conftest.py` and `tests/_support/activation_strict_mode.py`: delete `SWEPT_PREFIXES`, both hooks and the module.
5. `tests/_factories/activation_ledger.py`: drop anything that only served the transition, and keep `legacy_seed` for class-A tests.
6. `grep -rn "SPEC_KITTY_ACTIVATION_STRICT\|SWEPT_PREFIXES\|D0 transition\|activation_strict" src tests` returns nothing outside the gate file.

### Subtask T080: Unmigrated deny writes refuse, all-or-nothing

**Steps**:
1. In `deactivate.py`, before any write and before the required-floor read, ask the seam whether the project is unmigrated. If it is, refuse the direct path and the cascade path alike: exit 1, render the message with `render_pack_config_error`, write nothing (hole 2).
2. Promotion writers (interview, org-required, synthesis, seeding) on an unmigrated project never write deny keys (they never did). Check them: they keep their legacy target.
3. Unit-test the predicate and both CLI paths.

### Subtask T081: Fresh projects and `init` get the ledger

**Steps**:
1. `default_charter.provision_default_mission_type_activations`: write the ledger when the resolver says **fresh**; on an unmigrated project, keep the legacy target (hole 3).
2. The upgrade finalizer's provisioning (WP08 T049) runs after the migrations and resolves outside the legacy scope, so a migrated project, or a keyless pre-ledger one (pass-8 M3), is on the ledger. Confirm both under the one-mode resolver.
3. Keep `compiler._bootstrap_charter_yaml`'s allow-key copy and the `CharterYaml` activation fields (holes 4 and 5). Edit only `_bootstrap_charter_yaml` in `compiler.py`; this is a dependency-ordered share with WP05, which is approved.
   - The copy runs **only when the resolved source is LEGACY**, and copies allow keys only.
   - With a ledger it copies **nothing**, even when stray `config.yaml` activation keys exist (pass-9 M2, C-003).
   - Red-first tests:
     - a ledger, stray `config.yaml` activation keys and no `charter.yaml` → bootstrap → the new `charter.yaml` has no activation key;
     - the copy never carries a deny key;
     - positive control: on an unmigrated no-pointer project the allow keys are copied.

### Subtask T082: Rewrite the transition-pinning tests and re-seed what turned red (bounded, red-first)

**Steps**:
1. Rewrite the tests that pinned the transition, with these post-flip expectations:
   - `tests/kernel/test_activation_ledger_store.py`: the one-mode table rows. Rename `testlegacy_save_accepts_deny_follows_the_mode`, and keep the probe-cache test.
   - `tests/upgrade/test_legacy_activation_scope.py`: in scope → LEGACY; outside the scope on an unmigrated project → LEGACY with `unmigrated=True`.
   - `tests/doctor/test_doctor_activation_ledger.py`: `ACTIVATION_UNMIGRATED` (warning), `LEGACY_KEYS_PRESENT`, `LEGACY_DENY_KEY`.
   - `tests/charter/activation/test_activation_write_target_ledger.py`: the legacy save refuses deny keys, and accepts a `deny_change` with no delta.
   - `tests/specify_cli/cli/commands/test_init_writes_ledger.py`: fresh → ledger; unmigrated → legacy target.
   - the files that WP02–WP10 listed in `SWEPT_PREFIXES`: they ran strict test mode; re-check each one under the one mode.
2. **Bounded re-seed.**
   - Run `make test-fast` and the owning subsystem trees twice: once on the WP10 tip (the base, before T079) and once after T079–T081. Then diff the failure sets.
   - Only tests that are red after and green before are this WP's. Expect `charter deactivate` on legacy-keyed fixtures (now refused) and `init`/blank-project post-write assertions (now on the ledger).
   - Re-seed each one: route the seed through `tests/_factories/activation_ledger.py` (`seed_activation_ledger`), or assert against the ledger. Never weaken the behaviour under test.
   - Record the measured red list and each fix in `traces/approach.md`.
   - If the list exceeds about 60 files, stop and hand back to the orchestrator: the scale belongs in the epic.

### Subtask T083: Subprocess e2e and the preflight error rendering

**Steps**:
1. Make `tests/acceptance/test_unmigrated_cli_still_runs.py` green.
2. Render the activation error body in `charter_runtime/preflight/cli.py` and `preflight/hook.py` (`render_pack_config_error`), instead of the bare `preflight aborted: ACTIVE_CHARTER_CONFIG_INVALID`. Add a malformed-ledger subprocess case.

### Subtask T084: Closeout LOW fold, then full verification

**Steps**:
1. Fold the WP06 LOWs from `carry-forward.md`, since this is the last code WP:
   - pin that `gate_bindings` and the mission-step executor still return `None` on a non-activation exception;
   - the invocation registry's `resolve` / `resolve_local` refuse a denied profile;
   - `_synthesis._catalog_is_established`: drop the `charter_yaml_path` it immediately `del`s.
2. Run the Validation commands below.
3. Diff `spec-kitty charter context --action implement` on this repository before and after the WP: it must be identical.
4. The timing tests (reworked by WP09 into ratio-vs-base form) must show no regression against the base (NFR-003, R6). The absolute 2 s budget is pre-existing on `main` (#6506): classify any absolute-budget red there and never retry it to green.

## Validation / targeted test surface

```bash
cd /home/user/spec-kitty
.venv/bin/python -m pytest -q tests/acceptance/test_persistent_deactivation.py tests/acceptance/test_init_ledger_flow.py tests/acceptance/test_unmigrated_cli_still_runs.py tests/architectural/test_no_activation_strict_env.py
.venv/bin/python -m pytest -q tests/kernel/test_activation_ledger_store.py tests/upgrade/test_legacy_activation_scope.py tests/doctor/test_doctor_activation_ledger.py tests/charter/activation/test_activation_write_target_ledger.py tests/specify_cli/cli/commands/test_init_writes_ledger.py tests/specify_cli/cli/commands/charter/test_deactivate_records_exclusion.py
.venv/bin/python -m pytest -q -n auto --dist loadfile -m "not timing and not stress" tests/charter tests/charter_offering tests/upgrade tests/specify_cli/upgrade
.venv/bin/python -m pytest -q -n auto --dist loadfile -m "not timing and not stress" <the measured red-then-re-seeded files from T082.2>
.venv/bin/python -m pytest -q -n0 -m timing tests/specify_cli/cli/commands/charter/test_deactivate_cli_timing.py tests/specify_cli/cli/commands/charter/test_context_cli_timing.py tests/specify_cli/cli/commands/charter/test_preset_cli_timing.py
.venv/bin/python -m pytest -q tests/architectural/test_deny_list_survives_upgrade.py tests/architectural/test_no_raw_activation_membership.py tests/architectural/test_no_dead_symbols.py tests/architectural/test_no_dead_modules.py tests/architectural/test_layer_rules.py tests/architectural/test_charter_kind_vocabulary_single_authority.py tests/architectural/test_migration_order_manifest.py tests/architectural/test_charter_path_literal_authority.py
make test-fast
uv run --frozen ruff check <touched files>
uv run --frozen ruff format --check --force-exclude <touched files>
uv run --frozen mypy src/kernel/activation_ledger_store.py src/charter/activation/activation_ledger.py src/charter/activation/pack_manager.py src/charter/activation/charter_yaml_io.py src/specify_cli/provisioning/default_charter.py src/specify_cli/cli/commands/charter/deactivate.py src/specify_cli/charter_runtime/preflight/cli.py src/specify_cli/charter_runtime/preflight/hook.py
```

Never run the bare `tests/architectural/` directory, never `make test-full`, and never a whole
tree you do not own (`NO_FULL_HEAVY_SUITES_IN_MISSION`).

## Standing orders

- Follow python-pedro: complexity ≤ 15, ruff/format(`--force-exclude`)/mypy clean, no suppressions.
- Append dated entries to the Mission's `traces/*.md`: the red list goes in `approach.md`, the hole fixes in `design-decisions.md`.
- Do not edit shipped migrations.

## Definition of Done

- One mode remains, the variable and hooks are gone, and the gate is green.
- Unmigrated reads match `main`, and unmigrated deny writes refuse, all-or-nothing.
- Fresh projects and `init` get the ledger, and no ledger is ever created implicitly on an unmigrated project.
- The bootstrap allow-key copy and the `CharterYaml` fields are kept, never carrying deny keys.
- SC-001, the init flow and the subprocess e2e are green.
- The bounded re-seed is recorded, and every subtask is marked done.

## Risks

- The re-seed set is larger than expected: stop at about 60 files and hand back (epic scale).
- An unmigrated-detection mismatch between the kernel and `deactivate.py`: use the one resolver result, never a second probe.

## Reviewer Guidance

- Walk every row of the reduced-flip table and every hole fix, and find the test for each.
- `grep -rn "SPEC_KITTY_ACTIVATION_STRICT" src tests` returns only the gate file.
- Confirm that `_bootstrap_charter_yaml` still copies allow keys, and that `CharterYaml` still has its fields.
