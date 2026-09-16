---
title: 'API & Dashboard — Domain Plan'
description: 'Durable domain plan for the application/mission-data API surface (#645) and dashboard/UX (#650): stable data API, dashboard consumers, retiring the Feature-labelled UI drift.'
doc_status: durable
updated: '2026-09-06'
related:
- docs/plans/index.md
- docs/plans/3-2-x-open-core-delivery-plan.md
- docs/plans/domains/doctrine-charter-domain-plan.md
- docs/plans/domains/packs-extraction-domain-plan.md
- docs/architecture/status-model.md
---

# API & Dashboard — Domain Plan

**Audience:** the project maintainer — technical, time-pressed, wants signal over ritual.

> **Status: durable domain plan (throughline).** Unlike the release-scoped
> `docs/plans/` working notes that follow the distil-then-retire lifecycle, this
> document is one of the **standing domain throughlines** meant to persist across
> releases. It is the index and the "why" for the **application/mission-data API and
> the dashboard/UX** surface; the release milestones and epics it references are the
> "what ships when." Where a release plan and this plan disagree on *scope of the
> domain*, this plan is the canonical map; where they disagree on *what ships in a given
> tag*, the milestone roadmap and the owning epic win. Keep this plan factual and
> current; do not let it accrete release-scoped tracking that belongs in an epic.

---

## 1. Purpose & scope

