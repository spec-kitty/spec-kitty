---
description: "Work packages for retiring DocFX"
---

# Work Packages: Retire DocFX

**Inputs**: Design documents from `kitty-specs/retire-docfx-01M78FG2/`
**Prerequisites**: plan.md, spec.md

**Tests**: requested. Each work package opens with an absence or invariant test that is red on the base (#7484).

**Organization**: Fine-grained subtasks (`Txxx`) roll up into two work packages. Subtasks are reference rows; completion is recorded with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first: absence test for the DocFX sources and dropped modules, plus the contract-backed published-set and reports guards | WP01 | |
| T002 | Delete the DocFX sources: `docs/docfx.json`, every `toc.yml`, `docs/templates/`, `docs/CNAME`, `docs/robots.txt`, `docs/.nojekyll`, `docs/.gitignore` | WP01 | |
| T003 | Delete the DocFX-only scripts and data, move `slugify` into `docs_index.py`, drop `moves_ledger.derive_redirect_map`/`validate`, add `published_pages()` to the contract | WP01 | |
| T004 | Delete the tests of deleted modules; rebase the tests that guard live rules; replace the reports guard | WP01 | |
| T005 | Clean ratchets and inventories: `pyproject.toml`, `ruff.toml`, the pinning-rule inventory, the retired-vocabulary exempt list; reword DocFX comments in kept scripts | WP01 | |
| T006 | Run `tests/docs`, the touched tests, the named gate files, ruff, mypy | WP01 | |
| T007 | Red-first: living-files DocFX gate with a self-test; the router jar-cache absence pin | WP02 | |
| T008 | Remove the PlantUML-jar steps from `ci-router.yml` `tests (docs)`; update `docs-pages.yml` comments; update the CI pin tests | WP02 | |
| T009 | Update living docs: `docs/api/configuration.md`, `docs/api/file-structure.md`, `docs/development/**`; reword the ledger header comments | WP02 | [P] |
| T010 | ADR 2026-10-31-1: `## Amendment 2026-11-12 (DocFX retired)` | WP02 | |
| T011 | Changelog fragment in `docs/changelog/unreleased/` | WP02 | |
| T012 | Run the CI pin tests, the gate files, actionlint, changelog style and spelling, `make docs-site` if available | WP02 | |

---

## Work Package WP01: Remove DocFX and rebase its tests (Priority: P1)

**Goal**: the DocFX sources and the DocFX-only `scripts/docs` modules are gone; every live rule they guarded is tested through `scripts/docs/_dockitty_contract.py`.
**Independent Test**: `tests/docs/test_legacy_docsite_retired.py`, the rebased `tests/docs/test_docs_seo.py`, the terminology tests through `tests/_support/reports_unpublished_guard.py`, and `pytest tests/docs` green.
**Prompt**: `tasks/WP01-remove-docfx-and-rebase-tests.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, NFR-001, NFR-002, NFR-003, C-002, C-003

### Included Subtasks

T001 Red-first absence and invariant tests (WP01)
T002 Delete the DocFX sources (WP01)
T003 Delete the DocFX-only scripts; contract `published_pages()` (WP01)
T004 Delete or rebase their tests; replace the reports guard (WP01)
T005 Ratchets, inventories, comments (WP01)
T006 Verify (WP01)

### Implementation sketch

Tests first and red; then delete sources and scripts; then fix every importer; then the ratchets.

### Dependencies and risks

- None upstream. Risk: a kept module importing a deleted one; a ratchet listing a deleted path.

---

## Work Package WP02: Plumbing, docs and the record (Priority: P2)

**Goal**: CI provisions nothing for deleted scripts, the living docs describe doc-kitty, a gate keeps DocFX out of living files, and the ADR and changelog record the retirement.
**Independent Test**: `tests/architectural/test_legacy_docsite_named_nowhere.py`, `tests/ci/test_nightly_tooling_cache.py`, `tests/release/test_release_ci_ownership.py`, `check_changelog_style`, `check_spelling --pass unreleased`.
**Prompt**: `tasks/WP02-plumbing-docs-and-record.md`
**Requirement Refs**: FR-007, FR-008, FR-009, FR-010, NFR-001, NFR-002, C-001, C-004, C-005

### Included Subtasks

T007 Red-first living-files gate and jar-cache absence pin (WP02)
T008 CI plumbing and pin tests (WP02)
T009 Living docs and ledger headers (WP02)
T010 ADR amendment (WP02)
T011 Changelog fragment (WP02)
T012 Verify (WP02)

### Dependencies and risks

- Depends on WP01. Risk: a generated file (retrieval index, shard timings) naming DocFX; it is excluded as generated, not hand-edited.
