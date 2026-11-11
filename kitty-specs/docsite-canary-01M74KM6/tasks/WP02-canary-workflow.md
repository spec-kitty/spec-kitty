---
work_package_id: WP02
title: Canary path and shared-build wiring
dependencies:
- WP01
requirement_refs:
- FR-004
- FR-005
- FR-006
- FR-007
- FR-008
- FR-009
- NFR-003
- C-001
- C-002
- C-003
- C-004
- C-005
- SC-001
- SC-003
planning_base_branch: issue-6938-docsite-canary
merge_target_branch: issue-6938-docsite-canary
branch_strategy: Planning artifacts for this mission were generated on issue-6938-docsite-canary. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6938-docsite-canary unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
- T009
- T010
phase: Phase 2 - Canary
history:
- at: '2026-11-11T06:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: .github/workflows/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- .github/workflows/docs-pages.yml
- .github/workflows/docs-site-build.yml
- .github/workflows/ci-router.yml
- tests/release/ci_retirement_scrub.json
- tests/release/test_release_ci_ownership.py
- tests/ci/test_docs_site_job.py
- docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md
- docs/changelog/unreleased/**
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Canary path and shared-build wiring

## ⚡ Do This First: Load Agent Profile

Load the assigned profile with the `/spk-charter-profile-load` skill (`implementer-ivan`) before reading anything else.

## Objective

A `workflow_dispatch` input `canary` on `.github/workflows/docs-pages.yml` that builds the doc-kitty site through the shared `docs-site-build.yml` (D-11), publishes it, runs the WP01 probe against `https://docs.spec-kitty.ai`, and always lets the existing DocFX `deploy` job republish DocFX; the run is red when the probe failed. The default push and dispatch path keeps its jobs and guards.

## Context & Constraints

- Spec FR-004..FR-009, NFR-003, C-001..C-005; plan "Engineering Alignment"; research R-1..R-4, R-6.
- The cutover is NOT done here. The canary is never dispatched by the Mission.
- `test_release_ci_ownership.py` is updated only to pin the new path; never loosened. `test_fork_guard.py` stays green.
- Pins: `actions/deploy-pages@368f82528645a54fb793d4d04e342629a3f51346 # v5.0.1`, `actions/checkout@08c6903cd8c0fde910a37f88322edcfb5dd907a8 # v5.0.0`.

## Subtasks

### T006 — Shared build

`pages-artifact-name` input (string, default `github-pages`) passed to `upload-pages-artifact`'s `name`; a step after the build serves `site/dist` on a local port and runs the probe with `--attempts 1`. Pin both in `tests/ci/test_docs_site_job.py`.

### T007 — docs-pages.yml

Jobs `canary-build` (calls the shared build), `canary-deploy` (needs `canary-build` and `build`; core repository, `main`, dispatch, `canary`; environment `github-pages`; `pages: write`, `id-token: write` only there), `canary-probe` (needs `canary-deploy`; `contents: read`). `deploy`: `needs: [build, canary-probe]`, `if:` adds `(!cancelled() || inputs.canary)` to the existing guards. `pages` and `build` unchanged.

### T008 — Workflow test pins

Pin the canary jobs' needs, conditions, permissions, artifact names, environment and pins, and the DocFX jobs' unchanged parts, in `test_release_ci_ownership.py`. Include a test that evaluates the `deploy` condition for the default and canary paths.

### T009 — Router

Add `scripts/docs/site_live_probe.py` to the `docs_site` filter in `ci-router.yml` and its scrub copy `tests/release/ci_retirement_scrub.json` (the shared build now runs the probe).

### T010 — ADR and changelog

Append `## Amendment 2026-11-11` to the ADR (body unchanged) recording the canary mechanism and the probe classes; add a fragment in `docs/changelog/unreleased/` that passes `check_changelog_style` and `check_spelling --pass unreleased`.

## Definition of Done

Workflow, router, scrub, docs-site and fork-guard tests green; actionlint clean; terminology guard green; ADR amendment and fragment pass their checks.

## Implementation command

```bash
spec-kitty agent action implement WP02 --agent claude --mission docsite-canary-01M74KM6
```
