---
title: Glossary Chokepoint p95 Latency Measurement
description: 'Confirms the 50 ms p95 budget for the glossary chokepoint with measured sub-linear scaling, keeping the per-step semantic scan off the agent loop critical path.'
status: Accepted
doc_status: active
kind: ADR
date: '2026-04-22'
---

## Context and Problem Statement

`GlossaryChokepoint.run()` is invoked on every agent step to scan request text
for semantic conflicts.  It must complete well within the human-perceptible
threshold so that the scan never becomes a bottleneck in the agent loop.

The design target was **p95 ≤ 50 ms** for all realistic input sizes.  This ADR
records the measured performance to confirm or revise that threshold.

---

## Benchmark Setup

Benchmark script: `tests/specify_cli/glossary/bench_chokepoint.py`

| Parameter | Value |
|-----------|-------|
| Synthetic term index | 500 active SPEC_KITTY_CORE terms |
| Iterations per input size | 1 000 (after 10 warm-up) |
| Input sizes tested | 500 words, 2 000 words, 5 000 words |
| Term hit rate in texts | ~20 % (deliberate over-representation) |
| Platform | macOS Darwin 24.6.0, Python 3.14.0 |

Approximately 20 % of tokens in the generated texts were drawn from the
synthetic index, which is a deliberate over-representation of realistic
inputs.  Real agent requests typically contain far fewer glossary terms.

---

## Measured Results

Benchmark executed on 2026-04-22.

| Input size (words) | mean | p50 | p95 | p99 |
|--------------------|------|-----|-----|-----|
| 500 | 2.28 ms | 2.19 ms | **2.44 ms** | 4.03 ms |
| 2 000 | 8.88 ms | 8.79 ms | **9.16 ms** | 9.67 ms |
| 5 000 | 22.19 ms | 21.91 ms | **22.85 ms** | 26.70 ms |

All three input sizes pass p95 ≤ 50 ms comfortably.

---

## Decision

**Threshold confirmed: p95 ≤ 50 ms.**

The measured p95 values fall well below the 50 ms target at every tested
input size.  The design constraint is satisfied without modification.

Key observations:

1. **Latency scales sub-linearly with input size.**  A 10× input increase
   (500 → 5 000 words) yields only a ~9× p95 increase (2.44 ms → 22.85 ms),
   thanks to the per-token deduplication and the O(1) dictionary lookup in
   `GlossaryTermIndex.surface_to_senses`.

2. **Index load is amortised.**  `_load_index()` is called at most once per
   `GlossaryChokepoint` instance.  The benchmark pre-loads the index before
   timed iterations, matching production behaviour where the chokepoint is
   constructed once and reused across many calls.

3. **Headroom is substantial.**  Even at 5 000 words the p95 is 22.85 ms —
   less than half the threshold.  This leaves room for future index growth
   (e.g. 2 000+ terms) before the threshold becomes a concern.

---

## Consequences

### Positive

- The 50 ms p95 threshold is confirmed as a realistic operating constraint.
- No performance-driven architecture changes are needed at this time.
- CI tests can run without special hardware; the chokepoint adds negligible
  latency to the existing test suite (< 1 ms per call in tests).

### Negative

- None identified.

### Neutral

- The threshold should be re-measured if the index grows beyond ~5 000 terms
  or if a new text pre-processing step (e.g. NLP tokenisation) is added.
- The benchmark script (`bench_chokepoint.py`) is **not** part of the CI suite;
  it must be run manually when the chokepoint implementation changes.

---

## Re-measurement Trigger Conditions

Re-run `tests/specify_cli/glossary/bench_chokepoint.py` and update this ADR if:

1. The `GlossaryTermIndex` grows to more than 5 000 active terms.
2. `_run_inner()` is modified to call additional I/O-bound operations.
3. A new text pre-processing step (e.g. sentence segmentation, NLP) is added
   before the tokenisation loop.
4. The runtime target platform changes significantly (e.g. from macOS to a
   resource-constrained container).

---

## Related Documents

- `src/specify_cli/glossary/chokepoint.py` — implementation
- `tests/specify_cli/glossary/bench_chokepoint.py` — benchmark script
- `tests/specify_cli/glossary/test_chokepoint.py` — unit tests (T014)
- WP01 ADR: `architecture/adrs/2026-04-09-1-mission-identity-uses-ulid-not-sequential-prefix.md`
