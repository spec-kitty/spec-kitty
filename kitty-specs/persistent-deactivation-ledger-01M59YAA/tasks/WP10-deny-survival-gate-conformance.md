---
work_package_id: WP10
title: FR-014 deny-survival gate and FR-015 conformance table
dependencies:
- WP09
requirement_refs:
- FR-014
- FR-015
- SC-003
- FR-024
planning_base_branch: core-align-3-persistent-deactivation
merge_target_branch: core-align-3-persistent-deactivation
branch_strategy: Planning artifacts for this mission were generated on core-align-3-persistent-deactivation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into core-align-3-persistent-deactivation unless the human explicitly redirects the landing branch.
subtasks:
- T059
- T060
- T061
- T062
- T063
phase: Phase 7 - Proof
history:
- at: '2026-10-19T12:17:27Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/
create_intent:
- tests/architectural/test_deny_list_survives_upgrade.py
- tests/charter/conformance/__init__.py
- tests/charter/conformance/activation_ledger_cases.yaml
- tests/charter/conformance/test_activation_ledger_conformance.py
execution_mode: code_change
model: ''
owned_files:
- tests/architectural/test_deny_list_survives_upgrade.py
- tests/charter/conformance/**
- tests/conftest.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP10 – FR-014 deny-survival gate and FR-015 conformance table

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro` (`packs/built-in/agent_profiles/python-pedro.agent.yaml`)
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

- Check `review_ref` in the event log; address every item; record with `spec-kitty agent tasks add-history WP10 --note "..."`.

---

## Objective

Prove, as a standing gate, that **no registered migration and no built-in preset can remove a
deny entry** (static scan + classifier + dynamic runs + self-mutation), and freeze the mission's
fixed answers as one portable, data-driven conformance table (FR-015) that spec-kitty-charter
and open-packs can port.

## Context

- Plan IC-10; data-model.md §8 (table schema and sample rows); research.md D-14, D-17; spec US5, FR-014, FR-015, SC-003.
- Mission order: WP10 of 15 (strictly linear). Deny entries exist only in a ledger: no migration touches deny keys (operator ruling `deny_writers`), and the rc8 migration refuses a legacy `deactivated_*` key (WP08).
- Everything under test already exists (WP02–WP09). This WP adds tests only; if a test finds a
  real defect in production code, stop, record it in `traces/tooling-friction.md` and the history
  note, and route it back to the owning WP's reviewer (do not patch `src/` here). A scope-wrapper defect routes to WP08.
- Operator ruling `conformance_corpus`: no export script; the table is the corpus.
- Precedent for a conformance runner: `tests/contract/_mission_status_conformance.py`.
- Built-in presets: `packs/built-in/presets/*.yaml` (`default.yaml`, `minimal.yaml` today — assert the count by glob, never a literal).

## Branch Strategy

- **Strategy**: single_branch; sequential in the repository root checkout on `core-align-3-persistent-deactivation`.
- **Planning base branch**: `core-align-3-persistent-deactivation`
- **Merge target branch**: `core-align-3-persistent-deactivation`

```bash
spec-kitty agent action implement WP10 --agent claude --mission persistent-deactivation-ledger-01M59YAA
```

## ATDD (red first)

These tests are the deliverable, and the code under test already exists, so "red on the base"
is shown two ways: (1) the conformance table and gate are committed first together with the
self-mutation cases of T063, which must fail against a deliberately broken seam (raw deny-dropping
migration, unguarded write, `PackContext.denied` forced empty by monkeypatch); (2) record in your
history note the failing row ids when the runner is pointed at the forced-empty seam. Then commit
the passing runners.

## Subtasks

### Subtask T059: Conformance table `activation_ledger_cases.yaml`

**Steps**:
1. Create `tests/charter/conformance/activation_ledger_cases.yaml` with `schema: activation-ledger-conformance/1` and sections `effective_set`, `identity`, `readers`, `cascade`, `deactivation`, `ledger_migration` (data-model.md §8).
2. Rows (minimum): every row of the data-model.md §2 facts table; identity stem vs declared id (R4) both directions; readers: agent_profile and tactic denied with absent allow through the action bundle and the profile registry (M2); cascade stop-at-denied, second-path reach, unreached bucket, requires flag, out-of-scope denied, include-deactivated; deactivation: required refusal (packs, policy key, ledger unchanged), already-denied no-op, unknown id, cascade child under absent allow (P11), required child skipped; ledger_migration: pointer charter.yaml move, no-pointer config.yaml, equal leftover copy, differing copy refused, stray copy with authority lacking the key refused, rerun-after-crash strips equal, `[]` preserved.
3. Plain data only: no Python expressions, no repository paths except the legacy surface names.
4. **Both spellings per case** (FR-024, `mission_pivot_option_b` adjustment): every case records each artifact id as `{stem, declared_id}`; for an id with no distinct declared id, `declared_id == stem`. The charter harness maps them to contract URNs.
5. **`divergences:` section** (FR-024, ruling `required_always_active_divergence`). Each entry is `{id, core, contract, status, ruling, cases: [case ids]}`. At least:
   - `required-on-read`;
   - `write-time-floor` (`promote_activations`);
   - `preset-force-clears-exclusions` (R7);
   - `unknown-deny-key-preserved` (R5);
   - `stale-required-deny-inert` (R5);
   - `languages-authored-vs-derived` (R10);
   - `id-spelling` (R11);
   - `unknown-token` (R11).

   Activate (select and clear its own exclusion) and deactivate (record it and unselect) are **not** divergences: charter #125 aligned the contract's `select` / `deactivate` with core (2026-10-20; R8 is a 1:1 mapping). The meta-test asserts that no entry with those ids exists.

   Each entry cites at least one case that demonstrates core's side. The rows mirror the **open** divergences of the register in `docs/architecture/activation-ledger-and-charter-contract.md`. Aligned rows, such as Activate and Deactivate (charter #125), stay on that page only. WP15 links both.

### Subtask T060: Conformance runner `test_activation_ledger_conformance.py`

**Steps**:
1. Load the YAML, validate the schema id, `pytest.mark.parametrize` per section with `ids=row["id"]`.
2. One small adapter per section turning a row into calls on the public API (`charter.activation.api` / `pack_manager` / the cascade engine / `plan_ledger_migration`) inside a `tmp_path` project built by `tests/_factories/activation_ledger.py`.
3. Assert exactly the `expect` mapping; unknown expect keys fail the row (keeps the table honest).
4. A meta-test asserts that every section has ≥ 1 row, that row ids are unique, that every case carries both spellings, and that every `divergences` entry cites an existing case id. It also asserts that the required divergence ids are present.

### Subtask T061: Static half of the gate

**Steps** (`tests/architectural/test_deny_list_survives_upgrade.py`):
1. AST-scan `src/specify_cli/upgrade/migrations/**`, `src/charter/activation/preset_application.py`; text-scan `packs/built-in/presets/*.yaml`.
2. Fail on a `deactivated_` string constant, a `DENY_KEYS` / `deny_key` reference, or any call passing a non-`None` `deny_change=`, **except** inside an exact allowlist (L4), given by function name:
   - `preset_application.apply_preset_plan`, the `--preset --force` path, which may reference `DENY_KEYS` / `deny_key` and pass `DenyListChoice.PRESET_FORCE`;
   - `ActiveCharterManager.activate` and `ActiveCharterManager.deactivate`;
   - the cascade reinstate path in `activate.py`.

   **No migration may reference a deny key or pass any non-`None` `deny_change`.** Assert the allowlist is exact in both directions by scanning `src/` for every `deny_change=` keyword and every `DENY_KEYS` / `deny_key` reference.
3. Classifier: a migration module is *activation-touching* when it imports from `charter.activation` or names the activation-ledger path (`activation.yaml`, `ACTIVATION_LEDGER`) or a `LEDGER_KEYS` key (derive from `activation_ledger.LEDGER_KEYS`). The bare word "ledger" never matches (it collides with the Migration Ledger, F16); add a self-mutation case proving a module that only mentions `migration-ledger.jsonl` is **not** classified. Expected today: ~10 modules + `_charter_pack_cutover_snapshots.py` + `m_4_0_0rc8_activation_ledger.py` — assert the classifier's set is non-empty and includes those two named modules plus `m_3_2_x_normalize_activation_absence`; do not hard-code the full list (D-14).

### Subtask T062: Dynamic half of the gate

**Steps**:
1. Assert `len(MigrationRegistry registered) == number of entries in order_manifest.txt`.
2. For each activation-touching migration: a builder makes a post-ledger fixture where `detect()` is True (assert it), with deny entries for directive, tactic and skill and allow lists equal to the frozen cutover default snapshots (the #66 reset shape, from `_charter_pack_cutover_snapshots.py`); run `apply()` (inside the scope, as the runner would); byte-compare the deny keys on disk before/after. Builders live in a helper module inside the test file or `tests/charter/conformance/` — never in `src/`.
3. Every built-in preset (count asserted against the glob) is planned and applied **without** `--force` on a fixture with deny entries; deny keys byte-identical afterwards; the plan's `denied_listed` names the denied ids it lists.
4. **Pre-ledger-shaped migrations (F8, revised in analyze pass 3, M3)**.
   - **Run where it applies.** Every activation-touching migration runs on a post-ledger fixture with deny entries, wherever it applies, and must leave the ledger's deny bytes unchanged. This covers `m_3_2_x_normalize_activation_absence` and every migration that ledger-diff selection can re-select (`skipped` or `failed` records, `registry.py:130`, or `reselect_when_recorded`).
   - **Exemption by ordering** ("ordered before `4.0.0rc8_activation_ledger` in `order_manifest.txt`") is allowed **only** for a migration whose `detect()` cannot be made true once a ledger exists. The gate proves it by calling `detect()` on the post-ledger fixture and asserting False.
   - SC-003 stays as written.
   - Any needed wrapper fix routes to WP08.
5. A non-applicable migration needs no fixture: non-applicability is derived from the classifier.

### Subtask T063: Non-vacuity (self-mutation)

**Steps**:
1. A throwaway migration class (defined in the test) that drops a deny entry with a raw YAML write must fail the dynamic check, and the failure message names the offender.
2. A throwaway call through the seam without `deny_change` must raise `DenyListWriteRefused`.
3. A throwaway source snippet with `deny_change=DenyListChoice.ACTIVATE` in a migration path must fail the static check.
4. Monkeypatch-revert: with `PackContext.denied` forced empty, at least the `effective_set` conformance rows fail (proves the table exercises the seam).

## Validation / targeted test surface

```bash
cd /home/user/spec-kitty
.venv/bin/python -m pytest -q tests/architectural/test_deny_list_survives_upgrade.py tests/charter/conformance
.venv/bin/python -m pytest -q tests/architectural/test_migration_order_manifest.py tests/architectural/test_charter_kind_vocabulary_single_authority.py tests/architectural/test_no_dead_symbols.py
.venv/bin/python -m pytest -q -n auto --dist loadfile -m "not timing and not stress" tests/charter tests/upgrade
make test-fast
uv run --frozen ruff check tests/architectural/test_deny_list_survives_upgrade.py tests/charter/conformance
uv run --frozen ruff format --check --force-exclude tests/architectural/test_deny_list_survives_upgrade.py tests/charter/conformance
uv run --frozen mypy tests/architectural/test_deny_list_survives_upgrade.py tests/charter/conformance
```

Record the timing of the gate file; if it exceeds ~20 s, mark the dynamic half `@pytest.mark.slow` only if the architectural lane already runs slow tests (check `pytest.ini` markers), otherwise optimise the fixtures.

## Standing orders

- python-pedro; complexity ≤ 15 even in tests (split adapters); ruff/format(`--force-exclude`)/mypy clean.
- Append dated entries to the Mission's `traces/*.md`.
- Do not edit shipped migrations; do not edit `src/` in this WP.

## Definition of Done

- Table with all six sections and the minimum rows; runner green.
- Gate: static + classifier + dynamic + self-mutation, all green; counts asserted against the registry/manifest and the preset glob (SC-003).
- Subtasks marked done.

## Risks

- Builders for activation-touching migrations can be brittle; keep them minimal and assert `detect()` True so a stale builder fails loudly.
- Cutover snapshot imports from a migrations helper module: import it, do not copy it.

## Reviewer Guidance

- Check the allowlist is exact and minimal.
- Check every self-mutation case actually fails without the guard (read the assertion messages).

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
