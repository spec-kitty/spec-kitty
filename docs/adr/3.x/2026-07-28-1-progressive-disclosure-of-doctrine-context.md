---
title: 'ADR: doctrine context is delivered as navigable links, not inlined bodies — `when`/`reason` carry the fetch guidance'
description: 'Doctrine context arrives as navigable links: `requires` edges resolve eagerly and inline, `suggests` edges ship as `when`/`reason` fetch guidance, with an `--include-all` hatch.'
status: Accepted
doc_status: active
kind: ADR
date: '2026-07-28'
---

**Status:** Accepted

**Date:** 2026-07-28

**Deciders:** Operator (Stijn Dejongh). Proposed mid-mission during
`doctrine-delivery-reachability-01KYMXD6`, after a post-plan adversarial squad established that the
mission's delivery obligation (NFR-003: *delivery is complete, not truncated*) collides with a fixed
32,000-token context budget and a measured ~2× latency cost.

**Technical Story:** mission `doctrine-delivery-reachability-01KYMXD6`
([spec](../../../kitty-specs/doctrine-delivery-reachability-01KYMXD6/spec.md),
[plan](../../../kitty-specs/doctrine-delivery-reachability-01KYMXD6/plan.md)). Successor to
`doctrine-silence-guards-01KYFV7Q` (PR #3007, merged `ed470756e`).

**Relates to:** [ADR 2026-07-26-1](2026-07-26-1-drg-edges-are-the-canonical-relationship-authority.md)
— DRG edges are the canonical relationship authority. This ADR makes those edges *load-bearing at
runtime* rather than only at resolution time.

---

## Context

The mission that prompted this ADR closes a defect class: **a declaration that validates and reaches
nobody**. Its remedy — deliver every activated, reachable artefact at every action boundary — creates
the opposite problem.

Measured on `ed470756e`:

| quantity | value |
|---|---|
| activated artefacts | 184 |
| context budget (`BUDGET_DEFAULT`, `src/charter/context_renderers/token_budget.py:54`) | 32,000 tokens |
| bootstrap render (in-process `build_charter_context`, depth 2, `ed470756e`) | ~31.5 KB, 80 activated ids |
| steady-state render today (in-process) | ~982 ms |
| steady-state render after delivery-on-every-load (in-process) | ~1.94 s |

> **The render figures are in-process measurements, not CLI output.** `spec-kitty charter context
> --action bootstrap --json` on this branch returns ~9.5 KB / 13 ids, because the CLI cannot reach
> the bootstrap depth once first-load state is consumed — which is itself one of the defects the
> carrying mission fixes. Anyone re-deriving these must call `build_charter_context` directly with an
> explicit depth. **None of them is load-bearing for this decision**: the 184-artefact / 32,000-token
> arithmetic carries it alone.

NFR-003 forbids truncation, because truncation is how the current defect hides: the reference block's
`[:10]` cap is order-rigged such that the first tactic sits at index 34 and can never be emitted. So
the mission cannot cap. But it also cannot inline 184 artefact bodies into every prompt.

**The unexamined assumption is that delivery means inlining.**

### What the graph already carries

`DRGEdge` declares `when` and `reason`. Both are populated, on disjoint relation sets, and both were
authored as *applicability guidance* rather than as prose decoration:

| field | edges | relations | coverage of that relation | example |
|---|---|---|---|---|
| `when` | 219 | `suggests` **only** — every `when` is on a `suggests` edge | **219 of 337 `suggests` edges = 65%** | *"Use to verify the automated gates before handoff."* · *"Decision has high impact or limited reversibility."* |
| `reason` | 43 | `requires` (33), `rejects` (8), `in_tension_with` (2) | 33 of 262 `requires` = 13% | *"Applied to each sub-agent's output during convergence synthesis to identify gaps before authoring the fix plan"* |

> **Read the first column carefully — an earlier draft of this ADR misread it.** "219 of 219" is
> exhaustive on the **numerator** (every `when` sits on a `suggests` edge), not on the denominator.
> Coverage of the relation is **65%**, not 100%. The convention is real and one-directional —
> `when` belongs to `suggests` and appears nowhere else — but it is not universally applied, and
> 118 `suggests` edges carry no guidance.

`both = 0` — the populations are disjoint because they attach to different relations, not because
authoring drifted. **519 of 781 edges (66%) carry neither**, concentrated in `requires`, where an
unconditional relation arguably needs no "when".

That text is already, verbatim, the description a hypermedia link needs: *when should you follow
this?*

## Decision

**Doctrine context is delivered as a navigable link set, not as inlined bodies.**

1. Every artefact DTO returned from the charter context entrypoint carries a **`references[]`**
   element. Each entry is `{id, relation, when, reason}` — the edge's own fields, unmodified.
2. `requires` edges are **followed eagerly** and their targets delivered inline. A required artefact is
   unconditional; there is no "when" to evaluate, and 87% of `requires` edges carry no guidance text
   because none is needed.
3. `suggests` edges are **emitted as links**, carrying the edge's `when` as the fetch guidance. The
   agent decides.
4. The existing `--include <selector>` surface is the fetch verb; no new retrieval mechanism is built.
5. A **`--include-all` escape hatch** materialises the entire reachable closure inline, for harnesses
   that ignore fetch instructions and for operators who want the whole chain.

**This is the default cadence, not an opt-in mode.**

An earlier draft of this ADR deferred the default change on blast-radius grounds. **Operator ruling,
2026-07-28: that is backwards, and the deferral is withdrawn.** The mission that carries this ADR also
makes delivery happen on *every* context load. If bodies remain the default when that lands, every
agent receives 184 artefacts' worth of inlined bodies at every action boundary, and the mitigation
arrives in a later mission. **A mitigation must land with the thing it mitigates.** The window between
them is the context explosion this ADR exists to prevent.

The consumer-facing change is therefore accepted deliberately, and its ordering is a constraint:
progressive disclosure must be the default **before** delivery-on-every-load is switched on.

### What this ADR does *not* decide

- **It does not instruct agents to fetch.** Deferred to [#3056](https://github.com/Priivacy-ai/spec-kitty/issues/3056).
  This affects how *well* the link set is used, not whether the payload is safe — a link costs the same
  whether or not it is followed.

  **The authoring surface is `src/doctrine/missions/mission-steps/` — roughly 30 `prompt.md` files
  across four mission types — which then propagate.** An earlier draft said "twelve agent directories
  plus mission-steps", which inverts the repo's own rule: agent directories are *generated copies* and
  are never edited by hand. The correction makes the work **smaller to author and wider to verify**:
  verification must cover the 12 entries in `AGENT_DIRS`, the 68 shared `.agents/skills/` directories,
  and `.roo` — which `CLAUDE.md` documents as a thirteenth slash-command agent but which is **absent
  from `AGENT_DIRS`**, a pre-existing drift that would silently skip Roo.
- **It does not backfill authoring.** 118 `suggests` edges lack a `when` and render a stated default
  until they are authored.

## Rationale

**The data already fits the shape.** `when`-on-`suggests` is not a field being repurposed; it is a
field whose authored text answers exactly the question a link description must answer. The convention
is **one-directional and unambiguous** — `when` appears on `suggests` edges and nowhere else — and it
covers **65%** of that relation. The remaining 118 edges are an authoring gap, not a design mismatch:
they need the text written, not the mechanism changed.

**It resolves the NFR-003 tension without reintroducing truncation.** A link set is *complete* — every
reachable artefact is named. Nothing is silently dropped, which is the property the mission exists to
protect. Bodies are fetched, not omitted. The distinction matters: truncation removes an artefact from
an agent's awareness; a link keeps it addressable.

**It makes the relation vocabulary load-bearing at runtime.** ADR 2026-07-26-1 established DRG edges
as the canonical relationship authority. Today that authority governs *resolution*. Under this ADR it
also governs *delivery cadence* — `requires` is eager, `suggests` is lazy. The vocabulary earns its
keep twice.

**It is cheaper than the alternative on the axis that is scarce.** The latency cost the mission
accepted (~2×) is dominated by the load-and-filter, not by rendering. Links do not reduce that. What
they reduce is **token pressure**, which is the axis where a 184-artefact delivery is actually
infeasible.

## Alternatives considered

**Inline everything, raise the budget.** Rejected: 184 artefact bodies exceed any plausible budget,
and the budget is shared with the work the agent is actually doing. This is the option NFR-003's
90-id ceiling was silently approximating.

**Keep truncation, make the cap principled (per-kind quotas).** This is what the mission currently
plans for the reference block. It is strictly worse than links for the artefacts it drops: a quota
still makes an artefact invisible rather than addressable. Retained *within* the link set as an
ordering concern, not as a delivery mechanism.

**Summarise bodies instead of linking.** Rejected: a summary is a lossy copy that drifts from its
source, which is a fresh instance of the defect class this programme exists to close.

**Do nothing; let agents use `--include` unprompted.** This is today's behaviour and it is precisely
the measured defect — `--include` requires already knowing the id, so an agent cannot discover what it
does not already know about.

## Consequences

### Positive

- Complete delivery becomes affordable; NFR-003 and the token budget stop contradicting each other.
- The `when`/`reason` fields become load-bearing, which gives their authoring a reason to be correct
  and makes the 118-edge gap a visible defect rather than cosmetic absence.
- Progressive disclosure is the same shape the compact view already has (it emits ids, not bodies), so
  the plumbing largely exists.

### Negative / risks

- **A link an agent never follows is a declaration that reaches nobody** — the mission's own defect
  class, relocated one level up. This is the central risk and the reason `--include-all` is part of
  the decision rather than an afterthought: it is the falsifiability escape hatch.
- **`suggests` coverage is 65%.** 118 edges would emit a link with no guidance. Until backfilled, those
  render a stated default rather than an empty string, so absence is visible.
- **Fetch guidance in a prompt is advisory.** Harnesses vary in how faithfully they follow tool-use
  instructions. This is exactly why the default is not being changed in this ADR.

### Neutral

- No change to the DRG schema. `when` and `reason` already exist and are already serialized.

## Folding decision (mission `doctrine-delivery-reachability-01KYMXD6`)

**Partially folded.** The split is on blast radius:

| Element | Disposition |
|---|---|
| `references[]` on the context DTO, populated from edge `when`/`reason` | **Folded** — additive, uses data that exists, and WP10 is already restructuring the bundle's return shape |
| `requires` eager / `suggests` linked, **as the default cadence** | **Folded** — a delivery-cadence rule inside the gate function WP10 already builds |
| `--include-all` escape hatch | **Folded** — small, and it is the safety property that makes the rest safe |
| Agents *instructed* to fetch (prompt templates, twelve agent dirs, mission-steps) | **Deferred** — affects link *utilization*, not payload safety |
| Backfill `when` on the 118 uncovered `suggests` edges | **Deferred** — doctrine content authoring, squarely mission B2's territory |

**Ordering constraint (binding).** Progressive disclosure must be the default **before**
delivery-on-every-load is enabled. In the carrying mission that is `WP10 → WP15 → WP11`; WP11 is the
package that switches on every-load delivery, and it must not land ahead of the cadence rule.

The deferred items are both *quality* concerns — how well the link set is used, and how good its
guidance text is. Neither is a *safety* concern, because an unfollowed link costs the same as a
followed one. That is the line the split now falls on, and it is why the earlier draft's deferral of
the default was withdrawn.
