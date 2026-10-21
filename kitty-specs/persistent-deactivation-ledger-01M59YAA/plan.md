# Implementation Plan: Persistent deactivation: one activation ledger

**Branch**: `core-align-3-persistent-deactivation` (planning base and merge target; `single_branch` topology, WPs run in sequence in the repository root checkout) | **Date**: 2026-10-19 (revised after the post-plan squad) | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/persistent-deactivation-ledger-01M59YAA/spec.md`; core side of spec-kitty-charter ADR-0013 (spec-kitty-charter#62, #63, #64, #66, #67; corpus #9).

Branch contract: the current branch at plan start is `core-align-3-persistent-deactivation`; planning artifacts land on it and the completed mission is delivered on it as the PR branch (target `main` via PR, the operator merges). Restated: plan base = merge target = `core-align-3-persistent-deactivation`.

## Summary

One new file, `.kittify/charter/activation.yaml` (the **activation ledger**), becomes the only
authority for activation allow state (`activated_<plural>`, three-state; `activated_kinds`;
`mission_type_activations`) and deny state (`deactivated_<plural>`, omitted when empty).

- **One source resolver** in `kernel.activation_ledger_store` picks ledger, legacy or refusal. The
  activation seam (`charter.activation.activation_ledger`) and the offering-side SPDD probe both call it.
- **One required-floor reader** (the existing org-pack doc iterator, gaining per-pack provenance and
  one `extends:` walk) feeds both the deny exemption and the selection overlay. It reads strictly:
  an unreadable declared pack refuses.
- **One deny subtraction**, in identity space (`resolve_deny`), computed once in
  `PackContext.from_config` and used by every reader through an effective-membership accessor.
- The planners carry allow and deny in one plan and one write. A plain
  `deny_change: DenyListChoice` keyword on the ledger writer is the structural guard.
  `NoActivationRestrictionsError` is retired.
- **Cascade** stops at a denied node, reports it under "skipped, deactivated" (with `via_requires`),
  reports what lay behind it as "unreached", and `--include-deactivated` restores the full walk.
- **Required refusal**: deactivating an org-required artifact is refused, naming the pack(s).
- **Migration**: a new upgrade migration (`4.0.0rc8_activation_ledger`) moves the keys, verbatim, and can be
  re-run after a crash; `spec-kitty migrate activation-ledger` runs it narrowly (FR-021). Shipped migrations keep their legacy target through an upgrade-only scope.
  `spec-kitty init` writes the ledger for fresh projects. On an unmigrated project, reads stay on the
  legacy allow keys (as on `main`) and deny writes refuse naming `spec-kitty upgrade` (`mission_pivot_option_b`, 2026-10-20);
  the strict fail-closed read moves to the charter-contract alignment epic (epic child #6535: retire the legacy activation reader).
- **Proof**: a gate proves no migration or preset can remove a deny entry. The fixed answers are one
  portable conformance table, with a divergence register against the charter contract (FR-024); doctor
  and `charter list` surface required ids an explicit allow list omits (FR-023).

## Technical Context

**Language/Version**: Python 3.11+ (3.11 floor; CI also runs 3.13)
**Primary Dependencies**: ruamel.yaml (round-trip writes; kernel follows the `kernel.yaml_io` precedent), pydantic v2, typer + rich. No new dependency (DIRECTIVE_051: nothing to check).
**Storage**: Files only. The new `.kittify/charter/activation.yaml` is git-tracked: an optional tracked bundle member and an optional content-hash member. `charter.yaml` and `config.yaml` lose their activation keys through the migration.
**Testing**: pytest, ATDD-first. Each WP opens with failing acceptance tests for its FRs. Targeted surfaces are listed per WP, plus `make test-fast`, `tests/charter/`, `tests/charter_offering/`, the migration tests and the named architectural gates. Never the bare `tests/architectural/` directory (`NO_FULL_HEAVY_SUITES_IN_MISSION`).
**Target Platform**: The `spec-kitty` CLI in consumer repositories on Linux, macOS and Windows.
**Project Type**: Single Python project (`src/kernel`, `src/charter`, `src/specify_cli`).
**Performance Goals**: `charter activate`/`deactivate` < 2 s on this repository (NFR-003). Reads add one `stat` when the ledger exists. Effective deny (identity resolution plus the required floor) is computed once per `PackContext`, and only for kinds whose deny list is non-empty.
**Constraints**: C-001 to C-010. Layer chain `kernel <- charter <- specify_cli`. `charter.offering` never imports `charter.activation`. specify_cli reaches activation internals only through `charter.activation.api` or an existing baseline row. The 236-row activation boundary baseline does not grow and loses one row. Ruff, ruff-format and mypy show zero new findings; complexity ≤ 15; diff coverage ≥ 90 % (NFR-004).
**Scale/Scope**: ~45 production modules touched; 1 new migration; 1 new kernel module; 1 new charter module. 281 test files mention activation keys, and ~200 need re-seeding into the ledger (IC-12).

## Charter Check

*Charter: `.kittify/charter/charter.md` v1.5.0 (loaded). Re-checked after the post-plan squad.*

| Principle / rule | Verdict | How the plan meets it |
|---|---|---|
| Single canonical authority | PASS | **Store**: one ledger, one source resolver (kernel; the SPDD pointer replica is deleted). **Readers**: one required-floor reader, one deny subtraction (`resolve_deny`), one membership accessor on `PackContext`. **Bypasses removed**: the loaders in `consistency_check`, `list_activated`, `_synthesis`, `compiler._read_legacy_config_activation`, init provisioning and `rendering_inputs` all re-point to the seam. **Mirrors gone**: the hand-kept key mirrors are deleted or derived from `ArtifactKind`. |
| Architectural alignment (layers) | PASS | **Placement**: the seam sits in `charter.activation`; kernel holds only the path, the raw read, the resolver and the scope variable. **specify_cli access**: through the API, existing baseline rows, or kernel directly (`base.py`, `rendering_inputs`). **Baseline**: shrinks by one row. |
| DDD + tiered rigour | PASS | Algebra and planners are pure (data-model.md §2–3); CLI glue is thin. |
| ATDD-first / red-first | PASS | Each WP's first task writes the failing acceptance tests; SC-004 positive control: FR acceptance tests red on the base. |
| Terminology canon | PASS (watch) | The glossary gets an "Activation ledger" entry, guarded against confusion with the Migration Ledger, the decision ledger and the status event log. Use "Mission", never "feature". |
| DIRECTIVE_044 | PASS | No shipped migration edited; the scope wrapper and the new migration only. |
| Canonical sources | PASS | The ledger path is declared once (kernel) and re-exported from `charter.bundle`. |
| Kind vocabulary single authority | PASS | Keys derive from `ArtifactKind.activatable`; `ACTIVATION_YAML_KEYS` stays tuple-identical (pinned). |
| No aliases/shims | PASS | `NoActivationRestrictionsError` deleted at all nine sites. |
| Fail closed | PASS | Malformed ledger, an unmigrated project and an unreadable required floor all raise `ActiveCharterConfigError`. The three fail-open `PackContext` callers stop swallowing it (P2). |
| Adversarial squad | DONE | Post-plan squad (alphonso, robbie, randy, paula): every finding dispositioned in research.md §Squad findings. |
| Test policy / Sonar | PASS (watch) | Helpers are extracted around the planners and the cascade walk, with direct unit tests. |

No violation needs a Complexity Tracking entry.

## Project Structure

### Documentation (this mission)

```
kitty-specs/persistent-deactivation-ledger-01M59YAA/
├── spec.md, plan.md, research.md, data-model.md, issue-matrix.md
└── tasks/           # /spec-kitty.tasks output
```

### Source Code (repository root)

```
src/kernel/activation_ledger_store.py         # NEW: path, raw read, resolver (tolerant/strict via activation_strict()), legacy scope
src/charter/
├── bundle.py                                 # ACTIVATION_YAML, optional tracked + optional hash member
└── activation/
    ├── activation_ledger.py                  # NEW: vocabulary, typed load, write + deny_change guard, resolve_deny
    ├── activation_engine.py, pack_manager.py, pack_context.py, org_pack_discovery.py, org_charter.py
    ├── resolver.py, drg_activation.py, compiler.py, consistency_check.py, action_governance_bundle.py,
    │   active_charter_service_builder.py, profile_resolution.py, context.py,
    │   context_renderers/reference_pointers.py
    ├── cascade.py, preset_application.py, synthesizer/reach_only.py, charter_yaml_io.py, schemas.py
    └── api.py
