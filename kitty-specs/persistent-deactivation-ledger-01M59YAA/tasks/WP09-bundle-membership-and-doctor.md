---
work_package_id: WP09
title: Bundle membership and doctor
dependencies:
- WP08
requirement_refs:
- FR-005
- FR-018
- FR-023
- NFR-003
planning_base_branch: core-align-3-persistent-deactivation
merge_target_branch: core-align-3-persistent-deactivation
branch_strategy: Planning artifacts for this mission were generated on core-align-3-persistent-deactivation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into core-align-3-persistent-deactivation unless the human explicitly redirects the landing branch.
subtasks:
- T053
- T054
- T055
- T056
- T057
- T058
phase: Phase 6 - Bundle identity and diagnostics
history:
- at: '2026-10-19T12:17:27Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/
create_intent:
- src/charter/activation/activation_ledger.py
- tests/charter/test_bundle_optional_ledger_hash.py
- tests/doctor/test_doctor_activation_ledger.py
- tests/specify_cli/cli/commands/charter/test_list_required_omitted.py
execution_mode: code_change
model: ''
owned_files:
- src/charter/bundle.py
- src/specify_cli/cli/commands/charter_bundle.py
- src/specify_cli/cli/commands/charter/generate.py
- src/specify_cli/charter_runtime/freshness/computer.py
- src/specify_cli/state/contract.py
- src/specify_cli/cli/commands/_charter_pack_collect.py
- src/specify_cli/cli/commands/doctor.py
- src/charter/activation/activation_ledger.py
- src/charter/activation/api.py
- tests/architectural/test_charter_activation_api_reexport.py
- tests/architectural/charter_path_literal_allowlist.yaml
- tests/charter/test_bundle_manifest_model.py
- tests/charter/test_bundle_optional_ledger_hash.py
- tests/specify_cli/charter_freshness/test_computer.py
- tests/doctor/test_doctor_activation_ledger.py
- .kittify/charter/synthesis-manifest.yaml
- tests/conftest.py
- src/specify_cli/cli/commands/charter/list_cmd.py
- tests/specify_cli/cli/commands/charter/test_list_required_omitted.py
- tests/specify_cli/cli/commands/charter/test_deactivate_cli_timing.py
- tests/specify_cli/cli/commands/charter/test_context_cli_timing.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP09 – Bundle membership and doctor

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro` (`packs/built-in/agent_profiles/python-pedro.agent.yaml`)
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

- Check `review_ref` in the event log; address every item; record with `spec-kitty agent tasks add-history WP09 --note "..."`.

---

## Objective

Make `activation.yaml` an optional tracked member of the charter bundle and an optional member
of its content hash (an out-of-band edit is detected; projects without a ledger keep their
hash), and make `spec-kitty doctor charter-packs` report activation drift: errors for an
unreadable store and for legacy keys beside a ledger, warnings for stale or odd deny entries.

## Context

- Plan IC-09; data-model.md §9 (finding codes), §10 (bundle); research.md D-13, D-16, D-22; spec US2.4, US2.5, US4.2, FR-005, FR-018.
- `tracked_files` means "must be present" to `charter bundle validate` (`charter_bundle.py:323-400`, `require_tracked=True` at `:364`), `generate.py:430, 645-655` and the shipped `m_3_2_0rc35_unified_bundle.py:185-248`: **do not** add the ledger there (M5). Use a new `optional_tracked_files` field.
- FR-018 wording note: a seam write restamps, so a CLI deny change never reads as stale; the guarantee is detection of out-of-band edits (P14).
- Doctor goes through `charter.activation.api` (`ledger_findings`, exported here). No boundary-baseline growth.
- Mission order: WP09 of 15 (strictly linear).
- Shared files (ordered): `bundle.py` (from WP03), `activation_ledger.py`, `api.py`, API re-export gate (from WP08).

## Branch Strategy

- **Strategy**: single_branch; sequential in the repository root checkout on `core-align-3-persistent-deactivation`.
- **Planning base branch**: `core-align-3-persistent-deactivation`
- **Merge target branch**: `core-align-3-persistent-deactivation`

```bash
spec-kitty agent action implement WP09 --agent claude --mission persistent-deactivation-ledger-01M59YAA
```

## ATDD (red first)

T053 writes: a hash test (no ledger → hash unchanged vs. the base; ledger present → hash covers
it; hand edit of the ledger → freshness reports stale), a manifest-model test for
`optional_tracked_files` (disjointness), and doctor tests for each finding code. Commit before
implementation; record the red summary.

## Subtasks

### Subtask T053: Failing acceptance tests

**Steps**:
1. `tests/charter/test_bundle_optional_ledger_hash.py`: compute the bundle content hash for a fixture without a ledger and compare against the value computed by the base implementation (hard-code the expected digest produced on the base, or compute via the unchanged required members); add a ledger → hash changes; edit the ledger by hand (no restamp) → `charter_runtime.freshness` reports the bundle stale; a seam write (activate/deactivate) restamps → fresh.
2. `tests/charter/test_bundle_manifest_model.py`: `optional_tracked_files` validated disjoint from `tracked_files`/`derived_files`; `CANONICAL_MANIFEST.tracked_files` unchanged.
3. `tests/doctor/test_doctor_activation_ledger.py` — one test per code, through `spec-kitty doctor charter-packs --json`:
   - `ACTIVATION_STORE_ERROR` (malformed ledger; unreadable required floor) → error, report not healthy;
   - `ACTIVATION_UNMIGRATED` (legacy activation keys, no ledger) → **warning** naming `spec-kitty upgrade` / `spec-kitty migrate activation-ledger` (reads stay legacy under `mission_pivot_option_b`, so it is not an error). **Transition-mode pin (rewritten by WP14 T082)**: this file runs in the in-Mission strict test mode, so until WP14 the seam also raises on the unmigrated fixture, and `ACTIVATION_STORE_ERROR` co-occurs (report not healthy). Assert both now; WP14 removes the co-occurring error and asserts "warning only, healthy";
   - `LEGACY_DENY_KEY` (a `deactivated_<kind>` key on a legacy surface: never applied, and the migration refuses it) → error, with the remedy "remove it by hand, then migrate";
   - `REQUIRED_OMITTED_BY_ALLOW_LIST` (FR-023, R12): an org-required id that an explicit `activated_<kind>` list leaves out → **warning** naming the requiring pack(s). Core semantics are unchanged (ruling `required_always_active_divergence`). Add a positive control: the same id under an absent allow list gives no warning;
   - `LEGACY_KEYS_PRESENT` (keys in `charter.yaml` or `config.yaml` beside a ledger) → error, ledger answer wins (US2.4);
   - `DENY_UNKNOWN_ID`, `DENY_REQUIRED_ID` (names the pack, US4.2), `DENY_SELECTED_ID` (`answers.selected_*` lists a denied id), `UNKNOWN_DENY_KEY` → warnings, report healthy if nothing else (US2.5).
   - `charter bundle validate` reports the ledger present/absent without failing.

### Subtask T054: Bundle manifest and hash (`charter/bundle.py`)

**Steps**:
1. `CharterBundleManifest` (`bundle.py:84-130`) gains `optional_tracked_files: list[Path]` with a validator for disjointness; `CANONICAL_MANIFEST` (`:133-140`) lists `ACTIVATION_YAML` there.
2. `BUNDLE_OPTIONAL_CONTENT_HASH_FILES = (ACTIVATION_LEDGER.name,)`, derived from `kernel.activation_ledger_store.ACTIVATION_LEDGER`. No new `"activation.yaml"` literal (M5); the path-literal gate keeps an empty allowlist for the ledger name; `compute_bundle_content_hash` (`:148-200`) appends the ledger digest only when the file exists (order: after the required members, so ledger-less hashes are byte-identical to today).

### Subtask T055: Bundle consumers

**Steps**:
1. `cli/commands/charter_bundle.py` `validate`: report optional files as present/absent, never fail on absence; `_enumerate_out_of_scope_files` must treat `optional_tracked_files` as **declared** (otherwise the ledger is reported out of scope, F12) — add a test.
2. `cli/commands/charter/generate.py`: only if its manifest read needs the new field (likely no change; record "no change needed" if so).
3. `charter_runtime/freshness/computer.py:221`: add `_OPTIONAL_BUNDLE_FILES`, derived from `ACTIVATION_LEDGER` (no literal, M5), parse-checked at `:565-600`; update `tests/specify_cli/charter_freshness/test_computer.py::test_bundle_file_lists_stay_in_sync` to pin both pairs.
4. `state/contract.py:563`: declare the ledger as a git-tracked project-state surface, with its `path_pattern` **derived** from `kernel.activation_ledger_store.ACTIVATION_LEDGER` (`ACTIVATION_LEDGER.as_posix()`), never a new literal (L3, M5).
5. Do not add an allowlist entry for the ledger name. If an existing row's token moves, refresh its rationale at `tests/architectural/charter_path_literal_allowlist.yaml:127`.

### Subtask T056: `ledger_findings` in the seam

**Steps**: `activation_ledger.ledger_findings(repo_root) -> LedgerFindings(errors, warnings)` with `Finding = {code, file, key, ids, message}` per data-model.md §9. Catch `ActiveCharterConfigError` once → `ACTIVATION_STORE_ERROR` carrying its `body`. Compute `ACTIVATION_UNMIGRATED` and `LEGACY_DENY_KEY` from the resolver result as data. Compute `REQUIRED_OMITTED_BY_ALLOW_LIST` from the strict floor provenance and each **present** allow list (stem comparison through `IdentityIndex`). `LEGACY_KEYS_PRESENT` is computed from the **data** `resolve_activation_source(...).stray_legacy_keys`. It never goes through the raising read path (M2), so in strict test mode it is still reported. The doctor test pins `LEGACY_KEYS_PRESENT` in test mode, and WP14 keeps that assertion after the flip. Compute the warnings from the ledger, available ids (all layers), the strict floor provenance (pack names) and `answers.selected_*` (read-only, provenance — ADR 3.x/2026-07-18-1). Export `ledger_findings` (and the result type) on `charter.activation.api`; update the re-export gate.

### Subtask T057: Doctor wiring, and `charter list` marks required-omitted ids (FR-023)

Also: in `src/specify_cli/cli/commands/charter/list_cmd.py`, an org-required id omitted by an explicit allow list is shown as `required (not in force: explicit allow list omits it)`, naming the pack(s). `--json` gains `required_not_in_force: {<plural>: [{id, packs}]}`, only when non-empty (an additive JSON change; WP15 documents it). The test goes in the new `tests/specify_cli/cli/commands/charter/test_list_required_omitted.py` (listed in `SWEPT_PREFIXES`). #6417 (P1, 4.0.0) is the user-visible face of this divergence; classify its Gherkin as drift in the history note.


**Steps**: in `cli/commands/_charter_pack_collect.py` add `_run_activation_ledger_check(report, repo_root)` modelled on `_run_retired_governance_key_check` (`:1101-1131`), storing `org_drg["activation_ledger"] = {"errors": [...], "warnings": [...]}`; wire it in `doctor.py` `charter_packs_check` (`:1153`) and render at `:1168` / `:1206` (errors red, warnings yellow; any error → not healthy).

### Subtask T058: Gates, polish, and this repository's restamp (M4)

**Timing tests restated (pass-8 L4, NFR-003 = no regression against the base, R6, #6506)**: WP04's `tests/specify_cli/cli/commands/charter/test_deactivate_cli_timing.py` and WP05's `test_context_cli_timing.py` carry an absolute 2 s budget. `test_deactivate_cli_timing` fails at 2.3–2.6 s on a loaded machine, and the absolute budget is pre-existing on `main` (#6506). Rework both, since this WP owns them now:
- these tests measure the **cost of the deny list**, not a regression against the base (pass-9 L2). On the same code, in the same process, they compare a fixture **with** a deny list against one **without**;
- assert that the median ratio stays at or below 1.25, with the absolute numbers recorded in the test output;
- NFR-003's no-regression-against-base check is separate and **manual**: alternate base and head runs (for example five each, interleaved) of `charter activate` / `deactivate` / `charter context` on this repository, and record the medians in the PR's *Tests run* section;
- keep `pytestmark = [pytest.mark.timing]`, and run them with `-n0 -m timing`;
- cite #6506 in the docstring.

- WP08 dogfooded a ledger into this repository. Once T054 adds `activation.yaml` to the bundle content hash, run `spec-kitty charter bundle validate` and the freshness check on this repository.
- Restamp `.kittify/charter/synthesis-manifest.yaml` (`restamp_bundle_hash`; this WP owns that file) so this repository's own bundle reads fresh.
- Commit it with this WP.


**Steps**: run the gates below; fix path-literal and dead-symbol findings; make sure every finding message names the file and the remedy (`spec-kitty upgrade`, `charter activate <kind> <id>`, or remove the stale entry by hand).

## Validation / targeted test surface

```bash
cd /home/user/spec-kitty
.venv/bin/python -m pytest -q tests/charter/test_bundle_optional_ledger_hash.py tests/charter/test_bundle_manifest_model.py tests/doctor/test_doctor_activation_ledger.py tests/specify_cli/charter_freshness/test_computer.py
.venv/bin/python -m pytest -q -n auto --dist loadfile -m "not timing and not stress" tests/doctor tests/specify_cli/charter_freshness tests/charter tests/charter_offering tests/specify_cli/charter_packs
.venv/bin/python -m pytest -q tests/specify_cli/cli/commands/test_doctor_cli_surface_golden.py tests/charter/test_governance_fail_closed.py
.venv/bin/python -m pytest -q tests/charter_offering/test_fresh_seed_restamp_parity.py tests/specify_cli/upgrade/test_charter_bundle_v2_migration.py
.venv/bin/python -m pytest -q tests/architectural/test_charter_path_literal_authority.py tests/architectural/test_json_contract_enumeration.py tests/architectural/test_doctrine_census.py tests/architectural/test_override_policy_parity.py tests/architectural/test_charter_activation_api_reexport.py tests/architectural/test_runtime_charter_activation_boundary.py tests/architectural/test_layer_rules.py tests/architectural/test_no_dead_symbols.py
.venv/bin/python -m pytest -q -n0 -m timing tests/specify_cli/cli/commands/charter/test_deactivate_cli_timing.py tests/specify_cli/cli/commands/charter/test_context_cli_timing.py
make test-fast
uv run --frozen ruff check <touched files>
uv run --frozen ruff format --check --force-exclude <touched files>
uv run --frozen mypy src/charter/bundle.py src/charter/activation/activation_ledger.py src/specify_cli/cli/commands/_charter_pack_collect.py src/specify_cli/cli/commands/doctor.py src/specify_cli/charter_runtime/freshness/computer.py
.venv/bin/spec-kitty doctor charter-packs --json
```

The last command on this (migrated) repository must report no activation-ledger error.

## Standing orders

- python-pedro; complexity ≤ 15 (doctor collectors grow — extract per-code helpers and test them); ruff/format(`--force-exclude`)/mypy clean; no suppressions.
- Append dated entries to the Mission's `traces/*.md` (the P14 wording note goes in `design-decisions.md`).
- Do not edit shipped migrations (rc35 bundle migration stays unchanged).

## Definition of Done

- Ledger is an optional tracked + optional hash member; ledger-less hashes unchanged.
- Doctor reports all six codes with the right severities.
- Gates green; subtasks marked done.

## Risks

- Changing the hash for ledger-less projects would stale every existing project: the T053 base-equality test guards this.
- The freshness computer keeps its own file lists: the sync test pins them.

## Reviewer Guidance

- Confirm `tracked_files` is unchanged and rc35's output is unaffected.
- Confirm doctor uses the API, not activation internals.

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
