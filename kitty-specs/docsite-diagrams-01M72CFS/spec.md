# Mission Specification: Docsite diagrams

**Mission Branch**: `kitty/mission-docsite-diagrams-01M72CFS` (lands on `issue-6936-docsite-diagrams`; built on PR #7501's branch, rebased onto `main` once #7501 lands)
**Created**: 2026-11-10
**Status**: Draft
**Input**: Issue #6936 of epic #6100; ADR `docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md` D-11 "Diagrams"; ADR `docs/adr/3.x/2026-08-12-1-plantuml-schema-diagram-rendering.md`; operator ruling of 2026-11-01 on #6936.

## Intent Summary

- **Primary actors:** a reader of `docs.spec-kitty.ai` after cutover; a maintainer who adds or edits a diagram in `docs/**`.
- **Trigger:** every pull request that selects the `docs-site` gate builds the site through the shared `docs-site-build.yml`.
- **Desired outcome:** every published Mermaid and PlantUML diagram (24 Mermaid blocks on 11 pages, 8 PlantUML blocks on 4 pages; see `research/code-grounding.md`) is a static SVG in the built site, rendered at build time, as DocFX shows them today. A maintainer whose diagram fails to render gets a red gate.
- **Rule that must always hold:** no diagram can make the renderer fetch remote content. PlantUML renders only against a self-hosted server pinned by digest, running the `SANDBOX` security profile; before the build, a canary check proves the running server refuses a remote include. Nothing renders against `plantuml.com`.
- **Operator decisions:**
  - Image: `plantuml/plantuml-server:jetty-v1.2026.9@sha256:065c66adc6728ba6dd353a29d4ada73f8358b68549a0f710c4bf46b43c103618`, the digest doc-kitty v0.7.0's consumer guide recommends.
  - Isolation: SANDBOX plus the canary check is enough. No network isolation is required, external includes stay off, and doc-kitty #268's opt-in is not used (ruling 2026-11-01).
  - DocFX's PlantUML path is left untouched (`scripts/docs/plantuml_*` and the checksum-verified jar restore); #6943 deletes it.
- **Test value (#7484):** the evidence is a check over the built site plus the real canary run on CI, not restatements of workflow YAML.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Diagrams render on the doc-kitty site (Priority: P1)

A reader opens an architecture page and sees its diagrams as images, not as raw `mermaid` or `plantuml` source.

**Why this priority**: diagrams carry the architecture docs; cutover (#6938) cannot ship code blocks in their place.

**Independent Test**: build the site. The built-site check counts, per page, the rendered diagram figures against the diagram blocks in the published source. It fails on any leftover raw diagram code block, any diagram error block, or any reference to `plantuml.com`. Mutant fixtures (a raw fence left, an error block, a missing figure, a `plantuml.com` URL) each make it fail.

**Acceptance Scenarios**:

1. **Given** the published docs, **When** the site is built, **Then** every Mermaid and PlantUML block is a static SVG figure, and no raw diagram fence remains.
2. **Given** a diagram that fails to render, **When** the site is built, **Then** the build or the built-site check fails.

### User Story 2 - The renderer cannot reach the network through a diagram (Priority: P1)

A maintainer (or an attacker editing a doc) writes a PlantUML `!include` of a remote URL; it is refused.

**Why this priority**: the security guarantee ADR 2026-08-12-1 gives today (no egress), restated for a service container.

**Independent Test**: before the build, the shared workflow runs `dockitty-assert-plantuml-no-remote-include` against the running service container, with a canary host. The check fails if the server fetches the canary, or if the container's security settings are not SANDBOX. doc-kitty's guard also asserts that no `plantuml.com` or non-self-hosted default reaches the build.

**Acceptance Scenarios**:

1. **Given** the pinned server running with SANDBOX, **When** the canary check runs, **Then** it passes, and the build continues.
2. **Given** a server without SANDBOX, or one that fetches the canary, **Then** the check fails and the build does not run.

### Edge Cases

- `@startyaml` schema diagrams (5 of the 8 PlantUML blocks) are valid PlantUML and render through doc-kitty v0.7.0's transform (verified 2026-11-10 with the pinned jar); the doc-kitty theme preamble does not reach them, so they keep PlantUML's default colours (cosmetic, upstream suggestion).
- Local `make docs-site` has no service container: it needs a documented way to run the same pinned image, or must fail clearly when no server is reachable.
- A diagram in an unpublished page (draft, excluded, archived) is not rendered and is not counted.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Diagrams render at build time | As a reader, I want every published Mermaid and PlantUML block rendered as a static SVG in the built site, so that diagrams read as on DocFX. | High | Open | [build] | no — the current build ships them as raw code blocks |
| FR-002 | Pinned sandboxed PlantUML server | As a maintainer, I want the shared build to run the PlantUML server as a job-level service, pinned by digest, with the SANDBOX profile and a readiness wait, so that PlantUML renders against a known, restricted server. | High | Open | [build] | no — no server runs today |
| FR-003 | Canary proof before the build | As a maintainer, I want the canary check (`--canary-host`, `--service-container`) to run before the build and fail it if the server would fetch a remote include, so that the no-egress guarantee is proven on every run. | High | Open | [build] | no — no check runs today |
| FR-004 | Built-site diagram surface | As a maintainer, I want the built-site check to fail on a leftover raw diagram fence, a diagram error block, a missing figure or a `plantuml.com` reference, so that a broken diagram cannot ship. | High | Open | [build] | no — mutants prove it fails |
| FR-005 | Deterministic render mode | As a maintainer, I want diagrams rendered in build mode, with a pinned Chromium, in CI and locally, so that local and CI builds do not differ. | Medium | Open | [build] | no — the mode follows whether a browser happens to be installed |
| FR-006 | ADR records the guarantee | As a reader of the ADRs, I want ADR 2026-08-12-1 amended to say the renderer refuses every remote include, proven by a canary check, so that the decision record matches the build. | Medium | Open | [build] | no — the ADR describes `--network=none` |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Build time | The diagram steps add at most 4 minutes to the `docs-site` job on CI. | Performance | Medium | Open |
| NFR-002 | Pinned inputs | The server image is pinned by digest, Chromium by an exact version, and every third-party action by commit; no credential is used. | Security | High | Open |
| NFR-003 | Check fidelity | The diagram surface fails on 100% of its mutant fixtures. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | DocFX path untouched | `scripts/docs/plantuml_*`, the jar restore and `docs-pages.yml` are not changed. | Business | High | Open |
| C-002 | No external includes | doc-kitty #268's external-include opt-in is not used. | Security | High | Open |
| C-003 | Immutable history | ADR bodies are not rewritten; the change is an amendment section. | Business | High | Open |
| C-004 | Upstream first | A doc-kitty gap is filed upstream before any local workaround, and is named in the PR. | Technical | High | Open |
| C-005 | Out of scope | Redirects (#6933), cutover (#6938), DocFX retirement (#6943). | Business | High | Open |

### Key Entities

- **PlantUML service**: the pinned server image, its security profile and its port.
- **Canary check**: doc-kitty's remote-include assertion against the running service.
- **Diagram surface**: the built-site check's per-page count of rendered figures against source blocks.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 0 raw diagram code blocks and 0 diagram error blocks in the built site; the figure count equals the published source block count. — [build] · no-op passable: no
- **SC-002**: The canary check runs and passes on the landing pull request's `docs-site` job. — [build] · no-op passable: no
- **SC-003**: Every diagram-surface mutant fixture makes the check fail. — [build] · no-op passable: no

## Assumptions

- doc-kitty v0.7.0's own CI pattern (`services:` block, `job.services.plantuml.id` for `--service-container`, the canary host from the service gateway) works on GitHub-hosted runners; doc-kitty #287 (non-container services) is not needed.
- Playwright is added to `site/` as an exact-pinned dependency (doc-kitty tests with 1.62.1); `make docs-site-bump` does not track it.
- The two diagram environment variables are read only from the process environment, so they go in the job `env:` and the Makefile, not `site/.env.production`.
