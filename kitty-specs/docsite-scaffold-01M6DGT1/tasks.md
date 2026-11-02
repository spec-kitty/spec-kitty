---
description: "Work packages for the docsite scaffold mission (#6930)"
---

# Work Packages: Docsite scaffold, pinned doc-kitty and the docs-site PR build job

**Inputs**: `kitty-specs/docsite-scaffold-01M6DGT1/` (spec.md, plan.md, research/code-grounding.md)
**Prerequisites**: plan.md, spec.md

**Tests**: ATDD-first (charter C-011): each work package commits its failing acceptance tests before the implementation.

## Subtask Format: `[Txxx] [P?] Description`

Subtasks are reference rows; completion is recorded with `spec-kitty agent tasks mark-status <Txxx> --status done`.

---

## Work Package WP01: Site project and single exclusion authority (Priority: P1)

**Goal**: a `site/` project that builds the published corpus from `../docs`, its exclusion/index config projected from `_dockitty_contract.py`, and `docs/_meta/sections.yaml`.
**Independent Test**: `tests/docs/test_site_scaffold.py` passes; `pnpm exec astro build` in `site/` exits 0 with about 640 pages.
**Prompt**: `/tasks/WP01-site-project.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, C-001, C-003, C-004, C-005, C-006, SC-002

### Included Subtasks

T001 Commit failing acceptance tests `tests/docs/test_site_scaffold.py` (config values, parity, drift negative control, sections registry coverage)
T002 `scripts/docs/site_contract.py` (write/check `site/dockitty-contract.json`)
T003 `site/` files: `package.json`, `pnpm-lock.yaml`, `astro.config.mjs`, `src/content.config.ts`, `.env.production`, `public/CNAME`, `public/robots.txt`, `src/pages/404.astro`
T004 `docs/_meta/sections.yaml`
T005 Local build and page count

### Dependencies

- None.

### Risks & Mitigations

- `docsDir: '../docs'` is untested upstream: verified by the local build.

---

## Work Package WP02: Local build and doc-kitty bump targets (Priority: P2)

**Goal**: `make docs-site` and `make docs-site-bump REF=<tag|sha>` (ADR D-2 steps 1-2).
**Independent Test**: `tests/docs/test_site_bump.py` passes against fixtures; `make docs-site` exits 0.
**Prompt**: `/tasks/WP02-make-targets.md`
**Requirement Refs**: FR-005, FR-006, FR-009, NFR-004, SC-002

### Included Subtasks

T006 Commit failing tests `tests/docs/test_site_bump.py`
T007 `scripts/docs/site_bump.py` (resolve ref, rewrite pin + peer ranges)
T008 Makefile targets `docs-site`, `docs-site-bump`

### Dependencies

- Depends on WP01.

---

## Work Package WP03: docs-site router job (Priority: P1)

**Goal**: the `docs-site` job in `ci-router.yml` behind the non-src `docs_site` group, outside `router-gate.needs`.
**Independent Test**: `tests/ci/test_docs_site_job.py` and the named router gates pass.
**Prompt**: `/tasks/WP03-router-job.md`
**Requirement Refs**: FR-007, FR-008, FR-009, NFR-001, NFR-002, NFR-003, C-001, C-002, SC-001, SC-003, SC-004

### Included Subtasks

T009 Commit failing tests `tests/ci/test_docs_site_job.py`
T010 `docs_site` filter group + `changes.outputs` row + scrub registry row
T011 `docs-site` job (SHA-pinned pnpm/node setup, frozen install, build, upload `site/dist`)
T012 Changelog fragment

### Dependencies

- Depends on WP01, WP02.
