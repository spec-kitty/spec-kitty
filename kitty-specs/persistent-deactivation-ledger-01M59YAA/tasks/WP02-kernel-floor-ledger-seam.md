---
work_package_id: WP02
title: Kernel floor, ledger seam, write guard, test factory
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-002
- FR-014
- FR-017
- FR-020
- C-002
- C-003
- C-004
- NFR-003
- NFR-004
planning_base_branch: core-align-3-persistent-deactivation
merge_target_branch: core-align-3-persistent-deactivation
branch_strategy: Planning artifacts for this mission were generated on core-align-3-persistent-deactivation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into core-align-3-persistent-deactivation unless the human explicitly redirects the landing branch.
subtasks:
- T005
- T006
- T007
- T008
- T009
- T010
phase: Phase 1 - Foundation
history:
- at: '2026-10-19T12:17:27Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks (revised after the post-tasks squad, D0/D1/D2)
agent_profile: python-pedro
authoritative_surface: src/charter/activation/
create_intent:
- src/kernel/activation_ledger_store.py
- src/charter/activation/activation_ledger.py
- tests/_factories/activation_ledger.py
- tests/kernel/test_activation_ledger_store.py
- tests/charter/activation/test_activation_ledger.py
execution_mode: code_change
model: ''
owned_files:
- src/kernel/activation_ledger_store.py
- src/kernel/README.md
- src/charter/activation/activation_ledger.py
- src/charter/activation/pack_context.py
- src/charter/activation/pack_manager.py
- src/charter/activation/api.py
- tests/_factories/activation_ledger.py
- tests/conftest.py
- tests/kernel/test_activation_ledger_store.py
- tests/charter/activation/test_activation_ledger.py
- tests/charter/test_activation_vocabulary_setequal.py
- tests/architectural/test_charter_activation_api_reexport.py
- tests/architectural/test_charter_path_literal_authority.py
- tests/architectural/charter_path_literal_allowlist.yaml
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Kernel floor, ledger seam, write guard, test factory

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro` (`packs/built-in/agent_profiles/python-pedro.agent.yaml`)
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

- Check `review_ref` in the event log (`spec-kitty agent tasks status --mission persistent-deactivation-ledger-01M59YAA`). Address every item; record each with `spec-kitty agent tasks add-history WP02 --note "..."`.

---

## Objective

Create the floor every later WP builds on:

- **kernel** `kernel.activation_ledger_store`: the path, the raw read, the one source resolver
  with its two modes (tolerant / strict, D0), and the upgrade-only legacy scope;
- **seam** `charter.activation.activation_ledger`: vocabulary, typed load, write with the
  `deny_change` guard;
- **tests**: the test factory and an empty swept-prefix red-signal fixture.

Nothing outside the new modules changes behaviour. Re-pointing the existing readers and writers
is **WP03**.

## Context

- Plan IC-01 and IC-02 (as revised by D0); data-model.md §1, §5 (tolerant/strict tables), §6;
  research.md D-01, D-04, D-15 (revised), D-16, D-22.
- ADR: `docs/adr/4.x/2026-10-19-1-activation-ledger-persists-deactivation.md` (WP01).
- Mission order: this is WP02 of 15 (WP01 → … → WP15, strictly linear). WP03 re-points the
  store. WP04 adds the required floor and the planners. WP05 adds `resolve_deny`. WP08 adds the
  migration. WP11–WP13 run the fixture sweep. WP14 makes strict mode unconditional.
- **Transition model (D0, binding)**: `activation_strict()` reads `SPEC_KITTY_ACTIVATION_STRICT`:
  - unset → tolerant (today's storage behaviour, the default);
  - `"1"` → strict;
  - `"test"` → strict, and stray legacy keys beside a ledger raise.

  The variable never ships: WP14 deletes it.
- **Import direction (F20, binding), cycle-free**:
  `kernel.activation_ledger_store` ← `charter.activation.activation_ledger` ← `pack_context` ← `pack_manager`.
  - `activation_ledger` imports only `kernel`, `charter.offering.artifact_kinds` and `charter.activation.charter_yaml_io`, at module level.
  - `ActiveCharterConfigError` **moves** from `pack_context.py:63` into `activation_ledger.py`. `pack_context` imports it from there, so `from charter.activation.pack_context import ActiveCharterConfigError` keeps resolving for its 26 importers. That is an ordinary import, not an alias shim.
  - `activation_ledger` never imports `pack_context` or `pack_manager`.
  - `charter_yaml_io`'s existing lazy import of `ACTIVATION_YAML_KEYS` (`charter_yaml_io.py:494`) stays lazy.
- **The kernel never raises an activation-domain error (D2).** It returns the pointer path, `pointer_exists`, the raw data and `source` (`LEDGER | LEGACY | UNMIGRATED`). Callers keep their golden error texts, all byte-identical:
  - `pack_context.py:570` `_config_error(".kittify/config.yaml 'charter:' pointer names …, which does not exist.")`;
  - `pack_manager.py:658`;
  - the SPDD probe's `_SpddActivationConfigError` (`spdd_reasons/activation.py:147`).

  The only kernel raise is `ActivationLedgerFormatError`, from the raw read.
- Layer rules (C-002):
  - `kernel` imports nothing from `charter` or `specify_cli`;
  - `charter.offering` never imports `charter.activation`;
  - `specify_cli` reaches activation through `charter.activation.api` or an existing baseline row, and the baseline does not grow.
- Kind vocabulary single authority (C-004): every key set derives from `ArtifactKind`.

## Branch Strategy

- **Strategy**: single_branch; sequential in the repository root checkout on `core-align-3-persistent-deactivation`.
- **Planning base branch**: `core-align-3-persistent-deactivation`
- **Merge target branch**: `core-align-3-persistent-deactivation`

```bash
spec-kitty agent action implement WP02 --agent claude --mission persistent-deactivation-ledger-01M59YAA
```

## ATDD (red first)

T005 writes acceptance tests for:
- FR-001 and FR-002: vocabulary and typed load;
- FR-014: the structural guard;
- FR-017: every resolver row in data-model.md §5, in both modes. Only the kernel resolver test drives the mode with `monkeypatch.setenv("SPEC_KITTY_ACTIVATION_STRICT", ...)`, as the sole allowed exception;
- FR-020: the stray-key warning.

Commit them before any implementation: `git commit -m "test(WP02): red acceptance for activation ledger seam"`. Paste the red summary into your history note.

## Subtasks

### Subtask T005: Failing acceptance tests

**Steps**:
1. `tests/kernel/test_activation_ledger_store.py`, one parametrised case per row of both data-model.md §5 tables:
   - tolerant:
     - ledger exists → `LEDGER`;
     - ledger + legacy keys → `LEDGER` with `stray_legacy_keys`;
     - no ledger, with or without legacy keys (blank fixture included) → `LEGACY` with the pointer resolved.
   - strict (`"1"`):
     - no ledger, in scope → `LEGACY`;
     - no ledger, outside the scope, legacy keys → `UNMIGRATED`, with the files and keys reported (the kernel does not raise);
     - neither → `LEDGER`, `exists=False`.
   - `"test"`: the kernel still only **reports** `stray_legacy_keys`. It never raises for them; the raise lives in the seam (M1, T005.2).
   - Dangling pointer → `pointer_exists=False`; the kernel does not raise.
   - Raw read:
     - zero-byte ledger → `{}`;
     - non-mapping root or YAML error → `ActivationLedgerFormatError`.
   - Scope:
     - re-entrant;
     - matches a worktree path through `canonical_root`.
   - Probe cache: `(path, mtime, size)`. A changed file is re-probed; an unchanged one is not (spy on the YAML load).
   - **Positive control (F15)**: each refusal and `UNMIGRATED` case has a sibling case on the same fixture plus a ledger that resolves `LEDGER`.
2. `tests/charter/activation/test_activation_ledger.py`:
   - **Vocabulary pin (D2)**:
     - `KIND_ALLOW_KEYS == tuple(f"activated_{k.plural}" for k in ArtifactKind if k.activatable)` (enum order);
     - `NON_KIND_ALLOW_KEYS == ("activated_kinds", "mission_type_activations")`;
     - `DENY_KEYS == tuple(f"deactivated_{k.plural}" for k in ArtifactKind if k.activatable)`;
     - `LEDGER_KEYS == NON_KIND_ALLOW_KEYS + KIND_ALLOW_KEYS + DENY_KEYS`;
     - `pack_manager.ACTIVATION_YAML_KEYS` keeps its **live** order (`("activated_kinds", *YAML_KEY_MAP.values(), *_TOKENLESS_ACTIVATION_KEYS)`, `pack_manager.py:187`). Pin it by tuple equality in `tests/charter/test_activation_vocabulary_setequal.py`, with the literal captured on the base.
   - **L1/L2 on the LEDGER source only (D2)**:
     - an unknown non-deny key → `ActiveCharterConfigError`, nothing written;
     - an unknown `deactivated_newkind` → kept, listed in `unknown_deny_keys`;
     - a non-list value or non-string id → error;
     - `null` → absent;
     - a LEGACY mapping (a `charter.yaml` full of non-activation keys, read inside `legacy_activation_scope` because the file runs strict) is **projected** to the activation key set first and never trips L1.
   - **Guard**:
     - a normalised deny change with `deny_change=None` → `DenyListWriteRefused`, file byte-identical (NFR-001);
     - with `DenyListChoice.DEACTIVATE` → succeeds (positive control);
     - absent, `[]` and `null` compare equal;
     - an empty deny list is removed on write;
     - new keys are appended in `LEDGER_KEYS` order;
     - comments survive.
   - **FR-020 (M2)**: the stray-key report is **data**. `load_activation_ledger` exposes `stray_legacy_keys` as computed by `resolve_activation_source`; nothing catches an exception to obtain it.
     - `report_stray_legacy_keys(stray, *, raise_on_stray)` is the only raising point. Only the ordinary command read path calls it with `raise_on_stray=activation_strict_test()`.
     - Unit-test it directly in both modes (warn / raise).
     - Doctor-style callers read the data and never call the raising path; WP09 relies on this.
     - The production-mode case "two loads emit exactly one warning, and `charter list --json` stdout stays parseable" runs with `SPEC_KITTY_ACTIVATION_STRICT=1`, not `test`. It lives in `tests/kernel/test_activation_ledger_store.py`, the documented exception that may set the variable directly (WP14 rewrites it).
3. Import-direction test: importing `charter.activation.activation_ledger` in a fresh interpreter does not import `charter.activation.pack_context` (`python -c` subprocess checking `sys.modules`).

**Files**: two new test files plus the vocabulary pin (~380 lines). Seed YAML by hand for the red commit; switch to the factory (T009) after.

### Subtask T006: `src/kernel/activation_ledger_store.py`

**Steps**:
1. `ACTIVATION_LEDGER = Path(KITTIFY_DIRNAME, "charter", "activation.yaml")` (`KITTIFY_DIRNAME` from `kernel/charter_pack_paths.py`) and `activation_ledger_path(repo_root)`.
2. `read_activation_ledger_raw(repo_root) -> dict[str, Any] | None`, using the ruamel safe loader as `kernel/yaml_io.py` does:
   - `None` when the file is absent;
   - `{}` for zero bytes;
   - `ActivationLedgerFormatError(KittyInternalConsistencyError)` otherwise on bad content.
3. Scope:
   - `_LEGACY_SCOPE: ContextVar[frozenset[Path]]`;
   - `legacy_activation_scope(repo_root, canonical_root=None)`: a re-entrant context manager recording resolved roots;
   - `in_legacy_activation_scope(repo_root)`.
4. `activation_strict() -> bool` and `activation_strict_test() -> bool`, reading `SPEC_KITTY_ACTIVATION_STRICT` at call time.
   - Put the variable name in one module constant `_STRICT_ENV = "SPEC_KITTY_ACTIVATION_STRICT"`.
   - No new `"activation.yaml"` literal anywhere else (M5): every other module derives the name from `ACTIVATION_LEDGER.name` or the path constant.
   - Add a comment: `# Transition only (D0): WP14 deletes this variable and every reference to it.`
