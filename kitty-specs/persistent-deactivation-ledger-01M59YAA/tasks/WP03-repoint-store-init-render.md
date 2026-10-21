---
work_package_id: WP03
title: Re-pointed store, SPDD resolver, init and rendering writers
dependencies:
- WP02
requirement_refs:
- FR-001
- FR-017
- FR-019
- C-002
- C-003
- NFR-001
planning_base_branch: core-align-3-persistent-deactivation
merge_target_branch: core-align-3-persistent-deactivation
branch_strategy: Planning artifacts for this mission were generated on core-align-3-persistent-deactivation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into core-align-3-persistent-deactivation unless the human explicitly redirects the landing branch.
subtasks:
- T011
- T012
- T013
- T014
- T015
phase: Phase 1 - Foundation
history:
- at: '2026-10-19T12:17:27Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks (split from the old WP02 by the post-tasks squad, D1)
agent_profile: python-pedro
authoritative_surface: src/charter/activation/
create_intent:
- tests/charter/activation/test_activation_write_target_ledger.py
- tests/specify_cli/cli/commands/test_init_writes_ledger.py
execution_mode: code_change
model: ''
owned_files:
- src/charter/activation/pack_context.py
- src/charter/activation/pack_manager.py
- src/charter/activation/consistency_check.py
- src/charter/activation/charter_yaml_io.py
- src/charter/bundle.py
- src/charter/offering/spdd_reasons/activation.py
- src/specify_cli/provisioning/default_charter.py
- src/specify_cli/core/mission_creation_scaffold.py
- src/specify_cli/skills/command_renderer.py
- src/specify_cli/skills/command_installer.py
- src/specify_cli/skills/installer.py
- src/specify_cli/upgrade/assessment.py
- tests/charter/activation/test_activation_write_target_ledger.py
- tests/charter/test_spdd_reasons_activation_parity.py
- tests/charter/test_mission_type_activations_seed_read_parity.py
- tests/specify_cli/cli/commands/test_init_writes_ledger.py
- tests/specify_cli/cli/commands/test_init_provisioning.py
- tests/specify_cli/skills/test_command_renderer.py
- tests/conftest.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Re-pointed store, SPDD resolver, init and rendering writers

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro` (`packs/built-in/agent_profiles/python-pedro.agent.yaml`)
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

- Check `review_ref` in the event log; address every item; record with `spec-kitty agent tasks add-history WP03 --note "..."`.

---

## Objective

Route every existing activation reader and writer through WP02's resolver and seam.

- **Tolerant mode** (the default): behaviour is byte-identical to today on legacy fixtures. The
  one exception is that the legacy save now **carries `deactivated_<kind>` keys** (D0), so the
  deny semantics of WP04+ work on legacy-shaped fixtures.
- **Strict mode** (`SPEC_KITTY_ACTIVATION_STRICT=1`): unmigrated projects fail closed,
  `spec-kitty init` writes the ledger, and legacy saves refuse deny keys (C-003).

## Context

- Plan IC-02 (re-pointing) and IC-03 (writers); data-model.md §5; research.md D-02, D-19.
- Builds on WP02:
  - `kernel.activation_ledger_store.resolve_activation_source`;
  - `activation_ledger.load_activation_ledger`, `prepare_ledger_write`, `legacy_save_accepts_deny()`;
  - `ActiveCharterConfigError`, now defined in the seam.
- The **m6** upgrade-finalizer ordering item moved to **WP08**, the migration WP, which owns `cli/commands/upgrade.py`. Do not touch `upgrade.py` here.
- Golden error texts stay byte-identical. The kernel returns `pointer_exists`, and each caller raises its own error:
  - `pack_context.py:570` `_config_error` (now living in the seam);
  - `pack_manager.py:658`;
  - SPDD `_SpddActivationConfigError` (`spdd_reasons/activation.py:147`).
- Shared files (dependency-ordered):
  - `pack_context.py`, `pack_manager.py` (from WP02, then WP04 and WP05);
  - `charter_yaml_io.py`, `default_charter.py` (then WP14);
  - `consistency_check.py` (then WP05);
  - `bundle.py` (then WP09);
  - the SPDD probe (then WP06).

  Touch only the functions named here.
- Mission order: WP03 of 15, strictly linear.

## Branch Strategy

- **Strategy**: single_branch; sequential in the repository root checkout on `core-align-3-persistent-deactivation`.
- **Planning base branch**: `core-align-3-persistent-deactivation`
- **Merge target branch**: `core-align-3-persistent-deactivation`

```bash
spec-kitty agent action implement WP03 --agent claude --mission persistent-deactivation-ledger-01M59YAA
```

## ATDD (red first)

T011 writes failing acceptance tests for:
- the write target in both modes;
- the strict legacy save (inside the scope) refusing deny keys. The tolerant deny-carrying save gets no new test (test-mode rules);
- strict-mode `init` writing the ledger (FR-019);
- the strict unmigrated fail-closed refusal through `charter context`, with a valid-ledger positive control on the same fixture.

Commit them before implementation and record the red summary.

## Subtasks

### Subtask T011: Failing acceptance tests

**Steps**:
1. `tests/charter/activation/test_activation_write_target_ledger.py`:
   - **ledger present** (either mode): `resolve_activation_write_target` returns the ledger path and a save that accepts the positional `(path, data)` call `commit_plan` makes, plus a `deny_change=` keyword;
   - tolerant behaviour (today's triple; the deny-carrying legacy save) gets **no new test**. It is pinned by the existing `tests/charter/test_pack_manager.py`, `tests/charter/test_activation_engine_charter_yaml.py` and `tests/charter/test_activate_restamps_bundle_hash.py`, which must stay green unchanged;
   - **strict, in scope, legacy**: a save with deny keys refuses (C-003);
   - **dangling pointer**: the `pack_manager.py:658` text is unchanged.
2. `tests/specify_cli/cli/commands/test_init_writes_ledger.py`:
   - (strict through `SWEPT_PREFIXES`) `spec-kitty init` writes `mission_type_activations` to `.kittify/charter/activation.yaml`, writes no activation key to `config.yaml`, and `rendering_inputs()[-1]` is the ledger path;
   - tolerant `init` gets no new test: the existing `tests/specify_cli/cli/commands/test_init_provisioning.py` must stay green unchanged.
3. Strict refusal (the new file runs strict through `SWEPT_PREFIXES`): a legacy-keyed fixture with no ledger:
   - `charter context --action implement` exits non-zero, naming `spec-kitty upgrade`;
   - the **same fixture** after `seed_activation_ledger` succeeds (F15 positive control);
   - all three files stay byte-identical on the refusal (NFR-001).
4. SPDD: in `tests/charter/test_spdd_reasons_activation_parity.py`, the probe resolves through the kernel. Pin the dangling-pointer text.

### Subtask T012: Re-point the store

**Steps**:
1. `pack_context`:
   - `_load_charter_activation_source` (`pack_context.py:556-581`) returns `load_activation_ledger(...).raw()` (projected);
   - `resolve_charter_yaml_pointer` (`:306`) becomes a thin call into the kernel pointer helper; it is kept for its importers.
2. `pack_manager.resolve_activation_write_target` (`:629-671`) keeps its `(path, data, save)` triple, which the shipped rc35 migration consumes (D-02):
   - **LEDGER** → `_save_ledger(path, data, *, deny_change=None)`;
   - **LEGACY** → today's code, moved verbatim. `_save_charter_yaml_activation` and the `YAML_KEY_MAP` key filtering **carry deny keys** while `legacy_save_accepts_deny()` holds, and refuse them otherwise;
   - **UNMIGRATED** → `ActiveCharterConfigError` (naming `spec-kitty upgrade`).
3. `prepare_activation_write` (`:674-705`) gains `deny_change`.
4. `list_activated` (`:915-946`) reads `load_activation_ledger`.
5. `consistency_check._load_raw_activation_source` / `_load_config_yaml_mapping` (`consistency_check.py:340-394`) are replaced by the seam's projected mapping.
6. `charter_yaml_io`: whatever the deny-carrying legacy save needs; `_activation_keys` (`:480`) learns the deny keys under tolerant mode.
7. `charter/bundle.py`: re-export `ACTIVATION_YAML` (from the kernel constant) beside `CHARTER_YAML` (`bundle.py:52`).

### Subtask T013: SPDD probe through the kernel resolver

**Steps**:
- `src/charter/offering/spdd_reasons/activation.py`: replace `_resolve_charter_pointer` and the pointer branch (`:141-147, 171-184`) with `kernel.activation_ledger_store.resolve_activation_source` + `read_activation_ledger_raw`.
- Keep the early `False` for a missing `config.yaml` (`:128-138`), and keep `_SpddActivationConfigError` texts.
- Add no deny subtraction yet; that is WP06.
- Do not import `charter.activation` here.

### Subtask T014: Init, scaffold message, rendering identity, upgrade repairs

**Steps**:
1. `provision_default_mission_type_activations` (`default_charter.py:47-89`, called at `cli/commands/init.py:1456`):
   - **strict mode**: write the ledger through `charter.activation.compiler.provision_mission_type_activations` / `prepare_activation_write` (existing baseline row);
   - **tolerant mode**: keep today's provisioning (D0).
2. `core/mission_creation_scaffold.py:147`: the message names `.kittify/charter/activation.yaml`.
3. `skills/command_renderer.rendering_inputs` (`:517-542`) appends the ledger path last when the resolver says `LEDGER`. Follow through in:
   - `validate_mission_provisioning` (`:545-565`);
   - `upgrade/assessment.py:127` (the comparison only; the m6 re-prepare ordering is WP08);
   - `skills/command_installer.py:887-895`;
   - `skills/installer.py:375-399`.

### Subtask T015: Blast-radius regression on the files that call the re-pointed functions (F3, F10; C1: no heavy sweeps)

**Steps**:
1. Derive the list:
   ```bash
   grep -rlE "resolve_activation_write_target|prepare_activation_write|list_activated|_load_charter_activation_source|resolve_charter_yaml_pointer|provision_default_mission_type_activations|rendering_inputs|validate_mission_provisioning" tests --include='*.py' | sort
   ```
   Record the list in `traces/approach.md`.
2. Run exactly those files, plus the named F10 files below. Tolerant mode must keep them green unchanged.
3. Do not run whole trees such as `tests/integration/` or `tests/core/`: the sweep WPs own them (charter rule `NO_FULL_HEAVY_SUITES_IN_MISSION`).

## Validation / targeted test surface

```bash
cd /home/user/spec-kitty
.venv/bin/python -m pytest -q tests/charter/activation/test_activation_write_target_ledger.py tests/specify_cli/cli/commands/test_init_writes_ledger.py tests/charter/test_spdd_reasons_activation_parity.py tests/charter/test_mission_type_activations_seed_read_parity.py
.venv/bin/python -m pytest -q -n auto --dist loadfile -m "not timing and not stress" tests/charter tests/charter_offering tests/kernel
.venv/bin/python -m pytest -q tests/specify_cli/skills/test_command_renderer.py tests/specify_cli/tool_surface/providers/test_command_skills.py tests/specify_cli/cli/commands/test_init_provisioning.py tests/specify_cli/upgrade/test_upgrade_provisions_mission_type_activations.py
.venv/bin/python -m pytest -q -n auto --dist loadfile -m "not timing and not stress" $(grep -rlE "resolve_activation_write_target|prepare_activation_write|list_activated|_load_charter_activation_source|resolve_charter_yaml_pointer|provision_default_mission_type_activations|rendering_inputs|validate_mission_provisioning" tests --include='*.py' | sort)
.venv/bin/python -m pytest -q tests/architectural/test_layer_rules.py tests/architectural/test_charter_offering_does_not_import_activation.py tests/architectural/test_runtime_charter_activation_boundary.py tests/architectural/test_org_activation_seam.py tests/architectural/test_no_dead_symbols.py tests/architectural/test_charter_path_literal_authority.py tests/architectural/test_charter_kind_vocabulary_single_authority.py
make test-fast
uv run --frozen ruff check <touched files>
uv run --frozen ruff format --check --force-exclude <touched files>
uv run --frozen mypy <touched src files>
```

## Standing orders

- Follow python-pedro: complexity ≤ 15, ruff/format(`--force-exclude`)/mypy clean, no suppressions.
- Append dated entries to the Mission's `traces/*.md`.
- Do not edit shipped migrations. The rc35 consumption of the write-target triple must keep working unchanged.

## Definition of Done

- Red-first tests are committed, and green now.
- Tolerant mode is byte-identical on legacy fixtures, except that legacy saves carry deny keys.
- Strict mode fails closed, refuses legacy deny writes, and init writes the ledger.
- The grep-derived regression list is recorded and green.
- Gates are green, and every subtask is marked done.

## Risks

- `_save_ledger` must accept the positional call shape `commit_plan` uses today.
- Deny keys in tolerant legacy saves are temporary. Mark every such branch `# D0 transition: WP14 removes`.

## Reviewer Guidance

- Diff the golden error texts.
- Run one legacy fixture in both modes.
- Confirm `upgrade.py` is untouched.

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
  WP11 step-0 helpers or `tests/_factories/activation_ledger.py`, which work in both modes.
- **No test file references `SPEC_KITTY_ACTIVATION_STRICT`.** That covers `setenv`, `delenv`
  and string mentions. There are two exceptions: the kernel resolver test
  `tests/kernel/test_activation_ledger_store.py` (WP02 creates it, WP14 rewrites it), and the
  swept-prefix fixture in `tests/conftest.py` itself (WP02 creates it, WP14 deletes it).
- **No new tolerant-mode-only test.** Tolerant behaviour is pinned only by the existing tests,
  which stay unchanged until their sweep WP, and by the kernel resolver test. An existing test
  file this WP modifies must stay correct in tolerant mode. Tests for new behaviour go in new,
  ledger-seeded files.
