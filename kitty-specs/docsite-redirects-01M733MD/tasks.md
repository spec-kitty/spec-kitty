# Tasks: Docsite legacy redirects

**Mission**: `docsite-redirects-01M733MD` · [spec.md](spec.md) · [plan.md](plan.md)

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red: generator rule and refusal mutants, stub-predicate fixtures | WP01 | |
| T002 | `redirect_stub_target` in `_dockitty_contract.py`; `page` and `render` surfaces skip stubs | WP01 | |
| T003 | `scripts/docs/site_redirects.py` (render, write, `--check`) and the generated `site/legacy-redirects.json` | WP01 | |
| T004 | `astro.config.mjs` reads the map into `legacyHtmlRedirects`; local build and both gate runs green | WP01 | |
| T005 | ADR 2026-10-31-1 amendment section (D-5, D-14) | WP01 | |
| T006 | Red, then `selftest <dist>`: the real gate's three mutant verdicts | WP02 | |
| T007 | `docs-site-build.yml` and `make docs-site`: `--check`, two coverage runs, self-test | WP02 | |
| T008 | Router `docs-site` filter and scrub copy gain `moves_ledger.py` and `site_redirects.py` | WP02 | |

## Phase 1 — Map and site

### WP01 – Legacy map, stub exemption and site wiring
- FR-001, FR-002, FR-006, FR-007; prompt [tasks/WP01-legacy-map-and-site.md](tasks/WP01-legacy-map-and-site.md). Dependencies: none.

T001 Red: generator rule and refusal mutants, stub-predicate fixtures (WP01)
T002 `redirect_stub_target` in `_dockitty_contract.py`; `page` and `render` surfaces skip stubs (WP01)
T003 `scripts/docs/site_redirects.py` (render, write, `--check`) and the generated `site/legacy-redirects.json` (WP01)
T004 `astro.config.mjs` reads the map into `legacyHtmlRedirects`; local build and both gate runs green (WP01)
T005 ADR 2026-10-31-1 amendment section (D-5, D-14) (WP01)

## Phase 2 — Gates

### WP02 – Redirect gates in CI and the self-test
- FR-003, FR-004, FR-005; prompt [tasks/WP02-redirect-gates.md](tasks/WP02-redirect-gates.md). Depends on WP01.

T006 Red, then `selftest <dist>`: the real gate's three mutant verdicts (WP02)
T007 `docs-site-build.yml` and `make docs-site`: `--check`, two coverage runs, self-test (WP02)
T008 Router `docs-site` filter and scrub copy gain `moves_ledger.py` and `site_redirects.py` (WP02)
