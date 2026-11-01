---
title: Connascence-matrix measurement
description: "Measured analysis of the AMMERSE first- and second-order impact matrices: spectral radius, truncation soundness, the false derivation claim, and the one asymmetric cell."
doc_status: deprecated
updated: '2026-07-26'
related:
- docs/plans/doctrine/foundational-values-and-creed.md
---
# Connascence-matrix analysis — measured 2026-07-26

> **Retired (deprecated).** Superseded by the canonical creed AUTHORITY doc [foundational-values-and-creed.md](../../../../plans/doctrine/foundational-values-and-creed.md). Preserved as a historical record.

> ⚠️ **SUPERSEDED MATHS — read [`foundational-values-and-creed.md`](../../../../plans/doctrine/foundational-values-and-creed.md) §6 and §11 instead.**
> This evidence file endorses the three-term composition (`base + 0.5×fo + 0.25×so`) and quotes a
> "~6%" residual; the adopted design is **two-term damped** (residual **4.70%**) and **rejects
> second-order outright**. Its "49/49" mismatch count is now stated as **42/42 off-diagonal**, and
> "48 of 49 symmetric" as **one asymmetric pair of 21 (47/49 cells)**. Kept verbatim as the
> measurement record.

Source: `https://patterns.sddevelopment.be/practices/ammerse_impact_analysis/`.
Coefficients now available (previously not in-repo). All results computed, not asserted.

## 1. The truncation is SOUND — the design's central maths question is answered favourably

First-order matrix `M` (7×7, rows = impacting value, cols = impacted).

- **Dominant |eigenvalue| λ = 2.3350** (power iteration, 3000 iters)
- Max abs row sum (upper bound) = 4.0000
- AMMERSE applies **divisor 6** in the formula
- **Effective per-step gain λ/6 = 0.3892 < 1** ⇒ the Neumann series converges
- **Truncation error after two terms is governed by (λ/6)³ ≈ 0.0589 (~6%)**

> `base + 0.5×first_order + 0.25×second_order` is a legitimate limited-horizon truncation with
> ~6% residual. "Good enough for government work" is **quantitatively defensible here.** This
> retires the convergence objection.

## 2. The second-order matrix is NOT derivable from the first-order one

The article states second-order values are obtained *"by multiplying the first-order impact
matrix with itself."* **Tested and false.** Hypotheses tried, mismatches out of 49 cells:

| Hypothesis | Mismatches |
| --- | --- |
| `M×M` (as published claim) | **49/49** |
| `M×M` with diagonal zeroed | 42/49 |
| indirect paths only, `Σ_{k≠i,j} M[i][k]·M[k][j]` | 42/49 |
| `M + 0.5·(M×M)`, diagonal zeroed | 40/49 |
| `1.75 × M` | 32/49 (best fit, still wrong) |
| first-order with diagonal zeroed | 42/49 |

The published normalisation is also not `raw / max|raw|`: for the Agile row that gives
`[0, −0.58, 0.29, 0.12, −0.88, 0.58, 0.50]` against the published
`[0, −0.69, 0.25, 0.05, −1.00, 0.82, 0.56]`.

**Consequence:** the second-order matrix is **independently authored judgement**, not a computed
ripple. Two design implications:

1. The `0.25 × second_order` term is a **second independent input**, so it needs its own
   provenance record — it cannot inherit the first-order matrix's.
