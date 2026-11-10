# Implementation Plan: Docsite publication rules, llms.txt and render parity

**Branch**: `kitty/mission-docsite-publication-llms-parity-01M70Z7A` → lands on `issue-6932-docsite-publication-llms-parity` (based on PR #7486) | **Date**: 2026-11-09 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/docsite-publication-llms-parity-01M70Z7A/spec.md`

## Summary

Extend the single authority `scripts/docs/_dockitty_contract.py` with the draft-only folders and an `unpublished_routes(docs_root)` derivation (excluded folders + draft/unpublished pages by the existing `is_published`), projected to `site/dockitty-contract.json` where JS needs it (the `llms.txt` version stance). Add a standard-library built-site check, `scripts/docs/site_built_check.py`, that walks `site/dist` and fails when any unpublished route appears on a page, hub link, the sitemap, `llms.txt`, the agent index, `okf/` or the pagefind index, and (later WPs) when `llms.txt` lacks the stance or a page lacks its SEO tags or shows a literal alert marker; it is proven by mutant fixtures. Wire, in the shared `docs-site-build.yml` and the `make docs-site` target, `dockitty-validate-frontmatter` and `dockitty-check-links --strict` (both `--astro-config astro.config.mjs`) after install and the built-site check plus `dockitty-assert-no-broken-links` after the build. Content: flip the 12 non-draft working-note pages to `doc_status: draft` (frontmatter only), `git mv` the retired hosted/sync pages and `sync-workspaces` under `docs/archive/<section>/` with append-only `site/moves.yaml` rows to their section hub, and reword published links into them. Site: mount a thin `llms.txt` wrapper over doc-kitty's `llmsTxtRoute` that inserts the stance (doc-kitty #265 has no preamble option), mount `agentIndexRoute` at `/api/index.json`, set `githubAlerts: true`. Amend ADR D-8 (the loader-filter shim it describes never existed: doc-kitty's `exclude` does the job) as an amendment section. A parity checklist against DocFX's SEO rules lands in the mission's `research/`.

## Technical Context

