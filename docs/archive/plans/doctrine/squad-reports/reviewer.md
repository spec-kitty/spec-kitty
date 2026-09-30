---
title: Reviewer lens — adversarial pass and the 39% verdict
description: "Adversarial review of the creed design: the sign channel is measurably noisy, five of seven axes carry no cost signal, and creed-weighted ranking collapses to magnitude."
doc_status: deprecated
updated: '2026-07-26'
related:
- docs/archive/plans/doctrine/creed-and-values-design-hardened.md
- docs/archive/plans/doctrine/creed-and-values-design-as-proposed.md
---
# Reviewer lens — adversarial pass and the 39% verdict

> **Retired (deprecated).** Superseded by the canonical creed AUTHORITY doc [foundational-values-and-creed.md](../../../../plans/doctrine/foundational-values-and-creed.md). Preserved as a historical record.

> ⚠️ **EVIDENCE — figures here predate the authority.** "The 39% verdict" is canonically **35% (12/34)**;
> "five of seven axes carry no cost signal" is canonically **two never-negative, six with ≤3 negatives**.
> Authority: [`foundational-values-and-creed.md`](../../../../plans/doctrine/foundational-values-and-creed.md) §11.
>
> Squad report, 2026-07-26. Profile-loaded (`reviewer-renata`), read-only. Evidence base for
> [`creed-and-values-design-hardened.md`](../creed-and-values-design-hardened.md).
> Tactics applied: `reverse-speccing` (the load-bearing one — reconstruct the intended semantics
> of the `ammerse` field from the corpus alone, then compare against the design's stated
> invariants), `code-review-incremental`; DIRECTIVE_041 generalized from tests to schema slots
> (a gate that passes for the wrong reason), DIRECTIVE_030, DIRECTIVE_024, DIRECTIVE_032.
> All corpus files fetched read-only; all statistics recomputed independently.

## Findings

**[CRITICAL]** `:113` — *"Every number is paired 1:1 with its rationale sentence — co-location is
already the invariant."* **Falsified by the corpus.** Of the 14 files fetched,
`the_point_of_dissent.md` carries 7 deltas and **zero** `rationale` keys;
`quad_A_test_structure.md` carries 7 deltas and **zero** `rationale` keys; `TEMPLATE_PRACTICE.md`
carries 7 empty-string rationales. Co-location is a convention with ≥3/38 violations, not an
invariant. This directly undercuts §6's row "Ungrounded scores are unfalsifiable → Addressed":
the corpus offered as proof the pairing works contains the exact unpaired case.
→ Stop citing co-location as established practice. If rationale is mandatory it is a **new**
constraint the calibration corpus fails, needing the same advisory-vs-hard decision §5.6 demands
for negatives.

**[CRITICAL]** `:189-192` — **The 39% figure is contaminated and is the wrong quantity.** Two of
the 14 named all-non-negative vectors are not authored artefacts: `TEMPLATE_PRACTICE` is the
literal authoring template (all-zero, empty rationales) and `quad_A_test_structure` is an unfilled
stub (all-zero, no `rationale` keys). Honest denominator 34, numerator 12 → **35%** — and both
stub rows sit inside the n=36 PCA of §5.3 and the means of §5.4.
→ Republish §5.2/§5.3/§5.4/§5.6 at n=34 with the stub-exclusion rule stated. I re-ran it: **the
conclusions survive** (PCA cumulative 0.816 at PC4; per-axis signs unchanged), so this costs the
argument nothing and removes an easy shot.

**[CRITICAL]** `:150, :164-168` — *"two axes carry no cost information"* **materially
understates** the measured result. Negative-cell census (n=36): agile 2, minimal **19**,
maintainable 3, environmental **0**, reachable 2, solvable **0**, extensible 1. Total **27 of 252
cells (10.7%)**, and `minimal` alone carries **19 of 27 (70%)**. **Five** of seven axes have ≤3
negative cells.
→ Restate as **"one cost axis and six benefit axes."** It changes what a creed weighting can
mean, and it is the honest reading of the design's own data.

