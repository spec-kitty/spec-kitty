---
title: 'Built-in Doctrine DRG — missing / under-specified links analysis'
description: A measured census of the built-in doctrine reference graph's obligation-vs-tension edges and cascade dead-ends — the input analysis for ADR 2026-07-21-1 (in_tension_with).
doc_status: deprecated
updated: '2026-09-30'
audience: docs/context/audience/internal/system-architect.md
related:
- docs/adr/3.x/2026-07-21-1-in-tension-with-drg-edge.md
- docs/plans/engineering-notes/index.md
---
# Built-in Doctrine DRG — Missing / Under-Specified Links Analysis

> **Historical (input analysis).** This census fed [ADR 2026-07-21-1](../../adr/3.x/2026-07-21-1-in-tension-with-drg-edge.md), which [ADR 2026-07-26-3](../../adr/3.x/2026-07-26-3-impacts-edge-subsumes-in-tension-with.md) has since superseded. The `src/doctrine/` paths below now live under `src/charter/offering/`. Kept as a record; the active cycle is 4.0.0 — see the [4.0.0 roadmap](../4-0-0-milestone-roadmap.md).

**Date:** 2026-07-21
**Branch:** `doctrine/drg-missing-links-analysis` (== `upstream/main` @ `0a79355f8`)
**Scope:** the built-in DRG only — `src/doctrine/*.graph.yaml` (10 per-kind fragments).
**Method:** all fragments parsed and cross-referenced programmatically with `ruamel.yaml`
(the same loader the runtime uses); live `spec-kitty charter lint` output folded in.
This is a read-and-report analysis — no graph file was modified.

## Ground-truth totals (measured, not inferred)

| Metric | Value |
|---|---|
| Total nodes | **289** |
| Total edges | **765** |
| Dangling edges (target URN missing) | **0** |
| Dangling edges (source URN missing) | **0** |

Node kinds: tactic 124, directive 25, template 24, action 24, procedure 22,
styleguide 19, agent_profile 18, paradigm 17, toolguide 12, mission_type 4.

Relation usage vs. the full `Relation` enum in `src/doctrine/drg/models.py`:

| Relation | Edges | Notes |
|---|---|---|
| `suggests` | 330 | |
| `requires` | 255 | |
| `scope` | 157 | **all** in `action.graph.yaml` (action → artifact) |
| `replaces` | 10 | |
| `instantiates` | 8 | action → template |
| `specializes_from` | 4 | implementer family only |
| `applies` | 1 | single edge, see finding 4 |
| `governs` | **0** | **NOT an enum member** — magic string in `orphan.py` only (never authorable) |
| `vocabulary` | **0** | enum member, never emitted |
| `delegates_to` | **0** | enum member, never emitted |
| `enhances` | **0** | enum member, never emitted |
| `overrides` | **0** | enum member, never emitted |
| `refines` | **0** | enum member, never emitted |

> **Canonical-but-sparse by design — not gaps (operator clarification).** `replaces`,
> `enhances`, `overrides`, and `specializes_from` are **canonical** relations whose primary
> role is **multi-tier pack composition** — an org/project pack augmenting or superseding
> built-in doctrine. The Spec Kitty repository does **not currently set up its own multi-tier
> pack layering**, so their low/zero edge count in the built-in layer is **expected, not a
> missing link**. Do NOT "fix" these by authoring built-in edges. Distinct cases: `governs`
> (never an enum member — a defective lint rule, #2737) and `vocabulary`/`refines` (real enum
> members, org/project-layer); `delegates_to` is a documented topological relation with no
> runtime effect yet (loose-governance agent swarm — future scope, ADR 2026-07-21-1).

---

## Executive summary — the five highest-value findings

