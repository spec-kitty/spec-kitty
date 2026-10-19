# Mission Specification: FoundationalValues and Creed Band

**Created**: 2026-07-26
**Status**: ⏸ **NOT YET SPECCED — deliberately.** Scope sketch only.
**Programme**: Mission **D** of five — see the programme record [`doctrine-canonical-structure-remediation-01KYEYSD`](../doctrine-canonical-structure-remediation-01KYEYSD/spec.md).
**Order**: Blocked by **A** only. Independent of B1, B2 and C.
**Design authority**: [`foundational-values-and-creed.md`](../../docs/plans/doctrine/foundational-values-and-creed.md) · **Sequencing authority**: [`manifesto-program-delivery-sequence.md`](../../docs/plans/doctrine/manifesto-program-delivery-sequence.md)

## Why this is a sketch and not a specification

**Operator guidance, 2026-07-26:** do not over-specify or plan any mission after phase A. Missions run
**one at a time**, each specced and planned only after the previous phase is finalized.

This mission's blocking design decisions are now **all settled** — D-1, D-5 and ADR-D8 were answered
on 2026-07-26 and are recorded under *Carried constraints* below. What still argues for waiting is
mission A: it adds `extra="forbid"` to `AgentProfile` and the zero-producer lint that both of this
mission's new profile fields must satisfy, so the shape of that work is only knowable after A lands.
D-4 (the interview instrument's question design) also remains operator-only and unanswered, though it
gates only a slice.

## Scope sketch

Doctrine resolves to an unordered bag of co-valid rules. When two conflict, the arbiter is whatever
prior the consuming model brings — which for current-generation LLMs favours delivering output now.
**The system delegates its value arbitration by omission.** This mission builds the value layer that
closes that, under the operative frame: a **limited-horizon heuristic that informs**, never
auto-decides, and degrades gracefully.

> ### The corpus is a reference, not a target *(operator, 2026-07-26)*
>
> The AMMERSE practice corpus is **reference material, not a corpus to chase**. Four consequences,
> and the last cuts against us:
>
> - **D-5's recorded consequence softens.** An earlier revision required I9's import to supply or reject the ≥3-of-38 corpus entries lacking rationales. It does not: the corpus need not satisfy our rules — **our authored artefacts must**. Import it labelled as reference.
> - **I5 narrows to internal consistency.** Unifying the two drifted definition copies is still real — the tactic says "use these verbatim" and routes to different text on a live shipped path — but it is a self-consistency fix, not fidelity to upstream.
> - **I1a keeps its calibration set, changes its subject.** The 12 known rows stay useful for tuning the lint; the lint then runs against **our** artefacts rather than policing the corpus.
> - **⚠️ Releasing the corpus as a target also releases it as a check.** The "1,372 cells against a 34-vector calibration set" objection dissolves — and so does the only external referent the numeric layer had. That leaves **I8's perturbation probe and I1a's polarity lint as the sole instruments**. Thinner than before; know it going in.

- **I5** — unify the two drifted AMMERSE definition copies (tactic + template) with a parity test.
- **I6** — accreditation: required non-empty `attribution`, a root `NOTICE`, packaging inclusion.
- **I9** — corpus import + value-set artefact + a **non-AMMERSE N ≠ 7 fixture**.
  **Inherited burn-down obligation:** mission A's zero-producer lint measured **20 baseline entries for the `import-candidate` kind** — the model and schema are declared, and every instance in the repository is a test fixture. That is not a surprise: the sequencing authority already says I9 "gives `import_candidates` its first real producer." I9 is therefore the owner of those entries, and **this mission cannot reach `done` with them outstanding** (mission A SC-001a, enforced by test). The legal dispositions are `wire-the-producer` or `delete-the-declaration` — there is no `accepted`.
- **I13** — N-generic first-order connascence matrix and its validator. *ADR-D8 settled 2026-07-26 — unblocked.*
- **I8** — perturbation-stability probe (~20 lines). Can falsify the mechanism; **run it early**.
- **I1a** — sign-vs-rationale polarity lint, advisory, against the 12-row validation set.
- **I16** — advisory-homonym unification, 8 vocabularies → 2. **Its own occurrence map** (C2).
- **I4-WP01/02** — additive `ResolvedContext` partition; un-vacuum `walker.py:507-509` (the RED is the deliverable).
- **I4-WP03** — Required/Suggested render grouping. Independent merit only; its arm-B purpose died with G5.
- **I10** — ranking function. Unparked by the D-3 arithmetic ruling.
- **Charter interview slice** — see below.

Estimated 7–13 agent-days plus the interview slice, ~60–100 files.

## The charter interview slice (operator ruling, 2026-07-26)

**The creed creation band must include a charter interview slice.** A creed that cannot be created is
a schema slot with no producer — precisely what mission A's zero-producer lint exists to reject, so
shipping the value layer without a creation path would fail A's own gate.

The design authority puts the creed on the charter (§7.7): project-specific data carrying
`value_set: <id>` plus N weights, each with a rationale. So creation runs through the charter
interview, and §7.7 already names the hazard:

> ⚠️ The charter's on-disk sections are **not model-validated in production** — every production
> reader goes through raw ruamel; `model_validate` appears only in tests. So a `creed:` block would
> land **silently unvalidated**.

That makes the slice concrete rather than vague:

- Extend the charter interview to elicit a creed: `value_set` pointer plus N weights with rationales.
- An explicit **per-section validate at the sync seam**, because the production readers do not validate.
- A **three-state loader** — `absent` / `partial` / `complete` — whose `absent` state surfaces as a **consistency-check finding**, not an info log.

**D-4 is settled (2026-07-26), and its answer shapes this slice.** The original framing — authored
question bank versus model-chosen questions — bundled two independent failures:

- **Flatness comes from the response format, not the authorship.** "Rate Maintainable 0–1" yields ~0.8 for every value whoever asks it. The ruling is a **constant-sum budget** ("distribute 100 points across the N values"), which prevents a flat creed structurally. §13's own objection concedes this by saying "with no budget".
- **Provenance laundering is a separate concern with a separate fix**: record **per-weight provenance** — `operator` / `model-suggested-operator-confirmed` / `default`. Required regardless, because §9 names override events as the only available gradient and a deviation ledger of *(suggestion, override, reason)* is what makes that real.
- **An authored question bank was rejected on a third ground the framing missed**: it is basis-specific and breaks **ADR-D10's N-genericity**. A bank of 21 AMMERSE pairs cannot serve a consumer's 5-value basis, so shipping one makes every non-default basis second-class — the failure the N≠7 fixture exists to prevent. **Elicitation questions live on the value-set artefact**, authored by whoever authors the basis.
- **I8 runs before the instrument is built.** It reports how much elicitation precision is worth buying: stable under wide wobble → cheapest honest instrument; stable only under tight weights → forced-choice rigour earns its cost; unstable everywhere → the numeric layer is dead and I10 dies with it.

**The interview is a general doctrine-gap elicitation surface, not a creed-only tool** (operator,
2026-07-26). Once it exists it is plausibly the cheapest route through several things currently
priced as authoring sweeps — FR-018's 55 laundered `suggests` verdicts, this mission's ~126 bias
cells, and artefact vectors generally.

**What is in scope versus what stays closed.** The *plumbing* above is in scope. **I17's interview
instrument stays closed** — that is the question-bank design question (D-4: authored bank with forced
choice, versus model-chosen questions), it is operator-only, and the design authority is explicit
about why it cannot be agent-drafted: model-chosen questions over N virtues with no budget
predictably yield a near-flat creed — the regime in which the creed is inert — and nothing records
*who supplied each weight*, so a model's prior silently acquires operator provenance.

**The 3.3.x milestone scoping of charter-interview work is not final and should be revised.** It was
assigned before the creed became a charter-resident artefact with a creation dependency. Re-decide
the milestone when this mission is specced; do not inherit 3.3.x as settled.

## What Phase 0 closed — and the caveat on it

**Gate G5 failed: the `#2538` experiment rig does not exist.** Verified twice, independently, and
re-verified against the fork: every in-repo hit for `2538` is a document; the rig's unique markers
("Reproduction threshold", "consulted-arbitration", "add CSV export", "reporting module") return
**zero hits across all 115 fork branches**; `git log --all -S` returns only the commits that added
the design documents. The investigation branch `origin/docs/manifesto-tier-analysis` is fully
reconciled with main — nothing was lost in transfer. The rig was never built.

Therefore gate **G3 is unreachable**, and **I14** (value fields — 14–18 code files plus
**~1,372–1,596 authored cells**, the programme's entire unquantified authoring tail) and **I17** (the
interview instrument, as distinct from the charter slice above) are **CLOSED, not deferred**.

**Be precise about *why* I14 closed.** It closed on **G3 being unreachable** — not on a measured null,
and **not** on authoring cost, which the D-4 interview ruling plausibly collapses. "We could not run
the experiment" is a weaker reason than "we ran it and it read null." Do not restate this as settled
evidence when speccing.

**Caveat, stated plainly:** this proves the rig is not in any repository or fork branch reachable from
here. If it exists in the operator's own environment, these closures reverse. `#2538` itself is
milestone 3.3.x and stays open.

## Carried constraints — do not lose these when speccing

- **ADR-D8 — SETTLED 2026-07-26. I13 is unblocked.** The asymmetric `maintainable ↔ extensible` pair is confirmed an error and symmetrised to **`+0.75` in both directions**; the adopted claim is that the two values **reinforce** each other. Headline residual **4.70% → 4.37%**, per-step gain **0.3892 → 0.3766**. The amendment lands on ADR `2026-07-26-3`.
  - **Basis:** the operator authored the AMMERSE *analysis procedure* this repository implements, and holds **prior written consent** from J.B. Crossland to use the AMMERSE idea and publish that procedure under his own IP. Crossland's value system is the acknowledged **ideological root** (§3). The adjudication is therefore the operator's own, on his own authority. **Not provisional, not pending anyone.**
  - **No upstream report is owed.** Earlier revisions treated one as an outstanding operator-only obligation gating the matrix — **superseded**. Accreditation and mention discharge the obligation in full, which makes the required non-empty `attribution` and the root `NOTICE` (I6) load-bearing rather than ceremonial.
  - **Divergence record — keep it, but as provenance, not a gate.** Our matrix differs from the published one at exactly one cell. Record which and why, with a `source_digest` so a later upstream change is detected. Good engineering; no longer a precondition on shipping.
  - **Do not edit `_ammerse-connascence-first-order.json` or `_ammerse-second-order.json`.** They are the published upstream data and the reproduction script's inputs. The repair is applied at consumption, in the value-set artefact — editing the source data would destroy the ability to reproduce the discrepancy for the upstream report.
- **D-1 — SETTLED IN FULL by operator ruling, 2026-07-26.**
  - **`toolguide` is OUT.** A complimentary artefact, not a behavioural one, so there is no Δ-from-not-adopting to record. Confirms §7.4 ("consulted, not adopted"). `_VALUE_IMPACT_KINDS` stays `{DIRECTIVE, TACTIC, STYLEGUIDE, PROCEDURE}`.
  - **`agent_profile` is IN, on the bias side, and carries *two* fields** — more than §7.4 anticipated:
    1. an explicit **creed/bias matrix**: a list of `{value, bias, rationale}` entries;
    2. a **creed description**: free-text, multiline.

  `_VALUE_BIAS_KINDS = {AGENT_PROFILE, PARADIGM}` (+ the charter creed) is confirmed.

  **Authoring tail this creates:** 18 built-in profiles × N values = **~126 bias cells at N = 7, plus 18 creed descriptions**. Real, but two orders of magnitude below I14's closed ~1,372–1,596 cells, and it is **not** a reopening of I14: this is the *bias* side (who is weighing), not the *impact* side (what an artefact costs). I14 was gated on G3; the bias side never was.

  **Both fields are new schema slots on `AgentProfile`, so C-009 binds them**: producer plus coverage gate in the same commit, or they ship inert and mission A's zero-producer lint fails. Mission A also adds `extra="forbid"` to `AgentProfile`, which is a further reason this cannot precede A.
- **D-5 — mandatory `rationale` is HARD on value descriptions and deltas. Settled by operator ruling, 2026-07-26**, with a deliberate boundary: the numeric value is a *warning signal*; the rationale is the tie-breaker and the real value-add, so a number without one is the failure mode the layer exists to prevent. **Hard** on value descriptions and `delta` entries; **not** on `DRGEdge` relationships, unless the rationale there can be trivially inferred.
  **Consequence to handle at import:** the calibration corpus fails a hard rule (≥3 of 38 entries lack a rationale). I9's corpus import must therefore either supply the missing rationales or reject those entries — it cannot import them silently. Decide which when speccing; do not let the import quietly weaken the rule to advisory.
- **Do not unify into the compiled charter bundle.** `.kittify/charter/` is a regeneration target; divergence there is a staleness symptom, and a fix written there is deleted by the next regeneration.
- **The gain check must be start-vector-independent.** Plain power iteration is **fail-open** on two-camp bases — a true gain of 1.0 reads as 0.33 from an all-ones start. That is the dangerous direction.
- **Never renormalise per tier** — that *is* power iteration, and every artefact converges to the same attractor. Scale once at the end, from the **sup-norm** (`1/(1+r∞)` = 0.75 for AMMERSE), not the spectral radius, which overflows to 1.074 on an adversarial ±1 base. And **no fixed constant bounds a sum** — two real corpus vectors already sum past 1.7.
- **I10 must not rebuild what already failed measurement:** creed-weighted ranking collapses to row-sum at r ≈ 0.98, and vector-derived precedence scored **0 reproductions of 6** — worse than chance. Run I8 first; it can falsify the arithmetic reading cheaply.
- **Land I5 before I9** so the parity test is green on arrival. If I5 slips, land it as `xfail(strict=True)` with the ticket ID inline — **never as a plain red**, which is indistinguishable from the honest P0 reds and invites green-washing.
- **I16 needs its own occurrence map** — C2 forbids batching two all-surface sweeps.
- **Everything is N-parameterised** (ruling (d)); axis identity is by `id`, never position. The N ≠ 7 fixture is what makes that a fact rather than a claim.
- **Do not expose the value set as a `DoctrineService` `@property`** — an architectural test introspects every property and demands matching `selected_<kind>` / `required_<kind>` config fields. Use `resolve_active_value_set()`.
