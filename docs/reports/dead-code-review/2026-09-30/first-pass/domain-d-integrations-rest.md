---
doc_status: active
updated: '2026-09-30'
---

# Dead-code review, first pass — Domain D: integrations and the rest

Part of the [dead-code review of 2026-09-30](../README.md). Analysed at `origin/main` `bd1577a3`.

## Domain summary

Domain D covers the `src/specify_cli` subpackages the other reviewers did not take (auth, tracker, zeitgeist_client, saas_client, audit, doc_analysis, doctrine, dossier, events, retrospective, review, skills, tool_surface, validators, live_work, invocation, etc.) plus the grandfathered-orphan module entries. There are three headline results:

1. **`_WIDENED_SCOPE_GRANDFATHERED_470` has no stale ratchet, and 52 of its 215 entries are already stale.** The gate only asserts `any(...)` over it (test_no_dead_symbols.py:4000), so no single entry is ever forced out. I re-ran the gate's own `_compute_offenders` widened pass: 43 of the 52 stale entries are in this domain. They include every `zeitgeist_client.*` entry, `skills.command_installer::{remove,verify,prune_stale}` and `tool_surface.bundles.claude_wrapper::*`, which all have live `src/` callers today.
2. **`events/adapter.py`'s `Event` and `LamportClock` dataclasses (about 95 LOC) are dead.** They are sync-era residue, still re-exported from `specify_cli.events.__all__`.
3. **Most "WP-in-flight" rationales are wrong in one of two ways.** Some point at work that has since landed (charter_activate CLI wiring, `charter context --include template:`). Others cover symbols that are in fact used inside their own module and are only over-exported in `__all__`.

`auth.transport` is still a 525-LOC dead module. Its deletion ADR (2026-05-18-2) still holds, and the sync subsystem it cited has since been removed, so the only thing blocking removal is the owner-gate. The `pack_descriptor` / `pack_lineage` "WP in flight" work has not landed: #3518 and #3511 are both open, and #3511 is `status:blocked`.

| Class | Count |
|---|---|
| DEAD | 34 |
| TEST-ONLY | 62 |
| API/DYNAMIC | 21 |
| FALSE-POSITIVE | ~95 (incl. 43 stale widened entries, 15 ERA001 section-header comments) |
| **High-confidence DEAD** | **30** |

Estimated removable LOC for the High-confidence DEAD set: **~480 LOC** of symbols, plus **525 LOC** for `auth/transport.py` if the owner signs off (**~1,000 in total**). Removing it would also retire `tests/auth/test_auth_transport_refresh_lock.py`, `tests/integration/test_token_refresh_dedup.py` (partially) and the vacuous `tests/architectural/test_auth_transport_singleton.py` allowlist row. TEST-ONLY clusters that could go on an owner decision add about 1,600 LOC:
- doc generators `configure`/`generate`: ~440
- research citation validators: ~330
- tracker.origin ticket-start: ~170
- skills installer legacy projection chain: ~165
- the rest: smaller clusters

Evidence method: `grep -rnw <name> src tests packs scripts .github pyproject.toml .kittify` (with `__pycache__` excluded), a per-entry own-module reference count (throwaway scripts, not kept), and a replay of the gate's widened pass ([`tooling/widened_stale.py`](../tooling/widened_stale.py)).

## Findings by module

### auth
| file:line | symbol (kind) | class | evidence | confidence | action |
|---|---|---|---|---|---|
| auth/transport.py (module, 525 LOC) | `specify_cli.auth.transport` (module; Cat-7 orphan) | DEAD | Zero `src/` importers (only comments in token_manager.py:678, refresh_transaction.py:28/103/196, tracker/saas_client.py:443). ADR 2026-05-18-2 says DELETE. The "sync subsystem" in its evidence is now gone, and the saas_client.py:445 docstring promises a "sync, websocket" migration wave that is sync residue. | High | Remove the module, its two test files and the `test_auth_transport_singleton.py` allowlist row (`_baselines.yaml` `allowed_direct_httpx_files: 3`→2). **Owner-gated (Robert, HiC C-001).** Update the ADR with the deletion commit. |
| auth/device_flow/state.py:83 | `time_remaining` (method) | DEAD | Only hit is the def (grep src/tests). | High | remove |
| auth/device_flow/state.py:98 | `last_polled_at` (field) | DEAD | Written by `record_poll()`, never read anywhere in src or tests. | Medium | Remove the field (keep `poll_count`, which tests observe). |
| auth/secure_storage/file_fallback.py:127 | `_load_or_create_salt` | TEST-ONLY | The new key path is `_load_or_create_key`; the legacy salt is only *read* in `_decrypt`. One test uses it. | High | Remove with its test. |
| auth/loopback/browser_launcher.py:25 | `BrowserLauncher.is_available` | TEST-ONLY | Only tests/auth/test_browser_launcher.py:20,28 use it. | Medium | Remove with its tests. |
| auth/server_target.py:111 | `to_diagnostics_dict` | TEST-ONLY | Only tests/auth/test_server_target.py:72 uses it. | Medium | Remove, or wire into `_auth_doctor --json`. |
| auth/transport.py:149,168 | `reset_user_facing_dedup`, `_user_facing_failure_was_emitted` | TEST-ONLY | Tests-only helpers in the dead module. | High | Go with the module. |

