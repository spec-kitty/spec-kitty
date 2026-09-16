---
title: 'Packs Extraction — Domain Plan'
description: 'Durable domain plan for physically extracting the doctrine layer into the standalone spec-kitty-doctrine module: boundary, import-cycle break, strangler cutover, repo split.'
doc_status: durable
updated: '2026-08-12'
related:
- docs/plans/index.md
- docs/plans/3-2-x-open-core-delivery-plan.md
- docs/plans/domains/doctrine-charter-domain-plan.md
- docs/plans/domains/api-dashboard-domain-plan.md
- docs/adr/3.x/2026-08-02-1-charter-wheel-assessment.md
- docs/adr/3.x/2026-05-16-1-doctrine-layer-merge-semantics.md
---

# Packs Extraction — Domain Plan

**Audience:** the project maintainer — technical, time-pressed, wants signal over ritual.

> **Status: durable domain plan (throughline).** Unlike the release-scoped
> `docs/plans/` working notes that follow the distil-then-retire lifecycle, this
> document is one of the **standing domain throughlines** meant to persist across
> releases. It is the index and the "why" for the **physical extraction** of the
> doctrine layer into a standalone module and, later, a standalone repo; the release
> milestones and epics it references are the "what ships when." Where a release plan
> and this plan disagree on *scope of the domain*, this plan is the canonical map;
> where they disagree on *what ships in a given tag*, the milestone roadmap and the
> owning epic win. Keep this plan factual and current; do not let it accrete
> release-scoped tracking that belongs in an epic.

---

## 1. Purpose & scope

**Purpose.** Give the **physical code extraction / modularization** of the doctrine
layer a single durable home that states the *invariants* the split must hold, groups
the domain's lasting sub-areas, and points at the epics, ADRs, and the open-core plan
that carry the design and the tracking. Before this plan, the extraction lineage was
carried implicitly inside the release-window [3.2.x Open-Core Delivery Plan](../3-2-x-open-core-delivery-plan.md)
(its §2.2 item 3 and §2.3) and the wheel-assessment ADR (see §2). This plan makes the
throughline explicit and becomes the domain's index. It is a sibling domain throughline
to the [Doctrine & Charter Domain Plan](doctrine-charter-domain-plan.md) and (until its
2026-09-06 retirement, Convergence #3881) the SaaS & Hosted Sync domain plan.

**In scope — the physical split.** "Packs extraction" here means the movement of code
and packaged doctrine content across a module (and eventually a repo) boundary:

- **The standalone `spec-kitty-doctrine` module boundary** — `src/doctrine/pyproject.toml`
  already declares a standalone `spec-kitty-doctrine` v1.0.0 distribution with kernel-only
  dependencies, guarded by a layer test. Keeping that boundary buildable and importable
  as its own unit is this domain's core artefact.
- **The charter↔doctrine import-cycle break** — the one structural blocker to a clean
  lift: the misfiled charter-reaching imports inside the doctrine package
  (`agent_profiles/repository.py`) that make `spec-kitty-doctrine` non-standalone until
  they are inverted or relocated.
- **In-place strangler cutover** — the move → shim → repoint → delete rhythm on `main`
  (never a long-lived divergent branch), so the P0 fix stream is never stalled by the
  restructure.
- **The `kernel → doctrine → charter` wheel split** and the **built-in pack physical
  packaging** — how the built-in packs are packaged and distributed as a unit.
- **Repo-split transparency** — the later move to a separate repository must be a
  non-event for consumers *because they already consume across the module boundary*.

**Explicit boundary / non-goal (FR-003).**

> **This plan is the PHYSICAL code extraction / modularization lineage. It is NOT the
> pack *authoring / governance* model.** The doctrine/charter *pack ecosystem* — pack
> tiers (`built-in → org → project`), DRG merge semantics (`enhances` = field-merge,
> `overrides` = full replacement, `specializes_from` lineage), owner-declared
> `component-type` immutability, and the author-able first-class kinds (assets,
> shortcodes, mission types) — is owned by the **[Doctrine & Charter Domain Plan
> §3.2](doctrine-charter-domain-plan.md) ("Doctrine/charter extensibility & the pack
> ecosystem")**. That section governs *how a customer authors and layers packs and what
> a lower-tier pack may not silently mutate*; **this** plan governs *where the doctrine
> code physically lives and how it is packaged and shipped as a module/repo*. They share
> the word "packs" and the epics #2466 / #2216 (each of which has both a governance facet
> and a physical-packaging facet), so the seam is explicit: **DRG merge / tier
> immutability / `enhances`/`overrides` authoring semantics are §3.2's and are not
> restated here; the module boundary, the import-cycle break, and the wheel/repo split
> are this plan's and are not restated there.** When the two must be read together (a
> packaging change that alters an authoring guarantee), cross-reference — do not
> duplicate.

