# Implementation Plan: Retire DocFX

**Branch**: `kitty/mission-retire-docfx-01M78FG2` (lands on `issue-6943-retire-docfx`) | **Date**: 2026-11-12 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/retire-docfx-01M78FG2/spec.md`

## Summary

Delete the DocFX toolchain that the cutover (#6938) left in the tree: its configuration, navigation files, template and static resources; the `scripts/docs` modules that only fed the DocFX build (D-6 "drop", and "port" scripts whose job doc-kitty now does and whose only runner was the DocFX build); the superseded redirect map and manifest; and the tests of all of them. Rebase the two tests that guard a still-live rule (the published-page metadata rule and "`docs/reports/` is never published") on `scripts/docs/_dockitty_contract.py`. Then remove the CI plumbing for deleted scripts, update the living docs that describe DocFX, append the ADR amendment, add a changelog fragment, and add a gate that keeps DocFX out of living files.

## Technical Context

**Language/Version**: Python 3.11+ (scripts and tests), GitHub Actions YAML, Markdown
**Primary Dependencies**: pytest, PyYAML; the doc-kitty site build (`site/`, pnpm) is unchanged
**Storage**: files in the repository
**Testing**: `pytest tests/docs` plus the CI pin tests (`tests/ci`, `tests/release`) and the named architectural gate files; `make docs-site` when the toolchain is available
**Target Platform**: CI (ubuntu-24.04) and developer machines
**Project Type**: single repository
**Performance Goals**: none beyond keeping `tests (docs)` at or below its current runtime (it loses the jar provisioning steps)
**Constraints**: immutable history (C-001), no `packs/` edits (C-002), the D-6 keep list (C-003), append-only ledgers (C-005)
**Scale/Scope**: about 15 deleted scripts and data files, about 20 deleted or rebased test files, 8 `toc.yml`, one workflow job edited

## Charter Check

- **Single canonical authority.** The published set has one authority after this mission: the contract module. `_published_pages.py`, which read `docfx.json`, is deleted, not kept as a second answer. PASS.
- **ATDD / red-first.** Each WP opens with an absence or invariant test that is red on the base: WP01 with the DocFX-sources-and-modules absence test and the two contract-rebased guards; WP02 with the living-files gate and the jar-cache absence pin. PASS.
- **Architectural gate discipline (Standing Order #5).** The living-files gate starts from an explicit immutable-history and generated-files list (data, not an allowlist of offenders) and carries a self-test mutant. No ratchet grows (NFR-003). PASS.
- **Terminology.** Mission, never feature, in new prose. PASS.
- **No full heavy suites.** Only `tests/docs`, touched files and named gate files run. PASS.

## Design

### What goes and why

| Path | Verdict | Reason |
| --- | --- | --- |
| `docs/docfx.json`, 8 × `toc.yml`, `docs/templates/` | delete | D-6 "drop" at retirement. `docs/templates/index.md` only describes the template. |
| `docs/CNAME`, `docs/robots.txt`, `docs/.nojekyll`, `docs/.gitignore` | delete | DocFX `resource` entries and DocFX build-output ignores; `site/public/` carries the site's `CNAME` and `robots.txt`, and `actions/deploy-pages` needs no `.nojekyll`. |
| `plantuml_render.py`, `plantuml_invoke.py`, `plantuml_pins.json` (+ 4 tests) | delete | D-6 "port, then drop at retirement"; doc-kitty renders diagrams (#6936). |
| `generate_kitty_specs_docs.py` | delete | D-6 "drop" (dashboards dropped, ruling 3). `slugify`, its only helper a kept module imports, moves into `docs_index.py`. |
| `glossary_linker.py`, `glossary_page/` (+ test) | delete | DocFX HTML post-processor and the DocFX glossary page; nothing runs them since the cutover. The port target is doc-kitty's Contextive glossary (D-10, #6940), which reuses no Python. The glossary source `.kittify/glossaries/spec_kitty_core.yaml` stays. |
| `redirect_stub_generator.py`, `redirect_map.yaml`, `redirect_baseline_urls.json` (+ tests) | delete | Ported to `site_redirects.py` (#6933); the ledgers supersede the map and manifest. `moves_ledger.derive_redirect_map` and `moves_ledger.validate`, used only by the DocFX map, go too. |
| `capture_baseline_urls.py` (+ test) | delete | D-6 "keep for one run, then drop"; `site/url-baseline.txt` is seeded. |
| `seo_postprocess.py`, `seo_verify.py` (+ tests) | delete | D-6 "port"; Starlight emits the tags and `site_built_check_render.py` proves them on the built site. |
| `description_length_check.py`, `_published_pages.py` (+ tests) | delete | D-6 "port"; `dockitty-validate-frontmatter` enforces the description band in the build, and the published set is the contract's. No workflow runs the gate. |
| `test_publish_manifest_coherence.py`, `_publish_manifest_helpers.py` | delete | They check DocFX `toc.yml` hrefs and the DocFX map; the site's redirect coverage gate and `test_site_redirects.py` own those rules now. |
| `tests/_support/docfx_reports_guard.py` (+ test) | replace | By `tests/_support/reports_unpublished_guard.py`, which reads the contract. |
| `test_docs_seo.py` | rebase | Published set from the contract; band from the contract's `DESCRIPTION_SOFT_MIN`/`DESCRIPTION_MAX`; drop the `seo_postprocess` cases; keep the static-file check, pointed at `site/public/`. |
| `test_moves_ledger.py`, `test_one_index_per_folder.py`, `test_redirect_spine.py`, `test_rulers_blocking.py`, `test_docs_index.py`, `test_versioned_docs_integrity.py` | rebase | Read `collapse` and the contract instead of the DocFX map and `docfx.json`; drop the description-gate cases; drop `toc.yml` from file lists. |

The contract gains one public function, `published_pages(docs_root)`, the published counterpart of `unpublished_routes`, sharing its per-page predicate so the two cannot disagree.

### Decisions and alternatives

- **Delete port-verdict scripts now rather than leave them.** Leaving them would keep scripts that read `docfx.json`, which the deletion of `docfx.json` breaks. Rewriting them on the contract would keep a second description gate beside doc-kitty's. Deletion is the smaller, single-authority change.
- **Keep `glossary_linker.py`?** Rejected: it post-processes DocFX HTML and imports the deleted generator; the port (#6940) writes no Python.
- **Living-files gate as data, not an allowlist of offenders.** The excluded set is the immutable-history and generated list from the spec, the same list the operator named. A self-test proves the scan finds a planted mention.

## Project Structure

### Documentation (this mission)

```
kitty-specs/retire-docfx-01M78FG2/
├── spec.md
├── plan.md
├── tasks.md
└── tasks/
```

### Source Code (repository root)

```
docs/            # DocFX sources removed; api/ and development/ pages updated
scripts/docs/    # DocFX-only modules removed; _dockitty_contract.py gains published_pages()
site/            # ledger header comments only
tests/docs/      # deleted or rebased tests; new absence tests
tests/_support/  # reports guard replaced
tests/ci/, tests/release/  # pin tests follow the workflow edits
.github/workflows/ci-router.yml, docs-pages.yml
docs/adr/4.x/2026-10-31-1-...md  # appended amendment only
docs/changelog/unreleased/        # one fragment
```

**Structure Decision**: single repository; tests mirror their subjects.

## Implementation Concern Map

### IC-01 — Remove DocFX and rebase its tests

- **Purpose**: delete the DocFX sources and DocFX-only scripts and keep every live rule tested through the contract.
- **Relevant requirements**: FR-001 to FR-006, NFR-001 to NFR-003, C-002, C-003
- **Affected surfaces**: `docs/` DocFX files, `scripts/docs/`, `tests/docs/`, `tests/_support/`, the three terminology tests, `pyproject.toml`, `ruff.toml`, `src/specify_cli/docs/index_model.py` (comment)
- **Sequencing/depends-on**: none
- **Risks**: a kept module importing a deleted one (`docs_index` → `slugify`); ratchet files listing deleted paths.

### IC-02 — Plumbing, docs and the record

- **Purpose**: remove CI steps for deleted scripts, describe doc-kitty in living docs, record the retirement, and gate against regressions.
- **Relevant requirements**: FR-007 to FR-010, C-001, C-004, C-005
- **Affected surfaces**: `.github/workflows/ci-router.yml`, `.github/workflows/docs-pages.yml`, `tests/ci/`, `tests/release/`, `docs/api/`, `docs/development/`, `site/moves.yaml` and `site/url-baseline.txt` headers, the ADR, the changelog
- **Sequencing/depends-on**: IC-01
- **Risks**: pin tests asserting the removed jar cache; the generated retrieval index and shard timings naming deleted tests.
