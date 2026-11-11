# Mission Specification: Docsite cutover to doc-kitty

**Mission Branch**: `kitty/mission-docsite-cutover-01M75N3E` (lands on `issue-6938-docsite-cutover`)
**Created**: 2026-11-11
**Status**: Draft
**Input**: Operator brief for #6938 PR B: cut the docsite over from DocFX to doc-kitty, with the #2361 post-deploy smoketest, and delete `docs/llms.txt`.

## Context

ADR `docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md` D-13 runs the cutover in steps. Step 2, the canary, passed on production: run [43027580608](https://github.com/spec-kitty/spec-kitty/actions/runs/43027580608), report on [#6938](https://github.com/spec-kitty/spec-kitty/issues/6938#issuecomment-6796965517). All 8 URL classes passed on the real GitHub Pages service and DocFX was restored byte-identical, so the D-5 GitHub Pages leg is verified. This mission is step 3: one pull request switches the deploy to the doc-kitty build. Step 4, rollback, is reverting that pull request.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Main publishes the site the gate built (Priority: P1)

A maintainer merges a docs change to `main`. The deploy workflow builds the doc-kitty site with the same shared build definition the required `docs-site` pull-request gate uses, and publishes that build to `docs.spec-kitty.ai`.

**Why this priority**: it is the cutover itself, and it makes ADR D-11 true: `main` never deploys a site no pull request built.

**Independent Test**: evaluate the deploy workflow's real job conditions for a push to `main` and check that the deployed artifact is the one the shared build uploads.

**Acceptance Scenarios**:

1. **Given** a push to `main` of the core repository with Pages configured, **When** the workflow runs, **Then** the shared doc-kitty build uploads the Pages artifact and the deploy job publishes it.
2. **Given** the doc-kitty build fails, **When** the workflow runs, **Then** nothing is deployed and the run is red.
3. **Given** a run on a fork, or a dispatch from a branch other than `main`, **When** the workflow runs, **Then** nothing is deployed.

### User Story 2 - A broken live site turns the run red (Priority: P1)

After every deploy, a smoketest probes the live site's URL classes, derived from the committed ledgers, and fails the run on any mismatch (#2361).

**Why this priority**: a green deploy can still serve a broken or stale site; #2361's week-long outage went unnoticed because nothing probed the live site.

**Independent Test**: evaluate the job graph with the smoketest failing and check that the run ends red; check the job runs the ledger-derived probe against the production domain with read-only permissions.

**Acceptance Scenarios**:

1. **Given** a successful deploy from `main`, **When** the run continues, **Then** the smoketest runs `python3 -m scripts.docs.site_live_probe https://docs.spec-kitty.ai`.
2. **Given** the probe reports a mismatch, **When** the smoketest ends, **Then** the run is red. No alert issue is filed: the operator decided the red run is the signal.
3. **Given** the deploy was skipped or failed, **When** the run continues, **Then** the smoketest does not run.

### User Story 3 - One `llms.txt` (Priority: P2)

The site generates `/llms.txt` (D-9). The hand-written `docs/llms.txt` is deleted, so there is one source.

**Independent Test**: `docs/llms.txt` is absent, and no live test, script or config reads it.

**Acceptance Scenarios**:

1. **Given** the cutover, **When** a reader fetches `/llms.txt`, **Then** the generated file answers (already probed by the live-site probe's `llms` class).
2. **Given** the deletion, **When** the docs test suite runs, **Then** no test requires `docs/llms.txt`.

### Edge Cases

- A dispatch with no input on `main` deploys and smoketests the doc-kitty site, like a push.
- A dispatch from a topic branch builds the site (useful for checking the build) but never deploys or smoketests.
- Pages not configured (probe answers 404): the build and the deploy skip, as today.
- The Pages probe answers another status: the run fails, as today.
- The smoketest's retries cover Pages propagation; each URL has a 300 s budget (already in the probe).
- A revert of this pull request must bring back the DocFX build and deploy, the canary jobs and `docs/llms.txt`.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Deploy the doc-kitty build | As a maintainer, I want a push to `main` to publish the doc-kitty build of the shared `docs-site-build.yml` (`pages-artifact: true`), not DocFX, so that main deploys only a site the gate's build definition built. | High | Open | [build] | no — the job-graph test fails on today's workflow, whose deploy needs the DocFX build |
| FR-002 | A failed build blocks the deploy | As a maintainer, I want a failed doc-kitty build to skip the deploy so that a broken build never goes live. | High | Open | [build] | no — paired with FR-001's positive run on the same model |
| FR-003 | Deploy only from main of the core repository | As the operator, I want nothing published from a fork or off `main`, behind the Pages probe-then-configure job, so that the production site has one source. | High | Open | [ratchet] | no — paired with FR-001's positive run |
| FR-004 | Post-deploy smoketest | As the operator, I want a job with `needs: deploy`, on `main` only and with read permissions only, to run the live-site probe against `https://docs.spec-kitty.ai` after every deploy, so that a broken live site is caught on the first run (#2361). | High | Open | [build] | no — today's workflow has no job after `deploy` |
| FR-005 | A smoketest failure leaves the run red | As the operator, I want a failed smoketest to turn the run red, with no alert issue, so that the failure is visible in the deploy pipeline. | High | Open | [build] | no — the test fails the smoketest job in the model and requires a failure result |
| FR-006 | Canary retired into the smoketest | As a maintainer, I want the dispatch-only canary jobs and the `canary` input removed, the smoketest being the one live-probe mechanism, so that no path deploys anything but the current site. | Medium | Open | [build] | no — the test requires the canary jobs and input to be absent |
| FR-007 | Delete `docs/llms.txt` | As a maintainer, I want the hand-written `docs/llms.txt` deleted and every live reference to it removed or updated (tests, scripts, DocFX config), with immutable history untouched, so that the generated `/llms.txt` is the one source (D-9). | Medium | Open | [build] | no — the parity test that reads the file is removed and a test asserts its absence |
| FR-008 | Record the cutover | As a reader of the ADR, I want an amendment to ADR 2026-10-31-1 recording the cutover, the canary evidence, the smoketest, the deletion of `docs/llms.txt` and exactly what a revert restores, and a changelog fragment, so that the decision trail is complete. | Medium | Open | [build] | no — the amendment and fragment are new files or sections checked by the docs gates |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Least privilege | The workflow's default token permission is `contents: read`; only the deploy job holds `pages: write` and `id-token: write`; the smoketest holds `contents: read` only. Asserted by tests. | Security | High | Open |
| NFR-002 | Pinned actions | Every action added or touched by this mission is pinned by a 40-character commit SHA. | Security | High | Open |
| NFR-003 | Behavioural tests | Every job-graph claim is tested by evaluating the real `if:` conditions with `tests/ci/_gh_expr.py` (#7484), never by restating YAML text; 0 tests are skipped or xfailed. | Reliability | High | Open |
| NFR-004 | Bounded smoketest | The smoketest job has a `timeout-minutes` of at most 60. | Reliability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Rollback is a revert | The DocFX build path, `docs/docfx.json`, `toc.yml`, the template and the DocFX scripts are not deleted; #6943 removes them. A revert of this pull request must restore DocFX publishing. | Technical | High | Open |
| C-002 | No production action | No workflow is dispatched and nothing is deployed from this mission; merging the pull request is the production switch, done by the operator. | Business | High | Open |
| C-003 | Immutable history | ADR bodies, plans, reports, changelog and archive pages are not edited; the ADR changes by amendment only. | Technical | High | Open |
| C-004 | Guards kept | The fork guard (`tests/ci/test_fork_guard.py`), the `pages` concurrency group and the ownership test (`tests/release/test_release_ci_ownership.py`) are kept; the ownership test is updated to pin the new deploy, never loosened. | Technical | High | Open |

### Key Entities

- **Deploy workflow** (`.github/workflows/docs-pages.yml`): jobs `pages` (probe and configure), `build` (calls the shared build), `deploy`, `smoketest`.
- **Shared build** (`.github/workflows/docs-site-build.yml`): the one doc-kitty build definition (D-11), called by the `docs-site` gate and by the deploy.
- **Live-site probe** (`scripts/docs/site_live_probe.py`): derives one URL per D-13 class from the ledgers and checks each over HTTP.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In the job-graph model, a push to `main` of the core repository runs `pages`, `build`, `deploy` and `smoketest`, in that order, all succeeding — [build] · no-op passable: no
- **SC-002**: In the model, a failure of `build`, `deploy` or `smoketest` leaves at least one failed job and no deploy after a failed build — [build] · no-op passable: no
- **SC-003**: In the model, 0 deploy or smoketest runs for a fork or a non-`main` ref — [ratchet] · no-op passable: no
- **SC-004**: 0 live files reference `docs/llms.txt`, and the targeted test set passes with 0 skips — [build] · no-op passable: no
- **SC-005**: After merge, the first deploy is green and its smoketest passes on `docs.spec-kitty.ai` (deferred: provable only after the operator merges; follow-up #6938) — [build] · no-op passable: no

## Assumptions

- Reading the Pages site configuration (`GET /repos/{repo}/pages`) and `actions/configure-pages` without enablement need `pages: read`, not `pages: write`.
- The DocFX build stops running in this workflow; a revert restores it. DocFX is then built nowhere in CI until the revert or #6943, which is acceptable to the operator.