2. The composition invariant ("authored `delta` is the only persistable term; the matrix supplies
   derived ripple") holds for first-order and **does not hold** for second-order.

**Recommendation: use first-order only.** The existing in-repo tactic already calls first-order
"the standard path" and second-order "high-stakes only". That guidance is now backed by a
measurement rather than a preference — and first-order alone carries the sound λ/6 = 0.389 gain.

## 3. One probable typo in the published first-order matrix

The first-order matrix is symmetric in **48 of 49** cells. The single exception:

- `Maintainable → Extensible = +0.75`
- `Extensible → Maintainable = −0.75`

The published *second-order* matrix is **fully symmetric (0 asymmetric pairs)**. Given the
surrounding symmetry, this is very likely a sign error worth reporting upstream. It matters
because it is the one cell that would make the matrix directional, and any consumer must decide
which sign to trust.

## 4. The matrix is symmetric — which vindicates the "correlation" framing *for the matrix*

An earlier review argued the authored number is a **gain**, not a correlation, because
correlation is symmetric while causal links are directed. Measured: the connascence matrix **is
symmetric** (48/49, see §3), i.e. correlation-shaped, not gain-shaped.

So both framings are right, in different places:

| Artefact | Shape | Right name |
| --- | --- | --- |
| **Value↔value connascence matrix** | symmetric | **correlation-like** — the operator's framing is correct here |
| **Node→node `impacts` edge** | directed | **gain / elasticity** — directed, so not a correlation |
| **Artefact→value `delta`** | directed, intervention effect | **effect of adopting**, neither of the above |

The earlier "it's a gain not a correlation" correction applies to the **edges**, not to the
matrix. Withdraw it for the matrix.

---

## 5. The absolutism problem — diagnosed, and it is the renormalisation

**Operator's concern:** iterating past tertiary effects over-amplifies the signal and converges on
1s, 0s and −1s; a dampening effect (lowering each tier's relative weight) was attempted, but the
maths was unverified.

**Verdict: the concern is real and correctly observed, the dampening is sound and in fact
conservative, but the cause is NOT the iteration. It is the per-tier max-renormalisation.**

### 5.1 With per-tier renormalisation: absolutism is provable, not incidental

Renormalising after each matrix application *is* **power iteration**. `M^k·v / ‖M^k·v‖` converges to
the dominant eigenvector regardless of the starting vector. So every artefact's higher-order profile
converges to the **same** pattern, and the base vector's identity is destroyed.

Demonstrated with three deliberately dissimilar starting artefacts, renormalised each tier:

| Artefact | tier 3 | tier 5 |
| --- | --- | --- |
| rigour-heavy | `[1.0, 0.37, −0.06, 0.07, 0.27, −0.30, 0.61]` | `[1.0, 0.47, −0.36, 0.03, 0.43, −0.57, 0.63]` |
| velocity-heavy | `[−0.62, 1.0, 0.52, 0.35, 0.89, 0.71, −0.82]` | `[−0.61, 1.0, 0.43, 0.32, 0.95, 0.56, −0.82]` |
| `safe_to_fail` | `[0.05, 0.72, 0.66, 0.25, 0.02, 1.0, −0.13]` | `[−0.46, 1.0, 0.66, 0.36, 0.74, 0.86, −0.76]` |

All three migrate toward the same attractor — the **dominant eigenvector of M**:

> Agile **−0.55** · Minimal **+1.00** · Maintainable **+0.35** · Environmental **+0.30** ·
> Reachable **+0.97** · Solvable **+0.46** · Extensible **−0.77**

Under renormalisation, every artefact eventually "says" Minimal-and-Reachable-maximal,
Agile-and-Extensible-negative. That is the absolutism, and values piling onto ±1 and 0 is its
signature. Note the published *normalised* second-order matrix contains cells at exactly −1 and +1 —
the fingerprint of max-normalisation.

### 5.2 Without renormalisation, the dampening already solves it — with room to spare

Per-tier contribution `(1/2)^(k−1) · (M^(k−1)·b) / (N−1)^(k−1)`, so the decay ratio is

```
r = 0.5 × λ/(N−1) = 0.5 × 0.3892 = 0.1946
```

Measured contribution norms for a real artefact (`safe_to_fail`):

| Tier | Contribution norm | Cumulative |
| --- | --- | --- |
| 1 (base) | 1.2971 | 1.2971 |
| 2 | 0.1215 | 1.3135 |
| 3 | 0.0123 | 1.3234 |
| 4 | 0.0014 | 1.3239 |
| 5 | 0.0002 | 1.3239 |

- **Tail beyond tier 3 = 0.91% of base.** Stopping at tertiary is not a compromise; it is already
  past the point of measurable difference.
- **Tail beyond tier 2 = 4.70%.** Two tiers would also be defensible.
- **Even undamped it converges** — ratio 0.3892, tail beyond tier 3 ≈ 9.6%. The divergence fear was
  unfounded in both cases; saturation came entirely from renormalising.

### 5.3 The fix: one final scaling, never per-tier

Since `|base| ≤ 1` element-wise, the composed value is bounded by the series sum
`S = 1/(1−r) = 1.2416`. So scale **once, at the end**, by `(1−r) = 0.8054`:

```
composed(v) = (1−r) × [ base(v) + Σ_{k≥2} (1/2)^(k−1) · (M^(k−1)·base)(v) / (N−1)^(k−1) ]
```

Verified on three real corpus artefacts: every output lands inside [−1, 1], and because every
artefact is multiplied by the **same constant**, all relative ordering is preserved exactly.

| Artefact | base max\|·\| | output max\|·\| | in range |
| --- | --- | --- | --- |
| `safe_to_fail` | 0.90 | 0.740 | ✓ |
| `avoid_gold_plating` | 0.70 | 0.640 | ✓ |
| `AMMERSE_impact_analysis` | 0.60 | 0.438 | ✓ |

**Generic over N:** `r = 0.5 × λ/(N−1)` and `λ ≤ N−1` (§1), so `r ≤ 0.5` for any admissible
consumer basis, giving `S ≤ 2` and a final scale never below 0.5. The rule holds for any value
system, and both `λ` and `N` are computable from the supplied matrix.

### 5.4 Consequences for the design

1. **Drop per-tier renormalisation. Keep the dampening.** The dampening was the right instinct; the
   renormalisation was silently undoing it.
2. **This is a second, independent reason to use first-order only.** The published second-order
   matrix has already been max-normalised, so consuming it as-is imports the very step that causes
   absolutism.
3. **Truncation depth becomes a free choice** rather than a defensive one: tertiary leaves <1%,
   secondary <5%. Pick on taste, and record the number.
4. **`r` is a useful reportable diagnostic.** As `r → 0.5` the basis is approaching total agreement
   and the higher tiers stop adding information — the same degeneracy warning as §1, from the other
   direction.