### audit
| file:line | symbol | class | evidence | conf | action |
|---|---|---|---|---|---|
| audit/engine.py:366,380 | `_compute_repo_findings`, `_merge_repo_findings` | DEAD | No references at all. The docstring admits "exists to satisfy the WP spec API contract". `run_audit` uses `_compute_repo_findings_by_slug`. | High | remove (55 LOC) |
| audit/identity_adapter.py:100,140,177 | `prefix_groups_to_findings`, `selector_groups_to_findings`, `duplicate_ids_to_findings` | TEST-ONLY | engine.py:43 imports only `identity_state_to_findings`. The repo-level findings are rebuilt inline in `_compute_repo_findings_by_slug` (engine.py:216-218), so these duplicate that logic. Only test_identity_adapter.py uses them. | High | Remove with tests (~115 LOC). |
| audit/detectors.py:156 | `detect_corrupt_jsonl` | TEST-ONLY | The corruption check lives in `classifiers/status_events.classify_status_events_jsonl` (engine.py:164). Only test_detectors.py uses this. | High | Remove with its test (38 LOC). |
| audit/models.py:131 | `finding_codes` (property) | TEST-ONLY | 4 test refs, 0 src. | Low | Keep (cheap test convenience) or inline in tests. |

### events (sync-era residue)
| file:line | symbol | class | evidence | conf | action |
|---|---|---|---|---|---|
| events/adapter.py:30,87 | `Event`, `LamportClock` (dataclasses incl. `from_lib_*`/`to_lib_*`/`tick`/`update`) | DEAD | `grep -rnE "from specify_cli\.events(\.adapter)? import"` shows only `EventAdapter` (`__init__.py:413`) and `sanitize_event_for_log` in use. `Event`/`LamportClock` have zero consumers. The host Lamport clock "died with the sync" (tests/status/test_journal_lock_unification.py:15). | High | Remove both classes and drop them from `events/__init__.__all__` (~95 LOC). |
| events/adapter.py (EventAdapter) | `check_library_available` / `get_missing_library_error` | API | Live in `__init__.py:413`. But `spec-kitty-events>=10.4.0` is a hard dependency (pyproject.toml:80), and the error text still says "SSH access… pip install -e .". | Medium | keep-with-note: simplify or drop the dead import-guard in a follow-up. |

### doc_analysis (documentation mission)
| file:line | symbol | class | evidence | conf | action |
|---|---|---|---|---|---|
| gap_analysis.py:516 (+452, 486) | `detect_version_mismatch` → `extract_public_api_from_python`, `extract_documented_api_from_sphinx` | DEAD | The two helpers are called only from `detect_version_mismatch` (528-529), which has zero references outside the gate list, even in tests. | High | Remove the whole chain (80 LOC). |
| gap_analysis.py:885 | `run_gap_analysis_for_feature` | DEAD | Zero references (it also carries the prohibited "feature" term). | High | remove (24 LOC) |
| gap_analysis.py:273,284 | `CoverageMatrix.get_coverage_for_area/_type` | DEAD | Zero references. | High | remove (22 LOC) |
| doc_generators.py:77 | `check_tool_available` | DEAD | Zero references (the domain-file "tests=1" is the gate list only). | High | remove (19 LOC) |
| doc_generators.py:40,157,292,465 (+`generate` 55/200/365/509) | `DocGenerator.configure/generate` + three impls | TEST-ONLY | mission_setup_plan.py:922-941 only calls `gen.detect()`. `configure`/`generate` are called only in tests/agent/test_doc_generators.py. | Medium | needs-owner-decision: the CLAUDE.md "Generators" docs imply wiring. Otherwise shrink the generators to `detect()` (~300 LOC). |
| doc_state.py:138,166,347,383,418,453 | `set_iteration_mode`, `set_divio_types_selected`, `initialize_/update_/ensure_documentation_state`, `get_state_version` | TEST-ONLY | Production uses `read_documentation_state`/`set_generators_configured`/`set_audit_metadata` only (mission_setup_plan.py:860-921). | Medium | needs-owner-decision (a forward API never wired); otherwise remove with tests. |
| gap_analysis.py:389 | `prioritize_gaps(existing_docs=…)` (param) | DEAD | Already carries `# noqa: ARG001`, and the caller passes it (829). | Low | Drop the param in a campsite pass. |

