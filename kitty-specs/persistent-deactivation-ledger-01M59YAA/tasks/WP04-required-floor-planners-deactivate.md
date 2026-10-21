---
work_package_id: WP04
title: Required floor, planners, manager, deactivate CLI
dependencies:
- WP03
requirement_refs:
- FR-006
- FR-007
- FR-008
- FR-009
- FR-012
- FR-013
- C-005
- C-007
- C-008
- NFR-001
planning_base_branch: core-align-3-persistent-deactivation
merge_target_branch: core-align-3-persistent-deactivation
branch_strategy: Planning artifacts for this mission were generated on core-align-3-persistent-deactivation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into core-align-3-persistent-deactivation unless the human explicitly redirects the landing branch.
subtasks:
- T016
- T017
- T018
- T019
- T020
- T021
- T022
phase: Phase 2 - Deny algebra and writers
history:
- at: '2026-10-19T12:17:27Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/
create_intent:
- tests/charter/activation/test_required_floor_provenance.py
- tests/charter/activation/test_deny_planning.py
- tests/specify_cli/cli/commands/charter/test_deactivate_records_exclusion.py
- tests/specify_cli/cli/commands/charter/test_deactivate_cli_timing.py
execution_mode: code_change
model: ''
owned_files:
- src/charter/activation/org_pack_discovery.py
- src/charter/activation/org_charter.py
- src/charter/activation/activation_engine.py
- src/charter/activation/pack_manager.py
- src/specify_cli/cli/commands/charter/deactivate.py
- tests/architectural/charter_activation_boundary_baseline.yaml
- tests/architectural/_baselines.yaml
- tests/charter/test_pack_manager.py
- tests/charter/test_skill_activation.py
- tests/charter/test_pack_manager_catalog.py
- tests/charter/test_activation_engine.py
- tests/charter/test_activation_preserves_effective_4253.py
- tests/charter/activation/test_promotion_fail_closed.py
- tests/charter/activation/test_required_floor_provenance.py
- tests/charter/activation/test_deny_planning.py
- tests/specify_cli/cli/commands/charter/test_charter_deactivate_commands.py
- tests/specify_cli/cli/commands/charter/test_deactivate_records_exclusion.py
- src/specify_cli/_completion_manifest.json
- tests/specify_cli/cli/commands/charter/test_deactivate_cli_timing.py
- tests/conftest.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Required floor, planners, manager, deactivate CLI

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro` (`packs/built-in/agent_profiles/python-pedro.agent.yaml`)
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

- Check `review_ref` in the event log; address every item; record with `spec-kitty agent tasks add-history WP04 --note "..."`.

---

## Objective

Make deactivation persist: one strict required-floor reader with per-pack provenance, plans that
carry allow **and** deny state in one write, a refusal for org-required artifacts, the retirement
of `NoActivationRestrictionsError`, and a `charter deactivate` CLI that records an exclusion under
"absent = all" and only for the id the user named.

## Context

- Plan IC-04; data-model.md §2, §3, §4, §6; research.md D-05, D-08, D-09, D-11, D-18.
- Mission order: WP04 of 15 (strictly linear). Builds on WP02 (`activation_ledger.prepare_ledger_write`, `DenyListChoice`, `ActiveCharterConfigError` in the seam) and WP03 (`resolve_activation_write_target` with `deny_change`; the tolerant legacy save carries deny keys).
- **Transition model (D0)**: tolerant mode (default) stores on the legacy surface when no ledger exists and the legacy save accepts `deactivated_<kind>` keys, so existing legacy-keyed tests keep working. New acceptance tests are ledger-seeded and run strict through `SWEPT_PREFIXES` (see the test-mode rules at the end). This resolves analysis F1: legacy-keyed fixtures such as `tests/charter/test_activate_restamps_bundle_hash.py` stay green (they are in the targeted surface below).
- `resolve_deny` / `PackContext` membership is WP05. Here, ship **one private stem-space helper**
  `_effective_deny_stems(kind, deny, required_floor)` in `activation_engine.py` (stems normalised
  through `IdentityIndex.stem`, as `--only` does at `pack_manager.py:527-529`). WP05 replaces it with
  the identity-space `_effective_deny`; a test added there pins that exactly one effective-deny
  helper remains.
- C-005: never touch `_fold_policies`, `resolve_pack_chain`, `_resolve_chain` (precedence belongs to the parallel later-declared-pack-wins workstream).
- C-007: cascade deactivation keeps the shared-reference skip.
- C-008: no alias or shim for the retired error.
- Shared files (dependency-ordered): `pack_manager.py` (from WP02 and WP03), `org_pack_discovery.py` (→WP05), `src/specify_cli/_completion_manifest.json` (→WP07).

## Branch Strategy

- **Strategy**: single_branch; sequential in the repository root checkout on `core-align-3-persistent-deactivation`.
- **Planning base branch**: `core-align-3-persistent-deactivation`
- **Merge target branch**: `core-align-3-persistent-deactivation`

```bash
spec-kitty agent action implement WP04 --agent claude --mission persistent-deactivation-ledger-01M59YAA
```

## ATDD (red first)

T016 writes acceptance tests for US1.1, US1.2, US1.4, US1.5, US4.1, US4.3, the edge cases
(unknown id, already-denied, `[]`+activate, `--only`, skill "required" kind, unreadable org pack),
NFR-001 byte-identity for every refusal, and the US1.3 promotion rows (F17). Every refusal test has
a **same-fixture positive control** (F15): an allowed deactivation of another id on the same fixture
succeeds. Commit them before implementation and record the red summary in your history note.

## Subtasks

### Subtask T016: Failing acceptance tests

**Steps**:
1. `tests/specify_cli/cli/commands/charter/test_deactivate_records_exclusion.py` (CLI via `CliRunner`, seeded with `tests/_factories/activation_ledger.py`):
   - no `activated_directives` → `charter deactivate directive D` exits 0, ledger gains `deactivated_directives: [D]`, no allow key appears (US1.1);
   - `activated_directives: [A, D]` → allow `[A]`, deny `[D]` (US1.2);
   - org pack `acme` with `required_directives: [D]` (write a project org pack fixture under `.kittify/charter-packs/` the way `tests/charter/activation/test_org_charter_union.py` does) → exit ≠ 0, stderr names `acme` and `required_directives`, ledger/charter.yaml/config.yaml byte-identical (US4.1, NFR-001);
   - D already denied → warning, exit 0, ledger byte-identical;
   - unknown id → existing unknown-id error, nothing written;
   - declared org pack with malformed `org-charter.yaml` → refusal, nothing written (FR-013 strict);
   - cascade deactivation of P under an absent allow-list → only `deactivated_<kind>: [P]` recorded; output contains "still active (no allow-list; only P excluded)" (P11);
   - cascade reaching a required child → "skipped (required by acme)";
   - each refusal case first deactivates a non-required id on the same fixture successfully (positive control, F15);
   - every case is ledger-seeded. Legacy-shape coverage comes from the existing tests in the F1 list, which stay green unchanged.
2. `tests/charter/activation/test_deny_planning.py` (pure planner tests, one per row of data-model.md §3 that this WP owns): activate denied id under absent "all" → deny-only plan, allow stays absent (US1.4, D-09); under absent "required" (skill) → in-force set materialised + id; `[]` → `[x]`; `[A]` → `[A, x]` (US1.5); `--only` → required stems + x and clears x only; promotion skips effective-denied ids and reports them in `PromotionOutcome.skipped_denied`; **named US1.3 rows (F17)**: `test_org_required_promotion_of_other_ids_keeps_denied` (org pack requires A, user denied D → promotion adds A, D stays denied) and `test_mission_type_seeding_keeps_denied` (mission-type default seeding lists D → D stays denied and is reported).
3. `tests/charter/activation/test_required_floor_provenance.py`: provenance through an `extends:` chain (`RequiringPack(pack=base, via=declared)`), union over two declared packs, stem normalisation, strict mode refusing on a cycle / dangling base / unreadable pack, non-strict mode unchanged for the overlay.

### Subtask T017: One required-floor reader (R3)

**Steps** (all in `org_pack_discovery.py`):
1. `_iter_org_charter_docs` (`:136-169`) yields `(declared_pack, member_pack, raw)` and walks each declared pack's `extends:` chain once via `charter.offering.packs.extends.resolve_extends_order`; add a keyword `strict: bool`.
2. Add `@dataclass(frozen=True) class RequiringPack(pack: str, via: str | None = None)`.
3. Add `read_org_required_provenance(repo_root, kind, *, strict) -> dict[str, tuple[RequiringPack, ...]]`; ids normalised with `org_charter._normalize_required_ids` (`org_charter.py:294`).
4. Re-point `read_org_required_ids` (`:216-230`) and `_read_org_required_selections` (`:197-214`) at the same iterator (D-18: the overlay now includes `extends:`-inherited requirements; note it in `design-decisions.md`).
5. Strict mode raises `ActiveCharterConfigError` on an unreadable or malformed `org-charter.yaml`, a cycling or dangling `extends:` (precedent: `require_org_skill_policy_readable`, `:248`). Never silently widen.
6. M2/M5 (matches the amended spec edge case):
   - Deactivation and promotion **always** read the strict required floor. An unreadable declared org pack or an `extends:` cycle refuses them.
   - On the read path (WP05) the floor is read, and fails closed, whenever the kind's deny list is non-empty: that is the only case where the floor changes the answer.
   - An empty deny list cannot widen anything, so the floor is not read then (NFR-003).
   - Neither path ever widens.

### Subtask T018: `ActivationPlan` carries deny; one write

**Steps**:
1. `ActivationPlan` (`activation_engine.py:156-192`) gains `deny_key: str | None`, `new_deny_list: list[str] | None` (`[]` removes the key), `deny_change: DenyListChoice | None`.
2. Pure helper `deny_delta(before, after) -> tuple[list[str], list[str]]` (added, cleared) used for reporting; do not store deltas on result types (R11).
3. `commit_plan` (`:484-525`) assigns both keys and calls `save(path, data, deny_change=plan.deny_change)` exactly once; `restamp_bundle_hash` after success as today.

### Subtask T019: Planners and the refusal seam

**Steps**:
1. `plan_activation` (`:251-410`): extract `_deny_branch(...)` and `_materialise_absent(...)` helpers (the function is near the complexity ceiling) for the four cases of data-model.md §3 (deny-only, materialise-then-append for "required" kinds, clear-then-append for `[]`/list, `--only` clears only the named id). Every case that clears a deny entry sets `deny_change=DenyListChoice.ACTIVATE`. The absent-list materialisation (#4253) leaves out denied ids.
2. `plan_deactivation` (`:413-481`) gains `available_ids` and `required_by: Mapping[str, tuple[RequiringPack, ...]]`; first step `check_deactivation_permitted(kind, artifact_id, required_by)` raising `RequiredArtifactDeactivationError(DeactivationRefused)` with `kind`, `artifact_id`, `reason="required"`, `policy_key`, `requiring`; message: `Cannot deactivate directive 'D': required by org pack 'acme' (required_directives). Nothing was recorded.` `DeactivationRefused` is an abstract `ValueError` subclass a later `locked` check joins.
3. Unknown id → `UnknownActivationIdError` (also from `plan_deactivation` now); already denied → a plan flagged no-op with a warning.
4. `_plan_promotion` / `promote_activations` (`:597-731`) take `required_exempt` and skip effective-denied ids, reporting them in `PromotionOutcome.skipped_denied: dict[str, list[str]]`.

### Subtask T020: Retire `NoActivationRestrictionsError` (C-008)

**Steps**: delete the class (`activation_engine.py:113-146`) and every reference: `pack_manager.py:50` (docstring), `:78` (import), `:859`, `:887` (docstrings), `:1137` (`__all__`); `specify_cli/cli/commands/charter/deactivate.py:17`, `:31`, `:201`, `:311`; tests in `tests/charter/test_pack_manager.py`, `test_skill_activation.py`, `test_pack_manager_catalog.py`, `test_activation_engine.py`, `tests/specify_cli/cli/commands/charter/test_charter_deactivate_commands.py` (rewrite those cases to the new behaviour: an exclusion is recorded). Add `RequiredArtifactDeactivationError`, `DeactivationRefused`, `RequiringPack` to `pack_manager.__all__`. `grep -rn NoActivationRestrictionsError src tests docs` must return nothing outside CHANGELOG history.

### Subtask T021: Manager and org promotion

**Steps**:
1. `ActiveCharterManager.activate` (`pack_manager.py:737-843`) gains `reinstate: DenyListChoice = DenyListChoice.ACTIVATE`.
2. `deactivate` (`:845-913`) gains `record_exclusion: bool = True`; it **always** reads the strict floor (T017.6) and passes `required_by` to the planner.
3. `_preservation_set` (`:430-478`) subtracts the effective deny (stem comparison).
4. Deny entries are written in stem spelling via `IdentityIndex.stem`.
5. `org_charter._promote_org_required_to_config` (`org_charter.py:404-484`) passes its ids as `required_exempt`.
6. Update `tests/charter/test_activation_preserves_effective_4253.py` and `tests/charter/activation/test_promotion_fail_closed.py` for the deny-aware materialisation/promotion.

### Subtask T022: Deactivate CLI and the boundary baseline

**Steps**:
1. Direct path (`deactivate.py:304-311`): catch `DeactivationRefused` → red error naming pack(s) and policy key, exit 1, nothing written; already-denied → yellow warning, exit 0.
2. `_render_cascade_deactivation` (`:157-241`) runs even when the named id was implicit (remove the gate at `:335-341`); per child call `manager.deactivate(..., record_exclusion=False)` (`:194`); render required children "skipped (required by <pack>)"; under an absent allow-list render "still active (no allow-list; only <P> excluded)".
3. `_active_urns` (`:113-155`) counts the effective allow state (C-007).
4. Import the new symbols through `pack_manager` / `charter.activation.api`, then drop the drained row `deactivate.py -> charter.activation.activation_engine` from `tests/architectural/charter_activation_boundary_baseline.yaml` and lower `tests/architectural/_baselines.yaml:26` from 236 to 235.
5. Help text changed → regenerate `src/specify_cli/_completion_manifest.json` with `.venv/bin/python -m specify_cli.completion --regenerate` and run `tests/architectural/test_completion_manifest_freshness.py` (F14).
6. NFR-003 automated: add `tests/specify_cli/cli/commands/charter/test_deactivate_cli_timing.py` modelled on `test_preset_cli_timing.py` and marked `pytestmark = [pytest.mark.timing]` (median of N `charter deactivate` runs on a fixture copy, budget 2 s) (F18).

## Validation / targeted test surface

```bash
cd /home/user/spec-kitty
.venv/bin/python -m pytest -q tests/specify_cli/cli/commands/charter/test_deactivate_records_exclusion.py tests/charter/activation/test_deny_planning.py tests/charter/activation/test_required_floor_provenance.py
.venv/bin/python -m pytest -q tests/charter/test_pack_manager.py tests/charter/test_skill_activation.py tests/charter/test_pack_manager_catalog.py tests/charter/test_activation_engine.py tests/charter/test_activation_preserves_effective_4253.py tests/charter/activation/test_promotion_fail_closed.py tests/specify_cli/cli/commands/charter/test_charter_deactivate_commands.py tests/charter/activation/test_org_charter_union.py tests/charter/activation/test_resolve_pack_chain.py
.venv/bin/python -m pytest -q -n auto --dist loadfile -m "not timing and not stress" tests/charter tests/charter_offering tests/specify_cli/cli/commands/charter
.venv/bin/python -m pytest -q tests/architectural/test_runtime_charter_activation_boundary.py tests/architectural/test_charter_activation_api_reexport.py tests/architectural/test_layer_rules.py tests/architectural/test_no_dead_symbols.py tests/architectural/test_charter_kind_vocabulary_single_authority.py tests/architectural/test_org_pack_chain_single_authority.py tests/architectural/test_kind_table_derivation.py tests/architectural/test_override_policy_parity.py tests/architectural/test_builtin_override_policy.py tests/architectural/test_completion_manifest_freshness.py
# F1 legacy-keyed fixtures that must stay green in tolerant mode
.venv/bin/python -m pytest -q tests/charter/test_activate_restamps_bundle_hash.py tests/charter/test_activation_engine_charter_yaml.py tests/charter/test_glossary_pack_activation.py tests/charter/test_activate_resolves_no_answers_edit.py tests/charter/test_charter_cwd_tripwire.py tests/integration/test_pack_skill_lifecycle.py tests/specify_cli/cli/commands/charter/test_activation_layout.py tests/specify_cli/cli/commands/charter/test_activate_preserve.py tests/specify_cli/cli/commands/charter/test_activate_recompile_4785.py tests/specify_cli/cli/commands/charter/test_org_cascade_chain.py tests/specify_cli/cli/commands/charter/test_resynthesize_and_hotpath.py tests/specify_cli/cli/commands/charter/test_whole_kind_unresolved_handling_5257.py tests/specify_cli/test_charter_activate_cli.py
.venv/bin/python -m pytest -q -n0 -m timing tests/specify_cli/cli/commands/charter/test_deactivate_cli_timing.py
make test-fast
uv run --frozen ruff check <touched files>
uv run --frozen ruff format --check --force-exclude <touched files>
uv run --frozen mypy src/charter/activation/activation_engine.py src/charter/activation/pack_manager.py src/charter/activation/org_pack_discovery.py src/charter/activation/org_charter.py src/specify_cli/cli/commands/charter/deactivate.py
```

NFR-003 is enforced by `test_deactivate_cli_timing.py` (T022.6); also record one manual wall time on this repository.

## Standing orders

- python-pedro; complexity ≤ 15 (extract helpers, test them directly); ruff/format(`--force-exclude`)/mypy clean; no suppressions.
- Append dated entries to the Mission's `traces/approach.md`, `traces/design-decisions.md` (D-18 overlay alignment), `traces/tooling-friction.md`.
- Do not edit shipped migrations (C-001).

## Definition of Done

- Red-first tests committed, now green; every refusal path proven byte-identical (NFR-001).
- `NoActivationRestrictionsError` gone everywhere (C-008); baseline 236 → 235.
- Precedence code untouched (C-005; `git diff` shows no change in `_fold_policies`/`resolve_pack_chain`/`_resolve_chain`).
- Gates green; subtasks marked done.

## Risks

- The strict floor read on every deactivate and promotion (always, by design) could regress latency: `test_deactivate_cli_timing.py` guards the 2 s budget.
- `extends:` walk ordering: use the canonical resolver, do not hand-roll.
- Tests asserting the old `NoActivationRestrictionsError` message: rewrite, do not delete coverage.

## Reviewer Guidance

- Walk data-model.md §3 rows owned here and find a test for each.
- Confirm cascade deactivation adds a deny entry only for the named id (US3.4).
- Confirm the refusal names every requiring pack and the `required_<kind>` key.

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
