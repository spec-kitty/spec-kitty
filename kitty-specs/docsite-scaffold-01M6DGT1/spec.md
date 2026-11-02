# Mission Specification: Docsite scaffold, pinned doc-kitty and the docs-site PR build job

**Mission Branch**: `issue-6930-docsite-scaffold`
**Created**: 2026-11-02
**Status**: Draft
**Input**: Issue #6930 (epic #6100, plan step S-5): "Site scaffold, pinned doc-kitty and the pull-request build job (parallel run starts)". Governed by ADR `docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md` D-1, D-2, D-8 and D-11. Operator decisions: <https://github.com/spec-kitty/spec-kitty/issues/6100#issuecomment-6544333324>.

## Context

The docsite moves from DocFX to doc-kitty. The prerequisites are merged: the sdist excludes `site/**` (#6926), `site/url-baseline.txt` and `site/moves.yaml` exist with one index per folder (#6927/#6928), and the frontmatter of `docs/` builds on doc-kitty (#6929, 640 pages in a one-off build). Nothing in the repository builds the doc-kitty site yet. This mission starts the **parallel run** (ADR D-13 step 1): every pull request that touches the docs builds the doc-kitty site, while DocFX keeps deploying the live site.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A docs pull request builds the doc-kitty site (Priority: P1)

A contributor changes a page under `docs/`. The pull request runs a `docs-site` job that installs the pinned toolkit with the frozen lockfile and no token, builds the full published corpus and uploads the built site as an artifact, so a broken page shows up on the pull request rather than at cutover.

**Why this priority**: it is the parallel run itself; the later steps (#6931-#6938) all build on it.

**Independent Test**: the router's parsed authority (`scripts/ci/gate_selection.py`) selects the `docs-site` job for a `docs/**` or `site/**` change and for no unrelated change; the job's steps install with `--frozen-lockfile`, build and upload `site/dist`.

**Acceptance Scenarios**:

1. **Given** a pull request that changes `docs/guides/x.md`, **When** the router computes its selection, **Then** the `docs-site` job is selected.
2. **Given** a pull request that changes only `site/package.json`, **When** the router computes its selection, **Then** the `docs-site` job is selected and no code shard is.
3. **Given** a pull request that changes only `src/specify_cli/status/store.py`, **When** the router computes its selection, **Then** the `docs-site` job is not selected.
4. **Given** the `docs-site` job runs, **When** it installs the site, **Then** it uses `pnpm install --frozen-lockfile`, receives no secret or PAT, and every action is pinned by a 40-character SHA.

---

### User Story 2 - A maintainer builds the site locally and bumps doc-kitty (Priority: P2)

A maintainer runs `make docs-site` to install and build the site exactly as CI does, and `make docs-site-bump REF=<tag|sha>` to move the doc-kitty pin (ADR D-2 steps 1 and 2: resolve the ref to a commit, rewrite the pin and the peer ranges, reinstall).

**Why this priority**: local reproduction of the gate and a single bump procedure keep the pin honest; without them a bump is a hand edit.

**Independent Test**: `make docs-site` exits 0 and reports the page count; the bump helper, run against a fixture `package.json` and a fixture toolkit manifest, rewrites the SHA and the `astro` / `@astrojs/starlight` / `@astrojs/markdown-remark` ranges.

**Acceptance Scenarios**:

1. **Given** a clean checkout with node >= 22.22 and pnpm, **When** `make docs-site` runs, **Then** it exits 0 and the build reports about 640 pages.
2. **Given** a ref that resolves to a commit, **When** `make docs-site-bump REF=<ref>` runs, **Then** `site/package.json` names that 40-character commit and the peer ranges of the toolkit at that commit.
3. **Given** a ref that resolves to nothing, **When** the bump runs, **Then** it fails and leaves `site/package.json` unchanged.

---

### User Story 3 - The site leaves out exactly the unpublished folders, from one authority (Priority: P2)

The site excludes `archive`, `reports`, `convergence` and `changelog/unreleased`, and uses `['README', 'index']` as index basenames. These come from `scripts/docs/_dockitty_contract.py`, the single authority #6929 established; the site does not keep a second copy that can drift.

**Independent Test**: a parity test fails when the site's exclusion list or index basenames differ from `EXCLUDED_FOLDERS` / `INDEX_BASENAMES`.

**Acceptance Scenarios**:

1. **Given** `EXCLUDED_FOLDERS` gains a folder, **When** the parity test runs without regenerating the site's copy, **Then** it fails naming the drift.

---

### Edge Cases

- A pull request on a fork: the job must run (pull_request runs everywhere) and needs no secret.
- A push to `main` in a fork: the job must skip, through the fork-guarded `changes` job it depends on.
- A pull request labelled `pr:pause-ci`: the job must not run (the `changes` job carries the pause guard).
- A legacy `.html` redirect key: not passed through Astro `redirects` (doc-kitty #253 makes it fatal on static output); redirects are #6933's scope.
- PlantUML sources: the build must not reach `plantuml.com`; the PlantUML service is #6936's scope.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | site/ project | As a maintainer, I want a `site/` Astro project (`package.json` pinning `@spec-kitty/doc-toolkit` as `github:spec-kitty/doc-kitty#<sha>&path:/src`, `pnpm-lock.yaml`, `astro.config.mjs`, `src/content.config.ts`, `.env.production`, `public/CNAME`, `public/robots.txt`, a 404 page with the `/kitty-specs/` notice) so that the doc-kitty site builds from `../docs`. | High | Open | [build] | no — the build must emit pages from `../docs` |
| FR-002 | Site configuration values | As a maintainer, I want `site: https://docs.spec-kitty.ai`, `base: '/'`, `docsDir: '../docs'`, `indexBasename: ['README', 'index']` and `DK_PUBLISH_DRAFTS=off` in `.env.production` so that the site matches ADR D-1 and D-8. | High | Open | [build] | no — asserted against the committed files |
| FR-003 | Single exclusion authority | As a maintainer, I want the site's folder exclusion and index basenames taken from `scripts/docs/_dockitty_contract.py` (via a generated, committed JSON checked for parity) so that there is one authority. | High | Open | [build] | no — paired with a drifted-copy negative control |
| FR-004 | Section registry | As a maintainer, I want `docs/_meta/sections.yaml` registering every published top-level section, `development` as its own section and `plans` with restricted feeds, so that doc-kitty knows the sections (ADR D-8). | Medium | Open | [build] | no — every published top-level folder must be registered |
| FR-005 | make docs-site | As a maintainer, I want `make docs-site` to install with the frozen lockfile and build so that I reproduce the CI build locally. | High | Open | [build] | no — exit 0 with a page count |
| FR-006 | make docs-site-bump | As a maintainer, I want `make docs-site-bump REF=<tag|sha>` to resolve the ref, rewrite the pin and the peer ranges, and reinstall (ADR D-2 steps 1-2). | Medium | Open | [build] | no — fixture test rewrites SHA and ranges; unresolvable ref refused |
| FR-007 | docs-site router job | As a contributor, I want a `docs-site` job in `ci-router.yml` gated on a `docs_site` filter group (`docs/**`, `site/**`, the job's own workflow and its helper scripts) parsed by `gate_selection.py`, that installs with `--frozen-lockfile`, builds and uploads `site/dist`. | High | Open | [build] | no — selection tests on doc, site and src paths |
| FR-008 | Not yet required | As the operator, I want the `docs-site` job kept out of `router-gate`'s `needs:` so that it becomes required only in #6937. | High | Open | [build] | no — asserted absent |
| FR-009 | dockitty-* calls carry --astro-config | As a maintainer, I want every `dockitty-*` invocation in the workflow and Makefile to pass `--astro-config astro.config.mjs` (ADR D-1) so that a later gate never misreads the index files. | Medium | Open | [build] | yes — no gate is wired yet; paired with a self-mutation fixture that the check rejects |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No credential | The job declares no `secrets.*`, no PAT and only `contents: read`; `pnpm install --frozen-lockfile` succeeds with no token. | Security | High | Open |
| NFR-002 | Pinned inputs | Every `uses:` in the job is pinned to a 40-character commit SHA; doc-kitty is pinned to a 40-character commit in `package.json` and the lockfile. | Security | High | Open |
| NFR-003 | Bounded runtime | The job carries a `timeout-minutes` of at most 20. | Reliability | Medium | Open |
| NFR-004 | Code quality | New Python passes ruff, ruff format and mypy with zero findings; complexity <= 15. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | DocFX unchanged | `.github/workflows/docs-pages.yml` is not modified; DocFX keeps deploying. | Technical | High | Open |
| C-002 | Non-src group | The new filter group carries no `src/` glob and stays out of the FR-004 `unmatched` union. | Technical | High | Open |
| C-003 | Separate toolchain | `site/` has its own `package.json` and `pnpm-lock.yaml`; the root `package.json` is untouched. | Technical | Medium | Open |
| C-004 | Packaging | `site/**` stays out of the sdist and the wheel (`test_packaging_safety.py`). | Technical | High | Open |
| C-005 | Out of scope | No redirects (#6933), `llms.txt` (#6934), SEO/alert parity (#6935), PlantUML service (#6936), required gate (#6937), deploy/cutover (#6938), frontmatter completion (#6931), publication rules beyond the build's needs (#6932). | Business | High | Open |
| C-006 | Upstream gaps | A doc-kitty gap is filed in `spec-kitty/doc-kitty`, not worked around locally (ADR D-14). | Technical | Medium | Open |

### Key Entities

- **Site project** (`site/`): the Astro sub-project that reads `../docs`.
- **Toolkit pin**: the doc-kitty commit in `site/package.json` and `site/pnpm-lock.yaml`.
- **Site contract** (`site/dockitty-contract.json`): the generated projection of `_dockitty_contract.py`'s exclusion list and index basenames.
- **Section registry** (`docs/_meta/sections.yaml`).
- **`docs_site` filter group** and **`docs-site` job** in `ci-router.yml`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The `docs-site` job builds the full published corpus (about 640 pages) on this mission's pull request and uploads `site/dist`. — [build] · no-op passable: no
- **SC-002**: `make docs-site` exits 0 locally with about 640 pages. — [build] · no-op passable: no
- **SC-003**: The router, fork-guard and routing tests cover the job, and the packaging test still excludes `site/**` from the sdist. — [build] · no-op passable: no
- **SC-004**: `pnpm install --frozen-lockfile` passes in CI with no token. — [build] · no-op passable: no
