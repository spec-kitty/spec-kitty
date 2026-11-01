---
title: "Delivery-reachability wiring table (FR-015)"
description: "Per candidate artefact: proposed inbound source, its measured action-reachability (WP08 helper), and the C-007 wire/defer disposition; the deferred set is the decision surface."
doc_status: deprecated
updated: '2026-07-29T00:00:00Z'
related:
  - kitty-specs/doctrine-delivery-reachability-01KYMXD6/spec.md
  - kitty-specs/doctrine-delivery-reachability-01KYMXD6/contracts/activation-delivery.md
  - kitty-specs/doctrine-delivery-reachability-01KYMXD6/tasks/WP09-wiring-edges.md
kind: Planning
---

# Delivery-reachability wiring table (FR-015, WP09)

> **Retired (deprecated).** Design shipped via merged mission `doctrine-delivery-reachability-01KYMXD6` (15 WPs). Preserved as a historical record.

This is the enumerated wiring table FR-015 requires. Its purpose is to make
"obvious" a **computation** rather than a judgement, so this work package does
not reproduce PR #3007's failure — 4 edges authored to sources that were
themselves unreachable, so the wired artefacts still reached nobody.

## The disposition rule (C-007, operator ruling 2026-07-28)

An unreachable **activated** artefact is *obvious* (in scope to wire now) **iff**:

- **(a)** the relationship is **attested in the artefact's own text** — not
  inferred from topic adjacency — **and**
- **(b)** the proposed inbound source is **itself action-reachable** under the
  WP08 measure, **or** the edge is a `scope` edge from an **action** node.

Everything failing **(b)** is **deferred** to an after-mission operator
interview. `wire` = passes (a)+(b); `defer` = fails (b).

## How every reachability value here was measured (R-1)

Reachability is **measured, never eyeballed**. Every `source action-reachable?`
value below is the result of *calling* WP08's helper
`doctrine.drg.reachability.action_channel_reachable`, which itself *calls*
`doctrine.drg.query.resolve_context` (the single canonical walk) once per action
seed and unions the result. No BFS was reimplemented — R-1 forbids it, and every
hand-rolled walk in this mission's history produced a wrong number.

Baseline, shipped built-in graph before this WP:

| measure | value |
|---|---|
| nodes / edges | 310 / 781 |
| action-reachable artefacts, `d=1` (compact) | 111 |
| action-reachable artefacts, `d=2` (bootstrap) | 118 |
| resolved activated artefacts (node form) | 184 |
| activated **and** action-unreachable at `d=2` | 78 |

## The wiring table

`source action-reachable?` is the **measured** value for the *proposed source*
(the value C-007(b) turns on). For a `scope`-from-action row the source is an
`action` node, which is the reachability seed itself — C-007(b)'s second clause.

