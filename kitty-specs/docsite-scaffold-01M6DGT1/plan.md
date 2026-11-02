# Implementation Plan: Docsite scaffold, pinned doc-kitty and the docs-site PR build job

**Branch**: `issue-6930-docsite-scaffold` | **Date**: 2026-11-02 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/docsite-scaffold-01M6DGT1/spec.md`

## Summary

Add the `site/` doc-kitty project that builds `../docs`, pinned to doc-kitty `45e455b154b3ea97e9e1914a9962bf0aea55d043` (doc-kitty `main` HEAD on 2026-11-02, toolkit 0.6.0) as a pnpm git dependency; take its folder exclusion and index basenames from `scripts/docs/_dockitty_contract.py` through a generated, parity-tested JSON; add `docs/_meta/sections.yaml`; add `make docs-site` and `make docs-site-bump REF=…`; and add a `docs-site` job to `ci-router.yml` behind a new non-src `docs_site` filter group that installs with `--frozen-lockfile`, builds and uploads `site/dist`, outside `router-gate`'s `needs:`. Grounding: [research/code-grounding.md](research/code-grounding.md).

## Technical Context

**Language/Version**: Python 3.11+ (helpers, tests); Node >= 22.22 with pnpm 10.28 (site); Astro 7.4 / Starlight 0.42 (toolkit peers)
**Primary Dependencies**: `@spec-kitty/doc-toolkit` (git dependency by commit), `astro`, `@astrojs/starlight`, `@astrojs/markdown-remark`
**Storage**: files (`site/`, `docs/_meta/sections.yaml`)
**Testing**: pytest (`tests/ci/`, `tests/docs/`, packaging, named architectural router gates); local `make docs-site` build
**Target Platform**: GitHub Actions `ubuntu-24.04`; maintainer machines
**Project Type**: single repository with a separate `site/` Node sub-project
**Performance Goals**: build job under 20 minutes (`timeout-minutes: 20`)
**Constraints**: no PAT/secret; SHA-pinned actions; DocFX workflow untouched; job not required yet
**Scale/Scope**: about 640 published pages

## Charter Check

- **Single canonical authority**: the exclusion list stays in `_dockitty_contract.py`; the site reads a generated projection and a parity test fails on drift. Routing stays in the two router authorities parsed by `gate_selection.py`; no second map.
- **ATDD-first**: the routing/job acceptance tests, the parity test and the bump-helper tests are committed red before the implementation.
- **Architectural gate discipline**: the `--astro-config` invariant is a non-vacuous structural test with a self-mutation fixture.
- **Canonical sources**: canonical templates; doc-kitty consumed per ADR D-2; upstream gaps filed upstream.
- **Terminology**: Mission, never feature; no `ceremony`.
- **No full heavy suites**: targeted files and named architectural router gates only.

No violations.

## Project Structure

### Documentation (this mission)

```
kitty-specs/docsite-scaffold-01M6DGT1/
├── spec.md
├── plan.md
├── research/code-grounding.md
├── traces/{approach,design-decisions,tooling-friction}.md
├── tasks.md
└── tasks/
```

### Source Code (repository root)

```
site/
├── package.json            # pinned toolkit + peers, packageManager, onlyBuiltDependencies
├── pnpm-lock.yaml
├── astro.config.mjs        # reads dockitty-contract.json
├── dockitty-contract.json  # GENERATED from scripts/docs/_dockitty_contract.py
├── .env.production         # DK_PUBLISH_DRAFTS=off
├── src/content.config.ts   # docKittyDocsLoader({ base: '../docs' }), no shim
├── src/pages/404.astro     # /kitty-specs/ notice
└── public/{CNAME,robots.txt}
docs/_meta/sections.yaml
scripts/docs/site_contract.py     # writes/checks site/dockitty-contract.json
scripts/docs/site_bump.py         # D-2 steps 1-2 helper
Makefile                          # docs-site, docs-site-bump
.github/workflows/ci-router.yml   # docs_site group, output row, docs-site job
tests/release/ci_retirement_scrub.json  # docs_site row
tests/ci/test_docs_site_job.py
tests/docs/test_site_scaffold.py
```

**Structure Decision**: one sub-project `site/` beside `docs/` (ADR D-1); Python helpers under `scripts/docs/` next to `_dockitty_contract.py`.

## Implementation Concern Map

### IC-01 — Site project and single exclusion authority

- **Purpose**: a `site/` project that builds the published corpus, with its exclusion/index config projected from the one Python authority.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004
- **Affected surfaces**: `site/**`, `docs/_meta/sections.yaml`, `scripts/docs/site_contract.py`, `.gitignore`
- **Sequencing/depends-on**: none
- **Risks**: `docsDir: '../docs'` is untested upstream (ADR D-1 spike built it; #6929 rebuilt it); every `exclude` folder must exist with exact case; `_meta/` is reserved by doc-kitty; `sections.yaml` ids must match top-level folders.

### IC-02 — Local build and bump

- **Purpose**: `make docs-site` reproduces CI; `make docs-site-bump REF=` implements ADR D-2 steps 1-2.
- **Relevant requirements**: FR-005, FR-006, FR-009
- **Affected surfaces**: `Makefile`, `scripts/docs/site_bump.py`
- **Sequencing/depends-on**: IC-01
- **Risks**: the toolkit's peer ranges must be read from the pinned commit's `src/package.json` (network: `raw.githubusercontent.com` / `git ls-remote`); keep the network seam injectable for tests.

### IC-03 — Router job

- **Purpose**: the `docs-site` job in `ci-router.yml` behind the `docs_site` group.
- **Relevant requirements**: FR-007, FR-008, FR-009, NFR-001..003
- **Affected surfaces**: `.github/workflows/ci-router.yml`, `tests/release/ci_retirement_scrub.json`, `tests/ci/test_docs_site_job.py`
- **Sequencing/depends-on**: IC-01
- **Risks**: `_GROUP_REF` parses every `needs.changes.outputs.*`; the group must stay non-src and out of the `unmatched` union; pnpm and Node setup actions must be SHA-pinned; existing router gates may pin the job/group sets.
