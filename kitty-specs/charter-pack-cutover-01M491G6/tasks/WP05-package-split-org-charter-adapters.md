---
work_package_id: "WP05"
title: "Package split II — org charter, adapters, delete specify_cli.doctrine"
subtasks: ["T026", "T027", "T028", "T029"]
dependencies: ["WP04"]
requirement_refs: ["FR-010", "C-007", "NFR-002"]
task_type: "implement"
phase: "Phase 1 - Foundations (paths, package split)"
execution_mode: "code_change"
owned_files:
  - "src/charter/activation/org_charter.py"
  - "src/charter/activation/org_charter_loader.py"
  - "src/specify_cli/doctrine/__init__.py"
  - "src/specify_cli/doctrine/config.py"
  - "src/specify_cli/doctrine/org_charter_loader.py"
  - "src/specify_cli/doctrine/sources/__init__.py"
  - "src/specify_cli/doctrine/sources/protocol.py"
  - "src/specify_cli/doctrine/sources/git_source.py"
  - "src/specify_cli/doctrine/sources/https_source.py"
  - "src/specify_cli/doctrine/template_render/__init__.py"
  - "src/specify_cli/doctrine/template_render/ignore_copy.py"
  - "src/specify_cli/doctrine/template_render/pipeline.py"
  - "src/specify_cli/doctrine/template_render/resolve.py"
  - "src/specify_cli/doctrine/template_render/substitute.py"
  - "src/specify_cli/doctrine/template_render/validation.py"
  - "src/specify_cli/charter_packs/**"
  - "src/specify_cli/charter_runtime/lint/checks/org_layer.py"
  - "src/specify_cli/cli/commands/charter/context.py"
  - "src/specify_cli/cli/commands/charter/generate.py"
  - "src/specify_cli/review/scope_source.py"
  - "src/specify_cli/dossier/__init__.py"
  - "tests/specify_cli/doctrine/__init__.py"
  - "tests/specify_cli/doctrine/test_collision_warnings.py"
  - "tests/specify_cli/doctrine/test_config.py"
  - "tests/specify_cli/doctrine/test_missing_pack_policy.py"
  - "tests/specify_cli/doctrine/test_org_charter.py"
  - "tests/specify_cli/doctrine/test_org_charter_merge_parity.py"
  - "tests/specify_cli/doctrine/test_org_charter_pack_context.py"
  - "tests/specify_cli/doctrine/test_org_charter_union.py"
  - "tests/specify_cli/doctrine/test_sources.py"
  - "tests/specify_cli/doctrine/test_sources_security.py"
  - "tests/specify_cli/doctrine/test_template_render_ignore_copy.py"
  - "tests/specify_cli/doctrine/test_template_render_pipeline.py"
  - "tests/specify_cli/doctrine/test_template_render_resolve.py"
  - "tests/specify_cli/doctrine/test_template_render_substitute.py"
  - "tests/specify_cli/doctrine/test_template_render_validation.py"
  - "tests/specify_cli/charter_packs/**"
  - "tests/charter/activation/test_org_charter.py"
  - "tests/charter/activation/test_org_charter_merge_parity.py"
  - "tests/charter/activation/test_org_charter_pack_context.py"
  - "tests/charter/activation/test_org_charter_union.py"
  - "tests/charter/activation/test_missing_pack_policy.py"
  - "tests/charter/activation/test_org_pack_registry_paths.py"
  - "tests/charter/test_collision_warnings.py"
  - "tests/charter/test_answers_inert_and_org_union.py"
  - "tests/charter/test_directive_identity_mapping.py"
  - "tests/charter/test_iter_org_charter_docs.py"
  - "tests/cli/test_doctrine_org_commands.py"
  - "tests/cli/commands/test_charter_json_error_contract.py"
  - "tests/cli/commands/test_charter_rendering.py"
  - "tests/doctrine/pack_skills/test_kind_registration.py"
  - "tests/integration/test_org_pack_artifact_lifecycle.py"
  - "tests/integration/test_org_pack_subdir_e2e.py"
  - "tests/specify_cli/cli/commands/test_doctrine_collect.py"
  - "tests/specify_cli/cli/commands/test_charter_interview_org_prefill.py"
  - "tests/specify_cli/test_provenance_integration.py"
  - "tests/architectural/test_doctrine_census.py"
  - "tests/architectural/test_runtime_charter_doctrine_boundary.py"
  - "tests/architectural/_owned_checkout_scan.py"
  - "tests/architectural/test_owned_checkout_gate_selftest.py"
  - "tests/architectural/test_owned_checkout_single_authority.py"
  - "tests/architectural/test_egress_consent_boundary.py"
  - "tests/architectural/test_destructive_op_routing.py"
  - "tests/architectural/test_mutation_ownership_routing.py"
  - "tests/architectural/test_kind_table_derivation.py"
  - "tests/architectural/_gate_coverage.py"
  - "tests/architectural/_interpreter_shard_roster.py"
  - "tests/architectural/ci_topology_census.json"
  - "tests/review/test_pre_review_gate_engine.py"
  - ".github/ci-module-registry.yml"
  - ".github/workflows/ci-nightly.yml"
  - ".github/ci-foreign-coverage-baseline.json"
