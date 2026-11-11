# Implementation Plan: Docsite diagrams

**Branch**: `kitty/mission-docsite-diagrams-01M72CFS` → lands on `issue-6936-docsite-diagrams` (from `main` after #7501) | **Date**: 2026-11-10 | **Spec**: [spec.md](spec.md)

## Summary

Turn on doc-kitty v0.7.0's build-time diagram rendering and prove it on the built site:

- **Config:** set `diagrams: true` in `site/astro.config.mjs`. Add `playwright` to `site/` as an exact-pinned dependency, at the version doc-kitty tests with.
- **Render environment:** run with `DK_DIAGRAM_BUILD_RENDER=build` and `DK_PLANTUML_SERVER_URL=http://localhost:8091/svg/`. Both are read from the process environment only. They go in the shared job's `env:` and the `make docs-site` target, not in `site/.env.production`.
- **PlantUML server in CI:** the shared `docs-site-build.yml` job runs `plantuml/plantuml-server:jetty-v1.2026.9@sha256:065c66ad…` as a job-level `services:` container with `PLANTUML_SECURITY_PROFILE: SANDBOX` and a readiness wait. The job then installs Playwright Chromium.
- **Canary check:** before the build, the job runs `dockitty-assert-plantuml-no-remote-include --service-container ${{ job.services.plantuml.id }} --canary-host <gateway> --astro-config astro.config.mjs`, as doc-kitty's own CI does (`ci.yml:258-264`). It also runs a thin wrapper over doc-kitty's `plantuml-guard` library.
- **Diagram surface:** a new surface in the built-site check, `scripts/docs/site_built_check_diagrams.py`, with mutant fixtures. Per published page, the rendered figure count equals the source block count. No raw diagram fence or error block remains, and no `plantuml.com` URL appears.
- **ADR:** ADR 2026-08-12-1 gets an amendment section. Its guarantee becomes "the renderer refuses every remote include, proven by a canary check".
- **DocFX:** the DocFX PlantUML path is untouched.

## Technical Context

**Language/Version**: Python 3.11+ (stdlib) for the surface and guard wrapper; GitHub Actions YAML; Astro/doc-kitty config (JS)
**Primary Dependencies**: doc-kitty v0.7.0 (`5acb83c`, pinned): `diagrams`, `DK_DIAGRAM_BUILD_RENDER`, `DK_PLANTUML_SERVER_URL`, `dockitty-assert-plantuml-no-remote-include`, `plantuml-guard`. Added:
- `playwright` (exact pin, version doc-kitty tests with);
- the PlantUML server image pinned by digest (operator decision).
**Storage**: N/A
**Testing**:
- pytest: the diagram surface over fixture `dist/` trees, with one mutant per failure mode;
- the real CI `docs-site` run: canary check, build, built-site check;
- local `make docs-site` needs docker for the server (documented helper or preflight). This container has no docker daemon, so the full render is proven in CI.
**Target Platform**: GitHub-hosted `ubuntu-24.04`
**Project Type**: single
**Performance Goals**: ≤ 4 min added to the `docs-site` job (NFR-001)
**Constraints**: C-001..C-005
**Scale/Scope**: 24 Mermaid + 8 PlantUML published blocks (5 `@startyaml`, verified renderable); about 6 files changed

## Charter Check

- **Single authority:**
  - The image digest lives once, in the shared workflow's `services:` block. The Makefile helper reads it from the same constant if possible; otherwise the duplication is named and pinned by a test that they are equal.
  - The published set comes from `_dockitty_contract`.
- **ATDD with lasting value (#7484):** the diagram surface's mutants go red first. The canary run is the security evidence. No YAML-shape tests.
- **Supply chain (DIRECTIVE_051):**
  - The new image is pinned by digest, taken from doc-kitty's consumer guide.
  - Playwright is pinned exactly, and Chromium comes via `playwright install chromium` at that version.
  - No credential.
  - The adversarial challenge is the independent review.
- **Immutable history:** the ADR change is an amendment section only.
- **Gate discipline:** no allowlist. A diagram the toolkit cannot render fails the gate.
- **Terminology:** run the terminology guard on the ADR text.

## Project Structure

```
site/astro.config.mjs                         # diagrams: true
site/package.json, site/pnpm-lock.yaml        # playwright (exact)
Makefile                                      # docs-site: diagram env vars + PlantUML server preflight/helper
scripts/docs/site_built_check_diagrams.py     # NEW surface
scripts/docs/site_built_check.py              # one registration line
scripts/docs/site_plantuml_guard.*            # NEW thin wrapper over doc-kitty's plantuml-guard (if a wrapper is needed)
.github/workflows/docs-site-build.yml         # services: plantuml, readiness wait, chromium, canary, env
tests/docs/test_site_built_check_diagrams.py  # NEW fixtures + mutants
tests/ci/test_docs_site_job.py                # only if a pin rule must cover the services image
docs/adr/3.x/2026-08-12-1-plantuml-schema-diagram-rendering.md  # amendment section
```

## Implementation Concern Map

### IC-01 — Render and prove diagrams

- **Purpose**: diagrams are static SVGs in the built site, and a broken one fails the gate.
- **Relevant requirements**: FR-001, FR-004, FR-005, NFR-003, SC-001, SC-003
- **Affected surfaces**: `astro.config.mjs`, `site/package.json` and lock, the Makefile, the diagram surface and its tests
- **Sequencing/depends-on**: none
- **Risks**: Playwright and Chromium version drift; no local server in this container.

### IC-02 — Sandboxed server, canary and ADR

- **Purpose**: PlantUML renders only against the pinned SANDBOX server, proven by a canary on every run.
- **Relevant requirements**: FR-002, FR-003, FR-006, NFR-001, NFR-002, SC-002
- **Affected surfaces**: the shared workflow, the guard wrapper, ADR 2026-08-12-1
- **Sequencing/depends-on**: IC-01
- **Risks**:
  - `ci-router.yml` churn (not touched here);
  - the gateway and canary-host derivation on GitHub runners;
  - #6933 edits the same workflow in parallel, so rebase the later one.
