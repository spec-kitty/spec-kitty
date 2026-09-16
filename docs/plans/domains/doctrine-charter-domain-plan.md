---
title: 'Doctrine & Charter — Domain Plan'
description: 'Durable, version-spanning plan for the doctrine/charter surface: charter lifecycle, sole-door access, extensibility, activation, fail-closed reads, public API, and glossary.'
doc_status: durable
updated: '2026-09-04'
related:
- docs/plans/index.md
- docs/plans/3-2-x-open-core-delivery-plan.md
- docs/plans/glossary-doctrine-overhaul-program.md
- docs/changelog/4.0.0.md
- docs/plans/doctrine/charter-sole-door-deferred-issues.md
- docs/plans/doctrine/index.md
- docs/adr/3.x/2026-05-16-1-doctrine-layer-merge-semantics.md
- docs/adr/3.x/2026-08-02-1-charter-wheel-assessment.md
---

# Doctrine & Charter — Domain Plan

**Audience:** the project maintainer — technical, time-pressed, wants signal over ritual.

> **Status: durable domain plan (throughline).** Unlike the release-scoped
> `docs/plans/` working notes that follow the distil-then-retire lifecycle, this
> document is one of the **standing domain throughlines** meant to persist across
> releases. It is the index and the "why" for the doctrine/charter governance
> surface; the release milestones and epics it references are the "what ships when."
> Where a release plan and this plan disagree on *scope of the domain*, this plan is
> the canonical map; where they disagree on *what ships in a given tag*, the milestone
> roadmap and the owning epic win. Keep this plan factual and current; do not let it
> accrete release-scoped tracking that belongs in an epic.

---

## Addendum 2026-09-04 — milestone re-key + resolved sub-areas (post-2026-08-23 reconciliation)

*This durable plan was last revised 2026-08-12, **11 days before** the 2026-08-23
release-queue reconciliation; its milestone labels (§3 open-issue lists and the §5 table)
predate it, and several sub-areas have since closed out. Per this plan's own status contract
— "where they disagree on *what ships in a given tag*, the milestone roadmap and the owning
epic win" — the labels and closed items are corrected here from live GitHub state (queried
2026-09-04, `GITHUB_TOKEN` unset). The **invariants and sub-areas (the durable "why") are
unchanged**; only the release-scoped "what ships when" moved. See the roadmap's
[2026-09-04 re-anchor](../3-2-x-milestone-roadmap.md#addendum-2026-09-04--milestone-taxonomy-re-anchor-the-delayed-action-r)
and the [4.0.0 declaration](../../changelog/4.0.0.md).*

**Taxonomy change.** The **3.3.x** milestone was **retired** (closed 2026-08-23) and
milestone #4 repurposed into **Product backlog**. Read every "3.3.x" label below as
**4.0.0** unless the issue is closed; the structural/extensibility epics that were implicitly
"3.2.x-cycle work" now sit in **Product backlog** — validated but on no committed release.

**Owning epic re-milestoned 3.2.x → 4.0.0:** **#2519** (charter authoring & lifecycle
robustness — §3.1 design-of-record and the §5 owning epic for the now-closed #3282). The
extensibility/spine epics **#2466 / #2467 / #2468 / #2216** (§3.2), **#2652** (§3.3),
**#645 / #3179** (§3.6), and **#2539** (deferred verified distribution) are all in **Product
backlog** — none is committed to 3.2.7 or 4.0.0; they need an explicit release-milestone
decision (see the roadmap addendum's disposition note).

**§3.5 (meta.json fail-closed read routing) is DONE — strike the whole sub-area's open list.**
Epic **#3259 is CLOSED**, and every child listed open — **#3230 / #3229 / #3228 / #3240** —
**CLOSED** (the children 2026-08-11). The §3.5 "Open issues" block and its four §5 table rows
are resolved; the invariant now holds as shipped state, not pending work.

**Other resolved-but-unstruck items (verified 2026-09-04):**

- **#3282 CLOSED** — the §3.1 load-bearing P0 (pointer-based charters lack mission-type
  activations on upgrade) shipped under **3.2.6**; the §5 table carries it as open 3.2.x.
- **#3176 CLOSED** — the §3.1 / §5 "last builder-unreachable site" P1 residual is discharged.
- **#3183 CLOSED** and **#2657 CLOSED** — §3.3 lists both as open (#3183 the
  activation-vs-loadability collision; #2657 the external blocker on #2659's provisioned
  default charter). #2652 and #3251 remain open (Product backlog).
