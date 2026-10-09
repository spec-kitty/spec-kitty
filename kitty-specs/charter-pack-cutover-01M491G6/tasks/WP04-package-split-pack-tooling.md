---
work_package_id: WP04
title: Package split I — pack model and tooling to charter.offering.packs
dependencies:
- WP02
- WP03
requirement_refs:
- FR-010
- C-007
planning_base_branch: issue-3732-charter-pack-rename
merge_target_branch: issue-3732-charter-pack-rename
branch_strategy: Planning artifacts for this mission were generated on issue-3732-charter-pack-rename. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-3732-charter-pack-rename unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-pack-cutover-01M491G6
base_commit: da7b1a39eb4fcec3dc15bb3bc53263711ca84be1
created_at: '2026-10-07T04:56:45.163702+00:00'
subtasks:
- T021
- T022
- T023
- T024
- T025
phase: Phase 1 - Foundations (paths, package split)
history:
- at: '2026-10-06T19:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: architect-alphonso
authoritative_surface: src/charter/offering/packs/
create_intent:
- src/charter/offering/packs/__init__.py
- src/charter/offering/packs/hashing.py
- src/charter/offering/packs/extends.py
- src/charter/offering/packs/pack_descriptor.py
- src/charter/offering/packs/pack_lineage.py
- src/charter/offering/packs/pack_manifest.py
- src/charter/offering/packs/builtin_manifest.py
- src/charter/offering/packs/pack_validator.py
- src/charter/offering/packs/pack_assembler.py
- src/charter/packs.py
- tests/charter/packs/__init__.py
- tests/charter/packs/test_pack_validator.py
- tests/charter/packs/test_pack_validator_fragment_finding.py
- tests/charter/packs/test_pack_validator_kind_derivation.py
- tests/charter/packs/test_pack_assembler.py
- tests/charter/packs/test_hashing.py
- tests/charter/packs/test_pack_manifest_writer.py
- tests/charter/packs/test_charter_packs_facade.py
execution_mode: code_change
owned_files:
- src/charter/offering/packs/__init__.py
- src/charter/offering/packs/hashing.py
- src/charter/offering/packs/extends.py
- src/charter/offering/packs/pack_descriptor.py
- src/charter/offering/packs/pack_lineage.py
- src/charter/offering/packs/pack_manifest.py
- src/charter/offering/packs/builtin_manifest.py
- src/charter/offering/packs/pack_validator.py
- src/charter/offering/packs/pack_assembler.py
- src/charter/activation/org_extends.py
- src/specify_cli/doctrine/pack_descriptor.py
- src/specify_cli/doctrine/pack_lineage.py
- src/specify_cli/doctrine/pack_manifest.py
- src/specify_cli/doctrine/builtin_manifest.py
- src/specify_cli/doctrine/pack_validator.py
- src/specify_cli/doctrine/pack_assembler.py
- src/specify_cli/doctrine/org_charter.py
- src/specify_cli/doctrine/snapshot.py
- src/specify_cli/doctrine/sources/api_source.py
- src/charter/packs.py
- src/charter/drg.py
- src/charter/__init__.py
- src/specify_cli/drg_writers/registry.py
- pyproject.toml
- tests/charter/packs/**
- tests/specify_cli/doctrine/test_pack_validator.py
- tests/specify_cli/doctrine/test_pack_validator_fragment_finding.py
- tests/specify_cli/doctrine/test_pack_validator_kind_derivation.py
- tests/specify_cli/doctrine/test_pack_assembler.py
- tests/specify_cli/doctrine/test_snapshot.py
- tests/charter/test_org_extends.py
- tests/doctrine/test_pack_lineage.py
- tests/doctrine/test_pack_id_identity.py
- tests/doctrine/test_pack_manifest_schema.py
- tests/doctrine/test_builtin_manifest.py
- tests/doctrine/test_counts_derivation.py
- tests/doctrine/test_pack_version_relocation.py
- tests/doctrine/test_charter_profile_absorption.py
- tests/doctrine/test_org_pack_augmentation.py
- tests/doctrine/test_template_asset_e2e.py
- tests/doctrine/drg/test_org_fragment_validation.py
- tests/doctrine/drg/test_sharding_silent_degrade.py
- tests/integration/test_quickstart_end_to_end.py
- tests/kernel/test_byte_identity_mapping.py
- tests/architectural/test_pack_lineage_no_parallel_resolver.py
- tests/architectural/test_pack_manifest_no_author_edit.py
- tests/architectural/test_no_dead_modules.py
- tests/architectural/_baselines.yaml
- tests/architectural/test_charter_sole_door_agent_profile_repository.py
- tests/architectural/test_drg_writer_discovery.py
- tests/architectural/test_charter_facades_reexport_doctrine.py
- tests/architectural/test_doctrine_public_surface.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Package split I — pack model and tooling to `charter.offering.packs`

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

After WP18 lands, the `/ad-hoc-profile-load` skill is deleted: load profiles with `spk-charter-profile-load` instead (use whichever exists in your checkout).

- **Profile**: `architect-alphonso`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If the profile cannot be loaded, run `spec-kitty agent profile list` and pick the best match for `task_type: implement` on `src/charter/offering/packs/`.

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?** Check `review_ref` in the event log (`spec-kitty agent tasks status`) or the Activity Log below.
- Address every feedback item before you finish; log each fix in the Activity Log.

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers on code blocks.

## Objectives & Success Criteria

1. The pack model and tooling (descriptor, lineage, manifest, built-in manifest, validator, assembler) live in `src/charter/offering/packs/` (OD-9), with no import of `charter.activation` or `specify_cli` from that package.
2. `specify_cli` reaches them only through a new **`charter.packs` facade** (object-identity re-exports, like `charter.drg`), so the boundary gates close without growing a lazy baseline (NFR-002).
3. `charter.drg` additionally exports `CORE_KIND_PLURALS` and `resolve_relative_path_within_root`.
4. Every gate named for this half of the split is green; the moved modules' tests are green at their new homes.
5. WP01's FR-010 tests pending on WP04 are green.

## ⚠️ Start condition (read before claiming)

`src/charter/activation/synthesizer/manifest.py`, `src/charter/activation/project_registration.py` and `src/specify_cli/cli/commands/doctrine.py` are owned by **WP03** (write-side cutover) and edited here by steps 0a, 2 and 4. WP04 depends on WP02 and WP03, so the two never run in parallel; your edits to those three files are then mechanical follow-ups on a completed upstream WP (tasks.md rule), logged in the Activity Log.

## Context & Constraints

- Read: `spec.md` FR-010, OD-9, C-001, C-007, NFR-002; `research/package-split-and-paths.md` **Part A in full** (A.1 inventory, A.3 blockers, A.4 gate table, A.5 test homes, A.6 move order).
- The gate that drives the prep moves: `tests/architectural/test_charter_offering_does_not_import_activation.py` walks the full AST (lazy and `TYPE_CHECKING` imports count).
- `tests/architectural/test_charter_no_specify_cli_import.py` newly applies to every module moved into `charter`.
- **No aliases (C-001)**: no module left at the old path, no `import X as X` re-export, no `try/except ImportError` fallback. The `charter.packs` facade is the canonical public door (research A.3 #8), not an alias: it keeps no old name alive.
- `src/charter/__init__.py:103-106` maps lazy exports to `charter.activation.org_extends`; repoint them to `charter.offering.packs.extends`. CLAUDE.md says changes to `__init__.py` need a version bump and a changelog entry: confirm with the orchestrator whether that rule covers `src/charter/__init__.py` (it was written for the CLI package) and record the answer; do not bump the version on your own.
- Code style: ruff, `ruff format`, mypy clean; complexity ≤ 15; no new suppressions. Moved files listed in `pyproject.toml` `[tool.ruff.format].exclude` (`:344` `org_extends.py`, `:575-583`) are preferably **formatted and dropped** from the exclude list (a shrink under `tests/architectural/test_ruff_format_exclude_ratchet.py`); otherwise rename the entry in place at its sorted position.

## Mechanical edits outside owned_files (log each in the Activity Log)

Import-path and key-only edits, behaviour unchanged, in files owned by completed upstream WPs (tasks.md rule): `src/charter/activation/synthesizer/manifest.py`, `src/charter/activation/project_registration.py`, `src/specify_cli/cli/commands/doctrine.py`, `tests/architectural/charter_pack_path_allowlist.yaml` (WP03); `src/specify_cli/cli/commands/_doctrine_collect.py`, `tests/architectural/dead_symbol_allowlist.yaml` (WP02). Docstring path references in unowned files: `src/charter/offering/assets/models.py:14`, `src/charter/offering/drg/org_pack_config.py:177`, `src/charter/offering/drg/org_pack_loader.py:150,286`.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on `issue-3732-charter-pack-rename`; completed changes merge back into `issue-3732-charter-pack-rename`.
- **Planning base branch**: `issue-3732-charter-pack-rename`
- **Merge target branch**: `issue-3732-charter-pack-rename`
- Lane: from `lanes.json` (filled by `spec-kitty agent mission finalize-tasks`).

## Red-first (C-006 / C-011)

First commit: delete the `pending_until("WP04", …)` markers in `tests/acceptance/charter_pack_cutover/test_package_split.py` (`test_fr010_pack_tooling_lives_in_charter_offering_packs`, `test_fr010_charter_packs_facade_exports`). Run them red, record, commit. Do not change their assertions.

## The move order (research/package-split-and-paths.md §A.6, verbatim)

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

**How this WP executes the table.** Step 0c is already done (WP02 T012). This WP does **0a, 0b, 0d, 1, 2 and 4**; WP05 does **3, 5 and 6**. Because tasks.md puts the validator/assembler move (step 4) here and the org-charter move (step 3) in WP05, step 4 runs **before** step 3. That is safe with one interim: the two org-charter step functions and the composing entries are added to `src/specify_cli/doctrine/org_charter.py` here (T022), and WP05 carries them to `charter.activation.org_charter` with the rest of the module. In this WP the `charter.packs` facade exports **only offering-side functions**; the CLI imports the two composing entries directly from `specify_cli.doctrine.org_charter`, and WP05 adds them to the facade once they live in `charter.activation`. Every gate stays green after each step. Steps 0a, 0b and 0d may run in any order; 1, 2, 4 run in order; one commit per step.

## Subtasks & Detailed Guidance

### Subtask T021 – Prep: hash helpers and `org_extends` to offering; `absorb_synthesis_manifest` to activation (steps 0a, 0b)

- **Purpose**: remove the offering→activation edges of `pack_manifest`, `builtin_manifest` and `pack_lineage` before they move (A.3 #1–#3).
- **Steps**:
  1. Create `src/charter/offering/packs/__init__.py` (docstring only; no re-exports).
  2. Create `src/charter/offering/packs/hashing.py` with `hash_manifest_payload(data, *, exclude_keys)` and `hash_content_bytes(raw)`, moved verbatim from `src/charter/activation/synthesizer/manifest.py:208-236` with their `# noqa: TID251 - production raw SHA-256 owner` comments (one definition each; TID251 keeps one owner). `hash_manifest_payload` uses `charter.offering.yaml_utils.canonical_yaml` (`yaml_utils.py:27`), which the synthesizer's `canonical_yaml` (`synthesize_pipeline.py:163`) delegates to; prove byte identity with the existing manifest-hash tests and `tests/doctrine/test_counts_derivation.py`.
  3. Repoint importers (only four at planning time: `grep -rn "hash_content_bytes\|hash_manifest_payload" src`): `synthesizer/manifest.py` (WP03-owned, mechanical), `project_registration.py` (WP03-owned, mechanical), `specify_cli/doctrine/pack_manifest.py`, `builtin_manifest.py`. No import of the helpers through `synthesizer.manifest` may remain.
  4. Move `absorb_synthesis_manifest` (`specify_cli/doctrine/pack_manifest.py:310`) into `charter.activation.synthesizer.manifest`. It needs `PackManifest`, and `charter` may not import `specify_cli`, so do this sub-step **inside step 2's commit**, once `PackManifest` lives in offering. Update `tests/doctrine/test_charter_profile_absorption.py` and re-key its dead-symbol entry. (The research's `_fresh_doctrine` importer does not exist at planning time; `grep` is the authority.)
  5. Step 0b: move `src/charter/activation/org_extends.py` to `src/charter/offering/packs/extends.py` (it imports only `collections.abc`). Repoint `pack_lineage.py:43`, `specify_cli/doctrine/org_charter.py`, `src/charter/__init__.py:103-106`, `tests/charter/test_org_extends.py`, and the guardrail `tests/architectural/test_pack_lineage_no_parallel_resolver.py` (its "one resolver" target becomes `charter.offering.packs.extends`; `_PACK_MODULES_ROOT` at `:44` changes in step 1).
- **Files**: `offering/packs/{__init__,hashing,extends}.py`, `activation/org_extends.py` (deleted), the importers.
- **Validation**:
  - [ ] `pytest tests/architectural/test_tid251_enforcement.py tests/architectural/test_pack_lineage_no_parallel_resolver.py tests/charter/test_org_extends.py tests/charter/synthesizer -q`.
  - [ ] `tests/charter/packs/test_hashing.py`: the two functions return the same digests as before for a fixed payload (golden values computed once from the pre-move code and pasted into the test).

### Subtask T022 – Prep: org-charter steps behind hooks; pure manifest writer out of `snapshot` (A.3 #4, #6; step 0d)

- **Purpose**: `pack_validator` and `pack_assembler` call `OrgCharterPolicy` lazily (`pack_validator.py:1684`, `pack_assembler.py:679`) and `pack_assembler` imports the adapters (`.snapshot.write_pack_manifest`, `.sources.protocol.FetchResult`, `pack_assembler.py:50-52`). Both edges must go before the move.
- **Steps**:
  1. Org-charter steps (A.3 #4, minimal fix, ruling 9 placement kept):
     - Move the bodies of `pack_validator._validate_org_charter` (`:1668`) and `pack_assembler._merge_org_charters_to_output` (`:659`) into `src/specify_cli/doctrine/org_charter.py` as public `validate_org_charter_file(path) -> list[ValidationIssue]` and `merge_org_charter_files(paths, output_dir) -> None`. Delete the dead `try/except ModuleNotFoundError` fallbacks.
     - `validate_pack(pack_dir, *, check_drg_root=True, org_charter_check: Callable[[Path], list[ValidationIssue]] | None = None)` and `assemble(..., org_charter_merge: Callable[[Sequence[Path], Path], None] | None = None)`: when the pack has an `org-charter.yaml` and no hook is given, record an explicit issue/refusal ("org charter not validated: no checker supplied"), never skip silently.
     - Add one composing entry next to the steps: `validate_pack_with_org_charter(pack_dir, **kw)` and `assemble_pack_with_org_charter(...)`. The CLI (`cli/commands/doctrine.py`, `_doctrine_collect.py`) imports them directly from `specify_cli.doctrine.org_charter` (`specify_cli` → `specify_cli` is legal). Do **not** export them from `charter.packs` here: that would be a `charter` → `specify_cli` import, which C-007 forbids and `tests/architectural/test_charter_no_specify_cli_import.py` fails. WP05 adds them to the facade when `org_charter` moves to `charter.activation` (the facade module is not under `charter/offering/`, so importing `charter.activation` there is legal). Pin with a test that the CLI path reaches `validate_org_charter_file` (monkeypatch it to raise and assert the CLI reports it).
     - If the hook split grows past about 100 lines, stop and raise the A.3 #4 alternative (validator/assembler under `charter.activation`) with the orchestrator; do not deviate silently.
  2. Pure manifest writer (A.3 #6): move `snapshot.write_pack_manifest` (`snapshot.py:454`) and its pure helpers (`_strip_credentials`, `_safe_urlsplit`, `_source_uses_query`, `_source_fingerprint`, `_snapshot_sha256`, `_iso_now`, `_manifest_artifact_counts`, `_count_artifacts`) into the manifest module (lands in offering in step 2; do this sub-step inside step 2's commit). New signature takes primitives: `write_pack_manifest(local_path, *, pack_version, etag, source_url, source_type)`. `snapshot.py` unpacks `FetchResult` and calls it through `charter.packs`. Keep `_iso_now` once (api_source has its own `_iso_now`, `api_source.py:317`; leave it). Update `tests/kernel/test_byte_identity_mapping.py:429` key to `charter.offering.packs.pack_manifest._iso_now#fetched_at`.
  3. Step 0d: add `CORE_KIND_PLURALS` (from `charter.offering.api` if exposed there, else `charter.offering.artifact_kinds`) and `resolve_relative_path_within_root` (`charter.offering.drg.org_pack_config`) to `src/charter/drg.py` `__all__`. Repoint `sources/api_source.py:25` and `snapshot.py:449` to `charter.drg`. Create `src/charter/packs.py` (docstring: "the public door for `specify_cli` to the pack model and tooling; object-identity re-exports only"). Update `tests/architectural/test_charter_facades_reexport_doctrine.py:60` (and `test_doctrine_public_surface.py` if it pins sets) for both facades.
- **Files**: `specify_cli/doctrine/{org_charter,pack_validator,pack_assembler,snapshot}.py`, `sources/api_source.py`, `charter/drg.py`, `charter/packs.py`.
- **Validation**:
  - [ ] `pytest tests/specify_cli/doctrine tests/architectural/test_charter_facades_reexport_doctrine.py tests/architectural/test_doctrine_public_surface.py tests/kernel/test_byte_identity_mapping.py -q`.

### Subtask T023 – Move pack model and tooling to `charter.offering.packs` (steps 1, 2, 4)

- **Steps**:
  1. Step 1: `git mv` `pack_descriptor.py` and `pack_lineage.py` into `src/charter/offering/packs/`. Re-key `tests/architectural/test_no_dead_modules.py:455-464` (`charter.offering.packs.pack_descriptor`, `.pack_lineage`; count unchanged), reword `_baselines.yaml:61-62`, re-key the dead-symbol entries (`pack_lineage` ×5, `pack_descriptor` ×1), set `_PACK_MODULES_ROOT` in `test_pack_lineage_no_parallel_resolver.py:44` to `src/charter/offering/packs`.
  2. Step 2: move `pack_manifest.py` and `builtin_manifest.py`. Their imports become offering-only (`hashing`, `yaml_utils.canonical_yaml`, `artifact_kinds`). `builtin_manifest.py:48` `GENERATED_BY` keeps its value here (WP15 changes it and regenerates). Re-key dead-symbol entries (manifest ×12 incl. builtin ×4), `test_pack_manifest_no_author_edit.py:13,42` imports `charter.offering.packs.builtin_manifest`.
  3. Step 4: move `pack_validator.py` (1,819 lines) and `pack_assembler.py`. Repoint their B.2 pack-relative literals (`pack_validator.py:584,1422,1546,1678`, `pack_assembler.py:467,481,672,685,695`) to `kernel.charter_pack_paths` and delete the matching rows from `tests/architectural/charter_pack_path_allowlist.yaml` (WP03-owned; mechanical follow-up, logged). Delete the stale descriptor in `tests/architectural/test_charter_sole_door_agent_profile_repository.py:199` (`src/charter/offering/` is already exempt there). Re-key dead-symbol entries (assembler ×2). Update prose references in `charter/offering/assets/models.py:14`, `drg/org_pack_config.py:177`, `drg/org_pack_loader.py:150,286` (docstrings; mechanical, logged).
  4. `pyproject.toml` ruff-format excludes for every moved file (prefer formatting and dropping).
- **Validation** (after each step, run the gates of that step's table row):
  - [ ] `pytest tests/architectural/test_charter_offering_does_not_import_activation.py tests/architectural/test_charter_no_specify_cli_import.py tests/architectural/test_layer_rules.py -q`.
  - [ ] `grep -rn "specify_cli.doctrine.\(pack_\|builtin_manifest\)" src tests` returns nothing.

### Subtask T024 – `charter.packs` facade; `charter.drg` exports; repoint `specify_cli` importers

- **Steps**:
  1. Fill `src/charter/packs.py` with the names `specify_cli` uses (find them: `grep -rn "pack_validator\|pack_assembler\|builtin_manifest\|pack_manifest" src/specify_cli`): offering-side functions only: at least `validate_pack`, `assemble`, `ValidationResult`/issue types, `write_pack_manifest`, the built-in-manifest regenerate/check functions, `pack_document_dict` (a public name for the assembler's `_document_dict`, A.3 #8).
  2. Repoint: `src/specify_cli/cli/commands/doctrine.py:294,415,462,721,813` (WP03-owned, mechanical; `_artifact_schema_registry` is private: expose a public facade name instead of importing a private), `src/specify_cli/cli/commands/_doctrine_collect.py` (WP02-owned, mechanical), `src/specify_cli/drg_writers/registry.py:56,196-197` (`name=` must equal the real `module.qualname`, cross-checked by `tests/architectural/test_drg_writer_discovery.py`; with the public alias decide whether the registry tracks `charter.offering.packs.pack_assembler._document_dict` or the public name, and update the gate's docstring `:124`).
  3. `snapshot.py` (still in `specify_cli.doctrine`) imports the writer from `charter.packs`.
- **Validation**:
  - [ ] `pytest tests/architectural/test_runtime_charter_doctrine_boundary.py tests/architectural/test_doctrine_census.py tests/architectural/test_drg_writer_discovery.py -q`: the lazy-import baseline did **not** grow (NFR-002).
  - [ ] `tests/charter/packs/test_charter_packs_facade.py`: every facade name `is` the offering object.

### Subtask T025 – Move tests mirroring the moved modules; run gates

- **Steps**:
  1. `git mv` `tests/specify_cli/doctrine/test_pack_validator.py`, `test_pack_validator_fragment_finding.py`, `test_pack_validator_kind_derivation.py`, `test_pack_assembler.py` to `tests/charter/packs/` (A.5); add `tests/charter/packs/__init__.py` if sibling test dirs use one (check `tests/charter/activation/__init__.py`). Update imports.
  2. Import-only changes in `tests/doctrine/{test_pack_lineage,test_pack_id_identity,test_pack_manifest_schema,test_builtin_manifest,test_counts_derivation,test_pack_version_relocation,test_charter_profile_absorption,test_org_pack_augmentation,test_template_asset_e2e}.py`, `tests/doctrine/drg/{test_org_fragment_validation,test_sharding_silent_degrade}.py`, `tests/integration/test_quickstart_end_to_end.py`, `tests/specify_cli/doctrine/test_snapshot.py`.
  3. `pyproject.toml:2014-2022` test-path ruff excludes for moved tests.
  4. Confirm `tests/charter/packs` is collected by the charter cone (`tests/architectural/_gate_coverage.py`) and the roster gates stay green: `pytest tests/architectural/test_ci_collection_completeness.py tests/architectural/test_module_shard_registry.py tests/architectural/test_gate_selection_authority.py -q`.
  5. Flip: run `tests/acceptance/charter_pack_cutover/test_package_split.py`; the two WP04 tests are green, the WP05 ones still xfail.

## Test Strategy

```bash
make test-fast
uv run --frozen pytest tests/acceptance/charter_pack_cutover -q -rxX
uv run --frozen pytest tests/charter tests/doctrine -q                       # owning subsystems of src/charter/offering/**
uv run --frozen pytest tests/specify_cli/doctrine tests/kernel/test_byte_identity_mapping.py tests/integration/test_quickstart_end_to_end.py -q
uv run --frozen pytest tests/architectural/test_charter_offering_does_not_import_activation.py tests/architectural/test_charter_no_specify_cli_import.py \
  tests/architectural/test_layer_rules.py tests/architectural/test_runtime_charter_doctrine_boundary.py tests/architectural/test_doctrine_census.py \
  tests/architectural/test_pack_lineage_no_parallel_resolver.py tests/architectural/test_pack_manifest_no_author_edit.py \
  tests/architectural/test_no_dead_modules.py tests/architectural/test_no_dead_symbols.py tests/architectural/test_dead_symbol_allowlist_contract.py \
  tests/architectural/test_charter_sole_door_agent_profile_repository.py tests/architectural/test_drg_writer_discovery.py \
  tests/architectural/test_charter_facades_reexport_doctrine.py tests/architectural/test_doctrine_public_surface.py \
  tests/architectural/test_tid251_enforcement.py tests/architectural/test_ruff_format_exclude_ratchet.py \
  tests/architectural/test_charter_pack_path_authority.py tests/architectural/test_ci_collection_completeness.py \
  tests/architectural/test_module_shard_registry.py tests/architectural/test_gate_selection_authority.py -q
uv run --frozen mypy src/charter/offering/packs src/charter/packs.py src/charter/drg.py <other touched src files>
uv run --frozen ruff check <touched files>
uv run --frozen ruff format --check --force-exclude <touched files>
uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q
```

Never bare `tests/architectural/` or `make test-full`. Record commands and counts.

## Commit discipline

One commit per A.6 step (0a, 0b, 0d, 1, 2, 4) plus the red-first commit and the test move, each `refactor(charter): … (#3732)` naming the step. Never push to `main`.

## Risks & Mitigations

- **Silent skip of the org-charter leg**: explicit issue when no hook is supplied; CLI-path test.
- **Byte drift in manifest hashes**: golden digests in `test_hashing.py`; `test_counts_derivation`.
- **Lazy baseline growth**: every `specify_cli` caller goes through `charter.packs`, except the two composing entries, imported from `specify_cli.doctrine.org_charter` until WP05 moves them.

## Definition of Done

- [ ] Steps 0a, 0b, 0d, 1, 2, 4 done, each in its own commit with its gates green.
- [ ] `charter.offering.packs` imports neither `charter.activation` nor `specify_cli`; `charter.packs` imports no `specify_cli` module and exports only offering-side names; it is the only `specify_cli` door to the moved modules.
- [ ] WP04 acceptance tests red first, green last; mechanical edits logged.

## Review Guidance

- Walk the commits against the A.6 table; each step's gate row must be green at that commit.
- Check no old module path remains importable and no re-export alias exists.
- Verify the org-charter hook cannot be skipped silently (read the test).
- Verify `hash_*` have one definition each, with the TID251 noqa.

## Activity Log

- 2026-10-06T19:30:00Z – system – Prompt created.
- 2026-10-07T06:09:14Z – claude – shell_pid=1299 – Mechanical edits outside owned_files (completed upstream WPs, import/key-only): synthesizer/manifest.py, project_registration.py (WP03: hash helper import; absorb_synthesis_manifest moved in), cli/commands/doctrine.py (WP03: charter.packs + composing entries), charter_pack_path_allowlist.yaml (WP03: 6 WP04 entries drained, baseline 27->21), _doctrine_collect.py (WP02: docstring), dead_symbol_allowlist.yaml (WP02: re-keys; also dropped 7 REVIVED kernel.charter_pack_paths entries left stale by WP03), specify_cli/doctrine/__init__.py (stop re-exporting write_pack_manifest, C-001), docstrings in offering assets/models.py, drg/org_pack_config.py, drg/org_pack_loader.py, pack_paths.py, test_charter_kind_vocabulary_single_authority.py; _completion_manifest.json regenerated (also picks up an upstream stale .kittify/charter-packs help text).
- 2026-10-07T06:09:17Z – claude – shell_pid=1299 – Decisions: (1) charter/packs.py created in step 2 not 0d (an empty facade would trip test_no_dead_modules). (2) Hook signature OrgCharterCheck = Callable[[Path, AbstractSet[str]], list[ValidationIssue]] (pack directive ids needed for the required_directives advisory); validate_org_charter_file(path, pack_directive_ids=frozenset()). (3) write_pack_manifest helpers made public in pack_manifest (strip_source_credentials, safe_urlsplit, source_fingerprint, snapshot_sha256, count_snapshot_artifacts, RECOGNISED_ARTIFACT_DIRS) since snapshot still needs them; exported via charter.packs. (4) _artifact_schema_registry -> artifact_schema_registry, _document_dict -> pack_document_dict (public, via facade). (5) Dead-symbol gate: OrgCharterPolicy, validate_org_charter_file, merge_org_charter_files dropped from org_charter.__all__ (no cross-module src caller; WP05 should add the composing entries/steps to the facade and may re-add). (6) src/charter/__init__.py lazy-export repoint: no version bump per tasks.md (WP24 changelog). (7) Campsite: dropped stale _doctrine_paths.py ruff format exclude.
