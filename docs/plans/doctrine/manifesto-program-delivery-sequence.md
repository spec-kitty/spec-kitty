---
title: FoundationalValues/creed program — delivery sequence
description: "Executable delivery sequence: critical path with gate positions, 22 increments ranked by evidence-per-cost, superseding-ADR scope, park register, and effort envelope."
doc_status: draft
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
related:
- docs/plans/doctrine/foundational-values-and-creed.md
- docs/archive/plans/doctrine/squad-reports/index.md
- docs/plans/doctrine/index.md
---
# FoundationalValues/creed program — delivery sequence

> **Tier: AUTHORITY** for sequencing. The design authority is
> [`foundational-values-and-creed.md`](foundational-values-and-creed.md).

> **Status (2026-09-30): resumed for 4.x, tracked by #5432 on 4.x Work.** Only Mission A (`doctrine-silence-guards-01KYFV7Q`) has
> landed. Missions B1, B2, C and D never got past specify. Milestone references below are as
> of 2026-07-26: the 3.2.x line has since closed (last release 3.2.7), #2934 closed on
> 2026-07-26, and the 3.3.x milestone was retired on 2026-08-23 (#2538 is now in Product
> backlog). See the [doctrine index](index.md#programme-realization-2026-07-26-operator-ruling).

**Date:** 2026-07-26 · **Base:** `0fcb4b3d2` + the review-round-2 fix commit, branch `docs/manifesto-tier-analysis`
**Role:** sequencing only. No architectural decision is taken here; **D-2 is escalated, not
resolved.**

## Settled inputs — do not re-litigate

| Ruling | Consequence |
| --- | --- |
| (a) `impacts: -1` **is** `in_tension_with`; `impacts` **subsumes** it; a superseding ADR is an accepted cost | Open decision "annotate vs replace" is settled: **replace**. The ADR moves onto the critical path |
| (b) The goal is a heuristic informing agent reasoning; per-cell defensibility is not the bar | Retires the ranking-collapse objection *as an objection*. The numeric gate becomes **surfaced-vs-silent**, not ranking fidelity |
| (c) AMMERSE is authorized — accreditation, not licensing | Unparks the coefficient port. Trademark question closed; accreditation obligations remain (increment **I6**) |
| (d) **The design is generic over N values**; AMMERSE is the default basis | Every increment touching the value set or matrix must be **N-parameterised**. Adds an explicit non-AMMERSE fixture to **I9** and an N-generic validator to **I13** |

## What the matrix measurement changed

Measured: λ = 2.3350, gain **λ/(N−1) = 0.3892**, adopted two-term damped residual **4.70%**;
second-order not derivable (**42/42 off-diagonal**); one asymmetric pair of 21 (47/49 cells); **divisor read as
N−1** (an interpretation, not an upstream statement); and by Gershgorin gain **≤ 1** for any basis
with coefficients ∈ [−1,1] and zero diagonal — so **bounded** always, **sound** for gain < 1, with
equality at perfect polarisation. Sensitivity to the one asymmetric pair: residual 4.37%–6.00%
depending on the repair, so **design D-6 (≡ ADR-D8) must be adjudicated before the matrix ships**.

| # | Effect | Was | Is now |
| --- | --- | --- | --- |
| 1 | Spectral-radius experiment | "cheapest next experiment", blocked on coefficients not in repo | **DONE.** Retired. One gate and one afternoon removed |
| 2 | Matrix park — "a slot with no available producer" | Parked indefinitely | **UNPARKED** → increment **I13** |
| 3 | The composition formula | Unstated convergence assumption | **Licensed**, 4.70% residual (two-term damped), and **bounded for any admissible basis** (gain ≤ 1; sound for gain < 1) |
| 4 | Composing `impacts` along DRG cycles | Open runaway-gain risk needing a cycle guard | **Bounded.** I12 loses a sub-requirement |
| 5 | `0.25 × second_order` | Planned third term | **DEAD.** Scope halved |
| 6 | Matrix validator | 3 assertions | **4** — add symmetry. Plus an N-generic range + zero-diagonal check, which is what makes soundness structural |
| 7 | "Gain, not correlation" | Applied to matrix and edges | **Withdrawn for the matrix.** Authored as N(N−1)/2 unique pairs, not N² — authoring halved again |

**Net: the measurement removed one gate, unparked one increment, killed one term, and halved two
authoring burdens. It is a scope reduction.**

## 1. Critical path

`◆` = gate. `═` = critical path. *(Gate IDs are stable identifiers, not a sequence — path order is G0, G1, G2, G5, G3, G4. G5 is a precondition of rank 8, not an independently scheduled row.)*

```
  ◆G0  truncation soundness ............ CLEARED (gain=0.389; bounded generically)

  ═══ STRAND A — impacts / tension subsumption (the long pole) ═══
  I3a  generate_schemas --check → CI ......... campsite, no deps
   │
  I2   silent-kind-drop closure ............. shared enabler of 4 open issues
   │     ├ query.py:230-242 (16 bucketed / 10 read out)
   │     ├ charter/context.py:672-683 (4 kind branches, no else)
   │     ├ extractor.py:133-145 (_KIND_MAP, 11 entries)
   │     └ extractor.py:1210-1229 (_node_to_dict/_edge_to_dict — 4th site)
   │
  I3b  DRGNode/DRGEdge extra="forbid" + writers + round-trip  (ONE commit)
  I3c  AgentProfile extra="forbid" (1 line; same campsite cluster, no deps)
   │
  ◆G1  SUPERSEDING ADR — impacts subsumes in_tension_with ... CLEARED (ADR 2026-07-26-3, Accepted)
  ◆G2  ══ WHICH RELATION CARRIES `impacts` ══  *** the program-shape gate *** ... CLEARED (Option A: new `Relation.IMPACTS` — §10)
   │
  I12  Relation.IMPACTS + edge annotation + retire in_tension_with
   │      + re-point consistency_check.py:917-1050
  I13  first-order connascence matrix, N-generic, inside the value-set artefact
         ▲                    ▲
  I5 → I6  AMMERSE definition unification → accreditation (NOTICE, provenance)
  I9       corpus import + value-set artefact + a NON-AMMERSE N≠7 fixture
  I8       perturbation-stability probe  [needs I9; runs independent of #2538]

  ─── STRAND B — context strength (independent; the #2538 arm-B enabler) ───
  ◆G5  verify the #2538 rig still runs ....... FAILED 2026-07-26 — rig verified absent in-repo (§10)
  I4-WP01  additive ResolvedContext partition + campsite deletions
  I4-WP02  un-vacuum walker.py:507-509 — the RED is the deliverable
  I16      advisory-homonym unification (8 vocabularies → 2)  ← blocks WP03
  I4-WP03  Required:/Suggested: render grouping
  ◆G3  #2538 ARM-B RUN ....... UNREACHABLE — G5 failed (§10); gates ONLY the numeric value branch
   │
  I14  value_impact / value_bias fields        [CLOSED 2026-07-26 — G3 unreachable, not deferred (§10); was: gated on G3 positive]
  I17  interview instrument                    [CLOSED 2026-07-26 — G3 unreachable, not deferred (§10); was: gated on G3 + D-4]

  ─── STRAND C — prose layer (gates on nothing) ───
  I1a  sign-vs-rationale-polarity lint ..... validation set exists TODAY
  I19  zero-producer lint .................. guards every increment above
  I1b  operator-authored charter deprioritisation statement (human)
  I1c  costs: field sweep
  I15  #2591 component-type
  ◆G4  D-3 — arithmetic, or agent reads creed.yaml as prose? ... ANSWERED 2026-07-26: ARITHMETIC (operator ruling; §10)
  I10  ranking function                       [UNPARKED 2026-07-26 — G4 answered "arithmetic" (§10); was: gated on G4; dies if "prose"]
```

**Key sequencing conclusions:**

- **`#2538` gates only the numeric value branch** (I14, I17) — I10 is gated on **G4** (design D-3), *not* G3; and it does not gate I12/I13/I1a. Ruling (a)
  settles the tension question on operator authority; it does not need the experiment. Prior art
  predicts arm B ≈ null, and a probably-null gate must not hold a strand that is already decided.
- **`#2591` is off the critical path.** It is a child of `#2216`, which is `blocked_by #2467`
  (KEYSTONE). Making Strand A wait on a blocked epic buys nothing.
- **The ADR is the cheapest gate to clear and unblocks the most.** Doc-only, and it supplies exactly
  the unpark condition the earlier handover set.
- **I2 cannot be sequenced after I12.** Sites 3 and 4 would silently delete the new edge field at
  extraction and regeneration.

## 2. Ranked increments — by evidence-per-cost

`C` = campsite commit.

| Rank | Increment | Shippable alone? | Blast radius | Evidence produced | Commit/Mission |
| --- | --- | --- | --- | --- | --- |
| **1** | **I19 zero-producer lint** | Yes | New test module | Mechanically proves/disproves the 3-for-3 thesis. **The only thing preventing a fourth inert register** | Commit **C** |
| **2** | **I1a polarity lint** | Yes | Lint + fixture; prose only | **The only component with a falsification set today** (12 known rows). Enforces the §7 floor | Commit |
| **3** | **I3a `generate_schemas --check` → CI** | Yes | 1 workflow file | Closes a verified gap: `--check` exists, zero references in `.github/` | Commit **C** |
| **4** | **I5 AMMERSE definition unification** | Yes | 2 YAML + parity test | Removes known drift. Hard prerequisite for accreditation | Commit **C**, `#2080` |
| **5** | **I2 silent-kind-drop closure (4 sites)** | Yes | 8–14 files. **Collides with `#2532`** | Unblocks `#2468`/`#2847`/`#2862`/`#2829` and I12 | **Mission**, `#2466` |
| **6** | **I3b DRG model + writers + round-trip** | Yes | 3–5 files | Converts two silent-drop hazards into load errors. Non-negotiably one commit | Commit **C** |
| **7** | **I3c `AgentProfile extra="forbid"`** | Yes | 1 line + test | Closes the highest-probability inert-ship path | Commit **C** |
| **8** | **I4-WP01/02 + campsite deletions** | Yes | 8–15 files | Un-blinds a CI instrument that measures nothing by construction. **WP02's red is the deliverable** | **Mission** (2 WPs) **C** |
| **9** | **G1/G2 the superseding ADR** | Yes | 1 ADR + supersession header | Unblocks a 45–60-file mission. **Highest leverage per unit cost in the program** | Commit |
| **10** | **I9 corpus import + value set + non-AMMERSE fixture** | Yes | 8 files | The calibration artefact every numeric increment needs. Gives `import_candidates` its first real producer. **Ruling (d): must include an N≠7 fixture** | **Mission** (~4h) |
| **11** | **I8 perturbation-stability probe** | Yes, once I9 exists | ~20 lines | Highest-information measurement available; can falsify the design. Runs whether or not `#2538` does | Commit |
| **12** | **I16 `advisory` homonym unification (8→2)** | Yes | 30–60 files; needs occurrence map | Removes a `primary`/`merge`-class footgun before it reaches agent context. **Blocks WP03** | **Mission** |
| **13** | **I4-WP03 render grouping** | No — needs I16 | 5–10 files | ~~Produces arm B of G3~~ — **G3 unreachable (§10, 2026-07-26)**; survives in mission **D** on independent merit only (render-grouping clarity), not as an experiment input | Mission WP |
| **14** | **G3 run `#2538` arm B** | ~~Yes~~ | No code | **CLOSED 2026-07-26 (§10): the rig is verified absent in-repo.** I14/I17 are closed directly below, not gated on this row running | Experiment — will not run |
| **15** | **I6 accreditation** | No — needs I5 | 5–8 files | Discharges ruling (c). `NOTICE` verified absent | **Mission** |
| **16** | **I12 `Relation.IMPACTS` + retire `in_tension_with`** | No — **G2 CLEARED** (Option A, §10); needs I2, I3b | **45–60 files** | Delivers ruling (a). Estimate confirmed, not reduced — Option A was the one chosen | **Mission**, `drg-relation-impacts-vocabulary-01KYFV87` |
| **17** | **I13 first-order matrix, N-generic** | No — needs I6, I9 | 6–10 files | Delivers the licensed composition. Scope halved | **Mission** |
| **18** | **I15 `#2591` component-type** | Blocked by `#2467` | 41–59 files | The discriminator I1c/I14 applicability should be expressed in | **Mission** |
| **19** | **I1c `costs:` field** | Yes | 12 code + 260 authored | The minimum that survives every lens | **Mission** |
| **20** | **I14 value fields** | **CLOSED 2026-07-26 (§10)** — G3 unreachable, not deferred | 14–18 code + **~1,372–1,596 cells** (post-§7.4 kind set) | — | ~~Mission ×2~~ CLOSED |
| **21** | **I10 ranking function** | **Yes — UNPARKED 2026-07-26**, G4 answered "arithmetic" (§10) | 3 files, ~4h | Ships in mission **D**. Must not rebuild the row-sum collapse (r≈0.98) or the vector-derived mechanism (0/6 reproductions); I8's perturbation probe is the cheapest instrument to falsify the arithmetic reading first | Mission WP → **D** |
| **22** | **I17 interview instrument** | **CLOSED 2026-07-26 (§10)** — G3 unreachable, not deferred | 5–10 files | Closes the production-side laundering | ~~Mission~~ CLOSED |

**Six of the top eight are campsite or campsite-adjacent — deliberate: debt before functional work.**

## 3. What the superseding ADR must cover

> **Status (2026-07-26): written and Accepted** —
> [`docs/adr/3.x/2026-07-26-3-impacts-edge-subsumes-in-tension-with.md`](../../adr/3.x/2026-07-26-3-impacts-edge-subsumes-in-tension-with.md).
> ADR-D2 chose **Option A**. **ADR-D8 is also now CLOSED**, by amendment to the same ADR (symmetrised
> to `+0.75`; headline residual 4.70% → 4.37%). See § 10, Ruling 5.

**Supersedes** `docs/adr/3.x/2026-07-21-1-in-tension-with-drg-edge.md` (Accepted 2026-07-21).
⚠️ **Two ADRs share the `2026-07-21-1` prefix** — the glossary one is *not* the target. Name the
full filename.

**Decides:** *(namespace note: `ADR-Dn` = decisions this ADR takes; `D-n` = the design authority's §13 open decisions. They are different lists — `ADR-D8` and design `D-6` are the same subject under two IDs; sequence gate `G2` ≡ design `D-2`.)*

| # | Decision |
| --- | --- |
| ADR-D1 | `impacts` is a numeric annotation on `DRGEdge` and **subsumes** `in_tension_with`: `impacts < 0` **is** a tension claim |
| **ADR-D2** | **◆ Which relation carries `impacts` after retirement (≡ design D-2 / gate G2).** Recommendation (not a decision): a new `Relation.IMPACTS` — subsumption removes the earlier objection, since the relation type *is* `impacts` and the sign says how. **If the answer is "keep the name, retire only the lifecycle", I12 collapses to ~5–10 files and rank 16 is badly wrong** |
| ADR-D3 | **`impacts` is AUTHORED-ONLY. Never derived.** The moment anything derives it from value vectors, the subsumption is unsound and this becomes the option the superseded ADR rejected |
| ADR-D4 | Candidate-pair predicate: `relation == impacts and impacts < 0` — **strict sign, no tunable threshold** |
| ADR-D5 | `reconciles_tension` **survives**, re-pointed at negative-`impacts` pairs |
| ADR-D6 | `impacts` meaningful on the tension successor / `rejects` / `refines`; ignored elsewhere. **Prose, no per-relation table** — there is no totality guard for a `Relation`-keyed table |
| ADR-D7 | Composition is **first-order only** — measured, the second-order derivation claim is false (42/42 off-diagonal) |
| **ADR-D8** | The matrix is **symmetric**, authored as N(N−1)/2 unique pairs; the one asymmetric published pair is **CLOSED 2026-07-26 by amendment** (≡ design D-6): symmetrised to `+0.75`, headline residual 4.70% → 4.37%, gain 0.3892 → 0.3766. See § 10, Ruling 5 |
| ADR-D9 | The computed projection is a **frozen dataclass with no `model_dump()`** in a module no writer imports, stamped `matrix_id`/`matrix_version` |
| **ADR-D10** | **Ruling (d): the value set and matrix are N-parameterised.** Boundedness follows from coefficients ∈ [−1,1] + zero diagonal (Gershgorin); the validator enforces those two, **errors at gain ≥ 1−ε** (the series does not converge at the boundary) and **warns as gain → 1** |

**Retires:** `in_tension_with` as a relation member · the prior rejection of `Relation.IMPACTS` ·
the `0.25 × second_order` term · the convergence caveat · the "no superseding ADR needed" claim.

**Migrates:** the 2 authored edges (`directive.graph.yaml:90-93`, `:103-106`) to
`{relation: impacts, impacts: <negative>}` preserving each `reason`; the tension surface (1 dataclass + 5 functions, `consistency_check.py:917-1050`); `RELATION_DESCRIPTIONS` + verbatim doc parity, in one commit.

## 4. Tracker shape — report only

**Epics:** `#2466` (extensibility/packs, P1) absorbs I2, I3b/c, I19, the ADR, I12, I13.
`#2216` (governance tiers, P2, `blocked_by #2467`) absorbs I15 via `#2591`.

**Existing issues that absorb work — do not duplicate:** `#2591` (I15 entirely) · `#2538` (G3
entirely — add arm-B pre-registration as a comment **before** the run) · `#2080` (I5, README kind-table
drift, `RECONCILE_CHANGE_SCOPE_TENSIONS` delete-or-wire) · `#2468`/`#2847`/`#2862`/`#2829` are
**consumers** of I2, cross-link as `blocks`. `#2537` is **CLOSED** — do not reopen.

**Collisions:**

| # | Collision | Adjudication |
| --- | --- | --- |
| C1 | `#2532` (decompose `charter/context.py`) vs **I2 site 2** — the missing `else` is inside that module | **I2 first.** Cross-reference both so the decomposition cannot drop the `else`; assert it **behaviourally**, not by code shape, so it survives |
| C2 | **Four all-surface sweeps, not two:** `#2591` component-type · I1c `costs:` · I14 value fields · **I12 `impacts` across 774 edges** | **Do not batch any pair.** Each needs its own occurrence map. Order: `#2591` → I12 → I1c → I14 |
| C3 | Artefact-count divergence: 260 vs ~310 vs 41–59 | Use **260** for authoring burden, **41–59 files** for code surface. They measure different things |
| C4 | Lens disagreement on `toolguide` / `agent_profile` (design D-1) | Must be resolved before any WP touches the 12 model/schema files. Behind G3, so not urgent — but must not be discovered mid-mission |
| C5 | `#2934` P0 data-loss + 14 open P0s are the 3.2.x blocker *(as of 2026-07-26; #2934 closed that day)* | Constrains *when* anything lands. `#2538` was on 3.3.x (retired; now Product backlog), so G3 is not on the release path either way |

## 5. Explicitly parked

| Parked | Reason | Unpark on |
| --- | --- | --- |
| `0.25 × second_order` | Measured: not derivable (42/42 off-diagonal). Independently authored judgement | Upstream publishes independent provenance **and** a consumer exists |
| **Deriving `impacts` from value vectors** | The option the superseded ADR rejected, plus 5/5 false positives with overlapping bands | **Never** without a blind study clearing precision/recall (3 scorers × 20 artefacts, ~1 day) |
| `minItems: 1` mandatory-negative as schema | Gates on the least reliable field and inverts its outcome | **Never as schema.** The advisory lint is the shipping form |
| Mandatory `rationale` as hard constraint | Calibration corpus fails it (≥3 of 38) | ≥95% corpus compliance, measured, after I1a runs |
| A delta resolution grid | Rejects the corpus (`0.125`) | Never |
| Populating `Directive.severity` / `governance.enforcement` | **Permanently**, in favour of deletion | Never — a consumer must be designed first, at which point it is a new field |
| `manifesto` NodeKind / a new tier | 41–59 files, and no new kind is needed | Never as scoped |
| Computable squad coverage / collinearity | Zero prior art; depends on vectors that do not exist | Only if I14 ships for independent reasons |
| Outcomes tier | Downstream of an ungated prerequisite | Value tier shipped |
| Re-tier AMMERSE onto `glossary_pack` | Not in `extractor._KIND_MAP` — the edge would silently vanish | I2 landed **and** a consumer exists |
| I10 ranking function | Only remaining consumer is I8 | **UNPARKED 2026-07-26** — G4 answered "arithmetic" (operator ruling; §10). Must not rebuild the row-sum collapse (r≈0.98) or the vector-derived mechanism (0/6 reproductions); I8's perturbation probe is the cheapest instrument to falsify the arithmetic reading before more is built on it |
| I14 value fields | ~1,372–1,596 cells against a 34-vector calibration set | **CLOSED 2026-07-26, not deferred** — G3 is unreachable: the `#2538` rig is verified absent in-repo (§10). Unpark only if a rig materializes **and** a coverage gate is designed before the schema |
| I17 interview instrument | Closes the production-side laundering, gated on G3 + D-4 | **CLOSED 2026-07-26, not deferred** — same G3-unreachable finding as I14 (§10) |
| Batching any two all-surface sweeps | One unreviewable occurrence map | Structural. Never |

## 6. Upstream report

Two measured findings against the AMMERSE practice article: the probable sign error
(`Maintainable→Extensible +0.75` vs `Extensible→Maintainable −0.75`, sole asymmetry in 49 cells) and
the false derivation claim (`M×M` mismatches 49/49; six hypotheses rejected). **The sign-error
finding is CLOSED, not merely reported — see Ruling 5, §10.**

~~**Who: the operator, not an agent.** This is an external communication about a trademarked work
inside the accreditation relationship ruling (c) establishes.~~ **Superseded (§10, Ruling 5): no
external report is owed.** Ruling (c)'s accreditation relationship rests on the operator's prior
written consent from Crossland to use the AMMERSE idea and publish this procedure under his own
intellectual property; accreditation and mention discharge it in full. The sign-error repair is the
operator's own adjudication over his own procedure, not a call requiring Crossland's confirmation,
and there is no conversation it was waiting on.

**Where:** ~~(1) upstream, via the article's channel;~~ **struck — no upstream report is owed
(§10).** (2) in-repo as an `## Upstream discrepancies` section in the corpus README created by I9,
carrying both findings, the mismatch counts, the `accessed_on` URL, and a **`source_digest`** so a
later re-read detects an upstream fix — **kept, reframed as provenance hygiene for our own matrix,
not an accreditation deliverable (§10)**; (3) in the ADR — **D8 records the adjudication, CLOSED
2026-07-26 by amendment**, D7 cites the derivation finding.

**Sequencing constraint:** ~~the in-repo record must exist before I13 ships, because the validator
has to encode a decision about the asymmetric cell.~~ **Moot (§10): the decision already exists**
(symmetrised to `+0.75`), so the validator can encode it without waiting on the record. The in-repo
divergence record in item (2) above remains **recommended** for I13, not a blocking precondition.

~~**Safe default so nothing blocks:** take the symmetric reading; if ambiguous, set the cell to `0`
and record the abstention. Abstaining on 1 of 49 costs ~2% and **cannot** introduce a wrong
steer.~~ **Superseded (§10): the fallback was never exercised.** The pair is adjudicated —
symmetrised to `+0.75`, not zeroed — so I13 encodes that reading directly rather than the abstention
default.

## 7. Effort envelope

**Precedent anchors** (`git show --stat`): `d54470c83` glossary-pack kind = **41 files / +3,192**;
`1e3dc8d2c` TEMPLATE+ASSET = **48 / +2,183**; `ce9d20e6c` tension edges (added a relation, retired
one) = **59 / +3,845**. The 41–59 files / 2.2–3.8 kLOC figure reproduces exactly, and `ce9d20e6c` is
the directly analogous precedent for I12.

**Band totals:**

| Band | Ranks | Files | LOC | Wall |
| --- | --- | --- | --- | --- |
| Campsite, zero gates | 1–7 | ≈22–34 | 1.1–1.6k | **4–7 days** |
| Through the gates | 8–15 | ≈55–100 | 2.4–4.6k | 11–18 days |
| Post-gate, sweep-dominated | 16–22 | ≈95–150\* | 6–11k\* | 25–45 days\* |

\* **Adjusted 2026-07-26 (§10):** ranks 20 (I14) and 22 (I17) are CLOSED, not deferred — the
`#2538` rig they were gated on is verified absent in-repo. That directly removes their stated file
counts (14–18 + 5–10 = 19–28 files) from the row above and removes the entire unquantified
authoring tail (~1,372–1,596 cells) from the programme — it was I14's alone. No per-item LOC or
day breakdown existed for I14/I17 to subtract precisely from the 6–11k / 25–45-day figures, so
those two columns are carried forward as upper bounds pending a re-tabulation, not recomputed
here. Rank 21 (I10) stays in this band (unparked, not closed) at its existing 3-file / ~4h
estimate.

**~60–65% of the tabulated engineering cost is in the last band** (pre-2026-07-26 figure; falls
with the I14/I17 closure above). **Of the closed portion, I12 remains behind G2 (now CLEARED, §10);
I15 is behind `#2467`; I10 is behind G4 (now ANSWERED, §10); I13/I1c are behind no gate at all.**

**Landing overheads to budget:** every new `docs/` page needs inventory + index regeneration and
`relative_link_fixer --check`; `src/doctrine/` or prose changes need
`pytest tests/architectural/test_no_legacy_terminology.py` pre-push (CI-only gate); every new test
file appends to a shard tuple; every new `== N` needs a `# golden-count` marker; any sweep ≥ ~300
YAML files needs an `occurrence_map.yaml`.

**One correction to the implementer's plan:** land **I5 before I9** so the definition-parity test is
green on arrival, rather than landing it deliberately red. Main already carries 14 open P0 reds under
the honest-red policy; a deliberately red new test is indistinguishable from those, and the
predictable outcome is a future agent green-washing it. If I5 slips, land the parity test as
`xfail(strict=True)` with the ticket ID inline — never as a plain red.

## 8. Concession

Nothing was executed; every "breaks silently" claim is a static read. **D-2 is the load-bearing thing
this plan cannot settle, and the rank-16 estimate is hostage to it** — if the answer is "keep the
relation name", I12 drops from 45–60 files to 5–10 and the critical path shortens by about a week. A
driver who starts I12 before D-2 is answered is gambling a week. I12's sizing is an analogy to
`ce9d20e6c`, not a measurement of the retirement surface. The 260-vs-310-vs-41–59 divergence is
unresolved and the two largest items inherit that uncertainty. The `#2538` rig's liveness is
unverified by anyone, and G3 decays with it. C4 is a semantics call left to the design authority.
Ruling (b) removes any instrument for pricing the numeric layer's *value* — only its cost; G3 is the
only such instrument, and prior art predicts it reads null.

> **2026-07-26 update (§10):** both open items in this concession are now resolved. **D-2 is
> settled** — ADR `2026-07-26-3` (Accepted) chose Option A, so the rank-16 estimate is confirmed at
> 45–60 files, not hostage to it. **The `#2538` rig's liveness is no longer unverified** — it was
> checked this session (repo search + `git log --all -S` over its distinctive phrases across all
> branches) and found absent: every in-repo reference is a document, and nothing was ever committed
> or deleted under that name. This is an in-repo-only finding; it does not prove no such rig exists
> in the operator's own environment. G3 (and, with it, I14/I17) is closed on that basis, not merely
> decayed.

## 9. Verdict

**Ship ranks 1–4 as one campsite band: the zero-producer lint, the polarity lint, the
`generate_schemas --check` CI wiring, and the AMMERSE definition unification.** ≈9–12 files, under
0.7 kLOC, touching nothing another mission is editing; three of the four are pure campsite, and each
either produces evidence against a validation set that exists today or structurally guards an
increment further down — the zero-producer lint in particular is the only thing in this program that
mechanically prevents a fourth inert register. Then run **rank 5, the four-site silent-kind-drop
closure**, as the first real mission: four verified-OPEN issues wait on it, and it must land before
`impacts` touches an edge or the extractor deletes the field at regeneration. **The gate that
actually decides this program's shape is not `#2538` — it is D-2, inside the superseding ADR.**
`#2538` gates only the numeric branch, was on milestone 3.3.x (now Product backlog), and prior art predicts it reads null; D-2
gates a 45-to-60-file mission on the near path, is a one-document decision, and is the one question
that cannot be discovered during implementation. **Write the ADR in parallel with ranks 1–5 and
answer D-2 in it before anyone opens `extractor.py` with intent to add a field.**

> **2026-07-26 update:** carried out. See § 10 for the realization into five sequenced missions,
> the D-2/ADR-D2 closure, the D-3 operator ruling, and the `#2538` rig finding.

<a id="10-realization-amendment-2026-07-26"></a>

## 10. Realization & amendment — 2026-07-26

This section is an **addition**, not a rewrite: §§1–9 above are left as originally written except
for the specific rows and cells this section falsifies (each carries an inline `§10` pointer back
here). This is the operator's realization ruling plus two measurements and two decisions taken
against this document, on this branch, this session.

### (a) Realization into five sequenced missions

The 22 ranked increments in § 2 were split by operator ruling into five sequenced missions
(scaffolds already exist under `kitty-specs/`). Mission
`doctrine-canonical-structure-remediation-01KYEYSD` is the **programme record**: it carries the
spec that did this split, and does **not** itself implement — it has zero work packages.

| Mission | Slug | Increments (this document's numbering) |
| --- | --- | --- |
| **A** | `doctrine-silence-guards-01KYFV7Q` | Ranks 1, 3, 5, 6, 7 (I19, I3a, I2, I3b, I3c) + layout/enum ratchets, followable guidance, org→DRG bridge fix, `applies` hygiene |
| **B1** | `drg-relation-impacts-vocabulary-01KYFV87` | Rank 9 (the superseding ADR — written, Accepted), rank 16 (I12) |
| **B2** | `drg-edge-migration-extractor-retirement-01KYFV8C` | The 774-edge authored-edge migration and extractor edge-production retirement (broader than the original 22 increments; see the mission's own spec) |
| **C** | `test-quality-doctrine-series-01KYFV8H` | Rank 2 (I1a) + the original #2935 test-quality series deliverable |
| **D** | `foundational-values-creed-band-01KYFV8N` | Ranks 4, 10, 11, 12, 13 (reduced scope), 15, 17, 21 (I5, I9, I8, I16, I4-WP03, I6, I13, I10) |

**Mandatory order: A → B1 → B2 → C; D gates on A only** — unchanged from, and consistent with, the
critical-path ordering already established in § 1 (I2 cannot sequence after I12; the ADR is the
cheapest gate).

### (b) Two measurements taken this session

**Finding 1 — Gate G5 fails: the `#2538` experiment rig does not exist in-repo.** Checked: every
in-repo hit for `2538` (across `.py`, `.md`, `.yaml`) is a document — the superseded ADR, four plan
files, four squad reports, and the docs retrieval index — plus two `test_no_dead_symbols.py` hits
that are content-hash substrings, not references to the rig. No brief, fork fixtures,
pre-registration, or judge harness exists under `tests/`, `scripts/`, `src/`, or `.local/`, on this
branch or any other (checked via `git log --all -S` over the rig's distinctive phrases, e.g. "CSV
export to a reporting module", "Reproduction threshold" — the only hits are the commits that added
the *design* documents referencing the rig; nothing rig-specific was ever committed or deleted).
Issue #2538 itself confirms this: it says "Rig is standing. Run and results pending," is labeled
`priority:P2`, and sat in milestone 3.3.x (now Product backlog) — not release-critical.

**Consequence:** § 1's gate **G3 is unreachable**. Ranks **20 (I14) and 22 (I17) are CLOSED, not
deferred** — this removes the programme's entire unquantified authoring tail (~1,372–1,596 cells).
**Rank 13 (I4-WP03)** loses its only stated purpose (producing G3's arm B) and survives in mission
D on independent merit only. **Rank 12 (I16)** is unaffected — it keeps its independent merit (a
`primary`/`merge`-class footgun removal) by operator ruling, regardless of G3. **Rank 14 (the G3
run itself) is closed** as unreachable, not merely deferred.

**Caveat, stated explicitly:** this proves only that the rig is not in this repository. If it
exists in the operator's own environment, this finding — and the G3/I14/I17 closures that follow
from it — reverses.

**Finding 2 — Rank 4 (I5, AMMERSE definition unification): the second copy is FOUND, and the
estimate holds.** It is `src/doctrine/templates/architecture/ammerse-analysis-template.md`
(Markdown — an earlier search scoped to YAML missed it). All seven value definitions differ
between it and the tactic (`src/doctrine/tactics/built-in/analysis/ammerse-impact-analysis.tactic.yaml`):
the template carries compressed glosses, the tactic carries full text. Sharper than drift: the
tactic instructs "Use the canonical definitions **exactly as stated** … use these **verbatim** as
the scoring lens," then says "Use the AMMERSE Analysis template to structure the record" — and
`tactic:ammerse-impact-analysis --suggests--> template:ammerse-analysis-template` is a **live DRG
edge** (`src/doctrine/tactic.graph.yaml:405`). So an agent following the tactic is told to quote
verbatim and is routed by the graph to a second copy with seven different definitions — the §12
accreditation hazard, on a shipped path. This does not change rank 4's row (the estimate was
already right); it confirms **I5 does not collapse to a parity test** — the unification must cover
both surfaces.

### Two rulings this session

**Ruling 3 — Gate G2 / ADR-D2 is CLOSED.**
[`docs/adr/3.x/2026-07-26-3-impacts-edge-subsumes-in-tension-with.md`](../../adr/3.x/2026-07-26-3-impacts-edge-subsumes-in-tension-with.md)
(Accepted 2026-07-26) decided it: a new `Relation.IMPACTS` (**Option A**). The operator overruled
the reviewing analysis's evidence-per-cost recommendation of Option B, accepting the ~45–60-file
cost knowingly. § 8's Concession — "D-2 is the load-bearing thing this plan cannot settle" — is now
settled; the rank-16 estimate is confirmed at 45–60 files, not reduced, since Option A (the
expensive one) was chosen.

**Ruling 4 — operator ruling on design decision D-3: ARITHMETIC.** The creed feeds a ranking
function; it is not read as prose. **Rank 21 (I10) UNPARKS** into mission D. Recorded alongside it,
per the design authority's own measurements: creed-weighted ranking collapses to row-sum at
r ≈ 0.98, and vector-derived precedence scored 0 reproductions of 6. I10 must not rebuild either
mechanism; I8's perturbation-stability probe is the cheapest instrument that can falsify the
arithmetic reading before anything further is built on it.

**Ruling 5 — design decision D-6 / ADR-D8 is CLOSED: the asymmetric pair is a sign error,
repaired by symmetrising to `+0.75`.** Recorded as an amendment to
[ADR `2026-07-26-3`](../../adr/3.x/2026-07-26-3-impacts-edge-subsumes-in-tension-with.md)
(§ 3's status blockquote and ADR-D8 row above are updated in place, since they describe the ADR's
current state rather than a point-in-time finding). The adopted claim is that maintainability and
extensibility **reinforce** each other; the published `−0.75` cell is the errant one. **Headline
residual moves 4.70% → 4.37%, per-step gain 0.3892 → 0.3766** (reproduced via
`_reproduce_matrix_findings.py`). This unblocks I13's validator (rank 17, mission **D**) fully — it
no longer waits on anything.

**Basis, stated plainly:** this is **the operator's own adjudication, on his own authority over his
own analysis procedure** — not upstream authorial confirmation from Crossland, who authored the
AMMERSE value system itself. The operator holds Crossland's prior written consent to use the
AMMERSE idea and publish this procedure under his own intellectual property; accreditation (§12 of
the design authority) discharges that relationship in full. **§6 above is corrected in place**: no
external report is owed, there is no conversation the adjudication was front-running, and the
in-repo divergence record item (2) of §6 is retained as **provenance for our own matrix** — useful
so a future reader knows where and why it diverges from the published one, and so a `source_digest`
can catch an upstream change later — not as an accreditation deliverable or a precondition on I13
shipping. The safe-default fallback (§6's "take the symmetric reading; if ambiguous, zero the
cell") was never exercised: the adjudicated reading is `+0.75`, not the abstention default.