**[CRITICAL]** `:68` — **Part 3's retrieval degenerates to a magnitude ranking at any plausible
creed.** Because six of seven axes are near-monotonically positive, a weighted sum is dominated by
row magnitude. Measured (34 authored vectors, Dirichlet creeds on the positive simplex, Spearman
vs the **unweighted row mean**, top-5 overlap vs the flat-creed top-5):

| Concentration | Spearman r | Same top-5 |
| --- | --- | --- |
| near-flat (α=50) | **0.980** | **97%** |
| mild tilt (α=20) | 0.958 | 90% |
| moderate (α=8) | 0.913 | 81% |
| opinionated (α=3) | 0.825 | 67% |
| uniform (α=1) | 0.671 | 48% |
| extreme (α=0.3) | 0.486 | 34% |

The flat-creed top-5 is `external-memory, efficient_async_communication,
define_test_boundaries, do_the_important_things, easy_to_change` — **exactly the five largest
row-sums**. `external-memory` (largest sum, +3.50) appears in the top-5 for **53% of all creeds**.
→ Before building this, specify the ranking function and state the null model. If the answer is a
linear dot product, gate it on *"top-5 must differ from the flat-creed top-5 by ≥2 items"*, or it
is measuring authorial enthusiasm and labelling it the operator's values.

**[MAJOR]** `:68` — **The creed score carries no query term, so it is not retrieval.** It imposes
one global preference order over the whole corpus regardless of what the operator is doing: the
flat-creed top hit for *any* question, including a testing question, is `external-memory`. Any
usable system must combine it with a topical filter and the design does not say how. Worse, the
topical filter selects a small, topically-coherent candidate set whose vectors are **more**
similar to each other than the corpus average (the design's own maintainable × extensible
r = +0.41), so the creed's discriminating power falls exactly where it gets used. *(Last step is
reasoning, not measured.)*

**[MAJOR]** `:206` — **§6's answer to the 3-for-3 decay precedent is a category error.** "Part 3
(the interview) *is* the producer" is true for the creed (7 weights + 7 rationales = 14 cells). It
is false for everything else. Measured in this repo: **260** behavioural doctrine artefacts (27
directive, 126 tactic, 21 styleguide, 14 toolguide, 14 paradigm, 22 procedure, 18 agent, 17
step-contract, 1 glossary-pack) × 7 axes × (delta + rationale) = **1,820 authored cells**; **774**
DRG edges across 9 populated graph files × 1 `impacts` value; plus a 7×7 matrix ≈ **2,650 cells**.
**The named producer covers ~0.5% of the register it is offered as the answer for.**

**[MAJOR]** `:56-60` — **Part 2 and the ValueConnascence matrix have ZERO grounding in §5.** §5 is
titled "Verified grounding measured against this design" and every measurement in it concerns the
artefact→value delta field. Nothing in the 36-vector corpus calibrates an edge strength or an
inter-value coefficient, and **774 edges is 23× the entire calibration set**. §6 row 11 concedes
*availability* of the first-order matrix but not *calibration*.
→ Split the document. Inheriting §5's credibility across the section boundary is the main
rhetorical risk here.

**[MAJOR]** `:63` — **The interview's elicitation format is delegated to the model, and the
design's own provenance chain says format inverts the answer.** The handover records prior art in
which a declared value ordering moved revealed model priorities by 0.145 normalized, *"with
rankings inverting between elicitation formats."* Part 3 makes format a free model choice — putting
the operator's value ranking under the control of the single variable prior art says inverts it.
→ Fix the instrument: authored question bank, constant-sum or forced pairwise comparison (never
independent Likert over seven virtues), and per-weight provenance
(`source: operator | model-proposed | default`).

**[MODERATE]** `:32-52` — **The design retires nothing.** Part 2 says `impacts` is added "rather
than the black-or-white absolutist `in_tension_with`" but the verb is *added*, and §6 row 2
explicitly preserves authored edges. Verified: `in_tension_with` is still 2 edges
(`src/doctrine/directive.graph.yaml:92, :105`) and is the subject of an **Accepted** ADR this
document does not propose superseding. **Net: +5 registers, −0.**

