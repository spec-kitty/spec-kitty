# Tasks: Docsite diagrams

**Mission**: `docsite-diagrams-01M72CFS` · [spec.md](spec.md) · [plan.md](plan.md)

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red: diagram surface fixtures + mutants | WP01 | |
| T002 | Diagram surface (`site_built_check_diagrams.py`) + registration | WP01 | |
| T003 | `diagrams: true`, exact-pinned `playwright` in site/ | WP01 | |
| T004 | Makefile: diagram env vars + PlantUML server preflight/helper | WP01 | |
| T005 | Shared workflow: `services: plantuml` (digest, SANDBOX, readiness), Chromium install, env | WP02 | |
| T006 | Canary check + plantuml-guard before the build | WP02 | |
| T007 | ADR 2026-08-12-1 amendment section | WP02 | |
| T008 | Prove on CI: canary green, every diagram an SVG, surface green | WP02 | |

## Phase 1 — Render and prove

### WP01 – Diagram rendering and the diagram surface
- FR-001, FR-004, FR-005; prompt [tasks/WP01-diagram-rendering-and-surface.md](tasks/WP01-diagram-rendering-and-surface.md). Dependencies: none.

T001 Red: diagram surface fixtures + mutants (WP01)
T002 Diagram surface (`site_built_check_diagrams.py`) + registration (WP01)
T003 `diagrams: true`, exact-pinned `playwright` in site/ (WP01)
T004 Makefile: diagram env vars + PlantUML server preflight/helper (WP01)

## Phase 2 — Sandbox and proof

### WP02 – Sandboxed PlantUML service, canary and ADR
- FR-002, FR-003, FR-006; prompt [tasks/WP02-sandboxed-service-canary-adr.md](tasks/WP02-sandboxed-service-canary-adr.md). Depends on WP01.

T005 Shared workflow: `services: plantuml` (digest, SANDBOX, readiness), Chromium install, env (WP02)
T006 Canary check + plantuml-guard before the build (WP02)
T007 ADR 2026-08-12-1 amendment section (WP02)
T008 Prove on CI: canary green, every diagram an SVG, surface green (WP02)
