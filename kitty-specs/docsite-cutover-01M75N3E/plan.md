# Implementation Plan: Docsite cutover to doc-kitty

**Branch**: `kitty/mission-docsite-cutover-01M75N3E` → `issue-6938-docsite-cutover` | **Date**: 2026-11-11 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/docsite-cutover-01M75N3E/spec.md`

## Summary

Switch `.github/workflows/docs-pages.yml` from DocFX to the doc-kitty build. The `build` job becomes a call of the shared `.github/workflows/docs-site-build.yml` with `pages-artifact: true`, the build the required `docs-site` pull-request gate already runs (ADR D-11). `deploy` publishes that artifact from `main` of the core repository only. A new `smoketest` job (`needs: deploy`) runs the ledger-derived live-site probe against `https://docs.spec-kitty.ai` and fails the run on a mismatch (#2361). The dispatch-only canary jobs and the `canary` input are removed; the smoketest is the one live-probe mechanism. `docs/llms.txt` is deleted with its live references. Rollback is reverting the pull request (D-13 step 4). Planning answers are recorded as Decision Moments under `decisions/` (all resolved from the operator brief).

## Technical Context

**Language/Version**: GitHub Actions workflow YAML; Python 3.11+ for the tests and the existing probe (`scripts/docs/site_live_probe.py`, unchanged)
**Primary Dependencies**: `actions/deploy-pages` (SHA-pinned v5.0.1), `actions/checkout` (SHA-pinned v5.0.0), `actions/configure-pages@v6` (unchanged), the shared build `docs-site-build.yml`; tests use PyYAML and `tests/ci/_gh_expr.py`
**Storage**: N/A
**Testing**: pytest; job-graph tests evaluate the workflow's real `if:` conditions through `_gh_expr` inside the job scheduler model in `tests/release/test_release_ci_ownership.py` (#7484: no YAML-text restatement for behaviour); red first
**Target Platform**: GitHub-hosted `ubuntu-24.04` runners; GitHub Pages
**Project Type**: single repository (CI configuration plus tests)
**Performance Goals**: the smoketest completes in well under its 60-minute timeout; each probed URL is bounded by the probe's 300 s budget
**Constraints**: no dispatch and no deploy from this mission (C-002); DocFX sources stay (C-001); ADR changes by amendment only (C-003); fork guard and ownership test kept (C-004)
**Scale/Scope**: 2 workflows, 4 test files, 1 deleted docs file plus its references, 1 ADR amendment, 1 changelog fragment

## Charter Check

- **Single canonical authority**: one build definition (D-11) is now both the gate and the deploy; one live-probe mechanism (the smoketest) replaces the canary; one `llms.txt` (generated) replaces the hand copy. PASS.
- **ATDD-first / red-first**: the job-graph tests are written first and fail against `origin/main`'s workflow. PASS (WP01 then WP02 ordering below).
- **Architectural gate discipline**: tests evaluate real conditions; the ownership test is updated, not loosened; the fork-guard test is kept. PASS.
- **Git & workflow discipline**: draft PR, operator merges; merging is the production switch. PASS.
- **Mission hygiene**: issue-matrix rows for #6938, #2361 (fixed) and cited-only issues (not-applicable); implementer and reviewer are distinct. PASS.
- **Supply chain (DIRECTIVE_051)**: no new dependency; every action the mission adds is SHA-pinned (reusing pins already vetted in this repository). PASS.
- **Adversarial squad**: optional and advisory; not run, the independent reviewer covers the WP review.

## Design

### Job graph after cutover

```
pages (probe + configure; fork-guarded root)
  └─ build      uses: docs-site-build.yml  with: pages-artifact: true   (contents: read)
       └─ deploy     main + core repo only; actions/deploy-pages        (pages: write, id-token: write)
            └─ smoketest  main + core repo only; site_live_probe https://docs.spec-kitty.ai  (contents: read)
```