### doctrine / charter_runtime
| file:line | symbol | class | evidence | conf | action |
|---|---|---|---|---|---|
| doctrine/org_charter.py:894 | `org_charter_to_json_block` | DEAD | Zero references outside the gate list (tests=0). | High | remove (18 LOC) |
| doctrine/pack_manifest.py:173 | `PackManifest.sorted_constituents` | DEAD | Zero references (callers use `sort_constituents()`). | High | remove |
| charter_runtime/lint/_drg.py:116 | `get_nodes_by_kind` | DEAD | Zero references besides the gate list. | High | remove (15 LOC) |
| doctrine/pack_lineage.py (module) + pack_descriptor.py | `resolve_pack_lineage_order`, `resolve_accompanying_doctrine_pack`, 3 errors, `PackDescriptor` | TEST-ONLY | `PackDescriptor` has one src consumer: pack_lineage.py. pack_lineage has zero src importers. #3511 (wiring) is OPEN with `status:blocked`, and #3518 is OPEN. | High | needs-owner-decision: the rationale is literally true but has been stalled for 6+ weeks. See the stale-rationales section. |
| doctrine/pack_manifest.py:250,313 | `load_pack_manifest`, `absorb_synthesis_manifest` | TEST-ONLY | own-module refs = def + `__all__`; tests only. They are named deliverables of #3511 item 4. | Medium | Keep until the #3511 decision. |
| doctrine/org_charter.py:226,238 | `OrgCharterCycleError`, `OrgCharterExtensionError` | API | Raised in-module and caught nowhere by name (fail-loud). | Medium | keep-with-note, and re-categorize (see below). |
| doctrine/org_charter.py:102,85,762 | `GovernancePolicy`, `REQUIRED_KIND_FIELDS`, `apply_org_charter_pre_fill` | API | Used in-module 8/10/5 times; only the export is unused. | Medium | Drop from `__all__`. |
| charter_runtime/preflight/ambient_warning.py:108 | `_reset_surfaced_for_testing` | API | A test hook by name and design. | High | keep |

### skills
| file:line | symbol | class | evidence | conf | action |
|---|---|---|---|---|---|
| skills/installer.py:311 | `_make_entries_for_existing` | DEAD | Zero references anywhere. | High | remove (41 LOC) |
| skills/verifier.py:179 | `_project_managed_path` | DEAD | Zero references. | High | remove |
| skills/installer.py:131-308 | `_project_skill_files` → `_project_skill_file` → `_archive_existing_path`, `_replacement_is_owned`, `create_skill_backup` | TEST-ONLY | `_project_skill_files` has no src caller. The others are called only from inside that chain (lines 157, 233, 236, 271, 276, 282). The live path is `_install_caller_skills` (line 367). tests/specify_cli/skills/test_installer.py:716-956 exercises the chain. `prepare_skill_backup` stays live (line 825). | High | Remove the chain with its tests (~165 LOC). |
| skills/manifest.py:74,80,84; manifest_store.py:106 | `remove_entries_for_agent`, `find_by_skill`, `find_by_installed_path`, `with_agent_removed` | TEST-ONLY | 0 src refs. | Medium | Remove with tests, or keep as a manifest query API. |
| runtime/agent_skills.py:92 | `_retired_skill_cleanup_needed` | DEAD | Zero references. | High | remove |

### runtime (specify_cli.runtime)
| file:line | symbol | class | evidence | conf | action |
|---|---|---|---|---|---|
| runtime/resolver.py:672,116 | `resolve_template_by_urn`, `TemplateURNError` | TEST-ONLY | Its target consumer, `charter context --include template:`, **landed differently**: charter/activation/context_renderers/template_include.py:89 uses `charter.offering.template_catalog.resolve_template_by_id`. #2761 is still open. | High | Remove the lane and its test, then close #2761 as superseded (~75 LOC). |
| runtime/agent_commands.py:776 | `_sync_agent_commands` | TEST-ONLY | "Retain existing scoped owner entry point". The only callers are 22 refs in tests/specify_cli/runtime/test_agent_commands.py. | Medium | Retarget the tests to `ensure_global_agent_commands(agent_keys=[…])`, then remove. |
| runtime/bootstrap.py:121 | `_cleanup_orphaned_update_dirs` | TEST-ONLY | Only tests/runtime/test_bootstrap_unit.py:491-530 calls it. It is now a warn-only no-op. | Medium | Remove with its tests. |
| runtime/resolver.py:230 | `_reset_migrate_nudge` | API | A test reset hook (4 test files). | High | keep |