**Purpose.** Give the **application/mission-data API and the dashboard** a single durable
home that states the *invariants* the surface must hold, groups the domain's lasting
sub-areas, and points at the epics and design records that carry the work. Before this
plan, this surface had no standalone throughline — the [plans index](../index.md) listed
"API & dashboard" only as a *planned* domain plan. This plan makes the throughline
explicit and becomes the domain's index. It is a sibling to the [Doctrine & Charter
Domain Plan](doctrine-charter-domain-plan.md), the [Packs Extraction Domain
Plan](packs-extraction-domain-plan.md), and (until its 2026-09-06 retirement,
Convergence #3881) the SaaS & Hosted Sync domain plan.

**In scope — the application surface.** "API & dashboard" here means the data surface the
project's own consumers read mission state from, and the UX that renders it:

- **The application / mission-data API (#645, Epic: Stable Application API Surface)** —
  the stable, versioned surface that exposes mission and work-package state (the status
  projection reduced from `status.events.jsonl` — see [status-model](../../architecture/status-model.md))
  to the dashboard and any external application consumer, so consumers bind to a
  documented data contract, not to internal reducers or on-disk file shapes.
- **The dashboard / UX (#650)** — the mission dashboard that renders that data: the
  WP-lane board, the mission and work-package views, and the localhost daemon surface.
- **Terminology fidelity in the UI (#650)** — the dashboard renders the **Mission** canon
  end to end; the historical `Feature`-labelled UI drift is retired (see §3.3). This is a
  drift-elimination goal, not new vocabulary.

**Explicit boundary / non-goal (FR-004) — the two things called "API".**

> **This plan owns the application/mission-data API + dashboard. It is NOT the doctrine &
> charter *Python import surface*.** There are two distinct surfaces the corpus calls an
> "API," and conflating them is the load-bearing miscategorisation this boundary exists to
> prevent:
>
> 1. **The application/mission-data API — THIS plan (#645).** The *data* surface: mission
>    and WP state, the reduced status projection, consumed by the dashboard and external
>    application consumers over a documented data contract.
> 2. **The doctrine & charter public import surface — [Doctrine & Charter Domain Plan
>    §3.6](doctrine-charter-domain-plan.md) ("Stable public API surface for doctrine &
>    charter"), design-spike #3179.** A *different* API: the **Python import / single-
>    entry-point** surface for the doctrine modules — the `runtime → charter → doctrine`
>    layering where the runtime reaches doctrine *through* the charter proxy, never
>    directly (`doctrine/__init__.py` declares 3 public names while ~79 files reach past it
>    across ~30 submodule paths, with no architectural test pinning the public surface).
>    That is a code-import boundary enforced by a layer test — **not** a data API consumed
>    by a UI.
>
> **The shared-epic subtlety.** §3.6 records that #3179 **reconciles its epic home to
> #645** because it is a direct instance of #645's single-entry-point *pattern* (the
> #645/#460 service-extraction → typed-contract → architectural-test sequence). #645 is
> therefore a **shared epic with two facets**: (a) the **application/mission-data API
> surface + dashboard** slice — **this plan's** — and (b) the **doctrine-module Python
> import surface** slice — **§3.6's**. The seam: **the importable Python entry-point for
> the doctrine modules is §3.6's and is not restated here; the application data contract
> the dashboard consumes is this plan's and is not restated there.** Cross-reference §3.6
> when a change touches both — do not duplicate it.

**Why a durable domain plan and not a release plan.** The surface is governed by standing
invariants — an application consumer binds to a documented, versioned data contract, never
to internal reducers or file shapes; the dashboard never asserts UI behaviour it cannot
prove (frontend can fail silently); and the UI speaks the Mission canon, never re-drifting
to a `Feature` label. Those invariants outlive any one tag; the experience-shaped delivery
(deferred to 3.3.x, see §5) churns beneath them.

---

## 2. Where API/dashboard planning lives today (honest inventory)

There has been **no standalone API/dashboard throughline** before this document. The
surface was distributed across three surfaces:

1. **The [plans index](../index.md)** — lists "API & dashboard" only as a *planned* domain
   plan; a placeholder, not a map.
2. **[Status model architecture](../../architecture/status-model.md)** — the append-only
   `status.events.jsonl` event log and its `reduce()` projection that any mission-data API
   must expose. It is the data source of record, not an API/dashboard plan.
3. **The epics themselves** — **#645** (Epic: Stable Application API Surface) and **#650**
   (dashboard/UX, including the `Feature`-label drift retirement). Issue-tracker groupings
   with scope bullets, **not written plans.** Experience-shaped delivery is deferred to
   3.3.x by the [milestone roadmap](../3-2-x-milestone-roadmap.md) ("everything
   experience-shaped — UX, dashboard, SaaS tie-in — is deliberately deferred to 3.3.x").

**This plan now becomes the domain's index.** It ties #645 and #650 together under one set
of invariants and surfaces the gaps they leave open (§4), and it draws the boundary with
the doctrine-charter public-import surface (§1, §3.6-cross-ref) that shares the word "API"
and, now, the #645 epic home.

---

## 3. Standing concerns — the durable spine

The domain divides into three lasting sub-areas. Each states the **invariant** it must
hold (the durable "why"), then lists the **currently open work** (the release-scoped
"what," which turns over across versions).

### 3.1 The application/mission-data API contract

**Invariant.** External application consumers and the dashboard bind to **one documented,
versioned data contract** for mission and work-package state — never to internal reducers,
event-log internals, or on-disk file shapes. The contract exposes the reduced status
projection as its stable surface; internal churn behind it is not externally visible.

**Design of record.** Epic **#645** (Stable Application API Surface), whose
service-extraction → typed-contract → architectural-test single-entry-point pattern
(the #645/#460 precedent) is the shape of the contract; the
[status model](../../architecture/status-model.md) `reduce()` projection as the data
source the contract exposes.

**Open work.** Enumerate and version the mission-data contract (the #645 application-data
facet — *distinct from* the #3179 doctrine-import facet §3.6 owns), then pin it with a
contract test so a consumer can rely on it across versions.

### 3.2 The dashboard / UX surface

**Invariant.** The dashboard renders mission and WP state truthfully and **never asserts a
UI behaviour it cannot prove** — a frontend can fail silently (a caught 404 shows a
fallback), so dashboard behaviour is verified by a browser-level regression, not inferred
from an API response. The localhost daemon surface stays loopback-only.

**Design of record.** Epic **#650** (dashboard/UX); the browser-level UI regression
discipline recorded in the repository guidelines (the WP-modal Playwright guard is the
standing example — API responses do not prove the UI works).

**Open work.** The experience-shaped dashboard delivery deferred to 3.3.x (§5): the
WP-lane board, mission/WP views, and their browser-verified regressions.

### 3.3 Terminology fidelity in the UI (retiring the `Feature` drift)

**Invariant.** The dashboard speaks the **Mission** canon end to end. The historical
`Feature`-labelled UI drift — a legacy label that leaked into the dashboard against the
Terminology Canon — is **retired**, and the UI never re-introduces a `Feature` label for
a Mission-domain object.

**Design of record.** Epic **#650** carries this as an explicit goal: kill the legacy
`Feature`-labelled UI drift in favour of the Mission canon. The Terminology Canon (Mission,
never "feature") is the standard the retirement restores; here it is a
**reviewer-verified** fidelity concern, since the terminology guard does not scan the UI
label surface.

**Open work.** Complete the #650 label-retirement sweep so no dashboard view renders the
legacy `Feature` label, and keep it retired as the dashboard delivery lands in 3.3.x.

---

## 4. Known gaps

1. **The #645 two-facet split is unreconciled in the tracker.** #645 now hosts both the
   application-data API facet (this plan, §3.1) and the doctrine-module import surface
   facet (doctrine-charter §3.6, #3179 reparented under #645). Without a facet split in the
   epic, a PO cannot tell which slice is the data contract and which is the Python import
   surface. §1's boundary statement is the reconciling map; the tracker should mirror it.
2. **The mission-data contract is unenumerated.** The §3.1 invariant asserts a versioned
   data contract, but no contract or contract test exists yet — the dashboard binds to the
   projection directly today. This is the domain's key structural gap, gated behind #645.
3. **Dashboard delivery is deferred, its invariants are not.** The experience-shaped
   delivery is a 3.3.x concern (§5), but the invariants (contract-bound consumers,
   browser-proven UI, Mission-canon labels) are in force now and must not regress as the
   surface is built.

---

## 5. Release-scoped view (the "what ships when")

This plan tracks the **why** (the API/dashboard invariants and sub-areas); the epics track
the **what-ships-when**. The table below is a snapshot for orientation, not a schedule.
Verify live state via `gh issue view <n> --repo spec-kitty/spec-kitty` before acting.

| Work | Sub-area (§3) | Owning epic | Milestone |
|---|---|---|---|
| Enumerate + version the mission-data API contract | Data API contract (3.1) | #645 (application-data facet) | 3.3.x (experience-shaped) |
| Dashboard WP-lane board + mission/WP views | Dashboard/UX (3.2) | #650 | 3.3.x |
| Retire the legacy `Feature`-labelled UI drift | Terminology fidelity (3.3) | #650 | 3.3.x |

*Read the WHY in §3; the epic tracks the WHAT-ships-when. The `Feature`-label row is the
drift being killed — not a live UI label.*

---

## 6. Cross-references

**Sibling domain throughlines (the durable spine of `docs/plans/`):**

- **Doctrine & charter** — [Doctrine & Charter Domain Plan](doctrine-charter-domain-plan.md).
  Its **§3.6 (Stable public API surface for doctrine & charter)** is the **non-goal
  boundary** for this plan (§1): §3.6 owns the doctrine/charter **Python import / single-
  entry-point** surface (#3179), a *different* API from this plan's **application/mission-
  data** surface — even though #3179 now shares the #645 epic home as a separate facet.
  *(At this plan's commit the doctrine-charter plan still lives at
  `docs/plans/doctrine-charter-domain-plan.md`; the domains/ migration WP moves it and
  repoints these links.)*
- **Packs extraction** — [Packs Extraction Domain Plan](packs-extraction-domain-plan.md).
- **SaaS & hosted sync** — domain plan retired 2026-09-06 (Convergence #3881). The former
  in-process sync projection no longer exists: hosted/team rendering is server-side in the
  authoritative upstream repos, and this repo's dashboard data surface is consumed locally,
  with hosted status delivered via `zeitgeist_client` (ephemeral by design). See the
  convergence-retirement ADR.

**Design of record:**

- [Status model architecture](../../architecture/status-model.md) — the
  `status.events.jsonl` event log and `reduce()` projection the mission-data API exposes.
- [3.2.x milestone roadmap](../3-2-x-milestone-roadmap.md) — records the deferral of
  experience-shaped (UX/dashboard) work to 3.3.x.

**Epics:** #645 (Stable Application API Surface — application-data facet here; the #3179
doctrine-import facet is doctrine-charter §3.6), #650 (dashboard/UX + `Feature`-drift
retirement).

**Plans index:** [docs/plans/index.md](../index.md).
