---
title: Architecture Diagrams (living C4)
description: The living C4 model for the current architecture, carried forward from the 2.x snapshot and refreshed in place against the ratified domain model.
doc_status: active
updated: '2026-10-08'
audience: docs/context/audience/internal/system-architect.md
related:
- docs/architecture/README.md
- docs/architecture/diagrams/01_context/README.md
- docs/architecture/diagrams/02_containers/README.md
- docs/architecture/diagrams/03_components/README.md
---
# Architecture Diagrams (living C4)

This directory holds the **living C4 model** for the **current architecture**.
It is not era-stamped: it was carried forward from the 2.x snapshot and is refreshed
in place against the ratified domain model. It is one of the living surfaces
described in [`../README.md`](../README.md).

The numbered C4 levels are kept stable so navigation and tooling stay predictable:

| Level | Directory | Scope |
|---|---|---|
| C4 L1 — Context | [`01_context/`](01_context/README.md) | System boundary, actors, external interactions |
| C4 L2 — Containers | [`02_containers/`](02_containers/README.md) | The four bounded modules + the Op execution tier |
| C4 L3 — Components | [`03_components/`](03_components/README.md) | Component-level behavior sequences |

## The domain model these diagrams depict

The model is the **four bounded modules** ratified in
[`docs/adr/3.x/2026-06-03-1-execution-state-domain-model.md`](../../adr/3.x/2026-06-03-1-execution-state-domain-model.md):

| Module | Domain responsibility |
|---|---|
| **Governance** | Charter and Doctrine artifacts — what the project is allowed to do and how |
| **Mission Management** | Mission lifecycle, WP status/kanban, status events, planning artifacts |
| **Execution / Runtime** | Workspace resolution, branch state, mission-run lifecycle, CWD-invariant context |
| **Shared Kernel** | Value types, identifiers, and utilities shared across modules — no domain logic |

Modules communicate via **Open Host Service (OHS) facades** only; direct
cross-module imports of internal submodules are prohibited by architectural tests.
Status and kanban are owned **exclusively by Mission Management** (the `status/`
OHS facade). The canonical execution-state surface is the top-level
[`mission_runtime`](../../adr/3.x/2026-06-07-1-execution-state-canonical-surface.md)
package. The **Op execution tier** (`spec-kitty dispatch` plus
`profile-invocation complete` and the pre/post-mission lifecycle) sits across
the modules as the shared Op shape.

### How the modules map onto the enforced layer packages

The four modules are *domain* boundaries. The *import* boundaries CI enforces are
the wheel packages in `pyproject.toml` and the layer chain in
`tests/architectural/test_layer_rules.py`:
`kernel <- charter <- {glossary, runtime, mission_runtime} <- specify_cli`.
The two views line up like this:

| Module | Main packages |
|---|---|
| Shared Kernel | `src/kernel/` (root layer) |
| Governance | `src/charter/` (including `charter/offering/`, the charter offering package that absorbed the former `doctrine` package) and `src/glossary/` |
| Execution / Runtime | `src/mission_runtime/` (execution-state surface) and `src/runtime/` (the `spec-kitty next` control loop); workspace resolution under `src/specify_cli/workspace/` |
| Mission Management | `src/specify_cli/` (status, lanes, consolidation, coordination, the CLI) |

When a diagram and the enforced pair disagree, the enforced pair wins and the
diagram is the thing to fix.

## Convention

- **Hand-authored Markdown + Mermaid** (renders on GitHub, no build tooling) — R-04.
- Each level uses a single canonical `README.md` entrypoint; additional detail
  pages may live beside it.
- The 2.x snapshot under `docs/architecture/{01_context,02_containers,03_components}/`
  is frozen as history; this living copy is the one refreshed against the
  current domain model.

> Deterministic diagram **generation** (Structurizr/PlantUML) is deliberately out
> of scope here — see upstream `#1839` (deduped vs `#1812`). This living C4 stays
> hand-authored per R-04; the generated-C4 swap is cross-referenced only.
>
> **R-04 carve-out (2026-08-12) — a separate lane, not a reversal.** R-04 is
> **unchanged for the hand-authored C4 architecture diagrams** in this directory:
> they stay hand-authored Markdown + Mermaid so they render on GitHub, and
> deterministic *generation of the C4 model* remains out of scope. A **new,
> narrowly-scoped lane** now covers a different genre — **generated,
> docsite-only schema diagrams of code models** (the doctrine artefact schemas:
> agent-profile, mission-type/step, DRG, artefact-kind vocabulary). Those are
> `@startyaml` diagrams generated from the frozen models, rendered at docs-build
> time and drift-guarded, and they render **only on the built docsite**, not on
> github.com source view. This lane does **not** touch the C4 diagrams here. See
> [`../../adr/3.x/2026-08-12-1-plantuml-schema-diagram-rendering.md`](../../adr/3.x/2026-08-12-1-plantuml-schema-diagram-rendering.md).