src/charter/offering/spdd_reasons/activation.py
src/specify_cli/ (provisioning/default_charter.py, core/mission_creation_scaffold.py, skills/command_renderer.py,
   upgrade/{assessment.py,runner.py,registry.py,migrations/base.py,migrations/m_4_0_0rc8_activation_ledger.py,
   migrations/order_manifest.txt}, cli/commands/{upgrade.py,doctor.py,_charter_pack_collect.py,charter_bundle.py,
   profiles_cmd.py}, cli/commands/charter/{activate,deactivate,interview,list_cmd,generate,_synthesis,
   _resynthesis_preflight}.py, cli/commands/agent/{workflow_executor,mission_finalize_bootstrap,tasks_status_cmd}.py,
   review/gate_bindings.py, mission_step_contracts/executor.py, charter_runtime/{preflight/runner.py,freshness/computer.py},
   invocation/{registry.py,empty_charter.py}, state/contract.py)
tests/_factories/activation_ledger.py         # NEW seed/read helpers (red-signal fixture lives in tests/conftest.py, D0)
tests/charter/conformance/                    # NEW FR-015 table + runner
tests/architectural/test_deny_list_survives_upgrade.py, test_no_raw_activation_membership.py   # NEW gates
docs/adr/4.x/2026-10-19-1-activation-ledger-persists-deactivation.md                           # NEW ADR
```

## Implementation Concern Map

> Concerns are not work packages; the slicing follows the map. Anchors verified against the
> working tree on 2026-10-19 (post-squad).

### IC-01 — Kernel floor: path, raw read, the one source resolver, legacy scope

- **Purpose**: a single, layer-neutral answer to "where is activation read and written" (R2, design questions 1–2).
- **Relevant requirements**: FR-001, FR-017, C-002, C-003.
- **Affected surfaces and design** — `src/kernel/activation_ledger_store.py` (NEW; ruamel safe loader as in `kernel/yaml_io.py`, m7):
  - `ACTIVATION_LEDGER = Path(KITTIFY_DIRNAME, "charter", "activation.yaml")` (`KITTIFY_DIRNAME` from `kernel/charter_pack_paths.py`) and `activation_ledger_path(repo_root)`. `charter/bundle.py` re-exports it as `ACTIVATION_YAML` beside `CHARTER_YAML` (`bundle.py:52`); no other module spells the literal.
  - `read_activation_ledger_raw(repo_root) -> dict | None`: `None` when absent, `{}` for a zero-byte file, `ActivationLedgerFormatError(KittyInternalConsistencyError)` on a YAML error or a non-mapping root.
  - **Scope (M3)**: `_LEGACY_SCOPE: ContextVar[frozenset[Path]]`. `legacy_activation_scope(repo_root)` is re-entrant and records both `repo_root.resolve()` and the canonical repository root. The canonical root comes from a kernel-side mirror of the rule `charter.resolution.resolve_canonical_repo_root` applies; readers canonicalise at `charter/activation/sync.py:102`/`:215` and `m_3_2_0rc35_unified_bundle.py:157`. `in_legacy_activation_scope(repo_root)` matches either form. The kernel cannot import `charter.resolution`, so the scope accepts an optional `canonical_root` that `base.py` passes (resolved in specify_cli).
  - **Transition model (D0, post-tasks squad; superseded at the flip by the one-mode resolver of IC-13, `mission_pivot_option_b`)**: one kernel function `activation_strict()` selects the resolver's mode. Until the flip WP it reads the env var `SPEC_KITTY_ACTIVATION_STRICT` (unset = tolerant, `"1"` = strict, `"test"` = strict + raise on stray legacy keys beside a ledger); an env var reaches subprocess CLI tests and threads (F4). **In-Mission only**: the flip WP (WP14, IC-13) does **not** make strict unconditional. It deletes the variable and every reference to it (gate: no reference left in `src/` or `tests/`) and ships the one-mode resolver of IC-13 / data-model.md §5.
  - **The kernel never raises an activation-domain error**: it returns the pointer path, `pointer_exists` and raw data; callers keep their golden error texts (`pack_context.py:570` `_config_error`, `pack_manager.py:658`, SPDD `_SpddActivationConfigError`). Only `ActivationLedgerFormatError` (raw read) is a kernel raise.
  - **The one resolver (R2)**: `resolve_activation_source(repo_root, *, legacy_keys: frozenset[str]) -> ResolvedActivationSource`. **Shipped (after WP14)**: `source` is `LEDGER | LEGACY`, plus an `unmigrated` flag, `pointer`, `pointer_exists` and `stray_legacy_keys`; see IC-13 and data-model.md §5. The two transition modes below exist **in-Mission only** (WP02–WP10):
    - **tolerant** (default until the flip) = today's storage exactly: ledger exists → `LEDGER`; otherwise → `LEGACY` (today's pointer rule, reads and writes, blank fixtures included). The legacy save accepts `deactivated_<kind>` keys in tolerant mode (temporary), so deny semantics work on legacy-shaped fixtures; `init` keeps today's provisioning;
    - **strict** (in-Mission test mode only; never shipped): ledger exists → `LEDGER`; no ledger + in scope → `LEGACY` byte-for-byte (string-only `charter:` pointer, the `pack_context.py:306-334` rule moved here); no ledger + outside the scope + `legacy_keys` present → `UNMIGRATED` (the activation seam raises `ActiveCharterConfigError` naming both files, the keys and `spec-kitty upgrade`); neither → `LEDGER` (`exists=False`; `init` writes the ledger). Legacy saves refuse deny keys (C-003).
  - **NFR-003**: the legacy-key probe is cached per process keyed on `(path, mtime, size)`.
  - **Late legacy writes (P10)**: when the result is `LEDGER` and legacy activation keys sit beside the ledger, `resolve_activation_source` returns `stray_legacy_keys`. The activation seam emits one warning per process through the existing warnings/console path (never a bare `print` in library code; JSON outputs stay clean): the keys are ignored and the ledger wins. Under `SPEC_KITTY_ACTIVATION_STRICT=test` it raises instead (test red signal, F5).
  - `pack_context.resolve_charter_yaml_pointer` (`pack_context.py:306`) becomes a thin call into the kernel pointer helper (kept for its existing importers).
- **Sequencing**: first code concern.
- **Risks**: the kernel README lists the module. `test_no_dead_symbols` needs cross-module importers: activation, the offering probe, `base.py` and `command_renderer`.

### IC-02 — The ledger seam `charter.activation.activation_ledger`

- **Purpose**: vocabulary, typed load, write and guard in one module (design question 1, R1).
- **Relevant requirements**: FR-001, FR-002, FR-014 (structural half), C-003, C-004.
- **Affected surfaces and design**:
  - **Vocabulary (FR-002)**: `allow_key(kind)` and `deny_key(kind)`. `ALLOW_KEYS` keeps the exact order of today's `pack_manager.ACTIVATION_YAML_KEYS` (`pack_manager.py:183-186`), which is now defined as `activation_ledger.ALLOW_KEYS`; a tuple-equality pin goes into `tests/charter/test_activation_vocabulary_setequal.py` (m1). Also `DENY_KEYS` (activatable kinds, enum order) and `LEDGER_KEYS`.
  - `load_activation_ledger(repo_root) -> ActivationLedger` (data-model.md §1), typed and frozen:
    - an unknown **non-deny** key, a non-list value or a non-string id → `ActiveCharterConfigError`;
    - an unknown `deactivated_<x>` key (written by a later CLI for a newer kind) is kept verbatim and reported in `ActivationLedger.unknown_deny_keys`; doctor warns about it (P15).
  - `prepare_ledger_write(repo_root, values, *, remove=(), deny_change: DenyListChoice | None = None) -> PreparedYamlWrite` (R1):
    - **file handling**: ruamel round-trip keeps comments and order; new keys are appended in `LEDGER_KEYS` order; an empty deny list is removed; the CAS check goes through `observe_yaml_input`/`prepare_yaml_write`/`apply_yaml_write` (`charter_yaml_io.py:67,142,178`);
    - **guard**: compares each deny key's **normalised** set before and after (absent == `[]` == `null`, P13). Any difference while `deny_change is None` raises `DenyListWriteRefused` and writes nothing. Unknown deny keys pass through untouched;
    - **legacy saves**: refuse a non-`None` `deny_change` (C-003).
  - `DenyListChoice` (`ACTIVATE`, `DEACTIVATE`, `CASCADE_INCLUDE_DEACTIVATED`, `PRESET_FORCE`) goes into `pack_manager.__all__` and onto `charter.activation.api` (m5).
- **Re-pointing**:
  - `pack_context._load_charter_activation_source` (`pack_context.py:556-581`) returns the ledger mapping or the legacy mapping, as the resolver decides.
  - `pack_manager.resolve_activation_write_target` (`pack_manager.py:629-671`) keeps its `(path, data, save)` triple, which the shipped rc35 migration consumes. For `LEDGER` it returns the ledger path, the ledger's round-trip mapping and `_save_ledger(path, data, *, deny_change=None)`; for `LEGACY` it runs today's code moved verbatim.
  - `prepare_activation_write` (`:674-705`) gains `deny_change`.
  - `list_activated` (`:915-946`) reads `load_activation_ledger`.
  - `consistency_check._load_raw_activation_source` / `_load_config_yaml_mapping` (`consistency_check.py:340-394`) are replaced by the seam's mapping.
  - The SPDD probe's `_resolve_charter_pointer`/pointer branch (`charter/offering/spdd_reasons/activation.py:141-147, 171-184`) is replaced by the kernel resolver, which deletes the replica. The early `False` for a missing `config.yaml` (`:128-138`) stays (m3). Deny subtraction there is IC-06.
- **Sequencing**: IC-01.
- **Risks**: `_save_ledger` must accept the same positional call `commit_plan` uses. A deny-bearing plan passes `deny_change` by keyword (IC-04).

### IC-03 — Writers outside the manager that target activation (B1, M1)

- **Purpose**: every activation write path goes through the seam; fresh projects are never "unmigrated".
- **Relevant requirements**: FR-001, FR-017.
- **Affected surfaces and design**:
  - **B1 init**: `specify_cli/provisioning/default_charter.provision_default_mission_type_activations` (`default_charter.py:47-89`, called at `cli/commands/init.py:1456`) has its own ruamel write to `config.yaml`. It moves onto `charter.activation.compiler.provision_mission_type_activations` (or `prepare_activation_write` through the existing `default_charter.py -> charter.activation.compiler` baseline row), so a fresh `init` writes `mission_type_activations` to the ledger. The init seed records every migration, including the rc8 one, as applied. That is now correct, because a fresh project never has legacy keys.
  - `core/mission_creation_scaffold.py:147`: the message names `.kittify/charter/activation.yaml` instead of `config.yaml`.
  - **M1 rendering identity**: `skills/command_renderer.rendering_inputs` (`command_renderer.py:517-542`) includes the ledger path whenever the resolver says `LEDGER`, as the last element (kernel import; no baseline row). `validate_mission_provisioning` (`:545-565`) compares against it. `upgrade/assessment.py:127` and `skills/command_installer.py:887-895` (provisioning target == `rendering_inputs()[-1]`) and `skills/installer.py:375-399` follow.
  - **m6** (moved to the migration concern IC-08 / WP08 by the post-tasks squad): `upgrade/assessment.prepare_upgrade_repairs` (`assessment.py:121-127`) builds a CAS provisioning write before migrations run. Inside the scope with no ledger it targets the legacy surface, which the ledger migration then moves, so the CAS would be stale. The finalizer therefore re-prepares the provisioning write after the migrations (`cli/commands/upgrade.py:1050-1100`, `_finalizer_step_provision`), and a test pins the ordering.
- **Sequencing**: IC-02.
- **Risks**: init writes the ledger in strict mode only (D0); in tolerant mode it keeps today's provisioning. The init acceptance test (`init → charter context → mission create → upgrade is a no-op`) runs strict (its file is listed in `SWEPT_PREFIXES`) here and unconditionally after the flip.

### IC-04 — Required floor, planners, manager, deactivate CLI

- **Purpose**: one algebra and one write per command; required refusal (design questions 4, 6).
- **Relevant requirements**: FR-006, FR-007, FR-008, FR-009 (promotion seam), FR-012 (CLI), FR-013, C-005, C-008.
- **Affected surfaces and design**:
  - **Required floor (R3)** in `org_pack_discovery.py`:
    - `_iter_org_charter_docs` (`:136-169`) yields `(declared_pack, member_pack, raw)` and walks each declared pack's `extends:` chain once, through `charter.offering.packs.extends.resolve_extends_order`;
    - `read_org_required_ids` (`:216-230`) gains a sibling `read_org_required_provenance(repo_root, kind, *, strict) -> dict[str, tuple[RequiringPack, ...]]`;
    - `_read_org_required_selections` (`:197-214`) reads the same iterator, so the overlay union and the deny exemption agree;
    - the strict mode used by deactivation and by effective deny refuses with `ActiveCharterConfigError` when a declared pack's `org-charter.yaml` is unreadable or malformed, or its `extends:` chain cycles or dangles (the `require_org_skill_policy_readable` precedent, `org_pack_discovery.py:248`). It never silently widens;
    - ids are normalised to stems with `org_charter._normalize_required_ids` (`org_charter.py:294`);
    - no change to `_fold_policies`, `resolve_pack_chain` or `_resolve_chain` (C-005);
    - the overlay gaining `extends:`-inherited requirements is a recorded behaviour alignment (research.md D-18).
  - **`ActivationPlan`** (`activation_engine.py:156-192`) gains `deny_key`, `new_deny_list` and `deny_change`. The reporting deltas (`reactivated`, `deny_added`) are **computed** from the before/after deny lists by one helper `deny_delta(before, after)`; they are not stored on four types (R11). `commit_plan` (`:484-525`) assigns both keys and calls `save(path, data, deny_change=plan.deny_change)` once.
  - **Planners** (semantics in data-model.md §3):
    - `plan_activation` (`:251-410`) handles four cases: a deny-only plan (absent "all" list), materialise-then-append (absent "required" list, i.e. skills), clear-then-append (`[]`/list), and `--only`, which clears the named id only;
    - `plan_deactivation` (`:413-481`) gains `available_ids` and `required_by`; its first step is the refusal seam `check_deactivation_permitted` (`RequiredArtifactDeactivationError`, a `DeactivationRefused` subtype);
    - `_plan_promotion`/`promote_activations` (`:597-731`) skip effective-denied ids (`required_exempt` from the caller) and report them in `PromotionOutcome.skipped_denied`.
  - **Retire `NoActivationRestrictionsError`** (m2), at all sites:
    - definition `activation_engine.py:113-146`;
    - `pack_manager.py:50` (docstring), `:78` (import), `:859`, `:887` (docstrings), `:1137` (`__all__`);
    - `specify_cli/cli/commands/charter/deactivate.py:17` (docstring), `:31` (import), `:201`, `:311`;
    - tests `tests/charter/test_pack_manager.py`, `test_skill_activation.py`, `test_pack_manager_catalog.py`, `test_activation_engine.py`, `tests/specify_cli/cli/commands/charter/test_charter_deactivate_commands.py`.

    `RequiredArtifactDeactivationError` and `RequiringPack` take its place in `pack_manager.__all__`.
  - **Manager** (`pack_manager.py`):
    - `ActiveCharterManager.activate` (`:737-843`) gains `reinstate: DenyListChoice = ACTIVATE`;
    - `deactivate` (`:845-913`) gains `record_exclusion: bool = True`;
    - `_preservation_set` (`:430-478`) subtracts effective deny;
    - deny entries are written in stem spelling through `IdentityIndex.stem` (as `--only` does at `:527-529`).
  - **`org_charter._promote_org_required_to_config`** (`org_charter.py:404-484`) passes its ids as `required_exempt`.
  - **Deactivate CLI** (`deactivate.py`):
    - direct path (`:304-311`): refusal → red error naming pack(s) and policy key, exit 1, ledger byte-identical; already denied → warning, exit 0;
    - `_render_cascade_deactivation` (`:157-241`) runs even when the named id was implicit (the gate at `:335-341` is removed). It calls `manager.deactivate(..., record_exclusion=False)` per child (`:194`) and renders required children as "skipped (required by <pack>)". Under an absent allow list each child is rendered as "still active (no allow-list; only <P> excluded)" (P11);
    - `_active_urns` (`:113-155`) counts the effective allow state (C-007).
  - **Boundary baseline**: drop the drained row `deactivate.py -> charter.activation.activation_engine` from `tests/architectural/charter_activation_boundary_baseline.yaml` and lower `tests/architectural/_baselines.yaml:26` from 236 to 235.
- **Sequencing**: IC-02.
- **Risks**: `plan_activation` is near the complexity ceiling, so `_deny_branch` and `_materialise_absent` are extracted with unit tests. Deactivation and promotion always read the strict floor; the read path reads it (and fails closed) only when the kind's deny list is non-empty, the only case where it changes the answer (NFR-003, spec edge case amended for analyze M2/M5).

### IC-05 — Deny in identity space; `PackContext` membership; charter-side readers (R4/R5, M2, P6, P7)

- **Purpose**: every charter read path subtracts the same effective deny, spelled the way the reader filters.
- **Relevant requirements**: FR-016, FR-006, US1.6.
- **Affected surfaces and design**:
  - **`resolve_deny(kind, tokens, identity: IdentityIndex) -> DenySet`** (`activation_ledger`) returns stems, declared ids and DRG URNs together (#6406 identity index, `charter/activation/identity_index.py`). `effective_deny` stays private (deny − strict required floor).
  - **`PackContext`** (`pack_context.py:96-200`, `from_config` `:205-288`):
    - `denied` holds a sorted, hashable tuple of `(plural, DenySet)` pairs, computed once at construction and only for kinds with a non-empty deny list;
    - present allow lists are netted in identity space;
    - new accessors: `denied_for(kind)`, `admits(kind, token, *, available) -> bool` and `effective_ids(kind, available) -> frozenset[str]` (allow, or absent default, minus deny). These are the effective-membership accessor of M2;
    - `deactivated_urns` is a property derived from `denied` (R5), so the cascade, the DRG filter and the resolver share one answer;
    - `_absent_key_default` (`:735-744`) and `explicit_activated_skills` (`:724-732`) return deny-netted sets; their consumers `charter/activation/skill_preparation.py:250,290` (skill projection) follow, and `specify_cli/skills/catalog.py` (which consumes the prepared projection) needs no change of its own beyond a test.
  - **Charter readers moved onto the accessor**:
    - `resolver._gated` (`resolver.py:217-245`) and the root helpers (`:683-706`, `:802-840`);
    - `drg_activation._resolve_activated_urns_for_kind` / `_node_is_activated` (`drg_activation.py:294-444`). The mission-step branch (`:419-425`) returns on the mission-type check before the per-id gate, so a denied `mission_step_contract` is now checked first (P6);
    - `compiler._resolve_config_activated_roots` (`compiler.py:192-290`); `_CONFIG_ACTIVATION_FIELDS` (`:139-147`) is derived from the enum;
    - `action_governance_bundle._catalog_default_or_activated` (`action_governance_bundle.py:53-91`), `_graph_and_catalog_default_ids` (`:94-160`) and `_seed_sets` (`:173-205`). These widen absent lists to catalog ∪ graph ids and now subtract deny; also `:413`;
    - `active_charter_service_builder` (`:217-268`) and `profile_resolution` (`:62`, `:164`);
    - `org_pack_discovery._load_governance_charter_config` (`org_pack_discovery.py:291-343`) subtracts deny after the required union (US1.6);
    - `consistency_check` treats denied ids as inactive.
  - **P7 include selectors and references**:
    - `context.build_charter_context_include` (`context.py:374-490`) gates `--include <kind>:<id>` and `artifact:<id>` for every kind, not just agent_profile/glossary_pack (`:432`). A denied id renders `"<kind>:<id> is deactivated in this project (charter activate <kind> <id> restores it)"` and exits 0;
    - `context_renderers/reference_pointers._load_references` (`reference_pointers.py:247`) and the selection over it (`:94-245`) drop references whose target is denied, so a skipped recompile (`--no-compile`) cannot leak a denied artifact.
  - **Gate (M2)**: `tests/architectural/test_no_raw_activation_membership.py` AST-scans `src/` for `.activated_<plural> is None` / `is not None` / `in <ctx>.activated_<plural>` outside `pack_context.py`, `activation_ledger.py` and an empty allowlist. It fails on new raw membership checks; a self-mutation test proves non-vacuity.
- **Sequencing**: IC-04 (strict floor).
- **Risks**: the resolver's per-kind cache keys deny separately. The conformance rows cover a stem that differs from its declared id, and an allow list in declared-id spelling with deny in stem spelling (R4).

### IC-06 — specify_cli readers, fail-open callers, mission-step executor, SPDD deny (M2, P2, P6)

- **Purpose**: the CLI-side consumers use the membership accessor and stop swallowing activation errors.
- **Relevant requirements**: FR-016, FR-017.
- **Affected surfaces and design**:
  - **P2 fail-open → fail-closed**: `ActiveCharterConfigError` (including the unmigrated refusal) propagates like `OrgPackEnvVarUnsetError`; each caller gets a test. Sites:
    - `review/gate_bindings._resolve_pack_context` (`gate_bindings.py:238-251`);
    - `mission_step_contracts/executor._resolve_pack_context` (`executor.py:593-608`);
    - `charter_runtime/preflight/runner.py:221-224`. Its never-raise contract becomes "never raise except activation-store errors".
  - **P6**: `executor.py:184` filters `_contracts.get_by_action(...)` through `pack_context.admits(MISSION_STEP_CONTRACT, id)`. A denied contract is reported as not runnable and is never picked.
  - **M2 call sites moved onto `admits`/`effective_ids`**:
    - `invocation/registry.py:59-142` and `invocation/empty_charter.py:84`;
    - `cli/commands/agent/workflow_executor.py:715` (implement precondition), `mission_finalize_bootstrap.py:82` and `tasks_status_cmd.py:75`;
    - `cli/commands/profiles_cmd.py:25-37, :173, :332`.
  - **SPDD probe deny** (`spdd_reasons/activation.py:150-167`): the deny keys come from the kernel raw read. The directive deny reuses `_is_directive_038` normalisation (m3). The required floor is not applied (residual, D-07).
  - `cli/commands/charter/_synthesis.py:606-625, 741-752`: `_ACTIVATION_SIGNAL_KEYS` is deleted; the probe reads `load_activation_ledger` through the API, and a non-empty deny list also counts as established.
  - `cli/commands/charter/list_cmd.py:270`: the deactivated column comes from `ActivationLedger` via the API (R12; no `list_deactivated`).
- **Sequencing**: IC-05.
- **Risks**: `preflight/runner.py` gains a raising path. The acceptance runs cover `charter context`, implement preflight, the review gate and the mission-step executor with a malformed ledger, which must fail closed.

### IC-07 — Cascade (FR-010/011/012) and the non-explicit writers (FR-008/009)

- **Purpose**: the cascade stops at and reports exclusions; promotion, presets and synthesis never re-add them.
- **Relevant requirements**: FR-008, FR-009, FR-010, FR-011, FR-022 (analyze pass 7 M3; operator ruling `mission_type_cascade_source`, folded into WP07 rather than a new WP).
- **Mission type as a cascade source (FR-022)**:
  - `charter activate mission-type X --cascade <scope>` walks the mission type's DRG node with the same scope, skip-and-report and stop-at-deny rules as an artifact source: its action-sequence `requires` steps, type-wide `scope` governance and `instantiates` templates.
  - The source URN is derived by `_source_urn` for both artifact and mission-type sources.
  - On the deactivate side, the C-005 shared-reference count treats an active mission type as a referencing source.
  - Without `--cascade`, the no-cascade warning lists everything the mission type references.
- **Affected surfaces and design**:
  - **Cascade engine** (`cascade.py`):
    - `_reference_adjacency` (`:275-281`) keeps `Relation`;
    - `_forward_reference_closure` (`:253-272`) gains `blocked: frozenset[str]`: a denied node is recorded but not expanded, and its `REQUIRES` edges are not followed (P12);
    - `ReferencedArtifact` (`:328-337`) gains `via_requires` and `required_by` and is **reused** for the skipped bucket (R10);
    - `CascadeActivationResult` (`:346-368`) gains `skipped_deactivated: dict[str, list[ReferencedArtifact]]` and `unreached_behind_deactivated: dict[str, list[str]]` (P12). The latter holds nodes reachable in the full walk but only through denied nodes;
    - `cascade_activation_targets(graph, source_urn, scope, *, deactivated_urns=frozenset(), include_deactivated=False)` (`:371-412`). With the opt-in it walks the full graph and returns the formerly denied nodes in `activated`; the "reinstated" report comes from the deny delta (R11);
    - invariant test: every node of the **full** walk lands in exactly one of `activated`, `skipped_by_scope`, `skipped_deactivated`, `unreached_behind_deactivated`, `not_cascaded_kind_filtered`;
    - `NoCascadeReport` / `referenced_but_not_cascaded` (`:421-500`) list denied nodes as deactivated.
  - **Activate CLI** (`activate.py`):
    - `--include-deactivated` next to `--cascade` (`:866-910`), refused without `--cascade`;
    - `_render_cascade_activation` (`:237-341`) takes `pack_context.deactivated_urns`, runs the engine at `:268` and calls `manager.activate(..., reinstate=CASCADE_INCLUDE_DEACTIVATED)` at `:280`;
    - new headings "Skipped, deactivated" (with the requires flag) and "Unreached (behind a deactivated artifact)" beside "Skipped (out of scope)" (`:300-308`). The zero-target summary (`:337-341`) and `_render_no_cascade_warning` (`:386`) account for both.
  - `_resynthesis_preflight.py:80` passes `deactivated_urns`.
  - **Presets** (`preset_application.py`):
    - `_target_state` (`:482-494`) partitions preset-listed ids into kept and denied;
    - without `--force`, denied ids are left out and named in a warning;
    - with `--force`, `apply_preset_plan` (`:594-607`) clears them through `prepare_activation_write(..., deny_change=PRESET_FORCE)` and keeps them in the allow lists. `PresetPlan` gains `denied_listed`; the cleared list comes from the deny delta;
    - CLI rendering at `activate.py:790-855`; `restamp_bundle_hash` after the write;
    - `GOVERNED_KEYS` (`:106`) stays allow-only.
  - **Synthesis**: `synthesizer/reach_only.append_synthesized_tactic_activations` (`reach_only.py:115-165`) returns the skipped-denied tactics, and never re-adds a denied tactic, even on first creation.
  - **Interview**: `cli/commands/charter/interview.py:100-199` (`promote_activations` at `:187`) prints "kept deactivated".
- **Sequencing**: IC-05 (`deactivated_urns`), IC-04 (`reinstate`).
- **Risks**: `tests/charter/test_cascade.py` (37 tests) gets new empty buckets by default; `--force` now does two things, and the help text says both.

### IC-08 — Ledger migration, upgrade-only scope, dogfood (FR-003/004/017)

- **Purpose**: move projects to the ledger, keep shipped migrations unchanged, survive a crash (design questions 2, 8).
- **Relevant requirements**: FR-003, FR-004, FR-017, NFR-001, NFR-002, C-001.
- **Affected surfaces and design**:
  - **Scope entry (M4)**:
    - `BaseMigration.__init_subclass__` (`upgrade/migrations/base.py:74`) wraps every public method each subclass defines in its own `cls.__dict__` and that takes `project_path` first: `detect`, `can_apply`, `apply` (`:199`), and the rc6 `structural_detect` / `is_first_application` (`m_4_0_0rc6_charter_pack_cutover.py:912-934`) as well as `reselect_when_recorded`. The wrapper uses `functools.wraps`, is re-entrant and passes the project path positionally. `base.py` imports the scope from **kernel** directly.
    - The selection entry points also enter it: `MigrationRegistry.get_applicable` (`upgrade/registry.py:87-130`), `MigrationRunner.upgrade` (`runner.py:170-312`, selection at `:364`), worktree selection (`:573`), and the `spec-kitty migrate ledger` read surface (`cli/commands/migrate_cmd.py:1773`).
    - The `spec-kitty upgrade` command body (`cli/commands/upgrade.py`) enters it too, which covers dry-run preview (`:515`) and repairs. The finalizer provisioning (`:1050`) runs **after the legacy scope closes**, so a keyless project resolves as fresh (WP08 T049.3, IC-13, data-model §5; pass-9 M1).
  - **Worktree test (M3)**: upgrade a lane worktree while the main checkout is unmigrated; the scope matches the canonical root.
  - **New migration** `upgrade/migrations/m_4_0_0rc8_activation_ledger.py`: `migration_id = "4.0.0rc8_activation_ledger"`, `target_version = "4.0.0rc8"` (`pyproject.toml:3`), `clone_local_effect = False`, no `runs_first`, `runs_on_worktrees = False`. It is appended after `4.0.0rc7_track_charter_pack_yaml` in `order_manifest.txt` (no `# tie:`).
  - **Planner and apply** (`activation_ledger.plan_ledger_migration` / `apply_ledger_migration`, exported on the API in this concern):
    - **surfaces**: authority (pointer `charter.yaml`, else `config.yaml`), a leftover `config.yaml` copy, an existing ledger;
    - **comparison**: per key, order-insensitive, keeping all three states;
    - **legacy deny keys refuse** (analyze pass 2, H2/H3): the migration moves allow keys only (`deny_change=None`); a `deactivated_<kind>` key on any legacy surface (possible only in the in-mission tolerant mode, which never ships) refuses, naming key and file, nothing written. No migration ever touches deny keys (operator ruling `deny_writers`);
    - **refusal**: two differing values refuse, naming the key and the files. This includes "authority lacks the key, stray copy has it" (operator ruling `stray_config_copy`) and "ledger and legacy differ";
    - **when a ledger exists**: legacy keys **equal** to the ledger are stripped (P9);
    - **apply order (P9; as shipped by WP08)**: ledger write (allow keys only, `deny_change=None`) → stamp the synthesis manifest with the post-strip bundle hash → strip `charter.yaml` (`prepare_charter_yaml_section(..., remove=)`) → strip `config.yaml`. Stamping before the strip keeps a legacy key on disk in every crash window, so a re-run recovers, and crash-injection tests sit between every step;
    - NFR-001 holds per refusal; NFR-002 holds on a second run.
  - **m6 ordering** (from IC-03): the finalizer re-prepares the provisioning write after migrations (`cli/commands/upgrade.py:1050-1100`), with a test pinning the order.
  - **Repository-reading tests (H1)**: `tests/charter/test_config_stem_parity.py` and `tests/charter_offering/test_project_charter_single_owner.py` read this repository's `.kittify` activation keys raw; the dogfood commit re-points both to `load_activation_ledger` (via `charter.activation.api`).
  - **Narrow move command (FR-021, operator ruling `dogfood_migration_path`, analyze pass 4 H1)**: `spec-kitty migrate activation-ledger [--dry-run] [--json]` in `cli/commands/migrate_cmd.py`, beside `migrate backfill-*`.
    - It is a thin shell over `plan_ledger_migration` / `apply_ledger_migration`, with the same divergence and legacy-deny-key refusals. It is idempotent; `--dry-run` lists the moves. It runs inside the legacy scope.
    - On success it writes the `success` row for `4.0.0rc8_activation_ledger` **only when `.kittify/migration-ledger.jsonl` already exists** (ledger-adopted project), through the ledger module's writer. With no migration ledger it records nothing (`ledger_record: "not_recorded"`), because creating the file would flip `metadata._ledger_adopted` and drop `metadata.yaml`'s `migrations:` history before the backfill reads it. A later `spec-kitty upgrade` then still selects rc8; its `detect()` is False, nothing moves, and the runner records `skipped` (carry-forward M2; binding source: WP08 T051.2).
    - It needs help text, a completion-manifest regeneration and tests. The docs land in WP15 (`docs/api/cli-commands.md`).
  - **Dogfood (P15, H1)**: this repository has no migration ledger (`migrate ledger --json`: 125/125 pending), so the dogfood **never runs `spec-kitty upgrade`**.
    - It runs `spec-kitty migrate activation-ledger --dry-run`, then `spec-kitty migrate activation-ledger`. It stops only if the move reports a divergence or a legacy deny key.
    - It commits only `.kittify/charter/activation.yaml`, the edited `charter.yaml` (and `config.yaml` if it held keys), the restamped `synthesis-manifest.yaml`, the migration-ledger record if one was written, and the two re-pointed repository-reading tests.
    - The flip WP refuses to start unless `.kittify/charter/activation.yaml` exists here.
