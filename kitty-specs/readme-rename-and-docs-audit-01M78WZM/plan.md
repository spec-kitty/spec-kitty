# Implementation Plan: Rename section indexes to README.md; docs staleness inventory and retired-surface gate

**Branch**: `kitty/mission-readme-rename-and-docs-audit-01M78WZM` (lands on `issue-6939-readme-rename-and-audit`) | **Date**: 2026-11-12 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/readme-rename-and-docs-audit-01M78WZM/spec.md`

## Summary

Two work packages, in order. WP01 renames the 59 `docs/**/index.md` section indexes to `README.md` (#6939), records each rename in the moves ledger, rewrites links through it, narrows the site's `indexBasename` to `README` and updates every reader. WP02 builds the staleness inventory of the published living pages on the final paths, adds a retired-surface gate backed by one shared retired-surface authority and a shrink-only burn-down list, wires the gate into the always-on `docs-lint` job, and writes the per-section page lists for #7522–#7528 (#7520).

## Technical Context

**Language/Version**: Python 3.11+ (scripts and tests); the site is Astro + doc-kitty under `site/` (pnpm 10.28.0, Node 22).
**Primary Dependencies**: PyYAML (ledgers), `scripts/docs/_dockitty_contract.py` (published set, index basenames), `scripts/docs/moves_ledger.py`, the doc-kitty gates (`dockitty-check-links`, `dockitty-check-redirect-coverage`).
**Storage**: committed files only (`site/moves.yaml`, `site/dockitty-contract.json`, the burn-down YAML, the Mission's page lists).
**Testing**: pytest under `tests/docs`, `tests/ci`, the implicated `tests/architectural` gates; the doc-kitty build and gates via `make docs-site` when Docker is available.
**Target Platform**: GitHub Actions `ci-router.yml` (`docs-lint`, `tests (docs)`, `docs-site`).
**Project Type**: single repository.
**Performance Goals**: the retired-surface gate under 10 s, no git history (NFR-002).
**Constraints**: immutable bodies change link targets only (C-001); bot-owned generated surfaces untouched (C-002); the moves ledger is append-only (C-005).
**Scale/Scope**: 59 renamed files; about 160 files under `docs/` naming an `index.md`; about 340 published living pages in the inventory.

## Charter Check

- **Single canonical authority.** The retired set gets one home shared by the code gate and the docs gate (D-7 below). The inventory reuses the published set (`_dockitty_contract`), the audience field and the committed CLI command tree; it adds no second source for any fact.
- **ATDD-first.** WP01 opens with the basename ratchet (red on the tree), the ledger return test and the redirect-map invariance test. WP02 opens with the gate and inventory acceptance tests on fixtures.
- **Architectural gate discipline.** The retired-surface gate has a planted positive control, refuses stale burn-down entries and is size-ratcheted in `tests/architectural/_baselines.yaml` (burn-down policy). Its allowlist is priced debt: each entry names a section sub-issue (#7522–#7528), the owner epic #3891.
- **Terminology.** Mission, never Feature; `consolidate`, never `merge` for lane consolidation.
- **Tracker rule.** The charter asks an agent to assign the ticket; the operator's brief forbids changing #6939's assignee or labels. The brief wins (recorded, not silently skipped).

## Design decisions

### D-1 The rename covers 59 files, all of them

`docs/templates/index.md` left with the DocFX template (#6943), so 59 of the issue's 60 remain. The 4 folders #6928 resolved are among them and rename too: D-1's "after DocFX retirement, all 60 `index.md` become `README.md`". The reused #7040 map is the list of 60 pairs minus `docs/templates`.

### D-2 The ledger records each rename, and a return into a route is not a cycle

Each rename is appended as `/x/index.html -> /x/README.html` (ref `#6939`). Eight folders moved `README.md` -> `index.md` earlier (#3914, #6928), so their new entry points back at a route that already has a move away. `moves_ledger.collapse` therefore reads a later entry *into* a route as superseding that route's earlier move away: the route is live again. A move of a route to itself is still refused as a cycle. This keeps the ledger append-only and gives the rewriters and the redirect generator one history. Recorded in the ADR amendment.

### D-3 The redirect map does not change

`site_redirects` folds a legacy `dir/index.html` and `dir/README.html` to `dir/` by the legacy site's own names, independent of the narrowed `INDEX_BASENAMES`, and rule 3 now asks only whether a `dir/index.html` route ends at its own live directory page, moved or not. Result: `site/legacy-redirects.json` is byte-identical (prototype verified). A moved route must still be in the URL baseline, except an index-basename rename (`from` and `to` fold to the same directory): it keeps its directory URL, so it creates no URL to protect. That covers `assets/`, `contracts/` and the 8 archived indexes, which have no baselined `dir/index.html`. One predicate in `moves_ledger` (`is_index_rename`) serves the baseline test and `rename_reconcile`'s forward check (every other move must be a redirect key; an index rename needs none, rule 3).

