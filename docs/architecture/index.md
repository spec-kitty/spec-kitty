---
title: Architecture
description: 'Landing page and page index for docs/architecture/: the boundary rule between decisions and consumption, living and frozen pages, the decay rule, and ADR locations.'
doc_status: active
updated: '2026-11-01'
audience:
- profile: internal/system-architect
  guidance_text: Written for the System Architect reader.
related:
- adr/3.x/2026-04-06-2-connector-auth-binding-separation
- adr/3.x/2026-04-06-3-github-app-installation-authority
- architecture/diagrams/01_context
- architecture/diagrams/02_containers
- architecture/diagrams/03_components
- ''
external_references:
- url: https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/architecture/ARCHITECTURE_DOCS_GUIDE.md
  title: Architecture Documentation Guide
- url: https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/architecture/NAVIGATION_GUIDE.md
  title: Architecture Navigation Guide
- url: https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/architecture/feature-detection.md
  title: 'Architecture: Centralized Feature Detection'
- url: https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/architecture/gap-analysis-connector-installation-model.md
  title: 'Gap Analysis: Migrating Spec-Kitty to the Installation-Link-Mapping-Override Connector Model'
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

## Page index

Every page in `docs/architecture/`. These pages capture design rationale and models; they are working engineering material rather than end-user documentation.

### Living architecture (current + forward)

- [Architecture Vision (living)](vision/README.md) — current and future forward intent, including the 4.x forward signal.
- [Architecture Diagrams (living C4)](diagrams/README.md) — the living C4 model and how its modules map onto the enforced layer packages.
- [Diagrams: System Context (living)](diagrams/01_context/README.md) — C4 level 1, including Team Kitty and the Zeitgeist relay.
- [Diagrams: Containers (living)](diagrams/02_containers/README.md) — C4 level 2.
- [Diagrams: Runtime/Execution Domain (living)](diagrams/02_containers/runtime-execution-domain.md) — C4 level 2 container detail.
- [Diagrams: Components (living)](diagrams/03_components/README.md) — C4 level 3.
- [System Landscape (living)](00_landscape/README.md) — C4 level 0: domain containers and the packages that implement them.
- [Implementation Mapping (living)](04_implementation_mapping/README.md) — C4 level 4: where each architecture concept lives in the source tree.
- [Core Code Patterns Applied in the Codebase](04_implementation_mapping/code-patterns.md) — recurring implementation idioms mapped to components.

### Explanations

- [Explanation](explanation-index.md) — the Divio "understanding-oriented" hub for this section.
- [Spec-driven development](spec-driven-development.md) — the core methodology.
- [Mission system](mission-system.md) — how missions and work packages relate.
- [Mission-type resolution](mission-type-resolution.md) — the doctrine → charter → core seam.
- [Execution lanes](execution-lanes.md) — the lane-based parallel execution model.
- [Git worktrees](git-worktrees.md) — what worktrees share and keep separate.
- [Git workflow: who does what](git-workflow.md) — infrastructure git vs content git.
- [Multi-agent orchestration](multi-agent-orchestration.md) — coordinating work across agents.
- [Zeitgeist publisher and lease identity](zeitgeist-session-identity.md) — logical agents, SaaS leases, and relay session references.
- [Kanban workflow](kanban-workflow.md) — the nine lanes and their transitions.
- [Mission transition gates](mission-gates.md) — the declarative, asset-backed, trust-gated model for the checks that guard lane transitions.
- [The acceptance scenario contract](acceptance-scenario-contract.md) — how scenarios link to product promises by identifier only, the per-PR scenario check, and the nightly evidence bundle.
- [The runtime loop](runtime-loop.md) — how `spec-kitty next` inverts control.
- [AI agent architecture](ai-agent-architecture.md) — how Spec Kitty stays agent-agnostic across the 17 supported agents.
- [Why the Divio documentation system?](divio-documentation.md) — tutorials/how-to/reference/explanation mapping.
- [Doctrine relationships](doctrine-relationships.md) — DRG relation types as typed graph edges.
- [Understanding the org layer of the charter offering](org-doctrine-layer.md) — built-in/org/project-layer resolution.
- [Understanding Charter: synthesis, DRG, and governed context](charter-synthesis-drg.md).
- [Understanding governed profile invocation](governed-profile-invocation.md) — standalone dispatch under governance.
- [Profile-load reliability](profile-load-reliability.md) — why squads stopped loading charter agent profiles, and the stabilization design (partly shipped in 3.2.6; the rest is on 4.x Work).
- [Charter backend service (future)](charter-backend-service-future.md) — preliminary backlog design for a deployable charter/doctrine resolution endpoint.
- [Documentation Mission Guide](documentation-mission.md) — the Documentation Kitty mission.
- [Understanding the retrospective learning loop](retrospective-learning-loop.md) — the four-category model.
- [The Artifact Placement Seam](artifact-placement-seam.md) — the layer model deciding which physical tree a mission artifact resolves to, and where callers bypass it.
- [Post-merge partition authority](post-merge-partition-authority.md) — one model for the write half (which bytes win per artifact on squash) and the read half (which surface a post-merge reader trusts).
- [The activation ledger and the charter contract](activation-ledger-and-charter-contract.md) — how core's activation ledger maps onto the charter service's activation contract through one seam, what diverges, and the impact on the remaining work.
- [Branch-target routing](branch-target-routing.md) — which git branch receives each type of change.
- [WP runtime-state eviction](wp-runtime-state-eviction.md) — evicting runtime-mutable state into the event log.
- [Doctrine artifact kinds](doctrine-kinds.md) — what each of the eight doctrine artifact kinds is for, with a built-in example of each.
- [SPDD and the REASONS Canvas](spdd-reasons.md) — the opt-in Structured-Prompt-Driven Development artifact set and its change-intent canvas.
- [Team Kitty and Zeitgeist](../context/team-kitty.md) — the live hosted model: CLI → per-team Zeitgeist relay → Team Kitty Pulse, with the lane-transition sequence diagram.

