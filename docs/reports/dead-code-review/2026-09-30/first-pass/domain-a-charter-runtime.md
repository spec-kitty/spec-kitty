---
doc_status: active
updated: '2026-09-30'
---

# Dead-code review, first pass — Domain A: charter, glossary, kernel, mission_runtime, runtime

Part of the [dead-code review of 2026-09-30](../README.md). Analysed at `origin/main` `bd1577a3`.

## Domain summary

The runtime surfaces in this domain (charter activation, the DRG, glossary, runtime.next) are live. Most of the dead code is **residue from god-module splits and "thin delegate" refactors**, plus **forward APIs that never got a caller**. The largest items are:
- the three `_internal_runtime` "frozen" re-export modules;
- the `doctrine.py` shim, which is now overdue for removal;
- `synthesize_pipeline.run` (170 LOC, superseded by `run_all`);
- the unused re-export aliases in `charter.offering.shared` and the kind subpackages;
- two grandfathered orphan modules (`charter.parser`, `charter.activation.template_resolver`) whose own deadline, "target = 0 by 4.0", has passed now that the version is 4.0.0rc5.

About a third of the `test_no_dead_symbols.py` allowlist rationales for this domain are stale. The cited missions are done, the cited contracts do not say what the comment claims, or the named symbol now has a caller or no longer exists. The unratcheted `_WIDENED_SCOPE_GRANDFATHERED_470` set holds one entry whose caller now exists and one entry whose module no longer exists.

| Class | Count |
|---|---|
| DEAD | 28 (25 High, 3 Medium) |
| TEST-ONLY | 55 |
| API/DYNAMIC | 32 |
| FALSE-POSITIVE | ~75 (vulture YAML/regex attribute noise, 22 ERA001 prose comments, 1 protocol param) |

Estimated removable LOC:
- **High-confidence DEAD:** about 480 LOC of src.
  - Symbols: about 285 LOC.
  - The `_internal_runtime` emitter/lifecycle/models modules: 80 LOC.
  - `src/doctrine.py`: 115 LOC.
- **Medium DEAD:** another about 450 LOC (`charter/parser.py` 276 and `template_resolver.py` 176).
- **TEST-ONLY:** the "remove with tests" subset adds about 700 src LOC, mostly `_internal_runtime` engine and planner helpers, `merge_defaults`, `build_glossary_drg_layer`, and the five `validate_<kind>` clones.

Evidence method: for every name I ran `rg -w NAME src packs scripts pyproject.toml .kittify .github` excluding the defining file, then `rg -l -w NAME tests`. For allowlisted names I also checked for `from <module> import` sites and for code uses inside the defining module (to separate "unused" from "used only inside its own module"). I read each definition before classifying it.

## Findings by module

### charter.activation (+ charter top-level)

