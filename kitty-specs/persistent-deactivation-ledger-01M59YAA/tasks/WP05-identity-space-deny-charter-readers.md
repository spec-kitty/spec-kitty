---
work_package_id: WP05
title: Identity-space deny and charter-side readers
dependencies:
- WP04
requirement_refs:
- FR-006
- FR-016
- NFR-003
- C-002
planning_base_branch: core-align-3-persistent-deactivation
merge_target_branch: core-align-3-persistent-deactivation
branch_strategy: Planning artifacts for this mission were generated on core-align-3-persistent-deactivation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into core-align-3-persistent-deactivation unless the human explicitly redirects the landing branch.
subtasks:
- T023
- T024
- T025
- T026
- T027
- T028
- T029
phase: Phase 3 - Readers honour the ledger
history:
- at: '2026-10-19T12:17:27Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/
create_intent:
- src/charter/activation/activation_ledger.py
- tests/architectural/test_no_raw_activation_membership.py
- tests/charter/activation/test_deny_identity_space.py
- tests/charter/activation/test_pack_context_deny.py
- tests/charter/activation/test_charter_readers_honour_deny.py
- tests/specify_cli/cli/commands/charter/test_context_cli_timing.py
- tests/charter/activation/test_skill_projection_deny.py
- tests/specify_cli/skills/test_skills_catalog_installer_deny.py
execution_mode: code_change
model: ''
owned_files:
- src/charter/activation/pack_context.py
- src/charter/activation/activation_ledger.py
- src/charter/activation/resolver.py
- src/charter/activation/drg_activation.py
- src/charter/activation/compiler.py
- src/charter/activation/action_governance_bundle.py
- src/charter/activation/active_charter_service_builder.py
- src/charter/activation/profile_resolution.py
- src/charter/activation/skill_preparation.py
- src/charter/activation/org_pack_discovery.py
- src/charter/activation/consistency_check.py
- src/charter/activation/context.py
- src/charter/activation/context_renderers/reference_pointers.py
- tests/architectural/test_no_raw_activation_membership.py
- tests/charter/activation/test_deny_identity_space.py
- tests/charter/activation/test_pack_context_deny.py
- tests/charter/activation/test_charter_readers_honour_deny.py
- tests/charter/test_context_include_activation.py
- tests/charter/test_context_include.py
- src/charter/activation/activation_engine.py
- tests/specify_cli/cli/commands/charter/test_context_cli_timing.py
- tests/charter/activation/test_skill_projection_deny.py
- tests/specify_cli/skills/test_skills_catalog_installer_deny.py
- tests/conftest.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – Identity-space deny and charter-side readers

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro` (`packs/built-in/agent_profiles/python-pedro.agent.yaml`)
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

- Check `review_ref` in the event log; address every item; record with `spec-kitty agent tasks add-history WP05 --note "..."`.

---

## Objective

Every charter-side read path subtracts the **same** effective deny, spelled the way the reader
filters (stem, declared id, DRG URN). Add `resolve_deny` / `DenySet`, compute the effective deny
once in `PackContext.from_config`, expose an effective-membership accessor, move every
charter-side reader onto it, and add a gate forbidding raw `activated_<plural> is None`
membership checks outside the seam.

## Context

- Plan IC-05; data-model.md §2, §2.1; research.md D-05, D-06, D-21; spec US1.6 (`charter context`
  never serves a denied id even when `answers.selected_directives` lists it).
- Mission order: WP05 of 15 (strictly linear). Transition model D0: tolerant mode is the default. New reader tests are ledger-seeded and run strict through `SWEPT_PREFIXES`; the existing reader tests stay green unchanged. The read-path floor rule is WP04 T017.6 (read and fail closed only when a deny list is non-empty).
- Builds on WP04's strict required floor (`read_org_required_provenance(..., strict=True)`):
  `D* = resolve_deny(D) − R`.
- Identity index (#6406): `src/charter/activation/identity_index.py` (`IdentityIndex`), and `normalize_activation_identifier` for URNs.
- NFR-003: compute deny only for kinds with a non-empty deny list; zero overhead otherwise.
- C-002: `charter.offering` must not import activation (SPDD probe deny is WP06).
- Shared files (ordered): `pack_context.py` (from WP02/WP03), `activation_ledger.py` (from WP02), `activation_engine.py` (from WP04, to delete `_effective_deny_stems`), `org_pack_discovery.py` (from WP04), `compiler.py` (→WP14), `consistency_check.py` (from WP03).

## Branch Strategy

- **Strategy**: single_branch; sequential in the repository root checkout on `core-align-3-persistent-deactivation`.
- **Planning base branch**: `core-align-3-persistent-deactivation`
- **Merge target branch**: `core-align-3-persistent-deactivation`

```bash
spec-kitty agent action implement WP05 --agent claude --mission persistent-deactivation-ledger-01M59YAA
```

## ATDD (red first)

T023 writes reader-level acceptance tests: a denied directive under an absent allow-list is not
served by `charter context --action implement` even when `answers.selected_directives` lists it
(US1.6); a denied agent_profile and tactic are omitted from the action governance bundle and the
profile resolution; a declared-id allow entry with a stem deny yields an empty effective set
(R4); `--include directive:D` on a denied id renders the "deactivated" note and exits 0; a
denied `mission_step_contract` is filtered before the mission-type early return (P6). Commit
them before implementation; record the red summary.

## Subtasks

### Subtask T023: Failing acceptance tests

**Steps**:
1. `tests/charter/activation/test_charter_readers_honour_deny.py` — fixtures seeded with
   `tests/_factories/activation_ledger.py`; one test per reader in the T026–T028 list; use the
   real built-in pack (pick a directive/tactic/agent_profile id that exists, for example via
   `charter.activation.api` listing) rather than invented ids. **Positive control (F15)**: every
   reader test first asserts the id **is served** on the same fixture before the deny step
   (US1.6: `charter context --action implement` lists D, then deactivate D, then it does not).
2. `tests/charter/activation/test_deny_identity_space.py` — the conformance-shaped facts of
   data-model.md §2 table (rows 1–3, 4 "stale deny inert", 5 skill "required", 7 declared-id vs stem).
3. `tests/charter/activation/test_pack_context_deny.py` — `denied_for`, `admits`, `effective_ids`, `deactivated_urns`; `denied` defaults to `()`; `admits(kind, token)` under an absent "all" allow-list returns **False for a token not in `Avail(k)`** (True only when available and not denied); netting never rewrites or drops hand-edited ids on the next derived write (writers derive from the ledger, never from the netted context: activate X on a ledger holding a hand-edited unknown id U → U survives); hashability/equality of `PackContext` stays (cache keys); no deny computation when deny lists are empty (assert the strict floor reader is not called, via monkeypatch spy).
4. Extend `tests/charter/test_context_include_activation.py` / `test_context_include.py` for the include selector note.
5. NFR-003 automated (F18): `tests/specify_cli/cli/commands/charter/test_context_cli_timing.py` modelled on `test_preset_cli_timing.py` and marked `pytestmark = [pytest.mark.timing]` (median `charter context --action implement` with and without a deny list, budget 2 s).
6. M6 skills projection: `tests/charter/activation/test_skill_projection_deny.py` covers `skill_preparation` (`:250,290`) and `explicit_activated_skills`. A denied non-required skill is absent from the prepared projection under an absent allow list (the "required" default) and under a present list, and a required skill stays projected.
7. M6 skills consumer: `tests/specify_cli/skills/test_skills_catalog_installer_deny.py` checks that `specify_cli/skills/catalog.py` and `skills/installer.py`, consuming the prepared projection, neither list nor install a denied skill. The test only; production changes there are not expected. If one is needed, record it as an out-of-map edit.
8. Single-helper pin: a test asserts `activation_engine` no longer defines `_effective_deny_stems` (WP04's stem-space helper) and that `activation_ledger._effective_deny` is the only effective-deny helper (AST scan of `src/charter/activation/`).

### Subtask T024: `DenySet` and `resolve_deny` (`activation_ledger.py`)

**Steps**:
1. `@dataclass(frozen=True) class DenySet(stems, declared_ids, urns)` with `admits(token) -> bool` (False if the token matches any spelling) and `EMPTY` sentinel.
2. `resolve_deny(kind, tokens, identity: IdentityIndex) -> DenySet`: map each token (stored as stem) to its declared id and DRG URN; unknown tokens stay as stems only.
3. Private `_effective_deny(kind, deny, required_floor, identity) -> DenySet` = resolve_deny minus the floor (in identity space).
4. Unit tests in `test_deny_identity_space.py`.

### Subtask T025: `PackContext` deny and accessors

**Steps** (`pack_context.py:96-200`, `from_config` `:205-288`):
1. Field `denied: tuple[tuple[str, DenySet], ...] = ()` (sorted by plural; hashable; default empty), computed once in `from_config` from `load_activation_ledger` + strict floor, only for kinds with non-empty deny.
2. Present allow lists are netted in identity space; absent lists stay `None`.
3. Accessors `denied_for(kind) -> DenySet`, `admits(kind, token, *, available) -> bool` (allow state with the absent default — under absent "all" the token must be in `available` — minus deny), `effective_ids(kind, available) -> frozenset[str]`. Netting affects reads only; writers keep deriving from the ledger mapping.
3a. Replace WP04's `_effective_deny_stems` with `activation_ledger._effective_deny` at every call site and delete it.
4. `deactivated_urns` becomes a property derived from `denied` (R5).
5. `_absent_key_default` (`:735-744`) and `explicit_activated_skills` (`:724-732`) return deny-netted sets; check consumers `skill_preparation.py:250,290`.
6. A malformed ledger or unreadable floor raises `ActiveCharterConfigError` from `from_config` (fail closed).

### Subtask T026: Resolver and DRG filter

**Steps**:
1. `resolver._gated` (`resolver.py:217-245`) and root helpers (`:683-706`, `:802-840`) use `admits`/`effective_ids`; the per-kind cache key includes the deny set.
2. `drg_activation._resolve_activated_urns_for_kind` / `_node_is_activated` (`drg_activation.py:294-444`): subtract `deactivated_urns`; in the mission-step branch (`:419-425`) check the per-id deny **before** the mission-type early return (P6).

### Subtask T027: Compiler, governance bundle, service builder, profiles, skills

**Steps**:
1. `compiler._resolve_config_activated_roots` (`compiler.py:192-290`) uses the accessor; derive `_CONFIG_ACTIVATION_FIELDS` (`:139-147`) from `ArtifactKind` (C-004). Do **not** touch `_bootstrap_charter_yaml` (WP14).
2. `action_governance_bundle._catalog_default_or_activated` (`:53-91`), `_graph_and_catalog_default_ids` (`:94-160`), `_seed_sets` (`:173-205`) and `:413` subtract deny after widening absent lists.
3. `active_charter_service_builder` (`:217-268`) and `profile_resolution` (`:62`, `:164`) use the accessor.
4. `skill_preparation` follows the netted `_absent_key_default`.

### Subtask T028: Governance selection overlay, consistency, include selectors, references

**Steps**:
1. `org_pack_discovery._load_governance_charter_config` (`:291-343`): `Sel(k) = (selected ∪ R) − D*` — subtract deny after the required union (US1.6).
2. `consistency_check` treats denied ids as inactive.
3. `context.build_charter_context_include` (`context.py:374-490`): gate every kind (not only agent_profile/glossary_pack at `:432`); a denied selector renders `"<kind>:<id> is deactivated in this project (charter activate <kind> <id> restores it)"` and exits 0.
4. `context_renderers/reference_pointers._load_references` (`:247`) and the selection over it (`:94-245`) drop references whose target is denied (a skipped recompile must not leak, P7).

### Subtask T029: Gate `test_no_raw_activation_membership.py`

**Steps**:
1. AST-scan `src/` for `.activated_<plural> is None`, `is not None`, and `in <x>.activated_<plural>` comparisons, **and `getattr(<ctx>, <name>)` where `<name>` is an `activated_*` string constant or a name derived from one** (f-string / `allow_key(...)` / a module constant whose value starts with `activated_`). Known sites today: `resolver.py:247`, `compiler.py:210/215`, `action_governance_bundle.py:194`, `drg_activation.py:367` (moved onto the accessor in this WP) and `specify_cli/cli/commands/charter/_resynthesis_preflight.py:40` (WP06 removes). Derive the plural set from `ArtifactKind`; allowed only in `src/charter/activation/pack_context.py` and `src/charter/activation/activation_ledger.py`.
2. **Concrete floor**: the allowlist is asserted exact (no extra, no missing entries) and the scanner reports ≥ 1 hit on an embedded snippet that reproduces the pre-change `resolver.py:247` pattern. Self-mutation: a temp module with each pattern (attribute `is None`, `in`, `getattr` with literal, `getattr` with f-string) is flagged.
3. Any remaining hit in `specify_cli` that WP06 owns: list it in the gate as a **temporary** xfail-free allowlist entry with a comment `# WP06 removes`, and tell WP06 in your history note; prefer zero.

