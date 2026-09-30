---
doc_status: active
updated: '2026-09-30'
---

# Test-only deep dive — Domain D: integrations and the rest

Part of the [dead-code review of 2026-09-30](../README.md). Analysed at `origin/main` `bd1577a3`.

Checkout: `bd1577a3` (history unshallowed to 13,975 commits during this pass; all `git log -S` evidence below is from the full history). LOC are AST spans (decorators included). "Test LOC" is the removable test body only: whole test functions that touch nothing but the dead symbols. Mixed tests are counted separately.

| # | slice | symbols | src LOC | test LOC | verdict | confidence | behaviour gap? |
|---|---|---|---|---|---|---|---|
| 1 | Doc generators `configure`/`generate` | `DocGenerator.configure/generate` + 3 impls, `GeneratorResult`, `GeneratorError`, (`check_tool_available` DEAD) | ~419 | ~130 (8 tests) | DELETE, keep `detect()` | High | Minor: `generators_configured[].config_path` is always `""` |
| 2 | `doc_state` setter API | `set_iteration_mode`, `set_divio_types_selected`, `initialize_/update_/ensure_documentation_state`, `get_state_version`, `write_documentation_state` | ~193 | ~425 (38 tests) + 3 mixed | OWNER-DECISION (wire `set_iteration_mode`) | High | **YES: `iteration_mode` is never set, so the setup-plan gap analysis cannot run** |
| 3 | Research citation validators | `validate_citations`, `validate_source_register`, `detect_citation_format`, `is_*_format`, `Citation*`, `ResearchValidationError`, patterns, `VALID_*`, `format_report`, `CSVSchemaValidation.format_mismatch_report` | ~365 | ~190 (15 tests + 3 mixed) | OWNER-DECISION (re-wire as research guard, or delete) | High | **YES: research review used to block on citation errors; that gate was dropped on 2026-04-04** |
| 4 | Tracker ticket-first origin + gateway report | `search_origin_candidates`, `start_mission_from_ticket` (+4 private helpers, 2 result models); `record_conflicts`, `authority_report`, `GatewayAuthorityReport`; `supported_providers` | ~240 + ~46 + 4 | ~300 origin + 67 gateway + 15 | DELETE origin pair; OWNER-DECISION gateway (one-line wire available) | High / Medium | No (the live `mission create --from-ticket` covers the origin use case) |
| 5 | Skills installer legacy projection chain + manifest query API | `_project_skill_files`, `_project_skill_file`, `_archive_existing_path`, `_replacement_is_owned`, `create_skill_backup`; `remove_entries_for_agent`, `with_agent_removed`; `find_by_skill`, `find_by_installed_path` | 165 + 13 | 169 (7 tests) + 4 mixed + 41 | MOVE-TESTS-THEN-DELETE chain; DELETE 2 manifest mutators; KEEP 2 finders | High | No |
| 6 | `specify_cli.calibration` package | `walk_mission`, `CalibrationFinding`, `assert_inequality_holds`, `InequalityResult`, `REQUIRED_SCOPE_MAP` | 637 | 435 (33 tests) | MOVE to tests/ (it is a live DRG gate) | High | No, but deleting it outright would remove the FR-032 gate |
| 7 | `specify_cli.proof` package | `ProofEventType`, `PROOF_EVENT_*`, 8 payload models | 424 | 298 (11 tests) | DELETE | High | No |
| 8 | `auth.websocket` package + auth test-only helpers | `WebSocketTokenProvisioner`, `WebSocketProvisioningError`; `_load_or_create_salt`, `BrowserLauncher.is_available`, `ResolvedServerTarget.to_diagnostics_dict` | 212 + 34 | ~545 + 22 | DELETE (the salt test is MOVE) | High | No |
| 9 | Audit repo-level converters twin | `prefix_/selector_/duplicate_ids_groups_to_findings`, `detect_corrupt_jsonl`, `finding_codes` | 153 + 4 | 232 (15 tests) | WIRE (engine calls the adapters), then DELETE `detect_corrupt_jsonl` | High | Coverage gap: the live repo-level findings have **no** test |
| 10 | Runtime leftovers | `resolve_template_by_urn`, `TemplateURNError`; `_sync_agent_commands`; `_cleanup_orphaned_update_dirs` | 83 + 6 + 7 | 176 + 173 + 31 | DELETE URN lane (close #2761); KEEP `_sync_agent_commands` as test seam or retarget; DELETE cleanup | High / Medium | No |
| 11 | Review / retrospective residue | `load_gate_bindings`, `prompt_arbiter_checklist`, `has_complete_override`; `_classify_risk`, `ProposalGeneratedPayload`, `_read_slug_from_meta` | ~124 | ~200 (23 tests) | DELETE review trio + `_read_slug_from_meta`; OWNER-DECISION proposal pair | High | **YES: `generate_proposals=True` (the default) produces zero proposals; the generator never appends one** |
| 12 | Zeitgeist focus lifecycle | `focus_heartbeat`, `focus_pause`, `focus_end`, `FilteredStream.current_focus`, `Deadline.expired` | 53 + ~15 | 16 + 10 mixed tests | OWNER-DECISION (wire `focus_end`, or drop 3 verbs) | Medium | Possible UX gap: focus is never ended, so it lingers until relay TTL |
| 13 | `tool_surface` vocabulary and docs linter | `MANAGED_FILE_MODIFIED`, `NATIVE_CONFIG_DRIFT`, `DOCS_REF_STALE`, `CommandSurfaceCapability`, `MutabilityPolicy`, `doctrine_skill_entries`; `format_findings`, `lint_docs_directory` | 3 + 13 + 8 | ~25 | DELETE vocab; MOVE `doctrine_skill_entries`; **KEEP docs linter (live CI gate)** | High | No |
| 14 | `doctrine.pack_lineage` / `pack_descriptor` / manifest loaders | `resolve_pack_lineage_order`, `resolve_accompanying_doctrine_pack`, 3 errors, `PackDescriptor`, `load_pack_manifest`, `absorb_synthesis_manifest` | 309 + 44 | 372 whole files + mixed | OWNER-DECISION (timebox #3511) | Medium | No |
| 15 | Misc small helpers | `RuntimeRoot.sync_dir/daemon_dir`, `has_profiles`, `known_verbs`, `default_ports`, `wp_tasks_dir`, `UpgradeAttemptStore` query trio, `FakeMissionResolver`, 9 predicates, `WP_*_PROJECTION_FIELDS`, `is_functional`, `capability_notes` | ~250 | ~200 | Batch: DELETE sync-era paths and ports helpers; MOVE `FakeMissionResolver`; KEEP value-type predicates and contract constants | Medium | compat history store is write-only (no gap; its query API is unused) |

**Headline.** The TEST-ONLY set in this domain splits three ways, not two:
- **Genuinely dead twins (DELETE):** proof, auth.websocket, the skills chain, the URN lane, the origin pair and the doc-generator `configure`/`generate`, about 1,900 src LOC.
- **Test-driven gates that live in `src/` by design (KEEP or MOVE to tests/):** the calibration walker (FR-032) and the tool-surface docs linter (FR-017). The first pass called these dead. They are not: deleting them silently removes a CI gate.
- **Forward APIs whose absence is a behaviour gap:** four bug candidates.
  1. The documentation mission's `iteration_mode` is never written, so setup-plan's gap analysis is unreachable.
  2. The research review lost its citation gate in the 2026-04-04 doctrine cutover.
  3. The retrospective `generate_proposals` policy produces nothing.
  4. The audit engine's repo-level findings (DUPLICATE_PREFIX, AMBIGUOUS_SELECTOR, DUPLICATE_MISSION_ID) have no coverage. Their tested twins are the dead adapters.

Deleting files in slices 6/7/8 also requires removing their entries from the `pyproject.toml` ruff-format `exclude` list (lines 467, 681, 1029-1030, 1715). That list is a ratchet requiring "every entry must exist on disk" (#559).

---

## Slice 1: Doc generators `configure`/`generate`
- **What.** `src/specify_cli/doc_analysis/doc_generators.py` (571 LOC). It has a `DocGenerator` Protocol and JSDoc/Sphinx/rustdoc implementations with `detect()`, `configure()` (writes jsdoc.json / conf.py / rustdoc instructions) and `generate()` (subprocess `npx jsdoc` / `sphinx-build` / `cargo doc`, returning `GeneratorResult`).
- **History.** Introduced in `cf8bbdd73` (2026-01-13, "Merge WP01-WP06: Complete documentation mission", mission `012-documentation-mission`, WP05 generator-protocol). `git log -S'gen.configure(' / '.generate(source_dir' -- src/` is empty, so it was **never wired**. Only `detect()` was ever called.
- **Replaced by.** The live path is `mission_setup_plan.py:950` `_detect_and_configure_generators`. It calls only `gen.detect()` and persists `{"name","language","config_path": ""}` through `set_generators_configured`. Actual configuration and generation are done by the agent: `packs/built-in/missions/mission-steps/documentation/generate/prompt.md:42` ("Invoke the configured generator (for example: `sphinx-build …`, `npx jsdoc -c jsdoc.json`, `cargo doc --no-deps`)") using `packs/built-in/missions/documentation/templates/generators/{jsdoc.json,sphinx-conf.py}.template`. The composition rewrite (`documentation-mission-composition-rewrite-01KQ5M1Y` FR-015) says step contracts "MUST NOT become model runners or text generators".
- **Tests.** `tests/agent/test_doc_generators.py` has 19 tests:
  - 11 `detect` tests: live, keep.
  - 8 configure/generate/repr tests (lines 115-262, ~130 LOC): (b), DELETE.
  - The live orchestrator `_detect_and_configure_generators` has **no direct test**. `test_mission_setup_plan_phases.py:838` monkeypatches it to `[]`. Add one while touching this.
- **Open intent.** Only the 012 spec (FR-018 "integrate with JSDoc…") and `docs/architecture/documentation-mission.md:630` ("`conf.py not found - run configure() first`") and `:900` still refer to it. That doc is stale.
- **Risk.** None at runtime. Update `documentation-mission.md` and the CLAUDE.md "Generators" section, which implies CLI-driven generation.
- **Verdict.** DELETE `configure`/`generate`/`GeneratorResult`/`GeneratorError`/`check_tool_available` (419 src LOC) and the 8 tests. Keep the `detect()` classes. Confidence High.
- **Gap.** Minor: `config_path` in `meta.json` is always `""`. Either drop the field or have the design step record it.

## Slice 2: `doc_state` setter API (documentation mission)
- **What.** The `meta.json → documentation_state` API in `doc_analysis/doc_state.py`. Production uses only `read_documentation_state`, `canonical_iteration_mode`, `set_generators_configured` and `set_audit_metadata` (mission_setup_plan.py:860-921). `mission_creation.py:1401-1410` seeds the block once with `iteration_mode: "initial"`.
- **History.** `a3d8c1224` (2026-01-13, "T041-T046: Implement complete documentation state management", mission 012). `git log -S'set_iteration_mode(meta' -- src/` shows only a reformat in `7428880c4` (#445) and a move in `556c34e86`. **Never wired.**
- **Replaced by.** Nothing. The `discover` step asks the agent to *declare* the iteration mode in `spec.md` (`discover/prompt.md:59,80`; spec template line 12 `**Iteration Mode**:`), but nothing copies it into `meta.json`.
- **Tests.**
  - The three test files hold 58 tests: `tests/missions/test_doc_state.py` (12 dead, 2 mixed, 6 live), `test_doc_state_unit.py` (14 dead, 4 live) and `test_doc_state_formatting.py` (12 dead, 1 mixed, 5 live). About 425 LOC are (b).
  - `tests/specify_cli/test_meta_fail_closed_full_census_contract.py:172,267` uses `set_iteration_mode` as the doc_analysis **write** exemplar of the fail-closed meta contract. That is (a): retarget it to `set_generators_configured`.
- **Open intent.** 012 spec FR-003 ("persist documentation mission state between iterations to support gap analysis"). No live issue found.
- **Risk / BEHAVIOUR GAP.** `_run_documentation_gap_analysis` (mission_setup_plan.py:850-872) runs only when `iteration_mode ∈ {gap_filling, mission_specific}`. No CLI, prompt or code path ever writes anything but `"initial"` (grep `documentation_state|iteration_mode` in src/packs). So **gap-analysis generation during setup-plan is unreachable** unless someone hand-edits `meta.json`. This is a bug candidate, not cleanup.
- **Verdict.** OWNER-DECISION. Question: "Should setup-plan honour the discover step's declared iteration mode?"
  - **Recommend WIRE:** parse `**Iteration Mode**:` from spec.md in setup-plan, or add `spec-kitty agent mission set-doc-state --iteration-mode` called by `discover/prompt.md`, via `set_iteration_mode`.
  - Then DELETE `initialize_/update_/ensure_documentation_state`, `get_state_version` and `write_documentation_state` (~165 LOC).
  - If not wired, delete the gap-analysis branch too. Confidence High.

## Slice 3: Research citation validators
- **What.** `validators/research.py` (420 LOC) is BibTeX/APA/simple citation-format detection plus CSV validation of `research/evidence-log.csv` and `source-register.csv`: required columns, unique `source_id`, enum values, and format warnings. The only live src importer is migration `m_0_13_0_research_csv_schema_check.py:16`, which uses `EVIDENCE_REQUIRED_COLUMNS`/`SOURCE_REGISTER_REQUIRED_COLUMNS` and `csv_schema.validate_csv_schema`.
- **History.** `553c837d3` (2025-11-16, "Implement WP05: Research citation validators"). The runtime consumer was prompt-embedded Python in `src/doctrine/missions/research/command-templates/review.md` and `merge.md` ("Citation Validation (Research Mission Specific) … Research review cannot proceed if validation reports blocking errors"). It was removed in `4eee6aeee` and `37484eeb8` (2026-04-04, "Fix PR 348 CI readiness and doctrine cutover").
- **Replaced by.** Only partly. `runtime_bridge_cores.py:550` `_evaluate_gathering_guard` checks that `source-register.csv` is present and `source_documented_count >= 3`. The `research-citation-discipline` styleguide (`gathering/prompt.md:46-54`) is advisory prose. No live code checks citation completeness, duplicate `source_id` or confidence values.
- **Tests.**
  - `tests/agent/test_validators_unit.py`: 11/28 tests (58 LOC) are (b). The rest cover `validators.paths` (live).
  - `tests/research/test_research_workflow_integration.py`: 4/8 (100 LOC) are (b).
  - `tests/agent/test_csv_schema.py`: 3 `format_mismatch_report` tests are (b); 10 others are live.
  - `tests/adversarial/test_csv_attacks.py`: 16 tests, live via `validate_csv_schema`, keep.
- **Open intent.** `packs/built-in/missions/research/mission-runtime.yaml:53` ("verify citation completeness"). There is no issue number.
- **Risk / BEHAVIOUR GAP.** The research mission lost an enforced quality gate in an incidental cutover commit. Vocabulary has also drifted: `VALID_SOURCE_STATUS = reviewed/pending/archived`, but `gathering/prompt.md:42` says `reviewed / pending / excluded`. Wiring the validator as-is would reject prompt-compliant rows.
- **Verdict.** OWNER-DECISION. Question: "Should research gathering/output fail on malformed evidence CSVs?"
  - **Recommend WIRE** `validate_source_register`/`validate_citations` errors (not format warnings) into `_evaluate_gathering_guard`/`_evaluate_output_guard`, after aligning the status vocabulary.
  - Otherwise DELETE ~365 LOC, keeping the two column constants.
  - Confidence High (on the facts).

## Slice 4: Tracker ticket-first origin + gateway authority report
- **What.**
  - `tracker/origin.py:117` `search_origin_candidates` (SaaS issue search) and `:324` `start_mission_from_ticket` (derive slug, create mission, bind origin). Their private helpers are `_derive_slug_from_ticket`, `_derive_ticket_summary`, `_normalize_summary_text`, `_ORIGIN_PROVIDERS` and the two regexes (49 LOC), plus `origin_models.SearchOriginResult`/`MissionFromTicketResult` (24 LOC).
  - `tracker/gateway.py:487-531` `record_conflicts`/`authority_report`/`GatewayAuthorityReport`.
  - `tracker/service.py:113` `supported_providers`.
- **History.**
  - Origin pair: `d1dafbaf4` (2026-04-01, "feat(061): Ticket-first mission origin binding (#360)"). **Never wired.** The 061 WP05 names `/spec-kitty.specify` as the consumer, but no template ever called it (`git log -S'search_origin_candidates' -- packs src/doctrine` is empty).
  - Gateway: `83ac1bfd3` (2026-08-21, "feat(TRK-M1-04): add GatewayCommandRunner").
  - `supported_providers`: `ad9b32711` (2026-02-27).
- **Replaced by.**
  - Origin: `spec-kitty mission create --from-ticket provider:KEY` (`cli/commands/mission_type.py:252`, ticket fetch at ~316 via `SaaSTrackerService.issue_search`, saas_service.py:609), then `write_pending_origin`, then `tracker/origin_consumer.py` → `bind_mission_origin`.
  - Gateway: nothing. `local_service.py:389` builds the runner but discards it (`connector, _gateway_runner = …`), and `:451-457` surfaces `result.conflicts` directly.
- **Tests.**
  - `tests/tracker/test_origin.py`: 9 dead + 3 mixed of 29.
  - `test_origin_integration.py`: 5 dead + 1 mixed of 13 (~300 LOC (b)).
  - `test_origin_models.py`: result-model cases.
  - `tests/tracker/test_gateway.py:460-545`: 7 tests, 67 LOC (b).
  - `tests/tracker/test_service.py:87-110`: 4 tests (b).
  - Live `bind_mission_origin` coverage stays in the same files (17 live tests).
- **Open intent.** `kitty-specs/journal-project-consent-3030-01KYKWQS/egress-inventory.md:218` already records "`search_origin_candidates` — No production caller". There is no open issue.
- **Risk.** Deleting `search_origin_candidates` removes one SaaS egress site. Update the egress inventory, and remove the `pyproject.toml:754` exclude entry only if origin.py disappears (it does not).
- **Verdict.**
  - DELETE the origin pair, its helpers and the two models (~240 LOC).
  - DELETE `supported_providers`.
  - Gateway: OWNER-DECISION. Recommend WIRE (keep the runner at local_service.py:389, call `runner.record_conflicts(result.conflicts)` after `engine.sync`, and surface `authority_report()` in `tracker status --json`), else DELETE the 46 LOC.
  - Confidence High (origin), Medium (gateway).

## Slice 5: Skills installer legacy projection chain + manifest query API
- **What.** `skills/installer.py:131-308`: `create_skill_backup`, `_archive_existing_path`, `_replacement_is_owned`, `_project_skill_file`, `_project_skill_files`. This was the pre-assessment direct projection path that archived owned files and copied skill files. Also covered: `ManagedSkillManifest.remove_entries_for_agent/find_by_skill/find_by_installed_path` (manifest.py:74-89) and `ManifestEntry.with_agent_removed` (manifest_store.py:106).
- **History.** Introduced in `cea2d8de0` (2026-04-04, "globalize managed doctrine skills (#380)"). The last runtime callers were removed in `5f271f07f` (2026-09-06, "feat(WP05): coordinate retained skill assessments and guarded project repair", mission `upgrade-preview-mission-health-01M1V6E1`), which rerouted `install_skills_for_agent`/`install_all_skills` to `_install_caller_skills` (installer.py:1177). Finders from `024f5089e` (#330); `with_agent_removed` from `18cb1b358` (#628).
- **Replaced by.** `_prepare_project_skills` (installer.py:756), which retains the old file via `prepare_skill_backup` plus a planned backup write (806-830), `_preserve_project_path` (882, consent_required for modified managed content), and `_apply_project_skill_write` (959). `_backup_parent` and `SkillBackupReplacement` stay live. `asset_preservation/provers.py:16,117` cite `_replacement_is_owned` in comments; update those.
- **Tests.** `tests/specify_cli/skills/test_installer.py` has 63 tests:
  - 7 dead (169 LOC): 713, 738, 782, 876, 916, 1578, 1791. These include the Windows no-`fchmod` and symlink-chmod regressions. They pin the dead copy only (b), because the live apply uses `Path.chmod`/`chmod_no_follow`.
  - 4 mixed (842, 897, 938, 992) → SPLIT onto `prepare_skill_backup`/`apply_project_skills`.
  - `test_manifest.py`: 3 (b).
  - `find_by_skill`/`find_by_installed_path` are used as **assertion helpers** in live-path tests (`test_e2e.py:281,400`, `test_verifier.py:607`) → keep.
- **Open intent.** None.
- **Risk.** Low. Confirm the live backup path has a symlink-member test before dropping 1791 (grep `apply_project_skills` + symlink in test_installer.py).
- **Verdict.**
  - MOVE-TESTS-THEN-DELETE the chain (165 LOC).
  - DELETE `remove_entries_for_agent` and `with_agent_removed` (13 LOC).
  - KEEP the two finders with an allowlist note: "manifest query API used by live-path test assertions".
  - Confidence High.

## Slice 6: `specify_cli.calibration` (walker + inequality)
- **What.** `walk_mission(mission_key, repo_root)` resolves each step's DRG scope (built-in graph + `.kittify/doctrine/overlays/calibration-<mission>.yaml`) and asserts the architecture §4.5.1 inequality against a curated `REQUIRED_SCOPE_MAP`. `assert_inequality_holds` is the predicate.
- **History.** `9733727df` (2026-04-27, #821). Mission `mission-retrospective-learning-loop-01KQ6YEG` WP10 "Action-Surface Calibration", FR-030/031/032. **Never runtime-wired by design**: FR-032 says inequalities "MUST hold … validated by the calibration". It is maintained as a gate: `4c1e179ce` (2026-08-29, DIRECTIVE_003 move, WP03) updated the map when edges moved.
- **Replaced by.** Nothing. The FR-030 per-mission reports (`architecture/calibration/*.md`) do not exist in the repo. The four overlay YAMLs do, and only the walker reads them.
- **Tests.** `tests/calibration/test_walker.py` (283 LOC) and `test_inequality.py` (151 LOC). 33 tests, **all pass** (13.8 s). `test_inequality_holds_for_all_steps` is parametrized over the real built-in graph and overlays. Classification: (a), a live DRG regression gate. No other test pins per-action direct scope membership (`test_required_scope_membership_is_byte_stable`).
- **Open intent.** FR-032 (01KQ6YEG). The first-pass §3.1 recommended "remove with tests"; that would silently delete this gate.
- **Risk.** Deleting it loses the only enforcement of FR-032 and orphans the four `.kittify/doctrine/overlays/calibration-*.yaml`.
- **Verdict.** MOVE: relocate `walker.py` and `inequality.py` to `tests/calibration/_walker.py` (or `tests/_support/`), then delete the src package (637 src LOC out of the wheel). Update the `pyproject.toml:467,1029-1030` exclude entries. Alternative: KEEP with a `_CATEGORY_TEST_GATE` note. Confidence High.

## Slice 7: `specify_cli.proof`
- **What.** Pydantic schemas for `ProofItemRecorded`, `ReviewProofRecorded`, `TestEvidenceCaptured`, etc.: "Typed schemas for CLI proof/evidence **sync** events" (events.py:1).
- **History.** Added in `b64b8e079` (2026-06-10, "feat(sync): add local proof event schemas (#1803)"). The only runtime consumer was `src/specify_cli/sync/emitter.py` (`from specify_cli.proof.events import …`). It was deleted in `66038e2a5` (2026-08-25, "refactor(sync): remove sync transport surfaces", Issue #5), together with `tests/sync/test_proof_event_emission.py`.
- **Replaced by.** Nothing. Zeitgeist moments carry no proof payloads.
- **Tests.** `tests/proof/test_event_schemas.py` (219 LOC, 9 tests) and `tests/architectural/test_lifted_proof.py` (79 LOC, 2 tests), both (b). `tests/architectural/test_verdict_vocab_single_source.py:109` lists the file in `_SWEPT_MODULES`. That constant is never read (only its definition), and it still lists the deleted `sync/emitter.py`. Remove the line, or the whole vacuous constant.
- **Open intent.** None (the "until spec-kitty-events grows canonical models" docstring is moot).
- **Risk.** None found. Remove `pyproject.toml:681,1715` exclude entries.
- **Verdict.** DELETE (424 src, 298 test). Confidence High.

## Slice 8: `auth.websocket` + auth test-only helpers
- **What.**
  - `WebSocketTokenProvisioner` POSTs `/api/v1/ws-token` before a WS upgrade. Its docstring: "immediately before `sync/client.py` opens a WS upgrade".
  - `FileFallbackStorage._load_or_create_salt` (file_fallback.py:127, 12 LOC).
  - `BrowserLauncher.is_available` (browser_launcher.py:25, 13 LOC).
  - `ResolvedServerTarget.to_diagnostics_dict` (server_target.py:111, 9 LOC).
- **History.**
  - websocket: `1bb9f3947` (2026-04-10, mission 080 #578). Its consumer `sync/client.py` was deleted in `66038e2a5` (2026-08-25).
  - Salt writer de-wired in `046870733` (2026-09-05, "fix(auth): make stored sessions hostname-stable"): v3 uses `_load_or_create_key`, and the legacy salt is only read in `_decrypt` (line 190).
  - `is_available`: never called since `1bb9f3947`. The live fallback is `BrowserLauncher.launch()` returning False (authorization_code.py:127).
  - `to_diagnostics_dict`: last caller went with `522e462a6` (2026-08-25, retire hosted-sync consent chain).
- **Replaced by.** Zeitgeist uses `/api/v1/live/capability/cli/` (zeitgeist_client/resolution.py:232), not ws-token.
- **Tests.**
  - `tests/auth/test_websocket_provisioning.py` (14 tests, 307 LOC) and `test_ws_provisioning_issuer.py` (4, 227): (b).
  - One test in `tests/auth/integration/test_transport_rewired.py:96`: (b).
  - Allowance rows in `tests/architectural/test_egress_consent_boundary.py:564,1888,1929` and prose in `test_endpoint_opt_in.py:56,263`: remove.
  - `test_secure_storage_file.py:208` `test_legacy_v2_session_is_read_and_migrated` uses the salt helper as a **fixture** for a live legacy-migration test (a). MOVE: write `os.urandom(16)` to `session.salt` directly.
  - `test_browser_launcher.py:20,28` (2 tests, b).
  - `test_server_target.py:72` (1 test, b).
- **Open intent.** The planning repo `reference/AUDIT-REPO-ADMISSION-PARADIGM-2026-08-24.md:463` calls the provisioner "zero rework needed; reusable" for the zeitgeist push side. Zeitgeist then chose capability minting instead, so that reuse did not happen.
- **Risk.** The `auth/config.py:164` docstring lists the file as a fenced token-send path; update it. `_baselines.yaml` `allowed_direct_httpx_files` is not affected (the provisioner uses `PublicHttpClient`).
- **Verdict.** DELETE (246 src LOC, ~545 test LOC). MOVE the one salt fixture test. Confidence High.

## Slice 9: Audit repo-level converters (dead twin of an uncovered live path)
- **What.** `audit/identity_adapter.py:100,140,177` convert duplicate-prefix, ambiguous-selector and duplicate-mission_id groups into `MissionFinding`s. `detectors.py:156` `detect_corrupt_jsonl`. `models.py:131` `finding_codes`.
- **History.** All from `2ff3bf326` (2026-05-02, "feat(audit): add read-only mission-state audit engine"). `engine.py:205-282` `_compute_repo_findings_by_slug` reimplements the three converters inline. Its own docstring says "by re-running the adapters", which is false. The detail strings are byte-identical.
- **Replaced by.**
  - Repo-level: the inline loops in engine.py:236-282 (duplicated logic).
  - Corrupt JSONL: `audit/classifiers/status_events.py:69-98` (reports multiple lines, not first-only).
- **Tests.**
  - `tests/audit/test_identity_adapter.py`: 10/15 (178 LOC) pin the adapters.
  - `test_detectors.py`: 5 (54 LOC) pin `detect_corrupt_jsonl`. The live classifier is covered in `test_audit_classifiers.py:311-430,864-889` (b).
  - **The live repo-level path is uncovered**: `grep DUPLICATE_PREFIX|AMBIGUOUS_SELECTOR|DUPLICATE_MISSION_ID tests/audit/test_audit_engine.py` returns nothing.
  - `finding_codes` is used as an assertion helper in `test_audit_models.py` and `tests/migration/test_teamspace_migration_rehearsal.py` → keep.
- **Open intent.** None.
- **Risk.** Deleting the adapters would leave the live repo-level findings with zero tests.
- **Verdict.**
  - WIRE: make `_compute_repo_findings_by_slug` call the three adapters (partitioning by slug), which removes ~45 inline LOC. Keep the adapter tests and add one engine test for attribution.
  - DELETE `detect_corrupt_jsonl` and its 5 tests.
  - KEEP `finding_codes`.
  - Confidence High.

## Slice 10: Runtime leftovers
- **What.** `runtime/resolver.py:672` `resolve_template_by_urn` + `TemplateURNError` (the "URN lane", C-004). `runtime/agent_commands.py:776` `_sync_agent_commands` (a 6-LOC per-agent wrapper). `runtime/bootstrap.py:121` `_cleanup_orphaned_update_dirs` (now warn-only).
- **History.**
  - URN lane: `867a414a9` (2026-07-17, mission-step-creatability S-C). Never called.
  - `_sync_agent_commands`: `54269f7c1` (2026-04-07, v3.1.1a3). Its runtime caller was removed in `07bb21e17` (2026-09-06, "feat(WP03): prepare immutable global asset batches"), which also removed `_cleanup_orphaned_update_dirs(home.parent)`. That function had been added in `c60f4c796` (2026-02-09).
- **Replaced by.**
  - `charter/activation/context_renderers/template_include.py:89` → `charter.offering.template_catalog.resolve_template_by_id` (covered by `tests/charter/test_context_include.py` and others).
  - `ensure_global_agent_commands` (agent_commands.py:784).
  - Nothing for the cleanup; the new staging never creates `.kittify_update_*`.
- **Tests.**
  - `tests/runtime/test_resolve_by_urn.py`: 11 tests, 176 LOC (b).
  - `_sync_agent_commands`: 8 tests (173 LOC) across `tests/specify_cli/runtime/test_agent_commands.py` and `test_agent_commands_routing.py`. These are (a): they exercise live `assess_global_agent_commands`/`_apply_command_assessment` with an injected `templates_dir`, which `ensure_global_agent_commands` cannot take.
  - `tests/runtime/test_bootstrap_unit.py`: 3 tests, 31 LOC (b).
- **Open intent.** #2761 (the allowlist comment at `test_no_dead_symbols.py:1572-1581`: "consumer wired in #2761"). Status unknown offline. The consumer shipped through the charter-layer resolver instead.
- **Risk.** None.
- **Verdict.**
  - DELETE the URN lane (83 LOC + `_TEMPLATE_URN_PREFIX` / `_URN_LANE_MISSIONS_ROOT_SENTINEL`) and close #2761 as superseded.
  - `_sync_agent_commands`: KEEP as a test seam (allowlist "templates_dir-injection seam for command-sync tests"), or add `templates_dir`/`script_type` kwargs to `ensure_global_agent_commands` and retarget.
  - DELETE the cleanup.
  - Confidence High / Medium / High.

## Slice 11: Review / retrospective residue
- **What and history.**
  - `review/gate_bindings.py:195` `load_gate_bindings` (`0616a5957`, 2026-07-22): a 14-LOC wrapper over `_load_review_contract`. The live join is `resolve_gate_bindings_for_transition` (:364), imported by `tasks_move_task.py:138`.
  - `review/arbiter.py:257` `prompt_arbiter_checklist` (76 LOC, `4bf7f5ac6` 2026-04-06, mission 066 WP06, #441): the interactive checklist. **Never wired.** The live path is non-interactive: `parse_category_from_note` + `_synthetic_checklist` + `create_arbiter_decision` (tasks_verdict_persistence.py:105,1017).
  - `review/artifacts.py:174` `has_complete_override` (`89fc2b8ee` 2026-06-14, #1924). Note that `-S'has_complete_override('` misses property access. Its last reader, `has_override = snapshot_complete or artifact.has_complete_override`, was deliberately removed in `a5ae131e4` (2026-08-06, `verdict-seam-write-unification-01KZ9Q35`, "WP10 deletes the fallback"). The replacement is the event-sourced `ReviewOverride.complete` (status/models.py:453).
  - `retrospective/generator.py:618` `_classify_risk` and `retrospective/events.py:114` `ProposalGeneratedPayload`: `16af677bf` (2026-05-19, #1138/#1181) and `9733727df` (#821).
  - `retrospective/summary.py:195` `_read_slug_from_meta` (#821).
- **Tests.**
  - `test_gate_bindings.py`: 4 dead (29 LOC) (b).
  - `test_arbiter.py`: 4 (40) (b).
  - `test_artifacts.py:114-120`: 1 (b).
  - `tests/post_merge/test_2684_review_override_recognition.py:162` uses the predicate as a probe (a): assert `override_actor is None` instead.
  - `test_generator.py`: 8 (77) and `test_events.py`: 3 (23), for `_classify_risk`/`_read_slug_from_meta`.
  - `test_events_shapes.py`: 2 (15).
- **BEHAVIOUR GAP.** `_build_findings` (generator.py:1181-1367) declares `proposals: list[GenProposal] = []` and only ever sorts it. `git log -S'GenProposal(' / 'proposals.append(' -- src/specify_cli/retrospective/` shows no producer ever existed. `policy.generate_proposals` defaults to `True` (policy.py:168), and `apply_low_risk_changes` (policy.py:149) has nothing to apply. **Proposal generation is advertised policy with no implementation.** `_classify_risk` and `ProposalGeneratedPayload` are its unbuilt parts.
- **Verdict.**
  - DELETE `load_gate_bindings`, `prompt_arbiter_checklist`, `has_complete_override` (finishing mission 191's WP10) and `_read_slug_from_meta` (~110 LOC).
  - OWNER-DECISION on the proposal pair. Question: "Implement retrospective proposal generation (#1138), or retire `generate_proposals`/`apply_low_risk_changes`?" Recommend retiring the knobs and the pair (~20 LOC) unless #1138 has a live follow-up.
  - Confidence High.

## Slice 12: Zeitgeist focus lifecycle
- **What.** `ZeitgeistClient.focus_heartbeat/focus_pause/focus_end` (transport.py:483-530, 53 LOC) complete the relay's focus protocol. `FilteredStream.current_focus` (filtered_stream.py:579) and `Deadline.expired` (repo_identity.py:130) are small readers.
- **History.** `01b19888a` (2026-08-21, "feat(Z1-T1): transport.py — offer()/focus_*()/presence()"). Only `focus_start` is wired (`status/zeitgeist_bridge.py:566`, on each liveness refresh while a WP is in focus).
- **Replaced by.** Nothing. The bridge returns early when `focus_wp is None` (bridge.py:548), so focus is never ended or paused. The relay's TTL is the only terminator.
- **Tests.** `tests/zeitgeist_client/test_transport.py`: 1 dead + 10 mixed. The mixed tests parametrize over all four verbs and assert the `focus_ref` grammar (FIX-M2-10), `focus_end` reason restriction and so on. `test_operability.py`: 1 mixed. `test_filtered_stream.py`: 1 (b) for `current_focus`.
- **Open intent.** `docs/plans/zeitgeist-client-wp01-remaining.md:17` lists the verbs as delivered surface. The zeitgeist schema (`managed_control.schema.json FocusArgs`) is authored upstream (`spec-kitty/zeitgeist`, a client repo per ADR 2026-09-06-1).
- **Risk.** These are client verbs for an upstream-authored protocol. Deleting them diverges the client from the relay contract.
- **Verdict.** OWNER-DECISION. Question: "Should a WP leaving `in_progress` send `focus.end reason=user`?" Recommend WIRE `focus_end` in the bridge on transitions out of focus (small), and KEEP heartbeat/pause as protocol-complete client API with an allowlist note. Remove `current_focus` only if the dashboard reader never lands. Confidence Medium.

## Slice 13: `tool_surface` vocabulary and docs linter
- **What.**
  - Finding codes no detector emits: `findings.py:30,40,65`.
  - Unused enums: `enums.py:64,72` (13 LOC).
  - `providers/managed_skills.py:755` `doctrine_skill_entries`, whose docstring says "helper for tests" (8 LOC).
  - The FR-017 docs linter: `docs.py` `DocsLinter`/`format_findings`, `service.py:107-120` `build_docs_linter`/`lint_docs_directory`.
- **History.** All from `3aaf618fd` (2026-06-14, mission `tool-surface-contract-01KV2K2P`).
- **Correction.** The docs linter is **not** dead. `tests/specify_cli/tool_surface/test_docs.py:193` `test_docs_contract_lint` lints the real repo `docs/` on every run (T040 "CI-level docs contract assertion", FR-017), and two mutation tests (200, 218) prove it bites. It is a test-hosted gate like slice 6.
- **Tests.** `test_findings.py` and `test_enums.py` (5+5 parametrized vocabulary tests) are (b). `test_managed_skills.py`: 1 (b). `test_docs.py`: 16 tests, (a), keep.
- **Verdict.**
  - DELETE the three codes and two enums with their test rows.
  - MOVE `doctrine_skill_entries` into tests.
  - KEEP `format_findings`/`lint_docs_directory` under a test-gate allowlist note ("FR-017 docs-contract gate, driven from test_docs.py").
  - Confidence High.

## Slice 14: `doctrine.pack_lineage` / `pack_descriptor` / manifest loaders
- **What.** Pack-lineage ordering and accompanying-pack resolution over `PackDescriptor` (309 LOC). `pack_manifest.load_pack_manifest`/`absorb_synthesis_manifest` (44 LOC).
- **History.** `610cdbfaa` (2026-08-16, "unify pack metadata onto one pack-manifest schema (#3500-#3503)"). Never wired.
- **Replaced by.** Not yet. This is the intended cutover of #3511 item 4.
- **Tests.**
  - Whole-file (b): `tests/doctrine/test_pack_lineage.py` (10 tests, 146 LOC) and `tests/architectural/test_pack_lineage_no_parallel_resolver.py` (4, 226).
  - Mixed: `test_pack_manifest_schema.py`, `test_charter_profile_absorption.py`, `test_pack_id_identity.py`, `test_builtin_manifest.py` and `tests/specify_cli/doctrine/test_snapshot.py` touch the loaders alongside live code.
- **Open intent.** #3511 (wiring; the first pass saw it OPEN `status:blocked`) and #3518 (OPEN). Status unknown offline beyond that.
- **Risk.** Deleting preempts a planned cutover. Keeping stalls indefinitely.
- **Verdict.** OWNER-DECISION. Question: "Timebox #3511, e.g. two weeks, else delete both modules plus the two loaders and re-add them with the cutover?" Recommend the timebox. Confidence Medium.

## Slice 15: Misc small helpers
- **Sync-era path properties.** `paths/windows_paths.py:48,52` `RuntimeRoot.sync_dir`/`daemon_dir` (`95ad7d78e` 2026-04-15, #633). The last runtime use went with `66038e2a5`. Asserts: `tests/paths/test_windows_paths.py:30-31`, `test_runtime_root_spec_kitty_home.py:165-166,198-199`, `tests/kernel/test_paths_unified_windows_root.py:114-115`, plus the `tests/conftest.py:686-688` daemon cleanup. → DELETE, High. Nothing removes stale `~/.spec-kitty/{sync,daemon}` dirs on user machines. That is cosmetic, but it could go in a one-shot upgrade migration.
- **Invocation helpers.** `invocation/registry.py:194` `has_profiles` (`177cb91ab`) and `task_class_map.py:76` `known_verbs` (`9366cb87f`): 2 test files each (b). → DELETE, Medium.
- **Tasks ports.** `agent_tasks_ports.py:468` `default_ports` (12 LOC) and `wp_tasks_dir` (Protocol + Real; `381db8d5f` 2026-07-02). Commands build their own `TasksPorts` bound to the patchable `tasks` module (tasks_mark_status.py:137, tasks_status_cmd.py:112). → DELETE `default_ports` and retarget `test_tasks_ports.py`/`test_verdict_save_topologies.py` to construct ports explicitly. `wp_tasks_dir`: DELETE (3 test files), Medium.
- **Upgrade-attempt query API.** `compat/history.py:228,255,294` `UpgradeAttemptStore.is_idempotent`/`consecutive_failure_count`/`last_success_timestamp` (94 LOC, `00e9abc8b` "feat(1358)"). The store is write-only (`readiness/upgrade_ux.py:281` appends; nothing reads). → OWNER-DECISION: "use it to damp repeated upgrade nags (#1358), or drop the query API?" Recommend DELETE unless the nag work is scheduled.
- **Test double in src.** `context/mission_resolver.py:466` `FakeMissionResolver` (25 LOC, `24b50de6a` 2026-07-09). It is a test double in src; `mission_runtime` references it only in docstrings. → MOVE to `tests/` fixtures, Medium.
- **Predicates, each with 0 src callers and 1-2 test files.**
  - Keep:
    - `requirement_mapping/grammar.py:146` `is_functional`: value-type property from `3e9f5fd4e` (2026-09-29, one day old, sibling of live `is_success_criterion`).
    - `dossier/hasher.py:215,243` `WP_*_PROJECTION_FIELDS`: partition contract pinned by `test_canonical_hash.py`.
  - Delete in a campsite batch (Low confidence each):
    - `decisions/ownership.py:240` `has_unreadable_ledger`
    - `dossier/models.py:388` `has_parity_diff`
    - `dossier/reconciler.py:125` `differing_paths`
    - `dossier/manifest.py:216,242` `get_blocking_artifacts`, `validate_manifest` (the module docstring at 31-32 and `runtime/resolver.py:633` mention them; fix the prose)
    - `widen/state.py:168` `validate_entry_schema`
    - `widen/interview_helpers.py:46` `render_widen_hint_if_present`
    - `frontmatter.py:383` `validate_frontmatter`
    - live_work `capability_notes` (`994177009`, #4268; a Protocol member, so check adapters before removing)

---

## Corrections to the first pass
1. **The calibration package is a live test-driven gate, not dead** (§3.1 said "remove with tests (needs-owner)"). The 33 tests run `walk_mission` against the real built-in DRG and enforce FR-032 (mission 01KQ6YEG). Recommend relocating it into `tests/`, not deleting it.
2. **The `tool_surface` docs linter (`format_findings`, `lint_docs_directory`, plus the unlisted `build_docs_linter`/`DocsLinter`) is a live FR-017 CI gate** via `test_docs.py:193`. Reclassify it as API/test-gate KEEP.
3. **`doc_state` setters, research validators and retrospective proposals are behaviour gaps, not just forward APIs.**
   - Setup-plan gap analysis is unreachable, because `iteration_mode` is never set.
   - The research review citation gate was dropped in `37484eeb8`/`4eee6aeee`.
   - `generate_proposals` is a no-op.
4. **The audit adapters are a tested twin of an untested live path.** Deleting them "with tests" (first pass) would leave `_compute_repo_findings_by_slug` at zero coverage. WIRE the engine onto them instead.
5. **`has_complete_override` was deliberately de-wired** by mission 191 (`a5ae131e4`), which promised "WP10 deletes the fallback". It is unfinished cleanup, and one test (`test_2684…:162`) uses it as a probe. First-pass history lookups keyed on `(` miss it because it is a property.
6. **`find_by_skill`/`find_by_installed_path` and `audit.models.finding_codes` are assertion helpers inside live-path tests.** Keep them as cheap query API; removal would mean rewriting live tests.
7. **`_sync_agent_commands` is a `templates_dir`-injection seam** that the live `ensure_global_agent_commands` lacks. Its 8 tests exercise live assessment code. Keep it, or widen the live signature, before removing.
8. **Line drift:** `_install_caller_skills` is at installer.py:1177, not 367. Line 367 is inside `install_skills_for_agent`.
9. **Vacuous test constant.** `tests/architectural/test_verdict_vocab_single_source.py:106` `_SWEPT_MODULES` is never read and still lists the deleted `src/specify_cli/sync/emitter.py`.
10. **Deletion mechanics the first pass did not list:**
    - `pyproject.toml` `[tool.ruff.format] exclude` entries (467 calibration/walker.py, 681 proof/events.py, 1029-1030 tests/calibration/*, 1715 tests/proof/test_event_schemas.py) are guarded by an "every entry must exist on disk" ratchet (#559).
    - `test_egress_consent_boundary.py` allowance rows 564/1888/1929 for `auth/websocket/token_provisioning.py`.