### review / retrospective
| file:line | symbol | class | evidence | conf | action |
|---|---|---|---|---|---|
| review/baseline.py:656 | `load_baseline` | DEAD | tests=0: the test hits are other `load_baseline` functions. All importers take `BaselineFailure`/`capture_baseline`. | High | remove |
| review/cycle.py:371 | `is_resolved` (property) | DEAD | The only `is_resolved` hits are `core/vcs` dataclass fields, and there are no test refs. | High | remove |
| review/gate_bindings.py:115 | `is_no_coverage` | DEAD | Zero references. | High | remove |
| review/gate_bindings.py:195 | `load_gate_bindings` | TEST-ONLY | Only test_gate_bindings.py uses it. | Medium | Remove with its test. |
| review/arbiter.py:257 | `prompt_arbiter_checklist` (76 LOC interactive) | TEST-ONLY | Only test_arbiter.py uses it. | Medium | needs-owner-decision (an interactive arbiter that was never wired). |
| review/artifacts.py:174 | `has_complete_override` | TEST-ONLY | 2 test files. | Low | Remove with its tests. |
| retrospective/gate.py:45 | `ModeResolutionError` (duplicate class) | DEAD | A *distinct* class from `retrospective.mode.ModeResolutionError`. It is never raised; gate.py:618 documents the `mode` one. Its docstring "Re-exported from gate" is false, and `except gate.ModeResolutionError` would never match. | High | remove (misleading) |
| retrospective/lifecycle_events.py:303 | `RetroLifecycleEvent` (type alias) | DEAD | 0 refs in src and tests. | High | remove |
| retrospective/generator.py:306,323 | `_make_evidence_counter`, `_next_proposal_id` | DEAD | Zero references (`_next_evidence_id` is live). | High | remove |
| retrospective/generator.py:618 | `_classify_risk` | TEST-ONLY | 11 test refs, 0 src. | Medium | Remove with its tests. |
| retrospective/summary.py:195 | `_read_slug_from_meta` | TEST-ONLY | 9 test refs. | Medium | Remove with its tests. |
| retrospective/events.py:114 | `ProposalGeneratedPayload` | TEST-ONLY | test_events_shapes.py only; no emitter. | Medium | needs-owner-decision |
| retrospective/cli.py:18,31 | `import sys`, `MalformedSummaryEntry` (F401) | DEAD | No `sys.` use in the file. No test imports either name via `retrospective.cli`. | High | remove |
| retrospective/summary.py:43 | `logger` | DEAD | own-module refs=1 (def only). | High | remove |

### tracker / saas_client / zeitgeist_client
| file:line | symbol | class | evidence | conf | action |
|---|---|---|---|---|---|
| tracker/factory.py:25 | `_require` | DEAD | `grep -n _require tracker/factory.py` shows the def only. The 15 "other" hits are unrelated `_require` functions. | High | remove |
| tracker/origin.py:30; saas_client/client.py:37 | `logger` | DEAD | own refs=1 each. | High | remove |
| saas_client/endpoints.py:57 | `AdmissionMetadata` (TypedDict) | DEAD | Zero references (tests=0). | High | remove |
| zeitgeist_client/outbox_approval.py:429 | `get_receipt` | DEAD | Zero references; the gate replay confirms it is still an offender. | High | remove (15 LOC) |
| tracker/origin.py:117,324 | `search_origin_candidates`, `start_mission_from_ticket` | TEST-ONLY | Only `bind_mission_origin` is imported (origin_consumer.py:55). The pair is used only in test_origin*.py. | Medium | needs-owner-decision: an unwired ticket-first mission start (~170 LOC). |
| tracker/gateway.py:487,496 | `record_conflicts`, `authority_report` | TEST-ONLY | `local_service.py:39` imports only `TrackerGatewayToken`/`build_gateway_beads_connector`. test_gateway.py:460+ exercises these. | Medium | needs-owner-decision |
| tracker/service.py:112 | `supported_providers` | TEST-ONLY | 1 test. | Low | Remove with its test. |
| zeitgeist_client/transport.py:483,496,513 | `focus_heartbeat`, `focus_pause`, `focus_end` | TEST-ONLY | Only `focus_start` is wired (status/zeitgeist_bridge.py:566). | Medium | needs-owner-decision (relay-protocol completeness vs TTL expiry). |
| zeitgeist_client/filtered_stream.py:579; repo_identity.py:130 | `current_focus`, `Deadline.expired` | TEST-ONLY | test refs only. | Low | keep or remove |
| tracker/local_service.py:245,286 | `engine._checkpoint = …` | API | Writes a private attribute of the `spec_kitty_tracker` SyncEngine. The library now has `restore_checkpoint()` (sync.py:129-134). | High | Campsite: switch to `engine.restore_checkpoint(checkpoint)`. |

