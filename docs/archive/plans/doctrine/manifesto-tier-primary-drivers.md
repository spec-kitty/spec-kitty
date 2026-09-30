---
title: The Manifesto Tier — doctrine's missing primary-driver layer
description: "Meta-analysis: doctrine implements only the middle tier of a three-tier sense-making model. AMMERSE is in-repo but mis-tiered as a tactic. Proposes a manifesto tier."
doc_status: deprecated
updated: '2026-07-26'
related:
- docs/plans/doctrine/index.md
- docs/plans/doctrine/org-doctrine-layer-architecture-review.md
- docs/plans/doctrine/layered-doctrine-resolution-design.md
---
# The Manifesto Tier — doctrine's missing primary-driver layer

> **Retired (deprecated).** Superseded by the canonical creed AUTHORITY doc [foundational-values-and-creed.md](../../../plans/doctrine/foundational-values-and-creed.md). Preserved as a historical record.

**Date:** 2026-07-26
**Status:** ⚠️ **SUPERSEDED IN PART — the proposed mechanism is REJECTED.** Two adversarial
squads (8 profile-loaded agents) ran against this document on 2026-07-26. The **diagnosis
survives and was sharpened**; the **mechanism (§4c, §7.2–§7.4, §6) is dead**, killed by an
experiment this document itself nominated as its falsification condition. Read
[`manifesto-tier-verdict-and-handover.md`](manifesto-tier-verdict-and-handover.md) **first** —
it carries the verdict, the corrected facts, and the actionable sequence. Sections below
marked ❌ are retained as the record of the investigation, not as proposals.
**Known factual errors in this document are listed in the handover, §"Corrections".**
**Scope:** meta-level. Read-only investigation of the doctrine tier model, run as a
complementary lens alongside the grounded architectural work on
`fix/2934-demock-planning-closeout-test`.
**Sequencing:** steps 2–5 of §7 target the **3.3.x doctrine-extensibility / packs**
band. Step 1 is available immediately.

---

## Summary

Doctrine has no tier for **values**. Every value-shaped artifact is therefore filed
under the nearest available kind — a technique, a rule, or a methodology label. The
consequence is architectural, not cosmetic: doctrine resolves to an **unordered bag
of co-valid rules**, so when two of them conflict the arbiter is whatever prior the
consuming model brings. For current-generation LLMs that prior is *deliver output
now*. **The system delegates its value arbitration by omission.**

Three findings make this concrete and actionable:

1. The omission is **inherited and was deliberate upstream** — doctrine was imported
   from a knowledge base that explicitly scoped itself to the middle tier of a
   three-tier model and excluded values by design (§2). Correct for a human
   audience; impossible for an agent.
2. **AMMERSE is already in the repository**, canonically defined, and completely
   inert — mis-tiered as an optional tactic with its value definitions buried in
   step-2 prose (§3).
3. A manifesto tier does not merely document values; it makes **tension derivable
   instead of declared**, turning O(N²) hand-authored reconciliations into O(N)
   one-time scorings (§4).

---

## 1. The slot is already declared, and it is empty

`src/doctrine/README.md` documents the tier table:

| Artifact kind | What it defines |
| --- | --- |
| **Paradigm** | *Worldview-level framing (e.g. test-first, DDD)* |

But `schemas/paradigm.schema.yaml` has four meaningful fields — `id`, `name`,
`summary`, `directive_refs` — and all 14 instances are **named methodologies**, not
worldviews:

```yaml
# paradigms/test-first.paradigm.yaml — the entire artifact
id: test-first
name: Test-First Doctrine
summary: Prefer acceptance-first and red-green-refactor loops for
         deterministic delivery quality.
```

`domain-driven-design`, `trunk-based`, `atomic-design`, `execution-lanes`,
`shared-branch-ci` — all techniques. A paradigm says *which school of practice we
follow*. None says what we are for, what we would trade away, or over what horizon
we are judged.

### Three mis-tierings, one root cause