5. Types:
   - `class ActivationSource(StrEnum): LEDGER, LEGACY, UNMIGRATED`;
   - `@dataclass(frozen=True) ResolvedActivationSource(source, pointer: Path | None, pointer_exists: bool, stray_legacy_keys: tuple[tuple[Path, tuple[str, ...]], ...], unmigrated_keys: tuple[tuple[Path, tuple[str, ...]], ...])`.
6. `resolve_legacy_pointer(repo_root) -> tuple[Path | None, bool]`: the string-only `charter:` pointer rule moved from `pack_context.py:306-334`, returning `(path, exists)` without raising.
7. `resolve_activation_source(repo_root, *, legacy_keys)` implements both tables of data-model.md §5.
   - Split it into `_tolerant(...)`, `_strict(...)` and `_legacy_keys_present(...)`, each at complexity ≤ 15.
   - `_legacy_keys_present` caches per process in a dict keyed on `(resolved path, st_mtime_ns, st_size)` (NFR-003).
8. List the module in `src/kernel/README.md`.

### Subtask T007: Seam vocabulary, typed load, error home (`activation_ledger.py`)

**Steps**:
1. Move `ActiveCharterConfigError` (and its `body` handling) here from `pack_context.py:63`, and import it back into `pack_context` (see Context).
2. Define `allow_key(kind)`, `deny_key(kind)`, `KIND_ALLOW_KEYS`, `NON_KIND_ALLOW_KEYS`, `DENY_KEYS` and `LEDGER_KEYS` exactly as pinned in T005.
3. `pack_manager.ACTIVATION_YAML_KEYS` stays defined in `pack_manager` with its live order. Do **not** redefine it from the ledger tuples, because the order differs.
4. `@dataclass(frozen=True) class ActivationLedger` as in data-model.md §1, with `allow_for`, `deny_for` and `raw()`.
5. `load_activation_ledger(repo_root, *, legacy_loader=None) -> ActivationLedger`:
   - **LEDGER**: read raw, then validate L1/L2.
   - **LEGACY**: read the legacy mapping through `charter_yaml_io` (pointer `charter.yaml`, else `config.yaml`), **project it to `LEDGER_KEYS`**, and skip L1.
   - **UNMIGRATED**: raise `ActiveCharterConfigError` with body `Activation keys <keys> in <files> have not been moved to .kittify/charter/activation.yaml. Run spec-kitty upgrade.`
   - A dangling pointer raises `_config_error` with the exact `pack_context.py:570` text. Move that helper here and keep its text byte-identical.