### paths (sync-era residue)
| file:line | symbol | class | evidence | conf | action |
|---|---|---|---|---|---|
| paths/windows_paths.py:48,52 | `RuntimeRoot.sync_dir`, `.daemon_dir` | TEST-ONLY | 0 src callers. They are pinned only by tests/paths/test_windows_paths.py:30-31, test_runtime_root_spec_kitty_home.py:165-199 and tests/kernel/test_paths_unified_windows_root.py:114-115. Sync transport and daemon were deleted Aug 2026. | High | Remove with those asserts, plus the `daemon_dir` cleanup in tests/conftest.py:686-688. |

### validators / text / misc
| file:line | symbol | class | evidence | conf | action |
|---|---|---|---|---|---|
| validators/research.py (≈330 of 420 LOC) | `validate_citations`, `validate_source_register`, `detect_citation_format`, `is_*_format`, `*_PATTERN`, `Citation*`, `ResearchValidationError`, `VALID_*` | TEST-ONLY | The only src importer is migration m_0_13_0 (`EVIDENCE_REQUIRED_COLUMNS`, `SOURCE_REGISTER_REQUIRED_COLUMNS`). No research-mission prompt references the validators (grep packs/…/research). | Medium | needs-owner-decision: wire into the research accept gate or delete (all under Cat-B). |
| validators/research.py:95; csv_schema.py:33 | `format_report`, `format_mismatch_report` | TEST-ONLY | 1 test each. | Low | Go with the above. |
| text_sanitization.py:84 | `sanitize_markdown_text(preserve_utf8=…)` | DEAD (param) | Carries `# noqa: ARG001` while the docstring claims behaviour. No caller passes it. | High | Drop the param and fix the docstring. |
| identity/project.py:150 | `generate_build_id` | DEAD | Zero references besides the gate and a docstring mention (line 166). It was superseded by `derive_build_id`. | High | remove |
| invocation/executor.py:133 | `ActionRouterPlugin` (Protocol) | DEAD | A duplicate of router.py:180's `ActionRouterPlugin` class. Nothing references the executor copy (widened-gate offender). | High | remove |
| invocation/router.py:220 | `router_plugin` param + router.py:180 class | API | A forward stub "reserved for future hybrid extension (WP02)". tests/specify_cli/invocation/test_router.py:399 pins the no-op. | Medium | needs-owner-decision (a forward API that was never wired). |
| invocation/registry.py:194; task_class_map.py:76 | `has_profiles`, `known_verbs` | TEST-ONLY | test refs only. | Low | Remove with tests, or keep. |
| session_presence/writers/markdown_rules.py:371 | `_replace_section` | DEAD | Zero call sites; the only other hit is a docstring in m_3_2_0rc39. | High | remove (13 LOC) |
| bulk_edit/occurrence_map.py:27; state/doctor.py:25 | `logger` | DEAD | own refs=1. | High | remove |
| tool_surface/findings.py:30,40,65 | `MANAGED_FILE_MODIFIED`, `NATIVE_CONFIG_DRIFT`, `DOCS_REF_STALE` | TEST-ONLY | Finding codes that no detector emits (own refs=1, test_findings.py only). | Medium | Remove, or emit them (the vocabulary drifted). |
| tool_surface/profiles/projection.py:43-44 | `LAYER_ORG`, `LAYER_PROJECT` | DEAD | own refs=1, 0 tests. | Medium | remove |
| tool_surface/enums.py:64,72 | `CommandSurfaceCapability`, `MutabilityPolicy` | TEST-ONLY | test_enums.py only. | Medium | Remove with tests. |
| tool_surface/docs.py:257; service.py:117; providers/managed_skills.py:755 | `format_findings`, `lint_docs_directory`, `doctrine_skill_entries` ("helper for tests") | TEST-ONLY | test refs only. | Medium | Move to test helpers, or remove. |
| agent_tasks_ports.py:468 | `default_ports` | TEST-ONLY | 5 commands build their own `TasksPorts` bound to the patchable `tasks` module (e.g. tasks_mark_status.py:137, tasks_status_cmd.py:112). | Medium | Remove with tests (test_tasks_ports.py, test_verdict_save_topologies.py). |
| agent_tasks_ports.py:136,255 | `wp_tasks_dir` (Protocol + Real) | TEST-ONLY | Tests only (3 files). | Low | keep or remove |
| compat/history.py:228,255,294 | `is_idempotent`, `consecutive_failure_count`, `last_success_timestamp` | TEST-ONLY | The store is **write-only** in production: upgrade_ux.py:281 appends and nothing reads. | Medium | needs-owner-decision: wire into the upgrade nag, or drop the query API. |
| compat/provider.py:175,178 | `package_name_default` param / `_package_name_default` | DEAD | Documented as "Ignored"; no caller passes it. | High | remove |
| context/mission_resolver.py:466 | `FakeMissionResolver` | TEST-ONLY | A test double shipped in src. mission_runtime has only docstring refs. | Medium | Move to tests/ (fixtures). |
| decisions/ownership.py:240; dossier/models.py:388; reconciler.py:125; manifest.py:216,242; requirement_mapping/grammar.py:146; widen/state.py:168; widen/interview_helpers.py:46; frontmatter.py:383; live_work adapters `capability_notes` | small predicates / validators | TEST-ONLY | 0 src callers each (verified by grep). | Low | Batch-remove in a campsite pass, or keep as cheap API. |
| proof/events.py:25,271 | `ProofEventType`, `PROOF_EVENT_REQUIRED_FIELDS` | TEST-ONLY / DEAD | `ProofEventType` has 0 refs anywhere. The fields map is tests-only. | Medium | Remove the alias; keep the map only if a validator will use it. |
| dossier/hasher.py:215,243 | `WP_RUNTIME/DESCRIPTIVE_PROJECTION_FIELDS` | TEST-ONLY | A partition contract enforced only by test_canonical_hash.py. | Medium | keep-with-note (a test-contract constant). |
| agent_utils/directories.py:11; manifest.py:10; verify_enhanced.py:6 | `List`,`Tuple`; `Dict`,`List`,`Optional`; `KITTY_SPECS_DIR` (F401) | DEAD | No use in-file and no `mod.X` references in tests. | High | Remove the imports (hidden by per-file-ignores). |

