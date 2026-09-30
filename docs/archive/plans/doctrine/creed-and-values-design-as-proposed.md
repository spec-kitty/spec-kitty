---
title: Creed and FoundationalValues — design as proposed (operator input record)
description: "Verbatim record of the operator's creed/FoundationalValues design — value-impact deltas and a generalized impacts edge — plus the corpus evidence measured against it."
doc_status: deprecated
updated: '2026-07-26'
related:
- docs/archive/plans/doctrine/manifesto-tier-verdict-and-handover.md
- docs/archive/plans/doctrine/manifesto-tier-primary-drivers.md
- docs/plans/doctrine/index.md
---
# Creed and FoundationalValues — design as proposed

> **Retired (deprecated).** Superseded by the canonical creed AUTHORITY doc [foundational-values-and-creed.md](../../../plans/doctrine/foundational-values-and-creed.md). Preserved as a historical record.

> ⚠️ **RECORD — the operator's input design, kept verbatim. The build target is
> [`foundational-values-and-creed.md`](../../../plans/doctrine/foundational-values-and-creed.md).** Known-stale figures
> here: "rank ≈ 5" / "5 components for 80%" (canonical: **~4–5 effective dimensions**), "39%
> (14/36)" (canonical: **35% — 12/34**, two of the fourteen are stubs). See the authority's §11.

**Status:** operator input record. **No decision taken.** Prototyping / hardening.
**Author of the design:** Stijn Dejongh (operator). Recorded verbatim in §1–§4 below.
**Provenance:** supersedes the mechanism rejected in
[`manifesto-tier-verdict-and-handover.md`](manifesto-tier-verdict-and-handover.md); this is a
*different* design that answers most of that verdict's objections.

> **Framing, in the operator's words:** *"To be used for reference/grounding/steering, no
> decision yet, we are prototyping/hardening an architectural design."*

---

## Core problem statement

> **We are lacking a systems thinking model.**

---

## 1. Part 1 — Creed and Values

Create a new `FoundationalValues` **half-open enum**, based on the 7-axis AMMERSE system. The
design is a new rich type in the doctrine module, representing Organizational/Personal values
`{ name: str; description: str }`.

These can be **replaced/extended by consumers/customers** to fit their own system. The built-in
/ default structure takes the AMMERSE values, as the prior art already has examples of those. It
not being (fully) corroborated by other sources is not blocking, though it is a valid point of
critique. Hence the design is kept **easy to change** (open–closed principle).

`FoundationalValues` are used in:

- **A new `creed` artefact on the charter**, assigning a **weighted score** to each of the
  `FoundationalValues`, depicting *"How important is this to us"*, accompanied by a
  **rationale / free-text field** for each of them.