6. FR-020 (M1: the check lives **here, in the seam**):
   - `report_stray_legacy_keys(...)` emits the warning once per process per root, through the warnings path;
   - under `activation_strict_test()` it raises `ActiveCharterConfigError` naming the keys and files instead.
   - The kernel only returns `stray_legacy_keys`.
7. Legacy-key set passed to the kernel: `frozenset(LEDGER_KEYS)`. Deny keys count as legacy keys.

### Subtask T008: Ledger write and the `deny_change` guard

**Steps**:
1. Add `class DenyListChoice(StrEnum)` (`ACTIVATE`, `DEACTIVATE`, `CASCADE_INCLUDE_DEACTIVATED`, `PRESET_FORCE`) and `class DenyListWriteRefused(ActiveCharterConfigError)` with `key`, `added` and `removed`.
2. `prepare_ledger_write(repo_root, values, *, remove=(), deny_change=None) -> PreparedYamlWrite`:
   - build it on `observe_yaml_input`, `prepare_yaml_write` and `apply_yaml_write` (`charter_yaml_io.py:67,142,178`);
   - ruamel round-trip, keys appended in `LEDGER_KEYS` order, empty deny lists dropped;
   - the guard runs before any write;
   - unknown deny keys pass through untouched.
3. Pure helper `_deny_changes(before, after)` with a direct unit test.
4. Add `legacy_save_accepts_deny() -> bool`: `not activation_strict()`. WP03 uses it in the legacy save (tolerant mode accepts deny keys; strict mode refuses them, C-003).