| file:line | symbol (kind) | class | evidence | confidence | action |
|---|---|---|---|---|---|
| src/charter/activation/synthesizer/synthesize_pipeline.py:329 | `run` (func, 170 LOC) | DEAD | Its docstring says it implements `orchestrator.synthesize()`, but orchestrator.py:229 imports `run_all`. No `synthesize_pipeline.run` or `import run` hit in src or tests. Allowlisted in `_WIDENED_470`. | High | remove, and fix the stale docstrings in test_orchestrator_synthesize.py:4,183 and test_schema_conformance.py:4 |
| src/charter/activation/compiler.py:1778 | `_trim_source_path` (func) | DEAD | src hits are docstrings only (compiler.py:1531, provenance.py:107, m_3_2_7 docstring). Superseded by the `charter.offering.provenance` normalizer; tests mention it only in prose (test_provenance_normalizer.py:146). | High | remove |
| src/charter/activation/catalog.py:208 | `_resolve_doctrine_root` (func) | DEAD | Comment says "alias for existing private callers", but there are 0 hits in src, tests or scripts. | High | remove |
| src/charter/activation/catalog.py:353 | `_load_template_sets` (func) | DEAD | 0 refs anywhere. Only `_load_template_sets_with_presence` is used. | High | remove |
| src/charter/activation/catalog.py:28 | `DEFAULT_TEMPLATE_SET` (const) | DEAD | Only its own definition in catalog.py. The live copy is resolver.py:95, used at :915 and :1033. | High | remove the duplicate |
| src/charter/activation/context.py:121 | `NONE_LABEL` (const) | DEAD | Only its own definition in context.py. compact.py:36 has its own `NONE_LABEL`, used at :320. | High | remove |
| src/charter/activation/compiler.py:78 | `_SelectionBundle` (dataclass) | DEAD | 0 refs anywhere. | High | remove |
| src/charter/activation/context_json.py:58 | `_DirectivesConfigLike` (Protocol) | DEAD | 0 refs anywhere. | High | remove |
| src/charter/activation/synthesizer/interview_mapping.py:323 | `_section_is_nonempty` (func) | DEAD | 0 refs anywhere. | High | remove |
| src/charter/activation/evidence/code_reader.py:84 | `LANGUAGE_EXTENSIONS` (dict) | DEAD | Only its own definition in code_reader.py; 0 refs in tests or src. | High | remove |
| src/charter/bundle.py:41-43 | `GOVERNANCE_YAML` / `DIRECTIVES_YAML` / `METADATA_YAML` (consts) | DEAD | Each is used only at its own definition; 0 refs in tests or src. | High | remove |
| src/charter/activation/template_resolver.py (module, 176 LOC) | `CharterTemplateResolver` | DEAD | Module docstring: "thin delegate… its one production caller no longer uses this class". Only src refs are the lazy map in charter/__init__.py:129,211 and docstrings. Tests: test_template_resolver.py, test_resolver_tier_axis_via_factory.py. | Medium (lazy `charter.*` export) | remove, with its tests, the `charter/__init__` lazy map entries, and pyproject.toml:369,1162 |
| src/charter/parser.py (module, 276 LOC) | `CharterParser` / `CharterSection` | DEAD | Only src ref is the lazy map in charter/__init__.py:78-79. Test: tests/charter/test_parser.py. The vulture hit `requires_ai` is a field of it. | Medium | remove, with test_parser.py and the lazy map entries |
| src/charter/activation/pack_manager.py:1067 | `merge_defaults` (+ `MergeResult` :533) | TEST-ONLY | src hits are docstrings only (charter_yaml_io.py:4,624,644; state/contract.py:542). The 6 test files call it directly. The docs present it as a live INV-9 mutator, which is false. | Medium | needs-owner-decision: wire it into `charter init`/`upgrade`, or remove it with its tests and fix the charter_yaml_io docs |
| src/charter/activation/_catalog_miss.py:185 | `CharterCatalogMissError` (exc) | TEST-ONLY | Never raised in src. Only test_context_catalog_miss.py:323 constructs it. | High | remove with its test |
| src/charter/activation/context_json.py:183 | `_load_project_directives` (func) | TEST-ONLY | Docstring: "backward-compatible 2-tuple wrapper… existing seam tests pin this arity". Only test_context.py:889 and test_context_service_seams.py:120 call it. | High | remove, and repoint the tests at `_with_source` |
| src/charter/activation/catalog.py:212 | `_load_yaml_id_catalog` (func) | TEST-ONLY | src_other hits are comments (pack_manager.py:377, kind_vocabulary.py:98). Only test_catalog.py:216 calls it. | High | remove, and repoint the test at `_with_presence` |
| src/charter/activation/_io.py:124 | `load_charter_bytes` (func) | TEST-ONLY | 0 src callers. 3 test files use it (encoding_chokepoint, unsafe_bypass, io_edge_paths). Described as the "inline ingest path", but no ingest calls it. | Medium | needs-owner-decision |
| src/charter/activation/mission_type_profiles.py:458,465 | `expected_artifacts` / `step_contracts` (cached_property) | TEST-ONLY | No `.expected_artifacts` or `.step_contracts` attribute reads in src. These are the WP10/WP11 slots; their thunks are also built only for these properties. | Medium | needs-owner-decision (unfinished consumer) |
| src/charter/activation/invocation_context.py:143,181 | `require_org_root` / `require_active_profile` (methods) | TEST-ONLY | 0 src callers. Tests: test_invocation_context.py, test_operational_context.py. | Medium | remove with tests, or wire |
| src/charter/activation/resolver.py:517 | `resolve_mission_definition` (staticmethod) | TEST-ONLY | 0 src callers. Test: test_resolver_tier_axis_via_factory.py. Also mentioned in .kittify evidence notes. | Medium | remove it, together with template_resolver |
| src/charter/activation/pack_context.py:388-554; progressive_disclosure.py:94 | delivery-rail forward API: `charter_activated_urns`, `partition_activated_unreachable`, `ActivationReachabilityPartition`, `partition_delivery`, `normalize_activation_identifier` | TEST-ONLY | src hits are docstrings or comments only (empty_charter.py:35). `normalize_activation_identifier` is used inside its own module (4 code uses) and so is live. | Medium | needs-owner-decision (#3063). At minimum, drop `normalize_activation_identifier` from `__all__` |
| src/charter/activation/context_contract.py:82 | `CONTEXT_CONTRACT_TOP_LEVEL_KEYS` (const) | TEST-ONLY | 0 code uses in its own module or in src. 4 test files use it as a schema oracle. | Low | keep as a test oracle, or move it to tests |
| src/charter/activation/synthesizer/manifest.py:237 | `compute_manifest_hash` | TEST-ONLY | Used in its own module, but no cross-file caller. 2 tests. Deferred behind #3518. | Low | keep-with-note |
| src/charter/activation/interview.py:415 | `InterviewAnswersRegressionError` | TEST-ONLY | Raised only when `fail_closed_on_regression=True`, and no src caller passes that. | Low | keep-with-note, or drop the flag and the error |
| src/charter/activation/compact.py:64 | `CompactView.token_estimate` (property) | TEST-ONLY | Used only by test_compact.py. | Low | remove, or keep for smoke checks |
| src/charter/activation/pack_context.py:446 | `normalization_delta` (property) | TEST-ONLY | 2 test files. | Low | keep-with-note |
| src/charter/activation/synthesizer/reconcile.py:203 | `has_backed_removals` (property) | TEST-ONLY | 1 test. | Low | remove, or keep |
| src/charter/activation/synthesizer/adapter.py:111 | `BatchCapableSynthesisAdapter` (Protocol) | TEST-ONLY | Its name appears only at its own definition; the pipeline duck-types. Test: test_adapter_contract.py. | Low | keep as a typing contract, or remove |
| src/charter/activation/pack_manager.py:521 | `ActivationResult` | API | The live return type of `CharterPackManager.deactivate`, called by cli/commands/charter/deactivate.py:300. | High | keep. The allowlist category is stale (see below) |
| charter_yaml_io `OWNED_SECTIONS` / `UnknownCharterYamlSectionError`; compact `CompactView` / `extract_section_anchors`; `_catalog_miss` `CatalogMissCause` / `CharterCatalogMissWarning`; activations `ALLOWED_MISSION_TYPES` / `REGISTERED_TRIGGERS`; write_pipeline `StagedArtifact`; cascade `DeactivationPlan` / `ReferencedArtifact` / `SharedSkip`; activation_engine `ActivationPlan` | (types and consts) | API | Each has 2 to 14 code uses inside its own module and 0 cross-file imports. They are live, not "library never wired". | High | keep; drop them from `__all__` so the allowlist rows can go |
| invocation_context `ContextPreconditionError`; mission_type_profiles `MissionTypeEmptyActionSequenceError`; sync `LegacyGovernanceKeyWarning` | (exc / warning) | API | Raised in their own module and meant to propagate or to be filtered. The activate.py hits are comments. | High | keep-with-note |

### charter.offering

| file:line | symbol (kind) | class | evidence | confidence | action |
|---|---|---|---|---|---|
| src/charter/offering/shared/__init__.py | re-exports `ConflictType`, `ExtractedTerm`, `GlossaryScope`, `ScopeRef`, `SemanticConflict`, `SenseRef`, `Severity`, `Strictness`, `TermSurface` | DEAD | `rg "from charter\.offering\.shared import"` across src, tests and scripts only hits `scoping`. Every consumer imports from `kernel.glossary_types` or `glossary`. | High | remove the 9 re-exports and the docstring block (Cat B) |
| src/charter/offering/{directives,tactics,procedures}/__init__.py | `ArtifactKind` re-export | DEAD | 0 `from charter.offering.(directives\|tactics\|procedures) import …ArtifactKind` hits in src, tests or scripts. | High | remove (Cat B) |
| src/charter/offering/missions/__init__.py:14; repository.py:551 | `MissionRepository` aliases | DEAD | 0 importers anywhere; the only hit is the alias's own comment at repository.py:549-550. | High | remove both (Cat B + `_470`) |
| src/charter/offering/drg/migration/hand_authored_overlay.py:2166,2171 | `hand_authored_node_urns` / `hand_authored_edge_keys` | DEAD | Only hits outside the defining file are the allowlist lines test_no_dead_symbols.py:3709-3710. | High | remove |
| src/charter/offering/missions/mission_step_repository.py:164 | `StepKey` | TEST-ONLY | Its docstring (line 16) says it "enforces this at the cache layer", but the class is never used in code. 1 test. | High | remove, or wire into the cache key |
| src/charter/offering/{directives,paradigms,styleguides,tactics,toolguides}/validation.py:16-21 | `validate_<kind>` ×5 (27 LOC each, near-identical) | TEST-ONLY | 0 src callers; the repositories validate via pydantic plus `reject_*_inline_refs`. Tests use them as JSON-schema conformance checks. | Medium | fold into one `validate_artifact(kind, data)` or move to a tests helper |
| src/charter/offering/agent_profiles/validation.py:76 | `is_agent_profile_file` | TEST-ONLY | 0 src callers. 2 test files. | Medium | move to tests, or remove |
| src/charter/offering/agent_profiles/repository.py:670,760,788 | `find_by_role` / `get_hierarchy_tree` / `validate_hierarchy` | TEST-ONLY | 0 src callers. `validate_hierarchy` guards the shipped profiles in test_shipped_profiles.py. | Medium | keep `validate_hierarchy` as a test harness; remove the other two with their tests |
| src/charter/offering/agent_profiles/profile.py:95 | `Role.is_known` | TEST-ONLY | 2 tests only. | Low | remove, or keep |
| src/charter/offering/missions/repository.py:271,299,322 | `list_command_templates` / `list_content_templates` / `get_action_index` | TEST-ONLY | 0 src callers; runtime uses `missions.action_index`. The .kittify/overrides/missions/repository.py hits are a stale vendored copy. | Medium | remove with tests. Separately, audit `.kittify/overrides/missions/` (an old doctrine package copy) |
| src/charter/offering/missions/mission_type_repository.py:121 | `load_all` | TEST-ONLY | 4 test files. | Low | keep-with-note |
| src/charter/offering/versioning.py:69 | `needs_migration` (property) | TEST-ONLY | 2 test files. | Low | keep-with-note |
| src/charter/offering/template_catalog.py:206,227 | `template_node` / `template_nodes` | TEST-ONLY | The extractor.py:1805 hit is a local variable with the same name. 3 test files. | Medium | remove with tests, or wire |
| src/charter/offering/drg/org_pack_loader.py:259,268,812 | `AUGMENTATION_RELATIONS` / `TOPOLOGY_KINDS` / `merge_topology_artifact` | TEST-ONLY | Only test_org_pack_augmentation.py uses them. `TOPOLOGY_KINDS` has 0 code uses in its own module. | Medium | needs-owner-decision |
| src/charter/offering/drg/org_pack_config.py:721 | `ensure_pack_identity` | TEST-ONLY | 1 test (test_pack_id_identity.py). Deferred behind #3518. | Low | keep-with-note |
| src/charter/offering/drg/reachability.py:59-107 | `action_channel_reachable` / `action_seed_urns` / `PROFILE_CHANNEL_RELATIONS` | TEST-ONLY | src hits are comments (hand_authored_overlay.py:1150, extractor.py:497, profile_sections.py:341). | Medium | needs-owner-decision (#3063) |
| src/charter/offering/drg/models.py:154 | `RELATION_DESCRIPTIONS` (185 LOC) | TEST-ONLY | Consumed only by the doc-parity tests (test_relation_doc_parity.py and 3 others). | Low | keep-with-note as the doc source of truth |
| src/charter/offering/agent_profiles/repository.py:832 | `find_best_match` | API | Documented agent-facing API in the shipped skill (skills/spec-kitty-charter-doctrine/SKILL.md:442,753). | High | keep-with-note |
| agent_profiles/schema_models `AgentProfileSchema`; import_candidates/models `Legacy/CurationImportCandidate`; missions/models `Mission` | schema models | API | Loaded by scripts/generate_schemas.py:390-392,529,550-551 via importlib. | High | keep. Move `Mission` from Cat B into the schema-generator rationale |
| step_contracts `DelegatesTo`; missions/models `IDENTIFIER_PATTERN` / `VALID_PATH_KEYS` / `validate_path_conventions`; drg/org_pack_config `LegacyOrgPackDoctrineKeyWarning`; `charter.drg::load_graph`, `merge_three_layers`; `charter.assets::AssetManifest` / `AssetResolutionError`; `charter.model_routing::CatalogLoadResult` | (types, consts, facades) | API | Pydantic field types or pattern consts used in their own module, forward-slot APIs, and facade re-exports that the facade test enforces. | High | keep. For the facades, **wire** consumers (see the stale rationales below) |

### glossary

| file:line | symbol (kind) | class | evidence | confidence | action |
|---|---|---|---|---|---|
| src/glossary/semantic_events.py:201 | `is_high_severity` | DEAD | Only hit outside the defining file is its allowlist line; 0 hits in src or other tests. | High | remove (with `_HIGH_SEVERITIES` if that is otherwise unused) |
| src/glossary/clarification.py:163 | `_emit_deferred` (method) | DEAD | "Backward-compat alias". 0 refs in src or tests. | High | remove |
| src/glossary/store.py:21 | `GlossaryStore.load_from_events` | DEAD | Body is `pass  # WP08 will implement`. The only other ref is a comment at drg_builder.py:157 noting it is a stub. | High | remove the stub (or implement it) |
| src/glossary/entity_pages.py:106 | `GlossaryEntityPageRenderer.generate_all` | TEST-ONLY | Only a docstring ref in src (_status_collectors.py:52). The CLI uses `generate_one`, and nothing regenerates all pages. **Vacuous patch surface:** tests/specify_cli/cli/commands/test_charter_resynthesize.py:182 patches `entity_pages.GlossaryEntityPageRenderer`, which `_collect_charter_sync_status` never imports. The sentinel at tests/.../charter/test_status_json_safe.py:249 cannot fail because nothing calls `generate_all`. | Medium | wire it into `charter generate`/`sync` (the collector comment implies it runs there), or remove it with its tests |
| src/glossary/scope.py:280 | `activate_scope` | TEST-ONLY | The only caller of `emit_scope_activated` (events.py:1049). So `GlossaryScopeActivated` is never emitted in production. | Medium | needs-owner-decision (unfinished feature) |
| src/glossary/scope.py:39,56,70 | `get_scope_precedence` / `should_use_scope` / `validate_seed_file` | TEST-ONLY | 0 src callers. `validate_seed_file` is a thin wrapper over `seed_validation.validate_seed_file_data`. | High | remove with tests |
| src/glossary/extraction.py:382 | `score_confidence` | TEST-ONLY | 0 src callers; the extractors hard-code confidences. | High | remove with its test |
| src/glossary/middleware.py:48 | `MockContext` (test double in src) | TEST-ONLY | Docstring: "Mock context for testing… replaced in WP08". Used by tests/agent/glossary/* only. | High | move to tests/agent/glossary/conftest.py |
| src/glossary/middleware.py:176 | `scan_fields` | TEST-ONLY | 1 test. | Medium | remove with its test |
| src/glossary/models.py:113 | `term_sense_to_dict` | TEST-ONLY | 2 test files (test_models.py, test_glossary_handler.py). The dashboard handler has its own serializer. | Medium | remove with tests |
| src/glossary/drg_builder.py:214 | `build_glossary_drg_layer` (73 LOC) | TEST-ONLY | Other functions in the module are live (chokepoint.py:20); this one is used only by test_glossary_node_kind.py. | Medium | needs-owner-decision |
| src/glossary/middleware.py:655,686 | `context.resumed_from_checkpoint` / `checkpoint_cursor` (output attributes) | API | Written onto the caller's context; only tests read them. | Low | keep-with-note |
| semantic_events `SemanticConflictRecord` | type | API | 10 code uses inside its own module; the public return type of `iter_semantic_conflicts`. | High | keep; drop the Cat-B row |

### kernel

| file:line | symbol (kind) | class | evidence | confidence | action |
|---|---|---|---|---|---|
| src/kernel/_safe_re.py:217 | `is_re2_active` | TEST-ONLY | Always returns True (re2 is a hard dependency). Tests only assert True (test_safe_re.py:237, test_requirement_id_grammar.py:25). | High | remove with those asserts |
| src/kernel/locks.py:178,114 | `is_stuck` + `STALE_AFTER_S_DEFAULT` | TEST-ONLY | `STALE_AFTER_S_DEFAULT` is used only as `is_stuck`'s default. Tests: test_locks.py, test_locks_symlink_safe.py. | Medium | remove together, or wire into lock diagnostics |
| kernel.clock `SystemClock` / `FrozenClock`; doctrine_root `CANONICAL_DOCTRINE_DIRNAME` / `LegacyDoctrineRootWarning`; env_expand `UnresolvedEnvTokenError`; glossary_runner `clear_registry` | – | API | `SystemClock` backs `DEFAULT_CLOCK`. `FrozenClock` is an intentional test double. The others are raised or used in their own module, or (`clear_registry`) are a documented test hook (kernel/README.md:18). | High | keep |

### mission_runtime

| file:line | symbol | class | evidence | confidence | action |
|---|---|---|---|---|---|
| src/mission_runtime/checkout_identity.py:77 | `_is_within` | DEAD | 0 refs in src or tests; the module classifies paths via `_checkout_root`. | High | remove |

### runtime.next (+ `_internal_runtime`)

| file:line | symbol (kind) | class | evidence | confidence | action |
|---|---|---|---|---|---|
| src/runtime/next/_internal_runtime/{emitter,lifecycle,models}.py (80 LOC) | pure re-export modules | DEAD | Only importer is tests/next/test_internal_runtime_coverage.py:36-40. The cited contract does not freeze them (see stale rationales). | High | delete the modules, the coverage-test imports, and the dead-modules Cat-6 entries |
| src/runtime/next/_internal_runtime/schema.py:55 | `CommitContext` (model) | DEAD | Only hit outside the defining file is its allowlist line (test_no_dead_symbols.py:3735). | High | remove |
| src/runtime/next/_internal_runtime/schema.py:330,344,348 | `ContextTypeRegistry.get_builtin_type` / `register_custom_type` / `get_all_types` | DEAD | 0 refs in src or tests. Only `is_registered` is live (schema.py:233). | High | remove |
| src/runtime/next/runtime_bridge.py:201 | `KITTIFY_DIR` | DEAD | Only its definition in runtime_bridge.py. **Vacuous assert:** tests/runtime/test_bridge_io.py:141-143 says it is "still used by unmoved residual code" and asserts `hasattr(rb, "KITTIFY_DIR")`, but it is not used. | High | remove, and drop the assert |
| src/runtime/next/prompt_builder.py:47 | `_workflow_for` | DEAD | 0 refs in src or tests (T1). The module's WP11 docstring line 6 is stale. | High | remove |
| src/runtime/next/_internal_runtime/significance.py:434 | `effective_timeout_seconds` (property) | DEAD | 0 refs anywhere. | Medium (pydantic model API) | remove |
| src/runtime/next/_internal_runtime/retrospective_terminus.py:68 | `_record_path_str` | TEST-ONLY | The payload is built inline (`record_path=str(canonical_path)` at :294,:418). **Vacuous regression guard:** tests/retrospective/test_retrospective_durable_home_coord.py:216 and test_home_resolution_single_authority.py:166 guard this orphaned helper, not the real emit site. | High | remove, and retarget the tests at the emitted payload |
| src/runtime/next/_internal_runtime/engine.py:788,902 | `notify_decision_timeout` (107 LOC, + `TimeoutEscalationResult` significance.py:642), `TransitionGate` (96 LOC) | TEST-ONLY | Used only by the tests/next/test_internal_runtime_*coverage.py tests. The contract says behaviours outside the inventory are "not internalized". | High | remove with the coverage tests |
| src/runtime/next/_internal_runtime/events.py:344,365 | `JsonlEventLog` / `.read_all` | TEST-ONLY | 0 code uses in src. Coverage test only. | High | remove |
| src/runtime/next/_internal_runtime/planner.py:219,337 | `resolve_next_workflow_action`, `serialize_decision` | TEST-ONLY | orchestrator_api/commands.py:3885,4088 say it "never delegates" to it. Tests: integration/test_workflow_sequence_runtime.py and test_slice_f_cross_axis.py. | Medium | remove, or wire |
| src/runtime/next/_internal_runtime/discovery.py:344 | `diagnose_shadowing` | TEST-ONLY | Coverage test only. | High | remove |
| src/runtime/next/_internal_runtime/schema.py:240 | `validate_contract` | TEST-ONLY | Coverage test only. | Medium | remove |
| src/runtime/next/runtime_bridge_cores.py:847 | `evaluate_guards` | TEST-ONLY | All src hits are prose (runtime_bridge.py:895,1873; runtime_bridge_io.py:16,1091,1305). 7 test files, including the parity test tests/dossier/test_manifest_guard_parity.py, pin a function that production never calls. | Medium | wire the bridge to use it (the intended "pure core"), or remove it and its parity tests |
| `runtime.next.committed_authority::mission_terminal_verdict` | func | API (live) | Imported and called at runtime_bridge.py:2414-2416. | High | keep. The allowlist entry is stale |
| discovery `ClaimablePreview`; workflow_registry `UnknownWorkflowError`; charter/offering resolver `_reset_migrate_nudge`; `_reset_agent_profile_cache`; `_reset_emitted_for_testing` | – | API | Return type used inside its own module, a propagated exception, and test-reset hooks. | High | keep |

### doctrine.py

| file:line | symbol | class | evidence | confidence | action |
|---|---|---|---|---|---|
| src/doctrine.py (115 LOC) | deprecation shim | DEAD | `__removal_release__ = "3.3.0"`, and docs/migrations/shim-registry.yaml:25 sets `removal_target_release: "3.3.0"`, but pyproject says `version = "4.0.0rc5"`. 0 `import doctrine` / `from doctrine import` hits in src, tests or scripts. | High | delete the file, the shim-registry entry and dead-modules Cat-4 (tracker #805) |

## Stale allowlist rationales

1. **`_WIDENED_SCOPE_GRANDFATHERED_470`: `runtime.next.committed_authority::mission_terminal_verdict`.** The rationale says the caller was "deferred on the #1065 re-port queue". The caller now exists: runtime_bridge.py:2414 imports it and calls it at :2416. **Action:** delete the entry.
2. **`_WIDENED_SCOPE_GRANDFATHERED_470`: `charter.offering.hatch_build::DoctrinePacksSiblingBuildHook`.** The module does not exist (`find -name "hatch_build*"` finds nothing, and pyproject.toml:153 records `hatch_build.py` as DELETED). The widened set is only used as an offender filter (test_no_dead_symbols.py:3949) and has **no dangling/stale ratchet**, so rot like this is invisible. **Action:** delete the entry, and add a dangling check for `_WIDENED_470`.
3. **`_WIDENED_SCOPE_GRANDFATHERED_470`: `runtime.next.runtime_bridge::KITTIFY_DIR`, `synthesize_pipeline::run`, `hand_authored_*`.** These are simply dead, not "debt pending triage". **Action:** delete the symbols and the entries (#633).
4. **Dead-modules `_CATEGORY_6_FROZEN_RUNTIME_REEXPORTS`** (`_internal_runtime.{emitter,lifecycle,models}`). The rationale cites `contracts/internal_runtime_surface.md` as freezing a "per-task-layout surface". The contract actually does three things:
   - It lists only `__init__` exports plus `schema` / `engine` / `planner` symbols, and never mentions emitter, lifecycle or models.
   - It says the internalized code "MAY restructure the sub-module layout".
   - It says "External Python importers MUST NOT reach into `_internal_runtime`".

   **Action:** delete the three modules and the category.
5. **Dead-modules `_CATEGORY_7_GRANDFATHERED_ORPHANS`** (`charter.parser`, `charter.activation.template_resolver`). The category says "target = 0 by 4.0", and the version is 4.0.0rc5. `template_resolver`'s own docstring says production no longer uses it. **Action:** delete both (#925).
6. **Dead-modules `_CATEGORY_4_BACKCOMPAT_SHIMS`** (`doctrine`). It is past its registered removal release (3.3.0). **Action:** delete.
7. **`_CATEGORY_C_WP_IN_FLIGHT_CHARTER_ACTIVATION`** ("callers in WP06/WP08", mission 01KSYE4V). That mission's status.json shows **11/11 WPs done**. `ActivationResult` is a live return type (the deactivate.py:300 CLI path). `MergeResult` belongs to the test-only `merge_defaults`. **Action:** move `ActivationResult` to a "structurally-consumed return type" rationale (or drop it from `__all__`), and decide on `merge_defaults`/`MergeResult`.
8. **`_CATEGORY_C_WP_IN_FLIGHT_UNIFIED_MISSION_STEP`** (01KSWJVX WP03-05). All 15 WPs are approved. `StepKey` still has no user, and its docstring claim about the cache layer is false. `DelegatesTo` is a live pydantic field type. **Action:** remove `StepKey` (or wire it into the cache), and demote `DelegatesTo` from `__all__`.
9. **`_CATEGORY_C_CHARTER_FACADE_FORWARD_API_01KZPDSR`.** The rationale says consumer WPs WP05–WP07 "have NOT landed". Mission doctrine-public-api-surface-01KZPDSR is 10/10 done. Runtime still bypasses the doors, for example specify_cli/doctrine/pack_validator.py:194 (`from charter.offering.assets.models import AssetManifest`) and pack_assembler.py:206 (`from charter.offering.drg.loader import … load_graph`). **Action:** wire these importers through `charter.assets` / `charter.drg` / `charter.model_routing`, which also clears the Cat-C rows.
10. **`_CATEGORY_A_SLICE_F_DEFERRED`** ("library written but never wired; target 0 by Slice G"). Most rows in my domain are **used inside their own module** (`CompactView`, `extract_section_anchors`, `CatalogMissCause`, `CharterCatalogMissWarning`, `ALLOWED_MISSION_TYPES`, `REGISTERED_TRIGGERS`, `StagedArtifact`), not unwired. The header comment (line 152) says `is_re2_active` was "rescued by detector (a)", yet it is still listed (lines 239-240), and it always returns True. `CharterCatalogMissError` is never raised. **Action:**
    - demote the in-module-live symbols from `__all__`;
    - delete `is_re2_active` and `CharterCatalogMissError`.
11. **`_CATEGORY_B_GRANDFATHERED_LEGACY`** (my domain's rows). The `charter.offering.shared` ×9 re-exports, the `ArtifactKind` ×3 re-exports and the `MissionRepository` ×2 aliases have zero importers even in tests. They are dead re-export shims, not legacy API. `Mission` is a schema-generator model and belongs with the Cat-2-style rationale. `SemanticConflictRecord` and `SystemClock` are live inside their own modules. **Action:**
    - delete the re-exports;
    - recategorize the rest.
12. **`_CATEGORY_C_WP_IN_FLIGHT_CHARTER_YAML_IO_WRITE_HELPER`.** The rationale (and charter_yaml_io.py:4,624) names `pack_manager.merge_defaults` as one of three live INV-9 mutators. It has no src caller. **Action:** correct the rationale and docstrings once `merge_defaults` is decided.
13. **`_CATEGORY_C_ORG_DOCTRINE_CLOSEOUT`** ("awaiting production callers in later WPs of the same mission family"). No such WPs are identifiable. The cascade `DeactivationPlan` / `ReferencedArtifact` / `SharedSkip` and `ActivationPlan` are used inside their own modules. `template_node(s)` and the `org_pack_loader` topology trio are test-only. **Action:** demote the in-module-live symbols, and put the test-only ones to an owner.

## Notable patterns

- **Thin-delegate / god-split residue.** Splits left behind unused compat wrappers and aliases: `template_resolver`, `_resolve_doctrine_root`, `_load_template_sets`, `_load_yaml_id_catalog`, `_load_project_directives`, `_emit_deferred`, and duplicate constants (`DEFAULT_TEMPLATE_SET` and `NONE_LABEL` defined in two modules). Several are kept alive only because "seam tests pin this arity".
- **Re-export-for-convenience shims with zero consumers:** `charter.offering.shared` glossary types, kind-subpackage `ArtifactKind`, the `MissionRepository` aliases, and the `_internal_runtime` emitter/lifecycle/models modules.
- **Over-internalized upstream runtime.** `_internal_runtime` carries whole spec-kitty-runtime features (`TransitionGate`, `notify_decision_timeout` + `TimeoutEscalationResult`, `JsonlEventLog`, `ContextTypeRegistry` mutators, `diagnose_shadowing`, `serialize_decision`, `CommitContext`). Only `*_coverage.py` tests exercise them, which contradicts the contract's "not on the inventory → not internalized" rule.
- **Tests pinning dead code, including vacuous guards.** Examples: `_record_path_str`, `evaluate_guards` parity tests, the `KITTIFY_DIR` hasattr check, the `GlossaryEntityPageRenderer` patch, and the `generate_all` "not called" sentinel. These give false coverage confidence while the real call sites go unguarded.
- **"__all__ inflation" drives the allowlist.** Many allowlisted symbols are live inside their own module. The right fix is demotion from `__all__` (the precedent in progressive_disclosure.py), not a standing allowlist row.
- **Forward APIs that never got callers after their mission closed:** the delivery rail (#3063), the path_conventions slot (#2652), pack identity and manifest hash (#3518), `merge_defaults`, `activate_scope` (the `GlossaryScopeActivated` event is never emitted), and `expected_artifacts` / `step_contracts` slots. Rationales still say "WP in flight" long after status.json shows done or approved.
- **Test doubles and stubs in src:** `glossary.middleware.MockContext`, `GlossaryStore.load_from_events` (`pass  # WP08`), `kernel.clock.FrozenClock` (intentional).
- Out of scope but notable: `.kittify/overrides/missions/` holds a stale vendored copy of the old doctrine missions package (repository.py, models.py, …).

## False positives (compact)

- **ruamel/YAML config attributes** (`default_flow_style`, `preserve_quotes`, `explicit_start`, `allow_unicode`), about 40 hits across charter, glossary and kernel. They are attribute assignments on a `YAML()` instance.
- **`kernel/_safe_re.py:131-141`** `M`, `S`, `X`, `A`, `U`, `L`: regex flag aliases, re-exported as a module drop-in for `re`.
- **`runtime_bridge_retrospective.py:124` `call_count`:** a Mock-compatible attribute on a test-facing fake.
- **`synthesizer/staging.py:240` `exc_tb`:** a required `__exit__` protocol parameter.
- **All 22 ERA001 hits** (action_doctrine_bundle:313, consistency_check:1350, pack_manager:322, write_pipeline:564/579, chokepoint:44/100, store:17, significance:451/483/509/530/663-686, runtime_bridge:3583, runtime_bridge_cores:623, runtime_bridge_retrospective:449). All are prose, section banners, or `__all__` group labels, not commented-out code.
- **Test-reset hooks** (`_reset_emitted_for_testing`, `_reset_agent_profile_cache`, `_reset_migrate_nudge` ×2, `clear_registry`): intentional test seams.
- **`charter.drg::load_graph`, `charter.drg::merge_three_layers`:** contract-required facade re-exports, enforced by test_charter_facades_reexport_doctrine.py. The underlying `charter.offering.drg.merge.merge_three_layers` is live (_drg_helpers.py:36).
