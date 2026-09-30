---
title: WP & Op Schema Model — Related Open Tracker Tickets
description: 'Deduped map of open tracker issues covering WP-metadata rework, ops/WP-template moves, model-first formalization, and WP prompt/template friction, from a three-lens sweep.'
doc_status: draft
updated: '2026-09-30'
audience: docs/context/audience/internal/system-architect.md
related:
- docs/plans/investigations/wp-op-schema-model.md
- docs/archive/plans/investigations/wp-op-schema-research/README.md
---
# WP & Op Schema Model — Related Open Tracker Tickets

> **Status update (2026-09-30).** Parked idea, written against the 3.2.x milestone. The 3.x line has closed and 3.3.x was retired, so any "deferred to 3.3.x" routing below needs re-triage. The active cycle is 4.0.0 — see the [4.0.0 roadmap](../4-0-0-milestone-roadmap.md).

Deduped synthesis of a three-lens tracker sweep (WP-metadata/hash · ops/invocation ·
template-moves/format) over `Priivacy-ai/spec-kitty` (371 open issues), grounded
against [wp-op-schema-model.md](wp-op-schema-model.md). All issues below are
**OPEN** unless marked. Relationship legend: **reconcile-first** · **move** ·
**formalization** · **friction** · **blocking-parent**.

## Headline: the idea's maximal ambition is already ticketed

The single most important finding — **the "structured-authoritative, markdown-derived"
ambition already has filed tickets**, so this is a *reconcile-and-adopt*, not a
greenfield proposal:

- **#1676** (P0, epic) — *deterministic structured authoring for planning artifacts*:
  `interview → structured draft model → Pydantic validation → deterministic renderer`.
  This **is** the idea's target architecture, at P0.
- **#424** (PRD) → **#425** — *make structured planning lists JSON-canonical, render
  into Markdown* + *define canonical JSON schemas for planning artifacts*. This **is**
  the idea's Slice-X ("YAML authoritative, markdown derived") — already written down.
- **#2093 / #2400** — the WP-metadata **authority** split is already **adjudicated**
  (REWORK-staged), and decided the semantic-vs-bookkeeping boundary the *opposite* way
  (static intent stays frontmatter-canonical; dynamic state → event log). **Reconcile,
  do not re-litigate.**