### Subtask T009: Test factory and the empty red-signal fixture

**Steps**:
1. `tests/_factories/activation_ledger.py` provides:
   - `seed_activation_ledger(repo_root, **keys) -> Path`. It writes through `prepare_ledger_write` with `deny_change=DenyListChoice.DEACTIVATE` when deny keys are given.
   - `read_activation_ledger(repo_root) -> dict`.
   - `legacy_seed(repo_root, *, surface="charter_yaml", **keys)`. Class-A tests that need a legacy shape use it explicitly; its docstring tells them to wrap their reads in `legacy_activation_scope`.
2. `tests/conftest.py`:
   - add `SWEPT_PREFIXES: tuple[str, ...] = ()`, with a comment: `# D0 red signal: every code WP (WP02–WP13) appends the exact path of each new test file, and the sweep WPs WP11–WP13 append their trees; WP14 deletes this block.`;
   - add a `pytest_runtest_setup(item)` hookimpl (`@pytest.hookimpl(tryfirst=True)`). It sets `os.environ["SPEC_KITTY_ACTIVATION_STRICT"] = "test"` when the item's file path (relative to the repository root) starts with any entry of `SWEPT_PREFIXES`, and clears the variable otherwise. It runs **before** any fixture of the item, so function- and module-scoped seeding fixtures see the item's mode (M1). A session fixture is set up once, in its first user's mode, so session-scoped seeders must be mode-independent (L1). A matching `pytest_runtest_teardown(item)` restores the previous value. Test them with `pytester`, including a module-scoped fixture that observes the mode.
   - There is no opt-out flag (`LEGACY_ACTIVATION_FIXTURE` is forbidden).