## Validation / targeted test surface

```bash
cd /home/user/spec-kitty
.venv/bin/python -m pytest -q tests/charter/activation/test_charter_readers_honour_deny.py tests/charter/activation/test_deny_identity_space.py tests/charter/activation/test_pack_context_deny.py tests/charter/test_context_include_activation.py tests/charter/test_context_include.py
.venv/bin/python -m pytest -q tests/charter/activation/test_effective_set.py tests/charter/activation/test_effective_set_chain.py tests/charter/activation/test_identity_index.py tests/charter/activation/test_context_identity_reuse.py tests/charter/test_answers_inert_and_org_union.py tests/charter/test_governance_fail_closed.py
.venv/bin/python -m pytest -q -n auto --dist loadfile -m "not timing and not stress" tests/charter tests/charter_offering
.venv/bin/python -m pytest -q tests/architectural/test_no_raw_activation_membership.py tests/architectural/test_org_pack_chain_single_authority.py tests/architectural/test_kind_table_derivation.py tests/architectural/test_override_policy_parity.py tests/architectural/test_builtin_override_policy.py tests/architectural/test_charter_sole_door_resolver_imports.py tests/architectural/test_no_read_side_bypass.py tests/architectural/test_layer_rules.py tests/architectural/test_charter_offering_does_not_import_activation.py tests/architectural/test_charter_kind_vocabulary_single_authority.py tests/architectural/test_no_dead_symbols.py
.venv/bin/python -m pytest -q -n0 -m timing tests/specify_cli/cli/commands/charter/test_context_cli_timing.py
make test-fast
uv run --frozen ruff check <touched files>
uv run --frozen ruff format --check --force-exclude <touched files>
uv run --frozen mypy <touched src files>
```

NFR-003: time `spec-kitty charter context --action implement` on this repository before and after (no deny lists → no measurable change); record both numbers.

## Standing orders

- python-pedro; complexity ≤ 15; ruff/format(`--force-exclude`)/mypy clean; no suppressions; new helpers get direct tests.
- Append dated entries to the Mission's `traces/*.md`.
- Do not edit shipped migrations.

## Definition of Done

- Every charter-side reader in T026–T028 uses the accessor; tests prove a denied id is never served.
- Deny computed once per `PackContext`, only for non-empty deny lists.
- The raw-membership gate is green and non-vacuous.
- Subtasks marked done; gates green.

## Risks

- `PackContext` equality/hash used as cache keys: keep `denied` a sorted tuple.
- Spelling mismatches (declared id vs stem): covered by the identity tests; do not compare raw strings.
- Wide blast radius in `tests/charter/`: run the full owning directories.

## Reviewer Guidance

- Grep for `activated_` attribute membership outside the seam; the gate must catch it.
- Check US1.6 end to end through `charter context`.
- Check the mission-step deny happens before the mission-type early return.

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
