---
title: Verification round — three-lens review of the finalized authorities
description: "Final review squad before handover: sequence executability, fresh-eyes fix verification, and adversarial number-by-number reproduction. Verdict plus the applied fix list."
doc_status: deprecated
updated: '2026-07-26'
related:
- docs/plans/doctrine/foundational-values-and-creed.md
- docs/plans/doctrine/manifesto-program-delivery-sequence.md
- docs/plans/doctrine/README.md
---
# Verification round — three-lens review of the finalized authorities

> **Retired (deprecated).** Superseded by the canonical creed AUTHORITY doc [foundational-values-and-creed.md](../foundational-values-and-creed.md). Preserved as a historical record.

> **EVIDENCE + the applied fix record.** Three profile-loaded lenses ran read-only against the
> corpus at `0fcb4b3d2` after the publication-readiness rewrite. Every finding below marked ✅ was
> **applied in the finalization commit**; the authorities are post-fix. This file is the record of
> what the round found and what changed.

## Aggregated verdict

**The measurements hold up; the coordination layer needed one more pass — and got it.**

- **The reproducibility claim is substantially TRUE, and unusually strong.** The debugger lens
  recomputed ~60 figures by deliberately independent methods (characteristic polynomial +
  Durand–Kerner instead of the script's power iteration; its own Jacobi PCA instead of trusting
  any published series). **Every substantive number in §6.1–6.4, §10.2, the negative-cell census,
  and all five grep counts reproduced — most to more decimals than published.** Exactly two
  published figures were off: a mean (0.3842 → **0.3841**) and a symmetry count (48/49 → **47/49
  cells; one asymmetric pair of 21**). Neither moves any conclusion.
- **Two genuine HIGH defects were found in the maths layer, both now fixed:**
  1. **The reference spectral-radius method was fail-open** (F-1). Power iteration from a fixed
     all-ones start reports gain **0.33** for a two-camp ±1 basis whose true gain is exactly
     **1.0** — because all-ones is an eigenvector of a *smaller* eigenvalue. AMMERSE's own figures
     were never affected (real dominant eigenvalue, non-deficient start), but the method would
     have shipped into the validator §6.2 calls load-bearing at exactly the boundary case. **Fix
     applied:** the committed script now uses seeded random restarts (verified: reports 3.0/2.0
     correctly on both counterexamples, AMMERSE unchanged), and §6.2 documents the hazard.
  2. **The `(1−r)` bounding claim confused the spectral norm with the sup-norm** (F-2). A per-axis
     [−1, 1] guarantee is an ℓ∞ statement; the tight two-term constant is `1/(1+r∞)` with
     `r∞ = 0.5·max_row_abs_sum/(N−1)` — **0.75** for AMMERSE (verified exactly tight: worst
     admissible ±1 base lands at 1.000000, while `(1−r) = 0.8054` overflows to **1.074**). And no
     fixed constant bounds a *sum* of deltas — the active-set composition must clamp or average
     first, recorded as an open design consequence. **Fix applied** in §6.4 + register.
- **The sequence document — the one authority that never had a review pass — turned out to carry
  the fewest unverifiable claims** (all seven of its `file:line` citations resolve, six exactly;
  all three precedent anchors reproduce to the file and line), **but its coordination layer had
  five executable blockers**, all now fixed: a decision-ID namespace collision (`Dn` ADR decisions
  vs `D-n` design decisions, colliding on different meanings → renamed **`ADR-Dn`**); a false
  "last band entirely behind G2/G3" claim (truth: roughly half — I15 is behind `#2467`, I10 behind
  G4, I13/I1c ungated); two missing increments in the critical path (I3c, I8) and an unranked gate
  (G5); the `consistency_check` re-point range excluding one function it must re-point
  (934→**917**); and two surviving pre-review `49/49` figures.
- **The design doc's §0 ask was priced on the wrong band** (fresh-eyes lens): the "Prose-only (§8)"
  row carried the ranks-1–4 campsite figures, while §8's own `costs:` field is sequence rank 19
  with a 196–228-artefact authoring sweep. **Fixed:** the row is relabeled, §8 is priced honestly,
  and the headline "~85% behind two gates" — which reproduced from no column of the effort table —
  is now "**~60–65% of tabulated engineering cost in the final band, roughly half of it behind the
  two gates, the authoring tail entirely behind `#2538`**".
- **The 1,820-cell figure was never re-derived after §7.4 narrowed the kind set** — it counted
  toolguide/step-contract/glossary_pack artefacts the design excludes. Canonical: **~1,372–1,596**
  (196–228 × 7). Fixed in both authorities + register.
- **The register's own account of the superseded "~6%" was wrong** (it said "undamped three-term",
  which is 9.65%; the 6% was `gain³ = 5.89%`, the first-omitted-term magnitude). Fixed — the one
  row that cannot afford to be wrong is the one explaining a previous error.
- **Corpus-wide figure hygiene:** the evidence docs still published superseded numbers with no
  pointer (the matrix-measurement doc even *endorses the three-term composition the authority
  forbids*). **Fixed:** superseded banners on `connascence-matrix-measurement.md`,
  `creed-and-values-design-hardened.md`, `creed-and-values-design-as-proposed.md`,
  `manifesto-tier-verdict-and-handover.md`, and `squad-reports/reviewer.md`; six new rows in the
  authority's §11 register.

**Net:** nothing found moves the architecture. Everything found moves a number, a label, or a
pointer — and the two HIGH maths defects were in the *reference implementation and one bounding
sentence*, not in any adopted result. The published second-order matrices are now committed
(`_ammerse-second-order.json`), closing the one evidence gap where the most consequential
empirical claim (the false upstream derivation) was uncheckable.

