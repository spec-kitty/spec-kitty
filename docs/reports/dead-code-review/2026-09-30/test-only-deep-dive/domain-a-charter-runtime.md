---
doc_status: active
updated: '2026-09-30'
---

# Test-only deep dive — Domain A: charter, glossary, kernel, mission_runtime, runtime

Part of the [dead-code review of 2026-09-30](../README.md). Analysed at `origin/main` `bd1577a3`.

Scope: every TEST-ONLY row in "Domain A: charter / glossary / kernel / mission_runtime / runtime / doctrine.py", at bd1577a3. The history comes from a full clone of spec-kitty/spec-kitty (13,984 commits), queried with `git log -S'<sym>'` / `-S'<sym>('` / `-G` restricted to `src/`. Test counts are test functions whose body names the symbol (AST scan), shown as `Nt/NL` (N tests / N lines).

| # | slice | symbols | src LOC | test LOC | verdict | confidence | behaviour gap? |
|---|---|---|---|---|---|---|---|
| 1 | Default-pack merge writer | `merge_defaults`, `MergeResult`, `_load_default_pack` | 71 | 7t/91L | OWNER-DECISION (rec. DELETE) | High | **Yes (adjacent):** `charter pack apply` writes the retired config mirror |
| 2 | charter.activation compat wrappers | `CharterCatalogMissError`, `_load_project_directives`, `_load_yaml_id_catalog`, `load_charter_bytes` | 98 | 11t/205L | MOVE-TESTS-THEN-DELETE | High | No |
| 3 | `ResolvedMissionType` lazy slots | `expected_artifacts`, `step_contracts`, `_resolve_expected_artifacts_slot`, `_resolve_step_contracts_slot`, `resolve_step_contract_ids`, 2 thunk fields | ~140 | 6t/170L (+ `test_step_contract_resolution.py`) | OWNER-DECISION (rec. DELETE) | Medium | No |
| 4 | Delivery-rail measurement helpers (#3063) | `charter_activated_urns`, `partition_activated_unreachable`, `ActivationReachabilityPartition`(+`normalization_delta`), `normalize_activation_identifier`, `_resolve_activation_kind`, `_ACTIVATION_URN_KINDS`, `action_channel_reachable`, `action_seed_urns` | ~208 | ~30t/~640L | MOVE to a tests support module (keep the gate) | Medium | No |
| 5 | Misc small helpers (charter.activation + kernel) | `require_org_root`, `require_active_profile`, `resolve_mission_definition`, `token_estimate`, `has_backed_removals`, `BatchCapableSynthesisAdapter`, `InterviewAnswersRegressionError` + flag, `CONTEXT_CONTRACT_TOP_LEVEL_KEYS`, `is_re2_active`, `is_stuck` | ~150 | ~16t/~250L | mixed (per symbol) | High | No |
| 6 | Per-kind JSON-schema validators | `validate_{directive,paradigm,styleguide,tactic,toolguide}`, `is_agent_profile_file`, `StepKey` | ~156 | 47t/~330L | OWNER-DECISION (rec. fold into one test helper) | Medium | **Maybe:** shipped schemas are never enforced at load for 5 kinds |
| 7 | Offering repository query helpers | `find_by_role`, `get_hierarchy_tree`, `validate_hierarchy`, `Role.is_known`, `list_command_templates`, `list_content_templates`, `get_action_index`, `MissionTypeRepository.load_all`, `needs_migration`, `template_node(s)` | ~194 | ~52t/~420L | SPLIT: DELETE most; WIRE `validate_hierarchy` | Medium | No |
| 8 | Org-pack topology `enhances` merge | `merge_topology_artifact`, `_merge_action_sequence`, `_merge_action_sequence_step`, `_step_id`, `TOPOLOGY_KINDS` | 132 | 7t/54L | OWNER-DECISION → WIRE or retract the documented contract | Medium | **YES:** documented drop-rejection is not enforced |
| 9 | Pack identity + relation docs | `ensure_pack_identity`, `RELATION_DESCRIPTIONS` | 222 | 9t/105L | KEEP-with-note | Medium | No |
| 10 | Glossary-in-DRG + entity pages | `build_glossary_drg_layer`, `GlossaryEntityPageRenderer.generate_all` | 91 | 13t/~180L | OWNER-DECISION (WIRE or retire the whole surface) | Medium | **YES:** entity pages and vocabulary edges never materialize |
| 11 | Glossary scope activation + helpers | `activate_scope` (+ `emit_scope_activated`), `get_scope_precedence`, `should_use_scope`, `validate_seed_file` | 68 (+41) | 12t/121L | DELETE helpers; OWNER on `activate_scope` | High / Medium | **Yes (spec):** `GlossaryScopeActivated` is never emitted |
| 12 | Glossary WP03 scaffolding | `score_confidence`, `MockContext`, `scan_fields`, `term_sense_to_dict` | 67 | 49t/~1010L | DELETE 3; MOVE `MockContext` to tests | High | No |
| 13 | Over-internalized upstream runtime | `notify_decision_timeout`+`TimeoutEscalationResult`, `TransitionGate`+`contracts.py`, `JsonlEventLog`, `diagnose_shadowing`+`ShadowingDiagnostics`, `StepContextContract.validate_contract`, `serialize_decision` | ~436 | ~14t/~180L | DELETE | High | No |
| 14 | Workflow-sequence next-action resolver | `resolve_next_workflow_action`, `PlanResult`, `_resolve_workflow_for_mission`, `runtime_bridge_engine.resolve_workflow_for_mission` (+ DEAD `prompt_builder._workflow_for`) | 103 | 7t/210L (+ `test_bridge_engine.py`) | OWNER-DECISION (rec. DELETE, keep sequencing tests on live path) | Medium | No (defaulting differs, benign) |
| 15 | Runtime thin wrappers | `evaluate_guards`, `_record_path_str` | 30 | 38t/~420L | MOVE-TESTS-THEN-DELETE | High | No, but one regression guard is vacuous |

**Headline.**
- **Almost none of this was ever wired.** Only 5 of the ~70 symbols ever had a runtime caller that was later removed: `_load_project_directives`, `_load_yaml_id_catalog`, `validate_seed_file`, `charter_activated_urns` and `generate_all`, plus `evaluate_guards`, which became `evaluate_guards_strict`.
- **The rest are forward APIs, or library code imported or authored without a consumer.** Examples: mission 057's doctrine stack (623057f97), the #796 runtime internalization (fda13faf3) and the glossary WP01–WP03 scaffolding (Feb 2026).
- **About 1,900 src LOC can go with high or medium confidence.** The largest pieces are the `_internal_runtime` upstream features (~436 LOC), the delivery-rail helpers, the lazy mission-type slots and the org-pack topology merge.
- **Two slices hide real behaviour gaps.**
  1. The CLAUDE.md contract says an `enhances` overlay may not silently drop steps or strip step I/O. That rule lives only in the test-only `merge_topology_artifact`. The live repositories merge with a shallow `{**built_in, **overlay}` (slice 8).
  2. The glossary-in-DRG / entity-page surface (WP5.1/WP5.5) never gets fed. The dashboard's `entity_pages_generated` stays false and `query.py:232` walks `vocabulary` edges that nothing mints (slice 10).
- **Adjacent bug candidate (slice 1).** On a migrated project, `charter pack apply` writes activation keys into the `config.yaml` mirror, which `pack_context` no longer reads.
- **Five first-pass rows are live:** `partition_delivery`, `compute_manifest_hash`, `PROFILE_CHANNEL_RELATIONS`, `AUGMENTATION_RELATIONS` and `STALE_AFTER_S_DEFAULT`. Several transitively test-only symbols were missed. See the corrections at the end.

---

## Slice 1: Default-pack merge writer (`pack_manager.merge_defaults`)
- **What / why.** The function is at `src/charter/activation/pack_manager.py:1067` (55 LOC), with `MergeResult` at :534 and `_load_default_pack` at :679, which only `merge_defaults` uses.
  - It fills every absent `activated_*` / `mission_type_activations` key from `packs/default.yaml`.
  - It writes through `resolve_activation_write_target`: `charter.yaml` on a migrated project, `config.yaml` on a legacy one.
  - It backs up `charter.md` before writing.
- **History.**
  - Introduced in f07bed9b1 (2026-05-31, "feat(WP04): default charter pack + CharterPackManager").
  - `-S'merge_defaults('` returns only that commit, so it **never had a src caller**.
  - ADR `docs/adr/3.x/2026-07-15-1-doctrine-offers-charter-activates-runtime-consumes.md:149` slated it as "S1 — `init` provisions the default charter via `merge_defaults`".
- **What replaced it.** Three live writers use `merge_pack_into_config` (`src/specify_cli/charter_pack_registry.py:146`):
  - `init` → `provisioning/default_charter.py:171`. It seeds **only** `mission_type_activations`.
  - the rc35 migration → `m_3_2_0rc35_default_charter_pack.py:199`.
  - `charter pack apply` → `cli/commands/charter/pack.py:319`.
- **Tests.**

  | Test file | Tests | Class | What it pins |
  |---|---|---|---|
  | `tests/charter/test_pack_manager.py` | 5t/70L | (b) | this method |
  | `tests/charter/test_activation_engine_charter_yaml.py` | 1t/16L | (a) | a migrated project's write lands in `charter.yaml` |
  | `tests/specify_cli/cli/commands/charter/test_resynthesize_and_hotpath.py` | 1t/5L | (a) | "writer-agnostic" freshness (doctrine-activation-freshness-01KXRSDN C-005): a non-`commit_plan` writer is still seen |

  Both (a) tests can reseed through `merge_pack_into_config` or `provision_default_mission_type_activations`.
- **Open intent.**
  - ADR 2026-07-15-1 S1 (the "new default-charter provisioning issue", number not recorded).
  - kitty-specs/doctrine-activation-freshness-01KXRSDN/spec.md:244 still names it a live bypass writer.
  - Stale docs that present it as a live INV-9 mutator: `charter_yaml_io.py:4,624,644`, `state/contract.py:542` and `pack_manager.py:602`.
- **Risk if deleted.** Low, since there is no caller. The only loss is the "fill every kind + back up charter.md" behaviour, which no live path offers.
- **Verdict.** OWNER-DECISION.
  - **Question:** "Should `init`/`upgrade` provision every activation kind (S1), or only `mission_type_activations` as today?"
  - **Recommendation:** DELETE `merge_defaults`, `MergeResult` and `_load_default_pack` (71 LOC), plus the 5 (b) tests. Move the 2 (a) tests onto `merge_pack_into_config`. Fix the four docstrings. Confidence High.
- **Behaviour gap (adjacent, bug candidate).** `merge_defaults` writes through `resolve_activation_write_target`. `charter pack apply` (`pack.py:306-323`) always writes `.kittify/config.yaml`. On a migrated project (a `charter:` pointer is present), `pack_context._load_charter_activation_source` (`pack_context.py:557-585`) reads **only** `charter.yaml`. So a `charter pack apply` without `--compile` writes keys that nothing reads. Not reproduced; needs a one-test repro.

## Slice 2: charter.activation compat wrappers
- **What / why.** Arity- and name-compat shims left over from god-module splits, plus one exception nobody raises.
  - `_load_project_directives` (`context_json.py:183`) is a 2-tuple wrapper over `_with_source`.
  - `_load_yaml_id_catalog` (`catalog.py:212`) is a wrapper over `_with_presence`.
  - `load_charter_bytes` (`_io.py:124`) is an "inline ingest path" that no ingest uses. It deletes its own `origin` argument.
  - `CharterCatalogMissError` (`_catalog_miss.py:185`) is "not currently raised… exported for downstream consumers".
- **History.**

  | Symbol | Introduced | Last caller removed |
  |---|---|---|
  | `_load_project_directives` | 38abeebf6 (#1297) | c0019e3c6 (2026-08-25, #3728 "make project-local directives additive"). The re-port 53abf91c7 (#806) repeats that removal. |
  | `_load_yaml_id_catalog` | 7bf4fae1e (2026-02-22) | 2db24b362 (2026-04-17, #661 complexity-debt remediation; the file with the two callers was deleted) |
  | `load_charter_bytes` | c12cc95cb (#1034, mission 116) | never had a caller |
  | `CharterCatalogMissError` | fa80fa0f9 (2026-05-19) | never raised |
- **What replaced it.**
  - `_load_project_directives_with_source` (`context_json.py`).
  - `_load_yaml_id_catalog_with_presence` (`catalog.py`).
  - `load_charter_file` (`_io.py:99`), which shares `_load_inner`.
  - For the catalog miss, `CharterCatalogMissWarning` is the live path.
- **Tests.**
  - `test_context.py:889` and `test_context_service_seams.py:120` (2t/26L) → (a). Repoint them at `_with_source` and drop the third tuple element.
  - `test_catalog.py:216` (1t/35L) → (a). Repoint at `_with_presence`.
  - `load_charter_bytes` → (a). The tests exercise the shared `_load_inner` pipeline (ambiguity raise, unsafe bypass, UTF-8). Rewrite them with `load_charter_file(tmp_path/…)`. Files:
    - `test_unsafe_bypass.py` 3t/64L
    - `test_io_edge_paths.py` 3t/23L
    - `test_encoding_chokepoint.py:235` 1t/48L
  - `test_context_catalog_miss.py:323` (1t/9L) → (b). Delete.
- **Open intent.** None. The `context_json.py:39-42` comment says both helpers "stay module-internal helpers used by the functions below", which is false for `_load_project_directives`. Fix it.
- **Risk.** Nil. These are private, apart from `CharterCatalogMissError` in `__all__`. No sibling-repo use was found; spec-kitty-saas is not checked out, so status is unknown offline.
- **Verdict.** MOVE-TESTS-THEN-DELETE. 98 src LOC; about 170 test LOC move and 9 are deleted. Confidence High.
- **Behaviour gap.** None.

## Slice 3: `ResolvedMissionType` lazy slots (WP10/WP11)
- **What / why.** `mission_type_profiles.py:458-470` defines two `@cached_property` slots on the bundle that `resolve_mission_type_context` returns:
  - `expected_artifacts`: the org-then-built-in manifest dict.
  - `step_contracts`: the ordered contract ids.

  The slots are fed by thunks (:429-435, :682-686) → `_resolve_expected_artifacts_slot` (:1068, 65 LOC) and `_resolve_step_contracts_slot` (:1194, 21 LOC) → `step_contracts.resolve_step_contract_ids` (31 LOC, which has no other caller).
- **History.**
  - The seam arrived in b23a1c55a (2026-07-15, #883 "charter-mediated mission-type resolution seam") and 96e225d07 (#2651, the lazy grain).
  - Hardened in d212360ac (#3516), 443bb577d, 9b6fb4925 (#3412) and c438da78a (#3704).
  - There is no `.expected_artifacts` / `.step_contracts` attribute read in src, then or now.
- **What replaced it.**
  - Expected artifacts are consumed through `charter/activation/manifest_loader.py:260-264` (→ `org_expected_artifacts.resolve_org_expected_artifacts`) by the dossier `ManifestRegistry.load_manifest` and the runtime guards. That is the #3770 loader unification, 4e5fab124 and 57bdaf886.
  - Step contracts are consumed through `MissionStepContractRepository` (`step_contracts.py:163`) in `mission_step_contracts/executor.py`.
- **Tests.**
  - `tests/charter/test_mission_type_profiles.py` 4t/138L (:1044-1168): org-tier precedence, malformed manifests fail loud, and laziness. **Mixed (c).** The precedence and fail-loud cases duplicate `tests/charter/test_org_expected_artifacts.py`, `tests/charter/activation/test_org_expected_artifacts.py` and `tests/architectural/test_expected_artifacts_loader_gate.py`. The laziness cases are (b).
  - `test_resolved_mission_type_context.py:161-170` 1t/16L → (b).
  - `tests/specify_cli/mission_step_contracts/test_documentation_composition.py` 1t/39L → check before deleting.
  - `tests/doctrine/mission_step_contracts/test_step_contract_resolution.py` (the `resolve_step_contract_ids` tests) → (b).
- **Open intent.** The class docstring (:392-407) calls these the public read shape. The mission-B WP10/WP11 missions are done. No open issue found.
- **Risk.** Public attributes on a frozen dataclass. A sibling-repo read is unknown offline, but none exists in this repo or in spec-kitty-planning.
- **Verdict.** OWNER-DECISION.
  - **Question:** "Is the `ResolvedMissionType` read shape a promised external API?"
  - **Recommendation:** DELETE the two properties, thunks, both slot resolvers and `resolve_step_contract_ids` (~140 LOC). Keep `governance`/`template_set` untouched. Confidence Medium.
- **Behaviour gap.** None found. The live manifest loader has the same org-first, fail-loud semantics (#3412).

## Slice 4: Delivery-rail measurement helpers (#3063)
- **What / why.** Measurement instrumentation for the doctrine-delivery-reachability gate:
  - `charter_activated_urns` (`pack_context.py:523`) is the "single activation authority (FR-017)" projection of activated `kind:id` URNs.
  - `partition_activated_unreachable` (:453), `ActivationReachabilityPartition` (:417) with `.normalization_delta`, `normalize_activation_identifier` (:388) and its private `_resolve_activation_kind` split activated-but-unreachable into `not_a_node` and `node_but_unreachable` (C-009).
  - `action_channel_reachable` / `action_seed_urns` (`offering/drg/reachability.py:64-107`) call `resolve_context` per action seed.

  `docs/plans/doctrine/delivery-reachability-wiring-table.md:359,1108,1143` says pins are "measured via `profile_channel_reachable` / `action_channel_reachable` only".
- **History.**
  - All introduced in 102fce06b (2026-07-29, mission doctrine-delivery-reachability-01KYMXD6; 13 WPs done).
  - `charter_activated_urns` gained a runtime caller in bb1ef75db (#3064, `invocation/empty_charter.py`). That caller was removed in 184118d9a (2026-08-02, #3104/#3118): "Folds #3118 (previously two config loads)", `empty_charter.py:35`.
  - The others never had a src caller.
- **What replaced it.**
  - Runtime delivery uses `resolve_context` directly through `charter.activation.context`, plus the live **profile** channel (`profile_channel_reachable`, reached from `agent_profiles/repository.py:26,953` and `profile_sections.py:487`).
  - The emptiness check is `empty_charter.is_charter_empty` with its own single config load.
- **Tests.** These tests *are* the gate. They pin the named reachable sets against the shipped graph. Class (a) for the doctrine gate, (b) for the src placement.
  - `tests/doctrine/drg/test_reachability.py` (1,293 L; 12t/211L use the action channel)
  - `test_c4_and_anti_pattern_topology.py` 2t/35L
  - `test_activation_identifier_normalization.py` 5t/74L
  - `test_activation_authority.py` 1t/19L
  - `test_charter_pack_builtin.py` 2t/48L
  - `test_is_charter_empty_bundle_predicate.py` 1t/39L
- **Open intent.** The allowlist comment at `test_no_dead_symbols.py:1735-1745` reads "Follow-up tracker: #3063 … Target = 0 once a later mission wires each remaining helper". #3063 status is unknown offline. Its follow-on mission doctrine-delivery-activation-01KYQVQK (7/7 done) wired the profile channel only.
- **Risk.** If `charter_activated_urns` drifts from the runtime's own activation read, the gate measures a different set from the one runtime delivers. That argues for one reader. Otherwise none.
- **Verdict.** MOVE these ~208 LOC into a test support module (e.g. `tests/doctrine/drg/_reachability_support.py`) and keep the gate. Alternatively, KEEP them in src with an honest "test instrumentation" allowlist note instead of "forward API". Confidence Medium.
- **Behaviour gap.** None.

## Slice 5: Misc small helpers (charter.activation + kernel)

| Symbol | Lines | Class | Introduced / caller history | Live equivalent | Tests | Verdict |
|---|---|---|---|---|---|---|
| `ProjectContext.require_org_root`, `OperationalContext.require_active_profile` | 7 + 17 | never wired | d1b2c5aba (WP03, 2026-05-31) | callers read `.org_root` directly. The sibling guards `require_repo_root` / `require_pack_context` are used (5 and 6 src files). | `test_invocation_context.py` 3t/15L, `test_operational_context.py` 2t/24L → (b) | DELETE (High) |
| `CharterTemplateResolver.resolve_mission_definition` (`resolver.py:518`) | 20 | never wired | 6c5d8812e (WP01, "unify DoctrineService construction") | `specify_cli.runtime.show_origin:235` → `resolve_mission` | `test_resolver_tier_axis_via_factory.py` 2t/59L → (b); that file already goes with the DEAD `template_resolver` module | DELETE with `template_resolver` (High) |
| `CompactView.token_estimate` | 4 | never wired | 3aff2e9fc (01KQ4ARB) | none | `test_compact.py` 1t/4L → (b) | DELETE (High) |
| `ReconciliationPlan.has_backed_removals` | 4 | never wired | f4b781f1f (charter-synthesize WP01) | — | `test_synthesize_reconcile.py` 2t/13L → (b) | DELETE (High) |
| `BatchCapableSynthesisAdapter` Protocol | 18 | typing-only by design ("documentation / static analysis aid"; the orchestrator uses `hasattr`) | cb9c4f8d0 (#677) | — | `test_adapter_contract.py` imports it only | KEEP-with-note, or DELETE (Low stakes) |
| `InterviewAnswersRegressionError` + `fail_closed_on_regression` + `_guard_against_regression` + `_KNOWN_REGRESSION_GUARDED_LIST_FIELDS` (`interview.py:407-517`) | ~58 | opt-in flag no caller passes | d2f97d638 (#3664 charter-authority-flip). Docstring: for "the answers-migration tooling". `scripts/migrate_charter_interview_answers.py` does **not** use it. | `cli/commands/charter/interview.py:414` calls with the default `False` | `test_answers_migration.py` 1t/49L; the merge half is (a), the guard half is (b) | OWNER: "should the answers migration use the guard?" Rec.: drop the flag and the guard, keep the merge test (Medium) |
| `CONTEXT_CONTRACT_TOP_LEVEL_KEYS` (`context_contract.py:82`) | 17 | contract ledger by design. Module docstring :26-31: "MUST be updated in the same change… `CONTEXT_SCHEMA_VERSION` MUST be bumped" | 8466727eb (#2787), de-exported a1b28f1f1 | — | 4 files use it as an oracle → (a) | **KEEP** (a public-contract ledger, correctly private) |
| `kernel._safe_re.is_re2_active` | 3 | always `True` | ea12637d7 (#529) | re2 is a hard dependency | `tests/kernel/test_safe_re.py:237` (1t/2L, b); `test_requirement_id_grammar.py:25` (c: drop the one assert, keep the pattern-compile check) | DELETE (High) |
| `kernel.locks.LockRecord.is_stuck` | 3 | never wired | d5d5fa52b (daemon-singleton 01KQ9M3M, `core/file_lock.py`), moved to kernel in c206e7d2d (#4714) | the same logic is inlined at `cli/commands/_auth_doctor.py:272` (`stuck=age_s > stuck_threshold_s`) | `tests/kernel/test_locks.py` 1t/8L (a) | **WIRE** at `_auth_doctor.py:272` (a one-line reuse) or DELETE. Low stakes |

No behaviour gap in this slice.

## Slice 6: Per-kind JSON-schema validators
- **What / why.** `validate_{directive,paradigm,styleguide,tactic,toolguide}` are five byte-identical 27-LOC functions (`offering/<kind>/validation.py:16-21`). Each is `jsonschema.Draft202012Validator(SchemaUtilities.load_schema(kind))`, with the #4409 lazy import.
  - `is_agent_profile_file` (`agent_profiles/validation.py:76`) is a suffix check.
  - `StepKey` (`mission_step_repository.py:164`) is a frozen `(mission_type_id, step_id)` dataclass. The module docstring (:16) claims it "enforces [isolation] at the cache layer".
- **History.**
  - Validators and `is_agent_profile_file` were imported with the doctrine stack in 623057f97 (2026-03-30, mission 057). There is no caller in that commit or since.
  - `StepKey` arrived in c181cd8c0 (charter-doctrine-mission-type-configuration-01KSWJVX) and never had a caller.
- **What replaced it.**
  - Kinds are validated at load by pydantic models plus `reject_<kind>_inline_refs`. Agent profiles **do** run JSON-schema at load (`agent_profiles/repository.py:509,531` → `validate_agent_profile_yaml`).
  - Step isolation is structural: `_resolve_all_for_mission_type_cached` is keyed by mission type, and files live under the mission-type directory.
- **Tests.**
  - The validator tests are shipped-content schema-conformance checks (`test_schema_compatibility.py` 7t/126L) plus unit tests of the wrappers: directives 8t/37L, paradigms 4t/14L, styleguides 7t/65L, tactics 6t/33L, toolguides 5t/19L. Class (a) for "shipped YAML matches the shipped schema", (b) for the wrapper plumbing.
  - `is_agent_profile_file`: 11t/30L → (b).
  - `StepKey`: 5t/25L in `test_mission_step_resolver.py:119-143,399` → (b). The real isolation is already covered by `TestCompoundKeyIsolation` (:346, :378).
- **Open intent.** None. The allowlist rows sit in Cat A/B.
- **Risk.** Low. Public-looking names in `charter.offering.<kind>.validation`; no in-repo importers.
- **Verdict.** OWNER-DECISION.
  - **Recommendation:** replace the five clones with one `tests/doctrine/_schema.py::validate_against_schema(kind, data)`, keep the conformance tests on it, and delete the clones (135 LOC). DELETE `is_agent_profile_file` and `StepKey` and fix the docstring at `mission_step_repository.py:16`. Confidence Medium.
- **Behaviour gap (maybe).** The shipped `schemas/{directive,paradigm,styleguide,tactic,toolguide}.schema.yaml` are never enforced at runtime for org or project overlays, unlike agent profiles. If a schema is stricter than the pydantic model (patterns, `additionalProperties: false`), an org pack can load YAML that the documented schema rejects. That is worth a quick diff of each schema against its model.

## Slice 7: Offering repository query helpers
- **What / why.** Query conveniences on the doctrine repositories:
  - `AgentProfileRepository.find_by_role` (:670), `get_hierarchy_tree` (:760) and `validate_hierarchy` (:788, a cycle/orphan check).
  - `Role.is_known`.
  - `MissionTemplateRepository.list_command_templates` / `list_content_templates` / `get_action_index` (:271-340).
  - `MissionTypeRepository.load_all`.
  - `BundleCompatibilityResult.needs_migration` (`versioning.py:70`).
  - `template_catalog.template_node(s)` (:206, :227).
- **History.**
  - The first six came with 623057f97 (mission 057) and have had no caller since.
  - `Role.is_known`: 650f5632e (profiles roles VO).
  - `needs_migration`: 986ab5419 (charter-p7-schema-versioning-01KQEG13). Live callers use `.is_compatible` only (`charter/_common.py:145`, `charter_bundle.py:263`).
  - `template_node(s)`: 9038c5967 (WP18, #1333). Superseded in 867a414a9 (mission-step-creatability S-C), where the extractor mints template nodes via `extract_template_instantiation_edges` (`drg/migration/extractor.py:1805`).
- **What replaced it.**
  - Action indexes: `missions/action_index.load_action_index` (via `activation/action_grain.py:51`). Note: `get_action_index` swallows YAML errors and returns `None`, while the live loader raises. The dead copy is the weaker one.
  - Profile selection: `find_best_match` (API).
- **Tests.**

  | Tests | Count | Class |
  |---|---|---|
  | `test_profile_repository.py`: `find_by_role` | 10t/51L | (b) |
  | `test_profile_repository.py` + `test_profile_diagnostics.py`: `get_hierarchy_tree` | 2t/18L | (b) |
  | `validate_hierarchy` in `test_shipped_profiles.py:~` 1t/4L, plus 5t/88L | 6t/92L | (a): guards shipped profiles |
  | `is_known` | 9t/45L | (b) |
  | list templates | 9t/41L | (b) |
  | `get_action_index`: `test_repository.py` 8t/47L | 8t/47L | (b) |
  | `get_action_index`: `test_action_indexes.py` 2t/21L and `test_mattpocock_skill_doctrine.py` 1t/12L | 3t/33L | (a): shipped-content checks; repoint at `load_action_index` |
  | `load_all` | 3t/12L | (b) |
  | `needs_migration` | 5t/10L in `tests/doctrine/test_versioning.py` | (b); the `test_m_0_13_8` hit is a local variable |
  | `template_node(s)` | 5t/81L | mixed; the `test_template_asset_e2e.py` e2e should be repointed at the extractor |
- **Open intent.** None found.
- **Risk.** Low. `.kittify/overrides/missions/repository.py` is a stale vendored copy that also defines these; audit it separately.
- **Verdict.** SPLIT.
  - DELETE `find_by_role`, `get_hierarchy_tree`, `is_known`, both list-templates, `get_action_index` (after repointing 3 tests), `load_all`, `needs_migration` and `template_node(s)` (~150 LOC).
  - **WIRE** `validate_hierarchy` into `spec-kitty doctor doctrine` profile diagnostics, next to `skipped_profiles` (FR-010: "a pack with invalid profiles is NOT reported healthy"). Otherwise KEEP it as a shipped-content guard.
  - Confidence Medium.
- **Behaviour gap.** None. The live action-index loader is stricter.

## Slice 8: Org-pack topology `enhances` merge (FR-029)
- **What / why.** `org_pack_loader.merge_topology_artifact` (:812, 67 LOC) with `_merge_action_sequence` (:891), `_merge_action_sequence_step` (:917), `_step_id` and `TOPOLOGY_KINDS` (:268). These are the field-merge semantics for mission step contracts and mission types:
  - `overrides` means full replace.
  - `enhances` means per-field merge, **ordering follows the overlay, and every base step must still appear with its I/O intact**. Otherwise it raises `TopologyMergeError` (:908-913).
- **History.** Introduced in 9a7346100 (2026-06-02, "feat(WP04): augmentation auto-emit single-source + parity (FR-028..FR-032)"). `-S'merge_topology_artifact('` returns only that commit, so it has never been called.
- **What replaced it.** Nothing topology-aware. Live overlays go through `BaseDoctrineRepository._merge_overlay_item` → `_merge` (`offering/base.py:335-360, 411-414`): `{**built_in.model_dump(), **overlay}`. `MissionStepContractRepository` (`step_contracts.py:163`) inherits it and does not override `_merge`. `pack_validator.py:1281` only checks augmentation-edge intent and collisions.
- **Tests.** `tests/doctrine/test_org_pack_augmentation.py` 7t/54L → (a). It pins the documented contract. It needs moving onto whatever live path adopts the semantics; otherwise (b).
- **Open intent.**
  - CLAUDE.md, "specializes_from DRG Lineage": "`enhances` = field-merge (preserves action sequence + step I/O)… Silently dropping steps or stripping step I/O is rejected."
  - ADR `2026-05-16-1` for field-merge.
  - The allowlist Cat-C "ORG_DOCTRINE_CLOSEOUT" ("awaiting production callers in later WPs").
- **Risk if deleted.** Loses the only implementation of a documented safety rule.
- **Verdict.** OWNER-DECISION.
  - **Question:** "Should org `enhances` overlays of step contracts and mission types reject dropped steps and I/O as documented?"
  - **Recommendation:** WIRE by overriding `_merge` in `MissionStepContractRepository` (and the mission-type loader) to call `merge_topology_artifact(base, overlay, mode=ENHANCES)`. Alternatively, amend CLAUDE.md and the ADR and DELETE (132 LOC). Confidence Medium.
- **BEHAVIOUR GAP (bug candidate).** An org overlay that supplies a partial `steps:` list replaces the whole list through the shallow merge, silently dropping the base steps, which the contract says is rejected. Not reproduced here; one test on `MissionStepContractRepository` with a two-step base and a one-step overlay would confirm it.

## Slice 9: Pack identity + relation docs
- **`ensure_pack_identity`** (`org_pack_config.py:721`, 37 LOC) backfills the built-in pack's stable `pack_id`.
  - Introduced in 610cdbfaa (#3500-#3503, pack-manifest unification) and never called.
  - The allowlist note at `test_no_dead_symbols.py:241-244` reads "not wired… until the deferred integration WP (#3518)". Status of #3518 is unknown offline.
  - Tests: `test_pack_id_identity.py` 4t/62L (b).
  - Verdict: KEEP-with-note while #3518 is open, else DELETE. Low risk.
- **`RELATION_DESCRIPTIONS`** (`drg/models.py:154`, 185 LOC) is the prose source of truth for DRG relations.
  - Introduced in ce9d20e6c ("model tension as first-class DRG edges").
  - Read only by the doc-parity tests (`test_relation_doc_parity.py` 2t/23L, `test_models.py` 3t/20L), which keep the docs in sync with the enum. Class (a).
  - Verdict: **KEEP**, allowlisted as "documentation source of truth". Moving it to docs would lose the enum-parity check. Confidence Medium.

## Slice 10: Glossary-in-DRG + entity pages (Phase 5 WP5.1/WP5.5)
- **What / why.**
  - `glossary/drg_builder.build_glossary_drg_layer` (:214, 73 LOC) mints one `NodeKind.GLOSSARY` node per active sense and adds `Relation.VOCABULARY` edges from actions.
  - `GlossaryEntityPageRenderer.generate_all` (`entity_pages.py:106`) writes every term's page to `.kittify/charter/compiled/glossary/`. It reverse-walks `vocabulary` edges out of `.kittify/doctrine/graph.yaml`.
- **History.**
  - `build_glossary_drg_layer`: 6a641841e (2026-04-22, #759 mission-094 "glossary DRG residence") and never called. It was de-exported by harden-dead-symbol-gate-01KW0RJR (comment at :291).
  - `generate_all`: wired in 376653f24 (#763) into `charter.py`, moved to `_status_collectors.py` by 3bd688758 (#1312), and **removed** by f892894e2 (2026-06-17, "charter status side-effect-free", FR-010, #1914 slice). The plan's hook into `ensure_charter_bundle_fresh()` call sites (`kitty-specs/glossary-drg-surfaces-and-charter-lint-01KPTY5Y/plan.md:88,190`) never landed. That mission's status.json still shows every WP `planned`.
- **What replaced it.** Only `generate_one`, used on demand by `glossary show` (`cli/commands/glossary.py:741`). It falls back to the seed store when the term is not in the DRG (:747-755). Nothing in src or packs mints `glossary:*` nodes or `vocabulary` edges; rg over packs/*.yaml and `src/charter` finds none.
- **Tests.**
  - `tests/glossary/test_entity_pages.py` 9t/78L (b, including the 500-term benchmark).
  - `tests/doctrine/drg/test_glossary_node_kind.py` 1t/10L (b).
  - Vacuous guards: `test_status_json_safe.py:249` and `test_status_no_op.py` (2t/43L) assert "not called", which is guaranteed. `test_charter_resynthesize.py:182` patches `entity_pages.GlossaryEntityPageRenderer` (1t/48L), which is never imported there. All three: (b) the assertion; keep each test's other checks.
- **Open intent.** #467 (Phase 5 WP5.1–5.6), #759 and #763. Status unknown offline.
- **Risk.** Deleting it retires a user-visible capability. Leaving it keeps the dashboard lying.
- **Verdict.** OWNER-DECISION.
  - **Question:** "Ship glossary entity pages and vocabulary edges, or retire WP5.1/WP5.5?"
  - **Recommendation:** decide at feature level. To WIRE, call `build_glossary_drg_layer` where the project graph is compiled, and `generate_all` after bundle refresh in `charter generate`/`sync` (the write paths named at `_status_collectors.py:59`). To retire, delete both (91 LOC), the dashboard fields and the `vocabulary` walk. Confidence Medium.
- **BEHAVIOUR GAP.** Three consumers depend on data that is never produced:
  - The dashboard health tile's `entity_pages_generated` (`dashboard/handlers/glossary.py:232-243`) stays false unless someone ran `glossary show`.
  - `drg/query.py:232` walks `vocabulary` edges that never exist.
  - `template/renderer.py:181` annotates `glossary:<slug>` links whose pages may never be generated.

## Slice 11: Glossary scope activation + scope helpers
- **What / why.**
  - `scope.activate_scope` (:280) is the only caller of `events.emit_scope_activated` (:1049, still exported from `glossary/__init__.py:115,201`), so `GlossaryScopeActivated` is never emitted.
  - `get_scope_precedence` (:39) and `should_use_scope` (:56) are trivial list helpers.
  - `validate_seed_file` (:70) is a wrapper over `seed_validation.validate_seed_file_data`.
- **History.**
  - The helpers came with 674cf2e1c and c7202f4d6 (2026-02-16, mission 041 WP01/WP02) and were never called.
  - `validate_seed_file`'s caller in `load_seed_file` was replaced by `validate_seed_file_data` in a75a612a3 (2026-05-27, mission glossary-seed-file-schema-validation-01KSN752).
- **What replaced it.**
  - Middleware uses `SCOPE_RESOLUTION_ORDER` directly (`middleware.py:229`).
  - Seed validation goes through `validate_seed_file_data` (tested in `tests/glossary/test_seed_validation.py`).
  - No mission-start hook emits scope activation.
- **Tests.**
  - `activate_scope`: 3t/57L in `tests/agent/glossary/test_scope.py` and `test_event_emission.py`. Class (b), unless it is wired.
  - precedence/should-use: 2t/14L (b).
  - `validate_seed_file`: 7t/50L. Class (b); the equivalent behaviour is covered in `test_seed_validation.py`.
- **Open intent.** `kitty-specs/041-mission-glossary-semantic-integrity/data-model.md:96`: "Mission start emits `GlossaryScopeActivated` for each active scope". The contract is in `contracts/events.md:20-43`. Mission 041 shows 11/11 WPs done, so this requirement silently lapsed.
- **Risk.** `emit_scope_activated` is public API of the `glossary` package. Downstream event consumers (spec-kitty-events, SaaS) may expect the event; unknown offline.
- **Verdict.**
  - DELETE `get_scope_precedence`, `should_use_scope` and `validate_seed_file` (41 LOC, High).
  - OWNER-DECISION on `activate_scope`: WIRE at mission start, or delete it together with `emit_scope_activated` (68 LOC) and mark the 041 requirement dropped. Recommendation: delete unless a consumer needs the event (Medium).
- **Behaviour gap.** Spec-level: the event promised by 041 is never emitted.

## Slice 12: Glossary WP03 scaffolding
- **What / why.**
  - `extraction.score_confidence` (:382) is a heuristic scorer. The extractors hard-code their confidences.
  - `middleware.MockContext` (:49) is "Mock context for testing… will be replaced by the actual PrimitiveExecutionContext in WP08".
  - `GlossaryCandidateExtractionMiddleware.scan_fields` (:176) is never called.
  - `models.term_sense_to_dict` (:113) is a serializer; the dashboard has its own.
- **History.** 45830e174 / 79e9de9be (2026-02-16, glossary WP03) and c7202f4d6 (WP01). None of these ever had a caller.
- **What replaced it.** The `PrimitiveExecutionContext` Protocol (`middleware.py:27`) with real contexts, and the dashboard handler's own serialization.
- **Tests.**
  - `MockContext` is a harness for 41 tests (`test_middleware.py` 39t/839L, `test_event_emission.py` 2t/45L). Class (a): move the class, not the tests.
  - `score_confidence` 4t/14L (b).
  - `scan_fields` 2t/29L (b).
  - `term_sense_to_dict`: `tests/agent/glossary/test_models.py` 1t/38L (b); `test_glossary_handler.py` 1t/46L builds fixtures with it (c: inline a dict).
- **Open intent.** None.
- **Risk.** Nil.
- **Verdict.**
  - MOVE `MockContext` to `tests/agent/glossary/conftest.py`.
  - DELETE `score_confidence`, `scan_fields` and `term_sense_to_dict` (56 LOC) and their (b) tests.
  - Confidence High.

## Slice 13: Over-internalized upstream runtime (`_internal_runtime`)
- **What / why.** Whole spec-kitty-runtime 0.4.3 features copied during the #796 internalization:

  | Feature | Location | LOC |
  |---|---|---|
  | `notify_decision_timeout` + `TimeoutEscalationResult` | `engine.py:788`; `significance.py:643` | 107 + 12 |
  | `TransitionGate` | `engine.py:902` | 96 |
  | the whole `contracts.py` (`RemediationPayload`), whose only importer is `engine.py:21` for `TransitionGate` | `contracts.py` | 119 |
  | `JsonlEventLog` | `events.py:344` | 32 |
  | `diagnose_shadowing` + `ShadowingDiagnostics` | `discovery.py:344` | 37 |
  | `StepContextContract.validate_contract` | `schema.py:240` | 25 |
  | `serialize_decision` | `planner.py:337` | 8 |
- **History.** All from fda13faf3 (2026-04-25, "shared-package-boundary-cutover: internalize runtime", #796, mission 01KQ22DS). None was ever called from src. The later `TransitionGate` hits (0616a5957, 8fbc4d413 …) are an unrelated "transition-gate hook" string.
- **What replaced it.** Nothing; not needed. The binding contract `kitty-specs/shared-package-boundary-cutover-01KQ22DS/contracts/internal_runtime_surface.md` lists only `DiscoveryContext`, `MissionPolicySnapshot`, `MissionRunRef`, `NextDecision`, `NullEmitter`, `next_step`, `provide_decision_answer`, `start_mission_run`, `schema.{ActorIdentity, load_mission_template_file, MissionRuntimeError}`, `engine._read_snapshot` and `planner.plan_next`. It adds: "Behaviors not on the inventory are not internalized" (:99).
- **Tests.** Only the coverage-padding suites exercise these: `tests/next/test_internal_runtime_coverage.py` (1,875 L, 132 tests; ~9t/~70L touch this slice) and `test_internal_runtime_engine_coverage.py` (724 L, 30 tests; ~6t/~70L). Class (b). The rest of those files covers live code and stays.
- **Open intent.** None. This contradicts the contract.
- **Risk.** Nil: `_internal_runtime` is private by contract.
- **Verdict.** DELETE ~436 src LOC (including `contracts.py`) and ~140 test LOC. Check `StepContextContract`/`ContextTypeRegistry` afterwards: they may become test-only too. Confidence High.
- **Behaviour gap.** None.

## Slice 14: Workflow-sequence next-action resolver (Slice F WP11)
- **What / why.**
  - `planner.resolve_next_workflow_action` (:219, 41 LOC) and `PlanResult` (19 LOC) resolve the next action from `meta.json::workflow_id` through the `WorkflowSequence` graph.
  - `_resolve_workflow_for_mission` (27 LOC) and its wrapper `runtime_bridge_engine.resolve_workflow_for_mission` (:125) are reachable **only** from these and from the DEAD `prompt_builder._workflow_for` (:47). So they are transitively test-only, which the first pass missed.
- **History.** fa80fa0f9 (2026-05-19, "composable workflows", 4 missions); never called from src. `orchestrator_api/commands.py:3885,4088` (d79b28e1a) forbids delegating to it. The comment at `planner.py:70-76` claims it is exercised "by prompt_builder._workflow_for", which is itself dead.
- **What replaced it.** `runtime_bridge_io.py:646-658` composes the workflow into the mission template (`get_workflow` + `compose_template_with_workflow`), and `plan_next` drives the DAG. Semantic difference: with no `workflow_id`, the live path uses the base template, while the dead helper defaults to `software-dev-default`. Likely equivalent for software-dev.
- **Tests.**
  - `tests/integration/test_workflow_sequence_runtime.py` 5t/96L and `test_slice_f_cross_axis.py` 2t/114L → (c). The workflow-ordering assertions (FR-013/FR-015: unknown id raises, no silent fallback) are real product rules. Repoint them at `get_workflow` + `compose_template_with_workflow` / `plan_next`, and drop the `PlanResult` plumbing.
  - `tests/runtime/test_bridge_engine.py` (the wrapper) → (b).
  - Coverage of the live composition: check `tests/runtime` for `compose_template_with_workflow`; otherwise the live path is uncovered for the unknown-id case.
- **Open intent.** None open.
- **Risk.** Low.
- **Verdict.** OWNER-DECISION (Medium).
  - **Recommendation:** DELETE the four symbols and `_workflow_for` (115 LOC) after moving the FR-015 unknown-workflow test onto `get_workflow`. Fix the `planner.py:1-20,70-76` docstrings.

## Slice 15: Runtime thin wrappers
- **`evaluate_guards`** (`runtime_bridge_cores.py:847`, 17 LOC) is a tolerant wrapper over `evaluate_guards_strict` that swallows `UnregisteredMissionFamilyError`.
  - History: live since 767ca9131. Its production callers (`runtime_bridge.py`, `runtime_bridge_composition.py`) were switched to `_strict` by 4f4b6187b (2026-08-17, #3386 "no silent software-dev fall-through"). The docstring now says it is "kept… only for existing direct test callers".
  - Tests: `tests/runtime/test_bridge_cores.py` 36t/327L, plus `test_bridge_composition.py` 1t/43L and `tests/runtime/next/test_cli_guard_family.py` 1t/13L. Class (a): they pin the guard table the live `_strict` uses. Rename them to `evaluate_guards_strict`, and flip the unregistered-family cases to `pytest.raises`.
  - Stale comment at `runtime_bridge.py:1873` ("composition-dispatch's own tolerant `evaluate_guards` remains the authority") is false: composition uses `_strict` (`runtime_bridge_composition.py:571`).
  - Verdict: MOVE-TESTS-THEN-DELETE. High.
- **`_record_path_str`** (`retrospective_terminus.py:68`, 13 LOC).
  - Introduced in 9733727df (#821). The emit sites now build the payload inline from `write_record`'s return (`record_path=str(canonical_path)` at :294, :418, :473).
  - Tests: `test_retrospective_durable_home_coord.py:207-226` (1t/20L) is a **vacuous regression guard**: it tests the orphan, not the emitted payload. Retarget it at the `CompletedPayload` emitted by the terminus (a).
  - `test_home_resolution_single_authority.py:166` is an AST scan of the module for hardcoded `.kittify` payloads. It stays valid; only its docstring names the helper.
  - Live coverage: no test asserts the terminus-emitted `record_path`, so it is uncovered.
  - Verdict: MOVE-TESTS-THEN-DELETE. High.

---

## Corrections to the first pass
1. **`progressive_disclosure.partition_delivery` is LIVE.** 8bf5114a6 (2026-07-30) added an in-module call at `progressive_disclosure.py:210` inside `profile_channel_references`. That function is live via `context_renderers/profile_sections.py:487`. The `__all__` comment at :385-388 ("genuinely forward API with no `src/` caller") and the `_CATEGORY_C_DELIVERY_RAIL_FORWARD_API` row are stale. Action: remove it from the allowlist; optionally demote it from `__all__`.
2. **`synthesizer.manifest.compute_manifest_hash` is LIVE.** `finalize_manifest` (:271) and `verify_manifest_hash` (:296) call it, and `verify_manifest_hash` is called from `charter/bundle.py:569` and `activation/project_registration.py`. The #3518 "deferred API" allowlist grouping is wrong for it. It is API used in its own module: demote it from `__all__`.
3. **`reachability.PROFILE_CHANNEL_RELATIONS` is LIVE.** It is used at `reachability.py:135` by `profile_channel_reachable`, which is live (`agent_profiles/repository.py:26`). Only `action_channel_reachable` and `action_seed_urns` in that module are test-only.
4. **`org_pack_loader.AUGMENTATION_RELATIONS` is LIVE** in its own module (:696-698 `_PROJECTION_FIELD_TO_RELATION`). Of the "topology trio", only `TOPOLOGY_KINDS` (0 code uses) and `merge_topology_artifact` are test-only.
5. **`kernel.locks.STALE_AFTER_S_DEFAULT` is LIVE.** It is the default of `force_release` (:376), which `_auth_doctor.py:824` calls, and of the lock constructor at :612. Only `is_stuck` is test-only.
6. **`normalize_activation_identifier` is not live.** The first pass counted it live through "4 code uses in its own module", but every in-module caller (`partition_activated_unreachable`, `charter_activated_urns`) is itself test-only. It is **TEST-ONLY transitively**, together with `_resolve_activation_kind` and `_ACTIVATION_URN_KINDS`.
7. **Transitively test-only, missed:**
   - `runtime_bridge_engine.resolve_workflow_for_mission`, `planner._resolve_workflow_for_mission` and `PlanResult` (slice 14).
   - `step_contracts.resolve_step_contract_ids` and `_resolve_expected_artifacts_slot` / `_resolve_step_contracts_slot` (slice 3).
   - `pack_manager._load_default_pack` (slice 1).
   - `_internal_runtime/contracts.py` as a whole module (slice 13).
   - `glossary.events.emit_scope_activated` (slice 11; only an `__init__` export).
8. **`resolve_mission_definition` belongs with the DEAD `template_resolver` removal.** Its only test file (`test_resolver_tier_axis_via_factory.py`) is the one already slated to go with that module.
9. **Vacuous tests: the first pass's three are confirmed, and there is one more.**
   - Confirmed: `test_retrospective_durable_home_coord.py:207`, `test_status_json_safe.py:249` and `test_charter_resynthesize.py:182`.
   - Additional: `test_status_no_op.py:223-239` asserts that the collector writes no entity pages. That cannot fail, because nothing calls `generate_all`. Keep its other no-op checks.
