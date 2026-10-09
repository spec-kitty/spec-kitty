# Plan research: package split (FR-010 / OD-9), project pack root (FR-016), rename sizing

Mission `charter-pack-cutover-01M491G6`, branch `issue-3732-charter-pack-rename`. Read-only survey taken 2026-10-06 at the branch head. No `.codegraph/` index exists, so every count here comes from AST or token scans of the live tree (scripts were kept in the session scratchpad and are not committed).

Inputs: spec FR-010, FR-015, FR-016, C-007, OD-9; ADR `docs/adr/4.x/2026-10-06-1-...` amendment ruling 9; CLAUDE.md "Modularity SSOT" (`kernel <- charter <- {glossary, runtime, mission_runtime} <- specify_cli`).

---

## Headline findings

1. **The ruling's `charter.offering.packs` destination breaks an existing gate as written.** `tests/architectural/test_charter_offering_does_not_import_activation.py` forbids any import from `charter.offering` into `charter.activation`, and it walks the full AST, so lazy imports count too. Four of the six pack-model and tooling modules import `charter.activation` today: `pack_manifest`, `builtin_manifest`, `pack_lineage` and `pack_validator`. `pack_assembler` will import it once `org_charter` moves. Each case has a small fix that pushes the dependency down into `offering` (§A.3). The ruling's placement can therefore stand, but the WP must do those fixes first.
2. **`pack_assembler` imports the adapters.** It uses `snapshot.write_pack_manifest` and `sources.protocol.FetchResult`. The minimal fix moves the pure manifest writer into `charter.offering.packs.pack_manifest`, where it takes primitive fields, not `FetchResult` (§A.3).
3. **Deleting the boundary exemption has a cost on the `specify_cli` side.** Today `src/specify_cli/doctrine/**` may import `charter.offering.*` directly (`test_runtime_charter_doctrine_boundary._EXEMPT_SUBPACKAGE`, `test_doctrine_census.EXEMPT_MANAGEMENT_SURFACE`). After the split, every `specify_cli` caller of the pack model reaches `charter.offering` and goes red. That covers the CLI command module, `drg_writers/registry.py`, `snapshot.py` and `api_source.py`. The fix is a **`charter.packs` facade** (a sibling of `charter.drg` and `charter.pack_paths`), plus two names added to the `charter.drg` facade. Without the facade, the gates close empty only by growing the lazy ratchet baseline, which NFR-002 forbids.
4. **`_layer_roots` moves to `charter` with no blocker.** It imports only `charter.drg` (`resolve_org_roots`, `resolve_existing_org_roots`).
5. **A kernel module for the project root already exists, under the retired name.** `src/kernel/doctrine_root.py` already defines `CANONICAL_DOCTRINE_DIRNAME = "charter-packs"`, plus the read-side fallback `resolve_doctrine_read_root` and its `LegacyDoctrineRootWarning`. FR-011 removes both. FR-016 should **replace** this module with `kernel/charter_pack_paths.py` rather than add a second one.
6. **Path sites.** 50 `src` files and 123 lines spell `.kittify/doctrine` (literal or `".kittify" / "doctrine"`). An AST scan finds **56 path-construction sites** that join a `"doctrine"` segment to the project root, directly or through a layer root. Of those, **12 are WRITE or BOTH**, listed in §B.1. On the test side, 109 files and 309 lines spell the path.

---

## Part A: splitting `src/specify_cli/doctrine/` (7,615 lines, 22 files)

### A.1 Module inventory: imports, importers, tests

"Charter imports" lists only first-party and third-party imports. Stdlib imports are omitted.