- **#2262 CLOSED** — referenced under §3.4 of the SaaS plan; noted here for cross-consistency.

**Still-live gaps (unchanged by the reconciliation):** §4 gap 1 (doctrine content-QA has no
owning workstream — **#3275** still P3/no-milestone/no-epic) and §4 gap 4 (activation
reachability R1/R2, unspecced and blast-radius-bearing) remain the domain's largest
declared-vs-in-force gaps. Treat the §5 table's `Milestone` column as superseded by this
addendum until it is next revised in place.

---

## 1. Purpose & scope

**Purpose.** Give the doctrine/charter surface a single durable home that states the
*invariants* the surface must hold, groups the domain's lasting sub-areas, and points
at the epics, ADRs, and design notes that carry the design and the tracking. Before
this plan, doctrine/charter planning had no standalone throughline — it was implicit,
spread across the open-core delivery plan, the glossary overhaul program, and the
`docs/plans/doctrine/` design corpus (see §2). This plan makes the throughline
explicit and becomes the domain's index. It is the **second** domain throughline
(the SaaS & Hosted Sync domain plan — retired 2026-09-06, Convergence #3881 — was first).

**In scope — the governance substrate.** "Doctrine & charter" here means the
governance layer and the seam through which it reaches the runtime:

- **The charter** as the project's governance onboarding and the **single door** to
  provisioned assets — activation/deactivation, the plan/commit activation seam, the
  cascade over DRG `requires`/`suggests`/`refines` edges, and reconciliation between
  the activation ledgers.
- **The doctrine library** — the artefact kinds (directive, tactic, styleguide,
  toolguide, paradigm, procedure, agent_profile, mission_step_contract, glossary_pack),
  their DRG (doctrine reference graph), and the layered `built-in → org → project`
  resolution.
- **Doctrine/charter extensibility & the pack ecosystem** — org/project packs, pack
  dependencies, governance tiers, and the author-able surfaces customers extend.
- **Activation-driven availability** — deriving what mission types (and artefacts) are
  *available* from the charter activation set, not from filesystem position.
- **Doctrine content quality** — whether the shipped artefact *content* (not just its
  wiring) is scoped, non-duplicated, and operationalised as it claims.
- **meta.json fail-closed read routing** — the mission-identity/VCS-lock record read
  through the canonical fail-closed loader, since it is doctrine-adjacent canonical
  metadata that a corrupt read must never silently absorb.
- **The consumer-facing seam** — a stable public API/import surface for the doctrine &
  charter modules, and the `runtime → charter → doctrine` layering that keeps the
  runtime from reaching doctrine directly.
- **Glossary-as-doctrine** — promoting canonical terminology to a first-order,
  activatable `GLOSSARY_PACK` doctrine artefact with executable adherence gating.

**Explicit non-goals.**

- **Not the hosted product.** Sync, event-envelope integrity, consent/identity egress,
  CLI↔hosted auth, and rollout gating were a *different domain* — the
  SaaS & Hosted Sync domain plan (retired 2026-09-06, Convergence #3881; the surface
  re-homed upstream). This plan does not
  restate them. Charter *domain events* (`CharterCreated`/`CharterUpdated`, #2520) are
  named here where the charter lifecycle emits them, but the hosted consumer of those
  events belongs to the SaaS domain. (Note the inverse miscategorisation the SaaS plan
  flags: the open-core plan's "SaaS" label is the open-core split of *this* doctrine
  layer, not the hosted product.)
- **Not the wheel/packaging cutover as a build task.** The `kernel → doctrine → charter`
  wheel split (#3101, ADR 2026-08-02-1) and the built-in pack extraction (#3091/#3022)
  are a *packs-extraction* concern — a planned sibling throughline. This plan owns the
  charter/doctrine *access boundary and public surface* those cutovers depend on, and
  cross-references the packaging track rather than owning it.
- **Not release scheduling.** Which fix ships in 3.2.6 vs 3.3.x is the milestone
  roadmap's and the epic's job (§5).

**Why a durable domain plan and not a release plan.** Doctrine/charter is a standing
set of invariants (the charter is the sole door to assets; activation means an agent
actually receives the artefact; availability derives from activation, not from disk;
a lower-tier pack cannot silently mutate a higher tier's governed artefact; canonical
metadata fails closed). Those invariants outlive any one tag. Release plans churn as
milestones close; the invariants and their sub-areas do not. The issue tracker is
already unwieldy, so the throughline deliberately holds the *durable spine* and
cross-references the release-scoped docs rather than duplicating their tables.

---

## 2. Where doctrine/charter planning lives today (honest inventory)

There has been **no standalone doctrine/charter throughline** before this document.
The planning was distributed across four surfaces, none of which is the domain's index:

1. **[3.2.x Open-Core Delivery Plan](../3-2-x-open-core-delivery-plan.md)** — the closest
   thing to a doctrine/charter strategy, but framed as a *release-window* delivery plan,
   not a durable domain map. Its organizing principle is the "last permitted
   breaking-change window" for the doctrine/charter seam: charter-as-sole-door (its §1.1
   / §2.2 done-bar), the built-in → module extraction (§2.2 item 3), and the
   Creed/Values schema build (§3 item 4). It carries the *what-ships-in-3.2.x* framing;
   it does not hold the domain's standing invariants across versions.
2. **[Glossary Doctrine Overhaul — Program Plan](../glossary-doctrine-overhaul-program.md)**
   — a four-mission program promoting the glossary to a first-order `GLOSSARY_PACK`
   doctrine kind and building the executable ASSET-kind gate. A program plan scoped to
   one sub-area, not the domain.
3. **[`docs/plans/doctrine/`](../doctrine/index.md)** — the design/review corpus: the
   charter-activation-vs-reachability assessment, the `runtime → charter → doctrine`
   boundary audit, the charter-as-central-path-resolver gap analysis, the layered
   resolution design, the doctrine-inclusion assessment, the FoundationalValues/Creed
   AUTHORITY docs, and the next-doctrine-slice research (wheel / mission-type
   relocation / public API). Rich, tiered (AUTHORITY / RECORD / EVIDENCE), but a
   collection of investigations, not a single throughline.
4. **The epics themselves** — #2519 (charter authoring & lifecycle), #2466
   (doctrine/charter extensibility & pack ecosystem), #2652 (specify_cli/missions
   retirement / activation-driven availability), #1799 (charter/doctrine governance
   config & docs), #2216 (governance tiers), #3259 (meta.json fail-closed routing),
   and #645 (stable application API surface). These are issue-tracker groupings with
   scope bullets — **not written plans**.