- **Sequencing**: IC-03, IC-04.
- **Risks**: the rc35 raw `yaml.dump` (`m_3_2_0rc35_activate_builtin_mission_types.py:221`) writes legacy surfaces before the ledger exists; the ledger migration moves the result. The rc5-era full-manifest acceptance test (SC-002) is in this concern.

### IC-09 — Bundle membership (FR-018) and doctor (FR-005)

- **Purpose**: the ledger is part of the bundle identity; doctor reports divergence (design questions 8, 9; M5, P14, R12).
- **Relevant requirements**: FR-005, FR-018.
- **Affected surfaces and design**:
  - **Bundle (M5)**:
    - `CharterBundleManifest` (`bundle.py:84-130`) gains `optional_tracked_files: list[Path]` (validated disjoint from `tracked_files`/`derived_files`); `CANONICAL_MANIFEST` (`:133-140`) lists `ACTIVATION_YAML` there and keeps `tracked_files` unchanged, so `charter_bundle.validate` (`cli/commands/charter_bundle.py:323-400`, `require_tracked=True` at `:364`), `generate.py:430, 645-655` and the shipped `m_3_2_0rc35_unified_bundle.py:185-248` behave as today;
    - `charter_bundle.validate` reports the optional file as present or absent without failing;
    - `BUNDLE_OPTIONAL_CONTENT_HASH_FILES = (ACTIVATION_LEDGER.name,)` (derived from the kernel constant; no new `"activation.yaml"` literal, M5; the path-literal gate keeps an empty allowlist for the ledger name): `compute_bundle_content_hash` (`bundle.py:148-200`) appends the ledger digest only when the file exists, so an out-of-band edit is detected (P14);
    - writers keep calling `restamp_bundle_hash` after a successful write;
    - `charter_runtime/freshness/computer.py:221` gains `_OPTIONAL_BUNDLE_FILES` (derived from `ACTIVATION_LEDGER`, no literal), parse-checked at `:565-600`; `tests/specify_cli/charter_freshness/test_computer.py::test_bundle_file_lists_stay_in_sync` pins both pairs; the `charter_path_literal_allowlist.yaml:127` rationale is refreshed if its token moves;
    - `state/contract.py:563` declares the ledger surface with its `path_pattern` derived from `ACTIVATION_LEDGER` (no literal; analyze pass 4 L3).
  - **Doctor (R12)**: `_run_activation_ledger_check(report, repo_root)` in `_charter_pack_collect.py`, modelled on `_run_retired_governance_key_check` (`:1101-1131`). It is wired in `doctor.py` `charter_packs_check` (`:1153`) and rendered at `:1168`/`:1206`. Findings:
    - one error code `ACTIVATION_STORE_ERROR` carrying the seam's `ActiveCharterConfigError.body` (malformed, unmigrated, unreadable required floor);
    - `LEGACY_KEYS_PRESENT` (error; the ledger wins). It is computed from the resolver's `stray_legacy_keys` **data**, never through the raising read path, so it is reported in strict test mode too (M2);
    - the three spec warnings: `DENY_UNKNOWN_ID`, `DENY_REQUIRED_ID` (names packs) and `DENY_SELECTED_ID`;
    - `UNKNOWN_DENY_KEY` is reported with the warnings (P15).

    It goes through `charter.activation.api` (`ledger_findings`, exported in this concern).
