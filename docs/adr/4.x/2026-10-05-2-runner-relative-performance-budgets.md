---
title: 'ADR: owned-checkout and start-up performance tests assert runner-relative ratios'
description: 'Start-up tests assert the ratio of a command median to a start-up floor or fixed workload sampled in the same run, not an absolute 2.5 s; limits are provisional.'
status: Accepted
date: '2026-10-05'
updated: '2026-10-05'
---

**Status:** Accepted

**Date:** 2026-10-05

**Deciders:** Stijn Dejongh (owner). Design decisions D4 and D5 of Mission `nightly-suites-green-01M44FEP`; the floor command, throttle method, workload and limits below are the work package's own calibration.

**Technical Story:** [#5419](https://github.com/spec-kitty/spec-kitty/issues/5419), [#5614](https://github.com/spec-kitty/spec-kitty/issues/5614), Mission `nightly-suites-green-01M44FEP` (WP05, FR-007 to FR-012, NFR-001 to NFR-003).

---

## Context and Problem Statement

Three owned-checkout performance tests (`agent tasks status`, `agent mission setup-plan`, `agent context resolve`) compared the median of five fresh `python -m specify_cli` runs with an absolute 2.5 s budget. The shared nightly runner is not a constant. A bare `--help` alone moved from 1.14 s to 1.95 s between nightly runs with no product change, and the job went red on four of the last six nightlies. Two more tests carried absolute limits too: a single-shot `--help` against 2.5 s, and a warm second `context list --json` call against 5.0 s.

The nightly data (xunit of six runs):

| Run | Head | `--help` | Owned medians | Owned / `--help` | Absolute 2.5 s |
|---|---|---|---|---|---|
| 36811585861 | `f4dc26694c` | 1.95 | 2.71 / 2.85 / 2.76 | 1.46 | red |
| 36920764277 | `3546f35be7` | 1.83 | 2.65 / 2.72 / 2.62 | 1.48 | red |
| 36960774283 | `d79a12928b` | 1.14 | about 1.54 | about 1.35 | green |
| 37094126479 | `a3f76f673a` | 1.76 | about 1.88 | about 1.07 | green |
| 37177460494 | `b2c466d7d1` | 1.94 | 2.60 / 2.70 / 2.60 | 1.39 | red |
| 37225822329 | `9adc68803f` | 1.72 | 2.52 / 2.59 / 2.54 | 1.51 | red |

The ratio of an owned command to a floor measured in the same run stayed between 1.35 and 1.51 across the same runs (the 1.07 row comes from a single-shot denominator).

`testing-flakiness.md` says a budget is tuned only with evidence, never by retry, and that shared-runner wall clock is not accepted as evidence.

## Status of the figures

The limits are **provisional**. They come from local calibration on one machine under shared load, and the robustness proofs were cut short on the operator's instruction (see "Robustness runs"). They are to be re-checked against real CI-runner data from a nightly run on the branch. The tests record `ratio`, the floor (or workload) median and the command median as xunit properties on pass as well as on failure, so a nightly report can be read for that calibration.

## Decision

1. **Owned-checkout tests assert a ratio.** Each test samples the command and a **start-up floor** interleaved in one run, five spawns of each (the order flips on odd rounds), and asserts `median(command) / median(floor)` through `assert_timing_budget` against `OWNED_CHECKOUT_RATIO_LIMIT = 1.78`. The assertion name carries both medians, the ratio, the limit and the raw samples.
2. **Start-up tests assert against a fixed interpreter workload.** The bare `--help` test and the warm `context list --json` test divide their median by the median of a fixed interpreter workload (a fresh interpreter that imports 22 standard-library modules and then compiles 12,000 generated functions; no product code), sampled interleaved in the same run, against `STARTUP_RATIO_LIMIT = 2.90` and `WARM_LEAF_RATIO_LIMIT = 6.0`. No absolute number of seconds remains in any of the three files or the helper.
3. **One authority.** Every limit, every sample count and the measuring helper live in `tests/_perf_helpers.py`. `tests/architectural/test_perf_limit_authority.py` fails when a test file that times a CLI spawn defines its own numeric limit. It has no allowlist, and lives in the architectural tree because no job runs an unmarked test in `tests/performance`.
4. **Each assertion is proved able to fail.** Two committed planted-work tests write a fixed-iteration CPU-bound loop into a `sitecustomize.py` first on the child's `PYTHONPATH` (test side only, no product hook, chained to any later `sitecustomize`). The owned-checkout plant runs only for an `agent` command, so the floor is untouched. The plant's measured cost (planted median minus clean median, interleaved) must lie inside a band, and the same limit constant must then reject the planted ratio. The bands and plant sizes were set at 0.3 to 0.7 of the floor (12,000,000 and 10,000,000 iterations) and re-set from CI data in "CI calibration, sample 1" below: owned 0.62 to 1.30 of the floor at 20,000,000 iterations; start-up 0.45 to 1.10 of the clean `--help` at 15,000,000 (upper edges widened after "CI calibration, sample 2").
5. **The previous assertion is a committed positive control.** The six nightly rows above run through the helper as injected timings: the 2.5 s assertion is red on the four rows the nightly reported red and green on the two it reported green; the ratio assertion is green on all six.

### Floor command: `--version`

Candidates, 10 rounds each, one isolated `SPEC_KITTY_HOME`, idle and under a 45 percent quota (the first throttle tried; the 50 percent quota below was chosen afterwards to land the floor at about 2.0 s). Median ratio of owned command to floor:

| Floor | Idle floor | Idle ratio | Throttled floor | Throttled ratio |
|---|---|---|---|---|
| `--version` | 1.01 s | 1.37 to 1.41 | 2.60 s | 1.44 to 1.56 |
| `--help` (root) | 1.00 s | 1.38 to 1.42 | 2.63 s | 1.43 to 1.54 |
| `agent --help` | 1.41 s | 0.98 to 1.00 | 3.68 s | 1.02 to 1.10 |
| `import specify_cli` | 0.14 s | 10.1 to 10.4 | 0.40 s | 9.5 to 10.3 |

`import specify_cli` is not a start-up floor: at 0.14 s the ratio is dominated by interpreter spawn noise. `agent --help` has a similar relative spread to the other two, but it shares the owned commands' import chain, so a regression in that chain moves floor and command together and stays invisible; its ratio of about 1.0 also leaves the limit no room above clean. `--version` and the root `--help` cost the same (1.01 s and 1.00 s, both 1658 modules in-process) and have the same spread. `--version` was chosen because it has the same cost as the `--help` the nightly evidence is about, takes no help-rendering path, and still pays the full CLI import, including the owned commands' import chain, so a regression there raises the ratio.

### Throttle: a cgroup CPU quota

`systemd-run --user --scope -p CPUQuota=50%` runs the whole pytest process, with its children, on half a CPU. The start-up floor then measures 2.0 to 2.1 s on a quiet machine (idle 0.97 s), above the 1.9 s the slowest nightly showed, and every owned-command median exceeds the old 2.5 s. Burners pinned to one core with `taskset` were tried first and slowed the floor only 1.4 times with one burner and 1.7 times with two; the quota is deterministic and does not depend on what else the machine is doing.

Red first for the previous assertion, base `7a59ab8339`, quota 50 percent, load1 2.45, floor about 2.0 s:

```
AssertionError: agent tasks status owned median-of-5;  budget exceeded: measured=2.8990914300084114 > budget=2.5
AssertionError: agent mission setup-plan owned median-of-5;  budget exceeded: measured=2.9973015199939255 > budget=2.5
AssertionError: agent context resolve owned median-of-5;  budget exceeded: measured=2.901110578008229 > budget=2.5
```

Across the 180 clean throttled owned measurements below, every owned-command median was between 2.70 s and 4.40 s, all above 2.5 s.

### Calibration data

Machine: AMD Ryzen 9 7950X3D, 32 logical cores, Python 3.11.15, lane commit `b7142503eb` plus the helper commits. Sampling as in the tests: 5 floor and 5 command spawns per ratio, interleaved. Other agents ran pytest on the machine throughout, so the load1 shown beside each series (taken before each sample) is often above the 3 the series ought to start from. The throttled series ran concurrently with the idle ones on separate fixtures and separate `SPEC_KITTY_HOME` directories. The orchestrator re-runs the 30 and 10 proofs on a quiet machine at closeout.

**Owned-checkout clean ratios** (command median over `--version` median; 30 samples per command per series; two independent series per condition):

| Condition | Series | status | setup-plan | context resolve | load1 |
|---|---|---|---|---|---|
| idle | A | 1.288 to 1.398 | 1.327 to 1.467 | 1.300 to 1.445 | 5.5 to 17.6 |
| idle | B | 1.290 to 1.423 | 1.336 to 1.480 | 1.302 to 1.407 | 2.8 to 18.1 |
| throttled 50% | A | 1.245 to 1.521 | 1.282 to 1.650 | 1.210 to 1.525 | 4.3 to 18.6 |
| throttled 50% | B | 1.332 to 1.535 | 1.347 to 1.495 | 1.320 to 1.532 | 1.3 to 17.3 |

All 360 clean ratios: 1.210 to 1.650. Medians per command lie between 1.357 and 1.414. The three largest values are 1.650 (setup-plan, load1 10.6, floor 2.61 s), 1.581 and 1.535. Floors: idle 0.99 to 1.31 s, throttled 1.88 to 2.99 s.

**Owned-checkout planted ratios** (`agent tasks status`, plant on the command only, floor and clean command interleaved):

| Condition | Plant iterations | Samples | Planted ratio | Clean ratio | Plant cost, fraction of floor | load1 |
|---|---|---|---|---|---|---|
| idle | 10,000,000 | 10 | 1.798 to 1.911 | 1.332 to 1.423 | 0.42 to 0.51 | 6.0 to 10.7 |
| idle | 11,000,000 | 10 | 1.802 to 1.892 | 1.313 to 1.395 | 0.45 to 0.51 | 5.6 to 7.7 |
| idle | 12,000,000 | 15 | 1.884 to 1.982 | 1.325 to 1.410 | 0.52 to 0.58 | 3.1 to 4.9 |
| throttled 50% | 10,000,000 | 10 | 1.724 to 1.959 | 1.273 to 1.396 | 0.43 to 0.60 | 5.4 to 10.7 |
| throttled 50% | 11,000,000 | 10 | 1.844 to 1.899 | 1.349 to 1.417 | 0.45 to 0.53 | 2.7 to 6.4 |
| throttled 50% | 12,000,000 | 15 | 1.853 to 2.008 | 1.286 to 1.455 | 0.53 to 0.60 | 2.4 to 4.9 |

The first committed plant was 12,000,000 iterations (since enlarged, see "CI calibration, sample 1"), about 0.56 of the floor (0.5 s of CPU per 10 million iterations on the calibration machine; the loop runs at about 47 ns per iteration). It started at 10,000,000, went to 11,000,000 and then to 12,000,000: the first count put the realised cost slightly under half the floor, and a robustness campaign (below) showed the clean tail reaching the first limit, so the plant was enlarged to widen the gap to a limit that clears that tail while staying inside the 0.3 to 0.7 band.

**Start-up measures** (30 clean samples per row, 10 planted, 5 regressed):

| Measure | Condition | Ratio | Notes |
|---|---|---|---|
| `--help` over fixed workload, clean | idle | 2.235 to 2.484 | workload 0.44 to 0.49 s, `--help` 0.98 to 1.20 s |
| `--help` over fixed workload, clean | throttled | 2.120 to 2.594 | workload 0.90 to 1.34 s |
| `--help` over fixed workload, planted (10,000,000 iterations) | idle | 3.249 to 3.509 | plant cost 0.41 to 0.51 of clean `--help` |
| `--help` over fixed workload, planted | throttled | 3.233 to 3.575 | plant cost 0.38 to 0.50 of clean `--help` |
| warm `context list --json` over fixed workload | idle | 2.499 to 2.964 | leaf 1.11 to 1.49 s |
| warm `context list --json` over fixed workload | throttled | 2.453 to 2.628 | leaf 2.19 to 2.69 s |
| from-scratch render (fresh home each call), the regression | idle | 12.7 to 14.3 | leaf 5.7 to 7.8 s |
| from-scratch render, the regression | throttled | 12.6 to 13.0 | leaf 11.2 to 11.9 s |

The fixed workload imports `argparse asyncio csv dataclasses decimal difflib email.message fractions http.client json logging pathlib pickle re shutil sqlite3 subprocess tempfile typing unittest urllib.request xml.etree.ElementTree` and then compiles 12,000 generated functions. Standard-library imports alone cost 0.07 to 0.10 s against a 1.0 s start-up, a denominator too small for a stable ratio; the compile step brings it to about 0.45 s and adds the parse, compile and allocate work import itself spends its time on.

### Limits and headroom

| Limit | Value | Largest clean | Smallest planted or regressed | Headroom |
|---|---|---|---|---|
| `OWNED_CHECKOUT_RATIO_LIMIT` | 1.78 | 1.650 in 360 calibration ratios; one further evaluation in the robustness campaign exceeded 1.70 (value not captured) | 1.853 planted (30 samples at the committed plant) | 8 percent above the largest calibration value, 4 percent below the smallest planted value; 18 percent above the largest nightly ratio (1.51); 28 percent above the median clean ratio |
| `STARTUP_RATIO_LIMIT` | 2.90 | 2.594 | 3.233 planted | 12 percent above clean, 11 percent below planted |
| `WARM_LEAF_RATIO_LIMIT` | 6.0 | 2.964 | 12.6 regressed | twice the largest clean value, under half the smallest regressed one |

Clean and planted ranges separate in every calibration series, but for the owned-checkout measure only narrowly, and the tails touch: the clean tail under contention reaches at least 1.70 while the smallest planted ratio at the committed plant is 1.853. The owned-checkout limit was first set at 1.70 (between the 1.650 clean maximum and the 1.724 planted minimum of the 10,000,000-iteration series) and one evaluation in a robustness campaign went red at that limit with no regression. The limit was then raised to 1.78 and the plant enlarged to 12,000,000 iterations to widen the gap; that change was not re-proved with a full campaign. If a clean ratio at or above 1.78 shows up in a CI run, re-measure and record before touching the limit.

### Robustness runs

Run against the committed tests, one pytest process per run, with the throttle applied to the whole process. Load1 was often well above 3 because other agents ran pytest on the machine.

| Series | Constants | Result | Status |
|---|---|---|---|
| three owned tests, throttled 50%, 30 runs (load1 2.6 to 16.0) | limit 1.70, plant 11,000,000 | 29 of 30 green; run 11 red (load1 4.4, concurrent with other series of this work) | complete; this is the evidence that led to 1.78 |
| planted owned test, idle, 10 runs | 1.70, 11,000,000 | 10 of 10 pass (the assertion failed as expected) | complete |
| planted owned test, throttled 50%, 10 runs | 1.70, 11,000,000 | 10 of 10 pass | complete |
| start-up tests (`--help`, planted `--help`, warm leaf), idle, 10 runs | 2.90, 6.0 | 10 of 10 green | complete |
| start-up tests, throttled 50%, 10 runs | 2.90, 6.0 | 10 of 10 green | complete |
| three owned tests, throttled 50%, 30 runs | limit 1.78, plant 12,000,000 | 5 of 5 green (load1 2.0 to 14.0) | **cut short at run 5 of 30** |

There is no 30 of 30 at the final constants, and no 10 of 10 planted run at the final plant (the 12,000,000 plant is covered by 30 calibration samples only: 15 idle and 15 throttled, all above the 1.78 limit). The orchestrator re-runs these proofs at closeout.

### Sample counts and suite cost

Five floor and five command spawns per assertion (`SAMPLE_RUNS`). The owned-checkout file (fixture, three tests, planted test) takes about 65 s on an idle machine (one serial run of the whole file at the 11,000,000 plant: fixture 7 s, three tests 12 s each, planted test 22 s), against the NFR-003 ceiling of 90 s.

## Considered Options

1. **Ratio to a start-up floor measured in the same run (chosen).** Removes runner speed from the result; a planted slowdown lands at 1.72 or above (1.85 at the committed plant) against a clean maximum of 1.65 in the calibration series.
2. **Delta over the floor.** Still runner-bound: in the grounding probe a delta doubled under load while the ratio moved from 1.34 to 1.51.
3. **One wider absolute budget.** The same test moves 1.7 times between nightlies; any budget generous enough to be green on the worst nightly stops catching a regression on the best one.
4. **Count proxies alone** (git subprocesses per command). A count is exact and runs on pull requests, but it is blind to a CPU slowdown. The count pin (WP06) complements this record; it does not replace it.

## Consequences

- The nightly `performance` job no longer depends on the speed of the runner for these five tests.
- The measures are real subprocess runs, so a failure names both medians, the ratio, the limit and the raw samples: a nightly red is diagnosable without a re-run.
- A regression that slows the floor and the command alike (a slower interpreter start, an import in the shared chain) is invisible to the owned-checkout ratio. The start-up tests (`--help` and the warm leaf against the fixed workload) and the git-subprocess count pin cover part of that; a regression confined to the standard-library workload's own cost is covered by neither.
- The plant loop is CPU-bound with a fixed iteration count. On a Python build where that loop runs much faster or slower relative to import than on the calibration machine, the plant's cost can leave its band (see "CI calibration, sample 1") and the planted test fails loudly instead of passing vacuously; the iteration count would then be recalibrated and recorded here. Staying inside the band is not enough, though, unless the band's lower edge clears the detection threshold: the planted test goes red (the plant is not detected) when the plant's cost is below roughly the limit minus the clean ratio. The first bands did not guarantee that (see "CI calibration, sample 1"). The planted tests record `planted_ratio`, `clean_ratio`, `plant_cost_fraction` and the medians as xunit properties before asserting, and the not-detected failure message carries the same figures.
- **The calibration is tied to the pinned interpreter.** `.python-version` pins 3.11.15, which the figures above were measured on. The fixed workload costs about 0.43 s on 3.11, 0.53 s on 3.12 and 0.66 s on 3.14 (reviewer measurement), so the start-up ratios shift with the interpreter. A bump of the pin needs a recalibration of every limit and of the plant iteration counts.
- **Remedy if the owned measure goes red on CI.** The remedy is more samples or a larger plant, not a wider limit.

### Questions the first nightly runs must answer

1. The largest clean owned-checkout ratio per command, against 1.78 (the `ratio` property of the three owned tests).
2. The smallest planted ratio and the plant cost fraction (`planted_ratio`, `plant_cost_fraction`), against the limit and the plant bands (owned 0.62 to 1.15 of the floor; start-up 0.45 to 0.90 of the clean `--help`).
3. The `--help` and warm-leaf ratios against 2.90 and 6.0.
4. The wall clock of the whole `performance` job against its 35-minute timeout.
- No retry was added anywhere.

## CI calibration, sample 1 (#5753)

Sample 1 is nightly run 37307043614: GitHub-hosted runner, Python 3.11, `performance` job green. It is the first real runner data for the provisional limits above. The limits are unchanged.

| Measure | Value | Limit or band |
|---|---|---|
| Owned clean ratio (`tasks status` / `setup-plan` / `context resolve`) | 1.321 / 1.473 / 1.227 | at most 1.78 |
| Owned planted test (12,000,000 iterations) | clean 1.315, planted **1.806**, plant cost 0.491 of the floor; floor 1.141 s, clean median 1.501 s, planted median 2.062 s | planted must exceed 1.78: margin 1.5 percent |
| Start-up clean ratio (`--help`) | 2.482 (command 1.220 s, workload 0.492 s) | at most 2.90 |
| Start-up planted test (10,000,000 iterations) | clean 2.459, planted 3.329, plant cost **0.354** of the clean `--help`; clean median 1.204 s, planted median 1.630 s, workload 0.490 s | planted must exceed 2.90; band 0.30 to 0.70 |
| Warm leaf ratio | 2.491 | at most 6.0 |

The clean assertions have room. The two planted tests did not:

- **Owned.** The planted ratio is about the clean ratio plus the plant's cost fraction. The runner's clean ratios ranged 1.23 to 1.47, so a plant costing 0.49 of the floor gives about 1.72 when the clean ratio is low: below 1.78, "planted work not detected", a red nightly without a product change. The plant cost is a fraction of the start-up **floor** median (`--version`), and the old band (0.3 to 0.7) had a lower edge below the detection threshold of 1.78 minus 1.21 = 0.57.
- **Start-up.** The plant cost is a fraction of the **clean `--help` median** (not of the workload). The ratio under test is `--help` over the workload, so a plant of fraction f multiplies the clean ratio by 1 + f; it is detected when f exceeds 2.90 / (clean ratio) - 1, which is 0.368 at the lowest clean ratio (2.12). The old lower edge 0.30 was below that, and the runner's 0.354 sat just above the edge.

Per the rule in "Consequences", the remedy is a larger plant, not a wider limit. Cost per iteration is linear: 46.7 ns on the runner for the owned plant (0.491 times 1.141 s over 12,000,000), 42.6 ns for the start-up plant (0.354 times 1.204 s over 10,000,000), about 43 to 46 ns locally.

| Test | Iterations (was) | Band (was) | Runner cost fraction | Local cost fraction |
|---|---|---|---|---|
| Owned, of the floor | 20,000,000 (12,000,000) | 0.62 to 1.15, widened to 1.30 in sample 2 (0.30 to 0.70) | 0.82 | 0.87 to 1.00 expected; 0.927 measured |
| Start-up, of the clean `--help` | 15,000,000 (10,000,000) | 0.45 to 0.90, widened to 1.10 in sample 2 (0.30 to 0.70) | 0.53 | 0.57 to 0.77 expected; 0.740 measured |

Bands are now per test (`OWNED_PLANT_*_FRACTION_OF_FLOOR`, `STARTUP_PLANT_*_FRACTION_OF_CLEAN` in `tests/_perf_helpers.py`). The two band edges mean:

- **Lower edge: an in-band plant is always detected.** Owned: 1.21 (lowest clean ratio, `OWNED_LOWEST_CLEAN_RATIO`) plus 0.62 is 1.83, above 1.78. Start-up: 2.12 (`STARTUP_LOWEST_CLEAN_RATIO`) times 1.45 is 3.07, above 2.90.
- **Upper edge: an oversized plant cannot pass under any limit.** An in-band plant is still detected at a limit up to 1.21 plus 1.15 = 2.36 (owned, 33 percent above 1.78) and 2.12 times 1.90 = 4.03 (start-up, 39 percent above 2.90). `tests/architectural/test_perf_limit_authority.py` pins both facts.

Headroom of the planted ratio over the limit at the lowest observed clean ratio: owned 1.21 plus 0.82 (runner cost) = 2.03, 14 percent above 1.78 (it was 1.21 plus 0.49 = 1.70, below); start-up 2.12 times 1.53 = 3.25, 12 percent above 2.90. Local readings after the change, one run each: owned plant cost 0.927, clean 1.491, planted 2.418 (floor 0.934 s); start-up plant cost 0.740, clean 2.170, planted 3.777.

**What remains.** The new plants are unproven on the runner until a nightly runs them. A second sample from the nightly on `main` is to confirm the cost fractions land inside the bands (owned about 0.82, start-up about 0.53) and the planted ratios above the limits. The limits (1.78, 2.90, 6.0) are unchanged and remain provisional on the clean side as before.

## CI calibration, sample 2 (#5753)

Sample 2 is nightly run 37352245083 on `main` at 3e47f5a4cb: GitHub-hosted runner, with the old plants (12,000,000 iterations owned, 10,000,000 start-up). It ran on a different runner instance than sample 1. The limits are unchanged.

| Measure | Value | Limit or band |
|---|---|---|
| Owned clean ratio (three commands) | 1.363 / 1.397 / 1.376 | at most 1.78 |
| Owned planted test (12,000,000 iterations) | clean 1.353, planted 1.940, plant cost fraction **0.5875** (sample 1: 0.491) | planted must exceed 1.78 |
| Start-up clean ratio (`--help`) | 2.288 | at most 2.90 |
| Warm leaf ratio | 2.418 | at most 6.0 |
| Start-up planted test (10,000,000 iterations) | clean 2.308, planted 3.542, plant cost fraction **0.5345** (sample 1: 0.354) | planted must exceed 2.90 |

The clean ratios in both samples sit well inside the limits: owned at most 1.47 against 1.78, start-up at most 2.48 against 2.90, warm leaf at most 2.49 against 6.0.

The plant cost fraction varies a lot between runner instances: owned 0.49 to 0.59, start-up 0.35 to 0.53 at the old sizes, a spread of 20 percent and 50 percent. Scaled linearly to the current plant sizes (owned 20,000,000 is times 1.667, start-up 15,000,000 is times 1.5), the runner would give owned 0.82 to 0.98 and start-up 0.53 to 0.80; local readings are owned 0.87 to 1.00 (0.95 measured) and start-up 0.57 to 0.77 (0.71 and 0.74 measured). The upper edges set after sample 1 (1.15 and 0.90) left only 12 to 17 percent above the highest scaled runner value, too little for that spread.

Decision: raise only the two upper edges, to `OWNED_PLANT_MAX_FRACTION_OF_FLOOR = 1.30` (33 percent above 0.98) and `STARTUP_PLANT_MAX_FRACTION_OF_CLEAN = 1.10` (37 percent above 0.80). Iteration counts, lower edges (0.62 and 0.45) and the three ratio limits are unchanged. An in-band plant is now detected at a limit up to 1.21 plus 1.30 = 2.51 (owned, 41 percent above 1.78) and 2.12 times 2.10 = 4.45 (start-up, 53 percent above 2.90). The width test in `tests/architectural/test_perf_limit_authority.py` therefore pins "at most 1.6 times the limit" instead of 1.4 times. The band still bounds an oversized plant: a plant that costs much more than intended leaves the band and fails loudly.

**What remains.** The new plant sizes themselves are still unproven on the runner: both samples ran the old sizes and the new fractions are scaled, not measured. A third sample from a nightly that runs the new plants is to confirm the realised fractions land inside the bands and the planted ratios above the limits.
