# Mission Specification: Docsite shared build definition

**Mission Branch**: `kitty/mission-docsite-shared-build-01M70V33` (lands on `issue-6937-docs-site-shared-build`)
**Created**: 2026-11-09
**Status**: Draft
**Input**: The remaining part of #6937 (ADR `docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md` D-11): the pull-request docs-site gate and the future Pages deploy share one build definition, so `main` can never deploy a site no pull request built.

## Intent Summary

- **Primary actor:** a maintainer (or the CI router acting for them) who changes `docs/**`, `site/**` or the docsite's build inputs.
- **Trigger:** a pull request, merge-group run or push that selects the `docs-site` gate; later (#6938) a push to `main` that deploys.
- **Desired outcome:** the docsite is built by exactly one definition. Today the router's `docs-site` job calls it; at cutover the Pages deploy calls the same definition with a Pages upload. Nothing else changes for the maintainer: the gate stays required and behaves as before.
- **Rule that must always hold:** the build that gates a pull request and the build the deploy will publish are the same steps; the gate stays required (a red build blocks `router gate`); the build uses no credential and only commit-pinned third-party actions.
- **Decisions (operator, 2026-11-09, recorded as Decision Moments):** a reusable workflow, not a composite action, because #6936 needs job-level `services:`; this mission lands before #6932–#6936 so they add their gate steps to the shared definition; the deploy is not switched here.
- Grounding: `research/code-grounding.md`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The gate builds through the shared definition (Priority: P1)

A maintainer opens a pull request that touches `docs/**`. The `docs-site` gate runs, builds the site through the shared definition, uploads `site/dist`, and `router gate` reports its result exactly as before.

**Why this priority**: the gate is required on `main`; moving it must not weaken it.

**Independent Test**: the router's tests read the called definition (not the now step-less caller) and show the contract check, frozen install, build and upload, commit pins and no credential; a red row of the called build blocks the router gate.

**Acceptance Scenarios**:

1. **Given** a pull request touching `docs/guides/x.md`, **When** the router selects gates, **Then** `docs-site` is selected and its job calls the shared definition.
2. **Given** the shared build fails, **When** `router gate` classifies the run's job rows (the called job is reported as `<caller> / <callee>`), **Then** the gate blocks.
3. **Given** a pull request that edits only the shared definition, **When** the router selects gates, **Then** `docs-site` is selected (the definition is one of the docsite's inputs).

---

### User Story 2 - The deploy can reuse the definition at cutover (Priority: P2)

At cutover (#6938) the deploy workflow calls the same definition and asks for a Pages artifact instead of a plain artifact.

**Why this priority**: it is the point of D-11, but the switch itself is #6938.

**Independent Test**: a test reads the shared definition and shows it is callable from another workflow, needs no secret, and, when asked for a Pages artifact, uploads `site/dist` as one through a commit-pinned action; the router's call does not ask for it.

**Acceptance Scenarios**:

1. **Given** the shared definition, **When** a caller passes the Pages-artifact input, **Then** the upload step that runs is the Pages-artifact upload of `site/dist`, and the plain upload does not run.
2. **Given** the router's `docs-site` call, **When** it runs, **Then** it does not request a Pages artifact.

### Edge Cases

- A fork pull request: the gate behaves as today (it follows `changes`, which carries the core-repository guard).
- `pr:pause-ci`: the gate skips with `changes`, as today.
- A test that reads the caller's `steps` after extraction would pass vacuously; every step-level check must read the called definition, with a mutant proving it is not vacuous.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | One shared build definition | As a maintainer, I want the docsite build steps (contract check, frozen install, build, upload) defined once, in a definition other workflows can call, so that the gate and the deploy cannot drift. | High | Open | [build] | no — on the base the router job holds the steps inline and no callable definition exists |
| FR-002 | The gate calls it | As a maintainer, I want the router's `docs-site` job to build only by calling the shared definition, so that the gate is the shared build. | High | Open | [build] | no — on the base the job has inline steps |
| FR-003 | The gate stays required | As a maintainer, I want `docs-site` to stay in `router-gate`'s `needs:`, without `continue-on-error`, with the advisory set empty, and a red row of the called build to block the gate, so that extraction does not weaken the merge check. | High | Open | [ratchet] | yes — paired with the red-row-blocks positive control on the called job's real row name |
| FR-004 | Step checks read the called definition | As a reviewer, I want the commit-pin, no-credential, frozen-install, contract-check and no-swallowed-failure checks to read the steps that actually run, each with a mutant, so that they cannot pass vacuously on a step-less caller. | High | Open | [build] | no — on the base the checks read the caller's steps, which are about to disappear |
| FR-005 | Deploy-reuse input | As the #6938 implementer, I want an input that makes the shared definition upload `site/dist` as a Pages artifact (and skip the plain upload), off by default, so that the deploy can call the same build. | High | Open | [build] | no — no such input exists on the base |
| FR-006 | The definition is a docsite input | As a maintainer, I want a change to the shared definition to select the `docs-site` gate (and its documentation copy in the CI retirement scrub to match), so that the definition is tested on the pull request that changes it. | Medium | Open | [build] | no — the filter does not name the new file on the base |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No credential | The shared definition and its caller reference 0 secrets and 0 tokens, and request no permission beyond `contents: read`. | Security | High | Open |
| NFR-002 | Commit-pinned actions | 100% of third-party `uses:` in the shared definition are pinned by a 40-character commit. | Security | High | Open |
| NFR-003 | Same build time budget | The called job keeps a timeout of at most 20 minutes, as today. | Reliability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Reusable workflow | The shared definition is a reusable workflow (operator decision 2026-11-09), so #6936 can add a job-level `services:` container to it. | Technical | High | Open |
| C-002 | Deploy unchanged | `.github/workflows/docs-pages.yml` is not edited; DocFX keeps deploying; the D-12 pins in `tests/release/test_release_ci_ownership.py` stay green unchanged. | Business | High | Open |
| C-003 | No new gates | No new size or ratchet gate and no allowlist (Standing Order #5); the gate set of the docs-site build is unchanged by this mission. | Technical | High | Open |
| C-004 | Out of scope | The gates of #6932–#6936 and the deploy switch of #6938 are not added here. | Business | High | Open |

### Key Entities

- **Shared build definition**: the one callable description of how the docsite is built and uploaded.
- **Gate caller**: the router's `docs-site` job, which calls the definition and makes it required.
- **Deploy caller** (future, #6938): the Pages workflow, which will call the definition with the Pages-artifact input.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The docsite build steps exist in exactly 1 workflow file; the router's `docs-site` job has 0 inline steps. — [build] · no-op passable: no
- **SC-002**: On the pull request that lands this, the `docs-site` gate is green and `router gate` is green. — [ratchet] · no-op passable: yes (paired with SC-003)
- **SC-003**: Every step-level check of the docs-site tests fails on at least 1 mutant of the called definition. — [build] · no-op passable: no
- **SC-004**: A test proves the deploy can reuse the definition (Pages-artifact input) without changing it. — [build] · no-op passable: no

## Assumptions

- GitHub reports a called workflow's job as `<caller job name> / <called job name>` in the jobs API; `router gate` classifies every row of the run, so that row is classified like any other.
- `actions/upload-pages-artifact` v5.0.0 is `fc324d3547104276b827a68afc52ff2a11cc49c9`.
