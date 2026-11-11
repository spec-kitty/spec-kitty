# Mission Specification: Docsite canary deploy

**Mission Branch**: `issue-6938-docsite-canary`
**Created**: 2026-11-11
**Status**: Draft
**Input**: Operator brief for #6938 PR A: a live-site probe and a dispatched canary in the docs deploy workflow (ADR 2026-10-31-1 D-11, D-13).

## Intent Summary

- **Primary actor:** the docs operator (a maintainer with permission to dispatch the deploy workflow).
- **Trigger:** before the docsite cuts over from DocFX to doc-kitty, the operator announces a short production window, freezes docs merges to `main`, and dispatches the deploy workflow from `main` with the canary option on.
- **Outcome:** the run builds the doc-kitty site with the one shared build definition, publishes it to the real GitHub Pages service, probes a small sample of legacy and live URLs over HTTP, then always rebuilds and republishes the DocFX site. The run is red when any probe fails. This ends the UNVERIFIED status of the GitHub Pages leg of ADR D-5.
- **Invariant:** the canary never leaves the doc-kitty site live; a push to `main`, or a dispatch without the canary option, keeps deploying DocFX exactly as before; only `main` of the core repository can publish.
- **Boundary:** the cutover (switching the deploy to `site/dist`, deleting `docs/llms.txt`, the post-deploy smoketest of #2361) is a separate, later pull request. This Mission builds the probe logic that smoketest will reuse, and does not switch the deploy.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Probe a live docsite for the URL classes that matter (Priority: P1)

The operator, or a later post-deploy smoketest, runs one command against a site's base URL. It derives a small, deterministic sample from the committed URL ledgers and checks each URL over HTTP, printing one line per URL and exiting non-zero on any mismatch.

**Why this priority**: the probe is the evidence. Without it the canary publishes a site and proves nothing; with it, #2361's smoketest has its logic ready.

**Independent Test**: run the probe against a local web server that serves a small fixture site shaped like the doc-kitty build, and against fixtures with one defect each.

**Acceptance Scenarios**:

1. **Given** a site that serves every sampled URL correctly, **When** the probe runs, **Then** every line reports a pass and it exits 0.
2. **Given** a legacy URL whose redirect stub names a target other than the committed map's, **When** the probe runs, **Then** that line fails and it exits non-zero.
3. **Given** a stub whose target does not serve 200, **When** the probe runs, **Then** that line fails.
4. **Given** the retired dashboard route serves 200, **When** the probe runs, **Then** that line fails (retired pages must stay gone).
5. **Given** a URL that fails once and then serves correctly (Pages propagation), **When** the probe runs with retries, **Then** it passes within the retry budget; **Given** it never serves correctly, **Then** it fails after the budget.

### User Story 2 - Dispatch a canary that always restores DocFX (Priority: P1)

The operator dispatches the deploy workflow on `main` with the canary option. The doc-kitty site is built by the same definition the pull-request gate uses, published, probed, and then DocFX is republished whatever the probe said. The run fails when the probe failed.

**Why this priority**: it is the only way to exercise the real Pages service before cutover (ADR D-13 step 2).

**Independent Test**: static checks over the workflow pin the job graph, conditions, permissions, artifact names and pins; the real run is the operator's dispatch in an announced window.

**Acceptance Scenarios**:

1. **Given** a dispatch from `main` in the core repository with the canary on, **When** the run proceeds, **Then** the doc-kitty build is published, probed, and DocFX is rebuilt and republished afterwards.
2. **Given** the probe fails, **When** the run ends, **Then** DocFX was still republished and the run is red.
3. **Given** a push to `main` or a dispatch without the canary, **When** the run proceeds, **Then** only DocFX is built and published, as before.
4. **Given** a dispatch from another branch or a fork, **When** the run proceeds, **Then** nothing is published.

### Edge Cases

- The doc-kitty build fails before publishing: production is never touched by the canary; DocFX is still republished (harmless).
- The DocFX build fails: the canary must not publish, because the restore could not follow.
- The ledgers no longer contain a URL of some class (for example no moved chain is left): the probe refuses to run rather than silently probing fewer classes.
- The served stub is wrapped in a redirect (a 3xx) instead of being served directly: that is a failure, because D-5's flat stubs remove that hop.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Ledger-derived sample | As the operator, I want the probe's URL sample derived from the committed URL baseline, moves ledger and legacy redirect map, so that it never drifts from a hand list. It takes one legacy key to its own page, one moved-chain key, one live `dir/index.html` with no key, one `dir/README.html` key, one directory URL, the site root, `/llms.txt` and one retired `/kitty-specs/` route. The choice is deterministic, and a missing class refuses. | High | Open | [build] | no |
| FR-002 | HTTP assertions per class | As the operator, I want each sampled URL checked over HTTP: 200 for a page, 404 for the retired route, and for a redirect key a directly served stub whose target equals the map's target and whose target serves a page (200, not a stub). | High | Open | [build] | no |
| FR-003 | Bounded retries and a clear report | As the operator, I want each URL retried a bounded number of times with a pause and a timeout, one report line per URL, and a non-zero exit on any mismatch. | High | Open | [build] | no |
| FR-004 | Dispatched canary path | As the operator, I want a dispatch option on the deploy workflow that builds the doc-kitty site through the one shared build definition, publishes it with the same Pages deploy action, and probes the live site. | High | Open | [build] | no |
| FR-005 | DocFX always restored | As the operator, I want the canary run to rebuild and republish DocFX after the canary whatever the probe's result, publish the canary only once the DocFX restore artifact is built, and fail the run when the probe failed. | High | Open | [build] | no |
| FR-006 | Unchanged default path | As a docs contributor, I want a push to `main` and a dispatch without the canary to keep building and publishing DocFX with the same jobs, steps and guards as before. | High | Open | [ratchet] | yes — paired with FR-004 on the same workflow fixture |
| FR-007 | Guards kept | As the maintainers, I want the Pages probe-then-configure job, the `main`-only and core-repository-only publish, the fork guard and the `pages` concurrency group kept, with the release-ownership test pinning the new path and never loosened. | High | Open | [ratchet] | yes — paired with FR-004 on the same workflow fixture |
| FR-008 | Decision record | As the maintainers, I want the ADR to record the canary mechanism and the probe's URL classes in a dated amendment, and a changelog fragment to announce it. | Medium | Open | [build] | no |
| FR-009 | Gate selection | As the maintainers, I want a change to the probe script to select the docs-site pull-request gate, like the other site scripts. | Medium | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Bounded run time | The probe makes at most 10 URL checks plus one target check per stub; each request has a timeout of at most 30 s and at most 6 attempts, so one URL takes under 5 minutes in the worst case. | Reliability | High | Open |
| NFR-002 | No new dependencies | The probe uses the standard library plus the repository's existing ledger readers (PyYAML through `moves_ledger`), so the runner's `python3` runs it. | Maintainability | High | Open |
| NFR-003 | Least privilege | Only the job that publishes the canary holds `pages: write` and `id-token: write` among the new jobs; every action is pinned by commit SHA. | Security | High | Open |
| NFR-004 | Tested logic | The probe's derivation and every assertion branch are covered by fast tests against a local HTTP server, with 90 % or more line coverage of the new module. | Quality | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No cutover | The deploy is not switched to doc-kitty here; that is PR B of #6938. | Business | High | Open |
| C-002 | Never dispatched by the Mission | The canary and any deploy workflow are dispatched only by the operator, in an announced window with docs merges frozen. | Business | High | Open |
| C-003 | One build definition | The canary builds the site only by calling the shared docs-site build workflow (ADR D-11); no copy of its steps. | Technical | High | Open |
| C-004 | ADR body unchanged | The ADR changes only by an appended amendment. | Technical | High | Open |
| C-005 | Packs untouched | Nothing under `packs/built-in/` or `packs/internal/` is edited. | Technical | High | Open |

### Key Entities

- **URL baseline**: every route the site has published (`site/url-baseline.txt`).
- **Moves ledger**: append-only `from -> to` moves (`site/moves.yaml`); a chain is a move whose target moved again.
- **Legacy redirect map**: the generated `site/legacy-redirects.json`; one flat stub per key.
- **Probe**: one sampled URL with its class and expected answer.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a dispatched canary, all sampled URL classes (8 classes) pass on the real Pages service, and the production site serves DocFX again when the run ends. — [build] · no-op passable: no
- **SC-002**: Every assertion branch of the probe has a test that fails when the branch is broken (each defect fixture makes the probe exit non-zero). — [build] · no-op passable: no
- **SC-003**: The default deploy path's jobs and guards are unchanged, as pinned by the release-ownership test. — [ratchet] · no-op passable: yes — paired with SC-001's canary path on the same workflow

## Assumptions

- The GitHub Pages environment `github-pages` accepts more than one deployment in a run, from distinctly named artifacts.
- The doc-kitty site serves `/llms.txt` (ADR D-9) and a 404 for `/kitty-specs/` routes (ADR D-5, dashboards dropped).
- SC-001 is proven only by the operator's dispatch; in this Mission it is recorded as deferred to #6938.