## Fix ledger

| # | Finding (lens) | Severity | Status |
| --- | --- | --- | --- |
| 1 | Spectral-radius method fail-open on deficient start vectors (debugger F-1) | HIGH | ✅ script: seeded random restarts; §6.2 hazard note |
| 2 | `(1−r)` does not bound output in sup-norm; tight constant 0.75; sums unbounded (debugger F-2) | HIGH | ✅ §6.4 rewritten; register row |
| 3 | §0 cost row prices ranks 1–4 as "Prose-only (§8)" (patterns) | HIGH | ✅ relabeled + §8 priced honestly |
| 4 | 1,820 cells uses pre-§7.4 superset (patterns) | HIGH | ✅ ~1,372–1,596 in both authorities + register |
| 5 | `Dn`/`D-n` namespace collision, 3 pairs mean different things (architect) | HIGH | ✅ `ADR-Dn` rename + namespace note |
| 6 | "Last band entirely behind G2/G3" false (architect) | HIGH | ✅ corrected in both authorities |
| 7 | "48 of 49 symmetric" arithmetically impossible (architect + debugger F-3) | HIGH | ✅ "one asymmetric pair of 21 (47/49 cells)" in both docs + JSON |
| 8 | Register row 1's "6% = undamped three-term" contradicts §6.1 (patterns + debugger F-6) | MEDIUM | ✅ corrected attribution (`gain³ = 5.89%`, first-omitted-term) |
| 9 | Second-order matrix not committed — key evidence uncheckable (debugger F-5) | MEDIUM | ✅ `_ammerse-second-order.json` committed (raw + normalised) |
| 10 | `49/49` survivals in sequence doc (architect) | MEDIUM | ✅ → 42/42 off-diagonal |
| 11 | "~85% behind two gates" not derivable (architect + patterns) | MEDIUM | ✅ → ~60–65% + half-band + tail statement |
| 12 | I3c, I8 missing from critical path; G5 unranked (architect) | MEDIUM | ✅ added; gate-order legend note |
| 13 | G3-gated set listed I10 (architect) | MEDIUM | ✅ I10 → G4 |
| 14 | `consistency_check` range 934→917; "7 functions" → 1 dataclass + 5 (architect) | MEDIUM | ✅ |
| 15 | JSON missing `matrix_version` + `source_digest` (architect) | MEDIUM | ✅ both added, digest scope stated |
| 16 | §6.2 heading "non-degenerate" asserts unproven equivalence (patterns) | MEDIUM | ✅ heading → "sound for gain < 1" |
| 17 | §7.2 "five of seven axes" → six (patterns) | MEDIUM | ✅ |
| 18 | §6.5 "32 of 49" → 32 of 42 off-diagonal (patterns) | MEDIUM | ✅ |
| 19 | ~47,900 basis unstated; 260-vs-310 divergence unregistered (patterns) | MEDIUM | ✅ inline basis + register row |
| 20 | Stale-figure banners on 5 RECORD/EVIDENCE docs (patterns) | MEDIUM | ✅ |
| 21 | PCA convention unstated — correlation-PCA readers get 75.7% (debugger) | MEDIUM | ✅ convention clause in §10.2 |
| 22 | Mean 0.3842 → 0.3841 (debugger F-4) | LOW | ✅ doc + script |
| 23 | Script positional cell indexing vs §4's by-id rule (debugger F-7) | LOW | ✅ `axes.index()` |
| 24 | Reproducibility claim scope (banner bullet 2) (debugger F-5) | LOW | ✅ scoped per file |
| 25 | Sweep figure needs `SAMPLES=30000` note (architect) | LOW | ✅ env-var override + note |
| 26 | Walker citation `:507` → `:507-509`; "4 elif" → "4 kind branches"; base-commit bumps; gate-order legend | LOW | ✅ |

**Deliberately not applied:** renumbering gates to path order (stable IDs preferred; legend added
instead); moving §9.3/§11 mechanics out of the design doc (the standalone review version handles
digestibility separately); the correlation-PSD third constraint (recorded as a candidate in §6.2,
not adopted — it is a design choice, not a fix).

## What the lenses could not verify (carried forward honestly)

- **Tracker states** (`#2466`, `#2467`, `#2532`, `#2538`, `#2591`, `#2934`, the four I2 consumers)
  — no lens audited them this round; the sequence doc's §4 collision adjudications rest on the
  planning round's checks.
- **The `#2538` rig's liveness** — still unverified by anyone; G3 decays with it (G5 exists for
  exactly this reason).
- **The upstream prose quotations** (the "decidedly not minimal" class) — the corpus JSON carries
  ids and vectors only; the 11-of-12 prose split is verified against numbers, not against the
  upstream text, which is not committed.
- **The 38→37 tiers of the corpus ladder** — upstream-only; the committed JSON starts at 36.
- **The Dirichlet ranking-collapse table** in the hardened RECORD doc — no seed or code was ever
  committed for it; it remains non-reproducible and is banner-flagged as a superseded objection.

## Lens verdicts, condensed

- **Architect:** *"Not as-is, but the gap is one editing pass, not a rewrite… the document that
  never had a review pass is carrying fewer unverifiable claims than the one that did, because it
  is the only one that cites line numbers at all."* → the editing pass is applied.
- **Patterns (fresh eyes):** *"Nothing I found moves the architecture, everything I found moves a
  number… hand it to the human reviewer, with the §0 cost table fixed first."* → fixed.
- **Debugger:** *"Reproducibility of the published figures: verified. Reproducibility of the
  evidence base, and soundness of the method carried forward into a validator: not yet."* → the
  second-order JSON is committed and the method is restart-hardened; both gaps closed.