- **A new optional field on all behavioural doctrine artefacts** (assets and templates are
  **exempt**) encoding *"How does this support/weaken each of the `FoundationalValues`?"* — the
  `[-1;1]` normalized system already applied in the operator's patterns library
  (worked example: [safe to fail](https://patterns.sddevelopment.be/practices/safe_to_fail/)).

Also included: a **`ValueConnascence` matrix** — an N×N matrix explaining how each value impacts
the others (per the self-created AMMERSE analysis process).

## 2. Part 2 — Enhance the existing DRG edge / relationship model

Rather than the black-or-white absolutist `in_tension_with` relationship we currently have, a
more generic **`impacts`** field on edges / relationships can be added, to indicate whether two
nodes are *"more antagonistic"* or *"more cooperative"* — a `[-1;1]` normalized bounded-strength
approach on the **sabotages ↔ reinforces** scale.

## 3. Part 3 — Charter creation

During charter creation / interviewing, a set of **LLM-chosen questions** can be asked of the
operator/team to determine how they rank each of the values (again, a normalized score on an
easy-to-reason-with scale).

This directly results in the capture in **`creed.yaml`**, which in turn allows the LLM to use
the **doctrine API** to look for artefacts that align with the chosen value-importance
assignments.

## 4. Counterpoints raised by the operator

- **AMMERSE being licensed work.** The operator has personal authorization from Jonathan to use
  and extend the AMMERSE system; the *idea* is not licensed — the **name** and **trademark**
  are. Therefore: provide **accreditation**, not a license of the consultancy framework. This is
  acceptable because inventing a derivative system would weaken the AMMERSE brand.
- **Not exclusively stochastic.** The design uses stochastic heuristics to **inform** the LLM.
  Because natural language and human interaction are vital here — *humans can hold two
  conflicting opinions in tension and work through the apparent paradox; deterministic systems
  cannot* — the `rationale` / `description` fields are **pivotal** in allowing correct-ish
  interpretation by LLM models.
- **Graceful degradation is acceptable.** Behaviour will degrade with less-powerful inference
  models. Worst-case *"better than not doing it"* behaviour is a perfectly valid reason for
  building a system like this.

---

## 5. Verified grounding measured against this design

Everything in this section was measured on 2026-07-26, not asserted. It is recorded here
because it materially changes two conclusions from the earlier squad verdict.

### 5.1 The authored shape (canonical, from the source repository)

`sddevelopment-be/penguin-pragmatic-patterns@develop`, `content/practices/*.md` — TOML
frontmatter:

```toml
ammerse = [
  {name = "agile",         delta = "0.9",   rationale = "The technique enhances agility, with a strong focus on rapid adaptation and iterative learning."},
  {name = "minimal",       delta = "-0.25", rationale = "The technique does introduce some additional complexity through documentation and tracking of experiments, but the overall negative impact remains low."},
  {name = "maintainable",  delta = "-0.15", rationale = "Minor impact on maintainability..."},
  {name = "environmental", delta = "0.45",  rationale = "..."},
  {name = "reachable",     delta = "0.45",  rationale = "..."},
  {name = "solvable",      delta = "0.6",   rationale = "..."},
  {name = "extensible",    delta = "0.15",  rationale = "..."}
]
```

Field names are `name` / `delta` / `rationale`. **`delta` is a quoted string, not a number.**
Every number is paired 1:1 with its rationale sentence — co-location is already the invariant.
The rendered HTML shows only the prose; the `index.json` output carries the numbers. (An earlier
review read the HTML and wrongly concluded no numbers are published. Corrected.)

**"Delta" is the semantically right word:** it is the *change caused by adopting the practice*,
relative to not adopting — not an absolute property. This matters for composition (see §5.4).

### 5.2 Corpus size and completeness

- **38** files in `content/practices/`; **37** carry an `ammerse` block; **36** carry a complete
  7-axis vector. Machine-readable extract committed alongside this document as
  [`_ammerse-corpus-36-practices.json`](../../../plans/doctrine/_ammerse-corpus-36-practices.json).
- A meaningful share of Spec Kitty's current doctrine originates from this library, so this is a
  genuine **calibration set**, not a external analogue.

### 5.3 Dimensionality — REFUTES the earlier "one-axis collapse" finding

PCA over the 36 authored vectors:

| Component | Variance | Cumulative |
| --- | --- | --- |
| PC1 | 31.9% | 31.9% |
| PC2 | 21.3% | 53.2% |
| PC3 | 14.2% | 67.4% |
| PC4 | 12.5% | 79.8% |
| PC5 | 8.7% | 88.6% |
| PC6 | 7.6% | 96.1% |
| PC7 | 3.9% | 100.0% |

**5 components are needed for 80% of variance.** Only two pairwise correlations exceed |0.35|:
`minimal ↔ reachable` (r = −0.46) and `maintainable ↔ extensible` (r = +0.41).

> The earlier squad finding that "the corpus occupies roughly one rigour-vs-velocity axis, not
> seven dimensions" is **refuted by the real authored corpus.** That finding came from an LLM
> scoring ~13 artifacts itself, and measured its own scoring bias rather than a property of the
> value system. **The 7 axes carry genuine independent information.**

### 5.4 Per-axis distribution — two axes carry no cost information

n = 36. Mean / stdev / min / max:

| Axis | Mean | Stdev | Min | Max | Non-zero |
| --- | --- | --- | --- | --- | --- |
| agile | +0.335 | 0.342 | −0.45 | +1.00 | 28/36 |
| minimal | **+0.022** | 0.391 | −0.65 | +0.85 | 31/36 |
| maintainable | +0.412 | 0.377 | −0.25 | +1.00 | 30/36 |
| environmental | +0.252 | 0.203 | **+0.00** | +0.85 | 31/36 |
| reachable | +0.333 | 0.308 | −0.50 | +1.00 | 30/36 |
| solvable | **+0.607** | 0.296 | **+0.00** | +1.00 | 33/36 |
| extensible | +0.275 | 0.309 | −0.70 | +1.00 | 26/36 |

Two observations that should shape the schema:

1. **`solvable` and `environmental` are never negative in 36 authored vectors.** They carry no
   cost information in practice. `solvable` also has the highest mean (+0.607) — it behaves like
   a near-constant "this is a good practice" signal rather than a discriminator.
2. **`minimal` is the only axis with a near-zero mean (+0.022) and high spread (0.391).** It is
   the genuinely discriminating axis — the one that actually separates practices.

### 5.5 Granularity

**22 distinct |delta| values** are in use: `0.0, 0.05, 0.1, 0.125, 0.15, 0.2, 0.25, 0.3, 0.35,
0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1.0`. Effectively continuous
at 0.05 resolution, with one 0.125 outlier. This is **not** a coarse ordinal band scale.

### 5.6 The mandatory-negative-component rule, measured

The earlier verdict identified "a value vector with no negative component is visibly a lie" as
the one contribution with no prior art, and recommended it as a schema constraint. Measured
against the corpus:

- **22 of 36 (61%)** carry at least one negative component.
- **14 of 36 (39%)** are all-non-negative: `LARS`, `TEMPLATE_PRACTICE`,
  `communication_channel_compression`, `define_test_boundaries`, `easy_to_change`,
  `external-memory`, `fail_fast`, `impact_oriented_communication`, `manual_of_me`,
  `quad_A_test_structure`, `ten_minute_tasks`, `the_point_of_dissent`, `wax_on_wax_off`,
  `wipe_the_board`.

> A hard `minItems: 1` constraint on negative components would **reject 39% of the operator's
> own authored corpus.** Either the rule must be advisory (a lint/warning), or those 14 entries
> are genuinely slogan-shaped and the rule is correctly catching them. **This is a decision the
> operator must make; it cannot be resolved from the data alone.**

---

## 6. What the earlier verdict's objections look like against *this* design

| Earlier objection | Status against this design |
| --- | --- |
| Derived ordering fails 0/6 | **Not applicable** — this design does not derive orderings; it informs |
| 5/5 false positives from sign-opposition | **Not applicable** — `impacts` edges stay *authored*; no derivation step |
| Corpus is one-dimensional | **Refuted** (§5.3) — rank ≈ 5 |
| Project-specific data in a reusable library | **Resolved** — `creed` lives on the **charter** |
| Closed kind universe / "fork the CLI" | **Sidestepped** — charter artefact, not a doctrine `NodeKind` |
| Basis lock-in | **Resolved** — replaceable/extensible value set by design |
| Scoring register decays (3-for-3 precedent) | **Addressed** — Part 3 (the interview) *is* the producer |
| AMMERSE trademark | **Resolved** — accreditation, authorized by the author |
| Ungrounded scores are unfalsifiable | **Addressed** — mandatory `rationale` per value |
| Field-authored relationships are banned | **Overstated** — the ban covers exactly `specializes-from` / `enhances` / `overrides` |
| First-order matrix not in repo | **Resolvable** — authorization permits bringing it in-repo |

---

*Hardening findings and the recommended final shape are in the companion document produced by
the hardening squad.*