authoritative_surface: "src/specify_cli/charter_packs/"
create_intent:
  - "src/charter/activation/org_charter.py"
  - "src/charter/activation/org_charter_loader.py"
  - "src/specify_cli/charter_packs/__init__.py"
  - "src/specify_cli/charter_packs/snapshot.py"
  - "src/specify_cli/charter_packs/sources/__init__.py"
  - "src/specify_cli/charter_packs/template_render/__init__.py"
  - "tests/specify_cli/charter_packs/__init__.py"
  - "tests/charter/activation/test_org_charter.py"
  - "tests/charter/activation/test_org_charter_merge_parity.py"
  - "tests/charter/activation/test_org_charter_pack_context.py"
  - "tests/charter/activation/test_org_charter_union.py"
  - "tests/charter/activation/test_missing_pack_policy.py"
  - "tests/charter/activation/test_org_pack_registry_paths.py"
  - "tests/charter/test_collision_warnings.py"
agent_profile: "architect-alphonso"
role: "implementer"
agent: "claude"
history:
  - at: "2026-10-06T19:30:00Z"
    actor: "system"
    action: "Prompt generated via /spec-kitty.tasks"
---

# Work Package Prompt: WP05 – Package split II — org charter, adapters, delete `specify_cli.doctrine`

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

After WP18 lands, the `/ad-hoc-profile-load` skill is deleted: load profiles with `spk-charter-profile-load` instead (use whichever exists in your checkout).

- **Profile**: `architect-alphonso`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If the profile cannot be loaded, run `spec-kitty agent profile list` and pick the best match for `task_type: implement` on `src/specify_cli/charter_packs/`.

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

1. Org charter composition (`org_charter`, `org_charter_loader`, with `config.py` folded in) lives in `src/charter/activation/` (OD-9).
2. The fetch and scaffold adapters (`sources/`, `snapshot`, `template_render/`) live in `src/specify_cli/charter_packs/`.
3. `src/specify_cli/doctrine/` is deleted, including `__init__.py`. `import specify_cli.doctrine` raises `ModuleNotFoundError`.
4. The package's census and boundary exemptions are **deleted, not moved** (NFR-002): `EXEMPT_MANAGEMENT_SURFACE` is empty, `_EXEMPT_SUBPACKAGE` and its predicate are gone, and no new exemption names `specify_cli/charter_packs`.
5. The five roster files and the `pyproject.toml` test-path entries change in one atomic commit; every roster gate is green.
6. WP01's FR-010 package tests and the NFR-002 census/boundary rows pending on WP05 are green.

## Context & Constraints

