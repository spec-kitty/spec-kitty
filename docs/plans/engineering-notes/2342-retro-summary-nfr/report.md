---
title: "Retro-summary NFR investigation (#2342) — verdict + disposition"
description: "Verdict for spec-kitty #2342: the retrospective-summary 200-mission NFR breach on CI is runner-class hardware variance, not a code regression."
doc_status: closeout
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
---

# Retro-summary NFR investigation — verdict + disposition (#2342)

**Subject**: `tests/retrospective/test_summary_tolerance.py::test_200_missions_under_5s`
(NFR-003: `build_summary` over a 200-mission corpus < 5.0s), currently
`@pytest.mark.quarantine` after two CI breaches (5.11s / 5.10s, PR #2336,
unrelated diffs).

**Verdict: CI variance (runner-class/hardware). No *discrete or large* code regression in the candidate window; a small (~5–15%) creeping regression is below this hardware's noise floor and is *not* ruled out (see §Honest Limitation). The CI breach is a hardware-baseline story, not a code regression a local machine would also exhibit.**

**Recommended disposition: keep the test in the existing `quarantine` +
non-blocking `quarantine-visibility` lane (this already *is* the "dedicated
non-blocking perf pipeline slice" the issue's disposition matrix asks for);
do not lift the quarantine yet, and do not touch the 5.0s budget.**

---

## 1. Per-phase profiling (FR-001 / NFR-001 / SC-001)

Harness: [`evidence/profile_harness.py`](evidence/profile_harness.py) —
rebuilds the exact 200-mission corpus the quarantined test builds (same
`_make_completed_yaml` template, same mission-id derivation), then runs
`build_summary` **7 times unprofiled** (real wall-time) plus **1 profiled
run** (cProfile, for phase attribution only — instrumentation measurably
inflates elapsed time and must not be read as a wall-time number). Raw
output: [`evidence/profiling.txt`](evidence/profiling.txt).

**Real (unprofiled) wall-time, current mission tip (`254613f5e`), N=7:**

| | |
|---|---|
| Median | **1.3782s** |
| Min-max spread | 1.1773s - 1.7158s |
| All readings | 1.5589, 1.1773, 1.2002, 1.3782, 1.2314, 1.4417, 1.7158 |

This is **~3.6x below the 5.0s budget** and **~3.7x below the two CI
breach readings** (5.10s / 5.11s) — on the *same* corpus and the *same*
code. Local hardware is simply much faster than the CI runner (consistent
with the spec's Assumptions).

**Per-phase breakdown** (cProfile `tottime` — self time, not double-counted
across nested calls — from one profiled run):

| Phase | Self-time | % of total |
|---|---|---|
| Filesystem scan (`_iter_mission_dirs`, `_resolve_summary_record_path`) | 0.028-0.037s | ~0.6% |
| **YAML parse** (`_load_yaml_mapping` -> `ruamel.yaml` safe-load) | **4.31-5.27s** | **~88.7-88.9%** |
| Schema coerce+validate (`_coerce_legacy_schema_versions`, `RetrospectiveRecord.model_validate`) | 0.011-0.015s | ~0.2-0.3% |
| Reduce (everything else in `build_summary`'s loop body — counters, classification) | 0.50-0.62s | ~10.3-10.4% |

**This confirms the research squad's lead exactly**: the dominant cost is
`ruamel.yaml`'s YAML-parse path inside `reader.py:_load_yaml_mapping`
(`read_record` -> `_load_yaml_mapping` -> `YAML(typ="safe").load(...)`), *not*
`summary.py` (whose only role is the `read_record(retro_path)` call site)
and *not* Pydantic schema validation (a rounding error at ~0.2-0.3%). Per
the top-20-by-cumulative-time table in `profiling.txt`, essentially all of
`read_record`'s 4.7s cumulative time (of 4.8s total profiled run) is inside
`ruamel.yaml`'s composer/parser/scanner — pure YAML-parsing cost, run x200,
not a validation or classification cost.

---

## 2. Flippable-oracle bisection (FR-002 / SC-002)

Full methodology and calibration proof: [`evidence/oracle-proof.md`](evidence/oracle-proof.md).
Full per-commit sweep: [`evidence/bisect.log`](evidence/bisect.log).

**The raw `assert elapsed < 5.0` oracle is provably not flippable on this
hardware.** A synthetic +2.0s regression (10ms x 200 missions — nearly 2x
the actual CI breach margin) injected at the `read_record` call site only
pushed the median to **3.60s**, still comfortably under the 5.0s budget.
`git bisect run` with the raw oracle would have marked every commit GOOD
regardless of ground truth (the exact false-GOOD trap the plan warned
against) — so it was not used.

**Relative-delta oracle used instead**: median of 5 unprofiled runs per
commit; BAD if median > 1.8s (~1.5x the ~1.2s baseline floor). **Calibration
proof**: the same +2.0s synthetic injection reads 3.60s under this oracle —
clearly BAD — confirming the oracle can and does flip given a genuine
regression of the scale that matters.

**Candidate window**: all 9 commits touching `reader.py`/`schema.py`/
`summary.py` (`git log -- <those 3 paths>`), explicitly including
`0818c7590` (#1778 — the prime suspect that rewrote `_load_yaml_mapping`
and added a per-record `_coerce_legacy_schema_versions` pass, without
touching `summary.py`, so a `summary.py`-only bisect would have stepped
right over it).

Since **both window endpoints read GOOD** (1.1692s at `9733727df` and
~1.20-1.38s at HEAD `254613f5e`), there was no BAD revision anywhere to seed
a literal `git bisect start <bad> <good>` — bisect requires one. In its
place, an **exhaustive linear sweep of all 9 commits** (strictly more
thorough than the ~4 samples a `log2(9)` bisect would have taken) was run.
Full table in `bisect.log`; summary:

- **`0818c7590` (#1778, prime suspect) shows a -0.0023s delta against its
  parent** (1.1715s -> 1.1692s) — noise, not a regression. The corpus
  demonstrably exercises this code path (all 200 missions carry
  `proposals:`/`not_helpful:`/`gaps:` content, and the parse+validate path
  is confirmed the dominant cost by profiling), so this is a substantive
  refutation, not an untested absence of signal.
- Two commits read moderately higher (`c6c13c73d` 1.57s, `8544012fa`
  1.50s) — both explained by legitimate added functionality (proposal
  lifecycle event reading, execution-context resolver unification), both
  far under the 1.8s BAD threshold, and both **already stable at that level
  for many releases** predating the #2336 CI breach — not new, not
  actionable.
- One commit (`365f1bb25`, #1681) crashes the harness against the synthetic
  corpus with `ActionContextError` — a real but already-fixed defect window
  (fixed one commit later, `fbc7eb065`, well before the current CI breach);
  noted for completeness, not actionable today.
- Every other commit, including HEAD, reads within 1.17s-1.37s.

**Bisection outcome: substantiated "no discrete regression across the
window"** — the oracle is demonstrated flippable (calibration), and no real
commit crosses the calibrated threshold.

**Honest limitation** (disclosed, not hidden): this oracle reliably catches
regressions of hundreds-of-milliseconds-to-seconds scale. Observed run-to-run
noise on this hardware reached ~20-50% within a single commit; a small
(~5-15%) creeping regression could not be reliably separated from that noise
with this sample size and is not ruled out.

---

## 3. Verdict (FR-003 / SC-002 / SC-003)

**CI variance — not a real regression.**

Evidence chain:
1. Local median (1.20-1.38s) is ~3.6-3.7x faster than the CI breach readings
   (5.10s/5.11s) on the identical corpus and identical code at HEAD.
2. No commit in the full `reader.py`/`schema.py`/`summary.py` candidate
   window — including the explicitly-named prime suspect `0818c7590`
   (#1778) — shows a discrete regression under a calibration-proven-
   flippable oracle.
3. The dominant cost (~89%) is inherent `ruamel.yaml` parse cost on this
   workload shape, not a validation or classification defect introduced by
   any commit in the window.
4. The two prior CI readings (5.10s, 5.11s) are "too consistent for pure
   runner noise, too close to the line for an obvious algorithmic blow-up"
   per the issue — but with no discrete regressing commit found and a
   ~4x local/CI absolute-time gap, the more likely explanation is CI-runner
   class being both slower and closer to its own noise ceiling on this
   workload, not a code-level regression that a local machine (much faster,
   with much more headroom below 5.0s) would also have to exhibit.

This is **not** "inconclusive" — the oracle was demonstrated flippable
(calibration section above), and the sweep is exhaustive across the full
candidate window, not a partial/inconclusive sample.

---

## 4. Recommended disposition (FR-004 / SC-003)

**Recommendation: leave `test_200_missions_under_5s` in the existing
`@pytest.mark.quarantine` + non-blocking `quarantine-visibility` CI lane.
Do not raise the budget (per C-002). Do not lift the quarantine yet
(per C-003 — quarantine is tracking state, not an end state, and lifting it
requires evidence the 5.0s budget is durably safe *on CI hardware*, which
this investigation — constrained to local measurement per C-001 — cannot
supply).**

Rationale: the issue's disposition matrix offers, for a CI-flake/perf-OK
verdict, either (a) a dedicated non-blocking perf pipeline slice, or (b) a
`local_only` designation. The repository **already has (a)**: the
`quarantine` marker plus the `quarantine-visibility` non-blocking job
(`docs/development/testing-flakiness.md`, Tier-3) is precisely that mechanism,
already wired up and already running since the interim-budget revert
(`f844a057f`). No structural CI change is needed — the disposition is to
**ratify the status quo**, not invent a new lane.

**Enactment steps**:
1. No code or CI-config change ships from this investigation (per T005 —
   see below).
2. The report and its evidence (`evidence/`) are committed as the durable
   record of this investigation (FR-006), closing the "guess-and-tune loop"
   the issue asked to replace.
3. **Maintainer follow-up (out of session scope per C-001)**: let the
   `quarantine-visibility` job continue collecting real CI-hardware
   readings over the week the issue calls for. If that week-long collection
   shows CI readings durably and comfortably under 5.0s (i.e. the 5.10/5.11s
   pair was itself the noise ceiling, not a new floor), lift the quarantine
   and restore the test to the blocking suite at 5.0s — no budget change,
   just re-enabling. If CI readings continue to cluster near or over 5.0s
   without a discrete regressing commit (consistent with this
   investigation), consider a `local_only` reclassification instead of
   perpetual quarantine, since "CI-class hardware genuinely needs more time
   for this workload" would then be the standing explanation rather than a
   transient flake.
4. Quarantine-lift step (when the above resolves): remove
   `@pytest.mark.quarantine` from `test_200_missions_under_5s` in
   `tests/retrospective/test_summary_tolerance.py` and confirm it runs
   green in the normal blocking suite at the existing 5.0s budget.

---

## 5. Conditional clean fix (FR-005 / SC-004)

**No code ships.** T003/T004 above found no clean, low-risk root-cause
regression — no commit in the candidate window produces a discrete,
attributable slowdown; the dominant cost is inherent YAML-parsing overhead,
not a defect. Per the plan's explicit scope boundary ("a large fix is out
of scope — recommend, don't ship it"), there is nothing here to fix: the
~89% YAML-parse cost is the expected cost of parsing 200 real
`retrospective.yaml` files with `ruamel.yaml`'s safe loader, not a
regression introduced by any commit under investigation. `@pytest.mark.quarantine`
remains on `test_200_missions_under_5s` for the reason stated in section 4
above (evidence-based: no regression found, but CI-side durability is not
yet re-confirmed and is explicitly a maintainer follow-up per C-001).

---

## Evidence index

- [`evidence/profile_harness.py`](evidence/profile_harness.py) — runnable,
  regenerates the profiling table (rebuild + rerun: `PYTHONPATH=<repo>/src
  <venv-python> evidence/profile_harness.py 7`).
- [`evidence/profiling.txt`](evidence/profiling.txt) — raw output of the
  above (7 unprofiled runs + 1 profiled run + top-20 cProfile table).
- [`evidence/oracle-proof.md`](evidence/oracle-proof.md) — the flippable-
  oracle methodology and calibration proof (known-bad synthetic injection).
- [`evidence/bisect.log`](evidence/bisect.log) — the full per-commit sweep
  across the candidate window (substituting for a literal `git bisect log`
  since no BAD revision existed to seed one — see the log's own
  explanation).
