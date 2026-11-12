---
work_package_id: WP01
title: Remove DocFX and rebase its tests
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- NFR-001
- NFR-002
- NFR-003
- C-002
- C-003
planning_base_branch: issue-6943-retire-docfx
merge_target_branch: issue-6943-retire-docfx
branch_strategy: Planning artifacts for this mission were generated on issue-6943-retire-docfx. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6943-retire-docfx unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Removal
history:
- at: '2026-11-12T18:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: scripts/docs/
create_intent:
- tests/docs/test_legacy_docsite_retired.py
- tests/_support/reports_unpublished_guard.py
execution_mode: code_change
model: ''
owned_files:
- docs/docfx.json
- docs/toc.yml
- docs/api/toc.yml
- docs/changelog/toc.yml
- docs/changelog/1x/toc.yml
- docs/changelog/2x/toc.yml
- docs/development/toc.yml
- docs/guides/toc.yml
- docs/operations/toc.yml
- docs/templates/**
- docs/CNAME
- docs/robots.txt
- docs/.nojekyll
- docs/.gitignore
- docs/_meta/sections.yaml
- site/link-debt.json
- scripts/docs/**
- tests/docs/**
- tests/_support/**
- tests/audit/test_no_legacy_agent_profiles_path.py
- tests/contract/test_terminology_guards.py
- tests/specify_cli/cli/test_decision_command_shape_consistency.py
- tests/architectural/test_retired_charter_vocabulary.py
- tests/architectural/test_no_dead_src_path_literals.py
- tests/architectural/global_state_allowlist/S6.yaml
- tests/glossary/test_activation_ledger_terms.py
- tests/release/pinning_rule_inventory.json
- src/specify_cli/docs/index_model.py
- pyproject.toml
- ruff.toml
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6943'
---

# Work Package Prompt: WP01 – Remove DocFX and rebase its tests

## Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

## Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`). Address all feedback; record progress with `spec-kitty agent tasks add-history WP01 --note "..."`.

## Objectives & Success Criteria

- `docs/docfx.json`, every `toc.yml`, `docs/templates/`, `docs/CNAME`, `docs/robots.txt`, `docs/.nojekyll`, `docs/.gitignore` are gone (FR-001).
- The DocFX-only modules listed in `plan.md` (Design, "What goes and why") are gone, with their tests (FR-002), and so are `redirect_map.yaml` and `redirect_baseline_urls.json` (FR-003).
- No `scripts/docs` module or test imports a deleted module (FR-004).
- The published-page metadata rule and the reports-unpublished guard read the contract and each has a mutant that turns it red (FR-005, FR-006).
- No ratchet grows (NFR-003); ruff, format and mypy clean on changed files (NFR-002).

## Context & Constraints

- Spec and plan in `kitty-specs/retire-docfx-01M78FG2/`. ADR `docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md` D-6, D-13 and its amendments.
- C-003: keep every D-6 keep script and every module the doc-kitty build reads (`_dockitty_contract.py`, `site_*.py`, `moves_ledger.py`, `docs_index.py`, `_inventory.py`, `inventory_lockfile.py`, the freshness and CLI-reference checks, the rename tools). Do not edit `packs/` (C-002) or immutable history (spec C-001).
- Do not touch `.github/`, `docs/api/*.md`, `docs/development/**`, `site/`, the ADR or the changelog: WP02 owns them.

## Subtasks & Detailed Guidance

### T001 – Red-first tests

- `tests/docs/test_legacy_docsite_retired.py`: (a) each DocFX source path and dropped module/data file is absent; (b) no `.py` under `scripts/` or `tests/` imports a dropped module (AST scan of `import`/`from` statements, non-vacuous: it must examine at least 100 files and have a self-test that a planted import is found).
- Contract: `published_pages(docs_root)` (rel paths of published `.md` pages) and its test in `tests/docs/test_dockitty_contract.py` (a draft, an excluded-folder page and a working-note page are absent; an active page is present; `unpublished_routes` and `published_pages` partition the tree's routes).
- `tests/_support/reports_unpublished_guard.py`: `assert_reports_unpublished(docs_root)` fails unless `reports` is in `EXCLUDED_FOLDERS` and every `docs/reports/**.md` route is in `unpublished_routes`; with a self-test where the contract's excluded folders omit `reports` (monkeypatch) and the guard fails.
- Run them before the deletions and record the red count.

### T002 – Delete the DocFX sources

`git rm` the files listed in the objectives. `docs/templates/index.md` goes with the folder (its route was never in the URL baseline).

### T003 – Delete the DocFX-only scripts

`git rm` `plantuml_render.py`, `plantuml_invoke.py`, `plantuml_pins.json`, `generate_kitty_specs_docs.py`, `glossary_linker.py`, `glossary_page/`, `redirect_stub_generator.py`, `redirect_map.yaml`, `redirect_baseline_urls.json`, `capture_baseline_urls.py`, `seo_postprocess.py`, `seo_verify.py`, `description_length_check.py`, `_published_pages.py`. Move `slugify` into `docs_index.py` (same behaviour). Remove `moves_ledger.derive_redirect_map` and `moves_ledger.validate`. Add `published_pages()` to `_dockitty_contract.py`, sharing the per-page predicate with `unpublished_routes`.

### T004 – Tests

- Delete: `test_plantuml_render.py`, `test_plantuml_invoke.py`, `test_plantuml_no_egress_corpus.py`, `test_plantuml_sandbox_negative.py`, `test_glossary_linker.py`, `test_redirect_stub_generator.py`, `test_capture_baseline_urls.py`, `test_seo_verify.py`, `test_description_length_gate.py`, `test_description_length_check_propagation.py`, `test_published_pages.py`, `test_publish_manifest_coherence.py`, `_publish_manifest_helpers.py`, `tests/_support/docfx_reports_guard.py`, `tests/_support/test_docfx_reports_guard.py`.
- Rebase: `test_docs_seo.py` (contract published set, contract band, floor 500; static files from `site/public/`); `test_moves_ledger.py` (ledger unit tests and the #3914 reconcile on `collapse`; drop the DocFX-map, manifest and DocFX-published-set tests, which `site_redirects` and `test_site_redirects.py` own now); `test_redirect_spine.py` (derive from `collapse`; frozen keys are a subset of `site/legacy-redirects.json` keys; drop the DocFX stub-coverage case); `test_one_index_per_folder.py` (`collapse`); `test_rulers_blocking.py` (drop the description-gate cases); `test_docs_index.py` (slugify lives in `docs_index`); `test_versioned_docs_integrity.py` (no `toc.yml`); the three terminology tests use the new guard; `tests/_support/terminology_scope.py` comment.

### T005 – Ratchets, inventories, comments

- Remove deleted paths from `pyproject.toml` (formatter exclude, any test lists) and `ruff.toml`.
- Re-derive `tests/release/pinning_rule_inventory.json` with `scripts/ci/derive_pinning_inventory.py` if a deleted test was listed.
- Drop `docs/changelog/1x/toc.yml` from `_RELEASED_CHANGELOG_FILES`; reword the DocFX mention in `test_no_dead_src_path_literals.py`.
- Reword DocFX comments in kept modules (`_dockitty_contract.py`, `bulk_ref_rewrite.py`, `dockitty_frontmatter_migration.py`, `moves_ledger.py`, `site_built_check_render.py`, `site_redirects.py`, `_guards.py`, `src/specify_cli/docs/index_model.py`) and their tests, without changing behaviour.

### T006 – Verify

```bash
uv run --frozen pytest tests/docs -n 4 --dist loadfile --tb=line -q
uv run --frozen pytest tests/_support tests/audit/test_no_legacy_agent_profiles_path.py tests/contract/test_terminology_guards.py tests/specify_cli/cli/test_decision_command_shape_consistency.py tests/release/test_pinning_inventory_fresh.py --tb=line -q
uv run --frozen pytest tests/architectural/test_retired_charter_vocabulary.py tests/architectural/test_no_dead_src_path_literals.py tests/architectural/test_ruff_format_exclude_ratchet.py tests/architectural/test_pyproject_shape.py tests/architectural/test_no_legacy_terminology.py --tb=line -q
uv run --frozen ruff check <changed .py>; uv run --frozen ruff format --check --force-exclude <changed .py>; uv run --frozen mypy --strict <changed modules>
```

## Review Guidance

- Each deletion is DocFX-only or has a doc-kitty successor named in `plan.md`; no D-6 keep script is gone.
- The rebased guards read the contract and have a red mutant.
- No ratchet entry was added; no skip or xfail.