- `build` keeps the job name `build`, so `needs.build.result` gates `deploy` and the run model's failure-blocks-deploy test reads the same job.
- `deploy.if`: `github.repository == 'spec-kitty/spec-kitty' && github.ref == 'refs/heads/main' && needs.build.result == 'success'`. No status function, so it also requires every ancestor to succeed.
- `smoketest.if`: the same repository and ref atoms and `needs.deploy.result == 'success'`. `timeout-minutes: 60`. No `continue-on-error`, no `|| true`: a probe failure fails the job and the run. No alert issue (operator decision).
- Workflow-level `permissions: contents: read`; each job widens only what it needs. The `pages` concurrency group with `cancel-in-progress: false` stays.
- Push path filter: the `docs_site` group of `ci-router.yml` (the inputs of the shared build) minus `ci-router.yml`, plus `docs-pages.yml` itself. A test keeps the filter a superset of the gate's group so a build input never changes without a deploy.

### Decisions and alternatives

- **Canary removed, not repurposed** (decision `plan.architecture.canary-and-docfx`). A canary that publishes the current site and probes it is the smoketest with extra steps. Keeping a dispatch-only path would leave a second mechanism for one check. A plain dispatch on `main` already deploys and smoketests.
- **DocFX build removed from this workflow** (same decision). Building DocFX without publishing it costs a .NET install per deploy and would turn a good doc-kitty deploy red on a DocFX-only failure. The rollback stays a revert: the DocFX sources, scripts and their tests remain until #6943, and the revert restores the `build` (DocFX) and `deploy` jobs and the canary.
- **Tests that pinned the DocFX build** in `tests/ci/test_nightly_tooling_cache.py` (DocFX version pin and tool cache, PlantUML jar cache in `docs-pages.yml`): the DocFX version and tool cache tests are retired with the job (a revert restores them); the router `tests-docs` jar cache test keeps its key equality against the shared key literal instead of the deleted DocFX step.
- **`pages-artifact-name` input** of the shared build stays (default `github-pages`, which `deploy-pages` reads by default); its descriptions no longer name the canary.

### `docs/llms.txt` references

| Reference | Action |
|-----------|--------|
| `docs/llms.txt` | delete |
| `docs/docfx.json` resource list | drop `llms.txt` (a revert restores both) |
| `tests/docs/test_docs_seo.py::test_static_seo_files_exist` | drop `llms.txt` from the list |
| `tests/docs/test_dockitty_contract.py` stance-parity test | replace with a test that `docs/llms.txt` is absent (the generated route is the one source) |
| `scripts/docs/_dockitty_contract.py` `LLMS_STANCE` comment | update: no hand copy remains |
| `scripts/docs/bulk_ref_rewrite.py` basename/move-skip sets | keep: they name the historical moves file's `from` path and a generic basename filter, not the file |
| ADRs, plans, reports, changelog, archive, `kitty-specs/`, `kitty-ops/` | untouched (immutable history) |

## Project Structure

### Documentation (this mission)

```
kitty-specs/docsite-cutover-01M75N3E/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── decisions/
└── tasks.md            # /spec-kitty.tasks
```

### Source Code (repository root)

```
.github/workflows/docs-pages.yml          # cutover, smoketest, canary removed
.github/workflows/docs-site-build.yml     # header comments only
.github/workflows/ci-router.yml           # docs-site comment only
tests/release/test_release_ci_ownership.py
tests/ci/test_nightly_tooling_cache.py
tests/docs/test_docs_seo.py
tests/docs/test_dockitty_contract.py
scripts/docs/_dockitty_contract.py        # comment only
docs/llms.txt                             # deleted
docs/docfx.json                           # resource entry dropped
docs/development/reference/ci-gate-mechanics.md
docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md   # Amendment only
docs/changelog/unreleased/<fragment>.md
```

**Structure Decision**: single repository; CI configuration under `.github/workflows/`, tests mirror their subjects under `tests/release`, `tests/ci` and `tests/docs`.

## Implementation Concern Map

- **IC-01 Deploy graph**: the cutover of `docs-pages.yml`, the smoketest, the canary removal, the permissions, the path filter, and the tests that evaluate the job graph (red first). Covers FR-001 to FR-006, NFR-001 to NFR-004, C-002, C-004.
- **IC-02 Single `llms.txt` and the record**: the deletion and its references, the ADR amendment, the changelog fragment and the live docs page that describes the deploy. Covers FR-007, FR-008, C-001, C-003.