### D-4 Links are rewritten from the ledger's #6939 entries, link targets only in history

- The pairs are the ledger's own: `moves_ledger.source_pairs` over the `#6939` entries of `site/moves.yaml`, nothing typed by hand.
- A link target (inline `](…)`, reference definition, `href`, an anchored `docs/…` target or a `github.com/…/blob/<ref>/docs/…` URL) that resolves to a renamed source has its `index.md` segment replaced by `README.md`; the rest of the target, anchors included, is kept byte for byte.
- Living pages and repository files (`AGENTS.md`, the `src/` diagram template, scripts, `site/link-debt.json`) also get exact path mentions (`docs/x/index.md`) rewritten.
- Immutable pages (ADRs, `plans/`, `reports/`, `changelog/`, `archive/`) change link targets only (ADR D-7). Prose and frontmatter that name a path are history and stay. Evidence: every changed immutable line differs from its base only inside a link target, checked by a scratch verifier whose result goes in the PR.
- Why not the existing tools as they are: `bulk_ref_rewrite.py` rewrites prose in `plans/` and `archive/` and replays the whole ledger (minutes per run); `relative_link_fixer.py` heals only bare-relative links, resolves a link from the file's pre-move folder first (it sent `guides/how-to/monitoring/use-dashboard.md`'s `index.md` link to `guides/README.md` in the prototype) and also "heals" unrelated dead links by basename. Its `--check` mode stays the body-link gate after the rewrite.

### D-5 Generated surfaces stay bot-owned

The retrieval index and page inventory are not edited (C-002). `check_docs_freshness` reports their lag as warnings. `check_generated_docs_untouched` keys ADR era table rows by era folder, not by file, so a table that moves from `index.md` to `README.md` adds no new rows. If a gate goes red only because of the bot-owned surfaces, the PR says so.

### D-6 The inventory is generated on demand, with a dated snapshot in the Mission directory

- **Command**: `python -m scripts.docs.staleness_audit --out <dir>` writes `inventory.json` (machine-readable, every field) and `page-lists.md` (per section). It reads the published set from `_dockitty_contract` minus `adr/`, `plans/`, `reports/`, `changelog/`, `archive/`.
- **Why not commit it under `docs/`**: its main field comes from git history and changes with every docs commit. A committed copy would drift on every merge and conflict with every docs PR in flight, the problem that moved the page inventory and retrieval index to a post-merge bot. A CI artifact would be one more job for a report that people read when a section pass starts, not on every PR.
- **What is committed**: a dated snapshot in this Mission's directory (`kitty-specs/<mission>/audit/`), the baseline the section passes start from and the source of the page lists posted to #7522–#7528. Kept under 200 KB.
- **Fit with `check_docs_freshness.py`** (revised in WP02): that script is the publication gate's orchestrator for the generated surfaces, and no CI job runs it. The inventory is a report, not a gate, so it is a sibling module; the retired-surface gate runs where it is enforced, the always-on `docs-lint` job, and is not wired into the orchestrator a second time. No fact gets a second source: the page set comes from `_dockitty_contract`, the retired set from `scripts/retired_surfaces.py`.
- **Last real content change**: walk `git log --follow` for the page and take the newest commit whose diff changes the body after whitespace normalisation (frontmatter excluded). Renames from WP01 are followed.
- **Code paths and commands**: paths matching `src/…`, `scripts/…`, `tests/…`, `.github/…` and the like, checked with `Path.exists()`; `spec-kitty …` commands checked against the committed completion manifest `src/specify_cli/_completion_manifest.json`, kept in step with the live CLI by its own test.
- **Reader**: the frontmatter `audience` profiles under `docs/context/audience/`.
- **Text-drawn diagrams**: unlabelled or `text` code fences with box-drawing characters or ASCII arrow/box art.
- **Divio type**: the frontmatter `kind`; mixed when a page carries headings or structures of a second type (heuristic, reported as a hint).

### D-7 One retired-surface authority

`tests/architectural/test_no_retired_subsystems.py` holds the retired code paths and CLI prefixes. They move to `scripts/retired_surfaces.py`, which the arch gate imports under its old names, so nothing else changes for it. The same module adds the documentation-level retirements that predate the code list: `src/doctrine/`, `src/specify_cli/glossary/`, `spec-kitty merge`, Blacksmith, Zeitgeist, `saas_client`, and the #6164 CLI entries. The docs gate and the inventory read it; nothing else lists retired surfaces.

### D-8 The gate and its burn-down

