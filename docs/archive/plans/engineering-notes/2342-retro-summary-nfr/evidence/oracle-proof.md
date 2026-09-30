---
title: "Flippable-oracle proof (#2342)"
description: "Flippable-oracle proof for spec-kitty #2342: the raw 5.0s budget oracle cannot flip on this hardware, so a calibrated relative-delta oracle was used for the bisection."
doc_status: closeout
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
---

# Flippable-oracle proof — retro-summary NFR investigation (#2342)

## Why a raw `assert elapsed < 5.0` oracle is not usable here

The local dev machine used for this investigation is markedly faster than
the CI runner: every commit in the candidate window (see `bisect.log`) reads
between **1.17s and 1.57s** median wall-time for `build_summary` over the
200-mission corpus — roughly **3.5-4x faster** than the two CI readings that
triggered the quarantine (5.10s / 5.11s on PR #2336, unrelated diffs).

To confirm the raw budget oracle is genuinely unusable (not just "probably"
unusable), a synthetic **calibration regression** was injected: a
`time.sleep(0.01)` per mission (`+0.01s x 200 = +2.0s` on top of the
~1.2s baseline) was added at the `record = read_record(retro_path)` call
site in a scratch copy of `summary.py`. Measured result:

```
src=<injected-bad-src>/src runs=[4.364440911973361, 3.598804328008555, 3.595119679986965]
MEDIAN 3.5988
```

**Even a synthetic +2.0s injected regression (nearly 2x the actual CI
breach margin) only reaches ~3.6s median — still comfortably under the
5.0s budget on this hardware.** This proves conclusively that the raw
`assert elapsed < 5.0` oracle cannot be made to flip on this machine for
any regression in the plausible size range that would explain the CI
breach; `git bisect run` with that oracle would mark every commit GOOD
regardless of ground truth (the exact false-GOOD trap flagged in the plan).

## The relative-delta oracle used instead

**Oracle**: median of 5 unprofiled `build_summary(<200-mission corpus>)`
wall-time samples per commit. **BAD if median > 1.8s** (~1.5x the ~1.2s
observed baseline floor across the whole window).

**Proof this oracle flips** (the required calibration, per the plan's
C-005-style rigor requirement): the same +2.0s synthetic injection above
was run through the identical measurement harness (`bisect_probe.py`) and
threshold:

| Input | Median | Verdict (threshold 1.8s) |
|---|---|---|
| HEAD (`254613f5e`), unmodified | ~1.20-1.38s (multiple samples) | GOOD |
| HEAD + synthetic `+0.01s/mission` injection | 3.5988s | **BAD** |

The oracle correctly flips GOOD → BAD when a genuine ~2-second regression is
present. It is not an inert/broken instrument — it simply found no commit in
the real `reader.py`/`schema.py`/`summary.py` history that reaches anywhere
near that size of regression (see `bisect.log`: max observed non-crash
median across all 9 real commits was 1.57s, well under the 1.8s threshold
and the 3.6s calibration point).

## Honest limitation

This oracle is calibrated to reliably catch regressions on the order of
**hundreds of milliseconds to seconds** — the scale that would plausibly
explain a budget breach of this size. Run-to-run noise on this hardware was
observed up to ~20-50% within a single commit (e.g. a single 1.82s outlier
run at `ecf45f52c` against a 1.37s median). A **small** (roughly 5-15%)
creeping regression could not be reliably distinguished from that noise
floor with this method and sample size, and is not ruled out by this
investigation. This limitation is disclosed in the report rather than
silently assumed away.

## Reproduction (independently confirmed)

The committed `profile_harness.py` regenerates the baseline numbers directly
(`python profile_harness.py 7`). The calibration BAD point above is
reproducible-by-instruction — it is exactly `profile_harness`'s corpus run
with a **one-line `time.sleep(0.01)` added per `read_record` call** (`+2.0s`
across the 200-mission corpus). An independent pre-merge reviewer reconstructed
this and measured baseline **1.3947s → injected 3.6238s** (vs the 3.5988s
recorded here — within 0.03s), and re-derived the phase split (yaml_parse
88.9%). The scratch injection/sweep probe (`bisect_probe.py`) is intentionally
`.gitignore`d (it hard-codes throwaway paths); the numbers it produced are the
`bisect.log` sweep medians, which are reproducible via the documented method
above but are not, as shipped, a one-command re-run. Note: the real candidate
window is **10** commits (`git log -- reader.py schema.py summary.py`), not 9 as
an earlier line in `bisect.log` states — the extra commit is a no-op
literal→constant swap (`ecf45f52c`, #2119) and does not change the sweep result.

## What this does NOT prove

It does not prove CI's own hardware reads the same way — CI absolute
seconds are not directly comparable to local absolute seconds (per the
spec's Assumptions and Edge Cases). The relative finding (no discrete
regression in the candidate window, on this hardware, at the scale this
oracle can detect) stands independent of that gap; the absolute-time gap
between local (~1.2-1.4s) and CI (5.10-5.11s) is itself evidence pointing
toward CI-runner-class variance rather than an in-repo code regression —
see `report.md`.