3. Unit-test the prefix matching and the factory briefly in `tests/charter/activation/test_activation_ledger.py`.

### Subtask T010: API exports, path-literal gate, cleanup

**Steps**:
1. Export on `charter.activation.api` only what later specify_cli consumers need now: `DenyListChoice`, `ActivationLedger`, `load_activation_ledger`, `DenyListWriteRefused`. Update `tests/architectural/test_charter_activation_api_reexport.py`. Add `DenyListChoice` to `pack_manager.__all__`.
2. **Path-literal gate (D2)**: `test_charter_path_literal_authority.py` does not cover the ledger filename today. Extend it so `"activation.yaml"` may be spelled only in `src/kernel/activation_ledger_store.py`, with any legitimate exception added to `tests/architectural/charter_path_literal_allowlist.yaml` with its rationale. Add a self-mutation case.
3. Fix dead-symbol findings: every new symbol needs a cross-module importer. If a symbol has no consumer until WP03, keep it private or add its consumer in this WP. Never allowlist it.

## Validation / targeted test surface

```bash
cd /home/user/spec-kitty
.venv/bin/python -m pytest -q tests/kernel/test_activation_ledger_store.py tests/charter/activation/test_activation_ledger.py tests/charter/test_activation_vocabulary_setequal.py
.venv/bin/python -m pytest -q -n auto --dist loadfile -m "not timing and not stress" tests/kernel tests/charter tests/charter_offering
.venv/bin/python -m pytest -q tests/architectural/test_layer_rules.py tests/architectural/test_charter_offering_does_not_import_activation.py tests/architectural/test_charter_kind_vocabulary_single_authority.py tests/architectural/test_kind_table_derivation.py tests/architectural/test_runtime_charter_activation_boundary.py tests/architectural/test_charter_activation_api_reexport.py tests/architectural/test_no_dead_symbols.py tests/architectural/test_no_dead_modules.py tests/architectural/test_charter_path_literal_authority.py
make test-fast
uv run --frozen ruff check <touched files>
uv run --frozen ruff format --check --force-exclude <touched files>
uv run --frozen mypy src/kernel/activation_ledger_store.py src/charter/activation/activation_ledger.py src/charter/activation/pack_context.py src/charter/activation/pack_manager.py src/charter/activation/api.py tests/_factories/activation_ledger.py
```

Do not run the bare `tests/architectural/` directory or `make test-full`. Record commands and counts.

## Standing orders

- Follow python-pedro.
- Keep complexity ≤ 15 per function (ruff C901 / Sonar S3776).
- No blanket `# noqa` or `# type: ignore`.
- A literal repeated three or more times becomes a constant.
- Append dated entries to `kitty-specs/persistent-deactivation-ledger-01M59YAA/traces/approach.md`, `design-decisions.md` (the error-home move) and `tooling-friction.md`.
- Do not edit shipped migrations (C-001).

## Definition of Done

- The T005 tests were committed red first and are now green.
- Nothing outside the new modules changed behaviour.
- `activation_ledger` does not import `pack_context`.
- Both resolver modes match data-model.md §5.
- The factory exists, and the swept-prefix fixture exists with an empty list.
- The gates are green, and ruff, format and mypy are clean.
- Every subtask is marked done with `spec-kitty agent tasks mark-status ... --status done`.

## Risks

- Moving `ActiveCharterConfigError` can break `isinstance` checks or pickling. Keep the same class object, imported back.
- Env-var reads happen at call time. Never cache `activation_strict()` at import.

## Reviewer Guidance

- Check that the kernel raises nothing but `ActivationLedgerFormatError`.
- Check that L1 never fires on a LEGACY mapping.
- Check that the import-direction test runs in a fresh interpreter.

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