- Read: `spec.md` FR-010, OD-9, C-001, C-007, C-008, NFR-002; `research/package-split-and-paths.md` Part A (A.1, A.3 #4 and #7, **A.4 gate table, every row**, A.5 test homes, A.6 order).
- WP04 has moved the pack model and tooling to `charter.offering.packs`, created the `charter.packs` facade, extended `charter.drg`, and added `validate_org_charter_file`, `merge_org_charter_files` and the composing entries to `src/specify_cli/doctrine/org_charter.py`. Read WP04's Activity Log first.
- **C-008 note**: `org_charter.py:45` imports `charter.activation.default_pack`, which FR-005 deletes later (WP13). WP06 (FR-015) comes after this WP, so the move **carries** that import (legal inside `charter`, A.6 step 3 "Prerequisite").
- **No aliases (C-001)**: `config.py`'s four `import X as X` re-exports of `charter.offering.drg.org_pack_config` symbols are a laundering conduit; they are deleted, and every caller imports the real home. No `specify_cli/doctrine/__init__.py` stub, no `charter_packs/__init__.py` re-export list beyond what a package needs (keep it docstring-only unless a caller needs a name, and then prefer the submodule path).
- Renames of identifiers are **not** in this WP: do the module move only, except where an identifier is a path (for example roster keys). `MissingDoctrinePackError` (→ `MissingCharterPackError`) is renamed by WP20 (R2) and `OrgDoctrineSource` (→ `OrgCharterPackSource`) by WP21 (R3); WP01's `test_fr010_retired_identifiers_absent` rows pin both.
- Code style: ruff, `ruff format`, mypy clean; complexity ≤ 15; no new suppressions.

## Ownership of moved sources

`src/specify_cli/doctrine/org_charter.py`, `snapshot.py` and `sources/api_source.py` were edited and are owned by WP04. Moving them here (git mv + delete at the old path) is a mechanical rename of files owned by a completed upstream WP, which the tasks.md rule allows. Log each with a one-line rationale. The destinations are yours (`src/charter/activation/org_charter.py`, `src/specify_cli/charter_packs/**`).

Other mechanical edits outside owned_files (log each): `src/specify_cli/cli/commands/_doctrine_collect.py` (WP02), `src/specify_cli/cli/commands/doctrine.py` (WP03), `src/specify_cli/cli/commands/charter/interview.py` (import line only; later owned by WP06), `tests/architectural/dead_symbol_allowlist.yaml` (WP02), `tests/architectural/charter_pack_path_allowlist.yaml` (WP03), `pyproject.toml`, `tests/specify_cli/doctrine/test_snapshot.py`, `tests/kernel/test_byte_identity_mapping.py` (WP04), docstring path references in `src/charter/activation/{_drg_helpers,activations,context_contract,default_pack,interview,org_pack_discovery,pack_manager}.py` and `src/specify_cli/upgrade/migrations/m_unify_charter_activation.py:36,106` (docstrings only; WP06 owns that migration and runs after you, so touch only those two docstring lines and log them).

## Branch Strategy

- **Strategy**: Planning artifacts were generated on `issue-3732-charter-pack-rename`; completed changes merge back into `issue-3732-charter-pack-rename`.
- **Planning base branch**: `issue-3732-charter-pack-rename`
- **Merge target branch**: `issue-3732-charter-pack-rename`
- Lane: from `lanes.json` (filled by `spec-kitty agent mission finalize-tasks`).

## Red-first (C-006 / C-011)

First commit: delete the `pending_until("WP05", …)` markers in `tests/acceptance/charter_pack_cutover/test_package_split.py` (`test_fr010_specify_cli_doctrine_package_deleted`, `test_fr010_org_charter_and_adapters_at_ruled_homes`) and in `tests/acceptance/charter_pack_cutover/test_gates_latency_messaging.py` (`test_nfr002_gates_close_empty` rows "census exemption empty" and "boundary exemption gone"). Run them red, record, commit. Do not change their assertions.

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

**How this WP executes the table.** Steps 0a–2 and 4 are done (WP02 did 0c, WP04 the rest). This WP does **3, 5 and 6**, in that order, one commit each (6 is atomic). In step 3, `validate_org_charter_file`, `merge_org_charter_files` and the composing entries already exist (WP04 added them to `specify_cli/doctrine/org_charter.py`); they move with the module.

## Subtasks & Detailed Guidance

### Subtask T026 – Move org charter composition to `charter.activation`; fold `config.py` (step 3)

- **Purpose**: org charter composition is an activation concern (OD-9, A.2: siblings `org_extends`, `org_pack_discovery`, `org_expected_artifacts` already live there; `org_extends` moved to offering in WP04).
- **Steps**:
  1. `git mv src/specify_cli/doctrine/org_charter.py src/charter/activation/org_charter.py` and `org_charter_loader.py` likewise. Fix imports inside them:
     - `from specify_cli.doctrine.config import load_pack_registry` (`org_charter.py:699,793,857`) → `from charter.offering.drg.org_pack_config import load_pack_registry`;
     - lazy `charter.activation.layer_roots` imports (repointed by WP02) stay;
     - `org_charter_loader.py:58` → `from charter.activation.org_charter import …`.
  2. Fold `config.py` (44 lines): delete its four `import X as X` re-exports (C-001); move `assert_pack_local_paths_exist` into `charter.activation.org_charter` next to `MissingDoctrinePackError`. It has no `src` caller (A.1): if `tests/architectural/test_no_dead_symbols.py` flags it, delete it and its test half instead, and record which. Do **not** create `charter/activation/config.py` (A.2).
  3. Repoint `src` importers (real imports at planning time): `charter_runtime/lint/checks/org_layer.py:96`, `cli/commands/charter/context.py:77`, `cli/commands/charter/generate.py:490`, `cli/commands/charter/interview.py:205` (mechanical), `cli/commands/_doctrine_collect.py:178,1112` (mechanical), `cli/commands/doctrine.py` org paths (mechanical). `specify_cli` may import `charter.activation.*` directly (only `charter.offering` needs a facade); confirm with `test_runtime_charter_doctrine_boundary.py`.
  4. Repoint test importers and the three patch strings: `tests/cli/commands/test_charter_rendering.py:353`, `tests/cli/commands/test_charter_json_error_contract.py:164`, `tests/specify_cli/cli/commands/test_doctrine_collect.py:85`; plus `tests/specify_cli/test_provenance_integration.py:24`, `tests/charter/{test_answers_inert_and_org_union,test_directive_identity_mapping,test_iter_org_charter_docs}.py`, `tests/cli/test_doctrine_org_commands.py`, `tests/doctrine/pack_skills/test_kind_registration.py`, `tests/integration/test_org_pack_artifact_lifecycle.py`, `tests/specify_cli/cli/commands/test_charter_interview_org_prefill.py`, `tests/architectural/test_kind_table_derivation.py:23`.
  5. Re-key dead-symbol entries (org_charter ×5); ruff exclude for `org_charter_loader` (`pyproject.toml:576`).
  6. Add the two composing entries `validate_pack_with_org_charter` and `assemble_pack_with_org_charter` (now in `charter.activation.org_charter`) to the `charter.packs` facade (`src/charter/packs.py`, WP04, a logged follow-up edit), as object-identity re-exports. WP04 left them out because they lived in `specify_cli` then. The facade module is not under `charter/offering/`, so importing `charter.activation` there is legal. Repoint the CLI importers (`cli/commands/doctrine.py`, `_doctrine_collect.py`) from `specify_cli.doctrine.org_charter` to `charter.packs`, and extend `tests/charter/packs/test_charter_packs_facade.py` (WP04, logged) with the two names.
- **Files**: the two destinations; `config.py` and the two sources deleted; importers; logged edits in `src/charter/packs.py` and its facade test.
- **Validation**:
  - [ ] `pytest tests/architectural/test_charter_no_specify_cli_import.py tests/architectural/test_kind_table_derivation.py tests/architectural/test_layer_rules.py -q` (the moved modules import nothing from `specify_cli`).
  - [ ] `pytest tests/charter tests/doctrine tests/cli/test_doctrine_org_commands.py tests/cli/commands -q`.

### Subtask T027 – Move adapters to `specify_cli.charter_packs` (step 5)

- **Steps**:
  1. `git mv` `src/specify_cli/doctrine/sources/` → `src/specify_cli/charter_packs/sources/`, `snapshot.py` → `src/specify_cli/charter_packs/snapshot.py`, `template_render/` → `src/specify_cli/charter_packs/template_render/`. Create `src/specify_cli/charter_packs/__init__.py` (docstring only). Relative imports (`from .sources.protocol import …`) keep working; absolute ones are repointed.
  2. Callers: `cli/commands/doctrine.py:148,1052-1053` (mechanical), `review/scope_source.py:9` and `dossier/__init__.py` (docstrings), `cli/commands/charter/_status_collectors.py:465` (docstring; WP02-owned, mechanical).
  3. Gate rows of A.4 for this step (each in this commit):
     - `tests/architectural/test_egress_consent_boundary.py:575,580` allowance keys → `specify_cli/charter_packs/sources/{api,https}_source.py`; reword "doctrine content" to "charter pack content";
     - `tests/architectural/test_destructive_op_routing.py:179` `CensusKey.rel` → `src/specify_cli/charter_packs/sources/git_source.py` (keep `token_line`);
     - `tests/architectural/test_mutation_ownership_routing.py:130-131,296-328` paths;
     - `tests/architectural/_owned_checkout_scan.py:44,100` `ORG_PACK_MODULE_PATHS`: replace `"src/specify_cli/doctrine/"` by `"src/specify_cli/charter_packs/"` only if `snapshot`/`sources` still call `OrgPackConfig.effective_root` (grep); otherwise delete the entry. Fix the docstring in `test_owned_checkout_single_authority.py:29`; rename the synthetic path in `test_owned_checkout_gate_selftest.py:258` to `src/specify_cli/charter_packs/loader.py`;
     - `.github/ci-foreign-coverage-baseline.json:71` → `specify_cli.charter_packs.template_render` (confirm the shrink-only rule with `scripts/ci/coverage_guard_lib.py`; drop the entry if the moved tests import it directly);
     - `pyproject.toml:581-583` ruff excludes (prefer formatting and dropping);
     - `pyproject.toml:84` comment on `requests` ("HTTP client for doctrine-pack https/api sources") → charter-pack wording.
  4. B.2 literals in `snapshot.py:357,468,582` → `kernel.charter_pack_paths` constants if they are pack-relative paths; delete the matching rows in `tests/architectural/charter_pack_path_allowlist.yaml` (mechanical).
  5. `OrgDoctrineSource`: leave the identifier for WP21 (R3, → `OrgCharterPackSource`), so this commit stays a pure move.
- **Parallel?**: after T026 (step order).
- **Validation**:
  - [ ] `pytest tests/architectural/test_egress_consent_boundary.py tests/architectural/test_destructive_op_routing.py tests/architectural/test_mutation_ownership_routing.py tests/architectural/test_owned_checkout_single_authority.py tests/architectural/test_owned_checkout_gate_selftest.py -q`.

### Subtask T028 – Delete `specify_cli/doctrine/`; boundary exemption deleted; census, roster, pyproject (step 6, atomic)

- **Purpose**: FR-010 "with its architectural census/boundary exemptions removed (not moved)"; NFR-002.
- **Steps** (one commit):
  1. Delete `src/specify_cli/doctrine/__init__.py` (it re-exports config, org_charter, snapshot, sources: C-001) and the now-empty directory. `grep -rn "specify_cli\.doctrine\b\|from specify_cli import doctrine" src tests` must return nothing except prose in files later WPs own (list any left in the Activity Log).
  2. `tests/architectural/test_doctrine_census.py:80,377-380`: `EXEMPT_MANAGEMENT_SURFACE = frozenset()`; rewrite `test_management_surface_is_frozen` to assert emptiness **and** that `src/specify_cli/doctrine` does not exist; update docstrings `:18,179`. Do not rename the file (NFR-002 names it).
  3. `tests/architectural/test_runtime_charter_doctrine_boundary.py:30-45`: delete `_EXEMPT_SUBPACKAGE` and `_is_exempt_subpackage` and their uses; **do not** point them at `specify_cli/charter_packs`. `:141-155,386-433`: retarget the laundering scan to "no `src/specify_cli/**` module lists a `charter.offering`-origin symbol in `__all__`" (keep a planted test), and delete `test_config_conduit_is_closed` (the module is gone). The lazy ratchet `_LAZY_BASELINE_ALLOWLIST` must not grow; with the exemption gone, any `specify_cli/charter_packs` reach into `charter.offering` turns red: it must go through `charter.drg` / `charter.packs` (WP04 step 0d did `api_source`/`snapshot`).
  4. Roster bijection, together: `tests/architectural/_gate_coverage.py:2263` key `"charter_packs"`, cone `("tests/specify_cli/charter_packs",)`; `_interpreter_shard_roster.py:331`; `ci_topology_census.json:85-91` `{"dir": "charter_packs", "cone_roots": ["tests/specify_cli/charter_packs"], …}`; `.github/ci-module-registry.yml:637`; `.github/workflows/ci-nightly.yml:774`.
  5. `pyproject.toml:2014-2022`: the remaining `tests/specify_cli/doctrine/*` ruff-format entries renamed to their new paths or (preferred) formatted and dropped.
  6. `tests/review/test_pre_review_gate_engine.py:82`: fake routing glob → `src/specify_cli/charter_packs/**` (cosmetic, FR-018).
- **Validation**:
  - [ ] `pytest tests/architectural/test_doctrine_census.py tests/architectural/test_runtime_charter_doctrine_boundary.py tests/architectural/test_module_shard_registry.py tests/architectural/test_gate_selection_authority.py tests/architectural/test_ci_collection_completeness.py tests/architectural/test_ruff_format_exclude_ratchet.py tests/architectural/test_no_dead_modules.py -q`.
  - [ ] `uv run --frozen python -c "import specify_cli.doctrine"` fails with `ModuleNotFoundError`.

### Subtask T029 – Move tests; flip WP01 FR-010 package xfails

- **Steps**:
  1. Move per A.5: `tests/specify_cli/doctrine/test_org_charter*.py` (4) and `test_missing_pack_policy.py` → `tests/charter/activation/`; `test_config.py` split: the registry half → `tests/charter/activation/test_org_pack_registry_paths.py`, the `doctrine fetch` CLI half → `tests/specify_cli/charter_packs/`; `test_sources*.py`, `test_snapshot.py`, `test_template_render_*.py` (5) → `tests/specify_cli/charter_packs/` (with `__init__.py`); `test_collision_warnings.py` (tests `charter.offering.base`) → `tests/charter/test_collision_warnings.py`. Delete `tests/specify_cli/doctrine/` including `__init__.py`.
  2. Update `tests/integration/test_org_pack_subdir_e2e.py` imports.
  3. Check that no test asserted behaviour of the deleted alias layer (`config.py` re-exports, `specify_cli.doctrine.__init__` names): delete such assertions with the shim (C-001), never adapt them; list each in the Activity Log.
  4. Run the acceptance file: the WP05 tests and NFR-002 rows are green; everything else unchanged.

## Test Strategy

```bash
make test-fast
uv run --frozen pytest tests/acceptance/charter_pack_cutover -q -rxX
uv run --frozen pytest tests/charter tests/doctrine -q
uv run --frozen pytest tests/specify_cli/charter_packs tests/cli/test_doctrine_org_commands.py tests/cli/commands \
  tests/specify_cli/cli/commands/test_doctrine_collect.py tests/specify_cli/cli/commands/test_charter_interview_org_prefill.py \
  tests/specify_cli/test_provenance_integration.py tests/integration/test_org_pack_subdir_e2e.py \
  tests/integration/test_org_pack_artifact_lifecycle.py tests/review/test_pre_review_gate_engine.py -q
uv run --frozen pytest tests/architectural/test_doctrine_census.py tests/architectural/test_runtime_charter_doctrine_boundary.py \
  tests/architectural/test_charter_no_specify_cli_import.py tests/architectural/test_charter_offering_does_not_import_activation.py \
  tests/architectural/test_layer_rules.py tests/architectural/test_kind_table_derivation.py tests/architectural/test_egress_consent_boundary.py \
  tests/architectural/test_destructive_op_routing.py tests/architectural/test_mutation_ownership_routing.py \
  tests/architectural/test_owned_checkout_single_authority.py tests/architectural/test_owned_checkout_gate_selftest.py \
  tests/architectural/test_module_shard_registry.py tests/architectural/test_gate_selection_authority.py \
  tests/architectural/test_ci_collection_completeness.py tests/architectural/test_ruff_format_exclude_ratchet.py \
  tests/architectural/test_no_dead_modules.py tests/architectural/test_no_dead_symbols.py \
  tests/architectural/test_charter_pack_path_authority.py -q
uv run --frozen mypy src/charter/activation/org_charter.py src/charter/activation/org_charter_loader.py src/specify_cli/charter_packs <other touched src files>
uv run --frozen ruff check <touched files>
uv run --frozen ruff format --check --force-exclude <touched files>
uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q
```

Never bare `tests/architectural/` or `make test-full`. Record commands and counts.

## Commit discipline

Red-first commit, then one commit per step (3, 5, 6) and one for the test moves, e.g. `refactor(charter): org charter composition moves to charter.activation (#3732)`, `refactor(cli): delete specify_cli.doctrine and its exemptions (#3732)`. Never push to `main`.

## Risks & Mitigations

- **Roster drift**: step 6 is one commit; the bijection gates run in that commit.
- **Hidden alias survives** (`__init__` re-exports, `config.py` conduit): grep and the boundary gate's retargeted laundering scan.
- **Lazy baseline growth after the exemption goes**: adapters reach offering only through `charter.drg` / `charter.packs`.

## Definition of Done

- [ ] `src/specify_cli/doctrine/` and `tests/specify_cli/doctrine/` gone; no import of `specify_cli.doctrine` anywhere.
- [ ] Census and boundary exemptions empty/deleted, not moved; lazy baseline unchanged.
- [ ] Roster files and ruff-exclude entries consistent; all named gates green.
- [ ] WP05 acceptance tests red first, green last; mechanical edits logged.

## Review Guidance

- Check out the red-first commit (WP05 acceptance tests red), then the last commit (green).
- Confirm no `specify_cli/charter_packs` exemption was introduced anywhere in `tests/architectural/`.
- Confirm `config.py`'s re-exports were deleted, not relocated, and `charter/activation/config.py` does not exist.
- Diff the five roster files in one commit.

## Activity Log

- 2026-10-06T19:30:00Z – system – Prompt created.
