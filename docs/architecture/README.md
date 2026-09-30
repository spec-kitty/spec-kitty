---
title: Architecture
description: 'Landing page for the architecture corpus: what lives in docs/architecture/ versus docs/adr/, which pages are living, and which are frozen history.'
doc_status: active
updated: '2026-09-30'
audience: docs/context/audience/internal/system-architect.md
related:
- docs/archive/architecture/ARCHITECTURE_DOCS_GUIDE.md
- docs/archive/architecture/NAVIGATION_GUIDE.md
- docs/architecture/diagrams/01_context/README.md
- docs/architecture/diagrams/02_containers/README.md
- docs/architecture/diagrams/03_components/README.md
---
# Architecture

This directory is the architecture corpus for Spec Kitty. The active release cycle
is **4.0.0** (see the [4.0.0 milestone roadmap](../plans/4-0-0-milestone-roadmap.md)).

## Boundary rule (single source of truth)

Two surfaces, two jobs. They never duplicate each other:

| Surface | Holds | Authority |
|---|---|---|
| `docs/architecture/` + `docs/adr/` | **Decisions & models**: ADRs, C4 diagrams, vision, audits, calibration | Authoritative; changes are deliberate and reviewed |
| The rest of `docs/` | **Consumption**: tutorials, how-tos, reference, context | Reader-facing; narrates and links *up* to architecture |

- **Architecture = decisions & models.** ADRs (under `docs/adr/`), the C4 model, vision,
  audits and calibration are the deliberately changed source of truth.
- **Reader-facing docs link up; they never duplicate architecture narrative.** When the
  two overlap, architecture wins.
- **Vision is an architecture concern.** There is no `docs/vision/`; forward intent lives
  in `docs/architecture/vision/`.
- **Terminology canon lives in the glossary context pages** (see
  [glossary conventions](../context/glossary-conventions.md)). Architecture docs
  *reference* glossary terms; they do not host a second glossary.
- **Module boundaries are owned by code, not prose.** The enforced pair (the
  `pyproject.toml` wheel package list plus `tests/architectural/test_layer_rules.py`)
  is the modularity source of truth; every module map in this directory is a derived view.

## Living pages and frozen history

- **Living** (describes the architecture now and going forward; not era-stamped):
  - `docs/architecture/vision/`: current and future vision (forward intent).
  - `docs/architecture/diagrams/`: the living C4 model (`01_context/`, `02_containers/`,
    `03_components/`), hand-authored Markdown + Mermaid.
  - `docs/architecture/00_landscape/` and `docs/architecture/04_implementation_mapping/`:
    the landscape and the concept-to-code map, kept current with the package layout.
  - The topical explanation pages at the top of `docs/architecture/`.
- **Frozen history**:
  - `docs/architecture/01_context/`, `02_containers/`, `03_components/`: the 2.x C4
    snapshot. Not refreshed; the living copy is under `diagrams/`.
  - `docs/adr/<era>/`: dated, immutable decision records per era.

### Decay rule (so the layout can't re-drift)

When a living page stops being current, it is **relabelled as history** rather than
deleted: set its `doc_status` to `superseded` (naming the successor) or `deprecated`,
add a one-line banner under the H1, and move its index entry into the history group.
For vision content, the era history slots are `vision/README-<era>.md`. Nothing is
silently rewritten; history accrues by era.

## Structure

| Path | Purpose |
|---|---|
| `docs/architecture/vision/` | Living current + future architecture vision (forward intent) |
| `docs/architecture/diagrams/` | Living C4 model: `01_context/`, `02_containers/`, `03_components/` |
| `docs/architecture/00_landscape/`, `04_implementation_mapping/` | Living landscape and implementation mapping (derived views of the module map) |
| `docs/architecture/01_context/`, `02_containers/`, `03_components/` | Frozen 2.x C4 snapshot |
| `docs/adr/<era>/` | ADRs by era: `1.x/`, `2.x/`, `3.x/` (see below) |
| `docs/context/audience/` | Persona catalog for architecture audiences and actor links |
| `docs/plans/engineering-notes/architecture-audits/` | Architecture audits (point-in-time forensic records) |
| `docs/architecture/calibration/` | Per-mission-type calibration notes |
| `docs/architecture/assessments/` | Code-as-a-crime-scene and similar assessments |
| `docs/architecture/adr-template.md` | Shared ADR template used by all eras |

> **Layout is structure, not policy.** Directory layout here encodes only the boundary,
> era and decay rules. It does **not** encode per-artifact tiering: a future optional
> per-artifact *tier* (upstream `#1843`), if introduced, is a **declared field** on
> artifacts, never a directory level.

## ADR locations

ADRs are grouped into era folders under `docs/adr/<era>/`. The [ADR index](../adr/index.md)
lists them all.

- `docs/adr/1.x/`: 1.x-era decisions.
- `docs/adr/2.x/`: 2.x-era decisions (frozen).
- `docs/adr/3.x/`: 3.x-era decisions, through the start of the 4.0.0 cycle.
- ADRs for the 4.x line land in `docs/adr/4.x/`.

Older era folders remain authoritative for the decisions made in those eras; a later
ADR supersedes an earlier one explicitly, never by silence.

## C4 model

The living C4 lives under `docs/architecture/diagrams/` with stable numbered levels:

1. [`diagrams/01_context/README.md`](diagrams/01_context/README.md): system boundary and external interactions.
2. [`diagrams/02_containers/README.md`](diagrams/02_containers/README.md): runtime/governance container responsibilities.
3. [`diagrams/03_components/README.md`](diagrams/03_components/README.md): component-level behavior sequences.

C4 is **hand-authored Markdown + Mermaid** (renders on GitHub, no build tooling).
The 2.x C4 under `docs/architecture/{01_context,02_containers,03_components}/` is kept
frozen as the 2.x snapshot; the living copy under `diagrams/` is the one refreshed
against the current domain model. (Generated-C4 tooling is deferred: `#1812`.)

## Creating a new ADR

Copy the shared template into the era folder for the current line:

```bash
cp docs/architecture/adr-template.md docs/adr/<era>/YYYY-MM-DD-N-your-decision.md
```

Use an older era folder only when documenting legacy behavior for that era.

## Find ADRs

```bash
ls -1 docs/adr/*/ | sort
rg -n "Status:|Decision Outcome|Technical Story" docs/adr/
```

## See also

- Project terminology canon: [glossary conventions](../context/glossary-conventions.md)
- [ADR index](../adr/index.md)
- [`docs/archive/architecture/ARCHITECTURE_DOCS_GUIDE.md`](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/architecture/ARCHITECTURE_DOCS_GUIDE.md)
- [`docs/archive/architecture/NAVIGATION_GUIDE.md`](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/architecture/NAVIGATION_GUIDE.md)