- **Sequencing**: IC-08.
- **Risks**: none beyond the manifest-model test (`tests/charter/test_bundle_manifest_model.py`).

### IC-10 — FR-014 gate and FR-015 conformance table

- **Purpose**: prove no migration or preset can remove a deny entry, and freeze the fixed answers (design questions 6, 12).
- **Relevant requirements**: FR-014, FR-015, SC-003.
- **Affected surfaces and design**:
  - **Gate** `tests/architectural/test_deny_list_survives_upgrade.py` (NEW):
    1. **static**:
       - AST-scan `src/specify_cli/upgrade/migrations/**`, `src/charter/activation/preset_application.py` and the preset YAML under `packs/built-in/presets/`;
       - fail on a `deactivated_` string constant, on `DENY_KEYS`/`deny_key`, and on any call passing a non-`None` `deny_change=` outside an exact allowlist, given by function name: `preset_application.apply_preset_plan` (the `--preset --force` path, which may reference `DENY_KEYS`/`deny_key`), `ActiveCharterManager.activate`, `ActiveCharterManager.deactivate`, and the cascade reinstate path in `activate.py` (L4). No migration may reference a deny key or pass a non-`None` `deny_change`;
       - the allowlist is asserted exact;
       - **classifier (R12, F16)**: a migration is activation-touching when it imports `charter.activation` or names the activation-ledger path (`activation.yaml` / `ACTIVATION_LEDGER`) or a `LEDGER_KEYS` key; the bare word "ledger" (Migration Ledger) never matches. That covers 10 modules today, plus `_charter_pack_cutover_snapshots.py` (m4), plus the new one. The rest are not applicable by derivation (no hand table);
    2. **dynamic**:
       - assert `len(registry) == len(order_manifest entries)`;
       - every activation-touching migration gets a builder that makes `detect()` true (asserted); it runs on a post-ledger fixture with deny entries for directive, tactic and skill and allow lists equal to the frozen cutover default snapshots (the #66 reset shape); the deny keys are byte-compared on disk afterwards;
       - **pre-ledger-shaped migrations (F8, revised in analyze pass 3, M3)**: every activation-touching migration runs on a post-ledger fixture with deny entries wherever it applies, and leaves the ledger's deny bytes unchanged. That includes `m_3_2_x_normalize_activation_absence` and every migration ledger-diff selection can re-select (`skipped`/`failed` records, `registry.py:130`, `reselect_when_recorded`). The ordering exemption ("ordered before `4.0.0rc8_activation_ledger`") is allowed only for a migration whose `detect()` cannot be made true once a ledger exists, which the gate proves by calling `detect()` on the post-ledger fixture. SC-003 is unchanged. Any wrapper fix routes to the migration WP;
       - every built-in preset (count asserted against `packs/built-in/presets/*.yaml`) is planned and applied without `--force`;
    3. **non-vacuity**: a throwaway migration that drops a deny entry with a raw write, and one that calls the seam without `deny_change`, must both fail the gate, which names the offender.
  - **Table** `tests/charter/conformance/activation_ledger_cases.yaml` + `test_activation_ledger_conformance.py`:
    - sections: `effective_set`, `identity` (stem vs declared id, R4), `readers` (agent_profile and tactic denied with absent allow, checked through the action bundle and the profile registry, M2), `cascade` (stop-at-denied, unreached, requires flag), `deactivation` (required refusal, P11 absent-allow rendering), `ledger_migration` (moves, refusals, re-run after crash);
    - plain data, data-model.md §8.
- **Sequencing**: IC-06, IC-07, IC-08, IC-09.

### IC-11 — Core ADR and glossary first (C-009)

- **Purpose**: record the decision before code.
- **Affected surfaces**:
  - NEW `docs/adr/4.x/2026-10-19-1-activation-ledger-persists-deactivation.md` (Accepted). It supersedes 3.x/2026-07-18-1 Decision 2 and amends 4.x/2026-10-03-1 (write target) and 4.x/2026-10-06-2 (presets `--force`, synthesis). It records:
    - the algebra and the source resolver;
    - the upgrade scope and the stop-at-denied cascade;
    - the strict required floor and the SPDD residual;
    - stray-key warnings, the downgrade hazard and the revisit triggers;
    - FR-022, a mission type as a cascade source (operator ruling `mission_type_cascade_source`, 2026-10-20; analyze pass 7 M3). WP15 records it in the ADR's 2026-10-20 amendment together with the Option B rulings.
  - Amendment notes in the three older ADR files; the ADR inventory refreshed.
  - Glossary terms in `docs/context/charter.md`: "Activation ledger", "Exclusion", "Effective deny" and "Required floor".

### IC-12 — Test-fixture re-seeding (CANCELED by `mission_pivot_option_b`, 2026-10-20)

- The three fixture-sweep WPs (WP11–WP13) are canceled. The full sweep and the strict fail-closed
  read move to the charter-contract alignment epic on milestone #11 (epic child #6535: retire the legacy activation reader).
- What remains in this Mission is the reduced flip's **bounded, red-first re-seed**, inside WP14:
  only the tests that its one-mode semantics turn red (measured red on the WP10 tip vs after the
  flip), with a hand-back threshold of about 60 files.
- The classification vocabulary (A legacy-by-design, B runtime seed, C post-write assertion, D direct
  `PackContext`, E prose) still guides those re-seeds.
- SC-004 is re-homed to WP14.

### IC-13 — The reduced flip (`mission_pivot_option_b`, 2026-10-20)

- **Purpose**: ship one mode that never writes deny keys off the ledger, gives fresh projects the
  ledger, and leaves unmigrated reads exactly as on `main`.
- **Relevant requirements**: FR-017 (amended), FR-019, FR-020, C-003, SC-001, SC-004.
- **Affected surfaces and design**:
  - **Delete the transition machinery**: `SPEC_KITTY_ACTIVATION_STRICT`, `activation_strict()` and `activation_strict_test()`, the tolerant/strict split, `legacy_save_accepts_deny()`, `SWEPT_PREFIXES`, both `pytest_runtest_*` hooks and `tests/_support/activation_strict_mode.py`. A gate asserts that no reference remains in `src/` or `tests/`.
  - **One-mode resolver** (data-model.md §5): ledger present → ledger; inside the upgrade scope → legacy; an unmigrated project (legacy keys, no ledger, outside the scope) → legacy **allow** keys, flagged `unmigrated`; fresh → ledger.
  - **Deny writes on an unmigrated project refuse**, naming `spec-kitty upgrade` / `spec-kitty migrate activation-ledger`, with nothing written. A deny write is an actual deny key or delta; a `deny_change` that clears nothing is not one. Cascade deactivation checks this before any write and before the floor read (all-or-nothing).
  - **No implicit ledger on an unmigrated project**: a new ledger beside legacy keys would strand them and widen to "absent = all". Only `spec-kitty upgrade` or `migrate activation-ledger` creates it there. `init` writes the ledger for fresh projects.
  - **Kept until the epic (#6535)**: `compiler._bootstrap_charter_yaml` keeps copying the legacy **allow** keys (never deny keys) into a newly bootstrapped `charter.yaml` **only when the activation source is LEGACY** (an unmigrated project). When a ledger exists, or the project is fresh, it copies nothing, so it never duplicates the ledger's keys or creates stray keys beside it. Removing the copy entirely is the epic's (#6535). The `CharterYaml` activation fields stay too, because unmigrated `charter.yaml` files must keep validating.
  - **Keyless pre-ledger upgrade (pass-8 M3)**: the upgrade's final provisioning step (WP08 T049) resolves its target **outside** the legacy scope, after the migrations. A project with no legacy keys is therefore fresh, and `mission_type_activations` lands in the ledger. A full upgrade never ends unmigrated.
  - **Init seed (pass-8 M4, moot)**: a re-run of `init` on an unmigrated project stops at the "Already initialized" exit before provisioning and before `init_seed.seed_migration_ledger_for_init`, and a fresh init never has pre-existing legacy keys, so the seed needs no skip; WP08 pinned the early exit instead (`test_init_reseed_keeps_rc8_pending.py`), and `spec-kitty upgrade` stays a working remedy after an `init` re-run.
  - **Legacy `deactivated_*` keys** are never applied. They are reported by FR-020, doctor `LEGACY_DENY_KEY`, and the migration's refusal.
  - **Precondition**: the WP refuses to start unless `.kittify/charter/activation.yaml` exists in this repository (WP08 dogfood).
  - **Tests**: rewrite the transition-pinning tests (kernel resolver, legacy scope, doctor, write target, init), and run the bounded red-first re-seed.
  - **Acceptance**: SC-001; the init flow; a subprocess e2e on an unmigrated fixture covering `--version`, `doctor charter-packs`, `migrate ledger`, `charter context` equal to `main`, allow-only writes on the legacy surface, deactivate refused, then `migrate activation-ledger` → deactivate succeeds.
  - **Carry-forward**: render the preflight error body (`preflight/cli.py`, `preflight/hook.py`), and fold the WP06 closeout LOWs.
- **Moved to the epic** (epic child #6535: retire the legacy activation reader): strict fail-closed reads, the full fixture sweep, the bootstrap-copy removal and the `CharterYaml` field removal.

### IC-14 — Docs, changelog, agent instructions (final)

- **Affected surfaces**:
  - `docs/api/charter-commands.md`, `docs/architecture/charter-pack-usage-journey.md`, `docs/architecture/06_unified_charter_bundle.md`, `docs/context/governance.md`, `docs/migrations/charter-pack-cutover.md`;
  - the "Charter Activation" sections of `CLAUDE.md` and `AGENTS.md`;
  - `docs/changelog/CHANGELOG.md` under `## [Unreleased] - 4.0.0rc8`, with Breaking, Upgrade Notes (run upgrade; older CLIs widen to "all"; stray legacy keys are ignored with a warning), Added and Fixed entries;
  - checks: `make docs-lint`, `check_docs_freshness --ci`, `docs_index --write`;
  - the PR body announces the cutover for open branches (P10).

## Proposed WP slicing (15 WPs, 12 active after `mission_pivot_option_b`; dependency-ordered, linear chain)

`single_branch` topology: WPs run strictly in sequence. Files shared between two WPs are
named; every such pair is dependency-ordered (exempt per
`src/specify_cli/ownership/validation.py:165-176`). The 12-WP slicing was split after the
post-tasks squad: the old WP02 became WP02 + WP03, the old fixture sweep became WP11 + WP12 +
WP13, and every later WP shifted.

| WP | Title | Depends | Key owned files | FRs / Cs |
|---|---|---|---|---|
| WP01 | Core ADR and glossary | – | `docs/adr/4.x/2026-10-19-1-…md` (new), amendment notes in the three older ADRs, ADR inventory, docs retrieval index, `docs/context/charter.md` | C-009 |
| WP02 | Kernel floor, ledger seam, write guard, test factory | WP01 | `src/kernel/activation_ledger_store.py` (new: path, raw read, resolver with `activation_strict()` + `SPEC_KITTY_ACTIVATION_STRICT`, scope), `src/kernel/README.md`, `src/charter/activation/activation_ledger.py` (new: vocabulary, typed load, write + guard), `api.py` (WP02 symbols), `pack_manager.py` (`ACTIVATION_YAML_KEYS` alias, `__all__`), `tests/_factories/activation_ledger.py` (new), `tests/conftest.py` (empty swept-list fixture), `tests/architectural/test_charter_path_literal_authority.py` (ledger filename), new kernel/seam tests | FR-001, FR-002, FR-014 (guard), FR-017 (resolver), FR-020 |
| WP03 | Re-pointed store, SPDD resolver, init and rendering writers | WP02 | `pack_context.py` (source loader, pointer helper), `pack_manager.py` (write target, `prepare_activation_write`, `list_activated`, tolerant legacy save carrying deny keys), `consistency_check.py`, `charter_yaml_io.py`, `charter/bundle.py` (`ACTIVATION_YAML` re-export only), SPDD probe (resolver only), `default_charter.py`, `mission_creation_scaffold.py`, `command_renderer.py`, `command_installer.py`, `skills/installer.py`, `upgrade/assessment.py` (rendering comparison only), re-pointing/init/render tests | FR-001, FR-017, FR-019 (strict-mode init) |
| WP04 | Required floor, planners, manager, deactivate CLI | WP03 | `org_pack_discovery.py`, `org_charter.py`, `activation_engine.py`, `pack_manager.py` (manager), `deactivate.py`, boundary baseline + `_baselines.yaml`, `_completion_manifest.json`, the retired-error test files, new deny-planning/required/timing tests | FR-006, FR-007, FR-008, FR-009, FR-012, FR-013 |
| WP05 | Identity-space deny and charter-side readers | WP04 | `pack_context.py` (deny + accessors), `activation_ledger.py` (`resolve_deny`), `resolver.py`, `drg_activation.py`, `compiler.py`, `action_governance_bundle.py`, `active_charter_service_builder.py`, `profile_resolution.py`, `skill_preparation.py`, `org_pack_discovery.py`, `consistency_check.py`, `context.py`, `reference_pointers.py`, `test_no_raw_activation_membership.py` (new) | FR-016 (charter side), FR-006, NFR-003 |
| WP06 | specify_cli readers, fail-open callers, mission-step executor, SPDD deny | WP05 | `gate_bindings.py`, step-contract `executor.py`, `preflight/runner.py`, `invocation/{registry,empty_charter}.py`, agent `{workflow_executor,mission_finalize_bootstrap,tasks_status_cmd}.py`, `profiles_cmd.py`, `_synthesis.py`, `list_cmd.py` (WP06 → WP09, FR-023), `_resynthesis_preflight.py` (raw getattr), SPDD probe (deny), the raw-membership gate | FR-016 (CLI side), FR-017 |
| WP07 | Cascade, activate CLI, presets, synthesis, interview | WP06 | `cascade.py`, `activate.py`, `_resynthesis_preflight.py`, `interview.py`, `synthesize.py`, `resynthesize.py`, `preset_application.py`, `synthesizer/reach_only.py`, `_completion_manifest.json`, cascade/preset/activate tests | FR-008, FR-009, FR-010, FR-011 |
| WP08 | Ledger migration, upgrade-only scope, m6 ordering, dogfood | WP07 | `migrations/base.py`, `m_4_0_0rc8_activation_ledger.py` (new), `order_manifest.txt`, `registry.py`, `runner.py`, `cli/commands/upgrade.py` (scope + m6), `upgrade/assessment.py` (m6), `migrate_cmd.py` (scope + new `migrate activation-ledger`, FR-021), `_completion_manifest.json`, `activation_ledger.py` (migration planner), `api.py`, this repo's `.kittify/{charter/activation.yaml,charter/charter.yaml,charter/synthesis-manifest.yaml,config.yaml,migration-ledger.jsonl}`, repo-reading tests (`tests/charter_offering/test_project_charter_single_owner.py`, `tests/charter/test_config_stem_parity.py`; H1), new migration/scope/worktree/crash tests, rc5 full-manifest test | FR-003, FR-004, FR-017 (scope), SC-002, FR-021 |
| WP09 | Bundle membership and doctor | WP08 | `list_cmd.py` (FR-023 `required_not_in_force`), `charter/bundle.py` (manifest, hash), `charter_bundle.py` (incl. `_enumerate_out_of_scope_files`), `generate.py` (only if needed), freshness `computer.py`, `state/contract.py`, `_charter_pack_collect.py`, `doctor.py`, `activation_ledger.py` (`ledger_findings`), `api.py`, tests | FR-005, FR-018, FR-023 |
| WP10 | FR-014 gate and FR-015 conformance table | WP09 | divergence register + both spellings (FR-024), `tests/architectural/test_deny_list_survives_upgrade.py` (new), `tests/charter/conformance/**` (new) | FR-014, FR-015, SC-003, FR-024 |
| WP11 | Fixture sweep 1: step 0 (shared cross-tree helpers, H2), then `tests/charter`, `tests/charter_offering`  — **CANCELED 2026-10-20** (`mission_pivot_option_b`; moved to the alignment epic)| WP10 | `tests/charter/**`, `tests/charter_offering/**`, `tests/_factories/**` and the other step-0 helpers, `tests/conftest.py` (swept list) | none (canceled; SC-004 re-homed to WP14) |
| WP12 | Fixture sweep 2: `tests/specify_cli`  — **CANCELED 2026-10-20** (`mission_pivot_option_b`; moved to the alignment epic)| WP11 | `tests/specify_cli/**`, `tests/conftest.py` | none (canceled; SC-004 re-homed to WP14) |
| WP13 | Fixture sweep 3: every remaining tree and the YAML fixtures  — **CANCELED 2026-10-20** (`mission_pivot_option_b`; moved to the alignment epic)| WP12 | the remaining census trees (`tests/acceptance`, `upgrade`, `integration`, `runtime`, `core`, `agent`, `cli`, `review`, `next`, `git`, `compat`, `test_template`, `status`, `consolidation`, `coordination`, `contract`, `doctor`, `kernel`, `unit`, `init`, `missions`, `regressions`, `audit`, `context`, `performance`, `_factories`), `tests/fixtures/**`, four architectural files, `tests/conftest.py` | none (canceled; SC-004 re-homed to WP14) |
| WP14 | The reduced flip (one mode, no deny keys off the ledger, fresh projects on the ledger) | WP10 | `kernel/activation_ledger_store.py` (one-mode resolver, env var deleted), `activation_ledger.py`, `pack_manager.py`, `charter_yaml_io.py`, `default_charter.py` (fresh-only ledger), `deactivate.py` (unmigrated refusal, all-or-nothing), `preflight/{cli,hook}.py`, `tests/conftest.py`, `tests/_support/activation_strict_mode.py` (deleted), transition-pinning tests, acceptance tests (SC-001, init flow, unmigrated subprocess e2e), the no-env-var gate, bounded re-seed globs | FR-017 (amended), FR-019, FR-020, C-003, SC-001, SC-004 |
| WP15 | Docs, changelog, agent instructions | WP14 | `docs/changelog/CHANGELOG.md`, `docs/api/cli-commands.md` (FR-021 command), the doc pages in IC-14, `CLAUDE.md`, `AGENTS.md`, the glossary pack and the files `charter pack regenerate-graph` writes | C-009, C-010, FR-021, FR-024 (docs: the downgrade hazard `older_cli_downgrade`, the ADR amendments, the divergence register) |

Dependency-ordered shared files: `pack_context.py` (WP03 → WP05), `pack_manager.py` (WP02 →
WP03 → WP04 → WP14), `activation_ledger.py` (WP02 → WP05 → WP08 → WP09 → WP14), `activation_engine.py` (WP04 → WP05),
`tests/_factories/activation_ledger.py` (WP02 → WP14; the WP11 step-0 helpers are canceled with WP11), `migrate_cmd.py` and `_completion_manifest.json` (WP08 adds `migrate activation-ledger`), the two repository-reading tests (WP08 only), `api.py` + its re-export gate
(WP02 → WP08 → WP09; each WP exports only the symbols its own consumers need, R6),
`org_pack_discovery.py` (WP04 → WP05), `compiler.py` (WP05 → WP14), `charter/bundle.py` (WP03 →
WP09), the SPDD probe (WP03 → WP06), `kernel/activation_ledger_store.py` (WP02 → WP14),
`charter_yaml_io.py` (WP03 → WP14), `consistency_check.py` (WP03 → WP05),
`_resynthesis_preflight.py` (WP06 → WP07), `_completion_manifest.json` (WP04 → WP07),
`cli/commands/upgrade.py` (WP08 only), `upgrade/assessment.py` (WP03 → WP08), `tests/conftest.py` (every code WP WP02 → WP10 and WP14, append-only `SWEPT_PREFIXES` entries; WP14 deletes the fixture), `.kittify/charter/synthesis-manifest.yaml` (WP08 → WP09 restamp),
`default_charter.py` (WP03 → WP14), `activate.py` (WP07 only). No unordered pair shares a file.

Per-WP targeted test surface: the WP's own new and edited tests, its module tests, its owning
subsystem directories (`tests/charter/` and/or `tests/charter_offering/` for charter code;
`tests/upgrade/` + `tests/specify_cli/upgrade/` + `tests/migration/` + `tests/migrate/` for
WP08), `make test-fast`, and the named gates listed in each WP prompt (never the bare
`tests/architectural/` directory). No WP runs a whole heavy tree it does not own (analyze pass 2,
C1, `NO_FULL_HEAVY_SUITES_IN_MISSION`): WP03 runs a grep-derived file list, WP13 runs only the
files it re-seeds plus the factory consumers, and WP14 runs `make test-fast`, `tests/charter/`,
`tests/charter_offering/`, `tests/upgrade/`, `tests/specify_cli/upgrade/`, its acceptance and
transition tests and the named gates, never more.


## Resolved planning points

1. **FR-014 dynamic tier**: activation-touching migrations, found by a static classifier (imports from `charter.activation`, or names a ledger/activation key or path), each get a `detect()`-true fixture. Every other migration is not applicable *by derivation*, with no hand table (R12). Every run is byte-checked for deny survival.
2. **SPDD probe and the required floor**: a documented residual in the ADR. The probe subtracts deny, uses the kernel resolver and has no pointer replica (R2). Doctor warns on stale deny entries for required ids.
3. **Legacy scope entry**: the `BaseMigration` wrapper over every public method a subclass defines, the registry and runner selection entry points, `migrate ledger`, and the `spec-kitty upgrade` command body. It is canonical-root aware (M3/M4) and covers only migration code paths.
4. **Stray `config.yaml` copy when the authority lacks the key**: refuse as divergent (operator ruling `stray_config_copy`).
5. **Cascade through a denied node**: the walk stops at it (operator ruling `cascade_walk_through_denied`). What lies behind it is reported as "unreached" (P12).
6. **Fixture sweep**: canceled by `mission_pivot_option_b` (2026-10-20). Only WP14's bounded red-first re-seed remains; the full sweep moves to the alignment epic (epic child #6535: retire the legacy activation reader).
7. **Dogfood**: the last task of WP08 runs `spec-kitty migrate activation-ledger` (FR-021; never `spec-kitty upgrade`, since this repository has no migration ledger) and commits this repository's `.kittify/` ledger move; once the ledger exists both modes read it. The flip stays in WP14, whose first step refuses to start without `.kittify/charter/activation.yaml` (P15, analyze pass 4 H1).
8. **Late legacy writes**: ordinary commands warn once per process; doctor reports an error; a reconcile command is deferred (P10).
9. **Unknown `deactivated_<kind>` keys** from a newer CLI are tolerated with a warning; unknown non-deny keys refuse (P15).