- `python -m scripts.docs.retired_surface_gate` scans the published living pages (same set as the inventory, body only), compares (page, surface) hits with `scripts/docs/retired_surface_burndown.yaml`, and fails on a new hit or a stale entry, printing page, line and surface.
- Each burn-down entry names the page, the surfaces and the section sub-issue (#7522–#7528) that drains it.
- The entry count is a size ratchet in `tests/architectural/_baselines.yaml` (`test_ratchet_baselines`), so the list only shrinks.
- CI: one more command in the `docs-lint` job (always-on, runs no pytest), with its job pin test and the retirement scrub record updated where they transcribe the job.

## Project Structure

### Documentation (this mission)

```
kitty-specs/readme-rename-and-docs-audit-01M78WZM/
├── spec.md
├── plan.md
├── tasks.md
├── tasks/WP01-*.md, WP02-*.md
└── audit/              # WP02: inventory snapshot + per-section page lists
```

### Source Code (repository root)

```
docs/**/README.md                       # renamed from index.md (59)
site/moves.yaml                         # +59 entries
site/dockitty-contract.json             # indexBasename ['README']
scripts/docs/_dockitty_contract.py      # INDEX_BASENAMES
scripts/docs/moves_ledger.py            # return supersedes move away
scripts/docs/site_redirects.py          # legacy index fold, rule 3
scripts/docs/freshen_adr_inventory.py   # README era landing page
scripts/ci/check_generated_docs_untouched.py, generated_docs_surfaces.py, regen_docs_index.py
scripts/retired_surfaces.py             # WP02: the one retired-surface authority
scripts/docs/staleness_audit.py         # WP02: the inventory
scripts/docs/retired_surface_gate.py    # WP02: the gate
scripts/docs/retired_surface_burndown.yaml
tests/docs/test_section_index_basename.py, test_moves_ledger.py, test_site_redirects.py, ...
tests/docs/test_staleness_audit.py, test_retired_surface_gate.py
.github/workflows/ci-router.yml         # docs-lint step
```

**Structure Decision**: single repository; scripts under `scripts/docs/`, tests under `tests/docs/` and `tests/ci/`.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Moving the retired lists out of an arch test | one authority for the code gate and the docs gate (FR-010) | a second list with a parity test is two authorities |

## Implementation Concern Map

### IC-01 — Rename and ledger
- **Purpose**: rename the 59 indexes and record them so the tools agree.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-005, FR-007
- **Affected surfaces**: `docs/**`, `site/moves.yaml`, `site/dockitty-contract.json`, `scripts/docs/moves_ledger.py`, `_dockitty_contract.py`, `site_redirects.py`
- **Sequencing/depends-on**: none
- **Risks**: a ledger return read as a cycle; a redirect key colliding with a live page.

### IC-02 — Links and readers
- **Purpose**: no broken link and no reader naming `index.md`.
- **Relevant requirements**: FR-004, FR-006, FR-008
- **Affected surfaces**: link targets across `docs/`, `AGENTS.md`, `src/` templates; `scripts/docs/*`, `scripts/ci/*`, the docs-index workflow, `tests/docs`, `tests/ci`
- **Sequencing/depends-on**: IC-01
- **Risks**: rewriting immutable prose; tests that read the real tree by path.

### IC-03 — Inventory
- **Purpose**: the per-page audit the section passes read.
- **Relevant requirements**: FR-009, FR-014
- **Affected surfaces**: `scripts/docs/staleness_audit.py`, the Mission's `audit/`
- **Sequencing/depends-on**: IC-01, IC-02 (final paths)
- **Risks**: git-history cost; heuristic diagram and Divio detection over-reporting.

### IC-04 — Retired-surface authority and gate
- **Purpose**: one retired set and a shrink-only gate over the published living pages.
- **Relevant requirements**: FR-010, FR-011, FR-012, FR-013
- **Affected surfaces**: `scripts/retired_surfaces.py`, `tests/architectural/test_no_retired_subsystems.py`, the gate and burn-down, `_baselines.yaml`, `test_ratchet_baselines.py`, `ci-router.yml`, `tests/ci/test_docs_lint_job.py`
- **Sequencing/depends-on**: IC-01
- **Risks**: false hits on live identifiers (`merge-driver-*`, `charter sync`).

### IC-05 — Record
- **Purpose**: ADR amendment and changelog fragment.
- **Relevant requirements**: FR-015
- **Affected surfaces**: `docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md` (append only), `docs/changelog/unreleased/`
- **Sequencing/depends-on**: IC-01..IC-04
- **Risks**: none beyond the changelog style and spelling gates.

## Test plan

- `uv run --frozen pytest tests/docs -n 4 --dist loadfile --tb=line -q`; every touched test file; `tests/ci` job pins; the architectural gates `test_retirement_scrub.py`, `test_no_duplicate_suite_execution.py`, `test_ci_router_transcription_guards.py`, `test_module_shard_registry.py`, `test_coverage_breadth.py`, `test_no_legacy_terminology.py`, `test_legacy_docsite_named_nowhere.py`, `test_no_retired_subsystems.py`, `test_ratchet_baselines.py`.
- `python -m scripts.docs.site_redirects --check`, `spec-kitty regen --check`, doc-kitty's frontmatter and link gates, `make docs-site` when Docker is available.
- ruff, `ruff format --check --force-exclude`, `mypy --strict` on touched modules, actionlint on `ci-router.yml`.