**This plan now becomes the domain's index.** It does not replace the open-core plan,
the glossary program, the design corpus, or the epics — it ties them together under one
set of invariants and surfaces the gaps they collectively leave open (§4). Verify live
issue/epic state with `gh issue view <n> --repo spec-kitty/spec-kitty` before acting.

---

## 3. Standing concerns — the durable spine

The domain divides into seven lasting sub-areas. Each states the **invariant** it must
hold (the durable "why"), then lists the **currently open issues** grouped beneath it
(the release-scoped "what," which will turn over across versions).

### 3.1 Charter authoring, activation & lifecycle

**Invariant.** The charter is the **sole door** to provisioned doctrine assets: any
path that reaches an asset around the charter is a second seam that leaks internals.
The two activation ledgers (`config.yaml activated_*` and `answers.yaml selected_*`,
projecting into `references.yaml`/`graph.yaml`) are **reconciled by construction** — an
artefact is never activated-yet-dangling — and **"activated" means an agent actually
receives the artefact** at the action-context boundary, not merely that it is a member
of a filter list. Charter lifecycle transitions emit their domain events on the unified
activation seam.

**Design of record.** Epic **#2519** (charter authoring & lifecycle hardening — the
disjoint-ledgers root defect, deterministic intake, `charter author` scaffold, charter
domain events); the sole-door done-bar in the
[Open-Core Delivery Plan §1.1/§2.2](../3-2-x-open-core-delivery-plan.md); ADR
[2026-05-16-1 doctrine-layer merge semantics](../../adr/3.x/2026-05-16-1-doctrine-layer-merge-semantics.md)
(plan/commit activation seam, cascade over DRG edges). The reasoning trail lives in two
now-archived design notes (both `doc_status: deprecated`, cited here as historical
provenance) — [charter-activation-reachability-assessment](../doctrine/charter-activation-reachability-assessment.md)
(the V1/V2/V3 activation-vocabulary split; 185 activated artefacts, zero surfaced at the
action boundary) and [runtime-charter-doctrine-boundary](../doctrine/runtime-charter-doctrine-boundary.md)
(the `runtime → charter → doctrine` layering ratchet); their findings are distilled into
this plan's invariants and §4 gaps.

**Open issues.**