Two things the idea wants are genuinely **unticketed** (see [Gaps](#unticketed-gaps)):
the semantic-only content-hash fix, and an Op scope/intent field.

---

## Bucket A — WP-metadata rework / field-authority

| # | Title (abbrev) | P | Relationship | Why |
|---|---|---|---|---|
| **2093** | WP-metadata authority split: static intent stays frontmatter, dynamic runtime state (agent/shell_pid/history/reviews) → event-log/invocation | P1 | **reconcile-first** | The decided authority split the idea must reconcile with; ruled opposite on authority. |
| **2400** | Sub-epic: Metadata & profile authority — single canonical source across WP frontmatter / event-log / invocation-time profile loading | P1 | **blocking-parent** | The live sub-epic owning single-canonical-source WP metadata; nearest home for any schema formalization. |
| 2399 | Structurally enforce agent-profile loading across all invocation contexts (ops, ad-hoc, dispatch, WP) | P1 | rework | Consumer of the #2093 authored-intent vs resolved-binding split. |
| 1841 | Deterministic pre-execution profile load at WP claim (Python, not prompt preambles) | — | rework | Same field-split consumer at claim time. |
| 2570 | Multi-lane /implement: allocator serialized behind its own uncommitted frontmatter write | — | friction | Frontmatter-as-mutable-state pain (self-write then gate). |
| 2334 | Cross-worktree planning-artifact duplication: WP frontmatter in N hand-synced copies | P2 | friction | Split-copy drift — the parity/hand-sync friction the idea targets. |
| 2644 | Refinalizing a task graph leaves stale WPCreated/TasksCompleted authority | — | friction | Event-log residual vs new graph — bookkeeping/semantic authority leaking. |
| 2643 | finalize-tasks rejects planning_artifact WPs that own Mission artifacts | — | friction | WP `owned_files`/`create_intent` validation surface too rigid. |
| 2066 | Opaque diagnostics when WP `requirement_refs` don't match spec.md FR IDs | P1 | friction | Brittle free-text FR-ID parsing of WP frontmatter. |

## Bucket B — Ops / WP-template moves into doctrine

Timing anchor for the idea. The **#2652 retirement arc** literally lifts WP prompt-templates into doctrine.

| # | Title (abbrev) | Relationship | Why |
|---|---|---|---|
| **2652** | EPIC: specify_cli/missions retirement — activation-driven availability, single canonical mission-type source | **blocking-parent** | The migration engine lifting mission-type config (+ WP templates) into doctrine. |
| **2658** | Templates-as-config: fill `template_set` slot, retire `software-dev-default` template magic | **move** | The literal "WP prompt-templates → doctrine (config)" slice. |
| 2659 | Activation-driven enumeration + mission-runtime **template discovery** | move | The template-resolution seam the idea rides (blocked by 2658 + 2657). |
| 2657 | Provisioned default charter: retire implicit 'all built-in' mission-type default | move | Availability from charter activation, not filesystem. |
| 2660 | Remove software-dev template-selection fallback in `mission.py` | move / friction | Deletes a meta.json-less template-resolution fallback. |
| 2661 | Delete doctrine→.kittify copy step + `specify_cli/missions/<type>/` dirs | move | Removes the derived mission-type tree; final consolidation. |
| 2656 | Mission-instance governance addendum layer (4th field-merge layer) | formalization | Per-`meta.json` refinement — same "record refines the instance" shape as Op-scope. |
| **2677** | Wire mission_type DRG nodes → steps, **WP templates, assets, guards** | formalization | Models "mission type → WP templates + assets" as DRG edges — the backbone the idea assumes. |
| 2680 | Shard generated DRG graph into per-kind `*.graph.yaml` fragments | blocking-parent (tidy-first) | Enabler unblocking template/asset edge growth. |
| 2467 | Split built-in doctrine into packs + compound packs (**KEYSTONE**) | blocking-parent | Pack-manifest schema + DAG everything builds against (child of CLOSED epic #2466). |
| 2468 | Promote mission types + step contracts to full doctrine artifact kinds | move | Makes `mission-type` a first-class `ArtifactKind`. |
| 2470 | Shortcodes / harness command aliases as doctrine | move | Doctrine-authored alias layer. |
| 2472 | Decide fate of standalone 'procedure' kind post mission-type promotion | formalization | Kind-consolidation ADR. |
| 883 | Mission-type governance profiles for non-software missions | blocking-parent | Root of the doctrine mission-type lineage (#2652/#2656 descend). |
| 2302 | Codify the documentation standard as doctrine (directive + templates + styleguides) | move | Precedent for lifting hand-authored templates into doctrine. |

## Bucket C — Formalization (model-first / schema / structured-authoritative)

| # | Title (abbrev) | P | Relationship | Why |
|---|---|---|---|---|
| **1676** | EPIC: deterministic structured authoring for planning artifacts | **P0** | **formalization (target)** | The idea's exact architecture: model → validate → render; includes `wps.yaml`. |
| **424** | PRD: make structured planning lists JSON-canonical, render into Markdown | P3 | formalization | The "YAML/JSON authoritative, markdown derived" ambition, already filed. |
| **425** | Define canonical JSON schemas for structured planning artifacts | P1 | formalization | Machine-readable schemas + validation for WP/tasks/lanes. |
| 1740 | Introduce `mission-card.json` deterministic machine-readable mission summary | P2 | formalization | Derived machine-readable view from scattered WP/frontmatter facts. |
| 2591 | Doctrine governance tiers: `component-type` field on all doctrine artefacts | P2 | formalization | Model-first schema growth (foundation of epic #2216). |
| 2597 | Add versioned declarative gate-binding schema to step contracts | — | formalization | Schema addition on `extra="forbid"` `MissionStep` (step 3/5 of #2535). |
| 2471 | Extract standalone pack validator as lightweight CI entry point | — | formalization | The schema+DRG drift-gate the idea's schema-checks extend. |
| 957 | Dashboard API: resource-oriented mission + WP endpoints (incl. `WorkPackageAssignment` schema) | P1 | formalization | Typed WP schema surface — a consumer of a formalized WP model. |

## Bucket D — WP prompt/template FORMAT misses & friction

| # | Title (abbrev) | Relationship | Why |
|---|---|---|---|
| 852 | Have `/spec-kitty.analyze` inspect every WP prompt before implementation | friction | WP prompts have no enforced shape — the "inconsistency" pain point. |
| 2582 | analyze not surfaced in tasks→implement; implement blocks on missing analysis-report | friction | WP-prompt handoff wall. |
| 1710 | Review prompts should require contract round-trip checks for discriminator/enum values | friction | Prompts don't enforce contract vocabulary; schema-checks move this earlier. |
| 1738 | issue-matrix completeness gate scans only spec.md, missing refs in tasks/, plan.md | friction | Frontmatter↔body / cross-file duplication cost. |
| 2642 | Staged tasks-outline cannot advance because runtime still requires `tasks.md` | friction | `wps.yaml`-as-authority collides with markdown-still-required — the adoption gap. |
| 990 | review-cycle artifact generation can wrap prior cycle frontmatter/body | friction | Frontmatter/body isolation failure across generated artifacts. |
| 2493 | Implement-review loop frictions: analysis-report re-stale on mark-status, review-cycle schema | friction | Mutable bookkeeping re-staling content-addressed artifacts — the churn pattern. |

## Sequencing / blocking parents (cross-cutting)

The idea is a **downstream consumer** of these; it sits *behind* them.

| # | Title (abbrev) | Role |
|---|---|---|
| 1797 | EPIC: 3.2.0 codebase sanitization — dead-code & LOC reduction | Home for the low-risk **Slice 0/2** (unify the 3 field lists, retire the `WorkPackage` regex scraper). |
| 2173 | EPIC: Infra-to-logic separation — inject ports (FS/Clock/GitOps/Renderer) | Express WP/Op parsing **as** a port; sequenced behind. |
| 1868 | EPIC: Canonical seams exist in name only — bind authority to type/owner | Authority-binding framing; #2400 is its sibling. |
| 2160 | EPIC: Coord topology authority for task/status surfaces (P0) | Writer/validator authority over WP/status artifacts. |
| 1666 | EPIC: Execution-state & context domain-boundary redesign (#1619 tree) | Re-cutting the WP/Mission aggregate the model must sit in — **mid-revision**. |
| 1746 | EPIC: Mission Clarity Layer (parents #1740/#1738) | "No single canonical source for what a mission is/closes" — same root. |
| 2017 | EPIC: Guards that block legitimate actions / don't model operator intent | Same intent-capture gap, at the guard layer. |
| 901 | EPIC: 4.0 central `/spec-kitty` governed front door (deferred, P3) | UX umbrella any Op-intent-enrichment would land under. |

## Dossier / sync (content-hash machinery)

The whole-file hashing of `wp*.md` lives here, but **no issue isolates the churn defect**.

| # | Title (abbrev) | Relationship |
|---|---|---|
| 2180 | P0: make Teamspace dossier sync required, replayable, automatic | friction |
| 1133 | 3.3.0: Include analyze.md in dossier sync and body upload | friction / formalization |
| 1058 | Legacy cleanup: split dossier queue migration from live emitter APIs | move / friction |
| 2144 | Guarantee every Teamspace-bound event has SQLite or git durability | friction |

## Unticketed gaps

Two of the idea's elements have **no existing open ticket** — the genuine novel residue:

1. **Semantic-only content-address (the hash-churn fix).** Hashing a normalized
   `WPMetadata` projection instead of raw bytes in `dossier/{hasher,indexer}.py` +
   `sync/body_upload.py`. The note's **highest-signal, lowest-risk slice** — and it has
   no home; it would be new work under the dossier/sync surface. `content_hash_mismatch`
   / `body_upload` / `parity hash` returned zero dedicated issues.
2. **"Make Ops persist why/what" (Op scope/intent field).** No open issue asks for it.
   The Ops layer (#1804 + all children) is **CLOSED/shipped**; the Op record shape is
   frozen (`invocation/record.py`, schema v2). An optional `scope`/`intent` field is a
   **field-extension under ADR 2026-06-11-1**, respecting `MinimalViableTrailPolicy`
   (opt-in Tier-2, C-005 no-parallel-primitive) — it attaches cleanly to **#2400**
   (authority) or as a **#2399-sibling** record-shape extension, not a new epic.

## Closed provenance — do NOT re-file

Shipped ground the idea builds on, not re-opens:

- **#1804** Ops execution layer epic + all children (#1688 Op-as-artifact, #1781 orphan
  hygiene, #1670 advise, #1229 host wrapper/traces, #1810 do/ask/advise→`dispatch`,
  #1825, closeout #1926) — **all CLOSED**.
- **#2466** doctrine/pack-ecosystem epic — **CLOSED** (but children #2467/2468/2470/2471/2472 OPEN).
- **#2651** mission-type DRG node (nodes-only) — **CLOSED**; **#2677** is the open edge-wiring follow-up.
- **#2666/2667/2668/2669** mission-type single-source + gate-wiring — **CLOSED** (PR #2676).
- **#2495** templates-as-DRG-nodes, **#2469** loose-contract ASSET kind — **CLOSED** (the primitives #2677 builds on).
- **#2654** mission-type doctrine authority slice-1 — **CLOSED**.

---

## Disposition

Across all four buckets the idea is **well-covered by existing open tickets**, and its
two headline formalization ambitions are already filed at P0/P1 (**#1676**, **#424/#425**)
with the authority question already adjudicated (**#2093/#2400**). The correct next move
is **reconcile-and-attach**, not open a new mission:

- **Formalization / structured-authoring** → reconcile the note into **#1676** (+ #424/#425).
- **WP-metadata authority** → reconcile with **#2093/#2400** (accept its authority ruling).
- **Template-move timing** → track **#2652** arc (#2658/#2659) + **#2677** DRG edges.
- **Low-risk tidy slices** → file under **#1797/#2173**.
- **Two new tickets worth opening** (unticketed): (1) semantic-only WP content-hash;
  (2) optional Op scope/intent field under #2400 / ADR 2026-06-11-1.