| # | candidate artefact | proposed inbound source | source action-reachable? (measured) | disposition |
|---|---|---|---|---|
| 1 | `directive:DIRECTIVE_042` | `action:documentation/generate` (`scope`) | **n/a — action seed** (C-007b clause 2) | **wire** |
| 2 | `asset:common-docs-structural-lint` | `directive:DIRECTIVE_042` (`requires`, already present) | **False → True after row 1 lands** | **wire (transitive)** |
| 3 | `styleguide:common-docs` | `directive:DIRECTIVE_042` (`suggests`, already present) | **False → True after row 1 lands** | **wire (transitive)** |
| 4 | `tactic:common-docs-curation` | `directive:DIRECTIVE_042` (`suggests`, already present) | **False → True after row 1 lands** | **wire (transitive)** |
| 5 | `tactic:common-docs-find` | `directive:DIRECTIVE_042` (`suggests`, already present) | **False → True after row 1 lands** | **wire (transitive)** |
| 6 | `tactic:common-docs-scaffold` | `directive:DIRECTIVE_042` (`suggests`, already present) | **False → True after row 1 lands** | **wire (transitive)** |
| 7 | `tactic:common-docs-write` | `directive:DIRECTIVE_042` (`suggests`, already present) | **False → True after row 1 lands** | **wire (transitive)** |
| 8 | `paradigm:atomic-design` | `tactic:atomic-design-review-checklist` (`suggests`, already present from PR #3007) | **False** | **defer** |
| 9 | `styleguide:reasons-canvas-writing` | `paradigm:structured-prompt-driven-development` (`suggests`, already present from PR #3007) | **False** | **defer** |
| 10 | `tactic:occurrence-classification-workflow` | `directive:DIRECTIVE_035` (`requires`, already present from PR #3007) | **False** (DIRECTIVE_035 has no reaching inbound edge) | **defer** |

Rows 8–10 are the re-adjudication of PR #3007's three still-inert wirings: each
already carries an inbound edge, but its source is itself action-unreachable
(measured **False**), so the target reaches nobody. That is precisely the
incidence-vs-reachability gap this mission exists to close — an inbound edge is
**not** reachability (R-6). They are **not** re-wired (that would repeat the #3007
error); they are recorded here and deferred.

### Why only ONE edge is authored

Row 1 (`action:documentation/generate --scope--> directive:DIRECTIVE_042`) is
the only **new** edge. DIRECTIVE_042 already carries `requires`/`suggests` edges
to the asset, the styleguide and the four common-docs tactics; making 042 itself
action-reachable delivers all six transitively (rows 2–7). Measured after the
edge lands: `d=1` and `d=2` action-reachable each grow by exactly **7**
(111→118, 118→125), the seven artefacts in rows 1–7. Minimal edge, maximal
delivery (avoid gold-plating / locality-of-change).

## The `common-docs` cluster (T050) — wired

`asset:common-docs-structural-lint` is the first shipped doctrine ASSET
(WP10/WP11 of the delivery rail ship assets). It has four inbound `requires`
edges, from DIRECTIVE_042, `styleguide:common-docs`, `tactic:common-docs-curation`
and `tactic:common-docs-scaffold` — and **all four sources were measured
unreachable**. The whole documentation-authoring family (042, the common-docs
styleguide, the common-docs `find`/`write`/`curation`/`scaffold` tactics, and the
docs styleguides `divio-type-discipline` / `docs-accessibility` /
`docs-freshness-sla` / `plain-language` / `publication-authority`) is a
strongly-connected **island**: every edge pointing into it originates **inside**
it, and **no `action` node scopes any member** (measured — the documentation
step contracts scope DIRECTIVE_010/037/003/001/018 and a handful of tactics,
never 042 or common-docs).

C-007(b) offers two ways in. Both were tested against the graph, not guessed:

1. **Edge from an action-reachable source** — measured **impossible**. Every
   artefact that even *mentions* common-docs / the structural lint / DIRECTIVE_042
   in its own text is itself action-unreachable (the cluster members plus the
   five docs styleguides). No reachable directive, tactic or procedure attests a
   relationship into the cluster, so any such edge would be topic-adjacency — the
   exact C-007(a) violation, and the #3007 failure mode.
2. **A `scope` edge from an action node** — **available and attested.**
   DIRECTIVE_042's own `scope:` text reads *"Applies whenever a documentation
   file under the Common Docs root is created, moved, renamed…"*. The
   `documentation/generate` action's `write_docs` step writes `docs/**/*.md`
   under the mission — i.e. it **creates documentation files**, exactly 042's
   stated trigger. The relationship is therefore attested in 042's own text
   (C-007a), and the source is an action node (C-007b clause 2). This is a
   recorded relationship, **not an invented one** — so the "defer instead of
   invent" guard does not fire.

**Disposition: WIRE**, via row 1.

## B2 handoff — the scope edge's canonical home

The edge lands in `HAND_AUTHORED_EDGES`
(`src/doctrine/drg/migration/hand_authored_overlay.py`), because that is where
WP09's wiring edges land per the contract and the WP prompt. The **canonical**
home for an action→artefact `scope` edge is the documentation mission **step
contract action index** — `src/doctrine/missions/built_in_step_contracts/documentation-generate.step-contract.yaml`
would list `042-common-docs` as a `delegates_to` candidate, and the extractor
would mint the scope edge from it. That surface is **outside WP09's owned
files**, so WP09 authors the reaching edge in the overlay and records the
migration here.

**Mission B2 (`drg-edge-migration-extractor-retirement-01KYFV8C`) retires the
overlay generator.** When it does, it must **not** silently drop this edge: it
migrates `action:documentation/generate --scope--> directive:DIRECTIVE_042` into
the documentation step-contract action index (and may, per 042's full scope
text, additionally scope 042 in `documentation/design`, `/publish`, `/validate`
and `/accept` — WP09 authored only the single minimal edge needed for
reachability). This is a **known** migration, inherited deliberately, not a
surprise.

## Family A (#3063 DDD family) — operator interview outcome, WIRED

The #3063 operator interview ATTESTED the Domain-Driven Design family (C-007(a)
satisfied by operator ruling). Hub: `paradigm:domain-driven-design`. Fourteen
edges land in `HAND_AUTHORED_EDGES`:

| # | source | relation | target | delivers reachability? |
|---|---|---|---|---|
| A1 | `action:software-dev/specify` | **`scope`** | `paradigm:domain-driven-design` | **yes — the reaching edge** |
| A2–A11 | `paradigm:domain-driven-design` | `requires` | the 10 DDD members below | yes, transitively via A1 |
| A12 | `agent_profile:architect-alphonso` | `suggests` | `paradigm:domain-driven-design` | no — composition-only (inert) |
| A13 | `agent_profile:paula-patterns` | `suggests` | `paradigm:domain-driven-design` | no — composition-only (inert) |
| A14 | `agent_profile:randy-reducer` | `suggests` | `paradigm:domain-driven-design` | no — composition-only (inert) |

The 10 `requires` members (A2–A11), each attested as DDD in its **own** text:
`tactic:bounded-context-identification`, `tactic:context-mapping-classification`,
`tactic:context-boundary-inference`, `tactic:bounded-context-canvas-fill`,
`tactic:strategic-domain-classification`, `tactic:aggregate-boundary-design`,
`tactic:entity-value-object-classification`, `tactic:domain-event-capture`,
`tactic:anti-corruption-layer`, `styleguide:aggregate-design-rules`.

### ⚠️ The specify edge is `scope`, NOT `suggests` (relation correction)

The #3063 wiring instruction named the specify→paradigm edge `suggests` **and**
required it to change action reachability + move the pinned unreachable sets.
Those two are contradictory, and the contradiction is resolved by **measurement**
(WP08 helper, R-1): a `suggests` edge whose SOURCE is an `action` node is **inert**
— `resolve_context` walks `suggests` only from scope-resolved artifacts, never
from the action node itself (`query.resolve_context` steps 2/3 seed from
`scoped_artifacts`). Measured: `specify --suggests--> ddd` leaves `d=1`/`d=2`
unchanged (118/125); `specify --scope--> ddd` grows both by 12. Only `scope`
delivers — exactly the WP09 precedent (`documentation/generate --scope--> 042`).
The `§3` mandate ("this edge DOES change action reachability; update the pins")
is satisfiable **only** by `scope`, so the edge is authored as `scope` and the
`suggests` label is corrected here. C-007: (a) DDD's own summary attests aligning
code with a deep domain model — what the software-dev specify step does; (b) the
source is an `action` node (C-007(b) clause 2).

### Attestation audit — what was EXCLUDED as non-attested

- `tactic:reference-architectural-patterns` — its own text is *general* reference-
  architecture selection by quality attributes (scalability/consistency/latency),
  with no DDD content. NOT a DDD member; the `requires` edge is **not** authored.
- `tactic:compositional-stream-boundaries`, `tactic:cross-cutting-state-via-store`,
  `tactic:atomic-state-ownership` — state/UI concerns, not DDD strategic/tactical
  design. Left out (per the #3063 ambiguity guard).

### DEFERRED — the DDD↔documentation mutual-reinforcement edge (B1)

Not authored: the DDD↔documentation mutual-reinforcement relationship is **gated
on the upcoming value-based edge properties (B1)** and is left **pending** until
that lands. Recorded here, not wired.

### Measured reachability delta (WP08 helper, R-1)

`d=1` action-reachable 118→130; `d=2` 125→137 (each +12). The twelve that become
action-reachable and leave BOTH `_ACTION_UNREACHABLE_D1`/`D2`:
`paradigm:domain-driven-design`, `directive:DIRECTIVE_031`, `directive:DIRECTIVE_032`
(the paradigm's pre-existing `directive_refs`, delivered once it is scoped),
`styleguide:aggregate-design-rules`, `tactic:aggregate-boundary-design`,
`tactic:anti-corruption-layer`, `tactic:bounded-context-canvas-fill`,
`tactic:bounded-context-identification`, `tactic:context-boundary-inference`,
`tactic:context-mapping-classification`, `tactic:domain-event-capture`,
`tactic:entity-value-object-classification`.
`tactic:strategic-domain-classification` was already action-reachable, so it is
delivered but moves no pin. The profile channel is unchanged (measured 39→39): the
three `agent_profile --suggests--> ddd` edges are inert, and the DDD paradigm stays
profile-unreachable so its new `requires` edges deliver nothing there.

> **SUPERSEDED (WP03, mission `doctrine-delivery-activation-01KYQVQK`, D19):** the
> "profile channel is unchanged (measured 39→39)" claim above describes the
> pre-WP01 profile channel ({requires, specializes_from} only). WP01 added
> `SUGGESTS`, so the live profile channel reaches far more
> (`_PROFILE_UNREACHABLE` 153 → 60). See "Composition ledger (NFR-002) —
> profile-channel walk-activation" below for the current record. Left in situ as
> the historical Family-A record.

## The deferred set (T052) — the operator's decision surface

> **WP03 reconciliation (mission `doctrine-delivery-activation-01KYQVQK`, D19):**
> This "**50**" is the **action-channel** deferred set (`_ACTION_UNREACHABLE_D2`),
> re-measured and **confirmed still 50** — WP02's Family A/B/C topology is
> action-inert. The "**60**" that appears in the Family B/C ledgers below
> ("Deferred set unchanged at 60") is a *pre-Family-D snapshot*, not a live
> baseline (this same section records Family D delivering 10, 60 → 50). The plan's
> D19 asked to reset 50 → 60; re-measurement shows 50 is the correct current
> action figure, so it is left at 50. What this mission *does* lower is the
> **neither-channel** deferred set (delivered by no channel): 48 → 20, via WP01's
> profile-channel `suggests` walk. See "Composition ledger (NFR-002) —
> profile-channel walk-activation" for the 30 rescued members and the 20 that
> remain.

These **50** activated artefacts remain action-unreachable at `d=2` after row 1
(WP09), Family A (#3063), and Family D (#3063, ACCEPT DELIVERY) land. Each fails C-007(b): no action-reachable source with a textually-attested
relationship, and no `scope`-from-action path whose relationship is attested
without invention. **Family E (#3063) does not change this count**: it is
topology-only / INERT (every source is the architect profile or an action-
unreachable tactic/toolguide, and the reinforcement edges point into already-
reachable paradigms), so no artefact leaves the deferred set — delivery is the
fast-follow's job per the operator. The set stays at **50**. **This is not a filed issue** — it is the surface the
after-mission operator interview rules on (C-007). Wiring any of these now would
mean either wiring to an unreachable source (#3007's error) or inventing a
relationship (the guard T050 forbids).

> **Family D (#3063) delivered 10 of the previous 60.** The operator ruled
> ACCEPT DELIVERY for the TESTING/BDD/MUTATION family, so these left the deferred
> set and are now action-reachable at implement/review (they are dropped from the
> list below): `paradigm:specification-by-example`,
> `procedure:example-mapping-workshop`, `tactic:development-bdd`,
> `tactic:atdd-adversarial-acceptance`, `tactic:formalized-constraint-testing`,
> `tactic:adversarial-qa-handoff`, `tactic:work-package-completion-validation`
> (all seven reachable at d=1 and d=2), plus `tactic:reverse-speccing`,
> `tactic:test-to-system-reconstruction` and `styleguide:mutation-aware-test-design`
> (reachable at d=2 only). See the Family D section below.

### Note: 4 of the 50 are edge-incident from a reachable source, depth-gated

The following already carry an inbound edge **from an action-reachable source**,
but the edge is `suggests` (or a `requires` chain) that sits **beyond the
traversal depth horizon**, so `resolve_context` does not reach them at `d=2`.
They are **not orphans** and are **not** wiring candidates: the relationship
already exists as an edge; "fixing" them would mean upgrading `suggests`→`requires`
(claiming a hard dependency the text does not attest) or deepening the bootstrap
walk — both are traversal-policy decisions for the operator, not edge authoring.
(Five former rows — `DIRECTIVE_032`, `anti-corruption-layer`,
`bounded-context-identification`, `context-mapping-classification`,
`domain-event-capture` — left this table when Family A (#3063) made them
action-reachable via the DDD paradigm.)

| artefact | reachable inbound source (relation) |
|---|---|
| `tactic:ownership-map-leeway` | `styleguide:planning-and-tracking` (suggests) |
| `tactic:pr-agent-worktree-isolation` | `directive:DIRECTIVE_043` (suggests) |
| `tactic:zombies-tdd` | `tactic:delete-the-assertion-not-the-test` (suggests) |
| `toolguide:github-tracker` | `styleguide:planning-and-tracking` (suggests) |

(`procedure:example-mapping-workshop` left this table when Family D made it
action-reachable at implement/review via `directive:DIRECTIVE_034`.)

**Operator ruling (2026-07-29): ACCEPT all four as-is.** They are reachable in
principle — an agent following the `suggests` chain still reaches them — and
correctly sit *beyond the eager `d=2` bootstrap horizon* by design. The two
alternatives were both rejected: upgrading `suggests`→`requires` would falsely
claim a hard dependency none of the four texts attest (misrepresentation), and
deepening the bootstrap walk is a **global** traversal-policy change whose blast
radius pulls in *every* depth-3 artefact, not just these four. Delivery-depth
tuning (and the profile-channel `suggests`-follow that would animate the inert
Family B/C/E edges) is deferred to the **fast-follow walk-update mission**. No
edge is upgraded and no walk is deepened here.

### Full deferred set (50), by kind — directive 4 · paradigm 3 · procedure 4 · styleguide 3 · tactic 28 · toolguide 8

- `directive:DIRECTIVE_035`
- `directive:DIRECTIVE_038`
- `directive:DIRECTIVE_039`
- `directive:DIRECTIVE_044`
- `paradigm:atomic-design`
- `paradigm:c4-incremental-detail-modeling` — Family C: topology authored, delivery pending
- `paradigm:structured-prompt-driven-development`
- `procedure:documentation-gap-prioritization` — Family C candidate EXCLUDED as non-attested (see Family C section)
- `procedure:drill-down-documentation` — Family C: topology authored, delivery pending
- `procedure:event-storming-discovery`
- `procedure:migrate-project-guidance-to-spec-kitty-charter`
- `styleguide:deployable-skill-authoring`
- `styleguide:java-conventions`
- `styleguide:reasons-canvas-writing`
- `tactic:analysis-extract-before-interpret`
- `tactic:architecture-diagram-review-checklist` — Family C: topology authored, delivery pending
- `tactic:atomic-design-review-checklist`
- `tactic:atomic-state-ownership`
- `tactic:c4-zoom-in-architecture-documentation` — Family C: topology authored, delivery pending
- `tactic:canonical-source-unification`
- `tactic:chain-of-responsibility-rule-pipeline`
- `tactic:code-documentation-analysis` — Family C: topology authored, delivery pending
- `tactic:compositional-stream-boundaries`
- `tactic:cross-cutting-state-via-store`
- `tactic:mutation-testing-workflow`
- `tactic:occurrence-classification-workflow`
- `tactic:ownership-map-leeway`
- `tactic:pr-agent-worktree-isolation`
- `tactic:reasons-canvas-fill`
- `tactic:reasons-canvas-review`
- `tactic:refactoring-encapsulate-record` — Family B: topology authored, delivery pending
- `tactic:refactoring-encapsulate-variable` — Family B: topology authored, delivery pending
- `tactic:refactoring-extract-first-order-concept` — Family B: topology authored, delivery pending
- `tactic:refactoring-move-field` — Family B: topology authored, delivery pending
- `tactic:refactoring-move-method` — Family B: topology authored, delivery pending
- `tactic:refactoring-state-pattern-for-behavior` — Family B: topology authored, delivery pending
- `tactic:refactoring-strangler-fig` — Family B: topology authored, delivery pending
- `tactic:reference-architectural-patterns`
- `tactic:secure-regex-catastrophic-backtracking`
- `tactic:terminology-extraction-mapping`
- `tactic:test-readability-clarity-check`
- `tactic:zombies-tdd`
- `toolguide:contextive`
- `toolguide:github-tracker`
- `toolguide:maven-review-checks`
- `toolguide:mermaid-diagramming` — Family C: topology authored, delivery pending
- `toolguide:plantuml-diagramming` — Family C: topology authored, delivery pending
- `toolguide:python-mutation-tools`
- `toolguide:terminology-guard`
- `toolguide:typescript-mutation-tools`

## Composition ledger (NFR-002) — profile-channel walk-activation (mission `doctrine-delivery-activation-01KYQVQK`, WP01 + WP03)

**This section is the successor to the "fast-follow walk-update mission" the
prose above repeatedly defers to.** Mission `doctrine-delivery-activation-01KYQVQK`
IS that fast-follow. WP01 added `Relation.SUGGESTS` to `PROFILE_CHANNEL_RELATIONS`
(`src/doctrine/drg/reachability.py`, FR-001), so the profile channel's unbounded
`walk_edges` closure now follows the soft-recommendation web out of every activated
agent profile — animating the previously-inert Family B/C/E `suggests` edges the
prior mission authored (lines above: *"the profile-channel `suggests`-follow that
would animate the inert Family B/C/E edges … is deferred to the fast-follow
walk-update mission"*).

### Pin moves (measured via `profile_channel_reachable` / `action_channel_reachable` only — C-001)

Every number below traces to a call through the canonical reachability helpers
(no hand-rolled walk). WP03 re-measured against the WP01+WP02 topology:

- **`_PROFILE_UNREACHABLE` 153 → 60** (`tests/doctrine/drg/test_reachability.py`).
  93 activated artefacts became profile-reachable via a `suggests` chain from an
  activated profile once WP01's relation addition landed.
- **`_PROFILE_RESCUES` 2 → 30** (`_ACTION_UNREACHABLE_D2 − _PROFILE_UNREACHABLE`).
  These 30 are the mission's actual *delivery*: activated artefacts the action
  channel misses at `d=2` but the profile channel now reaches. Enumerated below.
- **`_ACTION_UNREACHABLE_D1` (60) and `_ACTION_UNREACHABLE_D2` (50) UNCHANGED** —
  measured, not assumed. WP02's Family-A `when` backfill, the C4
  `template:instantiates` edge and the anti-pattern `REJECTS` edges are all
  action-channel-inert (a `when` guard, an `instantiates` edge no channel walks,
  and validation-tier `REJECTS` edges — D13/D14). So this mission moves **no**
  action-channel pin. `_ACTION_UNREACHABLE_D2` staying at 50 is the load-bearing
  confirmation that the "50 vs 60" contradiction below is a *timeline* artefact,
  not a live discrepancy (see the reconciliation note).

### The 30 rescued artefacts, by prior-mission family attribution

Each is now delivered through the **profile** channel (the responsible change is
WP01's `PROFILE_CHANNEL_RELATIONS` `SUGGESTS` addition; the family grouping names
the `suggests` cluster the artefact sits in, most authored by the prior mission's
Family B/C topology):

- **Family B (#3063 REFACTORING) — 7**, formerly "topology authored, delivery pending":
  `tactic:refactoring-encapsulate-record`, `tactic:refactoring-encapsulate-variable`,
  `tactic:refactoring-extract-first-order-concept`, `tactic:refactoring-move-field`,
  `tactic:refactoring-move-method`, `tactic:refactoring-state-pattern-for-behavior`,
  `tactic:refactoring-strangler-fig`.
- **Family C (#3063 ARCHITECTURE-DOCS / DIAGRAMMING) — 7**, formerly "topology authored, delivery pending":
  `paradigm:c4-incremental-detail-modeling`, `procedure:drill-down-documentation`,
  `tactic:architecture-diagram-review-checklist`, `tactic:c4-zoom-in-architecture-documentation`,
  `tactic:code-documentation-analysis`, `toolguide:mermaid-diagramming`,
  `toolguide:plantuml-diagramming`.
- **Depth-gated `suggests` (the "4 of the 50 edge-incident, depth-gated" table above) — 4**:
  `tactic:ownership-map-leeway`, `tactic:pr-agent-worktree-isolation`,
  `tactic:zombies-tdd`, `toolguide:github-tracker`. These carried an inbound
  `suggests` from a reachable source but sat beyond the action-channel `d=2`
  horizon; the profile channel's unbounded closure now reaches them.
- **Other `suggests`-web artefacts — 10**:
  `procedure:event-storming-discovery`, `styleguide:reasons-canvas-writing`,
  `tactic:canonical-source-unification`, `tactic:mutation-testing-workflow`,
  `tactic:occurrence-classification-workflow`, `tactic:terminology-extraction-mapping`,
  `toolguide:contextive`, `toolguide:python-mutation-tools`,
  `toolguide:terminology-guard`, `toolguide:typescript-mutation-tools`.
- **Already profile-reachable pre-mission (in the prior `_PROFILE_RESCUES`) — 2**:
  `directive:DIRECTIVE_044`, `tactic:test-readability-clarity-check` (reached via a
  profile `requires`/`suggests` edge that pre-dates WP01; carried forward).

### Deferred set (neither channel) — 48 → 20

The wiring table's "deferred set" (the `d=2` action-unreachable list above) is a
**single-channel** surface. The operator's true decision surface is what **no**
channel delivers — `_ACTION_UNREACHABLE_D2 ∩ _PROFILE_UNREACHABLE`. Before this
mission the profile channel rescued only 2 of the 50, so the neither-channel set
was 48. After WP01 it rescues 30, so the neither-channel deferred set drops to
**20**:

- `directive:DIRECTIVE_035`
- `directive:DIRECTIVE_038`
- `directive:DIRECTIVE_039`
- `paradigm:atomic-design`
- `paradigm:structured-prompt-driven-development`
- `procedure:documentation-gap-prioritization`
- `procedure:migrate-project-guidance-to-spec-kitty-charter`
- `styleguide:deployable-skill-authoring`
- `styleguide:java-conventions`
- `tactic:analysis-extract-before-interpret`
- `tactic:atomic-design-review-checklist`
- `tactic:atomic-state-ownership`
- `tactic:chain-of-responsibility-rule-pipeline`
- `tactic:compositional-stream-boundaries`
- `tactic:cross-cutting-state-via-store`
- `tactic:reasons-canvas-fill`
- `tactic:reasons-canvas-review`
- `tactic:reference-architectural-patterns`
- `tactic:secure-regex-catastrophic-backtracking`
- `toolguide:maven-review-checks`

### Reconciliation note — the "50 vs 60" / "39→39" stale prose (WP03, D19)

The plan's D19 asked WP03 to treat the main deferred-set section's **50** as
stale and reset it to **60**. WP03's re-measurement shows the opposite is true, so
this note records the correct reconciliation instead of a silent inversion
(NFR-002 forbids moving a golden number without a paired justification, and that
cuts both ways — including *not* moving a correct one to match a stale premise):

- **`_ACTION_UNREACHABLE_D2` measures 50**, exactly matching the main
  "Full deferred set (50)" section. The `60 → 50` transition is the same doc's
  own Family-D ledger ("Family D delivered 10 of the previous 60"). So **50 is the
  current, correct action-channel figure**; the **60** in the Family B/C ledgers
  ("Deferred set unchanged at 60") is a *pre-Family-D snapshot* written earlier in
  the doc's authoring, not a live baseline. The two numbers are a timeline
  artefact of a multi-pass document, not a contradiction to resolve by picking 60.
- **The "profile channel … measured 39→39" claims (Family A section) ARE stale**
  (D19 correct on this point): they describe the profile channel *before* WP01
  added `SUGGESTS`. Under the live topology the profile channel reaches far more
  (`_PROFILE_UNREACHABLE` 153 → 60), so those "39→39" figures are superseded by
  this ledger. They are left in place as the historical Family-A record and
  explicitly superseded here rather than edited in situ, to keep the Family-A
  diff legible.
- **Net**: this mission does not lower the *action-channel* deferred count (it
  stays 50, correctly). It lowers the *neither-channel* deferred count 48 → 20 via
  the profile channel — the genuine delivery this mission ships. Per D18 the
  per-member ledger-vs-diff comparison above is the sole non-delegable correctness
  gate for the pins; a reviewer should verify each of the 30 rescued members and
  the 20 remaining against the measured diff.

### Writing-comms/diagramming activation (commit `9a99801f1`, #3009) — profile-channel rescues +6

The dogfooding activation of the writing-comms/diagramming doctrine set (commit
`9a99801f1`) added seventeen artefacts to the action-channel unreachable sets
(`_ACTION_UNREACHABLE_D1`/`D2`). Seven of the seventeen are **rescued by the
profile channel** — action-`d=2`-unreachable yet delivered by an activated
writing-comms profile — so `_PROFILE_RESCUES` moves **30 → 37**. Each delivering
edge is traced from the built-in graph via `profile_channel_reachable` (C-001, no
hand-rolled walk):

- `directive:DIRECTIVE_047` — `agent_profile:scribe-sally` requires it directly.
- `directive:DIRECTIVE_048` — `agent_profile:scribe-sally` requires it directly.
- `directive:DIRECTIVE_049` — `agent_profile:minutes-maker-mahad` requires it directly.
- `directive:DIRECTIVE_050` — `agent_profile:minutes-maker-mahad` requires it directly.
- `directive:USE_C4_MODEL_TECHNIQUES` — `agent_profile:diagram-daisy` requires it
  directly (the slug-hub directive; its store slug `use-c4-model-techniques` now
  normalizes to this node URN via the `id_normalizer` hyphen→underscore fix).
- `styleguide:quadruple-a-test-format` — via `agent_profile:generic-agent` →
  `directive:DIRECTIVE_041` --`suggests`--> the styleguide.
- `tactic:writing-audience-catalog` — `agent_profile:comms-cleo` reaches it directly.

The other ten of the seventeen are unreachable from **both** channels and are
recorded as tracked #3009 debt (added to `_PROFILE_UNREACHABLE`), to be wired with
real inbound edges by the deferred orphan-wiring doctrine mission — they are NOT
rescues and carry no ledger row here. (`directive:RECONCILE_CHANGE_SCOPE_TENSIONS`
is one of the ten: it is wired only by hand-authored `reconciles_tension` overlay
edges the profile channel does not walk.)

### Mission `drg-reachability-metric-wiring-01KZS5VR` (WP01, #3009 point 3) — profile-channel rescue +1 / -10

Six genuine traced edges land (`_CURATED_ARTIFACT_EDGES`, `src/doctrine/drg/migration/extractor.py`
— see the companion-metric section near the end of this document for the full
edge table). Two members move the profile-channel pins:

- **`_PROFILE_UNREACHABLE` 62 → 60** (`-2`). `directive:RECONCILE_CHANGE_SCOPE_TENSIONS`
  becomes profile-reachable via `directive:DIRECTIVE_024 --suggests--> RECONCILE`
  and `directive:DIRECTIVE_025 --suggests--> RECONCILE` (both 024/025 are
  themselves profile-reachable, so the closure reaches RECONCILE). `procedure:
  glossary-maintenance-workflow` becomes profile-reachable via
  `agent_profile:lexical-larry --suggests--> glossary-maintenance-workflow`
  (larry is a profile-channel seed).
- **`_PROFILE_RESCUES` 37 → 28** (`-10` leave, `+1` enters). TEN members leave:
  `tactic:mutation-testing-workflow`, the seven `refactoring-*` Fowler tactics
  (`tactic:refactoring-encapsulate-record`, `tactic:refactoring-encapsulate-variable`,
  `tactic:refactoring-extract-first-order-concept`, `tactic:refactoring-move-field`,
  `tactic:refactoring-move-method`, `tactic:refactoring-state-pattern-for-behavior`,
  `tactic:refactoring-strangler-fig`) and `toolguide:python-mutation-tools` /
  `toolguide:typescript-mutation-tools` all became action-`d=2`-reachable (the
  new `procedure:refactoring --suggests--> directive:DISCIPLINED_REFACTORING`
  and `directive:DIRECTIVE_030 --suggests--> directive:USE_MUTATION_TESTING_TO_
  VALIDATE_TEST_QUALITY` edges cascade their tactic families into the action
  channel at the bootstrap depth), so the action channel now covers them and
  they leave the profile-only rescue set. ONE member enters:
  `procedure:glossary-maintenance-workflow` (see above) — it stays
  action-`d=2`-unreachable but is now profile-reachable, so it moves from
  `_PROFILE_UNREACHABLE` into `_PROFILE_RESCUES`.
- `directive:RECONCILE_CHANGE_SCOPE_TENSIONS` leaves BOTH `_ACTION_UNREACHABLE_D2`
  and `_PROFILE_UNREACHABLE` (it is reachable at both depths via edges 2/3 — see
  the companion-metric section), so it does **not** enter `_PROFILE_RESCUES`
  (defined as the set difference of the two).

## Composition ledger (NFR-004) — counts this WP moves

The single authored edge moves these counts. Each is recorded so no golden
number moves silently.

- **Shipped-graph edges 781 → 782** (+1). `len(HAND_AUTHORED_EDGES)` 17 → 18. The
  pure-extraction golden counts (`_EXPECTED_NODE_COUNT=304`, `_EXPECTED_EDGE_COUNT=764`)
  are **unchanged** — the edge is overlay-authored, not extractor-derived — so
  `test_extractor_projection`'s byte-identical assertion (`… == _EXPECTED_EDGE_COUNT + len(HAND_AUTHORED_EDGES)`)
  stays green by construction once the fragments are regenerated. Ledger entry (8)
  is added to that module's composition ledger.
- **`scope`-relation histogram 157 → 158.** `RELATION_DESCRIPTIONS[Relation.SCOPE]`
  (`doctrine.drg.models`) and its char-for-char mirror in
  `docs/architecture/doctrine-relationships.md` state "(157 edges)"; both move to
  "(158 edges)". This count **is** gated —
  `tests/architectural/test_no_authored_applies_edge.py::TestPositiveCountClaimsAreTrue`
  parses the claim and asserts it against the live graph — so the prose is a
  contract, updated here, not left to drift.
- **`_ACTION_UNREACHABLE_D1` and `_ACTION_UNREACHABLE_D2`** (WP08,
  `tests/doctrine/drg/test_reachability.py`) each **lose the same 6 members**:
  `directive:DIRECTIVE_042`, `styleguide:common-docs`,
  `tactic:common-docs-curation`, `tactic:common-docs-find`,
  `tactic:common-docs-scaffold`, `tactic:common-docs-write`. The `d1↔d2` spread
  stays 7 (same members removed from both); `_PROFILE_UNREACHABLE` and
  `_PROFILE_RESCUES` are unaffected (the profile channel is unchanged, and the 6
  are profile-unreachable too). Orphan sets are unaffected (042 and the asset were
  already edge-incident). Ledgered in that module's docstring.

## Composition ledger (NFR-004) — Family A (#3063 DDD family)

Fourteen authored edges. Each moved count is recorded so no golden number moves
silently.

- **Shipped-graph edges 782 → 796** (+14). `len(HAND_AUTHORED_EDGES)` 18 → 32. The
  pure-extraction golden counts (`_EXPECTED_NODE_COUNT=304`, `_EXPECTED_EDGE_COUNT=764`)
  are **unchanged** — all fourteen are overlay-authored — so
  `test_extractor_projection`'s byte-identical assertion stays green once the
  fragments are regenerated (`764 + 32 = 796`). Ledger entry (9) is added to that
  module's composition ledger.
- **Relation histogram**: `requires` 262 → 272 (+10 paradigm→member edges),
  `suggests` 337 → 340 (+3 profile→paradigm edges), `scope` 158 → 159 (+1 reaching
  edge). All three are gated by
  `tests/architectural/test_no_authored_applies_edge.py::TestPositiveCountClaimsAreTrue`
  and mirrored char-for-char in `RELATION_DESCRIPTIONS` (`doctrine.drg.models`) and
  `docs/architecture/doctrine-relationships.md`; all updated.
- **`_ACTION_UNREACHABLE_D1` and `_ACTION_UNREACHABLE_D2`** each **lose the same 12
  members**: `paradigm:domain-driven-design`, `directive:DIRECTIVE_031`,
  `directive:DIRECTIVE_032`, `styleguide:aggregate-design-rules`,
  `tactic:aggregate-boundary-design`, `tactic:anti-corruption-layer`,
  `tactic:bounded-context-canvas-fill`, `tactic:bounded-context-identification`,
  `tactic:context-boundary-inference`, `tactic:context-mapping-classification`,
  `tactic:domain-event-capture`, `tactic:entity-value-object-classification`. The
  `d1↔d2` spread stays 7 (same members removed from both).
  `tactic:strategic-domain-classification` was already reachable, so it moves no
  pin.
- **`_PROFILE_UNREACHABLE` unchanged** (profile channel measured 39→39). **`_PROFILE_RESCUES`
  loses 4** (`directive:DIRECTIVE_031`, `directive:DIRECTIVE_032`,
  `tactic:anti-corruption-layer`, `tactic:domain-event-capture`) — the action
  channel now covers them, so they are no longer profile-only rescues.
- **Orphan sets unaffected** — every one of the 14 endpoints was already
  edge-incident.
- **Deferred set 72 → 60** (directive 6→4, paradigm 5→4, styleguide 5→4, tactic
  43→35; procedure 5 and toolguide 8 unchanged).

## Family B (#3063 REFACTORING family) — operator interview outcome, INERT (composition-only)

The #3063 operator interview ATTESTED a REFACTORING family (C-007(a) satisfied by
operator ruling). Its hub is a **NEW built-in directive**,
`directive:DISCIPLINED_REFACTORING`
(`src/doctrine/directives/built-in/disciplined-refactoring.directive.yaml`):
disciplined, behaviour-preserving refactoring — refactor in small steps under
green tests, name the smell before the move, one transformation at a time,
structural moves kept separate from behaviour changes. No equivalent directive
existed (`grep -ri refactor src/doctrine/directives/` found only the
`reconcile-change-scope-tensions` tension directive, which is unrelated).

### ⚠️ URN casing (relation/id correction)

The wiring instruction named the hub `directive:disciplined-refactoring`
(lower-kebab). A directive node's URN is derived from its artifact `id`, and the
`Directive` model requires `id` to match `^[A-Z][A-Z0-9_-]*$` while
`doctrine.drg.migration.id_normalizer.normalize_directive_id` upper-cases any
non-numeric slug — so the only URN a real directive artifact can yield is
`directive:DISCIPLINED_REFACTORING`, exactly the
`directive:RECONCILE_CHANGE_SCOPE_TENSIONS` precedent. The lower-kebab form is
unreachable through the schema; the canonical URN is UPPER_SNAKE, corrected here.

### The 14 authored edges (all `suggests`, all INERT under today's traversal)

The 7 directive→tactic edges each carry a per-tactic `when` = the tactic's own
attested applicability (the "problem" it solves), derived from the tactic's own
`purpose`/first-step text — **not invented**:

| # | source | relation | target | `when` (grounded in the tactic's own text) |
|---|---|---|---|---|
| B1 | `directive:DISCIPLINED_REFACTORING` | `suggests` | `tactic:refactoring-encapsulate-record` | a raw data record (dict/plain object/mutable named tuple) is accessed by field name from many call sites, blocking validation, renames, or a change of representation |
| B2 | `directive:DISCIPLINED_REFACTORING` | `suggests` | `tactic:refactoring-encapsulate-variable` | a widely-accessed module-level/global variable (or public attribute) is read and written from many locations and needs a single chokepoint for validation, monitoring, or a later type change |
| B3 | `directive:DISCIPLINED_REFACTORING` | `suggests` | `tactic:refactoring-extract-first-order-concept` | an important concept is implicit, duplicated, or scattered with no explicit name or single home |
| B4 | `directive:DISCIPLINED_REFACTORING` | `suggests` | `tactic:refactoring-move-field` | a field is read/modified more by another class than the one that declares it, so data ownership has drifted |
| B5 | `directive:DISCIPLINED_REFACTORING` | `suggests` | `tactic:refactoring-move-method` | a method uses more of another class's data and behaviour than its own host's (feature envy) |
| B6 | `directive:DISCIPLINED_REFACTORING` | `suggests` | `tactic:refactoring-state-pattern-for-behavior` | a class's methods are full of conditionals branching on the same internal state variable, and behaviour is driven by lifecycle state transitions |
| B7 | `directive:DISCIPLINED_REFACTORING` | `suggests` | `tactic:refactoring-strangler-fig` | a legacy component/path must be replaced incrementally — new alongside old, rerouting callers one at a time — because a single-step cutover is too risky |

The 7 profile→directive edges all share `when` = *"when tidying code, encountering
long classes/methods, or discovering convoluted logic"*. The **implementer-role
profiles** are every built-in profile whose role is `implementer` (resolved via
`spec-kitty agent profile list`; python-pedro is the primary):

| # | source (role: implementer) | relation | target |
|---|---|---|---|
| B8 | `agent_profile:frontend-freddy` | `suggests` | `directive:DISCIPLINED_REFACTORING` |
| B9 | `agent_profile:generic-agent` | `suggests` | `directive:DISCIPLINED_REFACTORING` |
| B10 | `agent_profile:implementer-ivan` | `suggests` | `directive:DISCIPLINED_REFACTORING` |
| B11 | `agent_profile:java-jenny` | `suggests` | `directive:DISCIPLINED_REFACTORING` |
| B12 | `agent_profile:node-norris` | `suggests` | `directive:DISCIPLINED_REFACTORING` |
| B13 | `agent_profile:python-pedro` (primary) | `suggests` | `directive:DISCIPLINED_REFACTORING` |
| B14 | `agent_profile:randy-reducer` | `suggests` | `directive:DISCIPLINED_REFACTORING` |

### Why Family B is INERT — measured, not assumed (WP08 helper, R-1)

All 14 edges are inert under today's traversal:

- The **directive is not charter-activated** in this project, so it never enters
  the `_activated()` universe the reachability pins subtract from — a new
  unactivated built-in directive cannot join `_ACTION_UNREACHABLE_*`.
- The **profile→directive** edges are `suggests`; the profile channel walks
  `{requires, specializes_from}` only, so it never follows them.
- The **directive→tactic** edges are only reachable if the directive is
  action-reachable, which it is **not** (no action scopes it; it is reached only
  via the inert profile edges). `resolve_context` walks `suggests` only *from*
  scope-resolved artifacts.

Measured before/after the edges landed with `resolve_context` via the WP08 helper:
`_ACTION_UNREACHABLE_D1` (67), `_ACTION_UNREACHABLE_D2` (60), `_PROFILE_UNREACHABLE`
(153) and `_PROFILE_RESCUES` (the same 4) are **UNCHANGED**. Family B moves **no**
reachability pin — only composition counts.

The seven refactoring tactics therefore **remain in the DEFERRED set above** —
*topology authored, delivery pending fast-follow*. Their delivery needs the
profile-channel walk to follow `suggests` (or the directive to be
action-scoped); that is a traversal-policy decision for the operator, not edge
authoring, so they are not action-reachable yet.

### Pending anti-pattern-authoring companion (NOT authored here)

The operator flagged that the `anti_pattern` kind — the code smells that are the
"problem" each refactor solves — is sensible to author for this family (smell →
refactor, i.e. `anti_pattern --…--> tactic:refactoring-*`). That is
doctrine-CONTENT authoring, **deferred to the fast-follow decision** and **not
authored in this pass**. Recorded here as a known companion so it is not lost.

## Composition ledger (NFR-004) — Family B (#3063 REFACTORING family)

One new directive node (via extraction) + fourteen `suggests` overlay edges. Each
moved count is recorded so no golden number moves silently.

- **Shipped-graph nodes 310 → 311** (+1). The directive is a real
  `*.directive.yaml`, so the extractor mints its node: pure golden
  `_EXPECTED_NODE_COUNT` **304 → 305** (`test_extractor_projection`). It carries
  **no inline references** (relationships are edges), so it mints **zero**
  extractor edges — `_EXPECTED_EDGE_COUNT` stays **764**.
- **Shipped-graph edges 796 → 810** (+14). `len(HAND_AUTHORED_EDGES)` **32 → 46**.
  `test_shipped_graph_is_fresh_and_byte_identical` stays green by construction
  (`764 + 46 = 810`) once the fragments are regenerated. Ledger entry (10) is added
  to that module's composition ledger.
- **`suggests` relation histogram 340 → 354** (+14; all 14 edges are `suggests`).
  `requires` (272) and `scope` (159) are **unchanged**. Gated by
  `tests/architectural/test_no_authored_applies_edge.py::TestPositiveCountClaimsAreTrue`
  and mirrored char-for-char in `RELATION_DESCRIPTIONS` (`doctrine.drg.models`) and
  `docs/architecture/doctrine-relationships.md`; both updated.
- **Orphan sets:** in a **pure** regeneration the directive is an orphan (its only
  edges are overlay-authored), so pure orphans **23 → 24** — it joins
  `_AWAITING_REFERENCES` (4 → 5) and `_ORPHANS_RESOLVED_BY_OVERLAY` (2 → 3). Shipped
  orphans stay **21** (the overlay wires it as both an edge source and target).
- **`_ACTION_UNREACHABLE_D1`/`D2`, `_PROFILE_UNREACHABLE`, `_PROFILE_RESCUES`
  UNCHANGED** — Family B is inert (measured). No pin moves.
- **Deferred set unchanged at 60** — the seven refactoring tactics stay deferred
  (topology authored, delivery pending); no artefact leaves the set.

## Family C (#3063 ARCHITECTURE-DOCS / DIAGRAMMING family) — operator interview outcome, INERT (composition-only)

The #3063 operator interview ATTESTED an ARCHITECTURE-DOCS / DIAGRAMMING family
(C-007(a) satisfied by operator ruling). Its hub is a **NEW built-in directive**,
`directive:USE_C4_MODEL_TECHNIQUES`
(`src/doctrine/directives/built-in/use-c4-model-techniques.directive.yaml`): use
the C4 model's progressive zoom (System Context → Container → Component → Code) to
document and reason about architecture at the right level of detail; keep diagrams
as text-based, version-controlled diagram-as-code; drawn as an **extensible hub**
for architecture-documentation techniques (further techniques wired in as they are
supplied). No equivalent directive existed (`grep -ri "c4\|architecture.*model\|diagram" src/doctrine/directives/`
found none).

### ⚠️ URN casing (relation/id correction, same rule as Family B)

The wiring named the hub `directive:use-c4-model-techniques` (lower-kebab). A
directive node's URN is derived from its artifact `id`, and the `Directive` model
requires `id` to match `^[A-Z][A-Z0-9_-]*$` while
`id_normalizer.normalize_directive_id` upper-cases any non-numeric slug — so the
only URN a real directive artifact can yield is `directive:USE_C4_MODEL_TECHNIQUES`
(the `DISCIPLINED_REFACTORING` / `RECONCILE_CHANGE_SCOPE_TENSIONS` precedent). The
lower-kebab form is unreachable through the schema; the canonical URN is UPPER_SNAKE.

### The 9 authored edges (all `suggests`, all INERT under today's traversal)

The 7 directive→member edges each carry a per-member `when` = the member's own
attested applicability, derived from the member's own `purpose`/`scope`/`summary`
text — **not invented**:

| # | source | relation | target | `when` (grounded in the member's own text) |
|---|---|---|---|---|
| C1 | `directive:USE_C4_MODEL_TECHNIQUES` | `suggests` | `paradigm:c4-incremental-detail-modeling` | communicating architecture to more than one audience at more than one level of detail, so it must be broken into progressive zoom levels rather than a single all-in-one diagram |
| C2 | `directive:USE_C4_MODEL_TECHNIQUES` | `suggests` | `tactic:c4-zoom-in-architecture-documentation` | actually drawing the diagrams — starting from the System Context and zooming in to Container and Component levels only where detail adds value |
| C3 | `directive:USE_C4_MODEL_TECHNIQUES` | `suggests` | `tactic:architecture-diagram-review-checklist` | an architecture diagram is about to be shared/committed and must be understandable without a verbal walkthrough |
| C4 | `directive:USE_C4_MODEL_TECHNIQUES` | `suggests` | `toolguide:mermaid-diagramming` | rendering the diagrams as text-based, version-controlled diagram-as-code in Mermaid |
| C5 | `directive:USE_C4_MODEL_TECHNIQUES` | `suggests` | `toolguide:plantuml-diagramming` | rendering the diagrams as text-based, version-controlled diagram-as-code in PlantUML |
| C6 | `directive:USE_C4_MODEL_TECHNIQUES` | `suggests` | `procedure:drill-down-documentation` | capturing decisions/architecture at a consistent abstraction level (org → arch → design → code) with upward/downward traceability, rather than mixing levels in one artifact |
| C7 | `directive:USE_C4_MODEL_TECHNIQUES` | `suggests` | `tactic:code-documentation-analysis` | reverse-engineering or reviewing an existing system's architecture — extracting terminology from code and docs to surface implicit context boundaries before documenting them |

The reinforcement ("supporting") bridge and the profile edge:

| # | source | relation | target | `when` / note |
|---|---|---|---|---|
| C8 | `directive:USE_C4_MODEL_TECHNIQUES` | `suggests` | `paradigm:domain-driven-design` | the architecture is organised around a domain model, so its container/component boundaries should reflect bounded contexts and the ubiquitous language — the attested DDD-reinforcement leg |
| C9 | `agent_profile:architect-alphonso` | `suggests` | `directive:USE_C4_MODEL_TECHNIQUES` | `when` = "documenting or reviewing system architecture" (alphonso's attested scope) |

### The "supporting" relation and "the documentation paradigm" — what was found

- **Relation for "supporting/reinforces":** `Relation` (`src/doctrine/drg/models.py`)
  offers no dedicated support/reinforce member. The closest **attested** relation is
  `suggests` (a directional, soft, non-mandatory pointer) — used for C8. **No new
  relation kind was invented** (the "defer/report instead of invent" guard).
- **"The documentation paradigm":** there is **no distinct documentation paradigm
  node**. `paradigm:c4-incremental-detail-modeling` **IS** the documentation /
  architecture-modelling paradigm, and it is already a hub member (edge C1). So the
  "documentation" leg of "supporting the documentation and DDD paradigms" is covered
  by C1, and **only the DDD-bridge leg (C8) is added** as a separate edge. This is
  what was found and done.

### Attestation audit — what was EXCLUDED as non-attested

- `procedure:documentation-gap-prioritization` — a #3063 candidate member, but its
  own text triages documentation **gaps** by user impact across ALL doc types
  (tutorials, how-to, reference, explanation). That is a documentation-project-
  management technique, **not** a C4 / architecture-documentation / diagramming one.
  No member edge is authored for it; it stays in the DEFERRED set (plain, not
  "topology authored").

### Why Family C is INERT — measured, not assumed (WP08 helper, R-1)

All 9 edges are inert under today's traversal:

- The **directive is not charter-activated** in this project, so it never enters the
  `_activated()` universe the reachability pins subtract from — a new unactivated
  built-in directive cannot join `_ACTION_UNREACHABLE_*`.
- The **directive→member** and **directive→DDD** edges are `suggests`, and the
  directive is scoped by no action, so `resolve_context` never reaches it and never
  walks its outbound `suggests`. The seven members stay action-unreachable (they
  already were).
- The **C8 DDD-bridge** edge is INBOUND to `paradigm:domain-driven-design`, which
  Family A already made action-reachable; a directive→paradigm edge does not make
  the SOURCE reachable, so it delivers nothing new and moves no DDD pin either.
- The **profile→directive (C9)** edge is `suggests`; the profile channel walks
  `{requires, specializes_from}` only, so it never follows it.

Measured before/after with the WP08 helper: `_ACTION_UNREACHABLE_D1`,
`_ACTION_UNREACHABLE_D2`, `_PROFILE_UNREACHABLE` and `_PROFILE_RESCUES` are
**UNCHANGED**. Family C moves **no** reachability pin — only composition counts.

The seven architecture-doc technique members therefore **remain in the DEFERRED set
above** — *topology authored, delivery pending fast-follow*. Their delivery needs
the directive to be action-scoped (the canonical home would be a mission
step-contract action index), or the profile-channel walk to follow `suggests`; that
is a traversal-policy / scoping decision for the operator, not edge authoring.

### Asset / template assessment (operator asked specifically)

The mission's asset surface (`AssetRepository`, `doctrine asset` commands,
`*.asset.yaml` manifests) was assessed for shippable architecture-doc
exemplars/templates. **Finding: the exemplars already ship — as `template` artefacts,
not assets.** `src/doctrine/templates/architecture/` already contains
`c4-context-mermaid-template.md`, `c4-container-mermaid-template.md` and
`c4-component-mermaid-template.md` (plus a broad `templates/diagrams/{mermaid,plantuml}/`
library), and the C4 zoom-in tactic already references them by id
(`c4-context-mermaid-template`, etc.). A text-based C4 context+container template is
therefore **already self-contained and shipped in the correct kind** (`template`, the
fill-in-the-blanks companion), so authoring a NEW `*.asset.yaml` would duplicate
existing canonical content in the wrong kind. **Decision: author NO new asset.** The
asset kind is reserved for a loaded policy blob like `common-docs-structural-lint`
(a lint config the structural-lint gate loads), which is a different concern from a
fill-in exemplar. **Recommendation for the fast-follow:** if the operator wants these
C4 templates *delivered* to an agent's context, wire the existing template nodes via
the C4 zoom-in tactic's already-authored `references:` (a template `instantiates`
edge from the `documentation/design` action is the canonical delivery path) rather
than re-homing them as assets.

## Composition ledger (NFR-004) — Family C (#3063 ARCHITECTURE-DOCS family)

One new directive node (via extraction) + nine `suggests` overlay edges. Each moved
count is recorded so no golden number moves silently.

- **Shipped-graph nodes 311 → 312** (+1). The directive is a real `*.directive.yaml`,
  so the extractor mints its node: pure golden `_EXPECTED_NODE_COUNT` **305 → 306**
  (`test_extractor_projection`). It carries **no inline references**, so it mints
  **zero** extractor edges — `_EXPECTED_EDGE_COUNT` stays **764**.
- **Shipped-graph edges 810 → 819** (+9). `len(HAND_AUTHORED_EDGES)` **46 → 55**.
  `test_shipped_graph_is_fresh_and_byte_identical` stays green by construction
  (`764 + 55 = 819`) once the fragments are regenerated. Ledger entry (11) is added to
  that module's composition ledger.
- **`suggests` relation histogram 354 → 363** (+9; all 9 edges are `suggests`).
  `requires` (272) and `scope` (159) are **unchanged**. Gated by
  `tests/architectural/test_no_authored_applies_edge.py::TestPositiveCountClaimsAreTrue`
  and mirrored char-for-char in `RELATION_DESCRIPTIONS` (`doctrine.drg.models`) and
  `docs/architecture/doctrine-relationships.md`; both updated.
- **Orphan sets:** in a **pure** regeneration the directive is an orphan (its only
  edges are overlay-authored), so pure orphans **24 → 25** — it joins
  `_AWAITING_REFERENCES` (5 → 6) and `_ORPHANS_RESOLVED_BY_OVERLAY` (3 → 4). Shipped
  orphans stay **21** (the overlay wires it as both an edge source and target).
- **`_ACTION_UNREACHABLE_D1`/`D2`, `_PROFILE_UNREACHABLE`, `_PROFILE_RESCUES`
  UNCHANGED** — Family C is inert (measured). No pin moves.
- **Deferred set unchanged at 60** — the seven architecture-doc members stay deferred
  (topology authored, delivery pending); `documentation-gap-prioritization` stays
  deferred (excluded as non-attested); no artefact leaves the set.

## Family D (#3063 TESTING / BDD / MUTATION family) — operator interview outcome, ACCEPT DELIVERY

Unlike Families B and C (inert, composition-only), the operator ruled **ACCEPT
DELIVERY** for Family D (2026-07-29). Family D is **reachability-affecting**: it
delivers the BDD + test-quality members at implement/review, and the pins move —
exactly as Family A did for DDD-at-specify.

### Why Family D delivers (measured, not assumed — WP08 helper, R-1)

Two of the four hubs are **existing directives already `scope`-linked from
actions**: `directive:DIRECTIVE_034` (test-first-development) and
`directive:DIRECTIVE_030` (test-and-typecheck-quality-gate) are both scoped from
`action:software-dev/implement` **and** `action:software-dev/review`.
`resolve_context` step 3 walks `suggests` **from scope-resolved artifacts**, so a
`suggests` edge sourced at 034/030 **is** followed and delivers its target. This
is the opposite of the Family-B/C pattern, where the hub was a **new, non-scoped**
directive whose outbound `suggests` were never walked.

### The five new artefacts

| artefact | kind | body |
|---|---|---|
| `directive:USE_MUTATION_TESTING_TO_VALIDATE_TEST_QUALITY` | directive (`lenient-adherence`) | mutation testing validates that tests constrain behaviour; a surviving mutant reveals a hollow assertion; score is a quality signal, not a target; run on the changed scope in review |
| `styleguide:quadruple-a-test-format` | styleguide (`testing`) | Arrange / Assumption-check / Act / Assert; the assumption check MAY precede Arrange when the default state already is the precondition |
| `styleguide:given-when-then-authoring` | styleguide (`testing`) | Given=precondition, When=single trigger, Then=observable outcome; one behaviour per scenario; domain language, declarative, runner-agnostic |
| `toolguide:sonar` (+ SONAR.md) | toolguide | SonarQube static analysis + quality gate; gate on NEW-code metrics; loopback-safe URLs (no forced HTTPS on 127.0.0.1) |
| `toolguide:gherkin` (+ GHERKIN.md) | toolguide | the Gherkin DSL only (Feature/Background/Scenario/Outline/Given-When-Then-And-But/Examples); explicitly NOT stack runners |

### The 54 authored edges (all `suggests`)

- **BDD/ATDD hub `DIRECTIVE_034` → 7** (DELIVERS at implement/review): `tactic:development-bdd`, `tactic:atdd-adversarial-acceptance`, `paradigm:specification-by-example`, `tactic:formalized-constraint-testing`, `procedure:example-mapping-workshop`, `styleguide:given-when-then-authoring` (new), `toolguide:gherkin` (new).
- **Brownfield `paradigm:brownfield-onboarding` → 2** (DELIVERS at d=2 only, via a ≤2-hop suggests chain; `suggests` matches how brownfield already links its non-mandatory members): `tactic:reverse-speccing`, `tactic:test-to-system-reconstruction`.
- **Mutation hub `USE_MUTATION_TESTING_TO_VALIDATE_TEST_QUALITY` → 4** (INERT — new non-scoped hub): `tactic:mutation-testing-workflow`, `styleguide:mutation-aware-test-design`, `toolguide:python-mutation-tools`, `toolguide:typescript-mutation-tools`.
- **Test-quality hub `DIRECTIVE_030` → 5** (DELIVERS; the quality-BAR the gate enforces): `tactic:adversarial-qa-handoff`, `tactic:work-package-completion-validation`, `styleguide:testing-principles`, `styleguide:test-desiderata-and-boundaries`, `toolguide:sonar` (new).
- **Test-quality hub `DIRECTIVE_041` → 3** (INERT — 041 is NOT scope-linked from any action; the clarity/authoring side): `tactic:test-readability-clarity-check`, `tactic:zombies-tdd`, `styleguide:quadruple-a-test-format` (new).
- **Profile → hub → 32** (INERT in the profile channel): 7 implementer-role profiles (frontend-freddy, generic-agent, implementer-ivan, java-jenny, node-norris, python-pedro, randy-reducer) each → {034, mutation, 030, 041}; reviewer-renata → {030, 041, mutation}; debugger-debbie → {mutation}.
- **Event-storming → 1** (INERT): `agent_profile:architect-alphonso --suggests--> procedure:event-storming-discovery`.

**030-vs-041 split rationale:** 030 (the quality gate) heads the members that
define the *bar* a suite must clear (QA handoff, WP-completion gates, the FIRST
testing principles, test desiderata/boundaries, Sonar). 041 (tests-as-scaffold)
heads the *clarity/authoring* members (readability check, ZOMBIES increments, the
Quad-A single-behaviour skeleton). Because 030 is action-scoped and 041 is not,
the 030-headed members deliver and the 041-headed members stay deferred.

### Event-storming — inert by design, DDD-cluster member

Event Storming is a DDD-cluster discovery procedure (Family A). The operator's
earlier explicit guard keeps it **out of the eager specify delivery** (context-
overload concern). Measured: `paradigm:domain-driven-design --suggests-->
event-storming` would deliver it at specify (DDD is scope-resolved since Family A
— reachable at d=1 and d=2), so it is attached instead via
`agent_profile:architect-alphonso --suggests--> procedure:event-storming-discovery`,
which is **INERT** (measured: not reachable at d=1 or d=2; the profile channel
walks requires/specializes_from only). It can be switched to paradigm-delivered
later if the operator wants it eager at specify.

## Composition ledger (NFR-004) — Family D (#3063 TESTING / BDD / MUTATION family)

Five new artefact nodes (via extraction) + 54 `suggests` overlay edges. Each moved
count is recorded so no golden number moves silently.

- **Shipped-graph nodes 312 → 317** (+5). All five are real `*.directive.yaml` /
  `*.styleguide.yaml` / `*.toolguide.yaml`, so the extractor mints their nodes:
  pure golden `_EXPECTED_NODE_COUNT` **306 → 311** (`test_extractor_projection`).
  None carries inline references, so they mint **zero** extractor edges —
  `_EXPECTED_EDGE_COUNT` stays **764**.
- **Shipped-graph edges 819 → 873** (+54). `len(HAND_AUTHORED_EDGES)` **55 → 109**.
  `test_shipped_graph_is_fresh_and_byte_identical` stays green by construction
  (`764 + 109 = 873`) once the fragments are regenerated. Ledger entry (12) is added
  to that module's composition ledger.
- **`suggests` relation histogram 363 → 417** (+54; all 54 edges are `suggests`).
  `requires` (272) and `scope` (159) are **unchanged**. Gated by
  `tests/architectural/test_no_authored_applies_edge.py::TestPositiveCountClaimsAreTrue`
  and mirrored char-for-char in `RELATION_DESCRIPTIONS` (`doctrine.drg.models`) and
  `docs/architecture/doctrine-relationships.md`; both updated.
- **Orphan sets:** in a **pure** regeneration all five new artefacts are orphans
  (their only edges are overlay-authored), so pure orphans **25 → 30** — they join
  `_AWAITING_REFERENCES` (6 → 11) and `_ORPHANS_RESOLVED_BY_OVERLAY` (4 → 9). Shipped
  orphans stay **21** (the overlay wires every one of them).
- **`_ACTION_UNREACHABLE_D1` 67 → 60** (−7) and **`_ACTION_UNREACHABLE_D2` 60 → 50**
  (−10). D1 loses the seven delivered at the compact depth (from 034:
  development-bdd, atdd-adversarial-acceptance, specification-by-example,
  formalized-constraint-testing, example-mapping-workshop; from 030:
  adversarial-qa-handoff, work-package-completion-validation). D2 loses those seven
  **plus** reverse-speccing, test-to-system-reconstruction (brownfield chain) and
  mutation-aware-test-design (2-hop out of 030). **`_ACTION_D1_D2_SPREAD` 7 → 10**
  (the three d=2-only members move into `D1 − D2`).
- **`_PROFILE_UNREACHABLE` UNCHANGED at 153** (every family-D profile edge is
  `suggests`, which the profile channel does not follow). **`_PROFILE_RESCUES` 4 → 2**
  (development-bdd and reverse-speccing entered the action channel, so they are no
  longer profile-only rescues; `DIRECTIVE_044` and `test-readability-clarity-check`
  remain). Ledgered in `tests/doctrine/drg/test_reachability.py`.
- **Deferred set 60 → 50** — ten members leave (the delivered artefacts, listed
  above and dropped from the deferred list). The mutation-hub members
  (mutation-testing-workflow, python/typescript-mutation-tools) and the 041 fan-out
  (test-readability-clarity-check, zombies-tdd) stay deferred (topology authored,
  delivery inert); `documentation-gap-prioritization` unaffected.

## Family E (#3063 ANALYSIS / TERMINOLOGY / REASONS-CANVAS family) — operator interview outcome, INERT (topology-only)

Like Families B and C (and unlike A and D), Family E is **inert** — it moves no
reachability pin. The operator ATTESTED the relationships (C-007(a) satisfied by
operator ruling); each `when` is additionally grounded in the **source
artefact's own text** so a reviewer can verify it is not a topic-adjacency
invention. Family E authors **no new artefact files** — every endpoint already
exists — so node count / `_EXPECTED_NODE_COUNT` stay unchanged and all nine edges
are overlay-authored `suggests`.

### The 9 authored edges (all `suggests`)

**E1 — reasons-canvas / SPDD** (1 edge). Operator ruling: link only the canvas
*writing* to alphonso, for now.

| # | source | relation | target | `when` (grounded in both source texts) |
|---|---|---|---|---|
| E1 | `agent_profile:architect-alphonso` | `suggests` | `styleguide:reasons-canvas-writing` | capturing the change-intent, decision boundaries and safeguards of a mission or significant architectural change as a REASONS Canvas — recording decisions with rationale, not mirroring code |

Grounded in BOTH alphonso's attested scope (architectural decisions documented
with rationale — DIRECTIVE_003, ADR/design outputs) AND the styleguide's own
purpose (capture intent as Safeguard/Norm/Approach for a mission or change, not
mirror code). `tactic:reasons-canvas-fill`, `tactic:reasons-canvas-review` and
`paradigm:structured-prompt-driven-development` are **untouched** — they stay in
the deferred set per the operator.

**E2 group 1 — reinforcement into paradigms** (2 edges; member→paradigm, the
family-C "C8 DDD-bridge" precedent, so inert). Authored ONLY where the tactic's
own text attests.

| # | source | relation | target | `when` (grounded in the tactic's own text) |
|---|---|---|---|---|
| E2 | `tactic:terminology-extraction-mapping` | `suggests` | `paradigm:domain-driven-design` | the extracted terms must be owned by a bounded context and cross-context uses translated at the boundary — the tactic's own strategic-DDD ubiquitous-language / ACL text |
| E3 | `tactic:terminology-extraction-mapping` | `suggests` | `paradigm:brownfield-onboarding` | recovering a shared vocabulary from an existing system's code and documentation (follow-up to code-documentation-analysis) — brownfield's own "terminology aliases inferred from the code" durable artefact |

**E2 group 2 — glossary / language links** (3 edges). The fourth implied edge is
a pre-existing extractor edge (see the exclusion audit) and is **omitted**.

| # | source | relation | target | `when` (grounded in the source's own text) |
|---|---|---|---|---|
| E4 | `toolguide:contextive` | `suggests` | `tactic:glossary-curation-interview` | capturing a curation round's terms in an enforceable, IDE-surfaced ubiquitous-language glossary (contextive's own "manage ubiquitous language … alignment with glossary curation workflows") |
| E5 | `toolguide:contextive` | `suggests` | `tactic:language-driven-design` | treating terminology drift as an architectural signal — an IDE-surfaced glossary makes same-term/different-meaning conflicts visible |
| E6 | `tactic:terminology-extraction-mapping` | `suggests` | `tactic:glossary-curation-interview` | feeding the extracted, validated terms into the HiC-led curation rounds (the tactic's own purpose: build "the authoritative source for the project ubiquitous language") |

**E2 group 3 — tools-support-tactics** (3 edges; toolguide→tactic).

| # | source | relation | target | `when` (grounded in the source's own text) |
|---|---|---|---|---|
| E7 | `toolguide:terminology-guard` | `suggests` | `tactic:canonical-source-unification` | enforcing single-canonical-authority at the commit level — the terminology instance of the tactic's step-4 "add a gate to enforce the canonical route"; both cite DIRECTIVE_044 |
| E8 | `toolguide:terminology-guard` | `suggests` | `tactic:occurrence-classification-workflow` | verifying a classified bulk terminology change (a rename) is complete and stays complete — the guard fails CI if a superseded term reappears |
| E9 | `toolguide:contextive` | `suggests` | `tactic:terminology-extraction-mapping` | capturing the extracted, bounded-context-owned terms in an enforceable Contextive glossary surfaced in the IDE |

### Attestation audit — what was EXCLUDED and why

- **`tactic:terminology-extraction-mapping --suggests--> tactic:language-driven-design` (group 2, the implied 4th edge) — OMITTED as a DUPLICATE.** It already
  exists as an **extractor-minted** edge, derived from terminology-extraction-mapping's
  own `references:` block (`Language-Driven Design … Apply after the glossary is
  validated`). Re-authoring it in the overlay would be a duplicate `(source,
  relation, target)`; the operator's "avoid duplicate edges" rule applies.
- **Group 1 — `canonical-source-unification`, `analysis-extract-before-interpret`,
  `occurrence-classification-workflow` — NO paradigm edge.** None attests DDD or
  brownfield in its **own** text: canonical-source-unification is about split-brain
  code/config surfaces (refs only DIRECTIVE_044); analysis-extract-before-interpret
  is a domain-agnostic reasoning discipline (extract facts before interpreting —
  applies equally to log analysis and requirement gathering); occurrence-classification-workflow
  is a bulk-edit guardrail. Authoring a paradigm edge for any of them would be
  topic-adjacency (the C-007(a) violation). Only terminology-extraction-mapping's
  own text carries the bounded-context / ubiquitous-language / ACL vocabulary.
- **Group 3 — `contextive → canonical-source-unification` / `→ occurrence-classification-workflow` — EXCLUDED.** Contextive is a ubiquitous-language *glossary*
  tool; canonical-source-unification (code/config surface consolidation) and
  occurrence-classification-workflow (generic string bulk-edit classification) are
  not glossary/terminology work, so contextive does not support them.
- **Group 3 — `terminology-guard → terminology-extraction-mapping` — EXCLUDED.**
  The guard enforces a canon of *superseded/forbidden* terms (catching reappearances
  in active source), which supports maintaining a **canonical route** (E7) and a
  **completed rename** (E8); it does not support *building a project glossary*, which
  is contextive's job (E9). Excluded to avoid stretching the support relation.
- **`analysis-extract-before-interpret` — NO Family E edge at all.** Its own text
  attests neither a paradigm link (group 1) nor a terminology-tool support relation
  (group 3): it is a general extract-before-interpret reasoning tactic, not a
  terminology/glossary technique. It stays in the deferred set, untouched.

### Why Family E is INERT — measured, not assumed (WP08 helper, R-1)

All nine edges are inert under today's traversal:

- Every source is either `agent_profile:architect-alphonso` (a **profile**: the
  profile channel walks `{requires, specializes_from}` only, never `suggests`) or
  an **action-UNREACHABLE** tactic/toolguide — `terminology-extraction-mapping`,
  `contextive`, `terminology-guard` are all pinned in `_ACTION_UNREACHABLE_D1`/`D2`,
  and `resolve_context` walks `suggests` only **from** scope-resolved artifacts, so
  an unreachable source's outbound `suggests` are never followed.
- The two reinforcement edges (E2/E3) point **into** the already-action-reachable
  DDD / brownfield paradigms; an edge into a reachable node does not make its
  **source** reachable.

Measured before/after with the WP08 helper: `_ACTION_UNREACHABLE_D1`,
`_ACTION_UNREACHABLE_D2`, `_PROFILE_UNREACHABLE` and `_PROFILE_RESCUES` are
**UNCHANGED**. Family E moves **no** reachability pin — only composition counts.

## Composition ledger (NFR-004) — Family E (#3063 ANALYSIS / TERMINOLOGY / REASONS-CANVAS family)

Nine `suggests` overlay edges, zero new artefacts. Each moved count is recorded
so no golden number moves silently.

- **Shipped-graph edges 873 → 882** (+9). `len(HAND_AUTHORED_EDGES)` **109 → 118**.
  Zero new artefacts, so the pure-extraction golden counts (`_EXPECTED_NODE_COUNT=311`,
  `_EXPECTED_EDGE_COUNT=764`) are **unchanged** — every edge is overlay-authored —
  and `test_shipped_graph_is_fresh_and_byte_identical` stays green by construction
  (`764 + 118 = 882`) once the fragments are regenerated. Ledger entry (13) is added
  to `test_extractor_projection`'s composition ledger.
- **`suggests` relation histogram 417 → 426** (+9; all nine edges are `suggests`).
  `requires` (272) and `scope` (159) are **unchanged**. Gated by
  `tests/architectural/test_no_authored_applies_edge.py::TestPositiveCountClaimsAreTrue`
  and mirrored char-for-char in `RELATION_DESCRIPTIONS` (`doctrine.drg.models`) and
  `docs/architecture/doctrine-relationships.md`; both updated.
- **Orphan sets UNCHANGED** — every one of the nine endpoints was already
  edge-incident, so nothing enters or leaves `_AWAITING_REFERENCES` /
  `_ORPHANS_RESOLVED_BY_OVERLAY`; pure orphans stay 30, shipped orphans stay 21.
- **`_ACTION_UNREACHABLE_D1`/`D2`, `_PROFILE_UNREACHABLE`, `_PROFILE_RESCUES`
  UNCHANGED** — Family E is inert (measured). No pin moves. Ledgered in
  `tests/doctrine/drg/test_reachability.py`.
- **Deferred set unchanged at 50** — no artefact leaves (topology-only; delivery
  is the fast-follow's job per the operator).

## Family F (#3063 ORPHAN GOVERNANCE DIRECTIVES) — operator interview outcome, ACCEPT (no edges authored)

The four remaining deferred directives (`DIRECTIVE_035`, `DIRECTIVE_038`,
`DIRECTIVE_039`, `DIRECTIVE_044`) are **hub directives that reach no action** —
but three of the four are unreachable *by design*, not by defect. Unlike the
tactic/toolguide families, a directive is a hub, not a leaf, so "fixing" it means
changing its **activation model** (scope it from an action, or make it always-on),
not authoring member edges. The operator ruled **ACCEPT** — author **no edges**;
record the disposition here (2026-07-29):

| directive | activation archetype | why unreachable-by-default is CORRECT | disposition |
|---|---|---|---|
| `DIRECTIVE_038` structured-prompt-boundary | **charter-opt-in by design** | its own `scope` states *"Does not apply to projects that have not opted in via charter"* (SPDD paradigm / reasons-canvas tactics / 038) | **ACCEPT** — intentionally charter-gated; forcing it reachable would violate its own scope contract. Ties to Family E1 (SPDD/reasons-canvas). |
| `DIRECTIVE_039` lynn-cole-engineering-culture | **user-selected persona by design** | its own `intent` states *"Select this directive when the user names Lynn Cole's rules…"* | **ACCEPT** — intentionally opt-in; not an orphan to wire. |
| `DIRECTIVE_035` bulk-edit-occurrence-classification | **conditional-on-mission-property** | `scope` = *"any mission marked `change_mode: bulk_edit`"* — a mission property, not an action; scoping it from `implement`/`review` would over-deliver it to *every* mission (context bloat) | **ACCEPT** — carried by the bulk-edit mission-type / charter selection, not a broad action scope. |
| `DIRECTIVE_044` canonical-sources-and-unification | **genuinely universal → always-on candidate** | applies to *"whenever an agent selects a template/skill/command… whenever a split-brain is discovered"* — i.e. ~all agent work — yet no action scopes it | **DEFER to #3064** — the universal engineering-hygiene rule belongs in the default `charter.yml` / empty-charter always-on set; the always-on **activation-model** decision is #3064's, not edge-authoring. |

**No graph change.** Family F authors zero edges and moves zero counts; the four
directives stay in the deferred set (now understood as intentionally-gated / #3064-owned,
not defects). This closes the #3063 operator interview: Families A–E
authored, F accepted, and the four depth-gated artefacts accepted (see the
depth-gated note above). All residual delivery/activation work is owned by the
fast-follow walk-update mission and #3064.

## Composition ledger (NFR-004) — mission `rehome-writing-comms-doctrine-01KZ9V0S` (WP04)

The writing/comms rehome ships 7 new agent profiles, directives 047–050, two
styleguides, two procedures, one tactic and five audience assets. Regenerating the
DRG off that final frontmatter (`spec-kitty doctrine regenerate-graph`) moved the
following counts — each measured via `load_built_in_graph()` /
`profile_channel_reachable` / `action_channel_reachable`, never estimated:

- **Shipped built-in graph `nodes 324 → 345` (+21), `edges 892 → 930` (+38).** The
  +21 nodes are exactly the shipped artefacts (7 profiles + 4 directives + 2
  styleguides + 2 procedures + 1 tactic + 5 assets); pinned in
  `tests/doctrine/test_pack_relocation_doctor_gate.py` as `(345, 930)`.
- **`_PROFILE_UNREACHABLE` 60 → 59** (`tests/doctrine/drg/test_reachability.py`).
  One member left the set: `tactic:secure-design-checklist` became
  profile-reachable via the authored chain
  `agent_profile:minutes-maker-mahad` --`requires`--> `directive:DIRECTIVE_050`
  (`050-credential-handling-discipline`, whose `references` list carries
  `type: tactic, id: secure-design-checklist`, minted as a `suggests` edge)
  --`suggests`--> `tactic:secure-design-checklist`. Both edges are authored
  frontmatter shipped by this mission (WP01/WP02); the profile channel seeds every
  agent profile, so the new profile's `requires` edge animates the pre-existing
  `DIRECTIVE_050 -> secure-design-checklist` reference.
- **`_PROFILE_RESCUES` UNCHANGED (30).** `secure-design-checklist` is
  action-reachable at `d=2` (absent from `_ACTION_UNREACHABLE_D2`), so it was never
  in `_ACTION_UNREACHABLE_D2 − _PROFILE_UNREACHABLE`; removing it from
  `_PROFILE_UNREACHABLE` does not change the rescues set. The ledger-coverage
  cross-check (`TestProfileRescuesHaveLedgerCoverage`) is therefore unaffected.
- **`_ACTION_UNREACHABLE_D1` (60) and `_ACTION_UNREACHABLE_D2` (50) UNCHANGED** —
  measured, not assumed. The new artefacts are not charter-activated in the
  dogfood `.kittify/charter/charter.yaml`, and `agent_profile`/`asset` are not
  activation kinds, so the action-channel activated-unreachable pins do not move.
- **Glossary term count UNCHANGED (108)** — no glossary edits.

## Composition ledger (NFR-002/NFR-004) — reachability companion metric (mission `drg-reachability-metric-wiring-01KZS5VR`, WP01, #3009 point 3)

This mission adds the **action-only whole-graph reachability companion guard**
(`_ACTION_UNREACHABLE_SHIPPED`, `tests/doctrine/drg/test_reachability.py`,
`test_shipped_graph_action_reachability_is_the_pinned_membership`) — the #3009
point-3 deliverable — and wires the six genuine, traced inbound edges that make
its residual orphans reachable. Every number below is measured against the
regenerated `packs/built-in` graph via the canonical
`action_channel_reachable`/`profile_channel_reachable` helpers (C-001; no
hand-rolled walk).

### The six curated edges (`_CURATED_ARTIFACT_EDGES`, `src/doctrine/drg/migration/extractor.py`)

| # | Edge | Relation | Trace (artifact text) |
|---|---|---|---|
| 1 | `procedure:refactoring` → `directive:DISCIPLINED_REFACTORING` | `suggests` | `refactoring.procedure.yaml` step 2 ("Select the relevant refactoring tactics") already cites 9 Fowler tactics; the directive holds 7 disjoint ones plus the "name the smell first" discipline. |
| 2 | `directive:DIRECTIVE_024` → `directive:RECONCILE_CHANGE_SCOPE_TENSIONS` | `suggests` | The reconciler's own `scope` names DIRECTIVE_024 as a trigger. |
| 3 | `directive:DIRECTIVE_025` → `directive:RECONCILE_CHANGE_SCOPE_TENSIONS` | `suggests` | Same scope sentence, names DIRECTIVE_025. |
| 4 | `directive:DIRECTIVE_030` → `directive:USE_MUTATION_TESTING_TO_VALIDATE_TEST_QUALITY` | `suggests` | DIRECTIVE_030 governs the coverage gate; the mutation-testing directive critiques coverage-as-proxy, deepening the same gate. |
| 5 | `agent_profile:researcher-robbie` → `procedure:spike-timebox-policy` | `requires` | Robbie's structured `operating-procedures` field lists `spike-timebox-policy` directly. |
| 6a | `agent_profile:lexical-larry` → `procedure:glossary-maintenance-workflow` | `suggests` | Larry is the diagnostic "feeder into" the workflow; `curator-carla` owns its acceptance — `suggests`, not `requires` (larry feeds, does not own). |
| 6b | `agent_profile:minutes-maker-mahad` → `procedure:meeting-minutes-pipeline` | `requires` | Mahad's own text: "the primary agent for the meeting-minutes-pipeline procedure." |

Zero new nodes; zero new orphans (C-003). `spec-kitty doctrine regenerate-graph
--check` confirms determinism (byte-identical fragments across two runs).

### The companion metric moves: `_ACTION_UNREACHABLE_SHIPPED` 88 → 75

Primary definition (action-only, whole-graph, excludes `_BY_DESIGN_UNREACHABLE_KINDS`
and the action/profile traversal-root seeds — see the guard contract,
`kitty-specs/drg-reachability-metric-wiring-01KZS5VR/contracts/reachability-companion-guard.md`):
**88 → 75** (`-13`), asserted total & disjoint into `_DEAD_DOCTRINE_SHIPPED`
(**38 → 34**, `-4`) and `_PROFILE_DELIVERED_SHIPPED` (**50 → 41**, `-9`).

**`_WIRED_THIS_MISSION` — the thirteen URNs this mission makes action-reachable**
(pinned in `test_reachability.py`; each asserted action-reachable AND named
here — the anti-null-delta forcing mechanism, Debbie Item 1):

- `directive:DISCIPLINED_REFACTORING` — reachable via edge 1 (the already
  action-scoped `procedure:refactoring`). Was profile-channel reachable
  already, so it leaves `_ACTION_UNREACHABLE_SHIPPED` but was never a member of
  `_DEAD_DOCTRINE_SHIPPED` (it moves from `_PROFILE_DELIVERED_SHIPPED`, not
  `_DEAD_DOCTRINE_SHIPPED`, into full action-reachability).
- `directive:RECONCILE_CHANGE_SCOPE_TENSIONS` — reachable via edges 2/3. Was
  reachable from **neither** channel pre-wiring, so it leaves
  `_DEAD_DOCTRINE_SHIPPED` (one of the four `_DEAD_DOCTRINE_SHIPPED` departures).
- `directive:USE_MUTATION_TESTING_TO_VALIDATE_TEST_QUALITY` — reachable via
  edge 4 (the already action-scoped `DIRECTIVE_030`). Was profile-channel
  reachable already (same shape as DISCIPLINED_REFACTORING above); moves from
  `_PROFILE_DELIVERED_SHIPPED` into full action-reachability.
- `tactic:refactoring-encapsulate-record`, `tactic:refactoring-encapsulate-variable`,
  `tactic:refactoring-extract-first-order-concept`, `tactic:refactoring-move-field`,
  `tactic:refactoring-move-method`, `tactic:refactoring-state-pattern-for-behavior`,
  `tactic:refactoring-strangler-fig` — the seven Fowler tactics cascaded into
  action context by `directive:DISCIPLINED_REFACTORING`'s pre-existing
  `suggests` edges (family-B overlay, ledger entry 10) once edge 1 makes the
  directive itself action-reachable. All seven were `_PROFILE_DELIVERED_SHIPPED`
  members (reachable via the profile channel already); they move into full
  action-reachability, not out of `_DEAD_DOCTRINE_SHIPPED`.
- `tactic:mutation-testing-workflow`, `toolguide:python-mutation-tools`,
  `toolguide:typescript-mutation-tools` — cascaded into action context by
  `directive:USE_MUTATION_TESTING_TO_VALIDATE_TEST_QUALITY`'s pre-existing
  `suggests` edges (family-D overlay, ledger entry 12) once edge 4 makes the
  directive action-reachable. All three were `_PROFILE_DELIVERED_SHIPPED`
  members; same move as the refactoring family.

Net: **four** `_DEAD_DOCTRINE_SHIPPED` departures — `directive:RECONCILE_CHANGE_
SCOPE_TENSIONS`, `procedure:spike-timebox-policy`, `procedure:glossary-
maintenance-workflow`, `procedure:meeting-minutes-pipeline` — the four members
reachable from **neither** channel pre-wiring that a curated edge now delivers.
The other **nine** `_ACTION_UNREACHABLE_SHIPPED` departures (the `_WIRED_THIS_
MISSION` tactics/toolguides plus the two remaining directives) were already
`_PROFILE_DELIVERED_SHIPPED` — genuinely unreachable from actions, but never
"dead doctrine" (a profile already surfaces them) — so wiring them shrinks the
**action-only primary pin** (`_ACTION_UNREACHABLE_SHIPPED`) without moving
`_DEAD_DOCTRINE_SHIPPED`.

`procedure:spike-timebox-policy` (edge 5) and `procedure:meeting-minutes-pipeline`
(edge 6b) are **not** `_WIRED_THIS_MISSION` members — they leave
`_ACTION_UNREACHABLE_SHIPPED`'s `_DEAD_DOCTRINE_SHIPPED` partition (now
profile-reachable) but stay action-unreachable, so they are not among the
thirteen the action channel newly reaches; they are, however, part of the
`_ACTION_UNREACHABLE_SHIPPED` measured 88→75 delta's dead-doctrine subset move
and are named here for that reason.

### C-003 verification — no new residual/defect member

Diffing the before/after `_ACTION_UNREACHABLE_SHIPPED` sets (measured, not
assumed): the `entered` set is **empty** — no node newly joins the whole-graph
unreachable measure. The `left` set is exactly the thirteen `_WIRED_THIS_MISSION`
URNs above. Same verification for the incidence orphan sets
(`_INTENTIONAL_ORPHANS`/`_ACTIVATED_BUT_ORPHANED`/`_AWAITING_REFERENCES`,
`tests/doctrine/drg/migration/test_extractor_projection.py`): `directive:
RECONCILE_CHANGE_SCOPE_TENSIONS` leaves `_ACTIVATED_BUT_ORPHANED` (29 → 26 pure
orphans); `directive:DISCIPLINED_REFACTORING` and `directive:USE_MUTATION_
TESTING_TO_VALIDATE_TEST_QUALITY` leave `_AWAITING_REFERENCES`. All three were
already resolved by the hand-authored overlay in the *shipped* graph (ledger
entries 10/12), so `_SHIPPED_ORPHANS`/`DOCUMENTED_ORPHAN_RESIDUAL` are
UNCHANGED at 21 — already tight (no slack) before this wiring, and still tight
after.

### Activated-only action pins (`_ACTION_UNREACHABLE_D1`/`_D2`, `_ACTION_D1_D2_SPREAD`)

The whole-graph companion metric above is one measure; the pre-existing
**activated-only** pins in `tests/doctrine/drg/test_reachability.py` are a
different, narrower one (this project's `.kittify/config.yaml` activation set
intersected with unreachability). They move too, and by a DIFFERENT count than
the whole-graph companion — activation is a subset, so only the activated
members of `_WIRED_THIS_MISSION` count here:

- **`_ACTION_UNREACHABLE_D1` 77 → 76** (`-1`). Only `directive:RECONCILE_
  CHANGE_SCOPE_TENSIONS` leaves — it is the sole `_WIRED_THIS_MISSION` member
  that is BOTH charter-activated AND reachable at the compact depth (`d=1`),
  because `DIRECTIVE_024`/`DIRECTIVE_025` (edges 2/3's sources) are themselves
  `d=1`-reachable.
- **`_ACTION_UNREACHABLE_D2` 67 → 56** (`-11`). RECONCILE plus TEN activated
  cascaded members leave at the bootstrap depth: the seven `refactoring-*`
  Fowler tactics, `tactic:mutation-testing-workflow`, `toolguide:python-
  mutation-tools` and `toolguide:typescript-mutation-tools` (edges 1/4 cascade
  their pre-existing family-B/family-D `suggests` edges into `d=2` reach once
  the two new directives become action-reachable). `directive:DISCIPLINED_
  REFACTORING` and `directive:USE_MUTATION_TESTING_TO_VALIDATE_TEST_QUALITY`
  are NOT charter-activated in this project, so the two directives themselves
  never entered this activated-only pin — only their cascaded activated
  members move it.
- **`_ACTION_D1_D2_SPREAD` 10 → 20** (`+10`). The ten activated members that
  leave `_ACTION_UNREACHABLE_D2` but NOT `_ACTION_UNREACHABLE_D1` (they are
  reachable only at the bootstrap depth) join the pre-existing d1↔d2 spread
  instead of leaving D1 too.

All three moves are measured against the regenerated graph via
`action_channel_reachable` (no hand-rolled walk); see the constant docstrings
in `test_reachability.py` for the full per-member derivation.