| What it actually is | Where it currently lives | Consequence |
| --- | --- | --- |
| A 7-dimensional **value basis** | `tactic:ammerse-impact-analysis`, step-2 prose | Discretionary ritual; inert on the graph |
| A **precedence ordering** | `directive:RECONCILE_CHANGE_SCOPE_TENSIONS` | Bespoke per triple; ID breaks the directive contract |
| **Worldview framing** | The `paradigm` README row | Slot declared, filled with methodologies |

The precedence case is worth reading directly.
`directives/built-in/reconcile-change-scope-tensions.directive.yaml` exists solely
to arbitrate DIRECTIVE_024 (Locality of Change), DIRECTIVE_025 (Boy Scout Rule), and
`tactic:change-apply-smallest-viable-diff`:

> "When the three pull in different directions on a specific change, **resolve in
> this order**: smallest-viable-diff picks the file set and edit size first; Boy
> Scout Rule then governs cleanup strictly inside that file set; Locality of Change
> is the brake…"

That is a precedence ordering over commitments, authored as a *procedure step*
inside a *rule*. Two tells that the type did not fit: its ID breaks
`^DIRECTIVE_\d{3}$`, and it is **bespoke per tension-triple** — there is no general
ordering to derive it from, and nothing that would catch a second reconciliation
directive encoding a contradictory ordering.

---

## 2. The omission is inherited and was deliberate

`patterns.sddevelopment.be/about` declares a **sense-making meta model** in three
tiers:

| Tier | Contents | Mutability |
| --- | --- | --- |
| **Primary drivers** | Values, axioms, current context | *immutable* |
| **Secondary elements** | **Creeds and behaviors** | *malleable* |
| **Outcomes** | Effects resulting from behaviors | — |

And it states its own scope explicitly:

> This knowledge base explicitly targets **"creeds and behaviors"** — how
> practitioners act. It **deliberately excludes primary drivers** (values,
> fundamental laws), directing readers elsewhere for philosophical foundations.

Spec Kitty's doctrine was imported from that catalog — a dozen artifacts carry
*"Adapted from patterns.sddevelopment.be"*, and AMMERSE came across with them. **So
doctrine inherited the exclusion along with the content.**

This is why the gap exists and why nobody noticed. It was never an oversight. It was
a **correct scope decision for a human-audience knowledge base** whose stated mission
is to *"help you build judgement"* rather than prescribe — so it can reasonably tell
a practitioner to bring their own values.

That instruction is coherent for a human reader and **impossible for an agent.** An
LLM has no values of its own to bring; it has a training prior. "Go elsewhere for
your philosophical foundations" resolves, for an agent, to "use the default
weighting" — which §5 shows is Reachable/Solvable-maximal. A deliberate boundary in
the source became a silent defect in the consumer.

### Doctrine implements only the middle tier — both ends are missing

A vocabulary census across all doctrine YAML (excluding generated graphs):

| Term | Hits |
| --- | --- |
| `output` | **168** |
| `outcome` | 49 — *every one* means BDD "observable outcome" of a test/step |
| `stewardship` | 4 |
| `horizon` | **1** — and it is *"horizontal* scale" |
| `long-term` / `long term` | **0** |
| `trade-off` / `tradeoff` | **0** |

The meta model's third tier is literally *"effects resulting from behaviors"*, and
doctrine has no vocabulary for it. So the value gap and the temporal gap are one
shape: **doctrine is a faithful port of "creeds and behaviors", with the primary
drivers above it and the outcomes below it both absent.** An agent needs both ends —
the primary drivers to arbitrate *with*, and the outcomes tier to have anything
beyond the current turn to optimise *toward*.

A corpus that cannot say `trade-off` cannot arbitrate one.

---

## 3. AMMERSE is already in the repository, mis-tiered and inert

`src/doctrine/tactics/built-in/analysis/ammerse-impact-analysis.tactic.yaml`

The seven canonical value definitions — the arbitration basis the entire doctrine
graph needs — currently live **inside the `description` prose of step 2 of a
tactic**:

