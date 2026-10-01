# CI measurements: ci-runtime-stabilisation (#5510, PR #5557)

Evidence for constraint C-011. Every figure below cites the workflow run it came from. Measurements are taken from the GitHub Actions API (`runs/{id}/attempts/{n}/jobs`) and the job logs; minutes are measured from the run's `run_started_at`.

## Runs measured

All runs are `pull_request` runs of PR #5557 at head `e01c3b1efd`, re-run three times to get three samples on the same tree.

| Workflow | Run ID | Attempts | Conclusion |
|---|---|---|---|
| CI Router | [36902986249](https://github.com/spec-kitty/spec-kitty/actions/runs/36902986249) | 1, 2, 3 | success × 3 |
| CI Modules | [36902986539](https://github.com/spec-kitty/spec-kitty/actions/runs/36902986539) | 1, 2, 3 | success × 3 |
| CI Aggregate (for CI Modules attempt 1) | [36904109139](https://github.com/spec-kitty/spec-kitty/actions/runs/36904109139) | 1 | success |

**Why no dispatched runs:** the PR comes from a fork, and a `workflow_dispatch` can only target a branch in `spec-kitty/spec-kitty`. The pr- and full-mode dispatches that C-011 names, and the nightly-only measurements, are therefore listed as post-merge below.

## Battery jobs per attempt (CI Router 36902986249)

| Attempt | Fast gate job: duration / end | Heavy leg 1/2: duration / end | Heavy leg 2/2: duration / end | Router gate end |
|---|---|---|---|---|
| 1 | 3.60 / 3.67 min | 11.70 / 12.33 min | 7.37 / 8.00 min | 12.77 min |
| 2 | 3.58 / 3.70 min | 10.55 / 11.08 min | 9.63 / 10.13 min | 11.52 min |
| 3 | 3.90 / 4.03 min | 10.45 / 10.97 min | 9.98 / 10.48 min | 11.35 min |

Job IDs:
- Attempt 1: fast 110506436160, leg 1/2 110506674119, leg 2/2 110506674265.
- Attempt 2: fast 110513521325, leg 1/2 110513695214, leg 2/2 110513695320.
- Attempt 3: fast 110518726085, leg 1/2 110518895839, leg 2/2 110518895700.

## Requirements

| Requirement | Bound | Measured | Verdict |
|---|---|---|---|
| NFR-001 battery wallclock (slowest of fast job and both legs) | median ≤ 14 min (baseline 23.4) | 11.70, 10.55, 10.45 min; median **10.55 min** | pass |
| SC-001 full architectural verdict (pipeline start → last battery job) | median ≤ 15 min (baseline ≈ 25) | 12.33, 11.08, 10.97 min; median **11.08 min** | pass |
| NFR-002 / SC-002 early red (pipeline start → fast gate job conclusion) | ≤ 5 min in ≥ 3 runs (baseline 16–25) | 3.67, 3.70, 4.03 min | pass |
| NFR-003 timeouts | fast gate and heavy legs ≤ 30 min; backstop ≤ 40 min | fast gate 10 min, heavy legs 30 min, backstop 40 min (`ci-router.yml`, `ci-nightly.yml`) | pass |
| NFR-003 headroom (slowest run ≤ 60% of the job timeout) | ≤ 60% | fast gate 3.90 / 10 = 39%; heavy legs 11.70 / 30 = 39% | pass |
| NFR-003 per-test timeout failures | 0 | 0 in all 9 battery jobs | pass |
| NFR-003 slowest single battery test | ≤ 180 s | 226.45, 217.51, 216.56 s for `test_interpreter_shard_coverage.py::test_no_shard_collects_zero_tests` | **breach on `e01c3b1efd`, fixed** in `9f6755daf8` (one case per shard): slowest is **114.14 s** on the fixed head (see below) |
| NFR-004 duplicate selections | 0 overlaps outside the allowlist; allowlist ≤ 10 entries, each reasoned | `test_same_tier_uniqueness.py::test_no_per_change_overlap_outside_the_allowlist` green in all three attempts; 4 allowlist entries, each with a reason | pass |
| NFR-005 peak memory per battery job (memory sampler `peak_rss_bytes`) | < 12 GiB on the 16 GiB runner | attempt 1: fast 3.48, leg 1/2 5.02, leg 2/2 4.86 GiB. Attempt 2: fast 3.46, leg 1/2 4.55, leg 2/2 5.04 GiB. Attempt 3: fast 3.93, leg 1/2 5.00, leg 2/2 5.46 GiB. Max **5.46 GiB** | pass |
| SC-006 a CI-configuration change runs the architectural gates on its own PR | the battery runs | this PR changes only workflows, `scripts/ci`, tests and the registry and timings; the `ci_config` group selected the fast job and both heavy legs in all three attempts | pass |
| SC-004 duplicate per-PR selections | 0 outside an allowlist of ≤ 10 | same as NFR-004 | pass |

### Re-measurement on the fixed head

[CI Router 36908397259](https://github.com/spec-kitty/spec-kitty/actions/runs/36908397259) ran at head `18c41d9898`, which carries `9f6755daf8`:

| Job | Duration / end | Peak memory | Slowest test |
|---|---|---|---|
| Fast gate job (110524641195) | 4.12 / 4.18 min | 3.99 GiB | 25.06 s |
| Heavy leg 1/2 (110524816030) | 10.58 / 11.08 min | 5.02 GiB | 83.68 s, `test_shard_union_equals_full_selection_with_zero_gap_and_zero_overlap` (each per-shard zero-test case ≤ 64.28 s) |
| Heavy leg 2/2 (110524816381) | 6.52 / 7.02 min | 5.36 GiB | 114.14 s, `test_same_tier_uniqueness.py` fixture setup |

- The slowest battery test is now 114.14 s, which meets NFR-003's ≤ 180 s.
- SC-001: the last battery job ended at 11.08 min. SC-002: the fast gate job ended at 4.18 min.

### Second-slowest battery test

The second-slowest battery test is the fixture setup of `test_same_tier_uniqueness.py`, which runs one full `gc.collect_universe()`. It took 114.07, 166.23 and 170.35 s. That is inside the 180 s bound, with the margin shrinking. Several battery files repeat the same full-tree collection; sharing one collection across files is tracked in #5559. Neither this test nor any other came within reach of the 240 s per-test timeout.

### Leg balance

The legs were predicted to be equal (1126.6 / 1126.5 worker-seconds from the seeded timings). Measured, they differed by 37% in attempt 1 (11.70 vs 7.37 min), then by 9% and 5% in attempts 2 and 3. Leg 1/2 holds `test_interpreter_shard_coverage.py`, whose collection-heavy test the NFR-003 fix splits.

## CI Modules (36902986539), for context

| Attempt | `ci` shard | `release` shard |
|---|---|---|
| 1 | 8.10 min | 3.27 min |
| 2 | 8.70 min | 3.22 min |
| 3 | 8.63 min | 3.47 min |

## Not measurable before merge

Each of these needs `main`, a same-repository branch, or the nightly.

- **NFR-006 consolidation shard duration and balance:** the two new consolidation shards only run when a diff touches the consolidation module, or in full mode (`ci-modules.yml -f mode=full`, or the nightly `full-module-matrix`). This PR touches neither. Measure from the first nightly after merge.
- **NFR-003 backstop headroom (slowest backstop run ≤ 24 min) and SC-003 (the nightly runs 100% of the battery):** `architectural-backstop` runs only in `ci-nightly.yml`. The structural guarantee is pinned by `tests/ci/test_nightly_architectural_backstop.py`. Measure from the first nightly after merge.
- **SC-005 (an already-green commit marked ready for review consumes no expensive jobs) and the CI Aggregate re-point:** fork PRs never skip, by design. `ci-aggregate.yml` is a `workflow_run` workflow and runs from `main`. Tracked in #5553.