**Language/Version**: Python 3.11+ (stdlib only for scripts run on the runner's `python3`); TypeScript/Astro pages in `site/src/pages`; GitHub Actions YAML
**Primary Dependencies**: doc-kitty v0.7.0 (`5acb83c`, already pinned) — `llmsTxtRoute`, `agentIndexRoute`, `githubAlerts`, `exclude`, `dockitty-validate-frontmatter`, `dockitty-check-links`, `dockitty-assert-no-broken-links`. No new package dependency.
**Storage**: N/A (files)
**Testing**: pytest for the contract predicates and the built-site check (fixture `dist` trees + one mutant per surface); the real check runs in the `docs-site` job over the real build; `make docs-site` locally (page count recorded)
**Target Platform**: GitHub-hosted `ubuntu-24.04` runner; local `make docs-site`
**Project Type**: single (docs + site sub-project + CI)
**Performance Goals**: added steps ≤ 3 min on CI (NFR-001)
**Constraints**: C-001..C-007 (immutable bodies, single authority, DocFX untouched, bot surfaces untouched, scope, no new ratchets, upstream-first)
**Scale/Scope**: ~12 frontmatter flips, ~10 moves, ~20 link rewordings, 1 new script + tests, 2 site pages, workflow/Makefile steps, 1 ADR amendment

## Charter Check

- **Single canonical authority:** unpublished set derived from the contract module + frontmatter + `sections.yaml`; no second list (C-002). The stance text gets one home (contract module → JSON projection); `docs/llms.txt` keeps its copy only until #6938 deletes it (temporary duplication recorded as priced debt, removed at cutover). PASS.
- **ATDD-first, with lasting value (#7484):** the acceptance test is the built-site check with mutant fixtures, committed red (on fixtures that model the current, wrong output) before the fix; no YAML-shape restatement tests. PASS (planned).
- **Immutable history:** frontmatter-only flips under `plans/`; moves are path changes with unchanged bodies; ADR D-8 gets an amendment section. PASS.
- **Gate discipline (SO#5):** the new gates are the ones D-11 already prescribes; no allowlist. If the strict link gate needs an exception, it is listed as priced debt in the PR. PASS.
- **Canonical sources / upstream-first:** doc-kitty gaps (#265 preamble, per-file exclude, unconditional machine-index line, no exported built-artifact check) are filed or referenced upstream before the wrapper lands (C-007). PASS (planned).
- **Terminology Canon:** stance text and reworded links are user-facing prose: run `tests/architectural/test_no_legacy_terminology.py`.

## Project Structure

### Documentation (this mission)

```
kitty-specs/docsite-publication-llms-parity-01M70Z7A/
├── spec.md, plan.md, research.md, data-model.md, quickstart.md
├── research/code-grounding.md
├── research/seo-parity-checklist.md     # WP04 output
└── tasks.md, tasks/
```

### Source Code (repository root)

```
scripts/docs/_dockitty_contract.py       # DRAFT_FOLDERS, LLMS_STANCE, unpublished_routes()
scripts/docs/site_contract.py            # projects llmsStance into site/dockitty-contract.json
scripts/docs/site_built_check.py         # NEW: built-site check (stdlib), surfaces registry
site/dockitty-contract.json              # regenerated
site/astro.config.mjs                    # githubAlerts: true; comment update
site/src/pages/llms.txt.ts               # NEW: stance wrapper over llmsTxtRoute
site/src/pages/api/index.json.ts         # NEW: agentIndexRoute
.github/workflows/docs-site-build.yml    # gate + check steps
Makefile                                 # docs-site target mirrors the steps
docs/plans/{engineering-notes,investigations,research}/**  # frontmatter flips
docs/archive/<section>/...               # moved retired pages
docs/** (published pages)                # reworded inbound links
site/moves.yaml, site/url-baseline.txt   # append-only rows
docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md  # D-8 amendment section
tests/docs/test_site_built_check.py      # NEW: fixtures + mutants
tests/docs/test_dockitty_contract.py, tests/docs/test_site_scaffold.py, tests/ci/test_docs_site_job.py
```

**Structure Decision**: one built-site check script with a per-surface registry so later slices (#6933 redirects, #6936 diagrams) add surfaces without a second checker.

## Implementation Concern Map

### IC-01 — Unpublished set and the built-site check

- **Purpose**: one definition of what is not published, and proof over the real build that nothing unpublished leaks.
- **Relevant requirements**: FR-003, FR-004, FR-005, NFR-001..003, SC-002, SC-005
- **Affected surfaces**: `_dockitty_contract.py`, `site_contract.py`, `site/dockitty-contract.json`, `site_built_check.py`, `docs-site-build.yml`, `Makefile`, tests
- **Sequencing/depends-on**: none
- **Risks**: the strict link gate may already be red on the current tree (measure first); pagefind index is binary-chunked (check its fragment/metadata JSON, not the wasm).

### IC-02 — Publication content changes

- **Purpose**: unpublish working notes and retired pages without breaking links or history.
- **Relevant requirements**: FR-001, FR-002, FR-010, SC-001
- **Affected surfaces**: `docs/plans/**` frontmatter, `docs/archive/**`, published pages linking to them, `site/moves.yaml`, `site/url-baseline.txt`, ADR D-8 amendment
- **Sequencing/depends-on**: IC-01 (the gates that prove it)
- **Risks**: DocFX's own TOC/link checks over moved files (DocFX keeps deploying); bot surfaces go stale (expected, C-004); immutable bodies linking to moved pages.

### IC-03 — `llms.txt` and agent index

- **Purpose**: generated `llms.txt` with the version stance, resolvable machine index.
- **Relevant requirements**: FR-006, FR-007, SC-003
- **Affected surfaces**: `site/src/pages/llms.txt.ts`, `site/src/pages/api/index.json.ts`, stance in the contract + projection, `site_built_check.py` llms surface, `dockitty-assert-no-broken-links` step
- **Sequencing/depends-on**: IC-01
- **Risks**: `dist/api/` shared with the `docs/api/` section; wrapper must stay thin and cite doc-kitty #265.

### IC-04 — Render parity

- **Purpose**: alerts render; SEO tags proven on every page; parity checklist vs DocFX.
- **Relevant requirements**: FR-008, FR-009, SC-004
- **Affected surfaces**: `site/astro.config.mjs` (`githubAlerts`), `site_built_check.py` render surface, `research/seo-parity-checklist.md`
- **Sequencing/depends-on**: IC-01
- **Risks**: doc-kitty #295 (no `starlight.head`); DocFX-only rules (JSON-LD dropped by ruling, default-description detection) need an explicit disposition.