**[MODERATE]** `:45-49` — **By the calibration corpus's own scoring, adopting this design's
central practice costs `minimal −0.6` and `agile −0.35`.** `AMMERSE_impact_analysis`'s authored
vector: minimal **−0.6** ("introduces significant complexity and effort, conflicting with
minimalism"), agile **−0.35** ("time-consuming and may hinder agility… The potential indirect
support for better decisions is not enough to offset this"). `minimal` is the design's own single
live discriminator.
→ Put that vector in the document as the design's self-assessment. It is the most credible thing
available and it is free — the corpus already authored it.

**[MODERATE]** Nothing in the design detects the defect the corpus actually has. A
**sign-vs-rationale-polarity lint** — flag any cell whose rationale names only a cost while
`delta ≥ 0` — is the single highest-value gate here, is mechanically checkable by an LLM on the
prose the design already mandates, and exists in no part. **Make it Part 0.** It is the only
proposed component with a demonstrated defect population to validate against.

**[MINOR]** `:110` — `"0.125"`, `"0"`, `"1"`, `"-0.25"` all appear. The string/number coercion
boundary and the `"0"` vs `""` vs absent-key distinction need a stated rule — and per §5.6 that
rule decides whether `the_point_of_dissent` is "complete."

**[MINOR]** `:43, :49, :58, :65` — **Four vocabularies for arguably two concepts:** creed
"weighted score", artefact "delta", edge "impacts", interview "normalized score" (DIRECTIVE_032).
The `advisory` homonym warning is the precedent — resolve the vocabulary before rendering any of it
into agent context.

## The 39% verdict

**Neither (a) nor (b). The rule is right about the content and wrong about the instrument it
reads.** I read the rationale prose for 12 of the 14 named files plus 3 negative-carrying
controls.

**1. Two of the 14 are not authored artefacts.** `TEMPLATE_PRACTICE` is the authoring template —
all-zero, seven empty-string rationales. `quad_A_test_structure` is an unfilled stub — all-zero,
no `rationale` keys. Real population: **12 of 34 (35%)**.

**2. Eleven of the remaining twelve name an explicit cost in prose.** Not slogans, not costless:

| practice | axis | delta | rationale (verbatim excerpt) |
| --- | --- | --- | --- |
| `manual_of_me` | minimal | **+0.25** | "introduces documentation and cognitive overhead… it is **decidedly not minimal**" |
| `wipe_the_board` | maintainable | **0** | "the daily upkeep burden **limits long-term sustainability**" |
| `fail_fast` | maintainable | **+0.5** | "the overhead of maintaining complex validation rules can detract from this, leading to **potential long-term maintenance challenges**" |
| `fail_fast` | reachable | **0** | "the overhead… can slightly **detract from its effectiveness**" |
| `fail_fast` | agile | **+0.1** | "may introduce some rigidity… **can limit quick adaptability**" |
| `LARS` | minimal | **0** | "**may introduce complexity** in managing emotional aspects" |
| `wax_on_wax_off` | agile | **0** | "may introduce **slight rigidity**" |
| `external-memory` | minimal | **+0.75** | "there is a **risk of over-complicating** the external memory system" |
| `ten_minute_tasks` | minimal | **+0.25** | "**requires some preparation and planning** to be effective" |
| `define_test_boundaries` | minimal | **+0.2** | "moderated slightly by the **complexity introduced**" |
| `impact_oriented_communication` | reachable | **0** | "some **discomfort remains** for newcomers" |
| `communication_channel_compression` | extensible | **+0.1** | "**may need refinement** as organisations scale" |

**3. Exactly one is a true slogan** — `the_point_of_dissent`: seven bare numbers, no rationale
keys, `solvable = 1`, four axes at `0`. Un-examined by construction — and **the
mandatory-negative rule would not catch it either**, because a rule that reads signs cannot
detect an absent argument.

**4. The floor-clamping hypothesis is wrong, and the truth is worse.** Three negative-carrying
controls show competent net arithmetic: `AMMERSE_impact_analysis` extensible `0` = "supports
future extensibility **but may initially hinder it**" (a correctly netted zero); agile `−0.35` =
"the potential indirect support… **is not enough to offset this**"; `avoid_gold_plating`
extensible `−0.70`, maintainable `−0.25`. The scale is not clamped — 27 cells go negative.

What is actually happening is **sign inconsistency for equivalent prose across artefacts**:

- `manual_of_me` minimal = **+0.25** for "introduces documentation and cognitive overhead…
  decidedly not minimal"
- `AMMERSE_impact_analysis` minimal = **−0.60** for "introduces significant complexity and effort,
  conflicting with minimalism"

Near-identical claims, **0.85 apart, opposite signs.** And:

- `fail_fast` maintainable = **+0.50** for "overhead… leading to potential long-term maintenance
  challenges"
- `safe_to_fail` maintainable = **−0.15** for the *milder* "minor impact… does not significantly
  contribute"

A 0.65 swing in the opposite direction from the prose.

**Therefore:** the 35% is not a measurement of authorial honesty. It is a measurement of **noise
in the sign channel** — the one field the mandatory-negative rule reads. Eleven of twelve authors
*did* the honest analysis; the number failed to record it.

**And this is the finding §5.3 stopped one step short of.** The design used the real corpus to
refute the earlier squad's *dimensionality* claim, correctly. It did not check whether the earlier
squad's *other* measurement — a Solvable sign flipping between the same agent's two passes an hour
apart — also replicates. **It replicates, in the human-authored corpus.** The rebuttal is
selective: one finding was tested and refuted, the adjacent one was not tested and survives.

**Recommended decisions:**

1. `minItems: 1 negative` should be **rejected as a hard schema constraint** — not because 35% of
   the corpus is slogans (it is 3%), but because it gates on the least reliable field and would
   reject eleven honestly-analysed practices while **passing** the only real offender.
2. The constraint belongs **on the prose**: every rationale must name what adopting this makes
   worse. Eleven of twelve already comply; `the_point_of_dissent` and `quad_A_test_structure`
   fail, correctly.
3. Ship the **sign-vs-prose-polarity lint** instead, validated against the twelve rows above —
   the only component of this design with a falsification set available today.

## Fakeable-success register

| Part | The fake success | Why it passes review | Detector that must ship in the same commit |
| --- | --- | --- | --- |
| **P1a** `FoundationalValues` type | Pydantic round-trips; enum half-open; tests green | This is `Directive.severity` verbatim — green for 162 days proving round-trips | A test that fails when zero readers exist. Assert an importer outside `src/doctrine/` consumes it |
| **P1b** `creed` on charter | `creed.yaml` exists with 7 weights + 7 rationales; operator recognizes their words | Authored once at charter time, never revisited; nothing re-opens it | (i) A creed whose max−min weight spread is below a floor is the flat creed → warn; (ii) log every read and assert non-zero reads per mission |
| **P1c** per-artefact deltas (1,820 cells) | **All values at ±0.5** — or the corpus's real tell, **all values at 0** (2 of 38 files are exactly this) | A complete 7-vector on every artefact looks like coverage | Distribution gate: flag if >X% of cells fall in {0, ±0.5}; flag all-identical-magnitude vectors; **the polarity lint** |
| **P1c'** rationales | Seven paraphrases of the artefact's own summary, one per axis | Reads fluent; every cell populated | Assert the 7 rationales are not near-duplicates of each other or of the description |
| **P1d** ValueConnascence 7×7 | **Imported wholesale and never revisited** | It is a constant; constants never break | If the project copy is byte-identical to upstream forever it is a citation, not a model. Require ≥1 cell to differ with a rationale, or delete it and link the URL |
| **P2** `impacts` on 774 edges | Field defaults to `0.0`; schema green; "partial population is first-class" | `GovernanceConfig.enforcement = {}` exactly | Coverage keyed to **non-default** values only. `0.0` counts as absent. Ratchet the non-default count upward |
| **P3a** the interview | It runs; the operator feels heard | No ground truth for "the operator's real values", so nothing can be wrong | **Test-retest**: same operator, two formats, report rank correlation. Prior art predicts inversion. If it inverts, the instrument is speaking |
| **P3b** retrieval | The LLM cites `creed.yaml` in its trace | Citation reads as causation | **A/B against a creed-blind arm.** My measurement predicts 81–97% top-5 identity at near-flat-to-moderate creeds |

The two I would rank first: **P1c's polarity lint** (a real defect population exists today) and
**P3b's creed-blind arm** (it decides whether the load-bearing consumer does anything).

## The interview loop

**Yes, it is a closed loop, and it is the sharpest objection available against this design.** The
mechanism is more specific — and more damaging — than generic anchoring.

1. **The seven axes are all virtues.** No operator says solvability is unimportant. Part 3
   specifies neither a constant-sum budget nor forced choice — only "a normalized score on an
   easy-to-reason-with scale." Independent scoring over seven virtues with no budget is the
   textbook acquiescence instrument, and its predictable output is a **near-flat, uniformly-high
   creed**.
2. **Near-flat is precisely the regime where the creed is inert.** At α=50, r = **0.980** with
   simply summing the deltas and **97%** of the top-5 is the flat-creed top-5. *The elicitation
   instrument most likely to be produced is the one that makes its own output irrelevant.* That is
   not rhetorical — it is measured, and it is the most compact statement of the problem.
3. **The laundering step is provenance, not generation.** The model chooses the questions, the
   questions determine which axes become salient, the answers land in `creed.yaml`, and the *same
   model class* reads it as operator authority. Nothing records **who supplied each weight**.
   Downstream, "the operator ranked maintainability at 0.8" and "the model proposed 0.8 and the
   operator did not object" are **byte-identical**.
4. **The design's own provenance chain says the format decides the answer** — 0.145 normalized,
   rankings inverting between formats. **The one variable prior art identifies as
   outcome-determining is the one the design leaves free.**
5. **The counterpoints do not reach this.** The rationale-fields argument defends the
   *consumption* side, and I accept it — prose does survive where arithmetic does not. But this is
   a *production*-side failure. And "graceful degradation… better than not doing it" does not
   apply: the failure is not weaker performance, it is **a false attribution that gets stronger
   with a better model**, because a more fluent interview produces a creed the operator is more
   likely to endorse and less likely to have originated.

**Fixes, all cheap:** authored question bank (the model administers, does not design);
forced-choice or constant-sum (21 pairwise, or 100 points across 7 — both make the flat creed
unreachable, which per (2) is the whole difference); per-weight provenance, refusing to render the
creed as operator authority when the `operator` count is zero; and **apply the mandatory-negative
rule to the creed itself** — require the operator to name what they are **deprioritising**. That
is the one place in the entire design where the rule has unambiguous teeth. Note: the earlier
verdict reserved the charter Purpose rewrite for the human precisely because an agent drafting it
is the self-scoring failure. **Part 3 as written re-delegates to an agent the one thing that
verdict reserved for the human.**

## What survives me

1. **§5.3 is correct and I verified it independently.** PCA cumulative variance replicates to
   three decimals, and holds with the stubs removed (0.339 / 0.561 / 0.712 / **0.816** / 0.900).
   Only two pairwise correlations exceed |0.35|. **The strongest thing in the document and it is
   solid.** My attack lands on the sign channel, not the dimensionality.
2. **The corpus is not slogan-shaped.** `avoid_gold_plating` extensible **−0.70**,
   `AMMERSE_impact_analysis` minimal **−0.60** *for its own method*, `be_a_STARR_at_interviews`
   minimal **−0.65**, `breaking-conditions` reachable **−0.50**. Specific, costly, unflattering
   self-assessments — a genuine calibration corpus authored by someone doing the work.
3. **`minimal` is a real discriminator.** Mean +0.024, stdev 0.402, 19 of 34 negative, range
   [−0.65, +0.85]. A single field asking "what does adopting this cost in simplicity?" is cheap,
   defensible, and has 34 worked examples. Nothing in my attack touches it.
4. **Co-locating a rationale with every number is right, and the corpus proves it in the way the
   design did not anticipate.** In `fail_fast` and `wipe_the_board` the prose is correct and the
   number is wrong. **The rationale is the surviving channel.**
5. **Charter-scoping the creed** is the right home. Not contested.
6. **The half-open, replaceable value set** genuinely defuses basis lock-in. Not contested.
7. **"Better than not doing it" is a legitimate posture** — for the prose. No counter there. Only
   to the arithmetic.

**The minimum I cannot argue away:**

> A **`costs:` free-text field** on behavioural doctrine artefacts — one sentence naming what
> adopting this makes worse — plus an operator-authored charter statement naming what the project
> deprioritises. No numbers. No 7-vector. No matrix. No edge weights. No weighting function. No
> retrieval claim.

Everything I attacked lives in the arithmetic. **Nothing I attacked touches the prose.** If the
design were resubmitted as prose-only I would have almost nothing left — and by §5.4's own
measurement it would keep the only axis that discriminates.

## Concession

**Sampling.** 14 of 38 files plus 3 controls — the all-non-negative set and the stubs, because
that is what settles the question. I did **not** sample the 22 negative-carrying files
systematically. The sign-inconsistency finding rests on 3 controls against 12 subjects: enough to
establish inconsistency exists at ±0.85 for equivalent prose, **not** enough to characterise its
distribution. I cannot rule out that the scale is coherently shifted by a constant, in which case
sign is meaningless but **ordering** survives intact — which strengthens "gate on prose, not
sign", but I did not test it.

**The retrieval model is mine, not the design's.** Part 3 does not specify a ranking function. I
assumed a linear dot product. If the real intent is an LLM reading `creed.yaml` as prose context
with no arithmetic, my α-sweep **does not apply** — but then "look for artefacts that align" is
doing no retrieval work and the 1,820 numbers are decorative. Either horn is a finding; the design
should say which was meant.

**Dirichlet-uniform is not a model of real operator creeds.** The sweep is sensitivity analysis,
not prediction. My claim that LLM interviews yield near-flat creeds is **inference** from the
virtue-framing plus the cited prior art. It is the weakest joint in my strongest argument, and it
is testable in a day.

**Repo claims are static greps.** No tests run. The 260-artefact and 774-edge counts are
`find`/`grep`; the 774 sums `relation:` occurrences across nine graph files and may double-count.
Directionally right; not audited.

**Out of lens:** the trademark/authorization question and licensing generally. Also whether a
**non-linear** consumer could rescue Part 3.

## Verdict

The design is materially stronger than its predecessor and its central empirical claim is sound: I
independently replicated §5.3 and the seven axes really do carry independent information — the
one-dimensionality finding is dead. On the question the input doc says cannot be resolved from the
data, **it can, and the answer is a third option**: the fourteen all-non-negative vectors are
neither costless nor slogans — two are unfilled stubs, one is a genuine slogan with no rationale
at all, and **eleven of the remaining twelve name explicit costs in prose while the number sits at
or above zero**, with `manual_of_me` recording minimal **+0.25** for prose reading "decidedly not
minimal" against `AMMERSE_impact_analysis`'s **−0.60** for the same claim. So `minItems: 1
negative` must not ship as a hard constraint — not because the corpus is dishonest, but because
the rule gates on the sign, and the sign is the one field the corpus demonstrably cannot hold
steady; it would reject eleven careful analyses and pass the only real offender. The correct
constraint is on the prose, and the correct new component is the polarity lint, the only piece
with a validation set available today. Against that, the numeric layer does not currently earn its
cost: five of seven axes carry ≤3 negative cells in 34 vectors, so a creed weighting is one cost
axis against six benefit axes, which makes the Part 3 ranking collapse into a magnitude ranking —
measured at **r = 0.98 and 97% top-5 identity with ignoring the creed entirely** at a near-flat
creed, and 81% even at a moderate tilt — and the interview as specified is the instrument most
likely to produce exactly that near-flat creed while giving a model's prior operator provenance in
a file no consumer can audit. Part 2 and the matrix carry none of §5's grounding, §6's "the
interview is the producer" answers 0.5% of a ~2,650-cell register, and the design retires nothing:
net +5 registers, −0. **Recommendation: split it.** Ship the prose layer — a one-sentence `costs:`
field plus an operator-authored deprioritisation statement plus the polarity lint — which is
cheap, has 34 worked examples, and survives everything above. Hold the numeric layer, the edge
`impacts`, and the matrix behind two gates: a creed-blind A/B on the retrieval claim, and a
test-retest on the interview.