**Why a durable domain plan and not a release plan.** The extraction is governed by
standing invariants — the doctrine layer must remain buildable as its own unit with
kernel-only dependencies; no charter→doctrine reach may re-introduce the import cycle;
every cutover step ships behind a deprecation shim so a consumer's break is auto-migrated,
not stranded; and a future repo split is transparent because the consumer already binds
across the boundary. Those invariants outlive any one tag. Release plans churn as
milestones close; the invariants do not.

---

## 2. Where extraction planning lives today (honest inventory)

There has been **no standalone extraction throughline** before this document. The
lineage was distributed across three surfaces:

1. **[3.2.x Open-Core Delivery Plan §2.2–2.3](../3-2-x-open-core-delivery-plan.md)** — the
   release-window home. §2.2 item 3 ("built-in artefacts extracted from `src/` into a
   root-level module") records the verified state: *~90% done structurally —
   `src/doctrine/pyproject.toml` already declares a standalone `spec-kitty-doctrine`
   v1.0.0 with kernel-only deps, guarded by a layer test; the one blocker is a
   charter↔doctrine import cycle (two misfiled function-local imports in
   `agent_profiles/repository.py`); resolve it and the lift mirrors the
   runtime/events/tracker cutover already done.* §2.3 mandates the **in-place strangler**
   discipline (move → shim → repoint → delete on `main`, never a long-lived branch) and
   the "engineered, not scheduled" auto-migrate + deprecation-shim posture. This is a
   release-window framing, not a durable domain map.
2. **ADR [2026-08-02-1 charter-wheel-assessment](../../adr/3.x/2026-08-02-1-charter-wheel-assessment.md)**
   — the `kernel → doctrine → charter` wheel split design of record (#3101).
3. **The epics themselves** — #3101 (wheel split), #3091 / #3022 (built-in pack
   extraction), and the physical-packaging facet of #2466 / #2216 / #2539. These are
   issue-tracker groupings with scope bullets, **not written plans.**

**This plan now becomes the domain's index.** It does not replace the open-core plan or
the wheel ADR — it ties them together under one set of extraction invariants and
surfaces the gaps they leave open (§4). The [Doctrine & Charter Domain Plan §1](doctrine-charter-domain-plan.md)
already names this plan as the owner of the wheel/packaging cutover (#3101, #3091/#3022)
and cross-references here rather than owning it — this plan is the other half of that seam.

---

## 3. Standing concerns — the durable spine

The domain divides into three lasting sub-areas. Each states the **invariant** it must
hold (the durable "why"), then lists the **currently open work** grouped beneath it (the
release-scoped "what," which turns over across versions).

### 3.1 The module boundary & the import-cycle break

**Invariant.** `spec-kitty-doctrine` builds and imports as a standalone distribution with
**kernel-only dependencies** — no doctrine module reaches "up" into charter. The layer
test that guards `src/doctrine/pyproject.toml` stays green; the charter↔doctrine import
cycle stays broken (dependency inversion, not a function-local import papering over it).

**Design of record.** Open-core plan §2.2 item 3 (the verified ~90%-done structural state
and the named import-cycle blocker in `agent_profiles/repository.py`); the module's own
`src/doctrine/pyproject.toml` (`spec-kitty-doctrine` v1.0.0, kernel-only deps).

**Open work.** Resolve the charter↔doctrine import cycle so the lift can complete; keep
the layer-boundary test as the standing regression guard.

### 3.2 In-place strangler cutover

**Invariant.** The boundary is drawn **in place on `main`** via small strangler steps
(move → shim → repoint → delete), never a long-lived branch that diverges from the P0
stream. Every consumer-visible break rides the migration rail (`spec-kitty migrate …`)
and lands behind a deprecation shim that names its replacement and removal version, so a
break is *auto-migrated and shimmed*, not stranded.

**Design of record.** Open-core plan §2.3 (dual-track, no hard freeze) and §2.4 (the
"minimal-hurt" machinery: migration rail, deprecation shims, versioned contract, batched
consumer-visible breaks). Mission `doctrine-built-in-seam-consolidation` (2026-08-02) is
the landed precedent — one fail-closed built-in doctrine location seam with the
`packs/built-in` relocation complete.

**Open work.** Continue the strangler steps for the residual doors the open-core plan §3
row 2 enumerates as sequenced under #3176 / #3091 / #3022 / #3101 (e.g.
`runtime/resolver.py`'s tier reimplementation, `runtime/home.py`'s importlib-resources
root path, and the missions-root duplicates), each as a move → shim → repoint → delete.

### 3.3 Wheel/repo-split packaging & transparency

**Invariant.** The built-in packs are packaged and distributed as a coherent unit along
the `kernel → doctrine → charter` layering, and the eventual move to a **separate repo is
transparent** for consumers — it changes the distribution's provenance, not the surface
they bind to, because they already consume across the module boundary.

**Design of record.** ADR [2026-08-02-1 charter-wheel-assessment](../../adr/3.x/2026-08-02-1-charter-wheel-assessment.md)
(#3101 wheel split); epics #3091 / #3022 (built-in pack extraction) and the
physical-packaging facet of #2466 / #2216, with **#2539 (verified distribution)**
deferred to 3.3.x as the distribution-integrity half of the split.

**Open work.** Land the wheel split (#3101), complete the built-in pack extraction
(#3091/#3022), and carry #2539 verified-distribution into 3.3.x so the repo split, when
it lands, ships with provenance guarantees rather than a bare code move.

---

## 4. Known gaps

1. **The import-cycle break is the single load-bearing blocker.** Until the
   charter-reaching imports in `agent_profiles/repository.py` are inverted, the
   standalone-module invariant (§3.1) is structurally reachable but not *proven* by a
   clean standalone build; everything downstream (wheel split, repo split) waits behind
   it. This is the one genuinely blocking item, not a scheduling nicety.
2. **Physical-packaging vs authoring-governance epic overlap is unreconciled in the
   tracker.** #2466 and #2216 carry both a §3.2-authoring facet and a §3.3-packaging
   facet under the same epic; without a facet split in the tracker, a PO reading the epic
   cannot tell which slice is this plan's and which is the doctrine-charter plan's. The
   boundary statement in §1 is the reconciling map; the tracker should mirror it.
3. **Repo-split transparency has no acceptance check yet.** The "transparent for
   consumers" invariant (§3.3) is asserted but not gated — there is no test that a
   consumer pinned to the module surface survives the repo move untouched. #2539
   verified-distribution is the nearest home for such a check.

---

## 5. Release-scoped view (the "what ships when")

This plan tracks the **why** (extraction invariants and sub-areas); the epics track the
**what-ships-when**. The table below is a snapshot for orientation, not a schedule. It
will turn over as milestones close. Verify live state via
`gh issue view <n> --repo spec-kitty/spec-kitty` before acting.

| Work | Sub-area (§3) | Owning epic | State |
|---|---|---|---|
| Built-in doctrine location seam / `packs/built-in` relocation | Strangler cutover (3.2) | — (mission `doctrine-built-in-seam-consolidation`) | **LANDED** (2026-08-02) |
| Charter↔doctrine import-cycle break | Module boundary (3.1) | #3091 / #3022 | Open — the blocker (§4.1) |
| Wheel split (`kernel → doctrine → charter`) | Wheel/repo split (3.3) | #3101 | Design of record (ADR 2026-08-02-1) |
| Built-in pack extraction | Wheel/repo split (3.3) | #3091 / #3022 | Sequenced |
| Verified distribution | Wheel/repo split (3.3) | #2539 | Deferred to 3.3.x |

*Read the WHY in §3; the epic tracks the WHAT-ships-when.*

---

## 6. Cross-references

**Sibling domain throughlines (the durable spine of `docs/plans/`):**

- **Doctrine & charter** — [Doctrine & Charter Domain Plan](doctrine-charter-domain-plan.md).
  Its **§3.2 (Doctrine/charter extensibility & the pack ecosystem)** is the **non-goal
  boundary** for this plan (§1): §3.2 owns the pack *authoring/governance* model (tiers,
  DRG merge, `enhances`/`overrides`, `component-type` immutability); this plan owns the
  *physical* module/repo split. *(At this plan's commit the doctrine-charter plan still
  lives at `docs/plans/doctrine-charter-domain-plan.md`; the domains/ migration WP moves
  it and repoints these links.)*
- **API & dashboard** — [API & Dashboard Domain Plan](api-dashboard-domain-plan.md), the
  application/mission-data API + dashboard throughline.
- **SaaS & hosted sync** — domain plan retired 2026-09-06 (Convergence #3881; surface re-homed upstream).

**Release & design of record:**

- [3.2.x Open-Core Delivery Plan §2.2–2.3](../3-2-x-open-core-delivery-plan.md) — the
  release-window extraction framing and the strangler/minimal-hurt discipline.
- ADR [2026-08-02-1 charter-wheel-assessment](../../adr/3.x/2026-08-02-1-charter-wheel-assessment.md) — the `kernel → doctrine → charter` wheel split (#3101).
- ADR [2026-05-16-1 doctrine-layer merge semantics](../../adr/3.x/2026-05-16-1-doctrine-layer-merge-semantics.md) — referenced for the §3.2 authoring seam this plan non-goals against (the merge semantics live there, not here).

**Epics:** #3101 (wheel split), #3091 / #3022 (built-in pack extraction), #2539 (verified
distribution, 3.3.x); physical-packaging facet of #2466 / #2216 (authoring facet is
doctrine-charter §3.2).

**Plans index:** [docs/plans/index.md](../index.md).
