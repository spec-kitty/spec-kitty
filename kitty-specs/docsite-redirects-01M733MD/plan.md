# Implementation Plan: Docsite legacy redirects

**Branch**: `issue-6933-docsite-redirects` (owned checkout, `single_branch`) → `main` via pull request | **Date**: 2026-11-10 | **Spec**: [spec.md](spec.md)

## Summary

- **Generator.** A new generator, `scripts/docs/site_redirects.py`, derives the legacy redirect map from three inputs: `site/url-baseline.txt`, `site/moves.yaml` (through `moves_ledger.collapse`) and the published set in `_dockitty_contract`.
  - It writes `site/legacy-redirects.json`, a flat JSON object.
  - `--check` fails when the committed copy is stale.
  - `selftest <dist>` proves the real coverage gate's verdicts on a hard-linked copy of the built site.
- **Site.** `site/astro.config.mjs` reads the map and passes it to doc-kitty v0.7.0's `legacyHtmlRedirects`. Astro's own `redirects` stays empty (#253).
- **Built-site check.** One predicate in `_dockitty_contract.py`, `redirect_stub_target(html)`, recognises doc-kitty's stub. It mirrors doc-kitty's `REDIRECT_STUB_RE` (`check-redirect-coverage.mjs:106`).
  - The `page` and `render` surfaces skip stubs.
  - The `link` surface still refuses a stub whose `<a href>` target is unpublished.
- **CI and Makefile.** The shared `docs-site-build.yml` job and `make docs-site` run, in order:
  1. `site_redirects --check` before the build;
  2. after the build, `dockitty-check-redirect-coverage` twice: with `--docs ../docs --declared-redirects legacy-redirects.json`, and without either;
  3. the self-test.
- **Router.** The router's `docs-site` filter gains `scripts/docs/moves_ledger.py` and `scripts/docs/site_redirects.py`, with the scrub copy in lockstep.
- **ADR.** ADR 2026-10-31-1 gets an amendment section for D-5 and D-14.

## Technical Context

**Language/Version**: Python 3.11+ (stdlib plus PyYAML, runnable on the runner's `python3`), Astro config (JS), GitHub Actions YAML
**Primary Dependencies**: doc-kitty v0.7.0 (`5acb83c`, pinned): `legacyHtmlRedirects`, `dockitty-check-redirect-coverage`. No new dependency.
**Storage**: committed `site/legacy-redirects.json` (generated)
**Testing**:
- pytest over fixture trees (a tmp `docs/`, moves ledger and baseline), with one mutant per generator rule and refusal;
- stub-predicate fixtures for the built-site check;
- the self-test's verdict logic with an injected gate command;
- the real gate run in CI and locally (`make docs-site`).
**Target Platform**: GitHub-hosted `ubuntu-24.04`
**Project Type**: single
**Performance Goals**: ≤ 1 min added to the `docs-site` job (NFR-001)
**Constraints**: C-001..C-005
**Scale/Scope**: 970 baseline routes, about 929 map keys, about 10 files changed

## Charter Check

- **Single authority:**
  - published and unpublished sets come from `_dockitty_contract`;
  - moves and chains from `moves_ledger`;
  - the stub shape from one predicate, `redirect_stub_target`;
  - the map is generated and checked, never hand-edited.
- **ATDD with lasting value (#7484):** the generator rules, its refusals, the stub exemption and the self-test's verdict matching go red first. No YAML-shape tests.
- **Immutable history:** the ADR change is an amendment section only.
- **Gate discipline:** the real gate runs twice, so no URL is excused silently. The self-test proves the gate's own verdicts on every run.
- **Terminology:** run the terminology guard on the ADR text.

## Project Structure

```
scripts/docs/_dockitty_contract.py          # redirect_stub_target (the one stub predicate)
scripts/docs/site_built_check.py            # page surface skips stubs
scripts/docs/site_built_check_render.py     # render surface skips stubs
scripts/docs/site_redirects.py              # NEW generator: render / write / --check / selftest
site/legacy-redirects.json                  # NEW generated map
site/astro.config.mjs                       # legacyHtmlRedirects from the map
.github/workflows/docs-site-build.yml       # --check, two coverage runs, self-test
.github/workflows/ci-router.yml             # docs-site filter: moves_ledger.py, site_redirects.py
tests/release/ci_retirement_scrub.json      # scrub copy of the router group
Makefile                                    # docs-site mirrors the workflow
tests/docs/test_site_redirects.py           # NEW
tests/docs/test_site_built_check.py, tests/docs/test_site_built_check_render.py, tests/docs/test_dockitty_contract.py
docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md   # amendment section
```

## Implementation Concern Map

### IC-01 — The legacy map and the site

- **Purpose**: generate the map by the D-5 rules, build the site with it, and keep the built-site check honest about stubs.
- **Relevant requirements**: FR-001, FR-002, FR-006, FR-007, NFR-002, NFR-003
- **Affected surfaces**: the generator, the map, `astro.config.mjs`, the contract predicate, two built-site surfaces, the ADR
- **Sequencing/depends-on**: none
- **Risks**:
  - the generator's live set differs from what doc-kitty builds (caught by the coverage gate);
  - collisions with built files (refused by the generator).

### IC-02 — Gates in CI and locally

- **Purpose**: the map cannot go stale, the coverage gate runs twice, and the gate's own verdicts are proven.
- **Relevant requirements**: FR-003, FR-004, FR-005, NFR-001, SC-001, SC-002
- **Affected surfaces**: `docs-site-build.yml`, `Makefile`, `ci-router.yml`, the scrub JSON, the generator's `selftest`
- **Sequencing/depends-on**: IC-01
- **Risks**:
  - #6936 (PR #7508) edits the same workflow and `astro.config.mjs`; the later PR rebases (textual conflict only);
  - `ci-router.yml` churn.