- **#3282 (P0, 3.2.x, → #2519)** — upgrade leaves pointer-based charters without
  mission-type activations on 3.2.6. A direct lifecycle/reconciliation failure: the
  activation state a charter should carry after upgrade is not derived. The load-bearing
  P0 of this sub-area.
- **#3176 (P1, 3.2.x, → #2466)** — `build_activation_aware_doctrine_service` cannot
  reach `.kittify/agent_profiles`, blocking `projection.py`'s FR-001 migration onto the
  unified builder. The last named, composite-key-excluded call site keeping the
  sole-door from being one builder / one entry point (see the Open-Core §1.1 residual).
- **#3261 (P3, Task, → #2519)** — `charter context --include` silently mishandles
  multi-selector input (comma errors; repeated flags drop all but the last) while the
  help text implies comma-separation. A usability defect on the on-demand fetch path
  that is the one activation vector that *does* surface artefacts today.

> **Standing sub-thread — activation reachability (unspecced, durable).** The
> [reachability assessment](../doctrine/charter-activation-reachability-assessment.md)'s (now archived) R1
> ("make activation an entry vector into action context") and R2 ("collapse the three
> activation vocabularies to one") are the difference between a doctrine layer that is
> *declared* and one that is *in force*. They are blast-radius-bearing (they change what
> every agent receives at every action boundary in every consumer project), have no
> owning mission, and should be decided before the DRG edge-migration encodes the
> ambiguity. Tracked here as a durable gap (see §4).

### 3.2 Doctrine/charter extensibility & the pack ecosystem

**Invariant.** Customers can define and refine their own doctrine as a coherent,
author-able **pack ecosystem** — packs nest and declare dependencies, and the surfaces
customers most want to extend (assets, shortcodes, mission types) are first-class
doctrine kinds — **without** a lower-tier pack being able to silently mutate a
higher-tier pack's *governed* artefact. Tier order is `built-in → org → project` (later
overlays earlier); immutability is a deliberate, opt-in pack-owner act
(`AUTHORITATIVE` + `component-type`), never implicit, and default behaviour stays
backward-compatible.

**Design of record.** Epic **#2466** (doctrine/charter extensibility & pack ecosystem —
pack-split keystone #2467, mission-types-as-doctrine #2468, assets kind, shortcodes,
pack validator; verified-distribution #2539 deferred to 3.3.x); epic **#2216**
(governance tiers — the owner-declared `component-type` immutability model folding in
the consumer-declared `replaceable-builtins.yaml` #2082) under parent epic **#1799**
(charter/doctrine governance configuration & docs); the pack/DRG merge semantics in ADR
[2026-05-16-1](../../adr/3.x/2026-05-16-1-doctrine-layer-merge-semantics.md)
(`enhances` = field-merge, `overrides` = full replacement, `specializes_from` lineage
as a DRG edge); and the [doctrine-inclusion-assessment](../doctrine/doctrine-inclusion-assessment.md)
(the three pillars — agent profiles, mission-type customization, ad-hoc composition —
and the compiler gap).

**Open issues.** Chiefly the #2466 children: **#2467** (pack-split keystone — the
foundational schema change everything else builds on), **#2468** (promote mission types +
step contracts to full doctrine kinds — sizing **L**, carrying a *named* "reverses a
tested no-silent-fallback contract" risk that requires its own decision record), the
assets-kind / shortcodes / pack-validator kinds (parallelisable once the keystone
lands), plus the #2216 governance-tier work. `mission-type` is deliberately **not** yet
an `ArtifactKind` (`MissionTypeNotAnArtifactKind` is intentional); its promotion is #2468
territory and must **not** land as a quiet behaviour change.

### 3.3 Activation-driven availability & the single canonical mission-type source

**Invariant.** What mission types (and artefacts) are *available* is derived from the
**charter activation set** (`activated_mission_types`), **not** from filesystem
position — a mission type present on disk but not charter-activated is neither offered
by `init`/enumeration nor resolvable as a template. There is **one** canonical
mission-type source and **no second availability source**: the derived
`src/specify_cli/missions/` tree is retired so `software-dev` is an ordinary peer
doctrine type that cannot be inherited by default.