```yaml
  - title: Assign base impact scores per AMMERSE value
    description: >
      Canonical AMMERSE value definitions (use these verbatim as the scoring lens):
      Agile (A): The ability to adapt quickly to changes…
      Minimal (Mi): The focus on simplicity…
      …
```

And it is gated to discretionary use:

> "**Reserve** the full numeric interaction-matrix analysis for high-stakes
> decisions" · "**Skip this step** for low- and medium-risk decisions"

Reachability is two edges: `procedure:situational-assessment` (`requires`) and
`tactic:reference-architectural-patterns` (`suggests`, *"for high-stakes
decisions"*). **No artifact in the corpus carries an AMMERSE score.** The words
"maintainable" / "extensible" appear elsewhere only as English adjectives.

So the value system is **present, canonically defined, and completely inert** — a
ritual that may optionally be performed on one decision, with zero purchase on the
graph that governs every decision.

---

## 4. Why a manifesto solves precedence, and better than a ranked list

The Agile Manifesto's grammar is **"we value A over B — while there is value in
B."** A preference relation *with acknowledged cost*. AMMERSE generalises it, and
improves on a ranked list in three ways:

**(a) It is a basis, not a total order.** An artifact's position is a **vector in 7
fixed dimensions**, not a rank. This answers the obvious objection to a global
ordering — that real engineering trade-offs are not totally ordered. Tensions stay
local to a decision-class.

**(b) Cost is structural, not narrative.** A negative component *is* the
acknowledged cost. A manifesto cannot be authored as a slogan, because a
value-vector with no negative components is visibly a lie. Shape enforces what a
prose convention could not.

**(c) Tension becomes DERIVABLE instead of DECLARED.** This is the architectural
payoff:

> Two artifacts are in tension wherever their impact vectors carry **opposite signs
> on the same value**.

Authoring cost drops from *O(N²) hand-authored pairs* to *O(N) one-time scorings* —
and, far more importantly, it surfaces the tensions **nobody noticed**. The corpus
today has **2** `in_tension_with` edges across ~200 artifacts; the unnoticed
conflicts are the whole problem, and per-pair authoring can only ever record
conflicts someone already spotted.

Checked against the one real example in the corpus:

- `DIRECTIVE_024` Locality of Change → Minimal **+**, Reachable **+**, Extensible **−**
- `DIRECTIVE_025` Boy Scout Rule → Maintainable **+**, Minimal **−**, Reachable **−**

Opposite signs on Minimal and Reachable. The tension that required a hand-authored
`in_tension_with` edge *plus* a bespoke reconciliation directive **falls out of the
vectors**. AMMERSE's own first-order matrix already encodes the structural reason:
Minimal→Extensible is −0.75, Extensible→Reachable is −0.75.

Reconciliation then derives from the project's declared **weighting** of the basis
rather than being authored per pair. `RECONCILE_CHANGE_SCOPE_TENSIONS` stops being a
bespoke node and becomes a **worked example** of a general rule — which is also the
honest test of this design: *if the manifesto cannot reproduce that directive's
stated ordering, the manifesto is wrong.*

---

## 5. The payoff: the output-bias gets an exact name

"Current-generation LLMs optimise output over outcomes" is a true but unactionable
intuition. In the AMMERSE basis it becomes a **specific point in value space**:

| Value | LLM default weight | Why |
| --- | --- | --- |
| **Reachable** | maximal | Achievable *now*, within the turn's constraints |
| **Solvable** | maximal | Address the problem in front of me |
| **Maintainable** | ~0 | Consequences land after the turn ends |
| **Extensible** | ~0 | Same — no future to optimise for |
| **Minimal** | ambiguous | Favours a locally-small diff, tolerates a globally-duplicated seam |
| **Environmental** | unweighted | No standing in the objective |
| **Agile** | *apparently* high, actually low | Optimises the current turn, not adaptability across turns |

This is no longer a vague bias but a nameable, correctable **weighting defect**. And
AMMERSE's own matrix *predicts* the failure rather than merely describing it:
**Reachable is negatively impacted by Extensible (−0.75)**, so a
Reachable-maximising agent will structurally sacrifice extensibility. Not a quirk —
a consequence.

Re-read the charter's nine Quality & Tech-Debt Standing Orders in this light: every
one is a patch on a **Maintainable / Extensible deficit**. Their own stated
throughline — *"never trust a green check, a clean diff, or a confident summary"* —
is nine symptom-patches for one weighting defect, which is why the list keeps
growing. Adding more rules cannot fix this: every rule enlarges the bag and makes
the implicit arbitration *more* load-bearing.

Two things follow immediately:

1. **Deviation becomes measurable.** A repository manifesto declaring
   `Maintainable > Reachable` for a decision-class makes "this diff scores Reachable
   +0.8 / Maintainable −0.7" a *statable* observation instead of a reviewer's hunch.
2. **The licensed non-delivery move gets a reason.** Today every profile's
   `avoidance-boundary` is a *scope* limit ("not my job"), never a *stop* condition.
   All 18 built-in `initialization-declaration`s are first-person job descriptions
   ("I am X. I do A, B, C. I do not do D"), so the only licensed outcome of an
   invocation is a deliverable — and the agent duly delivers one. In the basis the
   stop condition is expressible: *escalate rather than deliver when the
   deliverable's vector opposes the manifesto weighting beyond a threshold.*

---

## 6. The three scopes have precise meaning

- **Organizational manifesto** — the *weighting* over the basis: what this
  organization trades for what. AMMERSE's "context", made durable.
- **Repository manifesto** — weighting plus the **horizon** it is judged over; may
  override org weighting per decision-class. This is also where the missing temporal
  vocabulary (§2) enters the system.
- **Agent profile manifesto** — the profile's *characteristic value bias*. This is
  literally "who am I and how do I see the world?", as a vector.

The profile case has an immediate practical dividend: **squad composition becomes
computable.**

- Renata: Maintainable **+**, Solvable **+**, Reachable **−**
- Priti: Reachable **+**, Agile **+**, Extensible **−**
- Paula: Extensible **+**, Minimal **+**, Reachable **−**

Adversarial-squad lens selection is judgement today ("profile-by-lens", left to
taste). With vectors a squad can be checked for **coverage gaps** — if no member
weights Environmental, that lens is structurally absent — and for **redundancy**, if
two members' vectors are near-collinear. That is the first concrete thing the tier
buys that nothing else does.

---

## 7. Proposal

Sequenced so each step is independently valuable.

1. **Re-tier AMMERSE (pure refactor, no new kind — do this first).** Lift the seven
   canonical definitions out of the tactic's step-2 prose into a first-class,
   queryable basis. The tactic **remains**, as the *procedure for scoring against*
   the basis. That is the correct split: basis = declarative value tier; scoring
   ritual = tactic. Nothing is lost and the mis-tiering is corrected. Correct the
   `paradigm` README row to "named methodology" in the same pass.
2. **A `manifesto` node kind, three scopes** (§6), holding the weighting over the
   basis, the horizon, and the observable signals that the manifesto is being
   violated.
3. **Optional `value_impact` vector on directives / tactics / styleguides.** Author
   incrementally — the graph must work partially scored, so score the artifacts that
   appear in known tensions and on hot paths first.
4. **Derive `in_tension_with` from opposing signs**, keeping hand-authored edges as
   explicit overrides. Add a validator that flags a reconciliation whose ordering
   contradicts the declared weighting — the consistency check that is impossible
   today.
5. **Profile `worldview.value_bias` + `escalates_rather_than_delivers`**, the latter
   expressed as a threshold in the basis (§5.2).

**Naming.** Use **`manifesto`** — it carries the Agile Manifesto lineage, says
*statement of what we value*, and maps onto the meta model's **primary-driver**
tier. Do **not** overload `paradigm`: that repeats the `primary`/`merge` footgun
exactly (one token, two installed senses, 14 instances, live DRG edges). Do **not**
use `creed`: in the source meta model that word names the *secondary* tier doctrine
already implements.

**A sixth item, deferred but named.** §2 shows the **outcomes** tier is missing too.
A manifesto gives an agent something to arbitrate *with*; an outcomes tier gives it
something to optimise *toward*. It needs its own analysis, and the value tier is its
prerequisite — you cannot judge an effect without a value to judge it against. On the
record here so it is not rediscovered later.

---

## 8. Risks, and one non-negotiable

**The non-negotiable.** The existing AMMERSE tactic says its numbers are *"informed
guessing"* and *"conversation prompts, not deterministic verdicts"*, and that inputs
*"reflect the assessor's current mental model, not ground truth."* That caution
**must survive the port.** If manifesto scores become a gate that auto-decides, this
fails as precision theater and deserves to. The manifesto's job is to make the trade
**explicit** and the deviation **visible**, and to demand a rationale — never to
compute the answer.

Remaining risks:

1. **Scoring burden.** N artifacts × 7 values is real cost, and a half-scored graph
   yields half-derived tensions. Partial population must be a first-class state,
   never an error; score tension-participants and hot paths first.
2. **Basis lock-in.** Seven values is someone's ontology. If an organization needs an
   eighth, the basis must extend — it should be pack-overridable, which is precisely
   why this belongs with the pack work. (Pleasing recursion: the basis itself should
   score well on **Extensible**.)
3. **Second-order matrices are the weakest thing to port.** Those coefficients are
   calibrated judgement, not measurement. Port **first-order only** to start; the
   standard path in the existing tactic is already first-order.
4. **Derived tension could be noisy.** Opposite-sign-on-same-value will produce false
   positives on artifacts that are merely unrelated. It needs a magnitude threshold
   and probably a decision-class scope, or reviewers will learn to ignore it.
5. **Vector-washing.** An agent asked to score its own output against the basis will
   score it favourably, for exactly the Reachable-maximising reason in §5. A
   deliverable's score cannot be self-attested by the profile that produced it.
6. **Additive-only failure.** A tier at the top of an already-large bag only helps if
   it **replaces** injected prose with an ordering. If it is purely additive it makes
   the context problem worse, not better.

---

## 9. Framing note for whoever specs this

§2 establishes that the primary-driver tier was *deliberately out of scope upstream*,
for a human audience. That makes this a **scope extension, not a bug fix** — Spec
Kitty is consuming a knowledge base outside the audience it was scoped for. Framing
it as an inherited defect would be unfair to the source and would also understate the
work: **the tier has to be authored, not ported**, because the upstream catalog
deliberately never wrote it down.

---

## Provenance

- Prior art: [AMMERSE Impact Analysis](https://patterns.sddevelopment.be/practices/ammerse_impact_analysis/)
  — the seven values, the −1..+1 scale, and the first/second-order interaction matrices.
- Prior art: [Pragmatic Penguin Patterns — About](https://patterns.sddevelopment.be/about/)
  — the three-tier sense-making meta model and its stated scope exclusion (§2).
- Secondary: [Structured Knowledge Sharing](https://patterns.sddevelopment.be/practices/structured_knowledge_sharing/).
- In-repo evidence: `src/doctrine/README.md` (tier table),
  `src/doctrine/schemas/paradigm.schema.yaml`,
  `src/doctrine/tactics/built-in/analysis/ammerse-impact-analysis.tactic.yaml`,
  `src/doctrine/directives/built-in/reconcile-change-scope-tensions.directive.yaml`,
  `src/doctrine/drg/models.py` (relation vocabulary),
  `src/doctrine/drg/query.py` (`resolve_transitive_refs` — the unordered bag),
  `src/doctrine/agent_profiles/built-in/*.agent.yaml`,
  `.kittify/charter/charter.md` (Standing Orders).

## See also

- [Doctrine plans index](../../../plans/doctrine/index.md)
- [Org Doctrine Layer — Post-Implementation Architecture Review](../../../plans/doctrine/org-doctrine-layer-architecture-review.md)
- [Layered Doctrine Resolution — Design Blueprint](../../../plans/doctrine/layered-doctrine-resolution-design.md)
