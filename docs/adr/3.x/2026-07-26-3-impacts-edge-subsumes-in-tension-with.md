---
title: 'ADR: a signed `impacts` edge subsumes `in_tension_with` — one relation, sign carries the direction of effect'
description: 'A signed `Relation.IMPACTS` edge subsumes `in_tension_with`: one directed relation whose numeric sign carries the direction of effect, with negative values meaning tension.'
status: Accepted
date: '2026-07-26'
doc_status: active
kind: ADR
updated: '2026-07-26T00:00:00Z'
---

**Status:** Accepted

**Date:** 2026-07-26

**Deciders:** Operator (Stijn Dejongh) — ADR-D2 (the programme-shape gate) decided explicitly on
operator authority after the trade-off was laid out with measured file counts. Design and
measurement by the FoundationalValues/creed session (15 profile-loaded agents across an initial
proposal, two adversarial squad rounds that killed the first mechanism, a four-lens hardening
round, corpus and matrix measurements, and a three-lens verification round producing a 26-item
fix ledger).

**Technical Story:** epic-level programme recorded in
[`docs/plans/doctrine/manifesto-program-delivery-sequence.md`](../../plans/doctrine/manifesto-program-delivery-sequence.md)
(sequencing authority) and
[`docs/plans/doctrine/foundational-values-and-creed.md`](../../plans/doctrine/foundational-values-and-creed.md)
(design authority). Landing on PR [#2936](https://github.com/Priivacy-ai/spec-kitty/pull/2936)
with mission `doctrine-canonical-structure-remediation-01KYEYSD`. Clears sequence gates **G1**
and **G2**.

**Supersedes:** [`docs/adr/3.x/2026-07-21-1-in-tension-with-drg-edge.md`](2026-07-21-1-in-tension-with-drg-edge.md)
(Accepted 2026-07-21).

> ⚠️ **Two ADRs share the `2026-07-21-1` prefix.** The target is the
> `in-tension-with-drg-edge` one. The `glossary-first-order-doctrine-artefact` ADR sharing that
> prefix is **not** superseded and must not be edited by this change.

---

## Context and Problem Statement

The doctrine graph has exactly one way to say two artefacts conflict: a boolean
`in_tension_with` edge. Two rules either compete or they don't — there is no way to say *how
strongly*, and no way at all to say the opposite (that one artefact **reinforces** another beyond
the coarse `requires`/`suggests` distinction).

The FoundationalValues/creed design generalises this to a signed strength on the edge:

```text
impacts: -1.0  ────────── 0 ────────── +1.0
        sabotages      neutral      reinforces
```

The operator's ruling is that **`impacts: −1` is what "is antagonistic towards" means**. Under
that ruling the boolean is not a sibling of the signed value — it is the negative half of it. So
keeping both would be two authorities for one concept, which the charter's
single-canonical-authority principle forbids and which
[ADR 2026-07-26-1](2026-07-26-1-drg-edges-are-the-canonical-relationship-authority.md) has just
finished cleaning up on the adjacent axis.

That leaves one genuinely open question, and it is the whole reason this ADR needed a decision
rather than a write-up: **once the boolean retires, what relation carries the signed value?** The
answer moves the migration between roughly 5–10 files and 45–60, so it had to be settled here
rather than discovered mid-implementation.

### Measured ground (verified in-tree, not inferred)

| Fact | Value |
| --- | --- |
| Files referencing `in_tension_with` / `IN_TENSION_WITH` | **21** (9 under `src/`, 12 under `tests/`) |
| Files touching the `Relation` vocabulary at all | **50** — this is the ripple that prices option A |
| Authored `in_tension_with` edges in the shipped graph | **2**, both in `directive.graph.yaml` |
| Relation histogram (built-in) | `suggests` 332 · `requires` 259 · `scope` 157 · `rejects` 8 · `instantiates` 8 · `specializes_from` 4 · `reconciles_tension` 3 · `in_tension_with` 2 · `applies` 1 · `refines` 0 |

The two authored edges are `DIRECTIVE_024 ↔ DIRECTIVE_025` (locality-of-change vs boy-scout) and
`DIRECTIVE_025 ↔ tactic:change-apply-smallest-viable-diff`. Both carry substantial `reason` prose
whose own words are *"both remain valid, co-activatable rules"* — i.e. the existing claims are
**symmetric**. That matters, because `IN_TENSION_WITH` is documented as symmetric and
non-transitive and is stored as a single canonical edge with the lexicographically-smaller URN as
source (constraint C-002 of its originating mission), whereas `impacts` is **directed**. The
migration therefore changes edge semantics, not merely edge labels.

## Decision Drivers

* **Single canonical authority** — one concept, one owning surface. A boolean relation plus a
  signed field expressing the same claim is two authorities.
* **The operative frame** — this layer *informs*, it never auto-decides. Numbers are conversation
  prompts; the rationale is authoritative where number and prose disagree. Any design that lets
  a magnitude decide something is out of frame.
* **Authored, never derived** — deriving tension from value vectors was measured at **5 out of 5
  false positives** on deliberately unrelated pairs. Whatever carries `impacts` must be
  hand-authored.
* **Decide the shape before the cost is sunk** — the file-count spread is ~6× between the options.
* **Do not add vocabulary to leaking infrastructure** — the org→DRG bridge currently drops
  cross-layer edges silently (see Consequences).

## Considered Options

* **Option A (chosen)** — a new `Relation.IMPACTS`: a directed, signed relation that replaces the
  boolean outright.
* **Option B** — keep `in_tension_with` as the relation and add the signed magnitude to it.
* **Option C** — adopt `Relation.IMPACTS` but retain symmetric canonical storage.
* **Option D** — keep both surfaces (boolean *and* signed field), scoped to different uses.

## Decision Outcome

**Chosen option: A — a new `Relation.IMPACTS`.**

The operator chose the clean end state over the cheap one, with the cost understood and stated.
The reviewing analysis had recommended B on evidence-per-cost grounds; that recommendation is
recorded in *Pros and Cons* below and was **overruled deliberately**, because B buys its saving by
keeping a relation name that cannot honestly carry half of its own value range.

### The decisions this ADR takes

| # | Decision |
| --- | --- |
| **ADR-D1** | `impacts` is a signed numeric annotation on `DRGEdge` and **subsumes** `in_tension_with`. `impacts < 0` **is** a tension claim. |
| **ADR-D2** | ◆ **DECIDED: a new `Relation.IMPACTS` carries it.** Directed and signed. The relation type *is* `impacts`; the sign says how it affects the target. This is the programme-shape gate (≡ design D-2 / sequence gate G2) and it is now closed. |
| **ADR-D3** | **`impacts` is AUTHORED-ONLY. Never derived.** The moment anything derives it from value vectors the subsumption is unsound and this becomes the option the superseded ADR rejected. |
| **ADR-D4** | Candidate-pair predicate is `relation == impacts and impacts < 0` — **strict sign, no tunable threshold**. |
| **ADR-D5** | `reconciles_tension` **survives**, re-pointed at negative-`impacts` pairs. Its existing rule stands: a pair counts as resolved only when an active artefact carries the edge to **both** sides. |
| **ADR-D6** | `impacts` is meaningful on `impacts` / `rejects` / `refines` and **ignored elsewhere**. Stated as prose, deliberately **not** a `Relation`-keyed table — there is no totality guard for such a table, so it would rot silently the next time a relation is added. |
| **ADR-D7** | Composition is **first-order only**. The published second-order matrix is **rejected**: all **42 of 42** off-diagonal cells mismatch `M×M` under six derivation hypotheses, so it is independently-authored judgement rather than computed ripple and cannot inherit the first matrix's provenance. |
| **ADR-D8** | The matrix is **symmetric**, authored as N(N−1)/2 unique pairs. ◆ **CLOSED by amendment, 2026-07-26: the one asymmetric published pair is a sign error, repaired by symmetrising to `+0.75`.** See *Amendment (2026-07-26)* below, after *Migrates*. |
| **ADR-D9** | The computed projection is a **frozen dataclass with no `model_dump()`**, in a module no writer imports, stamped with `matrix_id` / `matrix_version`. |
| **ADR-D10** | The value set and matrix are **N-parameterised** (N ≥ 3); AMMERSE is the default basis only, and axis identity is by `id`. Boundedness follows from coefficients ∈ [−1,1] plus a zero diagonal (Gershgorin). The validator enforces exactly those two properties, **errors at gain ≥ 1−ε** (the series does not converge at the boundary) and **warns as gain → 1**, using a start-vector-independent method — plain power iteration is **fail-open** on two-camp bases. |

### ADR-D11 — `is_symmetric` on `DRGEdge`: shorthand for the un-written inverse

Because the two shipped claims are symmetric and the new relation is directed, this ADR settles
the migration semantics rather than leaving them to the implementer. An earlier revision required
symmetric tensions to be **authored** as two directed edges; the operator replaced that with a
generic model field, which is better on three counts recorded below.

**`DRGEdge` gains `is_symmetric: bool = False`.** Semantics:

* `source` / `target` keep their existing meaning. In an **asymmetric** relationship they carry the
  direction of effect; nothing about them changes.
* `is_symmetric: true` is **shorthand meaning "the inverse relationship holds too"** — it exists so
  an author does not have to write the inverse as a second explicit edge. It is *not* a storage
  convention and *not* a claim about `source`/`target` being interchangeable at the authoring layer.
* Genuine asymmetry is still expressible, unchanged: two directed edges with their own values, or
  one edge with `is_symmetric: false`.

**The expansion happens in the generator, never in traversal.** This is what makes the field
cheap and safe, and it falls directly out of the source-plus-cache architecture:

| Layer | Holds |
| --- | --- |
| **(a)** authored `<kind>.edges.yaml` | **one** edge carrying `is_symmetric: true` |
| **(b)** generated `*.graph.yaml` cache | **both** directions, materialised |

Consequently `edges_from` / `edges_to` stay **purely structural** — `source == urn` and
`target == urn` respectively — and every existing consumer sees an ordinary directed pair with no
change and no adoption work. This matters because symmetry currently lives in *caller discipline*:
those accessors special-case no relation, so `in_tension_with`'s bidirectionality today depends on
each consumer remembering to query both directions. Expanding in the generator removes that
obligation instead of generalising it, and closes the site class where a symmetric edge could
silently resolve one-way.

Two properties this design gets for free, both of which must be **asserted** rather than assumed:

1. **Expansion is idempotent.** Expanding `{A→B, sym}` yields `{A→B, B→A}`; expanding *that* set
   yields the same two edges, since each expands to itself plus an inverse already present and the
   duplicate-triple check dedupes. The cache-coherence assertion `merge(authored) == cache` depends
   on this holding.
2. **Double-authoring is already an error.** Authoring both the symmetric shorthand *and* an
   explicit inverse produces a duplicate `(source, target, relation)` triple after expansion, which
   `assert_valid` already rejects. **No new validator rule is required** — the existing duplicate
   check does the work, once expansion runs before validation.

Accepted consequences:

* The **authored** count for the two shipped claims stays **2**; the **cache** count goes 2 → 4.
  That is a ledgered delta against the golden counts, recorded on the cache side only.
* The canonical single-edge storage convention (lexicographically-smaller URN as source) retires
  with the boolean. Its *purpose* survives as declared data: symmetry is now a field, not a
  convention documented in a docstring and remembered at call sites.
* `reconciles_tension` already requires an edge to **both** sides of a pair, and the cache presents
  both, so its semantics carry over with no change.
* `is_symmetric` is generic on the base model, so a future symmetric relation inherits it rather
  than re-inventing the convention. Edge-level rather than relation-level is deliberate: `impacts`
  can legitimately be symmetric or asymmetric *per claim*, and ADR-D6 has already rejected
  `Relation`-keyed tables for lack of a totality guard.
* **C-009 binds this field like any other.** Model + `_edge_to_dict` writer + generator expansion +
  round-trip test + coverage gate land in **one commit**, or it joins the three arbitration slots
  that shipped green and inert.

### Retires

`in_tension_with` as a `Relation` member · the prior rejection of `Relation.IMPACTS` · the
`0.25 × second_order` term · the convergence caveat · the "no superseding ADR needed" claim.

### Migrates (in one commit each, per surface)

* The 2 authored edges at `directive.graph.yaml:90-93` and `:103-106` → directed `impacts` pairs,
  **preserving each `reason` verbatim**.
* The tension surface: 1 dataclass + 5 functions at `consistency_check.py:917-1050`.
* `RELATION_DESCRIPTIONS` plus verbatim doc parity.

### Amendment (2026-07-26) — ADR-D8 closed: the asymmetric pair is a sign error, repaired by symmetrising to `+0.75`

This ADR was Accepted with ADR-D8 open (see *Open Decisions* below, kept for record — this
amendment is recorded here rather than by silently rewriting that section, because this ADR, not a
spec table, is the citable record, DIRECTIVE_003). The operator has since adjudicated it.

1. **The asymmetry is an error, not an intentional directional claim.** The published AMMERSE
   first-order matrix has exactly one asymmetric pair out of 21 (47 of 49 cells satisfy the
   symmetry predicate): `maintainable → extensible = +0.75` against
   `extensible → maintainable = −0.75`. Every other authored pair in the matrix is symmetric, and
   the published second-order matrix — a derivative of the first, per its own methodology
   statement — is *fully* symmetric, which is inconsistent with an intentional asymmetric claim
   surviving into it.
2. **Repair: symmetrise to `+0.75` in both directions.** The substantive claim adopted is that
   **maintainability and extensibility reinforce each other** — a well-maintained system is easier
   to extend, and cleanly-factored extension points keep a system maintainable. The published
   `−0.75` cell is the errant one and is superseded by `+0.75`.
3. **The matrix is symmetric, authored as N(N−1)/2 unique pairs.** This half of ADR-D8 was already
   stated at first acceptance; it was blocked on this repair choice and is now unblocked.

**Measured consequence** (verified via `docs/plans/doctrine/_reproduce_matrix_findings.py`, reading
the committed, unmodified `_ammerse-connascence-first-order.json`):

| Reading | gain | residual |
| --- | --- | --- |
| as published (asymmetric) | 0.3892 | 4.70% |
| **symmetrised to `+0.75` — ADOPTED** | **0.3766** | **4.37%** |
| symmetrised to `−0.75` | 0.4337 | 6.00% |
| zeroed (abstain) | 0.3995 | 4.99% |

The headline truncation residual for the adopted two-term damped composition moves from **4.70% to
4.37%**; the per-step gain moves from **0.3892 to 0.3766**. The as-published figure is retained in
the row above — and in the design authority's own sensitivity table (§6.3) — rather than dropped,
because it remains the figure that was actually measured off the unrepaired matrix, and the in-repo
divergence record (see below) cites it as the baseline the repair moved away from.

**Basis of this adjudication — stated plainly, without hedging.** Two different authorships are in
play here (design authority §3): **the operator (Stijn Dejongh) authored the AMMERSE *analysis
procedure***, the in-repo tactic and the Pragmatic Penguin Patterns library it draws on; **J.B.
Crossland authored the AMMERSE *value system and its impact matrices***, the ideological root this
procedure builds on. The operator holds Crossland's prior written consent to use the AMMERSE idea
and to publish his own procedure under his own intellectual property; accreditation and mention
(§12) discharge that relationship in full. This repair is therefore **the operator's adjudication,
taken on his own authority over his own procedure** — not upstream authorial confirmation from
Crossland, and that distinction is worth keeping precise (it says whose judgement this is), but it
is not a provisional or pending call. It does not await, and is not conditioned on, any response
from Crossland.

**One thing this closure does not become a gate on, and one thing it is worth keeping for its own
sake:**

* There is **no outstanding report owed to Crossland** and no step of this amendment waits on one.
  An earlier draft of this ADR framed the eventual repair as something that "should not front-run"
  a conversation with the AMMERSE author (see *Open Decisions* below) — that reasoning is
  **superseded** by the operator's standing consent and is recorded here as history, not as a
  constraint that still binds.
* **An in-repo divergence record still earns its place, as provenance hygiene for our own matrix,
  not as an accreditation deliverable or a shipping gate.** Our matrix differs from the published
  one at exactly one cell; a future reader needs to know which cell and why, and a
  **`source_digest`** lets a later re-read detect if the upstream figures ever change. Recording it
  (mismatch counts, the `accessed_on` URL, both this finding and the false `M×M`
  second-order-derivation claim, ADR-D7) is good engineering practice for the mission that ships the
  matrix, `foundational-values-creed-band-01KYFV8N` — not a precondition owed to anyone outside the
  repository.

The two evidence JSON files this amendment reasons over —
`docs/plans/doctrine/_ammerse-connascence-first-order.json` and
`docs/plans/doctrine/_ammerse-second-order.json` — are the published upstream data and stay
byte-identical; the repair is layered on consumption (the value-set artefact a later mission
authors), not a correction of the source data.

## Consequences

### Positive

* One relation owns "how do these two artefacts affect each other", with the sign carrying
  direction of effect. No boolean shadow of the same claim.
* The full range becomes authorable, including reinforcement, which `requires`/`suggests` can only
  approximate.
* Asymmetric tension becomes expressible for the first time.
* Clears G1 and G2, which the sequencing authority identifies as the cheapest gate to clear and
  the one unblocking the most downstream work.

### Negative

* **~45–60 files**, roughly 6× option B, rippling through the 50 files that touch the `Relation`
  vocabulary. Accepted knowingly.
* **The org→DRG bridge is currently leaking, and this ADR adds vocabulary to it.** Measured: a
  built-in-source → pack-target edge returns `None` with **no warning and no conflict record**; a
  bare built-in target id is blindly re-kinded to a node that may not exist; a URN-shaped target
  dies with a raw pydantic error rather than a typed pack error. **The bridge fix must land before
  or with the `Relation.IMPACTS` migration**, or the new relation inherits a silent-drop path.
* The positive half of the range has **no current author**. Nothing in the tree needs
  "A reinforces B" as a standalone relationship today, so that expressiveness is bought ahead of
  demand — a deliberate bet on the design's direction.
* Cache edge counts move (2 → 4 for the existing claims, via `is_symmetric` expansion), so every
  golden-count baseline and its composition ledger must be updated in step. The authored count is
  unchanged at 2.
* `is_symmetric` is a new field on a model with **no `model_config`**, so it is inert unless the
  writer, the generator expansion, and a round-trip test land with it (ADR-D11, C-009).

### Neutral

* `rejects` and `refines` gain an optional `impacts` annotation without changing their meaning.
* The `applies` relation is untouched here. Note for anyone reading the surrounding code: the
  comment at `drg/merge.py:97-98` claiming no traversal reads `applies` is **wrong** —
  `charter_runtime/lint/checks/orphan.py` reads it and `charter/synthesizer/project_drg.py`
  produces it. Do not build an "`applies` is dead" gate on that comment.

## Open Decisions

**ADR-D8 is CLOSED — see *Amendment (2026-07-26)* above (after *Migrates*, before *Consequences*).**
Symmetrised to `+0.75`. The paragraphs below are kept as the historical record of why it was
originally left open at first acceptance, not as a live description of the current state.

At first acceptance, **ADR-D8's asymmetric pair was not decided here.** The published matrix has
exactly one asymmetric pair out of 21 — Maintainable ↔ Extensible at `+0.75` one way and `−0.75`
the other — and it was most likely an upstream sign error. It was **deliberately left open**
because:

1. the repair choice moves the headline truncation error between **4.37%** and **6.00%**, so it is
   a measurement input, not a formatting detail;
2. the validator could not be written until it was settled;
3. ~~the upstream report to the AMMERSE author is **operator-only and never agent-drafted**, and
   the adjudication should not front-run that conversation.~~ **Superseded by the Amendment above:**
   the operator holds Crossland's prior written consent for this procedure, so there is no
   conversation to front-run and no report the adjudication was waiting on. This reason no longer
   applies; it is struck through rather than deleted because it was the accepted reasoning at first
   acceptance.

The options considered were: symmetrise to `+0.75` (**chosen**, see the Amendment), symmetrise to
`−0.75`, or zero the pair. Both the measured asymmetry and the rejected `M×M` derivation claim
remain committed as JSON (`_ammerse-corpus-36-practices.json`, `_ammerse-second-order.json`),
byte-identical — retained as provenance for our own matrix, not as material for any outstanding
report.

The design authority's remaining open decisions (§13 D-1, D-3, D-4, D-5) are out of scope for this
ADR; D-6 was the same subject as ADR-D8 above and is closed alongside it.

## Confirmation

* `Relation.IMPACTS` exists; `in_tension_with` has **zero** members and zero references outside
  historical records; `git grep` for it returns only this ADR, the superseded one, and changelog
  entries.
* The 2 shipped tension claims are **authored as 2** edges carrying `is_symmetric: true`, and
  **expand to 4** directed edges in the generated cache, with each original `reason` text
  byte-identical. The golden-count ledger carries an entry explaining the cache-side `2 → 4`.
* Expansion is idempotent — regenerating an already-expanded cache is a zero diff — and authoring
  both the shorthand and an explicit inverse fails `assert_valid` on the duplicate triple.
* `edges_from` / `edges_to` remain purely structural: a test asserts neither special-cases
  `is_symmetric`, so the expansion obligation cannot quietly migrate into traversal.
* `reconciles_tension` still resolves both sides of each migrated pair.
* The validator errors at gain ≥ 1−ε and warns as gain → 1, proven by a two-camp basis fixture on
  which plain power iteration fails open.
* No derivation path writes `impacts` — asserted by a gate, not by inspection (ADR-D3).
* The org→DRG bridge no longer drops a cross-layer edge silently, verified before the migration
  lands.

## Pros and Cons of the Options

### Option A — new `Relation.IMPACTS` (chosen)

**Pros:** honest directed semantics; the full signed range in one concept; the boolean genuinely
disappears rather than being shadowed; asymmetric tension becomes expressible; matches the design
authority's recommendation.
**Cons:** ~45–60 files; forces the two symmetric claims into directed pairs and retires their
canonical-storage guarantee; adds vocabulary to a bridge with a known silent-drop defect; buys
positive-half expressiveness that nothing currently authors.

### Option B — keep `in_tension_with`, add the magnitude to it

**Pros:** ~5–10 files; preserves the symmetry the two real edges actually have; delivers the only
thing measurably missing today, which is magnitude on an existing conflict claim; aligns with the
design's own finding that the sign channel is noisy and the rationale is what carries weight.
**Cons — and these decided it:** a relation named `in_tension_with` cannot coherently carry
`impacts: +0.5`, so half the range becomes unauthorable and the name lies about its own contents.
ADR-D4's predicate collapses to "is this a tension edge", because the relation already says so —
making the sign redundant with the relation. And "subsumes" would be the wrong word: this is
annotation, not subsumption. **Recommended by the reviewing analysis on evidence-per-cost;
overruled deliberately by the operator in favour of the clean end state.**

### Option C — `Relation.IMPACTS` but symmetric

**Pros:** honest name and full range without doubling the existing edges; keeps the canonical
single-edge storage.
**Cons:** pays option A's full ~45–60 file cost while giving up the directionality that motivates
a signed *directed* strength, and would require amending the design authority's plane-2
definition. Worst of both on cost-versus-fidelity.

### Option D — keep both the boolean and the signed field

**Pros:** no migration at all.
**Cons:** two authorities for one claim, which is precisely what the sibling ADR 2026-07-26-1 has
just spent a mission removing on the adjacent axis. Rejected on principle.

## More Information

* Design authority: [`foundational-values-and-creed.md`](../../plans/doctrine/foundational-values-and-creed.md)
  (§6 maths, §11 contradiction register, §13 open decisions).
* Sequencing authority: [`manifesto-program-delivery-sequence.md`](../../plans/doctrine/manifesto-program-delivery-sequence.md)
  (critical path, 22 ranked increments, park register).
* Verification round: [`squad-reports/review-round-2026-07-26.md`](../../plans/doctrine/squad-reports/review-round-2026-07-26.md)
  — the 26-item fix ledger these authorities are post-fix against.
* Reproduction: `docs/plans/doctrine/_reproduce_matrix_findings.py` (standard library only).
* Sibling axis: [ADR 2026-07-26-1](2026-07-26-1-drg-edges-are-the-canonical-relationship-authority.md)
  (DRG edges are the canonical relationship authority) and
  [ADR 2026-07-26-2](2026-07-26-2-doctrine-artefact-pack-layout-convention.md) (pack layout).
* Rejected with measurements, recorded so they are not rebuilt: vector-derived precedence
  orderings (0 successes in 6 attempts), sign-opposition tension derivation (5/5 false positives),
  creed-weighted ranking as a recommender (collapses to row-sum, r ≈ 0.98).