**Design of record.** Epic **#2652** (specify_cli/missions retirement — slice 2+;
sequenced #2658 template-slot → #2659 activation-driven enumeration → #2660 remove the
`meta.json`-less fallback → #2661 delete the doctrine→`.kittify` copy step) and its AC
("availability is charter-activation-driven, not filesystem-driven"); the provisioned
default-charter revision (#2657, under #461) that retires "all built-in doctrine" as the
implicit default; and the interlock analysis in the now-archived
[next-slice-wheel-mission-types-public-api-research](../doctrine/next-slice-wheel-mission-types-public-api-research.md)
note *(deprecated — historical record)* (how #3091 / #2468 / #2652 converge on the same
end state via three independently sequenced efforts).

**Open issues.**

- **#3251 (no milestone, → #2652)** — the `rc35_activate_builtin_mission_types` upgrade
  migration seeds from a disk-scan roster rather than the authored `default.yaml`; the
  two agree today (both four) but **drift** the moment a fifth built-in type is added.
  A concrete "second seed authority" leak against this invariant — repoint to the shared
  `default.yaml` helper or add a sync guard.
- **#3183 (→ #2652)** — `UnknownMissionTypeError` conflates "activated in config" with
  "has a loadable profile" — the exact activation-vs-availability vocabulary collision
  this sub-area exists to close; a relocation slice should resolve it, not inherit it.
- The #2652 sub-issue chain itself (#2658 → #2659 → #2660 → #2661), with #2659 blocked
  externally on #2657 (provisioned default charter).

### 3.4 Doctrine content quality

**Invariant.** Shipped doctrine artefact **content** — not just its wiring — is
correctly scoped, non-duplicated, and operationalised as it claims: a directive whose
title promises multi-ecosystem coverage does not silently operationalise only one
ecosystem, and a tactic is not duplicated across artefacts. Content is subject to the
same "resolves means reachable, not just present" honesty the activation surface demands.

**Design of record.** *None as an owning workstream* — this is the domain's content-QA
gap (see §4). The nearest guardrails are the terminology enforcement in the
[glossary program](../glossary-doctrine-overhaul-program.md) (canonical-term casing, banned
synonyms) and the reachability-metric discipline recorded in the now-archived
[reachability assessment §5](../doctrine/charter-activation-reachability-assessment.md) *(deprecated)*
(measure reachability, not incidence) — both wiring/terminology gates, neither a
content-scoping review.

**Open issues.**

- **#3275 (P3, no milestone, no owning epic)** — the supply-chain security directive is
  operationalised JS/TS-only while its scope claims multi-ecosystem coverage, with tactic
  duplication. The concrete instance of content drift, currently unowned and unmilestoned;
  §4 flags the missing workstream it exposes.

### 3.5 meta.json fail-closed read routing

**Invariant.** `meta.json` is the mission's canonical identity and VCS-lock record.
**Every read flows through the fail-closed loader** (or a shared L1 pure-decode
primitive, `text|bytes → dict|None`); a corrupt, truncated, or wrong-authority file
**fails loud** rather than being silently absorbed by an ad-hoc `json.loads` / `git show`
stdout / `show_blob` bytes read. The inline-meta-read architectural gate reaches
**0 un-routed / 0 un-allowlisted** bypass reads, with the routed floor re-derived from a
live count. This is the doctrine-adjacent facet of the metadata-authority discipline:
the split-brain / wrong-authority failure mode the epic exists to close.

**Design of record.** Epic **#3259** (finish routing the residual `meta.json` bypass
reads onto the canonical seam), continuing the `meta-fail-closed-3162` mission that
routed one of five bypass sites; the active
`meta-json-fail-closed-routing-01KZPJ1F` mission in this tree.

**Open issues.**

- **#3230 (→ #3259)** — route the 4 remaining `meta.json` bypass reads (deferred on
  routed budget + missing L1 tier, not on structure).
- **#3229 (→ #3259)** — add the L1 pure-decode primitive (`text|bytes → dict|None`) so
  the two blob-fed bypass parsers can route. The enabling seam #3230 waits on.
- **#3228 (→ #3259)** — the VCS-lock-only comparison is duplicated (2 declarations, 2
  non-equivalent comparators); collapse to one comparator.
- **#3240 (→ #3259)** — the `inline_meta_read` allow-list is absent from
  `tests/architectural/_baselines.yaml`; register it or record the deviation (open
  operator call) so the gate's floor is auditable.

### 3.6 Stable public API surface for doctrine & charter

**Invariant.** External consumers of the doctrine & charter modules bind to **one
documented, versioned public surface**, not to deep internal submodule imports — the
single-entry-point invariant is enforced by an architectural test so it cannot silently
regress. This is the `runtime → charter → doctrine` layering seen from outside: the
runtime (and any future SDK/MCP adapter) reaches doctrine **through** the charter proxy,
never directly.