1. **`governs` is a phantom relation: 0 edges, yet the orphan lint rule demands it on every
   directive.** All **25/25** `directive` nodes are flagged `orphaned_directive`
   (issue #2737, reproduced live). This is a **rule/graph mismatch, not a graph gap**:
   **23 of 25** directives are already referenced through other relations
   (`requires` 135, `suggests` 72, `scope` 65, `replaces` 2 inbound to directives).
   The lint rule in `orphan.py` hard-codes `{"governs"}` as the only satisfying inbound
   relation — a relation the built-in layer emits **nowhere**. **Top recommendation below.**

2. **Cascade cannot reach directives, tactics, or templates from an action.**
   `charter.cascade.REFERENCE_RELATIONS = {REQUIRES, SUGGESTS, REFINES}`
   (`src/charter/cascade.py:87`). Actions reach directives/tactics via **`scope`** (157 edges)
   and templates via **`instantiates`** (8 edges) — **none** of which cascade follows.
   So activating a `mission_type` cascades `requires` → its actions and then **stops**:
   every directive/tactic/template an action scopes is left un-activated. This is the
   single largest *functional* connectivity gap in the built-in layer.

3. **Two directives are genuinely disconnected (zero inbound of any relation):**
   `directive:DIRECTIVE_035` (bulk edit occurrence classification) and
   `directive:DIRECTIVE_039` (Lynn Cole Engineering Culture). These are real orphans that
   would survive even after the `governs`/`scope` rule is reconciled — no action, procedure,
   paradigm, or mission-type references them.

4. **`applies` is effectively a dead relation and semantically mis-wired.**
   The model docstring says *"`APPLIES` (an action applies a directive/tactic)"*, but there
   is exactly **one** `applies` edge in the whole built-in layer, and it is
   `agent_profile:doctrine-daphne → procedure:onboard-external-agent-to-pack` — profile→procedure,
   not the action→directive/tactic the model describes. The action→directive/tactic role the
   model assigns to `applies` is in practice filled by **`scope`** (157 edges). The vocabulary
   and the graph disagree about which relation carries "an action applies a rule".

5. **The `retrospect` actions are unreachable, and `plan` has none.**
   `action:documentation/retrospect`, `action:research/retrospect`, and
   `action:software-dev/retrospect` exist as nodes but have **zero** inbound edges. Every
   *other* action is pulled in by its `mission_type` via `requires`; the retrospect actions
   are not. (`mission_type:plan` has no retrospect action node at all.) Either the retrospect
   step is deliberately out-of-band or the `mission_type --requires--> …/retrospect` edges
   are simply missing.

**Top recommendation on `governs`:** do **not** author 25 `governs` edges. The relation is a
lint-only invention with no source-node kind that legitimately "governs" a directive — nothing
in the model, the activation engine, or the cascade consumes `governs`, and directives are
already well-connected via `scope`/`requires`/`suggests`. Fix the *rule*: broaden the directive
orphan rule's satisfying set from `{"governs"}` to the relations the built-in layer actually
emits toward directives (`{"scope", "requires", "suggests", "applies", "refines"}`), or retire
the directive branch of the orphan rule entirely. Then the census collapses from 25 false
positives to the **2 genuine** orphans in finding 3, which are worth a real edge each.

---

## Category detail

### 1. Orphan census (lint-expected inbound relation vs. reality)

`src/specify_cli/charter_runtime/lint/checks/orphan.py` defines three rules:

| Node kind | Required inbound relation(s) | Nodes present | Satisfying edges present | Verdict |
|---|---|---|---|---|
| `directive` | `governs` | 25 | **0 `governs`** (but 274 inbound of other relations) | **rule/graph mismatch** — 25 false orphans |
| `adr` | `supersedes` OR `references` | **0** | 0 | **dormant** — rule never fires; latent trap |
| `glossary_scope` | `vocabulary` | **0** | 0 | **dormant** — rule never fires; latent trap |

- The `directive` rule is the #2737 defect. `governs` and `vocabulary` are enum members that
  ship **zero** edges anywhere in the built-in layer; `supersedes`/`references` are not even
  enum relations used here. Neither `adr` nor `glossary_scope` node kind exists in the built-in
  graph, so those two rules are silent today — but they are the *same* class of bug waiting to
  bite: the first `adr` or `glossary_scope` node added without that exact relation will be
  flagged, regardless of how else it is connected.

**Genuinely disconnected nodes (zero inbound of *any* relation), by kind:**

| Kind | Zero-inbound | of total | Root-or-leaf expectation |
|---|---|---|---|
| `mission_type` | 4 | 4 | **Expected** — mission types are graph roots (they are edge *sources*: 21 `requires` → actions). Not real orphans; no lint rule targets them. |
| `agent_profile` | 15 | 18 | Mostly roots; see category 3. |
| `action` | 3 | 24 | **Gap** — the 3 `retrospect` actions (finding 5). |
| `directive` | 2 | 25 | **Gap** — DIRECTIVE_035, DIRECTIVE_039 (finding 3). |
| `tactic` | 18 | 124 | **Gap** — leaves that nothing suggests (list below). |
| `styleguide` | 8 | 19 | **Gap** — leaves that nothing suggests. |
| `procedure` | 4 | 22 | **Gap** — procedures nothing requires/suggests. |
| `paradigm` | 3 | 17 | **Gap** — paradigms nothing requires. |
| `toolguide` | 2 | 12 | **Gap** — `python-review-checks`, `rtk-search-tooling`. |
| `template` | 0 | 24 | Clean — all templates targeted (19 `suggests` + 8 `instantiates`). |

Disconnected **tactics** (18): `analysis-extract-before-interpret`,
`atomic-design-review-checklist`, `bounded-context-canvas-fill`,
`chain-of-responsibility-rule-pipeline`, `context-boundary-inference`,
`decision-marker-capture`, `formalized-constraint-testing`, `mutation-testing-workflow`,
`no-parallel-duplicate-test-runs`, `occurrence-classification-workflow`,
`refactoring-encapsulate-record`, `refactoring-move-field`,
`refactoring-state-pattern-for-behavior`, `reference-architectural-patterns`,
`secure-regex-catastrophic-backtracking`, `terminology-extraction-mapping`,
`test-to-system-reconstruction`, `work-package-completion-validation`.

Disconnected **styleguides** (8): `deployable-skill-authoring`, `divio-type-discipline`,
`docs-accessibility`, `docs-freshness-sla`, `java-conventions`, `plain-language`,
`reasons-canvas-writing`, `research-citation-discipline`.

Disconnected **procedures** (4): `drill-down-documentation`,
`migrate-project-guidance-to-spec-kitty-charter`, `red-main-release-discipline`,
`spike-timebox-policy`.

Disconnected **paradigms** (3): `atomic-design`, `c4-incremental-detail-modeling`,
`specification-by-example`.

Disconnected **toolguides** (2): `python-review-checks`, `rtk-search-tooling`.

Notable content mismatches here: `occurrence-classification-workflow` (tactic) and
`directive:DIRECTIVE_035` (bulk edit occurrence classification) are both orphaned yet are
obviously the same concern — a `tactic --suggests--> directive` (or an action scoping both)
would connect the pair. Likewise `java-conventions` (styleguide) is orphaned while
`agent_profile:java-jenny` exists; `plain-language`/`docs-accessibility` styleguides are
orphaned while the documentation actions exist.

### 2. Dangling / one-way edges

- **Dangling edges: 0.** Every edge `target` and every edge `source` resolves to a declared
  node. Reference integrity (`reference_integrity.py`, rule 1) is clean for the built-in layer.
- **Superseded-ADR rule (reference_integrity.py rule 2): dormant** — depends on `wp:` source
  nodes and `adr` targets, neither of which exist in the built-in layer.
- **One-way by design:** `mission_type` (4/4) and most `agent_profile` nodes appear only as
  edge sources. That is correct for roots; flagged only so a future stricter lint rule does not
  mistake them for orphans.

### 3. Expected-but-absent relations (model / engine implies an edge that is never emitted)

| Relation | Enum? | Built-in edges | What the model/engine expects | Gap severity |
|---|---|---|---|---|
| `governs` | yes | 0 | Orphan lint rule requires it inbound to every directive | **High** (25 false positives; #2737) |
| `delegates_to` | yes | 0 | Model: runtime work-handoff *between profiles* (`FR-002`); CLAUDE.md documents it as distinct from `specializes_from` | **Medium** — no profile→profile delegation encoded at all (e.g. orchestrator→implementer, implementer→reviewer) |
| `refines` | yes | 0 | Model: first-class refinement relation; cascade **follows** it | **Low/Info** — mainly an org/project-layer relation; absence in built-in is defensible |
| `enhances` / `overrides` | yes | 0 | Model: pack-layer augmentation pair | **None** — by design these belong to org/project packs, not the built-in layer |
| `vocabulary` | yes | 0 | `glossary_scope` orphan rule | **Low** — dormant (no `glossary_scope` nodes) |

**`specializes_from` coverage is thin.** Only 4 edges exist, all
`{frontend-freddy, java-jenny, node-norris, python-pedro} → implementer-ivan`. No lineage is
declared for any other profile (e.g. `reviewer-renata`, `debugger-debbie`, `curator-carla`,
`doctrine-daphne`, `randy-reducer`). If profile lineage is meant to model shared specialization,
several families are missing their parent edge.

**Cascade reachability (finding 2, expanded).** With `REFERENCE_RELATIONS = {REQUIRES, SUGGESTS,
REFINES}`, the reachable frontier from a `mission_type` is:
`mission_type --requires--> action` → **dead end**. The action's `scope` edges (→ 65 directives,
66 tactics, 8 templates, 8 paradigms, 11 procedures, 3 styleguides, 3 profiles, 1 toolguide) and
`instantiates` edges (→ templates) are not in the cascade set. Consequences:
- Activating a mission type does **not** activate the directives/tactics/templates its workflow
  actually uses.
- The only artifacts that cascade at all are those linked by `requires`/`suggests` chains that
  do *not* route through an action's `scope` — i.e. directive→directive `requires` (15),
  procedure→\* `requires` (82), paradigm→\* `requires` (41), and the `suggests` web.

Decision to make: either (a) add `scope` (and possibly `instantiates`) to `REFERENCE_RELATIONS`,
or (b) accept that `scope` is a non-activating "applicability context" relation and ensure any
artifact that must co-activate with an action is *also* linked by `requires`/`suggests`. This
should be an explicit, documented choice — right now it reads as an accident.

### 4. Cross-kind connectivity gaps

- **directive → toolguide:** 3 `suggests` edges exist (directives suggest toolguides). Good.
- **action → toolguide:** only **1** `scope` edge across all 24 actions and 12 toolguides.
  `python-review-checks` and `rtk-search-tooling` toolguides are reachable by no one.
- **tactic → toolguide:** 5 edges; **styleguide → toolguide:** 4; **procedure → toolguide:** 1.
  Toolguides are otherwise leaf documentation nobody points at.
- **`applies` (finding 4):** the model's designated "action applies a directive/tactic" relation
  is used once, and for a profile→procedure pair — a vocabulary/graph divergence.
- **templates:** fully connected as targets, but `template.graph.yaml` itself carries
  `edges: []` — every inbound edge lives in `action.graph.yaml` (`instantiates`/`scope`) or in
  tactic/procedure `suggests`. This is fine structurally but means the template fragment is
  purely a node registry; worth knowing when auditing per-file.

---

## Prioritized remediation table

| # | Gap | Option (a) — fix the rule | Option (b) — author edges | Recommendation |
|---|---|---|---|---|
| 1 | 25 false `orphaned_directive` (#2737); `governs` = 0 edges | Broaden directive orphan rule from `{governs}` to `{scope, requires, suggests, applies, refines}`, or drop the directive branch | Author 25 `governs` edges + a governing source kind | **(a)** — `governs` has no consumer; don't invent a source kind. Reduces to gap #3. |
| 2 | Cascade stops at actions (`scope`/`instantiates` not followed) | Add `SCOPE` (± `INSTANTIATES`) to `REFERENCE_RELATIONS` in `cascade.py` | Duplicate every action→artifact `scope` as a `requires`/`suggests` | **(a) with a documented decision** — pick whether `scope` is activating; encode it once. |
| 3 | 2 genuinely orphaned directives (035, 039) | n/a | `035`: link from `action:software-dev/*` scope or `tactic:occurrence-classification-workflow --suggests-->`. `039`: link from a culture/engineering paradigm or the review action scope | **(b)** — real missing edges; author them. |
| 4 | 3 unreachable `retrospect` actions; `plan` has none | n/a | Add `mission_type:{documentation,research,software-dev} --requires--> …/retrospect`; decide whether `plan` needs a retrospect action | **(b)** — confirm intent, then wire. |
| 5 | 18 tactics / 8 styleguides / 4 procedures / 3 paradigms / 2 toolguides with zero inbound | Add an "unreferenced-leaf" *info* lint (currently none exists) to surface these | Author `suggests`/`scope`/`instantiates` from the action or procedure that uses each | **(b) selectively** — many are obviously usable (e.g. `java-conventions`←java-jenny/review, `mutation-testing-workflow`←review action, `plain-language`/`docs-accessibility`←documentation actions). |
| 6 | `applies` mis-wired / near-dead | Update model docstring to reflect that `scope` carries action→directive/tactic, and reserve `applies` for its real use — or remove the single mismatched edge | Re-issue the doctrine-daphne edge as the intended relation | **(a)** — reconcile vocabulary; low urgency. |
| 7 | `delegates_to` = 0 (no profile→profile runtime handoff) | Confirm delegation is intended to be runtime-only, not graph-encoded | Author `delegates_to` edges for known handoffs (orchestrator→implementer, implementer→reviewer) | **Investigate** — depends on whether built-in is meant to seed delegation. |
| 8 | `adr`/`glossary_scope` orphan rules dormant but brittle | Gate those rules on the relation actually being emitted somewhere, or document them as project-layer-only | n/a | **(a)** — pre-empt the next #2737-shaped surprise. |

---

## Appendix — reproduction

```bash
# 25 false orphaned_directive findings
spec-kitty charter lint            # → 25 MEDIUM orphaned_directive

# Totals / dangling / per-kind orphans (ruamel parse of src/doctrine/*.graph.yaml)
#   289 nodes, 765 edges, 0 dangling (target and source)
#   governs=0, vocabulary=0, delegates_to=0, enhances=0, overrides=0, refines=0
#   applies=1 (agent_profile:doctrine-daphne -> procedure:onboard-external-agent-to-pack)
#   scope=157 (all in action.graph.yaml)

# Cascade relation set
grep -n "REFERENCE_RELATIONS" src/charter/cascade.py
#   REFERENCE_RELATIONS = {REQUIRES, SUGGESTS, REFINES}

# Orphan rule relation requirements
sed -n '/_ORPHAN_RULES/,/}/p' src/specify_cli/charter_runtime/lint/checks/orphan.py
```
