---
title: Plans
description: 'Plans landing page: durable domain throughlines plus the distil-then-retire working surface of investigations, research, initiatives, and release-scoped plans.'
doc_status: active
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
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

- **Team Kitty / hosted collaboration** — retired here; owned upstream. The former "SaaS &
  hosted sync" domain plan was retired on 2026-09-06 when the Convergence (#3881) removed the
  local sync transport. The hosted surface (Team Kitty over Zeitgeist) is authored in the
  upstream `spec-kitty/zeitgeist` and `spec-kitty/saas` repos, and this repo consumes their
  clients. See [Team Kitty context](../context/team-kitty.md) and the
  [convergence-retirement ADR](../adr/3.x/2026-09-06-1-convergence-retirement-and-client-repo-inversion.md).
- **Doctrine & charter** — [Doctrine & Charter — Domain Plan](domains/doctrine-charter-domain-plan.md):
  charter lifecycle & sole-door access, pack extensibility, activation-driven
  availability, meta.json fail-closed reads, the public API surface, and
  glossary-as-doctrine. Its release-scoped companion is the
  [4.0.0 Milestone Roadmap](4-0-0-milestone-roadmap.md) (the
  [3.2.x Open-Core Delivery Plan](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/3-2-x-open-core-delivery-plan.md) is the prior-cycle
  record); its program-scoped companions are the
  [Glossary Doctrine Overhaul — Program Plan](glossary-doctrine-overhaul-program.md) and the
  [Charter-Resolution Program](charter-resolution/README.md).
- **Packs extraction** — [Packs Extraction — Domain Plan](domains/packs-extraction-domain-plan.md):
  re-extracting the doctrine layer from `src/charter/offering/` and `packs/built-in/`
  into separately released units: the wheel split (#3101), open-packs re-vendoring
  (#3504) and verified distribution (#2539). None of it is 4.0.0 scope.
- **API & dashboard** — [API & Dashboard — Domain Plan](domains/api-dashboard-domain-plan.md):
  the stable application/mission-data API surface (#645) and the dashboard/UX consumers
  (#650), including retiring the Feature-labelled UI drift.

The three live throughlines (and the retired one) are catalogued one hop away in the
[domains catalog](domains/index.md). Naming convention for throughlines:
`<domain>-domain-plan.md`, filed under `domains/`.

## Portfolio & milestone planning

Release-scoped plans follow the distil-then-retire lifecycle and each links up to the
domain throughline it serves.

### Active cycle (4.x)

- [4.0.0 Milestone Roadmap](4-0-0-milestone-roadmap.md) — the operator-facing execution
  roadmap for 4.0.0 (rc-stage): the four goal themes (stability, maturity, extensibility,
  Team Kitty enablers), the epic dependency spine, per-theme progress, exit criteria, and
  watch items. Its declaration of intent is [`4.0.0.md`](../changelog/4.0.0.md). There is no
  4.x stakeholder (PO / C-suite) overview yet.

### Prior cycle (3.2.x) — historical

Kept as a record of the 3.2.x line, which closed with 3.2.7 (2026-09-10). Do not act on
their next steps; the 4.0.0 roadmap is the plan of record.

- [3.2.x Milestone Roadmap](3-2-x-milestone-roadmap.md) — *superseded.* The prior-cycle
  execution roadmap; re-anchored on 2026-09-14 to hand authority to the 4.0.0 roadmap.
  The durable declarations of intent it executed live in
  [release goals](../changelog/release-goals.md).
- [3.2.x Executive Overview](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/3-2-x-executive-overview.md) — *superseded.* PO / C-suite
  synthesis of 3.2.x goals and progress since 3.2.4, framed as business outcomes.
- [3.2.x Open-Core Delivery Plan](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/3-2-x-open-core-delivery-plan.md) — *superseded.*
  PO-facing status re-read and the open-core breaking-change delivery strategy
  (charter-as-sole-door, built-in→module extraction).
- [3.2.x Delivery Approach](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/3-2-x-approach.md) — *superseded.* Cross-mission sequencing
  intent, stress-tested by a two-round dialectic squad.

## Programmes and status notes

Standalone plans and status notes that sit at the top of `plans/` or in their own folder:

- [Glossary Doctrine Overhaul — Program Plan](glossary-doctrine-overhaul-program.md) —
  *draft.* Promote the glossary to a first-order doctrine artefact; see its status line for
  which missions landed.
- [Charter-Resolution Program](charter-resolution/README.md) — *parked.* Mission map (M1–M6)
  for org/project doctrine that loads healthy but reaches no consumer.
- [zeitgeist_client WP01 — remaining scope](zeitgeist-client-wp01-remaining.md) — status
  note for the bundled Zeitgeist client; error messages in
  `src/specify_cli/zeitgeist_client/transport.py` point here.
- [Agent moment delivery policy](agent-moment-delivery-4216.md) — how agents receive Team
  Kitty moments (#4216). Describes shipped behaviour; a candidate to move to
  `docs/architecture/`.

## Working collections (by area)

Subdirectories of the distil-then-retire surface. These are working notes, not plans of
record: each folder's own `index.md` says what in it is live and what is retired.

- **[Doctrine](doctrine/index.md)** — doctrine layering, charter boundary, and
  artifact-selection planning. The [Charter-Resolution Program](charter-resolution/README.md)
  is a sibling folder in the same area.
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
- **[User journeys](user_journey/index.md)** — the 2.x-era vision journeys (historical) plus
  the live init/doctrine flow walkthrough.
- **[Research](research/index.md)** — research deliverables (era spikes/explorations).

Retired collections (distilled and closed out; their `index.md` is `deprecated`, kept
on disk as archived provenance, not a live working surface): the **Reviews** collection
(PR review resolution plans, test plans, execution reports), the **3.2 doc
publication** collection (IA, navigation, and the 3.2 publication checklist), the
**[Initiatives](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/initiatives/index.md)** collection (2.x-era architecture initiatives, retired
2026-09-30), the **[Refactor](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/refactor/index.md)** collection (the degod/unshim
programme, executed; retired 2026-09-30), and the
**[Next-mission mappings](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/next-mission-mappings/index.md)** collection (both mapped gaps are
now hard regression tests; retired 2026-09-30).