**Design of record.** Design-spike **#3179** ("create a stable public API surface for
doctrine & charter modules"), which explicitly transfers the **#645/#460 pattern** —
service extraction → formalized typed contracts → architectural test enforcing the
single-entry-point invariant → *then* a transport/framework choice, sequenced last. The
verified surface gap: `doctrine/__init__.py` declares 3 public names while **79 files
reach past it across ~30 distinct submodule paths**, with no architectural test pinning
"use the public surface." The now-archived `runtime → charter → doctrine` boundary audit
([runtime-charter-doctrine-boundary](../doctrine/runtime-charter-doctrine-boundary.md), *deprecated*) is
the internal half of the same invariant; the now-archived
[next-slice research §(c)](../doctrine/next-slice-wheel-mission-types-public-api-research.md) *(deprecated)*
established that this public surface is a **precondition** for a credible wheel-cutover
external contract, not a parallel effort.

**Open issues.**

- **#3179 (P2, 3.2.x, epic home to reconcile — see §4)** — the public-API thread. Its
  own body cites the #645/#460 precedent (Refs #3101, #645, #460, #2787, #3176); the
  next-slice research recorded it as parented under #2466. §4 recommends the plan text
  reconcile its epic home to **#645** (Epic: Stable Application API Surface), whose
  single-entry-point-invariant pattern it is a direct instance of.