### Status, trail & workflow models

- [Status model (operator reference)](status-model.md) — the append-only event-log lane state machine, the `--mission` selector, and `mission_id` ULID identity.
- [Event ledger writers and readers](event-ledger-writers-and-readers.md) — every event log core writes and reads today, the target the event ADRs set, and the cited gap table.
- [Trail model](trail-model.md) — how every standalone dispatch writes an auditable JSONL trail for accountability and provenance.
- [Host-surface parity matrix](host-surface-parity.md) — how each supported host surface teaches the governance-injection contract, with per-surface parity status.
- [Spec Kitty mission workflow (canonical authority)](spec-kitty-mission-workflow.md) — the nine-phase end-to-end mission workflow and the focused-PR path.

### Connector & installation decisions

- [Connector auth / binding separation](../adr/3.x/2026-04-06-2-connector-auth-binding-separation.md) — separating connector authentication from binding.
- [GitHub App installation authority](../adr/3.x/2026-04-06-3-github-app-installation-authority.md) — installation-authority model for the GitHub App.

### Assessments

- [Code as a Crime Scene — High-Level Overview](assessments/code-as-a-crime-scene-overview.md) — pedagogical overview of the CaaCS auditing technique (durable methodology explainer; the dated 2026-05 forensic run itself lives under [`docs/archive/plans/engineering-notes/architecture-audits/`](https://github.com/spec-kitty/spec-kitty/tree/main/docs/archive/plans/engineering-notes/architecture-audits/)).

### Calibration reports

- [Calibration Report Template](calibration/README.md) — the per-mission-type DRG context calibration template: does context resolution return what each step needs, and nothing irrelevant?
- [Calibration Report: documentation](calibration/documentation.md).
- [Calibration Report: erp-custom](calibration/erp-custom.md).
- [Calibration Report: research](calibration/research.md).
- [Calibration Report: software-dev](calibration/software-dev.md).

### Ownership & charter models

- [Unified Charter Bundle](06_unified_charter_bundle.md) — the single-file authoritative `charter.yaml` model.
- [Activation Preset Usage Journey](charter-pack-usage-journey.md) — the `activate --preset` → `generate` two-step and the empty-charter dispatch safety net.

### Templates & reference

- [ADR template](adr-template.md) — the shared ADR authoring template used by all eras.
- [Pip vs pipx vs uv](pip-vs-pipx-vs-uv.md) — which installer to use for the Spec Kitty CLI.

### Historical / prior cycle

Kept as records; not maintained as current.

- [Vision history slot — 3.x](vision/README-3.x.md) — the prior era's settled vision, including the 2026-08-12 forward signal.
- [Vision history slot — 2.x](vision/README-2.x.md) — per-era vision record for 2.x.
- [Vision history slot — 1.x](vision/README-1.x.md) — per-era vision record for 1.x.
- [2.x System Context](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/architecture/01_context/README.md) — frozen 2.x C4 level 1 snapshot.
- [2.x Containers](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/architecture/02_containers/README.md) — frozen 2.x C4 level 2 snapshot.
- [2.x Runtime/Execution Domain](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/architecture/02_containers/runtime-execution-domain-2x.md) — frozen 2.x C4 level 2 container detail.
- [2.x Components](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/architecture/03_components/README.md) — frozen 2.x C4 level 3 snapshot.
- [Functional Ownership Map (demoted)](05_ownership_map.md) — superseded narrative; module boundaries are owned by the enforced pyproject package list and layer rules.
- [Architecture: centralized feature detection](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/architecture/feature-detection.md) — the v0.14.0 centralized mission-selection design, superseded by `mission_id` identity.
- [Launch-readiness behavior (archived)](launch-readiness-future.md) — stub kept so old links resolve; the superseded pre-Zeitgeist launch plan built on the retired sync gate is [archived](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/architecture/launch-readiness-future.md).
- [Team Kitty (SaaS) hosted-sync flow (removed)](team-kitty-saas.md) — stub kept so old links resolve; the flow was removed in #6164.
- [Gap analysis: connector installation model](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/architecture/gap-analysis-connector-installation-model.md) — point-in-time 2026-03 gap analysis against the pre-convergence code.
- [Architecture Documentation Guide](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/architecture/ARCHITECTURE_DOCS_GUIDE.md) — retired 2.x-era guide; redirects to the documentation home and `llms.txt`.
- [Architecture Navigation Guide](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/architecture/NAVIGATION_GUIDE.md) — retired 2.x-era guide; redirects to the documentation home and `llms.txt`.

## See also

- [Documentation home](../index.md)
- [Architecture Decision Records](../adr/index.md)
- Project terminology canon: [glossary conventions](../context/glossary-conventions.md)
