# Tasks: Docsite canary deploy

**Mission**: `docsite-canary-01M74KM6` · **Planning/merge branch**: `issue-6938-docsite-canary`
**Inputs**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md), [data-model.md](data-model.md)

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first tests for the probe: derivation from the real and synthetic ledgers | WP01 | |
| T002 | Red-first tests for every assertion branch against a local `http.server` fixture | WP01 | |
| T003 | Implement `scripts/docs/site_live_probe.py`: sample derivation | WP01 | |
| T004 | Implement the HTTP check, bounded retries, report and CLI | WP01 | |
| T005 | Run the probe against a local build of `site/dist` | WP01 | |
| T006 | Shared build: `pages-artifact-name` input and the local probe step | WP02 | |
| T007 | `docs-pages.yml`: canary input and jobs; DocFX deploy waits on the probe | WP02 | |
| T008 | Pin the canary and unchanged default path in the workflow tests | WP02 | |
| T009 | Router `docs_site` filter and scrub copy | WP02 | [P] |
| T010 | ADR amendment 2026-11-11 and changelog fragment | WP02 | [P] |

## WP01 — Live-site probe

**Goal**: a ledger-derived probe of the D-13 URL classes that exits non-zero on any mismatch. **Priority**: P1. **Prompt**: [tasks/WP01-live-site-probe.md](tasks/WP01-live-site-probe.md)
**Independent test**: `tests/docs/test_site_live_probe.py` against a local HTTP server.

T001 Red-first tests: derivation (WP01)
T002 Red-first tests: assertion branches (WP01)
T003 Sample derivation (WP01)
T004 HTTP check, retries, report, CLI (WP01)
T005 Local probe of a real build (WP01)

Dependencies: none. Risks: a class vanishing from the ledgers (refuse); redirect-following hiding a 3xx (do not follow).

## WP02 — Canary path and shared-build wiring

**Goal**: the dispatched canary in `docs-pages.yml` that always restores DocFX, the shared build's artifact name and local probe, the router filter, the ADR amendment and the changelog. **Priority**: P1. **Prompt**: [tasks/WP02-canary-workflow.md](tasks/WP02-canary-workflow.md)
**Independent test**: the workflow tests, actionlint.

T006 Shared build input and local probe step (WP02)
T007 Canary jobs in docs-pages.yml (WP02)
T008 Workflow test pins (WP02)
T009 Router filter and scrub copy (WP02)
T010 ADR amendment and changelog (WP02)

Dependencies: WP01. Risks: transitive `success()` skipping the restore; Pages artifact name collision; changing the default path.