- **#2787** — the existing precedent for a *frozen* charter contract (`charter context
  --json` as an activation-scoped external contract with `context_schema_version`) —
  the one place this project has already frozen a stable contract, scoped to a single
  CLI JSON payload rather than the importable Python surface.

### 3.7 Glossary-as-doctrine

**Invariant.** Canonical terminology is a **first-order, activatable doctrine
artefact** (`ArtifactKind.GLOSSARY_PACK`) shipping definitions, aliases, and banned
synonyms as a distributable pack — and terminology adherence is enforced by **shipped
executable code** (the ASSET-kind gate) consuming that pack, not by hardcoded in-repo
Python tests. The dead runtime glossary pipeline is retired without losing its two live
authorities (the 104 curated canonical definitions and the CI casing gate). The
executable-ASSET primitive it introduces is what lets other repo-specific enforcement
move out of the shared runtime into doctrine.

**Design of record.** The
[Glossary Doctrine Overhaul — Program Plan](../glossary-doctrine-overhaul-program.md) — four
sequenced missions **A** (glossary-pack kind keystone, #1418) → **D** (executable
ASSET-kind gate, #2599/#2535, phased built-in-only trust model) → **B** (enforcement +
cleanup, #2822/#2830/#2823) → **C** (retire the runtime glossary, #2727) — and its
correctness traps (URN must be `glossary_pack:` underscore; the silent-invisibility
guard; `GLOSSARY_PACK` joins the charter-activatable universe, not the `{template,
asset}` exclusion set; three mirrored kind-lists move in lockstep).

**Open issues.** The program's own ticket set — #1418, #2599 (epic #2535), #2822, #2830, #2823, #2727
(all pre-spec at the program's last pass). This sub-area is at
program-planning maturity (`doc_status: draft`), ahead of its per-mission specs.

---

## 4. Known gaps

1. **Doctrine content-QA has no owning workstream.** #3275 (supply-chain directive
   operationalised JS/TS-only vs its multi-ecosystem scope claim; tactic duplication)
   is a concrete content-scoping defect, but it is a lone **P3, no-milestone, no-epic**
   issue. The domain's guardrails all target *wiring* (activation reachability) or
   *terminology* (glossary casing/banned-synonyms) — nothing owns *content scoping /
   non-duplication / operationalisation-matches-claim* as a coherent workstream. §3.4 is
   the invariant; there is no epic behind it. Recommend either parenting #3275 (and its
   class) under a content-QA epic, or explicitly folding a content-scoping gate into the
   glossary program's ASSET-gate rail (mission B) so shipped content is reviewed the way
   its wiring now is.
2. **#3179 epic-home discrepancy.** The now-archived
   [next-slice research §(c)](../doctrine/next-slice-wheel-mission-types-public-api-research.md) *(deprecated)*
   recorded #3179 as filed **parented under #2466** (extensibility & pack ecosystem),
   while the issue itself is framed entirely on the **#645/#460** stable-application-API
   pattern (its Refs list is #3101, #645, #460, #2787, #3176) and the triage parents it
   to **#645**. These are different epics. Recommend the plan text and the tracker
   reconcile to **#645** — #3179 is a direct instance of #645's single-entry-point
   invariant, not of the pack ecosystem — and that §3.6 / §5 be the reconciling view
   until the tracker parent is corrected.
3. **Charter-sole-door residual doors are tracked in two places.** The residual bypass
   inventory lives in **both** the [charter-sole-door-deferred-issues](../doctrine/charter-sole-door-deferred-issues.md)
   record (six deferred issues: #2986, #3036, #3039, #3091, #3022, #3101) **and** the
   [Open-Core Delivery Plan §1.1](../3-2-x-open-core-delivery-plan.md) residual list
   (`resolve_template_by_id`'s 5 importers, `runtime/resolver.py`'s tier-1–4
   reimplementation, `runtime/home.py`'s importlib-resources root, three missions-root
   duplicates, the escalated #3176 site, sequenced as #3176/#3091/#3022/#3101). The two
   overlap but neither is the canonical ledger. Recommend one canonical residual-door
   ledger (this §3.1 + the deferred-issues doc as its citable summary) so a reader is not
   left to diff two lists to learn what the sole-door still leaks.
4. **Activation reachability (R1/R2) is unspecced and durable.** Per the now-archived
   [reachability assessment](../doctrine/charter-activation-reachability-assessment.md) *(deprecated)*, 185
   charter-activated artefacts surface **zero** at the action-context boundary because
   activation is operationalised as *filter membership* (V1) while the boundary renders
   from the *interview-answer* vocabulary (V2/V3). R1 (activation as an entry vector into
   action context) and R2 (collapse the three vocabularies to one, an ADR-level change)
   have no owning mission and are blast-radius-bearing across every consumer project.
   This is the domain's largest *declared-vs-in-force* gap and should be specced before
   the DRG edge-migration encodes the vocabulary ambiguity.

---

## 5. Release-scoped view (the "what ships when")

This plan tracks the **why** (invariants and sub-areas); the epic tracks the
**what-ships-when**. The table below is a snapshot for orientation, not a schedule. It
will turn over as milestones close. Verify live state via
`gh issue view <n> --repo spec-kitty/spec-kitty` before acting.

| Issue | Pri | Sub-area (§3) | Milestone | Owning epic | Notes |
|---|---|---|---|---|---|
| #3282 | P0 | Charter lifecycle (3.1) | 3.2.x | #2519 | Pointer-based charters lack mission-type activations on upgrade |
| #3176 | P1 | Charter lifecycle / sole-door (3.1) | 3.2.x | #2466 | Last builder-unreachable `.kittify/agent_profiles` site blocking `projection.py` FR-001 |
| #3261 | P3 | Charter lifecycle (3.1) | — | #2519 | `charter context --include` multi-selector mishandling |
| #2467 | P1 | Extensibility (3.2) | 3.2.x | #2466 | Pack-split keystone — foundational schema everything builds on |
| #2468 | P1 | Extensibility (3.2) | 3.2.x | #2466 | Mission-types-as-doctrine (sizing L); reverses a tested no-silent-fallback contract — needs a decision record |
| #2216 | — | Extensibility / gov tiers (3.2) | — | #1799 | Owner-declared `component-type` immutability, folds in #2082 |
| #3251 | — | Activation-driven availability (3.3) | — | #2652 | rc35 migration seeds from disk-scan, not `default.yaml` — second-authority drift |
| #3183 | — | Activation-driven availability (3.3) | — | #2652 | `UnknownMissionTypeError` conflates activation with loadability |
| #3275 | P3 | Doctrine content quality (3.4) | — | *(none — see §4)* | Supply-chain directive JS/TS-only vs multi-ecosystem scope; tactic duplication |
| #3230 | — | meta.json fail-closed (3.5) | — | #3259 | Route the 4 residual bypass reads |
| #3229 | — | meta.json fail-closed (3.5) | — | #3259 | L1 pure-decode primitive (`text\|bytes → dict\|None`) |
| #3228 | — | meta.json fail-closed (3.5) | — | #3259 | Duplicated VCS-lock comparator — collapse to one |
| #3240 | — | meta.json fail-closed (3.5) | — | #3259 | Register `inline_meta_read` allow-list in `_baselines.yaml` |
| #3179 | P2 | Public API surface (3.6) | 3.2.x | #645 *(recommended; tracker shows #2466 — see §4)* | Stable public surface; #645/#460 pattern |
| #1418 | — | Glossary-as-doctrine (3.7) | — | (glossary program) | `GLOSSARY_PACK` keystone; program mission A |
| #2599 | — | Glossary-as-doctrine (3.7) | — | #2535 | Executable ASSET-kind gate; program mission D |

*Read the WHY in §3; the epic tracks the WHAT-ships-when. Rows with no priority/milestone
are open but unscheduled; #3275 has no owning epic at all — the §4 content-QA gap.*

---

## 6. Cross-references

**Sibling domain throughlines (the durable spine of `docs/plans/`):**

- **SaaS & hosted sync** — domain plan retired 2026-09-06 (Convergence #3881; surface re-homed upstream).
  The **non-goal boundary** for this plan (§1): sync, consent/identity egress, auth, and
  rollout gating are its domain, not this one. Note the crossing thread — charter domain
  events (#2520) are emitted on *this* domain's activation seam and consumed by *that*
  domain's hosted projection.
- **Packs extraction** — *(planned sibling domain plan; not yet written.)* Will own the
  `kernel → doctrine → charter` wheel cutover (#3101, ADR 2026-08-02-1, Option B,
  no-partial) and the built-in pack extraction (#3091 missions/ relocation, #3022
  `spec-kitty-packs-open`). This plan owns the access boundary and public surface (§3.6)
  those cutovers depend on.

**Release-scoped doctrine/charter docs (the "what ships"):**

- [3.2.x Open-Core Delivery Plan](../3-2-x-open-core-delivery-plan.md) — the release-window
  delivery strategy: charter-as-sole-door done-bar (§1.1/§2.2), built-in → module
  extraction (§2.2), Creed/Values schema (§3 item 4). The `what-ships-in-3.2.x` view of
  §3.1/§3.2 here.
- [Glossary Doctrine Overhaul — Program Plan](../glossary-doctrine-overhaul-program.md) —
  the §3.7 program in detail (missions A/D/B/C; #1418/#2599/#2822/#2830/#2823/#2727).
- [Charter as Sole Door: Deferred Issues Record](../doctrine/charter-sole-door-deferred-issues.md) —
  the citable residual-door summary for §3.1 (six deferred follow-ons).

**Doctrine design corpus** ([`docs/plans/doctrine/`](../doctrine/index.md)):

- [Charter as Central Path Resolver — Gap Analysis](../doctrine/charter-path-resolution-gaps.md), [Doctrine Inclusion Assessment](../doctrine/doctrine-inclusion-assessment.md), [Layered Doctrine Resolution — Design Blueprint](../doctrine/layered-doctrine-resolution-design.md), and the FoundationalValues/Creed AUTHORITY docs — background design for §3.1/§3.2.

**Archived design notes (retired — cited above as historical provenance, not live design authority).**
These three `docs/plans/doctrine/` investigations have been distilled into the invariants and gaps above and flipped to `doc_status: deprecated`; the durable throughline no longer treats them as its live design corpus. They are retained for lineage — read them for the reasoning trail, not for current state:

- [Charter Activation vs DRG Reachability](../doctrine/charter-activation-reachability-assessment.md) *(deprecated)* — the V1/V2/V3 split and R1–R5, distilled into §3.1 and §4 gap 4.
- [Runtime → Charter → Doctrine — boundary audit](../doctrine/runtime-charter-doctrine-boundary.md) *(deprecated)* — the layering ratchet, distilled into §3.6.
- [Next doctrine slice — wheel / mission-types / public API research](../doctrine/next-slice-wheel-mission-types-public-api-research.md) *(deprecated)* — the (a)/(b)/(c) interlock, distilled into §3.3, §3.6, and §4 gap 2.

**Doctrine/charter ADRs (design of record):**

- [2026-05-16-1 doctrine-layer merge semantics](../../adr/3.x/2026-05-16-1-doctrine-layer-merge-semantics.md) — activation plan/commit seam, cascade, DRG merge verbs (§3.1, §3.2).
- [2026-08-02-1 charter-wheel assessment](../../adr/3.x/2026-08-02-1-charter-wheel-assessment.md) — the deferred `kernel → doctrine → charter` cutover (packs-extraction sibling; §3.6 precondition).

**Epics:** #2519 (charter authoring & lifecycle), #2466 (extensibility & pack ecosystem), #2652
(specify_cli/missions retirement / activation-driven availability), #1799
(governance configuration & docs), #2216 (governance tiers), #3259 (meta.json fail-closed
routing), #645 (stable application API surface).

**Plans index:** [docs/plans/index.md](../index.md).
