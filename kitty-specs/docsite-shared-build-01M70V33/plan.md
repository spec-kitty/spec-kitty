# Implementation Plan: Docsite shared build definition

**Branch**: `kitty/mission-docsite-shared-build-01M70V33` → lands on `issue-6937-docs-site-shared-build` | **Date**: 2026-11-09 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/docsite-shared-build-01M70V33/spec.md`

## Summary

Move the `docs-site` job's steps (`.github/workflows/ci-router.yml:1770-1810`) into a new reusable workflow, `.github/workflows/docs-site-build.yml` (`on: workflow_call`), with one boolean input, `pages-artifact` (default `false`), that swaps the plain `site/dist` upload for a Pages-artifact upload. The router's `docs-site` job keeps its key, display name, `needs: [changes]`, `if:` and place in `router-gate.needs`, and becomes a pure `uses:` call. `tests/ci/test_docs_site_job.py` is re-pointed at the steps that actually run, gains the deploy-reuse pin, and pins the real jobs-API row name (`docs site (doc-kitty build) / build`) as blocking. The new file joins the `docs_site` path group and its scrub copy. `docs-pages.yml` is untouched (#6938 switches it).

## Technical Context

**Language/Version**: GitHub Actions workflow YAML; Python 3.11 (pytest) for the pins
**Primary Dependencies**: existing actions only, all commit-pinned: `actions/checkout@08c6903…` (v5.0.0), `pnpm/action-setup@ea17c68…` (v6.1.0), `actions/setup-node@949feb2…` (v7.1.0), `actions/upload-artifact@043fb46…` (v7.0.1); added: `actions/upload-pages-artifact@fc324d3547104276b827a68afc52ff2a11cc49c9` (v5.0.0, the action `docs-pages.yml` already uses by tag)
**Storage**: N/A
**Testing**: pytest, `tests/ci/test_docs_site_job.py` (ATDD: acceptance tests red first, on their own commit); blast radius `tests/ci/`, `tests/release/test_release_ci_ownership.py`, `tests/architectural/test_dual_mode_contract.py`, `tests/ci/test_fork_guard.py`, `make test-fast`, and the real `docs-site` run on the PR
**Target Platform**: GitHub-hosted `ubuntu-24.04`
**Project Type**: single (CI configuration + tests)
**Performance Goals**: no change to the build's wall time; job timeout stays 20 minutes (NFR-003)
**Constraints**: required gate unchanged (FR-003); no credential, `contents: read` (NFR-001); commit pins (NFR-002); deploy untouched (C-002); no new gate or allowlist (C-003)
**Scale/Scope**: 1 new workflow (~60 lines), ~40 lines changed in `ci-router.yml`, 1 test module reworked, 1 JSON row

## Charter Check

- **Single canonical authority:** the build steps move to exactly one file; the router and (later) the deploy reference it. The path group stays the routing authority (`gate_selection.load_router`). PASS.
- **ATDD-first / red-first (C-011):** the acceptance tests (caller holds no steps, called definition holds the build, deploy-reuse input, real row name blocks) are committed failing before the extraction. PASS (planned).
- **Non-vacuous gates (Standing Order #5):** step checks currently read `jobs.docs-site.steps`; after extraction they would pass on an empty list. They are re-pointed at the called job, each keeps its mutant, and a guard asserts the called job has the expected steps. PASS (planned).
- **Tidy first (SO#2):** this is the extraction step before #6932–#6936 add gates. PASS.
- **Gate discipline:** no new gate, ratchet or allowlist. PASS.
- **Supply chain (DIRECTIVE_051):** one action added (`actions/upload-pages-artifact`), first-party GitHub, already used by `docs-pages.yml`; pinned here by commit (resolved with `git ls-remote` from the `v5.0.0` tag). No package-manager dependency changes. Adversarial challenge: covered by the review WP's independent reviewer. PASS.
- **Terminology Canon:** no `feature` wording; run `tests/architectural/test_no_legacy_terminology.py` before push.

## Project Structure

### Documentation (this mission)

```
kitty-specs/docsite-shared-build-01M70V33/
├── spec.md
├── plan.md
├── research.md
├── research/code-grounding.md
├── data-model.md
├── quickstart.md
└── tasks.md            # /spec-kitty.tasks
```

### Source Code (repository root)

```
.github/workflows/
├── docs-site-build.yml     # NEW: on: workflow_call, input pages-artifact; job `build`
└── ci-router.yml           # docs-site job → `uses: ./.github/workflows/docs-site-build.yml`; docs_site filter + new path
tests/ci/test_docs_site_job.py           # re-pointed step checks, deploy-reuse pin, row-name pin
tests/release/ci_retirement_scrub.json   # docs_site roots + new path
docs/changelog/unreleased/<pr>.internal.md
```

**Structure Decision**: one reusable workflow beside the existing `module-tests.yml` precedent; no composite action (C-001).

## Implementation Concern Map

### IC-01 — Shared build definition and the gate's call

- **Purpose**: one callable build that the required gate uses, with no loss of requiredness or hygiene.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004, FR-006, NFR-001..003
- **Affected surfaces**: `.github/workflows/docs-site-build.yml`, `.github/workflows/ci-router.yml` (job block, `docs_site` filter, header comment), `tests/ci/test_docs_site_job.py`, `tests/release/ci_retirement_scrub.json`
- **Sequencing/depends-on**: none
- **Risks**: vacuous step checks after extraction; the jobs-API row name changing (router gate classifies every row, so the row still gates, but the test must use the real name); `ci-router.yml` churn (114 commits / 90 days) — rebase late.

### IC-02 — Deploy reuse

- **Purpose**: let #6938's deploy call the same build and get a Pages artifact.
- **Relevant requirements**: FR-005
- **Affected surfaces**: the `pages-artifact` input and the two conditional upload steps in `docs-site-build.yml`; a pin in `tests/ci/test_docs_site_job.py`
- **Sequencing/depends-on**: IC-01
- **Risks**: an unused branch until #6938; kept to two `if:` lines and pinned by test so it is not dead weight.
