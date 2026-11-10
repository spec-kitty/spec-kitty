# Mission Specification: Docsite legacy redirects

**Mission Branch**: `issue-6933-docsite-redirects` (owned checkout, `single_branch`; lands on `main` through a pull request)
**Created**: 2026-11-10
**Status**: Draft
**Input**: Issue #6933 of epic #6100; ADR `docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md` D-5 "Redirects" and D-14; operator ruling of 2026-11-10 on the two `docs/assets/*.html` URLs (redirect both to the hub).

## Intent Summary

- **Primary actors:**
  - a reader or search engine following a link to `docs.spec-kitty.ai` that was valid on the DocFX site;
  - a maintainer who moves, drafts or archives a page.
- **Trigger:** every pull request that selects the `docs-site` gate builds the site through the shared `docs-site-build.yml`.
- **Desired outcome:** every one of the 970 routes in `site/url-baseline.txt` still resolves after cutover (#6938), either to its own page or through a redirect that ends on a live page. A change that would break one fails the gate.
- **Mechanism:** a committed map, `site/legacy-redirects.json`, feeds doc-kitty v0.7.0's `legacyHtmlRedirects` option.
  - A Python generator derives the map from `site/moves.yaml`, the URL baseline and the published set in `scripts/docs/_dockitty_contract.py`; it is never hand-edited.
  - `dockitty-check-redirect-coverage` gates it twice: once with `--docs` and the declared map, once without.
- **Rules (ADR D-5, as amended here):**
  1. `X.html` goes to `X/`. A `dir/README.html` or `dir/index.html` goes to `dir/`.
  2. Chains in `moves.yaml` are collapsed, so every key points at a final route.
  3. A legacy `dir/index.html` whose `dir/` is a live, unmoved page gets no key, because the page itself serves it.
  4. A route whose page is unpublished (draft folder, draft status, excluded, archived) goes to its nearest published ancestor, normally its section hub. While DocFX still publishes drafts, this rule lives in the generator, not in `moves.yaml`.
  5. A baseline URL with no page and no move is refused, except where the operator ruled otherwise. The two standalone HTML resources DocFX copied, `/assets/spec-kitty-backlog.html` and `/assets/spec-kitty-evolution-v1-to-v3.html`, redirect to the `/assets/` hub (ruling 2026-11-10).
- **Built-site check:** doc-kitty's redirect stubs are not publications. The built-site check recognises them through one shared predicate and still refuses a stub whose target is unpublished.
- **Test value (#7484):**
  - Python mutants over fixture inputs exercise the generator and the built-site check.
  - A self-test runs the real coverage gate against a copy of the built site with three mutants (dead target, missing key, draft-excused URL). No YAML-shape tests.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Old links keep working (Priority: P1)

A reader follows a bookmarked DocFX link such as `/architecture/status-model.html` or `/adr/1.x/README.html` and lands on the current page.

**Why this priority**: cutover (#6938) cannot break every inbound link.

**Independent Test**: build the site and run `dockitty-check-redirect-coverage` over `site/url-baseline.txt`. All 970 routes are covered, and every redirect stub reaches a live page.

**Acceptance Scenarios**:

1. **Given** the committed map, **When** the site is built, **Then** both coverage runs report 970 of 970 covered and no dead stub.
2. **Given** a map key whose target page was removed, **When** the gate runs, **Then** it fails.
3. **Given** a baseline route with no page and no key, **When** the gate runs, **Then** it fails.

### User Story 2 - A page move or draft cannot silently drop a URL (Priority: P1)

A maintainer moves a page, adds it to `moves.yaml`, or flips it to draft. The generated map must change in the same pull request.

**Why this priority**: the map is generated; a stale committed copy is a silent regression.

**Independent Test**: `python3 -m scripts.docs.site_redirects --check` fails when the committed map differs from what the generator produces.

**Acceptance Scenarios**:

1. **Given** a page newly marked draft, **When** `--check` runs without regenerating, **Then** it fails and names the regeneration command.
2. **Given** a draft-excused URL, **When** the gate runs without `--docs`, **Then** it fails, so no URL is excused silently.

### Edge Cases

- A legacy source path that equals an existing built file (a page or a `public/` asset) is fatal at build time in doc-kitty. The generator refuses it first, with a clear message.
- A `moves.yaml` cycle is refused (existing `collapse` behaviour).
- `dir/README.html` and `dir/index.html` map to `dir/` (case-folded `INDEX_BASENAMES`).
- The map is a flat JSON object with no comment key, because doc-kitty validates every key as a legacy `.html` path.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Generated legacy map | As a maintainer, I want `site/legacy-redirects.json` generated from `moves.yaml`, the URL baseline and the published set by rules 1 to 5, so that the map has one authority and is never hand-edited. | High | Open | [build] | no — no map exists today |
| FR-002 | Map wired into the site | As a reader, I want the site built with `legacyHtmlRedirects` from the committed map, so that every legacy `.html` URL is a redirect stub to its live page. | High | Open | [build] | no — no redirects are built today |
| FR-003 | Generated equals committed | As a maintainer, I want a `--check` step before the build that fails when the committed map is stale, so that a move or draft change regenerates the map in the same pull request. | High | Open | [build] | no — mutant proves it fails |
| FR-004 | Two coverage runs | As a maintainer, I want `dockitty-check-redirect-coverage` run twice after the build, with `--docs` and the declared map and without either, so that no URL is excused silently. | High | Open | [build] | no — no gate runs today |
| FR-005 | Real-gate self-test | As a maintainer, I want the job to run the coverage gate against a copy of the built site with a dead-target, a missing-key and a draft-excused mutant, and fail unless each verdict matches, so that the gate's own behaviour is proven on every run. | Medium | Open | [build] | no — a mutant that passes fails the step |
| FR-006 | Stubs are not publications | As a maintainer, I want the built-site check to recognise redirect stubs through one shared predicate, skipping them as pages while still refusing a stub whose target is unpublished, so that the stubs do not fail the publication and render checks. | High | Open | [build] | no — the check reports thousands of stub findings today |
| FR-007 | ADR records the mechanism | As a reader of the ADRs, I want ADR 2026-10-31-1 amended to record the legacy map, the retired gate override and the current counts, so that the decision record matches the build. | Medium | Open | [build] | no — D-5 describes Astro `.html` keys |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Build time | The redirect steps add at most 1 minute to the `docs-site` job. | Performance | Medium | Open |
| NFR-002 | Check fidelity | The generator and stub-predicate checks fail on 100% of their mutant fixtures. | Reliability | High | Open |
| NFR-003 | Standard library | The generator runs on the runner's `python3` (stdlib plus PyYAML), with no `uv sync`. | Operability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | DocFX path untouched | `redirect_map.yaml`, `redirect_stub_generator.py`, `moves_ledger.py`'s DocFX validation and `docs-pages.yml` are not changed; #6943 retires them. | Business | High | Open |
| C-002 | No Astro `.html` redirects | Astro's own `redirects` stays empty; doc-kitty refuses `.html` keys there (#253). | Technical | High | Open |
| C-003 | Immutable history | ADR bodies are not rewritten; the change is an amendment section. | Business | High | Open |
| C-004 | Upstream first | A doc-kitty gap is filed upstream before any local workaround. | Technical | High | Open |
| C-005 | Out of scope | Diagrams (#6936), cutover and the Pages canary (#6938), DocFX retirement (#6943). | Business | High | Open |

### Key Entities

- **Legacy map**: `site/legacy-redirects.json`, legacy `.html` route to live directory route.
- **URL baseline**: `site/url-baseline.txt`, the 970 routes that must keep resolving.
- **Moves ledger**: `site/moves.yaml`, the authored page moves.
- **Redirect stub**: the flat HTML page doc-kitty writes for each map key.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Both coverage runs report 970 of 970 baseline routes covered and no dead stub on the landing pull request's `docs-site` job. — [build] · no-op passable: no
- **SC-002**: The self-test's three mutants each give the expected verdict on that job. — [build] · no-op passable: no
- **SC-003**: Every generator and stub-predicate mutant fixture makes its check fail. — [build] · no-op passable: no

## Assumptions

- doc-kitty v0.7.0 (`5acb83c`) closes the gate's `dir/index.html` gap, so no `--redirects` override is needed (measured 2026-11-10: 970/970 with no override).
- The runner's system `python3` has PyYAML, as `docs-pages.yml` already relies on.
- Node is not available on the pytest module shards, so the real-gate self-test runs as a job step, not a pytest wrapper.