### API / DYNAMIC (keep-with-note)
- `ast_analysis/imports.py:42,70` (`module_of_import_from`, `extract_static_all`) are the shared AST primitives used by scripts/ci/coverage_guard_lib.py:42 and the architectural gates.
- `contracts/anchoring.py:270,332` are gate primitives (53 test refs).
- `drg_writers/registry.py` writers are a test-oracle registry hosted in src by design (docstring lines 1-30).
- `dossier/api.py::DossierHandlerAdapter` is the base class of the live `DossierAPIHandler` (api.py:201).
- `auth/refresh_transaction.py::RefreshResult` is a return type that callers consume.
- `review/scope_source` entries are factory-constructed.
- The `retrospective/deprecation.py:151` reset hook is a test hook.
- `tracker/store.py` `get_issue`/`upsert_issue`/`delete_issue` implement the `spec_kitty_tracker.protocols.LocalIssueStore` Protocol (protocols.py:66-77, called by sync.py:177-318).
- `live_work` constants (Cat C/D) are used in-module, for example `CODEX_NOTIFY_LINE` with 8 own refs. Only their `__all__` export is unused.

## Stale allowlist rationales

| Category / entry | Evidence | Recommended action |
|---|---|---|
| **`_WIDENED_SCOPE_GRANDFATHERED_470` as a whole** | There is no per-entry stale ratchet; only `assert any(...)` at test_no_dead_symbols.py:4000. Replaying `_compute_offenders(widened_only_decls, …, frozenset())` shows **52/215 entries are not offenders**. In this domain:<br>• all 36 `zeitgeist_client.*` entries (live via module-attr calls, e.g. resolution.py:483 `credentials.load`, transport.py:400 `budget.open_bounded`, mcp_stdio.py:227 `subscription.status`)<br>• `skills.command_installer::{remove,verify,prune_stale}`<br>• `tool_surface.bundles.claude_wrapper::{wrapper_bash_content,wrapper_cmd_content}`<br>• `session_presence.upgrade_check::refresh_cache_once` (used in-module)<br>• `runtime.resolver::required_artifacts_for` (now in `__all__` with the runtime_bridge_io caller)<br>Outside this domain: `mission_metadata::load_meta_strict`, `ownership.frontmatter_source::InMemoryFrontmatterSource`, `upgrade.autocommit::commit_touched_checkout`, `runtime.next.committed_authority::mission_terminal_verdict`, 3 loggers, `migration.mission_state::audit_invocation_disagreement` (moved into `__all__`), and `charter.offering.hatch_build::DoctrinePacksSiblingBuildHook` (no longer declared). | Prune the 52 entries, and add a per-entry stale check (`assert set(_WIDENED…) <= set(pre_rescue_widened_offenders) ∪ own-module-rescued`). |
| `_CATEGORY_7_GRANDFATHERED_ORPHANS` → `specify_cli.auth.transport` | The ADR 2026-05-18-2 DELETE verdict still holds (zero src importers). The "sync subsystem" alternatives it cites were deleted in Aug 2026. The tracker/saas_client.py:445 comment about a "next migration wave (sync, websocket…)" is sync residue. | Execute the ADR (owner Robert). Until then, update the comment to drop "sync". |
| `_CATEGORY_5_WP_IN_FLIGHT_ADAPTERS` → `doctrine.pack_descriptor`, `doctrine.pack_lineage` | The WP has **not** landed: #3518 is OPEN (status:ready), #3511 is OPEN (status:blocked), and neither has a closing PR. `PackDescriptor`'s only src consumer is pack_lineage.py, which has zero importers. | The rationale is still literally true but stalled. Ask the owner to either timebox #3511 or delete both modules (~310 LOC) plus `load_pack_manifest`/`absorb_synthesis_manifest`, and re-add them with the cutover. |
| `_CATEGORY_A_SLICE_F_DEFERRED` (the `specify_cli.doctrine.*` rows) | The comment says "src/charter + src/kernel … library never wired", but these are specify_cli symbols. 8 of 17 are **live in-module**:<br>• `SCHEMA_VERSION`, `HASH_EXCLUDED_FIELDS`, `CharterProfile`, `sort_constituents`, `compute_pack_manifest_hash`, `counts_by_kind` (via `resolve_counts`, called from snapshot.py:494)<br>• `GENERATED_BY`, `MANIFEST_FILENAME`, `build_builtin_manifest` (via `generate_builtin_manifest`, called from cli/commands/doctrine.py:293-340), `enumerate_constituents`<br>They are only over-exported. | Remove them from `__all__` so the entries drain. Keep only `load_pack_manifest`, `absorb_synthesis_manifest` and the pack_lineage names under the #3511 rationale. |
| `_CATEGORY_C_WP_IN_FLIGHT_CHARTER_ACTIVATION` → `charter_activate::{AffectedMission, StepRemovalWarning}` | The promised "WP06/WP08 CLI wiring" has landed: cli/commands/charter/activate.py:168 imports `specify_cli.charter_activate`. These are value-consumed return types (7 own refs each). | Move them to a "transitively consumed return type" category, like `_CATEGORY_C_WP_IN_FLIGHT_TOPOLOGY_AUTHORITY`, or drop them from `__all__`. |
| same category → `org_charter::{OrgCharterCycleError, OrgCharterExtensionError}` | Raised in-module and caught nowhere by name; this is the fail-loud shape. It is not "in flight". | Re-categorize under an uncaught-propagation surface (like #4600), or drop them from `__all__`. |
| `_CATEGORY_C_URN_RESOLUTION_LANE` (#2761) | The target consumer `charter context --include template:` shipped via `charter.offering.template_catalog.resolve_template_by_id` (template_include.py:89). It cannot import `specify_cli` for layer reasons anyway. #2761 is still open. | Delete `resolve_template_by_urn` and `TemplateURNError` and close #2761 as superseded. |
| `_CATEGORY_C_UPSTREAM_SESSION_PRESENCE` (`CACHE_PATH`, `TTL_SECONDS`) | True as written (used by `UpgradeChecker` in-module), but "wire or prune when callers land" will never trigger. | Drop them from `__all__`. |
| `_CATEGORY_B_GRANDFATHERED_LEGACY` → `validators.research.*` (17 rows), `tracker.origin::{search_origin_candidates,start_mission_from_ticket}`, `doc_state` | These are forward APIs that never got a caller (see findings). The "may only shrink" policy hides them indefinitely. | Owner wire-or-delete decisions, which would drain about 22 rows. |
| `_CATEGORY_B_GRANDFATHERED_LEGACY` → `frontmatter::get_field`, `intake.brief_writer::atomic_write_*`, `task_metadata_validation::{detect_lane_mismatch,validate_task_metadata}`, `text_sanitization::*`, `plan_validation::detect_unfilled_plan`, `pack_assembler::{AssemblyResult,ConflictItem}`, `invocation.projection_policy::*` | Used inside their own modules (3-22 own refs); only the `__all__` export is dead. | Drop them from `__all__`; the entries drain with no behaviour change. |

## Notable patterns

1. **Over-exporting in `__all__` inflates the allowlists.** About 35 allowlisted names in this domain are live inside their own module and are listed only because `__all__` names them. Trimming `__all__` drains the entries at no cost.
2. **Grandfather sets without per-entry staleness rot.** The widened #470 set accumulated 52 entries that have callers (43 in zeitgeist_client alone, which is consumed through `from . import credentials` + `credentials.load(...)`).
3. **Sync-retirement residue:**
   - `events.Event` / `LamportClock`
   - `RuntimeRoot.sync_dir` / `daemon_dir` and the conftest daemon cleanup
   - `auth.transport` (its ADR evidence cites the deleted sync package)
   - `generate_build_id` (upstream build-id contract)
   - the saas_client.py "sync, websocket migration wave" docstring
   - the `events.adapter` "SSH access / pip install -e ." error text

   Tracker `record_conflicts` / `SyncEngine.sync()` is the tracker-provider sync, not the transport, so it is not residue.
4. **Forward APIs that were never wired, or were later superseded by a parallel implementation:**
   - doc generator `configure` / `generate`
   - `doc_state` setters
   - research citation validators
   - tracker ticket-first mission start
   - gateway authority report
   - zeitgeist `focus_heartbeat` / `pause` / `end`
   - `ActionRouterPlugin` (duplicated in two modules)
   - the URN template lane, superseded by the charter-layer resolver
   - `compat.history` read API (the store is write-only)
5. **Refactors that leave the old path test-pinned.** Examples: the skills installer's `_project_skill_files` chain after `_install_caller_skills`; `_sync_agent_commands`; audit `identity_adapter` group converters and `detect_corrupt_jsonl` after the engine/classifier rewrite; `_merge_repo_findings` kept "for WP spec API contract".
6. **Test doubles and test-helper code shipped in `src/`:** `FakeMissionResolver`, `doctrine_skill_entries` ("helper for tests"), `drg_writers.registry`, and the `ast_analysis` / `anchoring` primitives. The last two are legitimate shared infrastructure; the first two should move to tests.
7. **No vacuous monkeypatch surfaces found** in the spot-checks of this domain. The `tracker.saas_client.httpx.Client` patches target a live call site.

## False positives (compact)

- **ruamel/yaml attribute writes:** `preserve_quotes`, `default_flow_style`, `allow_duplicate_keys` (analysis_report, doctrine_synthesizer/provenance, frontmatter, identity/project, provisioning/default_charter, review/artifacts, tracker/config ×3, gap_analysis:128).
- **Protocol / structural conformance:** tracker/store `get_issue`/`upsert_issue`/`delete_issue` (LocalIssueStore); drg_writers `node_to_mapping`/`edge_to_mapping`/`document_to_mapping` (registry members); live_work `capability_notes` Protocol member (test-only, noted above).
- **Library private-attribute write:** tracker/local_service `engine._checkpoint` (see the campsite note).
- **Dunder signature:** tracker/config.py:138 `__deepcopy__(memo)`.
- **Pydantic field assignment:** dossier/indexer `dossier_updated_at`.
- **Dataclass counter read by tests:** device_flow `poll_count`.
- **Name collisions that are live:** `tracker/config.egress_fault` (live), `saas_service.apply_binding_upgrade` (test-only by its own admission at service.py:99; defence-in-depth, keep), `docs/index_model.has_drift` (tests + CI script), `manifest.py` `Dict` (vulture duplicate of the F401).
- **ERA001, section-header comments or prose (all 15 non-intake hits):** calibration/walker:99, charter_runtime/freshness/cache:90, compat/_detect/runtime:104, compat/history:114, compat/messages:78/121, gap_analysis:70/74/78/82, invocation/executor:1060, retrospective/__init__:73/101 (`__all__` group comments), retrospective/gate:106 (YAML example), retrospective/policy:109, retrospective/schema:376, runtime/asset_preparation:1296, tracker/service:118, version_utils:23.
- **ERA001 intake_sources.py (20 hits, lines 69-159):** these are intentional TODO research notes, each ending in a commented-out candidate tuple.

  **Verdict:** keep the prose (sourced confidence and URLs are useful), but drop the ~11 commented-out tuple lines. They carry no information beyond the prose's "When promoted: add (...)" line, and they are what trips ERA001. Better still, move the whole block to a `docs/contracts/` table or to a structured `_CANDIDATE_SOURCES: tuple[CandidateSource, ...]` with a `confidence` field that the scanner filters on. That removes the need for per-file-ignores without any `noqa`.

  Also flag for staleness: several of the entries are dated around 2026-02/04 (e.g. Kilocode issue #6370, "as of 2026-04-20").
