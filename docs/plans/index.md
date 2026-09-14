---
title: Plans
description: 'Plans landing page: durable domain throughlines plus the distil-then-retire working surface of investigations, research, initiatives, and release-scoped plans.'
doc_status: active
updated: '2026-08-12'
related:
- docs/plans/4-0-0-milestone-roadmap.md
- docs/plans/code-quality/index.md
- docs/plans/domains/index.md
- docs/plans/domains/doctrine-charter-domain-plan.md
- docs/plans/3-2-x-milestone-roadmap.md
- docs/changelog/release-goals.md
---
# Plans

Two kinds of document live here. **Domain throughlines** are durable and persist
across releases. Everything else is the **distil-then-retire** working surface —
investigations, research, initiatives, user journeys, and release-scoped plans that
retire once distilled into durable architecture/reference docs (Mission B, FR-009).

## Domain throughlines (version-spanning)

Domain throughlines are the standing strategy for a domain. They hold the durable
"why" — invariants, sub-areas, cross-references — and point at the release-scoped
epics and roadmaps for the "what ships when" rather than duplicating them. Epics are
release/milestone-scoped tracking, not the throughline. Unlike the working notes
below, a throughline does not retire when a milestone closes.

- **SaaS & hosted sync** — domain plan retired 2026-09-06 (Convergence #3881): the local
  sync transport was removed and the hosted surface re-homed to the authoritative upstream
  repos (`spec-kitty/zeitgeist`, `spec-kitty/saas`); this repo consumes their clients. See the
  [convergence-retirement ADR](../adr/3.x/2026-09-06-1-convergence-retirement-and-client-repo-inversion.md).
- **Doctrine & charter** — [Doctrine & Charter — Domain Plan](domains/doctrine-charter-domain-plan.md):
  charter lifecycle & sole-door access, pack extensibility, activation-driven
  availability, meta.json fail-closed reads, the public API surface, and
  glossary-as-doctrine. Its release- and program-scoped companions are the
  [3.2.x Open-Core Delivery Plan](3-2-x-open-core-delivery-plan.md) and the
  [Glossary Doctrine Overhaul — Program Plan](glossary-doctrine-overhaul-program.md).
- **Packs extraction** — [Packs Extraction — Domain Plan](domains/packs-extraction-domain-plan.md):
  physically extracting the doctrine layer into the standalone `spec-kitty-doctrine`
  module — boundary definition, import-cycle break, strangler cutover, and repo split.
- **API & dashboard** — [API & Dashboard — Domain Plan](domains/api-dashboard-domain-plan.md):
  the stable application/mission-data API surface (#645) and the dashboard/UX consumers
  (#650), including retiring the Feature-labelled UI drift.

All four throughlines are catalogued one hop away in the
[domains catalog](domains/index.md). Naming convention for throughlines:
`<domain>-domain-plan.md`, filed under `domains/`.

## Portfolio & milestone planning

Release-scoped strategy for the current cycle. These follow the distil-then-retire
lifecycle and each links up to the domain throughline it serves.

- [4.0.0 Milestone Roadmap](4-0-0-milestone-roadmap.md) — **the active cycle.** The
  operator-facing execution roadmap for milestone 4.0.0 (rc-stage): the four goal themes
  (stability, maturity, extensibility, Team Kitty enablers), the epic dependency spine,
  per-theme progress, exit criteria, and watch items. Its declaration of intent is
  [`4.0.0.md`](../changelog/4.0.0.md).
- [3.2.x Executive Overview](3-2-x-executive-overview.md) — PO / C-suite synthesis:
  goals and progress since 3.2.4, framed as business outcomes; the top-level
  stakeholder entry point.
- [3.2.x Open-Core Delivery Plan](3-2-x-open-core-delivery-plan.md) — PO-facing status
  re-read and the open-core breaking-change delivery strategy (charter-as-sole-door,
  built-in→module extraction). Supersedes the roadmap's "G2-is-the-blocking-spine"
  framing where they disagree.
- [3.2.x Delivery Approach](3-2-x-approach.md) — cross-mission sequencing intent,
  stress-tested by a two-round dialectic squad. Doctrine-first confirmed.
- [3.2.x Milestone Roadmap](3-2-x-milestone-roadmap.md) — the prior-cycle execution roadmap;
  re-anchored on 2026-09-14 to hand active-cycle authority to the
  [4.0.0 roadmap](4-0-0-milestone-roadmap.md) above. The durable declarations of intent it
  executes live in [release goals](../changelog/release-goals.md).

## Working collections (by area)

Subdirectories of the distil-then-retire surface, each with its own `index.md`
cataloguing its contents. Roughly ordered by current activity:

- **[Doctrine](doctrine/index.md)** — doctrine layering, charter boundary, and
  artifact-selection planning.
- **[Refactor](refactor/index.md)** — degod/unshim program and slice-landing planning.
- **[Code quality](code-quality/index.md)** — the SonarCloud baseline, quality-metric
  evolution, the smell/vulnerability cluster taxonomy, and targeted cleanup scoping.
- **[Testing](testing/index.md)** — mutation testing, acceleration, friction audit,
  and CI gate tuning.
- **[Investigations](investigations/index.md)** — scope assessments, compatibility
  matrices, and RFC/endpoint research.
- **[Engineering notes](engineering-notes/index.md)** — the live remainder: architecture
  audits & reviews, mission notes, DRG/doctrine analyses, and maintenance/field-report
  briefs. (The runtime/state-overhaul, surface-resolution-cluster, and triage-log
  sub-clusters have been distilled and retired to `deprecated`; they remain on disk as
  archived provenance only.)
- **[Initiatives](initiatives/index.md)** — active architecture initiatives.
- **[User journeys](user_journey/index.md)** — end-to-end user-journey docs.
- **[Research](research/index.md)** — research deliverables (era spikes/explorations).
- **[Next-mission mappings](next-mission-mappings/index.md)** — mapping notes for the
  mission-next compatibility surface.

Retired collections (distilled and closed out; their `index.md` is `deprecated`, kept
on disk as archived provenance, not a live working surface): the **Reviews** collection
(PR review resolution plans, test plans, execution reports) and the **3.2 doc
publication** collection (IA, navigation, and the 3.2 publication checklist).