| Module (lines) | Destination | Charter / other imports | Blocking import | `src` importers (outside the package) | Test files |
|---|---|---|---|---|---|
| `pack_descriptor.py` (69) | `charter.offering.packs` | pydantic | none | **none**: a dead-module allowlisted adapter (#3518) | `tests/doctrine/test_pack_id_identity.py` |
| `pack_lineage.py` (240) | `charter.offering.packs` | `charter.activation.org_extends` | **offering→activation** | none (allowlisted not-yet-wired) | `tests/doctrine/test_pack_lineage.py`; gate `test_pack_lineage_no_parallel_resolver.py` |
| `pack_manifest.py` (365) | `charter.offering.packs` | pydantic, ruamel; `charter.activation.synthesizer.manifest` (`SynthesisManifest`, `hash_manifest_payload`); `charter.activation.synthesizer.synthesize_pipeline.canonical_yaml`; `charter.offering.artifact_kinds` | **offering→activation** (3 symbols) | `builtin_manifest`, `snapshot` (in-package) | `tests/doctrine/test_pack_manifest_schema.py`, `test_charter_profile_absorption.py`, `test_counts_derivation.py`, `test_builtin_manifest.py`; `tests/specify_cli/doctrine/test_snapshot.py` |
| `builtin_manifest.py` (156) | `charter.offering.packs` | ruamel; `charter.activation.synthesizer.manifest.hash_content_bytes`; `charter.offering.artifact_kinds`; `.pack_manifest` | **offering→activation** (1 symbol) | `cli/commands/doctrine.py` | `tests/doctrine/test_builtin_manifest.py`; gate `test_pack_manifest_no_author_edit.py` |
| `pack_validator.py` (1,819) | `charter.offering.packs` | pydantic, ruamel; `charter.offering.{artifact_kinds, drg.merge, drg.override_policy, drg.org_pack_loader, pack_paths, agent_profiles.*, assets, directives, ...}`; lazy `specify_cli.doctrine.org_charter.OrgCharterPolicy` (l.1684) | **`OrgCharterPolicy` → activation** after the move | `cli/commands/doctrine.py`, `pack_assembler` | `tests/specify_cli/doctrine/test_pack_validator.py`, `..._fragment_finding.py`, `..._kind_derivation.py`, `test_pack_assembler.py`; `tests/doctrine/drg/test_org_fragment_validation.py`, `test_sharding_silent_degrade.py`; `tests/doctrine/test_org_pack_augmentation.py`, `test_template_asset_e2e.py`; `tests/integration/test_quickstart_end_to_end.py` |
| `pack_assembler.py` (809) | `charter.offering.packs` | ruamel; `charter.offering.drg.{override_policy, loader, models, migration.extractor}`; `.pack_validator`; **`.snapshot.write_pack_manifest`**; **`.sources.protocol.FetchResult`**; lazy `specify_cli.doctrine.org_charter.OrgCharterPolicy` (l.679) | **imports adapters**; **`OrgCharterPolicy` → activation** | `cli/commands/doctrine.py`, `cli/commands/_doctrine_collect.py`, `drg_writers/registry.py` (module import + private `_document_dict`) | `tests/specify_cli/doctrine/test_pack_assembler.py`; `tests/doctrine/test_counts_derivation.py`, `test_pack_version_relocation.py`; gate `test_drg_writer_discovery.py` |
| `org_charter.py` (928) | `charter.activation` | pydantic, ruamel; `charter.activation.{activations, org_pack_discovery, default_pack, kind_vocabulary, pack_context, activation_engine, catalog, pack_manager, org_extends, invocation_context, interview}`; `charter.offering.{artifact_kinds, drg.org_pack_config}`; **lazy `specify_cli.cli.commands.charter._layer_roots` ×2 (l.386, l.918)** | **activation→specify_cli** (fixed by A.3 #5); also imports `charter.activation.default_pack`, which FR-005 deletes, so FR-015 must land first (C-008) | `charter_runtime/lint/checks/org_layer.py`, `cli/commands/_doctrine_collect.py`, `cli/commands/charter/generate.py`, `cli/commands/charter/interview.py`, `cli/commands/doctrine.py`, `upgrade/migrations/m_unify_charter_activation.py` | `tests/specify_cli/doctrine/test_org_charter.py`, `test_org_charter_merge_parity.py`, `test_org_charter_pack_context.py`, `test_org_charter_union.py`, `test_missing_pack_policy.py`; `tests/charter/test_answers_inert_and_org_union.py`, `test_directive_identity_mapping.py`; `tests/cli/test_doctrine_org_commands.py`; `tests/doctrine/pack_skills/test_kind_registration.py`; `tests/integration/test_org_pack_artifact_lifecycle.py`; `tests/specify_cli/cli/commands/test_doctrine_collect.py` (patch string); `tests/cli/commands/test_charter_json_error_contract.py` (patch string); gate `test_kind_table_derivation.py` |
| `org_charter_loader.py` (100) | `charter.activation` | lazy `.org_charter` | none | `cli/commands/charter/context.py` | `tests/specify_cli/doctrine/test_org_charter.py`; `tests/specify_cli/test_provenance_integration.py`; `tests/cli/commands/test_charter_rendering.py` (patch string) |
| `config.py` (44) | `charter.activation` | re-exports `charter.offering.drg.org_pack_config` symbols (`import X as X`, not in `__all__`); lazy `.org_charter.MissingDoctrinePackError` | none, but the re-exports are a C-001 alias | **no `src` caller** of `assert_pack_local_paths_exist` (only `__init__` and tests) | `tests/specify_cli/doctrine/test_config.py`, `test_missing_pack_policy.py`, `test_snapshot.py`; `tests/integration/test_org_pack_subdir_e2e.py` |
| `sources/` (`__init__` 21, `protocol` 80, `api_source` 318, `git_source` 280, `https_source` 790) | `specify_cli.charter_packs.sources` | `requests` (api, https); `specify_cli.git.ref_advance` (git); `kernel.clock`; **`charter.offering.artifact_kinds.CORE_KIND_PLURALS` (api_source, module level)** | `api_source` → `charter.offering` reach, which turns red once the exemption is deleted | `review/scope_source.py` (docstring only), `snapshot`, `template_render.resolve`, `pack_assembler` | `tests/specify_cli/doctrine/test_sources.py`, `test_sources_security.py`, `test_template_render_resolve.py`, `test_snapshot.py`, `test_config.py`; `tests/cli/test_doctrine_org_commands.py`; `tests/doctrine/test_counts_derivation.py`; `tests/integration/test_org_pack_subdir_e2e.py` |
| `snapshot.py` (728) | `specify_cli.charter_packs` | `yaml`, `hmac`; `kernel.clock`; `.config.OrgPackConfig` (TYPE_CHECKING); **lazy `charter.offering.drg.org_pack_config.resolve_relative_path_within_root`** (l.449); `.pack_manifest`; `.sources.*` | lazy `charter.offering` reach, which turns red once the exemption is deleted | `cli/commands/doctrine.py`, `dossier/__init__.py` (docstring) | `tests/specify_cli/doctrine/test_snapshot.py`, `test_config.py`; `tests/doctrine/test_counts_derivation.py`; `tests/integration/test_org_pack_subdir_e2e.py`; `tests/kernel/test_byte_identity_mapping.py` (string key `specify_cli.doctrine.snapshot._iso_now#fetched_at`) |
| `template_render/` (`__init__` 52, `pipeline` 233, `resolve` 260, `ignore_copy` 115, `substitute` 81, `validation` 78) | `specify_cli.charter_packs.template_render` | `.sources.git_source`, `.sources.protocol` only | none | `cli/commands/doctrine.py` | `tests/specify_cli/doctrine/test_template_render_*.py` (5); `tests/cli/test_doctrine_org_commands.py` |
| `__init__.py` (49) | delete | re-exports config, org_charter, snapshot, sources | C-001: no re-export package | `drg_writers/registry.py` (`from specify_cli.doctrine import pack_assembler`); `tests/doctrine/drg/test_org_fragment_validation.py` | none |

The package has three edges back into `specify_cli`, which matches OD-9's "3 back into specify_cli": `org_charter` → `_layer_roots` (×2), and `git_source` → `specify_cli.git.ref_advance`. The `git_source` edge stays inside `specify_cli`.

**Allowed dependencies at the destinations.** No module bound for `charter` uses `requests`, `subprocess`, sockets or git. `pack_assembler` uses `shutil` and `json`, and `pack_validator` uses `mimetypes`. `charter` already depends on pydantic, ruamel and `yaml` (`charter/activation/pack_manager.py`, `scope.py`, `offering/drg/org_governance.py`). `requests` is a top-level runtime dependency (`pyproject.toml:84`, "HTTP client for doctrine-pack https/api sources"). It stays used only by `specify_cli.charter_packs.sources`, so its comment needs the vocabulary change. No architectural test pins third-party imports per layer for `charter`. The egress gate (`test_egress_consent_boundary.py`) scans all of `src/` and keys allowances by path.

### A.2 Name collisions at the destinations

| Destination | Exists? | Note |
|---|---|---|
| `src/charter/offering/packs/` | **no** | Free. Siblings `offering/pack_paths.py` and `offering/pack_skills/` exist. |
| `src/charter/activation/packs/` | yes (`__init__.py`, `default.yaml`, `minimal.yaml`) | FR-005 deletes it. It is listed as a data package in `.github/ci-foreign-coverage-baseline.json` `_provenance.notes`. No clash with `offering/packs`, but do not reuse the name. |
| `src/charter/activation/org_charter.py`, `org_charter_loader.py` | no | Free. Siblings `org_extends.py`, `org_pack_discovery.py` and `org_expected_artifacts.py` already hold org-composition code, a good fit. |
| `src/charter/activation/config.py` | no | Free, but **do not create it**. After C-001 removes the four `import X as X` re-exports, `config.py` holds only `assert_pack_local_paths_exist`, which has no `src` caller. Fold it into `charter.activation.org_charter` next to its exception (`MissingDoctrinePackError` → `MissingCharterPackError`, FR-010), or delete it with its test if the dead-symbol gate flags it. A generic `charter.activation.config` module name would also be ambiguous next to `charter_yaml_io` and `pack_context`. |
| `src/specify_cli/charter_packs/` | no | Free. `specify_cli.charter_runtime` and `charter_*` CLI modules exist; no clash. |
| `src/charter/packs.py` (proposed facade) | no | Free. `charter/pack_paths.py` is the precedent. |
| `src/charter/activation/layer_roots.py` (proposed) | no | Free. |

### A.3 Blockers and minimal fixes, in dependency order

1. **`hash_content_bytes` / `hash_manifest_payload` live in `charter.activation.synthesizer.manifest`.** Move both to offering. Either put them in `charter/offering/yaml_utils.py`, which already owns an offering-side `canonical_yaml` that mirrors the synthesizer's (its docstring says so), or add a new `charter/offering/packs/hashing.py`. `charter.activation.synthesizer.{manifest,provenance,reconcile,write_pipeline,synthesize_pipeline}`, `charter.activation.project_registration` and `specify_cli/cli/commands/charter/_fresh_doctrine.py` then import them from offering, an allowed direction. Each function keeps one definition and its `# noqa: TID251 - production raw SHA-256 owner`. `pack_manifest` switches `canonical_yaml` to `charter.offering.yaml_utils.canonical_yaml`. Check byte-identity: both functions must produce the same bytes. The existing `test_counts_derivation` and the manifest hash tests prove it.
2. **`pack_manifest.absorb_synthesis_manifest(manifest: SynthesisManifest)`.** Its only callers are tests (`tests/doctrine/test_charter_profile_absorption.py`), and it is dead-symbol allowlisted. Move it into `charter.activation.synthesizer.manifest`, which then imports `PackManifest` from offering (allowed). The alternative is to type it against a `Protocol` and drop the import, but the gate also counts `TYPE_CHECKING` imports because it uses a full `ast.walk`.
3. **`pack_lineage` → `charter.activation.org_extends.resolve_extends_order`.** `org_extends.py` is pure: it imports only `collections.abc`. Move it to `charter/offering/packs/extends.py`, the one resolver, which preserves the single-source rule of `test_pack_lineage_no_parallel_resolver.py`. `org_charter`, now in activation, imports it from offering. Update `tests/charter/test_org_extends.py` and the guardrail's docstring and target path.
4. **`OrgCharterPolicy` used by `pack_validator._validate_org_charter` (l.1678) and `pack_assembler._merge_org_charters_to_output` (l.665).** Both sit inside `try/except ModuleNotFoundError` guards that date from before WP09 and are now dead. `OrgCharterPolicy` cannot move to offering cheaply, because its `activations: list[ActivationEntry]` field drags in `charter.activation.activations`. The minimal fix keeps org charter composition in activation, as the ruling intends:
   - Move the two org-charter steps into `charter.activation.org_charter`, as `validate_org_charter_file(path) -> list[ValidationIssue]` and `merge_org_charter_files(paths, output_dir)`. Delete the dead `ModuleNotFoundError` fallbacks.
   - `pack_validator.validate_pack(...)` and `pack_assembler.assemble(...)` in offering accept an optional hook (`org_charter_check` / `org_charter_merge`), or return the list of `org-charter.yaml` paths for the caller to handle.
   - Add one composing entry point in activation (for example `charter.activation.org_charter.validate_pack_with_org_charter`). The CLI and `charter.packs` call it, so no caller can silently skip the org-charter leg. Pin that with a test.
   - The alternative is a deviation from ruling 9: place `pack_validator` and `pack_assembler` under `charter.activation`, because they *compose* org charters, and keep only descriptor, manifest, built-in manifest and lineage in offering. Raise this with the owner only if the hook split proves larger than about 100 lines.
5. **`org_charter` → `specify_cli.cli.commands.charter._layer_roots` (lazy ×2).** `_layer_roots.py` (85 lines) imports only `charter.drg.resolve_org_roots` and `resolve_existing_org_roots`, so it has no blocker. Move it to `src/charter/activation/layer_roots.py` with `resolve_layer_roots`, `resolve_org_root_chain`, and the FR-016 project root via the kernel constant (Part B). Inside charter it imports `charter.offering.drg.org_pack_config` directly; the "go through the `charter.drg` proxy" comment applies only to `specify_cli` and runtime.
   - `src` importers to repoint: `cli/commands/charter/{_cascade_shared, _resynthesis_preflight, activate, deactivate (×2), interview, list_cmd}.py` and `doctrine/org_charter.py`. Docstring-only mentions sit in `charter/activation/pack_manager.py:337,349,422,465` and `charter/offering/missions/mission_type_repository.py:383`.
   - Test importers: `tests/charter/test_mission_type_path_layout_ssot.py`, `test_pack_manager.py`, `test_pack_manager_catalog.py`; `tests/specify_cli/cli/commands/charter/test_activation_layout.py`, `test_org_cascade_chain.py` (×3).
   - This also clears the way for C-007's effective-set seam (FR-015) to live in `charter`.
6. **`pack_assembler` → `snapshot.write_pack_manifest` + `sources.protocol.FetchResult`.** `write_pack_manifest` (snapshot l.454) relies only on pure helpers: `_strip_credentials`, `_safe_urlsplit`, `_source_uses_query`, `_source_fingerprint`, `_snapshot_sha256`, `_iso_now` (`kernel.clock`), `_manifest_artifact_counts` and `_count_artifacts`, with no network or git.
   - Move it and its helpers into `charter.offering.packs.pack_manifest`, which already owns `finalize_pack_manifest` and `dump_pack_manifest_bytes`.
   - Change its signature to primitives: `local_path, *, pack_version, etag, source_url, source_type`.
   - `FetchResult` and the `OrgDoctrineSource` protocol (renamed per FR-010, for example `CharterPackSource`) stay in `specify_cli.charter_packs.sources.protocol`. `snapshot.py` unpacks `FetchResult` when it calls the writer.
   - Watch `tests/kernel/test_byte_identity_mapping.py`, which pins `specify_cli.doctrine.snapshot._iso_now#fetched_at` as a key, and `test_clock_*`.
7. **Adapter reaches into `charter.offering` once the exemption is deleted.**
   - `api_source.py:25` imports `CORE_KIND_PLURALS` from `charter.offering.artifact_kinds`. Add it to the `charter.drg` facade, which already re-exports `ArtifactKind`.
   - `snapshot.py:449` imports `resolve_relative_path_within_root` from `charter.offering.drg.org_pack_config`. Add it to `charter.drg` next to `resolve_org_roots`.
   - `snapshot.py:470/494` imports `pack_manifest` functions. Route them through `charter.packs`.
8. **`specify_cli` consumers of the pack model** need the **`charter.packs` facade** (object-identity re-exports, the census's FACADE-ONLY door, like `charter.drg`). That is not a C-001 alias: it is the canonical public door and keeps no old name alive.
   - `cli/commands/doctrine.py` (`builtin_manifest`, `pack_validator`, `pack_assembler`), `_doctrine_collect.py` (`pack_assembler`) and `drg_writers/registry.py` all switch to it.
   - The registry imports the module and reads the private `_document_dict`. Either expose a public `pack_document_dict` from `charter.packs`, or keep the registry's `name=` string tracking the real `__module__`. `test_drg_writer_discovery.registered_writer_qualnames` cross-references `module.qualname`, so the name becomes `charter.offering.packs.pack_assembler._document_dict`.

### A.4 Every gate, census, allowlist, `pyproject.toml` entry and roster that names the old package

| File : line | What it holds | What it must become |
|---|---|---|
| `tests/architectural/test_doctrine_census.py:80, 377-380` | `EXEMPT_MANAGEMENT_SURFACE = {"src/specify_cli/doctrine"}`; `test_management_surface_is_frozen` asserts the set and `is_dir()` | Empty `frozenset()`. Rewrite the frozen test to assert emptiness and the directory's absence (FR-010: "removed, not moved"). Docstrings at l.18 and l.179 need updating. |
| `tests/architectural/test_runtime_charter_doctrine_boundary.py:30-45` | `_EXEMPT_SUBPACKAGE = src/specify_cli/doctrine`, `_is_exempt_subpackage` | Delete the exemption and the predicate. Do not point it at `specify_cli/charter_packs`. |
| same, l.141-155, 386-433 | `_LAUNDERING_BASELINE`, `test_source_side_no_new_doctrine_laundering`, `test_config_conduit_is_closed` (asserts `"src/specify_cli/doctrine/config.py" not in actual`) | The source-side laundering scan is scoped to the old package. Retarget it to "no `src/specify_cli/**` module lists a `charter.offering`-origin symbol in `__all__`", or delete it with the package. Delete the `config.py` closure-proof, since the module is gone. |
| `tests/architectural/_owned_checkout_scan.py:44,100` | `ORG_PACK_MODULE_PATHS` includes `"src/specify_cli/doctrine/"` (the `effective_root` concept exemption) | Replace with `"src/specify_cli/charter_packs/"`, needed only if `snapshot.py` or `sources/*` still call `OrgPackConfig.effective_root`. `src/charter/` already covers the charter-bound modules. Fix the docstring in `test_owned_checkout_single_authority.py:29`. |
| `tests/architectural/test_owned_checkout_gate_selftest.py:258` | synthetic rel `src/specify_cli/doctrine/loader.py` | Rename the synthetic path to `src/specify_cli/charter_packs/loader.py`, since it must still sit inside the exemption. |
| `tests/architectural/test_egress_consent_boundary.py:575,580` | `Allowance` keys `specify_cli/doctrine/sources/{api,https}_source.py` | `specify_cli/charter_packs/sources/{api,https}_source.py`. Notes reword "doctrine content" to "charter pack content". |
| `tests/architectural/test_destructive_op_routing.py:179` | `CensusKey(rel="src/specify_cli/doctrine/sources/git_source.py", qualname="GitSource._update", ...)` | `rel="src/specify_cli/charter_packs/sources/git_source.py"`. The `token_line` stays, unless the class rename touches the line. |
| `tests/architectural/test_mutation_ownership_routing.py:130-131, 296-328` | `_GIT_SOURCE_PY = SPECIFY_CLI_ROOT/"doctrine"/"sources"/"git_source.py"`, `_GIT_SOURCE_REL`, 4 rel entries | `.../"charter_packs"/"sources"/...` |
| `tests/architectural/test_charter_sole_door_agent_profile_repository.py:199` | `ContentDescriptor(rel_path="src/specify_cli/doctrine/pack_validator.py", qualname="_check_profile_skipped_diagnostics", ...)` | **Delete.** `src/charter/offering/` is already exempt (l.52-56), so the descriptor goes stale. |
| `tests/architectural/test_no_dead_modules.py:455-464` | allowlist `specify_cli.doctrine.pack_descriptor`, `specify_cli.doctrine.pack_lineage` | `charter.offering.packs.pack_descriptor`, `charter.offering.packs.pack_lineage`. The count is unchanged. |
| `tests/architectural/_baselines.yaml:61-62` | `category` justification comment naming those two modules | Reword the comment. The count stays at 2. |
| `tests/architectural/dead_symbol_allowlist.yaml:407-519, 722-734, 984-987, 1451` | 25 entries keyed `module: specify_cli.doctrine.{builtin_manifest, pack_lineage, pack_manifest, org_charter, pack_assembler, pack_descriptor}` | Re-key to the new dotted paths, keeping each `symbol` unless the symbol itself is renamed. Entries for `absorb_synthesis_manifest` move with it to `charter.activation.synthesizer.manifest`. |
| `tests/architectural/test_pack_lineage_no_parallel_resolver.py:44` | `_PACK_MODULES_ROOT = src/specify_cli/doctrine` | `src/charter/offering/packs`. Its "the one resolver" target becomes `charter.offering.packs.extends` (A.3 #3). |
| `tests/architectural/test_pack_manifest_no_author_edit.py:13,42` | `from specify_cli.doctrine.builtin_manifest import ...` | `from charter.offering.packs.builtin_manifest import ...` (tests may import offering directly). |
| `tests/architectural/test_kind_table_derivation.py:23` | `from specify_cli.doctrine.org_charter import REQUIRED_KIND_FIELDS, OrgCharterPolicy` | `from charter.activation.org_charter import ...` |
| `tests/architectural/test_drg_writer_discovery.py:124` | docstring example path | Reword. The scan is over `src`, so the move is picked up automatically. |
| `tests/architectural/test_charter_kind_vocabulary_single_authority.py:27`, `test_charter_sole_door_resolver_imports.py:52` | docstrings | Reword. |
| `tests/architectural/test_charter_offering_does_not_import_activation.py` | not named, but **newly applies** to the six offering-bound modules | Must stay green: the A.3 #1-#4 fixes are the precondition. |
| `tests/architectural/test_charter_no_specify_cli_import.py` | not named, newly applies to the 9 charter-bound modules | Green after A.3 #5. |
| `tests/architectural/test_runtime_charter_doctrine_boundary.py` lazy ratchet (`_LAZY_BASELINE_ALLOWLIST`) | not named; would **grow** if `specify_cli` callers import `charter.offering.packs.*` directly | Must not grow (NFR-002). Use the `charter.packs` facade (A.3 #8). |
| `tests/architectural/_gate_coverage.py:2263` | `"doctrine": ("governance", "misc", ("tests/specify_cli/doctrine",))` | Key `"charter_packs"`, cone `("tests/specify_cli/charter_packs",)`. Charter-side tests ride the existing charter and doctrine cones. |
| `tests/architectural/_interpreter_shard_roster.py:331` | `"tests/specify_cli/doctrine"` | `"tests/specify_cli/charter_packs"` |
| `tests/architectural/ci_topology_census.json:85-91` | `{"dir": "doctrine", "cone_roots": ["tests/specify_cli/doctrine"], ...}` | `{"dir": "charter_packs", "cone_roots": ["tests/specify_cli/charter_packs"], ...}`. Must stay bijective with `_gate_coverage`. |
| `.github/ci-module-registry.yml:637` | `- tests/specify_cli/doctrine` | `- tests/specify_cli/charter_packs` |
| `.github/workflows/ci-nightly.yml:774` | `tests/specify_cli/doctrine` in the fast-tier dir list | `tests/specify_cli/charter_packs` |
| `.github/ci-foreign-coverage-baseline.json:71` | `"specify_cli.doctrine.template_render"` (shrink-only set) | `"specify_cli.charter_packs.template_render"`. A rename is not a new member under the ratchet, but confirm with `scripts/ci/coverage_guard_lib.py`, or drop the entry if the moved tests now import it directly. |
| `pyproject.toml:575-583` (`[tool.ruff.format].exclude`) | 9 entries: `src/specify_cli/doctrine/{builtin_manifest, org_charter_loader, pack_assembler, pack_lineage, pack_manifest, pack_validator, snapshot, sources/api_source, sources/https_source}.py` | Rename in place to the new paths (the count stays 2808 under `test_ruff_format_exclude_ratchet.py`; `test_every_exclude_entry_exists_on_disk` forces it), **or** format the moved files and drop the entries (a shrink, preferred). The list is ordered, so place each new path at its sorted position. |
| `pyproject.toml:2014-2022` (same table) | 9 test entries under `tests/specify_cli/doctrine/` | Same: rename to the new test paths or format and drop. |
| `pyproject.toml` wheel `packages` (l.142), mypy overrides | not affected: `src/charter` and `src/specify_cli` are already packaged, and no mypy override names the package | none |
| `tests/review/test_pre_review_gate_engine.py:82` | fake routing fixture `"src/specify_cli/doctrine/**"` | Cosmetic. Rename for FR-018. |
| Docs / packs (FR-018 living surfaces) | `packs/built-in/assets/README.md:38` (`specify_cli.doctrine.pack_validator`); `packs/built-in/missions/mission-steps/software-dev/implement/prompt.md:177` (test path in prose); `docs/api/cli-commands.md`, `docs/configuration/yaml-libraries.md`, `docs/convergence/charter-fetch.md`, `docs/architecture/org-doctrine-layer.md`, `docs/development/docs-retrieval-index.yaml` | Reword. The pack edit triggers `regenerate-graph` (C-003). |

### A.5 Where the tests should go

| From `tests/specify_cli/doctrine/` | To |
|---|---|
| `test_pack_validator*.py` (3), `test_pack_assembler.py` | `tests/charter/packs/`, which is covered by `tests/charter` (owning-subsystem rule for `src/charter/offering/**`: `tests/charter` + `tests/doctrine`) |
| `test_org_charter*.py` (4), `test_missing_pack_policy.py`, `test_config.py` (registry half) | `tests/charter/activation/` (exists) |
| `test_sources*.py`, `test_snapshot.py`, `test_template_render_*.py`, `test_config.py` (`doctrine fetch` CLI half) | `tests/specify_cli/charter_packs/` |
| `test_collision_warnings.py` | Tests `charter.offering.base`, not this package. Move to `tests/doctrine/` (or `tests/charter/`). |

The existing pack-model tests under `tests/doctrine/` (`test_pack_lineage.py`, `test_pack_id_identity.py`, `test_pack_manifest_schema.py`, `test_builtin_manifest.py`, `test_counts_derivation.py`, `test_pack_version_relocation.py`, `test_charter_profile_absorption.py`) need only import changes.

### A.6 Move order (every gate green after each step)

| Step | Change | Gates touched in the same commit |
|---|---|---|
| 0a | Move `hash_content_bytes` and `hash_manifest_payload` into offering. Repoint activation synthesizer, `project_registration`, `_fresh_doctrine` and both doctrine manifest modules. Move `absorb_synthesis_manifest` into `charter.activation.synthesizer.manifest`. | dead-symbol allowlist (absorb), TID251 (one owner) |
| 0b | Create `charter/offering/packs/__init__.py` and move `org_extends.py` → `offering/packs/extends.py`. Repoint `org_charter` and `pack_lineage`. | `test_pack_lineage_no_parallel_resolver` (resolver target), `tests/charter/test_org_extends.py` |
| 0c | Move `_layer_roots.py` → `charter/activation/layer_roots.py`. Repoint the 8 `src` and 5 test importers. | none named; `test_charter_no_specify_cli_import` unchanged (charter does not import it yet) |
| 0d | Add `charter.drg` exports `CORE_KIND_PLURALS` and `resolve_relative_path_within_root`. Repoint `api_source` and `snapshot`, still under the exemption. Create the `charter/packs.py` facade (empty or growing). | `test_doctrine_public_surface.py` / `test_charter_facades_reexport_doctrine.py`, if they pin the facade export sets |
| 1 | **Leaves**: `pack_descriptor` and `pack_lineage` → `charter.offering.packs`. | `test_no_dead_modules` allowlist, `_baselines.yaml` comment, dead-symbol allowlist (pack_lineage ×5, pack_descriptor ×1), ruff exclude (pack_lineage) |
| 2 | `pack_manifest` (with the primitive-signature `write_pack_manifest`, A.3 #6) and `builtin_manifest` → `charter.offering.packs`. `snapshot` calls the writer through `charter.packs`. CLI `builtin_manifest` use goes through `charter.packs`. | dead-symbol allowlist (manifest ×12), ruff exclude ×2, `test_pack_manifest_no_author_edit`, `test_byte_identity_mapping` key, `test_charter_offering_does_not_import_activation` |
| 3 | `org_charter` and `org_charter_loader` → `charter.activation`. Fold `config.assert_pack_local_paths_exist` into `org_charter`. Add `validate_org_charter_file` and `merge_org_charter_files` (A.3 #4). Repoint the 6 `src` and about 15 test importers, plus 3 patch strings. Prerequisite: FR-015 has removed the `default_pack` dependency, or the move carries it, which is still legal. | `test_kind_table_derivation`, dead-symbol allowlist (org_charter ×5), ruff exclude (loader), `test_charter_no_specify_cli_import` (now covers it) |
| 4 | `pack_validator` and `pack_assembler` → `charter.offering.packs` with org-charter hooks. Add the activation composing entry. Repoint the CLI, `_doctrine_collect` and `drg_writers/registry.py` through `charter.packs`. | sole-door descriptor delete, `test_drg_writer_discovery`/registry name, dead-symbol allowlist (assembler ×2), ruff exclude ×2, the offering→activation gate |
| 5 | `sources/`, `snapshot`, `template_render/` → `specify_cli.charter_packs` (rename `OrgDoctrineSource` here or in the rename WP). | egress allowances, destructive-op `CensusKey.rel`, mutation-ownership paths, `_owned_checkout_scan` path, foreign-coverage baseline, ruff exclude ×3 |
| 6 | Delete `src/specify_cli/doctrine/` (including `__init__`). Remove both exemptions (census and boundary) and retire the laundering tests. Move `tests/specify_cli/doctrine/*` per A.5 and update the 5 roster files together (`_gate_coverage`, `_interpreter_shard_roster`, `ci_topology_census.json`, `ci-module-registry.yml`, `ci-nightly.yml`) plus the 9 test-path ruff exclude entries. | `test_doctrine_census`, `test_runtime_charter_doctrine_boundary`, `test_module_shard_registry` / `test_gate_selection_authority` / `test_ci_collection_completeness` (roster bijection), `test_ruff_format_exclude_ratchet` |

Steps 0a-0d can run in parallel; steps 1-5 run in order. Step 6 must be atomic, because the roster files are cross-checked. For gate runs, use the specific files named per step, not the bare `tests/architectural/` directory (NO_FULL_HEAVY_SUITES_IN_MISSION).

---

## Part B: the project pack root (FR-016)

### B.1 Sites that build or read the `.kittify/doctrine` project root

A site counts if it is a path-construction site (a `/` join, `Path()` or `joinpath()` argument, filename tuple, constant, or f-string) whose `"doctrine"` segment sits under `<repo>/.kittify`, directly or through `layer_roots["project"]`, which today is `.kittify` itself.

**WRITE / BOTH (12 sites, the ones the testability squad's A1 flagged)**

| Site | Class | Note |
|---|---|---|
| `charter/activation/synthesizer/write_pipeline.py:62,70,184,520,560,604` (`_KITTIFY_DIRNAME` + `_DOCTRINE_DIRNAME = LEGACY_DOCTRINE_DIRNAME`) | WRITE | Promotes staged content and `graph.yaml` into the live tree |
| `charter/activation/synthesizer/path_guard.py:37` (`_DEFAULT_ALLOWLIST ".kittify/doctrine"`) | WRITE | Write allowlist; if not flipped, every write is refused |
| `charter/activation/synthesizer/manifest.py:38` (`_ARTIFACT_PATH_PREFIX`) | BOTH | Recorded in `synthesis-manifest.yaml` and validated on read, so persisted state needs FR-012 to rewrite it |
| `charter/activation/synthesizer/reconcile.py:79,315` (`_DOCTRINE_DIRNAME = ".kittify"`, the CR-07 split-literal trap; f-string `f"{_DOCTRINE_DIRNAME}/{LEGACY_DOCTRINE_DIRNAME}/..."`) and `:612` (`resolve_doctrine_read_root`) | BOTH | |
| `charter/activation/project_registration.py:119` (read existing graph), `:297` (`.kittify/doctrine/graph.yaml` write) | BOTH | |
| `specify_cli/cli/commands/charter/_fresh_doctrine.py:108` (write), `:147` (plan), `:157` (delete `graph.yaml`), `:200` (`PROVENANCE.md`) | BOTH | |
| `specify_cli/doctrine_synthesizer/apply.py:195` (`_DOCTRINE_BASE`; `.flags`, kind dirs) | WRITE | Retrospective proposal applier |
| `specify_cli/cli/commands/doctrine.py:650` (`_resolve_scaffold_root`, `new` default target) | WRITE | Moves with the command rename |
| `specify_cli/cli/commands/charter/_synthesis.py:305,334` (planned artifact paths in JSON), `:750` (`_SYNTHESIS_ARTIFACT_PATHS`, fed to `safe_commit_recipe`) | BOTH | Paths are reported and committed |
| `charter/bundle.py:66` (`DOCTRINE_DIR`); consumers `charter/bundle.py:309`, `specify_cli/charter_runtime/freshness/computer.py:337-349` | READ, but this is the public constant | Retire it for the kernel constant |

**READ (44 sites)**

| Area | Sites |
|---|---|
| Synthesizer (project DRG reads) | `synthesizer/project_drg.py:460`; `resynthesize_pipeline.py:370,453,482` |
| Activation scans and layer discovery | `activation/_drg_helpers.py:196`; `_doctrine_paths.py:30` (`_PROJECT_ROOT_CANDIDATES`, used by `doctrine_service_builder`, `language_vocabulary`, `context_renderers/template_include`, `compact`, `cli/commands/_doctrine_asset`); `kind_vocabulary.py:295` (`root/"doctrine"/PROJECT_KIND_DIRS`); `pack_manager.py:288` (same shape); `mission_type_profile_repository.py:52` (`_PROJECT_OVERRIDE_PARTS`) |
| Offering | `offering/drg/project_scan.py:73,200,205`; `offering/drg/override_policy.py:70` (`POLICY_RELPATH .kittify/doctrine/replaceable-builtins.yaml`; also displayed by `_doctrine_collect.py:928-931`) |
| Layer roots | `cli/commands/charter/_layer_roots.py:21` (marker `.kittify/doctrine` is a dir, then `roots["project"] = .kittify`); consumer `list_cmd.py:74` |
| Runtime and glossary | `runtime/next/runtime_bridge_composition.py:286`; `glossary/entity_pages.py:72` |
| `specify_cli` readers | `analysis_inputs.py:200`; `calibration/walker.py:347,395` (overlays); `charter_runtime/lint/_drg.py:51`; `charter_runtime/preflight/runner.py:129,787` (dirty-scope prefixes); `cli/commands/_doctrine_collect.py:244,352,616,1175`; `cli/commands/charter/_status_collectors.py:211`; `cli/commands/profiles_cmd.py:105`; `mission_loader/command.py:274`; `mission_step_contracts/executor.py:176`; `review/gate_bindings.py:74` (`_PROJECT_CONTRACTS_SUBPATH`); `skills/catalog.py:60` (`_PROJECT_SKILLS_DIR`); `tool_surface/providers/agent_profiles.py:578` (fingerprint inputs, which also list a bare `"doctrine"`) |
| Kernel | `kernel/doctrine_root.py` (`LEGACY_DOCTRINE_DIRNAME`, `CANONICAL_DOCTRINE_DIRNAME`, `resolve_doctrine_read_root` + warning): **replace it**. Its users are `write_pipeline`, `reconcile`, `doctrine_synthesizer/apply.py` and `tests/kernel/test_doctrine_root.py`. |

**Persisted contract and ignore rules**

- **State contract.** `src/specify_cli/state/contract.py:592-603` holds `StateSurface(name="project_doctrine_graph", path_pattern=".kittify/doctrine/graph.yaml", ...)`. It becomes `name="project_pack_graph"` with a pattern built from the kernel constant. The `name` is a contract key, so check `tests/specify_cli/state/` and the state-contract docs.
- **This repository's `.gitignore:97-114`** has `.kittify/doctrine/**` plus negations for `directive/`, `tactic/`, `styleguide/`, `procedure/`, `overlays/` and `graph.yaml`. Rewrite it for `.kittify/charter-packs/`. The consumer squad already notes that `mission_types/`, `agent_profiles/`, `mission_step_contracts/` and `skills/` are not re-included today, so decide whether the new rule is all-tracked.
- **Consumer `.gitignore` rewriting.** No src writer emits `.kittify/doctrine` gitignore rules; the grep is clean. FR-012 rewrites only this repository's own file plus whatever the migration owns.
- **Persisted path strings FR-012 must rewrite.** `synthesis-manifest.yaml` `artifacts[].path`, provenance sidecars, and `skills-manifest.json` `source_ref` (`skills/manifest.py:43`), as already listed by the consumer squad.

**Not the project root.** Leave these out of the FR-016 gate or allowlist them by reason:

- **Staging subtree.** `synthesizer/staging.py:112,145`, `validation_gate.py:184`, `project_drg.py:549` and `write_pipeline.py:600` use `<staging>/doctrine/...` under `.kittify/charter/.staging/`. Recommendation: rename it to the same kernel segment, so promotion stays a 1:1 mapping and the gate can stay strict.
- **Org nested layout.** `kind_vocabulary.py:297` (`root/"doctrine"/plural/layer`) and `_doctrine_paths.py:32` (`"doctrine"` flat fallback) cover the nested `<pack>/doctrine/<plural>/<layer>` layout. This is a "doctrine" segment under an org or built-in root, not `.kittify`. FR-018 / FR-011 must decide whether that legacy layout survives.
- **Dead fallbacks.** `upgrade/migrations/m_2_1_2_*.py` and `m_3_2_0rc{30,35}_*.py` contain `parents[3]/"doctrine"/"skills"`, fallbacks that point at the deleted `src/doctrine/`. These are frozen migrations; the gate needs a by-file exemption, or the dead fallbacks get deleted.
- **Config keys, not paths.** `sync.py:244`, `org_pack_config.py:57`, `tracker/config.py:39` and `_doctrine_collect.py:1088` (`"doctrine"` as a legacy config key) are FR-011 territory. `retrospective/schema.py:490` (`ProposalCategory` literal) is not a path either.

### B.2 Pack-relative path literals

| Literal | Spelled at |
|---|---|
| `drg/fragment.yaml` (as `/ "drg" / "fragment.yaml"`) | `charter/activation/drg_activation.py:163`; `charter/activation/_drg_helpers.py:177`; `charter/offering/drg/org_pack_loader.py:536`; `specify_cli/doctrine/pack_validator.py:584` (+ `:1422`, `:1546` as `drg_dir / "fragment.yaml"`); `specify_cli/cli/commands/doctrine.py:1030` (scaffold write); `specify_cli/mission_step_contracts/executor.py:583` |
| `org-charter.yaml` | `charter/activation/org_pack_discovery.py:158,269`; `specify_cli/doctrine/org_charter.py:426`; `org_charter_loader.py:68`; `pack_validator.py:1678`; `pack_assembler.py:672,685,695`; `specify_cli/cli/commands/_doctrine_collect.py:173`; `specify_cli/cli/commands/doctrine.py:1029` (scaffold write) |
| `pack-manifest.yaml` / `pack.yaml` (siblings of the pack descriptors) | `builtin_manifest.py:43`; `snapshot.py:357,468,582`; `pack_assembler.py:467,481`; `_doctrine_collect.py:94,141` |
| `presets/` | no live spelling yet (FR-001 to FR-004 add it) |
| `graph.yaml` (project overlay) | `_fresh_doctrine.py:157`, `project_registration.py:297`, `freshness/computer.py:342`, `write_pipeline` `_GRAPH_FILENAME`, `project_drg` `_GRAPH_FILENAME` |

### B.3 Proposed kernel module

The module replaces `src/kernel/doctrine_root.py` and deletes its legacy fallback and warning. The FR-012 migration keeps its own legacy literal, exempt by file.

```python
# src/kernel/charter_pack_paths.py
KITTIFY_DIRNAME = ".kittify"
PROJECT_PACK_DIRNAME = "charter-packs"
PROJECT_PACK_ROOT = Path(KITTIFY_DIRNAME, PROJECT_PACK_DIRNAME)   # repo-relative
PROJECT_PACK_ROOT_POSIX = PROJECT_PACK_ROOT.as_posix()          # for prefix checks / manifests / globs

DRG_DIRNAME = "drg"
DRG_FRAGMENT = Path(DRG_DIRNAME, "fragment.yaml")               # pack-relative
ORG_CHARTER_FILENAME = "org-charter.yaml"
PRESETS_DIRNAME = "presets"
PROJECT_GRAPH_FILENAME = "graph.yaml"                           # project-pack overlay

def project_pack_root(repo_root: Path) -> Path: ...             # repo_root / PROJECT_PACK_ROOT
def project_pack_path(repo_root: Path, *parts: str) -> Path: ...
def pack_drg_fragment(pack_root: Path) -> Path: ...
def pack_org_charter(pack_root: Path) -> Path: ...
def pack_presets_dir(pack_root: Path) -> Path: ...
```

- It lives in `kernel` because `charter.activation.synthesizer`, `charter.offering.drg.project_scan`, `runtime`, `glossary` and `specify_cli` all need it, and C-007 puts path constants in kernel. `kernel/README.md` and `test_kernel_*` gates apply: kernel imports nothing upward.
- **Layer-root contract change.** `charter.activation.layer_roots.resolve_layer_roots(...)["project"]` should return `project_pack_root(repo_root)`, not `.kittify`. Its consumers then drop the `/"doctrine"` join (`pack_manager.py:288`, `kind_vocabulary.py:295`, `list_cmd.py:74`). Without that change, the "no doctrine segment joined to `.kittify`" rule is unmeetable through the layer-root indirection.
- Kind subdirectory names (`PROJECT_KIND_DIRS`, `charter/offering/artifact_kinds.py:432`) stay in offering. They are pack-relative vocabulary, not root paths.
- **Root layout.** This is open from the architecture squad's B6. The kernel API above assumes the project layer is **one flat pack** at `.kittify/charter-packs/`. If it becomes a directory of packs (`.kittify/charter-packs/<name>/`), then `project_pack_root` takes a pack id. Settle this in plan before WP slicing.

### B.4 Proposed gate shape: `tests/architectural/test_charter_pack_path_authority.py`

Model it on `test_charter_path_literal_authority.py` (743 lines; AST path-construction contexts, a composite-key allowlist, a shrink-only baseline, a FLOOR and margin, a staleness twin-guard, and planted self-tests):

- **Authority:** `src/kernel/charter_pack_paths.py`, the only file allowed to spell the literals.
- **Contexts:** the four of the existing gate (a `/` `BinOp`, a `Path(...)` argument, a constant-assignment RHS, an element of a sequence literal), plus `joinpath(...)` arguments and `JoinedStr` parts. The CR-07 split-literal shapes in `reconcile.py:315` and `_synthesis.py:305` are f-strings, and the current gate does not see them.
- **Clause (a):** a `"doctrine"` segment in any path-construction context under `src/`. Resolve module-level `str` constant aliases, as `_module_level_charter_filename_aliases` does, so `_DOCTRINE_DIRNAME = ".kittify"` / `_DOCTRINE_DIRNAME = LEGACY_DOCTRINE_DIRNAME` cannot hide one. The strict "any segment" form is simpler and stronger than "after `.kittify`". It needs the B.1 non-project-root decisions, plus a closed **by-file** exemption list (the cutover migration module only, plus the frozen `m_2_1_2_*` / `m_3_2_0rc*` migrations if their dead fallbacks are not deleted).
- **Clause (b):** a re-spelling of `.kittify/charter-packs`, a `"charter-packs"` segment, `"org-charter.yaml"`, `"fragment.yaml"` or a `"presets"` segment in a path-construction context outside the authority. This forces consumers onto the constants and stops a second root from creeping back in.
- **Clause (c), non-Python surfaces:** assert `.gitignore` has no `.kittify/doctrine` rule and has the `.kittify/charter-packs` rules. Assert the `StateSurface` for the project graph builds its pattern from the kernel constant (import-and-compare).
- **Non-vacuity:** a scanned-file floor (≥ 1,000 `src` files, as the kind-vocabulary gate uses); a planted-literal `tmp_path` test per clause and shape (BinOp, tuple, f-string, alias-constant); and "allowlisting one literal does not waive the module".
- **Allowlist:** **empty** at landing (NFR-002), with the composite-key machinery kept so a future exception has to be argued.
- **Prose:** docstrings and message text are excluded structurally. The FR-018 vocabulary gate owns the `.kittify/doctrine` token in prose.

---

## Part C: sizing the FR-010 identifier rename

The counts are NAME tokens from `tokenize`, so strings and comments are excluded. "Doctrine-as-content" files under `src/charter/offering/` (YAML and Markdown) are excluded automatically, because only `.py` is scanned.

| Measure | `src/` | `tests/` |
|---|---|---|
| Identifiers containing `doctrine` (any case) | **1,087 tokens / 139 files / 111 distinct names** | 2,618 tokens / 471 files / 407 distinct |
| Capitalised `*Doctrine*` identifiers | 211 tokens / 55 files / 20 distinct | 421 tokens / 80 files / 46 distinct |
| `DoctrineService` (word grep, including strings and comments) | 181 lines / 42 files (52 NAME tokens / 15 files) | 347 lines / 77 files (184 tokens / 36 files) |
| Modules with "doctrine" in the file name (`src`, `.py`) | `activation/action_doctrine_bundle.py`, `activation/doctrine_service_builder.py`, `activation/_doctrine_paths.py`, `specify_cli/doctrine_service_factory.py`, `specify_cli/doctrine/` (the package-split WP), `specify_cli/doctrine_synthesizer/`, `cli/commands/{_doctrine_collect, _doctrine_asset, _doctrine_health, doctrine}.py`, `cli/commands/charter/_fresh_doctrine.py`, `kernel/doctrine_root.py` (replaced in FR-016), `upgrade/migrations/m_2_1_2_fix_charter_doctrine_skill.py`, `m_4_0_0rc5_retire_single_owner_doctrine_ids.py` (migration ids: keep, as historical) | `tests/doctrine/` (193 files; a directory name; see the note below) |

The most frequent `src` names are: `doctrine_root` 225 tokens / 32 files (mostly the built-in root parameter), `doctrine` 53 / 19 (mostly `specify_cli.doctrine` import paths, which disappear with the split), `DoctrineService` 52 / 15, `doctrine_selection` 45 / 5, `resolve_doctrine_root` 37 / 13, `doctrine_service` 31 / 6, `build_activation_aware_doctrine_service` 25 / 12, `BaseDoctrineRepository` 24 / 13, `DoctrineSelectionConfig` 21 / 7, `DoctrineHealthReport` 17 / 4, `_ActionDoctrineBundle` 16 / 5, `ActivationAwareDoctrineService` 16 / 5, `DoctrineCatalog` 16 / 4, `doctrine_service_builder` (module) 15 / 13, `OrgDoctrineSource` 11 / 4, `MissingDoctrinePackError` 4 / 3, `LegacyDoctrineRootWarning` / `LegacyOrgPackDoctrineKeyWarning` (deleted by FR-011, not renamed).

`src` tokens by subsystem (files / tokens): `charter/activation` 42 / 550 · `specify_cli/cli/commands` 26 / 250 · `charter/offering` 19 / 81 · `specify_cli/doctrine` 14 / 51 · `specify_cli/upgrade` 13 / 43 · `specify_cli/charter_runtime` 4 / 19 · `specify_cli/tool_surface` 6 / 18 · `charter/bundle.py` 1 / 15 · `specify_cli/doctrine_synthesizer` 2 / 13 · `kernel/doctrine_root.py` 1 / 11 · `specify_cli/invocation` 2 / 11 · `specify_cli/doctrine_service_factory.py` 1 / 6 · 8 others with 1 file each, ≤ 4 tokens. Tests by area: `tests/charter` 109 / 1,016 · `tests/doctrine` 193 / 713 · `tests/specify_cli` 78 / 465 · `tests/architectural` 33 / 188 · the remaining 58 files / 236.

### Proposed WP split (excluding the package split itself, which is Part A's own WP chain)

| WP | Scope | `src` files | Test files (approx.) | Key renames |
|---|---|---|---|---|
| **R1: offering, facades and kernel** (lands first, because downstream names hang off it) | `charter/offering/**/*.py`, `charter/{bundle,drg}.py`, `charter/hasher.py` neighbours | ~21 | ~60 (`tests/doctrine`, part of `tests/charter`) | `DoctrineService`, `BaseDoctrineRepository`, `DoctrineArtifactLoadError`, `DoctrineLayerCollisionWarning`, `DoctrineResolutionCycleError`, `bundle.DOCTRINE_DIR` (FR-016), `charter.drg` exports |
| **R2: activation** | `charter/activation/**` (42 files, 550 tokens, the largest) | ~42 | ~110 (`tests/charter`, `tests/charter/activation`, `tests/charter/synthesizer`) | `doctrine_service_builder` module, `ActivationAwareDoctrineService`, `RawDoctrineService`, `build_activation_aware_doctrine_service`, `DoctrineCatalog` / `load_doctrine_catalog` / `resolve_doctrine_root`, `_ActionDoctrineBundle` / `action_doctrine_bundle`, `_doctrine_paths`, `DoctrineSelectionConfig` / `doctrine_selection`, `doctrine_root` params. Split R2 further (R2a catalog and service builder; R2b synthesizer and bundle) if one WP exceeds about 30 files. |
| **R3: `specify_cli` CLI surface** | `cli/commands/**` (26), `doctrine_service_factory.py`, `charter_runtime/**` (4), `tool_surface/**` (6), `invocation/**` (2), `runtime`, `template`, `skills`, `drg_writers`, `retrospective` | ~45 | ~90 (`tests/specify_cli`, `tests/cli`, `tests/integration`, `tests/runtime`) | module renames `_doctrine_collect` / `_doctrine_health` / `_doctrine_asset` / `_fresh_doctrine` / `doctrine.py` (with FR-006/FR-007 command moves), `DoctrineHealthReport`, `doctrine_service` locals |
| **R4: migrations, synthesizer applier and gates** | `upgrade/migrations/**` (13; rename only non-historical identifiers, and keep migration ids and class names that are recorded in `.kittify/migrations`), `doctrine_synthesizer/` package (2) → `charter_pack_synthesizer` or similar, plus `tests/architectural/**` (33 files / 188 tokens) census and gate renames | ~15 | ~45 | `doctrine_synthesizer`, `_LazyDoctrineVisitor`, census module names (`test_doctrine_census` stays named in NFR-002, so do not rename the files the spec names) |

Totals: about 123 `src` files plus the 14 split files ≈ 139, which matches the scan. About 300 test files carry identifier changes. `tests/doctrine/` (193 files) is a directory name. Renaming the directory, for example to `tests/charter/offering/`, is a separate decision: it touches every roster in A.4, it is not required by FR-010's identifier scope, and the CLAUDE.md test-tree mapping for `src/charter/offering/**` names it. Recommend leaving it out of scope, or giving it its own WP after R1-R4.

Ordering: R1 → R2 → R3, with R4 in parallel to R3. The Part A split (steps 0-6) should land **before** R1-R3, so the renames operate on the final module layout, and **after** FR-015, which removes the `org_charter` → `default_pack` edge.
