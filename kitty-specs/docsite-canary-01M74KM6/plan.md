# Implementation Plan: Docsite canary deploy

**Branch**: `issue-6938-docsite-canary` | **Date**: 2026-11-11 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/docsite-canary-01M74KM6/spec.md`

## Summary

Add a ledger-derived live-site probe (`scripts/docs/site_live_probe.py`) and a dispatched canary path in `.github/workflows/docs-pages.yml`. The canary calls the shared `docs-site-build.yml` with `pages-artifact: true` and a distinct Pages artifact name, publishes it with `actions/deploy-pages`, probes `https://docs.spec-kitty.ai`, and lets the existing DocFX `deploy` job republish DocFX afterwards whatever the probe said. The shared build also runs the probe against the freshly built `site/dist` over a local HTTP server, so every pull request proves the sample still derives and the built site answers it, before any canary.

## Technical Context

**Language/Version**: Python 3.11+ (standard library plus PyYAML through `scripts/docs/moves_ledger.py`); GitHub Actions YAML
**Primary Dependencies**: `urllib.request`, `http.server` (tests and the build-time local probe), the existing `scripts/docs/_dockitty_contract.py` (`redirect_stub_target`) and `scripts/docs/moves_ledger.py` readers; `actions/deploy-pages` pinned by SHA (v5.0.1, `368f825`, the commit `@v5` resolves to)
**Storage**: N/A (reads `site/url-baseline.txt`, `site/moves.yaml`, `site/legacy-redirects.json`)
**Testing**: pytest, fast marker, `tests/docs/test_site_live_probe.py` against a local `http.server` fixture; workflow pins in `tests/release/test_release_ci_ownership.py` and `tests/ci/test_docs_site_job.py`; actionlint
**Target Platform**: `ubuntu-24.04` GitHub-hosted runners; the GitHub Pages service
**Project Type**: single (repository scripts + workflows)
**Performance Goals**: probe completes in seconds when the site is healthy; at most 10 sampled URLs plus one target per stub
**Constraints**: no new dependency; per-request timeout 15 s default (cap 30 s); attempts 5 default (cap 6) with a 10 s pause; no cutover; the default deploy path keeps its behaviour
**Scale/Scope**: 1 new module, 1 test file, 2 workflows, 1 router filter line + its scrub copy, 1 ADR amendment, 1 changelog fragment

## Charter Check

- **Single canonical authority**: the probe reads the committed ledgers through the existing readers (`load_baseline`, `load_moves`, `collapse`) and judges stubs through the one predicate `redirect_stub_target`. The site is built only by the shared `docs-site-build.yml` (D-11). Pass.
- **ATDD-first**: the probe tests are written red first (committed before the module). Pass.
- **Architectural gate discipline**: the release-ownership test is extended to pin the new canary jobs exactly and the unchanged DocFX jobs; nothing is loosened. Pass.
- **Git & workflow discipline**: draft PR only; the canary is never dispatched by the Mission. Pass.
- **Packs untouched**, **ADR body unchanged** (amendment only). Pass.
- **Sonar/complexity**: functions stay under complexity 15; repeated literals become constants. Pass.

## Engineering Alignment

- **Job graph (docs-pages.yml)**:
  - `pages` (unchanged): probe-then-configure.
  - `build` (unchanged): the DocFX build; it runs in every mode, so the restore artifact `github-pages` exists before the canary publishes.
  - `canary-build` (new, dispatch + `canary` only): `uses: ./.github/workflows/docs-site-build.yml` with `pages-artifact: true` and `pages-artifact-name: github-pages-canary`.
  - `canary-deploy` (new): needs `canary-build` and `build`; core repository, `main`, both successful; environment `github-pages`; `pages: write`, `id-token: write`; `deploy-pages` with `artifact_name: github-pages-canary`.
  - `canary-probe` (new): needs `canary-deploy`; checkout, then `python3 -m scripts.docs.site_live_probe https://docs.spec-kitty.ai`; `contents: read` only.
  - `deploy` (DocFX, existing): `needs: [build, canary-probe]`; `if:` keeps the core-repository, `main` and `build` success guards and adds `(!cancelled() || inputs.canary)`. In the default path `canary-probe` is skipped, and the condition is equivalent to the old implicit `success()`. In the canary path the job runs after the probe whatever its result, and also after a cancel, so DocFX is restored.
  - A failed probe job makes the run red.
- **Shared build**: a new optional input `pages-artifact-name` (default `github-pages`) is passed to `upload-pages-artifact`'s `name`. A new step runs the probe against the built `site/dist` served on a local port with one attempt.
- **Concurrency**: the whole run sits in the `pages` group (unchanged), so the canary window queues pushes, which is why docs merges are frozen.

## Project Structure

### Documentation (this mission)

```
kitty-specs/docsite-canary-01M74KM6/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── tasks.md            # /spec-kitty.tasks
```

### Source Code (repository root)

```
scripts/docs/site_live_probe.py              # new: derive + probe + CLI
tests/docs/test_site_live_probe.py           # new: red-first tests, local http.server fixture
.github/workflows/docs-pages.yml             # canary input and jobs; deploy waits on the probe
.github/workflows/docs-site-build.yml        # pages-artifact-name input; local probe of site/dist
.github/workflows/ci-router.yml              # docs_site filter: site_live_probe.py
tests/release/ci_retirement_scrub.json       # scrub copy of the docs_site filter
tests/release/test_release_ci_ownership.py   # pins the canary path and the unchanged default path
tests/ci/test_docs_site_job.py               # pins the local probe step and the artifact-name input
docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md  # Amendment 2026-11-11
docs/changelog/unreleased/<id>.<section>.md  # fragment
```

**Structure Decision**: one stdlib module next to the other `site_*` scripts, tested under `tests/docs/`.

## Implementation Concern Map

### IC-01 — Live-site probe

- **Purpose**: derive the D-13 URL sample from the ledgers and assert each class over HTTP.
- **Relevant requirements**: FR-001, FR-002, FR-003, NFR-001, NFR-002, NFR-004
- **Affected surfaces**: `scripts/docs/site_live_probe.py`, `tests/docs/test_site_live_probe.py`
- **Sequencing/depends-on**: none
- **Risks**: a class can vanish from the ledgers (refuse, do not shrink); GitHub Pages answers a missing trailing slash with 301 (the sample uses trailing-slash directory URLs and flat stub files, and redirects are not followed, so a 3xx fails).

### IC-02 — Canary path and shared-build wiring

- **Purpose**: the dispatched canary in `docs-pages.yml`, the artifact-name input and local probe step in `docs-site-build.yml`, the router filter, the ADR amendment and the changelog fragment.
- **Relevant requirements**: FR-004, FR-005, FR-006, FR-007, FR-008, FR-009, NFR-003
- **Affected surfaces**: the workflows, router filter and scrub copy, the two workflow tests, the ADR, the changelog
- **Sequencing/depends-on**: IC-01 (the workflow runs the probe)
- **Risks**: job-level `success()` is transitive, so the DocFX deploy needs an explicit status function; two Pages artifacts in one run need distinct names.
